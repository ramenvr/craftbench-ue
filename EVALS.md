# How CraftBench evals & generation run

One-page runbook. Deep dives live in
`DEVELOPING.md` (architecture), `docs/TASK-AUTHOR-GUIDE.md` (the end-to-end
authoring guide: spec style, the implementor checklist and the definition of
done), `docs/pie-verification-playbook.md` (L2 recipes),
`tools/run-agent/README.md` (the arm definitions), and `docs/DOCS_INDEX.md`
(map of everything else).

## What an eval is

A task = a **behavior spec** (`tasks/<set>/<id>/task.md`) + a **level** in a
shared UE 5.8 substrate + a **deterministic verifier** (`tools/verify-single/`).
Every spec names its substrate in the `substrate:` key: `ThirdPerson` — the
stock Third Person C++ template, and what almost every task uses — or
`CraftBenchTemplate`, the older scaffold project. New team-authored tasks land directly in
the basket matching the agent-written surface: `tasks/bp/` (Blueprint/asset/
editor deliverables) or `tasks/cpp/` (C++ source deliverables). 

PASS/FAIL comes only from the verifier — ART (the artifact-present floor),
L1 (UBT build of both targets), L2 (`AFunctionalTest` driven in headless PIE)
and L2I (structural `.uasset` introspection via editor-Python). **No LLM sits
in the gate.** The R2 judge (`tools/verify-r2/`) is advisory by design, not yet
by circumstance: it annotates a rubric score and can never change a verdict.

## Authoring a new eval

(The condensed checkbox version of these steps, with file paths and gates,
is `docs/TASK-AUTHOR-GUIDE.md`.)

**Before inventing one:** the design target the task set is built against is
**50/20/30 pass-rate** — 50% of evals should pass every run, 20% sometimes, 30%
never. A set where everything passes discriminates nothing, which is the whole
reason the discrimination matrix is mandatory rather than advisory.

The eval-planning workbook those numbers came from was an internal spreadsheet
keyed by owner; neither it nor its per-owner CSV mirrors are part of this
open-source release, and task specs that used to cite them now say so in place
of a path. What ships instead is the authoring law itself:
`docs/AUTHORING_TEMPLATE.md` (spec format) and `docs/TASK-AUTHOR-GUIDE.md`
(how to write a spec that under-specifies without leaking the oracle, plus the
definition of done) — enough to author against without the workbook.

1. **Write the spec** — `tasks/<set>/<id>/task.md`. Opens with the **v2
   front-matter block** (`--- id / substrate / set / tier / layers: [L1, L2] /
   fixtures: ["L_<Map> :: A<Name>FunctionalTest"] ---`; grammar in
   `docs/AUTHORING_TEMPLATE.md` and `tools/verify-single/spec.py`).
   Body: behavior-only prompt (no class or pattern names), workspace-state
   section, 3–5 anti-gaming notes.

   Workspace-state section is for agent to understand how to do #2, anti-gaming is for the bad solution that will be used in #3 to generate variants (what are some possible bad answers we could get?)
2. **Write the two C++ halves the map will hold** — nothing else creates them,
   and step 3 assumes both are already on disk. Copy them from the flagship t0
   pair and rename:
   - the **agent-writable scaffold actor** at
     `UE-projects/<substrate>/Source/<AgentModule>/Tasks/<id>/<Name>Actor.{h,cpp}`
     — constructor stamps `Tags.Add(FName("<Tag>"))` and **nothing else**
     (no BeginPlay/Tick; that's the agent's job). Its header comment MUST
     contain `// … for task <id>` or the fairness layer can't hide it from
     other tasks' runs. `<AgentModule>` is `CraftBenchTemplate` or
     `ThirdPerson`, per the spec's `substrate:`.
   - the **L2 fixture** at
     `UE-projects/<substrate>/Source/CraftBenchTests/Tasks/<id>/<Name>FunctionalTest.{h,cpp}`
     deriving `ACraftBenchFunctionalTest` — resolve the host **by tag**, call
     `SetCheckpointSchedule({…})` in world game-time, assert in
     `OnCheckpoint`, and fail via a **named ASCII** message. Verifier-only and
     review-gated on commit.

3. **Build the task map** — a level created from `Template_Default` with the
   tagged scaffold actor and the functional-test fixture placed in it. Build it
   in the editor / via aura-mcp (real off-screen RHI, never `-nullrhi`) and
   commit the binary at
   `Content/Maps/<id>/L_<Map>.umap` — **the committed binary is the only map
   source** (scaffolders retired 2026-07; a missing binary is an explicit L2
   FAIL and a `cb lint` error). Add its row to `docs/MAPS.md`; `cb lint`
   errors if a committed map has none.
4. **Generate the reference + discrimination variants** — `tasks/<set>/<id>/reference/`
   (the PASS oracle) and `discrimination/<variant>/` (one per anti-gaming note, plus
   the empty stub). Both mirror the agent-writable prefix **including** the
   `Tasks/<id>/` segment, or the overlay lands beside the scaffold instead of
   onto it. Record the expected failure substring per variant in
   `discrimination/MATRIX.md`.
