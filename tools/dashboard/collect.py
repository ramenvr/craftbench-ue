"""On-disk discovery for the CraftBench dashboard — PURE STDLIB, read-only.

``collect(repo_root)`` is the SINGLE entry point both UIs call. It never launches
a run, never shells out, never writes: it globs ``runs/**/result.json`` and the
task specs (both layouts — flat ``tasks/[<set>/]<id>.md`` and folder-per-task
``tasks/<set>/<id>/task.md``) and parses them into a frozen ``model.Snapshot``.

Three parse surfaces, all mirroring existing repo code so the dashboard tracks
the source of truth instead of forking it:

1. **Task metadata + declared layers** — THE single task-spec parser,
   ``tools/verify-single/spec.py::parse_task_file`` (v2 front matter with the
   legacy H2 fallback), bridged onto ``sys.path`` exactly like
   ``aura_rig/tasks.py`` does. Title + prompt excerpt stay local (presentation
   concerns, not spec grammar).

2. **Per-layer L1/L2/L2I/L3/ART/R2 results** — PREFERRED source: an embedded
   ``result.json.verifier`` dict (new runs embed the verify-single report, whose
   ``layers`` map is the machine contract in ``report.py::Report.to_dict``).
   FALLBACK for old runs (where ``verifier`` is null even on PASS): text-parse
   the sibling ``verifier_stdout.txt``, whose format is
   ``report.py::Report.render_text()``. The text parse is best-effort: any
   surprise yields ``[]`` and the coarse ``result.json.overall`` stays
   authoritative (open-risk #1).

3. **Which task a run belongs to** — THE single implementation,
   ``tools/runlib/run_identity.py``, bridged the same way. It accepts both
   writer shapes (``run.py``'s ``task`` path and ``run_graded.py``'s bare
   ``task_id``) and both path separators, and reports ``UNKNOWN`` rather than
   guessing.

Phase-3 capture artifacts: each run may carry a ``<run_dir>/artifacts/`` dir of
swept screenshots; ``parse_run`` attaches the sorted ``*.png`` basenames as
``Run.artifacts`` (``[]`` when the dir is absent — the default for every run
recorded before capture existed).

The compare skip rule (drop any ``result.json`` lacking a non-empty ``model``)
excludes the aura-smoke ``iter-1`` records and other non-product JSON.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import pathlib
import re
import sys
from typing import Callable, Dict, List, Optional, Tuple

from .model import LAYER_KEYS, LayerResult, Run, Snapshot, Task, _iso_z

# ---------------------------------------------------------------------------
# Task-spec parsing — THE single parser lives in tools/verify-single (a
# non-importable dir name); bridge it onto sys.path, same pattern as
# aura_rig/tasks.py. spec.py is stdlib-only, so the data layer stays pure.
# ---------------------------------------------------------------------------

_VERIFY_SINGLE = pathlib.Path(__file__).resolve().parents[1] / "verify-single"
if str(_VERIFY_SINGLE) not in sys.path:
    sys.path.insert(0, str(_VERIFY_SINGLE))

import spec as _taskspec  # noqa: E402  (tools/verify-single/spec.py)

# ---------------------------------------------------------------------------
# "Which task is this run?" — THE single implementation, tools/runlib/
# run_identity.py, bridged the same way. Imported, never copied: this file's own
# answer used to be ``PurePosixPath(task).stem``, which never splits a WINDOWS
# path, so on the real corpus (2026-08-19) every run id was a whole
# ``C:\...\tasks\bp\<id>\task`` string and 0 of 18 joined the task tree —
# ``coverage_gaps`` therefore reported every task unattempted. Stdlib-only, so
# the data layer stays pure.
# ---------------------------------------------------------------------------
_RUNLIB = pathlib.Path(__file__).resolve().parents[1] / "runlib"
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))

import run_identity as _run_identity  # noqa: E402  (tools/runlib/run_identity.py)

# Canonical layer keys we surface (declared-layer values are filtered to these).
_KNOWN_LAYERS = set(LAYER_KEYS)

_PROMPT_EXCERPT_MAX = 600

# Non-task docs that live alongside specs in the task-set dirs. ``task.md``
# guards against a folder-form spec misplaced DIRECTLY in a set dir (it belongs
# one level down, at tasks/<set>/<id>/task.md). Mirrors aura_rig/tasks.py.
_TASK_SKIP_NAMES = {"README.md", "CATALOG.md", "task.md"}

# The spec filename inside a folder-form task dir (tasks/<set>/<id>/task.md).
_TASK_SPEC_NAME = "task.md"


def _split_h2_sections(markdown: str) -> Dict[str, str]:
    """Map H2 heading text -> body up to the next H2 (verbatim from run_task.py)."""
    out: Dict[str, str] = {}
    current_heading: Optional[str] = None
    current_lines: List[str] = []
    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if current_heading is not None:
                out[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        out[current_heading] = "\n".join(current_lines).strip()
    return out


def _parse_title(raw: str) -> str:
    """The first H1 ('# <text>') line; '' when absent (it equals task_id today)."""
    for line in raw.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return ""


def _parse_prompt_excerpt(sections: Dict[str, str]) -> str:
    """Blockquote of '## Prompt given to the agent', '> ' stripped, truncated.

    Each non-empty line of the section is a blockquote line beginning with '> '
    (or a bare '>'); we strip that prefix and join. Truncated to 600 chars with a
    trailing ellipsis when longer.
    """
    block = sections.get("Prompt given to the agent", "")
    if not block:
        return ""
    out_lines: List[str] = []
    for line in block.splitlines():
        s = line.rstrip()
        if s.startswith("> "):
            out_lines.append(s[2:])
        elif s == ">":
            out_lines.append("")
        else:
            out_lines.append(s)
    text = "\n".join(out_lines).strip()
    if len(text) > _PROMPT_EXCERPT_MAX:
        text = text[:_PROMPT_EXCERPT_MAX] + "…"
    return text


def _spec_task_id(path: pathlib.Path) -> str:
    """The bare task id a spec path denotes: the parent-dir name for the folder
    form (``.../<id>/task.md``), else the file stem (``.../<id>.md``)."""
    return path.parent.name if path.name == _TASK_SPEC_NAME else path.stem


def _is_task_spec(path: pathlib.Path) -> bool:
    return path.is_file() and path.suffix == ".md" and path.name not in _TASK_SKIP_NAMES


def _iter_task_specs(tasks_dir: pathlib.Path) -> List[pathlib.Path]:
    """Every task spec under ``tasks/``, BOTH layouts, deduped by bare task id.

    specs = ``tasks/*.md`` + ``tasks/<set>/*.md`` (skipping README/CATALOG/
    task.md) + ``tasks/<set>/*/task.md``; the id is the parent-dir name for the
    folder form, else the stem. This is a local mirror of the ``aura_rig/
    tasks.py`` enumeration — the data layer stays pure stdlib, so it cannot
    import the harness package. Dedupe matches the resolver there: within a set
    the folder form wins its flat same-id sibling; across sets the
    alphabetically-first set wins; a root ``tasks/<id>.md`` wins everything.
    Returned sorted by task id.
    """
    if not tasks_dir.is_dir():
        return []
    chosen: Dict[str, pathlib.Path] = {}
    for set_dir in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        by_id: Dict[str, pathlib.Path] = {}
        for p in sorted(set_dir.glob("*.md")):
            if _is_task_spec(p):
                by_id[p.stem] = p
        for d in sorted(p for p in set_dir.iterdir() if p.is_dir()):
            spec = d / _TASK_SPEC_NAME
            if spec.is_file():
                by_id[d.name] = spec        # folder form wins its flat sibling
        for tid, p in by_id.items():
            chosen.setdefault(tid, p)       # first set alphabetically wins a dup
    for p in sorted(tasks_dir.glob("*.md")):
        if _is_task_spec(p):
            chosen[p.stem] = p              # root wins any set-level dup
    return [chosen[k] for k in sorted(chosen)]


def parse_task(path: pathlib.Path) -> Task:
    """Parse one task spec (flat ``tasks/[<set>/]<id>.md`` or folder-form
    ``tasks/<set>/<id>/task.md``) into a frozen ``Task``.

    Structural facts come from ``spec.parse_task_file`` (v2 front matter, with
    the legacy H2 fallback built in). A parse failure never takes down the
    dashboard — the task renders uncategorized instead."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    sections = _split_h2_sections(raw)
    try:
        parsed = _taskspec.parse_task_file(path)
    except Exception:
        parsed = None  # malformed spec -> graceful uncategorized card
    task_id = (parsed.task_id if parsed else None) or _spec_task_id(path)
    return Task(
        task_id=task_id,
        title=_parse_title(raw) or task_id,
        capability_bucket=(parsed.capability_bucket if parsed else None) or "uncategorized",
        tier=(parsed.tier if parsed else None) or "",
        set_name=parsed.set_name if parsed else None,
        layers=[k for k in (parsed.layers if parsed else ()) if k in _KNOWN_LAYERS],
        prompt_excerpt=_parse_prompt_excerpt(sections),
        path=str(path.resolve()),
    )


