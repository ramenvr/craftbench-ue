"""Web API tests — TestClient over ``create_app(synthetic_repo)``.

Builds a small but realistic ``tasks/`` + ``runs/`` tree in a tempdir (mirroring
``tests/test_collect.py``'s fixtures so the two suites agree on the on-disk
format), points the FastAPI app at it via the ``create_app(repo_root)`` factory,
and asserts the HTTP surface:

  GET /                  -> 200, serves the single-page HTML client
  GET /api/snapshot      -> 200, JSON with the full payload keys + correct counts
  GET /api/snapshot?latest_only=true -> dedupes duplicate (product, task) attempts
  GET /api/run/{run_id}  -> 200 with {run, task} for a real run, 404 for an unknown
  GET /api/run for a no-stdout run -> empty layer_results (overall authoritative)

Pure pytest-free ``unittest``; needs ``fastapi`` (TestClient) installed but no UE,
no real run, no server process. Run from the repo root:

    python3 -m unittest tools.dashboard.web.tests.test_app
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tools.dashboard.web.app import create_app

# Golden verifier stdout pinning report.render_text() — a PASS L1 + FAIL L2 with
# bracket extras, log= suffix, and indented "- note" lines (same shape as the real
# runs/<id>/verifier_stdout.txt and the data-layer suite's fixture).
GOLDEN_STDOUT = """\
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  task_id   : gp-alpha
  L1  : PASS    [exit=0, warn=2] log=/tmp/x/l1_build.log
        - target CraftBenchTemplateEditor: exit 0 in 97.3s
        - target CraftBenchTemplate: exit 0 in 31.0s
  L2  : FAIL    [exit=3, tests=0/1] log=/tmp/x/l2_pie.log
        - filter: Project.Functional Tests.Maps.L_Alpha.AlphaFunctionalTest
  overall   : FAIL
