"""Crash-recovery layer of fairness.py — state persistence + the gate self-heal.

Fully OFFLINE — temp trees only, no git/editor/network. Covers:

  * fairness_state.json written/refreshed by every hide stage, round-tripped
    by load_fairness_state, and consumed (deleted) with the backup root;
  * layout INFERENCE for legacy backups without the state file;
  * heal_leftover_fairness — restores a crashed run's parked answer key,
    honors the in-flight age floor and the recorded project identity;
  * heal_dirty_from_presnap — reverts gate-listed agent edits from an
    orphaned presnap (including the project-name-appears-twice path shape);
  * heal_crashed_run_leftovers — the combined gate entry point.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fairness  # noqa: E402


def _age(path: Path, seconds: float) -> None:
    """Backdate a path's mtime by ``seconds``."""
    t = time.time() - seconds
    os.utime(path, (t, t))


class _Project:
    """A minimal live-project tree the hide stages recognize."""

    ACTIVE = "gp-alpha"

    def __init__(self, root: Path):
        self.dir = root / "UE-projects" / "CraftBenchTemplate"
        self.module = self.dir / "Source" / "CraftBenchTemplate"
        self.tests = self.dir / "Source" / "CraftBenchTests"
        self.content_tasks = self.dir / "Content" / "Tasks"
        self.module.mkdir(parents=True)
        self.tests.mkdir(parents=True)
        (self.content_tasks / "gp-other").mkdir(parents=True)
        (self.content_tasks / "gp-other" / "W.uasset").write_bytes(b"asset")
        (self.tests / "AlphaFunctionalTest.h").write_text(
            "// secret assertions H\n", encoding="utf-8")
        (self.tests / "AlphaFunctionalTest.cpp").write_text(
            "// secret assertions CPP\n", encoding="utf-8")
        (self.module / "ForeignActor.h").write_text(
            "// ForeignActor — pre-existing actor pair for task gp-other.\n",
            encoding="utf-8")
        (self.module / "AlphaActor.cpp").write_text(
            "// scaffold for the agent\n", encoding="utf-8")
        (self.dir / "AGENT_WRITABLE.json").write_text("{}", encoding="utf-8")

    def hide_all(self, run_dir: Path) -> fairness.FairnessState:
        state = fairness.stage_fairness_hide(self.dir, run_dir)
        fairness.stage_task_isolation_hide(self.dir, self.ACTIVE, state)
        fairness.stage_task_tree_isolation_hide(self.dir, self.ACTIVE, state)
        return state

    def snapshot(self) -> dict:
        """{rel: bytes} for every file under the project (the ground truth)."""
        return {p.relative_to(self.dir).as_posix(): p.read_bytes()
                for p in sorted(self.dir.rglob("*")) if p.is_file()}


