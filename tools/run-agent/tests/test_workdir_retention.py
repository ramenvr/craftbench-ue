"""aura_rig.workdir_retention — the retention POLICY layer (mode precedence,
the refusals, the CB_PREVIEW downgrade, and the returned dict shape).

Fully offline and, deliberately, fully DECOUPLED from the deletion half: the
``fs_cleanup`` seam (``workdir_retention._fs_cleanup``) is replaced with a fake
namespace in every test, so nothing here imports tools/verify-single, and no
test can ever reach the real ``C:\\cb\\wd``. ``paths.wd_root`` is patched to a
tempdir for the same reason.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import workdir_retention as wr  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes for the fs_cleanup seam                                                #
# --------------------------------------------------------------------------- #

class _Recorder:
    """A stand-in deleter that records its calls. Reclaims nothing on disk —
    the point is to prove WHETHER policy called a deleter, not to re-test
    fs_cleanup (whose real module is authored on the other side of the seam)."""

    def __init__(self, ret=4_720_000_000, raises=None):
        self.calls: list = []
        self.ret = ret
        self.raises = raises

    def __call__(self, workdir, log=None):
        self.calls.append(Path(workdir))
        if self.raises is not None:
            raise self.raises
        return self.ret


def _real_rmtree(workdir, log=None):
    """A robust_rmtree stand-in that actually removes the tree, so the "none"
    leg's before/after byte measurement has something real to measure."""
    shutil.rmtree(str(workdir), ignore_errors=True)
    return True


def _slim_stats(reclaimed_bytes=0, refused=False):
    """The shape fs_cleanup.slim_workdir really returns (a SlimStats dataclass),
    modelled rather than imported — see the module docstring on independence."""
    return types.SimpleNamespace(reclaimed_bytes=reclaimed_bytes,
                                 deleted_paths=1, elapsed_s=0.0, notes=[],
                                 refused=refused, project_dir=None)


def _cleanup_ns(**members):
    """A fake ``fs_cleanup`` module namespace. Members are opt-in so a test can
    model the checkout where ``slim_workdir`` does not exist yet."""
    return types.SimpleNamespace(**members)


class _Base(unittest.TestCase):
    """Clears every env the resolver reads (host config must not leak in) and
    builds a tmp wd-root with one populated workdir under it."""

    _ENV = ("CB_WORKDIR_RETENTION", "CB_PREVIEW", "CRAFTBENCH_WD_ROOT", "CB_ROOT")

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in self._ENV}
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.wd_root = self.root / "wd"
        self.wd = self.wd_root / "abc123def0"
        (self.wd / "Proj" / "Intermediate" / "Build" / "Win64" / "x64").mkdir(parents=True)
        (self.wd / "Proj" / "Binaries" / "Win64").mkdir(parents=True)
        (self.wd / "out").mkdir(parents=True)
        (self.wd / "Proj" / "Intermediate" / "Build" / "Win64" / "x64" / "a.obj"
         ).write_bytes(b"o" * 4096)
        (self.wd / "Proj" / "Binaries" / "Win64" / "p.dll").write_bytes(b"d" * 512)
        (self.wd / "out" / "report.json").write_text("{}", encoding="utf-8")
        self._patch_wd_root(self.wd_root)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _patch_wd_root(self, root: Path):
        p = mock.patch.object(wr.cb_paths, "wd_root", lambda: root)
        p.start()
        self.addCleanup(p.stop)

    def _patch_cleanup(self, ns):
        p = mock.patch.object(wr, "_fs_cleanup", lambda: ns)
        p.start()
        self.addCleanup(p.stop)

    @staticmethod
    def _pass_report():
        return {"layers": {"L1": {"status": "pass"}, "L2": {"status": "pass"}},
                "overall": "pass"}

    @staticmethod
    def _silent(*_a, **_k):
        return None


# --------------------------------------------------------------------------- #
# resolve_mode — precedence + the bad-value fallback                           #
# --------------------------------------------------------------------------- #

