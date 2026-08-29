"""cb bench — N sequential repetitions of {model} x {task} -> cost/time stats.

`cb matrix` answers "which model wins the grid" with ONE run per (model, task)
cell; repetition is deliberately out of its scope (parse_models dedupes, and
its leaderboard grid keys on (model, task) so repeats would silently overwrite).
This module is the repetition sibling: run the SAME (model, task) pair N times
SEQUENTIALLY and aggregate verdict/cost/time with spread (mean/min/max), which
is what a cost-and-latency analysis actually needs.

Hazards this module owns (vs naively looping `cb eval`):
  * run.py's run_id has 1-second granularity — two reps starting in the same
    second collide on BOTH the run dir and the derived verifier workdir
    (sha1(run_id)[:10]). Each rep gets its own --run-dir AND run() pauses
    between reps so even instant failures can't share a second.
  * `cb eval` ignores --ceiling on the baseline path; the caller's runner
    forwards an explicit agent --timeout to run.py instead.
  * pass-rate uses the graded-only denominator (adapters.base.is_graded_verdict)
    so SUBSTRATE-/SANDBOX-REJECT and harness errors never count as agent FAILs.

Results persist INCREMENTALLY: bench.json / bench.md / leaderboard.html are
rewritten after every rep, so a crash mid-batch keeps everything already
measured — including a readable comparison grid.

A multi-model bench IS the model-comparison surface: `leaderboard.html` renders
a standings table + a {model} x {task} grid where every rep is a verdict badge
linked to its run's report.html, and `models_used` attribution mismatches are
flagged per rep (trust the envelope's attribution, never the slug label).

Design seam: `run_one_rep` is injected into :func:`run` (matrix.py pattern), so
the loop + aggregation + rendering are unit-testable without UE
(tests/test_bench.py).
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from adapters.base import VERDICT_PASS, is_graded_verdict, pass_rate

from .matrix import _VERDICT_CSS, _pct


# --------------------------------------------------------------------------- #
# Pure data + helpers                                                          #
# --------------------------------------------------------------------------- #

@dataclass
class Rep:
    model: str
    task_id: str
    rep: int              # 1-based repetition index
    n_reps: int


@dataclass
class RepResult:
    model: str
    task_id: str
    rep: int
    verdict: Optional[str]              # PASS / FAIL / non-graded code, None on harness error
    cost_usd: Optional[float] = None
    agent_s: Optional[float] = None     # the agent's own wall-clock
    verify_s: Optional[float] = None    # the deterministic verifier's wall-clock
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    num_turns: Optional[int] = None
    tool_use_count: Optional[int] = None
    tool_names: Optional[List[str]] = None  # per-call sequence (drives tool-mix analysis)
    run_dir: Optional[str] = None       # where the rep's result.json landed
    error: Optional[str] = None         # harness-level failure (no verdict produced)
    models_used: Optional[List[str]] = None  # the envelope's attribution truth (never the slug)
    models_mismatch: bool = False       # attribution contradicts the requested slug
    mismatch_reason: Optional[str] = None
    underlying_verdict: Optional[str] = None  # graded verdict a MODEL-MISMATCH/CONTEXT-CONTAMINATED substitution replaced
    substrate_revision: Optional[str] = None  # verifier provenance (mixed revisions = suspect comparison)
    preamble_sha: Optional[str] = None
    report_href: Optional[str] = None   # rep's report.html, relative to the bench dir
    posthog_url: Optional[str] = None   # rep's PostHog LLM-analytics trace (aura-product)
    thread_id: Optional[str] = None     # the conversation the turn was submitted into
    thread_reused_from: Optional[str] = None  # what this rep's thread collided with


def parse_task_spec(spec: str, default_repeat: int) -> List[Tuple[str, int]]:
    """Parse a comma-separated task list with optional per-task ':N' repeat
    overrides — 'a:5,b' with default_repeat=3 -> [('a', 5), ('b', 3)].
    Dedupes on task id (first spelling wins), drops blanks."""
    seen: set = set()
    out: List[Tuple[str, int]] = []
    for part in (x.strip() for x in (spec or "").split(",")):
        if not part:
            continue
        task, _, n_str = part.rpartition(":")
        if task and n_str.isdigit():
            task_id, n = task, max(int(n_str), 1)
        else:
            task_id, n = part, max(default_repeat, 1)
        if task_id not in seen:
            seen.add(task_id)
            out.append((task_id, n))
    return out


def build_reps(models: Sequence[str],
               task_specs: Sequence[Tuple[str, int]],
               model_groups: Optional[Sequence[Sequence[str]]] = None) -> List[Rep]:
    """Group-major, then TASK-major, models within, rep-minor (stable order).

    Task-major because a task switch is the expensive boundary on the product
    path: every rep composes the single-task graded scratch, and switching
    tasks invalidates the composed tree's incremental build (and can switch
    the SUBSTRATE outright — a different .uproject for the editor). Per-task
    blocks pay that price once per task instead of once per (model, task).
    Every rep of a pair still runs back-to-back, which is what a
    like-for-like timing sample wants. On a single-task bench this order is
    IDENTICAL to the old models-major order — nothing moved.

    ``model_groups`` (optional) partitions ``models`` into ordered phases that
    each get their own task-major pass — cmd_bench passes [baseline, product]
    so baseline reps NEVER build under the product stack's memory pressure
    (the measured 5x-verify hazard; see _bench_teardown). Default: one group,
    all models. Per-drive fresh-editor and the recycle cadence are per-rep /
    pause-hook concerns and are unaffected by this ordering."""
    groups = [list(g) for g in (model_groups if model_groups is not None
                                else [models]) if g]
    return [Rep(m, t, i + 1, n)
            for g in groups for (t, n) in task_specs for m in g
            for i in range(n)]


# Per-rep cost anchors, verbatim from the certified-lane contract
# (.claude/skills/craftbench-runtask: "~$4/opus rep, ~$1-2/sonnet,
# ~$0.05/deepseek" — calibrated on the certified task). DIRECTIONAL, not
# billing: the preview exists so an operator sees the order of magnitude
# BEFORE the first token is spent. Models with no anchor are listed as
# unanchored and excluded from the total, which is therefore a FLOOR.
_COST_ANCHORS_USD: Tuple[Tuple[str, float], ...] = (
    ("opus", 4.0),
    ("sonnet", 1.5),      # skill anchor "~$1-2" — midpoint
    ("deepseek", 0.05),
)


def cost_anchor_usd(model_slug: str) -> Optional[float]:
    """The per-rep cost anchor for a model slug, or None when the certified
    lane has no calibration for it. Matches on the PINNED model's alphanumeric
    core (same normalization as attribution): 'claude-p:opus' / 'opus-4.8' /
    'openrouter:anthropic/claude-opus-4' all anchor as opus."""
    _, _, pin = (model_slug or "").partition(":")
    pin = pin.rpartition("/")[2]
    core = _norm_model(pin) or _norm_model(model_slug)
    for needle, usd in _COST_ANCHORS_USD:
        if needle in core:
            return usd
    return None


def render_cost_preview(models: Sequence[str],
                        task_specs: Sequence[Tuple[str, int]],
                        ceiling_s: int,
                        resumed: bool = False) -> str:
    """The pre-launch cost printout: the cell matrix (models x tasks x reps),
    per-rep anchors from the certified-lane contract, a total ESTIMATE, and
    the agent ceiling. Pure text — cb is non-interactive, so this printout IS
    the operator's check (no confirm prompt follows it)."""
    reps_per_model = sum(n for _, n in task_specs)
    lines = [
        "=== COST PREVIEW  (anchors: certified-lane calibration — directional, "
        "not billing) ===",
        f"  cells: {len(models)} model(s) x {len(task_specs)} task(s) = "
        f"{len(models) * len(task_specs)} cell(s); "
        f"{len(models) * reps_per_model} rep(s) total; "
        f"agent ceiling {ceiling_s}s/rep",
        "  tasks: " + ", ".join(f"{t} x{n}" for t, n in task_specs),
    ]
    total = 0.0
    unanchored = 0
    for m in models:
        anchor = cost_anchor_usd(m)
        if anchor is None:
            unanchored += reps_per_model
            lines.append(f"    {m:<28} (no anchor)   x{reps_per_model} rep(s)"
                         f"   est ?")
        else:
            est = anchor * reps_per_model
            total += est
            lines.append(f"    {m:<28} ~${anchor:.2f}/rep    x{reps_per_model}"
                         f" rep(s)   est ~${est:.2f}")
    tail = f"  TOTAL est ~${total:.2f}"
    if unanchored:
        tail += (f"  (+ {unanchored} rep(s) with no anchor — treat the total "
                 f"as a floor)")
    lines.append(tail)
    if resumed:
        lines.append("  (--resume: graded reps are reused, not re-spent — the "
                     "estimate above is the FULL plan)")
    return "\n".join(lines)


