"""Single-run report drill-in — a thin bridge over ``tools/dashboard/render.py``.

The fleet dashboard's matrix answers *which* (product, task) cells pass/fail. This
module answers *why one cell looks the way it does*: given a ``run_id``, it locates
``runs/<run_id>/``, loads ``result.json``, and re-uses ``render.py:render_html`` to
produce the same rich self-contained single-run HTML report the Aura demo runs use
— banner, task-spec excerpts, agent submission files, and per-layer verification
log excerpts.

We do **not** reimplement any HTML here. We only *assemble* ``render_html``'s
inputs from a ``runs/<id>/`` directory, replicating what ``render.py:main`` does for
an arbitrary ``run_id``:

  * ``result.json["verifier"]``  -> ``render_html(report=...)``  (the verifier's
    own report.json dict; ``None`` on runs that never reached the verifier).
  * ``result.json["task"]``      -> ``task_id`` -> ``find_task_spec`` ->
    ``parse_task_spec_excerpts`` -> ``render_html(task_spec_excerpts=...)``.
  * ``runs/<id>/submission/``     -> ``render_html(submission_dir=...)``.
  * ``runs/<id>/artifacts/*.png`` -> ``render_html(artifacts=[names], run_id=...)``
    — the swept capture screenshots, rendered as an "Artifacts" ``<img>`` section
    addressed at the dashboard's ``/api/run/{id}/artifact/{name}`` route.

``render.py`` expects a live verifier workdir for its per-layer log excerpts, and
by the time we render, the verifier's ``/tmp`` workdir is gone. We therefore
**degrade gracefully** — pass ``workdir=None``, and synthesize a minimal report
banner when ``verifier`` is ``None`` so the page still shows the task id + overall
outcome. Every ``render.py`` sub-renderer already returns ``""`` for missing/None
inputs, so nothing crashes.

This module is web-side: it may import ``render`` + stdlib. It intentionally does
NOT pull ``fastapi`` (the integration agent owns the route wiring and imports the
small ``(html, status)`` helper below). It also does NOT touch the pure-stdlib data
layer (``collect`` / ``model``).

Public API (stable — the integration agent wires these verbatim):

    render_run_report(repo_root, run_id) -> str
        Full single-run HTML. Raises LookupError for an unknown run_id.

    render_report_response(repo_root, run_id) -> tuple[str, int]
        (html, status_code) — never raises for an unknown run_id (returns a 404
        HTML page); returns a 500 HTML page on any unexpected render failure. The
        function a FastAPI route can mount directly and return as an HTMLResponse.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import quote

# Sibling-package import: tools/dashboard/web/ -> tools/dashboard/render.py
from ..render import (
    find_task_spec,
    parse_task_spec_excerpts,
    render_html,
)

__all__ = [
    "render_run_report",
    "render_report_response",
    "resolve_run_dir",
    "write_static_report",
    "RunNotFoundError",
]


class RunNotFoundError(LookupError):
    """Raised when ``runs/<run_id>/result.json`` does not exist.

    Subclasses ``LookupError`` so callers can ``except LookupError`` generically
    (the spec asks for a clean ``LookupError`` on an unknown run_id).
    """


# ---------------------------------------------------------------------------
# Input assembly — replicate render.py:main() for an arbitrary run_id
# ---------------------------------------------------------------------------


def resolve_run_dir(repo_root: Path, run_id: str) -> Path:
    """Resolve the run directory for ``run_id`` under repo_root/runs — shared
    by the report and artifact routes so flat and nested runs resolve
    identically.

    ``run_id`` is treated as a single path segment. We reject anything that
    would escape the ``runs/`` directory (path separators / ``..`` / glob
    chars) — a run_id is a directory *name*, never a path. This keeps the
    bridge from reading arbitrary files even though it only ever *reads*.

    Runs live either directly under ``runs/`` (the legacy flat layout) or one
    container level down (``runs/<backend>/<run_id>`` — claude-p, openrouter,
    unreal-mcp, aura-mcp — the layout older run sets used too). The direct child
    wins; otherwise the first existing ``runs/<container>/<run_id>`` in sorted
    container order is returned. When neither exists, the (missing)
    direct-child path is returned so the caller's result.json read yields the
    uniform unknown-run error.
    """
    runs_root = (repo_root / "runs").resolve()
    if (not run_id or run_id in (".", "..")
            or any(ch in run_id for ch in "/\\*?[")):
        raise RunNotFoundError(f"invalid run_id (not a directory name): {run_id!r}")
    candidate = (runs_root / run_id).resolve()
    # Containment check: candidate must be a direct child of runs_root.
    if candidate.parent != runs_root:
        raise RunNotFoundError(f"invalid run_id (not a runs/ child): {run_id!r}")
    if candidate.is_dir():
        return candidate
    try:
        containers = sorted(p for p in runs_root.iterdir() if p.is_dir())
    except OSError:
        return candidate
    # run_id was validated as a single segment above, so container/run_id
    # cannot escape the container — a plain is_dir() probe suffices (the
    # earlier per-candidate resolve()+parent re-check tripled the syscalls
    # on what is now the COMMON layout).
    for container in containers:
        nested = container / run_id
        if nested.is_dir():
            return nested
    return candidate


def _load_envelope(run_dir: Path) -> Tuple[dict, Path]:
    """Load the run's harness envelope: ``summary.json`` (the graded-harness
    shape) wins over ``result.json`` (baseline run.py runs). A graded run dir can
    carry BOTH — there ``result.json`` is the driver's own record (model-pin
    provenance), not the harness envelope, so summary.json must be preferred or
    the report renders the wrong schema. Raises
    ``RunNotFoundError`` when neither parses to a dict."""
    for name in ("summary.json", "result.json"):
        path = run_dir / name
        if not path.is_file():
            continue
        # The PREFERRED envelope exists: parse it or fail LOUDLY. Falling
        # through a corrupt summary.json to the driver-schema result.json
        # would render a 200 garbage page over real corruption (e.g. a
        # killed harness's truncated write) — corruption must stay a 500.
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"unreadable run envelope {path.name} under {run_dir}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} under {run_dir} is not a JSON object")
        return data, path
    raise RunNotFoundError(
        f"no summary.json/result.json under {run_dir}")


# ---------------------------------------------------------------------------
# "Which task is this run?" — THE single implementation, tools/runlib/
# run_identity.py. Imported, never re-spelled: this file's own answer used to be
# ``Path(task).stem``, which on the folder-form path run.py actually writes
# (``tasks/<set>/<id>/task.md``) returns the literal string ``"task"`` for EVERY
# run — the same defect that made compare_products see 2 distinct tasks across
# 110 records on 2026-08-19. Bridged the way tools/dashboard/collect.py bridges
# it, so a rename over there is an ImportError here rather than silent drift.
# ---------------------------------------------------------------------------
_RUNLIB = Path(__file__).resolve().parents[2] / "runlib"
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))

import run_identity as _run_identity  # noqa: E402  (tools/runlib/run_identity.py)


def _task_id_from_result(result: dict) -> Optional[str]:
    """Derive the task id from the run envelope.

    ``result["task"]`` is a path like ``tasks/gp-alpha.md`` (run-agent writes
    ``str(args.task)``). The task id is its basename without the ``.md`` suffix.
    A graded ``summary.json`` records a bare ``task_id`` instead. Falls back to
    the verifier report's own ``task_id`` when both are absent.
    """
    # Both writer shapes ("task" path from run.py, bare "task_id" from the
    # graded harness) are handled by the one rule, including the set-qualified
    # form ("cpp/t2-homing-projectile") that find_task_spec needs bare.
    ident = _run_identity.identify(result)
    if ident.task_id and ident.task_id != _run_identity.UNKNOWN_TASK_ID:
        return ident.task_id
    verifier = result.get("verifier")
    if isinstance(verifier, dict):
        vtid = verifier.get("task_id")
        if isinstance(vtid, str) and vtid:
            return vtid
    return None


def _fmt_usd(v) -> Optional[str]:
    return f"${v:.4f}" if isinstance(v, (int, float)) else None


def _run_summary_from_envelope(env: dict) -> dict:
    """The compact facts table for render_html(run_summary=...) — the SAME
    fields the terminal recap prints (cb.py::_recap_run_summary): verdict,
    model (agent.models_used beats the slug — the mislabel rule), cost, agent/
    grade time, tool calls (+ per-tool breakdown). Insertion order = render
    order. Only fields the run actually carries are emitted."""
    agent = env.get("agent") or {}
    t = env.get("timings") or {}
    out: dict = {}
    verdict = env.get("verdict") or env.get("overall")
    if verdict:
        out["verdict"] = verdict
    models_used = agent.get("models_used")
    model = ",".join(models_used) if models_used else env.get("model")
    if model:
        out["model"] = model
    cost = env.get("est_cost_usd")
    if cost is None:
        cost = agent.get("cost_usd")
    if _fmt_usd(cost):
        # Owner ask 2026-08-06 #6: name WHAT is measured. The thread-billed
        # spend includes tool/sub-agent turns, so PostHog's main trace shows a
        # smaller number — that difference is expected, not a bug.
        out["model spend"] = (
            f"{_fmt_usd(cost)} (thread-billed — includes tool/sub-agent "
            "turns; PostHog's main trace shows less)")
    # Some envelopes stamp the run's PostHog LLM-analytics trace URL;
    # render.py draws http(s) values as links. Absent -> the row is omitted.
    ph = env.get("posthog_url")
    if isinstance(ph, str) and ph:
        out["posthog trace"] = ph
    # Owner ask 2026-08-06 #6: agent time is WALL CLOCK including editor/tool
    # work — PostHog shows LLM generation time only, so its number is smaller.
    _AGENT_TIME_NOTE = ("wall clock incl. editor/tool work; PostHog shows "
                        "LLM generation time only")
    if t.get("aura_execution_time") is not None:
        agent_s = f"{t['aura_execution_time']}s"
        if t.get("drive_s") is not None:
            agent_s += f" (wall {t['drive_s']}s — {_AGENT_TIME_NOTE})"
        else:
            agent_s += f" ({_AGENT_TIME_NOTE})"
        out["agent time"] = agent_s
    elif t.get("agent_s") is not None:
        out["agent time"] = f"{t['agent_s']}s ({_AGENT_TIME_NOTE})"
    elif t.get("drive_s") is not None:
        out["agent time"] = f"drive {t['drive_s']}s ({_AGENT_TIME_NOTE})"
    grade = t.get("grade_s", t.get("verify_s"))
    if grade is not None:
        out["grade time"] = f"{grade}s"
    ntools = agent.get("tool_calls", agent.get("tool_use_count"))
    if ntools is not None:
        out["tool calls"] = ntools
        by = agent.get("by_tool") or {}
        if by:
            out["by tool"] = by
    gw = env.get("graded_workdir")
    if gw:
        out["graded build"] = gw
    proj = env.get("project")
    if proj:
        out["UE project"] = proj
    return out


def _gates_caption(task_spec_excerpts: Optional[dict]) -> Optional[str]:
    """The task's behavioral gates, for the film strip's caption line — so a
    reviewer knows what the checkpoints are testing.

    Best source: the first fenced code block inside the spec's ``## Verifier
    specification`` excerpt (the authoring convention for the gated-assertion
    summary, e.g. gp-glide-stamina-bp's ``(1)..(5)`` block); fallback: the
    section's first prose paragraph. None when there is no spec — the strip
    then renders without a caption rather than with a fabricated one."""
    if not task_spec_excerpts:
        return None
    spec = (task_spec_excerpts.get("verifier_spec") or "").strip()
    if not spec:
        return None
    m = re.search(r"```[a-zA-Z]*\s*\n(.*?)\n```", spec, re.S)
    text = m.group(1).strip() if m else spec.split("\n\n", 1)[0].strip()
    return text[:2000] or None




def _synthetic_report(result: dict, task_id: Optional[str]) -> Optional[dict]:
    """Build a minimal single-shape report so the banner renders without a verifier.

    ``render_html(report=...)`` expects either the single-task shape
    (``{"task_id", "layers", ...}``) or the batch shape (``{"verdicts": [...]}``).
    When a run never reached the verifier (``result["verifier"] is None``), we
    hand-roll the single shape from ``result``'s top-level ``overall`` so the
    banner still shows the task id + outcome (e.g. an ``AGENT_FAILED`` /
    ``FAIL_NO_EDITS`` run). Returns ``None`` only when there is truly nothing to
    show (no task id and no overall) — render_html tolerates ``report=None``.
    """
    overall = result.get("overall") or result.get("verdict")
    if not task_id and not overall:
        return None
    timings = result.get("timings") or {}
    return {
        "task_id": task_id or "?",
        "overall": overall or "unknown",
        "duration_seconds": (result.get("agent") or {}).get("duration_s")
        or timings.get("grade_s") or timings.get("verify_s"),
        "layers": {},
    }


def render_run_report(repo_root: Union[str, Path], run_id: str) -> str:
    """Render ``runs/<run_id>/`` as a full self-contained single-run HTML report.

    Assembles ``render.py:render_html``'s inputs exactly as ``render.py:main`` does
    for a directory, then returns the HTML string. Degrades gracefully when the run
    lacks the rich Aura inputs (no conversation, no live workdir) or even a verifier
    report — renders whatever is present and never crashes on missing optional data.

    Raises ``RunNotFoundError`` (a ``LookupError``) if neither ``summary.json``
    nor ``result.json`` exists for ``run_id``.
    """
    repo_root = Path(repo_root)
    run_dir = resolve_run_dir(repo_root, run_id)
    return _render_run_dir(run_dir, repo_root, run_id=run_id)


def _render_run_dir(
    run_dir: Path,
    repo_root: Path,
    *,
    run_id: Optional[str] = None,
    artifact_base: Optional[str] = None,
) -> str:
    """Shared renderer body: web route (``run_id`` -> /api artifact hrefs) and
    static report.html (``artifact_base`` -> run-dir-relative hrefs) assemble
    render_html's inputs identically from here."""
    result, _envelope_path = _load_envelope(run_dir)

    task_id = _task_id_from_result(result)
    # The page heading (owner ask 2026-08-06 #1): the task NAME, straight from
    # the run's own data. Graded envelopes may carry a set-qualified id
    # ("bp/gp-poison-dot-stack-bp") — richer than the bare id, so it is
    # passed through verbatim; render_html still prefers a spec human title.
    raw_tid = result.get("task_id")
    heading = (raw_tid.replace("\\", "/").rstrip("/")
               if isinstance(raw_tid, str) and raw_tid else task_id)

    # 1. report -> render_html(report=...). Prefer the verifier's own report dict;
    #    synthesize a minimal banner-only report when the run never reached it.
    verifier = result.get("verifier")
    report: Optional[dict]
    if isinstance(verifier, dict):
        report = verifier
        if not task_id:
            task_id = _task_id_from_result({"verifier": verifier})
    else:
        report = _synthetic_report(result, task_id)

    # 2. task spec excerpts -> render_html(task_spec_excerpts=...). Auto-discover
    #    tasks/<task_id>.md the same way render.py:main does; optional.
    task_spec_excerpts: Optional[dict] = None
    if task_id:
        spec_path = find_task_spec(task_id, repo_root)
        if spec_path is not None and spec_path.exists():
            try:
                task_spec_excerpts = parse_task_spec_excerpts(spec_path)
            except OSError:
                task_spec_excerpts = None

    # 3. submission dir -> render_html(submission_dir=...). Baseline runs name
    #    it submission/; graded runs name it deliverable/. Optional;
    #    the renderer returns "" when it is missing or empty.
    submission_dir: Optional[Path] = None
    for sub_name in ("submission", "deliverable"):
        if (run_dir / sub_name).is_dir():
            submission_dir = run_dir / sub_name
            break

    # 4. swept capture screenshots -> render_html(artifacts=..., run_id=...).
    #    Same discovery the data layer uses (sorted *.png basenames under
    #    runs/<id>/artifacts/); [] for every pre-capture run, and render_html
    #    emits no section for an empty list.
    artifacts_dir = run_dir / "artifacts"
    artifacts: list = []
    if artifacts_dir.is_dir():
        try:
            artifacts = sorted(p.name for p in artifacts_dir.glob("*.png") if p.is_file())
        except OSError:
            artifacts = []

    # workdir=None: the verifier's /tmp workdir is gone by render time, so per-layer
    # log excerpts come only from any inline ``log_excerpt`` the report embedded.
    return render_html(
        report=report,
        task_spec_excerpts=task_spec_excerpts,
        submission_dir=submission_dir,
        workdir=None,
        artifacts=artifacts,
        run_id=run_id,
        run_summary=_run_summary_from_envelope(result) or None,
        artifact_base=artifact_base,
        heading=heading,
    )


def write_static_report(run_dir: Union[str, Path],
                        repo_root: Union[str, Path]) -> Path:
    """Write a self-contained ``report.html`` INTO ``run_dir`` and return its
    path — the no-server twin of the dashboard's ``/api/run/{id}/report``
    route (same renderer, same inputs). Artifact ``<img>`` hrefs are run-dir-
    relative (``artifacts/<name>``) so the page works as a double-clicked
    file. Raises on an unreadable envelope; the caller decides how loud to
    be."""
    run_dir = Path(run_dir)
    html = _render_run_dir(run_dir, Path(repo_root), artifact_base="artifacts")
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# FastAPI-mountable helper — (html, status_code), never raises for unknown run
# ---------------------------------------------------------------------------


def _error_page(title: str, message: str, run_id: str) -> str:
    """A tiny self-contained HTML page for the 404 / 500 cases.

    Standalone (no external assets) so it renders even if the dashboard's CDN is
    blocked, and small enough that the integration agent can return it verbatim.
    """
    import html as _html

    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_html.escape(title)}</title>"
        "<style>body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,"
        "Roboto,Helvetica,Arial,sans-serif;background:#f8fafc;color:#0f172a;"
        "margin:0;padding:48px}main{max-width:640px;margin:0 auto}"
        "h1{font-size:20px;margin:0 0 8px}p{color:#475569;line-height:1.5}"
        "code{font-family:ui-monospace,Menlo,Consolas,monospace;background:#e2e8f0;"
        "padding:1px 5px;border-radius:4px}</style></head>"
        "<body><main>"
        f"<h1>{_html.escape(title)}</h1>"
        f"<p>{_html.escape(message)}</p>"
        f"<p>run_id: <code>{_html.escape(run_id)}</code></p>"
        "</main></body></html>"
    )