"""


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _write_bytes(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


# Recognizable fake-PNG payload for the artifact route content assertion.
_PNG_BYTES = b"\x89PNG\r\n\x1a\ncraftbench-artifact-1"
# ...and for the preview route's surround video (live channel).
_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42craftbench-surround-1"


def _task_md(name: str, capability: str, *, tier: str = "T1",
             set_name: str | None = "internal-1") -> str:
    set_line = f"- set: {set_name}\n" if set_name is not None else ""
    return (
        f"# {name}\n\n"
        "## Task ID and metadata\n\n"
        f"- task_id: {name}\n"
        f"- tier: {tier}\n"
        f"- capability_bucket: {capability}\n"
        f"{set_line}"
        "\n## Prompt given to the agent\n\n"
        "> Do the thing precisely.\n\n"
        "## Verifier layers\n\n- L1\n- L2\n"
    )


def _result_json(run_id: str, task: str, model: str | None, overall: str, *,
                 cost_usd: float | None = 0.5, summary: str = "did stuff") -> str:
    d: dict = {"run_id": run_id, "task": task, "overall": overall, "verifier": None}
    if model is not None:
        d["model"] = model
    agent: dict = {"exit_code": 0, "summary": summary, "duration_s": 120.0}
    if cost_usd is not None:
        agent["cost_usd"] = cost_usd
    d["agent"] = agent
    return json.dumps(d, indent=2)


def _build_repo(root: Path) -> None:
    """A synthetic repo: 2 tasks, gp-alpha run by 2 products (one duplicated)."""
    tasks, runs = root / "tasks", root / "runs"
    _write(tasks / "gp-alpha.md", _task_md("gp-alpha", "Gameplay Programming"))
    _write(tasks / "mat-beta.md", _task_md("mat-beta", "Technical Art", set_name=None))

    # gp-alpha: claude-p PASS (with verifier stdout) + aura-mcp FAIL then PASS dup.
    _write(runs / "20260602-100000-gp-alpha-claude-p-opus" / "result.json",
           _result_json("20260602-100000-gp-alpha-claude-p-opus", "tasks/gp-alpha.md",
                        "claude-p:opus", "PASS", cost_usd=0.30))
    _write(runs / "20260602-100000-gp-alpha-claude-p-opus" / "verifier_stdout.txt",
           GOLDEN_STDOUT)
    # Swept capture artifacts on the claude-p run: one PNG the route must serve,
    # plus a non-PNG on disk that is NOT collected (must 404 even though present).
    art = runs / "20260602-100000-gp-alpha-claude-p-opus" / "artifacts"
    _write_bytes(art / "shot-0001.png", _PNG_BYTES)
    _write_bytes(art / "secret.txt", b"not collected")
    _write(runs / "20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "result.json",
           _result_json("20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6",
                        "tasks/gp-alpha.md", "aura-mcp:claude-sonnet-4-6", "FAIL", cost_usd=0.40))
    _write(runs / "20260602-120000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "result.json",
           _result_json("20260602-120000-gp-alpha-aura-mcp-claude-sonnet-4-6",
                        "tasks/gp-alpha.md", "aura-mcp:claude-sonnet-4-6", "PASS", cost_usd=0.45))
    # mat-beta: FAIL_NO_EDITS, no verifier stdout → empty layer_results.
    _write(runs / "20260602-130000-mat-beta-claude-p-opus" / "result.json",
           _result_json("20260602-130000-mat-beta-claude-p-opus", "tasks/mat-beta.md",
                        "claude-p:opus", "FAIL_NO_EDITS", cost_usd=None))
    # Non-product noise (no model) → must be skipped by the data layer.
    _write(runs / "aura-smoke-9" / "iter-1" / "result.json",
           json.dumps({"iteration": 1, "ok": False, "exit_code": 1}))


class WebAppBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_repo(self.root)
        self.client = TestClient(create_app(self.root))

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestIndex(WebAppBase):
    def test_index_serves_html(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        # The single-page client mentions the dashboard + fetches /api/snapshot.
        self.assertIn("CraftBench dashboard", r.text)
        self.assertIn("/api/snapshot", r.text)


class TestSnapshotEndpoint(WebAppBase):
    def test_snapshot_200_and_schema(self):
        r = self.client.get("/api/snapshot")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["schema"], "craftbench.dashboard/v1")

    def test_snapshot_has_all_expected_keys(self):
        d = self.client.get("/api/snapshot").json()
        expected = {
            "schema", "generated_at", "products", "capabilities", "tasks",
            "runs", "matrix", "leaders", "head_to_head",
            "ungrounded_capabilities", "coverage_gaps", "totals",
        }
        self.assertTrue(expected.issubset(d.keys()),
                        f"missing keys: {expected - set(d.keys())}")

    def test_snapshot_counts(self):
        d = self.client.get("/api/snapshot").json()
        # 2 tasks; 4 product runs (the aura-smoke iter-1 is skipped).
        self.assertEqual(d["totals"]["n_tasks"], 2)
        self.assertEqual(d["totals"]["n_runs"], 4)
        # products: claude-p:opus, aura-mcp:claude-sonnet-4-6
        self.assertEqual(set(d["products"]),
                         {"claude-p:opus", "aura-mcp:claude-sonnet-4-6"})

    def test_snapshot_runs_carry_layer_results_from_stdout(self):
        d = self.client.get("/api/snapshot").json()
        run = next(r for r in d["runs"]
                   if r["run_id"] == "20260602-100000-gp-alpha-claude-p-opus")
        keys = [(lr["key"], lr["status"]) for lr in run["layer_results"]]
        self.assertEqual(keys, [("L1", "pass"), ("L2", "fail")])

    def test_fail_no_edits_has_empty_layer_results(self):
        d = self.client.get("/api/snapshot").json()
        run = next(r for r in d["runs"]
                   if r["run_id"] == "20260602-130000-mat-beta-claude-p-opus")
        self.assertEqual(run["overall"], "FAIL_NO_EDITS")
        self.assertEqual(run["layer_results"], [])
        self.assertIsNotNone(run["blocker"])  # synthesized "no edits ..."

    def test_advisory_score_null_everywhere(self):
        # Contract fact #2: never imply R2 ran — advisory_score is null on all runs.
        d = self.client.get("/api/snapshot").json()
        self.assertTrue(all(r["advisory_score"] is None for r in d["runs"]))

    def test_latest_only_dedupes_duplicate_attempts(self):
        # All-attempts: aura-mcp ran gp-alpha twice (FAIL, then PASS) → n=2 in cell.
        all_d = self.client.get("/api/snapshot").json()
        latest_d = self.client.get("/api/snapshot?latest_only=true").json()

        def cell_n(payload):
            for c in payload["matrix"]:
                if (c["capability"] == "Gameplay Programming"
                        and c["product"] == "aura-mcp:claude-sonnet-4-6"):
                    return c["n"], c["n_pass"]
            return None

        self.assertEqual(cell_n(all_d), (2, 1))       # both attempts counted
        self.assertEqual(cell_n(latest_d), (1, 1))    # only the newest PASS

    def test_head_to_head_present_for_shared_task(self):
        d = self.client.get("/api/snapshot").json()
        shared = {row["task_id"] for row in d["head_to_head"]}
        self.assertIn("gp-alpha", shared)  # run by 2 products


class TestRunEndpoint(WebAppBase):
    def test_run_detail_200_with_run_and_task(self):
        rid = "20260602-100000-gp-alpha-claude-p-opus"
        r = self.client.get(f"/api/run/{rid}")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["run"]["run_id"], rid)
        self.assertEqual(d["run"]["task_id"], "gp-alpha")
        # task context attached for the modal
        self.assertEqual(d["task"]["task_id"], "gp-alpha")
        self.assertEqual(d["task"]["capability_bucket"], "Gameplay Programming")
        # per-layer detail carried through
        self.assertTrue(len(d["run"]["layer_results"]) == 2)

    def test_run_detail_404_for_unknown(self):
        r = self.client.get("/api/run/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_run_detail_exposes_cost_and_duration(self):
        rid = "20260602-100000-gp-alpha-claude-p-opus"
        run = self.client.get(f"/api/run/{rid}").json()["run"]
        self.assertEqual(run["cost_usd"], 0.30)
        self.assertEqual(run["duration_s"], 120.0)


class TestArtifactEndpoint(WebAppBase):
    """GET /api/run/{run_id}/artifact/{name} — serve only COLLECTED artifacts."""

    RID = "20260602-100000-gp-alpha-claude-p-opus"

    def test_artifact_200_serves_png_bytes(self):
        r = self.client.get(f"/api/run/{self.RID}/artifact/shot-0001.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/png")
        self.assertEqual(r.content, _PNG_BYTES)

    def test_artifacts_listed_in_snapshot_and_run_detail(self):
        snap_run = next(r for r in self.client.get("/api/snapshot").json()["runs"]
                        if r["run_id"] == self.RID)
        self.assertEqual(snap_run["artifacts"], ["shot-0001.png"])
        detail = self.client.get(f"/api/run/{self.RID}").json()["run"]
        self.assertEqual(detail["artifacts"], ["shot-0001.png"])

    def test_unknown_run_404(self):
        r = self.client.get("/api/run/no-such-run/artifact/shot-0001.png")
        self.assertEqual(r.status_code, 404)

    def test_name_not_in_collected_list_404(self):
        # Missing file AND a file that exists on disk but was never collected
        # (non-PNG) — both must 404.
        for name in ("missing.png", "secret.txt"):
            r = self.client.get(f"/api/run/{self.RID}/artifact/{name}")
            self.assertEqual(r.status_code, 404, name)

    def test_run_without_artifacts_404(self):
        r = self.client.get(
            "/api/run/20260602-130000-mat-beta-claude-p-opus/artifact/shot-0001.png")
        self.assertEqual(r.status_code, 404)

    def test_traversal_names_rejected(self):
        # Names carrying .. or a separator (raw or percent-encoded) must never
        # read outside the run's artifacts/ dir — uniformly 404, never 200/500.
        # NB: a literal ".." path segment is dot-normalized away by the HTTP
        # client itself before it ever reaches the server, so the raw forms are
        # exercised percent-encoded (%2e%2e = "..", %2F = "/"): the ASGI layer
        # decodes them back into real ".."/"/" before routing + the handler.
        for name in (
            "%2e%2e",
            "../result.json",
            "..%2Fresult.json",
            "..%2F..%2Ftasks%2Fgp-alpha.md",
            "%2e%2e%2fresult.json",
            "sub%2Fdir.png",
        ):
            r = self.client.get(f"/api/run/{self.RID}/artifact/{name}")
            self.assertEqual(r.status_code, 404, name)

    def test_traversal_run_id_rejected(self):
        # A traversal run_id can never validate against the collected run list.
        r = self.client.get("/api/run/..%2F..%2Ftasks/artifact/gp-alpha.md")
        self.assertEqual(r.status_code, 404)




class TestNestedRunRoutes(WebAppBase):
    """runs/<backend>/<run_id>/ (run.py's per-backend folder default) — the
    artifact and report routes must resolve one container level down, not just
    direct children of runs/."""

    RID = "20260710-000000-gp-alpha-claude-p-sonnet"

    def setUp(self) -> None:
        super().setUp()
        nested = self.root / "runs" / "claude-p" / self.RID
        _write(nested / "result.json",
               _result_json(self.RID, "tasks/gp-alpha.md", "claude-p:sonnet",
                            "PASS", cost_usd=0.10))
        _write_bytes(nested / "artifacts" / "shot-0001.png", _PNG_BYTES)
        self.client = TestClient(create_app(self.root))

    def test_nested_artifact_200_serves_png_bytes(self):
        r = self.client.get(f"/api/run/{self.RID}/artifact/shot-0001.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/png")
        self.assertEqual(r.content, _PNG_BYTES)

    def test_nested_report_200(self):
        r = self.client.get(f"/api/run/{self.RID}/report")
        self.assertEqual(r.status_code, 200)
        self.assertIn("gp-alpha", r.text)


class TestSetAwareLayouts(unittest.TestCase):
    """Dual-layout coverage at the HTTP surface: the snapshot's task list, the
    launch options, and the SSE change-fingerprint must all see task specs in
    either shape (set-dir flat ``tasks/<set>/<id>.md`` and folder-form
    ``tasks/<set>/<id>/task.md``)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_repo(self.root)
        # A set-dir flat spec + a folder-form spec on top of the root fixtures.
        _write(self.root / "tasks" / "concept-1" / "gp-set-flat.md",
               _task_md("gp-set-flat", "Gameplay Programming"))
        _write(self.root / "tasks" / "concept-1" / "gp-folder" / "task.md",
               _task_md("gp-folder", "Gameplay Programming"))
        self.client = TestClient(create_app(self.root))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_snapshot_lists_set_and_folder_tasks(self):
        d = self.client.get("/api/snapshot").json()
        ids = {t["task_id"] for t in d["tasks"]}
        self.assertLessEqual({"gp-alpha", "gp-set-flat", "gp-folder"}, ids)

    def test_launch_options_list_set_qualified_ids(self):
        d = self.client.get("/api/launch/options").json()
        self.assertIn("concept-1/gp-set-flat", d["tasks"])
        self.assertIn("concept-1/gp-folder", d["tasks"])
        self.assertIn("gp-alpha", d["tasks"])

    def test_fingerprint_moves_on_folder_form_spec_change(self):
        # The SSE change-detector must watch specs in EVERY shape — bump the
        # folder-form spec's mtime into the future and the fingerprint moves.
        from tools.dashboard.web.app import _fingerprint
        fp0 = _fingerprint(self.root)
        spec = self.root / "tasks" / "concept-1" / "gp-folder" / "task.md"
        future = time.time() + 60
        os.utime(spec, (future, future))
        self.assertGreater(_fingerprint(self.root), fp0)


if __name__ == "__main__":
    unittest.main()
