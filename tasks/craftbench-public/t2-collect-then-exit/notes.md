# t2-collect-then-exit — provenance and design decisions

## Imported from

`t2-collect-unlock-portal-win` in an internal design note (not shipped)
(row 195; "ALREADY STRONG", 8-check rubric, `Score k/8 · PASS = 8/8`). Contract row
for the same id in an internal design note (not shipped)
(family `collect-unlock-win-loop`, primitive `pie-checkpoint-sampling`,
`L1|L2`, assertions
`PickupCountsExactlyOnce|PortalClosedBeforeAll|PortalOpensAtRequiredCount|EntrySetsWin|NoPrematureWin`).
Owner-ordered pilot-queue row 12; Wave 1 slate #1, fixture family **F-A**
(`L_CollectArena`) in an internal design note (not shipped).
Design lines followed verbatim from an internal design note (not shipped)
§1 (Expect / Control / Do / Sinks-it).

## What the owner said

an internal working note (not shipped), key `cand/1:t2-collect-unlock-portal-win`:

```json
{ "answer": "build", "note": "The name could be simplified to t2-collect-then-exit" }
```

The rename is applied — it is the folder name and the front-matter `id`. The
ADOPTION-REVIEW's own proposed id (`t2-exit-opens-when-every-relic-is-gathered`) is
superseded by the owner's shorter one.

## What changed from the corpus row, and why

- **Renamed** `t2-collect-unlock-portal-win` → `t2-collect-then-exit` (owner note
  above). "Portal" also went out of the vocabulary: the corpus called the same
  object a portal, the feedback calls it an exit, and the prompt now says exit
  throughout so the agent-visible language is internally consistent.
