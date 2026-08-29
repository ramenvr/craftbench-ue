# Discrimination matrix — t0-sanity-log-on-beginplay

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t0-sanity-log-on-beginplay [--wip]`.

The fixture (`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t0-sanity-log-on-beginplay/SanityFunctionalTest.cpp`)
carries two agent-creditable `FinishTest(EFunctionalTestResult::Failed, ...)`
gates: the tag-resolve gate in `PrepareTest` and the emission-count gate in
`OnCheckpoint`. Since the message-only literal split (DONE 2026-08-16) the
count gate prints ONE distinct literal per failure reason: a zero branch
(`observed none.`), an over-count branch (`observed %d (more than one).`),
and a listener-fault sentinel branch (verifier-side fault, still `Failed` so
every verdict stays byte-identical; never credited by any row).
(`PrepareTest: no UWorld available` is an `Error`-class
machine-fault message and is never credited by any row.)

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.1s) | `in the BeginPlay window; observed none.` | #1 (no BeginPlay override at all; runtime count 0). Reason-level credit via the zero-branch literal (split DONE 2026-08-16). Failure output is byte-identical to `wrong-category-log/`; kept because this leg proves the MANDATORY no-op submission fails (verdict-level discrimination). |
| `wrong-category-log/` | FAIL | cp0 (0.1s) | `in the BeginPlay window; observed none.` | #2 (custom category instead of LogTemp; the listener's category filter never counts it; runtime count 0). Reason-level credit via the zero-branch literal — count 0 is ONE reason, so this leg shares `empty`'s substring by nature (the empty leg is exempt from pairwise disjointness by design). Failure output is byte-identical to `empty`; kept because it proves a DIFFERENT plausible-wrong submission — one that DOES emit the literal, on the wrong channel — also fails (verdict-level discrimination). |
| `tick-repeat-emit/` | FAIL | cp0 (0.1s) | `(more than one)` | #4 (per-frame emission; the `== 1` assert sees >= 2 by the 0.1s checkpoint). Reason-level credit via the over-count branch literal (split DONE 2026-08-16); the exact count still sits in the fixture's `%d` placeholder, so N >= 2 stays an execution-time check in Status. |
| `logs-then-destroys-self/` | FAIL | PrepareTest (tag resolve) | `actor tagged 'SanityRoot' in the test level; found` | prompt clause "the actor should otherwise remain in the world" — Destroy() in BeginPlay leaves 0 tagged actors when PrepareTest resolves |

Notes:
- **Fixture literal split — DONE 2026-08-16 (awaiting the sweep):** the
  emission-count gate now prints a distinct ASCII literal per failure reason
  (zero / more-than-one / listener-fault sentinel), so `empty` and
  `wrong-category-log/` credit the zero branch's `observed none.` while
  `tick-repeat-emit/` credits the over-count branch's `(more than one)` —
  reason-level, pairwise non-containing, independent of the runtime `%d`.
  The split is MESSAGE-ONLY per the Q8 contract line (a split that only
  changes the message is safe; a split that moves any verdict replaces the
  task): the pass predicate, gate order, and every verdict are byte-identical,
  which is why the drafted re-route of the `-1` listener-fault sentinel to
  the `Error` channel was deliberately NOT applied — the sentinel keeps the
  `Failed` verdict with its own distinct literal naming the verifier-side
  fault (no row credits it; investigate, never credit). What the split still
  cannot do: separate `empty` from `wrong-category-log/` (both are count 0 at
  the same gate — invisible-to-the-listener is one reason, not two); that
  pair's separation stays verdict-level per the note below, permanently.
  Fake disjointness via distinct spans of one literal remains REMOVED — the
  per-reason literals now make the credited spans genuinely disjoint.
- **Verdict-level value of the byte-identical pair:** `empty` and
  `wrong-category-log/` produce byte-identical failure output (both count 0);
  no substring can ever separate them. Both rows stay because each proves a
  DIFFERENT plausible-wrong submission fails: `empty` is the mandatory no-op
  FAIL leg, while `wrong-category-log/` proves an agent that genuinely emits
  the literal — but on a self-defined category — is still caught by the
  listener's category filter. That is discrimination at the VERDICT level,
  not the message level.
- Anti-gaming note #3 (constructor-time log) is argued from the named
  assertion rather than a separate submission: a constructor emission fires
  during map load, before the fixture installs its GLog device in
  `OnWorldInitializedActors`, so its signature is byte-identical to
  `wrong-category-log/` (count 0 at the gate) — a second variant at the
  identical point adds no information.
- Anti-gaming note #5 (test tampering) is not a variant: edits under
  `Source/CraftBenchTests/` are sandbox-rejected (exit 4) before any layer
  runs, and the runner grades the verifier module from git HEAD regardless.
- **Substring disjointness across GATES:** the tag-gate substring
  (`actor tagged 'SanityRoot' in the test level; found`) shares no
  load-bearing span with any count-gate literal, so the
  `logs-then-destroys-self/` row is reason-level on its own. Within the
  count gate the zero-branch and over-count substrings are disjoint since
  the 2026-08-16 split; only `empty`/`wrong-category-log/` still share one
  substring, per the split note above.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. All
  fixture literals (tag gate + the three split count-gate branches) and
  every credited substring above are pure ASCII.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal span in
`SanityFunctionalTest.cpp`; the gate name is the durable join key. (The spans
here IDENTIFY the enforcing gate for audit — they are not per-reason credited
substrings; crediting is defined by the matrix rows above.)

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | emits the exact log line `CRAFTBENCH_SANITY_OK` | **fully** (closed 2026-08-19) | `Expected the exact log line 'CRAFTBENCH_SANITY_OK'; the one LogTemp/Display emission in the BeginPlay window merely CONTAINS it:` — the failing line is quoted verbatim in the message | count gate fires first (a decorated line is still ONE match, so this is reached exactly when count == 1) | the count gate matches by CONTAINS and always will — that is what makes "exactly once" robust. Exactness is now a SECOND observation made at emission time (`FSanitySubstringCounterDevice::ExactMatchCount`, trimmed case-sensitive equality), because by the time the checkpoint reads a count, WHICH line it was is gone. No leg probes it; the reference PASS (2026-08-19) is the evidence it does not false-FAIL correct work |
| 2 | on the `LogTemp` category | fully | count gate — `'CRAFTBENCH_SANITY_OK' in the BeginPlay window` (the device's `InCategory != Category` early-return makes any other category invisible, surfacing as count 0) | tag gate fired first | nothing — probed by `wrong-category-log/` |
| 3 | at `Display` verbosity or louder | fully | count gate — same literal (the device's verbosity-mask floor drops anything quieter than Display, surfacing as count 0) | tag gate fired first | nothing behavioral; no variant authored (identical count-0 signature to row 2) |
| 4 | exactly once | fully | count gate — `in the BeginPlay window; observed` (`Captured == 1`, not `>= 1`) | tag gate fired first | nothing — probed by `tick-repeat-emit/` in the >= 2 direction; the 0 direction is the empty leg |
| 5 | on the first frame of play | **fully**, to one frame (closed 2026-08-19) | `Expected the emission on the first frame of play; it arrived N frame(s) after the world initialized its actors (limit 1)` | count gate fires first | a GFrameCounter delta between listener-install (`OnWorldInitializedActors`, pre-BeginPlay) and the first match. A frame counter deliberately, not a world time: `Serialize` can run on whichever thread called GLog, where dereferencing a UWorld is unsafe, and a frame delta does not silently change meaning when the runner's `-FPS` does. **MEASURED on the reference: `[CB-SANITY] init_frame=306 match_frame=306 delta=0`.** The bound is 1, not 0, so an engine-side reordering cannot turn correct work into a FAIL; it is still ~6x tighter than the old 0.1s checkpoint window, and a 0.05s BeginPlay timer now lands at delta ~3 and FAILS. The delta is logged on the PASS path too, so the slack stays a measured quantity rather than a remembered one |
| 6 | via `UE_LOG` (mechanism) | NOT ASSERTED (by design) | none — the listener is an `FOutputDevice` on `GLog`; any write routed through GLog with the right category/verbosity/substring counts (e.g. a raw `GLog->Log`) | — | mechanism substitution; accepted residual under the behavior-only basket law |
| 7 | the actor otherwise remains in the world | **fully** (closed 2026-08-19) | `Expected the actor tagged 'SanityRoot' to still be in the world at the checkpoint; found` | count gate fires first; and the PrepareTest tag gate fires earlier still for a BeginPlay-time Destroy() | the tag is now re-resolved AT the checkpoint, not only at PrepareTest. `logs-then-destroys-self/` destroys inside BeginPlay and so is still credited at the PrepareTest gate (its MATRIX row is unchanged — a new gate must not move which message an existing leg scores on); what this closes is the DEFERRED route, where a 0.05s timer destroyed the actor after PrepareTest had already resolved it and nothing ever looked again |
| 8 | solve in C++ on the existing class; no Blueprint subclass, no level edit, no test-file edit | by the sandbox + substrate model, not a fixture literal | level edits: `Content/Maps/` is deny-listed (exit 4); test edits: `Source/CraftBenchTests/` is outside the writable set AND graded from git HEAD | — | a Blueprint subclass .uasset under an `asset_writable` prefix is path-ACCEPTED but inert — it cannot enter the deny-listed graded map, so it cannot affect any gate |

## Fixture literal split — DONE 2026-08-16 (awaiting the sweep)

Applied per the Q8 ruling (an internal working note (not shipped))
as a MESSAGE-ONLY split: only the FinishTest message strings changed; the
pass predicate (`Captured == 1`), gate order, and every verdict are
byte-identical to the pre-split fixture. One deliberate deviation from the
original draft: the draft routed the `Captured < 0` listener-fault sentinel
to the `Error` channel, but that moves a verdict (Failed -> Error), which
the Q8 contract line reserves for a task-replacing change — so the sentinel
branch keeps the `Failed` verdict and gets its own distinct literal naming
the verifier-side fault instead (no row credits it; investigate, never
credit). `Source/CraftBenchTests/` change: review-gated on commit, takes
grading effect only once committed. All literals are pure ASCII per the
ASCII rule.

The count gate (`SanityFunctionalTest.cpp`, `OnCheckpoint`) now reads (as
applied, minus in-code comments):

```cpp
	else if (Captured == 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; observed none."));
	}
	else if (Captured > 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; observed %d (more than one)."),
				Captured));
	}
	else
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected exactly one LogTemp/Display emission containing 'CRAFTBENCH_SANITY_OK' in the BeginPlay window; the log listener was never installed (count unavailable) - verifier-side fault to investigate, not an agent defect."));
	}
