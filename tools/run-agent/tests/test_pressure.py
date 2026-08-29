"""Unit tests for aura_rig.pressure — the IN-DRIVE commit-pressure guard.

Fully offline, in the test_stack_guard / test_stack_reap style: EVERY reading is
injected (``read`` / ``offenders`` / ``clock`` / ``on_critical`` / ``teardown``),
so nothing here samples the real machine's commit charge, enumerates real
processes, kills anything, or touches a live stack. The band logic is exercised
through ``DriveMonitor.poll()`` directly — deterministic, no threads — and the
one threaded test drives a fake clock through a fake drive.

The properties under test are the ones the guard exists for:
  * THE HARD INVARIANT — the sampler never spawns a process, on any band, in
    any fallback (``TestNoSubprocessInvariant``). The first cut fell back to
    ``powershell.exe`` when psutil was missing, which is the ACTIVE path on this
    box: the guard would have allocated ~100 MB of commit inside the WARN and
    CRITICAL bands, i.e. during the crisis it exists to prevent;
  * three bands off ONE floor (envgate's), with hysteresis so a reading hovering
    on a threshold logs once, not once per sample;
  * the CRITICAL abort fires exactly once, records COMMIT-EXHAUSTED and stays
    NON-GRADED (the "tears the stack down" half of that sentence was asserted
    against run_graded's call site, which left with the aura-product lane on
    2026-08-28 — see the note above TestTerminateTreeInProcess);
  * pressure.jsonl carries t / free_gb / band / top offender;
  * an EDITOR-GONE whose last sample sat under the WARN line gets a probable-
    cause sentence — and one that ended healthy does NOT;
  * the leak-triggered recycle is a pure decision over process footprints;
  * a healthy drive still records min-free and never moves its verdict.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import pressure  # noqa: E402


def _monitor(readings, *, run_dir=None, floor=10.0, warn_mult=2.0,
             margin=0.5, offenders=None, on_critical=None, logs=None):
    """A monitor over a fixed list of readings and a fake monotonic clock."""
    it = iter(readings)
    ticks = iter(range(1000, 100000, 5))

    def _read():
        try:
            return next(it)
        except StopIteration:
            return None

    return pressure.DriveMonitor(
        run_dir, floor=floor, warn_mult=warn_mult, margin_gb=margin,
        interval_s=0.01, read=_read,
        offenders=offenders or (lambda: None),
        on_critical=on_critical, clock=lambda: float(next(ticks)),
        offender_min_gap_s=0.0,
        log=(logs.append if logs is not None else (lambda s: None)))


def _drain(mon, n):
    return [mon.poll() for _ in range(n)]


# --------------------------------------------------------------------------- #
# THE HARD INVARIANT: no subprocess on the pressure path, ever.                #
# --------------------------------------------------------------------------- #

class TestNoSubprocessInvariant(unittest.TestCase):
    """A guard that allocates during the memory crisis it measures is worse
    than no guard.

    Spawning powershell costs ~50-100 MB of commit and a few hundred ms, and the
    original fallback did it in the WARN/CRITICAL bands — on a box where psutil
    is ABSENT, so it was the live path, not a fallback. These tests make the
    rule enforceable rather than aspirational."""

    def _forbid_spawning(self):
        """Replace every spawn primitive with a landmine, in BOTH the stdlib
        module and the modules under test (so a `from subprocess import run`
        style alias could not sneak past)."""
        import subprocess

        def boom(*a, **k):
            raise AssertionError(
                "pressure path spawned a subprocess — see THE HARD INVARIANT")

        patches = [mock.patch.object(subprocess, name, boom)
                   for name in ("run", "Popen", "call", "check_output",
                                "check_call")]
        if hasattr(os, "system"):
            patches.append(mock.patch.object(os, "system", boom))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_the_module_cannot_spawn_at_all(self):
        """Structural, not behavioural: `subprocess` is not imported, so no
        future edit can reintroduce a spawn without also reintroducing the
        import — which is the thing a reviewer will actually notice."""
        self.assertFalse(hasattr(pressure, "subprocess"),
                         "aura_rig.pressure must not import subprocess")
        src = (Path(pressure.__file__)).read_text(encoding="utf-8")
        code = "\n".join(ln for ln in src.splitlines()
                         if not ln.lstrip().startswith("#"))
        self.assertNotIn("import subprocess", code)

    def test_a_full_warn_and_critical_cycle_completes_without_spawning(self):
        """The behavioural half, with the REAL default offender reader (no
        injected `offenders`), which is where the powershell fallback lived."""
        self._forbid_spawning()
        fired = []
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run"
            readings = iter([40.0, 18.0, 17.0, 9.0, 8.0, 25.0])
            mon = pressure.DriveMonitor(
                rd, floor=10.0, warn_mult=2.0, margin_gb=0.5, interval_s=0.01,
                read=lambda: next(readings, None),
                on_critical=lambda s: fired.append(s),
                offender_min_gap_s=0.0, log=lambda s: None)
            samples = [mon.poll() for _ in range(6)]
        self.assertEqual(len(samples), 6)
        rep = mon.report()
        # 40 OK | 18,17 WARN | 9,8 CRITICAL | 25 recovered to OK (clears the
        # 20 GB WARN line by more than the 0.5 GB re-arm margin).
        self.assertEqual(rep["bands"], {pressure.BAND_OK: 2,
                                        pressure.BAND_WARN: 2,
                                        pressure.BAND_CRITICAL: 2})
        self.assertTrue(rep["aborted"])
        self.assertEqual(len(fired), 1)

    def test_the_real_probes_never_spawn(self):
        """Each in-process probe called directly, with spawning forbidden. They
        may return None (non-Windows, or a denied handle) — what they may never
        do is shell out."""
        self._forbid_spawning()
        self.assertIsInstance(pressure.win_listening_pids([3000, 3002]), dict)
        pressure.private_mb(os.getpid())          # our own pid: always openable
        pressure.read_stack_offender()
        pressure.read_stack_footprints()
        pressure.measure_stack_footprint_mb()
        pressure.drive_ports()

    def test_the_tcp_table_parser_finds_a_real_listener(self):
        """The one piece of new code that can be SUBTLY wrong: the row offsets
        and the network-byte-order port. Binds a listener in-process on an
        ephemeral port and asserts the table maps it back to THIS pid — so a
        wrong offset or a missing ntohs fails loudly instead of silently
        degrading every offender label to None.

        No spawn, no fixed port, nothing outside this process."""
        if os.name != "nt":
            self.skipTest("GetExtendedTcpTable is Windows-only")
        import socket
        srv = socket.socket()
        self.addCleanup(srv.close)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        self._forbid_spawning()
        table = pressure.win_listening_pids([port])
        self.assertIn(port, table, "the listener was not found in the TCP table")
        self.assertIn(os.getpid(), table[port])

    def test_our_own_private_bytes_are_readable_in_process(self):
        """Proves the ctypes path actually works here, not merely that it does
        not spawn — otherwise 'never spawns' could be satisfied by 'never
        measures'. Skipped off Windows, where commit charge is not the ceiling
        and the whole layer reports None by design."""
        if os.name != "nt":
            self.skipTest("Windows-only commit/private-bytes probes")
        mb = pressure.private_mb(os.getpid())
        self.assertIsNotNone(mb, "GetProcessMemoryInfo should read our own pid")
        self.assertGreater(mb, 0.0)

    def test_the_offender_is_omitted_rather_than_paid_for(self):
        """When nothing can be measured the sample still lands — free_gb is the
        number that matters, and a missing label must never cost an allocation.
        """
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run"
            mon = _monitor([18.0], run_dir=rd, offenders=lambda: None)
            _drain(mon, 1)
            row = json.loads((rd / pressure.PRESSURE_FILE)
                             .read_text(encoding="utf-8").strip())
        self.assertEqual(row["band"], pressure.BAND_WARN)
        self.assertEqual(row["free_gb"], 18.0)
        self.assertNotIn("top_offender", row)


# --------------------------------------------------------------------------- #
# Thresholds: ONE source of truth.                                             #
# --------------------------------------------------------------------------- #

class TestThresholds(unittest.TestCase):
    def test_floor_is_envgates_floor(self):
        """No second threshold may exist — the pre-spend gate, the pre-rep hook
        and the in-drive sampler must agree on 'how little is too little'."""
        from aura_rig import envgate
        with mock.patch.dict(os.environ, {"CB_COMMIT_FLOOR_GB": "4"}):
            self.assertEqual(pressure.floor_gb(), 4.0)
            self.assertEqual(pressure.floor_gb(), envgate.commit_floor_gb())

    def test_warn_line_is_a_multiple_of_the_floor(self):
        self.assertEqual(pressure.warn_gb(10.0, warn_mult=2.0), 20.0)
        with mock.patch.dict(os.environ, {"CB_PRESSURE_WARN_MULT": "3"}):
            self.assertEqual(pressure.warn_multiple(), 3.0)
            self.assertEqual(pressure.warn_gb(10.0), 30.0)

    def test_a_typo_never_disables_a_guard(self):
        for bad in ("", "banana", "-5", "0"):
            with mock.patch.dict(os.environ, {"CB_PRESSURE_WARN_MULT": bad}):
                self.assertEqual(pressure.warn_multiple(),
                                 pressure.DEFAULT_WARN_MULTIPLE)
            with mock.patch.dict(os.environ, {"CB_PRESSURE_SAMPLE_S": bad}):
                self.assertEqual(pressure.sample_interval_s(),
                                 pressure.DEFAULT_SAMPLE_INTERVAL_S)

    def test_kill_switch_and_the_shared_skip_switch(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CB_PRESSURE_GUARD", None)
            os.environ.pop("CB_NO_PREFLIGHT", None)
            self.assertTrue(pressure.guard_enabled())
        with mock.patch.dict(os.environ, {"CB_PRESSURE_GUARD": "0"}):
            self.assertFalse(pressure.guard_enabled())
        # Rides --no-preflight exactly like the envgate and the pre-rep hook.
        with mock.patch.dict(os.environ, {"CB_NO_PREFLIGHT": "1"}):
            self.assertFalse(pressure.guard_enabled())

    def test_stack_recycle_threshold_is_env_overridable_and_zero_disables(self):
        self.assertEqual(pressure.stack_recycle_mb({}),
                         pressure.DEFAULT_STACK_RECYCLE_MB)
        self.assertEqual(pressure.stack_recycle_mb({"CB_STACK_RECYCLE_MB": "9000"}),
                         9000.0)
        self.assertEqual(pressure.stack_recycle_mb({"CB_STACK_RECYCLE_MB": "0"}), 0.0)


# --------------------------------------------------------------------------- #
# Bands (pure).                                                                #
# --------------------------------------------------------------------------- #

class TestClassify(unittest.TestCase):
    def test_three_bands(self):
        self.assertEqual(pressure.classify(40.0, 10.0, warn_mult=2.0),
                         pressure.BAND_OK)
        self.assertEqual(pressure.classify(19.9, 10.0, warn_mult=2.0),
                         pressure.BAND_WARN)
        self.assertEqual(pressure.classify(9.9, 10.0, warn_mult=2.0),
                         pressure.BAND_CRITICAL)

    def test_boundaries_are_inclusive_upward(self):
        """Exactly ON the floor is not under it; exactly on the WARN line is OK."""
        self.assertEqual(pressure.classify(10.0, 10.0, warn_mult=2.0),
                         pressure.BAND_WARN)
        self.assertEqual(pressure.classify(20.0, 10.0, warn_mult=2.0),
                         pressure.BAND_OK)

    def test_an_absent_reading_is_not_a_band(self):
        """None is deliberately NOT 'OK' — unmeasurable and healthy are
        different facts, and an absent measurement is never a verdict."""
        self.assertIsNone(pressure.classify(None, 10.0))


class TestHysteresis(unittest.TestCase):
    def _h(self, prev, raw, free):
        return pressure.apply_hysteresis(prev, raw, free, 10.0, warn_mult=2.0,
                                         margin_gb=0.5)

    def test_escalation_is_immediate(self):
        self.assertEqual(self._h(pressure.BAND_OK, pressure.BAND_CRITICAL, 9.0),
                         pressure.BAND_CRITICAL)
        self.assertEqual(self._h(pressure.BAND_OK, pressure.BAND_WARN, 19.0),
                         pressure.BAND_WARN)

    def test_recovery_must_clear_the_boundary_by_the_margin(self):
        self.assertEqual(self._h(pressure.BAND_WARN, pressure.BAND_OK, 20.2),
                         pressure.BAND_WARN, "still inside the re-arm margin")
        self.assertEqual(self._h(pressure.BAND_WARN, pressure.BAND_OK, 20.6),
                         pressure.BAND_OK)

    def test_critical_recovers_through_warn(self):
        self.assertEqual(self._h(pressure.BAND_CRITICAL, pressure.BAND_WARN, 10.2),
                         pressure.BAND_CRITICAL, "not yet clear of the floor")
        self.assertEqual(self._h(pressure.BAND_CRITICAL, pressure.BAND_WARN, 10.6),
                         pressure.BAND_WARN)
        self.assertEqual(self._h(pressure.BAND_CRITICAL, pressure.BAND_OK, 15.0),
                         pressure.BAND_WARN, "clear of the floor, not of WARN")

    def test_an_absent_reading_holds_the_previous_band(self):
        self.assertEqual(self._h(pressure.BAND_CRITICAL, None, None),
                         pressure.BAND_CRITICAL)


# --------------------------------------------------------------------------- #
# The monitor: transitions, log discipline, evidence.                          #
# --------------------------------------------------------------------------- #

class TestMonitorBands(unittest.TestCase):
    def test_a_healthy_drive_logs_nothing_and_records_nothing(self):
        logs = []
        with tempfile.TemporaryDirectory() as td:
            mon = _monitor([40.0, 38.0, 41.0], run_dir=Path(td), logs=logs)
            _drain(mon, 3)
            rep = mon.report()
            self.assertEqual(logs, [], "OK band is silent")
            self.assertFalse((Path(td) / pressure.PRESSURE_FILE).exists())
            self.assertEqual(rep["worst_band"], pressure.BAND_OK)
            self.assertEqual(rep["bands"][pressure.BAND_OK], 3)

    def test_a_healthy_drive_still_records_min_free_and_at_exit(self):
        """Post-hoc evidence, ALWAYS. Its absence is exactly why two nights of
        mid-drive editor deaths took two days to attribute."""
        mon = _monitor([40.0, 26.0, 33.0])
        _drain(mon, 3)
        rep = mon.report()
        self.assertEqual(rep["min_free_gb"], 26.0)
        self.assertEqual(rep["first_free_gb"], 40.0)
        self.assertEqual(rep["last_free_gb"], 33.0)
        self.assertEqual(rep["samples"], 3)
        self.assertFalse(rep["aborted"])

    def test_warn_crossing_logs_once_not_per_sample(self):
        logs = []
        mon = _monitor([40.0, 19.0, 18.0, 17.5, 19.9], logs=logs)
        _drain(mon, 5)
        self.assertEqual(len(logs), 1, f"one crossing, one line: {logs}")
        self.assertIn("WARN", logs[0])
        self.assertEqual(mon.report()["bands"][pressure.BAND_WARN], 4)

    def test_a_reading_hovering_on_the_threshold_does_not_spam(self):
        """The hysteresis property: oscillation across the WARN line must not
        produce one log line per sample."""
        logs = []
        mon = _monitor([40.0, 19.0, 20.2, 19.5, 20.1, 19.8, 20.3], logs=logs)
        _drain(mon, 7)
        self.assertEqual(len(logs), 1, f"still ONE crossing: {logs}")

    def test_a_real_recovery_is_reported_once(self):
        logs = []
        mon = _monitor([40.0, 19.0, 19.5, 25.0, 26.0], logs=logs)
        _drain(mon, 5)
        self.assertEqual(len(logs), 2, logs)
        self.assertIn("recovered", logs[1])
        self.assertEqual(len(mon.report()["crossings"]), 3,
                         "None->OK, OK->WARN, WARN->OK")

    def test_unmeasurable_readings_never_produce_a_band_or_an_abort(self):
        logs = []
        fired = []
        mon = _monitor([None, None, None], logs=logs,
                       on_critical=lambda s: fired.append(s))
        _drain(mon, 3)
        rep = mon.report()
        self.assertEqual(logs, [])
        self.assertEqual(fired, [])
        self.assertFalse(rep["aborted"])
        self.assertIsNone(rep["last_free_gb"])
        self.assertEqual(rep["unmeasured"], 3)

    def test_a_raising_sampler_is_swallowed_and_counted(self):
        """Fail-open by contract: a sampler must never break a PAID drive."""
        def boom():
            raise RuntimeError("probe exploded")

        mon = pressure.DriveMonitor(None, floor=10.0, warn_mult=2.0,
                                    margin_gb=0.5, interval_s=0.01, read=boom,
                                    log=lambda s: None)
        self.assertIsNone(mon.poll())
        self.assertEqual(mon.report()["errors"], 1)
        self.assertFalse(mon.report()["aborted"])


class TestPressureJsonl(unittest.TestCase):
    def test_warn_samples_carry_t_free_band_and_the_top_offender(self):
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run"
            mon = _monitor([40.0, 18.0], run_dir=rd,
                           offenders=lambda: ("node", 8123.0))
            _drain(mon, 2)
            lines = [json.loads(ln) for ln in
                     (rd / pressure.PRESSURE_FILE).read_text(
                         encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, "only the WARN sample is recorded")
        row = lines[0]
        self.assertEqual(row["band"], pressure.BAND_WARN)
        self.assertEqual(row["free_gb"], 18.0)
        self.assertIn("t", row)
        self.assertIn("elapsed_s", row)
        self.assertEqual(row["top_offender"], "node")
        self.assertEqual(row["top_offender_mb"], 8123.0)

    def test_the_report_points_at_the_log_only_when_one_was_written(self):
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run"
            healthy = _monitor([40.0], run_dir=rd)
            _drain(healthy, 1)
            self.assertNotIn("log", healthy.report())
            warned = _monitor([18.0], run_dir=rd)
            _drain(warned, 1)
            self.assertEqual(warned.report()["log"], pressure.PRESSURE_FILE)

    def test_an_unwritable_run_dir_never_breaks_the_drive(self):
        mon = _monitor([18.0], run_dir=Path("Z:/definitely/not/a/dir"))
        self.assertIsNotNone(mon.poll())
        rep = mon.report()
        self.assertFalse(rep["aborted"])
        # Either the write failed (counted) or the platform allowed it; what
        # must never happen is a raise out of poll().
        self.assertGreaterEqual(rep["errors"] + rep["recorded"], 1)


class TestCriticalAbort(unittest.TestCase):
    def test_crossing_the_floor_fires_the_abort_exactly_once(self):
        fired = []
        logs = []
        mon = _monitor([40.0, 9.0, 8.0, 7.0], logs=logs,
                       on_critical=lambda s: fired.append(s))
        _drain(mon, 4)
        self.assertEqual(len(fired), 1, "one abort per drive, not one per sample")
        self.assertEqual(len(logs), 1)
        self.assertIn("CRITICAL", logs[0])
        rep = mon.report()
        self.assertTrue(rep["aborted"])
        self.assertIn("hard floor", rep["abort_note"])
        self.assertEqual(rep["worst_band"], pressure.BAND_CRITICAL)

    def test_the_abort_note_carries_the_measured_numbers(self):
        mon = _monitor([3.4], offenders=lambda: ("node", 9001.0),
                       on_critical=lambda s: None)
        _drain(mon, 1)
        note = mon.report()["abort_note"]
        self.assertIn("3.4 GB", note)
        self.assertIn("10 GB", note)
        self.assertIn("node", note)

    def test_a_raising_abort_hook_never_propagates(self):
        logs = []

        def boom(_s):
            raise RuntimeError("stop failed")

        mon = _monitor([5.0], logs=logs, on_critical=boom)
        self.assertIsNotNone(mon.poll())
        rep = mon.report()
        self.assertTrue(rep["aborted"], "the verdict is recorded regardless")
        self.assertTrue(any("abort hook failed" in ln for ln in logs))

    def test_the_verdict_is_the_between_rep_one_and_is_non_graded(self):
        from adapters.base import is_graded_verdict
        from aura_rig import stack_guard
        self.assertEqual(pressure.verdict(), "COMMIT-EXHAUSTED")
        self.assertEqual(pressure.verdict(), stack_guard.PRESSURE_VERDICT)
        self.assertFalse(is_graded_verdict(pressure.verdict()))


class TestMonitorThread(unittest.TestCase):
    def test_start_stop_samples_and_takes_a_final_at_exit_reading(self):
        mon = _monitor([40.0] * 50)
        mon.start()
        mon.stop()
        rep = mon.report()
        self.assertGreaterEqual(rep["samples"], 1)
        self.assertEqual(rep["last_free_gb"], 40.0)

    def test_stop_is_idempotent(self):
        mon = _monitor([40.0] * 50)
        mon.start().stop()
        mon.stop(final_poll=False)   # must not raise

    def test_the_factory_never_arms_inside_a_test_process(self):
        """Hermeticity, the kill_guard doctrine: a unit run must not sample the
        operator's box, let alone reach a teardown."""
        self.assertIsNone(pressure.start_drive_monitor(None))


