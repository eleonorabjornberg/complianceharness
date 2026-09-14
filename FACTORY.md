# The loop

CONTRACT.md says what a change must be. This says how a change gets from
the backlog to `main` with nobody in the middle of it.

## Where work comes from

Three sources, in descending order of how far they can be trusted:

1. **BACKLOG.md** — items already sized and specified. An agent takes one
   and does not invent a second.
2. **Issues labelled `finding`** — a report that was wrong, weak or
   misleading. Worth more than a backlog item, because it comes from the
   tool being used rather than from planning.
3. **`make self`** — dossier's own agent-control report. Anything it marks
   MISSING about this repository is a work item this repository chose for
   itself, in public, and then did not do.

## One item, one branch, one pull request

Never two items in a branch. Not for tidiness: a round of agents merges
independently, and a branch carrying two items cannot be merged halfway.

The parallel seam is `src/dossier/collectors/`. Collectors do not import
each other, so any number can be in flight at once. The seams that are not
parallel, and where a round will collide: `collectors/__init__.py` (every
new collector adds a line — resolve by taking both), `BACKLOG.md`, and
anything under `packs/`.

## The gates

Cheapest first. A pull request failing any of them is not merged, and the
fix is never to relax the gate.

    make check                             the suite, under a second
    make boundary BASE=origin/main         human-only paths untouched
    the determinism job                    two paths, one digest, byte for byte
    the PR body's mutation block           filled in, honestly
    a human, on the rationale only         claims and their justification

The first three are CI. The fourth is a convention CI cannot check, which
is why it is written down: a mutation block reading `caught by: nothing`
is an honest answer to the question and a failing test suite, and the
second of those is the more interesting fact.

The fifth is the only place a person is required, and it is deliberately
narrow — whether this is a claim a real reviewer would make, and whether
its rationale survives being read by one. Not the code.

## What an agent decides alone

- how a collector is implemented, what it names things, how its fixtures
  are built
- the wording of a reason string
- whether a backlog item that turned out to be two should be split

## What it stops and asks about

- anything that wants a human-only path changed
- a new claim whose rationale it cannot write without inventing authority
- a dependency
- an item tagged `[hard]`
- a determinism failure, which halts the round rather than being routed
  around

## Closing a round

Verify before believing. In each branch:

    make check
    make boundary BASE=origin/main
    make self

Then read the mutation block, then the rationale, then merge. That order
matters: the mutation block is what tells you whether the tests have any
power over the change, and without it the green suite above means nothing.

## Stop conditions

Halt the round, not just the branch:

- two runs of the same subject state produce two digests
- a merged mutation block turns out to have been false
- `make self` regresses on a claim this repository previously satisfied
