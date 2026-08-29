# CraftBenchTemplate substrate

The CraftBench **atomic-task substrate**. Tasks that declare
`substrate: CraftBenchTemplate` in their v2 front-matter block (see
`docs/AUTHORING_TEMPLATE.md`, "Substrate
decision") run against this project. The first task to exercise it is
[`tasks/cpp/t0-sanity-log-on-beginplay/task.md`](../../tasks/cpp/t0-sanity-log-on-beginplay/task.md).

## Engine and project shape

- Unreal Engine **5.8**
- Empty C++ project (no third-person template content; only the actor pairs
  individual tasks need)
- Two modules, intentionally split

### Two-module split

| Module | Type | Writable by agent? | Purpose |
|---|---|---|---|
| `CraftBenchTemplate` | Runtime (Game) | yes | The agent's edit surface. Hosts task-actor classes such as `ASanityActor`. |
| `CraftBenchTests` | Editor | **no** | The verifier's L2 fixture surface. Hosts `AFunctionalTest` subclasses such as `ASanityFunctionalTest`. |

The `CraftBenchTests` module is `Type = Editor` in its `.Build.cs`, so it is
not linked into a packaged build the agent could ship around. It also lives
behind the [`Source/CraftBenchTests/.AGENT_WRITE_DENY`](Source/CraftBenchTests/.AGENT_WRITE_DENY)
marker, backed by two enforcement layers: the sandbox (`AGENT_WRITABLE.json`)
denies the directory, so any submission file under it is rejected pre-grade;
and the eval runner materializes the graded substrate from **git HEAD**, so an
on-disk edit to this module never reaches the grade — committed changes are
review-gated on commit. This is what defends anti-gaming case
#5 (test disabling) in the t0 task spec.

### Per-task folders

New tasks keep their sources in per-task subfolders: the agent-facing scaffold
pair at `Source/CraftBenchTemplate/Tasks/<task-id>/` and the fixture pair at
`Source/CraftBenchTests/Tasks/<task-id>/`. Both modules are flat-layout, and
both `.Build.cs` files add `PrivateIncludePaths.Add(ModuleDirectory)` — that
is what lets sources under a `Tasks/` subfolder resolve includes as if they
sat at the module root. Pre-convention tasks stay flat at the module root.

## Eval maps

Every task map ships as a committed binary `.umap` under `Content/Maps/`
(new tasks: `Content/Maps/<task-id>/`) — the committed binary is the **only**
map source. The runner loads it directly and never re-bakes; a missing binary
is an explicit **L2 FAIL** (the text scaffolders were retired 2026-07).

Author maps by any route — directly in the editor, or via aura-mcp — and
commit the binary. Authoring needs a **real RHI** (no `-nullrhi` — the
historical `spawn_actor_from_class` crash under `-nullrhi`; L2 test runs
still use `-nullrhi`). Per-map contents, automation names, and provenance
live in the central inventory
[`docs/MAPS.md`](../../docs/MAPS.md) at the repo root (deliberately outside
the substrate: agent-visible surfaces are composed from this project tree,
`docs/` never reaches a model under test).

## L1 verifier command

The L1 build layer runs UnrealBuildTool against **both** targets — the
`CraftBenchTemplateEditor` (Editor) target and the `CraftBenchTemplate`
(Game) target. Both must exit 0; L1 short-circuits on the first failure.
On Windows the runner invokes the batch file via `cmd /c`:

```
cmd /c "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" ^
    CraftBenchTemplateEditor Win64 Development ^
    -project="%CD%\CraftBenchTemplate.uproject" -waitmutex
```

On POSIX it uses `Engine/Build/BatchFiles/Build.sh` with the matching
platform (e.g. `Mac`). The Game target repeats the same invocation with
`CraftBenchTemplate` in place of `CraftBenchTemplateEditor`.

L1 asserts the UBT exit code is 0 and that no new `shadowed-variable` or
`deprecated-declarations` warnings appear in agent-authored files (the
warning diff is pinned to the agent's writable paths only; substrate-
baseline warnings, if any, are tolerated).

## L2 verifier command

L2 runs the `ASanityFunctionalTest` actor via the automation framework in
PIE:

```bash
"$UE_ROOT/Engine/Binaries/Mac/UnrealEditor-Cmd" \
    "$(pwd)/CraftBenchTemplate.uproject" \
    -ExecCmds="Automation RunTests SanityFunctionalTest; Quit" \
    -unattended -nopause -nullrhi -log
```

The exact discovery filter and result-parse logic live in the eval runner;
this command is informational for developers reproducing a run locally.