def render_report_response(
    repo_root: Union[str, Path], run_id: str
) -> Tuple[str, int]:
    """Render ``run_id`` and return ``(html, status_code)`` for a FastAPI route.

    A route can mount this directly::

        from fastapi.responses import HTMLResponse
        from tools.dashboard.web.report_bridge import render_report_response

        @app.get("/api/run/{run_id}/report")
        def run_report(run_id: str) -> HTMLResponse:
            html, status = render_report_response(app.state.repo_root, run_id)
            return HTMLResponse(content=html, status_code=status)

    Status codes:
      * 200 — rendered the report.
      * 404 — no such run_id (clean ``RunNotFoundError`` -> 404 HTML page).
      * 500 — an unexpected render failure (e.g. corrupt result.json) -> 500 page.

    Never raises — the caller can return the tuple unconditionally.
    """
    try:
        return render_run_report(repo_root, run_id), 200
    except LookupError:
        return (
            _error_page(
                "Run not found",
                "No run with this id exists under runs/. It may have been removed, "
                "or never started.",
                run_id,
            ),
            404,
        )
    except Exception as exc:  # noqa: BLE001 — surface as a 500 page, never crash the route
        return (
            _error_page(
                "Report unavailable",
                f"Could not render this run's report: {exc}",
                run_id,
            ),
            500,
        )
