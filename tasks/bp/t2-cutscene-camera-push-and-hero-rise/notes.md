# t2-cutscene-camera-push-and-hero-rise — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build). **The binary half is not
done.** This file is the contract the editor track builds against: everything
below is stated property-by-property so the assets can be authored without
re-deriving anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — a sequencer row that
  was never implemented there. Its start state: *Empty Project*.
- **The source row's `Verification` cell is empty.** No acceptance criteria were
  ever written for this row, so every check in the spec is designed here; the
  twelve checks in `task.md` are that answer.
- Row status history: this was the highest-risk row of the import — no MCP
  sequencer tool at all, zero introspect precedent — and was upgraded to amber
  after the live probe found the full sequencer *introspection* surface
  present. This
  task is that upgrade cashed in. MCP still has no sequencer **authoring**
  tool, so the reference and the variants must be built through
  `execute_unreal_python` (or by hand in the Sequencer tab), not through a
  first-class MCP call.
- Substrate `ThirdPerson` is the owner's choice for the imported set. Nothing in
  the task needs the third-person character stack; the cost is real and should
  be recorded: a ThirdPerson L1 leg measured **172 s vs 131 s** on
  `CraftBenchTemplate` because there is no warm slot for it on this box
  (plan §6). If the imported set later moves to `CraftBenchTemplate`, this task
  moves with a one-key front-matter edit and no other change — nothing in the
  spec or the introspect script depends on the substrate.

## Deviations from the source row (all five are deliberate)

1. Id is `t<tier>-<outcome>`, not the source row's row index. See
   the set-provenance note (internal, not shipped).
2. `/Game/EvalTemplate/` -> `/Game/Tasks/<task-id>/`. The source row's folder does
   not exist anywhere in the repo and is outside every writable prefix.
3. **The camera and `EvalHero` are SPAWNED BY the sequence, not placed in the
   level.** The source row's first sentence ("in the current level, place a cube
   actor at the origin and name it EvalHero") is level state, which this
   harness cannot grade: `map_locator.locate_map` searches only
   `Content/Maps/`, `Content/Maps/` is deny-listed to the agent, and
   `apply_submission` is a copy-only file overlay with no way to express a
   level edit (plan §4/O3, §3.6/O2). Scoping the whole deliverable into the
   sequence asset makes it gradeable **and** makes it a stronger property. The
   API supports it in both of 5.8's spawnable representations — see §3 below.
4. **Six seconds at 24 fps, not five at 30.** Both source-row numbers are
   engine defaults. Evidence, read from `<UE-root>`:
   - `Engine/Source/Editor/MovieSceneTools/Private/MovieSceneToolsProjectSettings.cpp:9-10`
     — `DefaultStartTime(0.f), DefaultDuration(5.f)`, and
     `Engine/Source/Editor/UnrealEd/Private/Factories/LevelSequenceFactoryNew.cpp`
     stamps exactly those onto every brand-new sequence's playback range.
   - `Engine/Source/Runtime/LevelSequence/Private/LevelSequenceProjectSettings.cpp:11`
     — `DefaultDisplayRate("30fps")`, applied by `ULevelSequence::Initialize`
     (`LevelSequence.cpp:115-117`).

   So "five seconds long at thirty frames per second" is satisfied by a
   sequence the agent created and then never touched. **This is the one call a
   human should confirm before the assets are cut**, because reverting it
   means re-authoring the reference and all five variants. To revert: change
   `EXPECTED_FPS_NUM`, `EXPECTED_END_S`, the check id
   `sequence_display_rate_24fps`, the two numbers in the prompt and in the
   Verifier-specification block, the dead-gate table, and this section — and
   accept that two of the twelve checks then grade nothing.
5. **Camera rotation and fade colour are not asserted.** Both are engine
   defaults (rotation `(0,0,0)` for any actor; `FadeColor(FLinearColor::Black)`
   at `MovieSceneFadeSection.cpp:16`). Recorded in the spec's dead-gate table
   so nobody "adds the missing check" later.

---

## 1. BASELINE asset

**There is none.** This task ships nothing in the substrate. Do not create
`UE-projects/ThirdPerson/Content/Tasks/t2-cutscene-camera-push-and-hero-rise/`
— the agent creating that folder is part of the deliverable, and an empty
committed folder is not representable in git anyway.

That removes the pilot's most expensive serialized step and both of its
work-loss hazards for the *baseline*. The hazards still apply to the
**reference and variant** assets while they are being authored inside the
substrate before being copied out (plan §9.7):

- Fairness isolation physically **moves** an untracked `Content/Tasks/<id>/`
  out of the substrate the next time a *different* task is driven. Copy the
  asset out to `tasks/bp/.../reference/` and commit it as soon as it exists.
