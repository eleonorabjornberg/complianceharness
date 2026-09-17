"""Collector implementations.

Importing this package registers every collector. Add your module to the
import list below when you add one, or the registry will not know it
exists and every claim using it will come back UNVERIFIABLE.
"""

from . import declares_no_dependencies  # noqa: F401
from . import documents  # noqa: F401
from . import git_history  # noqa: F401

__all__ = ["documents", "git_history"]
__all__ = ["declares_no_dependencies", "documents"]
