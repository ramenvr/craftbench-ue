"""Unit tests for aura_rig.provenance — run provenance + telemetry capture.

Fully offline: no socket, no editor, no UE install. The /api/mcp GET is an injected
``opener`` seam returning canned bytes; asset capture's save/sweep functions are
injected stubs; the filesystem helpers run on a temp tree; git is an injected runner.

The sub-agent MODEL and TOKEN verdicts are asserted to stay UNRESOLVED — that is the
contract now that the vendor billing readback is out of this release (THIRD-PARTY.md
§4): absent, never a proxied model and never a zero cost.
"""

import json
import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import provenance  # noqa: E402


# A canned /api/mcp body: 2 servers, 2 + 1 tools (the real shape, shrunk).
_MCP_BODY = [
    {"name": "unreal_inspector", "status": "connected",
     "toolInfo": [
         {"name": "get_unreal_context", "description": "...", "inputSchema": {}},
         {"name": "get_asset_meta", "description": "...", "inputSchema": {}},
     ]},
    {"name": "unreal_editor", "status": "connected",
     "toolInfo": [
         {"name": "edit_blueprint", "description": "...", "inputSchema": {}},
     ]},
]


# ---------------------------------------------------------------------------
# (a) capture_tool_manifest
# ---------------------------------------------------------------------------

