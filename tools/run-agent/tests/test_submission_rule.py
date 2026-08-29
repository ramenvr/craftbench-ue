"""The submission collector must gather EXACTLY what the verifier's sandbox accepts.

WHY THIS FILE EXISTS (measured 2026-08-19). The collector gathered a strict SUBSET
of the sandbox's accept set, and everything in the gap was discarded before
grading. Run
``runs/unreal-mcp/20260819-034252-t3-piercing-projectile-unreal-mcp-claude-sonnet-5``
graded FAIL with 8 of 9 L2I checks reporting the verifier saw nothing
(``PIERCE_CHANNEL_COUNT expected=1 got=0``, ``PIERCE_PRESET_MISSING name=Bullet
defined=[]``, ...). The agent HAD written a correct collision vocabulary to the live
project's ``Config/DefaultEngine.ini``; ``submission/`` held only three ``.uasset``
files. The rule was spelled ``manifest["writable"]`` in four places and all four
ignored ``asset_writable`` / ``config_writable`` / ``deny``.

HOW THESE TESTS ARE KEPT HONEST. Every behavioural assertion below is made twice:
once through the shipping rule, and once through :func:`_prefix_only_collect` — the
collector loop as it shipped at git HEAD before the fix, copied verbatim (its two
halves are ``run.py``'s ``_writable_files`` and the live snapshot loop). The
``TestPreFixCollectorWasBroken`` class asserts the OPPOSITE outcome for each case,
so the suite itself demonstrates that these tests are red against the broken code
rather than merely green against the fixed code. A check that cannot tell "no" from
"could not tell" is not a check; a test that passes against both versions proves
nothing.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "verify-single"))

import sandbox  # noqa: E402  (the verifier's own sandbox — the authority)
from snapshot import (  # noqa: E402
    SubmissionRule, collect_submission, snapshot_submission)
from workspace import Workspace  # noqa: E402


# The ThirdPerson substrate's manifest, reduced to the keys under test. Kept as a
# literal (not read off UE-projects/) so the test states the semantics it pins and
# does not silently change meaning when a substrate is re-scoped.
MODERN_MANIFEST = {
    "substrate": "ThirdPerson",
    "game_module": "ThirdPerson",
    "writable": ["Source/ThirdPerson/", "Content/Tasks/"],
    "asset_writable": [
        "Content/Tasks/",
        "Content/Blueprints/",
        "Content/__ExternalActors__/Tasks/",
    ],
    "config_writable": ["Config/DefaultEngine.ini", "Config/DefaultInput.ini"],
    # "Content/Blueprints/Protected/" is SYNTHETIC — no shipping manifest has an
    # overlapping deny today, and without one the deny check cannot be measured:
    # every real denied path (Content/Maps/, Source/CraftBenchTests/) is ALSO
    # outside every allow prefix, so it is rejected by allowlist-miss whether deny
    # is consulted or not. An implementation that dropped deny entirely would pass
    # a deny test built only on the real manifest. This entry is the one input on
    # which "deny wins" is load-bearing.
    "deny": [
        "Source/CraftBenchTests/",
        "Content/Maps/",
        "Content/Blueprints/Protected/",
        "AGENT_WRITABLE.json",
    ],
}

# A substrate manifest from before asset_writable / config_writable / deny existed.
# REQUIREMENT 3: this must behave exactly as the pre-fix collector did.
LEGACY_MANIFEST = {
    "substrate": "Legacy",
    "game_module": "Legacy",
    "writable": ["Source/ThirdPerson/", "Content/Tasks/"],
}

#: baseline rel-path -> bytes. The substrate as committed, before the agent ran.
BASELINE_FILES = {
    "AGENT_WRITABLE.json": None,               # written from the manifest under test
    "Source/ThirdPerson/Existing.cpp": b"// substrate\n",
    "Source/CraftBenchTests/Fixture.cpp": b"// verifier-owned\n",
    "Config/DefaultEngine.ini": b"[/Script/Engine]\n",
    "Config/DefaultInput.ini": b"[/Script/Input]\n",
    "Config/SomethingElse.ini": b"[/Script/Other]\n",
    "Content/Maps/t3/L_Map.umap": b"MAPBYTES-baseline",
    "Content/Tasks/t3/Existing.uasset": b"ASSET-baseline",
}

#: rel-path -> bytes the agent leaves behind. Every one of these DIFFERS from its
#: baseline (or has none), so "was it collected?" isolates the RULE, never the diff.
AGENT_EDITS = {
    # Plain writable source edit — collected before and after the fix.
    "Source/ThirdPerson/Existing.cpp": b"// substrate\n// agent\n",
    # The measured bug: a config file listed by EXACT path in config_writable.
    "Config/DefaultEngine.ini": b"[/Script/Engine]\n[/Script/Engine.CollisionProfile]\n",
    # Exact-path semantics: Config/ is NOT a prefix, so a sibling ini stays out.
    "Config/SomethingElse.ini": b"[/Script/Other]\n; agent\n",
    # asset_writable prefix, asset extension -> collected.
    "Content/Blueprints/BP_Thing.uasset": b"ASSET-new",
    # asset_writable prefix, NON-asset extension -> rejected by the extension gate.
    "Content/Blueprints/notes.txt": b"not an asset\n",
    # deny wins over everything, including the Content/ family.
    "Content/Maps/t3/L_Map.umap": b"MAPBYTES-agent",
    # An asset that matches an asset_writable prefix AND a deny prefix. This is
    # the only file in the fixture whose verdict CHANGES if deny is not consulted.
    "Content/Blueprints/Protected/BP_Locked.uasset": b"ASSET-locked",
    # Verifier-owned module: denied.
    "Source/CraftBenchTests/Fixture.cpp": b"// tampered\n",
    # Ordinary writable asset deliverable.
    "Content/Tasks/t3/New.uasset": b"ASSET-task",
    # Outside every prefix.
    "STRAY_NOTE.txt": b"stray\n",
}


def _write(root: Path, rel: str, data: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def _build_trees(tmp: Path, manifest: dict) -> tuple[Path, Path]:
    """Return (baseline_dir, project_dir): the substrate, and it after the agent."""
    baseline = tmp / "substrate"
    project = tmp / "project"
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    for rel, data in BASELINE_FILES.items():
        payload = manifest_bytes if data is None else data
        _write(baseline, rel, payload)
        _write(project, rel, payload)
    for rel, data in AGENT_EDITS.items():
        _write(project, rel, data)
    return baseline, project


def _prefix_only_collect(project_dir: Path, baseline_dir: Path,
                         submission_dir: Path, manifest_path: Path) -> list[str]:
    """THE PRE-FIX COLLECTOR, verbatim from git HEAD before 2026-08-19.

    Two halves of ``run.py::_run_live_project``, unchanged except for being
    parameterised: ``_writable_files`` (prefix match on ``manifest["writable"]``
    only) and the live snapshot loop that diffs against the backup. This is the
    broken case the tests below are measured against.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    writable_prefixes = manifest["writable"]

    def _writable_files():
        out = []
        for p in project_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(project_dir).as_posix()
            if any(rel.startswith(pre) for pre in writable_prefixes):
                out.append(p)
        return out

    staged = []
    for p in _writable_files():
        rel = p.relative_to(project_dir).as_posix()
        b = baseline_dir / rel
        if (not b.exists()) or (b.read_bytes() != p.read_bytes()):
            dst = submission_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            staged.append(rel)
    return staged


