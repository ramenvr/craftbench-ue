# Discrimination matrix — tp2-sprint-stamina

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted checkpoint, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/tp2-sprint-stamina/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/tp2-sprint-stamina/…` — the one
  correct solution (mirrors the writable path INCLUDING the per-task segment;
  ThirdPerson substrate — the agent-writable module is `Source/ThirdPerson/`).
- `<variant>/Source/ThirdPerson/Tasks/tp2-sprint-stamina/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | PrepareTest (seam gate) | `sprint seam missing` | #1 / FR-017 |
| `permanent-boost/` | FAIL | checkpoint 2 (t=6.2s) | `after stamina exhaustion` | #2 permanent boost |
| `no-threshold/` | FAIL | checkpoint 3 (t=7.0s) | `below-threshold sprint request` | #3 cosmetic stamina (floor missing) |

Coverage note (bounded, argued from the named assertions rather than run as
separate submissions): the cruder constructor-time 850 hardcode dies even
earlier than `permanent-boost/`, at the cp0 baseline gate (`existing walking
speed unchanged`); a latch-at-threshold implementation (below-floor request
remembered and auto-started when regen crosses 30 at t=6.5) dies at the same
cp3 gate as `no-threshold/`.

## How to run (deterministic verifier, no agent, no tokens)
The one-command form runs the whole matrix (reference → PASS, implicit empty →
FAIL, every variant → FAIL matched against its named substring):
```sh
cb discriminate --task cpp/tp2-sprint-stamina          # committed task
cb discriminate --task cpp/tp2-sprint-stamina --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH):
```sh
UE='C:\Program Files\Epic Games\UE_5.8'
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/tp2-sprint-stamina/task.md \
    --submission tasks/cpp/tp2-sprint-stamina/discrimination/no-threshold \
    --ue-root "$UE" --substrate-from-live --workdir C:\cb\wd\tp2var   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-23 from the spec + the shipped fixture.
