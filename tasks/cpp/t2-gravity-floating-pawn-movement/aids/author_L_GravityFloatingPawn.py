# Authoring provenance for
# Content/Maps/t2-gravity-floating-pawn-movement/L_GravityFloatingPawn.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produces it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: one placed AHoverPawn (tagged HoverPawn by its own constructor) HIGH
# in clear air, and the L2 fixture actor placed well clear laterally. No
# PlayerStart, no GameMode: the fixture possesses the placed pawn itself.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-gravity-floating-pawn-movement"
MAP_NAME = "L_GravityFloatingPawn"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

# Z=6000 is LOAD-BEARING, not cosmetic: the pawn needs clear air below through
# the whole run. The prompt-disclosed sink band caps the descent rate at
# 800 uu/s, so the worst-case total sink over the 6.5s schedule is 5,200 uu —
# from 6,000 the pawn ends no lower than Z~800, well above the template floor
# at Z~0 (see ../notes.md map contract + calibration item 6).
PAWN_LOCATION = unreal.Vector(0.0, 0.0, 6000.0)
FIXTURE_LOCATION = unreal.Vector(0.0, 1200.0, 6000.0)  # well clear laterally

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[gravpawn] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

pawn_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.HoverPawn")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.GravityFloatingPawnFunctionalTest")
if pawn_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("HoverPawn", "GravityFloatingPawnFunctionalTest"):
        eas.destroy_actor(actor)

pawn = eas.spawn_actor_from_class(pawn_cls, PAWN_LOCATION)
if pawn is None:
    raise RuntimeError("HoverPawn spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[gravpawn] authored + saved {MAP_OBJECT_PATH} "
    f"(pawn={pawn.get_name()}, fixture={fixture.get_name()})")
