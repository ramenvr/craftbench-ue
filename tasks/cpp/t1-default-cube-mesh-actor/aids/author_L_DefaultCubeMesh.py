# Authoring provenance for Content/Maps/t1-default-cube-mesh-actor/L_DefaultCubeMesh.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produces it — NOT a runner fallback. Re-run only to re-author.)
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# Scene: one placed ACubeMeshActor (tagged CubeMeshDisplay by its constructor)
# and the L2 fixture actor. Nothing else is needed — the fixture observes the
# placed actor's default state; no PlayerStart, no GameMode override.
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t1-default-cube-mesh-actor"
MAP_NAME = "L_DefaultCubeMesh"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t1-default-cube-mesh-actor] map already exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

host_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.CubeMeshActor")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.DefaultCubeMeshFunctionalTest")
if host_cls is None or fixture_cls is None:
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

# Idempotence: clear any prior instances before placing fresh ones.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("CubeMeshActor", "DefaultCubeMeshFunctionalTest"):
        eas.destroy_actor(actor)

host = eas.spawn_actor_from_class(host_cls, unreal.Vector(0.0, 0.0, 100.0))
if host is None:
    raise RuntimeError("CubeMeshActor spawn failed")

fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 400.0, 100.0))
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(
    f"[t1-default-cube-mesh-actor] authored + saved {MAP_OBJECT_PATH} "
    f"(host={host.get_name()}, fixture={fixture.get_name()})")
