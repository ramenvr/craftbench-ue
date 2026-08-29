"""Opt-in screenshot capture (--capture) + the artifact sweep.

No UE needed — run_l2 / the editor subprocess are monkeypatched (same style as
test_l3_render.py). Covers:

  - collect_screenshots: copy Saved/CraftBench/*.png -> out_dir/artifacts/,
    run-dir-relative return paths, label prefixing, empty no-op.
  - run_l2(capture=True) appends -CraftBenchCapture to the editor cmd, and the
    determinism switches (-deterministic / -FPS) are NEVER dropped.
  - L2Layer threads capture into every run_l2 call (single + dt legs), sweeps
    after each leg (fps<hz>_ label on dt legs) into
    ctx.advisory_out["visual_artifacts"], and SKIPS the nullrhi-0-tests retry
    branch under capture.
  - Defaults unchanged: capture off => no -CraftBenchCapture, no sweep, no
    advisory key.
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

from layers.base import LayerContext  # noqa: E402
from layers.registry import L2Layer, collect_screenshots  # noqa: E402
import layers.l2_pie as l2pie  # noqa: E402


def _stub_l2(status="pass", tests_skipped=0):
    tests_run = 1 if status != "skipped" else 0
    from layers.l2_pie import L2Result
    # Build the REAL dataclass, not a hand-rolled namespace: this double has
    # broken on every field added to L2Result (rhi_unavailable, 2026-08-10, was
    # the third such break). The dataclass's own defaults now absorb new fields.
    return L2Result(
        status=status, log_path=Path("/tmp/l2.log"), duration_seconds=1.0,
        tests_run=tests_run, tests_passed=1 if status == "pass" else 0,
        tests_failed=0, tests_skipped=tests_skipped, notes=[], exit_code=0,
        report_path=None, result_source="json",
    )


def _drop_png(workdir: Path, name: str) -> Path:
    shot = workdir / "Saved" / "CraftBench" / name
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b"\x89PNG fake content")
    return shot


def _ctx(workdir: Path, *, capture=True, use_nullrhi=True,
         fps_legs=(), map_name=None, test_class_hint=None,
         test_filter="My.Explicit.Filter") -> LayerContext:
    task = types.SimpleNamespace(
        task_id="t", layers=("L1", "L2"), raw_text="", map_name=map_name,
        test_class_hint=test_class_hint,
        fixtures=(), introspect_scripts=(), artifact_path=None,
        l3_fixtures=(), fps_legs=fps_legs,
    )
    args = types.SimpleNamespace(
        ue_root=Path("/ue"), test_filter=test_filter,
        use_nullrhi=use_nullrhi, capture=capture, r2=False,
    )
    out_dir = workdir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return LayerContext(
        task=task, args=args, project_path=workdir / "x.uproject",
        workdir_substrate=workdir, out_dir=out_dir,
        manifest=types.SimpleNamespace(writable=(), game_module="m"),
        substrate_src=Path("/s"), requested_layers={"L1", "L2"},
    )


class TestCollectScreenshots(unittest.TestCase):
    def test_copies_pngs_and_returns_relative_paths(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_png(d, "b_shot.png")
            _drop_png(d, "a_shot.png")
            out = d / "out"
            rel = collect_screenshots(d, out)
            self.assertEqual(rel, ["artifacts/a_shot.png", "artifacts/b_shot.png"])
            for r in rel:
                self.assertTrue((out / r).is_file(), f"missing copy {r}")
            # Sources are copied, not moved.
            self.assertTrue((d / "Saved" / "CraftBench" / "a_shot.png").exists())

    def test_label_prefixes_filenames(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_png(d, "shot.png")
            out = d / "out"
            rel = collect_screenshots(d, out, label="fps20_")
            self.assertEqual(rel, ["artifacts/fps20_shot.png"])
            self.assertTrue((out / "artifacts" / "fps20_shot.png").is_file())

    def test_no_screenshots_is_a_noop(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "out"
            self.assertEqual(collect_screenshots(d, out), [])
            # No artifacts dir is created for an empty sweep.
            self.assertFalse((out / "artifacts").exists())

    def test_only_pngs_are_swept(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_png(d, "shot.png")
            (d / "Saved" / "CraftBench" / "trace.log").write_text("x", encoding="utf-8")
            rel = collect_screenshots(d, d / "out")
            self.assertEqual(rel, ["artifacts/shot.png"])


def _drop_umap(workdir: Path, *rel_parts: str) -> Path:
    """Create Content/Maps/<rel_parts...> with fake binary content."""
    umap = workdir / "Content" / "Maps"
    for part in rel_parts:
        umap = umap / part
    umap.parent.mkdir(parents=True, exist_ok=True)
    umap.write_bytes(b"\x00fake umap")
    return umap


class TestL2LayerMapLocation(unittest.TestCase):
    """L2Layer discovers the map's on-disk location and threads it into
    run_l2 (map_package_path) + derive_test_filter (prefix_for_map)."""

    def test_foldered_map_passes_package_path_and_foldered_filter(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "t0-folder", "L_SanityTask.umap")
            ctx = _ctx(d, capture=False, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest",
                       test_filter=None)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["map_package_path"],
                             "/Game/Maps/t0-folder/L_SanityTask")
            self.assertEqual(
                calls[0]["test_filter"],
                "Project.Functional Tests.Maps.t0-folder"
                ".L_SanityTask.SanityFunctionalTest",
            )

    def test_root_map_passes_flat_package_path_and_flat_filter(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_SanityTask.umap")
            ctx = _ctx(d, capture=False, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest",
                       test_filter=None)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                L2Layer().run(ctx)

            self.assertEqual(calls[0]["map_package_path"],
                             "/Game/Maps/L_SanityTask")
            self.assertEqual(
                calls[0]["test_filter"],
                "Project.Functional Tests.Maps.L_SanityTask"
                ".SanityFunctionalTest",
            )

    def test_dt_legs_thread_package_path_into_every_leg(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "t0-folder", "L_SanityTask.umap")
            ctx = _ctx(d, capture=False, fps_legs=(60, 20),
                       map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest",
                       test_filter=None)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual([kw["fps"] for kw in calls], [60, 20])
            self.assertTrue(all(
                kw["map_package_path"] == "/Game/Maps/t0-folder/L_SanityTask"
                for kw in calls))

    def test_missing_map_keeps_none_package_path(self):
        # No map on disk anywhere (and map_name=None so no scaffold attempt):
        # run_l2 gets map_package_path=None — today's behavior unchanged.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=False)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                L2Layer().run(ctx)

            self.assertIsNone(calls[0]["map_package_path"])


class TestRunL2CaptureCmd(unittest.TestCase):
    """run_l2 cmd construction — the editor subprocess is faked."""

    def _run(self, tmp: Path, **kwargs):
        captured = {}

        def fake_marker_kill(*, cmd, env, log_path, timeout_seconds):
            captured["cmd"] = list(cmd)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("TestResult=Passed\n", encoding="utf-8")
            return (0, False)

        fake_editor = tmp / "UnrealEditor-Cmd"
        fake_editor.write_text("stub", encoding="utf-8")
        with mock.patch.object(l2pie, "_editor_binary", lambda ue_root: fake_editor), \
             mock.patch.object(l2pie, "_run_editor_with_marker_kill", fake_marker_kill):
            res = l2pie.run_l2(
                ue_root=tmp,
                project_path=tmp / "p.uproject",
                test_filter="A.B.C",
                log_path=tmp / "l2.log",
                **kwargs,
            )
        return res, captured["cmd"]

    def test_capture_true_appends_switch_and_keeps_determinism(self):
        with tempfile.TemporaryDirectory() as d:
            res, cmd = self._run(Path(d), capture=True)
            self.assertIn("-CraftBenchCapture", cmd)
            self.assertIn("-deterministic", cmd)
            self.assertIn("-FPS=60", cmd)
            self.assertEqual(res.status, "pass")

    def test_capture_default_off_no_switch(self):
        with tempfile.TemporaryDirectory() as d:
            _, cmd = self._run(Path(d))
            self.assertNotIn("-CraftBenchCapture", cmd)
            # Determinism switches stay unconditional in all modes.
            self.assertIn("-deterministic", cmd)
            self.assertIn("-FPS=60", cmd)

    def test_capture_with_real_rhi_keeps_determinism(self):
        with tempfile.TemporaryDirectory() as d:
            _, cmd = self._run(Path(d), capture=True, use_nullrhi=False)
            self.assertNotIn("-nullrhi", cmd)
            self.assertIn("-CraftBenchCapture", cmd)
            self.assertIn("-deterministic", cmd)
            self.assertIn("-FPS=60", cmd)

    def test_map_package_path_used_verbatim_as_positional(self):
        # A DISCOVERED foldered package path wins over the flat derivation.
        with tempfile.TemporaryDirectory() as d:
            _, cmd = self._run(
                Path(d), map_name="L_X",
                map_package_path="/Game/Maps/some-task/L_X",
            )
            self.assertEqual(cmd[2], "/Game/Maps/some-task/L_X")
            self.assertNotIn("/Game/Maps/L_X", cmd)
            # -nullrhi still lands AFTER the map positional.
            self.assertEqual(cmd[3], "-nullrhi")

    def test_map_name_only_keeps_flat_positional(self):
        # Back-compat: no package path -> the legacy flat form.
        with tempfile.TemporaryDirectory() as d:
            _, cmd = self._run(Path(d), map_name="L_X")
            self.assertEqual(cmd[2], "/Game/Maps/L_X")
            self.assertEqual(cmd[3], "-nullrhi")


class TestL2LayerCapture(unittest.TestCase):
    def test_single_call_passes_capture_and_sweeps(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=True, use_nullrhi=False)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                _drop_png(d, "l2_shot.png")  # the fixture writes during PIE
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(len(calls), 1)
            self.assertIs(calls[0]["capture"], True)
            self.assertEqual(rep.status, "pass")
            self.assertEqual(ctx.advisory_out.get("visual_artifacts"),
                             ["artifacts/l2_shot.png"])
            self.assertTrue((ctx.out_dir / "artifacts" / "l2_shot.png").is_file())

    def test_capture_off_default_no_sweep_no_switch(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=False)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                # Even if a stray PNG exists, the default path must not sweep it.
                _drop_png(d, "stray.png")
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                L2Layer().run(ctx)

            self.assertIs(calls[0]["capture"], False)
            self.assertNotIn("visual_artifacts", ctx.advisory_out)
            self.assertFalse((ctx.out_dir / "artifacts").exists())

    def test_capture_attr_missing_defaults_off(self):
        # Callers that build args without the new flag keep old behavior.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=False)
            del ctx.args.capture
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                L2Layer().run(ctx)

            self.assertIs(calls[0]["capture"], False)
            self.assertNotIn("visual_artifacts", ctx.advisory_out)

    def test_dt_legs_prefix_artifacts_per_fps(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=True, use_nullrhi=False, fps_legs=(60, 20))
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                _drop_png(d, f"shot_fps{kw['fps']}.png")
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual([kw["fps"] for kw in calls], [60, 20])
            self.assertTrue(all(kw["capture"] is True for kw in calls))
            arts = ctx.advisory_out["visual_artifacts"]
            self.assertIn("artifacts/fps60_shot_fps60.png", arts)
            self.assertIn("artifacts/fps20_shot_fps20.png", arts)
            self.assertTrue(
                (ctx.out_dir / "artifacts" / "fps60_shot_fps60.png").is_file())
            self.assertTrue(
                (ctx.out_dir / "artifacts" / "fps20_shot_fps20.png").is_file())

    def test_nullrhi_zero_tests_retry_skipped_under_capture(self):
        # The skipped/0-tests retry re-runs without -nullrhi; under --capture
        # use_nullrhi is already real-RHI territory, so the retry must not fire.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=True, use_nullrhi=True)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("skipped", tests_skipped=0)

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(len(calls), 1)  # NO retry under capture
            self.assertEqual(rep.status, "skipped")

    def test_nullrhi_zero_tests_retry_still_fires_without_capture(self):
        # Guardrail: the pre-existing retry behavior is unchanged by default.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, capture=False, use_nullrhi=True)
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("skipped", tests_skipped=0)

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                L2Layer().run(ctx)

            self.assertEqual(len(calls), 2)  # original retry preserved
            self.assertIs(calls[1]["use_nullrhi"], False)


if __name__ == "__main__":
    unittest.main()
