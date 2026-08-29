"""Unit tests for preamble.py — the central benchmark-preamble renderer.

Fully offline: builds a throwaway repo tree (template + substrate manifest +
scaffold files) and asserts the rendered contract: placeholder filling, the
maintainer-comment strip, foldered/flat/asset-only scaffold enumeration
(including the wrapped-marker fixture form), the excerpt appendix + cap, and
loud failure when the template or manifest is missing.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preamble  # noqa: E402

_TEMPLATE = """<!--
maintainer notes — must never reach the agent
-->

# Benchmark session rules

- Unattended run for {task_id}.

# Task workspace ({task_id})

- Scaffold: {scaffold_files}
- Writable: {writable_roots}
- Assets: {asset_roots}
{scaffold_excerpt_section}
"""


class _Repo:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-preamble-"))
        (self.root / "tasks").mkdir(parents=True)
        (self.root / "tasks" / "PREAMBLE.md").write_text(_TEMPLATE, encoding="utf-8")
        self.substrate = self.root / "UE-projects" / "CraftBenchTemplate"
        self.module = self.substrate / "Source" / "CraftBenchTemplate"
        self.module.mkdir(parents=True)
        (self.substrate / "AGENT_WRITABLE.json").write_text(
            '{"writable": ["Source/CraftBenchTemplate/", "Content/Tasks/"],'
            ' "asset_writable": ["Content/Tasks/", "Content/Blueprints/"],'
            ' "deny": ["Source/CraftBenchTests/"]}',
            encoding="utf-8")

    def foldered(self, task_id: str, *names: str):
        d = self.module / "Tasks" / task_id
        d.mkdir(parents=True)
        for n in names:
            (d / n).write_text(f"// scaffold {n} for task {task_id}.\n",
                               encoding="utf-8")

    def flat(self, cls: str, task_id: str, *, marker_in=("h", "cpp"),
             wrapped: bool = False):
        tag = (f"for task\n// {task_id}." if wrapped else f"for task {task_id}.")
        for ext in ("h", "cpp"):
            body = (f"// A{cls} — pre-existing actor pair {tag}\n"
                    if ext in marker_in else f"// A{cls} implementation.\n")
            (self.module / f"{cls}.{ext}").write_text(body, encoding="utf-8")


class TestScaffoldEnumeration(unittest.TestCase):
    def test_foldered_task_lists_folder_files(self):
        r = _Repo()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h", "SanityActor.cpp")
        files = preamble.scaffold_files_for_task(
            "t0-sanity-log-on-beginplay", r.substrate)
        self.assertEqual(files, [
            "Source/CraftBenchTemplate/Tasks/t0-sanity-log-on-beginplay/SanityActor.cpp",
            "Source/CraftBenchTemplate/Tasks/t0-sanity-log-on-beginplay/SanityActor.h",
        ])

    def test_flat_task_marker_scan_with_pair_completion(self):
        r = _Repo()
        r.flat("SpawnerActor", "gp-spawner-population", marker_in=("h",))
        r.flat("CraftQueueActor", "gp-crafting-queue")  # foreign — excluded
        files = preamble.scaffold_files_for_task(
            "gp-spawner-population", r.substrate)
        # .cpp has no marker but is the .h's pair — both included.
        self.assertEqual(files, [
            "Source/CraftBenchTemplate/SpawnerActor.cpp",
            "Source/CraftBenchTemplate/SpawnerActor.h",
        ])

    def test_wrapped_marker_is_recognized(self):
        # Three real fixtures wrap the id onto the next comment line; the
        # widened _FOR_TASK_RE must see them (preamble + staging parity).
        r = _Repo()
        r.flat("HarvestableActor", "gp-harvestable-regrow", wrapped=True)
        files = preamble.scaffold_files_for_task(
            "gp-harvestable-regrow", r.substrate)
        self.assertEqual(len(files), 2)

    def test_asset_only_task_lists_content_baseline(self):
        r = _Repo()
        d = r.substrate / "Content" / "Tasks" / "umg-image-brush-bound"
        d.mkdir(parents=True)
        (d / "WBP_CardSlot.uasset").write_bytes(b"\x00\x01")
        files = preamble.scaffold_files_for_task(
            "umg-image-brush-bound", r.substrate)
        self.assertEqual(
            files, ["Content/Tasks/umg-image-brush-bound/WBP_CardSlot.uasset"])

    def test_set_qualified_id_normalized(self):
        r = _Repo()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h")
        files = preamble.scaffold_files_for_task(
            "cpp/t0-sanity-log-on-beginplay", r.substrate)
        self.assertEqual(len(files), 1)


class TestRender(unittest.TestCase):
    def test_placeholders_filled_and_comment_stripped(self):
        r = _Repo()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h")
        p = preamble.render_preamble("t0-sanity-log-on-beginplay", r.root)
        self.assertNotIn("maintainer notes", p.text)
        self.assertNotIn("{", p.text.replace("{}", ""))  # no unfilled tokens
        self.assertIn("Task workspace (t0-sanity-log-on-beginplay)", p.text)
        self.assertIn("SanityActor.h", p.text)
        self.assertIn("Source/CraftBenchTemplate/, Content/Tasks/", p.text)
        self.assertIn("Content/Blueprints/", p.text)
        self.assertEqual(len(p.sha), 64)

    def test_excerpt_included_only_on_request_and_capped(self):
        r = _Repo()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h", "SanityActor.cpp")
        big = r.module / "Tasks" / "t0-sanity-log-on-beginplay" / "SanityActor.cpp"
        big.write_text("// for task t0-sanity-log-on-beginplay\n" + "x" * 20000,
                       encoding="utf-8")
        off = preamble.render_preamble("t0-sanity-log-on-beginplay", r.root)
        self.assertNotIn("Current scaffold contents", off.text)
        on = preamble.render_preamble("t0-sanity-log-on-beginplay", r.root,
                                      include_excerpt=True)
        self.assertIn("Current scaffold contents", on.text)
        self.assertIn("(truncated)", on.text)
        # cap: template + excerpt stays well under 2x the excerpt budget
        self.assertLess(len(on.text), preamble._EXCERPT_CAP_BYTES * 2)

    def test_binary_assets_named_but_not_inlined(self):
        r = _Repo()
        d = r.substrate / "Content" / "Tasks" / "umg-image-brush-bound"
        d.mkdir(parents=True)
        (d / "WBP_CardSlot.uasset").write_bytes(b"\x00" * 64)
        p = preamble.render_preamble("umg-image-brush-bound", r.root,
                                     include_excerpt=True)
        self.assertIn("WBP_CardSlot.uasset", p.text)          # named
        self.assertNotIn("Current scaffold contents", p.text)  # nothing to inline

    def test_empty_scaffold_gets_explicit_note(self):
        r = _Repo()
        p = preamble.render_preamble("gp-glide-stamina-cpp", r.root)
        self.assertIn("starts from an empty workspace", p.text)

    def test_scratch_without_manifest_falls_back_to_repo_copy(self):
        # The C1 graded scratch deliberately omits AGENT_WRITABLE.json — the
        # renderer must fall back to the REPO substrate's manifest while still
        # reading scaffold files from the scratch (the agent-visible tree).
        r = _Repo()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h")
        import shutil as _sh
        scratch = r.root / "scratch"
        _sh.copytree(r.substrate, scratch)
        (scratch / "AGENT_WRITABLE.json").unlink()
        p = preamble.render_preamble("t0-sanity-log-on-beginplay", r.root,
                                     substrate_root=scratch)
        self.assertIn("Source/CraftBenchTemplate/, Content/Tasks/", p.text)
        self.assertIn("SanityActor.h", p.text)

    def test_missing_template_or_manifest_raises(self):
        r = _Repo()
        (r.root / "tasks" / "PREAMBLE.md").unlink()
        with self.assertRaises(FileNotFoundError):
            preamble.render_preamble("t0-sanity-log-on-beginplay", r.root)
        r2 = _Repo()
        (r2.substrate / "AGENT_WRITABLE.json").unlink()
        with self.assertRaises(FileNotFoundError):
            preamble.render_preamble("t0-sanity-log-on-beginplay", r2.root)


class TestRenderOrdering(unittest.TestCase):
    """The preamble renderer reads AGENT_WRITABLE.json, which
    stage_fairness_hide MOVES ASIDE — so the render must happen BEFORE the
    hide on every graded path (rendering after silently drove without the
    contract; 2026-07-11 FAILURE-LOG entry)."""

    def _src(self, rel: str) -> str:
        return (Path(__file__).resolve().parents[1] / rel).read_text(
            encoding="utf-8")

    def test_render_precedes_hide_in_the_graded_spine(self):
        """Until the 2026-08-28 public release this looped over the two
        aura-product graded modules, each of which rendered inline just above
        its own hide. Those went out with that lane. run.py -- the one spine
        all three shipped arms (claude-p / aura-mcp / unreal-mcp) run through
        -- gets the SAME property from a different shape: main() renders once
        and hands the finished prompt down, and only the callee hides. So the
        two things worth pinning are the order and the hand-off, not a
        per-site adjacency that no longer exists."""
        src = self._src("run.py")
        i_render = src.index("_pre = render_preamble(")
        i_hide = src.index("stage_fairness_hide(project_dir, run_dir)")
        self.assertLess(i_render, i_hide)

        # The render lives in main(); the hide lives in the callee main()
        # dispatches to. That is what makes the source order a RUNTIME order.
        i_main = src.index("def main() -> int:")
        i_live = src.index("def _run_live_project(")
        self.assertLess(i_main, i_render)
        self.assertLess(i_render, i_live, "the render must be main's, not the "
                        "live-project callee's")
        self.assertLess(i_live, i_hide)

        # And the prompt assembly consumes the STASHED text, not a fresh
        # (post-hide) render: the callee never renders at all.
        self.assertNotIn("render_preamble(", src[i_live:],
                         "a second render inside _run_live_project would run "
                         "AFTER the hide moved AGENT_WRITABLE.json aside")
        self.assertIn("preamble=preamble_text", src)


class TestSubstrateAwareWritableRoots(unittest.TestCase):
    """The contract must come from THE TASK'S substrate, not the default one.

    Measured 2026-08-08: the manifest fallback was substrate-blind, so a
    ThirdPerson task's prompt said "create new files only under
    Source/CraftBenchTemplate/". On -bp tasks that was harmless BY LUCK (the
    deliverable is a .uasset under Content/Tasks/, shared by both manifests);
    on -cpp it made the family unwinnable — the agent wrote C++ into a
    directory the ThirdPerson module does not compile, so the submission
    vanished and graded as a model FAIL. A harness fault must never reach a
    graded verdict, so this is locked by test rather than left to a probe.
    """

    def _repo_with_second_substrate(self):
        r = _Repo()
        # A ThirdPerson substrate whose writable module is NOT the default.
        tp = r.root / "UE-projects" / "ThirdPerson"
        (tp / "Source" / "ThirdPerson").mkdir(parents=True)
        (tp / "AGENT_WRITABLE.json").write_text(
            '{"game_module": "ThirdPerson",'
            ' "writable": ["Source/ThirdPerson/", "Content/Tasks/"],'
            ' "asset_writable": ["Content/Tasks/"],'
            ' "deny": ["Source/CraftBenchTests/"]}', encoding="utf-8")
        d = r.root / "tasks" / "cpp" / "gp-glide-stamina-cpp"
        d.mkdir(parents=True)
        (d / "task.md").write_text(
            "---\nid: gp-glide-stamina-cpp\nsubstrate: ThirdPerson\nset: bp-g2\n"
            "tier: T2\ncapability_bucket: Gameplay Programming\n"
            "layers: [L1, L2]\nfixtures: [\"L_GlideStamina :: AGlideStaminaFunctionalTest\"]\n"
            "---\n\n# gp-glide-stamina-cpp\n\nBody.\n", encoding="utf-8")
        return r, tp

    def test_task_substrate_is_resolved_from_the_spec(self):
        r, tp = self._repo_with_second_substrate()
        self.assertEqual(
            preamble.task_substrate_root("cpp/gp-glide-stamina-cpp", r.root), tp)

    def test_scratch_without_a_manifest_still_gets_ITS_OWN_roots(self):
        # The live graded scratch ships no AGENT_WRITABLE.json, so this is the
        # ACTIVE path on every aura run — the exact shape that broke.
        r, _ = self._repo_with_second_substrate()
        scratch = r.root / "scratch-no-manifest"
        scratch.mkdir()
        text = preamble.render_preamble(
            "cpp/gp-glide-stamina-cpp", r.root, substrate_root=scratch).text
        self.assertIn("Writable: Source/ThirdPerson/, Content/Tasks/", text)
        self.assertNotIn("Source/CraftBenchTemplate/", text)

    def test_default_substrate_task_is_unchanged(self):
        r, _ = self._repo_with_second_substrate()
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h")
        scratch = r.root / "scratch2"
        scratch.mkdir()
        text = preamble.render_preamble(
            "t0-sanity-log-on-beginplay", r.root, substrate_root=scratch).text
        self.assertIn("Writable: Source/CraftBenchTemplate/, Content/Tasks/", text)

    def test_a_manifest_in_the_given_root_still_wins(self):
        # Precedence is unchanged where a manifest actually exists.
        r, tp = self._repo_with_second_substrate()
        text = preamble.render_preamble(
            "cpp/gp-glide-stamina-cpp", r.root, substrate_root=tp).text
        self.assertIn("Writable: Source/ThirdPerson/, Content/Tasks/", text)

    def test_unresolvable_task_falls_back_without_raising(self):
        r, _ = self._repo_with_second_substrate()
        self.assertIsNone(preamble.task_substrate_root("no-such-task", r.root))
        scratch = r.root / "scratch3"
        scratch.mkdir()
        text = preamble.render_preamble(
            "no-such-task", r.root, substrate_root=scratch).text
        self.assertIn("Writable: Source/CraftBenchTemplate/, Content/Tasks/", text)



# ---------------------------------------------------------------------------
# The write-scope contract: every ALLOW-side manifest key must reach the agent.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERIFY_SINGLE = _REPO_ROOT / "tools" / "verify-single"
_REAL_TEMPLATE = _REPO_ROOT / "tasks" / "PREAMBLE.md"
if _VERIFY_SINGLE.is_dir() and str(_VERIFY_SINGLE) not in sys.path:
    sys.path.insert(0, str(_VERIFY_SINGLE))

# Every backend slug adapters/registry.py can dispatch. The write-scope
# contract must not mention any of them: the preamble is ONE prompt for every
# arm, and a per-arm write scope would break the "only the tool layer varies"
# comparison the benchmark is built on.
_ARM_SLUGS = ("aura-product", "aura-mcp", "aura-agent", "aura-baseline",
              "aura-mcp-bridge", "unreal-mcp", "claude-p", "openrouter")


class _ContractRepo:
    """A two-substrate repo shaped like the real one: a default substrate with
    NO config lane and a blanket ``Config/`` deny, and a ThirdPerson-shaped one
    that carries ``config_writable`` plus the two OFPA mirror roots."""

    def __init__(self, *, config_writable=("Config/DefaultEngine.ini",
                                           "Config/DefaultInput.ini"),
                 asset_writable=("Content/Tasks/",
                                 "Content/__ExternalActors__/Tasks/",
                                 "Content/__ExternalObjects__/Tasks/"),
                 extra_manifest_keys=""):
        self.root = Path(tempfile.mkdtemp(prefix="cb-contract-"))
        (self.root / "tasks").mkdir(parents=True)
        # The REAL template, not the toy one above: these tests pin the
        # sentence an agent actually reads, so a template edit that drops a
        # placeholder has to fail here rather than in the epoch.
        (self.root / "tasks" / "PREAMBLE.md").write_text(
            _REAL_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        # Default substrate: no config lane at all, Config/ denied outright.
        self.template = self.root / "UE-projects" / "CraftBenchTemplate"
        (self.template / "Source" / "CraftBenchTemplate").mkdir(parents=True)
        (self.template / "AGENT_WRITABLE.json").write_text(
            '{"substrate": "CraftBenchTemplate",'
            ' "game_module": "CraftBenchTemplate",'
            ' "writable": ["Source/CraftBenchTemplate/", "Content/Tasks/"],'
            ' "asset_writable": ["Content/Tasks/", "Content/Blueprints/"],'
            ' "deny": ["Source/CraftBenchTests/", "Config/", "Content/Maps/"]}',
            encoding="utf-8")
        # ThirdPerson-shaped substrate: config lane + OFPA mirrors.
        self.tp = self.root / "UE-projects" / "ThirdPerson"
        (self.tp / "Source" / "ThirdPerson").mkdir(parents=True)
        cw = ", ".join(f'"{f}"' for f in config_writable)
        aw = ", ".join(f'"{f}"' for f in asset_writable)
        (self.tp / "AGENT_WRITABLE.json").write_text(
            '{"substrate": "ThirdPerson", "game_module": "ThirdPerson",'
            ' "writable": ["Source/ThirdPerson/", "Content/Tasks/"],'
            f' "asset_writable": [{aw}],'
            f' "config_writable": [{cw}],'
            f'{extra_manifest_keys}'
            ' "deny": ["Source/CraftBenchTests/", "Content/Maps/"]}',
            encoding="utf-8")
        # The live graded scratch ships NO manifest — the ACTIVE render path.
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()

    def task(self, task_id: str, *, substrate: str = "ThirdPerson",
             config_allow=()):
        d = self.root / "tasks" / "bp" / task_id
        d.mkdir(parents=True)
        ca = ""
        if config_allow:
            ca = "config_allow: [" + ", ".join(
                f'"{e}"' for e in config_allow) + "]\n"
        (d / "task.md").write_text(
            f"---\nid: {task_id}\nsubstrate: {substrate}\nset: bp\n"
            "tier: T2\ncapability_bucket: Gameplay Programming\n"
            "layers: [L1, L2]\n"
            'fixtures: ["L_Probe :: AProbeFunctionalTest"]\n'
            + ca + f"---\n\n# {task_id}\n\nBody.\n",
            encoding="utf-8")
        # SELF-CHECK, not decoration. These tests only mean anything if
        # the renderer actually reaches THIS substrate's manifest. Under
        # an earlier draft of this fixture the spec failed to parse,
        # task_substrate_root fell back to the DEFAULT substrate, and
        # every config assertion was being made against a manifest with
        # no config lane at all — the tests failed loudly here, but a
        # differently-shaped drift could just as easily have passed
        # them. A fixture that cannot tell the substrate it built from
        # the fallback is not a fixture.
        resolved = preamble.task_substrate_root(task_id, self.root)
        assert resolved is not None and resolved.name == substrate, (
            f"fixture built a spec the renderer cannot resolve to "
            f"{substrate}: got {resolved}")

    def render(self, task_id: str) -> str:
        return preamble.render_preamble(
            task_id, self.root, substrate_root=self.scratch).text

    @staticmethod
    def contract_line(text: str) -> str:
        """The rendered write-scope sentence, unwrapped to one line — the only
        part of the preamble this suite governs."""
        body = " ".join(text.split())
        start = body.index("Create new files only under:")
        return body[start:body.index("Trust the filesystem", start)]


class TestConfigWritableReachesTheAgent(unittest.TestCase):
    """FAILS against the pre-fix renderer, which filled {writable_roots} from
    `writable` and {asset_roots} from `asset_writable` and never mentioned
    `config_writable`.

    bp/t3-piercing-projectile REQUIRES a Config/DefaultEngine.ini edit, the
    sandbox accepts it, and the prompt said Config/ was read-only — all three
    re-measured 2026-08-19. The 2026-08-18 review additionally reports that both
    of that task's graded passes came from the model inferring the undeclared
    lane, i.e. the cell scored guesswork rather than capability; that run
    evidence is cited here, not re-derived."""

    def test_licensed_config_file_is_named_in_the_contract(self):
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        line = r.contract_line(r.render("t3-piercing-projectile"))
        self.assertIn("Config/DefaultEngine.ini", line)

    def test_only_the_files_this_task_licenses_are_named(self):
        # The manifest lists two config files; this task licenses one. Naming
        # the other would advertise a path whose EVERY diff is uncovered.
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        line = r.contract_line(r.render("t3-piercing-projectile"))
        self.assertIn("Config/DefaultEngine.ini", line)
        self.assertNotIn("Config/DefaultInput.ini", line)

    def test_the_clause_says_exact_files_not_an_open_directory(self):
        """config_writable entries are EXACT rel-paths (sandbox matches them
        with `rel_path in manifest.config_writable`), unlike the prefix-matched
        writable/asset roots. The manifest's own warning is that a broad
        Config/ prefix would path-accept arbitrary engine-config edits with no
        semantic gate — so the agent must not read this as "Config/ is open"."""
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        line = r.contract_line(r.render("t3-piercing-projectile"))
        self.assertIn("nothing else under Config/ is writable", line)
        self.assertIn("EDIT (never create, never delete)", line)
        # …and no bare `Config/` root is ever offered as a create-here prefix.
        roots = line.split("You may also EDIT")[0]
        self.assertNotIn("Config/", roots)

    def test_task_without_a_config_lane_gets_no_config_clause(self):
        """Measured 2026-08-19 via config_lane.validate_config_submission: with
        `config_allow=()`, a single added `+ActionMappings` line in a
        config_writable file returns "config change not allowed", which
        run_task.py folds into sandbox_result.violations → exit 4
        SANDBOX-REJECT for the WHOLE submission. Census the same day: 64
        ThirdPerson tasks, exactly ONE declares config_allow. Naming the files
        unconditionally would hand the other 63 a trapdoor, and several of
        their anti-gaming entries depend on the opposite."""
        r = _ContractRepo()
        r.task("kp-fog-and-postprocess-rig")           # no config_allow
        line = r.contract_line(r.render("kp-fog-and-postprocess-rig"))
        self.assertNotIn("Config/", line)
        self.assertNotIn("EDIT", line)


class TestContractDegradesCleanly(unittest.TestCase):
    """CraftBenchTemplate has no `config_writable` and denies Config/ outright,
    so its contract must render exactly as it did before this change."""

    def test_template_substrate_names_no_config_file(self):
        r = _ContractRepo()
        r.task("t0-sanity-log-on-beginplay", substrate="CraftBenchTemplate")
        line = r.contract_line(r.render("t0-sanity-log-on-beginplay"))
        self.assertIn("Source/CraftBenchTemplate/, Content/Tasks/", line)
        self.assertNotIn("Config/", line)
        # No empty heading, no "(nothing)", no dangling connective.
        self.assertNotIn("(none)", line)
        self.assertNotIn("(nothing)", line)
        self.assertNotIn("You may also", line)
        self.assertNotIn("::", line)

    def test_asset_roots_fallback_is_not_polluted_by_the_config_clause(self):
        """{asset_roots} falls back to the writable roots when a manifest
        declares no asset_writable. That fallback must be the PLAIN root list:
        folding the config sentence into it would file "you may EDIT
        Config/DefaultEngine.ini" under "New assets … belong under:"."""
        r = _ContractRepo(asset_writable=())
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        line = r.contract_line(r.render("t3-piercing-projectile"))
        assets = line.split("belong under:")[1]
        self.assertNotIn("Config/", assets)
        self.assertIn("Source/ThirdPerson/, Content/Tasks/", assets)


