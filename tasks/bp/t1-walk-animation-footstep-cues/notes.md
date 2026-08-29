# t1-walk-animation-footstep-cues — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build). **The binary half is not
done.** This file is the contract the editor track builds against: everything
below is stated property-by-property so the assets can be authored without
re-deriving anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — an animation-notify
  row that was never implemented there.
- The source row's **Verification** and **Verification Method** cells are both
  EMPTY. Nothing was inherited; every acceptance criterion in the spec was
  designed here. The source row's `Issues` cell reads "Need a bunch of starting
  assets", which is exactly the baseline-duplication work in §1 below.
- Substrate `ThirdPerson` is forced, not chosen: the task needs the stock
  mannequin walk/jog clips, which only exist there. Cost to record — a
  ThirdPerson L1 leg measured **172 s vs 131 s** on `CraftBenchTemplate`
  because there is no warm slot for it on this box (plan §6).

## Deviations from the source row (all four are deliberate)

1. **Half 2 of the instruction is CUT.** The source row asks for the animation
   blueprint to handle the notify and print `Footstep` to the screen. That is
   ungradeable under `L1 + L2I` and is not shipped, in the prompt or in the
   checks. Full evidence in the spec's *"The source row is two halves; only the
   first half is gradeable"*; the short version, all from engine source at
   `<UE-root>`:
   - `UBlueprint`'s graph arrays are bare `UPROPERTY()`, and Python readability
     is exactly `CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable`
     (`PropertyAccessUtil.cpp:425-433`) — denied.
   - `unreal.BlueprintEditorLibrary.list_events()` is real and Python-reachable
     (`BlueprintEditorLibrary.h:229`) but cannot see the handler: its
     local-graph branch scans only `UK2Node_CustomEvent`
     (`BlueprintEditorLibrary.cpp:727`) while
     `AnimNotifyEventNodeSpawner.cpp:21` spawns the handler as a plain
     `UK2Node_Event`, and its inherited branch walks the parent chain, where
     `UAnimInstance` declares no `AnimNotify_Footstep`.
   - Even a working entry-point read would not show the *print*. "Prints to the
     screen" is a runtime observation and belongs to a PIE `L2` fixture, which
     this task deliberately does not declare.
   **When an animation-blueprint `L2` lane exists, add half 2 as a SEPARATE
   task.** Retrofitting it here would drag a map, a fixture and a placed actor
   into an asset-only task.
2. **Id is `t1-…`, not the plan's penciled `t2-footstep-notify`.** `t<N>-` is
   the tier, not the source row (the set-provenance note (internal, not shipped)); with half 2 cut, the
   remaining work is a single-concept asset edit and re-tiers to T1. The slug
   also drops "notify" because the id is agent-visible in the content path.
3. **Baselines are DUPLICATES under `Content/Tasks/<task-id>/`.** The stock
   clips live under `Content/Characters/`, which is deny-listed in
   `UE-projects/ThirdPerson/AGENT_WRITABLE.json`, so the agent cannot edit them
   in place. (`/Game/EvalTemplate`, which five other source rows name, does not
   exist anywhere in this repo.)
4. **A second, untouched clip ships alongside the walk.** The source row names one
   animation; this task ships a walk and a jog so that "you edited the clip you
   were asked about" is a graded fact rather than an accident.

---

## 1. BASELINE assets (ship in the substrate, committed, agent-writable)

Create the folder
`UE-projects/ThirdPerson/Content/Tasks/t1-walk-animation-footstep-cues/`
and put **two** duplicated animation sequences in it.

### 1a. `A_WalkForward.uasset`

**Content path:** `/Game/Tasks/t1-walk-animation-footstep-cues/A_WalkForward`

| property | required value | why the verifier cares |
|---|---|---|
| how to make it | **Duplicate** `/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd` (tracked at `UE-projects/ThirdPerson/Content/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.uasset`) into the task folder and rename to `A_WalkForward`. Do not re-import, retime or trim | `walk_timeline_length_unchanged` and `walk_frame_count_unchanged` compare the SUBMITTED clip against the stock one **read live at grade time**, so any drift introduced now becomes a false negative on the reference |
| asset type | Animation Sequence | `_load_sequence` gates on `isinstance(asset, unreal.AnimSequenceBase)` |
| skeleton | whatever the duplicate inherits (the Manny/Quinn skeleton) — do not retarget | not asserted directly; retargeting risks changing frame count |
| notify events | **ZERO.** The timeline must be completely empty | the empty leg is defined as "baseline in, `0/2` cues found". A stray inherited notify would make the empty leg pass a check it must fail, and would break `walk_carries_no_other_cues` for a correct submission |
| notify TRACKS | leave whatever the duplicate has (usually one default track). Track identity is not graded | `FAnimNotifyEvent::TrackIndex` is a bare `UPROPERTY()` and reflection-denied anyway |
| save state | saved, not dirty | — |

