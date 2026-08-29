# Build notes — t1-extraction-volume-per-actor-trigger (2026-07-29)

First conversion out of an earlier internal task list (the set's pilot
alongside t1-default-cube-mesh-actor and t1-overlap-teleport-portal). Source
row: "Basic volume class implementation". This file records design provenance
and the text-half state.

## Provenance and the documented cut

The source row's Verification cell is three code-shape checks:

1. "uses AVolume as the base"
2. "uses `virtual void NotifyActorBeginOverlap(AActor* OtherActor) override;`"
3. "doesn't use AddDynamic"

**All three are cut.** No source-inspection lane exists (L5 is defined-only —
`spec.py` parses the token, `IMPLEMENTED_LAYERS` excludes it, no Layer class),
and Hard Rule #2 forbids grading implementation pattern. What survives is the
source row's own behavioral sentence — "triggers endgame logic for an extraction
match for **each individual** that touches it" — which is *stronger* than the
code-shape checks: per-individual once-only semantics require real per-entrant
state, which is exactly what discriminates a thought-through solution from a
raw overlap logger. The reference solution happens to use
`NotifyActorBeginOverlap` without `AddDynamic` (honoring the source row's intent),
but a component-delegate binding is equally valid and equally passes.

The "endgame logic" side effect is abstracted to the exact marker line
`CRAFTBENCH_EXTRACTION_OK` — the substrate ships no endgame/match system, and
the marker-line contract is the substrate's proven observable (t0 /
t1-overlap-logs-once lineage).

## Differentiation from t1-overlap-logs-once

The neighboring wave1 task grades "log once on FIRST overlap, silent before".
This task's graded core is the **per-individual ledger**: same-individual
re-entry adds nothing (cp2) while a second distinct individual adds exactly
one (cp3). Neither checkpoint exists in t1-overlap-logs-once, and a passing
overlap-logs-once solution (single global log) FAILS this task at cp3 — that
is the `global-once` variant, verbatim.

## Fixture design

- **Listener**: GLog `FOutputDevice` counter installed in
  `OnWorldInitializedActors` filtered to this world, LogTemp/Display+ —
  byte-pattern copy of the proven `OverlapLogFunctionalTest` counter (renamed
  `FExtractionLogCounterDevice`; both classes live in the same module, so the
  rename is load-bearing against ODR collision).
- **Probes**: two fixture-spawned plain AActors with query-only overlap-sphere
  roots (radius 48), parked ~5000 units +X of the zone, 500 apart. Entry
  points sit inside the zone box at Y = -60 / +60 so both probes fit without
  stacking on each other.
- **Checkpoints** {0.5, 1.5, 2.0, 2.5, 3.5}: cp0 asserts pre-entry silence
  then inserts A; cp1 asserts ==1 then walks A OUT; cp2 carries **no graded
  count assert** — it only re-inserts A; cp3 asserts ==1 (the dedupe gate)
  then inserts B; cp4 asserts ==2. The exit and the re-entry are deliberately
  on SEPARATE checkpoints (~30 fixed frames apart): a same-frame
  out-then-in could be coalesced by the engine into "no overlap state
  change", in which case the `log-every-entry` cheat would get no second
  begin-overlap and grade a FALSE PASS — the worst matrix outcome. The split
  removes that failure mode by construction (adversarial review, 2026-07-29).
- **Move technique**: `SetActorLocation` + `UpdateOverlaps()` on the probe's
  root primitive — the exact `InduceOverlap` technique
  `OverlapLogFunctionalTest` field-proved for begin-overlap.
- **Probe spawn safety**: the probe's sphere root gets `SetWorldLocation`
  BEFORE `RegisterComponent()`. A rootless-spawned AActor discards its spawn
  transform, so a root registered at identity would exist at the WORLD ORIGIN
  for its registration overlap update — if the placed zone ever contained the
  origin, both probes would phantom-overlap during PrepareTest and the
  REFERENCE would fail cp0 (adversarial review, 2026-07-29).
- **Harness-precondition sentinel**: if the GLog listener never installed,
  `OnCheckpoint` refuses to run the graded comparisons and calls
  `FinishTest(EFunctionalTestResult::Error, "HARNESS-PRECONDITION: ...")`.
  HONESTY CAVEAT: `EFunctionalTestResult::Error` still lands as state "Fail"
  in `index.json` and `l2_pie.py` counts it as a graded test failure TODAY —
  the Error result + prefix correctly EXPRESS the semantics and mark the log
  for a future runner-side routing rule (a named work item in the parent
  plan), but today it still grades FAIL. Do not read this fixture as routing
  to exit 7.

