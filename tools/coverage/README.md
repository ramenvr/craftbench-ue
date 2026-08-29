# tools/coverage — task-set & concept coverage reporting

Two pure-stdlib reporting scripts that answer "how much of the benchmark
does the current task set actually cover, and how far along is each task?"
Neither builds the UE project, runs PIE, or calls any verifier layer — they
read only markdown + CSV + JSON already on disk, so they run anywhere with a
plain Python 3 (no UE install, no Aura). They are reporting instruments, not
part of the graded verifier path (that is `tools/verify-single/` / the `cb`
launcher).

- **`coverage.py`** — high-tier concept-coverage report. Joins each task
  spec's `## Primary concept` id(s) against the in-scope, high-tier rows of
  the concept catalogue (`tools/coverage/concepts.csv`, folder-local) and reports
  covered / uncovered concepts and a per-UE-doc-section rollup.

  It answers one question: of the UE concepts the benchmark says it cares
  about, which does the task set actually exercise? A concept counts as
  covered when some task spec names it as its PRIMARY concept.

## Running

```sh
# Concept-coverage report (human-readable + JSON tail); add --json for JSON only.
python3 tools/coverage/coverage.py

# Unit tests (stdlib unittest, no UE required)
python3 -m unittest discover -v tools/coverage/tests
```

Inputs resolve relative to the repo root by default; `--concepts` and
`--tasks` override them.

## Scope, and what this number is not

Coverage here means **referenced**: some task spec names the concept as its
primary. It does **not** mean the concept is well tested — one task naming
`enhanced-input` makes that concept covered no matter how narrow the task is.
Read it as a breadth map of the task set, not a quality claim.

The per-task evidence that a verifier actually discriminates lives with each
task, in `tasks/<set>/<id>/discrimination/MATRIX.md`.

There used to be a second tool here, `status_gen.py`, which classified every
task as validated / wired / advisory / paper and generated a status block into
`tasks/CATALOG.md`. Its authority for *validated* was a dated table in
`ROADMAP.md`, which is not part of this release — so in a public clone it
classified everything as `wired`, printed a pasteable block saying so, and
exited 0. It was removed rather than left to overwrite a correct table with an
empty one.
