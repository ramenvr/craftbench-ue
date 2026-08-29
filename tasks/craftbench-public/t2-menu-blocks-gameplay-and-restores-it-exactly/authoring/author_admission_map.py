"""Fail-closed real-RHI authoring of L_MenuInputRouting.

Run only after ``author_admission_assets.py`` and a green Editor build. The
script never overwrites an existing exact map.
"""
import unreal


TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
MAP_PATH = "/Game/Maps/%s/L_MenuInputRouting" % TASK_ID
MAP_TEMPLATE = "/Game/ThirdPerson/Lvl_ThirdPerson"
TASK_ROOT = "/Game/Tasks/%s" % TASK_ID
SUPPORT_ROOT = "/Game/Maps/%s/Support" % TASK_ID
GAME_MODE_PATH = (
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
    "BP_ThirdPersonGameMode_C")
PAWN_PATH = (
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter."
    "BP_ThirdPersonCharacter_C")
CONTROLLER_PATH = (
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController."
    "BP_ThirdPersonPlayerController_C")

REQUIRED_ASSETS = (
    "%s/WBP_InputBlockingMenu" % TASK_ROOT,
    "%s/IA_GameplayProbe" % SUPPORT_ROOT,
    "%s/IA_MenuProbe" % SUPPORT_ROOT,
    "%s/IA_UnrelatedProbe" % SUPPORT_ROOT,
) + tuple(
    "%s/IMC_%s%s" % (SUPPORT_ROOT, family, leg)
    for leg in ("Quartz", "Violet")
    for family in ("Gameplay", "Menu", "Unrelated")
)

PLACEMENTS = (
    ("/Script/ThirdPerson.MenuInputPolicy", "MenuInputPolicy", (420.0, -180.0, 160.0)),
    ("/Script/ThirdPerson.MenuInputHost", "MenuInputHost", (420.0, 0.0, 160.0)),
    ("/Script/CraftBenchTests.MenuInputFunctionalTest", "MenuInputFunctionalTest", (420.0, 180.0, 160.0)),
    ("/Script/CraftBenchTests.MenuInputAdmissionFunctionalTest", "MenuInputAdmissionFunctionalTest", (420.0, 360.0, 160.0)),
)


def die(message):
    unreal.log_error("MENU-INPUT-MAP-ERROR %s" % message)
    raise RuntimeError(message)


def subsystem(class_name):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        die("editor subsystem class unavailable: %s" % class_name)
    value = unreal.get_editor_subsystem(cls)
    if value is None:
        die("editor subsystem unavailable: %s" % class_name)
    return value


def load_class(path):
    cls = unreal.load_class(None, path)
    if cls is None:
        die("class unavailable: %s" % path)
    return cls


def spawn(actor_subsystem, class_path, label, location):
    actor = actor_subsystem.spawn_actor_from_class(
        load_class(class_path), unreal.Vector(*location), unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        die("spawn returned None: %s" % class_path)
    actor.set_actor_label(label)
    if actor.get_actor_label() != label:
        die("label readback failed: %s" % label)
    return actor


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        die("exact output map already exists: %s" % MAP_PATH)
    missing = [path for path in REQUIRED_ASSETS
               if not unreal.EditorAssetLibrary.does_asset_exist(path)]
    if missing:
        die("required authored assets missing: %s" % missing)

    levels = subsystem("LevelEditorSubsystem")
    actors = subsystem("EditorActorSubsystem")
    if not levels.new_level_from_template(MAP_PATH, MAP_TEMPLATE):
        die("new_level_from_template failed")

    game_mode = load_class(GAME_MODE_PATH)
    world = subsystem("UnrealEditorSubsystem").get_editor_world()
    if world is None:
        die("editor world unavailable after map creation")
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", game_mode)

    placed = [spawn(actors, *placement) for placement in PLACEMENTS]
    if len(placed) != 4:
        die("placement cardinality mismatch")
    if not levels.save_current_level():
        die("save_current_level failed")

    live = list(actors.get_all_level_actors())
    labels = [actor.get_actor_label() for actor in live]
    for _, label, _ in PLACEMENTS:
        if labels.count(label) != 1:
            die("exact actor label cardinality failed: %s count=%d" %
                (label, labels.count(label)))
    player_starts = [actor for actor in live if isinstance(actor, unreal.PlayerStart)]
    if len(player_starts) != 1:
        die("expected exact one PlayerStart; found %d" % len(player_starts))
    if settings.get_editor_property("default_game_mode") != game_mode:
        die("exact Third Person game mode readback failed")
    game_mode_cdo = unreal.get_default_object(game_mode)
    pawn_class = game_mode_cdo.get_editor_property("default_pawn_class")
    controller_class = game_mode_cdo.get_editor_property("player_controller_class")
    if pawn_class is None or pawn_class.get_path_name() != PAWN_PATH:
        die("game mode does not use exact visible Third Person pawn")
    if controller_class is None or controller_class.get_path_name() != CONTROLLER_PATH:
        die("game mode does not use exact Third Person PlayerController")
    pawn_cdo = unreal.get_default_object(pawn_class)
    missing_actions = []
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if pawn_cdo.get_editor_property(prop) is None:
                missing_actions.append(prop)
        except Exception:  # noqa: BLE001
            missing_actions.append(prop)
    mesh = pawn_cdo.get_editor_property("mesh")
    if missing_actions or mesh is None or mesh.get_editor_property("skeletal_mesh_asset") is None:
        die("playable character contract failed actions=%s mesh=%s" %
            (missing_actions, mesh))
    if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        die("saved map missing from asset registry")

    marker = (
        "MENU-INPUT-MAP-SAVED hosts=1 policies=1 final_fixtures=1 "
        "admission_fixtures=1 player_starts=1 playable=1")
    unreal.log(marker)
    print(marker)


if __name__ == "__main__":
    main()
