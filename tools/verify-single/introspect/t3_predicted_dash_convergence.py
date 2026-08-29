"""Fixed four-check source structural grader for predicted dash."""

import json
import os
from pathlib import Path
import re

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-dash-responds-now-and-converges-later"
REL = f"Source/ThirdPerson/Tasks/{TASK_ID}"
EXPECTED = sorted((f"{REL}/PredictedDashMovementComponent.h",
                   f"{REL}/PredictedDashMovementComponent.cpp"))
CHECK_IDS = (
    "DashUsesCustomSavedMove",
    "DashUsesCharacterNetworkMoveData",
    "AcceptedAccountingIsAuthorityOwned",
    "SubmissionHasNoTransformReplicationShortcut",
)


def result(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>")
                     .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def main():
    checks = {}
    try:
        project = Path(unreal.Paths.project_dir()) if unreal else Path.cwd()
        header = (project / REL / "PredictedDashMovementComponent.h").read_text(
            encoding="utf-8", errors="replace")
        cpp = (project / REL / "PredictedDashMovementComponent.cpp").read_text(
            encoding="utf-8", errors="replace")
        joined = header + "\n" + cpp
        manifest = json.loads(os.environ.get(
            "CRAFTBENCH_SUBMITTED_FILES_JSON", "[]"))
        submitted = sorted(str(item).replace("\\", "/") for item in manifest) \
            if isinstance(manifest, list) else []

        saved = all(token in joined for token in (
            "FPredictedDashSavedMove", "FSavedMove_Character",
            "AllocateNewMove", "FLAG_Custom_0", "SetMoveFor",
            "PrepMoveFor", "CanCombineWith"))
        checks[CHECK_IDS[0]] = result(
            CHECK_IDS[0], saved,
            "saved_move=%d custom_flag=%d replay=%d" % (
                "FPredictedDashSavedMove" in joined,
                "FLAG_Custom_0" in joined,
                "PrepMoveFor" in joined))

        move_data = all(token in joined for token in (
            "FPredictedDashNetworkMoveData", "FCharacterNetworkMoveData",
            "ClientFillNetworkMoveData", "Serialize(",
            "FPredictedDashNetworkMoveDataContainer",
            "SetNetworkMoveDataContainer", "GetCurrentNetworkMoveData"))
        checks[CHECK_IDS[1]] = result(
            CHECK_IDS[1], move_data,
            "custom_move_data=%d serialize=%d container=%d current_data=%d" % (
                "ClientFillNetworkMoveData" in joined,
                "NetSerialize" in joined,
                "SetNetworkMoveDataContainer" in joined,
                "GetCurrentNetworkMoveData" in joined))

        authority = "CharacterOwner->HasAuthority()" in cpp \
            and "AuthorizeAndCommitDash" in cpp
        no_local_accounting = not re.search(
            r"\b(?:DashEnergy|AccountingRevision|CooldownRevision)\s*[+\-=]",
            cpp)
        checks[CHECK_IDS[2]] = result(
            CHECK_IDS[2], authority and no_local_accounting,
            "authority_guard=%d protected_commit=%d local_accounting=%d" % (
                "CharacterOwner->HasAuthority()" in cpp,
                "AuthorizeAndCommitDash" in cpp, not no_local_accounting))

        forbidden = re.findall(
            r"\b(?:SetActorLocation|SetWorldLocation|TeleportTo|NetMulticast|"
            r"ServerSetTransform|ClientAuthoritativePosition)\b", joined)
        boundary = submitted == EXPECTED
        checks[CHECK_IDS[3]] = result(
            CHECK_IDS[3], boundary and not forbidden,
            "exact_files=%d forbidden=%r submitted=%r" %
            (boundary, sorted(set(forbidden)), submitted))
    except Exception as exc:
        for check_id in CHECK_IDS:
            checks[check_id] = result(check_id, False,
                                      "DASH_INTROSPECTION_ERROR %r" % exc)
    payload = json.dumps(
        {"checks": [checks[item] for item in CHECK_IDS]},
        separators=(",", ":"), ensure_ascii=True)
    print(START)
    print(payload)
    print(END)
    if unreal:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
