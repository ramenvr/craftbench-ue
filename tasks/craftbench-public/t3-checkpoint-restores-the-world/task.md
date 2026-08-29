---
id: t3-checkpoint-restores-the-world
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_CheckpointYard :: ACheckpointRestoreFunctionalTest"]
fps_legs: [60, 20]
---

# t3-checkpoint-restores-the-world

A yard of latching doors, takeable coins and a two-number counter. Dying sends
you back to the pad you last stood on and rolls the world back to the moment
that pad was armed — except that progress already carried over the line is never
given back. The rules are all in the prompt; what is hard is building the four
pieces so they agree: a per-coin **three-way** ledger, a snapshot taken at
**every** mark, a restore that intersects the two, and a CARRIED that is
**derived** from the answer instead of restored from the snapshot.

Three lives end on hot floor at three different points in one walk, and the
correct answer is a different world at each of them.

## Primary concept

- `checkpoint-state-restore` — an actor deciding what a saved moment means for a
  world that has moved on since
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine)

The load-bearing behaviour is **reconciling a remembered world with an
irreversible one**. The grade never asks *how*: a struct of arrays, a TMap, or
five little state machines all pass identically.

## Composed concepts

1. `actor-event-delegates` — the yard's props announce (a pad stood on, a line
   crossed, hot floor touched) and act on nothing.
2. `per-instance-state-ledger` — the submission has to hold a **three-way**
   place per coin, because "taken" and "banked" are the same picture from the
   outside and only one of them ever comes back.
3. `snapshot-and-restore` — the remembered moment is re-taken at every mark, not
   once, and it holds doors, coin places and nothing else.
4. `derived-vs-restored-quantity` — CARRIED is a **consequence** of where the
   coins ended up; BANKED is never written at all.
5. `player-relocation` — putting the character back somewhere they can carry on
   walking from.

These interact: the restore's coin loop needs the ledger; the ledger's
`over-the-line` state can only be written at the instant the line is crossed;
and CARRIED can only be computed after the coin loop has run. Getting any one of
them right in isolation is a T1; getting them to agree is the task.

## Prompt given to the agent

> The yard has checkpoint pads, sliding doors with floor plates, coins on stands,
> a counter with a line painted in front of it, and hot floor. All of it works
> and none of it is yours to change. A plate opens its door and the door stays
> open; nothing shuts it again. Walking over a coin's stand picks the coin up.
> The counter shows CARRIED, what is in your hands, and BANKED, what you have
> carried over the line; crossing the line moves everything in hand into BANKED.
> Hot floor ends a life. Nothing here decides what happens next. That is your
> job, and one empty piece is already placed for you to write.
>
> **The mark.** Standing on a pad makes it the mark, and it stays lit while it
> is; at most one pad is ever lit. The mark is simply the pad stood on most
> recently. The pads are numbered by depth into the yard and that numbering has
> nothing to do with it: the course doubles back. Standing on a pad does nothing
> else — no door moves, no coin is touched, nothing is banked. Before anybody has
> stood on a pad the mark is the spot they walked in from, and the moment that
> mark was set is the moment the yard opened.
>
> **Coming back.** When a life ends, within a second the character is standing at
> the mark and the yard is back to how it was when that mark was set — not how it
> was when the yard opened. A door open then stays open; a door opened since
> shuts again, properly, so its plate opens it once more. A coin on its stand
> then is back on its stand; a coin already in hand then is still in hand. What
> has gone over the line is gone for good: BANKED never changes at a death or at
> a mark, only crossing the line moves it, by exactly what was in hand, and a
> banked coin never returns to a stand or a hand. CARRIED always says how many
> coins are in hand. Afterwards a door put back must open again from its plate, a
> coin put back must be pickable again and picking it up must move CARRIED, and
> the character must be able to walk on under their own steam.
>
> How many of each there are, where they stand and what the counter already reads
> are things to read off the world; none of it is written down here. Do not edit
> the level, any config file, or any test file. Write your solution in C++ under
> `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-checkpoint-restores-the-world/CheckpointYardProps.h` / `.cpp` — the
  yard, supplied and working. Five classes, none of which knows that checkpoints
  exist. Each announces what happened to it and does nothing about it.

  | Class | Tag | What it does | What it deliberately does NOT do |
  |---|---|---|---|
  | `ACheckpointStandActor` | `CheckpointStand` | pad slab + volume + lamp; `EditAnywhere int32 StandOrder`; `SetArmed(bool)` / `IsArmed()`; `GetRespawnTransform()` — clear of the slab, facing the way the pad faces; multicast `OnStoodOn(ACheckpointStandActor*)` | decide which pad is current; light itself; put another pad out; remember anything |
  | `ALatchDoorActor` | `LatchDoor` | leaf + plate + plate volume; `EditAnywhere FName DoorId`, `float OpenSlideUu`, `FVector PlateOffsetUu`; `SetOpen(bool)` moves the leaf between two fixed places in one step **and sets the latch**; `IsOpen()`; `GetLeafShutLocation()` / `GetLeafOpenLocation()` in world space | shut itself. Its plate handler early-returns while the door is already open, so a leaf moved back by hand leaves the latch set and that door never opens again |
  | `ACoinPickupActor` | `CoinPickup` | stand + coin mesh + volume; `EditAnywhere FName CoinId`; `Collect()` hides the coin **and adds one to CARRIED**; `Restore()` un-hides it; `IsCollected()` | `Restore()` touches the counter. What CARRIED should read after a restore is not the coin's business |
  | `ABankCounterActor` | `BankCounter` | post + line volume + two `UTextRenderComponent` faces showing the bare numbers; `EditAnywhere int32 StartingBanked` applied at BeginPlay; `GetCarried()`/`GetBanked()`/`SetCarried()`/`SetBanked()`, both writers refreshing the faces; multicast `OnBanked(int32 Amount, int32 NewBanked)` fired the instant the line is crossed with something in hand | have any opinion about when a write is right |
  | `AHazardStripActor` | `HazardStrip` | flat non-blocking hot floor over a query-only volume; multicast `OnLethalTouch(AActor* Victim)` | move anybody; put anything back |

