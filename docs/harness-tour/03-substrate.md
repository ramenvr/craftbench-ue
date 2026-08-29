# 03 — The Substrate (`UE-projects/CraftBenchTemplate`)

> Teaching-tour section. Audience: someone learning the system end-to-end.
> Everything below is grounded in the files as they stood on the project mainline
> as of 2026-06-20. Path references are `file:line` and are accurate at time of writing;
> line numbers drift, so treat them as "open this file and look near here".
>
> **⚠ Dated snapshot — three mechanisms described below have since retired:**
> (1) the **hash manifest** (`verifier_hashes.json`, `--regen-verifier-hashes`,
> the exit-3 REJECT) retired 2026-07-16 — verifier-module integrity is now
> **git-HEAD provenance** (the runner materializes the graded substrate from
> git HEAD; on-disk edits never reach the grade) + **human review** on
> committed `CraftBenchTests` changes; (2) the **map scaffolders**
> (`Tools/scaffold_L_*.py` + the runner's `scaffold_map.py`) retired 2026-07 —
> committed binaries are the only map source and a missing binary is an
> explicit L2 FAIL; (3) the multi-fixture exemplar task `gp-gas-launch`
> retired 2026-07-21 — the multi-fixture mechanism (§7) is unchanged and keeps
> synthetic test coverage, but no shipping task uses it. Read those sections
> as history; the current law lives in the repo conventions and
> `docs/TASK-AUTHOR-GUIDE.md`.

---

## 1. Purpose — what the substrate *is*

The substrate is the single UE 5.8 project that every CraftBench task is graded
against. It is **engine-version-pinned (`EngineAssociation: "5.8"`,
`CraftBenchTemplate.uproject:3`)** and **substrate-pinned** — there is exactly one
project, `CraftBenchTemplate`, and all tasks (so far) share it. An agent never sees
the whole project; the runner overlays the agent's submission onto a clean copy,
runs the verifier layers, and throws the copy away.

The whole design rests on one split that everything else serves:

- **`Source/CraftBenchTemplate/`** — the **agent-writable runtime module**. The
  agent edits *only* here (plus a carve-out under `Content/`). Holds the base
  actors/pawn the agent extends to produce the asked-for behavior.
- **`Source/CraftBenchTests/`** — the **verifier-only editor module**. Holds the
  `AFunctionalTest` fixtures that *observe* the agent's behavior and decide
  PASS/FAIL. The agent cannot write here, and is hash-pinned so it cannot be edited
  even by accident; if it changes, the submission is rejected before any build runs.

This split is the anti-gaming spine: the thing being measured (agent code) and the
thing doing the measuring (fixtures) live in different modules with different
permissions, and gameplay code physically cannot link against the fixtures (see
§4.3, the `Editor`-type module).

The two `.uproject` modules confirm the split and their load types
(`CraftBenchTemplate.uproject:6-29`): `CraftBenchTemplate` is `Type: Runtime`,
`CraftBenchTests` is `Type: Editor`. Three plugins are enabled there:
`FunctionalTestingEditor`, `PythonScriptPlugin` (for L2-introspect editor-Python),
and `GameplayAbilities` (GAS tasks).

---

## 2. The agent-writable module: `Source/CraftBenchTemplate/`

This is a flat-layout module (no `Public/`/`Private/` split — relevant in §4.3).
It ships a family of **base actors**, each the seed for one task family. The pattern
is identical across all of them and is the single most important convention to
internalize:

> A base actor declares the *shape* the verifier will look for — and tags itself —
> but ships the behavior **deliberately absent**. Producing that behavior is the
> agent's task.

### 2.1 The canonical example: `ASanityActor`

- `SanityActor.h:17-24` — `ASanityActor : public AActor`, just a constructor. No
  `BeginPlay` override is declared. The header comment is explicit:
  *"NO BeginPlay override is declared here; supplying that override is the agent's
  task."*
- `SanityActor.cpp:14-18` — the constructor disables tick and does the one
  load-bearing thing: `Tags.Add(FName("SanityRoot"))`.

That tag is the whole identity contract (see §5). The verifier finds this actor by
its `SanityRoot` tag, **never by class**, so the agent is free to subclass
`ASanityActor` and the lookup still works. Task `t0-sanity-log-on-beginplay` asks
the agent to add a `BeginPlay` override that logs `CRAFTBENCH_SANITY_OK` exactly
once on `LogTemp/Display`.

`ATaskActor` follows the same template for the timer task
(`TaskActor.cpp:14-18`, tag `"TaskRoot"`, no `BeginPlay`).

### 2.2 The pawn base: `ACraftBenchCharacter`

This is the generalizable substrate pawn for **motion and GAS** tasks
(`CraftBenchCharacter.h:29-60`). It pre-wires the GAS plumbing an agent shouldn't
have to re-derive headless, while leaving the actual ability *absent*:

- A **pawn-owned** `UAbilitySystemComponent` (avatar = owner = this pawn; *not* a
  PlayerState-owned ASC — a deliberately minimal model for atomic single-player PIE;
  see the class comment `CraftBenchCharacter.h:5-13`).
- Implements `IAbilitySystemInterface::GetAbilitySystemComponent()`
  (`CraftBenchCharacter.h:38`) — the **stable handle the verifier resolves through**.
- `InitAbilityActorInfo()` called idempotently in both `BeginPlay` and
  `PossessedBy` (`CraftBenchCharacter.h:46-49`).
- The agent's actual contribution point:
  `UPROPERTY(EditAnywhere) TArray<TSubclassOf<UGameplayAbility>> GrantedAbilities`
  (`CraftBenchCharacter.h:42-43`). The pawn auto-grants these on the authority. The
  agent fills it via a C++ subclass ctor *or* Blueprint class defaults — **that is
  the only GAS wiring the agent must do** besides authoring the ability.
- Carries the `"CraftBenchPawn"` tag (resolved by tag, never class).

Anti-gaming detail: the base ships `GrantedAbilities` **empty**
(`CraftBenchCharacter.h:14-16`). An unmodified pawn grants nothing, so a GAS task's
tag-trigger finds no ability and fails — the empty-stub submission can't pass.

### 2.3 Other base actors (one per task family)

The module has grown a base actor per task it supports. Worth knowing they exist;
each follows the §2.1 "shape declared, behavior absent, tagged" pattern:
`MovingPlatform`, `InventoryHolder` + `InventorySaveGame`/`InventorySaveCoordinator`
(save-roundtrip), `Structure` + `AttachableModule` + `AttachCoordinator`
(modular-attach), `SpawnHostActor` (spawn-sequence), `CraftBenchLaunchPawn` /
`CraftBenchLaunchAbility` / `CraftBenchAttributeSet` / `CraftBenchGameplayTags`
(GAS launch). All under `Source/CraftBenchTemplate/`.

### 2.4 The agent's build descriptor: `CraftBenchTemplate.Build.cs`

`CraftBenchTemplate.Build.cs:16-30` fixes the public deps:
`Core, CoreUObject, Engine, InputCore, FunctionalTesting`, plus the GAS trio
`GameplayAbilities, GameplayTags, GameplayTasks`. The agent is *permitted* to edit
this file, but most tasks don't require it.

> **Note (load-bearing):** those GAS deps are required by the gold-#19 source files
> in this shared module. The comment at `CraftBenchTemplate.Build.cs:23-29` records
> that a blanket `git checkout` once reverted them (historical), which breaks L1 on
> *every* task (including the reference solutions). The substrate — `Build.cs`, its
> source files, and the fixtures below — is now **committed and tracked** (clone-and-go
> validated 2026-06-21: a fresh clone graded 22/22 reference solutions PASS on
> Windows + UE 5.8). A `git checkout` restores the committed deps rather than
> reverting to nothing; there is no longer uncommitted working state to lose here.

---

## 3. The verifier-only module: `Source/CraftBenchTests/`

This holds the `AFunctionalTest` fixtures plus the two abstract bases they derive
from. It is **deny-write and hash-pinned** (§6). The base-class machinery is the
core of the whole verifier model, so read it carefully.

### 3.1 `ACraftBenchFunctionalTest` — the PIE-native base

`CraftBenchFunctionalTest.{h,cpp}`. Every L2 fixture must derive from this. It owns
the **entire PIE time model** so per-fixture authors never re-implement it. Three
responsibilities, all stated in the header banner (`CraftBenchFunctionalTest.h:14-27`):

**(a) The PIE lever.**
`virtual bool IsEditorOnlyLoadedInPIE() const override { return true; }`
(`CraftBenchFunctionalTest.h:62`). This single override routes a map-based automation
test into a **real PIE world** instead of the Editor World. In PIE, the engine
auto-fires `BeginPlay` on placed actors, ticks `FTimerManager` / `CharacterMovement`,
and ticks the fixture actor every frame. The base sets it to `true` by default so
**no fixture can forget it**.

**(b) Fixed-timestep determinism.**
`PrepareTest()` (`CraftBenchFunctionalTest.cpp:20-30`) snapshots `FApp::UseFixedTimeStep`
+ `FixedDeltaTime` (`SnapshotGlobals`, lines 97-106) and forces `SetUseFixedTimeStep(true)`.
`EndPlay()` restores them *before* chaining `Super` (lines 78-82, 108-117) — so state
doesn't leak across the multi-test editor session. Note it deliberately does **not**
set `FixedDeltaTime` itself: the runner's `-FPS=<rate>` owns the per-frame dt (comment
at lines 24-28). That's how the Timer task runs a 60 Hz and a 20 Hz leg in two PIE
processes from the same fixture.

