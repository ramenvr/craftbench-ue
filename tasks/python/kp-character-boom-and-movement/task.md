---
id: kp-character-boom-and-movement
substrate: ThirdPerson
set: python
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2I]
introspect: [kp_character_boom_and_movement.py]
---

# kp-character-boom-and-movement

**The movement-tuning lane** (narrowed from a row in an earlier internal task
list, not shipped). The only task in the
`bp`/`python` lanes that reads **CharacterMovement** values: today those names
appear in C++ prose and one L2 runtime sampler, and nowhere an editor-scripting
agent can be graded on them.

## Primary concept

- `character-movement` — the movement component's tuning surface on a
  character's class defaults
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/character-movement-component-in-unreal-engine)

Adjacent in-scope concept: `blueprints` (the deliverable is a Blueprint with a
small component rig). Neither name appears in the prompt.

## Prompt given to the agent

> Produce a new player-character Blueprint at
> `Content/Tasks/kp-character-boom-and-movement/BP_TaskChar`, built on the
> engine's standard walking-character base class.
>
> Give it a camera rig of exactly two new components, named exactly:
>
> - `TaskBoom` — an extendable arm attached at the character's root.
> - `TaskCam` — a camera, attached **to the arm**, not to the character.
>
> Then tune the character's own movement so its class defaults read:
>
> - walk speed **900**
> - jump velocity **700**
> - acceleration **1024**
>
> Save the Blueprint where it is named, compiled.
>
> A character that still moves with this project's stock tuning has not been
> tuned — those three values are all different from the ones the shipped
> character uses, and each is checked exactly.

## Workspace state pre-task

Substrate content that **exists**: nothing under
`Content/Tasks/kp-character-boom-and-movement/` — this task ships **no
baseline**. The project's shipped player character
(`Content/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`) exists and is
readable, and is deliberately *not* off-limits (see *Anti-gaming*).

Files that **do not exist** (the correct end state produces it):

- `Content/Tasks/kp-character-boom-and-movement/BP_TaskChar.uasset`

Out of scope: no C++, no level, no placed actor, no functional test, no config.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is static: the asset's class,
two entries in its component tree, and three numbers on its class defaults.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

### L2I — Structural assertion

`tools/verify-single/introspect/kp_character_boom_and_movement.py`, headless
under `-nullrhi`, read-only. **Exactly 6 checks on every leg.** PASS requires
all 6:

```text
blueprint_present                   C1  BP_TaskChar exists   [LIVE - absent at start]
derives_from_character              C2  its class defaults are a walking-character
                                        instance
boom_component_present              C3  a component whose name stem is `TaskBoom`,
                                        whose type is a spring arm, attached at
                                        the character's root
camera_parented_to_boom             C4  a component whose stem is `TaskCam`, whose
                                        PARENT is `TaskBoom`  [the rig, not a flat list]
movement_values_exact               C5  walk 900 / jump 700 / acceleration 1024,
                                        each compared exactly
movement_untouched_defaults_absent  C6  none of the three is still sitting at the
                                        value the shipped character uses
```

**What actually discriminates here, stated plainly because it is not what the
row's title suggests.** The source row framed this as "build the hierarchy from
scratch". That is **not gradable**: the project's shipped character already has
an arm-and-camera rig, so a duplicate of it satisfies any structural check, and
a grader cannot tell an authored rig from a copied one. Measured 2026-08-14, the
shipped character reports `CameraBoom` → `FollowCamera` and
`orient_rotation_to_movement = True`.

Two consequences, both deliberate:

- **`OrientRotationToMovement` is NOT graded.** The shipped character already
  has it `True`, so requiring `True` would be a **dead gate** — it passes at
  baseline for reasons having nothing to do with the submission.
- **The movement values carry the discrimination.** The shipped character uses
  **500 / 500 / 2048**; this task asks for **900 / 700 / 1024**. Those are the
  only facts a duplicate cannot inherit. The prompt therefore asks for a
  character with this rig and these values, and does **not** claim to grade
  "authored from scratch".

**Dead-gate audit** (house law). All 6 checks are LIVE: the empty submission
scores a genuine **0/6** (no Blueprint, so every downstream check reports its
subject missing). C6 is the only check that could look redundant with C5 — it is
narrower on purpose: it can fail *only* when a value is still at the shipped
character's tuning, so it names the duplicate route by cause instead of letting
it hide inside a generic "wrong value".

**Two readback facts the grader is written against**, both measured before it
was written:

- **Component names come back suffixed.** A component named `TaskCam` reads
  back as `TaskCam_GEN_VARIABLE`. Every name match is on the **stem**; an exact
  comparison would FAIL conforming work.
- **The component tree includes inherited entries** (`CollisionCylinder`,
  `Arrow`, `CharacterMesh0` from the base class) in *every* submission. So
  nothing counts components — the two named ones are looked up by stem, and a
  count-based check would grade the base class rather than the agent.

The parent class is read from the generated class's default object, not from a
`parent_class` property on the Blueprint — that property raises.

**Score granularity.** `report.json` carries `x/6`. Reported, not gating.

## Reference solution metadata

- LOC range: **0** lines of shipped code; the deliverable is one Blueprint.
- Files touched: 1 created.
- Senior-dev hours: 0.2–0.5.

## Anti-gaming notes

1. **Duplicate the shipped player character.** *Failure mode*: copy it into the
   task folder under the required name. It already has an arm-and-camera rig, so
   C1–C4 look satisfiable for one call of work. *Defense*: its movement is
   500/500/2048, so C5 fails with `CHARRIG_MOVEMENT_WRONG` and C6 names the
   cause with `CHARRIG_MOVEMENT_STILL_STOCK fields=`. Its components are also
   named `CameraBoom`/`FollowCamera`, so C3–C4 fail on the stem lookup until
   they are renamed too. Variant `duplicate-the-stock-character/`.
2. **A flat rig.** *Failure mode*: add both components at the root, which is
   easier than parenting one to the other. *Defense*: C4 checks `TaskCam`'s
   PARENT, not merely its existence (`CHARRIG_CAMERA_WRONG_PARENT expected=`).
3. **Right names, wrong kinds.** *Failure mode*: name any two components
   `TaskBoom`/`TaskCam`. *Defense*: the rig is only credited through the
   component tree walk, and C2 additionally pins the asset to a walking-character
   class.
4. **Tune only the value that is checked first.** *Failure mode*: set walk speed
   and stop. *Defense*: C5 compares all three exactly and reports every wrong
   field, so a partial tune fails with the remaining fields named.
5. **Accepted residual, recorded honestly**: a submission that duplicates the
   shipped character, renames its two components and then sets the three values
   passes — and should. At that point it has done the work the prompt asks for;
   only the route differs, and the prompt does not constrain the route. What is
   NOT claimed is that this row proves an agent can build a component hierarchy
   from nothing.

## Hidden invariants

- The check denominator is fixed at 6 on every leg, including an empty
  submission (a genuine 0/6) and a no-editor-python import.
- Every name comparison is on the stem, because the engine suffixes stored
  component names; an exact match would fail conforming work.
- Nothing counts components — inherited entries from the base class are present
  in every submission, so a count would grade the base class.
- Every verifier-side failure path emits a distinct token from the grader's
  `UNCREDITED_TOKENS` tuple, which appears in **no** discrimination-matrix row.
- Echoed component and class names are agent-controlled, so they are
  marker-stripped and length-capped before reaching a check detail.
