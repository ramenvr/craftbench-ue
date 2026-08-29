---
id: t2-collect-then-exit
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_CollectArena :: ACollectThenExitFunctionalTest"]
---

# t2-collect-then-exit

The first complete playable loop in the tree: walk the arena picking relics up, an
on-screen n-of-N tally climbs, at N the dead-black exit lights up, and walking into
it wins. Imported from the Startup Eval corpus row `t2-collect-unlock-portal-win`
(renamed by the owner); provenance and every deviation are in `notes.md`.

Everything the grade reads is something a human watching Play can see: a two-faced
signboard (the tally and the status word), the exit's lamp going from dark to
bright, and relics visibly vanishing. The control is a **fourth relic the route
never visits** — it must still be standing, at its spot, at every single
checkpoint, and it must never once be counted.

`deliverable_root`: `Source/ThirdPerson/` — see the first line of *Workspace state
pre-task*. The front-matter key of that name is **rejected by the parser**
(`tools/verify-single/spec.py::_KNOWN_KEYS`), so per the set's README the path is
stated twice in agent-visible prose instead: in the prompt block and in the first
line of *Workspace state pre-task*. Those two H2s are exactly
`tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`.

## Primary concept

- `game-mode-and-game-state` — Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

What the verifier reads most directly is match-level objective state and its
terminal latch: a counted objective (3 of 4 relics), a gate that is a pure
function of that count, and a victory state that is entered exactly once and never
leaves. Contact detection on the relics and on the exit is the adjacent surface the
count is driven from, not the thing under test — an overlap edge is already the
primary concept of built `cpp/t1-overlap-teleport-portal`. The agent is free to
hold the count on the game mode, the game state, the exit, a subsystem or the
character; the gate never looks at where it lives, only at what the arena shows.

## Prompt given to the agent

> Four relics stand in the arena and the exit at the far end is sealed. Gathering
> three relics opens the exit; walking into an open exit wins the run. All of this
> must happen from the moment play begins, driven only by the character walking
> into things — no key presses anywhere.
>
> - The signboard's tally face shows how many relics have been gathered, out of
>   three: `0/3` when play begins, rising to `3/3`. Spacing is yours; the two
>   whole numbers and the slash between them are not.
> - The signboard's status face reads `SEALED` while the exit is sealed, `OPEN`
>   once the exit is open, and `ESCAPED` once the run is won.
> - The exit's lamp is dark — brightness 0 — while the exit is sealed, and is at
>   least 5000 bright once the exit is open. It must never go dark again after
>   that, and the exit must never re-seal.
> - When the character walks into a relic, that relic disappears from the arena
>   for good and the tally rises by exactly one. Walking back over the spot where
>   a relic stood must change nothing. A relic the character never walks into must
>   still be standing within 25 cm of where it was placed, at every moment of the
>   run, and must never be counted.
> - "Walks into" means the character's capsule reaching a relic's own contact
>   volume — a sphere of radius 120 cm around the relic, as shipped. No two relics
>   are within 500 cm of each other, so one contact can only ever be one relic.
> - The exit stays sealed and the run stays unwon until the third relic is
>   gathered. Touching a sealed exit, however many times, must never win. Only
>   walking into an open exit wins, and once the run is won it stays won — the
>   character can walk out of the exit and back in and it is still won.
>
> Implement in C++ in the existing gameplay module under `Source/ThirdPerson/` —
> do not edit the level, any config file, or any test file. Keep the signboard's
> two faces and the exit's lamp: they are the readouts your work is judged on, and
> you may add more on top of them but not instead of them.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`.** That is the agent-writable module on
this project; a file written under `Source/CraftBenchTemplate/` is a
SANDBOX-REJECT (exit 4), not a graded FAIL.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-collect-then-exit/RelicPickup.h` / `.cpp` — declares and defines
  `class THIRDPERSON_API ARelicPickup : public AActor`. The constructor builds a
  visible floating mesh plus a query-only sphere volume (`RelicVolume`, root,
  **`SphereRadius = 120.0f`**, overlap events enabled, Overlap response on all
  channels) and adds
  `Tags.Add(FName("ArenaRelic"))`. **No pickup handling, no counting, no removal
  ships.** All four placed relics are instances of this one class and are
  indistinguishable from one another — no per-instance tag, flag or name says
  which three are required.
