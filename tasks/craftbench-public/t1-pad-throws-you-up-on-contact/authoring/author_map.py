"""Author Content/Maps/t1-pad-throws-you-up-on-contact/L_PadLane.umap.

Run headless, from the repo root (CB_UE_ROOT = your UE 5.8 install):

    MSYS_NO_PATHCONV=1 "$CB_UE_ROOT/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
      "$(cygpath -m UE-projects/ThirdPerson/ThirdPerson.uproject)" \
      -ExecutePythonScript="$(cygpath -m tasks/craftbench-public/t1-pad-throws-you-up-on-contact/authoring/author_map.py)" \
      -nullrhi -unattended -nosplash

Every line this prints is prefixed PADLANE- so the runner can grep it out of
ThirdPerson.log, and the last line on success is PADLANE-DONE. A boot that ends
without that marker FAILED, whatever its exit code says — UE returns 0 from a
great many broken states.

WHY A CAPABILITY PROBE FIRST. This runs unattended, and a wrong API name in UE
python does not raise where you can see it: it either throws inside a callback
the engine swallows, or returns None and the script sails on to save an empty
level. So the probe resolves every subsystem and asset path up front and refuses
to author anything until they are all in hand.

The staged scene is the showroom convention: a striped floor so distance and
speed are readable by eye, the graded subject and its control twin in one frame,
a height post carrying the number the grade depends on, and a distinct landmark
at each end of the lane so a moving camera is distinguishable from a still one.
"""
import unreal

TASK = "t1-pad-throws-you-up-on-contact"
MAP_PKG = f"/Game/Maps/{TASK}/L_PadLane"

# --- the staged geometry, all in centimetres, floor top surface at Z = 0 ------
FLOOR_X, FLOOR_Y, FLOOR_T = 3600.0, 1400.0, 20.0
STRIPE_EVERY = 200.0
STRIPE_W = 12.0
PAD_AT = unreal.Vector(0.0, 0.0, 0.0)
START_AT = unreal.Vector(-700.0, 0.0, 92.0)
TWIN_MARK_AT = unreal.Vector(0.0, -254.0, 0.0)
POST_AT = unreal.Vector(0.0, 300.0, 0.0)
POST_BANDS = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
BRIGHT_BAND = 300.0
FAR_MARK_X = 800.0
LANDMARK_X = (-1300.0, 2100.0)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"


def log(msg):
    unreal.log(f"PADLANE- {msg}")


def fail(msg):
    unreal.log_error(f"PADLANE-ERROR {msg}")
    raise SystemExit(1)


