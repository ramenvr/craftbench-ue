"""Unit tests for aura_rig.mem_gate — the memory-pressure pre-gate (spec §5.3).

Fully offline: the pressure source, the clock, and the poll sleeper are ALL
injected seams, so nothing here reads real memory, shells sysctl, or sleeps for
real. A FAKE pressure source drives every blocking/admission decision.

The assertions cover the four behaviors the spec asks for:
  (1) admits IMMEDIATELY at 'normal';
  (2) BLOCKS at 'warn'/'critical' and only admits once the fake source returns
      to normal / a slot frees;
  (3) never exceeds max_slots concurrent admits;
  (4) no busy-spin — the poll interval is respected (the gate parks via the
      condition wait instead of tight-looping the pressure read).
"""

import sys
import threading
import time
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import mem_gate  # noqa: E402
from aura_rig.mem_gate import MemGate, Pressure  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes.
# ---------------------------------------------------------------------------

class FakePressure:
    """A mutable, thread-safe pressure source the test drives by hand.

    ``.level`` is read each time the gate polls. ``.reads`` counts how many
    times the gate sampled it (used to prove no busy-spin).
    """

    def __init__(self, level=Pressure.NORMAL):
        self._lock = threading.Lock()
        self._level = level
        self.reads = 0

    def __call__(self):
        with self._lock:
            self.reads += 1
            return self._level

    def set(self, level):
        with self._lock:
            self._level = level


def _instant_gate(pressure, **kw):
    """A gate whose poll-sleep is a no-op (tests fast-forward the wait)."""
    kw.setdefault("sleep", lambda _s: None)
    kw.setdefault("poll_interval", 0.001)
    return MemGate(read_pressure=pressure, **kw)


