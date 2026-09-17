"""Command line interface.

    python3 -m dossier check <path> --pack model-evidence
    python3 -m dossier check <path> --pack agent-control --json
    python3 -m dossier check <path> --pack agent-control --format markdown
    python3 -m dossier packs
    python3 -m dossier diff <a.json> <b.json>

`--format markdown` renders the report for a reader away from the
terminal — every verdict, the rationale of every unsupported claim, and
the same digest the text format prints. `--json` still wins when both
are given.

Exit codes are part of the contract, because CI depends on them:

    0  no blocking claim is missing or stale
    1  at least one blocking claim is missing or stale
    2  the run could not be performed at all

`diff` shares 0 and 2: 0 once the two reports have been compared, 2 when
either argument is missing, unreadable or not a report. A diff full of
regressions still exits 0 — deciding which differences block is the
baseline feature's (I1) business, not this command's.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import engine, packs
from .diff import diff_reports, document_digest
from .model import (
    MISSING,
    Pack,
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

# Inline rationale width, in characters (R4). A constant, not a terminal
# probe: the default output must render identically on every machine.
_RATIONALE_WIDTH = 72


def _inline_rationale(text: str, width: int = _RATIONALE_WIDTH) -> str:
    """A claim's rationale as one line, cut by character count.

    Cutting at a word boundary would let the rendered line depend on
    where words happen to fall; cutting at a character count keeps it a
    pure function of the rationale text.
    """
    collapsed = " ".join(text.split())
    if len(collapsed) <= width:
        return collapsed
    return collapsed[: width - 1] + "…"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dossier", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run a pack against a directory")
    check.add_argument("path", help="root of the system under review")
    check.add_argument("--pack", required=True, choices=packs.names())
    check.add_argument("--json", action="store_true", help="emit the report as JSON")
    check.add_argument("--name", help="override the subject name recorded in the report")
    check.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="render the report as markdown instead of terminal text",
    )

    sub.add_parser("packs", help="list available packs and their claims")

    diff = sub.add_parser("diff", help="compare two report JSON files")
    diff.add_argument("a", help="the earlier report (JSON)")
    diff.add_argument("b", help="the later report (JSON)")

    args = parser.parse_args(argv)

    if args.command == "packs":
        return _list_packs()
    if args.command == "diff":
        return _diff(args)
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
    elif args.format == "markdown":
        print(_format_markdown(report, pack))
    else:
        _print_report(report)

    return 1 if report.blocking else 0


def _print_report(report: Report) -> None:
    pack = packs.get(report.pack)
    rationales = {c.id: c.rationale for c in pack.claims} if pack else {}
    print(f"{report.subject}  ·  {report.pack} {report.pack_version}")
    print()
    for verdict in report.verdicts:
        mark = _MARKS[verdict.status]
        print(f"  {mark}  {verdict.claim_id}  {verdict.reason}")
        if verdict.status != SATISFIED and verdict.claim_id in rationales:
            print(
                f"          why: {_inline_rationale(rationales[verdict.claim_id])}"
            )
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


def _format_markdown(report: Report, pack: Pack | None = None) -> str:
    """Render a report as markdown a non-engineer can paste into a document.

    Formatting only: it reads the report and the pack's claims (for the
    words and rationale of each claim) and changes neither. Without a
    pack it renders what the report itself owns — the verdicts, the
    reasons, the digest — and shows no rationale, because there is none
    to show without inventing one.

    The digest is the report's own, the same number the text format
    prints: the format is a rendering, not a re-derivation.
    """
    claims = {claim.id: claim for claim in pack.claims} if pack else {}

    lines = [f"# dossier report — {report.pack} {report.pack_version}", ""]
    lines.append(f"Subject: {report.subject}")
    lines += ["", "## Verdicts"]
    for verdict in report.verdicts:
        claim = claims.get(verdict.claim_id)
        lines += ["", f"### {verdict.claim_id} — {verdict.status} ({verdict.severity})", ""]
        if claim is not None:
            lines += [claim.text, ""]
        lines += [verdict.reason, ""]
        lines += [
            f"- evidence: {item.kind} `{item.locator}`"
            for item in verdict.evidence
        ]
        if verdict.status != SATISFIED and claim is not None:
            lines += ["", f"> **Why this claim matters:** {claim.rationale}"]

    lines += ["", "## Summary", ""]
    counts = summarise(report.verdicts)
    lines += [f"- {name}: {count}" for name, count in counts.items() if count]
    lines += ["", f"digest: {report.digest()[:16]}"]

    if report.blocking:
        lines += ["", "## Blocking claims not supported", ""]
        lines += [f"- {verdict.claim_id}" for verdict in report.blocking]

    return "\n".join(lines) + "\n"


def _diff(args) -> int:
    try:
        before = _read_report(args.a)
        after = _read_report(args.b)
        result = diff_reports(before, after)
    except (OSError, ValueError) as error:
        print(f"diff: {error}", file=sys.stderr)
        return 2

    _print_diff(
        result,
        before_label=args.a,
        after_label=args.b,
        before_digest=document_digest(before),
        after_digest=document_digest(after),
    )
    return 0


def _read_report(path: str) -> dict:
    """The only filesystem access `diff` performs: reading one argument."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _print_diff(
    result: dict,
    *,
    before_label: str,
    after_label: str,
    before_digest: str,
    after_digest: str,
) -> None:
    print(f"diff  {before_label}  →  {after_label}")
    print(f"  a: {before_digest[:16]}  b: {after_digest[:16]}")
    print()

    sections = (
        ("gained", "gained support", "+"),
        ("lost", "lost support", "-"),
        ("changed", "changed status", "~"),
        ("appeared", "appeared", "+"),
        ("disappeared", "disappeared", "-"),
    )
    for key, heading, mark in sections:
        if not result[key]:
            continue
        print(f"  {heading}:")
        for entry in result[key]:
            if "status" in entry:  # one-sided: only one status exists
                print(f"    {mark} {entry['claim_id']}  {entry['status']}")
            else:
                print(
                    f"    {mark} {entry['claim_id']}"
                    f"  {entry['before']} → {entry['after']}"
                )

    unchanged = result["unchanged"]
    listed = ", ".join(unchanged)
    print()
    print(f"unchanged: {len(unchanged)}" + (f" ({listed})" if unchanged else ""))
