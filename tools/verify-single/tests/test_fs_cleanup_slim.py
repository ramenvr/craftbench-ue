"""Offline tests for retention mode "slim" (fs_cleanup.slim_workdir). No UE needed.

Every test builds a synthetic workdir laid out the way a real one is — measured on
C:\\cb\\wd\\<hash> on 2026-07-25: the substrate cloned to <workdir>/<SubstrateName>/,
the verifier's out/ dir as its SIBLING — and asserts on the two halves of the
contract that actually cost money if they break:

  * the DELETE half (~5.5 GB of the 5.54 GB a kept workdir costs) really goes, and
  * the KEEP half — out/, Saved/, DerivedDataCache/, the UHT Inc/ output, the
    loadable Binaries — really survives. A slim that eats the report or the crash
    dump has destroyed the only reason the workdir was kept.

Two of these are regression guards rather than feature tests:
  * one project is deliberately named ThirdPersonTemplate, so a "CraftBenchTemplate"
    hardcoded anywhere in the locator turns into a silent no-op on half the fleet
    (the repo is substrate-pinned to TWO substrates, not one), and
  * the allow-root gate is exercised from outside the root, because this is code
    whose failure mode is deleting the wrong 5 GB.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import fs_cleanup  # noqa: E402


def _write(path: Path, size: int = 16) -> Path:
    """Create ``path`` with exactly ``size`` bytes, so a reclaim total can be
    checked against arithmetic rather than against a re-walk of the same tree."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


class _WorkdirFixture(unittest.TestCase):
    """A synthetic workdir under a temp allow-root.

    ``PROJECT`` is a class attribute so a subclass can re-run the whole battery
    against a different substrate name — that is the anti-hardcoding lever.
    """

    PROJECT = "CraftBenchTemplate"

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="slimtest-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.wd = self.root / "wd" / "08085611c8"
        self.proj = self.wd / self.PROJECT

        # --- the verifier's own output: SIBLING of the project, must survive ----
        self.keep_report = _write(self.wd / "out" / "report.json", 40)
        self.keep_index = _write(self.wd / "out" / "l2_report" / "index.json", 40)
        _write(self.wd / "out" / "l1_build.log", 40)

        # --- the project ------------------------------------------------------
        _write(self.proj / f"{self.PROJECT}.uproject", 32)
        self.keep_src = _write(
            self.proj / "Source" / self.PROJECT / "SanityActor.cpp", 64)
        self.keep_content = _write(
            self.proj / "Content" / "Maps" / "L_SanityTask.umap", 64)
        self.keep_config = _write(self.proj / "Config" / "DefaultEngine.ini", 64)
        self.keep_ddc = _write(self.proj / "DerivedDataCache" / "cache.udd", 2048)
        self.keep_dmp = _write(self.proj / "Saved" / "Crashes" / "x.dmp", 128)
        self.keep_png = _write(self.proj / "Saved" / "CraftBench" / "shot.png", 128)
        _write(self.proj / "Saved" / "Logs" / f"{self.PROJECT}.log", 128)

        # --- Binaries: keep the loadable, drop the debug/link scaffolding ------
        bins = self.proj / "Binaries" / "Win64"
        self.keep_dll = _write(bins / f"UnrealEditor-{self.PROJECT}.dll", 512)
        self.keep_modules = _write(bins / "UnrealEditor.modules", 24)
        self.keep_target = _write(bins / f"{self.PROJECT}.target", 24)
        self.keep_editor_target = _write(bins / f"{self.PROJECT}Editor.target", 24)
        self.keep_nested_dll = _write(bins / "D3D12" / "D3D12RHI.dll", 256)
        self.gone_pdb = _write(bins / f"UnrealEditor-{self.PROJECT}.pdb", 4096)
        self.gone_exe = _write(bins / f"{self.PROJECT}.exe", 2048)
        self.gone_lib = _write(bins / f"{self.PROJECT}.lib", 256)
        self.gone_exp = _write(bins / f"{self.PROJECT}.exp", 128)
        self.gone_iobj = _write(bins / f"{self.PROJECT}.iobj", 64)
        self.gone_ipdb = _write(bins / f"{self.PROJECT}.ipdb", 64)
        self.gone_nested_pdb = _write(bins / "D3D12" / "D3D12RHI.pdb", 1024)

        # --- Intermediate: x64/ and CachedAssetRegistry/ go, the rest stays ----
        build = self.proj / "Intermediate" / "Build" / "Win64"
        self.gone_obj_tree = build / "x64"
        self.gone_obj = _write(
            self.gone_obj_tree / self.PROJECT / "Development" / "SanityActor.cpp.obj",
            8192)
        self.gone_pch = _write(
            self.gone_obj_tree / self.PROJECT / "Development" / "SharedPCH.h.pch",
            8192)
        inc = build / "UnrealEditor" / "Inc" / self.PROJECT / "UHT"
        self.keep_generated = _write(inc / "SanityActor.generated.h", 96)
        self.keep_manifest = _write(inc / f"{self.PROJECT}.uhtmanifest", 96)
        self.keep_deps = _write(inc / "SanityActor.gen.cpp.deps", 96)
        self.keep_action_history = _write(build / "ActionHistory.bin", 32)
        self.gone_registry_tree = self.proj / "Intermediate" / "CachedAssetRegistry"
        self.gone_registry = _write(self.gone_registry_tree / "registry.bin", 4096)
        self.keep_registry_discovery = _write(
            self.proj / "Intermediate" / "CachedAssetRegistryDiscovery.bin", 32)
        self.keep_shader_autogen = _write(
            self.proj / "Intermediate" / "ShaderAutogen" / "Autogen.ush", 32)

    def slim(self, **kw) -> fs_cleanup.SlimStats:
        kw.setdefault("allow_root", self.root)
        return fs_cleanup.slim_workdir(self.wd, **kw)

    def assertGone(self, *paths: Path) -> None:
        for p in paths:
            self.assertFalse(p.exists(), f"should have been slimmed away: {p}")

    def assertKept(self, *paths: Path) -> None:
        for p in paths:
            self.assertTrue(p.exists(), f"slim destroyed a KEEP path: {p}")


