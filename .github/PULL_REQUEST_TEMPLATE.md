## What this is

Backlog item:
<!-- C1 / R2 / I3 ... or "unlisted", and why it was worth doing anyway -->

One sentence: what a reviewer can now see that they could not see before.

## Boundary

- [ ] No file in this diff is a human-only path. CI checks this too, by
      reading the list out of CONTRACT.md — if the check and this box
      disagree, the check is right.
- [ ] The engine is unmodified. If this change wanted the engine changed,
      say so here rather than routing around it:

## Determinism

- [ ] Nothing added here reads a clock, an absolute path, the environment,
      or the network. `tests/test_purity.py` checks the imports; this box
      is for what a test cannot see.
- [ ] `make self` digest unchanged, or changed for the reason below:

## Test power

Break your own change on purpose and prove the suite notices.

    mutation:
    caught by:
    note:

A mutation block reading `caught by: nothing — the suite stayed green` is
more valuable than an omitted one. Report it and say what you did about it.