def _wait_until(pred, timeout=2.0):
    """Spin-wait (test-side, real time) until ``pred()`` or timeout. Returns pred()."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.005)
    return pred()


# ---------------------------------------------------------------------------
# Pressure mapping (the sysctl-band logic).
# ---------------------------------------------------------------------------

class TestPressureMapping(unittest.TestCase):
    def test_sysctl_codes_map_to_bands(self):
        self.assertEqual(Pressure.from_sysctl("1"), Pressure.NORMAL)
        self.assertEqual(Pressure.from_sysctl("2"), Pressure.WARN)
        self.assertEqual(Pressure.from_sysctl("4"), Pressure.CRITICAL)

    def test_unknown_value_fails_open_to_normal(self):
        # A parse miss must NOT wedge a run — soft OOM guard, fail-open.
        self.assertEqual(Pressure.from_sysctl("garbage"), Pressure.NORMAL)
        self.assertEqual(Pressure.from_sysctl(None), Pressure.NORMAL)
        self.assertEqual(Pressure.from_sysctl(""), Pressure.NORMAL)

    def test_codes_above_critical_clamp_to_critical(self):
        self.assertEqual(Pressure.from_sysctl("8"), Pressure.CRITICAL)

    def test_blocking_snapshot_only_at_warn_or_above(self):
        self.assertFalse(mem_gate.MemSnapshot(Pressure.NORMAL).blocking)
        self.assertTrue(mem_gate.MemSnapshot(Pressure.WARN).blocking)
        self.assertTrue(mem_gate.MemSnapshot(Pressure.CRITICAL).blocking)


# ---------------------------------------------------------------------------
# (1) admits immediately at normal.
# ---------------------------------------------------------------------------

class TestAdmitAtNormal(unittest.TestCase):
    def test_acquire_slot_admits_immediately_when_normal(self):
        gate = _instant_gate(FakePressure(Pressure.NORMAL), max_slots=2)
        with gate.acquire_slot():
            self.assertEqual(gate.in_use, 1)
        self.assertEqual(gate.in_use, 0)  # released on exit

    def test_admits_up_to_max_slots_without_blocking_at_normal(self):
        gate = _instant_gate(FakePressure(Pressure.NORMAL), max_slots=2)
        # No real sleeping happened to admit the first two slots → poll_count==0.
        gate._acquire()
        gate._acquire()
        self.assertEqual(gate.in_use, 2)
        self.assertEqual(gate.poll_count, 0)
        gate.release()
        gate.release()


# ---------------------------------------------------------------------------
# (2) blocks at warn/critical; admits once normal returns OR a slot frees.
# ---------------------------------------------------------------------------

class TestBlocksUnderPressure(unittest.TestCase):
    def _run_acquirer_thread(self, gate):
        """Start a thread that tries to acquire one slot; return (thread, state)."""
        state = {"admitted": False}

        def worker():
            gate._acquire()
            state["admitted"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t, state

    def test_blocks_at_warn_then_admits_when_pressure_returns_to_normal(self):
        pressure = FakePressure(Pressure.WARN)
        # poll_interval tiny + real sleep so the worker re-polls quickly.
        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.01, sleep=time.sleep)

        t, state = self._run_acquirer_thread(gate)

        # Under WARN it must NOT admit, even though a slot is free.
        self.assertFalse(_wait_until(lambda: gate.poll_count >= 2, timeout=1.0)
                         and state["admitted"],
                         "gate admitted under WARN pressure")
        self.assertFalse(state["admitted"])
        self.assertEqual(gate.in_use, 0)

        # Pressure recedes → the next poll admits.
        pressure.set(Pressure.NORMAL)
        self.assertTrue(_wait_until(lambda: state["admitted"], timeout=2.0),
                        "gate never admitted after pressure returned to normal")
        self.assertEqual(gate.in_use, 1)
        gate.release()
        t.join(timeout=1.0)

    def test_blocks_at_critical_then_admits_when_normal(self):
        pressure = FakePressure(Pressure.CRITICAL)
        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.01, sleep=time.sleep)
        t, state = self._run_acquirer_thread(gate)

        _wait_until(lambda: gate.poll_count >= 2, timeout=1.0)
        self.assertFalse(state["admitted"])

        pressure.set(Pressure.NORMAL)
        self.assertTrue(_wait_until(lambda: state["admitted"], timeout=2.0))
        gate.release()
        t.join(timeout=1.0)

    def test_third_waiter_blocks_then_admits_when_a_slot_frees(self):
        # Normal pressure, but full → the (k+1)-th launch blocks on the slot cap
        # and admits the instant a peer releases (no pressure change needed).
        pressure = FakePressure(Pressure.NORMAL)
        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.01, sleep=time.sleep)
        gate._acquire()
        gate._acquire()
        self.assertEqual(gate.in_use, 2)

        t, state = self._run_acquirer_thread(gate)
        # Full → third waiter blocks.
        _wait_until(lambda: gate.poll_count >= 1, timeout=1.0)
        self.assertFalse(state["admitted"])

        # Free a slot → the waiter wakes (via notify) and admits.
        gate.release()
        self.assertTrue(_wait_until(lambda: state["admitted"], timeout=2.0),
                        "waiter never admitted after a slot freed")
        self.assertEqual(gate.in_use, 2)  # one freed, one admitted
        gate.release()
        gate.release()
        t.join(timeout=1.0)

    def test_acquire_timeout_raises_when_pressure_never_recedes(self):
        pressure = FakePressure(Pressure.CRITICAL)
        clock = {"t": 0.0}

        def fake_now():
            return clock["t"]

        def fake_sleep(_s):
            clock["t"] += 0.5  # each poll advances the fake clock

        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.001, acquire_timeout=1.0,
                       sleep=fake_sleep, now=fake_now)
        with self.assertRaises(TimeoutError):
            gate._acquire()
        self.assertEqual(gate.in_use, 0)


# ---------------------------------------------------------------------------
# (3) never exceeds max_slots concurrent admits.
# ---------------------------------------------------------------------------

class TestNeverExceedsMaxSlots(unittest.TestCase):
    def test_concurrent_admits_capped_at_max_slots(self):
        pressure = FakePressure(Pressure.NORMAL)
        max_slots = 2
        gate = MemGate(read_pressure=pressure, max_slots=max_slots,
                       poll_interval=0.01, sleep=time.sleep)

        n_workers = 8
        inside = {"now": 0, "peak": 0}
        inside_lock = threading.Lock()
        start = threading.Event()
        done = []

        def worker():
            start.wait()
            with gate.acquire_slot():
                with inside_lock:
                    inside["now"] += 1
                    inside["peak"] = max(inside["peak"], inside["now"])
                    # Hard invariant: the gate must NEVER let more than
                    # max_slots bodies run at once.
                    self.assertLessEqual(inside["now"], max_slots)
                # Hold the slot briefly so contention is real.
                time.sleep(0.02)
                with inside_lock:
                    inside["now"] -= 1
            done.append(True)

        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(n_workers)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(len(done), n_workers, "not all workers finished")
        self.assertLessEqual(inside["peak"], max_slots)
        self.assertGreaterEqual(gate.max_observed, 1)
        self.assertLessEqual(gate.max_observed, max_slots)
        self.assertEqual(gate.in_use, 0)


# ---------------------------------------------------------------------------
# (4) no busy-spin — the poll interval is respected.
# ---------------------------------------------------------------------------

class TestNoBusySpin(unittest.TestCase):
    def test_parks_on_condition_wait_not_tight_loop(self):
        # A blocked waiter must PARK between polls, not hammer the pressure read.
        # We give it a real (short) poll_interval and let it block briefly under
        # CRITICAL: in a busy-spin the pressure read count would explode into the
        # hundreds/thousands; parked on the condition wait it stays tiny.
        pressure = FakePressure(Pressure.CRITICAL)
        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.05, sleep=lambda _s: None)

        state = {"admitted": False}

        def worker():
            gate._acquire()
            state["admitted"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # Block under CRITICAL for ~0.25 s ≈ 5 poll intervals.
        time.sleep(0.25)
        self.assertFalse(state["admitted"], "admitted while CRITICAL")
        # Parked, not spinning: at 0.05s/poll over 0.25s we expect roughly a
        # handful of reads (≤ ~20 with scheduling slack), NOT hundreds.
        reads_while_blocked = pressure.reads
        self.assertLessEqual(reads_while_blocked, 25,
                             f"busy-spin suspected: {reads_while_blocked} reads")
        self.assertGreaterEqual(gate.poll_count, 1,
                                "gate never actually polled")

        pressure.set(Pressure.NORMAL)
        self.assertTrue(_wait_until(lambda: state["admitted"], timeout=2.0))
        gate.release()
        t.join(timeout=1.0)

    def test_poll_count_tracks_each_blocked_iteration(self):
        # With an injected no-op sleep and a tiny condition timeout, each blocked
        # loop increments poll_count exactly once — proving one park per cycle.
        pressure = FakePressure(Pressure.WARN)
        gate = MemGate(read_pressure=pressure, max_slots=2,
                       poll_interval=0.005, sleep=lambda _s: None)
        state = {"admitted": False}

        def worker():
            gate._acquire()
            state["admitted"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        _wait_until(lambda: gate.poll_count >= 3, timeout=2.0)
        self.assertGreaterEqual(gate.poll_count, 3)
        self.assertFalse(state["admitted"])
        pressure.set(Pressure.NORMAL)
        self.assertTrue(_wait_until(lambda: state["admitted"], timeout=2.0))
        gate.release()
        t.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Live readers (parse helpers) — exercised with FAKE subprocess output.
# ---------------------------------------------------------------------------

class _FakeProc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class TestLiveReaderParsers(unittest.TestCase):
    def test_read_pressure_level_parses_sysctl(self):
        runner = lambda *a, **k: _FakeProc("2\n")  # noqa: E731
        self.assertEqual(mem_gate.read_pressure_level(runner), Pressure.WARN)

    def test_read_pressure_level_fails_open_on_runner_error(self):
        def boom(*a, **k):
            raise OSError("no sysctl")
        self.assertEqual(mem_gate.read_pressure_level(boom), Pressure.NORMAL)

    def test_real_reader_returns_band(self):
        # The injected runner is a *sysctl* runner, so this asserts the macOS
        # contract (real_reader shells sysctl -> band). Off-mac real_reader
        # ignores the runner and reads read_pressure_nonmac (psutil/ctypes/live)
        # by design — that path is covered by TestRealReaderDispatch /
        # TestReadPressureNonMac. Pin the platform so the sysctl parse is
        # exercised deterministically on every host (mirrors
        # TestRealReaderDispatch.test_mac_uses_sysctl_reader).
        orig = mem_gate.sys.platform
        try:
            mem_gate.sys.platform = "darwin"
            runner = lambda *a, **k: _FakeProc("4\n")  # noqa: E731
            reader = mem_gate.real_reader(runner)
            self.assertEqual(reader(), Pressure.CRITICAL)
        finally:
            mem_gate.sys.platform = orig

    def test_swap_pct_parser(self):
        text = "total = 2048.00M  used = 512.00M  free = 1536.00M"
        runner = lambda *a, **k: _FakeProc(text)  # noqa: E731
        self.assertAlmostEqual(mem_gate.read_swap_used_pct(runner), 25.0, places=1)

    def test_footprint_mb_parser_gb_and_mb(self):
        self.assertAlmostEqual(
            mem_gate._parse_footprint_mb("phys_footprint: 8.0 GB"), 8192.0, places=1)
        self.assertAlmostEqual(
            mem_gate._parse_footprint_mb("phys_footprint: 4096 MB"), 4096.0, places=1)

    def test_read_snapshot_assembles_level_and_advisory(self):
        # Snapshot assembly from the *sysctl* level + *vm.swapusage* runners is
        # the macOS contract. Off-mac read_snapshot ignores the runner and pulls
        # swap from psutil (None when psutil is absent — the documented Win32
        # ctypes limitation; that branch is covered by the non-mac tests). Pin
        # the platform so the level+swap assembly via the parse helpers is
        # exercised deterministically on every host (psutil-present or absent).
        orig = mem_gate.sys.platform
        try:
            mem_gate.sys.platform = "darwin"

            def runner(cmd, *a, **k):
                if cmd[:2] == ["sysctl", "-n"] and "pressure_level" in cmd[2]:
                    return _FakeProc("1\n")
                if "swapusage" in cmd[-1]:
                    return _FakeProc("total = 1000.00M  used = 100.00M")
                return _FakeProc("")  # top/footprint -> no parse
            snap = mem_gate.read_snapshot(runner=runner)
            self.assertEqual(snap.pressure, Pressure.NORMAL)
            self.assertAlmostEqual(snap.swap_used_pct, 10.0, places=1)
            self.assertFalse(snap.blocking)
        finally:
            mem_gate.sys.platform = orig


# ---------------------------------------------------------------------------
# Non-macOS pressure path (the Windows hand-off target + Linux).
#
# The macOS readers above shell sysctl/footprint, which don't exist off macOS.
# These exercise the NEW psutil/ctypes-or-WARN path that gives the gate a REAL
# pressure signal there instead of the old silent fail-open-to-NORMAL bug.
# ---------------------------------------------------------------------------

class TestPressureFromUsage(unittest.TestCase):
    """The RAM%+swap% -> band mapping used on non-mac hosts."""

    def test_low_usage_is_normal(self):
        self.assertEqual(Pressure.from_usage(40.0, 0.0), Pressure.NORMAL)
        self.assertEqual(Pressure.from_usage(79.9, 9.9), Pressure.NORMAL)

    def test_high_ram_or_touched_swap_is_warn(self):
        self.assertEqual(Pressure.from_usage(80.0, 0.0), Pressure.WARN)
        self.assertEqual(Pressure.from_usage(50.0, 10.0), Pressure.WARN)

    def test_very_high_ram_or_heavy_swap_is_critical(self):
        self.assertEqual(Pressure.from_usage(90.0, 0.0), Pressure.CRITICAL)
        self.assertEqual(Pressure.from_usage(60.0, 50.0), Pressure.CRITICAL)

    def test_swap_dominates_when_thrashing(self):
        # Plenty of free RAM but swap is being hammered -> already thrashing.
        self.assertEqual(Pressure.from_usage(30.0, 55.0), Pressure.CRITICAL)


class TestReadPressureNonMac(unittest.TestCase):
    """read_pressure_nonmac: a REAL band from psutil -> ctypes -> one-time WARN."""

    def setUp(self):
        # Reset the one-time-WARN latch so each test sees a clean slate.
        mem_gate._inert_warned = False

    def test_psutil_reading_maps_to_real_band(self):
        # Fake a psutil reading high enough to land in WARN; ctypes is unused.
        fake_psutil = lambda: (82.0, 0.0)  # noqa: E731
        boom_ctypes = lambda: self.fail("ctypes must not run when psutil works")  # noqa: E731
        band = mem_gate.read_pressure_nonmac(
            psutil_reader=fake_psutil, ctypes_reader=boom_ctypes)
        self.assertEqual(band, Pressure.WARN)

    def test_critical_psutil_reading(self):
        band = mem_gate.read_pressure_nonmac(
            psutil_reader=lambda: (95.0, 0.0), ctypes_reader=lambda: None)
        self.assertEqual(band, Pressure.CRITICAL)

    def test_falls_back_to_ctypes_when_no_psutil(self):
        # No psutil -> the ctypes (Windows GlobalMemoryStatusEx) shim drives it.
        band = mem_gate.read_pressure_nonmac(
            psutil_reader=lambda: None, ctypes_reader=lambda: (91.0, 0.0))
        self.assertEqual(band, Pressure.CRITICAL)

    def test_no_probe_emits_one_time_inert_warn_and_fails_open(self):
        # Neither probe available -> must WARN the operator (not silent) and,
        # only then, fail open to NORMAL so the batch still runs.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            band = mem_gate.read_pressure_nonmac(
                psutil_reader=lambda: None, ctypes_reader=lambda: None)
        self.assertEqual(band, Pressure.NORMAL)
        inert = [w for w in caught
                 if issubclass(w.category, RuntimeWarning)
                 and "INERT" in str(w.message)]
        self.assertEqual(len(inert), 1, "expected exactly one inert WARN")

    def test_inert_warn_fires_only_once_per_process(self):
        # A polling gate calls this every tick; the operator signal must not spam.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(5):
                mem_gate.read_pressure_nonmac(
                    psutil_reader=lambda: None, ctypes_reader=lambda: None)
        inert = [w for w in caught if "INERT" in str(w.message)]
        self.assertEqual(len(inert), 1, "inert WARN must be emitted at most once")


class TestRealReaderDispatch(unittest.TestCase):
    """real_reader picks the mac sysctl path vs the non-mac psutil/ctypes path."""

    def test_mac_uses_sysctl_reader(self):
        # On darwin the live reader still shells sysctl (byte-identical path).
        orig = mem_gate.sys.platform
        try:
            mem_gate.sys.platform = "darwin"
            runner = lambda *a, **k: _FakeProc("2\n")  # noqa: E731
            reader = mem_gate.real_reader(runner)
            self.assertEqual(reader(), Pressure.WARN)
        finally:
            mem_gate.sys.platform = orig

    def test_nonmac_uses_nonmac_reader(self):
        orig = mem_gate.sys.platform
        try:
            mem_gate.sys.platform = "win32"
            reader = mem_gate.real_reader()
            # It is the non-mac function itself (psutil/ctypes/WARN path), NOT
            # the sysctl lambda — so it never shells the absent macOS sysctl.
            self.assertIs(reader, mem_gate.read_pressure_nonmac)
        finally:
            mem_gate.sys.platform = orig


# ---------------------------------------------------------------------------
# Constructor guards.
# ---------------------------------------------------------------------------

class TestConstructorGuards(unittest.TestCase):
    def test_rejects_zero_max_slots(self):
        with self.assertRaises(ValueError):
            MemGate(read_pressure=FakePressure(), max_slots=0)

    def test_rejects_nonpositive_poll_interval(self):
        with self.assertRaises(ValueError):
            MemGate(read_pressure=FakePressure(), poll_interval=0)


if __name__ == "__main__":
    unittest.main()