- `Tasks/t3-checkpoint-restores-the-world/CheckpointDirectorActor.h` / `.cpp` —
  **the one empty piece**, tagged `CheckpointDirector`. A bare `AActor` with a
  scene root, an empty `BeginPlay`, no tick, no timer, no reference to any prop
  and no state. **The answer has to land on THIS class**: every prop and the
  director are placed instances in a map the agent cannot edit, so a subclass
  would never be instantiated.
- `Content/Maps/t3-checkpoint-restores-the-world/L_CheckpointYard.umap` — the
  staged yard, committed binary. World Settings name NO game mode, so the level
  inherits `BP_ThirdPersonGameMode` and both halves of Enhanced Input survive.
  What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 10,600 x 8,400, striped, stripes **non-colliding** | |
  | Checkpoint pads | one lane, numbered by depth into the yard | the numbering and the route disagree on purpose |
  | Latching doors | a low wall down one side; each plate out on the open floor; each leaf slides **away** from its plate | the route never passes through a doorway, so a wrongly-shut door names itself instead of jamming the walk |
  | Coins on stands | one lane, all **movable** | |
  | Counter | with the line painted on the floor in front of it, and a non-zero `StartingBanked` | |
  | Hot floor | two strips, flat and non-blocking | walked over, never bumped into |
  | PlayerStart | at the mouth | |
  | Backdrop + landmarks | a back wall and three posts of different sizes | a moving camera is distinguishable from a still one |
  | Fixture | one placed `ACheckpointRestoreFunctionalTest` | |

  **No coordinate, no id, no count and no `StartingBanked` value appears
  anywhere in this section or in the prompt.** They are readable in the level, on
  the props.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No checkpoint logic of any kind, no Blueprint subclass, no level edits. The
  empty submission compiles (L1 green) and FAILs L2 at the first death.
- No test source in the agent's writable path.
  `ACheckpointRestoreFunctionalTest` lives in the `CraftBenchTests` module the
  agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-checkpoint-restores-the-world/L_CheckpointYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice: once at 60 FPS and once at 20 FPS**
(`fps_legs`), in separate PIE processes. Verification primitive:
**pie-checkpoint-sampling** plus an every-frame readback of visible consequences
over a fixture-driven walk, with `timer-framerate-legs` as the anti-overfit for
the disclosed one-second settle.

**Every graded read is a visible consequence:** a leaf's world position against
that door's own two places, a coin mesh's visibility, a pad lamp's intensity
(`IsVisible() && !bHiddenInGame && Intensity > 0` — never a bool), the two
numbers parsed off the counter's own text faces, and the character's location.

