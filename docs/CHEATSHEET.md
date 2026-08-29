# CraftBench command cheatsheet

Narrative run-book (how the pieces fit, end to end): [EVALS.md](../EVALS.md).
Setup: the [README](../README.md) Quick start (`setup.ps1` / `setup.sh`, then `cb smoke`);
the deep runbook is [ONBOARDING.md](../ONBOARDING.md). Two tiers ship in this release:

1. **Grade-only** — UE 5.8 + Python 3.11+ (3.12 recommended) + git/tar, **no secrets**: `run_task.py` / `cb batch-eval --references all`.
2. **Baseline** — + `claude` CLI + `ANTHROPIC_API_KEY` (`OPENROUTER_API_KEY` for `openrouter:`): `cb eval --model claude-p:<model>`.
The third arm, **`aura-mcp`**, is disclosed and dispatchable but **not reproducible from
this repository**: it needs a proprietary UE plugin, two private local services and an
entitled account, none of which are published. Selecting it fails fast with that message.

`setup` pip-installs `cb` as a console script; with no install the repo-root shims
`.\cb` / `./cb` always work (or `python -m aura_rig.cb <command>` from `tools/run-agent/`).
Bare `cb` prints the grouped overview; `cb help <cmd>` / `cb <cmd> --help` print scoped help;
`cb completions powershell|bash` enables tab-completion (commands, flags, task ids, models).
Eval-family commands open with the ~2s pre-spend env gate
(`--no-preflight` / `CB_NO_PREFLIGHT=1` to skip).

---

## Daily commands

Model slugs for `eval`: `claude-p[:<model>]` / `openrouter:<provider/model>` / `bare:<provider/model>` → baseline `run.py`; `unreal-mcp[:<model>]` → Epic's in-editor MCP (`run.py --live-project`). `aura-mcp[:<model>]` is disclosed but NOT runnable from this repository — `cb` refuses it in the first second.

