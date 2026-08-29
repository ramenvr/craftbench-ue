# CraftBench Task Author Guide

> The single guide to authoring a task. The only other authoring document is
> [`AUTHORING_TEMPLATE.md`](AUTHORING_TEMPLATE.md), which is the **normative**
> spec format — a spec that departs from it fails `tasklint`. Everything else
> lives here, in four parts:
>
> 1. **The walkthrough** (below) — what a task is, and the path from idea to a graded task.
> 2. **Spec style** — what the agent may and must never see.
> 3. **The implementor checklist** — the step-by-step build.
> 4. **Acceptance** — what must be true before it ships.

> **TL;DR**
> 1. A task = one observable behavior contract, graded deterministically (L1 build + L2 PIE test). If you can't name the trigger, the observable, and the tolerance, it's not a task yet.
> 2. Prompts are **behavior-only** — no UE class/plugin/asset/pattern names. The agent picks the pattern; the verifier checks the behavior.
> 3. Pick a **verification primitive** before writing anything (`AUTHORING_TEMPLATE.md` § "Pick a verification primitive"). Subjective signals never gate.
> 4. **Two authoring steps, not one**: idea → spec (an ambiguous idea gets concrete choices resolved on the open design axes, never guessed), then spec → the runnable artifacts. Claude Code skills under `.claude/` used to drive both halves; they are not part of this open-source release, so the steps below are the hand-run version of exactly what they did.
> 5. A task is done only when the reference PASSes and every gaming variant FAILs **at its named assertion** — run `cb discriminate --task <id>`.
> 6. Fixture + binary `.umap` are committed **together** — `cb eval` grades from **git HEAD**, so an uncommitted fixture/map simply doesn't exist to the grader; committed `Source/CraftBenchTests/` changes are review-gated on commit.
> 7. The pipeline **closes** post-commit by re-running **`cb discriminate --task <set>/<id>` on the committed tree** — the committed reference must grade PASS and the empty leg must FAIL for its named reason. Reference gating lives HERE, at authoring time: benches no longer auto-gate, fresh-machine onboarding is `cb smoke`, and per-run protection is envgate. (`cb refgate` was the older single-purpose form of this gate and is retired — see `docs/CHEATSHEET.md`.)
> 8. The condensed end-to-end TODO sheet (spec → scaffold → fixture → map → reference → discrimination → gates → PR → the discriminate close) is **`docs/TASK-AUTHOR-GUIDE.md`** — work from it; this guide is the why behind each line.

Audience: engineers authoring tasks, possibly in bulk. This guide is the narrative rail; the law is `docs/AUTHORING_TEMPLATE.md` (section order, heading text, layer semantics). When they disagree, the template wins.

---

## 1. What a task is

A task is one folder — `tasks/<set>/<id>/`, with the spec at `task.md` and the reference solution + discrimination variants co-located (`reference/`, `discrimination/`, plus an optional verifier-owned `ue-config/` ini overlay; layout contract: `tasks/README.md`). New team-authored tasks land directly in the basket matching the agent-written surface: **`tasks/bp/`** (Blueprint/asset/editor deliverables) or **`tasks/cpp/`** (C++ source deliverables). The spec specifies four things: the behavior the agent must produce, the workspace it starts from, the verifier that decides PASS/FAIL, and coverage metadata. Two families (`AUTHORING_TEMPLATE.md` § "What a CraftBench task is"):