**Gate this baseline on one measurement first.** The clip must be **longer than
0.80 s**, or the `0.75` s cue does not fit on its timeline and the task is
impossible as written. `MF_Unarmed_Walk_Fwd` is a full forward walk cycle and is
expected to run ~1.0-1.3 s, but that is an expectation, not a measurement — read
`AnimationLibrary.get_sequence_length` on it and record the value in §5 **before**
cutting any asset. If it comes back shorter than 0.80 s, do not widen the
tolerance or move the cue: switch the baseline to a longer clip in the same
family (`MF_Unarmed_Walk_Left`, `MF_Unarmed_Walk_Bwd`, …), update `ORACLE_WALK`
in the introspect script, and re-record here. Nothing else in the task changes.

### 1b. `A_JogForward.uasset`

**Content path:** `/Game/Tasks/t1-walk-animation-footstep-cues/A_JogForward`

| property | required value | why the verifier cares |
|---|---|---|
| how to make it | **Duplicate** `/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd` into the task folder and rename to `A_JogForward` | it is the "did you edit the right clip" control |
| notify events | **ZERO** | `jog_carries_no_cues` reads exactly this |
| length / frames | not graded — leave as duplicated | — |

Both files must be **committed**, for two reasons that have bitten this repo:

- Fairness isolation physically **moves** an untracked `Content/Tasks/<id>/` out
  of the substrate the next time a *different* task is driven (plan §9.7).
- `run_task` grades from **git HEAD**, so an uncommitted baseline is invisible
  to a normal grade (use `--substrate-from-live` / `cb discriminate --wip`
  while iterating).
- `_CB_EDITOR_MARKER = "craftbench"` means an in-repo authoring editor is
  classified CraftBench-owned: `cb down` / `cb eval` / `cb view` will kill it
  unwarned. Launch via `launch_unreal_project` (its argv carries `-unattended`,
  which gates Live Coding OFF); an attended editor makes every UBT build on
  this box fail exit 6 in ~13 s.

---

## 2. REFERENCE solution

**Path on disk:**
`tasks/bp/t1-walk-animation-footstep-cues/reference/Content/Tasks/t1-walk-animation-footstep-cues/A_WalkForward.uasset`

The reference overlay carries **only `A_WalkForward.uasset`**.
`apply_submission` is copy-only with no wipe, so the untouched `A_JogForward`
falls through from the substrate — which is exactly what `jog_carries_no_cues`
should see.

Build it by taking the baseline `A_WalkForward` and adding two cues:

| step | required end state | check it satisfies |
|---|---|---|
| 1 | asset still named `A_WalkForward`, same folder, still an Animation Sequence | `walk_asset_exists` |
| 2 | a notify named exactly `Footstep` (case-sensitive) at trigger time `0.25` s | `walk_has_exactly_two_footstep_cues`, `walk_footstep_at_quarter_second` |
| 3 | a second notify named exactly `Footstep` at trigger time `0.75` s | `walk_has_exactly_two_footstep_cues`, `walk_footstep_at_three_quarter_second` |
| 4 | both are plain notifies, **not** notify STATES — zero span, no `NotifyStateClass` | `walk_footsteps_are_instantaneous` |
| 5 | nothing else on the timeline: total notify-event count is exactly 2 | `walk_carries_no_other_cues` |
| 6 | play length and frame count identical to the stock `MF_Unarmed_Walk_Fwd` | `walk_timeline_length_unchanged`, `walk_frame_count_unchanged` |
| 7 | `A_JogForward` **not** touched (do not overlay it) | `jog_asset_exists`, `jog_carries_no_cues` |

Expected reference verdict: **L2I `10/10`, overall PASS.**

### Authoring route and the one placement gotcha

The reliable route is editor Python, because it sets the time as a float
without frame snapping:

```python
import unreal
seq = unreal.EditorAssetLibrary.load_asset(
    "/Game/Tasks/t1-walk-animation-footstep-cues/A_WalkForward")
for t in (0.25, 0.75):
    unreal.AnimationLibrary.add_animation_notify_event(seq, "1", t, None)
```

`AddAnimationNotifyEvent(AnimationSequenceBase, NotifyTrackName, StartTime,
NotifyClass)` is at `AnimationBlueprintLibrary.h:240`. Passing `None` for the
class produces a **skeleton notify**, whose `NotifyName` must then be set to
`Footstep` — confirm with
`unreal.AnimationLibrary.get_animation_notify_event_names(seq)` before saving;
if the helper names it after the track instead, set `NotifyName` directly on
each `FAnimNotifyEvent` and re-read.

**The gotcha:** placing the cues through the notify PANEL snaps them to frames.
At 30 fps, `0.25` s is frame 7.5 — not a frame boundary — so the panel will
land on `0.2333` or `0.2667`, i.e. `0.0167` off. That is inside the graded
`+/-0.02` but only by `0.0033` s, which is far too little margin for a
reference solution. **Author the reference through Python, then read the times
back and record them in §5 below.** If the read-back is not within `0.002` of
`0.25`/`0.75`, do not ship the reference — fix the authoring route rather than
widening the tolerance, because widening it starts eroding the
`cues-at-wrong-times` variant.

