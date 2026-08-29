# Discrimination matrix — t0-sanity-bp-log-on-beginplay

Verdicts are from the DETERMINISTIC verifier (no agent, no tokens). Run each with
`--substrate-from-live` until the fixture/map/manifest are committed.

Design: **L1 + L2 only.** The fixture loads the one deliverable by its required
path `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`, spawns it, and asserts the token is logged
exactly once. No asset scan, no L2I, no tags.

The discrimination-table format is normative: **first column = the submission**
(`../reference`, `empty`, or a `<variant>/` dir), an **Overall** column, and an
**Expected message** column whose backtick-wrapped literal must appear in the L2 log
(the discriminate parser keys on these — a leading `#` number column breaks it).

| Submission | Overall | Fails at | Expected message |
|------------|---------|----------|------------------|
| `../reference` | **PASS** | — | BP_Announcer BeginPlay→Print CRAFTBENCH_BP_OK; all gates green (L1✓, L2 count==1) |
| empty (no overlay → base scaffold, no BP at the path) | **FAIL** | L2 PrepareTest | `No Actor Blueprint found at the required path` |
| `cpp-only/` (C++ actor prints token on BeginPlay; no `.uasset`) | **FAIL** | L2 PrepareTest | `No Actor Blueprint found at the required path` |
| `wrong-path/` (BP authored at a different path) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 PrepareTest | `No Actor Blueprint found at the required path` |
| `wrong-string/` (BP_Announcer prints `CRAFTBENCH_BP_XX`) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 cp0 | `observed 0` |
| `tick-print/` (BP_Announcer prints token every Tick) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 cp0 | `observed >=2` |

## Coverage bounded (stated honestly, not silently)

- The `wrong-path/`, `wrong-string/`, and `tick-print/` rows require authoring
  Blueprint `.uasset` binaries in a UE 5.8 editor; they are NOT materialized as dirs
  and so are documented, not run. `reference`, `empty`, and `cpp-only/` are the graded
  legs.
- **`empty` and `cpp-only/` both fail at the SAME point** (load-by-path returns null).
  That is correct and intended: an empty submission and a C++-only submission are
  indistinguishable to a Blueprint-path load, and both should FAIL with the same
  named message.
- **Accepted residual (T0 scope):** a BP that prints the token from its
  Construction Script rather than BeginPlay would PASS (count==1). Distinguishing
  that needs graph introspection (L2I), which this smoke task intentionally omits.

## Calibration — resolved by evidence

- **Log routing** (Print String → `LogBlueprintUserMessages` at `Log`): confirmed
  headless on Windows in the vendor headless bring-up runbook (not shipped) (a Blueprint
  BeginPlay→Print run verified `LogBlueprintUserMessages: ... <token>`, count 1).
  The fixture's `FBpTokenCounterDevice` filters exactly that channel/verbosity.
- **No scan / no pre-existing-asset interference:** the fixture loads only
  `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`; `BP_SanityLogger` and friends are never touched.

## Status — VALIDATED 2026-07-15 (Windows + UE 5.8)

- ✅ Fixture load path, task prompt, and all docs point at the per-task path
  `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`.
- ✅ Map committed at `Content/Maps/t0-sanity-bp-log-on-beginplay/L_BpSanityTask.umap`
  (+ `Tools/scaffold_L_BpSanityTask.py`); the grade uses it directly (no re-bake).
- ✅ `tools/verify-single/verifier_hashes.json` re-hashed for the updated fixture.
- ✅ Reference `BP_Announcer.uasset` re-pathed in-editor (`rename_asset`) so its
  internal package name is `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`,
  re-harvested to `reference/Content/Tasks/t0-sanity-bp-log-on-beginplay/`.
- ✅ Rows 1–3 run with the deterministic verifier (`run_task.py --substrate-from-live`):
  - Row 1 reference → **PASS** (L1 both targets exit 0; L2 `tests=1/1`, token once).
  - Row 2 empty → **FAIL** at L2 PrepareTest, named assertion citing the required path.
  - Row 3 cpp-only → **FAIL** at L2 PrepareTest, same named assertion.

