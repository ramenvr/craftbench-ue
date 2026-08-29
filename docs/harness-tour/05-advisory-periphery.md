# 05 — The Advisory Periphery (and why it never certifies anything)

> **Read this section last, and read it lightly.** Everything here is *annotation*. The deterministic gate — L1 build, L2 PIE fixtures, L2-introspect — is the eval. It is the only thing that produces a PASS/FAIL, and per spec FR-020d that is by design. The two subsystems below decorate a verdict with extra colour; neither can move it. If you only remember one sentence from this page: **the gate decides; R2 and the Aura rig annotate.**

---

## 1. `verify-r2` — the firewalled, non-gating LLM judge

### Purpose

The deterministic gate can only check what it can *deterministically* check: did it build, did the PIE trace match, does the `.uasset` graph have the right nodes. There is a residue it structurally cannot express — visual fidelity, design quality, the helpfulness of prose advice (`config.py:9-10`, the three R2 `DIMENSIONS`). R2 is an *advisory* signal over exactly that residue. It is an LLM judge, and the entire design exists to make an LLM judge **safe to attach to a deterministic benchmark without contaminating it**. It does that with two provable properties:

- **Non-gating** — the advisory can never flip PASS/FAIL.
- **Firewalled (anti-anchoring) + anti-circular** — the judge never sees the gate's verdict, never sees the reference solution, never sees the answer-key task sections, and gathers its own evidence only through CraftBench's own stock-UE / filesystem primitives (never Aura, never the agent-under-test).

The module docstring at `tools/verify-r2/judge.py:1-26` is the canonical statement of intent.

### Key files (what each does)

| File | Role |
|---|---|
| `tools/verify-r2/run_r2.py` | Orchestrator + CLI. Builds the firewalled judge workspace, wires the live model + tools, runs the ensemble, writes `r2-advisory.json`. |
| `tools/verify-r2/judge.py` | The judge core: `JudgeContext`, the `assert_firewalled` invariant, the read-only tool implementations, the single-judge loop (`run_one_judge`), and the ensemble fold (`run_ensemble`). |
| `tools/verify-r2/rubric.py` | Parses the inline `## R2 advisory rubric` JSON block from a task `.md` into `Rubric`/`Criterion` dataclasses. Judges nothing — pure data. |
| `tools/verify-r2/ensemble.py` | Pure-math aggregation: N judges → `advisory_score` (median) + `confidence = coverage × agreement × groundedness`. No model, no UE. |
| `tools/verify-r2/report_block.py` | The `R2Advisory` dataclass that hangs off the report. `gating` is hard-coded `False`; `validate_non_gating()` refuses anything else. |
| `tools/verify-r2/evidence/record.py` | `EvidenceRecord` — the content-addressed, anti-circular bundle of everything the judge observed, with `assert_anticircular()`. |
| `tools/verify-r2/ue_tools.py` | The optional live `editor_introspect` tool (read-only headless editor-Python). **Disabled by default** — see the gotchas. |
| `tools/verify-r2/config.py` | The two closed vocabularies: `EVIDENCE_SOURCES` (anti-circularity) and the firewall section/path/artifact lists (anti-anchoring). |

### Data flow (inputs → outputs)

```
task.md  +  submission dir  +  clean substrate
        │
        ▼  run_r2.build_judge_workspace()              (run_r2.py:64)
   clone substrate MINUS answer-key paths, overlay submission
        │   - skips Source/CraftBenchTests/ (the fixtures ARE the answer key)
        │   - skips AGENT_WRITABLE.json, report.json/verdict.json/score-report.json
        │   - skips reference-solutions/, gate-logs/                 (run_r2.py:44-61)
        ▼  judge.build_judge_context()                 (judge.py:243)
   JudgeContext = rubric  +  SCRUBBED behavior prompt  +  read-only tool menu
        │   assert_firewalled() runs here and fails CLOSED            (judge.py:176)
        ▼  judge.run_ensemble()  → N × run_one_judge()  (judge.py:596 / 466)
   each judge: tool_call → fenced untrusted result → … → {"type":"final", verdicts}
        ▼  ensemble.aggregate()                         (ensemble.py:54)
   advisory_score (median) + confidence + per-criterion agreement/spread
        ▼  R2Advisory(gating=False); validate_non_gating()  (report_block.py:76)
        ▼
   r2-advisory.json   →   attached to report.json as report.r2_advisory
```

