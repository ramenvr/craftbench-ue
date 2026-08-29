"""Unit tests for aura_rig.envgate — the pre-spend environment gate, fully offline.

Mirrors tests/test_cb_doctor.py's pattern: build an everything-OK Facts literal
via _all_good(), flip ONE field per test with dataclasses.replace, assert the
single resulting check. gate() is pure over its Facts argument — no UE, no
process scan, no .env.

Run from tools/run-agent:  py -3.12 -m unittest tests.test_cb_envgate -v
"""

import os
import unittest
from dataclasses import replace
from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import envgate  # noqa: E402


def _all_good(**over) -> envgate.Facts:
    """An everything-OK Facts literal for the aura tier (superset of the rest)."""
    base = envgate.Facts(
        ue_root=r"C:\Program Files\Epic Games\UE_5.8",
        wd_root=r"C:\cb\wd",
        is_windows=True,
        live_coding=0,
        ram_pct=45.0,
        l1_cap=None,
        startup_task_maps=[],
        temp_root=r"C:\cbtmp",
        temp_root_canonical=r"C:\cbtmp",
        claude_cli=r"C:\bin\claude.cmd",
    )
    return replace(base, **over)


def _by_id(checks, cid):
    got = [c for c in checks if c.id == cid]
    assert len(got) == 1, f"expected exactly one {cid!r} check, got {len(got)}"
    return got[0]


def _statuses(checks):
    return {c.id: c.status for c in checks}


class TestGradeTier(unittest.TestCase):
    def test_all_ok(self):
        checks = envgate.gate(_all_good(), "grade")
        self.assertTrue(all(c.status == "OK" for c in checks), _statuses(checks))

    def test_grade_tier_has_no_baseline_or_aura_checks(self):
        ids = {c.id for c in envgate.gate(_all_good(), "grade")}
        self.assertNotIn("claude-cli", ids)
        self.assertNotIn("genius-checkout", ids)

    def test_missing_ue_root_fails(self):
        c = _by_id(envgate.gate(_all_good(ue_root=None), "grade"), "ue-root")
        self.assertEqual(c.status, "FAIL")
        self.assertIn("CB_UE_ROOT", c.fix)

    def test_long_workdir_fails_on_windows(self):
        long_wd = "C:\\Users\\someone\\OneDrive\\Documents\\GitHub\\craftbench\\wd\\deep"
        assert len(long_wd) > envgate.MAX_WD_ROOT_LEN
        c = _by_id(envgate.gate(_all_good(wd_root=long_wd), "grade"), "workdir-short")
        self.assertEqual(c.status, "FAIL")
        self.assertIn("CB_ROOT", c.fix)

    def test_long_workdir_ok_off_windows(self):
        long_wd = "/home/someone/very/long/path/that/exceeds/sixty/characters/easily/wd"
        c = _by_id(envgate.gate(_all_good(wd_root=long_wd, is_windows=False), "grade"),
                   "workdir-short")
        self.assertEqual(c.status, "OK")

    def test_live_coding_fails(self):
        c = _by_id(envgate.gate(_all_good(live_coding=1), "grade"), "live-coding")
        self.assertEqual(c.status, "FAIL")
        self.assertIn("13s", c.detail)          # the signature a user will have seen
        self.assertIn("cb down", c.fix)

    def test_high_ram_warns_not_fails(self):
        c = _by_id(envgate.gate(_all_good(ram_pct=92.0), "grade"), "ram-headroom")
        self.assertEqual(c.status, "WARN")
        self.assertIn("C3859", c.detail)
        self.assertIn("CRAFTBENCH_L1_MAX_PARALLEL", c.fix)

    def test_ram_probe_unavailable_is_ok(self):
        c = _by_id(envgate.gate(_all_good(ram_pct=None), "grade"), "ram-headroom")
        self.assertEqual(c.status, "OK")

    def test_startup_task_map_fails(self):
        rows = ["CraftBenchTemplate: GameDefaultMap=/Game/Maps/L_SanityTask.L_SanityTask"]
        c = _by_id(envgate.gate(_all_good(startup_task_maps=rows), "grade"),
                   "startup-maps")
        self.assertEqual(c.status, "FAIL")
        self.assertIn("L_SanityTask", c.detail)
        self.assertIn("/Engine/Maps/Entry", c.fix)

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            envgate.gate(_all_good(), "full-rig")   # doctor's tier name, not ours


