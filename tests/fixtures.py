"""Synthetic subjects.

Collectors are tested against repositories built here, never against
this repository or the developer's own machine. A test that reads the
real filesystem passes or fails for reasons that have nothing to do with
the code, and under autonomous delivery that is how a suite quietly
stops meaning anything.
"""

from __future__ import annotations

import shutil
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
