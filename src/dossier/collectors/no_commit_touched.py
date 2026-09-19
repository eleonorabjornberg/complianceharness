"""The collector that checks the history never touched protected paths.

AC-01 asks that the boundaries agents may not cross are written down.
This collector is what keeps that writing true: given the globs of the
paths a claim protects, it walks every commit of the subject's history
and reports any commit that modified a matching path. It is how a
reviewer is shown that the agents did not edit their own judge — not
because nobody looked, but because a walk of the history says so.

Globs come from the claim's parameters, never from a constant here:
what counts as protected is the claim's opinion to state, and the same
subject must answer two different claims with two different verdicts.

Matching is ``fnmatchcase`` — pure pattern matching, no case folding,
so a report cannot depend on the machine it was produced on. One star
matches across directory separators, the way git pathspecs and
reviewers both read globs: ``src/*.py`` reaches ``src/dossier/model.py``.

The walk is ``git log --first-parent``: the delivered history of the
branch, one entry per commit, with each merge shown as the change it
introduces relative to its first parent. Rename detection is off, so
the answer does not depend on a machine's git config.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from typing import Sequence

from ..model import MISSING, SATISFIED, UNVERIFIABLE, Evidence
from ..registry import register
from ..subject import Subject

# ``--format=%H`` emits exactly one full sha per commit; every other
# non-blank line under ``--name-only`` is a path that commit changed.
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _pairs_from_log(stdout: str) -> list[tuple[str, str]]:
    """(sha, path) for every path every walked commit changed, in order."""
    pairs: list[tuple[str, str]] = []
    commit: str | None = None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        if _SHA.fullmatch(line):
            commit = line
            continue
        if commit is not None:
            pairs.append((commit, line))
    return pairs


def _violations(
    pairs: Sequence[tuple[str, str]], globs: Sequence[str]
) -> list[tuple[str, str]]:
    """Every pair whose path matches a glob, deduplicated and sorted.

    Sorted because report reproducibility depends on it: git answers in
    reverse-chronological order, and a report must not.
    """
    return sorted(
        {
            (sha, path)
            for sha, path in pairs
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in globs)
        }
    )


@register("no_commit_touched")
def no_commit_touched(
    subject: Subject, protected: Sequence[str]
) -> tuple[str, str, tuple[Evidence, ...]]:
    """No commit in the history modified a path matching the protected globs.

    Walks every commit of the subject's first-parent history and reports
    MISSING when any of them changed a path matching one of the claim's
    ``protected`` globs — naming each offending sha and path as evidence,
    including a violation that was later reverted, which the tree at HEAD
    no longer shows. Reports SATISFIED, with HEAD's sha as evidence, when
    the walk is clean.

    Absent, the same ladder git_history climbs: no ``.git`` at the
    subject root, or no ``git`` on the machine, is UNVERIFIABLE; a
    repository with no commits is MISSING, because the absence of a
    history is knowledge, not ignorance. A claim that protects no paths
    is UNVERIFIABLE too — a vacuous pass would answer the claim without
    looking at it. Never raises.

    Git is asked, never guessed at: subprocess runs an explicit argv list
    against the subject root, never a shell string, and what it answers
    about the subject's commits is a property of the subject, not of the
    machine.
    """
    globs = list(protected)
    if not globs:
        return (
            UNVERIFIABLE,
            "the claim protects no paths: no globs were given, so there is nothing to check",
            (),
        )

    if not subject.exists(".git"):
        return (
            UNVERIFIABLE,
            "no .git at the subject root, so there is no history to check the commits against",
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
                "the repository has no commits on HEAD, so there is no history that could have touched a protected path",
                (),
            )
        walk = subprocess.run(
            [
                "git",
                "log",
                "--first-parent",
                "--no-renames",
                "--format=%H",
                "--name-only",
            ],
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

    if walk.returncode != 0:
        # HEAD resolved but the walk failed: the collector cannot say
        # the history is clean, and it does not invent one.
        return (
            UNVERIFIABLE,
            "git could not list the history, so the commits could not be checked",
            (),
        )

    offenses = _violations(_pairs_from_log(walk.stdout), globs)
    if not offenses:
        head_sha = head.stdout.strip()
        return (
            SATISFIED,
            f"no commit in the history touched a path matching any of the {len(globs)} protected globs",
            (Evidence(kind="commit", locator=head_sha, note="HEAD"),),
        )

    evidence = tuple(
        Evidence(kind="commit", locator=path, note=f"modified by commit {sha}")
        for sha, path in offenses
    )
    first_sha, first_path = offenses[0]
    reason = f"commit {first_sha} modified {first_path}, a protected path"
    if len(offenses) > 1:
        reason += f", and {len(offenses) - 1} more"
    return MISSING, reason, evidence