## Remaining work (optional, needs a UE 5.8 editor)

- Rows 4–6 (`wrong-path`, `wrong-string`, `tick-print`) are argued from the named
  assertions (bounded coverage, above). Materializing them as `.uasset` binaries
  would upgrade them from argued to run — see the task's `REFERENCE-NOTE.md`.
  Rows 1–3 gate the task today.

## Requirements table (checklist §7, the mandatory soundness artifact)

Layers are `[L1, L2]` — no L2I grader. Every backticked span in a FIXTURE-gate row
is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t0-sanity-bp-log-on-beginplay/BpSanityFunctionalTest.cpp`
(never crossing a printf placeholder). Three rows cite non-fixture facts, and their
backticked tokens are verbatim in the source named inline: `-nullrhi` in
`tools/verify-single/layers/l2_pie.py` (the runner's L2 editor launch, row 5);
`Content/Maps/` in the `deny` list of
`UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` (row 11); and the two L1
target strings in this task's `task.md` L1 assert block (row 12 —
`tools/verify-single/layers/l1_build.py` composes them at runtime as
`<Module>Editor` / `<Module>`, so they are not literals there). The L1 gate is the
layer itself (`l1_build.py`, UBT exit 0 for both targets), which has no FinishTest
literal. The error-class literal `PrepareTest: no UWorld available` is a machine
fault and is never credited as a gate.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the deliverable is a Blueprint asset, not C++ ("Create a new Actor Blueprint asset") | fully | load-by-path gate — `No Actor Blueprint found at the required path` (StaticLoadClass of `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.BP_Announcer_C` returns null → named FAIL) | unconditional (first gate after the world-availability error check) | nothing; a C++-only BeginPlay override produces no `.uasset` at the path and dies here, and the deny-listed verifier map blocks placing a C++ actor |
| 2 | asset lives at the exact path/name `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer` | fully | load-by-path gate — `No Actor Blueprint found at the required path` (no asset scan; only the one package path is tried, and the internal package name must match, not just the file location) | unconditional | nothing; an asset authored anywhere else, or a `.uasset` copied on disk without a matching internal package name, is never found |
| 3 | it is an **Actor** Blueprint (spawnable actor class) | fully | load-by-path gate (StaticLoadClass is rooted at `AActor::StaticClass()`, so a non-Actor parent loads null → same token) plus spawn gate — `Failed to spawn an instance of ` | spawn gate skipped when rows 1–2 already failed | any AActor SUBCLASS parent (Pawn, Character, the task scaffold…) is accepted — "Actor Blueprint" is read as is-an-Actor, not parent-is-exactly-Actor |
| 4 | prints `CRAFTBENCH_BP_OK` to the **engine log** | fully | count gate — `Expected exactly one LogBlueprintUserMessages emission containing ` (GLog listener filtering category `LogBlueprintUserMessages` at verbosity floor `Log`, installed at world-init before the spawn/BeginPlay) | rows 1–3 (no class loaded / nothing spawned) | mechanism is effectively pinned to the Print String channel: a token emitted on any OTHER log category (e.g. a custom `UE_LOG`) counts 0 and FAILS — over-strict direction, not a gaming hole |
| 5 | prints the message **to the screen** | **NOT ASSERTABLE at L2** (engine-level; established 2026-08-19, was "NOT ASSERTED") | — none, and none is available: see the evidence below | — | **This row is closed as UNREACHABLE, not as unfinished** — read the reasons before proposing a gate. `UKismetSystemLibrary::PrintString`'s screen half calls `GEngine->AddOnScreenDebugMessage(InnerKey = -1, ...)` (`KismetSystemLibrary.cpp:456+`), which appends to `UEngine::PriorityScreenMessages` — and that member is **private** with no public read accessor (`Engine.h:2188`, under a `private:`). The one public probe, `UEngine::OnScreenDebugMessageExists(uint64)`, **returns `true` unconditionally** for key `-1` (`UnrealEngine.cpp:12657-12662`, comment: "Priority messages assumed to always exist"), so it cannot distinguish a message that was added from one that was not. `-nullrhi` is NOT the obstacle — the message is still recorded headless, because the only gate is `bEnableOnScreenDebugMessages` and the editor build is not SHIPPING/TEST. The one remaining route is structural: an L2I check that the graph's Print String node has `bPrintToScreen` set. That is a new layer on this task and an OWNER DECISION, not honing. Meanwhile the LOG half is fully gated (row 4), and the fixture listens on `LogBlueprintUserMessages` at `Log`, which is exactly where `PrintString`'s log half goes (verified against the same engine source) |
| 6 | the message is the **exact** string `CRAFTBENCH_BP_OK` | partially | count gate — `Expected exactly one LogBlueprintUserMessages emission containing ` (the device counts lines via `Strstr` substring containment) | rows 1–3 | containment, not equality: `HELLO CRAFTBENCH_BP_OKAY` matches and passes; a mutated/misspelled token counts 0 and fails, so only supersets slip through |
| 7 | emitted **exactly once** | fully | count gate — checkpoint asserts `Captured == 1`, else `during BP_Announcer's BeginPlay window; observed ` N | rows 1–3 | nothing within the window: 0 fails, ≥2 fails (a Tick loop at the fixed 1/60 dt emits ~12 by the 0.2 s checkpoint) |
| 8 | emission happens **when gameplay begins** (BeginPlay) | partially | count gate — the instance is spawned into a HasBegunPlay world (BeginPlay dispatches immediately) and the count is read at the 0.2 s checkpoint, so the emission must land in that spawn window | rows 1–3 | a Construction Script emission is captured identically (documented T0 accepted residual — distinguishing it needs L2I graph introspection); any event firing inside 0.2 s of spawn is credited as "BeginPlay" |
| 9 | after the single message it **does nothing further** | partially | count gate — only further TOKEN emissions inside the 0.2 s window are caught (they push the count ≥2) | rows 1–3; anything after the cp0 `FinishTest` is unobserved | token re-emission after t=0.2 s, and ANY non-token side effect (movement, spawning, other log lines) at any time — behavior beyond the message is unconstrained |
| 10 | it should **simply remain in the world** | **fully** (closed 2026-08-19) | `The BP_Announcer instance printed the message but did not remain in the world; it was gone by the checkpoint` | count gate fires first (this is inside the count-is-one branch, so every leg previously credited at the count literal still is) | `bSpawned` only ever recorded that the SPAWN succeeded, so a Blueprint that printed the token once and then `DestroyActor`'d itself scored a clean PASS. The instance is now held in a `TWeakObjectPtr` and re-checked at the checkpoint — weak deliberately, since a raw pointer would keep the actor reachable and a destroyed actor would still look present. **Residual:** "remain" is liveness only; hiding itself or teleporting away is still invisible, and "do nothing further" is bounded by the exactly-once count rather than by an activity check |
| 11 | no level placement is needed (asset must work as a standalone spawned instance) | fully, by construction | spawn gate — `Failed to spawn an instance of ` (the VERIFIER owns placement: the fixture spawns exactly one instance; `Content/Maps/` is a `deny` entry in `UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` — sandbox fact, not a fixture literal — so the agent cannot pre-place anything) | rows 1–2 | nothing; a class that cannot be runtime-spawned (e.g. flagged abstract) fails here |
| 12 | "make sure it compiles cleanly" | partially | L1 build gate — UBT exits 0 for `CraftBenchTemplateEditor` and `CraftBenchTemplate` (Game) — target names verbatim in this task's `task.md` L1 assert block; `tools/verify-single/layers/l1_build.py` derives them at runtime as `<Module>Editor`/`<Module>`, no source literal. The Blueprint's OWN compile state has no direct gate — its proxy is behavioral (a broken graph emits 0 → row 7 fails) | L1 is unconditional; the behavioral proxy is skipped when rows 1–3 fail | a Blueprint saved with compiler warnings or non-fatal graph issues passes as long as the generated class still spawns and emits the token once; L1 only certifies the C++ project still builds |
