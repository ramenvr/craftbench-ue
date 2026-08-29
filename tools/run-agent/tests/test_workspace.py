"""workspace.build_workspace round-trips against the real substrate.

No synthetic fixtures — we treat UE-projects/CraftBenchTemplate/ and its
AGENT_WRITABLE.json as committed fixtures, same approach as
test_prompt_extract.py reusing the real tasks.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workspace import build_workspace  # noqa: E402
from snapshot import SubmissionRule  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
SUBSTRATE = REPO_ROOT / "UE-projects/CraftBenchTemplate"
AGENT_WRITABLE = SUBSTRATE / "AGENT_WRITABLE.json"

# The second substrate — the ONLY one with a config lane (`config_writable`),
# and therefore the only one on which the write-scope contract can be wrong in
# the direction that matters. CraftBenchTemplate has no `config_writable` and
# denies Config/ outright, so every assertion below that involves a config file
# is vacuous there; that is precisely how the defect survived this file.
TP_SUBSTRATE = REPO_ROOT / "UE-projects/ThirdPerson"
TP_AGENT_WRITABLE = TP_SUBSTRATE / "AGENT_WRITABLE.json"

# The one task in the tree that declares `config_allow` (census 2026-08-19:
# `grep -rl "^config_allow:" tasks` returns exactly this file), and one that
# does not. bp/gp-heal-over-time-bp is deliberate: its own anti-gaming entry
# says "declares no `config_allow`, so such a submission is sandbox-rejected
# (exit 4)", so naming a config file in ITS prompt would contradict its spec.
TASK_WITH_CONFIG = REPO_ROOT / "tasks/bp/t3-piercing-projectile/task.md"
TASK_WITHOUT_CONFIG = REPO_ROOT / "tasks/bp/gp-heal-over-time-bp/task.md"


class TestBuildWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-agent-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, prompt_text="Do the thing.\n"):
        return build_workspace(
            substrate_root=SUBSTRATE,
            agent_writable_json=AGENT_WRITABLE,
            prompt_text=prompt_text,
            run_id="test-run",
            root_dir=self.tmp,
        )

    def test_project_dir_exists_and_contains_uproject(self):
        ws = self._build()
        self.assertTrue(ws.project_dir.exists())
        self.assertTrue((ws.project_dir / "CraftBenchTemplate.uproject").exists())

    def test_prompt_md_written(self):
        ws = self._build()
        self.assertTrue(ws.prompt_path.exists())
        content = ws.prompt_path.read_text(encoding="utf-8")
        # Bare (preamble-less) body gets the legacy heading; workspace
        # mechanics stay. Behavioral constraints now live in the CENTRAL
        # preamble (tasks/PREAMBLE.md) and must not be duplicated here.
        self.assertIn("# Your task", content)
        self.assertIn("Writable source files", content)
        self.assertNotIn("Do not ask clarifying questions", content)

    def test_prompt_md_preamble_led_body_not_double_wrapped(self):
        # A preamble-led body already opens with its own H1 — the renderer
        # must not stack "# Your task" on top of it.
        ws = self._build(prompt_text="# Benchmark session rules\n\n- rule\n\n"
                                     "# Task\n\nDo the thing.\n")
        content = ws.prompt_path.read_text(encoding="utf-8")
        self.assertNotIn("# Your task", content)
        self.assertTrue(content.startswith("# Benchmark session rules"))
        self.assertIn("# Your workspace", content)

    def test_writable_files_match_agent_writable_json(self):
        # The classification is the VERIFIER's rule, not `manifest["writable"]`
        # alone — pinned against SubmissionRule (which delegates to
        # sandbox._is_writable) rather than a re-spelled prefix match here, so
        # this test cannot become the next stale copy of the rule. On
        # CraftBenchTemplate the two coincide (no config_writable; nothing under
        # an asset_writable-only prefix), which is exactly why this file alone
        # could not catch the ThirdPerson defect — see
        # TestPromptContractMatchesTheSandbox below.
        rule = SubmissionRule.for_substrate(SUBSTRATE)
        ws = self._build()
        self.assertGreater(len(ws.writable_files), 0)
        for p in ws.writable_files:
            rel = p.relative_to(ws.project_dir).as_posix()
            self.assertTrue(rule.accepts(rel),
                            f"{rel} is classified writable but the sandbox rejects it")

    def test_deny_listed_files_not_copied(self):
        ws = self._build()
        denied = ws.project_dir / "Source" / "CraftBenchTests"
        self.assertFalse(denied.exists(), "deny-listed CraftBenchTests was copied")

    def test_generated_subtrees_not_copied(self):
        ws = self._build()
        for skip in ("Binaries", "Intermediate", "DerivedDataCache", "Saved"):
            self.assertFalse(
                (ws.project_dir / skip).exists(),
                f"transient subtree {skip!r} was copied",
            )

    def test_uproject_is_present_but_marked_readonly(self):
        ws = self._build()
        uproject = ws.project_dir / "CraftBenchTemplate.uproject"
        self.assertIn(uproject, ws.readonly_files)


class TestBuildWorkspacePerTaskIsolation(unittest.TestCase):
    """active_task_id opts the workspace into the graded-scratch staging:
    only the active task's content reaches the agent copy."""

    TASK_ID = "gp-spawner-population"
    SPEC = REPO_ROOT / "tasks/cpp/gp-spawner-population/task.md"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-agent-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, **kw):
        return build_workspace(
            substrate_root=SUBSTRATE,
            agent_writable_json=AGENT_WRITABLE,
            prompt_text="Do the thing.\n",
            run_id="test-run",
            root_dir=self.tmp,
            extra_skip_subtrees=("Plugins",),
            **kw,
        )

    def _build_isolated(self):
        return self._build(
            active_task_id=self.TASK_ID,
            task_spec_text=self.SPEC.read_text(encoding="utf-8"),
        )

    def test_active_task_content_kept(self):
        ws = self._build_isolated()
        p = ws.project_dir
        self.assertTrue((p / "Content/Maps/L_SpawnerPopulation.umap").exists())
        self.assertTrue((p / "Source/CraftBenchTemplate/SpawnerActor.h").exists())
        # Untagged shared infra stays (fail-safe KEEP).
        self.assertTrue((p / "Source/CraftBenchTemplate/CraftBenchCharacter.h").exists())
        # Shared render probe stays on every surface.
        self.assertTrue((p / "Content/Maps/L_RenderProbe.umap").exists())

    def test_foreign_task_content_pruned(self):
        ws = self._build_isolated()
        p = ws.project_dir
        # Foreign flat map + foreign per-task map folder.
        self.assertFalse((p / "Content/Maps/L_PoisonStack.umap").exists())
        self.assertFalse((p / "Content/Maps/t0-sanity-log-on-beginplay").exists())
        # Foreign per-task source tree + foreign marker-tagged flat scaffold.
        self.assertFalse(
            (p / "Source/CraftBenchTemplate/Tasks/t0-sanity-log-on-beginplay").exists())
        self.assertFalse((p / "Source/CraftBenchTemplate/CraftQueueActor.h").exists())
        # Verifier-side scaffolder recipes never reach the agent.
        self.assertFalse((p / "Tools").exists())

    def test_file_lists_hold_no_pruned_paths(self):
        ws = self._build_isolated()
        for lst in (ws.writable_files, ws.readonly_files):
            for f in lst:
                self.assertTrue(f.exists(), f"pruned path left in list: {f}")

    def test_default_build_stays_unpruned(self):
        # Opt-in only: without active_task_id the historical shape is kept
        # (--workspace reuse and ad-hoc builds rely on it). NB: no Tools/
        # assertion — the substrate's Tools/ dir emptied out (and thus
        # vanished from git) when the map scaffolders were retired 2026-07.
        ws = self._build()
        p = ws.project_dir
        self.assertTrue((p / "Content/Maps/L_PoisonStack.umap").exists())
        self.assertTrue((p / "Content/Maps/L_SpawnerPopulation.umap").exists())


