"""cb — THE single cross-platform entry point for the CraftBench-UE rig.

It is a *thin* argparse CLI: every piece of orchestration machinery lives in
:mod:`aura_rig.stack` and the graded spine is ``tools/run-agent/run.py``. This
file only wires them together per-command — it reimplements nothing of its own.

History: this replaced the Windows-only PowerShell rig (``stack/cb.ps1`` +
``stack/cb-common.ps1``), retired 2026-06-14 after the Python CLI passed a live
Windows bring-up + graded ``eval`` (t0-sanity, L1+L2) → PASS. The inline
``# ports cb.ps1 ...`` / ``# exactly like cb.ps1 ...`` comments below record that
lineage (the per-command ordering deliberately mirrors what the .ps1 did); the
.ps1 files no longer exist in the tree.

THE THREE MEASURED ARMS (tools/run-agent/adapters/registry.py). All three are
the SAME ``ClaudePAdapter`` differing only in ``--mcp-config`` and
``--disallowed-tools`` — that asymmetry IS the measurement:

    claude-p     a generalist reasoner with Claude Code's own file tools
    unreal-mcp   ...the same reasoner given Epic's first-party in-editor MCP
                 server (UE 5.8 ModelContextProtocol + AllToolsets)
    aura-mcp     ...the same reasoner given the Aura UE plugin's MCP servers

**aura-mcp is DISCLOSED BUT NOT REPRODUCIBLE from this repository.** Running it
needs the proprietary Aura stack — a closed-source UE plugin, two private web
services and an entitled account — none of which ship here, and the login
machinery that drove them was removed from this release rather than published.
The arm stays in the registry and in the docs (its dispatch, its MCP config and
its verifier lane are public, so the published measurement can be read and
audited), but SELECTING it from this CLI fails fast with a message saying so
instead of pretending to bring a stack up. See THIRD-PARTY.md.

Run it (always as a module so the package imports resolve)::

    python -m aura_rig.cb up                                   bring the editor stack up + gate on readiness (no run)
    python -m aura_rig.cb smoke [--agent [MODEL]]              prove the golden path: preflight -> verifier unit tests -> t0 reference grade (+ one live eval with --agent; that leg spends tokens)
    python -m aura_rig.cb eval     --task gp-spawner-population graded craftbench eval (dispatch + L1 + L2)
    python -m aura_rig.cb batch-eval <outputs_dir>            grade a FOLDER of isolated submission dirs in PARALLEL (memory-gated cold verifies; NO tokens)
    python -m aura_rig.cb batch-eval --references [all|<set>]  ...same, over every task's own REFERENCE solution (folder-local reference/ or legacy tests/reference-solutions/<id>/)
    python -m aura_rig.cb tasks                                browse task sets -> tasks -> detail, then run the chosen one
    python -m aura_rig.cb view     [--graded] [--map L_SpawnSequence] [--run <run_dir>] [--project <dir>]
                                                               open a WINDOWED editor to SEE / Play(PIE) the change
    python -m aura_rig.cb status                               one-shot overview: stack health, editor project, recent runs
    python -m aura_rig.cb where [--link]                       READ-ONLY: print every resolved machine dir (CB_ROOT model) + existence; --link drops gitignored <repo>/.cb/{wd,scratch} links
    python -m aura_rig.cb doctor                               READ-ONLY env diagnostic: per-tier readiness + fix hints
    python -m aura_rig.cb clean                                reset the headless scratch project to pristine
    python -m aura_rig.cb down                                 stop the WHOLE stack (supervisor + editor + LiveCodingConsole)

Overrides (flag OR env, exactly like cb.ps1):
    --project / CB_DRIVE_PROJECT   scratch playground (used AS-IS, never reset)
    --ue-root / CB_UE_ROOT         UE 5.8 install root
    --py      / CB_PY              harness python launcher line ("py -3.12", a full path, ...)
    CB_CRAFTBENCH                  repo root
    --model --ceiling --map --keep --reuse-editor

Dispatch contract (mirrors cb.ps1):
  * ``eval``     routes on the model slug: claude-p / openrouter / bare -> the
                 generalist BASELINE runner (run.py, no editor stack);
                 unreal-mcp -> run.py --live-project against a headless editor
                 serving Epic's in-editor MCP; aura-mcp -> the fail-fast notice
                 above.
  * ``view``     stops the headless editor (releases the project lock) and opens a
                 WINDOWED editor (default the scratch; --run overlays a graded
                 deliverable onto the template; --project overrides the target).
  * ``status``   READ-ONLY: probes the editor the way ``up`` GATES it (one real
                 MCP initialize, never a port probe — so the two can never
                 disagree about "ready"), then prints the stack owner, the
                 LiveCoding-count and scratch-state diagnostics the cb.ps1
                 status arm had, and the last run's verdict. It renders no
                 stack.snapshot(): that five-component health frame went out
                 with the aura-product lane (see cmd_status).
  * ``doctor``   READ-ONLY: doctor.real_probe builds a Probe of live facts, then
                 prints doctor.diagnose()'s per-tier readiness + fix hints; never mutates.
  * ``clean``    resets the managed scratch to pristine (a user --project is left alone).
  * ``down``     stops the whole stack supervisor-first via stack.stop_stack().

The only token-spending step is the shelled-out run.py; this CLI never drives
an agent itself.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# The orchestration library (port of cb-common.ps1) — JUST written; we dispatch
# to ITS real function names and never reimplement them.
from aura_rig import stack
# The ONE machine-dir resolver (CB_ROOT -> wd/scratch roots); `cb where` prints it.
from aura_rig import paths as cb_paths


# --------------------------------------------------------------------------- #
# Small console helper (cb.ps1 used Write-Host everywhere).                     #
# --------------------------------------------------------------------------- #

BAR = "=" * 60

# The reference-gate FAIL code, shared by `cb refgate` and `cb bench
# --refgates`. DISTINCT from cb's own 0/1/2 AND from run_task.py's 0-8 verdict
# taxonomy (the repo conventions — 3 retired, 6 forbidden), so a wrapper reading either
# domain can never mistake "a committed reference failed its token-free gate"
# for a usage error or a graded verdict.
EXIT_BENCH_REFGATE_FAIL = 9

# The eval default task; also the sentinel `cb tasks` uses to tell "no --task given"
# (launch the picker) from an explicit `--task` (run it directly).
_DEFAULT_TASK = "t0-sanity-log-on-beginplay"

# The eval/bench default model; also the sentinel `cb bench` uses to tell "no
# --model given" (bare invocation -> the interactive wizard) from an explicit
# --model. Same accepted limitation as _DEFAULT_TASK: literally typing the
# default value reads as "not given".
#
# This was a bare Aura model key ("sonnet-5") until the open-source release.
# With no colon that slug resolved to the aura-product backend BY CONVENTION,
# so an operator who never passed --model was silently routed onto the
# proprietary lane. The public default is the arm every reader of this repo can
# actually run: claude-p - Claude Code's own file tools, no editor stack at all.
_DEFAULT_MODEL = "claude-p"


def _say(msg: str = "") -> None:
    print(msg, flush=True)


def _stdio_is_tty() -> bool:
    """Both ends interactive — the gate for the bench wizard (and a seam tests
    monkeypatch). Piped/redirected invocations must keep flag-only behavior."""
    return sys.stdin.isatty() and sys.stdout.isatty()


# --------------------------------------------------------------------------- #
# Pure model-slug routing (unit-testable WITHOUT UE).                          #
# --------------------------------------------------------------------------- #

# Backends that go through run.py (the generalist BASELINE runner) with NO
# editor stack at all: the agent gets Claude Code's own file tools and a
# workspace copy of the substrate.
_BASELINE_BACKENDS = ("claude-p", "openrouter", "bare")

# The stock-Unreal tool-layer backend: run.py --live-project against ONE
# headless editor serving Epic's first-party in-editor MCP server (UE 5.8
# ModelContextProtocol + AllToolsets). No web services, no login.
_UNREAL_MCP_BACKEND = "unreal-mcp"

# The Aura tool-layer backend. A first-class, DISPATCHABLE slug, so the
# published three-arm measurement stays readable from this repository — but NOT
# runnable here; see _AURA_MCP_UNAVAILABLE below.
_AURA_MCP_BACKEND = "aura-mcp"

# Every slug this CLI knows how to route. A colon-free slug outside this set
# used to fall through to the aura-product default, so `--model sonnet-5` — or
# any typo — silently entered the proprietary lane instead of being reported.
# There is no such default any more: an unknown slug is named and refused.
_KNOWN_BACKENDS = _BASELINE_BACKENDS + (_UNREAL_MCP_BACKEND, _AURA_MCP_BACKEND)


def _backend_of(model_slug: str) -> str:
    """Return the backend portion of a "<backend>:<model>" slug.

    With a colon, the backend is the part before it ("claude-p:opus" ->
    "claude-p"). With NO colon the slug IS the backend name ("claude-p",
    "unreal-mcp", "aura-mcp"). An UNRECOGNIZED bare word returns ITSELF rather
    than raising, so the caller can print it verbatim in the refusal below — a
    routing helper that threw from underneath every f-string in this file would
    trade a silent mis-route for a stack trace, which is not an improvement."""
    if ":" in model_slug:
        return model_slug.split(":", 1)[0]
    return model_slug


def _is_unreal_mcp_backend(model_slug: str) -> bool:
    """True iff the slug routes to the Epic-MCP editor path (unreal-mcp[:*])."""
    return _backend_of(model_slug) == _UNREAL_MCP_BACKEND


def _is_aura_backend(model_slug: str) -> bool:
    """True iff the slug names the Aura tool-layer arm (aura-mcp[:*]).

    NOT runnable from this repository — every command that accepts a model puts
    such a slug through _refuse_unroutable_model before it can spend anything."""
    return _backend_of(model_slug) == _AURA_MCP_BACKEND


# --------------------------------------------------------------------------- #
# aura-mcp: DISCLOSED, NOT REPRODUCIBLE (open-source release).                 #
# --------------------------------------------------------------------------- #
#
# The ARM survives in full: adapters/registry.py still dispatches it, its
# --mcp-config and --disallowed-tools ship verbatim (that asymmetry against
# claude-p and unreal-mcp IS the measurement), and it is graded by the same
# verifier every other arm is graded by. What does NOT survive is the RUNTIME.
# Bringing this arm up drove the proprietary Aura product's own login and its
# two private web services, and that login machinery was DELETED for this
# release rather than published. Nobody outside the vendor could complete the
# bring-up in any case (it also needs a closed-source UE plugin and an entitled
# account), so the honest behavior is to say so in the first second instead of
# failing eight minutes deep in a stack that was never going to come up.
_AURA_MCP_UNAVAILABLE = """\
FAIL  the `aura-mcp` arm is DISCLOSED BUT NOT REPRODUCIBLE from this repository.
      Running it needs the proprietary Aura stack - a closed-source UE plugin,
      two private web services and an entitled account - none of which are part
      of this open-source release, and the login machinery that drove them was
      removed rather than published.
      The arm itself is still fully disclosed: its dispatch lives in
      tools/run-agent/adapters/registry.py and its exact tool-access
      configuration in adapters/aura_mcp_config.py, so the published three-arm
      measurement can be read and audited without running it.
      Having the Aura plugin on this machine does not change this: what `cb`
      removed is the bring-up and login this route ran BEFORE dispatch, not
      just the plugin lookup. See THIRD-PARTY.md.
      Arms that DO run from this repository: claude-p[:<model>],
      unreal-mcp[:<model>], openrouter:<provider/model>, bare:<provider/model>."""


def _refuse_unroutable_model(model_slug: str) -> bool:
    """The gate every model-taking command runs FIRST — before the env gate,
    before task resolution, before a single process starts. True (and says why)
    when the slug names no backend this CLI routes, or names the disclosed but
    unavailable aura-mcp arm. Costs nothing and never raises."""
    backend = _backend_of(model_slug)
    if backend not in _KNOWN_BACKENDS:
        _say(f"FAIL  unknown model backend `{backend}` "
             f"(from --model {model_slug!r}).")
        _say("      Known backends: " + ", ".join(_KNOWN_BACKENDS) + ".")
        _say("      Spell the arm explicitly, e.g. `--model claude-p:sonnet-5` "
             "or `--model unreal-mcp`.")
        return True
    if backend == _AURA_MCP_BACKEND:
        _say(_AURA_MCP_UNAVAILABLE)
        return True
    return False


def _live_substrate_for_spec(ctx: "_Ctx", spec_path):
    """(substrate_dir_name, substrate_root, live_uproject) for a resolved task
    spec — the LIVE substrate the task declares (multi-substrate threading for
    the --live-project arms). On the DEFAULT substrate the uproject stays
    ``ctx.paths.uproject`` (which honors a CB_UPROJECT override), keeping
    today's behavior byte-identical; a non-default substrate resolves its own
    single .uproject by glob (FileNotFoundError when it is missing/ambiguous —
    callers report FAIL rather than silently driving the wrong project). An
    UNPARSEABLE spec falls back to the default substrate — exactly the
    pre-multi-substrate behavior; downstream run.py surfaces the real error."""
    from aura_rig import graded_scratch
    try:
        name = graded_scratch.substrate_for(spec_path)
    except Exception:  # noqa: BLE001 — unreadable/malformed spec
        name = "CraftBenchTemplate"
    substrate_root = ctx.paths.craftbench / "UE-projects" / name
    if name == "CraftBenchTemplate":
        return name, substrate_root, ctx.paths.uproject
    return name, substrate_root, stack.find_uproject(substrate_root)


# --------------------------------------------------------------------------- #
# Resolution shared by every command (ports cb.ps1's top-of-file block).       #
# --------------------------------------------------------------------------- #

class _Ctx:
    """The resolved environment cb.ps1 sets up once at the top: paths, the Aura
    env, the harness python (exe + pre-args), and the UE editor binary."""

    def __init__(self, args: argparse.Namespace):
        # Flag -> env, exactly as cb.ps1 does it BEFORE dot-sourcing cb-common.
        if args.ue_root:
            os.environ["CB_UE_ROOT"] = args.ue_root
        if args.py:
            os.environ["CB_PY"] = args.py

        self.paths = stack.StackPaths()
        stack.load_aura_env(self.paths)  # Import-AuraEnv
        # load_aura_env may have just surfaced a plugin-root override from
        # craftbench/.env. StackPaths was built BEFORE the load, so any member
        # derived from that root still points at the substrate Plugins/
        # fallback — rebuild so the rig resolves (cheap + pure).
        if os.environ.get("CB_GENIUS"):
            self.paths = stack.StackPaths()

        hp = stack.resolve_harness_py()  # Resolve-HarnessPy -> (exe, pre) | None
        self.py_exe: Optional[str] = hp[0] if hp else None
        self.py_pre: List[str] = list(hp[1]) if hp else []

        self.ue: Optional[Path] = stack.resolve_ue()  # Resolve-UE (+ exports CB_UE_ROOT)

    # --- Require-Stack: gate that both prerequisites + a GREEN stack exist ---
    def require_stack(self, uproject: Path) -> None:
        """Port of cb.ps1 Require-Stack: fail fast on a missing harness python or
        UE, else bring the stack up on <uproject> and exit 1 if it is not GREEN.

        It used to take two more keyword arguments, and both belonged to the cut
        lane rather than to the bring-up: ``product_login`` logged a browser
        into the proprietary product client so its in-page tool executor would
        mount, and ``defer_editor`` handed editor ownership to the aura-mcp
        lane so run.py could start it after the fairness hide. Neither route
        exists in this release, and no surviving caller passed either."""
        if self.py_exe is None:
            _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
            sys.exit(1)
        if self.ue is None:
            _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
            sys.exit(1)
        green = stack.invoke_bringup(
            uproject, self.ue, self.py_exe, self.py_pre, self.paths, log=_say,
        )
        if not green:
            _say(BAR)
            sys.exit(1)


# --------------------------------------------------------------------------- #
# Helpers ported from cb.ps1 (Show-NewestRun / Stop-HeadlessEditor).           #
# --------------------------------------------------------------------------- #

def _show_newest_run(ctx: _Ctx, sub: str, open_report: bool = False) -> None:
    """Print the newest run dir under runs/<sub> (ports Show-NewestRun), write
    its static report.html, and — for interactive `cb eval` (open_report=True,
    stdout a TTY, CB_OPEN_REPORT!=0) — open the report in the browser."""
    runs = ctx.paths.craftbench / "runs" / sub
    try:
        dirs = [p for p in runs.iterdir() if p.is_dir()]
    except OSError:
        dirs = []
    if dirs:
        newest = max(dirs, key=lambda p: p.stat().st_mtime)
        _say(str(newest))
        _recap_run_summary(newest)
        rep = _write_run_report(ctx, newest)
        if rep is not None:
            opening = (open_report and sys.stdout.isatty()
                       and os.environ.get("CB_OPEN_REPORT", "1") != "0")
            _say(f"    report (html) : {rep}"
                 + ("  (opening in your browser; CB_OPEN_REPORT=0 to disable)"
                    if opening else ""))
            if opening:
                _open_in_browser(rep)


def _write_run_report(ctx: _Ctx, run_dir: Path) -> Optional[Path]:
    """Write the run's self-contained report.html via the dashboard's ONE
    renderer (tools/dashboard/web/report_bridge.write_static_report — the
    static twin of the web app's /api/run/{id}/report). Never fails the
    command: a run without an envelope is silently skipped; anything else
    prints a WARN and returns None."""
    repo = str(ctx.paths.craftbench)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    try:
        import importlib
        bridge = importlib.import_module("tools.dashboard.web.report_bridge")
        return bridge.write_static_report(run_dir, ctx.paths.craftbench)
    except LookupError:
        return None  # no summary.json/result.json (e.g. a wedged run) — nothing to render
    except Exception as e:  # report generation must never mask the verdict
        _say(f"  WARN  report.html not generated ({e.__class__.__name__}: {e})")
        return None


def _rep_report_href(ctx: _Ctx, run_dir: Path, base_dir: Path) -> Optional[str]:
    """Backfill a rep run dir's report.html (dashboard's ONE renderer, via the
    never-raises _write_run_report) and return its href relative to
    ``base_dir`` (the bench dir, where leaderboard.html lives). None when no
    report could be produced — the leaderboard cell then renders link-free."""
    rep_html = _write_run_report(ctx, run_dir)
    if rep_html is None:
        cand = run_dir / "report.html"      # a previously-generated report still counts
        rep_html = cand if cand.is_file() else None
    if rep_html is None:
        return None
    try:
        return os.path.relpath(rep_html, base_dir).replace(os.sep, "/")
    except ValueError:                      # cross-drive on Windows — no relpath exists
        return Path(rep_html).as_uri()


def _open_in_browser(path: Path) -> None:
    """Open a local file in the user's default browser, detached; best-effort."""
    try:
        if stack.IS_WINDOWS:
            os.startfile(str(path))  # noqa — the Windows default-app opener
        else:
            import webbrowser
            webbrowser.open(path.as_uri())
    except OSError:
        pass


def _recap_run_summary(run_dir: Path) -> None:
    """Terminal recap off the run's artifacts — since 2026-08-05 this IS the
    per-rep SUMMARY CARD (aura_rig.repcard), shared verbatim by cmd_eval's
    recap and every `cb bench` rep: verdict / model / cost / time / per-layer
    status / the failing gate's evidence / the per-checkpoint measured story /
    film strip + workdir + report locations, in one aligned box.
    Defensive throughout — repcard omits fields the run does not carry, and an
    unreadable envelope prints nothing (the old recap's behavior)."""
    from aura_rig import repcard
    for line in repcard.card_for_run(run_dir):
        _say(line)


def _stop_headless_editor() -> None:
    """Kill CRAFTBENCH's headless editor(s) to release the project lock (ports
    Stop-HeadlessEditor). Scoped — kill_craftbench_editors spares foreign
    editors (e.g. the user's own dev project); a blanket
    kill_by_image("UnrealEditor") here reaped them (2026-07-23 review)."""
    stack.kill_craftbench_editors(log=_say)


def _live_run_active(ctx: _Ctx) -> bool:
    """Non-blocking probe: does a graded run hold runs/.live-run.lock right now?

    FAIL-OPEN, deliberately, per the 'absent measurement is never a verdict'
    contract envgate's ram_pct/commit_pct use verbatim: a probe that cannot
    measure (no live_lock import, an unreadable runs/ dir) returns False and the
    caller proceeds. The cost of a false False is contention (recoverable, and
    named in the logs); the cost of a false True is refusing every build on a
    box whose lockfile happens to be unreadable — a harness fault that would
    block work with no way to see why."""
    try:
        try:
            from live_lock import is_live_run_active
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from live_lock import is_live_run_active
        lock = ctx.paths.craftbench / "runs" / ".live-run.lock"
        return bool(is_live_run_active(lock))
    except Exception:  # noqa: BLE001 — a broken probe must not brick the command
        return False


def _refuse_if_live_run(ctx: _Ctx) -> bool:
    """True (and says why) when a live graded run holds runs/.live-run.lock —
    view/review kill editors to take the project lock, which mid-drive means
    killing the run's OWN editor (tokens already spent, NO_DELIVERABLE)."""
    if not _live_run_active(ctx):
        return False
    _say("FAIL  a live run is in flight (runs/.live-run.lock is held) — "
         "view/review would kill its editor mid-drive; wait for the run "
         "to finish first")
    return True


