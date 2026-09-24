"""Golden report fixtures (I2).

A committed JSON report for a committed fixture tree, asserted byte for
byte. Schema drift — a renamed key, a reordered field, a reason string
reworded — shows up here as one line of diff before it reaches anyone
who parses the report.

When this fails because the change was intended, regenerate with
``make golden`` and commit the diff. Do not delete or loosen the
assertion: it is the only test that sees the report the way a
downstream consumer does.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from dossier import engine, packs
from dossier.subject import Subject

GOLDEN = Path(__file__).resolve().parent / "golden"
SUBJECT = GOLDEN / "subject"
SUBJECT_NAME = "golden-subject"

_REGENERATE = (
    "\n\nThe {pack} report for tests/golden/subject no longer matches "
    "tests/golden/{pack}.json byte for byte.\n"
    "If the change is intended, regenerate deliberately with `make golden`, "
    "read the diff, and commit it with the change that caused it.\n"
    "Do not delete or loosen this assertion."
)


def render(pack_name: str) -> str:
    """The report exactly as ``dossier check --json`` prints it."""
    pack = packs.get(pack_name)
    report = engine.check(Subject.at(SUBJECT, name=SUBJECT_NAME), pack)
    return report.to_json() + "\n"


class GoldenReports(unittest.TestCase):
    def test_every_pack_has_a_golden_report(self):
        for name in packs.names():
            with self.subTest(pack=name):
                self.assertTrue(
                    (GOLDEN / f"{name}.json").is_file(),
                    f"no golden report for {name}; run `make golden` and commit it",
                )

    def test_reports_match_their_golden_files_byte_for_byte(self):
        for name in packs.names():
            path = GOLDEN / f"{name}.json"
            if not path.is_file():
                continue  # reported by the test above
            with self.subTest(pack=name):
                self.maxDiff = None
                self.assertEqual(
                    render(name),
                    path.read_text(encoding="utf-8"),
                    _REGENERATE.format(pack=name),
                )

    def test_the_golden_subject_carries_more_than_one_status(self):
        """A golden tree where everything passes would not notice a
        change to how failures are written, which is most of the schema."""
        for name in packs.names():
            with self.subTest(pack=name):
                statuses = {
                    v["status"]
                    for v in __import__("json").loads(render(name))["verdicts"]
                }
                self.assertGreater(len(statuses), 1, statuses)


if __name__ == "__main__":
    unittest.main()