class TestResolveMode(_Base):
    def test_default_is_slim(self):
        # The maintainer decision of 2026-07-25: full retention is what filled
        # 121 GB, so the DEFAULT with nothing set at all must be "slim".
        self.assertEqual(wr.DEFAULT_MODE, "slim")
        self.assertEqual(wr.resolve_mode(log=self._silent), "slim")

    def test_env_beats_default(self):
        os.environ["CB_WORKDIR_RETENTION"] = "full"
        self.assertEqual(wr.resolve_mode(log=self._silent), "full")

    def test_explicit_beats_env(self):
        os.environ["CB_WORKDIR_RETENTION"] = "none"
        self.assertEqual(wr.resolve_mode("full", log=self._silent), "full")

    def test_explicit_beats_env_both_directions(self):
        os.environ["CB_WORKDIR_RETENTION"] = "full"
        self.assertEqual(wr.resolve_mode("none", log=self._silent), "none")

    def test_value_is_normalized(self):
        self.assertEqual(wr.resolve_mode("  SLIM \n", log=self._silent), "slim")

    def test_bad_env_falls_back_to_slim_with_a_warning(self):
        os.environ["CB_WORKDIR_RETENTION"] = "lean"   # the name-collision typo
        logged = []
        self.assertEqual(wr.resolve_mode(log=logged.append), "slim")
        self.assertTrue(any("lean" in m and "CB_WORKDIR_RETENTION" in m
                            for m in logged), logged)

    def test_bad_explicit_falls_back_to_slim_without_consulting_env(self):
        os.environ["CB_WORKDIR_RETENTION"] = "full"
        logged = []
        self.assertEqual(wr.resolve_mode("nope", log=logged.append), "slim")
        self.assertTrue(any("nope" in m for m in logged), logged)

    def test_empty_env_reads_as_unset(self):
        # An exported-but-empty var is routine on Windows/CI — it must fall
        # through to the default, not trip the unrecognised-value warning.
        os.environ["CB_WORKDIR_RETENTION"] = "   "
        logged = []
        self.assertEqual(wr.resolve_mode(log=logged.append), "slim")
        self.assertEqual(logged, [])

    def test_modes_tuple_is_the_contract(self):
        self.assertEqual(wr.MODES, ("full", "slim", "none"))


# --------------------------------------------------------------------------- #
# apply — the returned dict shape                                              #
# --------------------------------------------------------------------------- #

class TestApplyShape(_Base):
    def test_slim_happy_path_returns_exactly_the_three_keys(self):
        slim = _Recorder(ret=4_720_000_000)
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(set(out), {"mode", "reclaimed_bytes", "elapsed_s"})
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(out["reclaimed_bytes"], 4_720_000_000)
        self.assertIsInstance(out["reclaimed_bytes"], int)
        self.assertIsInstance(out["elapsed_s"], float)
        self.assertGreaterEqual(out["elapsed_s"], 0.0)
        self.assertEqual(slim.calls, [self.wd])

    def test_full_is_a_no_op_that_touches_no_deleter(self):
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim,
                                        robust_rmtree=_Recorder()))
        out = wr.apply(self.wd, "full", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reclaimed_bytes"], 0)
        self.assertNotIn("reason", out)
        self.assertEqual(slim.calls, [])
        self.assertTrue(self.wd.is_dir())

    def test_mode_none_argument_resolves_instead_of_silently_doing_nothing(self):
        os.environ["CB_WORKDIR_RETENTION"] = "slim"
        slim = _Recorder(ret=1)
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, None, report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(slim.calls, [self.wd])

    def test_delegate_without_a_log_kwarg_is_still_called(self):
        seen = []

        def _slim_no_log(workdir):
            seen.append(Path(workdir))
            return 77

        self._patch_cleanup(_cleanup_ns(slim_workdir=_slim_no_log))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["reclaimed_bytes"], 77)
        self.assertEqual(seen, [self.wd])

    def test_delegate_dict_return_is_accepted(self):
        self._patch_cleanup(_cleanup_ns(
            slim_workdir=lambda wd, log=None: {"reclaimed_bytes": 4_720_000_000}))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["reclaimed_bytes"], 4_720_000_000)

    def test_slimstats_shaped_return_is_unwrapped(self):
        # The REAL fs_cleanup.slim_workdir returns a SlimStats dataclass, not a
        # number. Modelled here (not imported) so this suite stays independent
        # of the verifier package.
        self._patch_cleanup(_cleanup_ns(
            slim_workdir=lambda wd, log=None: _slim_stats(4_720_000_000)))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(out["reclaimed_bytes"], 4_720_000_000)

    def test_success_is_logged_with_the_reclaimed_size(self):
        self._patch_cleanup(_cleanup_ns(
            slim_workdir=lambda wd, log=None: 4_720_000_000))
        logged = []
        wr.apply(self.wd, "slim", report=self._pass_report(), log=logged.append)
        self.assertTrue(any("4.72 GB" in m and "slim" in m for m in logged),
                        logged)


