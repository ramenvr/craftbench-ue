# gp-spawner-population — discrimination matrix

**Status (2026-08-17): MEASURED, and the measurement found a defect in the task.** This
package is the task's first — it previously had **no `discrimination/` directory at all**
(dossier verdict `NO-EVIDENCE`). Each leg is a byte-exact copy of `../reference` carrying a
single behavioural change.

First `cb discriminate` run: **`discriminated: NO`, exit 1.** After the fix below, the re-run returned **`discriminated: YES`, 5/5 legs credited, exit 0.**

Originally: Four of five legs credited;
the radius leg returned `PASS(unexpected-pass)`. The variant was not at fault — **the
radius gate is dead**, because the host actor reports the world origin just as a rootless
minion does. Full evidence in *MEASURED DEFECT* below; the leg was replaced with
`far-offset-spawn/`, which trips that gate regardless of what the host reports.

| leg | state |
|---|---|
| `../reference`, `empty` | measured, credited |
| `static-population/`, `respawn-during-teardown/` | **measured, credited** — gate-order traces confirmed |
| `far-offset-spawn/` | **measured, credited** — re-run after the finding: `discriminated: YES`, 5/5 |

**Why three variants.** The fixture has four agent-reachable gates and the `empty` leg can
only reach the first, so the three variants take the other three — one gate each, no two
sharing a failure literal. That was the selection rule, not the anti-gaming note count.

