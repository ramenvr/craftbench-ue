# t2-ladder-climb-volume — build contract + calibration notes

Source row "Ladder system", out of an earlier internal task list — the hardest
row of its block. Text half authored 2026-07-30 on the
tp2-sprint-stamina mold (Do* seams by reflection, GameMode/PlayerStart
possession, per-frame fixture drive) + the wave-1 teleport patterns
(continuous guard, HARNESS-PRECONDITION prefixes).

## Provenance and cuts

- **Key → seam rephrase**: the source row's hold-a-key climb is rephrased to
  `DoClimbStart`/`DoClimbEnd`, the substrate's programmatic input-seam
  convention — headless PIE has no key events. tp2 set the precedent and its
  matrix proved the seams discriminate.
- **"Climb down" CUT**: a second input axis with no independent observable
  beyond the up-axis (same evidence class), cut exactly as tp2 cut the
  caps-lock walk-toggle. Recorded here, not silently dropped.
- **"Place a ladder in the map" moved to the map contract**: the ladder is a
  committed scaffold + placed actor; the agent implements behavior, not level
  layout (level edits are deny-listed).

## Map contract (aids/author_L_LadderClimb.py must match)

| element | value | why |
|---|---|---|
| floor | engine cube, scale (30, 20, 1) → 3,000 x 2,000 x 100, center (300, 0, -48), top at Z=+2 | spans X [-1200, 1800]: covers the PlayerStart, the walk lane, and the ladder base |
| PlayerStart | (0, 0, 120), yaw 0 (+X facing) | spawn settles to Z ≈ 98 (floor top +2 + capsule half-height 96 — stock `InitCapsuleSize(42, 96)`) well before cp0=0.6s; 540uu from the volume's near face |
| ladder volume | `ALadderVolumeActor` at (600, 0, 600) | ctor box half-extent (60,60,600) → spans X [540,660], Y [-60,60], Z [0,1200]; bottom at floor level, top at 1200 |
| fixture | `ALadderClimbFunctionalTest` at (0, 400, 120) | off the walk lane |
| GameModeOverride | `ALadderGameMode` (`/Script/ThirdPerson.LadderGameMode`) | spawns/possesses the ClimbHero-tagged character; keeps the stock BP mannequin stack out of the headless run |

The fixture reads the volume's world bounds ONCE in PrepareTest (center X,
top Z) — the map values above are the contract those reads return.

## Fixture design (why each number)

- **Schedule {0.6, 1.6, 4.0, 5.2, 9.8}**, world game-time. Timeline: settle
  (≤0.4s, to Z≈98) → away probe 0.6-1.6 → walk 1.6-~2.7 (540uu at stock
  ~500-575uu/s) → climb1 ~2.7-4.0 (gain ≈ 330-390 at the disclosed 300uu/s)
  → hold 4.0-5.2 → climb2 5.2-~7.2-8.2 (from Z≈460-520 to the top-cross,
  recorded at Z > top−2) → fall → cp4 at 9.8. TimeLimit = 9.8 + 2.0 (base
  margin).