| Command | What it does | Key flags |
|---|---|---|
| `cb smoke` | Prove the golden path: preflight → verifier unit tests → a real t0 reference grade; exit 0 = your machine benches | `--agent [MODEL]` (append ONE live eval; SPENDS tokens) `--no-preflight` |
| `cb eval` | Graded eval: stack bring-up (backend-dependent) + agent drive + L1/L2 verify on the template | `--task <id\|set/id>` `--model <slug>` `--ceiling <s>` (900) `--visible` `--capture` `--keep` `--keep-workdir` (full ~5.9 GB verifier workdir instead of the slim default) `--preview` (live scene capture -> `runs/<run>/preview/`) `--reuse-editor` (skip the per-drive fresh-editor restart) `--restart-client` `--restart-editor` `--ue-root` `--py` `--no-preflight` |
| `cb batch-eval <outputs-dir>` | Token-FREE parallel grade of a folder of isolated submission dirs (each named by its task id) | `--references [all\|<set>]` (grade the tasks' own reference solutions instead; mutually exclusive with the positional) `--verify-concurrency N` (1; raise only on >32 GB) `--warm-cache` `--keep` `--wip` (force from-live) `--label` `--no-gate` (exit 0 despite graded FAILs — measurement mode; the default is a GATE: any graded FAIL, or 0 graded, exits 1) |
| `cb refgate <task>[,…]` | **RETIRED — do not use.** It is still dispatchable and still works, but nothing requires it and it is not the authoring gate. `cb discriminate` already grades the committed reference from git HEAD on the same tree — exactly what refgate certified — and additionally proves the EMPTY leg fails for its named reason, which refgate never checked. Refgate's one unique addition, per-machine certificates, is voided wholesale by any substrate change (one surface-pair rename invalidated the entire set). Use `cb discriminate --task <task>`. | `--all` `--force` `--no-preflight` |
| `cb discriminate` | Token-FREE FR-017 matrix per task: reference→PASS, empty + each `discrimination/` variant→FAIL via its named substring | `--task <id\|set\|set/id>` `--keep` (legs kept under `runs/discriminate/<task>-<ts>/`) `--warm-cache` `--wip`; `cb wip` = alias of `discriminate` |
| `cb lint` | Token-free STATIC spec lint (wraps `tools/verify-single/tasklint.py`) — no UE, no build | `--task <id\|set\|set/id>` (default `--all`) |
| `cb bench` | N SEQUENTIAL reps per {model}×{task} → cost/time SPREAD **+ the model-comparison leaderboard**: `runs/bench-<ts>/bench.{json,md}` + `leaderboard.html` (model×task grid, one badge per rep linked to its run's `report.html`, models_used-mismatch flags). Multiple models in ONE invocation; `--repeat 1` = pure head-to-head comparison; aura-mcp/unreal-mcp → per-run `cb eval`. **Bare `cb bench` in a terminal opens an interactive wizard** (task checkboxes → backend → models → reps → confirm; ends by printing the equivalent flag command); non-TTY / explicit `--model`/`--task` keep the classic run | `--model A,B,C` `--task <id>[:reps][,…]` `--repeat N` (3) `--ceiling <s>` (900) `--refgates` (OPT IN to the pre-spend per-task reference gates — default OFF; certify at authoring time with `cb discriminate` instead; `--skip-refgates` is a deprecated no-op) `--preview` `--resume [DIR]` `--wizard` (force it) `--prune-workdirs` `--no-teardown` (leave the Aura stack UP afterwards; the DEFAULT stops it, because a stack left resident starves the next invocation's build - measured 5x verify, 118.5s -> 588.6s, on a claude-p baseline backend that never touches the stack) `--no-preflight` |
| `cb matrix` | {model}×{task} cross product — the baseline-only one-run-per-cell sibling of `cb bench` (claude-p/openrouter only; MCP-lane comparisons → `cb bench --repeat 1`) → `runs/matrix-<ts>/leaderboard.{html,md,json}` | `--model A,B,C` (comma list) `--task <id\|set\|set/id>` |
| `cb tasks` | Interactive browser: sets → tasks → detail; confirming runs it as `cb eval --task <id>` | `--task <id>` skips the picker and runs directly |
| `cb warm-prime` | Build the L1 warm-cache pool so verifies build incrementally; pair with `--warm-cache`. **Expect ~1.8-2x on THIS substrate, not the ~6x headline** — the correctness gate bumps all ~38 writable `CraftBenchTemplate` sources before the incremental build, so ~55-120s of L1 is the floor. The 6x applies to substrates with a SMALL writable footprint. **Costs ~5.95 GB per slot** under `%LOCALAPPDATA%\CraftBench\warm-baseline` — a root NO `cb clean` path prunes and the `wd-disk` preflight probe does not measure | `--warm-slots N` (2; match `--verify-concurrency`) `--force` `--task` (substrate pick) |
| `cb review <run-dir>` | Overlay the run's `deliverable/` onto the SCRATCH project, list artifacts, open a windowed editor to PIE it | `--map <L_X>` `--project <dir>` |
| `cb view` | Windowed editor to see/PIE a change (default: the headless scratch) | `--map <L_X>` `--run <run-dir>` (overlay onto the template) `--project <dir>` |
| `cb clean` | Reset the headless scratch to pristine; with `--workdirs`, prune `CRAFTBENCH_WD_ROOT` dirs unreferenced by any `runs/**/summary.json` `graded_workdir`; with `--workdirs --slim`, instead SLIM every workdir in place — referenced or not, since the referenced ones are exactly what the prune can never touch; with `--presnaps`, sweep orphaned crash-debris pre-run snapshots (60-min in-flight floor) | `--workdirs` `--slim` `--runs` `--keep-last K` `--presnaps` `--older-than N` (days) `--check` (dry-run) |
| `cb up` | Bring up the Aura stack + readiness gate, no run | `--restart-client` `--restart-editor` |
| `cb down` | Stop the whole stack (supervisor + editor + LiveCodingConsole). Since 2026-08-07 this ALSO happens automatically when the process that brought the stack up dies without teardown (hard-stop/crash/closed console): a janitor watchdog + per-command startup reconciliation run the same kill-audited teardown, incl. a command-line-scoped orphan sweep of stray UnrealEditor/-Cmd/LiveCodingConsole/CrashReportClient from older stack generations (foreign UE projects untouchable) | — |
| `cb status` | One-shot overview: stack health, current/last run, cost tally, LiveCoding count, scratch state | — |
| `cb doctor` | READ-ONLY diagnostic: per-tier readiness + fix hints (exit 0 iff highest provisioned tier READY) | — |
| `cb where` | READ-ONLY: print the RESOLVED machine dirs (repo, substrate, `cb_root`, `wd_root`, graded + drive scratch, runs) and which env vars overrode them. Run this before believing any path in these docs — it is the ground truth for where workdirs actually land | `--link` (gitignored `<repo>/.cb/{wd,scratch}` junctions/symlinks to the resolved dirs; refuses to clobber a real dir) |

---

## Direct verifier (`tools/verify-single/run_task.py`)

```sh
python tools/verify-single/run_task.py \
    --task tasks/<set>/<id>/task.md \
    --submission <agent-output-dir> \
    --ue-root "C:\Program Files\Epic Games\UE_5.8"
```

| Group | Flags |
|---|---|
| **Core** | `--task <spec.md>` `--submission <dir>` (or `--submission-from-project <ue-proj>` [+ `--capture-assets` to save-all + sweep Content/ .uassets]) `--ue-root <install-root>` `--layers L1,L2` `--test-filter <str>` `--substrate-overlay <dir>` |
| **Retention** | `--workdir <path>` (must not exist; default: fresh tempdir) `--keep-workdir` `--out-dir <path>` (logs/report outside the workdir) `--report-json <path>` |
| **Modes** | `--visible` (real-RHI L2/L2I; `-deterministic -FPS` never dropped) `--capture` (real RHI + `-CraftBenchCapture` → `<out>/artifacts/`) `--no-nullrhi` `--warm-cache` [+ `--warm-cache-dir`] `--strict-warnings` |
| **Maintainer** | `--substrate-from-live` (DEBUG: copy live tree, not git HEAD) |
| **Misc** | `--harness {filesystem,aura,bare_llm}` `--model <provider/model>` (pinning metadata) `--r2` [+ `--r2-eval-model` `--r2-agent-model` `--r2-ensemble`] non-gating advisory judge; hardening: `--govern-resources` (default ON; `--no-govern-resources`) `--tighten-workdir-acl` `--sandbox` (experimental WSB, Win Pro+ only) |

Direct harness (`tools/run-agent/run.py`) — agent drive + auto-grade in one shot:
`python tools/run-agent/run.py --task <spec.md> --model <slug> --ue-root <root>`; key flags: `--live-project`
(aura-mcp/unreal-mcp), `--keep`/`--keep-workspace`, `--visible` `--capture`, `--max-turns` (25), `--timeout` (600 s),
`--no-preflight` `--skip-plugins` `--prepare-only` `--workspace <dir>` `--allow-dirty-substrate` `--run-dir` `--substrate-root`.

---

## Environment variables

`.env` at the repo root (copy from `.env.example` — the authoritative list). Almost everything auto-detects.

| Var | Effect | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Model access: baseline `claude-p` + Aura's local model route | required for baseline + full-rig |
| `OPENROUTER_API_KEY` | Enables `openrouter:<provider/model>` (Bearer token, unquoted) | unset |
| `OPENROUTER_BASE_URL` | OpenRouter Anthropic-skin endpoint | `https://openrouter.ai/api` |
| `CB_UE_ROOT` | UE install root (same as `--ue-root`) | auto: `C:\Program Files\Epic Games\UE_5.8` (5.8 first, older only if absent) |
| `CB_PY` | The interpreter the harness launches for verifier/child work (same as `cb --py`; tried first in the resolver) | auto: `py -3.12` → `py -3` → `python` → `python3` |
| `CB_PYLAUNCH` | The interpreter the repo-root shims (`cb.cmd` / `./cb`) boot `cb` itself with — read before any Python runs, so before `CB_PY` resolution | first working Python 3.11+ of `py -3.12` → `py -3` → `python` → `python3` |
| `CB_CRAFTBENCH` | Repo root | auto: this repo |
| `CB_UPROJECT` | Template `.uproject` path | auto: `UE-projects/CraftBenchTemplate/...` |
| `CB_DRIVE_PROJECT` | Your own project for `cb view` (used as-is, never reset) | unset (managed scratch) |
| `CRAFTBENCH_WD_ROOT` | Short verifier-workdir root (MAX_PATH dodge; `cb clean --workdirs` prunes it) | `<CB_ROOT>/wd` (e.g. `C:\cb\wd`) — the old `C:\cbwd` default is RETIRED |
| `CB_WORKDIR_RETENTION` | `full` \| `slim` \| `none` — what to keep of a workdir after grading. `slim` drops the ~4.7 GB obj tree + debug binaries, keeps `out/` and a launchable project. `cb eval/bench/batch-eval --keep-workdir` is the CLI equivalent of `full`. Readable from `.env` | `slim` |
| `CRAFTBENCH_L1_MAX_PARALLEL` | Cap UBT parallel actions. **Not just a RAM-tight-host knob** — C3859 is a per-`cl.exe` PCH failure under CONCURRENCY, so a big box hits the same wall: measured 2026-07-26 on 66 GB / 8 cores with **26 GB commit headroom free**, cap `4` PASSes (L1 86.8s) and cap `6` and `8` FAIL L1 deterministically (5/5, `C3859`+`C1076`). Raise it by MEASURING, never by inferring from RAM — an over-high cap FAILs the *reference solution*, which in a real eval is recorded as the agent failing the task. `2` on ~32 GB; `4` is the measured ceiling here | unset (no cap) |
| `CRAFTBENCH_ALLOW_UBA` | `=1` re-enables Unreal Build Accelerator (off: UE 5.8 UBA crashes on a dirty shared cache) | unset (UBA disabled) |
| `CB_VISIBLE` / `CB_CAPTURE` / `CB_KEEP` | The eval-mode contract `cb eval --visible/--capture/--keep` exports to every child; set `=1` by hand for the same effect | unset |
| `CB_WARM_CACHE` / `CB_WARM_CACHE_DIR` | `=1` = `run_task.py --warm-cache` / baseline cache root | unset / `%LOCALAPPDATA%\CraftBench\warm-baseline` |
| `CRAFTBENCH_SUBSTRATE_FROM_LIVE` | `=1` = `--substrate-from-live` (debug) | unset (grade from git HEAD) |
| `CRAFTBENCH_GOVERN_RESOURCES` | `1`/`0` overrides `--govern-resources` in both directions | flag default (ON) |
| `CB_TMP` | Scratch + log dir | OS temp |
| `CB_GATEWAY` | Model-gateway base URL override (openrouter/bare routing) | provider default |
| `CB_COMMIT_FLOOR_GB` | Hard floor on FREE COMMIT (GB) — THE one threshold. The envgate `commit-headroom` probe FAILs below it, every aura drive/bench rep re-checks it pre-spend (below-floor → stack recycle; still below → the rep aborts non-graded as `COMMIT-EXHAUSTED`), and the IN-DRIVE sampler bands off it (WARN below 2x, CRITICAL below it) | `10` |
| `CB_PRESSURE_GUARD` / `CB_PRESSURE_SAMPLE_S` / `CB_PRESSURE_WARN_MULT` / `CB_PRESSURE_HYSTERESIS_GB` | In-drive commit sampling: `=0` disables it; seconds between samples; the WARN multiple of the floor; the de-escalation re-arm margin in GB | on / `10` / `2` / `0.5` |
| `CB_STACK_RECYCLE_MB` | Leak trigger: `cb bench` also recycles the stack at a rep boundary once the (now-removed) vendor stack's two server processes hold this many MB of private bytes combined — inert on this release (`0` = cadence only) | `6000` |
| `CB_STACK_IDLE_TEARDOWN_HOURS` | OPT-IN janitor idle teardown: a stack idle beyond N hours is torn down even with a live owner (overnight rot). Unset = off | unset |
| `CB_STACK_GUARD` | `=0` disables the whole stack auto-recovery subsystem (ownership manifest, startup reconciliation, janitor) | on |
| `CB_AURA_SKILLS` `CB_PROXY_INJECT_CACHE` | Advanced tuning — leave unset | unset |

---

## Reading a run

`runs/<track>/<task>-<ts>/` contains: `summary.json` / `result.json` (`overall` PASS/FAIL verdict + the **embedded
verifier report** + `graded_workdir` + `artifacts` list), `deliverable/` (the agent's submitted files),
`verifier_stdout.txt`, `artifacts/*.png` (`--capture`), and `project-lean/` (`--keep` — lean graded-project copy).

- **Terminal recap** — `cb eval` ends with `Result: … (agent Xs | verify Ys; …)`:
  `agent` = the agent's own turn, `verify` = the deterministic verifier
  (build-dominated). The difference between an arm's wall time and its agent
  time is harness overhead — editor bring-up on the editor-backed arms — not
  model time, so never read one for the other.
  Same numbers live in `summary.json`/`result.json` under `timings`.
- `graded_workdir` = the built project under `CRAFTBENCH_WD_ROOT` (default `<CB_ROOT>/wd`, e.g. `C:\cb\wd` — **not** the retired `C:\cbwd`; if you have a `C:\cbwd` it is a stale root from an older default and nothing prunes it). Prune with `cb clean --workdirs`; reclaim the ~5.9 GB/run build tree in place with `cb clean --workdirs --slim`.
- Reopen a run's generation in a windowed editor: `cb review <run-dir>`.
- Dashboard: `python -m tools.dashboard.web` from the repo root (see Utilities).

---

## Utilities

| Command | What it does |
|---|---|
| `python -m aura_rig.tasks resolve <id> [--repo <path>]` | Print the spec path for a (possibly set-qualified) task id; run from `tools/run-agent/` |
| `pip install -r tools/dashboard/requirements.txt` | One-time dashboard UI deps (the data layer is pure stdlib) |
| `python -m tools.dashboard.tui [--repo-root <path>]` | Textual TUI over runs/tasks (read-only); from the repo root |
| `python -m tools.dashboard.web [--repo-root <path>]` | Web dashboard (matrix, run drill-in, launch panel); opens `http://127.0.0.1:<port>/` |

---

## Gotchas

- Raw `run_task.py` on ANY box (not just a RAM-tight one): set `CRAFTBENCH_L1_MAX_PARALLEL` yourself — `cb` applies its own gate, the bare runner doesn't. `4` is the measured-safe value here; `6`+ FAILs L1 with C3859 even with 26 GB free. Precedence is now uniform (fixed 2026-07-26): an **explicitly-exported value wins on every path**, and `.env` fills only what is unset. `cb` prints `[env] .env NOT applied (an explicit environment value wins): …` for anything it declines, so you can see which value won. (Previously `cb` and raw `run_task.py` disagreed and `.env` clobbered your export under `cb`.)
- An open editor with Live Coding blocks ALL UBT builds — set `bEnabled=False` in the project's `Saved/.../EditorPerProjectUserSettings.ini` (or `cb down` frees the lock).
- `--substrate-from-live` runs are annotated `substrate_source: live` and are uncertified — certified verdicts grade from git HEAD (the default).
- The `aura-mcp` arm needs a proprietary plugin under `Plugins/` that this repository does not ship; it aborts with an explanatory message rather than half-running.
- Aborted-not-failed verdicts (excluded from pass-rates, zero tokens spent): `BRIDGE-NOT-READY` (tool bridge probe failed — re-run `cb up`), `DIRTY-SUBSTRATE` (tracked writable files modified; the gate first SELF-HEALS from a crashed run's leftover `fairness_backup`/presnap and re-checks — pre-heal bytes are parked under `CB_TMP/cb-heal-rescue/<stamp>/`; only still-unexplained dirt aborts: `git checkout -- <files>` or override `CB_ALLOW_DIRTY_SUBSTRATE=1`), `LIVE-RUN-ACTIVE` (another live-substrate run holds `runs/.live-run.lock` — wait or kill it), `EDITOR-NOT-READY`, `TOOL-AUTH-BLOCKED`, `DRIVE-ERROR`, `NO_DELIVERABLE`.
- Windows Git Bash eats bare backslashes in flags like `--workdir C:\x\y` — use forward slashes or run from PowerShell/cmd.
- Killed a bench/eval mid-run? The stack now cleans itself up: the janitor tears it down within ~60 s of the owner dying (or the next `cb` command does, first thing), every kill lands in `runs/.kill-audit.log`, and `--no-teardown` only keeps a stack while YOUR session lives. `cb down` still works as the explicit form; `CB_STACK_GUARD=0` opts the whole subsystem off.