class TestOfpaMirrorRootsReachTheAgent(unittest.TestCase):
    """REGRESSION PIN, not a fix: measured 2026-08-19, the pre-fix renderer
    ALREADY named both OFPA roots wherever the ThirdPerson manifest was the one
    in play, because they are plain `asset_writable` entries. Four epoch task
    specs promise them in agent-visible prose (bp/t1-playable-level-bootstrap,
    python/kp-blueprint-actor-audit-report, python/kp-fog-and-postprocess-rig,
    python/kp-spawn-level-actors), so this pins the agreement rather than
    creating it — dropping either root would silently contradict four specs."""

    def test_both_ofpa_roots_are_named(self):
        r = _ContractRepo()
        r.task("t1-playable-level-bootstrap")
        line = r.contract_line(r.render("t1-playable-level-bootstrap"))
        self.assertIn("Content/__ExternalActors__/Tasks/", line)
        self.assertIn("Content/__ExternalObjects__/Tasks/", line)


class TestAllowKeyCoverage(unittest.TestCase):
    """The anti-drift seam. The original defect was a human transcribing a
    SUBSET of the manifest once, so a new allowlist key must be impossible to
    add without either reaching the agent or stopping the run."""

    def test_an_unrendered_allow_key_fails_closed(self):
        r = _ContractRepo(extra_manifest_keys=' "plugin_writable": ["Plugins/X/"],')
        r.task("t3-piercing-projectile")
        with self.assertRaises(ValueError) as cm:
            r.render("t3-piercing-projectile")
        self.assertIn("plugin_writable", str(cm.exception))

    def test_manifest_prose_keys_are_not_mistaken_for_policy(self):
        # `_comment` / `_asset_writable_comment` are the manifests' own prose.
        r = _ContractRepo(
            extra_manifest_keys=' "_comment": "x", "_asset_writable_comment": "y",')
        r.task("t3-piercing-projectile")
        r.render("t3-piercing-projectile")   # must not raise

    @unittest.skipUnless(_VERIFY_SINGLE.is_dir(), "verify-single not present")
    def test_table_covers_every_allow_field_the_sandbox_reads(self):
        """Bound to the SANDBOX's own dataclass, not to a copy of the manifest:
        adding an allow field to sandbox.WritableManifest without teaching
        preamble.py fails HERE, at test time, instead of quietly understating
        the write scope in every prompt of the epoch."""
        import dataclasses
        import sandbox                                    # noqa: PLC0415
        allow_fields = [f.name for f in dataclasses.fields(sandbox.WritableManifest)
                        if f.name == "writable" or f.name.endswith("_writable")]
        self.assertIn("config_writable", allow_fields)    # the one that drifted
        self.assertEqual(sorted(allow_fields),
                         sorted(preamble._RENDERED_ALLOW_KEYS))


