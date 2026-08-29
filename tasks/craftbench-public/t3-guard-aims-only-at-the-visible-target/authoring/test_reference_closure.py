"""Offline contracts for the reference closure."""

import ast
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


class ReferenceClosureContracts(unittest.TestCase):
    def test_all_scripts_parse(self):
        for name in (
            "reference_contract.py", "author_reference.py",
            "readback_reference.py", "readback_restored_baseline.py",
            "close_reference.py", "run_final_reference_probe.py",
        ):
            path = HERE / name
            ast.parse(path.read_text("utf-8"), filename=str(path))

    def test_atomic_restore_and_fail_closed_markers(self):
        closure = (HERE / "close_reference.py").read_text("utf-8")
        for token in (
            "assert_no_writers()", "move_directory(contract.FINAL_DISK_DIR",
            "os.replace(baseline_vault, contract.FINAL_DISK_DIR)",
            "GUARD-AIM-REFERENCE-COLD-PASS",
            "GUARD-AIM-BASELINE-COLD-PASS", "recover(output, baseline_vault)",
            "complete reference equals empty baseline",
        ):
            self.assertIn(token, closure)

    def test_reference_is_exactly_one_asset(self):
        contract = (HERE / "reference_contract.py").read_text("utf-8")
        author = (HERE / "author_reference.py").read_text("utf-8")
        self.assertIn("expected = {FINAL_ASSET.name}", contract)
        self.assertIn("build_anim_graph(asset, True)", author)
        self.assertIn("inspect_anim_blueprint(asset, True)", author)

    def test_final_probe_is_exact_two_and_restores_baseline(self):
        probe = (HERE / "run_final_reference_probe.py").read_text("utf-8")
        for token in (
            "expected_test_count=2", "GUARD-VISIBLE-AIM-NAV-ROUTE PASS",
            "projected=4 paths=2", "move_directory(contract.FINAL_DISK_DIR",
            "os.replace(baseline_vault, contract.FINAL_DISK_DIR)",
            "baseline_restored", "immutable_unchanged",
        ):
            self.assertIn(token, probe)


if __name__ == "__main__":
    unittest.main()
