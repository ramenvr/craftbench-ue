# CraftBench Task Catalog

> **What this is.** What each benchmark task evaluates, and how the
> deterministic verifier grades it. CraftBench tasks are *behavior-only*
> prompts — the prompt never names a class, plugin or design pattern; the agent
> chooses the implementation and the verifier checks observable behavior.

## The task tree

**117 task specs** in four directories. The paper's benchmark is the 70 in `cpp/`, `bp/` and `python/`; the 47 in `craftbench-public/` are not part of that study. Three are keyed on what the agent has to
write; the fourth is not a basket at all and its README says so before you try
to "fix" it into one.

| directory | n | the deliverable |
|---|---|---|
| `tasks/cpp/` | 33 | C++ source in the agent-writable module |
| `tasks/bp/` | 25 | a Blueprint / asset / editor artifact |
| `tasks/python/` | 12 | editor-scripting, graded by the same deterministic `L2I` lane as `bp/` |
| `tasks/craftbench-public/` | 47 | mixed — this directory is keyed on disclosure status, not deliverable |

The layout contract, and the rules each directory carries, are in
[`tasks/README.md`](README.md).

### Every task, by directory

The full roster. `tasklint` checks this list against `git ls-files` on every
CI run, so a task that exists on disk and is missing here is a build error.

<details>
<summary><code>tasks/cpp/</code> — 33 tasks</summary>

- `gp-crafting-queue`
- `gp-dot-aoe-burn-cpp`
- `gp-double-jump-stamina-cpp`
- `gp-glide-stamina-cpp`
- `gp-harvestable-regrow`
- `gp-heal-over-time-cpp`
- `gp-health-attribute-ops-cpp`
- `gp-inventory-stacking`
- `gp-poison-dot-stack-cpp`
- `gp-spawner-population`
- `t0-sanity-log-on-beginplay`
- `t1-data-asset-drives-speed`
- `t1-datatable-drives-value`
- `t1-default-cube-mesh-actor`
- `t1-extraction-volume-per-actor-trigger`
- `t1-gameplay-tag-gate`
- `t1-movement-component-drives-actor`
- `t1-mud-wade-cpp`
- `t1-overlap-logs-once`
- `t1-overlap-teleport-portal`
- `t1-physics-drop-and-rest`
- `t1-screen-tint-cpp`
- `t2-gravity-floating-pawn-movement`
- `t2-homing-projectile`
- `t2-hud-layout-and-countdown`
- `t2-ladder-climb-volume`
- `t2-melee-ability-with-cooldown`
- `t2-npc-follows-player`
- `t2-race-clock-cpp`
- `t2-timeline-color-cycle`
- `t2-weapon-fire-animation-on-trigger`
- `t3-gate-and-door-cpp`
- `tp2-sprint-stamina`

</details>

<details>
<summary><code>tasks/bp/</code> — 25 tasks</summary>

- `gp-additem-stack-fix-bp`
- `gp-door-hitch-fix-bp`
- `gp-dot-aoe-burn-bp`
- `gp-double-jump-stamina-bp`
- `gp-glide-stamina-bp`
- `gp-heal-over-time-bp`
- `gp-health-attribute-ops-bp`
- `gp-poison-dot-stack-bp`
- `t0-sanity-bp-log-on-beginplay`
- `t1-blueprint-event-to-action`
- `t1-blueprint-graph-on-beginplay`
- `t1-dawn-fog-lighting-rig`
- `t1-hero-blueprint-copy-with-flashlight`
- `t1-mud-wade-bp`
- `t1-playable-level-bootstrap`
- `t1-screen-tint-bp`
- `t1-third-person-chase-camera`
- `t1-walk-animation-footstep-cues`
- `t2-consistent-enum-names`
- `t2-cutscene-camera-push-and-hero-rise`
- `t2-datatable-csv-export`
- `t2-race-clock-bp`
- `t2-weapon-held-in-right-hand`
- `t3-gate-and-door-bp`
- `t3-piercing-projectile`

</details>

<details>
<summary><code>tasks/python/</code> — 12 tasks</summary>

