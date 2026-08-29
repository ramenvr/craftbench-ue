"""Unit tests for the CraftBench verifier runner.

These tests must not require a UE installation. They exercise:

  - The task-spec parsing shim (run_task.parse_task_spec -> spec.parse_task_file).
  - The sandbox path-prefix enforcement (deny under CraftBenchTests/).
  - The Report serializer round-trip (incl. substrate_source provenance).
  - The retirement of the verifier-hash manifest gate (--regen flags gone,
    exit 3 retired; git provenance replaced it).
  - The dual-target L1 driver against a fake UBT script.
"""

from __future__ import annotations

import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

# Make the verify package importable when running this file directly.
_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402
from report import HostInfo, LayerReport, Report, report_from_dict  # noqa: E402
from run_task import (  # noqa: E402
    Fixture,
    TaskSpec,
    _apply_task_rhi,
    _apply_visible_capture,
    _parse_fixtures_block,
    _parse_framerate_legs,
    _parse_metadata_block,
    _resolve_repo_root_for,
    _split_h2_sections,
    _stage_config_overlay,
    _substrate_dir_name,
    build_parser,
    copy_substrate,
    derive_test_filter,
    parse_task_spec,
    robust_rmtree,
)
from layers.l1_build import run_l1  # noqa: E402
from layers.l2_pie import parse_automation_log, parse_index_json  # noqa: E402
from sandbox import WritableManifest, _is_writable, scan_submission  # noqa: E402


REPO_ROOT = _VERIFY.parents[1]
T0_TASK_PATH = REPO_ROOT / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "task.md"
TEMPLATE_MANIFEST = (
    REPO_ROOT / "UE-projects" / "CraftBenchTemplate" / "AGENT_WRITABLE.json"
)


def _make_test_dir_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


class TestRobustRmtree(unittest.TestCase):
    """The Windows-safe workdir cleanup (`robust_rmtree`) that tolerates the
    transient `.umap` lock a just-finished L2 editor leaves on the workdir —
    the "process cannot access L_SanityTask.umap, being used by another process"
    (WinError 32) failure. It must remove a normal tree, no-op on a missing
    path, and NEVER raise when a handle is still open (retry -> non-raising sweep)."""

    def test_removes_a_normal_tree(self) -> None:
        d = tempfile.mkdtemp()
        (Path(d) / "Content" / "Maps").mkdir(parents=True)
        (Path(d) / "Content" / "Maps" / "L_SanityTask.umap").write_bytes(b"0")
        self.assertTrue(robust_rmtree(d, retries=2))
        self.assertFalse(os.path.exists(d))

    def test_missing_path_is_noop_true(self) -> None:
        self.assertTrue(robust_rmtree(os.path.join(tempfile.gettempdir(), "cb-nope-xyz")))

    def test_open_handle_never_raises(self) -> None:
        # Simulate the lingering-handle case cross-platform: hold an open file and
        # confirm cleanup degrades gracefully (never raises) instead of crashing.
        d = tempfile.mkdtemp()
        umap = Path(d) / "L_SanityTask.umap"
        umap.write_bytes(b"0")
        logs: list[str] = []
        fh = open(umap, "rb")
        try:
            # On Windows an open handle blocks delete (WinError 32) -> retries then
            # a non-raising sweep. On POSIX the delete succeeds; either way NO raise.
            result = robust_rmtree(d, retries=2, base_delay=0.05, log=logs.append)
            self.assertIsInstance(result, bool)  # returned, did not raise
            if platform.system() == "Windows":
                self.assertFalse(result)            # left locked
                # Assert on robust_rmtree's OWN warning text, not the embedded
                # OS strerror — Windows localizes WinError 32's message, so the
                # English "another process" substring fails on non-English boxes.
                self.assertTrue(any(
                    "not fully removed (a process still holds a file under it)" in m
                    for m in logs))
        finally:
            fh.close()
            shutil.rmtree(d, ignore_errors=True)

    def test_removes_a_plain_file(self) -> None:
        # A FILE is not an rmtree job. shutil.rmtree raises NotADirectoryError,
        # which IS an OSError, so the retry loop used to swallow it, burn every
        # attempt of backoff, then no-op its ignore_errors sweep and return False.
        # Measured cost of that bug: ~4.8h to delete the 1814 leaked
        # cb-aura-driver-*.json temp files on a real box (2026-07-25).
        fd, p = tempfile.mkstemp(prefix="cb-aura-driver-", suffix=".json")
        os.close(fd)
        self.assertTrue(robust_rmtree(p, retries=2))
        self.assertFalse(os.path.exists(p))

    def test_file_delete_is_fast_not_a_retry_storm(self) -> None:
        # Guards the regression by TIME: the old path slept through every retry
        # before giving up. base_delay is deliberately large here, so a single
        # unlink finishes instantly while a retry storm could not.
        fd, p = tempfile.mkstemp(prefix="cb-aura-driver-", suffix=".json")
        os.close(fd)
        t0 = time.monotonic()
        self.assertTrue(robust_rmtree(p, retries=6, base_delay=1.0))
        self.assertLess(time.monotonic() - t0, 1.0)

    def test_missing_file_is_noop_true(self) -> None:
        p = os.path.join(tempfile.gettempdir(), "cb-aura-driver-nope-xyz.json")
        self.assertTrue(robust_rmtree(p))


