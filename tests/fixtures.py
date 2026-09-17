"""Synthetic subjects.

Collectors are tested against repositories built here, never against
this repository or the developer's own machine. A test that reads the
real filesystem passes or fails for reasons that have nothing to do with
the code, and under autonomous delivery that is how a suite quietly
stops meaning anything.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dossier.subject import Subject


class TempSubject:
    """A throwaway directory, used as a context manager.

        with TempSubject({"README.md": "# Purpose\\n"}) as subject:
            ...
    """

    def __init__(self, files: dict[str, str] | None = None, name: str = "fixture"):
        self.files = files or {}
        self.name = name
        self._directory: str | None = None

    def __enter__(self) -> Subject:
        self._directory = tempfile.mkdtemp(prefix="dossier-fixture-")
        root = Path(self._directory)
        for relative, content in self.files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return Subject.at(root, name=self.name)

    def __exit__(self, *exc_info) -> None:
        if self._directory:
            shutil.rmtree(self._directory, ignore_errors=True)


# --- Canned subjects ------------------------------------------------------

WELL_DOCUMENTED = {
    "README.md": (
        "# Example model\n\n"
        "## Purpose\n\nForecasts the thing.\n\n"
        "## Limitations\n\nNot valid outside the sample period.\n\n"
        "## Evaluation\n\nRolling origin with a purge gap.\n\n"
        "To reproduce: `make check`.\n\n"
        "Owner: a named human.\n"
    ),
    "DATA.md": "# Data\n\nEach source is listed with its publisher and retrieval date.\n",
}

UNDOCUMENTED = {
    "README.md": "# thing\n\nit does stuff\n",
}

EMPTY_SHELL = {
    "README.md": "",
    "DATA.md": "",
}


# --- Git fixtures ---------------------------------------------------------

# Screened out of the parent environment: a leaked GIT_DIR or index would
# point the fixture's git at some other repository's state.
_STRIP_FROM_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_NAMESPACE")


def _git(root: Path, args: list[str], commit: int | None = None) -> None:
    """Run one git command inside a fixture, with a fixed identity and clock.

    Machine git config is screened out and author, committer and dates are
    fixed per commit, so the same commits build the same repository on any
    machine — a fixture's shas are reproducible, which is the least a
    fixture in this project owes the determinism rule. ``commit`` is the
    one-based index of the commit being made; it fixes the commit date.
    """
    env = dict(os.environ)
    for key in _STRIP_FROM_ENV:
        env.pop(key, None)
    env.update({"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
    if commit is not None:
        day = f"2026-01-{commit:02d}"
        env.update(
            {
                "GIT_AUTHOR_NAME": "Fixture Author",
                "GIT_AUTHOR_EMAIL": "fixture@example.com",
                "GIT_AUTHOR_DATE": f"{day}T12:00:00+00:00",
                "GIT_COMMITTER_NAME": "Fixture Committer",
                "GIT_COMMITTER_EMAIL": "fixture@example.com",
                "GIT_COMMITTER_DATE": f"{day}T12:00:00+00:00",
            }
        )
    subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


class GitTempSubject(TempSubject):
    """A throwaway git repository, used as a context manager.

        with GitTempSubject([{"README.md": "# x\\n"}, {"DATA.md": "y\\n"}]) as subject:
            ...

    Each dict is one commit, in order: commit one is the history's first
    commit, the last dict is HEAD. Commits are made with the fixed identity
    and clock of ``_git``, so the same commits list builds the same
    repository — and the same shas — every time. An empty commits list is
    a repository with no commits.
    """

    def __init__(self, commits: list[dict[str, str]] | None = None, name: str = "git-fixture"):
        super().__init__(files={}, name=name)
        self.commits = commits or []

    def __enter__(self) -> Subject:
        subject = super().__enter__()
        _git(subject.root, ["init"])
        for index, files in enumerate(self.commits, start=1):
            for relative, content in files.items():
                path = subject.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            _git(subject.root, ["add", "-A"])
            _git(subject.root, ["commit", "-m", f"fixture commit {index}"], commit=index)
        return subject