class TestTempWorkdir8Dot3Probe(unittest.TestCase):
    """FAILURE-LOG 2026-07-25 — preflight printed "grade: 5 checks OK" and then
    all 15 tasks failed.

    The pre-existing ``workdir-short`` probe validates ``CB_ROOT\\wd``, the root
    used only under ``--keep``. With ``--keep`` OFF (the ``batch-eval`` default)
    the cold verify workdir is an mkdtemp under ``%TEMP%``, which on the testbed
    host is the 8.3 SHORT form ``C:\\Users\\BENCHU~1\\AppData\\Local\\Temp``.
    That short name reached ``-ReportExportPath``, every L2 leg came back
    ``exit_code 3`` -> ``skipped`` -> FAIL, and ``cb batch-eval --references
    all`` scored 0/15.

    ``run_task.new_temp_workdir()`` now auto-heals it, so this probe is
    heal-CONFIRMING: OK (naming the expansion) when the short name expands, WARN
    with the exact TEMP override when it cannot.
    """

    def _check(self, **over):
        return _by_id(envgate.gate(_all_good(**over), "grade"), "temp-8dot3")

    def test_clean_temp_root_is_ok(self):
        c = self._check(temp_root=r"C:\cbtmp", temp_root_canonical=r"C:\cbtmp")
        self.assertEqual(c.status, "OK")
        self.assertEqual(c.fix, "")

    def test_expandable_8dot3_is_ok_and_names_both_spellings(self):
        c = self._check(
            temp_root=r"C:\Users\BENCHU~1\AppData\Local\Temp",
            temp_root_canonical=r"C:\Users\benchuser\AppData\Local\Temp")
        # Auto-healed by the runner -> OK, not a WARN on every single run.
        self.assertEqual(c.status, "OK")
        self.assertIn("BENCHU~1", c.detail)         # what the host reports
        self.assertIn("benchuser", c.detail)        # what the runner will use

    def test_unexpandable_8dot3_warns_with_an_actionable_fix(self):
        short = r"C:\Users\BENCHU~1\AppData\Local\Temp"
        c = self._check(temp_root=short, temp_root_canonical=short)
        self.assertEqual(c.status, "WARN")          # informational, never a hard abort
        self.assertIn("skipped", c.detail)          # the L2 status a user will have seen
        self.assertIn("TEMP", c.fix)
        self.assertIn("TMP", c.fix)   # the fix must name BOTH vars to work

    def test_unresolvable_temp_root_warns(self):
        c = self._check(temp_root=r"C:\Users\BENCHU~1\AppData\Local\Temp",
                        temp_root_canonical="")
        self.assertEqual(c.status, "WARN")
        self.assertIn("<unresolvable>", c.detail)

    def test_8dot3_is_never_flagged_off_windows(self):
        c = self._check(is_windows=False, temp_root="/tmp/PROGRA~1",
                        temp_root_canonical="/tmp/PROGRA~1")
        self.assertEqual(c.status, "OK")

    def test_a_tilde_that_is_not_a_short_name_is_ok(self):
        # '~' without a trailing digit is a backup suffix, not an 8.3 alias.
        c = self._check(temp_root=r"C:\tmp\scratch~bak",
                        temp_root_canonical=r"C:\tmp\scratch~bak")
        self.assertEqual(c.status, "OK")

    def test_probe_runs_in_every_tier(self):
        # It is a grade-tier fact: EVERY eval-family command mints verify
        # workdirs, so no tier may skip it.
        for tier in envgate.TIERS:
            ids = {c.id for c in envgate.gate(_all_good(), tier)}
            self.assertIn("temp-8dot3", ids, tier)

    def test_has_8dot3_component_is_segment_wise(self):
        self.assertTrue(envgate.has_8dot3_component(
            r"C:\Users\BENCHU~1\AppData\Local\Temp"))
        self.assertTrue(envgate.has_8dot3_component("/mnt/c/PROGRA~2/x"))
        self.assertFalse(envgate.has_8dot3_component(r"C:\Users\benchuser\Temp"))
        self.assertFalse(envgate.has_8dot3_component(r"C:\tmp\scratch~bak"))
        self.assertFalse(envgate.has_8dot3_component(""))

    def test_tilde_digit_mid_segment_is_not_an_8dot3_alias(self):
        """A real alias carries its ``~N`` at the END of the name part. A
        directory that merely contains a tilde-digit is an ordinary name and
        must not raise a spurious WARN — the original `~[0-9]` `.search()`
        matched anywhere in the segment (2026-07-25 verification)."""
        self.assertFalse(envgate.has_8dot3_component(r"C:\Users\my~2project\Temp"))
        self.assertFalse(envgate.has_8dot3_component("/home/u/backup~1notes/x"))
        # ...while the genuine trailing form, with and without an extension,
        # still trips it.
        self.assertTrue(envgate.has_8dot3_component(r"C:\Users\me\LOCALS~1.CDE\x"))
        self.assertTrue(envgate.has_8dot3_component(r"D:\ABCDEF~12\y"))


