"""Pure unit tests for ClaudePAdapter command construction + stream-json parsing.

The live subprocess invocation is not unit-tested against a real `claude` binary
(would require it in CI and would spend tokens). ``TestProxyAccounting`` DOES
drive ``run()`` with the subprocess stubbed, because the gateway accounting it
performs is not visible in any pure parse: the ids come from the proxy's usage
log, not from the CLI stream.
"""

import json
import subprocess
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.claude_p import (  # noqa: E402
    ClaudePAdapter,
    build_claude_command,
    parse_stream_json,
)
from aura_rig import proxy  # noqa: E402


class TestBuildClaudeCommand(unittest.TestCase):
    def test_includes_required_flags(self):
        cmd = build_claude_command(
            workspace_dir=Path("/tmp/run-agent-x/CraftBenchTemplate"),
            max_turns=25,
            claude_binary="claude",
        )
        self.assertEqual(cmd[0], "claude")
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)
        self.assertIn("--add-dir", cmd)
        self.assertIn(str(Path("/tmp/run-agent-x/CraftBenchTemplate")), cmd)
        self.assertIn("--permission-mode", cmd)
        # bypassPermissions: a single-shot agent runs its allowed tools without
        # prompts (auto denied MCP write tools in the parent — subagent-leak only).
        self.assertIn("bypassPermissions", cmd)
        self.assertIn("--max-turns", cmd)
        self.assertIn("25", cmd)

    def test_prompt_not_in_argv(self):
        # The prompt goes on stdin (so variadic tool flags can't swallow it).
        cmd = build_claude_command(workspace_dir=Path("/tmp/x"), max_turns=10)
        self.assertNotIn("do the thing", cmd)

    def test_baseline_default_has_no_mcp_or_tool_flags(self):
        cmd = build_claude_command(workspace_dir=Path("/tmp/x"), max_turns=10)
        self.assertNotIn("--disallowedTools", cmd)
        self.assertNotIn("--mcp-config", cmd)
        self.assertNotIn("--strict-mcp-config", cmd)

    def test_strict_mcp_with_no_config(self):
        # Baseline product: strict MCP, no config → zero MCP servers.
        cmd = build_claude_command(workspace_dir=Path("/tmp/x"), max_turns=10, strict_mcp=True)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertNotIn("--mcp-config", cmd)

    def test_aura_mcp_flags(self):
        # Authentic aura-mcp product: Aura's MCP config + denied generic actuators.
        cmd = build_claude_command(
            workspace_dir=Path("/tmp/x"), max_turns=10,
            mcp_config=Path("/cfg/aura_mcp.json"), strict_mcp=True,
            disallowed_tools=["Write", "Edit", "Bash"],
        )
        self.assertIn("--mcp-config", cmd)
        # str(Path(...)) so the separator matches the host (\ on Windows, / on POSIX).
        self.assertIn(str(Path("/cfg/aura_mcp.json")), cmd)
        self.assertIn("--strict-mcp-config", cmd)
        i = cmd.index("--disallowedTools")
        self.assertEqual(cmd[i + 1:i + 4], ["Write", "Edit", "Bash"])

    def test_model_specifier_passed_through(self):
        cmd = build_claude_command(
            workspace_dir=Path("/tmp/x"), max_turns=10, claude_binary="claude", model="opus-4-7",
        )
        self.assertIn("--model", cmd)
        self.assertIn("opus-4-7", cmd)

    def test_model_omitted_when_none(self):
        cmd = build_claude_command(
            workspace_dir=Path("/tmp/x"), max_turns=10, claude_binary="claude", model=None,
        )
        self.assertNotIn("--model", cmd)


class TestAdapterName(unittest.TestCase):
    def test_name_includes_model_slug(self):
        a = ClaudePAdapter(model="opus-4-7")
        self.assertEqual(a.name, "claude-p:opus-4-7")

    def test_name_when_no_model(self):
        a = ClaudePAdapter(model=None)
        self.assertEqual(a.name, "claude-p:default")


