"""aura_rig.paths — the ONE CB_ROOT machine-dir resolver — plus `cb where`.

Fully offline: pure env/dir resolution, tmp dirs, no UE, no stack bring-up.
Covers the resolution precedence contract (env override > CB_ROOT default),
the retirement of the old defaults (C:\\cbwd / LOCALAPPDATA-cache scratch),
`cb where`'s read-only row set, and `cb where --link`'s idempotent symlinks.
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import paths as cb_paths  # noqa: E402
from aura_rig import cb as _cb  # noqa: E402
from aura_rig import graded_scratch, stack  # noqa: E402

_ENV = ("CB_ROOT", "CRAFTBENCH_WD_ROOT", "CB_GRADED_PROJECT", "CB_DRIVE_PROJECT")


class _EnvIsolated(unittest.TestCase):
    """Save/clear the resolver envs so host machine config can't leak in."""

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in _ENV}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestCbRoot(_EnvIsolated):
    def test_env_override_wins(self):
        os.environ["CB_ROOT"] = "/somewhere/else"
        self.assertEqual(cb_paths.cb_root(), Path("/somewhere/else"))

    def test_default_is_platform_root(self):
        # Windows-FAMILY detection (native + Git-Bash/Cygwin/MSYS/MinGW
        # pythons), mirroring l2_pie._editor_binary's host check.
        expected = (Path(r"C:\cb") if cb_paths._is_windows_family()
                    else Path.home() / "cb")
        self.assertEqual(cb_paths.cb_root(), expected)

    def test_windows_family_matches_l2_pie_semantics(self):
        # The predicate itself: native NT or a win/cygwin/msys/mingw
        # platform.system() prefix — never True on Darwin/Linux pythons.
        import platform
        win = (platform.system().lower().startswith(
            ("win", "cygwin", "msys", "mingw")) or os.name == "nt")
        self.assertEqual(cb_paths._is_windows_family(), win)


class TestWdRoot(_EnvIsolated):
    def test_old_env_override_still_wins(self):
        # Back-compat: CRAFTBENCH_WD_ROOT keeps working as the override...
        os.environ["CRAFTBENCH_WD_ROOT"] = "/my/wd"
        os.environ["CB_ROOT"] = "/cbroot"
        self.assertEqual(cb_paths.wd_root(), Path("/my/wd"))

    def test_default_hangs_off_cb_root(self):
        # ...but the DEFAULT is <cb_root>/wd, NOT the retired C:\cbwd.
        os.environ["CB_ROOT"] = "/cbroot"
        self.assertEqual(cb_paths.wd_root(), Path("/cbroot") / "wd")

    def test_old_cbwd_default_is_retired(self):
        self.assertNotEqual(cb_paths.wd_root(), Path(r"C:\cbwd"))


class TestScratchAndGraded(_EnvIsolated):
    def test_scratch_root_hangs_off_cb_root(self):
        os.environ["CB_ROOT"] = "/cbroot"
        self.assertEqual(cb_paths.scratch_root(), Path("/cbroot") / "scratch")

    def test_graded_precedence_explicit_env_default(self):
        os.environ["CB_ROOT"] = "/cbroot"
        # default
        self.assertEqual(cb_paths.graded_project_dir(),
                         Path("/cbroot") / "scratch" / "CraftBenchGraded")
        # env override beats the default
        os.environ["CB_GRADED_PROJECT"] = "/env/graded"
        self.assertEqual(cb_paths.graded_project_dir(), Path("/env/graded"))
        # explicit arg beats everything
        self.assertEqual(cb_paths.graded_project_dir("/explicit/graded"),
                         Path("/explicit/graded"))

    def test_graded_scratch_module_delegates(self):
        # graded_scratch.get_graded_project_dir is the SAME resolver (a
        # back-compat entry point) — identical precedence, no re-derivation.
        os.environ["CB_ROOT"] = "/cbroot"
        self.assertEqual(graded_scratch.get_graded_project_dir(),
                         Path("/cbroot") / "scratch" / "CraftBenchGraded")
        os.environ["CB_GRADED_PROJECT"] = "/env/graded"
        self.assertEqual(graded_scratch.get_graded_project_dir(),
                         Path("/env/graded"))
        self.assertEqual(graded_scratch.get_graded_project_dir("/x"), Path("/x"))

    def test_drive_playground_hangs_off_cb_root(self):
        # stack.get_drive_project_dir keeps its CB_DRIVE_PROJECT override but its
        # default is now <cb_root>/scratch/CraftBenchScratch (LOCALAPPDATA/
        # XDG-cache default retired).
        os.environ["CB_ROOT"] = "/cbroot"
        self.assertEqual(stack.get_drive_project_dir(""),
                         Path("/cbroot") / "scratch" / "CraftBenchScratch")
        os.environ["CB_DRIVE_PROJECT"] = "/env/drive"
        self.assertEqual(stack.get_drive_project_dir(""), Path("/env/drive"))
        self.assertEqual(stack.get_drive_project_dir("/explicit"),
                         Path("/explicit"))


