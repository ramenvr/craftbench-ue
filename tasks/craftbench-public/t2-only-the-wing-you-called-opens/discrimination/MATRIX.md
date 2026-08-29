# Discrimination matrix — t2-only-the-wing-you-called-opens

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs; the
per-checkpoint named gates carry the discrimination.

> **EVERY NUMBER AND EVERY VERDICT BELOW IS PREDICTED, NOT MEASURED.** Nothing in
> this task has been built or run: the five `.umap` binaries are authored by
> `../authoring/author_map.py`, which has not been executed, the fixture and the
> reference have never been compiled, and no PIE leg has ever started. The times
> are arithmetic off the layout table and the character's 500 uu/s pace; the
> verdicts are traced by hand through the fixture's gate precedence. The
> orchestrator measures all of it afterwards and rewrites this file with what
> actually happened.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS (PREDICTED) | `Test Completed. Result={Success}` | The board listens to every mark's step volume and, at the moment of the step, reads that mark's live label, joins wing name to section off that wing's own post, brings the named section in and takes out **only the one that was called before it**, then counts what is actually standing — every frame, not once — and prints it. Nothing is cached at `BeginPlay`, no section name is built out of a wing name, and no number is a constant, so the mid-run re-deal, the mirrored 60/20 Hz deals and the different wing sizes all cost it nothing; the hall is never the previously-called wing, so the take-down never reaches it, and `CallWing` returns early when the mark calls the wing already standing, so the cp6 re-step is a no-op. Hand-traced through both legs: cp1 rose (4), cp2 gold (6), cp3 rose (re-trigger, unchanged), cp3r rose (re-lettering is not a call), cp4 gold, cp5 rose, cp6 rose (same-mark re-step, unchanged) on the 60 Hz leg, and the mirror of that on the 20 Hz leg. |
| `empty` | FAIL (PREDICTED) | `CalledWingOpens: mark ` | The unmodified scaffold compiles, so L1 is green. `StepVolume` generates overlap events and **nothing is bound to it**; `Report` works and nobody calls it. cp0 passes cleanly and on purpose — the hall is already standing, the furniture is untouched, and the supplied board already reads `NONE 0` — so the first failure is the MISSION gate at cp1, 1.5 s after the character first stands on ALPHA (PREDICTED t≈9.5 s of world time): 0 of that wing's fittings stand in the host. |

Both rows run **twice**, at `-FPS=60` and `-FPS=20`, in separate PIE processes,
with **mirrored deals**; every leg must pass.

**Why the empty leg's substring stops where it does.** The full message on the
60 Hz leg is `CalledWingOpens: mark ALPHA showed ROSE at the step; 0 of 4 ROSE
fittings stand in the host at cp1` — and on the 20 Hz leg the same gate says
`GOLD` and `0 of 6`, because the two legs deal the marks mirrored and the wings
are different sizes. A substring carrying a wing name **or a count** would match
one leg and read the other as a wrong-reason FAIL — note that `0 of 3`, which an
earlier draft of this file suggested, is now wrong on BOTH legs. The substring
above is leg-independent, and every FAIL message in the fixture begins with its
own gate name, so `<GateName>:` is always a safe row substring here.

## Requirements table

The full prompt-requirement to gate mapping is in `../task.md` under
**Requirement-to-assertion map** — 17 rows, each naming the gate that checks the
requirement and the condition under which that gate does not run.

## Which gate names which wrong answer

Deterministic because `task.md` fixes the gate precedence within a gauge point
(`CalledWingOpens`, `OnlyCalledWingPresent`, `SealedWingUntouched`, then
`OpenWingIsSolidAndSeen`, then `BoardNamesTheOpenWing` last). Written down so no
gate is left with a named failure another gate always steals — a gate whose
message can never be the one printed is a dead gate. **All PREDICTED.**

