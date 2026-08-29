# Discrimination matrix — t1-overlap-logs-once

One row per submission; the "Expected message substring" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t1-overlap-logs-once [--wip]`.

Every "Expected message substring" cell is a verbatim contiguous span of ONE
`FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-overlap-logs-once/OverlapLogFunctionalTest.cpp`,
never spanning a printf placeholder.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp1 (2.0s) | `observed none - the marker never reached the LogTemp/Display-or-louder counter` | #4. Reason-level credit via the zero-branch literal (split DONE 2026-08-16). Failure output is byte-identical to `wrong-verbosity/` (both genuinely observe 0) — kept because it proves a DIFFERENT wrong submission fails: the untouched scaffold, i.e. nothing delivered at all. |
| `logs-on-beginplay/` | FAIL | cp0 (0.5s) | `marker to NOT be logged before any overlap; observed ` | #1. The one row with fully disjoint failure output (cp0 literal only). |
| `wrong-verbosity/` | FAIL | cp1 (2.0s) | `observed none - the marker never reached the LogTemp/Display-or-louder counter` | #2. Reason-level credit via the zero-branch literal — count 0 is ONE reason, so this leg shares `empty`'s substring by nature (the empty leg is exempt from pairwise disjointness by design). Byte-identical output to `empty` (a sub-Display emission is filtered and reads as 0) — kept because it proves a DIFFERENT wrong submission fails: one that binds the overlap CORRECTLY but emits below the Display floor (verdict-level discrimination). |
| `logs-per-tick/` | FAIL | cp1 (2.0s) | `the marker was re-emitted after the single induced overlap` | #3. Reason-level credit via the multiple-branch literal (split DONE 2026-08-16); the exact count sits in the uncredited `%d` (expected >= 2; ~90 at 1/60 fixed dt is an execution-time check, see Status). |

Notes:
- **Crediting is reason-level for the cp1 rows since the literal split (DONE
  2026-08-16, message-only).** The cp1 exactly-once gate now prints a
  distinct ASCII literal per failure reason — a zero branch (`observed none
  - the marker never reached the LogTemp/Display-or-louder counter`), a
  multiple branch (`the marker was re-emitted after the single induced
  overlap`, with the count in the uncredited `%d`), and a listener-fault
  sentinel branch (`log counter device was never installed`, verifier-side,
  never credited by any row) — while the `After != 1` predicate, gate order,
  and every verdict stay byte-identical (Q8 contract line: a message-only
  split is safe; a verdict move replaces the task — which is why the drafted
  `Error` re-route of the `-1` sentinel was NOT applied). The cp0 silence
  gate and the PrepareTest/probe-spawn gates are unchanged (the latter two
  are reachable only by scaffold vandalism / verifier-side faults; no row
  targets them). Even after the split, `empty` and `wrong-verbosity/` remain
  byte-identical (both genuinely observe 0 — one reason, two submissions);
  that pair is justified at VERDICT level per the table's per-row notes, and
  the empty leg is exempt from pairwise disjointness by design
  (`matrix_oracle.is_isolation_leg`).
- `logs-on-beginplay/` dies at cp0, so no cp1 literal ever prints in its
  log, and no cp1-failing leg ever prints the cp0 literal (cp0 passed there
  by definition). Since the split, `logs-per-tick/`'s cp1 output is also
  fully disjoint from the 0-count legs' (multiple branch vs zero branch).
- The raw marker spam a gamed submission emits (`LogTemp: Display:
  CRAFTBENCH_OVERLAP_OK`) contains none of the table's substrings — every
  span above carries fixture-message context (`LogTemp/Display` with the
  slash, or surrounding prose) that a bare marker line lacks.
- **ASCII rule (inherited from t2-homing-projectile, found the hard way):**
  FinishTest messages and these substrings must be ASCII-only — the UE log's
  UTF-8 bytes are read back as cp1252, so an em dash becomes mojibake and the
  substring grep misses, classifying a CORRECT fail as wrong-reason. Both
  distinct substrings above are pure ASCII (the fixture's literals are too),
  and the variant SOURCE files are ASCII+CRLF to byte-match the reference.

## Fixture literal split — DONE 2026-08-16 (awaiting the sweep)

Applied per the Q8 ruling (an internal working note (not shipped))
as a MESSAGE-ONLY split in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-overlap-logs-once/OverlapLogFunctionalTest.cpp`:
only the FinishTest message strings changed; the `After != 1` predicate,
gate order, and every verdict are byte-identical to the pre-split fixture.
One deliberate deviation from the original draft: the draft routed the
`After < 0` listener-fault sentinel to the `Error` channel, but that moves a
verdict (Failed -> Error), which the Q8 contract line reserves for a
task-replacing change — so the sentinel branch keeps the `Failed` verdict
and gets its own distinct literal naming the verifier-side fault instead (no
row credits it; investigate, never credit). `Source/CraftBenchTests/`
change: review-gated on commit, takes grading effect only once committed.