- `Tasks/t2-collect-then-exit/ExitGate.h` / `.cpp` — declares and defines
  `class THIRDPERSON_API AExitGate : public AActor`. The constructor builds the
  archway mesh, a query-only box volume (`ExitVolume`, overlap events enabled) and
  a light component named `ExitLamp` whose Intensity is **0**, and adds
  `Tags.Add(FName("ArenaExit"))`. **No unlock logic, no entry handling, no
  victory state ships.**
- `Tasks/t2-collect-then-exit/ArenaSignboard.h` / `.cpp` — declares and defines
  `class THIRDPERSON_API AArenaSignboard : public AActor`: a board mesh carrying
  two in-world text components named `TallyText` and `StatusText`, **both shipped
  blank**, and `Tags.Add(FName("ArenaBoard"))`. Nothing writes to either face.
- `Content/Maps/t2-collect-then-exit/L_CollectArena.umap` — the arena (below).

The arena, as committed:

- A solid floor spanning the whole route (X 0..2400, Y -1200..+1200, top at Z=0),
  striped every 200 cm across X so distance and speed are readable by eye, with a
  distinct landmark at each end of the backdrop. Every relic, including the one the
  route never visits, stands at least 200 cm inboard of a floor edge — no relic sits
  *on* a bound that a predicate also tests.
- A `PlayerStart` **on** that floor at roughly (300, 0, 100), off the world
  origin, facing +X toward the exit. World Settings select a game mode whose
  default pawn is the stock third-person mannequin character
  (`/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`), so hitting Play
  possesses a **visibly represented** character on the mark and WASD walks the
  same route the verifier drives.
- Four `ARelicPickup` instances, all tagged `ArenaRelic`, at approximately
  (900, -500), (1500, +500), (1900, -500) and (1900, -1000) — the last two 500 cm
  apart, so the relic that vanishes and the relic that stays sit side by side in
  one camera frame while staying well outside each other's 120 cm contact volume.
  500 cm is also the smallest gap between any two relics in the arena.
- One `AExitGate` (tagged `ArenaExit`) centred at (2100, 0), its volume straddling
  the centre lane. The lane Y in [-200, +200] is deliberately relic-free, so the
  route can reach the sealed exit without touching a relic.
- One `AArenaSignboard` (tagged `ArenaBoard`) beside the exit, its two faces
  turned toward the camera.
- One placed `ACollectThenExitFunctionalTest`.
- A `cameras.json` (the camera-plan lane; not part of this release) framing the exit, the signboard, the last relic pair and at
  least four floor stripes, with both backdrop landmarks in shot.

Files that **do not exist**:

- No overlap handler, no count, no board writes, no lamp control, no victory
  state, no Blueprint subclass, no level edits. The empty submission compiles (L1
  green) and FAILs L2 at the first checkpoint on a blank signboard.
- No test source in the agent's writable path. `ACollectThenExitFunctionalTest`
  lives in the separate `CraftBenchTests` module the agent can neither read nor
  modify.

## Verifier specification

The test runs in PIE from `Content/Maps/t2-collect-then-exit/L_CollectArena.umap`
on the **ThirdPerson** substrate, at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** (`docs/pie-verification-playbook.md` §2), driven by
the shipping per-frame `AddMovementInput` walk timeline
(`Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194`,
`Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246`,
`Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144`) and composed with
in-fixture **pie-state-probe** reads of the two text faces, the lamp and relic
presence. No new verifier mechanism is invented.

**Subjects, and the one that must not change.** The graded subject is the arena
loop (relics + exit + board). The **control is the fourth relic**, at (1900, -1000),
which the route never visits: it is gauged at **every** checkpoint for visible
presence, for standing within 25 cm of its authored spot, and for never having
contributed to the tally. It is a *placed actor*, not a second pawn, so this
fixture needs no second-subject spawner: the hero comes from the map's PlayerStart
and game mode and is resolved by possession, and
`ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()` is not used at all. **Do not
go looking for a shared two-subject helper and do not edit the base classes** —
`ACraftBenchFunctionalTest` / `ACraftBenchPawnFunctionalTest` are owned elsewhere
and spawn exactly one pawn; where a batch task needs a second *pawn*, it duplicates
a local spawner in its own fixture (owner-approved duplication). This task needs
neither.