class TestSlimDeletes(_WorkdirFixture):
    """The reclaim half: the 5.5 GB of pure build byproduct really goes."""

    def test_obj_tree_is_gone_but_generated_headers_survive(self) -> None:
        # Inc/ is a SIBLING of x64/, so the wholesale tree delete must not reach it.
        # These headers are the forensic artifact when UHT fails — the exact run
        # whose workdir someone chose to keep.
        stats = self.slim()
        self.assertGone(self.gone_obj_tree, self.gone_obj, self.gone_pch)
        self.assertKept(self.keep_generated, self.keep_manifest, self.keep_deps,
                        self.keep_action_history)
        self.assertFalse(stats.refused)

    def test_cached_asset_registry_tree_is_gone(self) -> None:
        # 119 MB whose only cost is one registry scan on the next launch. Its
        # *Discovery.bin sibling is NOT in the delete list and must stay.
        self.slim()
        self.assertGone(self.gone_registry_tree, self.gone_registry)
        self.assertKept(self.keep_registry_discovery, self.keep_shader_autogen)

    def test_binaries_matched_by_extension_not_by_name(self) -> None:
        self.slim()
        self.assertKept(self.keep_dll, self.keep_modules, self.keep_target,
                        self.keep_editor_target, self.keep_nested_dll)
        self.assertGone(self.gone_pdb, self.gone_exe, self.gone_lib, self.gone_exp,
                        self.gone_iobj, self.gone_ipdb, self.gone_nested_pdb)

    def test_reclaimed_bytes_and_deleted_paths_are_accounted(self) -> None:
        victims = (self.gone_obj, self.gone_pch, self.gone_registry, self.gone_pdb,
                   self.gone_exe, self.gone_lib, self.gone_exp, self.gone_iobj,
                   self.gone_ipdb, self.gone_nested_pdb)
        expected_bytes = sum(p.stat().st_size for p in victims)
        stats = self.slim()
        self.assertEqual(stats.reclaimed_bytes, expected_bytes)
        # deleted_paths counts OPERATIONS, not the files inside a tree:
        # 2 trees + 6 flat Binaries files + 1 nested Binaries file = 9,
        # against the 10 individual files those operations actually removed.
        self.assertEqual(stats.deleted_paths, 9)
        self.assertEqual(len(victims), 10)
        self.assertGreaterEqual(stats.elapsed_s, 0.0)
        self.assertEqual([n for n in stats.notes if n.startswith("PARTIAL")], [])

    def test_reclaimed_mb_matches_bytes(self) -> None:
        stats = self.slim()
        self.assertAlmostEqual(
            stats.reclaimed_mb, round(stats.reclaimed_bytes / 1048576.0, 1))

    def test_second_pass_is_a_no_op(self) -> None:
        # Retention may be re-run (a resumed sweep, a double-registered hook); the
        # second pass must reclaim nothing and still not raise or report PARTIAL.
        self.slim()
        again = self.slim()
        self.assertEqual(again.reclaimed_bytes, 0)
        self.assertEqual(again.deleted_paths, 0)
        self.assertFalse(again.refused)
        self.assertEqual([n for n in again.notes if n.startswith("PARTIAL")], [])


