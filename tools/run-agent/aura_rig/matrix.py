"""cb matrix — run a {model} x {task} cross product and aggregate a leaderboard.

The `--model` slug already encodes the backend (`claude-p:opus`,
`openrouter:openai/gpt-4o-mini`), so a comma-separated model list spans BOTH
models and harnesses in one matrix. Each cell shells the generalist baseline
runner (`run.py`) into its own per-cell `--run-dir`, then this module reads the
cell's `result.json` and rolls the cells up into a leaderboard.

v1 supports the BASELINE backends (`claude-p`, `openrouter`) — they need no Aura
stack and grade through the deterministic verifier. aura-* slugs are reported as
unsupported by the caller (use `cb eval`).

The pass-rate reuses `adapters.base.pass_rate`, so non-graded verdicts
(SUBSTRATE-REJECT / SANDBOX-REJECT / harness errors) are EXCLUDED from the
denominator exactly as everywhere else in the harness — a model is never
silently penalised for a verifier-noise / infra cell.

Design seam: `run_one_cell` is injected into :func:`run`, so the orchestration
loop is unit-testable without UE (tests pass a fake runner).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from adapters.base import VERDICT_PASS, is_graded_verdict, pass_rate


# --------------------------------------------------------------------------- #
# Pure data + helpers                                                          #
# --------------------------------------------------------------------------- #

@dataclass
class Cell:
    model: str
    task_id: str


@dataclass
class CellResult:
    model: str
    task_id: str
    verdict: Optional[str]          # PASS / FAIL / a non-graded code, or None on harness error
    cost_usd: Optional[float] = None
    duration_s: Optional[float] = None
    tool_use_count: Optional[int] = None
    error: Optional[str] = None     # harness-level failure (no verdict produced)


def parse_models(spec: str) -> List[str]:
    """Split a comma-separated `--model` list, trim, drop blanks, dedupe (order-preserving)."""
    seen: set = set()
    out: List[str] = []
    for m in (x.strip() for x in (spec or "").split(",")):
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def build_cells(models: Sequence[str], task_ids: Sequence[str]) -> List[Cell]:
    """The {model} x {task} cross product, models-major (stable order)."""
    return [Cell(m, t) for m in models for t in task_ids]


def safe_name(s: str) -> str:
    """Filesystem-safe slug for a per-cell run dir (mirrors run.py's model_slug_safe)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-") or "x"


def aggregate(results: Sequence[CellResult],
              models: Sequence[str],
              task_ids: Sequence[str],
              meta: Optional[dict] = None) -> dict:
    """Roll cell results into a JSON-serialisable leaderboard structure.

    Per-model: graded-only pass-rate (None if nothing graded), pass/fail/
    non-graded/error counts, and summed cost/duration over the model's cells.
    ``meta`` (e.g. {"ue_root": ..., "generated_at": ...}) is recorded verbatim
    so the leaderboard self-documents the engine it ran against — fair
    comparison is meaningless without pinning the UE version.
    """
    by_model: Dict[str, dict] = {}
    for m in models:
        cells = [r for r in results if r.model == m]
        verdicts = [r.verdict for r in cells]
        graded = [v for v in verdicts if is_graded_verdict(v)]
        costs = [r.cost_usd for r in cells if r.cost_usd is not None]
        durs = [r.duration_s for r in cells if r.duration_s is not None]
        by_model[m] = {
            "pass": sum(1 for v in verdicts if v == VERDICT_PASS),
            "fail": sum(1 for v in graded if v != VERDICT_PASS),
            "non_graded": sum(1 for r in cells
                              if r.error is None and not is_graded_verdict(r.verdict)),
            "errors": sum(1 for r in cells if r.error is not None),
            "graded_n": len(graded),
            "total_n": len(cells),
            "pass_rate": pass_rate(verdicts),          # None => no graded sample
            "total_cost_usd": round(sum(costs), 4) if costs else None,
            "total_duration_s": round(sum(durs), 1) if durs else None,
        }
    cells_out = [
        {
            "model": r.model, "task_id": r.task_id, "verdict": r.verdict,
            "cost_usd": r.cost_usd, "duration_s": r.duration_s,
            "tool_use_count": r.tool_use_count, "error": r.error,
        }
        for r in results
    ]
    return {
        "models": list(models),
        "task_ids": list(task_ids),
        "meta": dict(meta or {}),
        "by_model": by_model,
        "cells": cells_out,
    }


def _meta_line(agg: dict) -> str:
    """One-line provenance from agg['meta'] (UE root + generation time)."""
    meta = agg.get("meta") or {}
    bits = []
    if meta.get("ue_root"):
        bits.append(f"UE: {meta['ue_root']}")
    if meta.get("generated_at"):
        bits.append(f"generated {meta['generated_at']}")
    return "  ·  ".join(bits)


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

def _pct(rate: Optional[float]) -> str:
    return "n/a" if rate is None else f"{rate * 100:.0f}%"


def _cell_label(verdict: Optional[str], error: Optional[str]) -> str:
    if error is not None:
        return "ERR"
    if verdict is None:
        return "—"
    return verdict


def render_markdown(agg: dict) -> str:
    """A compact leaderboard: a per-model summary table + a per-task PASS/FAIL grid."""
    models = agg["models"]
    task_ids = agg["task_ids"]
    grid = {(c["model"], c["task_id"]): c for c in agg["cells"]}

    lines: List[str] = []
    lines.append("## CraftBench matrix leaderboard")
    prov = _meta_line(agg)
    if prov:
        lines.append("")
        lines.append(f"_{prov}_")
    lines.append("")
    lines.append("| Model | Pass-rate | Pass/Graded | Non-graded | Err | Cost |")
    lines.append("|---|---|---|---|---|---|")
    # sort by pass-rate desc (None last), then cost asc
    def _key(m):
        r = agg["by_model"][m]["pass_rate"]
        return (-(r if r is not None else -1), agg["by_model"][m]["total_cost_usd"] or 0.0)
    for m in sorted(models, key=_key):
        s = agg["by_model"][m]
        cost = "n/a" if s["total_cost_usd"] is None else f"${s['total_cost_usd']:.2f}"
        lines.append(f"| `{m}` | {_pct(s['pass_rate'])} | {s['pass']}/{s['graded_n']} | "
                     f"{s['non_graded']} | {s['errors']} | {cost} |")

    lines.append("")
    lines.append("### Per-task grid")
    lines.append("")
    header = "| Model | " + " | ".join(task_ids) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(task_ids) + 1))
    for m in models:
        row = [f"`{m}`"]
        for t in task_ids:
            c = grid.get((m, t))
            row.append(_cell_label(c["verdict"] if c else None, c["error"] if c else None))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


