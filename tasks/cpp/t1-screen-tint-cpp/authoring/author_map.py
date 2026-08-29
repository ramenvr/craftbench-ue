"""Authors L_TintTrack for t1-screen-tint.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A straight measured track. The difficulty of this task is not in the geometry --
it is that the effect has to follow the character's MEASURED speed as a fraction
of the top speed it has RIGHT NOW, and the fixture changes that top speed between
the two legs. What the geometry has to guarantee is only that the drive fits:
the character must be able to walk the whole schedule without running out of
floor, or it stops early and the gates measure a wall rather than an effect.
That is asserted below from the numbers the fixture actually uses.

This level names NO game mode: it inherits the project default, so the play lane
comes for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import unreal

TASK = "t1-screen-tint"
MAP_PKG = f"/Game/Maps/{TASK}/L_TintTrack"

FLOOR_MIN = (-1400.0, -1200.0)
FLOOR_MAX = (8600.0, 1200.0)
STRIPE_EVERY = 200.0
START_AT = (-800.0, 0.0)

# Mirrors the fixture's drive schedule, so "the track is long enough" is measured
# rather than eyeballed. (phase seconds, input scale) for the outbound leg.
LEG_ONE_PHASES = ((4.0, 0.0), (8.0, 0.5), (8.0, 1.0), (5.0, 0.0))
SECOND_LEG_SPEED_SCALE = 0.52
DEFAULT_TOP_SPEED = 500.0   # the stock ThirdPerson character's MaxWalkSpeed

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"TINTTRACK- {msg}")


def fail(msg):
    unreal.log_error(f"TINTTRACK-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW, M_HAZARD):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("ScreenTintActor", "ScreenTintFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, yaw=0.0, collide=True):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    if not collide:
        # The PROFILE, not just the enum: set_collision_enabled alone did not survive
        # into a saved level on the detour task, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def check_track_length():
    """The character must not run out of floor before the drive finishes."""
    travel = sum(seconds * scale * DEFAULT_TOP_SPEED
                 for seconds, scale in LEG_ONE_PHASES)
    need_forward = travel + 400.0        # room to stop and not scrape the backdrop
    have_forward = FLOOR_MAX[0] - START_AT[0]
    if have_forward < need_forward:
        fail(f"the outbound leg walks {travel:.0f} uu but there is only "
             f"{have_forward:.0f} uu of floor ahead of the start (need "
             f"{need_forward:.0f}); the character would stop against the edge and "
             f"the effect would be graded against a wall")
    # The return leg is slower, so it cannot overshoot backwards, but check anyway.
    back = sum(seconds * scale * DEFAULT_TOP_SPEED * SECOND_LEG_SPEED_SCALE
               for seconds, scale in LEG_ONE_PHASES)
    if travel - back < -(START_AT[0] - FLOOR_MIN[0]) + 400.0:
        fail(f"the return leg walks {back:.0f} uu back from {travel:.0f} uu out and "
             f"would leave the floor behind the start")
    log(f"track length checked: outbound {travel:.0f} uu into "
        f"{have_forward:.0f} uu of floor, return {back:.0f} uu")


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    check_track_length()

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

    # Stripes every 200 cm so a reviewer can see the pace change by eye, and so the
    # distance covered between two checkpoints is countable off a still.
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        every_fifth = (n % 5) == 0
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.1 if every_fifth else 0.05, span_y / 100.0, 0.03),
              f"Stripe_{n:02d}", M_GLOW if every_fifth else M_STRIPE, collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"track {span_x:.0f}x{span_y:.0f} + {n} stripes, every fifth one bright")

    tint = eas.spawn_actor_from_class(
        env["ScreenTintActor"], unreal.Vector(mid_x, mid_y, 400.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if tint is None:
        fail("could not place the screen tint actor")
    tint.set_actor_label("ScreenTint")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # Side rails, so a reviewer running the track has something to judge speed
    # against, and two differently sized end posts.
    for side in (-1.0, 1.0):
        block(env, CUBE, unreal.Vector(mid_x, side * (FLOOR_MAX[1] - 60.0), 60.0),
              unreal.Vector(span_x / 100.0, 0.4, 1.2), f"Rail_{'L' if side < 0 else 'R'}",
              M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 200.0, FLOOR_MAX[0] - 200.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 300.0, 280.0),
              unreal.Vector(1.1 + idx * 0.9, 1.1 + idx * 0.9, 5.6), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1000.0),
        unreal.Rotator(roll=0.0, pitch=-50.0, yaw=-120.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1000.0),
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

    eas.spawn_actor_from_class(
        env["ScreenTintFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 200.0, FLOOR_MIN[1] + 200.0, 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)).set_actor_label(
            "ScreenTintFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    tints = [a for a in eas.get_all_level_actors() if a.actor_has_tag("ScreenTint")]
    if len(tints) != 1:
        fail(f"{len(tints)} actor(s) tagged ScreenTint, expected 1")

    # THE EFFECT MUST BE LIVE BEFORE ANYTHING TOUCHES IT. An unbound volume whose
    # overrides are off shows nothing however correctly a submission drives it, and
    # that failure would read as the submission's.
    rest = float(tints[0].get_editor_property("rest_vignette"))
    full = float(tints[0].get_editor_property("full_vignette"))
    fringe = float(tints[0].get_editor_property("supplied_fringe"))
    if abs(full - rest) < 0.3:
        fail(f"the effect only swings {abs(full - rest):.2f} between rest ({rest:.2f}) "
             f"and full ({full:.2f}); the fixture grades to 0.12 and could not tell "
             f"a correct answer from a wrong one")
    if not 0.05 <= fringe <= 1.0:
        fail(f"the supplied colour-fringe control reads {fringe:.2f}; it has to be a "
             f"value a submission could plausibly disturb, or the control proves "
             f"nothing")
    log(f"effect swings {rest:.2f} -> {full:.2f}, control fringe supplied at "
        f"{fringe:.2f}")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
