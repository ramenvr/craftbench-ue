"""reliability — does a repeated bench actually MEAN anything?

The owner's third criterion for a trustable eval is not "what was the pass
rate". It is: *5 back-to-back, the harness does not break, and the results are
consistent.* Nothing in the rig answered that. ``bench.md`` / ``leaderboard.html``
render a grid of verdicts, which shows WHAT happened but never adjudicates
whether the set is poolable, whether the spread is tight, or whether the harness
stayed out of the way.

This module answers it, and deliberately answers it in a way that can say NO.

Four checks, in the order that can invalidate the ones after them:

1. **CONTRACT** — the pooling rule. Every rep must share ``benchmark_mode_active:
   true`` AND one ``preamble_sha``. A set that fails this is NOT poolable and no
   rate is computed from it, because a rate across two contracts is a number
   with no referent. (This rule has already caught one contaminated cell; it is
   the reason the 2026-08-08 deepseek rep was excluded from the -cpp table.)
2. **HARNESS** — every non-graded verdict, named. ``DRAINER-STALLED``,
   ``COMMIT-EXHAUSTED``, ``STACK-DOWN``, ``EDITOR-GONE``, ``BRIDGE-NOT-READY``
   are machine faults. They are already excluded from pass-rates, which is
   exactly why they can hide: a 3-of-3-graded run that quietly discarded two
   harness deaths is NOT a reliable eval, and the pass rate alone will not say so.
3. **CONSISTENCY** — the verdict spread among graded reps. Unanimous or not.
   A split is the finding; it must never be averaged into a rate and presented
   as though the task had a probability.
4. **VARIANCE** — spread of agent seconds / cost / tool calls. Advisory only: a
   set can be perfectly consistent in verdict and still be wildly unstable
   underneath, and that is worth seeing before handing the eval to someone else.

The verdict line is intentionally binary with reasons attached, because the
question it exists to answer is binary: is this fit to hand to someone else.

Pure functions over already-collected JSON — no network, no stack, no cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Verdicts that count toward a rate. Mirrors adapters.base.GRADED_VERDICTS —
# an ALLOWLIST, so a verdict invented tomorrow is non-graded here by default.
GRADED = {"PASS", "FAIL"}


# A fixture may declare that it SKIPPED a gate rather than failing it. That is a
# deliberate anti-false-FAIL design (gp-glide-stamina's gate (5) went
# window-consumed on 2026-08-06 so a slow-but-conforming drain stops near-miss
# failing) — but it means two PASSes can assert DIFFERENT things, and a report
# that renders them identically is overstating the weaker one. The marker is
# already in the L2 notes, so no fixture change is needed to say so.
_SKIP_MARK = "is SKIPPED, not failed"


def skipped_gates(summary: dict) -> List[str]:
    """Gate labels a fixture reported as SKIPPED for this rep, e.g. ``gate (5)``.

    Found by scanning the L2 notes rather than by asking the fixture, because
    the fixture already logs it and re-deriving it here would be a second source
    of truth for the same fact."""
    layers = ((summary.get("verifier") or {}).get("layers") or {})
    out: List[str] = []
    for name in ("L2", "L2I"):
        for note in (layers.get(name) or {}).get("notes") or []:
            if _SKIP_MARK not in note:
                continue
            head = note.split(_SKIP_MARK)[0]
            # "…— gate (5) " -> "gate (5)"; fall back to the whole clause.
            frag = head.rsplit("—", 1)[-1].strip() or head.strip()
            out.append(frag[-40:])
    return out


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def collect_reps(bench_dir: Path) -> List[dict]:
    """One flat record per rep, joining ``bench.json`` with each run's
    ``summary.json`` — the contract fields (``benchmark_mode_active``,
    ``inspector_warm``, ``pressure``) live only in the latter."""
    bench = _load(bench_dir / "bench.json")
    out: List[dict] = []
    for r in bench.get("reps") or []:
        rd = r.get("run_dir")
        s = _load(Path(rd) / "summary.json") if rd else {}
        agent = s.get("agent") or {}
        out.append({
            "model": r.get("model"),
            "task_id": r.get("task_id"),
            "rep": r.get("rep"),
            "verdict": r.get("verdict"),
            "cost_usd": r.get("cost_usd"),
            "agent_s": r.get("agent_s"),
            # NB the live runner writes agent.tool_calls; tool_use_count is the
            # OTHER lane's field. Reading the wrong one manufactures phantoms.
            "tools": agent.get("tool_calls", r.get("tool_use_count")),
            "preamble_sha": r.get("preamble_sha") or s.get("preamble_sha"),
            "benchmark_mode_active": s.get("benchmark_mode_active"),
            "inspector_warm": (s.get("inspector_warm") or {}).get("status"),
            "skipped_gates": skipped_gates(s),
            "run_dir": rd,
        })
    return out


def check_contract(reps: Sequence[dict]) -> Tuple[bool, List[str]]:
    """The pooling rule. Returns ``(poolable, reasons)``.

    ``benchmark_mode_active`` is TRI-STATE — ``None`` means the probe could not
    read it, which is NOT the same as ``False`` and must not be silently treated
    as either. An unreadable contract is an unpoolable set."""
    notes: List[str] = []
    modes = {r["benchmark_mode_active"] for r in reps}
    shas = {r["preamble_sha"] for r in reps if r["preamble_sha"]}
    if modes - {True}:
        bad = sorted(str(m) for m in modes - {True})
        notes.append(f"benchmark_mode_active not True on every rep (saw {', '.join(bad)}) "
                     "— live Unreal context may have been injected; not comparable "
                     "with the 2026-08-08+ baseline")
    if len(shas) > 1:
        notes.append(f"{len(shas)} different preamble_sha values — these reps ran "
                     "different prompts and cannot share a denominator")
    if not shas:
        notes.append("no preamble_sha recorded — contract identity unverifiable")
    return (not notes, notes)


def split_verdicts(reps: Sequence[dict]) -> Tuple[List[dict], List[dict]]:
    """``(graded, non_graded)`` by the allowlist."""
    graded = [r for r in reps if r["verdict"] in GRADED]
    return graded, [r for r in reps if r["verdict"] not in GRADED]


def spread(values: Sequence[Optional[float]]) -> Optional[Dict[str, float]]:
    """min/max/mean and the max:min ratio, or None when nothing is measurable.

    The RATIO is the reason this is not just min/max: 240 s vs 1800 s and
    240 s vs 300 s are both "a spread", and only one of them means the harness
    is unstable."""
    vals = [float(v) for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    return {"min": round(lo, 2), "max": round(hi, 2),
            "mean": round(sum(vals) / len(vals), 2),
            "ratio": round(hi / lo, 2) if lo > 0 else None}


def assess(reps: Sequence[dict]) -> dict:
    """The full adjudication. ``reliable`` is True only when the set is
    poolable, harness-clean, and unanimous — all three, because any one of them
    failing makes the pass rate mean something different from what a reader
    will assume it means."""
    poolable, contract_notes = check_contract(reps)
    graded, non_graded = split_verdicts(reps)
    verdicts = sorted({r["verdict"] for r in graded})
    unanimous = len(verdicts) <= 1

    blockers: List[str] = list(contract_notes)
    if non_graded:
        detail = ", ".join(f"{r['verdict']}(rep {r['rep']})" for r in non_graded)
        blockers.append(f"{len(non_graded)} of {len(reps)} reps hit a HARNESS fault: "
                        f"{detail} — excluded from the rate, which is exactly why "
                        "they must be named here")
    if not unanimous:
        counts = {v: sum(1 for r in graded if r["verdict"] == v) for v in verdicts}
        blockers.append("graded verdicts are SPLIT " +
                        "/".join(f"{v}x{n}" for v, n in counts.items()) +
                        " — report the split, never an averaged rate")
    if not graded:
        blockers.append("no graded rep at all — nothing was measured")

    # NOT a blocker: a skipped gate is a documented fixture decision, not a
    # fault, and treating it as one would push the fixture back toward the
    # false-FAILs the skip exists to prevent. It IS a caveat that must travel
    # with the verdict — two PASSes that assert different things must not be
    # rendered identically.
    skipped = sorted({g for r in reps for g in (r.get("skipped_gates") or [])})
    inconsistent_gating = bool(skipped) and any(
        not r.get("skipped_gates") for r in reps if r["verdict"] in GRADED)

    warms = [r["inspector_warm"] for r in reps if r["inspector_warm"]]
    return {
        "skipped_gates": skipped,
        "inconsistent_gating": inconsistent_gating,
        "n_reps": len(reps),
        "n_graded": len(graded),
        "poolable": poolable,
        "unanimous": unanimous,
        "verdicts": verdicts,
        "non_graded": [{"rep": r["rep"], "verdict": r["verdict"]} for r in non_graded],
        "pass_rate": (round(sum(1 for r in graded if r["verdict"] == "PASS")
                            / len(graded), 3) if graded and poolable else None),
        "agent_s": spread([r["agent_s"] for r in reps]),
        "cost_usd": spread([r["cost_usd"] for r in reps]),
        "tools": spread([r["tools"] for r in reps]),
        "inspector_warm": {s: warms.count(s) for s in sorted(set(warms))} or None,
        "reliable": poolable and unanimous and not non_graded and bool(graded),
        "blockers": blockers,
    }


def by_cell(reps: Sequence[dict]) -> Dict[Tuple[str, str], List[dict]]:
    """Group by ``(model, task)``.

    THE grouping mistake this exists to prevent: adjudicating a whole bench as
    one set. A 2-model x 3-rep bench where model A passes 3/3 and model B fails
    3/3 is PERFECTLY consistent — and pooled it reads as a 'SPLIT PASSx3/FAILx3'
    inconsistency, i.e. the report would condemn exactly the clean result it
    exists to certify. Reliability is a property of one model on one task."""
    cells: Dict[Tuple[str, str], List[dict]] = {}
    for r in reps:
        cells.setdefault((r["model"] or "?", r["task_id"] or "?"), []).append(r)
    return cells


def _render_cell(model: str, task: str, reps: Sequence[dict], a: dict) -> List[str]:
    L = [f"### {model} on {task} — {len(reps)} rep(s)", ""]
    L.append("| rep | verdict | agent s | cost | tools | bench mode | inspector |")
    L.append("|---|---|---|---|---|---|---|")
    for r in sorted(reps, key=lambda x: (x["rep"] or 0)):
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["rep"], r["verdict"], r["agent_s"],
            ("$%.4f" % r["cost_usd"]) if isinstance(r["cost_usd"], (int, float)) else "?",
            r["tools"] if r["tools"] is not None else "?",
            r["benchmark_mode_active"], r["inspector_warm"] or "-"))
    L.append("")
    for label, key in (("agent s", "agent_s"), ("cost", "cost_usd"), ("tools", "tools")):
        sp = a.get(key)
        if sp:
            L.append("* %s: %s–%s (mean %s, max/min %sx)" %
                     (label, sp["min"], sp["max"], sp["mean"], sp["ratio"]))
    if a.get("inspector_warm"):
        L.append("* inspector warm-up: " +
                 ", ".join(f"{k}x{v}" for k, v in a["inspector_warm"].items()))
    if a.get("skipped_gates"):
        L.append("* **gates SKIPPED on at least one rep**: %s — those reps did "
                 "not assert that requirement, so their verdict is a weaker "
                 "claim than a rep that was gated on it."
                 % ", ".join(a["skipped_gates"]))
        if a.get("inconsistent_gating"):
            L.append("  * and the skip was NOT uniform across this cell, so the "
                     "reps here do not all mean the same thing. Say which were "
                     "gated before quoting them together.")
    L.append("")
    if a["reliable"]:
        L.append("**RELIABLE** — %d/%d graded, unanimous %s, contract identical, "
                 "zero harness faults." % (a["n_graded"], a["n_reps"],
                                           a["verdicts"][0] if a["verdicts"] else "?"))
    else:
        L.append("**NOT RELIABLE YET**:")
        for b in a["blockers"]:
            L.append(f"  * {b}")
    L.append("")
    return L


def render(cells: Dict[Tuple[str, str], Tuple[List[dict], dict]]) -> str:
    """A terse report — the thing that gets pasted into a handoff."""
    L: List[str] = ["## Reliability", ""]
    bad = [k for k, (_, a) in cells.items() if not a["reliable"]]
    if not cells:
        return "## Reliability\n\nNo reps found — is this a bench dir?\n"
    L.append("**%d of %d cell(s) meet the bar.**" % (len(cells) - len(bad), len(cells)))
    L.append("")
    for (model, task), (reps, a) in sorted(cells.items()):
        L.extend(_render_cell(model, task, reps, a))
    if bad:
        L.append("A cell that does not meet the bar must not be quoted as a pass "
                 "rate — say what went wrong instead. Reliability is judged per "
                 "(model, task): a bench where one model passes and another fails "
                 "is consistent, not split.")
    return "\n".join(L) + "\n"


def report(bench_dir: Path) -> Tuple[str, dict]:
    reps = collect_reps(Path(bench_dir))
    cells = {k: (v, assess(v)) for k, v in by_cell(reps).items()}
    text = render(cells)
    return text, {
        "cells": {f"{m} :: {t}": a for (m, t), (_, a) in cells.items()},
        # The gate: EVERY cell must clear the bar. An empty bench is not "fine".
        "reliable": bool(cells) and all(a["reliable"] for _, a in cells.values()),
    }