def _stats(values: Sequence[float]) -> Optional[dict]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "total": round(sum(vals), 4),
    }


def _norm_model(s: str) -> str:
    """Alphanumeric core of a model name — the comparison unit for attribution
    ('opus-4.8' / 'claude-opus-4-8' / 'Opus 4.8' all share 'opus48' cores)."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def flag_mismatch(model_slug: str,
                  models_used: Optional[Sequence[str]],
                  envelope_flag: bool = False) -> Tuple[bool, Optional[str]]:
    """Conservative models_used attribution check -> (mismatch, reason).

    The envelope's own model_mismatch flag wins outright (aura-product computes
    it from the thread's usage_events ledger — strictly better evidence than
    any name heuristic). Baseline heuristic, deliberately conservative:
      * absent/empty models_used is NOT a mismatch — `agent.models_used` only
        exists on 2026-07-22+ envelopes, so absence means "unattributed";
      * a pinned slug (`claude-p:opus`, `openrouter:openai/gpt-4o-mini`) flags
        only when NO models_used entry shares the pin's alphanumeric core;
      * a bare slug (`claude-p`) with a non-empty models_used is annotated
        "session-default", never flagged — the doctrine is trust models_used
        over the label, not punish the label."""
    if envelope_flag:
        return True, "envelope model_mismatch flag (thread usage ledger)"
    used = [str(m) for m in (models_used or []) if m]
    if not used:
        return False, None
    _, _, pin = (model_slug or "").partition(":")
    pin = pin.rpartition("/")[2]        # openrouter:<provider>/<model> -> <model>
    core = _norm_model(pin)
    if not core:
        return False, "session-default (unpinned slug)"
    for m in used:
        m_core = _norm_model(m)
        if core in m_core or m_core in core:
            return False, None
    return True, f"pinned '{pin}' not among models_used {used}"


#: Verdict for a rep whose turn was submitted into a conversation that ANOTHER
#: run already used. Non-graded by omission from ``adapters/base.GRADED_VERDICTS``
#: (the allowlist), exactly like STACK-DOWN / MODEL-MISMATCH.
VERDICT_THREAD_REUSED = "THREAD-REUSED"


def flag_thread_reuse(results: Sequence[RepResult],
                      known_threads: Optional[Dict[str, str]] = None) -> int:
    """Assert every rep ran in its OWN conversation; demote the ones that did not.

    Returns the number of reps demoted. Mutates them in place: the graded
    verdict moves to ``underlying_verdict`` and the rep becomes
    ``THREAD-REUSED`` (non-graded), so it can never land in a pass-rate.

    THE BUG THIS EXISTS FOR (measured 2026-08-10, 159 recorded product runs):
    thread ``4bf9bfa4-…`` was used by NINE separate runs across two days, two
    tasks and two models. Four reps of one bench were the same conversation
    continued four times: reps 1-3 called 24, 6 and 3 tools and were all scored
    PASS — rep 3 authored a working GAS ability having READ NOTHING — and rep 4
    ended GRADE-SPAWN-DIED. A "5 back-to-back reps" pass rate measured one
    conversation with N turns, and the per-thread cost ledger (``cost_thread``)
    is CUMULATIVE over that thread, so the reps' costs also rose monotonically
    for no reason the agent did.

    Across all nine the verdicts were 5 PASS / 2 FAIL / 1 GRADE-SPAWN-DIED (one
    run wrote no summary.json). Worth stating precisely rather than as "they all
    passed": contamination manufactured false FAILs too — ``opus-5`` at
    2026-08-09 19:58 and ``grok-4.5`` at 2026-08-10 16:43 — so this is not only
    a score-inflation bug, which is what
    ``test_a_fail_on_a_reused_thread_is_demoted_too`` pins.

    The FIRST rep on a given thread is left alone deliberately: it is the run
    that legitimately opened the conversation (the 2026-08-09 02:07 run did,
    and it is the one of the nine with a clean submit). Only the runs that
    landed on someone else's thread are demoted.

    ``known_threads`` maps thread id -> a human label for threads used by runs
    OUTSIDE this bench (earlier benches on the same box). It is what catches the
    case an in-bench uniqueness check structurally CANNOT: a bench whose very
    first rep lands on a thread a previous bench created has no in-bench
    duplicate to compare against, and four of the nine measured runs were
    exactly that. Callers that cannot supply it get the weaker check, not a
    silent pass.

    Reps with no recorded thread id are skipped rather than grouped: ``None`` is
    "the harness did not observe one" (a drive that died before any POST), not
    "the same conversation as the other unobserved reps".
    """
    seen: Dict[str, str] = dict(known_threads or {})
    demoted = 0
    for r in results:
        tid = r.thread_id
        if not tid:
            continue
        owner = seen.get(tid)
        if owner is None:
            seen[tid] = f"{r.model} :: {r.task_id} rep {r.rep}"
            continue
        if r.thread_reused_from is None:
            r.thread_reused_from = owner
        if is_graded_verdict(r.verdict):
            r.underlying_verdict = r.verdict
            r.verdict = VERDICT_THREAD_REUSED
            demoted += 1
    return demoted


def _provenance_warnings(results: Sequence[RepResult]) -> List[str]:
    """A comparison spanning >1 substrate revision / prompt preamble is suspect
    — the graded substrate or the agent-facing prompt changed mid-bench (cross-
    epoch numbers are not comparable; see the preamble_sha boundary rule)."""
    warns: List[str] = []
    for attr, label in (("substrate_revision", "substrate revision(s)"),
                        ("preamble_sha", "preamble SHA(s)")):
        vals = sorted({getattr(r, attr) for r in results if getattr(r, attr)})
        if len(vals) > 1:
            warns.append(f"reps span {len(vals)} {label}: "
                         + ", ".join(str(v)[:12] for v in vals))
    # Rep INDEPENDENCE is a provenance property too, and a louder one: a reused
    # thread means the reps were turns of one conversation, so every spread
    # statistic below is describing a single sample.
    for r in results:
        if r.thread_reused_from:
            warns.append(
                f"{r.model} :: {r.task_id} rep {r.rep} ran in the conversation "
                f"already used by {r.thread_reused_from} (thread {r.thread_id}) "
                f"— NOT an independent rep")
    return warns


def aggregate(results: Sequence[RepResult],
              models: Sequence[str],
              task_specs: Sequence[Tuple[str, int]],
              meta: Optional[dict] = None) -> dict:
    """Roll rep results into a JSON-serialisable report: per-(model, task)
    verdict counts + graded-only pass-rate + cost/agent/verify spread, plus a
    per-model cost/time rollup. Partial by design — called after every rep."""
    by_pair: Dict[str, dict] = {}
    for m in models:
        for (t, n) in task_specs:
            reps = [r for r in results if r.model == m and r.task_id == t]
            verdicts = [r.verdict for r in reps]
            graded = [v for v in verdicts if is_graded_verdict(v)]
            by_pair[f"{m} :: {t}"] = {
                "model": m,
                "task_id": t,
                "reps_planned": n,
                "reps_done": len(reps),
                "pass": sum(1 for v in verdicts if v == VERDICT_PASS),
                "fail": sum(1 for v in graded if v != VERDICT_PASS),
                "non_graded": sum(1 for r in reps
                                  if r.error is None and not is_graded_verdict(r.verdict)),
                "errors": sum(1 for r in reps if r.error is not None),
                "graded_n": len(graded),
                "pass_rate": pass_rate(verdicts),
                "mismatches": sum(1 for r in reps if r.models_mismatch),
                "cost_usd": _stats([r.cost_usd for r in reps]),
                "agent_s": _stats([r.agent_s for r in reps]),
                "verify_s": _stats([r.verify_s for r in reps]),
            }
    by_model: Dict[str, dict] = {}
    for m in models:
        reps = [r for r in results if r.model == m]
        by_model[m] = {
            "reps_done": len(reps),
            "pass": sum(1 for r in reps if r.verdict == VERDICT_PASS),
            "graded_n": sum(1 for r in reps if is_graded_verdict(r.verdict)),
            "pass_rate": pass_rate([r.verdict for r in reps]),
            "mismatches": sum(1 for r in reps if r.models_mismatch),
            "cost_usd": _stats([r.cost_usd for r in reps]),
            "agent_s": _stats([r.agent_s for r in reps]),
            "verify_s": _stats([r.verify_s for r in reps]),
        }
    return {
        "models": list(models),
        "task_specs": [{"task_id": t, "reps": n} for (t, n) in task_specs],
        "meta": dict(meta or {}),
        "provenance_warnings": _provenance_warnings(results),
        "by_pair": by_pair,
        "by_model": by_model,
        "reps": [
            {
                "model": r.model, "task_id": r.task_id, "rep": r.rep,
                "verdict": r.verdict, "cost_usd": r.cost_usd,
                "agent_s": r.agent_s, "verify_s": r.verify_s,
                "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                "num_turns": r.num_turns, "tool_use_count": r.tool_use_count,
                "tool_names": r.tool_names,
                "run_dir": r.run_dir, "error": r.error,
                "models_used": r.models_used,
                "models_mismatch": r.models_mismatch,
                "mismatch_reason": r.mismatch_reason,
                "underlying_verdict": r.underlying_verdict,
                "substrate_revision": r.substrate_revision,
                "preamble_sha": r.preamble_sha,
                "report_href": r.report_href,
                "posthog_url": r.posthog_url,
                "thread_id": r.thread_id,
                "thread_reused_from": r.thread_reused_from,
            }
            for r in results
        ],
    }


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

def _spread(s: Optional[dict], fmt: str, unit: str = "") -> str:
    if s is None:
        return "n/a"
    if s["n"] == 1:
        return f"{s['mean']:{fmt}}{unit}"
    return (f"{s['mean']:{fmt}}{unit} "
            f"({s['min']:{fmt}}–{s['max']:{fmt}})")


def render_markdown(agg: dict) -> str:
    """Per-(model, task) stats table + a model x task comparison grid + a
    per-rep detail table."""
    lines: List[str] = ["## CraftBench bench report"]
    meta = agg.get("meta") or {}
    prov = "  ·  ".join(f"{k}: {v}" for k, v in meta.items())
    if prov:
        lines += ["", f"_{prov}_"]
    for w in agg.get("provenance_warnings") or []:
        lines += ["", f"> ⚠ {w}"]
    lines += [
        "",
        "| Model | Task | Pass | MM | Cost mean (min–max) | Agent s | Verify s | Total $ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in agg["by_pair"].values():
        cost, agent, verify = row["cost_usd"], row["agent_s"], row["verify_s"]
        total = "n/a" if cost is None else f"${cost['total']:.3f}"
        lines.append(
            f"| `{row['model']}` | `{row['task_id']}` "
            f"| {row['pass']}/{row['graded_n']} ({_pct(row['pass_rate'])}) "
            f"| {row.get('mismatches', 0)} "
            f"| {_spread(cost, '.3f') if cost else 'n/a'} "
            f"| {_spread(agent, '.0f')} | {_spread(verify, '.0f')} "
            f"| {total} |"
        )
    task_ids = [t["task_id"] for t in agg["task_specs"]]
    cell_reps: Dict[tuple, list] = {}
    for r in agg["reps"]:
        cell_reps.setdefault((r["model"], r["task_id"]), []).append(r)
    lines += ["", "### Model × task grid", "",
              "| Model | " + " | ".join(f"`{t}`" for t in task_ids) + " |",
              "|" + "---|" * (len(task_ids) + 1)]
    for m in agg["models"]:
        row_cells = [f"`{m}`"]
        for t in task_ids:
            toks = []
            for r in sorted(cell_reps.get((m, t), []), key=lambda r: r["rep"]):
                label = (r["verdict"] or "ERR") + ("!" if r.get("models_mismatch") else "")
                toks.append(f"[{label}]({r['report_href']})"
                            if r.get("report_href") else label)
            row_cells.append(" · ".join(toks) or "—")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines += ["", "_Grid: one entry per rep (`!` = models_used mismatch; links "
                  "open the rep's report.html). Pass-rates use the graded-only "
                  "denominator — aborted ≠ failed._"]
    lines += ["", "### Per-rep detail", "",
              "| Model | Task | Rep | Verdict | Cost | Agent s | Verify s | Turns | Tools | Trace |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in agg["reps"]:
        cost = "n/a" if r["cost_usd"] is None else f"${r['cost_usd']:.4f}"
        agent = "n/a" if r["agent_s"] is None else f"{r['agent_s']:.0f}"
        verify = "n/a" if r["verify_s"] is None else f"{r['verify_s']:.0f}"
        verdict = r["verdict"] or f"ERR ({r['error']})"
        if r.get("models_mismatch"):
            verdict += " !"
        tools = "n/a"
        if r.get("tool_use_count") is not None:
            tools = str(r["tool_use_count"])
            if r.get("tool_names"):
                mix = Counter(r["tool_names"])
                tools += " (" + ", ".join(f"{k}×{v}" for k, v in mix.most_common()) + ")"
        trace = (f"[trace]({r['posthog_url']})" if r.get("posthog_url") else "—")
        lines.append(f"| `{r['model']}` | `{r['task_id']}` | {r['rep']} "
                     f"| {verdict} | {cost} | {agent} | {verify} "
                     f"| {r['num_turns'] if r['num_turns'] is not None else 'n/a'} "
                     f"| {tools} | {trace} |")
    return "\n".join(lines)


def render_html(agg: dict, title: str = "CraftBench bench leaderboard") -> str:
    """The model-comparison leaderboard: a standings table + a {model} x {task}
    grid where every rep is a verdict badge linked to its run's report.html
    (when the harvest recorded one; plain span otherwise). Self-contained
    (inline CSS, matrix.render_html's visual template) and rewritten after
    every rep, so a crashed bench still leaves a readable grid."""
    models = agg["models"]
    task_ids = [t["task_id"] for t in agg["task_specs"]]
    e = _html.escape

    def _key(m):
        s = agg["by_model"][m]
        r = s["pass_rate"]
        cost = (s["cost_usd"] or {}).get("total") or 0.0
        return (-(r if r is not None else -1), cost)

    rows_summary = []
    for m in sorted(models, key=_key):
        s = agg["by_model"][m]
        cost = s["cost_usd"]
        cost_txt = ("n/a" if cost is None
                    else f"${cost['total']:.2f} (mean ${cost['mean']:.3f})")
        ag = s["agent_s"]
        ag_txt = "n/a" if ag is None else f"{ag['mean']:.0f}s"
        rows_summary.append(
            f"<tr><td class='mono'>{e(m)}</td><td class='num'>{_pct(s['pass_rate'])}</td>"
            f"<td class='num'>{s['pass']}/{s['graded_n']}</td>"
            f"<td class='num'>{s['reps_done']}</td>"
            f"<td class='num'>{s.get('mismatches', 0)}</td>"
            f"<td class='num'>{cost_txt}</td><td class='num'>{ag_txt}</td></tr>")

    cell_reps: Dict[tuple, list] = {}
    for r in agg["reps"]:
        cell_reps.setdefault((r["model"], r["task_id"]), []).append(r)

    def _badge(r: dict) -> str:
        label = r["verdict"] or "ERR"
        css = _VERDICT_CSS.get(label, "background:#fde68a;color:#92400e")
        tip_bits = [f"rep {r['rep']}", label]
        if r.get("cost_usd") is not None:
            tip_bits.append(f"${r['cost_usd']:.4f}")
        if r.get("run_dir"):
            tip_bits.append(Path(r["run_dir"]).name)
        if r.get("mismatch_reason"):
            tip_bits.append(str(r["mismatch_reason"]))
        if r.get("error"):
            tip_bits.append(str(r["error"]))
        tip = e(" · ".join(tip_bits))
        mm = "<sup class='mm'>MM</sup>" if r.get("models_mismatch") else ""
        body = f"{e(label)}{mm}"
        # Companion chip: the rep's PostHog LLM-analytics trace (aura-product
        # runs stamp posthog_url in summary.json) — sits NEXT to the badge so
        # the badge itself keeps opening report.html.
        ph = ""
        if r.get("posthog_url"):
            ph = (f"<a class='ph' href='{e(str(r['posthog_url']))}' "
                  f"title='PostHog LLM trace (rep {r['rep']})'>ph</a>")
        if r.get("report_href"):
            return (f"<a class='badge' style='{css}' href='{e(str(r['report_href']))}' "
                    f"title='{tip}'>{body}</a>{ph}")
        return f"<span class='badge' style='{css}' title='{tip}'>{body}</span>{ph}"

    grid_head = "".join(f"<th>{e(t)}</th>" for t in task_ids)
    grid_rows = []
    for m in models:
        tds = []
        for t in task_ids:
            reps = sorted(cell_reps.get((m, t), []), key=lambda r: r["rep"])
            tds.append("<td class='cell'>"
                       + (" ".join(_badge(r) for r in reps) or "—") + "</td>")
        grid_rows.append(f"<tr><td class='mono'>{e(m)}</td>{''.join(tds)}</tr>")

    meta = agg.get("meta") or {}
    prov = "  ·  ".join(f"{k}: {v}" for k, v in meta.items())
    warns = "".join(f"<p class='warn'>⚠ {e(w)}</p>"
                    for w in agg.get("provenance_warnings") or [])
    n_reps = len(agg["reps"])
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>
  body {{ font: 14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; margin: 2rem; color:#111; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
  .sub {{ color:#6b7280; margin: 0 0 1.5rem; }}
  table {{ border-collapse: collapse; margin: 0 0 2rem; }}
  th,td {{ border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; }}
  th {{ background:#f3f4f6; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .mono {{ font-family: ui-monospace,Menlo,Consolas,monospace; }}
  .cell {{ text-align:center; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:3px; font-weight:600;
            font-size:12px; text-decoration:none; margin:1px; }}
  a.badge:hover {{ outline:2px solid #111; }}
  .mm {{ color:#fde68a; font-weight:700; margin-left:2px; }}
  .ph {{ font-size:10px; vertical-align:super; margin-left:1px; color:#2563eb;
         text-decoration:none; }}
  a.ph:hover {{ text-decoration:underline; }}
  .warn {{ background:#fef3c7; color:#92400e; padding:6px 10px; border-radius:4px; }}
  .legend span {{ display:inline-block; padding:2px 8px; border-radius:3px; margin-right:8px; font-size:12px; }}
  .foot {{ color:#6b7280; font-size:12px; }}
  .scroll {{ overflow-x:auto; }}
</style></head><body>
<h1>{e(title)}</h1>
<p class="sub">{len(models)} model(s) &times; {len(task_ids)} task(s), {n_reps} rep(s).{(' &middot; ' + e(prov)) if prov else ''}</p>
{warns}
<h2 style="font-size:1.1rem">Standings</h2>
<div class="scroll"><table>
  <tr><th>Model</th><th>Pass-rate</th><th>Pass/Graded</th><th>Reps</th><th>Mismatch</th><th>Cost</th><th>Agent mean</th></tr>
  {''.join(rows_summary)}
</table></div>
<h2 style="font-size:1.1rem">Model &times; task grid</h2>
<p class="legend"><span style="background:#1a7f37;color:#fff">PASS</span><span style="background:#b91c1c;color:#fff">FAIL</span><span style="background:#6b7280;color:#fff">ERR (harness)</span><span style="background:#fde68a;color:#92400e">non-graded</span> &middot; one badge per rep; click a badge for that run's report.html; <b>MM</b> = models_used mismatch; <b>ph</b> = PostHog LLM trace</p>
<div class="scroll"><table>
  <tr><th>Model</th>{grid_head}</tr>
  {''.join(grid_rows)}
</table></div>
<p class="foot">Pass-rate excludes non-graded reps (substrate-reject, MODEL-MISMATCH, CONTEXT-CONTAMINATED, THREAD-REUSED, harness errors) — aborted &ne; failed. A sandbox-reject, empty submission or missing deliverable COUNTS, as a non-pass: those are model outcomes, and excluding them biases the rate upward. Cost semantics differ by backend: aura-product = thread-scoped est_cost_usd; baseline = agent.cost_usd — comparable, not identical. A THREAD-REUSED rep's cost is also a CUMULATIVE thread ledger, not this rep's spend.</p>
</body></html>"""


def _write_atomic(path: Path, text: str) -> None:
    """tmp + os.replace (the batch_eval.py pattern) — a crash mid-rewrite must
    never truncate the incrementally-persisted report."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# Orchestration (sequential; rep runner injected)                              #
# --------------------------------------------------------------------------- #

def run(models: Sequence[str],
        task_specs: Sequence[Tuple[str, int]],
        run_one_rep: Callable[[Rep], RepResult],
        out_dir: Path,
        log: Callable[[str], None] = print,
        meta: Optional[dict] = None,
        pause: Callable[[], None] = lambda: time.sleep(1.2),
        prior: Optional[Sequence[RepResult]] = None,
        model_groups: Optional[Sequence[Sequence[str]]] = None,
        known_threads: Optional[Dict[str, str]] = None) -> dict:
    """Run every rep SEQUENTIALLY, persisting bench.{json,md} +
    leaderboard.html after each one.

    Sequential by design (each rep is a full UE build + PIE). ``pause`` runs
    between consecutive RUN reps so run.py's 1-second run_id can never collide
    even when a rep fails instantly. A runner exception becomes an ERROR rep —
    the bench never aborts midway and loses the reps already measured.

    ``prior`` (resume): reuse any prior rep that produced a GRADED verdict
    (PASS/FAIL) keyed on (model, task_id, rep); re-run everything else (harness
    errors, non-graded codes) so a resumed bench only re-spends on reps that
    never yielded a clean measurement. Resumed reps consume no pause (they don't
    invoke run.py).

    ``model_groups``: ordered execution phases forwarded to build_reps (rep
    IDENTITY stays (model, task_id, rep) — grouping changes only the order, so
    a bench resumed under a different grouping still matches its reps).

    ``known_threads``: thread id -> label, for conversations used by runs from
    BEFORE this bench. Forwarded to :func:`flag_thread_reuse`, which runs after
    every rep so a broken-independence bench says so on the rep that broke it
    rather than at the end (see that function for what it is guarding)."""
    reps = build_reps(models, task_specs, model_groups=model_groups)
    results: List[RepResult] = []
    init_deaths = 0  # CONSECUTIVE 0xC0000142-shaped errors (spawn_health)
    done = {(r.model, r.task_id, r.rep): r
            for r in (prior or []) if is_graded_verdict(r.verdict)}
    out_dir.mkdir(parents=True, exist_ok=True)
    ran_any = False
    for i, rep in enumerate(reps, 1):
        label = (f"[{i}/{len(reps)}] {rep.model} :: {rep.task_id}  "
                 f"(rep {rep.rep}/{rep.n_reps})")
        cached = done.get((rep.model, rep.task_id, rep.rep))
        if cached is not None:
            log(label + f"  -> RESUMED {cached.verdict}")
            results.append(cached)
        else:
            if ran_any:
                pause()
            log(label)
            try:
                res = run_one_rep(rep)
            except Exception as exc:      # never lose prior reps to one bad runner
                res = RepResult(rep.model, rep.task_id, rep.rep,
                                verdict=None, error=repr(exc))
            ran_any = True
            results.append(res)
            bits = [res.verdict or "ERROR"]
            if res.cost_usd is not None:
                bits.append(f"${res.cost_usd:.4f}")
            if res.agent_s is not None:
                bits.append(f"agent {res.agent_s:.0f}s")
            if res.verify_s is not None:
                bits.append(f"verify {res.verify_s:.0f}s")
            if res.error:
                bits.append(f"({res.error})")
            log(f"    -> {'  '.join(bits)}")
        # REP INDEPENDENCE, checked before the aggregate is written so a
        # contaminated rep can never appear in a persisted pass-rate even for
        # the seconds between two reps. Runs over ALL results each time (cheap,
        # and a resumed rep's thread counts as taken too).
        if flag_thread_reuse(results, known_threads):
            bad = results[-1]
            log(f"    !! {VERDICT_THREAD_REUSED} — this rep ran in the "
                f"conversation already used by {bad.thread_reused_from} "
                f"(thread {bad.thread_id}). It is a LATER TURN of that "
                f"conversation, not an independent rep: it inherits the prior "
                f"turns' context and its thread cost ledger is cumulative. "
                f"Graded verdict {bad.underlying_verdict} is preserved in the "
                f"run dir but the rep is NON-GRADED here.")
        agg = aggregate(results, models, task_specs, meta=meta)
        _write_atomic(out_dir / "bench.json", json.dumps(agg, indent=2))
        _write_atomic(out_dir / "bench.md", render_markdown(agg))
        _write_atomic(out_dir / "leaderboard.html", render_html(agg))

        # 0xC0000142 CIRCUIT BREAKER (build machine, 2026-08-07): spawn poisoning is
        # BOX-STATE — once two consecutive reps die of DLL-init failure,
        # every further rep is another minute of bring-up churn that learns
        # nothing (measured: 8+ ERR reps cycled at $0; even taskkill dies
        # poisoned, so the rig cannot even clean up). Abort the bench with a
        # NAMED machine fault, snapshot the box SPAWN-FREE while it is still
        # poisoned (the numbers that distinguish desktop-heap exhaustion vs
        # commit-during-DLL-load vs AV injection), and leave the aggregate on
        # disk — `cb bench --resume` picks up once the box is healed.
        # Cached/resumed reps never count: they spawned nothing this run.
        if cached is None:
            from . import spawn_health
            if spawn_health.looks_like_init_death(getattr(res, "error", None)):
                init_deaths += 1
            else:
                init_deaths = 0
            if init_deaths >= spawn_health.BREAKER_THRESHOLD:
                log("")
                log("=" * 70)
                log(f"MACHINE FAULT: {init_deaths} consecutive reps died of "
                    f"STATUS_DLL_INIT_FAILED (0xC0000142) - spawn poisoning "
                    f"is box-state; retries cannot beat it. ABORTING: "
                    f"{len(reps) - i} rep(s) not attempted.")
                snap = spawn_health.snapshot(
                    out_dir.parent, trigger=str(getattr(res, "error", ""))[:200])
                if snap:
                    log(f"forensics -> runs/{spawn_health.SNAPSHOT_FILE}  "
                        f"(commit_free={snap.get('commit_free_gb')}GB, "
                        f"procs={snap.get('process_count')}, "
                        f"gui_user={snap.get('gui_user_objects_total')})")
                log("Heal the box (drain processes / reboot), then "
                    "`cb bench --resume` - graded reps are reused.")
                log("=" * 70)
                break
    return aggregate(results, models, task_specs, meta=meta)
