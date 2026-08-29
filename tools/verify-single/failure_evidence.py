"""Preserve the log a NON-PASSING layer wrote, before the workdir is deleted.

WHY THIS EXISTS. ``run_task``'s cleanup is VERDICT-BLIND — its ``finally`` runs
``robust_rmtree(workdir)`` whether the run passed or failed — so the one artifact
that can name a build failure, ``out/l1_build.log``, is destroyed precisely on
the runs that need it. ``workdir_retention``'s "never slim a failed L1" guard
does NOT cover this: that guard governs only workdirs a batch deliberately KEPT
(``--keep-workdir``), and on the DEFAULT path there is no retention decision at
all, because ``run_task`` mints the tempdir itself and removes it itself. So the
protection reads as if it covers every failure and covers none of the common
ones.

MEASURED COST OF NOT HAVING IT (2026-08-14). A 63-reference sweep returned one
L1 FAIL — ``target ThirdPersonEditor: exit 0`` / ``target ThirdPerson: exit 1``
— on bytes that had PASSED in the two prior sweeps and PASSED again on re-run.
Its cause is still unknown, and is now unknowable: the workdir was already gone
when anyone went to look, so nobody can say whether it was a lost build mutex, a
transient write failure, or a real intermittent compile break. One byte-bounded
copy taken before the rmtree would have answered it.

DIAGNOSTIC ONLY, and structurally unable to change a verdict: it is called after
the report has been written, it only ever WRITES (never reads back into a
report), every failure inside it is swallowed, and it refuses to write anywhere
except beside a report that already lives OUTSIDE the workdir.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping, Optional

# Bounds the bytes WRITTEN, not the characters read. UE and MSVC both emit
# localized text, and 64 KiB of it can encode to ~3x that (crash_evidence.py
# shipped that bug and had it caught in review) — so the cap is applied after
# encoding, and the file is opened with newline="" so Windows' \n -> \r\n
# translation cannot push the written file back over the line.
_EXCERPT_CAP_BYTES = 64 * 1024

# Lines worth lifting out of the middle of a long log. A build error is usually
# near the END (hence the tail below), but UBT can print the failing action
# early and then several thousand lines of unrelated link output, which a pure
# tail would bury. Deliberately a SMALL list of high-signal markers: a wide net
# here would fill the cap with warnings and push the actual error out.
_ERROR_MARKERS = (
    "error C",           # MSVC compile (C2065, C3859, ...)
    "fatal error",       # MSVC C1076 / LINK fatal
    "LINK : fatal",
    " error:",           # clang / gcc
    "ERROR:",            # UBT
    "Error executing",   # UBT action failure
    "Assertion failed",
)
_MAX_MARKER_LINES = 60
_MAX_COMPANIONS = 3


def _bounded_write(dst: Path, text: str) -> None:
    """Write ``text`` truncated so the FILE is at most _EXCERPT_CAP_BYTES."""
    body = text.encode("utf-8")[:_EXCERPT_CAP_BYTES].decode("utf-8", "ignore")
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)


def _excerpt(src: Path) -> Optional[str]:
    """Marker lines + the tail of ``src``, or None when it cannot be read."""
    try:
        raw = src.read_bytes()
    except OSError:
        return None
    size = len(raw)
    # Only the tail is decoded in full: a 200 MB log must not be materialized as
    # a str to take 64 KiB off the end. The marker scan reads the same tail plus
    # a bounded head, which is where UBT prints the action that failed.
    head = raw[: 256 * 1024]
    tail = raw[-(4 * _EXCERPT_CAP_BYTES):]
    scan = (head + b"\n" + tail).decode("utf-8", "replace").splitlines()

    hits: List[str] = []
    seen = set()
    for line in scan:
        if any(m in line for m in _ERROR_MARKERS):
            k = line.strip()
            if k and k not in seen:
                seen.add(k)
                hits.append(line.rstrip())
            if len(hits) >= _MAX_MARKER_LINES:
                break

    out = [
        "# CraftBench failure evidence — %s" % src.name,
        "# original: %s (%d bytes)" % (src, size),
        "# this file is a BOUNDED EXCERPT (marker lines, then the tail), not the log.",
        "",
    ]
    if hits:
        out += ["=== matched error lines (%d) ===" % len(hits), *hits, ""]
    out += ["=== tail ===", tail.decode("utf-8", "replace")]
    return "\n".join(out)


def _companions(log: Path) -> List[Path]:
    """Sibling logs the layer's own log defers to, e.g. ``l2_pie_nullrhi.log``.

    Not scope creep — the difference between keeping evidence and keeping the
    WRONG file. On an L2 fallback the layer's ``log`` is the full-RHI RETRY, and
    its own notes say "the -nullrhi attempt's log is preserved at
    l2_pie_nullrhi.log — read THAT to learn why the headless run produced
    nothing". Preserving only the pointed-FROM file answers the wrong question.
    """
    try:
        sibs = sorted(log.parent.glob(log.stem + "_*.log"))
    except OSError:
        return []
    return [s for s in sibs if s.is_file()][:_MAX_COMPANIONS]


def _dest_name(report_json_path: Path, log: Path) -> str:
    base = report_json_path.stem            # "<task>.report" for batch-eval
    if base.endswith(".report"):
        base = base[: -len(".report")]
    return "%s.%s.excerpt.log" % (base, log.stem)


def preserve(
    layers: Mapping[str, Any],
    *,
    report_json_path: Path,
    workdir: Path,
) -> List[Path]:
    """Copy a bounded excerpt of every NON-PASSING layer's log beside the report.

    Returns the paths written (empty on every no-op). Callers must treat this as
    advisory: an empty return is normal, and never means anything is wrong.

    Refuses, silently, when:
      * every layer passed — there is nothing anyone would come looking for;
      * the destination directory is INSIDE ``workdir`` — it would be deleted by
        the same rmtree this exists to survive, so writing there is worse than
        not writing at all (it looks like evidence was kept);
      * a layer's ``log`` is absent, or does not point at a real file.
    """
    try:
        dest_dir = report_json_path.resolve().parent
        wd = workdir.resolve()
    except OSError:
        return []
    if dest_dir.is_relative_to(wd):   # True for dest_dir == wd as well
        return []

    written: List[Path] = []
    for name in sorted(layers):
        layer = layers[name]
        status = getattr(layer, "status", None)
        if status is None and isinstance(layer, dict):
            status = layer.get("status")
        if status == "pass":
            continue
        log = getattr(layer, "log", None)
        if log is None and isinstance(layer, dict):
            log = layer.get("log")
        if not log:
            continue
        src = Path(str(log))
        if not src.is_file():
            continue
        for candidate in (src, *_companions(src)):
            text = _excerpt(candidate)
            if text is None:
                continue
            dst = dest_dir / _dest_name(report_json_path, candidate)
            try:
                _bounded_write(dst, text)
            except OSError:
                continue
            written.append(dst)
    return written
