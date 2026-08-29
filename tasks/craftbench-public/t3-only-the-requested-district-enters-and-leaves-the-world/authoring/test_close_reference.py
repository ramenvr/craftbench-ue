"""Offline file-contract tests for district reference closure."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CONTRACT = load("reference_contract")
with mock.patch.dict(sys.modules, {"reference_contract": CONTRACT}):
    CLOSE = load("close_reference")


class DistrictReferenceClosureTests(unittest.TestCase):
    def test_completed_closure_assets_are_exact_and_plain(self) -> None:
        self.assertEqual([CONTRACT.LOADER_FILE],
                         CONTRACT.files_under(CONTRACT.TASK_DIR))
        self.assertEqual(CONTRACT.BASELINE_SHA256,
                         CONTRACT.facts(CONTRACT.LOADER_FILE)["sha256"])
        for path, expected_hash in CONTRACT.EXPECTED_IMMUTABLE.items():
            self.assertEqual(expected_hash,
                             CONTRACT.facts(path)["sha256"])
        self.assertEqual(
            "03953E2F8D502240998835482DD514B004B920A3528173CC1B7A574C868264FE",
            CONTRACT.sha256(CONTRACT.FINAL_MAP))
        reference = CONTRACT.require_reference_exact(
            "10040E35C2AC25E09EA6F62FE9315A7704A9AE64AC96A93BA0ED5CACB912EC0C")
        self.assertEqual(50429, reference["size"])

    def test_copy_verified_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.uasset"
            destination = root / "destination.uasset"
            source.write_bytes(b"reference")
            destination.write_bytes(b"existing")
            with self.assertRaisesRegex(
                    CLOSE.ClosureError, "destination already exists"):
                CLOSE.copy_verified(
                    source, destination, CONTRACT.sha256(source))
            self.assertEqual(b"existing", destination.read_bytes())

    def test_restore_quarantines_partial_and_restores_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "live" / CLOSE.RELATIVE_ASSET
            vault = root / "run" / "baseline" / CLOSE.RELATIVE_ASSET
            live.parent.mkdir(parents=True)
            vault.parent.mkdir(parents=True)
            baseline = b"empty-district-loader"
            partial = b"partial-reference"
            live.write_bytes(partial)
            vault.write_bytes(baseline)
            baseline_hash = CONTRACT.sha256(vault)
            with mock.patch.object(CONTRACT, "LOADER_FILE", live), \
                    mock.patch.object(CONTRACT, "BASELINE_SHA256", baseline_hash):
                value = CLOSE.restore_baseline(vault, root / "run")
            self.assertEqual(baseline, live.read_bytes())
            quarantined = (
                root / "run" / "rollback" / "partial-live" /
                CLOSE.RELATIVE_ASSET)
            self.assertEqual(partial, quarantined.read_bytes())
            self.assertEqual(baseline_hash, value["sha256"])

    def test_output_ancestor_reparse_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "fresh" / "closure"
            real_is_reparse = CONTRACT.is_reparse

            def fake_is_reparse(path: Path) -> bool:
                return path == root or real_is_reparse(path)

            with mock.patch.object(
                    CONTRACT, "is_reparse", side_effect=fake_is_reparse):
                with self.assertRaisesRegex(
                        CLOSE.ClosureError, "link/reparse"):
                    CLOSE.require_plain_output(output)

    def test_copy_refuses_reparse_source_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.uasset"
            destination = root / "destination.uasset"
            source.write_bytes(b"reference")
            real_is_reparse = CONTRACT.is_reparse

            def fake_is_reparse(path: Path) -> bool:
                return path == source or real_is_reparse(path)

            with mock.patch.object(
                    CONTRACT, "is_reparse", side_effect=fake_is_reparse):
                with self.assertRaisesRegex(
                        CLOSE.ClosureError, "link/reparse"):
                    CLOSE.copy_verified(
                        source, destination, CONTRACT.sha256(source))
            self.assertFalse(destination.exists())

    def test_preflight_refuses_existing_output_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            output.mkdir()
            editor = root / "UnrealEditor-Cmd.exe"
            project = root / "ThirdPerson.uproject"
            author = root / "author.py"
            reference_readback = root / "reference.py"
            baseline_readback = root / "baseline.py"
            for path in (
                    editor, project, author, reference_readback,
                    baseline_readback):
                path.write_bytes(b"fixture")
            with mock.patch.multiple(
                    CLOSE, PROJECT=project, AUTHOR_SCRIPT=author,
                    REFERENCE_READBACK=reference_readback,
                    BASELINE_READBACK=baseline_readback):
                with self.assertRaisesRegex(
                        CLOSE.ClosureError, "fresh output already exists"):
                    CLOSE.preflight(editor, output)


if __name__ == "__main__":
    unittest.main()