**Preconditions, not scored checks.** The corpus rubric's checks 1 and 2
(`RequiredPickupCountExists`, `PickupsInsidePlacementArea`) are static placement
facts that the committed map supplies and an empty submission therefore earns for
free. They are asserted in `PrepareTest` as staging preconditions and reported via
`FinishTest(EFunctionalTestResult::Error, "HARNESS-PRECONDITION: …")` — the shipped
convention (`HudLayoutFunctionalTest.cpp:52`) — so a staging regression is legible
as a staging regression and never as a model failure. They score nothing.

**Two forgiving predicates, so a correct-but-different route is not false-FAILed:**

- `LampBrightness(exit)` = 0 when the lamp component is hidden or not visible,
  otherwise its Intensity. Turning the lamp off by visibility and by intensity both
  read as dark, because both look identical to a human.
- `VisiblyGone(relic)` = the actor is destroyed, **or** its mesh is hidden, **or**
  it has left the arena bounds, where **arena bounds = the floor extent expanded by
  300 cm in every direction** (X -300..2700, Y -1500..+1500, Z -300..+600).
  Consuming a relic by destroying, hiding or removing it all read as gone.
  `VisiblyPresent` is the negation, and the control relic must satisfy it at every
  checkpoint. The 300 cm of slack exists so that a relic authored *near* a floor
  edge can never read GONE by settling or by float epsilon — the control at
  (1900, -1000) sits 500 cm inside this boundary, not on it.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ACollectThenExitFunctionalTest (derives ACraftBenchFunctionalTest):

    PrepareTest():
        Super::PrepareTest()
        Hero = UGameplayStatics::GetPlayerCharacter(World, 0)   // identity by possession
        Relics = GetAllActorsWithTag("ArenaRelic")              // identity by tag, never class
        Exit   = GetAllActorsWithTag("ArenaExit")
        Board  = GetAllActorsWithTag("ArenaBoard")
        PRECONDITIONS (Error + "HARNESS-PRECONDITION:", unscored):
            Hero valid; exactly 4 relics; exactly 1 exit; exactly 1 board;
            board exposes TallyText + StatusText; exit exposes ExitLamp;
            every relic transform inside the authored placement area
        Route = the 8-leg waypoint list; Spare = the relic nearest (1900,-1000)
        Required = the other three (NO ordering is assumed of them)
        Contacted = {} (an empty SET of relic pointers — fixture-owned truth)
        SetCheckpointSchedule({0.7, 5.0, 8.4, 10.6, 13.8, 16.4, 18.5, 20.6, 23.8})

    Tick (every frame, after the base checkpoint clock):
        // drive: one leg per checkpoint window; the leg is released by the
        // checkpoint that graded the previous one, so the next observable is
        // never reached before the current one is graded.
        if (leg active) Hero->AddMovementInput(unit(dir to waypoint), 1.0)
        if (arrived within tolerance) leg = idle

        // COUNT — a SET of distinct relics, never an index high-water mark, so
        // the order GetAllActorsWithTag happened to return Required in cannot
        // change any verdict.
        for (R : Required)
            if (dist2D(Hero, R) <= K_FIXTURE_CONTACT)   // 300.0f, see below
                Contacted.Add(R)
        Taken = Contacted.Num()          // 0..3

        // CONTINUOUS GUARDS — every frame, so there is no gap between samples
        // to thread. All five gate on FIXTURE-owned truth, never on the
        // submission's own readout.
        G1  Taken < 3 and LampBrightness(Exit) > 0
              -> FAIL "the exit lit up before the third relic was gathered"
        G2  Hero has not yet entered ExitVolume-expanded-by-K_FIXTURE_MARGIN
            while Taken == 3, and StatusText reads ESCAPED
              -> FAIL "the run was won without walking into an open exit"
        G3  ReadTally() > Taken
              -> FAIL "the tally counted more relics than were walked into"
        G4  a previously-lit lamp reads dark again, or a previously-ESCAPED
            status stops reading ESCAPED
              -> FAIL "the exit re-sealed" / "the win did not persist"
        G5  Spare is not VisiblyPresent, or has moved > 25cm
              -> FAIL "the relic nobody walked into did not survive the run"

    OnCheckpoint(i, t):   // every checkpoint also gauges the control: Spare
                          // VisiblyPresent at its spot, and ReadTally() == Taken
        cp0 t=0.7   BEFORE PHOTOGRAPH: tally reads 0/3, status SEALED,
                    LampBrightness == 0, all four relics VisiblyPresent
                    (named FAIL: "the tally face was blank when play began")
                    release leg 1 -> walk up the centre lane into the exit
        cp1 t=5.0   sealed contact #1 (Taken == 0, Hero inside ExitVolume):
                    LampBrightness == 0
                      -> "the exit was already lit on the first sealed contact"
                    status != ESCAPED
                      -> "the first sealed contact won the run"
                    [the divergent pair: an exit that stays shut but wins on
                     locked contact passes the first and fails the second]
                    release leg 2 -> walk to relic A
        cp2 t=8.4   relic A: VisiblyGone, tally == 1/3, status SEALED, lamp dark
                      -> "the first relic was not consumed and counted"
                    release leg 3 -> step 300cm off A's spot and back over it
        cp3 t=10.6  RE-TOUCH: tally still 1/3, no relic reappeared
                    (named FAIL: "walking back over a gathered relic counted
                     it again")
                    release leg 4 -> walk to relic B
        cp4 t=13.8  relic B: VisiblyGone, tally == 2/3, status SEALED, lamp dark
                      -> "the second relic was not consumed and counted"
                    release leg 5 -> walk back into the exit
        cp5 t=16.4  sealed contact #2 (Taken == 2) [second firing, same measured
                    outcome as cp1, its OWN literals]:
                    lamp dark + status SEALED
                      -> "the exit opened on the second sealed contact, two
                          relics in"
                    status != ESCAPED
                      -> "the second sealed contact won the run"
                    release leg 6 -> walk to relic C
        cp6 t=18.5  UNLOCK INSTANT: relic C VisiblyGone, tally == 3/3,
                    status OPEN, LampBrightness >= 5000
                      -> "the exit did not open when the third relic was gathered"
                    AND status != ESCAPED (unlocking alone must not win)
                      -> "opening the exit won the run without an entry"
                    release leg 7 -> walk into the now-open exit
        cp7 t=20.6  status ESCAPED, lamp still >= 5000, tally still 3/3
                      -> "walking into the open exit did not win the run"
                    release leg 8 -> walk out 500cm and back into the exit
        cp8 t=23.8  AFTER PHOTOGRAPH [second firing of the win, its OWN literal]:
                    status still ESCAPED, lamp >= 5000, tally 3/3
                      -> "the win did not survive leaving the exit and
                          re-entering it"
                    and the untouched relic still standing on its spot
                      -> "the relic nobody walked into was gone by the end of
                          the run" -> Succeeded

    every checkpoint logs "[t2-collect calib] cp<i> t=<t> taken=<n>
    tally='<s>' status='<s>' lamp=<f> relics=<n>" (LogTemp/Display) for
    tolerance and timing calibration.