# --------------------------------------------------------------------------- #
# Post-hoc attribution.                                                        #
# --------------------------------------------------------------------------- #

def _report(**over):
    base = {"samples": 40, "floor_gb": 10.0, "warn_gb": 20.0,
            "min_free_gb": 3.1, "last_free_gb": 3.4, "aborted": False}
    base.update(over)
    return base


class TestAttribution(unittest.TestCase):
    def test_editor_gone_with_a_low_last_sample_names_the_probable_cause(self):
        note = pressure.attribution("EDITOR-GONE", _report())
        self.assertIsNotNone(note)
        self.assertIn("PROBABLE CAUSE", note)
        self.assertIn("3.4 GB", note)
        self.assertIn("3.1", note, "low-water mark is named too")
        self.assertIn(pressure.PRESSURE_FILE, note)

    def test_a_drive_that_ended_healthy_is_never_blamed_on_pressure(self):
        self.assertIsNone(
            pressure.attribution("EDITOR-GONE", _report(last_free_gb=41.0)))

    def test_an_unmeasured_drive_is_never_blamed_on_pressure(self):
        self.assertIsNone(
            pressure.attribution("EDITOR-GONE", _report(last_free_gb=None)))

    def test_only_verdicts_pressure_can_cause_are_annotated(self):
        for v in ("PASS", "FAIL", "NO_DELIVERABLE", "AGENT-TIMEOUT", None):
            self.assertIsNone(pressure.attribution(v, _report()), v)
        self.assertIsNotNone(pressure.attribution("STACK-DOWN", _report()))

    def test_annotate_summary_writes_and_logs_once(self):
        logs = []
        summary = {"verdict": "EDITOR-GONE", "pressure": _report()}
        note = pressure.annotate_summary(summary, log=logs.append)
        self.assertEqual(summary["pressure_attribution"], note)
        self.assertEqual(len(logs), 1)

    def test_annotate_summary_is_a_no_op_without_evidence(self):
        summary = {"verdict": "EDITOR-GONE"}
        self.assertIsNone(pressure.annotate_summary(summary))
        self.assertNotIn("pressure_attribution", summary)

    def test_annotate_summary_never_raises_on_junk(self):
        self.assertIsNone(pressure.annotate_summary(None))
        self.assertIsNone(pressure.annotate_summary({"verdict": "EDITOR-GONE",
                                                     "pressure": "nonsense"}))


