# t1-guard-only-spots-what-it-can-see — provenance and design decisions

## Imported from

`t1-ai-sight-detection` in an internal design note (not shipped)
(row 39). Companion rows carried forward:

- an internal design note (not shipped) — primitive
  `pie-checkpoint-sampling`, layers `L1|L2`, named assertions
  `NotDetectedWhenBehindGuard|NotDetectedWhenOccluded|DetectedInSightCone|NeverDetectedOutOfSight`.
- an internal design note (not shipped) — queue order 5, priority P0,
  work flags `Harden verifier|Add negative control`.
- an internal design note (not shipped) row 82 — `Keep`,
  capability "AI, Behavior & Navigation", family "03 Perception & Reactive
  Behavior".
- an internal design note (not shipped) §1 #10 — the
  Expect/Control/Do/Sinks-it lines this spec implements.

The corpus row was marked **`Hardening Status: HOLD`**. It is **un-held** here,
on the reviewer's recorded grounds (`ADOPTION-REVIEW-2026-08-16.md` row 5 and
merge-loss row 4): the hold is a merge pointer at `t1-ai-detects-patrols-and-chases`,
whose rubric keeps only the occlusion leg and **drops both the behind-the-guard
and the beyond-range legs** — i.e. precisely what makes this row worth building.
Under the successor alone, line-of-sight-only detection at any distance passes.

## What the owner said

From an internal working note (not shipped), item `1:t1-ai-sight-detection`:

```json
{ "cand/1:t1-ai-sight-detection": { "section": "1", "item": "1:t1-ai-sight-detection",
  "row_id": "t1-ai-sight-detection", "answer": "agree", "note": "" } }
```

(Quoted with its wrapper key and with `"section"` as the string it is in the file;
an earlier version of this block dropped the `cand/1:` key and printed
`"section": 1` as an integer.)

The owner's note field is empty; the accompanying instruction with this task was:

> agree. NOTE this corpus row is marked HOLD in the source row and needs un-holding:
> its hold is a merge pointer whose successor drops both the behind-the-guard and
> the beyond-range legs, i.e. exactly what makes the row worth building.

The only other reviewer text attached to the row is the verification-contracts
"Review evidence" cell: *"For 51, this task is good, but look closer to how do
we verify it. Same for 52."* — read here as the mandate for the verifier detail
below rather than for any change of behaviour.

## What changed from the corpus row, and why

- **The `k/4` rubric became ONE two-sided verdict.** THE defect: three of the
  row's four checks (`NotDetectedWhenBehindGuard`, `NotDetectedBeyondSightRange`,
  `NotDetectedWhenOccluded`) are true of a delivery that does nothing at all, so
  an empty submission reported **3/4** and the rubric read strict while measuring
  almost nothing. L2 emits a single `AFunctionalTest` outcome, so the re-band is
  structural, not cosmetic: PASS requires the lit side (cp1 **and** cp4) and the
  dark side (cp0, cp2, cp3 + two continuous guards) together, and there is no
  partial credit to bank. Stated explicitly under *Scoring — the re-band*.
- **Detection state became a lamp.** The row graded a "readable detection
  state" — a property nobody watching Play can see. The graded readback is now a
  red/dark point light on the guard's head, so the whole grade is photographable,
  and the two disclosed numbers (1200 range, 45 deg) are painted on the floor as
  a range arc plus cone-edge stripes. Per the owner's bar, a value with no
  on-screen readout is a rejected design.
- **A control twin was added** (the row had negative *positions* but no negative
  *subject*). A second, identical `ASightGuardActor` 300 cm from the graded one,
  with a permanent wall 160 cm in front of it sized so **every** ray inside its
  45 deg cone is blocked at every distance. Its lamp is gauged EVERY FRAME, not
  only at checkpoints. This is what makes line-of-sight-only detection fail
  twice: the twin's line to the start waypoint is clear and only its cone
  excludes it.
- **The twin carries no distinguishing per-instance tag, and the graded/control
  roles are assigned geometrically in `PrepareTest`.** Without this, "if I am the
  second guard, never light" would satisfy the control leg with no occlusion
  implemented at all — the control would have been decorative.
- **The crate is relocated by the fixture before play** (the
  `t1-overlap-teleport-portal` precedent). The row's occluder was static, which
  left "bake the crate's shadow polygon from the map" as a passing non-solution.
  The occluded waypoint is derived from the crate's LIVE transform.
- **Every trigger fires twice.** cp1 and cp4 measure the identical position, so a
  one-shot latch or a fire-once implementation dies at cp4. The corpus row
  sampled each state once.
