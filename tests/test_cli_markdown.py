"""Behaviour of ``dossier check --format markdown``.

The markdown format exists for the reader the terminal text was never
written for: a non-engineer who needs a report they can paste into a
document. So the tests hold the format to what such a reader needs —
every verdict, the words of every unsupported claim's rationale, the
digest — and to one invariant they must never break: the digest printed
by the markdown format is the report's digest, the same one the text
format prints for the same report. The digest is how this project says
``when``; a format that re-derived it from its own rendering would have
two formats saying two different things about one report.

No filesystem anywhere: the report and pack are built as real objects,
because formatting is a pure function of exactly those two things.
"""

from __future__ import annotations

import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from dossier import cli
from dossier.model import (
    BLOCKING,
    Claim,
    Evidence,
    MATERIAL,
    MISSING,
    Pack,
    Report,
    SATISFIED,
    STALE,
    UNVERIFIABLE,
    Verdict,
)

_DIGEST_LINE = re.compile(r"digest: ([0-9a-f]{16})")


def _pack() -> Pack:
    """A real pack with one claim per status a verdict can take."""
    return Pack(
        name="agent-control",
        version="0.1.0",
        source="test source",
        claims=(
            Claim(
                id="AC-01",
                text="Claim one text.",
                severity=MATERIAL,
                collector="document_present",
                rationale="Rationale for claim one.",
            ),
            Claim(
                id="AC-02",
                text="Claim two text.",
                severity=BLOCKING,
                collector="document_present",
                rationale="Rationale for claim two.",
            ),
            Claim(
                id="AC-03",
                text="Claim three text.",
                severity=MATERIAL,
                collector="document_present",
                rationale="Rationale for claim three.",
            ),
            Claim(
                id="AC-04",
                text="Claim four text.",
                severity=BLOCKING,
                collector="document_present",
                rationale="Rationale for claim four.",
            ),
        ),
    )


def _canned_report() -> Report:
    """One verdict per status, against the claims in _pack()."""
    return Report(
        subject="fixture",
        pack="agent-control",
        pack_version="0.1.0",
        verdicts=(
            Verdict(
                claim_id="AC-01",
                status=SATISFIED,
                severity=MATERIAL,
                reason="found",
                evidence=(Evidence(kind="file", locator="README.md"),),
            ),
            Verdict(
                claim_id="AC-02",
                status=MISSING,
                severity=BLOCKING,
                reason="not there",
            ),
            Verdict(
                claim_id="AC-03",
                status=STALE,
                severity=MATERIAL,
                reason="code moved on",
                evidence=(Evidence(kind="commit", locator="4f2c1ab"),),
            ),
            Verdict(
                claim_id="AC-04",
                status=UNVERIFIABLE,
                severity=BLOCKING,
                reason="nothing to look at",
            ),
        ),
    )


