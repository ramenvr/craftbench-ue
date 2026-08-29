"""Fixed-denominator structural checks for the Primary Asset bundle lease task.

This read-only introspector always emits exactly three check IDs. Runtime
behavior and residency remain authoritative in L2; L2I only proves the required
engine API route and rejects broad/synchronous shortcuts.
"""

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
TASK_ID = "t2-one-bundle-loads-without-pulling-in-the-rest"
CHECK_IDS = (
    "ManagedPrimaryAssetBundleApisPresent",
    "SharedOwnerHandleTopologyPresent",
    "NoBroadOrSynchronousLoading",
)
FORBIDDEN = (
    re.compile(r"\bTryLoad\s*\("),
    re.compile(r"\bLoadSynchronous\s*\("),
    re.compile(r"\bUnloadPrimaryAsset\s*\("),
    re.compile(r"\bAddToRoot\s*\("),
    re.compile(r"\b(?:Quartz|Violet|Amber|DA_BundleRecord_[A-Za-z0-9_]+)\b"),
)


def result(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:700]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def is_reparse(path):
    stat_result = os.lstat(path)
    return path.is_symlink() or bool(
        getattr(stat_result, "st_file_attributes", 0) & 0x400)


def read_sources():
    project = Path(unreal.Paths.project_dir()).resolve()
    root = project / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
    if not root.is_dir() or is_reparse(root):
        raise RuntimeError("BUNDLE_LEASE_SOURCE_ROOT_MISSING_OR_REPARSE " + str(root))
    expected = ("BundleLeaseRuntime.h", "BundleLeaseRuntime.cpp")
    texts = {}
    for name in expected:
        path = root / name
        if not path.is_file() or is_reparse(path):
            raise RuntimeError("BUNDLE_LEASE_SOURCE_MISSING_OR_REPARSE " + str(path))
        texts[name] = path.read_text(encoding="utf-8")
    return texts


def inspect():
    texts = read_sources()
    header = texts["BundleLeaseRuntime.h"]
    source = texts["BundleLeaseRuntime.cpp"]
    load_api = bool(re.search(r"\bLoadPrimaryAsset\s*\(", source))
    change_api = bool(re.search(
        r"\bChangeBundleStateForPrimaryAssets\s*\(", source))
    topology_tokens = (
        "TSet<TWeakObjectPtr<UObject>> Owners",
        "TSharedPtr<FStreamableHandle> LoadHandle",
        "TMap<TWeakObjectPtr<UObject>, FBundleLeaseKey> OwnerToKey",
        "TMap<FBundleLeaseKey, FBundleLeaseEntry> Entries",
    )
    topology = all(token in header for token in topology_tokens)
    forbidden = [
        pattern.pattern for pattern in FORBIDDEN if pattern.search(source)
    ]
    detail = (
        "load_primary=%d change_bundle=%d owners=%d handle=%d owner_map=%d "
        "entry_map=%d forbidden=%s" % (
            load_api,
            change_api,
            "TSet<TWeakObjectPtr<UObject>> Owners" in header,
            "TSharedPtr<FStreamableHandle> LoadHandle" in header,
            "TMap<TWeakObjectPtr<UObject>, FBundleLeaseKey> OwnerToKey" in header,
            "TMap<FBundleLeaseKey, FBundleLeaseEntry> Entries" in header,
            forbidden,
        ))
    return (load_api and change_api, topology, not forbidden), detail


def main():
    checks = {}
    if unreal is None:
        for check_id in CHECK_IDS:
            checks[check_id] = result(check_id, False, "BUNDLE_LEASE_NO_UNREAL")
    else:
        try:
            gates, detail = inspect()
            for check_id, passed in zip(CHECK_IDS, gates):
                checks[check_id] = result(check_id, passed, detail)
        except Exception as exc:
            for check_id in CHECK_IDS:
                checks[check_id] = result(
                    check_id, False, "BUNDLE_LEASE_READ_ERROR %r" % (exc,))
    payload = json.dumps(
        {"checks": [checks[item] for item in CHECK_IDS]},
        separators=(",", ":"), ensure_ascii=True)
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
