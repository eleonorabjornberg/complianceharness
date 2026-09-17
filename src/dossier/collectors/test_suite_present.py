"""Collector: that the subject actually has a test suite.

A directory named ``tests/`` and modules named ``test_*.py`` are
promises. This collector counts the thing itself: it parses every Python
module under the claim's test directory with ``ast`` and counts the
function definitions whose names begin with ``test`` — including
methods, because unittest suites live in classes. A module that only
mentions tests in prose contains zero of them, which is exactly the gap
between a grep and a parse.
"""

from __future__ import annotations

import ast

from ..model import MISSING, SATISFIED, Evidence
from ..registry import register
from ..subject import Subject


def _is_test_function(node: ast.AST) -> bool:
    return (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
    )


@register("test_suite_present")
def test_suite_present(
    subject: Subject, directory: str = "tests", minimum: int = 1
) -> tuple[str, str, tuple[Evidence, ...]]:
    """A test directory exists and holds at least `minimum` test functions.

    Counted by parsing each module under `directory` with ``ast``, never
    by matching the word test in source text: a file named
    test_things.py whose docstring plans tests it never wrote is not a
    suite. The absence of the directory is reported MISSING rather than
    UNVERIFIABLE — knowing a subject has no suite is knowledge about it,
    not a failure to look.
    """
    if not directory:
        raise ValueError("directory must name the claim's test directory")
    if minimum < 1:
        raise ValueError(
            "minimum must be at least 1 — a suite with no tests is not a suite"
        )

    directory = directory.rstrip("/")
    prefix = directory + "/"
    if not subject.exists(directory):
        return (
            MISSING,
            f"no test directory: {prefix} does not exist",
            (),
        )

    modules = 0
    unparseable: list[str] = []
    evidence: list[Evidence] = []
    count = 0

    # iter_files yields sorted relative paths, so the evidence order — and
    # therefore the report digest — is the same on every machine.
    for relative in subject.iter_files(suffix=".py"):
        if not relative.startswith(prefix):
            continue
        modules += 1
        try:
            tree = ast.parse(subject.read_text(relative))
        except SyntaxError:
            unparseable.append(relative)
            continue
        found = sum(1 for node in ast.walk(tree) if _is_test_function(node))
        if found:
            count += found
            evidence.append(
                Evidence(
                    kind="module",
                    locator=relative,
                    digest=subject.digest(relative),
                    note=f"{found} test functions",
                )
            )

    if count < minimum:
        reason = (
            f"{count} test functions found in {modules} Python module(s) "
            f"under {prefix}, fewer than the required {minimum}"
        )
        if unparseable:
            reason += f"; could not parse: {', '.join(unparseable)}"
        return MISSING, reason, ()

    reason = f"{count} test functions across {len(evidence)} module(s) under {prefix}"
    return SATISFIED, reason, tuple(evidence)
