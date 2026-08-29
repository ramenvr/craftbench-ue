"""Shared, task-local map authoring for the catalog-reader task."""

import unreal


TASK_ID = "t2-each-catalog-reader-reports-only-its-own-records"
TEMPLATE_MAP = "/Engine/Maps/Templates/Template_Default"
READER_CLASS = "/Script/ThirdPerson.CatalogReaderActor"
FIXTURE_CLASS = "/Script/CraftBenchTests.CatalogReadersFunctionalTest"


def fail(message):
    unreal.log_error("CATALOG-MAP-AUTHOR ERROR " + message)
    raise RuntimeError(message)


def load_class(path):
    value = unreal.load_class(None, path)
    if value is None:
        fail("class unavailable: " + path)
    return value


def spawn(eas, actor_class, location, label):
    actor = eas.spawn_actor_from_class(actor_class, location, unreal.Rotator())
    if actor is None:
        fail("could not spawn " + label)
    actor.set_actor_label(label)
    return actor


def set_exact_tags(actor, tags):
    actor.set_editor_property("tags", [unreal.Name(value) for value in tags])


def tagged(actors, tag):
    return [actor for actor in actors if actor.actor_has_tag(tag)]


def author_map(map_package, fixture_label):
    if unreal.EditorAssetLibrary.does_asset_exist(map_package):
        fail("refusing to overwrite protected map: " + map_package)

    helper = getattr(unreal, "CatalogReaderAuthoringLibrary", None)
    if helper is None:
        fail("CatalogReaderAuthoringLibrary is unavailable")
    catalog_pre = str(helper.inspect_protected_catalog())
    if not catalog_pre.startswith("OK CATALOG-READBACK "):
        fail("protected catalog preflight failed: " + catalog_pre)
    if "count=9" not in catalog_pre or "unloaded=9" not in catalog_pre:
        fail("protected catalog preflight lacks exact cold facts: " + catalog_pre)
    unreal.log("CATALOG-MAP-AUTHOR PREFLIGHT " + catalog_pre)

    reader_class = load_class(READER_CLASS)
    fixture_class = load_class(FIXTURE_CLASS)
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if les is None or eas is None:
        fail("required editor subsystem unavailable")
    if not les.new_level_from_template(map_package, TEMPLATE_MAP):
        fail("new_level_from_template failed for " + map_package)

    # Author an exact, minimal actor set. WorldSettings is not returned by
    # get_all_level_actors. The live fixture replaces these serialized decoys
    # before either reader receives BeginPlay.
    for actor in list(eas.get_all_level_actors()):
        eas.destroy_actor(actor)

    reader_a = spawn(
        eas,
        reader_class,
        unreal.Vector(0.0, -250.0, 80.0),
        "CatalogReader_A",
    )
    set_exact_tags(reader_a, ("CatalogReader", "CatalogReader.A"))
    reader_a.set_editor_property("reader_id", unreal.Name("SerializedDecoyA"))
    reader_a.set_editor_property(
        "configured_package_path",
        unreal.Name(f"/Game/Maps/{TASK_ID}/Catalog/Outside"),
    )

    reader_b = spawn(
        eas,
        reader_class,
        unreal.Vector(0.0, 250.0, 80.0),
        "CatalogReader_B",
    )
    set_exact_tags(reader_b, ("CatalogReader", "CatalogReader.B"))
    reader_b.set_editor_property("reader_id", unreal.Name("SerializedDecoyB"))
    reader_b.set_editor_property(
        "configured_package_path",
        unreal.Name(f"/Game/Maps/{TASK_ID}/Catalog/Outside"),
    )

    fixture = spawn(
        eas,
        fixture_class,
        unreal.Vector(-500.0, 0.0, 100.0),
        fixture_label,
    )

    actors = list(eas.get_all_level_actors())
    readers = [actor for actor in actors if actor.get_class() == reader_class]
    fixtures = [actor for actor in actors if actor.get_class() == fixture_class]
    if len(readers) != 2 or len(fixtures) != 1:
        fail(
            "actor cardinality mismatch readers=%d fixtures=%d actors=%d"
            % (len(readers), len(fixtures), len(actors))
        )
    if len(tagged(actors, "CatalogReader")) != 2:
        fail("common reader tag cardinality is not two")
    if len(tagged(actors, "CatalogReader.A")) != 1:
        fail("CatalogReader.A tag cardinality is not one")
    if len(tagged(actors, "CatalogReader.B")) != 1:
        fail("CatalogReader.B tag cardinality is not one")
    if tagged(actors, "CatalogReader.A")[0] == tagged(actors, "CatalogReader.B")[0]:
        fail("specific reader tags resolve to the same actor")

    if not les.save_current_level():
        fail("save_current_level failed for " + map_package)

    catalog_post = str(helper.inspect_protected_catalog())
    if not catalog_post.startswith("OK CATALOG-READBACK "):
        fail("protected catalog post-save readback failed: " + catalog_post)
    if "count=9" not in catalog_post or "unloaded=9" not in catalog_post:
        fail("protected catalog post-save readback lacks exact cold facts: " + catalog_post)
    unreal.log("CATALOG-MAP-AUTHOR POSTSAVE " + catalog_post)
    unreal.log(
        "CATALOG-MAP-AUTHOR SAVED map=%s actors=%d readers=2 fixtures=1 "
        "common_tags=2 specific_tags=2"
        % (map_package, len(actors))
    )
