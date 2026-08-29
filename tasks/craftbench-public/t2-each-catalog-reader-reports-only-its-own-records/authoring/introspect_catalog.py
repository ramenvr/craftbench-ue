"""Fixed, verifier-owned cold readback for catalog assets and maps.

Set CRAFTBENCH_CATALOG_INSPECT to assets, admission-map, final-map, or all.
This script never saves a package and never resolves a catalog FAssetData.
"""

import os
import unreal


TASK_ID = "t2-each-catalog-reader-reports-only-its-own-records"
FINAL_MAP = f"/Game/Maps/{TASK_ID}/L_CatalogReaders"
ADMISSION_MAP = f"/Game/__CraftBenchAdmission/{TASK_ID}/L_CatalogReadersAdmission"
READER_CLASS = "CatalogReaderActor"
FIXTURE_CLASS = "CatalogReadersFunctionalTest"


def fail(message):
    unreal.log_error("CATALOG-READBACK ERROR " + message)
    raise RuntimeError(message)


def inspect_catalog():
    helper = getattr(unreal, "CatalogReaderAuthoringLibrary", None)
    if helper is None:
        fail("CatalogReaderAuthoringLibrary is unavailable")
    report = str(helper.inspect_protected_catalog())
    unreal.log("CATALOG-READBACK " + report)
    if not report.startswith("OK CATALOG-READBACK "):
        fail("protected catalog readback failed: " + report)
    if "count=9" not in report or "unloaded=9" not in report:
        fail("protected catalog readback lacks exact count/unloaded facts: " + report)
    return report


def by_tag(actors, tag):
    return [actor for actor in actors if actor.actor_has_tag(tag)]


def inspect_map(map_package):
    # Establish cold residency before loading the map. This call uses only
    # registry metadata and compiled class identities.
    inspect_catalog()
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if les is None or eas is None or not les.load_level(map_package):
        fail("could not cold-load exact map: " + map_package)

    actors = list(eas.get_all_level_actors())
    readers = [actor for actor in actors if actor.get_class().get_name() == READER_CLASS]
    fixtures = [actor for actor in actors if actor.get_class().get_name() == FIXTURE_CLASS]
    if len(actors) != 3 or len(readers) != 2 or len(fixtures) != 1:
        fail(
            "map cardinality mismatch map=%s actors=%d readers=%d fixtures=%d"
            % (map_package, len(actors), len(readers), len(fixtures))
        )
    if len(by_tag(actors, "CatalogReader")) != 2:
        fail("common CatalogReader tag cardinality is not two")
    reader_a = by_tag(actors, "CatalogReader.A")
    reader_b = by_tag(actors, "CatalogReader.B")
    if len(reader_a) != 1 or len(reader_b) != 1 or reader_a[0] == reader_b[0]:
        fail("specific reader tag identity/cardinality mismatch")
    if reader_a[0].get_class().get_name() != READER_CLASS:
        fail("CatalogReader.A is not the supplied reader class")
    if reader_b[0].get_class().get_name() != READER_CLASS:
        fail("CatalogReader.B is not the supplied reader class")

    outside = f"/Game/Maps/{TASK_ID}/Catalog/Outside"
    for reader, expected_id in (
        (reader_a[0], "SerializedDecoyA"),
        (reader_b[0], "SerializedDecoyB"),
    ):
        if str(reader.get_editor_property("reader_id")) != expected_id:
            fail("serialized reader-id decoy mismatch: " + reader.get_path_name())
        if str(reader.get_editor_property("configured_package_path")) != outside:
            fail("serialized path decoy mismatch: " + reader.get_path_name())

    # Loading either map must still leave all nine protected records cold.
    inspect_catalog()
    unreal.log(
        "CATALOG-READBACK MAP PASS map=%s actors=3 readers=2 fixtures=1 "
        "common_tags=2 specific_tags=2 protected_unloaded=9" % map_package
    )


def main():
    mode = os.environ.get("CRAFTBENCH_CATALOG_INSPECT", "all").strip().lower()
    if mode not in ("assets", "admission-map", "final-map", "all"):
        fail("unknown CRAFTBENCH_CATALOG_INSPECT mode: " + mode)
    if mode in ("assets", "all"):
        inspect_catalog()
    if mode in ("admission-map", "all"):
        inspect_map(ADMISSION_MAP)
    if mode in ("final-map", "all"):
        inspect_map(FINAL_MAP)
    unreal.log("CATALOG-READBACK COMPLETE mode=" + mode)


main()
