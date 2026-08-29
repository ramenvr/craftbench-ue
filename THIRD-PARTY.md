# Third-party components

CraftBench-UE is released under the MIT License (see [`LICENSE`](LICENSE)) — but
that grant covers **only the parts of this repository that CraftBench authored**.
Running the benchmark also puts material owned by Epic Games, Inc. into your
working tree. That material is *not* CraftBench's to relicense and is **not**
covered by the MIT grant.

This file records exactly where that line falls: what this repository ships, what
it deliberately does not, and what ends up in your tree once you have installed
the engine and run the bootstrap.

---

## 1. Unreal Engine 5.8 — required, not distributed

CraftBench-UE is pinned to Unreal Engine 5.8 and cannot run without it. The
engine is **not** included in this repository. You must obtain and install it
yourself from Epic Games, under the
[Unreal Engine End User License Agreement](https://www.unrealengine.com/eula).

Epic's in-engine `ModelContextProtocol` plugin — which the `unreal-mcp` arm
measures — ships inside the engine and is likewise Epic's, under the same EULA.

## 2. Epic Games template content — restored, not redistributed

**This repository contains no Unreal Engine template content.** The two
substrates under `UE-projects/` are Unreal Engine projects built on Epic's stock
templates, but the Epic-authored half of them — 881 files, about 260 MB — is not
committed here. CraftBench does not own that material and cannot relicense it,
so rather than ship a copy the repository ships a script that restores it from
your own UE 5.8 install. (Epic's template *source* is a separate question,
answered further down this section.)

```sh
py -3.12 tools\scripts\bootstrap_substrate.py     # Windows
python3 tools/scripts/bootstrap_substrate.py      # macOS / Linux / git-bash
```

It reads from your engine and writes into `UE-projects/`. No template content
travels from this project to you: the copy you end up with came out of the
engine you already licensed. README section 3 has the full step, including the
`--check` verification.

### What is Epic's inside a bootstrapped working tree

Once the bootstrap has run, these paths in **your** tree are **© Epic Games,
Inc., All Rights Reserved**, governed by the
[Unreal Engine EULA](https://www.unrealengine.com/eula), and **not** covered by
CraftBench's MIT grant. Restoring them changes nothing about who owns them; it
moves them from your engine into your project, which is what every Unreal
project created from a template does.

| Path in your tree | Files | Restored from, inside your UE 5.8 install |
|---|---:|---|
| `UE-projects/ThirdPerson/Content/Characters/` | 128 | `Templates/TemplateResources/High/Characters/Content/` — the Mannequin characters (`SKM_Manny`, `SKM_Quinn`), their rigs, animations and materials |
| `UE-projects/ThirdPerson/Content/ThirdPerson/` | 5 | `Templates/TP_ThirdPerson/Content/ThirdPerson/` |
| `UE-projects/ThirdPerson/Content/Variant_Combat/` | 31 | `Templates/TP_ThirdPerson/Content/Variant_Combat/` |
| `UE-projects/ThirdPerson/Content/Variant_SideScrolling/` | 19 | `Templates/TP_ThirdPerson/Content/Variant_SideScrolling/` |
| `UE-projects/ThirdPerson/Content/Variant_Platforming/` | 11 | `Templates/TP_ThirdPerson/Content/Variant_Platforming/` |
| `UE-projects/ThirdPerson/Content/LevelPrototyping/` | 29 | `Templates/TemplateResources/High/LevelPrototyping/Content/` |
| `UE-projects/ThirdPerson/Content/Input/` | 9 | `Templates/TemplateResources/High/Input/Content/` |
| `UE-projects/ThirdPerson/Content/__ExternalActors__/{ThirdPerson,Variant_Combat,Variant_SideScrolling,Variant_Platforming}/` | 479 | the same four subdirectories of `Templates/TP_ThirdPerson/Content/__ExternalActors__/` |
| `UE-projects/ThirdPerson/Content/__ExternalObjects__/{ThirdPerson,Variant_Combat,Variant_SideScrolling,Variant_Platforming}/` | 42 | the same four subdirectories of `Templates/TP_ThirdPerson/Content/__ExternalObjects__/` |
| `UE-projects/CraftBenchTemplate/Content/Characters/` | 128 | `Templates/TemplateResources/High/Characters/Content/` — the same character content, in the minimal substrate |
| **Total** | **881** | **≈260 MB** |

The one-file-per-actor sidecar directories are shared, not wholly Epic's. Under
`Content/__ExternalActors__/` and `Content/__ExternalObjects__/`, only the four
subdirectories named above come from Epic; everything under `.../Maps/` (286 and
9 files) belongs to CraftBench's own task maps, is MIT, stays committed, and the
bootstrap never writes there.

The scope note at the bottom of [`LICENSE`](LICENSE) describes this
bootstrapped state — the state in which those paths actually exist.

### Epic-authored template C++ source

The 87 stock Third Person template source files — 85 under
`UE-projects/ThirdPerson/Source/ThirdPerson/`, plus `ThirdPerson.Target.cs` and
`ThirdPersonEditor.Target.cs` beside them, ~200 KB in total — **remain committed
in this repository**: the project wizard rewrote the engine's `TP_ThirdPerson`
identifiers when the project was created, so copying
`Templates/TP_ThirdPerson/Source/` back does not reproduce them, and a bootstrap
that tried would hand you a project that does not compile.

Committed or restored, they are Epic's. They carry `Copyright Epic Games, Inc.`
headers, sit outside the MIT grant, and are governed by the EULA — as the
`LICENSE` scope note states. They are a derivative of a template Epic publishes
free for its licensees to build on, and anyone who can run this benchmark at all
is already such a licensee.

**Practical consequence for you.** You need an Unreal Engine license to run this
benchmark at all, so you are already a party to the EULA that governs this
material — which is why restoring it from your own install is the ordinary thing
to do here rather than a workaround. What you may **not** do is lift these files
out of your bootstrapped tree and redistribute them outside an Unreal Engine
project, or treat them as MIT-licensed because they sit in a directory of an
MIT-licensed repository. If you publish a fork, publish it the way this
repository is published: without them.

## 3. What the MIT grant *does* cover

Everything else, including all of the parts that make this a benchmark:

| Path | What it is |
|---|---|
| `tools/` | The harness: the `cb` CLI, the agent adapters for all three measured arms, the fairness/anti-cheat layer, the deterministic verifier (`tools/verify-single/`), and the substrate bootstrap (`tools/scripts/bootstrap_substrate.py`) |
| `tasks/` | Every task specification, reference solution, and discrimination variant authored by CraftBench |
| `UE-projects/*/Content/Maps/`, `Content/Tasks/`, `Content/Data/`, and the matching `Content/__External*__/Maps/` sidecars | The committed task maps and per-task assets — the benchmark itself. Authored by CraftBench, and the reason `UE-projects/*/Content/` is not simply empty in this repository |
| `UE-projects/*/Source/CraftBenchTests/` | The verifier-only UE module that drives the graded PIE fixtures. Contains no Epic-authored code |
| `UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/` | The agent-writable scaffold actors CraftBench authored |
| `docs/`, and the repository's own documentation | CraftBench-authored |

Source files CraftBench authored carry a `Copyright CraftBench` header; Epic's
carry `Copyright Epic Games, Inc.`. When the two disagree with anything written
here, **the per-file header is authoritative**.

## 4. The `aura-mcp` arm — disclosed, but not reproducible

CraftBench-UE measures three tool layers driving the same model. Two of them you can
run yourself; the third you cannot, and we would rather say so plainly than ship a
stub that pretends otherwise.

| Arm | What it is | Can you run it? |
|---|---|---|
| `claude-p` | Claude Code with no editor tools at all — the baseline | **Yes.** Needs only your own model API key |
| `unreal-mcp` | Claude Code plus Epic's in-engine MCP server, which ships inside UE 5.8 | **Yes.** Needs a stock UE 5.8 install and your own API key |
| `aura-mcp` | Claude Code given only Aura's MCP tool layer | **No** — see below |

`aura-mcp` measures a commercial product, Aura, which is not part of this release.
Running it requires all of: Aura's proprietary Unreal Engine plugin, two private
server components, and an Aura account with an active entitlement. None of those are
distributable, so the arm cannot be reproduced from this repository by anyone outside
the vendor.

What this repository *does* contain for that arm, so the comparison remains auditable:

- its dispatch and configuration (`tools/run-agent/adapters/registry.py`,
  `tools/run-agent/adapters/aura_mcp_config.py`) — including the exact tool
  restrictions applied to it, which is what makes it comparable to the other two;
No run results ship in this repository, for any arm — only the harness, the tasks
and the verifier. Where results are published separately, `aura-mcp`'s are
labelled as measurements of a system a reader cannot re-run.

What this repository deliberately does **not** contain is the machinery that logged a
browser into the Aura product and drove it. That code performed a credentialed
authentication flow against a private backend, and publishing it would expose a third
party's internals. It was removed rather than redacted.

Consequently, selecting `aura-mcp` in this open-source build fails immediately with an
explanatory message instead of attempting a partial run. That is intentional: a
half-working arm would produce numbers that look comparable and are not.

## 5. Runtime dependencies

The harness has **no third-party runtime dependencies** — it is standard-library
only by design (`tools/run-agent/pyproject.toml`). Two optional extras exist and
are not required:

| Extra | Package | Used for | If absent |
|---|---|---|---|
| `mem` | `psutil` | memory probes | falls back to a `ctypes` implementation |

Running an arm additionally requires the Claude Code CLI and a model API key,
which you supply yourself. Those are not distributed here.

---

*If you believe anything in this repository is misattributed, please open an
issue — we would rather fix it than argue about it.*