# --------------------------------------------------------------------------- #
# Leak-triggered recycle (pure).                                               #
# --------------------------------------------------------------------------- #

class TestStackFootprint(unittest.TestCase):
    def test_sums_measured_processes(self):
        entries = [pressure.ProcFootprint("vercel", 111, 4200.0),
                   pressure.ProcFootprint("client", 222, 3100.0)]
        self.assertEqual(pressure.stack_footprint_mb(entries), 7300.0)

    def test_one_pid_serving_both_ports_is_counted_once(self):
        entries = [("vercel", 111, 4200.0), ("client", 111, 4200.0)]
        self.assertEqual(pressure.stack_footprint_mb(entries), 4200.0)

    def test_a_blind_read_is_none_not_zero(self):
        """0 MB would read as 'the stack is tiny, no recycle needed' — a failed
        measurement silently voting AGAINST the guard."""
        self.assertIsNone(pressure.stack_footprint_mb([]))
        self.assertIsNone(pressure.stack_footprint_mb(
            [pressure.ProcFootprint("vercel", None, None)]))

    def test_partial_measurement_still_counts_what_it_saw(self):
        entries = [("vercel", 111, 4200.0), ("client", None, None)]
        self.assertEqual(pressure.stack_footprint_mb(entries), 4200.0)

    def test_read_stack_footprints_uses_injected_probes(self):
        got = pressure.read_stack_footprints(
            ports=(("vercel", 3000), ("client", 3002)),
            listening_pids=lambda port: {3000: [11], 3002: [22]}[port],
            private_mb=lambda pids: {11: 5000.0, 22: 1500.0})
        self.assertEqual(pressure.stack_footprint_mb(got), 6500.0)
        self.assertEqual([f.label for f in got], ["vercel", "client"])

    def test_a_raising_port_probe_degrades_to_unmeasured(self):
        def boom(_port):
            raise OSError("the TCP table is gone")

        got = pressure.read_stack_footprints(
            listening_pids=boom, private_mb=lambda pids: {})
        self.assertIsNone(pressure.stack_footprint_mb(got))


