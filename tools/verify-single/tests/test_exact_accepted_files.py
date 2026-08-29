"""Task-scoped exact accepted-files boundary tests (no UE required)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
VERIFY = HERE.parent
if str(VERIFY) not in sys.path:
    sys.path.insert(0, str(VERIFY))

from sandbox import (  # noqa: E402
    WritableManifest,
    enforce_exact_accepted_files,
    scan_submission,
)
from spec import parse_task_file  # noqa: E402


def spec_text(accepted: str) -> str:
    return (
        "---\n"
        "id: t-test-exact-files\n"
        "substrate: ThirdPerson\n"
        "set: bp\n"
        "tier: T1\n"
        "capability_bucket: Other\n"
        "category: other\n"
        "layers: [L1]\n"
        f"accepted_files: {accepted}\n"
        "---\n\n# t-test-exact-files\n"
    )


class ExactAcceptedFilesTests(unittest.TestCase):
    def test_spec_round_trips_normalized_exact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            task = Path(temp) / "task.md"
            task.write_text(
                spec_text("[Content/Tasks/t-test-exact-files/A.uasset, "
                          "Source/ThirdPerson/A.cpp]"),
                encoding="utf-8",
            )
            parsed = parse_task_file(task)
        self.assertEqual(
            parsed.accepted_files,
            (
                "Content/Tasks/t-test-exact-files/A.uasset",
                "Source/ThirdPerson/A.cpp",
            ),
        )

    def test_spec_rejects_empty_unsafe_and_case_duplicate_lists(self) -> None:
        bad = (
            "[]",
            "[../A.uasset]",
            "[C:/A.uasset]",
            "[Content/Tasks/A.uasset, content/tasks/a.uasset]",
        )
        for value in bad:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                task = Path(temp) / "task.md"
                task.write_text(spec_text(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    parse_task_file(task)

    def test_exact_manifest_accepts_only_equality(self) -> None:
        manifest = WritableManifest(
            substrate="ThirdPerson",
            game_module="ThirdPerson",
            writable=("Source/ThirdPerson/",),
            deny=(),
            asset_writable=("Content/Tasks/",),
        )
        expected = (
            "Content/Tasks/t-test-exact-files/A.uasset",
            "Source/ThirdPerson/A.cpp",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel in expected:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            result = scan_submission(root, manifest)
            enforce_exact_accepted_files(result, root, expected)
            self.assertTrue(result.ok, result.render_report())

    def test_missing_and_writable_extra_are_both_rejected(self) -> None:
        manifest = WritableManifest(
            substrate="ThirdPerson",
            game_module="ThirdPerson",
            writable=(),
            deny=(),
            asset_writable=("Content/Tasks/",),
        )
        expected = ("Content/Tasks/t-test-exact-files/A.uasset",)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            extra = root / "Content/Tasks/t-test-exact-files/B.uasset"
            extra.parent.mkdir(parents=True)
            extra.write_bytes(b"x")
            result = scan_submission(root, manifest)
            enforce_exact_accepted_files(result, root, expected)
        reasons = sorted(item.reason for item in result.violations)
        self.assertEqual(
            reasons,
            [
                "not declared in task accepted_files",
                "required by task accepted_files but missing",
            ],
        )

    def test_legacy_task_without_manifest_keeps_substrate_policy(self) -> None:
        manifest = WritableManifest(
            substrate="ThirdPerson",
            game_module="ThirdPerson",
            writable=(),
            deny=(),
            asset_writable=("Content/Tasks/",),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = root / "Content/Tasks/legacy/A.uasset"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"x")
            result = scan_submission(root, manifest)
            enforce_exact_accepted_files(result, root, ())
            self.assertTrue(result.ok, result.render_report())


if __name__ == "__main__":
    unittest.main()