class TestWdDiskProbe(unittest.TestCase):
    """FAILURE-LOG 2026-07-25 — the disk wall, caught BEFORE the token spend.

    Measured across a 21-run stress test: one graded workdir is 5.54 GB (4.72 GB
    of it compiler intermediates), and 24 of them held 121 GB against 128 GB
    free — ~23 evals from a full disk with no CLI path to reclaim, because
    ``cb clean --workdirs`` KEEPS every workdir a ``runs/**/summary.json`` names
    in ``graded_workdir`` and ``cb eval`` has no prune flag. The reclaim
    (``cb clean --workdirs --slim``) ships WITH this probe, per the closure
    doctrine: an incident is CLOSED only once preflight detects its signature.

    Why FAIL and not just WARN at the bottom band: a full disk never presents as
    "disk full". cl.exe fails a write, L1 FAILs, the task scores FAIL — which is
    indistinguishable from a bad agent, for every remaining task in the batch.
    """

    def _check(self, **over):
        return _by_id(envgate.gate(_all_good(**over), "grade"), "wd-disk")

    def test_probe_unavailable_is_ok(self):
        # _all_good() does NOT carry wd_free_gb — the field's None default IS
        # this case, and it is why test_all_ok above still passes untouched.
        # Same contract as ram-headroom: an absent measurement is never a verdict.
        c = self._check()
        self.assertEqual(c.status, "OK")
        self.assertIn("skipped", c.detail)
        self.assertEqual(c.fix, "")

    def test_field_defaults_to_none(self):
        self.assertIsNone(_all_good().wd_free_gb)

    def test_ample_free_space_is_ok(self):
        c = self._check(wd_free_gb=240.0)
        self.assertEqual(c.status, "OK")
        self.assertEqual(c.fix, "")
        # Derived, not hardcoded: WD_PER_EVAL_GB is re-measured whenever the
        # workdir's real size moves (5.54 -> 5.95 on 2026-07-26), and a literal
        # here just breaks the suite on an honest constant update.
        expected = f"{240.0 / envgate.WD_PER_EVAL_GB:.0f} more graded workdirs"
        self.assertIn(expected, c.detail)

    def test_warn_threshold_is_inclusive(self):
        # Exactly at the band edge is still runway, not a warning.
        c = self._check(wd_free_gb=envgate.WD_FREE_WARN_GB)
        self.assertEqual(c.status, "OK")

    def test_low_free_space_warns_but_does_not_block(self):
        c = self._check(wd_free_gb=30.0)
        self.assertEqual(c.status, "WARN")
        self.assertIn("30 GB free", c.detail)
        self.assertIn(r"C:\cb\wd", c.detail)     # WHICH drive is filling up

    def test_fail_threshold_is_inclusive_of_the_warn_band(self):
        # 15 GB exactly is still ~2.7 evals of runway - WARN, not a hard abort.
        c = self._check(wd_free_gb=envgate.WD_FREE_FAIL_GB)
        self.assertEqual(c.status, "WARN")

    def test_critical_free_space_fails(self):
        c = self._check(wd_free_gb=9.0)
        self.assertEqual(c.status, "FAIL")
        self.assertIn("write error", c.detail)   # why a FAIL wall reads as agent-fault
        self.assertNotEqual(c.fix, "")

    def test_fix_names_the_exact_reclaim_command(self):
        for free in (30.0, 9.0):
            c = self._check(wd_free_gb=free)
            self.assertIn("cb clean --workdirs --slim --check", c.fix, free)
            self.assertTrue(c.fix.startswith("cb clean --workdirs --slim --check"),
                            c.fix)

    def test_probe_runs_in_every_tier(self):
        # Every eval-family command mints verify workdirs on the same drive, so
        # no tier may skip it.
        for tier in envgate.TIERS:
            ids = {c.id for c in envgate.gate(_all_good(), tier)}
            self.assertIn("wd-disk", ids, tier)

    def test_bands_are_ordered(self):
        self.assertLess(envgate.WD_FREE_FAIL_GB, envgate.WD_FREE_WARN_GB)


