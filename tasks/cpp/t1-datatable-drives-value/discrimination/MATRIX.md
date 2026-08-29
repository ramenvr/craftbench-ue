# Discrimination matrix — t1-datatable-drives-value

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Every substring is a verbatim
contiguous span of ONE `FinishTest(EFunctionalTestResult::Failed, ...)` source
literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-datatable-drives-value/DataDrivenFunctionalTest.cpp`,
never spanning a printf placeholder. Run:
`cb discriminate --task cpp/t1-datatable-drives-value [--wip]`.

**Crediting granularity, stated up front:** since the message-only literal
split (DONE 2026-08-16, see "Fixture literal split" below) the value gate
prints one `Failed` literal per failure reason — a sentinel branch (the -1
was never replaced) and a wrong-value branch (a non-sentinel wrong value) —
so `empty` and `late-apply-after-checkpoint/` credit the sentinel literal
and `hardcoded-guess/` credits the wrong-value literal: reason-level, and
pairwise non-containing. What no split can add: `empty` vs `late-apply` are
OBSERVATIONALLY IDENTICAL at cp0 by construction (both fire the sentinel
branch at t=1.00s), so that pair's separation is verdict-level only (the
empty leg is exempt from pairwise disjointness by design,
`matrix_oracle.is_isolation_leg`).

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | value gate (cp0, t=1.0s: sentinel left) | `still reads the -1 sentinel: the DT_Tuning 'Default' row's TunedValue was never applied` | #2 (unread table leaves the -1 sentinel). Reason-level credit via the sentinel-branch literal (split DONE 2026-08-16). |
| `hardcoded-guess/` | FAIL | value gate (cp0: wrong value) | `a wrong value means it wasn't read from the DT_Tuning 'Default' record` | #1 (number written in code; undisclosed non-round row value + tight tolerance). Reason-level credit via the wrong-value-branch literal (split DONE 2026-08-16); the printf-expanded `ConfiguredValue=100.0000` (vs the sentinel) stays outside the source-span rule — see Status for the execution-time corroboration. |
| `double-typed-property/` | FAIL | property-read gate (cp0) | `Could not read a float 'ConfiguredValue' UPROPERTY` | #4 (renamed/retyped property; fixture reads the float UPROPERTY by name). Own literal — reason-level credit. |
| `late-apply-after-checkpoint/` | FAIL | value gate (cp0: sentinel still present at t=1.0s) | `still reads the -1 sentinel: the DT_Tuning 'Default' row's TunedValue was never applied` | #2 boundary (correct lookup, applied AFTER the first checkpoint — probes the t=1.0s observation window). Reason-level credit via the sentinel-branch literal — shared with `empty` by nature (both genuinely read the sentinel; the empty leg is exempt from pairwise disjointness by design). **Byte-identical failure output to the empty leg** (both fire the sentinel branch at t=1.00s): no log substring can ever separate them. Kept anyway — VERDICT-level discrimination: it proves a DIFFERENT plausible-wrong submission fails (a fully correct FindRow lookup deferred behind a 1.5s timer, the "wait for assets to settle" shape), where empty proves the untouched scaffold fails. The separation exists in source, not in observable output, and stayed that way through the literal split (DONE 2026-08-16). |

Notes:
- **The fixture has exactly four `EFunctionalTestResult::Failed` literals**
  (tag-count gate, property-read gate, and the value gate's sentinel +
  wrong-value branches since the 2026-08-16 message-only split) plus one
  `EFunctionalTestResult::Error` literal (`PrepareTest: no UWorld available`),
  which is a harness-fault path, not a graded FAIL, and intersects no row
  substring. The split changed ONLY the messages (Q8 contract line): the
  gate predicate and every verdict are byte-identical, so the "-1 sentinel
  left" and "wrong value" causes now print distinct literals while the
  graded outcomes are untouched.
- Within the value gate, the reason (sentinel vs wrong value) is now carried
  by WHICH literal fired; the printf-expanded numbers
  (`ConfiguredValue=100.0000` on the wrong-value branch) remain
  execution-time corroboration in Status, never crediting cells — the
  source-span rule keeps expanded placeholders out of the substring cells.
