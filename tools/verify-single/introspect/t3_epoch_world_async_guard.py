"""Fixed-denominator structural checks for the cross-world epoch subsystem."""

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
TASK_ID = "t3-the-old-world-cannot-complete-into-the-new-one"
CHECK_IDS = (
    "UsesCancellableAsynchronousRequest",
    "CallbackIsBoundToWeakWorldEpoch",
    "SubmissionHasNoCrossWorldOrSynchronousSubstitute",
)
EXPECTED_FILES = sorted([
    "Source/ThirdPerson/Tasks/%s/EpochAssetWorldSubsystem.h" % TASK_ID,
    "Source/ThirdPerson/Tasks/%s/EpochAssetWorldSubsystem.cpp" % TASK_ID,
])
EXPECTED_ROOT_FILES = sorted([
    "EpochAssetWorldSubsystem.cpp", "EpochAssetWorldSubsystem.h",
    "EpochTravelProtectedTypes.cpp", "EpochTravelProtectedTypes.h",
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
        raise RuntimeError("EPOCH_SOURCE_INVENTORY %r" %
                           [path.name for path in files])
    texts = {path.name: path.read_text(encoding="utf-8") for path in files
             if path.name.startswith("EpochAssetWorldSubsystem")}
    manifest = json.loads(os.environ.get(
        "CRAFTBENCH_SUBMITTED_FILES_JSON", "[]"))
    if not isinstance(manifest, list):
        raise RuntimeError("EPOCH_MANIFEST_SHAPE")
    return texts, sorted(item.replace("\\", "/") for item in manifest)


def main():
    results = {}
    if unreal is None:
        results = {item: check(item, False, "EPOCH_NO_UNREAL")
                   for item in CHECK_IDS}
    else:
        try:
            texts, manifest = source_and_manifest()
            cpp = texts["EpochAssetWorldSubsystem.cpp"]
            header = texts["EpochAssetWorldSubsystem.h"]
            all_text = cpp + "\n" + header
            async_tokens = (
                "RequestAsyncLoad", "FStreamableHandle", "CancelHandle",
                "bStartStalled", "Deinitialize", "RetireActiveRequest",
            )
            async_ok = all(token in all_text for token in async_tokens)
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], async_ok,
                "EPOCH_ASYNC tokens=%d/%d" %
                (sum(token in all_text for token in async_tokens),
                 len(async_tokens)))
            guard_tokens = (
                "TWeakObjectPtr<UEpochAssetWorldSubsystem>",
                "TWeakObjectPtr<UWorld>",
                "TWeakObjectPtr<AEpochAssetDisplay>",
                "ActiveEpoch", "RequestEpoch", "Self->GetWorld()",
                "LiveDestination->GetWorld()", "WeakSelf.Get()",
            )
            guard_ok = all(token in all_text for token in guard_tokens) \
                and bool(re.search(r"ActiveEpoch\s*!=\s*RequestEpoch", cpp))
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], guard_ok,
                "EPOCH_GUARD tokens=%d/%d epoch_compare=%d" %
                (sum(token in all_text for token in guard_tokens),
                 len(guard_tokens),
                 bool(re.search(r"ActiveEpoch\s*!=\s*RequestEpoch", cpp))))
            forbidden = (
                r"LoadSynchronous\s*\(", r"StaticLoadObject\s*\(",
                r"LoadObject\s*<", r"GetGameInstance\s*\(",
                r"EpochTravelReporterSubsystem", r"EPOCH-TRAVEL-",
                r"OldQuartz|NewViolet|L_OldEpochStart|L_NewEpochDestination",
                r"\bstatic\s+(?!ConstructorHelpers|constexpr)",
            )
            hits = [pattern for pattern in forbidden
                    if re.search(pattern, all_text)]
            boundary_ok = manifest == EXPECTED_FILES and not hits
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], boundary_ok,
                "EPOCH_BOUNDARY files=%r forbidden=%r" % (manifest, hits))
        except Exception as exc:
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "EPOCH_READ_ERROR %r" % exc)
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
