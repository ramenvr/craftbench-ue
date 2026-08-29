# notes — t3-hold-the-marks-in-the-order-given

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Not yet built, not yet run** — the authoring agent
was forbidden from touching UBT, the editor or `cb` (builds are serial on this
box and other agents were live in the same tree), so everything below is
designed, arithmetic-checked and source-checked but not compiled.

**What this pass produced, and what it deliberately did not.**
*(Superseded by the later passes — see the table below it and
`## The 2026-08-19 adversarial review` at the bottom.)*

| Shipped here | Still owed by the build-verifier pass |
|---|---|
| `task.md` (v2 front matter, parses — verified against `spec.py::parse_task_file`) | `Source/CraftBenchTests/Tasks/<id>/MarkOrderFunctionalTest.{h,cpp}` |
| `notes.md` | `Content/Maps/<id>/L_MarkOrder.umap` (+ `authoring/author_map.py`) |
| the agent scaffold — `FloorMarkActor.{h,cpp}` + `DutyBoardActor.{h,cpp}` | `cameras.json` (the camera-plan lane; not part of this release) |
| the reference — `DutyBoardActor.{h,cpp}` only | `discrimination/MATRIX.md` |

**Where it actually stands, 2026-08-19 after the adversarial review.** Everything
in the right-hand column above now exists **except the map**:

| On disk | Still owed |
|---|---|
| `task.md`, `notes.md`, `cameras.json`, `discrimination/MATRIX.md` | **`Content/Maps/<id>/L_MarkOrder.umap`** — still not authored. `authoring/author_map.py` writes it; nothing in this task can be graded until it exists, because `map_locator.py` cannot resolve the fixture map and L2 is an explicit FAIL rather than a behavioural verdict. This is the one blocker in front of every other claim in this folder. The basename `L_MarkOrder` is unique repo-wide, so no `DuplicateMapBasenameError` once it is authored. |
| the scaffold and the reference under `Source/ThirdPerson/Tasks/<id>/` | one L1 build, one `cb discriminate`, one `cb refgate` — none has ever run |
| `Source/CraftBenchTests/Tasks/<id>/MarkOrderFunctionalTest.{h,cpp}` | |
| `authoring/author_map.py` (its pure preflight — staging tables + all 38 drive polylines — **does** run and passes) | |

`tasklint` on this spec was **run** (`py -3.13 tools/verify-single/tasklint.py
tasks/craftbench-public/t3-hold-the-marks-in-the-order-given/task.md`) and returns
exactly **one ERROR and two WARNs**, nothing else:

- `ERROR [map-binary-exists] map L_MarkOrder: no committed L_MarkOrder.umap` — the
  missing map, owed by the build-verifier pass. Note that tasklint does **not**
  error on the missing fixture source, so a green-but-for-the-map lint is not
  evidence the fixture exists.
- `WARN [spec-h2-allowlist] non-canonical H2: 'Composed concepts',
  'Requirement-to-assertion map'` — carried by every sibling in this set.
- `WARN [discrimination-required] ships reference/ but has no
  discrimination/MATRIX.md`.

For comparison, the exemplar `t2-alarm-escalates-and-cools-down` lints at 1 error
+ 8 warnings and `t3-lift-serves-its-calls-in-order` at 1 + 5, so this is the
cleanest lint in the set — because the reference ships only the pair it changed
and therefore carries none of the `reference-in-substrate` warnings.

## Provenance

Two corpus rows, both marked `ALREADY STRONG` in
an internal design note (not shipped) and on neither the §9 kill
list nor the §10 watch list of `ADOPTION-REVIEW-2026-08-16.md`:

- **`t2-hold-the-zone`** (review row 197, 6 checks) — accumulate held time only
  while the player occupies a control zone; pause without resetting on exit;
  resume on re-entry; win at a declared cumulative threshold.
- **`t2-ordered-objective-run`** (review row 200, 5 checks) — activate numbered
  objectives in a declared order; correct activations advance, a wrong one
  resets, a fresh full sequence wins.

Both are *good* rows and both are single-mechanism T2s on their own. The owner's
2026-08-18 verdict is that a single mechanism gives no spread, so this task is
the **product** of the two rather than a concatenation: the sequence decides
which zone meter is allowed to run, and any out-of-sequence contact destroys
every meter. That is the whole design, and it is why the composition is
load-bearing rather than decorative — see *The coupling* below.

Corpus-defect fixes applied on the way in (ADOPTION-REVIEW §5.1, non-negotiable):

| Defect | What was done |
|---|---|
| **Mechanism-named ids** (~85% of the corpus). | The assigned id names the outcome (`hold-the-marks-in-the-order-given`), not `zone`, `objective`, `timer` or `sequence`. It leaks to the agent through the `Content/Tasks/<id>/` path, so it had to. |
| **DEF-3, mission leaks mechanism** (73%). | The agent-visible prose names no class the agent must write, no pattern, no plugin and no engine feature. It names only the supplied starting state (marks, board, the two display calls and the ring predicate), which is the precedented `supplied-property reads` carve-out and exactly what the sibling `t2-alarm-escalates-and-cools-down` does. |
| **DEF-4, undisclosed gate literals** (60%). | Every literal any gate enforces is in the prompt: the 150 cm ring, the 500 cm minimum separation, one decimal on each face half, lamp brightness 0 / >= 5000, the 0.5 s settle and the 0.25 s face lag. The *names* of the gates are nowhere in the agent-visible text. |
| **DEF-5, dead gates / denominator inflation.** | `TheHallIsNotYoursToRewire` passes trivially for an empty delivery. That is acceptable **only because the CraftBench verdict is binary** (every gate must pass), so it inflates no denominator. Do not translate this gate list into a scored k/N rubric without re-auditing it. |
| **DEF-6, temporal negative control** (77% of rows). | Converted to an **in-scene** control: a fifth mark that neither list ever names, same class, same 150 cm ring, 500 cm from a listed one, in the same camera frame, gauged at **every** checkpoint and never suppressed. |
| **DEF-1, route policing** (47%). | Nothing grades *how*. A cursor + `TMap`, one state machine per mark, a component, or a real StateTree all pass identically. The only "do not" in the prompt is the observable-spoofing one (do not re-write the hall), and it is enforced because the fixture's own model reads those live values. |
| **§7.1.3 Tier-1 trigger.** | Both corpus rows imply "activate" / "interact". Re-shaped into pure locomotion: every trigger in this task is walking into or out of a 150 cm circle. There is not one key press anywhere, so nothing waits on the blocked input lane. |
| **§7.1.4 re-trigger.** | Two full rounds. Pause/resume, the out-of-turn wipe and completion each fire at least twice, and `TheHallDidItTwice` asserts it. |
| **§7.1.2 visible readout.** | Five faces, five lamps and a tally face — and they are the **only** graded channel. The board carries no other readout, so there is no ungraded switch a submission can call instead of doing the work. |

