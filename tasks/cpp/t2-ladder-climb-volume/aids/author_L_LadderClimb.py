# Authoring provenance for Content/Maps/t2-ladder-climb-volume/L_LadderClimb.umap
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
# a 3,000 x 2,000 flat floor (engine basic cube, scaled), a PlayerStart at the
# origin end facing +X, the ladder volume scaffold standing on the floor at
# X=600 (its ctor box spans Z [0,1200] from this placement), the L2 fixture
# actor off the walk lane, and WorldSettings GameModeOverride = ALadderGameMode
# (spawns/possesses the "ClimbHero"-tagged ALadderCharacter at the PlayerStart).
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-ladder-climb-volume"
MAP_NAME = "L_LadderClimb"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

FLOOR_LABEL = "LadderFloor"
# Engine basic cube is 100uu; scale (30, 20, 1) -> 3,000 x 2,000 x 100.
FLOOR_SCALE = unreal.Vector(30.0, 20.0, 1.0)
# Center at (300, 0), top face at Z=+2: spans X [-1200, 1800].
FLOOR_LOCATION = unreal.Vector(300.0, 0.0, -48.0)

# Volume ctor half-extent is (60, 60, 600); placed at Z=600 the box spans
# Z [0, 1200] — bottom at floor level, top at 1200 (the fixture reads these
# bounds in PrepareTest; ../notes.md map contract).
LADDER_LOCATION = unreal.Vector(600.0, 0.0, 600.0)
FIXTURE_LOCATION = unreal.Vector(0.0, 400.0, 120.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t2-ladder] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

ladder_cls = unreal.load_class(None, "/Script/ThirdPerson.LadderVolumeActor")
gm_cls = unreal.load_class(None, "/Script/ThirdPerson.LadderGameMode")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.LadderClimbFunctionalTest")
if ladder_cls is None or gm_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build ThirdPersonEditor first")

# Idempotence: clear any prior instances before placing fresh ones. PlayerStart
# is re-placed too so its transform is exactly the contract above.
for actor in list(eas.get_all_level_actors()):
    cls_name = actor.get_class().get_name()
    if cls_name in ("LadderVolumeActor", "LadderClimbFunctionalTest", "PlayerStart"):
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

# PlayerStart at the origin end, yaw 0: controller-forward == +X == the walk
# lane toward the ladder. Z=120: the spawned capsule settles onto the floor
# top well before the first checkpoint at t=0.6.
start = eas.spawn_actor_from_class(
    unreal.PlayerStart, unreal.Vector(0.0, 0.0, 120.0), unreal.Rotator(0.0, 0.0, 0.0))
if start is None:
    raise RuntimeError("PlayerStart spawn failed")

ladder = eas.spawn_actor_from_class(ladder_cls, LADDER_LOCATION)
if ladder is None:
    raise RuntimeError("ladder volume spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
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
    f"[t2-ladder] authored + saved {MAP_OBJECT_PATH} "
    f"(floor={floor.get_name()}, start={start.get_name()}, ladder={ladder.get_name()}, "
    f"fixture={fixture.get_name()}, gm={gm_cls.get_name()})")
