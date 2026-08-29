"""Deterministic retained/admission map authoring for Guard Visible Aim."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import unreal

from guard_aim_common import (
    ADMISSION_ANIM, ADMISSION_MAP, FINAL_ANIM, FINAL_MAP, REFERENCE, disk,
    sha256, snapshot,
)


TEMPLATE = "/Engine/Maps/Templates/Template_Default"


@dataclass(frozen=True)
class Scenario:
    suffix: str
    origin: tuple[float, float]
    target_offset: tuple[float, float, float]
    decoy_offset: tuple[float, float, float]
    yaw_sign: float
    pitch_sign: float


FINAL_SCENARIOS = (
    Scenario("LeftHigh", (-3500.0, -300.0), (1300.0, -700.0, 260.0),
             (1050.0, 150.0, 120.0), -1.0, 1.0),
    # Keep the sight trace endpoint above the floor while retaining a clear
    # positive yaw and greater-than-four-degree downward aim after the guard's
    # first movement phase.
    Scenario("RightLow", (3500.0, 300.0), (1150.0, 400.0, 25.0),
             (1050.0, -150.0, 120.0), 1.0, -1.0),
)
ADMISSION_SCENARIOS = (
    Scenario("Admission", (0.0, 0.0), (1280.0, -660.0, 245.0),
             (1040.0, 145.0, 120.0), -1.0, 1.0),
)


def fail(message):
    unreal.log_error("GUARD-AIM-MAP-FAILED: " + message)
    raise RuntimeError(message)


def vec(origin, offset):
    return unreal.Vector(origin[0] + offset[0], origin[1] + offset[1], offset[2])


def midpoint(left, right):
    return unreal.Vector((left.x + right.x) * 0.5,
                         (left.y + right.y) * 0.5,
                         (left.z + right.z) * 0.5)


def spawn(subsystem, cls, location, label, rotation=None):
    actor = subsystem.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def tag(actor, *values):
    actor.set_editor_property("tags", [unreal.Name(value) for value in values])


def author(mode):
    if mode not in ("admission", "final"):
        fail("unsupported mode=" + mode)
    map_path = ADMISSION_MAP if mode == "admission" else FINAL_MAP
    anim_path = ADMISSION_ANIM if mode == "admission" else FINAL_ANIM
    scenarios = ADMISSION_SCENARIOS if mode == "admission" else FINAL_SCENARIOS
    map_file = disk(map_path, ".umap")
    protected = {
        "anim": disk(anim_path, ".uasset"),
        "other_anim": disk(FINAL_ANIM if mode == "admission" else ADMISSION_ANIM,
                           ".uasset"),
        "reference": REFERENCE,
    }
    before = {name: snapshot(path) for name, path in protected.items()}
    if before["anim"].get("kind") != "file":
        fail("required AnimBlueprint absent")
    if unreal.EditorAssetLibrary.does_asset_exist(map_path) or map_file.exists():
        fail("refusing to overwrite map: " + map_path)
    anim = unreal.EditorAssetLibrary.load_asset(anim_path)
    helper = getattr(unreal, "GuardVisibleAimAssetAuthoring", None)
    if anim is None or anim.generated_class() is None or helper is None:
        fail("AnimBlueprint or native helper missing")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(map_path, TEMPLATE):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)
    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "GuardAimFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    # The final RightLow lane ends at X=5900.  Keep both authored lanes well
    # inside the physical floor and navigation bounds instead of relying on a
    # projection from beyond their edge.
    floor.set_actor_scale3d(unreal.Vector(140.0, 55.0, 1.0))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    nav = spawn(actors, unreal.NavMeshBoundsVolume,
                unreal.Vector(0.0, 0.0, 350.0), "GuardAimNavBounds")
    nav.set_actor_scale3d(unreal.Vector(140.0, 55.0, 9.0))
    fixture_classes = {
        "Admission": unreal.GuardVisibleAimAdmissionFunctionalTest,
        "LeftHigh": unreal.GuardVisibleAimLeftHighFunctionalTest,
        "RightLow": unreal.GuardVisibleAimRightLowFunctionalTest,
    }
    for spec in scenarios:
        group = "GuardVisibleAim.Group." + spec.suffix
        main_location = vec(spec.origin, (0.0, 0.0, 96.0))
        control_location = vec(spec.origin, (0.0, 1650.0, 96.0))
        visible_location = vec(spec.origin, spec.target_offset)
        decoy_location = vec(spec.origin, spec.decoy_offset)
        main = spawn(actors, unreal.GuardVisibleAimCharacter, main_location,
                     "GuardAimMain_" + spec.suffix)
        control = spawn(actors, unreal.GuardVisibleAimCharacter, control_location,
                        "GuardAimControl_" + spec.suffix)
        for guard, role in ((main, "Main"), (control, "Control")):
            tag(guard, "GuardVisibleAim.Guard", group,
                "GuardVisibleAim.Guard.%s.%s" % (spec.suffix, role))
            detail = str(helper.configure_guard(guard, anim))
            if not detail.startswith("PASS "):
                fail("guard configure failed: " + detail)
        visible = spawn(actors, unreal.GuardVisibleAimTarget, visible_location,
                        "GuardAimVisible_" + spec.suffix)
        decoy = spawn(actors, unreal.GuardVisibleAimTarget, decoy_location,
                      "GuardAimDecoy_" + spec.suffix)
        tag(visible, "GuardVisibleAim.Target", group,
            "GuardVisibleAim.Target.%s.Visible" % spec.suffix)
        tag(decoy, "GuardVisibleAim.Target", group,
            "GuardVisibleAim.Target.%s.OccludedDecoy" % spec.suffix)
        decoy_wall_location = unreal.Vector(
            main_location.x + (decoy_location.x - main_location.x) * 0.9,
            main_location.y + (decoy_location.y - main_location.y) * 0.9,
            main_location.z + (decoy_location.z - main_location.z) * 0.9)
        decoy_wall = spawn(actors, unreal.GuardVisibleAimOccluder,
                           decoy_wall_location, "GuardAimDecoyWall_" + spec.suffix)
        decoy_wall.set_actor_scale3d(unreal.Vector(0.55, 2.2, 2.8))
        blocked = unreal.Vector(
            main_location.x + (visible_location.x - main_location.x) * 0.8,
            main_location.y + (visible_location.y - main_location.y) * 0.8,
            main_location.z + (visible_location.z - main_location.z) * 0.8)
        opened = vec(spec.origin, (-700.0, -1200.0, 160.0))
        switch = spawn(actors, unreal.GuardVisibleAimOccluder, opened,
                       "GuardAimSwitchWall_" + spec.suffix)
        switch.set_actor_scale3d(unreal.Vector(0.55, 2.8, 3.2))
        tag(decoy_wall, "GuardVisibleAim.Occluder", group,
            "GuardVisibleAim.Occluder.%s.Decoy" % spec.suffix)
        tag(switch, "GuardVisibleAim.Occluder", group,
            "GuardVisibleAim.Occluder.%s.Switch" % spec.suffix)
        main_goal = spawn(actors, unreal.GuardVisibleAimGoal,
                          vec(spec.origin, (2400.0, 0.0, 20.0)),
                          "GuardAimMainGoal_" + spec.suffix)
        control_goal = spawn(actors, unreal.GuardVisibleAimGoal,
                             vec(spec.origin, (2400.0, 1650.0, 20.0)),
                             "GuardAimControlGoal_" + spec.suffix)
        tag(main_goal, "GuardVisibleAim.Goal", group,
            "GuardVisibleAim.Goal.%s.Main" % spec.suffix)
        tag(control_goal, "GuardVisibleAim.Goal", group,
            "GuardVisibleAim.Goal.%s.Control" % spec.suffix)
        scenario = spawn(actors, unreal.GuardVisibleAimScenario,
                         vec(spec.origin, (-300.0, -350.0, 40.0)),
                         "GuardAimScenario_" + spec.suffix)
        tag(scenario, "GuardVisibleAim.Scenario",
            "GuardVisibleAim.Scenario." + spec.suffix)
        for prop, value in {
            "scenario_id": unreal.Name(spec.suffix),
            "expected_anim_class": anim.generated_class(),
            "main_guard": main,
            "control_guard": control,
            "visible_target": visible,
            "occluded_decoy": decoy,
            "decoy_occluder": decoy_wall,
            "switch_occluder": switch,
            "main_goal": main_goal,
            "control_goal": control_goal,
            "switch_open_location": opened,
            "switch_blocked_location": blocked,
            "expected_yaw_sign": spec.yaw_sign,
            "expected_pitch_sign": spec.pitch_sign,
        }.items():
            scenario.set_editor_property(prop, value)
        spawn(actors, fixture_classes[spec.suffix],
              vec(spec.origin, (-500.0, -500.0, 120.0)),
              "GuardVisibleAim%sFunctionalTest" % spec.suffix)
    spawn(actors, unreal.PlayerStart, unreal.Vector(0.0, -3600.0, 120.0),
          "GuardAimPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1200.0),
          "GuardAimKeyLight", unreal.Rotator(-55.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 900.0),
          "GuardAimSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    stock_game_mode = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode")
    if stock_game_mode is None or stock_game_mode.generated_class() is None:
        fail("stock ThirdPerson game mode missing")
    world.get_world_settings().set_editor_property(
        "default_game_mode", stock_game_mode.generated_class())
    nav_detail = str(helper.build_navigation(world))
    if not nav_detail.startswith("PASS "):
        fail("navigation failed: " + nav_detail)
    contract = str(helper.inspect_world(world, mode == "admission"))
    if not contract.startswith("PASS "):
        fail("pre-save contract failed: " + contract)
    if not levels.save_current_level() or not map_file.is_file():
        fail("save_current_level failed")
    after = {name: snapshot(path) for name, path in protected.items()}
    if after != before:
        fail("AnimBlueprint/reference protected bytes changed")
    unreal.log("GUARD-AIM-MAP-SAVED mode=%s map=%s sha256=%s groups=%d "
               "guards=%d targets=%d occluders=%d goals=%d nav=%s contract=%s" %
               (mode, map_path, sha256(map_file), len(scenarios),
                len(scenarios) * 2, len(scenarios) * 2,
                len(scenarios) * 2, len(scenarios) * 2, nav_detail, contract))
