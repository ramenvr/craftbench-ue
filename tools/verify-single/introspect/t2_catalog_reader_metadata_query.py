"""Fixed source-introspection gates for the catalog-reader task.

The runtime test proves the two independently configured results and package
non-residency.  These read-only checks close the complementary shortcut: a
submission may not replace the Asset Registry metadata route with protected
package literals, object loads, or filesystem enumeration.  The denominator is
always four checks, including missing or malformed submissions.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

try:
    import unreal
except ImportError:  # Offline contract tests may import the module.
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t2-each-catalog-reader-reports-only-its-own-records"
REL_ROOT = Path("Source/ThirdPerson/Tasks") / TASK_ID
HEADER_REL = (REL_ROOT / "CatalogReaderActor.h").as_posix()
SOURCE_REL = (REL_ROOT / "CatalogReaderActor.cpp").as_posix()
CHECK_IDS = (
    "catalog_submission_surface_exact",
    "catalog_filter_uses_live_actor_configuration",
    "catalog_query_is_metadata_only",
    "catalog_result_is_sorted_and_protected_published",
)


def _check(check_id: str, passed: bool, detail: str) -> dict:
    safe = str(detail).replace("CRAFTBENCH-INTROSPECT-JSON", "CB-MARKER")[:500]
    return {"id": check_id, "passed": bool(passed), "detail": safe}


def _emit(checks: list[dict]) -> None:
    payload = json.dumps({"checks": checks}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


def _project_dir() -> Path:
    if unreal is None:
        return Path.cwd()
    raw = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return Path(str(raw))


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\r\n]*", " ", text, flags=re.DOTALL)


def _has_all(text: str, tokens: tuple[str, ...]) -> tuple[bool, list[str]]:
    missing = [token for token in tokens if token not in text]
    return not missing, missing


def _run() -> list[dict]:
    results: dict[str, dict] = {}
    expected = {HEADER_REL, SOURCE_REL}
    try:
        manifest = json.loads(os.environ.get("CRAFTBENCH_SUBMITTED_FILES_JSON", "[]"))
        observed = {str(item).replace("\\", "/") for item in manifest}
        surface_ok = observed == expected
        results[CHECK_IDS[0]] = _check(
            CHECK_IDS[0],
            surface_ok,
            "CATALOG_SOURCE_SURFACE_OK files=2" if surface_ok else
            "CATALOG_SOURCE_SURFACE_MISMATCH observed=%s" % sorted(observed),
        )
    except Exception as exc:  # noqa: BLE001 - fail closed into fixed check.
        results[CHECK_IDS[0]] = _check(
            CHECK_IDS[0], False, "CATALOG_SOURCE_SURFACE_ERROR %r" % (exc,))

    try:
        root = _project_dir()
        header = (root / HEADER_REL).read_text(encoding="utf-8-sig")
        source = (root / SOURCE_REL).read_text(encoding="utf-8-sig")
        code = _without_comments(header + "\n" + source)
    except Exception as exc:  # noqa: BLE001
        cause = "CATALOG_SOURCE_READ_ERROR %r" % (exc,)
        for check_id in CHECK_IDS[1:]:
            results[check_id] = _check(check_id, False, cause)
        return [results[check_id] for check_id in CHECK_IDS]

    filter_tokens = (
        "FARFilter",
        "PackagePaths.Add(ConfiguredPackagePath)",
        "ClassPaths.Add(ConfiguredAssetClass)",
        "bRecursivePaths = true",
        "bIncludeOnlyOnDiskAssets = true",
        "GetAssets(Filter",
    )
    filter_ok, filter_missing = _has_all(code, filter_tokens)
    results[CHECK_IDS[1]] = _check(
        CHECK_IDS[1],
        filter_ok,
        "CATALOG_LIVE_FILTER_OK dimensions=2" if filter_ok else
        "CATALOG_LIVE_FILTER_MISSING tokens=%s" % filter_missing,
    )

    forbidden = (
        "LoadObject",
        "LoadPackage",
        "StaticLoadObject",
        ".GetAsset(",
        "->GetAsset(",
        "IFileManager",
        "FFileHelper",
        "std::filesystem",
        f"/Game/Maps/{TASK_ID}/Catalog",
        "DA_Alpha_Cedar",
        "DA_Alpha_Lapis",
        "DA_Alpha_Quartz",
        "DA_Beta_Amber",
        "DA_Beta_Violet",
        "NorthArchive",
        "SouthArchive",
    )
    found_forbidden = [token for token in forbidden if token in code]
    results[CHECK_IDS[2]] = _check(
        CHECK_IDS[2],
        not found_forbidden,
        "CATALOG_METADATA_ONLY_OK forbidden=0" if not found_forbidden else
        "CATALOG_METADATA_ONLY_FORBIDDEN tokens=%s" % found_forbidden,
    )

    publish_tokens = (
        "Asset.PackageName",
        "ReportedPackageNames.Sort",
        "ReportedCount = ReportedPackageNames.Num()",
        "FCatalogReaderReportBridge::Publish(this)",
    )
    publish_ok, publish_missing = _has_all(code, publish_tokens)
    results[CHECK_IDS[3]] = _check(
        CHECK_IDS[3],
        publish_ok,
        "CATALOG_SORTED_PUBLICATION_OK bridge=protected" if publish_ok else
        "CATALOG_SORTED_PUBLICATION_MISSING tokens=%s" % publish_missing,
    )
    return [results[check_id] for check_id in CHECK_IDS]


def main() -> None:
    try:
        checks = _run()
    except Exception as exc:  # noqa: BLE001
        checks = [_check(check_id, False, "CATALOG_INTROSPECT_ABORTED %r" % (exc,))
                  for check_id in CHECK_IDS]
    _emit(checks)


if __name__ == "__main__":
    main()
