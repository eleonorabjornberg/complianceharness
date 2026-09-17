# Backlog

Every item is sized so one agent can finish it without asking a question,
and specified so that finishing it is a fact rather than an opinion. Read
[CONTRACT.md](CONTRACT.md) first, then [FACTORY.md](FACTORY.md).

Each item states:

    Sees       what a reviewer can see afterwards that they cannot now
    Touches    the files it may create or change, and no others
    Done when  the test that must exist, and the statuses it must produce
    Absent     what it returns when the thing it looks for is not there
    Mutation   the wrong version of it, and the test that must catch that

Tags: `[collector]` a new way of looking · `[pack]` new claims ·
`[cli]` surface · `[infra]` plumbing · `[human]` a human-only path, not
available to an agent.

Two items were tagged `[hard]` and are now decided; the decisions are
recorded in **C4** and **P1** below and are not open again inside a round.

---

## Collectors — the parallel seam

Each is a new file in `src/dossier/collectors/`, one import line in that
package's `__init__.py`, and a test file with fixtures. They do not import
each other, so all of them can be in flight at once. Expect the conflict in
`collectors/__init__.py` and resolve it by taking both sides.

- [x] **C1 `git_history`** `[collector]`
  - **Sees:** that the subject has a history at all, and which history —
    the sha of its first and last commit, so a verdict can be tied to a
    tree a reviewer can check out.
  - **Touches:** `collectors/git_history.py`, one line in
    `collectors/__init__.py`, `tests/test_collectors_git_history.py`, new
    fixture builders in `tests/fixtures.py`.
  - **Done when:** a fixture built with `git init` and two commits reports
    SATISFIED with both shas as evidence; a fixture with no `.git` reports
    UNVERIFIABLE. `subprocess` is run against the subject root only, with
    an explicit argv list, never a shell string.
  - **Absent:** UNVERIFIABLE, reason naming which of the two it was — no
    `.git`, or no `git` on the machine. Never raises.
  - **Mutation:** raise instead of returning UNVERIFIABLE when `.git` is
    missing. Caught by the no-`.git` fixture test.

- [ ] **C2 `no_commit_touched`** `[collector]`
  - **Sees:** that no commit in the history modified any path matching a
    given glob. This is the collector that makes AC-01 a finding rather
    than an aspiration: it is how a reviewer is shown that the agents did
    not edit their own judge.
  - **Touches:** `collectors/no_commit_touched.py`, `__init__.py`,
    `tests/test_collectors_no_commit_touched.py`, `tests/fixtures.py`.
  - **Done when:** a fixture where one commit touches a protected path
    reports MISSING and names the offending sha and path as evidence; a
    fixture where none does reports SATISFIED. Globs come from the claim's
    parameters, not from a constant in the collector.
  - **Absent:** no history → UNVERIFIABLE, the same way C1 does it.
  - **Mutation:** compare against HEAD's tree only instead of walking every
    commit — a violation that was later reverted would go unreported.
    Caught by a fixture whose offending commit is not HEAD.

- [x] **C3 `commits_are_attributable`** `[collector]` — done 17 Sep
  - **Sees:** that every commit has an author and a non-empty message, and
    — where an agent-author pattern is given — that every matching commit
    carries a trailer naming what produced it.
  - **Touches:** `collectors/commits_are_attributable.py`, `__init__.py`,
    test file, `tests/fixtures.py`.
  - **Done when:** fixtures with and without trailers report SATISFIED and
    MISSING respectively, and the MISSING evidence names the shas, not a
    count.
  - **Absent:** no history → UNVERIFIABLE.
  - **Mutation:** accept an empty trailer value as present. Caught by a
    fixture with `Co-Authored-By:` and nothing after it.

