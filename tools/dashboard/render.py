#!/usr/bin/env python3
"""Render a CraftBench task run as a self-contained HTML dashboard.

The page is written for a NON-cb-expert first (owner ask 2026-08-06): the
heading is the task name, and the sections run

  1. Task — what the agent was asked (prompt + spec excerpts)
  2. Verification — a plain-language checklist ("✓ the code compiles",
     "✗ descent was not slowed by the glide … — this is why the run failed")
     mapped from the verifier's evidence lines
  3. Screenshots — the per-checkpoint in-game captures (+ scene stills /
     video when the preview bundle has them)
  4. everything else — run summary, submission files
  5. Verifier internals — the full jargon view (layer ids, exit codes, cmd
     lines, log excerpts), collapsed by default; nothing is lost, just folded

Inputs (--report is required; combine the rest as needed):

  --report <path>      Required. Verifier JSON report (verify-single, or
                       the legacy batch score-report shape).
  --task-spec <path>   Optional. tasks/<id>.md — auto-discovered from
                       report's task_id when omitted.
  --submission <dir>   Optional. Agent's submission directory.
  --workdir <dir>      Optional. Verifier workdir for log excerpts.
  --output <path>      Where to write the HTML. Default: stdout.

Styling: Tailwind CSS via CDN (single <script> tag, no build step).

Example::

    python3 tools/dashboard/render.py \\
        --report runs/<run_id>/verifier_report.json \\
        --output /tmp/cb-dashboard.html
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else "—"


def _fmt_seconds(s: Optional[float]) -> str:
    if s is None:
        return "—"
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 60:
        return f"{s:.1f} s"
    m, sec = int(s // 60), int(s % 60)
    return f"{m}m {sec}s"


def _outcome_class(outcome: str) -> str:
    norm = (outcome or "").upper()
    return norm if norm in ("PASS", "FAIL", "REJECT", "ERROR", "SKIP", "SKIPPED") else "ERROR"


def _outcome_color(outcome: str) -> str:
    """Tailwind color hint for a status."""
    norm = (outcome or "").upper()
    return {
        "PASS": "green",
        "FAIL": "red",
        "REJECT": "amber",
        "ERROR": "purple",
        "SKIP": "slate",
        "SKIPPED": "slate",
        "SUCCESS": "green",
        "AGENT_FAILED": "red",
        "TOOL_FAILED": "red",
    }.get(norm, "slate")


# ---------------------------------------------------------------------------
# Task spec parsing — pull H2 section content out of tasks/<id>.md
# ---------------------------------------------------------------------------


def parse_task_spec_excerpts(spec_path: Path) -> dict[str, str]:
    """Return per-section excerpts keyed by short name.

    Also carries ``title``: the spec's first H1 line — usually the task id
    itself, occasionally a human title. The page heading prefers it when it
    differs from the bare id (derived from data, never hardcoded — a parallel
    lane is renaming task ids)."""
    text = spec_path.read_text(encoding="utf-8")
    headings = {
        "prompt": "## Prompt given to the agent",
        "primary_concept": "## Primary concept",
        "verifier_layers": "## Verifier layers used",
        "verifier_spec": "## Verifier specification",
    }
    out: dict[str, str] = {}
    for key, heading in headings.items():
        pat = re.compile(rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", re.M | re.S)
        m = pat.search(text)
        out[key] = m.group(1).strip() if m else ""
    m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    out["title"] = m.group(1).strip() if m else ""
    return out


# Task ids renamed by the 2026-08-06 -cpp suffix epoch. Run envelopes graded
# before the rename carry the OLD bare ids; without this alias their reports
# silently lose the whole Task section (the spec lookup misses). Applied only
# after every direct lookup fails, so a resurrected old-id spec would win.
RENAMED_TASK_IDS = {
    "gp-glide-stamina": "gp-glide-stamina-cpp",
    "gp-poison-dot-stack": "gp-poison-dot-stack-cpp",
}


def find_task_spec(task_id: str, repo_root: Path) -> Optional[Path]:
    for p in (repo_root / "tasks").rglob(f"{task_id}.md"):
        return p
    # Folder-per-task layout: the spec lives at tasks/<set>/<task_id>/task.md.
    for p in (repo_root / "tasks").glob(f"*/{task_id}/task.md"):
        return p
    direct = repo_root / "tasks" / f"{task_id}.md"
    if direct.exists():
        return direct
    alias = RENAMED_TASK_IDS.get(task_id)
    return find_task_spec(alias, repo_root) if alias else None


# ---------------------------------------------------------------------------
# Report shape normalization
# ---------------------------------------------------------------------------


def normalize_report(report: dict) -> list[dict]:
    """Return per-task records in a consistent shape (handles single+batch)."""
    if "task_id" in report and "layers" in report:
        return [
            {
                "task_id": report.get("task_id", "?"),
                "outcome": (report.get("overall") or "").lower(),
                "duration_seconds": report.get("duration_seconds"),
                "submission_sha": report.get("submission_sha"),
                "ue_version": report.get("ue_version"),
                "host": report.get("host"),
                "layers": report.get("layers", {}),
                "seed": None,
                "agent_metrics": None,
                "attribution": "",
                "source_shape": "single",
            }
        ]
    pinning = report.get("pinning", {})
    out = []
    for v in report.get("verdicts", []):
        layers: dict[str, dict] = {}
        for lr in v.get("layer_results") or []:
            name = lr.get("layer", "L?")
            layers[name] = {
                "status": (lr.get("outcome") or "").lower(),
                "duration_seconds": lr.get("duration_seconds", 0.0),
                "notes": [lr.get("attribution")] if lr.get("attribution") else [],
                "log_excerpt": lr.get("log_excerpt", ""),
            }
        out.append(
            {
                "task_id": v.get("task_id", "?"),
                "outcome": (v.get("outcome") or "").lower(),
                "duration_seconds": v.get("wall_clock_seconds"),
                "submission_sha": None,
                "ue_version": pinning.get("engine_version"),
                "host": report.get("host_info"),
                "layers": layers,
                "seed": v.get("seed"),
                "agent_metrics": v.get("agent_metrics"),
                "attribution": v.get("attribution", ""),
                "source_shape": "batch",
            }
        )
    return out


# ---------------------------------------------------------------------------
# Log excerpt extraction
# ---------------------------------------------------------------------------


def _read_log_excerpt(
    log_path: Optional[Path], *, layer_name: str, tail_lines: int = 80
) -> str:
    if not log_path or not log_path.exists():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    if layer_name == "L2":
        keepers = [
            ln for ln in lines
            if re.search(
                r"(Test (Passed|Failed|Completed)|PASS:|FAIL:|Functional Test|"
                r"Automation Test|tests? passed|Test summary|RunTests result|"
                r"^\s*Error:|^\s*Warning:|CRAFTBENCH)",
                ln,
            )
        ]
        tail = lines[-tail_lines:]
        seen: set[str] = set()
        combined = []
        for ln in keepers + tail:
            if ln not in seen:
                seen.add(ln)
                combined.append(ln)
        return "\n".join(combined)
    return "\n".join(lines[-tail_lines:])


# ---------------------------------------------------------------------------
# Plain-language verification (owner ask 2026-08-06)
#
# The default view of the Verification section is a checklist a non-cb-expert
# reads directly: "✓ the code compiles", "✓ the ability is granted to the
# character", "✗ descent was not slowed by the glide … — this is why the run
# failed". The KNOWN evidence-line families (l2_pie._EVIDENCE_PATTERNS:
# FinishTest verdict lines, the automation controller's Result={...} line, the
# fixture convention's [<TAG>-FINAL]/[<TAG>-ADVISORY]/[<TAG>-RESUME-DIAG]
# summaries) map to human sentences below; UNKNOWN evidence lines fall back to
# their raw text rather than being dropped. Everything jargon-shaped (exit
# codes, cmd lines, layer ids, log excerpts) moves to the collapsed "Verifier
# internals" fold at the bottom — nothing is lost, just folded.
# ---------------------------------------------------------------------------


_EVIDENCE_NOTE_PREFIX = "verdict-evidence:"

_FINISHTEST_RE = re.compile(
    r"FinishTest\s+TestResult=(?P<result>\w+)\.?\s*(?P<msg>.*)", re.S)
# Trailing source location the FinishTest line carries: " [C:\...\X.cpp(185)]"
_SRC_LOC_RE = re.compile(r"\s*\[[^\[\]]*\(\d+\)\]\s*$")
_TEST_COMPLETED_RE = re.compile(
    r"Test Completed\.\s*Result=\{(?P<result>[^}]*)\}")
_FINAL_LINE_RE = re.compile(r"^\[(?P<tag>[A-Z][A-Z0-9]*)-FINAL\]\s*(?P<rest>.*)$")
_ADVISORY_LINE_RE = re.compile(
    r"^\[(?P<tag>[A-Z][A-Z0-9]*)-(?:ADVISORY|RESUME-DIAG)\]\s*(?P<rest>.*)$")
_KV_RE = re.compile(r"([A-Za-z_]\w*)=(-?\d+(?:\.\d+)?)")
# An L2I per-check note: "<script>.py:<check>: PASS — <detail>"
_L2I_CHECK_RE = re.compile(
    r"^(?P<script>\S+\.py):(?P<check>\w+):\s*(?P<result>PASS|FAIL|SKIP|ERROR)"
    r"\s*[—–-]*\s*(?P<detail>.*)$")

# Boolean-flag fields of a [<TAG>-FINAL] gate-input summary -> (pass, fail)
# sentences. Field VOCABULARY is the fixture convention, not a task id — new
# tasks reusing the field names get sentences for free.
_FLAG_FIELD_SENTENCES = {
    "granted": ("the ability is granted to the character",
                "the ability was never granted to the character"),
    "activated": ("the ability activated when triggered",
                  "the ability did not activate when triggered"),
    "drained": ("energy drained while the ability was active",
                "energy did not drain while the ability was active"),
}

# Measurement fields -> a plain sentence for the value.
def _measure_field_sentence(key: str, v: float) -> Optional[str]:
    if key == "exhausted":
        return ("the energy reserve ran out during the test" if v > 0
                else "the energy reserve did not run out during the test")
    if key == "freefall":
        return f"free-fall descent speed before the ability: {v:g} cm/s"
    if key == "minglide":
        if v < 0:
            return "no gliding samples were captured"
        return f"slowest descent while gliding: {v:g} cm/s"
    if key == "minpower":
        return f"lowest energy level seen: {v:g}"
    if key == "lastspeed":
        return f"descent speed at the end of the test: {v:g} cm/s"
    if key == "ratio":
        return (f"the stacked effect drained {v:g}x faster than a "
                "single application")
    return None


# Per-layer plain sentences (fallbacks when a layer carries no mappable
# evidence, and the one-line summary for L1).
_LAYER_PASS_SENTENCE = {
    "sandbox": "the submission changes only files it is allowed to change",
    "L1": "the code compiles",
    "L2": "the behavior test passed in the running game",
    "L2I": "the submitted assets pass inspection",
}
_LAYER_FAIL_SENTENCE = {
    "sandbox": "the submission changes files it is not allowed to change",
    "L1": "the code does not compile",
    "L2": "the behavior test failed in the running game",
    "L2I": "the submitted assets fail inspection",
}


_LAYER_SUBJECT = {
    "sandbox": "the submission file check",
    "L1": "the build",
    "L2": "the in-game behavior test",
    "L2I": "the asset inspection",
}


def _plain_pass(name: str) -> str:
    return _LAYER_PASS_SENTENCE.get(name, f"the {name} check passed")


def _plain_fail(name: str) -> str:
    return _LAYER_FAIL_SENTENCE.get(name, f"the {name} check failed")


def _plain_subject(name: str) -> str:
    return _LAYER_SUBJECT.get(name, f"the {name} check")


def _evidence_lines(notes: list) -> list[str]:
    """The de-duplicated verdict-evidence payloads out of a layer's notes
    (l2_pie appends some lines twice, once with a trailing ``[log]``)."""
    out: list[str] = []
    seen: set[str] = set()
    for n in notes:
        n = str(n).strip()
        if not n.startswith(_EVIDENCE_NOTE_PREFIX):
            continue
        e = n[len(_EVIDENCE_NOTE_PREFIX):].strip()
        e = re.sub(r"\s*\[log\]$", "", e)
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out


def humanize_evidence_line(line: str) -> list[tuple[str, str]]:
    """Map ONE evidence line to plain checklist items ``[(mark, text), ...]``
    with mark in {"ok", "bad", "skip", "info"}. Unknown/unmapped lines fall
    back to ``[("info", <raw text>)]`` — never dropped."""
    line = str(line).strip()
    if not line:
        return []

    m = _FINISHTEST_RE.search(line)
    if m:
        result = m.group("result").lower()
        msg = _SRC_LOC_RE.sub("", m.group("msg")).strip()
        if result == "passed":
            return [("ok", msg or "the in-game test finished: passed")]
        if result == "failed":
            return [("bad", msg or "the in-game test finished: failed")]
        if result == "skipped":
            return [("skip", msg or "the in-game test was skipped")]
        return [("info", line)]

    m = _TEST_COMPLETED_RE.search(line)
    if m:
        result = m.group("result").lower()
        if result in ("success", "pass", "passed"):
            return [("ok", "the behavior test passed in the running game")]
        if result in ("fail", "failed"):
            return [("bad", "the behavior test failed in the running game")]
        return [("info", line)]  # localized/unknown result text: keep raw

    m = _FINAL_LINE_RE.match(line)
    if m:
        pairs = _KV_RE.findall(m.group("rest"))
        if not pairs:
            return [("info", line)]
        items: list[tuple[str, str]] = []
        leftovers: list[str] = []
        for k, v in pairs:
            key = k.lower()
            try:
                fv = float(v)
            except ValueError:  # pragma: no cover — regex only matches numbers
                leftovers.append(f"{k}={v}")
                continue
            if key in _FLAG_FIELD_SENTENCES:
                ok_txt, bad_txt = _FLAG_FIELD_SENTENCES[key]
                items.append(("ok", ok_txt) if fv > 0 else ("bad", bad_txt))
                continue
            sentence = _measure_field_sentence(key, fv)
            if sentence:
                items.append(("info", sentence))
            else:
                leftovers.append(f"{k}={v}")
        if leftovers:
            items.append(("info", "other measured values: "
                          + " · ".join(leftovers)))
        return items

    m = _ADVISORY_LINE_RE.match(line)
    if m:
        rest = m.group("rest").strip()
        return [("info", rest or line)]

    return [("info", line)]  # the fallback law: raw text, never dropped


def _plain_layer_items(name: str, layer: dict) -> list[tuple[str, str]]:
    """The plain checklist items one layer contributes."""
    status = (layer.get("status") or "").lower()
    notes = [str(n) for n in (layer.get("notes") or []) if n]
    items: list[tuple[str, str]] = []

    if status in ("skipped", "skip"):
        return [("skip", f"{_plain_subject(name)} was not run — an earlier "
                 "check already failed")]
    if status == "error":
        return [("bad", "this check could not produce a verdict "
                 "(a verifier-side error, not graded against the agent — "
                 "see verifier internals)")]

    if name == "L1":
        if status == "pass":
            items.append(("ok", _plain_pass("L1")))
        elif status == "fail":
            items.append(("bad", _plain_fail("L1")))
            # On a failed build the notes ARE the explanation — keep them
            # verbatim (raw fallback) rather than hiding the why.
            for n in notes:
                items.append(("info", n))
        return items

    # L2I-style per-check notes (any layer that writes them).
    checks = [m for n in notes if (m := _L2I_CHECK_RE.match(n.strip()))]
    if checks:
        for m in checks:
            mark = {"PASS": "ok", "FAIL": "bad", "SKIP": "skip"}.get(
                m.group("result"), "info")
            text = m.group("check").replace("_", " ")
            detail = m.group("detail").strip()
            if detail:
                text += f" — {detail}"
            items.append((mark, text))
        return items

    evidence = _evidence_lines(notes)
    if evidence:
        finals: list[tuple[str, str]] = []
        advisories: list[tuple[str, str]] = []
        finishes: list[tuple[str, str]] = []
        completions: list[tuple[str, str]] = []
        unknowns: list[tuple[str, str]] = []
        for e in evidence:
            mapped = humanize_evidence_line(e)
            if _FINISHTEST_RE.search(e):
                finishes.extend(mapped)
            elif _TEST_COMPLETED_RE.search(e):
                completions.extend(mapped)
            elif _FINAL_LINE_RE.match(e):
                finals.extend(mapped)
            elif _ADVISORY_LINE_RE.match(e):
                advisories.extend(mapped)
            else:
                unknowns.extend(mapped)
        # Story order: measured gate inputs first, then advisory notes and
        # anything unknown, then the verdict line. "Test Completed" repeats
        # what a FinishTest line already says with its message — suppress the
        # echo, keep the one with the why.
        items.extend(finals + advisories + unknowns)
        items.extend(finishes if finishes else completions)
        return items

    # No evidence at all (older reports, batch shape): status + test counts.
    if status == "pass":
        text = _plain_pass(name)
        if layer.get("tests_run"):
            text += (f" ({layer.get('tests_passed', 0)} of "
                     f"{layer.get('tests_run')} tests)")
        items.append(("ok", text))
    elif status == "fail":
        text = _plain_fail(name)
        if layer.get("tests_run"):
            text += (f" ({layer.get('tests_passed', 0)} of "
                     f"{layer.get('tests_run')} tests passed)")
        items.append(("bad", text))
    return items


_PLAIN_MARKS = {
    "ok": ('<span class="text-green-600 font-bold shrink-0">&#10003;</span>'),
    "bad": ('<span class="text-red-600 font-bold shrink-0">&#10007;</span>'),
    "skip": ('<span class="text-slate-400 font-bold shrink-0">&mdash;</span>'),
    "info": ('<span class="text-slate-400 shrink-0">&middot;</span>'),
}

_WHY_FAILED_SUFFIX = (' <strong class="text-red-700">— this is why the run '
                      "failed</strong>")


def _render_plain_verification(record: dict) -> str:
    """The default-view Verification section: a plain checklist."""
    layers = record.get("layers") or {}
    if not layers:
        return ""
    order = ["sandbox", "L1", "L2", "L2I", "ART", "L3", "R2"]
    sorted_layers = sorted(
        layers.items(),
        key=lambda kv: order.index(kv[0]) if kv[0] in order else 999)

    items: list[tuple[str, str]] = []
    why_pos: Optional[int] = None
    for name, lyr in sorted_layers:
        if not isinstance(lyr, dict):
            continue
        layer_items = _plain_layer_items(name, lyr)
        if why_pos is None and str(lyr.get("status") or "").lower() == "fail":
            for j, (mark, _t) in enumerate(layer_items):
                if mark == "bad":
                    why_pos = len(items) + j
                    break
        items.extend(layer_items)
    if not items:
        return ""

    lis = []
    for i, (mark, text) in enumerate(items):
        suffix = _WHY_FAILED_SUFFIX if i == why_pos else ""
        lis.append(
            f'<li class="flex gap-2 items-baseline">'
            f'{_PLAIN_MARKS.get(mark, _PLAIN_MARKS["info"])}'
            f"<span>{_esc(text)}{suffix}</span></li>")
    return (
        '<h2 class="text-lg font-semibold border-b border-slate-200 pb-2 '
        'mt-8 mb-3">Verification</h2>'
        '<div class="bg-white border border-slate-200 rounded p-4 mb-3">'
        '<ul class="space-y-1 text-sm">' + "".join(lis) + "</ul>"
        '<p class="text-xs text-slate-400 mt-3">Full logs, commands and exit '
        "codes are in the collapsed fold at the bottom of this page.</p>"
        "</div>")


# ---------------------------------------------------------------------------
# Tailwind-styled HTML fragments
# ---------------------------------------------------------------------------


_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  /* Slight tweaks Tailwind doesn't cover */
  pre.log { background:#0f172a; color:#e2e8f0; font-size:11px; line-height:1.45; max-height:360px; overflow:auto; padding:12px; border-radius:6px; font-family:ui-monospace,Menlo,Consolas,monospace; }
  pre.log .pass-line { color:#4ade80; }
  pre.log .fail-line { color:#f87171; }
  pre.code { background:#f4f4f5; padding:12px; border-radius:6px; font-size:12px; overflow:auto; font-family:ui-monospace,Menlo,Consolas,monospace; }
  blockquote.prompt { background:#fef9c3; border-left:4px solid #facc15; padding:12px 16px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; white-space:pre-wrap; border-radius:4px; margin:0; }
  .conv-turn { border-left:4px solid #cbd5e1; padding-left:16px; margin-bottom:16px; }
  .conv-turn.role-user { border-left-color:#3b82f6; }
  .conv-turn.role-assistant { border-left-color:#a855f7; }
  .conv-turn.role-tool_use { border-left-color:#f59e0b; }
  .conv-turn.role-tool_result.ok { border-left-color:#22c55e; }
  .conv-turn.role-tool_result.fail { border-left-color:#ef4444; }
</style>
</head>
<body class="bg-slate-50 text-slate-900">
<div class="max-w-5xl mx-auto p-6">
<h1 class="text-2xl font-semibold mb-1">{heading}</h1>
"""

