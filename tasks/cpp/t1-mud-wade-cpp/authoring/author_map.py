"""Authors L_MudLane for t1-mud-wade.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

This script also SUPPLIES the wade clip the task promises: it duplicates a visibly
different mannequin gait into Content/Tasks/<id>/A_MudWade. The clip is supplied
content, not the agent's work -- what the agent has to build is deciding WHEN it
drives the pose. Duplicating rather than authoring keeps the task free of any new
asset dependency.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import unreal

TASK = "t1-mud-wade"
MAP_PKG = f"/Game/Maps/{TASK}/L_MudLane"
WADE_DIR = f"/Game/Tasks/{TASK}"
WADE_PKG = f"{WADE_DIR}/A_MudWade"
# A visibly different gait from the unarmed walk the figures otherwise use.
# NOT a Pistol or Rifle clip. Those carry a WEAPON POSE: the owner played this
# level and asked why the character starts aiming when it steps in mud, which is
# exactly what MF_Pistol_Walk_Fwd looks like. Unarmed is the only family in this
# substrate with no weapon in it, and the backwards walk reads as somebody
# leaning against resistance -- visibly a different gait, and nothing else.
WADE_SOURCE = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Bwd"

FLOOR_MIN = (-200.0, -900.0)
FLOOR_MAX = (3400.0, 900.0)
STRIPE_EVERY = 200.0
HERO_AT = unreal.Vector(200.0, -300.0, 100.0)
TWIN_AT = unreal.Vector(200.0, 300.0, 100.0)
MUD_AT = unreal.Vector(1600.0, -300.0, 0.0)
LANDMARKS = [(-100.0, 800.0), (3300.0, 800.0)]

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_POST = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"


def log(msg):
    unreal.log(f"MUDLANE- {msg}")


def fail(msg):
    unreal.log_error(f"MUDLANE-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_POST, WADE_SOURCE):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("MudHeroCharacter", "MudPatchActor", "MudLaneGameMode",
                     "MudWadeFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # SUPPLY THE WADE CLIP FIRST: the character class resolves it at construction, so
    # it has to exist before anything is placed.
    # NEVER a weapon-set clip. The figure would appear to be aiming a gun while
    # wading, which is what a reviewer sees and asks about (measured 2026-08-18).
    if any(k in WADE_SOURCE for k in ("/Pistol/", "/Rifle/", "_ADS", "/Aim")):
        fail(f"the wade clip {WADE_SOURCE} comes from a weapon set; the figure would "
             f"appear to be aiming a gun while wading")
    if not unreal.EditorAssetLibrary.does_asset_exist(WADE_PKG):
        if not unreal.EditorAssetLibrary.duplicate_asset(WADE_SOURCE, WADE_PKG):
            fail(f"could not supply the wade clip at {WADE_PKG}")
        unreal.EditorAssetLibrary.save_asset(WADE_PKG)
        log(f"supplied the wade clip {WADE_PKG} (from {WADE_SOURCE})")
    else:
        log(f"wade clip already present at {WADE_PKG}")

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR)

    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes")

    place(env, env["MudPatchActor"], MUD_AT, "MudPatch")
    log(f"mud patch at {MUD_AT.x:.0f},{MUD_AT.y:.0f} (400 cm of the graded lane)")

    twin = place(env, env["MudHeroCharacter"], TWIN_AT, "CleanLaneTwin")
    twin.tags = ["MudHero", "CleanLaneTwin"]
    log("clean-lane figure placed with the CleanLaneTwin instance tag")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, HERO_AT, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    for idx, (lx, ly) in enumerate(LANDMARKS):
        block(env, CYL, unreal.Vector(lx, ly, 320.0),
              unreal.Vector(1.2 + idx * 0.7, 1.2 + idx * 0.7, 6.4),
              f"Landmark_{idx}", M_POST)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=-47.0, yaw=-135.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(mid_x, mid_y, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    place(env, env["MudWadeFunctionalTest"],
          unreal.Vector(-100.0, -1100.0, 100.0), "MudWadeFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["MudLaneGameMode"])
    log("world settings: default game mode = MudLaneGameMode")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    gm_cdo = unreal.get_default_object(env["MudLaneGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass; the level could not be "
             "driven by hand")
    pawn_cdo = unreal.get_default_object(pawn_class) if pawn_class else None
    unbound = [p for p in ("move_action", "look_action", "mouse_look_action",
                           "jump_action")
               if not (pawn_cdo and pawn_cdo.get_editor_property(p))]
    if unbound:
        fail(f"the pawn has nothing bound to {', '.join(unbound)}")
    log(f"play lane OK: controller={pc_class.get_name()} pawn={pawn_class.get_name()}")

    # The wade clip has to EXIST, or the whole animation half of the task is
    # unbuildable and the fixture would report it as a model failure.
    #
    # Checked on the ASSET, not on the pawn's CDO. The pawn resolves the clip with a
    # constructor FObjectFinder, which runs when the class is first loaded -- i.e. at
    # editor startup, BEFORE this script duplicates the clip into place. So on the
    # very run that supplies it the CDO is legitimately null, and every run after it
    # resolves. Asserting the CDO here failed a correct level for a reason that had
    # nothing to do with the level (measured 2026-08-18).
    if not unreal.EditorAssetLibrary.does_asset_exist(WADE_PKG):
        fail(f"the supplied wade clip is missing at {WADE_PKG}")
    log(f"the supplied wade clip is in place at {WADE_PKG}")

    # The graded lane and the clean lane must be far enough apart that the control
    # figure can never wander onto the mud.
    mud = [a for a in eas.get_all_level_actors() if a.actor_has_tag("MudPatch")]
    if len(mud) != 1:
        fail(f"{len(mud)} actors tagged MudPatch, expected 1")
    lane_gap = abs(TWIN_AT.y - MUD_AT.y)
    if lane_gap < 500.0:
        fail(f"the clean lane is only {lane_gap:.0f} cm from the mud; the control "
             f"could reach it")
    log(f"clean lane is {lane_gap:.0f} cm clear of the mud")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
