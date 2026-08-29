# Discrimination matrix — t2-gravity-floating-pawn-movement

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted checkpoint, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-gravity-floating-pawn-movement/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/CraftBenchTemplate/Tasks/t2-gravity-floating-pawn-movement/…`
  — the one correct solution (movement subclass + the constructor
  subobject-class override in the scaffold pawn).
- `<variant>/Source/CraftBenchTemplate/Tasks/t2-gravity-floating-pawn-movement/…`
  — one dir per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | checkpoint 1 (t=2.5s) | `the pawn does not sink while idle` | #1 / FR-017 |
| `sinks-while-driven/` | FAIL | checkpoint 2 (t=5.0s) | `the pawn sinks while movement is applied` | #2 unconditional gravity |
| `teleport-down-on-timer/` | FAIL | per-frame continuity guard (t≈0.75s, first timer step) | `altitude changed by a discontinuous jump` | #3 stepped teleport descent (coarse) |
| `small-step-timer-descent/` | FAIL | per-frame continuity guard (first velocity-gated 50uu step while running, t<=~0.6s) | `altitude changed by a discontinuous jump` | #3 stepped teleport descent (fine, velocity-gated) |
| `no-resume-after-input/` | FAIL | checkpoint 3 (t=6.5s) | `sinking does not resume after input ends` | #4 one-shot gravity latch |

Coverage note: both timer variants step at a band-plausible AVERAGE rate
(350uu/0.75s ≈ 467 uu/s and 50uu/0.1s = 500 uu/s — inside the disclosed
150-800 band), so the checkpoint-average band gate alone would credit them.
`small-step-timer-descent/` additionally velocity-gates its steps, so every
checkpoint-level gate (idle sink, driven hold, resume) reads correct — only
the continuity guard PAIR kills it, which is the property the variant exists
to prove: the per-frame cap (~30uu at the fixed 60Hz step) bounds single-step
amplitude, and the rolling-window cap (300uu per 0.25s) bounds burst rate. A
still-finer cheat (steps under ~30uu each, totalling under the window cap) is
ACCEPTED BY DESIGN — at that amplitude the descent is indistinguishable from
smooth in-band motion at this frame rate; the guards bound amplitude, they do
not forbid stepping metaphysically. The windowed guard's own substring
(`descent rate burst beyond the allowed band`), the band-ceiling assert
(`sinks faster than the required band`), and the lateral-progress assert
(`no lateral movement under input`) have no dedicated variants: the windowed
guard is defense-in-depth behind the per-frame cap, the band ceiling enforces
a disclosed prompt band (a too-fast solution is a spec miss, not a gaming
shape), and the lateral gate only fires for a pawn that ignores input
entirely — all three are argued from their named assertions rather than run
as separate submissions.

## How to run (deterministic verifier, no agent, no tokens)
The one-command form runs the whole matrix (reference → PASS, implicit empty →
FAIL, every variant → FAIL matched against its named substring):
```sh
cb discriminate --task cpp/t2-gravity-floating-pawn-movement          # committed task
cb discriminate --task cpp/t2-gravity-floating-pawn-movement --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH; UE root per this box's `.env` / `CB_UE_ROOT`):
```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t2-gravity-floating-pawn-movement/task.md \
    --submission tasks/cpp/t2-gravity-floating-pawn-movement/discrimination/sinks-while-driven \
    --ue-root "$CB_UE_ROOT" --substrate-from-live --workdir C:\cb\wd\gravpawn   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-30 (text half + adversarial review fixes same day).
- **EXECUTED 2026-07-30** (after the binary half landed):
  `cb discriminate --task cpp/t2-gravity-floating-pawn-movement --wip` =
  **discriminated: YES on the first attempt** — reference PASS; empty,
  sinks-while-driven, teleport-down-on-timer, small-step-timer-descent,
  no-resume-after-input all FAIL, each `[ok ]` (credited via its named
  substring). The reference PASS also proves AI-controller `AddMovementInput`
  consumption on `ADefaultPawn` (see ../notes.md calibration record).

# t2-gravity-floating-pawn-movement — Requirements table draft (checklist §7)

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in a FIXTURE-GATE row (rows 1–3, 5–11) is a contiguous
`FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t2-gravity-floating-pawn-movement/GravityFloatingPawnFunctionalTest.cpp`
(the task is `layers: [L1, L2]` — there is no L2I grader). Rows 4, 13 and 14
are substrate-model gates, not fixture gates: their backticked spans are
verbatim in the sources those rows name instead —
`tasks/cpp/t2-gravity-floating-pawn-movement/task.md` (the L1 assert block) and
`UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json` (the sandbox manifest).
The L1 target names themselves are runtime-COMPOSED by
`tools/verify-single/layers/l1_build.py` (`f"{game_module}Editor"` +
`game_module`, with `"Win64"` / `"Development"` as separate arguments), so
row 4 is marked (composed) and quotes task.md-side spans that do not cross
that block's line-wrap seam. The fixture ends at
the FIRST FinishTest, so every later gate is skipped once any earlier one fires
— including gate ORDER inside a single checkpoint (cp2 checks lateral progress
BEFORE driven sink); the continuity guard pair runs per simulated frame only
while the test is running and the pawn resolves.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed hovering pawn stays discoverable (implicit: "the level contains a hovering pawn") | fully | resolve gate (PrepareTest) — `Expected exactly one actor tagged 'HoverPawn' (the hovering pawn) in the running level; found ` | unconditional (first gate) | nothing at grade time; the tag lives on the placed instance in the deny-listed map — a BeginPlay-time duplicate fails here (the tag resolve runs exactly once in PrepareTest) and a runtime destroy fails at row 3 (weak pointer), but a duplicate tagged actor spawned AFTER PrepareTest (e.g. on a timer) is never rechecked by any gate |
| 2 | the tagged actor is actually a pawn (implicit: "the pawn") | fully | pawn-cast gate (PrepareTest) — `the tagged actor is not a pawn` | row 1 fired | class identity beyond APawn is free — the pawn is resolved by tag, never by class (but the graded instance stays the scaffold class regardless: level edits are deny-listed) |
| 3 | the pawn keeps existing for the whole run (implicit in every phase gate) | fully, at every checkpoint | liveness gate (GuardPawn) — `the hovering pawn is no longer valid (it must keep existing for the whole run).` | rows 1–2 (never resolved) | a destroy-and-respawn swap cannot pass (the fixture holds a weak pointer to the ORIGINAL instance); nothing else to get away with |
| 4 | "Change its movement" compiles: the edited module builds | fully | L1 layer (not a fixture gate; composed) — UBT must exit 0 for BOTH targets, `CraftBenchTemplateEditor Win64` `Development` and `CraftBenchTemplate Win64 Development` (task.md L1 assert block; target names composed by l1_build.py per preamble); L2 never runs after an L1 FAIL | unconditional (L2 requires L1) | nothing; warnings are free, only exit codes gate |
| 5 | idle descent happens: "the pawn must descend ... at a rate between 150 and 800 units per second" (floor) | fully for phase A | cp1 (t=2.5) floor — `the pawn does not sink while idle (dropped ` — phase-A drop (cp0→cp1, 2.0 s idle) must be >= 300 uu (= 150 uu/s x 2.0 s); the unmodified scaffold measures ~0 and dies here | any earlier FinishTest (rows 1–3, or a continuity trip before t=2.5) | the floor is averaged over the single phase-A window only; the resume phase (row 11) tolerates rates well below 150 uu/s (>= 0.3 x phase-A drop over 1.5 s, i.e. ~60 uu/s when phase A measured the 300 uu minimum) |
| 6 | idle descent rate cap: the 150–800 uu/s band (ceiling) | fully for phase A, run-wide as a burst cap | cp1 ceiling — `the pawn sinks faster than the required band (dropped ` (phase-A drop <= 1600 uu = 800 uu/s x 2.0 s); plus the run-wide rolling window — `a descent rate burst beyond the allowed band (` (> 300 uu lost in any 16-sample/0.25 s window = 1.5x the band ceiling) | ceiling: rows 1–5, or a continuity trip before t=2.5; window guard: needs 16 samples buffered, and stops with the run | outside phase A the AVERAGE ceiling is not re-checked — a phase-C descent sustained at up to ~1200 uu/s (1.5x band ceiling, under the window cap) passes |
| 7 | descent is smooth and steady — "no jumps or snaps" | fully, per frame for the whole run | continuity guard pair (Tick) — `altitude changed by a discontinuous jump (` (any single-frame \|dZ\| > 30 uu at the fixed 60 Hz step) + the rolling-window token of row 6 | pawn unresolved / test not running; needs a previous frame (`bHaveLastZ`) resp. a full 16-sample window | a stepped descent with every step < 30 uu/frame AND < 300 uu per rolling 0.25 s — accepted BY DESIGN (MATRIX coverage note): at that amplitude it is indistinguishable from smooth in-band motion at 60 Hz |
| 8 | "the descent should reach its steady rate within about half a second of going idle" | **NOT ASSERTED** | — no gate reads the ramp; cp0 (t=0.5) merely anchors Z0, and the phase gates check only phase-TOTAL drops | — | a descent that stays flat for up to ~1.6 s after going idle still passes phase A by then sinking near the band ceiling ((2.0 − delay) x 800 >= 300 ⇒ delay <= 1.625 s); the resume phase is even laxer (0.3 x phase-A drop over 1.5 s). The half-second ramp expectation is absorbed, never measured |
| 9 | driven: "hold its altitude ... must not lose height just because it is moving" | fully (ratio-gated) | cp2 (t=5.0) — `the pawn sinks while movement is applied (lost ` — Z loss across the 2.5 s driven phase must be <= 0.25 x the run's own phase-A drop | rows 1–6 (cp1 fan-out), row 10 fired first (inside cp2 the lateral-progress gate evaluates and FinishTests BEFORE this driven-sink gate), or a continuity trip mid-phase | up to 25% of the idle drop may still bleed off while driven (per-second: < 20% of the idle sink rate); CLIMBING while driven is entirely ungated (only loss is checked) |
| 10 | driven: "translate as it does today" | partially (floor only) | cp2 — `no lateral movement under input (progressed ` — X progress since cp1 must be >= 200 uu over 2.5 s of held +X input (stock movement yields ~2,800 uu) | rows 1–6, or a continuity trip mid-phase (between t=2.5 and t=5.0) | speed is barely constrained: ~80 uu/s (15x slower than stock 1200 uu/s MaxSpeed) passes; only the fixture-driven +X axis is exercised — Y behavior, turning, and "as it does today" fidelity are unmeasured |
| 11 | "When movement input stops, the descent must resume on its own" | fully (ratio-gated) | cp3 (t=6.5) — `sinking does not resume after input ends (dropped ` — 1.5 s post-input drop must be >= 0.3 x the phase-A drop | rows 1–10 (cp1/cp2 fan-out), or a continuity trip mid-phase | a permanently degraded resume rate (>= ~40% of the idle rate per second) passes; the test ends at cp3, so behavior after t=6.5 s (e.g. a delayed re-latch) is unobserved |
| 12 | "The change belongs to the pawn type itself — any instance of this pawn anywhere ... no per-instance setup" | **NOT ASSERTED** | — deliberately CUT per task.md: the constructor subobject-override idiom is the reference implementation, but no source-inspection lane exists (L5 defined-only) and only the ONE placed map instance is ever graded | — | logic keyed to the specific placed instance (actor label, world position, map name, a this-level-only BeginPlay branch) passes every gate; the structural backstop is only that level edits are deny-listed and a subclass/rename never reaches the grade (the placed instance stays the scaffold class), which forces the EDIT into the type but not its universality |
| 13 | "Implement in C++ in the existing gameplay module" | fully, by the substrate model | not a fixture gate — sandbox `writable` = `Source/CraftBenchTemplate/` (AGENT_WRITABLE.json; a source file anywhere else → SANDBOX-REJECT exit 4), and the graded instance is the scaffold C++ class, so a Blueprint-asset "solution" under an asset-writable path never affects the placed pawn; L1 (row 4) compiles the module | unconditional | nothing behavioral; file layout inside the module is free |
| 14 | "do not edit the level, any config file, or any test file" | fully, by the substrate model | not a fixture gate — `Content/Maps/` and `Config/` are on AGENT_WRITABLE.json's `deny` list and `Source/CraftBenchTests/` is sandbox-denied the same way (exit 4 pre-grade); the runner materializes the graded substrate from git HEAD, so an on-disk fixture edit never reaches the grade | unconditional | nothing |

Holes found (escalation list): rows 8 and 12 — the half-second ramp-to-steady-rate
expectation is never measured (only loosely bounded by the phase-A average floor),
and the type-level/no-per-instance-setup clause is graded purely by the one placed
instance's trajectory (the code-shape check was cut by explicit owner decision in
task.md, but a placed-instance-keyed solution passes undetected).
