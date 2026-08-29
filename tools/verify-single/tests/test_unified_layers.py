"""Unified `## Verifier layers` declaration block + the ART artifact floor.

One block now declares every layer + its inline config (replacing the four-channel
scheme: L-tokens / section-presence / fixtures block / prose regex), while the
legacy parsing remains a backward-compatible fallback for un-migrated tasks.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
_REPO = _VERIFY.parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from run_task import _parse_verifier_layers_block, parse_task_spec  # noqa: E402
from report import LayerReport  # noqa: E402
from layers.base import LayerContext  # noqa: E402
from layers.registry import ArtifactLayer, REGISTRY, run_layers  # noqa: E402


class TestUnifiedBlockParser(unittest.TestCase):
    def test_keys_and_inline_config(self):
        block = (
            "- L1\n"
            "- L2 (fixtures: L_A :: AAFunctionalTest, L_B :: ABFunctionalTest)\n"
            "- L2I (scripts: foo.py, bar.py)\n"
            "- R2\n"
            "- ART (artifact: Content/Tasks/x/OVERVIEW.md)\n"
            "prose line is ignored\n"
        )
        parsed = _parse_verifier_layers_block(block)
        self.assertEqual(list(parsed), ["L1", "L2", "L2I", "R2", "ART"])  # order preserved
        self.assertEqual(parsed["L2"]["fixtures"], "L_A :: AAFunctionalTest, L_B :: ABFunctionalTest")
        self.assertEqual(parsed["ART"]["artifact"], "Content/Tasks/x/OVERVIEW.md")
        self.assertEqual(parsed["L1"], {})

    def test_empty_section_yields_empty(self):
        self.assertEqual(_parse_verifier_layers_block(""), {})


class TestParseTaskSpecUnified(unittest.TestCase):
    def _write(self, body: str) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / "t.md"
        p.write_text("## Task ID and metadata\n\n- task_id: t\n- substrate: template\n\n" + body,
                     encoding="utf-8")
        return p

    def test_unified_block_populates_fields(self):
        p = self._write(
            "## Verifier layers\n\n"
            "- L1\n"
            "- L2 (fixtures: L_Map :: AMapFunctionalTest)\n"
            "- L2I (scripts: thing.py)\n"
            "- ART (artifact: Content/Tasks/t/OUT.md)\n"
        )
        spec = parse_task_spec(p)
        self.assertEqual(set(spec.layers), {"L1", "L2", "L2I", "ART"})
        self.assertEqual([(f.map_name, f.test_class) for f in spec.fixtures],
                         [("L_Map", "AMapFunctionalTest")])
        self.assertEqual(spec.introspect_scripts, ("thing.py",))
        self.assertEqual(spec.artifact_path, "Content/Tasks/t/OUT.md")

    def test_legacy_parsing_still_works_without_unified_block(self):
        p = self._write(
            "## Verifier layers used\n\nL1, L2\n\n"
            "## Verifier introspection\n\n- legacy.py\n"
        )
        spec = parse_task_spec(p)
        self.assertEqual(set(spec.layers), {"L1", "L2"})
        self.assertEqual(spec.introspect_scripts, ("legacy.py",))
        self.assertIsNone(spec.artifact_path)

    # (test_real_summarize_project_migrated was removed in the fresh-start
    # cull along with its subject spec, tasks/flagship/summarize-project —
    # no surviving task declares the ART advisory layer.)


class TestArtifactLayer(unittest.TestCase):
    def _ctx(self, workdir: Path, artifact):
        task = types.SimpleNamespace(layers=("ART",), introspect_scripts=(), raw_text="",
                                     map_name=None, fixtures=(), task_id="t", artifact_path=artifact)
        manifest = types.SimpleNamespace(writable=("Content/Tasks/",), game_module="CraftBenchTemplate")
        return LayerContext(task=task, args=types.SimpleNamespace(r2=False),
                            project_path=workdir / "x.uproject", workdir_substrate=workdir,
                            out_dir=workdir, manifest=manifest, substrate_src=Path("/s"),
                            requested_layers={"ART"})

    def test_in_registry_and_opt_in(self):
        self.assertIn("ART", {l.key for l in REGISTRY})
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(ArtifactLayer().applies(self._ctx(Path(d), None)))   # no artifact_path
            self.assertTrue(ArtifactLayer().applies(self._ctx(Path(d), "x.md")))

    def test_pass_when_present_fail_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            rel = "Content/Tasks/t/OUT.md"
            (d / "Content" / "Tasks" / "t").mkdir(parents=True)
            (d / rel).write_text("real content", encoding="utf-8")
            self.assertEqual(ArtifactLayer().run(self._ctx(d, rel)).status, "pass")
        with tempfile.TemporaryDirectory() as d:  # missing
            self.assertEqual(ArtifactLayer().run(self._ctx(Path(d), "Content/Tasks/t/OUT.md")).status, "fail")

    def test_empty_artifact_fails(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "OUT.md").write_text("", encoding="utf-8")   # 0 bytes
            self.assertEqual(ArtifactLayer().run(self._ctx(d, "OUT.md")).status, "fail")

    def test_runs_through_run_layers(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "OUT.md").write_text("x", encoding="utf-8")
            layers_out, _ = run_layers(self._ctx(d, "OUT.md"), registry=[ArtifactLayer()])
            self.assertEqual(layers_out["ART"].status, "pass")


if __name__ == "__main__":
    unittest.main()
