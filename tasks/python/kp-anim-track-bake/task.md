---
id: kp-anim-track-bake
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Technical Art
category: gameplay
layers: [L1, L2I]
introspect: [kp_anim_track_bake.py]
---

# kp-anim-track-bake

A `python`-basket, **outcome-graded** editor-scripting task: the workspace
ships a walk animation, and the deliverable is that same asset carrying a
new, named, non-flat numeric track spanning its timeline. Graded by a
deterministic verifier-owned introspect script against the resulting asset
state; per the python-basket law, **no gate asserts how the state was
produced** — editor scripting, editor UI, or the MCP asset lane all earn
the same PASS.

### Provenance and the redesign this port forced

Ported from the v2 corpus draft `t1-anim-modifier-bakes-curve`
(track T1-template-feature, kept at review). The draft's central
`ScriptedPassRecorded` check — "the asset's modifier stack records the
applied pass" — is **unreachable for a headless agent on UE 5.8** and was
cut, with the engine citations pinned in `notes.md` §4: the official apply
pipeline (`UAnimationModifier::ApplyToAnimationSequence`,
`AnimationModifier.h:44`) is a bare `UE_API` method — the class's only
UFUNCTIONs are the `OnApply`/`OnRevert` events themselves
(`AnimationModifier.h:47-53`) — no engine scripting library wraps it, and
the class lives in an **Editor** module, so an agent cannot even ship a
native subclass through the writable game module (L1 links the Game
target). A task gating on the modifier stack would be unwinnable as
prompted — the `craftbench-verifier-capability-truth` /
"mechanism exists but is unreachable" class.

What survives is the row's load-bearing outcome: **programmatic numeric-
track authoring on an animation asset**, graded from the asset. The
re-runnable-pass half is dropped from prompt and grading alike (grading a
demand the prompt cannot fairly make is the same bug inverted). Two more
deliberate divergences: the draft's in-place edit of a **stock** animation
is retargeted to a task-folder duplicate (`Content/Characters/` is
deny-listed on every substrate — the sandbox model forbids the draft's
premise), and identity is by the pre-declared task-folder path, never by
name scanning.

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names the
> provided asset, its folder, and the graded numbers (the opening/closing
> tenth of the timeline, "not a flat constant") — workspace inputs and
> graded values, the precedented exception. No engine class, subsystem,
> or feature name appears: the deliverable is described as "a named
> numeric track on the animation", not by the machinery that authors it.
> The id names the outcome (a baked track), not a mechanism — the draft's
> own id leaked the intended feature and was renamed at port time
> (`notes.md` §4).

## Primary concept

- `anim-curves` — Animation Curves
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-curves-in-unreal-engine)

The load-bearing capability is **programmatic authoring of a named float
track on an existing animation asset**: creating the track, keying it
across the clip, and saving the asset so the track reads back from disk.
(The draft's source page, Animation Modifiers, is retained in `notes.md`
as provenance — the modifier-stack half of that page is the part cut as
unreachable.)

## Prompt given to the agent

> The folder `Content/Tasks/kp-anim-track-bake/` contains one asset:
> `AS_TaskWalk`, a short walk animation on the project's standard
> character skeleton. Add a **named numeric track** to that animation:
>
> - The track's name is your choice.
> - The track must carry keys that span the clip: its first key within
>   the opening tenth of the timeline, its last key within the closing
>   tenth.
> - Its value must change across the clip — the value at its last key
>   must differ from the value at its first key (not a flat constant).
>   For example, a value that rises from the start of the clip to the
>   end.
> - Everything the animation already carries must survive: do not remove
>   existing tracks and do not change the clip's length.
>
> Save the modified `AS_TaskWalk` in place (same folder, same name), so
> the named track can be read back from the asset afterward.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-anim-track-bake/`:

- `AS_TaskWalk.uasset` — an editor-made duplicate of a stock unarmed walk
  cycle on the template mannequin skeleton (the duplication is authoring-
  time work; the agent sees only the task-folder asset). Its baseline
  float-track inventory and clip length are pinned verifier-side
  (`notes.md` §2) — whatever stock tracks it carries must survive the
  agent's edit.

Read-only context: the stock animation tree under
`Content/Characters/Mannequins/` (deny-listed for writing — the graded
asset is the task-folder duplicate, never the stock original).

Files that **do not exist**: any additional artifact is the agent's
choice and unconstrained; only the modified `AS_TaskWalk` is graded.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded fact is a static property of the
saved asset (track inventory, key times, key values, clip length), read
headless by verifier-owned editor-Python. Nothing is observed over time
(no PIE), so L2 is not declared; no rendering assertion, so L3 is not
declared.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The natural submission is content-only, so L1 is a precondition, never a
correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/kp_anim_track_bake.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with **exactly 5
named checks on every leg** (constant denominator). PASS requires all 5:

```text
task_walk_asset_resolves   /Game/Tasks/kp-anim-track-bake/AS_TaskWalk
                           loads as an animation sequence
