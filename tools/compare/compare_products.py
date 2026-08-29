"""Cross-product comparison — aggregate run-agent result.json into the taxonomy verdict.

CraftBench's point is to run the SAME scrubbed tasks across multiple PRODUCTS
(aura-mcp:<model>, claude-p:<model>, official-UE-MCP, …) and answer "which product
is strong at what." This consumes the per-run result.json the harness emits
(tools/run-agent/run.py) — one per product × task — and produces the SC-003
headline: **per-capability-bucket pass-rate per product**, plus each product's
strong / weak capabilities.

Gate-driven: the deterministic ``overall`` (PASS/FAIL) is what scores a run. The
R2 advisory (``verifier.r2_advisory.advisory_score``) is reported ALONGSIDE but is
NEVER folded into the pass-rate — FR-020d (the judge never gates). Per-capability
normalization avoids the "one product wins because it's good at the oversampled
bucket" trap the leaderboard schema warns about.

Pure stdlib, no UE, no network — runs on result.json files alone.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parents[2]
_CAP_RE = re.compile(r"^\s*-\s*capability_bucket\s*:\s*(?P<cap>.+?)\s*$", re.MULTILINE)
_UNCATEGORIZED = "uncategorized"

# "Which task is this run?" has exactly ONE implementation, in tools/runlib --
# imported, never copied. This file's own answer used to be ``Path(task).stem``,
# which on the real corpus (87 records carrying a path, 2026-08-19) returned the
# literal string "task" for every single one, because every recorded path ends
# in ``.../<id>/task.md``. One product's whole run set became one task cell.
# run_identity.py is stdlib-only, so the "stdlib-only, importable from a bare
# checkout" property of this tool is preserved.
_RUNLIB = str(_REPO / "tools" / "runlib")
if _RUNLIB not in sys.path:
    sys.path.insert(0, _RUNLIB)
from run_identity import identify, spec_path  # noqa: E402

# Which verdicts belong in a pass-rate DENOMINATOR.
#
# This tool is deliberately stdlib-only and outside the run-agent package, so
# the set is spelled out here rather than imported — the same choice
# ``verify-stability/reliability.py`` makes.
#
# HARNESS-ERROR / TIMEOUT / AGENT-CONFIG-ERROR / UNGRADED never reached a state
# where the model's work could be graded. Counting them as non-passes charged
# infrastructure failures to the model and silently deflated every rate below.
#
# The three MODEL-outcome verdicts below stay IN the denominator. **Owner
# decision 2026-08-14**, resolving a real contradiction: the denominator rule
# argues SANDBOX-REJECT and NO_DELIVERABLE describe what the MODEL did, so
# excluding them biases scores UPWARD — the mirror of the harness-fault bias and
# equally wrong.
#
# RECONCILED 2026-08-17. ``run-agent/adapters/base.GRADED_VERDICTS`` used to
# exclude these three and was recorded in the denominator rule as a known
# divergence; it now carries them too, so this set and that one are equal and
# one run set yields one pass rate. Because this tool is stdlib-only and cannot
# import that constant, the equality is enforced by
# ``tools/run-agent/tests/test_denominator_is_one_definition.py``, which parses
# all the copies and fails if any drifts. Edit them together or that test fails.
_MODEL_OUTCOME_GRADED = frozenset({
    "FAIL_NO_EDITS", "SANDBOX-REJECT", "NO_DELIVERABLE",
})
_GRADED_VERDICTS = frozenset({"PASS", "FAIL"}) | _MODEL_OUTCOME_GRADED


@dataclass
class RunRecord:
    product: str           # the harness --model slug, e.g. "aura-mcp:claude-sonnet-4-6"
    task_id: str
    capability: str
    passed: bool           # deterministic gate: overall == "PASS"
    advisory_score: Optional[float]   # R2 advisory, informational only
    cost_usd: Optional[float]
    # Whether this run belongs in a pass-rate denominator at all. Defaults True
    # so existing constructions keep their meaning.
    graded: bool = True


def _capability_for(task_field: object, task_id: str = "") -> str:
    """Parse capability_bucket from a task .md.

    Candidates in order: the path the RUN recorded (absolute, then relative to
    this repo root), then -- for a record that carries only a bare ``task_id``
    (aura-product's summary.json) -- the spec that id resolves to in this tree.
    Without that last candidate every such record is ``uncategorized``, i.e. one
    arm's entire epoch in a single capability cell: the same collapse the task-id
    bug caused, one column over.
    """
    text = str(task_field or "")
    cands = [Path(text), _REPO / text] if text else []
    resolved = spec_path(task_id, _REPO)
    if resolved is not None:
        cands.append(resolved)
    for cand in cands:
        try:
            if not cand.is_file():
                continue
            m = _CAP_RE.search(cand.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue          # unreadable / not a legal path -> not a claim
        return m.group("cap").strip() if m else _UNCATEGORIZED
    return _UNCATEGORIZED


def load_result(path: Path) -> Optional[RunRecord]:
    """Parse one run-agent result.json into a RunRecord (None if unreadable)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # The product slug (``model``) is the join key. A result.json without one is
    # not a per-product run (e.g. the aura-smoke harness emits iteration/ok/blocker
    # records) — skip it rather than fold a garbage "?" column into the table.
    if not str(d.get("model", "")).strip():
        return None
    # Accepts BOTH writer shapes: run.py's "task" path and run_graded.py's bare
    # "task_id". An unidentifiable record reports run_identity.UNKNOWN_TASK_ID,
    # which is a visible row, never a merge into a neighbouring task's cell.
    ident = identify(d, _REPO)
    verifier = d.get("verifier") or {}
    adv = None
    if isinstance(verifier, dict):
        r2 = verifier.get("r2_advisory") or {}
        if isinstance(r2, dict) and isinstance(r2.get("advisory_score"), (int, float)):
            adv = float(r2["advisory_score"])
    agent = d.get("agent") or {}
    overall = str(d.get("overall", "")).upper()
    return RunRecord(
        product=str(d.get("model", "?")),
        task_id=ident.task_id,
        capability=_capability_for(d.get("task"), ident.task_id),
        passed=overall == "PASS",
        advisory_score=adv,
        cost_usd=agent.get("cost_usd") if isinstance(agent.get("cost_usd"), (int, float)) else None,
        graded=overall in _GRADED_VERDICTS,
    )


@dataclass
class Cell:
    n: int = 0            # GRADED runs only — the pass-rate denominator
    n_pass: int = 0
    advisories: List[float] = field(default_factory=list)
    cost: float = 0.0
    # Non-graded runs seen for this cell. Reported, never silently dropped: a
    # 6/6 cell that voided four harness faults must not render identically to a
    # clean 6/6, or a wrong number is merely replaced by an invisible one.
    n_excluded: int = 0

    @property
    def pass_rate(self) -> float:
        return self.n_pass / self.n if self.n else 0.0

    @property
    def mean_advisory(self) -> Optional[float]:
        return round(statistics.mean(self.advisories), 3) if self.advisories else None


@dataclass
class Comparison:
    cells: Dict[Tuple[str, str], Cell]   # (capability, product) -> Cell
    capabilities: List[str]
    products: List[str]
    task_cells: Dict[Tuple[str, str], Cell] = field(default_factory=dict)  # (task_id, product) -> Cell
    task_caps: Dict[str, str] = field(default_factory=dict)                # task_id -> capability
    task_ids: List[str] = field(default_factory=list)

    def cell(self, cap: str, product: str) -> Cell:
        return self.cells.get((cap, product), Cell())

    def ranked(self, product: str) -> List[Tuple[str, float]]:
        """(capability, pass_rate) for a product, only where it has runs, hi→lo."""
        out = [(c, self.cell(c, product).pass_rate)
               for c in self.capabilities if self.cell(c, product).n]
        return sorted(out, key=lambda x: (-x[1], x[0]))

    def leader(self, cap: str) -> Optional[str]:
        """Product with the best (pass_rate, mean_advisory) in a capability."""
        contenders = [(p, self.cell(cap, p)) for p in self.products if self.cell(cap, p).n]
        if not contenders:
            return None
        return max(contenders, key=lambda pc: (pc[1].pass_rate, pc[1].mean_advisory or -1.0))[0]

    # --- task-level / head-to-head: did products actually compete on the SAME task? ---
    def task_cell(self, task_id: str, product: str) -> Cell:
        return self.task_cells.get((task_id, product), Cell())

    def products_for_task(self, task_id: str) -> List[str]:
        return [p for p in self.products if self.task_cell(task_id, p).n]

    def shared_tasks(self) -> List[str]:
        """Tasks run by ≥2 products — the only true apples-to-apples head-to-heads."""
        return [t for t in self.task_ids if len(self.products_for_task(t)) >= 2]

    def is_grounded(self, cap: str) -> bool:
        """A capability is grounded iff ≥1 of its tasks was run by ≥2 products.
        An ungrounded capability's row aggregates disjoint tasks — not a real comparison."""
        shared = set(self.shared_tasks())
        return any(self.task_caps.get(t) == cap for t in shared)


def aggregate(records: List[RunRecord]) -> Comparison:
    cells: Dict[Tuple[str, str], Cell] = {}
    task_cells: Dict[Tuple[str, str], Cell] = {}
    task_caps: Dict[str, str] = {}
    caps, prods, tids = [], [], []
    for r in records:
        if r.capability not in caps:
            caps.append(r.capability)
        if r.product not in prods:
            prods.append(r.product)
        if r.task_id not in tids:
            tids.append(r.task_id)
        task_caps[r.task_id] = r.capability
        c = cells.setdefault((r.capability, r.product), Cell())
        tc = task_cells.setdefault((r.task_id, r.product), Cell())
        # Cost accrues on EVERY run, graded or not: a run that died on a harness
        # fault still spent real money, so dropping it would understate spend.
        # It is a plain total here and is never divided by ``n``.
        # `is not None`, not truthiness: a genuine 0.0 cost is a
        # measurement, not a missing value.
        if r.cost_usd is not None:
            c.cost += r.cost_usd
        if not r.graded:
            # Out of the denominator, but counted so the exclusion is visible.
            c.n_excluded += 1
            tc.n_excluded += 1
            continue
        c.n += 1
        c.n_pass += 1 if r.passed else 0
        if r.advisory_score is not None:
            c.advisories.append(r.advisory_score)
        tc.n += 1
        tc.n_pass += 1 if r.passed else 0
        if r.advisory_score is not None:
            tc.advisories.append(r.advisory_score)
    return Comparison(cells, sorted(caps), sorted(prods), task_cells, task_caps, sorted(tids))


def render_markdown(cmp: Comparison) -> str:
    if not cmp.products:
        return "_no runs to compare_\n"
    lines = ["# Cross-product comparison", "",
             "Cell = deterministic pass-rate `n_pass/n` (+ R2 advisory mean, informational).", ""]
    header = "| capability | " + " | ".join(cmp.products) + " | leader |"
    lines += [header, "|" + "---|" * (len(cmp.products) + 2)]
    for cap in cmp.capabilities:
        grounded = cmp.is_grounded(cap)
        row = [cap if grounded else f"{cap} ⚠"]
        for p in cmp.products:
            c = cmp.cell(cap, p)
            if not c.n:
                row.append("—")
            else:
                adv = f" · adv {c.mean_advisory}" if c.mean_advisory is not None else ""
                row.append(f"{c.n_pass}/{c.n} ({c.pass_rate:.0%}){adv}")
        row.append((cmp.leader(cap) or "—") if grounded else "_n/a_")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "⚠ = ungrounded: no task in this row was run by ≥2 products, so the "
              "cells aggregate **disjoint tasks** and the leader is not a real winner."]

    lines += ["", "## Head-to-head (same task, ≥2 products)", ""]
    shared = cmp.shared_tasks()
    if not shared:
        lines += ["_No task has been run by ≥2 products yet — **every** capability cell "
                  "above aggregates disjoint tasks, so none is a true comparison. Run one "
                  "shared task across products to ground it._"]
    else:
        hh = "| task | capability | " + " | ".join(cmp.products) + " |"
        lines += [hh, "|" + "---|" * (len(cmp.products) + 2)]
        for t in shared:
            row = [t, cmp.task_caps.get(t, _UNCATEGORIZED)]
            for p in cmp.products:
                c = cmp.task_cell(t, p)
                row.append(f"{c.n_pass}/{c.n} ({c.pass_rate:.0%})" if c.n else "—")
            lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Per-product capability profile", ""]
    for p in cmp.products:
        ranked = cmp.ranked(p)
        if not ranked:
            continue
        strong = [c for c, r in ranked if r >= 0.999]
        weak = [c for c, r in ranked if r <= 0.001]
        mid = [f"{c} ({r:.0%})" for c, r in ranked if 0.001 < r < 0.999]
        lines.append(f"- **{p}** — strong: {', '.join(strong) or '—'}; "
                     f"weak: {', '.join(weak) or '—'}"
                     + (f"; partial: {', '.join(mid)}" if mid else ""))
    return "\n".join(lines) + "\n"


