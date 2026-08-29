# Discrimination matrix — t2-cutscene-camera-push-and-hero-rise

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated — fix it, or relabel the task for the weaker property it actually
tests.

> **STATUS: NOT RUNNABLE IN UE YET.** Every leg of this matrix needs a binary
> `.uasset` that does not exist on disk. The rows, the expected substrings and
> the per-variant asset specs below are complete and authored; the bytes are
> not. See **What is missing** and `../notes.md`. The *logic* oracle below the
> line IS runnable today, offline, with no editor.

## Four parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]` (`discriminate.py:227`), so a *second* table that
  repeats a variant label silently **overwrites** the first — and because a
  table without a "substring"/"message" header column yields an empty message,
  the overwrite lands a blank substring tuple and the leg can never be
  credited. This file therefore has **exactly one table with variant rows**;
  every secondary/derived observation lives in prose below it, where no `|`
  row can re-register a label. (This defect blanked 4 of 6 negative legs on the
  pilot, 2026-07-27.)
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither a space nor that punctuation, so
  it hits the broken branch. Pairing the token with the fixed prefix of the
  text that follows it in the script (`... /Game/Tasks/`, `... tracks=`,
  `... name=`, `... keys=`) makes the cell substantive **and** keeps it a
  verbatim substring of the printed `detail`. This works whether or not the
  last-resort branch is ever fixed in code.
- **NO variant directory may start with `empty`.** `parse_matrix` classifies a
  row by its first cell, and the `empty` branch
  (`elif first_plain.lower().startswith("empty")`, `discriminate.py:281`) is
  tested **before** the variant-directory branch — so a variant folder named
  `empty-timeline-right-length/` registers under the reserved label `empty`
  and, being later in the file, **overwrites the real empty leg's row**. Caught
  here on the first run of the real parser: the dict came back with 6 rows
  instead of 7 and `empty` carried
  `CAMERA_CUT_TRACK_MISSING tracks=` instead of `SEQ_ASSET_MISSING /Game/Tasks/`,
  so the genuine empty submission could never have been credited. The variant
  is therefore named `timeline-header-only/`. Same class of defect as the
  duplicate-label overwrite above, reached by a different door; it will hit any
  task that wants an "empty-something" variant.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an *earlier* script could never be
  credited. This task declares one script, and must keep declaring one.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/cutscene_camera_push_and_hero_rise.py`.
- **ASCII rule:** every expected substring is ASCII-only. The UE log's UTF-8
  bytes are read back as cp1252, so a non-ASCII character in a detail string
  becomes mojibake and the grep misses — a correct FAIL then misclassifies as
  wrong-reason (live incident, `t2-homing-projectile`, 2026-07-21). The whole
  introspect script is ASCII by construction.

**Error tokens are distinct from failure tokens.** Every exception path in the
script emits a `*_READ_ERROR` / `*_PROBE_ERROR` / `*_LOAD_ERROR` /
`*_UNRESOLVED` / `*_UNAVAILABLE` / `*_ABORTED` token that appears in **no**
matrix row. So a broken UE API name can never be credited as a variant's named
failure — it shows up as an uncredited FAIL, which is the signal you want.
Asserted by `tools/verify-single/tests/test_introspect_cutscene_sequence.py::
TestErrorTokensAreDisjointFromMatrix`.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t2-cutscene-camera-push-and-hero-rise/…` — the
  one correct solution. The `ThirdPerson` substrate's agent-writable Content
  carve-out is `Content/Tasks/`, so the overlay mirrors that path exactly,
  including the per-task segment.
- `<variant>/Content/Tasks/t2-cutscene-camera-push-and-hero-rise/…` — one dir
  per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