# --------------------------------------------------------------------------- #
# apply — the refusals (every one stays "full" and says why)                    #
# --------------------------------------------------------------------------- #

class TestApplyRefusals(_Base):
    def _assert_refused(self, out, reason, slim):
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reclaimed_bytes"], 0)
        self.assertEqual(out["reason"], reason)
        self.assertEqual(out["requested"], "slim")
        self.assertIsInstance(out["elapsed_s"], float)
        self.assertEqual(slim.calls, [], "a refusal must call no deleter")

    def test_refuses_when_warm(self):
        # A warm slot's Intermediate/+Binaries/ ARE the path-bound UBT cache
        # (warm_cache.py); slimming it would silently kill the 5x L1 speed-up.
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim", report=self._pass_report(), warm=True,
                       log=self._silent)
        self._assert_refused(out, "warm_cache_pool", slim)
        self.assertTrue(self.wd.is_dir())

    def test_refuses_when_report_is_none(self):
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim", report=None, log=self._silent)
        self._assert_refused(out, "no_report", slim)

    def test_refuses_when_l1_failed(self):
        # A BROKEN BUILD is exactly when the .obj tree is the evidence.
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim",
                       report={"layers": {"L1": {"status": "fail"}}},
                       log=self._silent)
        self._assert_refused(out, "l1_fail", slim)

    def test_refuses_when_l1_skipped(self):
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim",
                       report={"layers": {"L1": {"status": "skipped"}}},
                       log=self._silent)
        self._assert_refused(out, "l1_skipped", slim)

    def test_refuses_when_l1_absent_from_the_report(self):
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim", report={"layers": {"L2": {"status": "pass"}}},
                       log=self._silent)
        self._assert_refused(out, "l1_missing", slim)

    def test_refuses_when_l2_failed_but_l1_passed_is_allowed(self):
        # Only L1 gates retention: an L1-pass/L2-fail run built fine, so its
        # .obj tree is not the evidence anyone needs.
        slim = _Recorder(ret=10)
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd, "slim",
                       report={"layers": {"L1": {"status": "pass"},
                                          "L2": {"status": "fail"}}},
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(slim.calls, [self.wd])

    def test_refuses_outside_wd_root(self):
        outside = self.root / "elsewhere" / "someproject"
        outside.mkdir(parents=True)
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(outside, "slim", report=self._pass_report(),
                       log=self._silent)
        self._assert_refused(out, "outside_wd_root", slim)
        self.assertTrue(outside.is_dir())

    def test_refuses_the_wd_root_itself(self):
        # The root is the POOL, not a run workdir — a strict-descendant test.
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        out = wr.apply(self.wd_root, "slim", report=self._pass_report(),
                       log=self._silent)
        self._assert_refused(out, "outside_wd_root", slim)
        self.assertTrue(self.wd.is_dir())

    def test_refuses_when_workdir_is_missing_or_not_a_dir(self):
        slim = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim))
        gone = self.wd_root / "never-existed"
        afile = self.wd_root / "a-file"
        afile.write_text("x", encoding="utf-8")
        for target in (None, "", gone, afile):
            out = wr.apply(target, "slim", report=self._pass_report(),
                           log=self._silent)
            self._assert_refused(out, "workdir_missing", slim)

    def test_refuses_when_the_slim_delegate_does_not_exist_yet(self):
        # fs_cleanup.slim_workdir ships separately; a checkout without it must
        # keep the workdir, never fall through to a whole-tree wipe.
        self._patch_cleanup(_cleanup_ns(robust_rmtree=_real_rmtree))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "slim_delegate_unavailable")
        self.assertEqual(out["requested"], "slim")
        self.assertTrue(self.wd.is_dir())

    def test_a_delegate_that_refuses_reports_full_not_a_zero_byte_slim(self):
        # fs_cleanup.slim_workdir runs its OWN wd-root gate; when ITS gate says
        # no, nothing left the disk and the honest mode is "full".
        self._patch_cleanup(_cleanup_ns(
            slim_workdir=lambda wd, log=None: _slim_stats(0, refused=True)))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "slim_delegate_refused")
        self.assertEqual(out["requested"], "slim")
        self.assertEqual(out["reclaimed_bytes"], 0)

    def test_a_raising_delegate_never_escapes(self):
        self._patch_cleanup(_cleanup_ns(
            slim_workdir=_Recorder(raises=OSError("WinError 32"))))
        logged = []
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=logged.append)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "delete_failed")
        self.assertIn("WinError 32", out["error"])
        self.assertTrue(any("WARN" in m for m in logged), logged)


