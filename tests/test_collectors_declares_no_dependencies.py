"""Behaviour of the `declares_no_dependencies` collector.

The claim behind it: an unpinned dependency is one nobody can audit —
the subject says it uses requests without saying which requests. Done
when is three fixtures — pinned (SATISFIED), unpinned (MISSING) and
absent (SATISFIED, because a subject that declares nothing has nothing
to pin) — with the unpinned evidence naming the offending lines and the
two satisfied passes told apart by their reason strings.
"""

from __future__ import annotations

import unittest

from dossier.collectors.declares_no_dependencies import declares_no_dependencies
from dossier.model import MISSING, SATISFIED
from fixtures import (
    GEQ_ONLY_REQUIREMENTS,
    LOCKFILE_AND_UNPINNED_REQUIREMENTS,
    LOCKFILE_ONLY,
    NO_DEPENDENCY_DECLARATION,
    PINNED_REQUIREMENTS,
    PYPROJECT_OPTIONAL_UNPINNED,
    PYPROJECT_PINNED,
    PYPROJECT_UNPINNED,
    TempSubject,
    UNPINNED_REQUIREMENTS,
)


class PinnedTests(unittest.TestCase):
    def test_a_fully_pinned_requirements_file_satisfies(self):
        with TempSubject(PINNED_REQUIREMENTS) as subject:
            status, reason, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, SATISFIED)
        self.assertIn("pinned", reason)
        self.assertEqual(evidence[0].locator, "requirements.txt")

    def test_a_pinned_pyproject_dependency_list_satisfies(self):
        with TempSubject(PYPROJECT_PINNED) as subject:
            status, reason, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, SATISFIED)
        self.assertIn("pinned", reason)
        self.assertEqual(evidence[0].locator, "pyproject.toml")

    def test_a_lockfile_pins_the_dependency_set(self):
        with TempSubject(LOCKFILE_ONLY) as subject:
            status, reason, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, SATISFIED)
        self.assertIn("pinned", reason)
        self.assertEqual(evidence[0].locator, "poetry.lock")


class UnpinnedTests(unittest.TestCase):
    def test_an_unpinned_requirements_file_is_missing_and_names_the_offending_lines(self):
        with TempSubject(UNPINNED_REQUIREMENTS) as subject:
            status, reason, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(
            {item.locator for item in evidence},
            {"requirements.txt:1", "requirements.txt:2"},
        )
        notes = " | ".join(item.note for item in evidence)
        self.assertIn("pandas>=2.0", notes)

    def test_a_geq_constraint_is_not_a_pin(self):
        """A range is not an exact version. This is also the test that must
        catch the C6 mutation — treating >= as a pin — which is why the
        fixture uses >= rather than a bare name."""
        with TempSubject(GEQ_ONLY_REQUIREMENTS) as subject:
            status, _, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence[0].locator, "requirements.txt:1")

    def test_an_unpinned_pyproject_dependency_list_is_missing(self):
        with TempSubject(PYPROJECT_UNPINNED) as subject:
            status, _, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(
            {item.locator for item in evidence},
            {"pyproject.toml:4", "pyproject.toml:5"},
        )

    def test_unpinned_optional_dependencies_are_dependencies(self):
        with TempSubject(PYPROJECT_OPTIONAL_UNPINNED) as subject:
            status, _, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual({item.locator for item in evidence}, {"pyproject.toml:5"})

    def test_a_lockfile_does_not_rescue_an_unpinned_requirements_file(self):
        with TempSubject(LOCKFILE_AND_UNPINNED_REQUIREMENTS) as subject:
            status, _, _ = declares_no_dependencies(subject)
        self.assertEqual(status, MISSING)


class AbsentTests(unittest.TestCase):
    def test_no_dependency_file_at_all_is_a_pass_that_says_so(self):
        """Absent — the pass where there is nothing to pin. The reason must
        say which of the two passes it is."""
        with TempSubject(NO_DEPENDENCY_DECLARATION) as subject:
            status, reason, evidence = declares_no_dependencies(subject)
        self.assertEqual(status, SATISFIED)
        self.assertIn("no dependency", reason)
        self.assertTrue(evidence, "a satisfied verdict must cite evidence")

    def test_the_two_satisfied_passes_are_reported_differently(self):
        with TempSubject(NO_DEPENDENCY_DECLARATION) as subject:
            _, absent_reason, _ = declares_no_dependencies(subject)
        with TempSubject(PINNED_REQUIREMENTS) as subject:
            _, pinned_reason, _ = declares_no_dependencies(subject)
        self.assertIn("no dependency", absent_reason)
        self.assertIn("pinned", pinned_reason)
        self.assertNotEqual(absent_reason, pinned_reason)


if __name__ == "__main__":
    unittest.main()
