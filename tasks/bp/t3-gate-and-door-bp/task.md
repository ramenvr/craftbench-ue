---
id: t3-gate-and-door-bp
substrate: ThirdPerson
set: bp
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_OldDoorYard :: AOldDoorYardFunctionalTest"]
fps_legs: [60, 20]
introspect: [t3_gate_and_door_bp.py]
---

# t3-gate-and-door-bp

The Blueprint leg of a surface pair. `cpp/t3-gate-and-door-cpp`
is the other one. **Same map, same fixture, same checkpoint schedule, same drive, same
named gates, same tolerances, same `fps_legs`** — the only difference is which surface
the answer is written on, which is what makes the pair a measurement of the surface
rather than of two designs. Nothing is re-tuned for this surface: a re-tuned gate would
measure the tuning.

> # UNBLOCKED 2026-08-23 — the harness gap this banner described is closed
>
> The surface lane now carries both of the things this yard is built out of.
> Verified against `SwapAllForGradedBlueprint` specifically
> (`CraftBenchFunctionalTest.cpp:859-923`), not just the single-actor path, because
> the banner below warns precisely about a partial fix:
>
> * per-instance `UPROPERTY` values ride across via `SpawnStandInFor` ->
>   `CopyPropertiesForUnrelatedObjects`, so `CutForFirstName` / `CutForSecondName`
>   no longer collapse to `(None, None)`;
> * every inbound `AActor*` is re-pointed by `RepointReferencesTo`, so each pad's
>   `AnsweredBarrier` and each lamp's `LampBarrier` follow the swap;
> * and it is TWO PASSES — the first builds, wires and destroys each placed actor,
>   only the second calls `FinishStandIn`. No stand-in's `BeginPlay` runs until the
>   whole set is wired, which is the ordering that keeps `Pads` / `Lamps` non-empty.
>
> The `BLOCKED` guard in
> `tools/verify-single/introspect/t3_gate_and_door_bp.py`
> is lifted, and the reference asset `BP_YardBarrier` exists. **The leg has still
> never DISCRIMINATED** — the six-leg round of 2026-08-23 recorded
> `harness-error` on both legs, which was this guard firing exactly as designed, so
> the run said nothing about the submission. That discrimination is the next step,
> and it is the only thing that makes any claim here real.
>
> The original banner is kept below, collapsed, because the per-line cites in it are
> the record of what was actually wrong and the guard's lift condition was written
> against them.
>
> <details><summary>The original BLOCKED banner (2026-08-20), retained for provenance</summary>
>
> # ⛔ THIS LEG WAS BLOCKED AND NOT RUNNABLE AS OF 2026-08-20
>
> **Read this before spending a minute on the recipe or on an editor session.** The
> shared surface lane does not carry the two things this particular task's yard is
> built out of — **per-instance property values** and **inter-actor instance
> references** — and without them a *perfect* Blueprint submission cannot reach a
> graded verdict at all. Three blockers, in the order they fire, each read off the
> shipped code rather than predicted:
>
> 1. **The lamps lose their gate.** `ACraftBenchFunctionalTest::SwapForGradedBlueprint`
>    carries the **transform and the tags** across the swap and nothing else
>    (`CraftBenchFunctionalTest.cpp:701-730`, and the same body inlined in
>    `SwapAllForGradedBlueprint` at `:735-798`). `AGateLampActor::LampBarrier` is an
>    `EditInstanceOnly AActor*` staged in the level pointing at the **placed** gate,
>    and the swap destroys that gate. So `L.Barrier.Get()` is null / stale for all four
>    lamps and the fixture exits
>    `HARNESS-PRECONDITION: a lamp is bolted to something that is not one of the two gates`
>    (`OldDoorYardFunctionalTest.cpp:600-606`) — exit 7, NON-GRADED, before any judged
>    frame.
> 2. **The pads lose their barrier.** Same cause, `AYardPadActor::AnsweredBarrier`. The
>    fixture pins the wiring explicitly at `OldDoorYardFunctionalTest.cpp:645-656`
>    (`the six pads do not answer for the four barriers the way the yard is laid out`)
>    and — worse — its **own running model** decides which pads belong to which barrier
>    off that same pointer (`:1482`, `:1508`, `:1541`, `:1558`). The model cannot be
>    built on the Blueprint lane, not merely the staging check.
> 3. **The gates lose their staged pair, so the level-pair staging checks self-trip.**
>    `CutForFirstName` / `CutForSecondName` are per-instance `EditAnywhere` values. After
>    the swap every barrier holds the *Blueprint's class defaults*, i.e. `(None, None)`.
>    `PrepareTest` reads the level pair off the swapped actor
>    (`OldDoorYardFunctionalTest.cpp:1296-1301`), and `PairIsOpenable(None, None)` is
>    false by its first line (`:870-875`), so the run exits
>    `HARNESS-PRECONDITION: the level was saved with the arch gate cut for (None, None), which nobody could open by hand`.
>    The "both gates saved cut for the same pair" check at `:1324` would fire on the same
>    facts. `OpenAngleDeg` and `TravelRateDegPerSec` are lost the same way; they happen to
>    survive only because the class defaults (90 / 180) match what the yard wants.
>
> **And even with all three staging checks satisfied, the submission itself would still
> be dead:** the Blueprint reaches its pads and lamps through the inherited `Pads` /
> `Lamps` arrays, which `AYardBarrierActor::BeginPlay` fills by scanning for
> `AnsweredBarrier == this` / `LampBarrier == this`
> (`YardBarrierActor.cpp:147-168`). On a stand-in spawned by the swap those scans match
> nothing, so **every one of the four barriers wakes up with no pads and no lamps** — the
> old door can never open, which fails the headline preservation gate for a *correct*
> answer. That is an unwinnable leg, not surface discrimination.
>
> **What has to change, and it is not in this folder.** The fix belongs in the shared
> surface lane, because every future placed-prop pair whose yard is wired
> instance-to-instance will hit it:
> `SwapForGradedBlueprint` / `SwapAllForGradedBlueprint` must (a) copy the placed
> instance's editable `UPROPERTY` values onto the stand-in, (b) re-point every inbound
> `AActor*` reference in the world from the placed actor to its stand-in, and (c) do both
> **before** the stand-in's `BeginPlay` runs — a deferred spawn (`bDeferConstruction` +
> `FinishSpawningActor`) is the only ordering that lets the stand-in's own `BeginPlay`
> see a repaired yard. Fixing (a) and (b) after the spawn repairs the fixture's staging
> checks and leaves the submission's `Pads` / `Lamps` empty, which reads as a graded FAIL
> of a correct answer — the worst possible outcome and the reason to be explicit here.
> A per-task alternative (lazy re-resolution inside `AYardBarrierActor`) touches the
> scaffold both legs share and would invalidate the `-cpp` leg's discrimination, so it is
> the worse of the two.
>
> **What stops a run, mechanically, and what does not.** The front matter still declares
> `layers: [L1, L2, L2I]` with the `-cpp` leg's fixture, because there is no front-matter
> key for "blocked": `tools/verify-single/spec.py` validates against a closed
> `_KNOWN_KEYS` set (`spec.py:148`, enforced at `:226`) and rejects an unknown key
> outright, which would make the spec **unparseable** rather than skippable — a worse
> failure than the one it would record, and no task in the tree has ever declared a
> `status:` / `blocked:` / `draft:` key. So the stop is put where it can actually be
> enforced:
>
> * **L2I fails closed.**
>   `tools/verify-single/introspect/t3_gate_and_door_bp.py`
>   opens with a BLOCKED guard that prints a diagnostic and **emits no verdict block**.
>   `layers/l2_introspect.py` reports that as status `error`, and
>   `run_task.harness_error_reasons` predicate (5) turns it into **exit 7 /
>   `overall: "harness-error"`**, which `adapters.base.GRADED_VERDICTS` excludes from
>   every pass-rate denominator. That is the point: it guarantees this leg can never
>   produce a *graded* verdict while the gap stands — including the one bad outcome L2
>   alone would not prevent, a partial swap fix that stages successfully and then grades
>   a correct answer FAIL on empty `Pads` / `Lamps`. Lifting it is deleting one block,
>   and the guard states its own lift condition in place.
> * **What a sweep costs today, measured rather than assumed.** `cb discriminate bp`
>   expands by folder (`discriminate.expand_targets`) and does reach this id, but stops
>   cheaply — `no reference solution at … (the PASS oracle is required)`, no editor, no
>   build. `cb refgate` and `cb bench --refgates` also stop cheaply (`no committed
>   reference for … — cannot certify this task`) but do it under
>   **fail-verbatim-and-STOP** semantics (`cb.py:_run_refgates`), so they abort the whole
>   sweep here and grade none of the tasks queued after it. **Both cheap exits disappear
>   the moment the reference `.uasset` lands** — which is exactly what `REFERENCE-NOTE.md`
>   instructs — and each becomes a full non-graded run per `fps_leg`. Author the asset if
>   you want the recipe validated by hand in an editor; do not schedule this id.
>
> Everything below is written to be correct **once that lands**. Nothing below has been
> run. The recipe in `REFERENCE-NOTE.md` is complete and buildable; it is simply not
> gradeable yet.
>
> </details>