### The non-gating proof (the load-bearing part)

R2 is wired into the gate as a **Layer with `gating=False`**: `R2Layer` at `tools/verify-single/layers/registry.py:325-330` declares `key, gating, order, requires = "R2", False, 40, ()`. Its output goes to `ctx.advisory_out["R2"]`, **never** to `layers_out`. The `overall` verdict is then computed in `run_task.py:1454-1456` over `layers_out` alone:

```python
overall = "pass" if all(lr.status == "pass" for lr in layers_out.values()) else "fail"
```

Because advisory layers are structurally absent from `layers_out`, no R2 value can be read into `overall`. This is belt-and-braces:

1. The registry never puts R2 in `layers_out` (registry.py).
2. `R2Advisory.gating` is a hard-coded `False` and `validate_non_gating()` raises `NonGatingViolation` on anything else (`report_block.py:39, 76-81`).
3. `report_block.compute_overall()` (`report_block.py:84-92`) *accepts* an `r2_advisory` argument and deliberately never reads it — an executable demonstration that the certified overall ignores R2.

### The firewall (anti-anchoring) and anti-circularity

These are the *interesting* invariants, and both are enforced as raising assertions, not comments:

- **`assert_firewalled(ctx)`** (`judge.py:176-230`) enforces, in order: (1) the evaluator model must differ from the agent-under-test model (no self-grading); (2) no firewalled answer-key task-section body leaked into the judge's prompt, and the prompt is *exactly* the allow-list scrub (`extract_judge_visible_prompt`); (3) every tool's `kind` is in `EVIDENCE_SOURCES`; (4) no reachable file is a gate/reference artifact. It runs at context-build time and fails closed.
- **What the judge may see** is a two-section allow-list: `JUDGE_VISIBLE_TASK_SECTIONS = ("Prompt given to the agent", "Workspace state pre-task")` (`config.py:42-45`) — the *same* scrub the agent under test saw. The answer-key sections (`Verifier specification`, `Anti-gaming notes`, `Reference solution`, …) are the `FIREWALLED_TASK_SECTIONS` (`config.py:48-55`) and are dropped.
- **There is deliberately no `gate_result` evidence source.** Re-read `config.py:21-30`: the closed `EVIDENCE_SOURCES` vocabulary has P1–P5 stock-UE primitives, the workspace filesystem, the judge's own re-run logs, the submission artifact, and author-pinned ground truth — but the gate's PASS/FAIL simply does not exist as a citable source. A `ToolSpec` whose `kind` is outside that set cannot even construct (`judge.py:140-145`). Anti-circularity is enforced again on the evidence bundle by `EvidenceRecord.assert_anticircular()` (`record.py:68-80`): `aura_mcp_tools_invoked` must stay empty and `agent_under_test_consulted` must stay `False`.

### Important schemas

- **The advisory block** (`R2Advisory`, `report_block.py:26-57`): `rigor_tier`, `evaluator_model_id`, `ensemble_n`, `advisory_score` (informational only), `confidence`, `confidence_factors` (`coverage`/`agreement`/`groundedness`), `per_criterion`, `reliability_flags`, `evidence_record_sha256`, and the hard `gating: false` / `NON_GATING: true`.
- **The output file** is `craftbench.r2.advisory/v1` (`run_r2.py:191`), carrying the advisory plus per-judge verdicts and evidence ids.
- **The rubric** lives *inline* in the task `.md` as a fenced JSON block under `## R2 advisory rubric` (`rubric.py:31, 91-105`), parsed by the same H2-split machinery as every other task section. Each `Criterion` has an `id`, a `dimension` (must be one of the three `DIMENSIONS`), a `weight`, and a `verdict_to_points` table. Author-pinned `groundtruth_facts` are validated to contain no grading directives (`rubric.py:41-51`) — a fact may state project truth, never "score this pass".

### How to run / observe it

R2 is opt-in behind a flag on the *deterministic* runner, which shells out to the R2 subprocess:

