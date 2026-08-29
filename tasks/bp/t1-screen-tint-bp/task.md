---
id: t1-screen-tint-bp
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_TintTrack :: AScreenTintFunctionalTest"]
introspect: [t1_screen_tint_bp.py]
---

# t1-screen-tint-bp

The Blueprint leg of a surface pair. `cpp/t1-screen-tint-cpp` is
the other one. **Same map, same fixture, same checkpoint schedule, same named
gates** — the only difference is which surface the answer is written on, which is
what makes the pair a measurement of the surface rather than of two designs.

## Provenance

Adopted from the startup-eval design corpus row
`t1-runtime-postprocess-reacts-to-movement`, whose own mission carries the
mandate *"Without generated C++"* — so the Blueprint constraint is the corpus's,
not an invention here. That row was Wave 1 #13 of
an internal design note (not shipped); the C++ leg was
built from the same row first, and this leg cashes the surface half the review
noted but never scheduled.

**Why the pair exists at all.** The benchmark's thesis is a (model x tool x SURFACE)
interaction, and the surface axis was carried by six `gp-` pairs alone: all 30
tasks in the former `craftbench-public` set were C++-only, because their graded
actor is PLACED in the committed map and `Content/Maps/` is deny-write to agents,
so a Blueprint subclass would never be instantiated. Two changes make this leg
possible, both landed 2026-08-20 and both recorded here because neither is
guessable from the spec:

1. `AScreenTintFunctionalTest::SpawnGradedBlueprintIfPresent` — if a Blueprint
   under `/Game/Tasks/` derives from what the map placed, the fixture spawns it
   at the placed transform, carries the tags over, and removes the placed one.
   Additive: with no such Blueprint the C++ leg runs byte-identically.
2. `AScreenTintActor`'s constructor now supplies `bCanEverTick = true`.
   `EngineBaseTypes.h:211-217` declares `bCanEverTick` as a bare `UPROPERTY()`
   with no editor exposure, so a Blueprint author could not enable ticking and
   this leg was **unwinnable** before that change. An unwinnable leg is not
   surface discrimination.

## Primary concept

- `runtime-postprocess` — driving a post-process setting from live gameplay state
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-effects-in-unreal-engine)

## Composed concepts

- `ps-bp-overview` — Blueprints Visual Scripting Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprints-visual-scripting-in-unreal-engine)
- `movement-components` — reading a character's own current top speed rather than
  a constant
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

## Prompt given to the agent

> Deliver your solution **entirely as Blueprint assets** created in the editor and
> saved under `Content/Tasks/t1-screen-tint-bp/`. **Do not add or
> modify any C++ source for this task.**
>
> The track has a screen effect fitted: a vignette that covers the whole level.
> It is already switched on and already visible, and it currently reads its
> resting value all the time.
>
> Make it follow how fast the character the player controls is **actually
> moving**. Standing still it reads its resting value; at the character's top
> speed it reads its full value; in between it is proportional. It must be within
> **0.12** of the right value, and must get there within **0.4 seconds** of a
> change.
>
> The character's top speed is **not a constant** — the track changes it part way
> through — so the effect has to be proportional to whatever that character can
> currently do, not to a number you decide now.
>
> The screen also carries a second, unrelated setting, supplied at a fixed value.
> Leave it exactly as you found it.
>
> The effect and the switch that sets it are already supplied. Nothing decides
> what to set it to. Do not edit the level, any config file, or any test file.

## Workspace state pre-task

The deliverable root is `Content/Tasks/t1-screen-tint-bp/` —
Blueprint assets only. No C++ file may be added or changed; the C++ that ships is
read-only reference material for what you can call.

What the level already carries, all of it working:

- A screen actor covering the whole track, its effect switched on and visible from
  the first frame, currently showing its resting value and nothing else.
- On that actor: its resting value, its full value, and a second unrelated
  setting, all readable; plus one call that sets the effect, and one that reads
  back what it currently is.
- A character the player controls, with its own current top speed readable off it.

Nothing in the level decides what the effect should read. That is the whole task.

