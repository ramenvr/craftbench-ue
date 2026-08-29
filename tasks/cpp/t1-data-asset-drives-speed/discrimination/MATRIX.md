# Discrimination matrix — t1-data-asset-drives-speed

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t1-data-asset-drives-speed [--wip]`.

Every substring below is a verbatim contiguous span of ONE
`FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-data-asset-drives-speed/ProfiledMoverFunctionalTest.cpp`,
never spanning a printf placeholder — so each span is STATIC text guaranteed
present in EVERY firing of its gate's literal.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.5s) | `it should be cruising at the profile's CruiseSpeed` | #2 (nothing delivered; the scaffold is tagged but motionless). GATE-level credit; see the shared-literal note. |
| `hardcoded-speed/` | FAIL | cp2 (1.5s) rate gate | `a wrong speed means the value did not come from the profile` | #1 / #4 (moves confidently at 300 uu/s, a number written in code; 173 +/-12% rejects it). GATE-level credit; see the shared-literal note. |
| `one-shot-teleport/` | FAIL | cp2 (1.5s) rate gate | `A near-zero speed means the profile was never read` | #3 (v2 "teleport burst": 30 uu tick-steps confined to world t<0.42s clear cp0's 20 uu floor, then static — both later 0.5s intervals measure ~0 uu/s). GATE-level credit; see the shared-literal note. |
| `applies-too-late/` | FAIL | cp0 (0.5s) | `the actor has barely moved (` | #2 boundary (reads the profile CORRECTLY but only starts moving at t=0.9s — probes that "when gameplay begins" is a real gate, not just "eventually"). GATE-level credit; see the shared-literal note. |

Notes:
- **The fixture has FOUR `EFunctionalTestResult::Failed` literals** (an earlier
  draft of this file said three — corrected): the resolve gate (line 53), the
  host-gone re-check `Host actor went missing during the test.` (line 67, fired
  defensively at every checkpoint), the cp0 movement gate (line 81), and the
  cp2 rate gate (lines 101-103). No row substring intersects the host-gone
  literal, and it has no authored variant: an agent submission cannot plausibly
  null the fixture's resolved host pointer without also failing every motion
  gate. The disjointness analysis below is built on the full four-literal set.
- **SHARED-LITERAL HONESTY — crediting is GATE-level, not reason-level, for
  both variant pairs.** The cp0 literal serves both `empty` and
  `applies-too-late`, and the cp2 literal carries BOTH sub-reasons (near-zero
  and wrong-speed) in one printf serving `one-shot-teleport` and
  `hardcoded-speed`. Within a pair, disjoint substrings are structurally
  unattainable: each row's span is static text of the shared literal and so is
  GUARANTEED to appear in the sibling leg's failure output too. The rows'
  spans are therefore chosen only to be pairwise non-containing and
  cross-GATE disjoint (a cp0 span never appears in a cp2 failure or the
  resolve/host-gone literals, and vice versa — note the cp2 message's
  `(the profile's CruiseSpeed, +/-` fragment does NOT contain the empty row's
  longer `it should be cruising at ...` span). What a row's grep certifies is
  "failed at the expected GATE"; reason-level separation within a gate awaits
  the fixture literal split proposed below (a review-gated
  `Source/CraftBenchTests/` change, not done here).
- **Variant value at cp0 (`empty` vs `applies-too-late`)**: both legs are
  motionless through t=0.5s, so their failure lines are BYTE-IDENTICAL
  (`At t=0.50s the actor has barely moved (0.0 uu); ...`) — no substring can
  ever separate them, and no literal split can either (the fixture observes
  the identical physical state). Both rows are kept because each proves a
  DIFFERENT plausible-wrong submission fails — nothing-delivered vs
  read-the-profile-correctly-but-applied-late — i.e., the discrimination
  between them is VERDICT-level (each must FAIL, at the cp0 gate), not
  message-level.