class TestContractIsNotArmConditional(unittest.TestCase):
    """FAIRNESS. This change edits the prompt for EVERY arm identically; the
    renderer has no way to know which backend will read it, and must not gain
    one. (The two disclosed per-lane qualifications — the aura-only scaffold
    excerpt and the tool-name bullets — live elsewhere in the template and are
    logged in the accommodations log.)"""

    def test_no_backend_slug_appears_in_the_write_scope_contract(self):
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        line = r.contract_line(r.render("t3-piercing-projectile"))
        for slug in _ARM_SLUGS:
            self.assertNotIn(slug, line)

    def test_write_scope_helpers_take_no_arm_parameter(self):
        """The write-scope contract is computed from the manifest and the task
        spec and from nothing else. Scoped to the helpers this change owns —
        render_preamble as a whole may legitimately grow per-lane knobs for
        OTHER parts of the prompt (see the lane-rules block and its
        ACCOMMODATIONS disclosure); what must never become lane-aware is which
        paths an agent is told it may write."""
        import inspect                                    # noqa: PLC0415
        for fn in (preamble._allow_keys_present,
                   preamble._assert_allow_keys_rendered,
                   preamble._config_files_for_task):
            params = set(inspect.signature(fn).parameters)
            self.assertFalse(params & {"arm", "model", "backend", "adapter",
                                       "lane", "provider"}, fn.__name__)

    def test_write_scope_contract_is_byte_identical_across_lanes(self):
        """The load-bearing fairness assertion: whatever else the renderer may
        vary per lane, the write-scope sentence an agent reads must be the SAME
        text for every arm. Rendered once per arm slug and compared byte for
        byte, so a future per-lane knob cannot reach it unnoticed."""
        import inspect                                    # noqa: PLC0415
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        baseline = r.contract_line(r.render("t3-piercing-projectile"))
        self.assertIn("Config/DefaultEngine.ini", baseline)  # not vacuous
        if "lane" not in inspect.signature(preamble.render_preamble).parameters:
            return          # no per-lane knob exists; the property is trivial
        for slug in _ARM_SLUGS:
            text = preamble.render_preamble(
                "t3-piercing-projectile", r.root,
                substrate_root=r.scratch, lane=slug).text
            self.assertEqual(baseline, r.contract_line(text), slug)

    def test_two_renders_of_the_same_task_are_byte_identical(self):
        r = _ContractRepo()
        r.task("t3-piercing-projectile", config_allow=[
            "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile "
            ":: +Profiles"])
        a = preamble.render_preamble("t3-piercing-projectile", r.root,
                                     substrate_root=r.scratch)
        b = preamble.render_preamble("t3-piercing-projectile", r.root,
                                     substrate_root=r.scratch)
        self.assertEqual(a.sha, b.sha)


