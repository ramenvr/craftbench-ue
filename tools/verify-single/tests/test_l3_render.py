"""L3 render layer (PIE path): declared via the unified block as a fixture, runs a
REAL-RHI PIE functional test (run_l2), and records the screenshot artifact for R2.
No UE needed — run_l2 is monkeypatched. (One-shot editor-Python rendered black; PIE
ticks → content, validated live 2026-06-02 with ARenderProbeFunctionalTest.)
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from run_task import parse_task_spec  # noqa: E402
from layers.base import LayerContext  # noqa: E402
from layers.registry import REGISTRY, L3RenderLayer, _l3_test_filter  # noqa: E402
import layers.l2_pie as l2pie  # noqa: E402


def _stub_l2(status="pass"):
    from layers.l2_pie import L2Result
    # Real dataclass — see the note in test_capture_artifacts._stub_l2.
    return L2Result(
        status=status, log_path=Path("/tmp/l3.log"), duration_seconds=1.0,
        tests_run=1, tests_passed=1 if status == "pass" else 0, tests_failed=0,
        tests_skipped=0, notes=["pie note"], exit_code=0, report_path=None, result_source="json",
    )


def _ctx(workdir: Path, fixtures=(("L_RenderProbe", "ARenderProbeFunctionalTest"),)) -> LayerContext:
    fx = tuple(types.SimpleNamespace(map_name=m, test_class=c) for m, c in fixtures)
    task = types.SimpleNamespace(layers=("L1", "L3"), introspect_scripts=(), raw_text="",
                                 map_name=None, fixtures=(), task_id="t",
                                 artifact_path=None, l3_fixtures=fx)
    return LayerContext(
        task=task, args=types.SimpleNamespace(ue_root=Path("/ue"), r2=False),
        project_path=workdir / "x.uproject", workdir_substrate=workdir,
        out_dir=workdir, manifest=types.SimpleNamespace(writable=(), game_module="m"),
        substrate_src=Path("/s"), requested_layers={"L1", "L3"},
    )


def _drop_umap(workdir: Path, map_name: str) -> Path:
    """Maps ship as committed binaries (scaffolders retired 2026-07) — the L3
    layer now hard-FAILs on a locate_map miss, so run tests must stage one."""
    umap = workdir / "Content" / "Maps" / f"{map_name}.umap"
    umap.parent.mkdir(parents=True, exist_ok=True)
    umap.write_bytes(b"\x00fake umap")
    return umap


class TestL3Parsing(unittest.TestCase):
    def test_unified_block_l3_fixtures(self):
        d = Path(tempfile.mkdtemp())
        (d / "t.md").write_text(
            "## Task ID and metadata\n\n- task_id: t\n\n"
            "## Verifier layers\n\n- L1\n- L3 (fixtures: L_RenderProbe :: ARenderProbeFunctionalTest)\n",
            encoding="utf-8")
        spec = parse_task_spec(d / "t.md")
        self.assertEqual([(f.map_name, f.test_class) for f in spec.l3_fixtures],
                         [("L_RenderProbe", "ARenderProbeFunctionalTest")])
        self.assertIn("L3", spec.layers)


class TestFilter(unittest.TestCase):
    def test_strips_A_prefix(self):
        self.assertEqual(_l3_test_filter("L_RenderProbe", "ARenderProbeFunctionalTest"),
                         "Project.Functional Tests.Maps.L_RenderProbe.RenderProbeFunctionalTest")


class TestL3RegistryMetadata(unittest.TestCase):
    def test_l3_registered_gating_requires_l1(self):
        by_key = {l.key: l for l in REGISTRY}
        self.assertIn("L3", by_key)
        self.assertTrue(by_key["L3"].gating)
        self.assertEqual(by_key["L3"].requires, ("L1",))


class TestL3RunUsesPIE(unittest.TestCase):
    def test_real_rhi_pie_and_screenshot_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_RenderProbe")
            shot = d / "Saved" / "CraftBench" / "l3_renderprobe.png"
            shot.parent.mkdir(parents=True)
            shot.write_bytes(b"\x89PNG content")
            captured = {}

            def fake_run_l2(**kw):
                captured["use_nullrhi"] = kw["use_nullrhi"]
                captured["filter"] = kw["test_filter"]
                captured["map"] = kw["map_name"]
                captured["expected_test_count"] = kw["expected_test_count"]
                return _stub_l2("pass")

            ctx = _ctx(d)
            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L3RenderLayer().run(ctx)

            self.assertIs(captured["use_nullrhi"], False)        # REAL RHI for rendering
            self.assertEqual(captured["map"], "L_RenderProbe")
            self.assertEqual(captured["filter"],
                             "Project.Functional Tests.Maps.L_RenderProbe.RenderProbeFunctionalTest")
            # Each L3 leg runs exactly ONE declared fixture — the leg-count
            # guard threads through so a filter collision over-count FAILs.
            self.assertEqual(captured["expected_test_count"], 1)
            self.assertEqual(rep.status, "pass")
            self.assertTrue(any("screenshot:" in n and "l3_renderprobe.png" in n for n in rep.notes))
            self.assertIn("L3_visual", ctx.advisory_out)         # handed to R2 visual track

    def test_fixture_fail_fails_layer(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_RenderProbe")
            with mock.patch.object(l2pie, "run_l2", lambda **kw: _stub_l2("fail")):
                rep = L3RenderLayer().run(_ctx(d))
            self.assertEqual(rep.status, "fail")

    def test_no_screenshot_noted(self):
        with tempfile.TemporaryDirectory() as d:  # no Saved/CraftBench/*.png
            d = Path(d)
            _drop_umap(d, "L_RenderProbe")
            with mock.patch.object(l2pie, "run_l2", lambda **kw: _stub_l2("pass")):
                rep = L3RenderLayer().run(_ctx(d))
            self.assertTrue(any("no screenshot captured" in n for n in rep.notes))

    def test_missing_map_binary_is_explicit_fail_without_running(self):
        # Mirrors L2Layer: locate_map miss -> hard FAIL, run_l2 never invoked
        # (maps ship as committed binaries; scaffolders retired 2026-07).
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L3RenderLayer().run(_ctx(Path(d)))
            self.assertEqual(rep.status, "fail")
            self.assertEqual(calls, [])
            self.assertTrue(any("map binary missing: L_RenderProbe" in n
                                for n in rep.notes))


if __name__ == "__main__":
    unittest.main()
