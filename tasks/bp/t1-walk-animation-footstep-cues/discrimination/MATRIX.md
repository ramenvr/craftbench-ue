# Discrimination matrix — t1-walk-animation-footstep-cues

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated — fix it, or relabel the task for the weaker property it actually
tests.

> **STATUS: NOT RUNNABLE YET.** Every leg of this matrix needs a binary
> `.uasset` that does not exist on disk. The rows, the expected substrings and
> the per-variant asset specs below are complete and authored; the bytes are
> not. See **What is missing** and `../notes.md`.

## Three parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]` (`discriminate.py:227`), so a *second* table that
  repeats a variant label silently **overwrites** the first — and because a
  table without a "substring"/"message" header column yields an empty message,
  the overwrite lands a blank substring tuple and the leg can never be
  credited. This file therefore has **exactly one table with variant rows**;
  every secondary/derived observation lives in prose below it, where no `|` row
  can re-register a label. (This defect blanked 4 of 6 negative legs on the
  pilot; plan §13.1.)
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither, so it hits the broken branch.
  Pairing the token with the fixed prefix of the text that follows it in the
  script (`... found=`, `... times=`, `... durations=`, `... total=`,
  `... length=`, `... names=`) makes the cell substantive **and** keeps it a
  verbatim substring of the printed `detail`. This works whether or not the
  last-resort branch is ever fixed in code.
- **Numbers in the detail are rendered `%.3f`.** `_round3` in the introspect
  script fixes the formatting of every float it prints, so a substring may
  safely be extended with a literal number (`times=[0.300`) if a future row
  needs to be sharper. None of the rows below relies on that.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/walk_animation_footstep_cues.py`.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an *earlier* script could never be
  credited. This task declares one script, and must keep declaring one.

**ASCII rule:** every expected substring is ASCII-only. The UE log's UTF-8 bytes
are read back as cp1252, so a non-ASCII character in a detail string becomes
mojibake and the grep misses — a correct FAIL then misclassifies as
wrong-reason (live incident, `t2-homing-projectile`, 2026-07-21). The whole
introspect script is ASCII by construction.

**Error tokens are distinct from failure tokens.** Every exception path in the
script emits a `*_READ_ERROR` / `*_PROBE_ERROR` / `*_UNAVAILABLE` / `*_ABORTED`
/ `CHECK_NOT_EVALUATED` token that appears in **no** matrix row. So a broken UE
API name can never be credited as a variant's named failure — it shows up as an
uncredited FAIL, which is the signal you want. Asserted by
`tools/verify-single/tests/test_introspect_walk_footstep_cues.py::
TestErrorTokensAreDisjointFromMatrix`.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t1-walk-animation-footstep-cues/…` — the one
  correct solution. The `ThirdPerson` substrate's agent-writable Content
  carve-out is `Content/Tasks/`, so the overlay mirrors that path exactly,
  including the per-task segment.
