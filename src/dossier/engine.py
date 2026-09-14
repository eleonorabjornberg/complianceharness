"""Run a pack against a subject and produce a report.

The engine is deliberately small and deliberately boring. It holds no
opinion about what should be true of a system — that lives in packs —
and it does no looking itself — that lives in collectors. What it owns
is the one thing both of those must not get wrong: a claim whose
collector fails, is missing, or misbehaves comes back UNVERIFIABLE with
a reason, never as a pass and never as a crash.

An unverifiable claim is not a soft failure. It is the register saying
it does not know, which is a different and more honest thing than
saying no.
"""

from __future__ import annotations

from . import collectors as _collectors  # noqa: F401  (registers collectors on import)
from . import registry
from .model import (
    ContractError,
    Report,
    STATUSES,
    UNVERIFIABLE,
    Verdict,
)
from .model import Pack
from .subject import OutsideSubject, Subject


def check(subject: Subject, pack: Pack) -> Report:
    verdicts: list[Verdict] = []

    for claim in pack.claims:
        verdicts.append(_evaluate(subject, claim))

    return Report(
        subject=subject.name,
        pack=pack.name,
        pack_version=pack.version,
        verdicts=tuple(verdicts),
    )


def _evaluate(subject: Subject, claim) -> Verdict:
    collector = registry.get(claim.collector)

    if collector is None:
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=(
                f"no collector named {claim.collector!r} is registered; "
                f"known collectors: {', '.join(registry.names())}"
            ),
        )

    try:
        status, reason, evidence = collector(subject, **dict(claim.params))
    except OutsideSubject as error:
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=f"collector tried to read outside the subject: {error}",
        )
    except TypeError as error:
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=f"claim params do not match collector signature: {error}",
        )
    except Exception as error:  # noqa: BLE001 - a broken collector must not sink the run
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=f"collector raised {type(error).__name__}: {error}",
        )

    if status not in STATUSES:
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=f"collector returned unknown status {status!r}",
        )

    try:
        return Verdict(
            claim_id=claim.id,
            status=status,
            severity=claim.severity,
            reason=reason,
            evidence=tuple(evidence),
        )
    except ContractError as error:
        return Verdict(
            claim_id=claim.id,
            status=UNVERIFIABLE,
            severity=claim.severity,
            reason=f"collector produced an invalid verdict: {error}",
        )
