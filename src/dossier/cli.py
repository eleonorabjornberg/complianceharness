"""Command line interface.

    python3 -m dossier check <path> --pack model-evidence
    python3 -m dossier check <path> --pack agent-control --json
    python3 -m dossier check <path> --pack agent-control --format markdown
    python3 -m dossier check <path> --pack agent-control --allow-commands
    python3 -m dossier check <path> --pack model-evidence --baseline old.json
    python3 -m dossier packs
    python3 -m dossier diff <a.json> <b.json>

`--baseline <report.json>` measures this run against an earlier report of
the same subject. A claim unsupported in both is known debt: reported,
but it does not block — this is how a repository that would fail
everything today starts using the tool. A claim the baseline supported
and this run does not is a regression and blocks, whatever its severity.
A claim the baseline could not support and this run can is reported as
fixed. The comparison summary goes to stderr, so stdout stays the
report in every format, including --json.

`--format markdown` renders the report for a reader away from the
terminal — every verdict, the rationale of every unsupported claim, and
the same digest the text format prints. `--json` still wins when both
are given.

`--allow-commands` is the operator's half of a two-party opt-in. Running
a command the subject declares (the command_succeeds collector) needs
both the subject's declaration in .dossier.json and this flag; neither
alone is enough, because a repository cannot make a stranger's machine
run its Makefile and an operator cannot run something the repository
never offered.

Exit codes are part of the contract, because CI depends on them:

    0  no blocking claim is missing or stale, and no regression
    1  at least one blocking claim is missing or stale, or a claim
       regressed against the baseline
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
from dataclasses import replace
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
    Verdict,
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
    check.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="render the report as markdown instead of terminal text",
    )
    check.add_argument(
        "--allow-commands",
        action="store_true",
        help=(
            "run the commands the subject declares in .dossier.json; without it "
            "command_succeeds claims report UNVERIFIABLE and nothing runs"
        "--baseline",
        help=(
            "a previous report (JSON): claims it already knew as"
            " unsupported become known debt and do not block"
        ),
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

    if args.allow_commands:
        pack = authorise_declared_commands(pack)

    report = engine.check(subject, pack)

    classification = None
    if args.baseline:
        try:
            baseline = _read_report(args.baseline)
            classification = _baseline_classification(baseline, report.to_dict())
        except (OSError, ValueError) as error:
            print(f"baseline: {error}", file=sys.stderr)
            return 2

    if args.json:
        print(report.to_json())
    elif args.format == "markdown":
        print(_format_markdown(report, pack))
    else:
        _print_report(report)

    if classification is not None:
        _print_baseline_summary(classification)

    blocked = (
        report.blocking
        if classification is None
        else _baseline_blocking(report, classification)
    )
    return 1 if blocked else 0


def authorise_declared_commands(pack: Pack) -> Pack:
    """Grant the operator's half of the command opt-in to a pack.

    The command_succeeds collector runs only when two parties agree: the
    subject declares its commands in .dossier.json, and the operator
    passes --allow-commands. A pack may name a declared command but can
    never authorise running it — permission arrives from the operator or
    not at all — so the flag is injected into claim params here, the one
    channel the engine gives a collector, rather than living in a pack.
    Every other claim is passed through untouched and the pack itself is
    left unmodified.
    """
    claims = tuple(
        replace(claim, params={**claim.params, "allow_commands": True})
        if claim.collector == "command_succeeds"
        else claim
        for claim in pack.claims
    )
    return replace(pack, claims=claims)


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


def _baseline_classification(baseline: dict, current: dict) -> dict:
    """Sort every claim the two reports mention into movement categories.

    A pure function of two parsed report documents — the baseline and
    the current run. Shape validation is ``diff_reports``' job, so a
    document that is not a report raises ValueError here too.

        debt       unsupported in both: known debt, does not block
        regressed  supported in the baseline, not now: blocks
        fixed      unsupported in the baseline, supported now
        supported  satisfied in both
        vanished   in the baseline, absent from the current run
        new        absent from the baseline

    Debt must be explicit: a claim the baseline never recorded is never
    forgiven by it. Only the verdict status is compared, never reasons
    or evidence — the same rule `diff` applies.
    """
    movement = diff_reports(baseline, current)
    before = _claim_statuses(baseline)
    after = _claim_statuses(current)

    fixed = [
        {"claim_id": e["claim_id"], "baseline": e["before"], "current": e["after"]}
        for e in movement["gained"]
    ]
    regressed = [
        {"claim_id": e["claim_id"], "baseline": e["before"], "current": e["after"]}
        for e in movement["lost"]
    ]
    debt = [
        {"claim_id": e["claim_id"], "baseline": e["before"], "current": e["after"]}
        for e in movement["changed"]
    ]
    supported: list[str] = []
    for claim_id in movement["unchanged"]:
        if after[claim_id] == SATISFIED:
            supported.append(claim_id)
        else:
            debt.append(
                {
                    "claim_id": claim_id,
                    "baseline": before[claim_id],
                    "current": after[claim_id],
                }
            )
    debt.sort(key=lambda entry: entry["claim_id"])

    return {
        "fixed": fixed,
        "regressed": regressed,
        "debt": debt,
        "supported": supported,
        "vanished": movement["disappeared"],
        "new": movement["appeared"],
    }


def _claim_statuses(document: dict) -> dict[str, str]:
    """Claim id -> status for one parsed report. Call after validation."""
    return {v["claim_id"]: v["status"] for v in document["verdicts"]}


def _baseline_blocking(report: Report, classification: dict) -> tuple[Verdict, ...]:
    """What blocks once the baseline is accounted for.

    Debt never blocks. A regression blocks whatever its severity —
    support that existed in the baseline and is gone now cannot be lost
    quietly. Every other claim keeps its ordinary meaning.
    """
    debt_ids = {entry["claim_id"] for entry in classification["debt"]}
    regressed_ids = {entry["claim_id"] for entry in classification["regressed"]}

    blocked = [
        verdict
        for claim_id, verdict in {v.claim_id: v for v in report.verdicts}.items()
        if claim_id in regressed_ids or (verdict.blocks and claim_id not in debt_ids)
    ]
    return tuple(sorted(blocked, key=lambda verdict: verdict.claim_id))


def _print_baseline_summary(classification: dict) -> None:
    """The baseline comparison, on stderr: stdout stays the report.

    Written to stderr rather than stdout so the chosen output format —
    text, markdown or --json — remains exactly the report, unpolluted:
    CI can parse stdout, and a human can still read what the baseline
    changed about the run's meaning.
    """
    lines = []
    if classification["regressed"]:
        lines.append("regressed since baseline (blocking): " + ", ".join(
            entry["claim_id"] for entry in classification["regressed"]
        ))
    if classification["fixed"]:
        lines.append("fixed since baseline: " + ", ".join(
            entry["claim_id"] for entry in classification["fixed"]
        ))
    if classification["debt"]:
        lines.append("known debt, does not block: " + ", ".join(
            entry["claim_id"] for entry in classification["debt"]
        ))
    if classification["vanished"]:
        lines.append("absent from this run: " + ", ".join(
            entry["claim_id"] for entry in classification["vanished"]
        ))
    if classification["new"]:
        lines.append("new since baseline (assessed normally): " + ", ".join(
            entry["claim_id"] for entry in classification["new"]
        ))
    lines.append(f"unchanged supported: {len(classification['supported'])}")
    for line in lines:
        print(f"baseline: {line}", file=sys.stderr)


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
