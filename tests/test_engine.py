"""The engine must never lie and must never die.

A broken collector is a normal event in a repository where agents write
the collectors. The engine's job is to turn every way a collector can go
wrong into an honest UNVERIFIABLE verdict, so that one bad contribution
degrades a single row of the report instead of the whole run.
"""

from __future__ import annotations

import unittest

from dossier import engine, packs, registry
from dossier.model import (
    Claim,
    Evidence,
    MATERIAL,
    Pack,
    SATISFIED,
    UNVERIFIABLE,
)
from fixtures import TempSubject, UNDOCUMENTED, WELL_DOCUMENTED


def _pack(*claims: Claim) -> Pack:
    return Pack(name="test", version="0.0.0", source="tests", claims=claims)


def _claim(collector: str, **params) -> Claim:
    return Claim(
        id="TEST-01",
        text="a claim under test",
        severity=MATERIAL,
        collector=collector,
        rationale="Exists so that the engine has something to evaluate in tests.",
        params=params,
    )


class UnverifiableTests(unittest.TestCase):
    def test_unregistered_collector_is_unverifiable_not_a_pass(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, _pack(_claim("no_such_collector")))
        self.assertEqual(report.verdicts[0].status, UNVERIFIABLE)
        self.assertIn("no_such_collector", report.verdicts[0].reason)

    def test_wrong_params_are_unverifiable_not_a_crash(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(
                subject, _pack(_claim("document_present", wrong_kwarg=1))
            )
        self.assertEqual(report.verdicts[0].status, UNVERIFIABLE)

    def test_a_raising_collector_does_not_sink_the_run(self):
        @registry.register("explodes_for_tests")
        def explodes(subject):
            """Always raises, to prove one bad collector cannot end a run."""
            raise RuntimeError("boom")

        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(
                subject,
                _pack(
                    _claim("explodes_for_tests"),
                    Claim(
                        id="TEST-02",
                        text="the claim after the broken one",
                        severity=MATERIAL,
                        collector="document_present",
                        rationale="Proves later claims still run after an exception.",
                        params={"candidates": ["README.md"]},
                    ),
                ),
            )

        self.assertEqual(report.verdicts[0].status, UNVERIFIABLE)
        self.assertIn("RuntimeError", report.verdicts[0].reason)
        self.assertEqual(report.verdicts[1].status, SATISFIED)

    def test_a_satisfied_verdict_without_evidence_is_rejected(self):
        @registry.register("claims_success_with_nothing")
        def liar(subject):
            """Returns satisfied while citing no evidence at all."""
            return SATISFIED, "trust me", ()

        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, _pack(_claim("claims_success_with_nothing")))

        self.assertEqual(report.verdicts[0].status, UNVERIFIABLE)
        self.assertIn("evidence", report.verdicts[0].reason)

    def test_an_unknown_status_is_rejected(self):
        @registry.register("invents_a_status")
        def inventive(subject):
            """Returns a status that is not in the vocabulary."""
            return "probably_fine", "hmm", (Evidence(kind="file", locator="README.md"),)

        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, _pack(_claim("invents_a_status")))

        self.assertEqual(report.verdicts[0].status, UNVERIFIABLE)
        # Asserting the reason, not just the status, is what gives the engine's
        # own guard power. Without this line the model-layer invariant catches
        # the same case, the verdict still comes back UNVERIFIABLE, and
        # deleting the engine's check breaks nothing that the suite notices.
        self.assertTrue(
            report.verdicts[0].reason.startswith("collector returned unknown status"),
            f"expected the engine's own guard to report this, got: "
            f"{report.verdicts[0].reason!r}",
        )


class RealPackTests(unittest.TestCase):
    def test_a_documented_subject_passes_its_blocking_model_claims(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, packs.get("model-evidence"))
        self.assertEqual(report.blocking, (), msg=report.to_json())

    def test_an_undocumented_subject_fails_blocking_claims(self):
        with TempSubject(UNDOCUMENTED) as subject:
            report = engine.check(subject, packs.get("model-evidence"))
        self.assertTrue(report.blocking)

    def test_this_repository_is_a_valid_subject_for_the_agent_pack(self):
        """dossier must pass its own agent-control pack. If it cannot, it has
        no business telling anyone else their agents are under control."""
        from pathlib import Path

        from dossier.subject import Subject

        root = Path(__file__).resolve().parent.parent
        report = engine.check(Subject.at(root, name="dossier"), packs.get("agent-control"))
        self.assertEqual(report.blocking, (), msg=report.to_json())


if __name__ == "__main__":
    unittest.main()