# ---------------------------------------------------------------------------
# verifier_stdout.txt parsing — mirrors report.py::Report.render_text().
# ---------------------------------------------------------------------------

# A layer line: two leading spaces, a left-padded(3) key, " : ", UPPER status,
# optional "[extras]", optional " log=...". e.g.:
#   "  L1  : PASS    [exit=0, warn=4] log=/tmp/.../l1_build.log"
#   "  L2I : SKIPPED"
_LAYER_LINE_RE = re.compile(
    r"^  (?P<key>[A-Za-z0-9]{1,3})\s*: "
    r"(?P<status>[A-Z/]+)\s*"
    r"(?:\[(?P<extras>[^\]]*)\])?"
    r"(?:\s+log=\S+)?\s*$"
)
# An indented note under a layer line: eight spaces then "- <note>".
_NOTE_LINE_RE = re.compile(r"^        - (?P<note>.*)$")

# UPPERCASE stdout status -> normalized lowercase enum (model contract).
_STATUS_MAP = {
    "PASS": "pass",
    "FAIL": "fail",
    "SKIPPED": "skip",
    "SKIP": "skip",
    "ERROR": "error",
    "N/A": "n/a",
}


def parse_verifier_stdout(text: str) -> List[LayerResult]:
    """Best-effort parse of captured verifier stdout into ``LayerResult`` rows.

    Walks ``render_text`` output: each ``  KEY : STATUS [extras] log=...`` line
    starts a layer; subsequent ``        - note`` lines attach to it. ``detail``
    is the bracket extras joined to the newline-joined notes (None if neither).
    Unknown keys are skipped so prose / the 'overall' line never become layers.
    Returns ``[]`` on empty input or if nothing parses (the coarse overall stays
    authoritative — open-risk #1).
    """
    if not text:
        return []
    results: List[LayerResult] = []
    # accumulate (key, status, extras, [notes]) so notes can append after the line
    pending: Optional[Tuple[str, str, Optional[str], List[str]]] = None

    def _flush() -> None:
        if pending is None:
            return
        key, status, extras, notes = pending
        parts: List[str] = []
        if extras:
            parts.append(extras)
        parts.extend(notes)
        detail = "\n".join(parts) if parts else None
        results.append(LayerResult(key=key, status=status, detail=detail))

    for line in text.splitlines():
        m = _LAYER_LINE_RE.match(line)
        if m and m.group("key") in _KNOWN_LAYERS:
            _flush()
            extras = m.group("extras")
            pending = (
                m.group("key"),
                _STATUS_MAP.get(m.group("status"), m.group("status").lower()),
                extras.strip() if extras else None,
                [],
            )
            continue
        note = _NOTE_LINE_RE.match(line)
        if note and pending is not None:
            pending[3].append(f"- {note.group('note')}")
            continue
        # Any other line (header, 'overall', blank) ends the current layer's notes
        # but a known-key line above already flushed; a stray line just means the
        # next note won't attach. We keep `pending` so trailing notes still bind,
        # but a non-note, non-layer line after notes is simply ignored.
    _flush()
    return results