# --------------------------------------------------------------- probe --------
def probe():
    """Resolve everything before authoring. Refuses rather than half-builds."""
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for meth, sub_key in (("new_level", "les"), ("save_current_level", "les"),
                          ("spawn_actor_from_class", "eas")):
        if not hasattr(got[sub_key], meth):
            fail(f"{sub_key}.{meth}() does not exist on this engine build")
    for path in (CUBE, CYL):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"engine asset missing: {path}")
    # The pad class comes from the agent-writable module; the fixture from the
    # verifier module. Both must be loaded, or the placed actors would be nulls.
    for cls_name in ("ContactPadActor", "PadContactLaunchFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python — is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    gm = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"
    if not unreal.EditorAssetLibrary.does_asset_exist(
            gm.split(".")[0]):
        fail(f"game mode missing: {gm}")
    got["gm_path"] = gm
    log(f"probe OK: {sorted(k for k in got)}")
    return got


# --------------------------------------------------------------- helpers -----
def block(env, mesh, loc, scale, label, tag=None):
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
    if tag:
        actor.tags = [unreal.Name(tag)]
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # RE-AUTHORING NEEDS THE FILE GONE FROM DISK FIRST, and it cannot be done
    # from inside this boot. new_level() refuses to overwrite (returns False),
    # and deleting the package in-session does not help: this repo's TOMBSTONE
    # LAW applies -- once a package is deleted in an editor session the registry
    # never tells the truth about that path again in that boot, so the
    # subsequent new_level() still returns False. Measured 2026-08-17: the
    # in-editor delete reported success and new_level failed anyway.
    # (The same law is documented in tasks/bp/t2-consistent-enum-names/authoring/.)
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and "
             f"re-run this script in a fresh boot:  "
             f"    rm UE-projects/ThirdPerson/Content/Maps/{TASK}/L_PadLane.umap")

    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # Floor: top surface at Z = 0, so the plate centre sits half a thickness down.
    block(env, CUBE, unreal.Vector(FLOOR_X / 2 - 1300.0, 0.0, -FLOOR_T / 2),
          unreal.Vector(FLOOR_X / 100.0, FLOOR_Y / 100.0, FLOOR_T / 100.0),
          "Floor")

    # Stripes across the lane every 200 cm, so a reviewer can read distance and
    # speed off the floor without instrumentation.
    n = 0
    x = -1300.0
    while x <= 2100.0 + 0.1:
        # 3 cm tall, not 0.5: a flush stripe is the same tone as the floor and
        # reads as nothing in a still. This height catches the sun and throws a
        # thin shadow, which is what makes distance readable by eye.
        block(env, CUBE, unreal.Vector(x, 0.0, 1.5),
              unreal.Vector(STRIPE_W / 100.0, FLOOR_Y / 100.0, 0.03),
              f"Stripe_{int(x)}")
        n += 1
        x += STRIPE_EVERY
    log(f"floor + {n} stripes")

    # The graded pad, at the world origin. Placed instance of the agent-writable
    # class; the fixture finds it by its constructor-stamped tag, never by class.
    pad = eas.spawn_actor_from_class(env["ContactPadActor"], PAD_AT,
                                    unreal.Rotator(0, 0, 0))
    if pad is None:
        fail("could not place ContactPadActor")
    pad.set_actor_label("ContactPad")
    log(f"pad placed at {PAD_AT} (plate edges at +/-200)")

    # Where the player starts: three stripes back, off the origin, facing the pad.
    start = eas.spawn_actor_from_class(unreal.PlayerStart, START_AT,
                                      unreal.Rotator(0.0, 0.0, 0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # The control twin's mark. The CHARACTER is not placed: the fixture spawns and
    # possesses it here at the start of every run, so exactly one body ever
    # occupies this spot. Two capsules at one location is how a "the control
    # stayed put" gate false-FAILs.
    block(env, CUBE, unreal.Vector(TWIN_MARK_AT.x, TWIN_MARK_AT.y, 0.5),
          unreal.Vector(1.2, 1.2, 0.01), "ControlMark")

    # The height post: bands every 100 cm to 600, and a wider bright band at
    # exactly 300 — the number the prompt discloses and the grade depends on.
    block(env, CYL, unreal.Vector(POST_AT.x, POST_AT.y, 300.0),
          unreal.Vector(0.25, 0.25, 6.0), "HeightPost")
    for z in POST_BANDS:
        wide = 0.7 if z == BRIGHT_BAND else 0.45
        thick = 0.10 if z == BRIGHT_BAND else 0.04
        block(env, CYL, unreal.Vector(POST_AT.x, POST_AT.y, z),
              unreal.Vector(wide, wide, thick),
              f"Band_{int(z)}" + ("_BRIGHT" if z == BRIGHT_BAND else ""))
    log(f"height post with {len(POST_BANDS)} bands, bright at {BRIGHT_BAND}")

    # The far mark the drive walks to between the two throws.
    block(env, CUBE, unreal.Vector(FAR_MARK_X, 0.0, 0.5),
          unreal.Vector(1.2, 1.2, 0.01), "FarMark")

    # A distinct landmark at each end, so a still camera and a following camera
    # are visibly different in a recording.
    for i, lx in enumerate(LANDMARK_X):
        block(env, CYL, unreal.Vector(lx, 600.0, 200.0),
              unreal.Vector(1.0 + i, 1.0 + i, 4.0), f"Landmark_{i}")

    # LIGHTING. new_level() gives a COMPLETELY EMPTY level -- no sun, no sky, no
    # skylight -- so every --capture still comes out pure black while every gate
    # passes. Measured 2026-08-17: five checkpoint stills, byte-identical at
    # 17,758 bytes each, all black, against a reference that PASSED and held a
    # valid certificate. A task that grades clean and is invisible to a reviewer
    # is the exact failure this whole set exists to avoid, so this rig is not
    # decoration and the probe below asserts it.
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight,
                                    unreal.Vector(0.0, 0.0, 1200.0),
                                    unreal.Rotator(-46.0, -35.0, 0.0))
    if sun is None:
        fail("could not place the DirectionalLight")
    sun.set_actor_label("Sun")
    sky = eas.spawn_actor_from_class(unreal.SkyLight,
                                    unreal.Vector(0.0, 0.0, 1400.0),
                                    unreal.Rotator(0, 0, 0))
    if sky is None:
        fail("could not place the SkyLight")
    sky.set_actor_label("SkyLight")
    atmo = eas.spawn_actor_from_class(unreal.SkyAtmosphere,
                                      unreal.Vector(0.0, 0.0, 0.0),
                                      unreal.Rotator(0, 0, 0))
    if atmo is None:
        fail("could not place the SkyAtmosphere")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    # The fixture itself. It is an actor in the level, like every other L2 test.
    ft = eas.spawn_actor_from_class(env["PadContactLaunchFunctionalTest"],
                                    unreal.Vector(-1100.0, -500.0, 100.0),
                                    unreal.Rotator(0, 0, 0))
    if ft is None:
        fail("could not place PadContactLaunchFunctionalTest")
    ft.set_actor_label("PadContactLaunchFunctionalTest")

    # Hitting Play must possess the stock mannequin, or a human reviewing this
    # level controls nothing and the fixture finds no player character.
    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings() if hasattr(world, "get_world_settings") else None
    gm_cls = unreal.EditorAssetLibrary.load_blueprint_class(
        env["gm_path"].split(".")[0])
    if settings is not None and gm_cls is not None:
        settings.set_editor_property("default_game_mode", gm_cls)
        log("world settings: default game mode set to BP_ThirdPersonGameMode")
    else:
        log("WARNING world settings game mode NOT set "
            f"(settings={settings is not None} gm={gm_cls is not None}) "
            "- the project default applies")

    # Refuse to save a level nobody can see. This check exists because the first
    # version of this script shipped exactly that.
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a --capture still would be "
             f"black and the task would grade clean while being invisible")
    log(f"lighting check: {len(lit)} light actors present")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"saved {MAP_PKG}")
    unreal.log("PADLANE-DONE")


main()
