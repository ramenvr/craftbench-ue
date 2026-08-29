# tools/run-agent — CraftBench Agent Harness

> **`run.py` is the graded spine.** Every arm `cb` dispatches — `claude-p`,
> `unreal-mcp`, `aura-mcp`, `openrouter`, `bare` — runs through this harness, so
> the only variable across arms is the tool layer. The day-to-day entry point is
> the **`cb`** launcher (`smoke` / `eval` / `bench` / `matrix` / `batch-eval` /
> `view` / `status` / `clean` / `down`); `run.py` is what `cb` shells out to, and
> is documented here for anyone reading or extending the arm definitions
> themselves. Flag reference: `cb help <command>`.

One-command runner: pick a task, pick an arm (`claude-p:<model>`,
`unreal-mcp:<model>`, `openrouter:<provider/model>`, `bare:<provider/model>`),
get back a PASS/FAIL verifier result with all run artefacts persisted.

## Quick start

```sh
python3 tools/run-agent/run.py \
    --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
    --model claude-p:opus \
    --ue-root "/Users/Shared/Epic Games/UE_5.8"
```

The `--model` value after `claude-p:` is passed straight to `claude --model`,
so any alias the CLI accepts works (`opus`, `sonnet`, `haiku`) as well as
full names (`claude-opus-4-7`, `claude-sonnet-4-6`, etc.).

The harness will pause once with an A2 pre-flight prompt asking you to
open the workspace `.uproject` in your existing UE editor:

```
======================================================================
A2 pre-flight: open this UE project in your editor, then press Enter:

  /tmp/run-agent-<id>/CraftBenchTemplate/CraftBenchTemplate.uproject

The Unreal MCP plugin in UE will then point at the workspace copy,
so the agent's MCP edits land here and the live template stays clean.
======================================================================
```

In UE: **File → Open Project** → pick the printed path. Wait for the
project to load, then press Enter in the terminal. Everything else is
automated.

Run artefacts land in `runs/<backend>/<UTC-timestamp>-<task>-<model>/` — each
backend gets its own folder (`runs/claude-p/`, `runs/unreal-mcp/`,
`runs/openrouter/`, ...); an explicit `--run-dir` is used as-is:

```
runs/claude-p/20260527-143052-gp-spawn-sequence-claude-p-opus/
    prompt.md                  # exactly what the agent saw (PROMPT.md from workspace)
    workspace_manifest.json    # which workspace files were writable
    agent_transcript.txt       # raw `claude -p` stdout
    agent_result.json          # parsed adapter result (exit_code, duration, summary)
    submission/                # the agent's diff, verifier-shaped
        Source/CraftBenchTemplate/...
    verifier_stdout.txt        # verifier's stdout
    verifier_stderr.txt        # verifier's stderr
    result.json                # top-level PASS/FAIL + durations + paths
```

Exit codes:

| | Meaning |
|---|---|
| 0 | overall PASS |
| 2 | agent produced no edits (empty submission) |
| 3 | verifier returned non-PASS |
| 4 | harness error (missing task section, etc.) |

## Agent backends — the arms

Every arm runs through the **same `claude -p` harness** (except `bare`, which is
our own minimal loop) so the only variable is the **tool layer**.
`adapters/registry.py` is the single source of truth; this table mirrors it. If
the two ever disagree, the code is right and this table is stale.

