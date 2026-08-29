"""Author Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap.

Run headless, from the repo root, with ABSOLUTE paths (a relative one reaches UE
verbatim and the boot dies with "Failed to open descriptor file"):

    REPO=$(pwd)
    MSYS_NO_PATHCONV=1 "$CB_UE_ROOT/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
      "$(cygpath -m "$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject")" \
      -ExecutePythonScript="$(cygpath -m "$REPO/tasks/craftbench-public/t1-door-stays-open-while-you-stand-on-the-plate/authoring/author_map.py")" \
      -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput

`-FullStdOutLogOutput` is not optional: without it the script runs and prints
NOTHING, which reads exactly like a crash.

Every line is prefixed PLATEDOOR- and the last on success is PLATEDOOR-DONE. A
boot that ends without that marker FAILED, whatever its exit code says.

A capability probe runs first because a wrong API name in UE python does not raise
where you can see it — it returns None and the script sails on to save a broken
level.
"""
import unreal

TASK = "t1-door-stays-open-while-you-stand-on-the-plate"
MAP_PKG = f"/Game/Maps/{TASK}/L_PlateDoorLane"

# --- the staged geometry, all in centimetres, floor top surface at Z = 0 ------
FLOOR_X, FLOOR_Y, FLOOR_T = 3000.0, 1600.0, 20.0
STRIPE_EVERY = 200.0
STRIPE_W = 12.0
START_AT = unreal.Vector(-600.0, -150.0, 95.0)
GRADED_PLATE_AT = unreal.Vector(0.0, -150.0, 0.0)
GRADED_DOOR_AT = unreal.Vector(300.0, -150.0, 0.0)
CONTROL_PLATE_AT = unreal.Vector(0.0, 150.0, 0.0)
CONTROL_DOOR_AT = unreal.Vector(300.0, 150.0, 0.0)
LANDMARK_X = (-1200.0, 1500.0)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"


def log(msg):
    unreal.log(f"PLATEDOOR- {msg}")


def fail(msg):
    unreal.log_error(f"PLATEDOOR-ERROR {msg}")
    raise SystemExit(1)


def probe():
    """Resolve everything before authoring. Refuses rather than half-builds."""
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"engine asset missing: {path}")
    for cls_name in ("ContactPlateActor", "SwingDoorActor", "PlateHeroCharacter",
                     "PlateDoorGameMode", "PlateDoorFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(k for k in got)}")
    return got


