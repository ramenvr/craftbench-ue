"""CraftBench dashboard — read-only visualization of what already exists on disk.

This package is a *viewer*, not a runner: it never launches an agent, never
invokes UnrealEditor, and never writes into the repo. Both UIs (the Textual TUI
and the FastAPI web app) sit on top of one shared, pure-stdlib data layer:

    collect.collect(repo_root) -> model.Snapshot

``model`` is the frozen data model (pure stdlib). ``collect`` discovers
``runs/**/result.json`` + sibling ``verifier_stdout.txt`` and ``tasks/*.md``,
and delegates *all* matrix / head-to-head / grounding math to the existing
``tools/compare/compare_products.py`` (the single intra-repo, non-stdlib import,
isolated inside ``Snapshot.comparison()``). The UI layers depend on this package;
this package depends on neither textual nor fastapi.

Re-exports the data-layer entry points for ergonomic import
(``from tools.dashboard import collect, watch, Snapshot``).
"""

from .collect import collect, watch
from .model import LayerResult, Run, Snapshot, Task

__all__ = ["collect", "watch", "Snapshot", "Task", "Run", "LayerResult"]