**Precedence within a frame is not the whole story.** `SealedWingUntouched`
clause (a) is also evaluated on **every frame** once cp0 has been sampled, ahead
of the drive, so it fires roughly a second before the checkpoint that would have
caught the same fault — which moves four rows below off the gauge point a
precedence-only reading would put them at. See
*[When the guard beats the checkpoint](#when-the-guard-beats-the-checkpoint-read-this-before-matching-a-substring)*
after the table.

| Wrong answer | Dies at | Where (PREDICTED) |
| --- | --- | --- |
| nothing at all (the unmodified scaffold) | `CalledWingOpens` | cp1, the first step |
| clear every section the world knows about, then bring in the one this mark names | `SealedWingUntouched` (the every-frame clause — see *when the guard beats the checkpoint* below) | **the frame the hall leaves, between cp0 and cp1** — NOT at cp1. THE owner's named wrong answer. The clear-everything loop evicts the hall, which is a section exactly like the other three, at the instant of the first step; the guard runs before the drive on the very next frame, so the message is `SealedWingUntouched: hall fitting HALL.1 left the host between cp0 and the next gauge point; the hall is open when play begins and stays open all night` |
| the same loop, but the hall is put back inside the settle window | `SealedWingUntouched` (the every-frame clause) | the frame it leaves, between cp0 and cp1 — identical landing site to the row above, and this is the row that justifies the every-frame clause existing: without it the row above would still die at cp1, and this one would not die at all |
| the hall evicted in `BeginPlay`, before the guard is armed | `SealedWingUntouched` (the cp-gauge clause) | **cp0** — the only reachable checkpoint form of the hall-absent message, because the guard is armed the frame after cp0 and beats every later eviction. Message: `SealedWingUntouched: hall fitting HALL.1 absent from the host at cp0 (no mark ever calls the hall and nothing may disturb it)` |
| bring the named wing in and never take the previous one out | `OnlyCalledWingPresent` | cp2, six called fittings where three are allowed, naming both tag sets |
| open everything on the first step | `OnlyCalledWingPresent` | cp1 |
| cache the mark-to-wing pairing at `BeginPlay` | `CalledWingOpens` | cp4 — right at cp1, cp2, cp3 and cp3r, wrong the moment the same plate demands a different wing |
| a pairing hard-coded in the source | `CalledWingOpens` | cp1 of ONE of the two legs, with certainty, because the deals are mirrored and both legs must pass |
| poll the mark's label and swap whenever it changes | `CalledWingOpens` and `OnlyCalledWingPresent` | cp3r — gauged 1.0 s after the re-lettering with the character standing on nothing, expectation unchanged from cp3 |
| a one-shot latch: the first step works and later steps do nothing | `CalledWingOpens` | cp2 (a latch that never swaps) or cp5 (a latch that stops after the re-deal) |
| **write the board once, in the step handler** — the minimal shape, and THE locally-reasonable wrong answer | `BoardNamesTheOpenWing` | **cp1** — at the instant of the step the called wing has not arrived, so an honest count reads zero and the board says `<WING> 0` for the rest of the run. Message: `BoardNamesTheOpenWing: the board should read 'ROSE 4' at cp1 and it reads 'ROSE 0'` |
| **print a constant count** (`Report(W, 3)`, or whatever the first wing held) | `BoardNamesTheOpenWing` | cp1 or cp2 of **both** legs — the wings hold 3 / 4 / 6 / 4 and the deals are mirrored, so no constant survives one full leg |
| **build the section's name out of the wing's name** (`"L_Wing" + WingName`) | `CalledWingOpens` | cp1 — the place a wing's fittings are kept is not named after the wing, so the name resolves nothing and no fitting arrives |
| **open the right wing but only part of it** (three of gold's six) | `CalledWingOpens` then `OnlyCalledWingPresent` | the gauge point it happens — `CalledWingOpens` runs first and names `3 of 6 GOLD fittings` |
| resolve the section from the mark instead of from the wing's own post | `CalledWingOpens` | cp1 — a mark carries no section at all, so nothing arrives |
| two latent actions, the take-down and the bring-in, sharing one handle | `CalledWingOpens` / `OnlyCalledWingPresent` | **cp6 is the only place the worst case can present** — the same-mark re-step issues both calls against the SAME section, so a discarded call leaves the standing wing gone; at every other step the two calls name different sections and the slip can hide. Elsewhere: whichever gauge point the collision bites, naming exactly which tags stand that should not |
| spawn look-alike fittings instead of bringing the wing in, tagged from the agent-writable constructor | `OnlyCalledWingPresent` | cp1 — a tag added in `AWingFittingActor`'s constructor lands on **all seventeen** fittings at once, so the hall's three carry it too and the multiset is wrong immediately |
| spawn look-alike fittings and stamp the three exact per-instance tags at run time | `OpenWingIsSolidAndSeen`, **or nothing** | cp1 if the stand-ins carry no visible pawn-blocking mesh. If a submission reproduces three exactly-tagged, visible, solid actors it is **observably byte-identical to the answer and PASSES** — deliberately not special-cased (`task.md` anti-gaming note 6, adoption review §5.1 rule 3). It is simply far more work than the answer and none of it is derivable from the writable tree |
| bring the wing in but leave its fittings hidden or non-colliding | `OpenWingIsSolidAndSeen` | cp1, naming the fitting and which of the two failed |
| load the section and never make it part of the running world | `CalledWingOpens` (zero tagged actors) or `OpenWingIsSolidAndSeen` (hidden ones) | cp1 — correct either way; which of the two the engine actually does here is one of the unmeasured facts below |
| a correct internal model and no content moved | `CalledWingOpens` | cp1 — nothing private is ever graded |
| open the right wing and report the wrong line | `BoardNamesTheOpenWing` | the first gauge point where they disagree; the gate asserts against the EXPECTED line, so a consistently-wrong reporter still fails |
| re-letter the marks to pin each one to a wing | `SealedWingUntouched` clause (b) | the next gauge point — the fixture grades against what it DEALT, so a rewritten label makes the submission disagree with the grade instead of with itself |
| move a mark, a post or the board to make the join easier | `SealedWingUntouched` clause (b) | the next gauge point, 2 uu — checkpoint-only, because the guard does not read the furniture. Graded, never attributed: an attributed exit a submission can trigger is a free way out of the denominator |
| move a hall fitting | `SealedWingUntouched` clause (a) | **the frame it moves**, 1 uu, via the every-frame guard (`moved N uu from where the level stands it, after <last gauge>`) — at cp0 only if it was moved during `BeginPlay` |
| open slate, which no mark ever calls on a stepped plate | `OnlyCalledWingPresent` | the gauge point it appears — GAMMA carries SLATE in both deals of both legs and is never stepped on |

### When the guard beats the checkpoint (read this before matching a substring)

`SealedWingUntouched` has **two emitters**, and which one speaks decides both the
message text and the world-time it appears at. The gate NAME is the same either
way, so `SealedWingUntouched:` is always a safe row substring — but the tail is
not, and a matrix that quotes the wrong tail turns a correct FAIL into a
wrong-reason FAIL.

1. **The every-frame guard** (`GuardControlsContinuously`) runs at the top of the
   fixture's `Tick`, **before the drive advances**, and is armed the frame after
   cp0 is sampled. It reads clause (a) only — the hall's three fittings, present
   and within 1 uu of the shared layout table. Its message ends
   `left the host between <last gauge> and the next gauge point` (absent) or
   `moved N uu from where the level stands it, after <last gauge>` (moved).
2. **The checkpoint clause** (`GateSealedWingUntouched`) runs at cp0..cp6 and cp3r
   and covers clause (a) *and* clause (b), the host's fixed furniture. Its
   messages end `at <gauge>`.

**Consequence, and it is not obvious:** because the guard is armed from the frame
after cp0 and the first step is roughly five seconds later, **every hall eviction
or hall move that happens after cp0 is caught by the guard, about a second before
the checkpoint that would otherwise have caught it.** So the checkpoint form of
the hall-absent / hall-moved message is reachable **only at cp0** — i.e. only from
a submission that disturbed the hall during `BeginPlay`. Neither message is dead:
clause (a)'s *third* sub-check (a hall fitting standing but hidden or
non-blocking, `is standing at <gauge> but ...`) is **not** covered by the guard and
stays reachable at every gauge point, and the whole of clause (b) is
checkpoint-only.

None of this changes a verdict — the same submissions fail, under the same gate
name. It changes **where the orchestrator should expect to read the line**, which
is the whole job of this file.

## What carries the discrimination without variants

**Two subsystems, and getting either one alone right still fails a named gate.**
Which wing a mark calls is a world state that is re-dealt mid-run; what that
answer does is move content into and out of the running world. Perfect streaming
with the pairing cached fails `CalledWingOpens` at cp4. A perfect pairing with the
exclusivity scoped to *everything* rather than to *the wing called before* fails
`SealedWingUntouched` at cp1.

**The in-scene negative control is a matched twin, not a before/after.** The hall
is built from the same fitting class, stands in the same host, is streamed by the
same mechanism, and is indistinguishable from a callable wing to any
clear-everything loop. It is gauged at every checkpoint including cp0 **and on
every frame after cp0**, and its expected transforms come from the layout table
the authoring script and the fixture share — never from a cp0 reading, because cp0
is already downstream of the submission.

**Every trigger fires at least twice.** ALPHA is stepped on three times (cp1, cp3,
cp4) and BETA three times (cp2, cp5, cp6). ALPHA at cp1 and cp3 is the
identical-outcome re-trigger: same mark, same deal, same demanded result. ALPHA at
cp4 and BETA at cp5 are the same plates demanding *different* wings, because the
re-deal sits between them — which is what a latch dies on. BETA at cp6 is the
same-mark re-step with **no** re-letter in between, so the step calls the wing that
is already standing and the demanded outcome is cp5's unchanged.

**The load-bearing fact is read from the world and varies per run.** The
mark-to-wing pairing is knowable only by reading the mark, is re-dealt mid-run
from the fixture's own table, and is **mirrored between the two framerate legs**,
so a constant is wrong at the first gauge point of one of the two legs that both
have to pass. The deal index comes from the leg's fixed delta time
(`FApp::GetFixedDeltaTime()`), never from wall clock and never from randomness, so
the same input gives the same deal every run.

**Three world reads, chained, and each one has its own named gate** (added
2026-08-19 after adversarial review found one read carrying the whole task):

| Read | Where it lives | What fails without it |
| --- | --- | --- |
| which wing this mark is calling *now* | the mark's live label, re-dealt mid-run, mirrored per leg | `CalledWingOpens` at cp4 (cached) or cp1 of one leg (hard-coded) |
| where that wing's fittings are kept | that wing's own post; the place is **not** named after the wing and the names are printed nowhere | `CalledWingOpens` at cp1 — a concatenated name resolves nothing |
| how many of them are actually standing | counted from the host world; the wings hold 3 / 4 / 6 / 4 and a wing arrives over several frames | `BoardNamesTheOpenWing` — a constant is wrong on both legs, and a count taken in the step handler reads zero |

**Nothing gates on a streaming object.** No gate reads a loaded flag, a visible
flag or a `ULevelStreaming`. Every gate is a statement about actors standing in
the host world and about the rendered text on the board, so an implementation that
got the right tagged, visible, solid fittings into and out of the host by some other
means is correct by the prompt's own words and passes.

**The drive cannot manufacture a FAIL.** Every leg is straight and no walk passes
within 900 uu of a mark it is not aiming at (the authoring script refuses to save a
level where any leg comes within 400 uu). The approach ramps down so the character
arrives slowly instead of braking off the plate. The fixture registers the step at
45 uu from the mark's centre while the engine's own begin-overlap fires at about
152 uu, so the submission is always notified first and never gets less than the
second the prompt promised. Every gauge point is derived from its own event, and
the re-deal fires only after cp3 is sampled and while the character overlaps no
mark.

## What the first real run must confirm — none of it is measured yet

1. **The drive's own clock.** PREDICTED world-time gauge points at cp0 ≈ 1.5 s,
   cp1 ≈ 9.5 s, cp2 ≈ 18 s, cp3 ≈ 26.5 s, cp3r ≈ 35 s, cp4 ≈ 43 s, cp5 ≈ 51.5 s,
   cp6 ≈ 61 s, from 1,200 and 1,400 uu straight legs at a 500 uu/s pace with the
   ramp-down roughly tripling the last 800 uu, and seven 1.5 s settles. The
   sentinel sits at 135 s and the `TimeLimit` at 137 s, so there is about 2.2x
   margin. Both legs, and the wall clock against `l2_pie.py`'s 600 s per-leg budget
   (which the two fps legs do **not** share).
2. **Gate 10: the swap inside the disclosed window, at 20 Hz. STILL THE TIGHTEST
   UNVALIDATED NUMBER IN THE TASK.** The window was widened from 1.0 s to 1.5 s on
   2026-08-19 — at 20 Hz that is 30 world ticks rather than 20 — in the prompt and
   the fixture together, because a full `UWorld::RemoveFromWorld` of the outgoing
   wing **and** a full `UWorld::AddToWorld` of the incoming one must both finish
   inside it, and both are time-sliced by the engine. Gold's six fittings are the
   worst case. If a byte-perfect reference still needs longer, **widen the number
   in the prompt again** and re-measure the walk — never widen the fixture's window
   past a number the agent was given.
2a. **The stall re-check cannot invent a FAIL.** `RecheckStallableGates` no longer
   re-runs the checkpoint form of `OnlyCalledWingPresent` against the previous
   gauge point's expectation (which a stall could strand one step behind reality,
   between the engine's 152 uu begin-overlap and the fixture's 45 uu step-landed).
   It now asks a scope-only question: the hall, plus the complete set of at most
   one called wing, that wing being the last gauged one or the one lettered on a
   mark within 250 uu. If any run reports
   `OnlyCalledWingPresent: the walk to ... stalled`, read it as a real scope
   violation, not as a timing artefact.
