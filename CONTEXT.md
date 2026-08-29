# CraftBench — Domain Glossary

> This file is the dictionary for CraftBench's testing-and-measurement words. Read it when a term in another doc or in the code is unclear. Each entry defines one term in plain English.
>
> **Scope of authority — read this before relying on anything below.** This file is authoritative for *what a word means*, and nothing else. When a term here disagrees with another doc's **wording**, this file wins and the other doc should be fixed. When anything here disagrees with the **code**, the **code wins** — full stop. An earlier version of this line claimed authority over the code itself, and that was actively harmful: this file went on describing the verifier hash manifest for months after it was deleted (2026-07-16), so an agent following the old precedence would have tried to reinstate a deliberately-removed grading mechanism. A glossary cannot outrank the thing it describes. For counts and status, defer to `tasks/CATALOG.md` and `cb lint`, which a machine checks.
>
> Everything from here down to "Deprecated terms" is dictionary only — definitions, no how-it-works detail and no file paths (for the file map, see `docs/DOCS_INDEX.md`). After the dictionary come design/decision write-ups (see "Aura wheels adoption") that *do* carry diagrams, file paths, and implementation detail.
>
> **For the real task counts, read [`tasks/CATALOG.md`](tasks/CATALOG.md); it is generated from what git tracks and this file defers to it.** The one-paragraph summary: CraftBench tests AI coding agents on Unreal Engine 5.8 game-programming tasks against a deterministic grader. The task set was deliberately culled in July 2026 to a small template benchmark from which every later task was grown; `cb lint` checks the counts carried in the repo conventions and `tasks/CATALOG.md` against `git ls-files`, so trust those over any prose here. Read on for the vocabulary those statements use.

## What CraftBench is (one screen, plain English)

- **The benchmark.** A fixed set of game-programming jobs for an AI coding agent, each written as a plain description of the behavior wanted. An automatic grader compiles the agent's code, runs the game, and checks whether the behavior actually happened. Same engine every time (Unreal Engine 5.8), same starting project every time.
- **How honest the numbers are (defer to `tasks/CATALOG.md` for the live count).** A task is "fully proven" when the grader passes a correct solution and fails wrong/cheating ones. The July 2026 cull left 9 tasks and the tree grew from there, every committed reference solution grading PASS on Windows + UE 5.8. For exact counts, read [`tasks/CATALOG.md`](tasks/CATALOG.md) — it carries the generated per-task status block.
- **What the grader can check today.** It can build the project, run it and watch behavior, and inspect generated game assets. It cannot yet judge looks/visuals, performance, or code structure as a hard pass/fail — but it can now *show a human* the behavior: opt-in flags run the editor windowed (`--visible`) and capture a screenshot at every checkpoint (`--capture`) for review; those visuals never decide pass/fail.
- **The current priority.** Keep the grader fully automatic and deterministic (no AI deciding pass/fail), and grow the task set from the post-cull template: each new task is one folder (`tasks/<set>/<id>/`) plus per-task folders inside the Unreal project, authored against `docs/TASK-AUTHOR-GUIDE.md` and proven by the discrimination check before it ships.

## Verification model

**Layer** — One kind of check the grader runs on the agent's work. ("Layer" is the unit; the grader is a stack of layers.) Each layer says three things about itself: whether it counts toward pass/fail (whether it *gates* — see below), where it sits in the run order, and what it depends on. The layers, in run order: `ART`, `L1`, `L2`, `L2I` are the checks that can decide pass/fail today; `R2` runs too but only advises. (An `L3` render check exists in code but no task uses it yet, so it does not decide pass/fail in practice — see the `L3` entry below.)

**ART** — The "the file is actually there" floor check (ART = artifact). It confirms the thing the task asked the agent to produce exists and isn't empty. Cheap but real — it's the only hard check for "advisory-only" tasks whose real quality is judged by the AI reviewer (R2). It runs only when a task names an `artifact_path`. Counts toward pass/fail (gating).

