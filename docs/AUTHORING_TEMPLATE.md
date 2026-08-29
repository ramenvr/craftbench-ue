# CraftBench Task Authoring Template

Read this template end-to-end before writing your first task, then use
it as a reference. This document is the spec-format law; its
end-to-end build companion (spec → scaffold → fixture → map →
reference → discrimination → gates → PR) is
[`TASK-AUTHOR-GUIDE.md`](TASK-AUTHOR-GUIDE.md).

> **Format: v2 front matter (the only format to write).** Every machine
> fact — id, substrate, layers, fixtures — lives in a **front-matter
> block** at the very top of `task.md`, not in an H2 section. THE parser
> is `tools/verify-single/spec.py::parse_task_file`; it also carries a
> **legacy H2 fallback** for un-migrated specs, but that path is
> read-only history. Never author a new task in it.
>
> Every front-matter example in this file is round-tripped through the
> real parser by `tools/verify-single/tests/test_docs_front_matter.py`,
> so anything you copy from here parses — and a block that stops parsing
> fails the suite instead of failing an author.

## What a CraftBench task is

A CraftBench task is a single, self-contained programming exercise for
an Unreal Engine agent under test. Each task lives in its own folder,
`tasks/<set>/<task_id>/`, whose spec file `task.md` specifies four
things: the behavior the agent must produce, the workspace state the
agent starts from, the verifier that decides pass/fail, and the
metadata that places the task in the benchmark's coverage matrix. The
task's reference solution (`reference/`), discrimination variants
(`discrimination/`), optional verifier-owned UE config overlay
fragments (`ue-config/`, append-applied to the substrate's `Config/`
at staging) are co-located in the same folder; the full layout contract lives
in `tasks/README.md`.

Two families of task exist:

- **Atomic** — probes a single Deliverable 1 concept (one
  `concept_id`). Forms the broad coverage layer.
- **Compositional** — probes the integration of 3-7 Deliverable 1
  concepts that real production work composes. Per Hard Rule #1,
  every compositional task cites an external production pattern.
  Forms the depth layer.

Both families share the same skeleton; compositional tasks add three
sections on top. One task per folder — the spec is always named
`task.md`, placed at `tasks/<set>/<task_id>/task.md`.

## Conventions

- **File and slug naming.** One folder per task; the spec file is
  always `task.md`, and the `task_id` metadata MUST equal the folder
  name (`tasks/<set>/<task_id>/task.md`). `task_id` is kebab-case
  ASCII, 3-60 chars, no spaces or uppercase. An optional 2-3 letter
  tier prefix is allowed (e.g. `t2-`). Name the behavior, not the
  implementation: `gas-stamina-regen` good, `uattributeset-subclass`
  bad.
- **Markdown structure.** Exactly one H1 per task (the title). Each
  template section is an H2 with the heading text fixed by this
  document — scripts join across files by H2 text. Subsections are
  H3. Code in fenced blocks with a language tag.
- **Linking to Deliverable 1 concepts.** Reference every concept by
  its `concept_id` slug from `tools/coverage/concepts.csv`,
  paired with the Epic doc URL from the same row:

  ```text
  - `anim-animation-montage` — Animation Montage
    (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-montage-in-unreal-engine)
  ```

  Per Hard Rule #4, cite public sources only. The `concept_id` is the
  internal join key; the Epic URL is the public anchor.

## Atomic task template

Use this structure for any task that probes a single primary concept.
Section order is normative; do not re-order, omit, or rename headings.

### Front matter (the machine facts)

The spec **opens** with a front-matter block: `---`, one `key: value`
per line, `---`. It replaces the old *Task ID and metadata*, *Verifier
layers used*, *Verifier fixtures* and *Verifier framerate legs* H2
sections — those were prose the parser had to scrape; these are typed
and validated.

```text
---
id: t2-gas-stamina-regen
substrate: CraftBenchTemplate
set: bp   # or cpp — the basket matching the agent-written surface
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_StaminaRegen :: AStaminaRegenFunctionalTest"]
---
```

**Grammar rules the parser enforces** (violations are a hard
`ValueError`, i.e. exit 2 "spec malformed" — never a graded FAIL):

- **Lists are INLINE only** — `layers: [L1, L2]`. A YAML-style list
  broken across lines (`fixtures:` then `  - "…"`) raises
  *"front matter line N is not 'key: value'"*. This is the single most
  common authoring mistake; it is also why every example here is
  machine-checked.
- **Unknown keys are rejected**, so a typo cannot silently do nothing.
  The full allowed set is: `id`, `substrate`, `set`, `tier`,
  `capability_bucket`, `category`, `deadline_s`, `action_budget`,
  `layers`, `fixtures`, `introspect`, `fps_legs`, `randomization`.
  (Note `deadline_s` — **not** `deadline_seconds`.)
- Blank lines and `#` comment lines inside the block are fine.

