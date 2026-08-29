"""stack_guard — stack ownership manifest, startup reconciliation, the
generation-aware orphan sweep, and the pre-rep commit-pressure hook.

Owner mandate 2026-08-07, after a night where two hard-stopped benches skipped
teardown: the accumulated vercel/client leak plus orphaned editors drove commit
charge to 70/84 GB and silently killed drive editors. The eight scenarios this
module (plus :mod:`aura_rig.janitor`) closes:

  1-3. wrapper death of ANY kind (hard-stop, crash, closed console) leaving the
       stack resident — closed at the NEXT cb invocation by
       :func:`reconcile_at_entry` (dead-owner manifest -> full ``stop_stack``),
       and WITHOUT waiting for one by the janitor watchdog;
  4.   ``--no-teardown`` + a human forgetting ``cb down`` — the manifest records
       the flag, but the janitor still tears down when the OWNER dies. The flag
       means "keep the stack between MY runs", not "keep it after I'm gone":
       ownership transfers to the operator's SESSION (shell/wrapper) on clean
       exit, so the stack lives exactly as long as the session that asked for it;
  5.   ``cb eval``'s designed-resident stack leaking across a long session —
       bounded by the pre-rep pressure hook (:func:`ensure_commit_headroom`);
  6.   pressure crossing the ceiling mid-bench between cadence recycles (or
       inherited at launch) — the envgate ``commit-headroom`` hard floor at
       launch, :func:`ensure_commit_headroom` before each drive/rep, and —
       because BOTH of those can only ever prove the box was healthy when a
       20-minute drive STARTED — :mod:`aura_rig.pressure`'s in-drive sampler
       DURING it (same floor, three bands, a deliberate abort under the floor);
  7.   orphaned editors/LiveCodingConsole/CrashReportClient from OLDER stack
       generations surviving teardown (measured: a stray ``-AuraHeadless``
       editor on the repo project held 3.7 GB for 6+ hours) —
       :func:`orphan_sweep`, command-line–scoped, wired into ``stop_stack``;
  8.   idle rot (stack up overnight, no runs) — the janitor's OPT-IN
       ``CB_STACK_IDLE_TEARDOWN_HOURS`` limit.

OWNERSHIP MODEL. ``invoke_bringup`` records a manifest whose owner is the cb
PROCESS that brought the stack up (pid + create time, so a reused pid can never
impersonate it). While that process runs, the stack is its. On CLEAN exit
(``cb.main``'s release hook) ownership transfers to the SESSION ANCHOR — the
nearest ancestor process meaningfully older than cb itself (the interactive
shell / agent wrapper), skipping the transient ``cmd.exe``/``py.exe`` shim
chain by AGE rather than by name. A stack is therefore:

  * ``owner_kind == "cb"``      — a run is in flight; a second stack-mutating
                                  cb refuses (existing exclusivity convention;
                                  ``CB_ALLOW_STACK_TAKEOVER=1`` overrides);
  * ``owner_kind == "session"`` — deliberately resident between runs; reused
                                  exactly as before;
  * owner DEAD                  — an orphan, torn down on sight (reconciliation)
                                  or within one janitor poll (~60s).

A cb that dies WITHOUT reaching the release hook (hard-stop, crash, closed
console, Ctrl-C) leaves the manifest owned by its dead pid — precisely the
orphan signature. When no live session anchor can be resolved at release time
the manifest keeps the dying cb pid: the janitor then reaps the stack within a
poll. That is the CONSERVATIVE direction — a teardown costs a ~1 min re-bring-up
(and measurement hygiene wants it anyway), a leak costs the next bench 5x
verify and, at 70/84 GB commit, its editors.

Everything here is offline-testable: pure decision cores over injected facts,
seams for every process/filesystem touch. ``CB_STACK_GUARD=0`` disables the
whole subsystem (manifest, reconciliation, janitor arm) as the escape hatch.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from . import kill_guard  # test-process / live-owner refusal (2026-08-07)

IS_WINDOWS = os.name == "nt"

#: Windows FILETIME epoch offset (1601-01-01) in 100ns ticks vs Unix epoch.
_FILETIME_EPOCH_DELTA = 116444736000000000

#: Manifest schema version — bump when the CONTRACT changes so an old file
#: auto-reads as unknown (treated orphan: the leak-safe direction).
SCHEMA = 1

#: Manifest lifecycle states (the ``state`` field, added 2026-08-07).
#:
#: GAP FOUND LIVE: the manifest used to be written only at STACK GREEN, so a
#: bring-up interrupted MID-FLIGHT (hard-stop during the ~1 min editor warm-up,
#: a crash in [4/6], a closed console) left real vercel/client/editor processes
#: running with NO manifest and NO janitor — invisible to reconciliation, to
#: the watchdog, and to the orphan sweep, because all three key off a manifest.
#: The window is exactly the minutes when a bring-up is most likely to be
#: interrupted. So ``invoke_bringup`` now arms a PENDING manifest at its START
#: and promotes it to GREEN on success; a pending manifest with a DEAD owner is
#: treated identically to a green one (orphan -> full teardown) by both
#: :func:`classify_owner` and the janitor's ``decide``.
#:
#: A manifest written before this change has no ``state`` field and reads as
#: GREEN (:func:`manifest_state`) — which is what it was.
STATE_PENDING = "pending"
STATE_GREEN = "green"

#: The named harness reason a pressure-aborted rep records. Non-graded by
#: omission from ``adapters/base.GRADED_VERDICTS`` (the allowlist), exactly
#: like STACK-DOWN / EDITOR-GONE — a commit-exhausted box is a machine fault
#: and must never land in a pass-rate denominator as a model failure.
PRESSURE_VERDICT = "COMMIT-EXHAUSTED"

#: Ancestors younger than this are treated as transient launcher shims
#: (``cmd.exe`` running cb.cmd, the ``py.exe`` proxy) when resolving the
#: session anchor; the first ancestor OLDER than this is the session.
_SESSION_MIN_AGE_S = 60.0

# Commands that must see NO reconciliation output at all (machine-facing).
_SILENT_COMMANDS = frozenset({"help", "completions", "__complete"})
# Documented READ-ONLY commands: they get the one-line orphan NOTICE but never
# mutate (cmd_doctor's contract is "never mutates"; where/sync-aura likewise).
_READONLY_COMMANDS = frozenset({"status", "where", "doctor", "sync-aura", "lint"})
# Stack-mutating commands that refuse to run over another LIVE cb's stack
# (the live_lock / foreign-editor refusal convention).
_EXCLUSIVE_COMMANDS = frozenset({
    "up", "eval", "bench", "batch-gen", "headless", "tasks", "smoke",
    "view", "review",
})


# --------------------------------------------------------------------------- #
# Paths + kill switch.                                                         #
# --------------------------------------------------------------------------- #

def guard_enabled() -> bool:
    """The subsystem kill switch (default ON). ``CB_STACK_GUARD=0`` disables
    manifest recording, reconciliation, and the janitor arm in one place."""
    return os.environ.get("CB_STACK_GUARD", "1").strip().lower() not in (
        "0", "false", "no")


def manifest_path() -> Path:
    """``<repo>/runs/.stack-manifest.json`` (same repo-root derivation as
    ``stack._KILL_AUDIT_PATH`` and the live-run lock — the stack is machine-
    global, but every existing machine-state file of this rig lives under the
    invoking checkout's ``runs/``; consistency beats a second convention).
    ``CB_STACK_MANIFEST`` overrides (tests)."""
    env = os.environ.get("CB_STACK_MANIFEST")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "runs" / ".stack-manifest.json"


def janitor_lock_path() -> Path:
    """The janitor's single-instance lockfile (an OS advisory lock à la
    live_lock — it dies with the process, so there is no stale state)."""
    env = os.environ.get("CB_STACK_JANITOR_LOCK")
    if env:
        return Path(env)
    return manifest_path().with_name(".stack-janitor.lock")


# --------------------------------------------------------------------------- #
# Pid liveness (psutil -> ctypes on Windows -> os.kill(pid, 0) on POSIX).      #
# NEVER os.kill(pid, 0) on Windows — there any non-CTRL signal TERMINATES.     #
# --------------------------------------------------------------------------- #

def _win_open_process(pid: int):
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    return ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))


def _win_pid_alive(pid: int) -> bool:
    import ctypes
    k32 = ctypes.windll.kernel32
    h = _win_open_process(pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def _win_pid_create_time(pid: int) -> Optional[float]:
    """Process creation time as a Unix epoch float, or None."""
    import ctypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                    ("dwHighDateTime", ctypes.c_uint32)]

    k32 = ctypes.windll.kernel32
    h = _win_open_process(pid)
    if not h:
        return None
    try:
        c, e, kt, ut = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
        if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                   ctypes.byref(kt), ctypes.byref(ut)):
            return None
        ft = (c.dwHighDateTime << 32) | c.dwLowDateTime
        return (ft - _FILETIME_EPOCH_DELTA) / 1e7
    finally:
        k32.CloseHandle(h)


def pid_create_time(pid: int) -> Optional[float]:
    """Best-effort creation time (Unix epoch) of ``pid``; None if unknowable.
    Used to defeat PID REUSE: a manifest owner is (pid, create_time), and a
    recycled pid with a different birth is NOT the owner."""
    try:
        import psutil  # type: ignore
        return float(psutil.Process(int(pid)).create_time())
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            return _win_pid_create_time(int(pid))
        except Exception:
            return None
    return None


def pid_alive(pid, created: Optional[float] = None, tol_s: float = 5.0) -> bool:
    """True iff ``pid`` is a live process AND (when both sides know a create
    time) it is the SAME process the manifest recorded. An unknowable create
    time on either side degrades to the bare liveness check — an absent
    measurement is never a verdict, matching the envgate contract."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    alive = False
    try:
        import psutil  # type: ignore
        alive = psutil.pid_exists(pid)
    except Exception:
        if IS_WINDOWS:
            try:
                alive = _win_pid_alive(pid)
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)  # POSIX-only liveness probe (signal 0)
                alive = True
            except ProcessLookupError:
                alive = False
            except PermissionError:
                alive = True
            except OSError:
                return False
    if not alive:
        return False
    if created is None:
        return True
    now_created = pid_create_time(pid)
    if now_created is None:
        return True
    return abs(now_created - float(created)) <= tol_s