**L1** — The "does it compile" check (build layer). It builds the project twice, once as the editor build and once as the shipped-game build (both via Unreal's build tool, UnrealBuildTool / UBT). Both must succeed. Counts toward pass/fail (gating).

**L2** — The "does it actually behave right when run" check (runtime-behavior layer). It launches the game for real — by default with no graphics window (headless) — using a built-in Unreal test object (an `AFunctionalTest`, the engine's standard automated-test actor — we call any such test object a *fixture*), and watches the game state at scheduled moments to confirm the wanted behavior happened. ("PIE" = Play-In-Editor, Unreal's run-the-game-inside-the-editor mode.) Opt-in review modes exist (`--visible` runs it windowed with real graphics; `--capture` screenshots every checkpoint) but the verdict logic is identical either way. Counts toward pass/fail (gating).

**L3** — The "does it look right" check (render layer): the same kind of in-game test (`AFunctionalTest`), but run **with graphics actually turned on** (a real renderer rather than the no-graphics mode) so the scene draws, for tasks whose deliverable is *visible* — a UI widget appears, a particle effect spawns, a material shows on a model. The pass/fail part still comes only from plain yes/no facts the test checks in code; the screenshot it captures (under `Saved/CraftBench/*.png`) is handed to the AI reviewer for comment — comparing pixels **never** decides pass/fail (the rule FR-020d: no looks-based and no AI judgment in the hard gate). The reusable test template for this is `RenderProbeFunctionalTest`. Designed to count toward pass/fail (gating) — but as of today no task wires it up, so it is unproven end-to-end (see `tasks/CATALOG.md`).

**L2I** (L2-introspect) — The "is the generated asset built correctly inside" check (structural layer). It opens a generated Unreal asset file (`.uasset`) and reads its internal structure — its node graph, its settings, its default values — using read-only editor scripting, with no graphics and no AI. Counts toward pass/fail (gating).

**gating** — Whether a layer's result is allowed to set the official pass/fail. A gating layer can flip the verdict; a non-gating one cannot. This single yes/no *is* the line between an official check and a merely-advisory one.

**Certified verdict** (`overall`) — CraftBench's official PASS/FAIL for a submission, decided **only** by the gating layers. It is fully mechanical (rule FR-020d): every check is a concrete fact — a build succeeded or not, an in-game test passed or not, an asset's structure matched or not, or a code-shape rule held or not. No AI model has a vote in this verdict.

**Advisory / R2** — A check that comments but does not decide. An AI reviewer gathers its own evidence and writes a quality note (on design, on advice, on how it looks) and a rubric score, but it can **never** change the official pass/fail. **"R2" is just the name of this advisory check — it is not a level or rank in some scale.**

**Discrimination check** — The bar a task must clear before it's allowed to ship (rule FR-017): the known-correct solution must PASS, and every wrong-or-cheating version (empty, or gaming the test) must FAIL — and each failure must be caught by a *different, specifically-named* check. This is what proves a task's grader really tests the intended skill, instead of just checking "it compiles" or "a file exists." So "this task has a real grader" means "it passed the discrimination check."

**Anti-circularity** — The rule that the grader must figure out what happened in the game *on its own*, using neutral Unreal Engine tools that CraftBench controls. It must **never** ask the agent-being-tested's own tools to report whether the agent succeeded, and the AI reviewer (R2) must run on a different model than the agent. Put simply: the agent's own words and tools are *the thing under examination*, never trusted as proof about what happened.

**Capture primitive (P1–P5)** — The five neutral ways the grader collects evidence about the running game, independent of which layer asks for it: P1 read live game state over Unreal's Remote Control link; P2 read an asset's structure via editor scripting; P3 read the logs / test report; P4 read a performance-profile CSV; P5 take a screenshot. (A "primitive" here just means a basic, reusable evidence-gathering technique.)

## Measurement model

**Product / `product_id`** — One thing we put under test and compare. A product is a chosen AI model paired with a chosen set of tools it's allowed to use (`model × tool-layer`). We always say exactly which pairing it is — for example, a result from "the model using a tool layer" is never reported as if it were "the tool maker's full agent." The compared products:

- **Baseline** — a Claude model with **no Aura tools and no Unreal tools** — only a plain file editor and shell. This is the control: it shows what a tool layer *adds* on top of plain Claude. (Aura = the third-party Unreal AI assistant CraftBench is measuring against.)
- **Unreal-MCP** — a Claude model with its own file/shell tools **plus Epic's first-party in-editor MCP server** (UE 5.8's stock `ModelContextProtocol` plugin). The "stock editor tooling" comparison point: no Aura anywhere. Slug `unreal-mcp:<model>`.
- **Aura-MCP** — a Claude model driving **only** a commercial third-party Unreal agent product's tool layer (its tools exposed over the standard tool protocol, MCP — Model Context Protocol), with the generic actuators denied so nothing else can reach the project. This measures that product's *tools*, **not** its own autonomous agent. Slug `aura-mcp:<model>`; label it that way, never with the bare product name.
- **Aura-MCP is disclosed but not reproducible here.** The arm's *definition* ships in full — `adapters/registry.py`'s branch for it, its MCP config, its tool-denial list — because the difference between that definition and Unreal-MCP's *is* the published result and has to be auditable. Its *runtime* does not ship: the vendor's closed-source UE plugin, the two private web services behind it, an entitled account, and the login that authenticated one. Selecting the slug from a public clone fails in the first second with that explanation. Results attributed to Aura-MCP in any write-up are therefore **not independently reproducible**; Baseline and Unreal-MCP are.