- `<variant>/Content/Tasks/t1-walk-animation-footstep-cues/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

Note the asymmetry that makes the empty leg meaningful here: the substrate ships
BOTH clips, so an empty submission still has a loadable `A_WalkForward` with a
completely empty timeline. It therefore fails on the *content* of the clip
(`walk_has_exactly_two_footstep_cues`, found 0) rather than on the asset being
absent, and it PASSES `walk_asset_exists`, both length/frame checks and both
`jog_*` checks — `5/10`, which is correct: the baseline really is intact and the
sibling really is silent.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 10 checks green (10/10) | — | — |
| empty | FAIL | `walk_has_exactly_two_footstep_cues` | `WALK_FOOTSTEP_COUNT_WRONG found=` | the 3 dependent `walk_footstep*` checks fan out on the same root cause, and `walk_carries_no_other_cues`; `5/10` | #1 / FR-017 |
| `cues-at-wrong-times/` | FAIL | `walk_footstep_at_quarter_second` | `WALK_CUE_NOT_AT_QUARTER_SECOND times=` | `walk_footstep_at_three_quarter_second` | #2 placed by eye, not by the clock |
| `ranged-cues-not-instants/` | FAIL | `walk_footsteps_are_instantaneous` | `WALK_CUE_NOT_INSTANTANEOUS durations=` | — | #3 a span dressed as an instant |
| `extra-cues-left-on-clip/` | FAIL | `walk_carries_no_other_cues` | `WALK_CUE_TOTAL_WRONG total=` | — | #4 shotgun the timeline |
| `clip-retimed-to-short-stub/` | FAIL | `walk_timeline_length_unchanged` | `WALK_LENGTH_CHANGED length=` | `walk_frame_count_unchanged` | #5a move the goalposts |
| `cues-on-both-clips/` | FAIL | `jog_carries_no_cues` | `JOG_HAS_CUES names=` | — | #5b hit every target |

Why each "Also fails" entry is expected and does **not** make the discrimination
muddy (prose on purpose — a table here would re-register the labels and blank
their substrings):

- **empty** also fails `walk_footstep_at_quarter_second`,
  `walk_footstep_at_three_quarter_second` and
  `walk_footsteps_are_instantaneous`, all three carrying the *same*
  `WALK_FOOTSTEP_COUNT_WRONG found=0 …` detail. That is deliberate: with a
  count other than 2 there is no well-defined placement or span to grade, so
  the three dependents name the single root cause instead of inventing a
  second one. It also fails `walk_carries_no_other_cues`
  (`WALK_CUE_TOTAL_WRONG total=0`) — the total is 0, not 2.
- `cues-at-wrong-times/` also fails `walk_footstep_at_three_quarter_second`
  (`WALK_CUE_NOT_AT_THREE_QUARTER_SECOND times=`): the variant moves both cues,
  so both placement gates fire. Two independent checks catching the same defect
  is the point of splitting them (spec anti-gaming #2).
- `clip-retimed-to-short-stub/` also fails `walk_frame_count_unchanged`
  (`WALK_FRAME_COUNT_CHANGED frames=`): length and frame count are two
  independent reads of the same tampering, and neither is satisfiable by
  editing anything the submission can write — the oracle is the deny-listed
  stock clip.

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A submission that places the two cues correctly but names them something else
  (`Foot_L` / `Foot_R`) dies at `walk_has_exactly_two_footstep_cues`
  (`WALK_FOOTSTEP_COUNT_WRONG found=0`) — the same gate the empty leg
  exercises, from the opposite direction (2 events present, 0 correctly named).
  No separate variant is authored because the leg would be credited by an
  identical substring.
- A submission that puts both cues at 0.25 s dies at
  `walk_footstep_at_three_quarter_second`, not at
  `walk_footstep_at_quarter_second` — the "exactly one match per moment" rule
  means the quarter-second gate fails too (two matches, not one), so the
  reported shape is `8/10` and not a misleading `9/10`.
- A submission that DELETES `A_JogForward` dies at `jog_asset_exists`
  (`JOG_ASSET_MISSING /Game/Tasks/`) rather than passing `jog_carries_no_cues`
  by absence. No variant is authored for it because the fail-closed branch is
  covered by the offline oracle test instead, which is cheaper and does not
  need a sixth `.uasset`.
- A submission that leaves the clip uncompiled/dirty is not a state this task
  can reach: the deliverable is an animation asset, not a Blueprint, and the
  runner grades a file overlay, so unsaved editor state presents as the
  baseline bytes and dies at the count gate.

## What is missing (this matrix cannot run until these exist)

**Binary `.uasset`s cannot be authored from a text-only track.** Eight binaries
are needed. Each variant folder holds a `README-MISSING-ASSETS.md` at the exact
path the `.uasset` must occupy, describing property-by-property what to author;
**delete that README in the same commit that lands the real asset.** The full
property-level spec for the baselines and the reference is `../notes.md`.

| # | Path | What it must be |
|---|---|---|
| 0a | `UE-projects/ThirdPerson/Content/Tasks/t1-walk-animation-footstep-cues/A_WalkForward.uasset` | **baseline**, shipped in the substrate (not a submission). `notes.md` §1 |
| 0b | `UE-projects/ThirdPerson/Content/Tasks/t1-walk-animation-footstep-cues/A_JogForward.uasset` | **baseline**, shipped in the substrate. `notes.md` §1 |
| 1 | `../reference/Content/Tasks/…/A_WalkForward.uasset` | the **reference**. `notes.md` §2 |
| 2 | `cues-at-wrong-times/Content/Tasks/…/A_WalkForward.uasset` | variant. See that folder's README |
| 3 | `ranged-cues-not-instants/Content/Tasks/…/A_WalkForward.uasset` | variant |
| 4 | `extra-cues-left-on-clip/Content/Tasks/…/A_WalkForward.uasset` | variant |
| 5 | `clip-retimed-to-short-stub/Content/Tasks/…/A_WalkForward.uasset` | variant |
| 6 | `cues-on-both-clips/Content/Tasks/…/{A_WalkForward,A_JogForward}.uasset` | variant — **two** assets (the only leg that overlays the jog clip) |

Must every variant ALSO ship an unmodified copy of the other baseline? **No** —
deliberately not. `apply_submission` is a copy-only overlay with no wipe, so any
asset a submission does not carry is simply the substrate's own committed
baseline. Only the variant that must *change* `A_JogForward` overlays it.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-walk-animation-footstep-cues
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-walk-animation-footstep-cues/task.md \
    --submission tasks/bp/t1-walk-animation-footstep-cues/discrimination/ranged-cues-not-instants \
    --ue-root "$UE" --workdir C:\cb\wd\kv10var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `walk_animation_footstep_cues.py` needs no commit —
but the `.uasset` files DO need committing before a non-`--wip` grade sees them
(`run_task` materializes the substrate from git HEAD).

## Status

- Authored 2026-07-27 from the spec, text-only track. **Never executed against
  a real editor** — no leg has run in UE, because no `.uasset` exists yet.
- Every one of the six negative legs parses out of this file with a
  **non-empty, backtick-free** substring, and every substring is proven to be a
  literal the introspect script actually prints — simulated offline against a
  fake `unreal` module and joined through the REAL `discriminate.parse_matrix`
  + the REAL `layers/l2_introspect` parser by
  `tools/verify-single/tests/test_introspect_walk_footstep_cues.py`. That is
  the LOGIC oracle, not an engine oracle.
- **Still missing, in order:** (1) the eight `.uasset` binaries above — nothing
  here can run in UE without them; (2) a live-editor confirmation of the UE API
  names the offline fake cannot check (which spelling of
  `notify_name` / `notify_state_class` `get_editor_property` resolves, and the
  exact return shape of the six `AnimationLibrary` getters under `-nullrhi`);
  (3) the measured `.uasset` length and frame count of the stock
  `MF_Unarmed_Walk_Fwd`, recorded in `notes.md` §5 so the
  `clip-retimed-to-short-stub` variant can be authored to a known-different
  value.
- Shares the pilot's two harness blockers, neither of which is this task's to
  fix: `tools/verify-single/tests/test_verdict_taxonomy.py:79`
  (`test_every_shipping_spec_declares_only_landable_gating_layers`) asserts
  every spec on disk is exactly `("L1","L2")`, and the registry bookkeeping
  pass (`inventory.py`) needs a `tasks/CATALOG.md` row plus the hard-coded
  task-count claims bumped. Both are plan §9.1 / §9.2 items and are shared with
  `t1-hero-blueprint-copy-with-flashlight`, not additive to it.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `detail`-string literal emitted by the
one verifier-owned grader, `tools/verify-single/introspect/walk_animation_footstep_cues.py`
(this task is `layers: [L1, L2I]` — no L2 fixture, no map; L1 is a load-clean
precondition, never a correctness gate, so every enforcing token below is an
L2I check `detail`). Rows marked **(composed)** carry a token that is NOT a
contiguous source literal: the grader builds those details at emit time by
%-formatting a bare token constant (`WALK_MISSING_TOKEN` /
`JOG_MISSING_TOKEN` / `CUE_COUNT_TOKEN`, source lines 131–133) together with
the pre-declared asset path or the measured counts (`"%s %s"` at lines
367/525, `"%s found=%d expected=%d names=%s"` at line 404) — for those rows
grep the bare constant value, which IS verbatim in source. One blanket
fan-out precedes every per-stage read-failure route the rows below name: when
`A_WalkForward` exists but fails to load as an animation sequence or reads a
non-positive length, ALL walk checks after row 1 (rows 2–8) fail with the
uncreditable `WALK_LOAD_READ_ERROR` token (grader lines 375–383) before any
row's stated skip condition can apply — the authoritative route order is the
source. The check id in
the gate column is the durable join key; per the file's parser traps this
table names no "substring"/"message" column, so `parse_matrix` cannot
re-register any variant label from it.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the walk clip stays present at `Content/Tasks/t1-walk-animation-footstep-cues/A_WalkForward` (the edit is in place; nothing is created) | fully | `walk_asset_exists` — `WALK_ASSET_MISSING` (composed; joined to the asset path at emit) | unconditional (first walk gate) | nothing; deleting or moving the clip fans all 8 walk checks to FAIL on this token, and a clip authored at any other path is never read (the grader loads pre-declared paths only) |
| 2 | exactly two events named exactly `Footstep` (case-sensitive; no near-miss spellings, no third under the same name) | fully | `walk_has_exactly_two_footstep_cues` — `WALK_FOOTSTEP_COUNT_WRONG` (composed; joined to found/expected/names at emit) | row 1 fails, or the cue list is unreadable (records the uncreditable `WALK_CUE_READ_ERROR raised` instead) | nothing on the name itself — the match is exact string equality against `Footstep`; `footstep`/`Foot_L` count as 0 and die here |
| 3 | one of them a quarter of a second in (0.25 s) | fully | `walk_footstep_at_quarter_second` — `WALK_CUE_NOT_AT_QUARTER_SECOND times=` | rows 1–2 (a wrong count re-records the count detail on this check instead of inventing a second cause), or the trigger-time read raises (records the uncreditable `WALK_CUE_TIME_READ_ERROR raised` on exactly rows 3–4) | placement anywhere in 0.25 +/- 0.02 s; the exactly-one-match rule means two cues both at 0.25 s fail this gate too (two matches, not one) |
| 4 | the second three-quarters of a second in (0.75 s) | fully | `walk_footstep_at_three_quarter_second` — `WALK_CUE_NOT_AT_THREE_QUARTER_SECOND times=` | rows 1–2 (same fan-out), or the trigger-time read raises (same `WALK_CUE_TIME_READ_ERROR raised` route as row 3) | placement anywhere in 0.75 +/- 0.02 s |
| 5 | each of the two is an instant — no start and separate end, no occupied stretch | fully, doubly | `walk_footsteps_are_instantaneous` — `WALK_CUE_NOT_INSTANTANEOUS durations=` | rows 1–2 (same fan-out), or the duration read raises (uncreditable `WALK_CUE_DURATION_READ_ERROR raised`) | a span under the 0.001 s tolerance; both signals (UFUNCTION duration AND a ranged-event backing object) must be clean — the corroboration can only add a failure |
| 6 | those two are the ONLY things the clip raises — no third, nothing under any other name | fully | `walk_carries_no_other_cues` — `WALK_CUE_TOTAL_WRONG total=` | row 1 fails, or the cue list is unreadable (same `WALK_CUE_READ_ERROR raised` as row 2) | timeline additions that are not raised events — sync markers and float curves are invisible to the notify-event reader; arguably outside "raises", but a reviewer should know the gate counts notify events only |
| 7 | when done the clip must still run for exactly as long as today (no retime/trim/extend/re-import of the duration) | fully | `walk_timeline_length_unchanged` — `WALK_LENGTH_CHANGED length=` | row 1 fails, or the clip/stock-oracle read raises (uncreditable `WALK_LENGTH_READ_ERROR raised` / `WALK_ORACLE_UNAVAILABLE`) | +/-0.01 s of slack; the compare target is the deny-listed stock clip `/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd`, read live — the submission cannot move the goalposts |
| 8 | and contain exactly as many frames as today | fully, exact integer equality | `walk_frame_count_unchanged` — `WALK_FRAME_COUNT_CHANGED frames=` | row 1 fails, or the frame read raises (uncreditable `WALK_FRAME_READ_ERROR raised`) | nothing — exact equality against the same live stock oracle |
| 9 | "do not ... otherwise alter the clip's motion" — the motion CONTENT itself (pose keys, curves, rig association) stays the shipped walk | **NOT ASSERTED** | no gate reads pose/curve/skeleton data; rows 7–8 are the only proxies (length + frame count) | n/a | a re-import or key edit that preserves length and frame count passes all 10 checks — the walk could be replaced with a T-pose, a different gait, or a clip retargeted to another skeleton, provided it still loads as an `AnimSequenceBase` of unchanged length/frames |
| 10 | the events are raised **to gameplay while the clip plays** ("gameplay watching the walking figure is told, at those two moments") | **NOT ASSERTED** (deliberate scope cut — no PIE leg; structural presence on the timeline is the proxy) | no gate observes runtime dispatch; L2 is deliberately not declared (task spec, "Verifier specification") | n/a | a structurally perfect cue whose runtime-dispatch fields suppress firing (e.g. trigger-chance 0, min-trigger-weight, LOD/dedicated-server filters on `FAnimNotifyEvent`) grades 10/10 yet never tells gameplay anything |
| 11 | `A_JogForward` stays present (its silence is graded on the real clip, never credited to absence) | fully, fail-closed | `jog_asset_exists` — `JOG_ASSET_MISSING` (composed; joined to the asset path at emit) | unconditional (first jog gate; jog checks run whatever the walk did) | nothing; deleting the sibling fails BOTH jog checks with this token |
| 12 | `A_JogForward` is left completely silent — it raises nothing at all | fully, triple-guarded (accessor exists, two independent accessors agree about emptiness, object reads back as a positive-length animation) | `jog_carries_no_cues` — `JOG_HAS_CUES names=` | row 11 fails, or any reader doubt (records the uncreditable `JOG_CUE_READ_ERROR raised` — a broken UE API is never scored as "silent") | the jog clip has NO length/frame oracle: retiming, trimming or wholesale replacing its motion passes, provided it stays event-free and loads as a positive-length animation — the prompt only demands silence of the jog, so this is latitude, not a hole |
| 13 | "Save your work" — the edit reaches the submitted bytes | fully, by the grading model | not a gate — the runner grades a copy-only file overlay onto a clean substrate; unsaved editor state presents as the untouched baseline and dies at `WALK_FOOTSTEP_COUNT_WRONG` (composed, as row 2) with found=0 | unconditional | nothing |
| 14 | the deliverable is the named clip in the named folder (`Content/Tasks/t1-walk-animation-footstep-cues/`) | fully, by construction | not a gate — the grader loads only the pre-declared content paths (`ASSET_WALK`/`ASSET_JOG` constants); a stray file outside the agent-writable prefixes is SANDBOX-REJECT exit 4 before any layer runs | unconditional | extra assets inside writable prefixes are ignored (never loaded, never graded) — harmless debris, not a bypass |

**Holes found (rows 9 and 10).** Both trace to the same root the task spec
already documents: L2I is a structural read of a saved asset, so (a) motion
content is proxied only by length/frame equality against the stock oracle, and
(b) runtime dispatch is never observed because the task deliberately declares
no PIE leg. Row 10 is the sharper one: the spec's scope cut argues "which
events the clip carries" is fully structural, but `FAnimNotifyEvent` carries
runtime-suppression fields the grader never reads, so "carries the cue"
and "raises the cue" are not the same claim. Neither hole is reachable by the
lazy/cheating trajectories the anti-gaming notes model (both require deliberate
extra work), but per the standardization doctrine they are gate-affecting and
escalate rather than being papered over.
