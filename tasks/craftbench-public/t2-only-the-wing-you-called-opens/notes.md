# notes — t2-only-the-wing-you-called-opens

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Not yet built, not yet run** — the authoring agent was
forbidden from touching UBT, the editor or `cb` (builds are serial on this box and other
agents were live in the same tree), so everything below is designed, engine-source-
checked and lint-checked but not compiled.

Four artefacts are owned here: `task.md`, this file, the agent scaffold at
`UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t2-only-the-wing-you-called-opens/`
(four actor pairs), and the reference at `reference/Source/ThirdPerson/Tasks/<id>/`.

**THIRD PASS, 2026-08-19 — the adversarial-review fixes. Read *Adversarial review*
below before anything else in this file: the wings are no longer all the same size,
the wing sections are no longer named after their wings, the settle window is 1.5 s
rather than 1.0 s, and the drive has a seventh gauge point (cp6). Anything earlier in
this file that says otherwise is the record of an earlier pass, not the current
design.**

**Second pass, same day.** The verifier-owned fixture
(`Source/CraftBenchTests/Tasks/t2-only-the-wing-you-called-opens/WingHostFunctionalTest.{h,cpp}`)
landed AFTER this spec was first written, so the four artefacts were re-read against it
and `task.md` was reconciled to the judge on four points — see *Reconciled against the
landed fixture* below. **The five `.umap` binaries, `authoring/author_map.py`,
`cameras.json` (the camera-plan lane; not part of this release), `discrimination/MATRIX.md` and the `docs/MAPS.md` bookkeeping are still
NOT written** — see *What the orchestrator still owes* at the bottom.

## Provenance

Corpus row: **`t1-stream-sublevel-actors`** (review row 161).

- `hardened-tasks.csv` — mission, provided setup, a 4-check rubric
  (`NamedSectionLoaded` / `NamedSectionVisible` / `ExactlyThreeExpectedActorsPresent` /
  `UnrelatedSectionsUnchanged`), verdict `PASS = 4/4`.
- `check-contracts.csv` — the same four checks, one row each, all
  `Runtime binding: UNBOUND`, `Manifest status: NOT CREATED`.
- `verification-contracts.csv` — **no row at all.** The highest-value file in the corpus
  has nothing for this id, so the discrimination triple (named assertions, empty-
  submission failure, gamed variants) had to be **authored, not carried over**. That is
  the single biggest difference between this task and the corpus row it descends from.

