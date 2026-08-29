# Authoring provenance for
# Content/Maps/t1-extraction-volume-per-actor-trigger/L_ExtractionVolume.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produces it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: one placed AExtractionZoneActor (tagged ExtractionZone by its own
# constructor, unscaled — the fixture's entry offsets assume the constructor's
# 200x200x100 half-extent) and the L2 fixture actor placed well clear of the
# zone. No PlayerStart, no GameMode: the fixture spawns its own probe actors.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t1-extraction-volume-per-actor-trigger"
MAP_NAME = "L_ExtractionVolume"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

# Z=200 is LOAD-BEARING, not cosmetic: the zone's detection box (half-extent
# 100) spans Z 100..300, so it can never contain the WORLD ORIGIN. Components
# that register before being positioned momentarily exist at the origin; a
# grounded zone containing (0,0,0) would phantom-overlap them during
# PrepareTest and fail the REFERENCE at cp0 (see ../notes.md calibration
# checklist, origin-coupling item). The zone free-floats; probes teleport in.
ZONE_LOCATION = unreal.Vector(0.0, 0.0, 200.0)
FIXTURE_LOCATION = unreal.Vector(0.0, 1200.0, 200.0)  # well clear of the zone box

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[extraction] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

zone_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.ExtractionZoneActor")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.ExtractionVolumeFunctionalTest")
if zone_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("ExtractionZoneActor", "ExtractionVolumeFunctionalTest"):
        eas.destroy_actor(actor)

zone = eas.spawn_actor_from_class(zone_cls, ZONE_LOCATION)
if zone is None:
    raise RuntimeError("zone spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[extraction] authored + saved {MAP_OBJECT_PATH} "
    f"(zone={zone.get_name()}, fixture={fixture.get_name()})")
