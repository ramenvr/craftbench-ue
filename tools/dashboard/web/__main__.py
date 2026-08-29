"""``python3 -m tools.dashboard.web`` — launch the dashboard web UI via uvicorn.

Prints the localhost URL up front (so the operator can click/share it) and then
serves the dashboard FastAPI app. Binds to 127.0.0.1 by default.

NOT read-only, and NOT safe to expose. ``POST /api/launch`` spawns a real
graded run — it spends your model API key and takes a filesystem path into
the child argv — and there is no authentication of any kind. Anyone who can
reach the port can do that. Binding a non-loopback host therefore requires
``--allow-remote-launch``, so exposing it is always a deliberate act on a
network you trust.

``--repo-root`` lets you point the viewer at a different CraftBench checkout
(matching the TUI's override); it defaults to the repo this file lives in.
``--reload`` is offered for development of the app itself, NOT required to see new
runs — the app re-collects per request, so a live sweep shows up without reload.

Imports uvicorn (the ASGI server) — kept out of ``app.py`` so the app stays
importable (and testable) without a server runtime.
"""

from __future__ import annotations

import argparse
import sys
import pathlib

import uvicorn

from .app import _DEFAULT_REPO_ROOT, create_app

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765


def _parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.dashboard.web",
        description="Serve the CraftBench dashboard web UI. NOT read-only: "
                    "POST /api/launch spawns real graded runs, unauthenticated.",
    )
    ap.add_argument("--host", default=_DEFAULT_HOST, help="bind host (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=_DEFAULT_PORT, help="bind port (default 8765)")
    ap.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=_DEFAULT_REPO_ROOT,
        help="CraftBench checkout root (dir containing runs/ + tasks/)",
    )
    ap.add_argument(
        "--allow-remote-launch",
        action="store_true",
        help="permit binding a non-loopback --host. Required because the app "
             "exposes an UNAUTHENTICATED POST /api/launch that spawns graded "
             "runs and spends your model API key.",
    )
    ap.add_argument(
        "--reload",
        action="store_true",
        help="uvicorn auto-reload (for app development; not needed to see new runs)",
    )
    return ap.parse_args(argv)


#: Hosts that only the local machine can reach. Anything else is reachable by
#: someone else, and this app has no authentication at all.
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", ""})


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.host not in _LOOPBACK and not args.allow_remote_launch:
        print(
            f"REFUSING to bind {args.host}: this app is not read-only. It serves\n"
            "an UNAUTHENTICATED POST /api/launch that spawns a real graded run --\n"
            "spending your model API key -- and passes a caller-supplied path into\n"
            "the child argv. Anyone who can reach the port can do that.\n\n"
            "Re-run with --allow-remote-launch if that is genuinely what you want\n"
            "on a network you trust.",
            file=sys.stderr,
        )
        return 2
    repo_root = args.repo_root.resolve()
    url = f"http://{args.host}:{args.port}/"
    print(f"CraftBench dashboard serving {repo_root}")
    print(f"  open: {url}")
    print(f"  api : {url}api/snapshot")
    print("  (Ctrl-C to stop)")

    if args.reload:
        # Reload mode needs an import string; bind repo root via the default app.
        # (The default ``app`` targets the repo this file lives in; --repo-root is
        # ignored under --reload, which is a development-only convenience.)
        uvicorn.run(
            "tools.dashboard.web.app:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(repo_root), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