class _TreeCase(unittest.TestCase):
    """Shared fixture: a substrate, the same tree after an agent drive, and a rule."""

    MANIFEST = MODERN_MANIFEST

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-submission-rule-"))
        self.baseline, self.project = _build_trees(self.tmp, self.MANIFEST)
        self.submission = self.tmp / "submission"
        self.rule = SubmissionRule.for_substrate(self.baseline)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def collected(self) -> set:
        """Rel-paths the SHIPPING collector stages."""
        staged = collect_submission(
            self.project, self.baseline, self.submission, self.rule)
        return {p.relative_to(self.submission).as_posix() for p in staged}

    def collected_prefix_only(self) -> set:
        """Rel-paths the PRE-FIX collector stages, same tree."""
        return set(_prefix_only_collect(
            self.project, self.baseline, self.tmp / "submission_prefix",
            self.baseline / "AGENT_WRITABLE.json"))


class TestCollectorMatchesSandbox(_TreeCase):
    """REQUIREMENTS 1+2: one rule, all four manifest keys, real semantics."""

    def test_asset_under_asset_writable_prefix_is_collected(self):
        # Content/Blueprints/ is asset_writable but NOT writable. Pre-fix: dropped.
        self.assertIn("Content/Blueprints/BP_Thing.uasset", self.collected())

    def test_config_file_listed_by_exact_path_is_collected(self):
        # THE measured bug: t3-piercing-projectile's whole deliverable half.
        self.assertIn("Config/DefaultEngine.ini", self.collected())

    def test_other_config_file_is_not_collected(self):
        # config_writable entries are EXACT FILE PATHS, never a Config/ prefix —
        # the manifest's own warning: a broad Config/ prefix would path-accept
        # arbitrary engine-config edits with no semantic gate.
        # DISCRIMINATES AGAINST: collapsing config_writable into a prefix. That
        # wrong fix is red here and green everywhere else in this file.
        self.assertNotIn("Config/SomethingElse.ini", self.collected())

    def test_denied_path_under_content_is_not_collected(self):
        # Content/Maps/ is a verifier-owned map tree: rejected even though it is
        # under Content/ and carries an asset extension. NOTE this case alone does
        # NOT measure the deny check — Content/Maps/ is outside every allow prefix
        # too, so allowlist-miss would reject it anyway. The next test is the one
        # that measures deny.
        self.assertNotIn("Content/Maps/t3/L_Map.umap", self.collected())

    def test_deny_wins_over_an_asset_writable_prefix(self):
        # DISCRIMINATES AGAINST: an implementation that never consults deny.
        # BP_Locked.uasset matches asset_writable "Content/Blueprints/" AND deny
        # "Content/Blueprints/Protected/"; deny wins.
        self.assertNotIn("Content/Blueprints/Protected/BP_Locked.uasset",
                         self.collected())
        # ...and its non-denied sibling is still collected, so the assertion above
        # cannot be passing because the whole folder was dropped.
        self.assertIn("Content/Blueprints/BP_Thing.uasset", self.collected())

    def test_denied_verifier_module_is_not_collected(self):
        self.assertNotIn("Source/CraftBenchTests/Fixture.cpp", self.collected())

    def test_non_asset_file_under_asset_writable_prefix_is_not_collected(self):
        # asset_writable widens which generated-ASSET folders are gradeable, never
        # which source/config paths an agent may write.
        self.assertNotIn("Content/Blueprints/notes.txt", self.collected())

    def test_writable_source_and_task_assets_still_collected(self):
        got = self.collected()
        self.assertIn("Source/ThirdPerson/Existing.cpp", got)
        self.assertIn("Content/Tasks/t3/New.uasset", got)

    def test_stray_file_outside_every_prefix_is_not_collected(self):
        self.assertNotIn("STRAY_NOTE.txt", self.collected())

    def test_unmodified_files_are_not_collected(self):
        # The collector stages a DIFF, not the writable area.
        self.assertNotIn("Config/DefaultInput.ini", self.collected())
        self.assertNotIn("Content/Tasks/t3/Existing.uasset", self.collected())

    def test_accept_set_equals_the_verifier_sandbox_accept_set(self):
        """ANTI-DRIFT: rule.accepts agrees with sandbox's PUBLIC scan_submission.

        Not a restatement of the delegation — it runs the verifier's own tree
        scanner over a directory holding EVERY file in the project and compares
        the two accept sets. A semantic change in sandbox.py that the import
        alone would not notice shows up here.
        """
        everything = self.tmp / "everything"
        for p in sorted(self.project.rglob("*")):
            if p.is_file():
                _write(everything, p.relative_to(self.project).as_posix(),
                       p.read_bytes())
        manifest = sandbox.WritableManifest.load(
            self.baseline / "AGENT_WRITABLE.json")
        sandbox_accepted = {
            rel for _p, rel in sandbox.scan_submission(everything, manifest).accepted}
        all_rels = {p.relative_to(everything).as_posix()
                    for p in everything.rglob("*") if p.is_file()}
        rule_accepted = {rel for rel in all_rels if self.rule.accepts(rel)}
        self.assertEqual(sandbox_accepted, rule_accepted)
        self.assertTrue(sandbox_accepted, "fixture accepted nothing — vacuous pass")