| `--model` slug | `claude -p` flags | Tool layer the model can actuate with | Measures |
|---|---|---|---|
| `claude-p[:<model>]` | `--strict-mcp-config` (no `--mcp-config` → **zero MCP**) | generic `Write`/`Edit`/`Bash` only | **Baseline**: a strong generalist coder, no engine tooling |
| `unreal-mcp[:<model>]` | `--mcp-config <epic's server> --strict-mcp-config --disallowedTools <orchestration>` | Epic's **first-party in-editor MCP server** *plus* Claude's own file/shell tools | The same reasoner with the engine's own shipped MCP layer |
| `aura-mcp[:<model>]` | `--mcp-config aura_mcp.json --strict-mcp-config --disallowedTools <generic+subagents> --permission-mode bypassPermissions` | **only** a commercial third-party product's MCP tools; generic actuators denied | That product's tool layer — **disclosed, not reproducible here** |
| `openrouter:<provider/model>` | `--strict-mcp-config` + OpenRouter transport env | generic `Write`/`Edit`/`Bash` only | The **baseline** arm with a non-Anthropic reasoner |
| `bare:<provider/model>` | n/a — our own minimal loop, not `claude -p` | five local file tools, no editor | A model inside a scaffold **we** control and disclose |

> **Why `unreal-mcp` keeps the file tools and `aura-mcp` does not.** This is the
> one asymmetry in the table, and it is deliberate: Epic's MCP server has no C++
> source tool, so stripping `Write`/`Edit`/`Bash` from `unreal-mcp` would leave
> it unable to attempt a source task at all, while `aura-mcp` keeps C++ editing
> through the product's own `edit_cpp_file`. Aligning the two denylists would
> look tidier and would delete the result. Don't.

### `aura-mcp` — disclosed, not reproducible

The `aura-mcp` branch of `registry.py` and its `adapters/aura_mcp_config.py` /
`adapters/aura_mcp.json` ship **verbatim**, because the difference between that
branch and the `unreal-mcp` branch *is* the published measurement and has to be
auditable. What does not ship is the **runtime**: the product's closed-source UE
plugin, the two private web services behind it, and the login that authenticated
an entitled account. That machinery was removed rather than published.

Consequently `cb` refuses an `aura-mcp:*` slug in the first second, before any
task resolve, build, or token spend, and says why. Reading the arm is supported;
running it is not. See the repository README's "three measured arms" section and
`THIRD-PARTY.md`.

The model is given **only** that product's two MCP servers and is **denied the
generic actuators** (`Write`/`Edit`/`Bash`/`MultiEdit`/`NotebookEdit`) **and the
subagent/orchestration tools** (`Agent`/`Task`/`Skill`/`Workflow`/…) — a child
agent must not be spawnable to route around the denylist, which was a real leak
seen in the first spike. Read-only inspection (`Read`/`Glob`/`Grep`) and
`ToolSearch` stay allowed (the product ships ~138 tools that arrive **deferred**,
so the agent must search to reach them).

**It measures "the model using that product's tool layer", not the product's own
autonomous agent** — that loop was never externally drivable through this path.
Report results as `aura-mcp:<model>`, never as the bare product name.

### Retired backends

`registry.py:_REMOVED_BACKENDS` names every arm that once lived here —
`aura-product`, `aura-agent`, `aura-baseline`, `aura-mcp-bridge` — and answers a
slug naming one with what it was, rather than a bare "unknown backend". None of
them are part of this release; the table above is the complete live set.

## Important: don't run from inside an MCP-attached Claude session

Most UE MCP servers don't multiplex client connections cleanly. If you
run `tools/run-agent/run.py` from a Claude Code session that already
holds the Unreal MCP connection, the spawned `claude -p` will race the
parent session for the same MCP server.

**Run the harness from a plain terminal**, or from a Claude Code session
that has the Unreal MCP disabled.

## What the agent sees (and doesn't)

The agent's `claude -p` process is launched with (see
`adapters/claude_p.py::build_claude_command`):

- `--add-dir <workspace>` — scopes file access to the substrate (the /tmp
  workspace copy for Baseline; the live project for `aura-mcp --live-project`).
- `--permission-mode bypassPermissions` — a single-shot agent runs its
  *allowed* tools without interactive prompts. (`auto` was found to **deny**
  Aura's MCP write tools like `generate_cpp_file` in the parent context, so they
  only ran via a subagent leak — fixed by `bypassPermissions` + the denylist.)
