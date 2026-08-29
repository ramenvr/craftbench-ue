"""Worked example: adding a verification method as a pluggable Layer.

THIS IS THE COPY-PASTE TEMPLATE for a new verification method. To ship a real
one you do exactly two things, and touch nothing else in run_task:

    1. Copy this class, rename it, implement applies() + run().
    2. Append an instance to REGISTRY in layers/registry.py.

That's the whole "add a method" workflow the pluggable refactor bought us — no
edits to main()'s spine, no new result type, no new selection channel to teach.

``ExampleArtifactLayer`` is a REAL, deterministic, no-UE layer (so this file is
itself runnable + tested, not a hand-wave): it passes iff a required artifact
path under the applied workspace contains at least one non-empty file — a cheap
"did the deliverable actually land" structural floor. It demonstrates every part
of the Layer protocol; see layers/base.py for the contract and layers/registry.py
for the four production layers (L1/L2/L2I/R2).

It is intentionally NOT in REGISTRY — it's documentation-as-code. The test
(tests/test_example_layer.py) registers it via run_layers(..., registry=[...]) to
prove it plugs in (applies / gating / requires short-circuit) end to end.
"""
from __future__ import annotations

import sys
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from report import LayerReport  # noqa: E402
from layers.base import LayerContext  # noqa: E402


class ExampleArtifactLayer:
    # --- Protocol fields: WHAT this layer is, and WHEN it runs ---------------
    key = "EX"            # report key in Report.layers (and the L-token if token-selected)
    gating = True         # True  → contributes to the certified `overall`
    #                       False → advisory only (routed to ctx.advisory_out, like R2)
    order = 5             # run order, ascending (5 runs before L1's 10)
    requires = ()         # layer keys that must PASS first, else this is short-circuited
    #                       to "skipped" by run_layers (e.g. set ("L1",) to need a build)

    # Customisation point for this example: the workspace-relative path that
    # must contain a non-empty deliverable. A real layer would derive this from
    # the task spec instead of hardcoding it.
    required_artifact = "Source"

    def applies(self, ctx: LayerContext) -> bool:
        """Selection channel — return True iff this layer should run for the task.

        Here we key off an "EX" token in the declared layer set. A section-
        triggered layer would instead inspect the task (see L2IntrospectLayer,
        which returns ``bool(ctx.task.introspect_scripts)``); a flag-gated one
        would check ``ctx.args`` (see R2Layer).
        """
        return "EX" in ctx.requested_layers

    def run(self, ctx: LayerContext) -> LayerReport:
        """Do the verification and return a uniform LayerReport.

        Read everything from ``ctx`` (no globals). Return status pass|fail|skipped
        plus any optional fields (exit_code, duration_seconds, tests_run/passed,
        notes). That uniform shape is what let main() stop special-casing layers.
        """
        target = ctx.workdir_substrate / self.required_artifact
        files = (
            [p for p in target.rglob("*") if p.is_file() and p.stat().st_size > 0]
            if target.exists()
            else []
        )
        ok = bool(files)
        return LayerReport(
            status="pass" if ok else "fail",
            tests_run=1,
            tests_passed=1 if ok else 0,
            notes=[f"{self.required_artifact}: {len(files)} non-empty file(s) present"],
        )
