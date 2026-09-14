# Backlog

Items are sized so that one agent can finish one without asking a
question. Each names the test that would prove it. Read
[CONTRACT.md](CONTRACT.md) first — in particular the human-only paths and
what a change must carry.

Tags: `[collector]` new way of looking · `[pack]` new claims ·
`[cli]` surface · `[infra]` plumbing · `[hard]` needs a decision from
Eleonora before it can be built.

---

## Collectors — the main seam for parallel work

Each of these is a new file in `src/dossier/collectors/`, a line in that
package's `__init__.py`, and a test file with fixtures. They do not touch
each other, so they can all be in flight at once.

- [ ] **C1 `git_history`** `[collector]` — the subject is a git
  repository with more than one commit. Evidence: the sha of the first
  and last commit. Use `subprocess` against the subject root only, and
  return UNVERIFIABLE (never raise) when `.git` is absent or `git` is not
  installed. *Test: a fixture built with `git init` and two commits; a
  second fixture with no `.git` at all.*

- [ ] **C2 `no_commit_touched`** `[collector]` — no commit in the history
  modified any path matching a given glob. This is the collector that
  makes AC-01 real rather than aspirational: it is how you prove the
  agents did not edit their own judge. *Test: a fixture where a commit
  touches a protected path, and one where none does.*

- [ ] **C3 `commits_are_attributable`** `[collector]` — every commit has
  an author and a non-empty message; optionally, that every commit
  matching an agent-author pattern also carries a trailer naming what
  produced it. *Test: fixtures with and without trailers.*

- [ ] **C4 `command_succeeds`** `[collector]` — a declared command runs
  and exits zero inside the subject. Needs a timeout, needs the output
  captured but kept out of the report body (digest it instead — the
  determinism rule), and needs an explicit opt-in because running a
  stranger's Makefile is a real risk. *Test: a fixture with a trivially
  passing and a trivially failing command.* `[hard]` — decide the opt-in
  mechanism before building.

- [ ] **C5 `documented_within`** `[collector]` — a document was last
  modified in a commit no more than N commits behind HEAD. This is how
  `STALE` stops being a status nothing can produce. Measure in commits,
  not days: the determinism rule forbids reading the clock. *Test: a
  fixture where the doc is fresh and one where code moved on without it.*

- [ ] **C6 `declares_no_dependencies`** `[collector]` — no
  `requirements.txt`, `pyproject` dependency list or lockfile, or, where
  there is one, every entry is pinned. *Test: fixtures for pinned,
  unpinned and absent.*

- [ ] **C7 `test_suite_present`** `[collector]` — a test directory exists
  and contains at least N test functions, found by parsing with `ast`
  rather than by regex. *Test: a fixture with tests, one with an empty
  `tests/`, one with a file that only looks like tests.*

- [ ] **C8 `mutation_evidence_recorded`** `[collector]` — the repository
  records at least one mutation and the test that caught it, in the shape
  CONTRACT.md's "Test power" section describes. Weak evidence by design;
  the point is that its absence is informative. *Test: fixtures with and
  without the block.*

## Packs

- [ ] **P1** Split `model-evidence` into its two lineages — the Annex IV
  claims and the supervisory model-risk claims — so a user can run either
  alone and see where they overlap. Keep the claim ids stable. `[hard]`
  — the overlap is the interesting part of the thesis argument; decide
  how to represent a claim that belongs to both.

- [ ] **P2** Add a `privacy` pack: purpose limitation stated, legal basis
  recorded, retention period declared, data subject rights route
  documented, transfer mechanism named. Rationale for each in the
  reviewer's own terms, not the article number.

- [ ] **P3** Claims currently satisfied by presence alone should be
  downgraded once C5 lands, so a stale document reports STALE rather than
  a clean pass.

## Reporting and CLI

- [ ] **R1** `--format markdown` — emit a report a human can paste into a
  document, with the rationale shown for every unsupported claim. This is
  the output that makes the tool useful to a non-engineer, which is most
  of its audience.

- [ ] **R2** `dossier diff <report-a.json> <report-b.json>` — what
  changed between two reports. Pure function of two JSON files, no
  filesystem access, trivially testable.

- [ ] **R3** `--fail-on {blocking,any}` so CI can be strict or advisory.

- [ ] **R4** Show the claim's rationale inline for unsupported claims in
  the default output, truncated to one line.

- [ ] **R5** A `dossier explain <claim-id>` subcommand printing the full
  text, rationale, severity and source of one claim.

## Infrastructure

- [ ] **I1** A `--baseline <report.json>` flag that treats claims already
  unsupported in the baseline as known debt, so the tool can be adopted
  by a repository that would currently fail everything.

- [ ] **I2** Golden-report fixtures: a committed JSON report for a
  committed fixture tree, asserted byte-for-byte. Catches accidental
  schema drift in one line of diff.

- [ ] **I3** A `tests/test_purity.py` that imports every collector module
  and asserts none of them reference `datetime`, `time`, `os.environ`,
  `requests` or `urllib` — the determinism rule, enforced mechanically
  instead of by review.

- [ ] **I4** Run `dossier` against a second real repository in CI, as a
  smoke test that it does not crash on code it has never seen.

---

## Known gap, recorded rather than hidden

The `document_present` and `section_present` collectors check that
documentation exists and mentions the right words. They cannot tell
whether it is *true*. Every claim resting on them is therefore weaker
than its wording suggests, and the README says so under Limitations.
C1–C5 are the work that closes this gap; until they land, a green
`model-evidence` report means "the paperwork is where a reviewer would
look for it", nothing more.

## Mutation log

Recorded in the shape CONTRACT.md asks for.

    mutation: engine's unknown-status guard disabled (`if False:`)
    caught by: test_an_unknown_status_is_rejected
    note: NOT caught on first attempt — the model-layer invariant produced
          the same UNVERIFIABLE verdict, so the engine guard was redundant
          and the test had no power over it. Fixed by asserting the reason
          string, not just the status.
