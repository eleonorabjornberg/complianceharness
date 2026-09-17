#!/usr/bin/env python3
"""Run both packs against a foreign subject and refuse to swallow a crash.

Backlog I4: CI points dossier at one public repository, pinned by sha,
and asserts only that every pack exits 0 or 1. Both are reports --
0 nothing blocking missing, 1 blocking claims missing -- which is the
tool doing its job against a codebase that is not this one. Exit 2
means the run could not be performed at all: a crash on code the tool
has never seen, the exact failure the item exists to catch. A shell
line like ``dossier ... || true`` would call that crash green, so the
guard is explicit and tested (tests/test_foreign_subject.py).

Standard library only, like everything else here.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKS = ("model-evidence", "agent-control")
ALLOWED = frozenset({0, 1})

RunPack = Callable[[Path, str], subprocess.CompletedProcess]


def all_packs_reported(return_codes: Iterable[int]) -> bool:
    """True when every pack produced a report: exit 0 or 1, never 2."""
    codes = list(return_codes)
    return bool(codes) and all(code in ALLOWED for code in codes)


def run_pack(subject: Path, pack: str) -> subprocess.CompletedProcess:
    """Run one pack against the subject, inside this checkout."""
    env = dict(
        os.environ,
        PYTHONPATH=str(REPO_ROOT / "src"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return subprocess.run(
        [sys.executable, "-B", "-m", "dossier", "check", str(subject), "--pack", pack],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def main(argv: list[str], run_pack: RunPack = run_pack) -> int:
    """Exit 0 when both packs reported; anything else fails CI."""
    if len(argv) != 1:
        print("usage: foreign_subject.py <subject-path>", file=sys.stderr)
        return 1
    subject = Path(argv[0])
    if not subject.is_absolute():
        subject = REPO_ROOT / subject

    codes = []
    for pack in PACKS:
        result = run_pack(subject, pack)
        codes.append(result.returncode)
        print(f"== {pack}: exit {result.returncode}")
        if result.returncode not in ALLOWED:
            # A crash is the one thing this job must not pass through.
            # Show the tool's own words so the failure is diagnosable.
            print(f"-- {pack} crashed (exit {result.returncode}); output follows",
                  file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return 1
    return 0 if all_packs_reported(codes) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
