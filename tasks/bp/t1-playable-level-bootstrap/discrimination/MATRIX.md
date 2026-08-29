# Discrimination matrix — t1-playable-level-bootstrap

The self-validation oracle: the reference solution must PASS and the empty
leg must FAIL **at the predicted check, via the named substring**. A
wrong-reason FAIL (L1 build failure, a different check, a `0`-check/`error`
L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated —
fix it, or relabel the task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package ships
**no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements table**
below is the mandatory soundness artifact. Author a variant only when a
table row exposes a requirement whose defense turns out not to exist.

> **STATUS: TEXT-ONLY (authoring-lane run pending).** No binaries exist yet;
> `../aids/author_reference.py` builds the reference and self-grades it
> 12/12 against the real introspect before harvesting. The grader logic was
> proven offline 2026-08-11 through fourteen fake-`unreal` legs (see
> `../notes.md` §5).

## Parser traps this matrix is written against (inherited from the bp L2I set)

- **ONE parseable row-table.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table with a "substring" column
  and matching row labels would silently overwrite the first. This file has
  exactly one table with submission rows; the requirements table
  deliberately names none of its columns "substring" or "message" and its
  first cells are requirement prose, so `parse_matrix` skips it entirely.
- **Every "Expected substring" cell is a backtick-wrapped literal that
  contains a space or `=`** — `_extract_substrings` keeps only "substantive"
  backticked spans; a bare `SCREAMING_SNAKE` token hits the broken
  last-resort branch and can never match.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **Substrings are matched against the raw `detail` string inside the
  `CRAFTBENCH-INTROSPECT-JSON` block**, and every cell below is a verbatim
  contiguous span of ONE source literal in
  `tools/verify-single/introspect/kp_playable_level_bootstrap.py` — never a
  span that crosses a printf placeholder or an adjacent-literal seam (the
  static oracle greps source literals).
- **ASCII rule:** every expected substring is ASCII-only (the UE log's UTF-8
  read back as cp1252 turns anything else into mojibake and the grep
  misses).
- **Error tokens are distinct from failure tokens.** Every exception path in
  the script emits `*_PROBE_ERROR` / `*_READ_ERROR` / `*_ABORTED` /
  `CHECK_NOT_EVALUATED`, none of which appears in any row below — a broken
  UE API name surfaces as an uncredited FAIL, never as a credited named
  failure. (Observed directly: run the script with no `unreal` module and
  all 12 checks fail with `BOOT_LEVEL_ASSET_PROBE_ERROR`, which no row
  claims.)

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Content/Tasks/t1-playable-level-bootstrap/` — the one
  correct solution: `L_PlayableBootstrap.umap` + the two authored Blueprint
  assets (plus, if the editor saves One-File-Per-Actor, mirrors under
  `../reference/Content/__ExternalActors__/Tasks/…` and
  `../reference/Content/__ExternalObjects__/Tasks/…` — all three prefixes
  are `asset_writable` in `UE-projects/ThirdPerson/AGENT_WRITABLE.json`).
  **EMPTY until the authoring-lane run**; do not fabricate binaries.
- empty leg — run IMPLICITLY by `cb discriminate` (a throwaway empty dir;
  nothing to author). Its row documents the expected first-gate failure.

This task ships **no baseline asset**: the substrate contains nothing under
`Content/Tasks/t1-playable-level-bootstrap/`, so the empty leg is a
genuinely empty deliverable and scores `0/12`.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all 12 checks green (12/12) |
| empty | FAIL | `level_asset_exists` | `BOOT_LEVEL_MISSING /Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap` | the other 11 checks fan out on the same root cause (`0/12`) |
| `floor-beside-the-start/` | FAIL | `floor_under_player_start` | `BOOT_FLOOR_NOT_UNDER_START start=` | **MEASURED 11/12** in the authoring boot (self-graded by the real grader). The whole ruleset chain is wired and the floor still EXISTS — `floor_candidate_present` PASSES with `count=1` — it is simply moved 12000 units sideways so nothing collidable lies under the marker. That separation is the point: this leg distinguishes *a floor exists* from *a floor is under you*, which on a task called "playable level bootstrap" is the difference between spawning on ground and falling through the world. The only leg that credits the floor token. |
| `two-player-starts/` | FAIL | `player_start_exactly_one` | `BOOT_START_COUNT_WRONG count=` | **MEASURED 10/12.** A second `PlayerStart` at (600,0,110); everything else is the reference's. **Fails TWO checks by the grader's design** — `_start_check` returns `None` for any count != 1 (:615-620) and the floor check then `_fanout`s (:695-697). The cascade was TRACED before authoring, not discovered by a refusal, and the harvest gate demanded that exact pair. **Read the cascade carefully:** the fanned-out `floor_under_player_start` reports the UPSTREAM token (`BOOT_START_COUNT_WRONG count=2`), not a floor message — so a row that credited the floor check at a floor substring would be wrong about this leg. That is what `floor-beside-the-start` is for. |

## Requirements table (checklist §7, the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. Every backticked span
in the *verbatim token* column is a contiguous literal in
`tools/verify-single/introspect/kp_playable_level_bootstrap.py` (`grep`
finds it in source, and the script prints it inside the failing check's
`detail`). File:line anchors are into that script at authoring time; the
check id is the durable join key if lines drift.

| # | Prompt requirement | Asserted | Enforcing check — verbatim token (file:line) | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a level asset saved at `Content/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap` | fully | `level_asset_exists` — `BOOT_LEVEL_MISSING /Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap` (kp_playable_level_bootstrap.py:725) | unconditional (first gate) | nothing — every other check fans out from this root cause |
| 2 | the level opens and contains placed objects | fully | `level_opens_with_actors` — `BOOT_LEVEL_LOAD_FAILED path=` (:341) / `BOOT_ACTOR_LIST_EMPTY the loaded level enumerated zero actors` (:346) | asset missing (row 1 fans out) | nothing; an unopenable or empty level fails all remaining checks with one named cause |
| 3 | the level itself carries a per-level play-rules override | fully | `gamemode_override_present` — `BOOT_GAMEMODE_OVERRIDE_NONE the level carries no per-level game-rules override` (:471); plumbing check `world_settings_resolved` carries only probe-class tokens (no row credits them) | level missing/unopenable (rows 1–2 fan out) | nothing at this layer; WHERE the override points is rows 4–5 |
| 4 | the ruleset is an asset the agent authored, saved in the task folder | fully | `gamemode_is_task_blueprint` — `BOOT_GAMEMODE_NOT_TASK_ASSET class_path=` (:481) / `BOOT_GAMEMODE_NOT_BLUEPRINT_CLASS class_path=` (:482) | override unset (row 3 fans out) | asset NAME is free (deliberate — the verifier resolves through the wiring, never by name) |
| 5 | the ruleset really is a play-rules object the engine can consult | fully | `gamemode_is_gamemode_subclass` — `BOOT_GAMEMODE_WRONG_BASE class=` (:504) | override unset (row 3), CDO unresolvable (probe token, uncredited) | any legitimate rules SUBCLASS passes (`isinstance`) — accepted by design |
| 6 | the ruleset names a default controllable body | **partially** (dead alone — a fresh ruleset seeds the engine's built-in stand-in, non-None; the LIVE defense is row 7) | `default_pawn_class_present` — `BOOT_DEFAULT_PAWN_NONE the ruleset names no default controllable body` (:521) | rows 3–4 prerequisites fan out | wiring the built-in stand-in passes THIS row only — and then dies at row 7's prefix gate |
| 7 | the body is a second asset authored in the task folder | fully | `default_pawn_is_task_blueprint` — `BOOT_PAWN_NOT_TASK_ASSET class_path=` (:533) / `BOOT_PAWN_NOT_BLUEPRINT_CLASS class_path=` (:534) | pawn class unset (row 6 fans out) | parenting from stock content is allowed (the AUTHORED asset is what must live in the folder) — deliberate, prompt says so |
| 8 | the body is a possessable player body | fully | `default_pawn_is_pawn_subclass` — `BOOT_PAWN_NOT_PAWN_CLASS class=` (:554) | pawn class unset (row 6 fans out) | any pawn subclass passes — accepted, that IS the outcome; nothing gates movement/input wiring (accepted residual below) |
| 9 | exactly one spawn marker | fully | `player_start_exactly_one` — `BOOT_START_MISSING count=0 expected=1 no player spawn marker is placed` (:594) / `BOOT_START_COUNT_WRONG count=` (:599) | rows 1–2 fan out | marker's own location is unconstrained — deliberate; the floor gate is relative to it (row 11) |
| 10 | real collision-carrying ground at least 200 units across exists | fully | `floor_candidate_present` — `BOOT_FLOOR_NO_CANDIDATE examined=` (:668) | rows 1–2 fan out | any collidable surface with the footprint counts, including a query-only volume (accepted residual below) |
| 11 | that ground sits directly under the marker, top within 10 above / 500 below | fully | `floor_under_player_start` — `BOOT_FLOOR_NOT_UNDER_START start=` (:694) | no unique marker (row 9's token fans out) or no candidate (row 10 fans out) | anything inside the 50-unit XY containment margin (verifier-only generosity) |
| 12 | "no project-wide setting touched" | fully, by the SANDBOX not the introspect | not a check id — `UE-projects/ThirdPerson/AGENT_WRITABLE.json` rejects writes outside the writable set (deny wins; `Config/` edits are allowlist-missed / semantically gated by `tools/verify-single/config_lane.py`) | never (path gate precedes grading; exit 4) | in-level facts only — which is the point: the override MUST live in the level to pass rows 3–5 |
| 13 | "save everything to disk" | fully | same gates as rows 1, 4, 7 — only on-disk overlay files reach the graded substrate (the harness materializes the submission from files; unsaved editor state does not exist to it) | unconditional | nothing |

Every prompt requirement has an enforcing gate — nothing is unenforced
prose — so no targeted variant is owed under §7. Rows 6, 8 and 10 are
honest about being partial or tolerance-bounded; all are accepted residuals,
argued below, not holes.

## Accepted residuals (documented, not defended)

- **Playability is graded as WIRING, not as a play session.** No PIE runs in
  the L2I lane: nothing asserts the pawn can actually walk, that input maps,
  or that the camera behaves. The graded outcome is the bootstrap chain
  (override → rules → pawn → start → floor) — the stated scope of this
  task; a play-session gate would be an L2 task on a committed map, which
  contradicts the agent-authored-level premise. Recorded, not defended.
- **The pawn gate is `isinstance`-deep only** (row 8): a bare pawn subclass
  with no movement or mesh passes. Deliberate — the prompt says "building it
  on top of the playable character is fine and expected" but does not demand
  it, so the verifier cannot fairly demand more than pawn-ness.
- **A query-only collision volume can satisfy the floor gate** (row 10): the
  colliding-bounds heuristic does not distinguish blocking from overlap
  collision. Accepted: reading per-component blocking responses generically
  is fragile under headless reflection, and the free value (no collision at
  all) is still excluded.
- **Extra actors are unconstrained.** Decorations, lights, or leftover
  template actors do not fail anything. Deliberate: no graded outcome
  depends on the level containing nothing else.
- **Asset names are unconstrained** (rows 4, 7): the verifier resolves the
  two authored assets through the level's own wiring. An agent may name them
  anything; only the folder and the class facts are graded.
- **Mechanism-agnostic by basket law**: hand-authored, script-authored, and
  MCP-authored states are indistinguishable to every gate.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-playable-level-bootstrap --wip
```

(`--wip` until the reference binaries and this task's first commit land; the
runner materializes the graded substrate from git HEAD.) Per-leg fallback
while iterating (short `--workdir` dodges Windows MAX_PATH):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-playable-level-bootstrap/task.md \
    --submission tasks/bp/t1-playable-level-bootstrap/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpboot       # expect exit 0
```

Then open the workdir's `report.json` and the L2I log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the verdict. L2I
graders are read from the LIVE working tree, so iterating on
`kp_playable_level_bootstrap.py` needs no commit — but the level/asset
binaries DO need committing before a non-`--wip` grade sees them.

## Status

- Authored 2026-08-11, text-only track. **Never executed against a real
  editor** — no binaries exist yet; the map-load lane itself is proven
  (kp-spawn / audit refgates), but THIS script's world-settings and
  CDO-wiring routes are not yet live-confirmed.
- **Proven offline against the real grader logic**: a fake `unreal` module
  drove `kp_playable_level_bootstrap.py` through fourteen legs
  (reference-shaped 12/12 PASS; missing-level, load-refused, empty-world,
  no-override, stock-gamemode, native-default-pawn, non-pawn-body,
  wrong-base, no-start, two-starts, uncollidable-floor, floor-elsewhere,
  floor-too-deep all FAIL at the predicted check with the predicted token),
  the verdict block parsed at a constant 12-check denominator, and the
  script is ASCII throughout with no automation-marker collision.
- **Still missing, in order:** (1) the reference binaries
  (`../aids/author_reference.py` builds and self-grades them — that run is
  also the live spike for the world-settings write/read routes); (2) the
  empty-FAIL discriminate leg; (3) a `cameras.json` (the camera-plan lane; not part of this release) camera plan (checklist
  step 5) once the scene exists.

> **UPDATE 2026-08-12 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - corpus/reference artifacts are
> committed and `cb refgate` refgated PASS from git HEAD (202 s, 2026-08-12). The empty-FAIL leg rides the
> next `cb discriminate` run.