# --------------------------------------------------------------------------- #
# apply — mode "none" and the CB_PREVIEW downgrade                             #
# --------------------------------------------------------------------------- #

class TestApplyNoneMode(_Base):
    def test_none_removes_the_whole_tree_and_reports_the_bytes(self):
        self._patch_cleanup(_cleanup_ns(robust_rmtree=_real_rmtree,
                                        slim_workdir=_Recorder()))
        out = wr.apply(self.wd, "none", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "none")
        self.assertNotIn("reason", out)
        self.assertEqual(out["reclaimed_bytes"], 4096 + 512 + 2)
        self.assertFalse(self.wd.exists())

    def test_cb_preview_downgrades_none_to_slim(self):
        # cb.py::_maybe_chain_postrun_preview re-opens the graded project after
        # the eval returns — "none" would delete what it is about to photograph.
        os.environ["CB_PREVIEW"] = "1"
        slim = _Recorder(ret=4_720_000_000)
        rm = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim, robust_rmtree=rm))
        out = wr.apply(self.wd, "none", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(out["requested"], "none")
        self.assertEqual(out["reason"], "cb_preview_needs_launchable_project")
        self.assertEqual(out["reclaimed_bytes"], 4_720_000_000)
        self.assertEqual(slim.calls, [self.wd])
        self.assertEqual(rm.calls, [], "the tree must survive for the preview")
        self.assertTrue(self.wd.is_dir())

    def test_cb_preview_leaves_slim_and_full_alone(self):
        os.environ["CB_PREVIEW"] = "1"
        slim = _Recorder(ret=5)
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim,
                                        robust_rmtree=_Recorder()))
        out = wr.apply(self.wd, "slim", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertNotIn("reason", out)
        self.assertNotIn("requested", out)

        out = wr.apply(self.wd, "full", report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "full")
        self.assertNotIn("reason", out)

    def test_cb_preview_downgrade_still_obeys_the_refusals(self):
        os.environ["CB_PREVIEW"] = "1"
        slim = _Recorder()
        rm = _Recorder()
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim, robust_rmtree=rm))
        out = wr.apply(self.wd, "none", report=self._pass_report(), warm=True,
                       log=self._silent)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "warm_cache_pool")
        self.assertEqual(out["requested"], "none")
        self.assertEqual(slim.calls, [])
        self.assertEqual(rm.calls, [])

    def test_none_resolved_from_env_downgrades_too(self):
        os.environ["CB_WORKDIR_RETENTION"] = "none"
        os.environ["CB_PREVIEW"] = "1"
        slim = _Recorder(ret=3)
        self._patch_cleanup(_cleanup_ns(slim_workdir=slim,
                                        robust_rmtree=_Recorder()))
        out = wr.apply(self.wd, None, report=self._pass_report(),
                       log=self._silent)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(out["requested"], "none")


if __name__ == "__main__":
    unittest.main()