_VERDICT_CSS = {
    "PASS": "background:#1a7f37;color:#fff",
    "FAIL": "background:#b91c1c;color:#fff",
    "ERR": "background:#6b7280;color:#fff",
    "—": "background:#e5e7eb;color:#6b7280",
}


def render_html(agg: dict, title: str = "CraftBench matrix leaderboard") -> str:
    """A self-contained leaderboard page (inline CSS, no external assets)."""
    models = agg["models"]
    task_ids = agg["task_ids"]
    grid = {(c["model"], c["task_id"]): c for c in agg["cells"]}
    e = html.escape

    def _key(m):
        r = agg["by_model"][m]["pass_rate"]
        return (-(r if r is not None else -1), agg["by_model"][m]["total_cost_usd"] or 0.0)

    rows_summary = []
    for m in sorted(models, key=_key):
        s = agg["by_model"][m]
        cost = "n/a" if s["total_cost_usd"] is None else f"${s['total_cost_usd']:.2f}"
        dur = "n/a" if s["total_duration_s"] is None else f"{s['total_duration_s']:.0f}s"
        rows_summary.append(
            f"<tr><td class='mono'>{e(m)}</td><td class='num'>{_pct(s['pass_rate'])}</td>"
            f"<td class='num'>{s['pass']}/{s['graded_n']}</td><td class='num'>{s['non_graded']}</td>"
            f"<td class='num'>{s['errors']}</td><td class='num'>{cost}</td><td class='num'>{dur}</td></tr>"
        )

    grid_head = "".join(f"<th>{e(t)}</th>" for t in task_ids)
    grid_rows = []
    for m in models:
        tds = []
        for t in task_ids:
            c = grid.get((m, t))
            label = _cell_label(c["verdict"] if c else None, c["error"] if c else None)
            css = _VERDICT_CSS.get(label, "background:#fde68a;color:#92400e")
            tip = ""
            if c and c.get("error"):
                tip = f" title='{e(str(c['error']))}'"
            elif c and label not in ("PASS", "FAIL", "—"):
                tip = f" title='{e(str(c['verdict']))}'"
            tds.append(f"<td class='cell' style='{css}'{tip}>{e(label)}</td>")
        grid_rows.append(f"<tr><td class='mono'>{e(m)}</td>{''.join(tds)}</tr>")

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
  .cell {{ text-align:center; font-weight:600; }}
  .legend span {{ display:inline-block; padding:2px 8px; border-radius:3px; margin-right:8px; font-size:12px; }}
  .scroll {{ overflow-x:auto; }}
