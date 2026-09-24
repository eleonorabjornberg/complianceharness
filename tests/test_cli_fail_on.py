"""Behaviour of ``dossier check --fail-on {blocking,any}`` (R3).

The flag lets one pack serve a strict CI and an advisory one without
being rewritten. The Done-when is that exit codes still match the table
in ``cli.py``'s docstring and that every combination is asserted, so the
selection is tested as a pure function over every status × severity ×
setting, and the command is run end to end for the cases that decide an
exit code. The default is asserted separately: changing it would
silently change the meaning of every existing caller's exit code.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from dossier import cli
import fixtures
from dossier.model import (
    ADVISORY,
    BLOCKING,
    MATERIAL,
    MISSING,
    Report,
    SATISFIED,
    SEVERITIES,
    STALE,
    STATUSES,
    UNVERIFIABLE,
    Verdict,
)


def _one(status: str, severity: str, claim_id: str = "X-01") -> Report:
    evidence = ()
    if status == SATISFIED:
        from dossier.model import Evidence

        evidence = (Evidence(kind="file", locator="README.md"),)
    return Report(
        subject="s",
        pack="p",
        pack_version="0",
        verdicts=(
            Verdict(
                claim_id=claim_id,
                status=status,
                severity=severity,
                reason="r",
                evidence=evidence,
            ),
        ),
    )


class FailingSelection(unittest.TestCase):
    def test_every_status_severity_and_setting(self):
        """The whole table, written out rather than derived, so a change
        to either rule shows up as a named cell."""
        expected = {
            # (status, severity): (fails under blocking, fails under any)
            (MISSING, BLOCKING): (True, True),
            (MISSING, MATERIAL): (False, True),
            (MISSING, ADVISORY): (False, True),
            (STALE, BLOCKING): (True, True),
            (STALE, MATERIAL): (False, True),
            (STALE, ADVISORY): (False, True),
            (UNVERIFIABLE, BLOCKING): (False, False),
            (UNVERIFIABLE, MATERIAL): (False, False),
            (UNVERIFIABLE, ADVISORY): (False, False),
            (SATISFIED, BLOCKING): (False, False),
            (SATISFIED, MATERIAL): (False, False),
            (SATISFIED, ADVISORY): (False, False),
        }
        self.assertEqual(
            set(expected), {(s, v) for s in STATUSES for v in SEVERITIES},
            "the table must cover every status and severity",
        )
        for (status, severity), (on_blocking, on_any) in expected.items():
            report = _one(status, severity)
            with self.subTest(status=status, severity=severity, fail_on="blocking"):
                self.assertEqual(bool(cli.failing(report, "blocking")), on_blocking)
            with self.subTest(status=status, severity=severity, fail_on="any"):
                self.assertEqual(bool(cli.failing(report, "any")), on_any)

    def test_the_default_is_blocking(self):
        report = _one(MISSING, MATERIAL)
        self.assertEqual(cli.failing(report), cli.failing(report, "blocking"))
        self.assertEqual(cli.failing(report), ())

    def test_an_unknown_setting_is_refused_not_treated_as_a_default(self):
        with self.assertRaises(ValueError):
            cli.failing(_one(MISSING, MATERIAL), "strict")

    def test_known_debt_is_forgiven_under_any(self):
        report = _one(MISSING, ADVISORY)
        classification = {"debt": [{"claim_id": "X-01"}], "regressed": []}
        self.assertEqual(cli.failing(report, "any", classification), ())

    def test_a_regression_fails_under_either_setting(self):
        report = _one(UNVERIFIABLE, ADVISORY)
        classification = {"debt": [], "regressed": [{"claim_id": "X-01"}]}
        for fail_on in ("blocking", "any"):
            with self.subTest(fail_on=fail_on):
                self.assertEqual(
                    [v.claim_id for v in cli.failing(report, fail_on, classification)],
                    ["X-01"],
                )


# Every blocking model-evidence claim supported; ME-03 (material) missing,
# because the README has no Limitations section.
_ONLY_MATERIAL_MISSING = {
    "README.md": (
        "# Example model\n\n"
        "## Purpose\n\nForecasts the thing.\n\n"
        "## Evaluation\n\nRolling origin with a purge gap.\n\n"
        "To reproduce: `make check`.\n\n"
        "Owner: a named human.\n"
    ),
    "DATA.md": "# Data\n\nEach source is listed with its publisher.\n",
}


class FailOnCommand(unittest.TestCase):
    @staticmethod
    def _run(argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def _check(self, files, *extra):
        with fixtures.TempSubject(files) as subject:
            return self._run(
                ["check", subject.root, "--pack", "model-evidence", *extra]
            )[0]

    def test_a_material_gap_passes_by_default(self):
        self.assertEqual(self._check(_ONLY_MATERIAL_MISSING), 0)

    def test_a_material_gap_passes_under_blocking(self):
        self.assertEqual(self._check(_ONLY_MATERIAL_MISSING, "--fail-on", "blocking"), 0)

    def test_a_material_gap_fails_under_any(self):
        self.assertEqual(self._check(_ONLY_MATERIAL_MISSING, "--fail-on", "any"), 1)

    def test_a_blocking_gap_fails_under_both(self):
        for fail_on in ("blocking", "any"):
            with self.subTest(fail_on=fail_on):
                self.assertEqual(
                    self._check(fixtures.UNDOCUMENTED, "--fail-on", fail_on), 1
                )

    def test_a_clean_subject_passes_under_both(self):
        for fail_on in ("blocking", "any"):
            with self.subTest(fail_on=fail_on):
                self.assertEqual(
                    self._check(fixtures.WELL_DOCUMENTED, "--fail-on", fail_on), 0
                )

    def test_an_unknown_setting_exits_2(self):
        with self.assertRaises(SystemExit) as raised:
            self._check(fixtures.WELL_DOCUMENTED, "--fail-on", "strict")
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