- [ ] **C4 `command_succeeds`** `[collector]` — decided, buildable
  - **Sees:** that a command the subject itself declares runs and exits
    zero inside the subject. The first collector whose evidence is a
    behaviour rather than a document.
  - **The opt-in, decided:** two parties must agree.
    1. The **subject** declares its commands in `.dossier.json` at its
       root: `{"commands": {"suite": ["make", "check"]}}` — a name mapped
       to an argv list. JSON, not TOML: `tomllib` is 3.11+ and this runs on
       3.10. A claim references the *name*, never a command string of its
       own.
    2. The **operator** passes `--allow-commands`. Without it nothing runs.
  - Neither alone is enough. A repository cannot make a stranger's machine
    run its Makefile, and an operator cannot run something the repository
    never offered.
  - **Determinism:** the report records the declared name, the exit status,
    and a digest of stdout+stderr — never the output text, never a
    duration. The environment is constructed literally (a fixed `PATH`, and
    nothing else); reading `os.environ` is forbidden by
    `tests/test_purity.py` and that is the reason why. Timeout required.
  - **Touches:** `collectors/command_succeeds.py`, `__init__.py`,
    `cli.py` (the `--allow-commands` flag), test file, `tests/fixtures.py`.
  - **Done when:** a fixture declaring a trivially passing command reports
    SATISFIED; a trivially failing one reports MISSING with the exit
    status; the same fixture without `--allow-commands` reports
    UNVERIFIABLE, reason `command execution not authorised`; a command
    exceeding the timeout reports UNVERIFIABLE, not MISSING — a timeout is
    not knowledge that the command fails.
  - **Absent:** no `.dossier.json`, or the name not declared in it →
    UNVERIFIABLE naming which.
  - **Mutation:** honour `.dossier.json` without requiring the flag.
    Caught by the no-flag test, which must be written first.

- [ ] **C5 `documented_within`** `[collector]`
  - **Sees:** that a document was last modified within N commits of HEAD.
    This is how STALE stops being a status nothing can produce.
  - **Touches:** `collectors/documented_within.py`, `__init__.py`, test
    file, `tests/fixtures.py`.
  - **Done when:** a fixture where the doc moved with the code reports
    SATISFIED and one where the code moved on without it reports STALE,
    with the distance in commits as evidence. Measured in commits, never in
    days: the determinism rule forbids the clock, and `test_purity.py`
    enforces it.
  - **Absent:** no history, or the document absent → UNVERIFIABLE and
    MISSING respectively. These are different answers and must not collapse.
  - **Mutation:** use file mtime instead of commit distance. Caught by
    `test_purity.py` if it imports `time`, and by a fixture whose files are
    all touched at checkout if it does not.

- [x] **C6 `declares_no_dependencies`** `[collector]`
  - **Sees:** that the subject has no unpinned dependency — no
    `requirements.txt`, `pyproject` dependency list or lockfile, or, where
    there is one, every entry pinned.
  - **Touches:** `collectors/declares_no_dependencies.py`, `__init__.py`,
    test file, `tests/fixtures.py`.
  - **Done when:** fixtures for pinned, unpinned and absent report
    SATISFIED, MISSING and SATISFIED, and the unpinned evidence names the
    offending lines.
  - **Absent:** no dependency file at all is a pass, and the reason string
    must say which of the two passes it is.
  - **Mutation:** treat `>=` as a pin. Caught by an unpinned fixture using
    `>=` rather than a bare name.

- [x] **C7 `test_suite_present`** `[collector]` — done 17 Sep
  - **Sees:** that a test directory exists and contains at least N test
    functions, found by parsing with `ast` rather than by grepping for the
    word test.
  - **Touches:** `collectors/test_suite_present.py`, `__init__.py`, test
    file, `tests/fixtures.py`.
  - **Done when:** a fixture with real tests reports SATISFIED with the
    count; an empty `tests/` reports MISSING; a file that only looks like
    tests — a module named `test_things.py` containing no test function —
    reports MISSING. That third fixture is the point of the item.
  - **Absent:** no test directory → MISSING, not UNVERIFIABLE. Its absence
    is knowledge.
  - **Mutation:** count by regex on the source. Caught by the
    looks-like-tests fixture.

- [x] **C8 `mutation_evidence_recorded`** `[collector]`
  - **Sees:** that the repository records at least one mutation and the
    test that caught it, in the shape CONTRACT.md's "Test power" section
    describes. Weak evidence by design — the point is that its absence is
    informative.
  - **Touches:** `collectors/mutation_evidence_recorded.py`, `__init__.py`,
    test file, `tests/fixtures.py`.
  - **Done when:** fixtures with and without the block report SATISFIED and
    MISSING, and the SATISFIED evidence locates the block by file and line.
  - **Absent:** MISSING.
  - **Mutation:** match the word `mutation` anywhere in the repository.
    Caught by a fixture mentioning mutation testing in prose without
    recording one.

## Packs

