# t1-pad-throws-you-up-on-contact — provenance and design decisions

## Imported from

`t1-pad-launches-player-on-overlap` in
an internal design note (not shipped) (row 549; hardening status
`ALREADY STRONG`, fixed N = 6). Its draft contract is
an internal design note (not shipped), same id, which
names primitive `pie-checkpoint-sampling`, layers `L1|L2`, and five named
assertions (`PadInertBeforeContact|LaunchRaisesPlayer|ReachesApex|FallsBackUnderGravity|LandsAgain`).
Its per-check rows are in `check-contracts.csv` (review row 123). The rename +
fix list is an internal design note (not shipped) §1 item 5.

## What the owner said

From an internal working note (not shipped), item `1:t1-pad-launches-player-on-overlap`,
answer `agree`:

> "Yes, we could apply the fixes, but this concept is sound"

The feedback row itself, verbatim:

> **Expect:** The pad sits inert until Manny steps on it, then flings him up;
> he rises, hangs at the top, falls back under gravity and lands — and standing
> on the pad again does nothing. The grade proves one clean arc caused by the
> contact, so a pad that fires at BeginPlay or snaps him upward without a fall
> fails.
> **Control:** A second Manny 20 cm off the pad edge, grounded at baseline Z for
> the whole run and gauged at every checkpoint.
> **Do:** build; state the minimum apex in cm and the landing deadline in
> seconds in the prompt; add the second Manny 20 cm off the pad edge; collapse
> checks 4/5/6 into two.
> **Sinks it:** The apex floor and the landing deadline are fixture-declared and
> appear nowhere the agent can read, so a correct-but-conservative launch
> false-FAILs — both numbers must be stated in the prompt.

## What changed from the corpus row, and why

