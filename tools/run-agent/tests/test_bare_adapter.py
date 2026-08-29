"""Unit tests for the `bare` arm: the wire normaliser, the five tools, the adapter.

Fully offline — every live seam (`post_json`, `llm_call`, `dispatch`) is injected,
matching how the aura-mcp adapter's tests work. No API key, no network, no editor.

The properties worth pinning here are the ones whose failure would be SILENT and
would bias a cross-model comparison rather than crash it:
  * malformed tool arguments become a model-visible tool error, never an exception
    (otherwise the harness converts a weak model's syntax error into a harness
    fault and drops the rep from the denominator — the denominator rule);
  * a path escaping the workspace is refused;
  * `write_file` does not translate line endings;
  * a non-zero shell exit is OUTPUT, not a tool error;
  * mcp_tool_use_count is 0 (these tools are not MCP tools);
  * token counts survive into AgentResult (they used to be dropped);
  * the shared loop's system prompt is the one WE passed, not aura-mcp's.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import bare, bare_wire  # noqa: E402
from adapters.aura_mcp import build_system_prompt  # noqa: E402
from adapters.registry import make_adapter  # noqa: E402


def _completion(text=None, tool_calls=None, prompt_tokens=11, completion_tokens=7,
                model="vendor/some-model"):
    msg = {"content": text}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [{"message": msg}],
        "usage": {"prompt_tokens": prompt_tokens,
                  "completion_tokens": completion_tokens},
        "model": model,
    }


def _tc(call_id, name, arguments):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": arguments}}


class TestWireShapeConversion(unittest.TestCase):

    def test_tools_convert_to_openai_function_shape(self):
        out = bare_wire.anthropic_tools_to_openai(bare.BARE_TOOLS)
        self.assertEqual(len(out), len(bare.BARE_TOOLS))
        self.assertTrue(all(t["type"] == "function" for t in out))
        self.assertEqual(
            {t["function"]["name"] for t in out},
            {"read_file", "write_file", "list_dir", "grep", "bash"},
        )
        for t in out:
            self.assertIsInstance(t["function"]["parameters"], dict)

    def test_a_tool_with_no_schema_still_sends_an_object(self):
        """Some endpoints 400 on a null parameters field."""
        out = bare_wire.anthropic_tools_to_openai([{"name": "x"}])
        self.assertEqual(out[0]["function"]["parameters"],
                         {"type": "object", "properties": {}})

    def test_system_prompt_becomes_the_first_message(self):
        msgs = bare_wire.anthropic_messages_to_openai(
            [{"role": "user", "content": "do it"}], "SYS")
        self.assertEqual(msgs[0], {"role": "system", "content": "SYS"})
        self.assertEqual(msgs[1], {"role": "user", "content": "do it"})

    def test_assistant_tool_use_becomes_tool_calls(self):
        anth = [{"role": "assistant", "content": [
            {"type": "text", "text": "thinking"},
            {"type": "tool_use", "id": "c1", "name": "read_file",
             "input": {"path": "a.cpp"}},
        ]}]
        msgs = bare_wire.anthropic_messages_to_openai(anth, None)
        self.assertEqual(msgs[0]["role"], "assistant")
        self.assertEqual(msgs[0]["content"], "thinking")
        self.assertEqual(msgs[0]["tool_calls"][0]["id"], "c1")
        self.assertEqual(
            json.loads(msgs[0]["tool_calls"][0]["function"]["arguments"]),
            {"path": "a.cpp"})

    def test_assistant_with_only_tool_calls_sends_null_content(self):
        """content="" is rejected by some endpoints when tool_calls is present."""
        anth = [{"role": "assistant", "content": [
            {"type": "tool_use", "id": "c1", "name": "bash", "input": {}}]}]
        msgs = bare_wire.anthropic_messages_to_openai(anth, None)
        self.assertIsNone(msgs[0]["content"])

    def test_each_tool_result_becomes_its_own_tool_message(self):
        """One `role: tool` per result, keyed by tool_call_id.

        Collapsing a multi-tool turn into one message loses the pairing and makes
        the results unattributable to their calls.
        """
        anth = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "c1", "content": "AAA"},
            {"type": "tool_result", "tool_use_id": "c2", "content": "BBB"},
        ]}]
        msgs = bare_wire.anthropic_messages_to_openai(anth, None)
        self.assertEqual(len(msgs), 2)
        self.assertEqual([m["role"] for m in msgs], ["tool", "tool"])
        self.assertEqual([m["tool_call_id"] for m in msgs], ["c1", "c2"])
        self.assertEqual([m["content"] for m in msgs], ["AAA", "BBB"])

    def test_response_converts_to_anthropic_blocks_and_usage(self):
        got = bare_wire.openai_response_to_anthropic(
            _completion(text="hello", tool_calls=[
                _tc("c9", "write_file", '{"path":"x.cpp","content":"y"}')]))
        self.assertEqual(got["content"][0], {"type": "text", "text": "hello"})
        tu = got["content"][1]
        self.assertEqual(tu["type"], "tool_use")
        self.assertEqual(tu["name"], "write_file")
        self.assertEqual(tu["input"], {"path": "x.cpp", "content": "y"})
        # Anthropic key names, because run_loop reads those.
        self.assertEqual(got["usage"]["input_tokens"], 11)
        self.assertEqual(got["usage"]["output_tokens"], 7)
        # Provider accounting (cost / cache / reasoning) is absent here and must
        # read as UNKNOWN, never as zero — a 0 would silently claim "this call was
        # free" and pollute a cost table.
        self.assertIsNone(got["usage"]["cost_usd"])
        self.assertIsNone(got["usage"]["cache_read_tokens"])
        self.assertEqual(got["model"], "vendor/some-model")

    def test_malformed_arguments_do_not_raise(self):
        """THE property. A weak model's bad JSON must not abort the drive.

        If this raised, the model's own syntax error would surface as a harness
        fault and the rep would leave the denominator — systematically flattering
        exactly the models that make this mistake.
        """
        got = bare_wire.openai_response_to_anthropic(
            _completion(tool_calls=[_tc("c1", "read_file", "{not json")]))
        tu = got["content"][0]
        self.assertEqual(tu["type"], "tool_use")
        self.assertIn(bare_wire.MALFORMED_ARGS_KEY, tu["input"])

    def test_arguments_that_decode_to_a_non_object_are_malformed(self):
        got = bare_wire.openai_response_to_anthropic(
            _completion(tool_calls=[_tc("c1", "read_file", "[1,2]")]))
        self.assertIn(bare_wire.MALFORMED_ARGS_KEY, got["content"][0]["input"])

    def test_missing_usage_is_zero_not_a_crash(self):
        got = bare_wire.openai_response_to_anthropic({"choices": [{"message": {}}]})
        self.assertEqual(got["usage"]["input_tokens"], 0)
        self.assertEqual(got["usage"]["output_tokens"], 0)
        self.assertIsNone(got["usage"]["cost_usd"])
        self.assertEqual(got["content"], [])

    def test_call_posts_to_chat_completions_with_bearer_auth(self):
        seen = {}

        def fake_post(url, body, headers, timeout):
            seen.update(url=url, body=body, headers=headers, timeout=timeout)
            return _completion(text="done")

        bare_wire.call_openai_compatible(
            api_key="sk-test", model="vendor/m", system="SYS",
            messages=[{"role": "user", "content": "go"}],
            tools=bare.BARE_TOOLS, max_tokens=99, timeout=12.0,
            base_url="https://example.test/api/v1", post_json=fake_post)

        self.assertEqual(seen["url"],
                         "https://example.test/api/v1/chat/completions")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(seen["body"]["model"], "vendor/m")
        self.assertEqual(seen["body"]["max_tokens"], 99)
        self.assertEqual(seen["body"]["messages"][0]["role"], "system")
        self.assertEqual(seen["timeout"], 12.0)

    def test_default_base_url_is_the_openai_compatible_one(self):
        """NOT the Anthropic-compatible base the `openrouter` backend uses."""
        self.assertTrue(bare_wire.DEFAULT_BASE_URL.endswith("/api/v1"))


class TestDispatchFiles(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _d(self, name, **inp):
        return bare.dispatch_files("", name, inp, workspace_dir=self.root)

    def test_write_then_read_round_trips(self):
        r = self._d("write_file", path="Source/a.cpp", content="int x = 1;\n")
        self.assertTrue(r["bSuccess"])
        r = self._d("read_file", path="Source/a.cpp")
        self.assertTrue(r["bSuccess"])
        self.assertEqual(r["result_text"], "int x = 1;\n")

    def test_write_file_does_not_translate_line_endings(self):
        """A submitted source file must land byte-for-byte as the model wrote it.

        Without newline="", Python rewrites every \\n to \\r\\n on Windows, so a
        hash- or diff-based check would disagree with the model's own output.
        """
        self._d("write_file", path="lf.txt", content="a\nb\n")
        self.assertEqual((self.root / "lf.txt").read_bytes(), b"a\nb\n")

    def test_path_escape_is_refused(self):
        for path in ("../outside.txt", "Source/../../outside.txt"):
            with self.subTest(path=path):
                r = self._d("write_file", path=path, content="x")
                self.assertFalse(r["bSuccess"])
                self.assertIn("outside the project", r["error"])

    def test_absolute_path_is_refused(self):
        other = Path(tempfile.gettempdir()).resolve() / "cb-bare-escape.txt"
        r = self._d("write_file", path=str(other), content="x")
        self.assertFalse(r["bSuccess"])
        self.assertFalse(other.exists())

    def test_read_of_missing_file_is_a_tool_error_not_a_raise(self):
        r = self._d("read_file", path="nope.cpp")
        self.assertFalse(r["bSuccess"])
        self.assertIn("could not read", r["error"])

    def test_write_file_rejects_non_string_content(self):
        r = self._d("write_file", path="a.txt", content={"not": "a string"})
        self.assertFalse(r["bSuccess"])

    def test_list_dir(self):
        (self.root / "sub").mkdir()
        (self.root / "f.txt").write_text("x")
        r = self._d("list_dir", path=".")
        self.assertTrue(r["bSuccess"])
        self.assertIn("sub/", r["result_text"])
        self.assertIn("f.txt", r["result_text"])

    def test_list_dir_on_a_file_is_an_error(self):
        (self.root / "f.txt").write_text("x")
        self.assertFalse(self._d("list_dir", path="f.txt")["bSuccess"])

    def test_unknown_tool_is_a_tool_error(self):
        r = self._d("teleport")
        self.assertFalse(r["bSuccess"])
        self.assertIn("unknown tool", r["error"])

    def test_malformed_args_become_a_recoverable_tool_error(self):
        r = bare.dispatch_files(
            "", "read_file", {bare_wire.MALFORMED_ARGS_KEY: "{oops"},
            workspace_dir=self.root)
        self.assertFalse(r["bSuccess"])
        self.assertIn("not valid JSON", r["error"])

    def test_bash_nonzero_exit_is_output_not_a_tool_error(self):
        """A failing compile is information, not a tool malfunction.

        Marking it is_error invites the model to treat its own broken code as a
        harness problem and retry the tool instead of fixing the code.
        """
        r = bare.dispatch_files("", "bash", {"command": "exit 3"},
                                workspace_dir=self.root)
        self.assertTrue(r["bSuccess"])
        self.assertIn("exit 3", r["result_text"])

    def test_bash_requires_a_command(self):
        self.assertFalse(self._d("bash", command="")["bSuccess"])

    def test_output_is_truncated(self):
        big = "x" * (bare.MAX_TOOL_OUTPUT_CHARS + 5000)
        (self.root / "big.txt").write_text(big)
        r = self._d("read_file", path="big.txt")
        self.assertLessEqual(len(r["result_text"]), bare.MAX_TOOL_OUTPUT_CHARS)


class TestBareAdapter(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.prompt = self.root / "PROMPT.md"
        self.prompt.write_text("Make it work.", encoding="utf-8")

    def test_registry_resolves_the_slug(self):
        a = make_adapter("bare:vendor/model-x")
        self.assertEqual(a.name, "bare:vendor/model-x")
        self.assertEqual(a.model, "vendor/model-x")

    def test_no_key_and_no_injected_seam_fails_cleanly(self):
        a = bare.BareAdapter(model="m", api_key="")
        import os
        saved = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            r = a.run(self.prompt, self.root, max_turns=3, timeout_s=60)
        finally:
            if saved is not None:
                os.environ["OPENROUTER_API_KEY"] = saved
        self.assertEqual(r.exit_code, 1)
        self.assertIn("no API key", r.summary)

    def test_a_one_turn_run_with_no_tool_calls_completes(self):
        a = bare.BareAdapter(
            model="m", api_key="k",
            llm_call=lambda **kw: {"content": [{"type": "text", "text": "done"}],
                                   "usage": {"input_tokens": 5,
                                             "output_tokens": 2}})
        r = a.run(self.prompt, self.root, max_turns=3, timeout_s=60)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.summary, "done")
        self.assertEqual(r.num_turns, 1)
        self.assertEqual(r.tool_use_count, 0)

    def test_tokens_reach_the_agent_result(self):
        """They were collected and then dropped before 2026-08-17.

        These are the only cross-provider-comparable usage numbers: cost_usd is
        None for any model id without haiku/sonnet/opus in it, which is every
        non-Anthropic model.
        """
        a = bare.BareAdapter(
            model="vendor/gpt-ish", api_key="k",
            llm_call=lambda **kw: {"content": [{"type": "text", "text": "ok"}],
                                   "usage": {"input_tokens": 1234,
                                             "output_tokens": 56}})
        r = a.run(self.prompt, self.root, max_turns=2, timeout_s=60)
        self.assertEqual(r.tokens_in, 1234)
        self.assertEqual(r.tokens_out, 56)
        self.assertIsNone(r.cost_usd)  # unknown vendor -> no fabricated dollars

    def test_tool_calls_are_dispatched_and_counted_as_non_mcp(self):
        turns = []

        def fake_llm(**kw):
            turns.append(kw)
            if len(turns) == 1:
                return {"content": [{"type": "tool_use", "id": "c1",
                                     "name": "write_file",
                                     "input": {"path": "out.cpp",
                                               "content": "int x;"}}],
                        "usage": {"input_tokens": 3, "output_tokens": 1}}
            return {"content": [{"type": "text", "text": "finished"}],
                    "usage": {"input_tokens": 4, "output_tokens": 1}}

        a = bare.BareAdapter(model="m", api_key="k", llm_call=fake_llm)
        r = a.run(self.prompt, self.root, max_turns=5, timeout_s=60)

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.tool_names, ["write_file"])
        self.assertEqual(r.tool_use_count, 1)
        # Local file tools are NOT MCP tools. The shared mapper's default would
        # have reported 1 here and mislabelled a file edit as MCP traffic.
        self.assertEqual(r.mcp_tool_use_count, 0)
        self.assertEqual((self.root / "out.cpp").read_text(encoding="utf-8"), "int x;")

    def test_the_system_prompt_is_ours_not_aura_mcps(self):
        """A silent fairness lever: a different system prompt per arm would
        invalidate the comparison with nothing in any log to reveal it."""
        seen = {}

        def fake_llm(**kw):
            seen["system"] = kw.get("system")
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

        bare.BareAdapter(model="m", api_key="k", llm_call=fake_llm).run(
            self.prompt, self.root, max_turns=1, timeout_s=60)
        self.assertEqual(seen["system"], bare.BARE_SYSTEM_PROMPT)
        self.assertNotEqual(seen["system"], build_system_prompt())
        # And it must not leak Aura's one-tool instructions.
        self.assertNotIn("execute_unreal_python", seen["system"])

    def test_the_prompt_is_the_file_verbatim(self):
        """Prompt parity with the other arms is the point; nothing re-derives it."""
        seen = {}

        def fake_llm(**kw):
            seen["messages"] = kw.get("messages")
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

        bare.BareAdapter(model="m", api_key="k", llm_call=fake_llm).run(
            self.prompt, self.root, max_turns=1, timeout_s=60)
        self.assertEqual(seen["messages"][0],
                         {"role": "user", "content": "Make it work."})

    def test_transport_failure_is_an_adapter_error_not_a_model_failure(self):
        def boom(**kw):
            raise OSError("connection reset")

        a = bare.BareAdapter(model="m", api_key="k", llm_call=boom)
        r = a.run(self.prompt, self.root, max_turns=2, timeout_s=60)
        self.assertEqual(r.exit_code, 1)
        self.assertIn("connection reset", r.summary)

    def test_max_turns_zero_is_capped_not_infinite(self):
        calls = {"n": 0}

        def always_tool(**kw):
            calls["n"] += 1
            if calls["n"] > 20:
                return {"content": [{"type": "text", "text": "stop"}],
                        "usage": {}}
            return {"content": [{"type": "tool_use", "id": "c", "name": "bash",
                                 "input": {"command": "true"}}], "usage": {}}

        a = bare.BareAdapter(model="m", api_key="k", llm_call=always_tool)
        r = a.run(self.prompt, self.root, max_turns=0, timeout_s=60)
        self.assertEqual(r.exit_code, 0)
        self.assertGreater(r.num_turns, 1)


class TestCbRouting(unittest.TestCase):
    """`bare` must route to the BASELINE runner, not the Aura product stack.

    Regression for the gap this arm shipped with: `bare:x` has a colon, so
    `_backend_of` returned "bare", and because "bare" was absent from
    `_BASELINE_BACKENDS`, `_is_aura_backend` answered True — every bare run would
    have tried to bring up vercel :3000 / client :3002 / a dev browser / Supabase
    auth for an arm that needs none of it, and failed on a machine with no Aura.
    Nothing caught it: 34 adapter tests passed while the command was unusable,
    because the adapter and the routing are tested in different places.
    """

    def setUp(self):
        from aura_rig import cb
        self.cb = cb

    def test_bare_is_a_baseline_backend(self):
        self.assertIn("bare", self.cb._BASELINE_BACKENDS)

    def test_bare_slug_does_not_route_to_aura(self):
        for slug in ("bare:openai/gpt-5", "bare:x-ai/grok-4", "bare:vendor/m"):
            with self.subTest(slug=slug):
                self.assertEqual(self.cb._backend_of(slug), "bare")
                self.assertFalse(self.cb._is_unreal_mcp_backend(slug))

    def test_the_other_arms_still_route_where_they_did(self):
        self.assertTrue(self.cb._is_unreal_mcp_backend("unreal-mcp:sonnet"))
        # the aura-product backend is not part of this release

    def test_bare_takes_the_baseline_preflight_tier(self):
        """An Aura-tier gate would demand a stack this arm never brings up."""
        from aura_rig import envgate
        self.assertEqual(
            envgate.tier_for_model("bare:openai/gpt-5", self.cb._backend_of),
            "baseline")


if __name__ == "__main__":
    unittest.main()
