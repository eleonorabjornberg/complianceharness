"""Claim packs.

A pack is a versioned set of expectations from one source. Packs are the
only place the tool encodes an opinion about what "under control" means,
which keeps the engine honest: adding a regime means adding a pack, not
editing the machinery.
"""

from __future__ import annotations

from ..model import Pack
from . import agent_control, model_evidence

_PACKS: dict[str, Pack] = {
    model_evidence.PACK.name: model_evidence.PACK,
    agent_control.PACK.name: agent_control.PACK,
}


def get(name: str) -> Pack | None:
    return _PACKS.get(name)


def names() -> tuple[str, ...]:
    return tuple(sorted(_PACKS))


def all_packs() -> tuple[Pack, ...]:
    return tuple(_PACKS[name] for name in names())
