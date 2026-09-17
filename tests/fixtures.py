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
