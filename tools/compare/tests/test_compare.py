"""Cross-product comparison: load result.json, aggregate per capability×product,
rank, pick leaders, render. Synthetic data — no UE, no real runs needed."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

import compare_products as cp  # noqa: E402  (module handle: _REPO is patchable)
from compare_products import (  # noqa: E402
    aggregate,
    load_result,
    render_markdown,
    to_dict,
)

_B = chr(92)  # a literal backslash, spelled so nothing in the toolchain eats it


def _task_md(d: Path, name: str, capability: str) -> Path:
    p = d / f"{name}.md"
    p.write_text(f"## Task ID and metadata\n\n- task_id: {name}\n- capability_bucket: {capability}\n",
                 encoding="utf-8")
    return p


def _result(d: Path, *, product: str, task_md: Path, overall: str, advisory=None, cost=None) -> Path:
    verifier = None
    if advisory is not None:
        verifier = {"overall": overall.lower(), "r2_advisory": {"advisory_score": advisory, "gating": False}}
    payload = {"run_id": "r", "task": str(task_md), "model": product, "overall": overall,
               "agent": {"cost_usd": cost}, "verifier": verifier}
    out = d / f"result_{product.replace(':', '_')}_{task_md.stem}.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


class TestLoad(unittest.TestCase):
    def test_parses_fields_and_capability(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            t = _task_md(d, "t0", "Gameplay Programming")
            r = load_result(_result(d, product="claude-p:opus", task_md=t, overall="PASS",
                                    advisory=0.8, cost=0.05))
            self.assertEqual(r.product, "claude-p:opus")
            self.assertEqual(r.task_id, "t0")
            self.assertEqual(r.capability, "Gameplay Programming")
            self.assertTrue(r.passed)
            self.assertEqual(r.advisory_score, 0.8)
            self.assertEqual(r.cost_usd, 0.05)

    def test_verifier_none_means_no_advisory(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            t = _task_md(d, "t1", "Materials")
            r = load_result(_result(d, product="aura-mcp:sonnet", task_md=t, overall="FAIL"))
            self.assertFalse(r.passed)
            self.assertIsNone(r.advisory_score)


class TestAggregate(unittest.TestCase):
    def _records(self, d: Path):
        gp = _task_md(d, "gp1", "Gameplay Programming")
        gp2 = _task_md(d, "gp2", "Gameplay Programming")
        mat = _task_md(d, "mat1", "Materials")
        paths = [
            # claude-p: strong at GP (2/2), weak at Materials (0/1)
            _result(d, product="claude-p:opus", task_md=gp, overall="PASS"),
            _result(d, product="claude-p:opus", task_md=gp2, overall="PASS"),
            _result(d, product="claude-p:opus", task_md=mat, overall="FAIL"),
            # aura-mcp: weak at GP (0/2), strong at Materials (1/1)
            _result(d, product="aura-mcp:sonnet", task_md=gp, overall="FAIL"),
            _result(d, product="aura-mcp:sonnet", task_md=gp2, overall="FAIL"),
            _result(d, product="aura-mcp:sonnet", task_md=mat, overall="PASS"),
        ]
        return [load_result(p) for p in paths]

    def test_cells_and_pass_rates(self):
        with tempfile.TemporaryDirectory() as d:
            cmp = aggregate(self._records(Path(d)))
            self.assertEqual(set(cmp.products), {"claude-p:opus", "aura-mcp:sonnet"})
            self.assertEqual(set(cmp.capabilities), {"Gameplay Programming", "Materials"})
            self.assertEqual(cmp.cell("Gameplay Programming", "claude-p:opus").pass_rate, 1.0)
            self.assertEqual(cmp.cell("Materials", "claude-p:opus").pass_rate, 0.0)
            self.assertEqual(cmp.cell("Gameplay Programming", "aura-mcp:sonnet").pass_rate, 0.0)

    def test_leaders_and_ranking(self):
        with tempfile.TemporaryDirectory() as d:
            cmp = aggregate(self._records(Path(d)))
            self.assertEqual(cmp.leader("Gameplay Programming"), "claude-p:opus")  # 2/2 > 0/2
            self.assertEqual(cmp.leader("Materials"), "aura-mcp:sonnet")           # 1/1 > 0/1
            ranked = dict(cmp.ranked("claude-p:opus"))
            self.assertEqual(ranked["Gameplay Programming"], 1.0)
            self.assertEqual(ranked["Materials"], 0.0)

    def test_render_and_dict(self):
        with tempfile.TemporaryDirectory() as d:
            cmp = aggregate(self._records(Path(d)))
            md = render_markdown(cmp)
            self.assertIn("claude-p:opus", md)
            self.assertIn("strong:", md)
            doc = to_dict(cmp)
            self.assertEqual(doc["leaders"]["Gameplay Programming"], "claude-p:opus")
            self.assertTrue(any(c["product"] == "aura-mcp:sonnet" for c in doc["cells"]))


class TestHeadToHead(unittest.TestCase):
    def test_no_overlap_is_ungrounded(self):
        """Disjoint tasks per product → no shared task, capability ungrounded."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ga = _task_md(d, "gp-a", "Gameplay Programming")
            gb = _task_md(d, "gp-b", "Gameplay Programming")
            recs = [
                load_result(_result(d, product="aura-mcp:sonnet", task_md=ga, overall="PASS")),
                load_result(_result(d, product="claude-p:opus", task_md=gb, overall="PASS")),
            ]
            cmp = aggregate(recs)
            self.assertEqual(cmp.shared_tasks(), [])
            self.assertFalse(cmp.is_grounded("Gameplay Programming"))
            md = render_markdown(cmp)
            self.assertIn("No task has been run by ≥2 products", md)
            self.assertIn("⚠", md)  # ungrounded marker on the capability row
            self.assertIn("Gameplay Programming",
                          to_dict(cmp)["ungrounded_capabilities"])

    def test_shared_task_is_grounded_head_to_head(self):
        """Same task run by both products → shared task, grounded, head-to-head row."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            t = _task_md(d, "gp-gas-launch", "Gameplay Programming")
            recs = [
                load_result(_result(d, product="aura-mcp:sonnet", task_md=t, overall="PASS")),
                load_result(_result(d, product="aura-mcp:sonnet", task_md=t, overall="FAIL")),
                load_result(_result(d, product="claude-p:opus", task_md=t, overall="FAIL")),
            ]
            cmp = aggregate(recs)
            self.assertEqual(cmp.shared_tasks(), ["gp-gas-launch"])
            self.assertTrue(cmp.is_grounded("Gameplay Programming"))
            self.assertEqual(cmp.task_cell("gp-gas-launch", "aura-mcp:sonnet").pass_rate, 0.5)
            self.assertEqual(cmp.task_cell("gp-gas-launch", "claude-p:opus").pass_rate, 0.0)
            doc = to_dict(cmp)
            self.assertEqual(doc["ungrounded_capabilities"], [])
            h2h = {row["task_id"]: row for row in doc["head_to_head"]}
            self.assertIn("gp-gas-launch", h2h)
            self.assertEqual(h2h["gp-gas-launch"]["products"]["aura-mcp:sonnet"]["n"], 2)
            md = render_markdown(cmp)
            self.assertIn("Head-to-head", md)
            self.assertIn("gp-gas-launch", md)


class TestHarnessFaultsLeaveTheDenominator(unittest.TestCase):
    """A run that never reached a gradable state is not a model failure.

    Before this, ``passed`` was ``overall == "PASS"`` and ``n`` incremented
    unconditionally, so HARNESS-ERROR / TIMEOUT / SANDBOX-REJECT each landed in
    the denominator as a non-pass and silently deflated the rate. There was no
    excluded bucket, so the error was not even visible as a warning.
    """

    def _cmp(self, d: Path, verdicts):
        gp = _task_md(d, "gp1", "Gameplay Programming")
        paths = [_result(d / f"r{i}", product="claude-p:opus", task_md=gp, overall=v)
                 for i, v in enumerate(verdicts)]
        return aggregate([load_result(p) for p in paths])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        # _result writes into a per-verdict subdir so filenames never collide.
        for i in range(8):
            (self.d / f"r{i}").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_harness_error_is_not_a_failure(self):
        cmp = self._cmp(self.d, ["PASS", "PASS", "HARNESS-ERROR"])
        cell = cmp.cell("Gameplay Programming", "claude-p:opus")
        self.assertEqual(cell.n, 2)          # denominator excludes the fault
        self.assertEqual(cell.n_pass, 2)
        self.assertEqual(cell.n_excluded, 1)
        self.assertEqual(cell.pass_rate, 1.0)  # was 0.667 before the fix

    def test_every_harness_verdict_is_excluded(self):
        cmp = self._cmp(self.d, ["PASS", "FAIL", "HARNESS-ERROR", "TIMEOUT",
                                 "AGENT-CONFIG-ERROR", "UNGRADED"])
        cell = cmp.cell("Gameplay Programming", "claude-p:opus")
        self.assertEqual(cell.n, 2)
        self.assertEqual(cell.n_excluded, 4)
        self.assertEqual(cell.pass_rate, 0.5)

    def test_model_outcomes_are_graded_per_owner_decision(self):
        """SANDBOX-REJECT / NO_DELIVERABLE / FAIL_NO_EDITS keep today's meaning.

        Owner decision 2026-08-14: they describe what the MODEL did, so
        excluding them would bias scores UPWARD — the mirror of the
        harness-fault bias. the denominator rule is authoritative here;
        ``adapters/base.GRADED_VERDICTS`` is known to diverge and is tracked
        separately.
        """
        cmp = self._cmp(self.d, ["PASS", "SANDBOX-REJECT", "NO_DELIVERABLE",
                                 "FAIL_NO_EDITS"])
        cell = cmp.cell("Gameplay Programming", "claude-p:opus")
        self.assertEqual(cell.n, 4)
        self.assertEqual(cell.n_excluded, 0)
        self.assertEqual(cell.n_pass, 1)

    def test_exclusions_are_visible_in_the_json(self):
        """The count must be reported, or a wrong number becomes an invisible one."""
        cmp = self._cmp(self.d, ["PASS", "HARNESS-ERROR"])
        cell = [c for c in to_dict(cmp)["cells"]
                if c["capability"] == "Gameplay Programming"][0]
        self.assertEqual(cell["n"], 1)
        self.assertEqual(cell["n_excluded"], 1)

    def test_an_all_faulted_cell_still_appears(self):
        """n == 0 but the cell is not empty — it must not vanish from the report."""
        cmp = self._cmp(self.d, ["HARNESS-ERROR", "TIMEOUT"])
        cells = [c for c in to_dict(cmp)["cells"]
                 if c["capability"] == "Gameplay Programming"]
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]["n"], 0)
        self.assertEqual(cells[0]["n_excluded"], 2)

    def test_cost_still_accrues_on_a_faulted_run(self):
        """A run that died on a harness fault still spent real money."""
        gp = _task_md(self.d, "gp1", "Gameplay Programming")
        paths = [
            _result(self.d / "r0", product="claude-p:opus", task_md=gp, overall="PASS", cost=1.0),
            _result(self.d / "r1", product="claude-p:opus", task_md=gp,
                    overall="HARNESS-ERROR", cost=2.0),
        ]
        cmp = aggregate([load_result(p) for p in paths])
        cell = cmp.cell("Gameplay Programming", "claude-p:opus")
        self.assertEqual(cell.n, 1)
        self.assertEqual(cell.cost, 3.0)


# ---------------------------------------------------------------------------
# Which task is a run? Delegated to tools/runlib/run_identity.py since
# 2026-08-19. Every test below goes RED against this file's previous answer,
# ``Path(task).stem``, which returned the literal string "task" for all 87
# recorded run paths (every one ends in ``.../<id>/task.md``) -- i.e. one
# product's whole run set collapsed into a single task cell.
# ---------------------------------------------------------------------------
class TestTaskIdentity(unittest.TestCase):
    CAP = "Gameplay Programming"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for basket, tid in (("cpp", "gp-alpha"), ("bp", "gp-beta")):
            d = self.root / "tasks" / basket / tid
            d.mkdir(parents=True)
            (d / "task.md").write_text(
                "## Task ID and metadata\n\n- task_id: %s\n- capability_bucket: %s\n"
                % (tid, self.CAP), encoding="utf-8")
        self._repo = cp._REPO
        cp._REPO = self.root
        self.runs = self.root / "runs"
        self.runs.mkdir()

    def tearDown(self):
        cp._REPO = self._repo
        self._tmp.cleanup()

    def _write(self, name, payload):
        p = self.runs / ("%s.json" % name)
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_folder_form_path_is_the_task_id_not_the_word_task(self):
        rel = "tasks/cpp/gp-alpha/task.md"
        r = load_result(self._write("r0", {
            "model": "claude-p:opus", "task": rel, "overall": "PASS"}))
        self.assertEqual(r.task_id, "gp-alpha")
        self.assertNotEqual(r.task_id, "task")
        self.assertEqual(r.capability, self.CAP)

    def test_two_tasks_do_not_share_one_cell(self):
        recs = [load_result(self._write("r%d" % i, {
                    "model": "claude-p:opus", "overall": "PASS",
                    "task": "tasks/%s/%s/task.md" % (b, t)}))
                for i, (b, t) in enumerate((("cpp", "gp-alpha"), ("bp", "gp-beta")))]
        cmp = aggregate(recs)
        self.assertEqual(sorted(cmp.task_ids), ["gp-alpha", "gp-beta"])
        self.assertEqual(len({k[0] for k in cmp.task_cells}), 2)

    def test_windows_and_posix_paths_of_one_task_agree(self):
        win = _B.join(["C:", "cb", "bench-tree", "tasks", "cpp", "gp-alpha", "task.md"])
        a = load_result(self._write("rw", {"model": "claude-p:opus", "task": win,
                                           "overall": "PASS"}))
        b = load_result(self._write("rp", {
            "model": "claude-p:opus", "overall": "PASS",
            "task": "/c/cb/bench-tree/tasks/cpp/gp-alpha/task.md"}))
        self.assertEqual(a.task_id, b.task_id)
        self.assertEqual(a.task_id, "gp-alpha")
        self.assertEqual(len({k[0] for k in aggregate([a, b]).task_cells}), 1)

    def test_bare_task_id_shape_resolves(self):
        """aura_rig/run_graded.py writes task_id and NO task key at all."""
        r = load_result(self._write("r0", {
            "model": "aura-product:x", "task_id": "gp-beta", "overall": "PASS"}))
        self.assertEqual(r.task_id, "gp-beta")
        # ...and its capability comes from the spec that id resolves to, so the
        # arm does not land in one "uncategorized" bucket.
        self.assertEqual(r.capability, self.CAP)

    def test_set_qualified_task_id_shape_resolves(self):
        r = load_result(self._write("r0", {
            "model": "aura-product:x", "task_id": "bp/gp-beta", "overall": "PASS"}))
        self.assertEqual(r.task_id, "gp-beta")
        self.assertEqual(r.capability, self.CAP)

    def test_a_record_naming_no_task_is_visibly_unknown(self):
        r = load_result(self._write("r0", {"model": "aura-product:x",
                                           "overall": "PASS"}))
        self.assertEqual(r.task_id, "UNKNOWN")
        self.assertEqual(r.capability, "uncategorized")

    def test_unknown_runs_do_not_merge_into_a_real_task(self):
        good = load_result(self._write("r0", {
            "model": "aura-product:x", "task_id": "gp-alpha", "overall": "PASS"}))
        blank = load_result(self._write("r1", {
            "model": "aura-product:x", "overall": "FAIL"}))
        cmp = aggregate([good, blank])
        self.assertEqual(sorted(cmp.task_ids), ["UNKNOWN", "gp-alpha"])


# The ``unittest.main()`` entry point belongs at the END of the file. It used to
# sit mid-file (before TestHarnessFaultsLeaveTheDenominator), which meant a
# direct ``python test_compare.py`` ran only the classes defined ABOVE it and
# reported OK — a test file that silently skipped its own later half.
if __name__ == "__main__":
    unittest.main()