## Calibration checklist (runtime-unproven assumptions)

Every item below must be confirmed by the first live reference leg; none is
proven by the text half alone.

- [ ] **End-overlap on teleport-out fires at all.** The out/re-in is already
  split across separate checkpoints by design (cp1 exit, cp2 re-entry — see
  fixture design above), so same-frame coalescing is off the table; what the
  live leg must still confirm is that `SetActorLocation(parking) +
  UpdateOverlaps()` produces the END-overlap and the cp2 re-entry produces a
  fresh begin-overlap (begin-overlap alone is the proven half, via
  overlap-logs-once).
- [ ] **Zone box vs entry offsets.** Entry points assume the placed zone keeps
  the constructor's 200x200x100 half-extent and Y-offsets of +/-60 land inside.
  The map author script places the scaffold unscaled — keep it that way.
- [ ] **Zone placement vs world origin (map/fixture coupling).** The placed
  zone's detection box must NOT contain the world origin. The fixture already
  positions probe roots before registration, but the origin-exclusion is
  defense-in-depth for ANY component that momentarily registers at identity;
  the aids script's `ZONE_LOCATION` Z=200 (box spans Z 100..300) is
  load-bearing — a re-authored map that grounds the zone at Z<=100 re-opens
  the phantom-overlap hazard.
- [ ] **Probe cross-overlap harmless.** At cp3 both probes sit inside the zone
  60 units apart with 48-radius spheres — they do NOT mutually overlap
  (120 > 96), by construction; verify no stray events regardless.
- [ ] **Scaffold-as-empty-leg**: the empty discriminate leg overlays nothing,
  so the graded class is the scaffold itself — confirm it emits nothing and
  dies at cp1's named assertion (not an L1 surprise).
- [ ] Named-assertion substrings appear verbatim in the L2 log on real UE
  (ASCII-only rule) — confirm each variant's row after the first discriminate.

## Pending binary half (editor-serial; needs owner go-ahead)

- `UE-projects/CraftBenchTemplate/Content/Maps/t1-extraction-volume-per-actor-trigger/L_ExtractionVolume.umap`
  — NOT yet authored. Recipe: `aids/author_L_ExtractionVolume.py` (one placed
  scaffold zone + the placed fixture actor; no PlayerStart, no GameMode — the
  fixture spawns its own probes). **Placement contract: the zone's detection
  box must NOT contain the world origin** — the script's `ZONE_LOCATION`
  Z=200 is load-bearing (see the calibration checklist's origin-coupling
  item); do not ground the zone. Requires both modules built first
  (`CraftBenchTemplateEditor`) so the classes resolve.
- After the map lands: `cb discriminate --wip` -> fill MATRIX status + this
  checklist; commit map + task in one change (grading reads git HEAD).

## Landing gate

This task MUST NOT land in `tasks/CATALOG.md` / the registry count claims
before BOTH of these are true:

1. the `.umap` binary AND the scaffold/fixture sources are committed (grading
   reads git HEAD — an uncommitted fixture does not exist to the grader);
2. one full `cb discriminate` run has executed (reference PASS + all four
   negative legs FAIL via their named substrings) and its results have filled
   the calibration record above and the MATRIX status block.

Until then the task is a text-half draft, deliberately invisible to
`cb tasks` consumers via its absent CATALOG row.

## Registry reconciliation (deferred to the batch pass)

CATALOG row + the hard-coded count claims (`inventory.py` checks) are handled
in one shared pass across the three pilot ports — not per-task edits.

## Calibration record — first live validation (2026-07-29)

Binary half + full matrix ran this date on this box (Win11, UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8`, substrate=live via `--wip`):

- **Build**: editor target compiled the task's scaffold + fixture C++ clean on
  the FIRST attempt (no warnings in task files).
- **Map**: authored headless by `aids/` script (`-ExecutePythonScript`,
  `-RenderOffScreen`); single monolithic `.umap`, no OFPA spillover; placement
  log line confirmed in the editor log.
- **Matrix**: `cb discriminate --wip` = **discriminated: YES** — reference
  PASS; empty + EVERY variant FAIL, each credited via its named MATRIX
  substring (`[ok ]` on all legs).
- **Not retained**: per-leg run dirs (no `--keep`), so the fixture's numeric
  calib log lines were not harvested. The checklist's yes/no assumptions are
  answered by the verdicts themselves; re-run with `--keep` if the numeric
  baselines are wanted before re-timing any checkpoint.