class TestReadWdFreeGb(unittest.TestCase):
    """The live probe half — small enough to test directly, and its whole job is
    to fail SOFT (None) rather than take preflight down measuring free space."""

    def test_measures_an_existing_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            gb = envgate._read_wd_free_gb(Path(td))
        self.assertIsInstance(gb, float)
        self.assertGreater(gb, 0.0)

    def test_walks_up_to_the_first_existing_ancestor(self):
        # <CB_ROOT>\wd is created lazily by the first verify; on a fresh box the
        # probe must still report the DRIVE rather than going "unavailable".
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "wd" / "not-yet" / "deeper"
            self.assertFalse(missing.exists())
            gb = envgate._read_wd_free_gb(missing)
            here = envgate._read_wd_free_gb(Path(td))
        self.assertIsInstance(gb, float)
        self.assertAlmostEqual(gb, here, delta=max(here * 0.05, 1.0))

    def test_a_raising_probe_returns_none_never_raises(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("shutil.disk_usage", side_effect=OSError("boom")):
                self.assertIsNone(envgate._read_wd_free_gb(Path(td)))

    def test_no_existing_ancestor_returns_none(self):
        with mock.patch.object(Path, "exists", return_value=False):
            self.assertIsNone(envgate._read_wd_free_gb(Path(r"C:\cb\wd")))


class TestBaselineTier(unittest.TestCase):
    def test_missing_claude_cli_fails(self):
        c = _by_id(envgate.gate(_all_good(claude_cli=None), "baseline"), "claude-cli")
        self.assertEqual(c.status, "FAIL")

    def test_baseline_has_no_aura_checks(self):
        ids = {c.id for c in envgate.gate(_all_good(), "baseline")}
        self.assertIn("claude-cli", ids)
        self.assertNotIn("aura-creds", ids)


class TestTierForModel(unittest.TestCase):
    def _backend_of(self, slug):
        # Mirror cb._backend_of's contract for the slugs we route.
        if ":" in slug:
            return slug.split(":", 1)[0]
        return slug if slug in ("claude-p", "unreal-mcp", "bare") else "aura-mcp"

    def test_mapping(self):
        f = lambda s: envgate.tier_for_model(s, self._backend_of)  # noqa: E731
        self.assertEqual(f("claude-p"), "baseline")
        self.assertEqual(f("claude-p:claude-opus-4-8"), "baseline")
        self.assertEqual(f("openrouter:deepseek/deepseek-v4"), "baseline")
        self.assertEqual(f("unreal-mcp:sonnet"), "baseline")
        # The separate "aura" tier went with the proprietary rig probes; the
        # aura-mcp arm is refused up front (cb.py) and never reaches the gate,
        # so anything still routed here gates as an ordinary baseline.
        self.assertEqual(f("aura-mcp:opus-4.8"), "baseline")


class TestEnforce(unittest.TestCase):
    def test_skip_flag_short_circuits(self):
        lines = []
        ok = envgate.enforce(None, "grade", lines.append, skip=True)
        self.assertTrue(ok)
        self.assertIn("skipped", lines[0])

    def test_env_var_short_circuits(self):
        lines = []
        with mock.patch.dict(os.environ, {"CB_NO_PREFLIGHT": "1"}):
            ok = envgate.enforce(None, "grade", lines.append)
        self.assertTrue(ok)

    def test_fail_blocks_and_prints_fix(self):
        lines = []
        facts = _all_good(live_coding=2)
        with mock.patch.object(envgate, "real_facts", return_value=facts):
            ok = envgate.enforce(object(), "grade", lines.append)
        self.assertFalse(ok)
        text = "\n".join(lines)
        self.assertIn("live-coding", text)
        self.assertIn("fix:", text)
        self.assertIn("BEFORE any build/token spend", text)

    def test_warn_does_not_block(self):
        facts = _all_good(ram_pct=95.0)
        with mock.patch.object(envgate, "real_facts", return_value=facts):
            ok = envgate.enforce(object(), "grade", lambda s: None)
        self.assertTrue(ok)

    def test_gate_exception_fails_open(self):
        lines = []
        with mock.patch.object(envgate, "real_facts", side_effect=OSError("boom")):
            ok = envgate.enforce(object(), "grade", lines.append)
        self.assertTrue(ok)
        self.assertIn("continuing", "\n".join(lines))


class TestScanStartupMaps(unittest.TestCase):
    def test_scan_flags_task_maps_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / "GoodSub" / "Config"
            good.mkdir(parents=True)
            (good / "DefaultEngine.ini").write_text(
                "[/Script/EngineSettings.GameMapsSettings]\n"
                "GameDefaultMap=/Engine/Maps/Entry.Entry\n", encoding="utf-8")
            bad = root / "BadSub" / "Config"
            bad.mkdir(parents=True)
            (bad / "DefaultEngine.ini").write_text(
                "[/Script/EngineSettings.GameMapsSettings]\n"
                "GameDefaultMap=/Game/Maps/L_SanityTask.L_SanityTask\n"
                "EditorStartupMap=/Engine/Maps/Entry.Entry\n", encoding="utf-8")
            rows = envgate._scan_startup_maps(root)
        self.assertEqual(len(rows), 1)
        self.assertIn("BadSub", rows[0])
        self.assertIn("GameDefaultMap", rows[0])



class TestCommitHeadroomHardFloor(unittest.TestCase):
    """Owner mandate 2026-08-07, after the 70/84 GB night: two hard-stopped
    benches skipped teardown, the accumulated vercel/client leak + orphaned
    editors exhausted the commit charge, and drive editors died silently. The
    hard floor (default 10 GB free commit, env CB_COMMIT_FLOOR_GB) is the ONLY
    FAIL route of the commit-headroom probe: below it a build/bench is
    guaranteed to record machine deaths as agent FAILs, so refusing pre-spend
    is the cheap outcome. WARN below 2x floor. Unmeasured never FAILs (the
    standing absent-measurement contract)."""

    def _check(self, tier="grade", **over):
        return _by_id(envgate.gate(_all_good(**over), tier), "commit-headroom")

    def test_below_floor_FAILS_and_names_cb_down(self):
        c = self._check(commit_free_gb=8.0, commit_pct=83.0)
        self.assertEqual(c.status, "FAIL")
        self.assertIn("8.0 GB", c.detail)
        self.assertIn("C3859", c.detail)
        self.assertIn("cb down", c.fix)              # the remedy of record
        # The "~20 GB / vercel :3000" facts named the private stack that this
        # release does not ship; the remedy and the knob are the contract.
        self.assertIn("CB_COMMIT_FLOOR_GB", c.fix)   # the tuning knob

    def test_floor_fails_on_the_whole_eval_family(self):
        # The row is tier-unconditional, so every tier gates.
        for tier in envgate.TIERS:
            self.assertEqual(
                self._check(tier, commit_free_gb=3.0).status, "FAIL", tier)

    def test_warn_band_below_2x_floor(self):
        c = self._check(commit_free_gb=15.0, commit_pct=50.0)
        self.assertEqual(c.status, "WARN")
        self.assertIn("cb down", c.fix)

    def test_comfortable_headroom_is_ok(self):
        c = self._check(commit_free_gb=25.0, commit_pct=50.0)
        self.assertEqual(c.status, "OK")
        self.assertIn("25.0 GB", c.detail)

    def test_env_resolved_floor_fact_wins(self):
        # real_facts resolves CB_COMMIT_FLOOR_GB into the Facts field so the
        # gate stays pure; a 4 GB floor makes 5 GB a WARN (< 2x) not a FAIL.
        c = self._check(commit_free_gb=5.0, commit_pct=50.0,
                        commit_floor_gb=4.0)
        self.assertEqual(c.status, "WARN")
        c = self._check(commit_free_gb=3.0, commit_pct=50.0,
                        commit_floor_gb=4.0)
        self.assertEqual(c.status, "FAIL")

    def test_unmeasured_free_commit_never_fails(self):
        c = self._check(commit_free_gb=None, commit_pct=50.0)
        self.assertEqual(c.status, "OK")

    def test_commit_floor_gb_env_parsing(self):
        self.assertEqual(envgate.commit_floor_gb(env={}), envgate.COMMIT_FLOOR_GB)
        self.assertEqual(
            envgate.commit_floor_gb(env={"CB_COMMIT_FLOOR_GB": "24"}), 24.0)
        self.assertEqual(
            envgate.commit_floor_gb(env={"CB_COMMIT_FLOOR_GB": "6 # tuned"}), 6.0)
        for bad in ("abc", "-3", "0", ""):
            self.assertEqual(
                envgate.commit_floor_gb(env={"CB_COMMIT_FLOOR_GB": bad}),
                envgate.COMMIT_FLOOR_GB, bad)


class TestRigProvenanceProbe(unittest.TestCase):
    """FAILURE-LOG 2026-08-04 — a stale GLOBAL editable install made bare
    ``py -3 -m aura_rig.cb`` resolve aura_rig from a DIFFERENT clone
    (``C:\\Users\\hello\\cbtest``): the wrong clone's code ran, presenting as
    confusing import errors rather than as "wrong repo". A mismatch is a
    BLOCKER because every check after it (and the run itself) would exercise
    the OTHER clone's code.
    """

    def _check(self, **over):
        return _by_id(envgate.gate(_all_good(**over), "grade"), "rig-provenance")

    def test_matching_roots_is_ok(self):
        c = self._check(rig_pkg_root=r"C:\gh\craftbench",
                        cmd_repo_root=r"C:\gh\craftbench")
        self.assertEqual(c.status, "OK")
        self.assertEqual(c.fix, "")

    def test_mismatch_blocks_with_the_exact_fix(self):
        c = self._check(rig_pkg_root=r"C:\Users\hello\cbtest",
                        cmd_repo_root=r"C:\gh\craftbench")
        self.assertEqual(c.status, "FAIL")
        self.assertIn("cbtest", c.detail)           # WHICH clone really runs
        self.assertIn(r"C:\gh\craftbench", c.detail)
        self.assertIn("pip install -e tools/run-agent", c.fix)
        self.assertIn("./cb", c.fix)                # the no-install shim route

    def test_comparison_ignores_case_and_separator_spelling(self):
        # Two spellings of ONE clone must never read as a mismatch — a false
        # BLOCKER here stops a healthy run over path cosmetics.
        c = self._check(rig_pkg_root=r"C:\GH\CraftBench",
                        cmd_repo_root="c:/gh/craftbench/")
        self.assertEqual(c.status, "OK")

    def test_unresolvable_package_root_is_ok_skipped(self):
        # An odd/absent aura_rig.__file__ (frozen or namespace import) is an
        # absent measurement, never a verdict.
        c = self._check(rig_pkg_root=None, cmd_repo_root=r"C:\gh\craftbench")
        self.assertEqual(c.status, "OK")
        self.assertIn("skipped", c.detail)

    def test_field_defaults_are_none_and_ok(self):
        # _all_good() does NOT carry the roots — the None defaults ARE the
        # skip case, which is why test_all_ok above still passes untouched.
        self.assertIsNone(_all_good().rig_pkg_root)
        self.assertIsNone(_all_good().cmd_repo_root)
        self.assertEqual(self._check().status, "OK")

    def test_probe_runs_in_every_tier(self):
        # Wrong code is wrong for a token-free grade too — no tier may skip it.
        for tier in envgate.TIERS:
            ids = {c.id for c in envgate.gate(_all_good(), tier)}
            self.assertIn("rig-provenance", ids, tier)


class TestReadRigRepoRoot(unittest.TestCase):
    """The live probe half — derives the repo root of the aura_rig THIS test
    process imported, so it must land on a dir that actually holds the rig."""

    def test_derives_the_checkout_holding_the_running_package(self):
        root = envgate._read_rig_repo_root()
        self.assertIsNotNone(root)
        self.assertTrue(
            (Path(root) / "tools" / "run-agent" / "aura_rig" / "cb.py").is_file(),
            root)


class TestReadCmdRepoRoot(unittest.TestCase):
    """CWD-anchored on purpose: StackPaths.craftbench derives from the same
    hijacked ``__file__`` as the package, so in the incident ctx and package
    agreed on the WRONG clone — the operator's checkout is the only honest
    anchor."""

    def _in_dir(self, d, ctx_root):
        old = os.getcwd()
        os.chdir(d)
        try:
            return envgate._read_cmd_repo_root(ctx_root)
        finally:
            os.chdir(old)

    def test_cwd_inside_a_checkout_wins_over_ctx(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            clone = Path(td) / "clone"
            marker = clone / "tools" / "run-agent" / "aura_rig"
            marker.mkdir(parents=True)
            (marker / "cb.py").write_text("", encoding="utf-8")
            deep = clone / "tasks" / "somewhere"
            deep.mkdir(parents=True)
            got = self._in_dir(deep, Path(td) / "elsewhere")
            self.assertEqual(Path(got).resolve(), clone.resolve())

    def test_falls_back_to_ctx_root_outside_any_checkout(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            got = self._in_dir(td, Path(td) / "ctxroot")
            self.assertEqual(Path(got).name, "ctxroot")