- The empty leg runs the committed scaffold `ADataDrivenActor` (tagged, float
  `ConfiguredValue = -1`, no lookup), so it passes the tag-count and
  property-read gates and dies first at the value gate at cp0 — the predicted
  first-fire gate for an empty submission.
- The tag-count gate (`Expected exactly one actor tagged 'DataDrivenRoot' in
  the test level; found `) has no hand-authored variant: the tag is stamped by
  the scaffold constructor and the reference keeps that line; a variant that
  drops it would test a point no anti-gaming note names, and whether the
  committed .umap's placed instance ALSO serialized the tag is not
  determinable from source (scaffolder retired) — argued from the named
  assertion instead.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. All
  substrings above are ASCII-only.
- **EOL:** the reference is CRLF; all six variant source files are emitted
  CRLF, so each variant's diff vs the reference is exactly its banner comment
  plus the one behavioral delta.

## Fixture literal split — DONE 2026-08-16 (awaiting the sweep)

Applied per the Q8 ruling (an internal working note (not shipped))
as a MESSAGE-ONLY split in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-datatable-drives-value/DataDrivenFunctionalTest.cpp::OnCheckpoint`:
only the FinishTest message strings changed; the gate predicate, gate order,
and every verdict are byte-identical to the pre-split fixture (this task's
draft already kept both branches on the `Failed` channel, so it was applied
as drafted — no verdict moved). `Source/CraftBenchTests/` change: review-gated
on commit, takes grading effect only once committed.

Verbatim BEFORE (pre-split):

```cpp
	if (FMath::Abs(static_cast<double>(Value) - ExpectedRowValue) > Tolerance)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs ConfiguredValue=%.4f, expected %.4f (the DT_Tuning 'Default' row's TunedValue). ")
				TEXT("A -1 reading means the record was never read; a wrong value means it wasn't read from the record."),
				TimeSeconds, Value, ExpectedRowValue));
		return;
	}
```

Verbatim AFTER (as applied, minus in-code comments):

```cpp
	if (FMath::Abs(static_cast<double>(Value) - ExpectedRowValue) > Tolerance)
	{
		if (FMath::Abs(static_cast<double>(Value) - (-1.0)) <= Tolerance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs ConfiguredValue still reads the -1 sentinel: the DT_Tuning 'Default' row's TunedValue was never applied."),
					TimeSeconds));
			return;
		}
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs ConfiguredValue=%.4f, expected %.4f: a wrong value means it wasn't read from the DT_Tuning 'Default' record."),
				TimeSeconds, Value, ExpectedRowValue));
		return;
	}
