# CraftBench on Windows — platform notes

> **Install and first run live in the [README](../README.md)** — sections 3
> (Install) and 5 (Run your first eval) own that path, on every platform.
>
> This document is the Windows-specific remainder: the things that bite only
> here, and are not obvious from the error they produce. Line endings and the
> `.gitattributes` pins, `MAX_PATH`, argument quoting, where Windows behaviour
> diverges from macOS, and which files carry the platform-specific code.
>
> Windows + UE 5.8 is the validated platform and the only one CI runs.
> Verification is deterministic either way: an L1 UBT build of both targets
> plus an L2 PIE `AFunctionalTest`, with no LLM in the PASS/FAIL gate.

## 1. Prerequisites

| Requirement | Detail / how to check |
| --- | --- |
| **OS** | Windows 10 or 11, x64. |
| **UE 5.8 install** | Must contain `Engine\Build\BatchFiles\Build.bat` (L1 build script) and `Engine\Binaries\Win64\UnrealEditor-Cmd.exe` (L2 PIE editor). Default Epic Launcher path: `C:\Program Files\Epic Games\UE_5.8`. |
| **Python** | `python --version`. **Python 3.11+ (3.12 recommended)** (verifier core alone runs on 3.10; pure stdlib — `unittest`, `subprocess`, `shutil`, `tempfile`). `cb.cmd` defaults to `py -3.12`. |
| **`git` on PATH** | Required for the default substrate-from-git materialization pipe and for applying `.gitattributes` at checkout. Git for Windows provides it. |
| **`tar` on PATH** | The substrate-from-git pipe is `git archive HEAD \| tar -x`. Git for Windows ships `tar`; Windows 10 1803+/11 also ship a native `tar.exe`. If neither is present, plan to use `--substrate-from-live` (Section 7). |
| **`claude` CLI** | Needed by the `claude-p` and `unreal-mcp` arms (both drive it). The Claude Code installer drops a `claude.cmd` (and/or `claude.exe`) shim — it must be on `PATH`. Not needed for the deterministic verifier. |

Verify the two UE entry points exist (PowerShell):

```powershell
$UE = "C:\Program Files\Epic Games\UE_5.8"
Test-Path "$UE\Engine\Build\BatchFiles\Build.bat"
Test-Path "$UE\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

Both must print `True`. The verifier checks `script.exists()` / binary
`.exists()` up front and aborts L1/L2 with a clean error if either is missing
(it never depends on PATH for these — they are resolved as absolute paths under
`--ue-root`).

---

## 2. Repo checkout & line endings

Two byte-level hazards on a Windows checkout: CRLF rewrites of tracked text
the runner reads/writes, and text-normalization of the committed binary UE
assets. The repo ships a root `.gitattributes` that pins the load-bearing
bytes:

```
*.uproject                                text eol=lf
*.umap                                    binary
*.uasset                                  binary
```

Recommended one-time global setting (belt-and-suspenders; `.gitattributes`
already overrides per-path, but this keeps unrelated text clean):

```powershell
git config --global core.autocrlf input
```

After cloning, confirm `.gitattributes` is in force:

```powershell
git check-attr -a UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject
# expect:  text: set   eol: lf

git check-attr text eol UE-projects/CraftBenchTemplate/Content/Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap
# expect:  text: unset   (binary -> no eol conversion, no text diffing)
```

> **Why this matters:** without `.gitattributes`, `core.autocrlf=true` (the
> Windows git default) rewrites LF → CRLF on checkout for tracked text — the
> `eol=lf` pin keeps the `.uproject` (which the runner reads and rewrites)
> byte-stable across OSes. The committed binary `.umap` / `.uasset` files are
> marked `binary` so a stray `text=auto` guess can never re-normalize
> (corrupt) them — and the committed binary is the **only** map source, so a
> mangled `.umap` is an explicit L2 FAIL.

The runner also hardens itself at write time: when it disables the Aura plugin
in the cloned workdir `.uproject`, it uses `write_bytes(...encode("utf-8"))`
with explicit `\n`, so the file stays LF regardless of platform defaults
(byte-identical to the macOS output).

---

## 3. `Plugins\` — nothing to do

The whole `Plugins/` folder is **git-ignored** in craftbench — there is no
committed symlink or junction, and a fresh checkout has **no `Plugins/` at
all**. On this release that is the finished state, not a missing step.

Graded runs never read it. The runner **disables the Aura plugin in the cloned
workdir `.uproject`** (it appends `{"Name": "Aura", "Enabled": false}`, because
that plugin needs CEF3 which is absent headless) and **excludes all of
`Plugins/`** from the substrate copy, so an empty `Plugins/` changes no verdict
on any arm you can run from here.

The one thing that ever wanted a populated `Plugins/` was the commercial
product's own UE plugin, on the `aura-mcp` arm — which is disclosed but not
reproducible from this repository, and is refused by `cb` before it looks for a
plugin at all. There is no clone to make.

---

## 4. Run the verifier unit tests

These do **not** require UE installed — they exercise the parser, sandbox,
layer registry, and report logic (the exact files the Windows work touched).

```powershell
cd C:\path\to\craftbench
python -m unittest discover -v tools/verify-single/tests
```

Expected: **all tests pass** (`OK`, possibly with `skipped=N`); the Windows
SKIPs below are expected.

> **On Windows, the L1 dual-target tests SKIP by design.** `TestL1DualTarget`
> stubs UBT with a **shell script** (`#!/bin/sh`), which Windows cannot exec, so
> those cases are skipped when `platform.system() == "Windows"`. A `SKIPPED`
> there is **expected and correct** — not a failure. All other tests should
> pass.

