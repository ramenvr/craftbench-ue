"""Unit tests for task_layout.py — the shared per-task classification +
additive-staging module (Phase C0).

Covers: structural tests-module classification + manifest-v2 helpers
(expected_fileset / split_manifest_v2), structural per-task-dir staging,
the tests-module base-allowlist strip, and the wrap-tolerant marker scan.
The flat-scaffold stager keeps its original coverage in test_staging.py.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_layout  # noqa: E402


class TestClassification(unittest.TestCase):
    def test_classify_tests_rel(self):
        self.assertIsNone(task_layout.classify_tests_rel("CraftBenchFunctionalTest.cpp"))
        self.assertIsNone(task_layout.classify_tests_rel("GasLaunchFunctionalTest.cpp"))
        self.assertEqual(
            task_layout.classify_tests_rel(
                "Tasks/t0-sanity-log-on-beginplay/SanityFunctionalTest.cpp"),
            "t0-sanity-log-on-beginplay")
        # A FILE directly under Tasks/ is not a per-task dir member.
        self.assertIsNone(task_layout.classify_tests_rel("Tasks/README.md"))

    def test_wrapped_marker_declared(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "HarvestableRegrowFunctionalTest.h"
            p.write_text("// L2 verifier fixture for task\n// gp-harvestable-regrow.\n",
                         encoding="utf-8")
            self.assertEqual(task_layout.declared_tasks(p), {"gp-harvestable-regrow"})


class TestManifestV2Helpers(unittest.TestCase):
    ENTRY = {
        "schema": 2,
        "base": {"CraftBenchFunctionalTest.cpp": "aa", "CraftBenchTests.Build.cs": "bb"},
        "tasks": {
            "t0-sanity-log-on-beginplay": {
                "Tasks/t0-sanity-log-on-beginplay/SanityFunctionalTest.cpp": "cc"},
            "gp-gas-launch": {"Tasks/gp-gas-launch/GasLaunchFunctionalTest.cpp": "dd"},
        },
    }

    def test_expected_none_is_full_union(self):
        exp = task_layout.expected_fileset(self.ENTRY, None)
        self.assertEqual(len(exp), 4)

    def test_expected_active_is_base_plus_task(self):
        exp = task_layout.expected_fileset(self.ENTRY, "cpp/t0-sanity-log-on-beginplay")
        self.assertIn("Tasks/t0-sanity-log-on-beginplay/SanityFunctionalTest.cpp", exp)
        self.assertNotIn("Tasks/gp-gas-launch/GasLaunchFunctionalTest.cpp", exp)
        self.assertEqual(len(exp), 3)

    def test_expected_unknown_task_is_base_only(self):
        self.assertEqual(len(task_layout.expected_fileset(self.ENTRY, "nope")), 2)

    def test_split_round_trip(self):
        flat = {}
        for part in (self.ENTRY["base"], *self.ENTRY["tasks"].values()):
            flat.update(part)
        split = task_layout.split_manifest_v2(flat)
        self.assertEqual(split["schema"], 2)
        self.assertEqual(split["base"], self.ENTRY["base"])
        self.assertEqual(split["tasks"], self.ENTRY["tasks"])


class _Tree:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-layout-"))
        for rel, body in (
            ("Source/CraftBenchTemplate/Tasks/t0-x/T0Actor.h", "// for task t0-x."),
            ("Source/CraftBenchTemplate/Tasks/gp-y/YActor.h", "// for task gp-y."),
            ("Source/ThirdPerson/Tasks/t0-x/T0Portal.h", "// for task t0-x."),
            ("Source/ThirdPerson/Tasks/gp-y/YPortal.h", "// for task gp-y."),
            ("Source/CraftBenchTests/Tasks/t0-x/T0Fixture.h", "// for task t0-x."),
            ("Content/Maps/t0-x/L_T0.umap", "bin"),
            ("Content/Maps/L_Flat.umap", "bin"),
            ("Content/Maps/Developers/scratch.uasset", "bin"),
            ("Content/Tasks/gp-y/asset.uasset", "bin"),
            ("Content/__ExternalActors__/Maps/t0-x/L_T0/A/active.uasset", "bin"),
            ("Content/__ExternalActors__/Maps/gp-y/L_Y/F/foreign.uasset", "bin"),
            ("Content/__ExternalObjects__/Maps/t0-x/L_T0/A/active.uasset", "bin"),
            ("Content/__ExternalObjects__/Maps/gp-y/L_Y/F/foreign.uasset", "bin"),
            ("Plugins/GameFeatures/Tasks/t0-x/CBT0/CBT0.uplugin", "{}"),
            ("Plugins/GameFeatures/Tasks/gp-y/CBY/CBY.uplugin", "{}"),
            ("Source/CraftBenchTests/CraftBenchFunctionalTest.cpp", "// base"),
            ("Source/CraftBenchTests/CraftBenchTests.Build.cs", "// module"),
            ("Source/CraftBenchTests/GasLaunchFunctionalTest.cpp", "// flat fixture"),
            ("Source/CraftBenchTests/.AGENT_WRITE_DENY", ""),
        ):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")


class TestStructuralDirStaging(unittest.TestCase):
    def test_foreign_dirs_deleted_active_and_infra_kept(self):
        t = _Tree()
        removed = task_layout.stage_per_task_dirs_active_only(t.root, "t0-x")
        self.assertEqual(removed, [
            "Content/Tasks/gp-y",
            "Content/__ExternalActors__/Maps/gp-y",
            "Content/__ExternalObjects__/Maps/gp-y",
            "Plugins/GameFeatures/Tasks/gp-y",
            "Source/CraftBenchTemplate/Tasks/gp-y",
            "Source/ThirdPerson/Tasks/gp-y",
        ])
        self.assertTrue((t.root / "Source/CraftBenchTemplate/Tasks/t0-x").is_dir())
        self.assertTrue((t.root / "Content/Maps/L_Flat.umap").exists())     # flat file kept
        self.assertTrue((t.root / "Content/Maps/Developers").is_dir())      # engine dir kept
        self.assertTrue((t.root / "Content/__ExternalActors__/Maps/t0-x").is_dir())
        self.assertTrue((t.root / "Content/__ExternalObjects__/Maps/t0-x").is_dir())
        self.assertFalse((t.root / "Content/__ExternalActors__/Maps/gp-y").exists())
        self.assertFalse((t.root / "Content/__ExternalObjects__/Maps/gp-y").exists())
        self.assertTrue((t.root / "Source/CraftBenchTests/Tasks/t0-x").is_dir())
        self.assertTrue((t.root / "Source/ThirdPerson/Tasks/t0-x").is_dir())
        self.assertTrue((t.root / "Plugins/GameFeatures/Tasks/t0-x").is_dir())


class TestStripTestsToBase(unittest.TestCase):
    def test_strip_all_fixtures_keeps_allowlist(self):
        t = _Tree()
        removed = task_layout.strip_tests_to_base(t.root)
        self.assertIn("GasLaunchFunctionalTest.cpp", removed)          # flat fixture out
        self.assertIn("Tasks/t0-x/T0Fixture.h", removed)               # foldered out
        tests = t.root / "Source/CraftBenchTests"
        self.assertTrue((tests / "CraftBenchFunctionalTest.cpp").exists())
        self.assertTrue((tests / "CraftBenchTests.Build.cs").exists())
        self.assertTrue((tests / ".AGENT_WRITE_DENY").exists())
        self.assertFalse((tests / "Tasks" / "t0-x").exists())          # emptied dir swept

    def test_keep_task_retains_its_foldered_fixtures(self):
        t = _Tree()
        task_layout.strip_tests_to_base(t.root, keep_task="t0-x")
        self.assertTrue(
            (t.root / "Source/CraftBenchTests/Tasks/t0-x/T0Fixture.h").exists())


class TestRootMapStaging(unittest.TestCase):
    def _tree_with_root_maps(self):
        t = _Tree()
        maps = t.root / "Content/Maps"
        for rel in ("L_Keep.umap", "L_Keep.umap.NOTE.md",
                    "L_RenderProbe.umap", "L_Stray.uasset", "README.md"):
            (maps / rel).write_text("x", encoding="utf-8")
        return t

    def test_foreign_root_maps_and_note_siblings_deleted(self):
        t = self._tree_with_root_maps()
        removed = task_layout.stage_root_maps_active_only(t.root, {"L_Keep"})
        self.assertEqual(removed, [
            "Content/Maps/L_Flat.umap",
            "Content/Maps/L_Stray.uasset",
        ])
        maps = t.root / "Content/Maps"
        self.assertTrue((maps / "L_Keep.umap").exists())
        self.assertTrue((maps / "L_Keep.umap.NOTE.md").exists())  # kept stem
        self.assertTrue((maps / "L_RenderProbe.umap").exists())   # shared infra
        self.assertTrue((maps / "README.md").exists())            # non-map file
        self.assertTrue((maps / "t0-x/L_T0.umap").exists())       # foldered: other stager
        self.assertTrue((maps / "Developers").is_dir())

    def test_missing_maps_dir_is_noop(self):
        t = _Tree()
        removed = task_layout.stage_root_maps_active_only(
            t.root, set(), maps_rel="Content/NoSuchDir")
        self.assertEqual(removed, [])

    def test_spec_map_names_is_superset_extraction(self):
        # IGNORECASE on purpose: the runner's map derivation is
        # case-insensitive, so extraction must be at least as permissive —
        # a superset can only fail SAFE (keep).
        spec = ("## Verifier fixtures\n\n- L_SpawnTask :: ASpawnFunctionalTest\n\n"
                "Prose also mentions L_Other_2 and lowercase l_variant.\n")
        self.assertEqual(task_layout.spec_map_names(spec),
                         {"L_SpawnTask", "L_Other_2", "l_variant"})
        self.assertEqual(task_layout.spec_map_names(""), set())

    def test_keep_compare_is_case_insensitive(self):
        t = self._tree_with_root_maps()
        removed = task_layout.stage_root_maps_active_only(
            t.root, {"l_keep", "L_FLAT"})
        self.assertEqual(removed, ["Content/Maps/L_Stray.uasset"])
        self.assertTrue((t.root / "Content/Maps/L_Keep.umap").exists())
        self.assertTrue((t.root / "Content/Maps/L_Flat.umap").exists())


if __name__ == "__main__":
    unittest.main()