- `kp-anim-track-bake`
- `kp-blueprint-actor-audit-report`
- `kp-character-boom-and-movement`
- `kp-config-source-audit`
- `kp-derived-class-search`
- `kp-engine-source-search`
- `kp-fog-and-postprocess-rig`
- `kp-motion-set-shares-one-rig`
- `kp-retarget-maps-two-rigs`
- `kp-routine-usage-search`
- `kp-spawn-level-actors`
- `kp-typed-input-bindings`

</details>

<details>
<summary><code>tasks/craftbench-public/</code> — 47 tasks</summary>

- `t1-door-stays-open-while-you-stand-on-the-plate`
- `t1-guard-only-spots-what-it-can-see`
- `t1-guard-patrols-until-the-alarm-then-chases`
- `t1-pad-throws-you-up-on-contact`
- `t1-shoved-block-slides-on-one-rail`
- `t1-spikes-hurt-you-and-you-respawn-at-your-marker`
- `t1-touched-crate-lights-up`
- `t1-walks-around-the-marked-ground-to-the-goal`
- `t2-alarm-escalates-and-cools-down`
- `t2-bridge-only-holds-what-it-can-bear`
- `t2-collect-then-exit`
- `t2-crate-you-carry-changes-what-you-can-do`
- `t2-each-catalog-reader-reports-only-its-own-records`
- `t2-guard-goes-to-where-it-last-saw-you`
- `t2-menu-blocks-gameplay-and-restores-it-exactly`
- `t2-one-bundle-loads-without-pulling-in-the-rest`
- `t2-only-the-wing-you-called-opens`
- `t2-shared-helper-lives-until-the-last-lease-ends`
- `t2-shop-takes-your-coins-and-remembers`
- `t2-the-crew-arrives-and-thins-out`
- `t2-top-screen-keeps-focus-until-dismissed`
- `t2-turret-leads-you-and-holds-fire`
- `t3-alert-state-swaps-the-upper-body-without-breaking-stride`
- `t3-alerted-crowd-shares-live-poses-by-state`
- `t3-both-hands-follow-the-physics-driven-handle`
- `t3-both-walkers-yield-and-still-arrive`
- `t3-checkpoint-restores-the-world`
- `t3-dash-responds-now-and-converges-later`
- `t3-each-local-player-owns-its-top-modal`
- `t3-every-player-sees-the-same-door-state`
- `t3-filtered-points-and-visible-instances-stay-in-lockstep`
- `t3-forge-turns-what-you-bring-into-what-you-need`
- `t3-guard-aims-only-at-the-visible-target`
- `t3-hold-the-marks-in-the-order-given`
- `t3-keyring-opens-what-it-was-cut-for`
- `t3-lift-serves-its-calls-in-order`
- `t3-only-the-near-active-sector-exists`
- `t3-only-the-requested-district-enters-and-leaves-the-world`
- `t3-reach-the-exit-before-they-see-you`
- `t3-the-guard-resumes-patrol-after-the-chase`
- `t3-the-old-world-cannot-complete-into-the-new-one`
- `t3-the-round-number-everyone-agrees-on`
- `t3-the-run-resumes-at-the-latest-marker-without-paying-twice`
- `t3-the-worker-keeps-its-new-plan-after-the-signal`
- `t3-the-yard-remembers-after-you-leave`
- `t3-walkable-ground-follows-the-designated-scout`
- `t3-your-last-life-ends-the-run`

</details>

## Verifier layers (legend)

- **L1** — UBT build of both `<Module>Editor` and `<Module>` (Game) targets; both must exit 0.
- **L2** — `AFunctionalTest` driven in a real headless PIE world; finds actors **by tag** (never class), samples runtime state at a fixed **checkpoint schedule**, fixed-timestep determinism (`-deterministic -FPS=<n>`).
- **L2I** — Headless editor-Python **structural introspection** of a generated `.uasset` (material-graph walk / widget-tree / AnimBP state machine). No render, fully deterministic.
- **ART** — Build-floor + artifact-present check only (used by advisory tasks).
- **R2** — **Non-gating** advisory LLM-judge ensemble — annotates a rubric score; never changes PASS/FAIL.

