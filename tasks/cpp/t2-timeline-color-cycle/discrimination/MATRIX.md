# Discrimination matrix — t2-timeline-color-cycle

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted gate, via the named
assertion**. A wrong-reason FAIL (compile error, wrong gate, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-timeline-color-cycle/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/CraftBenchTemplate/Tasks/t2-timeline-color-cycle/…`
  — the one correct solution (BeginPlay MID + per-tick piecewise lerp).
- `<variant>/Source/CraftBenchTemplate/Tasks/t2-timeline-color-cycle/…`
  — one dir per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | both checkpoints green | — |
| empty | FAIL | checkpoint 0 (t=1.0s) | `no readable CycleColor parameter on the actor's mesh material` | #1 / FR-017 |
| `static-color/` | FAIL | checkpoint 1, gate 1 | `the color never changes` | #1 set-once color |
| `snap-cycle/` | FAIL | checkpoint 1, gate 2 | `the color snaps instead of blending smoothly` | #2 snap cycling |
| `wrong-order/` | FAIL | checkpoint 1, gate 3 | `does not cycle through green, blue and red in order` | #3 wrong sequence |
| `stops-after-one-cycle/` | FAIL | checkpoint 1, gate 5 | `the color stops cycling partway` | #4 one-pass-and-stop |

Coverage note: the gate order at cp1 (readability → movement → smoothness →
order → period → continuity) is deliberate so each variant dies at ITS gate:
a static color must not reach the order gate, and a snap cycle must not be
credited to it either. `stops-after-one-cycle` survives gates 1-4 by
construction — it changes, blends smoothly, in the right order, and its one
full interior run (~1.7s) sits inside the period band — leaving exactly 2
window transitions (blue→red→frozen-green in the [1.0, 10.0]s window) vs the
floor of 3, so gate 5 is the first to fire. Gate 4 (period,
`the cycle period is far from the required six seconds`) has no dedicated
variant: a wrong-period cycle is a spec miss rather than a gaming shape, and
the gate is argued from its named assertion (band [1.2s, 3.2s] on the median
FULL interior run vs the reference's ~1.7s; a 2s-period cycle runs ~0.57s and
an 18s one ~5.1s). Gate 0 (`no color samples could be read`) is a
sentinel-hygiene guard behind cp0's readable gate, not a distinct gaming
shape. Two residuals accepted by design and stated honestly: (a) a cycle
stepped FINER than the 0.15/frame cap but coarser than true blending (e.g.
0.1 steps every few frames) passes the smoothness gate — at that amplitude
the motion is indistinguishable from slightly-quantized blending at this
frame rate; the cap bounds snap amplitude, it does not forbid quantization
metaphysically. (b) LOW-AMPLITUDE cycles pass: the movement floor (0.2) and
dominance margin (0.15) mean a cycle between ~0.21-amplitude near-black
colors grades identically to the full-amplitude reference — the gates judge
shape, order and timing, not brightness; a pixel-level amplitude gate would
need the render track (non-gating by FR-020d).

## How to run (deterministic verifier, no agent, no tokens)
The one-command form runs the whole matrix (reference → PASS, implicit empty →
FAIL, every variant → FAIL matched against its named substring):
```sh
cb discriminate --task cpp/t2-timeline-color-cycle          # committed task
cb discriminate --task cpp/t2-timeline-color-cycle --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH; UE root per this box's `.env` / `CB_UE_ROOT`):
```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t2-timeline-color-cycle/task.md \
    --submission tasks/cpp/t2-timeline-color-cycle/discrimination/snap-cycle \
    --ue-root "$CB_UE_ROOT" --substrate-from-live --workdir C:\cb\wd\colorcycle   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-30 (text half + adversarial-review fixes same day).
- **EXECUTED 2026-07-30**: `cb discriminate --task cpp/t2-timeline-color-cycle --wip` =
  **discriminated: YES** — reference PASS; empty, static-color, snap-cycle, wrong-order, stops-after-one-cycle all FAIL (6/6), each `[ok ]` (credited via its named
  substring). Calibration record in ../notes.md.

# cpp/t2-timeline-color-cycle — requirements-table draft (to be appended to discrimination/MATRIX.md)

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the FIXTURE rows (1-8) is a contiguous
`FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t2-timeline-color-cycle/ColorCycleFunctionalTest.cpp`
(never spanning a printf placeholder; ASCII-only per the cp1252 log read-back rule).
Rows 9-12 are structural/layer rows with NO fixture literal; every backticked
span in those rows is verbatim-greppable in the additional source the row
names: the scaffold header
`UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/Tasks/t2-timeline-color-cycle/ColorCycleActor.h`,
the sandbox manifest `UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json`, the
task spec's L1 block (`tasks/cpp/t2-timeline-color-cycle/task.md`), and the L2
launcher `tools/verify-single/layers/l2_pie.py`. One composed exception,
marked "(composed)" in row 10: the two L1 target names are runtime-assembled
by `tools/verify-single/layers/l1_build.py` line 273 —
`targets = (f"{game_module}Editor", game_module)` — from the manifest's
`game_module` value ("CraftBenchTemplate"); the assembled names quoted in
row 10 are contiguous in task.md's L1 block.
The task's layers are `[L1, L2]` and the front-matter carries no `introspect:` key,
so the L2 fixture plus the L1 build verdict are the ONLY gate families — there is no
L2I grader for this task.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the level's display actor (tagged `ColorCycle`) stays a single live instance for the whole run | fully | resolve gate — `Expected exactly one actor tagged 'ColorCycle' (the display actor) in the running level; found ` (PrepareTest) + liveness gate — `the display actor is no longer valid (it must keep existing for the whole run).` (re-checked at both checkpoints) | unconditional (first L2 FAIL gate; only an L1 FAIL — or the fixture's harness-precondition route `HARNESS-PRECONDITION: PrepareTest: no UWorld available`, an Error verdict, never a graded FAIL — prevents it) | nothing at the identity level — destroying the actor or runtime-spawning a second tagged one fails here; adding UNtagged helper actors is free |
| 2 | the CURRENT color is readable from a vector parameter named exactly `CycleColor` on the material of the actor's mesh | fully | cp0 gate (t=1.0s) — `observed no readable CycleColor parameter on the actor's mesh material` | row 1 fails first | the parameter may live on ANY `UStaticMeshComponent` of the actor, in any material slot — including an agent-ADDED invisible mesh component; only a `UMaterialInstanceDynamic` cast is accepted (a static material with the parameter baked in does not read, so a dynamic instance is effectively mandatory) |
| 3 | keep the parameter updated / readable as the color moves ("readable at any moment") | partially | window-readability gate (cp1, gate 0) — `observed no color samples could be read` | rows 1-2 fail first | the floor is only >= 2 samples across the 9.0s window: a parameter readable only sporadically clears gate 0 (sampling gaps then feed enlarged inter-sample deltas into the smoothness gate, which usually — but not provably — catches the gap) |
| 4 | the color must actually change (not a set-once color) | fully | movement gate (cp1, gate 1) — `observed the color never changes (largest channel range ` | rows 1-3 fail first (cp1 gates fan in strict order) | only the LARGEST single channel range is gated (floor 0.2): a low-amplitude cycle between ~0.21-amplitude near-black colors grades identically to the full-amplitude reference (documented residual — the gates judge shape, not brightness) |
| 5 | blend gradually at every moment — never snap or jump between colors | fully, per fixed 60Hz frame | smoothness gate (cp1, gate 2) — `observed the color snaps instead of blending smoothly (a single-frame change of ` | rows 1-4 fail first | steps up to 0.15/frame (~18x the reference's ~0.008/frame blend rate) pass — quantized-but-not-snapping motion is indistinguishable from slightly-coarse blending at this frame rate (documented residual) |
| 6 | the cycle visits green, then blue, then red, then back to green — that cyclic order, all three anchors | fully | order gate (cp1, gate 3) — `observed the color does not cycle through green, blue and red in order` | rows 1-5 fail first | "green/blue/red" = dominant-CHANNEL by a 0.15 margin: dark or desaturated hues count as their dominant channel; the alpha component is unconstrained; the STARTING anchor is free (the gates are deliberately phase-agnostic — see row 8's spacing caveat) |
| 7 | a full cycle every 6 seconds, anchors at equal thirds (green at start, blue one third in, red two thirds in) | partially | period gate (cp1, gate 4) — `observed the cycle period is far from the required six seconds (median dominant-run length ` | rows 1-6 fail first; ALSO self-skips when fewer than 3 dominant runs exist (no window-interior run, median undefined — the continuity gate owns that case) | the band [1.2s, 3.2s] on the MEDIAN full dominant-run admits periods roughly 4.2s-11.3s; and because only the MEDIAN is gated, a lopsided dwell split (e.g. ~3s green / ~1.5s blue / ~1.5s red per cycle) passes so long as the median run stays in-band — equal-thirds spacing is bounded, not pinned |
| 8 | the cycle keeps running for as long as the game runs — must not stop after one pass | partially | continuity gate (cp1, gate 5) — `observed the color stops cycling partway` | rows 1-7 fail first (last cp1 gate) | only the [1.0s, 10.0s] window is ever observed (>= 3 dominant-run transitions ~ 1.5 disclosed cycles): a cycle that freezes at any time after t~10s — after two flawless passes — grades PASS; "forever" is asserted only as "for 9 seconds" |
| 9 | the change belongs to the actor TYPE — any instance behaves this way with no per-instance setup | fully, by the substrate model | not a fixture literal — the graded actor is the map's PLACED instance of the C++ scaffold class `AColorCycleActor` (verbatim in the scaffold header ColorCycleActor.h and in task.md's workspace-state block), and the level (`Content/Maps/`) + `Config/` are verbatim `deny` entries in AGENT_WRITABLE.json, so per-instance setup cannot be submitted; only type-level code can drive the placed instance | unconditional (structural, pre-grade) | nothing — a Blueprint subclass or per-instance hack never reaches the placed instance that gets graded |
| 10 | implement in C++ in the existing gameplay module (and it must build) | fully | L1 layer — UBT exit 0 for BOTH `CraftBenchTemplateEditor` and `CraftBenchTemplate` Win64 Development targets (composed — layer verdict, no fixture literal: the names are runtime-assembled at l1_build.py:273 from the manifest's `game_module`, see preamble; both quoted names are contiguous in task.md's L1 block) | never — L1 gates every later layer | any C++ shape inside the writable module: timeline component, tick lerp, timers, new helper files — the implementation route is deliberately free |
| 11 | do not edit the level, any config file, or any test file | fully, structurally | not a fixture literal — SANDBOX-REJECT exit 4 per UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json, where `Source/CraftBenchTests/`, `Config/` and `Content/Maps/` are all verbatim `deny` entries (the manifest even denies `AGENT_WRITABLE.json` itself), plus git-HEAD substrate materialization (an on-disk fixture edit never reaches the grade) | unconditional (pre-grade) | shipping unused `.uasset` files under the asset-writable prefixes is tolerated — they land but never affect the grade |
| 12 | the actor's RENDERED color actually cycles — the readable parameter corresponds to what the visible mesh displays | **NOT ASSERTED** | — (no such gate exists: L2 runs headless under `-nullrhi` — the runner launch flag, verbatim in tools/verify-single/layers/l2_pie.py:450, not a fixture literal — so no pixel is ever read, and `ResolveCycleMid` neither checks that the MID's PARENT material binds `CycleColor` to shading nor that the carrying mesh component is visible) | n/a | set `CycleColor` on a MID whose parent material ignores the parameter — or park the MID on an added hidden mesh component — and the cube renders its original fixed color forever while every gate above PASSES; the task doc discloses the parameter trace as the grade, but the prompt's "make its color cycle" (the visible color) is enforced only through this proxy |

## Accepted residuals already documented above (not re-argued here)

Rows 4, 5 and 7's get-aways restate the two residuals the coverage note in the
matrix section accepts by design (low-amplitude cycles; sub-cap quantization) plus
the median-only period bound; row 12 is the one genuine NOT ASSERTED hole this
table adds.

## Row 12 disposition (checklist §7: gate it or remove it from the prompt)

Recommendation: GATE the two closable sub-checks rather than remove the prompt
language. Both are structural and assertable in the fixture under `-nullrhi`
(no pixel read required):

1. **Parent-material binding** — in the fixture, after resolving the MID, walk
   its parent `UMaterialInterface` and FAIL unless the parent material actually
   declares a vector parameter named `CycleColor` (i.e. the MID's parameter is
   not an orphan the parent's shading graph never binds). This closes the
   "parent material ignores the parameter" get-away in row 12.
2. **Carrying-component visibility** — FAIL unless the mesh component carrying
   the accepted MID reports visible (`IsVisible()` / not `bHiddenInGame`),
   closing the "park the MID on an added hidden mesh component" get-away.

Neither sub-check proves the rendered pixel cycles (a parent graph may bind the
parameter to a non-emissive/occluded term — that residual is structural under
`-nullrhi` and stays disclosed), but together they collapse the two named
zero-render exploits. If the sub-checks are declined, the prompt's visible-color
phrasing ("make its color cycle") should be re-worded to the asserted proxy (the
readable `CycleColor` parameter) per checklist §7 — never left as unenforced
prose. Fixture edits are `Source/CraftBenchTests/` maintainer flow
(review-gated on commit, effective only once committed).