class TestScopedOffender(unittest.TestCase):
    """The offender is the largest of the STACK's OWN processes — never the
    biggest process on the box, because finding THAT means walking ~600
    processes, which is the enumeration the invariant forbids."""

    def test_picks_the_largest_measured_stack_process(self):
        with mock.patch.object(pressure, "read_stack_footprints", return_value=[
                pressure.ProcFootprint("vercel", 11, 4200.0),
                pressure.ProcFootprint("client", 22, 9100.0),
                pressure.ProcFootprint("editor-rc", 33, 3000.0)]):
            self.assertEqual(pressure.read_stack_offender(), ("client:22", 9100.0))

    def test_none_when_nothing_is_measurable(self):
        with mock.patch.object(pressure, "read_stack_footprints", return_value=[
                pressure.ProcFootprint("vercel", None, None)]):
            self.assertIsNone(pressure.read_stack_offender())

    def test_the_drive_scope_covers_the_editor_and_the_browser(self):
        """Naming the EDITOR in a post-mortem is worth a lot, and it costs the
        same two FFI calls as any other pid."""
        ports = dict((label, port) for label, port in pressure.DRIVE_PORTS)
        self.assertEqual(ports["editor-rc"], 30010)
        self.assertEqual(ports["dev-browser"], 9222)
        # ...but the RECYCLE scope stays the documented node leak only.
        self.assertEqual([p for _l, p in pressure.STACK_PORTS], [3000, 3002])