Note what makes the empty leg different from the pilot's: this task ships **no
baseline asset**, so an empty submission has *nothing* — all 12 checks fail
(`0/12`) on the single root cause. There is no partially-correct floor.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 12 checks green (12/12) | — | — |
| empty | FAIL | `sequence_asset_exists` | `SEQ_ASSET_MISSING /Game/Tasks/` | the 11 other checks fan out on the same root cause (`0/12`) | #1 / FR-017 |
| `timeline-header-only/` | FAIL | `camera_cut_track_present` | `CAMERA_CUT_TRACK_MISSING tracks=` | the 4 camera checks, the 3 hero checks and the fade check | #1 correctly-shaped empty timeline |
| `camera-possessed-from-level/` | FAIL | `camera_spawned_by_sequence` | `CAMERA_BINDING_NOT_SPAWNABLE name=` | — | #2 camera borrowed from the level |
| `camera-static-single-key/` | FAIL | `camera_pushes_in_over_full_shot` | `CAMERA_PUSH_IN_KEYS_WRONG keys=` | — | #4(a) motion faked by a section |
| `camera-snaps-instead-of-pushing/` | FAIL | `camera_pushes_in_over_full_shot` | `CAMERA_PUSH_IN_NOT_GRADUAL at=` | — | #4(c) endpoints right, motion snapped |
| `hero-ramps-whole-shot/` | FAIL | `hero_rises_then_holds` | `HERO_RISE_KEYS_WRONG keys=` | — | #4(b) ramp instead of rise-then-hold |
| `fade-out-not-in/` | FAIL | `fade_in_from_black` | `FADE_IN_KEYS_WRONG keys=` | — | #5 fade the wrong way round |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- `timeline-header-only/` is the only variant with fan-out, and that is
  the point of anti-gaming note #1: nine checks read past the timeline header,
  so an asset that only sets the two header properties fails nine of them.
  `camera_cut_covers_whole_shot`, `camera_cut_targets_cine_camera`,
  `camera_spawned_by_sequence` and `camera_pushes_in_over_full_shot` all
  inherit the *same* `CAMERA_CUT_TRACK_MISSING tracks=` detail by design (a
  single root cause is reported once and fanned out, never re-diagnosed), while
  the hero checks report `HERO_BINDING_MISSING bindings=` and the fade check
  reports `FADE_TRACK_MISSING tracks=`. Only the first of those is matched.
- The other five variants each fail **exactly one** check. That is deliberate:
  each is the reference with one property changed, so the matrix attributes the
  FAIL to one gate with no ambiguity. `camera-possessed-from-level/` in
  particular still PASSES `camera_cut_targets_cine_camera` — the camera is the
  right *type*, it is only the wrong *ownership* — which is why those two are
  separate checks.

### `camera-snaps-instead-of-pushing/` — a hole that was open, not a hypothetical

Added 2026-07-27 after a cross-row review. Until then
`camera_pushes_in_over_full_shot` sampled `_eval_curve` at **t=0 and t=6 only**,
and `_eval_curve` HOLDS the value outside the keyed range — so a camera that
sat still for 2.9 s, snapped 350 units in 0.2 s and sat still again scored
`12/12 overall PASS`. Reproduced against the pre-fix grader before the fix
landed; see the variant folder's README for the four-key spec and the transcript
of both verdicts.

The grader now samples the curve every half-second across the whole shot and
applies three gates (`_push_shape`): the keys must span the shot
(`CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT first_key=`), no sample may move away
from the target (`CAMERA_PUSH_IN_NOT_MONOTONIC at=`), and the fraction of
travel completed must track the fraction of the shot elapsed to within 0.20
(`CAMERA_PUSH_IN_NOT_GRADUAL at=`). Only the third is authored as a variant —
the other two are proven reachable in the offline oracle
(`TestPushShapeIsNotEndpointOnly`) and would each need their own binary to say
anything the third does not. The band is deliberately wide enough that an
**eased** push (five keys, slow-in/slow-out) still PASSES; only the linear
reference is required to be exact at the endpoints.

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A sequence left at the engine's own defaults (5 seconds, 30 fps) dies at
  `sequence_spans_six_seconds` (`SEQ_DURATION_WRONG start=`) and
  `sequence_display_rate_24fps` (`SEQ_DISPLAY_RATE_WRONG rate=`). No variant is
  authored for it because the *empty-timeline* variant already isolates the
  header/body split from the other side, and because those two constants are
  precisely the ones the dead-gate audit retargeted — an unmodified fresh
  sequence failing them is the audit's whole point.
- A cut section left unbounded, or two cut sections instead of one, dies at
  `camera_cut_covers_whole_shot` (`CAMERA_CUT_RANGE_WRONG start=`). Not
  authored as its own variant: it is the same gate the reference proves, and
  authoring an unbounded camera-cut section is not reliably reachable through
  the editor UI.
- A hero bound under any name other than `EvalHero` dies at
  `hero_binding_named_evalhero` (`HERO_BINDING_MISSING bindings=`), and a hero
  possessed from the level dies at `hero_spawned_by_sequence`
  (`HERO_BINDING_NOT_SPAWNABLE name=`) — the same shape
  `camera-possessed-from-level/` proves on the camera side, so it is argued
  rather than duplicated.

