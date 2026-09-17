"""What changed between two reports.

    dossier diff <a.json> <b.json>

The comparison is a pure function of two parsed report documents: no
filesystem access, no clock, no environment. Reading the two files is
the CLI's job and is the only filesystem access the command performs.
The result is sorted before it is returned, so the same two reports
produce the same diff on any machine — a diff a reviewer cannot
re-derive later is a rumour.

Only the verdict status is compared. Two runs whose claims kept their
statuses but reworded their reasons do not register as a change; support
is what the register is for, and a diff that reported prose churn would
bury the movements that matter.
"""

from __future__ import annotations

import hashlib
import json

from .model import SATISFIED

__all__ = ["diff_reports", "document_digest"]


def diff_reports(before: dict, after: dict) -> dict:
    """Diff two parsed report documents (the shape ``Report.to_dict`` emits).

    Returns a dict with every claim id from either document in exactly
    one category:

        gained        not satisfied before, satisfied now
        lost          satisfied before, not satisfied now
        changed       status moved without gaining or losing support
        appeared      present only in the later document
        disappeared   present only in the earlier document
        unchanged     same status in both

    Entries carry the statuses that justify them — ``before``/``after``
    where both exist, ``status`` where only one side does. Raises
    ``ValueError`` if either document is not shaped like a report.
    """
    before_status = _statuses(before, side="before")
    after_status = _statuses(after, side="after")

    gained: list[dict] = []
    lost: list[dict] = []
    changed: list[dict] = []
    unchanged: list[str] = []

    for claim_id in sorted(before_status.keys() & after_status.keys()):
        was = before_status[claim_id]
        now = after_status[claim_id]
        if was == now:
            unchanged.append(claim_id)
        elif now == SATISFIED:
            gained.append({"claim_id": claim_id, "before": was, "after": now})
        elif was == SATISFIED:
            lost.append({"claim_id": claim_id, "before": was, "after": now})
        else:
            changed.append({"claim_id": claim_id, "before": was, "after": now})

    appeared = [
        {"claim_id": claim_id, "status": after_status[claim_id]}
        for claim_id in sorted(after_status.keys() - before_status.keys())
    ]
    disappeared = [
        {"claim_id": claim_id, "status": before_status[claim_id]}
        for claim_id in sorted(before_status.keys() - after_status.keys())
    ]

    return {
        "gained": gained,
        "lost": lost,
        "changed": changed,
        "appeared": appeared,
        "disappeared": disappeared,
        "unchanged": unchanged,
    }


def document_digest(document: dict) -> str:
    """A report's own digest, recomputed from the parsed document.

    Matches ``Report.digest()`` for a genuine report however the file on
    disk was formatted, so a diff cites its two inputs by the same
    identity the ``check`` command printed.
    """
    canonical = json.dumps(document, indent=2, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _statuses(document: dict, side: str) -> dict[str, str]:
    """Claim id -> status for one parsed report, shape-checked."""
    verdicts = document.get("verdicts") if isinstance(document, dict) else None
    if not isinstance(verdicts, list):
        raise ValueError(f"{side} document is not a dossier report: no 'verdicts' list")

    statuses: dict[str, str] = {}
    for verdict in verdicts:
        if (
            not isinstance(verdict, dict)
            or not isinstance(verdict.get("claim_id"), str)
            or not isinstance(verdict.get("status"), str)
        ):
            raise ValueError(
                f"{side} document has a verdict without a claim id and status"
            )
        if verdict["claim_id"] in statuses:
            raise ValueError(
                f"{side} document repeats claim {verdict['claim_id']!r}"
            )
        statuses[verdict["claim_id"]] = verdict["status"]
    return statuses
