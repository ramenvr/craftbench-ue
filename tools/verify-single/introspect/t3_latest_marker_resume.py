"""Fixed-denominator structural checks for the SaveGame persistence task."""

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
TASK_ID = "t3-the-run-resumes-at-the-latest-marker-without-paying-twice"
CHECK_IDS = (
    "UsesSuppliedSaveGameSchema",
    "PersistsIdentitySetAndAuthoritativeTotal",
    "SubmissionHasNoInProcessPersistenceSubstitute",
)
EXPECTED_FILES = sorted([
    "Source/ThirdPerson/Tasks/%s/RunResumePersistenceComponent.h" % TASK_ID,
    "Source/ThirdPerson/Tasks/%s/RunResumePersistenceComponent.cpp" % TASK_ID,
])
EXPECTED_ROOT_FILES = sorted([
    "RunResumePersistenceComponent.cpp",
    "RunResumePersistenceComponent.h",
    "RunResumeProtectedTypes.cpp",
    "RunResumeProtectedTypes.h",
])


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>")
                     .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def source_and_manifest():
    project = Path(unreal.Paths.project_dir()).resolve()
    root = project / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
    files = sorted(path for path in root.iterdir() if path.is_file())
    if [path.name for path in files] != EXPECTED_ROOT_FILES:
        raise RuntimeError("RUN_RESUME_SOURCE_INVENTORY %r" %
                           [path.name for path in files])
    accepted_names = {
        "RunResumePersistenceComponent.cpp",
        "RunResumePersistenceComponent.h",
    }
    texts = {path.name: path.read_text(encoding="utf-8") for path in files
             if path.name in accepted_names}
    manifest = json.loads(os.environ.get(
        "CRAFTBENCH_SUBMITTED_FILES_JSON", "[]"))
    if not isinstance(manifest, list):
        raise RuntimeError("RUN_RESUME_MANIFEST_SHAPE")
    return texts, sorted(item.replace("\\", "/") for item in manifest)


def main():
    results = {}
    if unreal is None:
        results = {item: check(item, False, "RUN_RESUME_NO_UNREAL")
                   for item in CHECK_IDS}
    else:
        try:
            texts, manifest = source_and_manifest()
            cpp = texts["RunResumePersistenceComponent.cpp"]
            header = texts["RunResumePersistenceComponent.h"]
            schema_tokens = (
                "URunResumeSaveGame",
                "UGameplayStatics::CreateSaveGameObject",
                "UGameplayStatics::SaveGameToSlot",
                "UGameplayStatics::LoadGameFromSlot",
                "SlotName",
                "RunNonce",
            )
            schema_ok = all(token in cpp + header for token in schema_tokens)
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], schema_ok,
                "RUN_RESUME_SCHEMA tokens=%d/%d" %
                (sum(token in cpp + header for token in schema_tokens),
                 len(schema_tokens)))
            flow_tokens = (
                "LatestCheckpointId",
                "LatestCheckpointTransform",
                "CollectedRewardIds",
                "RewardTotal",
                "RecordCheckpoint",
                "CollectReward",
                "RestoreFromSlot",
                "SetRetired",
            )
            flow_ok = all(token in cpp + header for token in flow_tokens)
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], flow_ok,
                "RUN_RESUME_FLOW tokens=%d/%d" %
                (sum(token in cpp + header for token in flow_tokens),
                 len(flow_tokens)))
            forbidden = (
                r"\bstatic\s+(?!ConstructorHelpers)",
                r"\bUGameInstance\b",
                r"GetGameInstance\s*\(",
                r"TEXT\s*\(\s*\"(?:Slot|Save|Checkpoint)",
            )
            hits = [pattern for pattern in forbidden
                    if re.search(pattern, cpp + header)]
            boundary_ok = manifest == EXPECTED_FILES and not hits
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], boundary_ok,
                "RUN_RESUME_BOUNDARY files=%r forbidden=%r" %
                (manifest, hits))
        except Exception as exc:
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "RUN_RESUME_READ_ERROR %r" % exc)
    payload = json.dumps(
        {"checks": [results[item] for item in CHECK_IDS]},
        separators=(",", ":"), ensure_ascii=True)
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
