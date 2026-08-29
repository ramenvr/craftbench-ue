"""spawn_health — detect 0xC0000142 spawn poisoning and capture forensics.

WHY (build-machine overnight, 2026-08-07). STATUS_DLL_INIT_FAILED (0xC0000142 /
3221225794) storms are BOX-STATE: new processes die at DLL init while running
ones live on, a brand-new process tree re-poisons within ~20 minutes, and the
state self-heals as resources free. It struck arbitrary spawn sites — git,
node, editor auth, the login probe, even ``taskkill`` — so per-site retries
cannot beat it (measured: all 3 direct-node retries died 5 s apart) and the
bench cycled 8+ ERR reps at $0 learning nothing.

Two jobs, both deliberately dumb:

  * :func:`looks_like_init_death` — the string signature of an init death in a
    rep's error, for the bench-level circuit breaker (2 CONSECUTIVE matches =
    machine fault; abort the bench with a NAMED reason instead of cycling).
  * :func:`snapshot` — SPAWN-FREE forensics at detection time, appended to
    ``runs/.spawn-poisoning.jsonl``. Spawn-free is not hygiene here, it is the
    only option: the box is in precisely the state where new spawns die. The
    top hypotheses (session desktop-heap exhaustion vs commit-during-DLL-load
    vs AV injection) are DISTINGUISHED by exactly these numbers, so the next
    recurrence becomes root-cause data instead of another guess.

Never raises, never gates a verdict, never spawns — the pressure.py contract.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

#: exit 3221225794 == 0xC0000142 == STATUS_DLL_INIT_FAILED. The hex form
#: appears in tracebacks, the decimal in `run.py exit N` rep errors.
INIT_DEATH_RX = re.compile(r"3221225794|0xC0000142|STATUS_DLL_INIT_FAILED",
                           re.IGNORECASE)

#: Consecutive init-death reps that trip the breaker. Two, not one: a single
#: hit can be one doomed child; two in a row on DIFFERENT spawn sites is the
#: measured storm shape. Not three: every extra cycle is another ~1 min of
#: bring-up churn producing zero information.
BREAKER_THRESHOLD = 2

SNAPSHOT_FILE = ".spawn-poisoning.jsonl"


def looks_like_init_death(error: Optional[str]) -> bool:
    """True when a rep's error text carries the 0xC0000142 signature."""
    return bool(error) and bool(INIT_DEATH_RX.search(str(error)))


def snapshot(runs_dir, *, trigger: str = "") -> Optional[dict]:
    """One spawn-free forensic record, appended to ``runs/.spawn-poisoning.jsonl``.

    Collected entirely in-process: free/total commit (GlobalMemoryStatusEx),
    process + thread totals and the top-10 private-bytes processes (one
    Toolhelp walk + OpenProcess per pid), this process's session id, and GUI
    handle totals for the top pids (GetGuiResources — the desktop-heap
    correlate). Every field is optional; a reader that fails is omitted."""
    rec: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "trigger": (trigger or "")[:300]}
    try:
        if os.name == "nt":
            _collect_windows(rec)
    except Exception:  # noqa: BLE001 — forensics must never raise
        pass
    try:
        p = Path(runs_dir) / SNAPSHOT_FILE
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
    except Exception:  # noqa: BLE001
        return None
    return rec


def _collect_windows(rec: dict) -> None:
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    stat = _MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if k32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        gb = 1024.0 ** 3
        rec["commit_free_gb"] = round(stat.ullAvailPageFile / gb, 2)
        rec["commit_limit_gb"] = round(stat.ullTotalPageFile / gb, 2)
        rec["ram_free_gb"] = round(stat.ullAvailPhys / gb, 2)

    sid = wintypes.DWORD()
    if k32.ProcessIdToSessionId(k32.GetCurrentProcessId(), ctypes.byref(sid)):
        rec["session_id"] = int(sid.value)

    TH32CS_SNAPPROCESS = 0x2

    class _PE32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return
    procs = []
    threads = 0
    try:
        pe = _PE32()
        pe.dwSize = ctypes.sizeof(_PE32)
        ok = k32.Process32First(snap, ctypes.byref(pe))
        while ok:
            procs.append((int(pe.th32ProcessID),
                          pe.szExeFile.decode("mbcs", errors="replace")))
            threads += int(pe.cntThreads)
            ok = k32.Process32Next(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    rec["process_count"] = len(procs)
    rec["thread_count"] = threads

    # top private-bytes + GUI handles (the desktop-heap correlate) — bounded
    # per-pid syscalls, no enumeration beyond the snapshot already taken.
    class _PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t)]

    PROCESS_QUERY_LIMITED = 0x1000
    GR_GDIOBJECTS, GR_USEROBJECTS = 0, 1
    psapi = ctypes.windll.psapi
    user32 = ctypes.windll.user32
    tops = []
    gui_user = gui_gdi = 0
    for pid, name in procs:
        if pid == 0:
            continue
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            continue
        try:
            pmc = _PMC()
            pmc.cb = ctypes.sizeof(_PMC)
            if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                tops.append((round(pmc.PrivateUsage / (1024.0 ** 2)), pid, name))
            gui_user += int(user32.GetGuiResources(h, GR_USEROBJECTS) or 0)
            gui_gdi += int(user32.GetGuiResources(h, GR_GDIOBJECTS) or 0)
        finally:
            k32.CloseHandle(h)
    tops.sort(reverse=True)
    rec["top_private_mb"] = [
        {"mb": mb, "pid": pid, "name": name} for mb, pid, name in tops[:10]]
    rec["gui_user_objects_total"] = gui_user
    rec["gui_gdi_objects_total"] = gui_gdi