class TestCbWhere(_EnvIsolated):
    """`cb where`: read-only row set + --link junction/symlink helper."""

    def _fake_ctx(self, repo: Path):
        return types.SimpleNamespace(paths=types.SimpleNamespace(
            craftbench=repo,
            template_dir=repo / "UE-projects" / "CraftBenchTemplate",
        ))

    def test_rows_cover_every_machine_dir(self):
        os.environ["CB_ROOT"] = "/cbroot"
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            rows = dict(_cb._where_rows(self._fake_ctx(repo)))
        self.assertEqual(
            set(rows), {"repo", "substrate", "cb_root", "wd_root",
                        "graded scratch", "drive scratch", "runs"})
        self.assertEqual(rows["cb_root"], Path("/cbroot"))
        self.assertEqual(rows["wd_root"], Path("/cbroot") / "wd")
        self.assertEqual(rows["graded scratch"],
                         Path("/cbroot") / "scratch" / "CraftBenchGraded")
        self.assertEqual(rows["drive scratch"],
                         Path("/cbroot") / "scratch" / "CraftBenchScratch")
        self.assertEqual(rows["runs"], rows["repo"] / "runs")

    def test_cmd_where_is_read_only(self):
        # Plain `cb where` must not create ANY of the dirs it reports.
        with tempfile.TemporaryDirectory() as td:
            os.environ["CB_ROOT"] = str(Path(td) / "cbroot")
            repo = Path(td) / "repo"
            repo.mkdir()
            lines = []
            old_say = _cb._say
            _cb._say = lambda m="": lines.append(m)
            try:
                rc = _cb.cmd_where(self._fake_ctx(repo),
                                   types.SimpleNamespace(link=False))
            finally:
                _cb._say = old_say
            self.assertEqual(rc, 0)
            self.assertFalse((Path(td) / "cbroot").exists(),
                             "`cb where` must not mkdir anything")
            self.assertFalse((repo / ".cb").exists())
            joined = "\n".join(lines)
            for label in ("repo", "substrate", "cb_root", "wd_root",
                          "graded scratch", "drive scratch", "runs"):
                self.assertIn(label, joined)

    @unittest.skipIf(os.name == "nt", "posix symlink leg (junction leg is manual)")
    def test_link_creates_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["CB_ROOT"] = str(Path(td) / "cbroot")
            repo = Path(td) / "repo"
            repo.mkdir()
            args = types.SimpleNamespace(link=True)
            old_say = _cb._say
            _cb._say = lambda m="": None
            try:
                self.assertEqual(_cb.cmd_where(self._fake_ctx(repo), args), 0)
                # idempotent: second run neither raises nor duplicates
                self.assertEqual(_cb.cmd_where(self._fake_ctx(repo), args), 0)
            finally:
                _cb._say = old_say
            wd_link = repo / ".cb" / "wd"
            sc_link = repo / ".cb" / "scratch"
            self.assertTrue(wd_link.is_symlink())
            self.assertTrue(sc_link.is_symlink())
            self.assertEqual(Path(os.path.realpath(wd_link)),
                             Path(os.path.realpath(Path(td) / "cbroot" / "wd")))
            self.assertEqual(Path(os.path.realpath(sc_link)),
                             Path(os.path.realpath(Path(td) / "cbroot" / "scratch")))
            # --link creates the real target dirs so the links aren't dangling
            self.assertTrue((Path(td) / "cbroot" / "wd").is_dir())
            self.assertTrue((Path(td) / "cbroot" / "scratch").is_dir())

    @unittest.skipIf(os.name == "nt", "posix symlink leg")
    def test_link_retargets_a_stale_link_but_refuses_a_real_dir(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "real-target"
            stale = Path(td) / "stale-target"
            stale.mkdir()
            link = Path(td) / "repo" / ".cb" / "wd"
            link.parent.mkdir(parents=True)
            link.symlink_to(stale)
            self.assertEqual(
                _cb._ensure_dir_link(link, target, log=lambda m="": None), 0)
            self.assertEqual(Path(os.path.realpath(link)),
                             Path(os.path.realpath(target)))
            # A REAL non-empty dir at the link path is REFUSED: one-line
            # message + non-zero return, NEVER a traceback, data untouched.
            real = Path(td) / "repo" / ".cb" / "scratch"
            real.mkdir()
            (real / "keep.txt").write_text("data", encoding="utf-8")
            msgs: list = []
            rc = _cb._ensure_dir_link(real, target, log=msgs.append)
            self.assertEqual(rc, 1)
            self.assertTrue(any("refusing to clobber" in m for m in msgs))
            self.assertTrue((real / "keep.txt").exists())



class TestTmpScratchRoots(unittest.TestCase):
    r"""paths.tmp_scratch_roots — DEDICATED rig scratch roots, never the OS temp.

    `cb clean --workdirs` consumes this list and deletes whole child
    directories, so handing it the shared system temp would put pip caches, OS
    scratch and every other tool's data one age-check away from deletion. That
    exclusion is the contract worth pinning, not an implementation detail.

    Context (2026-08-20): an operator following envgate's 8.3 remediation
    (`set TEMP=C:\cbtmp`) sends every mkdtemp workdir to C:\cbtmp, which the
    sweep could not see — 95 GB of duplicated SharedPCH accumulated there.
    """

    _VARS = ("CB_TMP", "TEMP", "TMP")

    def setUp(self):
        # gettempdir() is cached by tempfile, so clearing TEMP/TMP here does not
        # move the temp dirs these tests create.
        self._saved = {k: os.environ.pop(k, None) for k in self._VARS}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_never_returns_bare_system_temp(self):
        sys_tmp = Path(tempfile.gettempdir()).resolve()
        os.environ["CB_TMP"] = str(sys_tmp)
        self.assertNotIn(sys_tmp, cb_paths.tmp_scratch_roots())

    def test_explicit_cb_tmp_is_returned(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["CB_TMP"] = td
            self.assertIn(Path(td).resolve(), cb_paths.tmp_scratch_roots())

    def test_temp_override_counts_only_when_it_is_a_cbtmp_root(self):
        with tempfile.TemporaryDirectory() as td:
            named = Path(td) / "cbtmp"
            named.mkdir()
            other = Path(td) / "random-temp"
            other.mkdir()
            os.environ["TEMP"] = str(other)
            self.assertNotIn(other.resolve(), cb_paths.tmp_scratch_roots())
            os.environ["TEMP"] = str(named)
            self.assertIn(named.resolve(), cb_paths.tmp_scratch_roots())

    def test_no_duplicate_roots(self):
        with tempfile.TemporaryDirectory() as td:
            named = Path(td) / "cbtmp"
            named.mkdir()
            os.environ["CB_TMP"] = str(named)
            os.environ["TEMP"] = str(named)
            roots = cb_paths.tmp_scratch_roots()
            self.assertEqual(len(roots), len(set(roots)))

if __name__ == "__main__":
    unittest.main()