- Executed on real UE: **Windows/UE 5.8.0, 2026-07-23 — discriminated 1/1**
  (`cb discriminate --wip`, short wd-root): reference PASS, empty FAIL,
  `no-threshold` FAIL, `permanent-boost` FAIL, every FAIL via its named
  substring. Calibration record: `../notes.md` (all six checkpoints
  dead-center; cp3 moved 7.2 → 7.0 after the first matrix caught the
  friction-braking settle — see notes).

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous verbatim literal from ONE
`FinishTest(EFunctionalTestResult::Failed, ...)` call in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/tp2-sprint-stamina/SprintStaminaFunctionalTest.cpp`
(never spanning a printf placeholder); this task's layers are `[L1, L2]`, so
there is no L2I gate family — the placement row (15) is enforced by the sandbox
model in `UE-projects/ThirdPerson/AGENT_WRITABLE.json`, not by a fixture literal.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the playable character stays discoverable and is a walking character-type pawn | fully | resolve gate — `Expected exactly one actor tagged 'SprintHero' (the playable character) in the running level; found ` / pawn-type gate — `The actor tagged 'SprintHero' is not a walking character-type pawn.` | unconditional (first gates; a missing UWorld is an Error verdict, not a FAIL) | subclassing or renaming the scaffold class is free — identity is the ctor-stamped tag, which inherits; destroying or duplicating the pawn at runtime dies here or at the row-14 validity guard |
| 2 | a function named exactly `DoSprintStart`, reflected (engine-callable), no parameters | fully | seam gate — `No parameterless reflected function named 'DoSprintStart' on the player character (sprint seam missing).` | row 1 (pawn unresolvable) | a return value is tolerated (deliberate: the prompt's "no parameters" is read as the argument list); implementing on the scaffold subclass or the stock parent grades identically |
| 3 | a function named exactly `DoSprintEnd`, reflected, no parameters | fully — existence + signature ONLY | seam gate — `No parameterless reflected function named 'DoSprintEnd' on the player character (sprint seam missing).` | rows 1-2 | the BODY is entirely free — see row 4 |
| 4 | `DoSprintEnd` actually ends an active sprint | **NOT ASSERTED** | none — the fixture resolves `SprintEndFn` in `PrepareTest` but never invokes it (`InvokeSeam(SprintEndFn)` does not exist in the source); every sprint termination the trace observes is exhaustion-driven | n/a | an empty-bodied `DoSprintEnd` — a character that can never voluntarily stop sprinting — grades PASS on the full trace |
| 5 | the normal (non-sprinting) maximum ground speed stays unchanged (~500 uu/s) | fully at the six sampled instants | baseline gate (cp0, t=1.0) — `(existing walking speed unchanged, no sprint requested); observed ` (absolute band [400,600]); re-checked as walk-ratio [0.85,1.15] of the measured baseline at cp2/cp3/cp4 | checkpoint reached only if the row-14 validity guard passed | any baseline in [400,600]; a walk-speed drift up to +/-15% of the run's own measured baseline; transients between the six undisclosed instants are invisible |
| 6 | while sprinting, max ground speed is 1.7x the normal value | fully | sprint-ratio gate (cp1, t=3.0) — `Expected sprint speed ~1.7x baseline while sprinting; observed ratio ` (band [1.55,1.85] of measured V0); re-checked at cp5 | rows 1-5 (cp0 must have measured V0) | any multiplier in [1.55,1.85]; the mechanism is free — anything producing that grounded 2D-velocity ratio passes (behavior-only by design, max-walk-speed change not inspected) |
| 7 | stamina starts at 100 and drains at 25 per second while sprinting | indirectly (window-bounded) | cp1 (still sprinting at t=3.0, token of row 6) + exhaustion gate (cp2, t=6.2) — `Expected speed back at baseline after stamina exhaustion (auto sprint end at 0); observed ratio ` | rows 1-6 | stamina is never read — only behavior is; any start/drain pair whose first-sprint budget lands in (2.0, 5.2] s passes (e.g. 60 draining at 20/s), provided the same constants also satisfy rows 9/11/13 |
| 8 | at stamina 0 the sprint ends automatically and speed returns to normal, even if `DoSprintEnd` was never called | fully | exhaustion gate (cp2, t=6.2) — same token as row 7; the fixture NEVER calls `DoSprintEnd`, so the trace is exactly the "never called" case | rows 1-6 | the zero-crossing instant is free anywhere in (3.0, 6.2); reversion latitude +/-15% of baseline |
| 9 | stamina regenerates at 20 per second while not sprinting | indirectly (window-bounded) | below-floor gate (cp3, token of row 11: stamina must still be under 30 at t=6.2, so regen < 25/s) + re-sprint gate (cp5, t=10.5) — `Expected sprint to work again after stamina regenerated; observed ratio ` (needs >= 37.5 by t=9.0 at nominal drain, so regen >= ~9.4/s) | rows 1-8 fan out first | any regen rate in roughly [9.4, 25) per second passes with the nominal drain and floor |
| 10 | regeneration is capped at 100 | **NOT ASSERTED** | none — stamina is never inspected, and the trace's longest non-sprint span (t=5.0 to 9.0) reaches only ~80 at the nominal rate, so the cap boundary is never exercised | n/a | an uncapped stamina (or a cap of 1000) grades PASS; only the disclosed constants keep the difference invisible on this trace |
| 11 | a `DoSprintStart` at stamina below 30 is ignored | fully | below-floor gate (cp3, t=7.0; the fixture invoked `DoSprintStart` at t=6.2 with stamina 24) — `Expected the below-threshold sprint request to be ignored (no sprint, no deferred start); observed ratio ` | rows 1-8 (cp2 fans out first) | the floor VALUE is only bracketed, not pinned: any threshold in (24, 80] behaves identically across the trace (honored at 100 and ~80, ignored at 24) |
| 12 | an ignored request is not remembered — no auto-start when stamina later crosses 30 | fully | same cp3 token (t=7.0 sits after the t=6.5 floor-crossing; a latched auto-start is at full speed by ~6.7) + no-pending gate (cp4, t=9.0) — `Expected no sprint without a new request; observed ratio ` | cp3 passes first (an instant below-floor sprint dies there, owning the concept) | a latch whose deferred start fires later than t=9.0 (>2.5 s after the crossing) is masked by the legitimate cp4 request and grades PASS |
| 13 | sprinting works again after stamina has regenerated, on a fresh request | fully | re-sprint gate (cp5, t=10.5; fixture invoked `DoSprintStart` at t=9.0, stamina ~80) — `Expected sprint to work again after stamina regenerated; observed ratio ` | rows 1-12 fan out first | ratio-band latitude only ([1.55,1.85]) |
| 14 | correctness judged from measured GROUND speed while driven forward (no flight/teleport spoofing) | fully — per-checkpoint measurement-validity guard | falling guard — `the character left the runway (falling) - ground speed cannot be judged.` / validity guard — `the player character is no longer valid.` (speed = CharacterMovement 2D velocity, ratio-gated vs the same pawn's baseline; fixture drives input every frame; instants undisclosed) | evaluated at every checkpoint BEFORE its assertion | grounded velocity manipulation that reproduces the full 6-checkpoint envelope is mechanism latitude, not a cheat — behavior-only by design |
| 15 | implement in C++ in the existing gameplay module; do not edit the level, any config file, or any test file | edit bans fully, by the substrate model (not a fixture literal); the in-C++ clause itself is unasserted | sandbox — `Source/CraftBenchTests/` and `Content/Maps/` are deny prefixes in `AGENT_WRITABLE.json` (SANDBOX-REJECT exit 4); a `Config/*.ini` diff validates against the spec's `config_allow`, which this spec does not declare, so any ini change rejects; the graded substrate materializes from git HEAD, so on-disk fixture/map edits never reach the grade; L1 (UBT exit 0 for BOTH ThirdPersonEditor and ThirdPerson targets) enforces "compiles in the module" | unconditional (sandbox runs pre-grade; L1 gates L2) | a Blueprint implementation delivered under an `asset_writable` path (e.g. a character BP under `Content/Tasks/` plus a writable `SprintGameMode.cpp` retarget of `DefaultPawnClass`) would satisfy every behavioral gate while violating the in-C++ letter — no gate checks the implementation language |

Holes this table found (checklist §7 doctrine: escalate, do not paper over):

- **Row 4 — `DoSprintEnd` is resolved but never invoked.** The voluntary-stop
  half of the sprint contract is untested; a no-op body passes. Fix shape: an
  extra checkpoint pair (invoke `DoSprintEnd` mid-sprint, assert walk ratio one
  sample later) — the fixture already holds `SprintEndFn`.
- **Row 10 — the 100 cap is never exercised** (no regen span long enough, and
  stamina is never read). Accept as a documented residual or extend the
  schedule past a full regen.
- **Row 15 — "implement in C++" is not gated per se**; only the edit bans are.
  Likely acceptable under mechanism-agnostic basket law, but the prompt states
  it, so the gap is recorded here rather than silently.