_FOOTER = """
<footer class="mt-12 text-xs text-slate-400 text-center">Generated {generated} · CraftBench dashboard · Tailwind</footer>
</div>
</body>
</html>"""


def _render_run_banner(record: dict) -> str:
    """Top banner for one verifier-report record."""
    outcome = (record.get("outcome") or record.get("overall_status") or "").upper()
    color = _outcome_color(outcome)
    duration = _fmt_seconds(record.get("duration_seconds"))
    task_id = record.get("task_id") or record.get("run_id") or "?"
    ue = record.get("ue_version") or ""
    host = record.get("host", {}) or {}
    host_str = host.get("os") or ""
    if host_str and host.get("arch"):
        host_str += f" · {host.get('arch')}"
    sub = (
        f" · UE {_esc(ue)}" if ue else ""
    ) + (
        f" · {_esc(host_str)}" if host_str else ""
    )
    return f"""
<div class="bg-{color}-50 border-l-4 border-{color}-500 rounded p-4 mb-6 flex items-center gap-4">
  <span class="text-3xl font-bold text-{color}-600">{_esc(outcome or "?")}</span>
  <div>
    <div class="text-sm"><code class="font-mono">{_esc(task_id)}</code></div>
    <div class="text-xs text-slate-500">total {duration}{sub}</div>
  </div>
</div>
"""


