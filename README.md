# Compliance Harness

An evidence register for systems that have to be shown to be under
control — to someone who does not trust you.

Point it at a repository. It reports which claims a reviewer would make
about that system are supported by evidence, which are not, and which it
cannot determine either way.

```
$ PYTHONPATH=src python3 -m dossier check ../repo-market-model --pack model-evidence

repo-market-model  ·  model-evidence 0.1.0

  ok    ME-01  found README.md
          └─ file: README.md
  MISS  ME-03  no 'Limitations' section in any of: README.md, MODEL_CARD.md
  ok    ME-04  README.md has a 'Evaluation' section
          └─ section: README.md:48

satisfied: 4  missing: 2
report digest: 9f2c1a44b8e07d31
```

## Purpose

Two kinds of reviewer are asking the same question in different
vocabularies.

A **model validator** — or a conformity reviewer working from Annex IV of
the EU AI Act — asks: what is this for, what was it built from, how do
you know it works, and what do you know it cannot do?

A **reviewer of an autonomous codebase**, where agents write the code,
asks: what were the agents forbidden to touch, can you attribute a change
to the thing that made it, and do the tests that judge the work have any
power to catch it cheating?

Both are asking *can you show this is under control*. `dossier` treats
them as one problem with two claim packs.

## Limitations

Read these before quoting a report at anyone.

- **Presence is weak evidence.** Most collectors today check that a
  document exists and mentions the right things. That a `DATA.md` exists
  is not a claim that its contents are true, complete, or current.
- **A green report is not a compliance opinion.** It says the evidence a
  reviewer would ask for can be located. Whether the evidence is any good
  is a human judgment and the tool does not make it.
- **The `agent-control` pack has no authority behind it.** There is no
  published framework for governing autonomous coding agents. Those
  claims are derived from observed failure modes and argued on their own
  merits in each claim's rationale. Disagree with them freely.
- **`unverifiable` is not a soft fail.** It means the register does not
  know, which is deliberately different from saying no.

## Evaluation

The property the project actually guarantees is reproducibility: the same
subject in the same state produces a byte-identical report, on any
machine, and the report's digest is how it records *when*. That guarantee
is enforced by `tests/test_determinism.py`, which is human-owned and
cannot be edited by an agent.

Reports carry no clock and no absolute paths. See the determinism rule in
[CONTRACT.md](CONTRACT.md).

## To reproduce anything here

```
make check      # run the test suite
make self       # run dossier against its own agent-control pack
make packs      # list every claim and its rationale
```

No install step, no dependencies, standard library only. Python 3.10+.

## Owner

Eleonora Björnberg. Claims, rationales and the determinism rule are
human-owned; see the human-only paths in [CONTRACT.md](CONTRACT.md).
