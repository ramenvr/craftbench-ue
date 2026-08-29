"""Watch the repo-level fairness hide for the duration of a drive.

run.py's breach gate reports THAT the hide fell (post-drive); this reports WHEN
and alongside WHAT, which is the part that identifies the resurrector. Poll-only
and append-only: it never renames anything, because a watcher that repairs the
tree would race the run it is observing.

Usage:  py -3.12 hide_watch.py --out runs/hide-watch.jsonl [--interval 5]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
PREFIX = ".cb-fairness-hidden__"
TARGETS = ("tasks", "tools/verify-single", ".git")


def _state() -> dict:
    out = {}
    for rel in TARGETS:
        src = REPO / rel
        park = src.parent / (PREFIX + src.name)
        out[rel] = ("live" if src.exists() else "-") + \
                   ("+park" if park.exists() else "")
    return out


def _processes() -> list:
    """Image names only, best effort — psutil is absent under this box's python."""
    try:
        cp = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                            capture_output=True, text=True, timeout=20)
        names = {ln.split('","')[0].lstrip('"') for ln in
                 cp.stdout.splitlines() if ln.startswith('"')}
        return sorted(names)
    except Exception as e:
        return [f"<unavailable: {type(e).__name__}>"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=5.0)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    def emit(event, **kw):
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "event": event, **kw}
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    prev = _state()
    emit("start", state=prev, pid=os.getpid())
    while True:
        time.sleep(a.interval)
        cur = _state()
        if cur == prev:
            continue
        # A target going "live" while its park survives is the breach signature:
        # the park proves this run hid it, the live copy proves something undid it.
        breached = [r for r, v in cur.items()
                    if v.startswith("live") and "+park" in v
                    and not prev[r].startswith("live")]
        emit("change", state=cur, was=prev,
             **({"breached": breached, "processes": _processes()}
                if breached else {}))
        prev = cur


if __name__ == "__main__":
    sys.exit(main())
