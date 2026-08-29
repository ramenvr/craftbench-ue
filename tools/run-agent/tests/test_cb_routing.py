"""cb eval model-slug routing, as the open-source release ships it:
claude-p:* / openrouter:* / bare:* -> the generalist BASELINE runner (run.py);
unreal-mcp[:*] -> the Epic-MCP editor path; aura-mcp[:*] -> REFUSED in the
first second (disclosed but not reproducible from this repository); anything
else -> refused as an unknown backend.

Until 2026-08-28 a bare key with no colon meant the aura-product lane and this
file's routing cases were mostly about steering INTO it. That lane is cut, so
what is worth pinning now is the opposite: which slugs reach a runner, and that
the two that do not are answered before any task resolve, env gate, build or
token spend.

These exercise the PURE helpers only — no UE, no stack bring-up, no subprocess."""

import json
import os
import re
import shutil
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import cb as _cb  # noqa: E402
from aura_rig.cb import _backend_of, _is_aura_backend, _robust_rmtree  # noqa: E402


def _repo_with_t0(tc: unittest.TestCase) -> Path:
    """A minimal REAL repo root holding tasks/t0.md, auto-cleaned. cmd_eval now
    gates the task id against the tree BEFORE routing/bring-up, so the mocked
    ctxs need a resolvable 't0' (runs/ stays absent — _show_newest_run's
    OSError path still exercised)."""
    td = tempfile.TemporaryDirectory()
    tc.addCleanup(td.cleanup)
    spec = Path(td.name) / "tasks" / "t0.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# t0\n", encoding="utf-8")
    return Path(td.name)


class TestRobustRmtree(unittest.TestCase):
    """`cb clean --workdirs` uses _robust_rmtree so a stale verifier workdir still
    locked by a lingering L2-editor handle is retried, not silently left forever —
    and a genuinely-stuck handle degrades gracefully (never raises)."""

    def test_removes_a_normal_tree(self):
        d = tempfile.mkdtemp()
        (Path(d) / "sub").mkdir()
        (Path(d) / "sub" / "L_SanityTask.umap").write_bytes(b"0")
        self.assertTrue(_robust_rmtree(d, retries=2))
        self.assertFalse(os.path.exists(d))

    def test_open_handle_never_raises(self):
        d = tempfile.mkdtemp()
        f = Path(d) / "L_SanityTask.umap"
        f.write_bytes(b"0")
        fh = open(f, "rb")
        try:
            result = _robust_rmtree(d, retries=2, base_delay=0.05)
            self.assertIsInstance(result, bool)  # returned, did not raise
        finally:
            fh.close()
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_removes_a_plain_file_immediately(self):
        # BUG (2026-07-25): shutil.rmtree on a FILE raises NotADirectoryError, an
        # OSError subclass — so the retry loop SWALLOWED it: 6 attempts, ~9.5 s of
        # backoff, then an ignore_errors=True sweep that is a no-op on a file, then
        # PARTIAL. Against the 1814 leaked cb-aura-driver-*.json temp files measured
        # on this box that is ~4.8 HOURS spent deleting exactly zero files. The
        # elapsed assert is the actual regression guard: a "fixed" version that
        # still falls into the loop would pass the existence check.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = Path(d) / "cb-aura-driver-1a2b3c.json"
        f.write_text("{}", encoding="utf-8")
        t0 = time.monotonic()
        self.assertTrue(_robust_rmtree(f))
        self.assertFalse(f.exists())
        self.assertLess(time.monotonic() - t0, 1.0,
                        "a file delete must not burn the tree retry backoff")

    def test_removes_a_symlink_without_following_it(self):
        # The same fast path takes links. It must remove the LINK and leave the
        # target alone — a workdir root reached through <repo>/.cb/wd (the junction
        # `cb where --link` drops) is one bad rmtree away from the real tree.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        target = Path(d) / "target"
        target.mkdir()
        (target / "keep.txt").write_text("x", encoding="utf-8")
        link = Path(d) / "link"
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError) as e:
            self.skipTest(f"symlink creation unavailable on this host ({e}) — "
                          f"Windows needs Developer Mode or an elevated shell")
        self.assertTrue(_robust_rmtree(link))
        self.assertFalse(os.path.lexists(link))
        self.assertTrue((target / "keep.txt").exists(),
                        "the link's TARGET must survive")


class TestCbBackendRouting(unittest.TestCase):
    """The slug taxonomy the shipped CLI routes on.

    Before the public release a bare colon-less key ("sonnet-4.6") meant the
    aura-product lane, and _is_aura_backend covered four aura-* spellings. With
    that lane cut there is exactly one Aura backend left (aura-mcp, disclosed
    but not runnable) and a bare unknown word is no longer a shorthand for
    anything -- _backend_of hands it back verbatim so the refusal can print it.
    """

    def test_colonless_unknown_word_is_returned_verbatim(self):
        # Deliberately NOT a raise: _backend_of is called from inside the
        # f-strings that build the refusal message, so it has to be total.
        self.assertEqual(_backend_of("sonnet-4.6"), "sonnet-4.6")
        self.assertFalse(_is_aura_backend("sonnet-4.6"))

    def test_aura_mcp_is_the_only_aura_backend_left(self):
        for slug in ("aura-mcp", "aura-mcp:claude-haiku-4-5"):
            self.assertEqual(_backend_of(slug), "aura-mcp", slug)
            self.assertTrue(_is_aura_backend(slug), slug)
        # The retired spellings are now just unknown words, not Aura lanes.
        for slug in ("aura-product:sonnet-4.6", "aura-agent:sonnet-4.6",
                     "aura-baseline:sonnet-4.6"):
            self.assertFalse(_is_aura_backend(slug), slug)

    def test_claude_p_routes_to_baseline(self):
        self.assertEqual(_backend_of("claude-p:opus"), "claude-p")
        self.assertFalse(_is_aura_backend("claude-p:opus"))
        self.assertFalse(_is_aura_backend("claude-p"))

    def test_openrouter_routes_to_baseline(self):
        self.assertEqual(_backend_of("openrouter:openai/gpt-5"), "openrouter")
        self.assertFalse(_is_aura_backend("openrouter:openai/gpt-5"))

    def test_unreal_mcp_is_its_own_backend_class(self):
        # unreal-mcp is NEITHER aura NOR baseline: it needs the Epic-MCP editor
        # up, so it routes to _cmd_eval_unreal_mcp.
        from aura_rig.cb import _is_unreal_mcp_backend
        for slug in ("unreal-mcp", "unreal-mcp:claude-haiku-4-5"):
            self.assertEqual(_backend_of(slug), "unreal-mcp", slug)
            self.assertTrue(_is_unreal_mcp_backend(slug), slug)
            self.assertFalse(_is_aura_backend(slug), slug)

    def test_every_routable_backend_is_declared_known(self):
        """The refusal gate reads _KNOWN_BACKENDS; a backend that routes but is
        not listed there would be refused before it could ever run."""
        from aura_rig.cb import _KNOWN_BACKENDS
        for slug in ("claude-p", "openrouter", "bare", "unreal-mcp"):
            self.assertIn(slug, _KNOWN_BACKENDS, slug)


