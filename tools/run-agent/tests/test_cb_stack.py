"""Offline unit tests for the Python CLI port (aura_rig/stack.py + cb.py).

Pure-offline: no live ports, no agent, no UnrealEditor, no subprocess to the
stack. Exercises the testable pure logic — path resolution, drive-project
precedence, the harness-python cascade shape, the robocopy-equivalent mirror,
and the .env loader. Restores os.environ around each env-mutating test.
"""

from __future__ import annotations

import json
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_rig import stack  # noqa: E402


class _EnvGuard:
    """Save/restore a set of env vars around a test."""
    def __init__(self, *keys):
        self.keys = keys
        self.saved = {}

    def __enter__(self):
        for k in self.keys:
            self.saved[k] = os.environ.get(k)
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestStackPaths(unittest.TestCase):
    def test_explicit_craftbench_and_derivations(self):
        with tempfile.TemporaryDirectory() as d:
            # resolve(): macOS tempdirs live under /var -> /private/var; the
            # StackPaths derivations resolve, so the expectation must too.
            root = Path(d).resolve()
            p = stack.StackPaths(craftbench=root, genius=root / "genius")
            self.assertEqual(p.template_dir, root / "UE-projects" / "CraftBenchTemplate")
            self.assertEqual(p.uproject, p.template_dir / "CraftBenchTemplate.uproject")
            self.assertEqual(p.runagent, root / "tools" / "run-agent")
            self.assertEqual(p.vercel_dir, root / "genius" / "Ramen" / "vercelServer")

    def test_genius_defaults_to_embedded_plugins(self):
        # With no override, genius is the aura-plugin clone INSIDE the substrate's
        # Plugins/ (the 2026-07 refactor) — server dirs derive from there.
        with _EnvGuard("CB_CRAFTBENCH", "CB_GENIUS"):
            os.environ.pop("CB_CRAFTBENCH", None)
            os.environ.pop("CB_GENIUS", None)
            with tempfile.TemporaryDirectory() as d:
                root = Path(d).resolve()
                p = stack.StackPaths(craftbench=root)   # no genius override, no .env
                self.assertEqual(p.genius, p.template_dir / "Plugins")
                self.assertEqual(p.vercel_dir,
                                 p.template_dir / "Plugins" / "Ramen" / "vercelServer")
                self.assertEqual(p.client_dir,
                                 p.template_dir / "Plugins" / "Ramen" / "mcp-client-chatbot")

    def test_cb_craftbench_env_override(self):
        with _EnvGuard("CB_CRAFTBENCH", "CB_GENIUS"):
            os.environ["CB_CRAFTBENCH"] = r"X:\some\craftbench"
            os.environ.pop("CB_GENIUS", None)
            p = stack.StackPaths()
            self.assertEqual(str(p.craftbench), r"X:\some\craftbench")

    def test_uproject_honors_cb_uproject(self):
        with _EnvGuard("CB_UPROJECT"):
            with tempfile.TemporaryDirectory() as d:
                p = stack.StackPaths(craftbench=Path(d), genius=Path(d))
                os.environ["CB_UPROJECT"] = r"C:\scratch\CraftBenchScratch\CraftBenchTemplate.uproject"
                self.assertEqual(str(p.uproject), r"C:\scratch\CraftBenchScratch\CraftBenchTemplate.uproject")
                os.environ.pop("CB_UPROJECT")
                self.assertEqual(p.uproject, p.template_dir / "CraftBenchTemplate.uproject")


class TestDriveProjectDir(unittest.TestCase):
    def test_precedence_explicit_env_default(self):
        with _EnvGuard("CB_DRIVE_PROJECT"):
            # explicit wins
            self.assertEqual(stack.get_drive_project_dir(r"D:\mine"), Path(r"D:\mine"))
            # env next
            os.environ["CB_DRIVE_PROJECT"] = r"E:\fromenv"
            self.assertEqual(stack.get_drive_project_dir(""), Path(r"E:\fromenv"))
            # default last (out-of-repo cache root, ends with the scratch leaf)
            os.environ.pop("CB_DRIVE_PROJECT")
            d = stack.get_drive_project_dir("")
            self.assertEqual(d.name, "CraftBenchScratch")
            self.assertIn("CraftBench", str(d))