- **Every grade-bearing number is now in the prompt.** The "sinks it" line names
  two (apex, landing deadline); the design has five, and all five are disclosed:
  300 cm apex, 1.0 s minimum air time, 4.0 s landing deadline, 50 cm mid-air
  re-gain tolerance, 10 cm ground tolerance. The corpus row's tolerance cell
  ("Pre-contact height, launch deadline, minimum rise, apex window,
  falling-state checkpoint, and landing-height tolerance are fixed") disclosed
  none of them.
- **Corpus checks 4 + 5 collapsed into one gate**, per the review note.
  `ReachesApex` and `FallsBackUnderGravity` are one shape question about one air
  interval, so they are one named assertion (`RisesThenFallsUnderGravity`);
  `LandsAgain` stays separate as `LandsBackOnTheGround` because it is a
  *deadline*, not a shape. 6 corpus checks -> 5.
- **"Standing on it again does nothing" was re-read as two different
  requirements, and both are kept.** Continued occupancy inside one contact must
  not re-throw (corpus check 3, now `OneThrowPerContact`, measured as "one
  >50 cm rise per air interval"). A *fresh* contact after landing and stepping
  off must throw again — this is the batch's rule 5 (every trigger fires at
  least twice, second firing same measured outcome) and it is the gate that
  catches the one-shot latch, the most common wrong implementation here. The
  corpus row had no second-firing check at all.
- **The velocity floor was dropped as a gate.** The draft contract had a
  "declared velocity or height floor". A disclosed apex of 300 cm plus a
  disclosed 1.0 s air-time floor already kills teleport-up (0.78 s of fall
  only) and snap-up-snap-down (1-2 frames), so a separate velocity threshold
  would be one more number to disclose for no added discrimination.
- **The control twin's geometry is stated as 20 cm of *capsule clearance*.**
  "20 cm off the pad edge" read literally as a centre offset would put the
  twin's capsule (radius 34) *inside* the pad's volume, so a correct
  footprint-based implementation would throw it and false-FAIL. The twin's
  centre is therefore at Y = -254 = pad edge 200 + capsule radius 34 + 20 cm
  clear. This is still deliberately tight: a radius-based "throw anything
  nearby" implementation catches it.
- **The twin is POSSESSED.** An unpossessed `ACharacter` is inert (`MOVE_None`,
  no gravity — the Slice-0 spike recorded in
  `CraftBenchPawnFunctionalTest.h:19-21`), so a "stays grounded" gate on an
  unpossessed twin cannot tell a correct pad from a pad that throws everything.
  The fixture FAILs by name at cp0 if the twin is not walking. Recorded as a
  hidden invariant because it is exactly the permissive-fake shape.
- **The subject is the map's own player character, not a fixture-spawned
  pawn.** The showroom convention wants a visible mannequin, and the batch wants
  the fixture and a human to drive the same path. The map's world settings
  select the stock `BP_ThirdPersonGameMode`, so PIE possesses
  `BP_ThirdPersonCharacter` at the PlayerStart: it carries the mannequin mesh,
  it responds to WASD for a human, and the fixture drives it with the same
  per-frame `AddMovementInput` those inputs route through. The twin is a second
  instance of the *same* read-only class, so "identical twin" is literal.
- **The fixture derives `ACraftBenchFunctionalTest`, not
  `ACraftBenchPawnFunctionalTest`.** The pawn base gives exactly the reductions
  this task wants (`RoseThenFell`, `ApexDeltaZ`, `NumRises`, dense sampling,
  `PawnVisiblyRepresented`), and they were *not* used, for a specific reason:
  `ResolveAgentPawnClass()` walks
  `GetDerivedClasses(ACraftBenchCharacter, bRecursive=true)` over the whole
  loaded module and takes the first non-abstract native subclass
  (`CraftBenchPawnFunctionalTest.cpp:73-103`). This task's deliverable is a pad,
  so it supplies no pawn to prefer and `PreferredAbilityTag()` cannot
  disambiguate — a foreign task's committed pawn (glide, double-jump) could
  become the graded body and change the arc. The three reductions are
  re-implemented locally instead; they are short. Same call means
  `PawnVisiblyRepresented` is not a gate here, which is correct anyway: the
  agent does not author the pawn, so gating on its mesh would grade staging.
- **Visible representation is verifier-owned staging, not a graded
  requirement.** Both characters are stock mannequins from the read-only
  `Content/Characters/Mannequins/` pool. The fixture additionally attaches an
  assert-free `UTextRenderComponent` over each character showing height above
  its own start, peak, and air time, so every graded number has an on-screen
  readout; and the map carries a striped height post with a bright band at the
  disclosed 300 cm line so a reviewer can see a throw clear (or miss) the bar
  from the level itself.
- **Subject-to-twin distance is 254 cm, not the batch's nominal ~300 cm.**
  The owner's "20 cm off the pad edge" is the binding constraint and it fixes
  the distance once the pad is 400 cm across. Both are in one camera frame with
  four stripes visible, which is what the convention is for.
- **`deliverable_root:` was REJECTED and is not in the front matter.** Verified
  against the real parser, not assumed: `tools/verify-single/spec.py`'s
  `_KNOWN_KEYS` is `_SCALAR_KEYS | _LIST_KEYS` and excludes it, and
  `_spec_from_front_matter` raises `ValueError: unknown front matter key(s) …
  deliverable_root` — a hard exit-2 "spec malformed", not a graded FAIL. The
  deliverable root is therefore the first line of `## Workspace state pre-task`
  and is restated in the prompt body. Those are the only two agent-visible
  sections (`tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`), so the
  statement genuinely reaches the agent from both places. `set:
  craftbench-public` parses clean — `set` has no enum validation.
- **Heading text follows `docs/AUTHORING_TEMPLATE.md`, so the section is
  `## Workspace state pre-task`**, not the batch brief's paraphrase "Workspace
  pre-state". That heading text is FROZEN in `prompt_extract.py`; a paraphrase
  would silently drop the deliverable-root line from what the agent sees.
- **Concept id is `collision-overview`, a real row in
  `tools/coverage/concepts.csv`.** The two sibling built tasks use
  `ps-collision-overlap` (`cpp/t1-overlap-teleport-portal`) and `char-movement`
  (`cpp/t2-ladder-climb-volume`), and **neither id exists in `concepts.csv`** —
  so they were not copied. `collision-overview` is high-tier, in-scope, and
  filed under Gameplay Programming, which is also this task's
  `capability_bucket`.

## Timeline calibration — read before pinning

The schedule `{0.6, 2.9, 6.6, 8.8, 13.2}` in the spec is DERIVED, not measured.
It assumes the stock third-person character's max ground speed (~500 cm/s) with
CMC default acceleration (2048), a 700 cm approach from the PlayerStart, and
standard gravity (980):

| Event | Derivation | Derived t |
|---|---|---|
| drive starts | cp0 | 0.6 |
| contact #1 | 61 cm to reach speed (0.24 s) + 639 cm at 500 | ~2.1 |
| cp1 sample | contact + ~0.8 s (rising for any apex >= 300) | 2.9 |
| landing #1 | apex 300 -> 1.57 s air; apex 800 -> 2.56 s air | 3.7-4.7 |
| landing deadline | contact + 4.0 (disclosed) | 6.1 |
| cp2 sample | 0.5 s past the deadline | 6.6 |
| far mark reached | up to 800 cm from the landing spot | ~8.4 |
| cp3 sample | after arrival, before the reverse drive | 8.8 |
| contact #2 | ~566 cm back to the volume's near face | ~10.2 |
| cp4 sample | contact #2 + worst-case 2.56 s arc + margin | 13.2 |

`TimeLimit` lands at 15.2 s via `SetCheckpointSchedule`'s margin. **Pin every
one of these against the reference's `[t1-pad calib]` log lines before
claiming the task is runnable** — the house convention (see
`tasks/cpp/tp2-sprint-stamina/task.md` "Hidden invariants", which records a
calibration that had to move). Two specific things to re-measure rather than
trust: the stock character's actual `MaxWalkSpeed` on this substrate, and
whether the first landing lands past the pad (horizontal speed preserved) or
back on it (horizontal speed zeroed) — the gates are written to accept both,
but cp3's `|X| >= 400` off-pad assertion is the one that moves if the landing
spot moves.

## What still needs building

The build-verifier skill owns all of this; none of it exists yet.

1. **Scaffold** — `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t1-pad-throws-you-up-on-contact/ContactPadActor.{h,cpp}`:
   `AContactPadActor : AActor`, a 400 x 400 x 20 cm visible plate root, a
   400 x 400 x 500 cm query-only box volume with overlap generation on standing
   on the plate, `Tags.Add(FName("ContactPad"))`, and **no** behaviour. The
   volume is deliberately taller than the disclosed 300 cm apex so the
   canonical implementation is not forced into a bounce; the gates accept a
   bounce anyway.
2. **Map** — `UE-projects/ThirdPerson/Content/Maps/t1-pad-throws-you-up-on-contact/L_PadLane.umap`,
   committed binary. Contents are enumerated in `## Workspace state pre-task`:
   3600 x 1400 floor at Z = 0, 200 cm stripes, the placed pad at the origin,
   PlayerStart at (-700, 0, 92) facing +X, the twin's marked spot as a **painted
   floor decal and nothing else** (the twin is spawned by the fixture, so the map
   must NOT place a character there — two capsules at (0, -254, 92) means the spawn
   either returns null and trips the PrepareTest assert, or gets displaced, and a
   displaced/interpenetrating capsule can breach `|Twin Z - TwinBaseZ| > 10` and
   false-FAIL gate 7 on correct work), the 300 cm
   height post at (0, +300), the far mark at X = +800, two distinct landmark
   posts at X = -1300 / +2100, and world settings selecting
   `BP_ThirdPersonGameMode`. **The basename is unique repo-wide, deliberately.**
   This spec originally declared `L_ContactLane`, which two siblings also declared
   — a blocker, not a design choice: `locate_map` raises
   `DuplicateMapBasenameError` on two candidates (it globs both
   `Content/Maps/<map>.umap` and `Content/Maps/*/<map>.umap`), so both tasks would
   have returned exit 7 HARNESS-ERROR for every submission, and `cb lint` cannot
   detect it. Renamed to `L_PadLane` 2026-08-17.
3. **Fixture** — `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t1-pad-throws-you-up-on-contact/PadContactLaunchFunctionalTest.{h,cpp}`,
   `APadContactLaunchFunctionalTest : ACraftBenchFunctionalTest`. Owns: the
   tag-resolved pad, `GetPlayerCharacter` subject resolution, **its own local
   twin spawner** (duplicated per task, owner-approved — the base has no
   second-subject API and adding one is the other machine's change), dense
   per-tick sampling, the local air-interval/rise reductions, the two
   continuous guards, the per-frame drive, the seven named FAIL messages
   (ASCII-only, cp1252 log read-back rule), the `[t1-pad calib]` line, and the
   assert-free text readouts.
4. **`cameras.json` (the camera-plan lane; not part of this release)** — authored now, per the checklist step-5 standard. Must
   frame the pad, the subject, the twin and at least four floor stripes in one
   shot, with both backdrop landmarks visible so a moving camera is
   distinguishable from a still one; a second shot at cp1/cp2 wide enough to
   contain the 300 cm band on the height post and the whole arc.
5. **Reference solution** — `reference/Source/ThirdPerson/Tasks/t1-pad-throws-you-up-on-contact/ContactPadActor.{h,cpp}`.
   Bind the volume's begin-overlap delegate, filter to a character, apply one
   upward impulse. 25-60 LOC. Must refgate PASS token-free from git HEAD
   (`cb refgate craftbench-public/t1-pad-throws-you-up-on-contact`).
6. **Discrimination variants** — the automatic reference-PASS / empty-FAIL legs
   plus hand-authored variants only for holes the requirement-to-gate table
   actually leaves. The four worth writing, because each targets a *different*
   named gate: throw-at-play-start (must FAIL `PadInertBeforeContact`),
   one-shot latch (must FAIL `SecondContactThrowsAgain`), set-Z-then-let-gravity
   (must FAIL `RisesThenFallsUnderGravity` on air time), and radius-instead-of-
   footprint (must FAIL `ControlStaysGroundedThroughout`).
7. **Known set gap, not this task's bug** — the corpus-ledger tool (since removed)
   iterates `("cpp", "bp", "python")` literally, so every task in
   `craftbench-public` is invisible on the generated review page until
   `"craftbench-public"` joins that tuple. Documented in
   `tasks/README.md`; it does not turn CI red.
