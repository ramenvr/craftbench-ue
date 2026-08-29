"""LIVE smoke for the `bare` arm. NOT a unit test — it spends tokens.

    py -3.13 tools/run-agent/tests/smoke_bare_live.py [<provider/model> ...]

Unit tests cover the wire conversion and every tool with injected seams, which
proves the code is self-consistent and proves NOTHING about whether a real
provider accepts our request shape. This closes that gap on the cheapest possible
task: a two-file edit in a temp directory, no Unreal, no build, ~4 turns.

What it is actually checking, per model:
  * the endpoint accepts our tools payload at all (a rejected schema 400s);
  * the model emits a tool_call our converter can read;
  * `write_file` lands real bytes on disk;
  * the loop terminates on its own instead of burning max_turns;
  * `usage` comes back populated — the only cross-provider-comparable cost
    figure we have.

Models differ in tool-calling reliability, so a FAIL here is a per-model result,
not necessarily a bug. It prints one line per model rather than asserting, so one
flaky provider does not mask the others.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_MODELS = [
    "deepseek/deepseek-v4-pro",
    "x-ai/grok-4.5",
    "z-ai/glm-5.3",
]

TASK = """Create a file `hello.txt` in the project root containing exactly the line:

CRAFTBENCH_BARE_OK

Then create `Source/note.md` containing one sentence describing what you did.
Use the tools. When both files exist, reply with plain text and stop.
"""


def main(argv):
    from adapters.bare import BareAdapter

    # Load the repo .env the sanctioned way rather than parsing it here, so this
    # exercises the same key-resolution path a real run uses.
    # `stack.load_aura_env` is the loader the cb path uses, and the only one that
    # exports OPENROUTER_API_KEY. `verify-single/repo_env.load_repo_env` exports
    # only CRAFTBENCH_*-prefixed names, so it silently does nothing for this key —
    # a real trap, since it neither errors nor warns.
    try:
        from aura_rig import stack
        stack.load_aura_env(stack.StackPaths())
    except Exception as e:  # noqa: BLE001
        print(f"note: could not load repo .env ({e}); relying on the environment")

    models = argv[1:] or DEFAULT_MODELS
    rows = []
    for model in models:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt = root / "PROMPT.md"
            prompt.write_text(TASK, encoding="utf-8")
            adapter = BareAdapter(model=model)
            res = adapter.run(prompt, root, max_turns=6, timeout_s=120)
            hello = (root / "hello.txt")
            note = (root / "Source" / "note.md")
            wrote_hello = hello.is_file() and "CRAFTBENCH_BARE_OK" in hello.read_text(
                encoding="utf-8", errors="replace")
            rows.append({
                "model": model,
                "exit": res.exit_code,
                "turns": res.num_turns,
                "tools": res.tool_use_count,
                "names": ",".join(res.tool_names or [])[:60],
                "tok_in": res.tokens_in,
                "tok_out": res.tokens_out,
                "mcp": res.mcp_tool_use_count,
                "hello": wrote_hello,
                "note": note.is_file(),
                "summary": (res.summary or "")[:70].replace("\n", " "),
            })

    print()
    print(f"{'model':28} {'exit':>4} {'turns':>5} {'tools':>5} {'mcp':>3} "
          f"{'tok_in':>7} {'tok_out':>7}  {'files':6} tool_names")
    for r in rows:
        files = ("H" if r["hello"] else "-") + ("N" if r["note"] else "-")
        print(f"{r['model']:28} {r['exit']:>4} {r['turns']:>5} {r['tools']:>5} "
              f"{r['mcp']:>3} {str(r['tok_in']):>7} {str(r['tok_out']):>7}  "
              f"{files:6} {r['names']}")
    for r in rows:
        if r["exit"] != 0 or not r["hello"]:
            print(f"  ! {r['model']}: {r['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