class TestL1Cap(unittest.TestCase):
    """stack.l1_cap: leading-integer parse of CRAFTBENCH_L1_MAX_PARALLEL — an
    inline .env comment must not silently drop the cap (FAILURE-LOG 2026-07-24)."""

    def _cap(self, value):
        with _EnvGuard("CRAFTBENCH_L1_MAX_PARALLEL"):
            if value is None:
                os.environ.pop("CRAFTBENCH_L1_MAX_PARALLEL", None)
            else:
                os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = value
            return stack.l1_cap()

    def test_plain_int(self):
        self.assertEqual(self._cap("4"), 4)

    def test_inline_comment_keeps_leading_int(self):
        self.assertEqual(self._cap("2 #tested up to 4"), 2)

    def test_unset_garbage_and_zero_are_none(self):
        self.assertIsNone(self._cap(None))
        self.assertIsNone(self._cap("abc"))
        self.assertIsNone(self._cap("0"))


class TestResolveHarnessPy(unittest.TestCase):
    def test_returns_exe_and_list_pre(self):
        # Stub the --version probe so the cascade resolves the same on ANY box
        # (no dependency on which interpreters are registered here); assert the
        # shape is (str, list) — the pre-args MUST be a list so the caller
        # splats separate argv (the PS single-element-array -> char-split
        # footgun cannot recur in Python).
        with _EnvGuard("CB_PY"):
            os.environ.pop("CB_PY", None)
            with mock.patch.object(stack, "_py_candidate_works", return_value=True):
                hp = stack.resolve_harness_py()
        self.assertIsNotNone(hp)
        exe, pre = hp
        self.assertIsInstance(exe, str)
        self.assertIsInstance(pre, list)

    @unittest.skipUnless(os.name == "nt", "the 'py' launcher is Windows-only")
    def test_cb_py_override_splits(self):
        with _EnvGuard("CB_PY"):
            os.environ["CB_PY"] = "py -3.12"
            # Stub the availability probe: this asserts pure CB_PY *splitting*,
            # not whether a PythonCore 3.12 happens to be registered locally
            # (without the stub, resolve silently falls back to ('py', ['-3'])).
            with mock.patch.object(stack, "_py_candidate_works", return_value=True):
                hp = stack.resolve_harness_py()
            self.assertIsNotNone(hp)
            exe, pre = hp
            # exe resolves to the launcher; pre carries -3.12 as its own token
            self.assertIn("-3.12", pre)