- **KTopCrossEpsilon 2 (BELOW the top, not a margin above)**: exit-detection
  styles differ legitimately — a center-in-box solution stops the climb the
  frame its center passes the top (max Z ≈ top+5 at 5uu/frame), while the
  reference's capsule-overlap exit climbs on to ≈ top+96 (half-height 96)
  before the overlap ends. Recording the cross at top−2 accepts both; a
  margin ABOVE the top would false-FAIL the boundary-exit class ("never
  climbed past the top") — adversarial-review MAJOR, fixed 2026-07-30.
- **Worst-case fall-to-cp4 math**: the slowest legitimate top-cross is ~8.2s
  (climb2 from ~460 at 240uu/s to 1200−2); a boundary-exit solution stops at
  ~1205 and falls from there — 1.6s of gravity is ~1250uu of drop (it lands,
  Z≈98) — comfortably below the cp4 gate (top−50 = 1150). The reference
  (exit at ≈1296, ~7.6s) lands even earlier.
- **Away probe FIRST** (trap inside the cheat window): a location-free climb
  is rising exactly when cp1 samples; probing after visiting the ladder would
  let a "was-ever-at-ladder" latch pass.
- **KAwayRiseTolerance 40**: settle motion is downward; jump-free heroes never
  rise. 40uu absorbs capsule adjustment noise.
- **The cp1 `DoClimbEnd` cleanup is belt-and-braces, not load-bearing**: the
  prompt promises only that an away-side request does nothing (the graded
  no-ascent gate); the reference ignores-and-does-not-retain such requests on
  its own. The cleanup neutralizes latched-but-inert requests on lenient
  implementations so later phases grade climb logic, not probe residue.
- **KMinClimbGain 150** at cp2: worst-case window (late arrival 2.9s) x slow
  band (240uu/s = disclosed −20%) = 264; 150 leaves ~1.7x margin. Gate is
  one-sided — over-fast climbing is caught by the continuity guard, not here.
- **KHoldTolerance 60** (two-sided) at cp3: the prompt discloses hold-in-place,
  so both a continued rise AND a plummet fail. Two-sided is what makes the
  hold load-bearing.
- **KMaxPerFrameRise 50/frame** (continuity guard, every climb-phase frame):
  disclosed rate is 5uu/frame at 60Hz; 50 is a 10x margin; a top-snap covers
  ~700+uu in one frame. Guard runs on fixture-tick deltas, so it is
  tick-order-independent.
- **cp4 at 9.8, gate top-crossed AND Z < top-50**: exit at ~7.3-8.5s (climb2
  from the held height across the ±20% rate band) leaves ≥1.3s of gravity —
  ≥800uu of drop or already landed. A hoverer parks at ~top+100; a
  never-releasing riser is far above.

## Named assertions → discrimination legs

| leg | dies at | credited substring |
|---|---|---|
| empty | PrepareTest seam gate | `climb seam missing` |
| `climb-anywhere/` | cp1 (t=1.6) | `climb engaged away from the ladder` |
| `teleport-to-top/` | continuity guard (~2.7s, first climb frame) | `ascent jumped discontinuously` |
| `never-releases/` | cp4 (t=9.8) | `still ascending or hovering after leaving the ladder` |

## Calibration checklist (fill from the first live matrix)

Every entry is a runtime-unproven assumption of the text half; the binary-half
session confirms each against the `[t2-ladder calib]` lines and the leg
verdicts. HONESTY NOTE: the fixture's `FinishTest(EFunctionalTestResult::Error,
"HARNESS-PRECONDITION: ...")` paths (no-world, invalid ladder bounds) still
GRADE AS AGENT FAIL today — automation Error lands as state Fail in index.json
and `l2_pie.py` counts it; the prefix is the hook for a future runner-side
routing rule, not a claim of exit-7 routing.

1. **Seam invocation on a GameMode-possessed ThirdPerson character** —
   tp2-PROVEN (its matrix ran the identical FindFunction/ProcessEvent helper
   on the identical possession path); cite, do not re-spike.
2. **Walk arrival time** — geometry says ~2.7s (540uu, stock max speed ~500,
   accel ramp). Confirm via the cp2 calib line's phase + climb gain; if
   arrival drifts past ~3.2s, cp2's 150-gain gate starves — re-time cp2
   before blaming a variant.
3. **MOVE_Flying hold + restore** — the reference holds via zero-velocity
   Flying and restores Falling on exit. Confirm the hold shows |dZ| ≤ ~10 in
   practice, and that the post-exit fall reaches the floor (landed) by cp4.
4. **Overlap-driven at-ladder detection under -nullrhi PIE** — capsule-vs-box
   overlap is teleport-task-PROVEN on this substrate; the reference's
   GetOverlappingActors polling is the same collision data read a different
   way. Confirm the climb engages within ~2 frames of the arrival seam call.
5. **Continuity guard false-positive sweep** — the reference must never
   trip the 50uu/frame guard (expected max ~5uu/frame): confirm zero guard
   fires across the reference leg.
6. **Bounds read** — `GetComponentsBoundingBox(true)` on the placed volume
   returns X-center 600 / top 1200 per the map contract; the cp4 gate keys
   off it.
7. **Top-cross epsilon** — confirm the reference leg records the cross (calib
   line phase turns Exited) at Z ≈ 1198 while its overlap-exit keeps climbing
   to ≈ 1296, and that both the reference and the boundary-exit solution
   class (max Z ≈ top+5) grade PASS; `never-releases` must still die at cp4
   under the lowered threshold (verified by design 2026-07-30, re-verify
   live).

## Residual bounds (acknowledged, not gates)

Two cheat shapes are accepted limits of one probe on one committed map
(mirrored in the MATRIX coverage note): a discard-the-FIRST-request cheat
passes the single away-probe by construction, and a coordinate-hardcode
(climb gated on X thresholds read off the agent-visible scaffold/map
constants) is indistinguishable from real volume logic on this single map.

## Landing gate

Do NOT land this task in CATALOG/registry before (1) the `.umap` + these
sources are committed and (2) one full `cb discriminate` run has filled the
calibration record and the MATRIX status section.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the calib
line values at each checkpoint, and any re-timed checkpoints.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date on this box (Win11, UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8`, substrate=live via `--wip`):

- **Build**: editor target compiled the task's scaffold + fixture C++ clean on
  the FIRST attempt (post-adversarial-review sources).
- **Map**: authored headless by the `aids/` script (`-ExecutePythonScript`,
  `-RenderOffScreen`); single monolithic `.umap`; placement log line confirmed.
- **Matrix**: `cb discriminate --wip` = **discriminated: YES on the first
  attempt** — reference PASS; empty + EVERY variant FAIL, each credited via
  its named MATRIX substring (`[ok ]` on all legs).
- **Not retained**: per-leg run dirs (no `--keep`) — numeric calib lines
  unharvested; the checklist's yes/no assumptions are answered by the
  verdicts. Re-run with `--keep` only if a checkpoint ever needs re-timing.

Checklist items resolved by the 2026-07-30 matrix (verdict-level evidence):
1. The reflection seams + GameMode possession worked on this task's own map
   (tp2 precedent transferred unchanged).
2. The top-cross epsilon (2 uu BELOW the top) behaved: reference recorded the
   cross and landed by cp4; `never-releases` still died at its named assert.
3. Walk-arrival/climb/exit timing all fit the shipped schedule on the first
   attempt; the continuity guard produced no false trips.