def _render_task_section(spec_excerpts: dict) -> str:
    if not spec_excerpts:
        return ""
    blocks = []
    prompt = spec_excerpts.get("prompt", "").strip()
    if prompt:
        cleaned = "\n".join(re.sub(r"^>\s?", "", ln) for ln in prompt.splitlines()).strip()
        blocks.append(f"""
<div class="bg-white border border-slate-200 rounded p-4 mb-3">
  <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Prompt given to the agent</h3>
  <blockquote class="prompt">{_esc(cleaned)}</blockquote>
</div>
""")
    concept = spec_excerpts.get("primary_concept", "").strip()
    layers_used = spec_excerpts.get("verifier_layers", "").strip()
    verifier_spec = spec_excerpts.get("verifier_spec", "").strip()
    if concept or layers_used:
        sub = ""
        if concept:
            sub += f'<h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Primary concept</h3><pre class="code mb-3">{_esc(concept)}</pre>'
        if layers_used:
            sub += f'<h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Verifier layers used</h3><pre class="code">{_esc(layers_used)}</pre>'
        blocks.append(f'<div class="bg-white border border-slate-200 rounded p-4 mb-3">{sub}</div>')
    if verifier_spec:
        blocks.append(f"""
<details class="mt-2"><summary class="cursor-pointer text-blue-600 text-sm">Verifier specification (the exact checks)</summary>
<pre class="code mt-2">{_esc(verifier_spec)}</pre></details>
""")
    if not blocks:
        return ""
    return '<h2 class="text-lg font-semibold border-b border-slate-200 pb-2 mt-8 mb-3">Task</h2>' + "".join(blocks)