# --------------------------------------------------------------------------- #
# Session anchor — the nearest MEANINGFULLY-OLDER ancestor (the shell /        #
# wrapper), skipping transient launcher shims by AGE, never by name.           #
# --------------------------------------------------------------------------- #

def _proc_table_cim() -> Optional[dict]:
    """{pid: (ppid, create_epoch|None)} for every process, via ONE CIM query.
    Windows-only fallback for the psutil-less box (psutil is an optional dep
    and absent under the harness python here). None on failure."""
    if not IS_WINDOWS:
        return None
    ps = ("Get-CimInstance Win32_Process | ForEach-Object { "
          "'{0}|{1}|{2}' -f $_.ProcessId, $_.ParentProcessId, "
          "$(if ($_.CreationDate) { $_.CreationDate.ToFileTimeUtc() } "
          "else { 0 }) }")
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    table: dict = {}
    for line in (out or "").splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3 or not (parts[0].isdigit() and parts[1].isdigit()):
            continue
        try:
            ft = int(parts[2])
        except ValueError:
            ft = 0
        created = ((ft - _FILETIME_EPOCH_DELTA) / 1e7) if ft > 0 else None
        table[int(parts[0])] = (int(parts[1]), created)
    return table or None


def _ancestor_chain(max_depth: int = 12) -> List[Tuple[int, Optional[float]]]:
    """[(pid, created), ...] walking UP from our parent. psutil when present,
    else the one-shot CIM table (Windows), else just ``os.getppid()``."""
    chain: List[Tuple[int, Optional[float]]] = []
    try:
        import psutil  # type: ignore
        p = psutil.Process(os.getpid())
        for _ in range(max_depth):
            # PARTIAL RESULTS ARE KEPT ON PURPOSE. This used to be one big try
            # with `return chain` inside it, so a single AccessDenied/NoSuchProcess
            # anywhere up the walk threw away every ancestor already gathered and
            # fell through to the CIM path — and when that also came back empty the
            # chain degraded to [(ppid, None)], whose unknown birth time
            # session_anchor() refuses. Net effect: `session_pid` was recorded as
            # None on every bring-up, release_at_exit had nothing to transfer to,
            # and the janitor reaped every interactive `cb up` within a poll
            # (measured 4/4 on 2026-08-11 — `cb up --drive-ready`'s whole documented
            # purpose, a stack you can hand-test mutating MCP tools against, was
            # unreachable). Walking UP crosses a session/service boundary sooner or
            # later, so the exception is the norm, not the edge case.
            try:
                p = p.parent()
            except Exception:  # noqa: BLE001 — walked out of what we may inspect
                break
            if p is None or p.pid <= 0:
                break
            try:
                chain.append((p.pid, float(p.create_time())))
            except Exception:  # noqa: BLE001 — pid is real, birth time is not
                chain.append((p.pid, None))
        if chain:
            return chain
    except Exception:
        pass
    table = _proc_table_cim()
    if table:
        me = os.getpid()
        my_created = (table.get(me) or (None, None))[1]
        pid, seen = me, set()
        for _ in range(max_depth):
            ent = table.get(pid)
            if ent is None:
                break
            ppid, _created = ent
            if ppid in seen or ppid <= 0 or ppid == pid:
                break
            seen.add(ppid)
            pent = table.get(ppid)
            pcreated = pent[1] if pent else None
            # A parent BORN AFTER its child is a reused ppid — stop the walk.
            if (pcreated is not None and my_created is not None
                    and pcreated > my_created + 5.0):
                break
            chain.append((ppid, pcreated))
            pid = ppid
        return chain
    try:
        ppid = os.getppid()
        if ppid > 0:
            chain.append((ppid, pid_create_time(ppid)))
    except OSError:
        pass
    return chain