def _refuse_build_if_live_run(ctx: _Ctx, command: str) -> bool:
    """True (and says why) when a BUILD-RUNNING command was started while a
    graded bench holds runs/.live-run.lock.

    THE EXCLUSIVITY GAP (found 2026-08-07 by the maintainer who caused it):
    _refuse_if_live_run guarded only view/review, so every command that runs a
    UBT build — refgate / batch-eval / discriminate / smoke — could start
    underneath a paid drive. Both measured consequences grade as the MODEL
    failing:

      * Epic's Build.bat mutex is keyed on the ENGINE INSTALL, not the project
        (%TMP%\\<mangled Build.bat path>.lock), so the loser returns exit 1 with
        a ~138-byte log and NO compile errors — indistinguishable in report.json
        from a broken submission. One submission sha measured 3 FAIL / 2 PASS
        purely by contention. (build_lock.py serializes builds INSIDE one
        process tree; it cannot stop a second cb invocation from starting one.)
      * The concurrent cl.exe tree added ~2.4 GB of commit charge, tripped the
        in-drive floor (aura_rig/pressure.py) and aborted a paid drive with
        COMMIT-EXHAUSTED — the guard firing on the interference, not the cause.

    THE SEAM IS THE cmd_* ARM, NEVER _run_refgates: that helper is shared
    VERBATIM by `cb refgate` and `cb bench --refgates`, and a bench holds the
    lock for its own reps — refusing inside the helper would make every bench
    refuse its own pre-spend gate.

    Escape hatch, deliberate and explicit: CB_ALLOW_CONCURRENT_BUILD=1 (the
    CB_ALLOW_* convention of stack_guard/kill_guard). Fail-open probe — see
    _live_run_active."""
    if stack.env_flag("CB_ALLOW_CONCURRENT_BUILD"):
        return False
    if not _live_run_active(ctx):
        return False
    _say(f"FAIL  a live graded run holds runs/.live-run.lock — NOT starting "
         f"`cb {command}`.")
    _say("      Why: this command runs a UBT build, and Epic's Build.bat mutex "
         "is keyed on the ENGINE install, not the project. The loser exits 1 "
         "with a ~138-byte log and no compile errors, which the running bench "
         "grades as an AGENT FAIL (one sha measured 3 FAIL / 2 PASS under "
         "contention, 2026-08-07); the concurrent cl.exe tree also added "
         "~2.4 GB of commit and aborted a paid drive as COMMIT-EXHAUSTED.")
    _say("      Wait for the run to finish (`cb status` shows it), then re-run. "
         "To override anyway: CB_ALLOW_CONCURRENT_BUILD=1.")
    return True


# =========================================================================== #
# Commands (one function per cb.ps1 switch arm; SAME per-command ordering).    #
# =========================================================================== #