class TestToolManifest(unittest.TestCase):
    def test_parse_counts_and_unions(self):
        m = provenance.parse_tool_manifest(_MCP_BODY)
        self.assertEqual(m["tool_count"], 3)
        self.assertEqual(len(m["servers"]), 2)
        self.assertEqual(m["servers"][0]["name"], "unreal_inspector")
        self.assertEqual(m["servers"][0]["tool_count"], 2)
        self.assertEqual(m["servers"][1]["tool_count"], 1)
        self.assertEqual(
            m["tools"], ["edit_blueprint", "get_asset_meta", "get_unreal_context"])

    def test_parse_tolerates_dict_wrapper(self):
        m = provenance.parse_tool_manifest({"servers": _MCP_BODY})
        self.assertEqual(m["tool_count"], 3)

    def test_parse_tolerates_garbage(self):
        self.assertEqual(provenance.parse_tool_manifest("nope")["tool_count"], 0)
        self.assertEqual(provenance.parse_tool_manifest(None)["tool_count"], 0)

    def test_capture_writes_file_via_seam(self):
        def opener(url, timeout):
            assert url.endswith("/api/mcp")
            return json.dumps(_MCP_BODY).encode()
        with TemporaryDirectory() as td:
            run = Path(td)
            m = provenance.capture_tool_manifest(opener=opener, run_dir=run)
            self.assertEqual(m["tool_count"], 3)
            self.assertTrue((run / "tool_manifest.json").exists())
            on_disk = json.loads((run / "tool_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk["tool_count"], 3)

    def test_capture_survives_opener_exception(self):
        def boom(url, timeout):
            raise ConnectionError("editor down")
        m = provenance.capture_tool_manifest(opener=boom)
        self.assertEqual(m["tool_count"], 0)
        self.assertIn("error", m)

    def test_capture_survives_bad_json(self):
        m = provenance.capture_tool_manifest(opener=lambda u, t: b"not json")
        self.assertEqual(m["tool_count"], 0)
        self.assertIn("error", m)


# ---------------------------------------------------------------------------
# (b) capture_assets — reuses asset_capture via injected seams
# ---------------------------------------------------------------------------

class TestCaptureAssets(unittest.TestCase):
    def test_sweeps_and_records_via_injected_seams(self):
        save_calls = []

        class _Res:
            status, exit_code = "ok", 0

        def fake_save(**kw):
            save_calls.append(kw)
            return _Res()

        def fake_sweep(*, project_root, out_dir, deny_prefixes, allow_prefixes):
            # Simulate two captured assets under an allow prefix.
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "BP_X.uasset").write_text("x")
            return ["Content/Blueprints/BP_X.uasset",
                    "Content/Tasks/t1/M_Y.uasset"]

        with TemporaryDirectory() as td:
            run = Path(td) / "run"
            run.mkdir()
            res = provenance.capture_assets(
                run_dir=run, project_root=Path(td) / "proj",
                manifest_allow_prefixes=["Content/Blueprints/", "Content/Tasks/"],
                manifest_deny_prefixes=["Content/Maps/"],
                ue_root=Path("/fake/UE_5.7"),
                _save_all_dirty=fake_save, _capture_content_assets=fake_sweep)
            self.assertEqual(res["count"], 2)
            self.assertEqual(res["save"]["status"], "ok")
            self.assertEqual(len(save_calls), 1)
            self.assertTrue((run / "assets_captured.json").exists())

    def test_skips_save_when_no_ue_root(self):
        def fake_sweep(**kw):
            return []

        def fail_save(**kw):  # must NOT be called
            raise AssertionError("save should be skipped")

        with TemporaryDirectory() as td:
            run = Path(td) / "run"
            res = provenance.capture_assets(
                run_dir=run, project_root=Path(td),
                manifest_allow_prefixes=["Content/Tasks/"],
                manifest_deny_prefixes=[],
                ue_root=None,  # -> no save pass
                _save_all_dirty=fail_save, _capture_content_assets=fake_sweep)
            self.assertEqual(res["count"], 0)
            self.assertFalse(res["save"]["ran"])

    def test_real_capture_content_assets_default_used(self):
        # No _capture_content_assets stub: exercises the real asset_capture import
        # against a tiny on-disk Content tree (no UE needed for the pure sweep).
        with TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            (proj / "Content" / "Blueprints").mkdir(parents=True)
            (proj / "Content" / "Blueprints" / "BP_Coin.uasset").write_text("a")
            (proj / "Content" / "Maps").mkdir(parents=True)
            (proj / "Content" / "Maps" / "L_X.umap").write_text("denied")
            run = Path(td) / "run"
            res = provenance.capture_assets(
                run_dir=run, project_root=proj,
                manifest_allow_prefixes=["Content/Blueprints/"],
                manifest_deny_prefixes=["Content/Maps/"],
                ue_root=None)
            self.assertEqual(res["captured"], ["Content/Blueprints/BP_Coin.uasset"])
            self.assertTrue((run / "assets" / "Content" / "Blueprints"
                             / "BP_Coin.uasset").exists())


# ---------------------------------------------------------------------------
# (c) capture_screenshots — mtime selection on a temp Saved/ tree
# ---------------------------------------------------------------------------

class TestScreenshots(unittest.TestCase):
    def _shot(self, d: Path, name: str, mtime: float):
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_bytes(b"\x89PNG fake")
        import os
        os.utime(p, (mtime, mtime))
        return p

    def test_copies_only_new_pngs(self):
        with TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            shots = proj / provenance.SCREENSHOT_DIR_REL
            t = 1_000_000.0
            self._shot(shots, "old.png", t - 100)   # stale (prior run)
            self._shot(shots, "new1.png", t + 10)
            self._shot(shots, "new2.png", t + 20)
            run = Path(td) / "run"
            res = provenance.capture_screenshots(run, t, project_root=proj)
            self.assertEqual(sorted(res["copied"]), ["new1.png", "new2.png"])
            self.assertEqual(res["count"], 2)
            self.assertTrue((run / "screenshots" / "new1.png").exists())
            self.assertFalse((run / "screenshots" / "old.png").exists())

    def test_missing_dir_is_empty_not_error(self):
        with TemporaryDirectory() as td:
            res = provenance.capture_screenshots(
                Path(td) / "run", 0.0, project_root=Path(td) / "no-proj")
            self.assertEqual(res["count"], 0)


# ---------------------------------------------------------------------------
# (d) build_run_manifest + version readers + telemetry verdicts
# ---------------------------------------------------------------------------

class TestVersionReaders(unittest.TestCase):
    def test_engine_association(self):
        with TemporaryDirectory() as td:
            up = Path(td) / "x.uproject"
            up.write_text(json.dumps({"EngineAssociation": "5.7"}))
            self.assertEqual(provenance.read_engine_association(up), "5.7")
            self.assertIsNone(provenance.read_engine_association(Path(td) / "missing"))

    def test_aura_plugin_version(self):
        with TemporaryDirectory() as td:
            up = Path(td) / "Aura.uplugin"
            up.write_text(json.dumps({"VersionName": "0.13.13", "Version": 55}))
            self.assertEqual(provenance.read_aura_plugin_version(up), "0.13.13")


class TestTelemetryVerdicts(unittest.TestCase):
    def test_model_verdict_unresolved_is_not_proxied_by_wire_model(self):
        # The sub-agent model is DECOUPLED from the main-loop wire model and its one
        # authoritative source (the vendor billing ledger) is out of this release, so
        # the verdict is NOT available and model is None. The wire_model is explicitly
        # NOT a proxy, and it is still not pinned to the sonnet-4.5 hardcoded default.
        v = provenance.subagent_model_verdict("claude-sonnet-4-6", "sonnet-4.6")
        self.assertFalse(v["available"])
        self.assertIsNone(v["model"])
        self.assertIsNone(v["source"])
        self.assertFalse(v["pinned_to_default"])  # still NOT sonnet-4.5
        self.assertIn("wire_model_is_not_a_proxy", v)
        self.assertEqual(v["main_loop_wire_model"], "claude-sonnet-4-6")
        self.assertIn("DECOUPLED", v["derivation"])

    def test_model_verdict_names_no_vendor_route(self):
        # The verdict must not carry a route back to the private service, and the
        # local :3008 lines must be labelled a crosscheck, not the verdict.
        v = provenance.subagent_model_verdict("claude-sonnet-4-6", "sonnet-4.6")
        self.assertNotIn("authoritative_routes", v)
        self.assertIn("local_crosscheck_only", v)

    def test_model_verdict_unavailable_when_no_wire_model(self):
        v = provenance.subagent_model_verdict(None, None)
        self.assertFalse(v["available"])
        self.assertIsNone(v["model"])

    def test_token_verdict_is_absent_not_zero(self):
        t = provenance.subagent_token_verdict()
        self.assertFalse(t["available"])
        self.assertEqual(t["reachable"], "cloud")
        self.assertIn("not_zero", t)
        # Must NOT fabricate a number a consumer could sum into a run cost.
        self.assertNotIn("credits", t)
        self.assertNotIn("totals", t)
        self.assertNotIn("usd", t)


class TestRunManifest(unittest.TestCase):
    def test_manifest_assembles_and_writes(self):
        with TemporaryDirectory() as td:
            repo = Path(td)
            proj = repo / provenance.PROJECT_REL
            proj.mkdir(parents=True)
            (proj / "CraftBenchTemplate.uproject").write_text(
                json.dumps({"EngineAssociation": "5.7"}))
            uplugin = repo / "Aura.uplugin"
            uplugin.write_text(json.dumps({"VersionName": "0.13.13"}))
            run = repo / "run"

            class _GR:
                stdout = "b2435dadDEADBEEF\n"
            fake_git = lambda *a, **k: _GR()

            m = provenance.build_run_manifest(
                task_id="realistic-collectible-coin", run_dir=run,
                model_key="sonnet-4.6", wire_model="claude-sonnet-4-6",
                ts_start=100.0, ts_end=1202.2, repo=repo,
                exposed_tool_count=139, aura_uplugin=uplugin,
                git_runner=fake_git, now=999.0)
            self.assertEqual(m["git_sha"], "b2435dadDEADBEEF")
            self.assertEqual(m["engine_version"], "5.7")
            self.assertEqual(m["aura_plugin_version"], "0.13.13")
            self.assertEqual(m["wire_model"], "claude-sonnet-4-6")
            self.assertEqual(m["exposed_tool_count"], 139)
            self.assertEqual(m["elapsed_s"], 1102.2)
            # Key kept for wire-format stability; the hash manifest retired
            # 2026-07-16 (git provenance = pinning substrate_revision) -> null.
            self.assertIn("substrate_hashes_ref", m)
            self.assertIsNone(m["substrate_hashes_ref"])
            self.assertFalse(m["subagent_model"]["pinned_to_default"])
            # No caller-supplied verdicts -> the explicit UNRESOLVED ones.
            self.assertFalse(m["subagent_model"]["available"])
            self.assertFalse(m["subagent_token"]["available"])
            self.assertEqual(m["subagent_token"]["reachable"], "cloud")
            self.assertTrue((run / "run_manifest.json").exists())

    def test_git_sha_none_on_runner_failure(self):
        def boom(*a, **k):
            raise OSError("no git")
        self.assertIsNone(provenance._git_sha(Path("/x"), boom))


# ---------------------------------------------------------------------------
# (e) capture_subagent_telemetry + the :3008 billed-line parser
# ---------------------------------------------------------------------------

class TestBilledParser(unittest.TestCase):
    _LOG = (
        "some unrelated line\n"
        "[usage] billed thread=aura_tool_1780585500918_3zo7p90v3 provider=anthropic "
        "model=opus-4.7 credits=140940\n"
        "noise\n"
        "[usage] billed thread=aura_tool_999_abc provider=anthropic "
        "model=sonnet-4.6 credits=251721\n"
    )

    def test_parses_all_billed_lines(self):
        recs = provenance.parse_vercelserver_billed(self._LOG)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["model"], "opus-4.7")
        self.assertEqual(recs[0]["credits"], 140940)
        self.assertEqual(recs[1]["model"], "sonnet-4.6")

    def test_thread_filter_substring(self):
        recs = provenance.parse_vercelserver_billed(self._LOG, thread_filter="999_abc")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["credits"], 251721)

    def test_empty_text(self):
        self.assertEqual(provenance.parse_vercelserver_billed(""), [])