class MarkdownFormatTests(unittest.TestCase):
    """The formatter — a pure function of a report and its pack."""

    def setUp(self):
        self.pack = _pack()
        self.report = _canned_report()
        self.markdown = cli._format_markdown(self.report, self.pack)

    def test_every_verdict_appears_with_its_status(self):
        for verdict in self.report.verdicts:
            self.assertIn(verdict.claim_id, self.markdown, verdict.claim_id)
            self.assertIn(verdict.status, self.markdown, verdict.claim_id)

    def test_every_claim_text_appears(self):
        """A non-engineer cannot act on an id alone; the claim's own words
        are what makes the report pasteable into a document."""
        for claim in self.pack.claims:
            self.assertIn(claim.text, self.markdown, claim.id)

    def test_the_rationale_of_every_unsupported_claim_is_shown(self):
        """The point of the item: why a claim matters, shown for every
        claim the report could not support."""
        for claim in self.pack.claims:
            verdict = next(
                v for v in self.report.verdicts if v.claim_id == claim.id
            )
            if verdict.status == SATISFIED:
                continue
            self.assertIn(claim.rationale, self.markdown, claim.id)

    def test_evidence_locators_are_shown(self):
        self.assertIn("README.md", self.markdown)
        self.assertIn("4f2c1ab", self.markdown)

    def test_the_digest_line_carries_the_report_digest(self):
        self.assertIn(f"digest: {self.report.digest()[:16]}", self.markdown)

    def test_the_digest_is_identical_across_text_and_markdown_formats(self):
        """The Done-when's equality: one report, two formats, one digest.
        This is the test the recorded mutation must fail."""
        text_out = io.StringIO()
        with redirect_stdout(text_out):
            cli._print_report(self.report)
        text_digest = _DIGEST_LINE.search(text_out.getvalue())
        markdown_digest = _DIGEST_LINE.search(self.markdown)

        self.assertIsNotNone(text_digest, "text output carries no digest line")
        self.assertIsNotNone(markdown_digest, "markdown carries no digest line")
        self.assertEqual(markdown_digest.group(1), text_digest.group(1))

    def test_blocking_claims_are_listed(self):
        """The blocking section mirrors the text output's: a blocking
        verdict is MISSING or STALE — an UNVERIFIABLE claim is never a
        block, in either format (model.py's `Verdict.blocks`)."""
        self.assertIn("Blocking claims not supported", self.markdown)
        self.assertIn("- AC-02", self.markdown)
        self.assertNotIn("- AC-04", self.markdown)

    def test_a_report_without_blocking_claims_has_no_blocking_section(self):
        report = Report(
            subject="fixture",
            pack="agent-control",
            pack_version="0.1.0",
            verdicts=(self.report.verdicts[0],),
        )

        markdown = cli._format_markdown(report, self.pack)

        self.assertNotIn("Blocking claims not supported", markdown)


class MarkdownAbsentTests(unittest.TestCase):
    """The Absent case: a report whose pack cannot supply the words.

    The formatter reads the pack for claim text and rationale. When no
    pack is supplied it renders what the report itself owns — the
    verdicts, the reasons, the digest — and invents nothing.
    """

    def setUp(self):
        self.report = _canned_report()

    def test_a_report_with_no_pack_still_renders_verdicts_and_digest(self):
        markdown = cli._format_markdown(self.report, None)

        for verdict in self.report.verdicts:
            self.assertIn(verdict.claim_id, markdown)
            self.assertIn(verdict.status, markdown)
        self.assertIn(f"digest: {self.report.digest()[:16]}", markdown)

    def test_a_report_with_no_pack_shows_no_invented_rationale(self):
        markdown = cli._format_markdown(self.report, None)

        self.assertNotIn("Rationale for claim two.", markdown)
        self.assertNotIn("Why this claim matters", markdown)


class MarkdownCommandTests(unittest.TestCase):
    """The command surface: --format markdown reaches the renderer."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory(prefix="dossier-md-test-")
        self.addCleanup(self._directory.cleanup)

    @staticmethod
    def _run(argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_check_with_format_markdown_prints_the_report(self):
        code, out, _ = self._run(
            ["check", self._directory.name, "--pack", "agent-control",
             "--format", "markdown"]
        )

        self.assertEqual(code, 1)  # nothing in an empty subject is supported
        self.assertIn("# dossier report", out)
        self.assertIn("digest: ", out)

    def test_check_markdown_and_text_agree_on_the_digest_end_to_end(self):
        argv = ["check", self._directory.name, "--pack", "agent-control"]

        _, text_out, _ = self._run([*argv])
        _, markdown_out, _ = self._run([*argv, "--format", "markdown"])

        text_digest = _DIGEST_LINE.search(text_out)
        markdown_digest = _DIGEST_LINE.search(markdown_out)
        self.assertIsNotNone(text_digest)
        self.assertIsNotNone(markdown_digest)
        self.assertEqual(markdown_digest.group(1), text_digest.group(1))

    def test_check_without_format_still_prints_text(self):
        code, out, _ = self._run(
            ["check", self._directory.name, "--pack", "agent-control"]
        )

        self.assertIn("report digest: ", out)
        self.assertNotIn("# dossier report", out)


if __name__ == "__main__":
    unittest.main()
