# Build notes — t2-timeline-color-cycle

Maintainer-facing. The agent never sees this file.

## Provenance

- Source row: an earlier internal task list (not shipped), "Changing colors
  with timeline test (could replace with door test, making a door)"
  (Blueprints / Timeline). Its
  prompt: *"can you make it so that the light green actors in this level
  change colors from green to blue to red and then back to green ... over
  time without stopping? but can you do this with timeline nodes?"*
- Adaptation deltas, both documented in `task.md`'s intro: (a) the source row's
  "timeline NODES" core metric is **CUT** — Blueprint-graph introspection is
  a denied read route (`t1-walk-animation-footstep-cues` cut its AnimBP
  handler half on the same grounds) and no source lane exists (L5 is
  defined-only); the graded observable is the timeline-QUALITY behavior
  (smooth, ordered, continuous interpolation). (b) "the light green actors
  in this level" becomes ONE tagged scaffold display actor — this substrate
  has no pre-existing green level dressing; per-task folders are the
  convention.
- The color READ ROUTE is the wave-3 spike's R24 verdict (2026-07-30):
  MID `Get/SetVectorParameterValue` works headless with an arbitrary name,
  including mid-run mutation; but `GetAllVectorParameterInfo` does NOT
  surface override-added parameters, so an agent-chosen name is
  undiscoverable — the prompt therefore DISCLOSES the parameter-name
  contract (`CycleColor`), the melee `Health`-contract precedent.
