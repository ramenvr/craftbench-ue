"""Deterministic one-group admission and two-group retained map authoring."""

from dataclasses import dataclass
import unreal

from alert_stride_common import (
    ADMISSION_INTERFACE, ADMISSION_MAP, ADMISSION_ROOT, FINAL_INTERFACE,
    FINAL_MAP, FINAL_ROOT, REFERENCE, disk, packages, sha256, signature,
    snapshot,
)


TEMPLATE = "/Engine/Maps/Templates/Template_Default"


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    origin: tuple[float, float]
    speed: float
    direction: tuple[float, float]
    alert_delay: float
    clear_delay: float
    end_delay: float


ADMISSION = (
    ScenarioSpec("Admission", (0.0, 0.0), 285.0, (0.92, 0.39),
                 0.92, 1.82, 2.82),
)
FINAL = (
    ScenarioSpec("SlowEarly", (-3300.0, -500.0), 210.0, (0.96, 0.28),
                 0.78, 1.62, 2.58),
    ScenarioSpec("FastLate", (3300.0, 500.0), 365.0, (0.89, -0.46),
                 1.08, 2.12, 3.18),
)


def fail(message: str):
    unreal.log_error("ALERT-STRIDE-MAP-FAILED: " + message)
    raise RuntimeError(message)


def spawn(subsystem, cls, location, label, rotation=None):
    actor = subsystem.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def tag(actor, *values):
    actor.set_editor_property("tags", [unreal.Name(value) for value in values])


def unpack(value):
    if isinstance(value, tuple) and len(value) == 2:
        return bool(value[0]), str(value[1])
    return bool(value), str(value)


def author(mode: str):
    if mode not in ("admission", "final"):
        fail("unsupported mode=" + mode)
    admission = mode == "admission"
    root = ADMISSION_ROOT if admission else FINAL_ROOT
    interface_path = ADMISSION_INTERFACE if admission else FINAL_INTERFACE
    map_path = ADMISSION_MAP if admission else FINAL_MAP
    specs = ADMISSION if admission else FINAL
    map_file = disk(map_path, ".umap")
    asset_paths = packages(root)
    protected = {
        "assets": disk(root, ""),
        "interface": disk(interface_path, ".uasset"),
        "other_assets": disk(FINAL_ROOT if admission else ADMISSION_ROOT, ""),
        "other_map": disk(FINAL_MAP if admission else ADMISSION_MAP, ".umap"),
        "reference": REFERENCE,
    }
    before = {name: snapshot(path) for name, path in protected.items()}
    if before["assets"].get("kind") != "directory" \
            or before["interface"].get("kind") != "file":
        fail("required asset set absent")
    if unreal.EditorAssetLibrary.does_asset_exist(map_path) or map_file.exists():
        fail("refusing to overwrite map: " + map_path)
    loaded = ([unreal.EditorAssetLibrary.load_asset(interface_path)] +
              [unreal.EditorAssetLibrary.load_asset(path) for path in asset_paths])
    if any(value is None for value in loaded):
        fail("one or more exact assets failed to load")
    interface, host, calm, alert, state_tree = loaded
    helper = getattr(unreal, "AlertStrideAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper missing")
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
                  unreal.Vector(0.0, 0.0, -50.0), "AlertStrideFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(100.0, 55.0, 1.0))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    fixture_classes = {
        "Admission": unreal.AlertStrideAdmissionFunctionalTest,
        "SlowEarly": unreal.AlertStrideSlowFunctionalTest,
        "FastLate": unreal.AlertStrideFastFunctionalTest,
    }
    fixture_labels = {
        "Admission": "AlertStrideAdmissionFunctionalTest",
        "SlowEarly": "AlertStrideSlowFunctionalTest",
        "FastLate": "AlertStrideFastFunctionalTest",
    }
    for spec in specs:
        origin = unreal.Vector(spec.origin[0], spec.origin[1], 0.0)
        group = "AlertStride.Group." + spec.scenario_id
        subject = spawn(
            actors, unreal.AlertStrideCharacter,
            origin + unreal.Vector(0.0, 0.0, 96.0),
            "AlertStrideSubject_" + spec.scenario_id)
        signal = spawn(
            actors, unreal.AlertStrideSignalActor,
            origin + unreal.Vector(-260.0, 240.0, 40.0),
            "AlertStrideSignal_" + spec.scenario_id)
        scenario = spawn(
            actors, unreal.AlertStrideScenario,
            origin + unreal.Vector(-300.0, -240.0, 40.0),
            "AlertStrideScenario_" + spec.scenario_id)
        tag(subject, "AlertStrideSubject", group,
            "AlertStride.Subject." + spec.scenario_id)
        tag(signal, "AlertStrideSignal", group,
            "AlertStride.Signal." + spec.scenario_id)
        tag(scenario, "AlertStrideScenario", group,
            "AlertStride.Scenario." + spec.scenario_id)
        scenario.set_editor_property("scenario_id", unreal.Name(spec.scenario_id))
        scenario.set_editor_property("subject", subject)
        scenario.set_editor_property("signal", signal)
        scenario.set_editor_property("walk_speed", spec.speed)
        scenario.set_editor_property(
            "travel_direction", unreal.Vector(spec.direction[0], spec.direction[1], 0.0))
        scenario.set_editor_property("alert_delay", spec.alert_delay)
        scenario.set_editor_property("clear_delay", spec.clear_delay)
        scenario.set_editor_property("end_delay", spec.end_delay)
        passed, detail = unpack(helper.configure_scenario(
            scenario, host, interface, calm, alert, state_tree))
        if not passed or not detail.startswith("PASS "):
            fail("scenario configure failed: " + detail)
        spawn(actors, fixture_classes[spec.scenario_id],
              origin + unreal.Vector(-500.0, -460.0, 120.0),
              fixture_labels[spec.scenario_id])
    spawn(actors, unreal.PlayerStart, unreal.Vector(0.0, -4200.0, 120.0),
          "AlertStridePlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1200.0),
          "AlertStrideKeyLight", unreal.Rotator(-55.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 900.0),
          "AlertStrideSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    stock_game_mode = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode")
    if stock_game_mode is None or stock_game_mode.generated_class() is None:
        fail("stock ThirdPerson game mode missing")
    world.get_world_settings().set_editor_property(
        "default_game_mode", stock_game_mode.generated_class())
    contract = str(helper.inspect_world(world, admission))
    if not contract.startswith("PASS "):
        fail("pre-save contract failed: " + contract)
    if not levels.save_current_level() or not map_file.is_file():
        fail("save_current_level failed")
    after = {name: snapshot(path) for name, path in protected.items()}
    if after != before:
        fail("asset/reference bytes changed while authoring map")
    unreal.log("ALERT-STRIDE-MAP-SAVED mode=%s map=%s sha256=%s groups=%d "
               "subjects=%d signals=%d fixtures=%d protected=%s contract=%s" %
               (mode, map_path, sha256(map_file), len(specs), len(specs),
                len(specs), len(specs), signature(after), contract))
