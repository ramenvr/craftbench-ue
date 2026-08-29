# Discrimination matrix — kp-anim-track-bake

The self-validation oracle: the reference solution must PASS and the empty
leg must FAIL **at the predicted check, via the named substring**. A
wrong-reason FAIL (L1 build failure, a different check, a `0`-check/`error`
L2I verdict) means the verifier is NOT discriminated — fix it, or relabel
the task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package ships
**no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements table**
below is the mandatory soundness artifact.

> **STATUS: TEXT-ONLY (authoring-lane run pending).** No binaries exist
> yet. `../aids/author_reference.py` duplicates the stock walk cycle into
> the task folder (the committed BASELINE), bakes the reference track,
> prints the baseline pin values, self-grades 5/5 once the pins land, and
> harvests both artifacts. The grader fails `baseline_state_intact`
> CLOSED on the unpinned sentinel until then (the re-pin law).

## Parser traps this matrix is written against (inherited from the python set)

- **ONE parseable row-table** (`parse_matrix` overwrite trap); the
  requirements table names no column "substring"/"message".
- **Every "Expected substring" cell is a backtick-wrapped literal with a
  space or `=`**, a verbatim contiguous span of ONE source literal in
  `tools/verify-single/introspect/kp_anim_track_bake.py`, never crossing a
  printf placeholder. ASCII-only.
- **Error tokens are disjoint from credited tokens**: `ANIMBAKE_PROBE_ERROR`
  / `ANIMBAKE_CHECK_UNREACHED` / `ANIMBAKE_ENUM_UNAVAILABLE ` /
  `ANIMBAKE_KEYS_UNREADABLE track=` / `ANIMBAKE_LENGTH_UNREADABLE` appear
  in no row below — a broken UE API surfaces as an uncredited FAIL.

## Layout (folder-local; agent-writable prefixes only)

- Substrate baseline (committed with the pins, aid-produced):
  `UE-projects/ThirdPerson/Content/Tasks/kp-anim-track-bake/AS_TaskWalk.uasset`
  — the unmodified duplicate of the stock unarmed walk cycle.
- `../reference/Content/Tasks/kp-anim-track-bake/AS_TaskWalk.uasset` — the
  same asset carrying the baked reference track (`WalkPhase`, keys
  `0.0 -> 0.0` and `length -> 1.0`). **EMPTY until the authoring-lane
  run**; do not fabricate binaries.
- empty leg — run IMPLICITLY by `cb discriminate`: the workdir keeps the
  untouched baseline, which carries zero new tracks.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all 5 checks green (5/5) |
| empty | FAIL | `new_named_track_exists` | `ANIMBAKE_NO_NEW_TRACK baseline=` | checks 1–2 PASS on the untouched baseline (by design — the substrate ships the asset); checks 4–5 fan out on the same root (`3/5` is the empty score, and ONLY the named token distinguishes it) |
| `track-covers-only-the-start/` | FAIL | `new_track_spans_timeline` | `ANIMBAKE_TRACK_SPAN_SHORT need=` | **MEASURED 4/5 in the authoring boot** (self-graded by the real grader). The track exists and VARIES, so checks 3 and 4 PASS on purpose; its keys sit in the opening tenth of the clip. The grader's window is `[<= SPAN_FRACTION*len .. >= (1-SPAN_FRACTION)*len]` = `[<=0.150 .. >=1.350]` for the pinned 1.5s clip, and the first key at 0.0 satisfies the OPENING bound deliberately — so the leg fails on the closing bound alone. The only leg that isolates check 5. |
| `track-is-flat/` | FAIL | `new_track_varies` | `ANIMBAKE_ALL_NEW_TRACKS_FLAT` | **MEASURED 3/5 in the authoring boot.** Spans the whole clip but every key holds the same value. **Fails TWO checks by the grader's own design** — check 5 emits `ANIMBAKE_NO_VARYING_TRACK (check 4 failed)` whenever check 4 fails, so NO leg can isolate check 4 alone and refusing this shape would mean never probing it. The cascade is DECLARED in the authoring table, and the harvest gate demands the failure set equal `{new_track_varies, new_track_spans_timeline}` exactly, so an unforeseen third failure would have refused it. **NB it scores 3/5 exactly like the `empty` leg**, whose failures fan out from check 3 instead — the score alone cannot tell them apart, only the named token can, which is why the token is the credited artifact and not the ratio. |

**The empty leg scores 3/5, not 0/5** — the asset resolves and the
baseline guard holds on an untouched substrate. That is deliberate
(check 2 is a collateral-damage GUARD, not a discriminator; task.md's
dead-gate audit calls both rows out), and it is why the empty row's
credit is the named substring, never the score.

