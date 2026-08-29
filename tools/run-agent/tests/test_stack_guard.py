"""Unit tests for aura_rig.stack_guard — ownership manifest, startup
reconciliation, the orphan sweep, and the pre-rep commit-pressure hook.

Fully offline in the test_stack_reap style: every process/filesystem/kill
touch is injected (procs / kill / foreign / alive / teardown / read / recycle /
sleep), manifests live in a per-test tempdir via CB_STACK_MANIFEST. Nothing
here lists real UE processes, kills anything, or reads the real machine's
commit charge (the two pid_alive smoke tests use only our OWN live pid and a
guaranteed-dead one).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import stack_guard as sg  # noqa: E402


def _mk_manifest(**over) -> dict:
    base = {
        "schema": sg.SCHEMA,
        "generation": "20260807-000000-1234",
        "created_at": 1000.0,
        "last_activity": 1000.0,
        "owner_pid": 4242,
        "owner_created": 999.0,
        "owner_kind": "cb",
        "session_pid": 77,
        "session_created": 500.0,
        "repo_root": r"C:\gh\craftbench",
        "uproject": r"C:\cb\scratch\CraftBenchGraded\CraftBenchTemplate.uproject",
        "ports": [3000, 3002, 9222, 30010],
        "no_teardown": False,
        "command": "bench",
    }
    base.update(over)
    return base


class _ManifestDir(unittest.TestCase):
    """Base: a tempdir manifest path via CB_STACK_MANIFEST."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.mpath = Path(self.td.name) / "stack-manifest.json"
        patcher = mock.patch.dict(
            os.environ, {"CB_STACK_MANIFEST": str(self.mpath)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("CB_STACK_GUARD", None)


# --------------------------------------------------------------------------- #
# Manifest I/O.                                                                #
# --------------------------------------------------------------------------- #

class TestManifestIO(_ManifestDir):
    def test_roundtrip(self):
        m = _mk_manifest()
        self.assertTrue(sg.write_manifest(m))
        self.assertEqual(sg.read_manifest(), m)

    def test_absent_reads_none(self):
        self.assertIsNone(sg.read_manifest())

    def test_corrupt_reads_none(self):
        self.mpath.write_text("{not json", encoding="utf-8")
        self.assertIsNone(sg.read_manifest())

    def test_wrong_schema_reads_none(self):
        # An unknown schema is DEBRIS, not a stack — reconciliation must not
        # trust fields whose contract it does not know.
        sg.write_manifest(_mk_manifest(schema=sg.SCHEMA + 1))
        self.assertIsNone(sg.read_manifest())

    def test_clear_removes_and_tolerates_absent(self):
        sg.write_manifest(_mk_manifest())
        sg.clear_manifest()
        self.assertIsNone(sg.read_manifest())
        sg.clear_manifest()  # second clear: no raise

    def test_touch_activity_bumps(self):
        sg.write_manifest(_mk_manifest(last_activity=1.0))
        sg.touch_activity(now=lambda: 555.0)
        self.assertEqual(sg.read_manifest()["last_activity"], 555.0)

    def test_touch_activity_no_manifest_is_noop(self):
        sg.touch_activity(now=lambda: 555.0)  # no raise, nothing created
        self.assertIsNone(sg.read_manifest())


# --------------------------------------------------------------------------- #
# Pid liveness (only our OWN pid + a guaranteed-dead one — no real kills).     #
# --------------------------------------------------------------------------- #

class TestPidAlive(unittest.TestCase):
    def test_own_pid_is_alive(self):
        self.assertTrue(sg.pid_alive(os.getpid()))

    def test_nonsense_pids_are_dead(self):
        self.assertFalse(sg.pid_alive(0))
        self.assertFalse(sg.pid_alive(-5))
        self.assertFalse(sg.pid_alive(None))
        self.assertFalse(sg.pid_alive("x"))

    def test_pid_reuse_defense_create_time_mismatch(self):
        # Our own pid with a WILDLY wrong recorded birth must read DEAD —
        # that is the reused-pid signature. Skipped when the host cannot
        # measure create times at all (then the check degrades to liveness,
        # per the absent-measurement-is-never-a-verdict contract).
        created = sg.pid_create_time(os.getpid())
        if created is None:
            self.skipTest("no create-time probe on this host")
        self.assertTrue(sg.pid_alive(os.getpid(), created))
        self.assertFalse(sg.pid_alive(os.getpid(), created - 86400.0))


class TestSessionAnchor(unittest.TestCase):
    """Pure over an injected ancestor chain — the AGE rule, not names."""

    def test_skips_young_shims_picks_first_old_ancestor(self):
        chain = [(10, 995.0), (20, 998.0), (30, 100.0), (40, 50.0)]
        got = sg.session_anchor(min_age_s=60.0, now=lambda: 1000.0, chain=chain)
        self.assertEqual(got, (30, 100.0))

    def test_unknown_age_is_skipped_not_trusted(self):
        chain = [(10, None), (30, 100.0)]
        got = sg.session_anchor(min_age_s=60.0, now=lambda: 1000.0, chain=chain)
        self.assertEqual(got, (30, 100.0))

    def test_no_qualifying_ancestor_is_none(self):
        chain = [(10, 999.0), (20, None)]
        self.assertIsNone(
            sg.session_anchor(min_age_s=60.0, now=lambda: 1000.0, chain=chain))


# --------------------------------------------------------------------------- #
# Owner classification.                                                        #
# --------------------------------------------------------------------------- #

class TestClassifyOwner(unittest.TestCase):
    def _cl(self, m, alive_ret=True, ancestor_ret=False, self_pid=9999):
        return sg.classify_owner(
            m, self_pid=self_pid,
            alive=lambda pid, created=None: alive_ret,
            is_ancestor=lambda pid: ancestor_ret)

    def test_none(self):
        self.assertEqual(self._cl(None), "none")

    def test_dead_owner_is_orphan(self):
        self.assertEqual(self._cl(_mk_manifest(), alive_ret=False), "orphan")

    def test_missing_owner_pid_is_orphan(self):
        # A manifest we cannot attribute is debris — the leak-safe direction.
        self.assertEqual(self._cl(_mk_manifest(owner_pid=None)), "orphan")
        self.assertEqual(self._cl(_mk_manifest(owner_pid="x")), "orphan")

    def test_self_owner(self):
        self.assertEqual(
            self._cl(_mk_manifest(owner_pid=9999), self_pid=9999), "live-self")

    def test_session_kind_is_live_session(self):
        m = _mk_manifest(owner_kind="session")
        self.assertEqual(self._cl(m), "live-session")

    def test_ancestor_owner_is_live_self(self):
        self.assertEqual(self._cl(_mk_manifest(), ancestor_ret=True),
                         "live-self")

    def test_other_live_cb_is_live_other(self):
        self.assertEqual(self._cl(_mk_manifest()), "live-other")

    def test_pid_reuse_via_alive_seam(self):
        # alive() receives the recorded create time — a reuse-aware alive
        # returning False must classify as orphan even though the PID exists.
        seen = {}

        def alive(pid, created=None):
            seen["args"] = (pid, created)
            return False

        got = sg.classify_owner(_mk_manifest(), self_pid=1,
                                alive=alive, is_ancestor=lambda p: False)
        self.assertEqual(got, "orphan")
        self.assertEqual(seen["args"], (4242, 999.0))


# --------------------------------------------------------------------------- #
# reconcile_at_entry.                                                          #
# --------------------------------------------------------------------------- #

class TestReconcileAtEntry(_ManifestDir):
    def _run(self, command, manifest=None, alive=False, env=None, logs=None,
             teardowns=None):
        logs = logs if logs is not None else []
        teardowns = teardowns if teardowns is not None else []
        if manifest is not None:
            sg.write_manifest(manifest)
        rc = sg.reconcile_at_entry(
            command, log=logs.append,
            teardown=lambda log: teardowns.append(1),
            classify=lambda m: ("none" if m is None else
                                ("live-other" if alive else "orphan")),
            env=env or {})
        return rc, logs, teardowns

    def test_no_manifest_is_silent_noop(self):
        rc, logs, td = self._run("eval")
        self.assertIsNone(rc)
        self.assertEqual(logs, [])
        self.assertEqual(td, [])

    def test_dead_owner_tears_down_before_a_mutating_command(self):
        rc, logs, td = self._run("eval", manifest=_mk_manifest())
        self.assertIsNone(rc, "reconciliation heals, it never blocks")
        self.assertEqual(td, [1], "full teardown must have run")
        joined = "\n".join(logs)
        self.assertIn("ORPHANED", joined)
        self.assertIn("4242", joined)          # names the dead owner pid
        self.assertIn("kill-audit", joined)    # points at the audit trail

    def test_read_only_command_gets_notice_but_never_mutates(self):
        for cmd in ("status", "where", "doctor", "sync-aura"):
            rc, logs, td = self._run(cmd, manifest=_mk_manifest())
            self.assertIsNone(rc, cmd)
            self.assertEqual(td, [], f"`cb {cmd}` is documented READ-ONLY")
            self.assertIn("ORPHANED", "\n".join(logs), cmd)

    def test_silent_commands_say_nothing_at_all(self):
        for cmd in ("help", "completions", "__complete"):
            rc, logs, td = self._run(cmd, manifest=_mk_manifest())
            self.assertIsNone(rc, cmd)
            self.assertEqual(logs, [], f"`cb {cmd}` output is machine-facing")
            self.assertEqual(td, [])

    def test_live_other_refuses_exclusive_commands(self):
        rc, logs, td = self._run("bench", manifest=_mk_manifest(), alive=True)
        self.assertEqual(rc, 2)
        self.assertEqual(td, [], "refusal must not tear a LIVE stack down")
        self.assertIn("CB_ALLOW_STACK_TAKEOVER", "\n".join(logs))

    def test_live_other_takeover_override(self):
        rc, _logs, td = self._run("bench", manifest=_mk_manifest(), alive=True,
                                  env={"CB_ALLOW_STACK_TAKEOVER": "1"})
        self.assertIsNone(rc)
        self.assertEqual(td, [])

    def test_live_other_nonexclusive_command_proceeds(self):
        rc, _logs, td = self._run("preview", manifest=_mk_manifest(), alive=True)
        self.assertIsNone(rc)
        self.assertEqual(td, [])

    def test_proceeding_touches_activity(self):
        sg.write_manifest(_mk_manifest(last_activity=1.0))
        rc = sg.reconcile_at_entry(
            "eval", log=lambda s: None, teardown=lambda log: None,
            classify=lambda m: "live-session", env={})
        self.assertIsNone(rc)
        self.assertGreater(sg.read_manifest()["last_activity"], 1.0)

    def test_kill_switch_disables_everything(self):
        with mock.patch.dict(os.environ, {"CB_STACK_GUARD": "0"}):
            rc, logs, td = self._run("eval", manifest=_mk_manifest())
        self.assertIsNone(rc)
        self.assertEqual(td, [])
        self.assertEqual(logs, [])

    def test_production_wiring_is_inert_in_a_test_process(self):
        # The 2026-08-07 entry path: tests/test_cb_preview_cmd calls the REAL
        # cb.main(), which calls this hook — and a stale manifest on the box
        # then ran the full production stop_stack from a unit test. With NO
        # seams injected (the production wiring) this must do nothing at all:
        # no teardown, no manifest write, no exit-2 host dependence.
        sg.write_manifest(_mk_manifest(last_activity=1.0))
        with mock.patch.object(sg, "_default_teardown") as td:
            self.assertIsNone(sg.reconcile_at_entry("eval", log=lambda s: None))
        td.assert_not_called()
        self.assertEqual(sg.read_manifest()["last_activity"], 1.0)

    def test_injected_seams_still_run_under_test(self):
        # ...and the inertness must not disable the unit under test itself.
        rc, logs, td = self._run("eval", manifest=_mk_manifest())
        self.assertIsNone(rc)
        self.assertEqual(td, [1])

    def test_never_raises(self):
        def boom(m):
            raise RuntimeError("probe died")

        sg.write_manifest(_mk_manifest())
        logs = []
        rc = sg.reconcile_at_entry("eval", log=logs.append,
                                   teardown=lambda log: None,
                                   classify=boom, env={})
        self.assertIsNone(rc, "a broken guard must not brick every cb command")
        self.assertIn("continuing", "\n".join(logs))


# --------------------------------------------------------------------------- #
# record_bringup / release_at_exit (the ownership transfer).                   #
# --------------------------------------------------------------------------- #

class TestRecordAndRelease(_ManifestDir):
    def test_record_bringup_owns_as_us(self):
        m = sg.record_bringup("X.uproject", command="eval", now=lambda: 42.0)
        self.assertIsNotNone(m)
        on_disk = sg.read_manifest()
        self.assertEqual(on_disk["owner_pid"], os.getpid())
        self.assertEqual(on_disk["owner_kind"], "cb")
        self.assertEqual(on_disk["uproject"], "X.uproject")
        self.assertEqual(on_disk["created_at"], 42.0)

    def test_record_bringup_replaces_prior_generation(self):
        sg.write_manifest(_mk_manifest(generation="OLD"))
        sg.record_bringup("Y.uproject")
        self.assertNotEqual(sg.read_manifest()["generation"], "OLD")

    def test_record_disabled_by_kill_switch(self):
        with mock.patch.dict(os.environ, {"CB_STACK_GUARD": "0"}):
            self.assertIsNone(sg.record_bringup("X.uproject"))
        self.assertIsNone(sg.read_manifest())

    def test_release_transfers_to_live_session(self):
        sg.write_manifest(_mk_manifest(owner_pid=os.getpid(),
                                       session_pid=77, session_created=500.0))
        logs = []
        sg.release_at_exit(no_teardown=True, log=logs.append,
                           alive=lambda pid, created=None: True)
        m = sg.read_manifest()
        self.assertEqual(m["owner_pid"], 77)
        self.assertEqual(m["owner_kind"], "session")
        self.assertTrue(m["no_teardown"])
        # The --no-teardown interpretation is DOCUMENTED at transfer time:
        self.assertIn("keep between MY runs", "\n".join(logs))

    def test_release_with_dead_session_keeps_our_pid(self):
        # No live anchor -> the manifest keeps the dying cb pid, and the
        # janitor reaps within a poll. Conservative: teardown over leak.
        sg.write_manifest(_mk_manifest(owner_pid=os.getpid()))
        logs = []
        sg.release_at_exit(log=logs.append,
                           alive=lambda pid, created=None: False)
        self.assertEqual(sg.read_manifest()["owner_pid"], os.getpid())
        self.assertIn("janitor", "\n".join(logs))

    def test_release_ignores_a_stack_we_do_not_own(self):
        sg.write_manifest(_mk_manifest(owner_pid=123456))
        sg.release_at_exit(log=lambda s: None,
                           alive=lambda pid, created=None: True)
        self.assertEqual(sg.read_manifest()["owner_pid"], 123456)

    def test_release_without_manifest_is_noop(self):
        sg.release_at_exit(log=lambda s: None)  # no raise


# --------------------------------------------------------------------------- #
# PENDING manifest — armed at bring-up START (gap found live 2026-08-07).      #
#                                                                              #
# The manifest used to be written only at STACK GREEN, so a bring-up           #
# interrupted mid-flight left real vercel/client/editor processes with NO      #
# manifest and NO janitor — invisible to every recovery path, all of which key #
# off a manifest. These tests pin the arm -> promote -> reconcile lifecycle.   #
# --------------------------------------------------------------------------- #

class TestPendingManifest(_ManifestDir):
    def test_legacy_manifest_without_state_reads_green(self):
        self.assertEqual(sg.manifest_state(_mk_manifest()), sg.STATE_GREEN)
        self.assertEqual(sg.manifest_state(None), sg.STATE_GREEN)
        self.assertEqual(sg.manifest_state({"state": "nonsense"}), sg.STATE_GREEN)

    def test_arm_writes_a_pending_manifest_owned_by_us(self):
        m = sg.record_bringup_pending("X.uproject", command="eval")
        self.assertEqual(m["state"], sg.STATE_PENDING)
        on_disk = sg.read_manifest()
        self.assertEqual(sg.manifest_state(on_disk), sg.STATE_PENDING)
        self.assertEqual(on_disk["owner_pid"], os.getpid())
        self.assertEqual(on_disk["owner_kind"], "cb")

    def test_promote_keeps_the_generation_the_janitor_was_armed_against(self):
        armed = sg.record_bringup_pending("X.uproject")
        promoted = sg.promote_to_green("X.uproject")
        self.assertEqual(promoted["generation"], armed["generation"],
                         "the janitor's staleness recheck compares generations")
        self.assertEqual(sg.manifest_state(sg.read_manifest()), sg.STATE_GREEN)

    def test_retry_by_the_same_process_reuses_the_pending_generation(self):
        # A bring-up that legitimately FAILS and is retried by the same cb must
        # not mint a new generation on every attempt.
        first = sg.record_bringup_pending("X.uproject", now=lambda: 10.0)
        again = sg.record_bringup_pending("X.uproject", now=lambda: 20.0)
        self.assertEqual(again["generation"], first["generation"])
        self.assertEqual(again["created_at"], 10.0)
        self.assertEqual(again["last_activity"], 20.0)
        self.assertEqual(sg.manifest_state(sg.read_manifest()), sg.STATE_PENDING)

    def test_arm_replaces_another_generations_manifest(self):
        sg.write_manifest(_mk_manifest(generation="OLD", owner_pid=123456))
        sg.record_bringup_pending("X.uproject")
        m = sg.read_manifest()
        self.assertNotEqual(m["generation"], "OLD")
        self.assertEqual(m["owner_pid"], os.getpid())

    def test_promote_without_a_pending_manifest_falls_back_to_a_green_record(self):
        # Guard disabled at arm time / manifest cleared under us: the result is
        # exactly the pre-2026-08-07 behaviour, never a missing manifest.
        m = sg.promote_to_green("X.uproject", command="bench")
        self.assertEqual(m["state"], sg.STATE_GREEN)
        self.assertEqual(sg.read_manifest()["owner_pid"], os.getpid())

    def test_promote_does_not_steal_another_owners_pending_manifest(self):
        sg.write_manifest(_mk_manifest(state=sg.STATE_PENDING, owner_pid=123456,
                                       generation="THEIRS"))
        m = sg.promote_to_green("X.uproject")
        self.assertEqual(m["owner_pid"], os.getpid())
        self.assertNotEqual(m["generation"], "THEIRS")

    def test_kill_switch_disables_both(self):
        with mock.patch.dict(os.environ, {"CB_STACK_GUARD": "0"}):
            self.assertIsNone(sg.record_bringup_pending("X.uproject"))
            self.assertIsNone(sg.promote_to_green("X.uproject"))
        self.assertIsNone(sg.read_manifest())

    def test_dead_owner_pending_classifies_as_orphan_exactly_like_green(self):
        m = _mk_manifest(state=sg.STATE_PENDING)
        self.assertEqual(
            sg.classify_owner(m, alive=lambda *a, **k: False,
                              is_ancestor=lambda p: False), "orphan")

    def test_live_owner_pending_still_blocks_a_second_exclusive_cb(self):
        m = _mk_manifest(state=sg.STATE_PENDING)
        self.assertEqual(
            sg.classify_owner(m, alive=lambda *a, **k: True,
                              is_ancestor=lambda p: False), "live-other")

    def test_reconcile_reaps_an_interrupted_bring_up(self):
        sg.write_manifest(_mk_manifest(state=sg.STATE_PENDING))
        logs, td = [], []
        rc = sg.reconcile_at_entry(
            "eval", log=logs.append, teardown=lambda log: td.append(1),
            classify=lambda m: "orphan")
        self.assertIsNone(rc)
        self.assertEqual(td, [1], "an interrupted bring-up is torn down")
        joined = "\n".join(logs)
        self.assertIn("INTERRUPTED bring-up", joined)
        self.assertIn("kill-audit", joined)


# --------------------------------------------------------------------------- #
# Orphan matcher + sweep (scenario 7).                                         #
# --------------------------------------------------------------------------- #

_MARKERS = ["craftbench", r"c:\gh\craftbench", "c:/gh/craftbench",
            r"c:\cb\scratch", "c:/cb/scratch", r"c:\cb\wd", "c:/cb/wd"]

_FOREIGN_CL = r"c:\ue\engine\binaries\win64\unrealeditor.exe " \
              r"c:\users\x\github\unrealfeaturedev\unrealfeaturedev.uproject -game"
_CB_SCRATCH_CL = r"c:\ue\engine\binaries\win64\unrealeditor.exe " \
                 r"c:\cb\scratch\thirdpersonscratch\thirdperson.uproject " \
                 r"-renderoffscreen -auraheadless"
_CB_REPO_CL = r"c:\ue\engine\binaries\win64\unrealeditor-cmd.exe " \
              r"c:\gh\craftbench\ue-projects\craftbenchtemplate\x.uproject"


class TestOrphanClassification(unittest.TestCase):
    def test_cb_paths_classify_cb(self):
        self.assertEqual(
            sg.classify_ue_cmdline("UnrealEditor", _CB_SCRATCH_CL, _MARKERS), "cb")
        self.assertEqual(
            sg.classify_ue_cmdline("UnrealEditor-Cmd", _CB_REPO_CL, _MARKERS), "cb")

    def test_foreign_project_classifies_other(self):
        self.assertEqual(
            sg.classify_ue_cmdline("UnrealEditor", _FOREIGN_CL, _MARKERS), "other")

    def test_empty_cmdline_is_other_never_by_image_name(self):
        # THE rule: the image name alone is never evidence of ownership.
        self.assertEqual(
            sg.classify_ue_cmdline("UnrealEditor", "", _MARKERS), "other")

    def test_markers_include_repo_scratch_and_wd_roots(self):
        markers = sg.cb_cmdline_markers(Path(r"C:\somewhere\repo"))
        joined = " | ".join(markers)
        self.assertIn("craftbench", joined)         # legacy name marker
        self.assertIn(r"c:\somewhere\repo", joined)
        self.assertIn("c:/somewhere/repo", joined)  # both slash spellings


class _SweepRig:
    """Recorder harness around orphan_sweep with inert defaults."""

    def __init__(self, entries, foreign=None):
        self.entries = entries
        self.foreign = foreign
        self.killed = []
        self.audited = []
        self.blanket_calls = []
        self.logs = []

    def run(self, **kw):
        return sg.orphan_sweep(
            procs=lambda: self.entries,
            markers=_MARKERS,
            kill=self.killed.append,
            foreign=lambda: self.foreign,
            blanket=lambda: self.blanket_calls.append(1),
            audit=lambda target, reason="": self.audited.append(target),
            log=self.logs.append, **kw)


class TestOrphanSweep(unittest.TestCase):
    def test_cb_editors_killed_foreign_untouchable(self):
        rig = _SweepRig([("UnrealEditor", 11, _CB_SCRATCH_CL),
                         ("UnrealEditor", 22, _FOREIGN_CL),
                         ("UnrealEditor-Cmd", 33, _CB_REPO_CL)])
        killed = rig.run()
        self.assertEqual(sorted(rig.killed), [11, 33])
        self.assertEqual({p for _i, p in killed}, {11, 33})
        self.assertNotIn(22, rig.killed,
                         "a FOREIGN project's editor is untouchable, full stop")

    def test_unmarked_editor_never_killed_by_image_name(self):
        rig = _SweepRig([("UnrealEditor-Cmd", 44, "")])
        rig.run()
        self.assertEqual(rig.killed, [])

    def test_helper_images_gated_on_foreign_editor(self):
        # LiveCodingConsole/CrashReportClient cmdlines rarely carry a project
        # path. Unmarked ones are killed ONLY when no foreign editor runs
        # (the ensure_editor_dead sweep convention).
        entries = [("LiveCodingConsole", 55, "livecodingconsole.exe"),
                   ("CrashReportClient", 66, "crashreportclient.exe")]
        rig = _SweepRig(entries, foreign=None)
        rig.run()
        self.assertEqual(sorted(rig.killed), [55, 66])
        rig2 = _SweepRig(entries, foreign=(22, _FOREIGN_CL))
        rig2.run()
        self.assertEqual(rig2.killed, [],
                         "they may belong to the foreign editor - spared")

    def test_marked_helper_killed_even_with_foreign_editor(self):
        rig = _SweepRig(
            [("CrashReportClient", 77,
              r"crashreportclient.exe c:\cb\scratch\x\saved\crashes\y")],
            foreign=(22, _FOREIGN_CL))
        rig.run()
        self.assertEqual(rig.killed, [77])

    def test_every_kill_is_audited(self):
        rig = _SweepRig([("UnrealEditor", 11, _CB_SCRATCH_CL)])
        rig.run()
        self.assertTrue(any("pid=11" in a for a in rig.audited))

    def test_enumeration_blind_falls_back_to_legacy_blanket(self):
        rig = _SweepRig(None)
        rig.entries = None
        killed = sg.orphan_sweep(
            procs=lambda: None, markers=_MARKERS,
            kill=rig.killed.append, foreign=lambda: None,
            blanket=lambda: rig.blanket_calls.append(1),
            audit=lambda *a, **k: None, log=rig.logs.append)
        self.assertEqual(killed, [])
        self.assertEqual(rig.blanket_calls, [1],
                         "fail-open: blind enumeration keeps the old behavior")

    def test_own_pid_is_never_swept(self):
        rig = _SweepRig([("UnrealEditor", os.getpid(), _CB_SCRATCH_CL)])
        rig.run()
        self.assertEqual(rig.killed, [])


# --------------------------------------------------------------------------- #
# Pre-rep commit-pressure hook (scenarios 5 + 6 mid-bench).                    #
# --------------------------------------------------------------------------- #

class TestEnsureCommitHeadroom(unittest.TestCase):
    def _run(self, readings, floor=10.0):
        it = iter(readings)
        recycles = []
        logs = []
        ok, note = sg.ensure_commit_headroom(
            recycle=lambda: recycles.append(1),
            read=lambda: next(it),
            floor=floor, sleep=lambda s: None, log=logs.append)
        return ok, note, recycles, logs

    def test_above_floor_no_recycle(self):
        ok, _n, recycles, _l = self._run([25.0])
        self.assertTrue(ok)
        self.assertEqual(recycles, [])

    def test_unmeasured_is_never_a_verdict(self):
        ok, _n, recycles, _l = self._run([None])
        self.assertTrue(ok)
        self.assertEqual(recycles, [])

    def test_below_floor_recycles_and_recovers(self):
        ok, note, recycles, logs = self._run([4.0, 24.0])
        self.assertTrue(ok)
        self.assertEqual(recycles, [1], "exactly one recycle")
        self.assertIn("recycl", "\n".join(logs).lower())
        self.assertIn("recovered", note)

    def test_still_below_after_recycle_aborts_with_named_reason(self):
        ok, note, recycles, _l = self._run([4.0, 5.0])
        self.assertFalse(ok)
        self.assertEqual(recycles, [1])
        self.assertIn("AFTER a stack recycle", note)
        self.assertIn("model failure", note)

    def test_floor_override_honored(self):
        ok, _n, recycles, _l = self._run([5.0], floor=4.0)
        self.assertTrue(ok, "5 GB clears a 4 GB floor")
        self.assertEqual(recycles, [])

    def test_pressure_verdict_is_non_graded(self):
        # The abort reason must stay OUT of every pass-rate denominator —
        # the allowlist property the whole taxonomy leans on.
        from adapters.base import is_graded_verdict
        self.assertFalse(is_graded_verdict(sg.PRESSURE_VERDICT))


if __name__ == "__main__":
    unittest.main()
