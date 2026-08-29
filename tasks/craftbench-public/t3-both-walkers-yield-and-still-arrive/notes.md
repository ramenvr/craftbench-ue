# t3-both-walkers-yield-and-still-arrive - owner notes

## Current state

**AUTHORED / PUBLISHED / COMMITTED-SUBSTRATE DISCRIMINATION PASS.**
Editor and Game compilation are green. The empty baseline, Detour admission
asset, dynamic-navigation admission map, final two-layout map, and their
independent cold readbacks are green and byte-stable. Five fresh exact-one
Detour runs (rounds 02-06) passed
with identical decisive telemetry: conflict steering `36.00/11.82 deg`,
pair-over-solo lateral deviation `128.44/19.17 uu`, live crowd registration and
data `1/1` for each pair agent, minimum clearance `72.10 uu`, maximum stall
`0.017 s`, and maximum frame step `4.75/3.83 uu`. Four admission-only controls
failed exactly their assigned gates without harness failures: no avoidance,
freeze one, collision disabled, and permanent detour. Thresholds are frozen.
The reference is closed while the live accepted asset remains the byte-exact
empty baseline. The scoped task substrate was published and committed as
`4ad7763bdaf352c7228d1b5b7260c07cd8cfbb94`, then both canonical legs were
rerun from Git HEAD on 2026-08-21.

The final map has SHA-256
`9B339F34123443B51B680D371FB5D3EC232576B30CF562100AF97946D9AA9347`.
Its fresh cold readback is
`<run-out>/readback.log`. The
reference asset has SHA-256
`9DF32A29EAF5D318CA2D89B6AC8E0E4643718A1D6E2EC0F169C1DD5C23A0D982`;
the retained live baseline remains
`804F3DBC239C376A7115EBEE627E1CF0018C5C5B8CB9194FABD00FD52AD8DE49`.

## Locked design

- Surface: one Blueprint asset at
  `/Game/Tasks/t3-both-walkers-yield-and-still-arrive/BP_YieldingWalker`.
- Admission asset:
  `/Game/__CraftBenchAdmission/t3-both-walkers-yield-and-still-arrive/BP_YieldingWalker_Admission`.
- Final map: `/Game/Maps/t3-both-walkers-yield-and-still-arrive/L_BothWalkersYield`.
- Admission map:
  `/Game/Maps/t3-both-walkers-yield-and-still-arrive/L_BothWalkersYieldAdmission`.
- Final fixtures: `ABothWalkersYieldLayoutAFunctionalTest` and
  `ABothWalkersYieldLayoutBFunctionalTest`; admission fixture:
  `ABothWalkersYieldAdmissionFunctionalTest`.
- The empty baseline and reference have the same Blueprint parent, visible
  mesh, animation, collision, and empty graphs. The accepted Blueprint class
  default selects the ordinary supplied controller for empty or Unreal's
  `ADetourCrowdAIController` for reference. CharacterMovement RVO stays off in
  both so only one engine avoidance backend owns velocity.

## UE 5.8.1 API audit

| Surface | Local source evidence | Task use |
|---|---|---|
| `ACharacter::AIControllerClass` | public editable class default | baseline selects the supplied ordinary controller; reference selects the engine Detour Crowd controller |
| `ADetourCrowdAIController` | public engine controller using `UCrowdFollowingComponent` | the single authored avoidance system |
| `UCrowdManager::GetCurrent` / `IsAgentValid` | public world-owned manager and registration query | independent live agent registration evidence |
| `UCrowdFollowingComponent` live getters | public simulation/avoidance/location/velocity/collision facts | engine-owned crowd data evidence |
| `UCharacterMovementComponent::bUseRVOAvoidance` | public editable property, pinned false | prevents stacking CharacterMovement RVO over Detour Crowd |
| `UPathFollowingComponent::GetCurrentDirection` | public current global path-segment direction | pre-avoidance path vs actual conflict steering |
| `AAIController::MoveToLocation` | public exported request API | four simultaneous independent moves |
| `AAIController::GetMoveStatus` | public path status | progress and arrival telemetry |
| `UNavigationSystemV1::Build` | public synchronous editor build path | deterministic authored navigation |
| `ARecastNavMesh::GetNumActiveTiles` | public read | cold-map and runtime nav readiness |

Engine source inspected under `<UE-root>`, engine 5.8.1. The task uses the
already-direct `Engine`, `AIModule`, `NavigationSystem`, `BlueprintGraph`, and
`KismetCompiler` dependencies; no shared Build.cs or `.uproject` edit is
expected.

## Two world-fact groups

Layout A is an orthogonal equal-distance crossing with unequal speeds and body
radii. Layout B is rotated and uses different path lengths, speed ordering,
and radii. In each group the two solo controls are translated copies of the two
pair paths and are separated from every conflict. The map owns all start/goal
transforms and scenario numbers; the fixture reads them and never substitutes
hardcoded transforms.

## Admission result

The admission distribution and controls are recorded in
`authoring/admission_calibration.json`. Frozen bars remain deliberately below
the weakest positive margin and above measured motion noise: `3.0 deg`
steering, `1.5 deg` pair-over-solo steering, `12 uu` pair-over-solo lateral,
`4 uu` clearance, `0.75 s` stall, `28 uu` frame step, and `115 uu` arrival.

Certified production reference evidence is
`<run-out>/report.json`: Git-HEAD
substrate `4ad7763bdaf3`, L1 passed both Editor and Game with zero agent-file
warnings, and L2 passed both layouts (2/2). The independent certified
baseline-only control is
`<run-out>/report.json`: the same Git-HEAD
substrate and two L1 targets passed with zero warnings, while both L2 fixtures
failed only `BothAgentsConflictDrivenSteering`, with no harness-precondition
failure. The remaining external promotion boundary is owner-play/refgate and
the eventual merge to the `craftbench-public` branch.

## Checklist

- [x] Formal task, world facts, named gates, and anti-gaming pre-mortem.
- [x] Task-local runtime, fixture, asset/map author helpers, cold introspector,
  fail-closed admission runner, and offline contract tests are present.
- [x] Initial Editor build and corrected Detour/control rebuilds.
- [x] Baseline/admission assets author and fresh cold readback.
- [x] Admission map author and cold readback.
- [x] Admission behavior/calibration: five positive passes and four named
  negative controls.
- [x] Final map and reference harvest/restore; live baseline restored exactly.
- [x] Committed Git-HEAD production reference/empty discrimination.
- [ ] Owner-play and refgate.
