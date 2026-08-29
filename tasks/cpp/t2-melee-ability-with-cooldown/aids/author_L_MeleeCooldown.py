# Authoring provenance for Content/Maps/t2-melee-ability-with-cooldown/L_MeleeCooldown.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produces it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: a floor (the pawn the fixture spawns at (0,0,120) must settle, not
# free-fall), TWO placed AMeleeDummyActors (authored spots are COSMETIC — the
# fixture repositions both relative to the settled pawn at its first
# checkpoint), and the L2 fixture actor. No PlayerStart, no GameMode: the
# fixture base spawns + possesses the agent pawn itself.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-melee-ability-with-cooldown"
MAP_NAME = "L_MeleeCooldown"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

FLOOR_LABEL = "MeleeFloor"
# Engine basic cube is 100uu; scale (30, 30, 1) -> 3,000 x 3,000 x 100.
FLOOR_SCALE = unreal.Vector(30.0, 30.0, 1.0)
# Centered at the origin, top face at Z=+2.
FLOOR_LOCATION = unreal.Vector(0.0, 0.0, -48.0)

# Cosmetic authored spots (the fixture re-places both at runtime).
NEAR_DUMMY_LOCATION = unreal.Vector(300.0, 0.0, 90.0)
FAR_DUMMY_LOCATION = unreal.Vector(900.0, 0.0, 90.0)
FIXTURE_LOCATION = unreal.Vector(0.0, 400.0, 120.0)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t2-melee] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

dummy_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.MeleeDummyActor")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.MeleeCooldownFunctionalTest")
if dummy_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("MeleeDummyActor", "MeleeCooldownFunctionalTest"):
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

near = eas.spawn_actor_from_class(dummy_cls, NEAR_DUMMY_LOCATION)
if near is None:
    raise RuntimeError("near dummy spawn failed")
far = eas.spawn_actor_from_class(dummy_cls, FAR_DUMMY_LOCATION)
if far is None:
    raise RuntimeError("far dummy spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, FIXTURE_LOCATION)
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[t2-melee] authored + saved {MAP_OBJECT_PATH} "
    f"(floor={floor.get_name()}, near={near.get_name()}, far={far.get_name()}, "
    f"fixture={fixture.get_name()})")
