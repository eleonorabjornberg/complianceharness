"""Core vocabulary of the evidence register.

Five nouns, and nothing else:

    Claim     an assertion that ought to hold about a subject system
    Collector a deterministic function that goes looking for support for a claim
    Evidence  what it found, with a locator you can check by hand
    Verdict   whether the claim is supported, and why
    Report    every verdict for one pack against one subject

The whole point of the tool is that a Report is reproducible: the same
subject in the same state produces a byte-identical Report. That is why
Reports carry no absolute paths and no wall-clock timestamps. See the
determinism rule in CONTRACT.md before you add a field to anything here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

# --- Statuses -------------------------------------------------------------

SATISFIED = "satisfied"
MISSING = "missing"
STALE = "stale"
UNVERIFIABLE = "unverifiable"

STATUSES = (SATISFIED, MISSING, STALE, UNVERIFIABLE)

# --- Severities -----------------------------------------------------------

BLOCKING = "blocking"
MATERIAL = "material"
ADVISORY = "advisory"

SEVERITIES = (BLOCKING, MATERIAL, ADVISORY)


class ContractError(Exception):
    """A value violated the register's own rules."""


@dataclass(frozen=True)
class Evidence:
    """Something a reviewer could go and check for themselves.

    ``locator`` is always relative to the subject root (a path, a commit
    sha, a test id). Never an absolute path: absolute paths differ between
    machines and would break report reproducibility.
    """

    kind: str
    locator: str
    digest: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.kind:
            raise ContractError("evidence.kind must not be empty")
        if not self.locator:
            raise ContractError("evidence.locator must not be empty")
        if self.locator.startswith("/") or ":\\" in self.locator:
            raise ContractError(
                f"evidence.locator must be relative to the subject root: {self.locator!r}"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "locator": self.locator,
            "digest": self.digest,
            "note": self.note,
        }


@dataclass(frozen=True)
class Claim:
    """An assertion a reviewer would expect a responsible team to support.

    ``rationale`` is not decoration. A claim nobody can explain the point
    of is a checklist item, and checklist items are what make tools like
    this useless. If you cannot say which reviewer asks for it and why,
    do not add the claim.
    """

    id: str
    text: str
    severity: str
    collector: str
    rationale: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ContractError(
                f"claim {self.id}: severity {self.severity!r} not in {SEVERITIES}"
            )
        if not self.rationale.strip():
            raise ContractError(f"claim {self.id}: rationale must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "severity": self.severity,
            "collector": self.collector,
            "rationale": self.rationale,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class Verdict:
    claim_id: str
    status: str
    reason: str
    severity: str
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ContractError(
                f"verdict {self.claim_id}: status {self.status!r} not in {STATUSES}"
            )
        if self.status == SATISFIED and not self.evidence:
            raise ContractError(
                f"verdict {self.claim_id}: a satisfied claim must cite evidence"
            )

    @property
    def blocks(self) -> bool:
        return self.severity == BLOCKING and self.status in (MISSING, STALE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "severity": self.severity,
            "reason": self.reason,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True)
class Pack:
    """A versioned set of claims drawn from one source of expectations."""

    name: str
    version: str
    source: str
    claims: tuple[Claim, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for claim in self.claims:
            if claim.id in seen:
                raise ContractError(f"pack {self.name}: duplicate claim id {claim.id}")
            seen.add(claim.id)


@dataclass(frozen=True)
class Report:
    subject: str
    pack: str
    pack_version: str
    verdicts: tuple[Verdict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "pack": self.pack,
            "pack_version": self.pack_version,
            "verdicts": [v.to_dict() for v in self.verdicts],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def digest(self) -> str:
        """Stable identity of this report. Same subject state -> same digest."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def by_status(self, status: str) -> tuple[Verdict, ...]:
        return tuple(v for v in self.verdicts if v.status == status)

    @property
    def blocking(self) -> tuple[Verdict, ...]:
        return tuple(v for v in self.verdicts if v.blocks)


def summarise(verdicts: Sequence[Verdict]) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    for verdict in verdicts:
        counts[verdict.status] += 1
    return counts
