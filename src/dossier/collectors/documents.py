"""Collectors that look for written evidence in the subject's own files.

These are deliberately the dullest collectors in the tool. They are the
vertical slice: if these work end to end, every richer collector is the
same shape with a different body.
"""

from __future__ import annotations

import re
from dataclasses import replace

from ..model import Evidence, MENTIONS, MISSING, SATISFIED
from ..registry import register
from ..subject import Subject


@register("document_present")
def document_present(subject: Subject, candidates: list[str], must_mention: list[str] | None = None) -> tuple[str, str, tuple[Evidence, ...]]:
    """A document exists at one of `candidates`, optionally mentioning every term in `must_mention`.

    Presence is the weakest possible evidence and this collector says so:
    it reports what it found and where, and never claims the document is
    any good. `must_mention` is a crude guard against an empty file with
    the right name.
    """
    found = subject.first_existing(*candidates)
    if found is None:
        return (
            MISSING,
            "none of these exist: " + ", ".join(candidates),
            (),
        )

    text = subject.read_text(found)
    evidence = (
        Evidence(
            kind="file",
            locator=found,
            digest=subject.digest(found),
            note=f"{len(text.splitlines())} lines",
        ),
    )

    if must_mention:
        lowered = text.lower()
        absent = [term for term in must_mention if term.lower() not in lowered]
        if absent:
            return (
                MISSING,
                f"{found} exists but does not mention: " + ", ".join(absent),
                evidence,
            )

    if must_mention:
        # The words were checked, so the file is evidence at 'mentions'.
        evidence = tuple(replace(item, strength=MENTIONS) for item in evidence)
    return SATISFIED, f"found {found}", evidence


@register("section_present")
def section_present(subject: Subject, candidates: list[str], heading: str) -> tuple[str, str, tuple[Evidence, ...]]:
    """A Markdown heading matching `heading` exists in one of `candidates`.

    Matched case-insensitively against ATX headings only, because a tool
    that guesses at document structure produces findings nobody trusts.
    """
    pattern = re.compile(r"^#{1,6}\s*" + re.escape(heading) + r"\s*$", re.IGNORECASE | re.MULTILINE)

    for candidate in candidates:
        if not subject.exists(candidate):
            continue
        text = subject.read_text(candidate)
        match = pattern.search(text)
        if match:
            line_number = text[: match.start()].count("\n") + 1
            return (
                SATISFIED,
                f"{candidate} has a {heading!r} section",
                (
                    Evidence(
                        kind="section",
                        locator=f"{candidate}:{line_number}",
                        digest=subject.digest(candidate),
                        note=match.group(0).strip(),
                        strength=MENTIONS,
                    ),
                ),
            )

    return (
        MISSING,
        f"no {heading!r} section in any of: " + ", ".join(candidates),
        (),
    )