- **Atomic** — probes one concept from `tools/coverage/concepts.csv`. Most tasks.
- **Compositional** — integrates 3–7 concepts and must cite a real, public production pattern (Hard Rule #1). Adds three extra H2 sections.

**Machine facts live in the v2 front matter; body H2 headings are normative for the rest.** The spec opens with a `--- id / substrate / set / tier / capability_bucket / layers / fixtures / … ---` block; THE single parser is `tools/verify-single/spec.py::parse_task_file` — everyone (runner, rig, lint, dashboard) imports it, and legacy H2-metadata specs parse only via its fallback (and draw a `cb lint` WARN). The markdown body keeps the human-facing H2 sections — prompt, workspace, verifier spec, anti-gaming — and tools still join on exact, case-sensitive H2 text there (including `tools/run-agent/prompt_extract.py`'s allow-list). Copy heading text verbatim from the template, in template order. A misspelled heading doesn't error — it silently drops the section.

**What the agent actually sees.** Only two sections are shown to the agent, by allow-list (`tools/run-agent/prompt_extract.py`, `ALLOWED_SECTIONS`):

- `## Prompt given to the agent`
- `## Workspace state pre-task`

Everything else — verifier spec, anti-gaming notes, checkpoints, tolerances — is the answer key and is never shown. Write the two visible sections as if they were the whole task, and never leak the verifier into them.

## 2. The five Hard Rules

Non-negotiable. (These came from an authoring skill under `.claude/`, which is not part of this open-source release — the rules themselves are reproduced in full here, so nothing is lost with it.)

| # | Rule |
|---|---|
| 1 | Compositional tasks cite a **real, public production pattern** and compose ≥3 concepts. Invented combinations are not acceptable. |
| 2 | **Behavior-only prompts.** No class names, plugin names, asset-type names, design-pattern names, no "use the X system." |
| 3 | **Only deterministic facts gate the score** (spec FR-020d). LLM judges / the R2 track are advisory, never gating. |
| 4 | **Public sources only.** Every concept cites its Epic doc URL; every production-pattern citation is publicly verifiable. |
| 5 | **Lyra tasks declare the dependency** at the top of *Workspace state pre-task*. Substrate default: **gameplay tasks (a playable/possessed character) default to `ThirdPerson`** — project decision 2026-08-05: it ships Manny/Quinn + the animation set natively, so no asset drops and every graded run is human-reviewable; non-gameplay/pure-actor tasks may still use `CraftBenchTemplate`. |

(A handful of GAS tasks name the GAS contract — e.g. `tasks/cpp/gp-poison-dot-stack-cpp/task.md` names the `Ability.Poison` tag — as a *documented exception*: verifying the effect *through GAS* is the point. If you take that exception, say so in the spec the way that task does.)

## 3. Lifecycle at a glance

```
 idea ──[write the spec]──► tasks/<set>/<id>/task.md (spec)
                                        │
                                        ▼
        [build the verifier] ──► 6 artifacts (scaffold, fixture, map
                                        binary, reference, variants, MATRIX.md)
                                        │
                                        ▼
        cb lint --task <id> ──► static spec/layout lint clean (tasklint.py)
                                        │
                                        ▼
        cb discriminate --task <id> ──► reference PASS + empty/variants FAIL
                                        at their NAMED assertions (FR-017)
                                        │
                                        ▼
        commit fixture + .umap TOGETHER ──► PR (human review gates any
                                        Source/CraftBenchTests change)
                                        │
                                        ▼
        cb discriminate --task <set>/<id> ──► re-run on the COMMITTED tree:
                                        the reference grades PASS and the empty
                                        leg FAILs (the close)
                                        │
                                        ▼
        cb eval --task <id>  (full agent run, grades from git HEAD)
```

Stages: **design** (sections 4–6 below), **build** (section 7), **lint + discriminate** (sections 8–9), **commit + PR + the discriminate close** (section 11). Don't skip forward: a spec that fails the verifiability gate wastes everything downstream.

## 4. Gate on verifiability first

Before writing a single spec section, map the behavior to a **reusable verification primitive** — do not invent a verifier. The picker table lives in `AUTHORING_TEMPLATE.md` § "Pick a verification primitive — do not invent a verifier" (full recipes: `docs/pie-verification-playbook.md`). Condensed:

| Primitive | Observes | Covers |
|---|---|---|
| `beginplay-log-capture` | GLog substring/count via a pre-BeginPlay `FOutputDevice` | "did/did-not log", sanity, clean-teardown |
| `pie-checkpoint-sampling` | Actor state at fixed world-times (`SetCheckpointSchedule` + `OnCheckpoint`) | spawn timing, self-destruct, lerp, transforms over time |
| `timer-framerate-legs` | Same fixture at two `-FPS` rates in separate PIE processes | framerate-independence (anti-overfit for anything timed) |
| `pie-state-probe` | Engine state read in-fixture: location/velocity, MovementMode, ASC tags/abilities | GAS arcs, movement modes, "state holds at t" |
| `L2-introspect` (L2I) | Static asset/graph structure via headless editor-Python | materials (structural), AnimBP graphs, widget trees, DataTables |
| `log-assertion` | On-disk `Saved/Logs/*.log` substrings/sequences | sequenced logs, absence assertions |
| `overlap-probe` / spatial readback | Overlap delegates; per-instance ISM transforms | trigger volumes, attach points, scatter footprints |
| `save-roundtrip` | `LoadGameFromSlot` + disk compare after wiping in-memory state | persistence, slot isolation |
| profiler (CSV) | frame times | **advisory only — never gates** |
| R2 advisory judge | evidence + prose to a judge model | design quality, visuals — **never gates** |

If the only success signal is subjective ("looks right", "well-architected", "faster") it **cannot gate** (Hard Rule #3). Narrow it to an observable proxy that can, or author it explicitly as advisory-only — never pretend (the task-authoring skill (under `.claude/`, not shipped) Phase 1).

Also restate the idea as one sentence before anything else: *"After \<trigger\>, \<observable\> is true within \<tolerance\>."* If you can't fill all three slots, the idea needs clarifying, not authoring (Phase 0 of the same skill).

## 5. Write the spec

Walk your idea through all of this, then self-review it against the Hard Rules. Where the idea leaves a decision-shaping axis open — the observable contract, surface (C++ / BP / agnostic; the `-cpp`/`-bp` suffix convention for pairs), substrate (`ThirdPerson` default for gameplay, owner 2026-08-05), tier + the 50/20/30 pass-rate band, layers (L1/L2/L2I), visual application (the 2026-08-06 visible-character/mannequin gate), camera-plan intent, anti-gaming surface — the skill asks you with **concrete choices** (AskUserQuestion, 2–4 options with a recommended default) and iterates until the spec is fully determined, rather than guessing. What follows is what it (or you, by hand) must produce, keyed to three exemplars:

- **`tasks/cpp/t0-sanity-log-on-beginplay/task.md`** — minimal structure; log-capture primitive; also the migrated template for the per-task UE folder layout (section 7).
- **`tasks/cpp/gp-spawner-population/task.md`** — checkpoint sampling (count-by-tag at fixed world-times); the canonical worked example the build-verifier skill mirrors.
- **`tasks/cpp/gp-poison-dot-stack-cpp/task.md`** — a T2 GAS task; relative-ratio gates, calibration notes, a documented advisory hole — the model for *honest deferral* (an unenforced defense is written down as advisory, not silently claimed).

First the **front-matter block** (the machine facts; v2 is normative — legacy H2 metadata parses only via the fallback and draws a `cb lint` WARN). Keys, per `tools/verify-single/spec.py`:

- `id` — kebab-case, names the behavior: `gas-stamina-regen` good, `uattributeset-subclass` bad; MUST equal the task's folder name.
- `substrate` — parser default `CraftBenchTemplate`; `ThirdPerson` selects the stock UE 5.8 Third Person substrate (`UE-projects/ThirdPerson/`). **Policy (project decision 2026-08-05): new gameplay tasks declare `substrate: ThirdPerson` explicitly** — it ships the mannequin characters natively, so playable-character tasks need no asset drops into a minimal substrate (the pre-2026-08-05 `gp-glide-stamina-bp` "mannequin pool" workaround this replaced). `CraftBenchTemplate` remains right for minimal scaffold-actor tasks with no playable character.
- `set` / `tier` / `capability_bucket` (+ optional `category`) — `tier` is T0–T3 by honest senior-dev hours.
- `layers` — most tasks: `[L1, L2]`. Asset tasks add `L2I` (paired with a `## Verifier introspection` body section + an `introspect:` list; wired by the 6 `tasks/asset-set/` tasks, first graded 2026-07-27 — originally proven on the retired `mat-emissive-pulse` and `umg-image-brush-bound`, git history).
- `fixtures` — `"L_<Map> :: A<Name>FunctionalTest"` entries, one per fixture. Use even for a single fixture; multiple fixtures run `+`-joined in one editor session, fresh PIE world per leg. (Pattern-only today: the sole multi-fixture task, `gp-gas-launch`, was retired 2026-07-21; synthetic tests keep the path alive.)
- `fps_legs` — optional list of fps values (e.g. `[60, 20]`) that re-run the *same* fixture per rate in its own PIE process. The standard anti-overfit for anything timed.

Then the **markdown body** (heading text verbatim, template order — humans plus the prompt extractor read these):

- **`## Primary concept`** — exactly one `concept_id` from `tools/coverage/concepts.csv` + its Epic doc URL, plus a line on why this concept is load-bearing. Torn between two? Probably compositional.
- **`## Prompt given to the agent`** — 50–200 words, one paragraph, addressed to a senior gameplay programmer. Run your draft against the contrastive example in `AUTHORING_TEMPLATE.md` § "Good vs bad: contrastive example":

  > GOOD: "The player character has a stamina resource that drains while sprinting and regenerates while not sprinting…"
  > BAD: "Implement a stamina system using the Gameplay Ability System. Create a UAttributeSet subclass…"

  The BAD prompt reduces the task to transcription. Allowed: gameplay terms, observable side effects, input contracts, timing. Forbidden: UE class/plugin/asset/pattern names, "use the X system."
- **`## Workspace state pre-task`** — the exact starting state, split into "files that **exist**" and "files that **do not exist**" (copy t0's shape). This is the integration seam with the build-verifier skill: name the placed actor *behaviorally* ("an actor placed in the level via the Outliner"), name the **tag** the scaffold constructor stamps, name the **map**. Keep it to what the agent could learn from `ls` — don't leak the verifier.
- **`## Verifier specification`** — per-layer assertions in pseudo-code, written to **discriminate**: ≥2 checkpoints or a rate-of-change (never an end-state a constant could satisfy), host placed off the world origin, per-run randomization where a literal could sneak through. Prefer relative gates (ratios, "still dropping?") over absolute magnitudes — see gp-poison-dot-stack-cpp's design note. Mark anything unenforced as DEFERRED/advisory in the spec, the way gp-poison-dot-stack-cpp's stack-cap note does; never promise a defense the fixture doesn't perform.
- **`## Reference solution metadata`** — honest LOC range, files touched, senior-dev hours, calibrated from actually sketching the solution. A "T1" that takes six hours is mis-tiered.
- **`## Anti-gaming notes`** — section 6 below.
- **`## Hidden invariants`** — optional but strongly encouraged whenever a constant or single-point fit could satisfy the visible assertions; the runnable check lives in the review-gated verifier module (graded from git HEAD), only the prose summary is here.

Compositional tasks add `## Composed concepts`, `## Production-pattern justification`, `## Concept-interaction notes` at the fixed positions the template defines.

## 6. Anti-gaming pre-mortem (3–5 entries, mandatory)

Each entry pairs a concrete gaming failure mode with the verifier defense. Work from the generic menu in `AUTHORING_TEMPLATE.md` § "Anti-gaming guidance":

constant return · single-point fit · wrong-path success · test disabling · magic-number mutation · mock substitution · time/frame coupling · asset-only solution

Worked examples to imitate:

- **t0** — *constructor-time log*: agent puts `UE_LOG` in the constructor; defense: the listener binds after world spawn, before the BeginPlay window, so CDO-construction logs don't count. *Multiple emits*: assert `== 1`, not `>= 1`.
- **gp-spawner-population** — *spawn-one-and-stop / over-spawn loop*: exact-count checkpoints (5 → 5-after-respawn → 0-after-teardown) catch both; *rootless (0,0,0) spawn*: the host is placed off the world origin so the radius check fails. (For anything *timed*, the standard anti-overfit is a second `-FPS` leg via `## Verifier framerate legs` — a tick-counter fit to 60 Hz fires at the wrong wall time at 20 FPS; the retired `gp-timer-delayed-destroy` task modeled this, git history.)
- **gp-poison-dot-stack-cpp** — *instant burst vs periodic*: sample several points across the window and require stepwise decrease; *never-stops*: assert stability after the duration. Its cap entry is a documented advisory hole ("an uncapped stack is NOT caught") — that honesty is the standard.

Every note you write becomes a **discrimination variant** in section 8 — if you can't build a failing submission for it, either the defense already falls out of an existing assertion (say which, in the MATRIX row) or the note is decorative and should be rewritten.

## 7. Make it runnable — the 6 artifacts

The canonical worked example is task `tasks/cpp/gp-spawner-population/task.md` plus its scaffold, fixture, map and reference — mirror it. (An authoring skill under `.claude/` used to generate these from templates; it is not part of this open-source release, so the six artifacts below are written by hand against that example. Paths are relative to `UE-projects/CraftBenchTemplate/` unless noted.)

| # | Artifact | Path |
|---|---|---|
| 1 | Task spec | `tasks/<set>/<id>/task.md` (repo root) |
| 2 | Agent-writable scaffold actor | `Source/CraftBenchTemplate/Tasks/<id>/<Name>Actor.{h,cpp}` |
| 3 | L2 fixture | `Source/CraftBenchTests/Tasks/<id>/<Name>FunctionalTest.{h,cpp}` |
| 4 | Committed map binary | `Content/Maps/<id>/L_<Map>.umap` + an inventory row in `docs/MAPS.md` (placed actors, automation name, authoring provenance). The committed binary is the ONLY map source — author in-editor or via aura-mcp; a missing binary is an explicit L2 FAIL (scaffolders retired 2026-07) |
| 5 | Reference solution | `tasks/<set>/<id>/reference/Source/CraftBenchTemplate/…` (repo root) |
| 6 | Discrimination variants + matrix | `tasks/<set>/<id>/discrimination/<variant>/…` + `MATRIX.md` (repo root) |

**Per-task UE folders are the convention for new tasks** (`t0-sanity-log-on-beginplay` is the migrated template; the bp-g2 ports predate it and stay flat at the module root — both shapes work). Both modules' `Build.cs` already do `PrivateIncludePaths.Add(ModuleDirectory)`, so sources under `Tasks/<id>/` resolve without further build edits; asset baselines go under `Content/Tasks/<id>/`. Note the automation-test name for a **foldered** map gains the folder segment — `Project.Functional Tests.Maps.<task-id>.<Map>.<Class>` — which the runner's map locator derives automatically; only a hand-written `--test-filter` needs to care.

The hard invariants the skill enforces — know them so you can review its output:

1. **Identity by tag, never by class.** The scaffold constructor stamps `Tags.Add(FName("<Tag>"))`; the fixture resolves via `GetAllActorsWithTag`. The agent may rename/subclass the scaffold.
2. **Scaffold ships NO behavior** (no BeginPlay/Tick) — behavior is the agent's job — and its header carries a `// … for task <id>` marker (the fairness layer hides foreign-task scaffolds per run by it).
3. **PIE-native: the engine drives the lifecycle.** Fixtures derive from `ACraftBenchFunctionalTest` (`Source/CraftBenchTests/CraftBenchFunctionalTest.{h,cpp}`), never raw `AFunctionalTest`. BeginPlay auto-fires before `PrepareTest`; **never** call `World->Tick`/`Actor->Tick`/`DispatchBeginPlay` (re-entrant tick → `TickTaskManager.cpp:1097` crash).
4. **Observe at a checkpoint schedule.** `SetCheckpointSchedule({t0,…})` in `PrepareTest`; sample in `OnCheckpoint(idx, t)`. The base owns fixed-timestep determinism and the clock — don't re-implement either. Synchronous tasks may instead do everything in `StartTest()` + one `FinishTest()`.
5. **FAIL via the NAMED assertion.** Every failure path: `FinishTest(Failed, FString::Printf(TEXT("At t=%.2fs (checkpoint %d): expected …; found …")))`. This message is what discrimination greps for.
6. **Map authoring drops `-nullrhi`** (test runs keep it); build maps from `Template_Default`, commit the binary (+ the scaffolder when the map is trivially scriptable — optional otherwise), and add the map's row to `docs/MAPS.md`.

## 8. Reference solution + discrimination package

- **Reference** (`tasks/<set>/<id>/reference/`) — the minimal correct solution, the PASS oracle. It mirrors **only agent-writable prefixes** (`Source/CraftBenchTemplate/…`, `Content/Tasks/…`); a stray root-level file (`README`, `.gitkeep`) lands outside the writable set → SANDBOX-REJECT exit 4. Keep notes at the package root, never inside a submission dir (layout contract: `tasks/README.md`).
- **Variants** (`tasks/<set>/<id>/discrimination/<variant>/`) — one negative submission per anti-gaming note, plus the empty stub (not materialized — any empty dir; overlaying nothing leaves the inert scaffold).
- **`tasks/<set>/<id>/discrimination/MATRIX.md`** — the FR-017 oracle. One row per submission (the reference row's first cell is the folder-relative `../reference`):

  | Submission | Overall | Fails at | Message (expected/found) | Anti-gaming note |
  |---|---|---|---|---|
  | `../reference` | **PASS** | — | all checkpoints green | — |
  | empty stub | **FAIL** | checkpoint 1 (t=1.5s) | expected 1, found 0 | — (FAIL-on-empty) |
  | `burst-spawn/` | **FAIL** | checkpoint 0 (t=0.5s) | expected 0, found 2 | #1 |

The standard: a variant must FAIL **at the listed checkpoint with the listed message substring** — not merely fail. A wrong-reason FAIL (compile error, wrong checkpoint, exit 3/4, SKIPPED/no-tests-discovered) counts as **NOT discriminated**; it's the pass-everything/fail-everything trap (`tools/run-agent/aura_rig/discriminate.py`, `grade_leg`). The message cell is machine-read — the runner extracts the `expected N` / `found M` anchors and requires them in the L2 log, so keep the cell's wording aligned with the fixture's actual `FinishTest` text.

## 9. Test it — command cookbook

All from the repo root, on Windows, UE 5.8 installed. Prefer the `cb` launcher form.

**Direct grade of one submission** (token-free, no agent):

```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/<set>/<id>/task.md \
    --submission tasks/<set>/<id>/reference \
    --ue-root "C:/Program Files/Epic Games/UE_5.8" \
    --workdir C:\cb58\wd01
```

- `--workdir` must be **short** (Windows MAX_PATH; e.g. `C:\cb58\wd01`) and must **not pre-exist**.
- Add `--substrate-from-live` while your fixture/map/manifest are uncommitted (grades the live tree instead of git HEAD).
- Read `report.json` and `l2_pie.log` in the workdir to confirm the failure message matches your MATRIX row.

**Whole matrix, one command** (the normal loop):

```sh
cb discriminate --task <id>          # or a set: --task bp-g2 ; or set-qualified: --task bp-g2/<id>
cb wip --task <id> --wip             # alias; --wip forces --substrate-from-live (mid-edit)
cb discriminate --task <id> --warm-cache   # incremental L1 (~6x); prime first:
cb warm-prime --warm-slots 2
```

Runs reference → PASS, empty → FAIL, every variant → FAIL via its MATRIX substring, and prints a per-leg table. Token-free, no stack bring-up.

**Certify the committed reference — the post-commit close:**

```sh
cb discriminate --task <set>/<id>   # token-free; reference PASS + empty/variant FAIL
cb discriminate --task <set>        # the whole basket at once
```

Run it **after** the section-11 commit: `cb discriminate` grades from git HEAD, so
pre-commit the fixture and map are not in the graded tree and the gate FAILs for the
wrong reason (that iteration is `--wip`'s job).

**Batch grade a folder of submissions** (e.g. agent outputs):

```sh
cb batch-eval <outputs_dir>   # --verify-concurrency defaults to 1 (safe on <=32 GB); add 2+ only on a >32 GB host
```

**Full agent run** (spends tokens; requires everything committed):

```sh
cb eval --task <id>
```

**Exit codes** (`run_task.py`; mirrored in `discriminate.py`):

| Code | Meaning |
|---|---|
| 0 | PASS |
| 1 | FAIL (a layer's assertion failed) |
| 2 | usage error (bad flags/paths) |
| 3 | retired/reserved (the historical hash-gate REJECT — never emitted since 2026-07-16) |
| 4 | SANDBOX-REJECT — submission has files outside the writable prefixes |

**Env knobs:** `CB_UE_ROOT` (UE install root), `CRAFTBENCH_WD_ROOT` (short workdir root), `CRAFTBENCH_L1_MAX_PARALLEL=4` on 32 GB hosts, UBA off by default (`CRAFTBENCH_ALLOW_UBA=1` to re-enable).

**Id resolution:** a bare `<id>` works when unique across sets (true for all 13 current tasks); set-qualified `<set>/<id>` always works and is REQUIRED if an id ever exists in two sets. Reference/discrimination trees are folder-local (`tasks/<set>/<id>/reference/`, `…/discrimination/`), so there is no separate test-tree lookup. Check what an id resolves to with `python -m aura_rig.tasks resolve <id>` (from `tools/run-agent`).

## 10. Automation boundary — where the judgment actually is

The bottleneck is judgment, not C++. This gradient was measured while a code-gen skill was doing the mechanical half; it still describes which fixture shapes are rote and which need a person, whoever or whatever writes them.

**HIGH — the skill finishes end-to-end, no human needed:** count-actors-with-tag-at-checkpoint, exactly-one-tagged precondition, GLog substring/line-count, property-within-tolerance at sampled times, timer-framerate-legs. (~50–60 LOC fixtures; gp-spawner-population is the template.)

**MEDIUM/LOW — the skill generates the skeleton + draft matrix, then STOPS for your sign-off:** trajectory-shape fits, GAS arc/ability-grant checks, AnimBP/graph reachability, UFUNCTION matrices, save-roundtrip identity isolation. The structure is templatable, but the **load-bearing anti-gaming pin needs adversarial design plus empirical tolerance calibration** against a real run (e.g. the retired gp-gas-launch's untriggered control-leg discriminator — git history; gp-poison-dot-stack-cpp's `«calibrate»` bands). When the skill says "confirm the pin," that's your job as author: check the tolerance against the reference run's actual numbers and against the nearest-miss gaming variant. Never wave a judgment-family verifier through uncalibrated.

## 11. Commit protocol + hazards

- **Commit atomically:** the task spec, scaffold pair, L2 fixture (`Source/CraftBenchTests/…`), the binary `.umap`, reference, and discrimination package go in the **same commit**, then a PR to `main` — `Source/CraftBenchTests/**` changes are review-gated on commit.

  `cb eval` grades from **git HEAD**, so until this commit lands the graded tree simply lacks your fixture/map and the run FAILs for the wrong reason (filter-miss / 0-tests) — validate WIP with `--substrate-from-live` / `cb discriminate --wip` instead. (The hash manifest + `--regen-verifier-hashes` flow retired 2026-07-16; there is nothing to regenerate.)
- **Close with the reference gate:** once the commit lands, **`cb discriminate --task <set>/<id>` must grade the committed reference PASS and its empty leg FAIL** — the task is not done until this is green. Iterate the reference/fixture until it passes. This authoring-time gate is where reference gating lives now (moved out of run-time entirely): benches no longer auto-gate (`cb bench --refgates` is an explicit opt-in), fresh-machine onboarding is `cb smoke`, and per-run protection is envgate's job.
- **Mid-authoring note:** the runner clones committed files from git HEAD into its workdir and never touches your live tree — uncommitted fixtures are not deleted by a concurrent grade; they simply never enter the graded tree.
- **Never** `git checkout` / `clean` / `reset` / `stash` near `UE-projects/CraftBenchTemplate/` — the substrate carries load-bearing untracked state.
- Commit only when you actually mean to (the repo conventions), and note in the task spec anything you bounded (a skipped variant, an uncalibrated tolerance): silent truncation reads as "verified" when it isn't.

## 12. Submitting ideas in bulk

Tasks are pure file-drop: anything at `tasks/<set>/<id>/task.md` with the normative headings is auto-discovered by `cb tasks` / `cb discriminate`. For bulk intake, submit a CSV with one row per idea:

| Column | Content |
|---|---|
| `id` | proposed kebab-case task id (behavior-named) |
| `behavior_description` | one sentence: trigger + observable + tolerance ("After X, Y is true within Z") |
| `capability_bucket_guess` | one of the six buckets (`AUTHORING_TEMPLATE.md` § "Capability-bucket reminder") |
| `tier_guess` | T0–T3 by honest senior-dev hours |
| `concept_hint` | candidate `concept_id`(s) from `tools/coverage/concepts.csv` |
| `source_citation` | public URL for any production-pattern claim (Hard Rules #1/#4) |

Pipeline per row: write the spec (row → `tasks/<set>/<id>/task.md`), then build the verifier (spec → 8 artifacts) → post-commit, `cb discriminate --task <set>` again on the committed tree (the close; token-free, so re-running the sweep after a bulk drop is cheap). Rows whose `behavior_description` lacks any of the three slots bounce back with clarifying questions — fill them before submitting.

(A `cb batch-gen` command used to accept such a CSV directly for *generation-only* runs against a scratch project — never gradable task intake — but it drove the commercial product's own UI and is not part of this release.)

---

**Pointers:** the law — `docs/AUTHORING_TEMPLATE.md` · primitives — `docs/pie-verification-playbook.md` · base fixture — `UE-projects/CraftBenchTemplate/Source/CraftBenchTests/CraftBenchFunctionalTest.{h,cpp}` · run guide — `EVALS.md` · layout contract — `tasks/README.md` · exemplar discrimination package — `tasks/cpp/gp-poison-dot-stack-cpp/discrimination/MATRIX.md`.

---

## Part 2 — Spec style: what the agent may and must never see

*The rules that keep a spec from leaking its own answer.*


_Distilled 2026-07-12 from established coding/agent benchmarks, adapted to
CraftBench's structure (allow-listed `task.md` sections + the on-disk scaffold
excerpt that the harness renders into the prompt). The audit this was
distilled from, and the apply-ready edit list that came with it, were
internal working files and are not part of this release — the rules below
are what survived them._

### The core principle

An agent must be able to produce a correct solution from **the prompt alone**,
and everything the hidden verifier enforces must be **derivable from the
prompt**. Two symmetric failure modes break this — and established benchmarks
screen for both:

- **Under-specification** — the prompt is too vague, so a competent agent can't
  know what "done" means. In the SWE-bench Verified annotation campaign, **38.3%
  of samples had under-specified problem statements**; these were downgraded or
  discarded. ([OpenAI](https://openai.com/index/introducing-swe-bench-verified/))
- **Oracle leakage / over-strict hidden checks** — the grader enforces something
  the prompt never states (or, inversely, the scaffold leaks how the grader
  works). SWE-bench Verified found **61.1% of samples had unit tests that could
  unfairly reject valid solutions**; the fix was to make the test's expectations
  match the stated issue. ([OpenAI](https://openai.com/index/introducing-swe-bench-verified/))

Both established standards keep the grader **out of the agent's view**:

- **METR Task Standard** separates the agent-visible instruction string from the
  scoring function, and ships a companion `task-protected-scoring` so scoring
  logic can't be read or manipulated by the agent.
  ([METR](https://github.com/METR/task-standard), [task-protected-scoring](https://github.com/METR/task-protected-scoring))
- **Terminal-Bench / Harbor**: `instruction.md` "should precisely specify the
  task goal or output expected... **Importantly, do not expose test details or
  verification logic — instead describe how 'done' looks conceptually**." The
  oracle `solution.sh` and `tests/` are kept separate from what the agent sees.
  ([Harbor task-authoring](https://deepwiki.com/harbor-framework/harbor/2.4-creating-tasks))

CraftBench already hides the `CraftBenchTests` module — but it re-leaks the
grader through **comments in the agent-writable scaffold files**, which the
harness renders verbatim into the prompt. That is the gap this scrub closes.

### What the agent MAY see

1. **The task prompt** (`## Prompt given to the agent`) — the single source of
   truth for the acceptance criteria. State the **observable contract
   precisely**: exact output strings, counts, timings, tolerances, the tag names
   the agent must stamp on actors it creates, and the log category/verbosity if
   the grader cares. Stating an observable output is **good spec practice, not a
   leak** (Terminal-Bench) — it is *not* the same as naming the C++ pattern to
   use (still forbidden by Authoring Hard Rule #2).
2. **Workspace facts** (`## Workspace state pre-task`) — which files exist, what
   each pre-existing class already does, what is intentionally absent. Reference
   the test harness only in neutral terms ("a test harness actor is placed in
   the level"), never by fixture class name.
3. **Public API the agent implements against** — method signatures on a scaffold
   class, a native tag accessor (`AbilityLaunch()` → `"Ability.Launch"`), an
   `EditAnywhere` array to populate, a component the agent binds. This is the
   interface, exactly like a header in any real codebase. Expose the *symbol*;
   never annotate it with how the grader uses it.

### What the agent must NEVER see

- The word **verifier / fixture / probe / L2 / automation test**, or any
  description of the grading harness.
- **How actors are resolved** ("by tag, never by class"), that a header is
  "looked up by exact path", that a tag is "what the verifier activates", or that
  a location is "where the verifier spawns a probe."
- **Grading details absent from the prompt**: verbosity floors, numeric
  tolerances, exact counts/timeouts the prompt doesn't state, or "the FIXED
  contract the fixture calls."

If the grader enforces something important (e.g. the log category + verbosity),
the fix is not to hide it in a scaffold comment — it is to **put it in the
prompt** (if it's a meaningful part of the contract) or **relax the check** (if
it's an arbitrary detail that would reject valid solutions, per the SWE-bench
over-strict-test lesson). Decide per task; never smuggle it into a comment.

### Scaffold-comment template

```cpp
// Copyright CraftBench. All Rights Reserved.
//
// A<Name> — pre-existing <class role> for task <task-id>. The constructor
// <what it already wires: tick, components, the identity tag it stamps>.
// The required behavior is NOT implemented here; it is specified in the task
// prompt and is the agent's to author. Agents may subclass or rename freely.
```

Describe only what the code in *this* file already does. No verifier references,
no acceptance-criteria literals, no "so that the grader can…".

### Author checklist (pre-commit, per task)

1. **Grep the scaffold for the grader.** `verifier|fixture|probe|L2|by tag|never
   by class|exact path` must return nothing in agent-writable files.
2. **No hidden acceptance criteria.** Every literal the fixture asserts (strings,
   counts, timings, tolerances, tag names, log category/verbosity) is either
   stated in the prompt or not enforced. Read the fixture; diff it against the
   prompt.
3. **Under-specification pass.** Could a competent engineer, given only the
   prompt, produce a solution that passes? If a reasonable choice would fail,
   the prompt is under-specified — tighten the prompt or loosen the check.
4. **Interface, not answer.** Scaffold comments name symbols (signatures, tags,
   arrays) but never the algorithm or the C++/design pattern to use.
5. **Prompt provenance.** Any wording change shifts the rendered prompt →
   `preamble_sha` / content hash moves; note the re-baseline so pre/post cost and
   pass-rate numbers aren't compared across the boundary.

### Sources

- [Introducing SWE-bench Verified — OpenAI](https://openai.com/index/introducing-swe-bench-verified/)
- [METR Task Standard](https://github.com/METR/task-standard) · [task-protected-scoring](https://github.com/METR/task-protected-scoring)
- [Terminal-Bench / Harbor — Creating Tasks](https://deepwiki.com/harbor-framework/harbor/2.4-creating-tasks) · [terminal-bench](https://github.com/laude-institute/terminal-bench)
- [Separating signal from noise in coding evaluations — OpenAI](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)


---

## Part 3 — The implementor checklist: spec to graded task

*The step-by-step build, in the order that works.*


**This is the single end-to-end TODO sheet for shipping a new CraftBench
task.** Copy the checkbox list into your task's `notes.md` (or the PR body)
and tick as you go. Every step names the file it produces and the gate that
proves it. Deep-dives live elsewhere — this sheet is the spine:

| topic | doc |
|---|---|
| Spec format law (front matter + body sections) | `docs/AUTHORING_TEMPLATE.md` |
| Narrative how-to + design judgment | `docs/TASK-AUTHOR-GUIDE.md` |
| Fixture/verification recipes (what's proven) | `docs/pie-verification-playbook.md` |
| Folder layout contract | `tasks/README.md` |
| Map inventory + conventions | `docs/MAPS.md` |
| Acceptance gate (definition of done) | `docs/TASK-AUTHOR-GUIDE.md` |
| Spec-writing style (under-specification vs. oracle leakage) | `docs/TASK-AUTHOR-GUIDE.md` |
| Skills that automate the two halves | `/craftbench-author-task`, `/craftbench-build-verifier` |

**Where new tasks land:** `tasks/<basket>/<task-id>/` — `bp` for Blueprint/asset/editor deliverables, `cpp` for C++ source deliverables (project decision 2026-08-11; team-authored
set; discovery is pure file-drop). The templates to copy are the flagship t0
pair: `t0-sanity-log-on-beginplay` (C++ deliverable) and
`t0-sanity-bp-log-on-beginplay` (Blueprint/asset deliverable — this one also
ships a compliant `discrimination/` package to mirror).

Substrates (pick via the spec's `substrate:` key): **`ThirdPerson`** (the
stock UE 5.8 Third Person C++ template — **the default for new GAMEPLAY
tasks**, project decision 2026-08-05: it ships Manny/Quinn and the stock
animation set natively, so playable-character tasks need no asset drops and a
graded run is human-reviewable out of the box; `gp-glide-stamina-bp` was
migrated onto it the same day, retiring the CraftBenchTemplate "mannequin
pool" workaround) and `CraftBenchTemplate` (the parser's default; minimal
per-task scaffold actors — still right for pure-logic/actor tasks with no
playable character).

---

### The checklist

#### 1. Spec — `tasks/<basket>/<id>/task.md`

- [ ] Open design axes resolved BEFORE writing — observable contract, surface
      (C++ / BP / agnostic; `-cpp`/`-bp` suffix pairs), substrate
      (`ThirdPerson` default for gameplay), tier + 50/20/30 band, layers,
      visual application (the 2026-08-06 visible-character gate), camera
      intent, anti-gaming surface. `/craftbench-author-task` asks
      concrete-choice questions (AskUserQuestion) for whatever the source
      idea leaves open — it never guesses (`docs/TASK-AUTHOR-GUIDE.md` §5).
- [ ] Folder + `task.md` created; the front-matter `id:` **equals the folder
      name** (`cb lint` errors otherwise).
- [ ] Opens with the **v2 front-matter block** (not the legacy H2 metadata):

      ```
      ---
      id: <task-id>
      substrate: CraftBenchTemplate
      set: bp   # or cpp — match the basket the task lives in
      tier: T1
      capability_bucket: Gameplay Programming
      category: gameplay
      layers: [L1, L2]
      fixtures: ["L_<Map> :: A<Name>FunctionalTest"]
      ---
      ```

      Full grammar: `docs/AUTHORING_TEMPLATE.md` (normative) and the
      `tools/verify-single/spec.py` module docstring (THE parser).
- [ ] `## Prompt given to the agent` written — **behavior-only** (no class,
      plugin, or pattern names; Hard Rule #2), and fully specified: verbosity,
      counts, timing windows the fixture will assert are *disclosed* (the t0
      Log-vs-Display under-spec cost two models before it was fixed).
      Only this section + `## Workspace state pre-task` reach the agent.
- [ ] `## Anti-gaming notes` — **3–5 entries**, each pairing a gaming failure
      mode with the verifier defense (lint-enforced).
- [ ] `## Verifier specification` (hidden human docs) describes every
      assertion with its NAMED failure message.

#### 2. Scaffold pair — `UE-projects/<substrate>/Source/<Module>/Tasks/<id>/`

- [ ] `<Name>Actor.{h,cpp}`: constructor stamps the identity tag
      (`Tags.Add(FName("<Tag>"))`), **no behavior** (no BeginPlay/Tick body).
- [ ] Header comment carries the literal `for task <id>` marker (the fairness
      layer hides foreign scaffolds by it) and comments are behavior-only —
      **scaffold comments are rendered into the agent's prompt** (Hard Rule
      #6; the 2026-07-12 leak audit found 8/8 tasks narrating the verifier).
- [ ] No `Build.cs` edit — `PrivateIncludePaths.Add(ModuleDirectory)` already
      resolves `Tasks/<id>/` sources.

#### 3. Fixture pair — `Source/CraftBenchTests/Tasks/<id>/`

- [ ] `<Name>FunctionalTest.{h,cpp}` derives **`ACraftBenchFunctionalTest`**
      (it owns the PIE lever, fixed-timestep determinism, and the checkpoint
      clock — never reimplement those in a subclass).
- [ ] `PrepareTest` resolves the host via `GetAllActorsWithTag` (**never by
      class** — agents may subclass), then `SetCheckpointSchedule({...})`.
- [ ] `OnCheckpoint(idx, t)` samples state; every failure goes through a
      **NAMED** `FinishTest(Failed, "At t=... expected ...; observed ...")` —
      the discrimination matrix greps for these substrings.
- [ ] **Assertion messages are ASCII-only.** The UE log's UTF-8 bytes get
      read back as cp1252, so an em dash becomes `â€”` and the MATRIX
      substring grep misses — a CORRECT fail then classifies as
      wrong-reason (found live on t2-homing-projectile, 2026-07-21).
- [ ] **Pre-mortem the SAMPLER, not just the assertions**: can the thing
      you measure be satisfied discontinuously (teleport between samples,
      destroy-and-respawn at the goal)? If yes, police per-frame motion
      and/or pin actor identity (see `HomingProjectileFunctionalTest`).
- [ ] **Prefer relative gates** (ratios of the measured pre-state) over
      absolute magnitudes — editor placement offsets make absolutes lie
      (t2's nominal 2000-unit separation measured 2328 on disk).
- [ ] **Trajectory/timing-family tolerances get CALIBRATED**: run the
      reference leg once, read your fixture's diagnostic log lines, verify
      every margin, and record the numbers in the task's `notes.md` BEFORE
      finalizing `MATRIX.md` (the automatability gradient's judgment step).
- [ ] **Never** call `World->Tick` / `Actor->Tick` / manual `BeginPlay` (PIE
      is engine-ticked; re-entrant ticking trips the TickTaskManager assert).
      To observe the BeginPlay window itself, install the listener via
      `FWorldDelegates::OnWorldInitializedActors` (see `SanityFunctionalTest`).

#### 4. Map — `Content/Maps/<id>/L_<Map>.umap` (committed binary)

- [ ] Map authored **in the editor or via aura-mcp** and committed as a binary
      `.umap` — the committed binary is the ONLY map source (scaffolders were
      retired 2026-07; a missing binary is an explicit L2 FAIL and a
      `cb lint` error).
- [ ] Tagged scaffold actor + fixture actor placed; host placed **off the
      world origin** if any radius/position check gates.
- [ ] The automation name derives from the folder:
      `Project.Functional Tests.Maps.<id>.<Map>.<Class>` (the `A` prefix is
      stripped). The front-matter `fixtures:` entry uses the raw class name.
- [ ] Inventory row added to `docs/MAPS.md` (placed actors, automation name,
      authoring provenance).
- [ ] **Use the substrate's own materials, not bare engine shapes.** Owner feedback
      2026-08-18 on the first four public tasks: *"they seem primitive."* They were --
      every floor, prop and marker was an `/Engine/BasicShapes` mesh with the default
      grey material, which is a grey-box look. ThirdPerson already ships everything
      needed, so this costs a `set_material` call per actor and nothing else:
      | want | asset |
      |---|---|
      | floor / stripes | `/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray` (and `_Gray_02`, `_Gray_Round`) |
      | dark / inactive marker | `/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark` |
      | bright / active marker | `/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT` |
      | hazard | `/Game/Variant_Combat/Materials/M_Lava` |
      | flat colour base | `/Game/LevelPrototyping/Materials/M_FlatCol` |
      All are committed substrate content, so there is no new asset dependency and no
      licensing question. Two visibly different SUPPLIED materials is also what a task
      needs when a marker has to "look visibly different" -- author it from this list
      rather than creating material instances.
- [ ] **If the map names its own game mode, the play lane is re-stated.**
      Naming any game mode replaces `GlobalDefaultGameMode`
      (`BP_ThirdPersonGameMode`), and BOTH halves of Enhanced Input live on the
      Blueprints it would have supplied: `IMC_Default` is on
      `BP_ThirdPersonPlayerController`, and the four `IA_*` actions are on
      `BP_ThirdPersonCharacter`'s CLASS DEFAULTS — `AThirdPersonCharacter`
      declares them and assigns none, so a native pawn subclass inherits four
      nulls and binds nothing. So set `PlayerControllerClass` in the game mode
      ctor and load the four actions in the pawn ctor. **No fixture catches
      this**: every one drives its pawn through `AddMovementInput`, so a level
      with a dead keyboard grades byte-identically — it builds, passes,
      discriminates and certifies while being impossible to walk around. Assert
      it as a `HARNESS-PRECONDITION` read by property NAME (see
      `APlateDoorFunctionalTest::DescribeBrokenPlayerInput`) and prove the guard
      in BOTH directions. Four shipped maps were measured broken this way
      2026-08-17: the 2026-08-17 unplayable-play-lane finding.
- [ ] `Default*Map` in `Config/DefaultEngine.ini` must NEVER point at a task
      map (live-editor map locks break eval isolation) — leave whatever neutral
      ENGINE map the substrate already commits, and do NOT "restore" it to a
      value you remember. The two substrates differ:
      `CraftBenchTemplate` is on
      `/Engine/Maps/Templates/Template_Default.Template_Default`,
      `ThirdPerson` is on `/Engine/Maps/Entry.Entry`. Retyping one as the other
      is a spurious substrate diff on your task PR. The `startup-maps` envgate
      probe enforces the invariant (never INTO `Content/Maps`), not a literal.

#### 5. Camera plan — `tasks/<basket>/<id>/cameras.json`


      (`[--call-claude]` to also emit `draft_cameras.json`). Run it AFTER the
      scaffold/map commit — the scene-facts dump materializes from git HEAD.
      The LLM proposes offline; a HUMAN reviews and commits (the proposer
      never writes `cameras.json` itself).
- [ ] LAW: presentation-only — never gates PASS/FAIL; the generator's input
      is the clean substrate + committed map + scaffold + public prompt ONLY
      (never `reference/`, never fixture internals; the checkpoint schedule's
      count/times are the one allowed fixture fact).
- [ ] Shot heuristics (both bit live): a fast mover needs a wide `pose` over
      the action envelope (`frame_subject` close-ups motion-blur); meshless
      subjects (bare-`AActor` scaffolds, capsule-only pawns) frame correctly
      but render NOTHING.

#### 6. Reference solution — `tasks/<basket>/<id>/reference/`

- [ ] Mirrors the agent-writable prefix **including** the `Tasks/<id>/`
      segment (e.g. `reference/Source/CraftBenchTemplate/Tasks/<id>/...`) —
      the overlay lands at the literal path.
- [ ] Nothing outside `AGENT_WRITABLE.json`'s writable set (sandbox reject =
      exit 4; `cb lint` sandbox-scans the reference).

#### 7. Discrimination package — `tasks/<basket>/<id>/discrimination/`

> **OWNER 2026-08-18: REFERENCE + EMPTY ONLY. Do not author variant legs.**
> The package is `MATRIX.md` with two rows — the reference (PASS) and `empty`
> (FAIL at its named gate). Nothing else, unless a maintainer asks for a specific
> leg.
>
> Why: variant legs cost more authoring time than the fixture they test. On
> `t1-shoved-block-slides-on-one-rail` the four legs took longer than everything
> else in the task combined, and one of them (`velocity-clamp`) needed three
> rewrites — two of which were spent fighting solver frame ordering, not improving
> the task. Meanwhile the per-checkpoint gates already carry the discrimination:
> a task with four to seven named checkpoint gates fails an empty submission at
> the first real one, and each gate is independently named and greppable.
>
> **What this gives up, stated honestly so nobody rediscovers it as a surprise.**
> Of the four "reads green while grading nothing" defects found on 2026-08-17,
> `empty` caught one (a reference committed into the substrate) and VARIANTS
> caught two (`one-shot-rail PASS(unexpected-pass)` exposed cp3 never running at
> all; `spoofed-motion PASS` exposed a peak-speed gate satisfiable by the push's
> own residual). Both of those holes are now closed STRUCTURALLY instead — the
> sentinel checkpoint (pitfall 8) and the motion-explained-by-velocity gate — so
> the specific classes do not need a variant to be caught again. But a variant
> passing remains the loudest signal there is, so if a task's central claim rests
> on ONE gate, say so in `notes.md` and ask a maintainer whether that one leg is
> worth building.

> **AMENDED 2026-08-11 (project decision). The old rule was "one `<variant>/`
> overlay per anti-gaming note", which with the mandatory 3-5 notes meant 3-5
> hand-authored wrong solutions per task. That is no longer required.** Existing
> variants are KEPT (they are paid for and have regression value); the
> requirement on NEW tasks changes. Rationale and evidence in §7a.

- [ ] **Floor — costs nothing, already automatic:** `cb discriminate` always
      runs reference→PASS and **empty→FAIL**. The stub-guard must be
      FAIL-on-empty, not differs-from-reference (the gp-gas-launch gold-leak
      lesson). This is the whole non-vacuity requirement. `discriminate.py`
      already treats a missing `discrimination/` dir as non-fatal.
- [ ] **Soundness — the REQUIREMENTS table in `MATRIX.md`** (replaces the
      per-note variant table as the mandatory artifact). One row per
      requirement in the agent-visible prompt:
      `requirement | asserted fully/partially/NOT AT ALL | file:line of the
      assertion | condition under which that gate is SKIPPED (or
      "unconditional") | what a submission could get away with`.
      A requirement with no assertion is either **gated or removed from the
      prompt** — never left as unenforced prose.
- [ ] **Targeted variants — only for a hole this table actually found.** One
      per hole, named for it. Not one per imagined cheat.

> **SECOND AMENDMENT 2026-08-11 (owner vote, same day): "as minimal as
> possible."** The three `-bp` twins validated today each ran SEVEN legs; the
> owner's verdict is that is too many, and the leg-by-leg record backs it. The
> shipping bar for NEW tasks is now exactly:
>
> 1. **reference → PASS** and **empty → FAIL** (automatic, costs nothing);
> 2. **`cpp-solve` → FAIL, on `-bp` deliverable-format twins ONLY** — the one
>    axis with a MEASURED false PASS (glide 2026-08-03: a C++ solve passed a
>    Blueprint task with every gate green). On a `-bp` twin this leg IS the
>    task's reason to exist; skip it and a model that ignores the word
>    "Blueprint" scores PASS.
> 3. **At most one attacker per hand-calibrated bar, and only when the
>    requirements table shows that bar otherwise unprobed.** Evidence for
>    keeping this class and only this class: all seven gate defects found
>    across the 2026-08-10/11 slate lived in gates with hand-pinned constants
>    (cost tolerances, stop windows, rate floors) — `never-stops-in-band`
>    caught StopEpsilon, `teleport` caught the missing ballistic bound,
>    `permanent-drain` caught the poison stop gate. Zero defects were found by
>    any other leg class.
>
> Explicitly NOT to be authored anymore: **family-standard re-proofs** (the
> `bp-no-mesh` class — the visibility gate is proven at family level by 9/9
> real glide reps shipping meshless pawns; today's three `bp-no-mesh` legs all
> confirmed predictions and found nothing) and **duplicate cheat legs for a
> mechanism already measured on a sibling family** (`cpp-solve-with-bp`
> re-proved glide's measured record three more times). Existing committed
> variants are KEPT as regression legs — paid for, and re-verifiable for free
> on a matrix re-run — but they are not the template. Under this bar a typical
> family ships 3-4 legs, not 7.
- [ ] `MATRIX.md` keeps its per-submission rows for whatever variants exist:
      expected verdict + the NAMED assertion substring that must appear in the
      L2 log (a wrong-reason FAIL — compile error, sandbox reject, SKIPPED —
      does **not** count).

#### 7a. Why the variant-per-note rule was dropped

**Two defects were found in the gold exemplar on 2026-08-11, and the variants
did not find either** (`gp-glide-stamina`, which ships **seven** of them):

1. Gate (5) — stop-on-exhaustion, the task's whole point — sat behind
   `if (LastSpeed < ResumeVZ)` with `ResumeVZ = 350`, an ABSOLUTE speed. All 13
   recorded runs ended at 1361-1836 cm/s, so the gate had **never executed**.
2. A glide sample was `FMath::Abs(vZ)` with no sign test, so *ascending* counted
   as "descending slower" and a *hover* scored 0 — passing the slow-descent gate
   trivially and zeroing gate (5)'s bar.

**The instructive part is that a variant for defect 1 EXISTED.**
`discrimination/slow-no-stop/` clamps descent and never releases — precisely the
cheat — and its author reasoned it through in a comment: *"reads the SAME
clamped speed as the glide samples — a 1.00x resume ratio against gate (5)'s
1.5x bar."* It clamps at `GlideFallSpeed = 100.0f`, so:

```
clamp 100 → LastSpeed 100 < 350 → ratio path → 1.00x < 1.5x → FAIL (correct)
clamp 400 → LastSpeed 400 >= 350 → FAST PATH → asserts nothing → PASS (hole)
```

Same cheat, same 1.00x ratio, opposite verdict — decided entirely by the
magnitude the author happened to pick. **A variant tests a POINT; the defect was
at a BOUNDARY.** No finite set of hand-authored variants reliably finds those,
and both defects fell out of *reading the gate* in an afternoon.

**The circularity is the deeper reason** (owner, 2026-08-11): the same author —
increasingly an LLM — writes the prompt, the fixture, and the variants, then we
use the variants to check whether LLM-generated solutions get caught. The
variants inherit the fixture's blind spots by construction. `slow-no-stop` is
that in one file: careful reasoning, right concept, and it still probed at
100 cm/s and never imagined 400.

What variants uniquely buy is proof that a gate **fails something at all** — a
vacuous gate passes everything and is indistinguishable from a good one in the
reports. That is one bit per task, and the automatic empty leg already provides
it. Seven variants do not buy seven bits.

Cost, for the record: 48 committed variants across bp-g2 today, each needing a
graded run to stay honest, scaling as *tasks x cheats*. The requirements table
scales as *tasks*, and catches the class variants structurally cannot — a
requirement nothing asserts, which no variant can probe because there is no
gate there to probe.

**FR-017 is unchanged.** A gate must still discriminate the concept rather than
a sanitized proxy. Only the instrument changed: read the gate against the
prompt, instead of guessing N ways to cheat it.

**The gold-set lint rule is unchanged and compatible — no code change.**
`tasklint`'s `discrimination-coverage` rule applies only to the four tasks named
in `tools/verify-single/gold_set.txt` (the glide + poison pairs), and it was
already written to accept two routes per note: **(a)** a committed variant dir,
or **(b)** an inherited/argued justification carrying a pointer to where the
defense IS proven. **A row in this section's requirements table is a valid
route-(b) pointer** — it names the assertion, its file:line, and the condition
under which it is skipped, which is strictly more than "argued". That file also
already rejects `len(variants) == len(notes)` as a bar, for reasons that
anticipate this amendment: it "outlaws the documented `-bp` inheritance law" and
"the cheapest way to go green under it is to DELETE an honest anti-gaming note".

So: keep writing 3-5 honest anti-gaming notes. Cover each one by pointing at
the assertion that defends it. Author a variant when — and only when — you find
a note whose defense turns out not to exist.

**The lint already told us, and nobody acted on it.** Running `tasklint` over
the four gold-set specs today reports 16 of 23 anti-gaming notes with no
resolvable defense pointer. Among them, on `gp-glide-stamina-bp`, is note 5:

> *"Glide forever / permanent fall-speed change (not resource-gated)"*

That note names the exact cheat, the lint flagged its defense as unproven, and
the defense — gate (5) — was in fact never executing. **The warning was correct
for the correct reason and went unread for days.** This is the strongest single
argument for the requirements table: it converts that WARN from a chore into the
artifact that answers it, and answering it is what finds the defect.

**It is NOT an argument for promoting `discrimination-coverage` to ERROR**
(considered and rejected, owner, 2026-08-11). `gold_set.txt` already refuses
count-equality on the grounds that "the cheapest way to go green under it is to
DELETE an honest anti-gaming note", and that reasoning applies unchanged to a
hard failure: with 16 of 23 notes uncovered, red lint would buy deleted notes
and pointers written to satisfy a grep, not sixteen investigations. A rule that
makes the spec less honest is worse than a warning nobody reads.

It also does not need promoting, because **the WARN is self-clearing under this
amendment**: route (b) accepts a resolvable pointer, a requirements-table row is
one, and the table is now the mandatory artifact. Notes get covered as tables
get written, and the warning quiets itself for the right reason instead of
being silenced.

#### 8. Gates — all five, in order

- [ ] **Static lint:** `cb lint --task <basket>/<id>` (wraps
      `tools/verify-single/tasklint.py`) — zero ERRORs.
- [ ] **WIP discrimination:** `cb discriminate --task <basket>/<id>
      --wip` (uncommitted fixtures/maps can't grade from git HEAD; `--wip`
      forces `--substrate-from-live`). Required: **reference PASS, empty FAIL**,
      and every variant that EXISTS failing via its named substring. A task with
      no `discrimination/` dir is legitimate as of the 2026-08-11 amendment (§7)
      — `discriminate.py:338` already treats a missing dir as non-fatal. What is
      NOT optional is §7's requirements table.
- [ ] **Reference gate — use `cb discriminate`, NOT `cb refgate`.** On a CLEAN
      tree, once the task commit exists: `./cb discriminate --task
      <basket>/<id>`. Its reference leg grades the committed reference from git
      HEAD, which is exactly what refgate certified — and it additionally proves
      the EMPTY leg fails for its named reason, which refgate never checked.
      What refgate ADDED was per-machine certificates so later runs self-skip,
      and that is the part that did not pay for itself: the cert key covers the
      task tree, the substrate tree AND the verifier tree, so one substrate
      change voids the whole set — a surface-pair rename invalidated every
      certificate in a single commit, and an uncertifiable gate is a full
      re-grade that caches nothing. Two mechanisms, one guarantee, and the
      surviving one proves strictly more. `cb refgate` is still dispatchable and
      still works; nothing requires it (`docs/CHEATSHEET.md`).
- [ ] **Sibling regression:** every OTHER committed reference must still
      PASS (the substrate is shared — Build.cs deps, tag collisions, and pawn
      ambiguity can break sibling tasks). `./cb batch-eval --references all` is
      that sweep — it is the same discovery `cb refgate --all` used
      (`aura_rig/cb.py::cmd_refgate`), so the two can never disagree about what
      "every reference" means.
- [ ] **Windows note:** direct `run_task.py` probes need a short `--workdir`
      (e.g. `C:\cb\wd`) for MAX_PATH, and `CRAFTBENCH_L1_MAX_PARALLEL=4` on
      32 GB boxes.

#### 9. Commit + PR + the reference close

- [ ] ONE atomic commit: spec + scaffold pair + fixture pair + binary `.umap`
      + reference (+ `cameras.json` + discrimination package +
      `docs/MAPS.md` row).
- [ ] Open a PR to `main`. `Source/CraftBenchTests/**` changes are
      review-gated on commit. There is **no hash-manifest
      step** — the runner grades from git HEAD, so your task only becomes
      gradable (`cb eval --task <basket>/<id>`) after merge; until
      then keep using `--wip`.
- [ ] **OWNER PLAYS IT (2026-08-18).** Before moving to the next task, hand the
      owner a tested command to play the REFERENCE solution, and wait. Not the
      inert scaffold — the solved state, in a workdir that already built it (a
      `cb discriminate --keep` run dir under `runs/discriminate/`
      holds exactly that, in its `reference/wd/` subtree):
      `./cb view --project <workdir>/<Substrate> --map L_<Map>`. Verify the
      project and map exist first; a command handed over untested has already
      failed twice (a relative `cygpath` path, and pointing at the BEFORE state
      when a maintainer asked for the generated one). Say what to press and what to
      look for, and warn that an open editor holds the build lock.
- [ ] **The close — the task is DONE only when it DISCRIMINATES against the
      landed commit:** `./cb discriminate --task <basket>/<id>` on a clean tree
      reports `discriminated: YES` — reference **PASS** and empty **FAIL for its
      named reason**. That is strictly more than the retired refgate proved,
      which only ever graded the reference.
      **Read the machine state before believing a red leg.** Measured
      2026-08-24 on one task: three attempts, and the first two failures were
      the box rather than the submission — a concurrent `cb eval` gave
      `empty FAIL(wrong-reason)`, then `L1 exit 6 / fatal error C1060`
      (compiler out of heap) inside ENGINE headers. It passed on the third run
      with `CRAFTBENCH_L1_MAX_PARALLEL=2`. Never run two graded things at once:
      the build lock covers BUILDS, and concurrent L2/L2I EDITORS are not
      protected. Fresh-machine onboarding is `cb smoke`; per-run protection is
      envgate.

---

### Pitfall shortlist (each has bitten a real task)

1. **Under-specified prompt** — if the fixture asserts it, the prompt must
   disclose it (t0's Log/Display gap claimed two models).
2. **Verifier narration in scaffold comments** — the harness renders scaffold
   excerpts into the prompt; comments are agent-visible surface.
3. **Class-based actor lookup** — penalizes legitimate subclassing; tag-only.
4. **Manual ticking in fixtures** — PIE is engine-ticked; use the checkpoint
   schedule.
5. **Un-named assertions** — discrimination needs a grep-able failure string
   per anti-gaming axis.
6. **Gold in the scaffold** — a filled "stub" makes the empty submission
   pass (the gas-launch b16859f leak); scaffolds carry identity + shape only.
7. **Forgetting the commit-to-grade rule** — an uncommitted fixture doesn't
   REJECT, it just never reaches the graded tree and FAILs for the wrong
   reason. `--wip` is the pre-merge path.
8. **A deferred grade the base finishes out from under you.**
   `ACraftBenchFunctionalTest::Tick` ends with `if (NextCheckpointIndex >=
   Checkpoints.Num()) FinishTest(Succeeded, "All checkpoints sampled.")` — the base
   declares SUCCESS the instant the last scheduled checkpoint is crossed. So a
   fixture that treats the schedule as *earliest* instants and grades later off a
   measured event (a detected impulse, a knock, an arrival) will have its last
   assertions **silently skipped**, and the test passes having graded nothing.
   Measured 2026-08-17 on `t1-shoved-block-slides-on-one-rail`: cp3 — the leg the
   whole task was built around — never ran, in the reference *and* in a variant,
   both reporting `Result={Success}` with no cp3 line in either log. What caught it
   was `cb discriminate` reporting `PASS(unexpected-pass)` on that variant; the
   reference passing looked entirely normal. Fix: schedule a **sentinel** instant
   well past any real grade so the auto-success is unreachable, and FAIL by name
   from it if the state machine has not finished. **If your last assertion is not
   clocked by a scheduled checkpoint, it is not clocked at all.**
9. **A level that grades clean and cannot be played** — a task game mode drops
   both halves of Enhanced Input (step 4), and no gate notices because fixtures
   drive the pawn in code. Five of six ThirdPerson maps were in this state on
   2026-08-17. Every automatic gate can be green while the deliverable is
   unreachable to a human; the black-stills incident was the same shape. Before
   calling a task done, **open the map and walk around it**.


---

## Part 4 — Acceptance checklist

*What must be true before a task ships.*


The **definition of done** for a CraftBench task. A task is *accepted* (counts
toward the benchmark, may merge) only when every gate below holds. This is the
bar for the standard flow:

> team sends a spec → a builder (a human or a CC agent) produces the substrate +
> verifier + reference → the task must clear the acceptance gate before it counts.

**Why the bar exists, in one incident:** `gp-gas-launch` once shipped a "stub"
that was actually the filled solution, so an **empty submission PASSed** — the
task measured nothing for weeks. A verifier that passes the reference proves
nothing on its own; only a verifier that *also fails a wrong answer* has teeth.
That single property — reference PASS **and** empty FAIL — is the heart of this
checklist.

Companion docs: `docs/AUTHORING_TEMPLATE.md` (normative task.md format),
`docs/TASK-AUTHOR-GUIDE.md` (narrative how-to), `docs/TASK-AUTHOR-GUIDE.md`
(spec-writing style + citations). This file is the go/no-go gate, not the how-to.

---

### What gets built (the five artifacts)

For task `<id>` in set `<set>` (foldered convention; `t0-sanity-log-on-beginplay`
is the template):

1. **Spec** — `tasks/<set>/<id>/task.md`. Agent-visible sections are ONLY
   `## Prompt given to the agent` and `## Workspace state pre-task`; every other
   H2 (`## Verifier specification`, `## Anti-gaming notes`, `## Hidden invariants`,
   `## Calibration matrix`, …) is hidden from the agent.
2. **Scaffold** — agent-writable pair under
   `Source/CraftBenchTemplate/Tasks/<id>/` (the class the agent extends).
3. **Fixture** — verifier-only `AFunctionalTest` under
   `Source/CraftBenchTests/Tasks/<id>/`; review-gated (on commit) + graded
   from git HEAD, the agent can never read it.
4. **Map** — `Content/Maps/<id>/L_<Map>.umap` — the committed binary is the
   ONLY map source (author in-editor / via aura-mcp; scaffolders retired
   2026-07; a missing binary is an explicit L2 FAIL).
5. **Reference** — `tasks/<set>/<id>/reference/`, mirroring the agent-writable
   prefix (the known-good). A **gamed/near-miss** negative is recommended.

---

### The acceptance gate

#### A. Spec hygiene — the agent must not see the grader
- [ ] Everything the fixture enforces is derivable from the agent-visible prompt.
- [ ] The prompt states the **observable acceptance criteria precisely** — exact
      strings, counts, timings, tolerances, the tags the agent must stamp, the log
      category/verbosity if the grader checks it. (Stating the observable output
      is good practice; it is *not* naming the pattern.)
- [ ] The prompt names **no** C++/design pattern, plugin, or fixture class
      (Authoring Hard Rule #2).
- [ ] Scaffold comments describe only what the file already does + "the required
      behavior is specified in the task prompt." **Grep is clean:**
      `verifier|fixture|probe|L2|never by class|by tag|exact path|activates to trigger`
      returns nothing under `Source/CraftBenchTemplate/`.
- [ ] `## Workspace state pre-task` refers to the test harness only in neutral
      terms ("a test harness actor is placed in the level"), never by class name.

#### B. Verifier validity — the core gate
- [ ] Fixture derives from `ACraftBenchFunctionalTest`; resolves actors **by tag,
      never by class**; never calls `World->Tick`/`Actor->Tick`; observes state on
      a `SetCheckpointSchedule()` clock (the PIE-native time model — see
      `docs/pie-verification-playbook.md`).
- [ ] **`cb discriminate <set>/<id>` = YES** — reference **PASS** and empty
      **FAIL**. The empty-FAIL leg is the one that proves the verifier discriminates;
      a reference-PASS alone is not acceptance.
- [ ] If a gamed/near-miss negative exists, it **also FAILs** (the fixture isn't
      fooled by the obvious cheat).
- [ ] `## Anti-gaming notes` has **3–5 entries**, each pairing a gaming failure
      mode with the verifier defense that catches it.

#### C. Under-specification pass — the SWE-bench-Verified lesson
- [ ] A competent engineer given **only the prompt** could produce a passing
      solution. Every literal the fixture enforces is either **stated in the
      prompt** or **not enforced**. If a reasonable choice would fail → tighten the
      prompt or relax the check. (Screened ~38% of raw SWE-bench for exactly this.)

#### D. Integrity + provenance
- [ ] `cb lint --task <set>/<id>` reports zero ERRORs (static: front matter,
      fixture sources on disk, map binary, prompt hygiene, reference sandbox).
- [ ] Any edit under `Source/CraftBenchTests/` lands as a **committed, atomic
      change** reviewed on commit — grading materializes from
      git HEAD, so uncommitted fixtures never reach the grade (validate WIP
      with `cb discriminate --wip`).
- [ ] Map shipped as committed binary + its `docs/MAPS.md` inventory row.
- [ ] Reference at `tasks/<set>/<id>/reference/`, mirroring the writable prefix.

#### E. Regression — all levels, because the substrate is shared
- [ ] Tasks that share substrate with this one (the base fixture class, the GAS
      trio `CraftBenchCharacter`/`AttributeSet`/`GameplayTags`, the
      preamble renderer) **still discriminate YES**. A change made "for task X"
      must not break sibling Y — this is why the gate runs across the folder, not
      just the new task.
- [ ] **`cb batch-eval --references all` = N/N PASS** at least once before merge.

---

### Difficulty — where the cost actually is

- **Running the gate is cheap and token-free.** `cb discriminate <set>/<id>` is
  one command: build + two PIE legs, minutes on a warm cache, no model tokens.
  Enforcing it continuously as tasks accumulate is trivial.
- **The real work is authoring a fixture whose assertion genuinely FAILs the
  plausible wrong answer** — plus the reference and a good negative. That's
  judgment, not typing (a fixture that passes the reference is easy; one that
  provably rejects the obvious near-miss is the skill). This is where builder
  effort — or a build-verifier helper / human review — should go.

### For a CC agent building a task from a spec

- You may edit the agent-writable module, author the fixture + reference, and
  materialize the map. You **must** end by running `cb discriminate <set>/<id>`
  and reporting **YES/NO with both legs shown**. A task with a green reference
  PASS but no demonstrated empty FAIL is **not done** — say so plainly rather
  than reporting success. Prefer the foldered layout; identity by tag, not class.
