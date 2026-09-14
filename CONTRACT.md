# Contract

This file is the standing instruction for every agent and every person
working in this repository. It is the thing the tool itself checks for in
other repositories, so it had better be true here.

## What this project is

`dossier` is an evidence register. You point it at a system and it tells
you which claims a reviewer would make about that system are supported by
evidence, which are not, and which it cannot determine either way.

It holds no opinion of its own. Opinions live in **packs**. Today there
are two:

- `model-evidence` — what a model validator or an EU AI Act Annex IV
  reviewer asks of a machine learning system.
- `agent-control` — what a reviewer should ask of a codebase where
  autonomous agents write the code.

They are the same problem wearing different clothes: *can you show this
system is under control, to someone who does not trust you?*

## The five nouns

    Claim      an assertion that ought to hold about a subject
    Collector  a deterministic function that looks for support for it
    Evidence   what it found, with a locator a human can go and check
    Verdict    supported, not supported, stale, or unknown — and why
    Report     every verdict for one pack against one subject

Adding a regime means adding a pack. Adding a way of looking means adding
a collector. Neither should require touching the engine. If your change
needs the engine modified, that is a signal worth raising rather than
routing around.

## Human-only paths

Agents may not modify these. They are the things that judge the work, and
work may not edit its own judge.

    src/dossier/model.py        the five nouns and their invariants
    src/dossier/engine.py       the evaluation loop
    tests/test_determinism.py   the reproducibility guarantee
    tests/test_packs.py         the guards on pack integrity
    CONTRACT.md                 this file

Everything else is fair game: collectors, packs, the CLI, fixtures, the
tests that go with your own contribution, docs.

If a task genuinely cannot be done without changing a human-only file,
stop and say so in the pull request. Do not work around the boundary by
adding a parallel implementation elsewhere — that is worse than asking.

## The determinism rule

**A report carries no clock and no absolute paths.** The same subject in
the same state must produce a byte-identical report on any machine, and
its digest is how the project says "when".

This means:

- every `Evidence.locator` is relative to the subject root
- no `datetime.now()`, anywhere, ever, in `src/`
- anything iterating the filesystem sorts its results before returning
- no environment variables, no network, no reading outside the subject

A report with a timestamp in it would be this project's own thesis
failing in its own output.

## What a change must carry

Every pull request, whoever or whatever opened it:

1. **A test that fails without the change.** Not a test that passes
   afterwards — one that demonstrably fails before. Say so in the PR body.
2. **A fixture, not the real filesystem.** Collector tests build their
   subject in `tests/fixtures.py`. A test that reads this repository, the
   developer's home directory, or the network is not a test.
3. **A rationale on any new claim,** in the reviewer's own terms: who
   asks for this and what goes wrong without it. "The framework requires
   it" is not a rationale and will be rejected.
4. **A green suite.** `make check` passes, including the determinism and
   pack-integrity tests.
5. **No new dependency.** The standard library only. A tool that audits
   other people's supply chains does not get to have one.

## Test power

A passing suite is evidence of nothing until someone has shown it fails
when the code is wrong. Under autonomous delivery this stops being
hygiene and becomes the primary control, because no human is reading the
diff.

So: when you add a collector, break it on purpose and confirm the suite
goes red. Record what you broke and which test caught it in the PR body,
in one line:

    mutation: returned SATISFIED with empty evidence
    caught by: test_a_satisfied_verdict_without_evidence_is_rejected

A change whose mutation nothing catches has no test power, whatever the
coverage figure says.

## How to reproduce anything this project reports

    make check          run the suite
    make self           run dossier against itself
    PYTHONPATH=src python3 -m dossier check <path> --pack model-evidence

There is no install step and no build. If a command in this file does not
work from a clean clone, that is a bug worth fixing before anything else.
