# Running CraftBench-UE

Operator reference: configuring the harness, running an eval, reading what
comes back, and comparing arms. The [README](../README.md) covers install and
the first run; this is what you consult while working.

One-page command reference: [`CHEATSHEET.md`](CHEATSHEET.md).

## Configure

Most configuration lives in one gitignored file, **`.env` at the repo root**, created from
[`.env.example`](../.env.example) — a commented starter template, **not** a mirror of what the loader
reads (it lists keys the loader ignores, and omits one it honours; both gaps are named below). Every
key there is commented out **on purpose**: the loader exports whatever it finds, so an uncommented
placeholder would override a real key already in your environment and the auth failure would be
invisible. An explicitly exported environment variable always wins; `.env` only fills what is unset.
The omission is `CB_BARE_BASE_URL`, the `bare` arm's endpoint override (`adapters/bare.py`): the
loader whitelists it and it works in `.env`, but it does not appear in `.env.example` at all.

> **`.env` is read through a whitelist, not a general loader.** `load_aura_env`
> (`tools/run-agent/aura_rig/stack.py`) exports a fixed set of names, so a variable outside that
> set is a **silent no-op** in `.env` — no error, no warning, the default simply stands. Those
> keys have to be **real environment variables**; they are marked **(env only)** below.

| What you want to run | Keys required |
| --- | --- |
| Deterministic grading only (no agent) | **none** |
| `claude-p` | `ANTHROPIC_API_KEY`, and the `claude` CLI on PATH |
| `unreal-mcp` | Same as `claude-p`, plus UE 5.8 with Epic's ModelContextProtocol plugin. `CB_UNREAL_MCP_URL` is optional **(env only)** — default `http://127.0.0.1:8000/mcp`. |
| `openrouter:<provider/model>` | `OPENROUTER_API_KEY` (sent as a Bearer token — do not wrap it in quotes) |
| `bare:<provider/model>` | `OPENROUTER_API_KEY`; `CB_BARE_BASE_URL` to point at another OpenAI-compatible endpoint (works in `.env`, absent from `.env.example`) |
| `aura-mcp` | none — it is refused before it runs, by design |

Each of those failures is loud: a missing key raises with the reason before any spend.

> ### `CRAFTBENCH_L1_MAX_PARALLEL` — set this, or correct answers get graded FAIL
>
> Uncapped, UnrealBuildTool picks its own parallelism, UE 5.8's editor PCH compiles exhaust commit
> charge, and `cl.exe` dies with C3859 **inside engine headers** — which the run records as the
> *submission* failing. This has taken a fresh checkout to 15/15 references failing. **Nothing
> sets it for you** except `cb discriminate`.
>
> Start at **`2`** on ~32 GB, `4` on a large box. Raise it by measuring, never by inferring from
> installed RAM — `6` and `8` fail L1 deterministically with 26 GB of commit still free. Full
> measured table: [`docs/CHEATSHEET.md`](../docs/CHEATSHEET.md).

Other optional keys, all auto-detected. `CB_WORKDIR_RETENTION` (`slim` by default, or `full` /
`none`) is whitelisted and works in `.env`. `CB_UE_ROOT`, `CB_ROOT` and `CB_PY` are **env only** —
`.env.example` lists them, but the loader never reads them, so a `.env` entry is silently ignored;
export them (`setx CB_ROOT C:\cb`) or, for the first and third, pass `cb --ue-root` / `cb --py`.
The full flag and variable reference is `docs/CHEATSHEET.md`.

## Run an eval

**Step 1 — the token-free path.** Grade a committed **reference solution**: this exercises the whole
pipeline — substrate materialisation, UBT build, headless PIE, assertions — with no API key and no
tokens. It builds and runs a real UE project, so the the README's install section bootstrap has to have run first;
`bootstrap_substrate.py --check` is the cheapest way to rule that out.

```sh
cb smoke
```

Three legs: environment preflight, verifier unit tests, then a **real** graded run of the
`t0-sanity-log-on-beginplay` reference (L1 build + L2 PIE). Budget **4-8 minutes cold** for that
grade, longer on the very first run because nothing is cached. Exit **0** means this machine grades
correctly; exit **2** means it refused before building or spending anything; exit **1** means a leg
genuinely failed. Then widen it — every committed reference in the tree must PASS:

```sh
cb batch-eval --references all       # exit 0 = all PASS, 1 = something graded FAIL
cb batch-eval --references cpp       # or one set: bp | cpp | python | craftbench-public
cb lint                              # instant static spec lint; no UE, no tokens
```

You can also drive the verifier directly, with no `cb` at all — this is the exact command
`cb smoke` builds. Set `CRAFTBENCH_L1_MAX_PARALLEL` in your environment first; this path does not
derive it for you.

