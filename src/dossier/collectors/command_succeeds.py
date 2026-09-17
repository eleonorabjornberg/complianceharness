"""The collector that runs a command the subject declares.

The document collectors read what a subject says about itself; this one
watches what it does. A claim that names a command is answered by
running that command inside the subject and reading its exit status —
the first collector whose evidence is a behaviour rather than a document.

Because running code is the strongest thing a collector does, it is the
only one behind a two-party opt-in, and neither party is enough alone:

    the SUBJECT  declares its commands in .dossier.json at its root —
                 a name mapped to an argv list. A claim references the
                 name, never a command string of its own, so the
                 operator always sees the argv before the run.
    the OPERATOR passes --allow-commands, which the CLI turns into
                 allow_commands=True on command_succeeds claims.

The reason string for the un-authorised case is fixed wording, and the
tests hold it to that: a verdict a report cannot paraphrase is a
verdict a reader can pattern-match in CI output.

Determinism: the report carries the declared name, the exit status, and
a digest of stdout+stderr — never the output text, never a duration.
The environment is constructed literally, a fixed PATH and nothing
else: inheriting the operator's environment would make a run a property
of the machine, and reading os.environ is forbidden by tests/test_purity.py.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

from ..model import MISSING, SATISFIED, UNVERIFIABLE, Evidence
from ..registry import register
from ..subject import Subject

_DECLARATION = ".dossier.json"
_NOT_AUTHORISED = "command execution not authorised"

# A literal environment: what the subject's commands see, in full. A
# machine's PATH, LANG or credentials must not reach a run the report
# has to reproduce elsewhere.
_FIXED_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LC_ALL": "C"}

# Every run has a timeout. A command that never answers is not evidence
# about the subject, and an unbounded collector is a hung report.
_DEFAULT_TIMEOUT_SECONDS = 300.0


@register("command_succeeds")
def command_succeeds(
    subject: Subject,
    name: str,
    allow_commands: bool = False,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> tuple[str, str, tuple[Evidence, ...]]:
    """A command the subject declares runs and exits zero.

    The claim's ``name`` parameter references a declaration in the
    subject's own .dossier.json: {"commands": {"suite": ["make", "check"]}}.
    The collector resolves that name and — only when the operator has
    passed --allow-commands — runs it inside the subject with a literal
    environment and a timeout.

    Satisfied with the exit status and a digest of stdout+stderr as
    evidence; Missing with the non-zero status, because a failing exit
    is knowledge; Unverifiable when the declaration is absent, the name
    undeclared, the declaration unreadable, the command exceeds its
    timeout, or execution was not authorised — a timeout is not
    knowledge that the command fails. Never raises.
    """
    if not allow_commands:
        return (
            UNVERIFIABLE,
            _NOT_AUTHORISED,
            (),
        )

    if not subject.exists(_DECLARATION):
        return (
            UNVERIFIABLE,
            f"the subject declares no commands: no {_DECLARATION} at its root",
            (),
        )

    try:
        declared = json.loads(subject.read_text(_DECLARATION))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return (
            UNVERIFIABLE,
            f"the command declaration {_DECLARATION} is not readable JSON",
            (),
        )

    commands = declared.get("commands") if isinstance(declared, dict) else None
    argv = commands.get(name) if isinstance(commands, dict) else None
    if not isinstance(argv, list) or not argv or not all(
        isinstance(part, str) for part in argv
    ):
        return (
            UNVERIFIABLE,
            f"the command {name!r} is not declared in {_DECLARATION}",
            (),
        )

    try:
        completed = subprocess.run(
            argv,
            cwd=subject.root,
            env=_FIXED_ENV,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            UNVERIFIABLE,
            f"the command {name!r} exceeded its {timeout_seconds:g}s timeout, "
            "so whether it can succeed is unknown",
            (),
        )
    except OSError:
        return (
            UNVERIFIABLE,
            f"the command {name!r} could not be started on this machine",
            (),
        )

    # A digest of the output, never the text: what the command printed is
    # its business; that it ran and what came out as a digest is ours.
    output = (completed.stdout or "") + (completed.stderr or "")
    output_digest = _digest(output)
    note = f"exit status {completed.returncode}"
    evidence = (Evidence(kind="command", locator=name, digest=output_digest, note=note),)

    if completed.returncode != 0:
        return (
            MISSING,
            f"the declared command {name!r} exited {completed.returncode}, not zero",
            evidence,
        )

    return (
        SATISFIED,
        f"the declared command {name!r} exited 0",
        evidence,
    )


def _digest(text: str) -> str:
    """A sha256 of stdout+stderr, in hex — stable, and not the text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