**(c) A checkpoint clock.**
`Tick()` (`CraftBenchFunctionalTest.cpp:40-76`) is engine-driven. It calls `Super::Tick`
first (which advances `AFunctionalTest::TotalTime` and runs the `IsReady()→StartTest()`
machinery), then reads the **world game-time**:
```
const double Now = World ? World->GetTimeSeconds() : TotalTime;   // line 57-58
```
It fires `OnCheckpoint(idx, t)` for **every** checkpoint crossed this frame (a `while`
loop, lines 61-70 — robust to a tick spanning more than one checkpoint), bailing out
early if a checkpoint failed the test. Once all checkpoints are sampled it calls
`FinishTest(Succeeded)` (lines 72-75).

`SetCheckpointSchedule()` (lines 84-95) sorts the schedule and sets
`TimeLimit = last + TimeLimitMargin` with `TimesUpResult = Failed`, so a stuck test
**fails at the deadline rather than hanging the editor**.

> **Why world game-time, not `TotalTime`?** `TotalTime` is zeroed at `StartTest`, which
> is offset from world-start by the `IsReady→StartTest` warmup. The agent's behavior
> (BeginPlay timers, gravity, spawns) is anchored at *world-start*, so the world clock
> is the only one that stays aligned with it. The comment at lines 51-56 calls this out;
> tight tolerances like the Timer task's ±0.05 s window would break against `TotalTime`.

