"""Behaviour of ``dossier diff <a.json> <b.json>``.

The comparison is a pure function of two parsed report documents
(``diff_reports``), so it is tested with no filesystem at all: reports
go in as dicts, exactly as ``json.load`` would hand them over. The
command itself is tested through ``main`` against two files in a
temporary directory, because the Done-when allows the command exactly
one filesystem access — reading its two arguments — and that is the
kind of promise a test should hold a command to.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from dossier import cli
from dossier.diff import diff_reports, document_digest
from dossier.model import (
    Evidence,
    MISSING,
    Report,
    SATISFIED,
    STALE,
    UNVERIFIABLE,
    Verdict,
)


def _verdict(claim_id: str, status: str, severity: str = "material") -> dict:
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
        "pack": "agent-control",
        "pack_version": "0.1.0",
        "verdicts": list(verdicts),
    }


def _canned_report() -> Report:
    """A real Report object, for pinning the digest definition."""
    return Report(
        subject="fixture",
        pack="agent-control",
        pack_version="0.1.0",
        verdicts=(
            Verdict(
                claim_id="AC-01",
                status=SATISFIED,
                severity="material",
                reason="found",
                evidence=(Evidence(kind="file", locator="README.md"),),
            ),
            Verdict(
                claim_id="AC-02",
                status=MISSING,
                severity="material",
                reason="not there",
            ),
        ),
    )


class DiffReportsTests(unittest.TestCase):
    """The pure comparison — no filesystem, no CLI."""

    def test_a_claim_that_changed_status_to_satisfied_is_reported(self):
        before = _report(_verdict("AC-03", MISSING))
        after = _report(_verdict("AC-03", SATISFIED))

        result = diff_reports(before, after)

        self.assertEqual(
            result["gained"],
            [{"claim_id": "AC-03", "before": MISSING, "after": SATISFIED}],
        )
        self.assertEqual(result["lost"], [])
        self.assertEqual(result["changed"], [])

    def test_a_claim_that_changed_status_away_from_satisfied_is_reported(self):
        before = _report(_verdict("AC-05", SATISFIED))
        after = _report(_verdict("AC-05", MISSING))

        result = diff_reports(before, after)

        self.assertEqual(
            result["lost"],
            [{"claim_id": "AC-05", "before": SATISFIED, "after": MISSING}],
        )
        self.assertEqual(result["gained"], [])

    def test_a_status_change_that_neither_gains_nor_loses_support(self):
        before = _report(_verdict("AC-07", UNVERIFIABLE))
        after = _report(_verdict("AC-07", MISSING))

        result = diff_reports(before, after)

        self.assertEqual(
            result["changed"],
            [{"claim_id": "AC-07", "before": UNVERIFIABLE, "after": MISSING}],
        )
        self.assertEqual(result["gained"], [])
        self.assertEqual(result["lost"], [])

    def test_an_unchanged_claim_is_in_unchanged_and_nowhere_else(self):
        before = _report(_verdict("AC-01", SATISFIED), _verdict("AC-02", MISSING))
        after = _report(_verdict("AC-01", SATISFIED), _verdict("AC-02", MISSING))

        result = diff_reports(before, after)

        self.assertEqual(result["unchanged"], ["AC-01", "AC-02"])
        for category in ("gained", "lost", "changed", "appeared", "disappeared"):
            self.assertEqual(result[category], [], category)

    def test_a_claim_present_in_only_one_report_is_not_reported_as_unchanged(self):
        """A claim with no counterpart is a finding — appeared, or
        disappeared — never a quiet pass. This is the case the recorded
        mutation tries to erase."""
        before = _report(_verdict("AC-01", SATISFIED))
        after = _report(_verdict("AC-01", SATISFIED), _verdict("AC-09", SATISFIED))

        result = diff_reports(before, after)

        self.assertEqual(
            result["appeared"], [{"claim_id": "AC-09", "status": SATISFIED}]
        )
        self.assertNotIn("AC-09", result["unchanged"])
        self.assertEqual(result["disappeared"], [])

        mirrored = diff_reports(after, before)
        self.assertEqual(
            mirrored["disappeared"], [{"claim_id": "AC-09", "status": SATISFIED}]
        )
        self.assertNotIn("AC-09", mirrored["unchanged"])
        self.assertEqual(mirrored["appeared"], [])

    def test_every_claim_in_either_report_lands_in_exactly_one_category(self):
        before = _report(
            _verdict("AC-01", SATISFIED),
            _verdict("AC-03", MISSING),
            _verdict("AC-05", SATISFIED),
            _verdict("AC-06", MISSING),
        )
        after = _report(
            _verdict("AC-01", SATISFIED),  # unchanged
            _verdict("AC-03", SATISFIED),  # gained
            _verdict("AC-05", STALE),  # lost
            _verdict("AC-08", MISSING),  # appeared
        )

        result = diff_reports(before, after)

        seen = list(result["unchanged"]) + [
            entry["claim_id"]
            for category in ("gained", "lost", "changed", "appeared", "disappeared")
            for entry in result[category]
        ]
        self.assertEqual(sorted(seen), ["AC-01", "AC-03", "AC-05", "AC-06", "AC-08"])
        self.assertEqual(len(seen), len(set(seen)))

    def test_entries_are_sorted_by_claim_id_not_by_input_order(self):
        """The same two reports must diff identically on any machine, so
        everything is sorted before it is returned."""
        before = _report(_verdict("AC-09", MISSING), _verdict("AC-02", MISSING))
        after = _report(_verdict("AC-09", SATISFIED), _verdict("AC-02", SATISFIED))

        result = diff_reports(before, after)

        self.assertEqual(
            [entry["claim_id"] for entry in result["gained"]], ["AC-02", "AC-09"]
        )

    def test_a_report_diffed_against_itself_changes_nothing(self):
        report = _report(_verdict("AC-01", SATISFIED), _verdict("AC-02", STALE))

        result = diff_reports(report, report)

        self.assertEqual(result["unchanged"], ["AC-01", "AC-02"])
        for category in ("gained", "lost", "changed", "appeared", "disappeared"):
            self.assertEqual(result[category], [], category)

    def test_a_document_that_is_not_a_report_is_rejected(self):
        with self.assertRaises(ValueError):
            diff_reports({"no": "verdicts here"}, _report())
        with self.assertRaises(ValueError):
            diff_reports(_report(), ["not", "a", "document"])
        with self.assertRaises(ValueError):
            diff_reports(
                _report(_verdict("AC-01", SATISFIED)), {"verdicts": ["not a verdict"]}
            )


class DocumentDigestTests(unittest.TestCase):
    """The digest line a diff is cited by."""

    def test_the_digest_matches_the_report_digest_for_a_real_report(self):
        report = _canned_report()

        parsed = json.loads(report.to_json())

        self.assertEqual(document_digest(parsed), report.digest())

    def test_the_digest_is_taken_from_the_document_not_the_file_bytes(self):
        """The identity is the document, not the file: the same report
        written compact must digest the same."""
        report = _canned_report()
        parsed = json.loads(report.to_json())
        compact = json.dumps(parsed, separators=(",", ":"))

        self.assertEqual(document_digest(json.loads(compact)), report.digest())


class DiffCommandTests(unittest.TestCase):
    """The command surface: two files in, one diff out, exit 0 — or exit 2
    when either argument cannot be read as a report."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory(prefix="dossier-diff-test-")
        self.addCleanup(self._directory.cleanup)

    def _write(self, name: str, document: dict, dump=json.dumps) -> str:
        path = Path(self._directory.name) / name
        path.write_text(dump(document), encoding="utf-8")
        return str(path)

    def _absent(self, name: str) -> str:
        return str(Path(self._directory.name) / name)

    @staticmethod
    def _run(argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_the_command_prints_the_change_and_exits_zero(self):
        a = self._write(
            "a.json",
            _report(
                _verdict("AC-01", SATISFIED),
                _verdict("AC-03", MISSING),
                _verdict("AC-05", SATISFIED),
            ),
        )
        b = self._write(
            "b.json",
            _report(
                _verdict("AC-01", SATISFIED),
                _verdict("AC-03", SATISFIED),
                _verdict("AC-05", MISSING),
                _verdict("AC-09", SATISFIED),
            ),
        )

        code, out, _ = self._run(["diff", a, b])

        self.assertEqual(code, 0)
        self.assertIn("gained support", out)
        self.assertIn("AC-03  missing → satisfied", out)
        self.assertIn("lost support", out)
        self.assertIn("AC-05  satisfied → missing", out)
        self.assertIn("appeared:", out)
        self.assertIn("AC-09", out)
        self.assertIn("unchanged: 1 (AC-01)", out)
        self.assertNotIn("changed status:", out)

    def test_a_file_that_is_absent_exits_two(self):
        """The Absent case: an argument that cannot be read means a run
        that cannot be performed, not an empty diff."""
        present = self._write("b.json", _report(_verdict("AC-01", SATISFIED)))

        code, _, err = self._run(["diff", self._absent("missing.json"), present])

        self.assertEqual(code, 2)
        self.assertTrue(err.strip(), "stderr should name the problem")

    def test_a_file_that_is_not_a_report_exits_two(self):
        a = self._write("a.json", {"subject": "not a report"})
        b = self._write("b.json", _report(_verdict("AC-01", SATISFIED)))

        code, _, err = self._run(["diff", a, b])

        self.assertEqual(code, 2)
        self.assertTrue(err.strip(), "stderr should name the problem")

    def test_the_digest_line_cites_each_report_by_its_own_digest(self):
        report = _canned_report()
        changed = json.loads(report.to_json())
        changed["verdicts"][1]["status"] = SATISFIED
        changed["verdicts"][1]["evidence"] = [
            {"kind": "file", "locator": "README.md"}
        ]
        a = self._write("a.json", json.loads(report.to_json()))
        b = self._write("b.json", changed)

        code, out, _ = self._run(["diff", a, b])

        self.assertEqual(code, 0)
        self.assertIn(report.digest()[:16], out)
        self.assertNotEqual(document_digest(changed), report.digest())

    def test_the_digest_survives_a_differently_formatted_file(self):
        """The same report, written compact instead of the check command's
        layout, must still be cited by the digest the check command printed."""
        report = _canned_report()
        changed = json.loads(report.to_json())
        changed["verdicts"][1]["status"] = SATISFIED
        changed["verdicts"][1]["evidence"] = [
            {"kind": "file", "locator": "README.md"}
        ]
        a = self._write(
            "a.json",
            json.loads(report.to_json()),
            dump=lambda document: json.dumps(document, separators=(",", ":")),
        )
        b = self._write("b.json", changed)

        code, out, _ = self._run(["diff", a, b])

        self.assertEqual(code, 0)
        self.assertIn(report.digest()[:16], out)


if __name__ == "__main__":
    unittest.main()