class TestCaptureSubagentTelemetry(unittest.TestCase):
    def test_unresolved_model_and_local_crosscheck_present(self):
        # The model verdict is UNRESOLVED and the tokens are ABSENT, but the local
        # :3008 crosscheck still runs and is recorded as evidence beside them.
        with TemporaryDirectory() as td:
            log = Path(td) / "v3008.log"
            log.write_text(
                "[usage] billed thread=aura_tool_1 provider=anthropic "
                "model=sonnet-4.6 credits=100\n")
            run = Path(td) / "run"
            t = provenance.capture_subagent_telemetry(
                wire_model="claude-sonnet-4-6", model_key="sonnet-4.6",
                run_dir=run, vercelserver_log=log)
            self.assertFalse(t["model"]["available"])  # decoupled, not resolved
            self.assertIsNone(t["model"]["model"])
            self.assertFalse(t["model"]["pinned_to_default"])
            self.assertEqual(t["model_local_crosscheck"]["count"], 1)
            self.assertFalse(t["tokens"]["available"])
            self.assertEqual(t["tokens"]["reachable"], "cloud")
            self.assertTrue((run / "subagent_telemetry.json").exists())

    def test_crosscheck_line_is_not_promoted_to_the_verdict(self):
        # A local billed line names a model; it stays EVIDENCE. Promoting it would
        # report a model the run may never have used.
        with TemporaryDirectory() as td:
            log = Path(td) / "v3008.log"
            log.write_text(
                "[usage] billed thread=aura_tool_1 provider=anthropic "
                "model=opus-4.7 credits=100\n")
            t = provenance.capture_subagent_telemetry(
                wire_model="claude-sonnet-4-6", vercelserver_log=log)
            self.assertEqual(
                t["model_local_crosscheck"]["billed_lines"][0]["model"], "opus-4.7")
            self.assertIsNone(t["model"]["model"])
            self.assertFalse(t["model"]["available"])

    def test_empty_crosscheck_when_log_absent_is_not_failure(self):
        with TemporaryDirectory() as td:
            t = provenance.capture_subagent_telemetry(
                wire_model="claude-sonnet-4-6",
                vercelserver_log=Path(td) / "nope.log")
            self.assertEqual(t["model_local_crosscheck"]["count"], 0)
            self.assertFalse(t["model"]["available"])  # decoupled, unresolved


