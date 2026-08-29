---
id: gp-door-hitch-fix-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Debug & Refactoring
category: gameplay
layers: [L1, L2]
fixtures: ["L_DoorHitch :: ADoorHitchFunctionalTest"]
---

# gp-door-hitch-fix-bp

A `bp`-basket **Edit(Debug)** task — the first member of the debugging
family (the largest uncovered demand block in the source list). The
workspace ships a WORKING-BUT-DEFECTIVE Blueprint: a swinging door that
opens and closes correctly from rest but visibly snaps when its
interaction fires mid-swing. The deliverable is the FIX, graded purely as
runtime behavior in a real PIE world: a per-tick continuity monitor plus
pose gates. The agent may repair the existing machinery or rebuild the
motion any way it likes — every gate is behavior, none is mechanism.

### Provenance and deliberate divergences from the source row

Ported from **`BP Test Prompts - G2 Medium Prompts.csv` row g2-6**
(`Door`, `Edit (Debug)`, easy; Concepts: Timelines) via the scale-up plan's
slate row **T2.3** (2026-08-07). Divergences, each deliberate:

- **The sound clause is DROPPED** (owner slate decision, plan T2.3): "play
  a sound when the Sound Event timeline event fires" would gate on an
  asset-mechanism pair the fixture cannot observe deterministically under
  `-nosound`, and the row's demand-block value is the DEBUG half.
- **The continuity gate runs on a Tick override, never OnCheckpoint**
  (owner constraint, same row): checkpoint spacing is 0.4–1.5 s and a
  one-frame teleport is invisible at that resolution.
- **The bug is authored, not described.** The source row prompt says "fix the
  animation hitching"; our prompt states the SYMPTOM contract (below) and
  the baseline genuinely exhibits it — the restart-instead-of-resume
  defect, which is also exactly the wiring the product's own timeline
  guidance document shows as its worked example. The prompt never names
  the cause, the node, or any engine feature.
- **Folder convention**: the source row's `/Game/G2/6/` becomes the standard
  `Content/Tasks/gp-door-hitch-fix-bp/`.

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names the
> shipped asset (`BP_Door`), its folder, the interaction entry
> (`Interact` — the contract the fixture drives), and the graded envelope
> numbers (a ~90-degree swing over ~1.5 seconds, the outer tenths of
> nothing — no timeline, no node, no engine class or feature appears).
> The DEFECT is described as observable behavior ("visibly jumps instead
> of smoothly reversing"), never by its cause.

## Primary concept

- `blueprint-timelines` — Timelines
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/timelines-in-unreal-engine)

The load-bearing capability is **debugging interruptible time-driven
state**: recognizing that a motion driver restarted from an endpoint
instead of resuming from its current position, and repairing it without
breaking the surrounding contract. (The fix is graded as behavior; an
agent that rebuilds the motion without the original machinery passes the
same gates.)

## Prompt given to the agent

> The folder `Content/Tasks/gp-door-hitch-fix-bp/` contains `BP_Door`, a
> swinging door. Its `Interact` event toggles it: fired while the door is
> closed, the door swings open (about 90 degrees over about 1.5 seconds);
> fired while open, it swings closed again. A placed instance of this
> door is driven exclusively through that `Interact` event.
>
> The door has a defect: if `Interact` fires again **while the door is
> still swinging**, the door visibly jumps to a different position before
> continuing, instead of smoothly reversing from wherever it currently
> is.
>
> Fix `BP_Door` **in place** (same asset, same folder) so that:
>
> - firing `Interact` mid-swing smoothly reverses the door from its
>   current position — the door must never jump or teleport;
> - everything that already works keeps working: the door stays still
>   until `Interact` first fires, opens/closes from rest exactly as
>   before (roughly the same ~90-degree swing and ~1.5-second duration),
>   and the `Interact` entry point keeps its name and takes no
>   parameters.

## Workspace state pre-task

Substrate content that **exists**:

- `Content/Tasks/gp-door-hitch-fix-bp/BP_Door.uasset` — the defective
  door (authored via the product's own asset lane; its property-by-
  property spec is `notes.md` §1). The folder is the agent-writable
  Content carve-out; the agent edits the asset in place.
- `Content/Maps/gp-door-hitch-fix-bp/L_DoorHitch.umap` — the VERIFIER'S
  fixture level (deny-listed for writing): one placed `BP_Door` instance
  tagged `HitchDoor` + the functional-test actor. The agent neither needs
  nor is able to touch it; edits to the Blueprint asset flow into the
  placed instance.

Files that **do not exist**: nothing else is required. Any additional
asset the agent authors in the task folder is unconstrained.

## Verifier specification

Layer choice: **L1 + L2**. The graded surface is motion over time in a
real PIE world — continuity is a per-frame property, unreadable from any
static asset fact, so L2 is the load-bearing layer and L2I is
deliberately NOT declared (a structural gate would pin the mechanism,
and the fix is mechanism-free by design).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The natural submission is content-only, so L1 is a precondition, never a
correctness signal.

### L2 — PIE behavioral fixture