class TestPortScope(unittest.TestCase):
    def test_the_manifest_is_the_authority_on_what_the_stack_is(self):
        got = pressure.drive_ports({"ports": [3000, 3002, 9222, 30010]})
        self.assertEqual(got, (("vercel", 3000), ("client", 3002),
                               ("dev-browser", 9222), ("editor-rc", 30010)))

    def test_an_unknown_port_still_gets_a_readable_label(self):
        self.assertEqual(pressure.drive_ports({"ports": [4567]}),
                         (("port-4567", 4567),))

    def test_no_manifest_falls_back_to_the_default_scope(self):
        self.assertEqual(pressure.drive_ports({}), pressure.DRIVE_PORTS)
        self.assertEqual(pressure.drive_ports({"ports": "junk"}),
                         pressure.DRIVE_PORTS)


class TestRecycleDecision(unittest.TestCase):
    def test_cadence_still_fires(self):
        do, why = pressure.recycle_decision(reps_since_recycle=4, cadence=4,
                                            footprint_mb=100.0,
                                            threshold_mb=6000.0)
        self.assertTrue(do)
        self.assertIn("cadence", why)

    def test_a_bloated_stack_recycles_before_the_cadence(self):
        do, why = pressure.recycle_decision(reps_since_recycle=1, cadence=4,
                                            footprint_mb=7412.0,
                                            threshold_mb=6000.0)
        self.assertTrue(do)
        self.assertIn("leak", why)
        self.assertIn("7,412", why)

    def test_a_healthy_stack_mid_cadence_is_left_alone(self):
        do, why = pressure.recycle_decision(reps_since_recycle=1, cadence=4,
                                            footprint_mb=2500.0,
                                            threshold_mb=6000.0)
        self.assertFalse(do)
        self.assertEqual(why, "")

    def test_a_blind_probe_never_manufactures_a_recycle(self):
        do, _why = pressure.recycle_decision(reps_since_recycle=1, cadence=4,
                                             footprint_mb=None,
                                             threshold_mb=6000.0)
        self.assertFalse(do)

    def test_the_leak_trigger_survives_a_disabled_cadence(self):
        """`--restart-stack-every 0` disables the CADENCE; the leak guard is a
        separate safety and is switched off with CB_STACK_RECYCLE_MB=0."""
        do, why = pressure.recycle_decision(reps_since_recycle=9, cadence=0,
                                            footprint_mb=7000.0,
                                            threshold_mb=6000.0)
        self.assertTrue(do)
        self.assertIn("leak", why)
        do, _ = pressure.recycle_decision(reps_since_recycle=9, cadence=0,
                                          footprint_mb=7000.0, threshold_mb=0.0)
        self.assertFalse(do)

    def test_threshold_defaults_to_the_env_knob(self):
        with mock.patch.dict(os.environ, {"CB_STACK_RECYCLE_MB": "1000"}):
            do, _ = pressure.recycle_decision(reps_since_recycle=0, cadence=4,
                                              footprint_mb=1500.0)
            self.assertTrue(do)

    def test_measure_stack_footprint_mb_never_raises(self):
        with mock.patch.object(pressure, "read_stack_footprints",
                               side_effect=RuntimeError("boom")):
            self.assertIsNone(pressure.measure_stack_footprint_mb())


