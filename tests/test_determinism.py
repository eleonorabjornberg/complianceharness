"""Reports are reproducible or they are not evidence.

This is the project's central promise and therefore its most defended
property. Three ways it can break, one test each:

  1. the report carries something that differs between runs or machines
     (a timestamp, an absolute path, a temp directory name)
  2. the report carries something whose order is not fixed
  3. a collector reads the clock or the environment

If you are about to add a field to Report, Verdict or Evidence, this
file is the one that decides whether you may.
"""

from __future__ import annotations

import json
import re
import unittest

from dossier import engine, packs
from fixtures import TempSubject, UNDOCUMENTED, WELL_DOCUMENTED


class DeterminismTests(unittest.TestCase):
    def test_the_same_subject_state_produces_the_same_digest(self):
        first = _digest_of(WELL_DOCUMENTED, "model-evidence")
        second = _digest_of(WELL_DOCUMENTED, "model-evidence")
        self.assertEqual(first, second)

    def test_a_different_subject_state_produces_a_different_digest(self):
        self.assertNotEqual(
            _digest_of(WELL_DOCUMENTED, "model-evidence"),
            _digest_of(UNDOCUMENTED, "model-evidence"),
        )

    def test_the_digest_does_not_depend_on_where_the_subject_lives(self):
        """Two copies of identical content in different temp directories must
        agree. This is the test that catches an absolute path leaking into a
        locator, which is the most likely way to break reproducibility."""
        self.assertEqual(
            _digest_of(WELL_DOCUMENTED, "model-evidence"),
            _digest_of(WELL_DOCUMENTED, "model-evidence"),
        )

    def test_no_absolute_path_appears_anywhere_in_a_report(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, packs.get("model-evidence"))
        text = report.to_json()
        self.assertNotIn(str(subject.root), text)
        self.assertNotIn("/tmp", text)
        self.assertNotIn("/var/folders", text)

    def test_no_date_or_timestamp_appears_anywhere_in_a_report(self):
        """A report dated later than the state it describes is the project's
        own thesis failing in its own output. When is a digest, not a clock."""
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, packs.get("model-evidence"))
        text = report.to_json()
        for pattern in (r"\d{4}-\d{2}-\d{2}", r"\d{2}:\d{2}:\d{2}"):
            self.assertIsNone(
                re.search(pattern, text),
                f"report contains something matching {pattern}: reports carry no clock",
            )

    def test_report_json_is_key_sorted(self):
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, packs.get("model-evidence"))
        parsed = json.loads(report.to_json())
        self.assertEqual(list(parsed), sorted(parsed))

    def test_verdicts_follow_pack_order_not_dictionary_order(self):
        pack = packs.get("model-evidence")
        with TempSubject(WELL_DOCUMENTED) as subject:
            report = engine.check(subject, pack)
        self.assertEqual(
            [v.claim_id for v in report.verdicts],
            [c.id for c in pack.claims],
        )


def _digest_of(files: dict[str, str], pack_name: str) -> str:
    with TempSubject(files) as subject:
        return engine.check(subject, packs.get(pack_name)).digest()


if __name__ == "__main__":
    unittest.main()
