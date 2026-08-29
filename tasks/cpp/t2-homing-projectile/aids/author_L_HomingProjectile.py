# Authoring provenance for Content/Maps/t2-homing-projectile/L_HomingProjectile.umap
# (committed binary is the ONLY map source; this one-shot recipe produced it).
#
# Run against the CraftBenchTemplate substrate with a REAL off-screen RHI:
#   UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/t2-homing-projectile"
MAP_NAME = "L_HomingProjectile"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[t2-homing] map exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    if not les.new_level_from_template(MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

launcher_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.MissileLauncherActor")
target_cls = unreal.load_class(None, "/Script/CraftBenchTemplate.MissileTargetActor")
fixture_cls = unreal.load_class(None, "/Script/CraftBenchTests.HomingProjectileFunctionalTest")
if None in (launcher_cls, target_cls, fixture_cls):
    raise RuntimeError("task classes not found — build CraftBenchTemplateEditor first")

for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() in ("MissileLauncherActor", "MissileTargetActor",
                                        "HomingProjectileFunctionalTest"):
        eas.destroy_actor(actor)

# Launcher off-origin; target 2000 units +X; both at flight height 300.
launcher = eas.spawn_actor_from_class(launcher_cls, unreal.Vector(300.0, 200.0, 300.0))
target = eas.spawn_actor_from_class(target_cls, unreal.Vector(2300.0, 200.0, 300.0))
fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 0.0, 300.0))
if None in (launcher, target, fixture):
    raise RuntimeError("spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(f"[t2-homing] authored + saved {MAP_OBJECT_PATH}")