The `case 1:` arm of `OnCheckpoint` now reads (as applied, minus in-code
comments):

```cpp
			const int32 After = LogCounter.IsValid() ? LogCounter->GetMatchCount() : -1;
			if (After < 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the 'CRAFTBENCH_OVERLAP_OK' log counter device was never installed (count unavailable) - verifier-side fault to investigate, not an agent re-emission."),
						TimeSeconds));
				return;
			}
			if (After == 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly one LogTemp/Display 'CRAFTBENCH_OVERLAP_OK' emission after one overlap; observed none - the marker never reached the LogTemp/Display-or-louder counter."),
						TimeSeconds));
				return;
			}
			if (After != 1)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected exactly one LogTemp/Display 'CRAFTBENCH_OVERLAP_OK' emission after one overlap; observed %d - the marker was re-emitted after the single induced overlap."),
						TimeSeconds, After));
				return;
			}
```

Row remap, live in the table above: `empty` and `wrong-verbosity/` credit
the zero-branch tail (`observed none - the marker never reached the
LogTemp/Display-or-louder counter`), `logs-per-tick/` credits the
multiple-branch tail (`the marker was re-emitted after the single induced
overlap`) — those two tails are disjoint and each is guaranteed in every
firing of its branch. `empty` vs `wrong-verbosity/` stay byte-identical by
nature (both observe 0); their separation is verdict-level only, as noted in
the table.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`OverlapLogFunctionalTest.cpp` unless the row says otherwise; the gate name is
the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed host actor stays discoverable (scaffold preserved) | fully | resolve gate — `Expected exactly one actor tagged 'OverlapLogRoot' in the test level; found ` | unconditional (first gate) | subclassing the host in C++ is deliberately allowed (identity by tag, never by class); destroying/duplicating/untagging it fails here |
| 2 | before anything overlaps it, the actor must not emit the line at all | fully | cp0 silence gate — `marker to NOT be logged before any overlap; observed ` | row 1 fails (test already finished) | nothing before t=0.5s; a log emitted between t=0.5s and the induced overlap in the same frame is indistinguishable from an overlap-driven one (window is one checkpoint call, effectively zero) |
| 3 | when another actor first enters the volume, emit the line — once for that overlap | fully | cp1 exactly-once gate — `expected exactly one LogTemp/Display 'CRAFTBENCH_OVERLAP_OK' emission after one overlap; observed ` | rows 1–2, or the probe-spawn gate (`failed to spawn the overlap probe to induce a begin-overlap.` — verifier-side fault, never an agent defect) | mechanism is free (component vs actor delegate, native vs dynamic bind) — behavior-only by design; only ONE overlap is ever induced, see residuals |
| 4 | on the `LogTemp` category | fully (by construction) | the listener's category filter (`FOverlapLogCounterDevice::Serialize` early-returns on `InCategory != Category`) — a wrong-category emit reads as count 0 and surfaces at the cp1 token of row 3 | rows 1–2 | no dedicated "wrong category" message — the FAIL says "observed 0", identical to never-logged |
| 5 | at `Display` verbosity or louder | fully (by construction) | the listener's verbosity floor (same `Serialize`, quieter-than-Display ignored) — surfaces at the cp1 token of row 3 | rows 1–2 | Warning/Error emits count (prompt says "or louder" — in-spec, not a hole) |
| 6 | "the exact log line `CRAFTBENCH_OVERLAP_OK`" | PARTIAL | substring match only (`FCString::Strstr`) inside the counter; surfaces at rows 2/3 tokens | — | NOT ASSERTED: line EXACTNESS. A longer line embedding the marker (`UE_LOG(LogTemp, Display, TEXT("done: CRAFTBENCH_OVERLAP_OK ok"))`) counts as a match and PASSES. No gate checks the line is exactly the marker |
| 7 | solve in C++ on the existing class — no Blueprint subclass | structurally | not a FinishTest gate — the level is deny-listed (`Content/Maps/`), so the PLACED instance stays the committed C++ class; a stray BP subclass under `Content/` can never be placed, so it can never satisfy rows 2–3 | unconditional | authoring a useless BP asset is unrejected but inert |
| 8 | do not edit the level | fully | sandbox path gate — `Content/Maps/` is deny-listed in `AGENT_WRITABLE.json` (exit 4, pre-grade; not an L2 literal) | unconditional | nothing |
| 9 | do not edit any test file | fully | substrate model — the runner materializes `Source/CraftBenchTests/` from git HEAD; a working-tree tamper never reaches the grade (human review gates commits). NB: task.md's anti-gaming note #5 still says "hash-pinned" — stale language, the hash manifest retired 2026-07-16 | unconditional | nothing |
| 10 | L1: no new shadowed-variable/deprecated warnings in the agent files (spec §L1) | NOT ASSERTED (by default) | warning counting exists (`l1_build.py::_count_warnings`, `warning_count_agent_files`) but it gates ONLY under the opt-in `--strict-warnings` flag — the default discriminate/refgate path does not enforce it | — | a warning-ridden but compiling submission passes L1 on the default path |

