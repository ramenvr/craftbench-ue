"""Launcher tests — JobManager lifecycle, input validation, injection safety.

Feature #3 ("LAUNCH-A-RUN"). These tests NEVER spawn UnrealEditor or the real
``tools/run-agent/run.py``: every JobManager is constructed with an INJECTED
``command_builder`` that returns a harmless ``[sys.executable, "-c", "..."]``
echo argv. A real launch only happens when a live user clicks in the UI.

What we pin:
  * a job goes queued/running → done with the subprocess's captured stdout in .log
  * a non-zero exit flips the terminal status to ``failed`` (not ``done``)
  * an unknown task_id and a bad model slug are REJECTED before any spawn
  * crafted injection-y task_id / model strings cannot escape (argv-only):
      - the validators reject shell metacharacters outright, AND
      - the default builder produces a LIST (never a shell string), AND
      - even if a malicious string reached Popen it stays a single argv element.

Pure ``unittest``; stdlib only. Run from the repo root via the venv:

    tools/dashboard/.venv/bin/python -m unittest \
        tools.dashboard.web.tests.test_launcher
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from tools.dashboard.web import launcher
from tools.dashboard.web.launcher import (
    JobManager,
    available_models,
    available_tasks,
    default_run_agent_command,
    resolve_task_path,
    validate_model,
)


# --- fake injectable builders ----------------------------------------------

def _echo_builder(*, task_path, model, repo_root, ue_root=None,
                  live_project=False, extra_args=None):
    """A harmless argv that prints a marker and exits 0 — NEVER run.py / UE."""
    return [sys.executable, "-c",
            f"import sys; print('ran {task_path.stem} via {model}'); sys.exit(0)"]


def _failing_builder(*, task_path, model, repo_root, ue_root=None,
                     live_project=False, extra_args=None):
    """A harmless argv that exits non-zero, to exercise the failed path."""
    return [sys.executable, "-c", "import sys; sys.exit(7)"]


def _capture_builder(sink):
    """Builder that records the argv it produced (so a test can inspect it),
    then returns a harmless exit-0 echo so no real process is run."""
    def build(*, task_path, model, repo_root, ue_root=None,
              live_project=False, extra_args=None):
        argv = default_run_agent_command(
            task_path=task_path, model=model, repo_root=repo_root,
            ue_root=ue_root, live_project=live_project, extra_args=extra_args,
        )
        sink.append(argv)
        return [sys.executable, "-c", "pass"]
    return build


def _build_repo(root: Path) -> None:
    """Minimal repo with real task specs in BOTH layouts (existence is what matters):
    two root flat specs, a set-dir flat spec, a folder-form spec, and set-dir
    docs (README/CATALOG) that must never surface as tasks."""
    tasks = root / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / "gp-spawn-sequence.md").write_text("# task\n", encoding="utf-8")
    (tasks / "t0-sanity-log-on-beginplay.md").write_text("# task\n", encoding="utf-8")
    flagship = tasks / "flagship"
    flagship.mkdir()
    (flagship / "some-id.md").write_text("# task\n", encoding="utf-8")
    (flagship / "folder-task").mkdir()
    (flagship / "folder-task" / "task.md").write_text("# task\n", encoding="utf-8")
    (flagship / "README.md").write_text("# not a task\n", encoding="utf-8")
    (flagship / "CATALOG.md").write_text("# not a task\n", encoding="utf-8")


class LauncherBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

class TestDiscovery(LauncherBase):
    def test_available_tasks_lists_both_layouts(self):
        # Root specs list bare; set-dir specs (flat OR folder-form) list
        # set-qualified; README/CATALOG never surface.
        tasks = available_tasks(self.root)
        self.assertEqual(
            tasks, ["flagship/folder-task", "flagship/some-id",
                    "gp-spawn-sequence", "t0-sanity-log-on-beginplay"])

    def test_available_tasks_empty_when_no_tasks_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(available_tasks(Path(d)), [])

    def test_every_available_task_resolves(self):
        # The listed ids are exactly the launchable set — each must round-trip
        # through resolve_task_path without error.
        for tid in available_tasks(self.root):
            self.assertTrue(resolve_task_path(tid, self.root).is_file(), tid)

    def test_available_models_are_all_valid_slugs(self):
        for slug in available_models():
            # Each seeded slug must itself pass the gate.
            self.assertEqual(validate_model(slug), slug)


# ---------------------------------------------------------------------------
# Validation (pre-spawn)
# ---------------------------------------------------------------------------

class TestValidation(LauncherBase):
    def test_resolve_task_path_accepts_real_task(self):
        p = resolve_task_path("gp-spawn-sequence", self.root)
        self.assertTrue(p.is_file())
        self.assertEqual(p.name, "gp-spawn-sequence.md")

    def test_resolve_task_path_rejects_unknown(self):
        with self.assertRaises(ValueError):
            resolve_task_path("does-not-exist", self.root)

    def test_resolve_task_path_rejects_traversal(self):
        # ../ escape must be refused even if a file happens to exist elsewhere.
        with self.assertRaises(ValueError):
            resolve_task_path("../tasks/gp-spawn-sequence", self.root)
        with self.assertRaises(ValueError):
            resolve_task_path("../../etc/passwd", self.root)

    def test_resolve_set_qualified_flat_spec(self):
        p = resolve_task_path("flagship/some-id", self.root)
        self.assertTrue(p.is_file())
        self.assertEqual(p.name, "some-id.md")
        self.assertEqual(p.parent.name, "flagship")

    def test_resolve_set_qualified_folder_form_spec(self):
        p = resolve_task_path("flagship/folder-task", self.root)
        self.assertTrue(p.is_file())
        self.assertEqual(p.name, "task.md")
        self.assertEqual(p.parent.name, "folder-task")

    def test_resolve_bare_id_unique_in_a_set(self):
        # A bare id with no root spec and exactly ONE set match resolves.
        p = resolve_task_path("folder-task", self.root)
        self.assertEqual(p, resolve_task_path("flagship/folder-task", self.root))

    def test_resolve_bare_id_root_wins_set_dup(self):
        # Add a set-level duplicate of a root task: the ROOT spec must win.
        dup = self.root / "tasks" / "flagship" / "gp-spawn-sequence.md"
        dup.write_text("# dup\n", encoding="utf-8")
        p = resolve_task_path("gp-spawn-sequence", self.root)
        self.assertEqual(p.parent.name, "tasks")

    def test_resolve_bare_id_ambiguous_across_sets_rejected(self):
        # The same bare id in TWO sets (and no root spec) must be rejected —
        # the caller has to pass the set-qualified form.
        other = self.root / "tasks" / "other-set"
        other.mkdir()
        (other / "some-id.md").write_text("# task\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            resolve_task_path("some-id", self.root)
        # Qualified forms still resolve fine.
        self.assertTrue(resolve_task_path("flagship/some-id", self.root).is_file())
        self.assertTrue(resolve_task_path("other-set/some-id", self.root).is_file())

    def test_resolve_folder_form_wins_flat_sibling_in_same_set(self):
        # Both shapes for one id in one set: the folder form wins (mirrors the
        # harness-side resolver).
        flat = self.root / "tasks" / "flagship" / "folder-task.md"
        flat.write_text("# flat sibling\n", encoding="utf-8")
        p = resolve_task_path("flagship/folder-task", self.root)
        self.assertEqual(p.name, "task.md")

    def test_resolve_rejects_set_qualified_traversal_shapes(self):
        # Every component must match TASK_ID_RE; >2 components are refused.
        for bad in ("flagship/../gp-spawn-sequence",   # 3 components after split
                    "flagship/..",                      # '..' component
                    "../flagship/some-id",              # leading '..'
                    "..%2F..%2Fetc%2Fpasswd",           # %-encoded separators
                    "flagship\\some-id",                # backslash separator
                    "a/b/c",                            # too many components
                    "flagship/",                        # empty component
                    "/some-id",                         # empty component
                    ".hidden/some-id",                  # leading-dot component
                    ""):                                # empty id
            with self.assertRaises(ValueError, msg=bad):
                resolve_task_path(bad, self.root)

    def test_resolve_rejects_non_task_docs(self):
        # README/CATALOG (root or set-level) and a stray set-level task.md are
        # never resolvable as tasks.
        (self.root / "tasks" / "CATALOG.md").write_text("# doc\n", encoding="utf-8")
        (self.root / "tasks" / "flagship" / "task.md").write_text(
            "# misplaced\n", encoding="utf-8")
        for bad in ("CATALOG", "flagship/README", "flagship/CATALOG",
                    "flagship/task"):
            with self.assertRaises(ValueError, msg=bad):
                resolve_task_path(bad, self.root)

    def test_resolve_rejects_symlink_escape(self):
        # A set dir symlinked to OUTSIDE tasks/ must not resolve, even though
        # the un-resolved candidate path looks contained.
        outside = self.root / "outside-set"
        outside.mkdir()
        (outside / "victim.md").write_text("# outside\n", encoding="utf-8")
        link = self.root / "tasks" / "evil-set"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):  # no symlink privilege (Windows)
            self.skipTest("symlinks unavailable on this platform/user")
        with self.assertRaises(ValueError):
            resolve_task_path("evil-set/victim", self.root)

    def test_validate_model_accepts_known_slugs(self):
        # One per RUNNABLE make_adapter() branch, in both id shapes: a native
        # Claude id for the two `claude -p` backends, a provider/model
        # OpenRouter id for the two that address OpenRouter.
        for slug in ("claude-p:opus", "claude-p:claude-sonnet-5",
                     "unreal-mcp:claude-sonnet-5",
                     "openrouter:openai/gpt-5.6-terra",
                     "bare:deepseek/deepseek-v4-pro-0813"):
            self.assertEqual(validate_model(slug), slug)

    def test_validate_model_rejects_unknown_backend(self):
        with self.assertRaises(ValueError):
            validate_model("gpt:4")
        with self.assertRaises(ValueError):
            validate_model("claude-p")  # bare backend, no model component

    def test_validate_model_refuses_unlaunchable_backends_by_name(self):
        # aura-mcp is dispatchable in the adapter registry but its MCP servers
        # ship with a plugin this repository does not carry; the private lanes
        # were removed outright. Both must be refused with a message that names
        # the backend and says why — a bare regex miss reads like a typo.
        for slug, backend in (("aura-mcp:claude-sonnet-5", "aura-mcp"),
                              ("aura-agent:claude-sonnet-5", "aura-agent"),
                              ("aura-product:claude-sonnet-5", "aura-product"),
                              ("aura-baseline:claude-sonnet-5", "aura-baseline"),
                              ("aura-mcp-bridge:claude-haiku-4-5-20251001",
                               "aura-mcp-bridge")):
            with self.assertRaises(ValueError, msg=slug) as cm:
                validate_model(slug)
            self.assertIn(backend, str(cm.exception))
            self.assertIn("cannot be launched", str(cm.exception))

    def test_validate_model_rejects_shell_metacharacters(self):
        # Includes the trailing-newline case: `$` would have matched before it,
        # so the anchor is `\Z`.
        for bad in ("claude-p:opus; rm -rf /", "claude-p:$(whoami)",
                    "claude-p:opus`id`", "claude-p:opus && touch pwned",
                    "claude-p:opus|cat", "claude-p:opus\nrm", "claude-p:opus\n",
                    "unreal-mcp:a b", "bare:../../etc/passwd",
                    "openrouter:.hidden/x", "openrouter:a//b", "bare:x/"):
            with self.assertRaises(ValueError, msg=bad):
                validate_model(bad)


# ---------------------------------------------------------------------------
# Job lifecycle with an INJECTED fake command
# ---------------------------------------------------------------------------

class TestJobLifecycle(LauncherBase):
    def test_job_runs_to_done_with_captured_output(self):
        jm = JobManager(self.root, command_builder=_echo_builder)
        job_id = jm.start("gp-spawn-sequence", "claude-p:opus")
        # start() returns once the process is spawned → status is running/done.
        self.assertIn(jm.status(job_id)["status"], ("running", "done"))
        final = jm.wait(job_id, timeout=30)
        self.assertEqual(final["status"], "done")
        self.assertEqual(final["returncode"], 0)
        self.assertIn("ran gp-spawn-sequence via claude-p:opus", final["log"])
        self.assertIsNotNone(final["started_at"])
        self.assertIsNotNone(final["finished_at"])
        self.assertIsNotNone(final["duration_s"])

    def test_set_qualified_task_id_launches(self):
        # A "<set>/<id>" id (folder-form spec) goes through the same validated
        # start path as a bare root id.
        jm = JobManager(self.root, command_builder=_echo_builder)
        job_id = jm.start("flagship/folder-task", "claude-p:opus")
        final = jm.wait(job_id, timeout=30)
        self.assertEqual(final["status"], "done")
        self.assertEqual(final["task_id"], "flagship/folder-task")

    def test_nonzero_exit_marks_failed(self):
        jm = JobManager(self.root, command_builder=_failing_builder)
        # a launchable arm: aura-mcp is refused by validate_model, and this
        # test is about the exit-code -> job-state mapping, not the guard.
        job_id = jm.start("t0-sanity-log-on-beginplay", "claude-p:claude-sonnet-4-6")
        final = jm.wait(job_id, timeout=30)
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["returncode"], 7)

    def test_list_returns_started_jobs_newest_first(self):
        jm = JobManager(self.root, command_builder=_echo_builder)
        a = jm.start("gp-spawn-sequence", "claude-p:opus")
        b = jm.start("t0-sanity-log-on-beginplay", "claude-p:sonnet")
        jm.wait(a, timeout=30)
        jm.wait(b, timeout=30)
        listing = jm.list()
        self.assertEqual(len(listing), 2)
        ids = [j["job_id"] for j in listing]
        self.assertEqual(set(ids), {a, b})
        # newest-first ordering by created_at
        self.assertEqual(ids[0], b)

    def test_status_unknown_job_is_none(self):
        jm = JobManager(self.root, command_builder=_echo_builder)
        self.assertIsNone(jm.status("nope"))
        self.assertIsNone(jm.wait("nope", timeout=1))

    def test_status_envelope_is_json_safe(self):
        import json
        jm = JobManager(self.root, command_builder=_echo_builder)
        job_id = jm.start("gp-spawn-sequence", "claude-p:opus")
        env = jm.wait(job_id, timeout=30)
        # No Popen handle leaks; the whole envelope round-trips through JSON.
        self.assertNotIn("_proc", env)
        json.dumps(env)  # raises if anything is not JSON-serializable


# ---------------------------------------------------------------------------
# Rejection BEFORE any spawn
# ---------------------------------------------------------------------------

class TestRejectionBeforeSpawn(LauncherBase):
    def test_unknown_task_rejected_no_spawn(self):
        spawned = []
        jm = JobManager(self.root, command_builder=_capture_builder(spawned))
        with self.assertRaises(ValueError):
            jm.start("totally-made-up", "claude-p:opus")
        self.assertEqual(jm.list(), [])       # no job registered
        self.assertEqual(spawned, [])         # builder never invoked

    def test_bad_model_rejected_no_spawn(self):
        spawned = []
        jm = JobManager(self.root, command_builder=_capture_builder(spawned))
        with self.assertRaises(ValueError):
            jm.start("gp-spawn-sequence", "evil-backend:x")
        self.assertEqual(jm.list(), [])
        self.assertEqual(spawned, [])

    def test_validation_order_does_not_leak_partial_job(self):
        # Both bad → still nothing in the table.
        jm = JobManager(self.root, command_builder=_capture_builder([]))
        with self.assertRaises(ValueError):
            jm.start("../escape", "not a slug")
        self.assertEqual(jm.list(), [])


# ---------------------------------------------------------------------------
# Injection safety — argv-only, never a shell
# ---------------------------------------------------------------------------

class TestInjectionSafety(LauncherBase):
    def test_injectiony_task_id_is_rejected_before_build(self):
        # A task_id carrying a shell payload never resolves to a real file →
        # rejected before the builder runs, so it never reaches Popen at all.
        spawned = []
        jm = JobManager(self.root, command_builder=_capture_builder(spawned))
        for evil in ("gp-spawn-sequence; rm -rf /",
                     "$(touch pwned)",
                     "gp-spawn-sequence`id`",
                     "../../etc/passwd"):
            with self.assertRaises(ValueError, msg=evil):
                jm.start(evil, "claude-p:opus")
        self.assertEqual(spawned, [])

    def test_injectiony_model_is_rejected_before_build(self):
        spawned = []
        jm = JobManager(self.root, command_builder=_capture_builder(spawned))
        for evil in ("claude-p:opus; rm -rf /",
                     "claude-p:$(whoami)",
                     "claude-p:opus && curl evil.sh"):
            with self.assertRaises(ValueError, msg=evil):
                jm.start("gp-spawn-sequence", evil)
        self.assertEqual(spawned, [])

    def test_default_builder_returns_argv_list_never_shell_string(self):
        # Even for a *valid* request, the canonical command is a LIST whose model
        # is a single discrete element — there is no shell string to inject into.
        task_path = resolve_task_path("gp-spawn-sequence", self.root)
        argv = default_run_agent_command(
            task_path=task_path, model="aura-mcp:claude-sonnet-4-6",
            repo_root=self.root, ue_root="/Users/Shared/Epic Games/UE_5.7",
            live_project=True,
        )
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(a, str) for a in argv))
        # run.py is the target — NOT the older aura_agent.py. (Normalize the
        # separator so the suffix check holds on Windows too.)
        self.assertTrue(any(
            a.replace("\\", "/").endswith("tools/run-agent/run.py") for a in argv))
        self.assertNotIn("aura_agent.py", " ".join(argv))
        # model is one argv element immediately after --model (not concatenated).
        i = argv.index("--model")
        self.assertEqual(argv[i + 1], "aura-mcp:claude-sonnet-4-6")
        # ue-root with a space stays a single element (would break in a shell str).
        j = argv.index("--ue-root")
        self.assertEqual(argv[j + 1], "/Users/Shared/Epic Games/UE_5.7")
        self.assertIn("--live-project", argv)

    def test_default_builder_omits_optional_flags_when_absent(self):
        task_path = resolve_task_path("gp-spawn-sequence", self.root)
        argv = default_run_agent_command(
            task_path=task_path, model="claude-p:opus", repo_root=self.root)
        self.assertNotIn("--ue-root", argv)
        self.assertNotIn("--live-project", argv)

    def test_builder_must_return_list_of_str(self):
        # A misbehaving custom builder that returns a string is refused — we never
        # hand a bare string to Popen (which with shell=False is harmless anyway,
        # but the guard makes the contract explicit).
        def bad_builder(**kw):
            return "echo hi; rm -rf /"
        jm = JobManager(self.root, command_builder=bad_builder)
        with self.assertRaises(ValueError):
            jm.start("gp-spawn-sequence", "claude-p:opus")

    def test_a_literal_injectiony_argv_element_stays_one_token(self):
        # Defense-in-depth: even if a builder somehow emitted a metacharacter-laden
        # element, shell=False keeps it a single literal arg (no shell parses it).
        # We prove the process sees it verbatim as one argument.
        marker = "weird ; | && $(x) arg"

        def echo_arg_builder(**kw):
            return [sys.executable, "-c",
                    "import sys; print(repr(sys.argv[1]))", marker]
        jm = JobManager(self.root, command_builder=echo_arg_builder)
        job_id = jm.start("gp-spawn-sequence", "claude-p:opus")
        final = jm.wait(job_id, timeout=30)
        self.assertEqual(final["status"], "done")
        self.assertIn(repr(marker), final["log"])


# ---------------------------------------------------------------------------
# Module constants sanity
# ---------------------------------------------------------------------------

class TestSlugRegex(unittest.TestCase):
    def test_regex_matches_brief_spec(self):
        part = r"(?!\.)[A-Za-z0-9._-]+"
        self.assertEqual(
            launcher.MODEL_SLUG_RE.pattern,
            rf"^(bare|claude-p|openrouter|unreal-mcp):{part}(?:/{part})*\Z")

    def test_backend_alternation_is_exactly_the_runnable_adapters(self):
        # The gate's alternation and the advertised backend list must not drift
        # apart: a backend offered in the UI that the regex rejects is a 400 on
        # the user's own dropdown choice, and a backend the regex accepts but
        # the UI hides is a lane with no disclosure.
        alternation = launcher.MODEL_SLUG_RE.pattern.split(":", 1)[0].strip("^()")
        self.assertEqual(set(alternation.split("|")),
                         set(launcher.known_backends()))
        # ...and none of them is a lane this repository cannot drive.
        self.assertFalse(
            set(launcher.known_backends()) & set(launcher._UNLAUNCHABLE_BACKENDS))


# ---------------------------------------------------------------------------
# Routes + per-route model menus + UE-root auto-locate (v1.5.1)
# ---------------------------------------------------------------------------

class TestRoutesAndModels(unittest.TestCase):
    def test_four_user_facing_routes(self):
        routes = launcher.available_routes()
        self.assertEqual([r["id"] for r in routes],
                         ["baseline", "unreal-mcp", "openrouter", "bare"])
        # baseline is the UI name for the claude-p backend.
        baseline = next(r for r in routes if r["id"] == "baseline")
        self.assertEqual(baseline["backend"], "claude-p")
        # Every route maps to a backend the gate actually accepts.
        self.assertEqual({r["backend"] for r in routes},
                         set(launcher.known_backends()))

    def test_only_unreal_mcp_needs_a_live_editor(self):
        # Epic's MCP server runs INSIDE the editor; the other three write files.
        # The client reads this flag instead of keeping its own lane list, so it
        # is the contract that keeps the live-project checkbox honest.
        for r in launcher.available_routes():
            self.assertEqual(r["live_editor"], r["id"] == "unreal-mcp", msg=r["id"])
            self.assertEqual(launcher.route_needs_live_editor(r["id"]),
                             r["id"] == "unreal-mcp", msg=r["id"])
        self.assertFalse(launcher.route_needs_live_editor("no-such-route"))

    def test_models_are_route_dependent(self):
        # claude-p AND unreal-mcp go through `claude -p` -> native Claude ids
        # (no slash); openrouter AND bare address OpenRouter -> provider/model.
        self.assertEqual(launcher.models_for_route("baseline"),
                         launcher.models_for_route("unreal-mcp"))
        self.assertEqual(launcher.models_for_route("openrouter"),
                         launcher.models_for_route("bare"))
        for m in launcher.models_for_route("baseline"):
            self.assertNotIn("/", m)                      # native ids, no slash
        for m in launcher.models_for_route("openrouter"):
            self.assertIn("/", m)                         # OpenRouter provider/model
        # no bare aliases anywhere — only concrete versioned ids
        for route in ("baseline", "unreal-mcp", "openrouter", "bare"):
            for alias in ("opus", "sonnet", "haiku"):
                self.assertNotIn(alias, launcher.models_for_route(route))
        self.assertEqual(set(launcher.models_by_route().keys()),
                         {"baseline", "unreal-mcp", "openrouter", "bare"})

    def test_every_composed_slug_passes_the_gate(self):
        for route, models in launcher.models_by_route().items():
            for m in models:
                slug = launcher.compose_slug(route, m)
                self.assertEqual(launcher.validate_model(slug), slug)

    def test_every_advisory_slug_passes_the_gate(self):
        # available_models() seeds the flat back-compat picker; a seed the gate
        # rejects would 400 on a choice the UI itself offered.
        for slug in launcher.available_models():
            self.assertEqual(launcher.validate_model(slug), slug)

    def test_compose_slug_maps_routes_to_backends(self):
        self.assertEqual(launcher.compose_slug("baseline", "claude-sonnet-5"),
                         "claude-p:claude-sonnet-5")
        self.assertEqual(launcher.compose_slug("bare", "deepseek/deepseek-v4-pro-0813"),
                         "bare:deepseek/deepseek-v4-pro-0813")

    def test_compose_slug_rejects_unknown_route(self):
        with self.assertRaises(ValueError):
            launcher.compose_slug("bogus", "sonnet")

    def test_default_ue_root_is_a_real_dir_or_none(self):
        root = launcher.default_ue_root()
        self.assertTrue(root is None or Path(root).is_dir())


class TestWatchdogTimeout(LauncherBase):
    """The zombie-job guard: a hung child must be killed, not pinned in RUNNING."""

    def test_hung_job_times_out_and_is_killed(self):
        def _hang_builder(**kw):
            # Sleeps far longer than the manager's timeout; must be reaped.
            return [sys.executable, "-c", "import time; time.sleep(60)"]
        jm = JobManager(self.root, command_builder=_hang_builder, timeout_s=0.5)
        job_id = jm.start("gp-spawn-sequence", "claude-p:opus")
        final = jm.wait(job_id, timeout=10)
        self.assertEqual(final["status"], "failed")
        self.assertIn("timed out", (final["error"] or ""))


if __name__ == "__main__":
    unittest.main()
