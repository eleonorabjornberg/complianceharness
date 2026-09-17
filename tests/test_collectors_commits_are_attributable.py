"""Behaviour of the commits_are_attributable collector.

The fixtures are real repositories built by GitTempSubject's siblings, so
what is under test is what git actually answers. The shas the collector
reports are checked against git's own answer rather than against the
collector's internals, because a collector that agrees with itself proves
nothing.
"""

from __future__ import annotations

import re
import subprocess
import unittest

from dossier import registry
from dossier.collectors.commits_are_attributable import commits_are_attributable
from dossier.model import MISSING, SATISFIED, UNVERIFIABLE
from fixtures import (
    AttributionTempSubject,
    GitTempSubject,
    NoAuthorTempSubject,
    TempSubject,
    WELL_DOCUMENTED,
)

SHA = re.compile(r"^[0-9a-f]{40}$")

# The agent-author pattern a claim would pass: it matches the author
# ident "Agent Bot <agent@example.com>" and nothing else in the fixtures.
AGENT_PATTERN = r"agent@example\.com$"

AGENT_AUTHOR = {"author_name": "Agent Bot", "author_email": "agent@example.com"}
HUMAN_AUTHOR = {"author_name": "Fixture Author", "author_email": "fixture@example.com"}

TRAILER = "Co-Authored-By: The Agent <agent@example.com>"


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


class AttributionTests(unittest.TestCase):
    def test_agent_commits_with_a_producer_trailer_report_satisfied(self):
        """Done when: a fixture whose agent-authored commits all carry a
        trailer naming what produced them reports SATISFIED, citing the
        commits it checked."""
        commits = [
            {"message": f"change {index}\n\n{TRAILER}\n", **AGENT_AUTHOR}
            for index in (1, 2)
        ]
        with AttributionTempSubject(commits) as subject:
            expected = _git_shas(subject.root)
            status, reason, evidence = commits_are_attributable(
                subject, agent_pattern=AGENT_PATTERN
            )

        self.assertEqual(status, SATISFIED)
        self.assertEqual(
            [item.locator for item in evidence], sorted(expected, reverse=True)
        )
        for item in evidence:
            self.assertEqual(item.kind, "commit")

    def test_agent_commits_without_trailers_report_missing_and_name_the_shas(self):
        """Done when: the same history without trailers reports MISSING,
        and the evidence names each offending sha — not a count."""
        commits = [
            {"message": f"change {index}\n", **AGENT_AUTHOR} for index in (1, 2)
        ]
        with AttributionTempSubject(commits) as subject:
            expected = _git_shas(subject.root)
            status, reason, evidence = commits_are_attributable(
                subject, agent_pattern=AGENT_PATTERN
            )

        self.assertEqual(status, MISSING)
        # Every offending commit is named, by its sha: a reviewer can go
        # and look at each one.
        self.assertEqual(
            sorted(item.locator for item in evidence), sorted(expected)
        )
        for item in evidence:
            self.assertEqual(item.kind, "commit")
            self.assertRegex(item.locator, SHA)

    def test_an_empty_trailer_value_is_not_a_producer_trailer(self):
        """The C3 mutation witness: `Co-Authored-By:` with nothing after it
        names nothing, so the commit counts as unattributed."""
        commits = [{"message": f"change 1\n\n{TRAILER}:\n", **AGENT_AUTHOR}]
        with AttributionTempSubject(commits) as subject:
            expected = _git_shas(subject.root)
            status, reason, evidence = commits_are_attributable(
                subject, agent_pattern=AGENT_PATTERN
            )

        self.assertEqual(status, MISSING)
        self.assertEqual(
            sorted(item.locator for item in evidence), sorted(expected)
        )

    def test_an_empty_commit_message_is_reported(self):
        """Every commit must say something: an empty message means the
        commit is MISSING from the register's answer, with its sha named."""
        commits = [{"message": "", **HUMAN_AUTHOR}]
        with AttributionTempSubject(commits) as subject:
            expected = _git_shas(subject.root)
            status, reason, evidence = commits_are_attributable(subject)

        self.assertEqual(status, MISSING)
        self.assertEqual(
            sorted(item.locator for item in evidence), sorted(expected)
        )

    def test_a_commit_with_no_author_is_reported(self):
        """A commit nothing stands behind. Built by fast-import because
        git commit refuses an empty author ident."""
        with NoAuthorTempSubject() as subject:
            expected = _git_shas(subject.root)
            status, reason, evidence = commits_are_attributable(subject)

        self.assertEqual(status, MISSING)
        self.assertEqual(
            [item.locator for item in evidence], expected
        )

    def test_only_pattern_matching_commits_are_required_to_carry_a_trailer(self):
        """The pattern scopes the trailer check: a human commit without a
        trailer is not a finding, an agent commit without one is."""
        commits = [
            {"message": "agent change\n", **AGENT_AUTHOR},
            {"message": "human change\n", **HUMAN_AUTHOR},
        ]
        with AttributionTempSubject(commits) as subject:
            agent_sha = subprocess.run(
                ["git", "log", "--format=%H", "--author=agent@example.com", "HEAD"],
                cwd=subject.root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            status, reason, evidence = commits_are_attributable(
                subject, agent_pattern=AGENT_PATTERN
            )

        self.assertEqual(status, MISSING)
        self.assertEqual([item.locator for item in evidence], [agent_sha])

    def test_without_an_agent_pattern_a_trailer_is_not_required(self):
        """Absent: no pattern given, so the trailer check is not armed —
        authors and messages are still checked."""
        commits = [{"message": f"change {index}\n", **AGENT_AUTHOR} for index in (1, 2)]
        with AttributionTempSubject(commits) as subject:
            status, reason, evidence = commits_are_attributable(subject)

        self.assertEqual(status, SATISFIED)

    def test_two_runs_against_the_same_state_agree(self):
        """Registry contract: two calls against the same subject state
        return the same triple."""
        with AttributionTempSubject(
            [{"message": "change 1\n", **AGENT_AUTHOR}]
        ) as subject:
            first = commits_are_attributable(subject, agent_pattern=AGENT_PATTERN)
            second = commits_are_attributable(subject, agent_pattern=AGENT_PATTERN)
        self.assertEqual(first, second)

    def test_no_git_directory_reports_unverifiable(self):
        """The Absent case, C1's way: a subject that is not a repository.
        UNVERIFIABLE naming what was missing, and never a raise."""
        with TempSubject(WELL_DOCUMENTED) as subject:
            status, reason, evidence = commits_are_attributable(subject)

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".git", reason)
        self.assertEqual(evidence, ())

    def test_a_repository_with_no_commits_reports_missing(self):
        """No history at all is knowledge, not ignorance: the subject
        verifiably has nothing to attribute."""
        with GitTempSubject([]) as subject:
            status, reason, evidence = commits_are_attributable(subject)

        self.assertEqual(status, MISSING)
        self.assertEqual(evidence, ())
        self.assertIn("no commits", reason)

    def test_an_agent_pattern_that_is_not_a_regex_reports_unverifiable(self):
        """A pattern the collector cannot compile is a claim-params
        problem: UNVERIFIABLE, not a crash dressed as an answer."""
        with AttributionTempSubject([{"message": "change 1\n", **AGENT_AUTHOR}]) as subject:
            status, reason, evidence = commits_are_attributable(
                subject, agent_pattern="("
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertEqual(evidence, ())

    def test_it_is_registered_under_its_backlog_name(self):
        """Packs select collectors by this name; the registry is the seam."""
        self.assertIs(registry.get("commits_are_attributable"), commits_are_attributable)


if __name__ == "__main__":
    unittest.main()
