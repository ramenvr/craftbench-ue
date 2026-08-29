"""Unit tests for aura_rig.batch_eval — the ``cb batch-eval`` command (design §5).

Fully offline: the per-submission verify call and the mem-gate are INJECTED, so
NOTHING here shells a real cold UE, reads real memory, or sleeps for real. A FAKE
verify records every leg + returns a canned verdict; a real :class:`MemGate`
driven by a FAKE pressure source (NORMAL) gates the slot so the gate logic IS
exercised but admits instantly.

We assert the four behaviours the brief asks for:
  (1) submissions are enumerated from the outputs folder (one per child dir,
      paired with its task spec; dotfiles/files skipped);
  (2) each scheduled verify passes through the mem-gate slot, never exceeding the
      slot cap (the gate's high-water mark is observed under contention);
  (3) the summary aggregates correctly (graded denominator, pass-rate, the
      excluded non-graded outcomes counted per kind);
  (4) a FAILING / crashing verify is isolated — the rest of the batch still
      completes and is summarized.

Mirrors the sibling tests' sys.path + unittest convention (test_mem_gate.py,
test_run_batch.py). Run from tools/run-agent::

    python3 -m unittest tests.test_batch_eval
"""

import asyncio
import json
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import batch_eval  # noqa: E402
from aura_rig.batch_eval import (  # noqa: E402
    EvalResult,
    Submission,
    discover_reference_submissions,
    discover_submissions,
    make_default_verify,
    run_batch_eval,
    summarize,
)
from aura_rig.mem_gate import MemGate, Pressure  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes — NO UE, NO real memory, NO subprocess.
# ---------------------------------------------------------------------------

def _normal_gate(max_slots=2):
    """A real MemGate whose pressure source is pinned NORMAL → admits instantly,
    but its slot accounting (max_observed) is live so concurrency can be asserted.
    The poll sleep is a no-op (never reached at NORMAL)."""
    return MemGate(read_pressure=lambda: Pressure.NORMAL, max_slots=max_slots,
                   poll_interval=0.001, sleep=lambda _s: None)


class _FakeVerify:
    """Records each (task_id, report_json) it is called with and returns a canned
    verdict per task. Tracks the PEAK number of concurrent in-flight verifies so
    the slot cap can be asserted (verify runs in an executor thread, so a real
    lock + a brief hold makes the contention real)."""

    def __init__(self, verdicts=None, layers=None, raise_for=None, hold_s=0.0):
        self._verdicts = verdicts or {}
        self._layers = layers or {}
        self._raise_for = set(raise_for or [])
        self._hold_s = hold_s
        self.calls = []
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def __call__(self, sub: Submission, report_json: Path):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.calls.append((sub.task_id, str(report_json)))
        try:
            if self._hold_s:
                time.sleep(self._hold_s)
            if sub.task_id in self._raise_for:
                raise RuntimeError(f"boom on {sub.task_id}")
            # Write a tiny report.json so report_path is populated.
            report_json.parent.mkdir(parents=True, exist_ok=True)
            report_json.write_text(json.dumps(
                {"overall": (self._verdicts.get(sub.task_id) or "fail").lower(),
                 "layers": {k: {"status": v} for k, v in
                            self._layers.get(sub.task_id, {}).items()}}),
                encoding="utf-8")
            return (self._verdicts.get(sub.task_id, "FAIL"),
                    self._layers.get(sub.task_id, {}))
        finally:
            with self._lock:
                self.active -= 1


def _mk_outputs(parent: Path, names):
    """Make ``parent/<name>/`` for each name; return parent. A leading '.' name
    makes a dotdir (must be skipped); a name ending '.txt' makes a FILE."""
    parent.mkdir(parents=True, exist_ok=True)
    for n in names:
        if n.endswith(".txt"):
            (parent / n).write_text("not a submission", encoding="utf-8")
        else:
            (parent / n).mkdir(parents=True, exist_ok=True)
    return parent


def _fake_resolve(specs):
    """Build a tasks.resolve_task_path stand-in from a {task_id: spec_path} map.

    Returns None for unknown ids (the UNPAIRED path)."""
    def _resolve(_repo, task_id):
        return specs.get(task_id)
    return _resolve


# ---------------------------------------------------------------------------
# (1) submissions enumerated from the outputs folder.
# ---------------------------------------------------------------------------

class TestDiscoverSubmissions(unittest.TestCase):
    def test_enumerates_child_dirs_skipping_files_and_dotdirs(self):
        with tempfile.TemporaryDirectory() as td:
            out = _mk_outputs(Path(td) / "outputs",
                              ["actor-lifecycle", "timer-delayed-spawn",
                               ".hidden", "stray.txt"])
            specs = {
                "actor-lifecycle": Path("/tasks/actor-lifecycle.md"),
                "timer-delayed-spawn": Path("/tasks/timer-delayed-spawn.md"),
            }
            subs = discover_submissions(out, Path("/repo"),
                                        resolve=_fake_resolve(specs))
            ids = [s.task_id for s in subs]
            self.assertEqual(ids, ["actor-lifecycle", "timer-delayed-spawn"])
            self.assertTrue(all(s.paired for s in subs))
            self.assertEqual(subs[0].submission_dir, out / "actor-lifecycle")

    def test_unresolved_task_id_is_unpaired_not_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            out = _mk_outputs(Path(td) / "outputs", ["known", "mystery-task"])
            specs = {"known": Path("/tasks/known.md")}
            subs = discover_submissions(out, Path("/repo"),
                                        resolve=_fake_resolve(specs))
            by_id = {s.task_id: s for s in subs}
            self.assertEqual(set(by_id), {"known", "mystery-task"})
            self.assertTrue(by_id["known"].paired)
            self.assertFalse(by_id["mystery-task"].paired)

    def test_missing_outputs_dir_yields_empty(self):
        self.assertEqual(
            discover_submissions(Path("/nope/does/not/exist"),
                                 resolve=_fake_resolve({})), [])


