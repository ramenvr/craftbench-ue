"""Offline regression tests for the menu reference closure file contract."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


AUTHORING = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, AUTHORING / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACT = load("reference_contract")
with mock.patch.dict("sys.modules", {"reference_contract": CONTRACT}):
    CLOSE = load("close_reference")


class CloseReferenceTests(unittest.TestCase):
    def test_copy_verified_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.uasset"
            destination = root / "destination.uasset"
            source.write_bytes(b"new-reference")
            destination.write_bytes(b"existing-evidence")
            with self.assertRaisesRegex(
                    CLOSE.ClosureError, "destination already exists"):
                CLOSE.copy_verified(
                    source, destination, CONTRACT.sha256(source))
            self.assertEqual(destination.read_bytes(), b"existing-evidence")

    def test_restore_quarantines_partial_and_restores_baseline_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "project" / CLOSE.REFERENCE_RELATIVE
            vault = root / "run" / "baseline" / CLOSE.REFERENCE_RELATIVE
            output = root / "run"
            live.parent.mkdir(parents=True)
            vault.parent.mkdir(parents=True)
            baseline = b"frozen-empty-baseline"
            partial = b"partial-reference"
            live.write_bytes(partial)
            vault.write_bytes(baseline)
            baseline_hash = CONTRACT.sha256(vault)
            with mock.patch.object(CONTRACT, "MENU_FILE", live), \
                    mock.patch.object(CONTRACT, "BASELINE_SHA256", baseline_hash):
                restored = CLOSE.restore_baseline(vault, output)
            self.assertEqual(live.read_bytes(), baseline)
            quarantined = (
                output / "rollback" / "partial-live" /
                CLOSE.REFERENCE_RELATIVE)
            self.assertEqual(quarantined.read_bytes(), partial)
            self.assertEqual(restored["sha256"], baseline_hash)

    def test_preflight_refuses_existing_reference_and_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            editor = root / "UnrealEditor-Cmd.exe"
            project = root / "ThirdPerson.uproject"
            author = root / "author.py"
            readback = root / "readback.py"
            for path in (editor, project, author, readback):
                path.write_bytes(b"fixture")
            entry = {"menu": {"sha256": CONTRACT.BASELINE_SHA256}}
            with mock.patch.multiple(
                    CLOSE, PROJECT=project, AUTHOR_SCRIPT=author,
                    READBACK_SCRIPT=readback), \
                    mock.patch.object(CLOSE, "require_plain_output"), \
                    mock.patch.object(CONTRACT, "require_reference_absent"), \
                    mock.patch.object(CONTRACT, "snapshot", return_value=entry):
                self.assertEqual(CLOSE.preflight(editor, output), entry)
                output.mkdir()
                with self.assertRaisesRegex(
                        CLOSE.ClosureError, "fresh output already exists"):
                    CLOSE.preflight(editor, output)


if __name__ == "__main__":
    unittest.main()
