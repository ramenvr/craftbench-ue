"""Unit tests for aura_rig.runs_clean — the `cb clean --runs` ledger-first pruner.

UE-free and disk-cheap: tiny synthetic runs/ trees in a tempdir; rmtree is the
real shutil for execute() (the trees are bytes, not builds).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from aura_rig import runs_clean as rcl


def _mk_run(root: Path, name: str, marker: str, payload: dict) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / marker).write_text(json.dumps(payload), encoding="utf-8")
    return d


class _TempRunsRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.runs = Path(self._tmp) / "runs"
        self.runs.mkdir()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestDiscovery(_TempRunsRoot):
    def test_flat_container_and_aggregate_shapes(self):
        flat = _mk_run(self.runs, "20260101-000000-t0-claude-p", "result.json",
                       {"overall": "PASS"})
        nested = _mk_run(self.runs, "aura-product/t0-12345", "summary.json",
                         {"verdict": "PASS"})
        matrix = _mk_run(self.runs, "matrix-20260101-000000", "leaderboard.json",
                         {"by_model": {}})
        # nested cells under an already-matched matrix dir must NOT double-count
        _mk_run(matrix, "cells/m__t/20260101-000001-t-m", "result.json", {})
        # loose files + marker-less container children are never units
        (self.runs / rcl.LEDGER_NAME).write_text("", encoding="utf-8")
        (self.runs / "aura-product" / "notes.txt").write_text("x", encoding="utf-8")

        units = rcl.discover_run_units(self.runs)
        paths = sorted(str(u.path.relative_to(self.runs)).replace("\\", "/")
                       for u in units)
        self.assertEqual(paths, ["20260101-000000-t0-claude-p",
                                 "aura-product/t0-12345",
                                 "matrix-20260101-000000"])
        by_path = {str(u.path): u for u in units}
        self.assertIsNone(by_path[str(flat)].container)
        self.assertEqual(by_path[str(nested)].container, "aura-product")

    def test_missing_root_is_empty(self):
        self.assertEqual(rcl.discover_run_units(self.runs / "nope"), [])

    def test_aborted_runs_match_via_prompt_report_or_emptiness(self):
        aborted = self.runs / "20260101-000002-t0-claude-p"
        aborted.mkdir()
        (aborted / "prompt.md").write_text("p", encoding="utf-8")
        gen = _mk_run(self.runs, "aura-product-gen/batch-gen-1", "report.json",
                      {"rows": []})
        (gen / "report.md").write_text("r", encoding="utf-8")
        empty = self.runs / "20260101-000003-t0-claude-p"
        empty.mkdir()
        units = rcl.discover_run_units(self.runs)
        paths = sorted(str(u.path.relative_to(self.runs)).replace("\\", "/")
                       for u in units)
        self.assertEqual(paths, ["20260101-000002-t0-claude-p",
                                 "20260101-000003-t0-claude-p",
                                 "aura-product-gen/batch-gen-1"])


class TestPlan(unittest.TestCase):
    def _units(self, *mtimes):
        # discover_run_units yields newest-first; mirror that.
        return [rcl.RunUnit(Path(f"/r/u{i}"), None, m)
                for i, m in enumerate(sorted(mtimes, reverse=True))]

    def test_keep_last_protects_newest(self):
        units = self._units(100.0, 200.0, 300.0)
        victims, kept = rcl.plan(units, keep_last=2, min_age_s=0, now=1000.0)
        self.assertEqual([u.mtime for u in kept], [300.0, 200.0])
        self.assertEqual([u.mtime for u in victims], [100.0])

    def test_older_than_protects_young(self):
        day = 86400.0
        now = 10 * day
        units = self._units(now - 1 * day, now - 5 * day)
        victims, kept = rcl.plan(units, older_than_days=3, min_age_s=0, now=now)
        self.assertEqual([u.mtime for u in victims], [now - 5 * day])
        self.assertEqual([u.mtime for u in kept], [now - 1 * day])

    def test_no_gates_prunes_everything_old(self):
        units = self._units(1.0, 2.0)
        victims, kept = rcl.plan(units, now=100000.0)   # far past the floor
        self.assertEqual(len(victims), 2)
        self.assertEqual(kept, [])

    def test_in_flight_floor_protects_recent_by_default(self):
        now = 100000.0
        units = self._units(now - 60.0, now - 2 * rcl.MIN_AGE_S)
        victims, kept = rcl.plan(units, now=now)        # defaults: floor active
        self.assertEqual([u.mtime for u in kept], [now - 60.0])
        self.assertEqual([u.mtime for u in victims], [now - 2 * rcl.MIN_AGE_S])

    def test_unit_holding_fairness_backup_is_never_pruned(self):
        # A crashed drive's fairness_backup is the DIRTY-SUBSTRATE gate's
        # self-heal source — pruning it destroys the automatic recovery path.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            crashed = Path(td) / "t0-crashed"
            (crashed / "fairness_backup").mkdir(parents=True)
            normal = Path(td) / "t0-normal"
            normal.mkdir()
            units = [rcl.RunUnit(crashed, None, 1.0),
                     rcl.RunUnit(normal, None, 2.0)]
            victims, kept = rcl.plan(units, min_age_s=0, now=100000.0)
            self.assertEqual([u.path for u in kept], [crashed])
            self.assertEqual([u.path for u in victims], [normal])


class TestLedgerRow(_TempRunsRoot):
    def test_result_json_shape(self):
        d = _mk_run(self.runs, "r1", "result.json", {
            "overall": "PASS", "task": "tasks/flagship/t0/task.md",
            "model": "claude-p:sonnet",
            "agent": {"cost_usd": 0.5, "duration_s": 60.2},
            "timings": {"agent_s": 60.2, "verify_s": 240.0},
            "verifier": {"duration_seconds": 239.9},
        })
        row = rcl.ledger_row(rcl.RunUnit(d, None, 123.0), deleted_at="T")
        self.assertEqual(row["verdict"], "PASS")
        self.assertEqual(row["cost_usd"], 0.5)
        self.assertEqual(row["agent_s"], 60.2)
        self.assertEqual(row["verify_s"], 240.0)   # timings wins over verifier
        self.assertEqual(row["model"], "claude-p:sonnet")
        self.assertEqual(row["deleted_at"], "T")

    def test_summary_json_shape_matches_the_summary_envelope(self):
        # The REAL per-run summary.json keys, as archived runs carry them:
        # model / model_intended (never "main_model_key"),
        # timings.drive_s/grade_s (never top-level wall_s).
        d = _mk_run(self.runs, "r2", "summary.json", {
            "task_id": "t0", "verdict": "FAIL", "est_cost_usd": 1.25,
            "model": "sonnet-4.6",
            "timings": {"drive_s": 500.0, "grade_s": 240.0},
        })
        row = rcl.ledger_row(rcl.RunUnit(d, "aura-product", 1.0))
        self.assertEqual(row["verdict"], "FAIL")
        self.assertEqual(row["cost_usd"], 1.25)
        self.assertEqual(row["model"], "sonnet-4.6")
        self.assertEqual(row["agent_s"], 500.0)    # timings.drive_s
        self.assertEqual(row["verify_s"], 240.0)   # timings.grade_s
        self.assertEqual(row["container"], "aura-product")

    def test_product_summary_model_intended_fallback(self):
        d = _mk_run(self.runs, "r2b", "summary.json", {
            "task_id": "t0", "verdict": "PASS", "model_intended": "opus-4.8",
        })
        row = rcl.ledger_row(rcl.RunUnit(d, "aura-product", 1.0))
        self.assertEqual(row["model"], "opus-4.8")

    def test_batch_aggregate_shape_records_counts_not_wall_s(self):
        # A batch-eval summary carries the WHOLE batch's wall_s — it must never
        # be recorded as one agent's time.
        d = _mk_run(self.runs, "r3", "summary.json",
                    {"n_pass": 8, "n_fail": 1, "wall_s": 3200.0, "results": []})
        row = rcl.ledger_row(rcl.RunUnit(d, "aura-product-eval", 1.0))
        self.assertNotIn("verdict", row)
        self.assertNotIn("agent_s", row)
        self.assertEqual(row["aggregate"], "summary.json")
        self.assertEqual(row["n_pass"], 8)

    def test_bench_aggregate_embeds_rollup(self):
        # bench-/matrix- units are pruned WHOLE; the by_pair/by_model rollup is
        # the only surviving cost/verdict record and must land in the ledger.
        pair = {"pass": 3, "graded_n": 3, "cost_usd": {"total": 1.8}}
        d = _mk_run(self.runs, "bench-1", "bench.json",
                    {"by_pair": {"M :: t0": pair}, "by_model": {}, "reps": []})
        row = rcl.ledger_row(rcl.RunUnit(d, None, 1.0))
        self.assertEqual(row["aggregate"], "bench.json")
        self.assertEqual(row["rollup"]["M :: t0"], pair)

    def test_unreadable_dir_still_yields_row(self):
        d = self.runs / "r4"
        d.mkdir()
        row = rcl.ledger_row(rcl.RunUnit(d, None, 9.0))
        self.assertEqual(row["run"], "r4")
        self.assertNotIn("verdict", row)


class TestExecute(_TempRunsRoot):
    def test_check_mode_deletes_nothing(self):
        d = _mk_run(self.runs, "victim", "result.json", {"overall": "PASS"})
        ledger = self.runs / rcl.LEDGER_NAME
        n = rcl.execute([rcl.RunUnit(d, None, 1.0)], ledger,
                        lambda p: True, check=True, log=lambda s: None)
        self.assertEqual(n, 0)
        self.assertTrue(d.exists())
        self.assertFalse(ledger.exists())

    def test_delete_appends_ledger_then_removes_and_drops_empty_container(self):
        d = _mk_run(self.runs, "aura-product/t0-1", "summary.json",
                    {"verdict": "PASS", "task_id": "t0"})
        ledger = self.runs / rcl.LEDGER_NAME
        unit = rcl.RunUnit(d, "aura-product", 1.0)

        def _rm(p):
            shutil.rmtree(p)
            return True

        n = rcl.execute([unit], ledger, _rm, check=False, now_iso="NOW",
                        log=lambda s: None)
        self.assertEqual(n, 1)
        self.assertFalse(d.exists())
        self.assertFalse((self.runs / "aura-product").exists())  # emptied container dropped
        lines = ledger.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row["verdict"], "PASS")
        self.assertEqual(row["deleted_at"], "NOW")
        self.assertEqual(row["status"], "deleted")

    def test_partial_delete_is_ledgered_as_partial(self):
        d = _mk_run(self.runs, "locked", "result.json", {"overall": "FAIL"})
        ledger = self.runs / rcl.LEDGER_NAME
        n = rcl.execute([rcl.RunUnit(d, None, 1.0)], ledger,
                        lambda p: False, check=False, log=lambda s: None)
        self.assertEqual(n, 0)
        row = json.loads(ledger.read_text(encoding="utf-8").strip())
        self.assertEqual(row["status"], "partial")
        self.assertEqual(row["verdict"], "FAIL")  # row was built BEFORE the delete

    def test_nonempty_container_survives(self):
        d = _mk_run(self.runs, "aura-product/t0-1", "summary.json", {"verdict": "PASS"})
        _mk_run(self.runs, "aura-product/t0-2", "summary.json", {"verdict": "FAIL"})

        def _rm(p):
            shutil.rmtree(p)
            return True

        rcl.execute([rcl.RunUnit(d, "aura-product", 1.0)],
                    self.runs / rcl.LEDGER_NAME, _rm, log=lambda s: None)
        self.assertTrue((self.runs / "aura-product" / "t0-2").exists())


def _rm_real(p: Path) -> bool:
    shutil.rmtree(p)
    return True


class TestSlim(_TempRunsRoot):
    """`cb clean --runs --slim` — reclaim in place, delete no unit.

    The contract under test is the one the sweep exists for: the bulk goes and
    the EVIDENCE stays, because an old verdict can only be re-adjudicated
    against a newer fixture while its logs are still on disk.
    """

    def _run_with_lean(self, name: str, *, lean_bytes: int = 4096) -> Path:
        d = _mk_run(self.runs, name, "summary.json", {"verdict": "PASS",
                                                      "model": "opus-5"})
        lean = d / "project-lean" / "Content"
        lean.mkdir(parents=True)
        (lean / "big.uasset").write_bytes(b"x" * lean_bytes)
        (d / "l2_pie.log").write_text("[GLIDE] idx=6 minglide=208.2", encoding="utf-8")
        (d / "deliverable").mkdir()
        (d / "deliverable" / "BP_Glide.uasset").write_bytes(b"y" * 32)
        return d

    def test_drops_project_lean_and_keeps_every_piece_of_evidence(self):
        d = self._run_with_lean("aura-product/t0-1")
        units = [rcl.RunUnit(d, "aura-product", 1.0)]

        slimmed, freed = rcl.slim_execute(
            rcl.slim_plan(units, min_age_s=0.0), self.runs / rcl.LEDGER_NAME,
            _rm_real, log=lambda s: None)

        self.assertEqual(slimmed, 1)
        self.assertGreaterEqual(freed, 4096)
        self.assertFalse((d / "project-lean").exists())
        self.assertTrue(d.is_dir())                              # unit survives
        for keep in ("summary.json", "l2_pie.log", "deliverable"):
            self.assertTrue((d / keep).exists(), keep)

    def test_ledger_and_in_unit_marker_record_the_reclaim(self):
        d = self._run_with_lean("aura-product/t0-1")
        rcl.slim_execute(rcl.slim_plan([rcl.RunUnit(d, "aura-product", 1.0)],
                                       min_age_s=0.0),
                         self.runs / rcl.LEDGER_NAME, _rm_real, log=lambda s: None)

        row = json.loads((self.runs / rcl.LEDGER_NAME).read_text(
            encoding="utf-8").strip())
        self.assertEqual(row["action"], "slim")
        self.assertEqual(row["dropped"], ["project-lean"])
        self.assertEqual(row["verdict"], "PASS")                 # identity preserved
        self.assertNotIn("deleted_at", row)                      # nothing was deleted
        marker = json.loads((d / rcl.SLIM_MARKER).read_text(encoding="utf-8"))
        self.assertEqual(marker["dropped"], ["project-lean"])

    def test_check_mode_reclaims_nothing(self):
        d = self._run_with_lean("aura-product/t0-1")
        slimmed, freed = rcl.slim_execute(
            rcl.slim_plan([rcl.RunUnit(d, "aura-product", 1.0)], min_age_s=0.0),
            self.runs / rcl.LEDGER_NAME, _rm_real, check=True, log=lambda s: None)

        self.assertEqual((slimmed, freed), (0, 0))
        self.assertTrue((d / "project-lean").exists())
        self.assertFalse((self.runs / rcl.LEDGER_NAME).exists())

    def test_in_flight_floor_protects_a_live_run(self):
        d = self._run_with_lean("aura-product/t0-1")
        fresh = rcl.RunUnit(d, "aura-product", __import__("time").time())
        self.assertEqual(rcl.slim_plan([fresh]), [])             # default floor applies

    def test_second_pass_is_a_no_op(self):
        d = self._run_with_lean("aura-product/t0-1")
        units = [rcl.RunUnit(d, "aura-product", 1.0)]
        rcl.slim_execute(rcl.slim_plan(units, min_age_s=0.0),
                         self.runs / rcl.LEDGER_NAME, _rm_real, log=lambda s: None)
        self.assertEqual(rcl.slim_plan(units, min_age_s=0.0), [])

    def test_unit_without_reclaimable_bytes_is_not_a_target(self):
        d = _mk_run(self.runs, "aura-product/t0-2", "summary.json", {"verdict": "FAIL"})
        self.assertEqual(rcl.slim_plan([rcl.RunUnit(d, "aura-product", 1.0)],
                                       min_age_s=0.0), [])

    def test_fairness_backup_does_not_block_slim(self):
        # plan() protects these units from DELETION; slim never touches the
        # directory that rule exists for, so it must not inherit the skip.
        d = self._run_with_lean("aura-product/t0-3")
        (d / "fairness_backup").mkdir()
        targets = rcl.slim_plan([rcl.RunUnit(d, "aura-product", 1.0)], min_age_s=0.0)
        self.assertEqual(len(targets), 1)
        rcl.slim_execute(targets, self.runs / rcl.LEDGER_NAME, _rm_real,
                         log=lambda s: None)
        self.assertTrue((d / "fairness_backup").is_dir())        # untouched
        self.assertFalse((d / "project-lean").exists())

    def test_held_directory_is_reported_not_claimed(self):
        d = self._run_with_lean("aura-product/t0-1")
        slimmed, freed = rcl.slim_execute(
            rcl.slim_plan([rcl.RunUnit(d, "aura-product", 1.0)], min_age_s=0.0),
            self.runs / rcl.LEDGER_NAME, lambda p: False, log=lambda s: None)

        self.assertEqual((slimmed, freed), (0, 0))
        self.assertFalse((self.runs / rcl.LEDGER_NAME).exists())
        self.assertFalse((d / rcl.SLIM_MARKER).exists())

    def test_largest_unit_is_planned_first(self):
        small = self._run_with_lean("aura-product/small", lean_bytes=100)
        big = self._run_with_lean("aura-product/big", lean_bytes=100_000)
        targets = rcl.slim_plan([rcl.RunUnit(small, "aura-product", 1.0),
                                 rcl.RunUnit(big, "aura-product", 1.0)],
                                min_age_s=0.0)
        self.assertEqual([t.unit.path for t in targets], [big, small])


if __name__ == "__main__":
    unittest.main()