```

Crediting, live in the table above: `empty` and `wrong-category-log/` credit
`in the BeginPlay window; observed none.` and `tick-repeat-emit/` credits
`(more than one)` — disjoint, count-bearing, and independent of the runtime
`%d` value. The split still CANNOT separate `empty` from
`wrong-category-log/` (both are count 0 at the same gate —
invisible-to-the-listener is one reason, not two); that pair's separation
stays verdict-level per the matrix note, permanently.

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- Authored 2026-08-16 from the spec + the shipped fixture; revised 2026-08-16
  per adversarial verify (shared-literal crediting made honest, spans
  collapsed to the gate literal). ~~NOT YET EXECUTED~~ [SUPERSEDED: it RAN the same day — see the EXECUTED line above] — validation was queued behind
  the reference sweep.
- **Fixture literal split applied 2026-08-16 (message-only; verdicts,
  predicate and gate order byte-identical; awaiting the sweep):** rows
  re-credited to the per-reason literals above. The 2026-08-16 EXECUTED line
  predates the split, so the next `cb discriminate` run re-validates the new
  substrings.
- **Execution-time reason checks (re-run when the split package first runs):**
  - `empty` and `wrong-category-log/` leg logs must each show
    `observed none.` at the count gate.
  - `tick-repeat-emit/` leg log must show `observed N (more than one).` with
    N >= 2 (predicted ~6: fixed dt 1/60, checkpoint at world t=0.1s; the
    exact N is an execution-time observation, deliberately not part of the
    credited substring).
  - A leg showing `the log listener was never installed` is a
    listener-install fault (verifier-side), not discrimination evidence —
    investigate, do not credit.
- Prediction risk worth naming before the run: `logs-then-destroys-self/`
  depends on `Destroy()` completing before `PrepareTest` resolves the tag
  (BeginPlay precedes PrepareTest in PIE per the substrate docs, and
  `UWorld::DestroyActor` is synchronous). If PIE ordering ever surprises and
  the actor survives to PrepareTest, the variant would PASS outright (count
  would read 1) — a discrimination failure to fix by re-aiming the variant,
  not by widening the gate.
