# kp-anim-track-bake — verifier-builder notes

v2-corpus port (`t1-anim-modifier-bakes-curve`), authored 2026-08-12 with a
forced redesign (§4). Companion docs: `task.md` (spec + provenance),
`discrimination/MATRIX.md` (oracle + requirements table).

## 1. Reference solution, property-by-property

- Baseline (substrate, committed):
  `UE-projects/ThirdPerson/Content/Tasks/kp-anim-track-bake/AS_TaskWalk.uasset`
  — `EditorAssetLibrary.duplicate_asset` of
  `/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd`
  (path re-verified on this tree 2026-08-12), UNMODIFIED.
- Reference deliverable:
  `reference/Content/Tasks/kp-anim-track-bake/AS_TaskWalk.uasset` — the
  same asset plus one float track `WalkPhase` with exactly two keys:
  `(0.0, 0.0)` and `(clip_length, 1.0)`. Track name and key shape are AID
  choices — the grader accepts any new name and any first!=last shape
  whose keys reach both outer tenths.
- Both artifacts carry the SAME package path (`/Game/Tasks/
  kp-anim-track-bake/AS_TaskWalk`), so plain filesystem copies of the
  saved file are valid at that path — no editor-side rename is involved
  (the classic fs-copy-breaks-uasset trap does not apply; the aid stages
  and restores bytes of the same package).

## 2. Baseline pins (the re-pin law)

`kp_anim_track_bake.py` grades "new" against `BASELINE_CURVE_NAMES` and
guards collateral damage with `BASELINE_LENGTH`. Both ship as the `None`
sentinel → `baseline_state_intact` fails CLOSED until the aid's
`KPBAKE-BASELINE names=... length=...` line is pinned in. Law: the pins
land in the **SAME commit** as the two binaries; a stock walk cycle may
well carry stock float tracks (curve-driven locomotion data), so never
assume the baseline inventory is empty — pin what the aid prints.

## 3. Aid runbook

One editor run (`aids/author_reference.py`, markers `KPBAKE-*`):
duplicate → save → print pins → stage baseline bytes → bake → save →
self-grade → harvest reference → restore + byte-verify substrate. On the
first run (grader still sentinel) the self-grade expects exactly the
`ANIMBAKE_BASELINE_UNPINNED` failure shape and reports
`KPBAKE-PIN-NEEDED`; pin, commit binaries+pins together, re-run for the
5/5 `KPBAKE-SELFGRADE` certificate, then `cb refgate`. After any run:
`git status --short UE-projects/ThirdPerson` must show ONLY the intended
baseline addition (scratch law; the `.baseline-stage` temp is removed by
the restore step).

## 4. The forced redesign — why the modifier-stack gate died (citations)

The draft's `ScriptedPassRecorded` check required the asset's modifier
stack to record an applied pass. Established against engine source
(<UE-root>, 2026-08-12):

- `UAnimationModifier::ApplyToAnimationSequence` / `RevertFrom...` are
  bare `UE_API` methods — **no UFUNCTION**
  (`Engine/Source/Editor/AnimationModifiers/Public/AnimationModifier.h:44`);
  the class's only UFUNCTIONs are the `OnApply`/`OnRevert`
  BlueprintNativeEvents themselves (`:47-53`). The stamping of
  `AnimationModifiersAssetUserData` happens inside the unexposed apply
  pipeline.
- No engine scripting library wraps it: searched `Engine/Source/Editor`
  and the `AnimationModifierLibrary` plugin (enabled-by-default:
  `.uplugin:13`) for exposed apply routes — the plugin ships stock
  modifier CLASSES only; `IAnimationModifiersModule` is C++-only.
- The C++ escape is closed too: `AnimationModifiers` is an **Editor**
  module, the agent-writable module (`Source/ThirdPerson/`) links into
  the Game target (L1 builds both), and adding an editor module requires
  Target.cs/.uproject edits outside every writable prefix.

Net: a headless agent can neither invoke the official apply pipeline nor
ship a class it would accept — "mechanism exists but is unreachable"
(the earlier-task-list L2I reframe class). The outcome that survives —
programmatic track authoring — rides `unreal.AnimationLibrary`
(`ScriptName` at `AnimationBlueprintLibrary.h:65`), whose read/write
surface is UFUNCTION-exposed end to end (`GetAnimationCurveNames:89`,
`AddCurve:336`, `AddFloatCurveKey:356/360`, `GetFloatKeys:456`,
`GetSequenceLength:598`).

Id rename rides the same review: the draft's `t1-anim-modifier-bakes-curve`
leaks the feature name into the agent-visible content path (Hard Rule #2,
third catch of this class); `kp-anim-track-bake` names the outcome.

## 5. Grader design decisions

- **Keys, not samples**: variance and span read `get_float_keys` raw
  arrays — no interpolated-read surface for instant-span or plateau
  tricks; MATRIX rows 2–3.
- **"New" is set-difference against the pinned baseline**, so renaming a
  stock track both mints no safe "new" name AND trips the guard.
- **The guard row is not a discriminator**: the empty leg scores 3/5
  (asset resolves, guard holds) — the MATRIX empty row credits the
  `ANIMBAKE_NO_NEW_TRACK` token, never the score. Wave-3's audit-task
  precedent (baseline ships → presence checks pass on empty) applied
  deliberately.
- **Token discipline**: credited `ANIMBAKE_*` failure tokens vs the
  uncredited error class (`ANIMBAKE_PROBE_ERROR`, `_CHECK_UNREACHED`,
  `_ENUM_UNAVAILABLE`, `_KEYS_UNREADABLE`, `_LENGTH_UNREADABLE`).

## 6. Live spikes owed to the authoring-lane run

1. The four `unreal.AnimationLibrary` calls under `-nullrhi` (whole
   surface is one library; header-verified, never run headless by us).
2. `duplicate_asset` on an AnimSequence (proven for other asset types in
   the import lane; anim-specific dependencies — skeleton ref — ride
   along).
3. Whether the stock walk carries baseline float tracks (§2 — pin truth,
   don't assume).
4. `save_loaded_asset` round-trip of baked curves (the draft flags no
   risk here, but the refgate boot from git HEAD is the real proof).

## 7. Status

Text-only track, authored 2026-08-12 (spec + grader + MATRIX + aid).
Binaries, pins, refgate certificate, and the discriminate legs pend the
authoring-lane run (§3).
