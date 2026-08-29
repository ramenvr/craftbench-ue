# Discrimination matrix — t1-default-cube-mesh-actor

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t1-default-cube-mesh-actor [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.5s) | `found no static-mesh component on the actor` | #3 (nothing delivered) |
| `mesh-set-in-beginplay/` | FAIL | cp0 (0.5s) | `assigned at runtime rather than carried as a class default` | #1 |
| `wrong-default-mesh/` | FAIL | cp0 (0.5s) | `instead of the engine cube` | #2 |
| `component-without-mesh/` | FAIL | cp0 (0.5s) | `with no mesh assigned` | #3 |

Notes:
- The checkpoint-0 probe emits ONE failure, ordered: live-instance display
  first (covers empty / wrong-mesh / no-mesh / hidden), then the pre-BeginPlay
  contrast (covers runtime assignment), then the class-default probe (backstop
  for anything that fakes the first two — no authored variant targets it
  alone; it is argued from the named assertion, bounded coverage stated
  honestly).
- Anti-gaming note #4 (invisible delivery) also falls out of the live-instance
  probe (`only on a component that is not registered and visible`); argued
  from the named assertion rather than a separate submission.
- **Substring disjointness:** the fixture's pre-BeginPlay fragments are worded
  differently from its checkpoint-time probe details precisely so that no row's
  substring above appears inside any OTHER leg's failure output (the
  runtime-assignment message embeds the pre-window fragment; verified by the
  authoring validation's cross-containment check).
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason.

## Status