**Retired products.** `adapters/registry.py:_REMOVED_BACKENDS` is the honest record of the labels that once appeared in this glossary and no longer name anything runnable: **Aura-Product** (the vendor's own autonomous agent, driven through its shipping UI over a browser-automation protocol), **Aura-Agent** / **Aura-Baseline** (an earlier vendor-side loop over a local HTTP/SSE endpoint), and **`aura-mcp-bridge`** (a CI-only outside loop that reached the product through a single Python-execution bridge call, collapsing its rich tools to roughly the Baseline experience). None of them are part of this release, and none should be presented as a current path. The compared products are the three above.

The three compared products all go through the same pipeline: a cleaned-up prompt (with the answer key removed) → the agent's submitted files → the official pass/fail. The driver is `tools/run-agent`: `run.py` does a single run (writing one `result.json`); `run_batch.py` runs many at once using two worker pools — one pool runs the agents (kept to one-at-a-time for the editor-backed arms since they share the single live editor), the other runs the cold-start Unreal grading (`--verify-concurrency`) — with each task isolated and a live status file the dashboard reads. The comparison **grid** is one `run_batch` per product, then `compare` rolls the `result.json` files up into the standard skill-bucket breakdown. (An older batch-runner scaffold was superseded by `run_batch.py` and never shipped; the only idea it had that `run_batch` lacks is retrying a task several times.)

**Substrate** — The shared Unreal project the agent edits, pinned to one engine version (`CraftBenchTemplate`). ("Substrate" = the fixed ground the tasks are built on.) It is split in two: a part the agent is allowed to change (the runtime code module) and a grader-only part the agent must not touch. That grader-only part is protected **by construction, not by detection**: the graded copy of the project is materialized from **git HEAD**, so an agent's edit to the grader files on disk simply never reaches the grade — there is nothing to detect, because the edited bytes are not the bytes that get built. Committed changes to it are gated on human review (on commit).

> **There is only ONE "pin" now.** `substrate_revision` in `pinning.py` records **provenance** — which git revision of the substrate was graded (FR-002). Nothing else is pinned.
>
> Historical note, because the old vocabulary is still in git history and in older docs: there used to be a second, *integrity* pin — a `verifier_hashes.json` SHA-256 manifest checked every run, with a `--regen-verifier-hashes` maintainer flag and its own exit-3 REJECT. **It was retired 2026-07-16 and no part of it exists today** (`tools/verify-single/hashes.py` is gone, no `verifier_hashes.json` is tracked, and the only surviving mentions in `run_task.py` are comments recording the removal). Git-HEAD materialization replaced it and is strictly stronger. **Exit code 3 stays retired-and-reserved** so nothing downstream mistakes a historical hash-REJECT for a new failure mode; sandbox rejection is exit 4 and is unchanged.

**Gold set** — A hand-certified roster of task *seeds* used as ground truth while the corpus was being grown. Seeds are **starting points, not finished tasks**: each is turned into a concrete, testable task named for what it *actually* checks, never shipped under its original seed title. `tools/verify-single/gold_set.txt` is the shipped list.

**Contamination** — When the agent gets to see the grader's internals it shouldn't (the grading spec, the reference solution, or the anti-cheating notes). Prevented by giving the agent a cleaned prompt, a cleaned workspace, and a fresh start — not merely by spinning up a fresh sub-agent. On live-editor runs the harness additionally hides, before the editor launches: the grader module's file bodies (stubbed), the sandbox manifest, and every OTHER task's files — both flat scaffold files (found by their `for task <id>` header tag) and whole per-task folders (source, maps, asset baselines) — all restored after the run.

## Deprecated terms

**~~R0 / R1 / R3~~** — Removed 2026-06-02. There used to be talk of a "rigor spectrum" R0–R3; drop it. The real distinctions are simpler: official-vs-advisory is just **`gating`** (does the check decide pass/fail); "does the official check truly test the intended skill" is the **Discrimination check**; and any future second kind of advisory review (looks-based, or a stronger judge) will just be a **label inside the advisory block**, not a new rung on a scale. Do not bring back an `R0/R1/R2/R3` spectrum.

**~~substrate-pin~~ / ~~`substrate_hashes.json`~~ / ~~verifier hash manifest~~ / ~~`verifier_hashes.json`~~ / ~~`--regen-verifier-hashes`~~ / ~~`--regen-substrate-hashes`~~** — **All retired 2026-07-16.** The whole grader-integrity-by-fingerprint mechanism is gone: no `hashes.py`, no manifest file, no regen flags, no exit-3 REJECT. (History, since the names recur in older docs and git log: `substrate_hashes.json` was renamed to `verifier_hashes.json` on 2026-06-08 to stop it colliding with the `substrate_revision` provenance pin — then the whole thing was deleted six weeks later.) Grader integrity is now **git-HEAD materialization + human review**, which is stronger because it prevents rather than detects. **Exit code 3 is retired and reserved** — do not reuse it. `substrate` the project noun is unchanged (it is still the right word for the project under test).

---

## Removed for the open-source release: the vendor-benchmark design record

This file used to end with a long design record (2026-06-02, "Aura wheels
adoption") comparing CraftBench against a commercial vendor's own internal,
non-public benchmark suite — which of its mechanisms to adopt, which to reject,
and a per-section critique of where its grading was fragile. It was sourced from
an internal summary document that is not part of this release, and it described
a third party's unpublished engineering in detail. Publishing that would have
been a disclosure of someone else's work, not of ours, so the whole section was
cut rather than trimmed.

Nothing in it was load-bearing for the definitions above: the two conclusions it
actually drove — a self-refilling matrix runner with usage capture, and the
fail-closed discrimination matrix as a mandatory per-task artifact — are both
shipped and documented on their own terms (`cb bench` / `cb matrix`, and
`cb discriminate` plus each task's `discrimination/MATRIX.md`).