# Sample stream-json output covering: init, two tool_use events (one MCP),
# a text reply, and a result event. Whitespace-normalized to one event per line.
_SAMPLE = """
{"type":"system","subtype":"init","session_id":"abc-123","model":"claude-opus-4-7"}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t1","input":{"file_path":"/x"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__unreal_editor__edit_cpp_file","id":"t2","input":{}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t3","input":{}}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"All set."}]}}
{"type":"result","subtype":"success","result":"All set.","duration_ms":4321,"num_turns":4,"total_cost_usd":0.0789}
""".strip()


class TestParseStreamJson(unittest.TestCase):
    def test_counts_total_and_mcp_tools(self):
        parsed = parse_stream_json(_SAMPLE)
        self.assertEqual(parsed["tool_use_count"], 3)
        self.assertEqual(parsed["mcp_tool_use_count"], 1)
        self.assertEqual(
            parsed["tool_names"],
            ["Read", "mcp__unreal_editor__edit_cpp_file", "Edit"],
        )

    def test_extracts_result_fields(self):
        parsed = parse_stream_json(_SAMPLE)
        self.assertEqual(parsed["summary"], "All set.")
        self.assertEqual(parsed["num_turns"], 4)
        self.assertAlmostEqual(parsed["cost_usd"], 0.0789)
        self.assertEqual(parsed["session_id"], "abc-123")

    def test_models_used_from_init_event(self):
        # Attribution over labels (2026-07-22: bare `claude-p` silently ran
        # claude-fable-5): the init event's model id must be captured.
        parsed = parse_stream_json(_SAMPLE)
        self.assertEqual(parsed["models_used"], ["claude-opus-4-7"])

    def test_models_used_from_message_and_modelusage(self):
        stream = "\n".join([
            '{"type":"assistant","message":{"model":"claude-fable-5","content":[]}}',
            '{"type":"result","subtype":"success","result":"ok",'
            '"modelUsage":{"claude-fable-5":{"outputTokens":10}}}',
        ])
        parsed = parse_stream_json(stream)
        self.assertEqual(parsed["models_used"], ["claude-fable-5"])

    def test_models_used_empty_when_absent(self):
        parsed = parse_stream_json("")
        self.assertEqual(parsed["models_used"], [])

    def test_empty_stdout_returns_empty_counts(self):
        parsed = parse_stream_json("")
        self.assertEqual(parsed["tool_use_count"], 0)
        self.assertEqual(parsed["mcp_tool_use_count"], 0)
        self.assertEqual(parsed["tool_names"], [])
        self.assertIsNone(parsed["summary"])
        self.assertIsNone(parsed["cost_usd"])

    def test_malformed_lines_skipped(self):
        garbage = (
            "not json at all\n"
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"X"}]}}\n'
            "another bad line\n"
            '{"type":"result","result":"done","num_turns":1,"total_cost_usd":0.01}\n'
        )
        parsed = parse_stream_json(garbage)
        self.assertEqual(parsed["tool_use_count"], 1)
        self.assertEqual(parsed["tool_names"], ["X"])
        self.assertEqual(parsed["summary"], "done")

    def test_no_tool_use_no_mcp(self):
        text_only = (
            '{"type":"system","subtype":"init","session_id":"s","model":"m"}\n'
            '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}\n'
            '{"type":"result","result":"hi","num_turns":1,"total_cost_usd":0.001}\n'
        )
        parsed = parse_stream_json(text_only)
        self.assertEqual(parsed["tool_use_count"], 0)
        self.assertEqual(parsed["mcp_tool_use_count"], 0)
        self.assertEqual(parsed["tool_names"], [])
        self.assertEqual(parsed["summary"], "hi")


