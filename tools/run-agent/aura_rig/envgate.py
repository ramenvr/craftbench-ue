"""envgate — the FAST environment gate cb runs BEFORE any build or token spend.

Every ``cb eval`` / ``batch-eval`` / ``discriminate`` / ``bench`` / ``refgate``
now opens with this gate (opt out: ``--no-preflight`` / ``CB_NO_PREFLIGHT=1``).
It exists so a broken environment costs ~2 seconds and prints the exact fix,
instead of costing a 20-minute build (or a paid drive) and printing a raw
symptom. It is the enforcement half of the project's closure doctrine: an
environment incident counts as CLOSED only once its signature is auto-healed by
the harness or detected HERE, before it can spend anything.

Shape: identical to :mod:`aura_rig.doctor` — a PURE core (:func:`gate`) over a
pre-resolved facts dataclass (:class:`Facts`), a live resolver
(:func:`real_facts`), and a thin enforcing wrapper (:func:`enforce`) the cb
commands call. ``tests/test_cb_envgate.py`` drives :func:`gate` fully offline.

Deliberately NOT here:
  * anything needing HTTP — live health belongs to ``stack.snapshot`` /
    ``cb doctor``. This gate is FULLY OFFLINE, and that is what buys the ~2s
    promise: every probe below is a file stat, one process-list scan or a
    ctypes memory read, and a probe that cannot measure reports OK-skipped
    rather than becoming a verdict it could not support;
  * anything the harness already self-heals downstream (the gutted-junction
    git restore) — those get a WARN at most, never a duplicate FAIL;
  * per-task facts (spec resolution, map presence) — ``cb lint`` and the
    runner own those;
  * anything about the PRIVATE product rig this repository does not ship. An
    earlier third tier probed an entitled account, a browser login, client
    ports and a private plugin checkout on behalf of the ``aura-mcp`` arm.
    That arm is disclosed and dispatchable here but NOT reproducible from this
    repository, so those probes were deleted outright rather than left to
    fail: a gate row that can never pass is worse than no row, because it
    teaches the reader to scroll past the gate.

Tier is what the command is ABOUT TO DO, not what the machine could do
(contrast doctor's provisioned-for tiers):
    grade      deterministic L1/L2 verifies only (batch-eval / discriminate / smoke)
    baseline   grade + a shelled ``claude`` CLI. Every agent arm in this
               repository shells that CLI and differs only in its
               --mcp-config / --disallowed-tools (claude-p / openrouter /
               unreal-mcp / aura-mcp / bare), so there is no third tier.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

TIERS = ("grade", "baseline")

# Windows workdir roots longer than this hit MAX_PATH once the verifier's
# hash-dir + project tree lands under them (FAILURE-LOG 2026-07-10: WinError
# 206 mid-batch cost $2.76; 2026-06: cold-5.8 false FAILs). The C:\cb default
# is 5 chars — only a CB_ROOT/CRAFTBENCH_WD_ROOT override can exceed this.
MAX_WD_ROOT_LEN = 60

# WARN band for RAM: full-parallel editor PCH compiles exhaust the commit
# charge and cl.exe dies with C3859 (FAILURE-LOG 2026-06-21 / the repo conventions UE 5.8
# build tuning). The gate only warns — mem_gate owns runtime back-off.
RAM_WARN_PCT = 88.0

# COMMIT CHARGE is the real ceiling, and it is NOT what ram-headroom measures.
# Measured on the build box: cap 6 FAILs L1 deterministically (5/5,
# C3859 + C1076) *with 26 GB of commit headroom free* — a per-cl.exe PCH
# allocation failure under concurrency, not a spare-RAM question. RAM% and
# commit% diverge badly whenever something large is resident: measured on this
# box 2026-08-01 with a game running, RAM read 66% (probe: OK, well under 88)
# while commit sat at 96.3% (73.7 of 76.5 GB). A grade started in that state
# produces a C3859 that is recorded as THE AGENT FAILING THE TASK.
#
# 90% leaves ~7 GB on a 76 GB box — enough for one capped UBT build's cl.exe
# tree, which is what the build lock now guarantees is the most that runs at once.
COMMIT_WARN_PCT = 90.0

# The HARD FLOOR on free commit, in GB (owner mandate 2026-08-07). The % band
# above stays ADVISORY, but a MEASURED free-commit below this floor is a FAIL:
# the night of 2026-08-06/07 ended at 70/84 GB commit — an accumulated leak
# in the long-running services a bench leaves resident, plus orphaned editors
# — and a bench launched into that state loses editors silently and grades
# its C3859/exit-1 L1 deaths as the AGENT failing the task. 10 GB is one
# capped UBT build's cl.exe tree plus slack; tune per-box with
# CB_COMMIT_FLOOR_GB. WARN below 2x floor. NB: healthy readings on the
# fixed-pagefile box (limit 84+ GB) sit well above 2x floor; a box where an
# otherwise idle machine breaches the floor needs the pagefile fix (see the
# pagefile-floor probe), not a lower floor.
COMMIT_FLOOR_GB = 10.0

#: A bench's TRANSIENT commit demand, measured 2026-08-07 across both boxes
#: with the whole rig resident: the editor under drive ~7 GB (post the
#: ray-tracing-off fix; it was 19 GB before), the long-running services a
#: bench leaves up, plus the grade build's cl.exe tree. It is a FIXED cost
#: — it does not scale with installed RAM, which is why `pagefile-floor`
#: asks for it in absolute GB rather than as a ratio.
BENCH_COMMIT_DEMAND_GB = 25.0


def commit_floor_gb(env=None) -> float:
    """The effective free-commit hard floor: env ``CB_COMMIT_FLOOR_GB`` (first
    float token) else :data:`COMMIT_FLOOR_GB`. Unparseable/non-positive values
    read as the default — a typo must never disable the floor."""
    env = os.environ if env is None else env
    raw = (env.get("CB_COMMIT_FLOOR_GB") or "").strip()
    if raw:
        try:
            val = float(raw.split()[0])
            if val > 0:
                return val
        except (ValueError, IndexError):
            pass
    return COMMIT_FLOOR_GB

# One graded verifier workdir, RE-MEASURED 2026-07-26 across a 6-run flag-matrix
# sweep: 5.95 GB, the bulk of it <Project>/Intermediate/Build/Win64/x64 (MSVC
# .obj/.pch nobody reads) plus Binaries. Kept here so the check can report free
# space as "~N more evals" instead of a bare GB number the reader has to convert
# on sight.
#
# Was 5.54 (measured 2026-07-25). Two independent reads agree on 5.95 today: the
# one workdir deliberately retained with --keep-workdir measured 5.952 GB whole,
# and every slim run reported "reclaimed 5.91 GB" against a ~42 MB remnant
# (5.952 - 5.91 = 0.042). Being 7% LOW here is the wrong direction to be wrong —
# it makes the disk gate promise more remaining evals than the box can take.
WD_PER_EVAL_GB = 5.95

# Free-space bands for the drive holding the workdir root. The same 2026-07-25
# sweep found 24 workdirs holding 121 GB against 128 GB free — ~23 evals from a
# full disk with NO CLI path to reclaim, because `cb clean --workdirs`
# deliberately KEEPS every workdir a runs/**/summary.json still names in
# graded_workdir and `cb eval` has no prune flag at all.
#   40 GB (~7 evals) is runway enough to slim between batches -> WARN only.
#   15 GB is under three evals: a batch started there runs the disk dry
#   MID-BUILD, cl.exe fails on the write, L1 FAILs, and every remaining task
#   scores FAIL for a reason that has nothing to do with the agent. That is a
#   whole batch of tokens spent on a disk error -> FAIL, before the spend.
WD_FREE_WARN_GB = 40.0
WD_FREE_FAIL_GB = 15.0

# A Windows 8.3 short-name path segment: a literal '~' followed by a digit
# (SHORT~1, PROGRA~2, ...). FAILURE-LOG 2026-07-25: %TEMP% on the testbed host
# reads C:\Users\SHORT~1\AppData\Local\Temp, and a verify workdir minted under
# it took `cb batch-eval --references all` to 0/15 — every L2 leg exit_code 3 ->
# status "skipped" -> FAIL, because the leg could not retrieve its automation
# result from a -ReportExportPath spelled in short form.
# A real 8.3 alias puts the ``~N`` at the END of the name part: SHORT~1,
# PROGRA~1, LOCALS~1.CDE. Anchoring there keeps an ordinary directory that
# merely CONTAINS a tilde-digit (``my~2project``, ``backup~1notes``) from
# tripping the probe — `.search()` on a bare ``~[0-9]`` matched mid-segment.
_SHORT_NAME_SEG = re.compile(r"~[0-9]+(?:\.[^.\\/]{0,3})?$")


def has_8dot3_component(path: str) -> bool:
    """True when any segment of ``path`` is a Windows 8.3 short name.

    Segment-wise on purpose: a '~' elsewhere in a path (a backup suffix, a POSIX
    home shorthand) is not an 8.3 name and must not trip the probe.
    """
    if not path:
        return False
    return any(_SHORT_NAME_SEG.search(seg) for seg in re.split(r"[\\/]+", path))


def _norm_root(path: str) -> str:
    """Comparison form for a repo root: separators unified, trailing separator
    dropped, casefolded. Pure (no filesystem) — real_facts already resolve()d
    both roots; this only removes spelling noise so two spellings of ONE clone
    never read as a mismatch (a false BLOCKER here stops a healthy run)."""
    return os.path.normpath(path).replace("\\", "/").rstrip("/").casefold()


# --------------------------------------------------------------------------- #
# (1) Facts — every live value the pure core needs, pre-resolved.              #
# --------------------------------------------------------------------------- #

@dataclass
class Facts:
    # --- grade tier ---
    ue_root: Optional[str]              # resolved UE install root (None = not found)
    wd_root: str                        # verifier workdir root (paths.wd_root())
    is_windows: bool
    live_coding: int                    # running LiveCodingConsole processes
    ram_pct: Optional[float]            # None = no probe available (psutil/ctypes)
    l1_cap: Optional[str]               # CRAFTBENCH_L1_MAX_PARALLEL (None = unset)
    commit_pct: Optional[float] = None  # % of the system commit LIMIT in use.
    #   ^ The quantity that actually gates a UBT build (see COMMIT_WARN_PCT).
    #     Placed after every non-defaulted field (dataclasses forbid the reverse)
    #     and DEFAULTED so the ~40 existing Facts(...) constructions in the test
    #     suite keep working unchanged; None means "unmeasured", which reports
    commit_free_gb: Optional[float] = None   # remaining commit charge, in GB
    #   ^ The ABSOLUTE headroom the hard floor gates on (owner mandate
    #     2026-08-07): commit_pct alone cannot say whether "90%" leaves 2 GB or
    #     20 GB, and the quantity a cl.exe allocation actually needs is GB, not
    #     percent. Same Optional-default contract as commit_pct: None means
    #     "unmeasured", reports OK-skipped, never becomes a verdict.
    commit_floor_gb: Optional[float] = None  # effective floor (env-resolved)
    #   ^ real_facts resolves CB_COMMIT_FLOOR_GB here so gate() stays pure
    #     (no env reads). None -> the COMMIT_FLOOR_GB default applies.
    commit_limit_gb: Optional[float] = None  # the commit LIMIT itself (RAM+pagefile)
    ram_total_gb: Optional[float] = None     # physical RAM
    #   ^ For the pagefile-floor CONFIG check (2026-08-04): commit_pct is a
    #     LOAD reading and can be healthy at gate time while the limit itself
    #     is the hazard — a system-managed pagefile sized ~9 GB put this box's
    #     limit at RAM+9; a 6-rep bench then drove free commit to 0 mid-run,
    #     where Windows' just-in-time pagefile growth lags burst allocations
    #     (cl.exe PCH) and an L1 dies with exit 1 / ZERO compile errors —
    #     graded as the agent failing. Same Optional-default contract as
    #     commit_pct: absent measurement is never a verdict.
    #     OK-skipped and never becomes a verdict — the same contract ram_pct holds.
    startup_task_maps: List[str] = field(default_factory=list)
    #   ^ "<substrate>: <Key>=/Game/Maps/..." rows — Default*/Startup map keys
    #     pointing INTO task maps (the fairness-lock crash, FAILURE-LOG 2026-07-10)
    temp_root: str = ""
    #   ^ tempfile.gettempdir() VERBATIM — the root the verifier's DEFAULT (no
    #     --keep) cold workdir is minted under. This is NOT wd_root: wd_root is
    #     the CB_ROOT\wd tree used only when --keep is on, which is exactly why
    #     the workdir-short probe printed "5 checks OK" right before all 15
    #     tasks failed on 2026-07-25.
    temp_root_canonical: str = ""
    #   ^ its Path.resolve()d form ("" = resolution raised). Equal to temp_root
    #     on a clean host; the LONG form when temp_root carries an 8.3 name.
    wd_free_gb: Optional[float] = None
    stale_wd_root: Optional[str] = None   # a RETIRED root that still holds data
    #   ^ free space (decimal GB) on wd_root's DRIVE; None = probe unavailable.
    #     Optional-with-a-default on purpose, and NOT hoisted up next to wd_root
    #     where it reads better: tests/test_cb_envgate.py's _all_good() literal
    #     is the everything-OK Facts every test flips one field of, it does not
    #     name this field, and a required one would break test_all_ok. Same
    #     contract as ram_pct — an absent measurement is never a verdict.
    rig_pkg_root: Optional[str] = None
    #   ^ repo root of the aura_rig package THIS process imported (derived from
    #     aura_rig.__file__, pre-resolve()d; None = underivable — a frozen or
    #     namespace import). A stale GLOBAL editable install points it at a
    #     DIFFERENT clone (FAILURE-LOG 2026-08-04: bare `py -3 -m aura_rig.cb`
    #     resolved from C:\Users\hello\cbtest and the wrong code ran, presenting
    #     as import errors). Same Optional-default contract as ram_pct.
    cmd_repo_root: Optional[str] = None
    #   ^ repo root the command OPERATES in, pre-resolve()d. CWD-anchored (see
    #     _read_cmd_repo_root): StackPaths.craftbench derives from the SAME
    #     hijacked __file__, so the checkout the operator is standing in is the
    #     only anchor a stale editable install cannot move.
    #   ^ Film-strip caption burn-in dependency (owner decision 2026-08-05).
    #     None  = probe skipped (film strip or burn-in opted out via
    #     ram_pct: tests' _all_good() literal does not name it.
    # --- baseline tier ---
    claude_cli: Optional[str] = None    # shutil.which result


# --------------------------------------------------------------------------- #
# (2) GateCheck + the pure core.                                               #
# --------------------------------------------------------------------------- #

@dataclass
class GateCheck:
    id: str
    status: str          # 'OK' | 'WARN' | 'FAIL'
    detail: str
    fix: str = ""        # exact command / edit — REQUIRED for WARN/FAIL


def gate(facts: Facts, tier: str) -> List[GateCheck]:
    """The pure core: Facts + tier -> ordered checks. No I/O, no env reads."""
    if tier not in TIERS:
        raise ValueError(f"unknown envgate tier: {tier!r}")
    checks: List[GateCheck] = []

    def add(id: str, ok: bool, detail_ok: str, detail_bad: str, fix: str,
            *, miss: str = "FAIL") -> None:
        checks.append(GateCheck(
            id=id, status="OK" if ok else miss,
            detail=detail_ok if ok else detail_bad, fix="" if ok else fix))

    # ------------------------------ grade ------------------------------- #
    # RIG PROVENANCE — is the code running this gate the code THIS repo holds?
    # A stale GLOBAL editable install resolves bare `py -3 -m aura_rig.cb` from
    # a DIFFERENT clone, and wrong code presents as confusing import errors,
    # never as "wrong repo" (FAILURE-LOG 2026-08-04: C:\Users\hello\cbtest).
    # First in the list: every check below it would be the OTHER clone's code.
    if facts.rig_pkg_root is None or facts.cmd_repo_root is None:
        checks.append(GateCheck("rig-provenance", "OK",
                                "rig provenance roots unresolvable - skipped"))
    elif _norm_root(facts.rig_pkg_root) == _norm_root(facts.cmd_repo_root):
        checks.append(GateCheck(
            "rig-provenance", "OK",
            f"aura_rig runs from this repo ({facts.rig_pkg_root})"))
    else:
        checks.append(GateCheck(
            "rig-provenance", "FAIL",
            f"the RUNNING aura_rig package resolves from a DIFFERENT clone: "
            f"{facts.rig_pkg_root} (this command operates on "
            f"{facts.cmd_repo_root}) - a stale global editable install hijacks "
            "bare `py -3 -m aura_rig.cb`, so that clone's code runs here and "
            "presents as confusing import errors",
            "Run via the repo shim (.\\cb <cmd> / ./cb <cmd>), or repoint the "
            "editable install at THIS repo:  pip install -e tools/run-agent   "
            f"(from {facts.cmd_repo_root})."))

    add("ue-root", facts.ue_root is not None,
        f"UE root: {facts.ue_root}",
        "UE 5.8 install not found",
        "Install UE 5.8 (default C:\\Program Files\\Epic Games\\UE_5.8) or point the "
        "harness at it:  cb <cmd> --ue-root \"<path>\"   or set CB_UE_ROOT in .env.")

    wd_ok = (not facts.is_windows) or len(facts.wd_root) <= MAX_WD_ROOT_LEN
    add("workdir-short", wd_ok,
        f"workdir root: {facts.wd_root}",
        f"workdir root is {len(facts.wd_root)} chars: {facts.wd_root}",
        "Long workdirs hit Windows MAX_PATH mid-build (WinError 206/3, false FAILs). "
        "Set CB_ROOT to a short root, e.g.  setx CB_ROOT C:\\cb   (workdirs land at "
        "<CB_ROOT>\\wd).")

    # The workdir-short probe above only ever looked at CB_ROOT\wd — the root
    # used when --keep is ON. With --keep OFF (the batch-eval default) the cold
    # verify workdir is an mkdtemp under %TEMP%, and THAT is the path that scored
    # `cb batch-eval --references all` 0/15 on 2026-07-25 while preflight
    # cheerfully printed "grade: 5 checks OK". Probe the root actually used.
    #
    # Heal-CONFIRMING, not blocking (FAILURE-LOG closure doctrine): run_task's
    # new_temp_workdir() canonicalizes the mkdtemp path, so a short name that
    # EXPANDS is already auto-healed and reports OK with the expansion named —
    # a WARN on every run of this host would be pure noise. What we cannot heal
    # is a short name with no long form to expand to (8.3 aliasing without a
    # resolvable target, or a resolve() that raised); that stays a WARN with the
    # exact TEMP override, because there the 0/N wipeout is still live.
    if facts.is_windows and has_8dot3_component(facts.temp_root):
        canon = facts.temp_root_canonical
        if canon and not has_8dot3_component(canon):
            checks.append(GateCheck(
                "temp-8dot3", "OK",
                f"temp workdir root {facts.temp_root} carries an 8.3 short name; "
                f"canonicalizes to {canon} (the runner expands it before use)"))
        else:
            checks.append(GateCheck(
                "temp-8dot3", "WARN",
                f"temp workdir root {facts.temp_root} carries an 8.3 short name that "
                f"does NOT expand (resolved: {canon or '<unresolvable>'}) - the L2 leg "
                "cannot retrieve its automation result under a short -ReportExportPath, "
                "so EVERY task returns exit_code 3 / status skipped and scores FAIL",
                "Point TEMP+TMP at a short, 8.3-free root for the run:  "
                "set TEMP=C:\\cbtmp && set TMP=C:\\cbtmp   (or pass --keep, which lands "
                "workdirs under <CB_ROOT>\\wd instead). A 0/N batch-eval with L1 pass + "
                "L2 skipped is ALWAYS this."))
    else:
        checks.append(GateCheck(
            "temp-8dot3", "OK",
            f"temp workdir root has no 8.3 short component "
            f"({facts.temp_root or 'unprobed'})"))

    add("live-coding", facts.live_coding == 0,
        "no LiveCodingConsole running (UBT build lock free)",
        f"{facts.live_coding} LiveCodingConsole.exe running - EVERY UBT build on this "
        "machine will fail in ~13s (exit 6) while it holds the Live Coding mutex",
        "Close the open Unreal editor (or its Live Coding console), or run  cb down  . "
        "A wall of ~13s L1 FAILs is ALWAYS this.")

    # The L1 cap is honored as a leading integer (l1_build.py) - a set-but-
    # unparseable value would build uncapped, so flag it BEFORE the build.
    cap_m = re.match(r"[0-9]+", facts.l1_cap.strip()) if facts.l1_cap else None
    if facts.l1_cap and not cap_m:
        add("l1-cap-value", False,
            "CRAFTBENCH_L1_MAX_PARALLEL parses",
            f"CRAFTBENCH_L1_MAX_PARALLEL={facts.l1_cap!r} has no leading number - "
            "the L1 parallel cap would be IGNORED (C3859 risk)",
            "Make the value a bare integer (e.g.  set CRAFTBENCH_L1_MAX_PARALLEL=2 ); "
            "keep comments on their own line in .env.",
            miss="WARN")

    if facts.ram_pct is None:
        checks.append(GateCheck("ram-headroom", "OK",
                                "RAM probe unavailable (psutil/ctypes) - skipped"))
    else:
        ram_ok = facts.ram_pct < RAM_WARN_PCT
        cap_note = (f"CRAFTBENCH_L1_MAX_PARALLEL={cap_m.group()}" if cap_m
                    else "CRAFTBENCH_L1_MAX_PARALLEL unset")
        add("ram-headroom", ram_ok,
            f"RAM {facts.ram_pct:.0f}% used ({cap_note})",
            f"RAM already {facts.ram_pct:.0f}% used - full-parallel editor PCH compiles "
            f"will exhaust the commit charge and cl.exe dies with C3859 ({cap_note})",
            "Close memory hogs, or cap UBT:  set CRAFTBENCH_L1_MAX_PARALLEL=4  "
            "(32 GB boxes). The verifier's mem gate backs off at runtime, but starting "
            "this high wastes a build attempt.",
            miss="WARN")

    # COMMIT HEADROOM — the ceiling ram-headroom above does NOT measure.
    # Kept as a SEPARATE check rather than folded into ram-headroom so the
    # output names which quantity is actually short: the two diverge (RAM 66% /
    # commit 96% was a real reading on this box), and "RAM is fine" is exactly
    # the wrong thing to tell someone whose next build is about to die of C3859.
    #
    # TWO legs since 2026-08-07 (owner mandate, after the 70/84 GB night):
    #   * the ABSOLUTE hard floor on MEASURED free commit (COMMIT_FLOOR_GB,
    #     env CB_COMMIT_FLOOR_GB) — the ONLY FAIL route. Below it a bench is
    #     guaranteed to lose editors / L1s to allocation deaths recorded as
    #     the agent's, so refusing pre-spend is the cheap outcome. WARN below
    #     2x floor.
    #   * the % band (COMMIT_WARN_PCT) — advisory as before; a percent
    #     cannot say how many GB remain.
    # An unmeasured quantity stays out of the verdict, per the standing
    # contract (commit_free_gb=None can never FAIL).
    if facts.commit_pct is None and facts.commit_free_gb is None:
        checks.append(GateCheck("commit-headroom", "OK",
                                "commit probe unavailable (ctypes) - skipped"))
    else:
        _commit_limit = COMMIT_WARN_PCT
        _floor = (facts.commit_floor_gb if facts.commit_floor_gb
                  else COMMIT_FLOOR_GB)
        _free = facts.commit_free_gb
        _pct_s = (f"commit {facts.commit_pct:.0f}% of limit in use"
                  if facts.commit_pct is not None else "commit % unmeasured")
        _free_s = (f"{_free:.1f} GB free" if _free is not None
                   else "free-commit unmeasured")
        _leak_fix = (
            "Run  cb down  first - tearing down what the harness left "
            "resident returns commit charge (an orphaned editor holds GBs "
            "for hours). Then check Task Manager > Details > Commit size "
            "for what remains. Floor tunable: CB_COMMIT_FLOOR_GB (default "
            f"{COMMIT_FLOOR_GB:.0f}).")
        if _free is not None and _free < _floor:
            checks.append(GateCheck(
                "commit-headroom", "FAIL",
                f"only {_free:.1f} GB of commit charge free (hard floor "
                f"{_floor:.0f} GB; {_pct_s}) - cl.exe PCH allocation fails "
                "under concurrency (C3859/C1076) and the L1 death is recorded "
                "as the AGENT failing the task; editors die silently at "
                "this level (measured 2026-08-07 at 70/84 GB)",
                _leak_fix))
        elif ((_free is not None and _free < 2 * _floor)
              or (facts.commit_pct is not None
                  and facts.commit_pct >= _commit_limit)):
            checks.append(GateCheck(
                "commit-headroom", "WARN",
                f"commit headroom is thin: {_free_s}, {_pct_s} (hard floor "
                f"{_floor:.0f} GB, warn under {2 * _floor:.0f} GB or over "
                f"{_commit_limit:.0f}% for the {tier} tier) - a long "
                "bench/build can cross the floor mid-run and die C3859, "
                "graded as an agent FAIL",
                _leak_fix))
        else:
            checks.append(GateCheck(
                "commit-headroom", "OK",
                f"{_pct_s} ({_free_s}; hard floor {_floor:.0f} GB, warn at "
                f"{_commit_limit:.0f}% for the {tier} tier)"))

    # PAGEFILE FLOOR — a CONFIG check, deliberately separate from the LOAD
    # check above. commit-headroom reads healthy at gate time and then a long
    # bench grows into the ceiling mid-run (measured 2026-08-04: gate-time 29 GB
    # free, rep 5 free commit 0; Windows' just-in-time pagefile growth lags
    # burst cl.exe PCH allocations, and the resulting L1 exit-1-with-zero-
    # compile-errors grades as the AGENT failing). A commit limit close to bare
    # RAM means the pagefile is system-managed-small — detectable before any
    # spend, independent of current load.
    if facts.commit_limit_gb is None or facts.ram_total_gb is None:
        checks.append(GateCheck("pagefile-floor", "OK",
                                "commit-limit probe unavailable (ctypes) - skipped"))
    else:
        # ABSOLUTE headroom, not a ratio to RAM (corrected 2026-08-07 after
        # the ratio MISSED this very box). A bench's transient commit demand is
        # a fixed ~25 GB — the editor under drive, the services a bench leaves
        # resident, and the grade build's cl.exe tree — and it does not scale
        # with how much RAM you have. The 1.25x rule therefore gets LOOSER
        # exactly where headroom is scarcest:
        # measured here at 84.6 GB limit / 61.6 GB RAM = 1.37x, it PASSED, and
        # the next bench still hit the floor mid-drive. Same arithmetic, stated
        # as the question that actually matters: is there room for a bench
        # ABOVE what RAM alone covers? 84.6 >= 61.6+25 is FALSE (would have
        # fired); after the explicit pagefile, 109.6 >= 86.6 is TRUE.
        add("pagefile-floor",
            facts.commit_limit_gb >= facts.ram_total_gb + BENCH_COMMIT_DEMAND_GB,
            f"commit limit {facts.commit_limit_gb:.0f} GB = RAM "
            f"{facts.ram_total_gb:.0f} GB + "
            f"{facts.commit_limit_gb - facts.ram_total_gb:.0f} GB pagefile "
            f"(need >= {BENCH_COMMIT_DEMAND_GB:.0f} GB of pagefile for a bench)",
            f"commit limit {facts.commit_limit_gb:.0f} GB leaves only "
            f"{facts.commit_limit_gb - facts.ram_total_gb:.0f} GB above RAM "
            f"({facts.ram_total_gb:.0f} GB), and a bench needs ~"
            f"{BENCH_COMMIT_DEMAND_GB:.0f} GB of transient commit - it will "
            f"exhaust the limit MID-RUN, and the resulting L1/editor death is "
            f"graded as an agent FAIL",
            "Windows' own lazy expansion does NOT save you: it engages only "
            "under paging pressure, not commit pressure, and the build machine "
            "measured a live expansion (63.9 -> 88.4 GB) TRIMMED BACK within "
            "~2 min of release. Only an explicit Initial=Max + reboot is a "
            "durable ceiling. Set it (elevated PowerShell):  "
            "$cs=Get-CimInstance Win32_ComputerSystem; "
            "$cs.AutomaticManagedPagefile=$false; Set-CimInstance $cs;  then "
            "Win32_PageFileSetting InitialSize=32768 MaximumSize=65536 and "
            "reboot BETWEEN matrices.",
            miss="WARN")

    # The disk wall, probed BEFORE the spend. This is the enforcement half of
    # the 2026-07-25 retention work (FAILURE-LOG closure doctrine: ship the
    # probe with the fix) — the leak that put 24 workdirs / 121 GB against
    # 128 GB free had no exit until `cb clean --workdirs --slim` existed, and a
    # run that discovers the wall 40 minutes into an L1 build has already paid
    # for the whole batch. A full disk does NOT present as "disk full": it
    # presents as cl.exe failing a write -> L1 FAIL -> task FAIL, i.e. it is
    # indistinguishable from a bad agent unless something says so up front.
    if facts.wd_free_gb is None:
        checks.append(GateCheck("wd-disk", "OK",
                                "disk probe unavailable - skipped"))
    elif facts.wd_free_gb >= WD_FREE_WARN_GB:
        checks.append(GateCheck(
            "wd-disk", "OK",
            f"workdir drive: {facts.wd_free_gb:.0f} GB free "
            f"(~{facts.wd_free_gb / WD_PER_EVAL_GB:.0f} more graded workdirs at "
            f"{WD_PER_EVAL_GB:.2f} GB each) - {facts.wd_root}"))
    else:
        blocking = facts.wd_free_gb < WD_FREE_FAIL_GB
        checks.append(GateCheck(
            "wd-disk", "FAIL" if blocking else "WARN",
            f"only {facts.wd_free_gb:.0f} GB free on the workdir drive "
            f"({facts.wd_root}) - a graded workdir is {WD_PER_EVAL_GB:.2f} GB, so "
            f"that is ~{facts.wd_free_gb / WD_PER_EVAL_GB:.0f} more eval(s)"
            + (" and a batch that runs the disk dry mid-build FAILs every "
               "remaining task on a write error, not on the agent" if blocking
               else ""),
            "cb clean --workdirs --slim --check   previews the reclaim; drop "
            "--check to run it. Slim keeps out/ + Binaries/ (the graded project "
            "still launches and still explains its verdict) and drops the "
            "Intermediate/Build tree that is ~85% of every workdir."))

    # A STALE workdir root is invisible debris: wd_root() moved from the old
    # C:\cbwd default to <CB_ROOT>/wd (paths.wd_root: "Old default C:\cbwd is
    # retired"), but the docs kept publishing C:\cbwd long after, so boxes
    # provisioned from them still have one. Nothing scans it — `cb clean
    # --workdirs` only ever walks the CURRENT root — so it just grows. A second
    # machine was found holding 325 GB there on 2026-07-25, more than the live
    # root. WARN, never FAIL: it costs disk, not correctness, and the remedy is
    # a delete the operator must authorise.
    if facts.stale_wd_root:
        checks.append(GateCheck(
            "wd-stale-root", "WARN",
            f"a RETIRED workdir root still holds data: {facts.stale_wd_root} "
            f"(live root is {facts.wd_root}) - nothing prunes it",
            "This is left over from the old CRAFTBENCH_WD_ROOT default. Confirm "
            "it is not your live root (`cb where`), then delete it by hand - "
            "`cb clean --workdirs` only ever walks the CURRENT root."))

    add("startup-maps", not facts.startup_task_maps,
        "no Default*/Startup map points at a task map",
        "substrate Default*/Startup map points INTO Content/Maps: "
        + "; ".join(facts.startup_task_maps),
        "A live editor LOCKS its startup map -> WinError 32 tree-isolation crashes on "
        "every eval of a DIFFERENT task. Point Default*Map at /Engine/Maps/Entry in the "
        "substrate DefaultEngine.ini. (Rule: Default* maps NEVER "
        "point at a task map).")

    # FILM-STRIP CAPTION BURN-IN dependency (owner decision 2026-08-05).

    # ----------------------------- baseline ----------------------------- #
    if tier == "baseline":
        add("claude-cli", facts.claude_cli is not None,
            f"claude CLI: {facts.claude_cli}",
            "claude CLI not on PATH - this backend shells `claude -p` and cannot run",
            "Install Claude Code (https://claude.com/claude-code) so `claude` resolves, "
            "then re-run. openrouter:* reuses the same CLI with env overrides.")

    return checks


# --------------------------------------------------------------------------- #
# (3) real_facts — the ONLY place that touches the machine. Fast: NO HTTP at   #
#     all, one process-list scan, a few stats and the substrate .ini reads.    #
# --------------------------------------------------------------------------- #

_STARTUP_KEYS = re.compile(
    r"^(GameDefaultMap|EditorStartupMap|ServerDefaultMap|TransitionMap)\s*=\s*(.+)$",
    re.MULTILINE)


def _scan_startup_maps(ue_projects: Path) -> List[str]:
    """Rows for Default*/Startup map keys pointing INTO /Game/Maps/ across ALL
    committed substrates (CraftBenchTemplate, ThirdPerson, ...)."""
    rows: List[str] = []
    try:
        substrates = [d for d in ue_projects.iterdir() if d.is_dir()]
    except OSError:
        return rows
    for sub in substrates:
        ini = sub / "Config" / "DefaultEngine.ini"
        try:
            text = ini.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for key, val in _STARTUP_KEYS.findall(text):
            if "/Game/Maps/" in val:
                rows.append(f"{sub.name}: {key}={val.strip()}")
    return rows


def _read_commit_pct() -> Optional[float]:
    """Percent of the SYSTEM COMMIT LIMIT in use, or None when unmeasurable.

    Windows-only and deliberately ctypes-direct: psutil's ``virtual_memory()``
    reports physical RAM, which is the quantity that reads healthy while a build
    is about to die. ``GlobalMemoryStatusEx`` exposes the commit totals
    (``ullTotalPageFile`` / ``ullAvailPageFile`` are the commit LIMIT and the
    remaining commit, not a pagefile-only figure).

    Returns None rather than raising on any platform or API problem — an absent
    measurement must never become a verdict, the same contract ram_pct holds.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        limit = float(stat.ullTotalPageFile)
        if limit <= 0:
            return None
        used = limit - float(stat.ullAvailPageFile)
        return max(0.0, min(100.0, 100.0 * used / limit))
    except Exception:  # noqa: BLE001 — a probe must never abort the gate
        return None


