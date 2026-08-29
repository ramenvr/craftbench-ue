# `tasks/` — how a task is laid out

This is the only document describing the task tree. Individual task folders carry
no README of their own; everything a reader needs is either here or inside the
task's own `task.md`.

Every task lives at `tasks/<basket>/<task-id>/`. There are no flat `tasks/*.md`
specs. Adding a task is `mkdir tasks/<basket>/<id>` plus a `task.md` — discovery
is a pure file drop, with no registry to update.

## What a task folder contains

| entry | required | contract |
|---|---|---|
| `task.md` | **yes** | The spec: a front-matter block (`--- id/layers/fixtures/… ---`, the machine-readable facts) followed by the markdown body (the agent's prompt plus human documentation). The one parser is `tools/verify-single/spec.py::parse_task_file`. The front-matter `id:` MUST equal the folder name. Format is normative — see `docs/AUTHORING_TEMPLATE.md`. |
| `reference/` | for runnable tasks | The PASS oracle: a minimal correct solution, laid out exactly like a submission overlay and mirroring **only** agent-writable prefixes. A stray root-level file (a `README`, a `.gitkeep`) lands outside the writable set and the run exits 4 SANDBOX-REJECT. |
| `discrimination/` | for validated tasks | One `<variant>/` submission overlay per anti-gaming concern, plus `MATRIX.md` — one row per submission giving the expected verdict and the NAMED assertion substring that must produce it. The reference row's first cell is `../reference`. |
| `ue-config/` | optional | Per-task UE `Config/*.ini` overlay fragments. Verifier-owned: the agent never sees or edits them, because `Config/` stays agent-denied. Each `<IniName>.ini` is **appended** onto the substrate's matching ini under a `; CraftBench per-task overlay: <task-id>` marker. UE's ini semantics (later-wins, `+Array` lines) make appending sufficient. Applied at workdir staging and reverted byte-identically after live-editor runs. Implementation: `tools/verify-single/config_overlay.py`. |
| anything else | no | Free-form. Tooling selects `*/task.md` and never `rglob("*.md")`, so notes and scratch files are ignored. |

## Task ids

CLI tools accept a bare `<task-id>` when it is unique across baskets, or a
basket-qualified `<basket>/<task-id>`, which always works and is required if an
id ever exists in two baskets. Run-artifact and backup names replace `/` with
`__`. Resolution lives in `tools/run-agent/aura_rig/tasks.py`; you can check one
with `python -m aura_rig.tasks resolve <id>`.

No task id may be a substring of another. The membership checks in
`tools/verify-single/inventory.py` match on raw substrings, so a prefix-shaped id
makes one task's row silently read as another's.

## The four directories

A task's directory says **what the agent writes**, never where the task came from.

| directory | tasks | the agent's deliverable |
|---|---:|---|
| `cpp/` | 33 | C++ source in the substrate's agent-writable module |
| `bp/` | 25 | A Blueprint, asset, or editor artifact — `.uasset`/`.umap`/editor-authored data. Includes every `L2I`-graded task |
| `python/` | 12 | The resulting **editor state** — assets, a saved level, a text report — from editor scripting. Graded by the same deterministic `L2I` lane as `bp/`. Note that no gate asserts "Python was used": these are outcome-graded, and Python is simply the natural way to hit the exactness and volume the prompts demand |
| `craftbench-public/` | 47 | Mixed. This one is keyed on **disclosure status**, not on deliverable — see below |

117 task specs in total.

### `craftbench-public/` is the open set

The other three directories say what the agent writes. This one says which tasks
are intended for publication, so the tree can distinguish open tasks from held-back
ones — a benchmark that cannot separate the two cannot reason about contamination
later. It is a deliberate exception, not a fourth basket; please do not "fix" it
back into the others.

It costs one thing, and there are two mandatory mitigations.

Because the path no longer tells you what the agent writes, an agent that writes to
the wrong module root exits 4 SANDBOX-REJECT — which reads as a harness fault rather
than a model failure. So:

- **Every spec states the deliverable root twice in agent-visible prose**: once in
  `## Prompt given to the agent`, and once as the first line of
  `## Workspace state pre-task`. Those two headings are exactly
  `tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`, so both reach the agent.
  There is deliberately **no** `deliverable_root:` front-matter key — it is not in
  `spec.py::_KNOWN_KEYS`, so a spec carrying one raises `ValueError` and exits 2.
- **Every spec's `substrate:` is `ThirdPerson`**, so the agent-writable module is
  `Source/ThirdPerson/`, never `Source/CraftBenchTemplate/`.

## The `-bp` variant convention

A task id ending in `-bp` is the Blueprint-deliverable twin of the task with the
same base id: identical behaviour spec, fixture logic and L2 gates, so C++ and
Blueprint results are directly comparable. What differs is that the prompt mandates
an asset-only Blueprint deliverable under `Content/Tasks/<id>-bp/`, and an
L2-introspect leg structurally gates that the deliverable really is a Blueprint —
a BP subclass of the scaffold actor under `/Game/Tasks/<id>-bp/`. Its C++ twin
carries a `-cpp` suffix. Each pair grades on the same substrate, map and shared
fixture; the two surfaces are equal-status deliverables.

## Which substrate a task uses

Gameplay tasks — anything involving a playable or possessed character — declare
`substrate: ThirdPerson`. The stock Third Person template ships the characters and
the animation set natively, so nothing has to be dropped into a minimal project and
every graded run stays human-reviewable. `CraftBenchTemplate` remains the substrate
for minimal scaffold-actor tasks.

## Map basenames must be globally unique

`tools/verify-single/map_locator.py` globs both `Content/Maps/<map>.umap` and
`Content/Maps/*/<map>.umap`, and raises `DuplicateMapBasenameError` — exit 7
HARNESS-ERROR, never a graded FAIL — as soon as two candidates exist. Putting maps
in per-task folders does **not** make a shared basename safe.

`cb lint` cannot catch this: `tasklint._check_map` reports clean once *any* tracked
copy exists. So every new spec's map basename has to be checked for uniqueness
across the whole repository by hand.

## The discrimination contract

For every runnable task the verifier must produce two distinguishable outcomes:

- the **empty** submission builds (L1 passes) but fails L2 **via the task's named
  assertion**, and
- `reference/` passes everything.

If that pair does not differ in that direction, the verifier is broken, and no
other result from that task can be trusted. A FAIL for the wrong reason is not
credited.

Grade one task's reference directly:

```sh
python tools/verify-single/run_task.py \
    --task tasks/<basket>/<id>/task.md \
    --submission tasks/<basket>/<id>/reference \
    --ue-root <path-to-UE_5.8>
```

Or run the whole set: `cb batch-eval --references all`.

## `CATALOG.md`

`tasks/CATALOG.md` is the per-task index — what each task evaluates and how the
verifier grades it, plus the full roster of every task id. It is hand-written
and **gated**: `tools/verify-single/inventory.py` (run by `cb lint`, which is
CI step 1) checks that every task on disk is named in it and that its
`N task specs` count matches `git ls-files`. Add your task's id when you add
the task, or CI fails.

There is no status column and no generator. Per-task evidence lives with the
task, in `discrimination/MATRIX.md`.
