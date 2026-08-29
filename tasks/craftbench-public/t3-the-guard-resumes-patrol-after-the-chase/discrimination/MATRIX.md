# Discrimination matrix

Status: **REFERENCE PASS / EMPTY FAIL PROVEN.** Admission has three clean
exact-one Success rounds. The harvested two-package reference passed unified
L1/L2/L2I, while the exact empty baseline passed L1 and failed the intended
runtime and structural topology checks.

| Submission | L1 expected | L2 expected | L2I expected | Overall expected |
|---|---|---|---|---|
| reference | PASS | PASS: all five named gates | PASS 4/4 | PASS |
| empty baseline | PASS | FAIL containing `GATE[PrioritySelectorAndDecoratorsAuthored]` | FAIL below 4/4 | FAIL |

Observed evidence matches both rows exactly:

- reference: `<run-out>/report.json`
  (`L1 PASS`, `L2 1/1`, `L2I 4/4`);
- empty baseline:
  `<run-out>/report.json` (`L1 PASS`, L2
  named topology failure, `L2I 0/4`).

## Requirements table

| Requirement | Reference expectation | Empty expectation | Evidence surface |
|---|---|---|---|
| Quiet guard executes the patrol branch | active Move To uses `PatrolPoint`; visible route progress | no running valid tree or patrol active node | L2 engine-owned active node and path following |
| True alert aborts patrol and starts chase | response within the scheduled window | no observer-driven transition | `GATE[TrueKeyAbortsPatrolAndStartsChase]` |
| Moving target is genuinely chased | distance closes while target moves; no teleport | no target request or no closing distance | `GATE[ChaseClosesDistance]` |
| False reset exits chase | active Move To changes from `LiveTarget` to `PatrolPoint` before target arrival | remains idle/chasing or uses native shadow | `GATE[ResetFalseExitsChase]` |
| Original patrol resumes | reaches one live marker and progresses toward the other | never re-enters route loop | `GATE[PatrolResumesAfterReset]` |
| Exact asset topology | selector, decorator abort, chase and patrol branches | empty graph lacks topology | fixed L2I 4/4 |

Only these two rows belong in the committed matrix. Admission experiments and author-only probes are recorded in `notes.md` and `authoring/RUNBOOK.md`, not added as benchmark submissions.
