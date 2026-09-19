"""Collector implementations.

Importing this package registers every collector. Add your module to the
import list below when you add one, or the registry will not know it
exists and every claim using it will come back UNVERIFIABLE.
"""

from . import commits_are_attributable  # noqa: F401
from . import command_succeeds  # noqa: F401
from . import declares_no_dependencies  # noqa: F401
from . import documented_within  # noqa: F401
from . import documents  # noqa: F401
from . import git_history  # noqa: F401
from . import mutation_evidence_recorded  # noqa: F401
from . import no_commit_touched  # noqa: F401
from . import test_suite_present  # noqa: F401

__all__ = [
    "command_succeeds",
    "commits_are_attributable",
    "declares_no_dependencies",
    "documented_within",
    "documents",
    "git_history",
    "mutation_evidence_recorded",
    "no_commit_touched",
    "test_suite_present",
]
