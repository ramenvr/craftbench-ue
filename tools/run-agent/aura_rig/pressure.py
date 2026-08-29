"""pressure — IN-DRIVE commit-pressure sampling, the deliberate abort, and the
leak-triggered stack recycle.

WHY THIS EXISTS (measured twice on the night of 2026-08-07). The drive editor
dies MID-DRIVE from commit-charge exhaustion: no kill (``kill_guard`` refuses
those now), no crash dump, just a failed allocation. The box is 61.6 GB RAM +
a Windows-managed 23.5 GB pagefile = an 84.6 GB commit LIMIT; the aura-plugin
dev stack leaks (vercel :3000 is the documented runaway — 10.9 GB private on
2026-08-04; node measured at 8 GB combined), so a 20-minute drive climbs
steadily and the editor dies at ~10 GB free.

The guard that shipped earlier the same day
(:func:`aura_rig.stack_guard.ensure_commit_headroom`) only fires BETWEEN reps.
That is far too late: it can prove the box was healthy when a 20-minute drive
STARTED and learn nothing about the minute it died in. This module closes the
gap in three layers, none of which may ever gate a model's verdict:

  1. IN-DRIVE SAMPLING. A daemon thread samples free commit every ~10 s for
     exactly as long as the CDP drive subprocess runs (:class:`DriveMonitor`,
     started/stopped by :func:`aura_rig.aura_product.drive`). See "THE SEAM"
     below for why the supervisor thread — not the vendored TypeScript driver —
     is the honest place for this.
  2. THREE BANDS off ONE threshold. The floor is ``envgate.commit_floor_gb()``
     (env ``CB_COMMIT_FLOOR_GB``), the same number the pre-spend gate and the
     pre-rep hook use — there is exactly one source of truth for "how much
     commit is too little".

       band      condition               action
       --------  ----------------------  ---------------------------------------
       OK        free >= 2x floor        nothing (min-free still tracked)
       WARN      floor <= free < 2x      append a timestamped sample to
                                         ``runs/<run>/pressure.jsonl``; log ONCE
                                         per crossing, never per sample
       CRITICAL  free < floor            append the sample, then ABORT the drive
                                         deliberately: stop the drive, tear the
                                         stack down, record the NON-GRADED
                                         ``COMMIT-EXHAUSTED`` verdict
       (none)    unmeasurable            hold the previous band — an absent
                                         measurement is never a verdict

     ``CB_PRESSURE_WARN_MULT`` moves the WARN multiple, ``CB_PRESSURE_SAMPLE_S``
     the cadence, ``CB_PRESSURE_HYSTERESIS_GB`` the re-arm margin,
     ``CB_PRESSURE_GUARD=0`` disables the whole layer.
  3. POST-HOC EVIDENCE, ALWAYS. Even a drive that finishes clean records
     ``min_free_gb`` / ``last_free_gb`` into ``summary.json`` (``"pressure"``).
     That is the entire point of the cheap OK-band path: the NEXT unexplained
     EDITOR-GONE is attributable in one read instead of two days — and when the
     last sample sat under the WARN line, :func:`annotate_summary` writes the
     probable cause into the summary in words.

THE SEAM (and why not the TypeScript driver). ``cb-aura-product-drive.ts``
already heartbeats the editor's RC port — that heartbeat is how EDITOR-GONE is
detected — so its poll loop is the natural cadence. It is nevertheless the
WRONG place to put this: the driver is VENDORED product-adjacent glue, it
cannot read ``CB_COMMIT_FLOOR_GB``'s Python resolution, it cannot tear the
stack down (``stop_stack`` is Python, kill-audited, and gated by
``kill_guard``), and it cannot write a harness verdict. The Python side that
OWNS the drive — :func:`aura_rig.aura_product.drive`, which blocks in
``runner(...)`` for the whole measured turn — is the honest supervisor: same
process as the verdict writer, same env, same kill gate. So the sampler is a
daemon thread there, started before the child and stopped in a ``finally``.

THE HARD INVARIANT: **THIS MODULE NEVER SPAWNS A PROCESS.** Not on any band,
not in any fallback, not on the abort path. ``subprocess`` is deliberately NOT
imported here, so the rule is structural rather than a promise.

WHY (owner catch, 2026-08-07, caught in review before this shipped). The first
cut of this file fell back to ``powershell.exe`` for the offender name and the
stack footprint whenever ``psutil`` was missing — and **psutil IS missing on
this box's harness python**, so that fallback was the ACTIVE path. Spawning
PowerShell costs ~50-100 MB of commit and a few hundred ms, and it happened in
the WARN/CRITICAL bands: the guard would have allocated ~100 MB precisely
during the memory crisis it exists to prevent, and could plausibly have BEEN
the allocation that killed the editor. A guard that participates in the failure
it measures is worse than no guard.

So every measurement here is an IN-PROCESS syscall, and every one of them is
scoped:

  * FREE COMMIT (the 10 s heartbeat) — ``envgate._read_commit_free_gb``, one
    ``GlobalMemoryStatusEx`` ctypes call. No allocation, no enumeration. This is
    the number that matters and it is free; nothing else is allowed to cost more.
  * WHICH PROCESS (the optional offender label, WARN/CRITICAL only) — the
    stack's OWN processes, resolved from the ownership manifest's PORTS via one
    ``GetExtendedTcpTable`` call, then ``OpenProcess`` +
    ``GetProcessMemoryInfo`` on that HANDFUL of known pids. Never a whole-box
    walk of ~600 processes (psutil's ``process_iter`` is as forbidden as
    PowerShell — it is the enumeration cost, not the interpreter, that is
    banned). When neither ctypes nor psutil can answer, **the offender field is
    simply OMITTED** — a missing label must never cost an allocation.
  * STOPPING THE DRIVE (the abort) — ``TerminateProcess`` on our own child and
    its descendants, via one Toolhelp snapshot. NOT ``taskkill``, and
    deliberately NOT ``stack._run_kill_cmd``: that routes through
    ``kill_guard.refusal`` -> ``stack_guard._ancestor_chain`` -> a PowerShell
    CIM query on a psutil-less box, i.e. the same bug one layer down. The kill
    gate exists to stop the rig killing processes it does NOT own; this target
    is a child we spawned ourselves, whose lineage needs no adjudication (and
    ``subprocess.run(timeout=…)`` already hard-kills it unconditionally). It is
    still written to ``runs/.kill-audit.log``, which is a file append.

The ONE deliberate boundary: the stack TEARDOWN that follows a critical abort is
the existing ``stack.stop_stack``, which does shell kills. That is out of scope
by design — it runs after the drive has ended, and killing those processes is
what RETURNS the ~20 GB. The invariant covers the sampler and the drive-stop:
everything that runs *while the drive is still alive*.

FAIL-OPEN EVERYWHERE, by construction:
  * a sampling error is swallowed and counted (``errors``), never raised into a
    drive that has already been paid for;
  * ``read()`` returning None (non-Windows, ctypes unavailable) can never
    produce a band change, an abort, or an attribution;
  * the abort produces a HARNESS verdict (``COMMIT-EXHAUSTED``, absent from
    ``adapters/base.GRADED_VERDICTS`` and therefore out of every pass-rate
    denominator) — never a model verdict;
  * the layer rides ``--no-preflight`` / ``CB_NO_PREFLIGHT=1`` exactly like the
    envgate and the pre-rep hook, and never arms inside a test process
    (``kill_guard.in_test_process``) — a unit run must not sample the operator's
    box, let alone tear a live stack down.

Everything decision-shaped is a PURE function over injected facts (:func:`classify`,
:func:`apply_hysteresis`, :func:`stack_footprint_mb`, :func:`recycle_decision`,
:func:`attribution`), so the whole module is unit-testable with fake readings and
no memory dependence at all.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import kill_guard

#: Band names. Deliberately plain strings — they land verbatim in
#: ``pressure.jsonl`` and in ``summary.json``, where a reader must not need this
#: module to interpret them.
BAND_OK = "OK"
BAND_WARN = "WARN"
BAND_CRITICAL = "CRITICAL"

#: Escalation order. Escalation is immediate; DE-escalation must clear the
#: boundary by the hysteresis margin (see :func:`apply_hysteresis`).
_RANK = {BAND_OK: 0, BAND_WARN: 1, BAND_CRITICAL: 2}

#: The per-run sample log, relative to the run dir.
PRESSURE_FILE = "pressure.jsonl"

#: Defaults for the three tunables. The WARN multiple is 2x the floor because
#: the floor is already "one capped UBT build's cl.exe tree plus slack" — a
#: drive that has eaten its way down to twice that is on the path to the floor,
#: and the whole value of the WARN band is that it is recorded BEFORE anything
#: dies.
DEFAULT_WARN_MULTIPLE = 2.0
DEFAULT_SAMPLE_INTERVAL_S = 10.0
#: Re-arm margin: a reading hovering ON a threshold must not flap the log.
DEFAULT_HYSTERESIS_GB = 0.5
#: Combined private bytes of the stack's own node processes (vercel :3000 +
#: client :3002) at which a bench recycles the stack at the NEXT rep boundary.
#: 6 GB is under the measured runaway (vercel alone reached 10.9 GB) and well
#: above a healthy green stack's node pair, so it fires on the leak and not on
#: the normal state.
DEFAULT_STACK_RECYCLE_MB = 6000.0

#: The stack's own listening ports, in the order a footprint line reports them.
#: This pair is the RECYCLE scope: "the vercel/client node processes' private
#: bytes", i.e. the documented leak.
STACK_PORTS: Tuple[Tuple[str, int], ...] = (("vercel", 3000), ("client", 3002))

#: The OFFENDER scope during a drive: the recycle pair plus the two processes
#: that are large and can also be the thing that dies — the dev-browser chromium
#: (measured 7.9 GB) and the drive editor itself on its Remote Control port.
#: Naming the editor is worth a lot in a post-mortem, and it costs the same two
#: FFI calls as any other pid.
DRIVE_PORTS: Tuple[Tuple[str, int], ...] = STACK_PORTS + (
    ("dev-browser", 9222), ("editor-rc", 30010))

#: Known labels for the ports the ownership manifest records, so a
#: manifest-scoped read stays readable.
_PORT_LABELS = {3000: "vercel", 3002: "client", 9222: "dev-browser",
                30010: "editor-rc"}

#: Verdicts whose CAUSE commit pressure can plausibly be. Both are already
#: non-graded machine-fault labels; the attribution only explains them, it never
#: changes them.
_PRESSURE_SUSPECT_VERDICTS = frozenset({"EDITOR-GONE", "STACK-DOWN"})

_MB = 1024.0 * 1024.0


def verdict() -> str:
    """The non-graded harness verdict a pressure abort records. Re-exported from
    :mod:`aura_rig.stack_guard` so the between-rep hook and the in-drive abort
    can never drift into two spellings of the same machine fault."""
    from . import stack_guard
    return stack_guard.PRESSURE_VERDICT


# --------------------------------------------------------------------------- #
# Env knobs (each unparseable value reads as the default — a typo must never    #
# disable a guard, the ``commit_floor_gb`` contract verbatim).                  #
# --------------------------------------------------------------------------- #

def _env_float(name: str, default: float, env=None,
               *, positive: bool = True) -> float:
    env = os.environ if env is None else env
    raw = (env.get(name) or "").strip()
    if raw:
        try:
            val = float(raw.split()[0])
            if val > 0 or (not positive and val >= 0):
                return val
        except (ValueError, IndexError):
            pass
    return default


def warn_multiple(env=None) -> float:
    """WARN band = below ``floor * warn_multiple``. ``CB_PRESSURE_WARN_MULT``."""
    return _env_float("CB_PRESSURE_WARN_MULT", DEFAULT_WARN_MULTIPLE, env)


def sample_interval_s(env=None) -> float:
    """Seconds between in-drive samples. ``CB_PRESSURE_SAMPLE_S``."""
    return _env_float("CB_PRESSURE_SAMPLE_S", DEFAULT_SAMPLE_INTERVAL_S, env)


def hysteresis_gb(env=None) -> float:
    """De-escalation margin, in GB. ``CB_PRESSURE_HYSTERESIS_GB``."""
    return _env_float("CB_PRESSURE_HYSTERESIS_GB", DEFAULT_HYSTERESIS_GB, env,
                      positive=False)


def stack_recycle_mb(env=None) -> float:
    """Combined stack-node footprint that triggers a between-rep recycle, in MB.
    ``CB_STACK_RECYCLE_MB``. ZERO is accepted and means OFF — unlike the band
    tunables (where 0 would be a nonsense value that must read as a typo), a
    threshold of 0 is the honest way to say "cadence only", and
    :func:`recycle_decision` guards on ``thr > 0``."""
    return _env_float("CB_STACK_RECYCLE_MB", DEFAULT_STACK_RECYCLE_MB, env,
                      positive=False)


def floor_gb(env=None) -> float:
    """THE floor — ``envgate.commit_floor_gb`` (``CB_COMMIT_FLOOR_GB``). One
    source of truth shared with the pre-spend gate and the pre-rep hook; this
    module never invents a second threshold."""
    from . import envgate
    return envgate.commit_floor_gb(env)


def drive_ports(manifest: Optional[dict] = None,
                default: Sequence[Tuple[str, int]] = DRIVE_PORTS
                ) -> Tuple[Tuple[str, int], ...]:
    """The ports to attribute a pressure sample to.

    Prefers the ownership manifest's ``ports`` (``runs/.stack-manifest.json`` —
    it is the authority on what the live stack IS, and reading it is one small
    file read, no spawn), falling back to :data:`DRIVE_PORTS`. Pure when
    ``manifest`` is supplied. Never raises."""
    try:
        if manifest is None:
            from . import stack_guard
            manifest = stack_guard.read_manifest()
        ports = (manifest or {}).get("ports")
        rows = [(_PORT_LABELS.get(int(p), f"port-{int(p)}"), int(p))
                for p in ports if isinstance(p, (int, float))] if ports else []
        if rows:
            return tuple(rows)
    except Exception:  # noqa: BLE001 — scope resolution is never a verdict
        pass
    return tuple(default)


def guard_enabled(env=None) -> bool:
    """The layer's kill switch plus the shared skip switch. ``CB_PRESSURE_GUARD=0``
    disables sampling outright; ``CB_NO_PREFLIGHT=1`` skips it exactly as it
    skips the envgate and the pre-rep hook (the owner contract: every guard
    rides the same escape hatch)."""
    env = os.environ if env is None else env
    if (env.get("CB_PRESSURE_GUARD", "1").strip().lower()
            in ("0", "false", "no", "off")):
        return False
    if (env.get("CB_NO_PREFLIGHT", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return False
    return True


# --------------------------------------------------------------------------- #
# Bands (pure).                                                                #
# --------------------------------------------------------------------------- #

def warn_gb(floor: float, *, warn_mult: Optional[float] = None) -> float:
    """The WARN threshold in GB, derived from the ONE floor."""
    mult = warn_multiple() if warn_mult is None else float(warn_mult)
    return float(floor) * mult


def classify(free_gb: Optional[float], floor: float,
             *, warn_mult: Optional[float] = None) -> Optional[str]:
    """The RAW band for one reading, or None when the reading is absent.

    None is deliberately NOT ``OK``: "unmeasurable" and "healthy" are different
    facts, and only the caller (which knows the previous band) can decide what
    to do with a gap. An absent measurement is never a verdict."""
    if free_gb is None:
        return None
    if free_gb < float(floor):
        return BAND_CRITICAL
    if free_gb < warn_gb(floor, warn_mult=warn_mult):
        return BAND_WARN
    return BAND_OK


def apply_hysteresis(prev: Optional[str], raw: Optional[str],
                     free_gb: Optional[float], floor: float,
                     *, warn_mult: Optional[float] = None,
                     margin_gb: Optional[float] = None) -> Optional[str]:
    """The band to ACT on, given the previous one.

    ESCALATION IS IMMEDIATE — a box that just crossed the floor gets no grace
    period. DE-ESCALATION requires clearing the boundary being left by
    ``margin_gb``, so a reading oscillating around a threshold produces ONE log
    line, not one per sample. An absent reading holds the previous band."""
    if raw is None:
        return prev
    if prev is None:
        return raw
    if _RANK.get(raw, 0) >= _RANK.get(prev, 0):
        return raw
    if free_gb is None:                       # cannot certify a recovery
        return prev
    margin = hysteresis_gb() if margin_gb is None else float(margin_gb)
    fl = float(floor)
    if prev == BAND_CRITICAL:
        if free_gb < fl + margin:
            return BAND_CRITICAL              # not yet clear of the floor
        if raw == BAND_OK and free_gb < warn_gb(fl, warn_mult=warn_mult) + margin:
            return BAND_WARN                  # clear of the floor, not of WARN
        return raw
    # prev == WARN, raw == OK
    if free_gb < warn_gb(fl, warn_mult=warn_mult) + margin:
        return BAND_WARN
    return BAND_OK


# --------------------------------------------------------------------------- #
# Samples.                                                                     #
# --------------------------------------------------------------------------- #

@dataclass
class Sample:
    """One in-drive reading. ``offender``/``offender_mb`` are filled only on
    WARN/CRITICAL samples — naming the hog costs a process enumeration, and the
    OK path must stay to one ctypes call so a 20-minute drive can afford it."""

    t: float
    free_gb: Optional[float]
    band: Optional[str]
    elapsed_s: Optional[float] = None
    offender: Optional[str] = None
    offender_mb: Optional[float] = None
    note: Optional[str] = None

    def as_dict(self) -> dict:
        d = {"t": round(float(self.t), 3), "free_gb": self.free_gb,
             "band": self.band}
        if self.elapsed_s is not None:
            d["elapsed_s"] = round(float(self.elapsed_s), 1)
        if self.offender is not None:
            d["top_offender"] = self.offender
            d["top_offender_mb"] = self.offender_mb
        if self.note:
            d["note"] = self.note
        return d


def read_free_gb() -> Optional[float]:
    """Free commit in GB — the SAME probe the envgate floor and the pre-rep hook
    read (``envgate._read_commit_free_gb``). None off Windows / without ctypes."""
    try:
        from . import envgate
        return envgate._read_commit_free_gb()
    except Exception:  # noqa: BLE001 — a probe must never break a drive
        return None


# --------------------------------------------------------------------------- #
# IN-PROCESS Win32 probes. NO SUBPROCESS — see THE HARD INVARIANT above.        #
# --------------------------------------------------------------------------- #

#: Lazily-built, process-lifetime cache of the ctypes bindings. Built once so a
#: sample is a few FFI calls and not a re-declaration of three structures.
_WIN_API: Optional[dict] = None
_WIN_API_TRIED = False


def _win_api() -> Optional[dict]:
    """{kernel32, psapi, iphlpapi, PMCEX} with argtypes/restypes pinned — or
    None off Windows / when ctypes cannot bind. Cached for the process.

    ``restype`` on ``OpenProcess`` is load-bearing: the default ``c_int``
    TRUNCATES a 64-bit HANDLE, and the truncated value then fails or, worse,
    closes something else."""
    global _WIN_API, _WIN_API_TRIED
    if _WIN_API_TRIED:
        return _WIN_API
    _WIN_API_TRIED = True
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _PMCEX(ctypes.Structure):
            """PROCESS_MEMORY_COUNTERS_EX — ``PrivateUsage`` is the process's
            private commit, i.e. exactly what charges the system commit limit
            this whole module is about."""

            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.TerminateProcess.argtypes = [ctypes.c_void_p, wintypes.UINT]
        _WIN_API = {"ctypes": ctypes, "k32": k32,
                    "psapi": ctypes.windll.psapi,
                    "iphlpapi": ctypes.windll.iphlpapi,
                    "PMCEX": _PMCEX}
    except Exception:  # noqa: BLE001 — an unbindable API is simply "no label"
        _WIN_API = None
    return _WIN_API


#: OpenProcess access masks, tried in order: the LIMITED right first (it is
#: enough for GetProcessMemoryInfo on Vista+ and survives tighter tokens).
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_PROCESS_TERMINATE = 0x0001


def _open_process(pid: int, *access: int):
    api = _win_api()
    if api is None:
        return None, None
    k32 = api["k32"]
    for mask in access:
        try:
            h = k32.OpenProcess(mask, False, int(pid))
        except Exception:  # noqa: BLE001
            h = None
        if h:
            return h, k32
    return None, k32


def win_private_bytes(pid: int) -> Optional[float]:
    """Private commit of ONE known pid, in bytes — ``OpenProcess`` +
    ``GetProcessMemoryInfo``, two FFI calls and no enumeration. None when the
    pid is gone or the handle is refused."""
    api = _win_api()
    if api is None:
        return None
    h, k32 = _open_process(pid, _PROCESS_QUERY_LIMITED_INFORMATION,
                           _PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ)
    if not h:
        return None
    try:
        ctypes = api["ctypes"]
        counters = api["PMCEX"]()
        counters.cb = ctypes.sizeof(api["PMCEX"])
        if not api["psapi"].GetProcessMemoryInfo(
                ctypes.c_void_p(h), ctypes.byref(counters), counters.cb):
            return None
        return float(counters.PrivateUsage or counters.PagefileUsage)
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            k32.CloseHandle(h)
        except Exception:  # noqa: BLE001
            pass


#: MIB_TCPROW_OWNER_PID is 6 DWORDs; MIB_TCPTABLE_OWNER_PID is a DWORD count
#: followed by the array (DWORD-aligned, so no padding).
_TCPROW_SIZE = 24
_TCP_TABLE_OWNER_PID_LISTENER = 3
_AF_INET = 2
_ERROR_INSUFFICIENT_BUFFER = 122


def win_listening_pids(ports: Sequence[int]) -> Dict[int, List[int]]:
    """{port: [pid]} for LISTENING TCP sockets, from ONE ``GetExtendedTcpTable``
    call.

    This is the cheap replacement for both ``netstat`` (a spawn) and psutil's
    ``net_connections`` (an enumeration): the kernel hands back a few tens of KB
    describing only the listener table, which is read once and scanned in
    place."""
    api = _win_api()
    want = {int(p) for p in (ports or ())}
    if api is None or not want:
        return {}
    try:
        ctypes = api["ctypes"]
        from ctypes import wintypes
        iphlpapi = api["iphlpapi"]
        size = wintypes.DWORD(0)
        rc = iphlpapi.GetExtendedTcpTable(
            None, ctypes.byref(size), False, _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER, 0)
        if rc not in (0, _ERROR_INSUFFICIENT_BUFFER) or size.value < 4:
            return {}
        buf = ctypes.create_string_buffer(size.value)
        rc = iphlpapi.GetExtendedTcpTable(
            buf, ctypes.byref(size), False, _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER, 0)
        if rc != 0:
            return {}
        raw = buf.raw                      # ONE copy, then scanned by offset
        count = int.from_bytes(raw[:4], "little")
        out: Dict[int, List[int]] = {}
        off = 4
        for _ in range(count):
            if off + _TCPROW_SIZE > len(raw):
                break
            # dwLocalPort is in NETWORK byte order in the low 16 bits.
            net_port = int.from_bytes(raw[off + 8:off + 12], "little")
            port = ((net_port & 0xFF) << 8) | ((net_port >> 8) & 0xFF)
            if port in want:
                pid = int.from_bytes(raw[off + 20:off + 24], "little")
                if pid:
                    out.setdefault(port, [])
                    if pid not in out[port]:
                        out[port].append(pid)
            off += _TCPROW_SIZE
        return out
    except Exception:  # noqa: BLE001
        return {}


def terminate_tree_in_process(pid: int) -> int:
    """``TerminateProcess`` ``pid`` and its descendants, IN-PROCESS. Returns how
    many were terminated.

    Why not ``taskkill /T`` (or ``stack._run_kill_cmd``): this runs at the
    CRITICAL band, during the commit crisis. A spawn there is the exact
    allocation the guard exists to avoid — and the gated variant is worse, since
    ``kill_guard.refusal`` reaches ``stack_guard._ancestor_chain``, which shells
    a PowerShell CIM query when psutil is absent (it is, here).

    The TREE matters, not just the child: on Windows the drive child is
    ``cmd.exe`` running the npx/tsx shim chain, and node INHERITS the stdout/
    stderr pipe handles — so killing ``cmd.exe`` alone leaves ``communicate()``
    blocked on a pipe that never reaches EOF, i.e. the abort would not actually
    return until the ceiling."""
    api = _win_api()
    if api is None:
        return 0
    try:
        ctypes = api["ctypes"]
        from ctypes import wintypes
        k32 = api["k32"]

        class _PROCESSENTRY32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_char * 260)]

        TH32CS_SNAPPROCESS = 0x00000002
        k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            children: Dict[int, List[int]] = {}
        else:
            children = {}
            try:
                entry = _PROCESSENTRY32()
                entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
                ok = k32.Process32First(ctypes.c_void_p(snap),
                                        ctypes.byref(entry))
                while ok:
                    children.setdefault(
                        int(entry.th32ParentProcessID), []).append(
                            int(entry.th32ProcessID))
                    ok = k32.Process32Next(ctypes.c_void_p(snap),
                                           ctypes.byref(entry))
            finally:
                k32.CloseHandle(snap)
        # Descendants first, then the root: a parent cannot respawn a child we
        # have already taken out.
        order: List[int] = []
        frontier = [int(pid)]
        seen = {int(pid)}
        while frontier:
            cur = frontier.pop()
            for kid in children.get(cur, ()):
                if kid not in seen:
                    seen.add(kid)
                    order.append(kid)
                    frontier.append(kid)
        order.append(int(pid))
        killed = 0
        for target in order:
            h, _k = _open_process(target, _PROCESS_TERMINATE)
            if not h:
                continue
            try:
                if k32.TerminateProcess(ctypes.c_void_p(h), 1):
                    killed += 1
            except Exception:  # noqa: BLE001
                pass
            finally:
                try:
                    k32.CloseHandle(h)
                except Exception:  # noqa: BLE001
                    pass
        return killed
    except Exception:  # noqa: BLE001 — a failed abort must not raise into a drive
        return 0


def private_mb(pid: int) -> Optional[float]:
    """Private commit of ONE known pid, in MB. ctypes first; psutil ONLY as a
    per-pid fallback (never ``process_iter`` — the enumeration is the cost).
    None when unmeasurable, which callers must treat as "no label", never 0."""
    raw = win_private_bytes(pid)
    if raw is not None:
        return round(raw / _MB, 1)
    try:
        import psutil  # type: ignore
        mi = psutil.Process(int(pid)).memory_info()
        val = getattr(mi, "private", None) or getattr(mi, "rss", None)
        return round(float(val) / _MB, 1) if val else None
    except Exception:  # noqa: BLE001
        return None


def read_stack_offender(ports: Sequence[Tuple[str, int]] = None
                        ) -> Optional[Tuple[str, float]]:
    """(label, private MB) of the LARGEST of the STACK's OWN processes, or None.

    Scoped to the stack on purpose, and that scope is the honest one twice over:
    the documented runaway IS the stack (vercel :3000 at 10.9 GB), and finding
    "the biggest process on the box" would require walking every process —
    the enumeration this module is forbidden to do. Ports come from the
    ownership manifest when one exists, so the label follows whatever the live
    stack actually is.

    None whenever the ports resolve to nothing or no pid can be measured: the
    offender is an OPTIONAL enrichment and a missing one costs the sample
    nothing (``free_gb`` is the number that matters)."""
    entries = read_stack_footprints(ports if ports is not None else drive_ports())
    best: Optional[Tuple[str, float]] = None
    for e in entries:
        if e.mb is None:
            continue
        if best is None or e.mb > best[1]:
            best = (f"{e.label}:{e.pid}", e.mb)
    return best


# --------------------------------------------------------------------------- #
# The in-drive monitor.                                                        #
# --------------------------------------------------------------------------- #

class DriveMonitor:
    """Samples free commit for as long as a drive runs; bands it; records it.

    Two ways to use it, both exercised by the tests: call :meth:`poll` directly
    (deterministic, no threads — this is where the band logic is tested), or
    :meth:`start`/:meth:`stop` a daemon thread around a blocking drive (the
    production path in :func:`aura_rig.aura_product.drive`).

    Every touchable fact is injected: ``read`` (free GB), ``offenders`` (the top
    process), ``clock``, ``log``, ``on_critical``. NOTHING here reads the real
    machine unless the defaults are left in place.
    """

    def __init__(self, run_dir=None, *,
                 floor: Optional[float] = None,
                 warn_mult: Optional[float] = None,
                 margin_gb: Optional[float] = None,
                 interval_s: Optional[float] = None,
                 read: Optional[Callable[[], Optional[float]]] = None,
                 offenders: Optional[Callable[[], Optional[Tuple[str, float]]]] = None,
                 on_critical: Optional[Callable[["Sample"], None]] = None,
                 liveness: Optional[Callable[[], Optional[bool]]] = None,
                 on_stack_down: Optional[Callable[[], None]] = None,
                 liveness_strikes: int = 3,
                 clock: Callable[[], float] = time.time,
                 offender_min_gap_s: float = 30.0,
                 log: Callable[[str], None] = print) -> None:
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.floor = float(floor) if floor is not None else floor_gb()
        self.warn_mult = warn_multiple() if warn_mult is None else float(warn_mult)
        self.margin_gb = hysteresis_gb() if margin_gb is None else float(margin_gb)
        self.interval_s = (sample_interval_s() if interval_s is None
                           else float(interval_s))
        self._read = read or read_free_gb
        self._offenders = offenders or read_stack_offender
        self._on_critical = on_critical
        # CLIENT LIVENESS (2026-08-07, build-machine finding 1): the client :3002 is
        # the least-guarded stack leg — it died 92 s into a measured turn and
        # the cloud-threads epoch kept generating AND BILLING against it for
        # the rest of the ceiling ($2.71, 39 starved tool calls). The probe is
        # an in-process socket connect (sockets are not spawns; the no-spawn
        # invariant is untouched), injected like every other touchable fact.
        # None = probe unavailable this sample, which never counts as a strike
        # (an unmeasured leg must not abort a paid drive — the ram_pct
        # contract). Strikes must be CONSECUTIVE: one transient refusal during
        # a client GC pause proves nothing.
        self._liveness = liveness
        self._on_stack_down = on_stack_down
        self._liveness_strikes = max(1, int(liveness_strikes))
        self.liveness_fails = 0          # consecutive
        self.liveness_checks = 0
        self.liveness_last_ok_s: Optional[float] = None
        self.stack_down = False
        self.stack_down_note: Optional[str] = None
        self._clock = clock
        self._log = log
        self._offender_min_gap_s = float(offender_min_gap_s)

        self.band: Optional[str] = None
        self.samples = 0
        self.recorded = 0
        self.unmeasured = 0
        self.errors = 0
        self.min_free_gb: Optional[float] = None
        self.first_free_gb: Optional[float] = None
        self.last_free_gb: Optional[float] = None
        self.band_counts: Dict[str, int] = {BAND_OK: 0, BAND_WARN: 0,
                                            BAND_CRITICAL: 0}
        self.crossings: List[dict] = []
        self.aborted = False
        self.abort_note: Optional[str] = None
        self.abort_top_committers: Optional[list] = None
        self._t0 = self._clock()
        self._last_offender_t = 0.0
        self._last_offender: Optional[Tuple[str, float]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

    # -- properties ------------------------------------------------------- #

    @property
    def warn_at_gb(self) -> float:
        return warn_gb(self.floor, warn_mult=self.warn_mult)

    @property
    def path(self) -> Optional[Path]:
        return (self.run_dir / PRESSURE_FILE) if self.run_dir is not None else None

    # -- one sample ------------------------------------------------------- #

    def poll(self) -> Optional[Sample]:
        """Take ONE reading, band it, record it, and fire the critical callback
        at most once. Never raises: a sampler that can break a paid drive is
        worse than no sampler (``errors`` counts what was swallowed)."""
        try:
            return self._poll()
        except Exception:  # noqa: BLE001 — fail-open, by contract
            with self._lock:
                self.errors += 1
            return None

    def _poll(self) -> Optional[Sample]:
        now = self._clock()
        free = self._read()
        with self._lock:
            self.samples += 1
            if free is None:
                self.unmeasured += 1
            else:
                free = float(free)
                self.last_free_gb = free
                if self.first_free_gb is None:
                    self.first_free_gb = free
                if self.min_free_gb is None or free < self.min_free_gb:
                    self.min_free_gb = free
            prev = self.band
            raw = classify(free, self.floor, warn_mult=self.warn_mult)
            band = apply_hysteresis(prev, raw, free, self.floor,
                                    warn_mult=self.warn_mult,
                                    margin_gb=self.margin_gb)
            self.band = band
            if band in self.band_counts:
                self.band_counts[band] += 1
            crossed = band is not None and band != prev
            sample = Sample(t=now, free_gb=free, band=band,
                            elapsed_s=now - self._t0)

        if band in (BAND_WARN, BAND_CRITICAL):
            off = self._offender(now)
            if off:
                sample.offender, sample.offender_mb = off
            self._append(sample)

        # LOG ONCE PER CROSSING, never per sample: a 20-minute drive samples
        # ~120 times, and a per-sample line would bury the crossing that matters
        # under a wall the operator learns to scroll past.
        if crossed:
            with self._lock:
                self.crossings.append({"t": round(now, 3), "from": prev,
                                       "to": band, "free_gb": free})
            self._log_crossing(prev, band, free, sample)

        if band == BAND_CRITICAL and crossed:
            self._fire_critical(sample)

        self._check_liveness(now)
        return sample

    def _check_liveness(self, now: float) -> None:
        """One client-liveness probe per sample; fires ``on_stack_down`` ONCE
        after ``liveness_strikes`` CONSECUTIVE dead readings.

        Fail-open in every direction (the sampler contract): no probe wired =
        no behavior; a probe that raises or answers None counts as UNMEASURED,
        never as a strike; the callback fires at most once and its exceptions
        are swallowed — a liveness bug must never break the drive it guards."""
        if self._liveness is None or self.stack_down:
            return
        try:
            alive = self._liveness()
        except Exception:  # noqa: BLE001 — probe error is not a strike
            alive = None
        if alive is None:
            return
        with self._lock:
            self.liveness_checks += 1
            if alive:
                self.liveness_fails = 0
                self.liveness_last_ok_s = round(now - self._t0, 1)
                return
            self.liveness_fails += 1
            fails = self.liveness_fails
            if fails < self._liveness_strikes:
                return
            self.stack_down = True
            self.stack_down_note = (
                f"client liveness lost: {fails} consecutive dead probes "
                f"(~{fails * self.interval_s:.0f}s) at t+{now - self._t0:.0f}s; "
                f"last OK at t+{self.liveness_last_ok_s or 0:.0f}s")
        self._log(f"  !! PRESSURE-GUARD: {self.stack_down_note} — stopping the "
                  f"drive (cloud-thread generation would keep BILLING against "
                  f"a dead client; measured $2.71 on 2026-08-07)")
        if self._on_stack_down is not None:
            try:
                self._on_stack_down()
            except Exception:  # noqa: BLE001 — never into a paid drive
                pass

    def _offender(self, now: float) -> Optional[Tuple[str, float]]:
        """The top offender, re-read at most every ``offender_min_gap_s`` (the
        enumeration is the expensive half of a sample; the hog does not change
        identity between two 10 s ticks)."""
        if (self._last_offender is not None
                and (now - self._last_offender_t) < self._offender_min_gap_s):
            return self._last_offender
        try:
            off = self._offenders()
        except Exception:  # noqa: BLE001
            with self._lock:
                self.errors += 1
            return self._last_offender
        if off:
            self._last_offender = (str(off[0]), float(off[1]))
            self._last_offender_t = now
        return self._last_offender

    def _append(self, sample: Sample) -> None:
        p = self.path
        if p is None:
            with self._lock:
                self.recorded += 1
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(sample.as_dict()) + "\n")
                fh.flush()
            with self._lock:
                self.recorded += 1
        except OSError:
            with self._lock:
                self.errors += 1

    def _log_crossing(self, prev, band, free, sample: Sample) -> None:
        who = ""
        if sample.offender:
            who = f" | biggest process: {sample.offender} {sample.offender_mb:.0f} MB"
        free_s = "unmeasured" if free is None else f"{free:.1f} GB free commit"
        if band == BAND_CRITICAL:
            self._log(f"  !!    COMMIT CRITICAL mid-drive: {free_s} < floor "
                      f"{self.floor:.0f} GB — aborting the drive DELIBERATELY "
                      f"(a drive that dies here records EDITOR-GONE with no "
                      f"crash dump and costs the whole turn){who}")
        elif band == BAND_WARN:
            self._log(f"  ..    commit pressure WARN mid-drive: {free_s} < "
                      f"{self.warn_at_gb:.0f} GB (2x the {self.floor:.0f} GB "
                      f"floor) — sampling into {PRESSURE_FILE}{who}")
        elif prev is not None:
            self._log(f"  OK    commit pressure recovered mid-drive: {free_s} "
                      f"(was {prev})")

    def _fire_critical(self, sample: Sample) -> None:
        free = sample.free_gb
        note = (f"free commit fell to "
                f"{'unmeasured' if free is None else f'{free:.1f} GB'} "
                f"(hard floor {self.floor:.0f} GB) "
                f"{sample.elapsed_s or 0.0:.0f}s into the measured turn"
                + (f"; biggest process {sample.offender} "
                   f"{sample.offender_mb:.0f} MB" if sample.offender else "")
                + ". The drive was stopped deliberately and the stack torn "
                  "down: an editor that dies of commit exhaustion leaves no "
                  "crash dump and grades as EDITOR-GONE (or worse, as the "
                  "agent failing). Non-graded harness verdict.")
        with self._lock:
            if self.aborted:
                return
            self.aborted = True
            self.abort_note = note
        # WHOLE-BOX CULPRITS, once, at the abort (added 2026-08-07 after this
        # guard's first real firing MISATTRIBUTED itself). The per-sample
        # offender label is scoped to the stack's OWN pids on purpose - a
        # whole-box walk every 10 s is the banned cost. But that scoping means
        # the label names OUR editor even when an EXTERNAL process is the
        # difference-maker, which is precisely the case this guard exists for:
        # measured here, the label read "editor-rc 8331 MB" while a shipped
        # game held 10,891 MB and was the actual cause. A reader would have
        # blamed the rig. So at abort time - ONE shot, drive already ending -
        # take the spawn-free whole-box snapshot (pure ctypes, same invariant:
        # spawn_health imports no subprocess) so the evidence names the real
        # hog. Fail-open: forensics never block an abort.
        try:
            from . import spawn_health
            if self.run_dir is not None:
                snap = spawn_health.snapshot(
                    self.run_dir, trigger=f"COMMIT-CRITICAL {note[:120]}")
                tops = (snap or {}).get("top_private_mb") or []
                if tops:
                    self.abort_top_committers = tops[:5]
                    self._log("     whole-box top committers: " + ", ".join(
                        f"{t['name']} {t['mb']} MB" for t in tops[:3]))
        except Exception:  # noqa: BLE001 - forensics must never block an abort
            pass
        if self._on_critical is None:
            return
        try:
            self._on_critical(sample)
        except Exception as e:  # noqa: BLE001 — an abort hook must not raise
            self._log(f"  WARN  pressure: abort hook failed "
                      f"({type(e).__name__}: {e}) — the drive runs on; the "
                      f"verdict is still recorded")
            with self._lock:
                self.errors += 1

    # -- thread lifecycle -------------------------------------------------- #

    def start(self) -> "DriveMonitor":
        """Arm the daemon sampler. Daemon on purpose: a wedged sampler must
        never hold the process open past the drive."""
        if self._thread is not None:
            return self
        self._t0 = self._clock()
        self._thread = threading.Thread(target=self._loop, name="cb-pressure",
                                        daemon=True)
        self._thread.start()
        return self

    def _loop(self) -> None:
        # Sample IMMEDIATELY, then on the cadence: the first reading is the
        # drive's own baseline and is what makes min-free meaningful.
        while True:
            self.poll()
            if self._stop_evt.wait(self.interval_s):
                return

    def stop(self, *, final_poll: bool = True) -> "DriveMonitor":
        """Stop sampling (idempotent) and take a final at-exit reading, so
        ``last_free_gb`` is the state the drive ENDED in — the number a later
        EDITOR-GONE is attributed from."""
        self._stop_evt.set()
        th, self._thread = self._thread, None
        if th is not None:
            th.join(timeout=max(2.0, self.interval_s))
        if final_poll:
            self.poll()
        return self

    def __enter__(self) -> "DriveMonitor":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # -- the record -------------------------------------------------------- #

    def report(self) -> dict:
        """The block that lands in ``summary.json`` under ``"pressure"``.

        Written even for a perfectly healthy drive, on purpose: recording
        ``min_free_gb`` costs nothing, and its ABSENCE is what made the
        2026-08-06/07 mid-drive editor deaths take two days to attribute."""
        with self._lock:
            worst = BAND_OK
            for b in (BAND_CRITICAL, BAND_WARN):
                if self.band_counts.get(b):
                    worst = b
                    break
            rep = {
                "samples": self.samples,
                "interval_s": self.interval_s,
                "floor_gb": self.floor,
                "warn_gb": round(self.warn_at_gb, 2),
                "min_free_gb": (round(self.min_free_gb, 2)
                                if self.min_free_gb is not None else None),
                "first_free_gb": (round(self.first_free_gb, 2)
                                  if self.first_free_gb is not None else None),
                "last_free_gb": (round(self.last_free_gb, 2)
                                 if self.last_free_gb is not None else None),
                "bands": dict(self.band_counts),
                "worst_band": worst,
                "crossings": list(self.crossings),
                "recorded": self.recorded,
                "unmeasured": self.unmeasured,
                "errors": self.errors,
                "aborted": self.aborted,
                "stack_down": self.stack_down,
                "liveness_checks": self.liveness_checks,
            }
            if self.liveness_last_ok_s is not None:
                rep["liveness_last_ok_s"] = self.liveness_last_ok_s
        if self.abort_note:
            rep["abort_note"] = self.abort_note
        if self.abort_top_committers:
            rep["abort_top_committers"] = self.abort_top_committers
        if self.stack_down_note:
            rep["stack_down_note"] = self.stack_down_note
        if self.recorded and self.path is not None:
            rep["log"] = PRESSURE_FILE
        return rep


def client_alive(port: int = 3002, timeout_s: float = 1.5) -> Optional[bool]:
    """In-process client-liveness probe: can we OPEN a TCP connection to the
    stack's client port? Sockets are not spawns — the no-spawn invariant is
    untouched. True/False on a definitive answer; None when the probe itself
    could not run (never a strike). A refused connect answers in microseconds;
    a hung-but-listening client still accepts (this probe detects a DEAD
    process, not a wedged one — the wedge family has its own remedies)."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", int(port)),
                                      timeout=float(timeout_s)):
            return True
    except (ConnectionRefusedError, OSError):
        return False
    except Exception:  # noqa: BLE001 — unmeasurable, not dead
        return None


