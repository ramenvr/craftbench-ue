# Authoring provenance for Content/Maps/tp2-sprint-stamina/L_TpSprint.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produced it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the ThirdPerson substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: a 25,000 x 2,000 flat runway along +X (engine basic cube, scaled),
# a PlayerStart at the -X end facing +X, the L2 fixture actor, and the world
# settings' GameModeOverride = ASprintGameMode (which spawns and possesses the
# "SprintHero"-tagged ASprintCharacter). Worst-case compliant run distance is
# ~9,000 units -> ~2.5x runway headroom before the IsFalling guard could trip.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/tp2-sprint-stamina"
MAP_NAME = "L_TpSprint"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

RUNWAY_LABEL = "SprintRunway"
# Engine basic cube is 100uu; scale (250, 20, 1) -> 25,000 x 2,000 x 100.
RUNWAY_SCALE = unreal.Vector(250.0, 20.0, 1.0)
# Center at X=12,000, top face at Z=+2 (2uu above the template floor's top —
# a trivial auto-step up, no coplanar z-fight): spans X in [-500, 24500].
RUNWAY_LOCATION = unreal.Vector(12000.0, 0.0, -48.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[tp2] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

gm_cls = unreal.load_class(None, "/Script/ThirdPerson.SprintGameMode")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.SprintStaminaFunctionalTest")
if gm_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build ThirdPersonEditor first")

# Idempotence: clear any prior instances before placing fresh ones. PlayerStart
# is re-placed too so its transform is exactly the contract below.
for actor in list(eas.get_all_level_actors()):
    cls_name = actor.get_class().get_name()
    if cls_name in ("SprintStaminaFunctionalTest", "PlayerStart"):
        eas.destroy_actor(actor)
    elif actor.get_actor_label() == RUNWAY_LABEL:
        eas.destroy_actor(actor)

runway = eas.spawn_actor_from_class(unreal.StaticMeshActor, RUNWAY_LOCATION)
if runway is None:
    raise RuntimeError("runway spawn failed")
runway.set_actor_label(RUNWAY_LABEL)
cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
if cube is None:
    raise RuntimeError("engine basic cube not found")
smc = runway.static_mesh_component
smc.set_editor_property("static_mesh", cube)
smc.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
runway.set_actor_scale3d(RUNWAY_SCALE)

# PlayerStart near the -X end, yaw 0: controller-forward == +X == runway axis.
# Z=120: the spawned capsule settles onto the runway top well before the first
# checkpoint at t=1.0.
start = eas.spawn_actor_from_class(
    unreal.PlayerStart, unreal.Vector(0.0, 0.0, 120.0), unreal.Rotator(0.0, 0.0, 0.0))
if start is None:
    raise RuntimeError("PlayerStart spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 400.0, 120.0))
if fixture is None:
    raise RuntimeError("fixture spawn failed")

# GameModeOverride: spawn/possess the task's tagged character instead of the
# global BP_ThirdPersonGameMode mannequin stack (lighter under -nullrhi).
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world_settings = unreal.GameplayStatics.get_actor_of_class(world, unreal.WorldSettings)
if world_settings is None:
    raise RuntimeError("WorldSettings not found")
world_settings.set_editor_property("default_game_mode", gm_cls)

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[tp2] authored + saved {MAP_OBJECT_PATH} "
    f"(runway={runway.get_name()}, start={start.get_name()}, fixture={fixture.get_name()}, gm={gm_cls.get_name()})")
