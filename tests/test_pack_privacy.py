"""The privacy pack (P2) against fixture subjects.

The claims are headings in a privacy document, so the fixtures are
documents: one with every section, one missing the legal basis (a
blocking claim), one missing only retention (a material claim), and
one with no privacy document at all.
"""

from __future__ import annotations

import unittest

import fixtures
from dossier import engine, packs
from dossier.model import BLOCKING, MISSING, SATISFIED

_FULL = (
    "# Privacy\n\n"
    "## Purpose of processing\n\nDelivering orders.\n\n"
    "## Legal basis\n\nContract.\n\n"
    "## Retention\n\nSix years after the last order.\n\n"
    "## Data subject rights\n\nprivacy@example.test, answered within a month.\n\n"
    "## International transfers\n\nNone: all processing stays in the EU.\n"
)


def _statuses(files):
    pack = packs.get("privacy")
    with fixtures.TempSubject(files) as subject:
        report = engine.check(subject, pack)
    return {v.claim_id: v.status for v in report.verdicts}, report


class PrivacyPack(unittest.TestCase):
    def test_the_pack_is_registered(self):
        self.assertIn("privacy", packs.names())

    def test_a_complete_privacy_document_satisfies_every_claim(self):
        statuses, report = _statuses({"PRIVACY.md": _FULL})
        self.assertEqual(set(statuses.values()), {SATISFIED})
        self.assertEqual(report.blocking, ())

    def test_a_missing_legal_basis_blocks(self):
        text = _FULL.replace("## Legal basis\n\nContract.\n\n", "")
        statuses, report = _statuses({"PRIVACY.md": text})
        self.assertEqual(statuses["PR-02"], MISSING)
        self.assertEqual([v.claim_id for v in report.blocking], ["PR-02"])

    def test_a_missing_retention_period_is_reported_but_does_not_block(self):
        text = _FULL.replace("## Retention\n\nSix years after the last order.\n\n", "")
        statuses, report = _statuses({"PRIVACY.md": text})
        self.assertEqual(statuses["PR-03"], MISSING)
        self.assertEqual(report.blocking, ())

    def test_no_privacy_document_misses_every_claim(self):
        statuses, _ = _statuses({"README.md": "# thing\n"})
        self.assertEqual(set(statuses.values()), {MISSING})

    def test_the_sections_may_live_in_docs(self):
        statuses, _ = _statuses({"docs/PRIVACY.md": _FULL})
        self.assertEqual(set(statuses.values()), {SATISFIED})

    def test_purpose_and_legal_basis_are_the_blocking_claims(self):
        blocking = {c.id for c in packs.get("privacy").claims if c.severity == BLOCKING}
        self.assertEqual(blocking, {"PR-01", "PR-02"})


if __name__ == "__main__":
    unittest.main()
