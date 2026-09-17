"""I4: the tool does not crash on code it has never seen.

CI runs both packs against one foreign repository, pinned by sha. The
only thing asserted is the exit code: 0 and 1 are both reports (nothing
blocking, or blocking claims missing -- either way the tool did its
job), while 2 means the run could not be performed at all. A crash on a
subject the tool has never seen is the exact failure this item exists
to catch, so the guard refuses to pass one through, and these tests
hold the guard to that.

The foreign subject itself is a CI concern -- a network checkout of a
pinned sha, never a test fixture. These tests build their subject in a
temp directory and run the real tool against it, so the guard is
exercised end to end without leaving the machine.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The guard lives in tools/, which is not a package and is not on the
# test path. Import it by path so CI and a fresh clone both find it.
sys.path.insert(0, str(REPO_ROOT / "tools"))

import foreign_subject  # noqa: E402


class EvaluateTests(unittest.TestCase):
    """The one rule the item exists for: a report passes, a crash does not."""

    def test_a_clean_report_passes_the_guard(self):
        self.assertTrue(foreign_subject.all_packs_reported([0]))

    def test_unsupported_claims_are_a_report_not_a_crash(self):
        # Exit 1 is "blocking claims missing" -- the tool working as
        # designed against a subject that is not its own repository.
        self.assertTrue(foreign_subject.all_packs_reported([1]))

    def test_an_unknown_exit_code_is_never_passed_through(self):
        # Absent guard: a pass-through of any nonzero code would call a
        # crash green. Nothing but 0 and 1 may pass.
        self.assertFalse(foreign_subject.all_packs_reported([2]))

    def test_one_crash_among_reports_fails_the_whole_run(self):
        self.assertFalse(foreign_subject.all_packs_reported([0, 1, 2]))

    def test_an_empty_run_is_not_a_pass(self):
        # A guard that ran nothing and reported success would be the
        # quietest possible crash.
        self.assertFalse(foreign_subject.all_packs_reported([]))


class RunBothPacksTests(unittest.TestCase):
    """The guard runs every pack, and runs them through the real tool."""

    def test_the_guard_runs_every_pack_in_the_pack_index(self):
        packs = []
        real_run_pack = foreign_subject.run_pack

        def recording_run_pack(subject: Path, pack: str) -> subprocess.CompletedProcess:
            packs.append(pack)
            return real_run_pack(subject, pack)

        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / "subject"
            subject.mkdir()
            (subject / "README.md").write_text("a subject for the guard\n", encoding="utf-8")
            code = foreign_subject.main([str(subject)], run_pack=recording_run_pack)
        self.assertEqual(code, 0)
        self.assertEqual(packs, ["model-evidence", "agent-control"])

    def test_a_subject_that_cannot_be_read_fails_the_guard(self):
        # The tool's own exit code for "could not be performed at all" is
        # 2; the guard must turn that into a CI failure, not a shrug.
        with tempfile.TemporaryDirectory() as tmp:
            code = foreign_subject.main([str(Path(tmp) / "does-not-exist")])
        self.assertNotEqual(code, 0)

    def test_usage_error_is_a_failure(self):
        self.assertNotEqual(foreign_subject.main([]), 0)


if __name__ == "__main__":
    unittest.main()
