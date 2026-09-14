"""The system under review.

A Subject is a read-only window onto a directory. Collectors are given a
Subject and nothing else, which is what makes them testable: a collector
cannot reach outside the subject root, cannot read the clock, and cannot
depend on where the repository happens to live on disk.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class OutsideSubject(Exception):
    """A collector tried to read outside the subject root."""


@dataclass(frozen=True)
class Subject:
    root: Path
    name: str

    @classmethod
    def at(cls, path: str | Path, name: str | None = None) -> "Subject":
        root = Path(path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"subject root is not a directory: {root}")
        return cls(root=root, name=name or root.name)

    # --- safe reads -------------------------------------------------------

    def _resolve(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise OutsideSubject(f"{relative!r} resolves outside the subject root")
        return candidate

    def exists(self, relative: str) -> bool:
        try:
            return self._resolve(relative).exists()
        except OutsideSubject:
            raise

    def read_text(self, relative: str) -> str:
        return self._resolve(relative).read_text(encoding="utf-8", errors="replace")

    def read_bytes(self, relative: str) -> bytes:
        return self._resolve(relative).read_bytes()

    def digest(self, relative: str) -> str:
        return hashlib.sha256(self.read_bytes(relative)).hexdigest()

    def iter_files(self, suffix: str | None = None) -> Iterator[str]:
        """Every file under the root, as a relative POSIX path, sorted.

        Sorted because report reproducibility depends on it: os.walk order
        is filesystem-dependent and would make digests differ per machine.
        """
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for filename in filenames:
                full = Path(dirpath) / filename
                relative = full.relative_to(self.root).as_posix()
                if suffix is None or relative.endswith(suffix):
                    found.append(relative)
        return iter(sorted(found))

    def first_existing(self, *candidates: str) -> str | None:
        for candidate in candidates:
            if self.exists(candidate):
                return candidate
        return None


_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache"}