```

**The one-sided margin that keeps G1/G2/G3 honest, and why it is one-sided.**
`Taken` and the fixture's exit-entry flag are the *upper bound* the submission's
readouts are checked against, so the fixture must register a contact **no later
than** the engine does — otherwise every legitimate pickup opens a window in which
`ReadTally() == Taken + 1` and G3 FAILs correct work, and the third pickup lights
the lamp while `Taken` is still 2 and G1 FAILs it. Numbers:

- The engine's begin-overlap edge fires when the hero capsule surface meets the
  120 cm `RelicVolume` surface, i.e. at centre-to-centre `<= 120 + 34 = 154 cm`
  (`ACraftBenchCharacter` keeps `ACharacter`'s default 34 cm capsule radius).
- `K_FIXTURE_CONTACT = 300.0f` — nearly **double** that, so on any approach path
  the fixture counts the relic several frames *before* the overlap can fire.
  One-sided by construction: the fixture may count early, never late, and the
  submission is never asked to match the fixture's instant, only to stay under it.
- `K_FIXTURE_MARGIN = 150.0f` expands the exit volume the same way for G2's own
  entry flag, so an entry-driven win can never be graded before the fixture agrees
  an entry happened.
- The margin cannot fire spuriously: the centre lane (Y = 0) that legs 1, 5, 7 and
  8 walk is 500 cm from the nearest relic, and no two relics are closer than
  500 cm — both comfortably outside 300 cm. So a leg can neither bank a relic it
  did not reach nor bank two at once.
- The per-checkpoint `ReadTally() == Taken` gauge is only ever sampled at a
  checkpoint, and every checkpoint sits at least 1.5 s after the leg that reached a
  relic has gone idle — so the ~0.3 s in which the fixture has counted and the
  engine has not is never a graded instant.

**Text comparison, and what a blank face reads as.** `TallyText` is compared with
all whitespace stripped, so `2/3`, `2 / 3` and `2  /  3` are all accepted;
`StatusText` is compared case-insensitively after trimming. The words and the
format are disclosed in the prompt, so no correct submission can be surprised by
them. **`ReadTally()` returns `-1` when the tally face does not parse as
`<int>/<int>`** — which is exactly what the shipped-blank board reads. `-1` is
never `> Taken`, so G3 cannot trip on an unwritten board and the empty submission
FAILs where it should: on cp0's named `the tally face was blank when play began`.
The gauge `ReadTally() == Taken` likewise fails cp0 by that same named message
rather than by a garbage guard.

**Scored rubric** (the L2 gate is all-or-nothing; this is the corpus rubric's
6 remaining checks and where each lands): `PickupsConsumedExactlyOnce` → cp2/cp3/
cp4/cp6 + G3; `PickupCountIncrementsExactlyOnce` → cp2/cp4/cp6 + the
per-checkpoint `ReadTally() == Taken` gauge; `PortalClosedBeforeAll` → cp0/cp1/cp5
+ G1; `PortalOpensAtRequiredCount` → cp6; `EntrySetsWin` → cp7/cp8 + G4;
`NoPrematureWin` → cp0/cp1/cp5/cp6 + G2.

**Which of those are free to a do-nothing submission, said plainly.**
`PortalClosedBeforeAll` and `NoPrematureWin` are **fail-only guards**: an
unimplemented arena never lights its lamp and never writes `ESCAPED`, so an empty
submission satisfies both, and all five continuous guards G1–G5 are vacuous on it
too. They bank **no credit**, because the L2 verdict is a single all-or-nothing
`AFunctionalTest` outcome with no k/N partial score, and the empty submission dies
at cp0 on the blank board before any of them is reached. They are kept for the same
reason the owner's guidance for the sibling row keeps its predicate check
(`an internal design note (not shipped):139`): they are the only scored
defence against opening everything at `BeginPlay`, and that defence is worth having
even though it is free to a submission that does nothing at all.
`PortalOpensAtRequiredCount` (cp6) and `EntrySetsWin` (cp7/cp8) are the two rows an
empty submission cannot satisfy.

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: relics, exit
and board by tag, the hero by possession, the readouts by the shipped component
names — never by C++ class, so subclassing any scaffold grades identically.

## Reference solution metadata

- LOC range: 110-180 (relic contact handling + one-shot consumption, a count that
  lives wherever the agent chooses, both board faces written on every change, the
  lamp driven from the count, exit contact gated on the count, a victory latch)
- Files touched: 4-6 (the three pre-existing scaffold pairs; a solution that puts
  the count on a new game-state class adds one pair)
- Senior-dev hours: 2-4

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffolds compile untouched,
   so L1 is green. *Defense*: cp0 reads the shipped-blank signboard and FAILs by
   the named message `the tally face was blank when play began` — FAIL-on-empty,
   not differs-from-reference. Nothing about the before-photograph is free: the
   two placement checks an empty submission *would* have earned are demoted to
   unscored preconditions.
2. **Exit opens, or the run is won, without the count.** *Failure mode*: the lamp
   is lit at play start or on a timer; or victory is latched at play start, on any
   relic pickup, or on contact with a *sealed* exit. *Defense*: G1 and G2 run on
   **every frame** against the fixture's own `Taken` counter and its own record of
   entering the exit volume, so there is no interval between checkpoints to land
   in; and cp1/cp5 keep the corpus's divergent pair — an implementation that
   leaves the exit sealed but wins on sealed contact passes the lamp assertion and
   fails the status assertion, which is exactly the split that makes the two
   checks worth having.
3. **Miscounting.** *Failure mode*: one pickup increments twice; a consumed relic
   is re-collectable (hidden but still overlapping); the untouched fourth relic is
   swept up by a "collect everything" implementation; or the readout carries its
   own private tally that only happens to agree. *Defense*: G3 caps the readout by
   the fixture's own contact count on every frame; cp3 walks back over the first
   relic's spot inside the window where a live-but-hidden volume would re-fire;
   the control relic is gauged for presence, position **and** non-contribution at
   every checkpoint (G5); and cp6 requires `3/3` at the exact instant the third
   relic is taken, which a shadow counter drifting by one cannot satisfy.
4. **One-shot latch / non-persistent state.** *Failure mode*: the lamp flashes on
   and reverts; the exit re-seals; the victory state clears when the character
   leaves the exit volume. *Defense*: G4 forbids either observable from reverting
   at any frame once seen, and the run's last leg walks out of the exit and back
   in — the second firing must produce the same measured outcome (cp8), which is
   what catches the most common wrong implementation in this corpus.
5. **Test disabling / environment repointing.** *Failure mode*: the agent edits
   the fixture, the map, the camera plan or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git HEAD
   so an on-disk edit never reaches the grade (committed changes are
   review-gated on commit), and `Content/Maps/` is deny-listed. `Config/` is
   **not** deny-listed on this substrate: `Config/DefaultEngine.ini` and
   `Config/DefaultInput.ini` are `config_writable`, so they are path-accepted and
   then semantically diffed against the spec's `config_allow` list
   (`tools/verify-single/config_lane.py`). **This spec declares no `config_allow`**,
   so any ini diff at all is uncovered and rides the exit-4 path — the reject is
   real, but it comes from an empty allowlist, not from a deny prefix. Never add a
   `config_allow` entry to this spec without re-reading this note.

## Hidden invariants

- **Every number the grade compares the submission against is disclosed** — four
  relics, three required, the `k/3` format, the three status words, brightness 0 and
  5000, the 120 cm relic contact volume, the 500 cm minimum relic separation, and
  the 25 cm the untouched relic may drift. Two numbers are verifier-side and
  deliberately **not** disclosed, because both are *leniency* — each can only ever
  make a correct submission pass more easily, never fail:
  `K_FIXTURE_CONTACT = 300 cm` and `K_FIXTURE_MARGIN = 150 cm`, the one-sided
  margins that make the fixture's own count and entry flag fire before the engine's
  overlap edges (see the margin note in the verifier section). A submission cannot
  read them and cannot be surprised by them in the failing direction.
  What is otherwise hidden is only *when* and *where*: the nine checkpoint instants,
  the eight-leg route and its waypoints, and the fact that the control is the relic
  at (1900, -1000).
  No relic carries a tag, flag or name distinguishing the required three from the
  spare, so a submission cannot special-case the control — it can only implement
  the behaviour generically and let the route decide.
- **The guards are per-frame, not per-checkpoint.** G1-G5 evaluate on every tick,
  so a timed lamp or a timed victory has no gap between samples to thread. This is
  the same shape as the continuous pre-contact guard in
  `TeleportPortalFunctionalTest`, and it is why the undisclosed checkpoint instants
  are a second line of defense rather than the first.
- **cp3 sits inside the re-fire window.** The step-off distance (300 cm) and the
  return are chosen so a relic that was hidden rather than disarmed generates a
  fresh overlap edge before cp3 grades — distinguishing "consumed" from "invisible
  but still live", which an end-state-only read cannot tell apart.
- **cp6 grades the unlock before the exit is entered.** The drive halts on taking
  the third relic and is released only by cp6, so "opened at N" and "won by
  entering" are measured as two separate events; an implementation that wins the
  moment the count reaches three (without an entry) fails cp6's `status != ESCAPED`
  assertion even though its exit state is correct.