baseline_state_intact      every pinned baseline float track is still
                           present AND the clip length matches the pinned
                           baseline within 0.01s (fails closed on the
                           unpinned sentinel)
new_named_track_exists     at least one float track exists whose name is
                           NOT in the pinned baseline inventory
new_track_varies           some new track's first-key and last-key VALUES
                           differ by more than 0.001
new_track_spans_timeline   that varying track's first key lies within the
                           opening tenth of the clip and its last key
                           within the closing tenth
```

**Read routes** (each wrapped, multi-spelling, fail-closed):

- *asset* — `unreal.EditorAssetLibrary.does_asset_exist` + `load_asset`
  on the pre-declared path; `isinstance` AnimSequenceBase, tri-state.
- *track inventory* — `unreal.AnimationLibrary.get_animation_curve_names`
  with the float track type (enum resolved multi-spelling).
- *keys* — `unreal.AnimationLibrary.get_float_keys` per new track
  (times + values arrays; the variance and span checks read KEYS, never
  interpolated samples, so a two-keys-in-one-instant submission cannot
  game an interpolated read).
- *length* — `unreal.AnimationLibrary.get_sequence_length`, falling back
  to the reflected sequence-length property.
- *baseline truth* — verifier-owned constants pinned from the authoring
  run (`BASELINE_CURVE_NAMES` / `BASELINE_LENGTH`); the `None` sentinel
  fails `baseline_state_intact` closed until the pin lands (the re-pin
  law — pins commit WITH the baseline binary).

**Every graded fact excludes the value an untouched or lazy delivery gets
for free** (the dead-gate audit):

| gate | free/untouched value | graded demand | free value inside the gate? |
|---|---|---|---|
| asset resolves | true (baseline ships) — presence alone is a DEAD gate | — (plumbing; the live gates follow) | (dead alone — by design, the substrate ships the asset) |
| baseline intact | true for an untouched asset | **also true** — this is a GUARD, not a discriminator: it fails collateral-damage submissions, not lazy ones | (guard row; the discriminating rows follow) |
| new named track | zero new tracks on the untouched asset | >= 1 | **no** |
| track varies | no new track to vary | first/last key values differ > 0.001 | **no** |
| spans timeline | no new track to span | keys reach both outer tenths | **no** |

**Score granularity.** `report.json` carries `x/5`; `overall` stays
`all(status == "pass")`.

## Reference solution metadata

- LOC range: ~10 lines of editor scripting (add a float track, key it at
  the clip's start and end, save) — deliberately the floor of T1.
- Files touched: 1 (the modified `AS_TaskWalk.uasset`).
- Senior-dev hours: 0.1–0.25.

## Anti-gaming notes

Per the amended checklist §7 the discrimination package ships no
hand-authored gaming variants; the requirements table in
`discrimination/MATRIX.md` is the soundness artifact. The failure modes it
is written against:

1. **Empty delivery.** The baseline asset grades as-shipped: zero new
   tracks — `new_named_track_exists` fails with its named token; the
   constant 5-check denominator scores the two downstream checks as
   failures too.
2. **Flat-constant track.** A single-key or constant-value track
   satisfies existence but fails `new_track_varies` (first/last key
   values within epsilon).
3. **Instant-span track.** Two keys microseconds apart with different
   values satisfies variance but fails `new_track_spans_timeline` (keys
   must reach both outer tenths of the clip) — and both checks read raw
   KEYS, so interpolation tricks have no surface.
4. **Collateral damage.** Deleting stock tracks, re-timing the clip, or
   replacing the asset wholesale with a shorter one fails
   `baseline_state_intact` against the pinned inventory/length.
5. **Renaming a stock track.** Renders as a removed baseline track (fails
   the guard) even though a "new" name appears.

## Discrimination

`discrimination/MATRIX.md` — reference-PASS / empty-FAIL legs plus the
mandatory requirements table, each requirement joined to its named check
and verbatim failure token.
