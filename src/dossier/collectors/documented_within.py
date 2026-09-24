"""The collector that asks whether documentation kept up with the code.

document_present and section_present see that a document exists and says
the right words. Neither can see whether it describes the system as it
is now rather than as it was when someone last remembered to update it.
This one does: it finds the last commit that touched the document and
counts how many commits have landed since, so a reviewer's question —
"is this paperwork describing the system I am looking at?" — becomes a
number a reviewer can check with git.

That number is a distance in commits, never in days. Wall-clock
staleness would differ between machines and between checkouts, and a
report that depends on when it was run breaks the determinism rule
(CONTRACT.md). Commits are the subject's own clock, and git owns it.
"""

from __future__ import annotations

import subprocess

from ..model import FRESH, MISSING, PRESENT, SATISFIED, STALE, UNVERIFIABLE, Evidence
from ..registry import register
from ..subject import Subject


@register("documented_within")
def documented_within(
    subject: Subject, candidates: list[str], within: int
) -> tuple[str, str, tuple[Evidence, ...]]:
    """The document at one of `candidates` was last modified within `within` commits of HEAD.

    `within` is a number of commits, not days: freshness measured against
    the clock would not survive a checkout, and the determinism rule
    forbids the clock anywhere under src/.

    Absent: a subject with no `.git` has no history to measure freshness
    in, which is UNVERIFIABLE; a document none of whose candidate paths
    exist is MISSING, and so is a document no commit has ever carried —
    those are different answers, and neither collapses into the other.
    A repository with no commits is MISSING for the same reason C1 gives:
    the absence of a history is knowledge, not ignorance. Never raises.

    Git is asked, never guessed at: subprocess runs an explicit argv list
    against the subject root, never a shell string.
    """
    if not subject.exists(".git"):
        return (
            UNVERIFIABLE,
            "no .git at the subject root, so there is no history to measure freshness in",
            (),
        )

    found = subject.first_existing(*candidates)
    if found is None:
        return (
            MISSING,
            "none of these exist: " + ", ".join(candidates),
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
                "the repository has no commits on HEAD, so no commit has ever touched the document",
                (),
            )
        last_touch = subprocess.run(
            ["git", "rev-list", "-n", "1", "HEAD", "--", found],
            cwd=subject.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if last_touch.returncode != 0:
            return (
                UNVERIFIABLE,
                "git could not find the last commit to touch the document, so freshness cannot be measured",
                (),
            )
        sha = last_touch.stdout.strip()
        if not sha:
            return (
                MISSING,
                f"no commit in the history has ever touched {found}, so it is not under version control",
                (),
            )
        counted = subprocess.run(
            ["git", "rev-list", "--count", f"{sha}..HEAD"],
            cwd=subject.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if counted.returncode != 0:
            return (
                UNVERIFIABLE,
                "git could not count the commits since the document was last touched, so freshness cannot be measured",
                (),
            )
    except OSError:
        return (
            UNVERIFIABLE,
            "git is not available on this machine, so the history cannot be read",
            (),
        )

    try:
        distance = int(counted.stdout.strip())
    except ValueError:
        return (
            UNVERIFIABLE,
            "git returned an unparseable commit count, so freshness cannot be measured",
            (),
        )

    evidence = (
        Evidence(
            kind="commit",
            locator=sha,
            note=f"last commit to touch {found}; {distance} commit(s) behind HEAD",
            strength=FRESH if distance <= within else PRESENT,
        ),
        Evidence(
            kind="file",
            locator=found,
            digest=subject.digest(found),
            note=f"{len(subject.read_text(found).splitlines())} lines",
        ),
    )

    if distance <= within:
        return (
            SATISFIED,
            f"{found} was last modified {distance} commit(s) behind HEAD, within the limit of {within}",
            evidence,
        )
    return (
        STALE,
        f"{found} was last modified {distance} commit(s) behind HEAD, which is beyond the limit of {within}",
        evidence,
    )