---

## 5. Grade a reference solution end-to-end

This is the real validation — it requires a UE 5.8 install. Quote `--ue-root`
because the default path contains spaces.

```powershell
cd C:\path\to\craftbench
python tools/verify-single/run_task.py `
    --task tasks/cpp/t0-sanity-log-on-beginplay/task.md `
    --submission tasks/cpp/t0-sanity-log-on-beginplay/reference `
    --ue-root "C:\Program Files\Epic Games\UE_5.8" `
    --workdir C:\cb58\wd   # Windows MAX_PATH: pick any short, NON-EXISTENT dir — the verifier requires the workdir not to exist
```

(The backtick `` ` `` is the PowerShell line-continuation; or put it all on one
line.)

What you should observe:

- **L1** builds **both** targets — `CraftBenchTemplateEditor` and
  `CraftBenchTemplate` (Game) — by invoking
  `cmd /c <UE>\Engine\Build\BatchFiles\Build.bat <Target> Win64 Development -project=<abs .uproject> -waitmutex`.
  Both must exit 0; L1 short-circuits on the first failure. (The `cmd /c` prefix
  is **required** on Windows: `Build.bat` is a batch file and `CreateProcess`
  under `shell=False` cannot exec a `.bat` directly. macOS/Linux exec `Build.sh`
  directly, unchanged.)
- **L2** launches `...\Engine\Binaries\Win64\UnrealEditor-Cmd.exe` against the
  task map (e.g. `/Game/Maps/L_SanityTask`) with
  `-ExecCmds="Automation RunTests <filter>" -nullrhi -deterministic -FPS=<rate>`,
  runs the `AFunctionalTest` in a real headless PIE world, and writes
  `index.json` under `-ReportExportPath`.

To grade an arbitrary task + submission:

```powershell
python tools/verify-single/run_task.py `
    --task tasks/<set>/<task_id>/task.md `
    --submission <path-to-agent-output-dir> `
    --ue-root "C:\Program Files\Epic Games\UE_5.8" `
    --workdir C:\cb58\wd
```

---

## 6. Run the parallel batch smoke: `batch-eval`

> **Status.** `batch-eval` is token-free and needs **no key and no vendor
> stack** — only Python plus a UE 5.8 install — so it runs on a clean checkout
> and is the half worth validating on a new Windows box. Its generation
> counterpart (`batch-gen`) drove the commercial product's own web UI and is not
> part of this release; §6-B below says what to run instead.
>
> `batch-eval` parallelizes on **one** editor pool, not a real fleet — read
> `--verify-concurrency` as a memory budget, not a speed dial.

Run the unit tests for these modules first (no UE, no key):

```powershell
cd C:\path\to\craftbench\tools\run-agent
python -m unittest tests.test_mem_gate tests.test_batch_eval
# expect:  OK  (all tests pass)
```

### A. `batch-eval` — parallel deterministic grade (token-FREE; validate this FIRST)

Needs a UE 5.8 install but **no key and no vendor stack**. Point it at a folder of already-isolated
submission dirs (each named by its task id), or use `--references all` to sweep
every committed reference solution (`tasks/<set>/<id>/reference/`) — the
ready-made smoke input:

```powershell
cd C:\path\to\craftbench\tools\run-agent
.\cb batch-eval --references all `
    --ue-root "C:\Program Files\Epic Games\UE_5.8"
```

**Confirm:** verifies run **one at a time by default** (`--verify-concurrency 1`),
each its own `craftbench-*` temp clone + `UnrealEditor-Cmd`, and a
`runs/aura-product-eval/<label>-<ts>/summary.json` is written with per-submission
verdicts. (That directory name is a leftover from the harness's history — it is
`batch_eval.DEFAULT_RUN_SUBDIR`, and nothing about this token-free command
touches a vendor lane.) Reference solutions should PASS. On a **>32 GB** host, add
`--verify-concurrency 2` to overlap L2 across two editors (the memory-pressure gate
then holds it to ≈2-wide, blocking a 3rd launch under WARN/CRITICAL); the speedup is
partial — UBT's global `-waitmutex` serializes the L1 compile phase, only L2 PIE overlaps.
>
> **`--verify-concurrency` now defaults to 1** (safe on ≤32 GB). Don't raise it on a
> constrained host: at 2-wide the two full-RHI L2 PIE editors contend and a reference
> solution can spuriously FAIL at **L2** even though it **passed L1** (observed
> 2026-06-20: 2/4 FAIL at 2-wide, all L1-pass) — and on Windows without psutil the
> mem-gate back-off is off, so the semaphore is the only cap. `--warm-cache` (below)
> recovers much of the 1-wide speed.

### B. Generation — `cb eval`, `cb bench`, `cb matrix`

There is no parallel *generation* command on this release. The one that existed
(`batch-gen`) fanned out N concurrent chats against the commercial product's own
web UI, which is the part of the `aura-mcp` lane that is disclosed but not
reproducible from this repository; it went with that lane rather than shipping
as a command that could never start.

Generate with the per-run commands instead, all of which run from a clean
checkout with one API key:

```powershell
cd C:\path\to\craftbench
.\cb eval  --task cpp/t0-sanity-log-on-beginplay --model claude-p:sonnet
.\cb eval  --task cpp/t0-sanity-log-on-beginplay --model unreal-mcp:sonnet
.\cb bench --model claude-p:sonnet,unreal-mcp:sonnet --task cpp/t0-sanity-log-on-beginplay --repeat 1
```

Grading stays decoupled either way: whatever produced a deliverable, `cb eval`
and `cb batch-eval` (§6-A) grade it through the same deterministic verifier.

> **Memory first.** Each cold verify / editor is ~8 GB; this is bench-marked for a
> 26 GB box at ≈2-wide. The memory-pressure gate is a **soft guard**: on macOS it
> reads the kernel `vm_pressure_level`; on Windows it reads `psutil`
> (virtual-memory + swap %) and falls back to a `GlobalMemoryStatusEx` ctypes
> shim. **If neither `psutil` nor the ctypes shim is available, the gate is INERT
> (a fail-open no-op) and emits a one-time WARN** — it will NOT stop an OOM. The
> Windows mem-gate path is itself unvalidated on Windows, so do not lean on it:
> set **`--verify-concurrency 2`** (and `--concurrency` ≤ 2–3) and **confirm free
> RAM manually** before bursting wider.

---

## 7. Path & quoting notes

- **Always quote `--ue-root` if it contains spaces** (the Epic default does:
  `C:\Program Files\Epic Games\UE_5.8`). In PowerShell, use double quotes.
- **No shell parsing of the UE command line.** Every editor/UBT invocation is
  built as an **argv list** and dispatched with `subprocess` using
  `shell=False`. So a path token like `C:\Program Files\Epic Games\UE_5.8` is
  passed as one verbatim argument — no extra escaping is needed inside the argv
  list, and spaces in the install path are preserved (true for every editor/UBT
  invocation).
- **Backslash paths in build warnings are normalized.** The L1 warning counter
  normalizes `\` → `/` when back-mapping `.gen.cpp` warnings to source, so
  Windows-style paths in UBT output are handled the same as POSIX.
- **`--substrate-from-live` fallback.** If `git`/`tar` are missing (or you want
  to grade uncommitted disk state), pass `--substrate-from-live` to copy the
  live working tree instead of materializing from git HEAD. Without it, a
  missing `git`/`tar` now raises a **named, actionable** error (see Section 9),
  not a bare `FileNotFoundError`.

---

## 8. Known divergences from Mac

- **The RequestExit / Cocoa-runloop hang is Mac-only.** On macOS the editor
  often prints `TEST COMPLETE`, calls `RequestExit`, then sits forever in a
  Cocoa runloop. The verifier tails stdout for terminal markers and kills the
  process on first match (`run_editor_with_marker_kill`). On **Windows the
  editor usually exits on its own**, so the marker-kill is a **safety net /
  wait-shortener, not a necessity**. The termination calls are
  platform-agnostic: `proc.terminate()` / `proc.kill()` map to
  `TerminateProcess` on Windows (Python 3.3+), so no host-specific signaling is
  needed. (`l2_introspect.py` and `asset_capture.py` both route their editor
  subprocess through the same wrapper and inherit this.)
- **Temp dirs live under `%TEMP%`.** Workdirs are created via
  `tempfile.mkdtemp(...)`, which on Windows resolves under `%TEMP%`
  (typically `C:\Users\<you>\AppData\Local\Temp`). Watch for path-length limits
  and antivirus file locks (Section 9).
- **Git-Bash / MSYS / Cygwin Python is supported.** Both the **L1 build script**
  (`Build.bat` + `Win64` platform arg) **and** the L2 editor-binary resolution
  match the host family case-insensitively via the shared `_is_windows_host()`
  check, so a `MSYS_NT-…`, `MINGW64_NT-…`, or `CYGWIN_NT-…` Python resolves
  `Build.bat` / `Engine\Binaries\Win64\UnrealEditor-Cmd.exe` instead of erroring
  out. (L1 and L2 agree on what counts as a Windows host — they no longer
  disagree.)

---

## 9. Troubleshooting

**Read the preflight gate's output first**: every `cb` eval-family command opens
with a ~2s environment gate (`aura_rig/envgate.py`) that detects the classic
Windows killers below (Live Coding mutex, MAX_PATH workdir, RAM/C3859, missing
UE root) and prints the exact fix before any build starts. Raw `run_task.py`
invocations skip the gate — this table is for those, and for the long tail.

| Symptom | Likely cause & fix |
| --- | --- |
| **L1 aborts: "script not found" / `Build.bat` missing** | `--ue-root` is wrong or the install lacks `Engine\Build\BatchFiles\Build.bat`. Verify with `Test-Path` (Section 1). The script path is resolved as an absolute path under `--ue-root`, not via PATH. |
| **L1 crashes mid-compile: `C3859`, `0xC0000005`, or "paging file too small"** | Two UE 5.8 knobs. The verifier already builds with `-NoUBA` (UE 5.8's Unreal Build Accelerator crashes on a dirty cross-run cache; set `CRAFTBENCH_ALLOW_UBA=1` only to re-enable). If it still overflows on a RAM-constrained host, cap UBT with `CRAFTBENCH_L1_MAX_PARALLEL` — `2` on a ~32 GB box (`4` can still overflow while the Aura stack is up). `cb` applies its own memory gate; raw `run_task.py` does not, so set the env var yourself. See `.env.example` + `tools/verify-single/layers/l1_build.py`. |
| **L1 fails: `Unable to build while Live Coding is active`** | An open editor on the project holds UE's Live Coding lock, which blocks **all** UBT builds of it. Close the editor (`cb down` stops the managed one; the graded `cb` path stops it automatically before building), or disable Live Coding for that project (`bEnabled=False` under the Live Coding section of its `Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini`). |
| **`'git' not found on PATH` / `'tar' not found on PATH`** | The substrate-from-git pipe needs both. Install Git for Windows (ships both), or rerun with `--substrate-from-live` to copy the live working tree. The runner now raises a named error naming the missing tool and pointing at the fallback. |
| **L2 fails: editor binary missing** | `UnrealEditor-Cmd.exe` is not at `<UE>\Engine\Binaries\Win64\`. Check the install layout; a source build may differ from the launcher layout. |
| **Substrate copy fails / `Plugins\` issues** | The graded path relies on the verifier's plugin-disable + `Plugins/` exclusion in the cloned `.uproject` (Section 3). An empty `Plugins/` is correct on this release; there is nothing to clone into it. |
| **`claude` not found (baseline harness)** | The Claude Code launcher shim (`claude.cmd` / `claude.exe`) is not on PATH. Reinstall Claude Code or add its install dir to PATH; the adapter probes `claude`, then `claude.cmd`, then `claude.exe` via `shutil.which`. |
| **Workdir / temp errors** | Path too long or antivirus lock under `%TEMP%`. For path-length failures the real fix is a **short `--workdir`** (e.g. `C:\cb58\wd` — any short, non-existent dir; the harness paths already default to `<CB_ROOT>\wd` = `C:\cb\wd`, and `CRAFTBENCH_WD_ROOT` is only a back-compat override on top of that — the old `C:\cbwd` default is RETIRED, so a `C:\cbwd` on disk is a stale second root nothing scans). `git config --global core.longpaths true` only fixes git *checkout* — it does NOT lift the UE/UBT tooling path limits. For antivirus locks, exclude the temp dir from real-time AV scanning. |

---

## Where the Windows-specific code lives

- `tools/verify-single/layers/l1_build.py` — `cmd /c Build.bat` wrap, Win64
  platform token, absolute-path script-exists check.
- `tools/verify-single/layers/l2_pie.py` — `Win64\UnrealEditor-Cmd.exe`
  resolution (case-insensitive host-family match), platform-agnostic
  marker-kill.
- `tools/verify-single/run_task.py` — LF-byte-stable `.uproject` write; named
  `git`/`tar` PATH error in `copy_substrate_from_git`.
- `tools/verify-single/sandbox.py` — backslash → POSIX prefix normalization.
- `tools/run-agent/adapters/claude_p.py` — `_resolve_claude_binary` probes
  `claude` / `claude.cmd` / `claude.exe` on Windows.
- `/.gitattributes` — LF-pin `.uproject`, binary-mark `.umap` / `.uasset`.
