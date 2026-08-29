# Discrimination matrix — t1-physics-drop-and-rest

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Every substring below is a verbatim
contiguous span of a `FinishTest(EFunctionalTestResult::Failed, ...)` literal in
`Source/CraftBenchTests/Tasks/t1-physics-drop-and-rest/PhysicsDropFunctionalTest.cpp`.
Run:
`cb discriminate --task cpp/t1-physics-drop-and-rest [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.2s) | `Collision response to the Pawn channel must be Ignore` | nothing delivered — the scaffold's default `BlockAll` profile still blocks Pawn, so cp0's FIRST collision probe fires |
| `no-simulate-physics/` | FAIL | cp1 (1.5s) | `Is dynamic physics enabled?` | #1 (collision responses set, simulation never enabled — the cube never falls) |
| `ignores-world-static/` | FAIL | cp0 (0.2s) | `Collision response to the WorldStatic channel must be Block` | #3 (ignores EVERY channel to "not collide with the player"; would fall through the floor) |
| `fakes-fall-in-tick/` | FAIL | cp3 (3.5s) | `it should have come to rest` | #4 / #1 (skips the mechanism: constant-rate manual descent in Tick — descends past cp1's bar but never settles) |

Notes:
- **cp0 gate order** (single failure, first hit wins): primitive-root probe →
  Pawn response → WorldStatic response. The empty leg is caught by the Pawn
  probe because the untouched scaffold's default profile blocks Pawn;
  `ignores-world-static/` deliberately passes the Pawn probe (Ignore) so the
  WorldStatic probe is the one that fires.
- **cp3 gate order**: the rest check (`it should have come to rest`) runs
  BEFORE the below-the-floor check, so `fakes-fall-in-tick/` — which is both
  still-moving and (by then) through the floor — credits the rest gate
  deterministically.
- **The below-the-floor gate has no authored variant** (`it fell through
  instead of blocking on the floor`): any one-delta submission that would fall
  through the floor either reads WorldStatic != Block at cp0 (caught there) or
  fails to simulate at all (caught at cp1). The gate is argued from the named
  assertion as a runtime backstop; bounded coverage stated honestly.
- **Substring disjointness:** the four substrings are pairwise non-containing,
  and each leg's single failure message contains exactly its own row's
  substring — the Pawn and WorldStatic literals differ in channel name and
  required response, and the cp1/cp3 spans appear in no other literal.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. All four
  substrings above are pure ASCII.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`PhysicsDropFunctionalTest.cpp`; the gate name is the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed actor stays discoverable (identity by tag) | fully | resolve gate — `Expected exactly one actor tagged 'PhysicsDropRoot' in the test level; found ` | unconditional (first gate, in PrepareTest) | subclassing / renaming the class is free by design (tag lookup, never class) |
| 2 | the root stays a collidable primitive | fully | prim gate — `The host's root is not a primitive component with collision to configure.` | row 1 | re-rooting onto a DIFFERENT primitive passes — all probes then read the new root, which is the behavior-only intent |
| 3 | make it a dynamic physics object so it falls under gravity | fully (for the gravity half) | descend gate (cp1) — `Is dynamic physics enabled?` | rows 1–2 | any mechanism that descends >= 50 units by t=1.5s clears cp1 — the settle gate (row 6) is what catches the fake-fall class |
| 4 | ignores the player (Pawn) channel | structurally | pawn gate (cp0) — `Collision response to the Pawn channel must be Ignore` | rows 1–2 | the RESPONSE is read, not exercised: no pawn is ever walked through the cube, so a custom pawn object-channel trick is invisible |
| 5 | blocks static world geometry (WorldStatic) | structurally + behaviorally | worldstatic gate (cp0) — `Collision response to the WorldStatic channel must be Block`; runtime backstop: floor gate (cp3) — `it fell through instead of blocking on the floor` | rows 1–2 (cp0); rows 1–4 + rest gate fires first (cp3) | a response that reads Block while physics collision is off routes to cp1 instead — see the matrix note on the floor gate |
| 6 | comes to rest on the floor | fully | rest gate (cp3) — `it should have come to rest`; resting height floored by the cp3 floor gate | rows 1–5 fan out | up to 5 units of cp2->cp3 Z drift (disclosed tolerance); "on the floor" is any rest Z above 20 |
| 7 | reacts to forces (beyond gravity) | NOT ASSERTED | no gate applies an external force or impulse; gravity is the only force exercised | — | a body that falls and rests but is kinematic to impulses would pass; accepted residual, the graded concept is simulate + channel responses |
| 8 | keeps displaying a cube | NOT ASSERTED | no mesh/visibility gate in this fixture; removing the mesh incidentally kills the physics body and trips the descend gate, but a swapped or hidden mesh passes | — | mesh swap, hidden-in-game — accepted residual (visuals are t1-default-cube-mesh-actor's concept, not this task's) |
| 9 | solve in C++ on the existing class; no level edits; no test-file edits | fully, by the substrate model | not a fixture gate — the sandbox rejects paths outside `Source/CraftBenchTemplate/` (exit 4) and the verifier module + map grade from git HEAD | unconditional | nothing |
| 10 | L1: builds clean, no new shadowed-variable / deprecated warnings | conditionally | UBT exit 0 for both targets (generic L1); agent-file warnings are COUNTED (`l1_build.py::_count_warnings`) but gate only under the opt-in `--strict-warnings` flag (`registry.py`: `warning_count_agent_files > 0`) | `--strict-warnings` not passed (the default) | on a default run, any number of new warnings in the agent files — see concerns |

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- ~~Authored 2026-08-16 from the spec + the shipped fixture. NOT YET EXECUTED.~~
  **SUPERSEDED by the EXECUTED line above — the package ran the same day it was
  authored and every leg was credited. Kept for provenance.**
