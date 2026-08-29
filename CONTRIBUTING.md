# Contributing to CraftBench-UE

Thanks for looking. This page is the process; [`DEVELOPING.md`](DEVELOPING.md) is
the architecture and the code tour. Read that one first if you want to know how
the thing works.

---

## Maintainer and project status

**Maintainer:** Shutong Wu ([@Scriptwonder](https://github.com/Scriptwonder)),
first author of the paper. Issues and pull requests are read and answered on a
best-effort basis — this is a research artifact maintained alongside other work,
not a staffed product, so please do not read silence as rejection. Ping the
thread if something has gone quiet.

**The studied task set is frozen.** The 70 tasks in `tasks/cpp/`, `tasks/bp/`
and `tasks/python/` are the benchmark the paper reports on. Their specs,
fixtures and reference solutions will not change in ways that would alter a
published verdict — a bug fix that changes what a task grades has to arrive as
a *new* task, not an edit to an existing one. Fixes that make an existing gate
match its own stated intent (a gate that passes a wrong answer, or fails a
right one) are still wanted; say so explicitly in the PR so the effect on
published numbers can be judged.

**New tasks are welcome and are the most valuable contribution.** The tree is
meant to grow past the studied set — that is what `tasks/craftbench-public/`
already is. A new task ships with its own discrimination matrix and does not
disturb anything already measured. See "If you are adding a task" below.

---

## What this project wants

CraftBench-UE measures AI coding agents on real Unreal Engine work, and its only
real asset is that **the verdict is mechanical**. No model judges PASS or FAIL.
Contributions are welcome in rough order of value:

1. **New tasks** that actually discriminate (see below) — the benchmark is only
   as good as its task set.
2. **Verifier fixes** — a gate that passes a wrong answer, or fails a right one,
   is the most serious class of bug here.
3. **Portability** — the validated platform is Windows + UE 5.8. macOS and Linux
   reports are genuinely useful.
4. **Docs** — especially anywhere a document promises something the code does not do.

What we are unlikely to take: changes to what a **measured arm's tools do**. An
arm's tool surface *is* the measurement, so editing one silently breaks
comparability with every number already collected under it. Add an arm instead.

## Before you open a pull request

Run the gates. All of it is stdlib-only and none of it needs the engine:

```sh
python tools/verify-single/tasklint.py --all          # task specs + repo inventory
python -m unittest discover -v tools/verify-single/tests
cd tools/run-agent && python -m unittest discover -v -s tests
```

`.github/workflows/unit-tests.yml` is the authoritative list of suites; CI runs
them on Python 3.11, 3.12 and 3.13 on Windows. If you add a suite, add it there.

**A known local-only failure.** Some fairness tests park fixtures in a directory
keyed by run name under the system temp, so a stale directory from an earlier run
makes them fail on your machine while CI stays green. Point `TEMP`/`TMP` at an
empty directory to tell a real failure from that one.

## If you are adding a task

A task is a file drop — `mkdir tasks/<basket>/<id>` plus a `task.md`. There is no
registry to update. The guides, in order:

1. [`docs/TASK-AUTHOR-GUIDE.md`](docs/TASK-AUTHOR-GUIDE.md) — the whole path, in four
   parts: the walkthrough, spec style, the implementor checklist, and what must be
   true before it ships
2. [`docs/AUTHORING_TEMPLATE.md`](docs/AUTHORING_TEMPLATE.md) — **normative** spec format
3. [`tasks/README.md`](tasks/README.md) — the directory contract and the id rules

**The bar is discrimination, not passing.** A task ships when the reference
solution PASSes *and* an empty submission FAILs **via that task's own named
assertion** — not merely because nothing compiled. A gate that cannot tell a real
solve from a plausible-looking one measures nothing. That evidence lives in the
task's `discrimination/MATRIX.md`, and it is not optional.

Two rules that have each cost a day when broken:

- **No task id may be a substring of another.** Membership checks match on raw
  substrings, so a prefix-shaped id silently reads as another task's row.
- **Map basenames must be globally unique**, even inside per-task folders.
  `tasklint` cannot catch a collision — check it by hand.

## Style

Match the file you are editing. Two things are load-bearing rather than taste:

- **Comments explain *why*, with evidence.** Much of this codebase is guards
  against failure modes that were actually measured. If you add a guard, say what
  it caught. If you remove one, say why it cannot fire any more.
- **Generated files are generated.** `tasks/CATALOG.md` and `docs/MAPS.md` come
  from `tools/coverage/`. Regenerate and commit; do not hand-edit the generated
  blocks. CI checks they agree with `git ls-files`.

## Reporting a problem

- **A wrong verdict** is the highest-value report. Include the task id, the
  submission, and the `result.json` if you have it.
- **A security issue** — see [`SECURITY.md`](SECURITY.md); please do not open a
  public issue for it.
- Anything else: open an issue and say what you expected.

## Licensing

By contributing you agree your contribution is licensed under the MIT License,
the same terms as the rest of the project ([`LICENSE`](LICENSE)). Note that not
everything in a working tree is ours to license — see
[`THIRD-PARTY.md`](THIRD-PARTY.md) for where that line falls, and please do not
add Epic Games engine or template content to this repository.