- **The VISIBLE half is headless-unverifiable, by design.** No pixel gate
  exists (FR-020d: fully deterministic, no render in the PASS/FAIL path), so
  the fixture cannot see the cube — `CycleColor` is the graded observable
  and the prompt requires it to BE the current color. Consequences, stated
  honestly: an agent that cycles the cube visibly but reports a wrong or
  stale `CycleColor` fails per the disclosed contract (correct — the
  contract is the spec); an agent that drives `CycleColor` correctly but
  renders nothing passes the gate (the render check belongs to the advisory
  `--capture`/preview track). The REFERENCE and all variants set BOTH
  parameters each update — `CycleColor` (the contract) and `Color` (the
  engine basic-shape material's own tint) — so the exemplar actually looks
  right in any capture.

## Dead-gate audit (graded values vs UE 5.8 engine defaults)

| gate | engine default | verdict |
|---|---|---|
| readable `CycleColor` by t=1.0 | a fresh MID has NO readable `CycleColor` — spiked live 2026-07-30: `GetVectorParameterValue` returns got=false until the parameter is first SET (the scaffold creates no MID at all, so the empty leg fails even earlier: no MID to find) | LIVE — excludes the do-nothing state |
| channel range >= 0.2 | an unchanged parameter has range 0 | LIVE |
| max frame delta <= 0.15 | n/a (only fires on change); disclosed-cycle blending moves ~0.0083/frame, snap = 1.0 | LIVE both directions — 18x above the reference, 6.7x below a snap |
| dominant order G→B→R cyclic | no default order exists (no default motion) | LIVE by construction |
| median full run in [1.2s, 3.2s] | no default runs exist; the disclosed 6s cycle dominates each anchor ~1.7s (2.0s leg minus the 0.15-margin trim on both blend shoulders: dominance holds for α in [0, 0.425] and [0.575, 1] of each leg → 0.85s + 0.85s per anchor) | LIVE — fails ~2x-off periods both ways |
| transitions >= 3 in 9.0s | zero without motion; disclosed 6s period yields 4-5 | LIVE |

**FPS-dependence (load-bearing, the gravity-task precedent):** the
smoothness cap 0.15 is a PER-FRAME delta derived for the spec's single
`-FPS=60` leg — at 30fps the reference's per-frame delta doubles to
~0.017 (still 9x margin) but a hypothetical much lower fps leg compresses
the margin. If this task ever gains an `fps_legs` declaration, re-derive
the cap (or rewrite it rate-based) BEFORE adding the leg.

## Fixture design

- Base: `ACraftBenchFunctionalTest`. No possession, no pawn — the actor
  drives itself.
- Read route: walk the tagged actor's `UStaticMeshComponent`s and every
  material slot for the first `UMaterialInstanceDynamic` whose
  `GetVectorParameterValue(CycleColor)` returns true. The walk runs FRESH
  EVERY FRAME — no caching — so a solution that recreates its dynamic
  material instance per tick (a classic mistake that still works visually)
  is read through the component's CURRENT material, never a stale orphaned
  instance. Component/slot ambiguity is handled by the walk: ANY mesh
  component + slot carrying the readable contract counts. The cp0 gate at
  t=1.0 is the readable-by deadline.
- The judge is a per-frame TRACE (~540 samples across cp0→cp1 at the fixed
  60Hz step; `TArray<FLinearColor>`, ~8.6 KB — negligible). Gates evaluated
  in a deliberate order — readability, movement, smoothness, order, period,
  continuity — so each gaming shape dies at ITS named assertion (a static
  color must hit "never changes", not the order gate; a snap cycle must hit
  the smoothness gate it exists to prove; a one-pass-stop must fall through
  to continuity). The readability guard (>= 2 samples) exists so an
  unreadable-after-cp0 trace fails with a clean named message instead of
  feeding float sentinels into the movement gate.
- Gate arithmetic at 60Hz: window 9.0s = 1.5 disclosed cycles. Dominance
  per anchor: on each 2s leg the fading anchor holds dominance while
  1−2α > 0.15 (α < 0.425) and the rising one from α > 0.575 — so each
  anchor dominates ~0.85s on each side of its peak = **~1.7s full-run
  length** (~102 samples). Period band [72, 192] samples ([1.2s, 3.2s]):
  the reference's 1.7s sits mid-band; a 2s-period cycle runs ~0.57s (under)
  and an 18s one ~5.1s (over). Only window-INTERIOR runs count (first/last
  are truncated); with fewer than 3 runs no interior exists and the period
  gate defers to continuity. Transitions: 1.5 cycles → 4-5 regardless of
  starting phase; floor 3 still fails a one-pass-stop (freezing at t=6s
  leaves runs B[1.15,2.85] R[3.15,4.85] G[5.15→end] in the [1,10]s window
  = 2 transitions).
- Checkpoint clock note: `OnCheckpoint` fires inside the base Tick BEFORE
  this fixture's per-frame sample append, so the cp1 gates read exactly the
  samples appended in [cp0, cp1).
- Error-precondition honesty (wave-1 convention): the fixture's single
  `FinishTest(Error, "HARNESS-PRECONDITION: ...")` path (no world) still
  **grades as agent FAIL today**; the prefix is the future routing hook.

## Map contract (mirrors `aids/author_L_ColorCycle.py` — keep in sync)

| element | value | why |
|---|---|---|
| template | `/Engine/Maps/Templates/Template_Default` | ships a WorldSettings |
| display actor | `AColorCycleActor` at (0, 0, 120) | above the template floor; no motion, placement is cosmetic |
| fixture | `AColorCycleFunctionalTest` at (0, 400, 120) | clear of the actor |
| PlayerStart / GameMode | none | nothing is possessed |

## Calibration checklist (fill from the first live run)

1. **Reference trace shape** — from the `[t2-colorcycle calib]` line:
   expect samples ≈ 540, runs 5-6, transitions 4-5, maxdelta ≈ 0.008-0.01,
   range ≈ 1.0, medianrun ≈ 100-105 (~1.7s). Confirm no false trip of the
   smoothness cap on the FIRST sampled frame, and that the median sits
   mid-band (72..192).
2. **snap-cycle timing** — timer epoch is BeginPlay (t≈0 world time), flips
   at t≈2.0/4.0/... — at least three snap frames land inside the cp0→cp1
   window; each is a 1.0 jump vs the 0.15 cap. Confirm it dies at the
   smoothness gate, not order/period/continuity.
3. **wrong-order runs** — expect runs to include an invalid transition
   (G→R or R→B or B→G) within the first ~4s. Confirm it survives gates 1-2
   and dies at the order gate.
4. **static-color** — range 0 vs the 0.2 floor; confirm it dies at gate 1.
5. **stops-after-one-cycle** — freeze at world t=6.0 leaves window runs
   B/R/G(frozen): confirm it survives gates 1-4 (one interior run R ≈ 1.7s
   → period passes) and dies at continuity with exactly 2 transitions.
6. **Late-MID solutions** — a solution that first SETS `CycleColor` after
   cp0 with a non-anchor initial value could register a large first-sample
   delta ONLY if it later jumps; consecutive-sample deltas within one
   solution's own updates are what the cap sees. A solution initializing
   the parameter to black at BeginPlay and starting the cycle at green
   would show one 1.0 G-channel jump — that shape violates the disclosed
   "green at cycle start, always readable, never snaps" contract and fails
   honestly; noted here because it is a near-miss shape found in design
   review.
7. **Per-frame MID re-resolution** — the fixture walks components every
   frame (never caches); confirm the reference trace is identical to the
   pre-fix cached behavior (it keeps one MID, so the walk resolves the same
   instance each frame) and no measurable cost shows at ~540 walks.
8. Confirm the empty leg (bare scaffold: no MID ever) dies at cp0's
   readable-parameter gate, not at L1.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the
calib line values, and any re-derived caps.

## Landing gate

MUST NOT land in CATALOG/registry before (1) the `.umap` + these sources are
committed and (2) one full `cb discriminate` run has filled the calibration
record and the MATRIX status. The registry reconciliation (CATALOG row +
count claims + MAPS.md row) happens in the shared batch pass, not per-task.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date (Win11, UE 5.8, substrate=live via
`--wip`): **`cb discriminate` = discriminated: YES** — reference PASS; empty +
EVERY variant FAIL via its named MATRIX substring (`[ok ]` on all legs).
Editor-target builds of the scaffold/fixture C++ were clean; per-leg run dirs
not retained (no `--keep`) — the verdicts answer the checklist's yes/no items.

Wave-3 specifics: the per-frame sampler, both continuity guards, the period
band, and the new stops-after-one-cycle variant all discriminated at the
shipped constants on the first attempt (6/6).