**What a per-fixture author writes — and nothing more:** tagged-actor resolution in
`PrepareTest` (after `Super::PrepareTest()`), one `SetCheckpointSchedule({...})` call,
and an `OnCheckpoint()` body that samples state. **Never** call `World->Tick` /
`Actor->Tick` (re-entrant inside PIE → `TickTaskManager.cpp:1097` assertion), never
manually dispatch `BeginPlay`, and never reimplement the snapshot/checkpoint loop in a
subclass.

### 3.2 `ACraftBenchPawnFunctionalTest` — the pawn/GAS base

`CraftBenchPawnFunctionalTest.{h,cpp}` sits *on top of* the base and adds three reusable
machines for motion/GAS tasks (`CraftBenchPawnFunctionalTest.h:5-21`):

1. **Pawn-class resolution** — `ResolveAgentPawnClass()` (`.cpp:30-93`) is
   *identity-by-derivation*: it `GetDerivedClasses(ACraftBenchCharacter::StaticClass())`
   and returns the agent's first non-abstract **C++** subclass (skipping `SKEL_`/`REINST_`
   and BP-generated classes, lines 35-57); if none, it scans the **asset registry under
   `/Game/Tasks`** for a Blueprint subclass (lines 63-88) — so a BP/MCP agent's deliverable
   is gradable; if still none, it returns the base, whose empty `GrantedAbilities` makes a
   GAS task correctly fail (lines 90-92). The task never dictates a class name.
2. **Spawn + possess** — `SpawnAndPossessPawn()` (`.cpp:95-125`) spawns the resolved pawn
   and calls `SpawnDefaultController()`. **Possession is mandatory:** the Slice-0 spike
   proved an *unpossessed* Character in headless PIE is inert (`MOVE_None`, no gravity,
   ignores `LaunchCharacter`); a possessed one integrates a clean ballistic arc
   (header comment `.h:14-17`). No input is injected.