# ---------------------------------------------------------------------------
# (1b) reference-solution discovery (the `cb batch-eval --references` mode).
# ---------------------------------------------------------------------------

def _mk_ref_repo(td: Path) -> Path:
    """A miniature repo tree exercising BOTH task layouts + BOTH reference homes:
      * tasks/root-task.md              + tests/reference-solutions/root-task/   (legacy)
      * tasks/bp-g2/gp-poison/task.md   + .../gp-poison/reference/               (folder-local)
      * tasks/concept-1/flat-legacy.md  + tests/reference-solutions/flat-legacy/ (legacy)
      * tasks/concept-1/no-ref.md       with NO reference anywhere -> skipped."""
    repo = td / "repo"
    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "root-task.md").write_text("# root\n", encoding="utf-8")
    (repo / "tests" / "reference-solutions" / "root-task").mkdir(parents=True)
    folder = repo / "tasks" / "bp-g2" / "gp-poison"
    (folder / "reference").mkdir(parents=True)
    (folder / "task.md").write_text("# poison\n", encoding="utf-8")
    (repo / "tasks" / "concept-1").mkdir(parents=True)
    (repo / "tasks" / "concept-1" / "flat-legacy.md").write_text(
        "# flat\n", encoding="utf-8")
    (repo / "tests" / "reference-solutions" / "flat-legacy").mkdir(parents=True)
    (repo / "tasks" / "concept-1" / "no-ref.md").write_text(
        "# noref\n", encoding="utf-8")
    return repo