class TestTheMeasuredRegression(unittest.TestCase):
    """The 2026-08-19 t3-piercing-projectile cell, against the SHIPPING manifest.

    The classes above run on a hand-written manifest so they state their own
    semantics. This one runs on ``UE-projects/ThirdPerson/AGENT_WRITABLE.json`` as
    committed, so that if the substrate is ever re-scoped in a way that re-closes
    the config lane, the failure names this run rather than an abstract rule.
    """

    REPO_ROOT = Path(__file__).resolve().parents[3]

    def setUp(self):
        manifest = self.REPO_ROOT / "UE-projects/ThirdPerson/AGENT_WRITABLE.json"
        if not manifest.is_file():
            self.skipTest(f"substrate manifest not present at {manifest}")
        self.rule = SubmissionRule.load(manifest)

    def test_the_dropped_deliverable_half_is_now_submittable(self):
        # The agent wrote [/Script/Engine.CollisionProfile] +DefaultChannelResponses
        # / +Profiles here; submission/ held only the three .uasset files and the
        # verifier reported defined=[] on 8 of 9 L2I checks.
        self.assertTrue(self.rule.accepts("Config/DefaultEngine.ini"))

    def test_the_uassets_that_did_arrive_still_arrive(self):
        self.assertTrue(self.rule.accepts(
            "Content/Tasks/t3-piercing-projectile/BP_PiercingBullet.uasset"))

    def test_the_lane_did_not_widen_to_the_rest_of_config(self):
        # The manifest's own warning: never add a broad Config/ writable prefix.
        for rel in ("Config/DefaultGame.ini", "Config/DefaultEditor.ini",
                    "Config/DefaultGameplayTags.ini"):
            self.assertFalse(self.rule.accepts(rel), rel)

    def test_the_lane_did_not_widen_to_protected_content(self):
        for rel in ("Content/Maps/t3-piercing-projectile/L_Pierce.umap",
                    "Content/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.uasset",
                    "Content/Input/IMC_Default.uasset",
                    "Content/__ExternalActors__/ThirdPerson/A/B/C.uasset"):
            self.assertFalse(self.rule.accepts(rel), rel)