# --------------------------------------------------------------------------- #
# Wiring: the in-process tree terminator the abort path uses.                  #
# --------------------------------------------------------------------------- #
#
# What used to stand here: TestRecordDrivePressure and TestDriveSeam, covering
# ``run_graded.record_drive_pressure`` (the COMMIT-EXHAUSTED verdict + teardown
# wiring) and ``aura_product.drive`` / ``aura_product.DriveChild`` (the
# cancellable CDP drive child, and its stop path's own no-subprocess rule).
# Both subjects belonged to the aura-product lane and left with it in the public
# release: ``record_drive_pressure`` is defined and called ONLY inside
# aura_rig/run_graded.py (:601, and its three call sites :1611/:1933/:2531),
# which no published arm reaches, and aura_rig/aura_product.py is gone
# altogether. Removed 2026-08-28 rather than skipped — a test whose subject does
# not ship cannot tell a broken guard from a correct one, and a green skip in a
# release suite reads as coverage that isn't there.
#
# NOTHING arm-generic went with them. The guard itself — the no-subprocess
# invariant, the three bands off envgate's floor, hysteresis, pressure.jsonl,
# the CRITICAL abort, the recycle decision, and ``pressure.annotate_summary`` /
# ``pressure.attribution``, which write the EDITOR-GONE probable-cause sentence
# that the deleted end-to-end test asserted through run_graded — is exercised
# directly against ``aura_rig.pressure`` above (TestAttribution, :489). Only the
# cut lane's CALL SITES are gone; aura_rig/pressure.py is kept and is still
# imported by stack.py and stack_guard.py.

class TestTerminateTreeInProcess(unittest.TestCase):
    """The tree kill the abort path calls. It fires DURING the commit crisis,
    so it is bound by the same hard rule as the sampler (see
    TestNoSubprocessInvariant): it must not spawn anything, and it must not
    raise on a pid that is not there any more."""

    def test_terminate_tree_never_raises_on_a_bogus_pid(self):
        self.assertEqual(pressure.terminate_tree_in_process(0), 0)
        self.assertIsInstance(pressure.terminate_tree_in_process(2 ** 31 - 1),
                              int)


if __name__ == "__main__":
    unittest.main()
