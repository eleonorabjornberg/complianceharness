"""The collector that looks for unpinned dependencies.

A subject that says "I use requests" without saying which requests
cannot be audited: the thing it depends on is free to change underneath
it. This collector reads the dependency declarations a Python subject
actually carries and reports every entry that is not pinned to an exact
version.

What it reads, and what it deliberately does not:

- ``requirements.txt`` — one entry per non-comment, non-blank line.
  Directive lines (``-r``, ``-e``, ``--index-url``) install things but
  declare no version to pin, so they are skipped; a ``-r`` include keeps
  another file's entries out of this check, which a pack using this
  collector should own in its claim text.
- ``pyproject.toml`` — the ``[project]`` ``dependencies`` array and the
  ``[project.optional-dependencies]`` tables, read line by line with a
  bracket count, because ``tomllib`` is 3.11+ and this project runs on
  3.10 (the same reason C4's ``.dossier.json`` is JSON). Build-system
  ``requires`` is a build backend's wish list, not the subject's
  dependency list, and is not read.
- lockfiles — ``Pipfile.lock``, ``poetry.lock``, ``uv.lock``. A lockfile
  pins every entry by construction; that is what makes it a lockfile.

Two ways to pass, and the reason string says which one happened: the
subject declares no dependency file at all, or every declared entry is
pinned with ``==``. A range — ``>=``, ``~=`` — is not a pin.
"""

from __future__ import annotations

import re

from ..model import MISSING, SATISFIED, Evidence
from ..registry import register
from ..subject import Subject

_REQUIREMENTS_FILE = "requirements.txt"
_PYPROJECT_FILE = "pyproject.toml"
_LOCKFILES = ("Pipfile.lock", "poetry.lock", "uv.lock")
_SEARCHED = (_REQUIREMENTS_FILE, _PYPROJECT_FILE) + _LOCKFILES

# Comments are stripped the way pip does it: a '#' at the start of the
# line or preceded by whitespace. A '#' inside a URL is not a comment.
_COMMENT = re.compile(r"(^|\s)#.*$")
_KEY_VALUE = re.compile(r"([A-Za-z0-9_.-]+)\s*=\s*(.*)")
_QUOTED = re.compile(r'"([^"]*)"')


def _is_pinned(entry: str) -> bool:
    """An exact version pin is ``==``. A range is not a pin."""
    return "==" in entry


def _requirements_entries(text: str) -> list[tuple[int, str]]:
    """Requirement entries in a requirements-style file, as (line, entry)."""
    entries: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _COMMENT.sub("", raw).strip()
        if not line or line.startswith("-"):
            continue
        entries.append((number, line))
    return entries


def _pyproject_entries(text: str) -> list[tuple[int, str]]:
    """Requirement entries in a pyproject.toml, as (line, entry).

    Line-based, not a TOML parse: the array is followed by a bracket
    count and every double-quoted string inside it is one entry. Covers
    the standard layouts (inline and multi-line arrays, one key per
    optional-dependency group); exotic TOML is left on the table rather
    than half-parsed.
    """
    entries: list[tuple[int, str]] = []
    table = ""
    key: str | None = None
    depth = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if depth == 0 and stripped.startswith("[") and stripped.endswith("]"):
            table = stripped[1:-1].strip()
            key = None
            continue
        if depth == 0:
            match = _KEY_VALUE.match(stripped)
            if match is None:
                continue
            key, value = match.group(1), match.group(2)
        else:
            value = stripped
        collecting = (table == "project" and key == "dependencies") or (
            table == "project.optional-dependencies"
        )
        if not collecting:
            continue
        depth += value.count("[") - value.count("]")
        for entry in _QUOTED.findall(_COMMENT.sub("", value)):
            if entry.strip():
                entries.append((number, entry.strip()))
        if depth <= 0:
            depth = 0
    return entries


@register("declares_no_dependencies")
def declares_no_dependencies(subject: Subject) -> tuple[str, str, tuple[Evidence, ...]]:
    """Every declared dependency is pinned to an exact version.

    Reads requirements.txt, the pyproject.toml dependency lists and the
    known lockfiles (see the module docstring for the deliberate limits
    of each parser). MISSING names the offending lines. The two passes
    are distinct and the reason says which happened: no dependency file
    at all, or every declared entry pinned.
    """
    files: list[tuple[str, list[tuple[int, str]]]] = []
    if subject.exists(_REQUIREMENTS_FILE):
        files.append(
            (
                _REQUIREMENTS_FILE,
                _requirements_entries(subject.read_text(_REQUIREMENTS_FILE)),
            )
        )
    if subject.exists(_PYPROJECT_FILE):
        files.append(
            (_PYPROJECT_FILE, _pyproject_entries(subject.read_text(_PYPROJECT_FILE)))
        )

    unpinned: list[Evidence] = []
    pinned: list[Evidence] = []
    for relative, entries in files:
        offending = [(number, entry) for number, entry in entries if not _is_pinned(entry)]
        if offending:
            unpinned.extend(
                Evidence(kind="entry", locator=f"{relative}:{number}", note=entry)
                for number, entry in offending
            )
        else:
            note = (
                f"{len(entries)} dependency entries, all pinned"
                if entries
                else "dependency file with no entries"
            )
            pinned.append(
                Evidence(
                    kind="file",
                    locator=relative,
                    digest=subject.digest(relative),
                    note=note,
                )
            )

    for name in _LOCKFILES:
        if subject.exists(name):
            pinned.append(
                Evidence(
                    kind="file",
                    locator=name,
                    digest=subject.digest(name),
                    note="lockfile pins every dependency",
                )
            )

    if unpinned:
        offending_files = list(
            dict.fromkeys(locator.rsplit(":", 1)[0] for locator in (e.locator for e in unpinned))
        )
        reason = (
            "unpinned dependency entries in " + ", ".join(offending_files)
            + " — every entry must be pinned to an exact version (==)"
        )
        return MISSING, reason, tuple(unpinned)

    if pinned:
        return (
            SATISFIED,
            "every declared dependency entry is pinned to an exact version",
            tuple(pinned),
        )

    return (
        SATISFIED,
        "no dependency declaration to audit: no requirements.txt, "
        "no pyproject.toml dependency list, no lockfile",
        (
            Evidence(
                kind="search",
                locator=", ".join(_SEARCHED),
                note="none of these exists",
            ),
        ),
    )