### The drive — twenty stops, one walk, three deaths

Every stop is the live world position of a prop's own trigger volume; **no
coordinate appears in the fixture**. The walking lane is derived too: the middle
of the widest gap between the yard's occupied lanes, refused if it is under
600 uu clear of everything. Every leg is *out to the lane, along the lane, in to
the stop*, and the character **stands still for 2.0 s at each stop** before the
drive advances — arrival-triggered advancement consumes waypoints instantly and
nothing would ever settle.

| # | Stop | What it sets up |
|---|---|---|
| 1 | door 0's plate | door 0 open **before any mark exists** |
| 2 | coin 0's stand | CARRIED 1 |
| 3 | hot floor 0 | **DEATH 1**, no pad ever stood on |
| 4 | door 0's plate | it must open again |
| 5 | coin 0's stand | it must be takeable again |
| 6 | coin 1's stand | CARRIED 2 |
| 7 | the **deepest** pad | **MARK 1** — door 0 open, 1 and 2 shut, two coins in hand |
| 8 | door 1's plate | opened *after* mark 1 |
| 9 | a **shallower** pad | **MARK 2** — doors 0 and 1 open, door 2 shut |
| 10 | coin 2's stand | CARRIED 3 |
| 11 | the line | BANKED + 3, CARRIED 0, three coins gone for good |
| 12 | door 2's plate | opened *after* mark 2 |
| 13 | hot floor 1 | **DEATH 2** |
| — | *(the coins change places)* | a cyclic shift among their own stands |
| 14 | door 2's plate | it must open again |
| 15 | coin 3's stand | CARRIED 1 |
| 16 | the **shallowest** pad | **MARK 3** — all three doors open, coin 3 in hand |
| 17 | coin 4's stand | CARRIED 2 |
| 18 | hot floor 0 | **DEATH 3** |
| 19 | coin 4's stand | it must be takeable again |
| 20 | clear of the last pad | they must be able to walk away |

After each death the fixture **stops feeding input for 5.0 s**, judges at
+2.0 s, watches for hot floor until +5.0 s, then resumes and starts the mobility
clock. Without that hold the fixture would still be walking the character at the
hazard while measuring how far they are from the mark — i.e. measuring its own
drive.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
G1 YouComeBackAtTheLastPadYouStoodOn
    at death_time + 2.0s (prompt says one second; the gate allows two):
      target := respawn spot of the pad the FIXTURE last saw stood on,
                using the pad's OWN overlap set -- never a grown box, so the
                fixture can never grade against a mark the pad never announced
      if no pad has been stood on: target := nearest of {character at t=0,
                any APlayerStart}, tolerance 300 uu instead of 200
      assert flat distance(character, target) <= tolerance
      assert character not inside any hazard volume, and stays out until +5.0s
    message names the mark, the distance and whether they are still on hot floor

G2 TheLitPadIsTheMark
    every frame, once 1.0s has passed since the last mark and since the last
    death window closed (BOTH clauses share the settle, so an ordinary
    two-statement arm -- light the new one, put the old one out -- cannot fail):
      assert at most one pad lamp is lit
      assert if a pad has been stood on, the lit pad is exactly that pad

G3 TheDoorsComeBackToHowTheyWereWhenYouArmed
    every frame, per door, leaf world position vs that door's own two places
    (20 uu; the fixture refuses to start if they are under 300 uu apart):
      assert the leaf is at exactly one of the two places
      a shut -> open transition is allowed only while the plate window is open
        or within 0.5s of it closing
      any transition inside a death window is allowed only to the state that
        door was in when the current mark was set
      no other transition, at any other time
    and at death_time + 2.0s: every door equals the mark-time snapshot
    message names the DoorId, what it is, what it was, and which death

G4 TheCoinsComeBackToWhereTheyWereWhenYouArmed
    every frame, per coin, on the coin mesh's visibility:
      visible -> hidden allowed only while that coin's stand window is open
        or within 0.5s of it closing        (ledger: on-stand -> in-hand)
      hidden -> visible allowed only inside a death window AND only if the
        mark-time snapshot says that coin was on its stand
    and at death_time + 2.0s: every coin's place equals
        (over-the-line if the ledger says so, else the mark-time snapshot)
    message names the CoinId, where it is, where it should be, and which death