# A result event carrying a usage block (input/output token counts).
_SAMPLE_WITH_USAGE = """
{"type":"system","subtype":"init","session_id":"abc-123","model":"claude-opus-4-8"}
{"type":"assistant","message":{"content":[{"type":"text","text":"All set."}]}}
{"type":"result","subtype":"success","result":"All set.","duration_ms":4321,"num_turns":4,"total_cost_usd":0.0789,"usage":{"input_tokens":1234,"output_tokens":567,"cache_read_input_tokens":100}}
""".strip()


class TestParseStreamJsonTokens(unittest.TestCase):
    def test_extracts_tokens_from_usage_block(self):
        # tokens_in is TOTAL billable input: uncached + cache creation + cache read.
        # 1234 + 100 (this fixture has no cache_creation_input_tokens key at all,
        # which must not poison the sum). Asserting the bare input_tokens here is
        # what let the 2026-07-26 under-reporting bug live: on a real t0 run
        # input_tokens=8 while cache creation+read carried 186,788 more.
        parsed = parse_stream_json(_SAMPLE_WITH_USAGE)
        self.assertEqual(parsed["tokens_in"], 1334)
        self.assertEqual(parsed["tokens_out"], 567)

    def test_cache_components_surfaced_separately(self):
        # Creation (1.25x) and read (0.1x) bill at different rates, so the split
        # has to survive into the summary — it is what explains a session's first
        # run costing ~57% more than its second.
        parsed = parse_stream_json(_SAMPLE_WITH_USAGE)
        self.assertIsNone(parsed["cache_creation_tokens"])   # key absent in fixture
        self.assertEqual(parsed["cache_read_tokens"], 100)

    def test_tokens_in_sums_all_three_input_components(self):
        stream = (
            '{"type":"result","subtype":"success","result":"ok","num_turns":1,'
            '"total_cost_usd":0.5,"usage":{"input_tokens":8,'
            '"cache_creation_input_tokens":47586,"cache_read_input_tokens":139202,'
            '"output_tokens":1177}}'
        )
        parsed = parse_stream_json(stream)
        self.assertEqual(parsed["tokens_in"], 186796)   # the real G1 measurement
        self.assertEqual(parsed["cache_creation_tokens"], 47586)
        self.assertEqual(parsed["cache_read_tokens"], 139202)
        self.assertEqual(parsed["tokens_out"], 1177)

    def test_cache_fields_none_when_no_usage_block(self):
        parsed = parse_stream_json(_SAMPLE)
        self.assertIsNone(parsed["cache_creation_tokens"])
        self.assertIsNone(parsed["cache_read_tokens"])

    def test_tokens_none_when_no_usage_block(self):
        # The original sample's result event has no usage block — tokens stay None,
        # never fabricated as 0.
        parsed = parse_stream_json(_SAMPLE)
        self.assertIsNone(parsed["tokens_in"])
        self.assertIsNone(parsed["tokens_out"])

    def test_tokens_none_on_empty_stdout(self):
        parsed = parse_stream_json("")
        self.assertIsNone(parsed["tokens_in"])
        self.assertIsNone(parsed["tokens_out"])


class TestAgentResultTokenFields(unittest.TestCase):
    def test_agent_result_has_token_fields_defaulting_none(self):
        from adapters.base import AgentResult
        r = AgentResult(exit_code=0, transcript="", summary="x",
                        tool_use_count=0, duration_s=1.0)
        self.assertIsNone(r.tokens_in)
        self.assertIsNone(r.tokens_out)
        # asdict / to_json round-trip carries the new fields.
        import json as _json
        d = _json.loads(r.to_json())
        self.assertIn("tokens_in", d)
        self.assertIn("tokens_out", d)


def _gateway_line(gid, provider, reasoning):
    return {"ts": 1.0, "path": "/v1/messages?beta=true", "status": 200,
            "stream": True, "input_tokens": 0, "output_tokens": 100,
            "cache_read": 0, "cache_write": 0, "model": "qwen/qwen3.8-max",
            "response_id": gid, "generation_id": gid, "cost_usd": 0.001,
            "provider": provider, "reasoning_tokens": reasoning}


