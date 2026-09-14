"""Command line interface.

    python3 -m dossier check <path> --pack model-evidence
    python3 -m dossier check <path> --pack agent-control --json
    python3 -m dossier packs

Exit codes are part of the contract, because CI depends on them:

    0  no blocking claim is missing or stale
    1  at least one blocking claim is missing or stale
    2  the run could not be performed at all
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import engine, packs
from .model import (
    MISSING,
    Report,
    SATISFIED,
    STALE,
    UNVERIFIABLE,
    summarise,
)
from .subject import Subject

_MARKS = {
    SATISFIED: "ok  ",
    MISSING: "MISS",
    STALE: "STALE",
    UNVERIFIABLE: "?   ",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dossier", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run a pack against a directory")
    check.add_argument("path", help="root of the system under review")
    check.add_argument("--pack", required=True, choices=packs.names())
    check.add_argument("--json", action="store_true", help="emit the report as JSON")
    check.add_argument("--name", help="override the subject name recorded in the report")

    sub.add_parser("packs", help="list available packs and their claims")

    args = parser.parse_args(argv)

    if args.command == "packs":
        return _list_packs()
    return _check(args)


def _list_packs() -> int:
    for pack in packs.all_packs():
        print(f"{pack.name} {pack.version}")
        print(f"  source: {pack.source}")
        for claim in pack.claims:
            print(f"  {claim.id}  [{claim.severity}]  {claim.text}")
        print()
    return 0


def _check(args) -> int:
    pack = packs.get(args.pack)
    if pack is None:
        print(f"unknown pack: {args.pack}", file=sys.stderr)
        return 2

    try:
        subject = Subject.at(args.path, name=args.name)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 2

    report = engine.check(subject, pack)

    if args.json:
        print(report.to_json())
    else:
        _print_report(report)

    return 1 if report.blocking else 0


def _print_report(report: Report) -> None:
    print(f"{report.subject}  ·  {report.pack} {report.pack_version}")
    print()
    for verdict in report.verdicts:
        mark = _MARKS[verdict.status]
        print(f"  {mark}  {verdict.claim_id}  {verdict.reason}")
        for item in verdict.evidence:
            print(f"          └─ {item.kind}: {item.locator}")
    print()

    counts = summarise(report.verdicts)
    print(
        "  ".join(
            f"{name}: {count}" for name, count in counts.items() if count
        )
    )
    print(f"report digest: {report.digest()[:16]}")

    if report.blocking:
        print()
        print("blocking claims not supported:")
        for verdict in report.blocking:
            print(f"  {verdict.claim_id}")