3. **cp0 residency.** The saved level marks the hall loaded and visible and the
   other three neither, and `author_map.py` re-reads all four flags from disk. What
   PIE does with a section that was loaded in the *editor* is not proven on this
   box. If a correct submission fails with `OnlyCalledWingPresent: at cp0 the host
   should hold exactly [Fitting.HALL.1, Fitting.HALL.2, Fitting.HALL.3]`, the fault
   is in the map and the fix belongs in the authoring script, never in the fixture.
4. **Loaded-but-not-visible.** Whether a section brought in and never made part of
   the running world yields ZERO tagged actors (expected — `UWorld::Levels` is
   populated by `AddToWorld`) or hidden ones. The design is correct either way
   (`CalledWingOpens` catches zero, `OpenWingIsSolidAndSeen` catches hidden), but
   the answer belongs in `../notes.md` once observed.
4a. **The section names and the wing sizes.** `L_WingVault` (HALL), `L_WingLoft`
   (ROSE), `L_WingKeep` (GOLD), `L_WingSpur` (SLATE), holding 3 / 4 / 6 / 4
   fittings. Confirm from the authoring log that all seventeen per-instance tags
   read back from disk, that `GetStreamingLevel` resolves each basename under the
   PIE prefix, and that no two neighbouring wings' columns intersect (the script
   asserts a 140 uu minimum; the measured worst pair is GOLD.5 / SLATE.4 at 260 uu).
5. **The reference's first compile.** It has never been built. The likely snags are
   all in `reference/.../GateBoardActor.cpp`: the `AddDynamic` delegate signature,
   the `Engine/LevelStreaming.h` and `Kismet/GameplayStatics.h` includes, and the
   `TObjectPtr` dereferences. Also the tick assumption — the board switches
   `PrimaryActorTick.bCanEverTick` on in the class constructor and relies on the
   placed instance carrying no serialized override of its own. If that is ever
   wrong the signature is unmistakable: every wing opens correctly (the swap rides
   an overlap delegate, not `Tick`) and the board never leaves `NONE 0`, i.e.
   `BoardNamesTheOpenWing: the board should read 'ROSE 4' at cp1 and it reads
   'NONE 0'`.
6. **The empirical half of the difficulty bar.** This task has never met a model.
   One cheap model, once: a first-try pass with zero iteration means the bar was
   not met.
