# Discrimination matrix — t2-weapon-fire-animation-on-trigger

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted gate, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-weapon-fire-animation-on-trigger/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/t2-weapon-fire-animation-on-trigger/…`
  — the one correct solution (mirrors the writable path INCLUDING the per-task
  segment; ThirdPerson substrate — the agent-writable module is
  `Source/ThirdPerson/`).
- `<variant>/Source/ThirdPerson/Tasks/t2-weapon-fire-animation-on-trigger/…` —
  one dir per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | PrepareTest (seam gate) | `fire seam missing` | #1 / FR-017 |
| `always-playing/` | FAIL | checkpoint 0 (t=0.5s, before any request) | `already playing before any fire request` | #2 always-playing |
| `no-animation/` | FAIL | checkpoint 1 (t=0.8s) | `no firing animation started` | #1 seam-stub half |
| `frozen-animation/` | FAIL | checkpoint 2 (t=1.4s) | `frozen, not playing` | #3 fake "playing" state |

Coverage note (bounded, argued from the named assertions rather than run as
separate submissions): a looping/never-ending fire (anti-gaming #4) dies at
cp3's `it never ended` — no dedicated variant, the always-playing variant
already proves the montage-state read and cp3 shares its mechanics; a solution
whose montage is playing at cp2 but was swapped for a DIFFERENT montage passes
the frozen gate by design (it is doing something, which is the graded
property). Acknowledged residual bounds: an internal re-trigger that replays
the clip once more and still ends before t=6.0 passes — play-count is graded
as "not permanent", not "exactly one"; and the fixture's observable is the
anim instance's MONTAGE channel, matched to the prompt's disclosed overlay
contract — a single-node `PlayAnimation` swap of the animation setup is
prompt-EXCLUDED (it violates "the existing animation setup must stay in
place"), not silently failed (../notes.md, Residual bounds).

## How to run (deterministic verifier, no agent, no tokens)
```sh
cb discriminate --task cpp/t2-weapon-fire-animation-on-trigger          # committed task
cb discriminate --task cpp/t2-weapon-fire-animation-on-trigger --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH):
```sh
UE='C:\Program Files\Epic Games\UE_5.8'
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t2-weapon-fire-animation-on-trigger/task.md \
    --submission tasks/cpp/t2-weapon-fire-animation-on-trigger/discrimination/frozen-animation \
    --ue-root "$UE" --substrate-from-live --workdir C:\cb\wd\firevar   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-30 (text half + adversarial-review fixes same day).
- **EXECUTED 2026-07-30**: `cb discriminate --task cpp/t2-weapon-fire-animation-on-trigger --wip` =
  **discriminated: YES** — reference PASS; empty, always-playing, no-animation, frozen-animation all FAIL (5/5), each `[ok ]` (credited via its named
  substring). Calibration record in ../notes.md.

# Requirements table draft — cpp/t2-weapon-fire-animation-on-trigger

(To be APPENDED to `tasks/cpp/t2-weapon-fire-animation-on-trigger/discrimination/MATRIX.md`.)

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the Enforcing-gate column is verbatim-greppable in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-weapon-fire-animation-on-trigger/FireAnimationFunctionalTest.cpp`
(the task's only L2 fixture; layers are `[L1, L2]` — no L2I grader exists for this
task), with two scoped exceptions: rows 8 and 15 quote the gate's C++ FAIL-CONDITION
expression (`Active != nullptr`, fixture lines 186/222) rather than a message
literal, and rows 18–19 are non-fixture gates whose tokens are sourced to the
files those rows name (the task spec's L1 assert block; the substrate sandbox
manifest `UE-projects/ThirdPerson/AGENT_WRITABLE.json`). Every other
Enforcing-gate span is a contiguous fragment of a
`FinishTest(EFunctionalTestResult::Failed, ...)` message literal in the fixture;
several of those literals are `FString::Printf` format strings (composed), so
quoted spans stop before the `%` conversion and never cross a literal boundary.
Checkpoint times: cp0 t=0.5 (silence check + the one fire request), cp1
t=0.8, cp2 t=1.4, cp3 t=6.0; the observable at every checkpoint is the anim
instance's active-montage channel.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the player-controlled character exists and is uniquely findable | fully | resolve gate (PrepareTest) — `Expected exactly one actor tagged 'FireHero' (the playable character) in the running level; found ` | unconditional (first gate after the UWorld harness precondition) | subclassing or renaming the character is free (the ctor-stamped tag inherits); spawning a SECOND tagged actor at runtime before PrepareTest fails here |
| 2 | the character is a character-type pawn with a body (mesh) to animate | fully | body gate (PrepareTest) — `The actor tagged 'FireHero' is not a character-type pawn with a body mesh.` | row 1 fails first | mesh asset choice is free — only `Cast<ACharacter>` + a non-null `GetMesh()` are gated, never the mannequin identity |
| 3 | the character stays alive for the whole run (implicit: "the character the player controls" is what animates) | fully, per checkpoint | hero guard (every OnCheckpoint) — `the player character is no longer valid.` | rows 1–2 (never resolved), or the rows-4/5 seam gate fires in PrepareTest (fixture lines 156–159, before `SetCheckpointSchedule` at line 164 — no checkpoint gate ever runs) | respawn-and-retag tricks: the guard checks the ORIGINAL weak pointer, so a swap fails here rather than passing |
| 4 | a function named exactly `DoFireStart`, declared so reflection can find and call it | fully | seam gate (PrepareTest) — `No parameterless reflected function named 'DoFireStart' on the player character (fire seam missing).` | rows 1–2 | implementing on the scaffold subclass or the writable stock parent — both resolve via `FindFunction` (by design); the FAIL-on-empty gate: the untouched scaffold dies here |
| 5 | `DoFireStart` takes no parameters | fully | same seam gate as row 4 — the resolver rejects any function with a real (non-return) parameter, so it FAILs via the row-4 literal `(fire seam missing).` | rows 1–2 | a return value is tolerated (documented in-source: "no parameters" reads as the argument list) |
| 6 | the body keeps a live animation setup (an anim instance) at every sample | fully, per checkpoint | anim-instance gate (every OnCheckpoint) — `the character's body has no animation instance to play on.` | rows 1–3, or the rows-4/5 seam gate fires in PrepareTest (before `SetCheckpointSchedule`, so no checkpoint gate ever runs) | only EXISTENCE is gated: a custom/blank anim instance class (ref-pose statue) passes this gate — see rows 8 and 15 for what that leaks |
| 7 | before any fire request, the body is not playing any firing animation | fully (on the montage channel) | cp0 silence gate (t=0.5, BEFORE the fixture's one fire request) — `already playing before any fire request (` | rows 1–6 | motion driven by the animation blueprint itself (idle/locomotion — or anything else non-montage) is invisible to the montage read; only a pre-armed MONTAGE trips it |
| 8 | "the character just stands under its normal idle locomotion" before the request | **NOT ASSERTED** | none — cp0 asserts only that no montage is active (its one gate FAILs on `Active != nullptr`, fixture line 186); no gate samples pose, velocity, or that the shipped ABP is actually evaluating | — | a submission that guts or replaces the idle setup (a frozen ref-pose statue, a blank custom anim instance) passes cp0 — only anim-instance EXISTENCE (row 6) is checked, never that idle locomotion plays |
| 9 | the firing animation starts promptly (within a fraction of a second) | fully | cp1 start gate (t=0.8, 0.3 s after the request) — `no firing animation started` | cp0 already FinishTest'd, or the row-3/row-6 per-checkpoint guards fire first at cp1 (they run before the switch at every checkpoint) | nothing on timing — 0.3 s is STRICTER than the prompt's "fraction of a second"; but the gate reads only the montage channel, so a non-montage overlay (manual bone transforms, a swapped anim setup) FAILs here even though it visibly animates |
| 10 | the animation plays forward (not paused/frozen) | fully | cp2 frozen gate (t=1.4) — `frozen, not playing (position ` (requires position advance >= 0.25 s over the 0.6 s since cp1) | cp0–cp1 already FinishTest'd, the row-3/row-6 guards fire first at cp2, the cp1 montage already ran its natural length and ended, OR a DIFFERENT montage is active at cp2 (the last two deliberate: short clips and re-triggers pass) | swapping to a second montage between cp1 and cp2 evades the advance check entirely (documented coverage-note residual); a playback rate as low as ~0.42x still clears the 0.25 s floor |
| 11 | plays "at normal speed" for "its natural length — about a second or two" | partially (envelope only) | no dedicated gate — bounded by row 9 (must be active at t=0.8), row 10 (must advance if still the same montage at t=1.4), and row 12 (must be over by t=6.0) | — | any clip/rate combination active at t=0.8 and silent by t=6.0: a ~0.35 s blip, a ~5 s crawl, or 0.25x slow-motion of a 1 s clip all pass — "about a second or two" is never measured |
| 12 | ends on its own; must not loop or keep playing indefinitely | fully | cp3 end gate (t=6.0, well past any natural one-shot clip) — `it never ended (still playing ` | cp0–cp2 already FinishTest'd, or the row-3/row-6 guards fire first at cp3 | a finite loop (e.g. loop-count 2) that still ends before t=6.0 passes — the graded property is "not permanent" |
| 13 | one request produces one animation, not a permanent state | partially | graded as "not permanent" via the row-12 gate (`it never ended (still playing `); play COUNT is not graded | cp0–cp2 already FinishTest'd, or the row-3/row-6 guards fire first at cp3 | an internal re-trigger that replays the clip once more and still ends before t=6.0 passes (documented residual: play-count is graded as "not permanent", not "exactly one") |
| 14 | the firing animation is an OVERLAY; the existing animation setup stays in place (do not swap/replace it) | indirectly | no named gate — the observable IS the montage channel: a submission that swaps the anim setup (e.g. a single-node PlayAnimation swap — a UE API name, not a fixture token) produces no active montage and dies at the row-9 gate `no firing animation started`; row 6 additionally requires a live anim instance at every checkpoint | rows 1–6 | the FAIL is wrong-named (the "no animation started" literal, not an overlay-specific one); per the coverage note the setup-swap route is prompt-EXCLUDED rather than distinctly asserted |
| 15 | idle/locomotion resumes seamlessly when the firing motion ends | **NOT ASSERTED** | none — cp3 asserts only that no montage is active (its gate FAILs on `Active != nullptr`, fixture line 222) plus a live anim instance (row 6); nothing samples the post-fire pose or that locomotion is evaluating again | — | a submission that permanently breaks/mutes the locomotion path as a side effect of firing (body frozen after the montage ends) passes — "resumes seamlessly" has no gate |
| 16 | the clip "reads as a firing/attack motion" ("like a real weapon-firing motion") | **NOT ASSERTED** (by design) | none — no gate inspects the montage's asset identity or content; the prompt itself discloses "judged by the character's animation state over time" | — | any clip whatsoever played as a one-shot montage (idle, death, dance) passes every gate — clip semantics are behavior-only-law territory, deliberately ungraded |
| 17 | a fire requested while the animation is still playing may be ignored | n/a — an explicit permission, not a requirement | no gate needed: the fixture issues exactly ONE `DoFireStart` call (at cp0), so the re-trigger branch is never even exercised | — | either policy (ignore or queue) is indistinguishable to the fixture |
| 18 | implement in C++ in the existing gameplay module (the code compiles) | fully | L1 build gate — UnrealBuildTool must exit 0 for BOTH build targets: `ThirdPerson Win64 Development` and its editor twin, stem `ThirdPersonEditor` (token source: `tasks/cpp/t2-weapon-fire-animation-on-trigger/task.md` L1 assert block, lines 151–152 — the full Editor target string line-wraps there, so only the stem is quotable verbatim; no fixture literal — it is a build, not an assertion) | unconditional (L2 never runs on an L1 FAIL) | a Blueprint-only montage route riding on scaffold C++ would build — but the sandbox writable set and the seam's reflection resolve still require the C++ `DoFireStart` (row 4) |
| 19 | do not edit the level, any config file, or any test file | fully, by the substrate model | not a fixture gate — sandbox exit 4: `Source/CraftBenchTests/` and `Content/Maps/` are `deny` entries in `UE-projects/ThirdPerson/AGENT_WRITABLE.json` (token source for this row), config edits gated by the semantic config lane (the same manifest's `config_writable` list; this spec declares no `config_allow`, so any ini diff rejects), plus git-HEAD materialization of the graded substrate (an on-disk fixture edit never reaches the grade) | unconditional (enforced pre-grade, before any layer) | nothing |