**Adoption review disposition: DEFER, not kill.** §9 K4's closing note lists
`t1-stream-sublevel-actors` among the ~24 deferrals — *"level streaming and SaveGame are
LOCALIZED-unbuilt and cheap; persistence has zero coverage anywhere in the tree"*. So
this is a deferral being cashed, not a killed row being resurrected (§9's standing ban).

**How the four corpus checks survive.**

| Corpus check | Where it went | Why |
|---|---|---|
| `NamedSectionLoaded` | folded into `CalledWingOpens` | DEF-1: "does the SECTION report loaded" grades the ROUTE. Rewritten as the world-content observable — *are all of that wing's fittings standing in the host* |
| `NamedSectionVisible` | folded into `CalledWingOpens` + `OpenWingIsSolidAndSeen` | same DEF-1 rewrite; "visible" is read off the fitting, never off a streaming flag |
| `ExactlyThreeExpectedActorsPresent` | `CalledWingOpens` + `OnlyCalledWingPresent` | kept almost verbatim; "all and only" is the exact-multiset half |
| `UnrelatedSectionsUnchanged` | `SealedWingUntouched` | upgraded from "other streaming-section STATES do not change" (route again) to an in-scene matched twin gauged at every checkpoint — DEF-6, and §5.1 item 5 |

Pre-flight rewrites applied (§5.1, non-negotiable): outcome-named id (assigned:
`t2-only-the-wing-you-called-opens`, not `t1-stream-sublevel-actors`); behaviour-only
mission and workspace state, with the supplied-property carve-out used for `MarkId` /
`WingName` / `SectionId` / `WingLabel`; every route hard-fail deleted except the
observable-spoofing ban (`OpenWingIsSolidAndSeen`); every enforced literal disclosed (the
settle window, `NONE 0`, the one-space format — and, after the third pass, the fitting
counts deliberately NOT disclosed as literals but disclosed as a world read); the negative
control made in-scene (the hall); the level made playable and pre/post staged with cp0 as
an explicitly reported baseline.

## What I changed from the approved design, and why

The design was implemented faithfully in shape. Six changes, five of them fixes to real
holes, one an editorial simplification. All are visible in `task.md`.

1. **`SealedWingUntouched` gained clause (b), and the staging-fault list was re-drawn.**
   *This was the one real defect.* The design's staging list ended runs as
   `HARNESS-PRECONDITION` on "wrong actor counts" and "a mark, post or board that does not
   expose its numbers readably" — but `BeginPlay` fires on every placed actor **before**
   `PrepareTest`, so a submission can cause both. That is a **denominator opt-out that
   costs the model nothing to buy**: destroy a post, get a non-graded verdict.
   `task.md` now draws the line by one question — *is the fixture's expected value
   satisfiable by any world?* Authoring faults (a `SectionId` naming nothing, a duplicated
   package, a hall section that cannot be unloaded, a tag missing inside a committed wing
   package, a level naming a game mode) stay attributed, because no C++ changes them;
   everything else — counts, moves, renames — is a graded `SealedWingUntouched` /
   `OnlyCalledWingPresent` FAIL.
2. **`CalledWingOpens` grades against the fixture's OWN deal table, never a read-back of
   the mark.** The design said "the name the mark was displaying at the moment of the
   step". Those are the same fact until a submission writes one of them — at which point
   reading it back lets a submission that re-letters every mark to `ROSE` agree with
   itself and pass. The fixture knows what it dealt; it grades against that.
3. **Added checkpoint `cp3r`, and the prompt sentence *"Re-lettering a mark is not a
   call"*.** Without it, a submission that polls the label and swaps whenever it changes
   is observationally identical to a correct one at every one of the design's cp1..cp5 —
   and it is a *plausible* reading of "read the mark, never assume a pairing", so it is
   exactly the kind of wrong answer this batch is supposed to separate. cp3r is gauged
   one settle window (1.5 s) after the re-lettering with the character standing on
   nothing, and its
   expectation is cp3's unchanged. **No new gate name** — the two existing gates carry it.
4. **The mirrored per-leg deal is MANDATORY, not "optional extra hardening".** The design
   offered it as a cheap extra. It is what makes difficulty condition (c) strictly true:
   with a single deal, a hard-coded `ALPHA→ROSE` is *right* at cp1, cp2, cp3 and cp3r and
   only wrong at cp4/cp5. With the 60 Hz and 20 Hz legs mirrored, and both legs required
   to pass, a hard-coded pairing is wrong at the **first** gauge point of one leg. It
   costs nothing: `fps_legs: [60, 20]` already runs both.
5. **The mid-run re-deal is event-driven, not `t = 10.0 s`.** The design pinned it to a
   wall-clock time after "three measured firings". Three walks plus three settles do
   not reliably fit in 10 s at 20 Hz, and a re-deal that lands *during* a step would
   manufacture a FAIL on a correct answer (the drive-manufactures-FAILs law: widen only in
   the safe direction, and never pin a phase to a clock when it can be pinned to its own
   event). It now fires after cp3 has been sampled and while the character overlaps no
   mark.
6. **The hall gets a post too (four posts, not three), and the board's API is
   `Report(FName, int32)` rather than a free-text setter.** The post makes the scene
   legible to a human and doubles the trap — an agent enumerating posts to "clear
   everything" now evicts the hall the same way an agent enumerating sections does. The
   typed `Report` removes a pure false-FAIL axis (a stray double space in `"ROSE  3"`)
   while leaving the graded content — *which* wing and *how many* fittings — entirely the
   submission's problem. The board still ships displaying `NONE 0`, which is the design's
   deliberate choice so the empty leg dies on the mission gate rather than on a blank
   board.

One thing I did **not** change: `GAMMA` always carries `SLATE`, in both deals of both
legs. It is the only assignment under which "a wing nobody has called must never have a
fitting in the host" is a *measured* statement — if a stepped mark could ever show slate,
a correct submission would open it and the check would be self-contradicting.

## Reconciled against the landed fixture

The fixture arrived after the first pass. Read end to end against the four artefacts it
judges; the contract matches exactly — tags `CallMark` / `WingPost` / `GateBoard` /
`WingFitting`, reflected `FName`s `MarkId` / `CalledWingName` / `WingName` / `SectionId`,
the `SetCalledWingName(FName)` switch with a direct-property fallback, the board's text
component named `Line`, the `Fitting.<WING>.<N>` per-instance identity, `ALPHA`/`BETA`/
`GAMMA`, the four sections (then `L_WingHall` / `L_WingRose` / `L_WingGold` /
`L_WingSlate`; renamed in the third pass — see *Adversarial review*),
the mirrored per-leg deals off `FApp::GetFixedDeltaTime()`, and the cp0..cp5 + cp3r gauge
set with the event-driven re-deal. **The scaffold and the reference needed no behavioural
change for any of it** (the only code edit in this pass was a factually wrong comment in
the reference — engine fact 6 below). Four things in `task.md` were prose the fixture then
contradicted, and prose that misdescribes the judge is a defect, so all four were fixed:

1. **The per-instance fitting tags are GRADED, not attributed.** `task.md` had listed "a
   per-instance fitting tag missing or duplicated inside a committed wing package" as an
   attributed authoring fault. It cannot be one: three of the four wings are out of the
   world when `PrepareTest` runs, so their tags are unobservable until after the
   submission has had its turn — an attributed exit keyed on them is exactly the
   denominator opt-out change 1 (above) was written to close. The fixture grades them and
   says so in its own header; `task.md` now agrees, and points the authoring-fault gate at
   `author_map.py` (refuse to save unless every per-instance tag reads back after a load from
   disk), which is the one place it can be submission-proof.
2. **`SealedWingUntouched` clause (a) also runs EVERY FRAME**, not only at the gauge
   points (`GuardControlsContinuously`, armed once cp0 is sampled, evaluated before the
   drive advances). It is the only thing that catches a hall taken out and put back
   *inside* a settle window, which a checkpoint-only sample would miss. Strictly a
   widening of a disclosed contract in the safe direction — a correct answer never touches
   the hall on any frame — so it needed disclosure in the spec, not a change to the gate.
3. **The hall's expected positions come from the SHARED LAYOUT TABLE, not from a
   transform recorded at cp0.** `task.md` said cp0 twice. The fixture compares against
   `kHallFittingAt`, the same numbers `author_map.py` places; and it is right to, for the
   same reason as (1) — cp0 is already downstream of the submission, so a cp0 recording
   would let a submission that moved a hall fitting before cp0 define its own baseline.
4. **A quoted FAIL literal did not exist.** `task.md` illustrated the hall failure as
   `"... absent from the host at cp1 (present at cp0)"`; the fixture's literal ends
   `"(no mark ever calls the hall and nothing may disturb it)"`. Left alone that becomes a
   `MATRIX.md` substring that never matches — a correct FAIL misclassified as a
   wrong-reason FAIL, which is the pass-everything trap in reverse.

## Adversarial review, 2026-08-19 — findings and fixes

Two reviewers attacked the task after the second pass. **Every one of their seven
findings held**; nothing was argued away. What each was, and what changed.

### BLOCKER — the minimal implementation passed every gate (difficulty condition (b))

The reviewer wrote out the ~35-line answer a competent engineer writes first — bind
`OnComponentBeginOverlap` on every `CallMark`, read the mark's live label in the
handler, hide the previously-opened section, show the new one from a hard-coded
`{ROSE→L_WingRose, …}` map, `Report(W, 3)` — and walked it through every gauge point of
both legs. It passed. The three difficulty axes were each a **verbatim prompt
sentence** rather than a judgment call, so every named wrong answer required
contradicting an explicit instruction instead of holding a defensible-but-wrong
reading. Condition (a) was thin for the same reason: the only computation the grade
forced was one `FName` read on one line, and the streaming half was driven by a value
transcribed out of the prompt.

**Fix — two more world reads, both coupled to the first, neither supplied by the
prompt.** Difficulty comes from coupling, not from riddles, so nothing was hidden that
the world does not answer:

1. **The wings are different sizes: 3 / 4 / 6 / 4** (hall / rose / gold / slate,
   `kWingFittings` in the fixture, `WING_FITTINGS` in the authoring script). The prompt
   says only that *no two wings need hold the same number* and that the board reports
   *how many of that wing's fittings are actually standing*. Consequences:
   - **Any constant count is wrong at cp1 or cp2 of BOTH legs**, because the deals are
     mirrored: cp1 wants rose's four on the fast leg and gold's six on the slow one.
   - **The count taken at the instant of the step is wrong everywhere**, because the
     wing has not arrived yet. That is the new locally-reasonable wrong answer, and it
     is the *minimal* shape rather than an extra-effort one: one function on the
     overlap that reads, swaps and reports. `BoardNamesTheOpenWing` names it at cp1.
   The prompt discloses the fact that makes it fair — "a wing does not arrive all at
   once" — without saying what to do about it.
2. **A wing's section is not named after the wing.** `L_WingVault` (HALL), `L_WingLoft`
   (ROSE), `L_WingKeep` (GOLD), `L_WingSpur` (SLATE), and the names appear nowhere in
   the agent-visible prose. This closes the fourth finding at the same time (below):
   `UGameplayStatics::GetStreamingLevel` suffix-matches **case-insensitively**, so with
   the old `L_Wing<WING>` scheme `FName(*(TEXT("L_Wing") + Wing.ToString()))` resolved
   without reading a single post, and the join the whole task turns on was free.

**The honest limit, written down rather than hidden.** Both new facts are *static*
properties of committed binaries. An agent with shell access could recover them by
grepping the `.umap` files for the baked `Fitting.<WING>.<N>` strings. That is
deliberately not special-cased — same reasoning as anti-gaming note 6 — because it is
strictly more work than reading the world, and because the fact that genuinely
**varies per run** (the mark→wing pairing) is fixture-side and appears in no committed
byte. Difficulty condition (c) still rests on the pairing; the two new reads carry (a)
and (b).

### MAJOR — the readout's number was a literal copied out of the prompt

`BoardNamesTheOpenWing` demanded `<WING> 3` at every gauge point of both legs, and the
settle window guarantees three are standing when it is sampled, so "count what is
actually standing rather than assuming three" was **unobservable by construction** —
not merely unpunished. Half the readout carried no information the prompt had not
already supplied, and the reference metadata still priced it at ~40 minutes. Fixed by
the same change as the blocker: the number is now a graded world read.

### MAJOR — the scaffold handed over the judgment cp4 exists to test

`CallMarkActor.h` ended its comment with *"Ask it at the moment you need the answer."*
The harness injects the scaffold into the prompt, so that sentence is an
**implementation directive**, and it defeats anti-gaming note 3 (cache the pairing at
`BeginPlay`) — the wrong answer that cp4 and the whole mirrored-deal machinery exist to
catch. Deleted. The two preceding sentences, which state the *fact* that marks are
re-lettered mid-run, are kept: Rule 7 requires the fact, not the instruction.

### MINOR — the section names were printed AND derivable

The agent-visible workspace section listed `L_WingHall.umap` … `L_WingSlate.umap` beside
the four wing names, so the join was a lookup table to copy; and it was free anyway via
the case-insensitive suffix match. Closed by the rename above plus removing the listing.
The workspace section now names the three things that are deliberately unwritten and
says they have to come out of the running world.

### MINOR — the re-entrancy guard was never exercised

Every step in the drive was a *change* of wing, so an implementation that
unconditionally hides the previous section and shows the new one graded identically to
one that guards, and anti-gaming note 5 (a take-down and a bring-in sharing one latent
handle) had no gauge point at which it could present. **Added cp6**: the drive steps off
`BETA` onto clear ground at (0, -2400) and straight back onto `BETA`, with no re-letter
in between, so the step calls the wing already standing and the expectation is cp5's
unchanged. It is the one step at which the take-down and the bring-in name the **same**
section, which is the only way that slip is observable. Cost: one drive phase, ~9 s of
world time, two new straight legs (both checked clear of every other mark).

### MINOR — the stall re-check could manufacture a FAIL

`RecheckStallableGates` re-ran the **checkpoint** form of `OnlyCalledWingPresent`
against the PREVIOUS gauge point's `ExpectedWing`. The engine's own begin-overlap fires
at about 152 uu and the fixture only calls the step landed at 45 uu, so throughout the
last ~107 uu of every approach a **correct** submission has already swapped — and a
walk-deadline or sentinel overrun in that window would have been written up as
`OnlyCalledWingPresent: at cp1 the host should hold exactly [… ROSE …] and it holds
[… GOLD …]`, i.e. the fixture's own stalled walk reported as the model's fault, in the
exact denominator the harness counts. Low probability, but *it could only ever invent a
FAIL, never catch one* — the opposite of the design intent.

**Fix.** `SealedWingUntouched` is expectation-independent (hall, furniture, and the
labels the fixture itself dealt) and is still re-checked whole. The multiset is now
checked for **scope only**: the hall, plus the complete fitting set of at most one
called wing, that wing being either the last gauged one or the one lettered on a mark
the character is within `kStallReachCm` (250 uu) of. Everything a stalling submission
can actually be caught by still fails by name — two wings at once, a duplicate, an
unnamed fitting, slate, a missing or moved hall, moved or renamed furniture. The
message keeps the `OnlyCalledWingPresent:` prefix so the matrix substrings still hold.

### MINOR — the settle window was the tightest number in the task and was unmeasured

1.0 s is exactly **20 world ticks** on the `-FPS=20` leg, in which a full
`UWorld::RemoveFromWorld` of the outgoing wing **and** a full `UWorld::AddToWorld` of
the incoming one must both complete — and both are incrementally time-sliced
(`World.cpp:3761` appends to `UWorld::Levels` at the start of the making-visible pass;
`World.cpp:4316` removes at the end of the making-invisible one), and `UWorld::Levels`
is exactly what the fixture's `TActorIterator` walks. A byte-perfect submission could
have failed with a harness timing budget wearing a gate's name.

**Fix — widened to 1.5 s IN THE PROMPT AND IN THE FIXTURE TOGETHER**, which is the only
legal direction (the negative gates are sampled at the same gauge points, so a later
gauge point does not weaken them, and none of the wrong answers this task catches fails
on *speed*). Gold's six fittings are now the worst case rather than three. **This is
still unmeasured** — widening reduces the risk and does not retire it. Gate 10 must
measure a real swap on the 20 Hz leg before any model result from this task is trusted;
if 1.5 s is not enough, widen the number in the prompt again, never the fixture's window
alone.

### What did NOT change

No gate was weakened or deleted, no assertion name changed, and no gate value was
hidden: every number the grade turns on is either stated in the prompt (the window, the
one-space format, `NONE 0`) or is a world quantity the prompt tells the agent to read
(the pairing, the section, the count). The reference needed **no behavioural change** —
it already resolved the section off the post and counted what was standing every frame,
and its `if (W == OpenWing) return;` guard is what cp6 now exercises. Only its header
comment was updated to say why each of the three reads is unavoidable.

## Design decisions worth writing down

**The hall MUST be a streamed section, and it must be `ULevelStreamingDynamic`.** This is
the whole task. If the hall's three fittings live in the persistent level, a
"clear every section, then load the target" loop never touches them, the owner's named
wrong answer passes, and the coupling evaporates — the task collapses to "load a level by
name", which is a T0. Worse, if the hall is added as `ULevelStreamingAlwaysLoaded`, it
*looks* right in the editor and is still fatal:
`ULevelStreamingAlwaysLoaded::ShouldBeLoaded()` is `{ return true; }`
(`LevelStreamingAlwaysLoaded.h:27`), so the world refuses to take it out — and
`SealedWingUntouched` becomes an **unfailable dead gate**, i.e. a permissive fake that
cannot tell the wrong answer from the right one. `task.md` lists "a hall section the world
refuses to take out" as an attributed staging fault precisely so this cannot ship
silently, and the authoring script must add all four wings with
`unreal.EditorLevelUtils.add_level_to_world(world, "/Game/Maps/<id>/L_Wing<X>",
unreal.LevelStreamingDynamic)` and then set the hall's `should_be_loaded` /
`should_be_visible` true and the other three false.

**Nothing about a fitting's wing may be read from the fitting.** `AWingFittingActor` lives
in the agent-writable module, so any `UPROPERTY` on it is a value the submission controls.
Identity is the per-instance `Tags` baked into the four committed wing packages
(`Fitting.HALL.1` …). `WingLabel` exists on the class as a supplied read **for the agent**
(the reference uses it to count what is standing) and the fixture never reads it. The
obvious tamper — adding a tag in the constructor — lands on all seventeen fittings at once
and fails `OnlyCalledWingPresent` immediately.

**No gate reads a streaming object.** Both corpus checks that did were rewritten (DEF-1).
Beyond the route-policing objection there is a second reason: an implementation that got
the right tagged, visible, solid fittings into and out of the host by some other means would
be *correct* by the prompt's own words, and a gate on `IsLevelVisible()` would fail it.

**The trigger is Tier 1 throughout (§7.1.3).** Walking onto a plate. No key press is
synthesised anywhere and no behaviour is invoked by calling into the submission, so the
Tier-2 block does not apply and there is no permissive-fake risk in the drive.

**The re-trigger convention (§7.1.4) is carried by `ALPHA` at cp1 and cp3** — same mark,
same deal, and the gates demand the same measured outcome. `BETA` also fires twice (cp2
and cp5) but with *different* demanded outcomes, because the re-deal sits between them;
that pair catches a latch too (a latched submission keeps gold standing at cp5 where rose
is required), it just is not the identical-outcome pair the convention asks for.

## Engine facts verified while authoring (UE 5.8 at `<UE-root>`)

Everything the reference relies on was read out of the engine source rather than
remembered:

1. **A short `SectionId` resolves in PIE.** `UGameplayStatics::GetStreamingLevel`
   (`Private/GameplayStatics.cpp:940-966`) runs the requested name through
   `FStreamLevelAction::MakeSafeLevelName` (`Private/LevelStreaming.cpp:304-324`), which
   prepends the world's `StreamingLevelsPrefix` (`UEDPIE_0_`) in PIE, then matches by
   **package-name suffix** against each `ULevelStreaming`'s `GetWorldAssetPackageName()`.
   So `SectionId = "L_WingLoft"` resolves under PIE exactly as the Blueprint
   `Load Stream Level` node's short name does. **This is why `SectionId` is a bare
   basename and not a `/Game/...` path.** The match is also **case-insensitive**, which
   is why the sections had to be renamed away from `L_Wing<WING>` in the third pass:
   `FName(*(TEXT("L_Wing") + Wing.ToString()))` produced `L_WINGROSE` and resolved
   `L_WingRose` anyway, so the post's `SectionId` was decorative.
2. **An unloaded section can be re-loaded — the re-trigger is safe.** Nothing in the
   plain streaming path calls `ULevelStreaming::SetIsRequestingUnloadAndRemoval`; the
   only callers are LevelInstance, World Partition and `UnrealEngine.cpp`'s force-unload.
   So `SetShouldBeVisible(false) + SetShouldBeLoaded(false)` leaves the `ULevelStreaming`
   object in `World->GetStreamingLevels()`, and `GetStreamingLevel` finds it again on the
   next call. Had that not been true, `ALPHA` at cp3 would have been unwinnable.
3. **`ULevelStreamingAlwaysLoaded` cannot be unloaded** — see above,
   `LevelStreamingAlwaysLoaded.h:27`.
4. **Loaded-but-not-visible is expected to yield ZERO tagged actors**, because
   `UWorld::Levels` (what `TActorIterator` / `GetAllActorsWithTag` walk) is populated by
   `AddToWorld`, which only runs once `bShouldBeVisible` is true. `task.md` states the
   design is correct either way — gate 1 catches zero actors, gate 4 catches hidden ones —
   but **this specific claim is the one engine behaviour that has not been observed on
   this box**, and the map batch must record which of the two it actually is.
5. **Reading the board's text**: `UTextRenderComponent::Text` is a public `FText`
   (`Components/TextRenderComponent.h:50`) and the shipped
   `LiftTowerFunctionalTest.cpp:1304` reads it as `R->Text.ToString()`. The fixture should
   use the same accessor.
6. **`PrimaryActorTick.bCanEverTick` IS a serialized `UPROPERTY()`** —
   `EngineBaseTypes.h:212`, a bare `UPROPERTY()` with no `Edit` specifier. The first draft
   of the reference asserted the opposite in a comment, which is now corrected: the
   conclusion (flipping it on the class reaches the board already placed in the level)
   still holds, but for the delta-serialization reason, not because the property is
   unserialized. The map is saved while the class default is `false`, so the instance
   record carries no override and inherits whatever the class says at load. **Failure
   signature if this is ever wrong:** the reference opens every wing correctly (the swap
   rides an overlap delegate, not `Tick`) and the board never leaves `NONE 0`, so refgate
   reports `BoardNamesTheOpenWing: the board should read 'ROSE 4' at cp1 and it reads
   'NONE 0'`. The one-line fix would be to drive the refresh off a repeating timer armed
   in `BeginPlay` instead of `Tick`.
7. **`MI_PrototypeGrid_Gray_01` does not exist in this substrate.** The four that do are
   `MI_PrototypeGrid_Gray`, `_Gray_02`, `_Gray_Round`, `MI_PrototypeGrid_TopDark`
   (plus `MI_DefaultColorway`). The first draft of `CallMarkActor.cpp` used `_Gray_01`;
   a failed `FObjectFinder` is guarded here, so it would not have broken the build — it
   would have logged an error at CDO construction and shipped an untextured pad.

## Hazards hit while authoring

1. **A submission-reachable `HARNESS-PRECONDITION` is a free way out of the denominator.**
   Written up as change 1 above; recording it here separately because it is the general
   lesson, not a fact about this task. The test to apply to any attributed exit: *can a
   submission cause this?* `BeginPlay` runs before `PrepareTest`, so "what the fixture
   found when it first looked" is never a clean baseline.
2. **A label-change listener passes a checkpoint set that only samples after steps.**
   Adding cp3r was cheap; noticing it was not. The general shape — *a wrong
   implementation that is observationally identical at every gauge point the design
   happens to have chosen* — is worth checking on every task with a mid-run re-stage.
3. **A scaled root multiplies both a child's offset and its bounds.** Every actor here
   uses either an unscaled `USceneComponent` pivot (fitting, post, board) or an unscaled
   `UBoxComponent` root sized with `SetBoxExtent` (mark), so no `UTextRenderComponent`
   ever inherits a scale. This is the trap the lift task had to divide back out of every
   child transform; sidestepping it costs one extra component.
4. **`FName(NAME_None).ToString().ToUpper()` is `"NONE"`**, which is exactly the board's
   pre-call line. Convenient, and deliberately relied on rather than special-cased — but
   it means a submission calling `Report(NAME_None, 0)` after a wing is standing reads
   `NONE 0`, which `BoardNamesTheOpenWing` catches, so the convenience costs no
   discrimination.
5. **The prompt is ~520 words against the authoring template's nominal 50–200.** Every
   shipped `craftbench-public` T2 exceeds that (the alarm exemplar is 971), and Rule 7
   forces it: every gate value has to be disclosed. Flagging it so nobody trims a
   disclosure to hit the word count and manufactures a DEF-4 undisclosed literal.
6. **Five new `.umap` basenames.** `L_WingHost`, `L_WingVault` (HALL), `L_WingLoft`
   (ROSE), `L_WingKeep` (GOLD), `L_WingSpur` (SLATE) were checked against
   `git ls-files` on 2026-08-19 and all five are free repo-wide; no basename is a
   suffix of another (which `GetStreamingLevel`'s suffix match would collapse), and
   `author_map.py` asserts that too. `cb lint` **cannot** catch a future collision
   (`tasklint._check_map` returns clean once any tracked copy exists) but it **does**
   verify the map count and every row of `docs/MAPS.md` against `git ls-files`, so
   `MAPS.md` and the prose count anchors must move in the same change or CI goes red and
   masks every later suite.

## Current lint state

`py -3.13 tools/verify-single/tasklint.py tasks/craftbench-public/t2-only-the-wing-you-called-opens/task.md`
now reports **1 error and 10 warnings** (it was 2 errors / 8 warnings before the fixture
landed). None is a spec defect:

- `ERROR map-binary-exists` — the five maps are not written yet. Clears when the
  orchestrator's map step lands. (`ERROR fixture-source-exists` has cleared.)
- `WARN discrimination-required` — no `discrimination/MATRIX.md` yet (the assignment
  enumerated four files and that was not one of them).
- **Two NEW `WARN fixture-fail-unique`**, on the fragments `'from the host at %s'` and
  `'the level put it, at %s'`. **Benign, and worth understanding before anybody "fixes"
  it.** The rule counts repeated `TEXT()` *fragments* across every
  `FinishTest(Failed, …)` in the file, not whole messages — and the fixture builds its
  messages from several adjacent `TEXT()` literals, so a shared tail fragment trips it.
  Both flagged fragments are tails of `SealedWingUntouched` messages (a missing hall
  fitting / a missing mark, post or board; a moved mark, post or board), and **every FAIL
  message in the file begins with its own gate name**, so the `MATRIX.md` substrings
  (`CalledWingOpens:`, `OnlyCalledWingPresent:`, `SealedWingUntouched:`,
  `OpenWingIsSolidAndSeen:`, `BoardNamesTheOpenWing:`) still identify the gate uniquely.
  The lint's stated worry — "the matrix cannot tell which fired" — does not apply. Do not
  reword a gate message to silence the warning without checking the MATRIX substrings.
- `WARN spec-h2-allowlist` (`Composed concepts`, `Requirement-to-assertion map`) and six
  `WARN reference-in-substrate` — **byte-identical to the green sibling's output**:
  `t2-alarm-escalates-and-cools-down` produces the same H2 warning and the same six
  byte-identical-reference warnings. The reference deliberately ships all four supplied
  pairs, three of them unmodified, which is the set's convention.

## What the orchestrator still owes

1. ~~The fixture~~ **DONE.** `AWingHostFunctionalTest` landed at
   `Source/CraftBenchTests/Tasks/t2-only-the-wing-you-called-opens/` and was read against
   these four artefacts — see *Reconciled against the landed fixture*. It is untracked, so
   it still has to be COMMITTED with the maps in one atomic change (the runner grades the
   substrate from git HEAD; an uncommitted fixture makes the L2 leg fail for the wrong
   reason — filter-miss / 0 tests).
2. **Five committed `.umap` binaries**, authored by a Python script that MUST assert, and
   refuse to save otherwise: (a) the persistent level is non-World-Partition — every
   committed `craftbench-public` map is authored with `LevelEditorSubsystem.new_level()`
   and none has a `Content/__ExternalActors__/` mirror, which is good evidence but not
   proof; (b) all four wings are added with `unreal.LevelStreamingDynamic`, never
   `AlwaysLoaded`; (c) the hall starts loaded+visible and the other three do not;
   (d) each fitting carries its per-instance `Fitting.<WING>.<N>` tag **and that tag
   survives an unload/reload cycle**; (e) World Settings name **no** game mode.

2a. **The layout table is SHARED and GRADED — copy it, do not re-derive it.** These are
   the numbers `WingHostFunctionalTest.cpp` compares against (`kMarkAt`, `kPostAt`,
   `kBoardAt`, `kHallFittingAt`), the marks/posts/board within **2 uu** and the hall
   fittings within **1 uu**, so a drift is a graded FAIL of a correct submission:

   | Thing | Position (X, Y) | Carries |
   |---|---|---|
   | mark ALPHA | (-1400, -1200) | `MarkId=ALPHA` |
   | mark BETA | (0, -1200) | `MarkId=BETA` |
   | mark GAMMA | (1400, -1200) | `MarkId=GAMMA` |
   | post HALL | (-2250, 600) | `WingName=HALL`, `SectionId=L_WingVault`, 3 fittings |
   | post ROSE | (-750, 600) | `WingName=ROSE`, `SectionId=L_WingLoft`, 4 fittings |
   | post GOLD | (750, 600) | `WingName=GOLD`, `SectionId=L_WingKeep`, 6 fittings |
   | post SLATE | (2250, 600) | `WingName=SLATE`, `SectionId=L_WingSpur`, 4 fittings |
   | gate board | (0, 2450) | — |
   | hall fittings | (-2670, 1250) · (-2250, 1650) · (-1830, 1250), all Z=0 | `Fitting.HALL.1..3` |

   `SectionId` is a BARE basename, never a `/Game/...` path — that is what
   `GetStreamingLevel`'s PIE-prefixed suffix match wants (engine fact 1 above) — and it
   is deliberately **not** the wing's own name, which is what makes the post the only
   place the join exists.

   **The per-wing COUNTS are graded too** (`kWingFittings` / `WING_FITTINGS` =
   3 / 4 / 6 / 4): the board must read `<WING> <that wing's size>` at every gauge
   point, so a wing built with the wrong number of fittings FAILs
   `BoardNamesTheOpenWing` and `CalledWingOpens` against a correct submission.

   The three callable wings' fittings are not position-graded; each wing takes the
   first N of `FITTING_OFFSETS` ((-420, +650), (0, +1050), (+420, +650), (-620, +1150),
   (+620, +1150), (0, +1650) from its post), so a human can see which wing arrived and
   how big it is. `|dx| <= 620` is load-bearing: the posts are 1,500 uu apart and a
   column is 90 cm across, so a wider offset puts two wings' columns inside each other
   (the script asserts a 140 uu minimum; the worst placed pair is GOLD.5 / SLATE.4 at
   260 uu). The hall keeps exactly its first three offsets, because those three
   positions are the graded in-scene control.

2b. **Two map facts the REFERENCE depends on.** Both are silent if missed — the reference
   FAILs refgate and the fixture's message names a gate, not the map:
   - **Every fitting's `WingLabel` must be set** to its own wing's name, in all four wing
     packages. The fixture never reads it (identity is the baked tag), but the reference
     counts what is standing with it, so an unset `WingLabel` makes the board read
     `ROSE 0` and fails `BoardNamesTheOpenWing` at cp1. It is also the only thing the
     nameplate prints, so a human sees blank plates.
   - **`PlayerStart` at the clear spot, (-1400, -2400), facing +Y.** The fixture's first
     leg is `PlayerStart -> ALPHA` and it drives straight lines only; from there the walk
     is due north onto ALPHA, passing no other mark — the nearest approach to BETA along
     that leg is 1400 uu, at the ALPHA end of it, and the clear spot itself is 1844 uu
     from BETA. The fixture does NOT check where the player starts, so a PlayerStart east of
     BETA would cross BETA's step volume on the way to ALPHA, call the wrong wing first,
     and manufacture a FAIL on correct work. Keep it clear of all three marks by at least
     the 700 uu the re-deal uses.

2c. **Stage the marks with leg 0's deal 0** — `ALPHA=ROSE`, `BETA=GOLD`, `GAMMA=SLATE`.
   `PrepareTest` re-deals immediately, so this does not affect the grade; it exists so a
   human who simply hits Play (checklist: the owner plays the reference before the task is
   done) walks into a coherent, correctly labelled building.
3. **`cameras.json`** (checklist step 5) framing the gate board and all four wing mouths.
4. **`discrimination/MATRIX.md`** — reference + empty only, per the 2026-08-18 owner
   directive; no variant legs. **Pick the empty leg's expected substring carefully: it
   must be leg-independent.** The mirrored deals mean the first mark shows ROSE on the
   60 Hz leg and GOLD on the 20 Hz leg, so the design's full literal
   (`CalledWingOpens: mark ALPHA showed ROSE at the step; 0 of 4 ROSE fittings stand in
   the host at cp1`) matches only one of the two legs and would misread the other as a
   wrong-reason FAIL — and since the third pass **the COUNT is per-leg too** (rose holds
   four, gold six), so `0 of 3` matches neither leg and `0 of 4` matches only one. Use
   `CalledWingOpens: mark ALPHA showed`, and note in the matrix that both the wing name
   and the count are per-leg by design. Every gate message begins with its gate name, so
   `<GateName>:` is always a safe row substring.
5. **`docs/MAPS.md` + the prose count anchors**, in the same change as the maps.
6. **Gate 10 calibration on BOTH legs**: measure how long a take-down plus a bring-in
   actually takes at 20 Hz — gold's six fittings are the worst case. The window was
   widened to **1.5 s** in the third pass (prompt and fixture together) precisely
   because 1.0 s was 20 ticks there, but it is STILL UNMEASURED. If it exceeds 1.5 s,
   **widen the number in the prompt** and
   re-measure the walk; do not widen the fixture's window past a number the agent was
   given. Also measure the wall clock for the whole drive plus sentinel against the 600 s
   per-leg L2 budget (it is one short walk per step, so this should be comfortable — but
   `l2_pie.py`'s 600 s is per `run_l2` call and the two fps legs do not share it).
7. **Confirm hazard 4 above** — whether a section loaded but never made visible yields
   zero tagged actors or hidden ones — and write the answer back into this file.
8. **The third pass is entirely unbuilt.** Everything under *Adversarial review* is
   designed and cross-checked and none of it has been compiled or run. Specifically:
   - the fixture gained `kWingFittings` / `kHallFittings` / `FittingsForWing()`, a
     `Cp6` gauge, `ToStepOff` / `ToBeta3` / `StandBeta3` phases, `kStepOffAt`,
     `kStallReachCm`, and a rewritten `RecheckStallableGates` with two local lambdas.
     `constexpr int32 kHallFittings = kWingFittings[0];` needs `kWingFittings` to stay
     `constexpr` — it is;
   - `author_map.py` gained `WING_FITTINGS`, `wing_index()`, `fittings_for()`, a
     `fitting_spots(x, y, count)` signature, six offsets instead of three, a
     minimum-separation assert, a step-off spot and two more drive legs in the leg
     clearance check. The geometry was verified arithmetically (all 17 fittings inside
     the floor's 200 uu margin, worst separation 260 uu, every leg >= 1,400 uu from a
     mark it is not aiming at, both clear spots >= 1,200 uu from every mark) but the
     script has still never been executed;
   - the five map basenames CHANGED: `L_WingHost`, `L_WingVault`, `L_WingLoft`,
     `L_WingKeep`, `L_WingSpur`. If any earlier draft of the maps was authored under
     the old names, delete it — `new_level` refuses an existing package and the fixture
     would raise a HARNESS-PRECONDITION on the missing sections.

## Still to do

The empirical half of the difficulty bar. **This task has never met a model.** Once it is
runnable, put a cheap model on it once (`cb eval --model claude-p:<cheap model>`): passing
first try with zero iteration means the bar was not met and it needs another axis. And per
the owner's 2026-08-18 directive, the task is not done until the owner has **played the
reference** — hit Play in `L_WingHost`, walk onto the marks, and watch the wings swap, the
board follow (the number changes with the wing now: rose reads 4, gold reads 6), and the
hall stay exactly where it is.

One thing to watch for in that first cheap-model run, specifically: **which gate it dies
on.** The third pass predicts the modal first failure is `BoardNamesTheOpenWing` at cp1
with `<WING> 0` — the board written once in the step handler. If instead every model
sails past the readout and only ever dies on `CalledWingOpens`, the count coupling is not
biting and the readout is decorative again.