- Authored 2026-07-29 from the spec + the shipped fixture.
- **EXECUTED 2026-07-29** (same date, after the binary half landed):
  `cb discriminate --task cpp/t1-default-cube-mesh-actor --wip` =
  **discriminated: YES** — reference PASS; empty, component-without-mesh,
  mesh-set-in-beginplay, wrong-default-mesh all FAIL, each `[ok ]` (credited
  via its named substring in the table above). First build of the fixture
  compiled clean; map authored by `aids/author_L_DefaultCubeMesh.py`.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-default-cube-mesh-actor/DefaultCubeMeshFunctionalTest.cpp`
(probe-detail fragments called out below come from the same file's shared `ProbeActorForEngineCube` helper and are appended into the gate literal via `%s`).
Structural rows cite `tools/verify-single/sandbox.py` + `UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` (exit-4 lane) and `tools/verify-single/layers/l1_build.py` (L1); the task wires `layers: [L1, L2]` — no L2I grader exists for this task.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the code still compiles (implicit in "Solve in C++") | fully | L1 — UnrealBuildTool must exit 0 for BOTH the Editor and Game targets (`l1_build.py`; short-circuits on first failure; no L2 literal — a build failure never reaches the fixture) | unconditional (first layer; every L2 row below is skipped when L1 fails) | anything that compiles: dead code, unused includes, style — L1 gates exit codes only in the default lane |
| 2 | one actor tagged `CubeMeshDisplay` stays discoverable in the level | fully | L2 PrepareTest resolve gate — `Expected exactly one actor tagged 'CubeMeshDisplay' in the test level; found ` (a host destroyed between PrepareTest and t=0.5s fails the separate literal `the tagged actor is no longer valid at checkpoint time.`) | L1 failed | nothing — the tag lives on the placed instance in the deny-listed map; only runtime destruction/duplication can break it, and both fail here |
| 3 | the placed instance visibly displays a mesh on a registered, visible, not-hidden-in-game static-mesh component | fully | L2 checkpoint-0 live gate — `expected a registered, visible static-mesh component on the 'CubeMeshDisplay' actor displaying the engine cube ('/Engine/BasicShapes/Cube.Cube'); ` (a cube parked on an unregistered/hidden component appends the helper fragment `found the engine cube only on a component that is not registered and visible.`) | rows 1-2 | anything after t=0.5s is unobserved — a component destroyed or hidden at t=1s passes; extra components, materials, transforms, scale are all free |
| 4 | the mesh is exactly the engine primitive `/Engine/BasicShapes/Cube.Cube`, not another primitive or a lookalike | fully | same checkpoint-0 live gate as row 3; the identity miss appends the helper fragment `instead of the engine cube.` (full found-path printed), an empty component appends `found a static-mesh component with no mesh assigned.`, no component at all appends `found no static-mesh component on the actor.` | rows 1-2 | only the object PATH is compared — a re-scaled/re-materialed engine cube passes (deliberate: appearance beyond mesh identity is not the graded concept) |
| 5 | the cube is in place BEFORE any of the actor's play-time logic runs | fully | L2 checkpoint-0 contrast gate — `assigned at runtime rather than carried as a class default (pre-BeginPlay observation: ` — keyed on the `FWorldDelegates::OnWorldInitializedActors` probe (fires after PostInitializeComponents, before placed-actor BeginPlay) | rows 1-4 (fires only once the live instance displays the cube) | an assignment in PostInitializeComponents or any hook EARLIER than the observation window passes this gate — it is caught only by row 6's CDO probe |
| 6 | the TYPE's class defaults already carry the cube on a mesh component (editor-visible class defaults, before any instance exists) | fully | L2 checkpoint-0 CDO gate — `the class default object does not carry the engine cube on a static-mesh component; ` (an unresolvable CDO routes to the `HARNESS-PRECONDITION:` Error literal, verifier-side by design) | rows 1-5 | CDO probe checks mesh identity only — a CDO whose component defaults to hidden-in-game plus a BeginPlay unhide passes (visibility is asserted on the live instance only, row 3) |
| 7 | EVERY instance shows the cube: designer-dropped and code-spawned instances, not just the placed one | partially | proxied by row 6 only — the CDO carrying the cube implies fresh instances inherit it; NO second instance is ever dropped or spawned by the fixture | rows 1-5 (same gate as row 6) | a lifecycle override that strips/hides the mesh on instances NOT tagged `CubeMeshDisplay` (only the placed one carries the tag) passes all three probes while every new instance renders nothing |
| 8 | no per-instance configuration and no level edits | fully | combination: level edits reject pre-grade at sandbox exit 4 (`Content/Maps/` is an explicit `deny` prefix in `AGENT_WRITABLE.json`; not an L2 literal), and per-instance setup fails rows 5-6 | unconditional (sandbox) / rows 1-4 (L2 legs) | nothing observable — the two lanes close both routes |
| 9 | do not create a Blueprint subclass | **NOT ASSERTED** | no gate — nothing inspects the submission for Blueprint assets; `Content/Tasks/` and `Content/Blueprints/` are `asset_writable`, so a `.uasset` subclass is ACCEPTED by the sandbox and then simply never graded | — | a submission may SHIP a Blueprint subclass alongside a correct C++ fix and still PASS; the route is structurally inert (the placed instance is the C++ class and the map is deny-listed, so a BP-subclass-ONLY submission cannot pass), but the prohibition itself is unenforced |
| 10 | solve on the EXISTING class (`Source/CraftBenchTemplate/` C++) | structurally | sandbox writable-allowlist — `Source/CraftBenchTemplate/` is a `writable` entry in `AGENT_WRITABLE.json` (two separate source spans; the JSON is a key + list, not a `key: value` line), everything else non-asset rejects exit 4 — + the placed instance in the deny-listed map IS the existing class, so only its own C++ (or a parent) can change what rows 3-6 observe; the fixture deliberately resolves by tag, never by class name | unconditional | free choice of mechanism inside the class — `CreateDefaultSubobject` vs `ObjectInitializer`, `FObjectFinder` vs a soft path — behavior-only by design (the source row's code-shape checks were cut with documented provenance) |
| 11 | do not edit any test file | fully | structural: `Source/CraftBenchTests/` is a `deny` prefix (sandbox exit 4) AND the runner materializes the graded substrate from git HEAD, so even an on-disk edit never reaches the grade; human review gates committed changes (prose, not a token — that path appears in none of the claimed source files) | unconditional | nothing |
| 12 | (verifier-spec claim, not a prompt clause) no new shadowed-variable / deprecated-declarations warnings in the agent-authored files | **NOT ASSERTED** | no default gate — `l1_build.py` COUNTS agent-file warnings (`warning_count_agent_files`) but the gate (`registry.py`: fail when count > 0) fires only under `--strict-warnings`, which is OFF by default; and even when on, it is an absolute agent-file warning count, not the "new warnings diff" the spec text promises | — | a submission can add any number of shadowed-variable / C4996-deprecation warnings and PASS the default lane; the spec's L1 warning assert is aspirational text |

Coverage notes, stated honestly:
- Rows 3-6 all live inside ONE checkpoint-0 dispatcher that emits exactly ONE failure, ordered live-display -> pre-BeginPlay contrast -> CDO; the "Gate skipped when" column reflects that fan-out.
- Row 7's escape is contrived (it requires deliberately anti-correlated lifecycle code) but real: no gate spawns a fresh instance. Closing it would take a fixture-side `SpawnActor` of the host's class plus a re-probe — noted as the boundary a hand-authored variant could not have found.