class TestMirrorTree(unittest.TestCase):
    def _seed(self, root):
        (root / "a").mkdir(parents=True)
        (root / "a" / "x.txt").write_text("x", encoding="utf-8")
        (root / "b.txt").write_text("b", encoding="utf-8")

    def test_copy_no_delete_keeps_extras(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir(); (dst / "extra.txt").write_text("e", encoding="utf-8")
            self.assertTrue(stack._mirror_tree(src, dst, delete_extras=False))
            self.assertTrue((dst / "a" / "x.txt").exists())
            self.assertTrue((dst / "extra.txt").exists())  # extra kept

    def test_mirror_deletes_extras(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir(); (dst / "extra.txt").write_text("e", encoding="utf-8")
            (dst / "gone").mkdir(); (dst / "gone" / "y.txt").write_text("y", encoding="utf-8")
            self.assertTrue(stack._mirror_tree(src, dst, delete_extras=True))
            self.assertTrue((dst / "a" / "x.txt").exists())
            self.assertFalse((dst / "extra.txt").exists())   # extra deleted
            self.assertFalse((dst / "gone").exists())         # extra dir deleted

    def test_mirror_collector_stays_empty_when_deletes_succeed(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir(); (dst / "extra.txt").write_text("e", encoding="utf-8")
            failed: list = []
            self.assertTrue(stack._mirror_tree(src, dst, delete_extras=True,
                                               failed_deletes=failed))
            self.assertEqual(failed, [])
            self.assertFalse((dst / "extra.txt").exists())

    @unittest.skipUnless(sys.platform == "win32",
                         "POSIX allows unlinking an open file")
    def test_mirror_reports_locked_extra_into_collector(self):
        # An open handle (no FILE_SHARE_DELETE) defeats the delete — the
        # live-editor-holds-the-leftover case. The old sweep swallowed the
        # OSError silently (returned True, extra survived, NO signal — the
        # graded-scratch contamination class); the survivor must now be
        # reported into failed_deletes so the compose can refuse.
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir()
            extra = dst / "stale.uasset"
            extra.write_text("locked leftover", encoding="utf-8")
            failed: list = []
            with open(extra, "rb"), \
                    mock.patch.object(stack.time, "sleep", lambda s: None):
                ok = stack._mirror_tree(src, dst, delete_extras=True,
                                        failed_deletes=failed)
            self.assertTrue(ok)  # the copy side succeeded
            self.assertEqual(failed, ["stale.uasset"])
            self.assertTrue(extra.exists())

    def test_delete_retry_removes_a_dangling_symlink_extra(self):
        # exists() follows links, so a DANGLING symlink extra used to read as
        # already-gone; the lexists-based sweep must remove the link itself.
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir()
            target = Path(d) / "gone-target"
            target.mkdir()
            link = dst / "dangler"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation not permitted on this host")
            target.rmdir()  # now dangling
            failed: list = []
            self.assertTrue(stack._mirror_tree(src, dst, delete_extras=True,
                                               failed_deletes=failed))
            self.assertEqual(failed, [])
            self.assertFalse(os.path.lexists(link))

    def test_mirror_without_collector_keeps_besteffort_contract(self):
        # Callers that pass no collector (the batch-gen drive-project
        # init/reset) keep the old best-effort semantics: no raise, True
        # returned.
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; dst = Path(d) / "dst"
            self._seed(src)
            dst.mkdir(); (dst / "extra.txt").write_text("e", encoding="utf-8")
            self.assertTrue(stack._mirror_tree(src, dst, delete_extras=True))


# TestEnsureScratchPlugins stood here until the public release: it required a clone of the private
# plugin repo into the scratch project.


class TestLoadAuraEnv(unittest.TestCase):
    def test_parses_and_renames(self):
        with _EnvGuard("AURA_USERNAME", "AURA_PASSWORD", "CB_SUPABASE_URL", "CB_SUPABASE_ANON"):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / ".env").write_text(
                    'AURA_USERNAME=user@example.com\nAURA_PASSWORD="secret"\n', encoding="utf-8")
                vdir = root / "genius" / "Ramen" / "vercelServer"
                vdir.mkdir(parents=True)
                (vdir / ".env").write_text(
                    "NEXT_PUBLIC_SUPABASE_URL=https://x.supabase.co\n"
                    "NEXT_PUBLIC_SUPABASE_ANON_KEY=anon123\n", encoding="utf-8")
                p = stack.StackPaths(craftbench=root, genius=root / "genius")
                stack.load_aura_env(p)

    def test_workdir_retention_reaches_os_environ(self):
        # load_aura_env is a WHITELIST, so an un-listed key in .env is a SILENT
        # no-op — no error, no warning, just ignored. CB_WORKDIR_RETENTION is the
        # only way to opt out of slim retention (there is no CLI flag), so an
        # operator who sets it in .env, sees no complaint, and then finds a
        # ~42 MB slimmed workdir where they wanted the build tree has been
        # actively misled. Same class as CRAFTBENCH_L1_MAX_PARALLEL below it.
        with _EnvGuard("CB_WORKDIR_RETENTION", "CRAFTBENCH_L1_MAX_PARALLEL"):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                os.environ.pop("CB_WORKDIR_RETENTION", None)
                (root / ".env").write_text(
                    "CB_WORKDIR_RETENTION=full\nCRAFTBENCH_L1_MAX_PARALLEL=2\n",
                    encoding="utf-8")
                p = stack.StackPaths(craftbench=root, genius=root / "genius")
                stack.load_aura_env(p)
                self.assertEqual(os.environ.get("CB_WORKDIR_RETENTION"), "full")
                # and it must actually change the resolved mode, not just sit in environ
                from aura_rig import workdir_retention as _wr
                self.assertEqual(_wr.resolve_mode(), "full")

    def test_password_with_trailing_inline_comment(self):
        # AURA_PASSWORD="secret" # note  must parse to `secret`, not
        # `secret" # note` — the broken parse reached Supabase verbatim and
        # walled the eval on "Invalid login credentials" (FAILURE-LOG
        # 2026-07-24; the .env inline-comment class, fourth sighting).
        with _EnvGuard("AURA_USERNAME", "AURA_PASSWORD"):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / ".env").write_text(
                    'AURA_USERNAME="user@example.com"\n'
                    'AURA_PASSWORD="s3cr#t pass" # from the team vault\n',
                    encoding="utf-8")
                p = stack.StackPaths(craftbench=root, genius=root / "genius")
                stack.load_aura_env(p)
                # `#` and spaces INSIDE the quotes are part of the password;
                # everything after the closing quote is comment.

    def test_dotenv_value_semantics(self):
        cases = [
            ("plain", "plain"),
            ('"quoted"', "quoted"),
            ('"quoted" # trailing comment', "quoted"),
            ("bare # trailing comment", "bare"),
            ('"has # inside"', "has # inside"),
            ('  padded  ', "padded"),
            ('"unterminated', "unterminated"),  # legacy fallback
            ("", ""),
        ]
        for raw, want in cases:
            self.assertEqual(stack._dotenv_value(raw), want, f"raw={raw!r}")

    def test_loads_rig_layout_keys(self):
        # CB_GENIUS/CB_AURA_SKILLS in craftbench/.env must reach os.environ —
        # a fresh process (detached batch-gen) otherwise falls back to the
        # substrate Plugins/ dir and the login probe dies with WinError 267
        # (2026-07-21 FAILURE-LOG entry).
        with _EnvGuard("CB_GENIUS", "CB_AURA_SKILLS"):
            os.environ.pop("CB_GENIUS", None)
            os.environ.pop("CB_AURA_SKILLS", None)
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / ".env").write_text(
                    "CB_GENIUS=C:\\rig\\checkout\n"
                    "CB_AURA_SKILLS=C:\\rig\\checkout\\.claude\\skills\n",
                    encoding="utf-8")
                p = stack.StackPaths(craftbench=root, genius=root / "genius")
                stack.load_aura_env(p)
                self.assertEqual(os.environ.get("CB_GENIUS"), "C:\\rig\\checkout")
                self.assertEqual(os.environ.get("CB_AURA_SKILLS"),
                                 "C:\\rig\\checkout\\.claude\\skills")


