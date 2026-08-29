#!/usr/bin/env python3
"""Audit EVERY run under a runs root for answer-key material, and report by LANE.

One command, one table, one decision. This exists because the per-run detector
(``leak_audit.py``) answers "was this cell contaminated?" and the question that
actually decides whether a sweep is worth continuing is different:

    is ONE LANE contaminated more than the other?

That distinction is the whole point. A leak spread evenly across arms is a
harness defect that costs cells. A leak concentrated in ONE arm is not a defect,
it is a CONFOUND: the benchmark's central claim is a (model x tool x surface)
interaction, and an arm that reads answer material from its own content index has
an information advantage that is not a tool-layer capability. Measured example
behind this file: the 2026-08-22 harness-issues review item 5 --
Aura's inspector index answered from a cache built BEFORE the fairness hide, so
`agent_transcript.jsonl:192` carried a verbatim fixture comment including the
checkpoint schedule while the on-disk fixture was stubbed. No filesystem hide can
close that, and it can only affect arm C.

DELEGATES to ``leak_audit.audit`` rather than re-deriving the marker sets: two
answers to "is this a leak?" is how one of them goes quietly stale, and the
confidence split (park = exposure, warn; answer/fixture = consumption, void) is a
judgement call that belongs in exactly one place.

Reads task ids through ``runlib.run_identity`` for the same reason. It does NOT
parse the run DIRECTORY name: real names look like
``20260821-020717-t1-dawn-fog-lighting-rig-unreal-mcp-qwen_qwen3.8-max``, where
the task id and the model slug are joined by the same ``-`` that appears inside
both, so any split is a guess.

Usage:
    py -3 tools/run-agent/leak_audit_sweep.py [RUNS_ROOT] [--void] [--json OUT]

    RUNS_ROOT   defaults to C:/cb/runs (the sweep's own default).
    --void      rewrite each CONSUMING run's verdict to FAIRNESS-BREACH.
                Omit it for a read-only survey -- which is what you want first.
    --json OUT  also write the machine-readable summary, for pasting back.

Exit 0 = no consumption anywhere, 1 = at least one contaminated run,
2 = the runs root does not exist / holds no runs.
Read-only without --void. No editor, no UE, no tokens, no machine contention.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_RUNLIB = _HERE.parent / "runlib"
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))

from leak_audit import audit  # noqa: E402  -- the ONE detector

CONSUMING = ("answer", "fixture")   # leak_audit's own confidence split
DEFAULT_RUNS_ROOT = Path("C:/cb/runs")


def _graded(verdict: object) -> bool:
    """Is ``verdict`` one the pass rate counts? Asked of the harness, not guessed."""
    try:
        from adapters.base import is_graded_verdict
        return bool(is_graded_verdict(verdict))
    except Exception:                                    # noqa: BLE001
        return False


#: Set once, so a resolver failure is stated ONCE instead of printing "?" on
#: every row. A broad `except -> "?"` is how this function shipped its first
#: version: it swallowed an AttributeError (the API is `identify`, not
#: `identity_of`) and every task column read "?" while the table looked complete.
_TASK_ID_FAILURE: list = []


def _task_id(record: dict) -> str:
    """The task id via ``runlib.run_identity`` — the ONE implementation.

    Never parses the run directory name: real names join the task id and the
    model slug with the same ``-`` that appears inside both, so any split is a
    guess.
    """
    try:
        from run_identity import identify
    except Exception as exc:                             # noqa: BLE001
        if not _TASK_ID_FAILURE:
            _TASK_ID_FAILURE.append(f"could not import run_identity: {exc}")
        return "?"
    try:
        return str(identify(record).task_id)
    except Exception as exc:                             # noqa: BLE001
        if not _TASK_ID_FAILURE:
            _TASK_ID_FAILURE.append(f"run_identity.identify raised: {exc}")
        return "?"


def _lane(run_dir: Path, record: dict) -> str:
    """The arm. TWO independent sources, and a disagreement is REPORTED.

    ``result.json``'s ``model`` is ``<backend>:<model>``; the run also physically
    sits in ``runs/<lane>/``. Both are authoritative-looking and they can only
    disagree if a run was moved or written by something unexpected -- exactly the
    case where silently picking one manufactures a clean-looking table.
    """
    from_dir = run_dir.parent.name
    raw = str(record.get("model") or "")
    from_rec = raw.split(":", 1)[0] if ":" in raw else ""
    if from_rec and from_dir and from_rec != from_dir:
        return f"MISMATCH({from_dir}!={from_rec})"
    return from_rec or from_dir or "?"


def _model(record: dict) -> str:
    raw = str(record.get("model") or "")
    return raw.split(":", 1)[1] if ":" in raw else (raw or "?")


def scan(runs_root: Path) -> list:
    rows = []
    for lane_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        for run_dir in sorted(p for p in lane_dir.iterdir() if p.is_dir()):
            rj = run_dir / "result.json"
            record = {}
            if rj.is_file():
                try:
                    record = json.loads(rj.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    record = {}
            hits = audit(run_dir)
            has_transcript = (run_dir / "agent_transcript.jsonl").is_file()
            consumed = sorted(k for k in hits if k in CONSUMING)
            if consumed:
                state = "LEAK"
            elif hits:
                state = "EXPOSED"
            elif has_transcript:
                state = "clean"
            else:
                state = "no-transcript"
            rows.append({
                "run": run_dir.name,
                "dir": str(run_dir),
                "lane": _lane(run_dir, record),
                "task": _task_id(record),
                "model": _model(record),
                "verdict": record.get("overall"),
                "graded": _graded(record.get("overall")),
                "state": state,
                "markers": {k: len(v) for k, v in sorted(hits.items())},
                "first_lines": {k: v[0] for k, v in sorted(hits.items())},
            })
    return rows


def _void(rows: list) -> int:
    """Rewrite each CONSUMING run's verdict. Delegates to leak_audit's own main
    so the voided record's shape and reason string have one author."""
    import leak_audit
    n = 0
    for r in rows:
        if r["state"] != "LEAK":
            continue
        if leak_audit.main([r["dir"], "--void"]) == 1:
            n += 1
    return n