| Submission | Overall | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | **PASS** | — | all 3 checkpoints green (1/1) | — (PASS oracle) |
| empty (no overlay → scaffold stub) | **FAIL** | checkpoint 0 (t=0.5s), count gate | ` SpawnedMinion actor(s) spawned on BeginPlay; found ` | FR-017 empty. The stub has no `BeginPlay`, so 0 minions exist and the FIRST gate fires |
| `far-offset-spawn/` | **FAIL** | checkpoint 0 (t=0.5s), **radius gate** | ` units from the spawner (limit ` | #3, *dumped-at-a-fixed-point* half only. MEASURED 2026-08-17. One delta: the spawn ring is ten times the intended radius (a units/scale slip — reading "500" as metres), at a FIXED distance rather than a random one so every minion lands 5000 units out. Each minion still gets a real scene root, so its location is genuinely read back. The count gate ahead of it PASSES on purpose (5 correctly-tagged actors exist), so the radius gate is the first this submission can trip, and it trips **regardless of where the host reports itself** — which is the property the leg it replaced did not have (see the dead-gate finding below) |
| `rootless-minions/` | **FAIL** | checkpoint 0 (t=0.5s), **spread gate** | `SpawnedMinion actor(s) occupy the same position` | #3, the *rootless* half — UNDEFENDED until 2026-08-19. One delta: the spawned `AActor` never gets a scene root, so `GetActorLocation()` reports `(0,0,0)` and `SetActorLocation` is a silent no-op. **Deleted 2026-08-17 because it PASSED** — the radius gate compares the host's location to each minion's and the scaffold host has no root either, so it computed `Dist(origin,origin)=0`. The spread gate catches it: five minions on one identical point are not five random ones. Restored as that gate's proof. **MEASURED 2026-08-19: FAILs at the spread gate** — its first run credited nothing only because this row was missing. |
| `static-population/` | **FAIL** | checkpoint 1 (t=1.5s), respawn gate | `after destroying one child, expected the population to return to ` | #4 no respawn (static population). **MEASURED 2026-08-17 — credited.** One delta: `OnMinionDestroyed` still runs and still keeps the tracking array honest, but never spawns a replacement. Checkpoint 0 is byte-for-byte reference behaviour (5 minions, all in radius), so both gates ahead of it PASS; the fixture destroys one child and checkpoint 1 reads 4 |
| `respawn-during-teardown/` | **FAIL** | checkpoint 2 (t=2.5s), cleanup gate | `after destroying the spawner, expected 0 SpawnedMinion actor(s); found ` | #5 no cleanup, **subtle half**: the parenthetical "a solution that respawns *during* its own teardown also fails this checkpoint". **MEASURED 2026-08-17 — credited.** One delta: the `bShuttingDown` guard is gone, so the respawn is unconditional. This submission implements **all three required behaviours** and passes checkpoints 0 and 1 indistinguishably from the reference; `EndPlay`'s destroy loop then re-enters `OnMinionDestroyed`, which respawns. The loop iterates a *snapshot*, so the 5 replacements are never destroyed and checkpoint 2 reads 5 |

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous literal from a
`FinishTest(EFunctionalTestResult::Failed, …)` call in the fixture, never spanning a
printf placeholder. Layers are `[L1, L2]` — there is no L2I grader here. The checkpoint
schedule is sequential and any `FinishTest` ends the run, so **every later gate is skipped
once an earlier one fires**.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed spawning actor stays discoverable (exactly one) | fully | resolve gate (`PrepareTest`) — `Expected exactly one actor tagged 'SpawnerRoot' in the test level; found ` | unconditional (first gate) | nothing at authoring time — the tag is on the placed instance in the verifier-owned map; only runtime destruction/duplication trips it, and that fails here |
| 2 | spawn **exactly five** additional actors | fully | cp0 count gate — ` SpawnedMinion actor(s) spawned on BeginPlay; found ` | row 1 | — (an exact count, so both under- and over-spawn fail) |
| 3 | spawn them **after gameplay begins**, *immediately* | partially | the cp0 count gate doubles as the timing gate: the population must already be 5 at t=0.5s | row 1 | up to ~0.5s of latency is invisible — a solution that spawns on a 0.4s timer instead of in `BeginPlay` passes. "Immediately" is gated only to half-second resolution |
| 4 | each at a location **within 500 units** of the spawning actor | partially — see the dead-gate finding | cp0 radius gate — ` units from the spawner (limit ` | row 1, and the cp0 count gate fires first | the limit is 650, not 500, so a solution spawning at radius 500–650 passes — deliberate calibration slack, documented in the spec |
| 5 | each at a **random** location | **NOT ASSERTED** | — (no gate compares minion positions to each other or across runs) | — | **HOLE**: five minions at one identical hard-coded point 100 units from the host pass every gate. Randomness, and even distinctness, is decorative under this fixture. Closing it needs a spread/uniqueness assertion the fixture does not make |
| 6 | each spawned actor carries the tag `SpawnedMinion` | fully, structurally | not a separate gate — the tag IS the counting mechanism (`GetAllActorsWithTag`), so an untagged minion is invisible and reads as a count shortfall at the cp0 gate | row 1 | tagging an actor that is not one of its spawns is not distinguished here — see row 8 |
| 7 | if any spawned actor is destroyed, spawn a replacement so five exist again shortly after | partially | cp1 respawn gate — `after destroying one child, expected the population to return to ` | rows 1–2, cp0 radius | only **one** destruction, of `Minions[0]`, is ever probed, once. A solution that replaces only the first-destroyed child, or that can respawn exactly once, passes. Repeated or simultaneous destruction is never driven |
| 8 | when the spawning actor is destroyed, **all of its** spawned actors are removed | partially | cp2 cleanup gate — `after destroying the spawner, expected 0 SpawnedMinion actor(s); found ` | rows 1–2, cp0 radius, cp1 respawn | the gate counts `SpawnedMinion` actors **world-wide**, not ownership: a solution that destroys every tagged actor it did not spawn would also pass. Ownership is a behavioural proxy here, which is the correct reading of a behaviour-only prompt |
| 9 | teardown must not re-trigger the respawn (implied by rows 7+8 together) | fully | the same cp2 cleanup gate — a teardown cascade that respawns leaves 5, not 0 | rows 1–2, cp0–cp1 | — (this is the requirement `respawn-during-teardown/` was authored to prove is gated) |
| 10 | solve in C++ on the existing class | fully, by L1 + the substrate model | not a `FinishTest` gate — the committed map places the C++ `ASpawnerActor`, so logic in a never-placed Blueprint subclass never executes, and the L1 dual-target build must exit 0 | unconditional | adding private members/helpers to the header is free (the spec allows it); subclassing is tolerated by design, since identity is by tag |

### MEASURED DEFECT — the radius gate cannot catch a rootless spawn, and anti-gaming note #3 says it can

**Found by a `[BAD]` leg, 2026-08-17.** The first version of the radius leg was
`rootless-minions/`: spawn the five `AActor`s and never give them a scene root, so
`GetActorLocation()` reports the origin. `cb discriminate` returned
**`PASS(unexpected-pass)`** for it — `discriminated: NO`, exit 1.

The cause is not the variant. It is the gate:

1. **A rootless actor really does report the origin.** UE 5.8 `Actor.h:4465` —
   `TemplateGetActorLocation` returns `FVector::ZeroVector` when `RootComponent` is
   null. So the minions were where the leg intended.