class TestDiscoverReferenceSubmissions(unittest.TestCase):
    def test_folder_local_and_legacy_references_both_found(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_ref_repo(Path(td))
            subs = discover_reference_submissions(repo)
            # Order follows tasks.discover: root first, then sets alphabetically;
            # the no-reference task is skipped (nothing to grade).
            self.assertEqual([s.task_id for s in subs],
                             ["root-task", "bp-g2/gp-poison",
                              "concept-1/flat-legacy"])
            by_id = {s.task_id: s for s in subs}
            # Folder-LOCAL reference/ for the folder-form task ...
            self.assertEqual(by_id["bp-g2/gp-poison"].submission_dir,
                             repo / "tasks" / "bp-g2" / "gp-poison" / "reference")
            # ... legacy tests/reference-solutions/<bare id>/ for the others.
            self.assertEqual(by_id["root-task"].submission_dir,
                             repo / "tests" / "reference-solutions" / "root-task")
            self.assertEqual(by_id["concept-1/flat-legacy"].submission_dir,
                             repo / "tests" / "reference-solutions" / "flat-legacy")
            # Same record shape discover_submissions produces: Submission,
            # paired with its own resolved spec.
            self.assertTrue(all(isinstance(s, Submission) for s in subs))
            self.assertTrue(all(s.paired for s in subs))
            self.assertEqual(by_id["bp-g2/gp-poison"].task_spec,
                             repo / "tasks" / "bp-g2" / "gp-poison" / "task.md")
            self.assertEqual(by_id["root-task"].task_spec,
                             repo / "tasks" / "root-task.md")

    def test_set_filter_keeps_only_the_named_set(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_ref_repo(Path(td))
            self.assertEqual(
                [s.task_id for s in discover_reference_submissions(repo, "bp-g2")],
                ["bp-g2/gp-poison"])
            self.assertEqual(
                [s.task_id for s in discover_reference_submissions(repo, "root")],
                ["root-task"])
            self.assertEqual(discover_reference_submissions(repo, "no-such-set"), [])

    def test_run_references_mode_grades_the_reference_dirs(self):
        # run(references=...) discovers via discover_reference_submissions (no
        # outputs folder involved) and feeds each reference dir to the verify.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = _mk_ref_repo(base)
            verify = _FakeVerify(verdicts={"root-task": "PASS",
                                           "bp-g2/gp-poison": "PASS",
                                           "concept-1/flat-legacy": "FAIL"})
            summary = batch_eval.run(
                None, ue_root="/fake/UE", repo=repo, runs_root=base / "runs",
                label="refs", references="all", verify=verify,
                gate=_normal_gate(), log=lambda *_a: None)
            self.assertEqual(summary["n_graded"], 3)
            self.assertEqual(summary["n_pass"], 2)
            self.assertEqual({c[0] for c in verify.calls},
                             {"root-task", "bp-g2/gp-poison",
                              "concept-1/flat-legacy"})


class TestCbReferencesFlag(unittest.TestCase):
    """`cb batch-eval --references [all|<set>]` parses (const 'all'), routes to
    batch_eval.run(references=...), and is mutually exclusive with the outputs
    positional."""

    _SUMMARY = {"n_graded": 1, "n_pass": 1, "n_fail": 0, "pass_rate": 1.0,
                "n_excluded": 0, "excluded_by_verdict": {}}

    def _fake_ctx(self, repo: Path):
        return types.SimpleNamespace(
            py_exe="py", py_pre=[],
            ue=Path("C:/UE/Engine/Binaries/Win64/UnrealEditor.exe"),
            paths=types.SimpleNamespace(craftbench=repo))

    def test_parser_bare_flag_means_all_value_names_a_set(self):
        from aura_rig import cb as _cb
        ap = _cb.build_parser()
        self.assertIsNone(ap.parse_args(["batch-eval"]).references)
        self.assertEqual(ap.parse_args(["batch-eval", "--references"]).references,
                         "all")
        self.assertEqual(
            ap.parse_args(["batch-eval", "--references", "bp-g2"]).references,
            "bp-g2")

    def test_references_and_outputs_are_mutually_exclusive(self):
        from aura_rig import cb as _cb
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            out = repo / "outputs"
            out.mkdir()
            args = _cb.build_parser().parse_args(
                ["batch-eval", str(out), "--references", "--no-preflight"])
            with mock.patch.object(batch_eval, "run") as run_mock, \
                 mock.patch.object(_cb, "_say", lambda *_a, **_k: None):
                rc = _cb.cmd_batch_eval(self._fake_ctx(repo), args)
            self.assertEqual(rc, 2)
            run_mock.assert_not_called()

    def test_references_routes_to_run_with_the_references_kwarg(self):
        from aura_rig import cb as _cb
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            args = _cb.build_parser().parse_args(
                ["batch-eval", "--references", "bp-g2", "--no-preflight"])
            with mock.patch.object(batch_eval, "run",
                                   return_value=dict(self._SUMMARY)) as run_mock, \
                 mock.patch.object(_cb, "_say", lambda *_a, **_k: None):
                rc = _cb.cmd_batch_eval(self._fake_ctx(repo), args)
            self.assertEqual(rc, 0)
            run_mock.assert_called_once()
            self.assertIsNone(run_mock.call_args[0][0])  # no outputs dir
            self.assertEqual(run_mock.call_args[1]["references"], "bp-g2")


# ---------------------------------------------------------------------------
# (2) each verify scheduled through the mem-gate, slot cap never exceeded.
# ---------------------------------------------------------------------------

class TestSchedulingThroughMemGate(unittest.TestCase):
    def _subs(self, n, base):
        return [Submission(task_id=f"t{i}", submission_dir=base / f"t{i}",
                           task_spec=Path(f"/tasks/t{i}.md")) for i in range(n)]

    def test_verify_runs_under_gate_and_cap_is_respected(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = self._subs(6, base)
            # hold each verify briefly so concurrency is real; cap = 2.
            verify = _FakeVerify(
                verdicts={f"t{i}": "PASS" for i in range(6)}, hold_s=0.03)
            gate = _normal_gate(max_slots=2)
            results = asyncio.run(run_batch_eval(
                subs, verify=verify, run_root=base / "run", label="x",
                gate=gate, verify_concurrency=5, log=lambda *_a: None))

            self.assertEqual(len(results), 6)
            self.assertEqual(len(verify.calls), 6)
            # The gate admitted at most max_slots at once — both the gate's own
            # high-water mark AND the fake verify's observed peak prove it.
            self.assertLessEqual(gate.max_observed, 2)
            self.assertLessEqual(verify.peak, 2,
                                 f"more than 2 verifies ran at once: {verify.peak}")
            self.assertEqual(gate.in_use, 0)  # all slots released

    def test_pool_b_semaphore_also_caps_below_gate(self):
        # verify_concurrency=1 must serialize even though the gate allows 2.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = self._subs(4, base)
            verify = _FakeVerify(
                verdicts={f"t{i}": "PASS" for i in range(4)}, hold_s=0.03)
            gate = _normal_gate(max_slots=2)
            asyncio.run(run_batch_eval(
                subs, verify=verify, run_root=base / "run", label="x",
                gate=gate, verify_concurrency=1, log=lambda *_a: None))
            self.assertLessEqual(verify.peak, 1,
                                 "verify_concurrency=1 did not serialize")

    def test_gate_blocks_under_pressure_until_it_recedes(self):
        # Direct gate-level proof that batch_eval relies on a gate that BLOCKS
        # under WARN — the scheduler admits only once pressure returns to normal.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = self._subs(1, base)
            verify = _FakeVerify(verdicts={"t0": "PASS"})

            level = {"p": Pressure.WARN}
            gate = MemGate(read_pressure=lambda: level["p"], max_slots=2,
                           poll_interval=0.01, sleep=time.sleep)

            done = {"results": None}

            def runner():
                done["results"] = asyncio.run(run_batch_eval(
                    subs, verify=verify, run_root=base / "run", label="x",
                    gate=gate, verify_concurrency=2, log=lambda *_a: None))

            t = threading.Thread(target=runner, daemon=True)
            t.start()
            # Under WARN the verify must NOT have been called yet.
            time.sleep(0.1)
            self.assertEqual(len(verify.calls), 0, "verify ran under WARN pressure")
            # Pressure recedes → the verify proceeds and the batch completes.
            level["p"] = Pressure.NORMAL
            t.join(timeout=3.0)
            self.assertFalse(t.is_alive(), "batch never completed after pressure receded")
            self.assertEqual(len(verify.calls), 1)
            self.assertEqual(done["results"][0].overall, "PASS")


# ---------------------------------------------------------------------------
# (3) summary aggregated correctly.
# ---------------------------------------------------------------------------

class TestSummaryAggregation(unittest.TestCase):
    def test_pass_rate_excludes_non_graded(self):
        results = [
            EvalResult("a", "/o/a", "PASS", 1.0),
            EvalResult("b", "/o/b", "FAIL", 1.0),
            EvalResult("c", "/o/c", "PASS", 1.0),
            EvalResult("d", "/o/d", "SUBSTRATE-REJECT", 1.0),
            EvalResult("e", "/o/e", None, 0.0, error="no task spec"),
        ]
        s = summarize(results, label="L", wall_s=5.5)
        self.assertEqual(s["n_total"], 5)
        self.assertEqual(s["n_graded"], 3)         # a, b, c
        self.assertEqual(s["n_pass"], 2)           # a, c
        self.assertEqual(s["n_fail"], 1)           # b
        self.assertAlmostEqual(s["pass_rate"], 2 / 3)
        self.assertEqual(s["n_excluded"], 2)       # d (reject) + e (unpaired)
        self.assertEqual(s["excluded_by_verdict"],
                         {"SUBSTRATE-REJECT": 1, "None": 1})
        self.assertEqual(s["label"], "L")
        self.assertEqual(s["wall_s"], 5.5)
        self.assertEqual(len(s["results"]), 5)

    def test_pass_rate_none_when_nothing_graded(self):
        results = [EvalResult("a", "/o/a", "SUBSTRATE-REJECT", 1.0)]
        s = summarize(results, label="L", wall_s=1.0)
        self.assertIsNone(s["pass_rate"])
        self.assertEqual(s["n_graded"], 0)

    def test_end_to_end_summary_carries_layers_and_reports(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = [
                Submission("t0", base / "t0", Path("/tasks/t0.md")),
                Submission("t1", base / "t1", Path("/tasks/t1.md")),
            ]
            verify = _FakeVerify(
                verdicts={"t0": "PASS", "t1": "FAIL"},
                layers={"t0": {"L1": "passed", "L2": "passed"},
                        "t1": {"L1": "passed", "L2": "failed"}})
            results = asyncio.run(run_batch_eval(
                subs, verify=verify, run_root=base / "run", label="e2e",
                gate=_normal_gate(), verify_concurrency=2, log=lambda *_a: None))
            s = summarize(results, label="e2e", wall_s=1.0)
            self.assertEqual(s["n_graded"], 2)
            self.assertEqual(s["n_pass"], 1)
            by_id = {r["task_id"]: r for r in s["results"]}
            self.assertEqual(by_id["t0"]["layers"], {"L1": "passed", "L2": "passed"})
            self.assertIsNotNone(by_id["t0"]["report"])  # report.json was written


# ---------------------------------------------------------------------------
# (4) a failing verify does not sink the batch.
# ---------------------------------------------------------------------------

class TestFailureIsolation(unittest.TestCase):
    def test_crashing_verify_isolated_others_complete(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = [
                Submission("good1", base / "good1", Path("/tasks/good1.md")),
                Submission("boom", base / "boom", Path("/tasks/boom.md")),
                Submission("good2", base / "good2", Path("/tasks/good2.md")),
            ]
            verify = _FakeVerify(
                verdicts={"good1": "PASS", "good2": "FAIL"}, raise_for=["boom"])
            results = asyncio.run(run_batch_eval(
                subs, verify=verify, run_root=base / "run", label="iso",
                gate=_normal_gate(), verify_concurrency=3, log=lambda *_a: None))

            by_id = {r.task_id: r for r in results}
            self.assertEqual(set(by_id), {"good1", "boom", "good2"})
            # The crash is contained as an error result, the rest still graded.
            self.assertEqual(by_id["good1"].overall, "PASS")
            self.assertEqual(by_id["good2"].overall, "FAIL")
            self.assertIsNone(by_id["boom"].overall)
            self.assertIn("boom", by_id["boom"].error)
            # The batch summary still aggregates the survivors.
            s = summarize(results, label="iso", wall_s=1.0)
            self.assertEqual(s["n_graded"], 2)
            self.assertEqual(s["n_excluded"], 1)

    def test_unpaired_submission_skips_verify_and_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            subs = [
                Submission("paired", base / "paired", Path("/tasks/paired.md")),
                Submission("orphan", base / "orphan", task_spec=None),
            ]
            verify = _FakeVerify(verdicts={"paired": "PASS"})
            results = asyncio.run(run_batch_eval(
                subs, verify=verify, run_root=base / "run", label="up",
                gate=_normal_gate(), verify_concurrency=2, log=lambda *_a: None))
            by_id = {r.task_id: r for r in results}
            # The unpaired one never reaches verify.
            self.assertEqual([c[0] for c in verify.calls], ["paired"])
            self.assertIsNone(by_id["orphan"].overall)
            self.assertIn("no task spec", by_id["orphan"].error)
            s = summarize(results, label="up", wall_s=1.0)
            self.assertEqual(s["n_graded"], 1)
            self.assertEqual(s["n_excluded"], 1)


# ---------------------------------------------------------------------------
# run() top-level: writes summary.json + per-submission reports under runs/.
# ---------------------------------------------------------------------------

class TestRunTopLevel(unittest.TestCase):
    def test_run_writes_summary_json_under_run_dir(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = _mk_outputs(base / "outputs", ["t0", "t1"])
            # Patch tasks.resolve_task_path so discovery pairs without a real tree.
            specs = {"t0": Path("/tasks/t0.md"), "t1": Path("/tasks/t1.md")}
            orig = batch_eval.tasks.resolve_task_path
            batch_eval.tasks.resolve_task_path = _fake_resolve(specs)
            try:
                verify = _FakeVerify(verdicts={"t0": "PASS", "t1": "FAIL"})
                summary = batch_eval.run(
                    out, ue_root="/fake/UE", repo=base, runs_root=base / "runs",
                    label="mylabel", verify=verify, gate=_normal_gate(),
                    log=lambda *_a: None)
            finally:
                batch_eval.tasks.resolve_task_path = orig

            self.assertEqual(summary["n_graded"], 2)
            self.assertEqual(summary["n_pass"], 1)
            # The run dir + summary.json exist on disk.
            run_dirs = list((base / "runs" / "aura-product-eval").iterdir())
            self.assertEqual(len(run_dirs), 1)
            self.assertTrue(run_dirs[0].name.startswith("mylabel-"))
            disk = json.loads((run_dirs[0] / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(disk["n_pass"], 1)
            self.assertEqual(disk["label"], "mylabel")

    def test_run_empty_outputs_returns_zero_total(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = _mk_outputs(base / "outputs", [])  # no children
            summary = batch_eval.run(
                out, ue_root="/fake/UE", repo=base, runs_root=base / "runs",
                label="empty", verify=_FakeVerify(), log=lambda *_a: None)
            self.assertEqual(summary["n_total"], 0)
            self.assertIsNone(summary["pass_rate"])


class TestDefaultVerifyCmd(unittest.TestCase):
    """The shelling verify builds the right run_task.py command line."""

    def _capture_cmd(self, **kwargs):
        captured = {}

        class _CP:
            returncode = 0
            stdout = ""

        def _fake_run(cmd, **_kw):
            captured["cmd"] = cmd
            return _CP()

        verify = make_default_verify(ue_root="/fake/UE", run_subprocess=_fake_run, **kwargs)
        sub = Submission(task_id="t", submission_dir=Path("/sub"), task_spec=Path("/spec.md"))
        verify(sub, Path("/r.json"))
        return captured["cmd"]

    def test_warm_cache_appends_flag(self):
        self.assertIn("--warm-cache", self._capture_cmd(warm_cache=True))

    def test_no_warm_cache_by_default(self):
        self.assertNotIn("--warm-cache", self._capture_cmd())

    def test_from_live_appends_flag(self):
        self.assertIn("--substrate-from-live", self._capture_cmd(from_live=True))

    def test_no_keep_workdir_by_default(self):
        cmd = self._capture_cmd()
        self.assertNotIn("--keep-workdir", cmd)
        self.assertNotIn("--workdir", cmd)


class TestKeepWorkdir(unittest.TestCase):
    """--keep threading: make_default_verify(keep_workdir=True) appends
    --keep-workdir + a SHORT per-task --workdir under CRAFTBENCH_WD_ROOT, and
    the row result records the kept path."""

    def setUp(self):
        import os
        self._os = os
        self._old_root = os.environ.pop("CRAFTBENCH_WD_ROOT", None)
        self._td = tempfile.TemporaryDirectory()
        os.environ["CRAFTBENCH_WD_ROOT"] = str(Path(self._td.name) / "cbwd")

    def tearDown(self):
        if self._old_root is None:
            self._os.environ.pop("CRAFTBENCH_WD_ROOT", None)
        else:
            self._os.environ["CRAFTBENCH_WD_ROOT"] = self._old_root
        self._td.cleanup()

    def _verify_and_cmd(self, **kwargs):
        captured = {}

        class _CP:
            returncode = 0
            stdout = ""

        def _fake_run(cmd, **_kw):
            captured["cmd"] = cmd
            return _CP()

        verify = make_default_verify(ue_root="/fake/UE", run_subprocess=_fake_run,
                                     **kwargs)
        sub = Submission(task_id="bp-g2/t", submission_dir=Path("/sub"),
                         task_spec=Path("/spec.md"))
        verify(sub, Path("/r.json"))
        return verify, sub, captured["cmd"]

    def test_keep_appends_keep_workdir_and_short_workdir(self):
        verify, sub, cmd = self._verify_and_cmd(keep_workdir=True, workdir_key="run-1")
        self.assertIn("--keep-workdir", cmd)
        wd = Path(cmd[cmd.index("--workdir") + 1])
        self.assertEqual(wd.parent, Path(self._os.environ["CRAFTBENCH_WD_ROOT"]))
        self.assertEqual(len(wd.name), 10)  # the short sha1 stem (MAX_PATH dodge)
        # The exposed workdir_for(sub) matches what went on the cmd line.
        self.assertEqual(verify.workdir_for(sub), wd)

    def test_workdir_keyed_by_run_and_task(self):
        verify, _sub, cmd_a = self._verify_and_cmd(keep_workdir=True, workdir_key="run-1")
        _v, _s, cmd_b = self._verify_and_cmd(keep_workdir=True, workdir_key="run-2")
        wd_a = cmd_a[cmd_a.index("--workdir") + 1]
        wd_b = cmd_b[cmd_b.index("--workdir") + 1]
        self.assertNotEqual(wd_a, wd_b, "different runs must not share a workdir")
        sub2 = Submission(task_id="bp-g2/other", submission_dir=Path("/s2"),
                          task_spec=Path("/spec2.md"))
        self.assertNotEqual(verify.workdir_for(sub2), Path(wd_a),
                            "different tasks must not share a workdir")

    def test_workdir_for_none_when_keep_off(self):
        verify, sub, _cmd = self._verify_and_cmd()
        self.assertIsNone(verify.workdir_for(sub))

    def test_row_records_kept_workdir(self):
        kept = Path("/kept/wd/abc123")

        def fake_verify(sub, report_json):
            return "PASS", {"L1": "passed"}

        fake_verify.workdir_for = lambda sub: kept
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=fake_verify, run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), log=lambda *_a: None))
        self.assertEqual(results[0].workdir, str(kept))
        row = summarize(results, label="k", wall_s=0.1)["results"][0]
        self.assertEqual(row["workdir"], str(kept))

    def test_row_workdir_none_for_plain_verify(self):
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=_FakeVerify(), run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), log=lambda *_a: None))
        self.assertIsNone(results[0].workdir)


# ---------------------------------------------------------------------------
# Workdir RETENTION on the kept workdirs.
#
# Measured 2026-07-25 on the Windows testbed: one kept verifier workdir is
# 5.54 GB, of which 4.72 GB is <Proj>/Intermediate/Build/Win64/x64 (cl.exe
# .obj/.pch) — so a 15-task `cb batch-eval --keep` is ~83 GB, ~71 GB of it
# compiler byproduct nobody reads, and `cb clean --workdirs` deliberately KEEPS
# anything a summary.json still names. Retention mode "slim" (the default) is
# the reclaim; the tests below pin the two halves that matter:
#   * a PASSING leg really reaches the deleter, with its kept workdir;
#   * an L1-FAILED leg does NOT — a broken build is exactly the run whose
#     .obj/.pch tree is the evidence. That guard lives in
#     workdir_retention.apply, and the point of asserting its REFUSAL REASON
#     here is to prove batch_eval routes THROUGH the guard instead of
#     re-deciding (or bypassing) it locally.
# The fs_cleanup seam is faked (as in test_workdir_retention.py), so nothing
# here imports tools/verify-single and no test can reach a real C:\cb\wd.
# ---------------------------------------------------------------------------

def _slim_stats(reclaimed_bytes=0, refused=False):
    """The shape fs_cleanup.slim_workdir really returns (a SlimStats dataclass),
    modelled rather than imported — the deleter is authored on the other side of
    a package seam and this suite must stay importable without it."""
    return types.SimpleNamespace(reclaimed_bytes=reclaimed_bytes, deleted_paths=3,
                                 elapsed_s=0.0, notes=[], refused=refused,
                                 project_dir=None)


class TestWorkdirRetention(unittest.TestCase):
    """make_default_verify's kept workdirs are handed to workdir_retention.apply
    AFTER the leg's report.json has been read, and the row/summary record what
    happened.

    The reclaim hangs off the verify callable as ``retain(sub, report_json)``
    rather than living inside ``_verify``, so ``_grade_one`` can run it once the
    row's ``wall_s`` clock has stopped — a multi-GB delete inside that window
    would inflate a number every summary row publishes."""

    _ENV = ("CB_WORKDIR_RETENTION", "CB_PREVIEW", "CB_ROOT", "CRAFTBENCH_WD_ROOT")

    def setUp(self):
        import contextlib
        import io
        import os
        # Method-local imports, following TestKeepWorkdir's precedent above.
        # contextlib/io are kept on self because _run_leg redirects the reclaim's
        # own stdout line away from the test output.
        self._contextlib, self._io = contextlib, io
        saved = {k: os.environ.pop(k, None) for k in self._ENV}

        def _restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(_restore)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        # ONE env var drives both sides: batch_eval._short_workdir places the
        # kept workdir under it and workdir_retention's _under_wd_root gate
        # resolves the SAME wd-root from it, so the two agree without patching.
        os.environ["CRAFTBENCH_WD_ROOT"] = str(self.root / "wd")

    def _run_leg(self, l1_status, *, keep=True, reclaimed=4_720_000_000):
        """Drive ONE make_default_verify leg with a FAKE run_task.py.

        The fake creates the ``--workdir`` tree a real verifier would have built
        and writes the report the real one writes to ``--report-json``, so
        retention sees exactly the on-disk shape production hands it. Both halves
        run in production order — the verify, then ``retain`` — because that IS
        the ordering contract: the report must be read out of the leg before the
        workdir is touched. Returns (verify, sub, record, slim_calls, stdout)."""
        slim_calls = []

        def _fake_slim(wd, log=None):
            slim_calls.append(Path(wd))
            return _slim_stats(reclaimed)

        def _no_rmtree(wd, log=None):
            self.fail("mode 'none' was never requested — the whole-tree deleter "
                      "must not be reachable from the default 'slim' path")

        cleanup_ns = types.SimpleNamespace(slim_workdir=_fake_slim,
                                           robust_rmtree=_no_rmtree)

        class _CP:
            returncode = 0
            stdout = ""

        def _fake_run(cmd, **_kw):
            if "--workdir" in cmd:
                wd = Path(cmd[cmd.index("--workdir") + 1])
                (wd / "Proj" / "Intermediate" / "Build" / "Win64" / "x64").mkdir(
                    parents=True, exist_ok=True)
                (wd / "out").mkdir(parents=True, exist_ok=True)
            rj = Path(cmd[cmd.index("--report-json") + 1])
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text(json.dumps({
                "overall": "pass" if l1_status == "pass" else "fail",
                "layers": {"L1": {"status": l1_status},
                           "L2": {"status": "pass"}}}), encoding="utf-8")
            return _CP()

        verify = make_default_verify(ue_root="/fake/UE", run_subprocess=_fake_run,
                                     keep_workdir=keep, workdir_key="ret-run")
        sub = Submission(task_id="wave1/t1-x", submission_dir=Path("/sub"),
                         task_spec=Path("/spec.md"))
        report_json = self.root / "r.json"
        buf = self._io.StringIO()
        with mock.patch.object(batch_eval.workdir_retention, "_fs_cleanup",
                               lambda: cleanup_ns), \
                self._contextlib.redirect_stdout(buf):
            verify(sub, report_json)
            record = verify.retain(sub, report_json)
        return verify, sub, record, slim_calls, buf.getvalue()

    def test_passing_leg_is_slimmed(self):
        verify, sub, rec, slim_calls, out = self._run_leg("pass")
        self.assertEqual(slim_calls, [verify.workdir_for(sub)],
                         "the passing leg's KEPT workdir must reach the deleter")
        self.assertEqual(rec["mode"], "slim")          # the 2026-07-25 default
        self.assertEqual(rec["reclaimed_bytes"], 4_720_000_000)
        self.assertNotIn("reason", rec)                # nothing refused
        self.assertIn("slim", out)                     # and it said so out loud

    def test_l1_failure_is_not_slimmed(self):
        _verify, _sub, rec, slim_calls, _out = self._run_leg("fail")
        self.assertEqual(slim_calls, [],
                         "a FAILED L1 build is the evidence — its .obj/.pch tree "
                         "must survive")
        # The REFUSAL REASON is the proof the guard is wired through rather than
        # re-implemented here: only workdir_retention.apply spells it 'l1_fail'.
        self.assertEqual(rec["reason"], "l1_fail")
        self.assertEqual(rec["mode"], "full")
        self.assertEqual(rec["requested"], "slim")
        self.assertEqual(rec["reclaimed_bytes"], 0)

    def test_no_kept_workdir_means_no_retention(self):
        # Without --keep-workdir the verifier grades in its own self-deleting
        # tempdir (or a warm slot) — there is no workdir of ours to reclaim, and
        # touching one anyway is how a shared warm pool gets destroyed.
        _verify, _sub, rec, slim_calls, _out = self._run_leg("pass", keep=False)
        self.assertEqual(slim_calls, [])
        self.assertIsNone(rec)

    def test_row_and_summary_carry_the_retention_record(self):
        rec = {"mode": "slim", "reclaimed_bytes": 4_720_000_000, "elapsed_s": 1.2}
        order = []

        def fake_verify(sub, report_json):
            order.append("verify")
            return "PASS", {"L1": "pass"}

        def fake_retain(sub, report_json):
            order.append("retain")
            return rec

        fake_verify.retain = fake_retain
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=fake_verify, run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), log=lambda *_a: None))
        # The scheduler must grade first and reclaim second — a retain that ran
        # before (or instead of) the verify would be deleting live evidence.
        self.assertEqual(order, ["verify", "retain"])
        self.assertEqual(results[0].retention, rec)
        row = summarize(results, label="k", wall_s=0.1)["results"][0]
        self.assertEqual(row["retention"], rec)

    def test_retention_is_not_billed_to_the_row_wall_s(self):
        """A slow reclaim must not inflate the leg's published wall_s — the
        clock stops with the verdict, not with the delete."""
        ticks = iter([100.0, 100.5, 999.0])   # t0, wall_s stop, (never reached)

        def fake_verify(sub, report_json):
            return "PASS", {"L1": "pass"}

        fake_verify.retain = lambda sub, report_json: {
            "mode": "slim", "reclaimed_bytes": 1, "elapsed_s": 480.0}
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=fake_verify, run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), clock=lambda: next(ticks),
                log=lambda *_a: None))
        self.assertAlmostEqual(results[0].wall_s, 0.5)

    def test_a_crashing_retain_cannot_cost_the_leg_its_verdict(self):
        """Cleanup is never worth a grade: a retain that blows up must leave the
        PASS intact (and graded), not turn the row into an overall=None error."""
        def fake_verify(sub, report_json):
            return "PASS", {"L1": "pass"}

        def _boom(sub, report_json):
            raise OSError("WinError 32: the process cannot access the file")

        fake_verify.retain = _boom
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=fake_verify, run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), log=lambda *_a: None))
        self.assertEqual(results[0].overall, "PASS")
        self.assertTrue(results[0].graded)
        self.assertIsNone(results[0].error)
        self.assertIsNone(results[0].retention)

    def test_row_retention_none_for_a_verify_without_the_retain_seam(self):
        with tempfile.TemporaryDirectory() as td:
            subs = [Submission("t0", Path(td) / "t0", Path("/tasks/t0.md"))]
            results = asyncio.run(run_batch_eval(
                subs, verify=_FakeVerify(), run_root=Path(td) / "run", label="k",
                gate=_normal_gate(), log=lambda *_a: None))
        self.assertIsNone(results[0].retention)


