#!/usr/bin/env python3
"""Publish a run's SMALL result artefacts into the tracked ``results/`` tree.

WHY THIS EXISTS. Two machines (this box and the build machine) need to pool graded results,
and the obvious move — un-ignore ``runs/`` — does not survive measurement:
``runs/`` was **29 GB**, of which 27.4 GB was ``.pch``/``.obj``/``.pdb`` build
artefacts in three kept workdirs. Tracking that tree means writing exclusion
rules inside it, i.e. a DENYLIST, and the next artefact type UE invents lands in
a commit by default.

The result artefacts themselves are **0.9 MB across 212 files**. So this is an
ALLOWLIST: only the files named below are copied, and nothing else can ride
along. ``runs/`` stays gitignored.

TWO DESIGN POINTS THAT MATTER FOR SHARING:

* **Paths are host-scoped** (``results/<host>/<run-id>/``). Both machines add
  files on the same branch; if they wrote to the same paths, every pull would be
  a conflict over binary-ish JSON. Host-scoped paths merge cleanly by
  construction, and the host is recoverable from the path when reading results
  back.
* **Excerpt logs are published as ``.txt``**, because ``.gitignore`` ignores
  ``*.log`` repo-wide. Publishing them as ``.log`` would silently drop the one
  artefact that explains a FAIL — the exact failure mode this repo keeps hitting,
  where a mechanism exists and is unreachable.

Deliberately NOT copied: the workdir, ``project-lean/``, screenshots, the L2
report HTML. Those are diagnosis material that belongs on the machine that
produced them; a path to them is recorded in the manifest instead.

Usage:
    python tools/run-agent/publish_results.py runs/_archive/2026-08-24/discriminate/*
    python tools/run-agent/publish_results.py <run-dir> --host <build-host> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

#: Result files worth sharing. Names, not globs: an allowlist that cannot widen
#: by accident.
RESULT_NAMES = ("summary.json", "result.json", "report.json", "verdict.json")

#: Failure evidence. Published with a `.txt` suffix because `*.log` is ignored
#: repo-wide -- see the module docstring.
EXCERPT_SUFFIXES = (".excerpt.log",)

#: A published excerpt is truncated to this many bytes. The point is to explain a
#: FAIL in a review, not to ship a build log; the full one stays on the producing
#: machine and the manifest records where.
EXCERPT_CAP = 64 * 1024


def host_name(explicit: Optional[str] = None) -> str:
    """The machine label used as the top path segment."""
    name = explicit or os.environ.get("CB_HOST") or socket.gethostname() or "unknown"
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in name).strip("-") or "unknown"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(run_dir: Path) -> List[Path]:
    """Every publishable file under ``run_dir``, sorted for a stable manifest."""
    out: List[Path] = []
    for p in sorted(run_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name in RESULT_NAMES or p.name.endswith(EXCERPT_SUFFIXES):
            out.append(p)
    return out


def publish(run_dir: Path, results_root: Path, host: str,
            check: bool = False) -> Dict:
    """Copy one run's result artefacts. Returns the manifest dict."""
    run_dir = Path(run_dir)
    files = collect(run_dir)
    dest_root = results_root / host / run_dir.name
    entries = []
    for src in files:
        rel = src.relative_to(run_dir)
        # Excerpts change suffix so the repo-wide *.log ignore cannot eat them.
        rel_out = rel.with_name(rel.name + ".txt") if rel.name.endswith(EXCERPT_SUFFIXES) else rel
        dest = dest_root / rel_out
        entries.append({
            "source": str(rel).replace(os.sep, "/"),
            "published": str(rel_out).replace(os.sep, "/"),
            "bytes": src.stat().st_size,
            "sha256": _sha256(src),
        })
        if check:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel_out != rel:
            data = src.read_bytes()[:EXCERPT_CAP]
            dest.write_bytes(data)
        else:
            shutil.copy2(src, dest)

    manifest = {
        "run": run_dir.name,
        "host": host,
        # Where the heavy diagnosis material stayed. Recorded rather than copied:
        # a reader on the other machine needs to know it exists and is not here.
        "source_run_dir": str(run_dir).replace(os.sep, "/"),
        "files": entries,
        "published_files": len(entries),
        "published_bytes": sum(e["bytes"] for e in entries),
        "not_published": ("workdirs, project-lean/, screenshots and the L2 report "
                          "HTML stay on the producing machine"),
    }
    if not check and entries:
        dest_root.mkdir(parents=True, exist_ok=True)
        (dest_root / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--host", default=None,
                    help="machine label (default: $CB_HOST, else hostname)")
    ap.add_argument("--check", action="store_true",
                    help="report what would be published; write nothing")
    a = ap.parse_args(argv)

    host = host_name(a.host)
    total_f = total_b = 0
    skipped = []
    for d in a.run_dirs:
        if not d.is_dir():
            skipped.append(str(d))
            continue
        m = publish(d, a.results_root, host, check=a.check)
        if not m["published_files"]:
            skipped.append(str(d) + " (no result artefacts)")
            continue
        total_f += m["published_files"]
        total_b += m["published_bytes"]
        print("  %-58s %2d file(s)  %6.1f KB -> %s"
              % (d.name[:58], m["published_files"], m["published_bytes"] / 1024,
                 (a.results_root / host / d.name).as_posix()))
    verb = "would publish" if a.check else "published"
    print("%s %d file(s), %.1f KB under %s/%s/"
          % (verb, total_f, total_b / 1024, a.results_root.as_posix(), host))
    for s in skipped:
        print("  skipped: %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
