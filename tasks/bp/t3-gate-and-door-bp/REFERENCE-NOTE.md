# Reference recipe — `t3-gate-and-door-bp`

There is no script lane for Blueprint **graph** authoring in this repo (no
`BlueprintEditorLibrary` / `K2Node` precedent anywhere in `tools/` or `tasks/`), so this
asset is built in an attended editor session. This file is precise to the node and the
pin so it can be rebuilt without re-deriving the design.

Everything here is checked against the read-only C++ that ships with the task, and
against the `-cpp` leg's committed reference:

```
UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t3-gate-and-door-cpp/
    YardBarrierActor.h / .cpp      <- the class this Blueprint parents to
    YardPadActor.h                 <- the occupancy questions
    YardCrateActor.h               <- the crate's own name
    GateLampActor.h                <- the switch
UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchFunctionalTest.cpp:649-798
    ResolveGradedBlueprintClass / SwapAllForGradedBlueprint
tasks/cpp/t3-gate-and-door-cpp/reference/...YardBarrierActor.cpp
```

---

## ⛔ STOP: build this only with the blocker in view

**The Blueprint leg cannot be graded as of 2026-08-20 and it is the harness, not the
recipe, that is wrong.** The full account with line cites is the banner at the top of
`task.md`. In one paragraph: `SwapAllForGradedBlueprint` carries the placed actor's
**transform and tags and nothing else**, so on the Blueprint lane every barrier's
per-instance staged values are replaced by the delivered asset's class defaults (its
pair of names becomes `(None, None)`), and every *inbound* instance reference in the
yard — each pad's `AnsweredBarrier`, each lamp's `LampBarrier` — still points at the
destroyed placed barrier. Three fixture HARNESS-PRECONDITION exits fire before the first
judged frame, and even past those the stand-in's own `BeginPlay` finds no pads and no
lamps, so the old door can never open and a **correct** submission grades FAIL.

**Build the asset anyway if you want the recipe validated by hand in the editor** — every
node below is correct and reachable, and the graph is what the leg needs the day the
surface lane carries per-instance state. Do **not** run `cb discriminate`, `cb refgate` or
`cb eval` against this task until the swap fix lands: the run cannot say anything about
the submission.

**Two mechanical facts about that, because "do not run it" is prose and prose does not
stop a sweep.**

1. **There is one machine-readable stop, and it is in the L2I script.**
   `tools/verify-single/introspect/t3_gate_and_door_bp.py`
   carries `BLOCKED = True` and emits **no verdict block**, which the layer reports as
   status `error` and the runner turns into exit 7 / `harness-error` — non-graded, out of
   every pass-rate denominator. It is there so that a *partial* swap fix, one that
   repairs the fixture's staging checks but not the stand-in's spawn ordering, cannot
   stage cleanly and then grade this recipe FAIL. **Lift it in the same change that fixes
   the swap** — `BLOCKED = False`, one line — not before and not separately.
2. **Authoring the `.uasset` removes today's accidental safety net.** Right now
   `cb discriminate` stops cheaply on this id (`no reference solution … the PASS oracle
   is required`) and `cb refgate` / `cb bench --refgates` stop cheaply too (`no committed
   reference … cannot certify`) — though the latter aborts the *whole sweep* at this task
   under fail-verbatim-and-STOP semantics, so it is not free either. The moment a
   reference asset exists at
   `reference/Content/Tasks/t3-gate-and-door-bp/`, both of
   those cheap exits are gone and each command becomes a real run per `fps_leg` that can
   only ever return exit 7. If you build the asset for hand-validation and the swap fix
   has not landed, **do not commit it into `reference/`** — keep it out of tree, or land
   it together with the fix.

---

## What the Blueprint author can actually reach

Checked specifier by specifier. `BlueprintReadWrite` / `BlueprintReadOnly` /
`BlueprintCallable` / `BlueprintPure` / `BlueprintNativeEvent` are reachable; a bare
`virtual` or a bare `UPROPERTY()` is not.

### On the barrier — the class this Blueprint parents to