class TestTaskParser(unittest.TestCase):
    def test_t0_task_extracts_id_and_layers(self) -> None:
        # T0 is a spec-v2 (front matter) file; run_task.parse_task_spec is a
        # thin shim over spec.parse_task_file, so it must parse identically.
        self.assertTrue(T0_TASK_PATH.exists(), f"missing {T0_TASK_PATH}")
        spec = parse_task_spec(T0_TASK_PATH)
        self.assertEqual(spec.task_id, "t0-sanity-log-on-beginplay")
        self.assertEqual(_substrate_dir_name(spec.substrate), "CraftBenchTemplate")
        self.assertEqual(spec.layers, ("L1", "L2"))
        # Hint extraction: map name + test-runner class (from fixtures[0])
        self.assertEqual(spec.map_name, "L_SanityTask")
        self.assertEqual(spec.test_class_hint, "ASanityFunctionalTest")
        self.assertFalse(spec.legacy)

    def test_legacy_h2_spec_still_parses_via_shim(self) -> None:
        # A pre-front-matter spec keeps parsing through the legacy fallback,
        # flagged legacy=True.
        body = (
            "# Legacy\n\n"
            "## Task ID and metadata\n"
            "- task_id: legacy-sample\n"
            "- substrate: template\n\n"
            "## Verifier layers used\n"
            "L1, L2\n\n"
            "## Verifier specification\n"
            "Uses Content/Maps/L_SanityTask.umap and ASanityFunctionalTest.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "task.md"
            spec_path.write_text(body, encoding="utf-8")
            spec = parse_task_spec(spec_path)
            self.assertEqual(spec.task_id, "legacy-sample")
            self.assertEqual(spec.substrate, "template")
            self.assertEqual(spec.layers, ("L1", "L2"))
            self.assertEqual(spec.map_name, "L_SanityTask")
            self.assertEqual(spec.test_class_hint, "ASanityFunctionalTest")
            self.assertTrue(spec.legacy)

    def test_folder_form_spec_falls_back_to_folder_name(self) -> None:
        # Folder-per-task layout: tasks/<set>/<id>/task.md with NO metadata
        # block derives task_id from the FOLDER name, not the "task" stem.
        body = "# Foo task\n\n## Verifier layers used\nL1, L2\n"
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "tasks" / "flagship" / "foo" / "task.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(body, encoding="utf-8")
            spec = parse_task_spec(spec_path)
            self.assertEqual(spec.task_id, "foo")

    def test_flat_spec_falls_back_to_file_stem(self) -> None:
        # Legacy flat layout keeps the file-stem fallback unchanged.
        body = "# Bar task\n\n## Verifier layers used\nL1, L2\n"
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "tasks" / "bar.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(body, encoding="utf-8")
            spec = parse_task_spec(spec_path)
            self.assertEqual(spec.task_id, "bar")

    def test_split_h2_sections_basic(self) -> None:
        md = "# Title\n\n## A\nfoo\n\n## B\nbar\n### nested\nbaz\n"
        sections = _split_h2_sections(md)
        self.assertEqual(sections["A"], "foo")
        self.assertIn("bar", sections["B"])
        self.assertIn("nested", sections["B"])

    def test_parse_metadata_block_picks_up_kebab_values(self) -> None:
        block = (
            "- task_id: t0-sanity-log-on-beginplay\n"
            "- tier: T0\n"
            "- substrate: template\n"
        )
        meta = _parse_metadata_block(block)
        self.assertEqual(meta["task_id"], "t0-sanity-log-on-beginplay")
        self.assertEqual(meta["tier"], "T0")
        self.assertEqual(meta["substrate"], "template")

    def test_map_name_extracted_from_foldered_umap_path(self) -> None:
        # Post-migration layout: Content/Maps/<task-id>/<map>.umap — the map
        # regex tolerates ONE folder segment (incl. hyphens) before the L_ name.
        body = (
            "# Foo\n\n## Verifier layers used\nL1, L2\n\n"
            "## Verifier specification\n"
            "Uses Content/Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "task.md"
            spec_path.write_text(body, encoding="utf-8")
            spec = parse_task_spec(spec_path)
            self.assertEqual(spec.map_name, "L_SanityTask")

    def test_map_name_flat_umap_path_still_extracted(self) -> None:
        # Guardrail: the pre-migration flat form is unchanged by the widening.
        body = (
            "# Foo\n\n## Verifier layers used\nL1, L2\n\n"
            "## Verifier specification\n"
            "Uses Content/Maps/L_TimerTask.umap\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "task.md"
            spec_path.write_text(body, encoding="utf-8")
            spec = parse_task_spec(spec_path)
            self.assertEqual(spec.map_name, "L_TimerTask")

    def test_derive_test_filter_uses_map_and_test_class(self) -> None:
        spec = parse_task_spec(T0_TASK_PATH)
        f = derive_test_filter(spec)
        # Format verified against UE 5.7's own "Automation List" output.
        self.assertEqual(
            f, "Project.Functional Tests.Maps.L_SanityTask.SanityFunctionalTest"
        )

    def test_derive_test_filter_explicit_wins(self) -> None:
        spec = parse_task_spec(T0_TASK_PATH)
        f = derive_test_filter(spec, explicit="My.Custom.Filter")
        self.assertEqual(f, "My.Custom.Filter")

    def test_derive_test_filter_prefix_for_map_folders_the_map_segment(self) -> None:
        # A foldered map contributes its folder as an extra dot segment
        # between "Maps" and the map name (UE's slashes-to-dots conversion).
        spec = parse_task_spec(T0_TASK_PATH)
        f = derive_test_filter(
            spec, prefix_for_map=lambda m: "t0-sanity-log-on-beginplay"
        )
        self.assertEqual(
            f,
            "Project.Functional Tests.Maps.t0-sanity-log-on-beginplay"
            ".L_SanityTask.SanityFunctionalTest",
        )

    def test_derive_test_filter_prefix_for_map_empty_keeps_root_form(self) -> None:
        # Root maps report "" — the filter must stay byte-identical to today.
        spec = parse_task_spec(T0_TASK_PATH)
        f = derive_test_filter(spec, prefix_for_map=lambda m: "")
        self.assertEqual(
            f, "Project.Functional Tests.Maps.L_SanityTask.SanityFunctionalTest"
        )

    def test_derive_test_filter_default_none_byte_identical(self) -> None:
        spec = parse_task_spec(T0_TASK_PATH)
        self.assertEqual(
            derive_test_filter(spec),
            derive_test_filter(spec, prefix_for_map=None),
        )


class TestSandbox(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            TEMPLATE_MANIFEST.exists(), f"missing {TEMPLATE_MANIFEST}"
        )
        self.manifest = WritableManifest.load(TEMPLATE_MANIFEST)

    def test_accepts_writable_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "Source" / "CraftBenchTemplate" / "SanityActor.cpp"
            good.parent.mkdir(parents=True)
            good.write_text("// agent code\n")
            result = scan_submission(root, self.manifest)
            self.assertTrue(result.ok, msg=result.render_report())
            self.assertEqual(len(result.accepted), 1)

    def test_rejects_write_under_tests_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "Source" / "CraftBenchTests" / "SanityFunctionalTest.cpp"
            bad.parent.mkdir(parents=True)
            bad.write_text("// tampering\n")
            result = scan_submission(root, self.manifest)
            self.assertFalse(result.ok)
            self.assertEqual(len(result.violations), 1)
            self.assertIn("denied", result.violations[0].reason.lower())

    def test_rejects_config_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Config").mkdir()
            (root / "Config" / "DefaultEngine.ini").write_text("[X]\n")
            (root / "Content").mkdir()
            (root / "Content" / "Foo.uasset").write_bytes(b"\x00")
            result = scan_submission(root, self.manifest)
            self.assertFalse(result.ok)
            rels = sorted(v.rel_path for v in result.violations)
            self.assertEqual(
                rels, ["Config/DefaultEngine.ini", "Content/Foo.uasset"]
            )

    def test_rejects_files_outside_writable_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Source" / "OtherModule").mkdir(parents=True)
            (root / "Source" / "OtherModule" / "Stuff.cpp").write_text("x\n")
            result = scan_submission(root, self.manifest)
            self.assertFalse(result.ok)
            self.assertIn("not under any writable prefix", result.violations[0].reason)


class TestGameFeaturePluginSandbox(unittest.TestCase):
    TASK_ROOT = (
        "Plugins/GameFeatures/Tasks/"
        "t2-the-capability-exists-only-while-enabled/CBEnabledCapability")
    CONTENT_ROOT = TASK_ROOT + "/Content"

    def setUp(self) -> None:
        self.manifest = WritableManifest.load(TEMPLATE_MANIFEST)

    def test_exact_plugin_asset_packages_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("GameFeatureData.uasset",
                         "BP_EnabledPulseComponent.uasset"):
                path = root / self.CONTENT_ROOT / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"asset")
            result = scan_submission(root, self.manifest)
            self.assertTrue(result.ok, result.render_report())
            self.assertEqual(len(result.accepted), 2)

    def test_descriptor_source_config_text_neighbor_and_host_plugins_rejected(self):
        rejected = (
            self.TASK_ROOT + "/CBEnabledCapability.uplugin",
            self.TASK_ROOT + "/Source/Escape.cpp",
            self.TASK_ROOT + "/Config/DefaultGame.ini",
            self.CONTENT_ROOT + "/NotAnAsset.txt",
            "Plugins/GameFeatures/Tasks/"
            "t2-the-capability-exists-only-while-enabled/OtherFeature/"
            "Content/Escape.uasset",
            "Plugins/Aura/Content/Escape.uasset",
            "Plugins/Ramen/Content/Escape.uasset",
            "Plugins/.git/objects/Escape.uasset",
            "Plugins/.claude/Escape.uasset",
        )
        for rel in rejected:
            with self.subTest(rel=rel):
                allowed, reason = _is_writable(rel, self.manifest)
                self.assertFalse(allowed, reason)
        allowed, reason = _is_writable(
            "plugins/aura/content/Escape.uasset", self.manifest)
        self.assertFalse(allowed)
        self.assertIn("denied", reason)

    def test_case_and_backslash_normalization_accept_exact_asset(self) -> None:
        mixed_case = self.CONTENT_ROOT.lower() + "/gamefeaturedata.UASSET"
        backslashes = (self.CONTENT_ROOT + "/BP_EnabledPulseComponent.uasset"
                       ).replace("/", "\\")
        self.assertTrue(_is_writable(mixed_case, self.manifest)[0])
        self.assertTrue(_is_writable(backslashes, self.manifest)[0])

    def test_traversal_and_absolute_spellings_are_rejected(self) -> None:
        for rel in (
            "../" + self.CONTENT_ROOT + "/GameFeatureData.uasset",
            self.CONTENT_ROOT + "/../CBEnabledCapability.uplugin",
            "C:\\escape\\GameFeatureData.uasset",
        ):
            with self.subTest(rel=rel):
                allowed, reason = _is_writable(rel, self.manifest)
                self.assertFalse(allowed)
                self.assertTrue(
                    "traversal" in reason or "absolute" in reason, reason)

    def test_in_project_junction_alias_to_aura_is_rejected_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aura = root / "Plugins/Aura/Content"
            aura.mkdir(parents=True)
            (aura / "Escape.uasset").write_bytes(b"aura")
            alias = root / self.CONTENT_ROOT
            alias.parent.mkdir(parents=True)
            try:
                _make_test_dir_link(alias, aura)
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("cannot create directory link on this host")
            result = scan_submission(root, self.manifest)
            self.assertFalse(result.ok)
            self.assertTrue(any(
                "link/junction/reparse" in v.reason for v in result.violations),
                result.render_report())
            self.assertFalse(any(
                rel.startswith(self.CONTENT_ROOT)
                for _path, rel in result.accepted))


class TestThirdPersonOfpaMirrorSandbox(unittest.TestCase):
    """The 2026-07-29 OFPA carve-out on the ThirdPerson manifest.

    UE 5.8 authors new levels One-File-Per-Actor by default, so an
    agent-delivered /Game/Tasks/<id>/ level arrives as the .umap PLUS actor
    packages under Content/__ExternalActors__/Tasks/<id>/... (and
    __ExternalObjects__/). Those two Tasks/-scoped mirror prefixes are
    asset_writable; the mirror of every OTHER map has NO matching prefix and
    must keep failing by allowlist-miss - that boundary is the whole point of
    the carve-out, so each side gets a test. The broad
    Content/__ExternalActors__/ deny was deliberately REMOVED; these tests are
    what alarms if someone re-adds it (task mirrors would start failing) or
    broadens asset_writable (protected mirrors would start passing).
    """

    TASK = "t9-basic-level-setup"  # any /Game/Tasks/<id>/ level

    def setUp(self) -> None:
        manifest_path = (
            REPO_ROOT / "UE-projects" / "ThirdPerson" / "AGENT_WRITABLE.json"
        )
        self.assertTrue(manifest_path.exists(), f"missing {manifest_path}")
        self.manifest = WritableManifest.load(manifest_path)

    def _scan_one(self, root: Path, rel: str, payload: bytes = b"\x00"):
        f = root / Path(rel)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(payload)
        return scan_submission(root, self.manifest)

    def test_task_map_and_its_ofpa_mirrors_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                f"Content/Tasks/{self.TASK}/L_AgentLevel.umap",
                f"Content/__ExternalActors__/Tasks/{self.TASK}/L_AgentLevel/"
                "1A/2B/3C4D5E6F7A8B9C0D1E2F3A4B.uasset",
                f"Content/__ExternalObjects__/Tasks/{self.TASK}/L_AgentLevel/"
                "0F/EE/DDCCBBAA9988776655443322.uasset",
            ):
                f = root / Path(rel)
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b"\x00")
            result = scan_submission(root, self.manifest)
            self.assertTrue(result.ok, msg=result.render_report())
            self.assertEqual(len(result.accepted), 3)

    def test_protected_map_mirror_still_fails_by_allowlist_miss(self) -> None:
        # An actor-level edit to the template's own map arrives exactly here;
        # it must stay rejected even with no explicit __ExternalActors__ deny.
        with tempfile.TemporaryDirectory() as tmp:
            result = self._scan_one(
                Path(tmp),
                "Content/__ExternalActors__/ThirdPerson/Lvl_ThirdPerson/"
                "1A/2B/3C4D5E6F7A8B9C0D1E2F3A4B.uasset",
            )
            self.assertFalse(result.ok)
            self.assertIn(
                "not under any writable prefix", result.violations[0].reason
            )

    def test_non_asset_file_in_task_mirror_is_rejected(self) -> None:
        # The mirror prefixes are asset_writable, so the .uasset/.umap
        # extension gate applies - a stray text file does not ride along.
        with tempfile.TemporaryDirectory() as tmp:
            result = self._scan_one(
                Path(tmp),
                f"Content/__ExternalActors__/Tasks/{self.TASK}/notes.txt",
                b"not an asset",
            )
            self.assertFalse(result.ok)
            self.assertIn(
                "not under any writable prefix", result.violations[0].reason
            )