- [ ] **P1 Split `model-evidence` into its lineages** `[pack]` — decided
  - **The decision:** one claim, many lineages; packs are selections over a
    single catalogue. A claim belonging to both Annex IV and supervisory
    model-risk practice keeps **one id and one collector**, and carries a
    citation per lineage — because the two regimes ask for the same
    evidence in different words, and that is the argument, not an
    inconvenience. Duplicating the claim per pack would have made the
    overlap something a reader reconstructs by following pointers.
  - [ ] **P1a** `[human]` — `Claim` gains `lineages` (non-empty, sorted,
    from a closed vocabulary) and `citation_by_lineage`, with the invariant
    that their keys match. This is `src/dossier/model.py` and the guard in
    `tests/test_packs.py`: both human-only. An agent must not attempt it.
  - [ ] **P1b** `[pack]` — after P1a: `annex-iv` and `model-risk` become
    named packs selecting from the catalogue, `model-evidence` becomes
    their union, every existing claim id is unchanged, and
    `dossier packs --overlap` lists the claims carrying more than one
    lineage. Touches `packs/`, `packs/__init__.py`, `cli.py`. *Done when a
    claim in both lineages appears once per pack with the same id, and the
    union pack reports it once.*

- [ ] **P2 A `privacy` pack** `[pack]`
  - **Sees:** purpose limitation stated, legal basis recorded, retention
    period declared, a data-subject-rights route documented, transfer
    mechanism named.
  - **Touches:** `packs/privacy.py`, `packs/__init__.py`, and a test in
    `tests/` of its own. Not `tests/test_packs.py`, which is human-only.
  - **Done when:** every claim has a rationale written in the reviewer's
    own terms — who asks for this, and what goes wrong without it. An
    article number is not a rationale and CONTRACT.md says so.
  - **Mutation:** a claim whose rationale restates its own text. Caught by
    a human at the fifth gate, which is why that gate exists.

- [ ] **P3 Downgrade presence-only claims once C5 lands** `[pack]`
  - **Sees:** a stale document reporting STALE instead of a clean pass.
  - **Blocked by:** C5. Taking this before C5 merges produces a claim
    pointing at a collector that does not exist.
  - **Done when:** at least one claim in `model-evidence` reports STALE
    against a fixture whose documentation lags its code.

## Reporting and CLI

- [x] **R1 `--format markdown`** `[cli]` — done 17 Sep
  - **Sees:** a report a non-engineer can paste into a document, with the
    rationale shown for every unsupported claim. Most of this tool's
    audience cannot read the terminal output and should not have to.
  - **Touches:** `cli.py` and a new test file. The report object is not
    changed — formatting reads it, nothing more.
  - **Done when:** the markdown output contains every verdict and every
    unsupported claim's rationale, and the digest line, and a test asserts
    the digest is identical to the text output's for the same report.
  - **Mutation:** compute the digest from the formatted string. Caught by
    the digest-equality test across the two formats.

- [x] **R2 `dossier diff <a.json> <b.json>`** `[cli]`
  - **Sees:** what changed between two reports — which claims gained
    support, which lost it, which appeared.
  - **Touches:** `cli.py`, a new module if it grows past fifty lines, a
    test file.
  - **Done when:** it is a pure function of two parsed JSON documents with
    no filesystem access beyond reading the two arguments, and a test
    covers a claim that changed status, one that did not, and one present
    in only one report.
  - **Mutation:** treat a claim missing from one report as unchanged.
    Caught by the third case.

- [ ] **R3 `--fail-on {blocking,any}`** `[cli]`
  - **Sees:** a CI that can be strict or advisory without the pack being
    rewritten.
  - **Done when:** exit codes still match the table in `cli.py`'s
    docstring, and a test asserts each combination. The default is
    `blocking` — changing the default silently changes every existing
    caller's meaning.

- [ ] **R4 Rationale inline for unsupported claims** `[cli]`
  - **Sees:** why a claim matters, at the moment it fails, truncated to one
    line, in the default output.
  - **Done when:** a test asserts the truncation is by character count and
    not by word, so the output cannot vary with wording.

- [ ] **R5 `dossier explain <claim-id>`** `[cli]`
  - **Sees:** the full text, rationale, severity, lineage and source of one
    claim, without running anything against a subject.
  - **Done when:** an unknown id exits 2 with a message naming the packs
    searched, and a known id in two packs prints both.

## Infrastructure

- [ ] **I1 `--baseline <report.json>`** `[infra]`
  - **Sees:** an adoptable tool. Claims already unsupported in the baseline
    become known debt rather than noise, so a repository that would
    currently fail everything can start using this.
  - **Done when:** a claim unsupported in both baseline and current run is
    reported as debt and does not block; a claim that regressed since the
    baseline blocks; a claim fixed since the baseline is reported as such.
    Test all three.
  - **Mutation:** suppress by claim id regardless of status, so a
    regression on a known-debt claim goes unreported. Caught by the third
    case.