- **The trigger is walking, with two drivers.** The row's "movement driver" is now
  the shipping per-frame `AddMovementInput` timeline over a fixture-owned
  waypoint route, and the walker is the game-mode-spawned stock mannequin at a
  PlayerStart — so a human hitting Play drives the same route with WASD and sees
  the same lamps. No key presses anywhere in the graded path.
- **Every graded number is in the prompt** (1200 units, 45 degrees either side,
  0.5 s response window, "dark when play begins"). The row left range and cone
  as "boundaries fixed by the fixture", which false-FAILs correct-but-conservative
  work. Undisclosed: only the checkpoint instants and the route (recorded under
  *Hidden invariants*).
- **`deliverable_root:` is NOT in the front matter.** It is not in
  `tools/verify-single/spec.py::_KNOWN_KEYS`; an unknown key raises
  `ValueError` → exit 2 "spec malformed", which would make the task unrunnable
  rather than merely unlabelled. Verified empirically against
  `spec.parse_task_file`. Per the set README's mitigation the root
  (`Source/ThirdPerson/`) is instead the first line of **Workspace state
  pre-task** and is repeated in the prompt body — both agent-visible sections
  (`spec.py:24`).
- **Heading name.** The batch brief calls the section `## Workspace pre-state`;
  the parser's and `tasklint`'s canonical H2 is `## Workspace state pre-task`
  (`spec.py:25`, `tasklint._CANONICAL_H2_ORDER`). The canonical spelling is used.
- **Renamed** `t1-ai-sight-detection` → `t1-guard-only-spots-what-it-can-see`:
  the old id names the mechanism, and a task id becomes an agent-visible path.
- **Substrate `ThirdPerson`, set `craftbench-public`, deliverable C++.** The
  writable root is `Source/ThirdPerson/`; `Source/CraftBenchTemplate/` does not
  exist on this substrate and writing there is a SANDBOX-REJECT.

## Calibrated geometry (the numbers the build step must re-confirm)

All in cm; guards face +X (yaw 0). Sight range 1200, cone +/-45 deg.

| Name | Position | dist to graded eye | angle off facing | line |
|---|---|---|---|---|
| Graded guard | `(0, +150)` | — | — | — |
| Control twin | `(0, -150)` | — | — | blocked by its wall at every angle in cone — **swept and asserted in `PrepareTest`**, not argued |
| Blocker wall | `(50, -150)`, 40 x 400 x 320 — **FLUSH to the twin's body**, was `(160, -150)` | — | — | see the near-field correction below |
| Crate authored | `(700, 600)`, 120 x 240 x 320 | — | — | valid occluder for a human Play session |
| Crate fixture-chosen | `(620, 480)` | 667 | 30 deg | shadow half-width ~194 at W3 |
| W0 start / PlayerStart | `(-400, 250)` | 459 (412 from origin) | 167 deg | clear -> DARK (behind, but IN range) |
| W1 clear | `(350, 300)` | 354 (381) | 26 deg | clear -> LIT |
| W2 beyond range | `(1600, 150)` | 1562 (1600) | 0 deg | clear -> DARK (30% beyond) |
| W3 occluded | `~(881, 628)` | 967 (1018) | 29 deg | blocked -> DARK |
| W3a transit | `(900, 200)` | — | — | walks round the crate, not into it |

Distances are from the guard's **eye point** `(40, 150, 170)` to the character's
capsule centre (`z ~= 88`), with the actor-origin reading in parentheses. **NOTE
THE ORDER IS THE OPPOSITE WAY ROUND IN `task.md`**, which is origin-first with the
eye reading in parentheses; the two files must agree number-for-number and both
were corrected 2026-08-17 (task.md had cp0 at `166 deg` against this file's `167`,
annotated cp1 in the origin basis and cp3 in the eye basis, and carried a `1004`
for W3 that matched neither). **Every leg lands the same verdict under either
reading** — both are correct implementations, so the ambiguity must not be
gradable. The tightest margin is cp2's beyond-range leg at 30%.

**The eye-vs-origin ambiguity was gradable on the continuous guard, and is not
any more.** The "same verdict either way" claim holds AT the five waypoints. It
did not hold BETWEEN them, and the every-frame pre-sighting guard measures
between them: on the `W0 -> W1` leg the 45-degree crossing is at path fraction
`s = 0.714` from the origin and `s = 0.771` from the eye, a ~43 cm / ~0.086 s
window in which an origin-measuring submission is legitimately lit while an
eye-based oracle still says not-yet-visible → immediate FAIL of correct work. The
same exposure exists for 2D-yaw vs 3D-dot and for tracing to head/capsule/feet.
`task.md`'s pre-sighting oracle is now the **union of every sanctioned basis**,
disarmed a further 0.5 s early (the disclosed settle window), so no basis choice
can decide a verdict. **The angles carry the same build-time calibration caveat as
the instants** — confirm every distance AND every angle against a reference run's
`calib` lines before any MATRIX row is trusted. W3's origin distance in particular
recomputes to ~1002-1018 depending on the assumed actor-origin Z, which is exactly
the kind of number that must come from the log rather than from arithmetic here.