## Provenance

Ported from `cpp/t3-gate-and-door-cpp`, whose behaviour, drive
and gates are reproduced here verbatim. That leg was built against the 2026-08-18
difficulty bar and hardened 2026-08-19 against two adversarial reviews (the second gate
and the third re-cut both come from that pass); its reference is 2 files,
**135 added / 17 removed**, and it is the leg this one is measured against.

**Why the pair exists at all.** The benchmark's thesis is a (model x tool x SURFACE)
interaction, and the surface axis was carried by six `gp-` pairs alone: every task whose
graded actor is **placed in the committed map** was C++-only, because `Content/Maps/` is
deny-write to agents, so a Blueprint subclass would never be instantiated. Three changes
opened the lane, all landed 2026-08-20 and all recorded here because none is guessable
from the spec:

1. **`ACraftBenchFunctionalTest::ResolveGradedBlueprintClass(UClass* PlacedClass)`** —
   the single Blueprint under `/Game/Tasks` (recursive, via the asset **registry**,
   because nothing in the map references a class the agent invented) whose
   `GeneratedClass` is a strict, non-abstract subclass of the placed class; `nullptr`
   when there is none, which is the C++ lane running byte-identically. **Two candidates
   raise `HARNESS-PRECONDITION` rather than picking one**, because grading a submission
   the agent may not have meant is not a verdict.
2. **`SwapAllForGradedBlueprint(TArray<AActor*>& InOut)`** — this task's swap, and the
   right one for it: four barriers built from one supplied class, **all replaced or
   none**. It resolves the Blueprint ONCE off the first entry, refuses a **mixed** array
   (a half-swapped yard would grade C++ for the old door and Blueprint for the gate,
   which is a verdict about neither), and rewrites `InOut` in place. The fixture then
   **re-resolves by tag and re-checks the count** rather than trusting the swap, so a
   half-completed swap is a HARNESS-PRECONDITION and not a graded failure
   (`OldDoorYardFunctionalTest.cpp:373-388`). The sibling entry points are
   `SwapForGradedBlueprint` (one instance) and `SwapAllForGradedBlueprintRepossessing`
   (the set swap plus re-possessing player 0 when the pawn it was driving was replaced);
   this task needs neither.
3. **`AYardBarrierActor::ShouldBeOpen` is now `UFUNCTION(BlueprintNativeEvent)`** — it
   was a bare `virtual bool` until 2026-08-20, and a bare virtual is invisible to
   Blueprint, so **this leg was flatly unwinnable before that change**. The C++ body
   moved to `ShouldBeOpen_Implementation`; every call site still reads `ShouldBeOpen()`
   (`YardBarrierActor.cpp:207`), so a Blueprint override is what the yard's `Tick`
   actually asks. An unwinnable leg is not surface discrimination.

What the swap carries — **transform and tags only** — is the fourth fact, and it is what
blocks this leg today. See the banner.

## Primary concept

- `ps-actors` — Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine)

The load-bearing behaviour is unchanged from the `-cpp` leg: **one shared actor class
whose placed instances must behave differently from each other, each decided from data
carried on that instance and re-read every time it is needed.** Four of the yard's
barriers are instances of that class; two must keep the behaviour they shipped with and
two must each acquire a new one that is *not the same as the other's*.

**What the surface adds to that, and it is not decoration.** On this leg the agent
delivers **one** Blueprint and the fixture puts it behind **all four** barriers. So
"per instance" stops being a discipline and becomes structural: the *same asset* is the
old door, the door nobody touches, the arch gate and the second gate. An answer that
overrides the yard's rule unconditionally does not merely risk breaking the old door —
it breaks it by construction, on the first cycle, in the one file the agent wrote. The
C++ leg lets a careless author narrow the rule and still be looking at four distinct
translation units; the Blueprint leg hands them one.

## Composed concepts

