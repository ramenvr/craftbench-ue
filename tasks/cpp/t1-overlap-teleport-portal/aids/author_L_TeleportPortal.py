# Authoring provenance for Content/Maps/t1-overlap-teleport-portal/L_TeleportPortal.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that will produce it — NOT a runner fallback. Re-run only to
# re-author.)
#
# Run against the ThirdPerson substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene contract (mirrors ../notes.md "Map contract" — keep the two in sync):
# a 3,600 x 3,000 flat floor (engine basic cube, scaled), the portal scaffold
# at (1400, 0, 122), the inert destination marker at its AUTHORED spot
# (3200, 900, 90) — the fixture MOVES it to the fixture-chosen spot before
# play — the L2 fixture actor, and WorldSettings GameModeOverride =
# GameModeBase (keeps the stock BP_ThirdPersonGameMode mannequin stack out of
# the headless run). NO PlayerStart: the fixture spawns and possesses its own
# walker.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t1-overlap-teleport-portal"
MAP_NAME = "L_TeleportPortal"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

FLOOR_LABEL = "PortalFloor"
# Engine basic cube is 100uu; scale (36, 30, 1) -> 3,600 x 3,000 x 100.
FLOOR_SCALE = unreal.Vector(36.0, 30.0, 1.0)
# Center at (1800, 0), top face at Z=+2: spans X [0, 3600], Y [-1500, 1500].
FLOOR_LOCATION = unreal.Vector(1800.0, 0.0, -48.0)

PORTAL_LOCATION = unreal.Vector(1400.0, 0.0, 122.0)
MARKER_LOCATION = unreal.Vector(3200.0, 900.0, 90.0)   # the AUTHORED spot
FIXTURE_LOCATION = unreal.Vector(0.0, 400.0, 120.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t1-teleport] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

portal_cls = unreal.load_class(None, "/Script/ThirdPerson.TeleportPortalActor")
marker_cls = unreal.load_class(None, "/Script/ThirdPerson.TeleportDestinationMarker")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.TeleportPortalFunctionalTest")
gm_cls = unreal.load_class(None, "/Script/Engine.GameModeBase")
if portal_cls is None or marker_cls is None or fixture_cls is None or gm_cls is None:
    raise RuntimeError("task classes not found — build ThirdPersonEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    cls_name = actor.get_class().get_name()
    if cls_name in ("TeleportPortalActor", "TeleportDestinationMarker",
                    "TeleportPortalFunctionalTest", "PlayerStart"):
        eas.destroy_actor(actor)
    elif actor.get_actor_label() == FLOOR_LABEL:
        eas.destroy_actor(actor)

floor = eas.spawn_actor_from_class(unreal.StaticMeshActor, FLOOR_LOCATION)
if floor is None:
    raise RuntimeError("floor spawn failed")
floor.set_actor_label(FLOOR_LABEL)
cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
if cube is None:
    raise RuntimeError("engine basic cube not found")
smc = floor.static_mesh_component
smc.set_editor_property("static_mesh", cube)
smc.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
floor.set_actor_scale3d(FLOOR_SCALE)

portal = eas.spawn_actor_from_class(portal_cls, PORTAL_LOCATION)
if portal is None:
    raise RuntimeError("portal spawn failed")

marker = eas.spawn_actor_from_class(marker_cls, MARKER_LOCATION)
if marker is None:
    raise RuntimeError("marker spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

# GameModeOverride: plain GameModeBase — no PlayerStart is placed, so its
# default pawn spawns at the world origin, off the walker's lane and >1,300uu
# from the portal (see ../notes.md calibration item 6).
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world_settings = unreal.GameplayStatics.get_actor_of_class(world, unreal.WorldSettings)
if world_settings is None:
    raise RuntimeError("WorldSettings not found")
world_settings.set_editor_property("default_game_mode", gm_cls)

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[t1-teleport] authored + saved {MAP_OBJECT_PATH} "
    f"(floor={floor.get_name()}, portal={portal.get_name()}, "
    f"marker={marker.get_name()}, fixture={fixture.get_name()}, gm={gm_cls.get_name()})")
