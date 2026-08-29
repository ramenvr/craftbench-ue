# Authoring provenance for Content/Maps/t2-timeline-color-cycle/L_ColorCycle.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produces it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: one placed AColorCycleActor (tagged ColorCycle by its constructor;
# the scaffold ships its own visible cube) and the L2 fixture actor. No
# PlayerStart, no GameMode: nothing is possessed. Placement is cosmetic — the
# fixture reads a material parameter, not world geometry.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-timeline-color-cycle"
MAP_NAME = "L_ColorCycle"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

DISPLAY_LOCATION = unreal.Vector(0.0, 0.0, 120.0)
FIXTURE_LOCATION = unreal.Vector(0.0, 400.0, 120.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t2-colorcycle] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

display_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.ColorCycleActor")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.ColorCycleFunctionalTest")
if display_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("ColorCycleActor", "ColorCycleFunctionalTest"):
        eas.destroy_actor(actor)

display = eas.spawn_actor_from_class(display_cls, DISPLAY_LOCATION)
if display is None:
    raise RuntimeError("display actor spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[t2-colorcycle] authored + saved {MAP_OBJECT_PATH} "
    f"(display={display.get_name()}, fixture={fixture.get_name()})")