Identical to the `-cpp` leg — `actor-lifecycle` (the pair is rewritten three times, the
first before the drive and after every `BeginPlay` has run), `collision-overview`
(resting is resolved per pad against that pad's own radius and level, for bodies of two
shapes), `ps-components` (every graded readout is a component read off the thing
itself), `movement-components` (the only trigger in the task is locomotion). The full
prose, the production-pattern citations (Stack-O-Bot's generic plate→door chain plus one
special-cased door; Lyra's "extend a shipped system without regressing its consumers")
and the two places a first-pass fix fights itself live in the `-cpp` spec's *Composed
concepts* and are not restated here.

`ps-bp-overview` — Blueprints Visual Scripting Overview
(https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprints-visual-scripting-in-unreal-engine)
— is the one concept this leg adds.

## Prompt given to the agent

> Deliver your solution **entirely as Blueprint assets** created in the editor and saved
> under `Content/Tasks/t3-gate-and-door-bp/`. **Do not add or
> modify any C++ source for this task.** The C++ that ships is read-only reference
> material for what you can call.
>
> **The yard as you find it.** An old door stands at the north end of the yard with a
> floor pad in front of it. It works, and it has worked for years: while somebody is
> standing on that pad the old door is open, and the rest of the time it is shut.
> Thirty metres east there is a second door with its own pad that nobody ever goes
> near. Both doors start shut.
>
> **Standing on a pad** means the middle of your solid body being within **100 cm** of
> the pad's centre, measured flat with height ignored, with the bottom of that body
> down on the pad's own level rather than up in the air. That is true of a person and
> it is equally true of a crate, and the yard has never cared which.
>
> **How the yard behaves today, before you touch it.** One rule runs every pad in the
> yard: while any single body — a person or a crate — is resting on a pad, whatever
> barrier that pad answers for is open, and otherwise it is shut. That one rule is what
> makes the old door work, and **the old door's behaviour has to survive whatever you
> do.**
>
> **Every barrier in this yard is built from the same one thing, and whatever you
> deliver stands behind all of them** — the old door, the door nobody goes near and both
> new gates alike.
>
> **The old door is judged exactly the way it is judged today, and that does not
> change.**
>
> - Within **1.20 s** of somebody stepping onto its pad, its panel must be at least
>   **80 degrees** from the pose it starts play in.
> - Within **1.20 s** of the last person stepping off, it must be back within
>   **10 degrees** of that pose.
> - It travels: its panel never moves faster than **720 degrees per second** or
>   **3000 cm per second**, in either direction.
> - It does this every time, not once — as many times as anyone walks on and off it,
>   including after the work below has been built and used.
>
> **What you are here to build. There are TWO new gates hung in the west wall.** Each
> of them has two floor pads of its own, and three crates sit on rails in the yard. A
> crate slides along its own rail between two hard stops when somebody shoves it, and
> one of those stops parks it on a pad. Two of the rails feed a far pad from opposite
> sides, so only one crate at a time can be parked there. **The two gates' pads are
> painted on the same two patches of floor**: a crate parked on one gate's pad is
> resting on the other gate's pad as well, and both gates are looking at the same three
> crates at every moment of the day.
>
> Every crate has a name written on it. **Each gate is cut for two of those names, and
> the two names a gate is cut for are written on that gate**, first and second. **The
> two gates are cut for different pairs, and neither gate's pair tells you anything
> about the other's.** A gate must be open exactly while a crate carrying the first of
> *its* two names and a crate carrying the second of *its* two names are both resting
> on *its* pads, and shut the rest of the time. Either of a gate's two names may be
> resting on either of that gate's two pads. Open and shut are measured for a gate
> exactly as they are for the old door: at least **80 degrees** from its play-start
> pose, or back within **10 degrees** of it, reached within **1.20 s** of whatever
> changed, and never travelling faster than **720 degrees per second** or **3000 cm per
> second**.
>
> When a crate a gate is cut for is shoved off one of that gate's pads the gate must
> shut again, and when it is shoved back on while the other one is still home the gate
> must open again — for either of the two, any number of times, in either order.
>
> **Each gate carries two lamps**, one for each of the two names *that* gate is cut
> for, in that order: a gate's first lamp stands for its first name and its second lamp
> for its second. A lamp is lit exactly while a crate carrying its own gate's name for
> its own slot is resting on one of its own gate's pads, and dark otherwise. They start
> dark. The lamps are the only way anybody outside can tell which crate a gate thinks
> it is holding, so a lamp has to be right within the same **1.20 s**.
>
> **What a gate is cut for is not fixed for the day.** The foreman re-cuts the names
> without announcing anything, and he does it whether or not a crate happens to be
> sitting on a pad at the time — including when nothing else in the yard is moving at
> all. He re-cuts each gate on its own account; he may put a different name in either
> slot, and he may put the same names back in a different order. A gate and its lamps
> have the same **1.20 s** to be right after a re-cut as after anything else. The names
> on the crates and the names on a gate are readable off the things themselves; they
> are written down nowhere else.
>
> **Nothing else in the yard may change.** No other barrier may move: the second door's
> panel must stay within **10 degrees** of its play-start pose from the first frame to
> the last. Do not move a pad, a crate, a rail, a door or a gate, and do not rewrite any
> number or name the yard came with, or the barrier a pad answers for — the foreman's
> re-cut is his to make, not yours. Everything needed to *show* what happens is already
> built and working: each barrier travels its own panel when it is told whether it
> should be open, each lamp has a switch, and each crate slides on its rail when it is
> shoved.
>
> All the times above are wall-clock seconds and must hold whatever the frame rate. Do
> not edit the level, any config file, or any test file. Deliver Blueprint assets only,
> under `Content/Tasks/t3-gate-and-door-bp/`.

## Workspace state pre-task

**Deliverable root: `Content/Tasks/t3-gate-and-door-bp/`** —
Blueprint assets only. **No C++ file may be added or changed**; the C++ that ships is
read-only reference material for what you can call. `Source/CraftBenchTests/` is
deny-listed and a submission file under it is a SANDBOX-REJECT (exit 4), not a graded
FAIL; so are `Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/`,
`Content/LevelPrototyping/` and every `Config/` file (no `config_allow` is declared by
this task). Note that a C++ file under `Source/ThirdPerson/` is *path-legal* on this
substrate, so the sandbox will accept it; it is the surface contract above that forbids
it.

The yard is exactly the `-cpp` leg's yard, staged in the same committed
`Content/Maps/L_OldDoorYard.umap`. What is in it, and what is supplied working:

- **Four barriers, all instances of one supplied class**, tagged `YardBarrier`: the old
  door at the north end, its pad 300 cm in front of the panel; an identical door with an
  identical pad 3,000 cm east that nobody ever goes near; the arch gate in the west wall
  with two pads of its own, one 700 cm east of the gate and one 800 cm south of that; and
  a second gate 2,100 cm further along the same wall whose two pads are painted
  **over the arch gate's**, 3 cm proud. Each barrier carries a frame, a bare hinge, the
  380 x 500 cm panel a person watches swing, a floating angle readout and a floating
  plate printing the pair it is cut for. Both readouts are derived from live state, so
  neither can disagree with the thing it describes; nothing reads them back. Its own
  `OpenAngleDeg` and `TravelRateDegPerSec`; its own ordered pair of names, **re-cut
  during play without announcement**; a `SetCommandedOpen(bool)` override that anyone
  may call from anywhere (the most recent call within a frame wins; with no call the
  yard's own rule decides, and the barrier never asks who called); and **the yard's one
  rule — open while any single body is resting on any pad that answers for this barrier**
  — which is the thing the deliverable is allowed to answer differently. A `Tick`
  resolves those two, sweeps the panel toward the pose it should hold at
  `TravelRateDegPerSec` and no faster, and keeps both readouts honest. **No reference to
  a crate's name and no reference to a lamp's switch.**
- **Six pads**, tagged `YardPad`: a 240 x 240 cm painted mat, flat with the floor,
  non-colliding, walked over and slid over. Its own contact radius and grounded band;
  the barrier it answers for, set per placed pad and **not the pad's to change**; and
  the question it has always answered — *who is resting on me* — for one body, for all
  of them, or as a yes/no, counting **people and crates alike**. A marker rides up while
  something rests here; nothing reads it back.
- **Three crates** on rails, tagged `YardCrate`: a solid 120 cm box with its own name,
  rail length, shove speed and shove reach; the rail anchor, axis and live parameter;
  a floating plate printing its own name; and a `Tick` that runs it along its own rail
  toward whichever hard stop somebody is walking it toward, stopping dead at either end,
  never leaving the segment and never changing height. Each rail parks its crate on a pad
  centre at one stop and 900 cm off it at the other. It stops **one footprint short of
  another crate** in its way, so the two rails that share the far stop can only take it
  one at a time. It reads what a body is **asking** to do rather than how fast it is
  managing to move. **It has never heard of a pad, a door or a gate.**
- **Four lamps**, tagged `GateLamp`, two on each gate's frame: a bracket, a bulb and a
  point light; its own slot (0 for the first of its own gate's two names, 1 for the
  second); the gate it is bolted to, set per placed lamp; **the switch**, which sets the
  light's intensity *and* swaps the bulb's material (a swap rather than a parameter
  write, because not every prototype material here carries a colour parameter and a
  write that silently does nothing leaves the state invisible while looking like it
  worked); and a read-back off the light rather than off a flag. **Starts dark. Nothing
  throws it.**
- **The level**: 9,000 x 9,000 cm floor striped every 400 cm (stripes non-colliding), so
  speed and distance are readable by eye; a PlayerStart on
  the floor south of the old door's pad facing it, a non-colliding backdrop and two
  landmark posts so a moving camera is distinguishable from a still one, and one placed
  test-harness actor in a module the agent can neither read nor modify. World Settings
  name **no** game mode, so the level inherits the template's game mode, controller,
  character and input mappings — pressing Play gives a visible, animated, drivable body
  with no per-task wiring at all.
- **The three crates' names, the pairs the two gates start cut for, the pads' radii, the
  barriers' travel rates and the rails' lengths are deliberately NOT written here.** They
  are readable in the level, on the things themselves.
- `cameras.json` (the camera-plan lane; not part of this release) — **not yet
  authored.** The `-cpp` leg's camera plan sits in its own folder and the two legs share
  a map, so the plan is portable; it is presentation-only and non-gating either way.

**What exists in code and what does not.** Everything above is C++ that ships read-only.
There is **no code anywhere that knows what a crate is called, that treats one barrier
differently from another, or that throws a lamp's switch**, and **no Blueprint asset of
any kind**. An empty submission compiles (L1 green, since nothing was added) and FAILs
L2 the first time a crate is shoved onto a gate pad, because the yard ships deliberately
**over-permissive**: the supplied one-body-per-pad rule already swings both gates wide
open on the first crate. On this leg an empty submission is also the C++ lane — with no
Blueprint under `/Game/Tasks` the swap is a no-op and the placed instances are graded,
byte-identically to the `-cpp` leg's empty submission.

**Everything the behaviour needs is reachable from a Blueprint that extends the
barrier** — the yard's rule, the lamp switch, the pad's occupancy questions, every
crate's name, every barrier's pair, and the list of pads and the list of lamps that
belong to the barrier being asked. Nothing this task requires is missing from the
Blueprint surface, so a dead end you hit is a dead end worth re-reading rather than a
wall. Two of the C++ readers you may see in the headers are not exposed to Blueprint; the
same two lists are exposed as properties a subclass can read instead, so there is nothing
here you need that you cannot reach.

## Verifier specification

**Identical to the `-cpp` leg, ported verbatim.** Same committed map
(`Content/Maps/L_OldDoorYard.umap`), same fixture (`AOldDoorYardFunctionalTest`), same
twenty-phase adaptive drive through the shipping per-frame `AddMovementInput` timeline,
same three re-cuts (#0 in `PrepareTest` before the first judged frame, #1 at phase 11
with both patches empty, #2 at phase 17 with nothing in the yard moving), same 110
calibration checkpoints plus the t = 900 s sentinel, same settle and suppression rules
(1.80 s since the model last changed anywhere; 1.5 s around each re-cut), same
`fps_legs: [60, 20]`, same eleven named gates in the same precedence, same failure
literals. The full description — the fixture's own model, why the two models cannot
drift apart, the phase table, the second gate's parallel trace, the staging exits and
the `::Error` denominator-opt-out invariant — lives in
`cpp/t3-gate-and-door-cpp`'s `## Verifier specification`.
**Nothing is re-tuned for this surface.**

The one thing worth restating, because it is what makes this leg a *pair* leg rather
than a second task: the fixture reaches every barrier by its own role **tag**
(`OldDoor`, `QuietDoor`, `ArchGate`, `SideGate`) and the swap carries tags over, so the
four roles survive the surface change intact and the eleven gates are gauging the same
four barriers on both legs.

**What this leg adds, and only this:** an L2I introspect leg
(`tools/verify-single/introspect/t3_gate_and_door_bp.py`) that
structurally proves the thing L2 graded really was a Blueprint. Proving a Blueprint
*exists* is not enough — a C++ solve shipped beside a conforming Blueprint would pass L2
on the C++ and pass a naive existence check on the asset. The script therefore
**reproduces the fixture's own resolution** and requires the resolved answer to be
Blueprint-generated, and separately requires that **no native subclass of the placed
class was delivered** (the scaffold class is exempt by exact `/Script/` path, never by
name). Because this task's fixture swaps **two** agent-facing classes' worth of
behaviour through one asset, the script checks the resolution for the barrier class and
asserts the absence of a Blueprint that shadows any of the other three placed classes —
a Blueprint subclass of the pad, the crate or the lamp is never instantiated by this
fixture and is therefore a silent no-op that would otherwise look like work. See the
script's own header.

**What that L2I leg does NOT cover, stated here and not only in the script.** Every sweep
looks for a **new** native class. An **in-place edit of a shipped scaffold `.cpp`** —
which is exactly how the `-cpp` reference solves this task — leaves no new class behind,
so all of L2I's checks pass while L2 grades a C++ answer. The submitted-file list the
runner already computes is filtered to `Content/` packages before L2I sees it
(`layers/l2_introspect.py:409-410`), so this cannot be closed from the introspect script;
it needs a runner-side "no submitted file under `Source/`" check. Anti-gaming note 12
carries the full account. **Until that lands, a green L2I here is not evidence that no
C++ was written**, and no sentence in this spec — agent-visible or not — should say
otherwise.

**And while the surface lane cannot stage this yard (see the banner), the L2I script
opens with a BLOCKED guard that emits no verdict block at all**, so the layer reports
`error` and the whole run lands as exit 7 / `harness-error` — non-graded, out of every
denominator. That is a deliberate fail-closed choice: it is the only place in this
folder's remit where a run can be stopped mechanically, and it forecloses the one outcome
L2 alone would not, namely a partial swap fix that stages and then grades a *correct*
answer FAIL. Both this guard and the coverage gap above are lifted by editing files
outside this folder; neither is lifted by editing this spec.

## Requirement-to-assertion map

Ported verbatim from the `-cpp` leg; the only added row is the last one.

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| the old door opens within 1.20 s of somebody standing on its pad, and shuts within 1.20 s of the last person leaving | `TheOldDoorStillOpensInsideItsBand` | **never** — armed on every judged frame. Its subject is the old door, whose model is shut everywhere outside phases 1, 2, 9 and 18, so those are the only phases where it can DISTINGUISH anything; a submission that swings the old door at, say, phase 5 is named by it there |
| the old door does it **every** time, not once, including after the gates are built and used | same gate, four cycles, two of them after the agent's work is exercised | as above |
| the panel never travels faster than 720 deg/s or 3000 cm/s | same gate on every judged frame of every cycle, and the same clause inside `TheGateOpensWhenBothItsCratesAreHome` | frames the settle rule suppresses |
| standing on a pad = middle of the body within 100 cm of the centre, flat, base on the pad's level | the fixture's model uses exactly that predicate, re-implemented from live transforms; `TheYardIsNotYoursToRewire` pins both radii so it cannot be widened underneath | never |
| a person or a crate both count for the pads | `TheOldDoorStillOpensInsideItsBand` (a person must count) and `TheGateStaysShutUntilBothItsCratesAreHome` (a crate must count, at phase 3) | as above |
| a gate is open exactly while crates carrying **both** of ITS two names are home | `TheGateOpensWhenBothItsCratesAreHome` and `TheGateStaysShutUntilBothItsCratesAreHome` for the arch gate; `TheSecondGateAnswersToItsOwnPair` for the other | frames a windowed gate above owns (arch only) |
| the **two gates are cut for different pairs** and neither's pair says anything about the other's | `TheSecondGateAnswersToItsOwnPair`, every judged frame, at four dwells where the two correct panels differ; and `TheGateLampsNameTheCratesItHolds` at phases 3 and 13, where one crate lights opposite slots on the two gates | never |
| either name may be on either of THAT gate's pads | `TheGateAnswersToWhatItIsCutForRightNow` at phases 13-14, where the first name is on the FAR pad and the second on the NEAR one, plus the lamp gate throughout | outside phases 12-14 |
| a crate the gate is not cut for is not enough | `TheGateStaysShutUntilBothItsCratesAreHome` at phase 5 (C on the contested pad) and phase 12 (B after re-cut #1) | outside those dwells |
| a person on a gate pad never counts toward anything | `TheRunnerIsNotACrate` | outside phases 7 and 15 |
| shoving a crate off shuts the gate; shoving it back on re-opens it; either crate, any number of times | `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack`, both crates, twice | outside phases 5-8 and 15-16 |
| each gate carries two lamps, one per name **in that order**, lit exactly while a crate carrying that gate's name for that slot is home on that gate's pads, dark otherwise, starting dark, right within 1.20 s | `TheGateLampsNameTheCratesItHolds`, every judged frame, all four lamps, each against its own gate, read from the light | only on a frame where a panel gate already failed |
| the pairs are re-cut without announcement, each gate on its own, including with nothing moving | `TheGateAnswersToWhatItIsCutForRightNow` for the arch gate (all three re-cuts), `TheSecondGateAnswersToItsOwnPair` for the other, `TheGateRoseAgainAfterEveryRecut` for both at run level | never, once the drive has arrived |
| the second door's panel stays within 10 deg from the first frame to the last | `TheDoorNobodyTouchesNeverMoves` | never |
| do not move a pad, crate, rail, door or gate, and do not rewrite any number or name, or the barrier a pad answers for | `TheYardIsNotYoursToRewire`, every frame, all four barriers and six pads | only the four name slots on the two gates, only inside the fixture-owned re-cut windows |
| all times are wall-clock and hold whatever the frame rate | `fps_legs: [60, 20]` runs the whole drive twice in two PIE processes | never |
| **the answer the run graded is Blueprint-generated, sits under `Content/Tasks/t3-gate-and-door-bp/`, and no NEW native class was delivered** | **L2I `t3_gate_and_door_bp.py`** | **never** — L2I is declared, so a missing or unparseable script is exit 7 (HARNESS-ERROR, non-graded), not a pass |
| **"no C++ added or modified"**, in the case that matters most: an **in-place edit** of a shipped scaffold `.cpp` | **NOTHING** | **always.** No gate in `tools/verify-single/` checks it — see note 12 and *What is NOT measured*. L2I sweeps for a NEW native subclass; a modified scaffold leaves no new class to find, and the swapped Blueprint simply inherits the edited native body. Caught only by the submission diff and human review |

## Reference solution metadata

- **Assets**: one Blueprint,
  `/Game/Tasks/t3-gate-and-door-bp/BP_YardBarrier`, parented
  to the supplied barrier class. Nothing else. The reference tree mirrors the deliverable
  root:
  `tasks/bp/t3-gate-and-door-bp/reference/Content/Tasks/t3-gate-and-door-bp/BP_YardBarrier.uasset`.
- **The recipe is `REFERENCE-NOTE.md`**, precise to the node and the pin, because there
  is no script lane for Blueprint **graph** authoring in this repo and the asset is built
  by hand in an attended editor session.
- **Shape of the answer**: one override of the yard's rule that branches on whether a
  pair of names is written on the barrier it is being asked about — unwritten hands
  straight back to the parent implementation, written runs a two-of-two name test — plus
  one helper function that answers *is a crate carrying this exact name resting on one of
  my pads* and one `Event Tick` pass that sets each of my own lamps from the name written
  in **its own** slot right now. Predicted at roughly 30-40 nodes across three graphs.
- **The `-cpp` reference is 135 added / 17 removed across 2 files**, ~62 of the added
  lines being code: one branch, one predicate, one name lookup, one slot accessor, one
  lamp loop. The Blueprint answer is the same five pieces in the same five places, which
  is the strongest evidence available at authoring time that the two legs differ in
  surface and not in design.

### What is NOT measured

Everything. To be explicit, because a spec that reads finished is how an unmeasured leg
gets scheduled:

- **This leg has never been graded, and cannot be**: see the banner. Three
  HARNESS-PRECONDITION exits fire before the first judged frame, and a fourth failure
  (empty `Pads` / `Lamps` on every stand-in) would produce a graded FAIL of a correct
  answer if the first three were fixed without fixing the spawn ordering.
- **There is no reference asset on disk.** `REFERENCE-NOTE.md` is a recipe derived from
  the `-cpp` reference and the shipped headers; no `.uasset` has been authored, so
  nothing has been compiled, spawned or swapped.
- **No discrimination.** No reference PASS, no empty FAIL, on either `fps_leg`. The
  `-cpp` leg's own discrimination status is recorded in its folder and is not evidence
  about this one.
- **No refgate certificate**, and none should be attempted: a gate on a task whose
  fixture cannot stage is a full re-grade that caches nothing.
- **The owner has not played it.** Per the 2026-08-18 directive a task is not done until
  the owner has played the reference; the map is the `-cpp` leg's, so the play project
  already carries the yard, but the Blueprint reference does not exist to be played.
- **`cameras.json` is not authored for this leg.**
- **The surface contract is only PARTLY checked, and the uncovered half is the cheap
  one.** L2I catches a new native subclass; it cannot catch an in-place edit of a shipped
  scaffold `.cpp`, which is the `-cpp` reference's own shape. See anti-gaming note 12 for
  the exact submission that beats it and *Verifier specification* for why it cannot be
  closed from the introspect script. Three earlier drafts of this spec asserted the
  contract *was* checked — including once inside `## Workspace state pre-task`, i.e. to
  the model under test — and those assertions are gone rather than softened.
- **Every claim in *Verifier specification*, *Requirement-to-assertion map* and
  *Anti-gaming notes* is a prediction** — inherited from a leg that does discriminate,
  which is good evidence about the gates and no evidence at all about the surface.

## Anti-gaming notes

> **On disclosure.** Every defence below rests on a contract the prompt states in
> positive form, plus the rule the yard runs today. It does **not** rest on the prompt
> naming the failure. The `-cpp` leg's first cut had a sentence in the agent-visible
> prompt for almost every note here, which made the pre-mortem a transcription
> exercise; those sentences are gone from both legs and the values they carried are
> still entailed by the contract. The one sentence this leg's prompt adds — that
> whatever is delivered stands behind **all** the barriers — is not a hint about a
> failure mode: it is a disclosure of how the surface lane instantiates the answer, and
> without it note 13 would be a trap rather than a requirement (and note 16 would burn a
> non-graded run to say so).
>
> **One sentence was cut on 2026-08-20 for being a hint rather than a disclosure.** The
> first draft followed the sentence above with: *"There is no way to give one of them a
> rule and leave the others out of it except by deciding, inside that rule, from what is
> written on the barrier it is being asked about."* That names the **shape of the
> answer** — branch inside the rule on what the barrier carries — which is the whole
> difficulty of the `-cpp` leg, stated there nowhere, and it pre-empts notes 13 and 16.
> A bp-vs-cpp pass-rate difference would then be partly a measurement of the hint rather
> than of the surface, which is the exact failure the pair convention exists to prevent.
> What remains is derivable from three facts the prompt already states: one asset stands
> behind all four barriers, the old door's behaviour must survive, and each gate's names
> are written on that gate. Deriving it is the task.

Notes 1-11 are the `-cpp` leg's, ported unchanged because the yard and the gates are
unchanged. Read them there in full; the summaries are here so this file is not a
dangling reference.

1. **"A barrier is open while ALL of the pads that answer for it are occupied."** The
   most likely submission: a one-line generalisation of the shipped ANY-pad rule that
   keeps the old door perfect (one pad, so all-of-one == any-of-one) and turns the gate
   into an AND. *Defense*: it reuses occupancy that counts ANY resting body, so it opens
   the gate when the character stands on one gate pad (`TheRunnerIsNotACrate`, phase 7)
   and when the un-named crate is parked on the contested pad
   (`TheGateStaysShutUntilBothItsCratesAreHome`, phase 5), and it never lights a lamp
   (`TheGateLampsNameTheCratesItHolds`).
2. **"The new requirement is about crates, so a pad is occupied when a crate is resting
   on it."** The brownfield failure the task is named for: narrow the shared occupancy
   where occupancy is computed, then add names and the two-of-two on top. Every gate
   about the *new* behaviour passes. *Defense*: the old door never opens again, because
   nobody ever puts a crate on its pad — `TheOldDoorStillOpensInsideItsBand` at cycle 3,
   against two baseline cycles measured earlier in the same run. **On this leg this note
   has a second, cheaper form** — see note 13.
3. **Reading the pair a gate is cut for once when play begins, and caching it** — or
   reading it out of the level in the editor and hard-coding it. *Defense*: `BeginPlay`
   fires on every placed actor **before** `PrepareTest`, and `PrepareTest` is where the
   fixture writes re-cut #0 over a *different* pair saved in the level, so both are
   wrong from the **first judged frame** (lamps at phase 3, panel at phase 4); two
   further mid-run re-cuts kill a cache refreshed once or on an event; and the lamps
   fail one dwell earlier than the panel in both cases.
4. **Recomputing only inside overlap begin/end handlers.** *Defense*: re-cut #2 changes
   the answer with no actor moving, no overlap beginning or ending and no contact state
   changing.
5. **Identifying the crates positionally** ("the near pad's crate is the first name") or
   by object pointer rather than by name. *Defense*: re-cut #1 puts the arch gate's
   FIRST name on the far pad and its SECOND on the near one, and at phase 13 one crate
   on one pad must light the arch gate's slot-1 lamp and the second gate's slot-0 lamp
   at the same instant.
6. **Latching the gate open on the first both-home moment.** *Defense*: four independent
   remove/re-add pairs across two crates and two re-cuts.
7. **Setting a correct internal flag and never touching a panel or a lamp.** *Defense*:
   nothing private is ever graded; the fixture reads four panels' live poses and four
   lamps' light intensity, and the barrier deliberately exposes no "is open" property.
8. **Driving the gate by moving a crate, or parking one on a pad from code.** *Defense*:
   `TheYardIsNotYoursToRewire` checks every crate's live location against the segment
   between its own two rail stops, every frame.
9. **Making the new rule apply to the barrier CLASS rather than to the barriers that are
   cut for names.** *Defense*: `TheDoorNobodyTouchesNeverMoves` on a matched twin
   3,000 cm away the drive never approaches; the preservation gate at cycles 3 and 4;
   and `TheSecondGateAnswersToItsOwnPair` at phase 4. **On this leg the class IS the
   deliverable**, so this is not a mistake an author can avoid by accident — see note 13.
10. **Solving it for THE gate** — locate one barrier that carries names (an iterator, a
    tag, the one that owns the lamps, a pointer cached in `BeginPlay`), compute "are
    both of its crates home", drive that one barrier and its two lamps. *Defense*: two
    gates, both cut for names, both carrying lamps, over one patch of floor;
    `TheSecondGateAnswersToItsOwnPair` at phases 5 and 17, the lamp gate one dwell
    earlier at phase 3, `TheGateRoseAgainAfterEveryRecut` at run level.
11. **One computed answer shared by both gates and all four lamps** — index the level's
    four lamps 0..3, or light each gate's lamps from whether that gate is open.
    *Defense*: at phase 3 the same near crate must light the arch gate's slot-0 lamp and
    the second gate's slot-1 lamp, and at phase 13 the reverse.

The rest are this leg's, and every one of them is a way to satisfy the *behaviour* while
failing the *surface* — or to fail the behaviour in a way only the Blueprint surface
makes available.

12. **Solving it in C++ and shipping a Blueprint beside it.** *Failure mode*: the
    surface-contract dodge. Note the sandbox does **not** stop it — `Source/ThirdPerson/`
    is path-legal on this substrate. It comes in two forms and **only one of them is
    covered**, which is stated here rather than glossed because a defence that does not
    exist is worse than none:
    - *A new native subclass of the barrier class.* **Covered.** L2I reproduces the
      fixture's own resolution and requires the **resolved** class to be
      Blueprint-generated, **and** sweeps for any native subclass of the placed class
      (scaffold exempt by exact `/Script/` path).
    - *An in-place edit of a shipped scaffold `.cpp`.* **NOT COVERED, and it is the
      cheaper of the two.** Overwrite
      `Source/ThirdPerson/Tasks/t3-…-cpp/YardBarrierActor.cpp` — which is precisely the
      shape of the committed `-cpp` reference — and ship an empty Blueprint subclass in
      the declared folder. All of L2I's checks pass (there is one Blueprint, it is
      Blueprint-generated, it is in the right folder, no *new* native class exists), the
      swapped Blueprint inherits the edited native `ShouldBeOpen_Implementation`, L2
      grades green on the C++ answer, and the report reads "Blueprint surface". Nothing
      in `tools/verify-single/` enforces "no C++ submitted": the runner does compute the
      accepted submission paths (`run_task.py:2288`) and already classifies compile
      inputs by extension for `--lite` (`:2300`), but that list is filtered to
      `Content/` packages before it reaches L2I (`layers/l2_introspect.py:409-410`), so
      the introspect script cannot see a submitted `.cpp` at all. Closing it needs a
      runner-side change, not a change here; see *What is NOT measured* and the
      unresolved list. Until then this is caught by the submission diff and human review
      of the deliverable, and **a green L2I on this leg does not mean "no C++ was
      written"** — the script's own header says so too.
13. **Overriding the yard's rule unconditionally.** *Failure mode*: **THE HEADLINE
    FAILURE OF THIS LEG, and the one the surface creates.** The agent delivers one
    Blueprint, overrides the rule with the two-of-two name test, and the fixture puts
    that same asset behind **all four barriers** — so the old door and the door nobody
    touches now answer a question about crate names that nothing will ever satisfy, and
    neither ever opens again. It is note 2's failure reached without touching occupancy
    at all, and it is *easier* to reach here than in C++, because the author is looking
    at one graph and not at four instances. *Defense*: `TheOldDoorStillOpensInsideItsBand`
    fails at **cycle 1**, before the character has ever touched a crate, with cycles 1
    and 2 being the explicit baseline pair — so this failure is reported against a
    measurement the same run was about to take, and it is the earliest FAIL any
    submission on this leg can produce. The correct answer branches on **what is written
    on the barrier being asked** and hands the unwritten case straight back to the
    inherited rule.
14. **Re-implementing the inherited ANY-pad rule by hand instead of calling the parent.**
    *Failure mode*: an author who branches correctly (note 13 avoided) but then rebuilds
    the shipped branch node-by-node — iterate my pads, ask each whether anything is
    resting on it. It is right the day it is written. *Defense*: it is a second copy of a
    rule that must not drift, it is exactly where an accidental ANY→ALL slip is
    introduced (note 1), and it costs nothing to avoid: overriding the yard's rule in a
    Blueprint exposes a call to the parent implementation, which *is* the shipped branch.
    Graded by note 1's gates rather than by a gate of its own, because the fixture judges
    behaviour and a faithful hand copy is not a failure — only an unfaithful one is.
15. **Narrowing occupancy in a Blueprint subclass of the pad, the crate or the lamp.**
    *Failure mode*: the Blueprint-surface form of note 2, and it fails in a way that is
    genuinely hard to see: the pads, crates and lamps are **placed** actors and this
    fixture's swap covers the **barrier** class only, so a Blueprint subclass of any of
    the other three is never instantiated and changes nothing at all. The submission
    then behaves exactly like the empty one and dies at phase 3, with an asset on disk
    that looks like the whole answer. *Defense*: L2I names it — a Blueprint deriving from
    a placed class the fixture does not swap is reported as a shadow asset rather than
    passing as "an asset exists".
16. **Shipping two Blueprints that derive from the barrier class.** *Failure mode*: a
    working answer plus an abandoned experiment, or one Blueprint per gate — the natural
    shape if the author has not registered that one asset stands behind all four
    barriers. *Defense*: `ResolveGradedBlueprintClass` raises `HARNESS-PRECONDITION`
    rather than picking one, so this is a **non-graded** exit 7 and not a FAIL. That is
    the correct outcome and it is also a cost: it burns a run and says nothing about the
    model. L2I asserts the count is exactly one, so a submission that would have gone
    this way is named structurally with a reason rather than as an ambiguity.
17. **Editing the delivered Blueprint's Class Defaults.** *Failure mode*: setting the
    pair of names, the open angle or the travel rate on the asset — reasonable-looking
    housekeeping, since the Blueprint editor shows those fields empty. It is fatal twice
    over: the class defaults apply to **all four** barriers, so writing a pair of names
    there hands both doors the new branch (note 13's failure by another road), and
    `TheYardIsNotYoursToRewire` pins the staged numbers and names on every frame. The
    same applies to unticking *Start with Tick Enabled*, which the yard's panel travel
    and the recipe's lamp pass both depend on. *Defense*: `TheYardIsNotYoursToRewire`
    and, for the names, the whole `TheGateAnswersToWhatItIsCutForRightNow` family.
18. **Reading the inherited pad and lamp lists in the Blueprint's own `BeginPlay`.**
    *Failure mode*: the correct-looking optimisation, and it silently yields nothing: the
    barrier's native `BeginPlay` calls `Super::BeginPlay()` **first**
    (`YardBarrierActor.cpp:123-125`), which is what fires a Blueprint's `Event
    BeginPlay`, and it fills the two lists **afterwards** (`:147-168`). A Blueprint that
    caches them there caches two empty arrays: the gate never opens, no lamp ever
    lights, and the old door never opens either. *Defense*: `TheOldDoorStillOpensInsideItsBand`
    at cycle 1 and `TheGateStaysShutUntilBothItsCratesAreHome` at phase 3 — but note the
    verdict is indistinguishable from an empty submission's, which is why this is written
    down here and stated twice in `REFERENCE-NOTE.md` rather than left to be discovered.

## Hidden invariants

Ported from the `-cpp` leg (read them there in full): the submission's own state is
never read, only its consequences; the fixture re-implements the resting predicate rather
than calling the pad's copy of it, because that copy is in the agent-writable module;
`GroundedBandUu` is disclosed in prose but not in figures and can only matter for an
airborne body the drive never produces; the preservation gate is free for the empty
submission and that is the nature of a preservation gate, not a dead gate; the old door's
side of the coupling is preservation, i.e. restraint rather than typing; the second gate
cost the drive no step, dwell or walking; what is constant across reps is the *sequence*
of pairs, not any pair a submission can see, and no `randomization:` key is declared
because the discrimination is in the re-staging and not in a seed; `fps_legs: [60, 20]`
runs the whole drive twice; and the supplied travel clears the band by 2.7x on purpose,
so the band is a contract on the submission's decision latency and never a race against
the supplied animation.

This leg's own, none of which is guessable from the `-cpp` spec:

- **THE SURFACE MECHANISM, recorded so the next reader does not re-derive it.**
  `ACraftBenchFunctionalTest` owns the lane, and it is one implementation rather than one
  copy per pair: `ResolveGradedBlueprintClass(UClass* PlacedClass)` returns the single
  Blueprint under `/Game/Tasks` (recursive, via the asset **registry**, because nothing
  in the map references a class the agent invented) whose `GeneratedClass` is a strict,
  non-abstract subclass of the placed class — `nullptr` means the C++ lane and TWO
  candidates raise HARNESS-PRECONDITION rather than picking one.
  `SwapForGradedBlueprint(AActor*)` spawns that class at the placed transform, carries
  the tags over and destroys the placed actor. `SwapAllForGradedBlueprint(TArray<AActor*>&)`
  does the same across every instance of one class, resolving **once** off the first
  entry and refusing a MIXED array. `SwapAllForGradedBlueprintRepossessing` adds
  re-possessing player 0 when the pawn it was driving was replaced. **This task uses
  `SwapAllForGradedBlueprint`** — four barriers, one supplied class, all-or-nothing —
  called from `ResolveYard` *before* the per-role tag lookups, because those would
  otherwise resolve the placed C++ instances and grade the wrong surface; the fixture
  then re-resolves by tag and re-checks the count rather than trusting the swap.
- **The swap carries the transform and the tags, and NOTHING ELSE.** Not per-instance
  property values, not inbound references from other actors. Everything in the banner
  follows from that one sentence, and any future placed-prop pair whose yard is wired
  instance-to-instance will hit it too.
- **One asset stands behind four barriers, and the prompt says so.** That is the surface
  half of the task's coupling and the reason note 13 exists. It is disclosed rather than
  hidden because it is a fact about how the answer is instantiated, not a failure mode:
  concealing it would make the preservation gate a trap instead of a requirement.
- **`ShouldBeOpen` became a `BlueprintNativeEvent` on 2026-08-20 and the C++ body moved
  to `ShouldBeOpen_Implementation`.** Call sites still read `ShouldBeOpen()`. Before that
  change the yard's rule was a bare virtual, invisible to Blueprint, and this leg was
  unwinnable — which is a broken task, not surface discrimination.
- **The Blueprint's `Event Tick` runs BEFORE the frame's decision, not after.** The
  barrier's native `Tick` opens with `Super::Tick(DeltaSeconds)`, which is what fires
  `Event Tick`, and only then resolves `bHasCommandThisTick ? bCommandedOpen :
  ShouldBeOpen()` (`YardBarrierActor.cpp:201-212`). Two consequences: a lamp pass written
  in `Event Tick` reads the same frame's world state the panel decision will read, and a
  `SetCommandedOpen` call made from `Event Tick` **is** consumed on that frame rather
  than the next.
- **`Event BeginPlay` fires BEFORE the pad and lamp lists exist.** The mirror image of
  the above, and the reason note 18 exists.
- **THE PAIR DIFF WAS AUDITED LINE BY LINE ON 2026-08-20, and what remains is a closed
  list.** Diffing each agent-visible H2 against the `-cpp` leg's, the only surviving
  differences are: (a) the surface-contract sentences at the head and tail of the prompt,
  which hard rule 1 puts there; (b) the one-asset-behind-four-barriers disclosure, argued
  for above; (c) the `-bp` `## Workspace state pre-task` being written as **behaviour
  prose** rather than as the `-cpp` leg's file-by-file C++ inventory — necessarily, since
  naming `AYardBarrierActor`, its specifiers and its headers to a Blueprint author is
  both a class-name disclosure this set forbids and useless to them; the exemplar
  (`bp/t1-screen-tint-bp`) does the same. Two things that were NOT
  differences by intent and were fixed: the five landmark distances the `-cpp` yard table
  discloses (400 cm stripes, the old door's pad at 300 cm, the arch gate's pads at 700 cm
  and 800 cm, the far stop at 900 cm) had been dropped in the rewrite and are restored —
  yard geography is surface-independent and the two legs' agents must not receive
  different amounts of it; and the paragraph that named `GetPadsAnsweringForMe()` /
  `GetMyLamps()` and `protected BlueprintReadOnly` in agent-visible prose is now stated in
  behaviour terms there, with the member table left here and in `REFERENCE-NOTE.md`.
  **Every gate value is identical on both legs** (100 cm, 1.20 s, 80 deg, 10 deg,
  720 deg/s, 3000 cm/s), as are `tier`, `substrate`, `fps_legs` and the fixture string.
- **The two C++ accessors are unreachable and the arrays behind them are not.**
  `GetPadsAnsweringForMe()` and `GetMyLamps()` are bare methods with no `UFUNCTION`;
  `Pads` and `Lamps` are `protected UPROPERTY(VisibleAnywhere, BlueprintReadOnly)`, which
  a Blueprint **subclass** may read. Every other member the behaviour needs is
  `BlueprintReadWrite`, `BlueprintReadOnly`, `BlueprintCallable`, `BlueprintPure` or
  `BlueprintNativeEvent` — the full table is in `REFERENCE-NOTE.md`. Nothing the
  behaviour needs is missing from the Blueprint surface.

