---
id: t1-walk-animation-footstep-cues
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: animation
layers: [L1, L2I]
introspect: [walk_animation_footstep_cues.py]
---

# t1-walk-animation-footstep-cues

The second `layers: [L1, L2I]` task in the repo, built in the shape the pilot
`bp/t1-hero-blueprint-copy-with-flashlight` established: committed baseline
`.uasset`s under `Content/Tasks/<task-id>/` -> the agent edits one of them in
place -> one verifier-owned introspect script asserts named structural checks.
No map, no fixture C++, no scaffold actor.

### Provenance and the deliberate scope cut

Imported from an earlier internal task list (not shipped): an animation-notify
row that was never implemented there. The source row's
**Verification cell is empty** and its Verification-Method cell is empty, so
there were no acceptance criteria to import — everything in *Verifier
specification* below was designed here.

### The source row is two halves; only the first half is gradeable

The source row instruction is:

> "On the walk animation, add two footstep notifications to the animation
> timeline — one at a quarter of a second in and one at three-quarters of a
> second in — and name both of them 'Footstep'. Then, on the character's
> animation blueprint, handle that footstep notification so that whenever it
> fires it prints the message 'Footstep' to the screen."

**Half 1 (the animation clip) ships. Half 2 (the animation blueprint) is cut**,
from the graded checks *and* from the prompt. The reason is not squeamishness;
it is that no read route exists for it under `L1 + L2I`, and this repo's law is
that a claim the verifier cannot check must not be made. Three routes were
investigated against UE 5.8 engine source on this box before cutting:

1. **Walk the animation blueprint's event graph.** `UBlueprint`'s graph arrays
   (`UbergraphPages`, `FunctionGraphs`, `EventGraphs`) are bare `UPROPERTY()`
   with no `CPF_Edit` / `CPF_BlueprintVisible` flag, and Python readability is
   exactly `CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable`
   (`PropertyAccessUtil.cpp:425-433`). Denied.
2. **`unreal.BlueprintEditorLibrary.list_events()`.** This *is* a real,
   `BlueprintCallable`, Python-reachable UFUNCTION
   (`Editor/BlueprintEditorLibrary/Public/BlueprintEditorLibrary.h:229`) that
   returns one `FBlueprintFunctionInfo` per event, `Name` and `bIsImplemented`
   both `BlueprintReadOnly` — so it looked like the answer. It is not. Its
   local-graph branch scans **only** `UK2Node_CustomEvent`
   (`BlueprintEditorLibrary.cpp:727`), while an AnimNotify handler node is
   spawned as a plain `UK2Node_Event` —
   `AnimNotifyEventNodeSpawner.cpp:21` sets
   `NodeSpawner->NodeClass = UK2Node_Event::StaticClass()` and
   `CustomEventName = "AnimNotify_Footstep"`. Its other branch iterates the
   parent-class chain, and `UAnimInstance` declares no `AnimNotify_Footstep`.
   So the handler is invisible to `ListEvents` in both branches. (The private
   helper `HasEventNodeFor` at `:658` *does* match `UK2Node_Event` by
   `CustomFunctionName`, but it is only consulted for names already found in
   the parent chain, and it is not a UFUNCTION.)
3. **Even if 1 or 2 worked, they prove the wrong thing.** They would show that
   an entry point named `AnimNotify_Footstep` exists — not that anything is
   wired to it, and certainly not that it prints `Footstep` to the screen.
   "Prints to the screen" is a *runtime* observation; it belongs to L2 in a PIE
   world, which this task deliberately does not declare (no map, no fixture, no
   placed actor). Shipping a check for the entry point alone would be a gate
   that reads as "the animation blueprint handles the footstep" while actually
   grading "a node with the right title was dropped on a graph".

So the graded deliverable is the animation clip, and it is graded hard: not
just "two cues named Footstep exist" but their exact placement, their
instantaneity, the absence of anything else on that timeline, the clip's own
length and frame count against the untouched stock original, and the silence of
its sibling clip. That is ten named checks on one asset. **When a PIE-driven
`L2` lane for animation-blueprint behaviour exists, half 2 should be added as a
separate task rather than retrofitted here** — its verification shape (drive a
character, watch for an on-screen message at t=0.25 s) has nothing in common
with this one.

### Other deliberate divergences from the source row