- **Placement moved to the verifier, and corpus checks 1-2 demoted to unscored
  preconditions.** The corpus made the level-placement surface agent-writable and
  then scored `RequiredPickupCountExists` + `PickupsInsidePlacementArea` — two
  points an empty submission banks for free (owner's *Do* line). The committed map
  now ships all four relics; those two facts are asserted in `PrepareTest` and
  reported as `HARNESS-PRECONDITION:` errors so a staging regression reads as
  staging, never as a model failure. Side benefit: the deliverable collapses to
  pure C++ under `Source/ThirdPerson/`, which is the batch's declared surface, and
  no `Content/` asset-write lane is needed at all.
- **Added the control the corpus had no concept of:** a **fourth** relic the route
  never visits, identical in class, tag, mesh and name to the required three,
  parked 300 cm from the last required one so both are in one camera frame. It is
  gauged at *every* checkpoint for presence, position (within 25 cm) and
  non-contribution, plus a per-frame guard. This is the owner's strongest
  corpus-wide ask and the built tree has it exactly once.
- **Every graded value is now something you can photograph.** The corpus graded a
  "readable Count/Portal/Victory state shell" — three invisible values, which is
  precisely its *Sinks it* line. Replaced by: a two-faced signboard (`TallyText`
  showing `k/3`, `StatusText` showing `SEALED` / `OPEN` / `ESCAPED`) and the exit's
  lamp going 0 → ≥ 5000. The before and after photographs are "exit dark, tally
  `0/3`, SEALED" and "exit bright, tally `3/3`, ESCAPED, one relic still standing".
  The signboard ships **blank**, deliberately, so the before-photograph is earned
  rather than free.
- **Every number the grade reads is in the prompt**: four relics, three required,
  the `k/3` format, the three status words, brightness `0` and `5000`. The corpus
  row disclosed none of them (it said "the fixture-declared number"), which is the
  false-FAIL mode that sank several sibling rows.
- **Every trigger fires at least twice** (batch convention; the corpus had it on 8
  of 244 rows): three relic pickups, **two** sealed-exit contacts (at tally 0 and
  at tally 2), and **two** open-exit entries (walk in, walk out, walk in again).
  The second firing must produce the same measured outcome.
- **Kept the divergent pair** (owner's *Do*): `PortalClosedBeforeAll` reads the
  lamp, `NoPrematureWin` reads the status word, and they are asserted separately at
  cp1 and cp5 — an implementation that leaves the exit sealed but wins on sealed
  contact passes one and fails the other.
- **Added a re-touch leg** (cp2 → cp3): the character steps 300 cm off the first
  relic's spot and walks back over it, and the tally must not move. This is the one
  new idea `startup-feedback.md:574` folds in here from the dropped
  `t3-sob-objective-any-order` row, and it is what tells "consumed" apart from
  "invisible but still live".
- **Two forgiving predicates instead of exact-mechanism reads**, so the gate scores
  the outcome and not the route: `VisiblyGone` accepts destroy / hide / remove-from-
  arena, and `LampBrightness` treats a hidden lamp as dark. Without these, a
  submission that hides a relic (visually identical to a human) or switches the lamp
  by visibility (ditto) would false-FAIL.
- **No key press anywhere.** The corpus contract said "overlap and input probes";
  the graded trigger is walking into a volume, driven by the shipping per-frame
  `AddMovementInput` timeline, so a human with WASD drives the identical route.
- **Per-frame guards replace sample-point trust.** G1-G5 evaluate every tick
  against fixture-owned truth (its own contact counter, its own record of entering
  the exit volume) rather than against the submission's readout — the same shape as
  the continuous pre-contact guard in `TeleportPortalFunctionalTest`.
- **`deliverable_root:` was NOT added to the front matter.** Verified against the
  real parser: `tools/verify-single/spec.py::_KNOWN_KEYS` rejects it with
  `ValueError: unknown front matter key(s) … deliverable_root`, which is exit 2
  "spec malformed", not a graded FAIL. Per the set README's mitigation the path is
  instead stated as the first line of `## Workspace state pre-task`, in the
  agent-visible prompt, and in the spec preamble.
- **Deliberately NOT adopted**, so the first Game-Loops task stays a T2:
  the arming delay from `t3-sob-portal-timer-gate`, the 1/N gradual material scalar
  from `t3-sob-portal-partial-credit`, and readable key ownership from
  `t2-key-locked-exit` — all three are pointed at this row by
  `startup-feedback.md:573-576` as "one extra check". They are additive later;
  each one adds a leg and a calibration to a task that already runs ~24 s.
- **Known loss, carried from the merge, not introduced here:** weighted per-item
  accumulation and the threshold crossing *with items still on the floor* died when
  `t2-collect-energy-portal-win` was merged into this row — a count-gated exit
  cannot express an early crossing (`startup-feedback.md:685`). The spare relic
  recovers half of it (the exit opens with a relic still on the floor); the weighted
  values are genuinely gone and want their own row.

## What still needs building

Everything below is `/craftbench-build-verifier`'s job — this folder deliberately
contains only `task.md` and `notes.md`. Until the fixture source and the map binary
exist, `cb lint` on this task ERRORs on `fixture-source-exists` and
`map-binary-exists`; that is expected for a spec-only landing, not a defect.

1. **Scaffolds** under `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t2-collect-then-exit/`:
   `RelicPickup.{h,cpp}` (visible mesh + query-only sphere `RelicVolume`, tag
   `ArenaRelic`), `ExitGate.{h,cpp}` (arch mesh + box `ExitVolume` + light
   `ExitLamp` at Intensity 0, tag `ArenaExit`), `ArenaSignboard.{h,cpp}` (two
   in-world text components `TallyText` / `StatusText`, both blank, tag
   `ArenaBoard`). All behaviour-free.
2. **Fixture** `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-collect-then-exit/CollectThenExitFunctionalTest.{h,cpp}`,
   deriving `ACraftBenchFunctionalTest` (**not** the pawn base — the hero comes
   from the PlayerStart and is resolved by possession; no local pawn spawner is
   needed because the control subject is a placed relic). Nine checkpoints, an
   eight-leg waypoint drive released one leg per checkpoint, the five continuous
   guards, the `[t2-collect calib]` log line.
3. **Map** `UE-projects/ThirdPerson/Content/Maps/t2-collect-then-exit/L_CollectArena.umap`:
   solid floor X 0..2400 / Y -1200..+1200 with 200 cm stripes, a landmark at each end
   of the backdrop, PlayerStart at ~(300, 0, 100) facing +X, four relics at
   ~(900,-500) / (1500,+500) / (1900,-500) / (1900,-1000), the exit at (2100, 0)
   with a relic-free centre lane Y ∈ [-200,+200], the signboard beside it, and the
   placed fixture. **Open builder decision:** World Settings can select the stock
   `BP_ThirdPersonGameMode` (already defaults to the mannequin
   `BP_ThirdPersonCharacter`) or a thin per-task C++ game mode; either satisfies
   the spec, which only requires that Play possesses a visibly represented
   character on the mark. Prefer the stock asset — it needs no new scaffold and no
   `/Game/Characters/` mesh wiring, which is where `tp2-sprint-stamina` ended up
   with an invisible hero.
4. **`cameras.json` (the camera-plan lane; not part of this release)** framing the exit, the signboard, the last relic pair (the one
   that vanishes and the one that stays) and ≥ 4 floor stripes, with both backdrop
   landmarks in shot; a shot assigned to cp0 (before), cp6 (unlock) and cp8 (after).
5. **Reference solution** at `reference/Source/ThirdPerson/Tasks/t2-collect-then-exit/…`,
   closed out by `cb refgate craftbench-public/t2-collect-then-exit` grading PASS.
6. **Discrimination** `discrimination/` + `MATRIX.md`: at minimum the automatic
   reference-PASS / empty-FAIL legs plus the requirements table. Hand-authored
   variants worth the money, each aimed at a named assertion: `open-at-start/`
   (lamp lit in the constructor → G1), `win-on-contact/` (any exit contact wins →
   cp1 status assertion), `count-everything/` (collects the fourth relic → G5),
   `double-count/` (increments per overlap tick → G3), `latch-once/` (lamp reverts
   or win clears on exit → G4).
7. **Calibration, before MATRIX.md**: the nine checkpoint instants and the per-leg
   arrival tolerances are estimates in the spec (500 uu/s stock walk speed + accel
   margin, ~24 s total). Run the reference once, read the `[t2-collect calib]`
   lines, and pin the instants so every leg completes with margin at the worst
   framerate the task ships at. Also confirm the light unit/threshold: the spec
   discloses `>= 5000`, so the reference must set exactly that or more, and the
   builder must confirm the shipped `ExitLamp` reads `Intensity == 0` at play start
   on the committed map.
8. **Set-level bookkeeping**: `tasks/CATALOG.md` row, `docs/MAPS.md` row + the
   `cb lint` map count, and note that
   the corpus-ledger tool (since removed) still iterates only the three basket
   names, so this task is invisible to the generated review page until
   `"craftbench-public"` is added to that tuple (README's known gap — not a CI red).