def session_anchor(min_age_s: float = _SESSION_MIN_AGE_S,
                   now: Callable[[], float] = time.time,
                   chain: Optional[Sequence[Tuple[int, Optional[float]]]] = None,
                   ) -> Optional[Tuple[int, Optional[float]]]:
    """(pid, created) of the operator's SESSION — the first ancestor at least
    ``min_age_s`` older than now-ish, i.e. a shell/terminal/wrapper that
    predates this cb invocation rather than a shim spawned to launch it.

    Age-based on purpose: the ``cb.cmd`` shim chain (``cmd.exe`` -> ``py.exe``
    -> python) is born milliseconds before us and dies the instant cb exits —
    anchoring there would hand every interactive stack to the janitor within a
    poll. A name allowlist would misclassify an interactive ``cmd.exe`` the
    same way; ages cannot. None when no such ancestor is resolvable (then the
    caller keeps the dying cb pid as owner — the conservative, reap-soon
    direction)."""
    chain = _ancestor_chain() if chain is None else list(chain)
    t = now()
    for pid, created in chain:
        if created is None:
            # Unknown age: cannot certify it as a session — keep walking; an
            # older ancestor with a known age may still qualify.
            continue
        if (t - created) >= min_age_s:
            return (pid, created)
    return None


def _is_ancestor(pid: int) -> bool:
    """True iff ``pid`` appears in our own ancestor chain (best-effort)."""
    try:
        return any(p == pid for p, _c in _ancestor_chain())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Manifest I/O.                                                                #
# --------------------------------------------------------------------------- #

def read_manifest(path: Optional[Path] = None) -> Optional[dict]:
    """The manifest dict, or None (absent / unreadable / wrong schema). A
    corrupt or foreign-schema file reads as None on purpose — reconciliation
    then treats whatever stack exists as unowned debris, the leak-safe
    direction (stop_stack is scoped and idempotent, so the worst case of a
    false orphan is a ~1 min re-bring-up)."""
    p = Path(path) if path is not None else manifest_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    return data


def write_manifest(data: dict, path: Optional[Path] = None) -> bool:
    """Write atomically-ish (tmp + replace). Never raises; False on failure."""
    p = Path(path) if path is not None else manifest_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def clear_manifest(path: Optional[Path] = None, log=None) -> None:
    """Remove the manifest (teardown ran; there is no stack to own)."""
    p = Path(path) if path is not None else manifest_path()
    try:
        p.unlink()
        if log:
            log("  ..    stack ownership manifest cleared (stack is down)")
    except FileNotFoundError:
        pass
    except OSError:
        pass


def touch_activity(path: Optional[Path] = None,
                   now: Callable[[], float] = time.time) -> None:
    """Bump ``last_activity`` (any cb invocation counts as activity for the
    janitor's OPT-IN idle-teardown clock). Best-effort."""
    m = read_manifest(path)
    if m is None:
        return
    m["last_activity"] = now()
    write_manifest(m, path)


def manifest_state(manifest: Optional[dict]) -> str:
    """A manifest's lifecycle state. A legacy manifest with no ``state`` field
    reads GREEN — it could only ever have been written at stack-green."""
    s = (manifest or {}).get("state")
    return s if s in (STATE_PENDING, STATE_GREEN) else STATE_GREEN


def record_bringup(uproject, *, command: str = "", path: Optional[Path] = None,
                   state: str = STATE_GREEN,
                   now: Callable[[], float] = time.time, log=None) -> Optional[dict]:
    """Record THIS process as the live stack's owner (called by
    ``invoke_bringup`` — PENDING at bring-up start, GREEN on stack-green).
    Replaces any prior generation's manifest — a new bring-up owns whatever is
    now up. Never raises."""
    if not guard_enabled():
        return None
    try:
        t = now()
        anchor = session_anchor(now=now)
        m = {
            "schema": SCHEMA,
            "state": state if state in (STATE_PENDING, STATE_GREEN) else STATE_GREEN,
            "generation": f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}",
            "created_at": t,
            "last_activity": t,
            "owner_pid": os.getpid(),
            "owner_created": pid_create_time(os.getpid()),
            "owner_kind": "cb",
            "session_pid": anchor[0] if anchor else None,
            "session_created": anchor[1] if anchor else None,
            "repo_root": str(Path(__file__).resolve().parents[3]),
            "uproject": str(uproject),
            "ports": [3000, 3002, 9222, 30010],
            "no_teardown": False,
            "command": command,
        }
        if write_manifest(m, path) and log:
            # Say whether the stack will OUTLIVE this cb. `session_pid: None` is
            # the difference between a resident stack and one the janitor reaps a
            # poll after cb exits, and it used to be invisible until the teardown
            # had already happened.
            anchored = (f"session pid {m['session_pid']}" if m["session_pid"]
                        else "NO session anchor - reaped when this cb exits")
            log(f"  ..    stack ownership manifest ({m['state']}) -> "
                f"{path or manifest_path()} (owner pid {m['owner_pid']}, "
                f"{anchored}, generation {m['generation']}; a dead owner is "
                f"auto-torn-down by the janitor / next cb)")
        return m
    except Exception:  # noqa: BLE001 — recording must never break a bring-up
        return None


