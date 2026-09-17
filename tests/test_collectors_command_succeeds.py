"""Behaviour of the command_succeeds collector.

This is the first collector whose evidence is a behaviour rather than a
document: a command the subject itself declares runs, inside the subject,
and exits zero. Because running code is the strongest thing a collector
does, its tests hold the opt-in to both halves the decision requires —
the subject's declaration in .dossier.json and the operator's
--allow-commands — and hold the report to what stays deterministic about
a run: the declared name, the exit status, a digest of the output. Never
the output text, never a duration.

The no-flag test below is written first on purpose: it is the test the
mutation must fail, and a mutation caught by nothing is a suite with no
power over the change.
"""

from __future__ import annotations

import unittest

from dossier import engine, registry
from dossier.cli import authorise_declared_commands
from dossier.collectors.command_succeeds import command_succeeds
from dossier.model import (
    ADVISORY,
    Claim,
    MATERIAL,
    MISSING,
    Pack,
    SATISFIED,
    UNVERIFIABLE,
)
from fixtures import (
    DECLARED_FAILING_COMMAND,
    DECLARED_PASSING_COMMAND,
    DECLARED_SLOW_COMMAND,
    MALFORMED_COMMAND_DECLARATION,
    TempSubject,
    UNDECLARED_COMMAND_NAME,
    UNDECLARED_COMMANDS,
)

_NOT_AUTHORISED = "command execution not authorised"


def _pack_with_command_claim() -> Pack:
    """A pack with one command claim and one claim that is none."""
    return Pack(
        name="commands",
        version="0.0.0",
        source="test source",
        claims=(
            Claim(
                id="CMD-01",
                text="The declared command runs.",
                severity=ADVISORY,
                collector="command_succeeds",
                rationale="A stated command that regenerates the evidence is the check on it.",
                params={"name": "suite"},
            ),
            Claim(
                id="DOC-01",
                text="A document exists.",
                severity=MATERIAL,
                collector="document_present",
                rationale="A reviewer looks for the document first.",
                params={"candidates": ["README.md"]},
            ),
        ),
    )


class CommandSucceedsTests(unittest.TestCase):
    # --- the operator's half of the opt-in (the mutation's catcher) ------

    def test_without_the_flag_a_declared_command_is_not_run(self):
        """A subject declaring a command is not permission to run it. The
        reason is fixed so a report cannot smuggle the run past a reader:
        either the operator authorised commands or they did not."""
        with TempSubject(DECLARED_PASSING_COMMAND) as subject:
            status, reason, evidence = command_succeeds(subject, name="suite")

        self.assertEqual(status, UNVERIFIABLE)
        self.assertEqual(reason, _NOT_AUTHORISED)
        self.assertEqual(evidence, ())

    # --- Done when --------------------------------------------------------

    def test_a_declared_passing_command_reports_satisfied(self):
        with TempSubject(DECLARED_PASSING_COMMAND) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True
            )

        self.assertEqual(status, SATISFIED)
        self.assertIn("suite", reason)
        self.assertIn("exited 0", reason)
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.kind, "command")
        self.assertEqual(item.locator, "suite")
        self.assertIn("exit status 0", item.note)
        # A digest of stdout+stderr, never the text itself.
        self.assertRegex(item.digest, r"^[0-9a-f]{64}$")

    def test_a_declared_failing_command_reports_missing_with_exit_status(self):
        with TempSubject(DECLARED_FAILING_COMMAND) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True
            )

        self.assertEqual(status, MISSING)
        self.assertIn("suite", reason)
        self.assertIn("exited 1", reason)
        self.assertEqual(len(evidence), 1)
        self.assertIn("exit status 1", evidence[0].note)

    def test_a_command_exceeding_the_timeout_reports_unverifiable(self):
        """A timeout is not knowledge that the command fails: the collector
        waited and is none the wiser. UNVERIFIABLE, never MISSING."""
        with TempSubject(DECLARED_SLOW_COMMAND) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True, timeout_seconds=0.2
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertNotEqual(status, MISSING)
        self.assertIn("suite", reason)
        self.assertEqual(evidence, ())

    # --- Absent -----------------------------------------------------------

    def test_no_declaration_names_the_missing_file(self):
        with TempSubject(UNDECLARED_COMMANDS) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".dossier.json", reason)
        self.assertEqual(evidence, ())

    def test_an_undeclared_name_names_which(self):
        with TempSubject(UNDECLARED_COMMAND_NAME) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn("suite", reason)
        self.assertEqual(evidence, ())

    def test_a_malformed_declaration_reports_unverifiable(self):
        with TempSubject(MALFORMED_COMMAND_DECLARATION) as subject:
            status, reason, evidence = command_succeeds(
                subject, name="suite", allow_commands=True
            )

        self.assertEqual(status, UNVERIFIABLE)
        self.assertIn(".dossier.json", reason)
        self.assertEqual(evidence, ())

    # --- registry contract -------------------------------------------------

    def test_two_runs_against_the_same_state_agree(self):
        with TempSubject(DECLARED_PASSING_COMMAND) as subject:
            first = command_succeeds(subject, name="suite", allow_commands=True)
            second = command_succeeds(subject, name="suite", allow_commands=True)

        self.assertEqual(first, second)

    def test_it_is_registered_under_its_backlog_name(self):
        """Packs select collectors by this name; the registry is the seam."""
        self.assertIs(registry.get("command_succeeds"), command_succeeds)

    # --- the CLI's half: --allow-commands reaches the collector ------------

    def test_the_flag_reaches_only_command_succeeds_claims(self):
        pack = _pack_with_command_claim()
        authorised = authorise_declared_commands(pack)

        command_claim = authorised.claims[0]
        document_claim = authorised.claims[1]
        self.assertEqual(command_claim.params, {"name": "suite", "allow_commands": True})
        self.assertEqual(
            document_claim.params, {"candidates": ["README.md"]}
        )
        self.assertEqual(command_claim.id, "CMD-01")
        self.assertEqual(authorised.name, pack.name)

    def test_the_pack_itself_is_left_unmodified(self):
        """Authorisation is the operator's view of the pack, not a rewrite
        of it: the catalogue a report names must not carry the flag."""
        pack = _pack_with_command_claim()
        authorise_declared_commands(pack)

        self.assertEqual(pack.claims[0].params, {"name": "suite"})

    def test_the_engine_honours_the_operator_flag_end_to_end(self):
        pack = _pack_with_command_claim()
        with TempSubject(DECLARED_PASSING_COMMAND) as subject:
            without_flag = engine.check(subject, pack)
            with_flag = engine.check(subject, authorise_declared_commands(pack))

        self.assertEqual(without_flag.verdicts[0].status, UNVERIFIABLE)
        self.assertEqual(without_flag.verdicts[0].reason, _NOT_AUTHORISED)
        self.assertEqual(with_flag.verdicts[0].status, SATISFIED)


if __name__ == "__main__":
    unittest.main()
