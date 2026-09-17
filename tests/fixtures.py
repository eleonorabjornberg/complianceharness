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