def record_bringup_pending(uproject, *, command: str = "",
                           path: Optional[Path] = None,
                           now: Callable[[], float] = time.time,
                           log=None) -> Optional[dict]:
    """Arm a PENDING manifest at bring-up START, so a bring-up interrupted
    mid-flight still leaves an owner the janitor / reconciliation can reap.

    RETRY-CORRECT: when this process already owns a PENDING manifest (a
    bring-up that legitimately failed and is being retried by the SAME cb), the
    generation and ``created_at`` are kept and only the activity stamp moves —
    otherwise every retry would mint a new generation and make the janitor's
    staleness recheck (which compares generations) look at a moving target."""
    if not guard_enabled():
        return None
    try:
        cur = read_manifest(path)
        if (cur and cur.get("owner_pid") == os.getpid()
                and manifest_state(cur) == STATE_PENDING):
            cur["last_activity"] = now()
            cur["uproject"] = str(uproject)
            if command:
                cur["command"] = command
            write_manifest(cur, path)
            if log:
                log(f"  ..    stack bring-up retry under the existing pending "
                    f"manifest (generation {cur.get('generation')})")
            return cur
    except Exception:  # noqa: BLE001
        pass
    return record_bringup(uproject, command=command, path=path,
                          state=STATE_PENDING, now=now, log=log)


def promote_to_green(uproject=None, *, command: str = "",
                     path: Optional[Path] = None,
                     now: Callable[[], float] = time.time,
                     log=None) -> Optional[dict]:
    """Promote OUR pending manifest to GREEN (called on STACK GREEN), keeping
    the generation the janitor was armed against. When no pending manifest of
    ours exists — guard disabled at start, manifest cleared under us, another
    generation took over — fall back to a fresh green record, i.e. exactly the
    pre-2026-08-07 behaviour."""
    if not guard_enabled():
        return None
    try:
        cur = read_manifest(path)
        if (cur and cur.get("owner_pid") == os.getpid()
                and manifest_state(cur) == STATE_PENDING):
            cur["state"] = STATE_GREEN
            cur["last_activity"] = now()
            if uproject is not None:
                cur["uproject"] = str(uproject)
            if command:
                cur["command"] = command
            if write_manifest(cur, path) and log:
                log(f"  ..    stack ownership manifest -> green "
                    f"(owner pid {cur.get('owner_pid')}, generation "
                    f"{cur.get('generation')})")
            return cur
    except Exception:  # noqa: BLE001
        pass
    return record_bringup(uproject, command=command, path=path,
                          state=STATE_GREEN, now=now, log=log)


def adopt_session(pid: int, *, path: Optional[Path] = None, log=None,
                  now: Callable[[], float] = time.time,
                  alive: Callable[..., bool] = None) -> bool:
    """Record an EXPLICITLY DECLARED session owner (``cb up --session-pid``).

    ``session_anchor()`` INFERS the session by walking cb's ancestors for one
    older than a minute. That inference has no answer at all in an agent / CI
    harness that spawns a fresh shell per command: measured 2026-08-11, cb's
    chain there is 2 deep and both entries are the launcher and its throwaway
    shell, so either nothing qualifies (they are ~2 s old at bring-up start) or
    — once a slow bring-up ages them past the threshold — the "session" resolves
    to the LAUNCHER, which dies with cb. Both land on the same outcome:
    ``release_at_exit`` finds no live anchor and the janitor reaps a stack the
    operator asked to keep, within a poll.

    Declaring the owner replaces a guess with a fact. It weakens nothing: the
    janitor's rule is unchanged and state-blind — a dead owner is an orphan and
    gets the full kill-audited teardown, declared or inferred. Refuses a pid
    that is not alive rather than writing an owner that is already a corpse.
    """
    if not guard_enabled():
        return False
    alive = alive or pid_alive
    try:
        created = pid_create_time(pid)
        if not alive(pid, created):
            if log:
                log(f"  WARN  --session-pid {pid} is not alive — ignoring it; "
                    f"the stack stays cb-owned and will be reaped on exit.")
            return False
        m = read_manifest(path)
        if not m:
            if log:
                log("  WARN  --session-pid: no manifest to adopt (guard off?).")
            return False
        m.update(session_pid=pid, session_created=created, last_activity=now())
        ok = write_manifest(m, path)
        if ok and log:
            log(f"  OK    session owner declared: pid {pid} — the stack stays up "
                f"until that process dies (then the janitor reaps it). "
                f"`cb down` is the explicit teardown.")
        return ok
    except Exception:  # noqa: BLE001 — never break a bring-up over ownership
        return False


def release_at_exit(*, no_teardown: bool = False, path: Optional[Path] = None,
                    alive: Callable[..., bool] = None, log=print,
                    now: Callable[[], float] = time.time) -> None:
    """CLEAN-exit hook (``cb.main``): transfer a stack THIS process owns to
    the session anchor, making the deliberate residency explicit. Reached only
    on a normal dispatch return — a crash / hard-stop / Ctrl-C never gets
    here, which is exactly what makes a dead-cb-owned manifest the orphan
    signature. When no live session anchor exists the manifest keeps our
    (dying) pid and the janitor reaps the stack within a poll — conservative:
    teardown over leak, always. Never raises."""
    if not guard_enabled():
        return
    alive = alive or pid_alive
    try:
        m = read_manifest(path)
        if not m or m.get("owner_pid") != os.getpid():
            return  # not ours (or already torn down / transferred)
        spid, screated = m.get("session_pid"), m.get("session_created")
        if spid and alive(spid, screated):
            m.update(owner_pid=spid, owner_created=screated,
                     owner_kind="session", no_teardown=bool(no_teardown),
                     last_activity=now())
            write_manifest(m, path)
            if no_teardown:
                log("  ..    stack left UP, ownership -> your session "
                    f"(pid {spid}); the janitor tears it down when the "
                    "session dies (--no-teardown means 'keep between MY "
                    "runs', not 'keep after I'm gone').")
        else:
            log("  ..    stack left UP but no live session anchor resolved - "
                "the janitor will tear it down within ~1 poll (leak-safe "
                "default; bring-up is ~1 min).")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# Reconciliation — the EVERY-entry-point hook (pure core + thin wrapper).      #