- `run_task` grades from **git HEAD**, so an uncommitted asset is invisible to
  a normal grade (use `cb discriminate --wip` while iterating).
- `_CB_EDITOR_MARKER = "craftbench"` means an in-repo authoring editor is
  classified CraftBench-owned: `cb down` / `cb eval` / `cb view` will kill it
  unwarned. Launch via `launch_unreal_project` (its argv carries `-unattended`,
  which gates Live Coding OFF); an attended editor makes every UBT build on
  this box fail exit 6 in ~13 s.

---

## 2. REFERENCE solution

**Path on disk:**
`tasks/bp/t2-cutscene-camera-push-and-hero-rise/reference/Content/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene.uasset`
**Content path:**
`/Game/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene`

One asset, nothing else in the overlay.

| # | required end state | check it satisfies |
|---|---|---|
| 1 | asset type `LevelSequence`, at the content path above | `sequence_asset_exists` |
| 2 | display rate exactly `24/1` (NOT the 30fps default) | `sequence_display_rate_24fps` |
| 3 | playback range `0.000 s .. 6.000 s` (tolerance +/-0.02 s). Tick resolution may stay at the `24000fps` default; the script converts | `sequence_spans_six_seconds` |
| 4 | a **spawnable** binding whose object template is a `CineCameraActor` | `camera_cut_targets_cine_camera`, `camera_spawned_by_sequence` |
| 5 | a **camera-cut track** on the sequence root with **exactly one** section, bounded, spanning `0.000 s .. 6.000 s`, whose `CameraBindingID.Guid` is the camera binding from step 4 | `camera_cut_track_present`, `camera_cut_covers_whole_shot` |
| 6 | a transform track on the camera binding whose `Location.X` channel has a key at `t=0.0 s` value `-500.0` and a key at `t=6.0 s` value `-150.0` (tolerance +/-1.0 uu). `Location.Y`/`Location.Z` and all rotation channels are **not** graded; leaving them unkeyed at 0 is fine and is the intended shot | `camera_pushes_in_over_full_shot` |
| 7 | a second **spawnable** binding, **named exactly `EvalHero`** (case-sensitive; `MovieSceneBindingExtensions.set_name`, i.e. the binding's `FString` name — the display text is accepted as a fallback but set the real name). Its object template may be any actor with a visible box shape; the class is **not** graded | `hero_binding_named_evalhero`, `hero_spawned_by_sequence` |
| 8 | a transform track on the `EvalHero` binding whose `Location.Z` channel has keys `t=0.0 s -> 0.0` and `t=3.0 s -> 200.0`. A third key `t=6.0 s -> 200.0` is optional — Sequencer holds the last key's value, and the script EVALUATES the curve, so two keys and three keys both pass | `hero_rises_then_holds` |
| 9 | a **fade track** on the sequence root with a section whose float curve has keys `t=0.0 s -> 1.0` and `t=0.5 s -> 0.0`. Leave the section's range alone (it is infinite by construction) and leave `FadeColor` at its default black — neither is graded | `fade_in_from_black` |
| 10 | compiled/saved, and the overlay carries **only** this one `.uasset` | sandbox scan (`cb lint` rule `reference-sandbox`) |

Expected reference verdict: **L2I `12/12`, overall PASS.**

### Two authoring gotchas to check by hand

- **Key times must land on exact ticks.** At the default tick resolution of
  24000 fps, 0.5 s = 12000 ticks and 3.0 s = 72000 ticks, both exact — but if
  you key by *display-rate frame number* remember the display rate is 24, so
  t=3.0 s is frame 72 and t=0.5 s is frame 12. Keying "frame 90" out of habit
  (30 fps thinking) puts the top of the rise at 3.75 s and fails
  `hero_rises_then_holds` by a mile.
- **The camera cut must be ONE section.** Sequencer's "add camera cut" flow
  will happily leave you with a section that starts at the playhead rather
  than at 0, or with two sections if you add the camera twice.
  `camera_cut_covers_whole_shot` requires exactly one bounded section spanning
  the full range and will reject both.

---

## 3. Why "spawnable" is the right binding kind, and how to read it

`MovieSceneSequenceExtensions.get_spawnables` (`.cpp:745-778`) unions **two**
representations:

- the legacy `UMovieScene::GetSpawnable(i)` array (`FMovieSceneSpawnable`), and
- every `FMovieSceneBindingReference` whose `CustomBinding` is a
  `UMovieSceneSpawnableActorBinding` — the 5.5+ shape.

The introspect script matches the binding's guid text against that union, so
whichever representation the authoring route produces, the check reads the
same. Similarly `MovieSceneBindingExtensions.get_object_template` reaches
`MovieSceneHelpers::GetObjectTemplate` (`MovieSceneCommonHelpers.cpp:1038-1063`)
which handles both. Nothing here depends on the *editor* being interactive; the
object template lives inside the asset.

A **possessable** binding, by contrast, names an actor in whatever level is
open. That is what the source row asked for and it is exactly what this
harness cannot grade — and worse, it makes the deliverable depend on level
state the submission overlay cannot carry. Hence anti-gaming note #2 and the
`camera-possessed-from-level/` variant.

---

## 4. Discrimination variants

Five variant `.uasset`s, one per anti-gaming note, specified in
`discrimination/MATRIX.md` and in each variant folder's
`README-MISSING-ASSETS.md`. Each is the reference with exactly ONE deviation,
so the matrix can attribute the FAIL to one gate.

| variant | the one deviation |
|---|---|
| `timeline-header-only/` | right rate + right length, **no tracks and no bindings at all** |
| `camera-possessed-from-level/` | the camera binding is a **possessable**, not a spawnable |
| `camera-static-single-key/` | the camera's `Location.X` has **one** key at `-500` |
| `camera-snaps-instead-of-pushing/` | four keys: still 0-2.9s, snap 350uu in 0.2s, still 3.1-6s (the 2026-07-27 cross-row-review hole; NB this row was MISSING from this table until 2026-07-29 - the folder always existed, and the authoring pass discovered it only via the discrimination leg count) |
| `hero-ramps-whole-shot/` | `EvalHero`'s `Location.Z` ramps `0 -> 200` across the **full six seconds** |
| `fade-out-not-in/` | the fade curve is keyed `0.0 -> 1.0` (a fade **to** black) |

**Six variants, not five** - the sentence above ("Five variant `.uasset`s")
predates the snap variant's addition and is wrong; the folder tree is the
authority.

---

## 5. Pre-flight before the first graded leg

Three blockers that are not about the assets at all. **None is introduced by
this task** — all three are the L2I lane's, inherited from the pilot:

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. Plan §9.1 assigns replacing that equality with a landability
   assertion to Phase 1.
2. **`registry.py:342` turns an L2I `error` into a graded FAIL** (plan §13.2).
   With L2I firing, a typo in a verifier-owned grader would score the *model*.
   Route it to harness-error (exit 7) before any L2I verdict is published.
3. **Registry bookkeeping (plan §9.2/§12.3).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the
   six hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md`
   x2, the verifier-building skill (under `.claude/`, not shipped) x2,
   the task-authoring skill (under `.claude/`, not shipped)). This task ships **no
   `.umap`**, so it costs 7, not 8. Do the reconciliation once for every source
   task landing in the same window rather than stacking drift.

## 6. Calibration record

- [x] Reference `SEQ_EvalCutscene.uasset` authored 2026-07-29 (headless
      `-ExecutePythonScript`, pure stock Sequencer scripting); the REAL grader
      run in-process reads **12/12**, re-confirmed by the live
      `cb discriminate` reference leg.
- [x] `get_spawnables` confirmed under **`-nullrhi`** (2026-07-29): both the
      camera and `EvalHero` spawnable-membership checks pass on the reference,
      and the possessed variant correctly reads NOT-spawnable.
      **One latent grader defect surfaced on first live contact:** `str(FGuid)`
      is an address repr in UE 5.8 (FGuid has no reflected fields), so every
      binding-identity comparison failed unfalsifiably; `_guid_text` now uses
      the `to_string()` ScriptMethod and treats an address-shaped fallback as
      unreadable (FAILURE-LOG 2026-07-29). 31 offline tests still green.
- [x] `get_object_template` confirmed headless (2026-07-29):
      `camera_cut_targets_cine_camera` passes on the reference, which requires
      the template read to have returned the CineCameraActor template.
- [x] `get_channel(section, "Location.X")` confirmed headless (the camera-push
      and hero-rise checks both evaluate their real curves).
- [x] `get_all_channels` confirmed to return the fade section's float curve
      (fade checks read real key values on every leg).
- [x] Discrimination executed 2026-07-29: reference PASS, empty + **6**
      variants FAIL (the table above; snap variant included), 8/8 legs, each
      variant via its MATRIX gate. Authoring API notes for future rows:
      channel `add_key` interprets times as DISPLAY-RATE frames by default
      (pass `unreal.MovieSceneTimeUnit.TICK_RESOLUTION` for off-frame times -
      `SequenceTimeUnit` is the pre-5.4 spelling and does not exist); the
      binding-id maker is `seq.get_binding_id(binding)`; the actor transform
      track class is `MovieScene3DTransformTrack`.
- [ ] **Measured L2I leg wall-clock recorded here.** Still not separately
      measured - the 8-leg matrix ran in one sitting but per-leg timing was
      not captured; take it from the next `cb batch-eval --references` pass.
