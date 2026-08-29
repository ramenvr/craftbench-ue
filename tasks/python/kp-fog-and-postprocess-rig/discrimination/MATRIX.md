# Discrimination matrix — kp-fog-and-postprocess-rig

The self-validation oracle for the first `tasks/python/` task: the reference
solution must PASS and the empty leg must FAIL **at the predicted check, via
the named substring**. A wrong-reason FAIL (L1 build failure, a different
check, a `0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the
verifier is NOT discriminated.

> **STATUS: RUNNABLE (reference leg PROVEN 2026-08-11).** reference authored + self-graded 14/14 by aids/author_reference.py, harvested, committed 39433c2, and `cb refgate` graded the committed reference PASS from git HEAD (161 s, 2026-08-11) - the headless map-load lane is proven at the real grading seam.
> Remaining before full certification: the empty-FAIL leg and the
> requirements-table spot checks ride the next `cb discriminate` run.

Per the amended checklist section 7 (owner decision 2026-08-11), the
mandatory artifacts here are (a) the automatic reference-PASS / empty-FAIL
rows and (b) the **requirements table** below. No hand-authored gaming
variants are shipped: the table found no hole that a variant is needed to
prove (every prompt requirement maps to an unconditional gate), and the
one-bit non-vacuity proof is the automatic empty leg.

## Parser and L2I traps this matrix is written against

- **ONE parseable table with submission rows.** `discriminate.parse_matrix`
  keys rows by label and a later table can silently overwrite an earlier
  label. The submission table below is the only table whose first column
  carries submission labels; the requirements table's first column is
  requirement prose that collides with no label.
- **Every expected-substring cell is a backtick-wrapped literal containing a
  space or `=`** (so `_extract_substrings` keeps it), and every one is a
  verbatim span that sits **inside ONE string literal** of
  `tools/verify-single/introspect/kp_fog_and_postprocess_rig.py` — never
  spanning a `%s` placeholder or a concatenation, so a static grep of source
  literals finds each of them.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule:** every expected substring is ASCII-only (the cp1252
  log-readback trap, `t2-homing-projectile`, 2026-07-21). The whole
  introspect script is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** Every exception path in
  the script emits `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` /
  `*_LOAD_ERROR` / `*_ABORTED`, none of which appears in any row below — a
  broken UE API name (a live risk on the unproven map-load pattern) surfaces
  as an uncredited FAIL, never as a credited discrimination.

## Layout (agent-writable prefixes only; a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/kp-fog-and-postprocess-rig/L_FogRig.umap` plus,
  if the level saves with One File Per Actor, its mirrors under
  `../reference/Content/__ExternalActors__/Tasks/kp-fog-and-postprocess-rig/`
  and `../reference/Content/__ExternalObjects__/Tasks/kp-fog-and-postprocess-rig/`
  (all three prefixes are `asset_writable` in the ThirdPerson
  `AGENT_WRITABLE.json`; the OFPA carve-out of 2026-07-29 exists exactly for
  this deliverable shape).
- empty leg — run IMPLICITLY by `cb discriminate` (throwaway empty dir;
  nothing to author). This task ships **no baseline** under
  `Content/Tasks/kp-fog-and-postprocess-rig/`, so the empty leg is a
  genuinely empty deliverable and scores `0/14`.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 14 checks green (14/14) | — |
| empty | FAIL | `level_asset_exists` | `RIG_LEVEL_MISSING path=` | the other 13 checks fan out on the same root cause (`0/14`) | #1 / FR-017 |
| `ppv-left-bounded/` | FAIL | `ppv_is_unbound` | `PPV_NOT_UNBOUND unbound=` | — (no other check failed) | **MEASURED 13/14 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** the mood volume is built correctly but left BOUNDED. A PostProcessVolume does nothing outside its own brush until that flag is set, so a submission that looks complete in the outliner grades as having no post-process at all. Every override and value is otherwise right. |
| `fog-falloff-default/` | FAIL | `fog_falloff_exact` | `FOG_FALLOFF_OFF_TARGET falloff=` | — (no other check failed) | **MEASURED 13/14 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** fog density and colour are exact; only the height falloff was never changed from the engine default 0.2, the value the grader names in its own text. |

## Requirements table (section 7 soundness artifact)

One row per requirement in the agent-visible prompt. Column 3 names the gate
(check id) in `tools/verify-single/introspect/kp_fog_and_postprocess_rig.py`
(the only file that asserts anything at L2I for this task; find each check id
in its `CHECK_IDS` tuple and its emitting function). "Never skipped" means
the check reports on every leg — when an upstream resolution fails, the gate
**FAILS carrying the upstream token** (fan-out), it never silently skips.

| Requirement (prompt) | Asserted | Gate (check id) | Gate skipped when | What a submission could get away with |
|---|---|---|---|---|
| A level asset named `L_FogRig` exists under `Content/Tasks/kp-fog-and-postprocess-rig/` | fully | `level_asset_exists` (`_rig_checks`) | never — first gate; everything fans out from it | nothing |
| The level is saved so values read back from the saved files alone | fully | `level_asset_exists` + `level_loads_clean` (the runner grades a git-materialized overlay on a clean substrate; unsaved editor state presents as a missing/partial asset) | never | nothing — printed claims are never read (anti-gaming #5) |
| The saved level actually loads (not a corrupt/partial file set) | fully | `level_loads_clean` (`_load_level` + `_world_matches`; wrong-world fails) | never — fans out to all downstream checks on failure | nothing |
| An object labelled `Fog` that is real in-world ground fog | fully | `fog_actor_present` (`_resolve_actor`, label AND `isinstance` ExponentialHeightFog, duplicates fail) | never | a subclass of the height-fog actor passes — accepted by design |
| Fog thickness exactly `0.03` | fully | `fog_density_exact` | never skipped; FAILS with the Fog resolution token when the actor did not resolve | any value in `[0.025, 0.035]` — transcription tolerance, excludes the `0.02` default |
| Fog thinning-with-height rate exactly `0.15` | fully | `fog_falloff_exact` | same fan-out rule | any value in `[0.13, 0.17]` (default `0.2` excluded) |
| Fog colour deep night blue `(0.02, 0.04, 0.10)`, full alpha | partially — RGB gated, alpha not | `fog_color_night_blue` | same fan-out rule | any RGB within `0.01` per channel; **alpha ungraded** (target equals what a black default renders as; recorded residual) |
| An object labelled `Mood` that re-grades what the camera sees | fully | `ppv_actor_present` (label AND `isinstance` PostProcessVolume) | never | a subclass passes — accepted |
| `Mood`'s influence covers the whole world, not just its bounds | fully | `ppv_is_unbound` | fan-out rule (Mood resolution) | nothing — the flag defaults false |
| Bright-spot glow raised to `1.8`, deliberately switched on | fully | `ppv_bloom_overridden` (flag AND band conjoined in one check) | fan-out rule (Mood resolution or unreadable settings struct) | value in `[1.7, 1.9]` with flag on |
| Corner darkening set to `0.6`, deliberately switched on | fully | `ppv_vignette_overridden` | fan-out rule | value in `[0.55, 0.65]` with flag on |
| Per-channel saturation `(0.85, 0.88, 0.95)`, deliberately switched on | partially — XYZ gated, W not | `ppv_saturation_overridden` | fan-out rule | XYZ within `0.02` with flag on; **W ungraded** (target equals default; recorded residual) |
| Brightness adaptation biased to `-0.5`, deliberately switched on | fully | `ppv_exposure_bias_overridden` | fan-out rule | value in `[-0.6, -0.4]` with flag on |
| An object labelled `Ambient` that is a sky-driven fill light | fully | `skylight_actor_present` (label AND `isinstance` SkyLight) | never | a subclass passes — accepted |
| `Ambient` brightness exactly `0.2` | fully | `skylight_intensity_exact` | fan-out rule (Ambient resolution) | any value in `[0.15, 0.25]` (default `1.0` excluded) |
| "cold, dim, heavily graded look" (framing prose) | NOT AT ALL — deliberately | — | — | the look is the sum of the nine gated values; no additional aesthetic gate exists and none is intended (FR-020d: no pixels, no judge) |

Ungated-prose audit: the only prompt sentences without a dedicated gate are
the framing ("cold, dim, heavily graded look", "together give the scene…"),
which are the *composition* of the sixteen gated rows above, and the
labels/path naming, which are the identity keys the gates resolve by. No
requirement is left as unenforced prose, so no targeted variant is required
under the amended section 7. Two candidate holes were considered and closed
structurally rather than by variant:

- **"set the value, never flip the flag"** (the inert-settings trap the
  source list's editor-scripting sessions actually hit): closed by conjoining
  flag AND band inside each single override check (`_flag_scalar_check`) —
  there is no code path where the value alone can satisfy the gate, so a
  variant would only re-prove the conjunction the source shows.
- **"redirect the grader to a pre-lit level"**: closed by `_world_matches` —
  the loaded editor world's package path must be the graded asset path.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-fog-and-postprocess-rig
```

Per-leg fallback while iterating (short `--workdir` dodges Windows MAX_PATH;
use the `py` launcher — this box's `py -3.12` does not resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-fog-and-postprocess-rig/task.md \
    --submission tasks/python/kp-fog-and-postprocess-rig/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpfog        # expect exit 0
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the checks' raw
`detail` strings. L2I graders are read from the LIVE working tree
(`registry.py` resolves `introspect/` next to itself), so iterating on
`kp_fog_and_postprocess_rig.py` needs no commit — but the level binaries DO
need committing before a non-`--wip` grade sees them (`run_task`
materializes the substrate from git HEAD).

## Status

- Authored 2026-08-11 from the spec, text-only track. **Never executed
  against a real editor** — no level binary exists yet, and the map-loading
  introspect pattern has never run anywhere.
- The two substrings above are proven offline to be verbatim single-literal
  spans of the introspect script (checked by grep at authoring time), and
  the script's 14-check constant-denominator emission was exercised offline
  with no `unreal` module (all 14 fail with `RIG_LEVEL_PROBE_ERROR path=`,
  which no row credits — exactly the fail-closed shape wanted).
- **Still missing, in order:** (1) the reference level binaries — produced by
  `../aids/author_reference.py` in the authoring lane; (2) a live run of the
  reference leg to prove the headless map-load pattern (THE blocking risk);
  (3) live confirmation of the property spellings the offline track cannot
  settle (`unbound`, `settings` write-back visibility,
  `fog_inscattering_luminance` vs legacy spellings — the script probes
  several each, but only an editor decides).