class TestSlimKeeps(_WorkdirFixture):
    """The half that costs a debuggable run if it regresses."""

    def test_out_dir_and_saved_artifacts_survive(self) -> None:
        # out/ is the whole point of keeping a workdir; Saved/ carries the crash
        # dump and the --capture checkpoint PNGs the dashboard links to.
        self.slim()
        self.assertKept(self.keep_report, self.keep_index,
                        self.keep_dmp, self.keep_png)

    def test_derived_data_cache_survives(self) -> None:
        # 2 MB = 0.04% of the reclaim; a cold DDC risks a shader stall in the
        # real-RHI preview PIE leg, which reads as a timeout, i.e. a false failure.
        self.slim()
        self.assertKept(self.keep_ddc)

    def test_project_sources_survive(self) -> None:
        self.slim()
        self.assertKept(self.keep_src, self.keep_content, self.keep_config,
                        self.proj / f"{self.PROJECT}.uproject")


class TestSlimThirdPersonSubstrate(TestSlimDeletes, TestSlimKeeps):
    """Re-runs the whole battery against the OTHER substrate.

    The repo is substrate-pinned to two projects (CraftBenchTemplate and
    ThirdPerson), and a workdir names its clone after whichever the spec selected.
    Nothing here is CraftBenchTemplate-shaped, so any hardcoded substrate name in
    the locator shows up as a wholesale no-op in this class rather than as a
    silently-unreclaimed disk in production."""

    PROJECT = "ThirdPersonTemplate"

    def test_located_project_is_the_third_person_one(self) -> None:
        stats = self.slim()
        self.assertEqual(stats.project_dir, str(self.wd / "ThirdPersonTemplate"))


class TestProjectLocation(_WorkdirFixture):
    """Locate-by-glob, and the degenerate layouts around it."""

    def test_project_located_by_glob_under_the_workdir(self) -> None:
        stats = self.slim()
        self.assertEqual(stats.project_dir, str(self.proj))

    def test_workdir_that_is_itself_the_project(self) -> None:
        # copy_lean_project tolerates this shape, so slim must too.
        flat = self.root / "flat"
        _write(flat / "Whatever.uproject", 32)
        obj = _write(flat / "Intermediate" / "Build" / "Win64" / "x64" / "a.obj", 99)
        stats = fs_cleanup.slim_workdir(flat, allow_root=self.root)
        self.assertEqual(stats.project_dir, str(flat))
        self.assertFalse(obj.exists())
        self.assertEqual(stats.reclaimed_bytes, 99)

    def test_no_uproject_reclaims_nothing_and_does_not_raise(self) -> None:
        bare = self.root / "bare"
        stray = _write(bare / "Intermediate" / "Build" / "Win64" / "x64" / "a.obj", 99)
        stats = fs_cleanup.slim_workdir(bare, allow_root=self.root)
        self.assertEqual(stats.reclaimed_bytes, 0)
        self.assertEqual(stats.deleted_paths, 0)
        self.assertFalse(stats.refused)
        self.assertTrue(stray.exists(), "no .uproject means no project — touch nothing")
        self.assertTrue(any("no *.uproject" in n for n in stats.notes), stats.notes)

    def test_missing_workdir_does_not_raise(self) -> None:
        stats = fs_cleanup.slim_workdir(self.root / "nope", allow_root=self.root)
        self.assertEqual(stats.reclaimed_bytes, 0)
        self.assertTrue(stats.notes)