def _render_submission_section(submission_dir: Optional[Path]) -> str:
    if not submission_dir or not submission_dir.exists():
        return ""
    files = sorted(p for p in submission_dir.rglob("*") if p.is_file())
    if not files:
        return ""
    blocks = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            blocks.append(f"""
<div class="border border-slate-200 rounded overflow-hidden mb-3">
  <div class="px-3 py-2 bg-slate-100 text-xs font-mono">{_esc(f.relative_to(submission_dir))}</div>
  <div class="px-3 py-2 text-xs text-slate-500">(binary — {f.stat().st_size:,} bytes)</div>
</div>""")
            continue
        blocks.append(f"""
<div class="border border-slate-200 rounded overflow-hidden mb-3">
  <div class="px-3 py-2 bg-slate-100 text-xs font-mono">{_esc(f.relative_to(submission_dir))} · {len(text):,} chars</div>
  <pre class="code rounded-none">{_esc(text)}</pre>
</div>""")
    return f"""
<h2 class="text-lg font-semibold border-b border-slate-200 pb-2 mt-8 mb-3">Agent submission</h2>
<div class="text-xs text-slate-500 mb-3">{len(files)} file(s) under <code class="font-mono">{_esc(submission_dir)}</code></div>
{"".join(blocks)}
"""