class TestL2ResultParsers(unittest.TestCase):
    """Verify the L2 result parsers without needing UE installed."""

    def test_parse_index_json_per_test_state(self) -> None:
        # Per-test array is the authoritative source when present.
        text = json.dumps(
            {
                "succeeded": 1,
                "failed": 1,
                "tests": [
                    {"testDisplayName": "good", "state": "Success"},
                    {"testDisplayName": "bad", "state": "Fail"},
                    {"testDisplayName": "n/a", "state": "NotRun"},
                ],
            }
        )
        p = parse_index_json(text)
        self.assertEqual(p.tests_run, 3)
        self.assertEqual(p.tests_passed, 1)
        self.assertEqual(p.tests_failed, 1)
        self.assertEqual(p.tests_skipped, 1)

    def test_parse_index_json_falls_back_to_top_counts(self) -> None:
        # No per-test array — trust the summary counts.
        text = json.dumps(
            {"succeeded": 2, "succeededWithWarnings": 1, "failed": 1, "notRun": 0}
        )
        p = parse_index_json(text)
        self.assertEqual(p.tests_run, 4)
        self.assertEqual(p.tests_passed, 3)
        self.assertEqual(p.tests_failed, 1)

    def test_parse_automation_log_counts_completion_lines(self) -> None:
        # Stdout fallback — counts "Test Completed. Result={...}" lines.
        text = (
            "[time] LogAutomation: Display: Test Completed. Result={Passed} ...\n"
            "[time] LogAutomation: Display: Test Completed. Result={Failed} ...\n"
            "[time] LogAutomation: Display: Test Completed. Result={Skipped} ...\n"
        )
        p = parse_automation_log(text)
        self.assertEqual(p.tests_run, 3)
        self.assertEqual(p.tests_passed, 1)
        self.assertEqual(p.tests_failed, 1)
        self.assertEqual(p.tests_skipped, 1)