class TestStatePersistence(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-fair-rec-"))
        self.proj = _Project(self.root)
        self.run_dir = self.root / "runs" / "aura-product" / "gp-alpha-x"
        self.run_dir.mkdir(parents=True)

    def _state_json(self) -> dict:
        p = self.run_dir / "fairness_backup" / "fairness_state.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_hide_writes_state_file_with_project(self):
        fairness.stage_fairness_hide(self.proj.dir, self.run_dir)
        data = self._state_json()
        self.assertEqual(data["schema"], "craftbench.fairness-state/v1")
        self.assertTrue(data["moved_manifest"])
        self.assertIn("AlphaFunctionalTest.h", data["stubbed_rels"])
        self.assertEqual(Path(data["project_dir"]).name, "CraftBenchTemplate")

    def test_later_stages_refresh_the_state_file(self):
        self.proj.hide_all(self.run_dir)
        data = self._state_json()
        self.assertIn("ForeignActor.h", data["isolated_rels"])
        self.assertIn(["Content/Tasks/gp-other",
                       "TreeIsolated/Content__Tasks/gp-other"],
                      data["isolated_dirs"])

    def test_load_round_trips_tuples(self):
        state = self.proj.hide_all(self.run_dir)
        loaded = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(loaded.stubbed_rels, state.stubbed_rels)
        self.assertEqual(loaded.moved_manifest, state.moved_manifest)
        self.assertEqual(loaded.isolated_rels, state.isolated_rels)
        self.assertEqual(loaded.isolated_dirs, state.isolated_dirs)
        self.assertEqual(loaded.project_dir, state.project_dir)
        # Tuples (not lists) so restore code treating them uniformly works.
        for t in loaded.isolated_dirs:
            self.assertIsInstance(t, tuple)

    def test_clean_restore_consumes_state_file_with_backup(self):
        state = self.proj.hide_all(self.run_dir)
        fairness.stage_fairness_restore(state, self.proj.dir)
        self.assertFalse((self.run_dir / "fairness_backup").exists())

    def test_inference_matches_persisted_state(self):
        state = self.proj.hide_all(self.run_dir)
        (state.backup_root / "fairness_state.json").unlink()  # legacy backup
        inferred = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(sorted(inferred.stubbed_rels), sorted(state.stubbed_rels))
        self.assertEqual(inferred.moved_manifest, state.moved_manifest)
        self.assertEqual(sorted(inferred.isolated_rels), sorted(state.isolated_rels))
        self.assertEqual(sorted(inferred.isolated_dirs), sorted(state.isolated_dirs))
        self.assertEqual(inferred.project_dir, "")  # unknowable from layout

    def test_torn_state_file_falls_back_to_inference(self):
        state = self.proj.hide_all(self.run_dir)
        (state.backup_root / "fairness_state.json").write_text(
            '{"schema": "craftbench.fair', encoding="utf-8")
        loaded = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(sorted(loaded.stubbed_rels), sorted(state.stubbed_rels))


class TestHealLeftoverFairness(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-fair-heal-"))
        self.proj = _Project(self.root)
        self.pristine = self.proj.snapshot()
        self.runs = self.root / "runs"
        self.run_dir = self.runs / "aura-product" / "gp-alpha-20260101-000000"
        self.run_dir.mkdir(parents=True)
        self.logged = []

    def _log(self, s):
        self.logged.append(s)

    def test_heals_a_crashed_hide_and_consumes_the_backup(self):
        self.proj.hide_all(self.run_dir)   # crash: no restore ever runs
        _age(self.run_dir / "fairness_backup", 2 * 3600)
        healed = fairness.heal_leftover_fairness(
            self.proj.dir, self.runs, log=self._log)
        self.assertEqual(len(healed), 1)
        self.assertEqual(self.proj.snapshot(), self.pristine)
        self.assertFalse((self.run_dir / "fairness_backup").exists())

    def test_young_backup_is_in_flight_and_skipped(self):
        self.proj.hide_all(self.run_dir)   # a drive could be live right now
        healed = fairness.heal_leftover_fairness(
            self.proj.dir, self.runs, log=self._log)
        self.assertEqual(healed, [])
        self.assertTrue((self.run_dir / "fairness_backup").exists())
        # And the answer key stays hidden (stub still in place).
        stub = (self.proj.tests / "AlphaFunctionalTest.cpp").read_text(encoding="utf-8")
        self.assertIn("fairness stub", stub)

    def test_backup_for_another_project_is_skipped(self):
        self.proj.hide_all(self.run_dir)
        state_path = self.run_dir / "fairness_backup" / "fairness_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["project_dir"] = str(self.root / "somewhere-else")
        state_path.write_text(json.dumps(data), encoding="utf-8")
        _age(self.run_dir / "fairness_backup", 2 * 3600)
        healed = fairness.heal_leftover_fairness(
            self.proj.dir, self.runs, log=self._log)
        self.assertEqual(healed, [])
        self.assertTrue((self.run_dir / "fairness_backup").exists())

    def test_flat_run_dir_backups_are_found_too(self):
        flat_run = self.runs / "20260101-000000-gp-alpha-aura-mcp"
        flat_run.mkdir(parents=True)
        self.proj.hide_all(flat_run)
        _age(flat_run / "fairness_backup", 2 * 3600)
        healed = fairness.heal_leftover_fairness(
            self.proj.dir, self.runs, log=self._log)
        self.assertEqual(len(healed), 1)
        self.assertEqual(self.proj.snapshot(), self.pristine)


class TestHealDirtyFromPresnap(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-presnap-heal-"))
        self.proj = _Project(self.root)
        self.presnaps = self.root / "cb-presnap"
        snap = self.presnaps / "gp-alpha-20260101-000000"
        # The presnap mirrors the writable tree keyed by project-relative rels.
        f = snap / "Source" / "CraftBenchTemplate" / "AlphaActor.cpp"
        f.parent.mkdir(parents=True)
        f.write_text("// scaffold for the agent\n", encoding="utf-8")
        _age(snap, 2 * 3600)

    def _mk_snap(self, name: str) -> Path:
        snap = self.presnaps / name
        f = snap / "Source" / "CraftBenchTemplate" / "AlphaActor.cpp"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// scaffold for the agent\n", encoding="utf-8")
        _age(snap, 2 * 3600)
        return snap

    def test_reverts_modified_and_deleted_files(self):
        # Simulate a killed run's leftover agent edits.
        live = self.proj.module / "AlphaActor.cpp"
        live.write_text("// AGENT EDIT\n", encoding="utf-8")
        # Porcelain paths are repo-root-relative — note the project name
        # appears TWICE (UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate).
        dirty = [" M UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/AlphaActor.cpp"]
        n = fairness.heal_dirty_from_presnap(
            self.proj.dir, dirty,
            fairness.find_writable_snapshots(self.root / "runs", self.presnaps))
        self.assertEqual(n, 1)
        self.assertEqual(live.read_text(encoding="utf-8"),
                         "// scaffold for the agent\n")

        # A used snapshot is CONSUMED — recreate one for the deleted-file case.
        self._mk_snap("gp-alpha-20260102-000000")
        live.unlink()
        dirty = [" D UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/AlphaActor.cpp"]
        n = fairness.heal_dirty_from_presnap(
            self.proj.dir, dirty,
            fairness.find_writable_snapshots(self.root / "runs", self.presnaps))
        self.assertEqual(n, 1)
        self.assertTrue(live.exists())

    def test_young_snapshot_is_skipped(self):
        snap = self.presnaps / "gp-alpha-20260202-000000"
        f = snap / "Source" / "CraftBenchTemplate" / "AlphaActor.cpp"
        f.parent.mkdir(parents=True)
        f.write_text("// newer pristine\n", encoding="utf-8")  # young: now
        # Remove the old consumable snapshot so only the young one remains.
        import shutil
        shutil.rmtree(self.presnaps / "gp-alpha-20260101-000000")
        live = self.proj.module / "AlphaActor.cpp"
        live.write_text("// AGENT EDIT\n", encoding="utf-8")
        dirty = [" M UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/AlphaActor.cpp"]
        n = fairness.heal_dirty_from_presnap(
            self.proj.dir, dirty,
            fairness.find_writable_snapshots(self.root / "runs", self.presnaps))
        self.assertEqual(n, 0)
        self.assertEqual(live.read_text(encoding="utf-8"), "// AGENT EDIT\n")

    def test_paths_outside_the_project_are_ignored(self):
        dirty = [" M docs/README.md"]
        n = fairness.heal_dirty_from_presnap(
            self.proj.dir, dirty,
            fairness.find_writable_snapshots(self.root / "runs", self.presnaps))
        self.assertEqual(n, 0)


class TestHealCombined(unittest.TestCase):
    def test_gate_entry_point_heals_both_layers(self):
        root = Path(tempfile.mkdtemp(prefix="cb-heal-combined-"))
        proj = _Project(root)
        pristine = proj.snapshot()
        runs = root / "runs"
        run_dir = runs / "aura-product" / "gp-alpha-20260101-000000"
        run_dir.mkdir(parents=True)

        # Crash mid-drive: hide applied + an agent edit, nothing restored.
        proj.hide_all(run_dir)
        presnap_root = root / "cb-presnap"
        snap = presnap_root / "gp-alpha-20260101-000000"
        f = snap / "Source" / "CraftBenchTemplate" / "AlphaActor.cpp"
        f.parent.mkdir(parents=True)
        f.write_text("// scaffold for the agent\n", encoding="utf-8")
        (proj.module / "AlphaActor.cpp").write_text("// AGENT EDIT\n",
                                                    encoding="utf-8")
        _age(run_dir / "fairness_backup", 2 * 3600)
        _age(snap, 2 * 3600)

        dirty = [
            " D UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json",
            " M UE-projects/CraftBenchTemplate/Source/CraftBenchTests/AlphaFunctionalTest.cpp",
            " M UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/AlphaActor.cpp",
        ]
        changed = fairness.heal_crashed_run_leftovers(
            proj.dir, runs, dirty, presnap_root=presnap_root)
        self.assertTrue(changed)
        self.assertEqual(proj.snapshot(), pristine)

    def test_nothing_to_heal_returns_false(self):
        root = Path(tempfile.mkdtemp(prefix="cb-heal-none-"))
        proj = _Project(root)
        runs = root / "runs"
        runs.mkdir()
        changed = fairness.heal_crashed_run_leftovers(
            proj.dir, runs, [" M some/file.cpp"],
            presnap_root=root / "cb-presnap")
        self.assertFalse(changed)

    def test_refuses_while_live_run_lock_is_held(self):
        # A LIVE drive legitimately has the tree hidden; the heal must keep
        # hands off its backups even past the age floor.
        from live_lock import live_run_lock
        root = Path(tempfile.mkdtemp(prefix="cb-heal-locked-"))
        proj = _Project(root)
        runs = root / "runs"
        run_dir = runs / "aura-product" / "gp-alpha-20260101-000000"
        run_dir.mkdir(parents=True)
        proj.hide_all(run_dir)
        _age(run_dir / "fairness_backup", 2 * 3600)
        with live_run_lock(runs / ".live-run.lock"):
            changed = fairness.heal_crashed_run_leftovers(
                proj.dir, runs, [" M x"], presnap_root=root / "cb-presnap")
        self.assertFalse(changed)
        self.assertTrue((run_dir / "fairness_backup").exists())
        stub = (proj.tests / "AlphaFunctionalTest.cpp").read_text(encoding="utf-8")
        self.assertIn("fairness stub", stub)


class TestHealSafetyRails(unittest.TestCase):
    """The heal must never be the only holder of destroyed bytes, and must not
    re-clobber the same files forever from a surviving orphan snapshot."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-heal-rails-"))
        self._old_cbtmp = os.environ.get("CB_TMP")
        os.environ["CB_TMP"] = str(self.root / "tmp")
        self.proj = _Project(self.root)
        self.runs = self.root / "runs"
        self.runs.mkdir()

    def tearDown(self):
        if self._old_cbtmp is None:
            os.environ.pop("CB_TMP", None)
        else:
            os.environ["CB_TMP"] = self._old_cbtmp

    def _rescue_files(self) -> dict:
        rescue_root = self.root / "tmp" / "cb-heal-rescue"
        if not rescue_root.is_dir():
            return {}
        return {p.relative_to(rescue_root).as_posix().split("/", 1)[1]: p.read_bytes()
                for p in rescue_root.rglob("*") if p.is_file()}

    def test_presnap_heal_parks_pre_heal_bytes_and_consumes_snapshot(self):
        presnap_root = self.root / "cb-presnap"
        snap = presnap_root / "gp-alpha-20260101-000000"
        f = snap / "Source" / "CraftBenchTemplate" / "AlphaActor.cpp"
        f.parent.mkdir(parents=True)
        f.write_text("// scaffold for the agent\n", encoding="utf-8")
        _age(snap, 2 * 3600)

        live = self.proj.module / "AlphaActor.cpp"
        live.write_bytes(b"// MAINTAINER WIP - precious\n")
        dirty = [" M UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/AlphaActor.cpp"]
        changed = fairness.heal_crashed_run_leftovers(
            self.proj.dir, self.runs, dirty, presnap_root=presnap_root)
        self.assertTrue(changed)
        # Overwritten — but the pre-heal bytes are parked in the rescue dir.
        self.assertEqual(live.read_text(encoding="utf-8"),
                         "// scaffold for the agent\n")
        rescued = self._rescue_files()
        self.assertEqual(
            rescued.get("Source/CraftBenchTemplate/AlphaActor.cpp"),
            b"// MAINTAINER WIP - precious\n")
        # The used snapshot is CONSUMED — no repeat clobber on the next gate.
        self.assertFalse(snap.exists())

    def test_fairness_heal_parks_overwritten_live_files(self):
        run_dir = self.runs / "aura-product" / "gp-alpha-20260101-000000"
        run_dir.mkdir(parents=True)
        self.proj.hide_all(run_dir)
        _age(run_dir / "fairness_backup", 2 * 3600)
        # Post-crash, someone edited a stubbed fixture (WIP over the stub).
        wip = self.proj.tests / "AlphaFunctionalTest.cpp"
        wip.write_bytes(b"// WIP fixture rewrite\n")
        changed = fairness.heal_crashed_run_leftovers(
            self.proj.dir, self.runs, [], presnap_root=self.root / "cb-presnap")
        self.assertTrue(changed)
        self.assertEqual(wip.read_text(encoding="utf-8"),
                         "// secret assertions CPP\n")  # healed to original
        rescued = self._rescue_files()
        self.assertEqual(
            rescued.get("Source/CraftBenchTests/AlphaFunctionalTest.cpp"),
            b"// WIP fixture rewrite\n")


class TestStateUnionOnStaleFile(unittest.TestCase):
    def test_stale_state_file_unions_with_layout(self):
        # A kill between a tree-isolation move and its persist leaves the
        # state file lagging the parked bytes; the union must restore BOTH.
        root = Path(tempfile.mkdtemp(prefix="cb-state-union-"))
        proj = _Project(root)
        run_dir = root / "runs" / "aura-product" / "gp-alpha-x"
        run_dir.mkdir(parents=True)
        state = proj.hide_all(run_dir)
        state_path = state.backup_root / "fairness_state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["isolated_dirs"] = []            # simulate the stale (pre-move) file
        data["stubbed_rels"] = data["stubbed_rels"][:1]
        state_path.write_text(json.dumps(data), encoding="utf-8")

        loaded = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(sorted(loaded.stubbed_rels), sorted(state.stubbed_rels))
        self.assertEqual(sorted(loaded.isolated_dirs), sorted(state.isolated_dirs))
        # And a restore driven by the union brings the whole tree back.
        fairness.stage_fairness_restore(loaded, proj.dir)
        self.assertTrue(
            (proj.content_tasks / "gp-other" / "W.uasset").exists())


if __name__ == "__main__":
    unittest.main()
