"""Behaviour of the document collectors.

Note what is being tested and what is not. These tests assert that the
collector reports accurately on what is in the fixture. They do not
assert that the fixture's documentation is any *good* — presence is weak
evidence and the tool must not overstate it.
"""

from __future__ import annotations

import unittest

from dossier.collectors.documents import document_present, section_present
from dossier.model import MISSING, SATISFIED
from dossier.subject import OutsideSubject
from fixtures import EMPTY_SHELL, TempSubject, UNDOCUMENTED, WELL_DOCUMENTED


class DocumentPresentTests(unittest.TestCase):
    def test_finds_the_first_candidate_that_exists(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            status, reason, evidence = document_present(
                subject, candidates=["MISSING.md", "README.md"]
            )
        self.assertEqual(status, SATISFIED)
        self.assertEqual(evidence[0].locator, "README.md")

    def test_reports_missing_when_no_candidate_exists(self):
        with TempSubject(UNDOCUMENTED) as subject:
            status, reason, evidence = document_present(
                subject, candidates=["DATA.md", "docs/DATA.md"]
            )
        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("DATA.md", reason)

    def test_a_file_with_the_right_name_and_no_content_does_not_satisfy(self):
        """The failure mode this collector exists to catch: someone creates
        DATA.md to make the check go green."""
        with TempSubject(EMPTY_SHELL) as subject:
            status, reason, evidence = document_present(
                subject, candidates=["DATA.md"], must_mention=["source"]
            )
        self.assertEqual(status, MISSING)
        self.assertIn("does not mention", reason)

    def test_evidence_cites_a_digest_so_the_finding_can_be_rechecked(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            _, _, evidence = document_present(subject, candidates=["README.md"])
        self.assertEqual(len(evidence[0].digest), 64)

    def test_a_collector_cannot_escape_the_subject_root(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            with self.assertRaises(OutsideSubject):
                document_present(subject, candidates=["../../../etc/passwd"])


class SectionPresentTests(unittest.TestCase):
    def test_finds_a_heading_at_any_level(self):
        with TempSubject({"README.md": "### Limitations\n\ntext\n"}) as subject:
            status, _, evidence = section_present(
                subject, candidates=["README.md"], heading="Limitations"
            )
        self.assertEqual(status, SATISFIED)
        self.assertEqual(evidence[0].locator, "README.md:1")

    def test_is_case_insensitive(self):
        with TempSubject({"README.md": "## LIMITATIONS\n"}) as subject:
            status, _, _ = section_present(
                subject, candidates=["README.md"], heading="Limitations"
            )
        self.assertEqual(status, SATISFIED)

    def test_a_mention_in_prose_is_not_a_section(self):
        """Prose that happens to contain the word is not evidence that the
        subject was documented under that heading."""
        with TempSubject(
            {"README.md": "We considered the limitations carefully.\n"}
        ) as subject:
            status, _, _ = section_present(
                subject, candidates=["README.md"], heading="Limitations"
            )
        self.assertEqual(status, MISSING)

    def test_reports_the_line_number_so_a_reviewer_can_go_and_look(self):
        with TempSubject({"README.md": "# Title\n\nintro\n\n## Evaluation\n"}) as subject:
            _, _, evidence = section_present(
                subject, candidates=["README.md"], heading="Evaluation"
            )
        self.assertEqual(evidence[0].locator, "README.md:5")


if __name__ == "__main__":
    unittest.main()