class TestMultiFixtureParsing(unittest.TestCase):
    """The ## Verifier fixtures section enumerates per-leg fixtures."""

    def _write_spec(self, tmp: Path, body: str) -> Path:
        path = tmp / "task.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_fixtures_block_parses_map_and_class(self) -> None:
        block = (
            "- L_TimerTask60 :: ATimerTask60HzFunctionalTest\n"
            "- L_TimerTask20 :: ATimerTask20HzFunctionalTest\n"
            "- L_TimerTaskTeardown :: ATimerTaskTeardownFunctionalTest\n"
        )
        fixtures = _parse_fixtures_block(block)
        self.assertEqual(
            fixtures,
            (
                Fixture("L_TimerTask60", "ATimerTask60HzFunctionalTest"),
                Fixture("L_TimerTask20", "ATimerTask20HzFunctionalTest"),
                Fixture("L_TimerTaskTeardown", "ATimerTaskTeardownFunctionalTest"),
            ),
        )

    def test_fixtures_block_skips_prose_and_malformed_lines(self) -> None:
        block = (
            "Some prose describing the leg semantics.\n"
            "\n"
            "- L_TimerTask60 :: ATimerTask60HzFunctionalTest\n"
            "- not a fixture line\n"
            "- L_TimerTask20 :: ATimerTask20HzFunctionalTest\n"
            "trailing text without a bullet\n"
        )
        fixtures = _parse_fixtures_block(block)
        self.assertEqual(
            fixtures,
            (
                Fixture("L_TimerTask60", "ATimerTask60HzFunctionalTest"),
                Fixture("L_TimerTask20", "ATimerTask20HzFunctionalTest"),
            ),
        )

    def test_fixtures_block_dedupes_repeated_entries(self) -> None:
        block = (
            "- L_TimerTask60 :: ATimerTask60HzFunctionalTest\n"
            "- L_TimerTask60 :: ATimerTask60HzFunctionalTest\n"
        )
        fixtures = _parse_fixtures_block(block)
        self.assertEqual(len(fixtures), 1)

    def test_fixtures_block_empty_when_section_missing(self) -> None:
        self.assertEqual(_parse_fixtures_block(""), ())

    def test_parse_task_spec_extracts_fixtures(self) -> None:
        body = (
            "# Sample\n\n"
            "## Task ID and metadata\n"
            "- task_id: gp-sample\n"
            "- substrate: template\n\n"
            "## Verifier layers used\n"
            "L1, L2\n\n"
            "## Verifier fixtures\n\n"
            "- L_SampleA :: ASampleAFunctionalTest\n"
            "- L_SampleB :: ASampleBFunctionalTest\n\n"
            "## Verifier specification\n"
            "Stuff.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_spec(Path(tmp), body)
            spec = parse_task_spec(path)
            self.assertEqual(spec.task_id, "gp-sample")
            self.assertEqual(
                spec.fixtures,
                (
                    Fixture("L_SampleA", "ASampleAFunctionalTest"),
                    Fixture("L_SampleB", "ASampleBFunctionalTest"),
                ),
            )

    def test_parse_task_spec_backward_compat_no_fixtures_section(self) -> None:
        # A legacy spec without a Verifier fixtures section yields no fixtures.
        body = (
            "# Sample\n\n"
            "## Task ID and metadata\n"
            "- task_id: gp-nofix\n"
            "- substrate: template\n\n"
            "## Verifier layers used\n"
            "L1, L2\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec = parse_task_spec(self._write_spec(Path(tmp), body))
            self.assertEqual(spec.fixtures, ())

    def test_t0_front_matter_fixtures_parse(self) -> None:
        # T0's spec-v2 front matter declares its single fixture compactly.
        spec = parse_task_spec(T0_TASK_PATH)
        self.assertEqual(
            spec.fixtures, (Fixture("L_SanityTask", "ASanityFunctionalTest"),)
        )


class TestFramerateLegsParsing(unittest.TestCase):
    """DD-9: ## Verifier framerate legs declares per-task fixed-timestep L2
    legs (was the hardcoded run_task._DT_LEGS_BY_TASK dict)."""

    def _write_spec(self, tmp: Path, body: str) -> Path:
        path = tmp / "task.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_bullets_parse_in_order(self) -> None:
        self.assertEqual(_parse_framerate_legs("- 60\n- 20\n"), (60, 20))

    def test_csv_parses(self) -> None:
        self.assertEqual(_parse_framerate_legs("60, 20"), (60, 20))

    def test_single_leg(self) -> None:
        self.assertEqual(_parse_framerate_legs("- 60\n"), (60,))

    def test_dedupes_preserving_order(self) -> None:
        self.assertEqual(_parse_framerate_legs("60, 60, 20, 20"), (60, 20))

    def test_empty_section(self) -> None:
        self.assertEqual(_parse_framerate_legs(""), ())

    def test_parse_task_spec_extracts_framerate_legs(self) -> None:
        body = (
            "# Sample\n\n"
            "## Task ID and metadata\n"
            "- task_id: gp-sample\n"
            "- substrate: template\n\n"
            "## Verifier layers used\n"
            "L1, L2\n\n"
            "## Verifier framerate legs\n\n"
            "- 60\n- 20\n\n"
            "## Verifier specification\n"
            "Stuff.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec = parse_task_spec(self._write_spec(Path(tmp), body))
            self.assertEqual(spec.fps_legs, (60, 20))

    def test_parse_task_spec_unified_block_fps(self) -> None:
        body = (
            "# Sample\n\n"
            "## Task ID and metadata\n"
            "- task_id: gp-sample\n"
            "- substrate: template\n\n"
            "## Verifier layers\n\n"
            "- L1\n- L2 (fps: 60, 20)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            spec = parse_task_spec(self._write_spec(Path(tmp), body))
            self.assertEqual(spec.fps_legs, (60, 20))

    def test_parse_task_spec_backward_compat_no_section(self) -> None:
        spec = parse_task_spec(T0_TASK_PATH)
        self.assertEqual(spec.fps_legs, ())
        # Single-class hint extraction still works.
        self.assertEqual(spec.test_class_hint, "ASanityFunctionalTest")
        self.assertEqual(spec.map_name, "L_SanityTask")


class TestMultiFixtureFilter(unittest.TestCase):
    """derive_test_filter emits a +-joined filter for multi-fixture tasks."""

    def _make_task(self, **overrides) -> TaskSpec:
        defaults = dict(
            task_id="gp-sample",
            substrate="template",
            layers=("L1", "L2"),
            raw_text="",
            source_path=Path("/tmp/sample.md"),
        )
        defaults.update(overrides)
        return TaskSpec(**defaults)

    def test_multi_fixture_filter_joins_with_plus(self) -> None:
        task = self._make_task(
            fixtures=(
                Fixture("L_TimerTask60", "ATimerTask60HzFunctionalTest"),
                Fixture("L_TimerTask20", "ATimerTask20HzFunctionalTest"),
            )
        )
        f = derive_test_filter(task)
        self.assertEqual(
            f,
            "Project.Functional Tests.Maps.L_TimerTask60.TimerTask60HzFunctionalTest"
            "+Project.Functional Tests.Maps.L_TimerTask20.TimerTask20HzFunctionalTest",
        )

    def test_multi_fixture_strips_class_prefix_per_fixture(self) -> None:
        task = self._make_task(
            fixtures=(
                Fixture("L_X", "AAlphaFunctionalTest"),
                Fixture("L_Y", "FBetaFunctionalTest"),
                Fixture("L_Z", "GammaFunctionalTest"),  # no prefix to strip
            )
        )
        f = derive_test_filter(task)
        self.assertEqual(
            f,
            "Project.Functional Tests.Maps.L_X.AlphaFunctionalTest"
            "+Project.Functional Tests.Maps.L_Y.BetaFunctionalTest"
            "+Project.Functional Tests.Maps.L_Z.GammaFunctionalTest",
        )

    def test_explicit_filter_wins_over_fixtures(self) -> None:
        task = self._make_task(
            fixtures=(Fixture("L_A", "AAFunctionalTest"),)
        )
        f = derive_test_filter(task, explicit="My.Override")
        self.assertEqual(f, "My.Override")

    def test_prefix_for_map_applies_per_fixture(self) -> None:
        # Mixed layout: L_A migrated into a task folder, L_B still at root —
        # only the foldered fixture gains the extra dot segment.
        task = self._make_task(
            fixtures=(
                Fixture("L_A", "AAlphaFunctionalTest"),
                Fixture("L_B", "ABetaFunctionalTest"),
            )
        )
        prefixes = {"L_A": "task-a", "L_B": ""}
        f = derive_test_filter(task, prefix_for_map=prefixes.__getitem__)
        self.assertEqual(
            f,
            "Project.Functional Tests.Maps.task-a.L_A.AlphaFunctionalTest"
            "+Project.Functional Tests.Maps.L_B.BetaFunctionalTest",
        )

    def test_prefix_for_map_default_none_multi_fixture_byte_identical(self) -> None:
        task = self._make_task(
            fixtures=(
                Fixture("L_TimerTask60", "ATimerTask60HzFunctionalTest"),
                Fixture("L_TimerTask20", "ATimerTask20HzFunctionalTest"),
            )
        )
        self.assertEqual(
            derive_test_filter(task, prefix_for_map=None),
            derive_test_filter(task),
        )

    def test_single_fixture_path_unchanged_when_no_fixtures(self) -> None:
        task = self._make_task(
            map_name="L_SanityTask",
            test_class_hint="ASanityFunctionalTest",
        )
        f = derive_test_filter(task)
        self.assertEqual(
            f, "Project.Functional Tests.Maps.L_SanityTask.SanityFunctionalTest"
        )


class TestHashManifestRetired(unittest.TestCase):
    """The verifier-hash manifest gate is GONE: no manifest file, no integrity
    function, no --regen flags, and exit code 3 is retired/reserved. Git
    provenance (grade-from-HEAD + pinning.py substrate_revision) replaced it."""

    def test_manifest_files_removed(self) -> None:
        self.assertFalse((_VERIFY / "verifier_hashes.json").exists(),
                         "verifier_hashes.json must be removed")
        self.assertFalse((_VERIFY / "hashes.py").exists(),
                         "hashes.py must be removed")

    def test_integrity_machinery_removed_from_run_task(self) -> None:
        for name in ("verify_tests_module_integrity", "IntegrityResult",
                     "DEFAULT_HASH_MANIFEST", "hash_tree"):
            self.assertFalse(hasattr(run_task, name),
                             f"run_task.{name} must be gone with the hash gate")

    def test_regen_flags_rejected_by_cli(self) -> None:
        base = ["--task", "t.md", "--ue-root", "/ue"]
        for flag in ("--regen-verifier-hashes", "--regen-substrate-hashes"):
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit):
                    build_parser().parse_args([*base, flag])

    def test_exit_3_reject_path_retired_in_main(self) -> None:
        # Pin the retirement in main(): the exit-3 REJECT return is gone and a
        # comment documents that the code stays reserved.
        src = (_VERIFY / "run_task.py").read_text(encoding="utf-8")
        self.assertNotIn("return 3", src)
        self.assertIn("Exit code 3", src)  # the reserved-code note


class TestL1DualTarget(unittest.TestCase):
    """run_l1 must invoke UBT for both <Module>Editor and <Module>."""

    def _make_fake_ue_root(self, tmp: Path, script_body: str) -> Path:
        """Write a fake UBT script at the platform-appropriate location."""
        ue_root = tmp / "UE"
        system = platform.system()
        if system == "Darwin":
            rel = ("Engine", "Build", "BatchFiles", "Mac", "Build.sh")
        elif system == "Linux":
            rel = ("Engine", "Build", "BatchFiles", "Linux", "Build.sh")
        else:
            rel = ("Engine", "Build", "BatchFiles", "Build.bat")
        script = ue_root.joinpath(*rel)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(script_body)
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return ue_root

    def test_runs_editor_and_game_targets_when_both_pass(self) -> None:
        if platform.system() == "Windows":
            self.skipTest("fake-UBT shell-script stub does not run on Windows here")
        # Fake UBT echoes its target arg so we can assert both were invoked.
        body = "#!/bin/sh\necho built target=$1\nexit 0\n"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            ue_root = self._make_fake_ue_root(tmp_p, body)
            project = tmp_p / "Fake.uproject"
            project.write_text("{}\n")
            log_path = tmp_p / "out" / "l1.log"
            result = run_l1(
                ue_root=ue_root,
                project_path=project,
                game_module="CraftBenchTemplate",
                log_path=log_path,
            )
            self.assertEqual(result.status, "pass", msg=result.notes)
            log = log_path.read_text(encoding="utf-8")
            self.assertIn("=== L1 target: CraftBenchTemplateEditor", log)
            self.assertIn("=== L1 target: CraftBenchTemplate (", log)
            self.assertIn("target=CraftBenchTemplateEditor", log)
            self.assertIn("target=CraftBenchTemplate", log)
            # Per-target summary lines surface in notes.
            self.assertTrue(
                any("CraftBenchTemplateEditor" in n for n in result.notes),
                msg=result.notes,
            )
            self.assertTrue(
                any("CraftBenchTemplate:" in n for n in result.notes),
                msg=result.notes,
            )

    def test_short_circuits_when_editor_target_fails(self) -> None:
        if platform.system() == "Windows":
            self.skipTest("fake-UBT shell-script stub does not run on Windows here")
        # Fake UBT: Editor target fails (exit 2), Game would pass — but must
        # not be invoked.
        body = (
            "#!/bin/sh\n"
            "echo built target=$1\n"
            'if [ "$1" = "CraftBenchTemplateEditor" ]; then exit 2; fi\n'
            "exit 0\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            ue_root = self._make_fake_ue_root(tmp_p, body)
            project = tmp_p / "Fake.uproject"
            project.write_text("{}\n")
            log_path = tmp_p / "out" / "l1.log"
            result = run_l1(
                ue_root=ue_root,
                project_path=project,
                game_module="CraftBenchTemplate",
                log_path=log_path,
            )
            self.assertEqual(result.status, "fail")
            self.assertEqual(result.exit_code, 2)
            log = log_path.read_text(encoding="utf-8")
            self.assertIn("CraftBenchTemplateEditor", log)
            self.assertNotIn(
                "target=CraftBenchTemplate\n",
                log,
                msg="Game target must NOT be invoked after Editor target fails",
            )


class TestReport(unittest.TestCase):
    def test_round_trip_via_json(self) -> None:
        original = Report(
            task_id="t0-sanity-log-on-beginplay",
            submission_sha="ab" * 32,
            layers={
                "L1": LayerReport(
                    status="pass",
                    log="out/l1_build.log",
                    exit_code=0,
                    duration_seconds=12.3,
                    warnings_in_agent_files=0,
                ),
                "L2": LayerReport(
                    status="pass",
                    log="out/l2_pie.log",
                    exit_code=0,
                    duration_seconds=33.4,
                    tests_run=1,
                    tests_passed=1,
                ),
            },
            overall="pass",
            duration_seconds=46.0,
            ue_version="5.7.0",
            host=HostInfo(os="darwin", arch="arm64"),
        )
        data = json.loads(original.to_json())
        round_tripped = report_from_dict(data)
        self.assertEqual(round_tripped.task_id, original.task_id)
        self.assertEqual(round_tripped.overall, original.overall)
        self.assertEqual(round_tripped.layers["L1"].status, "pass")
        self.assertEqual(round_tripped.layers["L2"].tests_passed, 1)
        self.assertEqual(round_tripped.host.os, "darwin")
        # And the serialized form is stable.
        self.assertEqual(round_tripped.to_json(), original.to_json())


class TestVisibleCaptureFlags(unittest.TestCase):
    """--visible / --capture: parse, imply a real RHI, and leave defaults alone."""

    _BASE = ["--task", "t.md", "--ue-root", "/ue"]

    def _parse(self, *extra: str):
        args = build_parser().parse_args([*self._BASE, *extra])
        _apply_visible_capture(args)
        return args

    def test_defaults_stay_headless(self) -> None:
        args = self._parse()
        self.assertFalse(args.visible)
        self.assertFalse(args.capture)
        self.assertTrue(args.use_nullrhi, "-nullrhi must remain the default")

    def test_visible_implies_real_rhi(self) -> None:
        args = self._parse("--visible")
        self.assertTrue(args.visible)
        self.assertFalse(args.use_nullrhi)

    def test_capture_implies_real_rhi(self) -> None:
        args = self._parse("--capture")
        self.assertTrue(args.capture)
        self.assertFalse(args.use_nullrhi)

    def test_both_flags_together(self) -> None:
        args = self._parse("--visible", "--capture")
        self.assertFalse(args.use_nullrhi)

    def test_explicit_no_nullrhi_unaffected(self) -> None:
        # Pre-existing spelling still works and is not toggled back on.
        args = self._parse("--no-nullrhi")
        self.assertFalse(args.use_nullrhi)

    def test_help_documents_headless_default_and_determinism(self) -> None:
        help_text = build_parser().format_help()
        self.assertIn("--visible", help_text)
        self.assertIn("--capture", help_text)
        self.assertIn("-deterministic", help_text)
        self.assertIn("-FPS", help_text)


class TestTaskRhiContract(unittest.TestCase):
    """A task may tighten the default runtime environment to real RHI."""

    def _args(self, *extra: str):
        return build_parser().parse_args(
            ["--task", "t.md", "--ue-root", "/ue", *extra]
        )

    def test_default_task_preserves_headless_default(self) -> None:
        args = self._args()
        _apply_task_rhi(args, TaskSpec("t", "ThirdPerson", ("L2",)))
        self.assertTrue(args.use_nullrhi)

    def test_real_task_overrides_nullrhi_default(self) -> None:
        args = self._args()
        _apply_task_rhi(
            args, TaskSpec("t", "ThirdPerson", ("L2",), rhi="real")
        )
        self.assertFalse(args.use_nullrhi)

    def test_real_task_cannot_be_weakened_by_explicit_nullrhi(self) -> None:
        args = self._args("--use-nullrhi")
        _apply_task_rhi(
            args, TaskSpec("t", "ThirdPerson", ("L2",), rhi="real")
        )
        self.assertFalse(args.use_nullrhi)

    def test_d3d11_task_uses_a_real_rhi(self) -> None:
        args = self._args()
        _apply_task_rhi(
            args, TaskSpec("t", "ThirdPerson", ("L2",), rhi="d3d11")
        )
        self.assertFalse(args.use_nullrhi)


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestCopySubstrateFromGit(unittest.TestCase):
    """copy_substrate materializes from git HEAD by default (F1/F3/F4 fix).

    The graded tree must be a function of COMMITTED files only, never of
    uncommitted/untracked working-tree state.
    """

    def _init_repo(self, root: Path) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
        # Some environments default to a protected branch name; not relevant here.
        self._env = env

    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, env=self._env)

    def _scaffold_substrate(self, root: Path) -> Path:
        """Create UE-projects/Sub/ with a tracked file + an untracked file."""
        sub = root / "UE-projects" / "Sub"
        (sub / "Source").mkdir(parents=True)
        (sub / "Source" / "tracked.cpp").write_text("// committed\n")
        return sub

    def test_git_clone_excludes_untracked_includes_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            sub = self._scaffold_substrate(root)
            # Commit only the tracked file.
            self._git(root, "add", "UE-projects/Sub/Source/tracked.cpp")
            self._git(root, "commit", "-q", "-m", "init substrate")
            # Now drop an UNTRACKED file into the live tree (WIP fixture residue).
            (sub / "Source" / "untracked_wip.cpp").write_text("// not committed\n")
            # And modify the tracked file on disk WITHOUT committing.
            (sub / "Source" / "tracked.cpp").write_text("// LIVE EDIT, not committed\n")

            dest = root / "workdir" / "Sub"
            source = copy_substrate(sub, dest)  # default = from git HEAD
            self.assertEqual(source, "git-head")

            tracked = dest / "Source" / "tracked.cpp"
            untracked = dest / "Source" / "untracked_wip.cpp"
            self.assertTrue(tracked.exists(), "committed file must be present")
            self.assertFalse(
                untracked.exists(),
                "untracked WIP file must be EXCLUDED from the graded tree",
            )
            # Committed CONTENT, not the live-disk edit.
            self.assertEqual(tracked.read_text(), "// committed\n")

    def test_git_clone_includes_tracked_gamefeature_and_strips_host_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            sub = self._scaffold_substrate(root)
            task_plugin = (sub / "Plugins" / "GameFeatures" / "Tasks"
                           / "t2-enabled" / "CBEnabled")
            (task_plugin / "Content").mkdir(parents=True)
            (task_plugin / "CBEnabled.uplugin").write_text("{}")
            (task_plugin / "Content" / "GameFeatureData.uasset").write_bytes(b"gfd")
            for host_name in ("Aura", "Ramen"):
                host = sub / "Plugins" / host_name
                host.mkdir(parents=True)
                (host / "HostOnly.txt").write_text("must not grade")
            self._git(root, "add", "UE-projects/Sub")
            self._git(root, "commit", "-q", "-m", "tracked feature substrate")

            dest = root / "workdir" / "Sub"
            copy_substrate(sub, dest)
            self.assertTrue(
                (dest / "Plugins/GameFeatures/Tasks/t2-enabled/CBEnabled/"
                 "CBEnabled.uplugin").exists())
            self.assertTrue(
                (dest / "Plugins/GameFeatures/Tasks/t2-enabled/CBEnabled/Content/"
                 "GameFeatureData.uasset").exists())
            self.assertFalse((dest / "Plugins/Aura").exists())
            self.assertFalse((dest / "Plugins/Ramen").exists())

    def test_not_a_git_repo_falls_back_to_live_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No `git init` here → not a git repo → fallback to live copy.
            sub = root / "Sub"
            (sub / "Source").mkdir(parents=True)
            (sub / "Source" / "tracked.cpp").write_text("// live\n")
            (sub / "Source" / "untracked_wip.cpp").write_text("// live wip\n")

            dest = root / "workdir" / "Sub"
            source = copy_substrate(sub, dest)
            self.assertEqual(source, "live", "fallback must report live provenance")

            # Live copy includes EVERYTHING on disk (the fallback's whole point).
            self.assertTrue((dest / "Source" / "tracked.cpp").exists())
            self.assertTrue((dest / "Source" / "untracked_wip.cpp").exists())

    def test_untracked_substrate_path_falls_back_to_live_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            # A repo exists, but the substrate dir is entirely UNTRACKED in HEAD.
            # Need at least one commit so HEAD resolves.
            (root / "README").write_text("repo\n")
            self._git(root, "add", "README")
            self._git(root, "commit", "-q", "-m", "init")
            sub = self._scaffold_substrate(root)  # never added/committed
            (sub / "Source" / "untracked_wip.cpp").write_text("// wip\n")

            dest = root / "workdir" / "Sub"
            copy_substrate(sub, dest)

            # Untracked-path → live fallback → everything present.
            self.assertTrue((dest / "Source" / "tracked.cpp").exists())
            self.assertTrue((dest / "Source" / "untracked_wip.cpp").exists())

    def test_substrate_from_live_escape_hatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            sub = self._scaffold_substrate(root)
            self._git(root, "add", "UE-projects/Sub/Source/tracked.cpp")
            self._git(root, "commit", "-q", "-m", "init substrate")
            (sub / "Source" / "untracked_wip.cpp").write_text("// wip\n")

            dest = root / "workdir" / "Sub"
            # Force live copy despite being in a git repo with a tracked substrate.
            source = copy_substrate(sub, dest, from_live=True)
            self.assertEqual(source, "live", "forced live copy must report live")

            self.assertTrue((dest / "Source" / "tracked.cpp").exists())
            self.assertTrue(
                (dest / "Source" / "untracked_wip.cpp").exists(),
                "--substrate-from-live must include untracked files",
            )

    def test_live_copy_adds_only_scoped_gamefeature_tasks(self) -> None:
        # The base copy excludes Plugins wholesale, then selectively copies the
        # task-owned root with generated-dir and link guards.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            sub = self._scaffold_substrate(root)
            external = root / "external-rig"
            external.mkdir()
            (external / "deep.txt").write_text("never copied\n")
            plugins = sub / "Plugins"
            plugins.mkdir()
            for host_name in ("Aura", "Ramen", "OtherPlugin"):
                host = plugins / host_name
                host.mkdir()
                (host / "HostOnly.txt").write_text("never copied\n")
            active = plugins / "GameFeatures" / "Tasks" / "t2-enabled" / "CBEnabled"
            (active / "Content").mkdir(parents=True)
            (active / "CBEnabled.uplugin").write_text("{}")
            (active / "Content" / "GameFeatureData.uasset").write_bytes(b"gfd")
            generated = []
            for name in ("bInArIeS", "iNtErMeDiAtE", "sAvEd",
                         "DerivedDATACache"):
                path = active / name
                path.mkdir()
                (path / "stale.bin").write_bytes(b"generated")
                generated.append(path)
            link = active / "LinkedLocalState"
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(link), str(external)],
                        check=True, capture_output=True)
                else:
                    link.symlink_to(external, target_is_directory=True)
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("cannot create junction/symlink on this host")

            dest = root / "workdir" / "Sub"
            copy_substrate(sub, dest, from_live=True)

            self.assertTrue((dest / "Source" / "tracked.cpp").exists())
            copied = dest / "Plugins/GameFeatures/Tasks/t2-enabled/CBEnabled"
            self.assertTrue((copied / "CBEnabled.uplugin").exists())
            self.assertTrue((copied / "Content/GameFeatureData.uasset").exists())
            for path in generated:
                self.assertFalse((copied / path.name).exists())
            self.assertFalse((copied / "LinkedLocalState").exists())
            for excluded in ("Aura", "Ramen", "OtherPlugin"):
                self.assertFalse((dest / "Plugins" / excluded).exists())

    def test_scoped_plugin_staging_records_foreign_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for task_id in ("t2-enabled", "t2-foreign"):
                d = project / "Plugins/GameFeatures/Tasks" / task_id
                d.mkdir(parents=True)
                (d / "Task.uplugin").write_text("{}")
            initial = run_task.StagingResult(
                mode="task-scoped", excluded=("Content/Tasks/t2-foreign",),
                notes=("content staged",))
            result = run_task._stage_scoped_task_plugins(
                project, "bp/t2-enabled", initial)
            self.assertTrue((project / "Plugins/GameFeatures/Tasks/t2-enabled").exists())
            self.assertFalse((project / "Plugins/GameFeatures/Tasks/t2-foreign").exists())
            self.assertIn("Plugins/GameFeatures/Tasks/t2-foreign", result.excluded)
            self.assertTrue(any("excluded 1 task plugin" in n for n in result.notes))

    def test_saved_dir_excluded_in_git_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            sub = self._scaffold_substrate(root)
            # Saved/ is gitignored by convention; git archive omits it.
            (root / ".gitignore").write_text("UE-projects/Sub/Saved/\n")
            saved = sub / "Saved"
            saved.mkdir()
            (saved / "stale.bin").write_text("stale\n")
            self._git(root, "add", "UE-projects/Sub/Source/tracked.cpp", ".gitignore")
            self._git(root, "commit", "-q", "-m", "init")

            dest = root / "workdir" / "Sub"
            copy_substrate(sub, dest)
            self.assertFalse(
                (dest / "Saved").exists(), "Saved/ must stay out of the graded tree"
            )

    def test_resolve_repo_root_outside_repo_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # A bare temp dir with no git repo anywhere above it (TMPDIR is not
            # under the craftbench repo) resolves to None.
            self.assertIsNone(_resolve_repo_root_for(Path(tmp)))


class TestConfigOverlayStaging(unittest.TestCase):
    """B7 — the per-task UE config overlay is staged into the workdir Config/.

    Exercises the ``_stage_config_overlay`` helper main() calls right after
    substrate materialization, on a throwaway temp tree (no UE, no git).
    """

    def _mk_task(self, root: Path, *, with_overlay: bool) -> Path:
        spec = root / "tasks" / "flagship" / "cfg-task" / "task.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Cfg\n\n## Verifier layers used\nL1, L2\n",
                        encoding="utf-8")
        if with_overlay:
            uc = spec.parent / "ue-config"
            uc.mkdir()
            (uc / "DefaultGameplayTags.ini").write_text(
                "[/Script/GameplayTags.GameplayTagsSettings]\n"
                '+GameplayTagList=(Tag="Task.Cfg")\n',
                encoding="utf-8")
            (uc / "DefaultEngine.ini").write_text(
                "[/Script/Engine.Engine]\nbSmoothFrameRate=False\n",
                encoding="utf-8")
        return spec

    def test_fragments_appended_into_workdir_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._mk_task(root, with_overlay=True)
            workdir_sub = root / "wd" / "CraftBenchTemplate"
            (workdir_sub / "Config").mkdir(parents=True)
            engine_ini = workdir_sub / "Config" / "DefaultEngine.ini"
            engine_ini.write_text("[/Script/Engine.Engine]\nExisting=1\n",
                                  encoding="utf-8")

            applied = _stage_config_overlay(spec, workdir_sub, "cfg-task")

            self.assertEqual(applied,
                             ["DefaultEngine.ini", "DefaultGameplayTags.ini"])
            engine_text = engine_ini.read_text(encoding="utf-8")
            self.assertTrue(engine_text.startswith(
                "[/Script/Engine.Engine]\nExisting=1\n"))
            self.assertIn("; CraftBench per-task overlay: cfg-task",
                          engine_text)
            self.assertIn("bSmoothFrameRate=False", engine_text)
            # The absent target is created, marker-headed.
            tags_ini = workdir_sub / "Config" / "DefaultGameplayTags.ini"
            self.assertIn('+GameplayTagList=(Tag="Task.Cfg")',
                          tags_ini.read_text(encoding="utf-8"))

    def test_task_without_ue_config_is_a_noop(self) -> None:
        # Every current task: the workdir Config/ must stay byte-identical.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._mk_task(root, with_overlay=False)
            workdir_sub = root / "wd" / "CraftBenchTemplate"
            (workdir_sub / "Config").mkdir(parents=True)
            engine_ini = workdir_sub / "Config" / "DefaultEngine.ini"
            engine_ini.write_bytes(b"[/Script/Engine.Engine]\nExisting=1\n")

            applied = _stage_config_overlay(spec, workdir_sub, "cfg-task")

            self.assertEqual(applied, [])
            self.assertEqual(engine_ini.read_bytes(),
                             b"[/Script/Engine.Engine]\nExisting=1\n")

    def test_main_stages_overlay_after_materialization(self) -> None:
        """Pins the call SITE in main(): the overlay is applied after BOTH
        materialization paths (warm slot reset, cold git clone) and before the
        submission sandbox scan — so a refactor can't silently move or
        drop it (same pinning style as run-agent's TestBackendWiring)."""
        src = (_VERIFY / "run_task.py").read_text(encoding="utf-8")
        i_warm_reset = src.index("warm_reset = warm_slot.reset_to_pristine()")
        i_cold_clone = src.index("from_live=args.substrate_from_live,")
        # Searched FROM the clone site so this finds the call in main(), not the
        # `def` further up — and so the pin survives a reindent (wrapping the
        # call in a `with` block used to break it, which is noise, not signal).
        i_overlay = src.index("_stage_config_overlay(", i_cold_clone)
        i_sandbox = src.index("sandbox_result = scan_submission(")
        self.assertLess(i_warm_reset, i_overlay)
        self.assertLess(i_cold_clone, i_overlay)
        self.assertLess(i_overlay, i_sandbox)


