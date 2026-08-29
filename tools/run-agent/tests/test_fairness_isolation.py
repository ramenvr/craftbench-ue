"""Unit tests for task-scoped fairness isolation (fairness.stage_task_isolation_hide).

Fully OFFLINE — operates on a throwaway temp tree, no editor/network. Verifies
that for a given run the agent-writable runtime module is reduced to the active
task's scaffold + untagged shared infra, with every OTHER task's scaffold moved
aside and restored byte-for-byte. This is the fix for the gp-spawn-sequence FAIL
where the agent edited TaskActor (gp-timer-delayed-destroy's decoy scaffold)
instead of the placed SpawnHostActor.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fairness  # noqa: E402
from aura_rig import driver  # noqa: E402


def _h(task: str | None, cls: str) -> str:
    """A scaffold header body, optionally tagged `for task <id>`."""
    if task is None:
        return f"// {cls} — shared substrate infra. No task tag.\n"
    return (
        f"// {cls} — pre-existing actor pair for task {task}.\n"
        f"#pragma once\nclass {cls} {{}};\n"
    )


def _cpp(task: str | None, cls: str) -> str:
    if task is None:
        return f"// {cls} implementation — shared substrate infra.\n"
    return f"// {cls} implementation for task {task}. The agent fills this.\n"


class _Tree:
    """Builds the temp project + run_dir layout used by every test."""

    ACTIVE = "gp-spawn-sequence"

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-fair-iso-"))
        self.project = self.root / "project"
        self.run_dir = self.root / "run"
        self.module = self.project / "Source" / "CraftBenchTemplate"
        self.tests = self.project / "Source" / "CraftBenchTests"
        self.module.mkdir(parents=True)
        self.tests.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

        # Active task scaffold (kept).
        self._pair("SpawnHostActor", self.ACTIVE)
        # Foreign task scaffolds (isolated).
        self._pair("TaskActor", "gp-timer-delayed-destroy")
        self._pair("SanityActor", "t0-sanity-log-on-beginplay")
        # A foreign single-file reference-solution header (isolated; no .cpp).
        (self.module / "AttachCoordinator.h").write_text(
            "// Reference solution for task gp-modular-attach-type-gated.\n",
            encoding="utf-8")
        # Untagged shared infra (kept).
        self._pair("CraftBenchTemplate", None)         # module impl
        self._pair("SharedBase", None)                 # a shared base class
        (self.module / "CraftBenchTemplate.Build.cs").write_text(
            "// build rules, not a scaffold\n", encoding="utf-8")

        # Verifier-only answer key (handled by the existing stage_fairness_hide).
        (self.tests / "SpawnSequenceFunctionalTest.h").write_text(
            "// secret assertions\n", encoding="utf-8")
        (self.tests / "SpawnSequenceFunctionalTest.cpp").write_text(
            "// secret assertions\n", encoding="utf-8")
        (self.project / "AGENT_WRITABLE.json").write_text("{}", encoding="utf-8")

    def _pair(self, cls: str, task: str | None):
        (self.module / f"{cls}.h").write_text(_h(task, cls), encoding="utf-8")
        (self.module / f"{cls}.cpp").write_text(_cpp(task, cls), encoding="utf-8")

    def state(self) -> fairness.FairnessState:
        (self.run_dir / "fairness_backup").mkdir(parents=True, exist_ok=True)
        return fairness.FairnessState(backup_root=self.run_dir / "fairness_backup")

    def exists(self, rel: str) -> bool:
        return (self.module / rel).exists()


class TestDeclaredTasks(unittest.TestCase):
    def setUp(self):
        self.t = _Tree()

    def test_tags_active_and_foreign(self):
        self.assertEqual(
            fairness._declared_tasks(self.t.module / "SpawnHostActor.h"),
            {"gp-spawn-sequence"})
        self.assertEqual(
            fairness._declared_tasks(self.t.module / "TaskActor.cpp"),
            {"gp-timer-delayed-destroy"})

    def test_reference_solution_phrasing_is_tagged(self):
        self.assertEqual(
            fairness._declared_tasks(self.t.module / "AttachCoordinator.h"),
            {"gp-modular-attach-type-gated"})

    def test_untagged_infra_has_no_task(self):
        self.assertEqual(
            fairness._declared_tasks(self.t.module / "CraftBenchTemplate.cpp"),
            set())
        self.assertEqual(
            fairness._declared_tasks(self.t.module / "SharedBase.h"), set())


class TestIsolationHide(unittest.TestCase):
    def setUp(self):
        self.t = _Tree()
        self.state = self.t.state()
        fairness.stage_task_isolation_hide(self.t.project, self.t.ACTIVE, self.state)

    def test_foreign_pairs_moved_aside(self):
        for rel in ("TaskActor.h", "TaskActor.cpp",
                    "SanityActor.h", "SanityActor.cpp", "AttachCoordinator.h"):
            self.assertFalse(self.t.exists(rel), f"{rel} should be hidden")
            self.assertIn(rel, self.state.isolated_rels)

    def test_active_scaffold_kept(self):
        self.assertTrue(self.t.exists("SpawnHostActor.h"))
        self.assertTrue(self.t.exists("SpawnHostActor.cpp"))
        self.assertNotIn("SpawnHostActor.h", self.state.isolated_rels)

    def test_untagged_infra_kept(self):
        for rel in ("CraftBenchTemplate.cpp", "CraftBenchTemplate.h",
                    "SharedBase.h", "SharedBase.cpp", "CraftBenchTemplate.Build.cs"):
            self.assertTrue(self.t.exists(rel), f"{rel} should be kept")

    def test_backup_holds_hidden_bytes(self):
        iso = self.state.backup_root / "TemplateIsolated"
        self.assertTrue((iso / "TaskActor.cpp").exists())
        self.assertIn("gp-timer-delayed-destroy",
                      (iso / "TaskActor.cpp").read_text(encoding="utf-8"))


class TestRestore(unittest.TestCase):
    def test_round_trip_byte_for_byte(self):
        t = _Tree()
        before = {p.name: p.read_bytes()
                  for p in sorted(t.module.glob("*")) if p.is_file()}
        state = t.state()
        # Full hide: answer key stub + task isolation share one state.
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        # Something was actually hidden.
        self.assertTrue(state.isolated_rels)
        self.assertTrue(state.stubbed_rels)
        self.assertFalse(t.exists("TaskActor.cpp"))
        # Restore everything.
        fairness.stage_fairness_restore(state, t.project)
        after = {p.name: p.read_bytes()
                 for p in sorted(t.module.glob("*")) if p.is_file()}
        self.assertEqual(before, after)
        # Manifest + answer-key fixtures also back.
        self.assertTrue((t.project / "AGENT_WRITABLE.json").exists())
        self.assertNotIn("fairness stub",
                         (t.tests / "SpawnSequenceFunctionalTest.cpp").read_text(
                             encoding="utf-8"))

    def test_clean_restore_deletes_backup_root(self):
        # A run RESULT must not permanently retain the answer-key backup —
        # after a clean restore the backup dir is gone from run_dir, and the
        # safety-net second restore still no-ops.
        t = _Tree()
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        self.assertTrue((t.run_dir / "fairness_backup").exists())
        fairness.stage_fairness_restore(state, t.project)
        self.assertFalse((t.run_dir / "fairness_backup").exists(),
                         "clean restore must delete run_dir/fairness_backup")
        fairness.stage_fairness_restore(state, t.project)  # no raise
        self.assertTrue(t.exists("TaskActor.cpp"))          # tree still whole


class TestRunGradedOrdering(unittest.TestCase):
    """Guards the backup<->isolation ORDER against the regression where the
    foreign scaffolds got deleted on restore.

    The graded route must: stage_fairness_hide -> backup_tree (FULL writable
    tree)
    -> stage_task_isolation_hide. driver.restore_tree deletes any live file
    absent from the backup, so if isolation runs BEFORE the backup, the backup
    is missing the 22 scaffolds and restore deletes them after fairness puts
    them back (the bug observed on gp-spawn-sequence run 1781418086).
    """

    def _run(self, *, backup_before_isolation: bool):
        t = _Tree()
        backup = t.root / "presnap"
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        if backup_before_isolation:                  # CORRECT order
            driver.backup_tree(t.project, backup)
            fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        else:                                        # BUGGY order (for contrast)
            fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
            driver.backup_tree(t.project, backup)
        # Simulate the drive: agent edits the active scaffold + adds a new file.
        (t.module / "SpawnHostActor.cpp").write_text("// agent edit\n", encoding="utf-8")
        (t.module / "NewHelper.cpp").write_text("// agent new\n", encoding="utf-8")
        # Restore exactly as the failure path does: fairness THEN restore_tree.
        fairness.stage_fairness_restore(state, t.project)
        driver.restore_tree(t.project, backup)
        return t

    def test_correct_order_keeps_foreign_scaffolds(self):
        t = self._run(backup_before_isolation=True)
        # Foreign scaffolds survive (the fix).
        for rel in ("TaskActor.cpp", "TaskActor.h", "SanityActor.h",
                    "SanityActor.cpp", "AttachCoordinator.h"):
            self.assertTrue(t.exists(rel), f"{rel} must survive restore")
        # Active scaffold present and reverted (agent edit undone).
        self.assertTrue(t.exists("SpawnHostActor.cpp"))
        self.assertNotIn("agent edit",
                         (t.module / "SpawnHostActor.cpp").read_text(encoding="utf-8"))
        # Agent's NEW file is cleaned up (restore_tree still does its job).
        self.assertFalse(t.exists("NewHelper.cpp"))

    def test_buggy_order_would_delete_foreign_scaffolds(self):
        # Documents the failure mode the ordering fix prevents.
        t = self._run(backup_before_isolation=False)
        self.assertFalse(t.exists("TaskActor.cpp"),
                         "buggy order deletes foreign scaffolds (regression marker)")


class TestSetQualifiedActiveId(unittest.TestCase):
    """A SET-QUALIFIED active id ('bp-g2/<id>', as `cb eval --task bp-g2/<id>`
    forwards it) must still match the scaffold's BARE `for task <id>` marker, so
    the active task's own scaffold is KEPT — not hidden and then clobbered by the
    restore. Regression for the gp-spawner-population/bp-g2 spurious-FAIL: Aura
    wrote a correct solution but the verifier graded the restored stub because
    isolation mistook the active scaffold for a foreign one."""

    def test_set_qualified_id_keeps_active_scaffold(self):
        t = _Tree()
        st = t.state()
        fairness.stage_task_isolation_hide(t.project, "bp-g2/" + t.ACTIVE, st)
        # The active task's scaffold survives (would be hidden without the fix).
        self.assertTrue(t.exists("SpawnHostActor.h"))
        self.assertTrue(t.exists("SpawnHostActor.cpp"))
        self.assertNotIn("SpawnHostActor.h", st.isolated_rels)
        # Foreign scaffolds are still hidden.
        self.assertFalse(t.exists("TaskActor.cpp"))

    def test_backslash_separator_also_normalized(self):
        t = _Tree()
        st = t.state()
        fairness.stage_task_isolation_hide(t.project, "bp-g2\\" + t.ACTIVE, st)
        self.assertTrue(t.exists("SpawnHostActor.h"))
        self.assertNotIn("SpawnHostActor.h", st.isolated_rels)


class TestEdgeCases(unittest.TestCase):
    def test_missing_module_dir_is_noop(self):
        root = Path(tempfile.mkdtemp(prefix="cb-fair-empty-"))
        (root / "fairness_backup").mkdir()
        st = fairness.FairnessState(backup_root=root / "fairness_backup")
        out = fairness.stage_task_isolation_hide(root, "gp-spawn-sequence", st)
        self.assertEqual(out.isolated_rels, [])

    def test_active_task_with_no_active_id_keeps_all_but_still_hides_foreign(self):
        # Empty active id: nothing is "active", so every tagged scaffold is
        # foreign and hidden; untagged infra still kept.
        t = _Tree()
        st = t.state()
        fairness.stage_task_isolation_hide(t.project, "", st)
        self.assertFalse(t.exists("SpawnHostActor.h"))   # now foreign too
        self.assertTrue(t.exists("CraftBenchTemplate.cpp"))  # untagged kept

    def test_restore_is_idempotent(self):
        t = _Tree()
        st = t.state()
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, st)
        fairness.stage_fairness_restore(st, t.project)
        fairness.stage_fairness_restore(st, t.project)  # second call: no raise
        self.assertTrue(t.exists("TaskActor.cpp"))


# --------------------------------------------------------------------------
# B6 drive-time foreign-task TREE isolation (folder-per-task migration).
# --------------------------------------------------------------------------

def _hash_files(root: Path) -> dict:
    import hashlib
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class _MigratedTree(_Tree):
    """_Tree + the folder-per-task migration layout (per-task source dirs,
    per-task fixture dirs, per-task map/asset folders, plus the un-migrated
    flat .umap and an engine folder that must both be left alone)."""

    FOREIGN = "t0-sanity-log-on-beginplay"

    def __init__(self):
        super().__init__()
        p = self.project
        # Per-task agent-writable source folders.
        self._task_dir(p / "Source/CraftBenchTemplate/Tasks" / self.ACTIVE,
                       "SpawnSequenceHelper", self.ACTIVE)
        self._task_dir(p / "Source/CraftBenchTemplate/Tasks" / self.FOREIGN,
                       "SanityScaffold", self.FOREIGN)
        # ThirdPerson-substrate scaffold root (the roots tuple is the union
        # across substrates; a real tree has one writable module, but the
        # union behavior is what these tests pin).
        self._task_dir(p / "Source/ThirdPerson/Tasks" / self.ACTIVE,
                       "PortalScaffold", self.ACTIVE)
        self._task_dir(p / "Source/ThirdPerson/Tasks" / self.FOREIGN,
                       "SprintScaffold", self.FOREIGN)
        # Per-task verifier-only fixture folders (name-visible even after the
        # body stubbing — the whole dir must move).
        self._task_dir(p / "Source/CraftBenchTests/Tasks" / self.ACTIVE,
                       "SpawnSequenceFixture", self.ACTIVE)
        self._task_dir(p / "Source/CraftBenchTests/Tasks" / self.FOREIGN,
                       "SanityFixture", self.FOREIGN)
        # Per-task maps + the un-migrated flat .umap + an engine folder.
        (p / "Content/Maps" / self.ACTIVE).mkdir(parents=True)
        (p / "Content/Maps" / self.ACTIVE / "L_Active.umap").write_bytes(b"\x00ACT")
        (p / "Content/Maps" / self.FOREIGN).mkdir(parents=True)
        (p / "Content/Maps" / self.FOREIGN / "L_Sanity.umap").write_bytes(b"\x00FRN")
        (p / "Content/Maps" / "L_TimerTask.umap").write_bytes(b"\x00FLAT")
        (p / "Content/Maps" / "Developers").mkdir()
        (p / "Content/Maps" / "Developers" / "scratch.uasset").write_bytes(b"\x00DEV")
        # Per-task asset baselines under Content/Tasks.
        (p / "Content/Tasks" / self.ACTIVE).mkdir(parents=True)
        (p / "Content/Tasks" / self.ACTIVE / "baseline.uasset").write_bytes(b"\x00BAS")
        (p / "Content/Tasks" / self.FOREIGN).mkdir(parents=True)
        (p / "Content/Tasks" / self.FOREIGN / "asset.uasset").write_bytes(b"\x00AST")

    def _task_dir(self, d: Path, cls: str, task: str):
        d.mkdir(parents=True)
        (d / f"{cls}.h").write_text(_h(task, cls), encoding="utf-8")
        (d / f"{cls}.cpp").write_text(_cpp(task, cls), encoding="utf-8")

    def p(self, rel: str) -> Path:
        return self.project / rel


class TestTreeIsolationHide(unittest.TestCase):
    def setUp(self):
        self.t = _MigratedTree()
        self.state = self.t.state()
        fairness.stage_task_tree_isolation_hide(
            self.t.project, self.t.ACTIVE, self.state)

    def test_foreign_dirs_moved_all_roots(self):
        f = self.t.FOREIGN
        for rel in (f"Source/CraftBenchTemplate/Tasks/{f}",
                    f"Source/CraftBenchTests/Tasks/{f}",
                    f"Source/ThirdPerson/Tasks/{f}",
                    f"Content/Maps/{f}",
                    f"Content/Tasks/{f}"):
            self.assertFalse(self.t.p(rel).exists(), f"{rel} should be hidden")
        self.assertEqual(sorted(s for s, _ in self.state.isolated_dirs),
                         sorted([f"Source/CraftBenchTemplate/Tasks/{f}",
                                 f"Source/CraftBenchTests/Tasks/{f}",
                                 f"Source/ThirdPerson/Tasks/{f}",
                                 f"Content/Maps/{f}",
                                 f"Content/Tasks/{f}"]))

    def test_active_dirs_kept_all_roots(self):
        a = self.t.ACTIVE
        for rel in (f"Source/CraftBenchTemplate/Tasks/{a}",
                    f"Source/CraftBenchTests/Tasks/{a}",
                    f"Source/ThirdPerson/Tasks/{a}",
                    f"Content/Maps/{a}/L_Active.umap",
                    f"Content/Tasks/{a}/baseline.uasset"):
            self.assertTrue(self.t.p(rel).exists(), f"{rel} should be kept")
        self.assertFalse(any(a in s for s, _ in self.state.isolated_dirs))

    def test_root_level_flat_umap_kept(self):
        self.assertTrue(self.t.p("Content/Maps/L_TimerTask.umap").exists())

    def test_non_task_id_dirs_kept(self):
        # "Developers" (uppercase) fails the kebab-case task-id regex → kept.
        self.assertTrue(self.t.p("Content/Maps/Developers/scratch.uasset").exists())

    def test_backup_layout_and_bytes(self):
        f = self.t.FOREIGN
        parked = (self.state.backup_root / "TreeIsolated" / "Content__Maps"
                  / f / "L_Sanity.umap")
        self.assertEqual(parked.read_bytes(), b"\x00FRN")
        parked_src = (self.state.backup_root / "TreeIsolated"
                      / "Source__CraftBenchTests__Tasks" / f / "SanityFixture.h")
        self.assertTrue(parked_src.exists())


class TestTreeIsolationRestore(unittest.TestCase):
    def test_full_stack_round_trip_byte_identical_and_backup_removed(self):
        # The COMPLETE hide stack in call-site order: answer-key stub →
        # marker isolation → tree isolation; one restore undoes everything.
        # Byte-identity across the WHOLE project also pins the restore ORDER:
        # the parked CraftBenchTests/Tasks/<id>/ dir holds STUBBED bodies, so
        # dirs must come back BEFORE the per-file stub restore.
        t = _MigratedTree()
        before = _hash_files(t.project)
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, state)
        self.assertTrue(state.isolated_dirs)
        fairness.stage_fairness_restore(state, t.project)
        self.assertEqual(before, _hash_files(t.project))
        # The tree-isolation backup is consumed by the restore.
        for _src_rel, backup_rel in state.isolated_dirs:
            self.assertFalse((state.backup_root / backup_rel).exists(),
                             f"{backup_rel} backup should be removed")

    def test_double_hide_tolerated(self):
        t = _MigratedTree()
        st = t.state()
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, st)
        n = len(st.isolated_dirs)
        # Second hide over an already-hidden tree: moves nothing, records nothing.
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, st)
        self.assertEqual(len(st.isolated_dirs), n)
        fairness.stage_fairness_restore(st, t.project)
        self.assertEqual(
            t.p(f"Content/Maps/{t.FOREIGN}/L_Sanity.umap").read_bytes(),
            b"\x00FRN")

    def test_restore_idempotent(self):
        t = _MigratedTree()
        st = t.state()
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, st)
        fairness.stage_fairness_restore(st, t.project)
        fairness.stage_fairness_restore(st, t.project)  # second call: no raise
        self.assertTrue(t.p(f"Content/Tasks/{t.FOREIGN}/asset.uasset").exists())

    def test_set_qualified_active_id_keeps_active_dirs(self):
        t = _MigratedTree()
        st = t.state()
        fairness.stage_task_tree_isolation_hide(
            t.project, "flagship/" + t.ACTIVE, st)
        self.assertTrue(t.p(f"Source/CraftBenchTemplate/Tasks/{t.ACTIVE}").exists())
        self.assertTrue(t.p(f"Content/Maps/{t.ACTIVE}").exists())
        self.assertFalse(t.p(f"Content/Maps/{t.FOREIGN}").exists())

    def test_missing_roots_are_noop(self):
        # The base _Tree has NONE of the four per-task roots.
        t = _Tree()
        st = t.state()
        out = fairness.stage_task_tree_isolation_hide(
            t.project, "gp-spawn-sequence", st)
        self.assertEqual(out.isolated_dirs, [])


class TestTreeIsolationOrdering(unittest.TestCase):
    """Tree isolation must run AFTER driver.backup_tree, exactly like the
    marker isolation (see TestRunGradedOrdering): restore_tree deletes any
    live file absent from the backup, so per-task dirs hidden BEFORE the
    backup would be deleted right after fairness restores them."""

    def test_correct_order_keeps_per_task_trees_through_restore(self):
        t = _MigratedTree()
        backup = t.root / "presnap"
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        driver.backup_tree(t.project, backup)                    # backup first
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, state)
        # Simulate the drive: agent edits the active per-task scaffold.
        (t.project / "Source/CraftBenchTemplate/Tasks" / t.ACTIVE
         / "SpawnSequenceHelper.cpp").write_text("// agent edit\n",
                                                 encoding="utf-8")
        # End-of-run order: fairness restore THEN restore_tree.
        fairness.stage_fairness_restore(state, t.project)
        driver.restore_tree(t.project, backup)
        f = t.FOREIGN
        for rel in (f"Source/CraftBenchTemplate/Tasks/{f}/SanityScaffold.h",
                    f"Source/CraftBenchTests/Tasks/{f}/SanityFixture.cpp",
                    f"Content/Maps/{f}/L_Sanity.umap",
                    f"Content/Tasks/{f}/asset.uasset"):
            self.assertTrue(t.p(rel).exists(), f"{rel} must survive restore")
        # The agent edit is reverted by restore_tree.
        self.assertNotIn(
            "agent edit",
            (t.project / "Source/CraftBenchTemplate/Tasks" / t.ACTIVE
             / "SpawnSequenceHelper.cpp").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# B7 per-task UE config overlay (live-drive apply + byte-identical revert).
# --------------------------------------------------------------------------

class _OverlayTree(_Tree):
    """_Tree + a live Config/ dir and a folder-form task spec shipping
    ue-config/ fragments (one appending onto an existing ini, one creating a
    new ini)."""

    def __init__(self):
        super().__init__()
        self.config = self.project / "Config"
        self.config.mkdir(parents=True)
        self.engine_ini = self.config / "DefaultEngine.ini"
        self.engine_ini.write_bytes(b"[/Script/Engine.Engine]\nExisting=1\n")
        # Folder-form task spec with ue-config fragments.
        self.task_dir = self.root / "tasks" / "flagship" / self.ACTIVE
        self.spec = self.task_dir / "task.md"
        self.spec.parent.mkdir(parents=True)
        self.spec.write_text("# Spawn\n", encoding="utf-8")
        uc = self.task_dir / "ue-config"
        uc.mkdir()
        (uc / "DefaultEngine.ini").write_text(
            "[/Script/Engine.Engine]\nbSmoothFrameRate=False\n",
            encoding="utf-8")
        (uc / "DefaultGameplayTags.ini").write_text(
            '+GameplayTagList=(Tag="Task.Spawn")\n', encoding="utf-8")


class TestConfigOverlayApply(unittest.TestCase):
    def setUp(self):
        self.t = _OverlayTree()
        self.state = self.t.state()
        fairness.stage_config_overlay_apply(
            self.t.project, self.t.spec, self.t.ACTIVE, self.state)

    def test_fragments_applied_to_live_config(self):
        text = self.t.engine_ini.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("[/Script/Engine.Engine]\nExisting=1\n"))
        self.assertIn(f"; CraftBench per-task overlay: {self.t.ACTIVE}", text)
        self.assertIn("bSmoothFrameRate=False", text)
        created = self.t.config / "DefaultGameplayTags.ini"
        self.assertIn('+GameplayTagList=(Tag="Task.Spawn")',
                      created.read_text(encoding="utf-8"))

    def test_state_records_and_parks_original_bytes(self):
        by_name = {n: (c, b) for n, c, b in self.state.applied_config}
        self.assertEqual(set(by_name), {"DefaultEngine.ini",
                                        "DefaultGameplayTags.ini"})
        created, backup_rel = by_name["DefaultEngine.ini"]
        self.assertFalse(created)
        self.assertEqual(
            (self.state.backup_root / backup_rel).read_bytes(),
            b"[/Script/Engine.Engine]\nExisting=1\n",
            "pre-apply bytes must be parked under backup_root/ConfigOverlay/")
        created2, backup_rel2 = by_name["DefaultGameplayTags.ini"]
        self.assertTrue(created2)
        self.assertEqual(backup_rel2, "", "created files park nothing")

    def test_set_qualified_active_id_uses_bare_marker(self):
        t = _OverlayTree()
        st = t.state()
        fairness.stage_config_overlay_apply(
            t.project, t.spec, "flagship/" + t.ACTIVE, st)
        self.assertIn(f"; CraftBench per-task overlay: {t.ACTIVE}\n",
                      t.engine_ini.read_text(encoding="utf-8"))

    def test_no_ue_config_dir_is_noop(self):
        t = _Tree()  # plain tree, no Config/, no ue-config/
        spec = t.root / "tasks" / "flagship" / t.ACTIVE / "task.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Spawn\n", encoding="utf-8")
        st = t.state()
        fairness.stage_config_overlay_apply(t.project, spec, t.ACTIVE, st)
        self.assertEqual(st.applied_config, [])
        self.assertFalse((t.project / "Config").exists())

    def test_flat_spec_is_noop(self):
        t = _OverlayTree()
        flat = t.root / "tasks" / f"{t.ACTIVE}.md"
        flat.write_text("# Spawn\n", encoding="utf-8")
        st = t.state()
        before = t.engine_ini.read_bytes()
        fairness.stage_config_overlay_apply(t.project, flat, t.ACTIVE, st)
        self.assertEqual(st.applied_config, [])
        self.assertEqual(t.engine_ini.read_bytes(), before)


class TestConfigOverlayRestore(unittest.TestCase):
    def test_full_stack_round_trip_byte_identical(self):
        # The COMPLETE hide stack in call-site order (answer-key stub → marker
        # isolation → tree isolation → config overlay); ONE restore undoes
        # everything, including the Config/ mutations.
        t = _OverlayTree()
        before = _hash_files(t.project)
        state = fairness.stage_fairness_hide(t.project, t.run_dir)
        fairness.stage_task_isolation_hide(t.project, t.ACTIVE, state)
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, state)
        fairness.stage_config_overlay_apply(t.project, t.spec, t.ACTIVE, state)
        self.assertTrue(state.applied_config)
        self.assertNotEqual(before, _hash_files(t.project))
        fairness.stage_fairness_restore(state, t.project)
        self.assertEqual(before, _hash_files(t.project),
                         "restore must be byte-identical incl. Config/")
        self.assertFalse((t.config / "DefaultGameplayTags.ini").exists(),
                         "an overlay-CREATED ini must be deleted on restore")

    def test_restore_idempotent(self):
        t = _OverlayTree()
        st = t.state()
        fairness.stage_config_overlay_apply(t.project, t.spec, t.ACTIVE, st)
        fairness.stage_fairness_restore(st, t.project)
        fairness.stage_fairness_restore(st, t.project)  # second call: no raise
        self.assertEqual(t.engine_ini.read_bytes(),
                         b"[/Script/Engine.Engine]\nExisting=1\n")
        self.assertFalse((t.config / "DefaultGameplayTags.ini").exists())

    def test_legacy_state_without_applied_config_tolerated(self):
        # A FairnessState pickled/constructed before B7 lacks applied_config;
        # restore must not raise (getattr fallback, same as isolated_dirs).
        t = _OverlayTree()
        st = t.state()
        del st.applied_config
        fairness.stage_fairness_restore(st, t.project)  # no raise


class TestBackendWiring(unittest.TestCase):
    """Pins the B6 isolation call SEQUENCE into the backend source so a
    refactor can't silently drop it again. The original bug was exactly that:
    marker isolation was wired into one backend and not the other, so which
    lane a rep took decided what the agent could see.

    Two sibling cases pinned the same sequence in the aura-product spine; that
    lane was cut for the 2026-08-28 public release, and run.py -- the one
    graded spine all three shipped arms (claude-p / aura-mcp / unreal-mcp) go
    through -- is now the only backend there is to pin."""

    ROOT = Path(__file__).resolve().parents[1]

    def _src(self, rel: str) -> str:
        return (self.ROOT / rel).read_text(encoding="utf-8")

    def test_run_live_project_wires_both_isolation_stages(self):
        src = self._src("run.py")
        i_backup = src.index('backup = run_dir / "live_backup"')
        i_hide = src.index("stage_fairness_hide(project_dir, run_dir)")
        i_marker = src.index(
            "stage_task_isolation_hide(project_dir, task_id, fairness_state)")
        i_tree = src.index(
            "stage_task_tree_isolation_hide(project_dir, task_id, fairness_state)")
        i_overlay = src.index(
            "stage_config_overlay_apply(project_dir, args.task, task_id,")
        i_dispatch = src.index("make_adapter", i_tree)
        self.assertLess(i_backup, i_hide)     # hide AFTER the writable backup
        self.assertLess(i_hide, i_marker)
        self.assertLess(i_marker, i_tree)
        self.assertLess(i_tree, i_overlay)    # B7 overlay after tree isolation
        self.assertLess(i_overlay, i_dispatch)  # ... and BEFORE dispatch
        # Restore is wired (pre-snapshot + the finally safety net).
        self.assertGreaterEqual(
            src.count("stage_fairness_restore(fairness_state, project_dir)"), 2)


import os  # noqa: E402  (used by the lock-tolerance tests below)
from unittest import mock  # noqa: E402


class TestRobustLockTolerance(unittest.TestCase):
    """The Windows share-violation layer (WinError 32 on a .umap held open by a
    live editor — the 2026-07-10 gp-gas-launch tree-isolation crash): transient
    locks are retried through; a persistent lock on the HIDE path raises with
    the live tree untouched and the dir unrecorded (never shutil.move's
    copy+half-rmtree); the RESTORE path degrades to copy so the live tree
    always comes back whole."""

    def _src_dst(self):
        root = Path(tempfile.mkdtemp(prefix="cb-fair-lock-"))
        src, dst = root / "src", root / "dst"
        src.mkdir()
        (src / "f.umap").write_bytes(b"\x00MAP")
        return src, dst

    def test_move_rides_out_transient_lock(self):
        src, dst = self._src_dst()
        real, calls = os.rename, {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(13, "being used by another process")
            real(a, b)

        with mock.patch.object(fairness.os, "rename", side_effect=flaky):
            fairness._robust_move(src, dst, retries=4, base_delay=0.01)
        self.assertFalse(src.exists())
        self.assertEqual((dst / "f.umap").read_bytes(), b"\x00MAP")

    def test_move_persistent_lock_raises_source_intact(self):
        src, dst = self._src_dst()
        locked = PermissionError(13, "being used by another process")
        with mock.patch.object(fairness.os, "rename", side_effect=locked):
            with self.assertRaises(OSError) as cm:
                fairness._robust_move(src, dst, retries=2, base_delay=0.01)
        self.assertIn(str(src), str(cm.exception))
        # os.rename never half-moves: live bytes intact, nothing at dst.
        self.assertEqual((src / "f.umap").read_bytes(), b"\x00MAP")
        self.assertFalse(dst.exists())

    @unittest.skipUnless(os.name == "nt", "Windows share-violation semantics")
    def test_real_windows_handle_blocks_rename_then_releases(self):
        # Pin the OS assumption the whole layer rests on: renaming a dir whose
        # child file has an open handle fails on Windows, and succeeds once the
        # handle closes.
        src, dst = self._src_dst()
        fh = open(src / "f.umap", "rb")
        try:
            with self.assertRaises(OSError):
                fairness._robust_move(src, dst, retries=2, base_delay=0.01)
            self.assertTrue((src / "f.umap").exists())
        finally:
            fh.close()
        fairness._robust_move(src, dst, retries=2, base_delay=0.01)
        self.assertEqual((dst / "f.umap").read_bytes(), b"\x00MAP")

    def test_hide_locked_map_aborts_clean_and_restore_recovers(self):
        # A persistently-locked foreign map folder aborts the hide with the
        # folder intact and UNRECORDED; the dirs that DID move are recorded,
        # so the graded route's finally-restore makes the tree whole again.
        t = _MigratedTree()
        before = _hash_files(t.project)
        state = t.state()
        orig = fairness._robust_move
        target = t.p(f"Content/Maps/{t.FOREIGN}")

        def locked_maps(src, dst, **kw):
            if Path(src) == target:
                raise OSError(f"locked: {src}")
            orig(src, dst, **kw)

        with mock.patch.object(fairness, "_robust_move",
                               side_effect=locked_maps):
            with self.assertRaises(OSError):
                fairness.stage_task_tree_isolation_hide(
                    t.project, t.ACTIVE, state)
        self.assertEqual(
            t.p(f"Content/Maps/{t.FOREIGN}/L_Sanity.umap").read_bytes(),
            b"\x00FRN")
        self.assertNotIn(f"Content/Maps/{t.FOREIGN}",
                         [s for s, _ in state.isolated_dirs])
        fairness.stage_fairness_restore(state, t.project)
        self.assertEqual(before, _hash_files(t.project))

    def test_restore_falls_back_to_copy_when_parked_dir_locked(self):
        # Even if every parked dir refuses to rename back (OneDrive holding
        # run_dir handles), the restore must still rebuild the live tree.
        t = _MigratedTree()
        before = _hash_files(t.project)
        state = t.state()
        fairness.stage_task_tree_isolation_hide(t.project, t.ACTIVE, state)

        def all_locked(src, dst, **kw):
            raise OSError(f"locked: {src}")

        with mock.patch.object(fairness, "_robust_move",
                               side_effect=all_locked):
            fairness.stage_fairness_restore(state, t.project)
        self.assertEqual(before, _hash_files(t.project))


class TestHideIsUnconditionalOnTheLivePath(unittest.TestCase):
    """The answer-key hide must fire for EVERY live-project backend.

    Regression for the 2026-08-19 finding: _run_live_project gated
    stage_fairness_hide on `backend in ("aura-agent", "unreal-mcp")`, on the
    false premise that aura-mcp cannot read files (its deny list covers the
    ACTUATORS — Read/Glob/Grep were never denied). Measured: aura-mcp
    calibration runs Read the current task's fixture and both base classes in
    full while unreal-mcp got the 77-char stub. This test parses run.py and
    asserts the three hide/isolate calls sit under NO `if` inside
    _run_live_project — a source-level pin, so a re-introduced gate fails here
    before it can leak an answer key again.
    """

    def _live_fn(self):
        import ast
        src = (Path(__file__).resolve().parents[1] / "run.py").read_text(
            encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and \
                    node.name == "_run_live_project":
                return node
        self.fail("_run_live_project not found in run.py")

    def test_hide_calls_are_not_gated_on_backend(self):
        import ast
        fn = self._live_fn()
        # Collect every call name that appears anywhere inside an If.
        gated = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.If):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and \
                            isinstance(sub.func, ast.Name):
                        gated.add(sub.func.id)
        for required in ("stage_fairness_hide", "stage_task_isolation_hide",
                         "stage_task_tree_isolation_hide",
                         "stage_repo_answer_hide"):
            self.assertNotIn(
                required, gated,
                f"{required} is called inside an `if` in _run_live_project — "
                f"the answer-key hide must be unconditional for every "
                f"live-project backend")

    def test_hide_calls_are_present_at_all(self):
        """The unconditional test above passes vacuously if the calls were
        deleted outright — assert they still exist."""
        import ast
        fn = self._live_fn()
        names = {sub.func.id for sub in ast.walk(fn)
                 if isinstance(sub, ast.Call) and
                 isinstance(sub.func, ast.Name)}
        for required in ("stage_fairness_hide", "stage_task_isolation_hide",
                         "stage_task_tree_isolation_hide",
                         "stage_repo_answer_hide"):
            self.assertIn(required, names)


class TestRepoAnswerHide(unittest.TestCase):
    """stage_repo_answer_hide: tasks/, tools/verify-single/ and sibling
    substrates' CraftBenchTests vanish for the drive and come back
    byte-identical; crash leftovers self-heal.

    Regression for the 2026-08-19 second/third leaks: agents Read
    tasks/<id>/reference/* verbatim (two "PASSes" delivered the reference's
    own files) and the sibling substrate's un-stubbed fixture copy after the
    active substrate's stubs blocked them.
    """

    def _repo(self):
        root = Path(tempfile.mkdtemp())
        (root / "tasks" / "cpp" / "t-x" / "reference").mkdir(parents=True)
        (root / "tasks" / "cpp" / "t-x" / "reference" / "A.cpp").write_text(
            "answer", encoding="utf-8")
        (root / "tools" / "verify-single" / "introspect").mkdir(parents=True)
        (root / "tools" / "verify-single" / "introspect" / "t_x.py").write_text(
            "l2i key", encoding="utf-8")
        # a worktree-style .git POINTER FILE (the dir form also renames fine;
        # the file form is the one a naive is_dir() check silently skips —
        # measured 2026-08-20: an agent `git show HEAD:`-recovered the full
        # reference through exactly that skip)
        (root / ".git").write_text("gitdir: C:/somewhere/.git/worktrees/x\n",
                                   encoding="utf-8")
        active = root / "UE-projects" / "ThirdPerson"
        (active / "Source" / "CraftBenchTests").mkdir(parents=True)
        sib = root / "UE-projects" / "CraftBenchTemplate"
        (sib / "Source" / "CraftBenchTests").mkdir(parents=True)
        (sib / "Source" / "CraftBenchTests" / "Fix.cpp").write_text(
            "sibling fixture", encoding="utf-8")
        return root, active, sib

    def _state(self, root):
        bk = root / "rundir" / "fairness_backup"
        bk.mkdir(parents=True)
        return fairness.FairnessState(backup_root=bk)

    def test_hide_then_restore_roundtrip(self):
        root, active, sib = self._repo()
        state = self._state(root)
        fairness.stage_repo_answer_hide(root, active, state)
        self.assertFalse((root / "tasks").exists())
        self.assertFalse((root / "tools" / "verify-single").exists())
        self.assertFalse((root / ".git").exists())
        self.assertFalse((sib / "Source" / "CraftBenchTests").exists())
        # active substrate untouched (its stubs are a different stage)
        self.assertTrue((active / "Source" / "CraftBenchTests").exists())
        self.assertEqual(len(state.repo_hidden), 4)
        fairness.stage_fairness_restore(state, active)
        self.assertEqual(
            (root / "tasks" / "cpp" / "t-x" / "reference" / "A.cpp")
            .read_text(encoding="utf-8"), "answer")
        self.assertTrue((root / ".git").is_file())
        self.assertEqual(
            (sib / "Source" / "CraftBenchTests" / "Fix.cpp")
            .read_text(encoding="utf-8"), "sibling fixture")

    def test_crash_leftover_self_heals_on_next_hide(self):
        root, active, sib = self._repo()
        state1 = self._state(root)
        fairness.stage_repo_answer_hide(root, active, state1)
        # simulate a hard kill: state1 discarded, dirs left hidden
        state2 = fairness.FairnessState(
            backup_root=root / "rundir2" / "fairness_backup")
        state2.backup_root.mkdir(parents=True)
        fairness.stage_repo_answer_hide(root, active, state2)
        self.assertEqual(len(state2.repo_hidden), 4)
        fairness.stage_fairness_restore(state2, active)
        self.assertTrue(
            (root / "tasks" / "cpp" / "t-x" / "reference" / "A.cpp").exists())

    def test_restore_prefers_a_live_source_over_the_park(self):
        root, active, sib = self._repo()
        state = self._state(root)
        fairness.stage_repo_answer_hide(root, active, state)
        # git checkout resurrects tasks/ mid-run
        (root / "tasks" / "cpp").mkdir(parents=True)
        (root / "tasks" / "cpp" / "fresh.md").write_text("live", encoding="utf-8")
        fairness.stage_fairness_restore(state, active)
        self.assertEqual((root / "tasks" / "cpp" / "fresh.md")
                         .read_text(encoding="utf-8"), "live")
        self.assertFalse(Path(state.repo_hidden[0][1]).exists())

    def test_missing_targets_are_a_noop(self):
        root = Path(tempfile.mkdtemp())
        active = root / "UE-projects" / "OnlySub"
        active.mkdir(parents=True)
        state = fairness.FairnessState(backup_root=root / "bk")
        state.backup_root.mkdir(parents=True)
        fairness.stage_repo_answer_hide(root, active, state)
        self.assertEqual(state.repo_hidden, [])

    def test_park_is_unreachable_from_the_repo(self):
        """The park must live outside repo_root.

        As a same-parent sibling it was renamed, not hidden: six drives on
        2026-08-21 walked into .cb-fairness-hidden__tasks/<set>/<id>/reference/,
        one of them its own task's, and the hide reported success throughout.
        """
        root, active, sib = self._repo()
        state = self._state(root)
        fairness.stage_repo_answer_hide(root, active, state)
        self.assertEqual(list(root.rglob("*.cb-fairness-hidden__*")), [])
        self.assertFalse(any(
            p.read_text(encoding="utf-8", errors="ignore") == "answer"
            for p in root.rglob("A.cpp") if p.is_file()))
        for _src, hidden in state.repo_hidden:
            self.assertFalse(
                str(root) == os.path.commonpath([str(root), hidden]),
                f"park {hidden} is inside the repo")

    def test_a_live_owners_park_is_not_reclaimed(self):
        """Reclaim heals a DEAD run's park. It used to reclaim ANY park it
        found, so a second process un-hid a live drive's answer key mid-run —
        measured 2026-08-22, one cell lost to the breach probe."""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        active = root / "UE-projects" / "Active"
        active.mkdir(parents=True)
        (root / "tasks").mkdir()
        state = fairness.FairnessState(backup_root=root / "bk")
        state.backup_root.mkdir(parents=True)
        fairness.stage_repo_answer_hide(root, active, state)
        self.assertFalse((root / "tasks").exists())

        # This process owns the park, so it is live by the same test a
        # concurrent cb would fail.
        fairness._reclaim_parks(fairness._park_root(root))
        self.assertFalse((root / "tasks").exists())

        # Same park, owner unmistakably dead. park.json records ABSOLUTE
        # paths, so re-home them or the reclaim no-ops on a missing dir.
        slot = fairness._park_slot(root)
        dead = slot.parent / "0"
        slot.rename(dead)
        m = json.loads((dead / "park.json").read_text(encoding="utf-8"))
        m["pairs"] = [[src, h.replace(str(slot), str(dead))]
                      for src, h in m.get("pairs", [])]
        (dead / "park.json").write_text(json.dumps(m), encoding="utf-8")
        fairness._reclaim_parks(fairness._park_root(root))
        self.assertTrue((root / "tasks").exists())

    def test_breach_probe_flags_a_resurrected_source(self):
        root = Path(tempfile.mkdtemp())
        active = root / "UE-projects" / "Active"
        active.mkdir(parents=True)
        (root / "tasks").mkdir()
        state = fairness.FairnessState(backup_root=root / "bk")
        state.backup_root.mkdir(parents=True)
        fairness.stage_repo_answer_hide(root, active, state)
        self.assertEqual(fairness.repo_hide_breaches(state), [])
        # A sync client / checkout / operator puts the tree back mid-drive.
        (root / "tasks").mkdir()
        self.assertEqual(fairness.repo_hide_breaches(state),
                         [str(root / "tasks")])


class TestIndexCacheHide(unittest.TestCase):
    """Aura's RAG index keeps its own copy of every file's text, and its query
    tool serves THAT copy — so stubbing the fixture source leaves the answer
    key readable. Four arm-C drives were served verbatim fixture bodies from
    it on 2026-08-22 while the on-disk fixture was a 77-char stub."""

    def _doc(self, d, name, file_path, content):
        (d / name).write_text(
            json.dumps({"file_path": file_path, "content": content}),
            encoding="utf-8")

    def test_only_verifier_docs_are_parked_and_all_come_back(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        project = root / "UE-projects" / "Active"
        docs = project / "Saved" / ".Aura" / "indexed_files_aura"
        docs.mkdir(parents=True)
        self._doc(docs, "qq-1_AoeBurnFunctionalTest_cpp.json",
                  "Source/CraftBenchTests/Tasks/gp-x/AoeBurnFunctionalTest.cpp",
                  "SetCheckpointSchedule({0.5, 1.87});")
        self._doc(docs, "qq-2_CraftBenchCharacter_h.json",
                  "Source/ThirdPerson/CraftBenchCharacter.h", "class A {};")
        spill = project / "Saved" / ".Aura" / "last_query_output.txt"
        spill.write_text("a previous cell's query output", encoding="utf-8")
        # A sibling substrate's cache is answer material too: unreachable
        # through Aura's query tool, but readable straight off disk.
        sib_docs = (root / "UE-projects" / "Sibling" / "Saved" / ".Aura"
                    / "indexed_files_aura")
        sib_docs.mkdir(parents=True)
        self._doc(sib_docs, "qq-9_PoisonStackFunctionalTest_cpp.json",
                  "Source/CraftBenchTests/Tasks/gp-y/PoisonStackFunctionalTest.cpp",
                  "stack cap violated")

        # UHT's generated glue is a third copy of the same fixtures, carrying
        # their reflected member names.
        uht = (project / "Intermediate" / "Build" / "Win64" / "UnrealEditor"
               / "Inc" / "CraftBenchTests" / "UHT")
        uht.mkdir(parents=True)
        (uht / "AoeBurnFunctionalTest.generated.h").write_text(
            "TargetNear TargetFar TargetControl TargetEdge", encoding="utf-8")

        state = fairness.FairnessState(backup_root=root / "bk")
        state.backup_root.mkdir(parents=True)
        fairness.stage_index_cache_hide(root, project, state)
        fairness.stage_generated_code_hide(root, project, state)

        self.assertEqual(fairness.indexed_answer_doc_count(project), 0)
        self.assertEqual(fairness.generated_answer_copy_count(project), 0)
        self.assertFalse((docs / "qq-1_AoeBurnFunctionalTest_cpp.json").exists())
        self.assertTrue((docs / "qq-2_CraftBenchCharacter_h.json").exists())
        self.assertFalse(spill.exists())
        self.assertFalse(
            (sib_docs / "qq-9_PoisonStackFunctionalTest_cpp.json").exists())
        for _src, park in state.index_hidden:
            self.assertNotIn("SetCheckpointSchedule", "".join(
                p.read_text(encoding="utf-8") for p in Path(park).iterdir()
                if p.name.startswith("qq-2")))

        # The indexer keeps writing into the live dir all drive long; a doc it
        # creates under a name the park also holds must survive the restore.
        self._doc(docs, "qq-3_AoeBurnFunctionalTest_cpp.json",
                  "Source/CraftBenchTests/Tasks/gp-x/AoeBurnFunctionalTest.cpp",
                  "// stubbed for the CraftBench verifier")

        fairness.stage_fairness_restore(state, project)
        self.assertEqual(fairness.generated_answer_copy_count(project), 1)
        self.assertTrue((docs / "qq-1_AoeBurnFunctionalTest_cpp.json").exists())
        self.assertTrue((docs / "qq-3_AoeBurnFunctionalTest_cpp.json").exists())
        self.assertEqual(spill.read_text(encoding="utf-8"),
                         "a previous cell's query output")
        self.assertTrue(
            (sib_docs / "qq-9_PoisonStackFunctionalTest_cpp.json").exists())


if __name__ == "__main__":
    unittest.main()