2. **The HOST reports the origin too, for the same reason.** The scaffold
   `ASpawnerActor` (`UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/SpawnerActor.cpp`)
   creates no root component at all — its constructor only enables tick and adds the
   `SpawnerRoot` tag. `PrepareTest` caches `SpawnerLocation = Found[0]->GetActorLocation()`,
   which is therefore `(0,0,0)`.
3. So the gate computed `Dist((0,0,0), (0,0,0)) = 0`, comfortably inside the 650 limit,
   and the leg passed every checkpoint.

**What is therefore false, in three places, all saying the same wrong thing:**

- `task.md` anti-gaming note 3 — *"the host is placed off the origin and the verifier
  asserts each minion is within 650 units of the host; origin-located minions are
  ~thousands of units away and fail."* They are 0 units away.
- the same claim in the spec's **Pass criteria** paragraph ("places the host OFF the
  world origin so a rootless 'minion' reporting (0,0,0) lands far outside the limit").
- the fixture's own source comment (`SpawnerPopulationFunctionalTest.cpp:26-28`),
  which is where the belief presumably started.
- and `cameras.json` (the camera-plan lane; not part of this release)'s note that the host sits at `(1500,500,100)`. Whatever the map
  binary stores, an actor with no root has no transform to report, so every
  `frame_subject` shot keyed on `SpawnerRoot` also resolves to the origin.

**Why no earlier run caught it.** The reference passes this gate whatever the host
reports, because it offsets its minions from `GetActorLocation()` — the same value the
fixture compares against. Origin-vs-origin and (1500,500,100)-vs-(1500,500,100) are
indistinguishable to a reference-only check. It took a leg that *should* have failed.

**The fix is a substrate change and therefore an owner decision.** Giving the scaffold a
root component (`CreateDefaultSubobject<USceneComponent>`) would make the host's placement
real, restore the note's reasoning, and revive the gate — but it changes the class every
submission inherits, so it is a contract change under D6, not an authoring fix. **CLOSED 2026-08-19, without the substrate change.** Rather than give the scaffold a
root component (a D6 contract change to the class every submission inherits), a
SPREAD gate was added at the same checkpoint: at least two of the five minions must
occupy distinct positions, read from the coordinates the radius loop already walks.
Five locationless minions all report the origin, so they fail there instead. That
also closes requirements row 5 (`random` placement) in its weakest honest form —
any distribution passes, only identical placement fails. `rootless-minions/` is
restored above as the gate's proof, and the radius gate's own comment now records
what it cannot see.

### Escalation notes (holes the table found)

- **Row 5 (`random`) is the one real hole**, and it is the only prompt requirement here
  with *no* assertion behind it. It is also the only one no variant can probe: a variant
  demonstrates that a gate catches a defect, and there is no gate to catch. Closing it
  needs a fixture change — the cheapest sound one is asserting that the five minions
  occupy at least two distinct locations, which rejects the hard-coded-point solve
  without over-fitting to any particular distribution.
- Rows 3, 7 and 8 are partial in ways that are **defensible for a behaviour-only prompt**:
  each gates the observable consequence rather than the mechanism. Row 7's single
  destruction is the weakest of the three — a second destroy/re-check pair at a fourth
  checkpoint would upgrade it to "any", and would cost one checkpoint.
- No gate reads a minion's mesh, class, or components, so the reference's marker cube is
  correctly non-load-bearing. A submission that spawns invisible minions passes, by design.

## Bounded coverage (honest note)

Reference (PASS), empty (FAIL), `static-population/` and `respawn-during-teardown/` are all
**measured** through the deterministic verifier — the latter two credited at their named
substrings on the 2026-08-17 run, confirming both gate-order traces. `far-offset-spawn/` is **measured and credited** — the re-run returned
`discriminated: YES` with all five legs green.

Notes #4 and #5-subtle are therefore proven defended. Note #3 is **half** proven: the
dumped-at-a-fixed-point route is caught (that is what `far-offset-spawn/` targets), and the
**rootless route is not caught at all** — measured, not argued. Notes #1 (spawn one and stop)
and #2 (over-spawn) both die at the *same* cp0 count gate the `empty` leg already credits, so
authoring them would add legs sharing one substring and isolate nothing.

What this package does NOT establish, stated plainly:

- that a **rootless** spawn is rejected — it is not, and the dead-gate finding above says why;
- that the fixture rejects a **non-random** spawn (row 5 — nothing asserts it);
- that respawn survives anything beyond a single destruction of the first child (row 7);
- (closed) `far-offset-spawn/` credited exactly as traced on the re-run.
