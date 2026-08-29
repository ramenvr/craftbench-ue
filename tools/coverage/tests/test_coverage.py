"""Unit tests for the CraftBench high-tier concept-coverage tool.

These tests must not require a UE installation and use only the Python
stdlib. They exercise, with tiny inline fixtures:

  - The task-spec parser that extracts the PRIMARY concept_id(s) from the
    normative ``## Primary concept`` H2 section (reusing the same H2 join-key
    convention as ``tools/verify-single/run_task.py``).
  - The concepts.csv loader (column names: concept_id, weight_tier
    high|medium|low|n/a, in_scope yes|no).
  - The coverage join: in_scope high-tier concepts -> referencing task(s),
    covered-vs-total counts, and the uncovered set.
  - The machine-readable JSON summary shape.

Run with the repo convention::

    python3 -m unittest discover -v tools/coverage/tests
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load the tool under test by file path (the package dir name "verify-single"
# in the sibling tool is not importable; we keep this tool import-by-path too
# so the test never depends on sys.path packaging tricks).
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_TOOL_PATH = _THIS_DIR.parent / "coverage.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("cb_coverage_under_test", _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


coverage = _load_tool()


# ---------------------------------------------------------------------------
# Tiny inline fixtures
# ---------------------------------------------------------------------------

# Mirrors the real concepts.csv header exactly (col order is incidental; we
# join by name, not position).
_FAKE_CONCEPTS_CSV = (
    "concept_id,concept_name,doc_url,doc_section,doc_depth,"
    "forum_mentions_12mo,weight_tier,in_scope,capability_bucket,notes\n"
    # in_scope high-tier, COVERED by a task
    "ps-actors,Actors,http://x,Programming,3,forum:>50,high,yes,Gameplay Programming,note\n"
    # in_scope high-tier, COVERED via a multi-id (+) task bullet
    "gas-abilities,Gameplay Ability System,http://x,GAS,3,forum:>50,high,yes,Gameplay Programming,note\n"
    # in_scope high-tier, NOT referenced by any task -> uncovered
    "behavior-trees,Behavior Trees,http://x,AI,3,forum:>50,high,yes,Gameplay Programming,note\n"
    # high-tier but OUT of scope -> excluded from the denominator entirely
    "deprecated-thing,Deprecated Thing,http://x,Old,1,forum:~0,high,no,Gameplay Programming,note\n"
    # medium-tier in_scope -> not a high-tier concept, excluded from denominator
    "material-instance-dynamic,MID,http://x,Materials,3,forum:>50,medium,yes,Technical Art,note\n"
    # the co-primary in the (+) bullet; in_scope high-tier, covered
    "ps-character-movement,Character Movement,http://x,Programming,3,forum:>50,high,yes,Gameplay Programming,note\n"
)

# A task referencing a single high-tier concept (canonical single bullet).
_TASK_PS_ACTORS = """# fake-actors

## Prompt given to the agent

do the thing

## Task ID and metadata

- task_id: fake-actors
- tier: T1

## Primary concept

