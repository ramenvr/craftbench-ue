"""Run both retained fixtures against the reference without changing baseline bytes.

This is an authoring probe, not a production grade.  It atomically parks the
live one-file empty baseline, overlays the already cold-read reference asset at
the same package path, runs exact L2, and restores the baseline in ``finally``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import shutil
import sys

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from close_reference import assert_no_writers, move_directory  # noqa: E402
from guard_aim_common import FINAL_MAP, PROJECT, REFERENCE, REPO, sha256  # noqa: E402
import reference_contract as contract  # noqa: E402


BASE = (
    "Project.Functional Tests.Maps."
    "t3-guard-aims-only-at-the-visible-target.L_GuardVisibleAim.")
EXPECTED = {
    "GuardVisibleAimLeftHighFunctionalTest":
        BASE + "GuardVisibleAimLeftHighFunctionalTest",
    "GuardVisibleAimRightLowFunctionalTest":
        BASE + "GuardVisibleAimRightLowFunctionalTest",
}
FILTER = "+".join(EXPECTED.values())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def exact_reference_hash() -> str:
    if REFERENCE.parent.is_symlink() or not REFERENCE.is_file():
        raise RuntimeError("exact reference asset missing or linked")
    observed = list(REFERENCE.parent.iterdir())
    if observed != [REFERENCE] or REFERENCE.is_symlink():
        raise RuntimeError("reference inventory is not exact one file")
    return sha256(REFERENCE)


def audit(output: Path, result: object) -> list[str]:
    problems: list[str] = []
    report_path = output / "report" / "index.json"
    report = json.loads(report_path.read_text(encoding="utf-8-sig")) \
        if report_path.is_file() else {}
    tests = report.get("tests", [])
    observed = {test.get("testDisplayName"): test for test in tests}
    if result.status != "pass" or result.tests_run != 2 \
            or result.tests_passed != 2 or result.tests_failed != 0:
        problems.append("L2 result/count mismatch")
    if set(observed) != set(EXPECTED):
        problems.append("exact display-name set mismatch")
    for display, full_path in EXPECTED.items():
        test = observed.get(display, {})
        if test.get("fullTestPath") != full_path \
                or test.get("state") != "Success":
            problems.append("identity/state mismatch: " + display)
    log_text = (output / "l2.log").read_text(
        encoding="utf-8", errors="replace")
    if log_text.count("GUARD-VISIBLE-AIM-NAV-ROUTE PASS") != 2:
        problems.append("route PASS count mismatch")
    if log_text.count("projected=4 paths=2") != 2:
        problems.append("route coverage vector mismatch")
    if log_text.count("GUARD-VISIBLE-AIM-PASS") != 2:
        problems.append("terminal PASS count mismatch")
    for gate in (
            "OnlySightPerceivedIdentityMayDriveAim",
            "PerceivedTargetDrivesAdditiveAimOverlay",
            "OccludedTargetStopsDrivingAim",
            "ReappearingTargetIsReacquired",
            "BaseLocomotionRemainsContinuous"):
        if log_text.count(gate) != 2:
            problems.append("named gate count mismatch: " + gate)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--timeout-seconds", type=float, default=720.0)
    args = parser.parse_args()
    output = args.output.resolve()
    assert_no_writers()
    if os.path.lexists(output):
        raise RuntimeError("output must be fresh")
    baseline = contract.exact_live_vector()
    immutable = contract.immutable_vector()
    reference_hash = exact_reference_hash()
    if baseline[contract.FINAL_ASSET.name] == reference_hash:
        raise RuntimeError("reference unexpectedly equals empty baseline")
    output.mkdir(parents=True, exist_ok=False)
    baseline_vault = output / "baseline-vault" / contract.FINAL_DISK_DIR.name
    overlay_vault = output / "reference-after-run" / contract.FINAL_DISK_DIR.name
    manifest: dict[str, object] = {
        "status": "running", "filter": FILTER, "expected_count": 2,
        "baseline": baseline, "immutable": immutable,
        "reference_sha256": reference_hash,
    }
    write_json(output / "probe.json", manifest)
    try:
        move_directory(contract.FINAL_DISK_DIR, baseline_vault)
        contract.FINAL_DISK_DIR.mkdir(parents=True, exist_ok=False)
        shutil.copy2(REFERENCE, contract.FINAL_ASSET)
        if contract.exact_live_vector()[contract.FINAL_ASSET.name] \
                != reference_hash:
            raise RuntimeError("live reference overlay hash mismatch")

        verify = REPO / "tools" / "verify-single"
        sys.path.insert(0, str(verify))
        sys.path.insert(0, str(verify / "layers"))
        from l2_pie import run_l2
        result = run_l2(
            ue_root=args.ue_root.resolve(), project_path=PROJECT,
            test_filter=FILTER, log_path=output / "l2.log",
            report_dir=output / "report", map_name="L_GuardVisibleAim",
            map_package_path=FINAL_MAP, use_nullrhi=True, fps=60,
            timeout_seconds=args.timeout_seconds, expected_test_count=2)
        write_json(output / "l2_result.json", dataclasses.asdict(result))
        problems = audit(output, result)
        manifest.update({"result": dataclasses.asdict(result),
                         "problems": problems})
    except Exception as exc:
        manifest.update({"problems": ["probe exception: " + str(exc)]})
    finally:
        try:
            if contract.FINAL_DISK_DIR.is_dir():
                move_directory(contract.FINAL_DISK_DIR, overlay_vault)
            if baseline_vault.is_dir() and not contract.FINAL_DISK_DIR.exists():
                contract.FINAL_DISK_DIR.parent.mkdir(parents=True, exist_ok=True)
                os.replace(baseline_vault, contract.FINAL_DISK_DIR)
        except Exception as exc:
            manifest.setdefault("problems", []).append(
                "baseline restoration exception: " + str(exc))

    restored = contract.exact_live_vector() == baseline
    immutable_after = contract.immutable_vector()
    protected = immutable_after == immutable
    manifest.update({"baseline_restored": restored,
                     "immutable_unchanged": protected})
    problems = manifest.setdefault("problems", [])
    if not restored:
        problems.append("baseline restoration mismatch")
    if not protected:
        problems.append("immutable package mismatch")
    manifest["status"] = "pass" if not problems else "fail"
    write_json(output / "probe.json", manifest)
    if problems:
        print("GUARD-AIM-FINAL-PROBE-FAILED " + "; ".join(problems))
        return 1
    print("GUARD-AIM-FINAL-PROBE-PASS tests=2 routes=2 gates=5 "
          "baseline_restored=1 immutable=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