| member | specifier | so a Blueprint can |
|---|---|---|
| `ShouldBeOpen()` | `UFUNCTION(BlueprintNativeEvent)` **(as of 2026-08-20)** | **OVERRIDE the yard's rule** — the whole leg rests on this |
| `ShouldBeOpen_Implementation()` | the native body | be called as `Parent: Should Be Open` from the override |
| `CutForFirstName`, `CutForSecondName` | `EditAnywhere, BlueprintReadWrite` | read them — and must **NOT** write them |
| `OpenAngleDeg`, `TravelRateDegPerSec` | `EditAnywhere, BlueprintReadOnly` | read them (the graph never needs to) |
| `Pads` | `protected UPROPERTY(VisibleAnywhere, BlueprintReadOnly)` | read the array **from a subclass graph** |
| `Lamps` | `protected UPROPERTY(VisibleAnywhere, BlueprintReadOnly)` | read the array **from a subclass graph** |
| `SetCommandedOpen(bool)` | `UFUNCTION(BlueprintCallable)` | force the frame's answer (the fallback path, §6) |
| `GetPanelAngleFromShutDeg()`, `GetShutPanelYaw()` | `UFUNCTION(BlueprintPure)` | read the panel (the graph never needs to) |
| `Frame`…`CutPlate` (8 components) | `VisibleAnywhere, BlueprintReadOnly` | read them (the graph never needs to) |
| **`GetPadsAnsweringForMe()`** | **bare `const` method, no `UFUNCTION`** | **NOT REACHABLE** — use the `Pads` array |
| **`GetMyLamps()`** | **bare `const` method, no `UFUNCTION`** | **NOT REACHABLE** — use the `Lamps` array |
| `DrivePanel`, `UpdateReadouts` | `protected`, no `UFUNCTION` | NOT reachable (and never needed — the parent `Tick` does both) |
| `ShutPanelYaw`, `SweptAngleDeg`, `bHasCommandThisTick`, `bCommandedOpen`, `ShownCut` | `private`, no `UPROPERTY` | NOT reachable |
| `PrimaryActorTick.bCanEverTick` | **supplied `true`** in the constructor (`YardBarrierActor.cpp:35`) | have `Event Tick` fire at all |
| `AActor` | `Blueprintable` (`Actor.h:281`) | subclass it |

### On the pad

| member | specifier | so a Blueprint can |
|---|---|---|
| `IsBodyResting(const AActor*)` | `UFUNCTION(BlueprintPure)` | ask about ONE body — **the node this recipe uses** |
| `GetRestingBodies(TArray<AActor*>&)` | `UFUNCTION(BlueprintCallable, BlueprintPure=false)` | list everything resting (out-param, needs exec) |
| `HasAnyRestingBody()` | `UFUNCTION(BlueprintPure)` | ask the ANY question — **counts people; do not use it for a gate** |
| `GetPadCentre()` | `UFUNCTION(BlueprintPure)` | read the centre |
| `ContactRadiusUu`, `GroundedBandUu` | `EditAnywhere, BlueprintReadOnly` | read them |
| `AnsweredBarrier` | `EditInstanceOnly, BlueprintReadOnly` | read it (do not rely on it — see the blocker) |

### On the crate

| member | specifier | so a Blueprint can |
|---|---|---|
| `CrateName` | `EditAnywhere, BlueprintReadOnly` | read the name — **the identity the whole task turns on** |
| `RailLengthUu`, `ShoveSpeedUu`, `ShoveReachUu` | `EditAnywhere, BlueprintReadOnly` | read them (never needed) |
| `GetRailAnchor()`, `GetRailAxis()`, `GetRailParamUu()` | `UFUNCTION(BlueprintPure)` | read the rail (never needed) |
| `RailAnchor`, `RailAxis`, `ShownName` | `private`, no `UPROPERTY` | NOT reachable |

### On the lamp

| member | specifier | so a Blueprint can |
|---|---|---|
| `SetLit(bool)` | `UFUNCTION(BlueprintCallable)` | **throw the switch** — the only write path to a lamp |
| `IsLit()` | `UFUNCTION(BlueprintPure)` | read it back off the light |
| `NameSlot` | `EditAnywhere, BlueprintReadOnly` | read which slot this lamp stands for |
| `LampBarrier` | `EditInstanceOnly, BlueprintReadOnly` | read it (do not rely on it — see the blocker) |
| `LitIntensity`, `LitLook`, `DarkLook` | `BlueprintReadOnly` | read them (never needed) |

**Verdict: nothing the behaviour needs is unreachable from Blueprint.** The rule is
overridable, the switch is callable, the crate names are readable, the pair is readable,
and both per-instance lists are readable from a subclass. The leg is winnable at the
*asset* level. It is blocked at the *harness* level, which is a different repair in a
different file.

---

## 1. The assets

**One Blueprint. Nothing else.** Not one per gate — see §5, do-not #3.

| what | path | parent class |
|---|---|---|
| the answer | `/Game/Tasks/t3-gate-and-door-bp/BP_YardBarrier` | `YardBarrierActor` |