1. **Id.** The source row's `t9-` is a row index; this repo's `t<N>-` is a tier
   (the set-provenance note (internal, not shipped)). The plan's §11.1 table pencilled in
   `t2-footstep-notify` at **T2**; with half 2 cut, the remaining work is a
   single-concept asset edit — 30-60 minutes for a fluent UE5 dev — so it is
   retiered to **T1**. The slug also drops the word "notify", which names the
   mechanism: the id is agent-visible (it appears in the content path the
   prompt quotes), and the set-provenance note (internal, not shipped) requires it to name the outcome,
   not the operation.
2. **Content path.** The source row's start state is "Third Person Template", and
   the stock walk clip lives at
   `Content/Characters/Mannequins/Anims/Unarmed/Walk/`, which is **deny-listed**
   in `UE-projects/ThirdPerson/AGENT_WRITABLE.json`. The agent therefore cannot
   edit the stock clip in place, which is what the source row's "Need a bunch of
   starting assets" issue is really about. Baselines are **duplicates** under
   the agent-writable, fairness-pruned `Content/Tasks/<task-id>/`, per repo
   convention. (`/Game/EvalTemplate`, which five other source rows name, does not
   exist anywhere in this repo.)
3. **A second, untouched clip ships alongside the walk.** The source row names one
   animation. This task ships two — a walk and a jog — because "put the cue on
   the clip you were asked about" is otherwise ungraded, and spraying cues over
   every clip in the folder is the cheapest way to satisfy a single-asset check
   by accident.

> **Note on the behavior-only rule (Hard Rule #2).** Like the pilot and
> `t0-sanity-bp-log-on-beginplay`, this task names the concrete deliverable
> asset paths and the one cue name the verifier keys on. That is the standard,
> precedented exception for asset-deliverable tasks whose whole point *is*
> producing specific asset content — naming the path lets the verifier load two
> assets directly instead of scanning content. Everything else stays
> behavior-only: no class name, no asset-type name, no editor operation. The
> prompt says what the clip must *announce* and *when*; it never says
> "notify", "anim notify", "notify state", "notify track", or names any panel
> or menu.

## Primary concept

- `anim-anim-notify` — Animation Blueprint Event Nodes
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprint-event-nodes-in-unreal-engine)

The load-bearing capability is authoring **timed events embedded in an
animation asset**: understanding that an animation clip can dispatch a named,
instantaneous event to gameplay at an exact point on its own timeline, that
this is distinct from an event that occupies a span of the timeline, and that
the placement is a number in seconds rather than an eyeballed frame. The
concept's second half — consuming that event in an animation blueprint — is out
of scope here for the reason given above.

## Prompt given to the agent

> This project ships two animation clips for the player figure, in the folder
> `Content/Tasks/t1-walk-animation-footstep-cues/`: `A_WalkForward` (one
> forward walk cycle) and `A_JogForward` (one forward jog cycle). Neither clip
> currently tells the rest of the game anything at all while it plays.
>
> Make the walk clip report footfalls. While `A_WalkForward` plays, it must
> raise an event named exactly `Footstep` a quarter of a second in, and raise a
> second event, also named exactly `Footstep`, three-quarters of a second in —
> so that gameplay watching the walking figure is told, at those two moments,
> that a foot has landed. Each of the two is an **instant**: it happens at that
> one moment and does not occupy a stretch of the clip, so neither has a start
> and a separate end.
>
> Those two must be the only things `A_WalkForward` raises — no third one, and
> nothing under any other name. Do not retime, re-import, trim, extend or
> otherwise alter the clip's motion: when you are done it must still run for
> exactly as long, and contain exactly as many frames, as it does today.
> `A_JogForward` must be left completely silent — it must raise nothing at all.
> Save your work.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t1-walk-animation-footstep-cues/`:

- `A_WalkForward.uasset` — an animation clip of one forward walk cycle for the
  project's player figure. It is an exact duplicate of the clip the project
  already ships for that motion, with its length, frame count, frame rate,
  motion data and rig association unchanged. **It raises nothing on its
  timeline** — the timeline is completely empty of events.
- `A_JogForward.uasset` — an animation clip of one forward jog cycle for the
  same figure, likewise an exact duplicate of the shipped one, and likewise
  raising nothing on its timeline.

Both ship with the project as committed, saved content.
`Content/Tasks/<task-id>/` is the agent-writable Content carve-out of the
`ThirdPerson` substrate (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`) and is
where this task's content belongs; fairness isolation keeps this task's folder
while hiding every other task's.

Files that **do not exist** (nothing has to be created):

- none. The whole deliverable is an edit to `A_WalkForward.uasset`. A
  submission that also carries an unmodified `A_JogForward.uasset` is
  equivalent to one that omits it — `apply_submission` is a copy-only overlay
  with no wipe, so anything the submission does not carry falls through from
  the substrate.