# --------------------------------------------------------------------------- #

def classify_owner(manifest: Optional[dict], *,
                   self_pid: Optional[int] = None,
                   alive: Callable[..., bool] = None,
                   is_ancestor: Callable[[int], bool] = None) -> str:
    """Pure-ish classification of the manifest's owner:

      'none'         no (readable) manifest
      'orphan'       owner pid dead / unrecorded / pid-reused
      'live-self'    owner is this process or one of its ancestors
      'live-session' owner_kind == 'session' (deliberate residency)
      'live-other'   another cb run is in flight
    """
    alive = alive or pid_alive
    is_ancestor = is_ancestor or _is_ancestor
    if manifest is None:
        return "none"
    pid = manifest.get("owner_pid")
    if not isinstance(pid, int) or pid <= 0:
        return "orphan"   # a manifest we can't attribute is debris, not a stack
    if not alive(pid, manifest.get("owner_created")):
        return "orphan"
    me = os.getpid() if self_pid is None else self_pid
    if pid == me:
        return "live-self"
    if manifest.get("owner_kind") == "session":
        return "live-session"
    if is_ancestor(pid):
        return "live-self"
    return "live-other"


def _default_teardown(log) -> None:
    from aura_rig import stack as _stack  # lazy: stack imports us back lazily
    _stack.stop_stack(log=log)


def reconcile_at_entry(command: str, log=print, *,
                       path: Optional[Path] = None,
                       teardown: Optional[Callable] = None,
                       classify: Optional[Callable] = None,
                       env: Optional[dict] = None) -> Optional[int]:
    """Startup reconciliation, run by EVERY cb entry point (scenarios 1-3 at
    next invocation). Returns None to proceed, or an exit code to refuse.

      * dead-owner manifest  -> loud one-line notice + full ``stop_stack``
        (kill-audited; the orphan sweep rides inside stop_stack), then proceed
        — EXCEPT under the documented READ-ONLY commands (status/where/doctor/
        sync-aura/lint), which only print the notice: their no-mutation
        contract predates this module and outranks it (deviation from the
        every-command teardown, recorded here);
      * a live owner that is NOT us (another cb in flight) -> stack-mutating
        commands refuse (exit 2), the existing live_lock / foreign-editor
        exclusivity convention; ``CB_ALLOW_STACK_TAKEOVER=1`` overrides;
      * a session-owned live stack -> proceed (normal amortized residency).

    Never raises; a broken probe must not brick every cb command."""
    if not guard_enabled():
        return None
    if command in _SILENT_COMMANDS:
        return None
    # THE ENTRY PATH THE 2026-08-07 INCIDENT TOOK. `tests/test_cb_preview_cmd.
    # TestPreviewIgnoredByCommand` calls the REAL `cb.main()` (it stubs
    # `_DISPATCH` and `_Ctx`, but not this hook), so a stale manifest on the
    # operator's box made a unit test run the full production `stop_stack` —
    # four times, with its output swallowed into a mocked `_say`. The kill gate
    # (aura_rig.kill_guard) already refuses the resulting kills, but the
    # production path itself has no business running from a test process at
    # all: it also writes the machine-global manifest (`touch_activity`) and
    # can refuse a command with exit 2 depending on host state, which is how a
    # unit test becomes host-dependent.
    #
    # Scoped to the PRODUCTION wiring: with `teardown`/`classify` injected this
    # function IS the unit under test, and those tests must keep running.
    if (teardown is None and classify is None
            and kill_guard.in_test_process()
            and not kill_guard.env_true("CB_ALLOW_REAL_KILLS")):
        return None
    env = os.environ if env is None else env
    try:
        m = read_manifest(path)
        state = (classify or classify_owner)(m)
        if state == "none":
            return None
        if state == "orphan":
            gen = (m or {}).get("generation", "?")
            opid = (m or {}).get("owner_pid", "?")
            # A PENDING manifest with a dead owner is an INTERRUPTED bring-up;
            # it is torn down exactly like a green one (that is the point of
            # arming the manifest early), only the wording differs.
            kind = ("an INTERRUPTED bring-up"
                    if manifest_state(m) == STATE_PENDING else "an ORPHANED stack")
            if command in _READONLY_COMMANDS:
                log(f"NOTE  {kind} manifest exists (generation {gen}, "
                    f"dead owner pid {opid}) - `cb {command}` is read-only, so "
                    "leaving it; any mutating cb command (or the janitor) tears "
                    "it down.")
                return None
            log(f"NOTE  reaping {kind} (generation {gen}, owner pid "
                f"{opid} is DEAD - hard-stopped/crashed wrapper): full teardown "
                "before proceeding (kill-audited in runs/.kill-audit.log).")
            (teardown or _default_teardown)(log)
            return None
        if state == "live-other" and command in _EXCLUSIVE_COMMANDS:
            if (env.get("CB_ALLOW_STACK_TAKEOVER", "").strip().lower()
                    in ("1", "true", "yes")):
                log("WARN  another cb run owns the live stack (pid "
                    f"{(m or {}).get('owner_pid')}) - proceeding anyway "
                    "(CB_ALLOW_STACK_TAKEOVER=1).")
            else:
                log(f"FAIL  another cb run owns the live stack (pid "
                    f"{(m or {}).get('owner_pid')}, started "
                    f"{(m or {}).get('command') or '?'}) - running `cb "
                    f"{command}` now would restart its editor/client mid-run. "
                    "Wait for it (or kill it), or override with "
                    "CB_ALLOW_STACK_TAKEOVER=1.")
                return 2
        touch_activity(path)
        return None
    except Exception as e:  # noqa: BLE001 — the guard must never be the outage
        try:
            log(f"WARN  stack reconciliation errored ({e.__class__.__name__}: "
                f"{e}) - continuing")
        except Exception:
            pass
        return None


# --------------------------------------------------------------------------- #
# Orphan sweep (scenario 7) — command-line-scoped, NEVER by image name alone.  #
# --------------------------------------------------------------------------- #

#: The UE process family a dead stack generation can strand.
UE_FAMILY = ("UnrealEditor", "UnrealEditor-Cmd", "LiveCodingConsole",
             "CrashReportClient")
