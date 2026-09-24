"""P3: the limitations and evaluation claims must be fresh, not merely present.

ME-03 (limitations) and ME-04 (evaluation) now ask documented_within for
their section and require the 'fresh' rung. The Done-when is a STALE
verdict against a fixture whose documentation lags its code. The demo
case the ladder exists for is here too: with no history, a section that
is present can only reach 'mentions', and the claim reports UNVERIFIABLE
rather than a clean pass.

Behaviour is tested with the limit lowered to 2 commits, so the
fixtures stay small whatever DOCS_MAY_LAG_BY is set to; one test pins
the real pack to its constant.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

import fixtures
from dossier import engine, packs
from dossier.model import (
    FRESH,
    MENTIONS,
    MISSING,
    Pack,
    SATISFIED,
    STALE,
    UNVERIFIABLE,
)
from dossier.packs.model_evidence import DOCS_MAY_LAG_BY

_README = (
    "# Model\n\n"
    "## Purpose\n\nForecasts.\n\n"
    "## Limitations\n\nNot valid outside the sample.\n\n"
    "## Evaluation\n\nRolling origin with a purge gap.\n"
)


def _pack(within: int = 2) -> Pack:
    original = packs.get("model-evidence")
    claims = tuple(
        replace(claim, params={**claim.params, "within": within})
        if claim.id in ("ME-03", "ME-04")
        else claim
        for claim in original.claims
    )
    return replace(original, claims=claims)


def _verdicts(subject, pack=None):
    report = engine.check(subject, pack or _pack())
    return {v.claim_id: v for v in report.verdicts}


def _code_commits(n: int) -> list[dict[str, str]]:
    return [{"model.py": f"VERSION = {i}\n"} for i in range(n)]


class Freshness(unittest.TestCase):
    def test_the_real_pack_requires_fresh_docs_within_its_constant(self):
        for claim in packs.get("model-evidence").claims:
            if claim.id in ("ME-03", "ME-04"):
                with self.subTest(claim=claim.id):
                    self.assertEqual(claim.collector, "documented_within")
                    self.assertEqual(claim.requires, FRESH)
                    self.assertEqual(claim.params["within"], DOCS_MAY_LAG_BY)

    def test_docs_that_moved_with_the_code_are_satisfied_at_fresh(self):
        commits = [{"README.md": _README}, *_code_commits(1)]
        with fixtures.GitTempSubject(commits) as subject:
            verdicts = _verdicts(subject)
        for claim_id in ("ME-03", "ME-04"):
            with self.subTest(claim=claim_id):
                verdict = verdicts[claim_id]
                self.assertEqual(verdict.status, SATISFIED)
                self.assertIn(FRESH, [e.strength for e in verdict.evidence])

    def test_docs_the_code_moved_on_without_are_stale(self):
        commits = [{"README.md": _README}, *_code_commits(3)]
        with fixtures.GitTempSubject(commits) as subject:
            verdicts = _verdicts(subject)
        for claim_id in ("ME-03", "ME-04"):
            with self.subTest(claim=claim_id):
                self.assertEqual(verdicts[claim_id].status, STALE)
                self.assertIn("3 commit(s) behind HEAD", verdicts[claim_id].reason)

    def test_a_stale_evaluation_section_blocks(self):
        commits = [{"README.md": _README}, *_code_commits(3)]
        with fixtures.GitTempSubject(commits) as subject:
            report = engine.check(subject, _pack())
        self.assertIn("ME-04", [v.claim_id for v in report.blocking])

    def test_touching_the_doc_again_makes_it_fresh(self):
        commits = [
            {"README.md": _README},
            *_code_commits(3),
            {"README.md": _README + "\nUpdated for version 3.\n"},
        ]
        with fixtures.GitTempSubject(commits) as subject:
            verdicts = _verdicts(subject)
        self.assertEqual(verdicts["ME-04"].status, SATISFIED)

    def test_a_missing_section_is_missing_even_with_fresh_history(self):
        readme = _README.replace("## Limitations\n\nNot valid outside the sample.\n\n", "")
        with fixtures.GitTempSubject([{"README.md": readme}]) as subject:
            verdicts = _verdicts(subject)
        self.assertEqual(verdicts["ME-03"].status, MISSING)
        self.assertEqual(verdicts["ME-04"].status, SATISFIED)

    def test_without_history_a_present_section_is_held_back_not_passed(self):
        """The ladder's own demo: the section is there, at 'mentions', and
        the claim wants 'fresh', so the register says it does not know."""
        with fixtures.TempSubject({"README.md": _README}) as subject:
            verdicts = _verdicts(subject)
        for claim_id in ("ME-03", "ME-04"):
            with self.subTest(claim=claim_id):
                verdict = verdicts[claim_id]
                self.assertEqual(verdict.status, UNVERIFIABLE)
                self.assertEqual([e.strength for e in verdict.evidence], [MENTIONS])

    def test_without_history_a_missing_section_is_still_missing(self):
        with fixtures.TempSubject({"README.md": "# Model\n"}) as subject:
            verdicts = _verdicts(subject)
        self.assertEqual(verdicts["ME-03"].status, MISSING)
        self.assertEqual(verdicts["ME-04"].status, MISSING)


if __name__ == "__main__":
    unittest.main()
