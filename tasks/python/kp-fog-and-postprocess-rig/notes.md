# kp-fog-and-postprocess-rig — authoring notes

Text-only track (no UE run). First task of the new
`tasks/python/` basket and the first task whose L2I introspect loads a map.

## 1. Provenance (the source row)

- **Source**: an earlier internal task list (not shipped) — a lighting row,
  one of a group derived from observed editor-scripting-agent failures; the
  `kp-` prefix disambiguates that group from the rest of the source list.
- **Its metrics columns**: "% of verification checks passed" and "# of
  execute_unreal_python calls + compile errors to reach success". Start
  state: "Empty Project"; verification: "None required - verified via printed
  editor state"; budget: "<=20 steps; <=8 min".
- **Basket law applied** (`tasks/README.md`):
  outcome-graded — the deliverable is the resulting editor state, graded by
  the deterministic L2I lane; the prompt's exactness/volume makes editor
  scripting the natural route, but **no gate asserts python was used**. A
  future v2 may re-execute submitted scripts; deliberately not this version.

## 2. Divergences from the source row (full record)

1. **API names stripped from the prompt** (Hard Rule #2). The source row's prompt
   is literally a python recipe (`fog_density = 0.03`,
   `set_editor_property('settings', settings)`, `unreal.Vector4`, spelling
   advice for the inscattering colour). Every requirement was rewritten as an
   observable outcome; the exact numbers stay (basket charter).
2. **Vignette 0.45 → 0.6.** UE 5.8 default is 0.4 (`Scene.cpp:541`); a
   readable tolerance band around 0.45 cannot exclude the default without
   being tighter than float transcription deserves. 0.6 gives band
   `[0.55, 0.65]` with the default cleanly outside.
3. **Graded surface scoped to nine values.** Dropped from the source row, with
   reasons:
   - `fog_max_opacity = 0.85`, `start_distance = 100.0` — fine values, but
     each added check dilutes the denominator without probing a new
     capability (same read route as density/falloff).
   - `volumetric_fog = True`, `volumetric_fog_scattering_distribution = 0.6`
     — volumetric fog is already the graded core of
     `t1-dawn-fog-lighting-rig`; duplicating it here blurs the two rows.
   - `color_contrast = (1.1, 1.1, 1.1, 1.0)` — target within 0.1 of the
     `(1,1,1,1)` default per channel; a band excluding the default would be
     ±<0.1 around 1.1, uncomfortably tight, and the override-flag half is
     already probed four times.
   - `lower_hemisphere_color = (0.005, 0.008, 0.02)` — **un-dead-gateable**:
     within noise of the `(0,0,0)` default; any honest tolerance admits the
     untouched value. Dropped rather than shipped as a dead gate.
4. **"Print a verification summary" dropped; "save the level" kept and made
   the backbone.** Printed prose grades nothing (anti-gaming note 5); the
   grader reads only the saved bytes. The source row's per-check percentage
   survives as the reported `x/14`; the step/efficiency metric has no
   harness signal today and is dropped.
5. **Start state**: the source row's "Empty Project" / "current level" → the
   `ThirdPerson` substrate, deliverable at `/Game/Tasks/<id>/L_FogRig`
   (repo path convention + the OFPA carve-out that makes an agent-authored
   level submittable at all).

## 3. Design decisions

- **Level deliverable, not an asset.** The source row's outcome IS level state
  (spawned actors). `t1-dawn-fog-lighting-rig` §"Why this row is not graded
  on a level" documents why that was impossible for its 2026-07-27 track:
  L2I never loads a map and the headless level-load was unspiked (plan U1).
  This task takes the other fork on purpose — the task card for the python
  basket names the map-loading introspect as the pattern to write cleanly
  and prove. All four of dawn's blockers are addressed: (1)/(2) are L2-only
  concerns and this task declares no L2; (3) the introspect loads the map
  itself (`_load_level`, two routes, world-identity check); (4) the OFPA
  deny was replaced 2026-07-29 by the `__ExternalActors__/Tasks/` +
  `__ExternalObjects__/Tasks/` asset_writable carve-out.
- **Identity = actor label** (`Fog`, `Mood`, `Ambient`), pre-declared in the
  prompt like dawn's subobject names; class is only the isinstance
  assertion. Duplicate labels fail (never resolved silently).
- **14-check constant denominator**, dawn's exact idiom: fan-out on root
  causes, error tokens disjoint from failure tokens, ASCII details, every
  MATRIX-creditable span inside one string literal (checked by grep).
- **Bands are transcription tolerances around promised numbers** — the
  prompt states the targets (basket charter), so unlike dawn there is no
  hidden rubric; the dead-gate discipline is still enforced band-by-band
  (task.md table, engine-source-cited, audited 2026-08-11).
- **Override gates conjoin flag AND value in one check.** The
  inert-settings trap (value written, `bOverride_*` never flipped) is the
  actual observed editor-scripting failure this row derives from; splitting
  flag and value into two checks would let a half-done submission collect
  half credit for a rendering no-op.
- **No hand-authored discrimination variants** (amended checklist §7,
  2026-08-11): the requirements table in `discrimination/MATRIX.md` maps
  every prompt requirement to an unconditional gate; the automatic empty
  leg provides the non-vacuity bit.

## 4. Reference

**Reference pending the authoring-lane run.** `reference/` is EMPTY on
purpose — level binaries cannot be fabricated from a text-only track.
`aids/author_reference.py` builds, self-grades (against the real introspect,
requiring 14/14), harvests and cleans up in one headless pass:

```sh
<UE-root>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe \
    <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
    -ExecutePythonScript=<repo>/tasks/python/kp-fog-and-postprocess-rig/aids/author_reference.py \
    -nullrhi -unattended -nosplash
# grep the newest ThirdPerson*.log for KPFOG-DONE (absent = FAILED)
```

## 5. Calibration TODOs (before the task can be `wired`)

- [ ] Run `aids/author_reference.py`; require `KPFOG-DONE`; commit the
      harvested `reference/` tree; record the `KPFOG-SPELLING` lines here.
- [ ] **Prove the map-load pattern live**: grade `reference/` through
      `run_task.py` (real L2I lane, `-nullrhi`) and confirm
      `level_loads_clean` passes headless. This is the risk gating
      everything; if `load_level`/`load_map` misbehaves under `-nullrhi`,
      the fallback order in `_load_level` is the first knob.
- [ ] Confirm the live property spellings the offline track cannot settle:
      `unbound`, `settings` (struct write-back visibility),
      `fog_inscattering_luminance` (vs legacy `fog_inscattering_color`),
      `override_*` flag names. The grader and the aid probe several
      spellings each; only an editor decides.
- [ ] Confirm the ThirdPerson value of `r.DefaultFeature.AutoExposure.Bias`
      stays outside `[-0.6, -0.4]` (engine ships non-negative; the exposure
      band is strictly negative, so only a bizarre project override could
      un-dead-gate it).
- [ ] Check whether saving produces `L_FogRig_BuiltData.uasset` and whether
      the sandbox accepts it under `Content/Tasks/` (it should: same
      prefix); confirm the harvested file set round-trips through
      `apply_submission` without SANDBOX-REJECT.
- [ ] Offline oracle (mirror dawn's `test_introspect_dawn_fog.py`): assert
      band-vs-default exclusion mechanically + the 14-check denominator on
      the no-unreal path, so a future band edit cannot quietly swallow a
      default.
- [ ] `cameras.json` (the camera-plan lane; not part of this release) (SHOULD ship; owner decision 2026-08-05) — propose via
      a camera plan after
      the reference lands.
- [ ] Run `cb lint` / tasklint on the new basket dir — first `set: python`
      spec; watch for any hardcoded `bp|cpp` set validation (a
      `tasklint`/`spec.py` allowlist may need the new basket added, the same
      shape as `test_verdict_taxonomy.py:79` blocking dawn's `L1+L2I`).

## 6. Risks

1. **THE pattern-to-prove: no existing introspect loads a map.**
   `l2_introspect.py` launches `UnrealEditor-Cmd` with no map argument; this
   script self-loads the level headless under `-nullrhi` via
   `LevelEditorSubsystem.load_level` → `EditorLoadingAndSavingUtils.load_map`
   (fail-closed, world-identity-verified). The headless level load was still
   an open probe (plan U1) when dawn scoped itself away from it. Until the
   reference leg runs live, treat every leg of this task as blocked on this
   proof — and if it fails, the fallback is the dawn-style re-scope (grade a
   placeable rig asset instead of a level), which would be a spec rewrite,
   not a patch.
2. **OFPA file-set handling is exercised for the first time.** The
   `__ExternalActors__/Tasks/` carve-out (2026-07-29) exists but no shipped
   task has actually submitted a level through it. Unknowns: whether
   `new_level` in 5.8 defaults this project to OFPA, what the external file
   set looks like, and whether `apply_submission` + fairness pruning treat
   the mirrors correctly.
3. **Property-spelling uncertainty** (grader and aid both probe; only an
   editor settles): `unbound`, the settings-struct write-back, the
   inscattering-colour name. A wrong-everywhere guess fails closed
   (`*_READ_ERROR`, uncreditable) — correct behavior, but it would fail the
   reference too, so it surfaces at calibration, not in production.
4. **First `set: python` spec.** Any tooling that validates the basket
   against a `bp|cpp` literal (spec.py front-matter validation, tasklint,
   status_gen) will trip on this task first. Budget for the same
   "equality → landability" fix shape as `test_verdict_taxonomy.py:79`.
5. **Dawn's no-digit prompt oracle must not be generalized.**
   `test_prompt_no_rubric_leak.py` asserts the dawn prompt contains no
   digits; this basket's prompts are DELIBERATELY full of digits. If that
   test is ever widened from per-task to glob-all-tasks, this basket breaks
   by design intent.
6. **`category: lighting` / bucket taxonomy.** Follows dawn's precedent
   (`category: lighting` ships today) rather than the template's
   `gameplay|materials-structural|other` triple; if a category validator
   lands, this task and dawn move together.

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.