#: Editors are killed ONLY on a command-line marker match — a foreign UE
#: project's editor must be untouchable no matter what.
_STRICT_IMAGES = frozenset({"UnrealEditor", "UnrealEditor-Cmd"})


def cb_cmdline_markers(repo_root: Optional[Path] = None) -> List[str]:
    """Lowercased path fragments that mark a command line as THIS repo's:
    the repo root, the managed scratch root, the workdir root (each in both
    slash spellings), plus the legacy 'craftbench' name marker
    (``stack._CB_EDITOR_MARKER``)."""
    markers: List[str] = ["craftbench"]
    roots: List[Path] = []
    try:
        roots.append(Path(repo_root) if repo_root is not None
                     else Path(__file__).resolve().parents[3])
    except Exception:
        pass
    try:
        from aura_rig import paths as cb_paths
        roots.append(cb_paths.scratch_root())
        roots.append(cb_paths.wd_root())
    except Exception:
        pass
    for r in roots:
        s = str(r).lower().rstrip("\\/")
        if not s:
            continue
        markers.append(s)
        markers.append(s.replace("\\", "/"))
    # De-dup, order-preserving.
    out: List[str] = []
    for m in markers:
        if m and m not in out:
            out.append(m)
    return out


def classify_ue_cmdline(image: str, cmdline: str,
                        markers: Sequence[str]) -> str:
    """'cb' when the command line carries any cb path marker, else 'other'.
    Path-prefix evidence only — the image NAME is never enough (the rule that
    keeps other UE projects on the box untouchable)."""
    cl = (cmdline or "").lower()
    if any(m in cl for m in markers if m):
        return "cb"
    return "other"


def _ue_family_procs() -> Optional[List[Tuple[str, int, str]]]:
    """[(image, pid, cmdline_lower)] for the UE process family. psutil ->
    PowerShell CIM (Windows; wmic is gone on current Win11) -> ps (POSIX).
    None when enumeration is entirely blind (callers fall back to the legacy
    blanket trio — fail-open, the ``kill_craftbench_editors`` convention)."""
    want = {n.lower() for n in UE_FAMILY}
    try:
        import psutil  # type: ignore
        out: List[Tuple[str, int, str]] = []
        for p in psutil.process_iter(["name", "pid", "cmdline"]):
            n = (p.info.get("name") or "")
            base = n[:-4] if n.lower().endswith(".exe") else n
            if base.lower() in want:
                out.append((base, p.info.get("pid"),
                            " ".join(p.info.get("cmdline") or []).lower()))
        return out
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            flt = " OR ".join(f"Name='{n}.exe'" for n in UE_FAMILY)
            ps = ("Get-CimInstance Win32_Process -Filter \"" + flt + "\" | "
                  "ForEach-Object { '{0}|{1}|{2}' -f $_.Name, $_.ProcessId, "
                  "$_.CommandLine }")
            text = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=25).stdout
            procs: List[Tuple[str, int, str]] = []
            for line in (text or "").splitlines():
                parts = line.strip().split("|", 2)
                if len(parts) >= 2 and parts[1].strip().isdigit():
                    name = parts[0].strip()
                    base = name[:-4] if name.lower().endswith(".exe") else name
                    procs.append((base, int(parts[1]),
                                  (parts[2] if len(parts) > 2 else "").lower()))
            return procs
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        text = subprocess.run(["ps", "-eo", "pid=,args="],
                              capture_output=True, text=True, timeout=15).stdout
        procs = []
        for line in (text or "").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                low = parts[1].lower()
                for img in UE_FAMILY:
                    if img.lower() in low:
                        procs.append((img, int(parts[0]), low))
                        break
        return procs
    except (OSError, subprocess.SubprocessError):
        return None


def _tree_kill(pid: int) -> None:
    """Force-kill ``pid`` and its descendants (children-first on POSIX).

    Routed through ``stack._run_kill_cmd`` so the 2026-08-07 kill gate covers
    the sweep too (a test process / a live foreign owner is refused, audited).
    ``orphan_sweep`` injects ``kill`` in every unit test, so this real path is
    only ever taken in production."""
    from aura_rig import stack as _stack
    try:
        if IS_WINDOWS:
            _stack._run_kill_cmd(["taskkill", "/F", "/T", "/PID", str(pid)],
                                 target=f"pid={pid} (orphan tree)",
                                 reason="stack_guard._tree_kill")
        else:
            for tpid in _stack._proc_tree_pids(pid):
                _stack._run_kill_cmd(["kill", "-9", str(tpid)],
                                     target=f"pid={tpid} (orphan tree)",
                                     reason="stack_guard._tree_kill")
    except (OSError, subprocess.SubprocessError):
        pass


def orphan_sweep(*, procs: Optional[Callable] = None,
                 markers: Optional[Sequence[str]] = None,
                 kill: Optional[Callable[[int], None]] = None,
                 foreign: Optional[Callable] = None,
                 blanket: Optional[Callable[[], None]] = None,
                 audit: Optional[Callable] = None,
                 log=print) -> List[Tuple[str, int]]:
    """Kill UE-family processes stranded by OLDER stack generations. Runs only
    where no live stack can exist (teardown / dead-owner reconciliation), so
    every cb-owned UE-family process in sight IS an orphan (measured instance:
    a stray ``-AuraHeadless`` editor on the repo project holding 3.7 GB for
    6+ hours after its generation's teardown).

    Scoping rules (the whole point):
      * UnrealEditor / UnrealEditor-Cmd — killed ONLY on a command-line cb
        path-marker match. Foreign projects' editors are structurally exempt.
      * LiveCodingConsole / CrashReportClient — their command lines rarely
        carry a project path, so an unmarked one is killed only when NO
        foreign editor is running (it can then belong to nobody else) — the
        ``ensure_editor_dead._sweep_if_safe`` convention, verbatim.
      * enumeration blind -> fall back to the LEGACY blanket trio
        (UnrealEditor-Cmd/LiveCodingConsole/CrashReportClient), i.e. exactly
        what ``stop_stack`` always did — fail-open, never fail-blind.

    Every kill is audited (``runs/.kill-audit.log``). Returns [(image, pid)]
    killed. Never raises."""
    from aura_rig import stack as _stack
    procs = procs or _ue_family_procs
    markers = list(markers) if markers is not None else cb_cmdline_markers()
    kill = kill or _tree_kill
    foreign = foreign if foreign is not None else _stack.foreign_editor
    audit = audit or _stack.audit_kill
    try:
        entries = procs()
    except Exception:
        entries = None
    if entries is None:
        try:
            (blanket or (lambda: _stack.kill_by_image(
                "UnrealEditor-Cmd", "LiveCodingConsole", "CrashReportClient")))()
        except Exception:
            pass
        return []
    try:
        foreign_live = foreign() is not None
    except Exception:
        foreign_live = False
    killed: List[Tuple[str, int]] = []
    me = os.getpid()
    for image, pid, cl in entries:
        if not isinstance(pid, int) or pid == me:
            continue
        owned = classify_ue_cmdline(image, cl, markers) == "cb"
        if image in _STRICT_IMAGES:
            if not owned:
                continue                       # NEVER by image name alone
        elif not owned and foreign_live:
            continue   # may be the foreign editor's own console/crash dialog
        try:
            audit(f"pid={pid} (image={image})", "stack_guard.orphan_sweep")
            kill(pid)
            killed.append((image, pid))
        except Exception:
            pass
    if killed:
        log("  ..    orphan sweep: killed "
            + ", ".join(f"{i} pid={p}" for i, p in killed)
            + " (older-generation cb debris; audited in runs/.kill-audit.log)")
    return killed