```

The rows above now credit: empty and late-apply-after-checkpoint ->
`still reads the -1 sentinel: the DT_Tuning 'Default' row's TunedValue was
never applied` (sentinel branch); hardcoded-guess -> `a wrong value means it
wasn't read from the DT_Tuning 'Default' record` (wrong-value branch). Both
literals are ASCII-only, and each row's span avoids the shared
`At t=%.2fs ConfiguredValue` prefix so the two branches stay
substring-disjoint. Honesty limit, stated so nobody oversells the split:
empty and late-apply are OBSERVATIONALLY IDENTICAL at cp0 by construction
(both fire the sentinel branch at t=1.00s), so the split separates
sentinel-vs-wrong-value, and can never separate empty-vs-late — that pair's
discrimination remains verdict-level only (see the late-apply row note).

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`DataDrivenFunctionalTest.cpp` unless the row says otherwise; the gate name is
the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed actor stays discoverable (exactly one) | fully | tag-count gate — `Expected exactly one actor tagged 'DataDrivenRoot' in the test level; found ` | unconditional (first gate) | subclassing/renaming the class is tolerated by design (identity is the tag); destroying or duplicating the tagged actor at runtime fails here |
| 2 | public `ConfiguredValue` setting other code can read | fully | property-read gate — `Could not read a float 'ConfiguredValue' UPROPERTY on the DataDrivenRoot actor.` | row 1 | visibility specifiers/category are free; only "a float UPROPERTY named ConfiguredValue, readable by reflection" is gated |
| 3 | look up the `Default` record and copy its numeric field onto `ConfiguredValue` when gameplay begins | as "correct value present by t=1.0s" | value gate (cp0) — sentinel branch `row's TunedValue was never applied` / wrong-value branch `wasn't read from the DT_Tuning 'Default' record` | rows 1–2 | any mechanism that lands the value before t=1.0s passes — "during BeginPlay" per se is not gated (timers/Tick under 1.0s slip through; the late-apply variant probes the far side of this boundary) |
| 4 | the applied value is stable (other gameplay code can rely on it) | fully | value gate re-fires at cp1 (t=2.0s) — same two literals | rows 1–3, and cp0 failing ends the test first | drift smaller than +/-0.01 between t=1.0 and t=2.0 |
| 5 | the value must COME FROM the record — never a number written in code | NOT ASSERTED (mechanism level) | no gate reads the agent's source or traces the FindRow call; the defense is statistical — the row value is non-round, undisclosed in the prompt, and the tolerance is +/-0.01 | — | a hardcode of the exact row value would PASS; implausible without disclosure, but structurally undefended (no AST/source assertion exists — do not invent one) |
| 6 | `ConfiguredValue` starts at the sentinel `-1` | NOT ASSERTED | no pre-BeginPlay observation exists (first sample is t=1.0s); this is workspace-state prose, not a graded behavior | — | an agent may re-initialize the sentinel to anything; only the post-lookup value is observed |
| 7 | do not edit the data table (`Content/Data/DT_Tuning`) | fully, by the sandbox (not an L2 gate) | `Content/Data/` is outside `writable` and outside the `asset_writable` allowlist — a submitted DT_Tuning is an exit-4 SANDBOX-REJECT before any layer runs | — | nothing; allowlist-miss rejection |
| 8 | do not edit any test file | fully, by substrate provenance (not an L2 gate) | runner materializes `Source/CraftBenchTests/` from git HEAD; agent disk edits never reach the grade (+ human review gate) | — | nothing at grade time |
| 9 | solve in C++ on the existing class | structurally (weak) | no gate — the map's placed instance is the scaffold C++ actor and `Content/Maps/` is deny-listed, so the graded behavior must ship through the compiled module; "on the existing class" itself is unenforced (a new tagged C++ class replacing the instance at runtime could pass rows 1–4) | — | mechanism-agnostic by basket law; accepted residual |
| 10 | (spec L1 clause) no new shadowed-variable / deprecated warnings | only under `--strict-warnings` | L1 counts `warning_count_agent_files` on every build but gates on it only when the runner is invoked strict — the default discriminate run does not gate warnings | — | a warning-emitting but compiling submission passes L1 by default |

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- Authored 2026-08-16 from the spec + the shipped fixture; revised same day
  (adversarial-verify pass: gate-level crediting made explicit, shared value-
  gate substring unified, literal-split recommendation added, variant EOLs
  re-emitted CRLF to match the reference). ~~NOT YET EXECUTED~~ [SUPERSEDED: it RAN the same day — see the EXECUTED line above] — validation
  queued behind tonight's reference sweep.
- **Fixture literal split applied 2026-08-16 (message-only; verdicts,
  predicate and gate order byte-identical; awaiting the sweep):** the three
  value-gate rows re-credited to the per-reason literals above. The
  2026-08-16 EXECUTED line predates the split, so the next `cb discriminate`
  run re-validates the new substrings.
- Execution-time checks to run alongside the substring greps (corroboration
  the credited literals do not carry):
  - empty and late-apply-after-checkpoint legs: the value-gate line must read
    `At t=1.00s ConfiguredValue still reads the -1 sentinel` (sentinel branch
    at cp0).
  - hardcoded-guess leg: the value-gate line must read
    `At t=1.00s ConfiguredValue=100.0000, expected 42.5000` (wrong-value
    branch, not the sentinel).
  - late-apply timing margin (why the sentinel claim is robust, not a race):
    the variant's lookup rides a 1.5s `SetTimer` armed in BeginPlay; the
    fixture samples at world game-time t=1.0s (`SetCheckpointSchedule({1.0,
    2.0})` reads `GetWorld()->GetTimeSeconds()`, the same clock the timer
    consumes) and BeginPlay on a placed actor fires at world t~=0 before the
    fixture's PrepareTest — a >=0.5s margin of fixed-timestep game time on
    the SAME clock, deterministic under the runner's `-FPS`. Confirm at
    execution that cp0 fires the sentinel FAIL and the run ends before the
    timer lands (cp0 firing no FAIL at all — the leg passing outright —
    would mean the margin assumption broke).
