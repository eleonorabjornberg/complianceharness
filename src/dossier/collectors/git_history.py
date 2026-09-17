"""The collector that reads the subject's git history.

The document collectors only ever see the subject as it is now. This one
sees that the subject has a history at all, and which history: the sha of
its first commit and the sha of HEAD, so a verdict can be tied to a tree
a reviewer can check out and read for themselves.

It is also the foundation the other git-aware collectors build on: they
all need the same two questions answered the same way — is there a
history, and if not, why not.
"""

from __future__ import annotations

import subprocess

from ..model import MISSING, SATISFIED, UNVERIFIABLE, Evidence
from ..registry import register
from ..subject import Subject


@register("git_history")
def git_history(subject: Subject) -> tuple[str, str, tuple[Evidence, ...]]:
    """The subject has a git history, and this is which history.

    Reports the sha of the first commit and the sha of HEAD as evidence,
    so any verdict can be tied to a tree a reviewer can check out.

    Absent: UNVERIFIABLE, naming which of the two was missing — a `.git`
    at the subject root, or a `git` executable on the machine. A
    repository with no commits is MISSING: the absence of a history is
    knowledge, not ignorance. Never raises.

    Git is asked, never guessed at: subprocess runs an explicit argv list
    against the subject root, never a shell string, and what it answers
    about the subject's commits is a property of the subject, not of the
    machine.
    """
    if not subject.exists(".git"):
        return (
            UNVERIFIABLE,
            "no .git at the subject root, so there is no history to tie a verdict to",
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
                "the repository has no commits on HEAD, so it has no history",
                (),
            )
        rev_list = subprocess.run(
            ["git", "rev-list", "HEAD"],
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

    if rev_list.returncode != 0:
        # HEAD resolved but the walk failed: the collector cannot say
        # which history this is, and it does not invent one.
        return (
            UNVERIFIABLE,
            "git could not list the history, so the commits could not be identified",
            (),
        )

    shas = rev_list.stdout.split()
    if not shas:
        return (
            MISSING,
            "the repository has no commits, so it has no history",
            (),
        )

    first, last = shas[-1], shas[0]
    evidence = (
        Evidence(kind="commit", locator=first, note="first commit"),
        Evidence(kind="commit", locator=last, note="HEAD"),
    )
    return (
        SATISFIED,
        f"git history runs from {first} to {last} ({len(shas)} commits)",
        evidence,
    )
