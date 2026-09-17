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

    A key mapped to ``None`` creates an empty directory, for subjects
    whose shape (a tests/ with nothing in it) is the fact under test.
    """

    def __init__(
        self, files: dict[str, str | None] | None = None, name: str = "fixture"
    ):
        self.files = files or {}
        self.name = name
        self._directory: str | None = None

    def __enter__(self) -> Subject:
        self._directory = tempfile.mkdtemp(prefix="dossier-fixture-")
        root = Path(self._directory)
        for relative, content in self.files.items():
            path = root / relative
            if content is None:
                path.mkdir(parents=True, exist_ok=True)
                continue
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


# --- Mutation evidence (C8) ------------------------------------------------

# A repository that keeps a mutation log in the shape CONTRACT.md's "Test
# power" section describes: what was broken on purpose, and the test that
# went red because of it.
MUTATION_RECORDED = {
    "BACKLOG.md": (
        "# Backlog\n\n"
        "## Mutation log\n\n"
        "    mutation: returned SATISFIED with empty evidence\n"
        "    caught by: test_a_satisfied_verdict_without_evidence_is_rejected\n"
    ),
}

# Mentions mutation testing in prose without recording one. The word is
# not a record: nothing here says what was broken or what caught it, so
# a collector that matches the word instead of the shape reports a pass
# this repository has not earned.
MUTATION_IN_PROSE = {
    "README.md": (
        "# Example\n\n"
        "We plan to adopt mutation testing next quarter, which should\n"
        "strengthen the suite beyond line coverage.\n"
    ),
}


# --- Test-suite subjects (C7) ---------------------------------------------

# Two modules of plain test functions: three tests in total, so the
# collector's reported count can be asserted exactly.
TESTED = {
    "README.md": "# Tested subject\n\nThe suite lives in tests/.\n",
    "tests/test_math.py": (
        "def test_addition():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "def test_subtraction():\n"
        "    assert 3 - 1 == 2\n"
    ),
    "tests/test_words.py": (
        "def test_upper():\n"
        "    assert 'a'.upper() == 'A'\n"
    ),
}

# The point of C7: a module whose name promises tests and whose body has
# none. The planned signatures in the docstring are what a grep for
# "def test" finds and an ast parse does not.
LOOKS_LIKE_TESTS = {
    "tests/test_things.py": (
        "\"\"\"Tests for the things module. (Not written yet.)\n"
        "\n"
        "Planned:\n"
        "    def test_addition(self): ...\n"
        "    def test_subtraction(self): ...\n"
        "\"\"\"\n"
        "\n"
        "def assemble_things():\n"
        "    return ['thing']\n"
    ),
}

# A test directory that exists and holds nothing at all.
EMPTY_TEST_DIR = {
    "README.md": "# Untested subject\n",
    "tests/": None,
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
# --- C6 declares_no_dependencies ------------------------------------------

# Every entry pinned to an exact version: the pass where dependencies are
# declared and all of them are pinned. Comments and blank lines are in the
# file so a parser that counts them as entries fails here.
PINNED_REQUIREMENTS = {
    "requirements.txt": (
        "# pinned by hand\n"
        "requests==2.31.0\n"
        "\n"
        "numpy==1.26.4\n"
    ),
}

# A bare name and a `>=` range are both unpinned. The `>=` line is the one
# that must catch the C6 mutation: a range is not a pin.
UNPINNED_REQUIREMENTS = {
    "requirements.txt": (
        "requests\n"
        "pandas>=2.0\n"
    ),
}

# Exactly one `>=` entry, so exactly one thing can go wrong under mutation.
GEQ_ONLY_REQUIREMENTS = {
    "requirements.txt": "pandas>=2.0\n",
}

# The pass where there is nothing to audit at all.
NO_DEPENDENCY_DECLARATION = {
    "README.md": "# No dependencies declared here\n",
}

# pyproject dependency lists, multi-line so the parser's array tracking is
# exercised and the evidence's line numbers are not all 1.
PYPROJECT_PINNED = {
    "pyproject.toml": (
        "[project]\n"
        'name = "example"\n'
        "dependencies = [\n"
        '    "requests==2.31.0",\n'
        '    "numpy==1.26.4",\n'
        "]\n"
    ),
}

PYPROJECT_UNPINNED = {
    "pyproject.toml": (
        "[project]\n"
        'name = "example"\n'
        "dependencies = [\n"
        '    "requests",\n'
        '    "pandas>=2.0",\n'
        "]\n"
    ),
}

# Optional dependencies are dependencies too.
PYPROJECT_OPTIONAL_UNPINNED = {
    "pyproject.toml": (
        "[project]\n"
        'name = "example"\n'
        "\n"
        "[project.optional-dependencies]\n"
        'test = ["pytest>=8.0"]\n'
    ),
}

# A lockfile pins by construction.
LOCKFILE_ONLY = {
    "poetry.lock": "# generated lockfile\n",
}

# A lockfile does not rescue an unpinned requirements file.
LOCKFILE_AND_UNPINNED_REQUIREMENTS = {
    "requirements.txt": "requests\n",
    "uv.lock": "# generated lockfile\n",
}


# --- Command declarations (C4) ----------------------------------------------

# A subject declaring its own commands in .dossier.json at its root: a name
# mapped to an argv list. JSON rather than TOML — tomllib is 3.11+ and
# dossier runs on 3.10. The commands are POSIX fixtures the way the git
# fixtures are git fixtures: /bin/true, /bin/false and /bin/sleep are the
# smallest witnesses of a passing, a failing and a hanging command.
DECLARED_PASSING_COMMAND = {
    "README.md": "# Command subject\n",
    ".dossier.json": '{"commands": {"suite": ["true"]}}\n',
}

DECLARED_FAILING_COMMAND = {
    ".dossier.json": '{"commands": {"suite": ["false"]}}\n',
}

# Five seconds is far longer than the timeout the test passes, and far
# shorter than any real hang: the fixture proves the timeout fires, not
# how long a patient command takes.
DECLARED_SLOW_COMMAND = {
    ".dossier.json": '{"commands": {"suite": ["sleep", "5"]}}\n',
}

# No .dossier.json at all: the subject never offered a command to run.
UNDECLARED_COMMANDS = {
    "README.md": "# Undeclared subject\n",
}

# A declaration exists, but the claim's name is not in it.
UNDECLARED_COMMAND_NAME = {
    ".dossier.json": '{"commands": {"lint": ["true"]}}\n',
}

# A declaration that is not JSON: UNVERIFIABLE, never a crash.
MALFORMED_COMMAND_DECLARATION = {
    ".dossier.json": "{ commands: ",
}