`ADoorHitchFunctionalTest` (Source/CraftBenchTests/Tasks/
gp-door-hitch-fix-bp/) runs in the committed `L_DoorHitch` map under
`-deterministic -FPS=60 -nullrhi`, driven by the base checkpoint clock;
the continuity monitor samples every TICK (Tick override, Super first).
The door is found **by actor tag** (`HitchDoor`, exactly-one), its
observable surface is every static-mesh part (pose gates are relative to
each part's own recorded closed pose — mesh choice, component names and
extra parts are free), and the fixture drives it exclusively through the
reflected parameterless `Interact` entry (`FindFunction`/`ProcessEvent`,
the sprint-fixture seam idiom).

Phases (world game-time; swing time 1.5 s):

```text
t=0.0-0.5   quiet window: the door must not move before any Interact
t=0.5       Interact #1 (open)
t=2.6       gate: opened (displacement >= 45 deg from closed pose)
t=3.1       Interact #2 (close, from rest)
t=5.2       gate: closed again (within 10 deg of closed pose)
t=5.7       Interact #3 (reopen)
t=6.45      gate: visibly mid-swing (>= 15 deg), then Interact #4 -
            THE mid-swing reversal
t=8.6       verdict gates: continuity first (max single-tick jump over
            the whole armed window: angle <= 12 deg/tick AND position
            <= 50 units/tick), then the honored-reversal end state
            (back within 10 deg of closed)
```

Threshold calibration: a smooth 90 deg / 1.5 s swing at the fixed 60 fps
timestep moves ~1 deg/tick (cubic-tangent peaks under ~3); the baseline's
restart defect jumps 40–90 deg in ONE tick. The 12 deg/tick limit
separates the families with ~4x margin on both sides. All numbers live
in the fixture's constants block and are mirrored in `notes.md`.

Every gate fails through its OWN `FinishTest(Failed, ...)` literal (the
named-FAIL placement law); the full literal inventory with the
requirements mapping is in `discrimination/MATRIX.md`.

**Every graded fact excludes the value an untouched or lazy delivery
gets for free** (the dead-gate audit):

| gate | free/untouched (BUGGY BASELINE) value | graded demand | free value inside the gate? |
|---|---|---|---|
| quiet window | still (baseline passes — guard row) | no pre-Interact motion | (guard; discriminators below) |
| opens / closes from rest | baseline PASSES both (its defect is mid-swing only) | preserved behavior | (deliberate — proves the task is a targeted DEBUG, not a rebuild: a fix that breaks rest behavior fails here) |
| mid-swing continuity | baseline FAILS: the restart teleports the door ~45 deg in one tick | max tick jump <= 12 deg | **no — THE discriminating gate; the empty leg IS the baseline** |
| honored reversal | baseline also ends wrong (reopens fully) but dies at the continuity gate first | ends closed | **no** (this gate owns the "mid-swing Interact ignored" fix-dodge) |

**Score granularity.** L2 is one fixture: `report.json` carries the
fixture verdict; `overall` = all layers green.

## Reference solution metadata

- LOC range: **0** lines of code; the minimal fix is rerouting two
  exec connections inside the existing graph (restart-from-endpoint →
  resume-from-current, both directions). `notes.md` §2 pins it
  property-by-property.
- Files touched: 1 (the modified `BP_Door.uasset`).
- Senior-dev hours: 0.1–0.3 for the minimal fix; the T2 content is
  DIAGNOSIS (reading the graph, recognizing the restart defect), not
  volume.

## Anti-gaming notes

Per the amended checklist §7 the discrimination package ships no
hand-authored gaming variants; the requirements table in
`discrimination/MATRIX.md` is the soundness artifact. The failure modes
it is written against:

1. **Empty delivery** — the untouched baseline: passes the rest-behavior
   gates, dies at the continuity gate with the named teleport literal.
2. **Dodge instead of fix** — make mid-swing `Interact` a no-op (door
   finishes opening) or freeze the door entirely: no teleport either
   way, but both die at the honored-reversal gate ("the mid-swing
   Interact was ignored" / never returns to closed).
3. **Nuke the motion** — a door that never moves passes continuity
   trivially; dies at the opens gate. One that opens instantly dies at
   the continuity gate (a 90-deg single-tick jump IS a teleport) — the
   envelope floors are load-bearing.
4. **Rename/reshape the contract** — removing or parameterizing
   `Interact` dies at the seam gate; deleting the mesh dies at the
   observable-surface gate. Retagging is impossible: the TAG lives on
   the placed instance in the verifier-owned map, not in the agent's
   asset.
5. **Slow-walk the swing** — stretching the duration so t=6.45 is no
   longer mid-swing dies at the mid-swing gate ("the swing timing
   changed too much"); the prompt floors roughly-current timing.

## Discrimination

`discrimination/MATRIX.md` — reference-PASS / empty-FAIL legs (the empty
leg IS the buggy baseline — the overlay-no-wipe workdir law makes the
shipped defect the automatic FAIL leg) plus the mandatory requirements
table.
