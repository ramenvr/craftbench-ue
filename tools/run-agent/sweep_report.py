"""Aggregate a multi-backend sweep's run dirs into comparison tables.

Reads ``<runs>/<backend>/<run>/result.json`` only — no editor, no UE, no
tokens. Five things it does that a hand count gets wrong:

  SCORED BUDGET  the scored-budget rule pins TWO numbers with different jobs:
             a SCORED BUDGET of 40 min (2400 s), applied in POST-PROCESSING from
             the recorded per-run wall time, and a MEASUREMENT CEILING of 60 min
             (``--ceiling 3600``) which is only the hard kill. "A run that has
             not delivered within the budget is a graded budget-FAIL." The 2026-08
             MCP-lane sweep reported pass@ceiling as if it were the score, which
             overstated BOTH arms (B 19/30 -> 16/30, C 19/27 -> 14/27) and
             reversed which arm led. So pass@budget is PRIMARY here and
             pass@ceiling is printed beside it, never alone.
             The clock is the AGENT PHASE — what a delegating developer waits for
             — not end-to-end per cell, which also counts harness bring-up and
             grading. Override with ``--budget-s 0`` to disable.

  DEDUPE     One attempt per (lane, task, model). The sweep re-runs a cell only
             when its first attempt was NON-GRADED, so keep the newest graded
             attempt. Without this, un-voiding a cell the sweep had already
             re-run counts it twice. A record carrying
             ``reinstated.superseded_by`` is excluded outright.

  DENOMINATORS  Only ``adapters.base.GRADED_VERDICTS`` count, AND only cells
             carrying no void (``leak_audit.read_void``). A FAIRNESS-BREACH or
             HARNESS-ERROR cell is listed, never averaged. The void is read from
             the cell's OWN result.json, never from a sweep-level ledger.

  PAIRING    The (task, model) combinations graded in EVERY lane, which is the
             only comparison where the tool layer is the sole difference.

  REASONING  No request path sets a reasoning parameter, so every cell today runs at
             its provider's DEFAULT effort. The per-model rollup NAMES the policy each
             cell RECORDED rather than assuming that, and groups by it, so no row can
             average two policies into one number. A measured token count exists only where the
             run was proxy-routed, which most are not, so the unmeasured marker is
             load-bearing: a 0 there would read as "this model did not reason",
             which for one panel model is nearly true and for another is the
             opposite of true.

Usage:  py -3 sweep_report.py [RUNS_ROOT] [--lanes a,b] [--models a,b|--pinned]
                              [--budget-s 2400]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters.base import GRADED_VERDICTS  # noqa: E402
from leak_audit import read_void, unauditable_void  # noqa: E402  -- the ONE void reader

DEFAULT_RUNS = Path(__file__).resolve().parents[2] / "runs"
#: the scored-budget rule, frozen at signing.
SCORED_BUDGET_S = 2400.0
#: The AUDITED price sheet, $/Mtok (in, out) -- the 2026-08-19 OpenRouter price audit.
#: the cost rule: "recorded cost_usd is untrusted for openrouter-served
#: runs -- measured 3.5x wrong on deepseek (Anthropic-keyed rate table). Every cost view
#: in section 9 is re-derived as recorded tokens x the audited price sheet." Measured on
#: the 2026-08-22 sweep, recorded overstates by 2.6x overall and 12.7x on gemini: the
#: table is Anthropic-keyed, so NATIVE sonnet is nearly right (1.3x) while the cheap
#: OpenRouter ids are billed as premium. Derived is the default view; recorded is shown
#: beside it so the gap stays visible instead of being quietly corrected away.
PRICE_SHEET = {
    "claude-sonnet-5":               (2.00, 10.00),
    "deepseek/deepseek-v4-pro-0813": (1.19,  3.56),
    "x-ai/grok-4.6":                 (2.00,  6.00),
    "google/gemini-3.7-flash":       (0.38,  1.88),
    "qwen/qwen3.8-max":              (2.00,  6.00),
    "openai/gpt-5.6-luna":           (0.20,  1.20),
    "openai/gpt-5.6-sol":            (2.00, 10.00),
    #: DIFFERENT PROVENANCE from the rows above, and it matters. Those come from
    #: From the 2026-08-19 OpenRouter price audit. This one was read live from
    #: OpenRouter's own /api/v1/models on 2026-08-27: prompt 0.000000075 and
    #: completion 0.00000025 per token, i.e. $0.075 / $0.25 per Mtok. That is the
    #: authoritative source rather than a remembered figure -- which §9 forbids --
    #: but it is a point-in-time read, not the dated audit, so re-read it before
    #: any published cost table.
    #:
    #: Its cache read is quoted at 0.000000015/token = 20% of input, NOT the 10%
    #: CACHE_READ_MULT below assumes. At a 95% hit rate that understates this
    #: model's prompt cost by about 2x. Left as-is because the multiplier is
    #: global and documented as an assumption; noted here so the next person
    #: reading a glm cost figure knows which way it is wrong.
    "z-ai/glm-5.3-flash":            (0.075, 0.25),
}
#: The sheet lists no CACHE rates, so these are the Anthropic/OpenRouter convention and
#: an ASSUMPTION, not audited. They are load-bearing: at 92-98% hit rates most of the
#: token volume IS cache reads. Edit them to check sensitivity.
CACHE_READ_MULT, CACHE_WRITE_MULT = 0.10, 1.25
#: The reasoning block ``adapters.base.reasoning_policy_fields`` stamps on every
#: record, read here as the writer declares it. Two absences that must never
#: collapse into each other, or into a zero: the POLICY missing (a record written
#: before the block existed) and the MEASUREMENT missing (nothing on the wire
#: reported a count for a cell that certainly did some thinking).
POLICY_KEY, MEASURE_KEY = "reasoning_policy", "reasoning_measurement"
POLICY_UNRECORDED = "unrecorded"
#: Both the recorded ``reasoning_measurement`` state and this report's column
#: marker, deliberately the same word so the table reads back the record's own.
UNMEASURED = "unmeasured"


def read_policy(agent: dict) -> str:
    """The reasoning policy this cell ran under, or ``unrecorded``.

    Read from the CELL's own result.json -- same rule as ``read_void``: the record
    travels with the cell, a sweep-level default does not.
    """
    return str(agent.get(POLICY_KEY) or "").strip() or POLICY_UNRECORDED


def read_reasoning(agent: dict):
    """The measured reasoning-token count, or None when the record reports none.

    The record's own MEASUREMENT STATE decides, not the presence of an integer, so
    a placeholder count beside an ``unmeasured`` state cannot re-enter the table as
    a measured zero -- which is the "this model did not reason" misread the column
    exists to prevent. A record written before the block existed carries neither
    key and falls back to the count.
    """
    if agent.get(MEASURE_KEY) == UNMEASURED:
        return None
    v = agent.get("reasoning_tokens")
    return v if isinstance(v, (int, float)) else None


def derived_cost(row):
    """Cost from recorded tokens x the audited sheet. None if the id is unpriced.

    Fresh input is tokens_in MINUS cache_read: the adapters report tokens_in
    inclusive of cache reads, so charging both double-counts the cached share,
    which is most of the volume.
    """
    p = PRICE_SHEET.get(row["model"])
    if p is None:
        return None
    pin, pout = p
    fresh = max(0, row["tin"] - row["crd"])
    return ((fresh / 1e6) * pin + (row["tout"] / 1e6) * pout
            + (row["crd"] / 1e6) * pin * CACHE_READ_MULT
            + (row["ccr"] / 1e6) * pin * CACHE_WRITE_MULT)

def cache_hit_rate(rows):
    """Share of input tokens served from cache, over ``rows``. None if no input.

    A COVARIATE, not a diagnostic. Measured 2026-08-26 across cpp block 1, the
    six arms did not get the same deal from the wire:

        gpt-5.6-sol   ~100%      deepseek-v4-pro   1.5%   (cache_write always 0)
        gpt-5.6-luna  ~100%      gemini-3.7-flash  2.2%   (writes, never re-reads)
        grok-4.6       95%
        claude-sonnet-5 98%

    That is a real difference between arms and belongs in the report rather than
    being averaged away: an arm that re-sends its whole context every turn pays
    full input price on all of it, and carries different latency and context
    pressure than one that does not. It cost 25% of the block's spend.

    Same convention as ``derived_cost``: ``tin`` is inclusive of cache reads, so
    the denominator is ``tin`` and not ``tin + crd``. Getting that backwards reads
    98% as 49%, which looks like a mediocre cache rather than a working one.
    """
    tin = sum(r["tin"] for r in rows)
    return (sum(r["crd"] for r in rows) / tin) if tin else None


#: §5 pins these four ids. `qwen/qwen3.8-max` is the NAMED RESERVE, usable only
#: as a §11-logged swap when a pinned family is unservable — not a fifth arm.
PINNED_PANEL = ("claude-sonnet-5", "deepseek/deepseek-v4-pro-0813",
                "x-ai/grok-4.6", "google/gemini-3.7-flash")


def cells(runs_root: Path, lanes):
    for lane in lanes:
        root = runs_root / lane
        if not root.is_dir():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            rj = d / "result.json"
            if not rj.is_file():
                continue
            try:
                r = json.loads(rj.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            model = r.get("model") or ""
            model = model.split(":", 1)[1] if ":" in model else model
            a = r.get("agent") or {}
            yield {
                "lane": lane, "run": d.name, "model": model,
                "task": Path(str(r.get("task") or "")).parent.name or "?",
                "verdict": r.get("overall") or "?",
                "cost": a.get("cost_usd") or 0.0,
                "priced": bool(a.get("cost_usd")),
                "turns": a.get("num_turns") or 0,
                "tools": a.get("tool_use_count") or 0,
                "mcp": a.get("mcp_tool_use_count") or 0,
                "dur": a.get("duration_s") or 0.0,
                "tin": a.get("tokens_in") or 0,
                "tout": a.get("tokens_out") or 0,
                "crd": a.get("cache_read_tokens") or 0,
                "ccr": a.get("cache_creation_tokens") or 0,
                # Deliberately NOT ``or 0`` like its neighbours: None means nobody
                # reported a count, and folding that to 0 is the one rendering this
                # column exists to prevent.
                "rsn": read_reasoning(a),
                "policy": read_policy(a),
                "names": a.get("tool_names") or [],
                "void": read_void(r),
                # A verdict that MEANS voided, with no reason recorded. Carried
                # on the row so the report can name it; never gates.
                "unauditable_void": unauditable_void(r),
                "superseded": bool((r.get("reinstated") or {}).get("superseded_by")),
            }


def is_graded(row) -> bool:
    """Does this cell belong in a pass-rate? A graded verdict AND no void.

    Two conditions, not one, because a void need not rewrite ``overall`` — an
    operator void leaves it at FAIL. A void leaves the numerator AND the
    denominator; it is not a converted PASS.
    """
    return row["verdict"] in GRADED_VERDICTS and not row["void"]


def dedupe(rows):
    """Newest GRADED attempt per (lane, task, model), else newest attempt.

    Ranked on ``is_graded`` rather than on the verdict string, or a void that
    kept its graded-looking ``overall`` would win the slot as the newest attempt
    and then be dropped by the denominator filter — DELETING the cell's real
    graded attempt instead of standing beside it.
    """
    best = {}
    for r in sorted(rows, key=lambda r: r["run"]):
        if r["superseded"]:
            continue
        k = (r["lane"], r["task"], r["model"])
        cur = best.get(k)
        if cur is None or is_graded(r) >= is_graded(cur):
            best[k] = r
    return list(best.values())


def _fisher(a, b, c, d):
    lf = lambda n: math.lgamma(n + 1)  # noqa: E731
    def pr(a, b, c, d):
        return math.exp(lf(a + b) + lf(c + d) + lf(a + c) + lf(b + d)
                        - lf(a) - lf(b) - lf(c) - lf(d) - lf(a + b + c + d))
    obs, tot = pr(a, b, c, d), 0.0
    for i in range(min(a + b, a + c) + 1):
        j, k, l = a + b - i, a + c - i, d - (a - i)
        if j < 0 or k < 0 or l < 0:
            continue
        p = pr(i, j, k, l)
        if p <= obs * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def _mcnemar(disc, k):
    if not disc:
        return 1.0
    return min(1.0, 2.0 * sum(math.comb(disc, i)
                              for i in range(min(k, disc - k) + 1)) / 2 ** disc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_root", nargs="?", default=str(DEFAULT_RUNS))
    ap.add_argument("--lanes", default="unreal-mcp,aura-mcp")
    ap.add_argument("--models", default=None,
                    help="comma-separated model filter (default: every model found)")
    ap.add_argument("--pinned", action="store_true",
                    help="restrict to the cost rule's pinned four")
    ap.add_argument("--budget-s", type=float, default=SCORED_BUDGET_S,
                    help="scored budget in seconds; 0 disables (default 2400 = §6b)")
    a = ap.parse_args(argv)
    lanes = [s.strip() for s in a.lanes.split(",") if s.strip()]
    budget = a.budget_s or None

    raw = list(cells(Path(a.runs_root), lanes))
    rows = dedupe(raw)
    keep = set(PINNED_PANEL) if a.pinned else (
        {s.strip() for s in a.models.split(",")} if a.models else None)
    if keep is not None:
        rows = [r for r in rows if r["model"] in keep]
    if not rows:
        print(f"no run dirs under {a.runs_root} for lanes {lanes}")
        return 2

    graded = lambda rs: [r for r in rs if is_graded(r)]  # noqa: E731
    p_ceil = lambda rs: [r for r in rs if is_graded(r) and r["verdict"] == "PASS"]  # noqa: E731
    def p_bud(rs):
        return [r for r in p_ceil(rs) if budget is None or r["dur"] <= budget]

    by_lane = collections.defaultdict(list)
    for r in rows:
        by_lane[r["lane"]].append(r)

    print(f"attempts on disk {len(raw)}   grid cells after dedupe {len(rows)}"
          + (f"   [{'pinned four' if a.pinned else 'models: ' + ','.join(sorted(keep))}]"
             if keep is not None else ""))
    if budget:
        print(f"scored budget {budget:.0f}s ({budget/60:.0f} min, the "
              f"scored-budget rule) applied to the AGENT phase; "
              f"pass@ceiling shown beside it")

    for lane in lanes:
        rs, g = by_lane[lane], graded(by_lane[lane])
        if not rs:
            continue
        pc, pb = p_ceil(g), p_bud(g)
        pct = lambda n: f"{100.0 * n / len(g):.0f}%" if g else "-"  # noqa: E731
        print(f"\n--- {lane}: {len(rs)} cells, {len(g)} graded")
        print(f"      PASS@budget  {len(pb)}/{len(g)} ({pct(len(pb))})   <- primary")
        print(f"      PASS@ceiling {len(pc)}/{len(g)} ({pct(len(pc))})"
              + (f"   ({len(pc) - len(pb)} over budget)" if len(pc) != len(pb) else ""))
        # VOID(<verdict>), not the bare verdict: this histogram is where a void
        # that kept ``overall: FAIL`` would read as an ordinary graded FAIL.
        lab = lambda r: (f"VOID({r['verdict']})" if r["void"]  # noqa: E731
                         else r["verdict"])
        for v, n in collections.Counter(lab(r) for r in rs).most_common():
            print(f"      {v:<18} {n}"
                  + ("" if v in GRADED_VERDICTS else "   (non-graded)"))
        pr = [r for r in rs if r["priced"]]
        # DERIVED first and RECORDED labelled as such: section 5 makes recorded
        # cost_usd untrusted for openrouter-served runs (measured 3.5x wrong on
        # deepseek), so it must never be the unqualified headline "cost".
        dsum = sum(x for x in (derived_cost(r) for r in rs) if x is not None)
        print(f"      cost ${dsum:.2f} derived "
              f"(recorded ${sum(r['cost'] for r in rs):.2f}, untrusted) "
              f"over {len(pr)}/{len(rs)} priced   "
              f"turns {sum(r['turns'] for r in rs)}   "
              f"tool calls {sum(r['tools'] for r in rs)} "
              f"(mcp {sum(r['mcp'] for r in rs)})   "
              f"agent-phase {sum(r['dur'] for r in rs) / 3600:.1f}h")
        hit = cache_hit_rate(rs)
        if hit is not None:
            print(f"      cache {hit:.0%} of input served from cache"
                  + ("   <-- LOW: this arm re-sends its context every turn"
                     if hit < 0.50 else ""))

    # Per-model cache, because the gap is between MODELS (really between the
    # backends serving them), not between lanes -- a per-lane average hides it.
    print(chr(10) + "=" * 78 + chr(10)
          + "CACHE HIT RATE BY MODEL  (covariate, not a verdict)")
    by_model = collections.defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    for m in sorted(by_model):
        hit = cache_hit_rate(by_model[m])
        if hit is None:
            print(f"  {m:<34} (no input recorded)")
            continue
        print(f"  {m:<34} {hit:>6.1%}"
              + ("   re-sends context every turn" if hit < 0.50 else ""))

    for label, key in (("TASK", "task"), ("MODEL", "model")):
        print(f"\n{'=' * 78}\nPASS BY {label}  (budget / ceiling / graded)")
        print(f"{key:<30}" + "".join(f"{l:>18}" for l in lanes))
        for val in sorted({r[key] for r in rows}):
            line = f"{val:<30}"
            for lane in lanes:
                g = graded([r for r in by_lane[lane] if r[key] == val])
                line += (f"{len(p_bud(g))}/{len(p_ceil(g))}/{len(g):<12}"
                         if g else f"{'-':>18}")
            print(line)

    if budget:
        over = [r for r in p_ceil(rows) if r["dur"] > budget]
        print(f"\n{'=' * 78}\nPASSES OUTSIDE THE SCORED BUDGET "
              f"({len(over)}; graded budget-FAIL per §6b(2))")
        for r in sorted(over, key=lambda r: -r["dur"]):
            print(f"  {r['dur']/60:>5.1f} min  {r['lane']:<11} {r['task']:<28} {r['model']}")
        if not over:
            print("  none")

    ng = [r for r in rows if not is_graded(r)]
    voids = [r for r in ng if r["void"]]
    print(f"\n{'=' * 78}\nNON-GRADED CELLS ({len(voids)} voided)")
    for r in sorted(ng, key=lambda r: r["run"]):
        print(f"  {r['verdict']:<18} {r['lane']:<11} {r['run']}")
        v = r["void"]
        if v:
            print(f"      VOID {v.get('at') or 'undated'}: "
                  f"{str(v.get('reason'))[:96]}")
    if not ng:
        print("  none")

    print(f"\n{'=' * 78}\nPER-CELL MEANS (graded cells; cost over PRICED cells only)")
    print(f"{'lane':<14}{'derived$':>10}{'recorded$':>11}{'priced':>8}"
          f"{'turns':>8}{'tools':>8}{'mcp':>8}{'min':>8}")
    for lane in lanes:
        g = graded(by_lane[lane])
        if not g:
            continue
        pr = [r for r in g if r["priced"]]
        dc = [x for x in (derived_cost(r) for r in pr) if x is not None]
        n = len(g)
        print(f"{lane:<14}"
              f"{(sum(dc) / len(dc)) if dc else 0:>10.2f}"
              f"{(sum(r['cost'] for r in pr) / len(pr)) if pr else 0:>11.2f}"
              f"{len(pr):>8}"
              f"{sum(r['turns'] for r in g) / n:>8.0f}"
              f"{sum(r['tools'] for r in g) / n:>8.0f}"
              f"{sum(r['mcp'] for r in g) / n:>8.0f}"
              f"{sum(r['dur'] for r in g) / n / 60:>8.0f}")

    print(f"\n{'=' * 78}\nSPEND BY MODEL (graded cells; DERIVED from tokens x the sheet)")
    per = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    unpriced = set()
    for r in graded(rows):
        d = derived_cost(r)
        if d is None:
            unpriced.add(r["model"])
            d = 0.0
        per[r["model"]][0] += d
        per[r["model"]][1] += r["cost"]
        per[r["model"]][2] += 1
        per[r["model"]][3] += 1 if r["priced"] else 0
    tot_d = sum(v[0] for v in per.values())
    tot_r = sum(v[1] for v in per.values())
    for m, (d, c, n, np_) in sorted(per.items(), key=lambda kv: -kv[1][0]):
        print(f"  ${d:>8.2f}  {100 * d / tot_d if tot_d else 0:>5.1f}%  {n:>2} cells "
              f"({np_} priced)  ${d / np_ if np_ else 0:>7.2f}/cell   "
              f"(recorded ${c:>8.2f} = {c / d if d else 0:>4.1f}x)  {m}")
    print(f"  ${tot_d:>8.2f}  derived total   (recorded ${tot_r:.2f} = "
          f"{tot_r / tot_d if tot_d else 0:.1f}x)")
    if unpriced:
        print(f"  NOT IN THE PRICE SHEET, counted as $0: {', '.join(sorted(unpriced))}")

    print(f"\n{'=' * 78}\nREASONING BY MODEL (graded cells, one row per POLICY)")
    print("  Policy is what the record says was REQUESTED -- no request path sets a "
          "reasoning\n  parameter today, so provider-default is the expected value. A "
          f"count exists only for\n  proxy-routed cells, and `{UNMEASURED}` there is "
          "silence, never a model that did not\n  reason; the share's denominator is the "
          "output of the MEASURED cells alone, so cells\n  nobody measured cannot dilute "
          "it.")
    print(f"  {'model':<30}{'policy':<17}{'measured':>9}{'reasoning tok':>15}"
          f"{'meas out':>11}{'share':>11}")
    # Keyed on (model, POLICY), not on model: a mixed-policy model then renders as two
    # rows, so averaging across policies is impossible rather than merely discouraged.
    # cells, measured, reasoning (all measured), and — kept separate on purpose —
    # the paired subset the SHARE is computed over, plus how many were excluded.
    rsn = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for r in graded(rows):
        v = rsn[(r["model"], r["policy"])]
        v[0] += 1
        if r["rsn"] is None:
            continue
        v[1] += 1
        v[2] += r["rsn"]
        # The share needs BOTH sides from the SAME cells. Summing every measured
        # reasoning count over only the cells that reported output tokens ratios
        # two different populations and can exceed 100%.
        if isinstance(r["tout"], (int, float)) and r["tout"] > 0:
            v[3] += r["tout"]
            v[5] += r["rsn"]
        else:
            v[4] += 1
    pols = collections.defaultdict(set)
    for m, pol in rsn:
        pols[m].add(pol)
    for (m, pol), (n, k, rt, out, no_den, rt_paired) in sorted(rsn.items()):
        share = ((f"{100.0 * rt_paired / out:.1f}%" if out else "no out tok")
                 if k else UNMEASURED)
        # `!` marks a comparability alarm, as it does in the bench leaderboard.
        mixed = len(pols[m] - {POLICY_UNRECORDED}) > 1
        print(f"{'! ' if mixed else '  '}{m:<30}{pol:<17}{f'{k}/{n}':>9}"
              f"{(f'{rt:,}' if k else UNMEASURED):>15}"
              f"{(f'{out:,}' if k else UNMEASURED):>11}{share:>11}"
              + (f"   ({no_den} of them reported no output tokens, so the share "
                 f"covers {k - no_den})" if no_den else ""))
    for m, ps in sorted(pols.items()):
        declared = ps - {POLICY_UNRECORDED}
        if len(declared) > 1:
            print(f"  ! MIXED POLICY, NOT COMPARABLE: {m} ran under "
                  f"{', '.join(sorted(declared))}")
        if POLICY_UNRECORDED in ps and declared:
            print(f"  ? POLICY UNRECORDED on some {m} cells, declared "
                  f"{', '.join(sorted(declared))} on the rest - unknown "
                  f"configuration rather than a different one")
    tot_n = sum(v[0] for v in rsn.values())
    tot_k = sum(v[1] for v in rsn.values())
    print(f"  {tot_k}/{tot_n} graded cells carry a measured reasoning count"
          + (f"; {tot_n - tot_k} {UNMEASURED}" if tot_k != tot_n else ""))
    if not tot_k:
        # Every marker and no number is the expected reading, not a broken column:
        # say where a number can come from instead of leaving the table looking empty.
        print("  Only a proxy-routed run reports one (CB_PROXY_OPENROUTER=1, off by "
              "default);\n  for runs already on disk the count is a ledger join -- "
              "reasoning_census.py.")

    print(f"\n{'=' * 78}\nTOP TOOLS PER CELL (graded cells)")
    for lane in lanes:
        g = graded(by_lane[lane])
        if not g:
            continue
        c = collections.Counter(n for r in g for n in r["names"])
        print(f"\n  {lane} ({len(g)} cells, {sum(c.values())} calls)")
        for name, k in c.most_common(8):
            print(f"     {k / len(g):>6.1f}/cell  {name}")

    if len(lanes) == 2:
        print(f"\n{'=' * 78}\nLANE COMPARISON")
        pairs = collections.defaultdict(dict)
        for r in rows:
            pairs[(r["task"], r["model"])][r["lane"]] = r
        both = [v for v in pairs.values()
                if len(v) == 2
                and all(is_graded(x) for x in v.values())]
        for name, bud in (("budget", budget), ("ceiling", None)):
            ok = lambda r: (r["verdict"] == "PASS"  # noqa: E731
                            and (bud is None or r["dur"] <= bud))
            w = collections.Counter((ok(v[lanes[0]]), ok(v[lanes[1]])) for v in both)
            disc = w[(True, False)] + w[(False, True)]
            print(f"  paired @{name}: n={len(both)}  both PASS {w[(True, True)]}  "
                  f"both FAIL {w[(False, False)]}  {lanes[0]} only {w[(True, False)]}  "
                  f"{lanes[1]} only {w[(False, True)]}  "
                  f"McNemar p={_mcnemar(disc, w[(False, True)]):.3f}")
        for name, sel in (("budget", p_bud), ("ceiling", p_ceil)):
            gs = [graded(by_lane[l]) for l in lanes]
            if not all(gs):
                continue
            x, y = (len(sel(g)) for g in gs)
            print(f"  unpaired @{name}: {lanes[0]} {x}/{len(gs[0])} vs "
                  f"{lanes[1]} {y}/{len(gs[1])}  Fisher p="
                  f"{_fisher(x, len(gs[0]) - x, y, len(gs[1]) - y):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
