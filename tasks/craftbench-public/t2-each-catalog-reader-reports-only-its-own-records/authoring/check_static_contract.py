"""Fail-closed static boundary for the genuine ThirdPerson catalog port."""

from pathlib import Path


TASK_ID = "t2-each-catalog-reader-reports-only-its-own-records"
HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = TASK.parents[2]
RUNTIME = REPO / "UE-projects/ThirdPerson/Source/ThirdPerson/Tasks" / TASK_ID
TESTS = REPO / "UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks" / TASK_ID
REFERENCE = TASK / "reference/Source/ThirdPerson/Tasks" / TASK_ID


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"CATALOG-PORT-STATIC missing={path}")
    return path.read_text(encoding="utf-8")


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise RuntimeError("CATALOG-PORT-STATIC " + detail)


def main() -> None:
    required = (
        RUNTIME / "CatalogReaderActor.h",
        RUNTIME / "CatalogReaderActor.cpp",
        RUNTIME / "CatalogRecordTypes.h",
        RUNTIME / "CatalogRecordTypes.cpp",
        TESTS / "CatalogReadersFunctionalTest.h",
        TESTS / "CatalogReadersFunctionalTest.cpp",
        TESTS / "CatalogReaderAuthoringLibrary.h",
        TESTS / "CatalogReaderAuthoringLibrary.cpp",
        REFERENCE / "CatalogReaderActor.h",
        REFERENCE / "CatalogReaderActor.cpp",
        HERE / "author_assets.py",
        HERE / "author_map_common.py",
        HERE / "author_admission_map.py",
        HERE / "author_final_map.py",
        HERE / "introspect_catalog.py",
    )
    texts = {path: read(path) for path in required}
    combined = "\n".join(texts.values())
    require("CraftBenchTemplate" not in combined, "old-substrate-token")
    require("CRAFTBENCHTEMPLATE_API" not in combined, "old-export-macro")
    require("/Script/ThirdPerson.CatalogReaderActor" in texts[HERE / "author_map_common.py"],
            "reader-class-not-thirdperson")
    require("THIRDPERSON_API" in texts[RUNTIME / "CatalogReaderActor.h"],
            "runtime-export-not-thirdperson")
    require("THIRDPERSON_API" in texts[REFERENCE / "CatalogReaderActor.h"],
            "reference-export-not-thirdperson")
    fixture = texts[TESTS / "CatalogReadersFunctionalTest.cpp"]
    for token in (
        "CR-1 exact_actor_scoped_metadata_reports",
        "CR-2 all_examined_packages_remain_unloaded",
        "CR-3 one_beginplay_report_per_instance",
        "FCatalogReaderReportBridge::AddListener",
        "SnapshotPublications",
    ):
        require(token in fixture, "missing-fixture-token=" + token)
    for forbidden in ("GLog->AddOutputDevice", "ReportInvocationCount"):
        require(forbidden not in fixture, "forbidden-fixture-token=" + forbidden)
    print("CATALOG-PORT-STATIC PASS runtime=4 verifier=4 scripts=5 reference=2")


if __name__ == "__main__":
    main()
