"""Adapter slug parser: "claude-p:opus-4-7" → ClaudePAdapter(model="opus-4-7")."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.claude_p import ClaudePAdapter  # noqa: E402
from adapters.registry import make_adapter  # noqa: E402


class TestMakeAdapter(unittest.TestCase):
    def test_claude_p_with_model(self):
        a = make_adapter("claude-p:opus-4-7")
        self.assertIsInstance(a, ClaudePAdapter)
        self.assertEqual(a.model, "opus-4-7")
        self.assertEqual(a.name, "claude-p:opus-4-7")

    def test_claude_p_without_model(self):
        a = make_adapter("claude-p")
        self.assertIsInstance(a, ClaudePAdapter)
        self.assertIsNone(a.model)

    def test_unknown_backend_raises(self):
        # A genuinely-unknown backend still raises (and names the bad backend).
        with self.assertRaises(ValueError) as ctx:
            make_adapter("bogus:x")
        self.assertIn("bogus", str(ctx.exception).lower())

    def test_openrouter_returns_claude_p_pointed_at_openrouter(self):
        env = {"OPENROUTER_API_KEY": "sk-or-test"}
        with mock.patch.dict(os.environ, env, clear=False):
            # Ensure no stray base-url override leaks in from the real env.
            os.environ.pop("OPENROUTER_BASE_URL", None)
            a = make_adapter("openrouter:openai/gpt-5")
        self.assertIsInstance(a, ClaudePAdapter)
        self.assertEqual(a.model, "openai/gpt-5")
        self.assertEqual(a.name, "openrouter:openai/gpt-5")
        self.assertTrue(a.strict_mcp)
        self.assertIsNotNone(a.env_overrides)
        # OpenRouter's Anthropic skin is at "/api" (the SDK appends /v1/messages);
        # "/api/v1" is the OpenAI-style base and would double the version segment.
        self.assertEqual(a.env_overrides["ANTHROPIC_BASE_URL"],
                         "https://openrouter.ai/api")
        # OpenRouter needs Bearer auth (ANTHROPIC_AUTH_TOKEN); the native
        # x-api-key (ANTHROPIC_API_KEY) is blanked to avoid a 401 / login clash.
        self.assertEqual(a.env_overrides["ANTHROPIC_AUTH_TOKEN"], "sk-or-test")
        self.assertEqual(a.env_overrides["ANTHROPIC_API_KEY"], "")

    def test_openrouter_honors_custom_base_url(self):
        env = {"OPENROUTER_API_KEY": "sk-or-test",
               "OPENROUTER_BASE_URL": "https://proxy.example/v1"}
        with mock.patch.dict(os.environ, env, clear=False):
            a = make_adapter("openrouter:openai/gpt-5")
        self.assertEqual(a.env_overrides["ANTHROPIC_BASE_URL"],
                         "https://proxy.example/v1")

    def test_openrouter_strips_quotes_from_env(self):
        # Common .env mistake: OPENROUTER_API_KEY="sk-or-..." (wrapped in quotes)
        # would otherwise become a quoted, malformed Bearer token -> 401.
        env = {"OPENROUTER_API_KEY": '"sk-or-quoted"',
               "OPENROUTER_BASE_URL": '"https://openrouter.ai/api"'}
        with mock.patch.dict(os.environ, env, clear=False):
            a = make_adapter("openrouter:openai/gpt-4o-mini")
        self.assertEqual(a.env_overrides["ANTHROPIC_AUTH_TOKEN"], "sk-or-quoted")
        self.assertEqual(a.env_overrides["ANTHROPIC_BASE_URL"], "https://openrouter.ai/api")

    def test_openrouter_without_key_raises_naming_the_var(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENROUTER_API_KEY", None)
            with self.assertRaises(ValueError) as ctx:
                make_adapter("openrouter:openai/gpt-5")
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_aura_mcp_with_model(self):
        a = make_adapter("aura-mcp:claude-haiku-4-5-20251001")
        self.assertEqual(a.name, "aura-mcp:claude-haiku-4-5-20251001")
        self.assertEqual(a.model, "claude-haiku-4-5-20251001")

    def test_aura_mcp_default_model(self):
        a = make_adapter("aura-mcp")
        self.assertTrue(a.name.startswith("aura-mcp:"))

    def test_aura_mcp_is_claude_p_restricted_to_aura_tools(self):
        # Authentic aura-mcp runs through claude -p with Aura's MCP + denied
        # generic actuators (so it can only act THROUGH Aura's tools).
        a = make_adapter("aura-mcp:claude-sonnet-4-6")
        self.assertIsInstance(a, ClaudePAdapter)
        self.assertTrue(a.strict_mcp)
        self.assertIsNotNone(a.mcp_config)
        self.assertIn("Write", a.disallowed_tools)
        self.assertIn("Bash", a.disallowed_tools)
        # Subagent/orchestration tools must be denied (else a child agent could
        # write files outside Aura, leaking past the restriction).
        self.assertIn("Agent", a.disallowed_tools)
        self.assertIn("Task", a.disallowed_tools)
        self.assertIn("Skill", a.disallowed_tools)

    def test_editor_self_destruct_tools_are_DENIED_not_merely_asked(self):
        """The two editor-lifecycle tools must be enforced where enforcement is
        possible, on BOTH mcp lanes.

        THE PRINCIPLE (owner, 2026-08-14): keep ONE preamble for every backend
        so runs stay comparable, and push backend-specific tool policy into the
        harness layer that can actually enforce it. Prose in a shared prompt is
        the weakest form of both — every backend pays for the tokens and none of
        them is bound by it.

        ``recompile_unreal_project`` shuts the editor down and expects the
        CALLER to relaunch; agents that skip that end their own session and the
        drive reports EDITOR-GONE (measured 2026-08-06, 5 reps lost across 3
        models). ``relaunch_editor`` defaults ``interactive`` to true, so it
        opens a windowed editor outside the harness's lifecycle that can outlive
        the session and collide with the next one. It had been banned in the
        preamble PROSE since that file was written and denied NOWHERE, i.e. a
        request rather than a rule on the two lanes that can enforce it — closed
        2026-08-14.

        Neither denial costs the agent anything measurable: the harness owns
        editor restarts, and the verifier always rebuilds the submission itself
        in a clean workdir (L1).

        aura-product is deliberately NOT covered here — Aura's client owns its
        tool set, so that lane cannot enforce a denylist and the preamble text
        is its only enforcement. That asymmetry is the sole reason the rule is
        still stated in tasks/PREAMBLE.md at all.
        """
        for slug in ("aura-mcp:claude-sonnet-4-6", "unreal-mcp:claude-haiku-4-5"):
            a = make_adapter(slug)
            for tool in ("recompile_unreal_project", "relaunch_editor"):
                self.assertIn(
                    tool, a.disallowed_tools,
                    f"{slug} can still call {tool} — the preamble ASKS agents not "
                    f"to, but this lane can enforce it, and a rule that is only "
                    f"asked for is not a rule",
                )

    def test_unreal_mcp_is_claude_code_plus_epic_mcp(self):
        # unreal-mcp = "Claude Code + Epic's Unreal MCP": Claude's file/shell tools
        # stay ENABLED (Epic's MCP has no C++ source tool, so Claude edits the C++);
        # only orchestration/web tools are denied. Contrast aura-mcp, which strips
        # Write/Edit/Bash because Aura's own tools include edit_cpp_file.
        a = make_adapter("unreal-mcp:claude-haiku-4-5")
        self.assertIsInstance(a, ClaudePAdapter)
        self.assertEqual(a.name, "unreal-mcp:claude-haiku-4-5")
        self.assertEqual(a.model, "claude-haiku-4-5")
        self.assertTrue(a.strict_mcp)
        self.assertIsNotNone(a.mcp_config)
        # Claude's editing tools are ALLOWED (this is the whole point).
        self.assertNotIn("Write", a.disallowed_tools)
        self.assertNotIn("Edit", a.disallowed_tools)
        self.assertNotIn("Bash", a.disallowed_tools)
        # ...but orchestration/web tools are still denied.
        self.assertIn("Agent", a.disallowed_tools)
        self.assertIn("WebSearch", a.disallowed_tools)
        # The generated config is an HTTP server keyed unreal_mcp (underscore).
        import json as _json
        data = _json.loads(Path(a.mcp_config).read_text(encoding="utf-8"))
        self.assertEqual(list(data["mcpServers"].keys()), ["unreal_mcp"])
        self.assertEqual(data["mcpServers"]["unreal_mcp"]["type"], "http")

    def test_unreal_mcp_default_model(self):
        a = make_adapter("unreal-mcp")
        self.assertEqual(a.name, "unreal-mcp:default")
        self.assertIsNone(a.model)

    def test_baseline_is_strict_no_aura_mcp(self):
        # Baseline must NOT silently inherit the operator's Aura MCP.
        a = make_adapter("claude-p")
        self.assertTrue(a.strict_mcp)
        self.assertIsNone(a.mcp_config)
        self.assertIsNone(a.disallowed_tools)

    def test_a_removed_private_surface_slug_is_refused_BY_NAME(self):
        """Replaces test_aura_mcp_bridge_is_legacy_adapter / test_aura_agent_*
        (removed 2026-08-28 with the private surfaces they constructed).

        Those three tests asserted that ``aura-mcp-bridge`` built an
        AuraMcpAdapter and ``aura-agent`` an AuraAgentAdapter. Both adapters
        drove Aura's private surfaces — the legacy external bridge and the local
        server-side agent loop — and neither ships in the public release;
        adapters/aura_agent.py is gone outright, so the old tests could not even
        be collected.

        What replaces them is the behaviour registry.py deliberately kept in
        their place: ``_REMOVED_BACKENDS`` (adapters/registry.py:412) turns each
        retired slug into a NAMED refusal rather than a bare "Unknown adapter
        backend". That distinction is the whole point of the table, so it is
        worth a test — an operator arriving with an older eval sheet must be told
        what happened to the slug, and a future edit that drops a row from the
        table would silently take that away.
        """
        for slug in ("aura-product:claude-sonnet-4-6", "aura-agent",
                     "aura-baseline", "aura-mcp-bridge:claude-haiku-4-5"):
            backend = slug.split(":", 1)[0]
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError) as ctx:
                    make_adapter(slug)
                msg = str(ctx.exception)
                self.assertIn(backend, msg,
                              f"{slug} was refused without naming itself")
                self.assertIn("public CraftBench-UE release", msg)
                # The refusal must point at what DOES ship, or it is just a wall.
                self.assertIn("claude-p", msg)
                self.assertIn("unreal-mcp", msg)


if __name__ == "__main__":
    unittest.main()