def block(env, mesh, loc, scale, label):
    """A static-mesh box/cylinder placed as a plain StaticMeshActor."""
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, 0))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    actor.set_actor_scale3d(scale)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # Same one-way constraint as the pad map: new_level() refuses to overwrite,
    # and deleting the package in-session does NOT help because of this repo's
    # TOMBSTONE LAW (once a package is deleted in an editor session the registry
    # never tells the truth about that path again in that boot; the delete
    # reports success and the following new_level still returns False).
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and "
             f"re-run in a fresh boot:  rm UE-projects/ThirdPerson/Content/Maps/"
             f"{TASK}/L_PlateDoorLane.umap")

    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    block(env, CUBE, unreal.Vector(200.0, 0.0, -FLOOR_T / 2),
          unreal.Vector(FLOOR_X / 100.0, FLOOR_Y / 100.0, FLOOR_T / 100.0), "Floor")

    # Stripes every 200 cm, 3 cm tall so they catch the sun and throw a thin
    # shadow. Flush stripes are the floor's own tone and read as nothing in a
    # still (measured on the pad map).
    n = 0
    x = -1200.0
    while x <= 1500.0 + 0.1:
        block(env, CUBE, unreal.Vector(x, 0.0, 1.5),
              unreal.Vector(STRIPE_W / 100.0, FLOOR_Y / 100.0, 0.03),
              f"Stripe_{int(x)}")
        n += 1
        x += STRIPE_EVERY
    log(f"floor + {n} stripes")

    # The two pairs. Instance tags sit on top of each constructor's class tag, so
    # the fixture finds both by class tag AND can tell graded from control.
    for label, plate_at, door_at, ptag, dtag in (
            ("Graded", GRADED_PLATE_AT, GRADED_DOOR_AT, "GradedPlate", "GradedDoor"),
            ("Control", CONTROL_PLATE_AT, CONTROL_DOOR_AT, "ControlPlate", "ControlDoor")):
        plate = eas.spawn_actor_from_class(env["ContactPlateActor"], plate_at,
                                          unreal.Rotator(0, 0, 0))
        door = eas.spawn_actor_from_class(env["SwingDoorActor"], door_at,
                                         unreal.Rotator(0, 0, 0))
        if plate is None or door is None:
            fail(f"could not place the {label} plate/door pair")
        plate.set_actor_label(f"{label}Plate")
        door.set_actor_label(f"{label}Door")
        plate.tags = [unreal.Name("ContactPlate"), unreal.Name(ptag)]
        door.tags = [unreal.Name("SwingDoor"), unreal.Name(dtag)]
        # Each plate belongs to its OWN door, and the fixture READS this rather
        # than assuming an ordering — which is what lets it catch a plate that
        # moves the other pair's door.
        plate.set_editor_property("LinkedDoor", door)
    log("two plate/door pairs placed, each LinkedDoor set to its own door")

    start = eas.spawn_actor_from_class(unreal.PlayerStart, START_AT,
                                      unreal.Rotator(0.0, 0.0, 0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    for i, lx in enumerate(LANDMARK_X):
        block(env, CYL, unreal.Vector(lx, 700.0, 200.0),
              unreal.Vector(1.0 + i, 1.0 + i, 4.0), f"Landmark_{i}")

    # LIGHTING. new_level() gives a COMPLETELY EMPTY level. On the pad map this
    # shipped five byte-identical black stills against a reference that PASSED
    # and held a valid certificate — a task that grades clean and is invisible to
    # a reviewer is the exact failure this set exists to avoid.
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight,
                                    unreal.Vector(0.0, 0.0, 1200.0),
                                    unreal.Rotator(-46.0, -35.0, 0.0))
    sky = eas.spawn_actor_from_class(unreal.SkyLight,
                                    unreal.Vector(0.0, 0.0, 1400.0),
                                    unreal.Rotator(0, 0, 0))
    atmo = eas.spawn_actor_from_class(unreal.SkyAtmosphere,
                                     unreal.Vector(0.0, 0.0, 0.0),
                                     unreal.Rotator(0, 0, 0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("Sun")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    ft = eas.spawn_actor_from_class(env["PlateDoorFunctionalTest"],
                                    unreal.Vector(-1000.0, -600.0, 100.0),
                                    unreal.Rotator(0, 0, 0))
    if ft is None:
        fail("could not place PlateDoorFunctionalTest")
    ft.set_actor_label("PlateDoorFunctionalTest")

    # The task's own game mode SPAWNS the tagged hero at the PlayerStart (no
    # mannequin is placed), so hitting Play gives a human a body to walk onto
    # the plate with.
    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["PlateDoorGameMode"])
    log("world settings: default game mode = PlateDoorGameMode")

    # Refuse to save a level nobody can DRIVE. Naming a game mode above just
    # replaced GlobalDefaultGameMode (BP_ThirdPersonGameMode), and both halves
    # of Enhanced Input live on the Blueprints it would have supplied:
    # IMC_Default on BP_ThirdPersonPlayerController, and the four IA_* actions
    # on BP_ThirdPersonCharacter's CLASS DEFAULTS -- AThirdPersonCharacter
    # declares them and assigns none, so a native pawn subclass binds nothing.
    # No fixture can catch this (they all drive the pawn through
    # AddMovementInput), which is how this map first shipped authored, lit,
    # graded and completely uncontrollable. See
    # the 2026-08-17 unplayable-play-lane finding.
    gm_cdo = unreal.get_default_object(env["PlateDoorGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass, so the player would "
             "get a bare APlayerController with no input mapping context and "
             "the level could not be driven by hand")
    unbound = []
    pawn_cdo = unreal.get_default_object(pawn_class) if pawn_class else None
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if pawn_cdo is None or not pawn_cdo.get_editor_property(prop):
                unbound.append(prop)
        except Exception:  # property gone entirely -- still unplayable
            unbound.append(prop)
    if unbound:
        fail(f"the pawn has nothing bound to {', '.join(unbound)}; the level "
             f"would grade identically and be impossible to walk around")
    log(f"play lane OK: controller={pc_class.get_name()} "
        f"pawn={pawn_class.get_name()} all four input actions bound")

    # Refuse to save a level nobody can see.
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a --capture still would be "
             f"black and the task would grade clean while being invisible")
    log(f"lighting check: {len(lit)} light actors present")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"saved {MAP_PKG}")
    unreal.log("PLATEDOOR-DONE")


main()