Out of scope / not needed:

- No C++ is required or expected. No level, no placed actor, no functional
  test. `Content/Maps/`, `Config/`, `Content/Characters/`,
  `Content/ThirdPerson/` and `Content/Input/` are deny-listed — the agent
  neither can nor needs to touch them, and in particular the **stock** clips
  the two baselines were duplicated from are unreachable to a submission.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved `.uasset` (which timed events a clip carries, what
they are named, at what second, over what span, and the clip's own length and
frame count), so it is read by verifier-owned editor-Python reflection over the
submitted assets — not by rendering, ticking, or a PIE world. L2 is deliberately
**not** declared: there is nothing to observe over time, and a fixture would
need a map and a placed actor this task has no use for. This is also precisely
why the source row's animation-blueprint half is cut rather than half-graded.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/walk_animation_footstep_cues.py` runs headless
via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 10
named checks on every leg** (a constant denominator, so the per-check
`tests_passed/tests_run` the registry already records is comparable across
submissions). PASS requires all 10:

```text
walk_asset_exists                     /Game/Tasks/<id>/A_WalkForward resolves
walk_has_exactly_two_footstep_cues    exactly 2 timeline events are named
                                      "Footstep" (case-sensitive)
walk_footstep_at_quarter_second       exactly one of them triggers at
                                      0.25 s (+/-0.02)
walk_footstep_at_three_quarter_second exactly one of them triggers at
                                      0.75 s (+/-0.02)
walk_footsteps_are_instantaneous      both have zero span (+/-0.001) and
                                      neither is backed by a ranged-event object
walk_carries_no_other_cues            the clip's TOTAL timeline-event count is
                                      2 — nothing else was left on it
walk_timeline_length_unchanged        the clip's play length still equals the
                                      untouched stock clip's (+/-0.01 s)
walk_frame_count_unchanged            its frame count still equals the
                                      untouched stock clip's, exactly
jog_asset_exists                      /Game/Tasks/<id>/A_JogForward resolves
jog_carries_no_cues                   it carries zero timeline events
```