3. **Trajectory sampler + GAS runtime probe** — `RecordSample()` captures
   `(t, location, velocity, movement-mode)` into `Samples` (`.cpp:127-142`), and the
   shape invariants `ApexDeltaZ()`, `RoseThenFell()`, `ReachedMovementMode()`,
   `VelocityZNear()`, `MaxVelocityZAfter()` (`.cpp:144-227`) separate a real launch from a
   teleport. The GAS side — `PawnASC()`, `NumGrantedAbilitiesWithTag()`,
   `TriggerAbilityByTag()` (`.cpp:229-265`) — does deterministic ASC introspection by tag.
   All plain API, **no LLM** (FR-020d-clean).

The data structure it samples into is `FCraftBenchTrajectorySample`
(`CraftBenchPawnFunctionalTest.h:34-43`): `{ double T; FVector Location; FVector Velocity;
TEnumAsByte<EMovementMode> Mode; }`.

### 3.3 How a *concrete* L2 fixture observes state

Two concrete fixtures show the two observation idioms an author chooses between.

**Idiom A — checkpoint-sampling (`ATimerTaskFunctionalTest`).** This is the textbook
shape. `TimerTaskFunctionalTest.cpp`:
- `PrepareTest()` (lines 39-72): `Super::PrepareTest()`, then **resolve by tag** —
  `UGameplayStatics::GetAllActorsWithTag(World, "TaskRoot", Found)` and assert exactly one
  (lines 53-60). Then a **dt-aware** schedule bracketing the agent's 1.5 s timer:
  `SetCheckpointSchedule({ 1.5 - 0.05, 1.5 + max(0.1, 4*dt) })` (lines 69-71). It reads the
  *actual* `FApp::GetFixedDeltaTime()` so the same fixture works at both 60 Hz and 20 Hz —
  that's the framerate-independence discrimination.
- `OnCheckpoint()` (lines 74-94): at checkpoint 0 the `TaskRoot` must still be present;
  at checkpoint 1 it must be gone (the timer must have `Destroy()`-ed it). A tick-count
  (60 Hz) overfit fires at `90*0.05 = 4.5 s` at 20 Hz and is caught here (comment lines
  62-68, 89-91).

**Idiom B — pre-BeginPlay listener (`ASanityFunctionalTest`).** When the behavior to observe
happens *during BeginPlay* (e.g. "logged on BeginPlay"), checkpoint-sampling is too late —
`BeginPlay` already fired before `PrepareTest`. So the fixture installs its observer earlier.
`SanityFunctionalTest.cpp`:
- The constructor registers `FWorldDelegates::OnWorldInitializedActors`
  (lines 46-54), which fires **after `PostInitializeComponents` but before placed-actor
  `BeginPlay`**. The callback installs a custom `FOutputDevice` (a GLog listener) — filtered
  to **our** PIE world only (`Params.World != GetWorld()`, line 59).
