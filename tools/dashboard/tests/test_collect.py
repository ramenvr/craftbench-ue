"""Unit tests for the dashboard data layer — SYNTHETIC tasks/ + runs/ in a tempdir.

Pure stdlib (``unittest``); no UE, no textual/fastapi, no real runs needed. These
assert that ``collect()`` parses tasks + runs correctly, text-parses the
``verifier_stdout.txt`` golden fixture into LayerResults, skips non-product
``result.json`` (no ``model``), tolerates ``verifier: null`` + missing cost, and
that the delegated matrix / head-to-head / coverage-gaps / latest-only views come
out right. The golden ``verifier_stdout.txt`` block PINS the current
``report.py::Report.render_text()`` format (open-risk #1) — if that rendering
changes, this fixture must be re-pinned and the parser updated.

Run from the repo root:

    python3 -m unittest tools.dashboard.tests.test_collect
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys as _sys

import tools.dashboard.collect  # noqa: F401  (ensure the submodule is in sys.modules)
from tools.dashboard.collect import (
    collect,
    layer_results_from_verifier,
    parse_run,
    parse_verifier_stdout,
)

# The package __init__ re-exports a ``collect`` FUNCTION, which shadows the
# ``collect`` submodule attribute on the package — so fetch the real module from
# sys.modules rather than via attribute access.
collect_mod = _sys.modules["tools.dashboard.collect"]

# A golden capture pinning report.render_text() — a PASS (L1) + a FAIL (L2) layer
# with bracket extras, log= suffix, and indented "- note" lines. Mirrors the real
# runs/<id>/verifier_stdout.txt byte-for-byte in structure.
GOLDEN_STDOUT = """\
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  task_id   : gp-spawn-sequence
  submission: c2b8eeece68e
  ue_version: 5.7.4
  host      : darwin/arm64
  duration  : 171.0s
  L1  : PASS    [exit=0, warn=2] log=/tmp/craftbench-x/out/l1_build.log
        - target CraftBenchTemplateEditor: exit 0 in 97.3s
        - target CraftBenchTemplate: exit 0 in 31.0s
  L2  : FAIL    [exit=3, tests=0/1] log=/tmp/craftbench-x/out/l2_pie.log
        - filter: Project.Functional Tests.Maps.L_SpawnSequence.SpawnSequenceFunctionalTest
        - result_source: json
  overall   : FAIL
json report: /tmp/craftbench-x/out/report.json
"""

# A passing-only golden with an L2I SKIPPED line, to exercise skip normalization.
GOLDEN_STDOUT_PASS = """\
CraftBench verifier report
  task_id   : mat-emissive-pulse
  L1  : PASS    [exit=0, warn=0] log=/tmp/x/l1.log
        - target CraftBenchTemplateEditor: exit 0 in 50.0s
  L2I : PASS    [tests=1/1]
        - introspect M_EmissivePulse: emissive pulse present
  overall   : PASS