class TestGovernResourcesDefault(unittest.TestCase):
    """The Win32 Job-Object governor is DEFAULT-ON for the cold verify path.

    Two contracts, both UE-free:
      * the ``--govern-resources`` flag defaults to True and ``--no-govern-resources``
        opts out (the parser surface), and
      * ``job_governor._enabled()`` reads CRAFTBENCH_GOVERN_RESOURCES as a tri-state
        so ``0``/``false`` opts OUT via the env even when the flag default is ON
        (the gate the layer spawns actually consult).
    """

    def setUp(self) -> None:
        import job_governor

        from run_task import build_parser  # noqa: F811

        self.build_parser = build_parser
        self.job_governor = job_governor
        # Snapshot the env var so we restore it byte-for-byte (set or unset).
        self._prev_env = os.environ.get("CRAFTBENCH_GOVERN_RESOURCES")

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("CRAFTBENCH_GOVERN_RESOURCES", None)
        else:
            os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = self._prev_env

    def _base_args(self, *extra: str) -> list[str]:
        # --task and --ue-root are required by the parser; values are never
        # touched (we only read the parsed namespace), so dummies are fine.
        return ["--task", "x.md", "--ue-root", "y", "--submission", "z", *extra]

    def test_flag_defaults_to_on(self) -> None:
        args = self.build_parser().parse_args(self._base_args())
        self.assertTrue(
            args.govern_resources,
            "the governor must be DEFAULT-ON (no flag => govern_resources True)",
        )

    def test_no_flag_opts_out(self) -> None:
        args = self.build_parser().parse_args(
            self._base_args("--no-govern-resources")
        )
        self.assertFalse(
            args.govern_resources,
            "--no-govern-resources must opt out (govern_resources False)",
        )

    def test_explicit_flag_still_on(self) -> None:
        # The opt-in spelling stays valid (e.g. test_hardening_discrimination.py
        # and any operator muscle memory both keep working).
        args = self.build_parser().parse_args(
            self._base_args("--govern-resources")
        )
        self.assertTrue(args.govern_resources)

    @unittest.skipUnless(os.name == "nt", "governor only actuates on Windows")
    def test_env_truthy_enables_on_windows(self) -> None:
        for val in ("1", "true", "yes", "on", "TRUE", " On "):
            with self.subTest(val=val):
                os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = val
                self.assertTrue(self.job_governor._enabled())

    @unittest.skipUnless(os.name == "nt", "governor only actuates on Windows")
    def test_env_falsey_opts_out_on_windows(self) -> None:
        # The load-bearing opt-out-via-env case: "0"/"false" must DISABLE even
        # though the run_task flag default is ON. (Old bool(str) treated "0" as
        # truthy — that bug is what this guards against.)
        for val in ("0", "false", "no", "off", "FALSE", " 0 "):
            with self.subTest(val=val):
                os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = val
                self.assertFalse(self.job_governor._enabled())

    def test_env_unset_does_not_actuate(self) -> None:
        # Absent/blank env is "unspecified" => disabled inside job_governor (it is
        # run_task.py that supplies the default-ON by writing "1"/"0"). Also the
        # non-Windows guard makes this False everywhere off Windows.
        os.environ.pop("CRAFTBENCH_GOVERN_RESOURCES", None)
        self.assertFalse(self.job_governor._enabled())
        os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = "   "
        self.assertFalse(self.job_governor._enabled())


