# Discrimination matrix — t1-overlap-teleport-portal

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted checkpoint, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t1-overlap-teleport-portal/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/t1-overlap-teleport-portal/…` — the
  one correct solution (mirrors the writable path INCLUDING the per-task
  segment; ThirdPerson substrate — the agent-writable module is
  `Source/ThirdPerson/`).
- `<variant>/Source/ThirdPerson/Tasks/t1-overlap-teleport-portal/…` — one dir
  per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | checkpoint 1 (t=3.5s) | `never left the portal area - no teleport happened` | #1 / FR-017 |
| `teleport-without-contact/` | FAIL | checkpoint 0 (t=0.5s) | `already delivered before it had walked at all` | #2 teleport without contact |
| `delayed-unconditional-teleport/` | FAIL | continuous pre-contact guard (t≈1.0s, between cp0 and contact) | `delivered mid-approach without ever reaching the portal` | #2 teleport without contact (timed shape) |
| `hardcoded-destination/` | FAIL | checkpoint 1 (t=3.5s) | `delivered somewhere else than the marked destination` | #3 hardcoded landing coordinates |
| `resnap-after-exit/` | FAIL | checkpoint 2 (t=5.0s) | `no repeated snapping back` | #4 sticky teleport |

Coverage note: the cp1 failure message is BRANCHED on the walker's position,
so the empty leg (never relocated — brakes ~70uu past the portal plane,
~1,450uu from the moved marker) and `hardcoded-destination/` (relocated to
the memorized authored spot, ~1,900uu from the moved marker and ~2,000uu from
the portal) carry DISTINCT credited substrings. `teleport-without-contact/`
(tick-driven) dies at the instant cp0 sample; `delayed-unconditional-teleport/`
(1.0s timer, no overlap logic) is green at cp0 and is killed by the CONTINUOUS
pre-contact guard in the fixture Tick. Those two gates carried the SAME
literal until the 2026-08-17 message-only split (below), so no row could
say which of them fired; each now names its own reason. Residual guard
granularity: a timed cheat landing inside the
~3-frame contact zone just before real contact would pass; the window is
~50ms wide, undisclosed, and geometry-dependent (see ../notes.md). A
BeginPlay-cached marker position (cache-at-start instead of read-at-teleport)
dies at the same gate as `hardcoded-destination/`, since the fixture moves the
marker after placed-actor BeginPlay — argued from the named assertion rather
than run as a separate submission.

**Message-only split (2026-08-17)** — closes the `fixture-fail-unique`
finding "2 gates share the FAIL literal 'Expected the walker character to be
far from the'". The two pre-contact gates in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp`
printed byte-identical text, so the `teleport-without-contact/` and
`delayed-unconditional-teleport/` rows were credited by the same grep and the
matrix proved a count, not a discrimination. What changed:

- cp0 (`OnCheckpoint` case 0, t=0.5s) now prints `Expected the walker
  character to be away from the marked destination at the first sample;
  observed it already delivered before it had walked at all (distance ` — the
  walker was at the destination on the FIRST sample, before `bDriving` was
  ever set, i.e. before it had walked a step.
- the continuous per-frame guard (fixture `Tick`, armed from cp0 until
  delivery) now prints `Expected the walker character to reach the portal
  before any delivery; observed it delivered mid-approach without ever
  reaching the portal (distance ` — delivery observed while the walked-X
  progress is still short of the contact zone.

