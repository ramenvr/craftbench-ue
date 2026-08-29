# gp-harvestable-regrow — discrimination matrix

**Status (2026-08-17):** package AUTHORED this session, the task's first. It previously had
**no `discrimination/` directory at all** — the dossier verdict was `NO-EVIDENCE`. Three
one-delta variant legs are rowed below; each is a byte-exact copy of `../reference` carrying
a single behavioural change, and each "fails at" cell is a **gate-order trace** against
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/gp-harvestable-regrow/HarvestableRegrowFunctionalTest.cpp`,
not a measurement. Nothing here may be read as measured until a `cb discriminate` result is
recorded in this file.

**Coverage shape.** The fixture has three agent-reachable gates (one per checkpoint). The
`empty` leg reaches the middle one; `starts-regrowing/` takes the first and `never-regrows/`
the last, so **every gate has a leg**. `regrows-instantly/` deliberately shares the middle
gate with `empty` — see its row for why that is evidence rather than duplication.

| Submission | Overall | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | **PASS** | — | all 5 checkpoints green on BOTH framerate legs (1/1 each) | — (PASS oracle) |
| empty (no overlay → scaffold stub) | **FAIL** | checkpoint 1 (t=2.0s) | `after being walked into, the harvestable should be regrowing (carry the 'Regrowing' tag) but it does not.` | FR-017 empty. The stub binds no overlap, so the harvest never happens. It **passes checkpoint 0** (an untagged actor is correctly "active"), so this is not a first-gate trip |
| `starts-regrowing/` | **FAIL** | checkpoint 0 (t=0.5s) | `carries the 'Regrowing' tag before any harvest; it should start active.` | *(no anti-gaming note covers this)* — AUTHORED 2026-08-17, NOT YET RUN. One delta: `BeginPlay` sets the state to `Regrowing` and tags itself, i.e. it reads `Regrowing` as the ready-to-harvest marker. The overlap wiring below it is byte-identical to the reference. **This leg exists because the requirements table found that "It begins in an active state" is a real, gated requirement that none of the five anti-gaming notes mentions** |
| `regrows-instantly/` | **FAIL** | checkpoint 1 (t=2.0s) | `after being walked into, the harvestable should be regrowing (carry the 'Regrowing' tag) but it does not.` | #3 regrows instantly (no real delay). AUTHORED 2026-08-17, NOT YET RUN. One delta: `OnRegrowComplete()` is called inline instead of arming the timer, so the state passes through `Regrowing` and back inside one frame. **Shares `empty`'s literal on purpose** — it cannot do otherwise, since the gate has one message and no placeholders. What it adds is the opposite failure mode at the same gate: `empty` proves the gate catches a transition that never happens, this proves it catches one that happens and does not *persist*. That distinction is the entire content of the "5 seconds" requirement, and no leg that fails elsewhere can establish it |
| `never-regrows/` | **FAIL** | checkpoint 3 (t=6.0s) | `still carries the 'Regrowing' tag ~5.5 s after being harvested` | #2 permanently regrowing (latches and never returns). One delta: the harvest half is complete and correct — it logs, changes state, tags itself — but no return timer is ever armed. **Passes checkpoints 0–2 indistinguishably from the reference**; only the t=6.0s gate separates them. RE-POINTED 2026-08-19: the schedule became {0.5, 2.0, 5.0, 6.0, 7.0} and this leg's old credited literal (`~7 s after harvest`) no longer exists, so leaving the row alone would have scored it `no-named-assertion` |

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous literal from a
`FinishTest(EFunctionalTestResult::Failed, …)` call in the fixture, never spanning a printf
placeholder. Layers are `[L1, L2]`. The schedule is sequential and any `FinishTest` ends the
run, so **every later gate is skipped once an earlier one fires**.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed harvestable stays discoverable (exactly one) | fully | resolve gate (`PrepareTest`) — `Expected exactly one actor tagged 'HarvestableRoot' in the test level; found ` | unconditional (first gate) | nothing at authoring time — the tag is on the placed instance in the verifier-owned map |
| 2 | it **begins in an active state** | fully | cp0 gate — `carries the 'Regrowing' tag before any harvest; it should start active.` | row 1 | "active" is observed only as *absence of the `Regrowing` tag*; an internal state variable may say anything. Correct for a behaviour-only prompt |
| 3 | when **any other actor** walks into its collision volume, it is harvested | partially | cp1 gate — `after being walked into, the harvestable should be regrowing (carry the 'Regrowing' tag) but it does not.` | row 1, cp0 | THREE probers are now used (t=0.5, 2.0 and 6.0), but they are three instances of the SAME shape: a bare `AActor` with a 48-unit `USphereComponent` root, spawned at the host's own location and forced to overlap. A submission that responds only to that shape — or filters on nothing at all — still passes. “Any other actor” is gated by one example repeated, not by variety |
| 4 | it **prints a log message** on harvest | **NOT ASSERTED** — and not assertable without a prompt change (established 2026-08-19) | — (the fixture never reads the log) | — | **The blocker is the PROMPT, not the fixture.** The repo has the instrument — `t0-sanity-log-on-beginplay` gates a log line with an `FOutputDevice` on `GLog` — but it gates a NAMED token (`CRAFTBENCH_SANITY_OK`). This prompt says only “it prints a log message”, naming no token, no category and no verbosity, so any gate would have to invent a contract the agent was never given, and “some line appeared on some category” is not separable from engine chatter between two ticks. Closing it means adding a token to the prompt, which changes the task and invalidates prior measurements — an OWNER DECISION, deliberately not taken here |
| 5 | it **immediately** switches to regrowing | partially | the same cp1 gate, at t=2.0s (~1.5s after the induced harvest) | row 1, cp0 | up to ~1.5s of latency is invisible. A submission that begins regrowing on a 1s delay after the overlap passes |
| 6 | while regrowing it carries the tag `Regrowing` | fully | cp1 and cp2 gates (present) **and** cp3 gate (absent afterwards) — the tag is the only observable | row 1, cp0 | — |
| 7 | while regrowing it must **not be harvestable again**; a second walk-in does nothing | **fully** (closed 2026-08-19) | cp3 gate — `still carries the 'Regrowing' tag ~5.5 s after being harvested; either the regrow delay is longer than 5 seconds, or a second walk-in during the regrow window restarted the clock (it must do nothing)` | row 1, cp0–cp2 | a SECOND walk-in is now induced at t=2.0, inside the regrow window, with a FRESH probe (begin-overlap fires on the transition, so re-using probe A would have induced nothing). Nothing observable happens at t=2.0 — the consequence is read at t=6.0: a host with no re-entrancy guard re-harvests and restarts its 5s clock, moving its deadline to ~7.0s, so it is still tagged when a correct host has been active for ~0.5s. **Residual:** the gate observes the RESTARTED CLOCK, not “nothing happened” — a host that re-harvested without restarting the clock would still pass |
| 8 | **exactly 5 seconds** after regrowing begins, it returns to active | **fully, to a 1.0s band** (narrowed 2026-08-19 from a 5.5s band) | cp2 — `has already returned to active, ~4.5 s after being harvested; the regrow delay is 5 seconds` — and cp3 — `still carries the 'Regrowing' tag ~5.5 s after being harvested` | row 1, cp0–cp1 | the two gates now bracket the delay to **(4.5s, 5.5s]** against a required 5.0s, where before they bracketed (1.5s, 7.0s] and accepted 2s, 4s or 6.5s as “exactly 5 seconds”. The band is +/-0.5s, which is >= 10 frames of margin at BOTH declared frame rates (60 and 20) — deliberately not tighter, because the harvest instant is itself known only to within one frame |
| 9 | the 5-second delay **holds regardless of frame rate** | **fully** (closed 2026-08-19) | the whole fixture is replayed at each declared rate and ALL legs must pass; a frame-counted regrow tuned for 60 Hz fails the 20 Hz leg at cp2/cp3 with the row 8 literals. The per-leg outcome is recorded in the report as `dt leg fps=<n>: <status>` | row 1, and fail-fast: a failed 60 leg skips the 20 leg | closed by the SPEC, not the fixture: `fps_legs: [60, 20]` in the front matter. **This is the first and only use of `fps_legs` in the corpus** — the mechanism has existed in `spec.py` + `registry.py` with the legacy `_DT_LEGS_BY_TASK` table EMPTY, so it had never once executed, which is why it was validated here rather than assumed. `t1-gameplay-tag-gate` has the same hole and its notes already point at `fps_legs`; it is the obvious next adopter now the mechanism is proven. **Cost, MEASURED on the 2026-08-19 gate (workdir rg969de7):** the report records `dt leg fps=60: pass (1/1)` + `dt leg fps=20: pass (1/1)`, `tests=2/2`, and L2 = **42.56s for BOTH legs** against L1 = ~234s of the same 278s run. So a second frame-rate leg costs about **+21s**, not a second editor’s worth of time — which is why adopting `fps_legs` on `t1-gameplay-tag-gate` is cheap. The bare PASS was deliberately not trusted here: 278s looked indistinguishable from a single-leg gate, so the per-leg logs were read |
| 10 | the tag is **removed** on return to active | fully | cp3 gate — `still carries the 'Regrowing' tag ~5.5 s after being harvested` | row 1, cp0–cp2 | — (this is the requirement `never-regrows/` proves is gated) |
| 11 | it can be harvested **again** after returning to active | **fully** (closed 2026-08-19) | cp4 gate — `after returning to active the harvestable was walked into again but did not begin regrowing; it must be harvestable again` | row 1, cp0–cp3 | the run used to END once the tag cleared, so a host that woke up permanently inert scored a full pass. A fresh probe is now spawned at t=6.0 (once the host is confirmed active) and the tag is re-checked at t=7.0. **Why the probes are destroyed at cp2:** probes A and B sit inside the volume until then, and a host that re-reads its CURRENT overlaps on waking would legitimately re-harvest itself the instant it returned to active — correct behavior failed by the fixture's own leftovers. Clearing them 0.5s before the deadline removes that |
| 12 | solve in C++ on the existing class | fully, by L1 + the substrate model | not a `FinishTest` gate — the committed map places the C++ `AHarvestableActor`, so logic in a never-placed Blueprint subclass never executes, and the L1 dual-target build must exit 0 | unconditional | private helpers/members in the header are free; subclassing is tolerated by design (identity is by tag) |

### Escalation notes (holes the table found)

- **Row 9 is the significant one, and it has a ready-made fix in this repo.** `task.md`'s
  anti-gaming note 4 states that a frame-count solution "tuned for 60 Hz returns at the wrong
  world-time under any other rate". True in principle — but **this task declares no framerate
  legs** (`layers: [L1, L2]`, no `fps:`, and it is absent from `registry._DT_LEGS_BY_TASK`),
  so L2 runs exactly once at the default `fps=60` (`layers/l2_pie.py:347`). A submission that
  returns to active after 300 ticks — verbatim the example the note names — therefore
  **passes**. The mechanism to close it already exists and is used by
  `bp/t1-walk-animation-footstep-cues`: declaring two legs makes `registry.py` run the fixture
  once per rate in its own PIE process, requiring all to pass. That would also unlock a fourth
  variant (`frame-count-timer/`) that passes at 60 and fails at the second rate — the only
  kind of leg that can prove row 9 at all.
  **Not applied here, deliberately.** It would convert a currently-ungated requirement into a
  gated one, i.e. change what verdict some submissions receive, which is the owner's call
  under decision D6, not an authoring detail. The argument *for* applying it is unusually
  strong in this specific case: this task has **no measured runs at all** (it was
  `NO-EVIDENCE` until today), so there is no historical comparability to protect — the usual
  cost of tightening a grader is absent. Flagged for an owner decision with that context.
- Rows 7 and 11 share one cause — the fixture induces exactly one overlap and then stops. A
  single added checkpoint that re-overlaps during the regrow window would close row 7, and one
  that re-overlaps after the return would close row 11. This is the cheapest real strengthening
  after row 9.
- Row 4 (the log message) is a requirement in the prompt with no assertion anywhere, in a repo
  that demonstrably can assert log lines. Either gate it or drop it from the prompt; leaving it
  stated-but-ungated is the state that misleads a reader of the spec.
- Row 8's "exactly 5 seconds" is honest slack, but the prompt's wording promises far more
  precision than the (1.5s, 7.0s) band delivers. Narrowing the band is cheap; rewording the
  prompt to "about 5 seconds" is cheaper and equally sound.

## Bounded coverage (honest note)

Reference (PASS) and empty (FAIL) have both been graded through the deterministic verifier as
part of `cb refgate`. The three variant legs are **authored, not yet run**. Of the spec's five
anti-gaming notes, #2 and #3 now have committed one-delta variants; #1 (ignores the overlap
entirely) is behaviourally the `empty` leg and needs no separate variant. **#4 is not merely
uncovered but claims a defense the task does not implement (row 9), and #5 concedes its own
gap in a parenthetical (row 7)** — those two findings are the most important thing this
package produced, and neither is fixable by authoring another variant.