# --------------------------------------------------------------------------- #
# L1 parallel cap vs commit headroom (2026-08-24).                             #
# --------------------------------------------------------------------------- #

def l1_cap_for_headroom(free_gb: Optional[float],
                        floor_gb: float,
                        operator_cap: Optional[int]) -> int:
    """The ``CRAFTBENCH_L1_MAX_PARALLEL`` to use for one graded build.

    NARROWS the operator's cap when commit headroom is thin; never raises it.

    WHY, measured 2026-08-24. A ``cb discriminate`` leg started with 10.6 GB of
    free commit against envgate's 10 GB floor — the preflight WARNED and let it
    run, correctly, because the preflight is a PRE-SPEND gate and cannot see a
    mid-build collapse. Its L1 then died with ``fatal error C1060`` (compiler out
    of heap) three times, all inside ENGINE headers, none in task code, at cap 4.
    The recorded verdict was ``reference FAIL(skipped)`` — the SUBMISSION
    failing. The same task, same commit, PASSED at cap 2 in 1113 s, i.e. LESS
    wall-clock than the cap-4 attempt that failed.

    So the repo's "cap 4 passes, cap 6 fails deterministically on this box" is
    true only of an IDLE box; under load cap 4 dies too, and a constant cap
    cannot express that. ``run_graded`` already applies a ``min(cap, 2)`` floor
    for the same reason (its stack stays up during grading) — this is that
    instinct made data-driven and given to the path that lacked it.

    Bands, all expressed against the ONE floor ``envgate`` already owns, never a
    second threshold:

      * headroom UNKNOWN -> 2. Unmeasurable is not the same as fine, and leaving
        the cap unset is the genuinely dangerous value: UBT then picks its own
        (6 on this box) and L1 dies deterministically, which the repo conventions record as
        15/15 references FAILing in a fresh worktree.
      * free < 2x floor -> 2.
      * otherwise -> the operator's cap, unchanged.
    """
    base = operator_cap if (isinstance(operator_cap, int) and operator_cap > 0) else 2
    if free_gb is None:
        return min(base, 2)
    try:
        thin = float(free_gb) < (2.0 * float(floor_gb))
    except (TypeError, ValueError):
        return min(base, 2)
    return min(base, 2) if thin else base


def l1_cap_env(env: Optional[dict] = None,
               read_free: Optional[Callable[[], Optional[float]]] = None,
               floor: Optional[Callable[[], float]] = None,
               operator: Optional[Callable[[], Optional[int]]] = None) -> dict:
    """``{"CRAFTBENCH_L1_MAX_PARALLEL": "<n>"}`` merged onto ``env``.

    Fail-open in the only direction that matters: if any probe raises, the
    operator's environment is returned untouched rather than a guessed cap.
    """
    out = dict(env if env is not None else os.environ)
    try:
        from aura_rig import pressure as _pressure
        from aura_rig import envgate as _envgate
        from aura_rig import stack as _stack
        rf = read_free or _pressure.read_free_gb
        fl = floor or _envgate.commit_floor_gb
        op = operator or _stack.l1_cap
        out["CRAFTBENCH_L1_MAX_PARALLEL"] = str(
            l1_cap_for_headroom(rf(), fl(), op()))
    except Exception:  # noqa: BLE001 - a probe failure must not change the build
        pass
    return out

# --------------------------------------------------------------------------- #
# MCP stdio orphans (2026-08-24) — the commit drain nothing else reaps.        #
# --------------------------------------------------------------------------- #

#: Command-line fragments that mark a python process as an MCP stdio server.
MCP_STDIO_MARKERS = ("aura/mcp/", r"aura\mcp" + "\\")