G5 WhatWentOverTheLineStaysOverTheLine
    baseline := the BANKED face read off the world at t=0, never a literal
    every frame:
      assert BANKED never decreases
      assert BANKED changes only while the line window is open or within 0.5s,
        never inside a death window, and then by exactly the number of coins
        the fixture ledgers in hand at that instant
      assert no coin the ledger calls over-the-line ever becomes visible again
    and at death_time + 2.0s: BANKED reads what it read before the death
    message prints both numbers, and names any coin that came back

G6 TheCounterAgreesWithYourHands
    every settled frame (1.0s after the last ledger change and after the last
    death window), and again at every death_time + 2.0s:
      assert the CARRIED face == the number of coins the fixture ledgers in
        hand. Both sides are derived the same way: coin-mesh visibility plus
        the fixture's own record of when BANKED went up -- exactly the
        information the submission has
    message prints both numbers and lists the CoinIds it believes are in hand

G7 TheYardStillWorksAfterYouComeBack
    whenever a door's plate window opens on a SHUT door:
      assert that door reaches its open place within 1.0s
    whenever a coin's stand window opens on a coin ON its stand:
      assert that coin leaves its stand within 1.0s
    message names the prop and what failed to happen

G8 TheYardRanAllThreeDeaths
    at the SENTINEL checkpoint, t = 720s, far past the ~240-300s walk:
      assert all twenty stops completed
      assert three deaths were judged
      assert after each death the character covered >= 400 uu under fixture
        input within 8s of input resuming
    message names the stop the walk stalled on, the number of deaths judged and
    the character's last position