- **Variant value at cp2 (`hardcoded-speed` vs `one-shot-teleport`)**: the
  shared literal's static text is identical in both outputs, but the `%.1f`
  measured-speed payload differs (~300.0 vs ~0.0), so the full lines are not
  byte-identical; each proves a different plausible-wrong submission
  (confident wrong constant vs impulse-then-static) fails at the rate gate.
- **One-shot-teleport v2 — the timing race is closed, not assumed away.** The
  v1 leg snapped once via a 0.25s BeginPlay timer and ASSUMED `PrepareTest`
  (which captures `StartLocation`) completes within 0.25s of world start; if
  it did not, the snap landed before capture and the leg mis-failed at cp0
  with the wrong substring. v2 instead teleports 30 uu per tick while world
  game-time < 0.42s, then never again. A single step clears cp0's 20 uu
  floor, so cp0 passes whenever ONE tick lands between capture and t=0.42s —
  a strictly WEAKER timing requirement than the reference PASS leg's own
  (the reference needs capture by ~t=0.384s to accumulate >20 uu at 173 uu/s
  by t=0.5s, and at -FPS=60 two whole frames still step between 0.384s and
  0.42s). If this leg ever mis-fails at cp0, the reference leg has already
  failed the package. The residual (a real run confirming cp2 attribution) is
  an execution-time check in Status.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. All
  substrings above are ASCII-only (the fixture uses `+/-`, not the sign).
- The resolve gate (`Expected exactly one actor tagged 'ProfiledMoverRoot'
  in the test level; found `) has no authored variant: the tag is stamped in
  the scaffold constructor and every plausible submission keeps it; the gate
  is argued from the named assertion (requirements row 8 below).

## Fixture literal-split recommendation

Reason-level crediting at the cp2 gate needs the composite literal split into
a sentinel (near-zero) branch and a wrong-value branch. Exact change to
`ProfiledMoverFunctionalTest.cpp` (review-gated: `Source/CraftBenchTests/` is
review-gated on commit and graded from git HEAD — proposed here, NOT applied):

Before (lines 96-105):

```cpp
		if (MeasuredSpeed < LowerBound || MeasuredSpeed > UpperBound)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the measured cruise speed was %.1f uu/s, expected ~%.1f (the profile's CruiseSpeed, +/-%.0f%%). ")
					TEXT("A near-zero speed means the profile was never read/applied; a wrong speed means the value did not come from the profile."),
					TimeSeconds, MeasuredSpeed, ExpectedCruiseSpeed, RateTolPct * 100.0));
			return;
		}
```

After (two literals; `MoveMin / SampleInterval` = 40 uu/s reuses the fixture's
own "counts as moving" floor as the near-zero threshold):

```cpp
		if (MeasuredSpeed < MoveMin / SampleInterval)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the measured cruise speed was %.1f uu/s -- near zero: the profile was never read/applied after the first checkpoint."),
					TimeSeconds, MeasuredSpeed));
			return;
		}
		if (MeasuredSpeed < LowerBound || MeasuredSpeed > UpperBound)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the measured cruise speed was %.1f uu/s, expected ~%.1f (the profile's CruiseSpeed, +/-%.0f%%); the value did not come from the profile."),
					TimeSeconds, MeasuredSpeed, ExpectedCruiseSpeed, RateTolPct * 100.0));
			return;
		}
```

