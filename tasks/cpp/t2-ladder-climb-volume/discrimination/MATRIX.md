# Discrimination matrix — t2-ladder-climb-volume

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted gate, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-ladder-climb-volume/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/t2-ladder-climb-volume/…` — the one
  correct solution (mirrors the writable path INCLUDING the per-task segment;
  ThirdPerson substrate — the agent-writable module is `Source/ThirdPerson/`).
- `<variant>/Source/ThirdPerson/Tasks/t2-ladder-climb-volume/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | PrepareTest (seam gate) | `climb seam missing` | #1 / FR-017 |
| `climb-anywhere/` | FAIL | checkpoint 1 (t=1.6s, the away probe) | `climb engaged away from the ladder` | #2 location-free climb |
| `teleport-to-top/` | FAIL | continuity guard (first climb frame, ~2.7s) | `ascent jumped discontinuously` | #3 teleport to the top |
| `never-releases/` | FAIL | checkpoint 4 (t=9.8s) | `still ascending or hovering after leaving the ladder` | #4 climb never releases |

Coverage note (bounded, argued from the named assertions rather than run as
separate submissions): a volume grown to cover the whole map is self-defeating
— the away probe then stands inside it and cp1's gate fires the same way; a
seam-stub that never actually ascends dies at cp2's `no meaningful height
gain`; a hold that plummets (restores walking on DoClimbEnd) dies at cp3's
two-sided `hold its height after the climb was ended` gate; an away-side
request that is latched-but-not-acted-on is neutralized by the fixture's cp1
`DoClimbEnd` cleanup (belt-and-braces — the graded property is the no-ascent
gate, and the prompt promises only that).

Acknowledged residual bounds (single-probe / single-map, NOT gates): a cheat
that discards its FIRST-ever climb request passes the one away-probe by
construction; and a coordinate-hardcode (climb gated on X thresholds read off
the agent-visible scaffold/map constants instead of the volume) is
indistinguishable from real volume logic on this single map. Both are accepted
limits of one probe on one committed map, recorded here so nobody mistakes
them for covered.

## How to run (deterministic verifier, no agent, no tokens)
```sh
cb discriminate --task cpp/t2-ladder-climb-volume          # committed task
cb discriminate --task cpp/t2-ladder-climb-volume --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH):
```sh
UE='C:\Program Files\Epic Games\UE_5.8'
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t2-ladder-climb-volume/task.md \
    --submission tasks/cpp/t2-ladder-climb-volume/discrimination/climb-anywhere \
    --ue-root "$UE" --substrate-from-live --workdir C:\cb\wd\ladvar   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-30 (text half + adversarial review fixes same day).
- **EXECUTED 2026-07-30** (after the binary half landed):
  `cb discriminate --task cpp/t2-ladder-climb-volume --wip` =
  **discriminated: YES on the first attempt** — reference PASS; empty,
  climb-anywhere, teleport-to-top, never-releases all FAIL, each `[ok ]`
  (credited via its named substring). The top-cross epsilon and the walk/
  climb/exit timing all behaved at the shipped schedule (../notes.md).

# DRAFT: to be appended to tasks/cpp/t2-ladder-climb-volume/discrimination/MATRIX.md

## Requirements table (checklist §7, the mandatory soundness artifact)

Layers are `[L1, L2]` — no L2I grader, so every runtime gate below is a
`FinishTest(EFunctionalTestResult::Failed, ...)` literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp`
(every backticked span in a fixture-gate row is contiguous verbatim source,
never crossing a printf placeholder). Two rows are not fixture gates and claim
different sources: row 1 (L1) is enforced by UnrealBuildTool — the layer
composes the two target names at runtime from the manifest's `game_module`
("<Module>Editor" / "<Module>", composed), so row 1's backticked spans are
quoted from the contiguous runs of `tasks/cpp/t2-ladder-climb-volume/task.md`'s
L1 assert block (the Editor-target string line-wraps there after "Win64", so
only the stem `ThirdPersonEditor` is quoted whole); row 18 (placement) is
enforced by the sandbox/config-lane model, so its backticked spans grep in
`UE-projects/ThirdPerson/AGENT_WRITABLE.json` (and `Source/CraftBenchTests/`
also in the fixture's line-4 header comment). Timeline for
reading the "skipped when" column: cp0 t=0.6 (away request), cp1 t=1.6 (away
gate + walk start), arrival ~2.7 s (at-ladder `DoClimbStart`), cp2 t=4.0
(gain gate + `DoClimbEnd`), cp3 t=5.2 (hold gate + second `DoClimbStart`),
top exit ~7.3–8.5 s, cp4 t=9.8 (exit + gravity gate).

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the submission compiles into the existing gameplay module (implicit in "Implement in C++") | fully | L1 — UnrealBuildTool exits 0 for BOTH targets, `ThirdPersonEditor` and `ThirdPerson Win64 Development` (composed — see preamble; spans quoted from task.md's L1 assert block, no fixture literal; short-circuits L2 on failure) | unconditional (first layer) | warnings, dead code, extra files under the writable prefix — L1 only demands both targets link |
| 2 | the character the player controls stays spawnable and discoverable (the writable scaffold's ctor tag + game-mode wiring must survive the agent's edits) | fully | resolve gate — `Expected exactly one actor tagged 'ClimbHero' (the playable character) in the running level; found ` | unconditional (first L2 gate) | subclassing/renaming the character is free (identity by tag, tag inherits); deleting `Tags.Add(FName("ClimbHero"))` from the writable `LadderCharacter.cpp` fails HERE, not at a climb gate |
| 3 | the climber remains a walking character-type pawn (implicit: "normal movement takes over", "falls under gravity as usual") | fully | pawn-shape gate — `The actor tagged 'ClimbHero' is not a walking character-type pawn.` (Cast to ACharacter + non-null CharacterMovement) | row 2 fails first | any movement-component configuration that still casts to ACharacter; custom movement modes are free |
| 4 | the ladder volume stays discoverable with real bounds (its scaffold ctor tag is agent-writable) | fully | resolve gate — `Expected exactly one actor tagged 'LadderVolume' (the ladder) in the running level; found ` | rows 2–3 | reshaping the volume in the writable `LadderVolumeActor.cpp` is tolerated until it breaks a later behavior gate — but growing it to cover the map is self-defeating (row 8's away-probe then stands inside it) |
| 5 | a function named exactly `DoClimbStart`, reflected, no parameters | fully | seam gate — `No parameterless reflected function named 'DoClimbStart' on the player character (climb seam missing).` | rows 2–4 (resolve/pawn gates fan out first) | a return value is tolerated (only real input/output parms reject); declaring on the scaffold subclass or the writable stock parent both pass |
| 6 | a function named exactly `DoClimbEnd`, reflected, no parameters | fully | seam gate — `No parameterless reflected function named 'DoClimbEnd' on the player character (climb seam missing).` | rows 2–5 | same latitude as row 5 |
| 7 | the character stays alive/valid for the whole scenario (implicit) | fully | per-checkpoint guard — `the player character is no longer valid.` | never (checked at every checkpoint) | nothing — self-destruction at any checkpoint fails here |
| 8 | a climb request away from the ladder does nothing — no ascent, no floating | fully (one probe) | away gate at cp1 (t=1.6, one full second after the away-side `DoClimbStart` at cp0) — `observed the climb engaged away from the ladder (height rose ` (fires when Z > Z0 + 40) | rows 2–7; fixture no longer running | up to 40 uu of rise (settle-jitter tolerance); a cheat that DISCARDS its first-ever climb request passes the single probe by construction (documented residual in the matrix above); non-vertical misbehavior (spin, lateral drift) is unchecked |
| 9 | the fixture-driven walk reaches the ladder (implicit: stock walking must still work under the agent's changes) | fully | walk gate at cp2 — `The character never reached the ladder on the walk approach (phase ` (arrival = \|X − ladder center X\| < 40 by t=4.0) | rows 2–8 | walking speed/animation changes that still arrive by ~4.0 s |
| 10 | while requested AND within the volume the character ascends (meaningful, sustained rise) | fully | gain gate at cp2 — `observed no meaningful height gain (` (fires when Z − climb-start Z < 150 over the ~2.7→4.0 s window) | row 9 fires first; rows 2–8 | any gain ≥ 150 uu regardless of mechanism, provided every later gate also holds |
| 11 | the ascent rate is 300 units per second | **partially — band, not the rate** | no gate measures 300. The floor is row 10's 150 uu/~1.3 s (~115 uu/s) plus cp4's must-cross-the-top-by-~8.5 s timing (effective floor ~200 uu/s); the ceiling is row 12's 50 uu/frame (3000 uu/s) plus the geometric trap that a much-faster climber overshoots the top during Climb1 and then fails cp3's hold. No literal names the rate. | rows 9–10 | any steady rate in roughly a 0.7x–2x band around 300 uu/s passes every gate; the disclosed number itself is never verified — **HOLE (under-asserted numeric)** |
| 12 | the ascent is smooth and continuous — not a jump or a snap | fully, per-frame | continuity guard (every Climb1/Climb2 tick) — `observed the ascent jumped discontinuously (` (fires on a one-frame rise > 50 uu; disclosed rate moves ~5 uu/frame) | only during climb phases — walk/hold/post-exit frames are unguarded (the hold gate's ±60 and the away gate's +40 bound those) | stair-step motion up to 50 uu/frame; discontinuities in X/Y (only Z is guarded) |
| 13 | `DoClimbEnd` mid-climb stops the ascent and the height holds at the ladder | fully | hold gate at cp3 — `Expected the character to hold its height after the climb was ended; observed it did not (moved ` (fires when \|Z − hold Z\| > 60 at 1.2 s after the cp2 `DoClimbEnd`) | rows 9–10 fire first; rows 2–8 | drift < 60 uu over the 1.2 s window (~50 uu/s slow leak); the hold is sampled ONCE — behavior after 1.2 s is row 14's problem |
| 14 | the hold lasts "until a new request or until it leaves the ladder" — the LEAVE branch: a holding (climb-ended) character that exits the volume must also release and fall | **NOT ASSERTED** | none — the fixture always issues the second `DoClimbStart` at cp3 (1.2 s into the hold) and never displaces a holding character out of the volume; only an ACTIVE climb (Climb2) ever crosses the boundary | — | a hold implemented as unconditional levitation (ignoring the volume once `DoClimbEnd` fires) passes every gate — the ended-state's volume-exit transition is never exercised |
| 15 | climbing resumes on a NEW `DoClimbStart` after a hold | fully | top-cross gate at cp4 — `The character never climbed past the top of the ladder (expected to cross ` (the cp3 re-request must carry the hero above top − 2 uu by t=9.8) | rows 9–13 fan out first | resume latency of up to ~1–2 s (any start that still crosses the top by ~8.5 s) |
| 16 | the moment the climbing character leaves the volume past the top, the climb ends and it falls under gravity | fully (with latitude) | gravity gate at cp4 — `observed it still ascending or hovering after leaving the ladder (height ` (fires when Z > top − 50 at t=9.8, i.e. ≥ ~1.3 s after the ~7.3–8.5 s exit) | row 15 fires first (its two halves kill different cheats: never-reached vs never-released); rows 2–13 | "the moment" has ~1+ s of latitude (overshoot past the top is fine if Z is back below top − 50 by 9.8); any descent counts — a slow controlled lower, not literal gravity, passes |
| 17 | leaving the ladder CLEARS the latched request (re-climb needs a fresh `DoClimbStart`) | indirectly (this geometry) | same gravity gate as row 16 — `still ascending or hovering after leaving the ladder`: a non-cleared request re-engages the moment the straight-down fall re-enters the volume (top exit is directly above it), producing top-oscillation/hover that sits above top − 50 at 9.8 | rows 2–16 | an implementation that displaces the character LATERALLY on exit never re-enters the volume, so its latched request is never re-tested — **partial (geometry-dependent enforcement)** |
| 18 | implement in C++ in the existing gameplay module; do NOT edit the level, any config file, or any test file | fully, by the substrate model | not a fixture gate — AGENT_WRITABLE.json: `Content/Maps/` and `Source/CraftBenchTests/` are `deny` entries → SANDBOX-REJECT exit 4. Config files are NOT deny-listed: `Config/DefaultEngine.ini` + `Config/DefaultInput.ini` are `config_writable` and their ini diff is validated against the spec's `config_allow` allowlist — this spec declares none, so ANY change to them rejects on the same exit-4 path; every other Config/ path rejects by allowlist-miss. Plus git-HEAD materialization of the graded substrate (an on-disk test edit never reaches the grade). (task.md's anti-gaming entry #5 still says "Config/ ... deny-listed" — stale vs the manifest; the prohibition holds, via the config lane) | unconditional | nothing structural; within `Source/ThirdPerson/` any file layout is free |

### Holes found by this table (escalate, do not paper over)

1. **Row 14 — NOT ASSERTED**: the hold's leave-the-ladder release branch
   ("holds ... until ... it leaves the ladder") is never exercised — the
   fixture re-requests at 1.2 s into every hold and only an active climb ever
   crosses the volume boundary. An unconditional-levitation hold passes.
2. **Row 11 — under-asserted numeric**: the disclosed 300 uu/s rate is never
   measured; the gates bound it only to roughly a 0.7x–2x band (gain floor +
   top-cross timing + 50 uu/frame ceiling).
3. **Row 17 — geometry-dependent**: request-clearing on exit is enforced only
   because the fall re-enters the volume straight down; a lateral-displacement
   exit escapes the re-test.
