"""Collector registry.

A collector is a pure function of a Subject and its claim's params:

    (subject, **params) -> (status, reason, evidence)

Pure means: no clock, no network, no absolute paths, no reading anything
outside the subject root. Two calls against the same subject state must
return the same triple. Every rule here is enforced by a test in
tests/test_purity.py, so a collector that breaks one fails CI rather
than quietly poisoning a report.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from .model import Evidence, ContractError
from .subject import Subject

CollectorResult = tuple[str, str, tuple[Evidence, ...]]
Collector = Callable[..., CollectorResult]

_REGISTRY: dict[str, Collector] = {}


def register(name: str) -> Callable[[Collector], Collector]:
    def decorate(function: Collector) -> Collector:
        if name in _REGISTRY:
            raise ContractError(f"collector {name!r} is already registered")
        if not (function.__doc__ or "").strip():
            raise ContractError(f"collector {name!r} must have a docstring")
        _REGISTRY[name] = function
        return function

    return decorate

def get(name: str) -> Collector | None:
    return _REGISTRY.get(name)


def names() -> Iterable[str]:
    return sorted(_REGISTRY)


def run(name: str, subject: Subject, params: dict[str, Any]) -> CollectorResult:
    collector = get(name)
    if collector is None:
        raise KeyError(name)
    return collector(subject, **params)
