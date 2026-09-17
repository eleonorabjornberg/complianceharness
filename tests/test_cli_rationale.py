"""Behaviour of the inline rationale line in the default text output (R4).

A reviewer reading the default output sees why a claim matters at the
moment it fails: every verdict that is not SATISFIED prints one line of
its claim's rationale under the verdict line. Rationales live on claims
in the pack, not on verdicts in the report, so the formatter looks them
up by the report's pack name — the report object is untouched.

The truncation is the part under contract: it cuts by character count,
never at a word boundary, so the rendered line is a pure function of the
rationale's characters and cannot vary with where words fall.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from dossier import cli, packs
from dossier.model import (
    Evidence,
    MISSING,
    Report,
    SATISFIED,
    UNVERIFIABLE,
    Verdict,
)

from fixtures import UNDOCUMENTED, TempSubject

_WIDTH = cli._RATIONALE_WIDTH


def _truncate_by_character_count(rationale: str) -> str:
    """The truncation rule restated independently of the implementation."""
    collapsed = " ".join(rationale.split())
    if len(collapsed) <= _WIDTH:
        return collapsed
    return collapsed[: _WIDTH - 1] + "…"


def _render(report: Report) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        cli._print_report(report)
    return out.getvalue()


def _report(*verdicts: Verdict) -> Report:
    return Report(
        subject="fixture",
        pack="model-evidence",
        pack_version="0.1.0",
        verdicts=verdicts,
    )


def _verdict(claim_id: str, status: str, evidence: tuple = ()) -> Verdict:
    return Verdict(
        claim_id=claim_id,
        status=status,
        reason=f"{claim_id} reason",
        severity="blocking",
        evidence=evidence,
    )


def _rationale_of(claim_id: str) -> str:
    pack = packs.get("model-evidence")
    return next(c.rationale for c in pack.claims if c.id == claim_id)


class TruncationTests(unittest.TestCase):
    """The truncation helper, against strings whose cut point is chosen
    so that a word-boundary cut would render something different."""

    def test_truncation_is_by_character_count_and_not_by_word(self):
        # Forty a's, a space, forty-four b's: the 72-character cut lands
        # mid-word. A word-boundary cut would drop the b-word whole and
        # return the a-word plus an ellipsis; a character-count cut keeps
        # thirty b's and ends inside the word. The exact string is
        # asserted so the cut point cannot drift, and the character
        # before the ellipsis is checked not to be a space — a
        # word-boundary cut always ends on a whole word.
        rationale = "a" * 40 + " " + "b" * 44
        rendered = cli._inline_rationale(rationale, width=72)
        self.assertEqual(rendered, "a" * 40 + " " + "b" * 30 + "…")
        self.assertNotEqual(rendered[-2], " ")

    def test_a_multi_line_rationale_is_collapsed_to_one_line(self):
        rendered = cli._inline_rationale("one\ntwo\n\t\tthree", width=200)
        self.assertEqual(rendered, "one two three")

    def test_a_rationale_that_fits_is_not_truncated(self):
        self.assertEqual(
            cli._inline_rationale("short enough", width=72), "short enough"
        )


class RenderedReportTests(unittest.TestCase):
    """Through _print_report, with the real model-evidence pack looked up
    by the report's pack name."""

    def test_a_missing_verdict_prints_its_rationale_truncated_to_one_line(self):
        text = _render(_report(_verdict("ME-01", MISSING)))
        self.assertIn("  MISS  ME-01", text)
        self.assertIn(
            f"          why: {_truncate_by_character_count(_rationale_of('ME-01'))}",
            text,
        )
        why_lines = [
            line for line in text.splitlines() if line.lstrip().startswith("why: ")
        ]
        self.assertEqual(len(why_lines), 1)

    def test_an_unverifiable_verdict_prints_its_rationale_too(self):
        text = _render(_report(_verdict("ME-02", UNVERIFIABLE)))
        self.assertIn("why: ", text)

    def test_a_satisfied_verdict_prints_no_rationale(self):
        verdict = _verdict(
            "ME-01",
            SATISFIED,
            evidence=(Evidence(kind="file", locator="README.md", digest="x"),),
        )
        text = _render(_report(verdict))
        self.assertNotIn("why:", text)


class CheckCommandTests(unittest.TestCase):
    """Through main, against a fixture subject: the surface a reviewer
    actually reads."""

    def test_the_default_output_shows_the_rationale_when_a_blocking_claim_fails(
        self,
    ):
        with TempSubject(UNDOCUMENTED) as subject:
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = cli.main(
                    ["check", str(subject.root), "--pack", "model-evidence"]
                )
        text = out.getvalue()

        # ME-01 is blocking, and UNDOCUMENTED's README never says "purpose".
        self.assertEqual(exit_code, 1)
        self.assertIn("  MISS  ME-01", text)
        self.assertIn(
            "why: " + _truncate_by_character_count(_rationale_of("ME-01")), text
        )
        for line in text.splitlines():
            if line.lstrip().startswith("why: "):
                # One line, at the fixed indent, never longer than the width.
                self.assertLessEqual(len(line), 15 + _WIDTH)


if __name__ == "__main__":
    unittest.main()
