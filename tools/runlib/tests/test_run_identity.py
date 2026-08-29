r"""The task-identity rule has ONE implementation. This test is why it stays one.

Before 2026-08-19 three readers each answered "which task is this run?" their own
way, and on the SAME 87 run records (the ``result.json`` under
``C:/cb/bench-tree/runs`` plus this repo's ``runs/``) they gave three answers:

    tools/compare/compare_products.py:106  Path(task).stem  ->  2 distinct ids
    tools/dashboard/collect.py:433  PurePosixPath(...).stem -> 18 distinct ids,
                                    each a whole Windows path; 0 joined tasks/

None of them made a run FAIL. They made the numbers wrong quietly, which is
worse, and nothing detected it because each copy looked correct in isolation.

The durable defence is that there is now nothing to keep in lockstep: the three
readers IMPORT ``run_identity`` (``TestNoSecondImplementation`` below asserts
that they still do, and that the three retired spellings have not come back).

Run from the repo root::

    python -m unittest discover -s tools/runlib/tests -t .
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RUNLIB = _HERE.parent
_REPO = _RUNLIB.parents[1]
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))

import run_identity as ri  # noqa: E402

B = chr(92)  # a literal backslash, spelled so no editor/heredoc can eat it


def _tree(root: Path) -> None:
    """A miniature task tree: one folder-form spec in each of two baskets."""
    for basket, tid in (("cpp", "t-alpha"), ("bp", "t-beta"), ("python", "t-gamma")):
        d = root / "tasks" / basket / tid
        d.mkdir(parents=True)
        (d / "task.md").write_text("- task_id: %s\n" % tid, encoding="utf-8")


class TestBothWriterShapes(unittest.TestCase):
    """Requirement: accept a "task" path AND a bare "task_id" — two writers
    exist (run.py and aura_rig/run_graded.py) and neither may be changed."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_windows_path_resolves(self):
        rec = {"task": B.join(["C:", "cb", "bench-tree", "tasks", "bp",
                               "t-beta", "task.md"])}
        got = ri.identify(rec, self.root)
        self.assertEqual((got.task_id, got.basket, got.source),
                         ("t-beta", "bp", "task"))

    def test_posix_path_resolves_identically(self):
        win = {"task": B.join(["C:", "cb", "bench-tree", "tasks", "bp",
                               "t-beta", "task.md"])}
        posix = {"task": "/c/cb/bench-tree/tasks/bp/t-beta/task.md"}
        a, b = ri.identify(win, self.root), ri.identify(posix, self.root)
        self.assertEqual((a.task_id, a.basket), (b.task_id, b.basket))
        self.assertEqual(a.task_id, "t-beta")

    def test_relative_path_resolves(self):
        rec = {"task": B.join(["tasks", "cpp", "t-alpha", "task.md"])}
        self.assertEqual(ri.identify(rec, self.root).task_id, "t-alpha")
        self.assertEqual(ri.identify(rec, self.root).basket, "cpp")

    def test_legacy_flat_spec_path(self):
        flat = self.root / "tasks" / "cpp" / "t-flat.md"
        flat.write_text("- task_id: t-flat\n", encoding="utf-8")
        got = ri.identify({"task": "tasks/cpp/t-flat.md"}, self.root)
        self.assertEqual((got.task_id, got.basket), ("t-flat", "cpp"))

    def test_bare_task_id_shape(self):
        """The aura-product shape: task_id and NO task key at all."""
        got = ri.identify({"task_id": "t-beta"}, self.root)
        self.assertEqual((got.task_id, got.basket, got.source),
                         ("t-beta", "bp", "task_id"))

    def test_set_qualified_task_id_both_separators(self):
        for value in ("bp/t-beta", "bp" + B + "t-beta"):
            got = ri.identify({"task_id": value}, self.root)
            self.assertEqual((got.task_id, got.basket), ("t-beta", "bp"), value)

    def test_trailing_separator_and_no_task_md(self):
        for value in ("tasks/bp/t-beta", "tasks/bp/t-beta/"):
            got = ri.identify({"task": value}, self.root)
            self.assertEqual((got.task_id, got.basket), ("t-beta", "bp"), value)