# ---------------------------------------------------------------------------
# (5) the GATE: the exit code must mean something, and must never contradict
#     the printed summary line.
#
# 2026-07-25 testbed regression: `cb batch-eval --references all` printed
# "batch-eval: 0/15 graded PASS (0.0%); 0 excluded {}" and exited 0, because
# batch_eval.main ended in a bare `return 0` and cb.cmd_batch_eval graded only
# HARNESS health (exit 1 iff nothing graded). README.md advertises this command
# as "the 15/15 regression gate" — a gate that greens a total wipeout gates
# nothing. Every test below FAILS against that pre-fix code.
# ---------------------------------------------------------------------------

def _summary(*, n_graded, n_pass, n_fail, n_excluded=0):
    """A summarize()-shaped dict — no verify, no grade, no UE (the sibling
    suites' fake-the-seam convention)."""
    return {"label": "gate", "wall_s": 1.0, "n_total": n_graded + n_excluded,
            "n_graded": n_graded, "n_pass": n_pass, "n_fail": n_fail,
            "pass_rate": (n_pass / n_graded) if n_graded else None,
            "n_excluded": n_excluded, "excluded_by_verdict": {}, "results": []}


class TestGateResult(unittest.TestCase):
    """batch_eval.gate_result — the single source of truth both entry points
    read for their exit code AND their verdict words."""

    def test_all_graded_passed_is_zero(self):
        code, verdict = batch_eval.gate_result(_summary(n_graded=15, n_pass=15, n_fail=0))
        self.assertEqual(code, 0)
        self.assertIn("GATE OK", verdict)

    def test_any_graded_fail_is_non_zero(self):
        code, verdict = batch_eval.gate_result(_summary(n_graded=15, n_pass=14, n_fail=1))
        self.assertNotEqual(code, 0)
        self.assertEqual(code, 1)      # 1 = real failure (2 stays usage-only)
        self.assertIn("GATE FAILED", verdict)

    def test_total_wipeout_is_non_zero(self):
        # The exact shape of the reported incident: 0/15 PASS.
        code, verdict = batch_eval.gate_result(_summary(n_graded=15, n_pass=0, n_fail=15))
        self.assertEqual(code, 1)
        self.assertIn("15/15 graded FAIL", verdict)

    def test_zero_graded_is_non_zero(self):
        # An empty gate is not a passing gate — nothing was actually judged.
        for s in (_summary(n_graded=0, n_pass=0, n_fail=0),
                  _summary(n_graded=0, n_pass=0, n_fail=0, n_excluded=15)):
            code, verdict = batch_eval.gate_result(s)
            self.assertEqual(code, 1)
            self.assertIn("0 graded", verdict)

    def test_allow_fail_opts_out_of_the_fail_rule_only(self):
        # The explicit measurement-mode opt-out restores the pre-fix harness-only
        # reading for graded FAILs ...
        code, verdict = batch_eval.gate_result(
            _summary(n_graded=15, n_pass=0, n_fail=15), allow_fail=True)
        self.assertEqual(code, 0)
        self.assertIn("--no-gate", verdict)
        # ... but can NEVER green an empty gate.
        code, _v = batch_eval.gate_result(
            _summary(n_graded=0, n_pass=0, n_fail=0), allow_fail=True)
        self.assertEqual(code, 1)

    def test_excluded_rows_alone_do_not_flip_a_clean_gate(self):
        # SUBSTRATE-REJECT / UNPAIRED rows are verifier noise, kept out of the
        # verdict exactly as summarize() keeps them out of the denominator.
        code, _v = batch_eval.gate_result(
            _summary(n_graded=14, n_pass=14, n_fail=0, n_excluded=1))
        self.assertEqual(code, 0)