---

## 3. Discrimination variants

Five variant `.uasset` sets, specified in `discrimination/MATRIX.md` and in each
variant folder's `README-MISSING-ASSETS.md`. Each is the reference with exactly
ONE deviation, so the matrix can attribute the FAIL to one gate:

| variant | one deviation | dies at |
|---|---|---|
| `cues-at-wrong-times/` | times `0.30` / `0.70` | `walk_footstep_at_quarter_second` |
| `ranged-cues-not-instants/` | both cues are notify STATES with non-zero spans | `walk_footsteps_are_instantaneous` |
| `extra-cues-left-on-clip/` | two extra cues named `Land` / `Step` | `walk_carries_no_other_cues` |
| `clip-retimed-to-short-stub/` | the clip itself is retimed | `walk_timeline_length_unchanged` |
| `cues-on-both-clips/` | the jog clip also gets the two cues (2 files) | `jog_carries_no_cues` |

---

## 4. Pre-flight before the first graded leg

Both blockers are **shared with the pilot**, not additive to it (plan §13.4 —
"the registry cost is shared, not additive"):

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. Any `L1+L2I` spec on disk makes CI red. Per plan §9.1 the fix
   is to replace the equality with a landability assertion **and** demonstrate
   an `L2I` key really appears in `layers_out`. Deliberately not done here — it
   is a verdict-taxonomy change and wants its own review, and the pilot files
   the same requirement.
2. **Registry bookkeeping (plan §9.2 / §12.3).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the
   six hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md` x2,
   the verifier-building skill (under `.claude/`, not shipped) x2,
   the task-authoring skill (under `.claude/`, not shipped)). This task ships **no
   `.umap`**, so the 8th claim (`inventory-maps-count`) does not fire — 7, not
   8. Do the reconciliation once for every source row that has landed, not once
   per row.

A third item that is specific to this task:

3. **`registry.py:342` turns an L2I `error` into a graded FAIL** (plan §13.2).
   This grader has more exception paths than the pilot's because it leans on a
   library rather than on reflection, so the exposure is real: a typo in a
   verifier-owned grader would score the *model*. It should be routed to
   harness-error (exit 7). Not this task's fix, but this task raises the stakes.

## 5. Calibration record

- [ ] Baseline `A_WalkForward.uasset` authored + committed (zero notifies
      confirmed via `get_animation_notify_events`).
- [ ] Baseline `A_JogForward.uasset` authored + committed (zero notifies
      confirmed).
- [x] **Stock `MF_Unarmed_Walk_Fwd` measured** and recorded here:
      play length = `1.500` s, frame count = `45`, frame rate = `30`
      fps (measured 2026-07-28, headless authoring pass). The
      `clip-retimed-to-short-stub` variant needs a target that differs
      by more than `0.10` s, and this is also the number the reference is
      implicitly pinned to.
      - The shipped `clip-retimed-to-short-stub` clip is a SUBSTITUTE, not a
        true retime: no Python route to the AnimationData controller exists
        under UE 5.8 headless (`GetController` is C++-only), so the variant is
        `MM_Jump` (`0.867` s / `26` frames) wearing the `A_WalkForward` name +
        the two perfect cues — which is exactly the "different clip wearing
        the right name" its README models. Cue read-back on both new variants:
        `0.2500` / `0.7500`.
- [ ] Reference `A_WalkForward.uasset` authored; L2I reads **10/10**.
- [ ] Trigger times read back from the saved reference: `______` / `______`.
      Must be within `0.002` of `0.25` / `0.75` — see the placement gotcha in §2.
- [ ] The six `AnimationLibrary` getters confirmed under **`-nullrhi`**
      (`-nullrhi` is unconditional for L2I on every `cb` path). All six are
      `BlueprintPure` UFUNCTIONs on an **Editor**-module library
      (`Engine/Source/Editor/AnimationBlueprintLibrary`), so they should be
      present with no plugin enabled, but only an actual
      `-ExecutePythonScript` run settles the RETURN SHAPES — the script's
      `_scalar_out` / `_array_out` split is written against
      `(return_value, out_param)` ambiguity and is the one place a shape
      surprise turns into a wrong number rather than an exception.
- [ ] `notify_name` / `notify_state_class` confirmed readable via
      `get_editor_property` from headless Python (both are flagged
      `EditAnywhere` + `BlueprintReadOnly` / `BlueprintReadWrite` in
      `AnimTypes.h`, so this should hold; the script tries both the
      pythonized and the C++ spelling).
- [ ] Discrimination executed: reference PASS, empty + 5 variants FAIL, each via
      its MATRIX substring.
- [ ] **Measured L2I leg wall-clock recorded here.** Still an open question from
      plan §1/§6 ("does an L2I leg actually cost ~131 s like an L2 leg?"); if the
      pilot has not answered it by then, this task is the second chance.