```sh
py -3.12 tools/verify-single/run_task.py \
  --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
  --submission tasks/cpp/t0-sanity-log-on-beginplay/reference \
  --ue-root "C:/Program Files/Epic Games/UE_5.8" \
  --workdir C:/cb/wd/myrun
```

**Step 2 — a real agent run.**

```sh
cb eval --task t1-movement-component-drives-actor --model claude-p:sonnet-5
cb eval --task t1-movement-component-drives-actor --model unreal-mcp:sonnet-5
cb eval --task t1-movement-component-drives-actor --model openrouter:openai/gpt-5
```

Wall clock is agent time plus verify time: the agent is capped by `--ceiling`, **default 1200
seconds**, and verification is the same L1 build + L2 PIE as above. `unreal-mcp` needs no manual
setup — `cb` launches the headless editor itself and waits for a real MCP handshake before driving.
Defaults if you omit them: `--task t0-sanity-log-on-beginplay`, `--model claude-p`. Task ids accept
`<id>`, `<set>`, or `<set>/<id>`. `cb eval <taskid>` **without** `--task` is refused with a
did-you-mean rather than silently grading the default task at full price. Scripting a loop? Add
`--teardown`, or each run inherits the previous run's increasingly stale editor.

> `cb tasks` opens an interactive task browser — but confirming a task there **runs a graded eval
> and spends tokens**. It is the one token-spending command that does not look like one.

## Read the result

Runs land under `runs/<backend>/<UTC-timestamp>-<task-id>-<model-slug>/`, one directory per backend
so arms never collide:

```
runs/claude-p/20260828-141203-t1-movement-component-drives-actor-claude-p-sonnet-5/
  report.html        <- OPEN THIS ONE
  result.json        machine envelope: verdict, agent stats, timings, workdir
  summary.json       written by batch runs only (cb batch-eval); a single
                     `cb eval` writes result.json and no summary.json
  submission/        what the agent produced
  artifacts/*.png    captures
```

**`report.html` is the file a human reads.** One self-contained file — no server, no build step; it does pull Tailwind from a CDN for styling, so archived reports opened offline render unstyled but complete — it carries the
verdict banner, task-spec excerpts, the agent's submitted files, per-layer verifier log excerpts,
and captures, and on an interactive `cb eval` it opens in your browser automatically
(`CB_OPEN_REPORT=0` to stop that). The terminal's last line is
`Result: <VERDICT>  (agent Ns | verify Ns; ...)`.

**What the verdicts mean.** Only two are *graded*: **`PASS`** (every declared layer passed) and
**`FAIL`** (graded, did not meet the spec). Three more count as **model outcomes** and stay in the
pass-rate denominator, because they are the agent's own doing: `FAIL_NO_EDITS` (it changed
nothing), `NO_DELIVERABLE`, and `SANDBOX-REJECT` (it wrote outside the writable workspace).

Everything else is **excluded from every pass-rate**, because it measures the harness rather than
the agent: `HARNESS-ERROR`, `SUBSTRATE-REJECT`, `UNGRADED`, `EDITOR-NOT-READY`,
`AGENT-TRANSPORT-ERROR`, `TOOL-AUTH-BLOCKED`, `FAIRNESS-BREACH` and their siblings. The exclusion
is structural — the pass-rate function takes an allowlist of graded verdicts — so a timed-out
transport is never quietly booked as a model failure.

Exit codes: `cb eval` returns **0** on PASS and **3** on anything else. Raw `run_task.py` uses a
finer taxonomy — `0` PASS, `1` FAIL, `2` usage error, `4` sandbox reject, `5` no uproject,
`7` harness error, `8` ungraded.

## Compare arms

The point of the benchmark is one task, several tool layers, one model, one verifier:

```sh
cb matrix --model claude-p:sonnet-5,openrouter:openai/gpt-5 --task cpp

cb bench  --model claude-p:sonnet-5,openrouter:openai/gpt-5 \
          --task bp/gp-glide-stamina-bp,cpp/gp-glide-stamina-cpp --repeat 2
```

`cb matrix` runs one rep per {model x task} cell and writes
`runs/matrix-<ts>/leaderboard.{html,md,json}`. `cb bench` runs N sequential reps per cell and writes
`runs/bench-<ts>/bench.{json,md}` plus a leaderboard whose cells link back to each rep's own
`report.html`; `cb reliability` adjudicates a repeated bench directory. Both are limited to the
baseline backends — `unreal-mcp` is reported as unsupported there and `aura-mcp` is refused — so to
compare tool layers today, run `cb eval` once per arm and read the reports.

Each workdir is about 5.95 GB, so: `cb clean --workdirs --slim` reclaims most of that in place
(add `--check` for a dry run), `cb clean --runs --keep-last 20` prunes old run directories, and
`cb down` stops the editor and frees the engine build lock.
