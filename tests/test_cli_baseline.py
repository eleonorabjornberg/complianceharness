"""Behaviour of ``dossier check --baseline <report.json>``.

A baseline is what makes the tool adoptable: a repository that would
fail everything today can record that failure once and move forward,
because what the baseline already knew about is debt, not noise. The
Done-when names the three movements that matter — unsupported in both
(known debt, does not block), supported before and not now (regression,
blocks), unsupported before and supported now (fixed, reported) — and
the tests hold the command to exactly those, plus the boundary that
makes debt honest: a claim the baseline never knew about is never
forgiven by it.

The classification is a pure function of two parsed report documents —
the baseline and the current run — so most of it is tested with no
filesystem at all, in the shape ``json.load`` hands over. The command
itself is tested against fixture subjects and a baseline captured from
a real run, because the Done-when is also about exit codes, and those
only exist once the command runs. The baseline summary is written to
stderr: stdout stays the report, in whatever format was asked for,
including ``--json`` — the report document's shape is not the baseline
feature's business, and a schema that drifts to carry it would break
every downstream consumer.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from dossier import cli
import fixtures
from dossier.model import (
    BLOCKING,
    MATERIAL,
    MISSING,
    Report,
    SATISFIED,
    STALE,
    UNVERIFIABLE,
    Verdict,
)

def _verdict(claim_id: str, status: str, severity: str = MATERIAL) -> dict:
    """One verdict, in the shape Report.to_dict() emits."""
    return {
        "claim_id": claim_id,
        "status": status,
        "severity": severity,
        "reason": f"{claim_id} reason",
        "evidence": [],
    }


def _report(*verdicts: dict) -> dict:
    """A parsed report document built from verdicts."""
    return {
        "subject": "fixture",
        "pack": "model-evidence",
        "pack_version": "0.1.0",
        "verdicts": list(verdicts),
    }


class BaselineClassificationTests(unittest.TestCase):
    """The pure comparison — no filesystem, no CLI."""

    def test_a_claim_unsupported_in_both_baseline_and_current_is_known_debt(self):
        baseline = _report(_verdict("ME-05", MISSING))
        current = _report(_verdict("ME-05", MISSING))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["debt"],
            [
                {
                    "claim_id": "ME-05",
                    "baseline": MISSING,
                    "current": MISSING,
                }
            ],
        )
        self.assertEqual(result["regressed"], [])
        self.assertEqual(result["fixed"], [])

    def test_an_unverifiable_claim_that_stays_unverifiable_is_debt_too(self):
        """Unsupported means not satisfied, whatever the flavour: a claim
        the machine could not check last time and cannot check now is the
        same noise the baseline exists to retire."""
        baseline = _report(_verdict("ME-01", UNVERIFIABLE))
        current = _report(_verdict("ME-01", UNVERIFIABLE))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["debt"],
            [
                {
                    "claim_id": "ME-01",
                    "baseline": UNVERIFIABLE,
                    "current": UNVERIFIABLE,
                }
            ],
        )

    def test_known_debt_records_the_movement_when_unsupported_statuses_differ(self):
        """Still unsupported, but differently: the debt entry says so, so
        a reader can see the subject changed even though nothing blocks."""
        baseline = _report(_verdict("ME-05", MISSING))
        current = _report(_verdict("ME-05", STALE))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["debt"],
            [
                {
                    "claim_id": "ME-05",
                    "baseline": MISSING,
                    "current": STALE,
                }
            ],
        )
        self.assertEqual(result["regressed"], [], "no support was lost")

    def test_a_claim_that_regressed_since_the_baseline_is_reported_as_regressed(self):
        baseline = _report(_verdict("ME-03", SATISFIED))
        current = _report(_verdict("ME-03", MISSING))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["regressed"],
            [
                {
                    "claim_id": "ME-03",
                    "baseline": SATISFIED,
                    "current": MISSING,
                }
            ],
        )
        self.assertEqual(result["debt"], [], "support was lost, not carried")

    def test_a_claim_fixed_since_the_baseline_is_reported_as_fixed(self):
        """The third Done-when case — and the catcher of the recorded
        mutation: a claim the baseline knew as debt and the current run
        supports is an achievement, reported as such."""
        baseline = _report(_verdict("ME-02", MISSING))
        current = _report(_verdict("ME-02", SATISFIED))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["fixed"],
            [
                {
                    "claim_id": "ME-02",
                    "baseline": MISSING,
                    "current": SATISFIED,
                }
            ],
        )
        self.assertEqual(result["debt"], [])
        self.assertEqual(result["regressed"], [])

    def test_a_claim_satisfied_in_both_reports_is_neither_debt_nor_a_fix(self):
        baseline = _report(_verdict("ME-01", SATISFIED))
        current = _report(_verdict("ME-01", SATISFIED))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(result["supported"], ["ME-01"])
        for category in ("fixed", "regressed", "debt", "vanished", "new"):
            self.assertEqual(result[category], [], category)

    def test_a_claim_absent_from_the_baseline_is_assessed_normally(self):
        """Debt must be explicit. A claim the baseline never recorded gets
        no forgiveness from it — it lands in `new` and keeps its ordinary
        meaning, whatever that is."""
        baseline = _report(_verdict("ME-01", SATISFIED))
        current = _report(_verdict("ME-01", SATISFIED), _verdict("ME-09", MISSING))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["new"],
            [{"claim_id": "ME-09", "status": MISSING}],
        )
        self.assertEqual(result["debt"], [], "the baseline never blessed ME-09")

    def test_a_claim_absent_from_the_current_run_is_reported_as_vanished(self):
        baseline = _report(_verdict("ME-01", SATISFIED), _verdict("ME-07", MISSING))
        current = _report(_verdict("ME-01", SATISFIED))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            result["vanished"],
            [{"claim_id": "ME-07", "status": MISSING}],
        )

    def test_every_claim_id_in_either_report_lands_in_exactly_one_category(self):
        baseline = _report(
            _verdict("ME-01", SATISFIED),  # unchanged supported
            _verdict("ME-02", MISSING),  # fixed
            _verdict("ME-03", SATISFIED),  # regressed
            _verdict("ME-05", MISSING),  # unchanged unsupported: debt
            _verdict("ME-07", MISSING),  # vanished
        )
        current = _report(
            _verdict("ME-01", SATISFIED),
            _verdict("ME-02", SATISFIED),
            _verdict("ME-03", STALE),
            _verdict("ME-05", UNVERIFIABLE),
            _verdict("ME-09", MISSING),  # new
        )

        result = cli._baseline_classification(baseline, current)

        seen = list(result["supported"]) + [
            entry["claim_id"]
            for category in ("fixed", "regressed", "debt", "vanished", "new")
            for entry in result[category]
        ]
        self.assertEqual(
            sorted(seen), ["ME-01", "ME-02", "ME-03", "ME-05", "ME-07", "ME-09"]
        )
        self.assertEqual(len(seen), len(set(seen)))

    def test_entries_are_sorted_by_claim_id_not_by_input_order(self):
        """The same two reports must classify identically on any machine,
        so every category is sorted before it is returned."""
        baseline = _report(_verdict("ME-09", SATISFIED), _verdict("ME-02", SATISFIED))
        current = _report(_verdict("ME-09", MISSING), _verdict("ME-02", MISSING))

        result = cli._baseline_classification(baseline, current)

        self.assertEqual(
            [entry["claim_id"] for entry in result["regressed"]], ["ME-02", "ME-09"]
        )

    def test_a_baseline_that_is_not_a_report_is_rejected(self):
        with self.assertRaises(ValueError):
            cli._baseline_classification({"subject": "not a report"}, _report())
        with self.assertRaises(ValueError):
            cli._baseline_classification(
                _report(_verdict("ME-01", SATISFIED)), {"verdicts": ["not a verdict"]}
            )


def _real_report(*verdicts: Verdict) -> Report:
    return Report(
        subject="fixture",
        pack="model-evidence",
        pack_version="0.1.0",
        verdicts=verdicts,
    )


class BaselineBlockingTests(unittest.TestCase):
    """What blocks once the baseline is accounted for."""

    def test_known_debt_does_not_block_even_when_the_pack_calls_it_blocking(self):
        report = _real_report(
            Verdict(
                claim_id="ME-02",
                status=MISSING,
                severity=BLOCKING,
                reason="not there",
            ),
        )
        classification = cli._baseline_classification(
            _report(_verdict("ME-02", MISSING, severity=BLOCKING)), report.to_dict()
        )

        blocked = cli._baseline_blocking(report, classification)

        self.assertEqual(blocked, ())

    def test_a_regression_blocks_regardless_of_its_severity(self):
        """Support that existed in the baseline and is gone now is a
        regression — an advisory claim cannot lose support quietly."""
        report = _real_report(
            Verdict(
                claim_id="ME-05",
                status=STALE,
                severity=MATERIAL,
                reason="code moved on",
            ),
        )
        classification = cli._baseline_classification(
            _report(_verdict("ME-05", SATISFIED)), report.to_dict()
        )

        blocked = cli._baseline_blocking(report, classification)

        self.assertEqual([verdict.claim_id for verdict in blocked], ["ME-05"])

    def test_a_blocking_claim_outside_the_baseline_still_blocks(self):
        """The baseline forgives only what it recorded. A claim it never
        saw keeps its ordinary meaning — here, blocking."""
        report = _real_report(
            Verdict(
                claim_id="ME-09",
                status=MISSING,
                severity=BLOCKING,
                reason="not there",
            ),
        )
        classification = cli._baseline_classification(
            _report(_verdict("ME-01", SATISFIED)), report.to_dict()
        )

        blocked = cli._baseline_blocking(report, classification)

        self.assertEqual([verdict.claim_id for verdict in blocked], ["ME-09"])

    def test_a_claim_that_both_regressed_and_blocks_is_listed_once(self):
        report = _real_report(
            Verdict(
                claim_id="ME-02",
                status=MISSING,
                severity=BLOCKING,
                reason="not there",
            ),
        )
        classification = cli._baseline_classification(
            _report(_verdict("ME-02", SATISFIED)), report.to_dict()
        )

        blocked = cli._baseline_blocking(report, classification)

        self.assertEqual(
            [verdict.claim_id for verdict in blocked], ["ME-02"]
        )

    def test_the_blocked_list_is_sorted_by_claim_id(self):
        report = _real_report(
            Verdict(
                claim_id="ME-05", status=STALE, severity=MATERIAL, reason="stale"
            ),
            Verdict(
                claim_id="ME-02", status=MISSING, severity=BLOCKING, reason="gone"
            ),
        )
        classification = cli._baseline_classification(
            _report(_verdict("ME-05", SATISFIED), _verdict("ME-02", SATISFIED)),
            report.to_dict(),
        )

        blocked = cli._baseline_blocking(report, classification)

        self.assertEqual(
            [verdict.claim_id for verdict in blocked], ["ME-02", "ME-05"]
        )


# --- Command-level subjects -------------------------------------------------
#
# model-evidence claims, verified against the collectors: _BAD satisfies
# only ME-01 (README exists); _OK satisfies all six. Claim ids and
# statuses here are the pack's own, probed against these fixture files.

_BAD_SUBJECT = {
    "README.md": "# Probe\n\n## Purpose\n\nForecasts the thing.\n",
}

_OK_SUBJECT = {
    "README.md": (
        "# Probe\n\n"
        "## Purpose\n\nForecasts the thing.\n\n"
        "## Limitations\n\nNot valid outside the sample period.\n\n"
        "## Evaluation\n\nRolling origin with a purge gap.\n\n"
        "To reproduce: `make check`.\n\n"
        "Owner: a named human.\n"
    ),
    "DATA.md": (
        "# Data\n\nEach source is listed with its publisher and retrieval date.\n"
    ),
}


class BaselineCommandTests(unittest.TestCase):
    """The command surface: flag parsing, exit codes, stream discipline."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory(prefix="dossier-baseline-test-")
        self.addCleanup(self._directory.cleanup)

    def _write_baseline(self, name: str, document: dict) -> str:
        path = Path(self._directory.name) / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def _capture_baseline(self, files: dict, expected_exit: int = 1) -> str:
        """Run a real check and keep its JSON report as the baseline file.

        The baseline is whatever the earlier run actually produced: a
        failing subject's report is the adopter's starting debt, and a
        passing subject's report is the state regressions are measured
        against.
        """
        with fixtures.TempSubject(files) as subject:
            code, out, _ = self._run(
                ["check", subject.root, "--pack", "model-evidence", "--json"]
            )
        self.assertEqual(code, expected_exit)
        return self._write_baseline("baseline.json", json.loads(out))

    @staticmethod
    def _run(argv):
        argv = [str(item) for item in argv]  # argparse takes strings
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_a_failing_subject_with_a_matching_baseline_exits_zero(self):
        """The adoption story, end to end: a run that fails everything,
        measured against the report of its own earlier state, exits 0 —
        the failures are known debt, named on stderr, and still visible
        in the report itself."""
        baseline_path = self._capture_baseline(_BAD_SUBJECT)

        with fixtures.TempSubject(_BAD_SUBJECT) as subject:
            code, out, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--baseline",
                    baseline_path,
                ]
            )

        self.assertEqual(code, 0, "known debt does not block")
        self.assertIn("known debt", err)
        self.assertIn("ME-05", err)
        self.assertIn("MISS", out, "debt is reported, not hidden")

    def test_a_claim_that_regressed_since_the_baseline_exits_one(self):
        baseline_path = self._capture_baseline(_OK_SUBJECT, expected_exit=0)

        with fixtures.TempSubject(_BAD_SUBJECT) as subject:
            code, out, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--baseline",
                    baseline_path,
                ]
            )

        self.assertEqual(code, 1, "a regression blocks")
        self.assertIn("regressed", err)
        self.assertIn("ME-02", err, "DATA.md was supported before, missing now")
        self.assertIn("ME-03", err, "the Limitations section was supported before")

    def test_a_claim_fixed_since_the_baseline_is_reported_as_such(self):
        """The third Done-when case, at the command surface. This is the
        test the recorded mutation must fail."""
        baseline_path = self._capture_baseline(_BAD_SUBJECT)

        with fixtures.TempSubject(_OK_SUBJECT) as subject:
            code, out, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--baseline",
                    baseline_path,
                ]
            )

        self.assertEqual(code, 0, "a fix is not a regression")
        self.assertIn("fixed", err)
        self.assertIn("ME-02", err, "DATA.md went from missing to satisfied")
        self.assertIn("ME-03", err)

    def test_a_baseline_file_that_is_absent_exits_two(self):
        """The Absent case: a baseline that cannot be read means a run
        that cannot be performed — exit 2, not an unchecked run."""
        with fixtures.TempSubject(_BAD_SUBJECT) as subject:
            absent = str(Path(self._directory.name) / "no-such-report.json")
            code, _, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--baseline",
                    absent,
                ]
            )

        self.assertEqual(code, 2)
        self.assertTrue(err.strip(), "stderr should name the problem")

    def test_a_baseline_file_that_is_not_a_report_exits_two(self):
        not_a_report = self._write_baseline("not-a-report.json", {"subject": "x"})

        with fixtures.TempSubject(_BAD_SUBJECT) as subject:
            code, _, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--baseline",
                    not_a_report,
                ]
            )

        self.assertEqual(code, 2)
        self.assertTrue(err.strip(), "stderr should name the problem")

    def test_json_stdout_stays_a_report_with_a_baseline(self):
        """The report document's shape is not the baseline feature's
        business: with --json, stdout parses as exactly the four report
        keys, and the baseline summary goes to stderr."""
        baseline_path = self._capture_baseline(_BAD_SUBJECT)

        with fixtures.TempSubject(_BAD_SUBJECT) as subject:
            code, out, err = self._run(
                [
                    "check",
                    subject.root,
                    "--pack",
                    "model-evidence",
                    "--json",
                    "--baseline",
                    baseline_path,
                ]
            )

        self.assertEqual(code, 0)
        document = json.loads(out)
        self.assertEqual(
            sorted(document), ["pack", "pack_version", "subject", "verdicts"]
        )
        self.assertIn("known debt", err)


if __name__ == "__main__":
    unittest.main()
