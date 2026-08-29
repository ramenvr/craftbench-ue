#!/usr/bin/env python3
"""Stop a sweep at a spend ceiling, at the next CELL BOUNDARY.

WHY A SEPARATE GUARD. ``sweep_mcp_lanes.sh`` has a clean pause already — touch
``$STOP_FLAG`` and the loop stops after the in-flight cell has been graded AND
audited, never mid-drive. What it does not have is anything that decides WHEN.
Killing the loop from outside is not a substitute: measured 2026-08-23, a waiter
polling every 45 s never caught the gap between cells, and killing mid-cell skips
that cell's post-cell leak audit — which is how a contaminated PASS got banked.
So this watches the spend and drops the flag; the sweep still decides where to
stop.

COST IS DERIVED, NEVER READ. the cost rule: "recorded cost_usd is
untrusted for openrouter-served runs — measured 3.5x wrong on deepseek". The
recorded figure comes from the Claude Code CLI, which prices every call at
Anthropic first-party rates and cannot see the gateway; on the 2026-08-22 sweep
it overstated by 2.6x overall and **12.7x on gemini**. Enforcing a ceiling on
that number would stop a sweep at a third of its real budget on the cheap models
and let the expensive ones run over. This delegates to
``sweep_report.derived_cost`` — the same tokens x audited-sheet arithmetic every
published cost view uses — rather than re-deriving it here.

An UNPRICED model id is not free. ``derived_cost`` returns None when the sheet
has no row (``anthropic/claude-opus-5`` has none today), and this counts those
cells in a separate bucket that is reported on every tick and BLOCKS at zero
spend if it is the only thing running — a ceiling that cannot see what it is
spending is not a ceiling.

    py -3 budget_guard.py --ceiling 50 --runs-root C:/cb/runs \\
        --stop-flag runs/.sweep-stop --exclude claude-sonnet-5

Read-only except for the stop flag. Never edits a run record.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sweep_report import derived_cost  # noqa: E402  -- the ONE cost derivation


def _row(result_path: Path):
    """One cell as ``derived_cost`` wants it, or None when unreadable."""
    try:
        r = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    a = r.get("agent") or {}
    if not isinstance(a, dict):
        a = {}
    return {
        "model": (r.get("model") or "").split(":", 1)[-1],
        "verdict": r.get("overall") or "?",
        "tin": a.get("tokens_in") or 0,
        "tout": a.get("tokens_out") or 0,
        "crd": a.get("cache_read_tokens") or 0,
        "ccr": a.get("cache_creation_tokens") or 0,
        "recorded": a.get("cost_usd") or 0.0,
    }


def tally(runs_root: Path, exclude):
    """(derived_total, unpriced_cells, n_cells, recorded_total) over every cell."""
    total = recorded = 0.0
    unpriced = cells = 0
    for p in runs_root.rglob("result.json"):
        row = _row(p)
        if row is None or row["model"] in exclude:
            continue
        cells += 1
        recorded += row["recorded"]
        c = derived_cost(row)
        if c is None:
            unpriced += 1
        else:
            total += c
    return total, unpriced, cells, recorded


#: Share of BILLABLE TOKENS the sheet may fail to price before the ceiling is
#: declared blind. Deliberately a share of TOKENS, not of CELLS: the risk is
#: proportional to volume, so one 2M-token cell counted at $0 defeats a ceiling
#: that a hundred 2k-token strays would not.
BLIND_TOKEN_SHARE = 0.15


def blind_share(runs_root: Path, exclude):
    """(unpriced_tokens, all_tokens, unpriced_model_ids) over every cell.

    THE HOLE THIS CLOSES. The blind-spend refusal below fired only when EVERY
    cell was unpriced. A run where the EXPENSIVE model is the unpriced one --
    exactly `anthropic/claude-opus-5`, which the 2026-08-19 audit skipped on
    purpose ("opus-5 is newer but a different tier") -- printed one soft
    `UNPRICED: n cell(s) counted at $0` line and kept going, with the ceiling
    blind to the single largest cost in the grid. Found as a hazard while block
    1 ran, before the opus phase could reach it.

    Tokens, not cells, because that is what the blindness is proportional to.
    Cache reads count: at the 92-98% hit rates these runs see, cache IS most of
    the volume, and omitting it would make a huge unpriced cell look small.
    """
    unpriced_tok = all_tok = 0
    ids = set()
    for path in runs_root.rglob("result.json"):
        row = _row(path)
        if row is None or row["model"] in exclude:
            continue
        tok = row["tin"] + row["tout"] + row["crd"] + row["ccr"]
        all_tok += tok
        if derived_cost(row) is None:
            unpriced_tok += tok
            ids.add(row["model"])
    return unpriced_tok, all_tok, ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ceiling", type=float, required=True, help="USD")
    ap.add_argument("--runs-root", type=Path, required=True)
    ap.add_argument("--stop-flag", type=Path, required=True)
    ap.add_argument("--exclude", default="",
                    help="comma-separated model ids left out of the ceiling")
    ap.add_argument("--poll-s", type=float, default=60.0)
    ap.add_argument("--once", action="store_true", help="report and exit")
    ap.add_argument("--no-refuse-blind", dest="refuse_blind",
                    action="store_false", default=True,
                    help="keep going even when every cell is unpriced and the "
                         "ceiling therefore measures nothing")
    a = ap.parse_args(argv)

    exclude = {s.strip() for s in a.exclude.split(",") if s.strip()}
    while True:
        total, unpriced, cells, recorded = tally(a.runs_root, exclude)
        # Both numbers, always. The gap between them IS the finding the price
        # audit exists for, and hiding it would quietly re-establish trust in
        # the figure §5 says not to trust.
        line = (f"spend ${total:,.2f} / ${a.ceiling:,.2f} over {cells} cell(s) "
                f"[recorded says ${recorded:,.2f}]")
        if unpriced:
            line += f"  UNPRICED: {unpriced} cell(s) counted at $0"
        print(line, flush=True)
        # BLIND SPEND. Cells are being graded, every one of them is unpriced, and
        # the derived total is therefore $0 no matter how much the run actually
        # costs. A ceiling that cannot see its own spend is not a ceiling, so it
        # stops rather than pretending. `anthropic/claude-opus-5` is exactly this
        # case today: no row in the audited sheet, and the sheet is dated on
        # purpose -- inventing a price from memory is what §9 forbids
        # ("costs derive from tokens x a dated sheet, never from a remembered
        # price"), so the fix is to AUDIT a row, not to guess one here.
        if a.refuse_blind and cells and unpriced:
            u_tok, all_tok, ids = blind_share(a.runs_root, exclude)
            share = (u_tok / all_tok) if all_tok else 1.0
            if unpriced == cells or share >= BLIND_TOKEN_SHARE:
                a.stop_flag.parent.mkdir(parents=True, exist_ok=True)
                a.stop_flag.write_text("budget_guard: blind spend\n",
                                       encoding="utf-8")
                scope = (f"all {cells} cell(s)" if unpriced == cells
                         else f"{unpriced} of {cells} cell(s), "
                              f"{share:.0%} of billable tokens")
                print(f"BLIND SPEND - {scope} are unpriced, so the ceiling "
                      f"cannot see that spend. Unpriced: "
                      f"{', '.join(sorted(ids)) or '(unknown)'}. Dropped "
                      f"{a.stop_flag}. Add an AUDITED row to "
                      "sweep_report.PRICE_SHEET (do not guess one) or pass "
                      "--no-refuse-blind to spend without a ceiling.",
                      flush=True)
                return 2
        if total >= a.ceiling:
            a.stop_flag.parent.mkdir(parents=True, exist_ok=True)
            a.stop_flag.write_text("budget_guard: ceiling reached\n",
                                   encoding="utf-8")
            print(f"CEILING REACHED — dropped {a.stop_flag}; the sweep stops at "
                  "the next cell boundary (in-flight cell still graded + audited)",
                  flush=True)
            return 0
        if a.once:
            return 0
        time.sleep(a.poll_s)


if __name__ == "__main__":
    sys.exit(main())