**Near-field correction to the wall (2026-08-17).** The wall was authored at
`(160, -150)`, i.e. **160 cm in FRONT of** the twin, and this file justified it as
"cone half-width 160 < half-extent 200". That reasoning only covers rays measured
at or beyond the wall plane. A character standing between the twin's eye
(`x = 40`) and the wall's near face (`x = 140`) is inside the +/-45 degree cone
with a **completely unobstructed line** — so a correct per-guard rule lights the
twin there and the every-frame control gauge FAILs it. The old geometry was safe
only because the fixture's route happened never to enter that pocket: safety by
route choice, unstated, and broken the moment a human hits Play and walks into it
(which also breaks the "a human hitting Play drives the identical route ... same
observable, two drivers" claim, and the prompt's absolute "it must stay dark all
session"). Two fixes, both applied: the wall moves flush to the body so there is
no pocket, and `PrepareTest` **sweeps a 5-degree fan across the twin's whole cone
out to 1200 uu and asserts every ray is blocked**, as a named
`HARNESS-PRECONDITION` — so if a future map edit reopens the gap it reports as a
staging fault and never as a model failure. The prompt sentence naming the walled
guard was also removed (it was half of the position-key leak, below).

Checkpoints `{1.0, 3.5, 7.5, 10.5, 13.5}` assume the stock ~500 uu/s ground
speed over ~4,000 cm of route plus turn/accel overhead, and leave >= 0.5 s of
settle after every arrival. Path legs were checked against the wall and crate
footprints, and against the graded guard's own body (W0 -> W1 passes 127 cm
clear of it).

## What still needs building

Handed to `/craftbench-build-verifier`:

1. **Scaffold** —
   `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t1-guard-only-spots-what-it-can-see/SightGuardActor.{h,cpp}`
   exactly as inventoried in *Workspace state pre-task*: `SightGuard` tag, `Body`
   / `Eye` (collision OFF, in front of the body) / `Bulb` / `AlertLamp` (red,
   intensity 0), `SetSpotted` + `IsSpotted`, the two pre-set numbers, and **no
   detection logic**.
2. **Map** — `Content/Maps/t1-guard-only-spots-what-it-can-see/L_SightYard.umap`,
   committed binary: striped floor, PlayerStart, both guards, the blocker wall,
   the tagged crate, the painted range arc + cone stripes (no collision), the
   backdrop wall with a marker post at each end, `BP_ThirdPersonGameMode` as the
   World Settings game-mode override, and the placed fixture.
3. **Camera plan** —
   `cameras.json` (the camera-plan lane; not part of this release) framing both
   guards, the crate and >= 4 floor stripes (non-gating;
   authored at authoring time, non-gating).
4. **Fixture** —
   `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t1-guard-only-spots-what-it-can-see/GuardSightFunctionalTest.{h,cpp}`,
   deriving `ACraftBenchFunctionalTest` (NOT the pawn base — the walker is player
   0, the twin is placed). Any control spawner it needs is task-local and
   duplicated; **do not edit either base class.** ASCII-only FAIL text, one
   unique literal per gate (`tasklint::fixture-fail-unique`), and the
   `[t1-guardsight calib]` line at every checkpoint.
5. **Reference** — `reference/Source/ThirdPerson/Tasks/.../SightGuardActor.{h,cpp}`,
   then re-derive the five checkpoint instants from its `calib` lines before
   trusting any MATRIX row.
6. **Discrimination** — `discrimination/` plus `MATRIX.md` with a
   `## Requirements table`. The variants the negative legs were designed around:
   `empty/` (never lights → cp1), `always-on/` (→ cp0 + the control twin),
   `distance-only/` (→ cp0), `los-only/` (→ cp0 and cp2, plus the twin),
   `cone-and-los-no-range/` (→ cp2 — the leg the successor row dropped),
   `range-and-cone-no-los/` (→ cp3), `latched/` (→ cp2), `baked-shadow/`
   (→ cp3 after the crate move).
7. **Gate** — `cb refgate craftbench-public/t1-guard-only-spots-what-it-can-see`
   must grade the committed reference PASS. Until the map, fixture and reference
   exist, `cb lint` errors on the missing `.umap` / fixture source and warns on
   the missing `reference/` — expected at spec-authoring time.

## Known set-level gap (not this task's to fix)

the corpus-ledger tool (since removed) iterates the three basket names
literally, so every task in `tasks/craftbench-public/` is silently omitted from
the generated review page until `"craftbench-public"` is added to that tuple.
Recorded in the set README; it does not turn CI red.