class TestMainExitCode(unittest.TestCase):
    """batch_eval.main (the standalone `python -m aura_rig.batch_eval` entry —
    the one that printed 0/15 PASS over exit 0) and the parity of its printed
    line with its return value."""

    def _main(self, summary, argv_extra=()):
        argv = ["/outputs", "--ue-root", "/fake/UE", *argv_extra]
        buf = []
        with mock.patch.object(batch_eval, "run", return_value=summary), \
             mock.patch("builtins.print", lambda *a, **_k: buf.append(" ".join(str(x) for x in a))):
            rc = batch_eval.main(argv)
        return rc, "\n".join(buf)

    def test_all_pass_exits_zero(self):
        rc, out = self._main(_summary(n_graded=15, n_pass=15, n_fail=0))
        self.assertEqual(rc, 0)
        self.assertIn("GATE OK", out)

    def test_some_fail_exits_non_zero(self):
        rc, out = self._main(_summary(n_graded=15, n_pass=14, n_fail=1))
        self.assertEqual(rc, 1)
        self.assertIn("GATE FAILED", out)

    def test_zero_graded_exits_non_zero(self):
        rc, out = self._main(_summary(n_graded=0, n_pass=0, n_fail=0))
        self.assertEqual(rc, 1)
        self.assertIn("GATE FAILED", out)

    def test_printed_line_and_exit_code_cannot_disagree(self):
        # The reported incident, verbatim: the human-readable line says 0/15 PASS
        # and the process must not claim success alongside it.
        rc, out = self._main(_summary(n_graded=15, n_pass=0, n_fail=15))
        self.assertIn("0/15 graded PASS", out)
        self.assertEqual(rc, 1)
        self.assertIn(f"(exit {rc})", out)
        self.assertNotIn("GATE OK", out)

    def test_allow_fail_flag_parses_and_forces_zero(self):
        self.assertFalse(batch_eval.parse_args(
            ["/o", "--ue-root", "/ue"]).allow_fail)
        rc, out = self._main(_summary(n_graded=15, n_pass=0, n_fail=15),
                             argv_extra=["--no-gate"])
        self.assertEqual(rc, 0)
        self.assertIn("--no-gate", out)