# TestBringupFailFast stood here until the public release: it drove the vercel :3000 / dev-browser
# stages, which are not part of this release.


class TestStartDetachedShim(unittest.TestCase):
    """Windows node shims (yarn/npx/pnpm/npm) route through `cmd /c`; direct
    executables (the editor) launch as-is."""

    def _launched(self, argv):
        seen = {}
        def fake_popen(cmd, **kw):
            seen["cmd"] = cmd
            return mock.Mock()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(stack, "IS_WINDOWS", True), \
                 mock.patch.object(stack.subprocess, "Popen", side_effect=fake_popen):
                stack.start_detached(argv, cwd=Path(d), log_path=Path(d) / "x.log")
        return seen["cmd"]

    def test_shim_routed_through_cmd(self):
        self.assertEqual(self._launched(["yarn", "local_dev"]),
                         ["cmd", "/c", "yarn", "local_dev"])

    def test_direct_exe_launched_as_is(self):
        self.assertEqual(self._launched(["UnrealEditor.exe", "-log"]),
                         ["UnrealEditor.exe", "-log"])


class TestEditorBootTimeout(unittest.TestCase):
    """Cold DerivedDataCache → a long editor-boot window (shader compile);
    warm DDC → the default. Env override wins."""

    def test_env_override_leading_int(self):
        with _EnvGuard("CB_EDITOR_BOOT_TIMEOUT"):
            os.environ["CB_EDITOR_BOOT_TIMEOUT"] = "900 # tuned"
            self.assertEqual(stack.editor_boot_timeout(Path("x.uproject")), 900)

    def test_cold_ddc_is_long(self):
        with _EnvGuard("CB_EDITOR_BOOT_TIMEOUT", "LOCALAPPDATA", "CB_UE_ROOT"):
            os.environ.pop("CB_EDITOR_BOOT_TIMEOUT", None)
            with tempfile.TemporaryDirectory() as d:
                # point every DDC candidate at empty/absent dirs
                os.environ["LOCALAPPDATA"] = str(Path(d) / "la")
                os.environ["CB_UE_ROOT"] = str(Path(d) / "ue")
                self.assertEqual(
                    stack.editor_boot_timeout(Path(d) / "proj" / "x.uproject"), 1800)

    def test_warm_ddc_is_default(self):
        with _EnvGuard("CB_EDITOR_BOOT_TIMEOUT", "LOCALAPPDATA", "CB_UE_ROOT"):
            os.environ.pop("CB_EDITOR_BOOT_TIMEOUT", None)
            os.environ.pop("CB_UE_ROOT", None)
            with tempfile.TemporaryDirectory() as d:
                ddc = Path(d) / "la" / "UnrealEngine" / "Common" / "DerivedDataCache"
                ddc.mkdir(parents=True)
                (ddc / "some.udd").write_bytes(b"x")  # non-empty = warm
                os.environ["LOCALAPPDATA"] = str(Path(d) / "la")
                self.assertEqual(
                    stack.editor_boot_timeout(Path(d) / "proj" / "x.uproject"), 480)