def report(rows: list, out: object = sys.stdout) -> None:
    def w(s=""):
        print(s, file=out)

    order = {"LEAK": 0, "EXPOSED": 1, "no-transcript": 2, "clean": 3}
    w("=== every run, worst first "
      "(LEAK = read answer material; EXPOSED = saw the park, did not read it) ===")
    w(f"{'STATE':<14}{'LANE':<12}{'GRADED':<8}{'TASK':<44}{'MODEL':<30}"
      f"{'VERDICT':<18}MARKERS")
    for r in sorted(rows, key=lambda r: (order.get(r["state"], 9), r["lane"],
                                         r["task"], r["model"])):
        marks = ", ".join(f"{k}x{v}@{r['first_lines'][k]}"
                          for k, v in r["markers"].items()) or "-"
        w(f"{r['state']:<14}{r['lane']:<12}{'yes' if r['graded'] else 'no':<8}"
          f"{r['task'][:43]:<44}{r['model'][:29]:<30}"
          f"{str(r['verdict'])[:17]:<18}{marks}")

    lanes = sorted({r["lane"] for r in rows})
    w()
    w("=== by lane ===")
    w(f"{'LANE':<12}{'cells':>7}{'graded':>8}{'LEAK':>7}{'exposed':>9}"
      f"{'clean':>7}{'no-tx':>7}")
    for ln in lanes:
        sub = [r for r in rows if r["lane"] == ln]
        w(f"{ln:<12}{len(sub):>7}{sum(1 for r in sub if r['graded']):>8}"
          f"{sum(1 for r in sub if r['state'] == 'LEAK'):>7}"
          f"{sum(1 for r in sub if r['state'] == 'EXPOSED'):>9}"
          f"{sum(1 for r in sub if r['state'] == 'clean'):>7}"
          f"{sum(1 for r in sub if r['state'] == 'no-transcript'):>7}")

    w()
    w("=== THE NUMBER THE DECISION HANGS ON: leaks among GRADED cells, per lane ===")
    w("    (a leak in a non-graded cell cost time; a leak in a GRADED one is in "
      "the results)")
    for ln in lanes:
        sub = [r for r in rows if r["lane"] == ln and r["graded"]]
        bad = sum(1 for r in sub if r["state"] == "LEAK")
        pct = f"{100.0 * bad / len(sub):.0f}%" if sub else "n/a"
        w(f"    {ln:<12} {bad}/{len(sub)} graded cells contaminated ({pct})")
    w()
    w("    EVEN across lanes -> a harness defect: void those cells and re-run them.")
    w("    CONCENTRATED in one lane -> a CONFOUND, not a defect. That lane's")
    w("    tool-layer comparison is not measuring the tool layer, and finishing")
    w("    the grid does not fix it. Stop, close the leak, re-run that lane.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_root", nargs="?", default=str(DEFAULT_RUNS_ROOT))
    ap.add_argument("--void", action="store_true",
                    help="rewrite each contaminated run's verdict to "
                         "FAIRNESS-BREACH (omit for a read-only survey)")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the summary as JSON, for pasting back")
    a = ap.parse_args(argv)

    root = Path(a.runs_root)
    if not root.is_dir():
        print(f"no such runs root: {root}", file=sys.stderr)
        return 2
    rows = scan(root)
    if not rows:
        print(f"no runs under {root}", file=sys.stderr)
        return 2

    report(rows)
    if a.void:
        n = _void(rows)
        print(f"\nvoided {n} run(s) -> FAIRNESS-BREACH", file=sys.stderr)
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"wrote {a.json_out}", file=sys.stderr)
    return 1 if any(r["state"] == "LEAK" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