## Requirements table (checklist §7, the mandatory soundness artifact)

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a named numeric track exists on `AS_TaskWalk` (name is the agent's choice) | fully | `new_named_track_exists` — `ANIMBAKE_NO_NEW_TRACK baseline=` (new = not in the pinned baseline inventory, so renaming a stock track cannot mint a "new" one without also tripping row 4) | asset missing/unloadable (`task_walk_asset_resolves` fans out via `ANIMBAKE_ASSET_MISSING path=` / `ANIMBAKE_ASSET_UNLOADABLE path=`) | any number of extra tracks — unconstrained by design |
| 2 | keys span the clip: first key in the opening tenth, last in the closing tenth | fully | `new_track_spans_timeline` — `ANIMBAKE_TRACK_SPAN_SHORT need=` (raw key times, no interpolation surface) | no varying track (row 3's token fans out as `ANIMBAKE_NO_VARYING_TRACK `) | keys 10.1%–89.9% latitude inside the tenths — disclosed generosity |
| 3 | the value changes across the clip (not a flat constant) | fully | `new_track_varies` — `ANIMBAKE_ALL_NEW_TRACKS_FLAT ` (first-key vs last-key VALUES, epsilon 0.001) | no new track (row 1 fans out) | a monotone rise is the example, not a demand — any first!=last shape passes, deliberate |
| 4 | everything the animation already carries survives (no removed tracks, same length) | fully | `baseline_state_intact` — `ANIMBAKE_BASELINE_CURVE_REMOVED missing=` / `ANIMBAKE_LENGTH_CHANGED got=` (pinned inventory + 0.01s length tolerance; `ANIMBAKE_BASELINE_UNPINNED ` is the fail-closed sentinel, never a credit) | never (guard runs whenever the asset loads) | key-level edits INSIDE surviving stock tracks (accepted residual below) |
| 5 | saved in place, same folder, same name | fully | the pre-declared path IS the read (`task_walk_asset_resolves` — path identity, never name scanning); an asset saved elsewhere is simply not read | unconditional | nothing — an unsaved edit does not exist to the harness |

## Accepted residuals (documented, not defended)

- **Key-level edits inside stock tracks are invisible** (row 4): the
  guard pins track NAMES and clip length, not stock key data. Accepted:
  pinning full key arrays would make the guard brittle against benign
  editor re-serialization, and no graded outcome depends on stock key
  values.
- **Mechanism-agnostic by basket law**: editor scripting, editor UI, and
  MCP-authored states are indistinguishable to every gate — deliberate
  (the python-basket law; the draft's mechanism gate was cut as
  unreachable, task.md provenance).
- **Track semantics are not graded**: the track need not drive anything
  (no anim-graph consumer, no gameplay read). The row's capability is
  programmatic track authoring; wiring a consumer is a different task.
- **No camera plan (`cameras.json` (the camera-plan lane; not part of this release))**: the task authors no scene —
  checklist step 5 is N/A by shape.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-anim-track-bake --wip
```

Per-leg fallback while iterating:

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-anim-track-bake/task.md \
    --submission tasks/python/kp-anim-track-bake/reference \
    --ue-root "$UE" --workdir C:\cb\wd\animbake     # expect exit 0
```

## Status

- Authored 2026-08-12, text-only track. **Never executed against a real
  editor.** The whole graded surface rides ONE engine library
  (`unreal.AnimationLibrary`, `ScriptName` confirmed at
  `AnimationBlueprintLibrary.h:65`) whose four calls
  (`get_animation_curve_names` / `get_float_keys` /
  `get_sequence_length` / write-side `add_curve`+`add_float_curve_key`)
  are the authoring-lane spike.
- **Still missing, in order:** (1) the baseline duplicate + reference
  binaries + `BASELINE_*` pins (one aid run, one commit — the re-pin
  law); (2) the refgate certificate; (3) the empty-FAIL discriminate leg
  on the next sweep.

> **UPDATE 2026-08-13 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - the reference binaries are committed
> (eb36cfb, pins in the same commit) and `cb refgate` refgated PASS from git HEAD (160 s, 2026-08-12/13). The AnimationLibrary surface works headless end to end; the stock walk duplicate carries ZERO float tracks (pinned: BASELINE_CURVE_NAMES=(), BASELINE_LENGTH=1.5); self-grade 5/5 (KPBAKE-DONE), substrate baseline restored byte-verified. The
> empty-FAIL leg rides the next `cb discriminate` sweep.
