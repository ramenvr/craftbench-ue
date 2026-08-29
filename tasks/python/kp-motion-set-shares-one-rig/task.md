---
id: kp-motion-set-shares-one-rig
substrate: ThirdPerson
set: python
tier: T2
capability_bucket: Asset Management
category: other
layers: [L1, L2I]
introspect: [kp_motion_set_shares_one_rig.py]
---

# kp-motion-set-shares-one-rig

**The from-scratch animation-asset lane** (from a row in an earlier internal
task list, not shipped). The first task whose deliverable is a set of
**newly created animation assets** rather than an edit to a supplied one, and
the first to grade **cross-asset rig assignment** — the fact that three
separately-authored assets all point at the same rig.

The gap it fills is exact: `AnimSequenceFactory`, `AnimMontageFactory` and
`AnimBlueprintFactory` appear nowhere in `tasks/` or `tools/`.
`kp-anim-track-bake` only *edits* a clip that is handed to it, and
`t1-walk-animation-footstep-cues` explicitly forbids altering the shipped
clips. Nothing in the tree asks an agent to make an animation asset.

## Primary concept

- `asset-creation` — creating animation assets and binding them to a skeleton
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-assets-in-unreal-engine)

The load-bearing capability is **cross-asset consistency**: three assets, each
created through a different factory, each of which silently accepts a different
rig, all of which must agree. Adjacent in-scope concept: `asset-management`
(the deliverables live in the task's own content folder). None of these names
appears in the prompt.

## Prompt given to the agent

> This project has a character rig at
> `Content/Tasks/kp-motion-set-shares-one-rig/SK_TaskRig`. It is an input: read
> it, do not rename, move, modify or delete it.
>
> Produce three new animation assets in that same folder, and give them exactly
> these names:
>
> - `A_TaskMotion` — a motion clip.
> - `AM_TaskAction` — an assembled action that plays `A_TaskMotion`.
> - `ABP_TaskLogic` — the per-frame animation logic asset for a character.
>
> Every one of the three must be built for the rig named above, not for any
> other rig in the project. Save all three where they are named, so the folder
> ends up holding the rig plus exactly those three new assets.
>
> The contents of the motion clip are not graded — an empty clip is fine. What
> is graded is that the three assets exist under those names, that each is
> built for that rig, and that the assembled action really plays the clip you
> made.

## Workspace state pre-task

Substrate content that **exists**:

- `Content/Tasks/kp-motion-set-shares-one-rig/SK_TaskRig.uasset` — the task's
  own rig. Authored by duplicating the stock `SK_Mannequin`, so it is a real,
  fully-formed skeleton; only its PATH differs from the stock one. That
  difference is the whole discriminator (see *Anti-gaming*).

Files that **do not exist** (the correct end state produces them):

- `Content/Tasks/kp-motion-set-shares-one-rig/A_TaskMotion.uasset`
- `Content/Tasks/kp-motion-set-shares-one-rig/AM_TaskAction.uasset`
- `Content/Tasks/kp-motion-set-shares-one-rig/ABP_TaskLogic.uasset`

Out of scope: no C++, no level, no placed actor, no functional test, no config.
`Content/Tasks/` is the `ThirdPerson` substrate's agent-writable carve-out
(`UE-projects/ThirdPerson/AGENT_WRITABLE.json`).

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of the
submitted assets (existence, class, rig reference, one asset-to-asset link).
No PIE, no world.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition, never a correctness
signal.

### L2I — Structural assertion

`tools/verify-single/introspect/kp_motion_set_shares_one_rig.py` runs headless
under `-nullrhi`, read-only, and prints one verdict block. **Exactly 7 checks on
every leg** (constant denominator). PASS requires all 7:

```text
clip_present           C1  A_TaskMotion exists and its class is the motion-clip
                           class            [LIVE - absent at baseline]
montage_present        C2  AM_TaskAction exists and its class is the assembled-
                           action class     [LIVE - absent at baseline]
animbp_present         C3  ABP_TaskLogic exists and its class is the animation-
                           logic class      [LIVE - absent at baseline]
clip_uses_task_rig     C4  A_TaskMotion's rig reference == SK_TaskRig
                                            [LIVE - a duplicate of shipped
                                             content reports SK_Mannequin]
montage_uses_task_rig  C5  likewise AM_TaskAction
animbp_uses_task_rig   C6  likewise ABP_TaskLogic
montage_plays_the_clip C7  AM_TaskAction's first animation reference ==
                           A_TaskMotion     [LIVE - an empty montage reports
                                             None]
```

**Why the rig is task-owned, which is the central design fact.** Measured
2026-08-13 on UE 5.8: the engine REFUSES to create any of the three assets
without a rig — the clip fails with a rig-hierarchy initialisation error, the
montage factory returns nothing, and the animation-logic asset's null-rig
template mode is not reachable from editor scripting at all. So if the task
anchored to the stock rig, C4-C6 could not fail for any submission that
produced the assets, and 43% of the score would be **dead gates**. Shipping the
task its own rig makes the cheapest wrong answer — duplicate the shipped
Mannequin animations — land on the stock rig and fail C4-C6 by name.

**Dead-gate audit** (house law). Every check is LIVE against the lazy state:
the untouched baseline scores a genuine **0/7** (three assets absent, so their
anchors and the link are unchecked and fail), and the empty submission scores
**0/7** likewise. No check equals a default or baseline state. There is
deliberately **no `rig_intact` check**: the submission overlay is copy-only, so
a deleted baseline rig is restored before grading and the check could never
fail — and overwriting the rig cannot help a submission either, since C4-C6
compare the rig's PATH, which an overwrite does not change.

**Ungraded by design, each because its failing state is unreachable rather
than because it is uninteresting** (all four established by live spike):

- **Compile status of the animation-logic asset.** The status field is
  *transient*, so a grader reads what its own load produced, never what was
  shipped; and the factory compiles at creation, so every probe returned
  up-to-date, including a child of a shipped asset.
- **Clip duration / retiming.** No editor-scripting route to the animation data
  controller exists; a factory-fresh clip is one frame. A duration gate would be
  unwinnable, so the prompt does not ask for one and says the clip's contents
  are not graded.
- **Animation graph content.** Authoring graph nodes needs a route stock editor
  scripting does not have, so the prompt never asks the logic asset to *play*
  anything — only to be built for the rig.
- **A rig authored from scratch.** Unreachable (the factory is not creatable
  from script, its input property is reflection-denied) and its success path
  writes into a deny-listed folder. The rig is therefore shipped, not requested.

**Score granularity.** `report.json` carries `x/7`. Reported, not gating.

## Reference solution metadata

- LOC range: **0** lines of shipped code. The deliverable is three assets.
  (`authoring/author_all_assets.py` is the verifier-side recipe, not a
  submission.)
- Files touched: 3 created.
- Senior-dev hours: 0.3–0.7 — the work is knowing that each factory takes its
  own rig argument and that the assembled action derives its rig from the clip
  it is given.

## Anti-gaming notes

1. **Duplicate the shipped animations instead of authoring.** *Failure mode*:
   copy the stock Mannequin clip/montage/logic assets into the task folder
   under the required names. Names and classes then satisfy C1-C3 for three
   calls of work. *Defense*: every duplicate keeps the **stock** rig reference,
   so C4-C6 fail with `MOTIONSET_WRONG_RIG expected=…/SK_TaskRig got=…/SK_Mannequin`.
   Proven live on 2026-08-13, both directions. **This is the defense the whole
   task-owned-rig design exists to provide.**
2. **Create the assets but skip the link.** *Failure mode*: three correctly
   anchored assets, but the assembled action is empty — cheaper than assembling
   one. *Defense*: C7 requires the first animation reference to be the authored
   clip; an empty action reports nothing and fails `MOTIONSET_LINK_WRONG`.
3. **Point the action at a shipped clip.** *Failure mode*: assemble the action
   from a stock animation, which is easier than making one. *Defense*: C7
   compares against `A_TaskMotion` exactly, and C5 additionally fails because an
   action assembled from a stock clip derives the **stock** rig.
4. **Wrong asset kinds under the right names.** *Failure mode*: create three
   cheap assets of any type and name them correctly. *Defense*: C1-C3 check the
   class, not just existence (`MOTIONSET_WRONG_CLASS`).
5. **Accepted residual, recorded honestly**: the clip's CONTENT is ungraded, so
   an empty clip passes — as the prompt says outright. There is no editor-
   scripting route to write curve data (see *Ungraded by design*), so grading it
   would make the task unwinnable rather than harder. A submission that authors
   a *real* motion and one that authors an empty clip are indistinguishable
   here, and that is a deliberate, disclosed limit rather than an oversight.

## Hidden invariants

- The check denominator is fixed at 7 on every leg, including the untouched
  baseline (a genuine 0/7) and a no-editor-python import. A submission cannot
  improve its reported `tests_passed/tests_run` by making checks unreachable.
- Anchors are read as single object references, so "built for exactly one rig"
  is a property of the asset type and needs no separate check.
- Every verifier-side failure path emits a distinct token from the grader's
  `UNCREDITED_TOKENS` tuple, which appears in **no** discrimination-matrix row,
  so a broken probe can never be credited as a variant's named failure.
- `get_first_anim_reference` returning nothing is a SUCCESSFUL answer meaning
  "no segment", not an unavailable route; the grader does not fall through to
  its fallback in that case, so a real empty-action FAIL cannot be laundered
  into an uncredited probe error.
- `AssetRegistry.get_dependencies` is deliberately NOT a read route: it works on
  a shipped montage but raises on one created in the same session, and a route
  that behaves differently at authoring time than at grade time is how a false
  FAIL gets manufactured.
- Echoed asset paths and class names are agent-controlled, so they are
  marker-stripped and length-capped before reaching a check detail.
