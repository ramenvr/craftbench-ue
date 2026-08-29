"""CraftBench dashboard — web UI subpackage (FastAPI + a static single page).

This is one of the two read-only viewers that sit on top of the shared,
pure-stdlib data layer (``tools.dashboard.collect.collect`` -> ``Snapshot``).
It launches NOTHING: no agent run, no UnrealEditor, no writes into the repo —
it only re-serves what ``collect()`` finds on disk, so the team can open one URL
and browse the cross-product matrix / failures / coverage gaps / head-to-head.

Why a server (and not a static dump): the dashboard must reflect ``runs/`` as it
grows during a sweep. ``app.create_app(repo_root)`` re-runs ``collect()`` on every
``GET /api/snapshot`` (cheap — pure disk globbing) and exposes an SSE ``/events``
stream that pushes when ``runs/`` mtime changes, so an open tab live-updates
without a manual reload. The client is a single self-contained ``index.html``
(vanilla JS + Tailwind via CDN, no build step) so sharing is "run one command,
send a localhost URL" with no node toolchain.

Re-exports ``create_app`` and a module-level ``app`` (the conventional ASGI
target) for ``uvicorn tools.dashboard.web.app:app`` and the TestClient suite —
LAZILY (PEP 562): ``report_bridge`` is deliberately fastapi-free (cb's eval
tail imports it to write each run's static report.html on installs that never
installed the UI deps), so importing this package must not execute ``app.py``.
"""

__all__ = ["app", "create_app"]


def __getattr__(name):
    if name in __all__:
        from .app import app as _app, create_app as _create_app
        # Importing .app just bound the SUBMODULE as this package's ``app``
        # attribute; rebind both names to the intended objects so every
        # subsequent lookup (which bypasses __getattr__) stays consistent.
        globals()["app"], globals()["create_app"] = _app, _create_app
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
