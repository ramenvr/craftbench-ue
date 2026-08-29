"""aura_rig.workdir_retention <-> tools/verify-single/fs_cleanup — the REAL seam.

tests/test_workdir_retention.py covers the policy half with the ``_fs_cleanup``
seam faked out, which is right for testing refusals but leaves the single most
likely way this feature breaks in production completely unasserted: **the two
halves live in different packages**. The policy lives in tools/run-agent
(``aura_rig``), the deleter lives in tools/verify-single (a bare module dir that
is NOT on sys.path when the rig runs), and they reach each other through two
lazy imports pointing in OPPOSITE directions —

    workdir_retention._fs_cleanup()      rig      -> verify-single/fs_cleanup
    fs_cleanup._resolve_allow_root()     verifier -> aura_rig.paths.wd_root

Either one silently degrading is invisible to a mocked suite and nearly
invisible in production: ``apply`` returns ``reason="slim_delegate_unavailable"``
or ``SlimStats.refused``, both of which look like an ordinary, correct refusal
while 5.91 GB per eval keeps accumulating (measured 2026-07-25: 24 workdirs,
129 GB, ~23 evals to a full disk). So everything below runs the ACTUAL modules
against a real fixture tree with nothing patched.

Nothing here can reach ``C:\\cb\\wd``: every case points ``CRAFTBENCH_WD_ROOT``
(paths.wd_root's documented override) at a fresh tempdir, which is also what
makes the reverse-direction import observable — a fixture workdir only gets
slimmed if fs_cleanup genuinely resolved the rig's wd_root and agreed the path
is in-root.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import workdir_retention as wr  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
RUN_AGENT = REPO / "tools" / "run-agent"
FS_CLEANUP = REPO / "tools" / "verify-single" / "fs_cleanup.py"

# Sizes big enough that a byte count can be asserted exactly, small enough that
# the fixture writes instantly. The RATIOS mirror the 2026-07-25 measurement of
# C:\cb\wd\08085611c8 (x64 4.931 GB / CachedAssetRegistry 0.124 GB / Binaries
# debug 0.853 GB), so a rule that reclaimed only the small targets would still
# read as an obvious under-count here.
_OBJ_BYTES = 4000
_REG_BYTES = 100
_PDB_BYTES = 800
_KEEP_BYTES = 200


def _write(p: Path, n: int) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * n)


class _RealSeamCase(unittest.TestCase):
    """A tempdir wd-root plus one fixture workdir shaped like a real one."""

    # Every one of these re-aims retention, so a developer's exported shell var
    # must not be able to decide what this suite proves.
    _ENV = ("CRAFTBENCH_WD_ROOT", "CB_ROOT", "CB_WORKDIR_RETENTION", "CB_PREVIEW")

    def setUp(self) -> None:
        self._saved = {k: os.environ.pop(k, None) for k in self._ENV}
        self.addCleanup(self._restore_env)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.wd_root = Path(td.name) / "wd"
        # The REAL override, not a mock.patch: fs_cleanup resolves the root
        # through its own `from aura_rig.paths import wd_root`, and only an env
        # var is visible to both sides of the seam at once.
        os.environ["CRAFTBENCH_WD_ROOT"] = str(self.wd_root)
        self.wd = self.wd_root / "abc123def0"
        self.proj = self.wd / "CraftBenchTemplate"
        self._build_fixture()

    def _restore_env(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _build_fixture(self) -> None:
        _write(self.proj / "CraftBenchTemplate.uproject", _KEEP_BYTES)
        # DELETE targets
        _write(self.proj / "Intermediate/Build/Win64/x64/Module.Core.cpp.obj",
               _OBJ_BYTES)
        _write(self.proj / "Intermediate/CachedAssetRegistry/CachedAssetRegistry.bin",
               _REG_BYTES)
        _write(self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTemplate.pdb",
               _PDB_BYTES)
        # KEEP targets — one per KEEP reason in fs_cleanup's block comment
        _write(self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTemplate.dll",
               _KEEP_BYTES)
        _write(self.proj / "Intermediate/Build/Win64/UnrealEditor/Inc/Foo.generated.h",
               _KEEP_BYTES)
        _write(self.proj / "DerivedDataCache/ddc.udd", _KEEP_BYTES)
        _write(self.proj / "Source/Craft/Craft.cpp", _KEEP_BYTES)
        _write(self.wd / "out/report.json", _KEEP_BYTES)

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _pass_report() -> dict:
        return {"layers": {"L1": {"status": "pass"}, "L2": {"status": "pass"}}}

    def _assert_kept_bytes_survive(self) -> None:
        for rel in ("Binaries/Win64/UnrealEditor-CraftBenchTemplate.dll",
                    "Intermediate/Build/Win64/UnrealEditor/Inc/Foo.generated.h",
                    "DerivedDataCache/ddc.udd",
                    "Source/Craft/Craft.cpp",
                    "CraftBenchTemplate.uproject"):
            self.assertTrue((self.proj / rel).is_file(), f"slim ate {rel}")
        self.assertTrue((self.wd / "out" / "report.json").is_file(),
                        "slim ate out/report.json — the only diagnostic bytes")


class TestTheLazyImportResolves(_RealSeamCase):
    """rig -> verifier. The import that, if it fails, turns every reclaim into a
    polite ``slim_delegate_unavailable`` nobody reads."""

    def test_fs_cleanup_resolves_to_the_real_verify_single_module(self):
        mod = wr._fs_cleanup()
        self.assertEqual(Path(mod.__file__).resolve(), FS_CLEANUP.resolve())
        self.assertTrue(callable(getattr(mod, "slim_workdir", None)),
                        "apply() reads slim_workdir off this module by name")
        self.assertTrue(callable(getattr(mod, "robust_rmtree", None)),
                        'mode "none" reads robust_rmtree off this module by name')

    def test_the_delegate_signature_is_the_one_apply_calls_with(self):
        # apply() -> _call_delegate passes `log=` only when the parameter exists.
        # If slim_workdir ever loses it the call still works, but proving the
        # kwarg is really there is what keeps the log line from quietly dying.
        import inspect
        params = inspect.signature(wr._fs_cleanup().slim_workdir).parameters
        self.assertIn("log", params)
        self.assertIn("allow_root", params)   # cb clean --slim passes this one

    def test_verify_single_dir_points_at_the_module_dir(self):
        # Path(__file__).parents[2] is an offset into the repo layout — an
        # arithmetic slip here is a one-character bug with a silent-refusal
        # symptom, so it gets asserted rather than assumed.
        self.assertEqual(wr.VERIFY_SINGLE_DIR.resolve(),
                         FS_CLEANUP.parent.resolve())

    def test_the_import_works_in_a_process_that_never_bridged_sys_path(self):
        """The load-bearing one.

        In THIS process a dozen other modules have already run — graded_scratch
        inserts tools/verify-single into sys.path at import time — so an
        in-process check can pass for somebody else's reason. The subprocess
        below scrubs the bridge back out (drops verify-single from sys.path,
        evicts fs_cleanup from sys.modules) after importing the rig and only
        then calls ``_fs_cleanup()``, so the sys.path insert being asserted is
        provably workdir_retention's own."""
        prog = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from aura_rig import workdir_retention as wr