def _read_commit_free_gb() -> Optional[float]:
    """Remaining commit charge in GB (``ullAvailPageFile``), or None.

    The quantity the COMMIT_FLOOR_GB hard floor gates on, and the one the
    pre-rep pressure hook (``stack_guard.ensure_commit_headroom``) re-reads
    mid-bench. Self-contained ctypes on purpose, like its two siblings — each
    probe stays independently None-able, and an absent measurement is never a
    verdict."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        return float(stat.ullAvailPageFile) / (1024.0 ** 3)
    except Exception:  # noqa: BLE001 — a probe must never abort the gate
        return None


def _read_commit_limit_and_ram_gb() -> Tuple[Optional[float], Optional[float]]:
    """(commit limit GB, physical RAM GB) via GlobalMemoryStatusEx, or
    (None, None). Separate from _read_commit_pct on purpose — each probe stays
    self-contained and independently None-able (the gate's standing contract)."""
    if os.name != "nt":
        return None, None
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None, None
        gb = 1024.0 ** 3
        limit = float(stat.ullTotalPageFile) / gb
        ram = float(stat.ullTotalPhys) / gb
        return (limit if limit > 0 else None), (ram if ram > 0 else None)
    except Exception:  # noqa: BLE001 — a probe must never abort the gate
        return None, None


def _read_ram_pct() -> Optional[float]:
    from aura_rig import mem_gate
    for reader in (mem_gate._read_usage_psutil, mem_gate._read_usage_ctypes_windows):
        try:
            usage = reader()
        except Exception:
            usage = None
        if usage is not None:
            return float(usage[0])
    return None


_RETIRED_WD_ROOTS = (r"C:\cbwd",)


def _read_stale_wd_root(live_root) -> Optional[str]:
    """A retired workdir root that still exists AND holds something, or None.

    Only reports a root that is NOT the live one (an operator who deliberately
    set CRAFTBENCH_WD_ROOT=C:\\cbwd is not stale, just old-fashioned), and only
    when it is non-empty — an empty leftover dir is noise, not debris."""
    try:
        live = Path(live_root).resolve()
    except (OSError, ValueError):
        live = None
    for cand in _RETIRED_WD_ROOTS:
        p = Path(cand)
        try:
            if not p.is_dir():
                continue
            if live is not None and p.resolve() == live:
                continue
            if next(p.iterdir(), None) is None:
                continue
        except OSError:
            continue
        return str(p)
    return None


def _read_wd_free_gb(root) -> Optional[float]:
    """Free space (decimal GB) on the drive holding ``root``, or None.

    Walks UP to the first EXISTING ancestor: ``shutil.disk_usage`` needs a path
    that exists, and ``<CB_ROOT>\\wd`` is created lazily by the first verify —
    probing a fresh box would raise FileNotFoundError and report the check as
    "unavailable" on exactly the machine with the most disk left to lose. The
    drive is the same either way, which is the only thing this measures.

    Decimal GB (1e9), matching the unit ``cb clean --workdirs`` and
    ``workdir_retention`` already print reclaims in — a probe that reported GiB
    would name a smaller number than the reclaim command promises to free.

    Never raises: the gate reads None as "skipped", which beats a preflight that
    dies measuring free space."""
    import shutil

    try:
        p = Path(root)
        for cand in (p, *p.parents):
            if cand.exists():
                return shutil.disk_usage(str(cand)).free / 1e9
    except Exception:  # noqa: BLE001 - a probe is never worth an outage
        return None
    return None


# A file only a craftbench checkout holds, used to walk CWD up to its repo
# root. The rig module itself (not e.g. the .git dir) so a bare worktree or a
# partial copy without the rig never counts as "a checkout to operate on".
_REPO_MARKER = ("tools", "run-agent", "aura_rig", "cb.py")


def _read_rig_repo_root() -> Optional[str]:
    """Repo root of the aura_rig package THIS process imported, or None.

    Derived from ``aura_rig.__file__`` exactly the way StackPaths derives the
    craftbench root (parents[3] of a module inside aura_rig/). None on any
    oddity — a frozen/namespace import with no ``__file__``, a path too shallow
    to hold a repo — because an absent measurement is never a verdict."""
    try:
        import aura_rig
        f = getattr(aura_rig, "__file__", None)
        if not f:
            return None
        return str(Path(f).resolve().parents[3])
    except Exception:  # noqa: BLE001 — a probe must never abort the gate
        return None


def _read_cmd_repo_root(ctx_root) -> Optional[str]:
    """The repo root this command OPERATES in, pre-resolved for comparison.

    CWD-anchored first: the checkout the operator is STANDING in is the one
    they mean, and it is the only anchor a stale editable install cannot move —
    ``StackPaths.craftbench`` derives from the same hijacked ``__file__``, so
    in the 2026-08-04 incident ctx and package agreed on the WRONG clone.
    Falls back to ``ctx_root`` when the CWD is not inside any checkout (an
    installed ``cb`` run from an arbitrary dir), which still covers an explicit
    CB_CRAFTBENCH pointing somewhere the package is not."""
    try:
        p = Path.cwd().resolve()
        for cand in (p, *p.parents):
            if cand.joinpath(*_REPO_MARKER).is_file():
                return str(cand)
    except Exception:  # noqa: BLE001 — a probe must never abort the gate
        pass
    try:
        return str(Path(ctx_root).resolve())
    except Exception:  # noqa: BLE001
        return str(ctx_root) if ctx_root else None


def real_facts(ctx, tier: str) -> Facts:  # pragma: no cover - live wiring
    import shutil as _shutil

    from aura_rig import paths as cb_paths
    from aura_rig import stack

    paths = ctx.paths
    ue_root = os.environ.get("CB_UE_ROOT") or (
        str(ctx.ue.parents[3]) if ctx.ue is not None else None)

    try:
        live_coding = stack.count_image("LiveCodingConsole")
    except Exception:
        live_coding = 0

    # The EFFECTIVE default workdir root: gettempdir() is exactly what
    # run_task's mkdtemp branch roots in, so probe the same string the runner
    # will see rather than re-deriving it from %TEMP% by hand.
    temp_root = tempfile.gettempdir()
    try:
        temp_root_canonical = str(Path(temp_root).resolve())
    except OSError:
        temp_root_canonical = ""

    # ONE wd-root resolution feeds both the MAX_PATH probe and the free-space
    # probe — a second cb_paths.wd_root() call could disagree with the first if
    # CB_ROOT moved mid-process, and then the two checks would be talking about
    # different drives.
    wd_root = cb_paths.wd_root()

    facts = Facts(
        ue_root=ue_root,
        wd_root=str(wd_root),
        is_windows=(os.name == "nt"),
        live_coding=live_coding,
        ram_pct=_read_ram_pct(),
        commit_pct=_read_commit_pct(),
        commit_free_gb=_read_commit_free_gb(),
        commit_floor_gb=commit_floor_gb(),
        commit_limit_gb=(lambda _t: _t[0])(_read_commit_limit_and_ram_gb()),
        ram_total_gb=(lambda _t: _t[1])(_read_commit_limit_and_ram_gb()),
        l1_cap=os.environ.get("CRAFTBENCH_L1_MAX_PARALLEL"),
        startup_task_maps=_scan_startup_maps(paths.craftbench / "UE-projects"),
        temp_root=temp_root,
        temp_root_canonical=temp_root_canonical,
        wd_free_gb=_read_wd_free_gb(wd_root),
        stale_wd_root=_read_stale_wd_root(wd_root),
        rig_pkg_root=_read_rig_repo_root(),
        cmd_repo_root=_read_cmd_repo_root(paths.craftbench),
    )


    if tier == "baseline":
        facts.claude_cli = (_shutil.which("claude") or _shutil.which("claude.cmd")
                            or _shutil.which("claude.exe"))

    return facts


# --------------------------------------------------------------------------- #
# (4) enforce — the thin wrapper cb commands call.                             #
# --------------------------------------------------------------------------- #

def tier_for_model(model_slug: str, backend_of: Callable[[str], str]) -> str:
    """Map a cb --model slug to the envgate tier (pure; unit-tested).

    Always ``baseline`` for an agent slug. Every arm in this repository shells
    the same ``claude`` CLI and differs only in its --mcp-config /
    --disallowed-tools, so the CLI is the whole of what a slug can add to the
    grade-tier facts. The third tier that used to live here probed a PRIVATE
    product rig (an entitled account, a browser login, client ports, a private
    plugin checkout) on behalf of the ``aura-mcp`` arm; none of that ships in
    this repository, so both the probes and the tier were removed rather than
    left as a branch that can never pass."""
    backend_of(model_slug)   # resolves/validates the slug; its answer no
                             # longer varies the tier (see above)
    return "baseline"


def enforce(ctx, tier: str, log: Callable[[str], None], *, skip: bool = False) -> bool:
    """Resolve facts, run the gate, print what a newcomer needs, return
    False on any FAIL (callers abort with exit 2). WARNs never block."""
    if skip or os.environ.get("CB_NO_PREFLIGHT", "").strip() == "1":
        log("[preflight] skipped (--no-preflight / CB_NO_PREFLIGHT=1)")
        return True
    t0 = time.time()
    try:
        checks = gate(real_facts(ctx, tier), tier)
    except Exception as e:  # noqa: BLE001 - the gate must never be the outage
        log(f"[preflight] gate errored ({e.__class__.__name__}: {e}) - continuing")
        return True
    bad = [c for c in checks if c.status == "FAIL"]
    warn = [c for c in checks if c.status == "WARN"]
    if not bad and not warn:
        log(f"[preflight] {tier}: {len(checks)} checks OK ({time.time() - t0:.1f}s)")
        return True
    log(f"[preflight] {tier}: {len(checks)} checks, "
        f"{len(bad)} blocker(s), {len(warn)} warning(s)")
    for c in checks:
        if c.status == "OK":
            continue
        log(f"  {c.status:<4} {c.id:<14} {c.detail}")
        if c.fix:
            log(f"       fix: {c.fix}")
    if bad:
        log("[preflight] aborting BEFORE any build/token spend - fix the blocker(s) "
            "above, or bypass once with --no-preflight.")
        return False
    return True