## Accepted residuals (documented, not defended)

- **Only one overlap is ever induced.** "Once PER overlap" across repeated
  overlaps is unverified — a handler that logs only on the first-ever overlap
  and unbinds is indistinguishable from the reference. In-spec: the prompt
  says "once for that overlap", singular.
- **The probe is a spawned query-only sphere, not a walking pawn** — a
  submission gating its handler on `OtherActor->IsA<APawn>()` FAILs at cp1
  even though a human reading the prompt might call it correct. The prompt
  says "another actor", so the probe is a faithful instance; noted because it
  is the one plausible correct-ish implementation the fixture rejects.
- **End-overlap behavior is unconstrained** — nothing gates OnComponentEndOverlap;
  extra logs on OTHER categories/verbosities are also free (only
  LogTemp/Display-or-louder emissions of the marker are counted).

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task cpp/t1-overlap-logs-once --wip
```

Per-leg fallback while iterating:

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/cpp/t1-overlap-logs-once/task.md \
    --submission tasks/cpp/t1-overlap-logs-once/reference \
    --ue-root "$UE" --workdir C:\cb\wd\overlaplog-ref    # expect exit 0
```

## Status


- **EXECUTED 2026-08-16** (`cb discriminate`, first execution): **discriminated YES** — reference PASS; every leg credited via its named substring (overnight review-iteration campaign, 2026-08-16; the campaign log was removed from the tree in the 2026-08-18 doc cleanup and lives in git history).
- ~~Authored 2026-08-16 from the spec + the shipped fixture. NOT YET EXECUTED.~~
  **SUPERSEDED by the EXECUTED line above — the package ran the same day it was
  authored and every leg was credited. Kept for provenance.**
- Revised 2026-08-16 after adversarial verify: (1) the three cp1 rows now
  credit the shared gate literal's full static span (GATE-level, disclosed
  above) instead of overlapping sub-spans, with the reason-level split filed
  as the fixture recommendation; (2) all six variant files re-emitted as
  ASCII+CRLF so each byte-diff vs `../reference` is exactly the one claimed
  behavioral delta (the two no-op headers are now byte-identical).
- **Fixture literal split applied 2026-08-16 (message-only; verdicts,
  predicate and gate order byte-identical; awaiting the sweep):** the three
  cp1 rows re-credited to the per-reason literals above. The 2026-08-16
  EXECUTED line predates the split, so the next `cb discriminate` run
  re-validates the new substrings.
- Execution-time checks (claims the substrings cannot carry, verify on the
  first post-split `cb discriminate` run): `logs-per-tick/`'s observed count
  (the `%d` ahead of the credited multiple-branch tail) is >= 2 (expected
  ~90 at 1/60 fixed dt between the induced overlap at cp0 t=0.5s and cp1
  t=2.0s); `empty` and `wrong-verbosity/` both report `observed none`.