def _mcp_stdio_procs() -> Optional[List[Tuple[str, int, int, str]]]:
    """``[(image, pid, ppid, cmdline_lower)]`` for MCP stdio server processes.

    ``None`` when enumeration is entirely blind — callers then do NOTHING, which
    is the opposite of ``_ue_family_procs``' fail-open blanket. That asymmetry is
    deliberate: a blanket kill of every ``python.exe`` would take out the
    operator's own tooling, and an unreaped orphan costs memory, not a verdict.
    """
    try:
        import psutil  # type: ignore
        out: List[Tuple[str, int, int, str]] = []
        for pr in psutil.process_iter(["name", "pid", "ppid", "cmdline"]):
            name = (pr.info.get("name") or "")
            if not name.lower().startswith("python"):
                continue
            cmd = " ".join(pr.info.get("cmdline") or []).lower()
            if any(m in cmd for m in MCP_STDIO_MARKERS):
                out.append((name, pr.info.get("pid"), pr.info.get("ppid") or 0, cmd))
        return out
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            ps = ("Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
                  "ForEach-Object { '{0}|{1}|{2}|{3}' -f $_.Name, $_.ProcessId, "
                  "$_.ParentProcessId, $_.CommandLine }")
            text = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=25).stdout
            out = []
            for line in (text or "").splitlines():
                parts = line.strip().split("|", 3)
                if len(parts) < 4:
                    continue
                cmd = (parts[3] or "").lower()
                if not any(m in cmd for m in MCP_STDIO_MARKERS):
                    continue
                try:
                    out.append((parts[0], int(parts[1]), int(parts[2]), cmd))
                except ValueError:
                    continue
            return out
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    return None


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness. Unknown counts as ALIVE, so an unreadable parent
    protects its child rather than condemning it."""
    if pid <= 0:
        return False
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(pid)
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            text = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue)"
                 " {'Y'} else {'N'}"],
                capture_output=True, text=True, timeout=20).stdout
            return "N" not in (text or "Y")
        except (OSError, subprocess.SubprocessError):
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def mcp_orphan_sweep(*, procs: Optional[Callable] = None,
                     alive: Optional[Callable[[int], bool]] = None,
                     kill: Optional[Callable[[int], None]] = None,
                     audit: Optional[Callable] = None,
                     log=print) -> List[Tuple[str, int]]:
    """Reap MCP stdio servers whose CLIENT process is gone.

    WHY THIS EXISTS, measured 2026-08-24. Twenty-six stranded ``Aura/MCP``
    python children held **11.75 GB of COMMIT** with no Aura client and no editor
    anywhere, which put free commit at 5.9 GB against envgate's 10 GB floor. The
    cost was not memory, it was a WRONG VERDICT: an eight-leg ``cb discriminate``
    sweep lost every leg — the first one's L1 died and was recorded as the
    SUBMISSION failing (the C1060/C3859 shape), and the remaining seven aborted
    at the preflight blocker. Reaping them returned free commit to 22.3 GB and
    the same command then read ``11 checks OK`` and PASSed.

    Nothing else in the rig reaps these. ``stop_stack``, ``orphan_sweep`` and
    ``ensure_editor_dead`` all scope to the UE family, the Aura client and the
    port owners; an MCP stdio child is none of those, so a box can sit under the
    commit floor with no stack up at all and nothing able to explain why.

    THE GATE IS A DEAD PARENT, not "no Aura is running". These servers are
    spawned by an MCP CLIENT (Claude Code), not by the Aura desktop client, so a
    live client legitimately owns its children — killing on "no Aura" would take
    out the working set of whoever is driving the editor at that moment. An
    unreadable parent counts as alive (see ``_pid_alive``).

    Every kill routes through ``_tree_kill`` -> ``stack._run_kill_cmd``, so the
    2026-08-07 kill gate covers this sweep too: refused and audited from a test
    process, or when the manifest names a live owner that is not an ancestor.
    Returns ``[(image, pid)]`` reaped. Never raises.
    """
    from aura_rig import stack as _stack
    procs = procs or _mcp_stdio_procs
    alive = alive or _pid_alive
    kill = kill or _tree_kill
    audit = audit or _stack.audit_kill
    try:
        entries = procs()
    except Exception:
        entries = None
    if not entries:
        return []
    reaped: List[Tuple[str, int]] = []
    for image, pid, ppid, _cmd in entries:
        try:
            if alive(ppid):
                continue
            audit(f"{image} pid={pid} (MCP stdio orphan, ppid={ppid} gone)",
                  "stack_guard.mcp_orphan_sweep")
            kill(pid)
            reaped.append((image, pid))
        except Exception:
            continue
    if reaped:
        log("  ..    MCP orphan sweep: reaped "
            + ", ".join(f"{i} pid={p}" for i, p in reaped)
            + " (stdio servers whose client is gone; they hold COMMIT and no "
              "other cb path reaps them)")
    return reaped

# --------------------------------------------------------------------------- #
# Pre-rep commit-pressure hook (scenarios 5 + 6 mid-bench).                    #
# --------------------------------------------------------------------------- #

def ensure_commit_headroom(*, recycle: Callable[[], None],
                           read: Optional[Callable[[], Optional[float]]] = None,
                           floor: Optional[float] = None,
                           settle_s: float = 8.0,
                           sleep: Callable[[float], None] = time.sleep,
                           log=print) -> Tuple[bool, str]:
    """Check FREE COMMIT against the hard floor immediately before a drive/rep;
    below it, recycle the stack NOW (the same stop-then-re-bring-up machinery
    as the every-4-reps cadence — the caller's next ``require_stack`` recreates
    it) and re-check. Returns ``(ok, note)``:

      * ok=True  — headroom fine (or unmeasurable: an absent measurement is
        never a verdict), possibly after a recycle;
      * ok=False — still under the floor AFTER the recycle: an EXTERNAL
        process holds the commit. The caller must abort the rep with
        :data:`PRESSURE_VERDICT` — a build started here dies with C3859/exit-1
        and grades as the AGENT failing the task, which is the exact
        false-negative this hook exists to prevent.

    The every-4-reps cadence stays the baseline; this is the emergency valve
    between cadence points (measured 2026-08-04: vercel :3000 grew to 10.9 GB
    private and free commit hit 0 MID-matrix, between recycles).

    SCOPE, and its limit: this fires BEFORE a drive, so it can only ever prove
    the box was healthy at t=0 of a 20-minute turn. The mid-turn half lives in
    :mod:`aura_rig.pressure` (same floor via ``envgate.commit_floor_gb``, so
    there is one threshold, not two)."""
    from aura_rig import envgate as _envgate
    read = read or _envgate._read_commit_free_gb
    floor = float(floor) if floor is not None else _envgate.commit_floor_gb()
    free = read()
    if free is None or free >= floor:
        return True, "headroom ok" if free is None else \
            f"commit headroom {free:.1f} GB >= floor {floor:.0f} GB"
    log(f"  !!    commit headroom {free:.1f} GB < floor {floor:.0f} GB - "
        "recycling the stack NOW (pressure-triggered; the resident stack is "
        "the measured runaway - vercel :3000 - and teardown returns ~20 GB)")
    recycle()
    sleep(settle_s)
    free2 = read()
    if free2 is None or free2 >= floor:
        log(f"  OK    commit headroom recovered after the recycle "
            f"({'unmeasured' if free2 is None else f'{free2:.1f} GB free'})")
        return True, "recovered by recycle"
    note = (f"commit headroom still {free2:.1f} GB (< {floor:.0f} GB floor) "
            "AFTER a stack recycle - an EXTERNAL process holds the commit "
            "charge. Not spending on a rep that would die C3859 and grade as "
            "a model failure. Close the hog (Task Manager > Details > Commit "
            "size), then re-run/resume.")
    log("  FAIL  " + note)
    return False, note