```

**Two predicate rules, and their direction is load-bearing.** The props react to
capsule-versus-box overlaps, which begin about a capsule radius of travel before
the character's own origin reaches the box. Every "within N seconds of standing
on X" window above is therefore opened by *(that prop's own overlap set) OR
(its box grown by capsule radius + half height + 60 uu)* — a strict superset of
what the prop can see, so the window opens **earlier** than the prop can fire
and never later. A door opening the instant its plate registers is always inside
its window. The **mark** ledger is the exception and uses the prop's overlap set
**ungrown**: a grown pad box would let the fixture record a stand the pad never
announced, and then grade the respawn against a mark the submission was never
told about.

**The death instant comes from the hazard's own announcement**, not from a
sampled overlap. A correct submission moves the character off the hot floor
inside the very frame the overlap fires, so an overlap sampled on the next tick
can read empty. A sampled overlap is kept as a second detector for a run where
no announcement arrives. The death window is opened **before** the frame's
transitions are observed, because that same correct submission shuts its doors
and restores its coins in that frame; observing first would score every correct
answer as "a door shut with nobody dead".

**The sentinel.** `ACraftBenchFunctionalTest::Tick` ends the test the moment the
last scheduled checkpoint is crossed, so a stalled walk would otherwise finish
green having graded nothing. The schedule is 60 gauging instants 6 s apart
carrying the calibration log and the camera plan, then a sentinel at t = 720 s.
A run that gets through all twenty stops finishes itself and never reaches it.

**Staging faults are attributed, not scored** (`HARNESS-PRECONDITION`, never a
model failure): fewer than three pads / three doors / five coins / two hazards,
duplicate `StandOrder`/`DoorId`/`CoinId`, a door already open when the yard
opens, a coin already gone, a door whose two leaf places are under 300 uu apart,
a trigger volume under 200 uu deep (at 20 FPS a walking character covers 25 uu a
frame and could step over anything shallower), a counter whose faces do not
parse or whose BANKED opens at 0, a walking lane under 600 uu clear, a leg that
would pass within 220 uu of a prop it is not aimed at, a pad whose respawn spot
is within 1500 uu of hot floor or of the line or within 400 uu of a coin stand,
pads whose numbering does not track depth into the yard, and a script that would
run two deaths with no pad stood on between them.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
|---|---|---|
| the mark is the pad stood on **most recently** | G1, at each of the three deaths | never — every death is judged |
| the numbering has nothing to do with it | G1 at deaths 2 and 3, where recency and depth name different pads; a staging check refuses a yard whose numbering does not track depth | never |
| before any pad, the mark is the way in | G1's pre-pad branch at death 1 | never |
| the lit pad is the mark, at most one lit | G2, every settled frame | for 1.0 s after each mark and after each death window |
| standing on a pad moves no door | G3's transition rule (a shut with nobody dead) | never |
| standing on a pad touches no coin | G4's transition rule | never |
| standing on a pad banks nothing | G5's window clause | never |
| a door open at the mark stays open | G3's death check | never |
| a door opened since shuts again | G3's death check | never |
| ...**properly**, so its plate opens it once more | G7's door clause, exercised at stops 4 and 14 | if the run never reaches those stops — and G8 then FAILs for that |
| a coin on its stand at the mark goes back | G4's death check | never |
| a coin in hand at the mark stays in hand | G4's death check, at death 3 | never |
| a put-back coin is pickable again | G7's coin clause, exercised at stops 5 and 19 | as above |
| BANKED never changes at a death | G5's death check | never |
| BANKED never changes at a mark | G5's window clause | never |
| BANKED moves only at the line, by exactly what was carried | G5's window clause | never |
| a banked coin never returns to a stand or a hand | G5's clause 2, every frame | never |
| CARRIED always says how many coins are in hand | G6, every settled frame and at every death | for 1.0 s after a ledger change or a death window |
| picking a coin up moves CARRIED | G6 — the face is compared with the fixture's ledger, so a pickup that leaves CARRIED alone fails there with both numbers printed. **There is no separate assertion for it** | as above |
| within a second the character is at the mark | G1, with a 2.0 s window (widened in the safe direction only) | never |
| able to walk on afterwards | G8's mobility clause | never |
| not on hot floor when they come back | G1's clearance clause, +2.0 s to +5.0 s | never |
| everything read off the world | no gate — an **anti-gaming property**, see below | — |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched:** 2 —
  `Source/ThirdPerson/Tasks/t3-checkpoint-restores-the-world/CheckpointDirectorActor.{h,cpp}`.
- **LOC:** ~230 (95 header incl. comments, ~135 body).
- **Honest senior-dev hours: 5–8.** Every rule is spelled out in the prompt and
  every operation the answer needs is supplied, so this is not a discovery
  problem; it is four interacting pieces and the hours go into making them
  agree. Roughly: 1 h reading the five prop classes and noticing the three
  things they pointedly do NOT do; 2–3 h on the three-way ledger and the fact
  that the only moment "which coins crossed the line" is knowable is the instant
  it happens; 1–2 h on snapshotting at every mark rather than once; 1–2 h on the
  restore, where the mark's coin places have to be intersected with what has
  been banked since and CARRIED derived rather than restored.
- **This is the top of T2 / bottom of T3** on hours alone. It is filed T3
  because the failure surface is wide — eight gates over three deaths, and one
  slip in any of the four pieces fails a different one.

## Anti-gaming notes

1. **Snapshot once and replay it at every death.** *Failure mode*: take the
   remembered moment in `BeginPlay`, or at the first mark, and reuse it — the
   shape most first passes take. *Defense*: the BeginPlay version passes death 1
   (before any pad the opening state IS the right answer) and then shuts two
   doors that were open when mark 2 was set; the first-mark version shuts the
   one door opened between the two marks. G3 names the door and the death in
   both cases. Fully disclosed — the prompt says *not how it was when the yard
   opened* — so this is the thing being measured, not a trap.
2. **Roll the counter back.** *Failure mode*: treat CARRIED and BANKED as part
   of the snapshot. *Defense*: BANKED falls by three at death 2 (G5 clause 1),
   and the three coins that went over the line come back to their stands
   (G5 clause 2). For CARRIED alone: at death 2 the two coins in hand when mark
   2 was set have both crossed the line since, so the answer is 0 and the
   snapshot says 2 (G6) — and handing them back would let the same two coins be
   banked twice. The prompt states the rule the other way round on purpose
   ("CARRIED always says how many coins are in hand"), so the correct behaviour
   is derivable; the discrimination is in noticing that *derive* and *restore*
   are different operations here.
3. **Put every currently-taken coin back.** *Failure mode*: the plainest reading
   of "the world comes back", and it looks right at death 1 and death 2.
   *Defense*: at death 3 coin 3 was already in hand when mark 3 was set — G4
   names it. Also caught: restoring the coins taken since the last *death*
   rather than since the last *mark*, which differ at death 2.
4. **Leave the character out of it, or leave something switched off.** *Failure
   mode*: two ends of the same instinct — restore the world and let something
   else move the character (G1 fails at death 1, still standing on hot floor);
   or freeze the character / turn off a restored coin's trigger so a coin put
   back under their feet is not instantly retaken, and never turn it back on.
   *Defense*: G7 requires every restored prop to work again when the drive
   returns to it, and G8's mobility clause requires 400 uu of movement under
   fixture input within 8 s of each respawn. **Documented limit:** a director
   that uses the supplied `SetOpen(bool)` and `Restore()` in the obvious way
   passes G7 for free. G7's discriminating family is the disable-and-forget one
   above plus bypassing a prop's own operation (moving a leaf by hand leaves the
   latch set; un-hiding a coin mesh leaves it un-pickable) — it is a regression
   check first and a discriminator second, and this spec does not claim
   otherwise.
5. **Hard-code the yard.** *Failure mode*: the editor-driving lanes
   (`unreal-mcp`, `aura-mcp`) can open the map and read off the
   ids, the coordinates and `StartingBanked`. *Defense*: **none of the graded
   facts are constants.** Which pad is the mark, which doors were open then,
   which coins were where, and what has been banked since are all events, and
   every gate compares the world against a ledger the fixture builds from the
   same runtime events. On top of that the **coins change places mid-run** (a
   cyclic shift among their own stands, after death 2 is judged), so an answer
   keyed to where a coin was rather than to which coin it is gets every coin
   wrong from there on; and the run is graded **twice at different frame rates**,
   so nothing fitted to a frame count or a wall-clock delay survives. *Honest
   limit*: the prop inventory itself (how many, which ids, where) IS a constant
   in one committed map, and hard-coding it is not detected — it simply buys
   nothing, because no gate is keyed on identity.

## Hidden invariants

- **`SetActorLocation` and `TeleportTo` are not interchangeable, and this task
  does not discriminate between them.** Only `TeleportTo` reaches
  `UCharacterMovementComponent::OnTeleported` (via `APawn::TeleportSucceeded`)
  and only it runs `FindTeleportSpot`; `SetActorLocation` leaves a capsule
  penetrating whatever it was dropped into. The respawn spot is clear of the
  pad slab by construction, so both work here, and **no gate distinguishes
  them**. Recorded so nobody later mistakes G8 for a check on this.
- **A teleport does not clear velocity.** `OnTeleported` only marks the move and
  re-finds the floor. Braking from 500 uu/s at 2000 uu/s² carries about 62 uu,
  well inside G1's 200 uu — and the fixture holds its own input across the whole
  judging window, so the character is braking rather than walking. Not gated,
  and not claimed to be.
- **The respawn re-announces the mark pad's own stand.** `GetRespawnTransform()`
  is a spot above the pad, so a teleport there re-fires that pad's trigger. Both
  conventions pass by construction: the mark is the same pad either way, the
  fixture suppresses mark events inside a death window, and the script is
  checked at `PrepareTest` to guarantee a fresh mark between every death and the
  next one — so no snapshot taken at a respawn instant is ever the one graded.
- **Editing the supplied props is not itself a gate.** The prompt says the yard
  is not the agent's to change and the sandbox permits it, because the whole
  module is writable. Everything is graded on visible consequences, so breaking
  a prop shows up behaviourally — with one named exception: silencing
  `OnLethalTouch` while still restoring instantly can leave the fixture unable
  to see a death at all, and that run FAILs G8 with "0 of 3 deaths were judged"
  rather than at a behaviour gate.
- **An unparseable counter face is a graded FAIL, not a precondition.** It reads
  as `-1` and falls through G5/G6 as a drop. Routing it to
  `HARNESS-PRECONDITION` would hand any submission a non-graded exit for the
  price of blanking the counter.
- **`fps_legs: [60, 20]` is declared but has not been run.** Every window in the
  fixture is at least 0.5 s (ten frames at 20 FPS) and every trigger volume is
  at least 200 uu deep against a 25 uu-per-frame step, so the 20 FPS leg is
  expected to hold. If it proves unstable, **drop the key and say so here** —
  the task grades correctly at 60 alone, and a half-claimed second leg is worse
  than one leg.
- **The `randomization:` front-matter key is deliberately NOT declared.**
  `run_task.apply_randomization` exists and is unit-tested but is **never called
  by the runner**, so declaring it would promise per-run variation the harness
  does not deliver. The in-run variation this task does have (the coin shuffle,
  the two frame-rate legs) is performed by the fixture itself and is real.
