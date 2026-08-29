# Authoring provenance for Content/Maps/gp-dot-aoe-burn/L_AoeBurn.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produced it - NOT a runner fallback. Re-run only to re-author.)
#
# Shape copied from tasks/bp-g2/gp-double-jump-stamina-cpp/aids/
# author_L_DoubleJump.py, the proven recipe on this substrate. Only the map
# path and the fixture class differ.
#
# PREREQUISITE: ThirdPersonEditor must be BUILT first, or
# /Script/CraftBenchTests.AoeBurnFunctionalTest does not exist yet and
# load_class returns None.
#
# Run against the ThirdPerson substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# WHY ONLY ONE PLACED ACTOR: pawn-shaped family — the fixture resolves, spawns
# and possesses the graded pawn itself, AND spawns its three verifier-owned
# targets itself (PIN §3), so the map places NOTHING but the fixture. The
# Template_Default floor is cosmetic here (movement-independent family; the
# pawn and targets stand on it for the film strip, nothing gates on motion).
# The farthest target spawns 3000 uu out — comfortably inside the template
# floor, which spans ~50 m from the origin.

import unreal

MAP_PACKAGE_PATH = "/Game/Maps/gp-dot-aoe-burn"
MAP_NAME = "L_AoeBurn"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"
FIXTURE_CLASS_PATH = "/Script/CraftBenchTests.AoeBurnFunctionalTest"
FIXTURE_CLASS_NAME = "AoeBurnFunctionalTest"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[aoeburn] map exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not) and the
    # floor everyone stands on.
    if not les.new_level_from_template(MAP_OBJECT_PATH,
                                       "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

fixture_cls = unreal.load_class(None, FIXTURE_CLASS_PATH)
if fixture_cls is None:
    raise RuntimeError(
        f"{FIXTURE_CLASS_PATH} not found - build ThirdPersonEditor first")

for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() == FIXTURE_CLASS_NAME:
        eas.destroy_actor(actor)

fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 0.0, 120.0))
if fixture is None:
    raise RuntimeError("fixture spawn failed")

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(f"[aoeburn] authored + saved {MAP_OBJECT_PATH} (fixture={fixture.get_name()})")