def _colorize_log_line(line: str) -> str:
    esc = _esc(line)
    if re.search(r"(PASS|Test Passed|success|: pass|exit 0)", line, re.I):
        return f'<span class="pass-line">{esc}</span>'
    if re.search(r"(FAIL|Test Failed|error|: fail|exit [1-9])", line, re.I):
        return f'<span class="fail-line">{esc}</span>'
    return esc


def _render_layer_block(layer_name: str, layer: dict, workdir: Optional[Path]) -> str:
    status = (layer.get("status") or "").lower()
    color = {"pass": "green", "fail": "red", "skipped": "slate"}.get(status, "slate")
    duration = _fmt_seconds(layer.get("duration_seconds"))
    exit_code = layer.get("exit_code")
    notes = layer.get("notes") or []
    log_path_str = layer.get("log")
    inline_excerpt = layer.get("log_excerpt", "")

    log_excerpt = ""
    if inline_excerpt:
        log_excerpt = inline_excerpt
    elif log_path_str:
        log_path = Path(log_path_str)
        if workdir is not None:
            candidate = workdir / "out" / Path(log_path_str).name
            if candidate.exists():
                log_path = candidate
        log_excerpt = _read_log_excerpt(log_path, layer_name=layer_name)

    notes_html = ""
    if notes:
        notes_html = '<ul class="list-disc ml-5 text-sm space-y-1 my-2">' + "".join(
            f"<li>{_esc(n)}</li>" for n in notes if n
        ) + "</ul>"

    test_counts_html = ""
    if "tests_run" in layer:
        passed = layer.get("tests_passed", 0)
        total = layer.get("tests_run", 0)
        failed = layer.get("tests_failed", 0)
        skipped = layer.get("tests_skipped", 0)
        pcolor = "green" if passed == total and total > 0 else ("red" if failed > 0 else "slate")
        test_counts_html = f'<span class="inline-block px-3 py-1 bg-{pcolor}-100 text-{pcolor}-700 rounded text-sm font-medium mr-2 my-2">tests {passed}/{total} passed</span>'
        if failed:
            test_counts_html += f'<span class="inline-block px-3 py-1 bg-red-100 text-red-700 rounded text-sm mr-2">{failed} failed</span>'
        if skipped:
            test_counts_html += f'<span class="inline-block px-3 py-1 bg-slate-100 text-slate-700 rounded text-sm mr-2">{skipped} skipped</span>'

    log_html = ""
    if log_excerpt:
        lines = log_excerpt.splitlines()
        colorized = "\n".join(_colorize_log_line(ln) for ln in lines)
        log_html = f"""
<details open class="mt-2">
  <summary class="cursor-pointer text-blue-600 text-sm">Log excerpt ({len(lines)} lines{f' from <code class="font-mono">{_esc(log_path_str)}</code>' if log_path_str else ''})</summary>
  <pre class="log mt-2">{colorized}</pre>
</details>
"""

    return f"""
<div class="border-l-4 border-{color}-500 pl-4 mb-4">
  <div class="flex items-baseline gap-3">
    <span class="text-lg font-semibold">{_esc(layer_name)}</span>
    <span class="px-3 py-1 bg-{color}-100 text-{color}-700 rounded text-xs font-semibold uppercase">{_esc(status or '?')}</span>
    <span class="text-xs text-slate-500">{duration} · exit {_esc(exit_code)}</span>
  </div>
  {test_counts_html}
  {notes_html}
  {log_html}
</div>
"""