- `--max-turns 0` (default, 2026-07-31 — was 25) — 0 = uncapped tool-use loop; the
  `--timeout` wall clock (600s default) is the governor. Adapters whose agent loop
  has no wall-clock deadline (aura-mcp) clamp 0 to a finite safety cap of 1000.
  Pass a positive N to restore a hard turn budget.
- The **prompt is passed on stdin**, never in argv, so the variadic
  `--disallowedTools`/`--allowedTools` lists can't swallow it.
- Tool access is product-specific (see the backends table): Baseline gets
  generic edits and no MCP; `aura-mcp` gets Aura's MCP and a generic+subagent
  **denylist** so it can only actuate through Aura's tools.

The agent's `PROMPT.md` contains:

- The `## Prompt given to the agent` section of the task `.md`.
- The `## Workspace state pre-task` section (describes the starting
  source files — same info the agent gets from `ls`).
- A list of writable files (the agent's submission).
- Constraints (don't read outside the workspace, don't ask clarifying
  questions).

The agent's `PROMPT.md` does NOT contain:

- The task's `## Verifier specification` (names exact log strings,
  tags, dt cadences, assertions).
- The task's `## Anti-gaming notes` (names failure modes and defenses).
- The task's `## Reference solution metadata` (LOC, approach hints).
- The task's `## Primary concept` (load-bearing UE API).

`tools/run-agent/prompt_extract.py` uses an allow-list, not a deny-list:
any future section added to task `.md` files is dropped by default.
Tests in `tests/test_prompt_extract.py` enforce zero answer-key leakage
on the two shipped tasks.

## Tests

```sh
python3 -m unittest discover -v -s tools/run-agent/tests
```

All tests use real shipped tasks / substrate as fixtures (matching the
`tools/verify-single/tests` convention). No tokens are spent — the
`claude -p` adapter's command construction is unit-tested but the
subprocess invocation itself is covered only by the end-to-end smoke.

## What's NOT in v0

- OpenRouter / non-Anthropic adapters. The `AgentAdapter` Protocol in
  `adapters/base.py` is designed to accommodate them; add a new module
  under `adapters/` and register it in `adapters/registry.py`.
- Batch mode (run all tasks vs all models).
- Auto-launching UE — user opens the workspace .uproject manually at
  the pre-flight handshake (A2 pattern).
- Process-level / OS-level agent sandboxing (Docker, Bubblewrap).
  Current scoping is `--add-dir` + neutral cwd + prompt discipline.
- L3/L4/L5 verifier layers — the underlying verifier doesn't implement
  them yet.

The original design spec + implementation plan were retired 2026-07-16
(git history: `docs/superpowers/`); the shipped behavior documented above
is the authority.

## Cost accounting

Per-run token/cost accounting is written into each run's `summary.json` by the
adapter that drove it. The separate `:41299` logging proxy and the cache-health
audit that once wrapped it belonged to the `aura-agent` backend, which is not
part of this release (`adapters/registry.py:_REMOVED_BACKENDS` is the honest
record of every arm that once lived here and no longer does).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR: ... has no '## Prompt given to the agent' section` | Task `.md` is malformed | Add the required section to the task spec |
| `agent produced no edits — submission is empty` (exit 2) | Agent refused, timed out, or wrote outside the writable set | Inspect `runs/<id>/agent_transcript.txt` to see what the agent did |
| Verifier FAIL (exit 3) but submission looks plausible | Agent's solution is genuinely wrong, OR there's a regression in substrate/fixture | Compare `runs/<id>/submission/` to `tasks/<set>/<task_id>/reference/` |
| `claude -p` hangs forever | MCP connection race (you ran from inside an MCP-attached Claude session) | Re-run from a plain terminal |
| Verifier reports `editor reached terminal marker but did not self-exit; force-killed` | Known UE-Mac RequestExit quirk, harmless | Ignore — see `tools/verify-single/README.md` Mac quirks section |