**Class Defaults: change nothing.** Leave `CutForFirstName` and `CutForSecondName`
**empty**, leave `OpenAngleDeg` at 90 and `TravelRateDegPerSec` at 180, and leave *Start
with Tick Enabled* ticked. This asset stands behind all four barriers, so a class default
is a value written on the old door as much as on the gate. See §5, do-not #4.

The folder name matters: `ResolveGradedBlueprintClass` filters the asset registry to
`/Game/Tasks` **recursively** and takes the single Blueprint whose `GeneratedClass` is a
strict subclass of the placed class. A second such Blueprint anywhere under `/Game/Tasks`
is `HARNESS-PRECONDITION`, not a verdict.

**This Blueprint has no `Event BeginPlay` and needs none.** That is deliberate and it is
the single most important structural property of the recipe: the parent's `BeginPlay`
calls `Super::BeginPlay()` **first** — which is what fires a Blueprint's `Event BeginPlay`
— and fills `Pads` and `Lamps` only **afterwards** (`YardBarrierActor.cpp:123-125` then
`:147-168`). Anything cached in `Event BeginPlay` from those two arrays is cached empty.
Every graph below reads them at the point of use instead.

---

## 2. Graph A — the override of the yard's rule

Create it from **My Blueprint → Functions → Override → Should Be Open**. UE generates a
**function** (not an event) because the signature returns `bool`, so it has exec pins and
a Return Node, and it is flagged **const** because the C++ declaration is `const`.