# TestBringupToolchainGate stood here until the public release: it gated on the node toolchain (pnpm)
# that only the removed vercel/client stages needed.


class TestScratchBuildStaleness(unittest.TestCase):
    """The scratch editor build is stamped with the UE engine; a stamp mismatch
    (or a pre-stamp empty marker) forces a CLEAN rebuild — this fixes the 'scratch
    built on UE 5.7, launched on 5.8 -> game module could not be found' failure and
    the stale-.obj link errors after it. Same-engine stays a fast incremental build."""

    def test_no_marker_means_plain_build(self):
        self.assertEqual(stack._scratch_build_action(None, "C:/UE_5.8"), "build")

    def test_matching_stamp_skips(self):
        self.assertEqual(stack._scratch_build_action("C:/UE_5.8", "C:/UE_5.8"), "skip")
        # whitespace/newline tolerant (marker is written without/with trailing ws)
        self.assertEqual(stack._scratch_build_action("C:/UE_5.8\n", "C:/UE_5.8"), "skip")

    def test_different_engine_forces_clean(self):
        self.assertEqual(stack._scratch_build_action("C:/UE_5.7", "C:/UE_5.8"), "clean")

    def test_pre_stamp_empty_marker_forces_clean(self):
        # Old format: `.cb-built` was an empty `touch` -> treat as stale -> clean.
        self.assertEqual(stack._scratch_build_action("", "C:/UE_5.8"), "clean")

    def test_substrate_change_forces_clean(self):
        # The stamp is ENGINE|PROJECT (2026-07-21: an engine-only stamp let a
        # recompose to a DIFFERENT substrate skip the build — the scratch held
        # only the previous substrate's DLLs and the editor exited on startup).
        self.assertEqual(stack._scratch_build_action(
            "C:/UE_5.8|CraftBenchTemplate", "C:/UE_5.8|ThirdPerson"), "clean")
        self.assertEqual(stack._scratch_build_action(
            "C:/UE_5.8|ThirdPerson", "C:/UE_5.8|ThirdPerson"), "skip")
        # A legacy engine-only marker mismatches the composite -> one safe clean.
        self.assertEqual(stack._scratch_build_action(
            "C:/UE_5.8", "C:/UE_5.8|ThirdPerson"), "clean")

    def test_clean_build_dirs_removes_binaries_intermediate_not_plugins(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "Binaries" / "Win64").mkdir(parents=True)
            (root / "Binaries" / "Win64" / "x.dll").write_text("x")
            (root / "Intermediate" / "Build").mkdir(parents=True)
            (root / "Plugins" / "Aura").mkdir(parents=True)   # the junction stand-in
            (root / "Plugins" / "Aura" / "keep.txt").write_text("keep")
            stack._clean_scratch_build_dirs(root, log=lambda *a: None)
            self.assertFalse((root / "Binaries").exists())
            self.assertFalse((root / "Intermediate").exists())
            # Plugins/ (Aura junction) MUST be untouched (data-loss guard).
            self.assertTrue((root / "Plugins" / "Aura" / "keep.txt").exists())