def layer_results_from_verifier(verifier: object) -> List[LayerResult]:
    """Build ``LayerResult`` rows from an embedded report dict (the PREFERRED source).

    New runs embed the verify-single report directly at ``result.json.verifier``;
    its ``layers`` map (``report.py::Report.to_dict``) is a machine contract, so
    when present we use it instead of the best-effort ``verifier_stdout.txt``
    text parse. ``detail`` mirrors what the text parse would have produced from
    ``render_text``: the bracket extras (``exit=``, ``tests=``, ``warn=``) joined
    to the ``- <note>`` lines. Statuses are normalized to the model contract
    (report's lowercase ``skipped`` -> ``skip``). Returns ``[]`` when ``verifier``
    is not a dict or carries no ``layers`` map — the caller then falls back to
    the stdout parse (old runs).
    """
    if not isinstance(verifier, dict):
        return []
    layers = verifier.get("layers")
    if not isinstance(layers, dict):
        return []
    results: List[LayerResult] = []
    for key, body in layers.items():
        if key not in _KNOWN_LAYERS or not isinstance(body, dict):
            continue
        raw_status = str(body.get("status", "")).strip()
        status = _STATUS_MAP.get(raw_status.upper(), raw_status.lower())
        extras: List[str] = []
        if body.get("exit_code") is not None:
            extras.append(f"exit={body['exit_code']}")
        if body.get("tests_run") is not None:
            extras.append(f"tests={body.get('tests_passed', 0)}/{body['tests_run']}")
        if body.get("warnings_in_agent_files") is not None:
            extras.append(f"warn={body['warnings_in_agent_files']}")
        parts: List[str] = []
        if extras:
            parts.append(", ".join(extras))
        notes = body.get("notes")
        if isinstance(notes, list):
            parts.extend(f"- {n}" for n in notes if n)
        results.append(
            LayerResult(key=key, status=status, detail="\n".join(parts) if parts else None)
        )
    return results


