"""Guards on the packs themselves.

These are the cheapest high-value tests in the project. A claim with a
misspelled collector name, a missing rationale or a duplicated id does
not crash anything — it produces a report that quietly under-reports,
which is the worst failure an evidence register can have. These tests
turn all three into a red build.
"""

from __future__ import annotations

import unittest

from dossier import packs, registry
from dossier import collectors  # noqa: F401  (registers collectors)
from dossier.model import LINEAGES, SEVERITIES, STRENGTHS


class PackIntegrityTests(unittest.TestCase):
    def test_every_claim_names_a_registered_collector(self):
        for pack in packs.all_packs():
            for claim in pack.claims:
                with self.subTest(pack=pack.name, claim=claim.id):
                    self.assertIsNotNone(
                        registry.get(claim.collector),
                        f"{claim.id} names collector {claim.collector!r}, "
                        f"which is not registered. Known: {list(registry.names())}",
                    )

    def test_every_claim_has_a_rationale(self):
        for pack in packs.all_packs():
            for claim in pack.claims:
                with self.subTest(pack=pack.name, claim=claim.id):
                    self.assertGreater(
                        len(claim.rationale.split()),
                        8,
                        f"{claim.id}: a rationale shorter than a sentence is a "
                        f"checklist item, not a claim",
                    )

    def test_claim_ids_are_unique_across_all_packs(self):
        seen: dict[str, str] = {}
        for pack in packs.all_packs():
            for claim in pack.claims:
                self.assertNotIn(
                    claim.id,
                    seen,
                    f"{claim.id} appears in both {seen.get(claim.id)} and {pack.name}",
                )
                seen[claim.id] = pack.name

    def test_severities_are_known(self):
        for pack in packs.all_packs():
            for claim in pack.claims:
                self.assertIn(claim.severity, SEVERITIES)

    def test_every_claim_requires_a_rung_of_the_ladder(self):
        for pack in packs.all_packs():
            for claim in pack.claims:
                with self.subTest(pack=pack.name, claim=claim.id):
                    self.assertIn(claim.requires, STRENGTHS)

    def test_every_claim_names_known_lineages_with_a_citation_each(self):
        for pack in packs.all_packs():
            for claim in pack.claims:
                with self.subTest(pack=pack.name, claim=claim.id):
                    self.assertTrue(claim.lineages)
                    for lineage in claim.lineages:
                        self.assertIn(lineage, LINEAGES)
                    self.assertEqual(
                        set(claim.citation_by_lineage), set(claim.lineages)
                    )

    def test_every_pack_declares_its_source(self):
        for pack in packs.all_packs():
            with self.subTest(pack=pack.name):
                self.assertTrue(
                    pack.source.strip(),
                    f"{pack.name} must say where its expectations come from",
                )


if __name__ == "__main__":
    unittest.main()
