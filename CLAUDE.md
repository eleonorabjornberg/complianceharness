# Agent instructions

Read [CONTRACT.md](CONTRACT.md) before your first change. It is short and
it is binding.

The three things people get wrong here:

1. **Human-only paths.** `src/dossier/model.py`, `src/dossier/engine.py`,
   `tests/test_determinism.py`, `tests/test_packs.py` and `CONTRACT.md`
   are not yours. If your task needs one of them changed, stop and say so.
2. **The determinism rule.** No clock, no absolute paths, no environment,
   no network. A report must be byte-identical across machines.
3. **Test power.** Break your own change on purpose, confirm the suite
   goes red, and record the mutation and the test that caught it in the
   PR body.

Pick work from [BACKLOG.md](BACKLOG.md). Items tagged `[hard]` need a
decision from Eleonora first — open an issue rather than guessing.

    make check      run the suite
    make self       dossier against its own agent-control pack