Both replacement messages are ASCII-only, and the natural row spans —
`near zero: the profile was never read` vs
`the value did not come from the profile` — are mutually non-appearing and
absent from every other literal in the fixture. Once merged, retarget the two
cp2 rows to those spans and drop their GATE-level caveat. The cp0 literal is
deliberately NOT split: its two legs present the identical physical state
(0.0 uu moved), so no message can separate them (see the variant-value note).

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`ProfiledMoverFunctionalTest.cpp`; the gate name is the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | reads the configured speed from the content and moves at it | fully, at the authored value | cp2 rate gate — `the measured cruise speed was ` (keyed to the undisclosed non-round 173.0, +/-12%) | host unresolvable (row 8) or cp0 fired first | a hardcoded number inside [152.2, 193.8] — a blind guess at an undisclosed non-round value (accepted residual, note #1) |
| 2 | moves when gameplay begins (moving by the first observation) | fully | cp0 gate — `the actor has barely moved (` (>20 uu by t=0.5s) | row 8 | any start inside the first ~0.4s; a start between 0.5s and never is caught here |
| 3 | moves CONTINUOUSLY (no one-shot snap) | fully for snap-then-static | cp2 rate gate — `A near-zero speed means the profile was never read` (rate averaged over two later 0.5s intervals) | rows 2, 8 | a non-uniform pattern whose two-interval AVERAGE lands in the +/-12% band (e.g. stutter-stepping around 173 uu/s) |
| 4 | equal distance in equal time (constant rate) | partially | same cp2 gate (two-interval average) | rows 2, 8 | the average hides per-interval variance; each interval is not gated separately |
| 5 | moves FORWARD (the actor's forward direction) | NOT ASSERTED | — no gate measures direction: the fixture uses `FVector::Dist` between samples, which is direction-agnostic | — | moving backward, sideways, or straight up at ~173 uu/s passes every gate |
| 6 | retuning the content changes the motion (the read is live) | NOT ASSERTED directly | — single-point test at the one authored value; no second-profile leg exists | — | code that reads the profile once then clamps/quantizes near 173 is indistinguishable; the single undisclosed non-round value is the whole defense |
| 7 | requires no player input | asserted by environment | headless PIE injects no input; the motion gates (rows 1-3) require motion regardless | — | nothing — input-dependent motion cannot pass cp0 headless |
| 8 | the placed actor stays discoverable (exactly one tagged root) | fully | resolve gate — `Expected exactly one actor tagged 'ProfiledMoverRoot' in the test level; found ` | unconditional (first gate) | mechanism freedom: subclassing, extra components, a helper that moves the placed instance — all pass (by design; identity is by tag) |
| 9 | do not edit the content asset (`Content/Data/DA_MovementProfile`) | fully, by the substrate model | not a gate — `Content/Data/` is outside `writable`/`asset_writable` in `AGENT_WRITABLE.json`; the submission is sandbox-rejected (exit 4) | unconditional | nothing |
| 10 | do not edit any test file | fully, by the substrate model | not a gate — `Source/CraftBenchTests/` is deny-listed and the runner materializes it from git HEAD | unconditional | nothing |
| 11 | solve in C++ on the existing class | partially, by the substrate model | sandbox confines source edits to `Source/CraftBenchTemplate/`; "the existing class" itself is not enforced | — | new classes/subclasses in the writable module that end up moving the placed tagged instance (tolerated — the scaffold header explicitly permits subclassing) |
| 12 | no new shadowed-variable / deprecated-declarations warnings (spec L1 assert) | conditionally | L1 counts warnings in agent files, but gates them only under `--strict-warnings` — not on the default discriminate/refgate path | strict-warnings not passed (the default) | new warnings on a default run |

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- Authored 2026-08-16 from the spec + the shipped fixture. Revised 2026-08-16
  after adversarial verify: literal count corrected (3 → 4), GATE-level
  crediting made explicit for both shared-literal pairs, cp2 literal-split
  recommendation added, one-shot-teleport hardened to the v2 tick burst, and
  all variant sources re-emitted CRLF to byte-match the reference outside the
  one delta.
- ~~NOT YET EXECUTED — validation queued behind the reference sweep.~~ [SUPERSEDED: it RAN the same day, every leg credited — see the EXECUTED line above.]
  Execution-time checks to run with it:
  1. `one-shot-teleport` must FAIL with the cp2 literal present and the cp0
     literal ABSENT from its log — the observable proof that the burst landed
     after `StartLocation` capture (the analytic bound above is argument, not
     evidence, until a real run).
  2. `applies-too-late` must FAIL with the cp0 literal present and the cp2
     literal absent (its 0.9s BeginPlay timer must not slip inside the 0.5s
     window).
  3. Reference PASS and empty FAIL legs ride the automatic
     `cb discriminate` pair as usual.