| Key | Required | Value |
|---|---|---|
| `id` | **yes** | kebab-case `[a-z0-9-]`, and it MUST equal the folder name |
| `layers` | **yes** | inline list from `L1 L2 L2I L3 ART R2` (implemented) + `L4 L5` (parse-only, unimplemented) |
| `fixtures` | **iff `L2`** | inline list of `"L_<Map> :: A<Name>FunctionalTest"`; declaring it without `L2` is an error, and `L2` without it is too |
| `introspect` | **iff `L2I`** | inline list of `.py` filenames under `tools/verify-single/introspect/` |
| `substrate` | no (default `CraftBenchTemplate`) | `CraftBenchTemplate` or `ThirdPerson` |
| `set` | no | the basket = the folder under `tasks/`: `bp` (Blueprint/asset/editor deliverable) or `cpp` (C++ source deliverable) — project decision 2026-08-11; see `tasks/README.md` |
| `tier` | no | `T0`–`T3` (see [Tier definitions](#tier-definitions)) |
| `capability_bucket` | no | see [Capability-bucket reminder](#capability-bucket-reminder) |
| `category` | no | coarse label: `gameplay` \| `materials-structural` \| `other` \| `lighting` \| `animation` \| `input`. **Has no consumer today** — parsed but never scored, so treat it as a label, not a gate |
| `fps_legs` | no | inline int list, e.g. `[60, 20]` — the same fixture re-run per `-FPS` rate, **all** must pass |
| `randomization` | no | inline kebab tokens naming per-run randomized inputs |
| `deadline_s` | no (default 600) | agent wall-clock budget, seconds |
| `action_budget` | no (default 30) | bounds multi-turn harness loops |

**Fixture naming.** The map must be a committed
`Content/Maps/<task-id>/L_<Map>.umap` binary — the only map source
(text scaffolders retired 2026-07; a missing binary is an explicit L2
FAIL and a `cb lint` error). The class is the C++ identifier the
verifier-only module declares, written **with** its `A` prefix here;
the runner strips it when building UE's automation filter string.

**Multiple fixtures** are how you split a multi-leg assertion so each
leg gets a fresh world (no cross-leg state leak) — the runner discovers
every fixture and runs them as one `RunTests A+B+C` invocation in a
single editor session:

```text
---
id: t2-timer-legs
layers: [L1, L2]
fixtures: ["L_TimerTask :: ATimerTaskFunctionalTest", "L_TimerTaskTeardown :: ATimerTaskTeardownFunctionalTest"]
---
```

**`fps_legs` vs multiple fixtures.** Use `fps_legs` when one fixture
works unchanged at every rate (it reads world game-time and asserts
absolute thresholds) — the common case, one fixture re-run as N
processes; declaring ≥2 rates closes the single-framerate gaming axis
(DD-9), because a frame-count overfit that lands on the right wall-time
at 60 Hz fires at the wrong time at 20 Hz and FAILs. Use distinct
fixtures only when a rate genuinely needs its own map or different
assertions. A task normally uses one mechanism or the other.

### H2: Primary concept

Exactly one `concept_id` from `concepts.csv`, the concept name, and
the Epic doc URL. Pick the single concept whose behavior the verifier
most directly checks. If you are torn between two, the task is
probably compositional.

```text
- `gas-attribute-set` — Attribute Sets
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)
```

### H2: Prompt given to the agent

One paragraph, 50-200 words, written as a behavior specification to a
senior gameplay programmer. Per Hard Rule #2, prompts are behavior-
only — observable contracts, not classes or patterns. See
[Prompt authoring guidance](#prompt-authoring-guidance).

```text
> Add a stamina resource to the player character. ...
```

### H2: Workspace state pre-task

The exact starting state before the agent runs: substrate baseline,
pre-existing files, content paths, partial implementations. The
verifier assumes this state.

Name the per-task files and content the agent starts with — not the
substrate (the front matter's `substrate:` decides that) and not the
engine version (repo-wide UE 5.8).

```text
Files that **exist** under `Source/CraftBenchTemplate/`:

- `Tasks/<task-id>/StaminaActor.h` / `.cpp` — declares
  `AStaminaActor : public AActor`; constructor adds
  `Tags.Add(FName("StaminaRoot"))`. **No behavior is implemented.**
- `Content/Maps/<task-id>/L_StaminaRegen.umap` — persistent level with
  the placed scaffold actor and the functional-test fixture.

Files that **do not exist**:

- No Blueprint subclass, no BeginPlay override. Solve in C++ on the
  existing class.
- No test source in the agent's writable path — the fixture lives in
  the `CraftBenchTests` module the agent can neither read nor modify.
```

### H2: Verifier specification

Per-layer assertions in pseudo-code or precise prose. Usually the
longest section. See
[Verifier specification format](#verifier-specification-format). Per
Hard Rule #3, L1-L4 plus L5 mechanical static checks gate the score;
L5 LLM judges are advisory only.

```text
- L1: build succeeds for both the <Module>Editor and <Module> (Game) targets
- L2: PIE-native ACraftBenchFunctionalTest <Test_StaminaRegen> ... (pseudo-code)
- L5: libclang asserts <UAttributeSet subclass exists> ...
```

### H2: Reference solution metadata

Three numbers describing the reference solution you wrote and
verified. The solution is not shipped; only its metadata is. See
[Reference-solution-metadata guidance](#reference-solution-metadata-guidance).

```text
- LOC range: 80-150 lines (additions across all files)
- Files touched: 4 (1 header, 1 cpp, 1 BP edit logged as text, 1 GE asset)
- Senior-dev hours: 1.5-2.5
```

### H2: Anti-gaming notes

3-5 gaming strategies you considered, one sentence each on the
verifier defense. See [Anti-gaming guidance](#anti-gaming-guidance).

```text
- Considered: agent returns a constant matching the asserted final
  value. Defense: L2 also asserts the mid-regen value at t=0.5s,
  which a constant return cannot satisfy.
- ...
```

### H2: Hidden invariants (optional, v1.0+)

Per the 2026-05-25 draft consumption clarification, tasks MAY declare
hidden invariants — assertion checkpoints kept in the verifier-only
module (`Source/<...>Tests/`) that the agent has no way to see. They
detect overfit to the visible assertions described in the **Verifier
specification** section. The prose summary lives here; the runnable
assertion lives under `Source/<...>Tests/`, which the agent cannot
reach: the runner materializes the graded substrate from **git HEAD**,
so an on-disk edit never reaches the grade, and human review
gates any committed change to it. (The old FR-011 hash
manifest and its exit-3 REJECT were retired 2026-07-16 — git-HEAD
provenance replaced them.)

```text
- The visible verifier asserts the stamina value at t=0 and t=1.0s.
  Hidden checkpoint at t=0.5s asserts the value lies on the expected
  regen curve — catches "skip mid, jump to asserted endpoint" gaming.
- The visible verifier asserts a single SpawnedChild at t=1.5s.
  Hidden checkpoint at t=4.0s asserts that NO additional children
  spawned after t=1.5s — catches "spawn-then-keep-spawning" gaming.
```

If the section is omitted, the task has no hidden invariants. v1.0
strongly encourages ≥ 1 hidden invariant for any task whose visible
verifier could be satisfied by a constant return or a single-point fit.

**Rollout pattern**: prove a hidden invariant on your own task's
`discrimination/` variants before relying on it — the variant that
targets the overfit must FAIL on the hidden checkpoint's named
assertion, which is exactly what `cb discriminate` reports. (The old
`tasks/canary/` internal-only rollout set was deleted 2026-07-08; git
history keeps it.)

### Materials structural-stage authoring (v1.0 materials category)

v1.0 ships materials tasks at the **structural stage only** (per
spec FR-020d, no LLM intervention). Assertions for materials tasks
draw exclusively from these deterministic introspection APIs:

- `unreal.MaterialEditingLibrary.get_num_material_expressions(mat)`
  — assert expression-count lower bounds.
- `unreal.MaterialEditingLibrary.get_material_parameter_names(mat,
  unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)` — assert
  exposed parameter names exist.
- `unreal.PythonMaterialLib.get_material_hlsl_code(mat)` — assert
  generated HLSL string contains (or does NOT contain) specific
  intrinsics, function calls, or scene-texture references.
- Material domain / blend mode introspection via standard `unreal`
  property reads.

Functional (FunctionalScreenshotTest at fixed timestamps) and Visual
(SSIM ≥ 0.92, LLM-judge fallback) stages are deferred to v1.x. v1.0
materials tasks MUST NOT depend on rendered output.

## Compositional task template

Compositional tasks use the same front matter and every H2 from the
atomic template, plus three extra H2 sections inserted at fixed
positions. Final order: **front matter**, Primary concept,
**Composed concepts**, **Production-pattern justification**,
**Concept-interaction notes**, Prompt given to the agent, Workspace
state pre-task, Verifier specification, Reference solution metadata,
Anti-gaming notes.

### H2: Composed concepts

3-7 `concept_id` entries from `concepts.csv` plus their Epic doc URLs.
The Primary concept is one of them but is repeated here. Per Hard
Rule #1, every compositional task cites at least 3 Deliverable 1
concepts.

```text
- `gas-ability-system-component` — Ability System Component (URL)
- `gas-gameplay-effect` — Gameplay Effects (URL)
- `gas-attribute-set` — Attribute Sets (URL)
- `ui-umg` — UMG (URL)
- `input-enhanced-input` — Enhanced Input (URL)
```

### H2: Production-pattern justification

One paragraph (50-150 words) citing a real public artifact that uses
this concept combination: a UE Marketplace plugin, a community
showcase, a GDC talk, or a documented studio practice. Per Hard Rule
#4, the citation is public; per Hard Rule #1, imagined combinations
are not acceptable.

```text
> The Marketplace plugin "GAS Companion" (listing URL) ships exactly
> this pairing of ability components, gameplay effects, and a stamina
> UI binding. ...
```

### H2: Concept-interaction notes

2-4 short paragraphs describing how the composed concepts interact at
the integration points the verifier actually checks. Name the cross-
system boundaries. Explain why no single concept's documentation alone
suffices.

```text
> The AttributeSet exposes a stamina float; the ASC routes
> GameplayEffect application to the set's PreAttributeChange. UMG
> binds via OnAttributeChanged ...
```

The remaining sections (Prompt given to the agent, Workspace state
pre-task, Verifier specification, Reference solution metadata,
Anti-gaming notes) follow the atomic definitions verbatim, and the
layers/fixtures a compositional task exercises are declared in its
front matter exactly as an atomic task's are.

## Prompt authoring guidance

The prompt is the only natural-language instruction the agent sees.
Per Hard Rule #2, prompts specify behavior. The agent chooses the
pattern; the verifier checks the behavior.

Write one paragraph, 50-200 words, addressed to a senior gameplay
programmer joining the project. State what must be true after the
work, observable from outside the implementation. Do not name
classes, functions, plugins, files, or directory paths unless they
are part of the starting workspace state (in which case they are
inputs, not instructions).

- **Acceptable**: gameplay terms (stamina, ability, ammo, damage),
  observable side effects ("the HUD shows X"), input contracts
  ("pressing K triggers B"), timing ("within N ms of E").
- **Unacceptable**: Unreal class names, plugin names, asset-type
  names, design-pattern names ("strategy", "observer"), and any
  phrase of the form "use the X system."

### Good vs bad: contrastive example

```text
GOOD (behavior-only):
> The player character has a stamina resource that drains while
> sprinting and regenerates while not sprinting. Stamina is in the
> range [0, 100] and starts at 100. While stamina is zero the
> character cannot sprint until stamina reaches at least 20. A HUD
> widget reflects the current stamina value.

BAD (implementation-leaky):
> Implement a stamina system using the Gameplay Ability System.
> Create a UAttributeSet subclass with a stamina attribute, apply a
> GameplayEffect-based regeneration on tick, and bind a UMG progress
> bar to OnAttributeChanged. Disable the sprint ability when stamina
> is zero.
```

The BAD prompt locks in a solution shape, reducing the task to
transcription. The GOOD prompt admits GAS, a plain
UCharacterMovementComponent extension, a component-on-pawn approach,
or any other valid pattern; the verifier checks observable behavior,
so all valid shapes pass.

## Verifier specification format

CraftBench verifiers run in five deterministic layers. Per Hard Rule
#3, L1-L4 plus L5's mechanical static checks gate the score; L5 LLM
judges are advisory only.

For each layer your task uses, write a subsection under **Verifier
specification** stating (a) the assertion(s) in pseudo-code or precise
prose and (b) the artifact that produces the signal (build log,
AFunctionalTest result, screenshot diff, Insights export, libclang
AST query). Cover exactly the layers named in the front matter's
`layers:` list — no more, no fewer.

### Pick a verification primitive — do not invent a verifier

Before writing any per-layer spec, pick a **reusable verification
primitive** that already covers your task's family. A primitive is a
proven (or planned) readback building block; the task space is covered
by ~9 of them. You write a thin per-fixture config against the chosen
primitive — you do **not** author a new verifier mechanism. The full
menu, per-archetype recipes, and honest proven-vs-spike status live in
[`pie-verification-playbook.md`](pie-verification-playbook.md);
the table below is the picker.

| Primitive | What it observes | Task family it covers |
|---|---|---|
| **beginplay-log-capture** | Substring/line count on a log category+verbosity, via a GLog `FOutputDevice` installed before BeginPlay | Sanity, "did/did-not log", "no stray Warning/Error on teardown" |
| **pie-checkpoint-sampling** | Actor state at fixed world-times via `SetCheckpointSchedule` + `OnCheckpoint(idx,t)` off `GetTimeSeconds` | Spawn timing, self-destruct, lerp/easing, traversal, transform/velocity over time |
| **timer-framerate-legs** | Same fixture run at two `-FPS` rates (e.g. 60/20) in independent PIE processes, each self-asserting absolute thresholds | Framerate-independence (anti-overfit for any timed behavior) |
| **pie-state-probe** (in-fixture) | Engine-owned runtime state read in-fixture after tag-resolve: `GetActorLocation`/`GetVelocity`, `MovementMode`, capsule, ASC tag/ability state | GAS arcs, movement-mode, "this state holds at sample t" |
| **L2-introspect** (editor-python) | Static asset/graph structure via `unreal.load_asset` reflection, headless, read-only: AnimBP graph, Material params/HLSL, `WidgetTree`, DataTables, gameplay tags | Materials (structural stage), AnimBP structure, widget tree, data-asset shape |
| **log-assertion** | On-disk `Saved/Logs/*.log` substring/sequence assertions (vs in-PIE GLog) | Sequenced log output, absence assertions across a batch |
| **overlap-probe** / **spatial-instance-readback** | Overlap-delegate firing; per-instance ISM transforms via `GetInstanceTransform`/`GetInstanceCount`; recorded `FVector` vs static bounds | Trigger volumes, attach/contact points, PCG/ISM scatter footprint |
| **save-roundtrip** | `DoesSaveGameExist`/`LoadGameFromSlot` in-fixture, disk-path + content compare after wiping in-memory state | Save/load persistence, per-identity slot isolation |
| **profiler (CSV)** | Wall-clock game-thread frame time to `Saved/Profiling/*.csv` | Performance — **R2-advisory only, never gates** (see rigor spectrum) |
| **R2 advisory-judge** | Deterministic evidence + agent prose handed to an evidence-grounded judge (model ≠ agent's) | Design quality, visual fidelity, diagnosis/explanation prose — **never gates** |

The synchronous-matrix shape (a fixture that spawns its own subjects,
invokes the agent's behavior, and asserts the result in one
`StartTest`/`FinishTest` with no ticking) is the cheapest realization
of `pie-state-probe`/`overlap-probe` and is the recommended default for
any task with no time evolution.

### Rigor: gating gate vs R2 advisory

Every assertion is either **gating** (contributes to the certified
PASS/FAIL) or **advisory** (annotates, never flips it). Per Hard Rule
#3 and spec FR-020d, only deterministic facts gate the score:

- **Gating — deterministic certified gate.** A binary/numeric/threshold-bearing
  fact, reproducible across same-machine reruns, drawn only from
  FR-020d's allowed signals (build-tool exit code, `AFunctionalTest`
  outcome, Python-introspection equality, hash equality, AST
  predicate). Examples: a transform hits `f(t)` within tolerance, a
  brush ResourceObject matches, two save slots are distinct files with
  isolated contents, 9/9 attach pairs satisfy `ok == expected` with
  zero stray logs. A non-reproducible result is **INDETERMINATE**,
  never a silent pass/fail. Produced by the gating layers (L1 / L2 / L2I).
- **R2 — advisory, NON-GATING.** Picks up the genuine residue and
  never flips pass/fail: "is this idiomatic/well-architected", visual
  fidelity (does it *look* right — `-nullrhi` uploads no pixels),
  diagnosis/explanation prose, and "is it faster" (wall-clock perf is
  refuted from the gate). Lives in the non-gating `R2` layer; its output
  attaches as a labelled, advisory-only sibling, excluded from the
  pass/fail computation. The R2 judge model **must differ** from the
  agent-under-test's model (anti-circularity).

> **Terminology (2026-06-02):** the old `R0/R1/R3` rigor tiers are
> retired. The certified-vs-advisory line is the layer's **`gating`**
> bool; **"R2"** is just the *name* of the advisory judge track, not a
> tier in a spectrum. Whether a gate truly discriminates the concept
> (the old "R1") is the **discrimination check** (FR-017) — see the
> paragraph below. Canonical definitions live in the root `CONTEXT.md`.

A gate must discriminate the **concept**, not a sanitized proxy: if a
single fixed reference point lets a hardcoded literal or a
wrong-mechanism solution pass, harden it (a second obstacle,
per-run-randomized geometry, an extra leg that tracks the causal
trigger) before claiming concept-discrimination, or relabel the task
honestly for the weaker property it actually tests. This is the
verifier-side complement of the **Anti-gaming notes** section.

### L1 — Build

Use on every task. L1 is the floor — no later layer runs if the
project does not build. Treat a green build as a precondition, not a
correctness signal.

```text
assert: UnrealBuildTool exits 0 for BOTH the <Module>Editor and
        <Module> (Game) targets (short-circuits on the first failure)
assert: no new "shadowed-variable" or "deprecated-declarations"
        warnings in the agent-touched compilation unit
```

Pitfalls: do not assert "zero warnings overall" — substrate baseline
warnings will fail every task. Pin warning asserts to agent-authored
files only.

### L2 — AFunctionalTest behavioral trace (PIE-native)

Use when the pass condition is observable runtime behavior — input
drives output, state changes over time, a delegate fires. The
workhorse layer for atomic and most compositional tasks. Author a C++
subclass of `ACraftBenchFunctionalTest` (not raw `AFunctionalTest`) in
the substrate's verifier-only module; the verifier discovers it by
class name and runs it in a **real PIE world**, not Editor World.

**The PIE-native fixture model is the only correct pattern.** L2
fixtures derive from `ACraftBenchFunctionalTest`
(`Source/CraftBenchTests/CraftBenchFunctionalTest.{h,cpp}`), which
overrides `IsEditorOnlyLoadedInPIE() -> true`. Because the test runs
in PIE:

- **`BeginPlay` auto-fires** on placed actors before `PrepareTest`
  runs. **Never call `DispatchBeginPlay` / `World->BeginPlay()`** — it
  has already happened.
- **The engine ticks the fixture and the world every frame.** **Never
  call `World->Tick(...)` or `Actor->Tick(...)` from a fixture** —
  fixture code executes *inside* the engine's in-progress world tick,
  so any re-entrant `World->Tick` trips an assertion
  (`TickTaskManager.cpp:1097`) and crashes the run.
- **`FTimerManager` ticks for real in PIE** (it did not in Editor
  World). Tasks whose verifier or solution depend on timers are no
  longer blocked.

Observe behavior over time the engine-driven way: call
`SetCheckpointSchedule({t0, t1, …})` (ascending seconds since
`StartTest`) in the constructor, then override `OnCheckpoint(Index, T)`
to sample state at each crossed checkpoint. The base class accumulates
elapsed time off `GetWorld()->GetTimeSeconds()` and calls your
`OnCheckpoint` from its own `Tick`; you read the freshly-updated time
and assert — you never advance the clock yourself.

For **synchronous** tasks (no time evolution — a one-shot computation,
an attach matrix, a static-structure assertion), a fixture may override
`StartTest()`, do all its work, and call `FinishTest()` in one shot —
**as long as it never ticks the world.** No checkpoint schedule is
needed. Such a fixture may also **spawn its own subjects** in
`PrepareTest`/`StartTest`, so only the fixture itself needs to be
placed in a map (see Identity and determinism below).

```text
// pseudo-ACraftBenchFunctionalTest  (checkpoint-sampling, async-over-time)
ctor():
  SetCheckpointSchedule({ 0.5, 1.5, 2.5, 3.5 })   // seconds of WORLD game-time

PrepareTest():
  Super::PrepareTest()                            // base sets fixed timestep
  GetAllActorsWithTag(World, "TaskRoot", Found)   // identity by TAG, never class
  assert Found.Num() == 1; TargetActor = Found[0]
  // NO DispatchBeginPlay — PIE already fired it.

OnCheckpoint(Index, T):                           // base calls this per checkpoint
  sample TargetActor state at T -> AssertValue_*  // NEVER World->Tick here
  // base calls FinishTest(Default) after the last checkpoint
```

```text
// pseudo-ACraftBenchFunctionalTest  (synchronous, no time evolution)
StartTest():
  spawn N subject actors with tags         // fixture supplies its own subjects
  for each: invoke the agent's behavior, read the resulting state
  AssertTrue(observed == expected, ...)
  FinishTest(Succeeded/Failed, ...)        // one shot; never ticks the world
```

**Identity and determinism (mandatory):**

- **Identity by tag, never by class.** Resolve subjects via
  `UGameplayStatics::GetAllActorsWithTag`, not by C++ class — the agent
  is allowed to subclass the substrate actor, and class-based lookup
  would penalize a valid solution.
- **Fixed-timestep determinism is owned by the base.**
  `ACraftBenchFunctionalTest::PrepareTest` sets
  `FApp::SetUseFixedTimeStep(true)` + `SetFixedDeltaTime` and the
  runner passes `-deterministic -FPS=<rate>`, so each frame's delta is
  exact and checkpoints land on the same frame every run. Do **not**
  re-implement this in a subclass (see the base-class note in the repo conventions)
  and do **not** use `t.MaxFPS` (a wall-clock limiter, not
  deterministic).

Pitfalls: do not assert end-state only when a constant could satisfy
it — sample at two checkpoints or assert a rate of change. Do not rely
on wall-clock latent commands (`FDelayedFunctionLatentCommand` gates on
`FPlatformTime::Seconds`, not the fixed-step world clock) as the
checkpoint clock. **BeginPlay-window log capture is the one thing PIE
breaks**: since BeginPlay fires before `PrepareTest`, install a GLog
`FOutputDevice` from a pre-BeginPlay hook
(`FWorldDelegates::OnWorldInitializedActors`) — or have the substrate
actor record state in its own BeginPlay and assert that at a
checkpoint. See
[`pie-verification-playbook.md`](pie-verification-playbook.md)
for the full base-class contract and recipes (the original
pattern doc was deleted with the specs tree; git history).

#### Multi-leg L2 tests

When a single behavioral assertion needs **multiple independent
contexts** (different framerates, different teardown timing, different
input sequences), split the assertion into one
`ACraftBenchFunctionalTest` subclass per context and enumerate them in
the front matter's `fixtures:` list. Reasons to prefer this pattern
over multiple legs in one fixture:

- **A single fixture can only call `FinishTest` once.** An
  early-teardown leg that needs `RequestEndPlayMap` cannot also report
  a result from the same fixture; the two lifecycles are mutually
  exclusive.
- **PIE-world state leaks across legs within one fixture.** Destroyed
  actors stay destroyed, GLog devices stay bound, GC roots persist,
  `UGameInstance` keeps state. Subsystem-cache anti-gaming defenses
  fail silently. Mid-run `FApp::SetFixedDeltaTime` changes also do not
  cleanly "take" within one continuous tick stream — distinct
  framerate legs MUST be distinct fixtures.
- **A fresh PIE world per leg is free isolation.** UE's automation
  framework loads each fixture's map and brings up a fresh PIE world
  before running its test; state starts clean each time.

Cost: ~5-15s per additional map load (warm editor) in the L2
wallclock. The verifier runs all fixtures in one editor session via
`RunTests A+B+C`, each opening its own PIE world, so cold-start is paid
once.

### L3 — AScreenshotFunctionalTest plus structural predicates

Use when the pass condition includes a visible artifact — a UMG
widget renders, a particle spawns, a material parameter changes. The
screenshot diff catches rendered output; the structural predicates
(asserted in the same test class) catch the underlying scene state so
the verifier does not depend on pixel-perfect equality alone.

```text
// pseudo-AScreenshotFunctionalTest
RunTest():
  apply 50 stamina-damage GE to player
  wait one frame for UMG repaint
  TakeScreenshot("stamina_half.png")
  assert SSIM(captured, reference) >= 0.95
  assert: world contains exactly one widget of class W_StaminaBar
  assert: W_StaminaBar.Percent within [0.45, 0.55]
```

Pitfalls: screenshots break on driver and platform variance. Always
back a screenshot with a structural predicate. Prefer SSIM with a
generous threshold over exact pixel match. Do not screenshot moving
content without a deterministic seed.

### L4 — Unreal Insights trace export

Use when the pass condition is a performance or timing property —
frame budget, async load latency, replication bandwidth, cook time,
memory ceiling. Run the agent's build with `-trace=` enabled, export
`.utrace` plus a CSV slice, assert against the CSV.

```text
trace_session = run("-trace=cpu,memory,loadtime", duration=10s)
csv = export(trace_session, "LoadTimeProfiler")
assert: row count for "AsyncLoad <StaminaWidget>" >= 1
assert: max LoadTime < 50ms across all rows for that asset
```

Pitfalls: traces are noisy — assert percentiles or maxima, not single
values. Always specify the trace channel set; omitting a channel
silently drops the asserted-on event.

### L5 — libclang static checks

Use when the pass condition includes a code-shape property that
cannot be inferred from runtime behavior alone — "uses replication",
"marks a UPROPERTY with Replicated", "subclasses UAttributeSet",
"does not call deprecated API X." Run libclang on the post-task
source tree, walk the AST, assert.

```text
// pseudo-libclang
tu = parse(agent_added_files, include_paths=project.includes)
classes = ast.classes_deriving_from("UAttributeSet")
assert: len(classes) >= 1
properties = classes[0].fields_with_attribute("Replicated")
assert: "Health" in [p.name for p in properties]
```

Pitfalls: libclang asserts shape, not correctness — a class can
derive from `UAttributeSet` and still be wrong. Pair every L5
mechanical assertion with an L2 behavioral assertion when feasible.
**L5 LLM judges, if present, are advisory only and never gate the
score (Hard Rule #3).** Label any LLM output `l5_advisory_notes` and
exclude it from pass/fail computation.

## Anti-gaming guidance

Gaming is the failure mode where the agent passes the verifier without
exhibiting the intended behavior. **Anti-gaming notes** is a pre-mortem
for the verifier. Consider these generic failure modes, note which
apply to your task, and record the verifier defense for each:

- **Constant return.** Agent returns a hardcoded value matching the
  asserted value at the asserted time.
- **Single-point fit.** Verifier samples one moment; agent fits that
  moment without implementing the process.
- **Wrong-path success.** Agent produces the asserted output through
  a different mechanism than the prompt implies. For pure-behavior
  tasks this is acceptable; for tasks with an implicit shape, add a
  paired L5 static check.
- **Test disabling.** Agent edits the verifier test class to suppress
  the assertion. Defense: verifier files live outside the agent's
  writable root; the runner re-applies them per evaluation.
- **Magic-number mutation.** Agent flips one literal in pre-existing
  code instead of touching the intended subsystem. Defense: assert at
  multiple inputs or assert the code-shape via L5.
- **Mock substitution.** Agent stubs the called subsystem with a no-op
  that satisfies the contract. Defense: assert on a downstream side
  effect the stub cannot produce.
- **Time/frame coupling.** Agent passes only at one framerate.
  Defense: assert rate-of-change, not per-frame deltas.
- **Asset-only solution.** Agent edits an asset rather than writing
  code, passing a behavior test that does not require code. Defense
  (for code tasks): add an L5 source-level assertion.

Record at least 3-5 of these (the ones that actually threaten your
task) plus the verifier defense for each.

## Reference-solution-metadata guidance

Write a reference solution to verify your task is feasible and to
calibrate difficulty. The reference solution itself is **not** part of
the task spec and is not published; only these three metadata fields
ship with the task.

- **LOC range.** Net new lines added (deletions excluded) as a low-
  high range, agent-authored delta only. Typical T1: 20-80 LOC; T3
  compositional: 300-800 LOC.
- **Files touched.** Count of distinct files modified or created.
  Include `.h`, `.cpp`, `.uproject`, build descriptors, and asset
  files saved as text. Exclude generated `.generated.h`.
- **Senior-dev hours.** Wall-clock hours a fluent UE5 gameplay
  programmer would take, as a range. Calibrate from your own reference
  solution time, adjusted for your slowdown factor.

A "T1" reference solution that takes six hours is mis-tiered. Under-
counting biases the benchmark; be honest.

## Substrate decision

Two substrates exist, both UE 5.8, both carrying the same verifier-only
`CraftBenchTests` module. Set `substrate:` in the front matter; omitting
it means `CraftBenchTemplate`.

| `substrate:` | On disk | Agent-writable module | Pick it when |
|---|---|---|---|
| `ThirdPerson` | `UE-projects/ThirdPerson/` | `Source/ThirdPerson/` | Normally. The stock UE 5.8 Third Person C++ template: a pre-built `ACharacter` with `CharacterMovement`, Enhanced Input mappings and an anim blueprint — so the graded behaviour can be driven through the same input path a player uses. 97 of the 117 shipped specs use it. |
| `CraftBenchTemplate` (parser default) | `UE-projects/CraftBenchTemplate/` | `Source/CraftBenchTemplate/` | When the task wants a bare stage and no character: a minimal C++ scaffold with per-task actor pairs, nothing incidental for an agent to lean on. 20 shipped specs use it. Note it is what the parser assumes when `substrate:` is omitted, so declare the key explicitly either way. |

Pick `ThirdPerson` unless the task genuinely wants no character at
all. Be aware of what that costs: everything a richer substrate
provides is also something the agent can accidentally satisfy the
assertion with, so the discrimination bar goes up — budget for the
extra anti-gaming variants rather than being surprised by them.

Whichever you pick, the front matter is the ONLY place that decides —
the runner resolves the substrate, the sandbox's writable prefixes, and
the fixture module from it. Don't restate it as prose in *Workspace
state pre-task* and risk the two disagreeing; describe there only the
per-task files and content the agent starts with.

> **Lyra.** Earlier drafts of this template offered `substrate: lyra`.
> There is no Lyra substrate in the repo and never was one on disk;
> `CraftBenchTemplate` and `ThirdPerson` are the two real choices. If a
> task truly needs Lyra, that is a substrate-maintainer conversation
> (a new `UE-projects/<name>/` + `AGENT_WRITABLE.json` + its own
> `CraftBenchTests` module), not a spec key you can just set.

## Tier definitions

Tier is a coarse difficulty axis aligned to the kind of agent
capability the task probes. Released distribution target: T0=2, T1=8,
T2=11, T3=4.

### T0 — Trivial sanity

Under 20 minutes for a fluent UE5 gameplay programmer. Probes basic
workspace literacy: find a file, edit a line, rebuild. Pass rate
among competent agents approaches 100%. Use T0 to detect tooling
regressions, not reasoning.

### T1 — Single-concept exercise

Atomic task that exercises one Deliverable 1 concept end-to-end.
Senior-dev time: 30 minutes to 2 hours. Most atomic tasks live here.

### T2 — Concept plus integration

A non-trivial atomic concept that touches an adjacent subsystem, or a
small compositional task. Senior-dev time: 2-6 hours. The agent must
make at least one non-obvious design decision.

### T3 — Cross-system production work

Compositional task integrating 4-7 concepts the way a shipped feature
does. Senior-dev time: 8-24 hours. Production-pattern justification is
mandatory; references to a real shipped feature make a T3 task
credible.

## Capability-bucket reminder

Place every task in exactly one of the six v2.1 buckets. Counts below
are the in-scope Deliverable 1 concept supply per bucket:

- **Gameplay Programming** (101): runtime gameplay — characters,
  abilities, AI, input, replication, gameplay state.
- **Technical Art** (59): art-programming seam — animation graph,
  materials, render parameters driven from gameplay.
- **Tools & Pipeline** (32): editor automation, build pipeline,
  automation framework, cook and packaging.
- **Content Integration** (9): asset and data ingestion — data
  tables, soft references, asset registry, gameplay tags as data.
- **Debug & Refactoring** (32): profilers, Insights, stat commands,
  log and assertion macros, deprecation API.
- **Architecture & Systems** (48): cross-cutting frameworks —
  subsystems, modules, plugin interfaces, replication graph, online
  subsystems, save game.

A task that legitimately spans buckets is filed under the bucket of
its **Primary concept**.

## Worked example: atomic task

### Front matter

Three fixtures because the behavior needs three independent contexts
(two framerates + an early-teardown leg), and per the rule above
distinct framerate legs MUST be distinct fixtures when a leg also needs
its own lifecycle:

```text
---
id: gp-timer-delayed-destroy
substrate: CraftBenchTemplate
set: bp   # or cpp — the basket matching the agent-written surface
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TimerTask60 :: ATimerTask60HzFunctionalTest", "L_TimerTask20 :: ATimerTask20HzFunctionalTest", "L_TimerTaskTeardown :: ATimerTaskTeardownFunctionalTest"]
---
```

Expected duration (30-60 minutes for a senior dev) is a tiering
judgement, not a spec key — it belongs in the tier rationale, and the
engine version is repo-wide (UE 5.8), never per task.

### Primary concept

- **concept_id**: `ps-timers`
- **concept_name**: Gameplay Timers (FTimerManager API)
- **doc_url**: https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine
- **doc_section**: Programming and Scripting
- **weight_tier**: `high`
- **Why this concept exercises it**: The prompt's success criterion — one-shot callback that fires once at a specified duration, framerate-independent — matches what the gameplay timer subsystem guarantees and what an ad-hoc tick accumulator does not.

### Prompt given to the agent

> You are working in a small Unreal Engine 5.8 C++ project. The project contains an empty actor type placed in the level via the Outliner. We need this actor to remove itself from the world automatically, exactly **1.5 seconds** after gameplay begins. The 1.5-second delay must be respected regardless of frame rate — running at 20 FPS or 240 FPS must not change when the actor disappears. After the delay elapses, the actor should no longer be present. If gameplay ends before 1.5 seconds elapse (e.g., the level is torn down early), the actor must not fire a stray removal on a half-destroyed world. Wire the behavior end-to-end so that placing this actor in any level produces the described effect with no additional setup.

(Behavior-only; the agent chooses the pattern.)

### Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames` already includes `Core`, `CoreUObject`, `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `TaskActor.h` / `TaskActor.cpp` — declares and defines `class ATaskActor : public AActor`. Constructor sets `PrimaryActorTick.bCanEverTick = false;` and adds the public static `FName TaskRootTag = TEXT("TaskRoot")` to `Tags`. No lifecycle overrides are present.
- `Content/Maps/gp-timer-delayed-destroy/L_TimerTask60.umap` / `L_TimerTask20.umap` / `L_TimerTaskTeardown.umap` — three persistent levels, each with one placed `ATaskActor` (tagged `TaskRoot`) and one placed `ACraftBenchFunctionalTest`-derived fixture (one per leg). Each is a committed binary `.umap`; the agent does not author maps.

Files that **do not exist**:

- No `FTimerHandle` member, no `BeginPlay` override, no Blueprint subclass of `ATaskActor`. Solve in C++ on the existing class.
- No test source in the agent's writable path. `FTimerTaskFunctionalTest` lives in a separate `CraftBenchTests` module the agent cannot read or modify.

### Why these layers

`layers: [L1, L2]`. L1 confirms the edit compiles; L2 confirms behavior
under deterministic fixed-timestep PIE across two framerate legs plus a
teardown leg. L2I/L3 are not used — no asset structure to introspect and
no rendering assertion — and no LLM sits in the gate at all (FR-020d).

### Verifier specification

The behavior is split across **three PIE-native fixtures** (the
`timer-framerate-legs` primitive) so each leg runs in a fresh PIE world
at its own `-FPS` rate — no cross-leg state leak, no mid-run global
mutation. None of them ticks the world: each derives from
`ACraftBenchFunctionalTest`, samples actor presence at a checkpoint
schedule clocked off `GetTimeSeconds`, and lets the engine drive the
clock. The actor's own `FTimerManager` fires for real under the PIE
clock.

```text
// Leg 1 — timing accuracy at 60 Hz (map L_TimerTask60, FixedDt = 1/60)
ATimerTask60HzFunctionalTest::ctor():
    SetCheckpointSchedule({ 1.45, 1.55 })          // seconds of WORLD game-time

ATimerTask60HzFunctionalTest::PrepareTest():
    Super::PrepareTest()                           // base sets fixed timestep
    // Identity by project tag, never by C++ class name — the agent may
    // legitimately rename/subclass ATaskActor.
    GetAllActorsWithTag(World, "TaskRoot", Found)
    AssertValue_Int(Found.Num(), Equal_To, 1, "Exactly one TaskRoot at start")
    // NO DispatchBeginPlay — PIE fired BeginPlay before PrepareTest ran,
    // arming the actor's one-shot timer.

ATimerTask60HzFunctionalTest::OnCheckpoint(Index, T):
    if Index == 0:   // t = 1.45s, 50ms before deadline
        AssertEqual_Int(CountActorsWithTag(World, "TaskRoot"), 1,
                        "Actor present 50ms before deadline")
    if Index == 1:   // t = 1.55s, 50ms after deadline
        AssertEqual_Int(CountActorsWithTag(World, "TaskRoot"), 0,
                        "No TaskRoot remains after 1.55s")
    // base calls FinishTest(Default) after the last checkpoint

// Leg 2 — framerate independence at 20 Hz (map L_TimerTask20, FixedDt = 1/20)
ATimerTask20HzFunctionalTest::ctor():  SetCheckpointSchedule({ 1.6 })
    OnCheckpoint(0, 1.6): AssertEqual_Int(CountActorsWithTag(World,"TaskRoot"), 0,
                                          "Removed at 20 FPS too")

// Leg 3 — clean teardown before deadline (map L_TimerTaskTeardown)
ATimerTaskTeardownFunctionalTest:
    // Install Warning|Error GLog FOutputDevice from a pre-BeginPlay hook
    // (OnWorldInitializedActors); let PIE tick to ~0.5s, then RequestEndPlayMap.
    // Assert zero stray timer callbacks fired on the torn-down world.
```

All three legs are enumerated in the front-matter `fixtures:` list
(`L_TimerTask60 :: ATimerTask60HzFunctionalTest`, etc.) — see this
example's own front matter above; there is nothing to add here. There is
no `## Verifier fixtures` H2 in v2: the front-matter key replaced it, and
`spec.py` reaches the H2 only through `_parse_legacy`. The runner runs
the legs as one `RunTests A+B+C` invocation, each in its own PIE world.

**Pass criteria**: all three legs green. **Timing tolerance**: ±50 ms
around 1.5 s (encoded by the 1.45/1.55 checkpoints). **Robust
identity**: lookup by the `TaskRoot` tag, never by class name —
renaming or subclassing `ATaskActor` does not penalize the agent.

### Reference solution metadata

- **LOC range**: 15-45 LOC (3x band; `SetTimer` with a UFunction name and an `FTimerDelegate::CreateLambda` dispatch differ by several lines).
- **Files touched**: 1 `.h` + 1 `.cpp` (extending the existing `TaskActor` pair). No new files, no `.uasset` edits, no `.Build.cs` edits.
- **Senior-dev time**: 30-60 minutes including reading prompt, picking pattern, local verification.
- The reference solution itself lives in an integrator-owned path and is **not** included here.

### Anti-gaming notes

1. **Hardcoded synchronous destroy.** *Failure mode*: agent calls `Destroy()` directly from `BeginPlay` or `Tick`, banking on a fixed dt. *Defense*: Leg 2 runs in its own PIE world at `FixedDt = 1/20 s`; a tick-count or sleep-based solution either fires far too early or never fires.
2. **Test-disabling.** *Failure mode*: agent edits the functional test to make it pass. *Defense*: `CraftBenchTests` lives outside the agent's writable workspace, is built by a separate CI target, and is graded from **git HEAD** — the runner materializes the substrate from HEAD, so an on-disk edit never reaches the grade, and human review gates any committed change to it. (Any tamper also appears as a diff outside permitted edit paths. The old FR-011 hash manifest and its exit-3 REJECT were retired 2026-07-16 — see the *Hidden invariants* note above; do not cite a hash check as the defense.)
3. **Wrong-actor identity shortcut.** *Failure mode*: agent spawns a second `ATaskActor` programmatically, hoping the verifier picks it. *Defense*: `PrepareTest` asserts exactly one `TaskRoot`-tagged actor exists at start, and the post-deadline checkpoint asserts zero remain — extras fail both ends.
4. **Stray callback after teardown.** *Failure mode*: agent uses an untracked timer handle, so when the map is torn down early the timer fires on a half-destroyed world and emits a "harmless" warning. *Defense*: Leg 3 runs in its own PIE world, calls `RequestEndPlayMap` before the deadline, and asserts zero Warning/Error log entries (via a pre-BeginPlay GLog device on `LogTemp`/`LogTimerManager`/`LogActor`) — the engine logs warnings for callbacks on destroyed worlds.
5. **60-Hz overfit.** *Failure mode*: agent uses a 90-tick counter (1.5 s at 60 Hz). *Defense*: the 20 FPS leg would fire at 4.5 s wall time; two independent PIE legs at distinct `FixedDt` convert "passes by luck" into "fails the second leg."

## Worked example: compositional task

### Front matter

```text
---
id: t3-inventory-pickup-drop-persistence
substrate: ThirdPerson
set: bp   # or cpp — the basket matching the agent-written surface
tier: T3
capability_bucket: Architecture & Systems
category: gameplay
layers: [L1, L2]
fixtures: ["L_InventoryPersistence :: AInventoryPersistenceFunctionalTest"]
---
```

`substrate: ThirdPerson` because this task genuinely needs the stock
template's character + Enhanced Input stack. Secondary capability
buckets (`Gameplay Programming`, `Content Integration`) and the
estimated senior-dev hours are tiering rationale for the body, not spec
keys — `capability_bucket` is a single value, filed under the **Primary
concept's** bucket.

Note what this example does NOT declare: L3/L4. The sections below were
drafted against a five-layer plan, and only L1/L2/L2I/L3 are
implemented today (L3 registered but wired by no shipping task; L4/L5
parse but do not run). Declaring `layers: [L1, L2, L3, L4]` would parse
and then quietly under-verify. **Declare only layers you have actually
wired a fixture for.**

### Primary concept

`ps-actors` (Actors) — https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine

The world-pickup and dropped-item entities are the load-bearing concept. Every other composed concept hangs off the lifecycle of an AActor: the data asset describes which actor to spawn, the soft reference defers its mesh load, the input action triggers pickup/drop on a specific actor, the save game serializes which actors existed and where, and the gameplay tag classifies the actor. If actor lifecycle is wrong (spawn/destroy ordering, BeginPlay timing) the whole composition fails regardless of how well the other pieces are implemented.

### Composed concepts

Six concepts (3-7 range satisfied). Five `high`-tier + one `medium`-tier (mix satisfied; the high-tier concepts dominate the critical path).

| concept_id | tier | doc_url | role |
|---|---|---|---|
| `ps-actors` | high | https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine | Primary. Pickup actor spawned/destroyed in response to interaction. |
| `saving-and-loading-your-game` | high | https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine | Persist inventory contents and dropped-item locations across level reload. |
| `ps-data-assets` | high | https://dev.epicgames.com/documentation/en-us/unreal-engine/data-assets-in-unreal-engine | Item definition (display name, mesh, tag). Decouples designer-tunable item params from the actor class. |
| `asynchronous-asset-loading` | medium | https://dev.epicgames.com/documentation/en-us/unreal-engine/asynchronous-asset-loading-in-unreal-engine | Item-definition mesh held as a soft reference; lazy-loaded when actually needed, not at definition load. |
| `enhanced-input` | high | https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine | One key picks up the looked-at item, another drops the most-recent item. |
| `gameplay-tags` | high | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-gameplay-tags-in-unreal-engine | Items carry `Item.Category.*` tags. The HUD test asserts category counts, which forces real tag composition. |

### Production-pattern justification

The "world pickup -> inventory slot -> drop back into world -> survives reload" flow has been a staple of Unreal Engine Marketplace inventory plugins for nearly a decade. Two public reference points ground the pattern:

1. **Ryan Laley's "Multiplayer Inventory System" tutorial series** on YouTube ([channel](https://www.youtube.com/@RyanLaley)) is one of the most-cited free Unreal-community references on inventory architecture. The series builds exactly this composition: an item Data Asset, an interaction trace, an Enhanced Input action for pickup, an inventory component, and a save-game pass that persists contents and world drops. The series is referenced repeatedly across `forums.unrealengine.com` and `r/unrealengine` inventory threads from 2023 onward as the de-facto starting point.

2. **The Unreal Engine Marketplace / Fab inventory category** ([Fab marketplace](https://www.fab.com/)) lists dozens of paid inventory plugins (e.g. "Inventory System Pro", "Advanced Inventory and Equipment System") that all converge on the same surface: a `UDataAsset`-derived item definition, soft references for visual content, Enhanced Input bindings the project supplies, a save/load entry point, and gameplay-tag-based categorization. The cross-plugin convergence is itself the evidence that this is real production practice.

This is explicitly **not** a Lyra citation. Lyra's `LyraInventoryItemDefinition` is one realization of the same shape, but the pattern predates Lyra and is reproduced independently in shipped marketplace products.

### Concept-interaction notes

The six concepts form a directed data flow with three hand-offs.

**Pickup -> inventory.** Player presses the pickup input action. The character runs a short trace (sphere or line; the trace surface itself is incidental), finds an actor implementing the pickup contract, reads its item-definition reference (soft pointer to a `UDataAsset`), resolves the definition, copies the relevant fields (definition path, count, category tag) into the inventory component's list, and destroys the world actor. The gameplay tag travels with the inventory entry, not the actor.

**Drop -> world.** Drop input pops the most-recent inventory entry, spawns a new pickup actor at the character's feet, and hands the soft definition reference to the spawned actor. The actor's BeginPlay (or a follow-on async-load call) is what triggers the mesh to resolve — not the spawn itself. Force-loading the mesh on the Game Thread inside `SpawnActor` defeats the soft-reference leg and L4 should flag the stall.

**Persist -> reload.** On `EndPlay` (or an explicit autosave hook) the system writes a save-game payload: (a) inventory contents as definition-path + count + tag tuples, and (b) world-drop list as definition-path + transform tuples. On level load, both are replayed; the level designer's `BP_PickupSpawnPoint` actors must consult the save state and **not** re-spawn already-picked-up items.

If `gameplay-tags` is dropped the HUD category assertion becomes unphrasable without naming internal item types; if `asynchronous-asset-loading` is dropped L4 fails; if `saving-and-loading-your-game` is dropped the persistence check collapses to an in-memory cache the agent can trivially satisfy.

### Prompt given to the agent

```text
The player is exploring a level containing several pickup items
placed by the level designer (each item is a mesh in the world).
The player should be able to:

  1. Press one key to pick up the pickup item they are looking at.
     The world actor for that item disappears, and the item joins
     the player's inventory.
  2. Press a different key to drop the most-recently-picked-up item
     at the player's feet. The dropped item appears as a world actor
     the player can pick up again.
  3. Quit the game and return: the inventory and any items dropped
     in the world must be exactly as the player left them.

Item content (display name, the mesh shown in the world, the item's
category — for example "Weapon" or "Consumable") is supplied by
the level designer as authored game-content assets; adding a new
kind of item must not require editing C++. Item visuals (meshes)
must not occupy memory until a pickup of that kind is actually
present in the level. The HUD should display a one-line readout
in the form "N items: W weapons, C consumables, ..." that updates
whenever the inventory changes.

Implement this on top of the provided third-person template.
```

(190 words; behavior-only. No class names, no plugin names, no framework-specific terminology — the agent must derive Data Assets, Save Game, soft references, Enhanced Input, gameplay tags, and Actor spawning from the description.)

### Workspace state pre-task

**Provided (scaffold the agent inherits):**

- Third-person C++ template project `CraftBenchInvTask` with default `BP_ThirdPersonCharacter`, `MainLevel.umap` + `PlayerStart`, and `BP_ThirdPersonGameMode`.
- Empty C++ class `UInventoryComponent : public UActorComponent` attached to the character. One stub function `void DebugPrint() const;` returning nothing; the rest is unimplemented.
- `IPickupSurface.h` declaring an empty `UPickupSurface` interface marker (no methods; the agent may use it or replace it).
- Three pre-authored static meshes in `/Content/Items/Meshes/` (sword, potion, coin).
- A `BP_PickupSpawnPoint` actor placed three times in the level with no logic — indicates where the level designer wants the three test items to appear.
- Enhanced Input plugin enabled in `.uproject`; empty `IMC_Default`, `IA_Pickup`, `IA_Drop` stubbed in `/Content/Input/`. The character does not consume them yet.
- `WBP_HUD` UMG widget with a `TextBlock` named `InventoryReadout` bound to a hardcoded `"0 items"` string; added to viewport by `BP_ThirdPersonCharacter::BeginPlay`.

**Not provided (agent must produce):** any item-definition asset type, any item-definition instances, any save-game class, any inventory state container, any pickup actor class, any `IA_Pickup` / `IA_Drop` wiring on the character, any inventory-state -> HUD update path, and any native gameplay-tag declarations for `Item.Category.*`.

### Why these layers

**L1 + L2**, per the front matter above.

Justification: L1 is mandatory (build must succeed and cook must not dangle on missing references). L2 is the core compositional check — drive Enhanced Input, observe world state, then reload.

> **Historical note.** The per-layer pseudo-code below still carries L3 and L4 legs from the original five-layer draft: an L3 HUD-readout assertion for the gameplay-tag composition, and an L4 frame-budget/residency probe for the soft-reference leg. Both remain good *ideas* and neither is wired today — L4 is not implemented in the runner at all. Kept as an illustration of layer reasoning; do not copy those two legs into a real spec's `layers:`.

### Verifier specification

Pseudo-code per layer. Behavior-only — no internal-API names appear in any assertion.

**L1 — compile + load**
```python
assert run("ubt build CraftBenchInvTask Win64 Development").exit == 0
assert run("UnrealEditor-Cmd CraftBenchInvTask.uproject -run=cook ...").exit == 0
# Compile passes; cook does not crash on missing references.
```

**L2 — functional gameplay (AFunctionalTest in PIE)**
```python
def test_pickup_drop_persistence():
    open_level("MainLevel")
    char    = get_player_character()
    pickups = find_actors_in_world(filter=is_pickup_like)
    assert len(pickups) == 3
    locs    = [p.transform.location for p in pickups]
    tags    = [pickup_tag(p)         for p in pickups]
    assert sorted(tags) == sorted([
        "Item.Category.Weapon",
        "Item.Category.Consumable",
        "Item.Category.Consumable"])

    # Pick up all three.
    for loc in locs:
        walk_to(loc); fire_input_action("IA_Pickup"); tick_frames(5)
        assert find_actor_at(loc) is None
    assert hud_readout_total_count() == 3

    # Drop the most recent at the character's current location.
    drop_loc = char.transform.location
    fire_input_action("IA_Drop"); tick_frames(5)
    dropped = find_actor_at(drop_loc, radius=100.0)
    assert dropped is not None
    assert pickup_tag(dropped) == tags[2]
    assert hud_readout_total_count() == 2

    # PERSISTENCE: reload (simulates quit + return; helper destroys
    # and respawns the GameInstance to defeat in-memory caching).
    reload_level("MainLevel", destroy_game_instance=True)
    pickups_after = find_actors_in_world(filter=is_pickup_like)
    assert len(pickups_after) == 1
    assert distance(pickups_after[0].transform.location, drop_loc) < 100.0
    assert hud_readout_total_count() == 2
```
Note: no `USaveGame`, `UDataAsset`, `TSoftObjectPtr`, `UInputAction`, or `FGameplayTag` name appears in the test.

The pseudo-helpers above (`tick_frames`, `walk_to`, `fire_input_action`, `reload_level`) are **behavior-level shorthand**, not a fixture API. In a real PIE-native fixture none of them is `World->Tick`: time advances by letting the engine tick between checkpoints (`SetCheckpointSchedule`/`OnCheckpoint`), and the `reload_level(..., destroy_game_instance=True)` semantics map to running the persistence assertion as a **separate fixture leg in a fresh PIE world** (the same pattern as the timer example's multi-leg split). Note also that live input injection (`walk_to`/`fire_input_action` on a possessed pawn) is a capability still on the roadmap — prefer a verifier-owned scripted-input timeline in the substrate base over live injection where the task allows it (see [`pie-verification-playbook.md`](pie-verification-playbook.md) §5).

**L3 — UMG state (per-category breakdown)**
```python
def test_hud_readout_categories():
    # 1 weapon + 2 consumables picked up:
    assert hud_readout_text() == "3 items: 1 weapons, 2 consumables"
    # after dropping 1 consumable:
    assert hud_readout_text() == "2 items: 1 weapons, 1 consumables"
```
This catches solutions that maintain a total count but never propagate per-category info — only a real gameplay-tag composition can satisfy it.

**L4 — async-load perf budget**
```python
def test_soft_reference_not_force_loaded():
    open_level("MainLevel")
    frame_times = capture_frame_times(during="level_open", count=10)
    assert max(frame_times) < 50.0  # ms
    # Meshes for items not in the level must not be in memory.
    assert mesh_residency("/Content/Items/Meshes/Mesh_LegendarySword") == "unloaded"
```

**L5 (advisory; never gates)**: an LLM judge scores the diff on style (naming, header organization, comment density), 0-3, advisory.

### Reference solution metadata

- **LOC range**: 240-360 lines of new C++ (excluding `.generated.h` content); plus 50-80 lines of Blueprint-graph equivalent or 0 if pure C++.
- **Files touched: 7-9**, typically:
  1. `InventoryComponent.h/.cpp` (filled in)
  2. `ItemDefinition.h/.cpp` (new `UDataAsset` subclass)
  3. `PickupActor.h/.cpp` (new `AActor` subclass)
  4. `InventorySaveGame.h/.cpp` (new `USaveGame` subclass)
  5. `CraftBenchInvTaskCharacter.cpp` (input wiring + interaction trace + drop spawn)
  6. `WBP_HUD` widget (binding `InventoryReadout` to inventory delegate)
  7. `IMC_Default`, `IA_Pickup`, `IA_Drop` (small input-asset edits)
  8. Optional `NativeGameplayTags.h/.cpp` for `Item.Category.*`
- **Senior-dev hours**: 2-4 hours, depending on whether the dev reuses an inventory-component pattern from muscle memory or composes it fresh.

### Anti-gaming notes

Five compositional failure modes the verifier and reviewer should catch:

1. **In-memory persistence shortcut.** Agent caches inventory state in a `UGameInstance` and never invokes `SaveGameToSlot`/`LoadGameFromSlot`. The L2 `reload_level(..., destroy_game_instance=True)` helper kills the GameInstance to defeat this; persistence only passes if a real save/load round-trips to disk.

2. **Hardcoded item types.** Agent enumerates `EItemType { Sword, Potion, Coin }` in C++ instead of driving content from a `UDataAsset`. The three seed items pass, but the prompt's "designer adds a new item without editing C++" is silently violated. A hidden follow-on stage adds a fourth Data Asset the agent never saw and re-runs the test; the new item must pick up and persist with zero code change.

3. **Hard reference defeats soft-load.** Agent declares `UPROPERTY() UStaticMesh* Mesh` instead of `TSoftObjectPtr<UStaticMesh>`. L2 and L3 still pass; L4 fails on the frame-time spike at level open and on the residency check for `Mesh_LegendarySword`.

4. **Magic-string HUD.** Agent satisfies L3 by hardcoding `"3 items: 1 weapons, 2 consumables"`. Mitigation: L3 includes a second post-drop assertion with different counts, and the hidden fourth-item stage produces a third distinct string — no single literal can satisfy all three.

5. **Drop bypasses inventory state.** Agent's drop handler spawns the pickup actor but doesn't remove the entry from the inventory (or removes it but never fires the HUD-update delegate). L2 step 4's `hud_readout_total_count() == 2` after the drop catches counts; reviewers should additionally inspect the delegate chain (a hand-set count value is a stage-2 review concern, not a verifier concern).

Two reviewer-only checks (not verifier-gated; weighted by the `Architecture & Systems` capability bucket):

- Does the pickup actor expose an interaction surface (interface or tag-based) future tasks can extend, or is detection baked in as `Cast<APickupActor>(Hit.GetActor())`?
- Does the gameplay-tag declaration use `UE_DEFINE_GAMEPLAY_TAG` (native registry) or string-equality on `FName`s? Both pass L3; the latter is a known-poor pattern the L5 advisory layer should flag.