Right-click the function's entry node → **Add Call to Parent Function** to get the
`Parent: Should Be Open` node. That node *is* the shipped ANY-pad rule. Do not rebuild it
(§5, do-not #2).

Add a **second Return Node** (right-click → Add Return Node); a function graph may carry
more than one, which is what lets the two branches return different things with no local
variable and no `Set`.

```
[Should Be Open]  (function entry, const, returns bool)
   |
   | ---- the "is a pair written on ME" test, all pure, no exec ----
   |   [Get Cut For First Name] --A--> [Not Equal (Name)]  B pin LEFT BLANK  --+
   |                                                                          +--> [OR Boolean] --+
   |   [Get Cut For Second Name] -A--> [Not Equal (Name)]  B pin LEFT BLANK --+                   |
   |                                                                                              |
   v                                                                                              v
[Branch]  Condition <-----------------------------------------------------------------------------+
   |
   |-- False (nothing is written on this barrier: it is a DOOR) -->
   |        [Parent: Should Be Open]
   |             exec ----> [Return Node #1]
   |             Return Value ----> Return Node #1 . Return Value
   |
   `-- True (a pair IS written on this barrier: it is a GATE) -->
            [Is Named Crate Home]   Wanted Name <-- [Get Cut For First Name]
                 exec ----v                                     Return Value --+
            [Is Named Crate Home]   Wanted Name <-- [Get Cut For Second Name]   |
                 exec ----v                                     Return Value --+--> [AND Boolean]
            [Return Node #2]   Return Value <----------------------------------------------+
```

Pin-level notes:

- **`Not Equal (Name)` with the B pin left blank** is how you test "is this slot empty".
  A blank `Name` literal pin is `NAME_None`, so the node reads *is this slot written on*.
  `Not Equal (Name)` (`KismetMathLibrary::NotEqual_NameName`) is pure and always present;
  do not go looking for an `Is None` node and do not convert to `String` first (§5,
  do-not #9).
- **`OR`, not `AND`,** across the two slots. A barrier is a gate if *anything* is written
  on it. This mirrors `IsCutForNames()` in the `-cpp` reference exactly
  (`return !CutForFirstName.IsNone() || !CutForSecondName.IsNone();`). With `AND`, a gate
  the foreman half-cuts falls back to the yard's ANY-body rule and swings open on the
  first crate.
- **Read `Cut For First Name` / `Cut For Second Name` fresh, here, every call.** Three of
  the run's discriminating moments are re-cuts, one of them with nothing in the yard
  moving. Do not promote either to a local variable outside the graph, do not cache them,
  do not read them in `Event Tick` and pass them in.
- **The two `Is Named Crate Home` calls are sequenced on exec** because the function is
  impure. Their order does not matter; both must be evaluated (`AND Boolean` takes both
  Return Values). Do not "optimise" by short-circuiting through a second Branch — it
  gains nothing and it is where a wrong-slot bug gets introduced.
- **Nothing in this graph writes anything.** It is a question. The panel is driven by the
  parent `Tick`, which calls this (`YardBarrierActor.cpp:207`).

---

## 3. Graph B — `Is Named Crate Home`

A new Blueprint **Function** on the same Blueprint.

- **Input**: `Wanted Name`, type `Name`.
- **Output**: `Return Value`, type `Boolean`.
- **Details panel**: **Const = CHECKED**, **Pure = unchecked**. Const is not cosmetic:
  Graph A is a const function, and a const graph may only call functions that are
  themselves const. Leave it unticked and Graph A will not compile.
- Sets no variables of any kind — which is also what lets it be const.

```
[Is Named Crate Home]  (Wanted Name : Name)
   |
   |  [Get Wanted Name] --A--> [Not Equal (Name)]  B pin LEFT BLANK --+
   v                                                                 v
[Branch]  Condition <--------------------------------------------------+
   |
   |-- False (asked about nobody) --> [Return Node #1]   Return Value pin LEFT UNWIRED (= false)
   |
   `-- True -->
       [Get All Actors Of Class]   Actor Class = YardCrateActor
            Out Actors --> [For Each Loop]  (call it CRATE LOOP)
                 |
                 Loop Body -->
                     [Cast To YardCrateActor]  Object <-- CRATE LOOP . Array Element
                        |  Cast Failed --> (unwired)
                        v  (succeeded)
                     [Get Crate Name]  Target <-- As Yard Crate Actor
                        |  Return Value --A--> [Equal (Name)]  B <-- [Get Wanted Name]
                        v
                     [Branch]  Condition <-- Equal (Name)
                        |-- False --> (unwired: next crate)
                        `-- True -->
                              [Get Pads]   (the INHERITED array)
                                 --> [For Each Loop]  (call it PAD LOOP)
                                        Loop Body -->
                                           [Is Valid]  Input Object <-- PAD LOOP . Array Element
                                              Is Valid -->
                                                 [Is Body Resting]        (pure)
                                                    Target <-- PAD LOOP . Array Element
                                                    Body   <-- As Yard Crate Actor
                                                    --> [Branch]
                                                          |-- True --> [Return Node #2]  Return Value = TRUE (checked)
                                                          `-- False --> (unwired: next pad)
                                              Is Not Valid --> (unwired)
                                        Completed --> (unwired: next crate)
                 Completed --> [Return Node #1]      (falls through to false)
```

Pin-level notes, each of which is a way to get it subtly wrong:

- **`Get Pads`, never `Get All Actors Of Class → YardPadActor`.** `Pads` is *this*
  barrier's own pads, resolved by the parent from what each pad says it answers for. A
  level-wide pad list makes both gates and both doors read the same six pads, so the old
  door opens whenever anybody stands anywhere and the two gates can never disagree —
  three named gates at once. (`Get All Actors Of Class` for **crates** is fine and is what
  this graph does: the yard's three crates are shared by every barrier, and there is no
  per-instance crate list to read.)
- **`Is Body Resting`, not `Has Any Resting Body`.** `Has Any Resting Body` is the yard's
  own ANY question and it counts **people**. Asking it here is `TheRunnerIsNotACrate` at
  phase 7, and it is the most likely single-node slip on this leg.
- **`Is Body Resting` is asked per pad, with the crate as the `Body`.** It is `BlueprintPure`,
  so it needs no exec wire — drop it straight into the Branch condition. Do not
  reimplement it from `GetPadCentre` + `ContactRadiusUu` + a distance: the fixture applies
  its own copy of that predicate and a hand-rolled one that differs by a unit is a wrong
  answer you cannot see.
- **The `Equal (Name)` compares the crate's live `CrateName` against `Wanted Name`.**
  Nothing here may compare against a literal typed into a pin: the pair is re-cut three
  times and the names are only ever legible off the things themselves.
- **The `Cast To YardCrateActor` is bookkeeping, not the identity test.**
  `Get All Actors Of Class` already returns only crates; the cast exists so the
  `Get Crate Name` node has a typed target. Wire `Cast Failed` to nothing.
- **The early-out on `Wanted Name` being blank is load-bearing.** A door is asked about
  nothing (Graph A never reaches here for a door, but a **half-cut gate** is asked about
  one written name and one blank one). Without the guard, "is a crate called *nothing*
  resting on my pads" would be answered by whatever `Equal (Name)` does with two blanks
  and could return **true** — which opens a half-cut gate on a single crate.
- **Return Node #1's `Return Value` pin is deliberately left unwired**, which is `false`.
  Both false paths (asked about nobody; the crate loop ran out) share it.

### If the editor refuses the const call

Some engine versions are stricter than others about what a const function graph may
invoke. If UE rejects `Is Named Crate Home` inside Graph A, do **not** untick Const on
Graph B and do **not** rewrite Graph A — inline the body. Duplicate the crate-loop /
pad-loop stack into Graph A twice, once per slot, reading `Cut For First Name` in the
first copy and `Cut For Second Name` in the second, and route both `true` paths into an
`AND` fed by two local... **no.** A const graph cannot set locals reliably either. Use §6
instead: move the whole decision to `Event Tick` and `SetCommandedOpen`, which is a
first-class supplied path with no const involvement at all.

---

## 4. Graph C — the lamps, in `Event Tick`

The parent `Tick` drives the panel and the readouts and **never touches a lamp**
(`YardBarrierActor.cpp:201-212`, and the `-cpp` reference had to add its own `DriveLamps`
for exactly this reason). So the lamp pass is the Blueprint's, and `Event Tick` is where
it goes.

`Event Tick` fires from inside `Super::Tick(DeltaSeconds)` at the **top** of the parent's
`Tick`, i.e. *before* the frame's panel decision — so this pass and the panel are reading
the same frame's world.

```
[Event Tick]
   |
   v
[Get Lamps]   (the INHERITED array)
   --> [For Each Loop]  (LAMP LOOP)
          Loop Body -->
             [Is Valid]   Input Object <-- LAMP LOOP . Array Element
                Is Valid -->
                   [Get Name Slot]  Target <-- LAMP LOOP . Array Element
                      Return Value --A--> [Equal (integer)]  B = 0
                                                  |
                   [Select]   (Name)               |
                      Option True  <-- [Get Cut For First Name]
                      Option False <-- [Get Cut For Second Name]
                      Index/Pick A <-----------------+
                      Return Value --+
                                     v
                   [Is Named Crate Home]   Wanted Name <-- Select . Return Value
                      Return Value --+
                                     v
                   [Set Lit]   Target <-- LAMP LOOP . Array Element
                               bLit   <-- Is Named Crate Home . Return Value
                Is Not Valid --> (unwired)
          Completed --> (unwired)
```

Pin-level notes:

- **`Get Lamps`, never `Get All Actors Of Class → GateLampActor`.** `Lamps` is *this*
  barrier's own lamps. The level's four lamps indexed 0..3 is anti-gaming note 11: at
  phase 3 the near crate must light the **arch** gate's slot-0 lamp and the **second**
  gate's slot-1 lamp at the same instant, so a global slot index is wrong in both
  directions.
- **`Get Name Slot` off the lamp, and select the barrier's own name for that slot.** Never
  the reverse (do not decide a lamp's name from where a crate is standing) and never a
  fixed order — `Get My Lamps` returns them "in whatever order the level hands them over"
  and the array is unsorted, so `Lamps[0]` is **not** slot 0.
- **`Set Lit` takes the answer for that slot's name, NOT whether the panel is open.**
  Driving lamps from "am I open" fails at every single-crate dwell: exactly one lamp must
  burn while the panel stays shut. This is the most common wrong wire on this graph and it
  is one pin away from correct.
- **No `Is Cut For Names` guard is needed here.** A door's `Lamps` array is empty, so the
  loop no-ops; and if a door ever carried a lamp, both its names are blank, `Is Named
  Crate Home` early-outs false, and the lamp is set dark — which is the right answer.
- **Do not put this pass inside Graph A.** Two reasons, both fatal: Graph A is const (it
  may not call `Set Lit`), and Graph A is only called on a frame where nobody used
  `SetCommandedOpen` (`YardBarrierActor.cpp:207`), so a lamp pass hidden in it would
  silently stop running the moment anything commanded the barrier.
- **Do not use a Timer instead of `Event Tick`.** A timer decouples the update from the
  frame the fixture samples and can drift outside the 1.20 s band; and the whole task's
  hardest moment (re-cut #2) is a change with nothing in the world moving, which no
  event-driven refresh sees at all.

---

## 5. Every way to get this subtly wrong

Read alongside `task.md`'s *Anti-gaming notes* and the `-cpp` reference's own comments.
Each entry is a **do not do this**, with the reason and, where there is one, the gate.

1. **Do not override the rule unconditionally — do not omit the Branch in Graph A.**
   THE HEADLINE. This one asset stands behind **all four** barriers
   (`SwapAllForGradedBlueprint`, four instances of one supplied class, all-or-nothing).
   An override with no `Is Cut For Names` branch hands the two-of-two crate-name test to
   the old door and to the door nobody touches, neither of which will ever have a crate
   on its pad, so neither ever opens again. `TheOldDoorStillOpensInsideItsBand` fails at
   **cycle 1** — before the character has touched a crate — and cycles 1 and 2 are the
   baseline pair the same run was about to record. In C++ this is a mistake you can talk
   yourself out of; here it is the default shape of the graph, and avoiding it is the
   task.
2. **Do not rebuild the ANY-pad rule by hand — use `Parent: Should Be Open`.** A hand
   copy (`For Each Pads → Has Any Resting Body → return true`) is right the day it is
   written and is a second copy of a rule that must not drift. It is also exactly where
   ANY silently becomes ALL — anti-gaming note 1, the most likely submission on either
   leg, which keeps the old door perfect and lets a person standing on a gate pad, or the
   un-named crate, swing a gate wide (`TheRunnerIsNotACrate` phase 7,
   `TheGateStaysShutUntilBothItsCratesAreHome` phase 5).
3. **Do not ship two Blueprints deriving from the barrier class.** Not one per gate, not
   a working one plus an experiment. `ResolveGradedBlueprintClass` raises
   `HARNESS-PRECONDITION` rather than picking one, so the run exits **non-graded** (exit
   7) and says nothing about anything. One asset, four barriers, the branch does the
   separating.
4. **Do not touch Class Defaults.** Writing `CutForFirstName` / `CutForSecondName` on the
   asset writes them on the old door too, which is do-not #1 by another road; and
   `TheYardIsNotYoursToRewire` pins every staged number and name on every frame. Do not
   change `OpenAngleDeg` or `TravelRateDegPerSec`, and do not untick *Start with Tick
   Enabled* — the panel travel and the whole lamp pass depend on it.
5. **Do not write `Cut For First Name` / `Cut For Second Name` from the graph.** They are
   `BlueprintReadWrite`, so the editor will happily give you a `Set` node. The foreman's
   re-cut is his to make: `TheYardIsNotYoursToRewire` compares both slots, every frame,
   against **what the fixture itself last wrote**, and the check is suspended only inside
   the fixture's own two mid-run re-cut windows.
6. **Do not read `Pads` or `Lamps` in `Event BeginPlay`.** The parent's `BeginPlay` calls
   `Super::BeginPlay()` first (which is what fires yours) and fills the arrays afterwards
   (`YardBarrierActor.cpp:123-125`, `:147-168`), so you cache two empty arrays: the gate
   never opens, no lamp ever lights, and the old door never opens either. The failure is
   **indistinguishable from an empty submission**, which is why this recipe has no
   `Event BeginPlay` at all.
7. **Do not cache the pair of names anywhere, or for any length of time.** Re-cut #0 lands
   in `PrepareTest`, which runs *after* every placed actor's `BeginPlay` and writes a pair
   the level was **not** saved holding — so a `BeginPlay` snapshot, and equally a pair read
   off the level in the editor and typed into a pin, is wrong from the **first judged
   frame** (lamps at phase 3, panel at phase 4). Two more re-cuts move it mid-run, the
   second with nothing in the yard moving. Read both slots inside Graph A and inside
   Graph C, every time.
8. **Do not drive any of this off overlap events.** `On Actor Begin/End Overlap` on the
   pad's volume is idiomatic, cheap and correct for every crate movement in the run — and
   re-cut #2 changes the correct answer with **no actor moving, no overlap beginning or
   ending and no contact state changing**. `TheGateAnswersToWhatItIsCutForRightNow` owns
   that moment and `TheGateRoseAgainAfterEveryRecut` names it again at run level. (The
   pad's volume "notices what is near and blocks nothing"; occupancy is answered by
   measurement precisely so the answer is the same whether it is asked once or every
   frame.)
9. **Do not compare names as strings.** `Conv_NameToString` → `Equal (String)` invites a
   case-sensitivity difference and a `None`-vs-`""` difference against the fixture's
   `FName` comparison. Use `Equal (Name)` / `Not Equal (Name)` throughout, and test
   "written" with a **blank B pin** rather than a typed `"None"`.
10. **Do not identify a crate by where it is standing, or by which object it is.** "The
    near pad's crate is the first name" is correct until re-cut #1, which puts the arch
    gate's FIRST name on the **far** pad and its SECOND on the **near** one; the panel is
    unaffected (both are still home) so only the lamps say so, at phases 13-14. And at
    phase 13 one crate on one pad must light the arch gate's slot-1 lamp and the second
    gate's slot-0 lamp *at the same instant*, so no rule about position can produce both.
11. **Do not latch.** No "has been open" bool, no Do-Once, no Gate node holding the
    answer. Four independent remove/re-add pairs across two crates and two re-cuts
    (`TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack`).
12. **Do not compute one answer for the yard and hand it to everything.** No
    `Get All Actors Of Class → YardBarrierActor` loop, no Game Instance / Game State /
    Blueprint-Function-Library singleton holding "which crates are home", no answer
    computed once and shared. The crate *list* is genuinely shared (the two gates' pads
    are painted on one patch of floor); the **pairs** are not.
    `TheSecondGateAnswersToItsOwnPair` names it at phase 5 (the second gate open while the
    arch gate is shut) and at phase 17 (one falls while the other rises, nothing moving);
    `TheDoorNobodyTouchesNeverMoves` names any level-wide driver from the first frame to
    the last.
13. **Do not set a variable and forget the output.** Nothing private is graded. The gates
    read four panels' live poses and four lamps' light **intensity**; the barrier
    deliberately exposes no "is open" property of its own.
14. **Do not move anything.** No `Set Actor Location` on a crate, no teleport onto a pad,
    no nudge. `TheYardIsNotYoursToRewire` checks every crate's live location against the
    segment between its own two rail stops, every frame — the fixture's model reads live
    transforms, so a moved crate would otherwise make the model agree with itself.
15. **Do not subclass the pad, the crate or the lamp in Blueprint.** This fixture's swap
    covers the **barrier** class only, so a Blueprint subclass of any of the other three
    is never instantiated and changes nothing at all — the submission behaves exactly like
    the empty one while carrying an asset that looks like the whole answer. (This is the
    Blueprint form of the brownfield failure: narrowing the pad's occupancy to crates
    would fix the gates and kill the old door in C++; in Blueprint it does not even run.)
    L2I reports it as a shadow asset.
16. **Do not add or modify a C++ file.** `Source/ThirdPerson/` is *path-legal* on this
    substrate, so the sandbox will not stop you; L2I will. It reproduces the fixture's own
    resolution and requires the resolved class to be **Blueprint-generated**, and sweeps
    for any native subclass of the placed class (the scaffold is exempt by exact
    `/Script/` path, never by name). A C++ answer with a decorative Blueprint beside it
    fails the surface contract instead of passing both legs.
17. **Do not file the asset outside the declared folder.** The fixture's resolver scans all
    of `/Game/Tasks` recursively, so a misfiled Blueprint would still be graded — which is
    precisely why L2I checks the folder separately from the count, so a misfiled answer
    reads as misfiled rather than as missing.
18. **Do not use `AND` where §2 says `OR`, and do not use `Lamps[0]` as slot 0.** Both are
    one-token slips with no visible symptom on the arch gate and a named failure
    elsewhere: `AND` makes a half-cut gate fall back to the yard's ANY-body rule, and the
    lamp array is unsorted so index-as-slot is a coin flip that
    `TheGateLampsNameTheCratesItHolds` calls at phase 3.

---

## 6. The documented fallback: `Event Tick` + `SetCommandedOpen`

Use this **only** if the editor refuses the const call in §3, and record which path the
reference took. It is a first-class supplied route, not a hack:
`SetCommandedOpen(bool)` is `BlueprintCallable` and documented as "an override anyone may
call from anywhere: the most recent call within a frame is what the barrier holds for that
frame, and with no call the yard's own rule decides. **The barrier never asks who
called.**"

The ordering works out, and this is the non-obvious part: `Event Tick` fires from inside
`Super::Tick(DeltaSeconds)` at the **top** of the parent's `Tick`, and the parent then
reads `bHasCommandThisTick ? bCommandedOpen : ShouldBeOpen()` on the same line
(`YardBarrierActor.cpp:203-208`). So a command issued from `Event Tick` **is consumed on
that frame**, not the next, and costs no latency against the 1.20 s band.

```
[Event Tick]
   |
   v
[Branch]  Condition <-- (the same OR-of-two-Not-Equals test as §2)
   |
   |-- False (a door) --> (nothing: NEVER call SetCommandedOpen, so the yard's own
   |                       rule decides and the old door behaves exactly as shipped)
   |
   `-- True (a gate) -->
        [Is Named Crate Home]  Wanted Name <-- [Get Cut For First Name]  --+
        [Is Named Crate Home]  Wanted Name <-- [Get Cut For Second Name] --+--> [AND Boolean]
        [Set Commanded Open]   Target = self,  bOpen <-------------------------------+
   |
   `-- then the lamp pass of §4, unchanged
```

Two things this path must get right, and both are easy to miss:

- **Never call `SetCommandedOpen` on a barrier that is cut for nothing** — not even with
  the value the yard's rule would have produced. Calling it at all takes the decision away
  from the shipped rule, so any bug in your copy of it becomes the old door's bug. The
  `False` branch must be empty.
- **It must be called EVERY frame while the barrier is a gate.** The command is one frame
  only (`bHasCommandThisTick = false` immediately after it is read), so a command issued
  on a change and not repeated hands the frame back to the yard's ANY-body rule and the
  gate flickers open on a single crate.

On this path Graph A is not overridden at all, and `Is Named Crate Home` can be left
non-const. Everything in §5 still applies verbatim.

---

## 7. Saving it out

Author it in the substrate project so the parent class resolves, then copy the `.uasset`
into the task folder — the reference tree mirrors the deliverable root:

```
tasks/bp/t3-gate-and-door-bp/reference/
  Content/Tasks/t3-gate-and-door-bp/BP_YardBarrier.uasset
```

Do **not** copy the reference over the substrate's own `Content/` and leave it there: a
reference that lives inside the substrate tree makes an EMPTY submission pass, and it is a
`tasklint` ERROR.

---

## 8. After it exists

**In this order, and not before the swap blocker is fixed.**

1. Confirm the surface lane carries per-instance state — the fixture must get past
   `OldDoorYardFunctionalTest.cpp:600` (lamp→gate), `:645` (pad→barrier) and `:1312`
   (`PairIsOpenable` on the level pair) on the Blueprint lane. Until then every run is a
   non-graded exit 7 and proves nothing about the asset.
2. `cb discriminate --task t3-gate-and-door-bp` — reference must
   PASS, empty must FAIL, **on both `fps_legs`**. Empty here means no Blueprint at all, in
   which case the swap is a no-op, the fixture grades the placed C++ scaffolds, and the
   yard's over-permissive ANY-body rule swings both gates open on the first crate at
   phase 3 (`TheGateStaysShutUntilBothItsCratesAreHome`).
3. Re-discriminate `t3-gate-and-door-cpp` as well. The two legs
   share one fixture and one map; a change that fixes this leg and breaks that one is a net
   loss and grading both is the only way to see it. Note the swap fix touches
   `ACraftBenchFunctionalTest`, which is the **verifier tree** — so it invalidates every
   refgate certificate on the box, not just this pair's.
4. Add this fixture's `::Error` sites to the internal design note (not shipped) if the `-cpp` leg
   has not already done it, and re-tighten the t = 900 s sentinel once both legs report a
   measured `[t3-olddooryard] run complete at t=`.
5. The owner has to **play** it (2026-08-18 directive). Same map as the C++ leg, so the
   play project already carries the yard; what has never been played is a yard whose four
   barriers are all this Blueprint.

---

**Nothing in this file has been run.** It is derived from the `-cpp` reference, the
shipped headers and the shipped fixture, and every value it depends on is either disclosed
in the prompt or read off the world. The first graded run is what makes any of it true —
and as of 2026-08-20 there cannot be one.

---

## AS BUILT 2026-08-23 — and the STOP banner above is now stale

The asset exists: `BP_YardBarrier` with all three graphs, compiling clean, each
graph read back and checked clause by clause against this file.

**The `⛔ STOP` block at the top no longer applies, and neither do the four
blockers in `task.md`.** Every one of them rested on `SwapAllForGradedBlueprint`
carrying "the transform and tags and nothing else". The banner even spelled out
the fix it was waiting for — copy the placed instance's editable UPROPERTY values
onto the stand-in, re-point every inbound `AActor*` in the world, and do both
BEFORE the stand-in's `BeginPlay` via a deferred spawn. That is exactly what the
surface lane now does (`SpawnStandInFor` ->
`CopyPropertiesForUnrelatedObjects`, then `RepointReferencesTo`, then
`FinishStandIn`). So the lamps keep their gate, the pads keep their barrier, the
gates keep their staged pair, and the stand-in's own `BeginPlay` sees a repaired
yard.

Nothing in the graph section below was changed. It is buildable and was built as
written.

**Not yet graded.** The asset compiling is not the leg discriminating; that still
needs `cb discriminate --task <id>` on a quiet machine, and per the note in
`REFERENCE-NOTE` of the pair's other leg, `--keep` is unusable here because the
task id is long enough to push UBT past the Windows 260-character path limit.