class TestProxyAccounting(unittest.TestCase):
    """The gateway's ids/backends/reasoning reach the AgentResult — or nothing does.

    They exist ONLY on the wire: the Claude Code CLI reports Anthropic
    first-party prices and no ids at all, so ``aura_rig.openrouter_cost`` has
    nothing to audit a published cost against unless this adapter reads the
    proxy's window. Dropping them is what left the recorded MCP-lane cells with no
    join key to audit against.
    """

    def _drive(self, adapter, log, appended, *, timeout=False):
        """Run the adapter with the CLI stubbed, appending ``appended`` mid-drive.

        ``timeout=True`` kills the stub the way an over-ceiling drive dies, so the
        adapter's OTHER exit path is exercised by the same harness.
        """
        def fake_run(*_a, **_kw):
            with open(log, "a", encoding="utf-8") as fh:
                for rec in appended:
                    fh.write(json.dumps(rec) + "\n")
            if timeout:
                raise subprocess.TimeoutExpired(
                    cmd="claude", timeout=60,
                    output=json.dumps({"type": "assistant"}).encode())
            return types.SimpleNamespace(
                returncode=0, stdout=json.dumps(
                    {"type": "result", "subtype": "success", "result": "done",
                     "num_turns": 2}) + "\n", stderr="")

        with TemporaryDirectory() as td:
            prompt = Path(td) / "PROMPT.md"
            prompt.write_text("do the thing", encoding="utf-8")
            with mock.patch.object(proxy, "USAGE_LOG", log):
                with mock.patch.object(subprocess, "run", fake_run):
                    return adapter.run(prompt, Path(td) / "ws", 10, 60)

    def test_routed_run_records_only_its_own_window(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            # A PRIOR drive's record. :41299's log is shared and append-only, so
            # claiming this id would attribute another run's spend to this one.
            log.write_text(json.dumps(
                _gateway_line("gen-earlier", "Together", 500)) + "\n",
                encoding="utf-8")
            adapter = ClaudePAdapter(
                model="qwen/qwen3.8-max",
                env_overrides={"ANTHROPIC_BASE_URL": proxy.CLI_BASE_URL})
            result = self._drive(adapter, log, [
                _gateway_line("gen-a", "Alibaba", 731),
                _gateway_line("gen-b", "Novita", 12),
            ])
            self.assertEqual(result.generation_ids, ["gen-a", "gen-b"])
            self.assertEqual(result.providers_served, ["Alibaba", "Novita"])
            self.assertEqual(result.reasoning_tokens, 743)

    def test_a_timed_out_drive_still_records_what_it_spent(self):
        # A timeout is a PAID drive that never printed a result event, so the proxy
        # window is the only surviving record of what those calls were — dropping it
        # makes the most expensive cell in a sweep the least auditable one.
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            log.write_text("", encoding="utf-8")
            adapter = ClaudePAdapter(
                model="qwen/qwen3.8-max",
                env_overrides={"ANTHROPIC_BASE_URL": proxy.CLI_BASE_URL})
            result = self._drive(
                adapter, log,
                [_gateway_line("gen-timed-out", "Alibaba", 4096)], timeout=True)
            self.assertEqual(result.exit_code, 124)
            self.assertEqual(result.generation_ids, ["gen-timed-out"])
            self.assertEqual(result.providers_served, ["Alibaba"])
            self.assertEqual(result.reasoning_tokens, 4096)

    def test_unrouted_run_claims_nothing_from_the_shared_log(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            log.write_text("", encoding="utf-8")
            # Straight at the gateway: these bytes never passed through :41299,
            # so every record in the window belongs to somebody else.
            adapter = ClaudePAdapter(
                model="qwen/qwen3.8-max",
                env_overrides={"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"})
            result = self._drive(adapter, log, [
                _gateway_line("gen-not-ours", "Alibaba", 731)])
            self.assertIsNone(result.generation_ids)
            self.assertIsNone(result.providers_served)
            self.assertIsNone(result.reasoning_tokens)


if __name__ == "__main__":
    unittest.main()