class TestSlimSafetyGate(_WorkdirFixture):
    """The gate exists because the failure mode is deleting the wrong 5 GB."""

    def test_refuses_a_path_outside_the_allowed_root(self) -> None:
        outside = Path(tempfile.mkdtemp(prefix="slimtest-outside-")).resolve()
        self.addCleanup(shutil.rmtree, outside, True)
        _write(outside / "Proj" / "Proj.uproject", 32)
        obj = _write(
            outside / "Proj" / "Intermediate" / "Build" / "Win64" / "x64" / "a.obj",
            4096)
        stats = fs_cleanup.slim_workdir(outside, allow_root=self.root)
        self.assertTrue(stats.refused)
        self.assertEqual(stats.reclaimed_bytes, 0)
        self.assertEqual(stats.deleted_paths, 0)
        self.assertTrue(obj.exists(), "refusal must not have deleted anything")
        self.assertTrue(any("refused" in n for n in stats.notes), stats.notes)

    def test_refuses_a_parent_traversal_that_escapes_the_root(self) -> None:
        # The gate resolves BOTH sides first; a ".." that lands outside must not
        # pass just because the literal string starts inside the root.
        escape = self.root / ".." / os.path.basename(str(self.root)) / ".." / "elsewhere"
        stats = fs_cleanup.slim_workdir(escape, allow_root=self.root)
        self.assertTrue(stats.refused)
        self.assertEqual(stats.reclaimed_bytes, 0)

    def test_default_root_comes_from_aura_rig_wd_root(self) -> None:
        # No allow_root= -> the ONLY sanctioned root is aura_rig.paths.wd_root().
        # Faked here because tools/verify-single/tests has no aura_rig on sys.path;
        # the point is that slim CONSULTS it rather than trusting the caller.
        fake_pkg = types.ModuleType("aura_rig")
        fake_paths = types.ModuleType("aura_rig.paths")
        fake_paths.wd_root = lambda: self.root  # type: ignore[attr-defined]
        fake_pkg.paths = fake_paths  # type: ignore[attr-defined]
        with mock.patch.dict(sys.modules, {"aura_rig": fake_pkg,
                                           "aura_rig.paths": fake_paths}):
            stats = fs_cleanup.slim_workdir(self.wd)
        self.assertFalse(stats.refused, stats.notes)
        self.assertGone(self.gone_obj_tree)
        self.assertKept(self.keep_generated, self.keep_dll)

    def test_refuses_when_wd_root_is_unavailable_and_no_allow_root(self) -> None:
        # A None in sys.modules makes the lazy import raise ImportError — the
        # tools/verify-single context, where aura_rig is a different package.
        with mock.patch.dict(sys.modules, {"aura_rig": None,
                                           "aura_rig.paths": None}):
            stats = fs_cleanup.slim_workdir(self.wd)
        self.assertTrue(stats.refused)
        self.assertEqual(stats.reclaimed_bytes, 0)
        self.assertKept(self.gone_obj_tree)
        self.assertTrue(any("allow_root" in n for n in stats.notes), stats.notes)

    def test_module_imports_without_aura_rig_on_sys_path(self) -> None:
        # The lazy-import contract, stated as a test: run_task and warm_cache import
        # this module for robust_rmtree in a context that has no aura_rig at all.
        self.assertNotIn("aura_rig", getattr(fs_cleanup, "__dict__", {}))
        self.assertTrue(callable(fs_cleanup.robust_rmtree))


class TestSlimDeleterInjection(_WorkdirFixture):
    """``rmtree=`` is called for BOTH trees and single files (a slim pass deletes
    individual Binaries/ files), and a deleter that fails degrades to a note."""

    def test_injected_deleter_receives_trees_and_files(self) -> None:
        seen: list[Path] = []

        def recording(path):
            seen.append(Path(path))
            return fs_cleanup._remove_path(path)

        self.slim(rmtree=recording)
        self.assertIn(self.gone_obj_tree, seen)          # a directory tree
        self.assertIn(self.gone_registry_tree, seen)     # a directory tree
        self.assertIn(self.gone_pdb, seen)               # a single file
        self.assertNotIn(self.keep_dll, seen)
        self.assertNotIn(self.keep_ddc, seen)

    def test_deleter_that_deletes_nothing_reports_partial_not_reclaim(self) -> None:
        stats = self.slim(rmtree=lambda path: True)
        self.assertEqual(stats.reclaimed_bytes, 0, "nothing left the disk")
        self.assertEqual(stats.deleted_paths, 0)
        self.assertTrue(any(n.startswith("PARTIAL") for n in stats.notes))
        self.assertKept(self.gone_obj_tree, self.gone_pdb)

    def test_deleter_that_raises_is_contained(self) -> None:
        def boom(path):
            raise OSError(32, "The process cannot access the file")

        stats = self.slim(rmtree=boom)          # must NOT propagate
        self.assertEqual(stats.reclaimed_bytes, 0)
        self.assertTrue(any("delete raised" in n for n in stats.notes), stats.notes)


class TestSlimLogging(_WorkdirFixture):
    """``log`` is optional and one-line, matching the rest of fs_cleanup."""

    def test_log_receives_a_summary_line(self) -> None:
        lines: list[str] = []
        stats = self.slim(log=lines.append)
        self.assertTrue(any("slim: reclaimed" in ln for ln in lines), lines)
        self.assertTrue(any(str(stats.reclaimed_mb) in ln for ln in lines), lines)

    def test_log_names_the_refusal(self) -> None:
        lines: list[str] = []
        fs_cleanup.slim_workdir(self.wd, allow_root=self.root / "elsewhere",
                                log=lines.append)
        self.assertTrue(any("REFUSED" in ln for ln in lines), lines)


if __name__ == "__main__":
    unittest.main()
