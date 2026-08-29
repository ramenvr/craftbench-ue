"""Run the CommonUI admission test three times through the real L2 runner.

Prepared authoring aid; do not execute while another Unreal task owns the
commandlet slot. It reuses layers/l2_pie.py so report parsing, timeout handling,
terminal-marker shutdown, and expected-test-count semantics are identical to
the benchmark runner rather than reimplemented in shell.
"""
import re
import sys
from pathlib import Path
import os


HERE = Path(__file__).resolve().parent
TASK_DIR = HERE.parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
LAYERS = VERIFY / "layers"
sys.path.insert(0, str(VERIFY))
sys.path.insert(0, str(LAYERS))

from l2_pie import run_l2  # noqa: E402


TASK_ID = "t2-top-screen-keeps-focus-until-dismissed"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
MAP_PACKAGE = "/Game/Maps/%s/L_FocusStack" % TASK_ID
MAP_FILE = (REPO / "UE-projects" / "ThirdPerson" / "Content" / "Maps" /
            TASK_ID / "L_FocusStack.umap")
TEST_FILTER = (
    "Project.Functional Tests.Maps.%s.L_FocusStack."
    "CommonUIFocusAdmissionFunctionalTest" % TASK_ID
)
SUCCESS_TOKEN = "FOCUS-ADMISSION: all activation and focus telemetry passed"
FOCUS_LINE = re.compile(
    r"\[focus-admission\] stage=(?P<stage>\S+).*"
    r"expected_focus=(?P<expected>true|false).*"
    r"unexpected_focus=(?P<unexpected>true|false)",
    re.IGNORECASE,
)
OUT = REPO / "runs" / "authoring" / TASK_ID / "admission"


def die(message):
    print("FOCUS-ADMISSION-RUNNER-ERROR %s" % message)
    raise SystemExit(message)


def focus_vector(log_text):
    vector = []
    for match in FOCUS_LINE.finditer(log_text):
        vector.append((match.group("stage"), match.group("expected").lower(),
                       match.group("unexpected").lower()))
    return tuple(vector)


def main():
    if not PROJECT.is_file():
        die("project missing: %s" % PROJECT)
    if not MAP_FILE.is_file():
        die("committed-path map missing: %s" % MAP_FILE)
    if OUT.exists():
        die("output already exists; preserve evidence and choose a clean run: %s" % OUT)

    vectors = []
    for round_number in range(1, 4):
        round_dir = OUT / ("round-%d" % round_number)
        log_path = round_dir / "l2.log"
        report_dir = round_dir / "report"
        result = run_l2(
            ue_root=UE_ROOT,
            project_path=PROJECT,
            test_filter=TEST_FILTER,
            log_path=log_path,
            report_dir=report_dir,
            map_name="L_FocusStack",
            map_package_path=MAP_PACKAGE,
            use_nullrhi=True,
            fps=60,
            timeout_seconds=600.0,
            expected_test_count=1,
        )
        print("FOCUS-ADMISSION-ROUND round=%d status=%s tests=%d passed=%d "
              "failed=%d exit=%d source=%s" % (
                  round_number, result.status, result.tests_run,
                  result.tests_passed, result.tests_failed, result.exit_code,
                  result.result_source))
        if result.status != "pass" or result.tests_run != 1 or \
                result.tests_passed != 1 or result.tests_failed != 0:
            die("round %d did not produce one authoritative PASS; log=%s" %
                (round_number, log_path))
        text = log_path.read_text(encoding="utf-8", errors="replace")
        if SUCCESS_TOKEN not in text:
            die("round %d lacks final success token" % round_number)
        for forbidden in ("HARNESS-PRECONDITION", "FOCUS-ADMISSION-RUNNER-ERROR"):
            if forbidden in text:
                die("round %d contains forbidden token %s" %
                    (round_number, forbidden))
        vector = focus_vector(text)
        if not vector:
            die("round %d emitted no focus telemetry vector" % round_number)
        vectors.append(vector)

    if not (vectors[0] == vectors[1] == vectors[2]):
        die("three admission focus vectors differ")
    print("FOCUS-ADMISSION-3X-DONE vector=%s" % (vectors[0],))


if __name__ == "__main__":
    main()
