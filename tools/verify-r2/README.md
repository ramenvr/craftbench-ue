# CraftBench R2 advisory judge

`tools/verify-r2/run_r2.py` runs the **R2 advisory judge** — an LLM-ensemble
that annotates a graded submission with a rubric score and confidence. It is
**strictly NON-GATING**: it can *never* flip a PASS/FAIL. The deterministic
L1/L2/L2I verifier (`tools/verify-single/`) is the only thing that decides the
outcome, per spec **FR-020d** ("no LLM-as-judge in the PASS/FAIL gate"). R2
exists to add a second, human-readable signal to the leaderboard, rendered as a
second-class *"advisory — not certified"* column.

> **Non-gating is enforced in code, not by convention.** `report_block.py`
> hard-codes `gating=False`/`NON_GATING=True` on every `R2Advisory`;
> `validate_non_gating()` raises on anything else, and `compute_overall()`
> *accepts* an advisory argument but structurally never reads it — the certified
> overall is a pure function of the deterministic layer statuses.

## How it's invoked

Directly:

```sh
python tools/verify-r2/run_r2.py \
  --task        tasks/<id>.md \
  --submission  /path/to/agent/output \
  --substrate   UE-projects/CraftBenchTemplate \
  --agent-model <model-under-test> \
  --eval-model  claude-opus-4-8 \
  [-n 5] [--out out/r2-advisory.json]
```

The judge model call is a **dependency-free `urllib` POST to the Anthropic
Messages API** (`make_anthropic_llm_call`); it needs `ANTHROPIC_API_KEY`. There
is no SDK dependency and — by design — **no Aura import** (see below).

Wired into a graded run: `tools/verify-single/run_task.py --r2` shells out to
`run_r2.py` *only* when the task carries a `## R2 advisory rubric` section
(`_maybe_run_r2`). It runs after the deterministic verdict is already computed,
never raises into the grade, and attaches the returned advisory block to the
report untouched. Any judge failure yields an `{"status": "error",
"gating": false, ...}` note — visible but harmless.

## Anti-circularity firewall

The judge must not be able to grade Aura *by asking Aura*, nor anchor on the
answer key:

- **Fresh, laundered workspace.** `build_judge_workspace()` clones
  `substrate ∪ submission` into a throwaway dir per run. The verifier-only
  fixture module (`Source/CraftBenchTests/` — encodes the answer key), the
  sandbox manifest (`AGENT_WRITABLE.json`), and any deterministic-gate
  report/verdict artifact are **filtered out** (case-insensitively). A submission
  that tries to smuggle a file onto a firewalled path is *refused*.
- **No agent-under-test tooling, ever.** The live model call goes straight to
  Anthropic — never through any arm's MCP layer. This invariant (I2) is
  **executable**: `tests/test_anticircularity.py` greps every non-test module
  under `tools/verify-r2/` and fails if any imports `aura*` or references
  `mcp__unreal_*`.
- **Distinct judge model.** `--eval-model` must differ from `--agent-model`;
  the runner rejects equality to prevent a model self-grading.

## Layout

- `run_r2.py` — orchestrator (workspace → firewalled context → ensemble → JSON).
- `judge.py` — per-judge context, read-only FS/workspace/groundtruth tools, ensemble loop.
- `rubric.py` — rubric parsing + scoring policy.
- `report_block.py` — the `R2Advisory` dataclass + the non-gating guards.
- `ensemble.py`, `config.py`, `ue_tools.py`, `evidence/` — aggregation, constants, read-only UE probes, evidence records.

## Running the unit tests

```sh
python -m unittest discover -v tools/verify-r2/tests
```

The suite (68 tests across 12 modules, no UE and no API key required) covers the
rubric, the ensemble, evidence records, the read-only grounding tools, judge
hardening, security findings, the report block's non-gating invariant, and the
executable anti-circularity check.