## How to check a task, rather than trust a summary

Every task carries its own evidence next to it, so nothing here has to be taken
on faith:

- **`tasks/<set>/<id>/discrimination/MATRIX.md`** — the discrimination record:
  which wrong-or-gaming variants were tried, which named assertion caught each
  one, and when that was last run. This is the per-task authority.
- **`cb discriminate`** re-runs that matrix yourself: the reference must PASS
  and every variant must FAIL, each by its own named assertion.
- **`cb batch-eval --references all`** grades every committed reference
  solution in one sweep.

These are deterministic and token-free — they need a UE 5.8 install and nothing
else.

> **A caveat worth stating plainly: a task passing its discrimination matrix is
> not the same as a task being un-gameable.** The matrix proves the verifier
> rejects the specific wrong answers its author thought of. An earlier
> adversarial audit of a since-retired task set did find gaming axes that the
> matrices had missed. **No currently-shipping task has been adversarially
> audited.** Treat the matrix as a floor, not a guarantee, and if you find an
> axis a task does not close, that is a genuinely useful issue to file.

## Task TLDRs

Long-form TLDRs exist for the tasks below; the rest of the tree is documented
by its own `task.md` and `discrimination/MATRIX.md`.

| task | basket | layers | category | evaluates |
|---|---|---|---|---|
| `gp-dot-aoe-burn-cpp` | cpp | L1+L2 | gameplay | Whether an agent can make one system act on OTHER entities selectively: an activatable ability that creates a burning area, damaging characters inside it periodically for a set duration while leaving characters outside untouched. The first WORLD-ACTING family — the targets are verifier-owned, so a submission cannot pre-rig them. |
| `gp-dot-aoe-burn-bp` | bp | L1+L2+L2I | gameplay | The Blueprint twin of the above: same fixture, same map, same gates, but the deliverable must be a Blueprint asset and an L2I leg structurally proves it. |
| `gp-spawner-population` | cpp | L1+L2 | gameplay | Whether an agent can spawn and maintain a fixed population of runtime actors: five within radius on BeginPlay, respawn on destroy, cleanup when the spawner dies (g2-4 "Spawner" port)… |
| `t0-sanity-log-on-beginplay` | cpp | L1+L2 | gameplay | Tests whether the verifier framework itself (L1 build + L2 PIE behavioral trace) wires end-to-end and can dis… |
| `t1-hero-blueprint-copy-with-flashlight` | bp | L1+L2I | other | Whether an agent can copy a shipped game-object asset, re-base the copy onto the engine's standard humanoid locomotion, and mount a cone light beneath the inherited animated body part at a non-default brightness — while leaving the source asset untouched. **The repo's first `L2I` task to grade**… |
| `t1-dawn-fog-lighting-rig` | bp | L1+L2I | lighting | Whether an agent can build a single placeable asset that lights an unlit level as a foggy early dawn — four named parts (sky/ambient/sun/fog), each graded on numeric property bands that were dead-gate audited against the UE 5.8 engine default they must exclude… |
| `t1-third-person-chase-camera` | bp | L1+L2I | other | Whether an agent can convert a first-person character asset to a third-person chase view in place: add a trailing boom off the collision body at a fixed length/offset/catch-up rate, re-parent the camera onto the boom's far end, and stop the camera aiming on its own… |
| `t1-walk-animation-footstep-cues` | bp | L1+L2I | animation | Whether an agent can place exactly two instantaneous, identically-named cues on one animation clip at fixed times without retiming the clip — and leave the sibling clip completely silent… |
| `t2-cutscene-camera-push-and-hero-rise` | bp | L1+L2I | other | Whether an agent can author a self-contained cutscene asset from nothing: fixed duration and frame rate, its own spawned cinematic camera held for the whole shot, a camera push-in and a hero rise on separate transform tracks, and an opening fade. The only task of that import shipping no baseline asset… |
| `t2-consistent-enum-names` | bp | L1+L2I | other | Whether an agent can perform a reference-preserving rename: derive four convention-correct enumeration names from a stated convention plus worked examples, apply them to live assets, and leave both consuming Blueprints resolving onto the new packages. The only task declaring `allow_redirectors`, and the only one graded as a tri-state closure over asset-registry state… |
| `t2-weapon-held-in-right-hand` | bp | L1+L2I | other | Whether an agent can coordinate three edits across two asset families: add a zero-offset attachment point on the right-hand joint of a skeleton, add a static cube part to the character asset, and mount that part on the animated body at the new attachment point… |