class TestAgainstTheCommittedRepo(unittest.TestCase):
    """The hermetic tests above pin the RULE; these pin the actual epoch
    inputs, so a manifest or spec edit that breaks the agreement is caught.
    Renders against a manifest-less substrate root, which is the live graded
    path (the C1 scratch ships no AGENT_WRITABLE.json)."""

    _T3 = _REPO_ROOT / "tasks" / "bp" / "t3-piercing-projectile" / "task.md"
    _T0 = (_REPO_ROOT / "tasks" / "cpp" / "t0-sanity-log-on-beginplay"
           / "task.md")

    def _render(self, task_id: str) -> str:
        scratch = Path(tempfile.mkdtemp(prefix="cb-contract-live-"))
        return preamble.render_preamble(task_id, _REPO_ROOT,
                                        substrate_root=scratch).text

    @unittest.skipUnless(_T3.is_file(), "t3-piercing-projectile not present")
    def test_thirdperson_config_task_is_told_about_DefaultEngine_ini(self):
        line = _ContractRepo.contract_line(
            self._render("bp/t3-piercing-projectile"))
        self.assertIn("Config/DefaultEngine.ini", line)
        self.assertIn("nothing else under Config/ is writable", line)
        self.assertIn("Content/__ExternalActors__/Tasks/", line)
        self.assertIn("Content/__ExternalObjects__/Tasks/", line)

    @unittest.skipUnless(_T0.is_file(), "t0-sanity not present")
    def test_template_substrate_task_is_told_about_no_config_file(self):
        line = _ContractRepo.contract_line(
            self._render("cpp/t0-sanity-log-on-beginplay"))
        self.assertNotIn("Config/", line)
        self.assertIn("Source/CraftBenchTemplate/", line)