5. **Lint, then validate on the live tree** — while the fixture/map are still
   uncommitted, run the static lint and the token-free discrimination batch:

   ```
   cb lint --task <set>/<id>
   cb discriminate --task <set>/<id> --wip
python tools/run-agent/publish_results.py <run-dir>        # share a graded run with the other machine (results/<host>/; runs/ stays gitignored)
   ```

   Required outcome: reference **PASS**, empty stub **FAIL**, every variant **FAIL on its named assertion**.
   `--wip` is not optional here: grading materializes from **git HEAD**, so
   without it your uncommitted fixture/map are simply absent and every leg
   fails for the wrong reason.
6. **Commit everything + PR** — the spec, scaffold pair, L2 fixture, the
   `.umap`, reference, and discrimination package go in the **same commit**.
   `Source/CraftBenchTests/` changes are review-gated on commit,
   and grading materializes from **git HEAD** — the task only becomes
   `cb eval`-able after the commit lands (until then, `--wip` is the path).
7. **Post-merge, re-prove it from HEAD** — the two gates that only mean
   something once the commit has landed:

   ```
   cb discriminate --task <set>/<id>      # no --wip: the COMMITTED tree discriminates
   cb batch-eval --references all         # your task broke no neighbour — last sweep 18/18 (2026-07-28); next full gate 21/21
   ```

   Shared-substrate breakage (Build.cs deps, tag collisions, pawn-resolution
   ambiguity) only shows up in that whole-set sweep.

## Running an eval on an LLM

`cb eval --task <set>/<id> --model <backend>` drives four stages:

1. **Mask the surface** — the agent-visible project is composed to contain only what the current task needs: its map, its scaffold actor, its asset baselines. The verifier fixtures are stripped to abstract base classes, `AGENT_WRITABLE.json` is withheld, and foreign per-task trees are pruned (see gaps below).
2. **Extract the prompt** — `prompt_extract.py` keeps only *Prompt given to the agent* + *Workspace state pre-task*. Verifier spec, anti-gaming notes, and references are hidden.
3. **The agent works** — where the eval actually runs with LLM generating given the prompt. The backend:
   `claude-p`/`openrouter:<model>` (files only, no editor), `unreal-mcp:<model>`
   (Claude + Epic's stock editor MCP), or `bare:<provider/model>` (our own minimal
   five-tool loop). The third published arm, `aura-mcp:<model>`, is disclosed but
   not runnable from this repository — `cb` refuses the slug.
4. **Grade on a fresh clone** — the verifier materializes the substrate from **git HEAD** (never the agent's tree — an agent edit to `Source/CraftBenchTests/` on disk never reaches the grade), sandbox-checks the submission (`AGENT_WRITABLE.json`, exit 4 on violation), overlays the deliverable, then runs L1 → L2 → L2I. `report.json` carries the verdict and, on failure, the named assertion that fired. The built project stays behind as a workdir under `<CB_ROOT>/wd` (`summary.json` records the path as `graded_workdir`); retention defaults to `slim`, so a finished one is ~42 MB — `out/` plus a launchable project — instead of the ~5.9 GB it built. Reclaim older ones in place with `cb clean --workdirs --slim` (`--check` dry-runs).

### Agent-visible surfaces

| Backend | Surface | Hidden there |
|---|---|---|
| `claude-p` / `openrouter` / `unreal-mcp` | `/tmp` (or `%TEMP%`) workspace copy (`workspace.py`) | `Source/CraftBenchTests/`, `AGENT_WRITABLE.json` |
| `bare` | `/tmp` (or `%TEMP%`) workspace copy (`workspace.py`) | `Source/CraftBenchTests/`, `AGENT_WRITABLE.json` |
| `aura-mcp` (live-project) | the checkout itself | fixture bodies stubbed, foreign trees parked, restored byte-identical after |

Solutions and references live under `tasks/…/reference/` — **outside the substrate** — so no composition path can copy them into the agent surface.

### Known isolation gaps (fix in flight)

- The pre-migration **flat maps** at `Content/Maps/` root survive scratch composition (pruning is per-task-*directory*); migrating them into `Content/Maps/<task-id>/` folders closes this.
- `build_workspace` does no per-task pruning yet — workspace backends can see foreign maps/scaffolds and `Tools/`. Same `task_layout` staging applies there.

## Quick commands

```
cb eval --task cpp/t0-sanity-log-on-beginplay --model claude-p:sonnet  # one graded run
cb bench --model sonnet-5,claude-p:opus --task <set>/<id> --repeat 1      # compare models → runs/bench-<ts>/leaderboard.html
cb batch-eval --references all                               # grade every reference (token-free)
cb discriminate --task <set>/<id>                            # THE authoring gate: reference PASS + empty/variant FAIL (cb refgate is retired)
cb lint [--task <id>]                                        # static spec lint, no UE
python3 -m unittest discover tools/verify-single/tests       # verifier unit tests, no UE
cb eval --task <set>/<id> --preview                          # ...or capture it LIVE during the run (also: bench, headless)
```