- That `FSanitySubstringCounterDevice` (`SanityFunctionalTest.h:31-51`,
  `.cpp:22-44`) counts log lines matching a substring, gated on category *and* verbosity —
  so an agent that emits to a different category or quieter verbosity to "hide" the line
  still fails. Installing *after* construction means a CDO/constructor-time log is never
  counted (anti-gaming case #3).
- `PrepareTest()` still resolves the actor by the `SanityRoot` tag (lines 83-91) and sets a
  single checkpoint at `0.1 s` (line 94, one tick past `StartTest`, by which point BeginPlay
  has fired). `OnCheckpoint()` asserts the match count is exactly 1 (lines 97-112).
- `EndPlay()` tears down the listener *and* unregisters the global delegate before chaining
  Super (lines 127-137).

**Idiom C (worth noting) — direct substrate entry-point call.** `AModularAttachFunctionalTest`
`#include`s the agent's runtime headers and calls a substrate API directly:
`Coord->TryAttachModule(Module, Structure)` (`ModularAttachFunctionalTest.cpp:165`, includes
at lines 15-17). This is only possible because the test module declares the runtime module as
a dependency and adds its source dir to the include path (§4.3).

---

## 4. Module wiring details

### 4.1 The flat-layout include hack (`CraftBenchTests.Build.cs`)

`CraftBenchTests.Build.cs:24-59`. The test module depends on `CraftBenchTemplate` (line 39),
but because the runtime module is **flat-layout** (no `Public/` folder), a plain module
dependency does *not* put its headers on the include path. So line 56 adds the runtime
source dir explicitly:
```
PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "..", "CraftBenchTemplate"));
```
Crucially this is done **verifier-side**, not in the agent's `Build.cs` — so the agent can't
break the include path by editing their own build file (comment lines 50-55).

### 4.2 Why the test module is `Type: Editor`

`CraftBenchTests.Build.cs:29` sets `Type = ModuleType.CPlusPlus` and the `.uproject` declares
it `Type: Editor`. The comment (`CraftBenchTests.Build.cs:8-20`) spells out the anti-gaming
intent: an Editor module is **excluded from packaged/shipping builds**, so the agent's runtime
code cannot link against the fixtures — gameplay code physically cannot reach into the test to
short-circuit it. The dependency direction is strictly editor→runtime, never the reverse.

### 4.3 Test-module deps

`CraftBenchTests.Build.cs:31-48`: `Core, CoreUObject, Engine, FunctionalTesting, UnrealEd,
AutomationController, CraftBenchTemplate`, the GAS trio (for the pawn fixture's ASC probe), and
`AssetRegistry` (for BP pawn resolution under `/Game/Tasks`).

---

## 5. The two integrity defenses

These are complementary; both must pass before any build runs.

### 5.1 Sandbox — `AGENT_WRITABLE.json`

`UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` declares the agent's writable surface;
`tools/verify-single/sandbox.py` enforces it (a submission file must match a `writable` prefix
**and** no `deny` prefix; rejection = exit 4). Current contents:

- `writable`: `Source/CraftBenchTemplate/`, `Content/Tasks/`.
- `asset_writable` (a *widening* allowlist for `.uasset`/`.umap` deliverables only, captured by
  `--capture-assets`): `Content/Tasks/`, `Content/Blueprints/`, `Content/Abilities/`,
  `Content/Generated_Materials/`, `Content/Generated_Audio/`. This exists because Aura's
  sub-agents author assets *outside* `Content/Tasks/` (observed on the realistic-collectible-coin
  run — see the `_asset_writable_comment` in the file).
- `deny` (always wins): `Source/CraftBenchTests/`, `Config/`, `Content/Maps/`, `Tools/`,
  `Plugins/`, the `.uproject`, and `AGENT_WRITABLE.json` itself.

The net effect: source edits only under `Source/CraftBenchTemplate/`; generated assets only under
the five `asset_writable` folders; **`Content/Maps/` (verifier-owned task maps) stays rejected**;
everything else in `Content/` is denied by allowlist-miss.

### 5.2 Integrity pin — `verifier_hashes.json`

`tools/verify-single/verifier_hashes.json` is keyed by substrate name (`"CraftBenchTemplate"`),
mapping each filename under `Source/CraftBenchTests/` to its SHA-256
(`.AGENT_WRITE_DENY`, every fixture `.cpp/.h`, the `Build.cs`, etc.). Strict-mode default: a
missing manifest, a missing substrate entry, *or any per-file drift* = **REJECT (exit 3)**, before
L1/L2 run. The only legitimate way to bump it is `run_task.py --regen-verifier-hashes` (used by
substrate maintainers in the same commit that edits a fixture). The policy is also documented in
plain English at `Source/CraftBenchTests/.AGENT_WRITE_DENY` (which the agent is told to read).

> **Gotcha:** *every* file under `Source/CraftBenchTests/` is pinned, including new fixtures. Any
> fixture on disk that is not in the manifest trips the pin (exit 3) — historically that bit WIP
> fixtures (`AnimInterrupt`, `RenderProbe`) before they were pinned. Both `AnimInterruptFunctionalTest.*`
> are present in the manifest today, so they're accounted for; adding a fixture means regenerating
> the manifest via `--regen-verifier-hashes` in the same commit.

---

## 6. The maps under `Content/Maps/`

`.umap` files are binary and can't be authored from text alone, so the substrate uses **two
coexisting patterns by design** (the repo's "headless map materialization"):

1. **Committed binary** — the canonical bootstrap today. Every map ships as a committed binary
   `.umap`. On disk now: `L_SanityTask`, `L_TimerTask`, `L_SpawnSequence`, `L_WalkAround`, plus the
   gold-task maps `L_FlightMode`, `L_GasLaunch`, `L_InventorySave`, `L_ModularAttach`,
   `L_PlatformLerp`, `L_RenderProbe`.
2. **Text-scaffolded** — the optional bootstrap. A map MAY ship `Tools/scaffold_<map>.py`
   (UE Python) that regenerates it; the runner's `scaffold_map.py` invokes the scaffolder if
   the `.umap` is missing. *(Updated 2026-07-16: the per-map `<map>.umap.NOTE.md` siblings this
   tour originally cited were retired — per-map contents/regen recipes now live centrally in
   `docs/MAPS.md`, and scaffolders are optional once the binary is committed.)*

**What a map contains** (now documented per-map in `docs/MAPS.md`): exactly the placed substrate actor
(`ATaskActor`, already tagged `TaskRoot` from its ctor — *do not edit Tags in the level*) **and**
the placed `AFunctionalTest` fixture (`ATimerTaskFunctionalTest`). Nothing else — no PlayerStart,
no lights, no geometry. The automation framework discovers placed `AFunctionalTest`-derived actors
automatically; no extra wiring.

> **Gotcha — map authoring needs a real RHI.** The map *scaffolder* drops `-nullrhi` and uses a
> real off-screen Metal RHI; that's what resolved the historical `spawn_actor_from_class` crash on
> UE 5.7.4 Mac Silicon. **Test runs still use `-nullrhi`.** Don't conflate the two.
>
> **Observation:** `Content/Maps/` also contains a stray `L_WalkAround.uasset` (47 KB, dated newer
> than its `.umap`) alongside `L_WalkAround.umap`. That's unusual — a map normally lives only as
> a `.umap`. Worth a maintainer glance; I'm flagging it rather than guessing its role.
>
> **Doc mismatch to note:** the `.uproject` `Description` (`CraftBenchTemplate.uproject:4`)
> points at a path `substrate/CraftBenchTemplate/...`. The project actually lives at
> `UE-projects/CraftBenchTemplate/...` — the `substrate/` path is stale phrasing, not a real dir.

---

## 7. How a task wires its fixture + map to the verifier

The join from a task spec to a fixture+map is done by the runner's spec parser
(`tools/verify-single/run_task.py`). Two paths:

**Path 1 — explicit `## Verifier fixtures` (preferred, multi-fixture).** A task lists
`<map> :: <AFunctionalTest class>` bullets. Example, `tasks/gp-gas-launch.md:96-98`:
```
## Verifier fixtures

- L_GasLaunch :: AGasLaunchFunctionalTest
```
`_parse_fixtures_block()` (`run_task.py:391-411`) extracts each `<map> :: <class>` bullet via
`_FIXTURE_LINE_RE` (deduping, order-preserving). For each, `_filter_for_fixture()`
(`run_task.py:1012-1016`) builds `Project.Functional Tests.Maps.<map>.<ClassNoAPrefix>`, and
`derive_test_filter()` `+`-joins them (`run_task.py:995-996`) into one `Automation RunTests`
filter that runs every fixture in one editor session (fresh world per test). Framerate-
independence tasks list the *same* fixture against two maps/legs.

**Path 2 — legacy single-fixture derivation (fallback).** With no fixtures block, the parser
regex-scrapes the spec: `_MAP_NAME_RE` finds `Maps/L_<Name>` (`run_task.py:141`, used at 181-184)
and a test-class hint feeds `Project.Functional Tests.Maps.<MapName>.<TestClassNoAPrefix>`
(`derive_test_filter`, `run_task.py:997-1001`).

There is also a newer **unified `## Verifier layers` block** (`run_task.py:213-229`) that, when
present, is the single source of truth — it can carry `L2` fixtures inline (`map :: class, ...`),
`L2I` scripts, `L3` fixtures, and an artifact path — and overrides the legacy multi-channel
parsing. Un-migrated tasks keep working via the fallback.

> **Gotcha — the `A` prefix is stripped.** `AGasLaunchFunctionalTest` appears in the UE automation
> filter as `GasLaunchFunctionalTest`. `_strip_class_prefix()` (`run_task.py:1004-1009`) drops a
> leading `A` or `F`. Spec authors may write either form; don't undo the strip.

### The end-to-end data flow

```
task spec (.md)                      submission (agent output dir)
  ## Verifier fixtures                 Source/CraftBenchTemplate/... (+ Content/Tasks/...)
  - <map> :: <Fixture>                          |
         |                                       v
         |                         sandbox.py  (AGENT_WRITABLE.json)  -> reject? exit 4
         |                         hash pin     (verifier_hashes.json) -> drift? exit 3
         v                                       |
  derive_test_filter()  ----------------------> overlay onto clean substrate copy
  "Project.Functional Tests.Maps.<map>.<Class>"  |
         |                                        v
         |                          L1: UBT build <Module>Editor + <Module>(Game)
         v                                        |
  scaffold_map.py (real RHI) materializes <map> if missing
         |                                        v
  UnrealEditor-Cmd /Game/Maps/<map>  L2: PIE world, -nullrhi -deterministic -FPS=<rate>
   -ExecCmds="Automation RunTests <filter>"       |
         |                                        v
         |     ACraftBenchFunctionalTest base ticks the fixture every frame
         |     PIE auto-fires BeginPlay; FTimerManager / CMC tick
         |       fixture: resolve-by-tag -> SetCheckpointSchedule -> OnCheckpoint samples
         v                                        v
                         JSON report (PASS/FAIL by deterministic gate; R2 advisory non-gating)
```

(L1/L2 invocation specifics belong to the runner tour section; included here only so the
substrate's role in the flow is legible.)

---

## 8. How to observe the substrate without a UE install

You can't build/PIE here (no UE installed). But the substrate is fully readable, and the parser
that wires it is pure-Python and unit-tested:

```sh
# Confirm the fixture/map wiring parses as you expect (no UE needed):
python3 -m unittest tools.verify-single.tests.test_run_task.TestMultiFixtureParsing

# See which files the integrity pin covers for this substrate:
python3 -c "import json; print(*sorted(json.load(open('tools/verify-single/verifier_hashes.json'))['CraftBenchTemplate']), sep='\n')"

# Inspect the sandbox surface:
cat UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json
```

---

## 9. Newcomer gotcha checklist (the things that bite)

1. **Two modules, two permission worlds.** Agent writes `Source/CraftBenchTemplate/` only;
   `Source/CraftBenchTests/` is deny-write *and* hash-pinned. Editing a fixture without
   `--regen-verifier-hashes` → exit 3.
2. **Identity by tag, never by class** (`GetAllActorsWithTag`). Agents may subclass; class lookup
   would penalize that. The tag is set in the base actor's *constructor*.
3. **PIE drives the lifecycle — never drive it yourself.** No `World->Tick`/`Actor->Tick` in a
   fixture (re-entrant → `TickTaskManager.cpp:1097`). Use the checkpoint schedule.
4. **BeginPlay fires before `PrepareTest`.** To observe the BeginPlay window, install the listener
   in `OnWorldInitializedActors`, filtered to your PIE world (the Sanity idiom).
5. **Checkpoint clock = world game-time, not `TotalTime`.** The latter is warmup-offset.
6. **dt is owned by the runner's `-FPS`,** not by the fixture and not by `t.MaxFPS`. The base only
   flips `UseFixedTimeStep`; tolerances must be dt-aware (the Timer fixture reads
   `FApp::GetFixedDeltaTime()`).
7. **`A`-prefix stripping** in automation filters: `AFoo` → `Foo`.
8. **Map authoring needs a real RHI; test runs use `-nullrhi`.** Don't mix them up.
9. **The substrate is committed/clone-and-go** — the Build.cs GAS deps, fixtures, sources, and
   binary maps are all tracked (clone-and-go validated 2026-06-21, 22/22 reference PASS on
   Windows + UE 5.8). A `git checkout` restores committed state, not an empty one; there is no
   uncommitted working state to protect here anymore.
10. **Watch for the stray `L_WalkAround.uasset`** and the stale `substrate/...` path string in the
    `.uproject` Description — neither is a functional problem, but both will confuse a newcomer.
