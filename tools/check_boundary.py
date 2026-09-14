"""Refuse a diff that touches a file the contract reserves for a human.

    python3 tools/check_boundary.py --list
    python3 tools/check_boundary.py origin/main

The reserved paths are not written here. They are read out of CONTRACT.md,
so the list exists in exactly one place and the check cannot fall out of
step with the contract it enforces.

Exit codes: 0 the diff respects the boundary, 1 it does not, 2 the check
could not be performed — which is also a failure, because a boundary that
cannot be checked is not a boundary.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent.parent / "CONTRACT.md"
HEADING = "## Human-only paths"
PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.(py|md|yml|toml)$")


def reserved_paths(contract: Path = CONTRACT) -> list[str]:
    lines = contract.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(HEADING) + 1
    except ValueError:
        raise SystemExit(f"2: {contract.name} has no '{HEADING}' section")

    found = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if not line.startswith("    "):
            continue
        token = line.split()[0]
        if PATH.match(token):
            found.append(token)
    if not found:
        raise SystemExit(f"2: no paths parsed from '{HEADING}' in {contract.name}")
    return found


def changed_paths(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"2: git diff against {base} failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def main(argv: list[str]) -> int:
    reserved = reserved_paths()

    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if argv[0] == "--list":
        for path in reserved:
            print(path)
        return 0

    touched = sorted(set(changed_paths(argv[0])) & set(reserved))
    if touched:
        print("this diff changes files the contract reserves for a human:")
        for path in touched:
            print(f"  {path}")
        print()
        print("work may not edit its own judge. If the change genuinely needs")
        print("one of these, say so in the pull request and stop.")
        return 1

    print(f"boundary respected: {len(reserved)} reserved paths untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