class TestCbEvalRefusesUnroutableModels(unittest.TestCase):
    """OPTION A, the open-source release's central routing decision: the
    `aura-mcp` ARM ships fully disclosed -- adapters/registry.py still
    dispatches it and adapters/aura_mcp_config.py still carries its exact
    --mcp-config and --disallowed-tools, which is the asymmetry the three-arm
    measurement IS -- but its RUNTIME does not, because bringing it up drove a
    proprietary login and two private web services that were deleted rather
    than published.

    Nobody outside the vendor could complete that bring-up anyway, so the
    honest behaviour is a refusal in the first second. `cmd_eval` runs the gate
    BEFORE the env gate, before task resolution and before any child process --
    that ordering is the whole point and is what these tests pin. The old
    aura-product editor-isolation and aura-mcp routing cases lived here until
    2026-08-28; both drove lanes that no longer exist.
    """

    def _ctx(self, calls):
        """A ctx whose every seam RECORDS. A refusal must reach none of them,
        so a regression shows up as an unexpected key rather than a crash."""
        ctx = types.SimpleNamespace()
        ctx.py_exe = "py"
        ctx.py_pre = []
        ctx.ue = Path("C:/UE/Engine/Binaries/Win64/UnrealEditor.exe")
        ctx.paths = types.SimpleNamespace(
            uproject=Path("X.uproject"),
            craftbench=_repo_with_t0(self),
            log=Path(tempfile.gettempdir()))
        ctx.require_stack = lambda *a, **kw: calls.__setitem__("require_stack", True)
        return ctx

    def _args(self, **kw):
        base = dict(model="aura-mcp:claude-haiku-4-5", task="t0", ceiling=900,
                    restart_client=False, restart_editor=False,
                    reuse_editor=False, no_preflight=False)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _eval(self, model):
        """Run cmd_eval with EVERY downstream route sabotaged: if the refusal
        does not fire first, the test fails loudly instead of quietly passing
        because some other guard happened to also return 2."""
        calls, said = {}, []
        orig_baseline = _cb._cmd_eval_baseline
        orig_unreal = _cb._cmd_eval_unreal_mcp
        from aura_rig import envgate as _eg
        orig_enforce = _eg.enforce
        _cb._cmd_eval_baseline = lambda c, a: calls.__setitem__("baseline", True) or 0
        _cb._cmd_eval_unreal_mcp = lambda c, a: calls.__setitem__("unreal", True) or 0
        _eg.enforce = lambda *a, **kw: calls.__setitem__("envgate", True) or True
        try:
            with mock.patch.object(_cb, "_say", said.append):
                rc = _cb.cmd_eval(self._ctx(calls), self._args(model=model))
        finally:
            _cb._cmd_eval_baseline = orig_baseline
            _cb._cmd_eval_unreal_mcp = orig_unreal
            _eg.enforce = orig_enforce
        return rc, calls, "\n".join(said)

    def test_aura_mcp_is_refused_before_anything_starts(self):
        rc, calls, text = self._eval("aura-mcp:claude-haiku-4-5")
        self.assertEqual(rc, 2)
        self.assertEqual(calls, {}, "the refusal must precede EVERY seam — "
                                    "env gate, task resolve, stack, runner")
        self.assertIn("DISCLOSED BUT NOT REPRODUCIBLE", text)

    def test_the_bare_aura_mcp_spelling_is_refused_too(self):
        rc, calls, _ = self._eval("aura-mcp")
        self.assertEqual(rc, 2)
        self.assertEqual(calls, {})

    def test_the_refusal_says_where_the_arm_is_still_readable(self):
        """A refusal that only says "no" reads as the arm being withdrawn. It
        is not: the dispatch and the tool-access config are the published
        measurement, so the message has to name where to read them."""
        _, _, text = self._eval("aura-mcp")
        self.assertIn("adapters/registry.py", text)
        self.assertIn("adapters/aura_mcp_config.py", text)
        # ...and what the reader CAN run instead.
        self.assertIn("claude-p", text)
        self.assertIn("unreal-mcp", text)

    def test_a_retired_bare_slug_is_refused_as_an_unknown_backend(self):
        """"sonnet-4.6" used to mean the aura-product lane. It must not now
        fall through to some other arm and silently measure the wrong thing."""
        rc, calls, text = self._eval("sonnet-4.6")
        self.assertEqual(rc, 2)
        self.assertEqual(calls, {})
        self.assertIn("unknown model backend", text)
        self.assertIn("sonnet-4.6", text, "the refusal must quote the slug back")

    def test_the_shipped_arms_are_NOT_refused(self):
        """The other half of the gate: a guard that refuses everything would
        pass every test above and ship a CLI that runs nothing."""
        for model, key in (("claude-p:sonnet-5", "baseline"),
                           ("openrouter:openai/gpt-5", "baseline"),
                           ("bare:openai/gpt-5", "baseline"),
                           ("unreal-mcp:sonnet-5", "unreal")):
            with self.subTest(model=model):
                rc, calls, _ = self._eval(model)
                self.assertEqual(rc, 0)
                self.assertTrue(calls.get(key), f"{model} never reached a runner")


class TestCbEvalBaselineTouchesNoEditor(unittest.TestCase):
    """The generalist arms get Claude Code's own file tools and no editor at
    all, so cmd_eval must not bring the stack up for them. (This survives from
    the old editor-isolation suite; the rest of that suite pinned the
    aura-product per-drive editor restart and went out with that lane.)"""

    def _ctx(self, calls):
        ctx = types.SimpleNamespace()
        ctx.paths = types.SimpleNamespace(
            uproject=Path("X.uproject"),
            craftbench=_repo_with_t0(self))
        ctx.require_stack = lambda *a, **kw: calls.__setitem__("require_stack", True)
        return ctx

    def test_baseline_backend_never_brings_up_stack(self):
        calls = {}
        orig = _cb._cmd_eval_baseline
        _cb._cmd_eval_baseline = lambda ctx, args: 0   # don't need UE/py here
        try:
            rc = _cb.cmd_eval(self._ctx(calls), types.SimpleNamespace(
                model="claude-p:sonnet", task="t0", ceiling=900,
                restart_client=False, restart_editor=False, reuse_editor=False,
                no_preflight=True))
        finally:
            _cb._cmd_eval_baseline = orig
        self.assertEqual(rc, 0)
        self.assertNotIn("require_stack", calls,
                         "baseline path must not touch the editor")


