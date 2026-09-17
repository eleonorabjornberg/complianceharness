"""Behaviour of the git_history collector.

The fixtures are real repositories built by GitTempSubject, so what is
under test is what git actually answers. The shas the collector reports
are checked against git's own answer rather than against the collector's
internals, because a collector that agrees with itself proves nothing.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from unittest import mock

from dossier import registry
from dossier.collectors.git_history import git_history
from dossier.model import MISSING, SATISFIED, UNVERIFIABLE
from fixtures import GitTempSubject, TempSubject, WELL_DOCUMENTED

SHA = re.compile(r"^[0-9a-f]{40}$")

TWO_COMMITS = [{"README.md": "# one\n"}, {"DATA.md": "two\n"}]


def _git_shas(root, *args: str) -> list[str]:
    """An independent read of the fixture's history, straight from git."""
    result = subprocess.run(
        ["git", "rev-list", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


class GitHistoryTests(unittest.TestCase):
    def test_two_commits_report_satisfied_with_both_shas(self):
        with GitTempSubject(TWO_COMMITS) as subject:
            history = _git_shas(subject.root, "HEAD")
            status, reason, evidence = git_history(subject)

        self.assertEqual(status, SATISFIED)
        self.assertEqual(len(evidence), 2)
        for item in evidence:
            self.assertEqual(item.kind, "commit")
            self.assertRegex(item.locator, SHA)
        # First commit first, HEAD second: the order a reviewer reads.
        self.assertEqual(
            [item.locator for item in evidence], [history[-1], history[0]]
        )
        # The reason ties the verdict to the tree by naming both shas.
        self.assertIn(history[-1], reason)
        self.assertIn(history[0], reason)

    def test_two_runs_against_the_same_state_agree(self):
        """Registry contract: two calls against the same subject state
        return the same triple."""
        with GitTempSubject(TWO_COMMITS) as subject:
            first = git_history(subject)
            second = git_history(subject)
        self.assertEqual(first, second)

    def test_no_git_directory_reports_unverifiable(self):
        """The Absent case: a subject that is not a repository. UNVERIFIABLE
        naming what was missing, and never a raise."""
        with TempSubject(WELL_DOCUMENTED) as subject:
            status, reason, evidence = git_history(subject)

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".git", reason)
        self.assertEqual(evidence, ())

    def test_a_missing_git_binary_reports_unverifiable(self):
        """The other Absent case: no git on the machine. The reason must
        distinguish this from no .git in the subject."""
        with GitTempSubject(TWO_COMMITS) as subject:
            with mock.patch(
                "dossier.collectors.git_history.subprocess.run",
                side_effect=FileNotFoundError("no git"),
            ):
                status, reason, evidence = git_history(subject)

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn("git", reason)
        self.assertEqual(evidence, ())

    def test_a_repository_with_no_commits_reports_missing(self):
        """An empty repository is knowledge, not ignorance: the subject
        verifiably has no history, which is MISSING, not UNVERIFIABLE."""
        with GitTempSubject([]) as subject:
            status, reason, evidence = git_history(subject)

        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("no commits", reason)

    def test_it_is_registered_under_its_backlog_name(self):
        """Packs select collectors by this name; the registry is the seam."""
        self.assertIs(registry.get("git_history"), git_history)


if __name__ == "__main__":
    unittest.main()