</style></head><body>
<h1>{e(title)}</h1>
<p class="sub">{len(models)} model(s) &times; {len(task_ids)} task(s) = {len(models)*len(task_ids)} cell(s). Pass-rate excludes non-graded (substrate-reject, harness errors); a sandbox-reject or empty submission COUNTS, as a non-pass.{(' &middot; ' + e(_meta_line(agg))) if _meta_line(agg) else ''}</p>
<h2 style="font-size:1.1rem">Standings</h2>
<div class="scroll"><table>
  <tr><th>Model</th><th>Pass-rate</th><th>Pass/Graded</th><th>Non-graded</th><th>Err</th><th>Cost</th><th>Duration</th></tr>
  {''.join(rows_summary)}
</table></div>
<h2 style="font-size:1.1rem">Per-task grid</h2>
<p class="legend"><span style="background:#1a7f37;color:#fff">PASS</span><span style="background:#b91c1c;color:#fff">FAIL</span><span style="background:#6b7280;color:#fff">ERR (harness)</span><span style="background:#fde68a;color:#92400e">non-graded</span></p>
<div class="scroll"><table>
  <tr><th>Model</th>{grid_head}</tr>
  {''.join(grid_rows)}
</table></div>
</body></html>"""


# --------------------------------------------------------------------------- #
# Orchestration (sequential; cell runner injected)                            #
# --------------------------------------------------------------------------- #

def run(models: Sequence[str],
        task_ids: Sequence[str],
        run_one_cell: Callable[[Cell], CellResult],
        out_dir: Path,
        log: Callable[[str], None] = print,
        meta: Optional[dict] = None) -> dict:
    """Run every cell SEQUENTIALLY via ``run_one_cell`` and write the leaderboard.

    Sequential by design: each cell is a full UE build + PIE; running them
    concurrently thrashes the machine and races the substrate-integrity
    preflight. Writes leaderboard.{json,md,html} into ``out_dir`` and returns
    the aggregate dict. A cell whose runner raises becomes an ERROR cell (the
    matrix never aborts midway and loses the cells already run)."""
    cells = build_cells(models, task_ids)
    results: List[CellResult] = []
    for i, cell in enumerate(cells, 1):
        log(f"[{i}/{len(cells)}] {cell.model} :: {cell.task_id}")
        try:
            res = run_one_cell(cell)
        except Exception as exc:  # never lose prior cells to one bad runner
            res = CellResult(cell.model, cell.task_id, verdict=None, error=repr(exc))
        results.append(res)
        bits = [res.verdict or "ERROR"]
        if res.cost_usd is not None:
            bits.append(f"${res.cost_usd:.4f}")
        if res.duration_s is not None:
            bits.append(f"{res.duration_s:.0f}s")
        if res.error:
            bits.append(f"({res.error})")
        log(f"    -> {'  '.join(bits)}")

    agg = aggregate(results, models, task_ids, meta=meta)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    (out_dir / "leaderboard.md").write_text(render_markdown(agg), encoding="utf-8")
    (out_dir / "leaderboard.html").write_text(render_html(agg), encoding="utf-8")
    return agg
