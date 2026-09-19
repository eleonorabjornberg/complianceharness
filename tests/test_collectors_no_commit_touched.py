"""Behaviour of the no_commit_touched collector.

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
from dossier.collectors.no_commit_touched import no_commit_touched
from dossier.model import MISSING, SATISFIED, UNVERIFIABLE
from fixtures import (
    CLEAN_HISTORY,
    GitTempSubject,
    REVERTED_VIOLATION,
    TempSubject,
    VIOLATED_HISTORY,
    WELL_DOCUMENTED,
)

SHA = re.compile(r"[0-9a-f]{40}")

PROTECTED = ["src/dossier/model.py", "src/dossier/engine.py"]


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


class NoCommitTouchedTests(unittest.TestCase):
    def test_a_commit_touching_a_protected_path_reports_missing(self):
        """The Done-when: one commit edited a protected path, and the
        verdict names that commit's sha and the path as evidence."""
        with GitTempSubject(VIOLATED_HISTORY) as subject:
            head = _git_shas(subject.root, "HEAD")[0]
            status, reason, evidence = no_commit_touched(subject, protected=PROTECTED)

        self.assertEqual(status, MISSING)
        self.assertEqual([item.locator for item in evidence], ["src/dossier/model.py"])
        self.assertRegex(evidence[0].note, SHA)
        # The reason names the offending sha and path, not a count.
        self.assertIn(head, reason)
        self.assertIn("src/dossier/model.py", reason)

    def test_a_history_that_never_touched_a_protected_path_reports_satisfied(self):
        """The other Done-when: the walk is clean, and the pass is tied to
        the tree that was walked."""
        with GitTempSubject(CLEAN_HISTORY) as subject:
            head = _git_shas(subject.root, "HEAD")[0]
            status, reason, evidence = no_commit_touched(subject, protected=PROTECTED)

        self.assertEqual(status, SATISFIED)
        self.assertEqual([item.locator for item in evidence], [head])
        self.assertIn("no commit", reason)

    def test_a_violation_later_reverted_is_still_reported(self):
        """The protected path was modified and the change was then
        reverted, so the tree at HEAD is clean. Only a walk over every
        commit sees the commit that did it; a collector that reads HEAD's
        tree alone reports a pass the history does not support."""
        with GitTempSubject(REVERTED_VIOLATION) as subject:
            shas = _git_shas(subject.root, "HEAD")
            status, reason, evidence = no_commit_touched(subject, protected=PROTECTED)

        self.assertEqual(status, MISSING)
        self.assertEqual(
            [item.locator for item in evidence], ["src/dossier/model.py"] * 2
        )
        # Both commits that touched the path are evidence — the edit and
        # the revert that hid it — and neither is HEAD.
        named = sorted(re.findall(SHA, " ".join(item.note for item in evidence)))
        self.assertEqual(named, sorted(shas[:2]))

    def test_the_globs_come_from_the_claim_parameters_not_a_constant(self):
        """The same subject, two different parameter sets, two different
        verdicts: a collector with a constant glob inside it cannot
        produce both."""
        with GitTempSubject(VIOLATED_HISTORY) as subject:
            untouched = no_commit_touched(subject, protected=["docs/judge.md"])
            touched = no_commit_touched(subject, protected=["src/*.py"])

        self.assertEqual(untouched[0], SATISFIED)
        self.assertEqual(touched[0], MISSING)
        # fnmatch semantics: one star crosses directory separators, so
        # src/*.py reaches src/dossier/model.py.
        self.assertIn("src/dossier/model.py", touched[1])

    def test_two_runs_against_the_same_state_agree(self):
        """Registry contract: two calls against the same subject state
        return the same triple."""
        with GitTempSubject(VIOLATED_HISTORY) as subject:
            first = no_commit_touched(subject, protected=PROTECTED)
            second = no_commit_touched(subject, protected=PROTECTED)
        self.assertEqual(first, second)

    def test_a_subject_with_no_git_reports_unverifiable(self):
        """The Absent case: a subject that is not a repository. There is
        no history to check, and the register says so rather than
        guessing — UNVERIFIABLE, naming what was missing, never a raise."""
        with TempSubject(WELL_DOCUMENTED) as subject:
            status, reason, evidence = no_commit_touched(subject, protected=PROTECTED)

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".git", reason)
        self.assertEqual(evidence, ())

    def test_a_missing_git_binary_reports_unverifiable(self):
        """The other Absent case: no git on the machine. The reason must
        distinguish this from no .git in the subject."""
        with GitTempSubject(VIOLATED_HISTORY) as subject:
            with mock.patch(
                "dossier.collectors.no_commit_touched.subprocess.run",
                side_effect=FileNotFoundError("no git"),
            ):
                status, reason, evidence = no_commit_touched(
                    subject, protected=PROTECTED
                )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn("git", reason)
        self.assertEqual(evidence, ())

    def test_a_repository_with_no_commits_reports_missing(self):
        """An empty repository is knowledge, not ignorance: the subject
        verifiably has no history, which is MISSING, not UNVERIFIABLE —
        the same ladder git_history climbs."""
        with GitTempSubject([]) as subject:
            status, reason, evidence = no_commit_touched(subject, protected=PROTECTED)

        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("no commits", reason)

    def test_a_claim_that_protects_no_paths_reports_unverifiable(self):
        """An empty glob list protects nothing, and a vacuous pass would
        answer the claim without looking at it. The register says it
        cannot determine this instead."""
        with GitTempSubject(CLEAN_HISTORY) as subject:
            status, reason, evidence = no_commit_touched(subject, protected=[])

        self.assertEqual(status, UNVERIFIABLE)
        self.assertEqual(evidence, ())
        self.assertIn("protects no paths", reason)

    def test_it_is_registered_under_its_backlog_name(self):
        """Packs select collectors by this name; the registry is the seam."""
        self.assertIs(registry.get("no_commit_touched"), no_commit_touched)


if __name__ == "__main__":
    unittest.main()