def start_drive_monitor(run_dir=None, *,
                        on_critical: Optional[Callable[[Sample], None]] = None,
                        on_stack_down: Optional[Callable[[], None]] = None,
                        log: Callable[[str], None] = print,
                        env=None) -> Optional[DriveMonitor]:
    """Arm an in-drive monitor, or return None when the layer is off.

    Returns None — never a disabled stub — so the caller's ``if monitor:`` reads
    as "was anything sampled?". OFF means: the kill switch / the shared
    ``CB_NO_PREFLIGHT`` skip, or a TEST process (a unit run must not sample the
    operator's box or reach the abort path; the whole point of
    ``kill_guard.in_test_process`` is that ambiguity refuses)."""
    try:
        if not guard_enabled(env):
            return None
        if kill_guard.in_test_process() and not kill_guard.env_true(
                "CB_ALLOW_REAL_KILLS", env):
            return None
        return DriveMonitor(run_dir, on_critical=on_critical,
                            liveness=client_alive,
                            on_stack_down=on_stack_down,
                            log=log).start()
    except Exception:  # noqa: BLE001 — arming must never break a drive
        return None


# --------------------------------------------------------------------------- #
# Post-hoc attribution.                                                        #
# --------------------------------------------------------------------------- #

def attribution(verdict_str: Optional[str], report: Optional[dict]) -> Optional[str]:
    """The probable-cause sentence for a machine-fault verdict, or None.

    Fires only when ALL of: the verdict is one commit pressure can cause
    (EDITOR-GONE / STACK-DOWN), the drive actually took a sample, and the LAST
    sample sat under the WARN line. That last condition is the honest one — a
    drive that ended with 40 GB free did not die of pressure, and claiming it
    did would poison the next investigation exactly as the missing evidence
    poisoned this one."""
    if not isinstance(report, dict):
        return None
    if (verdict_str or "") not in _PRESSURE_SUSPECT_VERDICTS:
        return None
    last = report.get("last_free_gb")
    warn = report.get("warn_gb")
    fl = report.get("floor_gb")
    if last is None or warn is None or fl is None:
        return None
    try:
        last, warn, fl = float(last), float(warn), float(fl)
    except (TypeError, ValueError):
        return None
    if last >= warn:
        return None
    lowest = report.get("min_free_gb")
    low_s = (f", low-water {float(lowest):.1f} GB"
             if isinstance(lowest, (int, float)) else "")
    return (f"PROBABLE CAUSE: COMMIT PRESSURE. The last in-drive sample read "
            f"{last:.1f} GB free commit{low_s} — under the {warn:.0f} GB WARN "
            f"line ({fl:.0f} GB hard floor), so the box was already starving "
            f"when the drive died. A commit-exhausted editor fails an "
            f"allocation and leaves NO crash dump, which is exactly what this "
            f"verdict looks like. See {PRESSURE_FILE} in this run dir; free "
            f"commit by tearing the stack down (`cb down`) before re-running.")


