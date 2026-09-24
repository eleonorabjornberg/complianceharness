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


class ContractError(Exception):
    """A value violated the register's own rules."""


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

# --- Evidence strength (S1) -----------------------------------------------
#
# The ladder, weakest first. Position is the meaning: a rung outranks every
# rung before it. Rungs are compared only through strength_rank(), never as
# strings — alphabetically, "behaves" would sort below "corresponds".

PRESENT = "present"          # the file is there
MENTIONS = "mentions"        # it contains the right words
CORRESPONDS = "corresponds"  # everything concrete it names can be found
AGREES = "agrees"            # two independent documents state the same fact
FRESH = "fresh"              # it moved when the code it describes moved
BEHAVES = "behaves"          # something was run and it exited zero

STRENGTHS = (PRESENT, MENTIONS, CORRESPONDS, AGREES, FRESH, BEHAVES)


def strength_rank(strength: str) -> int:
    """A rung's position on the ladder. The only way rungs are compared."""
    try:
        return STRENGTHS.index(strength)
    except ValueError:
        raise ContractError(
            f"strength {strength!r} is not a rung of the ladder {STRENGTHS}"
        ) from None


# --- Lineages (P1a) -------------------------------------------------------
#
# Where an expectation comes from. One claim can carry several, with one
# citation each: two regimes asking for the same evidence in different
# words is the argument, not a duplication.

ANNEX_IV = "annex-iv"
OBSERVED = "observed"
SR_11_7 = "sr-11-7"

LINEAGES = (ANNEX_IV, OBSERVED, SR_11_7)


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
    strength: str = PRESENT

    def __post_init__(self) -> None:
        strength_rank(self.strength)
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
            "strength": self.strength,
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
    requires: str = PRESENT
    lineages: tuple[str, ...] = (OBSERVED,)
    citation_by_lineage: Mapping[str, str] = field(
        default_factory=lambda: {OBSERVED: ""}
    )

    def __post_init__(self) -> None:
        strength_rank(self.requires)
        if not self.lineages:
            raise ContractError(f"claim {self.id}: lineages must not be empty")
        unknown = [lineage for lineage in self.lineages if lineage not in LINEAGES]
        if unknown:
            raise ContractError(
                f"claim {self.id}: lineages {unknown} not in {LINEAGES}"
            )
        if tuple(self.lineages) != tuple(sorted(set(self.lineages))):
            raise ContractError(
                f"claim {self.id}: lineages must be sorted and unique: {self.lineages}"
            )
        if set(self.citation_by_lineage) != set(self.lineages):
            raise ContractError(
                f"claim {self.id}: citation_by_lineage keys "
                f"{sorted(self.citation_by_lineage)} must match lineages {list(self.lineages)}"
            )
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
            "requires": self.requires,
            "lineages": list(self.lineages),
            "citation_by_lineage": dict(sorted(self.citation_by_lineage.items())),
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