## Verifier specification

**Identical to the C++ leg, ported verbatim** — same map
(`Content/Maps/L_TintTrack.umap`, flat so a pair can share it), same fixture
(`AScreenTintFunctionalTest`), same checkpoint schedule, same tolerances, same
gate names and same failure literals. The full description lives in
`cpp/t1-screen-tint-cpp`'s `## Verifier specification`; nothing is
re-tuned for this surface, because a re-tuned gate would measure the tuning
rather than the surface.

The drive is stand / half pace / flat out / stand, twice, with the fixture
writing a different `MaxWalkSpeed` (0.52x) between the legs — the anti-hard-coding
design. The effect is never judged during an acceleration ramp.

**What this leg adds, and only this:** an L2I introspect leg
(`t1_screen_tint_bp.py`) that structurally proves the thing L2
graded really was a Blueprint. Proving a Blueprint *exists* is not enough — a C++
solve shipped beside a conforming Blueprint would pass L2 on the C++ and pass a
naive existence check on the asset. See the introspect script's own header.

## Requirement-to-assertion map

| the prompt says | the gate that checks it | skipped when |
|---|---|---|
| follows how fast the character is actually moving | `TintTracksHowFastYouAreMoving` | never — it opens at the first settled window |
| resting value when standing still | same gate, at the two standing windows | never |
| full value at the character's top speed | same gate, at the flat-out windows | never |
| within 0.12 of the right value | the gate's tolerance | never |
| gets there within 0.4 s of a change | the settle rule that opens the window | never |
| proportional to the CURRENT top speed, not a constant | the same gate on leg 2, after `MaxWalkSpeed` is re-written to 0.52x | never |
| leave the second setting exactly as found | `TheOtherSettingIsUntouched` | never |
| Blueprint assets only, no C++ added | L2I `t1_screen_tint_bp.py` | never — L2I is declared, so a missing script is exit 7, not a pass |

## Anti-gaming notes

1. **A constant that happens to fit one leg.** Writing the effect to a fixed
   fraction can satisfy leg 1 and is wrong from the first settled window of leg 2,
   because the fixture re-writes `MaxWalkSpeed` between them. The value must be a
   ratio against whatever the character can *currently* do.
2. **Reading a speed the submission wrote down itself.** The fixture grades
   against the character's own velocity, derived from real motion, and
   cross-checks it against ground actually covered; a bookkeeping number cannot
   satisfy it.
3. **Driving the second setting too.** `TheOtherSettingIsUntouched` fails a
   submission that rewrites the whole settings struct instead of the one value —
   the most likely Blueprint-specific slip on this task, since the natural node
   for "set post process settings" takes the entire struct.
4. **Shipping C++ next to a conforming Blueprint.** L2I resolves what L2 actually
   graded and requires it to be Blueprint-generated, so a C++ answer with a
   decorative Blueprint beside it fails the surface contract rather than passing
   both legs.
5. **Two candidate Blueprints.** The fixture raises `HARNESS-PRECONDITION` rather
   than silently picking one, because grading a submission the agent may not have
   meant is not a verdict.

## Hidden invariants

- The gate values (0.12, 0.4 s) and the re-write factor's EXISTENCE are disclosed;
  the factor's value (0.52x) is not, and does not need to be — a correct solution
  reads the number rather than predicting it.
- The tick is SUPPLIED, not something to switch on: `bCanEverTick` carries no
  editor exposure, so requiring an agent to enable it would make this leg
  unwinnable rather than hard.

## Reference solution metadata

`reference/Content/Tasks/t1-screen-tint-bp/` — Blueprint assets,
authored in an attended editor session (there is no script lane for Blueprint
graph authoring in this repo). The recipe is `REFERENCE-NOTE.md`, precise to the
node and pin so the asset can be rebuilt without re-deriving the design.

**Not yet true:** this leg has never been graded. The C++ leg discriminates
(reference PASS / empty FAIL, 2026-08-20); this one has no reference asset yet and
no run. Every claim above about what it WILL do is a prediction.