# ---------------------------------------------------------------------------
# result.json parsing -> Run.
# ---------------------------------------------------------------------------

# Per-run artifact dir name (SHARED CONTRACT) — swept screenshots live at
# runs/<id>/artifacts/*.png; we surface basenames only (the web route re-derives
# the on-disk path itself, so no path fragment from JSON is ever joined).
_ARTIFACTS_DIR_NAME = "artifacts"


def _collect_artifacts(run_dir: pathlib.Path) -> List[str]:
    """Sorted ``*.png`` basenames under ``<run_dir>/artifacts/`` (``[]`` default)."""
    art_dir = run_dir / _ARTIFACTS_DIR_NAME
    if not art_dir.is_dir():
        return []
    try:
        return sorted(p.name for p in art_dir.glob("*.png") if p.is_file())
    except OSError:
        return []

# run_id prefix: "YYYYMMDD-HHMMSS" (15 chars) — _make_run_id in run-agent/run.py.
_RUN_ID_TS_RE = re.compile(r"^(?P<ts>\d{8}-\d{6})")


def _parse_started_at(run_id: str) -> Optional[_dt.datetime]:
    """Parse the 15-char YYYYMMDD-HHMMSS prefix as UTC; None if unparseable."""
    m = _RUN_ID_TS_RE.match(run_id)
    if not m:
        return None
    try:
        naive = _dt.datetime.strptime(m.group("ts"), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=_dt.timezone.utc)


