"""Behaviour of the documented_within collector.

This is the collector that makes STALE a status something can produce:
a document that exists and says the right words can still describe a
system the code has moved past. The fixtures are real repositories built
by GitTempSubject, so the distances under test are what git actually
answers, and the shas and distances the collector reports are checked
against git's own answer rather than against the collector's internals.
"""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from dossier import registry
from dossier.collectors.documented_within import documented_within
from dossier.model import MISSING, SATISFIED, STALE, UNVERIFIABLE
from fixtures import (
    DOCUMENT_ABSENT,
    DOCUMENTED_CURRENT,
    DOCUMENTED_LAGGING,
    GitTempSubject,
    TempSubject,
    WELL_DOCUMENTED,
)

CANDIDATES = ["docs/overview.md"]


def _last_touch_sha(root, path: str) -> str:
    """An independent read of the last commit that touched a path."""
    result = subprocess.run(
        ["git", "rev-list", "-n", "1", "HEAD", "--", path],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class DocumentedWithinTests(unittest.TestCase):
    def test_a_document_that_moved_with_the_code_reports_satisfied(self):
        """The Done-when pass: the document's last change is the commit at
        HEAD, 0 commits behind, inside the limit. The reported sha is
        git's own answer, not the collector's opinion."""
        with GitTempSubject(DOCUMENTED_CURRENT) as subject:
            expected = _last_touch_sha(subject.root, CANDIDATES[0])
            status, reason, evidence = documented_within(
                subject, CANDIDATES, within=1
            )

        self.assertEqual(status, SATISFIED)
        self.assertIn("0", reason)
        self.assertIn("1", reason)  # the limit is named too
        commit_evidence = [e for e in evidence if e.kind == "commit"]
        self.assertEqual([e.locator for e in commit_evidence], [expected])

    def test_a_document_left_behind_by_the_code_reports_stale(self):
        """The Done-when catch: two commits landed without the document,
        which is beyond a limit of one. The distance — not a boolean —
        is what the verdict rests on."""
        with GitTempSubject(DOCUMENTED_LAGGING) as subject:
            expected = _last_touch_sha(subject.root, CANDIDATES[0])
            status, reason, evidence = documented_within(
                subject, CANDIDATES, within=1
            )

        self.assertEqual(status, STALE)
        self.assertIn("2", reason)
        commit_evidence = [e for e in evidence if e.kind == "commit"]
        self.assertEqual([e.locator for e in commit_evidence], [expected])

    def test_the_limit_is_measured_in_commits(self):
        """The same lagging document inside a limit of two commits is
        SATISFIED: the comparison is a distance against a number of
        commits, so the boundary itself is pinned."""
        with GitTempSubject(DOCUMENTED_LAGGING) as subject:
            status, reason, _ = documented_within(
                subject, CANDIDATES, within=2
            )

        self.assertEqual(status, SATISFIED)
        self.assertIn("2", reason)

    def test_an_absent_document_reports_missing_not_unverifiable(self):
        """The Absent pair, second half: the history exists and verifiably
        never touched the document. That is knowledge — MISSING — not
        ignorance, and it must not collapse into the no-history answer."""
        with GitTempSubject(DOCUMENT_ABSENT) as subject:
            status, reason, evidence = documented_within(
                subject, ["docs/overview.md", "OVERVIEW.md"], within=1
            )

        self.assertEqual(status, MISSING)
        self.assertIn("docs/overview.md", reason)
        self.assertIn("OVERVIEW.md", reason)
        self.assertEqual(evidence, ())

    def test_a_document_no_commit_has_ever_touched_reports_missing(self):
        """A document in the working tree that no commit has ever carried
        has no commit evidence at all: MISSING, saying so — a different
        reason from a document that does not exist."""
        with GitTempSubject(DOCUMENT_ABSENT) as subject:
            (subject.root / "docs").mkdir()
            (subject.root / "docs" / "overview.md").write_text(
                "# untracked\n", encoding="utf-8"
            )
            status, reason, evidence = documented_within(
                subject, CANDIDATES, within=1
            )

        self.assertEqual(status, MISSING)
        self.assertIn("docs/overview.md", reason)
        self.assertIn("commit", reason)
        self.assertEqual(evidence, ())

    def test_a_repository_with_no_commits_reports_missing(self):
        """The C1 ladder, kept: a repository with no commits has no
        history, and the absence of a history is knowledge, not
        ignorance."""
        with GitTempSubject([]) as subject:
            (subject.root / "docs").mkdir()
            (subject.root / "docs" / "overview.md").write_text(
                "# untracked\n", encoding="utf-8"
            )
            status, reason, _ = documented_within(
                subject, CANDIDATES, within=1
            )

        self.assertEqual(status, MISSING)
        self.assertIn("no commits", reason)

    def test_no_git_directory_reports_unverifiable(self):
        """The Absent pair, first half: without a `.git` there is no
        history to measure freshness in, which is UNVERIFIABLE — the
        answer C1 gives, for the same reason."""
        with TempSubject(WELL_DOCUMENTED) as subject:
            status, reason, evidence = documented_within(
                subject, CANDIDATES, within=1
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".git", reason)
        self.assertEqual(evidence, ())

    def test_a_missing_git_binary_reports_unverifiable(self):
        """No git on the machine is the other unverifiable: the subject
        may have a history, but this machine cannot read it."""
        with GitTempSubject(DOCUMENTED_CURRENT) as subject:
            with mock.patch(
                "dossier.collectors.documented_within.subprocess.run",
                side_effect=FileNotFoundError("no git"),
            ):
                status, reason, evidence = documented_within(
                    subject, CANDIDATES, within=1
                )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn("git", reason)
        self.assertEqual(evidence, ())

    def test_two_runs_against_the_same_state_agree(self):
        """Registry contract: two calls against the same subject state
        return the same triple."""
        with GitTempSubject(DOCUMENTED_LAGGING) as subject:
            first = documented_within(subject, CANDIDATES, within=1)
            second = documented_within(subject, CANDIDATES, within=1)
        self.assertEqual(first, second)

    def test_it_is_registered_under_its_backlog_name(self):
        """Packs select collectors by this name; the registry is the seam."""
        self.assertIs(registry.get("documented_within"), documented_within)


if __name__ == "__main__":
    unittest.main()