class TestLaneRules(unittest.TestCase):
    """The 2026-08-19 split: lane-scoped OPERATIONAL rules
    (tasks/PREAMBLE.<lane>.md) render into {lane_rules} only for their lane;
    the uniform contract stays byte-identical for everyone else (the
    write-scope fairness tests above pin the load-bearing half)."""

    _TPL = _TEMPLATE.replace(
        "# Task workspace", "{lane_rules}\n\n# Task workspace")

    def _repo(self, lane_file: bool = True, placeholder: bool = True):
        r = _Repo()
        tpl = self._TPL if placeholder else _TEMPLATE
        (r.root / "tasks" / "PREAMBLE.md").write_text(tpl, encoding="utf-8")
        if lane_file:
            (r.root / "tasks" / "PREAMBLE.aura-product.md").write_text(
                "<!-- lane notes: maintainer-only -->\n"
                "- Do not restart the editor.\n", encoding="utf-8")
        r.foldered("t0-sanity-log-on-beginplay", "SanityActor.h")
        return r

    def test_rules_render_only_for_their_lane(self):
        r = self._repo()
        with_lane = preamble.render_preamble(
            "t0-sanity-log-on-beginplay", r.root, lane="aura-product").text
        self.assertIn("Do not restart the editor.", with_lane)
        for other in (None, "bare", "unreal-mcp", "aura-mcp"):
            text = preamble.render_preamble(
                "t0-sanity-log-on-beginplay", r.root, lane=other).text
            self.assertNotIn("Do not restart the editor.", text, other)
            self.assertNotIn("{lane_rules}", text, other)

    def test_lane_maintainer_comment_is_stripped(self):
        r = self._repo()
        text = preamble.render_preamble(
            "t0-sanity-log-on-beginplay", r.root, lane="aura-product").text
        self.assertNotIn("lane notes", text)

    def test_lane_file_without_placeholder_fails_closed(self):
        # Dropping a lane's rules silently would un-tell aura-product the
        # editor-lifecycle rules that cost 5 reps to learn (2026-08-06).
        r = self._repo(placeholder=False)
        with self.assertRaises(ValueError):
            preamble.render_preamble(
                "t0-sanity-log-on-beginplay", r.root, lane="aura-product")
        # Lanes without a rules file still render fine on the same template.
        preamble.render_preamble("t0-sanity-log-on-beginplay", r.root)


if __name__ == "__main__":
    unittest.main()
