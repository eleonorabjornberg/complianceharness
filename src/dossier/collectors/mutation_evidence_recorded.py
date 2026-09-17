"""Collector that looks for a recorded mutation and the test that caught it.

CONTRACT.md's "Test power" section asks every change to record what was
broken on purpose and which test went red because of it, in this shape:

    mutation: what was broken
    caught by: the test that caught it

This collector checks that the subject keeps at least one such record
where a reviewer can find it. The block is found, not inferred: a line
that opens with ``mutation:`` and, in the same paragraph, a line that
opens with ``caught by:``. Prose that merely mentions mutation testing
is not a record, and neither half of the pair alone is one.

The evidence is deliberately weak — a written line, not a verified
mutation run — and the collector's value is the informative absence: a
subject with no recorded block is one where nobody has shown the suite
has any power.
"""

from __future__ import annotations

import re

from ..model import Evidence, MISSING, SATISFIED
from ..registry import register
from ..subject import Subject

# A record line, not a mention in prose: the key must open the line, with
# at most a Markdown list or quote marker before it.
_MUTATION = re.compile(
    r"^\s*(?:[-*+]|\d+[.)]|>)?\s*mutation:\s*(?P<what>\S.*)$", re.IGNORECASE
)
_CAUGHT_BY = re.compile(
    r"^\s*(?:[-*+]|\d+[.)]|>)?\s*caught by:\s*(?P<test>\S.*)$", re.IGNORECASE
)


def _records_in(text: str) -> list[tuple[int, str, str]]:
    """(line number, what was broken, what caught it) for every block.

    The pair must share a paragraph: a ``caught by:`` line that follows
    the ``mutation:`` line before the next blank one.
    """
    lines = text.splitlines()
    records: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        mutation = _MUTATION.match(lines[i])
        if mutation is None:
            i += 1
            continue
        caught = None
        for j in range(i + 1, len(lines)):
            if not lines[j].strip():
                break
            witness = _CAUGHT_BY.match(lines[j])
            if witness is not None:
                caught = (j, witness.group("test").strip())
                break
        if caught is None:
            i += 1
            continue
        records.append((i + 1, mutation.group("what").strip(), caught[1]))
        i = caught[0] + 1
    return records


@register("mutation_evidence_recorded")
def mutation_evidence_recorded(subject: Subject) -> tuple[str, str, tuple[Evidence, ...]]:
    """The subject records at least one mutation and the test that caught it.

    Looks for the shape CONTRACT.md's "Test power" section describes —
    a ``mutation:`` line and a ``caught by:`` line sharing a paragraph —
    in every file the subject exposes. Reports MISSING when no block is
    found, which is the informative answer: it says nobody has recorded
    the suite failing when the code was wrong. It does not judge whether
    the recorded mutation was real; a written line is weak evidence and
    this collector does not pretend otherwise.
    """
    evidence: list[Evidence] = []
    for relative in subject.iter_files():
        text = subject.read_text(relative)
        for line_no, what, caught_by in _records_in(text):
            evidence.append(
                Evidence(
                    kind="mutation-record",
                    locator=f"{relative}:{line_no}",
                    digest=subject.digest(relative),
                    note=f"mutation: {what}; caught by: {caught_by}",
                )
            )
    if not evidence:
        return (
            MISSING,
            "no recorded mutation block: a 'mutation:' line followed by a "
            "'caught by:' line",
            (),
        )
    first = evidence[0].locator
    reason = f"a recorded mutation is at {first}"
    if len(evidence) > 1:
        reason += f", and {len(evidence) - 1} more"
    return SATISFIED, reason, tuple(evidence)
