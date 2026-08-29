# Authoring provenance for Content/Maps/gp-health-attribute-ops/L_HealthOps.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produced it — NOT a runner fallback. Re-run only to re-author.)
#
# Shape copied from tasks/cpp/tp0-sanity-log-on-beginplay/aids/
# author_L_TpSanity.py, which is the proven recipe on this substrate.
#
# PREREQUISITE: ThirdPersonEditor must be BUILT first, or
# /Script/CraftBenchTests.HealthAttributeOpsFunctionalTest does not exist yet
# and load_class returns None.
#
# Run against the ThirdPerson substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi — EditorActorSubsystem.spawn_actor_from_class
# asserts without a renderer):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# WHY ONLY ONE PLACED ACTOR: this task is pawn-shaped. The fixture derives
# ACraftBenchPawnFunctionalTest, which RESOLVES the agent's pawn class, then
# spawns and possesses it itself — so the map must not place a pawn, exactly as
# L_PoisonStack and L_GlideStamina do not. Template_Default supplies the
# WorldSettings and a floor; the floor matters only so a human reviewing the
# film strip sees the mannequin stand rather than fall out of the world (the
# health gates are movement-independent).
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/gp-health-attribute-ops"
MAP_NAME = "L_HealthOps"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"
FIXTURE_CLASS_PATH = "/Script/CraftBenchTests.HealthAttributeOpsFunctionalTest"
FIXTURE_CLASS_NAME = "HealthAttributeOpsFunctionalTest"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[healthops] map exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not).
    if not les.new_level_from_template(MAP_OBJECT_PATH,
                                       "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

fixture_cls = unreal.load_class(None, FIXTURE_CLASS_PATH)
if fixture_cls is None:
    raise RuntimeError(
        f"{FIXTURE_CLASS_PATH} not found - build ThirdPersonEditor first")

# Idempotence: clear any prior instance before placing a fresh one.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() == FIXTURE_CLASS_NAME:
        eas.destroy_actor(actor)

fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 0.0, 120.0))
if fixture is None:
    raise RuntimeError("fixture spawn failed")

# NO GameModeOverride on purpose. PIE will also spawn the substrate's default
# BP_ThirdPersonGameMode pawn at the PlayerStart; it is not an
# ACraftBenchCharacter subclass, so it can never win pawn resolution and no gate
# reads it — the graded pawn is exclusively the one the fixture spawns. Same
# invariant L_PoisonStack and L_GlideStamina rely on (see either task.md's
# Hidden invariants).

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(f"[healthops] authored + saved {MAP_OBJECT_PATH} (fixture={fixture.get_name()})")