def _prompt_listing(prompt_text: str) -> set:
    """The rel-paths PROMPT.md enumerates as writable, as a set.

    Parsed out of the rendered text rather than read off the Workspace object,
    because the thing under test is what the AGENT reads."""
    head, _, rest = prompt_text.partition(
        "Writable source files (your edits to these are the submission):")
    assert rest, "PROMPT.md has no writable listing"
    body = rest.split("Other files in this directory")[0]
    return {ln.strip()[2:] for ln in body.splitlines() if ln.strip().startswith("- ")}


class TestPromptContractMatchesTheSandbox(unittest.TestCase):
    """The workspace lanes (claude-p / openrouter / bare) hand the agent a
    write-scope contract in PROMPT.md. It must name what the sandbox will accept
    FROM THIS TASK — no broader, no narrower.

    MEASURED 2026-08-19, pre-fix, on bp/t3-piercing-projectile (ThirdPerson):
    build_workspace classified Config/DefaultEngine.ini as READ-ONLY (`writable
    =False readonly=True`) and PROMPT.md never named it, so the trailing "Other
    files in this directory are read-only context; do not edit them" covered a
    file that (a) sandbox.py path-accepts, (b) the task's `config_allow` rules
    license verbatim, (c) ships as one of the four committed reference files,
    and (d) the PREAMBLE — prepended into the very same PROMPT.md, ~60 lines
    above — explicitly licenses. Nothing prevented the write; the cell measured
    whether the model would disobey a written instruction.

    The naive fix is UNSAFE and these tests pin against it too: appending
    `config_writable` wholesale would promise BOTH ThirdPerson config files on
    every task, and on the 63 that declare no `config_allow` a config edit is a
    sandbox-class reject (exit 4) — a non-graded, unrecoverable cell."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="run-agent-test-"))
        cls.rule = SubmissionRule.for_substrate(TP_SUBSTRATE)
        cls.licensed = cls._build(TASK_WITH_CONFIG, "licensed")
        cls.unlicensed = cls._build(TASK_WITHOUT_CONFIG, "unlicensed")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def _build(cls, spec: Path, run_id: str):
        """One real ThirdPerson workspace per scenario, built once for the whole
        class — the copy is ~1.3k files and nothing here mutates it."""
        return build_workspace(
            substrate_root=TP_SUBSTRATE,
            agent_writable_json=TP_AGENT_WRITABLE,
            prompt_text="Do the thing.\n",
            run_id=run_id,
            root_dir=cls.tmp,
            extra_skip_subtrees=("Plugins",),
            active_task_id=spec.parent.name,
            task_spec_text=spec.read_text(encoding="utf-8", errors="replace"),
        )

    @staticmethod
    def _rels(ws, attr):
        return {p.relative_to(ws.project_dir).as_posix() for p in getattr(ws, attr)}

    # -- the fix ------------------------------------------------------------
    def test_licensed_config_file_is_writable_and_listed(self):
        ws = self.licensed
        self.assertIn("Config/DefaultEngine.ini", self._rels(ws, "writable_files"))
        self.assertNotIn("Config/DefaultEngine.ini", self._rels(ws, "readonly_files"))
        self.assertIn("Config/DefaultEngine.ini",
                      _prompt_listing(ws.prompt_path.read_text(encoding="utf-8")))

    def test_unlicensed_config_file_of_the_same_task_stays_readonly(self):
        # The manifest lists two config files; t3-piercing-projectile licenses
        # ONE. Naming DefaultInput.ini would advertise a path whose every diff
        # is uncovered by config_allow → exit 4 for the whole submission.
        ws = self.licensed
        self.assertIn("Config/DefaultInput.ini", self._rels(ws, "readonly_files"))
        self.assertNotIn("Config/DefaultInput.ini", self._rels(ws, "writable_files"))
        self.assertNotIn("Config/DefaultInput.ini",
                         _prompt_listing(ws.prompt_path.read_text(encoding="utf-8")))

    def test_task_without_config_allow_gets_no_config_file_at_all(self):
        ws = self.unlicensed
        writable = self._rels(ws, "writable_files")
        self.assertFalse([p for p in writable if p.startswith("Config/")],
                         "a task with no config_allow was promised a config file")
        section = ws.prompt_path.read_text(encoding="utf-8").split("# Your workspace")[1]
        self.assertNotIn("Config/", section)

    # -- no broader, no narrower -------------------------------------------
    def test_classification_is_the_verifier_rule_narrowed_by_config_allow(self):
        """Every writable file is sandbox-accepted, and the ONLY sandbox-accepted
        file classified read-only is a config file this task does not license.

        Asserted against SubmissionRule (which delegates to sandbox._is_writable)
        instead of a prefix match spelled out here — a test that re-spells the
        rule is the seventh copy, not a check on the sixth."""
        for ws, allowed_gap in ((self.licensed, {"Config/DefaultInput.ini"}),
                                (self.unlicensed, {"Config/DefaultEngine.ini",
                                                   "Config/DefaultInput.ini"})):
            writable = self._rels(ws, "writable_files")
            readonly = self._rels(ws, "readonly_files")
            self.assertEqual(
                sorted(p for p in writable if not self.rule.accepts(p)), [],
                "classified writable but the sandbox would REJECT it")
            self.assertEqual(
                {p for p in readonly if self.rule.accepts(p)}, allowed_gap,
                "read-only set differs from the sandbox by something other than "
                "the config files this task does not license")

    def test_asset_lane_files_are_writable_but_deliberately_not_enumerated(self):
        """The asset lane (.uasset/.umap under an `asset_writable` prefix) is part
        of the CLASSIFICATION but not of the LISTING.

        Why the listing stops there, measured 2026-08-19: `git ls-files` returns
        0 tracked files under every asset-lane-only prefix of either substrate,
        and the frozen bench tree C:/cb/bench-tree has none on disk — so on a clean
        checkout this omission covers exactly zero files. In THIS dev tree the
        two OFPA mirror roots hold 144 gitignored leftovers, and enumerating them
        would take the same task's PROMPT.md from 120 lines to 264 on this box
        and 120 on a fresh clone. Prompt length is a fairness lever; a listing
        whose length depends on gitignored residue is worse than a documented
        subset. Creation under those roots is already licensed upstream in the
        same PROMPT.md by tasks/PREAMBLE.md's {asset_roots}."""
        ws = self.licensed
        writable = self._rels(ws, "writable_files")
        listed = _prompt_listing(ws.prompt_path.read_text(encoding="utf-8"))
        self.assertTrue(listed <= writable,
                        "PROMPT.md lists a file the sandbox would not accept")
        manifest = json.loads(TP_AGENT_WRITABLE.read_text(encoding="utf-8"))
        source_prefixes = tuple(manifest["writable"])
        asset_only = {p for p in writable
                      if not p.startswith(source_prefixes)
                      and p not in ("Config/DefaultEngine.ini",)}
        # Guard the guard: with nothing in this set the assertion below tests
        # nothing, so it must not read as a pass. SKIP, not fail: the docstring
        # above MEASURED that a clean checkout has zero tracked files under
        # every asset-lane-only prefix, so an empty set is the NORMAL state of
        # CI and of the frozen bench tree -- asserting non-empty made this test
        # fail everywhere except a dev box carrying gitignored residue, which is
        # what it did on the bench host and in CI (masked until 2026-08-24 by
        # an earlier red gate). Where residue exists the assertion still runs.
        if not asset_only:
            self.skipTest(
                "no asset-lane-only file on disk -- the measured state of a "
                "clean checkout, so there is nothing here to leak into the "
                "listing. Re-point this test if the substrate ever tracks one.")
        self.assertFalse(asset_only & listed,
                         "asset-lane files leaked into the PROMPT.md listing")