- `ps-actors` — Actors
  (http://x)

## Prompt given to the agent

> do a thing
"""

# A task whose first Primary-concept bullet lists TWO concept_ids joined by
# `+` (mirrors tasks/gp-flight-mode.md). Both must count as referenced.
_TASK_FLIGHT = """# fake-flight

## Prompt given to the agent

do the thing

## Primary concept

- `gas-abilities` + `ps-character-movement` — GAS ability driving a
  CharacterMovement mode change
  (http://x)
"""

# A task referencing an in_scope MEDIUM concept and an advisory placeholder
# id that is NOT in the catalogue at all. Neither should appear in the
# high-tier coverage denominator; the unmatched id is reported separately.
_TASK_MEDIUM_AND_ADVISORY = """# fake-medium

## Prompt given to the agent

do the thing

## Primary concept

- `material-instance-dynamic` — MID (http://x)
"""

_TASK_ADVISORY_ONLY = """# fake-advisory

## Prompt given to the agent

do the thing

## Primary concept

- `project-onboarding-summary` — orienting a new session (Advisory; no class prescribed).
"""

# A malformed task with NO Primary concept section -> parser returns no ids
# (and must not raise).
_TASK_NO_CONCEPT = """# fake-broken

## Prompt given to the agent

do the thing

## Task ID and metadata

- task_id: fake-broken

## Prompt given to the agent

> nothing here
"""


class _TmpRepo:
    """Context-manager building a tiny throwaway repo layout on disk."""

    def __init__(self, csv_text: str, tasks: dict[str, str]):
        self._csv_text = csv_text
        self._tasks = tasks
        self._tmp: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        csv_path = root / "tools" / "coverage" / "concepts.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(self._csv_text, encoding="utf-8")
        tasks_dir = root / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        for rel, body in self._tasks.items():
            p = tasks_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        return root

    def __exit__(self, *exc):
        assert self._tmp is not None
        self._tmp.cleanup()
        return False


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestPrimaryConceptParser(unittest.TestCase):
    def test_single_bullet_yields_one_concept_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(_TASK_PS_ACTORS, encoding="utf-8")
            ids = coverage.parse_primary_concept_ids(p)
        self.assertEqual(ids, ["ps-actors"])

    def test_plus_joined_bullet_yields_all_concept_ids_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(_TASK_FLIGHT, encoding="utf-8")
            ids = coverage.parse_primary_concept_ids(p)
        # Both co-primaries are captured, first listed first.
        self.assertEqual(ids, ["gas-abilities", "ps-character-movement"])

    def test_missing_primary_concept_section_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(_TASK_NO_CONCEPT, encoding="utf-8")
            ids = coverage.parse_primary_concept_ids(p)
        self.assertEqual(ids, [])

    def test_only_first_bullet_of_section_is_read(self):
        # The kebab id must come from the FIRST list item, not from prose or
        # any later inline backticks (e.g. `AActor` mentions in the rationale).
        body = (
            "# x\n\n## Primary concept\n\n"
            "- `ps-actors` — Actors (http://x)\n\n"
            "`AActor` lifecycle is the load-bearing concept; see `gas-abilities`.\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(body, encoding="utf-8")
            ids = coverage.parse_primary_concept_ids(p)
        self.assertEqual(ids, ["ps-actors"])

    def test_h3_subheading_does_not_terminate_section(self):
        # _split_h2 must treat "### " as body, matching run_task.py.
        body = (
            "# x\n\n## Primary concept\n\n"
            "### sub\n\n- `ps-actors` — Actors (http://x)\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(body, encoding="utf-8")
            ids = coverage.parse_primary_concept_ids(p)
        self.assertEqual(ids, ["ps-actors"])


# ---------------------------------------------------------------------------
# CSV loader tests
# ---------------------------------------------------------------------------


class TestConceptsLoader(unittest.TestCase):
    def test_high_tier_in_scope_filter(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "concepts.csv"
            p.write_text(_FAKE_CONCEPTS_CSV, encoding="utf-8")
            high = coverage.load_high_tier_in_scope_concepts(p)
        # ps-actors, gas-abilities, behavior-trees, ps-character-movement.
        # NOT deprecated-thing (in_scope=no) and NOT material-instance-dynamic
        # (medium tier).
        self.assertEqual(
            set(high),
            {"ps-actors", "gas-abilities", "behavior-trees", "ps-character-movement"},
        )

    def test_loader_returns_concept_name_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "concepts.csv"
            p.write_text(_FAKE_CONCEPTS_CSV, encoding="utf-8")
            high = coverage.load_high_tier_in_scope_concepts(p)
        self.assertEqual(high["ps-actors"], "Actors")


# ---------------------------------------------------------------------------
# Coverage join tests
# ---------------------------------------------------------------------------


class TestCoverageJoin(unittest.TestCase):
    def _compute(self, tasks: dict[str, str]):
        repo = _TmpRepo(_FAKE_CONCEPTS_CSV, tasks)
        with repo as root:
            return coverage.compute_coverage(
                concepts_csv=root / "tools" / "coverage" / "concepts.csv",
                tasks_dir=root / "tasks",
            )

    def test_covered_and_uncovered_partition(self):
        result = self._compute(
            {
                "fake-actors.md": _TASK_PS_ACTORS,
                "fake-flight.md": _TASK_FLIGHT,
            }
        )
        # 4 high-tier in_scope total; ps-actors + gas-abilities +
        # ps-character-movement covered; behavior-trees uncovered.
        self.assertEqual(result["total_high_tier"], 4)
        self.assertEqual(result["covered_count"], 3)
        self.assertEqual(set(result["uncovered"]), {"behavior-trees"})
        self.assertEqual(
            set(result["covered"].keys()),
            {"ps-actors", "gas-abilities", "ps-character-movement"},
        )

    def test_task_attribution_lists_referencing_tasks(self):
        result = self._compute(
            {
                "fake-actors.md": _TASK_PS_ACTORS,
                "fake-flight.md": _TASK_FLIGHT,
            }
        )
        # ps-actors referenced by exactly fake-actors.
        self.assertEqual(result["covered"]["ps-actors"], ["fake-actors"])
        # gas-abilities referenced by fake-flight (the (+) bullet).
        self.assertEqual(result["covered"]["gas-abilities"], ["fake-flight"])

    def test_multiple_tasks_one_concept_are_all_attributed_sorted(self):
        result = self._compute(
            {
                "zeta.md": _TASK_PS_ACTORS.replace("fake-actors", "zeta"),
                "alpha.md": _TASK_PS_ACTORS.replace("fake-actors", "alpha"),
            }
        )
        # Both reference ps-actors; attribution sorted for determinism.
        self.assertEqual(result["covered"]["ps-actors"], ["alpha", "zeta"])

    def test_medium_and_advisory_ids_do_not_inflate_coverage(self):
        result = self._compute(
            {
                "fake-medium.md": _TASK_MEDIUM_AND_ADVISORY,
                "fake-advisory.md": _TASK_ADVISORY_ONLY,
            }
        )
        # Neither the medium concept nor the advisory placeholder is a
        # high-tier in_scope concept, so coverage stays at 0/4.
        self.assertEqual(result["covered_count"], 0)
        self.assertEqual(result["total_high_tier"], 4)
        # But unmatched (referenced-but-not-in-high-tier-catalogue) ids are
        # surfaced for transparency.
        self.assertIn("project-onboarding-summary", result["unmatched_referenced"])

    def test_recurses_into_subdirectories(self):
        result = self._compute(
            {
                "concept-1/spawn.md": _TASK_PS_ACTORS.replace("fake-actors", "spawn"),
            }
        )
        self.assertEqual(result["covered"]["ps-actors"], ["spawn"])

    def test_subdir_task_id_uses_filename_stem(self):
        # Attribution uses the task file's stem (its task_id), not its path.
        result = self._compute(
            {
                "internal-1/door.md": _TASK_PS_ACTORS.replace("fake-actors", "door"),
            }
        )
        self.assertEqual(result["covered"]["ps-actors"], ["door"])

    def test_non_spec_md_excluded_from_task_count(self):
        # CATALOG.md (the per-task TLDR index) and README.md are not task
        # specs and must not inflate task_count (the bug fixed 2026-06-11:
        # CATALOG.md was counted, reporting 69 instead of the honest 68).
        result = self._compute(
            {
                "fake-actors.md": _TASK_PS_ACTORS,
                "CATALOG.md": "# CraftBench Task Catalog\n\nnot a spec\n",
                "README.md": "# tasks\n",
                "internal-1/README.md": "# subset readme\n",
            }
        )
        self.assertEqual(result["task_count"], 1)

    def test_folder_form_task_id_from_dir_name(self):
        # 2026-07 dual layout: tasks/<set>/<id>/task.md attributes by the
        # DIR name (task_id_for), never the literal "task" stem.
        result = self._compute(
            {
                "bp-g2/spawn/task.md": _TASK_PS_ACTORS.replace("fake-actors", "spawn"),
            }
        )
        self.assertEqual(result["covered"]["ps-actors"], ["spawn"])
        self.assertEqual(result["task_count"], 1)

    def test_folder_form_sidecar_md_not_counted_as_specs(self):
        # A folder-form task dir co-locates non-spec markdown (notes.md,
        # discrimination/MATRIX.md, reference/ READMEs). Only task.md is the
        # spec — rglob-style enumeration would over-count these.
        result = self._compute(
            {
                "bp-g2/spawn/task.md": _TASK_PS_ACTORS.replace("fake-actors", "spawn"),
                "bp-g2/spawn/notes.md": "# scratch notes, not a spec\n",
                "bp-g2/spawn/discrimination/MATRIX.md": "| variant | verdict |\n",
                "bp-g2/spawn/reference/README.md": "# how to apply the reference\n",
            }
        )
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["covered"]["ps-actors"], ["spawn"])

    def test_stray_task_md_in_set_dir_is_skipped(self):
        # tasks/<set>/task.md is a MISPLACED folder-form spec (it belongs one
        # level down at tasks/<set>/<id>/task.md) — skipped, mirroring the
        # aura_rig.tasks _SKIP guard.
        result = self._compute(
            {
                "fake-actors.md": _TASK_PS_ACTORS,
                "bp-g2/task.md": _TASK_PS_ACTORS.replace("fake-actors", "stray"),
            }
        )
        self.assertEqual(result["task_count"], 1)


# ---------------------------------------------------------------------------
# task_id_for helper (dual-layout id derivation)
# ---------------------------------------------------------------------------


class TestTaskIdFor(unittest.TestCase):
    def test_folder_form_uses_parent_dir_name(self):
        self.assertEqual(
            coverage.task_id_for(Path("tasks/bp-g2/gp-x/task.md")), "gp-x"
        )

    def test_flat_form_uses_stem(self):
        self.assertEqual(coverage.task_id_for(Path("tasks/bp-g2/gp-x.md")), "gp-x")
        self.assertEqual(coverage.task_id_for(Path("tasks/gp-root.md")), "gp-root")


# ---------------------------------------------------------------------------
# JSON summary shape
# ---------------------------------------------------------------------------


class TestJsonSummary(unittest.TestCase):
    def test_summary_is_json_serializable_with_expected_keys(self):
        repo = _TmpRepo(
            _FAKE_CONCEPTS_CSV,
            {"fake-actors.md": _TASK_PS_ACTORS, "fake-flight.md": _TASK_FLIGHT},
        )
        with repo as root:
            result = coverage.compute_coverage(
                concepts_csv=root / "tools" / "coverage" / "concepts.csv",
                tasks_dir=root / "tasks",
            )
        blob = json.dumps(result)  # must not raise
        back = json.loads(blob)
        for key in (
            "total_high_tier",
            "covered_count",
            "covered",
            "uncovered",
            "unmatched_referenced",
        ):
            self.assertIn(key, back)
        # coverage_fraction convenience field, if present, must be sane.
        if "coverage_pct" in back:
            self.assertGreaterEqual(back["coverage_pct"], 0.0)
            self.assertLessEqual(back["coverage_pct"], 100.0)


# ---------------------------------------------------------------------------
# Per-doc-section rollup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