## Where I diverged from the approved design, and why

All eight are corrections, not preferences. Each is a defect I would rather name
here than have surface as a false FAIL on the build machine.

1. **`TheBankIsStillThereWhenYouComeBack` was unsatisfiable as specified.** The
   design asks for "the face reads the value it held at the instant of stepping
   off, within 0.25 s" over "the first 0.5 s after each re-entry". A **correct**
   implementation accrues up to 0.5 s inside that window, which is 2x the
   tolerance — so the gate would have failed the reference. Changed to a
   **one-sided lower bound**: the face must read at least the preserved value
   less 0.25 s. That is exactly the claim the gate exists to make ("it did not
   empty"); the upper bound is `TheBankPicksUpFromWhereItStopped`'s business and
   that gate is unchanged. The reset-on-exit answer still fails it by the whole
   preserved bank (~2.5 s against a 0.25 s tolerance), so nothing is lost.
2. **Windowed gates now arm at 0.75 s, not 0.5 s.** The design armed
   `AWrongStepEmptiesEveryClock` and `TheRoundStartsOverWhenTheListChanges` at
   exactly the settle time the prompt promises — i.e. judging the contract on its
   own boundary. Both now start at 0.75 s, the same 1.5x widening the
   everywhere-else channels use. Both windows still close well before the
   behaviour they catch could recover.
3. **The float-text parse is off the critical path, without making the readout
   cosmetic.** The design's own risk #1 is that the graded channel is a parsed
   string. Resolved structurally instead of with a lenient parser: the supplied
   `AFloorMarkActor::ShowBank` and `ADutyBoardActor::ShowTally` write the visible
   text **and** mirror the numbers into `LastShown*` in the same breath, so the
   glass and the mirror cannot disagree, and the mirror cannot be written without
   writing the glass. Rule 13 is satisfied by construction (the readout is
   load-bearing; grading it is what makes it so) and no gate depends on
   whitespace. Two consequences: the prompt's "Spacing is yours; the two numbers
   and the slash are not" clause is obsolete and was replaced with "the two
   numbers are yours; the wording around them is the hall's"; and a face never
   written at all is `bFaceEverWritten == false`, an AGENT FAIL named by
   `EveryFaceReadsItsOwnBank`, never a harness exit. This is the same move
   `t2-shop-takes-your-coins-and-remembers` makes with its stall signs.
4. **The out-of-turn step now lands on `list[0]`, both times.** The design's
   `StandingOutOfTurnBanksNothing` is only discriminating if, after the wipe, the
   mark being stood on is the mark whose turn it now is — otherwise every
   implementation passes for free, because a non-current mark banks nothing
   anyway. The drive therefore steps onto the **already-finished first name**,
   which the wipe makes current again. That is precisely where "reset progress,
   then re-evaluate where I am standing" — a two-line implementation that looks
   obviously right — starts banking and must not.
5. **Completion is checked whether or not anybody is standing there.** The design
   says a number dropped below an already-banked value "finishes the mark at
   once", which is not reachable if the completion test is attached to the
   banking step. Written into the spec and into the reference as a separate step
   that runs every frame against the live number. (It is also the single most
   likely place for a plausible implementation to be subtly wrong, which is why
   the fixture drops a number **while** the character stands on the mark: both
   readings agree there, and only the live-read one survives the raise.)
6. **The staging precondition "seconds pairwise >= 1.0 s apart" was relaxed to
   0.5 s.** It is unachievable together with the mid-stand raise and drop the
   same design demands — a raise or a drop lands the moved number next to a
   neighbour. 0.5 s is still 2x the 0.25 s comparison tolerance, which is all the
   separation is for (making "used another mark's number" detectable). Traced for
   the shipped table: the tightest transient pair is 0.5 s, every staged pair is
   >= 1.0 s.
7. **The BeginPlay-snapshot claim was made true rather than asserted.** The
   design says a submission that snapshots the list at `BeginPlay` "is already
   wrong at the baseline checkpoint". That only holds if the committed `.umap`'s
   decoy list has a different **length** from the round-1 staged list, since the
   baseline gate reads the tally denominator. Pinned in the spec: the committed
   map carries a **two-name** list, so the cached answer reads `0/2` against a
   demanded `0/4` and dies at the first gate armed.
8. **One corner is deliberately left undecided and unexercised.** Whether a stand
   poisoned by an out-of-turn step *stays* poisoned across a list replacement is
   not settled by any prompt sentence. Rather than add prose for a case nobody
   would think about (and thereby create a new DEF-4 literal), the drive never
   replaces the list while the character stands on a poisoned mark, no gate can
   distinguish the two answers, and `## Hidden invariants` says so in as many
   words. The three corners that ARE decided — re-stepping the current mark is
   legal, an already-finished listed mark is out of turn, an unlisted mark is
   inert — each have an explicit prompt sentence **and** a gate, per the design's
   own "ambiguity the prompt must keep closed" risk.

Nothing was dropped from the design. All 13 gates survive under their given
names, the two rounds survive, the negative control survives, and the two
subsystems and their coupling are unchanged.

## The coupling, in one paragraph, because it is the whole reason this is a T3

**A** is per-mark occupancy banking: accrue while inside my own ring, keep the
value when they leave, carry on from it when they return, finish against **my
own** number re-read at the moment of use. **B** is the hall-wide ordered
sequence read live off the board: whose turn it is, whether an entered mark is
current / listed-but-not-current / unlisted, the whole-hall wipe on an
out-of-turn step, the tally over the current list length, and the restart when
the list is replaced. **B gates A** — a mark may bank only while it is the
current one, so A-right-and-B-wrong (bank whatever ring you are on, judge the
order later) FAILs `StandingOutOfTurnBanksNothing` and
`AWrongStepEmptiesEveryClock`. **B destroys A** — an out-of-turn step or a list
change empties every preserved bank, so B-right-and-A-wrong (clear the bank on
exit) FAILs `TheBankIsStillThereWhenYouComeBack` even though the ordered run
still completes if you never step off. **A feeds B** — a mark finishing is what
moves the turn and the tally, so a wrong required-seconds read shifts the whole
sequence's timing and is named by `AMarkWaitsForItsOwnNumber`. Each direction has
its own named gate; get one right and the other wrong and you fail by name.

## The named wrong answers (difficulty criterion (b))

**Judge the declared order at COMPLETION instead of at the STEP.** Let every
listed mark bank whenever the character occupies it, and check at the end that
they were completed in the declared order. It compiles, it reads right, and on a
clean run — walk each mark in order, never touch a wrong one — it is
**byte-identical** to a correct implementation. Only a deliberately dirty route
separates them, which is why the out-of-turn phases of the drive exist. It fails
`AWrongStepEmptiesEveryClock` (nothing wipes within 2 s of the out-of-turn step;
the previously finished mark is still lit and the tally still reads 2/4) and
`StandingOutOfTurnBanksNothing` (the wrong mark's face climbs where it must stay
flat at 0.0).

**Three more, added 2026-08-19 after the adversarial review** — see
`## The 2026-08-19 adversarial review` at the bottom. Each of them was, as this
task originally shipped, byte-identical to the reference for the ENTIRE run:

- **Out of turn means already finished** (`Idx < TurnIndex` rather than
  `Idx != TurnIndex`). Caught by `AWrongStepEmptiesEveryClock` on the two new
  skip-ahead phases.
- **The completion test lives inside the banking step.** Caught by
  `AMarkWaitsForItsOwnNumber` on the two new off-mark drops.
- **A list changed when its length changed** (or its first name, or its set of
  names). Caught by `TheRoundStartsOverWhenTheListChanges` on the new
  same-length reorder.

Ten further wrong answers, each with the gate that names it, are in
`## Anti-gaming notes` in `task.md`.

## Design decisions worth writing down

**Why the deciding lives on the board in the reference, and why that is not
graded.** The hall is a committed level under a deny-listed path, so a brand new
actor class would never be instantiated and would never run — the prompt says so
in behaviour terms ("whatever does the deciding has to live on something already
standing in it"). The board is the one placed thing that can see the whole round,
so the reference puts it there. **The grade does not care**: a mark that watches
the character, a component, or the character itself all pass. Reflection here
buys avoiding a cast and nothing more.

**Why the mark ships `IsInsideRing` rather than a trigger volume.** The prompt
discloses the predicate as a flat centre-to-character distance, inclusive at the
edge. A `USphereComponent` overlap disagrees with that at the edges (it is
spherical, it includes height, and capsule-vs-sphere overlap has its own
margins), so shipping one would have manufactured disagreements between the
submission and the fixture that have nothing to do with the mission. Shipping the
predicate itself means the fixture, the reference and any submission that uses it
cannot disagree about which frame an entry happened on. A submission is still
free to roll its own; the 0.35 s crossing suppression is what keeps that from
being a false FAIL. **Design consequence to keep in mind:** this is also why the
ring's painted radius is driven from `RingRadiusUu` in `OnConstruction` — the
circle a person sees and the circle the hall means are the same circle, and
nobody should ever have to guess which is authoritative.

**Why the marks use an un-scaled `USceneComponent` root.** A scaled root
multiplies both a child's relative offset and its own collision extent
(`CalcBounds` uses the full `LocalToWorld`), which is how a 120x120 pad once
became 840x960 in mid-air with every comment still saying 120. Each part of the
mark is sized on its own beneath an anchor at scale 1, so re-sizing the ring
cannot move the lamp or squash the text. The sibling actors in this set divide
the root scale back out of every child offset instead; that works but it is a
trap for the next author.

**Why the required half of the face is the agent's to supply.** It would have
been safer to let `ShowBank` read `RequiredSeconds` itself — the agent could not
then get it wrong. It is deliberately not, because "the value cached when the
stand began" is a named wrong answer, and having the agent supply the required
half makes that bug visible on **every** frame rather than only at the one
instant a completion is judged. The cost is a trivial echo for a correct
implementation; the buy is that `EveryFaceReadsItsOwnBank` grades the live read
everywhere.

**Why the tally denominator is the agent's to supply, for the same reason.** "A
tally denominator compiled as a constant" is one of the design's named wrong
answers, and it only exists as a wrong answer if the agent writes the
denominator. Round 2 carries three names against round 1's four, so a constant
`/4` is wrong from the first frame after the shift change.

**Why the run is adaptive rather than timed.** Every standing phase is *"stay
until MY model says this mark's bank reads X"*, never *"stay for T seconds"*. A
submission's own accrual is not in the loop that decides when the drive moves on,
so a slow or fast implementation cannot shift the schedule the windowed gates are
anchored to — it just fails the gate that names it.

**Why `fps_legs: [60, 20]`.** Every number in this task is an integral of game
time. An accumulator that adds a per-frame constant instead of `DeltaSeconds`
lands on plausible values at one rate and is 3x wrong at the other, and dies at
the first `AMarkWaitsForItsOwnNumber` window on the 20 Hz leg. The cost is a
second PIE process; the design's ~235 s of modelled world time sits far inside
the per-leg 600 s L2 budget (the legs do **not** share it —
`registry.py`'s dt-leg loop makes one `run_l2` call per leg).

## Hazards hit, and what a reader should re-check

1. **Map basename.** `L_MarkOrder` is verified unused across the whole repo
   (`git ls-files | grep -ci L_MarkOrder` = 0), as is
   `MarkOrderFunctionalTest`. **Re-verify at build time**: `map_locator.py` globs
   both `Content/Maps/<map>.umap` and `Content/Maps/*/<map>.umap` and raises
   `DuplicateMapBasenameError` = exit 7 HARNESS-ERROR, never a graded FAIL, and
   `cb lint` cannot catch it (`tasklint._check_map` returns clean once *any*
   tracked copy exists).
2. **Nothing here has been compiled.** Builds are serial on this box and the
   authoring pass was forbidden from running UBT. The two scaffold pairs and the
   reference pair are source-checked against the shipping siblings for every API
   they touch (`UTextRenderComponent::SetWorldSize` / `SetHorizontalAlignment`,
   `ULightComponentBase::Intensity` read back directly, `EHTA_Center`,
   `UE_KINDA_SMALL_NUMBER` — all in use in this substrate today), and all four
   engine content paths they load (`/Engine/BasicShapes/Cylinder`, `.../Cube`,
   `MI_PrototypeGrid_TopDark`, `MI_PrototypeGrid_Gray_02`) are tracked in
   `UE-projects/ThirdPerson/Content/`. **L1 is still the first thing to run.**
3. **The reference ships only the pair it changed.** `FloorMarkActor.{h,cpp}` is
   deliberately absent from `reference/`, which is why this task carries none of
   the six `reference-in-substrate` WARNs the alarm task does. It is also the
   *reference-inside-the-substrate* law working the right way round: nothing in
   `reference/` is byte-identical to the scaffold, so an empty submission cannot
   inherit the answer.
4. **Do not let a harness exit launder a FAIL.** Every adaptive phase ends on a
   condition the **submission's** own output has to reach, so a hall that never
   advances would otherwise overrun a deadline and be written off as a staging
   fault. The spec requires `TheHallIsNotYoursToRewire`,
   `TheUnnamedMarkStaysCold` and `EveryLampBurnsOnlyForAFinishedMark` to be
   re-checked **unconditionally** before any overrun is attributed to staging.
   This is the exemplar's law and it matters more here than there.
5. **`fixture-fail-unique`.** `tasklint` warns when two gates in one fixture share
   a >= 6-character FAIL literal, because the discrimination matrix then cannot
   tell which fired. With 13 gates, several of which say similar things about
   faces and lamps, the fixture author has to pick 13 distinct message stems —
   the gate names themselves are the obvious choice, and the empty leg matches on
   `TheBoardShowsHowFarYouGot`.
6. **Playability.** World Settings must name **no** game mode, so the level
   inherits `BP_ThirdPersonGameMode` and its `BP_ThirdPersonPlayerController`
   (which carries `IMC_Default`). Naming a task game mode silently drops both
   halves of Enhanced Input and the map grades byte-identically while being
   completely uncontrollable — five of six ThirdPerson maps once shipped that
   way. Nothing in this task needs a game mode, and no native pawn subclass is
   introduced, so there is no reason to name one.
7. **Sandbox.** The deliverable root `Source/ThirdPerson/` appears in **both**
   agent-visible H2s (verified through
   `tools/run-agent/prompt_extract.py::extract_agent_visible_prompt` — three
   occurrences in the extracted text). A reference landing under
   `Source/CraftBenchTemplate/` would be exit 4 SANDBOX-REJECT, not a graded
   FAIL.
8. **Calibrate the 0.25 s face tolerance against the reference at Gate 10 before
   ship.** One-decimal rounding alone is +/-0.05 s, leaving a 0.20 s working
   margin against a 1/20 s worst-case frame. It should be comfortable; it has not
   been measured.

## The staged numbers (proposed; the fixture owns the table)

The fixture writes these in `PrepareTest`, which runs **after** every `BeginPlay`.
The committed `.umap` must carry a **different** set and a **two-name** list, so a
`BeginPlay` snapshot is wrong at the baseline checkpoint.

**These were re-derived from scratch in the closing pass, because the first version
of this table contradicted the drive.** The earlier table put the mid-stand raise on
`Ash` and the mid-stand drop on `Dune`, while `## The drive` in `task.md` lands the
raise on `list[0]` (phase 4) and the drop on `list[1]` (phase 6) — so the fixture
author would have staged a raise on a mark the drive never stands on at that phase,
and **both `AMarkWaitsForItsOwnNumber` live-read windows would have been empty**.
The list order below is chosen so that `list[0]` **is** the raised mark and
`list[1]` **is** the dropped mark, which is what the drive table already says. The
other claim that did not survive checking was "every staged set is >= 1.0 s apart":
the old round-1 set had `Cedar 3.5` sitting next to `Ash 4.0`. Every number below is
re-checked.

### Round 1 — list `[Dune, Birch, Cedar, Ash]` (four names)

| Mark | round 1 | mid-stand change (round 1) |
|---|---|---|
| **Dune** = `list[0]` | 2.5 | **RAISED to 4.2** at phase 4, when the model reads ~1.8 — after the 0.5 s re-entry window, and before the old 2.5 would have completed. The stand has to get longer. |
| **Birch** = `list[1]` | 5.0 | **DROPPED to 2.0** at phase 6, when the model reads ~3.6 — below what is already banked, so the mark must finish **at once, with nobody moving**. |
| **Cedar** = `list[2]` | 6.5 | — |
| **Ash** = `list[3]` | 3.5 | — |
| **Elm (control)** | 8.0 | — never on either list, never changed, first frame to last |

Pairwise separation: the base set `2.5 / 3.5 / 5.0 / 6.5 / 8.0` has a minimum gap of
**1.0 s**; after the raise (`4.2 / 3.5 / 5.0 / 6.5 / 8.0`) **0.7 s**; after the drop
(`2.0 / 3.5 / 4.2 / 6.5 / 8.0`) **0.7 s**. Every one is at least 2x the 0.25 s
comparison tolerance, which is the only thing the separation is for — making "used
another mark's number" detectable.

The order matches **no** orderable property of the hall, checked against all of
them: alphabetical `[Ash, Birch, Cedar, Dune]` and its reverse; ascending and
descending X (`[Ash, Birch, Dune, Cedar]`); ascending and descending distance from
the parking spot (also `[Ash, Birch, Dune, Cedar]`); ascending and descending
required seconds (`[Dune, Ash, Birch, Cedar]`). It differs from the nearest of these
at position 2.

**Round 1 reaches the first already-finished wipe with only two of four finished.**
Drive step 8 ends on `list[1]`, and step 9 steps onto `list[0]` out of turn — so at
the instant of the wrong step the tally reads **2/4** with two lamps burning, which
is exactly the state anti-gaming note 1 quotes.

**And Cedar is no longer finished by standing on it.** Drive step 13 banks
`list[2]` to **3.0** and stops there; step 14 walks the character all the way out
to the parking spot; the fixture then **DROPS Cedar to 1.2** with nobody in any
ring, so it must finish at once — lamp lit, tally 3/4, face at `1.2/1.2`. The
set after that drop is `1.2 / 2.0 / 3.5 / 4.2 / 8.0`, minimum gap **0.8 s**, and
1.2 clears the 1.0 s floor a mark needs to be measurably standable. Step 15 then
walks in from the parking spot to `list[3]` and finishes the round.

### Round 2 — list `[Cedar, Dune, Ash]` (three names)

Staged at the shift change (drive step 20), **while the character is standing on
Dune**.

| Mark | round 2 | note |
|---|---|---|
| **Cedar** = `new-list[0]` | 1.2 -> **3.0** | **RAISED to 5.2** mid-stand at drive step 25, when the model reads ~2.4 |
| **Dune** = `new-list[1]` | 4.2 -> **6.0** | **the mark being stood on** at the instant of the change: it must stop banking and read `0.0/6.0` where they stand, and **no wipe may fire, because no step happened** |
| **Ash** = `new-list[2]` | 3.5 -> **4.5** | |
| **Birch** | 2.0 -> **7.0** | **DEMOTED to unlisted** — round 1's `list[1]`, now as inert as the control |
| **Elm (control)** | 8.0 | unchanged |

Pairwise: `3.0 / 4.5 / 6.0 / 7.0 / 8.0` — minimum gap **1.0 s**; after the Cedar
raise, `5.2 / 4.5 / 6.0 / 7.0 / 8.0` — **0.7 s**; after the round-2 off-mark drop
puts **Dune at 1.5**, `5.2 / 4.5 / 1.5 / 7.0 / 8.0` — **0.7 s**. The denominator
moves `/4` -> `/3`, all four non-control numbers are re-written, and one round-1
name leaves the list entirely.

**Dune finishes with nobody standing on it too.** Drive step 32 banks
`new-list[1]` to **2.5** and stops; step 33 walks out to the parking spot; the
fixture drops Dune to **1.5**, which must finish it at once. That is the second
of the two off-mark completions the run-level gate demands.

### Round 3 — the same-length reorder, list `[Cedar, Ash, Dune]`

Staged while the character is **parked**, after the board has been seen reading
`3/3`. Three names again, **the same three names**, **the same first name**, and
**not one number moves** — the table is `4.5 / 7.0 / 5.2 / 1.5 / 8.0`, which is
exactly what the hall is already carrying after round 2's raise and its off-mark
drop. `StageRound` refuses to write it if that is ever untrue, and
`author_map.py` refuses to save a hall whose tables would make it drift.

Two reasons the numbers are frozen here, and both matter:

1. **Isolation.** If a number moved, a submission that failed to notice the
   reorder would fail `TheRoundStartsOverWhenTheListChanges` on the *required
   echo* rather than on the order — the gate would fire, but it would be
   measuring the wrong thing, and the discrimination claim in `MATRIX.md` would
   be false.
2. **The undecided corner.** Three marks are FINISHED at that instant, and
   whether a finished mark comes undone when its own number moves under it is
   settled by no prompt sentence (`## Hidden invariants`). Moving a number here
   would silently turn that corner into an undisclosed literal — corpus defect
   DEF-4, and the exact thing the closing pass wrote the invariant down to
   prevent.

**A staged set must be applied in ONE frame**, never one number per frame. The
separation guarantee is stated per staged *set*; writing four numbers across four
frames manufactures transient sets nobody checked, and a gate can be judged on any
of them.

### The decoy the committed `.umap` carries

- list: **`[Elm, Ash]`** — two names, so a `BeginPlay`-cached list reads `0/2`
  against the demanded `0/4` and dies at the first gate armed. It deliberately names
  **the control mark**, so the same cached answer also treats `Elm` as listed and
  fails `TheUnnamedMarkStaysCold` on the same checkpoint. The cached-list
  discrimination therefore does not rest on one string any more than the empty one
  does.
- seconds: `Ash 9.5 / Birch 8.0 / Cedar 11.0 / Dune 5.0 / Elm 3.5` — every one at
  least 0.5 s away from **every** value the fixture ever stages for that mark
  (both rounds and all five rewrites, checked per mark by `author_map.py`), and
  pairwise 1.5 s apart, so a fixture that validates separation on its first read
  of the level does not trip on the decoy. Cedar is 11.0 and not the tidy 6.5
  that would continue the ladder, because 6.5 is EXACTLY Cedar's round-1 staged
  value and the tidy number would have handed a `BeginPlay`-caching submission
  the right answer for that one mark.

### Time

**Superseded 2026-08-19, and this time MEASURED off the committed layout rather
than estimated.** `authoring/author_map.py`'s own drive table now sums the 38
polylines: **79,200 uu of walking = 158 s** at the template's 500 uu/s, plus ~98 s
of standing and dwell, plus ~10% for the acceleration ramps — **≈ 285 s**. The
old paragraph read "~25 transits ... so ~100 s of walking", which was low by more
than half even before the five new phases: the drive already made 33 legs, and
the mark-to-mark transits are 2,400-4,300 uu, not 1,200. Re-run the little sum in
`author_map.py` (it prints per step) rather than re-estimating.

285 s still sits far inside the **400 s** sentinel and the **600 s** per-leg L2
wall clock (the legs do not share it — `registry.py`'s dt-leg loop makes one
`run_l2` call per leg), and the calibration checkpoints were extended 50 -> 58 so
the calib log covers the whole drive (348 s). **The 600 s per-leg budget is the
number to watch on the first real run**: 285 s of world time is not 285 s of wall
clock, and the 20 Hz leg is the one that will find out.

### Layout (proposed; the authoring script and the fixture must each solve it)

`Ash (-1600, -900)`, `Birch (-400, -900)`, `Cedar (800, -900)`,
`Dune (200, 900)`, `Elm (700, 900)`; parking spot near `(-2600, 0)`; the board on
the wall at the open end. The minimum pairwise centre distance is **exactly 500 cm**
(`Dune`-`Elm`) — the control mark sits right beside a listed one on purpose, so
"walking across the control changes nothing" is asserted where it is hardest rather
than where it is easiest. Every other pair is >= 1,200 cm. Against a 150 cm ring the
character is never inside two rings at once, which is the claim the prompt makes.

The fixture and the authoring script should each solve the route from the marks'
**live** transforms, and each refuse its job if the separation, the ring radius, the
120 cm non-target clearance or the 300 cm parking clearance does not come out — a
re-authored hall must either move the drive with it or fail loudly.

## What changed in the closing pass, and why

Everything above was written in the first pass; these are the corrections made on
the second read. Each would otherwise have surfaced as a false FAIL, a gate that
grades nothing, or a doc that lies.

| Fix | Why |
|---|---|
| **The staged-numbers table was rebuilt** (above). | It contradicted the drive: the raise and the drop were staged on marks the drive does not stand on at those phases, so **two `AMarkWaitsForItsOwnNumber` windows would have been empty** and the "no cached required-value survives" claim would have gone untested. This is the one substantive defect found in the closing pass. |
| `capability_bucket: Gameplay Programming` -> **`Architecture & Systems`**. | `AUTHORING_TEMPLATE.md` files a task under **its Primary concept's** bucket, and `state-tree`'s bucket in `tools/coverage/concepts.csv` is `Architecture & Systems`. Two siblings in this set already carry that value, so nothing downstream is surprised. |
| Composed concept `ui-and-huds` -> **`ps-hud`**. | `ui-and-huds` is `in_scope=no` / `weight_tier=n/a` in `concepts.csv` (it is a documentation hub). `ps-hud` is the in-scope row carrying **the same `doc_url`**, so the citation is now a real, in-scope id. |
| The `cameras.json` bullet moved out of `Content/` and is marked **not committed yet**. | the camera-plan convention put it at `cameras.json`. The old line named a path under `Content/Maps/` that will never exist — and it sat in an **agent-visible** H2, so the agent would have gone looking for it. |
| Reference LOC **measured** (243 added, 108 of them comment or blank) instead of estimated (~150). | A diff against the shipped scaffold, per the template's "be honest" instruction on this field. Under-counting biases the benchmark. |
| A **second** deliberately-unexercised corner written into `## Hidden invariants`. | Whether a mark that has already finished becomes unfinished when **its own number is later raised above its bank** is settled by no prompt sentence. The staging never does it (numbers move only on an unfinished mid-stand mark, and the shift change wipes in the same instant it re-writes them), so it has to be recorded as undecided — otherwise a later drive phase silently turns it into an undisclosed literal (DEF-4). |
| `PoisonedMark = nullptr` -> `PoisonedMark.Reset()` in the reference. | `TWeakObjectPtr`'s nullptr assignment resolves only through the `TYPE_OF_NULLPTR` converting constructor plus the defaulted copy-assign — both template `operator=` overloads fail deduction on `nullptr_t`. It does compile in UE 5.8 (checked in `WeakObjectPtrTemplates.h`), but `Reset()` does not depend on that. |
| `SetTextRenderColor` added to all four text faces, identically in the scaffold and the reference. | Rule 13 wants a readout a **person** can read. The mark faces and the tally now read distinctly in a `--capture` frame. Same API a shipping sibling (`t2-race-clock`) already uses, so it is not a new dependency. |
| The ring-scale comment in `FloorMarkActor.cpp` was garbled (`0.03 x <radius> / 50`). | It described arithmetic the code below it does not do, which is exactly how the next author ends up "fixing" a correct line. |

## The 2026-08-19 adversarial review

Two reviewers attacked the task after the fixture, the reference and the
authoring script were on disk. Seven findings; **six were real and are fixed
below, one was already true and needed only recording**. The reference source was
NOT changed by any of it — every newly-gated branch was already satisfied by it.
What changed is the fixture's drive, its arming lifetime, and its run-level gate.

### Blocker 1 (REAL, fatal) — the reference could never PASS

`OutOfTurnMark` was set at the out-of-turn entry and **never cleared** — not at
the step off, not on a wipe, not on a list change. Gates 2 and 3 guard only on
`OutOfTurnMark != INDEX_NONE`, a 0.75 s / 2.0 s age, and `OccupiedLast ==
OutOfTurnMark`; none of them consults `PoisonedMark`, which is the piece of state
that actually says the poisoned stand is still in progress and which `StepModel`
clears correctly.

So both gates stayed permanently armed on the last mark anybody ever stepped onto
out of turn, and the drive walks back onto exactly those marks. After the first
out-of-turn step onto Dune, the character re-enters Dune **legitimately** (the
wipe made it list[0] with `Turn == 0`) and banks it to completion — and a correct
submission's face climbing past 0.25 s within a quarter second trips
`StandingOutOfTurnBanksNothing`. Four separate legitimate stands were fatal; the
first killed the run ~60 s in as a **graded FAIL on a right answer**, which means
`cb refgate` and `cb discriminate` could never have gone green.

**Fix.** `OutOfTurnMark` / `OutOfTurnAt` / `bOutOfTurnAhead` are now cleared in
the same block that clears `PoisonedMark` — the one place that already knows the
stand ended — and in `PrepareTest`, so the invariant "`OutOfTurnMark` is set
exactly when `PoisonedMark` is" holds from the first frame. Both gates also carry
an explicit "`PoisonedMark != OutOfTurnMark` stands the gate down" guard,
redundant by construction and written down because it was not redundant once.

### Major 2 (REAL, same root cause, opposite symptom) — a permissive gate

`AnyWindowArmed` used the same three stale conditions, so it returned true for
the whole of every later legitimate stand on that mark. That switched off the
`!bWindow` block in `Tick`, which is the only caller of `GateEveryFace` and of
the non-baseline `GateBoardTally` — leaving the per-mark faces and the tally
**ungraded** across ~13 s of standing, precisely where a mis-scoped wipe or a
stale denominator shows up.

The reviewer's warning is the important part and is now a comment in the source:
fixing the blocker with a per-gate guard **alone** would have closed the false
FAIL and left this hole open. Clearing the state at the step off closes both.
Suppression must be exactly as wide as the sharper gate that replaces it, never
wider.

### Major 3 (REAL) — half the out-of-turn rule was never driven

Every out-of-turn step in the 30-step drive landed on a mark that was **both
already finished AND at list index 0**: old step 7 (Dune, round-1 `Turn=2`), old
step 14 (Dune, `Turn=4`), old step 24 (Cedar, round-2 `Turn=1`). Every legitimate
entry was onto the mark at `index == Turn`, or onto an unlisted mark. So
`if (Idx != INDEX_NONE && Idx < TurnIndex)` — "out of turn means I have already
finished this one" — produced **byte-identical faces, lamps and tally for all
~235 s of both fps legs and passed all thirteen gates**, while failing the
prompt's "one that comes later in the list" in as many words.

That is not a strawman. It is the reading that comes to mind first, because
stepping *ahead* onto a mark nobody has touched does not feel like breaking an
order at all.

**Fix.** Two SKIP-AHEAD phases, one per round, each onto a mark that is later in
the list, unfinished, and has never been the current mark:

- drive step 3 — `list[0]` (Dune) is banked to 1.0 of 2.5, `Turn == 0`; the
  character walks onto `list[2]` (Cedar, index 2). Step 4 walks back and re-banks
  Dune, because the wipe took that bank with it.
- drive step 22 — `new-list[0]` (Cedar) is banked to 1.35 of 3.0, `Turn == 0`;
  the character walks onto `new-list[1]` (Dune, index 1). Step 23 re-banks Cedar.

Against the `Idx < TurnIndex` answer, neither step wipes, so
`AWrongStepEmptiesEveryClock` finds the part-banked current mark still standing
0.75 s later and names it. The two halves are now **counted separately**
(`SkipAheadJudged` / `FinishedStepJudged`) and the run-level gate demands two
judged windows of each; a short count is a HARNESS-PRECONDITION naming the
branch, never a model failure.

Skip-ahead targets were chosen for cost: Cedar and Dune are one lane-hop away
(2,400 uu each way) where Ash would have been 3,600. The stand is 4.0 s rather
than 6.5 — gate 2 needs 0.75-2.0 s and gate 3 needs 2.0 s onward, so 4.0 leaves
gate 3 two full seconds, forty frames at 20 Hz.

### Major 4 (REAL) — no completion ever had to fire outside the banking branch

`MaybeFireStagedRewrite` gated every mid-run rewrite on the character standing on
the rewritten mark, and `StageRound(2)` wipes every bank in the same frame it
re-writes the numbers. So **no finished-or-banking mark ever saw its number move
with nobody on it**, and the reference's section-4 completion loop could have
been moved *inside* the section-3 banking `if` with byte-identical output for the
whole drive — including `AMarkWaitsForItsOwnNumber`'s deferred check.

`task.md` sold that placement as ~1.5 h of the reference's judgment ("the check
cannot be attached to the banking step, because a number dropped below an
already-banked value must finish a mark with nobody moving") and the fixture's
own section-4 comment repeated it. Neither was true of what was staged. That is
an overclaim, and the honest fix is to stage it, not to soften the sentence.

**Fix.** A new rewrite mode, `bRewriteWhileAway`, and two phases that use it:

- drive step 13 banks `list[2]` (Cedar) to **3.0** of 6.5 and stops; step 14
  walks the character 4,300 uu out to the parking spot; once nobody is in any
  ring, the walk has arrived, and gate 7 has taken its "the bank did not move"
  sample, the fixture drops **Cedar to 1.2**. It must finish at once.
- drive steps 32/33 do the same on `new-list[1]` (Dune): banked to **2.5** of
  6.0, dropped to **1.5** from the parking spot.

Three details that are load-bearing rather than decorative:

1. **Gate 7 has to stand down, and only for the right reason.** The face
   legitimately moves to the mark's new number on that frame, which would have
   read as drift. The window is closed in the model's own completion block, on
   the condition `Mi == AwayMark` — "a bank that has just been FINISHED is no
   longer a PAUSED bank" — not by widening the drift tolerance.
2. **The drop waits for `bAwaySampled`** (with a `LastRingExitAt + 1.75 s`
   fallback so a missing sample cannot stall the step into a harness exit), so
   the completion is provably the only thing that could have moved that face.
3. **A drop that is not clear of the standing bank by 0.5 s is a staging fault**,
   attributed via `AttributeOverrun`, because "it finishes at once" must rest on
   the rule and not on the comparison tolerance.

Both resulting sets keep the 0.5 s pairwise separation and the 1.0 s floor:
round 1 becomes `1.2 / 2.0 / 3.5 / 4.2 / 8.0` (min 0.8) and round 2 becomes
`1.5 / 4.5 / 5.2 / 7.0 / 8.0` (min 0.7). Both are validated in `PrepareTest`
before anything is written, and mirrored in `author_map.py`.

Net cost is small, because these phases *replace* a full stand: Cedar used to be
banked to 6.5 and is now banked to 3.0.

### Minor 5 (REAL) — the list-change trigger fired substantively once

`RunLevelGate` demanded only `ListChangeJudged >= 1` where every other trigger is
demanded twice, and the two staged lists differ in **both** order and length
(4 names to 3). So a change detector that compares only `Num()` fires on exactly
the same two frames as a correct one — initial acquisition 2 to 4, shift change
4 to 3 — and the run is byte-identical. Same for a detector that watches only
`list[0]`, and same for one that compares the *set* of names.

**Fix.** A third staged list, `[Cedar, Ash, Dune]`, replacing round 2's
`[Cedar, Dune, Ash]` while the character is **parked**, after the board has been
seen reading `3/3` (drive step 36). Same length, same names, **same first name**,
and **no number moves at all**. Only an order-sensitive comparison sees it. The
run-level gate now demands `ListChangeJudged >= 2`.

The staging refuses to run unless that third list differs from the second in
order only — length, first name, name set and every mark's seconds are each
checked, in `PrepareTest` **and** in `author_map.py`. A reorder that quietly
changed any of them would be re-testing what the shift change already tested.

Why no number may move there: three marks are FINISHED at that instant, and
whether a finished mark comes undone when its own number moves under it is
settled by no prompt sentence (`## Hidden invariants` records it as deliberately
undecided). `StageRound(3)` compares its table against what the hall is carrying
and attributes a mismatch to staging rather than writing it.

### Minor 6 (REAL as an observation, no code change) — the prompt discloses the shape

The reviewer's point is that each of the ten anti-gaming failure modes is negated
verbatim by a sentence of the agent-visible prompt, so the spread measured is
transcription care rather than design judgment — and that the two places where
real judgment *would* be required are exactly the two branches findings 3 and 4
show were ungated.

This is **not** a rule violation and the fix is not to remove disclosure: hard
rule 7 requires every gated value to be in the prompt, and an undisclosed literal
that gates the score is a false FAIL (corpus defect DEF-4). The fix is the one
the reviewer names — close the two ungated branches, which is findings 3 and 4
above. The prompt gained three clauses, all of them **values** rather than
algorithm, because the new gates turn on them:

- "…finishes the mark at once — **even with nobody standing on it, and nobody
  standing anywhere**"
- "…one that comes later in the list, **including one nobody has stood on yet**,
  or one already finished…"
- "**The same names in a different order is a different list**, and so is a list
  of the same length."

### Blocker 7 (REAL, and still open) — there is no map

`task.md` claims `Content/Maps/<id>/L_MarkOrder.umap` is committed and the front
matter declares the fixture against it. **It does not exist** — there is no
`t3-hold-the-marks-in-the-order-given/` directory under
`UE-projects/ThirdPerson/Content/Maps/` and a repo-wide search for `L_MarkOrder*`
returns nothing. Only `authoring/author_map.py` exists.

This was already recorded in `MATRIX.md` §Status item 1, and it is still the
state the task ships in. **This pass could not fix it**: authoring the map
requires a headless editor boot, and the pass was forbidden from running the
editor, UBT or `cb`. It is the first thing the build pass must do, and until it
is done every other claim in this folder is unmeasured — L2 is an explicit FAIL,
not a behavioural verdict, so reference, empty and model legs all return a
non-verdict rather than a grade.

What *did* run: `author_map.py`'s pure preflight, driven with a stub `unreal`
module. All staged sets validate (tightest gap 0.70 s), the decoy validates, and
**all 12 route primitives and all 38 drive polylines clear every ring they are
not meant to cross by 120 uu**. That is the layout half of the map proved without
an editor; the save itself is not.

### What the build pass must check first

Every number below is designed, not measured.

1. **The map** (above). Nothing else can be checked until it exists.
2. **L1.** The fixture gained ~200 lines and several new members; it has never
   been compiled.
3. **The three new branch counters** in the calib line: `ahead`, `behind` and
   `alone` must each reach 2, and `l` must reach 2. A short count is exit 7, so a
   broken new phase presents as a harness fault rather than as a FAIL — which is
   correct, and also means it will not look like a task failure.
4. **The off-mark drops specifically.** The drop fires from
   `MaybeFireStagedRewrite`, which runs *after* `StepModel` in the same `Tick`,
   so the model sees the completion on the NEXT frame and records
   `bNobodyStanding` from `Occ` at that moment. If the character has drifted back
   inside a ring by then the completion is recorded as an ordinary one and
   `alone` never reaches 2. The drive parks 300+ uu clear, so it should not — but
   this is the single most fragile new thing here.
5. **Wall clock.** ≈ 285 s of modelled world time per leg, two legs, against a
   600 s per-leg L2 budget. The 20 Hz leg is the one that will find out.
