# CraftBench-UE — Documentation Index

> **The map of the docs that ship in this public release.** It names the front
> door, the reading order, and every live doc's role. It links to the
> authoritative doc for a topic rather than restating it.

**This index was rebuilt for the public release.** The private repository carried a
large body of dated run reports, per-machine operations logs, internal planning and
review records, and documentation for a proprietary product lane. None of that is
published. If a doc you remember is missing, that is why — nothing below is a stub or
a placeholder.

---

## Start here

**[`../DEVELOPING.md`](../DEVELOPING.md) is the contributor front door** — one page, the three things
you can do (set up a machine / run a task on models / author a new task), each
with the commands that do it.

Then, in order:

1. [`../README.md`](../README.md) — what CraftBench-UE is, quick start, status.
2. [`RUNNING.md`](RUNNING.md) — configure, run an eval, read a result, compare
   arms. The operator reference you keep open while working.
3. [`ANATOMY-OF-A-TASK.md`](ANATOMY-OF-A-TASK.md) — one task end to end: what the
   agent sees, what grades it, and how discrimination proves it works.
4. [`CHEATSHEET.md`](CHEATSHEET.md) — every `cb` command, flag, and environment
   variable on one page. The fastest way to find the thing you half-remember.
5. [`../EVALS.md`](../EVALS.md) — the narrative run-book: how a run flows from prompt
   to verdict.
6. [`../ONBOARDING.md`](../ONBOARDING.md) / [`WINDOWS.md`](WINDOWS.md)
   — the deep setup path.

---

## The five backends, on two axes

`--model <backend>:<model-id>` selects a backend. They are **not** one flat list —
three of them vary the *tool layer* while holding the model fixed (that asymmetry
**is** the measurement), and two vary *which provider serves the model*. Defined in
`tools/run-agent/adapters/registry.py`; the authoritative per-arm description is
[`../tools/run-agent/README.md`](../tools/run-agent/README.md).

**Tool layer — same model, different tools:**

| Backend | What it is | Runnable from this repo? |
|---|---|---|
| `claude-p` | Claude Code with **no editor tools**. The baseline. (`registry.py:485`) | **Yes** |
| `unreal-mcp` | Claude Code + Epic's in-engine MCP server, which ships inside UE 5.8. `Write`/`Edit`/`Bash` stay **enabled** — Epic's MCP has no C++ source tool — and only orchestration tools are denied. (`registry.py:514`) | **Yes** |
| `aura-mcp` | Claude Code given **only** a commercial product's MCP tools; `Write`/`Edit`/`Bash` are denied. Measures that product, not a model. (`registry.py:490`) | **No — disclosed, not reproducible** |
| `bare` | Our **own** minimal agent loop plus five local file tools, over any OpenAI-compatible endpoint. No editor, so it reaches only tasks whose deliverable is a file it can write. (`registry.py:531`) | **Yes** |

**Model routing — which provider serves the model:**

| Backend | What it is | Runnable from this repo? |
|---|---|---|
| `openrouter` | The **same** Claude CLI harness, pointed at OpenRouter's Anthropic-compatible endpoint. Needs `OPENROUTER_API_KEY` and fails loud without it. (`registry.py:546`) | **Yes** |

`bare` and `openrouter` are deliberately **not** the same measurement and must not be
collapsed into one row (`registry.py:534`): `bare` measures a model inside a scaffold
we control and disclose, `openrouter` measures a model inside Anthropic's harness.

`aura-mcp` is documented so published results can be read honestly, but it requires a
proprietary UE plugin, private local services and an entitled account, none of which
are published — so this repo **refuses it before spending anything**
(`tools/run-agent/aura_rig/cb.py:586`, with an explanatory message). Its login
machinery has been removed from this repository entirely. See
[`../THIRD-PARTY.md`](../THIRD-PARTY.md) section 4.

---

## Authoring a task

The core loop, in the order you need them:

| Doc | Role |
|---|---|
| [`TASK-AUTHOR-GUIDE.md`](TASK-AUTHOR-GUIDE.md) | **Start here.** The end-to-end guide — spec → scaffold → fixture → reference → discrimination — plus the per-task TODO sheet, the spec style guide (under-specification vs. oracle leakage) and the definition of done. These were four documents; they are one now. |
| [`AUTHORING_TEMPLATE.md`](AUTHORING_TEMPLATE.md) | **Spec-format law.** The allow-listed `task.md` sections and what each must contain. Read end-to-end once. |
| [`ANATOMY-OF-A-TASK.md`](ANATOMY-OF-A-TASK.md) | A worked read of one shipped task — useful before writing your first. |
| [`MAPS.md`](MAPS.md) | Eval-map inventory and provenance — which `.umap` belongs to which task, and why four are flat. |

## Verification and PIE

| Doc | Role |
|---|---|
| [`pie-verification-playbook.md`](pie-verification-playbook.md) | **The verifier's design of record.** Every PIE verification primitive, what it can and cannot observe, and the recipes that work headless. |

## The preview (visual) surface

| Doc | Role |
|---|---|

## Harness tour — reading the code

A five-part walkthrough of the harness for someone learning it end to end. It is a
**teaching tour, not a specification**: parts of it are dated snapshots and each
file's banner says which passages to read as history. Where the tour and the code
disagree, the code wins; where the tour and `docs/CHEATSHEET.md` disagree, the
cheatsheet wins.

- [`harness-tour/README.md`](harness-tour/README.md) — the tour's own map
- [`harness-tour/01-run-agent.md`](harness-tour/01-run-agent.md) — `tools/run-agent`, the agent harness
- [`harness-tour/02-verify-single.md`](harness-tour/02-verify-single.md) — `tools/verify-single`, the deterministic gate
- [`harness-tour/03-substrate.md`](harness-tour/03-substrate.md) — the substrate project
- [`harness-tour/04-output-side.md`](harness-tour/04-output-side.md) — runs, summaries, reports
- [`harness-tour/05-advisory-periphery.md`](harness-tour/05-advisory-periphery.md) — the advisory (non-gating) periphery

---

## Conventions

- **The generated indexes win on counts.** [`../tasks/CATALOG.md`](../tasks/CATALOG.md)
  is generated from disk; prose in any doc here can go
  stale, those cannot.
- **`cb where` is ground truth for paths.** Run it before believing any path printed
  in these docs.
- **Docs never reach a model under test.** Agent-visible surfaces are composed from
  the substrate project trees (`UE-projects/<substrate>/`) only, so nothing under
  `docs/` can leak into a prompt.
