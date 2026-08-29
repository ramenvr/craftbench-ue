"""Per-run behavior audit from agent transcripts: verifier-read exposure + self-test rounds.

Two disclosure columns for every run (stdlib-only, token-free post-processing):

  verifier_reads_real   tool_results that returned REAL CraftBenchTests content
                        (fixture sources / base classes / AGENT_WRITABLE.json).
                        A read that returned the fairness stub does NOT count —
                        the defense working is not an exposure.
  verifier_reads_stub   reads answered by the fairness stub (defense fired).
  pie_rounds            self-test play sessions the agent ran (start_pie count,
                        including ones issued through unreal-mcp's call_tool).

Why this exists (2026-08-19): calibration transcripts showed aura-mcp runs
reading the CURRENT task's fixture in full (checkpoint schedule, tags,
tolerances) because _run_live_project's fairness hide was gated to other
backends. The gate is now removed (test_fairness_isolation.py::
TestHideIsUnconditionalOnTheLivePath); this audit is the standing per-run
disclosure that lets any published result state, run by run, whether the graded
work was produced with verifier internals visible. Calibration-era runs will show
nonzero verifier_reads_real — that is the honest record, not a bug.

Usage:
  python tools/run-agent/transcript_audit.py --runs-root <runs-dir> [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

STUB_MARKER = "fairness stub"
# Any of these in a tool INPUT marks the call as touching verifier internals
# or committed answer material. Path-shaped tokens on purpose: the bare word
# "reference" false-positives on prose ("a reference to the actor"), so the
# tokens carry a path separator or a unique filename.
VERIFIER_TOKENS = ("CraftBenchTests", "AGENT_WRITABLE.json", "verify-single",
                   "reference/", "reference\\", "/aids", "\\aids",
                   "author_reference", "REFERENCE-NOTE", "discrimination")
# A result counts as REAL content only if it carries something a fixture /
# manifest BODY would carry. A `find`/Glob listing of path names is exposure
# of structure, not of test points, and carries none of these; the fairness
# stub carries none either. Length alone misclassifies long path listings
# (measured: an 895-char `find Source/CraftBenchTests` listing).
CONTENT_MARKERS = ("#include", "UCLASS", "OnCheckpoint", "SetCheckpointSchedule",
                   "PrepareTest", '"writable"', '"deny"',
                   # answer-material bodies: introspect scripts / authoring
                   # aids (python), reference notes (markdown prose)
                   "import unreal", "def ", "self-grade", "SELF-GRADE",
                   "Reference solution", "reference solution")


def _iter_blocks(tpath: Path):
    for line in tpath.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if not isinstance(j, dict):
            continue          # some adapters write bare-array lines; skip them
        msg = j.get("message")
        if not isinstance(msg, dict):
            continue
        for blk in (msg.get("content") or []):
            if isinstance(blk, dict):
                yield blk


def _result_text(blk) -> str:
    content = blk.get("content")
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


def audit_run(run_dir: Path) -> dict | None:
    tpath = run_dir / "agent_transcript.jsonl"
    if not tpath.is_file():
        return None
    pending = {}          # tool_use_id -> True for verifier-touching calls
    real = stub = 0
    pie_rounds = 0
    for blk in _iter_blocks(tpath):
        btype = blk.get("type")
        if btype == "tool_use":
            s = json.dumps(blk.get("input", {}))
            if any(t in s for t in VERIFIER_TOKENS):
                pending[blk.get("id")] = True
            if blk.get("name", "").endswith("start_pie") or '"start_pie"' in s:
                pie_rounds += 1
        elif btype == "tool_result" and blk.get("tool_use_id") in pending:
            pending.pop(blk["tool_use_id"])
            text = _result_text(blk)
            if STUB_MARKER in text:
                stub += 1
            elif any(m in text for m in CONTENT_MARKERS):
                real += 1
            # marker-free results (path listings, errors) count as neither
    result = {}
    rj = run_dir / "result.json"
    if rj.is_file():
        try:
            result = json.loads(rj.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            pass
    return {
        "run": run_dir.name,
        "lane": run_dir.parent.name,
        "model": result.get("model"),
        "verdict": result.get("overall"),
        "verifier_reads_real": real,
        "verifier_reads_stub": stub,
        "pie_rounds": pie_rounds,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", required=True)
    ap.add_argument("--csv", help="also write rows to this CSV path")
    args = ap.parse_args(argv)
    rows = []
    for lane_dir in sorted(Path(args.runs_root).iterdir()):
        if not lane_dir.is_dir():
            continue
        for run_dir in sorted(lane_dir.iterdir()):
            if run_dir.is_dir():
                row = audit_run(run_dir)
                if row:
                    rows.append(row)
    flagged = [r for r in rows if r["verifier_reads_real"] or r["pie_rounds"]]
    for r in rows:
        mark = "  <-- EXPOSED" if r["verifier_reads_real"] else ""
        print(f"{r['lane']:12} {r['run'][:58]:58} {str(r['verdict']):14} "
              f"real={r['verifier_reads_real']} stub={r['verifier_reads_stub']} "
              f"pie={r['pie_rounds']}{mark}")
    print(f"\n{len(rows)} runs audited; {len(flagged)} with real verifier reads "
          f"or self-test rounds")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                               ["run"])
            w.writeheader()
            w.writerows(rows)
        print(f"CSV -> {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