def _render_internals_section(record: dict, workdir: Optional[Path]) -> str:
    """The collapsed-by-default "Verifier internals" fold — the full per-layer
    blocks (layer ids, exit codes, cmd lines, notes, log excerpts). Nothing is
    lost from the old jargon view, just folded (owner ask 2026-08-06 #5)."""
    layers = record.get("layers") or {}
    if not layers:
        return ""
    order = ["sandbox", "L1", "L2", "L2I", "L3", "L4", "L5"]
    sorted_layers = sorted(layers.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 999)
    blocks = [_render_layer_block(name, lyr, workdir) for name, lyr in sorted_layers]
    return (
        '<details class="mt-8"><summary class="cursor-pointer text-blue-600 '
        'text-sm">Verifier internals (per-layer logs, commands, exit codes)'
        "</summary>"
        '<div class="mt-3">' + "".join(blocks) + "</div></details>")


def _render_artifacts_section(
    artifacts: Optional[list], run_id: Optional[str] = None,
    artifact_base: Optional[str] = None,
) -> str:
    """The "Artifacts" section — swept capture screenshots for this run.

    With a ``run_id`` the images are inlined as ``<img>`` tags addressed at the
    dashboard's artifact route (``/api/run/{id}/artifact/{name}`` — the only
    place these PNGs are served from). ``artifact_base`` overrides that with a
    caller-supplied href prefix (e.g. ``"artifacts"`` for a static report.html
    written INTO the run dir, where the PNGs sit right next to the page).
    Without either (e.g. a CLI render of a bare report, where no web route
    exists) we degrade to a plain filename list so the section still records
    what was captured. Empty/None artifacts -> "" (old runs keep rendering
    byte-identically).
    """
    if not artifacts:
        return ""
    header = (
        '<h2 class="text-lg font-semibold border-b border-slate-200 pb-2 mt-8 mb-3">'
        "Artifacts</h2>"
    )
    if artifact_base or run_id:
        figures = []
        for name in artifacts:
            if artifact_base:
                src = f"{artifact_base.rstrip('/')}/{quote(str(name), safe='')}"
            else:
                src = (
                    f"/api/run/{quote(str(run_id), safe='')}"
                    f"/artifact/{quote(str(name), safe='')}"
                )
            figures.append(f"""
<figure class="border border-slate-200 rounded overflow-hidden mb-3 bg-white">
  <img src="{_esc(src)}" alt="{_esc(name)}" loading="lazy" class="w-full">
  <figcaption class="px-3 py-2 bg-slate-100 text-xs font-mono">{_esc(name)}</figcaption>
</figure>
""")
        return header + "".join(figures)
    items = "".join(f'<li class="font-mono">{_esc(n)}</li>' for n in artifacts)
    return header + f'<ul class="list-disc ml-5 text-sm space-y-1">{items}</ul>'