class TestCbBatchEvalExitCode(unittest.TestCase):
    """cb.cmd_batch_eval — the arm README.md calls "the 15/15 regression gate"."""

    def _fake_ctx(self, repo: Path):
        return types.SimpleNamespace(
            py_exe="py", py_pre=[],
            ue=Path("C:/UE/Engine/Binaries/Win64/UnrealEditor.exe"),
            paths=types.SimpleNamespace(craftbench=repo))

    def _run(self, summary, argv_extra=()):
        from aura_rig import cb as _cb
        said = []
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            # --no-preflight is REQUIRED for hermeticity, not a shortcut:
            # cmd_batch_eval opens with the real envgate, which reads live
            # machine state (Live Coding console, editor processes, RAM). With
            # an editor up — i.e. during ordinary work — these 6 tests went red
            # for reasons that have nothing to do with the exit-code logic they
            # assert (observed 2026-07-25). The gate is exercised by
            # test_cb_envgate.py; here it is noise.
            args = _cb.build_parser().parse_args(
                ["batch-eval", "--references", "--no-preflight", *argv_extra])
            with mock.patch.object(batch_eval, "run", return_value=summary), \
                 mock.patch.object(_cb, "_say", lambda *a, **_k: said.append(
                     " ".join(str(x) for x in a))):
                rc = _cb.cmd_batch_eval(self._fake_ctx(repo), args)
        return rc, "\n".join(said)

    def test_all_pass_exits_zero(self):
        rc, out = self._run(_summary(n_graded=15, n_pass=15, n_fail=0))
        self.assertEqual(rc, 0)
        self.assertIn("GATE OK", out)

    def test_some_fail_exits_non_zero(self):
        rc, _out = self._run(_summary(n_graded=15, n_pass=14, n_fail=1))
        self.assertEqual(rc, 1)

    def test_total_wipeout_exits_non_zero_and_says_so(self):
        rc, out = self._run(_summary(n_graded=15, n_pass=0, n_fail=15))
        self.assertEqual(rc, 1)
        self.assertIn("0/15 graded PASS", out)   # the line the incident showed
        self.assertIn("GATE FAILED", out)
        self.assertIn(f"(exit {rc})", out)       # line and code cannot disagree

    def test_zero_graded_exits_non_zero(self):
        rc, out = self._run(_summary(n_graded=0, n_pass=0, n_fail=0))
        self.assertEqual(rc, 1)
        self.assertIn("0 submissions graded", out)

    def test_no_gate_restores_measurement_mode(self):
        rc, out = self._run(_summary(n_graded=15, n_pass=0, n_fail=15),
                            argv_extra=["--no-gate"])
        self.assertEqual(rc, 0)
        self.assertIn("--no-gate", out)

    def test_dash_a_still_abbreviates_to_agent(self):
        """The measurement opt-out must never be spelled `--a*` on the FLAT
        parser: argparse prefix-matching made `--a` ambiguous against `--agent`
        while this flag was `--allow-fail`, so `cb smoke --a <model>` died with
        exit 2 (2026-07-25 testbed verification)."""
        from aura_rig import cb as _cb
        ns = _cb.build_parser().parse_args(["smoke", "--a", "sonnet-4.6"])
        self.assertEqual(ns.agent, "sonnet-4.6")


if __name__ == "__main__":
    unittest.main()
