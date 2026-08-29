"""Runtime resolution of the Aura `--mcp-config` (no hardcoded paths)."""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import aura_mcp_config as amc  # noqa: E402


def _fake_plugin(root: Path) -> Path:
    """Build a minimal fake Aura plugin tree (MCP scripts + a portable python)."""
    plugin = root / "Aura"
    (plugin / "MCP").mkdir(parents=True)
    (plugin / "MCP" / "unreal_inspector.py").write_text("# stub", encoding="utf-8")
    (plugin / "MCP" / "unreal_editor.py").write_text("# stub", encoding="utf-8")
    plat = amc._platform_dir()
    exe = "python.exe" if sys.platform == "win32" else "python3"
    pybin = plugin / "PortablePython" / plat / exe
    pybin.parent.mkdir(parents=True)
    pybin.write_text("", encoding="utf-8")
    return plugin


class TestPluginResolution(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        # The substrate-junction location resolve_aura_plugin_dir checks by default.
        self.substrate = self.repo / "UE-projects" / "CraftBenchTemplate" / "Plugins"
        self.substrate.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_plugin_at_substrate_junction(self):
        _fake_plugin(self.substrate)  # -> .../Plugins/Aura
        got = amc.resolve_aura_plugin_dir(self.repo, env={})
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "Aura")

    def test_env_override_wins(self):
        plugin = _fake_plugin(self.tmp / "elsewhere")
        got = amc.resolve_aura_plugin_dir(
            self.repo, env={"CB_AURA_PLUGIN": str(plugin)})
        self.assertEqual(got, plugin.resolve())

    def test_returns_none_when_absent(self):
        self.assertIsNone(amc.resolve_aura_plugin_dir(self.repo, env={}))


class TestPythonResolution(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_prefers_bundled_portable_python(self):
        plugin = _fake_plugin(self.tmp)
        got = amc.resolve_mcp_python(plugin, env={})
        self.assertIsNotNone(got)
        self.assertIn("PortablePython", got)

    def test_env_override_wins(self):
        plugin = _fake_plugin(self.tmp)
        override = self.tmp / "my-python"
        override.write_text("", encoding="utf-8")
        got = amc.resolve_mcp_python(
            plugin, env={"CB_AURA_MCP_PYTHON": str(override)})
        self.assertEqual(Path(got), override)

    def test_none_when_no_interpreter(self):
        # Plugin dir with no PortablePython and no CB_UE_ROOT.
        bare = self.tmp / "Aura"
        (bare / "MCP").mkdir(parents=True)
        self.assertIsNone(amc.resolve_mcp_python(bare, env={}))


class TestConfigGeneration(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_config_dict_shape(self):
        plugin = _fake_plugin(self.tmp)
        cfg = amc.build_config_dict("py.exe", plugin)
        servers = cfg["mcpServers"]
        self.assertIn("unreal_inspector", servers)
        self.assertIn("unreal_editor", servers)
        for name, spec in servers.items():
            self.assertEqual(spec["type"], "stdio")
            self.assertEqual(spec["command"], "py.exe")
            self.assertEqual(len(spec["args"]), 1)
            self.assertTrue(spec["args"][0].endswith(".py"))
            # No foreign path leaks into the generated config. build_config_dict
            # derives every arg from the plugin_dir it was handed, so neither an
            # unsubstituted aura_mcp.json placeholder nor an absolute home path
            # baked in on whichever machine last edited that template can survive
            # into the config the agent is actually launched with.
            self.assertNotIn("<REPO_ROOT>", spec["args"][0])
            self.assertNotIn("<UE_ROOT>", spec["args"][0])

    def test_resolve_writes_machine_correct_config(self):
        repo = self.tmp / "repo"
        substrate = repo / "UE-projects" / "CraftBenchTemplate" / "Plugins"
        substrate.mkdir(parents=True)
        plugin = _fake_plugin(substrate)
        msgs = []
        path = amc.resolve_aura_mcp_config(repo, env={}, log=msgs.append)
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        insp = data["mcpServers"]["unreal_inspector"]
        # The generated args point at THIS machine's plugin scripts.
        self.assertEqual(
            Path(insp["args"][0]),
            (plugin / "MCP" / "unreal_inspector.py").resolve())
        self.assertEqual(msgs, [])  # clean resolution => no warnings

    def test_resolve_falls_back_to_legacy_when_plugin_absent(self):
        repo = self.tmp / "repo"
        (repo / "UE-projects").mkdir(parents=True)
        msgs = []
        path = amc.resolve_aura_mcp_config(repo, env={}, log=msgs.append)
        self.assertEqual(path, amc._LEGACY_CONFIG)
        self.assertTrue(any("could not locate" in m for m in msgs))

    def test_build_config_dict_applies_server_env(self):
        plugin = _fake_plugin(self.tmp)
        cfg = amc.build_config_dict(
            "py.exe", plugin, server_env={"LOCALAPPDATA": r"C:\scoped"})
        for spec in cfg["mcpServers"].values():
            self.assertEqual(spec["env"], {"LOCALAPPDATA": r"C:\scoped"})
        # Default stays empty (unchanged behavior for non-cb callers).
        for spec in amc.build_config_dict("py.exe", plugin)["mcpServers"].values():
            self.assertEqual(spec["env"], {})

    def test_resolve_points_mcp_at_scoped_localappdata(self):
        # The token-store fix (2026-08-09): CB_AURA_MCP_LOCALAPPDATA (set by cb
        # to the bring-up's scoped store) becomes the MCP server's LOCALAPPDATA,
        # so it reads the fresh dev session token instead of the real/prod one.
        repo = self.tmp / "repo"
        substrate = repo / "UE-projects" / "CraftBenchTemplate" / "Plugins"
        substrate.mkdir(parents=True)
        _fake_plugin(substrate)
        path = amc.resolve_aura_mcp_config(
            repo, env={"CB_AURA_MCP_LOCALAPPDATA": r"C:\cbtmp\cb-aura-session"},
            log=lambda *_: None)
        data = json.loads(path.read_text(encoding="utf-8"))
        for spec in data["mcpServers"].values():
            self.assertEqual(
                spec["env"].get("LOCALAPPDATA"), r"C:\cbtmp\cb-aura-session")
        # Absent the env var, the server env stays empty.
        path2 = amc.resolve_aura_mcp_config(repo, env={}, log=lambda *_: None)
        data2 = json.loads(path2.read_text(encoding="utf-8"))
        for spec in data2["mcpServers"].values():
            self.assertEqual(spec["env"], {})


if __name__ == "__main__":
    unittest.main()