class TestCrossFolderEditorIsolation(unittest.TestCase):
    """craftbench shares the editor RC :30010 + the single .Aura session with any
    other Aura on the box; these helpers must scope every editor kill to craftbench's
    OWN editor and detect a foreign one (e.g. ../unrealfeaturedev) so we never
    reap/hijack the user's dev editor."""

    CB = r"c:/u/x/appdata/local/craftbench/scratch/craftbenchscratch/craftbenchtemplate.uproject -renderoffscreen"
    CB2 = r"d:/github/craftbench/ue-projects/craftbenchtemplate/craftbenchtemplate.uproject -auraheadless"
    FOREIGN = r"c:/u/x/github/unrealfeaturedev/unrealfeaturedev.uproject -game"

    def test_predicate(self):
        self.assertTrue(stack._is_craftbench_editor(self.CB))
        self.assertTrue(stack._is_craftbench_editor(self.CB2))
        self.assertFalse(stack._is_craftbench_editor(self.FOREIGN))

    def test_predicate_owns_non_default_substrate_scratch(self):
        # A NON-default substrate's scratch has no "craftbench" in its path —
        # ownership must come from the managed scratch root (2026-07-21: the
        # ThirdPerson scratch editor was misclassified FOREIGN and the guard
        # blocked its own re-run).
        root = str(stack.cb_paths.scratch_root()).lower()
        tp = root.replace("\\", "/") + "/thirdpersonscratch/thirdperson.uproject -renderoffscreen"
        self.assertTrue(stack._is_craftbench_editor(tp))
        # ...while an arbitrary project elsewhere stays foreign
        self.assertFalse(stack._is_craftbench_editor(
            r"c:\projects\thirdperson\thirdperson.uproject -game"))

    @unittest.skipUnless(os.name == "nt", "backslash cmdlines are a Windows-only form")
    def test_predicate_owns_scratch_in_either_slash_form(self):
        # Windows cmdlines report the scratch path in EITHER slash form, so
        # _cb_owned_path_markers() publishes both. That is a Windows-only
        # concern: off Windows the native root is already forward-slash and
        # its backslash "form" (\home\runner\cb\...) is not a path any
        # producer emits — matching it could only ever be a false positive.
        root = str(stack.cb_paths.scratch_root()).lower()
        tp = root.replace("\\", "/") + "/thirdpersonscratch/thirdperson.uproject -renderoffscreen"
        self.assertTrue(stack._is_craftbench_editor(tp))
        self.assertTrue(stack._is_craftbench_editor(tp.replace("/", "\\")))

    def test_foreign_editor_detection(self):
        orig = stack._editor_procs
        try:
            stack._editor_procs = lambda: [(101, self.CB), (202, self.FOREIGN)]
            self.assertEqual(stack.foreign_editor()[0], 202)
            stack._editor_procs = lambda: [(101, self.CB)]   # only craftbench
            self.assertIsNone(stack.foreign_editor())
            stack._editor_procs = lambda: []                 # none / unenumerable
            self.assertIsNone(stack.foreign_editor())
        finally:
            stack._editor_procs = orig

    def test_kill_spares_foreign(self):
        import types
        o_procs, o_run, o_win = stack._editor_procs, stack.subprocess.run, stack.IS_WINDOWS
        killed = []
        def fake_run(cmd, **kw):
            if "/PID" in cmd:
                killed.append(int(cmd[cmd.index("/PID") + 1]))
            elif cmd[:2] == ["kill", "-9"]:
                killed.append(int(cmd[2]))
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        try:
            stack.IS_WINDOWS = True
            stack._editor_procs = lambda: [(101, self.CB), (202, self.FOREIGN), (303, self.CB2)]
            stack.subprocess.run = fake_run
            stack.kill_craftbench_editors(log=lambda *a: None)
            self.assertEqual(sorted(killed), [101, 303])  # craftbench pids only
            self.assertNotIn(202, killed)                 # foreign spared
        finally:
            stack._editor_procs, stack.subprocess.run, stack.IS_WINDOWS = o_procs, o_run, o_win

    def test_kill_falls_back_to_blanket_when_unenumerable(self):
        o_procs, o_kbi = stack._editor_procs, stack.kill_by_image
        called = []
        try:
            stack._editor_procs = lambda: []
            stack.kill_by_image = lambda *names: called.append(names)
            stack.kill_craftbench_editors(log=lambda *a: None)
            self.assertIn(("UnrealEditor",), called)  # best-effort when we can't enumerate
        finally:
            stack._editor_procs, stack.kill_by_image = o_procs, o_kbi


