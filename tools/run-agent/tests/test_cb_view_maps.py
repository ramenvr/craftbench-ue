"""cb view map resolution: _resolve_map_arg (bare L_* names through per-task
folders) + _graded_task_map (the composed task's map off the .cb-staged
marker). Pure path logic — no UE, no editor launch."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig.cb import _graded_task_map, _resolve_map_arg  # noqa: E402


def _project(tc: unittest.TestCase) -> Path:
    td = tempfile.TemporaryDirectory()
    tc.addCleanup(td.cleanup)
    return Path(td.name)


def _umap(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x00fake umap")


def _marker(root: Path, **fields) -> None:
    (root / ".cb-staged").write_text(json.dumps(fields), encoding="utf-8")


class TestResolveMapArg(unittest.TestCase):
    def test_full_package_path_passes_through(self):
        proj = _project(self)
        self.assertEqual(
            _resolve_map_arg(proj, "/Game/Maps/t0-x/L_SanityTask"),
            "/Game/Maps/t0-x/L_SanityTask")

    def test_bare_name_resolves_through_per_task_folder(self):
        # The bug: /Game/Maps/L_SanityTask is WRONG for a foldered map — the
        # editor opens the default level instead of the task map.
        proj = _project(self)
        _umap(proj, "Content/Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap")
        self.assertEqual(
            _resolve_map_arg(proj, "L_SanityTask"),
            "/Game/Maps/t0-sanity-log-on-beginplay/L_SanityTask")

    def test_bare_name_resolves_flat_root_map(self):
        proj = _project(self)
        _umap(proj, "Content/Maps/L_Armor.umap")
        self.assertEqual(_resolve_map_arg(proj, "L_Armor"), "/Game/Maps/L_Armor")

    def test_umap_suffix_stripped(self):
        proj = _project(self)
        _umap(proj, "Content/Maps/L_Armor.umap")
        self.assertEqual(_resolve_map_arg(proj, "L_Armor.umap"),
                         "/Game/Maps/L_Armor")

    def test_unknown_name_falls_back_to_legacy_flat_form(self):
        proj = _project(self)
        self.assertEqual(_resolve_map_arg(proj, "L_Nope"), "/Game/Maps/L_Nope")

    def test_msys_mangled_arg_is_healed_to_package_path(self):
        # git-bash (MSYS) rewrites a leading /Game/... into a Windows path
        # before Python runs (FAILURE-LOG 2026-07-23); the healed value must
        # resolve exactly as the un-mangled package path (passthrough).
        proj = _project(self)
        self.assertEqual(
            _resolve_map_arg(proj,
                             "C:/Program Files/Git/Game/t0-x/L_SanityTask"),
            "/Game/t0-x/L_SanityTask")

    def test_weird_absolute_input_falls_back_without_raising(self):
        # An absolute path WITHOUT a /Game/ mount can't heal; its stem is a
        # non-relative rglob pattern (NotImplementedError on 3.12) — that
        # must never escape cb view, just miss into the legacy flat form.
        proj = _project(self)
        _umap(proj, "Content/Maps/L_Armor.umap")  # maps_root exists -> rglob runs
        self.assertEqual(
            _resolve_map_arg(proj, "D:/weird/place/L_Thing"),
            "/Game/Maps/D:/weird/place/L_Thing")

    def test_empty_name_is_empty(self):
        self.assertEqual(_resolve_map_arg(_project(self), ""), "")


class TestGradedTaskMap(unittest.TestCase):
    def test_per_task_folder_wins(self):
        proj = _project(self)
        _marker(proj, task_id="t0-sanity-log-on-beginplay",
                root_maps_kept=["L_RenderProbe"])
        _umap(proj, "Content/Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap")
        self.assertEqual(_graded_task_map(proj),
                         "/Game/Maps/t0-sanity-log-on-beginplay/L_SanityTask")

    def test_flat_task_uses_kept_root_map_minus_renderprobe(self):
        # Pre-migration bp-g2 shape: no per-task map folder; the compose marker
        # records the spec-named survivors + the shared L_RenderProbe (infra).
        proj = _project(self)
        _marker(proj, task_id="g2-1-armor",
                root_maps_kept=["L_Armor", "L_RenderProbe"])
        self.assertEqual(_graded_task_map(proj), "/Game/Maps/L_Armor")

    def test_ambiguous_kept_maps_yield_empty(self):
        proj = _project(self)
        _marker(proj, task_id="g2-x",
                root_maps_kept=["L_A", "L_B", "L_RenderProbe"])
        self.assertEqual(_graded_task_map(proj), "")

    def test_no_marker_yields_empty(self):
        self.assertEqual(_graded_task_map(_project(self)), "")


class TestViewSafety(unittest.TestCase):
    """2026-07-23 review fixes: view/review must never blanket-kill foreign
    editors nor kill a LIVE run's editor mid-drive."""

    def test_stop_headless_editor_uses_scoped_kill(self):
        from unittest import mock
        from aura_rig import cb as _cb, stack as _stack
        with mock.patch.object(_stack, "kill_craftbench_editors") as scoped, \
             mock.patch.object(_stack, "kill_by_image") as blanket:
            _cb._stop_headless_editor()
        scoped.assert_called_once()
        blanket.assert_not_called()

    def test_refuse_if_live_run_while_lock_held(self):
        from types import SimpleNamespace
        from aura_rig.cb import _refuse_if_live_run
        from live_lock import live_run_lock
        repo = _project(self)
        (repo / "runs").mkdir()
        ctx = SimpleNamespace(paths=SimpleNamespace(craftbench=repo))
        lock = repo / "runs" / ".live-run.lock"
        with live_run_lock(lock):
            self.assertTrue(_refuse_if_live_run(ctx))
        self.assertFalse(_refuse_if_live_run(ctx))


if __name__ == "__main__":
    unittest.main()
