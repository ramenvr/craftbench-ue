"""mem_gate — the memory-pressure pre-gate for ``aura-product-eval`` (spec §5.3).

WHY this exists: the Pool-B grader runs each verify in its OWN cold headless UE
process (≈ ~8 GB editor + UBT compile RAM). On the 26 GB dev Mac, launching too
many concurrent cold verifies thrashes swap and OOMs the box — the same failure
mode ``stack/preflight_clean.sh`` was written to clean up after. So before the
scheduler launches the (k+1)-th concurrent verify it asks THIS gate for a slot;
the gate ADMITS while memory pressure is normal and BLOCKS (waits for a slot to
free / pressure to recede) while pressure is WARN/CRITICAL → concurrent cold
verifies stay ~2-wide on a 26 GB box without a hard-coded width.

It reads pressure the SAME way the rest of the rig does (so the two agree):

  * ``sysctl -n kern.memorystatus_vm_pressure_level`` — 1=normal, 2=WARN,
    4=CRITICAL (the exact mapping ``preflight_clean.sh`` §4 and ``preflight``
    use). Unknown → treated as normal (fail-open: never wedge a run on a parse
    miss; the OOM guard is a SOFT cap, the hard isolation is per-process).
  * a resident-footprint estimate via ``footprint`` / ``top -l 1 -o mem`` —
    NEVER ``ps rss`` (it LIES — caps at physical RAM; the rig's standing note).
    The footprint is advisory detail; the pressure LEVEL is the gate signal.

On NON-macOS hosts (the Windows hand-off target, and Linux) the macOS pressure
sysctl does not exist, so the gate reads a REAL signal a different way (see
:func:`read_pressure_nonmac`): ``psutil`` virtual-memory + swap percentages
mapped onto the same WARN/CRITICAL bands; if ``psutil`` is absent it falls back
to the Windows ``GlobalMemoryStatusEx`` ctypes call; if neither is available it
emits a ONE-TIME WARN that the soft OOM guard is INERT on this platform and only
the hard ``max_slots`` cap limits concurrency. It never SILENTLY fails open with
no operator signal — that silent no-op was the original Windows bug.

Every external touch (the sysctl read, the footprint read, the clock, the
blocking sleep) is an INJECTED seam, so the gate logic is unit-testable with a
FAKE pressure source — no live editor, no real memory, no real sleeping. The
real-seam factory (:func:`real_reader`) dispatches on platform and wires the
live ``sysctl``/``footprint`` (macOS) or ``psutil``/ctypes (non-mac) probes for
production. Mirrors the ``preflight``/``preflight_product`` seam-injection idiom
(and the lazy-``psutil``-with-fallback style in :mod:`aura_rig.stack`).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Iterator, Optional


# ---------------------------------------------------------------------------
# Pressure model.
# ---------------------------------------------------------------------------

class Pressure(IntEnum):
    """macOS ``kern.memorystatus_vm_pressure_level`` values (the rig's mapping).

    The int values are the literal sysctl codes (1/2/4) so a reader can return
    the raw sysctl number and have it land in the right band.
    """

    NORMAL = 1
    WARN = 2
    CRITICAL = 4

    @classmethod
    def from_sysctl(cls, raw: object) -> "Pressure":
        """Map a raw ``kern.memorystatus_vm_pressure_level`` value to a band.

        Unknown / unparseable values fail OPEN to NORMAL: the gate is a SOFT OOM
        guard, and the hard isolation is each verify's own process — we never
        want a parse miss to wedge an entire eval batch.
        """
        try:
            n = int(str(raw).strip())
        except (TypeError, ValueError):
            return cls.NORMAL
        if n >= cls.CRITICAL:
            return cls.CRITICAL
        if n == cls.WARN:
            return cls.WARN
        return cls.NORMAL

    @classmethod
    def from_usage(cls, mem_pct: float, swap_pct: float) -> "Pressure":
        """Map RAM-used % + swap-used % onto the WARN/CRITICAL bands (non-mac).

        macOS hands us a kernel pressure LEVEL directly; Windows/Linux don't, so
        we synthesize the band from the two percentages ``psutil`` (or a ctypes
        shim) gives us. The thresholds mirror the rig's standing note — once swap
        is being touched the 26 GB-class box is already thrashing — so swap is
        weighted at least as hard as raw RAM:

          * CRITICAL — RAM >= 90% OR swap >= 50% (the OOM-imminent / thrashing band)
          * WARN     — RAM >= 80% OR swap >= 10% (back off before launching ~8 GB more)
          * NORMAL   — otherwise.
        """
        if mem_pct >= 90.0 or swap_pct >= 50.0:
            return cls.CRITICAL
        if mem_pct >= 80.0 or swap_pct >= 10.0:
            return cls.WARN
        return cls.NORMAL


# A reader returns the current pressure band. Injected so tests can fake it.
PressureReader = Callable[[], Pressure]


@dataclass(frozen=True)
class MemSnapshot:
    """One read of the box's memory health (the gate decision + advisory detail)."""

    pressure: Pressure
    footprint_mb: Optional[float] = None  # advisory; None when unavailable
    swap_used_pct: Optional[float] = None  # advisory; None when unavailable

    @property
    def blocking(self) -> bool:
        """True iff this snapshot says a NEW heavy verify should wait."""
        return self.pressure >= Pressure.WARN


# ---------------------------------------------------------------------------
# Live readers (the real seams; subprocess shells, kept thin).
# ---------------------------------------------------------------------------

def read_pressure_level(
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Pressure:
    """Read ``kern.memorystatus_vm_pressure_level`` via sysctl → a band.

    ``runner`` is an injectable ``subprocess.run``-alike (so even this thin live
    reader is testable). Any failure → NORMAL (fail-open, see Pressure.from_sysctl).
    """
    try:
        r = runner(
            ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            capture_output=True, text=True, timeout=6,
        )
    except Exception:  # noqa: BLE001 — a probe never raises into the gate
        return Pressure.NORMAL
    return Pressure.from_sysctl(getattr(r, "stdout", "") or "")


def read_footprint_mb(
    pid: Optional[int] = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Optional[float]:
    """Best-effort resident footprint in MB via ``footprint``/``top`` (NOT ps rss).

    ``ps rss`` LIES on macOS — it caps at physical RAM, so a swapped-out 44 GB
    editor reads as ~26 GB. The rig's standing rule is ``footprint <pid>`` or
    ``top -l 1 -o mem``; we use those. Advisory only — None when unavailable.
    """
    # Per-process: `footprint <pid>` reports the true phys_footprint.
    if pid is not None:
        try:
            r = runner(["footprint", str(pid)], capture_output=True,
                       text=True, timeout=10)
            mb = _parse_footprint_mb(getattr(r, "stdout", "") or "")
            if mb is not None:
                return mb
        except Exception:  # noqa: BLE001
            pass
    # Whole-box fallback: top's wired+compressed line via -o mem (no ps rss).
    try:
        r = runner(["top", "-l", "1", "-o", "mem", "-n", "1", "-stats", "mem"],
                   capture_output=True, text=True, timeout=10)
        return _parse_top_mem_mb(getattr(r, "stdout", "") or "")
    except Exception:  # noqa: BLE001
        return None


def read_swap_used_pct(
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Optional[float]:
    """Swap used % via ``sysctl vm.swapusage`` (advisory; None on failure)."""
    try:
        r = runner(["sysctl", "-n", "vm.swapusage"], capture_output=True,
                   text=True, timeout=6)
    except Exception:  # noqa: BLE001
        return None
    return _parse_swap_pct(getattr(r, "stdout", "") or "")


def _parse_footprint_mb(text: str) -> Optional[float]:
    """Pull a MB figure out of ``footprint`` output (handles MB / GB units)."""
    import re
    # e.g. "phys_footprint: 8123 MB" or "... 8.1 GB"
    m = re.search(r"phys_footprint:?\s*([0-9.]+)\s*(GB|MB)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"([0-9.]+)\s*(GB|MB)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    return val * 1024.0 if m.group(2).upper() == "GB" else val


def _parse_top_mem_mb(text: str) -> Optional[float]:
    """Pull the first MEM column figure (top -o mem) → MB (handles M/G/K)."""
    import re
    for ln in text.splitlines():
        m = re.search(r"^\s*\d+\s+\S+.*?\b([0-9.]+)([KMG])\b", ln)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            return {"K": val / 1024.0, "M": val, "G": val * 1024.0}[unit]
    return None


def _parse_swap_pct(text: str) -> Optional[float]:
    """``vm.swapusage`` 'used = X.YM' / 'total = X.YM' → used %, None if total 0."""
    import re
    used = re.search(r"used\s*=\s*([0-9.]+)M", text)
    total = re.search(r"total\s*=\s*([0-9.]+)M", text)
    if not used or not total:
        return None
    t = float(total.group(1))
    if t <= 0:
        return None
    return 100.0 * float(used.group(1)) / t


# ---------------------------------------------------------------------------
# Non-macOS live readers (Windows hand-off target + Linux).
#
# The macOS readers above shell ``sysctl``/``footprint``/``vm.swapusage`` — none
# of which exist off macOS, where every probe raised FileNotFoundError and was
# swallowed into a SILENT fail-open to NORMAL (the original bug: the OOM guard
# was a permanent no-op on the hand-off target). These give the gate a REAL
# pressure signal there instead.
# ---------------------------------------------------------------------------

# One-time-WARN latch: emit the "soft OOM guard is INERT" warning at most once
# per process so a polling gate doesn't spam the operator's log every tick.
_inert_warned = False


def _warn_inert_once() -> None:
    """Emit (at most once) the operator signal that the soft OOM guard is INERT.

    Reached only when NO real probe is available on a non-mac host (no psutil,
    and ctypes GlobalMemoryStatusEx unavailable/failed). We must NOT silently
    fail open with no signal — that was the original Windows bug. The gate still
    functions, but only the ``--verify-concurrency`` / ``max_slots`` hard cap
    limits concurrency; the adaptive pressure back-off is off.
    """
    global _inert_warned
    if _inert_warned:
        return
    _inert_warned = True
    warnings.warn(
        "mem_gate: soft OOM pressure guard is INERT on this platform "
        f"(sys.platform={sys.platform!r}): no psutil and no ctypes "
        "GlobalMemoryStatusEx, so memory-pressure back-off is disabled. "
        "Concurrency is bounded ONLY by --verify-concurrency / max_slots. "
        "Install psutil to restore adaptive OOM back-off.",
        RuntimeWarning,
        stacklevel=2,
    )


def _read_usage_psutil() -> Optional[tuple]:
    """``(ram_used_pct, swap_used_pct)`` via psutil, or None if psutil absent.

    Lazy import + broad swallow, exactly like :mod:`aura_rig.stack` — psutil is
    an optional dependency the rig already leans on when present."""
    try:
        import psutil  # type: ignore
    except Exception:  # noqa: BLE001 — optional dep; absence is not an error here
        return None
    try:
        mem_pct = float(psutil.virtual_memory().percent)
        try:
            swap_pct = float(psutil.swap_memory().percent)
        except Exception:  # noqa: BLE001 — some hosts expose no swap device
            swap_pct = 0.0
        return mem_pct, swap_pct
    except Exception:  # noqa: BLE001 — a probe never raises into the gate
        return None


def _read_usage_ctypes_windows() -> Optional[tuple]:
    """``(ram_used_pct, 0.0)`` via Win32 ``GlobalMemoryStatusEx``, or None.

    The pure-stdlib Windows fallback when psutil is not installed. ``dwMemoryLoad``
    is the kernel's own 0-100 RAM-used percent. Win32 has no cheap swap-used %, so
    swap is reported 0.0 (the RAM band still drives the back-off). None on any
    non-Windows host or call failure."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
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
        return float(stat.dwMemoryLoad), 0.0
    except Exception:  # noqa: BLE001 — a probe never raises into the gate
        return None


def read_pressure_nonmac(
    psutil_reader: Callable[[], Optional[tuple]] = _read_usage_psutil,
    ctypes_reader: Callable[[], Optional[tuple]] = _read_usage_ctypes_windows,
) -> Pressure:
    """Read a REAL pressure band on non-macOS hosts (Windows hand-off + Linux).

    Probe order (first that yields a ``(ram_pct, swap_pct)`` reading wins):
      1. ``psutil`` virtual_memory + swap percentages (cross-platform);
      2. Windows ``GlobalMemoryStatusEx`` ctypes shim (no psutil needed);
      3. neither available → emit the ONE-TIME inert WARN and fail open to NORMAL.

    Readers are injected so tests can drive the band / the inert-WARN branch
    without a real psutil or a real Win32 call."""
    for reader in (psutil_reader, ctypes_reader):
        usage = reader()
        if usage is not None:
            mem_pct, swap_pct = usage
            return Pressure.from_usage(mem_pct, swap_pct)
    # No real probe on this host: signal the operator (once) — never silent.
    _warn_inert_once()
    return Pressure.NORMAL


def real_reader(
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> PressureReader:
    """A live :data:`PressureReader`, platform-dispatched.

    On macOS it returns the band from the real sysctl/footprint shells (byte-for-
    byte the original behavior). On every other host — the Windows hand-off target
    and Linux, where the macOS sysctl does not exist — it returns the band from
    :func:`read_pressure_nonmac` (psutil → ctypes → one-time inert WARN) so the
    soft OOM guard is a REAL signal there instead of a silent no-op.

    Either way it returns just the band (the gate's decision signal). Footprint/
    swap detail stays available via :func:`read_snapshot` for logging, same as
    ``preflight_clean.sh`` §4, which gates on the level + swap %.
    """
    if sys.platform == "darwin":
        return lambda: read_pressure_level(runner)
    return read_pressure_nonmac


def read_snapshot(
    *, pid: Optional[int] = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> MemSnapshot:
    """A full advisory snapshot (level + footprint + swap %) for logging.

    macOS path is unchanged (sysctl level + footprint + vm.swapusage). On non-mac
    hosts the sysctl shells don't exist, so the band comes from
    :func:`read_pressure_nonmac` and the advisory swap % from psutil when present
    (footprint stays None — the macOS-only ``footprint`` tool has no portable peer)."""
    if sys.platform != "darwin":
        usage = _read_usage_psutil()
        swap_pct = usage[1] if usage is not None else None
        return MemSnapshot(
            pressure=read_pressure_nonmac(),
            footprint_mb=None,
            swap_used_pct=swap_pct,
        )
    return MemSnapshot(
        pressure=read_pressure_level(runner),
        footprint_mb=read_footprint_mb(pid=pid, runner=runner),
        swap_used_pct=read_swap_used_pct(runner),
    )


# ---------------------------------------------------------------------------
# The gate.
# ---------------------------------------------------------------------------

class MemGate:
    """A memory-pressure-aware slot gate for concurrent heavy verifies.

    Two independent admission conditions, BOTH must hold to admit:

      1. **slots** — at most ``max_slots`` admissions are live at once (the hard
         concurrency cap; default 2 ≈ "~2-wide on 26 GB").
      2. **pressure** — at admission time, ``read_pressure()`` must be BELOW
         ``block_at`` (default WARN). If memory pressure is WARN/CRITICAL the
         gate BLOCKS the (k+1)-th launch and re-polls every ``poll_interval``
         seconds (via the injected ``sleep``) until pressure recedes OR a slot
         frees — it NEVER busy-spins.

    The first ``max_slots`` admissions when pressure is normal pass through
    immediately. Beyond that, or under pressure, a waiter blocks on a condition
    variable woken by ``release()`` and by the poll tick.

    Thread-based (``threading.Condition``) rather than asyncio because the
    Pool-B grader spawns each verify in its own thread/cold process; a sync
    context manager drops straight into that ``async with pool_b`` site via
    ``run_in_executor`` or a thread, with no event-loop coupling.

    Every side effect is injected:
      * ``read_pressure`` — a :data:`PressureReader` (FAKE in tests).
      * ``sleep``         — the poll-wait sleeper (a no-op / fast-forward in tests).
      * ``now``           — monotonic clock for the wait-timeout (injected for tests).
    """

    def __init__(
        self,
        *,
        max_slots: int = 2,
        read_pressure: Optional[PressureReader] = None,
        block_at: Pressure = Pressure.WARN,
        poll_interval: float = 5.0,
        acquire_timeout: Optional[float] = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_slots < 1:
            raise ValueError("max_slots must be >= 1")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be > 0")
        self.max_slots = max_slots
        self.block_at = block_at
        self.poll_interval = poll_interval
        self.acquire_timeout = acquire_timeout
        self._read_pressure = read_pressure or real_reader()
        self._sleep = sleep
        self._now = now

        self._cv = threading.Condition()
        self._in_use = 0
        # Bookkeeping the tests assert on: how many poll-sleeps we have done and
        # the high-water mark of concurrent admissions.
        self.poll_count = 0
        self.max_observed = 0

    # -- introspection (test + log) -----------------------------------------

    @property
    def in_use(self) -> int:
        with self._cv:
            return self._in_use

    def _can_admit_locked(self) -> bool:
        """Admission predicate (caller holds the lock).

        Admit iff a slot is free AND pressure is below the block threshold. A
        slot being free is checked under the lock; pressure is read OUTSIDE the
        lock by the caller and passed in — keeping the (potentially slow) sysctl
        shell off the critical section.
        """
        return self._in_use < self.max_slots

    # -- the blocking acquire/release ---------------------------------------

    def _acquire(self) -> None:
        """Block until a slot is free AND pressure is acceptable, then take it.

        Re-polls at ``poll_interval`` (via the injected ``sleep``) so a launch
        held off by WARN/CRITICAL wakes once pressure recedes even if no peer
        releases. Never busy-spins: between polls it sleeps the full interval.
        """
        deadline = (self._now() + self.acquire_timeout
                    if self.acquire_timeout is not None else None)
        while True:
            # Read pressure OUTSIDE the lock (sysctl shell may be slow).
            pressure = self._read_pressure()
            with self._cv:
                slot_free = self._can_admit_locked()
                pressure_ok = pressure < self.block_at
                if slot_free and pressure_ok:
                    self._in_use += 1
                    if self._in_use > self.max_observed:
                        self.max_observed = self._in_use
                    return
            # Cannot admit yet. Honor an optional overall timeout.
            if deadline is not None and self._now() >= deadline:
                raise TimeoutError(
                    f"mem_gate: no slot after {self.acquire_timeout}s "
                    f"(in_use={self._in_use}/{self.max_slots}, "
                    f"pressure={pressure.name})"
                )
            # Wait for either a release (condition notify) OR the poll interval,
            # whichever comes first — so we re-check pressure on a cadence AND
            # react promptly to a freed slot. This is the no-busy-spin point.
            self.poll_count += 1
            self._wait_for_change()

    def _wait_for_change(self) -> None:
        """Sleep up to one poll interval, woken early by a peer ``release()``.

        Implemented as a condition wait with a timeout; the injected ``sleep``
        is used when the condition wait is a no-op stand-in (tests fast-forward
        the clock with it). In production, ``Condition.wait(timeout)`` both
        parks (no CPU) and wakes early on notify.
        """
        with self._cv:
            # `wait` releases the lock while parked and reacquires on wake; a
            # peer `release()` calls `notify_all()` to wake us before the
            # timeout. Returns False on timeout (the poll tick).
            woke = self._cv.wait(timeout=self.poll_interval)
        if not woke:
            # Timed out → a real poll tick. Give the injected sleeper a chance
            # to advance a fake clock / record the cadence (no-op in prod since
            # the wait already consumed the interval).
            self._sleep(0)

    def release(self) -> None:
        """Return a slot and wake any waiters (peers blocked in ``_acquire``)."""
        with self._cv:
            if self._in_use > 0:
                self._in_use -= 1
            self._cv.notify_all()

    @contextmanager
    def acquire_slot(self) -> Iterator["MemGate"]:
        """Context manager: block for a slot, run the body, release on exit.

        Usage in the Pool-B scheduler::

            with gate.acquire_slot():
                run_one_cold_verify(submission)   # ≈ 8 GB editor

        Admits the first ``max_slots`` callers while pressure is normal; blocks
        the next launch when full OR when pressure is WARN/CRITICAL; admits once
        a slot frees AND pressure is acceptable.
        """
        self._acquire()
        try:
            yield self
        finally:
            self.release()


# ---------------------------------------------------------------------------
# CLI — a one-shot health line (mirrors preflight*'s __main__ shape).
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:  # pragma: no cover - live wiring
    """Print a one-shot memory snapshot; exit 0 iff pressure is normal."""
    import argparse
    p = argparse.ArgumentParser(
        description="memory-pressure snapshot for the aura-product-eval gate")
    p.add_argument("--pid", type=int, default=None,
                   help="optional pid to footprint (default: whole-box top)")
    args = p.parse_args(argv)
    snap = read_snapshot(pid=args.pid)
    fp = f"{snap.footprint_mb:.0f} MB" if snap.footprint_mb is not None else "?"
    sw = f"{snap.swap_used_pct:.0f}%" if snap.swap_used_pct is not None else "?"
    print(f"MEM-GATE: pressure={snap.pressure.name} footprint={fp} swap={sw} "
          f"blocking={snap.blocking}")
    return 0 if snap.pressure == Pressure.NORMAL else 1


if __name__ == "__main__":  # pragma: no cover - live wiring
    raise SystemExit(main())