if __name__ == "__main__":
    unittest.main()


class TestPlaceholderSecretGuard(unittest.TestCase):
    """`.env` placeholders must never be exported over a real environment value.

    `cb bootstrap` copies .env.example verbatim to .env, and until 2026-07-26
    three secrets were UNCOMMENTED there. load_aura_env assigns unconditionally,
    so a fresh box exported ANTHROPIC_API_KEY=sk-ant-xxxx OVER a real key the
    operator already had — an auth failure with no visible cause, because the
    variable IS set, just to nonsense.
    """

    def test_shipped_placeholders_are_detected(self):
        from aura_rig.stack import _is_placeholder
        for v in ("sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                  "sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                  "you@example.com",
                  "your-aura-password",
                  "your-vercel-token"):
            self.assertTrue(_is_placeholder(v), v)

    def test_realistic_secrets_are_not_flagged(self):
        # A false positive is loud (the operator sees an unset var); a false
        # negative is silent. Still, plausible real values must pass through.
        from aura_rig.stack import _is_placeholder
        for v in ("sk-ant-api03-EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE",
                  "user@example.com",
                  "hunter2-correct-horse",
                  "ghp_EXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE00"):
            self.assertFalse(_is_placeholder(v), v)

    def test_detection_is_case_insensitive(self):
        from aura_rig.stack import _is_placeholder
        self.assertTrue(_is_placeholder("SK-ANT-XXXXXXXX"))
        self.assertTrue(_is_placeholder("You@Example.com"))

    def test_env_example_ships_no_live_assignment(self):
        # The root cause, pinned: every key in .env.example must be commented,
        # so a freshly-copied .env exports nothing at all.
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        example = root / ".env.example"
        if not example.exists():
            self.skipTest(".env.example not present")
        live = [ln for ln in example.read_text(encoding="utf-8").splitlines()
                if re.match(r"^[A-Z][A-Z0-9_]*=", ln)]
        self.assertEqual(live, [], f"uncommented assignment(s) in .env.example: {live}")


