# Discrimination matrix — t2-homing-projectile

One row per submission; the "Expected message" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t2-homing-projectile [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.5s) | `expected exactly one actor tagged 'HomingMissile'` | #1 |
| `straight-line/` | FAIL | post-relocation | `not closing on the target` | #2 |
| `teleport-cheat/` | FAIL | first cp after t=2.5s | `u/s in a single frame` | #3 |

Notes:
- The straight-line shot keeps closing on the *moved* target for a while
  (it is flying toward the closest-approach point), so its FAIL may land at
  cp3 (2.2s) or cp4 (3.0s) depending on geometry — the message substring is
  the contract, not the checkpoint index.
- Anti-gaming note #4 (spawn-at-target) falls out of the cp0
  `initial separation` gate; argued from the named assertion rather than a
  separate submission (the teleport-cheat variant exercises the same
  motion-policing machinery live). Bounded coverage, stated honestly.
- **ASCII rule (found the hard way):** FinishTest messages and these
  substrings must be ASCII-only — the UE log's UTF-8 bytes are read back as
  cp1252, so an em dash becomes `â€”` and the substring grep misses,
  classifying a CORRECT fail as wrong-reason (this variant's first run).

## Status
- Authored 2026-07-21 from the spec + the shipped fixture.
- **RE-EXECUTED 2026-08-16**: discriminated YES, 4/4 credited — including the empty leg's FIRST credit ever: its row was `*(empty)*` (markdown emphasis), which parse_matrix deliberately skips; fixed to bare `empty` this campaign.
- Executed on real UE: Windows/UE-5.8 PASS/FAIL split confirmed (2026-07-21) — see the calibration record in `../notes.md`.

## Requirements table (checklist §7, the mandatory soundness artifact)

Layers are `[L1, L2]` — no L2I. Every backticked gate span is a contiguous
`FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t2-homing-projectile/HomingProjectileFunctionalTest.cpp`
(never spanning a printf placeholder); structural rows cite
`UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` (sandbox, exit 4) or the L1 layer.
The L1 row's target names are runtime-COMPOSED, not source literals: the runner
(`tools/verify-single/layers/l1_build.py`, line 273) builds them as
`{game_module}Editor` + the bare module from the manifest's `game_module`
(= `CraftBenchTemplate`, verbatim in AGENT_WRITABLE.json); that row is marked
"(composed)".

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed launcher stays discoverable (exactly one `MissileLauncher`) | fully | PrepareTest resolve gate — `Expected exactly one actor tagged 'MissileLauncher'; found ` | unconditional (first gate after the no-UWorld error check) | nothing at map level (the map is verifier-owned); agent BeginPlay that destroys or clones the launcher fails here, because placed-actor BeginPlay precedes PrepareTest in PIE |
| 2 | the placed target stays discoverable (exactly one `MissileTarget`) | fully | PrepareTest resolve gate — `Expected exactly one actor tagged 'MissileTarget'; found ` | row 1 fires first | same as row 1 — but only the actor's EXISTENCE is pinned, not its position (row 3) |
| 3 | launcher and target sit ~2000 units apart (the flight the task grades) | **NOT ASSERTED** | none — `InitialDistance` is measured in PrepareTest, AFTER agent BeginPlay has already run, and no gate pins it near 2000 or polices non-fixture target motion | — | the scaffold launcher/target classes are agent-writable: BeginPlay code can relocate the target onto the launcher (InitialDistance ≈ 0, first sample < 150u → instant PASS), or Tick code can drive the target toward the missile so "closing" happens with zero homing — the motion caps police only the MISSILE's displacement |
| 4 | when gameplay begins, fire exactly ONE projectile actor tagged `HomingMissile` | partially | cp0 (t=0.5s) count gate — `expected exactly one actor tagged 'HomingMissile' in flight` | the interception short-circuit fires first (closest approach already < 150u by t=0.5s) | the count is enforced ONLY at t=0.5s: `CountMissiles` is computed at every later checkpoint but its result is never checked, so a post-cp0 volley of extra tagged missiles is unpoliced (interception is still credited only to the first-pinned actor) |
| 5 | the LAUNCHER is what fires it | **NOT ASSERTED** | none — the fixture never checks spawn origin, owner, or instigator | — | any code path (GameMode, the target's own BeginPlay, a config-spawned third actor) that places one tagged actor beyond the 55% ring by t=0.5s passes; the launcher can stay inert |
| 6 | the projectile starts its flight from launcher distance (anti spawn-at-target) | partially | cp0 separation gate — `it must launch from the launcher and fly there` (fails when d < 0.55 × InitialDistance) | **the interception check precedes it**: a projectile spawned — or teleported in its spawn frame, before the fixture's first location sample — INSIDE the 150u arrival radius grades an outright PASS (anti-gaming note #4's defense is unreachable on that path) | the check is distance-from-TARGET only: spawning anywhere beyond the 55% ring (mid-air, off to the side — not at the launcher) passes |
| 7 | travels continuously — no teleporting (per-frame) | fully, ×2 slack | per-frame monitor → checkpoint FAIL — `in a single frame - impossible at the disclosed` | needs a pinned missile with a previous-frame sample: a jump inside the spawn frame is invisible (the first sample IS the post-jump location — see row 6's hole); checked FIRST at every checkpoint, so a teleporter cannot also win by interception | per-frame displacement up to 2400 u/s (40u per 60fps frame) is tolerated |
| 8 | no teleporting (checkpoint-interval belt) | fully, ×1.3 slack | closing-rate cap — `the projectile closed ` (FAIL when closed > 1200 × dt × 1.3) | cp0 (no previous distance yet); once intercepted | sustained closing up to 1560 u/s between checkpoints |
| 9 | speed ≤ 1200 u/s | partially | only rows 7–8 — both cap DISPLACEMENT, never speed | as rows 7–8 | a constant ~1500 u/s dash straight at the current target position clears both caps (1500×dt < 1560×dt checkpoint cap, 1500 < 2400 frame cap) |
| 10 | speed ≥ 600 u/s | partially (indirect only) | no floor gate exists; the working floors are the closing minimum — `not closing on the target (distance ` (≥ 50u per interval ≈ 70–100 u/s) — and the 3.0s arrival deadline (row 13), which forces average closing ≈ 620+ u/s from the cp0 ring | once intercepted | instantaneous speed is never measured: dawdle-then-sprint (within row 8's cap), or any profile averaging ≥ ~620 u/s closing, passes |
| 11 | steers toward the target its ENTIRE flight; adjusts course when the target moves | partially | closing gate — `not closing on the target` with the post-relocation suffix ` after the target relocated`; the discriminating perturbation is the fixture's cp1 (t=1.0s) target relocation of +800u lateral | intercepted first — and interception BEFORE the t=1.0s relocation is reachable within the caps: the Succeeded short-circuit (line 148) evaluates before the checkpoint closing-rate cap (line 195), so row 8's cap never sees the intercepting interval; from the cp0 55% ring (~1100u at 2000u initial) a straight ~1900 u/s dash — under row 7's 2400 u/s per-frame cap, the only cap still live — intercepts between cp0 and cp1 and grades PASS, dodging the relocation entirely (row 6's spawn-inside-150u hole is NOT required) | the whole steering requirement is dodged by the pre-relocation overspeed dash in the skip column (H6); otherwise checkpoint granularity only: ≥ 50u net closing per interval suffices; heading between checkpoints is unconstrained (a wide spiral that keeps net-closing passes the closing gates and is caught only if it misses the 3.0s deadline) |
| 12 | the projectile persists until arrival (may destroy itself only AFTER arriving) | fully | existence gate at every cp > 0 — `disappeared before reaching the target` | once closest approach < 150u (destroy-on-hit is then legal — by design, not a hole) | nothing: identity is pinned at first sighting, so destroy-and-respawn-at-target reads as a disappearance, not an arrival |
| 13 | arrives within 150 units of the target within 3.0 seconds of play start | fully | cp4 (t=3.0s) final gate — `The projectile never came within ` (plus the Succeeded short-circuit at any checkpoint when closest approach < 150u) | any earlier gate fires first | arrival = closest approach on ANY frame; flying PAST the target at full speed counts — no stop, hit event, or overlap is required |
| 14 | implement in C++ | **NOT ASSERTED** | none — no gate inspects the implementation language; only the entry point is de-facto C++ (the placed launcher is a C++ scaffold class) | — | a Blueprint projectile `.uasset` under an `asset_writable` prefix (`Content/Tasks/`, `Content/Blueprints/`, …), spawned by a one-line C++ launcher edit, passes every gate |
| 15 | in the existing gameplay module | fully (structural) | sandbox, not an L2 literal — `AGENT_WRITABLE.json` `writable` = `Source/CraftBenchTemplate/` + `Content/Tasks/`; any non-asset file outside it is exit 4 SANDBOX-REJECT | unconditional (pre-build, every submission file) | asset files under the wider `asset_writable` prefixes are also accepted — which is exactly row 14's lane |
| 16 | do not edit the level | fully (structural) | sandbox deny — `Content/Maps/` is on the `deny` list (deny wins over any allow) → exit 4 SANDBOX-REJECT | unconditional | RUNTIME mutation of placed actors is not a level edit and is untracked — row 3's hole |
| 17 | do not edit any test file | fully (structural) | sandbox deny — `Source/CraftBenchTests/` on the `deny` list → exit 4; plus the runner materializes the graded substrate from git HEAD, so an on-disk fixture edit never reaches the grade (human review gates committed ones) | unconditional | nothing |
| 18 | the submission builds (implied by "implement") | fully | L1 (composed) — UBT builds BOTH the Editor and Game targets, names composed in `tools/verify-single/layers/l1_build.py` as `{game_module}Editor` + the bare module (line 273), where `game_module` = `CraftBenchTemplate` (verbatim in AGENT_WRITABLE.json); each must exit 0, short-circuit on first failure; L2 requires L1 | never (gating layer) | nothing |

### Holes this table found (escalate, per the §7 doctrine)

- **H1 (rows 4/6/7 — ordering defect):** the interception short-circuit
  (`MinDistanceSeen < 150 → Succeeded`) is evaluated BEFORE the cp0 count and
  spawn-separation gates, so spawning the tagged projectile — or teleporting
  it within its spawn frame, before the fixture's first sample — inside the
  150u arrival radius grades an outright PASS. Anti-gaming note #4's stated
  defense is unreachable on that path.
- **H2 (row 3):** placed-actor positions are never pinned. `InitialDistance`
  is measured after agent BeginPlay, and target motion by non-fixture code is
  unpoliced — agent-writable scaffold code can move the target to the
  launcher (or chase the missile) and PASS with zero homing.
- **H3 (row 5):** "the launcher must fire" has no gate — no spawn-origin,
  owner, or instigator check anywhere in the fixture.
- **H4 (row 14):** "implement in C++" has no gate — a Blueprint projectile
  asset in an `asset_writable` lane, spawned from a minimal C++ launcher
  edit, passes every gate.
- **H5 (row 4):** "exactly one projectile" is checked only at t=0.5s; the
  per-checkpoint `CountMissiles` result is computed but unused at cp>0.
- **H6 (rows 9/10/11):** the 600–1200 u/s band is never measured as speed —
  the ceiling leaks to ~1560 u/s sustained / 2400 u/s per-frame, and the
  600 floor exists only via the 3.0s arrival deadline. Worse than a band
  leak: on the interval that INTERCEPTS, even the 1560 u/s checkpoint cap
  never evaluates (the Succeeded short-circuit at line 148 precedes the
  closing-rate cap at line 195), so a straight ~1900 u/s dash from the cp0
  55% ring intercepts between cp0 and cp1 — overspeed converts directly
  into dodging the cp1 steering perturbation (row 11), independent of H1's
  spawn-inside-150u hole.
