"""Fixed-denominator, verifier-owned shared-helper structural introspector.

This task-local candidate must be installed byte-for-byte under
tools/verify-single/introspect/ by the shared owner before production L2I.
It is read-only and always emits exactly three check IDs.
"""

import json
import os
from pathlib import Path
import re

try:
    import unreal
except ImportError:  # offline syntax/unit checks
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
CHECK_IDS = (
    "GameInstanceLeaseSurfacePresent",
    "ReflectedLeaseAndCacheOwnership",
    "WeakOwnerAndNoRootPin",
)
EXPECTED = re.compile(
    r"^(PASS|FAIL) subsystem=([01]) acquire=([01]) release=([01]) "
    r"lease_strong=([01]) owner_weak=([01]) cache_array=([01]) "
    r"cache_helper_strong=([01]) cache_leases_strong=([01]) "
    r"active_leases_strong=([01])$")
FORBIDDEN = (
    re.compile(r"\bAddToRoot\s*\("),
    re.compile(r"\bRemoveFromRoot\s*\("),
    re.compile(r"\bRF_RootSet\b"),
    re.compile(r"\bTStrongObjectPtr\s*<"),
    re.compile(r"\bstatic\s+(?:TObjectPtr\s*<\s*)?UShared(?:LeaseHelper|HelperLease)"),
)


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:700]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def _is_reparse(stat_result):
    return bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def source_texts():
    project = Path(unreal.Paths.project_dir()).resolve()
    root = (project / "Source" / "ThirdPerson" / "Tasks" /
            TASK_ID)
    if not root.is_dir() or _is_reparse(os.lstat(root)):
        raise RuntimeError("SHARED_HELPER_SOURCE_ROOT_MISSING_OR_REPARSE " + str(root))
    stack = [root]
    files = []
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or _is_reparse(info):
                    raise RuntimeError("SHARED_HELPER_SOURCE_REPARSE " + entry.path)
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False) and \
                        Path(entry.name).suffix.lower() in (".h", ".cpp"):
                    files.append(Path(entry.path))
    exact = {"SharedHelperLeaseSubsystem.h", "SharedHelperLeaseSubsystem.cpp"}
    names = {path.name for path in files}
    if not exact.issubset(names):
        raise RuntimeError("SHARED_HELPER_EXACT_SOURCE_MISSING actual=%r" % sorted(names))
    return [(path, path.read_text(encoding="utf-8"))
            for path in sorted(files)]


def inspect():
    helper = getattr(unreal, "SharedHelperLeaseAuthoringLibrary", None)
    if helper is None:
        raise RuntimeError("SHARED_HELPER_NATIVE_HELPER_UNAVAILABLE")
    detail = helper.inspect_runtime_contract()
    if type(detail) is not str:
        raise RuntimeError("SHARED_HELPER_NATIVE_SHAPE actual=%r" % (detail,))
    match = EXPECTED.fullmatch(detail)
    if match is None:
        raise RuntimeError("SHARED_HELPER_NATIVE_VECTOR_UNPARSEABLE " + detail)
    values = tuple(value == "1" for value in match.groups()[1:])
    source_failures = []
    for path, text in source_texts():
        for pattern in FORBIDDEN:
            if pattern.search(text):
                source_failures.append(path.name + ":" + pattern.pattern)
    gates = (
        all(values[0:3]),
        all((values[3], values[5], values[6], values[7], values[8])),
        values[4] and not source_failures,
    )
    return gates, detail, source_failures


def main():
    results = {}
    if unreal is None:
        for check_id in CHECK_IDS:
            results[check_id] = check(check_id, False, "SHARED_HELPER_NO_UNREAL")
    else:
        try:
            gates, detail, source_failures = inspect()
            for check_id, passed in zip(CHECK_IDS, gates):
                results[check_id] = check(
                    check_id,
                    passed,
                    "%s forbidden=%s" % (detail, source_failures),
                )
        except Exception as exc:  # fail closed, fixed denominator
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "SHARED_HELPER_READ_ERROR %r" % (exc,))
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