class TestEnvPrecedence(unittest.TestCase):
    """`.env` must NOT clobber an explicitly-exported value.

    Until 2026-07-26 `stack.load_aura_env` assigned unconditionally while its
    sibling `verify-single/repo_env.load_repo_env` skipped already-set vars with
    "explicit env wins" — so the SAME variable resolved differently depending on
    whether you went through `cb`. `export CRAFTBENCH_L1_MAX_PARALLEL=4 &&
    cb eval` with `.env` saying 2 silently built at 2.
    """

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("CRAFTBENCH_L1_MAX_PARALLEL", "AURA_USERNAME",
                        "CB_SUPABASE_URL")}
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        (self.root / "craftbench").mkdir()
        (self.root / "vercel").mkdir()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _paths(self, cb_env_text=""):
        (self.root / "craftbench" / ".env").write_text(cb_env_text, encoding="utf-8")
        return types.SimpleNamespace(craftbench=self.root / "craftbench",
                                     vercel_dir=self.root / "vercel")

    def test_exported_value_beats_dotenv(self):
        from aura_rig import stack
        os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = "4"
        stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        self.assertEqual(os.environ["CRAFTBENCH_L1_MAX_PARALLEL"], "4",
                         "`.env` clobbered an explicit export")

    def test_dotenv_fills_an_unset_var(self):
        from aura_rig import stack
        os.environ.pop("CRAFTBENCH_L1_MAX_PARALLEL", None)
        stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        self.assertEqual(os.environ["CRAFTBENCH_L1_MAX_PARALLEL"], "2")

    def test_blank_export_does_not_block_dotenv(self):
        # An empty string is "unset" for this purpose, matching repo_env's
        # `(target.get(key) or "").strip()` test.
        from aura_rig import stack
        os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = "   "
        stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        self.assertEqual(os.environ["CRAFTBENCH_L1_MAX_PARALLEL"], "2")

    def test_override_is_announced_not_silent(self):
        from aura_rig import stack
        os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = "4"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        out = buf.getvalue()
        self.assertIn("CRAFTBENCH_L1_MAX_PARALLEL", out)
        self.assertIn("explicit environment value wins", out)

    def test_identical_value_is_not_announced(self):
        # No conflict, so no noise.
        from aura_rig import stack
        os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = "2"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        self.assertNotIn("NOT applied", buf.getvalue())

    def test_agrees_with_repo_env_on_the_same_input(self):
        # The whole point: both loaders must resolve the same way now.
        from aura_rig import stack
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]
                              / "tools" / "verify-single"))
        import repo_env
        os.environ["CRAFTBENCH_L1_MAX_PARALLEL"] = "4"
        stack.load_aura_env(self._paths("CRAFTBENCH_L1_MAX_PARALLEL=2\n"))
        via_cb = os.environ["CRAFTBENCH_L1_MAX_PARALLEL"]
        target = {"CRAFTBENCH_L1_MAX_PARALLEL": "4"}
        (self.root / ".env").write_text("CRAFTBENCH_L1_MAX_PARALLEL=2\n",
                                        encoding="utf-8")
        repo_env.load_repo_env(self.root, env=target)
        self.assertEqual(via_cb, target["CRAFTBENCH_L1_MAX_PARALLEL"], "4")


class TestEditorMarkerUnification(unittest.TestCase):
    """2026-08-19 regression: the per-drive gate and the orphan sweep must
    agree about whose an editor is. They disagreed — _cb_owned_path_markers
    knew only the name marker + scratch root, so a headless editor on the
    repo's own UE-projects/ThirdPerson (no 'craftbench' substring in the
    path) was refused as FOREIGN by the unreal-mcp gate while cb down's
    sweep (repo root + wd root included) reaped it as cb debris. Two
    ceilinged go/no-go runs stalled pre-spend on that split."""

    def test_gate_honors_every_sweep_marker(self):
        from aura_rig import stack, stack_guard
        for m in stack_guard.cb_cmdline_markers():
            cl = f"unrealeditor.exe {m}/ue-projects/thirdperson/x.uproject"
            self.assertTrue(stack._is_craftbench_editor(cl.lower()), m)

    def test_repo_root_thirdperson_is_ours(self):
        from pathlib import Path
        from aura_rig import stack
        repo = Path(__file__).resolve().parents[3]
        cl = ("unrealeditor.exe "
              f"{repo}/UE-projects/ThirdPerson/ThirdPerson.uproject "
              "-renderoffscreen -modelcontextprotocolstartserver").lower()
        self.assertTrue(stack._is_craftbench_editor(cl))

    def test_foreign_project_stays_foreign(self):
        from aura_rig import stack
        self.assertFalse(stack._is_craftbench_editor(
            r"unrealeditor.exe d:\games\myrpg\myrpg.uproject".lower()))