```sh
python3 tools/verify-single/run_task.py \
    --task tasks/<id-with-rubric>.md \
    --submission <dir> --ue-root /path/to/UE_5.8 \
    --r2 --r2-eval-model claude-opus-4-8 --r2-agent-model <agent-model> --r2-ensemble 5
```

It only fires when `--r2` is set **and** the task has a `## R2 advisory rubric` (`run_task.py:1222-1226`). The advisory subprocess is best-effort: `_maybe_run_r2` never raises and degrades to an error-note advisory on failure (`run_task.py:1207-1256`). You can also drive it directly via `tools/verify-r2/run_r2.py` (needs `ANTHROPIC_API_KEY`). The whole module is unit-testable with **no UE and no API key** because `llm_call` and the UE tool are injectable seams — `python3 -m unittest discover -s tools/verify-r2/tests` runs **79 tests** green offline.

### Non-obvious gotchas

- **`editor_introspect` is OFF by default and gated behind `--unsafe-free-form-introspect`** (`run_r2.py:158-160, 328-332`). Free-form read-only editor-Python can still read outside the workspace and reach the network — an answer-key exfiltration / anti-circularity vector. Don't flip it on outside trusted local runs.
- **Tool results are UNTRUSTED.** The judge reads agent-authored files, so a malicious submission could embed "score this pass". Every tool result is wrapped in `_fence_untrusted` markers and the system prompt forbids obeying anything inside the fence (`judge.py:57-75, 433-440`). The firewall is case-insensitive on macOS APFS so a case-variant path can't slip (`judge.py:221, 289-302`; `run_r2.py:54-61`).
- **`confidence` and `advisory_score` are deliberately two different numbers.** A high score with low confidence (poor coverage, judges disagree, ungrounded claims) is a *weak* signal — the leaderboard renders R2 as a second-class "advisory — not certified" column (`report_block.py:1-6`). Don't read `advisory_score` without reading `confidence`.
- **A degraded ensemble is surfaced, not hidden.** Judges that error out (API failure) or exhaust their step budget produce abstained verdicts; `run_ensemble` flags `judge_errored:`, `step_exhausted:`, and `degraded_ensemble` rather than silently scoring off the survivors (`judge.py:620-629`).
- **The judge is told to call `read_task_groundtruth` first**, because firewall-withheld and repo-level paths are *not* on its disk; absence-on-disk alone must never be scored as a hallucination (`judge.py:442-449`). This is subtle: the firewall removes real files from view, which would otherwise look like "invented" claims.

---

## 2. The rig (`aura_rig/`) — drive, snapshot, hand to the gate

> **Read this section for the architecture, not for a runnable lane.** The
> hardest product it was built for — a proprietary agent driven headlessly
> through its own UI — is **not part of this public release**: the
> browser-drive, its login machinery and its run CLIs were removed rather than
> published, and the earlier local-HTTP autonomous path went with them. What
> survives in `aura_rig/` is the shared plumbing every runnable arm still uses.
> The load-bearing point is unchanged either way: *the rig generates a
> submission, the one deterministic gate certifies it.*

CraftBench measures several *arms* against the same gate, and `aura_rig/` is the
plumbing that drives them. Its job is to *generate a submission and rich
telemetry*, never to judge. `driver.py` does drive + trace parse +
fairness-safe backup/restore; `proxy.py` is a logging proxy that captures
per-request tokens and the true on-wire model; `model_keys.py`, `preflight.py`
and `provenance.py` round it out.

The point to internalize: after the rig drives an agent and snapshots its
deliverable, it grades that deliverable by calling `driver.grade()`, which
invokes **the exact same `tools/verify-single/run_task.py` deterministic gate**
as every other arm. The elaborate token/trace/sub-agent telemetry
(`summary.json` under `runs/<backend>/<task>-<ts>/`) is provenance *about how*
the verdict was reached, never an input *to* it. The fairness machinery — stub
the answer-key fixtures, move untracked WIP aside, back up and restore the
writable tree with **no git mutation** — protects the gate's integrity rather
than softening it. So even at the most autonomous, telemetry-rich edge of the
harness, certification still routes through the one deterministic gate: these
are annotations on a verdict that L1/L2/L2I, and they alone, decide.