"""


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _write_bytes(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


# An EMBEDDED verifier report dict (the report.py::Report.to_dict machine shape)
# whose layer story deliberately CONTRADICTS GOLDEN_STDOUT_PASS — so a test can
# prove which source won (the dict must be preferred over the text parse).
EMBEDDED_VERIFIER = {
    "task_id": "gp-alpha",
    "submission_sha": "deadbeefdead",
    "overall": "fail",
    "duration_seconds": 128.4,
    "ue_version": "5.8.0",
    "host": {"os": "windows", "arch": "x64"},
    "sandbox_violations": 0,
    "layers": {
        "L1": {
            "status": "pass",
            "exit_code": 0,
            "warnings_in_agent_files": 2,
            "log": "/tmp/x/l1_build.log",
            "notes": [
                "target CraftBenchTemplateEditor: exit 0 in 97.3s",
                "target CraftBenchTemplate: exit 0 in 31.0s",
            ],
        },
        "L2": {
            "status": "fail",
            "exit_code": 3,
            "tests_run": 1,
            "tests_passed": 0,
            "log": "/tmp/x/l2_pie.log",
            "notes": ["filter: Project.Functional Tests.Maps.L_Alpha.AlphaFunctionalTest"],
        },
        "L2I": {"status": "skipped"},
    },
}


def _task_md(
    name: str,
    capability: str,
    *,
    tier: str = "T1",
    set_name: str | None = "internal-1",
    layers_block: str = "## Verifier layers used\n\nL1, L2\n",
    prompt: str = "Do the thing.",
) -> str:
    set_line = f"- set: {set_name}\n" if set_name is not None else ""
    return (
        f"# {name}\n\n"
        "## Task ID and metadata\n\n"
        f"- task_id: {name}\n"
        f"- tier: {tier}\n"
        f"- capability_bucket: {capability}\n"
        f"{set_line}"
        "- substrate: template\n\n"
        "## Prompt given to the agent\n\n"
        f"> {prompt}\n\n"
        f"{layers_block}"
    )


def _result_json(
    run_id: str,
    task: str,
    model: str | None,
    overall: str,
    *,
    cost_usd: float | None = 0.5,
    duration_s: float | None = 100.0,
    summary: str = "did stuff",
    verifier=None,
    include_agent: bool = True,
) -> str:
    d: dict = {"run_id": run_id, "task": task, "overall": overall, "verifier": verifier}
    if model is not None:
        d["model"] = model
    if include_agent:
        agent: dict = {"exit_code": 0, "summary": summary}
        if duration_s is not None:
            agent["duration_s"] = duration_s
        if cost_usd is not None:
            agent["cost_usd"] = cost_usd
        d["agent"] = agent
    return json.dumps(d, indent=2)


class DashboardCollectBase(unittest.TestCase):
    """Builds a realistic synthetic repo under a tempdir and collects once."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        tasks = self.root / "tasks"
        runs = self.root / "runs"

        # --- tasks (top-level + a subdir draft that MUST be excluded) ---
        _write(tasks / "gp-alpha.md", _task_md("gp-alpha", "Gameplay Programming"))
        _write(
            tasks / "mat-beta.md",
            _task_md(
                "mat-beta",
                "Technical Art",
                set_name=None,  # the no-set case → set_name None
                layers_block="## Verifier layers\n\n- L1\n- L2I (scripts: x.py)\n",
            ),
        )
        _write(tasks / "doc-gamma.md", _task_md("doc-gamma", "Project Comprehension / Advisory"))
        # A set-dir spec with a COLLIDING id — enumeration is set-aware now, but
        # the dedupe rule says the root tasks/<id>.md WINS, so this one is shadowed.
        _write(tasks / "internal-1" / "gp-alpha.md", _task_md("gp-alpha", "WRONG-BUCKET"))

        # --- runs ---
        # gp-alpha run by two products → head-to-head + grounds Gameplay Programming.
        _write(
            runs / "20260602-100000-gp-alpha-claude-p-opus" / "result.json",
            _result_json("20260602-100000-gp-alpha-claude-p-opus", "tasks/gp-alpha.md",
                         "claude-p:opus", "PASS", cost_usd=0.30),
        )
        _write(
            runs / "20260602-100000-gp-alpha-claude-p-opus" / "verifier_stdout.txt",
            GOLDEN_STDOUT_PASS,
        )
        # Swept capture artifacts for the claude-p PASS run: two PNGs (written
        # out of order to prove sorting) + a non-PNG that must NOT be collected.
        art = runs / "20260602-100000-gp-alpha-claude-p-opus" / "artifacts"
        _write_bytes(art / "shot-0002.png", b"\x89PNG\r\n2")
        _write_bytes(art / "shot-0001.png", b"\x89PNG\r\n1")
        _write_bytes(art / "notes.txt", b"not an image")
        _write(
            runs / "20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "result.json",
            _result_json("20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6",
                         "tasks/gp-alpha.md", "aura-mcp:claude-sonnet-4-6", "FAIL", cost_usd=0.40),
        )
        _write(
            runs / "20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "verifier_stdout.txt",
            GOLDEN_STDOUT,
        )
        # A DUPLICATE (product, task) attempt — newer PASS replacing an earlier FAIL
        # under latest_only. Same product+task as the FAIL above.
        _write(
            runs / "20260602-120000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "result.json",
            _result_json("20260602-120000-gp-alpha-aura-mcp-claude-sonnet-4-6",
                         "tasks/gp-alpha.md", "aura-mcp:claude-sonnet-4-6", "PASS", cost_usd=0.45),
        )
        # mat-beta: single FAIL_NO_EDITS run with NO verifier_stdout.txt and NO cost.
        _write(
            runs / "20260602-130000-mat-beta-claude-p-opus" / "result.json",
            _result_json("20260602-130000-mat-beta-claude-p-opus", "tasks/mat-beta.md",
                         "claude-p:opus", "FAIL_NO_EDITS", cost_usd=None, include_agent=True),
        )
        # A May-27-style run with NO agent block at all (sparse telemetry).
        _write(
            runs / "20260527-090000-doc-gamma-claude-p-opus-4-7" / "result.json",
            _result_json("20260527-090000-doc-gamma-claude-p-opus-4-7", "tasks/doc-gamma.md",
                         "claude-p:opus-4-7", "FAIL_NO_EDITS", include_agent=False),
        )
        # NON-PRODUCT noise: aura-smoke-style result.json lacking "model" → MUST skip.
        _write(
            runs / "aura-smoke-1779730266" / "iter-1" / "result.json",
            json.dumps({"iteration": 1, "ok": False, "blocker": "x", "detail": "y", "exit_code": 1}),
        )
        # Another no-model record (empty model string) → MUST skip.
        _write(
            runs / "20260601-000000-ghost" / "result.json",
            _result_json("20260601-000000-ghost", "tasks/gp-alpha.md", "", "PASS"),
        )

        self.snap = collect(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestTasks(DashboardCollectBase):
    def test_task_ids_deduped_sorted(self):
        # Set-aware enumeration, deduped by id: internal-1/gp-alpha collides with
        # the root gp-alpha and is shadowed (root wins), so exactly one of each.
        ids = [t.task_id for t in self.snap.tasks]
        self.assertEqual(ids, ["doc-gamma", "gp-alpha", "mat-beta"])

    def test_colliding_set_task_shadowed_by_root(self):
        # The internal-1/gp-alpha.md (WRONG-BUCKET) must NOT shadow the root one.
        alpha = next(t for t in self.snap.tasks if t.task_id == "gp-alpha")
        self.assertEqual(alpha.capability_bucket, "Gameplay Programming")

    def test_set_name_none_when_absent(self):
        beta = next(t for t in self.snap.tasks if t.task_id == "mat-beta")
        self.assertIsNone(beta.set_name)

    def test_declared_layers_unified_and_legacy(self):
        alpha = next(t for t in self.snap.tasks if t.task_id == "gp-alpha")
        beta = next(t for t in self.snap.tasks if t.task_id == "mat-beta")
        self.assertEqual(alpha.layers, ["L1", "L2"])      # legacy "L1, L2" prose
        self.assertEqual(beta.layers, ["L1", "L2I"])      # unified "- KEY" bullets

    def test_title_and_prompt_excerpt(self):
        alpha = next(t for t in self.snap.tasks if t.task_id == "gp-alpha")
        self.assertEqual(alpha.title, "gp-alpha")
        self.assertEqual(alpha.prompt_excerpt, "Do the thing.")
        # normalize the separator so the suffix check holds on Windows too
        self.assertTrue(alpha.path.replace("\\", "/").endswith("/tasks/gp-alpha.md"))


class TestSetAwareEnumeration(unittest.TestCase):
    """Dual-layout discovery: tasks/*.md + tasks/<set>/*.md + tasks/<set>/<id>/task.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        tasks = self.root / "tasks"
        # Root flat spec.
        _write(tasks / "root-a.md", _task_md("root-a", "Root"))
        # Set-dir flat spec (legacy tasks/<set>/<id>.md shape).
        _write(tasks / "set-1" / "flat-b.md", _task_md("flat-b", "SetFlat"))
        # Folder-form spec WITHOUT a task_id metadata line — the id must fall
        # back to the parent-dir name (folder-c), NOT the stem ("task").
        _write(
            tasks / "set-1" / "folder-c" / "task.md",
            "# folder-c title\n\n"
            "## Task ID and metadata\n\n"
            "- tier: T1\n"
            "- capability_bucket: SetFolder\n\n"
            "## Prompt given to the agent\n\n> Folder form.\n\n"
            "## Verifier layers used\n\nL1\n",
        )
        # Same id in BOTH shapes within one set — the folder form must win.
        _write(tasks / "set-1" / "dup-d.md", _task_md("dup-d", "FlatLoses"))
        _write(tasks / "set-1" / "dup-d" / "task.md", _task_md("dup-d", "FolderWins"))
        # Same id in TWO sets — the alphabetically-first set must win.
        _write(tasks / "set-2" / "flat-b.md", _task_md("flat-b", "SecondSet"))
        # Root vs set collision — root must win.
        _write(tasks / "set-2" / "root-a.md", _task_md("root-a", "WRONG"))
        # Non-task docs in a set dir + a stray task.md DIRECTLY in it — all skipped.
        _write(tasks / "set-1" / "README.md", "# not a task\n")
        _write(tasks / "set-1" / "CATALOG.md", "# not a task\n")
        _write(tasks / "set-1" / "task.md", "# misplaced folder-form spec\n")
        self.snap = collect(self.root)
        self.by_id = {t.task_id: t for t in self.snap.tasks}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_both_layouts_enumerated_with_right_ids(self):
        self.assertEqual(sorted(self.by_id), ["dup-d", "flat-b", "folder-c", "root-a"])

    def test_folder_form_id_falls_back_to_dir_name(self):
        c = self.by_id["folder-c"]
        self.assertEqual(c.capability_bucket, "SetFolder")
        self.assertTrue(c.path.replace("\\", "/").endswith("/set-1/folder-c/task.md"))

    def test_folder_form_wins_flat_sibling_in_same_set(self):
        self.assertEqual(self.by_id["dup-d"].capability_bucket, "FolderWins")

    def test_first_set_wins_cross_set_dup(self):
        self.assertEqual(self.by_id["flat-b"].capability_bucket, "SetFlat")

    def test_root_wins_set_dup(self):
        self.assertEqual(self.by_id["root-a"].capability_bucket, "Root")

    def test_skip_names_never_become_tasks(self):
        self.assertNotIn("README", self.by_id)
        self.assertNotIn("CATALOG", self.by_id)
        self.assertNotIn("task", self.by_id)

    def test_fingerprint_watches_every_spec_shape(self):
        # The watched-path set must include specs in EVERY shape, so a change to
        # any of them (or an add/delete) flips the fingerprint.
        _, watched = collect_mod._fingerprint(self.root)
        tasks = self.root / "tasks"
        for spec in (tasks / "root-a.md",
                     tasks / "set-1" / "flat-b.md",
                     tasks / "set-1" / "folder-c" / "task.md"):
            self.assertIn(str(spec), watched)


class TestRuns(DashboardCollectBase):
    def test_skips_non_product_results(self):
        # aura-smoke iter-1 (no model) and the empty-model ghost are both dropped.
        run_ids = {r.run_id for r in self.snap.runs}
        self.assertNotIn("20260601-000000-ghost", run_ids)
        self.assertFalse(any("aura-smoke" in rid for rid in run_ids))

    def test_run_count_and_sort(self):
        # 5 product runs kept; sorted by started_at then run_id (doc-gamma May-27 first).
        self.assertEqual(len(self.snap.runs), 5)
        self.assertEqual(self.snap.runs[0].task_id, "doc-gamma")  # earliest timestamp

    def test_slug_split(self):
        aura = next(r for r in self.snap.runs if r.product == "aura-mcp:claude-sonnet-4-6"
                    and r.overall == "PASS")
        self.assertEqual(aura.tool_layer, "aura-mcp")
        self.assertEqual(aura.model, "claude-sonnet-4-6")

    def test_passed_casing(self):
        # passed is overall.upper()=="PASS"; FAIL/FAIL_NO_EDITS are not passed.
        by_overall = {r.run_id: r.passed for r in self.snap.runs}
        self.assertTrue(any(v for v in by_overall.values()))
        for r in self.snap.runs:
            self.assertEqual(r.passed, r.overall.upper() == "PASS")

    def test_started_at_parsed(self):
        r = next(r for r in self.snap.runs if r.run_id.startswith("20260602-100000"))
        self.assertIsNotNone(r.started_at)
        self.assertEqual(r.started_at.year, 2026)
        self.assertEqual(r.started_at.hour, 10)

    def test_missing_agent_block_nulls(self):
        gamma = next(r for r in self.snap.runs if r.task_id == "doc-gamma")
        self.assertIsNone(gamma.cost_usd)
        self.assertIsNone(gamma.duration_s)
        self.assertEqual(gamma.summary, "")

    def test_fail_no_edits_blocker_and_empty_layers(self):
        beta = next(r for r in self.snap.runs if r.task_id == "mat-beta")
        self.assertEqual(beta.overall, "FAIL_NO_EDITS")
        self.assertEqual(beta.blocker, "no edits (empty submission)")
        self.assertEqual(beta.layer_results, [])  # no verifier_stdout.txt

    def test_fail_blocker_from_layer_detail(self):
        fail = next(r for r in self.snap.runs
                    if r.product == "aura-mcp:claude-sonnet-4-6" and r.overall == "FAIL")
        # First failing layer (L2) detail surfaced as the blocker.
        self.assertIsNotNone(fail.blocker)
        self.assertIn("filter:", fail.blocker)

    def test_passed_run_has_no_blocker(self):
        ok = next(r for r in self.snap.runs if r.passed)
        self.assertIsNone(ok.blocker)

    def test_advisory_null_everywhere(self):
        self.assertTrue(all(r.advisory_score is None for r in self.snap.runs))

    def test_artifacts_attached_sorted_png_only(self):
        run = next(r for r in self.snap.runs
                   if r.run_id == "20260602-100000-gp-alpha-claude-p-opus")
        # Sorted basenames, PNGs only (notes.txt excluded).
        self.assertEqual(run.artifacts, ["shot-0001.png", "shot-0002.png"])

    def test_artifacts_default_empty_list(self):
        # Every run without an artifacts/ dir gets the [] default.
        for r in self.snap.runs:
            if r.run_id != "20260602-100000-gp-alpha-claude-p-opus":
                self.assertEqual(r.artifacts, [])


class TestVerifierStdoutParser(unittest.TestCase):
    def test_golden_layer_parse(self):
        layers = parse_verifier_stdout(GOLDEN_STDOUT)
        self.assertEqual([l.key for l in layers], ["L1", "L2"])
        self.assertEqual([l.status for l in layers], ["pass", "fail"])
        # L1 detail: bracket extras then the two notes, newline-joined.
        self.assertEqual(
            layers[0].detail,
            "exit=0, warn=2\n"
            "- target CraftBenchTemplateEditor: exit 0 in 97.3s\n"
            "- target CraftBenchTemplate: exit 0 in 31.0s",
        )
        self.assertTrue(layers[1].detail.startswith("exit=3, tests=0/1"))

    def test_skipped_normalizes_to_skip(self):
        text = "  L2I : SKIPPED\n        - structural check not requested\n"
        layers = parse_verifier_stdout(text)
        self.assertEqual(layers[0].key, "L2I")
        self.assertEqual(layers[0].status, "skip")
        self.assertEqual(layers[0].detail, "- structural check not requested")

    def test_no_bracket_no_notes_detail_none(self):
        layers = parse_verifier_stdout("  L1  : PASS\n")
        self.assertEqual(layers[0].detail, None)

    def test_empty_and_garbage_return_empty(self):
        self.assertEqual(parse_verifier_stdout(""), [])
        self.assertEqual(parse_verifier_stdout("not a report at all\nrandom text\n"), [])

    def test_unknown_keys_skipped(self):
        # The "overall" / header lines must never become LayerResults.
        layers = parse_verifier_stdout(GOLDEN_STDOUT_PASS)
        self.assertEqual([l.key for l in layers], ["L1", "L2I"])


class TestEmbeddedVerifierPreferred(unittest.TestCase):
    """New runs embed the verify-single report dict in result.json.verifier — the
    data layer must prefer it over the verifier_stdout.txt text parse (which stays
    the fallback for old runs)."""

    def _run_with(self, verifier, stdout_text: str | None):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        rid = "20260604-090000-gp-alpha-claude-p-opus"
        _write(root / "runs" / rid / "result.json",
               _result_json(rid, "tasks/gp-alpha.md", "claude-p:opus", "FAIL",
                            verifier=verifier))
        if stdout_text is not None:
            _write(root / "runs" / rid / "verifier_stdout.txt", stdout_text)
        return parse_run(root / "runs" / rid / "result.json")

    def test_embedded_dict_wins_over_stdout(self):
        # The stdout says L1+L2I PASS; the embedded dict says L1 pass / L2 fail /
        # L2I skipped. The dict must win.
        run = self._run_with(EMBEDDED_VERIFIER, GOLDEN_STDOUT_PASS)
        self.assertEqual([(lr.key, lr.status) for lr in run.layer_results],
                         [("L1", "pass"), ("L2", "fail"), ("L2I", "skip")])

    def test_embedded_detail_matches_text_parse_shape(self):
        # detail = bracket-extras line + "- note" lines, same as the text parse.
        run = self._run_with(EMBEDDED_VERIFIER, None)
        l1 = run.layer_results[0]
        self.assertEqual(
            l1.detail,
            "exit=0, warn=2\n"
            "- target CraftBenchTemplateEditor: exit 0 in 97.3s\n"
            "- target CraftBenchTemplate: exit 0 in 31.0s",
        )
        l2 = run.layer_results[1]
        self.assertTrue(l2.detail.startswith("exit=3, tests=0/1"))
        # No extras + no notes -> detail None (L2I skipped).
        self.assertIsNone(run.layer_results[2].detail)

    def test_blocker_derived_from_embedded_layers(self):
        run = self._run_with(EMBEDDED_VERIFIER, None)
        self.assertIn("filter:", run.blocker)

    def test_verifier_without_layers_falls_back_to_stdout(self):
        # A verifier dict lacking a layers map (or with an empty one) must not
        # shadow the stdout fallback.
        run = self._run_with({"task_id": "gp-alpha", "overall": "fail"},
                             GOLDEN_STDOUT_PASS)
        self.assertEqual([lr.key for lr in run.layer_results], ["L1", "L2I"])

    def test_layer_results_from_verifier_rejects_non_dicts(self):
        self.assertEqual(layer_results_from_verifier(None), [])
        self.assertEqual(layer_results_from_verifier("nope"), [])
        self.assertEqual(layer_results_from_verifier({"layers": "nope"}), [])
        # Unknown layer keys + non-dict bodies are skipped, not crashed on.
        self.assertEqual(
            layer_results_from_verifier({"layers": {"WAT": {"status": "pass"},
                                                    "L1": "not-a-dict"}}),
            [],
        )


class TestAggregationViews(DashboardCollectBase):
    def test_products_and_capabilities(self):
        self.assertEqual(
            self.snap.products,
            ["aura-mcp:claude-sonnet-4-6", "claude-p:opus", "claude-p:opus-4-7"],
        )
        self.assertEqual(
            self.snap.capabilities,
            ["Gameplay Programming", "Project Comprehension / Advisory", "Technical Art"],
        )

    def test_matrix_cell_all_attempts(self):
        # aura-mcp on Gameplay Programming: 2 attempts (FAIL + PASS), 1 pass.
        cell = self.snap.cell("Gameplay Programming", "aura-mcp:claude-sonnet-4-6")
        self.assertEqual((cell["n"], cell["n_pass"]), (2, 1))
        self.assertAlmostEqual(cell["pass_rate"], 0.5)
        self.assertIsNone(cell["mean_advisory"])

    def test_matrix_cell_latest_only_dedupes(self):
        # latest_only keeps the newest aura attempt (PASS) → 1 attempt, 1 pass.
        cell = self.snap.cell("Gameplay Programming", "aura-mcp:claude-sonnet-4-6",
                              latest_only=True)
        self.assertEqual((cell["n"], cell["n_pass"]), (1, 1))
        self.assertAlmostEqual(cell["pass_rate"], 1.0)

    def test_head_to_head_shared_task(self):
        hh = self.snap.head_to_head()
        tasks = {row["task_id"] for row in hh}
        self.assertIn("gp-alpha", tasks)  # run by claude-p AND aura-mcp
        row = next(r for r in hh if r["task_id"] == "gp-alpha")
        self.assertEqual(set(row["products"]),
                         {"claude-p:opus", "aura-mcp:claude-sonnet-4-6"})

    def test_coverage_gaps(self):
        gaps = {g["task_id"]: g for g in self.snap.coverage_gaps()}
        # mat-beta was only run by claude-p:opus → the other two products are missing.
        self.assertIn("mat-beta", gaps)
        self.assertEqual(
            set(gaps["mat-beta"]["products_missing"]),
            {"aura-mcp:claude-sonnet-4-6", "claude-p:opus-4-7"},
        )
        # gp-alpha was run by claude-p:opus + aura-mcp → only opus-4-7 missing.
        self.assertEqual(gaps["gp-alpha"]["products_missing"], ["claude-p:opus-4-7"])

    def test_totals(self):
        t = self.snap.totals()
        self.assertEqual(t["n_tasks"], 3)
        self.assertEqual(t["n_runs"], 5)
        self.assertEqual(t["n_products"], 3)
        self.assertEqual(t["n_pass"], 2)             # gp-alpha PASS x2 (claude-p + aura newer)
        self.assertEqual(t["n_fail"], 1)             # aura FAIL
        self.assertEqual(t["n_fail_no_edits"], 2)    # mat-beta + doc-gamma
        # cost summed only over present cost_usd (0.30 + 0.40 + 0.45) — gamma/beta null.
        self.assertAlmostEqual(t["total_cost_usd"], 1.15)
        self.assertIn("Gameplay Programming", t["grounded_capabilities"])
        self.assertIn("Technical Art", t["ungrounded_capabilities"])


class TestToDict(DashboardCollectBase):
    def test_payload_schema_and_keys(self):
        d = self.snap.to_dict()
        self.assertEqual(d["schema"], "craftbench.dashboard/v1")
        for key in ("generated_at", "products", "capabilities", "tasks", "runs",
                    "matrix", "leaders", "head_to_head", "ungrounded_capabilities",
                    "coverage_gaps", "totals"):
            self.assertIn(key, d)

    def test_payload_is_json_serializable(self):
        # Must round-trip through json with no custom encoder.
        s = json.dumps(self.snap.to_dict())
        self.assertIn("craftbench.dashboard/v1", s)

    def test_generated_at_z_suffix(self):
        self.assertTrue(self.snap.to_dict()["generated_at"].endswith("Z"))

    def test_run_started_at_iso_z_or_null(self):
        runs = self.snap.to_dict()["runs"]
        for r in runs:
            self.assertTrue(r["started_at"] is None or r["started_at"].endswith("Z"))

    def test_layer_results_in_payload(self):
        d = self.snap.to_dict()
        fail_run = next(r for r in d["runs"]
                        if r["product"] == "aura-mcp:claude-sonnet-4-6" and r["overall"] == "FAIL")
        keys = [lr["key"] for lr in fail_run["layer_results"]]
        self.assertEqual(keys, ["L1", "L2"])
        no_edits = next(r for r in d["runs"] if r["task_id"] == "mat-beta")
        self.assertEqual(no_edits["layer_results"], [])

    def test_artifacts_in_payload(self):
        d = self.snap.to_dict()
        with_art = next(r for r in d["runs"]
                        if r["run_id"] == "20260602-100000-gp-alpha-claude-p-opus")
        self.assertEqual(with_art["artifacts"], ["shot-0001.png", "shot-0002.png"])
        # Every run carries the key ([] default) so clients never key-check.
        for r in d["runs"]:
            self.assertIn("artifacts", r)


class TestRunModelRoundTrip(unittest.TestCase):
    """Run.artifacts is a first-class model field: default [] + in to_dict()."""

    @staticmethod
    def _mk_run(**overrides):
        from tools.dashboard.model import Run
        kwargs = dict(
            run_id="r1", task_id="t1", product="claude-p:opus",
            tool_layer="claude-p", model="opus", overall="PASS", passed=True,
            started_at=None, duration_s=1.0, cost_usd=0.1, summary="s",
            blocker=None, layer_results=[], advisory_score=None,
        )
        kwargs.update(overrides)
        return Run(**kwargs)

    def test_artifacts_default_empty(self):
        run = self._mk_run()
        self.assertEqual(run.artifacts, [])
        self.assertEqual(run.to_dict()["artifacts"], [])

    def test_artifacts_round_trip_to_dict(self):
        run = self._mk_run(artifacts=["a.png", "b.png"])
        d = run.to_dict()
        self.assertEqual(d["artifacts"], ["a.png", "b.png"])
        # to_dict copies (mutating the payload must not touch the frozen model).
        d["artifacts"].append("evil.png")
        self.assertEqual(run.artifacts, ["a.png", "b.png"])
        # And the payload stays plain-JSON serializable.
        self.assertIn("a.png", json.dumps(d))


class TestVerifierNullTolerance(unittest.TestCase):
    """A run with verifier=null and a missing cost still parses cleanly."""

    def test_null_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "tasks" / "x.md", _task_md("x", "Gameplay Programming"))
            _write(
                root / "runs" / "20260603-010101-x-claude-p-opus" / "result.json",
                _result_json("20260603-010101-x-claude-p-opus", "tasks/x.md",
                             "claude-p:opus", "PASS", cost_usd=None, verifier=None),
            )
            snap = collect(root)
            self.assertEqual(len(snap.runs), 1)
            self.assertIsNone(snap.runs[0].advisory_score)
            self.assertIsNone(snap.runs[0].cost_usd)
            self.assertTrue(snap.runs[0].passed)
            # to_dict still works with the empty comparison-ish corpus.
            self.assertEqual(snap.to_dict()["schema"], "craftbench.dashboard/v1")


class TestPureStdlib(unittest.TestCase):
    """model + collect must import with no third-party deps loaded."""

    def test_no_textual_or_fastapi_imported(self):
        # Purity is a property of model.py/collect.py IN ISOLATION. Assert it in a
        # FRESH subprocess: under `unittest discover` a sibling module (test_tui
        # imports textual, web test_app imports fastapi) loads a UI dep into THIS
        # interpreter first, which would false-fail a live sys.modules inspection.
        import subprocess
        repo_root = Path(__file__).resolve().parents[3]
        # NB: `from .collect import collect` in the package __init__ shadows the
        # submodule attr, so reach the function via `from ... import`, not
        # `tools.dashboard.collect.collect` (that would resolve to the function).
        code = (
            "import sys\n"
            "from tools.dashboard.collect import collect\n"
            "import tools.dashboard.model  # noqa: F401\n"
            "assert 'textual' not in sys.modules, 'data layer pulled in textual'\n"
            "assert 'fastapi' not in sys.modules, 'data layer pulled in fastapi'\n"
            "assert callable(collect)\n"
        )
        proc = subprocess.run(
            [_sys.executable, "-c", code],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestTaskProgress(unittest.TestCase):
    """Per-task implementation status (validated / wired / planned) + the funnel."""

    def _repo(self, d: Path) -> None:
        tasks = d / "tasks"
        _write(tasks / "gp-alpha.md", _task_md("gp-alpha", "Gameplay Programming"))
        _write(tasks / "gp-wired.md", _task_md("gp-wired", "Gameplay Programming"))
        _write(tasks / "gp-planned.md", _task_md("gp-planned", "Gameplay Programming"))
        # gp-alpha: a PASS run -> validated.
        _write(
            d / "runs" / "20260602-100000-gp-alpha-claude-p-opus" / "result.json",
            _result_json("20260602-100000-gp-alpha-claude-p-opus", "tasks/gp-alpha.md",
                         "claude-p:opus", "PASS"),
        )
        # gp-wired: a reference-solution dir but NO run -> wired.
        (d / "tests" / "reference-solutions" / "gp-wired" / "Source").mkdir(parents=True)
        # gp-planned: nothing -> planned.

    def test_status_tiers_and_funnel(self):
        with tempfile.TemporaryDirectory() as dd:
            d = Path(dd)
            self._repo(d)
            tp = collect(d).task_progress()
            by = {it["task_id"]: it for it in tp["items"]}
            self.assertEqual(by["gp-alpha"]["status"], "validated")
            self.assertEqual(by["gp-wired"]["status"], "wired")
            self.assertTrue(by["gp-wired"]["has_reference_solution"])
            self.assertEqual(by["gp-planned"]["status"], "planned")
            self.assertFalse(by["gp-planned"]["has_reference_solution"])
            s = tp["summary"]
            self.assertEqual(
                (s["authored"], s["validated"], s["wired"], s["planned"]), (3, 1, 1, 1))
            self.assertEqual(s["v1_target"], 40)

    def test_task_progress_in_to_dict(self):
        with tempfile.TemporaryDirectory() as dd:
            d = Path(dd)
            self._repo(d)
            self.assertIn("task_progress", collect(d).to_dict())

    def test_folder_local_reference_counts_as_wired(self):
        # Folder-per-task layout: tasks/<set>/<id>/reference/ is unioned with the
        # legacy tests/reference-solutions/<id>/ home — either makes a task wired.
        with tempfile.TemporaryDirectory() as dd:
            d = Path(dd)
            self._repo(d)
            _write(d / "tasks" / "set-1" / "gp-folded" / "task.md",
                   _task_md("gp-folded", "Gameplay Programming"))
            (d / "tasks" / "set-1" / "gp-folded" / "reference" / "Source").mkdir(
                parents=True)
            tp = collect(d).task_progress()
            by = {it["task_id"]: it for it in tp["items"]}
            self.assertEqual(by["gp-folded"]["status"], "wired")
            self.assertTrue(by["gp-folded"]["has_reference_solution"])
            # The legacy home still counts too (gp-wired from _repo).
            self.assertEqual(by["gp-wired"]["status"], "wired")


if __name__ == "__main__":
    unittest.main()


class TestHarnessFaultsAreNotModelFailures(unittest.TestCase):
    """A run that never reached a gradable state leaves every denominator.

    The dashboard had THREE independent counts (compare's aggregate, model's
    totals(), and the TUI's matrix cell). None used an allowlist, so a
    HARNESS-ERROR run was a red FAIL cell captioned "verifier FAIL" and a
    denominator unit in all three.
    """

    @staticmethod
    def _run(overall, passed=False, **kw):
        from tools.dashboard.model import Run
        from tools.dashboard.collect import _GRADED_VERDICTS
        kwargs = dict(
            run_id="r1", task_id="t1", product="claude-p:opus",
            tool_layer="claude-p", model="opus", overall=overall, passed=passed,
            started_at=None, duration_s=1.0, cost_usd=0.1, summary="s",
            blocker=None, layer_results=[], advisory_score=None,
            graded=overall.upper() in _GRADED_VERDICTS,
        )
        kwargs.update(kw)
        return Run(**kwargs)

    def test_graded_defaults_true(self):
        """Pre-existing constructions must keep their meaning."""
        from tools.dashboard.model import Run
        r = Run("r", "t", "p:m", "p", "m", "PASS", True, None, None, None, "",
                None, [], None)
        self.assertTrue(r.graded)

    def test_harness_verdicts_are_not_graded(self):
        for v in ("HARNESS-ERROR", "TIMEOUT", "AGENT-CONFIG-ERROR", "UNGRADED"):
            with self.subTest(verdict=v):
                self.assertFalse(self._run(v).graded)

    def test_contested_model_outcomes_stay_graded(self):
        """Owner decision pending; ambiguity resolves toward GRADED."""
        for v in ("FAIL_NO_EDITS", "SANDBOX-REJECT", "NO_DELIVERABLE"):
            with self.subTest(verdict=v):
                self.assertTrue(self._run(v).graded)

    def test_blocker_does_not_call_a_harness_fault_a_verifier_fail(self):
        from tools.dashboard.collect import _derive_blocker
        self.assertEqual(_derive_blocker("HARNESS-ERROR", False, []),
                         "not graded (HARNESS-ERROR)")
        # A real FAIL keeps its old wording.
        self.assertEqual(_derive_blocker("FAIL", False, []), "verifier FAIL")

    def test_totals_excludes_harness_faults_from_n_fail(self):
        from tools.dashboard.model import Snapshot
        runs = [self._run("PASS", passed=True), self._run("FAIL"),
                self._run("HARNESS-ERROR")]
        snap = Snapshot(generated_at="1970-01-01T00:00:00Z", tasks=[], runs=runs,
                        products=["claude-p:opus"], capabilities=[],
                        repo_root=Path("."))
        totals = snap.totals()
        self.assertEqual(totals["n_pass"], 1)
        self.assertEqual(totals["n_fail"], 1)     # was 2 before the fix
        self.assertEqual(totals["n_excluded"], 1)

    def test_tui_cell_denominator_is_graded_only(self):
        from tools.dashboard.tui import _cell_text
        txt = _cell_text([self._run("PASS", passed=True),
                          self._run("PASS", passed=True),
                          self._run("HARNESS-ERROR")])
        self.assertIn("2/2", txt)                 # was 2/3 before the fix


class TestVoidRunsStayVisible(unittest.TestCase):
    """Filtering without reporting turns a wrong number into an invisible one.

    Caught on review: the first cut of the graded filter made an all-faulted
    TUI cell render as ``·`` — identical to a cell nobody ever ran — and
    ``Run.to_dict()`` dropped ``graded`` so every web consumer silently
    re-counted what had just been excluded.
    """

    @staticmethod
    def _run(overall, passed=False):
        from tools.dashboard.model import Run
        from tools.dashboard.collect import _GRADED_VERDICTS
        return Run("r", "t", "p:m", "p", "m", overall, passed, None, None, None,
                   "", None, [], None, graded=overall.upper() in _GRADED_VERDICTS)

    def test_all_voided_cell_is_not_an_empty_cell(self):
        from tools.dashboard.tui import _cell_text
        empty = _cell_text([])
        voided = _cell_text([self._run("HARNESS-ERROR"), self._run("TIMEOUT")])
        self.assertNotEqual(empty, voided)
        self.assertIn("!2", voided)

    def test_void_count_shows_alongside_a_graded_result(self):
        from tools.dashboard.tui import _cell_text
        txt = _cell_text([self._run("PASS", passed=True),
                          self._run("PASS", passed=True),
                          self._run("HARNESS-ERROR")])
        self.assertIn("2/2", txt)
        self.assertIn("!1", txt)

    def test_a_clean_cell_carries_no_void_marker(self):
        from tools.dashboard.tui import _cell_text
        self.assertNotIn("!", _cell_text([self._run("PASS", passed=True)]))

    def test_graded_survives_to_dict(self):
        self.assertFalse(self._run("HARNESS-ERROR").to_dict()["graded"])
        self.assertTrue(self._run("PASS", passed=True).to_dict()["graded"])


# ---------------------------------------------------------------------------
# Which task is a run? Delegated to tools/runlib/run_identity.py since
# 2026-08-19. Every test below goes RED against this file's previous answer,
# ``PurePosixPath(str(d.get("task",""))).stem``, which never splits a WINDOWS
# path: on the real corpus every id came out as a whole
# ``C:\...\tasks\bp\<id>\task`` string, 0 of 18 joined the task tree, and
# ``coverage_gaps`` therefore reported every declared task unattempted.
# ---------------------------------------------------------------------------
_BSL = chr(92)  # a literal backslash, spelled so nothing in the toolchain eats it


class TestRunTaskIdentity(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # Folder-form specs, the convention every task authored since 2026-07
        # follows — and the shape whose paths all end in ".../<id>/task.md".
        _write(self.root / "tasks" / "cpp" / "gp-alpha" / "task.md",
               _task_md("gp-alpha", "Gameplay Programming"))
        _write(self.root / "tasks" / "bp" / "gp-beta" / "task.md",
               _task_md("gp-beta", "Gameplay Programming"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, run_id: str, payload: dict) -> None:
        _write(self.root / "runs" / run_id / "result.json", json.dumps(payload))

    def test_windows_path_yields_the_bare_id(self):
        win = _BSL.join(["C:", "cb", "bench-tree", "tasks", "cpp", "gp-alpha",
                         "task.md"])
        self._run("r0", {"run_id": "r0", "model": "bare:m", "overall": "PASS",
                         "task": win})
        run, = collect(self.root).runs
        self.assertEqual(run.task_id, "gp-alpha")
        self.assertNotIn(_BSL, run.task_id)

    def test_windows_and_posix_paths_agree(self):
        win = _BSL.join(["C:", "cb", "tasks", "bp", "gp-beta", "task.md"])
        self._run("r-win", {"run_id": "r-win", "model": "bare:m",
                            "overall": "PASS", "task": win})
        self._run("r-posix", {"run_id": "r-posix", "model": "bare:m",
                              "overall": "PASS",
                              "task": "/c/cb/tasks/bp/gp-beta/task.md"})
        ids = {r.task_id for r in collect(self.root).runs}
        self.assertEqual(ids, {"gp-beta"})

    def test_the_run_joins_the_task_tree(self):
        """The join coverage_gaps depends on: 0 of 18 ids joined before."""
        win = _BSL.join(["C:", "cb", "tasks", "cpp", "gp-alpha", "task.md"])
        self._run("r0", {"run_id": "r0", "model": "bare:m", "overall": "PASS",
                         "task": win})
        snap = collect(self.root)
        self.assertEqual({t.task_id for t in snap.tasks}, {"gp-alpha", "gp-beta"})
        gaps = {g["task_id"]: g for g in snap.coverage_gaps()}
        # gp-alpha WAS attempted by the only observed product, so it is not a gap.
        self.assertNotIn("gp-alpha", gaps)
        self.assertEqual(gaps["gp-beta"]["products_missing"], ["bare:m"])

    def test_bare_task_id_shape_resolves(self):
        """aura_rig/run_graded.py writes task_id and NO task key at all."""
        self._run("r0", {"run_id": "r0", "model": "aura-product:m",
                         "overall": "PASS", "task_id": "gp-beta"})
        run, = collect(self.root).runs
        self.assertEqual(run.task_id, "gp-beta")

    def test_a_record_naming_no_task_is_visibly_unknown(self):
        self._run("r0", {"run_id": "r0", "model": "aura-product:m",
                         "overall": "PASS"})
        run, = collect(self.root).runs
        self.assertEqual(run.task_id, "UNKNOWN")

    def test_unknown_runs_do_not_merge_into_a_real_task(self):
        self._run("r0", {"run_id": "r0", "model": "aura-product:m",
                         "overall": "PASS", "task_id": "gp-alpha"})
        self._run("r1", {"run_id": "r1", "model": "aura-product:m",
                         "overall": "FAIL"})
        self.assertEqual({r.task_id for r in collect(self.root).runs},
                         {"gp-alpha", "UNKNOWN"})

    def test_parse_run_without_a_repo_root_still_gets_the_id(self):
        win = _BSL.join(["C:", "cb", "tasks", "cpp", "gp-alpha", "task.md"])
        self._run("r0", {"run_id": "r0", "model": "bare:m", "overall": "PASS",
                         "task": win})
        run = parse_run(self.root / "runs" / "r0" / "result.json")
        self.assertEqual(run.task_id, "gp-alpha")
