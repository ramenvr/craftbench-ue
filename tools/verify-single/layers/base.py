"""Pluggable verification-layer protocol + shared context.

A Layer is one self-contained verification method (build, PIE test, asset
introspection, advisory judge). The runner iterates a REGISTRY of Layers instead
of hand-coding each one in main(): every Layer decides whether it applies,
declares its gating policy + dependencies, and returns a uniform LayerReport.

Selection, gating, and short-circuit dependencies — the three things that were
inconsistent across L1/L2/L2I/R2 — are now first-class on the Layer:

- ``applies(ctx)``  hides each method's selection channel (L-token vs section-
  presence vs --flag) behind one predicate.
- ``gating``        True  → the layer contributes to the certified ``overall``;
                    False → advisory only (routed to ctx.advisory_out, e.g. R2).
- ``requires``      keys of layers that must PASS first, else this layer is
                    short-circuited to "skipped" (e.g. L2/L2I require L1).

Adding a verification method becomes: write a Layer + append it to the registry.
See layers/registry.py for the concrete adapters.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Protocol, Tuple, runtime_checkable

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from report import LayerReport  # noqa: E402


@dataclass
class LayerContext:
    """Everything a Layer needs, assembled once by the runner after pre-flight.

    Types are duck-typed (Any) so this module stays decoupled from run_task —
    the registry adapters bind the concrete helpers lazily to avoid an import
    cycle.
    """

    task: Any                       # TaskSpec
    args: Any                       # argparse.Namespace
    project_path: Path              # workdir <substrate>.uproject
    workdir_substrate: Path         # cloned substrate root in the workdir
    out_dir: Path                   # where per-layer logs/reports are written
    manifest: Any                   # WritableManifest (writable prefixes, game_module)
    substrate_src: Path             # pristine substrate root (R2 re-clones from it)
    requested_layers: set           # L-tokens selected for this run
    # Sandbox-accepted submission rel-paths (POSIX). Feeds both the L2I
    # accepted-file environment and its asset-integrity preamble; empty when
    # the run has no --submission (or the caller predates the field).
    submitted_files: Tuple[str, ...] = ()

    # Filled in by the runner loop as layers complete.
    prior: Dict[str, LayerReport] = field(default_factory=dict)
    # Non-gating layers write their rich payloads here (e.g. "R2" -> advisory dict).
    advisory_out: Dict[str, dict] = field(default_factory=dict)

    @property
    def agent_prefixes(self) -> Tuple[str, ...]:
        return tuple(self.manifest.writable)


@runtime_checkable
class Layer(Protocol):
    key: str                        # report key, e.g. "L1" / "L2" / "L2I" / "R2"
    gating: bool                    # contributes to certified overall?
    order: int                      # run order (ascending)
    requires: Tuple[str, ...]       # layer keys that must PASS before this runs.
    #                                 NOTE: a required layer must have a LOWER
    #                                 `order` (run first) for the short-circuit to
    #                                 see its result — run_layers does not topo-sort.

    def applies(self, ctx: LayerContext) -> bool: ...
    def run(self, ctx: LayerContext) -> LayerReport: ...
