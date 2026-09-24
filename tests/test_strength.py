"""The evidence-strength ladder (S1) and claim lineages (P1a).

S1 is done when every existing test stays green on the defaults, and a
claim requiring 'corresponds' against a subject that only 'mentions'
reports UNVERIFIABLE with the rung it reached. The ordering test names
two rungs rather than counting them: comparing rungs as strings would
make 'behaves' weaker than 'corresponds', and only a named pair catches
that.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest import mock

import fixtures
from dossier import engine, registry
from dossier.model import (
    AGREES,
    ANNEX_IV,
    BEHAVES,
    BLOCKING,
    Claim,
    ContractError,
    CORRESPONDS,
    Evidence,
    FRESH,
    MENTIONS,
    MISSING,
    OBSERVED,
    Pack,
    PRESENT,
    SATISFIED,
    SR_11_7,
    STRENGTHS,
    UNVERIFIABLE,
    strength_rank,
)

_RATIONALE = "A reviewer asks for this because without it nothing downstream can be trusted."


def _claim(**overrides) -> Claim:
    base = dict(
        id="T-01",
        text="A test claim.",
        severity=BLOCKING,
        collector="section_present",
        params={"candidates": ["README.md"], "heading": "Purpose"},
        rationale=_RATIONALE,
    )
    base.update(overrides)
    return Claim(**base)


def _run(claim: Claim, files: dict):
    pack = Pack(name="t", version="0", source="test", claims=(claim,))
    with fixtures.TempSubject(files) as subject:
        return engine.check(subject, pack).verdicts[0]


_README = {"README.md": "# Thing\n\n## Purpose\n\nForecasts.\n"}


class Ladder(unittest.TestCase):
    def test_the_ladder_is_ordered_by_position_not_by_spelling(self):
        self.assertGreater(strength_rank(BEHAVES), strength_rank(CORRESPONDS))
        self.assertGreater(strength_rank(FRESH), strength_rank(AGREES))
        self.assertLess(strength_rank(PRESENT), strength_rank(MENTIONS))

    def test_the_ladder_is_exactly_the_six_rungs_in_order(self):
        self.assertEqual(
            STRENGTHS, (PRESENT, MENTIONS, CORRESPONDS, AGREES, FRESH, BEHAVES)
        )

    def test_an_unknown_rung_is_a_contract_error(self):
        with self.assertRaises(ContractError):
            strength_rank("probably")
        with self.assertRaises(ContractError):
            Evidence(kind="file", locator="README.md", strength="probably")
        with self.assertRaises(ContractError):
            _claim(requires="probably")

    def test_both_default_to_present(self):
        self.assertEqual(Evidence(kind="file", locator="a").strength, PRESENT)
        self.assertEqual(_claim().requires, PRESENT)


class Downgrade(unittest.TestCase):
    def test_a_claim_requiring_corresponds_against_a_mention_is_unverifiable(self):
        verdict = _run(_claim(requires=CORRESPONDS), _README)

        self.assertEqual(verdict.status, UNVERIFIABLE)
        self.assertIn("supported only at 'mentions'", verdict.reason)
        self.assertIn("requires 'corresponds'", verdict.reason)
        self.assertTrue(verdict.evidence, "the evidence found stays attached")

    def test_evidence_at_the_required_rung_satisfies(self):
        verdict = _run(_claim(requires=MENTIONS), _README)
        self.assertEqual(verdict.status, SATISFIED)

    def test_the_default_requirement_changes_nothing(self):
        verdict = _run(_claim(), _README)
        self.assertEqual(verdict.status, SATISFIED)

    def test_a_missing_verdict_is_never_touched(self):
        verdict = _run(_claim(requires=BEHAVES), {"README.md": "# Thing\n"})
        self.assertEqual(verdict.status, MISSING)

    def test_the_strongest_piece_of_evidence_decides(self):
        def two_rungs(subject):
            """Cites a weak and a strong piece of evidence."""
            return (
                SATISFIED,
                "two pieces",
                (
                    Evidence(kind="file", locator="a", strength=PRESENT),
                    Evidence(kind="command", locator="b", strength=BEHAVES),
                ),
            )

        # Registered for this test only, so no other test sees it.
        with mock.patch.dict(registry._REGISTRY, {"_two_rungs": two_rungs}):
            verdict = _run(
                _claim(collector="_two_rungs", params={}, requires=FRESH), _README
            )
        self.assertEqual(verdict.status, SATISFIED)


class Lineages(unittest.TestCase):
    def test_the_default_lineage_is_observed_with_an_empty_citation(self):
        claim = _claim()
        self.assertEqual(claim.lineages, (OBSERVED,))
        self.assertEqual(dict(claim.citation_by_lineage), {OBSERVED: ""})

    def test_a_claim_may_carry_several_lineages_with_one_citation_each(self):
        claim = _claim(
            lineages=(ANNEX_IV, SR_11_7),
            citation_by_lineage={ANNEX_IV: "Annex IV §2", SR_11_7: "SR 11-7 §V"},
        )
        self.assertEqual(claim.lineages, (ANNEX_IV, SR_11_7))

    def test_lineages_must_not_be_empty(self):
        with self.assertRaises(ContractError):
            _claim(lineages=(), citation_by_lineage={})

    def test_lineages_come_from_the_closed_vocabulary(self):
        with self.assertRaises(ContractError):
            _claim(lineages=("gdpr",), citation_by_lineage={"gdpr": "x"})

    def test_lineages_must_be_sorted(self):
        with self.assertRaises(ContractError):
            _claim(
                lineages=(SR_11_7, ANNEX_IV),
                citation_by_lineage={ANNEX_IV: "a", SR_11_7: "b"},
            )

    def test_citation_keys_must_match_lineages(self):
        with self.assertRaises(ContractError):
            _claim(lineages=(ANNEX_IV,), citation_by_lineage={SR_11_7: "b"})
        with self.assertRaises(ContractError):
            replace(_claim(), lineages=(ANNEX_IV, SR_11_7))


if __name__ == "__main__":
    unittest.main()