# Undo any bridge another rig module may have laid down, so what follows can
# only succeed through _fs_cleanup's own sys.path insert.
sys.modules.pop("fs_cleanup", None)
sys.path[:] = [p for p in sys.path if "verify-single" not in p]
pre = True
try:
    import fs_cleanup            # must NOT be reachable yet
    pre = False
except ImportError:
    pass
m = wr._fs_cleanup()
print(json.dumps({"unreachable_before": pre, "file": m.__file__,
                  "slim": callable(getattr(m, "slim_workdir", None))}))
"""
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        cp = subprocess.run([sys.executable, "-c", prog, str(RUN_AGENT)],
                            cwd=str(Path(tempfile.gettempdir())),
                            capture_output=True, text=True, env=env)
        self.assertEqual(cp.returncode, 0,
                         f"the cross-package import raised:\n{cp.stderr}")
        got = json.loads(cp.stdout.strip().splitlines()[-1])
        self.assertTrue(got["unreachable_before"],
                        "fs_cleanup was already importable — this test proved "
                        "nothing; the scrub above needs fixing")
        self.assertEqual(Path(got["file"]).resolve(), FS_CLEANUP.resolve())
        self.assertTrue(got["slim"])


class TestApplyAgainstTheRealDeleter(_RealSeamCase):
    """End to end with NOTHING patched: real resolve_mode, real refusals, real
    fs_cleanup, real files on disk."""

    def test_slim_drops_the_intermediates_and_keeps_the_evidence(self):
        out = wr.apply(self.wd, "slim", report=self._pass_report(), log=lambda _m: None)
        self.assertEqual(out["mode"], "slim")
        self.assertNotIn("reason", out)
        self.assertFalse((self.proj / "Intermediate/Build/Win64/x64").exists())
        self.assertFalse((self.proj / "Intermediate/CachedAssetRegistry").exists())
        self.assertFalse(
            (self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTemplate.pdb").exists())
        self._assert_kept_bytes_survive()
        # Exact, not ">0": a policy layer that unwrapped SlimStats wrongly (it is
        # a dataclass, not an int) would still report a plausible-looking number.
        self.assertEqual(out["reclaimed_bytes"],
                         _OBJ_BYTES + _REG_BYTES + _PDB_BYTES)
        self.assertTrue((self.wd).is_dir(), "slim must keep the workdir itself")

    def test_the_reverse_import_gate_lets_an_in_root_workdir_through(self):
        """fs_cleanup runs its OWN wd-root gate via ``from aura_rig.paths import
        wd_root`` — the verifier importing the RIG, the opposite direction from
        the test above. apply() passes no ``allow_root=``, so if that import
        degraded, SlimStats.refused would come back True, apply() would map it
        to reason ``slim_delegate_refused``, and nothing would ever be
        reclaimed on a correctly configured box."""
        out = wr.apply(self.wd, "slim", report=self._pass_report(), log=lambda _m: None)
        self.assertNotEqual(out.get("reason"), "slim_delegate_refused")
        self.assertGreater(out["reclaimed_bytes"], 0)

    def test_slim_is_the_default_with_no_env_var_set(self):
        self.assertIsNone(os.environ.get(wr.ENV_VAR))
        self.assertEqual(wr.resolve_mode(), "slim")
        # ...and the default is what an unspecified caller actually GETS, not
        # just what resolve_mode says in isolation.
        out = wr.apply(self.wd, None, report=self._pass_report(), log=lambda _m: None)
        self.assertEqual(out["mode"], "slim")
        self.assertFalse((self.proj / "Intermediate/Build/Win64/x64").exists())

    def test_a_failed_l1_keeps_every_byte(self):
        report = {"layers": {"L1": {"status": "fail"}}}
        out = wr.apply(self.wd, "slim", report=report, log=lambda _m: None)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "l1_fail")
        self.assertEqual(out["reclaimed_bytes"], 0)
        # A broken build is exactly when a human wants the .obj tree.
        self.assertTrue(
            (self.proj / "Intermediate/Build/Win64/x64/Module.Core.cpp.obj").is_file())

    def test_a_workdir_outside_the_wd_root_survives_both_gates(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        stray = Path(td.name) / "not-a-workdir"
        _write(stray / "P/P.uproject", _KEEP_BYTES)
        _write(stray / "P/Intermediate/Build/Win64/x64/a.obj", _OBJ_BYTES)
        out = wr.apply(stray, "slim", report=self._pass_report(), log=lambda _m: None)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["reason"], "outside_wd_root")
        self.assertTrue((stray / "P/Intermediate/Build/Win64/x64/a.obj").is_file())

    def test_a_warm_slot_is_never_slimmed_through_the_real_deleter(self):
        # The warm slot's Intermediate/+Binaries ARE the path-bound UBT cache;
        # slimming it costs every later verify the 5x L1. warm= is the one fact
        # only the call site holds, so it gets an end-to-end assertion too.
        out = wr.apply(self.wd, "slim", report=self._pass_report(), warm=True,
                       log=lambda _m: None)
        self.assertEqual(out["reason"], "warm_cache_pool")
        self.assertTrue(
            (self.proj / "Intermediate/Build/Win64/x64/Module.Core.cpp.obj").is_file())

    def test_a_second_slim_pass_is_a_no_op(self):
        first = wr.apply(self.wd, "slim", report=self._pass_report(), log=lambda _m: None)
        second = wr.apply(self.wd, "slim", report=self._pass_report(), log=lambda _m: None)
        self.assertGreater(first["reclaimed_bytes"], 0)
        self.assertEqual(second["reclaimed_bytes"], 0)
        self.assertEqual(second["mode"], "slim")   # ran and found nothing, not refused
        self._assert_kept_bytes_survive()


class TestNoneModeAgainstTheRealDeleter(_RealSeamCase):
    """``none`` goes through fs_cleanup.robust_rmtree — a DIFFERENT symbol on the
    same module, so it needs its own end-to-end proof that the name resolves."""

    def test_none_removes_the_whole_workdir_and_reports_the_bytes(self):
        os.environ["CB_WORKDIR_RETENTION"] = "none"
        out = wr.apply(self.wd, None, report=self._pass_report(), log=lambda _m: None)
        self.assertEqual(out["mode"], "none")
        self.assertFalse(self.wd.exists())
        self.assertGreater(out["reclaimed_bytes"],
                           _OBJ_BYTES + _REG_BYTES + _PDB_BYTES)
        self.assertTrue(self.wd_root.is_dir(), "the POOL must survive its member")

    def test_cb_preview_downgrades_none_to_slim_on_real_files(self):
        # cb.py's _maybe_chain_postrun_preview re-opens the graded project AFTER
        # the eval route returns; "none" would delete what it is about to
        # photograph. Slim still reclaims the 4.72 GB that matters.
        os.environ["CB_PREVIEW"] = "1"
        out = wr.apply(self.wd, "none", report=self._pass_report(), log=lambda _m: None)
        self.assertEqual(out["mode"], "slim")
        self.assertEqual(out["reason"], "cb_preview_needs_launchable_project")
        self.assertTrue(self.wd.is_dir())
        self._assert_kept_bytes_survive()


if __name__ == "__main__":
    unittest.main()
