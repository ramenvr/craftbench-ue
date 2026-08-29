"""FastAPI app for the CraftBench dashboard — read-only JSON + a static page.

The app is a thin re-server over the data layer: every request re-runs
``collect(repo_root)`` (pure disk globbing, no UE, no agent, no writes) and hands
back ``Snapshot.to_dict()``. There is no in-process cache of the snapshot on the
hot path *by design* — ``runs/`` grows while a sweep is live, and re-collecting
per request (a handful of ``glob`` + small JSON reads) is far cheaper than the
risk of serving a stale matrix. A short mtime fingerprint guards the SSE stream so
we only push when something actually changed.

Routes (v1, read-only):
  GET  /                 -> web/static/index.html (the single-page client)
  GET  /api/snapshot     -> Snapshot.to_dict() (the full payload; ?latest_only=)
  GET  /api/run/{run_id} -> one run's detail (summary + per-layer + cost/duration)
  GET  /api/run/{run_id}/artifact/{name} -> one swept capture PNG (FileResponse);
                            validated against the run's COLLECTED artifact list —
                            no path is ever joined from raw user input
  GET  /events           -> Server-Sent-Events: pushes a fresh snapshot when the
                            runs/ + tasks/ mtime fingerprint changes (live update)

Routes (v1.5 — drill-in + launch; this is where the dashboard stops being purely
read-only, since /api/launch can spawn a real run via the canonical harness):
  GET  /api/run/{run_id}/report -> the full self-contained single-run HTML report
                            (re-uses render.py via report_bridge; 404 on unknown)
  GET  /api/launch/options      -> {tasks, models, backends} for the launch panel
  POST /api/launch              -> validate + spawn one (task × model) run via
                            tools/run-agent/run.py in the background -> {job_id}
  GET  /api/jobs                -> all launched jobs' status envelopes, newest first
  GET  /api/jobs/{job_id}       -> one job's status envelope (404 if unknown)

``create_app(repo_root)`` is a factory so the TestClient suite can point the app
at a synthetic repo; the module-level ``app`` resolves the real checkout root
(``parents[3]`` of this file: tools/dashboard/web/app.py -> repo root) and is the
ASGI target ``uvicorn ...:app`` / ``python3 -m tools.dashboard.web`` use. A single
``JobManager`` is stashed on ``app.state`` so its in-memory job table survives
across requests.

Imports ``fastapi`` only (plus stdlib + the in-repo data layer + the web-side
``report_bridge`` / ``launcher`` helpers, which themselves pull only render/stdlib).
The pure-stdlib data layer (``collect`` / ``model``) stays UI-dependency-free.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from ..collect import collect
from . import launcher
from .report_bridge import render_report_response, resolve_run_dir

# tools/dashboard/web/app.py -> parents: [0]=web [1]=dashboard [2]=tools [3]=repo
_DEFAULT_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

# SSE poll cadence (seconds) — how often the server re-fingerprints runs/ + tasks/
# to decide whether to push. Independent of the client's own /api/snapshot poll;
# the client uses /events when available and falls back to polling otherwise.
_SSE_INTERVAL = 2.0


def _fingerprint(repo_root: pathlib.Path) -> float:
    """Max mtime over runs/**/result.json + verifier_stdout.txt + task specs.

    A cheap change-detector for the SSE stream. We deliberately reuse the same
    file set ``collect.watch`` watches (minus the path-set tiebreak, which only
    matters for equal-mtime add/deletes — acceptable for a live refresher).
    Task specs are watched in EVERY shape — root/set flat ``.md`` plus the
    folder-form ``tasks/<set>/<id>/task.md`` — so a change to any spec in any
    layout moves the fingerprint. When this float moves, we re-collect and
    push. ``0.0`` when nothing exists yet.
    """
    latest = 0.0
    for pattern_base, pattern in (
        ("runs", "**/result.json"),
        ("runs", "**/verifier_stdout.txt"),
        ("tasks", "*.md"),
        ("tasks", "*/*.md"),
        ("tasks", "*/*/task.md"),
    ):
        for p in (repo_root / pattern_base).glob(pattern):
            try:
                latest = max(latest, p.stat().st_mtime)
            except OSError:
                continue
    return latest


def _run_detail(payload: Dict[str, Any], run_id: str) -> Optional[Dict[str, Any]]:
    """Pull one run dict out of an already-built ``to_dict()`` payload.

    The per-run detail the modal needs (summary, per-layer results, cost,
    duration, blocker) already lives verbatim in ``payload["runs"]`` — we just
    index it by ``run_id`` rather than re-deriving, so /api/run can never drift
    from /api/snapshot. We also attach the run's task metadata (capability,
    declared layers, prompt excerpt) so the modal can render context without a
    second round-trip. Returns None when no run matches.
    """
    run = next((r for r in payload.get("runs", []) if r.get("run_id") == run_id), None)
    if run is None:
        return None
    task = next(
        (t for t in payload.get("tasks", []) if t.get("task_id") == run.get("task_id")),
        None,
    )
    return {"run": run, "task": task}


def create_app(repo_root: pathlib.Path = _DEFAULT_REPO_ROOT) -> FastAPI:
    """Build the FastAPI app bound to ``repo_root`` (factory; tests override it).

    Binding the repo root at construction time (rather than reading a global)
    lets the TestClient suite spin the app over a synthetic tempdir repo. All
    routes re-collect on demand from this root — the app holds no snapshot state.
    """
    repo_root = pathlib.Path(repo_root).resolve()
    app = FastAPI(
        title="CraftBench dashboard",
        version="1.0",
        description="Read-only viewer of CraftBench runs/ — cross-product pass-rate matrix.",
    )
    # Store on app.state so tests / handlers can read the bound root.
    app.state.repo_root = repo_root

    # ONE JobManager per app — its in-memory job table must survive across
    # requests, so it lives on app.state (not a per-request local). Bound to the
    # same repo_root; its default command_builder targets tools/run-agent/run.py.
    # Tests that want to avoid spawning run.py construct their own create_app and
    # then swap app.state.job_manager for a JobManager with a fake builder.
    app.state.job_manager = launcher.JobManager(repo_root)

    @app.get("/api/snapshot")
    def api_snapshot(latest_only: bool = Query(False)) -> JSONResponse:
        """The full dashboard payload (re-collected fresh on every request).

        ``latest_only=true`` dedupes duplicate (product, task) attempts to the
        newest before the comparison math — the escape hatch for the all-attempts
        matrix inflating n on re-run sweeps. Default false matches compare's
        n-counting.
        """
        payload = collect(repo_root).to_dict(latest_only=latest_only)
        return JSONResponse(payload)

    @app.get("/api/run/{run_id}")
    def api_run(run_id: str) -> JSONResponse:
        """One run's detail: the run row + its task context, 404 if unknown.

        Backs the cell-click modal. We index into a freshly collected payload so
        the detail is always consistent with the matrix the client just rendered.
        """
        payload = collect(repo_root).to_dict()
        detail = _run_detail(payload, run_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"no run with run_id={run_id!r}")
        return JSONResponse(detail)

    @app.get("/api/run/{run_id}/artifact/{name}")
    def api_run_artifact(run_id: str, name: str) -> FileResponse:
        """Serve ONE swept capture PNG for a run; 404 unless fully validated.

        SECURITY: nothing from the URL is path-joined raw. ``run_id`` must
        resolve to a known *collected* run and ``name`` must be in that run's
        collected artifact list (basenames from a ``glob`` — they can never
        contain a separator). Defense in depth on top of that allowlist:
        ``resolve_run_dir`` rejects ``..`` / separators / glob chars and only
        yields ``runs/<run_id>`` or ``runs/<container>/<run_id>`` (the
        per-backend folders), and the rebuilt artifact path must still be a
        direct child of that run's ``artifacts/`` after ``resolve()`` (rejects
        symlink escapes), and the file must exist. Any miss is a uniform 404 —
        the route never distinguishes "unknown run" from "bad name" to a prober.
        """
        snap = collect(repo_root)
        run = next((r for r in snap.runs if r.run_id == run_id), None)
        if run is None or name not in run.artifacts:
            raise HTTPException(
                status_code=404,
                detail=f"no artifact {name!r} for run_id={run_id!r}",
            )
        try:
            run_dir = resolve_run_dir(repo_root, run_id)
        except LookupError:
            raise HTTPException(
                status_code=404,
                detail=f"no artifact {name!r} for run_id={run_id!r}",
            )
        art_dir = run_dir / "artifacts"
        path = (art_dir / name).resolve()
        if path.parent != art_dir.resolve() or not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"no artifact {name!r} for run_id={run_id!r}",
            )
        return FileResponse(path, media_type="image/png")


    @app.get("/api/run/{run_id}/report")
    def api_run_report(run_id: str) -> HTMLResponse:
        """The FULL single-run HTML report (banner + task spec + submission + logs).

        Re-uses ``render.py`` via ``report_bridge`` — we do not reimplement any
        report HTML here. ``render_report_response`` never raises: it returns
        ``(html, 200)`` for a rendered run, ``(html, 404)`` for an unknown run_id
        (incl. path-traversal ids, which the bridge treats as unknown), and
        ``(html, 500)`` for a corrupt run envelope (``summary.json`` on graded
        runs, else ``result.json``) — always a real HTML page so
        the client can drop it straight into an iframe. This is a sync ``def``
        handler doing disk I/O (read the envelope, parse the task spec, walk the
        submission dir); FastAPI offloads it to the threadpool, so the blocking
        read never stalls the event loop / the SSE stream.
        """
        html, status = render_report_response(app.state.repo_root, run_id)
        return HTMLResponse(content=html, status_code=status)

    @app.get("/api/launch/options")
    def api_launch_options() -> JSONResponse:
        """Selectable tasks + suggested model slugs for the launch panel.

        ``tasks`` are the real task specs on disk — root stems plus
        set-qualified ``<set>/<id>`` ids, either layout (the only launchable
        set — ``JobManager.start`` re-checks against disk, so a stale listing can
        never smuggle a non-existent task through). ``models`` is an *advisory*
        seed of common ``(backend:model)`` operating points; the authoritative
        gate is ``launcher.MODEL_SLUG_RE`` (any conforming slug is accepted, so
        the UI may let a user type one). ``backends`` is the four RUNNABLE
        adapter prefixes — claude-p, unreal-mcp, bare, openrouter. Backends this
        repository cannot drive (aura-mcp and the removed private lanes) are
        deliberately absent: the panel only ever offers what a clone can run.
        """
        return JSONResponse(
            {
                "tasks": launcher.available_tasks(app.state.repo_root),
                # v1.5.1: route-aware launch. routes = the 4 user-facing tool-layers
                # (baseline -> claude-p); each route carries its own model menu via
                # models_by_route (claude-p/unreal-mcp -> native Claude ids;
                # openrouter/bare -> provider/model ids) and a ``live_editor`` flag
                # the client reads instead of keeping its own lane list;
                # ue_root_default is auto-located so the field comes pre-filled.
                "routes": launcher.available_routes(),
                "models_by_route": launcher.models_by_route(),
                "ue_root_default": launcher.default_ue_root(),
                # back-compat (older clients): flat advisory lists.
                "models": launcher.available_models(),
                "backends": launcher.known_backends(),
            }
        )

    @app.post("/api/launch")
    def api_launch(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
        """Validate + spawn ONE ``(task × model)`` run in the background -> {job_id}.

        This is the single write action in the dashboard — it shells the canonical
        harness ``tools/run-agent/run.py`` as an **argv list** (never a shell
        string) via ``JobManager.start``. Validation happens BEFORE any spawn:
        ``task_id`` (bare or set-qualified) must resolve to a real task spec
        under ``tasks/`` and ``model`` must match the
        product-slug regex; a bad request raises ``ValueError`` in the launcher,
        which we surface as a 400 (no job is ever registered for invalid input).

        Body: ``{task_id, model, ue_root?, live_project?}``. The live-editor
        contract is surfaced honestly — an ``unreal-mcp:*`` launch needs
        ``ue_root`` + ``live_project=true`` + a live editor; if those are absent,
        ``run.py`` itself fails and the job shows ``failed`` with its captured
        log. The launcher does NOT manage UE. A slug naming a lane this
        repository cannot drive (``aura-mcp:*``, or a removed private lane) is
        refused by name as a 400 before any spawn.
        """
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")
        task_id = payload.get("task_id")
        route = payload.get("route")
        model = payload.get("model")
        if not isinstance(task_id, str) or not isinstance(model, str):
            raise HTTPException(
                status_code=400, detail="task_id and model are required strings"
            )
        # Compose the backend:model slug. Preferred path: (route, model) — the UI
        # picks a route (baseline/unreal-mcp/openrouter/bare) + a per-route model.
        # Back-compat: a full "backend:model" slug in `model` (no route) is accepted.
        try:
            if isinstance(route, str) and route:
                slug = launcher.compose_slug(route, model)
            elif ":" in model:
                slug = model
            else:
                raise ValueError("provide a route + model, or a full backend:model slug")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        ue_root = payload.get("ue_root") or None
        if ue_root is not None and not isinstance(ue_root, str):
            raise HTTPException(status_code=400, detail="ue_root must be a string")
        # Auto-locate UE if the caller didn't supply a root (the panel pre-fills it,
        # but a bare POST still gets the detected install).
        if ue_root is None:
            ue_root = launcher.default_ue_root()
        live_project = bool(payload.get("live_project", False))
        try:
            job_id = app.state.job_manager.start(
                task_id,
                slug,
                ue_root=ue_root,
                live_project=live_project,
            )
        except ValueError as exc:
            # Pre-spawn validation failure (unknown task / bad model slug). No job
            # was registered; reject with the launcher's own message.
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse({"job_id": job_id}, status_code=202)

    @app.get("/api/jobs")
    def api_jobs() -> JSONResponse:
        """All launched jobs' status envelopes, newest first (JSON-safe; no Popen)."""
        return JSONResponse(app.state.job_manager.list())

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str) -> JSONResponse:
        """One job's status envelope; 404 when the job_id is unknown."""
        status = app.state.job_manager.status(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"no job with job_id={job_id!r}")
        return JSONResponse(status)

    @app.post("/api/jobs/{job_id}/cancel")
    def api_job_cancel(job_id: str) -> JSONResponse:
        """Best-effort terminate a running job (kills the child); 404 if unknown.

        ``cancelled`` is True only if a live process was actually signalled — a job
        that already finished returns ``cancelled: false``. Pairs with the watcher's
        wall-clock timeout so a wedged run.py / UE can always be reaped.
        """
        if app.state.job_manager.status(job_id) is None:
            raise HTTPException(status_code=404, detail=f"no job with job_id={job_id!r}")
        cancelled = app.state.job_manager.cancel(job_id)
        return JSONResponse({"job_id": job_id, "cancelled": cancelled})

    @app.get("/events")
    async def events(request: Request) -> StreamingResponse:
        """Server-Sent-Events: push a fresh snapshot when runs/ mtime changes.

        Live update without client polling: the client opens this once and the
        server emits a ``data: <snapshot-json>`` frame on the first connect and
        again whenever the mtime fingerprint of runs/ + tasks/ moves. Heartbeats
        (SSE comment lines) keep proxies from idling the connection out. The loop
        ends when the client disconnects. This is a convenience layer — the
        client still falls back to polling /api/snapshot if /events is blocked.
        """

        def _snapshot_json() -> str:
            return json.dumps(collect(repo_root).to_dict())

        async def stream():
            # collect()/_fingerprint() are SYNC and disk-I/O-heavy (glob runs/** +
            # read every result.json + verifier_stdout.txt). Offload them to a
            # thread so a single uvicorn worker's event loop is never blocked for
            # other SSE/HTTP connections while one client's snapshot is computed.
            # Emit one data frame on connect (blocking SSE clients wait on the
            # first read), then push only when the mtime fingerprint moves.
            last_fp = await asyncio.to_thread(_fingerprint, repo_root)
            yield f"data: {await asyncio.to_thread(_snapshot_json)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(_SSE_INTERVAL)
                fp = await asyncio.to_thread(_fingerprint, repo_root)
                if fp != last_fp:
                    last_fp = fp
                    yield f"data: {await asyncio.to_thread(_snapshot_json)}\n\n"
                else:
                    # SSE comment line as a heartbeat (ignored by EventSource).
                    yield ": keep-alive\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            },
        )

    @app.get("/")
    def index() -> FileResponse:
        """Serve the single-page client (vanilla JS + Tailwind CDN, no build)."""
        if not _INDEX_HTML.is_file():
            raise HTTPException(status_code=500, detail="index.html missing")
        return FileResponse(_INDEX_HTML, media_type="text/html")

    # Mount the static dir last so it never shadows the explicit routes above.
    # html=False: the explicit "/" route owns the index; this serves assets only.
    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


# Module-level ASGI target for ``uvicorn tools.dashboard.web.app:app`` and the
# ``python3 -m tools.dashboard.web`` launcher. Bound to the real checkout root.
app = create_app()