def annotate_summary(summary: dict, report: Optional[dict] = None, *,
                     log: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """Write the attribution into ``summary["pressure_attribution"]`` (and log
    it once). Returns the sentence, or None. Never raises — this runs on the
    verdict path of a finished, already-paid run."""
    try:
        if not isinstance(summary, dict):
            return None
        rep = report if report is not None else summary.get("pressure")
        note = attribution(summary.get("verdict"), rep)
        if not note:
            return None
        summary["pressure_attribution"] = note
        if log is not None:
            log("[!] " + note)
        return note
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Leak-triggered recycle (pure decision + a best-effort footprint reader).      #
# --------------------------------------------------------------------------- #

@dataclass
class ProcFootprint:
    """One measured stack process. ``mb`` is PRIVATE bytes — the quantity that
    charges the commit limit; working set would understate a leaked heap that
    has been paged out, which is precisely the state being detected."""

    label: str
    pid: Optional[int]
    mb: Optional[float]


def stack_footprint_mb(entries: Sequence) -> Optional[float]:
    """Combined MB over measured stack processes, or None when NOTHING could be
    measured. Pure. Accepts :class:`ProcFootprint`s or plain ``(label, pid, mb)``
    tuples/dicts, so a caller may hand it whatever its probe produced.

    None (not 0.0) on a blind read is load-bearing: 0 MB would read as "the
    stack is tiny, no recycle needed", i.e. a failed measurement silently
    voting AGAINST the guard. An absent measurement is never a verdict."""
    total = 0.0
    seen = False
    seen_pids = set()
    for e in entries or ():
        if isinstance(e, ProcFootprint):
            pid, mb = e.pid, e.mb
        elif isinstance(e, dict):
            pid, mb = e.get("pid"), e.get("mb")
        else:
            try:
                _label, pid, mb = e
            except (TypeError, ValueError):
                continue
        if mb is None:
            continue
        # A pid listening on BOTH ports (one node serving :3000 and :3002 in a
        # combined dev server) must be counted once, or the threshold fires at
        # half the real footprint.
        if pid is not None:
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
        try:
            total += float(mb)
        except (TypeError, ValueError):
            continue
        seen = True
    return round(total, 1) if seen else None


def recycle_decision(*, reps_since_recycle: int, cadence: int,
                     footprint_mb: Optional[float] = None,
                     threshold_mb: Optional[float] = None) -> Tuple[bool, str]:
    """PURE: should the bench recycle the stack at THIS rep boundary?

    Two independent triggers, either sufficient:

      * CADENCE — ``--restart-stack-every N`` (unchanged behaviour, and still
        the baseline: it bounds growth even when the footprint probe is blind);
      * LEAK — the stack's OWN node processes (vercel :3000 + client :3002)
        crossed ``threshold_mb`` combined. The cadence alone cannot see this:
        4 short reps and 4 long ones leak wildly different amounts, and the
        measured runaway (vercel at 10.9 GB) got there INSIDE one cadence
        window.

    Returns ``(recycle, reason)``; the reason is logged verbatim so a recycle is
    never mysterious. ``footprint_mb=None`` (blind probe) can only ever decline
    the leak trigger — it never manufactures one."""
    cadence = max(0, int(cadence or 0))
    if cadence > 0 and int(reps_since_recycle) >= cadence:
        return True, (f"cadence: {reps_since_recycle} rep(s) since the last "
                      f"recycle (--restart-stack-every {cadence})")
    if footprint_mb is None:
        return False, ""
    thr = stack_recycle_mb() if threshold_mb is None else float(threshold_mb)
    if thr > 0 and float(footprint_mb) >= thr:
        return True, (f"leak: the stack's own node processes hold "
                      f"{float(footprint_mb):,.0f} MB combined (>= "
                      f"{thr:,.0f} MB, CB_STACK_RECYCLE_MB) — the next drive "
                      f"would start on an already-bloated stack")
    return False, ""


def _private_mb_map(pids: Sequence[int]) -> Dict[int, float]:
    """{pid: private MB} for a HANDFUL of known pids — ctypes per pid, psutil
    per pid as a fallback. NO subprocess, NO ``process_iter``. Missing pids are
    simply absent (the caller records them as unmeasured, never as zero)."""
    out: Dict[int, float] = {}
    for pid in {int(p) for p in (pids or ()) if p}:
        mb = private_mb(pid)
        if mb is not None:
            out[pid] = mb
    return out


def read_stack_footprints(ports: Sequence[Tuple[str, int]] = STACK_PORTS, *,
                          listening_pids: Optional[Callable[[int], List[int]]] = None,
                          private_mb: Optional[Callable[[Sequence[int]], Dict[int, float]]] = None
                          ) -> List[ProcFootprint]:
    """Measure the stack's own processes by LISTENING PORT — all in-process.

    Port-resolved rather than cmdline-matched on purpose: the identity that
    matters is "whoever is serving :3000 / :3002 right now", and a recycle (or a
    per-drive editor restart) replaces those pids — resolving every time follows
    the restart instead of reporting a dead pid's last known size (the
    ``_client_sampler`` lesson).

    The default port probe is ONE ``GetExtendedTcpTable`` call shared across
    every port, NOT ``stack._listening_pids`` — that one shells ``netstat``
    whenever psutil is missing, which is the spawn this module forbids. Both
    probes stay injectable; a blind read yields entries with ``mb=None``, which
    :func:`stack_footprint_mb` reports as unmeasured (never as zero)."""
    lp = listening_pids
    if lp is None:
        table = win_listening_pids([p for _l, p in ports])
        lp = lambda port: table.get(port, [])  # noqa: E731 — one-line seam
    pm = private_mb or _private_mb_map
    found: List[Tuple[str, Optional[int]]] = []
    for label, port in ports:
        try:
            pids = lp(port) or []
        except Exception:  # noqa: BLE001
            pids = []
        if not pids:
            found.append((label, None))
            continue
        for pid in pids:
            found.append((label, pid))
    try:
        sizes = pm([pid for _l, pid in found if pid])
    except Exception:  # noqa: BLE001
        sizes = {}
    return [ProcFootprint(label=label, pid=pid,
                          mb=(sizes.get(pid) if pid else None))
            for label, pid in found]


def measure_stack_footprint_mb(**kw) -> Optional[float]:
    """Convenience: :func:`read_stack_footprints` -> :func:`stack_footprint_mb`.
    None when nothing could be measured. Never raises."""
    try:
        return stack_footprint_mb(read_stack_footprints(**kw))
    except Exception:  # noqa: BLE001
        return None


__all__ = [
    "BAND_OK", "BAND_WARN", "BAND_CRITICAL", "PRESSURE_FILE",
    "DEFAULT_WARN_MULTIPLE", "DEFAULT_SAMPLE_INTERVAL_S",
    "DEFAULT_HYSTERESIS_GB", "DEFAULT_STACK_RECYCLE_MB", "STACK_PORTS",
    "verdict", "warn_multiple", "sample_interval_s", "hysteresis_gb",
    "stack_recycle_mb", "floor_gb", "guard_enabled", "warn_gb",
    "classify", "apply_hysteresis", "Sample", "read_free_gb",
    "read_stack_offender", "DriveMonitor", "start_drive_monitor",
    "attribution", "annotate_summary", "ProcFootprint", "stack_footprint_mb",
    "recycle_decision", "read_stack_footprints", "measure_stack_footprint_mb",
    "DRIVE_PORTS", "drive_ports", "win_private_bytes", "win_listening_pids",
    "private_mb", "terminate_tree_in_process",
]