class TestMalformedSpecExitCode(unittest.TestCase):
    """A malformed v2 front-matter spec is a CONFIG error: main() must return
    exit code 2 (never 1 — the rig's VERDICT map reads 1 as a graded agent
    FAIL, so an uncaught ValueError would mis-record spec bugs as failures)."""

    def setUp(self) -> None:
        # main() writes CRAFTBENCH_GOVERN_RESOURCES when unset — keep the
        # process env clean for sibling tests.
        self._gov = os.environ.pop("CRAFTBENCH_GOVERN_RESOURCES", None)

    def tearDown(self) -> None:
        if self._gov is None:
            os.environ.pop("CRAFTBENCH_GOVERN_RESOURCES", None)
        else:
            os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = self._gov

    def test_malformed_front_matter_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            spec_path = Path(d) / "task.md"
            # Duplicate key => spec.parse_front_matter raises ValueError.
            spec_path.write_text(
                "---\nid: bad-task\nid: bad-task\nlayers: [L1]\n---\n\n"
                "## Prompt given to the agent\n\n> x\n",
                encoding="utf-8",
            )
            sub = Path(d) / "sub"
            sub.mkdir()
            import io
            from contextlib import redirect_stderr

            err = io.StringIO()
            with redirect_stderr(err):
                rc = run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(sub),
                    "--ue-root", str(Path(d) / "no-ue"),
                ])
            self.assertEqual(rc, 2)
            self.assertIn("task spec malformed", err.getvalue())

    def test_unclosed_front_matter_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            spec_path = Path(d) / "task.md"
            spec_path.write_text(
                "---\nid: bad-task\nlayers: [L1]\n\n## Prompt given to the agent\n",
                encoding="utf-8",
            )
            sub = Path(d) / "sub"
            sub.mkdir()
            import io
            from contextlib import redirect_stderr

            err = io.StringIO()
            with redirect_stderr(err):
                rc = run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(sub),
                    "--ue-root", str(Path(d) / "no-ue"),
                ])
            self.assertEqual(rc, 2)
            self.assertIn("task spec malformed", err.getvalue())


