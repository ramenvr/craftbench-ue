"""The example layer proves the 'add a method = write a Layer + append' workflow.

It runs the example through the SAME run_layers loop the production layers use,
showing selection, a real gating verdict, dependency short-circuit, and that it
composes with the real REGISTRY — all without editing run_task.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from report import LayerReport  # noqa: E402
from layers.base import Layer, LayerContext  # noqa: E402
from layers.registry import REGISTRY, run_layers  # noqa: E402
from layers.example_layer import ExampleArtifactLayer  # noqa: E402


def _ctx(workdir: Path, layers=("EX",)) -> LayerContext:
    task = types.SimpleNamespace(layers=layers, introspect_scripts=(), raw_text="",
                                 map_name=None, fixtures=(), task_id="demo")
    manifest = types.SimpleNamespace(writable=("Source/CraftBenchTemplate/",),
                                     game_module="CraftBenchTemplate")
    return LayerContext(
        task=task, args=types.SimpleNamespace(r2=False),
        project_path=workdir / "x.uproject", workdir_substrate=workdir,
        out_dir=workdir / "out", manifest=manifest, substrate_src=Path("/s"),
        requested_layers=set(layers),
    )


class _StubL1:
    key, gating, order, requires = "L1", True, 10, ()
    def __init__(self, status="pass"): self._s = status
    def applies(self, ctx): return True
    def run(self, ctx): return LayerReport(status=self._s, notes=["stub L1"])


class TestExampleLayer(unittest.TestCase):
    def test_conforms_to_protocol(self):
        self.assertIsInstance(ExampleArtifactLayer(), Layer)

    def test_applies_on_token(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(ExampleArtifactLayer().applies(_ctx(Path(d), layers=("EX",))))
            self.assertFalse(ExampleArtifactLayer().applies(_ctx(Path(d), layers=("L1",))))

    def test_real_pass_when_artifact_present(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Source").mkdir()
            (d / "Source" / "Thing.cpp").write_text("// content", encoding="utf-8")
            rep = ExampleArtifactLayer().run(_ctx(d))
            self.assertEqual(rep.status, "pass")
            self.assertEqual(rep.tests_passed, 1)

    def test_real_fail_when_artifact_absent(self):
        with tempfile.TemporaryDirectory() as d:
            rep = ExampleArtifactLayer().run(_ctx(Path(d)))   # no Source/ dir
            self.assertEqual(rep.status, "fail")

    def test_plugs_into_run_layers_alongside_real_registry(self):
        # The headline ergonomics proof: append the example to the registry and
        # it runs through the same loop — no run_task edits.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Source").mkdir()
            (d / "Source" / "A.cpp").write_text("x", encoding="utf-8")
            reg = [ExampleArtifactLayer()]            # a one-item custom registry
            layers_out, _ = run_layers(_ctx(d), registry=reg)
            self.assertIn("EX", layers_out)
            self.assertEqual(layers_out["EX"].status, "pass")

    def test_requires_short_circuit(self):
        # A variant that depends on L1 is skipped when L1 fails — for free.
        # order must be > L1's so L1 runs first (requires respects run order).
        class ExNeedsL1(ExampleArtifactLayer):
            requires = ("L1",)
            order = 15

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Source").mkdir()
            (d / "Source" / "A.cpp").write_text("x", encoding="utf-8")
            reg = [_StubL1(status="fail"), ExNeedsL1()]
            layers_out, _ = run_layers(_ctx(d), registry=reg)
            self.assertEqual(layers_out["EX"].status, "skipped")
            self.assertIn("short-circuited: L1 did not pass", layers_out["EX"].notes)

    def test_example_is_not_in_production_registry(self):
        # It's documentation-as-code, never auto-runs in real grading.
        self.assertNotIn("EX", {l.key for l in REGISTRY})


if __name__ == "__main__":
    unittest.main()
