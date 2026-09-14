"""The determinism rule, asserted instead of reviewed.

CONTRACT.md forbids a clock, a machine, the environment and the network
anywhere under ``src/``. Review catches that unevenly, and will catch it
less often the more of this code is written by agents, so it is checked
here instead. The check reads the source rather than the behaviour: a
collector that imports ``datetime`` is a finding whether or not the
current call path reaches it.

Deliberately not forbidden: ``subprocess``. Asking git what it knows is
how several planned collectors work, and what git answers is a property
of the subject, not of the machine.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent / "src" / "dossier"

FORBIDDEN_IMPORTS = {
    "datetime": "reads the clock",
    "time": "reads the clock",
    "calendar": "reads the clock",
    "random": "does not repeat",
    "secrets": "does not repeat",
    "uuid": "does not repeat",
    "socket": "is the network",
    "http": "is the network",
    "urllib": "is the network",
    "requests": "is the network",
    "platform": "is the machine, and a report may not depend on the machine",
    "getpass": "is the environment",
}

FORBIDDEN_ATTRIBUTES = {
    "os.environ": "is the environment",
    "os.getenv": "is the environment",
    "os.putenv": "is the environment",
}


def _modules():
    """Every module under src/dossier, sorted for a stable failure order."""
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        name = path.relative_to(SOURCE_ROOT.parent).as_posix()
        yield name, ast.parse(path.read_text(encoding="utf-8"))


def _imported_roots(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module.split(".")[0]


def _attribute_accesses(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            yield f"{node.value.id}.{node.attr}"


class PurityTests(unittest.TestCase):
    def test_the_source_tree_was_actually_found(self):
        """A purity test that inspects nothing passes for the wrong reason."""
        found = [name for name, _ in _modules()]
        self.assertIn("dossier/engine.py", found)
        self.assertIn("dossier/model.py", found)
        self.assertGreaterEqual(len(found), 8, found)

    def test_nothing_under_src_imports_a_source_of_irreproducibility(self):
        for name, tree in _modules():
            for root in _imported_roots(tree):
                reason = FORBIDDEN_IMPORTS.get(root)
                if reason is not None:
                    self.fail(f"{name} imports {root}, which {reason}")

    def test_nothing_under_src_reads_the_environment(self):
        for name, tree in _modules():
            for access in _attribute_accesses(tree):
                reason = FORBIDDEN_ATTRIBUTES.get(access)
                if reason is not None:
                    self.fail(f"{name} uses {access}, which {reason}")

    def test_every_collector_module_is_imported_by_its_package(self):
        """An unregistered collector makes every claim using it UNVERIFIABLE.

        That failure is silent — a clean-looking report with a whole
        category of claim quietly unanswered — so it is asserted rather
        than left to whoever notices.
        """
        package = SOURCE_ROOT / "collectors"
        modules = {
            path.stem
            for path in package.glob("*.py")
            if path.stem != "__init__"
        }
        tree = ast.parse((package / "__init__.py").read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 1
            for alias in node.names
        }
        self.assertTrue(modules, "no collector modules found")
        self.assertEqual(
            modules - imported,
            set(),
            "collector modules not imported in collectors/__init__.py",
        )


if __name__ == "__main__":
    unittest.main()