_8DOT3 = re.compile(r"~[0-9]")


def _has_8dot3(path) -> bool:
    """True when any segment of ``path`` is a Windows 8.3 short name."""
    return any(_8DOT3.search(seg) for seg in re.split(r"[\\/]+", str(path)))


def _short_path_name(p: Path) -> str:
    """The Windows 8.3 alias of an EXISTING path, or "" when unavailable.

    ``GetShortPathNameW`` returns the long path unchanged when 8.3 generation is
    disabled on the volume (``fsutil 8dot3name set 1``), which is why every
    caller re-checks for a ``~<digit>`` before trusting the result.
    """
    import ctypes

    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 1024)
    return buf.value if n else ""


class TestTempWorkdirIs83Canonical(unittest.TestCase):
    """FAILURE-LOG 2026-07-25 — ``cb batch-eval --references all`` scored 0/15.

    The default (no ``--keep``) cold verify workdir was a RAW ``mkdtemp`` under
    ``%TEMP%``, and on the testbed host ``%TEMP%`` is the Windows 8.3 SHORT form
    ``C:\\Users\\SHORT~1\\AppData\\Local\\Temp``. That short name propagated
    into ``out/l2_report`` — the dir handed to the editor as
    ``-ReportExportPath`` — the L2 leg could not retrieve its automation result,
    retried ("fell back to full RHI on first retry"), and returned
    ``exit_code 3`` -> status ``skipped``, which scores FAIL. Four controlled
    runs of the SAME two flagship references pinned it: the 35-char SHORT path
    FAILED while a 39-char LONG path PASSED, so path length / MAX_PATH is
    excluded and the 8.3 component is the only differing input.

    The fix is ``run_task.new_temp_workdir()`` — mkdtemp + ``.resolve()``, the
    same canonicalization the ``--workdir`` branch has always done.
    """

    def test_temp_workdir_equals_its_resolved_form(self) -> None:
        """The workdir the runner mints carries no 8.3 component, whatever
        %TEMP% says. On a host whose %TEMP% is already long this is a tautology;
        on the 2026-07-25 testbed host it is the whole incident."""
        wd = run_task.new_temp_workdir()
        try:
            self.assertTrue(wd.is_dir())
            self.assertEqual(
                wd, wd.resolve(),
                f"temp workdir {wd} is not canonical; UE would round-trip it to "
                f"{wd.resolve()} and the L2 report lookup would miss",
            )
            self.assertFalse(
                _has_8dot3(wd),
                f"temp workdir {wd} still carries an 8.3 short component - this is "
                "the exact 0/15 batch-eval signature from 2026-07-25",
            )
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "8.3 short names are a Windows-only concept")
    def test_temp_workdir_expands_an_8dot3_temp_root(self) -> None:
        """Host-independent reproduction: point tempfile at a REAL 8.3 alias of a
        real directory and prove the runner still hands back the long form.

        This does not depend on the maintainer's profile name being >8 chars —
        it manufactures the ``~1`` alias with ``GetShortPathNameW`` — so it keeps
        guarding the fix on any Windows box with 8.3 generation enabled.
        """
        long_root = Path(tempfile.mkdtemp(prefix="craftbench-8dot3-probe-")).resolve()
        short_root = _short_path_name(long_root)
        if not short_root or not _has_8dot3(short_root):
            shutil.rmtree(long_root, ignore_errors=True)
            self.skipTest("8.3 short-name generation is disabled on this volume")

        saved_tempdir = tempfile.tempdir
        try:
            # tempfile.tempdir is the documented override gettempdir()/mkdtemp()
            # both honor — the in-process stand-in for a short-form %TEMP%.
            tempfile.tempdir = short_root

            # Precondition: without the fix, mkdtemp hands back the SHORT form.
            raw = tempfile.mkdtemp(prefix="craftbench-raw-")
            try:
                self.assertTrue(
                    _has_8dot3(raw),
                    "test is vacuous: raw mkdtemp did not inherit the 8.3 root",
                )
            finally:
                shutil.rmtree(raw, ignore_errors=True)

            wd = run_task.new_temp_workdir()
            try:
                self.assertTrue(wd.is_dir())
                self.assertFalse(
                    _has_8dot3(wd),
                    f"new_temp_workdir() returned {wd}, which still carries the 8.3 "
                    "component that took batch-eval to 0/15 on 2026-07-25",
                )
                self.assertEqual(wd, wd.resolve())
                # ...and it is genuinely the SAME directory, just spelled long.
                self.assertEqual(wd.parent, long_root)
            finally:
                shutil.rmtree(wd, ignore_errors=True)
        finally:
            tempfile.tempdir = saved_tempdir
            shutil.rmtree(long_root, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "--tighten-workdir-acl is Windows-only")
    def test_acl_guard_still_accepts_a_canonicalized_workdir(self) -> None:
        """Lock-in for the safety assertion the fix had to not break.

        ``_maybe_tighten_workdir_acl`` refuses to touch anything outside the
        system temp root. Now that the workdir arrives CANONICAL while raw
        ``gettempdir()`` may be the 8.3 SHORT form, the guard only agrees because
        it resolves BOTH sides. Drop either ``.resolve()`` there and this test
        catches the resulting silent false-reject.
        """
        long_root = Path(tempfile.mkdtemp(prefix="craftbench-aclguard-")).resolve()
        short_root = _short_path_name(long_root)
        if not short_root or not _has_8dot3(short_root):
            shutil.rmtree(long_root, ignore_errors=True)
            self.skipTest("8.3 short-name generation is disabled on this volume")

        workdir = long_root / "craftbench-workdir"
        workdir.mkdir()
        err = io.StringIO()
        try:
            proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            with mock.patch.object(run_task.tempfile, "gettempdir",
                                   return_value=short_root), \
                 mock.patch.dict(os.environ, {"USERNAME": "tester"}), \
                 mock.patch.object(run_task.subprocess, "run",
                                   return_value=proc) as run_mock, \
                 redirect_stderr(err):
                run_task._maybe_tighten_workdir_acl(workdir)

            self.assertEqual(
                run_mock.call_count, 1,
                f"the temp-root guard rejected a legitimate workdir; stderr={err.getvalue()!r}",
            )
            self.assertNotIn("not under the system temp root", err.getvalue())
            self.assertEqual(run_mock.call_args.args[0][1], str(workdir))
        finally:
            shutil.rmtree(long_root, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