def _num(v: object) -> Optional[float]:
    """Coerce to float only for real, FINITE numbers (null/missing/NaN/Inf -> None).

    ``json.loads`` accepts bare ``NaN``/``Infinity`` by default; left unchecked one
    would poison ``Snapshot.totals()`` and make ``to_dict()`` emit non-strict JSON.
    Reject non-finite values here at the parse boundary.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


# Which verdicts belong in a pass-rate denominator. Kept in lockstep with
# ``tools/compare/compare_products.py`` AND with
# ``run-agent/adapters/base.GRADED_VERDICTS`` — a divergence between any two of
# them shows up as two different numbers for one run set.
#
# Being in lockstep with compare_products alone was NOT enough, and that is the
# whole history of this constant: the two aggregators agreed with each other
# while both disagreed with the harness's own summary, so nothing looked wrong
# from here. Reconciled 2026-08-17; enforced by
# ``tools/run-agent/tests/test_denominator_is_one_definition.py``, which parses
# every copy (this file is stdlib-only by design and cannot import the constant).
_MODEL_OUTCOME_GRADED = frozenset({
    "FAIL_NO_EDITS", "SANDBOX-REJECT", "NO_DELIVERABLE",
})
_GRADED_VERDICTS = frozenset({"PASS", "FAIL"}) | _MODEL_OUTCOME_GRADED


def _derive_blocker(
    overall: str, passed: bool, layer_results: List[LayerResult]
) -> Optional[str]:
    """Synthesize a human 'why not PASS' string (no such field in the schema).

    FAIL_NO_EDITS -> "no edits (empty submission)".
    A non-graded verdict -> the verdict itself; the verifier never rendered an
    opinion, so calling it "verifier FAIL" (as this did) told the reader a
    harness fault was a model failure — in the one artifact people actually look
    at.
    FAIL -> the first failing layer's detail, else "verifier FAIL".
    PASS -> None.
    """
    up = overall.upper()
    if passed:
        return None
    if up == "FAIL_NO_EDITS":
        return "no edits (empty submission)"
    if up not in _GRADED_VERDICTS:
        return f"not graded ({overall})"
    for lr in layer_results:
        if lr.status == "fail":
            return lr.detail or "verifier FAIL"
    return "verifier FAIL"


def _advisory_from_verifier(verifier: object) -> Optional[float]:
    """verifier.r2_advisory.advisory_score (kept forward-compat; None today)."""
    if not isinstance(verifier, dict):
        return None
    r2 = verifier.get("r2_advisory")
    if isinstance(r2, dict):
        return _num(r2.get("advisory_score"))
    return None


def parse_run(result_path: pathlib.Path,
              repo_root: Optional[pathlib.Path] = None) -> Optional[Run]:
    """Parse one ``runs/<id>/result.json`` (+ sibling stdout) into a ``Run``.

    Returns None for any JSON without a non-empty ``model`` (the compare skip
    rule — excludes aura-smoke iter-1 etc.) or any unreadable file.

    ``repo_root`` is optional and only ever refines the task lookup — the task
    id itself never needs it. It is passed EXPLICITLY by ``collect()`` rather
    than guessed from ``result_path``'s ancestors, because a run dir copied or
    read from another tree (a second checkout's ``runs/``) would make that guess wrong
    without saying so.
    """
    try:
        d = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    product = str(d.get("model", "")).strip()
    if not product:
        return None  # not a per-product run — skip (compare's rule)

    run_id = str(d.get("run_id") or result_path.parent.name)
    # Accepts BOTH writer shapes (run.py's "task" path, run_graded.py's bare
    # "task_id") and both separators; an unidentifiable record reports
    # run_identity.UNKNOWN_TASK_ID rather than a plausible-looking id.
    task_id = _run_identity.identify(d, repo_root).task_id
    tool_layer, _, model = product.partition(":")
    overall = str(d.get("overall", ""))
    passed = overall.upper() == "PASS"

    agent = d.get("agent")
    agent = agent if isinstance(agent, dict) else {}

    # Per-layer detail: PREFER the embedded verifier report dict (new runs write
    # the verify-single report into result.json.verifier — a machine contract).
    # FALLBACK for old runs (verifier null): best-effort text parse of the
    # sibling captured stdout; [] when both are absent/empty.
    layer_results: List[LayerResult] = layer_results_from_verifier(d.get("verifier"))
    if not layer_results:
        stdout_path = result_path.parent / "verifier_stdout.txt"
        if stdout_path.is_file():
            try:
                layer_results = parse_verifier_stdout(
                    stdout_path.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                layer_results = []

    return Run(
        run_id=run_id,
        task_id=task_id,
        product=product,
        tool_layer=tool_layer,
        model=model,
        overall=overall,
        passed=passed,
        graded=overall.upper() in _GRADED_VERDICTS,
        started_at=_parse_started_at(run_id),
        duration_s=_num(agent.get("duration_s")),
        cost_usd=_num(agent.get("cost_usd")),
        summary=str(agent.get("summary") or ""),
        blocker=_derive_blocker(overall, passed, layer_results),
        layer_results=layer_results,
        advisory_score=_advisory_from_verifier(d.get("verifier")),
        artifacts=_collect_artifacts(result_path.parent),
    )


# ---------------------------------------------------------------------------
# collect() + watch().
# ---------------------------------------------------------------------------


def collect(repo_root: pathlib.Path) -> Snapshot:
    """SINGLE entry point both UIs call — build a Snapshot from disk (read-only).

    Globs ``repo_root/runs/**/result.json``, dropping any without a non-empty
    ``model`` (the compare skip rule). For each kept run, text-parses the sibling
    ``verifier_stdout.txt`` into LayerResults (best-effort, [] if absent).
    Enumerates task specs SET-AWARE via ``_iter_task_specs`` (root + per-set,
    flat and folder layouts, deduped root-first) and parses metadata + declared
    layers + prompt excerpt. No run launch, no shell-out, no writes.
    """
    repo_root = pathlib.Path(repo_root)

    tasks: List[Task] = []
    for md in _iter_task_specs(repo_root / "tasks"):
        try:
            tasks.append(parse_task(md))
        except OSError:
            continue
    tasks.sort(key=lambda t: t.task_id)

    runs: List[Run] = []
    for rj in sorted((repo_root / "runs").glob("**/result.json")):
        run = parse_run(rj, repo_root)
        if run is not None:
            runs.append(run)
    # Stable order: started_at then run_id (None sorts first via epoch sentinel).
    epoch = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    runs.sort(key=lambda r: (r.started_at or epoch, r.run_id))

    products = sorted({r.product for r in runs})
    capabilities = sorted(
        {t.capability_bucket for t in tasks} | {_cap_for_run(r, tasks) for r in runs}
    )

    return Snapshot(
        generated_at=_iso_z(_dt.datetime.now(_dt.timezone.utc)),
        tasks=tasks,
        runs=runs,
        products=products,
        capabilities=capabilities,
        repo_root=repo_root.resolve(),
    )


def _cap_for_run(run: Run, tasks: List[Task]) -> str:
    """Capability bucket for a run's task (via parsed Task), else 'uncategorized'.

    A run may reference a task whose .md is absent; we still surface its capability
    as 'uncategorized' so the capabilities list mirrors what compare will produce.
    """
    for t in tasks:
        if t.task_id == run.task_id:
            return t.capability_bucket
    return "uncategorized"


def _fingerprint(repo_root: pathlib.Path) -> Tuple[float, frozenset]:
    """(max mtime, set of watched paths) — flips on content change OR add/delete.

    Watched set = runs/**/result.json + runs/**/verifier_stdout.txt + the task
    specs in EVERY shape (tasks/*.md + tasks/<set>/*.md + tasks/<set>/*/task.md
    — raw globs, not the deduped enumeration, so a change to any spec-shaped
    file registers). Including the path set means an add/delete at an equal
    mtime still registers.
    """
    paths: List[pathlib.Path] = []
    paths += list((repo_root / "runs").glob("**/result.json"))
    paths += list((repo_root / "runs").glob("**/verifier_stdout.txt"))
    paths += list((repo_root / "tasks").glob("*.md"))
    paths += list((repo_root / "tasks").glob("*/*.md"))
    paths += list((repo_root / "tasks").glob("*/*/task.md"))
    max_mtime = 0.0
    present: List[str] = []
    for p in paths:
        try:
            max_mtime = max(max_mtime, p.stat().st_mtime)
            present.append(str(p))
        except OSError:
            continue
    return max_mtime, frozenset(present)


def watch(
    repo_root: pathlib.Path,
    on_change: Callable[[Snapshot], None],
    interval: float = 2.0,
) -> None:
    """Poll ``repo_root`` and call ``on_change(collect(...))`` on any change.

    Calls ``on_change`` ONCE immediately with the initial Snapshot, then polls
    every ``interval`` seconds; fingerprint = max mtime over the watched files
    PLUS the set of watched paths (so add/delete at equal mtime still fires). Pure
    stdlib (no watchdog); blocks forever (the caller threads it). KeyboardInterrupt
    returns cleanly. ``collect()`` is always the on-demand source of truth — this
    is a convenience refresher and may miss sub-interval bursts (open-risk #7).
    """
    import time

    repo_root = pathlib.Path(repo_root)
    on_change(collect(repo_root))
    last = _fingerprint(repo_root)
    try:
        while True:
            time.sleep(interval)
            current = _fingerprint(repo_root)
            if current != last:
                last = current
                on_change(collect(repo_root))
    except KeyboardInterrupt:
        return
