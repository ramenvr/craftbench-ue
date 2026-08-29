"""Tests for the L2I asset-integrity preamble (2026-07-29).

The preamble's whole reason to exist is the redirector hole: ``load_asset``
FOLLOWS redirectors, so a submitted UObjectRedirector at a legal path would
make every grader silently grade the redirect TARGET instead of the
submission. These tests pin, offline (no UE):

  * the package-path derivation table (what participates in the scan);
  * the bootstrap generation (manifest content + task-script chaining with
    ``__name__ == "__main__"`` semantics);
  * the taxonomy routing: agent-caused violations grade as failed checks,
    verifier-side probe failures route to layer status "error", and a
    missing integrity block when one was expected is "error" too.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.l2_introspect import (  # noqa: E402
    INTEGRITY_JSON_END,
    INTEGRITY_JSON_START,
    INTROSPECT_JSON_END,
    INTROSPECT_JSON_START,
    content_package_path,
    parse_integrity_verdict,
    run_l2_introspect,
    write_integrity_bootstrap,
)
from spec import parse_task_file  # noqa: E402


class TestContentPackagePath(unittest.TestCase):
    def test_plain_asset_maps_to_game_path(self) -> None:
        self.assertEqual(
            content_package_path("Content/Tasks/t2-x/BP_EvalChar.uasset"),
            "/Game/Tasks/t2-x/BP_EvalChar",
        )

    def test_umap_participates(self) -> None:
        self.assertEqual(
            content_package_path("Content/Tasks/t9-y/L_AgentLevel.umap"),
            "/Game/Tasks/t9-y/L_AgentLevel",
        )

    def test_ofpa_mirrors_are_excluded(self) -> None:
        # Mirror packages are not registry assets; probing them would
        # false-positive on valid submissions.
        self.assertIsNone(content_package_path(
            "Content/__ExternalActors__/Tasks/t9-y/L_A/1A/2B/XYZ.uasset"
        ))
        self.assertIsNone(content_package_path(
            "Content/__ExternalObjects__/Tasks/t9-y/L_A/0F/EE/ABC.uasset"
        ))

    def test_non_content_and_non_asset_are_excluded(self) -> None:
        self.assertIsNone(content_package_path("Source/ThirdPerson/Foo.cpp"))
        self.assertIsNone(content_package_path("Config/DefaultEngine.ini"))
        self.assertIsNone(content_package_path("Content/Tasks/t2-x/notes.txt"))

    def test_backslash_rel_paths_normalize(self) -> None:
        self.assertEqual(
            content_package_path("Content\\Tasks\\t2-x\\SKM_EvalChar.uasset"),
            "/Game/Tasks/t2-x/SKM_EvalChar",
        )

    def test_gamefeature_submitted_packages_map_to_plugin_mount(self) -> None:
        base = (
            "Plugins/GameFeatures/Tasks/"
            "t2-the-capability-exists-only-while-enabled/CBEnabledCapability/Content/")
        self.assertEqual(
            content_package_path(base + "GameFeatureData.uasset"),
            "/CBEnabledCapability/GameFeatureData")
        self.assertEqual(
            content_package_path(base + "BP_EnabledPulseComponent.uasset"),
            "/CBEnabledCapability/BP_EnabledPulseComponent")
        self.assertEqual(
            content_package_path(base + "Nested/DA_Config.umap"),
            "/CBEnabledCapability/Nested/DA_Config")

    def test_malformed_or_ambiguous_plugin_paths_are_excluded(self) -> None:
        for rel in (
            "Plugins/Bad-Plugin/Content/A.uasset",
            "Plugins/Foo/Content/Nested/Content/A.uasset",
            "Plugins/Content/A.uasset",
            "Plugins/Foo/Content/notes.txt",
            "Plugins/Foo/Content/.uasset",
            "Plugins/Foo/Content/../Aura/A.uasset",
        ):
            with self.subTest(rel=rel):
                self.assertIsNone(content_package_path(rel))

    def test_plugin_external_actor_object_packages_are_excluded(self) -> None:
        for mirror in ("__ExternalActors__", "__ExternalObjects__"):
            rel = f"Plugins/Foo/Content/{mirror}/Map/AA/BB/Actor.uasset"
            with self.subTest(rel=rel):
                self.assertIsNone(content_package_path(rel))


class TestParseIntegrityVerdict(unittest.TestCase):
    def _block(self, payload: dict) -> str:
        return (
            f"noise\n{INTEGRITY_JSON_START}\n{json.dumps(payload)}\n"
            f"{INTEGRITY_JSON_END}\nmore noise\n"
        )

    def test_no_block_returns_none(self) -> None:
        self.assertIsNone(parse_integrity_verdict("no markers here"))

    def test_empty_violations_parse(self) -> None:
        got = parse_integrity_verdict(self._block({"violations": []}))
        self.assertEqual(got, [])

    def test_violations_parse_and_classify(self) -> None:
        got = parse_integrity_verdict(self._block({"violations": [
            {"path": "a.uasset", "reason": "REDIRECTOR_SUBMITTED /Game/x"},
            {"path": "b.uasset", "reason": "INTEGRITY_PROBE_ERROR boom"},
        ]}))
        self.assertEqual(len(got), 2)
        self.assertFalse(got[0].harness_side)   # agent-caused → graded
        self.assertTrue(got[1].harness_side)    # verifier-side → error path

    def test_ue_log_prefix_noise_is_tolerated(self) -> None:
        body = '[2026.07.29-1][2]LogPython: {"violations": []}'
        text = f"{INTEGRITY_JSON_START}\n{body}\n{INTEGRITY_JSON_END}"
        self.assertEqual(parse_integrity_verdict(text), [])

    def test_last_block_wins(self) -> None:
        text = (
            self._block({"violations": [{"path": "x", "reason": "REDIRECTOR_SUBMITTED"}]})
            + self._block({"violations": []})
        )
        self.assertEqual(parse_integrity_verdict(text), [])


class TestBootstrapGeneration(unittest.TestCase):
    def test_manifest_filters_and_bootstrap_chains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            task_script = out / "grader.py"
            task_script.write_text("print('grader ran')\n", encoding="utf-8")
            bootstrap = write_integrity_bootstrap(
                out_dir=out,
                task_script=task_script,
                asset_rel_paths=[
                    "Content/Tasks/t2-x/BP_EvalChar.uasset",
                    "Content/__ExternalActors__/Tasks/t9/L_A/1/x.uasset",
                    "Source/ThirdPerson/Foo.cpp",
                ],
                stem="grader",
            )
            manifest = json.loads(
                (out / "asset_integrity_grader.json").read_text(encoding="utf-8")
            )
            # Only the plain Content asset participates.
            self.assertEqual(
                [e["package"] for e in manifest],
                ["/Game/Tasks/t2-x/BP_EvalChar"],
            )
            src = bootstrap.read_text(encoding="utf-8")
            self.assertIn(INTEGRITY_JSON_START, src)
            self.assertIn('"__main__"', src)
            self.assertIn("wait_for_completion", src)

    def test_bootstrap_executes_under_fake_unreal(self) -> None:
        """Run the generated bootstrap under CPython with a fake ``unreal``.

        Proves the chaining semantics end to end: the integrity block prints
        first, then the task script runs with ``__name__ == "__main__"``.
        """
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            task_script = out / "grader.py"
            task_script.write_text(
                "if __name__ == '__main__':\n    print('GRADER-MAIN-RAN')\n",
                encoding="utf-8",
            )
            bootstrap = write_integrity_bootstrap(
                out_dir=out, task_script=task_script,
                asset_rel_paths=["Content/Tasks/t/BP_A.uasset"], stem="grader",
            )

            class _Data:
                def is_valid(self):
                    return True

                @property
                def asset_class_path(self):
                    class _P:
                        asset_name = "Blueprint"
                    return _P()

            class _EAL:
                @staticmethod
                def find_asset_data(pkg):
                    return _Data()

            class _Reg:
                def wait_for_completion(self):
                    return None

            class _RegHelpers:
                @staticmethod
                def get_asset_registry():
                    return _Reg()

            fake = type(sys)("unreal")
            fake.EditorAssetLibrary = _EAL
            fake.AssetRegistryHelpers = _RegHelpers
            fake.log = lambda *_a, **_k: None

            import contextlib
            import io
            buf = io.StringIO()
            old = sys.modules.get("unreal")
            sys.modules["unreal"] = fake
            try:
                with contextlib.redirect_stdout(buf):
                    src = bootstrap.read_text(encoding="utf-8")
                    exec(compile(src, str(bootstrap), "exec"),
                         {"__name__": "__main__", "__file__": str(bootstrap)})
            finally:
                if old is not None:
                    sys.modules["unreal"] = old
                else:
                    sys.modules.pop("unreal", None)
            text = buf.getvalue()
            self.assertIn(INTEGRITY_JSON_START, text)
            self.assertIn('"violations": []', text)
            self.assertIn("GRADER-MAIN-RAN", text)
            self.assertLess(
                text.index(INTEGRITY_JSON_END), text.index("GRADER-MAIN-RAN")
            )


class TestRunLayerIntegrityRouting(unittest.TestCase):
    """Drive run_l2_introspect with a fake editor writing synthetic logs."""

    def _run(self, log_body: str, submitted):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            script = out / "task_grader.py"
            script.write_text("# grader\n", encoding="utf-8")
            log_path = out / "l2i.log"

            def fake_editor(_root: Path) -> Path:
                exe = out / "UnrealEditor-Cmd.exe"
                exe.write_text("", encoding="utf-8")
                return exe

            def fake_run(*, cmd, env, log_path, timeout_seconds, extra_markers):
                log_path.write_text(log_body, encoding="utf-8")
                return 0, False

            return run_l2_introspect(
                ue_root=out, project_path=out / "P.uproject",
                introspect_script=script, log_path=log_path,
                submitted_assets=submitted,
                _editor_binary=fake_editor, _run_editor=fake_run,
            )

    @staticmethod
    def _task_block(checks):
        return (
            f"{INTROSPECT_JSON_START}\n"
            + json.dumps({"checks": checks})
            + f"\n{INTROSPECT_JSON_END}\n"
        )

    @staticmethod
    def _integrity_block(violations):
        return (
            f"{INTEGRITY_JSON_START}\n"
            + json.dumps({"violations": violations})
            + f"\n{INTEGRITY_JSON_END}\n"
        )

    def test_clean_integrity_plus_passing_task_is_pass(self) -> None:
        body = self._integrity_block([]) + self._task_block(
            [{"id": "a", "passed": True, "detail": ""}]
        )
        r = self._run(body, ["Content/Tasks/t/BP_A.uasset"])
        self.assertEqual(r.status, "pass")
        self.assertEqual((r.passed_count, r.total), (1, 1))

    def test_redirector_violation_grades_as_failed_check(self) -> None:
        body = self._integrity_block(
            [{"path": "Content/Tasks/t/BP_A.uasset",
              "reason": "REDIRECTOR_SUBMITTED /Game/Tasks/t/BP_A"}]
        ) + self._task_block([{"id": "a", "passed": True, "detail": ""}])
        r = self._run(body, ["Content/Tasks/t/BP_A.uasset"])
        self.assertEqual(r.status, "fail")           # GRADED, not error
        self.assertEqual((r.passed_count, r.total), (1, 2))
        self.assertEqual(r.checks[0].id, "asset_integrity")
        self.assertIn("REDIRECTOR_SUBMITTED", r.checks[0].detail)

    def test_probe_failure_routes_to_error_not_graded(self) -> None:
        body = self._integrity_block(
            [{"path": "x", "reason": "INTEGRITY_PROBE_ERROR boom"}]
        ) + self._task_block([{"id": "a", "passed": True, "detail": ""}])
        r = self._run(body, ["Content/Tasks/t/BP_A.uasset"])
        self.assertEqual(r.status, "error")
        self.assertTrue(any("verifier-side" in n for n in r.notes))

    def test_missing_integrity_block_when_expected_is_error(self) -> None:
        body = self._task_block([{"id": "a", "passed": True, "detail": ""}])
        r = self._run(body, ["Content/Tasks/t/BP_A.uasset"])
        self.assertEqual(r.status, "error")
        self.assertTrue(any("asset-integrity block" in n for n in r.notes))

    def test_no_submitted_assets_keeps_legacy_shape(self) -> None:
        body = self._task_block([{"id": "a", "passed": True, "detail": ""}])
        r = self._run(body, [])
        self.assertEqual(r.status, "pass")

    def test_only_mirror_files_skip_preamble_entirely(self) -> None:
        body = self._task_block([{"id": "a", "passed": True, "detail": ""}])
        r = self._run(
            body, ["Content/__ExternalActors__/Tasks/t/L_A/1/x.uasset"]
        )
        self.assertEqual(r.status, "pass")


class TestAllowRedirectorsFlag(unittest.TestCase):
    """The rename-residue exception (2026-07-30): default-closed, per-package.

    A rename task's legitimate deliverable can be a UObjectRedirector at the
    old path; the spec-declared ``allow_redirectors`` list exempts EXACTLY
    those packages from the preamble's rejection. Everything else — other
    packages, the identity check, probe-error routing, the manifest byte
    shape when the flag is absent — must be unchanged.
    """

    def _exec_bootstrap(self, bootstrap: Path, asset_class: str) -> str:
        class _Data:
            def is_valid(self):
                return True

            @property
            def asset_class_path(self):
                class _P:
                    asset_name = asset_class
                return _P()

        class _EAL:
            @staticmethod
            def find_asset_data(pkg):
                return _Data()

        class _Reg:
            def wait_for_completion(self):
                return None

        class _RegHelpers:
            @staticmethod
            def get_asset_registry():
                return _Reg()

        fake = type(sys)("unreal")
        fake.EditorAssetLibrary = _EAL
        fake.AssetRegistryHelpers = _RegHelpers
        fake.log = lambda *_a, **_k: None

        import contextlib
        import io
        buf = io.StringIO()
        old = sys.modules.get("unreal")
        sys.modules["unreal"] = fake
        try:
            with contextlib.redirect_stdout(buf):
                src = bootstrap.read_text(encoding="utf-8")
                exec(compile(src, str(bootstrap), "exec"),
                     {"__name__": "__main__", "__file__": str(bootstrap)})
        finally:
            if old is not None:
                sys.modules["unreal"] = old
            else:
                sys.modules.pop("unreal", None)
        return buf.getvalue()

    def _bootstrap(self, out: Path, allow):
        task_script = out / "grader.py"
        task_script.write_text("pass\n", encoding="utf-8")
        return write_integrity_bootstrap(
            out_dir=out, task_script=task_script,
            asset_rel_paths=["Content/Tasks/t/Old.uasset"], stem="grader",
            allow_redirectors=allow,
        )

    def test_allowed_redirector_is_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            bootstrap = self._bootstrap(out, ["/Game/Tasks/t/Old"])
            text = self._exec_bootstrap(bootstrap, "ObjectRedirector")
            self.assertIn('"violations": []', text)

    def test_non_listed_redirector_still_violates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            bootstrap = self._bootstrap(out, ["/Game/Tasks/t/SomethingElse"])
            text = self._exec_bootstrap(bootstrap, "ObjectRedirector")
            self.assertIn("REDIRECTOR_SUBMITTED", text)

    def test_allowed_entry_does_not_exempt_non_redirector_checks(self) -> None:
        # The exemption narrows ONLY the redirector rejection; a plain asset
        # at an allowed path passes exactly as before (no behavior change).
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            bootstrap = self._bootstrap(out, ["/Game/Tasks/t/Old"])
            text = self._exec_bootstrap(bootstrap, "Blueprint")
            self.assertIn('"violations": []', text)

    def test_default_manifest_byte_shape_unchanged(self) -> None:
        # Without the flag, manifest entries must not carry a redirector_ok
        # key — default runs stay byte-identical to the pre-flag shape.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            task_script = out / "grader.py"
            task_script.write_text("pass\n", encoding="utf-8")
            write_integrity_bootstrap(
                out_dir=out, task_script=task_script,
                asset_rel_paths=["Content/Tasks/t/Old.uasset"], stem="grader",
            )
            manifest = json.loads(
                (out / "asset_integrity_grader.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest,
                [{"rel": "Content/Tasks/t/Old.uasset",
                  "package": "/Game/Tasks/t/Old"}],
            )


class TestSpecAllowRedirectors(unittest.TestCase):
    """Front-matter 'allow_redirectors:' — task-scoped, L2I-only, fail-closed.

    Malformed declarations raise ValueError, which run_task surfaces as
    exit 2 (spec error) — a broken exception must never silently widen or
    narrow the preamble.
    """

    def _spec(self, *, layers="[L1, L2I]", introspect=True, allow=None):
        lines = ["---", "id: t2-rename-demo", "substrate: ThirdPerson",
                 f"layers: {layers}"]
        if introspect:
            lines.append("introspect: [rename_demo.py]")
        if allow is not None:
            lines.append(f"allow_redirectors: {allow}")
        lines += ["---", "", "## Prompt given to the agent", "", "> Do it."]
        return "\n".join(lines) + "\n"

    def _parse(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            p.write_text(text, encoding="utf-8")
            return parse_task_file(p)

    def test_round_trips_and_dedupes(self) -> None:
        spec_obj = self._parse(self._spec(
            allow='["/Game/Tasks/t2-rename-demo/Enums/WeaponType", '
                  '"/Game/Tasks/t2-rename-demo/Enums/WeaponType", '
                  '"/Game/Tasks/t2-rename-demo/Enums/ItemRarity"]'
        ))
        self.assertEqual(
            spec_obj.allow_redirectors,
            ("/Game/Tasks/t2-rename-demo/Enums/WeaponType",
             "/Game/Tasks/t2-rename-demo/Enums/ItemRarity"),
        )

    def test_absent_key_defaults_to_empty(self) -> None:
        spec_obj = self._parse(self._spec())
        self.assertEqual(spec_obj.allow_redirectors, ())

    def test_entry_outside_task_namespace_fails_closed(self) -> None:
        with self.assertRaises(ValueError) as cm:
            self._parse(self._spec(allow='["/Game/Shared/SomeAsset"]'))
        self.assertIn("task-scoped", str(cm.exception))

    def test_other_task_namespace_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self._parse(self._spec(allow='["/Game/Tasks/other-task/X"]'))

    def test_requires_l2i(self) -> None:
        with self.assertRaises(ValueError) as cm:
            self._parse(self._spec(
                layers="[L1]", introspect=False,
                allow='["/Game/Tasks/t2-rename-demo/X"]',
            ))
        self.assertIn("L2I", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