def to_dict(cmp: Comparison) -> dict:
    return {
        "schema": "craftbench.compare/v1",
        "products": cmp.products,
        "capabilities": cmp.capabilities,
        "cells": [
            {"capability": cap, "product": p,
             "n": (c := cmp.cell(cap, p)).n, "n_pass": c.n_pass,
             "pass_rate": round(c.pass_rate, 3), "mean_advisory": c.mean_advisory,
             "cost_usd": round(c.cost, 4) or None,
             "n_excluded": c.n_excluded}
            # A cell whose runs were ALL non-graded has n == 0 but is not empty —
            # emit it, or "every run here was a harness fault" renders as "no
            # runs here", which is the same invisibility bug one level up.
            for cap in cmp.capabilities for p in cmp.products
            if cmp.cell(cap, p).n or cmp.cell(cap, p).n_excluded
        ],
        "leaders": {cap: cmp.leader(cap) for cap in cmp.capabilities},
        "head_to_head": [
            {"task_id": t, "capability": cmp.task_caps.get(t, _UNCATEGORIZED),
             "products": {p: {"n": (c := cmp.task_cell(t, p)).n, "n_pass": c.n_pass,
                              "pass_rate": round(c.pass_rate, 3)}
                          for p in cmp.products if cmp.task_cell(t, p).n}}
            for t in cmp.shared_tasks()
        ],
        "ungrounded_capabilities": [c for c in cmp.capabilities if not cmp.is_grounded(c)],
    }


def collect_result_paths(args_paths: List[str], runs_dir: Optional[str]) -> List[Path]:
    paths: List[Path] = [Path(p) for p in args_paths]
    if runs_dir:
        paths += sorted(Path(runs_dir).glob("**/result.json"))
    return paths


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compare products across CraftBench runs.")
    ap.add_argument("results", nargs="*", help="result.json paths")
    ap.add_argument("--runs-dir", default=None, help="glob <dir>/**/result.json")
    ap.add_argument("--out", type=Path, default=None, help="write comparison JSON here")
    args = ap.parse_args(argv)

    paths = collect_result_paths(args.results, args.runs_dir)
    records = [r for r in (load_result(p) for p in paths) if r is not None]
    skipped = len(paths) - len(records)
    if skipped:
        print(f"skipped {skipped} non-product result.json (no model slug)", file=sys.stderr)
    if not records:
        print("no readable result.json found", file=sys.stderr)
        return 2
    cmp = aggregate(records)
    print(render_markdown(cmp))
    if args.out:
        args.out.write_text(json.dumps(to_dict(cmp), indent=2), encoding="utf-8")
        print(f"comparison JSON: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