class TestTemplateSubstrateRendersUnchanged(unittest.TestCase):
    """CraftBenchTemplate has no `config_writable` and denies Config/ outright.
    Its contract must render exactly as before: no config file named, no empty
    heading, no "(nothing)"."""

    TASK_ID = "gp-spawner-population"
    SPEC = REPO_ROOT / "tasks/cpp/gp-spawner-population/task.md"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-agent-test-"))
        self.ws = build_workspace(
            substrate_root=SUBSTRATE,
            agent_writable_json=AGENT_WRITABLE,
            prompt_text="Do the thing.\n",
            run_id="template",
            root_dir=self.tmp,
            extra_skip_subtrees=("Plugins",),
            active_task_id=self.TASK_ID,
            task_spec_text=self.SPEC.read_text(encoding="utf-8"),
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_config_file_is_named(self):
        section = self.ws.prompt_path.read_text(
            encoding="utf-8").split("# Your workspace")[1]
        self.assertNotIn("Config/", section)

    def test_listing_is_non_empty_and_has_no_placeholder(self):
        text = self.ws.prompt_path.read_text(encoding="utf-8")
        listed = _prompt_listing(text)
        self.assertTrue(listed)
        section = text.split("# Your workspace")[1]
        for placeholder in ("(none)", "(nothing)", "You may also"):
            self.assertNotIn(placeholder, section)

    def test_listing_equals_the_writable_classification(self):
        # Nothing on this substrate is writable through the asset or config
        # lanes alone, so listing and classification coincide here — the
        # pre-fix behaviour, pinned so the ThirdPerson fix cannot change it.
        rels = {p.relative_to(self.ws.project_dir).as_posix()
                for p in self.ws.writable_files}
        self.assertEqual(
            _prompt_listing(self.ws.prompt_path.read_text(encoding="utf-8")), rels)


if __name__ == "__main__":
    unittest.main()
