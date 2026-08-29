# Developing CraftBench-UE

The front door for anyone who wants to **understand, extend, or contribute to** the
harness — as opposed to just running it. If you only want to grade a task, start at
[`README.md`](README.md) instead; it takes you from clone to first verdict.

This page is deliberately a map, not a manual. Each section says what the thing is,
what the non-obvious constraint is, and where the real document lives.

---

## 1. The one idea

A task is a plain-English behaviour spec. An agent edits an Unreal project. A
**deterministic verifier** then builds that project, runs it for real, and inspects
what happened. **No model decides PASS or FAIL** — every gate is a concrete fact: a
build succeeded, an in-game assertion held, an asset's structure matched.

That constraint is the whole design. Most of what looks like over-engineering in
this repo exists to keep it true under an agent that is actively trying to pass.

The vocabulary — layer, gating, discrimination, substrate, contamination — is
defined once in [`CONTEXT.md`](CONTEXT.md). Read that before the code; the terms are
used precisely and the code will not make sense without them.

## 2. What is where

| Path | What lives there |
|---|---|
| `tools/run-agent/` | The driver. Puts an agent in front of a task, captures the transcript, writes `result.json`. The arms are in `adapters/`. |
| `tools/verify-single/` | The verifier. One task, one submission, one verdict. Layers in `layers/`, structural checks in `introspect/`. |
| `tools/dashboard/` | Reading a run afterwards: the HTML report, a TUI and a web UI. Never gating. |
| `tools/coverage/`, `tools/compare/`, `tools/runlib/` | Corpus bookkeeping, cross-run rollups, and the single task-identity implementation every reader delegates to. |
| `tasks/` | The benchmark. One directory per task: `task.md`, `reference/`, `discrimination/`. |
| `UE-projects/` | The two substrates. `CraftBenchTemplate` is minimal; `ThirdPerson` is the stock UE template. Each carries a verifier-only `CraftBenchTests` module the agent may never edit. |

Epic's template content is **not** committed. `tools/scripts/bootstrap_substrate.py`
restores it from your own UE 5.8 install — see [`THIRD-PARTY.md`](THIRD-PARTY.md) for
exactly where that line falls.

## 3. Running the checks

Everything is stdlib-only and needs no engine, except where noted.

```sh
# the two gates CI runs first
python tools/verify-single/tasklint.py --all        # task specs + repo inventory

# the suites, in the order CI runs them
python -m unittest discover -v tools/verify-single/tests
cd tools/run-agent && python -m unittest discover -v -s tests   # then cd back
python -m unittest discover -v -s tools/coverage/tests         -t .
python -m unittest discover -v -s tools/verify-r2/tests        -t .
python -m unittest discover -v -s tools/verify-stability/tests -t .
python -m unittest discover -v -s tools/compare/tests          -t .
python -m unittest discover -v -s tools/dashboard              -t .
python -m unittest discover -v -s tools/runlib/tests           -t .
python -m unittest discover -v -s tools/authoring/tests        -t .
```

`.github/workflows/unit-tests.yml` is the authoritative list — if you add a suite,
add it there too.

**One trap worth knowing.** Some fairness tests park fixtures in a directory keyed
by run name under the system temp. A stale park directory from an earlier run makes
them fail on a developer box while CI stays green. Point `TEMP`/`TMP` at an empty
directory to tell a real failure from that.

## 4. Authoring a task

A task is a file drop: `mkdir tasks/<basket>/<id>` plus a `task.md`. There is no
registry to update — discovery globs `*/task.md`.

The order that works:

1. [`docs/TASK-AUTHOR-GUIDE.md`](docs/TASK-AUTHOR-GUIDE.md) — the whole path in four
   parts: walkthrough, spec style, implementor checklist, acceptance.
2. [`docs/AUTHORING_TEMPLATE.md`](docs/AUTHORING_TEMPLATE.md) — **normative** spec format.
3. [`tasks/README.md`](tasks/README.md) — the directory contract and the id rules.

**A task is not finished when it passes.** It is finished when it *discriminates*:
the reference solution PASSes, and an empty submission FAILs **via that task's own
named assertion** — not merely because nothing compiled. A gate that cannot tell a
real solve from a plausible-looking one measures nothing, so
`discrimination/MATRIX.md` is mandatory and CI checks its shape.

Two rules that have each cost a day when broken:

- **No task id may be a substring of another.** Membership checks match on raw
  substrings, so a prefix-shaped id silently reads as another task's row.
- **Map basenames must be globally unique**, even in per-task folders. `cb lint`
  cannot catch a collision; it has to be checked by hand.

## 5. Extending the harness

**Adding an arm.** Arms live in `tools/run-agent/adapters/registry.py`. They sit on
two axes — the tool layer the agent gets, and how the model is routed — and the
registry's own comments warn against collapsing the two. An arm's tool surface *is*
the measurement: change what a shipped arm's tools do and you have broken
comparability with every number already collected under it. Add an arm rather than
editing one.

**Adding a verifier layer.** Layers declare whether they gate, where they sit in run
order, and what they depend on (`tools/verify-single/layers/registry.py`). A new
gating layer needs a discrimination story before it can gate anything.

**Reading the code.** [`docs/harness-tour/`](docs/harness-tour/) walks the whole
pipeline in five parts, from the run driver through the verifier to the output side.
That is the fastest way in.

## 6. Conventions

- **The code wins.** Where a document and the code disagree, the code is right and
  the document is a bug. [`CONTEXT.md`](CONTEXT.md) says this about itself, and it
  applies to this page too.
- **Generated files are generated.** `tasks/CATALOG.md` and `docs/MAPS.md` are
  produced by `tools/coverage/`. Regenerate and commit; do not hand-edit the
  generated blocks. CI checks they match `git ls-files`.
- **Windows is the validated platform.** UE 5.8 on Windows is what CI and the
  authors run. macOS support is historical and Linux is unproven — the docs say so
  wherever it matters, and [`docs/WINDOWS.md`](docs/WINDOWS.md) is the
  platform runbook.

## 7. Where else to look

| Document | For |
|---|---|
| [`README.md`](README.md) | Install, configure, run your first eval |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | The process: gates to run, the task bar, what we will and will not take |
| [`SECURITY.md`](SECURITY.md) | Reporting a vulnerability, and what is in scope |
| [`EVALS.md`](EVALS.md) | The narrative run-book: how a run flows end to end |
| [`ONBOARDING.md`](ONBOARDING.md) | Long-form setup, the `cb` launcher, troubleshooting |
| [`docs/CHEATSHEET.md`](docs/CHEATSHEET.md) | Every command and flag |
| [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) | The map of every other document |
| [`THIRD-PARTY.md`](THIRD-PARTY.md) | What is Epic's, what is ours, what the MIT grant covers |
