"""Unit tests for aura_rig.tasks — task discovery, parsing, and set-aware resolution.

Pure-offline: builds a throwaway tasks/ tree in a temp dir (never the real repo), so
it's deterministic and independent of the live task set.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_rig import tasks  # noqa: E402

_TASK_MD = """# {id}

## Task ID and metadata
- id: {id}

## Primary concept
{concept}

## Prompt given to the agent
{prompt}

## Verifier layers used
{layers}

## Anti-gaming notes
- none
"""


def _write(p: Path, **kw):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_TASK_MD.format(**kw), encoding="utf-8")


def _mk_repo(root: Path) -> Path:
    """A tasks tree: root {alpha, dup}, concept-1 {beta, dup}, internal-1 {gamma},
    plus a README + CATALOG that must be skipped, plus folder-form tasks:
    flagship/{delta}, concept-1/{epsilon} (folder form beside legacy files)."""
    t = root / "tasks"
    _write(t / "alpha.md", id="alpha", concept="root alpha concept", prompt="do alpha now", layers="L1, L2")
    _write(t / "dup.md", id="dup", concept="root dup concept", prompt="root dup prompt", layers="L1")
    _write(t / "concept-1" / "beta.md", id="beta", concept="beta concept", prompt="do beta now", layers="L2")
    _write(t / "concept-1" / "dup.md", id="dup", concept="set dup concept", prompt="set dup prompt", layers="L2")
    _write(t / "internal-1" / "gamma.md", id="gamma", concept="gamma concept", prompt="do gamma", layers="L1, L2I")
    _write(t / "flagship" / "delta" / "task.md", id="delta", concept="delta concept",
           prompt="do delta now", layers="L1, L2")
    _write(t / "concept-1" / "epsilon" / "task.md", id="epsilon", concept="eps concept",
           prompt="do epsilon", layers="L2I")
    (t / "concept-1" / "README.md").write_text("# concept-1 set\n", encoding="utf-8")
    (t / "CATALOG.md").write_text("# catalog\n", encoding="utf-8")
    return root


class TestDiscover(unittest.TestCase):
    def test_sets_order_and_counts(self):
        with tempfile.TemporaryDirectory() as td:
            sets = tasks.discover(_mk_repo(Path(td)))
            self.assertEqual(list(sets.keys()),
                             ["root", "concept-1", "flagship", "internal-1"])
            self.assertEqual([t.id for t in sets["root"]], ["alpha", "dup"])
            self.assertEqual([t.id for t in sets["concept-1"]], ["beta", "dup", "epsilon"])
            self.assertEqual(len(sets["internal-1"]), 1)

    def test_folder_form_discovered_with_dir_name_id(self):
        with tempfile.TemporaryDirectory() as td:
            sets = tasks.discover(_mk_repo(Path(td)))
            delta = sets["flagship"][0]
            self.assertEqual((delta.id, delta.set_name, delta.title), ("delta", "flagship", "delta"))
            self.assertEqual(delta.path.name, "task.md")
            self.assertEqual(delta.concept, "delta concept")

    def test_folder_wins_over_sibling_flat_dup(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            # Same id in one set, both shapes: the folder form must win.
            _write(repo / "tasks" / "concept-1" / "beta" / "task.md",
                   id="beta", concept="folder beta", prompt="p", layers="L1")
            sets = tasks.discover(repo)
            beta = [t for t in sets["concept-1"] if t.id == "beta"]
            self.assertEqual(len(beta), 1)
            self.assertEqual(beta[0].path.name, "task.md")
            self.assertEqual(
                tasks.resolve_task_path(repo, "concept-1/beta"),
                repo / "tasks" / "concept-1" / "beta" / "task.md")

    def test_stray_task_md_directly_in_set_dir_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            _write(repo / "tasks" / "concept-1" / "task.md",
                   id="stray", concept="c", prompt="p", layers="L1")
            ids = [t.id for ts in tasks.discover(repo).values() for t in ts]
            self.assertNotIn("task", ids)
            self.assertNotIn("stray", ids)

    def test_readme_and_catalog_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            sets = tasks.discover(_mk_repo(Path(td)))
            ids = [t.id for ts in sets.values() for t in ts]
            self.assertNotIn("README", ids)
            self.assertNotIn("CATALOG", ids)

    def test_parse_fields(self):
        with tempfile.TemporaryDirectory() as td:
            beta = tasks.discover(_mk_repo(Path(td)))["concept-1"][0]
            self.assertEqual((beta.id, beta.set_name, beta.title), ("beta", "concept-1", "beta"))
            self.assertEqual(beta.concept, "beta concept")
            self.assertEqual(beta.layers, "L2")
            self.assertIn("do beta now", beta.prompt_preview)

    def test_missing_tasks_dir_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(tasks.discover(Path(td)), {})

    def test_front_matter_spec_layers(self):
        # Spec v2: layers come from the front matter via the single parser
        # (spec.py) — not from any hardcoded H2 heading.
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            p = repo / "tasks" / "flagship" / "fm-task" / "task.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                "---\n"
                "id: fm-task\n"
                "layers: [L1, L2I]\n"
                "introspect: [fm_task.py]\n"
                "---\n\n"
                "# fm-task\n\n"
                "## Prompt given to the agent\n"
                "do the fm thing\n",
                encoding="utf-8",
            )
            fm = [t for t in tasks.discover(repo)["flagship"] if t.id == "fm-task"][0]
            self.assertEqual(fm.layers, "L1, L2I")
            self.assertIn("do the fm thing", fm.prompt_preview)

    def test_unified_verifier_layers_block(self):
        # Legacy spec with the unified "## Verifier layers" heading (NOT the
        # old "## Verifier layers used") must still show correct layers.
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            p = repo / "tasks" / "flagship" / "uni-task" / "task.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                "# uni-task\n\n"
                "## Prompt given to the agent\n"
                "do uni\n\n"
                "## Verifier layers\n\n"
                "- L1\n"
                "- L2 (fixtures: L_Uni :: AUniFunctionalTest)\n",
                encoding="utf-8",
            )
            uni = [t for t in tasks.discover(repo)["flagship"] if t.id == "uni-task"][0]
            self.assertEqual(uni.layers, "L1, L2")


class TestResolve(unittest.TestCase):
    def test_root_first_wins_over_subdir_dup(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            self.assertEqual(tasks.resolve_task_path(repo, "dup"), repo / "tasks" / "dup.md")

    def test_unique_subdir_match(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            self.assertEqual(tasks.resolve_task_path(repo, "beta"),
                             repo / "tasks" / "concept-1" / "beta.md")

    def test_set_qualified(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            self.assertEqual(tasks.resolve_task_path(repo, "concept-1/dup"),
                             repo / "tasks" / "concept-1" / "dup.md")

    def test_missing_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(tasks.resolve_task_path(_mk_repo(Path(td)), "nope"))

    def test_ambiguous_subdir_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write(repo / "tasks" / "a" / "twin.md", id="twin", concept="c", prompt="p", layers="L1")
            _write(repo / "tasks" / "b" / "twin.md", id="twin", concept="c", prompt="p", layers="L1")
            self.assertIsNone(tasks.resolve_task_path(repo, "twin"))

    def test_trailing_md_and_backslash(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            self.assertEqual(tasks.resolve_task_path(repo, "alpha.md"), repo / "tasks" / "alpha.md")
            self.assertEqual(tasks.resolve_task_path(repo, "concept-1\\beta"),
                             repo / "tasks" / "concept-1" / "beta.md")

    def test_folder_form_bare_and_set_qualified(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            want = repo / "tasks" / "flagship" / "delta" / "task.md"
            self.assertEqual(tasks.resolve_task_path(repo, "delta"), want)
            self.assertEqual(tasks.resolve_task_path(repo, "flagship/delta"), want)

    def test_cross_set_ambiguity_lists_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write(repo / "tasks" / "a" / "twin" / "task.md", id="twin", concept="c", prompt="p", layers="L1")
            _write(repo / "tasks" / "b" / "twin.md", id="twin", concept="c", prompt="p", layers="L1")
            self.assertIsNone(tasks.resolve_task_path(repo, "twin"))
            cands = tasks.resolve_task_candidates(repo, "twin")
            self.assertEqual(
                cands,
                [repo / "tasks" / "a" / "twin" / "task.md", repo / "tasks" / "b" / "twin.md"])


class TestSuggestionsAndErrors(unittest.TestCase):
    """known_task_ids / suggest_task_ids / resolution_error — the shared
    did-you-mean surface every failed resolve prints (cb eval routes and the
    resolve CLI)."""

    def test_known_task_ids_display_forms(self):
        with tempfile.TemporaryDirectory() as td:
            ids = tasks.known_task_ids(_mk_repo(Path(td)))
            self.assertIn("alpha", ids)            # root -> bare
            self.assertIn("delta", ids)            # folder form, unique -> bare
            self.assertIn("dup", ids)              # duplicated, root wins -> bare
            self.assertIn("concept-1/dup", ids)    # the shadowed set twin -> qualified
            self.assertNotIn("flagship/delta", ids)

    def test_suggests_the_o_for_zero_typo(self):
        # THE incident class (FAILURE-LOG 2026-07-21): 'to-…' typed for 't0-…'.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write(repo / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "task.md",
                   id="t0-sanity-log-on-beginplay", concept="c", prompt="p", layers="L1")
            self.assertEqual(
                tasks.suggest_task_ids(repo, "to-sanity-log-on-beginplay"),
                ["t0-sanity-log-on-beginplay"])

    def test_resolution_error_missing_has_did_you_mean_and_browse_hint(self):
        with tempfile.TemporaryDirectory() as td:
            msg = tasks.resolution_error(_mk_repo(Path(td)), "alpah")
            self.assertIn("task not found", msg)
            self.assertIn("did you mean", msg)
            self.assertIn("'alpha'", msg)
            self.assertIn("cb tasks", msg)

    def test_resolution_error_no_close_match_still_helpful(self):
        with tempfile.TemporaryDirectory() as td:
            msg = tasks.resolution_error(_mk_repo(Path(td)), "zzzz-qq-xx")
            self.assertIn("task not found", msg)
            self.assertNotIn("did you mean", msg)
            self.assertIn("cb tasks", msg)

    def test_resolution_error_ambiguous_lists_qualified_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write(repo / "tasks" / "a" / "twin" / "task.md", id="twin", concept="c", prompt="p", layers="L1")
            _write(repo / "tasks" / "b" / "twin.md", id="twin", concept="c", prompt="p", layers="L1")
            msg = tasks.resolution_error(repo, "twin")
            self.assertIn("ambiguous", msg)
            self.assertIn("a/twin", msg)
            self.assertIn("b/twin", msg)


class TestArtifactDirs(unittest.TestCase):
    def test_task_id_for_and_bare_id(self):
        self.assertEqual(tasks.task_id_for(Path("tasks/flagship/delta/task.md")), "delta")
        self.assertEqual(tasks.task_id_for(Path("tasks/concept-1/beta.md")), "beta")
        self.assertEqual(tasks.bare_id("bp-g2/gp-x"), "gp-x")
        self.assertEqual(tasks.bare_id("bp-g2\\gp-x"), "gp-x")
        self.assertEqual(tasks.bare_id("gp-x"), "gp-x")

    def test_folder_local_reference_wins_over_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            local = repo / "tasks" / "flagship" / "delta" / "reference"
            legacy = repo / "tests" / "reference-solutions" / "delta"
            local.mkdir(parents=True)
            legacy.mkdir(parents=True)
            self.assertEqual(tasks.reference_dir(repo, "delta"), local)
            self.assertEqual(tasks.reference_dir(repo, "flagship/delta"), local)

    def test_legacy_reference_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            legacy = repo / "tests" / "reference-solutions" / "beta"
            legacy.mkdir(parents=True)
            self.assertEqual(tasks.reference_dir(repo, "beta"), legacy)
            self.assertEqual(tasks.reference_dir(repo, "concept-1/beta"), legacy)
            self.assertIsNone(tasks.reference_dir(repo, "gamma"))

    def test_discrimination_dir_both_shapes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td))
            local = repo / "tasks" / "flagship" / "delta" / "discrimination"
            local.mkdir(parents=True)
            self.assertEqual(tasks.discrimination_dir(repo, "delta"), local)
            legacy = repo / "tests" / "discrimination" / "gamma"
            legacy.mkdir(parents=True)
            self.assertEqual(tasks.discrimination_dir(repo, "gamma"), legacy)

    def test_task_dir(self):
        self.assertEqual(tasks.task_dir(Path("t/flagship/delta/task.md")),
                         Path("t/flagship/delta"))
        self.assertIsNone(tasks.task_dir(Path("t/concept-1/beta.md")))


if __name__ == "__main__":
    unittest.main()
