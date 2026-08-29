# Discrimination matrix — t1-movement-component-drives-actor

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Every substring is a verbatim
contiguous span of ONE `FinishTest(EFunctionalTestResult::Failed, ...)` source
literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-movement-component-drives-actor/DriftFunctionalTest.cpp`,
never spanning a printf placeholder. Run:
`cb discriminate --task cpp/t1-movement-component-drives-actor [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.5s) MovingFromStart | `the actor has barely moved from its start` | #4 (no motion; the scaffold sits still and L1 passes) |
| `teleport-once-then-static/` | FAIL | cp3 (2.0s) ContinuesMoving | `the actor is no longer advancing` | #1 (one-shot teleport, timer-deferred to 0.35s so it lands after PrepareTest captures StartLocation) |
| `gravity-acceleration-ramp/` | FAIL | cp3 (2.0s) ConstantVelocity | `the drift is not constant-velocity` | #2 (gravity on + speed clamp removed; per-interval steps ~381/~621/~863 uu, ratio ~0.39 > 30% tolerance) |
| `spawns-tagged-proxy-mover/` | FAIL | PrepareTest (tag resolve) | `Expected exactly one actor tagged 'DriftRoot'` | robust-identity clause (wrong-actor gaming: a fresh proxy is tagged and driven while the placed actor stays still — two tagged actors resolve) |

Notes:
- **Gate order at cp3 matters.** The fixture checks ContinuesMoving (`d23 <=
  MoveMin`) BEFORE the equal-displacement pair, so a variant meant for the
  ConstantVelocity substring must keep advancing through the final interval
  (the gravity variant's d23 ~863 uu clears the 20 uu floor by 40x).
- **Anti-gaming note #3 (move-then-stop) is argued from the named assertion,
  not from a separate submission** — it dies at the SAME `d23 <= MoveMin`
  gate/literal as the one-shot teleport (`the actor is no longer advancing`),
  and duplicating a substring across rows would break disjointness. The
  teleport variant credits that gate; bounded coverage stated honestly: a stop
  landing inside roughly the final 0.15 s of the 2.0 s window (d23 >= ~70 uu
  and within 30% of the earlier ~100 uu steps) is invisible to both cp3
  checks — a boundary residual, not a variant-sized hole.
- **Anti-gaming note #5 (test disabling) is enforced by the substrate model,
  not a fixture gate**: `Source/CraftBenchTests/` is outside
  `AGENT_WRITABLE.json`'s writable set (sandbox exit 4) and the runner grades
  the verifier module from git HEAD. (The spec's "hash-pinned" wording is
  stale — the hash manifest retired 2026-07-16; provenance is git-HEAD +
  human review on commit now.) No submission row can probe it.
- **Timing assumption for the teleport variant**: checkpoints run on WORLD
  game-time and `PrepareTest` fires within the first frames of PIE (world
  t << 0.35 s), so `StartLocation` is pre-hop. If a pathological warmup ever
  ran `PrepareTest` after 0.35 s the leg would still FAIL, but at the
  MovingFromStart literal — a wrong-reason FAIL the discriminate run would
  correctly refuse to credit.
- **Substring disjointness:** the four failure literals open with distinct
  phrases (`barely moved from its start` / `no longer advancing` /
  `not constant-velocity` / `Expected exactly one actor tagged`); no row's
  substring appears inside any other row's expected failure output, and none
  spans a `%` placeholder.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. All four
  substrings above are pure ASCII.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`DriftFunctionalTest.cpp`; the gate name is the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the PLACED object is the thing that moves (one identifiable subject) | fully | resolve gate — `Expected exactly one actor tagged 'DriftRoot' in the test level; found ` | unconditional (first gate) | destroying the tagged actor and spawning exactly one replacement that carries the tag before PrepareTest would resolve as "the" actor — motion gates then judge the replacement |
| 2 | moves on its own from the moment play starts (no player input) | fully | MovingFromStart gate (cp0, t=0.5 s) — `the actor has barely moved from its start` | resolve gate failed | up to ~0.4 s of start latency (anything covering >20 uu by t=0.5 s); "no input" is enforced by construction — headless PIE injects none, so an input-dependent solution never moves and dies here |
| 3 | steady speed — equal distance in equal time, no accelerating | fully | ConstantVelocity gate (cp3) — `the drift is not constant-velocity` | resolve/cp0 failed, or ContinuesMoving fires first | drift-rate wobble under the disclosed 30% per-interval tolerance; a ramp gentle enough to stay under 30% across every adjacent pair |
| 4 | no stopping / no snapping (motion persists to the end) | partially | ContinuesMoving gate (cp3) — `the actor is no longer advancing` | resolve/cp0 failed | only the FINAL 0.5 s interval is floor-checked; a stop inside roughly the last 0.15 s (d23 >= ~70 uu, within 30% of prior steps) passes both cp3 checks |
| 5 | drifts in one HORIZONTAL direction | NOT ASSERTED | no gate — every check is `FVector::Dist` (scalar displacement); direction is never sampled | — | a vertical mover, a diagonal mover, or an equal-step zigzag all pass; the gravity variant fails for its acceleration, not its verticality |
| 6 | motion the same regardless of frame rate | NOT ASSERTED (single-rate run) | no gate — the leg runs once at `-deterministic -FPS=60`; the spec's "framerate-independent by construction" pins the CLOCK, it does not vary it | — | a fixed-uu-per-Tick mover (no DeltaTime scaling) is indistinguishable at the pinned 60 FPS; contrast the timer task's second -FPS=20 leg, which this task does not have |
| 7 | do not edit the level | fully, by the sandbox | not a fixture gate — `Content/Maps/` is deny-listed in `AGENT_WRITABLE.json` (exit 4) | unconditional | nothing |
| 8 | do not edit any test file | fully, by the substrate model | not a fixture gate — `Source/CraftBenchTests/` is outside the writable set and the runner grades it from git HEAD | unconditional | nothing |
| 9 | solve in C++ on the existing class | partially, by the sandbox | not a fixture gate — the writable set admits only `Source/CraftBenchTemplate/` (+ asset lanes); nothing pins the edit to DriftActor.{h,cpp} specifically | — | helper classes/files elsewhere in the writable module; mechanism is deliberately unconstrained (a DeltaTime-scaled Tick mover passes — behavior-only by basket law; "no per-frame scripting" appears in the task DESCRIPTION, not the agent prompt, and nothing gates it) |

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- ~~Authored 2026-08-16 from the spec + the shipped fixture. NOT YET EXECUTED.~~
  **SUPERSEDED by the EXECUTED line above — the package ran the same day it was
  authored and every leg was credited. Kept for provenance.**