**MESSAGE STRINGS ONLY.** Every predicate (`Distance < KFreeMinDistance`,
`MaxApproachX < PortalSpot.X - KContactZoneX`), the gate ORDER, and every
verdict are byte-identical to the pre-split fixture, so the set of
submissions that fail — and the gate each one dies at — is unchanged; only
the text a MATRIX row can grep for is different. Control flow, traced from
the checkpoint entry so neither literal is dead code: `bDriving` is false
until cp0's non-failing path sets it, so before t=0.5s the Tick guard cannot
run at all and an every-tick snap (`teleport-without-contact/`) can only
reach cp0's literal; a 1.0s-timer snap
(`delayed-unconditional-teleport/`) is >=250uu from the destination at cp0,
passes it, arms the drive, and is then caught by the guard at t~1.0s with
~300uu of walked progress against the 740uu approach — the only leg that
reaches the guard's literal. The other three legs never enter either gate:
`hardcoded-destination/` lands ~1,900uu from the moved marker (the guard's
distance test is false), `resnap-after-exit/` is delivered only after real
contact (the guard's contact test is false, so it just stops the drive), and
the empty leg is never relocated. The four credited variant substrings are
pairwise non-containing, and none of them appears in the empty leg's log.
The next `cb discriminate --task cpp/t1-overlap-teleport-portal` is what
re-validates the two NEW substrings against real logs; until it runs, this
split is argued from the source, not measured.

## How to run (deterministic verifier, no agent, no tokens)
The one-command form runs the whole matrix (reference → PASS, implicit empty →
FAIL, every variant → FAIL matched against its named substring):
```sh
cb discriminate --task cpp/t1-overlap-teleport-portal          # committed task
cb discriminate --task cpp/t1-overlap-teleport-portal --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH; UE root per this box's `.env` / `CB_UE_ROOT`):
```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t1-overlap-teleport-portal/task.md \
    --submission tasks/cpp/t1-overlap-teleport-portal/discrimination/resnap-after-exit \
    --ue-root "$CB_UE_ROOT" --substrate-from-live --workdir C:\cb\wd\tpport   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-29 from the spec + the fixture source.
- **EXECUTED 2026-07-29** (same date, after the binary half landed):
  `cb discriminate --task cpp/t1-overlap-teleport-portal --wip` =
  **discriminated: YES** — reference PASS; empty,
  delayed-unconditional-teleport, hardcoded-destination, resnap-after-exit,
  teleport-without-contact all FAIL, each `[ok ]` (credited via its named
  substring). The reference PASS also confirms the load-bearing possession
  assumption (AI-controller `AddMovementInput` drive) — see
  `../notes.md` calibration record.
- **Message-only split 2026-08-17** (see above): the two pre-contact FAIL
  literals were separated and this file's two credited substrings updated to
  match. No predicate changed, so the recorded 2026-07-29 discrimination
  result still holds for WHICH leg fails WHERE; the two new substrings are
  re-validated by the next `cb discriminate` run.

# Requirements table draft — cpp/t1-overlap-teleport-portal

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 span in the **Enforcing gate column** is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp`
(none spans a printf placeholder; ASCII-only per the cp1252 log read-back rule); row 9's backticked identifiers
(`ACharacter`, `SpawnDefaultController()`) are fixture-verbatim CODE spans (cpp:124-125, 131), not FinishTest literals.
Row 8's walker-validity guard runs at the ENTRY of every checkpoint (`GuardWalker`, cpp:217) before any distance gate,
so its firing additionally skips every checkpoint gate below (rows 3, 4, 6, 7) — the per-row skip cells list only their
same-family predecessors; the authoritative gate order is the source. The task wires `layers: [L1, L2]`
only — there is no `introspect:` key, so no L2I gate family exists; structural rows cite the sandbox
(`UE-projects/ThirdPerson/AGENT_WRITABLE.json` via `tools/verify-single/sandbox.py`, exit 4) and the L1 UBT gate.
Row 10 is **(composed)**: the L1 target names are runtime-composed in `tools/verify-single/layers/l1_build.py`
(line 273, `targets = (f"{game_module}Editor", game_module)`) from the manifest's `"game_module": "ThirdPerson"`
value — the row quotes those source-side fragments, never the emitted names (task.md's L1 block line-wraps them,
so the emitted strings are contiguous nowhere in source). Row 11's scaffold-class token cites the scaffold header
it is declared in, alongside the fixture.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed portal frame stays discoverable in the running level | fully | portal resolve gate — `Expected exactly one actor tagged 'TeleportPortal' (the portal frame) in the running level; found ` | L1 FAIL (L2 never runs); otherwise unconditional (first L2 gate) | subclassing/renaming the actor is free (the ctor-stamped tag inherits; identity is by tag, never by class); the resolve runs exactly ONCE, in PrepareTest — a duplicate tagged actor that exists by then (placed, or spawned during placed-actor BeginPlay, which precedes PrepareTest) fails here, but a destroy of the portal or a second tagged spawn AFTER PrepareTest (timer/first-Tick) is never rechecked by any gate |
| 2 | the destination marker stays discoverable, elsewhere in the level | fully | marker resolve gate — `Expected exactly one actor tagged 'TeleportDestination' (the destination marker) in the running level; found ` | row 1 | the marker "should not gain any code" clause is UNGATED as behavior — added code on the marker is tolerated so long as exactly one tagged, movable instance survives (a marker whose root is made immovable dies at the HARNESS-PRECONDITION relocate check, not a graded gate) |
| 3 | a character that walks into the portal is relocated to the destination | fully | cp1 delivered gate (t=3.5 s; fixture-driven contact at ~1.9 s; 3D distance to the fixture-chosen marker spot must be <= 150 uu) — no-teleport branch literal `observed it never left the portal area - no teleport happened (distance to destination ` | rows 1-2, or an earlier FinishTest (cp0 / the continuous guard) already ended the run | the relocation mechanism is free (SetActorLocation, TeleportTo, physics warp); landing up to 150 uu off the marker still grades delivered |
| 4 | delivery targets wherever the marker CURRENTLY is — read at the moment of the teleport, not remembered from level start (the marker can be moved) | partially | cp1 wrong-place branch — `observed it delivered somewhere else than the marked destination (distance ` — armed by PrepareTest MOVING the marker to an undisclosed fixture-chosen spot (~1,900 uu from the authored placement) AFTER placed-actor BeginPlay, so authored-coordinate constants AND BeginPlay-time caches both miss by ~1,900 uu | rows 1-3 fan out first; the no-teleport branch (walker still within 600 uu of the portal) owns the failure instead when nothing relocated at all | the fixture moves the marker exactly ONCE, before play — a one-time cache taken any time after PrepareTest (e.g. on the portal's first Tick) reads the moved spot and grades identically to a true read-at-teleport-time solution |
| 5 | the relocation is INSTANT | **NOT ASSERTED** | none — cp1 samples only the END state at t=3.5 s; no gate measures transit. The continuous per-frame guard treats ANY arrival at the destination after real contact as legitimate delivery (it just stops the drive and lets cp1 grade) | — | a smooth glide/lerp from portal to destination completing within the ~1.6 s post-contact settle window grades identically to an instant teleport |
| 6 | a character must never be relocated before it touches the portal | fully | cp0 sample (t=0.5 s, distance to destination must be >= 250 uu) PLUS a CONTINUOUS per-frame guard across the whole approach (delivery observed while walked X progress — advanced only on un-delivered frames — is still short of the portal's contact zone, box extent + capsule radius + ~5 frames = 140 uu) — two literals since the 2026-08-17 message-only split — cp0 prints `already delivered before it had walked at all (distance `, the continuous guard prints `delivered mid-approach without ever reaching the portal (distance ` | rows 1-2; the guard is armed only from cp0 until delivery (while the fixture is driving) | (a) a timed cheat landing inside the ~3-frame (~50 ms) contact zone just before real contact — window undisclosed and geometry-dependent; (b) a pre-contact relocation to anywhere OTHER than the destination is invisible (only delivery-shaped relocations trip the guard) |
| 7 | once delivered the character is free: moving away must not pull or snap it back | fully | cp2 gate (t=5.0 s; fixture relocated the walker 400 uu away at cp1, distance must be >= 250 uu again) — `stay free after leaving the destination (no repeated snapping back); observed distance ` | rows 1-4 (cp1 must have graded delivered) | a re-pin that first fires after t=5.0 s (e.g. a >1.5 s-period snap-back timer) is unobserved; re-teleporting a character that genuinely re-enters the portal is fine (the fixture's walk-out never re-enters) |
| 8 | the SAME character is relocated — not destroyed and replaced by a copy | fully | walker-validity guard, run at every checkpoint before any distance gate — `the walker character is no longer valid (it must be relocated, never destroyed).` | rows 1-2 (guard exists only once the walker is spawned) | destroy-at-portal + spawn-a-clone-at-destination fails at the first checkpoint after the destroy; nothing survives this gate |
| 9 | works for A character generally — one the agent's code has never seen (no class/possession/PlayerStart assumptions) | fully (implicit) | the walker is a fixture-owned plain engine `ACharacter` spawned in PrepareTest with `SpawnDefaultController()`; class-filtered logic (e.g. keyed to the ThirdPerson template character) never fires and dies at cp1 via the no-teleport branch (row 3 literal) | rows 1-2 | logic keyed to `ACharacter` (rather than APawn/any actor) passes — a non-Character pawn walking in is never tested; multi-entrant behavior is never tested (one walker only) |
| 10 | the change compiles (implicit in "implement in C++") | fully | L1 build gate (composed) — UnrealBuildTool must exit 0 for BOTH targets, composed in `tools/verify-single/layers/l1_build.py` as `f"{game_module}Editor", game_module` (line 273) from the manifest's `"game_module": "ThirdPerson"` (`AGENT_WRITABLE.json`) — i.e. ThirdPersonEditor and ThirdPerson, Win64 Development (short-circuits on first failure; L2 never runs after an L1 FAIL) | unconditional (first gate of the run) | warnings are free; only a hard build failure gates |
| 11 | implement in C++ in the existing gameplay module | fully (structural) | sandbox path allowlist — the ThirdPerson `AGENT_WRITABLE.json` writable list is `Source/ThirdPerson/` plus `Content/Tasks/` (the latter path-accepts any file type, but a file there never compiles into the module, so the C++ clause reduces to `Source/ThirdPerson/`); any file outside the writable/asset prefixes is SANDBOX-REJECT exit 4 before grading. Reachability closes the C++ clause: the map places the C++ portal scaffold `ATeleportPortalActor` (declared in the scaffold `Source/ThirdPerson/Tasks/t1-overlap-teleport-portal/TeleportPortalActor.h`) and the map/config are un-editable, so a pure-asset (Blueprint) deliverable never executes in the graded level | unconditional (pre-grade) | any file layout, new helper classes, or a subclass inside `Source/ThirdPerson/` — all free (both graded identically per the spec) |
| 12 | do not edit the level, any config file, or any test file | fully (structural) | sandbox reject, three mechanisms in the ThirdPerson `AGENT_WRITABLE.json`: (a) DENY — `Content/Maps/` and `Source/CraftBenchTests/` are deny entries (deny wins; rejected pre-grade, exit 4); (b) semantic config lane, NOT a deny (the broad Config/ deny was removed 2026-07-29) — only the two `config_writable` files (`Config/DefaultEngine.ini`, `Config/DefaultInput.ini`) are path-accepted, then their ini diff is validated against the spec's `config_allow` allowlist (`tools/verify-single/config_lane.py`), and THIS spec declares no `config_allow`, so any diff to them rejects; (c) every other Config/ file rejects by allowlist-miss. Plus: the runner materializes the graded substrate from git HEAD, so an on-disk fixture/map edit never reaches the grade, and committed changes are review-gated on commit | unconditional (pre-grade) | nothing |

### Escalation notes (holes this table found)

- **Row 5 is the one NOT ASSERTED row**: "instantly" is enforced only as
  delivered-by-t=3.5 s (~1.6 s of post-contact latitude). A smooth interpolated
  transit passes every gate. If instantaneity is meant to gate, cp1 needs a
  companion single-tick displacement check (the door-hitch continuity-gate
  shape); otherwise the prompt word should be treated as flavor.
- **Row 4 partial**: the marker moves exactly once, pre-play — the gate proves
  "not remembered from LEVEL START" (the prompt's literal words) but cannot
  distinguish read-at-teleport-time from a first-tick cache. A second in-play
  marker move between contact windows would close it, at the cost of a second
  delivery leg.
- **Row 6 residuals** (documented in `../notes.md` / the matrix coverage note):
  the ~3-frame contact-zone window, and pre-contact relocations to
  non-destination locations being invisible.
- **Row 7 residual**: re-snapping that first fires after the t=5.0 s final
  checkpoint is unobserved.
