"""Behaviour of ``dossier explain <claim-id>`` (R5).

Done when an unknown id exits 2 with a message naming the packs
searched, and a known id in two packs prints both. Today every claim id
is unique across packs (a human-only guard enforces it), so the two-pack
case is built by registering a second pack for the length of one test —
the case P1b will make real, when ``annex-iv`` and ``model-risk`` select
the same claims from one catalogue.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from unittest import mock

from dossier import cli, packs


def _run(*argv: str):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Explain(unittest.TestCase):
    def test_a_known_id_prints_text_rationale_severity_and_source(self):
        pack = packs.get("model-evidence")
        claim = next(c for c in pack.claims if c.id == "ME-02")

        code, out, err = _run("explain", "ME-02")

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn(claim.text, out)
        self.assertIn(" ".join(claim.rationale.split()), out)
        self.assertIn(claim.severity, out)
        self.assertIn(pack.source, out)
        self.assertIn("model-evidence", out)

    def test_an_unknown_id_exits_2_naming_every_pack_searched(self):
        code, out, err = _run("explain", "ZZ-99")

        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ZZ-99", err)
        for name in packs.names():
            self.assertIn(name, err)

    def test_ids_are_matched_exactly_not_case_insensitively(self):
        code, _, _ = _run("explain", "me-02")
        self.assertEqual(code, 2)

    def test_a_known_id_in_two_packs_prints_both(self):
        original = packs.get("model-evidence")
        twin = replace(original, name="twin-pack", source="a second source")
        registry = {**packs._PACKS, twin.name: twin}

        with mock.patch.dict(packs._PACKS, registry, clear=True):
            code, out, _ = _run("explain", "ME-02")

        self.assertEqual(code, 0)
        self.assertIn("model-evidence", out)
        self.assertIn("twin-pack", out)
        self.assertIn("a second source", out)
        self.assertEqual(out.count("ME-02  ·  "), 2)

    def test_explain_runs_nothing_against_a_subject(self):
        """No path argument exists to give it — the parser refuses one."""
        with self.assertRaises(SystemExit) as raised:
            _run("explain", "ME-02", ".")
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