## What is missing (this matrix cannot run in UE until these exist)

**I cannot author `.uasset` binaries from a text-only track.** Seven binaries
are needed. Each variant folder holds a `README-MISSING-ASSETS.md` at the exact
path the `.uasset` must occupy, describing property-by-property what to author;
**delete that README in the same commit that lands the real asset.** The full
property-level spec for the reference is `../notes.md`.

| # | Path | What it must be |
|---|---|---|
| 1 | `../reference/Content/Tasks/…/SEQ_EvalCutscene.uasset` | the **reference**. `notes.md` §2 |
| 2 | `timeline-header-only/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant. See that folder's README |
| 3 | `camera-possessed-from-level/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant |
| 4 | `camera-static-single-key/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant |
| 5 | `camera-snaps-instead-of-pushing/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant |
| 6 | `hero-ramps-whole-shot/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant |
| 7 | `fade-out-not-in/Content/Tasks/…/SEQ_EvalCutscene.uasset` | variant |

There is **no baseline asset** for this task, so unlike the pilot no substrate
`.uasset` has to land first, and no variant has to re-ship an untouched
baseline: `apply_submission` is a copy-only overlay with no wipe, and there is
nothing underneath to fall through to.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t2-cutscene-camera-push-and-hero-rise
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t2-cutscene-camera-push-and-hero-rise/task.md \
    --submission tasks/bp/t2-cutscene-camera-push-and-hero-rise/discrimination/hero-ramps-whole-shot \
    --ue-root "$UE" --workdir C:\cb\wd\kv9var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `cutscene_camera_push_and_hero_rise.py` needs no
commit — but the `.uasset` files DO need committing before a non-`--wip` grade
sees them (`run_task` materializes the substrate from git HEAD).

## The offline logic oracle (runnable today)

```sh
py -m unittest tools.verify-single.tests.test_introspect_cutscene_sequence -v
```

A fake `unreal` module models the SequencerScripting surface the script
actually uses (sequence, tracks, sections, channels, keys, bindings,
spawnables), so every leg of this matrix is simulated and joined against the
REAL `discriminate.parse_matrix` and the REAL `layers/l2_introspect` parser.
It proves the grader's LOGIC and its printed tokens. It cannot prove the UE
API *names* — only a live editor does that.

## Status

- Authored 2026-07-27 from the spec, text-only track. **Never executed against
  a real editor** — no leg has run in UE, because no `.uasset` exists yet.
- Every one of the seven negative legs parses out of this file with a
  **non-empty, backtick-free** substring, and every substring is proven to be a
  literal the introspect script actually prints, simulated offline against a
  fake `unreal` module.
- **Still missing, in order:** (1) the six `.uasset` binaries above — nothing
  here can run in UE without them; (2) a live-editor confirmation of the UE API
  names the offline fake cannot check (`get_spawnables`,
  `get_object_template`, `get_camera_binding_id`, `get_channel` with the
  `"Location.X"` / `"Location.Z"` metadata names, `get_all_channels` on the
  unnamed fade curve, and which spelling of `numerator`/`value`/`frame_number`
  `get_editor_property` resolves — the script tries both spellings, but only an
  editor settles it); (3) the `discriminate.py` last-resort backtick strip —
  this file no longer *depends* on it, but every future L2I MATRIX will hit the
  same trap until it lands.
- Shares the pilot's two harness blockers:
  `tools/verify-single/tests/test_verdict_taxonomy.py:79`
  (`test_every_shipping_spec_declares_only_landable_gating_layers`) asserts
  every spec on disk is exactly `("L1","L2")`, and `registry.py:342` turns an
  L2I `error` into a graded FAIL rather than a harness error (plan §9.1,
  §13.2). Neither is introduced by this task; both must land before any L2I
  verdict is trusted.

# DRAFT — to be appended to tasks/bp/t2-cutscene-camera-push-and-hero-rise/discrimination/MATRIX.md

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the gate column is a contiguous ASCII literal in
the verifier-owned grader
`tools/verify-single/introspect/cutscene_camera_push_and_hero_rise.py` (the
task's single L2I script; the durable join key is the check id) — with one
composed exception: the row-1/19 asset-missing detail is runtime-composed as
`"%s %s" % (SEQ_MISSING_TOKEN, ASSET_SEQUENCE)` (line 666), so those rows
backtick only the source-side literal `SEQ_ASSET_MISSING` and are marked
"(composed)"; the asset path is appended at emit time. Layers are
`[L1, L2I]`: the submission is content-only, so L1 is a build precondition
with no requirement of its own — every prompt requirement below is enforced
(or not) by one of the 12 L2I checks. All 12 checks report on every leg
(constant denominator); "skipped" below means the check inherits an earlier
root cause's detail instead of evaluating its own property. Additionally,
every `*_READ_ERROR` probe-fault route reroutes its rows below to an
uncreditable error token before any stated skip condition — including the
two routes no cell states: `CAMERA_CUT_BINDING_READ_ERROR` (a bindings-walk
or camera-binding-id read fault fails exactly `camera_cut_targets_cine_camera`,
`camera_spawned_by_sequence` and `camera_pushes_in_over_full_shot` — rows
8/9/10 — at cutscene_camera_push_and_hero_rise.py:869-876) and
`HERO_SPAWNABLE_READ_ERROR` (a spawnables probe fault fails
`hero_spawned_by_sequence` — row 14 — at line 997); the authoritative route
order is the source.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | exactly one new asset at `Content/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene`, of the right kind | fully | `sequence_asset_exists` — `SEQ_ASSET_MISSING` (composed; the emitted detail appends the `/Game/Tasks/…` asset path) (absent) / `SEQ_ASSET_NOT_LEVEL_SEQUENCE class=` (wrong asset type: positive `isinstance(asset, unreal.LevelSequence)`) | unconditional (first gate); if it fails, all 11 other checks fan out carrying the same root-cause detail (`0/12`) | nothing about the path or type — identity is by pre-declared content path |
| 2 | "…and nothing else" — no other new content | **NOT ASSERTED** | no gate reads the rest of the submission; the sandbox (the manifest UE-projects/ThirdPerson/AGENT_WRITABLE.json, exit 4 — named in prose, not a grader token) rejects only files OUTSIDE the writable/asset-writable prefixes, it never counts what is inside them | — | shipping any number of extra `.uasset`s under `Content/Tasks/<id>/` (or any asset-writable prefix) alongside the sequence; none is read, none fails anything |
| 3 | entirely self-contained: playable in a completely empty level, depends on nothing it did not bring | partially | only for the two graded actors, via `camera_spawned_by_sequence` — `CAMERA_BINDING_NOT_SPAWNABLE name=` and `hero_spawned_by_sequence` — `HERO_BINDING_NOT_SPAWNABLE name=` (binding guid must resolve into `get_spawnables`, which unions legacy spawnables + 5.8 custom spawnable bindings) | camera leg: no cut section (inherits whatever `camera_cut_track_present` recorded — `CAMERA_CUT_TRACK_MISSING tracks=` or `CAMERA_CUT_TRACK_EMPTY sections=0`) or cut binding unresolved (`CAMERA_CUT_BINDING_UNRESOLVED guid=`); hero leg: no binding named EvalHero (inherits `HERO_BINDING_MISSING bindings=`) | any ADDITIONAL binding may possess a level actor (a light, a prop, a second camera) — the spawnable test is run only on the cut's target and on `EvalHero`, so a sequence that also depends on level objects still passes |
| 4 | "takes it away again when the shot ends" — the brought actors do not outlive the shot | **NOT ASSERTED** | no gate; spawnable-ness (row 3) is the structural proxy, but the spawn-ownership/lifetime flag that decides whether a spawnable survives the sequence is never read | — | a spawnable whose spawn ownership is set to outlive the sequence (kept-alive/external ownership) leaves the camera and hero standing in the level after the shot and still passes both `*_spawned_by_sequence` checks |
| 5 | runs for exactly six seconds | fully | `sequence_spans_six_seconds` — `SEQ_DURATION_WRONG start=` (playback range must read 0.000..6.000 s, ±0.02 s; a non-default value — the engine stamps 5 s on every fresh sequence, see the dead-gate audit) | sequence absent/unloadable (row 1 fan-out) | ±0.02 s slack on each bound |
| 6 | timeline counted in twenty-four frames per second | fully | `sequence_display_rate_24fps` — `SEQ_DISPLAY_RATE_WRONG rate=` (display rate must be exactly 24/1; non-default — the engine stamps 30 fps) | sequence absent/unloadable (row 1 fan-out) | nothing; exact integer match |
| 7 | one continuous view through the shot's own camera — never cuts away, never falls back to the game camera | fully | `camera_cut_track_present` — `CAMERA_CUT_TRACK_MISSING tracks=` (or `CAMERA_CUT_TRACK_EMPTY sections=0`) then `camera_cut_covers_whole_shot` — `CAMERA_CUT_RANGE_WRONG` (exactly ONE section, BOTH bounds present — the seconds accessors return -1.0 on an unbounded section, so `has_start_frame`/`has_end_frame` are probed first — spanning 0.000..6.000 s ±0.02) | track gate: sequence root-cause only; range gate: no cut sections (inherits `CAMERA_CUT_TRACK_MISSING tracks=`) | a MUTED/inactive cut section — `get_sections` enumerates it and no gate reads an active flag, so a cut that is structurally perfect but deactivated (does nothing in play) passes |
| 8 | the camera is a cinematic camera (film-back / focal-length kind), not a plain viewpoint | fully | `camera_cut_targets_cine_camera` — `CAMERA_CUT_BINDING_NOT_CINE_CAMERA class=` (`isinstance` against `unreal.CineCameraActor` on the spawnable's object template; name fallback `CineCameraActor`/`CineCameraActor_C` for a possessable) | no cut section, or cut binding unresolved (`CAMERA_CUT_BINDING_UNRESOLVED guid=`) | subclassing the cine camera (deliberately allowed); film-back/focal-length VALUES are never read — any lens settings pass |
| 9 | the camera is carried BY the shot (brought, not borrowed from the level) | fully | `camera_spawned_by_sequence` — `CAMERA_BINDING_NOT_SPAWNABLE name=` (the cut's binding guid must be in `get_spawnables`) | no cut section, or cut binding unresolved; `CAMERA_SPAWNABLE_READ_ERROR` on a probe fault (error token, never credited) | nothing on ownership itself — the check is deliberately split from row 8 so "wrong camera" and "wrong ownership" are distinguishable |
| 10 | camera begins pulled back at X = -500 and slowly pushes in to X = -150 exactly as the six seconds run out | fully | `camera_pushes_in_over_full_shot` — endpoints: `CAMERA_PUSH_IN_KEYS_WRONG keys=` (≥2 keys; Location.X curve evaluated piecewise-linearly must read -500 ±1 at t=0 and -150 ±1 at t=6); shape (`_push_shape`, sampled every 0.5 s): `CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT first_key=` (keys must span the shot), `CAMERA_PUSH_IN_NOT_MONOTONIC at=` (no sample moves away from the target by >0.5 uu), `CAMERA_PUSH_IN_NOT_GRADUAL at=` (travel fraction tracks elapsed fraction within 0.20); no transform track at all: `CAMERA_TRANSFORM_TRACK_MISSING name=` | no cut section, or cut binding unresolved (both fan out); tick-resolution read failure routes to `CAMERA_PUSH_IN_READ_ERROR` (error token) | an eased (slow-in/slow-out) push inside the 0.20 progress band — deliberate; free motion on Y and Z (the prompt pins only X); keying the transform on the actor binding or its root-component child (both searched, deliberate) |
| 11 | camera "facing toward the origin" | **NOT ASSERTED** | no gate — documented dead gate (spec's dead-gate audit: at X=-500 looking at the origin is rotation (0,0,0), the default of any spawned actor; asserting it would grade nothing) | — | the camera may face any direction — backwards, up, anywhere; the prompt phrase is scene-description, deliberately ungated, and the audit says not to "add the missing check" later |
| 12 | brings its own simple stand-in for the hero — "a plain box shape is fine" | **NOT ASSERTED** (the stand-in's body) | no gate reads the hero binding's object template or class — only its NAME (row 13) and spawn ownership (row 14) | — | an EMPTY actor binding named `EvalHero` with no mesh, no visible body of any kind, passes every hero check; "any mesh" was the design intent, but NO mesh also passes |
| 13 | the cutscene refers to that object by the name `EvalHero` | fully | `hero_binding_named_evalhero` — `HERO_BINDING_MISSING bindings=` (a binding whose exact name is `EvalHero` must exist; the detail prints every binding name found) | sequence root-cause only (bindings walk is independent of the camera legs); `HERO_BINDING_READ_ERROR` on a probe fault | nothing on the name — exact string match |
| 14 | the hero is brought by the shot (spawned, not a level object) | fully | `hero_spawned_by_sequence` — `HERO_BINDING_NOT_SPAWNABLE name=` (EvalHero's guid must be in `get_spawnables`) | no binding named EvalHero (inherits `HERO_BINDING_MISSING bindings=`) | same ownership caveat as row 4 (lifetime flag unread) |
| 15 | `EvalHero` starts at Z = 0 and rises to Z = 200 over the first three seconds | partially | `hero_rises_then_holds` — `HERO_RISE_KEYS_WRONG keys=` (≥2 keys; Location.Z curve evaluated at t=0, t=3, t=6 must read 0 ±1, 200 ±1, 200 ±1 — the t=3 midpoint kills the straight 0→200 six-second ramp, which reads 100 there); no transform track: `HERO_TRANSFORM_TRACK_MISSING name=` | no binding named EvalHero (fan-out); tick-resolution fault routes to `HERO_RISE_READ_ERROR` (error token) | the rise SHAPE: unlike the camera, the hero curve is never run through `_push_shape` — it is sampled at the three anchor times ONLY, so a hero that holds Z=0 until t=2.9 and SNAPS to 200, or snaps at t=0.1 and holds, reads (0, 200, 200) and PASSES — the exact endpoint-vs-shape class of defect the 2026-07-27 camera fix closed, left open on the hero channel |
| 16 | then stays at that height for the remaining three seconds | partially | same gate — the t=6 sample of `hero_rises_then_holds` (`HERO_RISE_KEYS_WRONG keys=`); constant extrapolation after the last key means a 2-key (0s→0, 3s→200) solution passes, by design | same as row 15 | the hold is sampled at t=3 and t=6 only — a dip (e.g. 200 at t=3, 50 at t=4.5, 200 at t=6) satisfies both samples and passes "stays at that height" |
| 17 | the shot opens fully black | partially | `fade_in_from_black` — `FADE_IN_KEYS_WRONG keys=` (fade curve must read 1.00 ±0.01 at t=0; track/section presence gated first: `FADE_TRACK_MISSING tracks=` / `FADE_TRACK_EMPTY sections=0`; the fade section is infinite by construction, so keys, never bounds, are graded — via `get_all_channels`, since the fade channel has no metadata name) | sequence root-cause only; `FADE_READ_ERROR` on a probe fault | the fade COLOUR: documented dead gate (black is the constructor default) — but the default is agent-settable, so a fade section whose colour is set to white opens fully WHITE with a fully-passing curve; the value-1.0 curve is graded, the blackness is not |
| 18 | becomes fully visible over the first half second | partially | same gate — the t=0.5 sample of `fade_in_from_black` (curve must read 0.00 ±0.01 at t=0.5; polarity IS the assertion — a fade TO black reads (0,1) and fails) | same as row 17 | the fade after t=0.5 is unconstrained — keys re-darkening the shot at t=1.0 pass both samples; and within 0..0.5 only the two endpoints are sampled, so a hold-at-1.0-then-snap at t=0.49 also passes "over the first half second" |
| 19 | "Save the asset when you are done" | fully, by the substrate model | not a gate in the script — the runner grades a file overlay materialized onto a clean substrate, so unsaved editor state never reaches the grader; an unsaved sequence presents as no asset and dies at row 1 (`SEQ_ASSET_MISSING`, composed as in row 1) | unconditional | nothing |

### Holes this table found (escalation list, not paper-over)

- **Row 2 — "nothing else" is unasserted.** Extra assets anywhere inside the
  asset-writable prefixes ride along ungraded.
- **Row 3 — self-containment is only spot-checked.** Bindings other than the
  cut target and `EvalHero` may possess level actors; the "depends on nothing
  it did not bring" property is asserted for exactly two of N bindings.
- **Row 4 — "takes it away when the shot ends" has no gate.** Spawn
  ownership/lifetime is never read; a kept-alive spawnable passes.
- **Row 7 — section active/mute flags are never read** (applies equally to
  the cut, transform and fade sections): a structurally perfect but
  deactivated section passes every gate while doing nothing in play.
- **Row 11 — camera rotation ungated** (deliberate, documented dead gate —
  listed for completeness, not for fixing).
- **Row 12 — the hero stand-in's body is unasserted.** A meshless empty actor
  named `EvalHero` passes all three hero checks.
- **Row 15 — the hero rise has no shape gate.** `_push_shape` protects only
  the camera; a snap-rise reading (0, 200, 200) at the three sampled anchors
  passes — the same endpoint-only hole the camera side fixed on 2026-07-27.
- **Rows 16/18 — hold and fade windows are endpoint-sampled**, so a mid-hold
  dip or a post-fade re-darken passes.