**Read routes.** Every one was checked against UE 5.8 engine source at
`<UE-root>` while authoring; the `AnimationLibrary` family was additionally
confirmed live on UE 5.8.0-55116800 in the plan's §10 probe.

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`, then
  `load_asset` with an `isinstance(..., unreal.AnimSequenceBase)` gate so a
  non-animation asset at the right path cannot be read as "an animation with no
  events".
- *the timeline events* — `UAnimSequenceBase::Notifies` is a bare `UPROPERTY()`
  and therefore reflection-denied (Python readability is exactly
  `CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable`,
  `PropertyAccessUtil.cpp:425-433`). The public route is used instead:
  `unreal.AnimationLibrary.get_animation_notify_events` and
  `get_animation_notify_event_names`, both `BlueprintPure` UFUNCTIONs at
  `Editor/AnimationBlueprintLibrary/Public/AnimationBlueprintLibrary.h:232`
  and `:236`. The UCLASS carries `meta=(ScriptName="AnimationLibrary")` (`:65`),
  which is why the Python spelling drops the `Blueprint`. It is an **Editor**
  module, always loaded in `UnrealEditor-Cmd`; no plugin has to be enabled.
- *event name* — `FAnimNotifyEvent::NotifyName` is
  `EditAnywhere, BlueprintReadOnly` (`Runtime/Engine/Public/Animation/AnimTypes.h`)
  and is read directly.
- *trigger second* — `AnimationLibrary.get_anim_notify_event_trigger_time`
  (`:318`).
- *span* — `AnimationLibrary.get_anim_notify_event_duration` (`:322`). Note the
  struct's own `Duration` field is a bare `UPROPERTY()` and is **denied**, which
  is exactly why the UFUNCTION is used. `NotifyStateClass`
  (`EditAnywhere, Instanced, BlueprintReadWrite`) is read as a corroborating
  second signal that can only *add* a failure.
- *length and frame count* — `AnimationLibrary.get_sequence_length` (`:598`)
  and `get_num_frames` (`:73`).

**The length/frame oracle is the stock clip, not a hard-coded number.** Checks
7 and 8 compare the submitted clip against
`/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd`, read live
by the verifier. That path is agent-**deny**-listed
(`AGENT_WRITABLE.json`: `Content/Characters/`) and is not pruned by fairness
isolation, whose per-task roots are only `Content/Tasks`, `Content/Maps` and the
two `Source/*/Tasks` roots (`tools/run-agent/fairness.py:85`) — so it is a value
the submission provably cannot have moved. Deny-listing governs agent **writes**,
not verifier reads (the same argument the plan makes for R8 in §12.2). Using the
live stock asset instead of a literal also means the check cannot silently rot
if the template's animation content is ever updated.

**Identity is by pre-declared content path and pre-declared event name, never
by class.** The two asset paths and the name `Footstep` are fixed by the spec
and stated in the prompt. The agent may reach the outcome through the editor's
timeline panel, through editor Python
(`AnimationLibrary.add_animation_notify_event`), or by any other means, and
may put the two events on any timeline track it likes — track identity is not
graded (`FAnimNotifyEvent::TrackIndex` is reflection-denied anyway, and a
track is a visual-layout concern, not a behavioural one).

**Why the placement tolerance is +/-0.02 s.** The graded property is "a quarter
of a second in", and the two graded moments are 0.5 s apart, so the tolerance
only has to be tight enough to separate them from each other and from the clip
boundaries. `+/-0.02` is a little over half a frame at 30 fps: it absorbs the
notify panel's frame snapping and `FAnimNotifyEvent`'s `TriggerTimeOffset`
(which is non-zero only for events pinned to the very start or end of a clip),
while still failing an event dropped on an eyeballed foot-contact frame.

**Why "exactly one at 0.25" rather than "at least one".** Two events both at
0.25 s would otherwise satisfy check 3 and fail only check 4, giving a
misleading `9/10`. Requiring exactly one match per moment makes the pair of
checks report the actual shape.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/10` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2).

**Fail-closed note specific to this task.** The pilot's negative checks could
lean on "a Blueprint always has at least one subobject, so an empty walk is a
broken walk". That guard is **not available here**: zero timeline events is a
perfectly legitimate state for an animation clip, and it is the state
`jog_carries_no_cues` is looking for. The script therefore demands, before
crediting silence: the accessor exists; it returns a sequence type; the
independent `get_animation_notify_event_names` accessor also exists, also
returns a sequence, and *agrees about emptiness*; and the object itself read
back as an `AnimSequenceBase` with a positive length. Any violation raises and
the check records a `*_READ_ERROR` / `*_UNAVAILABLE` token that appears in no
MATRIX row, so a broken UE API surfaces as an uncredited FAIL rather than as a
free PASS.

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is one edited `.uasset`.
- Files touched: 0 created, 1 modified
  (`Content/Tasks/t1-walk-animation-footstep-cues/A_WalkForward.uasset`).
- Senior-dev hours: 0.3-0.7 (open the clip, place two named events at exact
  seconds rather than at snapped frames, confirm they are instants and not
  spans, confirm nothing else is on the timeline, save — plus checking the jog
  clip really was left alone).

## Anti-gaming notes

1. **Claimed, not done.** *Failure mode*: the agent reports that the footsteps
   were added — or adds them only in an unsaved editor session — and the clip
   on disk is still the untouched baseline. *Defense*: the verdict is read only
   from the submitted bytes. `walk_has_exactly_two_footstep_cues` fails with
   `WALK_FOOTSTEP_COUNT_WRONG found=0`, and three dependent checks fan out on
   the same root cause. Note that "unsaved" is not a separate check and does not
   need to be: the runner grades a file overlay materialized onto a clean
   substrate, so unsaved editor state never reaches the grader — it presents as
   the baseline bytes and fails here.
2. **Placed by eye instead of by the clock.** *Failure mode*: the agent scrubs
   the clip, finds the frames where the feet visually contact the ground, and
   drops the two events there — which is what a human animator would do and is
   *not* what was asked. It is also what happens if the events are snapped to
   the nearest keyframe without checking the resulting second. *Defense*:
   `walk_footstep_at_quarter_second` (`WALK_CUE_NOT_AT_QUARTER_SECOND`) and
   `walk_footstep_at_three_quarter_second`
   (`WALK_CUE_NOT_AT_THREE_QUARTER_SECOND`) are two independent checks pinned to
   the asked-for seconds, and both print the full observed time list so a
   near-miss is diagnosable rather than mysterious.
3. **A span dressed as an instant.** *Failure mode*: the agent uses the ranged
   flavour of a timeline event — the one with a beginning and an end — because
   it is adjacent in the same menu and looks identical once placed. At runtime
   it behaves completely differently: it fires begin/tick/end rather than a
   single footfall. *Defense*: `walk_footsteps_are_instantaneous`
   (`WALK_CUE_NOT_INSTANTANEOUS`) reads the span through the UFUNCTION getter
   and requires zero, and independently requires that no event is backed by a
   ranged-event object. Both signals must agree; the corroboration can only add
   a failure. This is the one check whose passing value (`0`) is also the
   engine's default for the *instant* flavour — it is retained anyway because
   the two authorable shapes it separates are both real and both reachable
   from the same editor menu (see *Dead-gate audit* below).
4. **Shotgun the timeline.** *Failure mode*: the agent sprays events across the
   clip so that two of them happen to land near the right seconds, or leaves
   scratch events behind after iterating. *Defense*: two checks, in opposite
   directions. `walk_has_exactly_two_footstep_cues` requires the `Footstep`
   count to be exactly 2 (six of them fails, even if two are correctly placed),
   and `walk_carries_no_other_cues` (`WALK_CUE_TOTAL_WRONG`) requires the
   clip's *total* event count to be 2, so debris under any other name fails too.
   The prompt states this requirement explicitly, so it is a graded instruction
   and not a hidden trap.
5. **Move the goalposts, or hit every target.** *Failure mode (a)*: the clip is
   retimed, trimmed, re-imported or replaced with a short stub so that placing
   an event "a quarter of a second in" becomes trivial or lands somewhere
   convenient. *Failure mode (b)*: the agent cannot tell which clip was meant,
   so it puts the footsteps on both. *Defense*: `walk_timeline_length_unchanged`
   (`WALK_LENGTH_CHANGED`) and `walk_frame_count_unchanged`
   (`WALK_FRAME_COUNT_CHANGED`) compare against the untouched **stock** clip,
   which lives behind a deny prefix the submission cannot write; and
   `jog_carries_no_cues` (`JOG_HAS_CUES`) fails the moment the sibling clip is
   touched. `jog_asset_exists` guards it fail-closed, so deleting the sibling
   is not a way to satisfy "the sibling is silent".

### Dead-gate audit

Per the plan's §12.6 lesson (the pilot's source row asserted `intensity == 5000`,
which is UE 5.8's engine default for every local light and therefore graded
nothing), every numeric this task asserts was checked against the engine
default before being trusted. The source row's own Verification cell was empty,
so there was nothing inherited to audit; these are this task's own numbers:

| assertion | engine default | verdict |
|---|---|---|
| trigger time `0.25` / `0.75` s | `FAnimNotifyEvent`'s link value defaults to `0.0`; a freshly added event lands where it is dropped | **live** — 0.25 and 0.75 are not reachable by accident |
| `Footstep` count `== 2` | a duplicated clip carries whatever the original had; both baselines ship **zero** events | **live** |
| total event count `== 2` | same | **live** |
| span `== 0` | `FAnimNotifyEvent()` initialises `Duration(0)` (`AnimTypes.h`), so this *is* the default for the instant flavour | **retained with justification** — it is not a dead gate because it separates two authorable states that both come out of the same editor menu: an instant event (`0`) and a ranged one (`> 0`). The check has real discriminating power against anti-gaming note #3 and is exercised by the `ranged-cues-not-instants` variant. It would be dead only if the ranged flavour were unauthorable, which it is not |
| length / frame count `== stock` | not a default at all — read live off the deny-listed stock asset | **live** |

## Hidden invariants

- `walk_carries_no_other_cues`, `walk_timeline_length_unchanged`,
  `walk_frame_count_unchanged` and `jog_carries_no_cues` are all stated in the
  prompt, so none of them is a hidden trap — but they are evaluated
  **independently of whether the two footsteps are correct**. An agent that
  places both cues perfectly and leaves a third one behind, or that gets the
  walk clip right by re-importing it at a different length, still fails, and it
  fails through a differently named assertion than any placement mistake, so
  the discrimination matrix can tell the two apart.
- The length/frame oracle is read from a path the submission cannot write. A
  submission cannot make checks 7 and 8 agree by changing the thing they are
  compared against.
- The check denominator is fixed at 10 on every leg, including a submission
  that deletes both clips. A submission cannot improve its reported
  `tests_passed/tests_run` by making checks unreachable — the crash-shaped
  "fewer checks ran, so the ratio looks better" path is closed by construction.
- `jog_carries_no_cues` is the only check that can pass on an *absence*. It is
  guarded three ways (the accessor must exist, two independent accessors must
  agree, and the object must read back as a real animation with positive
  length), and its failure tokens are disjoint from every MATRIX substring, so
  a UE API break can never be scored as "the sibling clip is silent".
