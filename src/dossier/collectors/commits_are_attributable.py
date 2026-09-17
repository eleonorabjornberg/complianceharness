"""The collector that reads who wrote the subject's commits.

``git_history`` sees that a history exists; this one sees that someone
answerable stands behind each commit in it: every commit has an author
and a non-empty message, and — where the claim gives an agent-author
pattern — every commit by a matching author carries a trailer naming
what produced it. Reviewers of agent-written code ask exactly this: not
"was code written" but "can I tell by what".
"""

from __future__ import annotations

import re
import subprocess

from ..model import MISSING, SATISFIED, UNVERIFIABLE, Evidence
from ..registry import register
from ..subject import Subject

# One git call answers everything, so the collector sees one consistent
# history: per commit, the sha, the author ident and the raw body,
# separated by the record and field separators git's own scripting docs
# reserve for this (%x1e between records, %x00 between fields).
_LOG_FORMAT = "%H%x00%an%x00%ae%x00%B%x1e"

_RECORD = "\x1e"
_FIELD = "\x00"

# A Git trailer: a `Token: value` line. The value is optional as far as
# the shape goes — and a trailer with an empty value (`Co-Authored-By:`
# and nothing after it) names nothing, which is exactly what the claim
# refuses to count as attribution.
_TRAILER = re.compile(r"^(?P<token>[A-Za-z][A-Za-z0-9-]*):(?:[ \t]+(?P<value>.*))?$")


@register("commits_are_attributable")
def commits_are_attributable(
    subject: Subject, agent_pattern: str | None = None
) -> tuple[str, str, tuple[Evidence, ...]]:
    """Every commit has an author and a non-empty message, and — where an
    agent-author pattern is given — every matching commit carries a
    trailer naming what produced it.

    The pattern is a regular expression matched against the author's
    ``Name <email>`` ident. Without it the trailer check is not armed and
    only authors and messages are looked at.

    Absent: no ``.git`` at the subject root, no ``git`` on the machine,
    or an uncompileable pattern is UNVERIFIABLE, naming which. A
    repository with no commits is MISSING: the absence of a history is
    knowledge, not ignorance. A commit that fails a check is MISSING,
    with each offending sha named in the evidence — a count is not
    something a reviewer can check out. Never raises.

    Git is asked, never guessed at: subprocess runs an explicit argv list
    against the subject root, never a shell string.
    """
    if not subject.exists(".git"):
        return (
            UNVERIFIABLE,
            "no .git at the subject root, so there is no history to attribute",
            (),
        )

    try:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=subject.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode != 0:
            return (
                MISSING,
                "the repository has no commits, so there is nothing to attribute",
                (),
            )
        log = subprocess.run(
            ["git", "log", f"--format={_LOG_FORMAT}", "HEAD"],
            cwd=subject.root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return (
            UNVERIFIABLE,
            "git is not available on this machine, so the history cannot be read",
            (),
        )

    if log.returncode != 0:
        # HEAD resolved but the walk failed: the collector cannot say
        # who wrote what, and it does not invent one.
        return (
            UNVERIFIABLE,
            "git could not list the history, so the commits could not be checked",
            (),
        )

    pattern = None
    if agent_pattern is not None and agent_pattern != "":
        try:
            pattern = re.compile(agent_pattern)
        except re.error as error:
            return (
                UNVERIFIABLE,
                f"the agent-author pattern is not a valid regular expression: {error}",
                (),
            )

    offenders: list[Evidence] = []
    checked: list[Evidence] = []
    for record in log.stdout.split(_RECORD):
        record = record.strip("\n")
        if not record:
            continue
        sha, name, email, body = record.split(_FIELD, 3)
        defects = _defects(name, email, body, pattern)
        if defects:
            offenders.append(
                Evidence(kind="commit", locator=sha, note="; ".join(defects))
            )
        else:
            checked.append(
                Evidence(kind="commit", locator=sha, note=_pass_note(name, email, pattern))
            )

    if offenders:
        return (
            MISSING,
            f"{len(offenders)} of {len(offenders) + len(checked)} commits are not "
            "attributable; each offender is named by sha in the evidence",
            tuple(offenders),
        )

    return (
        SATISFIED,
        _satisfied_reason(len(checked), pattern is not None),
        tuple(checked),
    )


def _defects(name: str, email: str, body: str, pattern: re.Pattern | None) -> list[str]:
    """What makes one commit unattributable, in the order a reviewer reads it."""
    defects: list[str] = []
    if not name.strip() and not email.strip():
        defects.append("has no author")
    if not body.strip():
        defects.append("has an empty commit message")
    if pattern is not None and pattern.search(f"{name} <{email}>"):
        if _producer_trailer(body) is None:
            defects.append(
                "is by a matching author and carries no trailer naming what produced it"
            )
    return defects


def _pass_note(name: str, email: str, pattern: re.Pattern | None) -> str:
    if pattern is not None and pattern.search(f"{name} <{email}>"):
        return "author, message and producer trailer checked"
    return "author and message checked"


def _producer_trailer(body: str) -> str | None:
    """The value of the commit message's producer trailer, or None.

    Trailers live in the message's final paragraph, one ``Token: value``
    line each. A line that only looks like a trailer because of its
    position — prose in the footer — does not match the shape, and a
    trailer whose value is empty does not name anything. Both return
    None.
    """
    final_paragraph = re.split(r"\n[ \t]*\n", body.strip())[-1]
    for line in final_paragraph.splitlines():
        match = _TRAILER.match(line)
        if match and (match.group("value") or "").strip():
            return match.group("value").strip()
    return None


def _satisfied_reason(count: int, pattern_armed: bool) -> str:
    reason = f"all {count} commits have an author and a non-empty message"
    if pattern_armed:
        reason += (
            ", and commits by a matching author carry a trailer naming what produced it"
        )
    return reason
