"""Behaviour of the mutation-evidence collector.

C8. CONTRACT.md's "Test power" section defines the shape of a recorded
mutation: what was broken on purpose, and the test that went red because
of it. These tests pin both halves of the bargain — a real block is
found and located by file and line, and anything short of the block
(prose about mutation testing, a mutation line with no witness) reports
MISSING rather than a pass.
"""

from __future__ import annotations

import unittest

from dossier.collectors.mutation_evidence_recorded import (
    mutation_evidence_recorded,
)
from dossier.model import MISSING, SATISFIED
from fixtures import MUTATION_IN_PROSE, MUTATION_RECORDED, TempSubject, UNDOCUMENTED


class MutationEvidenceRecordedTests(unittest.TestCase):
    def test_a_recorded_block_reports_satisfied(self):
        with TempSubject(MUTATION_RECORDED) as subject:
            status, reason, evidence = mutation_evidence_recorded(subject)
        self.assertEqual(status, SATISFIED)

    def test_the_satisfied_evidence_locates_the_block_by_file_and_line(self):
        with TempSubject(MUTATION_RECORDED) as subject:
            _, reason, evidence = mutation_evidence_recorded(subject)
        self.assertEqual(evidence[0].locator, "BACKLOG.md:5")
        self.assertEqual(len(evidence[0].digest), 64)
        self.assertIn("BACKLOG.md", reason)

    def test_a_repository_with_no_record_reports_missing(self):
        """The Absent case. Its absence is the informative part."""
        with TempSubject(UNDOCUMENTED) as subject:
            status, reason, evidence = mutation_evidence_recorded(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())

    def test_a_mention_in_prose_is_not_a_recorded_mutation(self):
        """The failure mode this collector exists to catch: prose about
        mutation testing reads like evidence to a collector that matches
        the word instead of the record."""
        with TempSubject(MUTATION_IN_PROSE) as subject:
            status, reason, _ = mutation_evidence_recorded(subject)
        self.assertEqual(status, MISSING)
        self.assertIn("caught by", reason)

    def test_a_mutation_line_without_a_caught_by_is_not_a_record(self):
        """Half a block is not a record: `mutation:` without its witness."""
        with TempSubject(
            {"NOTES.md": "    mutation: dropped the empty-evidence guard\n"}
        ) as subject:
            status, _, evidence = mutation_evidence_recorded(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())

    def test_a_caught_by_without_a_mutation_is_not_a_record(self):
        """A test named alone is a test, not a mutation that was caught."""
        with TempSubject(
            {"NOTES.md": "    caught by: test_something_or_other\n"}
        ) as subject:
            status, _, evidence = mutation_evidence_recorded(subject)
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())


if __name__ == "__main__":
    unittest.main()