---

### `gp-spawner-population`  · ps-actors
- **Evaluates:** Whether an agent can spawn and maintain a fixed population of runtime actors: spawn exactly five children at random locations within a radius on BeginPlay, respawn a replacement whenever one is destroyed, and remove all of them when the spawner itself is destroyed. Port of the g2-4 "Spawner" eval prompt; probes runtime `SpawnActor` + delegate-driven lifecycle — any mechanism (destroyed-delegate, Tick, or timer) that satisfies the observables passes.
- **Prompt:** A placed actor must, after gameplay begins, immediately spawn exactly five actors at random locations within 500 units, tag each SpawnedMinion, spawn a replacement whenever one is destroyed (back to five shortly after), and remove all of them when it itself is destroyed.
- **Verifies:** L1 (UBT build, both targets) + L2 (PIE-native AFunctionalTest). Checkpoints at 0.5/1.5/2.5s: expect exactly 5 SpawnedMinion within 650 units on BeginPlay (then the fixture destroys one), 5 again after respawn (then it destroys the host), 0 after host cleanup. Host placed off the world origin so a rootless (0,0,0) spawn fails the radius check.
- **Anti-gaming:** spawn-one-and-stop fails the exact-5 count; over-spawn loop fails every exact count; rootless/wrong-location spawn fails the 650-unit radius; no-respawn fails the 1.5s checkpoint; no-cleanup (or respawn-during-teardown) fails the 2.5s checkpoint (forcing a shutdown guard).
- **Evidence on disk:** `discrimination/MATRIX.md` in this task's folder records the matrix and when it was run. Fixture `SpawnerPopulationFunctionalTest`, the reference solution and `L_SpawnerPopulation.umap` are all committed; the grade materializes from git HEAD, and `CraftBenchTests` changes are review-gated on commit. Re-run it yourself with `cb discriminate`.
### `t0-sanity-log-on-beginplay`  · ps-actors
- **Evaluates:** Tests whether the verifier framework itself (L1 build + L2 PIE behavioral trace) wires end-to-end and can distinguish a correct submission from an empty one. BeginPlay-window log capture is non-trivial because constructor-time logs and wrong-category logs must be rejected, and logs must fire exactly once, not multiple times.
- **Prompt:** Override BeginPlay on a placed actor to emit exactly one log line "CRAFTBENCH_SANITY_OK" to LogTemp on the first frame of gameplay.
- **Verifies:** L1 + L2: UBT builds CraftBenchTemplateEditor target with zero new warnings; L2 fixture runs in PIE, binds log listener to LogTemp/Display AFTER world spawn but BEFORE first tick, advances one frame, and asserts CapturedLogCount == 1 (catches constructor-time logs, wrong categories, and per-tick repeats). Identity lookup by SanityRoot tag, not class name.
- **Anti-gaming:** Empty BeginPlay passes L1 but L2 asserts CapturedLogCount == 1; constructor-time logs are filtered by binding listener after world spawn; wrong log categories are filtered by LogTemp binding; multiple emits fail == 1 check; test tampering never reaches the grade — the CraftBenchTests module sits outside the agent-writable path, the runner grades from git HEAD, and committed changes to it are review-gated (on commit).
- **Evidence on disk:** the reference solution is at `tasks/cpp/t0-sanity-log-on-beginplay/reference/` and the L2 fixture at `Source/CraftBenchTests/Tasks/t0-sanity-log-on-beginplay/` (the per-task-layout template). The spec self-declares as the smoke task for the verifier framework. Re-run it yourself with `cb discriminate`.