class TestFailsClosed(unittest.TestCase):
    """Requirement: an unknown task must NOT silently become "cpp".

    The retired private ``_basket_of("")`` spelling returned "cpp" with confidence:
    an empty id made the probe ``(REPO/"tasks"/b/"")`` stat the basket DIRECTORY,
    which exists. A basket is either measured or UNKNOWN — never inferred.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_and_missing_fields(self):
        for rec in ({}, {"task": ""}, {"task": None}, {"task_id": ""},
                    {"task": "", "task_id": ""}):
            got = ri.identify(rec, self.root)
            self.assertEqual(got.task_id, ri.UNKNOWN_TASK_ID, rec)
            self.assertEqual(got.basket, ri.UNKNOWN_BASKET, rec)
            self.assertNotIn(got.basket, ri.KNOWN_BASKETS, rec)

    def test_empty_basket_probe_is_never_a_directory_hit(self):
        """The exact retired bug, pinned: tasks/cpp/ IS a directory."""
        self.assertTrue((self.root / "tasks" / "cpp").is_dir())
        self.assertEqual(ri.basket_from_tree("", self.root), ri.UNKNOWN_BASKET)
        self.assertEqual(ri.basket_from_tree(ri.UNKNOWN_TASK_ID, self.root),
                         ri.UNKNOWN_BASKET)

    def test_bare_spec_filename_is_not_an_id(self):
        for value in ("task.md", "tasks", "tasks/", ".", "C:"):
            got = ri.identify({"task": value}, self.root)
            self.assertEqual(got.task_id, ri.UNKNOWN_TASK_ID, value)

    def test_unknown_id_keeps_its_id_but_not_a_basket(self):
        got = ri.identify({"task_id": "t-never-existed"}, self.root)
        self.assertEqual(got.task_id, "t-never-existed")
        self.assertEqual(got.basket, ri.UNKNOWN_BASKET)

    def test_ambiguous_id_refuses_a_basket(self):
        dup = self.root / "tasks" / "python" / "t-alpha"
        dup.mkdir(parents=True)
        (dup / "task.md").write_text("x", encoding="utf-8")
        got = ri.identify({"task_id": "t-alpha"}, self.root)
        self.assertEqual(got.task_id, "t-alpha")
        self.assertEqual(got.basket, ri.UNKNOWN_BASKET)
        self.assertIsNone(ri.spec_path("t-alpha", self.root))

    def test_no_repo_root_means_unknown_not_a_guess(self):
        got = ri.identify({"task_id": "t-beta"})
        self.assertEqual(got.task_id, "t-beta")
        self.assertEqual(got.basket, ri.UNKNOWN_BASKET)

    def test_non_mapping_record(self):
        for rec in (None, [], "gp-x", 7):
            self.assertEqual(ri.identify(rec, self.root), ri.UNIDENTIFIED)

    def test_a_directory_that_is_not_a_set_is_not_a_basket(self):
        """".../scratch/<id>/task.md" must not report basket "scratch"."""
        rec = {"task": "/tmp/scratch/t-beta/task.md"}
        got = ri.identify(rec, self.root)
        self.assertEqual(got.task_id, "t-beta")
        self.assertEqual(got.basket, "bp")   # from the TREE, not from "scratch"
        rec2 = {"task": "/tmp/scratch/t-never-existed/task.md"}
        self.assertEqual(ri.identify(rec2, self.root).basket, ri.UNKNOWN_BASKET)


class TestBasketProvenance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_basket_wins_over_this_tree(self):
        """A run graded in ANOTHER checkout keeps that checkout's surface.

        Every bench-tree run's path points at C:/cb/bench-tree/tasks/..., a tree this
        process cannot stat. The path IS the measurement; a local lookup would
        silently relabel a run that never touched this tree.
        """
        rec = {"task": "/elsewhere/tasks/python/t-beta/task.md"}
        self.assertEqual(ri.identify(rec, self.root).basket, "python")

    def test_a_set_outside_the_three_is_reported_verbatim(self):
        rec = {"task": "/x/tasks/craftbench-public/t-public/task.md"}
        got = ri.identify(rec, self.root)
        self.assertEqual((got.task_id, got.basket), ("t-public", "craftbench-public"))
        self.assertNotIn(got.basket, ri.KNOWN_BASKETS)

    def test_task_path_wins_the_id_and_task_id_can_fill_the_basket(self):
        rec = {"task": "/nowhere/t-beta/task.md", "task_id": "bp/t-beta"}
        got = ri.identify(rec, self.root)
        self.assertEqual((got.task_id, got.basket, got.source),
                         ("t-beta", "bp", "task"))

    def test_disagreeing_fields_are_not_reconciled(self):
        """Two fields naming two tasks: take the trusted one, borrow nothing."""
        rec = {"task": "/nowhere/t-zeta/task.md", "task_id": "bp/t-beta"}
        got = ri.identify(rec, self.root)
        self.assertEqual(got.task_id, "t-zeta")
        self.assertEqual(got.basket, ri.UNKNOWN_BASKET)


class TestJoinAndOrder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_spec_path_joins_the_task_tree(self):
        self.assertEqual(ri.spec_path("t-beta", self.root),
                         self.root / "tasks" / "bp" / "t-beta" / "task.md")
        self.assertEqual(ri.spec_path("bp/t-beta", self.root),
                         self.root / "tasks" / "bp" / "t-beta" / "task.md")

    def test_spec_path_refuses_the_empty_and_the_absent(self):
        for value in ("", "task.md", "tasks", "t-never-existed", ri.UNKNOWN_TASK_ID):
            self.assertIsNone(ri.spec_path(value, self.root), value)
        self.assertIsNone(ri.spec_path("t-beta", None))

    def test_basket_order_shows_unknown_instead_of_dropping_it(self):
        order = ri.basket_order({"cpp", "UNKNOWN", "craftbench-public"})
        self.assertEqual(order, ["cpp", "bp", "python", "craftbench-public",
                                 "UNKNOWN"])
        self.assertEqual(ri.basket_order(set()), list(ri.KNOWN_BASKETS))
        self.assertNotIn("UNKNOWN", ri.basket_order({"cpp"}))


class TestOneCellPerTask(unittest.TestCase):
    """The headline defect, at the level the paper's cells are keyed.

    A results aggregator keys on (task_id, arm, model, basket). With the
    retired rules an aura-product epoch of N tasks x R reps produced ONE cell
    (id "unknown", basket "cpp"); the cost rule's contingency reads that
    arm's bp numbers, which came out as zero runs.
    """

    def test_n_tasks_stay_n_cells(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _tree(root)
            recs = [{"task_id": t, "model": "aura-product"}
                    for t in ("t-alpha", "t-beta", "t-gamma")] * 3
            keys = {(ri.identify(r, root).task_id, ri.identify(r, root).basket)
                    for r in recs}
            self.assertEqual(len(keys), 3)
            self.assertEqual(keys, {("t-alpha", "cpp"), ("t-beta", "bp"),
                                    ("t-gamma", "python")})


class TestNoSecondImplementation(unittest.TestCase):
    """The anti-duplication guard: the readers must DELEGATE, not re-derive.

    A corrected sixth spelling is the disease, not the cure. This asserts each
    reader imports ``run_identity`` and that none of the three retired spellings
    has grown back. It parses source rather than importing the modules, so it
    stays cheap and needs nothing on sys.path.
    """

    READERS = (
        Path("tools") / "compare" / "compare_products.py",
        Path("tools") / "dashboard" / "collect.py",
    )

    #: Retired spellings, verbatim. Each was one reader's private answer.
    RETIRED = (
        "PurePosixPath",          # dashboard: never splits a Windows path
        "def _task_id(",          # a reader's private id spelling
        "def _basket_of(",        # a reader's confident "cpp"
    )

    def _source(self, rel: Path) -> str:
        p = _REPO / rel
        self.assertTrue(p.is_file(), "reader moved: %s" % rel)
        return p.read_text(encoding="utf-8")

    def test_every_reader_imports_the_one_implementation(self):
        for rel in self.READERS:
            src = self._source(rel)
            names = set()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.ImportFrom) and node.module == "run_identity":
                    names.update(a.asname or a.name for a in node.names)
                elif isinstance(node, ast.Import):
                    names.update(a.asname or a.name for a in node.names
                                 if a.name == "run_identity")
            self.assertTrue(names, "%s does not import run_identity" % rel)

    def test_no_retired_spelling_came_back(self):
        for rel in self.READERS:
            src = self._source(rel)
            for spelling in self.RETIRED:
                # Comments are allowed to NAME the retired rule (they explain
                # why it was removed); only live code must be free of it.
                code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
                self.assertNotIn(spelling, code,
                                 "%s re-implements %r" % (rel, spelling))

    def test_task_stem_is_not_recomputed(self):
        """``Path(task).stem`` returned "task" for all 87 recorded paths."""
        for rel in self.READERS:
            code = "\n".join(line.split("#", 1)[0]
                             for line in self._source(rel).splitlines())
            self.assertNotIn('Path(task).stem', code, rel)
            self.assertNotIn('get("task", "")).stem', code, rel)

    def test_the_one_implementation_is_stdlib_only(self):
        """It is imported by three tools that must run from a bare checkout."""
        src = (_RUNLIB / "run_identity.py").read_text(encoding="utf-8")
        mods = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
        self.assertLessEqual(mods, {"__future__", "pathlib", "typing"}, sorted(mods))


class TestAgainstTheRealCorpus(unittest.TestCase):
    """A smoke pass over whatever runs are actually on disk, if any.

    Skips when the tree has no runs (a fresh clone, CI) rather than asserting on
    an empty set — a check that passes because it found nothing is not a check.
    """

    def test_every_recorded_task_field_resolves_or_says_it_cannot(self):
        runs = _REPO / "runs"
        records = []
        if runs.is_dir():
            for f in list(runs.glob("*/*/result.json"))[:200]:
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(d, dict) and str(d.get("task") or ""):
                    records.append(d)
        if not records:
            self.skipTest("no run records with a task path in this tree")
        for d in records:
            got = ri.identify(d, _REPO)
            self.assertTrue(got.known, d.get("task"))
            self.assertNotEqual(got.task_id, "task", d.get("task"))
            self.assertNotIn(B, got.task_id, d.get("task"))
            self.assertNotIn("/", got.task_id, d.get("task"))


if __name__ == "__main__":
    unittest.main()


class SurfaceVsBasket(unittest.TestCase):
    """ri.surface_of() answers "what did the agent write", which stopped being the
    same question as "which folder holds the spec" once tasks/craftbench-public/
    (keyed on DISCLOSURE) held tasks of both surfaces.

    These are inverted on purpose: if someone re-derives the reported surface
    column from the basket again, the second and fourth cases fail.
    """

    def test_id_suffix_wins_over_a_wrong_basket(self):
        self.assertEqual(ri.surface_of("gp-glide-stamina-bp", "cpp"), "bp")
        self.assertEqual(ri.surface_of("t1-screen-tint-cpp", "bp"), "cpp")

    def test_a_set_name_is_never_returned_as_a_surface(self):
        # The old behaviour folded an unrecognised set into "cpp" with full
        # confidence. A visible gap is the only honest answer.
        self.assertEqual(ri.surface_of("t2-collect-then-exit", "craftbench-public"),
                         ri.UNKNOWN_BASKET)

    def test_basket_answers_only_when_the_id_is_silent(self):
        self.assertEqual(ri.surface_of("t0-sanity-log-on-beginplay", "cpp"), "cpp")
        self.assertEqual(ri.surface_of("kp-anim-track-bake", "python"), "python")

    def test_no_id_and_no_usable_basket_is_unknown_not_cpp(self):
        self.assertEqual(ri.surface_of("", ""), ri.UNKNOWN_BASKET)
        self.assertEqual(ri.surface_of(ri.UNKNOWN_TASK_ID, "craftbench-public"),
                         ri.UNKNOWN_BASKET)

    def test_a_set_qualified_locator_still_reads_its_suffix(self):
        self.assertEqual(ri.surface_of("bp/gp-poison-dot-stack-bp", "bp"), "bp")
        self.assertEqual(ri.surface_of("tasks/cpp/t2-race-clock-cpp",
                                    "cpp"), "cpp")