def cmd_up(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Bring the stack up on the substrate .uproject and gate on readiness,
    without running anything. `cb eval` does this for itself; `cb up` is for
    holding an editor across several hand-driven commands, and `cb down` is its
    pair.

    It used to carry --drive-ready, which logged the dev-browser into the
    proprietary product client so that client's in-page tool executor would
    mount and MUTATING MCP tools would actually run. That whole login is gone
    with the product lane, so there is nothing left for the flag to select.
    --restart-client went the same way (it restarted that same client);
    --restart-editor was only ever set by cut-lane callers."""
    ctx.require_stack(ctx.paths.uproject)
    # AFTER bring-up: invoke_bringup has written the manifest, so this overwrites
    # the INFERRED anchor (which is the launcher, or nothing, when cb has no
    # surviving ancestor) with the declared one. Ownership itself still transfers
    # at clean exit via release_at_exit.
    session_pid = getattr(args, "session_pid", None)
    if session_pid:
        from aura_rig import stack_guard as _sg
        _sg.adopt_session(int(session_pid), log=_say)
    _say(BAR)
    return 0


def _apply_eval_mode_env(args: argparse.Namespace) -> None:
    """Export the shared visible/capture/keep contract (CB_VISIBLE / CB_CAPTURE /
    CB_KEEP) BEFORE any editor launch or graded shell-out, so every child — the
    editor launch (stack.editor_launch_args) and run.py — inherits it. Only
    SETS on opt-in flags; absent flags leave the env untouched (an
    operator-exported var still wins). Defaults never change."""
    if getattr(args, "visible", False):
        os.environ["CB_VISIBLE"] = "1"
    if getattr(args, "capture", False):
        os.environ["CB_CAPTURE"] = "1"
    if getattr(args, "keep", False):
        os.environ["CB_KEEP"] = "1"
    if getattr(args, "keep_workdir", False):
        # Opt out of slim retention for THIS run. Distinct from --keep: --keep
        # writes runs/<run>/project-lean/, which EXCLUDES Binaries/Intermediate
        # and so cannot be rebuilt or re-run; --keep-workdir preserves the real
        # built workdir under wd_root() (~5.9 GB) that you can open, rebuild and
        # re-verify. Set-only on opt-in, so an operator-exported
        # CB_WORKDIR_RETENTION=none is not silently overridden by its absence.
        os.environ["CB_WORKDIR_RETENTION"] = "full"
    if getattr(args, "warm_cache", False):
        # Read by run.py's _verifier_workdir_args, which covers every eval
        # route on both its workspace and --live-project spines (baseline /
        # unreal-mcp).
        # It passes --warm-cache to run_task and drops the --workdir pin, which
        # run_task reads as force-cold. Prime first with `cb warm-prime`; a warm
        # MISS falls back to cold safely.
        os.environ["CB_WARM_CACHE"] = "1"


def _eval_mode_argv(args: argparse.Namespace,
                    keep_flag: str = "--keep-workspace") -> List[str]:
    """The REAL-argv form of the same contract for the run.py-based paths
    (baseline / unreal-mcp). ``--keep`` maps to run.py's existing
    ``--keep-workspace`` semantics."""
    out: List[str] = []
    if getattr(args, "visible", False):
        out.append("--visible")
    if getattr(args, "capture", False):
        out.append("--capture")
    if getattr(args, "keep", False):
        out.append(keep_flag)
    return out


def _compose_reaping(task_id: str, spec, say) -> "Path":
    """graded_scratch.compose with ONE editor-reap retry on an OSError
    refusal. A surviving prior-session editor holding scratch handles is the
    dominant cause of a compose refusal (compose REFUSES on a locked leftover
    instead of silently keeping it), and the editor restart that would clear
    it only runs later — without this, one stuck editor cascades a bench's
    every remaining rep. Non-OSError failures (malformed
    spec, unknown substrate) are deterministic and propagate immediately;
    the second failure of any kind propagates to the caller's FAIL path."""
    from aura_rig import graded_scratch
    try:
        return graded_scratch.compose(task_id, task_spec_path=spec, log=say)
    except OSError as e:
        say(f"WARN  scratch compose failed ({type(e).__name__}: {e}) — "
            f"reaping the CraftBench editor and retrying once")
        stack.ensure_editor_dead(log=say)
        return graded_scratch.compose(task_id, task_spec_path=spec, log=say)


def cmd_eval(ctx: _Ctx, args: argparse.Namespace) -> int:
    # BEFORE anything else, including the env gate: an unknown backend, or the
    # disclosed-but-unavailable aura-mcp arm, is answered in the first second
    # rather than after a task resolve and a build. See _refuse_unroutable_model.
    if _refuse_unroutable_model(args.model):
        return 2
    # Shared phase-3 contract: export CB_VISIBLE/CB_CAPTURE/CB_KEEP before ANY
    # graded run (both eval routes below shell children that read it).
    _apply_eval_mode_env(args)
    # Fast environment gate BEFORE any build/token spend — a broken env costs
    # ~2s + the exact fix here, not a 20-min build + a raw symptom.
    from aura_rig import envgate
    if not envgate.enforce(ctx, envgate.tier_for_model(args.model, _backend_of),
                           _say, skip=getattr(args, "no_preflight", False)):
        return 2
    # Task-id gate BEFORE routing: a typo'd id must die HERE (<1s, with a
    # did-you-mean), not after a full compose + stack bring-up. The C1 composer
    # tolerates a None spec (it just stages out every per-task dir), so without
    # this the first objection came from run_graded — AFTER the editor restart
    # cycle (FAILURE-LOG 2026-07-21: 'to-…' for 't0-…').
    from aura_rig import tasks as _tasks
    task_spec = _tasks.resolve_task_path(ctx.paths.craftbench, args.task)
    if task_spec is None:
        _say("FAIL  " + _tasks.resolution_error(ctx.paths.craftbench, args.task))
        return 2
    eval_started = time.time()
    # Route by backend: unreal-mcp -> the Epic-MCP editor path (one headless
    # editor, no web services); claude-p / openrouter / bare -> the generalist
    # BASELINE runner (run.py, no editor at all). aura-mcp never reaches here —
    # _refuse_unroutable_model answered it at the top.
    if _is_unreal_mcp_backend(args.model):
        rc = _cmd_eval_unreal_mcp(ctx, args)
        _maybe_eval_teardown(args, "unreal-mcp headless editor")
        return rc
    rc = _cmd_eval_baseline(ctx, args)
    _maybe_eval_teardown(args, "baseline (no-op unless a stack is up)")
    return rc


def _cmd_eval_baseline(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Graded eval for a generalist backend (claude-p / openrouter / bare).

    These backends need no editor stack at all — the agent gets Claude Code's
    own file tools. We shell out to the v0 baseline harness (run.py), which
    builds a /tmp workspace from the substrate, dispatches the agent, snapshots
    its diff, and runs the deterministic verifier. run.py wants a task SPEC PATH
    and the UE install ROOT — we resolve both off ctx (the same env resolution
    cb.discriminate / cb.batch-eval use)."""
    from aura_rig import tasks as _tasks

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    # ctx.ue is the editor BINARY; run.py wants the install ROOT (the dir with
    # Engine/). resolve_ue() exported CB_UE_ROOT to exactly that — prefer it;
    # fall back to stripping Engine/Binaries/<Plat>/UnrealEditor (same as
    # cmd_discriminate / cmd_batch_eval).
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench

    # run.py takes a task SPEC PATH; resolve the (possibly set-qualified) id.
    spec = _tasks.resolve_task_path(repo, args.task)
    if spec is None:
        _say("FAIL  " + _tasks.resolution_error(repo, args.task))
        return 2

    run_py = repo / "tools" / "run-agent" / "run.py"
    cmd: List[str] = [
        ctx.py_exe, *ctx.py_pre, str(run_py),
        "--task", str(spec),
        "--model", args.model,
        "--ue-root", ue_root,
        "--no-preflight",
        "--skip-plugins",
        # Same ceiling passthrough the unreal-mcp lane already does (see
        # below). The BASELINE lane never got it, so run.py's own 600s default
        # silently won and `--ceiling` was a no-op here — the third instance of this
        # exact bug in this file. Measured 2026-08-17: a `bare` eval printed
        # "timeout=600s" under a 900s ceiling and then ran 2199s anyway.
        "--timeout", str(args.ceiling),
        *_eval_mode_argv(args),
    ]
    _say(f"\n=== GRADED EVAL (baseline {args.model}) : {args.task} ===")
    cp = subprocess.run(cmd, cwd=str(repo))
    _say(f"\n{BAR}")
    _say(f"eval exit={cp.returncode} | newest artifacts:")
    # run.py defaults to a per-backend folder (runs/<backend>/<run_id>/).
    _show_newest_run(ctx, _backend_of(args.model), open_report=True)
    _say(BAR)
    return cp.returncode


def _cmd_eval_unreal_mcp(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Graded eval for unreal-mcp — a generalist reasoner given ONLY Epic's
    first-party in-editor MCP server (UE 5.8 ModelContextProtocol + AllToolsets),
    actuating the LIVE substrate project through the open editor.

    Mirrors _cmd_eval_aura_mcp's run.py --live-project spine, but the stack is a
    single process: a headless editor launched with -ModelContextProtocolStartServer
    (Aura plugin disabled — this is the STOCK-tooling baseline). Readiness = a
    real MCP initialize round-trip (see aura_rig.unreal_mcp_stack). Per-drive
    isolation (default ON) launches that editor fresh; --reuse-editor opts out."""
    from aura_rig import tasks as _tasks
    from aura_rig import unreal_mcp_stack as _ums

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench

    spec = _tasks.resolve_task_path(repo, args.task)
    if spec is None:
        _say("FAIL  " + _tasks.resolution_error(repo, args.task))
        return 2

    isolate = not getattr(args, "reuse_editor", False)
    if isolate:
        _say("=== per-drive isolation: launching the Epic-MCP editor fresh "
             "(initialize-gated; --reuse-editor to skip) ===")
    # Live substrate = the one the TASK declares (multi-substrate threading;
    # the default substrate keeps ctx.paths.uproject exactly as before).
    try:
        _sub_name, substrate_root, live_uproject = _live_substrate_for_spec(ctx, spec)
    except (ValueError, FileNotFoundError) as e:
        _say(f"FAIL  {e}")
        return 2
    if not _ums.ensure_unreal_mcp_editor(live_uproject, ctx.ue,
                                         fresh=isolate, log=_say):
        return 1

    # run.py's substrate-clean preflight aborts on ANY dirty tracked substrate
    # file. The --live-project spine backs up + restores the writable tree and
    # grades the live project in place, so we deliberately tolerate non-source
    # dirt (uproject plugin enablement, pre-existing Config/Content WIP) that a
    # workspace-copy lane would never see. We still
    # BLOCK on dirty Source/ files, which would contaminate the graded C++ build.
    extra_flags: List[str] = []
    import substrate_check as _sc
    dirty = _sc.check_substrate_clean(substrate_root)
    if dirty:
        dirty_paths = [
            entry.strip().split(None, 1)[-1].strip().strip('"') for entry in dirty
        ]
        blocking = [p for p in dirty_paths if "/Source/" in p.replace("\\", "/")]
        if blocking:
            _say("ERROR dirty tracked substrate SOURCE file(s) would contaminate the "
                 "graded build; refusing to auto-allow (commit/revert them):")
            for p in blocking:
                _say(f"        {p}")
            # fall through WITHOUT the flag -> run.py aborts with its detailed message.
        else:
            _say("WARN  non-source substrate dirt (uproject/Config/Content WIP) — "
                 "passing --allow-dirty-substrate for THIS run (the "
                 "--live-project spine grades in place and restores after):")
            for p in dirty_paths:
                _say(f"        {p}")
            extra_flags.append("--allow-dirty-substrate")

    run_py = repo / "tools" / "run-agent" / "run.py"
    cmd: List[str] = [
        ctx.py_exe, *ctx.py_pre, str(run_py),
        "--task", str(spec),
        "--model", args.model,
        "--ue-root", ue_root,
        "--live-project",
        "--no-preflight",
        # Ceiling passthrough — run.py's own --timeout defaults to 600s, so
        # without this `--ceiling 1800` was silently ignored on this lane. Every
        # arm must get the SAME budget or the tool-layer comparison is measuring
        # the harness's caps, not the tool layers.
        "--timeout", str(args.ceiling),
        *extra_flags,
        *_eval_mode_argv(args),
    ]
    _say(f"\n=== GRADED EVAL (unreal-mcp) : {args.task}   (model {args.model}) ===")
    cp = subprocess.run(cmd, cwd=str(repo))
    _say(f"\n{BAR}")
    _say(f"eval exit={cp.returncode} | newest artifacts:")
    _show_newest_run(ctx, _backend_of(args.model), open_report=True)
    _say(BAR)
    return cp.returncode



def _maybe_eval_teardown(args, reason):
    """--teardown for EVERY eval route that leaves shared infrastructure up.

    The flag used to sit after ONE route's return, so a mixed-model
    `for m in ...; cb eval --teardown` loop inherited exactly the ever-staler
    stack it exists to prevent (workflow finding, 2026-08-04). Baseline routes
    call it too: stop_stack on a machine with nothing up is a cheap no-op, and
    a uniform contract beats a per-route matrix nobody remembers. Today the
    thing it actually reaps is the unreal-mcp lane's resident headless editor
    and the Live Coding console holding UE's build lock."""
    if not getattr(args, "teardown", False):
        return
    _say("")
    _say(f"=== --teardown ({reason}): stopping the stack this eval used ===")
    stack.stop_stack(log=_say)










def cmd_matrix(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Run a {model} x {task} cross product through the baseline runner and
    write a leaderboard. Models = a comma-separated --model list; --task is a
    task id / set / 'set/id' (expanded like discriminate). v1 supports the
    baseline backends (claude-p / openrouter / bare); unreal-mcp is reported
    unsupported (use `cb eval`) and aura-mcp is refused outright (it is not
    reproducible from this repository). Cells run SEQUENTIALLY (each is a full
    UE build).
    All orchestration/aggregation lives in aura_rig.matrix; this arm only wires
    the per-cell run.py shell-out + env resolution."""
    import datetime as _dt
    import json as _json
    from aura_rig import matrix as mtx
    from aura_rig import discriminate as _disc
    from aura_rig import tasks as _tasks

    models_all = mtx.parse_models(args.model)
    if not models_all:
        _say("FAIL  no models — pass a comma-separated list, e.g. "
             "--model claude-p:sonnet,openrouter:openai/gpt-4o-mini")
        return 2
    aura = [m for m in models_all if _is_aura_backend(m)]
    if aura:
        _say(_AURA_MCP_UNAVAILABLE)
        return 2
    baseline = [m for m in models_all if not _is_unreal_mcp_backend(m)]
    unsupported = [m for m in models_all if _is_unreal_mcp_backend(m)]
    if unsupported:
        _say(f"NOTE  unreal-mcp models are not supported in `cb matrix` yet "
             f"(run them with `cb eval`): {', '.join(unsupported)}")
    if not baseline:
        _say("FAIL  no baseline models to run (need claude-p:* or openrouter:*)")
        return 2

    repo = ctx.paths.craftbench
    # Comma-list support (2026-08-19, for the hand-picked overnight slate):
    # each element expands exactly like discriminate's target (id / set/id /
    # set name); duplicates de-dupe preserving first position.
    task_ids: List[str] = []
    for target in [t.strip() for t in str(args.task).split(",") if t.strip()]:
        ids, err = _disc.expand_targets(repo, target)
        if err:
            _say(f"FAIL  {err}")
            return 2
        task_ids += [i for i in ids if i not in task_ids]

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE)")
        return 1
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    run_py = repo / "tools" / "run-agent" / "run.py"
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = repo / "runs" / f"matrix-{ts}"

    def _run_one(cell):
        spec = _tasks.resolve_task_path(repo, cell.task_id)
        if spec is None:
            return mtx.CellResult(cell.model, cell.task_id, verdict=None,
                                  error="task spec not found")
        cell_dir = out_dir / "cells" / f"{mtx.safe_name(cell.model)}__{mtx.safe_name(cell.task_id)}"
        cmd = [ctx.py_exe, *ctx.py_pre, str(run_py),
               "--task", str(spec), "--model", cell.model,
               "--ue-root", ue_root, "--no-preflight", "--skip-plugins",
               # The operator's --ceiling MUST reach run.py, whose own
               # --timeout default (1200 s) otherwise silently governs every
               # cell — the exact §6b hazard that manufactured seven graded
               # FAIL_NO_EDITS at exactly 20.0 min (2026-08-18). Every other
               # eval-family arm already forwards it; matrix was the one that
               # didn't (found 2026-08-19 while briefing the overnight
               # 10x10 sweep).
               "--timeout", str(args.ceiling),
               "--run-dir", str(cell_dir)]
        cp = subprocess.run(cmd, cwd=str(repo))
        found = sorted(cell_dir.glob("*/result.json"))
        if not found:
            return mtx.CellResult(cell.model, cell.task_id, verdict=None,
                                  error=f"no result.json (run.py exit {cp.returncode})")
        data = _json.loads(found[-1].read_text(encoding="utf-8"))
        agent = data.get("agent") or {}
        return mtx.CellResult(
            cell.model, cell.task_id, verdict=data.get("overall"),
            cost_usd=agent.get("cost_usd"), duration_s=agent.get("duration_s"),
            tool_use_count=agent.get("tool_use_count"))

    n = len(baseline) * len(task_ids)
    _say(f"\n=== MATRIX  {len(baseline)} model(s) x {len(task_ids)} task(s) = {n} cell(s)  ->  {out_dir} ===")
    meta = {"ue_root": ue_root, "generated_at": f"{ts} UTC"}
    agg = mtx.run(baseline, task_ids, _run_one, out_dir, log=_say, meta=meta)
    _say("")
    _say(mtx.render_markdown(agg))
    _say(f"\n{BAR}")
    _say(f"leaderboard: {out_dir / 'leaderboard.html'}  (+ leaderboard.md / .json)")
    _say(BAR)
    return 0


def _split_bench_models(models_all: List[str]):
    """Partition a parsed --model list into (baseline, unsupported).

    baseline = claude-p / openrouter / bare (run.py, no editor stack);
    unsupported = unreal-mcp, which brings up its own editor per run and is
    driven one run at a time with `cb eval`. The third partition used to be
    `product` — the aura-product CDP agent, reached by any bare Aura model key
    — and it is gone with that lane; aura-mcp never reaches here because
    cmd_bench refuses it up front."""
    baseline = [m for m in models_all if not _is_unreal_mcp_backend(m)]
    unsupported = [m for m in models_all if _is_unreal_mcp_backend(m)]
    return baseline, unsupported


def _refused_cells(baseline_models: List[str],
                   task_specs,
                   asset_task_ids: set) -> List[tuple]:
    """The (model, task) cells a release matrix must REFUSE at parse time:
    baseline backends (claude-p / openrouter — file tools, no editor) on a
    task whose deliverable is an in-editor-authored asset (derived from the
    spec's L2I declaration by tasks.asset_deliverable_task, never from id
    naming). Such a cell is a guaranteed harness-reason FAIL per the
    certified-lane contract — running it silently burns money on an
    impossible measurement. Order: task-major, matching execution order."""
    return [(m, t) for (t, _n) in task_specs if t in asset_task_ids
            for m in baseline_models]


def _refgates_apply(task_specs, opt_in: bool) -> bool:
    """Whether cmd_bench runs the per-task reference gates: ONLY under the
    explicit --refgates opt-in (any task count — an operator who typed the
    flag is honored even on a single task).

    WHY the default flipped OFF (owner decision, 2026-08-06 night): the
    automatic multi-task gate phase spent real machine-time (a full token-free
    reference grade per distinct task) at the top of EVERY bench, re-proving
    state that rarely changes between benches. The owner accepted the
    trade-off knowingly: machine certification is now an explicit, separate
    action — `cb refgate <task>` at authoring time (required when a task, its
    fixture, or the substrate changes; docs/TASK-AUTHOR-GUIDE.md) and
    `cb refgate --all` at fresh-machine setup — with per-machine gate
    certificates (aura_rig/refgate.py) making repeats self-skip. The measured
    false-FAIL incident classes that motivated auto-gating (unset L1 cap
    15/15 FAIL, Build.bat contention, commit exhaustion, …) each survive as a
    named probe in aura_rig/envgate.py rather than as prose — the internal
    failure log they were written up in is not part of this release, so the
    probes are the record now; per-run protection is envgate's job
    (the ~2s pre-spend gate every eval-family command already runs), and the
    closure doctrine keeps converting new incident classes into probes. The
    per-run reference grade was interim scaffolding and the owner retired it."""
    return bool(task_specs) and bool(opt_in)


def _run_refgates(task_ids, grade, say, skip=None, on_pass=None) -> Optional[tuple]:
    """Grade each task's committed reference TOKEN-FREE, all gates upfront,
    before ANY model spend. ``grade(task_id) -> (exit_code, output_text)``
    is injected (subprocess in production; canned in tests — no real grades).

    ``skip(task_id) -> Optional[str]`` (optional) short-circuits a task with
    the returned per-task message and NO grade — the gate-certificate
    self-skip (aura_rig/refgate.py). ``on_pass(task_id)`` (optional) fires
    after each fresh PASS — the certificate write.

    Returns None when every gate PASSed (or skipped), else (task_id,
    exit_code, evidence_lines) for the FIRST failure — fail-verbatim-and-STOP
    semantics: never improvise past a failed gate, never grade the remaining
    tasks (a reference FAIL is a harness/machine problem, not a per-task
    skip)."""
    ids = list(task_ids)
    for i, tid in enumerate(ids, 1):
        if skip is not None:
            msg = skip(tid)
            if msg:
                say(f"  refgate [{i}/{len(ids)}] {tid}: {msg}")
                continue
        say(f"  refgate [{i}/{len(ids)}] {tid}: grading the committed "
            f"reference (token-free)")
        t0 = time.time()
        try:
            rc, out = grade(tid)
        except Exception as e:  # noqa: BLE001 — a runner crash is a gate FAIL
            rc, out = None, f"refgate runner error: {e!r}"
        if rc == 0:
            say(f"    -> PASS ({time.time() - t0:.0f}s)")
            if on_pass is not None:
                on_pass(tid)
            continue
        lines = [ln for ln in (out or "").splitlines() if ln.strip()]
        evidence = [ln for ln in lines if "verdict-evidence" in ln] or lines[-8:]
        return tid, rc, evidence
    return None


def _make_reference_grader(ctx: "_Ctx", repo: Path, ue_root: str,
                           spec_by_task: dict):
    """Build the ``grade(task_id) -> (exit_code, output)`` callable
    :func:`_run_refgates` drives: ONE token-free ``run_task.py`` grade of the
    task's committed reference, in a short throwaway workdir that is slimmed
    pass-or-fail. Shared verbatim by `cb refgate` and `cb bench --refgates`
    so the two commands can never certify differently."""
    import uuid as _uuid
    from aura_rig import tasks as _tasks
    run_task_py = repo / "tools" / "verify-single" / "run_task.py"
    wd_root = cb_paths.wd_root()

    def _grade_reference(tid: str):
        spec = spec_by_task.get(tid)
        if spec is None:
            return None, f"no task spec resolved for {tid} — cannot certify"
        ref = _tasks.reference_dir(repo, tid)
        if ref is None:
            return None, (f"no committed reference for {tid} (folder-local "
                          f"reference/ or legacy tests/reference-solutions/"
                          f"<id>/) — cannot certify this task")
        wd = wd_root / f"rg{_uuid.uuid4().hex[:6]}"   # short: MAX_PATH
        try:
            cp = subprocess.run(
                [ctx.py_exe, *ctx.py_pre, str(run_task_py),
                 "--task", str(spec), "--submission", str(ref),
                 "--ue-root", ue_root, "--workdir", str(wd)],
                cwd=str(repo), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=3600)
        except subprocess.TimeoutExpired:
            return None, "refgate timed out after 3600s"
        finally:
            # smoke leg-3's pattern: nothing ever adopts this workdir, so
            # slim it pass-or-fail rather than orphan ~5.9 GB per gate.
            slim = _slim_delegate()
            if wd.is_dir() and slim is not None:
                slim(wd, log=lambda s: None)
        return cp.returncode, cp.stdout + cp.stderr

    return _grade_reference


def _run_refgates_certified(ids, spec_by_task, grade, repo: Path,
                            ue_root: str, say, *, force: bool = False):
    """Certificate-aware wrapper around :func:`_run_refgates` (the "refgate
    runs once per real change" idempotency — owner amendment 2026-08-06):

      * a task whose stored certificate still matches its content key (task
        tree sha + substrate tree sha + UE root + hostname, all committed)
        self-skips with a one-line notice — ``force`` regrades anyway;
      * a fresh PASS writes/refreshes the certificate, unless the tree is
        dirty or git identity is unavailable (then the PASS stands but is NOT
        certified, and the operator is told why);
      * a FAIL drops any stored certificate and stops the gate run.

    Returns ``(failed, stats)``: ``failed`` is :func:`_run_refgates`'s
    ``None | (task_id, exit_code, evidence)``, ``stats`` counts
    ``passed`` / ``skipped`` / ``uncertified`` task ids."""
    from aura_rig import refgate as _refgate
    store = _refgate.CertStore(repo / _refgate.CERTS_RELPATH)
    idents = {tid: _refgate.identity_for(repo, tid, spec_by_task.get(tid),
                                         ue_root) for tid in ids}
    head = _refgate.head_rev(repo)
    stats = {"passed": [], "skipped": [], "uncertified": []}

    # THE COST, BEFORE IT IS SPENT. A dirty tree cannot be certified, so refgate
    # silently stops being a cached gate and becomes a FULL RE-GRADE every single
    # run — and until 2026-08-17 the only hint was a NOTE printed after the
    # minutes were already gone. That day 2 of 4 gate runs on this box were pure
    # waste for exactly this reason (~6 min), and `--all` multiplies it by the
    # task count. Printed, never enforced: "the gate still RUNS on a dirty tree"
    # is a deliberate decision (see refgate.py's header) because you still want
    # to learn that you broke the reference.
    if not force:
        blocked = [t for t in ids if not idents[t].certifiable]
        certified = [t for t in ids
                     if idents[t].certifiable and store.valid(idents[t])]
        if blocked:
            say(f"  COST  {len(blocked)} of {len(ids)} task(s) CANNOT be "
                f"certified — each re-grades in full now and caches NOTHING, "
                f"so every future run repeats this same work:")
            for t in blocked:
                say(f"          {t}: "
                    f"{idents[t].reason or 'no git identity'}")
            say(f"        Commit or stash those paths first if you wanted the "
                f"certificate. `cb discriminate` already grades the reference "
                f"leg, so re-grading a dirty tree usually proves nothing new.")
        if certified:
            say(f"  {len(certified)} of {len(ids)} already certified on this "
                f"machine — those self-skip in seconds.")

    def _skip(tid):
        if force:
            return None
        rec = store.valid(idents[tid])
        if rec is None:
            return None
        stats["skipped"].append(tid)
        return (f"already certified {rec.get('ts')} at "
                f"{str(rec.get('substrate_rev'))[:9]} on this machine — "
                f"skipping (`cb refgate --force` regrades)")

    def _on_pass(tid):
        stats["passed"].append(tid)
        ident = idents[tid]
        if store.certify(ident, head) is None:
            stats["uncertified"].append(tid)
            say(f"    NOTE  PASS not certified — "
                f"{ident.reason or 'certificate identity unavailable'} "
                f"(this gate will run again next time)")

    failed = _run_refgates(ids, grade, say, skip=_skip, on_pass=_on_pass)
    if failed is not None:
        ident = idents.get(failed[0])
        store.invalidate(ident.task_id if ident is not None else failed[0])
    return failed, stats


def _resolve_resume_dir(args, repo: Path) -> Optional[str]:
    """Resolve `--resume [DIR]` to a bench dir path, or None when no target
    QUALIFIES — a directory holding a readable bench.json. '__latest__' takes
    the newest qualifying runs/bench-*, not the newest mtime: a stray
    `bench-resume3.out.log` FILE parked in runs/ once outran every real bench
    dir (FAILURE-LOG 2026-08-05). Shared by the plan restore (pre-parse_models)
    and the rep reuse (post), so the two can never disagree about WHICH bench
    is resumed; None means the caller must REFUSE, never start a fresh spend."""
    def _qualifies(p: Path) -> bool:
        if not p.is_dir():
            return False
        try:
            with (p / "bench.json").open("rb"):
                return True
        except OSError:
            return False
    resume_dir = getattr(args, "resume", None)
    if resume_dir == "__latest__":
        cands = sorted((p for p in (repo / "runs").glob("bench-*") if _qualifies(p)),
                       key=lambda p: p.stat().st_mtime)
        return str(cands[-1]) if cands else None
    if resume_dir and not _qualifies(Path(resume_dir)):
        return None
    return resume_dir


def _load_prior_plan(resume_dir: str) -> Optional[dict]:
    """Read the {model, task} PLAN a prior bench.json recorded, in the CLI's own
    flag syntax ('a,b' for models; 'id:reps,id2:reps2' for tasks) so it can be
    assigned straight back onto args and re-parsed by the normal path.

    Returns None when the file is missing/corrupt or carries no usable plan —
    the caller must then REFUSE, never fall through to the flag defaults."""
    import json as _json
    try:
        data = _json.loads((Path(resume_dir) / "bench.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    models = [m for m in (data.get("models") or []) if isinstance(m, str) and m]
    specs = []
    for t in (data.get("task_specs") or []):
        tid = t.get("task_id") if isinstance(t, dict) else None
        if not tid:
            continue
        reps = t.get("reps")
        specs.append(f"{tid}:{reps}" if isinstance(reps, int) and reps > 0 else str(tid))
    if not models or not specs:
        return None
    return {"model": ",".join(models), "task": ",".join(specs)}


def _load_prior_reps(bench_json: Path, bch) -> list:
    """Rehydrate a prior bench.json's per-rep rows into RepResult objects for
    --resume (only the graded ones are actually reused; see bench.run)."""
    import json as _json
    try:
        data = _json.loads(bench_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in data.get("reps", []):
        out.append(bch.RepResult(
            r.get("model"), r.get("task_id"), r.get("rep"),
            verdict=r.get("verdict"), cost_usd=r.get("cost_usd"),
            agent_s=r.get("agent_s"), verify_s=r.get("verify_s"),
            tokens_in=r.get("tokens_in"), tokens_out=r.get("tokens_out"),
            num_turns=r.get("num_turns"), tool_use_count=r.get("tool_use_count"),
            tool_names=r.get("tool_names"), run_dir=r.get("run_dir"),
            error=r.get("error"),
            # comparison fields (2026-07-23) — absent in older bench.json rows
            models_used=r.get("models_used"),
            models_mismatch=bool(r.get("models_mismatch")),
            mismatch_reason=r.get("mismatch_reason"),
            underlying_verdict=r.get("underlying_verdict"),
            substrate_revision=r.get("substrate_revision"),
            preamble_sha=r.get("preamble_sha"),
            report_href=r.get("report_href"),
            posthog_url=r.get("posthog_url"),
            thread_id=r.get("thread_id"),
            thread_reused_from=r.get("thread_reused_from")))
    return out


def cmd_bench(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Run N SEQUENTIAL repetitions of {model} x {task} and aggregate
    verdict/cost/time SPREAD -> runs/bench-<ts>/bench.{json,md}. The repetition
    sibling of `cb matrix` (one-run-per-cell by design — its grid keys on
    (model, task), so repeats would silently overwrite).

    Backends: baseline only (claude-p / openrouter / bare — per-rep run.py
    shell-out with a SHORT per-rep --run-dir and an explicit agent --timeout
    from --ceiling, which the plain baseline eval path does NOT forward).
    unreal-mcp is reported unsupported (it brings its own editor up per run —
    use `cb eval`), and aura-mcp is refused outright (not reproducible from
    this repository). The second per-rep runner used to be aura-product —
    per-rep stack bring-up + product login + run_graded --product — and it is
    gone with that lane. All loop/aggregation/rendering live in
    aura_rig.bench."""
    import datetime as _dt
    import hashlib as _hashlib
    import json as _json
    from aura_rig import bench as bch
    from aura_rig import matrix as mtx
    from aura_rig import tasks as _tasks

    # Interactive wizard (tasks -> models -> params -> confirm). Bare `cb bench`
    # in a terminal opens it — the flag defaults would otherwise silently spend
    # tokens (_DEFAULT_MODEL x t0 x 3 reps). Must run BEFORE parse_models/envgate:
    # the gate's tier depends on the models the wizard picks. Explicit --model/
    # --task, non-TTY (scripts/CI/agents), and --resume keep flag-only behavior.
    forced = bool(getattr(args, "wizard", False))
    bare = (getattr(args, "model", None) == _DEFAULT_MODEL
            and getattr(args, "task", None) == _DEFAULT_TASK
            and not getattr(args, "resume", None))
    if forced and getattr(args, "resume", None):
        _say("FAIL  --wizard and --resume are mutually exclusive (a resumed bench "
             "re-runs its own model/task plan)")
        return 2
    if forced or bare:
        if not _stdio_is_tty():
            if forced:
                _say("FAIL  --wizard needs an interactive terminal (stdin+stdout TTY)")
                return 2
            # bare + non-TTY: scripts/CI keep the classic silent-default behavior
        else:
            from aura_rig import benchwizard
            res = benchwizard.run_wizard(
                ctx.paths.craftbench,
                preset_model=(None if getattr(args, "model", None) == _DEFAULT_MODEL
                              else args.model),
                preset_task=(None if getattr(args, "task", None) == _DEFAULT_TASK
                             else args.task),
                default_ceiling=getattr(args, "ceiling", 900) or 900)
            if res is None:
                _say("bench wizard: nothing to run.")
                return 0
            args.model, args.task = res.model, res.task
            args.repeat, args.ceiling = res.repeat, res.ceiling

    # --resume restores the PLAN, not just the reps. Without this, a bare
    # `cb bench --resume` re-parsed args.model/args.task — which are still the
    # DEFAULTS (_DEFAULT_MODEL x t0 x 3) because --resume suppresses the wizard
    # at `bare` above, the one guard against silent default spend. Worse,
    # bch.run keys cached reps on (model, task_id, rep), so a resumed plan on a
    # different model matched NOTHING and the whole set re-ran, at the more
    # expensive model's prices, into the same bench dir.
    # Measured hazard: ~3x cost on an unattended resume (2026-07-25).
    # Must run BEFORE parse_models/envgate — the gate's tier depends on it.
    if getattr(args, "resume", None):
        _resume_dir = _resolve_resume_dir(args, ctx.paths.craftbench)
        if _resume_dir is None:
            # Refuse rather than start a fresh bench: a resume that resolves
            # to nothing would re-spend the whole plan into a NEW dir.
            _say("FAIL  --resume: no bench dir with a readable bench.json"
                 + (" under runs/bench-*" if args.resume == "__latest__"
                    else f" at {args.resume}")
                 + "\n      Point --resume at a bench dir holding bench.json, "
                   "or drop --resume to start a new bench.")
            return 2
        _plan = _load_prior_plan(_resume_dir)
        _gave_model = getattr(args, "model", None) != _DEFAULT_MODEL
        _gave_task = getattr(args, "task", None) != _DEFAULT_TASK
        if _plan:
            if not _gave_model:
                args.model = _plan["model"]
                _say(f"  --resume: restored models from bench.json -> {args.model}")
            if not _gave_task:
                args.task = _plan["task"]
                _say(f"  --resume: restored tasks from bench.json  -> {args.task}")
        elif not (_gave_model and _gave_task):
            # Refuse rather than fall back to the defaults: spending opus money
            # because a plan could not be read is never the safe failure mode.
            _say("FAIL  --resume: could not read the prior plan from bench.json"
                 + (f" at {_resume_dir}" if _resume_dir else "")
                 + f"\n      Re-state the plan explicitly: --model <m> --task <t> "
                   f"(defaults would silently run {_DEFAULT_MODEL} x {_DEFAULT_TASK}).")
            return 2

    _apply_eval_mode_env(args)
    models_all = mtx.parse_models(args.model)
    # Unroutable slugs die BEFORE the env gate and before a single rep: a bench
    # is hours of repeats, and the one thing worse than refusing at minute 0 is
    # refusing at minute 90.
    for _m in models_all:
        if _refuse_unroutable_model(_m):
            return 2
    # Env gate once for the whole bench, at the STRICTEST tier any model needs
    # (a bench is hours of repeats — a preflight miss here is the worst case).
    from aura_rig import envgate
    _tiers = {envgate.tier_for_model(m, _backend_of) for m in models_all}
    _tier = "baseline" if "baseline" in _tiers else "grade"
    if not envgate.enforce(ctx, _tier, _say, skip=args.no_preflight):
        return 2
    baseline, unsupported = _split_bench_models(models_all)
    if unsupported:
        _say(f"NOTE  unreal-mcp models are not supported in `cb bench` yet "
             f"(run them with `cb eval`): {', '.join(unsupported)}")
    if not baseline:
        _say("FAIL  no runnable models (need claude-p[:<m>], "
             "openrouter:<provider/m> or bare:<provider/m>)")
        return 2

    task_specs = bch.parse_task_spec(args.task, args.repeat)
    if not task_specs:
        _say("FAIL  no tasks — pass --task <id>[:reps][,<id2>[:reps]...]")
        return 2

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench
    run_py = repo / "tools" / "run-agent" / "run.py"

    # Multi-task hardening, all at PARSE TIME — before any build or token spend:
    # (1) resolve EVERY task id upfront (set-qualified preferred; bare ids
    #     resolve per tasks/README, ambiguity refused with candidates) — on a
    #     MULTI-task bench a typo'd second task must die here, not after the
    #     first task's block already spent (a single-task bench keeps the
    #     classic late, per-rep resolution error — same asymmetry as the
    #     reference gates);
    # (2) refuse impossible (model, task) cells: a baseline backend (claude-p /
    #     openrouter — file tools, no editor) on an asset-deliverable task
    #     (derived from the spec's L2I declaration, never from id naming) is a
    #     guaranteed harness-reason FAIL per the certified-lane contract, and a
    #     release matrix must not silently burn money on it.
    spec_by_task = {}
    for _tid, _n in task_specs:
        _spec = _tasks.resolve_task_path(repo, _tid)
        if _spec is None:
            if len(task_specs) > 1:
                _say("FAIL  " + _tasks.resolution_error(repo, _tid))
                return 2
            continue   # single-task: the per-rep runner reports it, as today
        spec_by_task[_tid] = _spec
    asset_tasks = {tid for tid, spec in spec_by_task.items()
                   if _tasks.asset_deliverable_task(spec)}
    refused = _refused_cells(baseline, task_specs, asset_tasks)
    if refused:
        pairs = "\n".join(f"        {m}  x  {t}" for m, t in refused)
        if not getattr(args, "allow_mismatched_cells", False):
            _say(f"FAIL  {len(refused)} impossible (model, task) cell(s) — a "
                 f"baseline backend (file tools, no editor) cannot author the "
                 f"asset deliverable an L2I task grades, so every such rep is "
                 f"a guaranteed harness-reason FAIL:\n{pairs}\n"
                 f"      Drop those models/tasks, or pass "
                 f"--run-mismatched-cells to run them anyway.")
            return 2
        _say(f"WARN  --run-mismatched-cells: running {len(refused)} "
             f"guaranteed-FAIL baseline-x-asset cell(s) anyway:\n{pairs}")
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = repo / "runs" / f"bench-{ts}"
    wd_root = cb_paths.wd_root()

    # --resume: append to an existing bench dir, reusing its graded reps.
    # (The PLAN was already restored from this same dir before parse_models.)
    prior = None
    if getattr(args, "resume", None):
        resume_dir = _resolve_resume_dir(args, repo)
        if resume_dir and (Path(resume_dir) / "bench.json").is_file():
            out_dir = Path(resume_dir)
            prior = _load_prior_reps(out_dir / "bench.json", bch)
            kept = sum(1 for r in prior if bch.is_graded_verdict(r.verdict))
            _say(f"=== RESUME: {out_dir}  ({kept} graded rep(s) kept; "
                 f"errors/non-graded re-run) ===")
        else:
            _say(f"WARN  --resume: no bench.json at {resume_dir!r}; starting fresh")

    # Pre-spend operator check: the cell matrix + per-rep anchors + ceiling.
    # cb is non-interactive — this printout IS the confirm step.
    _say("")
    _say(bch.render_cost_preview(baseline, task_specs, args.ceiling,
                                 resumed=bool(getattr(args, "resume", None))))

    # Per-task REFERENCE GATES — OPT-IN via --refgates since 2026-08-06 (the
    # owner retired the automatic multi-task gate phase; the WHY, recorded in
    # full, lives on _refgates_apply). Everything about the gates themselves —
    # token-free reference grades, fail-verbatim-and-STOP, exit 9, evidence
    # lines — is unchanged; they simply fire only when asked, and they share
    # the gate certificates `cb refgate` writes, so certified tasks self-skip.
    if getattr(args, "skip_refgates", False):
        _say("\nNOTE  --skip-refgates is DEPRECATED and now a no-op: `cb bench` "
             "no longer runs reference gates by default (opt in with "
             "--refgates; gate at authoring time with `cb refgate <task>`).")
    if _refgates_apply(task_specs, getattr(args, "refgates", False)):
        distinct = [t for t, _n in task_specs]
        _say(f"\n=== REFGATES  {len(distinct)} distinct task(s) — every "
             f"committed reference must grade PASS token-free before any "
             f"spend (valid gate certificates self-skip; `cb refgate --force` "
             f"regrades) ===")
        _grade_reference = _make_reference_grader(ctx, repo, ue_root,
                                                  spec_by_task)
        _failed, _ = _run_refgates_certified(
            distinct, spec_by_task, _grade_reference, repo, ue_root, _say)
        if _failed is not None:
            _tid, _rc, _evidence = _failed
            _say(f"\nFAIL  REFGATE {_tid}: the committed reference did not "
                 f"grade PASS (run_task exit {_rc}) — a reference FAIL is a "
                 f"harness/machine problem; NOT spending a token on this "
                 f"matrix.")
            for _ln in _evidence:
                _say(f"  | {_ln}")
            _say("      Fix the machine/task first (/craftbench-setup), then "
                 "certify it with `cb refgate <task>`.")
            return EXIT_BENCH_REFGATE_FAIL

    def _run_one_baseline(rep):
        spec = _tasks.resolve_task_path(repo, rep.task_id)
        if spec is None:
            return bch.RepResult(rep.model, rep.task_id, rep.rep, verdict=None,
                                 error="task spec not found")
        # SHORT rep dir (r<NN>-<6-char pair hash>): the deepest submission path
        # (<rep_dir>/<run_id>/submission/Source/.../Tasks/<task-id>/<file>)
        # must stay under Windows MAX_PATH — a readable
        # <model>__<task>/rep-NN nesting blew 260 chars on the OneDrive repo
        # path and killed the snapshot mkdir (WinError 206). The full
        # (model, task) identity lives in bench.json's rep rows (run_dir).
        pair_h = _hashlib.sha1(
            f"{rep.model}::{rep.task_id}".encode("utf-8")).hexdigest()[:6]
        rep_dir = out_dir / "reps" / f"r{rep.rep:02d}-{pair_h}"
        cmd = [ctx.py_exe, *ctx.py_pre, str(run_py),
               "--task", str(spec), "--model", rep.model,
               "--ue-root", ue_root, "--no-preflight", "--skip-plugins",
               "--timeout", str(args.ceiling),
               "--run-dir", str(rep_dir),
               *_eval_mode_argv(args)]
        cp = subprocess.run(cmd, cwd=str(repo))
        found = sorted(rep_dir.glob("*/result.json"))
        if not found:
            # Salvage the agent's spend even when the harness died AFTER the
            # agent leg (agent_result.json is written before snapshot/verify),
            # so an infra failure never silently drops real cost from the bench.
            err = f"no result.json (run.py exit {cp.returncode})"
            ar_found = sorted(rep_dir.glob("*/agent_result.json"))
            if ar_found:
                try:
                    a = _json.loads(ar_found[-1].read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    a = {}
                return bch.RepResult(
                    rep.model, rep.task_id, rep.rep, verdict=None,
                    cost_usd=a.get("cost_usd"), agent_s=a.get("duration_s"),
                    tokens_in=a.get("tokens_in"), tokens_out=a.get("tokens_out"),
                    num_turns=a.get("num_turns"),
                    tool_use_count=a.get("tool_use_count"),
                    tool_names=a.get("tool_names"),
                    run_dir=str(ar_found[-1].parent), error=err)
            return bch.RepResult(rep.model, rep.task_id, rep.rep, verdict=None,
                                 error=err)
        data = _json.loads(found[-1].read_text(encoding="utf-8"))
        agent = data.get("agent") or {}
        timings = data.get("timings") or {}
        verifier = data.get("verifier") or {}
        # result.json omits token totals; the sibling agent_result.json (the
        # full AgentResult) carries them.
        tokens_in = tokens_out = None
        ar = found[-1].parent / "agent_result.json"
        try:
            a = _json.loads(ar.read_text(encoding="utf-8"))
            tokens_in, tokens_out = a.get("tokens_in"), a.get("tokens_out")
        except (OSError, ValueError):
            pass
        # Per-rep summary card, BEFORE the prune below — the card's checkpoint
        # story reads the graded workdir's L2 log, which the prune deletes.
        _recap_run_summary(found[-1].parent)
        if args.prune_workdirs:
            run_id = found[-1].parent.name
            wd = wd_root / _hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:10]
            if wd.is_dir() and _robust_rmtree(wd):
                _say(f"    pruned workdir {wd}")
        verify_s = timings.get("verify_s")
        if verify_s is None and isinstance(verifier, dict):
            verify_s = verifier.get("duration_seconds")
        # Attribution + provenance for the comparison leaderboard: models_used
        # is the truth (a bare claude-p once silently ran a different model —
        # trust the envelope, never the slug); absence just means an older
        # envelope (flag_mismatch treats it as unattributed, not mismatched).
        models_used = agent.get("models_used")
        mm, mm_reason = bch.flag_mismatch(rep.model, models_used)
        return bch.RepResult(
            rep.model, rep.task_id, rep.rep, verdict=data.get("overall"),
            cost_usd=agent.get("cost_usd"),
            agent_s=timings.get("agent_s", agent.get("duration_s")),
            verify_s=verify_s,
            tokens_in=tokens_in, tokens_out=tokens_out,
            num_turns=agent.get("num_turns"),
            tool_use_count=agent.get("tool_use_count"),
            tool_names=agent.get("tool_names"),
            run_dir=str(found[-1].parent),
            models_used=models_used,
            models_mismatch=mm, mismatch_reason=mm_reason,
            substrate_revision=(verifier or {}).get("substrate_revision"),
            preamble_sha=data.get("preamble_sha"),
            report_href=_rep_report_href(ctx, found[-1].parent, out_dir))

    _run_one = _run_one_baseline
    runnable = baseline
    total = sum(n for _, n in task_specs) * len(runnable)
    plan = ", ".join(f"{t}x{n}" for t, n in task_specs)
    _say(f"\n=== BENCH  {len(runnable)} model(s) x [{plan}] = {total} rep(s), "
         f"SEQUENTIAL  ->  {out_dir} ===")
    meta = {"ue_root": ue_root, "generated_at": f"{ts} UTC",
            "agent_timeout_s": args.ceiling}

    # Execution order (see bench.build_reps): per-TASK blocks with models
    # within (a task switch invalidates the composed scratch's incremental
    # build — and can switch the substrate outright), reps of a pair
    # back-to-back. Rep identity stays (model, task, rep), so --resume matches
    # regardless of order.
    agg = bch.run(runnable, task_specs, _run_one, out_dir, log=_say, meta=meta,
                  prior=prior)
    _say("")
    _say(bch.render_markdown(agg))
    _say(f"\n{BAR}")
    _say(f"leaderboard : {out_dir / 'leaderboard.html'}  (model x task grid, per-rep report links)")
    _say(f"bench report: {out_dir / 'bench.md'}  (+ bench.json; per-rep runs under reps/)")
    _say(BAR)
    return 0


def cmd_tasks(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Interactive browser: sets -> tasks -> detail. Browsing spends nothing and needs
    # no stack; confirming a task runs it as a graded eval (dispatch + L1 + L2), i.e.
    # exactly `cb eval --task <id>`. A pre-selected --task skips straight to running it.
    from aura_rig import taskpicker
    chosen = args.task if args.task and args.task != _DEFAULT_TASK else None
    if chosen is None:
        chosen = taskpicker.pick(ctx.paths.craftbench)
    if not chosen:
        _say("no task selected.")
        return 0
    _say(f"\n>>> cb eval --task {chosen}")
    args.task = chosen
    return cmd_eval(ctx, args)


def cmd_discriminate(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Token-FREE deterministic discrimination batch: for the --task target (id, set, or set/id) re-run the FULL
    # FR-017 matrix per task (reference->PASS, empty->FAIL, each discrimination variant — folder-local
    # discrimination/ or legacy tests/discrimination/<id>/ — ->FAIL via its MATRIX.md named substring).
    # NO agent, NO stack bring-up, NO tokens — the deterministic sibling of `cb eval`.
    # All logic lives in aura_rig.discriminate (pure + mockable subprocess seam); this arm only resolves the
    # environment and prints.
    from aura_rig import discriminate as disc
    from aura_rig import envgate
    from aura_rig import tasks as _tasks

    # Exclusivity BEFORE anything else: every leg of the matrix is a UBT build,
    # and a build started under a live bench grades as that bench's model
    # failing (see _refuse_build_if_live_run). Exit 2 = the same "refused
    # before doing anything" code the envgate blocker below returns in this
    # same arm — never 1, which disc.overall_exit_code uses for a real FAIL.
    if _refuse_build_if_live_run(ctx, "discriminate"):
        return 2
    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if not envgate.enforce(ctx, "grade", _say, skip=args.no_preflight):
        return 2
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    # ctx.ue is the editor BINARY; run_task.py wants the install ROOT (the dir with Engine/). resolve_ue()
    # exported CB_UE_ROOT to exactly that, so prefer it; fall back to stripping Engine/Binaries/<Plat>/UnrealEditor.
    ue_root = Path(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench
    run_task_py = repo / "tools" / "verify-single" / "run_task.py"

    ids, err = disc.expand_targets(repo, args.task)
    if err:
        _say(f"FAIL  {err}")
        return 2

    _say(f"\n=== DISCRIMINATION (deterministic, NO tokens) : {args.task} -> {len(ids)} task(s) ===")
    if args.warm_cache:
        _say("  warm-cache ON — matrix legs build incrementally (prime with `cb warm-prime`); "
             "from-live legs run cold")
    # --keep: retain every leg's report + workdir under runs/discriminate/<task>-<ts>/
    # (per-leg subdirs; per-task subdirs when the target expanded to a set).
    keep_base: Optional[Path] = None
    if getattr(args, "keep", False):
        import datetime as _dt
        _ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        _safe_target = args.task.replace("/", "__").replace("\\", "__")
        keep_base = repo / "runs" / "discriminate" / f"{_safe_target}-{_ts}"
        _say(f"  --keep ON — leg reports + workdirs kept under {keep_base}")
    outcomes: List[disc.TaskOutcome] = []
    for tid in ids:
        spec_path = _tasks.resolve_task_path(repo, tid)
        if spec_path is None:
            outcomes.append(disc.TaskOutcome(task_id=tid, error="task spec not found"))
            continue
        legs, build_err = disc.build_legs(repo, tid)
        if build_err:
            outcomes.append(disc.TaskOutcome(task_id=tid, error=build_err))
            continue
        from_live = disc.decide_from_live(repo, tid, force_wip=args.wip)
        _say(f"  - {tid}: {len(legs)} leg(s), substrate={'live' if from_live else 'HEAD'}")
        keep_root = None
        if keep_base is not None:
            keep_root = (keep_base if len(ids) == 1
                         else keep_base / tid.replace("/", "__").replace("\\", "__"))
        runner = disc.make_run_task_runner(
            py_exe=ctx.py_exe, py_pre=ctx.py_pre, run_task_py=run_task_py,
            task_spec=spec_path, ue_root=ue_root, from_live=from_live,
            warm_cache=args.warm_cache, keep_root=keep_root,
        )
        outcomes.append(disc.run_matrix(legs, runner, tid))

    _say("\n" + BAR)
    _say(disc.render_table(outcomes))
    _say(BAR)
    return disc.overall_exit_code(outcomes)


def cmd_batch_eval(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Token-FREE parallel deterministic grading: take a folder of already-isolated
    # submission dirs (each named by its task id), pair each with its task spec,
    # and run the EXISTING verifier N-wide in parallel — each verify in its OWN
    # cold UE process, memory-gated so it stays ~2-wide on a 26 GB box.
    # `--references [all|<set>]` grades every task's OWN reference solution instead
    # (folder-local reference/ or legacy tests/reference-solutions/<id>/). NO agent,
    # NO stack bring-up, NO tokens — the batch sibling of `cb eval`.
    # All logic lives in aura_rig.batch_eval (pure + an injected verify/mem-gate seam);
    # this arm only resolves the environment and shells the cold verifies.
    from aura_rig import batch_eval
    from aura_rig import envgate

    # Exclusivity BEFORE anything else — and this arm is the worst offender of
    # the four: --verify-concurrency fans out N cold UE builds at once, so the
    # engine-keyed Build.bat mutex is contended N ways against the live bench.
    # Exit 2 (same as the envgate blocker below), never 1: 1 is this command's
    # graded-FAIL gate result (batch_eval.gate_result).
    if _refuse_build_if_live_run(ctx, "batch-eval"):
        return 2
    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if not envgate.enforce(ctx, "grade", _say, skip=args.no_preflight):
        return 2
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    references = args.references
    outputs = Path(args.outputs) if args.outputs else None
    if references is not None and outputs is not None:
        _say("FAIL  --references and an outputs folder are mutually exclusive (pick one)")
        return 2
    if references is None and (outputs is None or not outputs.is_dir()):
        _say(f"FAIL  --outputs must be a folder of submission dirs (got: {args.outputs!r}); "
             "or pass --references [all|<set>] to grade the reference solutions")
        return 2
    # ctx.ue is the editor BINARY; run_task.py wants the install ROOT (the dir with
    # Engine/). resolve_ue() exported CB_UE_ROOT to exactly that — prefer it; fall
    # back to stripping Engine/Binaries/<Plat>/UnrealEditor (same as cmd_discriminate).
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench

    target = f"--references {references}" if references is not None else str(outputs)
    _say(f"\n=== BATCH-EVAL (deterministic, NO tokens) : {target} ===")
    if args.warm_cache:
        _say("  warm-cache ON — up to --verify-concurrency slots run warm "
             "(prime with `cb warm-prime --warm-slots N`); extras fall back to cold")
    if getattr(args, "keep", False):
        _say("  --keep ON — each verify keeps its workdir (short per-task dir under "
             "CRAFTBENCH_WD_ROOT; path recorded per row; prune later with "
             "`cb clean --workdirs`)")
    summary = batch_eval.run(
        outputs,
        ue_root=ue_root,
        repo=repo,
        label=args.label,
        verify_concurrency=args.verify_concurrency,
        py_exe=ctx.py_exe,
        py_pre=ctx.py_pre,
        from_live=args.wip,
        warm_cache=args.warm_cache,
        keep_workdir=getattr(args, "keep", False),
        references=references,
        log=_say,
    )
    rate = summary.get("pass_rate")
    rate_s = f"{rate * 100:.1f}%" if rate is not None else "n/a (0 graded)"
    # A FAIL or a REJECT verdict is a legitimate GRADING outcome, NOT a harness
    # error — surface the breakdown (graded / pass / fail / reject) so a non-PASS
    # batch reads clearly. n_excluded counts the SUBSTRATE/SANDBOX-REJECT + UNPAIRED
    # + crash rows the pass-rate denominator drops.
    n_graded = summary["n_graded"]
    n_reject = summary.get("n_excluded", 0)
    # The exit code and the verdict WORDS come from one batch_eval.gate_result
    # call, so they can never drift apart. Until 2026-07-25 this arm graded
    # HARNESS success only — exit 1 iff nothing graded, exit 0 even when every
    # single verdict was FAIL — which let `cb batch-eval --references all` print
    # "0/15 graded PASS (0.0%)" and still exit 0. README.md sells this command as
    # the all-references regression gate (15/15 at the time); a gate that greens a total wipeout gates
    # nothing, so a graded FAIL is now a real failure (exit 1, matching the
    # 2=usage/1=failure ladder cmd_discriminate uses).
    # `--no-gate` (dest allow_fail — it was spelled `--allow-fail` until the
    # 2026-07-25 prefix collision; see the SPELLING IS LOAD-BEARING note at its
    # add_argument) restores the old harness-only reading for the measurement
    # use (grading a folder of agent outputs, where FAILs are the data) — no
    # in-tree caller needed it at the time of the fix (surveyed: no CI workflow,
    # no script, and `cb smoke` shells run_task.py directly, never batch-eval).
    code, verdict = batch_eval.gate_result(
        summary, allow_fail=getattr(args, "allow_fail", False))
    _say("\n" + BAR)
    _say(f"batch-eval: {summary['n_pass']}/{n_graded} graded PASS "
         f"({rate_s}); graded={n_graded} pass={summary['n_pass']} "
         f"fail={summary['n_fail']} reject/excluded={n_reject} "
         f"{summary['excluded_by_verdict']}")
    _say(f"batch-eval: {verdict}  (exit {code})")
    _say(BAR)
    if code != 0 and n_graded == 0:
        _say("  WARNING  0 submissions graded (verifier produced no verdict — "
             "harness/setup failure, not a task FAIL)")
    return code


def cmd_refgate(ctx: _Ctx, args: argparse.Namespace) -> int:
    # THE authoring-time gate action (owner decision 2026-08-06): grade the
    # named tasks' committed references token-free — `cb refgate <task>[,...]`
    # when authoring/changing a task, its fixture, or the substrate; `cb
    # refgate --all` as the full committed-reference sweep (fresh machines,
    # after pulls). Reference gating lives HERE and at setup (`cb smoke` /
    # `cb refgate --all`), not inside every bench: per-run environment
    # protection is envgate's ~2s job, and gate CERTIFICATES
    # (aura_rig/refgate.py) make repeat invocations self-skip until the task
    # tree, substrate tree, UE root, or machine actually changes ("refgate
    # runs once per real change"). Exit 0 all-pass / 9 any-fail — the same
    # distinct code `cb bench --refgates` aborts with, so wrappers read one
    # gate-fail signal from both surfaces.
    from aura_rig import envgate
    from aura_rig import tasks as _tasks

    # Exclusivity BEFORE anything else. THE SEAM IS HERE, in the CLI arm, and
    # NOT in _run_refgates / _run_refgates_certified / _make_reference_grader:
    # those three are shared VERBATIM with `cb bench --refgates`, and a bench
    # holds runs/.live-run.lock for its own reps — refusing down there would
    # make every bench refuse its own pre-spend gate. Exit 2 (the envgate
    # blocker's code below), never 9: 9 means a committed reference FAILED its
    # gate, and no reference was graded here.
    if _refuse_build_if_live_run(ctx, "refgate"):
        return 2
    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if not envgate.enforce(ctx, "grade", _say, skip=args.no_preflight):
        return 2
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench

    listed = (args.outputs or "").strip()
    if getattr(args, "refgate_all", False):
        if listed:
            _say("FAIL  give a task list OR --all, not both")
            return 2
        # --all = the full committed-reference sweep: SAME discovery as
        # `cb batch-eval --references all` (batch_eval.
        # discover_reference_submissions — folder-local reference/ first,
        # legacy tests/reference-solutions/<id>/ fallback), so the two
        # commands can never disagree about what "every reference" means.
        from aura_rig import batch_eval as _batch_eval
        subs = _batch_eval.discover_reference_submissions(repo)
        ids = [s.task_id for s in subs]
        spec_by_task = {s.task_id: s.task_spec for s in subs}
        if not ids:
            _say("FAIL  --all: no committed reference solutions discovered under tasks/")
            return 2
    else:
        if not listed:
            _say("FAIL  nothing to gate — `cb refgate <task>[,<task>...]` or "
                 "`cb refgate --all` (see `cb help refgate`)")
            return 2
        ids, spec_by_task = [], {}
        for tid in [t.strip() for t in listed.split(",") if t.strip()]:
            if tid in spec_by_task:
                continue
            spec = _tasks.resolve_task_path(repo, tid)
            if spec is None:
                _say("FAIL  " + _tasks.resolution_error(repo, tid))
                return 2
            ids.append(tid)
            spec_by_task[tid] = spec

    _say(f"\n=== REFGATE  {len(ids)} task(s) — every committed reference "
         f"must grade PASS token-free (valid gate certificates self-skip; "
         f"--force regrades) ===")
    grade = _make_reference_grader(ctx, repo, ue_root, spec_by_task)
    failed, stats = _run_refgates_certified(
        ids, spec_by_task, grade, repo, ue_root, _say,
        force=bool(getattr(args, "force", False)))
    if failed is not None:
        tid, rc, evidence = failed
        _say(f"\nFAIL  REFGATE {tid}: the committed reference did not grade "
             f"PASS (run_task exit {rc}) — a reference FAIL is a harness/"
             f"machine/task problem, never a model's.")
        for ln in evidence:
            _say(f"  | {ln}")
        n_ok = len(stats["passed"]) + len(stats["skipped"])
        _say("\n" + BAR)
        _say(f"refgate: FAIL — {tid} did not certify ({n_ok} gate(s) OK "
             f"before it; {max(0, len(ids) - n_ok - 1)} not graded)  "
             f"(exit {EXIT_BENCH_REFGATE_FAIL})")
        _say(BAR)
        return EXIT_BENCH_REFGATE_FAIL
    parts = [f"{len(stats['passed'])} graded PASS"]
    if stats["skipped"]:
        parts.append(f"{len(stats['skipped'])} already certified (skipped)")
    if stats["uncertified"]:
        parts.append(f"{len(stats['uncertified'])} PASS but NOT certified "
                     f"(dirty tree / no git identity)")
    _say("\n" + BAR)
    _say(f"refgate: {len(ids)}/{len(ids)} gate(s) OK — " + ", ".join(parts)
         + "  (exit 0)")
    _say(BAR)
    return 0


def cmd_warm_prime(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Prime the L1 warm-build POOL: one cold build per slot, kept at a STABLE path
    # so cold verifies (cb batch-eval --warm-cache, run_task --warm-cache) build
    # INCREMENTALLY (~6x L1) instead of from scratch. N slots let N concurrent
    # verifies all run warm — match --warm-slots to your batch-eval
    # --verify-concurrency. ~2 min + ~5 GB disk per slot. No tokens, no stack.
    from aura_rig import tasks as _tasks

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT, or install UE 5.8)")
        return 1
    ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
    repo = ctx.paths.craftbench
    prime_py = repo / "tools" / "verify-single" / "build_warm_baseline.py"
    n = max(1, int(args.warm_slots))

    cmd: List[str] = [ctx.py_exe, *ctx.py_pre, str(prime_py),
                      "--ue-root", ue_root, "--slots", str(n)]
    # Substrate from --task when the user named a specific one, else the pinned template.
    if args.task and args.task != _DEFAULT_TASK:
        spec = _tasks.resolve_task_path(repo, args.task)
        cmd += ["--task", str(spec)] if spec else ["--task", args.task]
    else:
        cmd += ["--substrate", "CraftBenchTemplate"]
    if args.force:
        cmd.append("--force")

    _say(f"\n=== WARM-PRIME ({n} slot(s)) — one cold build per slot (~2 min each), "
         f"~5 GB disk each ===")
    if os.name == "nt" and not os.environ.get("CB_WARM_CACHE_DIR"):
        # A slot is the UE project path AND the -ReportExportPath parent, so it
        # carries the MAX_PATH risk a short --workdir exists to dodge. Re-prime,
        # not just re-set: UBT's cache is path-bound, so the primer and the
        # verifier reading two spellings throws the warm build away.
        _say("  note: pooling under %LOCALAPPDATA%\\CraftBench\\warm-baseline "
             "(79 chars to a slot; 221 of 260 used by the deepest build path). "
             "Set CB_WARM_CACHE_DIR=C:\\cb\\warm in .env and re-prime for the "
             "MAX_PATH headroom a normal workdir gets.")
    cp = subprocess.run(cmd, cwd=str(repo))
    _say(BAR)
    return cp.returncode


#: The per-arm run tracks `cb review --latest` searches. run.py writes
#: runs/<backend>/<run_id>/, one directory per arm; the aggregate tracks
#: (bench-*, matrix-*, batch-*, discriminate) never hold a single run's agent
#: output and are deliberately absent. aura-mcp is listed because a run
#: recorded on a machine that HAD the proprietary stack is still reviewable
#: here — reviewing an artifact needs none of the machinery that produced it.
_DELIVERABLE_TRACKS = ("claude-p", "unreal-mcp", "aura-mcp", "openrouter",
                       "bare")


def _newest_run_with_deliverable(ctx: _Ctx) -> Optional[Path]:
    """The most recent run dir (by mtime) under any per-arm track that carries
    a deliverable/ — the target of ``cb review --latest``."""
    roots = [ctx.paths.craftbench / "runs" / t for t in _DELIVERABLE_TRACKS]
    cands: List[Path] = []
    for root in roots:
        try:
            cands += [p for p in root.iterdir()
                      if p.is_dir() and _run_submission_dir(p) is not None]
        except OSError:
            pass
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def _run_submission_dir(run_dir: Path) -> Optional[Path]:
    """The run's agent-authored tree, whichever name this run used.

    ``run.py`` stages into ``submission/``. Older graded runs (and the
    live-project lane that is not part of this release) named the same tree
    ``deliverable/``. Looking for only one name made ``cb review`` and
    ``cb view --run`` silently find nothing on every run this build writes.
    ``dashboard/web/report_bridge.py`` already resolved both; this is the
    same rule so the two cannot drift apart again."""
    for name in ("submission", "deliverable"):
        cand = run_dir / name
        if cand.is_dir():
            return cand
    return None


def _overlay_deliverable(deliv: Path, view_dir: Path) -> List[str]:
    """Copy a run's deliverable/ tree over ``view_dir`` (mirror of the old
    Copy-Item -Recurse -Force). Returns the sorted view_dir-relative paths."""
    copied: List[str] = []
    for root, _dirs, files in os.walk(deliv):
        rel = Path(root).relative_to(deliv)
        target_dir = view_dir / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, target_dir / f)
            copied.append((rel / f).as_posix())
    return sorted(copied)


def _heal_msys_map(value: str) -> str:
    """Undo git-bash (MSYS) argument mangling of a /Game/... --map value:
    MSYS grafts its install root onto any leading-slash argument, so
    /Game/t0-x/L_X arrives as C:/Program Files/Git/Game/t0-x/L_X and the
    editor opens the wrong world (FAILURE-LOG 2026-07-23)."""
    v = str(value)
    if not v or v.startswith("/"):
        return v
    norm = v.replace("\\", "/")
    # drive-letter absolute (C:/...) with a /Game/ (or /Engine/) mount inside
    if len(norm) > 2 and norm[1] == ":":
        for mount in ("/Game/", "/Engine/"):
            i = norm.find(mount)
            if i > 0:
                return norm[i:]
    return v


def _resolve_map_arg(view_dir: Path, name: str) -> str:
    """Turn a --map value into the /Game/... package path the editor CLI
    takes. An MSYS-mangled value is healed back first (then passes through
    as a full package path); full package paths pass through; a bare map
    name is located under Content/Maps/** (per-task-foldered maps live at
    Content/Maps/<task-id>/L_<Map>.umap), falling back to the legacy flat
    /Game/Maps/<name>."""
    if not name:
        return ""
    name = _heal_msys_map(name)
    if name.startswith("/"):
        return name
    stem = name[:-len(".umap")] if name.endswith(".umap") else name
    maps_root = view_dir / "Content" / "Maps"
    if maps_root.is_dir():
        try:
            hits = sorted(maps_root.rglob(f"{stem}.umap"))
        except (NotImplementedError, ValueError):
            # a still-absolute stem (no /Game/ mount to heal to) is a
            # non-relative rglob pattern — treat it as a miss, never crash
            hits = []
        if hits:
            rel = hits[0].relative_to(view_dir / "Content").as_posix()
            return "/Game/" + rel[:-len(".umap")]
    return f"/Game/Maps/{stem}"


def _graded_task_map(scratch: Path) -> str:
    """The composed task's map as a /Game/... package path, resolved from the
    graded scratch's .cb-staged marker: the per-task map folder first
    (Content/Maps/<task-id>/*.umap — the authoring convention), then the
    marker's kept root maps (pre-migration flat tasks; the shared
    L_RenderProbe is infra, never the task map). '' when undeterminable —
    the editor then opens its default level."""
    from aura_rig import graded_scratch
    marker = graded_scratch.staged_marker(scratch) or {}
    task_id = marker.get("task_id") or ""
    if task_id:
        folder = scratch / "Content" / "Maps" / task_id
        if folder.is_dir():
            umaps = sorted(folder.glob("*.umap"))
            if umaps:
                return f"/Game/Maps/{task_id}/{umaps[0].stem}"
    kept = [m for m in (marker.get("root_maps_kept") or [])
            if m != "L_RenderProbe"]
    if len(kept) == 1:
        return f"/Game/Maps/{kept[0]}"
    return ""


def _launch_windowed_editor(ctx: _Ctx, view_dir: Path, uproj: Path,
                            map_name: str = "") -> None:
    """A WINDOWED editor (no -RenderOffScreen / -unattended): launch detached so
    the CLI returns immediately, like Start-Process ... | Out-Null."""
    eargs = [str(ctx.ue), str(uproj)]
    if map_name:
        # Already-resolved /Game/... package paths pass through (foldered maps
        # need their per-task prefix); bare names keep the legacy flat form.
        eargs.append(map_name if map_name.startswith("/")
                     else f"/Game/Maps/{map_name}")
    if stack.IS_WINDOWS:
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        subprocess.Popen(eargs, cwd=str(view_dir), creationflags=creationflags,
                         stdin=subprocess.DEVNULL)
    else:
        subprocess.Popen(eargs, cwd=str(view_dir), start_new_session=True,
                         stdin=subprocess.DEVNULL)


def cmd_view(ctx: _Ctx, args: argparse.Namespace) -> int:
    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT)")
        return 1
    if _refuse_if_live_run(ctx):
        return 1
    # --project wins; else --run (a GRADED deliverable) overlays onto the template;
    # else --graded targets the graded-eval scratch (what `cb eval` leaves dirty);
    # else the scratch PLAYGROUND (`cb review` / `cb clean` create it), falling
    # back to the graded scratch when no playground exists — which is now the
    # common state, since nothing populates the playground automatically.
    from aura_rig import graded_scratch
    graded_dir = graded_scratch.get_graded_project_dir()
    on_graded = False
    if args.project:
        view_dir = Path(args.project)
    elif args.run:
        view_dir = ctx.paths.template_dir
    elif getattr(args, "graded", False):
        view_dir, on_graded = graded_dir, True
    else:
        view_dir = stack.get_drive_project_dir("")
        try:
            stack.find_uproject(view_dir)
        except FileNotFoundError:
            try:
                stack.find_uproject(graded_dir)
            except FileNotFoundError:
                pass
            else:
                _say(f"info: no scratch playground — opening the GRADED scratch ({graded_dir})")
                view_dir, on_graded = graded_dir, True
    try:
        uproj = stack.find_uproject(view_dir)
    except FileNotFoundError:
        _say(f"FAIL  no project at {view_dir}")
        if getattr(args, "graded", False):
            _say("      (no graded scratch yet - run 'cb eval --task <id>' first)")
        elif not args.project and not args.run:
            _say("      (no scratch playground yet - `cb review <run-dir>` "
                 "or `cb clean` creates one)")
        return 1

    # Map to open: an explicit --map resolves through the project's Content/Maps
    # tree (per-task-foldered maps included); on the graded scratch the composed
    # task's own map is the default.
    map_path = _resolve_map_arg(view_dir, args.map) if args.map else ""
    if not map_path and on_graded:
        map_path = _graded_task_map(view_dir)
        if map_path:
            _say(f"  -> composed task map: {map_path}")

    if args.run:
        deliv = _run_submission_dir(Path(args.run))
        if deliv is not None:
            _say(f"Overlaying {deliv.name}/ from {args.run} onto {view_dir} (git checkout to revert)...")
            _overlay_deliverable(deliv, view_dir)
        else:
            _say(f"WARN  no submission/ or deliverable/ under {args.run}; "
                 f"opening the project as-is")

    _say("Stopping the headless editor (releasing the project lock)...")
    _stop_headless_editor()
    time.sleep(3)

    _say(f"Opening WINDOWED editor on: {view_dir}")
    _say("  -> Press Play (PIE) to see runtime behavior (spawns, timers, logs).")
    _say("  -> The editor offers to rebuild changed C++ on open; accept it.")
    _say("  -> Close the editor when done (then 'cb.py up' to run again).")
    _launch_windowed_editor(ctx, view_dir, uproj, map_path)
    return 0


def cmd_reliability(ctx: _Ctx, args: argparse.Namespace) -> int:
    """``cb reliability <bench-dir>`` — adjudicate a repeated bench.

    Answers the owner's third criterion, which a pass rate structurally cannot:
    *5 back-to-back, the harness does not break, and the results are
    consistent.* Writes ``reliability.md`` next to ``bench.json`` and prints it.

    Exit 1 when the set does NOT meet the bar — so it can gate a handoff instead
    of merely describing one. Token-free: pure JSON already on disk."""
    from aura_rig import reliability
    target = (args.outputs or "").strip()
    if not target:
        print("usage: cb reliability <bench-dir>            "
              "(the dir holding bench.json)")
        return 2
    d = Path(target)
    if not (d / "bench.json").exists():
        print(f"!! no bench.json under {d} — point at a bench dir "
              "(runs/bench-<ts>/), not a single run")
        return 2
    text, a = reliability.report(d)
    try:
        (d / "reliability.md").write_text(text, encoding="utf-8")
    except OSError:
        pass  # printing it is the deliverable; the file is a convenience
    print(text)
    return 0 if a["reliable"] else 1


def _review_run_task_id(run_dir: Path) -> Optional[str]:
    """The task id a run graded, or None.

    Three sources, most authoritative first, because runs are not uniform: an
    eval embeds the verifier report in summary.json/result.json, while a
    freeform UNGRADED drive (the runs/aura-drive/ track, produced by a command
    that is not part of this release) has no task at all and must resolve to
    None rather than to a guess. `cb review` still reads such a run dir, so the
    None branch is live even though nothing here can write a new one.
    """
    import json as _json
    for name in ("summary.json", "result.json"):
        try:
            data = _json.loads((run_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        for holder in (data.get("verifier"), data):
            if isinstance(holder, dict) and holder.get("task_id"):
                return str(holder["task_id"])
    return None


def _review_substrate_content(ctx: _Ctx, run_dir: Path) -> Optional[Path]:
    """``UE-projects/<substrate>/Content`` for the run under review, or None.

    None means UNKNOWN, and the caller must then skip the reset entirely — the
    bug this exists to prevent was resetting from the wrong substrate, which
    deletes the other substrate's player rig.

    The run dir NAME is a deliberate fallback (`bp-g2__gp-glide-stamina-bp-2026…`
    carries the id) because older runs predate the embedded verifier report.
    """
    import sys as _sys
    task_id = _review_run_task_id(run_dir)
    if not task_id:
        # Fallback: the longest known task id that appears in the dir name.
        # Longest-first so `gp-poison-dot-stack-bp` is not shadowed by a shorter
        # id that is a substring of it.
        try:
            from aura_rig import tasks as _tasks
            known = sorted(_tasks.known_task_ids(ctx.paths.craftbench),
                           key=len, reverse=True)
        except Exception:  # noqa: BLE001
            known = []
        name = run_dir.name
        task_id = next((t for t in known if t.split("/")[-1] in name), None)
    if not task_id:
        return None

    verify_dir = ctx.paths.craftbench / "tools" / "verify-single"
    if str(verify_dir) not in _sys.path:
        _sys.path.insert(0, str(verify_dir))
    try:
        from aura_rig import tasks as _tasks
        spec_path = _tasks.resolve_task_path(ctx.paths.craftbench, task_id)
        if spec_path is None:
            return None
        from spec import parse_task_file as _parse       # type: ignore
        from run_task import _substrate_dir_name as _dirname  # type: ignore
        spec = _parse(spec_path)
        sub = _dirname(str(spec.substrate or ""))
    except Exception:  # noqa: BLE001
        return None
    if not sub:
        return None
    return ctx.paths.craftbench / "UE-projects" / sub / "Content"


def cmd_review(ctx: _Ctx, args: argparse.Namespace) -> int:
    """``cb review <run-dir>`` — overlay the run's deliverable/ onto the SCRATCH
    playground project (stack.get_drive_project_dir — NEVER the benchmark
    template), print the run's artifacts + deliverable file list, and open a
    WINDOWED editor on the scratch to inspect/PIE the result."""
    import json as _json

    if ctx.ue is None:
        _say("FAIL  UnrealEditor not found (set --ue-root / CB_UE_ROOT)")
        return 1
    if _refuse_if_live_run(ctx):
        return 1
    run_arg = args.outputs or args.run
    if getattr(args, "latest", False) and not run_arg:
        run_dir = _newest_run_with_deliverable(ctx)
        if run_dir is None:
            _say("FAIL  --latest: no run with a deliverable/ under "
                 "runs/<arm>/ yet (" + ", ".join(_DELIVERABLE_TRACKS) + ")")
            return 2
        _say(f"--latest -> newest run: {run_dir}")
    elif not run_arg:
        _say("FAIL  usage: cb review <run-dir>   (or  cb review --latest)")
        return 2
    else:
        run_dir = Path(run_arg)
    if not run_dir.is_dir():
        _say(f"FAIL  run dir not found: {run_dir}")
        return 2

    # The SCRATCH playground (the same project view/headless use) — the
    # benchmark template stays untouched.
    drive_proj = stack.get_drive_project_dir(args.project or "")
    if not stack.initialize_drive_project(drive_proj, ctx.paths, log=_say):
        _say(f"FAIL  could not prepare playground: {drive_proj}")
        return 1
    try:
        uproj = stack.find_uproject(drive_proj)
    except FileNotFoundError as e:
        _say(f"FAIL  {e}")
        return 1

    deliv = _run_submission_dir(run_dir) or (run_dir / "submission")
    # Reset the scratch Content to THIS RUN'S SUBSTRATE first, so review shows
    # ONLY this run's deliverable — not an accumulation of every prior
    # review/drive. Before this, opening run A showed leftovers from B and C
    # (and, since every "world" drive saved to the same /Game/DriveWorlds/
    # L_DriveWorld path, an ambiguous world). --keep opts out (overlay onto
    # whatever's there, e.g. to compare).
    #
    # THE SUBSTRATE MUST MATCH THE RUN, and until 2026-08-15 it did not: this
    # used `ctx.paths.template_dir`, which stack.py hard-codes to
    # CraftBenchTemplate. Reviewing any of the 43 ThirdPerson tasks therefore
    # mirrored CraftBenchTemplate's Content over the scratch with
    # delete_extras=True — DELETING BP_ThirdPersonCharacter, the player
    # controller and IMC_Default, i.e. destroying exactly the player rig that
    # makes the review playable at all. `template_dir` itself is deliberately
    # NOT changed: doctor and the .uproject path both key off it.
    if not getattr(args, "keep", False):
        sub_content = _review_substrate_content(ctx, run_dir)
        if sub_content is None:
            # FAIL SAFE. An unresolvable substrate used to mean "reset from
            # CraftBenchTemplate anyway", which is the destructive case. Skipping
            # the reset only risks showing stale content from a previous review —
            # visible, and undone by re-running with a resolvable run.
            _say("Skipping the scratch reset: could not tell which substrate this "
                 "run used (no verifier.task_id in summary/result, and the run dir "
                 "name matches no task). Content may include earlier leftovers.")
        elif sub_content.is_dir():
            _say(f"Resetting scratch Content to {sub_content.parent.name} "
                 f"(clean sheet for this run)...")
            stack._mirror_tree(sub_content, drive_proj / "Content",
                               delete_extras=True)
    copied: List[str] = []
    if deliv.is_dir():
        _say(f"Overlaying deliverable from {run_dir} onto the SCRATCH {drive_proj} ...")
        copied = _overlay_deliverable(deliv, drive_proj)
    else:
        _say(f"WARN  no deliverable/ under {run_dir}; opening the scratch as-is")

    _say("\ndeliverable files:")
    for rel in copied:
        _say(f"  ~ {rel}")
    if not copied:
        _say("  (none)")

    # summary.json's artifacts (run_dir-relative — e.g. --capture screenshots).
    arts: List[str] = []
    sj = run_dir / "summary.json"
    if sj.exists():
        try:
            arts = (_json.loads(sj.read_text(encoding="utf-8", errors="replace"))
                    or {}).get("artifacts") or []
        except ValueError:
            arts = []
    _say("artifacts (summary.json):")
    for rel in arts:
        _say(f"  * {run_dir / rel}")
    if not arts:
        _say("  (none)")

    # Auto-open the run's own world map when the deliverable saved one (a
    # "world" drive ships Content/.../<L_X>.umap). Without this the editor
    # opened at the empty default map and a world run looked EMPTY even though
    # its level sat unopened in the content browser. Explicit --map wins.
    open_map = args.map
    if not open_map:
        umaps = [c for c in copied if c.lower().endswith(".umap")]
        umaps.sort(key=lambda c: ("driveworld" not in c.lower(), c))
        if umaps and umaps[0].startswith("Content/"):
            open_map = "/Game/" + umaps[0][len("Content/"):-len(".umap")]
            _say(f"  auto-opening the run's world map: {open_map}")

    _say("\nStopping the headless editor (releasing the project lock)...")
    _stop_headless_editor()
    time.sleep(3)
    _say(f"Opening WINDOWED editor on: {drive_proj}"
         + (f"  (map {open_map})" if open_map else ""))
    _say("  -> Press Play (PIE) to see the graded behavior; close it when done.")
    _launch_windowed_editor(ctx, drive_proj, uproj, open_map)
    return 0


def _norm_path(p) -> str:
    """Comparable path form (case-folded on Windows, separators normalized)."""
    return os.path.normcase(os.path.normpath(str(p)))


def _under_wd_root(p) -> bool:
    """True iff ``p`` is a STRICT descendant of the resolved machine wd-root.

    The containment gate for every destructive path this CLI is HANDED rather than
    derives itself (``bench --prune-workdirs`` reads its target out of a
    summary.json). STRICT on purpose: ``wd_root()`` is the POOL, so handing the root
    itself to a deleter takes out every other run's workdir — and under
    ``CB_WARM_CACHE=1`` the shared warm slot too — in one call.

    Both sides are ``.resolve()``d first, and that is load-bearing rather than
    tidy: this host reports ``%TEMP%`` as ``C:\\Users\\SHORT~1\\AppData\\...``, and
    that short-vs-long spelling mismatch is the FAILURE-LOG 2026-07-25 0/15
    signature. Compared unresolved, an in-root workdir reads as "outside" and the
    refusal fires on exactly the wrong side. An unresolvable wd-root refuses
    everything rather than raising — a broken CB_ROOT must not turn into a delete."""
    try:
        root = Path(cb_paths.wd_root()).resolve()
        child = Path(p).resolve()
    except (OSError, ValueError, TypeError):
        return False
    return child != root and child.is_relative_to(root)


def _referenced_workdirs(repo: Path, exclude_under=()) -> set:
    """Every ``graded_workdir`` any runs/**/summary.json OR result.json still
    points at — the KEEP set for ``cb clean --workdirs``. Baseline runs
    (run.py::_write_result) record their pinned Windows workdir in result.json
    only, so both file names must contribute refs. ``exclude_under`` drops the
    refs contributed by records under those dirs (the combined --runs
    --workdirs --check preview: those runs WOULD be deleted first, releasing
    their refs)."""
    import json as _json
    refs = set()
    runs = repo / "runs"
    if not runs.is_dir():
        return refs
    ex = [_norm_path(p) for p in exclude_under]
    for pattern in ("**/summary.json", "**/result.json"):
        for sj in runs.glob(pattern):
            sp = _norm_path(sj)
            if any(sp == e or sp.startswith(e + os.sep) for e in ex):
                continue
            try:
                data = _json.loads(sj.read_text(encoding="utf-8",
                                                errors="replace"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            gw = data.get("graded_workdir")
            if gw:
                refs.add(_norm_path(gw))
            # batch-eval --keep records per-row workdirs NESTED at
            # results[].workdir (never at the top level) — protect those too.
            for row in data.get("results") or []:
                wd = row.get("workdir") if isinstance(row, dict) else None
                if wd:
                    refs.add(_norm_path(wd))
    return refs


def _robust_rmtree(path, *, retries: int = 6, base_delay: float = 0.5) -> bool:
    """rmtree that tolerates the transient Windows lock a lingering L2-editor handle
    leaves on a workdir file (the ".umap ... being used by another process" WinError
    32). Retries with backoff, then a non-raising sweep. Returns True iff gone. This is
    the harness-local twin of tools/verify-single/fs_cleanup.robust_rmtree (a separate
    package, so the ~15 lines are duplicated rather than cross-imported)."""
    import os as _os
    import time as _time
    p = str(path)
    # A FILE (or a symlink/junction) is not an rmtree job: shutil.rmtree raises
    # NotADirectoryError, which IS an OSError, so the loop below would swallow it,
    # burn all 6 attempts of backoff (~9.5 s), then "degrade" to an
    # ignore_errors=True sweep that is a no-op on a file and report PARTIAL. Against
    # the 1814 leaked cb-aura-driver-*.json temp files measured on this box
    # (2026-07-25) that is ~4.8 HOURS spent deleting nothing. os.unlink is the whole
    # fix; its own OSError is handled exactly like the tree case (retry-free, since a
    # single unlink has no partial state to retry into) — never raise, report by
    # existence.
    if _os.path.isfile(p) or _os.path.islink(p):
        try:
            _os.unlink(p)
        except OSError:
            # A DIRECTORY symlink/junction unlinks via rmdir on Windows (os.unlink
            # raises PermissionError on one). Neither call ever follows the link, so
            # the target tree is untouched whichever one lands.
            try:
                _os.rmdir(p)
            except OSError:
                pass
        return not _os.path.lexists(p)
    for attempt in range(retries):
        if not _os.path.exists(p):
            return True
        try:
            shutil.rmtree(p)
            return True
        except OSError:
            _time.sleep(min(base_delay * (2 ** attempt), 3.0))
    shutil.rmtree(p, ignore_errors=True)  # last resort — never raise
    return not _os.path.exists(p)


def _prune_bench_workdir(graded_workdir, *, log=_say) -> bool:
    """Delete ONE rep's verifier workdir for ``bench --prune-workdirs``. True iff it
    is gone.

    Unlike every other deletion in this file, the target is a path summary.json
    HANDED us rather than one we derived — and it is not always a per-rep workdir.
    Under ``CB_WARM_CACHE=1`` the verifier grades INSIDE a shared warm slot, so
    ``graded_workdir`` can name the pool every later rep reuses; rmtree'ing that
    mid-bench silently destroys the 5x L1 speed-up for every remaining rep (and
    nothing stops a hand-edited summary.json naming something else entirely). Hence
    the wd-root containment gate, and hence the refusal is LOUD: a silent skip here
    reads as "the prune worked" while the disk keeps filling."""
    wd = Path(graded_workdir)
    if not _under_wd_root(wd):
        log(f"    !! REFUSED to prune {wd} — it does not resolve under the wd-root "
            f"({cb_paths.wd_root()}); under CB_WARM_CACHE=1 that path can BE the "
            f"shared warm-cache pool")
        return False
    if wd.is_dir() and _robust_rmtree(wd):
        log(f"    pruned workdir {wd}")
        return True
    return False


def _looks_like_workdir(child: Path) -> bool:
    """Is ``child`` a STAGED UE WORKDIR, judged by shape rather than location?

    True when a ``*.uproject`` sits within three levels of it — which is what
    every rig-staged workdir looks like (``<wd>/ThirdPerson/ThirdPerson.uproject``,
    or ``<wd>/scratch/CraftBenchTemplate/CraftBenchTemplate.uproject``).

    This is the guard that makes sweeping a TEMP root safe. ``wd_root()`` is ours
    by construction, so every child there is fair game; a root reached through
    ``CB_TMP``/``TEMP`` is only *conventionally* ours, and an operator who points
    ``CB_TMP`` at something shared must not have its siblings deleted. Shape is
    the check that survives that mistake — see ``paths.tmp_scratch_roots``.
    """
    for pat in ("*.uproject", "*/*.uproject", "*/*/*.uproject"):
        try:
            if next(child.glob(pat), None) is not None:
                return True
        except OSError:
            continue
    return False


def _prune_workdirs(wd_root: Path, referenced: set, *, older_than_days=None,
                    min_age_s=None, check: bool = False, now=None,
                    log=_say, require_project_shape: bool = False) -> List[Path]:
    """Prune ``wd_root`` subdirs NOT in ``referenced`` (and older than
    ``older_than_days`` / the ``min_age_s`` in-flight floor when given).
    ``check=True`` only reports. Returns the pruned (or would-be-pruned)
    dirs. Shared by the workdir sweep and the presnap sweep."""
    import time as _time
    now = _time.time() if now is None else now
    victims: List[Path] = []
    if not wd_root.is_dir():
        log(f"  (no workdir root at {wd_root})")
        return victims
    for child in sorted(wd_root.iterdir()):
        if not child.is_dir():
            continue
        if require_project_shape and not _looks_like_workdir(child):
            log(f"  KEEP          {child}  (no .uproject — not a staged workdir)")
            continue
        if _norm_path(child) in referenced:
            log(f"  KEEP          {child}  (referenced by a runs/**/summary.json)")
            continue
        if older_than_days is not None or min_age_s is not None:
            try:
                age_s = now - child.stat().st_mtime
            except OSError:
                continue
            if min_age_s is not None and age_s < min_age_s:
                log(f"  KEEP          {child}  (younger than the in-flight floor)")
                continue
            if (older_than_days is not None
                    and age_s / 86400.0 < older_than_days):
                log(f"  KEEP          {child}  (younger than {older_than_days}d)")
                continue
        victims.append(child)
        if check:
            log(f"  WOULD DELETE  {child}")
        elif _robust_rmtree(child):
            log(f"  DELETED       {child}")
        else:
            log(f"  PARTIAL       {child}  (a process still holds a file under it)")
    return victims


def _slim_delegate():
    """``fs_cleanup.slim_workdir``, reached through the rig's ONE lazy sys.path seam
    (``workdir_retention._fs_cleanup``) instead of a second copy of that dance here.
    Returns None when the verifier half is absent — a rig-only checkout must get a
    one-line "unavailable", not a traceback out of a cleanup command."""
    try:
        from aura_rig import workdir_retention as _wdr
        return getattr(_wdr._fs_cleanup(), "slim_workdir", None)
    except Exception:  # noqa: BLE001 — ImportError, broken checkout, anything
        return None


def _dir_bytes(path) -> int:
    """Bytes under ``path`` (stat-only walk; links not followed, unreadable entries
    skipped). Only the ``--check`` preview needs it — a real slim pass gets its
    number from ``SlimStats.reclaimed_bytes``, which fs_cleanup measures before AND
    after each delete so a Windows-locked partial removal is credited honestly."""
    p = str(path)
    try:
        st = os.lstat(p)
    except OSError:
        return 0
    if not os.path.isdir(p) or os.path.islink(p):
        return st.st_size
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda _e: None):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue  # deleted under us — 0 bytes of reclaim, not an error
    return total


def _human_bytes(n: int) -> str:
    """Byte count in the unit the reader is thinking in: the reclaim story is told
    in GB (5.54 GB/workdir, 121 GB across 24), a single Binaries/ file is not."""
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f} MB"
    return f"{n} B"


def _slim_workdirs(wd_root: Path, *, older_than_days=None, min_age_s=None,
                   check: bool = False, now=None, log=_say,
                   require_project_shape: bool = False) -> "Tuple[int, int]":
    """Slim EVERY workdir under ``wd_root`` IN PLACE — referenced or not — dropping
    the compiler intermediates while the dir itself, its ``out/`` reports and its
    launchable ``Binaries/`` survive. Returns ``(dirs_slimmed, bytes_reclaimed)``.

    Deliberately NOT built on :func:`_prune_workdirs`. That loop ``continue``s on a
    referenced dir BEFORE it reaches the age gate, which is right for a DELETE (a
    referenced dir is never a victim, so its age is moot) and exactly wrong here: the
    referenced dirs ARE the target set. They are the ones no existing CLI path can
    reclaim — ``cb clean --workdirs`` keeps them by contract and ``cb eval`` has no
    prune flag — and the 121 GB measured across 24 workdirs on 2026-07-25 is almost
    entirely theirs. Reusing that loop would have skipped the in-flight floor on
    precisely the dirs this pass targets.

    So the floor applies to EVERY dir here. A workdir mid-L1-build has no
    summary.json yet, i.e. "unreferenced" and "in flight" are the SAME state, and
    pulling ``Intermediate/Build/Win64/x64`` out from under a running cl.exe fails
    the build it was 40 minutes into."""
    import time as _time
    now = _time.time() if now is None else now
    slimmed = 0
    total = 0
    if not wd_root.is_dir():
        log(f"  (no workdir root at {wd_root})")
        return slimmed, total
    slim = _slim_delegate()
    if slim is None:
        log("  !! fs_cleanup.slim_workdir is unavailable (no tools/verify-single in "
            "this checkout) — nothing was slimmed")
        return slimmed, total
    for child in sorted(wd_root.iterdir()):
        if not child.is_dir():
            continue
        if require_project_shape and not _looks_like_workdir(child):
            log(f"  KEEP FULL     {child}  (no .uproject — not a staged workdir)")
            continue
        try:
            age_s = now - child.stat().st_mtime
        except OSError:
            continue
        if min_age_s is not None and age_s < min_age_s:
            log(f"  KEEP FULL     {child}  (younger than the in-flight floor)")
            continue
        if (older_than_days is not None
                and age_s / 86400.0 < older_than_days):
            log(f"  KEEP FULL     {child}  (younger than {older_than_days}d)")
            continue
        # allow_root is the very root this loop enumerated, so the deleter's own
        # containment gate is provably the same set we walked (and the CLI stops
        # depending on a second, independent wd_root() resolution mid-sweep).
        if check:
            # The dry-run reuses the REAL target selection by injecting a deleter
            # that only MEASURES. Re-deriving fs_cleanup's delete allowlist here
            # would let the preview drift away from what the live pass removes —
            # and a --check that under-reports is how you talk yourself out of the
            # reclaim you actually needed.
            probe: List[int] = []
            slim(child, rmtree=lambda t: probe.append(_dir_bytes(t)),
                 allow_root=wd_root)
            n = sum(probe)
            log(f"  WOULD SLIM    {child}  (-{_human_bytes(n)}, "
                f"{len(probe)} path(s))")
        else:
            stats = slim(child, allow_root=wd_root)
            if getattr(stats, "refused", False):
                notes = getattr(stats, "notes", None) or ["no reason given"]
                log(f"  REFUSED       {child}  ({notes[-1]})")
                continue
            n = int(getattr(stats, "reclaimed_bytes", 0) or 0)
            log(f"  SLIMMED       {child}  (-{_human_bytes(n)}, "
                f"{getattr(stats, 'deleted_paths', 0)} path(s))")
        slimmed += 1
        total += n
    return slimmed, total


def _cmd_clean_workdirs(ctx: _Ctx, args: argparse.Namespace,
                        exclude_refs_under=()) -> int:
    from aura_rig import runs_clean as rcl
    wd_root = cb_paths.wd_root()
    floor_min = int(rcl.MIN_AGE_S // 60)
    # wd_root() is ours by construction, so its children need no shape check.
    # The temp scratch roots (C:\cbtmp and friends) are only conventionally
    # ours, so there every child must LOOK like a staged workdir before we touch
    # it. Sweeping them at all is the 2026-08-20 fix: an operator following
    # envgate's 8.3 remediation (`set TEMP=C:\cbtmp`) sends every mkdtemp
    # workdir there, and this command used to walk wd_root() only — 95 GB of
    # duplicated SharedPCH accumulated in the blind spot.
    roots = [(wd_root, False)]
    for extra in cb_paths.tmp_scratch_roots():
        if extra != wd_root and extra.is_dir():
            roots.append((extra, True))
    if getattr(args, "slim", False):
        mode = "DRY-RUN (--check)" if args.check else "SLIM IN PLACE"
        n = total = 0
        for root, shape in roots:
            _say(f"=== clean --workdirs --slim : {root}  [{mode}]  "
                 f"(slims EVERY workdir, referenced or not — the referenced ones are "
                 f"exactly what no other path can reclaim; dirs younger than "
                 f"{floor_min} min are in-flight-protected"
                 f"{'; shape-gated temp root' if shape else ''}) ===")
            rn, rtotal = _slim_workdirs(root, older_than_days=args.older_than,
                                        min_age_s=rcl.MIN_AGE_S, check=args.check,
                                        log=_say, require_project_shape=shape)
            n += rn
            total += rtotal
        _say(f"{'would reclaim' if args.check else 'reclaimed'} "
             f"{_human_bytes(total)} across {n} workdir(s) "
             f"(the dirs, their out/ reports and their launchable Binaries stay)")
        return 0
    refs = _referenced_workdirs(ctx.paths.craftbench,
                                exclude_under=exclude_refs_under)
    mode = "DRY-RUN (--check)" if args.check else "DELETE"
    _say(f"=== clean --workdirs : {wd_root}  [{mode}]  "
         f"({len(refs)} workdir(s) referenced by runs/**/summary.json; dirs "
         f"younger than {floor_min} min are in-flight-protected) ===")
    # min_age_s is NOT optional here, and its absence was a data-loss bug (found
    # 2026-07-25): a workdir mid-L1-build has not written summary.json yet, so it
    # reads as "unreferenced" and this sweep deleted the build tree out from under a
    # live run. The presnap sweep below already passed the floor for the same
    # reason; the workdir sweep just never did.
    victims: List[Path] = []
    for root, shape in roots:
        if root != wd_root:
            _say(f"=== clean --workdirs : {root}  [{mode}]  "
                 f"(temp scratch root — only children holding a .uproject are "
                 f"eligible; dirs younger than {floor_min} min are "
                 f"in-flight-protected) ===")
        victims += _prune_workdirs(root, refs, older_than_days=args.older_than,
                                   min_age_s=rcl.MIN_AGE_S,
                                   check=args.check, log=_say,
                                   require_project_shape=shape)
    _say(f"{'would delete' if args.check else 'deleted'} {len(victims)} workdir(s)")
    return 0


def _cmd_clean_presnaps(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Sweep ORPHANED pre-run writable snapshots (crash debris).

    A healthy graded run deletes its presnap after the verified restore
    (run_graded.restore_writable_tree), so a surviving snapshot means a
    hard-killed run. Its content is ≡ git HEAD by the contamination gate
    (and the self-heal gate may already have consumed what it needed), so
    sweeping loses nothing git doesn't hold. Snapshots younger than the
    runs_clean in-flight floor are kept — they may belong to a live drive."""
    from aura_rig import runs_clean as rcl
    from fairness import default_presnap_root

    # One root now. There was a second, run_graded_product's own
    # /tmp/cb-presnap-product, and it went with that module.
    roots = (default_presnap_root(),)
    mode = "DRY-RUN (--check)" if args.check else "DELETE"
    _say(f"=== clean --presnaps  [{mode}]  (snapshots younger than "
         f"{int(rcl.MIN_AGE_S // 60)} min are in-flight-protected) ===")
    total = 0
    for root in roots:
        total += len(_prune_workdirs(root, set(), min_age_s=rcl.MIN_AGE_S,
                                     check=args.check, log=_say))
    _say(f"{'would delete' if args.check else 'deleted'} {total} presnap(s)")
    return 0


def _cmd_clean_runs(ctx: _Ctx, args: argparse.Namespace) -> "Tuple[int, List[Path]]":
    from aura_rig import runs_clean as rcl
    runs_root = ctx.paths.craftbench / "runs"
    units = rcl.discover_run_units(runs_root)

    # `--runs --slim` SLIMS IN PLACE and deletes nothing. It is the recommended
    # sweep: it reclaims the reconstructible bulk (project-lean/ — 83% of runs/
    # here) while every unit's summary/report/logs/traces/deliverable survive,
    # so a verdict graded by an older fixture stays re-adjudicable. It returns
    # NO released paths: nothing was freed for the workdir sweep to reclaim,
    # because no summary.json (and so no graded_workdir reference) went away.
    if getattr(args, "slim", False):
        targets = rcl.slim_plan(units)
        mode = "DRY-RUN (--check)" if args.check else "SLIM"
        total = sum(t.nbytes for t in targets)
        _say(f"=== clean --runs --slim : {runs_root}  [{mode}]  "
             f"({len(units)} run unit(s); {len(targets)} carry reclaimable bytes; "
             f"units younger than {int(rcl.MIN_AGE_S // 60)} min are "
             f"in-flight-protected) ===")
        _say(f"  drops {', '.join(rcl.SLIM_DROP)}/ per unit — "
             f"no unit is deleted, no evidence is lost")
        slimmed, freed = rcl.slim_execute(
            targets, runs_root / rcl.LEDGER_NAME, _robust_rmtree,
            check=args.check, log=_say)
        if args.check:
            _say(f"would slim {len(targets)} unit(s), reclaiming "
                 f"{total / 2**30:.2f} GB")
        else:
            _say(f"slimmed {slimmed} unit(s), reclaimed {freed / 2**30:.2f} GB; "
                 f"history appended to {runs_root / rcl.LEDGER_NAME}")
        return 0, []

    victims, kept = rcl.plan(units, keep_last=args.keep_last,
                             older_than_days=args.older_than)
    mode = "DRY-RUN (--check)" if args.check else "DELETE"
    _say(f"=== clean --runs : {runs_root}  [{mode}]  "
         f"({len(units)} run unit(s): keep {len(kept)}, prune {len(victims)}; "
         f"units younger than {int(rcl.MIN_AGE_S // 60)} min are in-flight-protected) ===")
    for u in kept:
        _say(f"  KEEP          {u.path}")
    removed = rcl.execute(victims, runs_root / rcl.LEDGER_NAME, _robust_rmtree,
                          check=args.check, log=_say)
    if args.check:
        _say(f"would delete {len(victims)} run unit(s)")
    else:
        _say(f"deleted {removed} run unit(s); "
             f"history appended to {runs_root / rcl.LEDGER_NAME}")
    return 0, [u.path for u in victims]


def cmd_clean(ctx: _Ctx, args: argparse.Namespace) -> int:
    # --runs / --workdirs: prune graded-run history / stale verifier workdirs
    # instead of the scratch project. Combined, runs go FIRST — deleting a run's
    # summary.json releases its graded_workdir reference, so the workdir sweep
    # can reclaim that tree in the same invocation. In --check mode nothing was
    # actually deleted, so the workdir preview must SIMULATE that release
    # (exclude refs under would-be-victim runs) or it under-reports.
    #
    # --slim IMPLIES the workdir route (it is a modifier of that sweep, and the
    # bare `cb clean --slim` a user reaches for must not silently reset the
    # scratch project instead). It REPLACES the delete rather than adding to it:
    # slim reclaims in place and every dir stays, so a run pointing at one keeps
    # working — mixing a delete into that would make "cb clean --slim" destroy the
    # unreferenced dirs as a side effect nobody asked for.
    #
    # EXCEPT alongside --runs, where --slim modifies the RUNS sweep instead.
    # Without this the single most guessable "shrink my runs/" command,
    # `cb clean --runs --slim`, took the --runs DELETE branch (slim was not
    # read there) and additionally slimmed workdirs — the one spelling whose
    # plain meaning is "keep them, just smaller" was the one that erased them.
    # --workdirs still composes explicitly: `--runs --slim --workdirs`.
    workdirs = getattr(args, "workdirs", False) or (
        getattr(args, "slim", False) and not getattr(args, "runs", False))
    if (getattr(args, "runs", False) or workdirs
            or getattr(args, "presnaps", False)):
        rc = 0
        released: List[Path] = []
        if getattr(args, "runs", False):
            rc_runs, victims = _cmd_clean_runs(ctx, args)
            rc = max(rc, rc_runs)
            if args.check:
                released = victims
        if workdirs:
            rc = max(rc, _cmd_clean_workdirs(ctx, args,
                                             exclude_refs_under=released))
        if getattr(args, "presnaps", False):
            rc = max(rc, _cmd_clean_presnaps(ctx, args))
        return rc
    # clean only manages the DEFAULT scratch; a user --project is left alone.
    if args.project:
        _say("clean only manages the default scratch; your --project is left alone")
        return 0
    dir_ = stack.get_drive_project_dir("")
    if stack.reset_drive_project(dir_, ctx.paths, log=_say):
        _say(f"playground clean: {dir_}")
        return 0
    return 1


def cmd_down(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Stop the WHOLE stack supervisor-first (ports cb.ps1 'down' -> stack.stop_stack:
    # kill the server ports FIRST so nothing can respawn the editor, then the UE
    # images + the Live Coding console that holds UE's engine lock). This is the
    # command that reaps a resident unreal-mcp headless editor.
    stack.stop_stack(log=_say)
    return 0


def cmd_status(ctx: _Ctx, args: argparse.Namespace) -> int:
    """One-shot, READ-ONLY overview of this machine: is the editor stack up and
    ready, who owns it, is a graded run in flight, and what did the last run
    decide. It starts nothing, stops nothing, and returns 0 whatever it finds —
    DOWN is an answer, not an error. (`cb doctor` is the other read-only
    command: it asks whether this machine COULD run, this one asks what it is
    doing right now.)

    WHY THIS IS HAND-ROLLED. It used to render a `stack.snapshot()` — a
    five-component health frame (the vercel dev server on :3000, the CDP dev
    browser on :9222, the private client on :3002, the editor, the last run)
    shared with the private stack's dashboard. Four of those five components
    are the aura-product lane, `invoke_bringup` is a ONE-stage gate now, and
    `snapshot` went out with them, so the frame is rebuilt here from what this
    release actually has.

    The editor line is probed exactly the way `invoke_bringup` gates it — a
    real MCP `initialize` round-trip through :mod:`aura_rig.unreal_mcp_stack`,
    never a port probe — deliberately, so `cb status` and `cb up` can never
    disagree about what "ready" means.
    """
    from aura_rig import runs_clean, stack_guard
    from aura_rig import unreal_mcp_stack as _ums

    # --- the one component a bring-up brings up -----------------------------
    url = _ums.resolve_url()
    # timeout_s=0 => exactly ONE initialize attempt and no wait loop (the
    # remaining<=0 branch returns before the "waiting" log can fire). `cb up`
    # is the command that WAITS for an editor; status only reports on one.
    ready = _ums.unreal_mcp_ready(url, timeout_s=0, log=lambda _m: None)
    _say(f"STACK [{'GREEN' if ready else 'DOWN'}]")
    _say(f"  {'OK  ' if ready else 'FAIL'} editor-mcp         {url} "
         f"({'MCP initialize round-trips' if ready else 'no MCP initialize'})")

    # WHOSE stack it is. A manifest whose owner pid is DEAD is precisely what
    # the janitor / the next cb tears down on sight, so say it here rather than
    # let the teardown be a surprise.
    man = stack_guard.read_manifest()
    if man is None:
        _say("  owner      : no ownership manifest (nothing here claims a stack)")
    else:
        owner = man.get("owner_pid")
        alive = stack_guard.pid_alive(owner, man.get("owner_created"))
        fate = "alive" if alive else "DEAD — reaped by the janitor / the next cb"
        _say(f"  owner      : {stack_guard.manifest_state(man)}, pid {owner} ({fate})")
        if man.get("uproject"):
            _say(f"  editor on  : {man['uproject']}")

    # A foreign editor is not ours to report on OR to reap — but it shares
    # :30010 with us, so it is the difference between "the stack is up" and
    # "something else is up on the port cb wants".
    foreign = stack.foreign_editor()
    if foreign:
        _say(f"  WARN  a NON-craftbench UnrealEditor is running (pid {foreign[0]}); "
             "cb refuses to hijack it — close it before `cb up`")

    if _live_run_active(ctx):
        _say("  live run   : a graded run holds runs/.live-run.lock right now "
             "(stack-mutating commands will refuse)")

    # Diagnostics the component line doesn't carry (cb.ps1 status showed these):
    lc = stack.count_image("LiveCodingConsole")
    sc = stack.get_drive_project_dir("")
    lc_note = ("holds UE's build lock while up — `cb down` frees it"
               if lc else "engine build lock is free")
    _say(f"\n  LiveCoding : {lc} console(s)  (UE hot-reload helper; {lc_note})")
    _say(f"  scratch    : {sc} (built: {(sc / '.cb-built').exists()})")

    # --- the last run -------------------------------------------------------
    # runs_clean is where the THREE run-record shapes (run.py's result.json,
    # run_graded's summary.json, and the batch/matrix/bench aggregates) are
    # ALREADY reconciled into one flat row. Status reads them through that same
    # extractor rather than growing a fourth schema guess of its own.
    units = runs_clean.discover_run_units(ctx.paths.craftbench / "runs")
    if not units:
        _say("\nLAST RUN  (none — nothing graded under runs/ yet)")
        return 0
    newest = units[0]
    row = runs_clean.ledger_row(newest)
    facts = "  ".join(f"{k}={row[k]}" for k in ("task", "model", "verdict", "cost_usd")
                      if row.get(k) is not None)
    _say(f"\nLAST RUN  {newest.path}")
    _say(f"          {facts or '(no verdict envelope — aborted, or still in flight)'}")
    report = newest.path / "report.html"
    if report.is_file():
        _say(f"          report: {report}")
    return 0


def cmd_doctor(ctx: _Ctx, args: argparse.Namespace) -> int:
    # THIN WRAPPER: doctor.real_probe resolves every live fact (filesystem, env,
    # live HTTP snapshot) into a Probe; doctor.diagnose is PURE over that bag of
    # facts; doctor.render formats it grouped-by-tier. ALL the I/O + the .env-text
    # read + placeholder-stripping live in doctor.real_probe (the single source of
    # truth) — doctor is local-imported so `cb where` and friends stay cheap.
    from aura_rig import doctor

    probe = doctor.real_probe(ctx)
    diag = doctor.diagnose(probe)
    print(doctor.render(diag, live_coding=probe.live_coding), flush=True)
    return diag.exit_code()


def _where_rows(ctx: _Ctx) -> "List[Tuple[str, Path]]":
    """The (label, dir) rows `cb where` prints — ONE place so the command and
    its test agree. Pure resolution, no filesystem writes."""
    repo = ctx.paths.craftbench
    return [
        ("repo", repo),
        ("substrate", ctx.paths.template_dir),
        ("cb_root", cb_paths.cb_root()),
        ("wd_root", cb_paths.wd_root()),
        ("graded scratch", cb_paths.graded_project_dir()),
        ("drive scratch", stack.get_drive_project_dir("")),
        ("runs", repo / "runs"),
    ]


def _ensure_dir_link(link: Path, target: Path, log=_say) -> int:
    """Idempotently point ``link`` at directory ``target`` (symlink on POSIX,
    junction via `mklink /J` on Windows). Creates ``target`` if missing.
    An existing link that already resolves to ``target`` is left alone; a
    stale LINK is replaced. A real, non-empty directory at ``link`` is
    REFUSED (never clobbered) — printed as a one-liner, returns 1; success
    returns 0. Never lets an OSError/mklink failure traceback out."""
    try:
        target.mkdir(parents=True, exist_ok=True)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            try:
                if Path(os.path.realpath(link)) == Path(os.path.realpath(target)):
                    log(f"  OK    {link} -> {target} (already linked)")
                    return 0
            except OSError:
                pass
            if link.is_symlink():
                link.unlink()
            elif link.is_dir():
                # A Windows junction presents as a dir; os.rmdir removes the
                # junction itself, never the target's content. A REAL non-empty
                # dir raises OSError here — deliberately: we refuse to clobber.
                os.rmdir(link)
            else:
                link.unlink()
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           check=True, capture_output=True)
        else:
            os.symlink(target, link, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError):
        log(f"  SKIP  refusing to clobber {link}; remove it manually")
        return 1
    log(f"  LINK  {link} -> {target}")
    return 0


def cmd_where(ctx: _Ctx, args: argparse.Namespace) -> int:
    # READ-ONLY by default: print every machine-local dir the rig resolves
    # (repo, substrate, CB_ROOT + its wd/scratch children, runs/) and whether
    # each exists. `--link` additionally drops gitignored <repo>/.cb/{wd,scratch}
    # links so the out-of-repo dirs are one click from the checkout.
    _say("=== cb where : resolved machine dirs (CB_ROOT model) ===")
    for name, p in _where_rows(ctx):
        mark = "OK  " if Path(p).exists() else "--  "
        _say(f"  {mark}{name:<15} {p}")
    _say("  (overrides: CB_ROOT, CRAFTBENCH_WD_ROOT, CB_GRADED_PROJECT, "
         "CB_DRIVE_PROJECT)")
    if getattr(args, "link", False):
        dot_cb = ctx.paths.craftbench / ".cb"
        _say(f"=== cb where --link : {dot_cb} ===")
        # Each entry is attempted independently; a refused link (real dir in
        # the way, mklink failure) prints one line and flips the exit code.
        rc = _ensure_dir_link(dot_cb / "wd", cb_paths.wd_root(), log=_say)
        rc |= _ensure_dir_link(dot_cb / "scratch", cb_paths.scratch_root(), log=_say)
        return rc
    return 0


def cmd_lint(ctx: _Ctx, args: argparse.Namespace) -> int:
    # Token-FREE static task-spec lint — a thin front-end over
    # tools/verify-single/tasklint.py (no UE, no stack, no tokens).
    # `cb lint` lints every spec under tasks/ (--all); `cb lint --task
    # <id|set|set/id>` expands the target exactly like cb discriminate.
    from aura_rig import discriminate as disc
    from aura_rig import tasks as _tasks

    if ctx.py_exe is None:
        _say("FAIL  no harness Python (set --py / CB_PY, or install the py launcher + 3.12)")
        return 1
    repo = ctx.paths.craftbench
    tasklint_py = repo / "tools" / "verify-single" / "tasklint.py"
    argv = [ctx.py_exe, *ctx.py_pre, str(tasklint_py)]
    if args.task and args.task != _DEFAULT_TASK:
        ids, err = disc.expand_targets(repo, args.task)
        if err:
            _say(f"FAIL  {err}")
            return 2
        for tid in ids:
            spec_path = _tasks.resolve_task_path(repo, tid)
            if spec_path is None:
                _say(f"FAIL  task spec not found: {tid}")
                return 2
            argv.append(str(spec_path))
    else:
        argv.append("--all")
    return subprocess.call(argv, cwd=str(repo))


# =========================================================================== #
# argparse front-end.                                                          #
# =========================================================================== #

def cmd_smoke(ctx: _Ctx, args: argparse.Namespace) -> int:
    """The golden path, proven by execution instead of prose: envgate ->
    verifier unit tests -> a real t0 reference grade on UE. ``--agent
    <model-slug>`` appends ONE live graded eval (token-spending; opt-in).
    Exit 0 iff every leg passed — a newcomer whose ``cb smoke`` exits 0 has a
    working benchmark machine; a red leg prints the exact fix (envgate) or the
    failing leg's tail. Run it after harness changes too: this command is what
    keeps the README quickstart honest."""
    import uuid as _uuid
    from aura_rig import envgate

    # Exclusivity BEFORE any leg. TWO independent reasons here, not one: leg 3
    # is a real t0 reference build (the engine-keyed Build.bat mutex — see
    # _refuse_build_if_live_run), and leg 2 runs the verifier UNIT TESTS, the
    # exact process class that murdered a live drive editor on 2026-08-07
    # (kill_guard.py's header incident: a test run reached the production
    # stop_stack and the rep recorded EDITOR-GONE with no crash dump).
    # kill_guard now REFUSES those kills, but not starting the suite under a
    # paid drive is the cheaper half of that defense. Exit 2 = smoke's existing
    # "refused, nothing built, nothing spent" code (the preflight-blocker
    # return below), never 1, which means a leg actually FAILED.
    if _refuse_build_if_live_run(ctx, "smoke"):
        return 2
    # --agent names the model of the OPTIONAL leg 4. Refuse an unroutable one
    # now: otherwise leg 1 picks its env tier from that slug and legs 1-3 run
    # in full before cmd_eval declines the only leg the operator asked for.
    if args.agent and _refuse_unroutable_model(args.agent):
        return 2

    repo = ctx.paths.craftbench
    legs: List[tuple] = []  # (name, ok_or_None, detail)

    # --- leg 1: the environment gate (same gate every eval runs) ------------
    tier = (envgate.tier_for_model(args.agent, _backend_of) if args.agent
            else "grade")
    _say(f"\n=== SMOKE [1/{3 + (1 if args.agent else 0)}] preflight ({tier}) ===")
    gate_ok = envgate.enforce(ctx, tier, _say, skip=args.no_preflight)
    legs.append(("preflight", gate_ok, tier))
    if not gate_ok:
        _say("\nsmoke: preflight has blockers — fix the lines above and re-run. "
             "(Nothing was built; nothing was spent.)")
        return 2

    # --- leg 2: verifier unit tests (no UE, ~seconds) -----------------------
    _say(f"\n=== SMOKE [2/{3 + (1 if args.agent else 0)}] verifier unit tests ===")
    if ctx.py_exe is None:
        legs.append(("verifier-unit-tests", False, "no harness python"))
    else:
        cp = subprocess.run(
            [ctx.py_exe, *ctx.py_pre, "-m", "unittest", "discover",
             "-s", "tools/verify-single/tests"],
            cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1800)
        tail = [ln for ln in (cp.stderr + cp.stdout).splitlines()
                if ln.strip().startswith(("Ran ", "OK", "FAILED", "ERROR"))]
        detail = "; ".join(tail[-2:]) or "<no output>"
        _say(f"  {detail}")
        legs.append(("verifier-unit-tests", cp.returncode == 0, detail))

    # --- leg 3: t0 reference grade (the real thing: L1 build + L2 PIE) ------
    _say(f"\n=== SMOKE [3/{3 + (1 if args.agent else 0)}] t0 reference grade "
         f"(L1 build + L2 PIE; ~4-8 min cold) ===")
    if ctx.ue is None or ctx.py_exe is None:
        legs.append(("t0-reference-grade", False, "UE / python missing (gate should have caught this)"))
    else:
        ue_root = str(os.environ.get("CB_UE_ROOT") or ctx.ue.parents[3])
        wd = cb_paths.wd_root() / f"smoke{_uuid.uuid4().hex[:6]}"
        spec = repo / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "task.md"
        ref = repo / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "reference"
        t0 = time.time()
        cp = subprocess.run(
            [ctx.py_exe, *ctx.py_pre,
             str(repo / "tools" / "verify-single" / "run_task.py"),
             "--task", str(spec), "--submission", str(ref),
             "--ue-root", ue_root, "--workdir", str(wd)],
            cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3600)
        dur = time.time() - t0
        ok = cp.returncode == 0
        if not ok:
            for ln in [l for l in (cp.stdout + cp.stderr).splitlines() if l.strip()][-8:]:
                _say(f"  | {ln}")
        legs.append(("t0-reference-grade", ok, f"exit {cp.returncode} in {dur:.0f}s"))
        _say(f"  t0 reference: {'PASS' if ok else 'FAIL'} ({dur:.0f}s)")
        # Slim this leg's workdir UNCONDITIONALLY (pass or fail): smoke passes no
        # --keep-workdir, so nothing ever adopts `wd` and nothing ever references it
        # — which is where the 6 unreferenced smoke* workdirs in the 2026-07-25
        # census (5.54 GB apiece) came from. Slim rather than delete so a FAILED
        # smoke still leaves out/l1_build.log and the launchable Binaries to read,
        # which is the entire point of running smoke on a new machine. Best-effort:
        # _slim_workdirs never raises, and a smoke verdict must not hinge on
        # housekeeping.
        slim = _slim_delegate()
        if wd.is_dir() and slim is not None:
            slim(wd, log=_say)   # wd is <wd_root>/smoke<hex>, so its own gate passes

    # --- leg 4 (opt-in): one LIVE graded eval (spends tokens) ---------------
    if args.agent and all(ok for _n, ok, _d in legs):
        _say(f"\n=== SMOKE [4/4] live graded eval ({args.agent} on t0; SPENDS tokens) ===")
        args.model = args.agent
        args.task = _DEFAULT_TASK
        rc = cmd_eval(ctx, args)
        legs.append((f"live-eval({args.agent})", rc == 0, f"cb eval exit {rc}"))
    elif args.agent:
        legs.append((f"live-eval({args.agent})", None, "skipped: an earlier leg failed"))

    # --- scoreboard ----------------------------------------------------------
    _say(f"\n{BAR}")
    n_ok = sum(1 for _n, ok, _d in legs if ok)
    for name, ok, detail in legs:
        word = "OK  " if ok else ("SKIP" if ok is None else "FAIL")
        _say(f"  {word}  {name:<22} {detail}")
    all_ok = all(ok for _n, ok, _d in legs)
    _say(f"smoke: {n_ok}/{len(legs)} legs OK — "
         + ("the golden path works on this machine"
            if all_ok else "fix the FAIL leg(s) above, then re-run `cb smoke`"))
    _say(BAR)
    return 0 if all_ok else 1


def cmd_completions(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Print the tab-completion registration snippet for a shell. The snippet
    calls the hidden `cb __complete <mode> [arg]` for candidates, so the
    completion data can never drift from the CLI itself."""
    from aura_rig import cli_help
    shell = (args.outputs or "").strip().lower()
    if shell == "powershell":
        _say(cli_help.POWERSHELL_COMPLETER)
        return 0
    if shell == "bash":
        _say(cli_help.BASH_COMPLETER)
        return 0
    _say("usage: cb completions powershell | bash")
    _say("  PowerShell (session): cb completions powershell | Out-String | Invoke-Expression")
    _say("  bash (session):       eval \"$(cb completions bash)\"")
    _say("  Persist by adding that same line to $PROFILE / ~/.bashrc.")
    return 0 if shell == "" else 2


def cmd_complete_candidates(ctx: _Ctx, args: argparse.Namespace) -> int:
    """Hidden machine-facing candidate emitter for the shell completers
    (`cb __complete <mode> [arg]`, one candidate per line). Never errors —
    a completer that throws breaks the user's TAB key."""
    from aura_rig import cli_help
    mode = (args.outputs or "").strip()
    arg = (getattr(args, "gen_outputs", "") or "").strip()
    try:
        for cand in cli_help.complete(mode, arg, ctx.paths.craftbench):
            _say(cand)
    except Exception:  # noqa: BLE001 — silent empty completion beats a stacktrace
        pass
    return 0


_DISPATCH = {
    "up": cmd_up,
    "smoke": cmd_smoke,
    "eval": cmd_eval,
    "matrix": cmd_matrix,
    "bench": cmd_bench,
    "discriminate": cmd_discriminate,
    "wip": cmd_discriminate,
    "lint": cmd_lint,
    "batch-eval": cmd_batch_eval,
    "refgate": cmd_refgate,
    "warm-prime": cmd_warm_prime,
    "tasks": cmd_tasks,
    "view": cmd_view,
    "review": cmd_review,
    "reliability": cmd_reliability,
    "status": cmd_status,
    "where": cmd_where,
    "doctor": cmd_doctor,
    "clean": cmd_clean,
    "down": cmd_down,
    "completions": cmd_completions,
    "__complete": cmd_complete_candidates,   # hidden: shell-completer data feed
}


# The two hidden commands have no cli_help entry (test_cli_help's `hidden`
# set), so their positional arity lives here instead.
_HIDDEN_POSITIONAL = {
    "__complete": ("<mode>", "[arg]"),   # machine-facing completer feed
}


def _positional_metavars(command: str) -> tuple:
    """The trailing positionals ``command`` CONSUMES, from the ONE registry."""
    from aura_rig import cli_help
    if command in _HIDDEN_POSITIONAL:
        return _HIDDEN_POSITIONAL[command]
    entry = cli_help.COMMANDS.get(command)
    return tuple(entry.positional) if entry is not None else ()


def reject_stray_positionals(args: argparse.Namespace) -> Optional[str]:
    """The error text for a trailing word ``args.command`` cannot consume, or None.

    The parser is FLAT: it offers the same two optional positionals
    (``outputs``, ``gen_outputs``) to every command, so argparse accepts a
    stray word after ANY of them. Before this guard
    ``cb eval t1-physics-drop-and-rest`` parsed as
    ``outputs='t1-physics-drop-and-rest'`` with ``--task`` left at its DEFAULT
    — a full-price agent drive that graded t0 and reported on t0, with nothing
    on screen naming the task the operator asked for. Same shape on
    ``discriminate``/``wip``/``lint``.
    """
    from aura_rig import cli_help
    allowed = _positional_metavars(args.command)
    supplied = [("outputs", getattr(args, "outputs", "") or ""),
                ("gen_outputs", getattr(args, "gen_outputs", "") or "")]
    stray = [v for (_n, v) in supplied[len(allowed):] if v.strip()]
    if not stray:
        return None
    entry = cli_help.COMMANDS.get(args.command)
    lines = [f"FAIL  `cb {args.command}` takes "
             + (f"{len(allowed)} positional argument(s) ({' '.join(allowed)}), "
                f"but got an extra: {stray[0]!r}"
                if allowed else f"no positional argument, but got {stray[0]!r}")]
    takes_task = entry is not None and any(f == "--task" for f, _d in entry.flags)
    if takes_task:
        lines.append(f"      Did you mean:  cb {args.command} --task {stray[0]}")
    lines.append(f"      See `cb help {args.command}` for what this command accepts.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    from aura_rig import cli_help
    ap = argparse.ArgumentParser(
        prog="cb",
        description="cb - CraftBench-UE, one cross-platform entry point "
                    "(run via the cb launcher, or `python -m aura_rig.cb`).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # The grouped overview is generated from cli_help.COMMANDS — the ONE
        # registry that also powers `cb help <cmd>`, `cb <cmd> --help`, and
        # tab completion (drift-guarded by tests/test_cli_help.py).
        epilog=cli_help.render_overview(),
    )
    # Optional + a 'help' alias so bare `python -m aura_rig.cb` prints usage and
    # exits 0 (cb.ps1 defaulted $Command to 'help'), not an argparse error.
    ap.add_argument("command", nargs="?", default="help",
                    choices=sorted(_DISPATCH.keys()) + ["help"],
                    help="which action to run (default: help)")

    # Shared positional[1]: for batch-eval it is the folder of already-isolated
    # submission dirs to grade; review reads it as the run dir.
    # Optional so every OTHER command still parses with no trailing positional.
    ap.add_argument("outputs", nargs="?", default="",
                    help="batch-eval: folder of submission dirs (each named by its task id; "
                         "or use --references to grade the tasks' own reference solutions); "
                         "preview / review: the run dir")
    # Positional[2]: kept for the hidden `__complete` feed, which takes
    # <mode> [arg] (see _HIDDEN_POSITIONAL). It used to be batch-gen's report
    # dir; reject_stray_positionals refuses it for every other command.
    ap.add_argument("gen_outputs", nargs="?", default="",
                    help=argparse.SUPPRESS)

    # Eval target + model/budget knobs (mirror cb.ps1 param defaults exactly).
    ap.add_argument("--task", default=_DEFAULT_TASK,
                    help="task id to grade (eval); set-aware (root, '<set>', or "
                         "'<set>/<id>'). bench: a COMMA LIST of ids runs a "
                         "multi-task matrix (set-qualified ids preferred; "
                         "optional per-task ':N' repeat override, e.g. "
                         "'bp/gp-glide-stamina-bp,bp/gp-poison-dot-stack-bp:2')")
    # The default is an ARM, not a vendor model key: see _DEFAULT_MODEL for why
    # a bare key is no longer accepted at all.
    ap.add_argument("--model", default=_DEFAULT_MODEL,
                    help="arm to run: claude-p[:<model>] (default), "
                         "unreal-mcp[:<model>], openrouter:<provider/model>, "
                         "bare:<provider/model>. aura-mcp[:<model>] is "
                         "recognized but not reproducible from this repository "
                         "(see THIRD-PARTY.md)")
    ap.add_argument("--ceiling", type=int, default=1200,
                    help="agent wall-clock ceiling in seconds (default 1200). "
                         "Now genuinely enforced at each turn boundary, and now "
                         "forwarded on the BASELINE lane too (it was a no-op there).")

    # View / map.
    ap.add_argument("--map", default="",
                    help="map to open in view (bare L_* name — resolved through "
                         "Content/Maps/** incl. per-task folders — or a full "
                         "/Game/... package path)")
    ap.add_argument("--graded", action="store_true",
                    help="view: open the GRADED-eval scratch at the composed "
                         "task's map (the project `cb eval` leaves dirty)")
    ap.add_argument("--run", default="",
                    help="view: overlay a graded run's deliverable/ onto the template")
    ap.add_argument("--latest", action="store_true",
                    help="review: open the MOST RECENT run's result (newest "
                         "run dir under any runs/<arm>/ track that has a "
                         "deliverable/) — no run dir needed")

    # Overrides (flag OR env).
    ap.add_argument("--project", default="",
                    help="view/review/clean project dir (used AS-IS, never reset)")
    ap.add_argument("--ue-root", default="", help="UE 5.8 install root (-> CB_UE_ROOT)")
    ap.add_argument("--py", default="", help="harness python launcher line (-> CB_PY)")
    ap.add_argument("--keep", action="store_true",
                    help="eval: keep the graded project (lean copy under the run dir / "
                         "run.py --keep-workspace). discriminate: keep every leg's "
                         "report+workdir under runs/discriminate/<task>-<ts>/. "
                         "batch-eval: keep each verify's workdir (recorded per row).")
    ap.add_argument("--keep-workdir", action="store_true",
                    help="eval/bench/batch-eval: keep the FULL verifier workdir "
                         "(~5.9 GB) instead of the slim default — sets "
                         "CB_WORKDIR_RETENTION=full for this run. Use when you intend "
                         "to reopen, rebuild or re-verify the graded project. NOT the "
                         "same as --keep, whose project-lean/ copy EXCLUDES Binaries + "
                         "Intermediate and so cannot be rebuilt. A run whose L1 FAILED "
                         "is never slimmed anyway, so debugging a failed build needs "
                         "neither flag.")
    ap.add_argument("--visible", action="store_true",
                    help="eval: run VISIBLE — the live editor renders to a real window "
                         "(drops only -RenderOffScreen) and the verifier's L2/L2I legs "
                         "use a real RHI. Opt-in; default stays headless-deterministic.")
    ap.add_argument("--capture", action="store_true",
                    help="eval: capture screenshots — the verifier runs with a real RHI "
                         "+ the -CraftBenchCapture hook and sweeps Saved/CraftBench/*.png "
                         "into the run dir's artifacts/.")
    ap.add_argument("--link", action="store_true",
                    help="where: create gitignored <repo>/.cb/{wd,scratch} links "
                         "(POSIX symlink / Windows junction) to the resolved "
                         "machine dirs; idempotent, refuses to clobber a real dir")
    ap.add_argument("--workdirs", action="store_true",
                    help="clean: prune machine wd-root workdirs (CRAFTBENCH_WD_ROOT, "
                         "default <cb_root>/wd — see `cb where`) not referenced by any "
                         "runs/**/summary.json or result.json graded_workdir; "
                         "workdirs younger than the 60-min in-flight floor are kept "
                         "(a mid-build workdir has no summary.json yet); "
                         "pair with --check to only list, --older-than N to age-gate")
    ap.add_argument("--slim", action="store_true",
                    help="clean --workdirs: SLIM every workdir in place instead of "
                         "deleting unreferenced ones — drops Intermediate/Build/Win64/"
                         "x64 + the Binaries debug/link files (~5.5 of 5.54 GB each) "
                         "and KEEPS the dir, its out/ reports and its launchable "
                         "Binaries. Applies to REFERENCED dirs too — those are exactly "
                         "the ones no other path can reclaim (measured 2026-07-25: 24 "
                         "workdirs = 121 GB). Honors --check / --older-than and the "
                         "in-flight floor; implies --workdirs. "
                         "WITH --runs it modifies the RUNS sweep instead (and implies "
                         "nothing): every run unit is KEPT and only its reconstructible "
                         "project-lean/ is dropped — 83%% of runs/ here, with every "
                         "summary/report/log/trace/deliverable intact so an old "
                         "verdict stays re-adjudicable against today's fixture")
    ap.add_argument("--runs", action="store_true",
                    help="clean: prune graded RUN DIRS under runs/ (flat + container-"
                         "nested, marker-file based), appending each run's verdict/"
                         "cost/time record to runs/LEDGER.jsonl first; gate with "
                         "--keep-last K / --older-than N; --check dry-runs; combine "
                         "with --workdirs to also sweep the freed verifier workdirs")
    ap.add_argument("--presnaps", action="store_true",
                    help="clean: sweep ORPHANED pre-run writable-tree snapshots "
                         "(CB_TMP/cb-presnap) left by "
                         "hard-killed runs — a clean run deletes its own presnap "
                         "after restore, so anything older than the 60-min "
                         "in-flight floor is crash debris (content ≡ git HEAD by "
                         "the contamination gate); --check dry-runs")
    ap.add_argument("--keep-last", type=int, default=0, metavar="K",
                    help="clean --runs: always keep the K newest run units (default: 0)")
    ap.add_argument("--older-than", type=int, default=None, metavar="N",
                    help="clean --runs/--workdirs: only prune (or --slim) items older "
                         "than N days")
    ap.add_argument("--check", action="store_true",
                    help="clean --runs / clean --workdirs [--slim]: "
                         "DRY-RUN — report what each step WOULD do (--slim reports "
                         "per-dir reclaimable bytes), mutate nothing")
    ap.add_argument("--wip", action="store_true",
                    help="discriminate / batch-eval: force --substrate-from-live for EVERY task (maintainer is mid-edit). "
                         "Default: decide per-task from git (committed+clean -> from HEAD; untracked/dirty -> from-live).")

    # batch-eval knobs.
    ap.add_argument("--verify-concurrency", type=int, default=1,
                    help="batch-eval: parallel cold-verify width (default: 1 — safe on <=32 GB. "
                         "2-wide, two full-RHI L2 PIE editors contend and can spuriously FAIL an "
                         "L1-passing solution; on Windows without psutil the mem-gate back-off is "
                         "off, so this is the only cap. Raise to 2+ only on a >32 GB host.)")
    ap.add_argument("--label", default="batch-eval",
                    help="batch-eval: run label (the runs/<track>/<label>-<ts>/ prefix)")
    ap.add_argument("--references", nargs="?", const="all", default=None,
                    metavar="SET",
                    help="batch-eval: grade every task's REFERENCE solution (folder-local "
                         "reference/ or legacy tests/reference-solutions/<id>/) instead of "
                         "an outputs folder. Bare --references = all sets; give a set name "
                         "(e.g. --references bp-g2) to filter. Mutually exclusive with the "
                         "outputs positional.")
    # SPELLING IS LOAD-BEARING: this parser is FLAT (every flag parses on every
    # command) and argparse allows prefix abbreviation, so a second `--a*` flag
    # would make the previously-unambiguous `--a` ambiguous against `--agent`
    # and turn `cb smoke --a <model>` into an exit-2 usage error. Verified
    # against HEAD before the rename. Any future flag here: check its prefix.
    ap.add_argument("--no-gate", action="store_true", dest="allow_fail",
                    help="batch-eval: exit 0 even when graded submissions FAIL "
                         "(MEASUREMENT mode — grading a folder of real agent "
                         "outputs, where a FAIL is the data, not a red build). "
                         "Default since 2026-07-25 is GATE mode: any graded FAIL "
                         "exits 1, so `--references all` is a real regression "
                         "gate. 0 graded still exits 1 either way — an empty "
                         "gate is never a passing gate.")

    # warm-cache (L1 incremental build pool).
    ap.add_argument("--warm-cache", action="store_true",
                    help="batch-eval / discriminate / eval / bench: build each "
                         "verify's L1 from the warm POOL. Honored on EVERY eval backend - "
                         "run.py forwards --warm-cache on both its workspace and "
                         "--live-project spines (baseline, unreal-mcp). Measured on t0 at one "
                         "submission sha: L1 104.2s cold -> 4.0s when no writable SOURCE byte "
                         "changed, 23.7s for a 2-file edit. Per-file content keying is what "
                         "makes an all-.uasset submission (no compile input "
                         "changed at all) take the 4s path. Costs ~5.95 GB/slot in a root no "
                         "`cb clean` prunes - keep it SHORT on Windows via CB_WARM_CACHE_DIR "
                         "(the default leaves 39 chars of MAX_PATH headroom). Prime first with "
                         "`cb warm-prime --warm-slots N`. Up to N concurrent verifies run warm; "
                         "extras (and from-live legs) fall back to cold. Safe no-op if no pool.")
    ap.add_argument("--warm-slots", type=int, default=2,
                    help="warm-prime: number of pool slots to build (default: 2; match your "
                         "batch-eval --verify-concurrency). Each slot is one cold build + ~5 GB.")
    ap.add_argument("--force", action="store_true",
                    help="warm-prime: rebuild slots even if already current. "
                         "preview: bundle a non-graded run anyway, and override "
                         "the drive-run staleness guard (capture the scratch as "
                         "it stands now and watermark the bundle). Sandbox-reject "
                         "/ dirty-substrate runs are still refused. "
                         "refgate: regrade even where a valid gate certificate "
                         "would self-skip (a fresh PASS refreshes the cert).")

    # bench knobs.
    ap.add_argument("--repeat", type=int, default=3, metavar="N",
                    help="bench: repetitions per (model, task) pair (default: 3; "
                         "per-task override via --task <id>:N)")
    ap.add_argument("--prune-workdirs", action="store_true",
                    help="bench: delete each rep's verifier workdir right after its "
                         "grade (the verdict + report.json already live in the rep's "
                         "run dir). Since slim retention became the default this "
                         "reclaims only the ~42 MB slim remnant per rep, NOT the ~5.9 "
                         "GB it once did — retention already ran inside the drive. It "
                         "is still the way to reclaim the full workdir when the rep "
                         "was run with --keep-workdir, and the way to drop the "
                         "surviving out/ + Content/ bytes entirely.")
    ap.add_argument("--resume", nargs="?", const="__latest__", default=None,
                    metavar="BENCH_DIR",
                    help="bench: resume an interrupted run — reuse its GRADED "
                         "(PASS/FAIL) reps and re-run only errors/non-graded, "
                         "appending to the SAME bench dir. Bare --resume picks the "
                         "newest runs/bench-* DIRECTORY holding a readable "
                         "bench.json (stray bench-* files never match); or pass "
                         "an explicit bench dir.")
    ap.add_argument("--no-teardown", action="store_true",
                    help="keep a stack this invocation left resident instead of "
                         "handing it to the janitor at clean exit. A resident "
                         "stack starves the NEXT invocation's build - measured "
                         "2026-07-26 at 5x verify (118.5s -> 588.6s) on a "
                         "claude-p backend that never touches a stack, and "
                         "worth 9,033 MB of commit charge - so it means 'keep "
                         "it between MY runs', never 'keep it after I am gone'.")
    ap.add_argument("--teardown", action="store_true",
                    help="eval: stop the stack after this eval (eval has no "
                         "default teardown - interactive use amortizes one "
                         "editor launch across runs). REQUIRED for scripted "
                         "eval loops: a loop without it inherits an ever-staler "
                         "editor + Live Coding console (measured 5x verify; "
                         "commit exhaustion grades correct work as an agent "
                         "FAIL).")
    ap.add_argument("--wizard", action="store_true",
                    help="bench: force the interactive wizard (tasks -> models -> "
                         "reps -> confirm; ends by printing the equivalent flag "
                         "command). Bare `cb bench` in a terminal opens it "
                         "automatically; explicit --model/--task or a non-TTY "
                         "invocation keep the classic non-interactive run. (Known "
                         "limitation: literally typing both default values reads "
                         "as not-given and still opens it.)")
    ap.add_argument("--refgates", action="store_true",
                    help="bench: OPT IN to the per-task REFERENCE GATES — "
                         "before any token is spent, every distinct task's "
                         "committed reference is graded token-free "
                         "(run_task.py), and a FAIL aborts the whole matrix "
                         "with exit 9 + the task's verdict-evidence lines (a "
                         "reference FAIL is a harness/machine problem, not a "
                         "model's). Default OFF since 2026-08-06 (owner "
                         "decision — see _refgates_apply for the reasoning): "
                         "gate at authoring time with `cb refgate <task>`, "
                         "and at setup with `cb refgate --all`. Tasks holding "
                         "a valid gate certificate self-skip here too.")
    ap.add_argument("--skip-refgates", action="store_true",
                    help="bench: DEPRECATED no-op (2026-08-06) — reference "
                         "gates no longer run by default, so there is nothing "
                         "to skip. Accepted so existing scripts keep parsing; "
                         "prints a one-line notice. See --refgates and "
                         "`cb refgate`.")
    # `--all` (refgate's sweep) is a second `--a*` flag on this FLAT parser,
    # which would make the bare abbreviation `--a` AMBIGUOUS against --agent —
    # the exact incident class the PREFIX NOTE below documents (2026-07-25,
    # guarded by test_batch_eval.test_dash_a_still_abbreviates_to_agent). The
    # fix: `--a` is REGISTERED as an explicit alias on --agent (see below) —
    # argparse resolves an exact option-string match BEFORE prefix matching,
    # so `cb smoke --a <m>` keeps meaning --agent.
    ap.add_argument("--all", action="store_true", dest="refgate_all",
                    help="refgate: gate EVERY task with a committed reference "
                         "solution (the full sweep — same discovery as "
                         "`cb batch-eval --references all`). Certified tasks "
                         "self-skip, so repeat sweeps cost seconds; the first "
                         "one on a fresh machine is the fuller setup "
                         "certification alongside `cb smoke`.")
    # PREFIX NOTE (see the SPELLING IS LOAD-BEARING comment at --no-gate): NOT
    # spelled `--allow-*` — a second `--a*` flag re-breaks `cb smoke --a <m>`
    # (the exact 2026-07-25 incident that renamed --allow-fail to --no-gate;
    # test_batch_eval.test_dash_a_still_abbreviates_to_agent guards it). The
    # `--r*` prefix is already many flags deep, so no working abbreviation
    # changes. The dest keeps the term of art.
    ap.add_argument("--run-mismatched-cells", action="store_true",
                    dest="allow_mismatched_cells",
                    help="bench: run (model, task) cells the parse-time check "
                         "REFUSES by default — a baseline backend (claude-p/"
                         "openrouter: file tools, no editor) on an asset-"
                         "deliverable task (spec declares L2I) is a guaranteed "
                         "harness-reason FAIL, so a matrix refuses those cells "
                         "listing the offending pairs rather than silently "
                         "burning money on them. This flag runs them anyway "
                         "(the reps land as graded FAILs).")

    ap.add_argument("--session-pid", type=int, default=None,
                    help="up: DECLARE the process that owns the resident stack, "
                         "instead of inferring it from cb's ancestors. Ownership "
                         "transfers to this pid on clean exit, so the stack lives "
                         "until that process dies — then the janitor reaps it "
                         "exactly as before. Use it when cb has no surviving "
                         "ancestor to anchor to: an agent/CI harness that spawns a "
                         "FRESH shell per command has none, so the inferred anchor "
                         "is the launcher, which dies with cb and the stack is "
                         "reaped within a poll (measured 4/4 on 2026-08-11). This "
                         "DISABLES NOTHING — a dead declared owner is still an "
                         "orphan and still torn down.")
    ap.add_argument("--reuse-editor", action="store_true",
                    help="unreal-mcp eval: REUSE the running headless editor "
                         "instead of launching it fresh per run. Faster for "
                         "repeat/debug runs; the run then inherits the prior "
                         "one's in-editor state (output-log buffer, loaded "
                         "level). Default OFF: each `cb eval` gets a clean, "
                         "initialize-gated editor.")
    ap.add_argument("--no-preflight", action="store_true",
                    help="skip the ~2s environment gate (aura_rig.envgate) that "
                         "eval / batch-eval / discriminate / bench run "
                         "BEFORE any build or token spend (UE root, Live Coding "
                         "mutex, MAX_PATH workdir, RAM headroom, per-tier stack "
                         "facts). Env twin: CB_NO_PREFLIGHT=1.")
    # `--a` is an EXPLICIT alias, not decoration: with refgate's `--all` on the
    # same flat parser, prefix-matching alone would make a bare `--a`
    # ambiguous and kill `cb smoke --a <m>` (the 2026-07-25 incident class;
    # argparse resolves exact option strings before prefixes, so this pin
    # keeps the abbreviation working — guarded by
    # test_batch_eval.test_dash_a_still_abbreviates_to_agent).
    ap.add_argument("--agent", "--a", nargs="?", const="claude-p", default=None,
                    metavar="MODEL",
                    help="smoke: append ONE live graded eval after the deterministic "
                         "legs (SPENDS tokens). Bare --agent = claude-p; or any "
                         "ROUTABLE cb model slug (claude-p[:<model>], "
                         "unreal-mcp[:<model>], openrouter:<p/m>, bare:<p/m>). "
                         "A bare Aura account key is no longer a slug at all — "
                         "the lane it routed to is not part of this release — and "
                         "aura-mcp is refused up front, before any leg runs.")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    # Force UTF-8 stdout/stderr: on Windows a redirected pipe defaults to cp1252,
    # so any non-ASCII in a log line (arrows, em-dashes, ellipses) crashes the
    # whole run with UnicodeEncodeError BEFORE doing any work. cb logs are mostly
    # ASCII, but this makes the launcher robust to the occasional fancy char.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
        except (AttributeError, ValueError):
            pass
    # SCOPED help pre-scan: the parser is FLAT (one namespace for every
    # command), so argparse's own -h would dump every command's flags. Route
    # `cb help <cmd>` and `cb <cmd> --help|-h` to the curated per-command
    # help BEFORE argparse can intercept -h.
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if argv_list:
        from aura_rig import cli_help
        if (argv_list[0] == "help" and len(argv_list) > 1
                and argv_list[1] in set(_DISPATCH) | {"help"}):
            print(cli_help.render_command(argv_list[1]))
            return 0
        if (argv_list[0] in _DISPATCH
                and any(a in ("-h", "--help") for a in argv_list[1:])):
            print(cli_help.render_command(argv_list[0]))
            return 0
    parser = build_parser()
    args = parser.parse_args(argv_list)
    if args.command == "help":
        parser.print_help()
        return 0
    # A stray positional means the operator asked for something this command
    # cannot do — refuse BEFORE _Ctx probes the machine or a drive spends a cent.
    _stray = reject_stray_positionals(args)
    if _stray:
        _say(_stray)
        return 2
    ctx = _Ctx(args)
    # STARTUP RECONCILIATION (owner mandate 2026-08-07): every entry point
    # first checks the stack ownership manifest. A stack whose owner pid is
    # DEAD (hard-stopped/crashed/closed-console wrapper) is torn down HERE,
    # loudly, before the command proceeds — the self-heal for the night two
    # hard-stopped benches left the stack leaking to 70/84 GB commit. A live
    # owner that is another cb run makes stack-mutating commands refuse (the
    # live_lock exclusivity convention). Read-only commands only get the
    # notice; help/completions stay silent. Never raises.
    from aura_rig import stack_guard
    _recon_rc = stack_guard.reconcile_at_entry(args.command, log=_say)
    if _recon_rc is not None:
        return _recon_rc
    rc = _DISPATCH[args.command](ctx, args)
    # CLEAN-exit release: a stack THIS process brought up and deliberately
    # left resident transfers to the operator's SESSION (shell/wrapper), so
    # the janitor tears it down when the session dies — --no-teardown means
    # 'keep between MY runs', never 'keep after I'm gone'. A crash/hard-stop
    # never reaches this line, which is exactly the orphan signature the
    # janitor + reconciliation key on.
    stack_guard.release_at_exit(
        no_teardown=bool(getattr(args, "no_teardown", False)), log=_say)
    return rc


if __name__ == "__main__":
    sys.exit(main())