- [ ] **I2 Golden report fixtures** `[infra]`
  - **Sees:** schema drift, in one line of diff, before it reaches anyone.
  - **Done when:** a committed JSON report for a committed fixture tree is
    asserted byte-for-byte, and the failure message tells the reader to
    regenerate deliberately rather than to delete the assertion.

- [x] **I3 `tests/test_purity.py`** `[infra]` — done 14 Sep
  - The determinism rule enforced mechanically: no module under `src/`
    imports a clock, a random source, the network, the machine or the
    environment, and every collector module is imported by its package.
    Both mutations recorded below.

- [ ] **I4 Run against a second real repository in CI** `[infra]`
  - **Sees:** that the tool does not crash on code it has never seen.
  - **Done when:** CI checks out one pinned public repository by sha and
    runs both packs against it, asserting only that the exit code is 0 or
    1 — never 2. The pin is the point: an unpinned subject makes CI
    non-deterministic, which this project cannot have.

---

## Known gap, recorded rather than hidden

`document_present` and `section_present` check that documentation exists and
mentions the right words. They cannot tell whether it is *true*. Every claim
resting on them is weaker than its wording suggests, and the README says so
under Limitations. C1–C5 are the work that closes the gap; until they land,
a green `model-evidence` report means "the paperwork is where a reviewer
would look for it", and nothing more.

## Suggested dispatch

Round one, all parallel, nothing shared but `collectors/__init__.py`:
**C1, C6, C7, C8, R2**. None needs a decision, none blocks another, and
C1 landing unblocks the rest of the git-aware collectors.

Round two: **C2, C3, C5** (each wants C1's history helper), **R1, R4**.

Round three: **C4** (its own flag in the CLI, so not alongside R3),
**P3** (needs C5 merged), **I1, I2, I4**.

Human, not agent, and before round two: **P1a**. Then **P1b** can go out
with round three.

## Mutation log

In the shape CONTRACT.md asks for.

    mutation: engine's unknown-status guard disabled (`if False:`)
    caught by: test_an_unknown_status_is_rejected
    note: NOT caught on first attempt — the model-layer invariant produced
          the same UNVERIFIABLE verdict, so the engine guard was redundant
          and the test had no power over it. Fixed by asserting the reason
          string, not just the status.

    mutation: `import datetime` added to collectors/documents.py
    caught by: test_nothing_under_src_imports_a_source_of_irreproducibility
    note: caught first attempt, naming the file and the reason the import
          is forbidden rather than only failing.

    mutation: a collector module added to collectors/ and left out of that
          package's import list — the silent failure that turns every claim
          using it UNVERIFIABLE
    caught by: test_every_collector_module_is_imported_by_its_package
    note: caught first attempt. This was previously a comment in
          collectors/__init__.py asking people to remember.

    mutation: git_history raised instead of returning UNVERIFIABLE when
          .git is missing
    caught by: test_no_git_directory_reports_unverifiable
    note: caught first attempt. The test calls the collector directly, so
          the raise surfaces; behind the engine's catch-all it would have
          come back as the same UNVERIFIABLE verdict and hidden the defect.
    mutation: `>=` accepted as a pin in declares_no_dependencies
    caught by: test_a_geq_constraint_is_not_a_pin
    note: caught first attempt, along with three sibling unpinned tests.
          The unpinned fixture uses `>=` rather than a bare name precisely
          so this mutation has a witness.

    mutation: diff treated a claim missing from one report as unchanged —
          the one-sided claim moved into `unchanged` and neither appeared
          nor disappeared was ever reported
    caught by: test_a_claim_present_in_only_one_report_is_not_reported_as_unchanged
    note: caught first attempt. The CLI-level test caught it too: the
          appeared section vanished and the one-sided claim showed up in
          the unchanged line.

    mutation: the markdown format computed the digest from the formatted
          string instead of the report
    caught by: test_the_digest_is_identical_across_text_and_markdown_formats
    note: caught first attempt. The text format digests the report; the
          mutated markdown hashed its own rendering, and for the same
          report the two formats printed different digests.

    mutation: an empty trailer value (`Co-Authored-By:` with nothing after
          it) accepted as a producer trailer
    caught by: test_an_empty_trailer_value_is_not_a_producer_trailer
    note: caught first attempt, as the only red test of twelve. A trailer
          that names nothing does not attribute a commit, so the fixture
          carrying the bare token reports MISSING, not SATISFIED.