def _render_pinning(record: dict, report: dict) -> str:
    rows = []
    if record and record.get("submission_sha"):
        rows.append(("submission_sha", record["submission_sha"]))
    if record and record.get("ue_version"):
        rows.append(("ue_version", record["ue_version"]))
    if record and record.get("host"):
        h = record["host"]
        os_str = h.get("os") or "?"
        arch = h.get("arch") or h.get("cpu") or "?"
        py = h.get("python_version") or ""
        rows.append(("host", f"{os_str} · {arch}{(' · py ' + py) if py else ''}"))
    if record and record.get("seed"):
        rows.append(("seed", record["seed"]))
    if report:
        pinning = report.get("pinning") or {}
        for k in ("harness_id", "model_id", "substrate_revision", "task_set_revision", "verifier_revision"):
            if pinning.get(k):
                rows.append((k, pinning[k]))
    if not rows:
        return ""
    rows_html = "".join(
        f'<div class="contents"><dt class="text-slate-500">{_esc(k)}</dt><dd class="font-mono">{_esc(v)}</dd></div>'
        for k, v in rows
    )
    return f"""
<details class="mt-6">
  <summary class="cursor-pointer text-blue-600 text-sm">Pinning + reproducibility</summary>
  <dl class="grid grid-cols-[180px_1fr] gap-y-1 gap-x-3 text-sm mt-3">{rows_html}</dl>
</details>
"""


def _render_run_summary_section(run_summary: Optional[dict]) -> str:
    """A compact key/value table right under the banner — the same facts the
    terminal recap prints (model, cost, agent/grade time, tool calls). The
    caller (report_bridge) assembles the dict from the run's envelope; keys
    render in insertion order. ``by_tool`` (a dict) renders as a per-tool
    breakdown line. None/empty -> "" (existing callers byte-identical)."""
    if not run_summary:
        return ""
    rows = []
    for k, v in run_summary.items():
        if v is None or v == "" or v == {}:
            continue
        if isinstance(v, dict):  # e.g. by_tool: {"edit_cpp_file": 2, ...}
            v = ", ".join(f"{name} ×{n}" for name, n in
                          sorted(v.items(), key=lambda kv: -kv[1]))
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            # e.g. posthog trace: draw the URL as a clickable link (report.html
            # is a static file — a bare URL string would be dead text).
            rows.append(
                f'<div class="contents"><dt class="text-slate-500">{_esc(k)}</dt>'
                f'<dd class="font-mono"><a class="text-blue-600 underline" '
                f'href="{_esc(v)}" target="_blank" rel="noopener">{_esc(v)}</a>'
                f"</dd></div>")
            continue
        rows.append(
            f'<div class="contents"><dt class="text-slate-500">{_esc(k)}</dt>'
            f'<dd class="font-mono">{_esc(v)}</dd></div>')
    if not rows:
        return ""
    return (
        '<h2 class="text-lg font-semibold border-b border-slate-200 pb-2 mt-8 mb-3">'
        "Run summary</h2>"
        '<dl class="grid grid-cols-[180px_1fr] gap-y-1 gap-x-3 text-sm mt-3">'
        + "".join(rows) + "</dl>"
    )


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------


