"""unreal_mcp_config: the (tiny) --mcp-config resolver for Epic's editor MCP."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import unreal_mcp_config as umc  # noqa: E402


class TestResolveUrl(unittest.TestCase):
    def test_default_url(self):
        self.assertEqual(umc.resolve_url(env={}), "http://127.0.0.1:8000/mcp")

    def test_env_override(self):
        env = {"CB_UNREAL_MCP_URL": "http://127.0.0.1:8123/mcp"}
        self.assertEqual(umc.resolve_url(env=env), "http://127.0.0.1:8123/mcp")

    def test_blank_env_falls_back_to_default(self):
        self.assertEqual(umc.resolve_url(env={"CB_UNREAL_MCP_URL": "  "}),
                         umc.DEFAULT_URL)


class TestGeneratedConfig(unittest.TestCase):
    def test_config_shape_and_server_key(self):
        # Server key MUST be underscore (tools namespace mcp__unreal_mcp__*).
        cfg = umc.build_config_dict("http://127.0.0.1:8000/mcp")
        self.assertEqual(list(cfg["mcpServers"].keys()), ["unreal_mcp"])
        server = cfg["mcpServers"]["unreal_mcp"]
        self.assertEqual(server["type"], "http")
        self.assertEqual(server["url"], "http://127.0.0.1:8000/mcp")
        # HTTP server: no command/args (nothing for claude to spawn).
        self.assertNotIn("command", server)

    def test_resolve_writes_temp_json_honoring_env(self):
        with mock.patch.dict(os.environ,
                             {"CB_UNREAL_MCP_URL": "http://127.0.0.1:8777/mcp"},
                             clear=False):
            out = umc.resolve_unreal_mcp_config()
        self.assertTrue(out.is_file())
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["mcpServers"]["unreal_mcp"]["url"],
                         "http://127.0.0.1:8777/mcp")


if __name__ == "__main__":
    unittest.main()