class TestManifestParseMatchesTheVerifier(unittest.TestCase):
    """SubmissionRule.load must parse a manifest into the same object sandbox does.

    Field wiring is the ONE thing snapshot.py restates (sandbox's loader requires
    ``substrate``/``game_module``; the harness's own tests build manifests without
    them). This runs both loaders over every committed manifest and demands an
    equal dataclass — so a key added to sandbox's loader cannot be silently
    dropped by ours.
    """

    REPO_ROOT = Path(__file__).resolve().parents[3]

    def test_every_committed_manifest_parses_identically(self):
        manifests = sorted((self.REPO_ROOT / "UE-projects").glob(
            "*/AGENT_WRITABLE.json"))
        self.assertTrue(manifests, "no substrate manifests found — vacuous pass")
        for path in manifests:
            with self.subTest(manifest=path.name, substrate=path.parent.name):
                self.assertEqual(
                    SubmissionRule.load(path).manifest,
                    sandbox.WritableManifest.load(path))

    def test_manifest_without_identity_keys_still_loads(self):
        # sandbox.WritableManifest.load raises KeyError here; ours must not.
        # Measured while wiring the fix in: requiring the identity keys broke 9
        # harness tests that build a manifest with only "writable".
        tmp = Path(tempfile.mkdtemp(prefix="cb-legacy-manifest-"))
        try:
            path = tmp / "AGENT_WRITABLE.json"
            path.write_text(json.dumps({"writable": ["Source/X/"]}),
                            encoding="utf-8")
            rule = SubmissionRule.load(path)
            self.assertTrue(rule.accepts("Source/X/A.cpp"))
            self.assertFalse(rule.accepts("Source/Y/A.cpp"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_windows_separators_normalize_like_the_verifier(self):
        rule = SubmissionRule.from_manifest_data(
            {"writable": ["Source\\ThirdPerson\\"], "deny": ["./Content/Maps/"]})
        self.assertTrue(rule.accepts("Source/ThirdPerson/A.cpp"))
        self.assertFalse(rule.accepts("Content/Maps/L_A.umap"))


class TestPreFixCollectorWasBroken(_TreeCase):
    """The same cases through the pre-fix collector: each assertion above is RED.

    This class is the evidence that the tests discriminate. If a future change
    makes one of these fail, the pre-fix behaviour has been misdescribed here —
    fix the description, do not delete the class.
    """

    def test_asset_under_asset_writable_prefix_was_dropped(self):
        self.assertNotIn("Content/Blueprints/BP_Thing.uasset",
                         self.collected_prefix_only())

    def test_config_file_was_dropped(self):
        self.assertNotIn("Config/DefaultEngine.ini", self.collected_prefix_only())

    def test_other_config_file_was_also_dropped(self):
        # Pre-fix this case was "right for the wrong reason": ALL of Config/ was
        # dropped, so the exact-path semantics were never exercised at all.
        self.assertNotIn("Config/SomethingElse.ini", self.collected_prefix_only())

    def test_denied_map_was_dropped_by_allowlist_miss_not_by_deny(self):
        # Also right for the wrong reason: deny was never consulted; Content/Maps/
        # merely missed the writable prefixes. A manifest that made a denied path
        # writable would have leaked, and nothing would have caught it.
        self.assertNotIn("Content/Maps/t3/L_Map.umap", self.collected_prefix_only())
        self.assertNotIn("Source/CraftBenchTests/Fixture.cpp",
                         self.collected_prefix_only())

    def test_the_gap_is_exactly_the_two_lanes_the_fix_opens(self):
        gap = self.collected() - self.collected_prefix_only()
        self.assertEqual(
            gap,
            {"Config/DefaultEngine.ini", "Content/Blueprints/BP_Thing.uasset"})
        # ...and the fix never NARROWS the set: nothing that used to be collected
        # is dropped now.
        self.assertEqual(self.collected_prefix_only() - self.collected(), set())


class TestLegacyManifestUnchanged(_TreeCase):
    """REQUIREMENT 3: a manifest without the three optional keys behaves as before.

    Pinned as an EQUALITY against the pre-fix collector on the same tree, which is
    the only formulation that can catch a widening nobody intended.
    """

    MANIFEST = LEGACY_MANIFEST

    def test_matches_the_pre_fix_collector_exactly(self):
        self.assertEqual(self.collected(), self.collected_prefix_only())

    def test_and_that_set_is_not_empty(self):
        # Guard against the equality above passing because BOTH returned nothing.
        self.assertIn("Source/ThirdPerson/Existing.cpp", self.collected())
        self.assertIn("Content/Tasks/t3/New.uasset", self.collected())

    def test_missing_keys_read_as_empty_not_as_absent_gate(self):
        self.assertEqual(self.rule.manifest.asset_writable, ())
        self.assertEqual(self.rule.manifest.config_writable, ())
        self.assertEqual(self.rule.manifest.deny, ())
        # No deny key must NOT mean "deny everything" or "accept everything":
        # allowlist-miss still rejects.
        self.assertFalse(self.rule.accepts("Content/Maps/t3/L_Map.umap"))
        self.assertFalse(self.rule.accepts("Config/DefaultEngine.ini"))
        self.assertTrue(self.rule.accepts("Content/Tasks/t3/New.uasset"))


class TestUntrackedScanPrefixes(_TreeCase):
    """The live pre-drive hygiene gate scans the area the collector reads."""

    def test_covers_writable_and_asset_writable(self):
        prefixes = self.rule.untracked_scan_prefixes()
        self.assertIn("Source/ThirdPerson/", prefixes)
        self.assertIn("Content/Tasks/", prefixes)
        self.assertIn("Content/Blueprints/", prefixes)
        self.assertEqual(len(prefixes), len(set(prefixes)), "duplicated prefix")

    def test_excludes_config_paths(self):
        # A config file is the substrate's OWN committed file, never an
        # agent-created leftover; quarantining one would move the project's
        # engine config out of the tree.
        self.assertNotIn("Config/DefaultEngine.ini",
                         self.rule.untracked_scan_prefixes())

    def test_deny_wins_over_a_writable_prefix(self):
        manifest = dict(MODERN_MANIFEST)
        manifest["asset_writable"] = ["Content/Blueprints/", "Content/Abilities/"]
        manifest["deny"] = list(MODERN_MANIFEST["deny"]) + ["Content/Abilities/"]
        path = self.tmp / "deny_test_manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        rule = SubmissionRule.load(path)
        self.assertIn("Content/Blueprints/", rule.untracked_scan_prefixes())
        self.assertNotIn("Content/Abilities/", rule.untracked_scan_prefixes())


class TestWorkspaceLaneUsesTheSameRule(_TreeCase):
    """Call site 4: snapshot_submission (bare / claude-p / openrouter lanes)."""

    def test_snapshot_submission_collects_config_and_assets(self):
        ws = Workspace(
            root=self.tmp, project_dir=self.project,
            prompt_path=self.tmp / "PROMPT.md",
            writable_files=[], readonly_files=[],
            # Deliberately WRONG/narrow: the collector must no longer read its
            # rule out of this field. Before the fix this alone decided the
            # submission, which is how the two lanes drifted apart.
            writable_prefixes=["Source/ThirdPerson/"],
        )
        staged = snapshot_submission(ws, self.submission, self.baseline)
        rels = {p.relative_to(self.submission).as_posix() for p in staged}
        self.assertIn("Config/DefaultEngine.ini", rels)
        self.assertIn("Content/Blueprints/BP_Thing.uasset", rels)
        self.assertIn("Content/Tasks/t3/New.uasset", rels)
        self.assertNotIn("Content/Maps/t3/L_Map.umap", rels)


class TestLiveBackupAndRestoreCoverTheSameSet(_TreeCase):
    """Call sites 1+2: the live lane's backup and its end-of-run restore.

    SECOND MEASURED BUG, 2026-08-19: the same run that lost its config deliverable
    also never RESTORED it — live_backup/ held only Content and Source, so the
    agent's Config/DefaultEngine.ini edit leaked into the live tree and only the
    batch's ``git checkout`` caught it. Backup and restore read the collector's
    rule, so widening the collector fixes the leak in the same stroke; this test
    is what says so rather than assuming it.
    """

    def test_backup_set_includes_config_and_assets(self):
        pre_rels = {p.relative_to(self.baseline).as_posix()
                    for p in self.rule.files_under(self.baseline)}
        self.assertIn("Config/DefaultEngine.ini", pre_rels)
        self.assertIn("Config/DefaultInput.ini", pre_rels)
        self.assertNotIn("Config/SomethingElse.ini", pre_rels)
        self.assertNotIn("Content/Maps/t3/L_Map.umap", pre_rels)

    def test_restore_puts_the_config_edit_back_and_removes_created_files(self):
        import run  # imported lazily: pulls the whole adapter registry

        # Stand in for run_dir/live_backup: the pre-drive bytes of the whole
        # submittable area, exactly as _run_live_project takes it.
        backup = self.tmp / "live_backup"
        pre_rels = set()
        for p in self.rule.files_under(self.baseline):
            rel = p.relative_to(self.baseline).as_posix()
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            pre_rels.add(rel)
        self.assertIn("Config/DefaultEngine.ini", pre_rels)

        # self.project already carries the agent's edits (AGENT_EDITS), including
        # the config edit and a created Content/Blueprints/ asset.
        out = run._restore_live_writable(
            self.project, backup, pre_rels,
            lambda: self.rule.files_under(self.project),
            run_dir=self.tmp, log=lambda _m: None)

        self.assertTrue(out["ok"], out)
        self.assertEqual(
            (self.project / "Config/DefaultEngine.ini").read_bytes(),
            BASELINE_FILES["Config/DefaultEngine.ini"],
            "the agent's config edit was not restored — this is the leak")
        self.assertFalse((self.project / "Content/Blueprints/BP_Thing.uasset").exists(),
                         "an agent-created asset survived the restore")
        # Files the rule does not cover are NOT the restore's business: an edit to
        # a non-submittable path is left exactly as found (the fairness state and
        # git own those), so the restore's blast radius equals the collector's.
        self.assertEqual(
            (self.project / "Config/SomethingElse.ini").read_bytes(),
            AGENT_EDITS["Config/SomethingElse.ini"])


class TestLoadWorkspaceFromDiskUsesTheSameRule(_TreeCase):
    """Call site 3: run.py::_load_workspace_from_disk (--workspace reuse)."""

    def test_writable_files_classified_by_the_full_rule(self):
        import run  # imported lazily: pulls the whole adapter registry

        # _load_workspace_from_disk expects <workspace_root>/<substrate.name>/.
        ws_root = self.tmp / "ws"
        ws_root.mkdir()
        shutil.copytree(self.project, ws_root / self.baseline.name)
        (ws_root / "PROMPT.md").write_text("task", encoding="utf-8")

        ws = run._load_workspace_from_disk(
            ws_root, self.baseline, self.baseline / "AGENT_WRITABLE.json")
        rels = {p.relative_to(ws.project_dir).as_posix() for p in ws.writable_files}
        self.assertIn("Config/DefaultEngine.ini", rels)
        self.assertIn("Content/Blueprints/BP_Thing.uasset", rels)
        self.assertNotIn("Content/Maps/t3/L_Map.umap", rels)
        self.assertNotIn("Content/Blueprints/notes.txt", rels)


if __name__ == "__main__":
    unittest.main()