def render_html(
    *,
    report: Optional[dict] = None,
    task_spec_excerpts: Optional[dict] = None,
    submission_dir: Optional[Path] = None,
    workdir: Optional[Path] = None,
    artifacts: Optional[list] = None,
    run_id: Optional[str] = None,
    run_summary: Optional[dict] = None,
    artifact_base: Optional[str] = None,
    heading: Optional[str] = None,
) -> str:
    # Build a record (banner data) from whatever input is richest
    records = normalize_report(report) if report else []
    if not records:
        records = [
            {
                "task_id": "?",
                "outcome": "unknown",
                "duration_seconds": None,
                "layers": {},
                "host": None,
            }
        ]

    task_id = records[0].get("task_id") or "?"
    title = f"CraftBench · {task_id}"
    # Page heading = the TASK NAME, derived from data (owner ask 2026-08-06
    # #1): the spec's human title when it says more than the bare id, else the
    # caller-supplied heading (report_bridge passes the envelope's possibly
    # set-qualified task id), else the record's task id. Never hardcoded — a
    # parallel lane is renaming task ids.
    spec_title = (task_spec_excerpts or {}).get("title", "").strip()
    if spec_title and spec_title != task_id:
        page_heading = spec_title
    elif heading:
        page_heading = heading
    elif task_id != "?":
        page_heading = task_id
    else:
        page_heading = "Task run report"

    # Section order (owner ask 2026-08-06 #2): Task (what the agent was
    # asked) -> Verification (the plain checklist) -> Screenshots (+ the rest
    # of the visual material) -> everything else; the jargon fold last.
    body_parts = []
    for i, record in enumerate(records):
        body_parts.append(_render_run_banner(record))
        if task_spec_excerpts:
            body_parts.append(_render_task_section(task_spec_excerpts))
        body_parts.append(_render_plain_verification(record))
        if artifacts and i == 0:
            body_parts.append(_render_artifacts_section(artifacts, run_id,
                                                        artifact_base))
        if run_summary and i == 0:
            body_parts.append(_render_run_summary_section(run_summary))
        body_parts.append(_render_submission_section(submission_dir))
        body_parts.append(_render_internals_section(record, workdir))
        body_parts.append(_render_pinning(record, report or {}))
        if len(records) > 1:
            body_parts.append('<hr class="my-8 border-slate-200">')

    generated = datetime.now(timezone.utc).isoformat()
    head = _HEAD.replace("{title}", _esc(title)).replace(
        "{heading}", _esc(page_heading))
    footer = _FOOTER.replace("{generated}", generated)
    return head + "\n".join(body_parts) + footer


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="render.py", description=__doc__.splitlines()[0])
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--task-spec", type=Path, default=None)
    p.add_argument("--submission", type=Path, default=None)
    p.add_argument("--workdir", type=Path, default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument(
        "--repo-root", type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
    )
    args = p.parse_args(argv)

    if not args.report:
        print("[abort] --report is required", file=sys.stderr)
        return 2

    report = None
    if args.report:
        if not args.report.exists():
            print(f"[abort] report not found: {args.report}", file=sys.stderr)
            return 2
        try:
            report = json.loads(args.report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[abort] failed to parse report: {e}", file=sys.stderr)
            return 2

    task_spec_path = args.task_spec
    if not task_spec_path and report:
        records = normalize_report(report)
        if records:
            task_id = records[0].get("task_id")
            if task_id:
                task_spec_path = find_task_spec(task_id, args.repo_root)
                if task_spec_path:
                    print(f"[ok] auto-discovered task spec: {task_spec_path}", file=sys.stderr)
    task_spec_excerpts = None
    if task_spec_path and task_spec_path.exists():
        try:
            task_spec_excerpts = parse_task_spec_excerpts(task_spec_path)
        except OSError as e:
            print(f"[warn] failed to read task spec: {e}", file=sys.stderr)

    html_doc = render_html(
        report=report,
        task_spec_excerpts=task_spec_excerpts,
        submission_dir=args.submission,
        workdir=args.workdir,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html_doc, encoding="utf-8")
        print(f"[ok] wrote {len(html_doc):,} bytes to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(html_doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