class TestCbEvalTaskGate(unittest.TestCase):
    """cmd_eval gates the task id BEFORE routing/compose/bring-up: a typo'd id
    must cost <1s and print a did-you-mean, never a full stack bring-up
    (FAILURE-LOG 2026-07-21: 'to-sanity-…' for 't0-sanity-…' burned an entire
    editor-restart cycle before 'task not found')."""

    def _ctx(self, calls, repo):
        ctx = types.SimpleNamespace()
        ctx.paths = types.SimpleNamespace(uproject=Path("X.uproject"), craftbench=repo)
        ctx.require_stack = lambda *a, **kw: calls.__setitem__("require_stack", True)
        return ctx

    def test_typo_fails_fast_with_did_you_mean(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            spec = repo / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "task.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("# t0\n", encoding="utf-8")
            calls = {}
            args = types.SimpleNamespace(
                model="claude-p:sonnet", task="to-sanity-log-on-beginplay",
                ceiling=900, restart_client=False, restart_editor=False,
                reuse_editor=False, no_preflight=True)
            buf = io.StringIO()
            baseline = []
            orig = _cb._cmd_eval_baseline
            _cb._cmd_eval_baseline = lambda c, a: baseline.append(a) or 0
            try:
                with contextlib.redirect_stdout(buf):
                    rc = _cb.cmd_eval(self._ctx(calls, repo), args)
            finally:
                _cb._cmd_eval_baseline = orig
        self.assertEqual(rc, 2)
        self.assertNotIn("require_stack", calls, "gate must fire BEFORE bring-up")
        self.assertEqual(baseline, [], "gate must fire BEFORE the runner")
        out = buf.getvalue()
        self.assertIn("did you mean", out)
        self.assertIn("t0-sanity-log-on-beginplay", out)


class _Phase3EnvGuard(unittest.TestCase):
    """Pops the shared-contract env vars around every test so no assertion can
    leak CB_VISIBLE/CB_CAPTURE/CB_KEEP into a sibling."""

    _ENV = ("CB_VISIBLE", "CB_CAPTURE", "CB_KEEP")

    def setUp(self):
        # These also used to pin CB_LIVE_SUBSTRATE=1, which selected the legacy
        # live-template branch of the aura-product spine. Nothing reads that
        # variable any more (the spine went out with the lane on 2026-08-28),
        # so setting it would only mislead the next reader.
        self._saved = {k: os.environ.pop(k, None) for k in self._ENV}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestCbParserPhase3Flags(unittest.TestCase):
    """The new flags/commands parse (and default OFF)."""

    def test_eval_flags_parse(self):
        args = _cb.build_parser().parse_args(
            ["eval", "--task", "t0", "--visible", "--capture", "--keep"])
        self.assertTrue(args.visible)
        self.assertTrue(args.capture)
        self.assertTrue(args.keep)

    def test_eval_flags_default_off(self):
        args = _cb.build_parser().parse_args(["eval", "--task", "t0"])
        self.assertFalse(args.visible)
        self.assertFalse(args.capture)
        self.assertFalse(args.keep)

    def test_review_command_routes(self):
        args = _cb.build_parser().parse_args(["review", "runs/aura-product/t0-1"])
        self.assertEqual(args.command, "review")
        self.assertEqual(args.outputs, "runs/aura-product/t0-1")
        self.assertIs(_cb._DISPATCH["review"], _cb.cmd_review)

    def test_clean_workdirs_flags_parse(self):
        args = _cb.build_parser().parse_args(
            ["clean", "--workdirs", "--older-than", "3", "--check"])
        self.assertEqual(args.command, "clean")
        self.assertTrue(args.workdirs)
        self.assertEqual(args.older_than, 3)
        self.assertTrue(args.check)

    def test_clean_workdirs_defaults(self):
        args = _cb.build_parser().parse_args(["clean"])
        self.assertFalse(args.workdirs)
        self.assertIsNone(args.older_than)

    # --- `--slim` means one thing alone and another beside --runs --------- #

    def _clean_routes(self, argv):
        """Run cmd_clean with both sweeps stubbed; return which ones fired."""
        fired = []
        args = _cb.build_parser().parse_args(argv)
        orig_r, orig_w = _cb._cmd_clean_runs, _cb._cmd_clean_workdirs
        _cb._cmd_clean_runs = lambda ctx, a: (fired.append("runs"), (0, []))[1]
        _cb._cmd_clean_workdirs = lambda ctx, a, **kw: (fired.append("workdirs"), 0)[1]
        try:
            _cb.cmd_clean(types.SimpleNamespace(paths=None), args)
        finally:
            _cb._cmd_clean_runs, _cb._cmd_clean_workdirs = orig_r, orig_w
        return fired

    def test_bare_slim_still_implies_the_workdir_sweep(self):
        self.assertEqual(self._clean_routes(["clean", "--slim"]), ["workdirs"])

    def test_runs_slim_takes_the_runs_route_only(self):
        # The footgun this closes: `--runs --slim` used to take the --runs
        # DELETE branch (which never read --slim) AND slim workdirs, so the one
        # spelling that plainly means "keep them, just smaller" erased them.
        self.assertEqual(self._clean_routes(["clean", "--runs", "--slim"]), ["runs"])

    def test_workdirs_still_composes_explicitly(self):
        self.assertEqual(
            self._clean_routes(["clean", "--runs", "--slim", "--workdirs"]),
            ["runs", "workdirs"])

    def test_runs_slim_keeps_the_unit_and_drops_only_project_lean(self):
        import tempfile, shutil, json as _json
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        run = tmp / "runs" / "aura-product" / "t0-1"
        (run / "project-lean" / "Content").mkdir(parents=True)
        (run / "project-lean" / "Content" / "big.uasset").write_bytes(b"x" * 8192)
        (run / "summary.json").write_text(_json.dumps({"verdict": "FAIL"}),
                                          encoding="utf-8")
        (run / "l2_pie.log").write_text("[GLIDE] minglide=208.2", encoding="utf-8")
        import os
        old = time.time() - 4 * 3600            # past the in-flight floor
        os.utime(run, (old, old))

        args = _cb.build_parser().parse_args(["clean", "--runs", "--slim"])
        ctx = types.SimpleNamespace(paths=types.SimpleNamespace(craftbench=tmp))
        rc, released = _cb._cmd_clean_runs(ctx, args)

        self.assertEqual(rc, 0)
        self.assertEqual(released, [])          # nothing freed for the workdir sweep
        self.assertTrue(run.is_dir())           # the unit SURVIVES
        self.assertFalse((run / "project-lean").exists())
        self.assertTrue((run / "summary.json").exists())
        self.assertTrue((run / "l2_pie.log").exists())   # re-adjudication evidence


class TestCbEvalModeEnvAndArgv(_Phase3EnvGuard):
    """cmd_eval exports CB_VISIBLE/CB_CAPTURE/CB_KEEP before the graded run;
    the run.py-based paths get the REAL argv (--visible/--capture/
    --keep-workspace) instead."""

    def _fake_ctx(self, calls):
        ctx = types.SimpleNamespace()
        ctx.paths = types.SimpleNamespace(
            uproject=Path("X.uproject"),
            craftbench=_repo_with_t0(self))
        ctx.require_stack = lambda *a, **kw: calls.__setitem__("require_stack", True)
        return ctx

    def _args(self, **kw):
        base = dict(model="claude-p:sonnet", task="t0", ceiling=900,
                    restart_client=False, restart_editor=False, reuse_editor=False,
                    visible=False, capture=False, keep=False,
                    no_preflight=True)  # routing tests skip the envgate (it has its own suite)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _env_at_route(self, calls, args):
        """Run cmd_eval and snapshot the three vars AT THE MOMENT the route is
        entered. That instant is the whole contract: the route shells a child,
        and a var exported after the fork is a var the child never saw.

        The observation point used to be the aura-product spine; that lane was
        cut on 2026-08-28, so it is now the baseline route -- which sits after
        the same _apply_eval_mode_env call in cmd_eval, and is one of the two
        that actually ship."""
        orig = _cb._cmd_eval_baseline

        def fake_baseline(ctx, a):
            calls["route"] = "baseline"
            calls["env_at_drive"] = {k: os.environ.get(k)
                                     for k in ("CB_VISIBLE", "CB_CAPTURE", "CB_KEEP")}
            return 0

        _cb._cmd_eval_baseline = fake_baseline
        try:
            return _cb.cmd_eval(self._fake_ctx(calls), args)
        finally:
            _cb._cmd_eval_baseline = orig

    def test_flags_export_env_before_graded_run(self):
        calls = {}
        rc = self._env_at_route(
            calls, self._args(visible=True, capture=True, keep=True))
        self.assertEqual(rc, 0)
        self.assertEqual(calls["route"], "baseline")
        self.assertEqual(calls["env_at_drive"],
                         {"CB_VISIBLE": "1", "CB_CAPTURE": "1", "CB_KEEP": "1"})

    def test_no_flags_leave_env_untouched(self):
        calls = {}
        self._env_at_route(calls, self._args())
        self.assertEqual(calls["env_at_drive"],
                         {"CB_VISIBLE": None, "CB_CAPTURE": None, "CB_KEEP": None})

    def test_eval_mode_argv_mapping(self):
        self.assertEqual(
            _cb._eval_mode_argv(self._args(visible=True, capture=True, keep=True)),
            ["--visible", "--capture", "--keep-workspace"])
        self.assertEqual(_cb._eval_mode_argv(self._args()), [])

    def test_baseline_forwards_real_argv(self):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = list(cmd)
            return types.SimpleNamespace(returncode=0)

        from aura_rig import tasks as _tasks
        ctx = types.SimpleNamespace(
            py_exe="py", py_pre=[],
            ue=Path("C:/UE/Engine/Binaries/Win64/UnrealEditor.exe"),
            paths=types.SimpleNamespace(uproject=Path("X.uproject"),
                                        craftbench=Path("__cb_no_runs__")))
        orig_run = _cb.subprocess.run
        orig_resolve = _tasks.resolve_task_path
        _cb.subprocess.run = fake_run
        _tasks.resolve_task_path = lambda repo, t: Path("tasks/t0.md")
        try:
            rc = _cb._cmd_eval_baseline(
                ctx, self._args(model="claude-p:sonnet", visible=True,
                                capture=True, keep=True))
        finally:
            _cb.subprocess.run = orig_run
            _tasks.resolve_task_path = orig_resolve
        self.assertEqual(rc, 0)
        self.assertIn("--visible", captured["cmd"])
        self.assertIn("--capture", captured["cmd"])
        self.assertIn("--keep-workspace", captured["cmd"])

    def test_baseline_default_omits_the_flags(self):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = list(cmd)
            return types.SimpleNamespace(returncode=0)

        from aura_rig import tasks as _tasks
        ctx = types.SimpleNamespace(
            py_exe="py", py_pre=[],
            ue=Path("C:/UE/Engine/Binaries/Win64/UnrealEditor.exe"),
            paths=types.SimpleNamespace(uproject=Path("X.uproject"),
                                        craftbench=Path("__cb_no_runs__")))
        orig_run = _cb.subprocess.run
        orig_resolve = _tasks.resolve_task_path
        _cb.subprocess.run = fake_run
        _tasks.resolve_task_path = lambda repo, t: Path("tasks/t0.md")
        try:
            _cb._cmd_eval_baseline(ctx, self._args(model="claude-p:sonnet"))
        finally:
            _cb.subprocess.run = orig_run
            _tasks.resolve_task_path = orig_resolve
        for flag in ("--visible", "--capture", "--keep-workspace"):
            self.assertNotIn(flag, captured["cmd"])


class TestCbCleanWorkdirs(unittest.TestCase):
    """cb clean --workdirs: prune CRAFTBENCH_WD_ROOT dirs not referenced by any
    runs/**/summary.json graded_workdir; --check only reports; --older-than
    age-gates."""

    def test_referenced_workdirs_collects_graded_workdir(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            rd = repo / "runs" / "aura-product" / "t0-1"
            rd.mkdir(parents=True)
            (rd / "summary.json").write_text(
                json.dumps({"graded_workdir": str(repo / "wd" / "keepme")}))
            (repo / "runs" / "junk").mkdir()
            (repo / "runs" / "junk" / "summary.json").write_text("not json{")
            refs = _cb._referenced_workdirs(repo)
            self.assertEqual(refs, {_cb._norm_path(repo / "wd" / "keepme")})

    def test_referenced_workdirs_collects_baseline_result_json(self):
        # Baseline runs (run.py::_write_result) record their pinned workdir in
        # result.json, NOT summary.json — the KEEP set must read both, or
        # `cb clean --workdirs` demotes a retained baseline back to
        # unsupported_until_rebuild.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            rd = repo / "runs" / "baseline" / "t0-1"
            rd.mkdir(parents=True)
            (rd / "result.json").write_text(
                json.dumps({"graded_workdir": str(repo / "wd" / "basekeep")}))
            refs = _cb._referenced_workdirs(repo)
            self.assertEqual(refs, {_cb._norm_path(repo / "wd" / "basekeep")})

    def test_prune_keeps_referenced_deletes_stale(self):
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "cbwd"
            (wd_root / "keepme").mkdir(parents=True)
            (wd_root / "stale").mkdir()
            refs = {_cb._norm_path(wd_root / "keepme")}
            victims = _cb._prune_workdirs(wd_root, refs, check=False,
                                          log=lambda *_a: None)
            self.assertEqual([v.name for v in victims], ["stale"])
            self.assertTrue((wd_root / "keepme").exists())
            self.assertFalse((wd_root / "stale").exists())

    def test_check_mode_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "cbwd"
            (wd_root / "stale").mkdir(parents=True)
            victims = _cb._prune_workdirs(wd_root, set(), check=True,
                                          log=lambda *_a: None)
            self.assertEqual([v.name for v in victims], ["stale"])
            self.assertTrue((wd_root / "stale").exists(), "--check must not delete")

    def test_older_than_gates_young_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "cbwd"
            young = wd_root / "young"
            young.mkdir(parents=True)
            now = young.stat().st_mtime + 1 * 86400  # 1 day later
            victims = _cb._prune_workdirs(wd_root, set(), older_than_days=7,
                                          check=True, now=now,
                                          log=lambda *_a: None)
            self.assertEqual(victims, [])
            victims = _cb._prune_workdirs(wd_root, set(), older_than_days=7,
                                          check=True, now=now + 30 * 86400,
                                          log=lambda *_a: None)
            self.assertEqual([v.name for v in victims], ["young"])


# --------------------------------------------------------------------------- #
# Retention: the in-flight floor, `--slim`, and the bench prune containment gate
# --------------------------------------------------------------------------- #

def _make_workdir(root: Path, name: str, *, age_s: float,
                  project: str = "CraftBenchTemplate") -> Path:
    """A synthetic verifier workdir with the REAL 2026-07-25 shape: the
    ``Intermediate/Build/Win64/x64`` .obj tree and a ``Binaries`` .pdb (together 5.5
    of the 5.54 GB a kept workdir costs), plus the ``.dll`` and ``out/report.json``
    slim must KEEP — the workdir has to stay launchable and still explain its verdict.

    ``age_s`` is stamped LAST: every mkdir under a dir bumps that dir's mtime, so a
    utime before the tree is built measures nothing."""
    wd = root / name
    proj = wd / project
    objs = proj / "Intermediate" / "Build" / "Win64" / "x64"
    objs.mkdir(parents=True)
    (objs / "Module.cpp.obj").write_bytes(b"o" * 4096)
    binw = proj / "Binaries" / "Win64"
    binw.mkdir(parents=True)
    (binw / "UnrealEditor.pdb").write_bytes(b"p" * 2048)
    (binw / "UnrealEditor.dll").write_bytes(b"d" * 16)
    (proj / f"{project}.uproject").write_text("{}", encoding="utf-8")
    (wd / "out").mkdir()
    (wd / "out" / "report.json").write_text("{}", encoding="utf-8")
    t = time.time() - age_s
    os.utime(wd, (t, t))
    return wd


def _run_clean_workdirs(tc: unittest.TestCase, repo: Path, wd_root: Path,
                        **flags) -> list:
    """Drive ``cb clean``'s workdir arm against a SYNTHETIC wd-root, returning the
    captured console lines. ``CRAFTBENCH_WD_ROOT`` is the only machine state touched
    and it is restored, so nothing here can reach the real C:\\cb\\wd."""
    args = types.SimpleNamespace(workdirs=True, slim=False, runs=False,
                                 presnaps=False, check=False, older_than=None,
                                 project="")
    for key, value in flags.items():
        setattr(args, key, value)
    ctx = types.SimpleNamespace(paths=types.SimpleNamespace(craftbench=repo))
    said: list = []
    old_env = os.environ.get("CRAFTBENCH_WD_ROOT")
    old_say = _cb._say
    os.environ["CRAFTBENCH_WD_ROOT"] = str(wd_root)
    _cb._say = lambda m="": said.append(str(m))
    try:
        tc.assertEqual(_cb.cmd_clean(ctx, args), 0)
    finally:
        _cb._say = old_say
        if old_env is None:
            os.environ.pop("CRAFTBENCH_WD_ROOT", None)
        else:
            os.environ["CRAFTBENCH_WD_ROOT"] = old_env
    return said


class TestCbCleanWorkdirsInFlightFloor(unittest.TestCase):
    """BUG (2026-07-25, destructive): `cb clean --workdirs` called the prune with NO
    min_age_s, unlike the presnap sweep right beside it. A workdir mid-L1-build has
    not written summary.json yet, so it reads as "unreferenced" and its whole build
    tree was deleted out from under a live 40-minute run."""

    def test_young_unreferenced_workdir_is_kept(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "runs").mkdir(parents=True)
            root = Path(td) / "wd"
            live = _make_workdir(root, "live00", age_s=120)          # mid-L1-build
            stale = _make_workdir(root, "stale0", age_s=3 * 3600)
            said = _run_clean_workdirs(self, repo, root)
            self.assertTrue(live.is_dir(),
                            "a mid-build workdir must survive the sweep")
            self.assertFalse(stale.is_dir(), "a genuinely stale workdir still goes")
            self.assertTrue(any("in-flight floor" in m for m in said), said)

    def test_the_floor_is_the_runs_clean_one(self):
        # Not a magic number: the workdir sweep and the presnap sweep must protect
        # the same window, or "in flight" means two different things in one command.
        from aura_rig import runs_clean as rcl
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "runs").mkdir(parents=True)
            root = Path(td) / "wd"
            just_under = _make_workdir(root, "under0", age_s=rcl.MIN_AGE_S - 60)
            just_over = _make_workdir(root, "over00", age_s=rcl.MIN_AGE_S + 60)
            _run_clean_workdirs(self, repo, root)
            self.assertTrue(just_under.is_dir())
            self.assertFalse(just_over.is_dir())


class TestCbCleanSlim(unittest.TestCase):
    """`cb clean --workdirs --slim`: reclaim the compiler intermediates IN PLACE from
    EVERY workdir, referenced ones included — those are precisely the dirs no
    existing path can touch (`cb clean --workdirs` keeps them by contract, `cb eval`
    has no prune flag), and they are where the measured 121 GB across 24 workdirs
    against 128 GB free lives."""

    def setUp(self):
        # Exercises the REAL tools/verify-single deleter through the rig's lazy
        # sys.path seam: a stubbed delegate would keep passing while that seam rots.
        if _cb._slim_delegate() is None:
            self.skipTest("fs_cleanup.slim_workdir unavailable in this checkout")

    def _referenced(self, td: Path):
        repo = td / "repo"
        root = td / "wd"
        wd = _make_workdir(root, "ref000", age_s=3 * 3600)
        rd = repo / "runs" / "aura-product" / "t0-1"
        rd.mkdir(parents=True)
        (rd / "summary.json").write_text(
            json.dumps({"graded_workdir": str(wd)}), encoding="utf-8")
        # Sanity anchor: this dir really IS in the KEEP set, so slim is the only
        # route that can ever reclaim its 4.7 GB of .obj.
        self.assertIn(_cb._norm_path(wd), _cb._referenced_workdirs(repo))
        return repo, root, wd

    def test_slims_a_referenced_dir_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            repo, root, wd = self._referenced(Path(td))
            said = _run_clean_workdirs(self, repo, root, slim=True)
            proj = wd / "CraftBenchTemplate"
            self.assertTrue(wd.is_dir(), "--slim must leave the workdir PRESENT")
            self.assertFalse((proj / "Intermediate" / "Build" / "Win64"
                              / "x64").exists())
            self.assertFalse((proj / "Binaries" / "Win64"
                              / "UnrealEditor.pdb").exists())
            self.assertTrue((proj / "Binaries" / "Win64"
                             / "UnrealEditor.dll").exists(),
                            "the graded project must still LAUNCH")
            self.assertTrue((wd / "out" / "report.json").exists(),
                            "the diagnostic out/ dir is the point of keeping it")
            self.assertTrue(any("SLIMMED" in m for m in said), said)

    def test_slim_honors_the_in_flight_floor(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "runs").mkdir(parents=True)
            root = Path(td) / "wd"
            live = _make_workdir(root, "live00", age_s=120)
            objs = live / "CraftBenchTemplate" / "Intermediate" / "Build" / "Win64"
            said = _run_clean_workdirs(self, repo, root, slim=True)
            self.assertTrue((objs / "x64" / "Module.cpp.obj").exists(),
                            "pulling the .obj tree out from under a live cl.exe "
                            "fails the build it is 40 minutes into")
            self.assertTrue(any("KEEP FULL" in m for m in said), said)

    def test_slim_check_mutates_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            repo, root, wd = self._referenced(Path(td))
            before = sorted(p.relative_to(wd).as_posix()
                            for p in wd.rglob("*"))
            said = _run_clean_workdirs(self, repo, root, slim=True, check=True)
            self.assertEqual(before,
                             sorted(p.relative_to(wd).as_posix()
                                    for p in wd.rglob("*")),
                             "--check must not remove a single path")
            self.assertTrue(any("WOULD SLIM" in m for m in said), said)
            # The preview has to name a real number, or it is not a preview.
            self.assertTrue(any("would reclaim" in m and " 0 B " not in m
                                for m in said), said)

    def test_slim_honors_older_than(self):
        with tempfile.TemporaryDirectory() as td:
            repo, root, wd = self._referenced(Path(td))   # 3 h old
            objs = wd / "CraftBenchTemplate" / "Intermediate" / "Build" / "Win64"
            _run_clean_workdirs(self, repo, root, slim=True, older_than=7)
            self.assertTrue((objs / "x64" / "Module.cpp.obj").exists())

    def test_slim_alone_implies_workdirs(self):
        # `cb clean --slim` must reach the workdir arm, not fall through to the
        # scratch-project reset (which would touch the machine, and does nothing a
        # user typing --slim asked for).
        with tempfile.TemporaryDirectory() as td:
            repo, root, wd = self._referenced(Path(td))
            said = _run_clean_workdirs(self, repo, root, workdirs=False, slim=True)
            self.assertTrue(any("clean --workdirs --slim" in m for m in said), said)
            self.assertFalse((wd / "CraftBenchTemplate" / "Intermediate" / "Build"
                              / "Win64" / "x64").exists())


class TestBenchPruneWorkdirContainment(unittest.TestCase):
    """BUG (2026-07-25, destructive): `cb bench --prune-workdirs` rmtree'd
    ``Path(summary["graded_workdir"])`` with no containment check. Under
    CB_WARM_CACHE=1 the verifier grades INSIDE a shared warm slot, so that field can
    name the pool every later rep reuses — one rep's prune wiped the 5x L1 speed-up
    for the rest of the bench."""

    def _prune(self, wd_root: Path, target):
        said: list = []
        old_env = os.environ.get("CRAFTBENCH_WD_ROOT")
        os.environ["CRAFTBENCH_WD_ROOT"] = str(wd_root)
        try:
            gone = _cb._prune_bench_workdir(str(target), log=said.append)
        finally:
            if old_env is None:
                os.environ.pop("CRAFTBENCH_WD_ROOT", None)
            else:
                os.environ["CRAFTBENCH_WD_ROOT"] = old_env
        return gone, said

    def test_refuses_a_graded_workdir_outside_wd_root(self):
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "wd"
            wd_root.mkdir(parents=True)
            pool = Path(td) / "warm-slot"          # the shared pool, NOT in wd_root
            pool.mkdir()
            (pool / "CraftBenchTemplate.uproject").write_text("{}", encoding="utf-8")
            gone, said = self._prune(wd_root, pool)
            self.assertFalse(gone)
            self.assertTrue(pool.is_dir(), "the warm-cache pool must survive")
            self.assertTrue(any("REFUSED" in m for m in said), said)

    def test_refuses_the_wd_root_itself(self):
        # STRICT containment: handing the pool root to the deleter takes out every
        # other rep's workdir in one call, including the ones clean must KEEP.
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "wd"
            (wd_root / "someoneelse").mkdir(parents=True)
            gone, said = self._prune(wd_root, wd_root)
            self.assertFalse(gone)
            self.assertTrue((wd_root / "someoneelse").is_dir())
            self.assertTrue(any("REFUSED" in m for m in said), said)

    def test_prunes_a_real_per_rep_workdir(self):
        with tempfile.TemporaryDirectory() as td:
            wd_root = Path(td) / "wd"
            wd = _make_workdir(wd_root, "rep001", age_s=0)
            gone, said = self._prune(wd_root, wd)
            self.assertTrue(gone)
            self.assertFalse(wd.exists())
            self.assertTrue(any("pruned workdir" in m for m in said), said)


class TestCbCleanPresnaps(unittest.TestCase):
    """cb clean --presnaps: sweep orphaned crash-debris presnap dirs under
    CB_TMP/cb-presnap, keeping anything younger than the in-flight floor;
    --check only reports."""

    def _run(self, tmp: Path, check: bool):
        import os as _os
        args = types.SimpleNamespace(check=check)
        ctx = types.SimpleNamespace()
        old = _os.environ.get("CB_TMP")
        _os.environ["CB_TMP"] = str(tmp)
        try:
            return _cb._cmd_clean_presnaps(ctx, args)
        finally:
            if old is None:
                _os.environ.pop("CB_TMP", None)
            else:
                _os.environ["CB_TMP"] = old

    def test_sweeps_old_keeps_young(self):
        import os as _os
        import time as _time
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "cb-presnap"
            old_snap = root / "t0-crashed"
            young_snap = root / "t0-inflight"
            old_snap.mkdir(parents=True)
            (old_snap / "A.cpp").write_text("x")
            young_snap.mkdir()
            t = _time.time() - 2 * 3600
            _os.utime(old_snap, (t, t))
            rc = self._run(Path(td), check=False)
            self.assertEqual(rc, 0)
            self.assertFalse(old_snap.exists())
            self.assertTrue(young_snap.exists())

    def test_check_mode_deletes_nothing(self):
        import os as _os
        import time as _time
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "cb-presnap"
            snap = root / "t0-crashed"
            snap.mkdir(parents=True)
            t = _time.time() - 2 * 3600
            _os.utime(snap, (t, t))
            rc = self._run(Path(td), check=True)
            self.assertEqual(rc, 0)
            self.assertTrue(snap.exists(), "--check must not delete")


class TestCbReview(unittest.TestCase):
    """cb review <run-dir>: overlays deliverable/ onto the SCRATCH (never the
    template), prints artifacts, launches the windowed editor detached."""

    def test_latest_picks_newest_run_with_deliverable(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Tracks must come from cb._DELIVERABLE_TRACKS; the aura-drive /
            # aura-product tracks went with that lane.
            drive = base / "runs" / "unreal-mcp"
            prod = base / "runs" / "claude-p"
            # older run WITH deliverable, newer one WITHOUT, newest WITH.
            for name, root, has in (("drive-old", drive, True),
                                    ("t0-new", prod, False),
                                    ("drive-new", drive, True)):
                d = root / name
                d.mkdir(parents=True)
                if has:
                    (d / "deliverable").mkdir()
                    (d / "deliverable" / "x.uasset").write_text("x")
                os.utime(d, None)
            # force drive-new to be newest by mtime
            import time as _t
            _t.sleep(0.02)
            (drive / "drive-new").touch()
            os.utime(drive / "drive-new", None)
            ctx = types.SimpleNamespace(
                paths=types.SimpleNamespace(craftbench=base))
            newest = _cb._newest_run_with_deliverable(ctx)
            self.assertIsNotNone(newest)
            self.assertEqual(newest.name, "drive-new")
            # the deliverable-less prod run is never chosen
            self.assertNotEqual(newest.name, "t0-new")

    def test_review_overlays_scratch_and_launches_editor(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            run_dir = base / "runs" / "unreal-mcp" / "t0-1"
            (run_dir / "deliverable" / "Source").mkdir(parents=True)
            (run_dir / "deliverable" / "Source" / "X.cpp").write_text("cpp")
            (run_dir / "summary.json").write_text(
                json.dumps({"artifacts": ["artifacts/s.png"]}))
            scratch = base / "scratch"
            scratch.mkdir()
            (scratch / "CraftBenchTemplate.uproject").write_text("{}")
            # Template Content the review reset mirrors over the scratch first
            # (clean-sheet-per-run — added 2026-07-29).
            template = base / "template"
            (template / "Content").mkdir(parents=True)
            (template / "Content" / "Keep.uasset").write_text("x")

            popen_calls = []
            said = []
            orig = (_cb.stack.get_drive_project_dir,
                    _cb.stack.initialize_drive_project,
                    _cb._stop_headless_editor, _cb.subprocess.Popen,
                    _cb.time.sleep, _cb._say)
            _cb.stack.get_drive_project_dir = lambda explicit="": scratch
            _cb.stack.initialize_drive_project = lambda d, p, log=None: True
            _cb._stop_headless_editor = lambda: None
            _cb.subprocess.Popen = (
                lambda cmd, **kw: popen_calls.append(list(cmd)) or
                types.SimpleNamespace())
            _cb.time.sleep = lambda _s: None
            _cb._say = lambda m="": said.append(str(m))
            try:
                ctx = types.SimpleNamespace(
                    ue=Path("C:/UE/UnrealEditor.exe"),
                    paths=types.SimpleNamespace(craftbench=base,
                                                template_dir=template))
                args = types.SimpleNamespace(outputs=str(run_dir), run="",
                                             project="", map="", latest=False,
                                             keep=False)
                rc = _cb.cmd_review(ctx, args)
            finally:
                (_cb.stack.get_drive_project_dir,
                 _cb.stack.initialize_drive_project,
                 _cb._stop_headless_editor, _cb.subprocess.Popen,
                 _cb.time.sleep, _cb._say) = orig

            self.assertEqual(rc, 0)
            # Deliverable landed on the SCRATCH project.
            self.assertTrue((scratch / "Source" / "X.cpp").exists())
            # The windowed editor launched on the scratch uproject.
            self.assertEqual(len(popen_calls), 1)
            self.assertIn(str(scratch / "CraftBenchTemplate.uproject"),
                          popen_calls[0])
            # The artifacts from summary.json were printed.
            self.assertTrue(any("s.png" in m for m in said))

    def test_review_requires_a_run_dir(self):
        _cb_say, _cb._say = _cb._say, lambda m="": None
        try:
            ctx = types.SimpleNamespace(ue=Path("UE.exe"),
                                        paths=types.SimpleNamespace())
            args = types.SimpleNamespace(outputs="", run="", project="", map="")
            self.assertEqual(_cb.cmd_review(ctx, args), 2)
            args = types.SimpleNamespace(outputs="__no_such_dir__", run="",
                                         project="", map="")
            self.assertEqual(_cb.cmd_review(ctx, args), 2)
        finally:
            _cb._say = _cb_say


class TestKeepWorkdirFlag(unittest.TestCase):
    """`--keep-workdir` is the CLI opt-out of slim retention.

    It exists because every OTHER retention-ish control on `cb eval` is a flag
    (--keep / --capture / --visible / --preview) while retention was env-only, so
    "how do I keep the workdir?" had no answer in `cb --help`. It must not be
    confused with --keep: project-lean/ EXCLUDES Binaries+Intermediate and cannot
    be rebuilt; --keep-workdir preserves the real built workdir."""

    def setUp(self):
        self._prev = os.environ.pop("CB_WORKDIR_RETENTION", None)

    def tearDown(self):
        os.environ.pop("CB_WORKDIR_RETENTION", None)
        if self._prev is not None:
            os.environ["CB_WORKDIR_RETENTION"] = self._prev

    def test_flag_sets_full_retention(self):
        _cb._apply_eval_mode_env(types.SimpleNamespace(keep_workdir=True))
        self.assertEqual(os.environ.get("CB_WORKDIR_RETENTION"), "full")

    def test_absent_flag_leaves_env_untouched(self):
        # Set-only on opt-in: an operator who exported CB_WORKDIR_RETENTION=none
        # must not have it silently reset just because the flag was not passed.
        os.environ["CB_WORKDIR_RETENTION"] = "none"
        _cb._apply_eval_mode_env(types.SimpleNamespace(keep_workdir=False))
        self.assertEqual(os.environ.get("CB_WORKDIR_RETENTION"), "none")

    def test_flag_actually_changes_the_resolved_mode(self):
        # Guard the whole chain, not just the env write.
        from aura_rig import workdir_retention as _wr
        self.assertEqual(_wr.resolve_mode(), "slim")
        _cb._apply_eval_mode_env(types.SimpleNamespace(keep_workdir=True))
        self.assertEqual(_wr.resolve_mode(), "full")

    def test_keep_and_keep_workdir_are_independent(self):
        # --keep must NOT imply full retention (they preserve different things).
        _cb._apply_eval_mode_env(types.SimpleNamespace(keep=True, keep_workdir=False))
        self.assertEqual(os.environ.get("CB_KEEP"), "1")
        self.assertIsNone(os.environ.get("CB_WORKDIR_RETENTION"))


class TestBenchResumeRestoresPlan(unittest.TestCase):
    """`cb bench --resume` must restore the PLAN from bench.json, not silently
    fall back to the flag defaults.

    The hazard this guards (measured 2026-07-25): --resume suppresses the wizard
    — the only thing stopping a bare invocation running the opus-4.8 x t0 x 3
    defaults — so a bare `--resume` re-parsed those defaults. And because
    bench.run keys reuse on (model, task_id, rep), a resumed sonnet plan matched
    NONE of its own cached reps, so the whole set re-ran at ~3x the cost into the
    same bench dir."""

    def _bench_dir(self, payload: dict) -> str:
        d = tempfile.mkdtemp(prefix="cb-resume-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (Path(d) / "bench.json").write_text(json.dumps(payload), encoding="utf-8")
        return d

    def test_plan_round_trips_in_cli_flag_syntax(self) -> None:
        # The restored strings are fed straight back to parse_models /
        # parse_task_spec, so they must be in the CLI's own syntax.
        d = self._bench_dir({
            "models": ["claude-p:sonnet", "sonnet-5"],
            "task_specs": [{"task_id": "cpp/t0-sanity-log-on-beginplay",
                            "reps": 12}],
        })
        plan = _cb._load_prior_plan(d)
        self.assertEqual(plan["model"], "claude-p:sonnet,sonnet-5")
        self.assertEqual(plan["task"], "cpp/t0-sanity-log-on-beginplay:12")

    def test_multi_task_plan_keeps_per_task_reps(self) -> None:
        d = self._bench_dir({
            "models": ["sonnet-5"],
            "task_specs": [{"task_id": "a", "reps": 3}, {"task_id": "b", "reps": 1}],
        })
        self.assertEqual(_cb._load_prior_plan(d)["task"], "a:3,b:1")

    def test_corrupt_or_missing_bench_json_returns_none(self) -> None:
        # None is the REFUSE signal — cmd_bench must not spend on defaults.
        self.assertIsNone(_cb._load_prior_plan(tempfile.mkdtemp()))
        d = tempfile.mkdtemp(prefix="cb-resume-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (Path(d) / "bench.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(_cb._load_prior_plan(d))

    def test_empty_plan_returns_none_rather_than_an_empty_run(self) -> None:
        self.assertIsNone(_cb._load_prior_plan(
            self._bench_dir({"models": [], "task_specs": []})))
        self.assertIsNone(_cb._load_prior_plan(
            self._bench_dir({"models": ["sonnet-5"], "task_specs": []})))

    def _repo_with_runs(self) -> Path:
        repo = Path(tempfile.mkdtemp(prefix="cb-resume-repo-"))
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        (repo / "runs").mkdir()
        return repo

    def test_resolve_resume_dir_picks_newest_for_latest(self) -> None:
        repo = self._repo_with_runs()
        old, new = repo / "runs" / "bench-old", repo / "runs" / "bench-new"
        for d in (old, new):
            d.mkdir()
            (d / "bench.json").write_text("{}", encoding="utf-8")
        os.utime(old, (1, 1))  # force old to be older regardless of creation order
        args = types.SimpleNamespace(resume="__latest__")
        self.assertEqual(_cb._resolve_resume_dir(args, repo), str(new))

    def test_latest_ignores_a_newer_bench_file(self) -> None:
        # The incident (FAILURE-LOG 2026-08-05): a stray `bench-resume3.out.log`
        # FILE in runs/ outran every real bench dir on mtime, and resume then
        # died reading bench.json "at ...out.log". Only a DIRECTORY holding a
        # readable bench.json may qualify.
        repo = self._repo_with_runs()
        real = repo / "runs" / "bench-20260805-044144"
        real.mkdir()
        (real / "bench.json").write_text("{}", encoding="utf-8")
        os.utime(real, (1, 1))  # the stray file below wins on mtime alone
        (repo / "runs" / "bench-resume3.out.log").write_text("log", encoding="utf-8")
        args = types.SimpleNamespace(resume="__latest__")
        self.assertEqual(_cb._resolve_resume_dir(args, repo), str(real))

    def test_resolve_resume_dir_passes_a_qualifying_explicit_path_through(self) -> None:
        d = self._bench_dir({"models": ["sonnet-5"], "task_specs": []})
        args = types.SimpleNamespace(resume=d)
        self.assertEqual(_cb._resolve_resume_dir(args, Path(".")), d)

    def test_explicit_path_without_bench_json_is_none(self) -> None:
        # Same REFUSE signal as the bare form: pointing --resume at a dir with
        # no bench.json must never fall through to a fresh-spend bench dir.
        d = tempfile.mkdtemp(prefix="cb-resume-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        args = types.SimpleNamespace(resume=d)
        self.assertIsNone(_cb._resolve_resume_dir(args, Path(".")))

    def test_latest_with_no_bench_dirs_is_none(self) -> None:
        repo = self._repo_with_runs()
        args = types.SimpleNamespace(resume="__latest__")
        self.assertIsNone(_cb._resolve_resume_dir(args, repo))

    def test_latest_with_no_qualifying_dir_is_none(self) -> None:
        # bench-* entries exist but none qualifies (a dir without bench.json,
        # a plain file) — None, so cmd_bench REFUSES instead of resuming junk.
        repo = self._repo_with_runs()
        (repo / "runs" / "bench-empty").mkdir()
        (repo / "runs" / "bench-note.txt").write_text("x", encoding="utf-8")
        args = types.SimpleNamespace(resume="__latest__")
        self.assertIsNone(_cb._resolve_resume_dir(args, repo))

    def test_cmd_bench_refuses_an_unqualifying_resume_target(self) -> None:
        # exit 2 BEFORE plan restore / envgate / any spend, naming the target.
        d = tempfile.mkdtemp(prefix="cb-resume-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        ctx = types.SimpleNamespace(paths=types.SimpleNamespace(craftbench=Path(d)))
        args = types.SimpleNamespace(resume=str(Path(d) / "bench-gone"))
        said = []
        with mock.patch.object(_cb, "_say", lambda m="": said.append(str(m))):
            rc = _cb.cmd_bench(ctx, args)
        self.assertEqual(rc, 2)
        self.assertIn("no bench dir with a readable bench.json", "\n".join(said))



class TestWorkdirShapeGate(unittest.TestCase):
    r"""`require_project_shape` — what makes sweeping a TEMP root safe.

    `cb clean --workdirs` grew C:\cbtmp coverage on 2026-08-20. wd_root() is
    ours by construction so every child there stays eligible, but a root reached
    through CB_TMP/TEMP is only *conventionally* ours — an operator who points
    CB_TMP at something shared must not have its siblings deleted. Shape ("does
    this child hold a .uproject?") is the check that survives that mistake.
    """

    @staticmethod
    def _staged(parent, name, *mids):
        """A staged workdir: <name>/<mids...>/ThirdPerson/ThirdPerson.uproject"""
        proj = parent.joinpath(name, *mids) / "ThirdPerson"
        proj.mkdir(parents=True)
        (proj / "ThirdPerson.uproject").write_text("{}", encoding="utf-8")
        return parent / name

    def test_shape_gate_spares_dirs_that_are_not_workdirs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "cbtmp"
            root.mkdir()
            self._staged(root, "crw-20260820-014157")
            (root / "someone-elses-data").mkdir()
            (root / "someone-elses-data" / "notes.txt").write_text("x")
            victims = _cb._prune_workdirs(root, set(), check=True,
                                          require_project_shape=True,
                                          log=lambda *_a: None)
            self.assertEqual([v.name for v in victims],
                             ["crw-20260820-014157"])
            self.assertTrue((root / "someone-elses-data").exists())

    def test_no_shape_gate_keeps_the_old_wd_root_contract(self):
        # wd_root() holds plain backup dirs (scaffold-backup, umap-backup-*)
        # that carry no .uproject and MUST stay collectable.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wd"
            root.mkdir()
            (root / "scaffold-backup").mkdir()
            victims = _cb._prune_workdirs(root, set(), check=True,
                                          log=lambda *_a: None)
            self.assertEqual([v.name for v in victims], ["scaffold-backup"])

    def test_uproject_detected_to_three_levels_and_no_further(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            flat = root / "flat"
            flat.mkdir()
            (flat / "ThirdPerson.uproject").write_text("{}", encoding="utf-8")
            self.assertTrue(_cb._looks_like_workdir(flat))
            self.assertTrue(_cb._looks_like_workdir(self._staged(root, "one")))
            self.assertTrue(
                _cb._looks_like_workdir(self._staged(root, "two", "scratch")))
            # four levels deep is outside the bounded glob, by design
            deep = self._staged(root, "deep", "a", "b")
            self.assertFalse(_cb._looks_like_workdir(deep))
            bare = root / "bare"
            bare.mkdir()
            self.assertFalse(_cb._looks_like_workdir(bare))

    def test_slim_shape_gate_spares_non_workdirs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "cbtmp"
            root.mkdir()
            (root / "not-a-workdir").mkdir()
            seen = []
            n, total = _cb._slim_workdirs(root, check=True,
                                          require_project_shape=True,
                                          log=lambda m: seen.append(m))
            self.assertEqual((n, total), (0, 0))
            self.assertTrue(any("not a staged workdir" in m for m in seen),
                            seen)

if __name__ == "__main__":
    unittest.main()


# TestBenchTeardown stood here until the 2026-08-28 public release. It pinned
# cb._bench_teardown, which stopped the web stack a bench had brought up -- and
# was deliberately SCOPED to benches that ran aura-product models, since a
# baseline-only bench never starts a stack and must not kill one the operator
# started for their own work. With that lane cut there is no stack for a bench
# to bring up, and the helper went with it. `cb eval --teardown` still runs for
# every route (_maybe_eval_teardown), which is the contract that survived.

class TestEveryVerifierCallTakesItsWorkdirArgsFromOneHelper(unittest.TestCase):
    """`--warm-cache` and `--workdir` are mutually exclusive.

    run_task reads an explicit ``--workdir`` as force-cold, so a verifier call
    site that assembles its own workdir args silently builds cold on that route
    while the operator believes the pool is on. Both spines in run.py (the
    workspace one and --live-project) must therefore route through
    ``_verifier_workdir_args``. This drift is what made cb.py's warm-cache
    warning false: run.py grew forwarding on both spines and the warning went on
    claiming the aura-mcp route could not honor the flag.
    """

    def test_no_verifier_command_assembles_its_own_workdir_args(self):
        src = (Path(__file__).resolve().parents[1] / "run.py").read_text(
            encoding="utf-8")
        builds = len(re.findall(r"verifier_cmd\s*=\s*\[", src))
        routed = len(re.findall(
            r"verifier_cmd\s*\+=\s*_verifier_workdir_args\(", src))
        self.assertEqual(
            builds, routed,
            f"{builds} verifier command(s) built but {routed} routed through "
            "_verifier_workdir_args; an unrouted call site pins --workdir and "
            "so builds cold even under CB_WARM_CACHE")


# TestThreadsAlreadyUsed stood here until the 2026-08-28 public release. It
# pinned cb's cross-run thread scan, which fed bench.flag_thread_reuse: an Aura
# CHAT THREAD id, harvested from summary.json, is what a rep could accidentally
# re-use, and threads only ever existed on the aura-product lane. The scanner
# went out with it. bench.py still carries the THREAD-REUSED verdict and its
# flagging (see test_bench.py) -- what no longer exists is a producer for the
# known_threads map it takes.