# ---------------------------------------------------------------------------
# capture_all — the thin integration hook (offline, best-effort)
# ---------------------------------------------------------------------------

class TestCaptureAll(unittest.TestCase):
    def test_capture_all_writes_index_and_survives_partial_failure(self):
        # Editor down (tool manifest fails) + assets disabled: index still complete.
        with TemporaryDirectory() as td:
            repo = Path(td)
            proj = repo / provenance.PROJECT_REL
            proj.mkdir(parents=True)
            (proj / "CraftBenchTemplate.uproject").write_text(
                json.dumps({"EngineAssociation": "5.7"}))
            run = repo / "run"

            # Monkeypatch the GW opener to fail (editor down) and git to a stub.
            orig_opener = provenance._default_mcp_opener
            orig_run = provenance.subprocess.run
            try:
                provenance._default_mcp_opener = (
                    lambda url, timeout: (_ for _ in ()).throw(OSError("down")))

                class _GR:
                    stdout = "abc123\n"
                provenance.subprocess.run = lambda *a, **k: _GR()

                idx = provenance.capture_all(
                    task_id="t1", run_dir=run, model_key="sonnet-4.6",
                    wire_model="claude-sonnet-4-6", ts_start=time.time(),
                    repo=repo, capture_assets_enabled=False,
                    log=lambda m: None)
            finally:
                provenance._default_mcp_opener = orig_opener
                provenance.subprocess.run = orig_run

            self.assertIn("tool_manifest", idx)
            self.assertIn("screenshots", idx)
            self.assertIn("subagent_telemetry", idx)
            self.assertIn("run_manifest", idx)
            self.assertEqual(idx["run_manifest"]["engine_version"], "5.7")
            # The sub-agent model is UNRESOLVED and its cost ABSENT — the index key
            # is kept for wire-format stability but must be null, never 0.0.
            self.assertFalse(idx["subagent_telemetry"]["model_available"])
            self.assertIsNone(idx["subagent_telemetry"]["model"])
            self.assertFalse(idx["subagent_telemetry"]["tokens_available"])
            self.assertIn("tokens_usd", idx["subagent_telemetry"])
            self.assertIsNone(idx["subagent_telemetry"]["tokens_usd"])
            self.assertTrue((run / "provenance.json").exists())
            self.assertTrue((run / "run_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
