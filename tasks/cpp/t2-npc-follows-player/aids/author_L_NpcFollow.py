# Authoring provenance for Content/Maps/t2-npc-follows-player/L_NpcFollow.umap
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
# a 4,000 x 2,000 flat floor (engine basic cube, scaled), a PlayerStart at the
# origin end, the enemy scaffold placed ~1,615uu away, the L2 fixture actor
# off both walk lanes, WorldSettings GameModeOverride = AFollowGameMode
# (spawns/possesses the "FollowHero"-tagged player at the PlayerStart), and —
# LOAD-BEARING — the runtime-navmesh trio: a NavMeshBoundsVolume covering the
# floor + a RecastNavMesh with runtime_generation=DYNAMIC. This is the
# 2026-07-30 wave-3 spike recipe verbatim: it produced working nav data in
# headless PIE with no editor bake (MoveToActor arrived, 2000uu -> 0). A map
# missing the volume or with default (static) generation has NO navmesh in
# the graded world and the reference FAILS.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-npc-follows-player"
MAP_NAME = "L_NpcFollow"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

FLOOR_LABEL = "FollowFloor"
# Engine basic cube is 100uu; scale (40, 20, 1) -> 4,000 x 2,000 x 100.
FLOOR_SCALE = unreal.Vector(40.0, 20.0, 1.0)
# Center at (1200, 0), top face at Z=+2: spans X [-800, 3200], Y [-1000, 1000].
FLOOR_LOCATION = unreal.Vector(1200.0, 0.0, -48.0)

NPC_LOCATION = unreal.Vector(1500.0, 600.0, 110.0)   # ~1,615uu from PlayerStart
FIXTURE_LOCATION = unreal.Vector(-400.0, -400.0, 120.0)
# Default volume brush is a 200uu cube; scale (25, 15, 5) -> 5,000 x 3,000 x
# 1,000 centered over the floor.
NAV_VOLUME_LOCATION = unreal.Vector(1200.0, 0.0, 200.0)
NAV_VOLUME_SCALE = unreal.Vector(25.0, 15.0, 5.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t2-npcfollow] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

npc_cls = unreal.load_class(None, "/Script/ThirdPerson.ChaserNpcCharacter")
gm_cls = unreal.load_class(None, "/Script/ThirdPerson.FollowGameMode")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.NpcFollowFunctionalTest")
if npc_cls is None or gm_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build ThirdPersonEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    cls_name = actor.get_class().get_name()
    if cls_name in ("ChaserNpcCharacter", "NpcFollowFunctionalTest", "PlayerStart",
                    "NavMeshBoundsVolume", "RecastNavMesh"):
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

start = eas.spawn_actor_from_class(
    unreal.PlayerStart, unreal.Vector(0.0, 0.0, 120.0), unreal.Rotator(0.0, 0.0, 0.0))
if start is None:
    raise RuntimeError("PlayerStart spawn failed")

npc = eas.spawn_actor_from_class(npc_cls, NPC_LOCATION)
if npc is None:
    raise RuntimeError("enemy scaffold spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

# LOAD-BEARING nav trio (spike recipe): bounds volume + dynamic RecastNavMesh.
nav_volume = eas.spawn_actor_from_class(unreal.NavMeshBoundsVolume, NAV_VOLUME_LOCATION)
if nav_volume is None:
    raise RuntimeError("NavMeshBoundsVolume spawn failed")
nav_volume.set_actor_scale3d(NAV_VOLUME_SCALE)

recast = eas.spawn_actor_from_class(unreal.RecastNavMesh, unreal.Vector(0.0, 0.0, 0.0))
if recast is None:
    raise RuntimeError("RecastNavMesh spawn failed")
recast.set_editor_property("runtime_generation", unreal.RuntimeGenerationType.DYNAMIC)

# GameModeOverride: spawn/possess the task's tagged player character.
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world_settings = unreal.GameplayStatics.get_actor_of_class(world, unreal.WorldSettings)
if world_settings is None:
    raise RuntimeError("WorldSettings not found")
world_settings.set_editor_property("default_game_mode", gm_cls)

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[t2-npcfollow] authored + saved {MAP_OBJECT_PATH} "
    f"(floor={floor.get_name()}, start={start.get_name()}, npc={npc.get_name()}, "
    f"fixture={fixture.get_name()}, navvol={nav_volume.get_name()}, "
    f"recast={recast.get_name()}, gm={gm_cls.get_name()})")
