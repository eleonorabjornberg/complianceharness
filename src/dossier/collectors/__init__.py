"""Collector implementations.

Importing this package registers every collector. Add your module to the
import list below when you add one, or the registry will not know it
exists and every claim using it will come back UNVERIFIABLE.
"""

from . import documents  # noqa: F401
from . import test_suite_present  # noqa: F401

__all__ = ["documents", "test_suite_present"]
