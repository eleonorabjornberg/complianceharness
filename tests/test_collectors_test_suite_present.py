"""Behaviour of the test_suite_present collector.

The three Done-when fixtures of C7, in order: a real suite satisfies with
the count, an empty tests/ is missing, and a module named test_things.py
containing no test function is missing — that last one is the point of
the item, because a file that is only named like a test is what a grep
counting calls a suite and a reviewer calls a fiction.
"""

from __future__ import annotations

import unittest

from dossier.collectors.test_suite_present import test_suite_present
from dossier.model import MISSING, SATISFIED, UNVERIFIABLE
from fixtures import EMPTY_TEST_DIR, LOOKS_LIKE_TESTS, TESTED, TempSubject


class TestSuitePresentTests(unittest.TestCase):
    def test_a_subject_with_real_tests_reports_satisfied_with_the_count(self):
        with TempSubject(TESTED) as subject:
            status, reason, evidence = test_suite_present(subject)
        self.assertEqual(status, SATISFIED)
        self.assertIn("3 test functions", reason)
        self.assertEqual(
            [e.locator for e in evidence],
            ["tests/test_math.py", "tests/test_words.py"],
        )

    def test_an_empty_test_directory_reports_missing(self):
        with TempSubject(EMPTY_TEST_DIR) as subject:
            status, reason, evidence = test_suite_present(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("tests/", reason)

    def test_a_module_that_only_looks_like_tests_reports_missing(self):
        """The failure mode this collector exists to catch: test_things.py
        mentions test functions in prose and has none."""
        with TempSubject(LOOKS_LIKE_TESTS) as subject:
            status, reason, evidence = test_suite_present(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("0 test functions", reason)

    def test_no_test_directory_is_missing_not_unverifiable(self):
        """Absent case: the absence of a test directory is knowledge, so
        the verdict is MISSING and says so, never UNVERIFIABLE."""
        with TempSubject({"README.md": "# Bare subject\n"}) as subject:
            status, reason, _ = test_suite_present(subject)
        self.assertEqual(status, MISSING)
        self.assertNotEqual(status, UNVERIFIABLE)
        self.assertIn("no test directory", reason)

    def test_fewer_test_functions_than_the_minimum_reports_missing(self):
        """'At least N' comes from the claim's parameters."""
        with TempSubject(TESTED) as subject:
            status, reason, _ = test_suite_present(subject, minimum=4)
        self.assertEqual(status, MISSING)
        self.assertIn("3 test functions", reason)
        self.assertIn("4", reason)

    def test_evidence_cites_a_digest_so_the_finding_can_be_rechecked(self):
        with TempSubject(TESTED) as subject:
            _, _, evidence = test_suite_present(subject)
        self.assertEqual(len(evidence[0].digest), 64)
        self.assertEqual(evidence[0].locator, "tests/test_math.py")


if __name__ == "__main__":
    unittest.main()
