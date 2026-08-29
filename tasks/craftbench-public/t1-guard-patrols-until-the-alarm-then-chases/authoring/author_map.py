"""Authors L_PatrolYard for t1-guard-patrols-until-the-alarm-then-chases.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

The yard is laid out so that the three distances the task turns on are TRUE OF THE
GEOMETRY and not merely written down: the alarm plate is inside the guard's alert
range, and both the spot the character waits on and the second figure are outside it.
Every one of those is asserted below before the level is allowed to save.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t1-guard-patrols-until-the-alarm-then-chases"
MAP_PKG = f"/Game/Maps/{TASK}/L_PatrolYard"

FLOOR_MIN = (-3200.0, -1400.0)
FLOOR_MAX = (3200.0, 1400.0)
STRIPE_EVERY = 400.0

# The patrol line runs along Y at X = 0; everything else is placed relative to it.
PATROL_LINE_X = 0.0
POST_A = (PATROL_LINE_X, -700.0)
POST_B = (PATROL_LINE_X, 700.0)
# NOT on a post. The guard's body is solid and so are the posts, and it walks by
# a SWEPT SetActorLocation: spawned inside a post it is penetrating from frame
# one and the sweep refuses every move. Measured -- the reference guard sat at
# its start for the whole 60 s run while its Tick ran 3600 times.
GUARD_AT = (PATROL_LINE_X, 0.0)
# Guard body radius + post radius + room to not be touching.
GUARD_POST_CLEARANCE = 35.0 + 25.0 + 90.0
# The guard's collision capsule is centred on its actor location, so it stands at
# half its own height plus a little daylight. Asserted from the placed actor's real
# bounds below, never assumed.
GUARD_STAND_Z = 95.0
FLOOR_TOP_Z = 0.0
# The panel stands OFF the axis everything else uses, facing across the yard. On
# the axis it is unplaceable: whichever way it faces, its board ends up between the
# plate and either the character walking up to it or the guard coming for the
# character. Measured -- the first layout put the board across the character's
# path, the alarm never rang, and the empty submission failed for the fixture's
# reason instead of its own.
# The BOARD stands off the walking line; the PLATE it puts 300 cm in front of
# itself lands ON that line. That is the whole point of the offset -- measured
# 2026-08-18, when the owner played this level and never found the plate at all,
# so the guard did nothing and the level read as broken. A trigger a player walks
# past is a trigger that does not exist.
PANEL_AT = (1100.0, -300.0)
PANEL_YAW = 90.0
PLATE_OFFSET = 300.0
PLATE_HALF = 120.0     # matches AAlarmPanelActor's plate volume half-extent
BOARD_HALF = (20.0, 150.0)   # the board's own half-extents, before its yaw
WAIT_AT = (3000.0, 0.0)
DECOY_AT = (-2600.0, 0.0)
# Matches APatrolGuardActor::AlertRangeUu. Asserted against the class default below
# rather than trusted, so the two cannot drift apart silently.
ALERT_RANGE = 2000.0
# Matches the fixture's post jitter, so the assertions hold for the staged yard too.
POST_JITTER = 80.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
SPHERE = "/Engine/BasicShapes/Sphere.Sphere"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def segment_clears_board(a, b, board_at, board_yaw, half, need):
    """Closest approach of the segment a->b to the board's footprint, vs `need`.

    Works in the board's own frame, so its yaw is handled rather than assumed
    away. Returns the clearance in cm; negative means the segment goes through.
    """
    ca, sa = math.cos(math.radians(-board_yaw)), math.sin(math.radians(-board_yaw))

    def local(p):
        dx, dy = p[0] - board_at[0], p[1] - board_at[1]
        return (dx * ca - dy * sa, dx * sa + dy * ca)

    la, lb = local(a), local(b)
    worst = None
    steps = max(2, int(math.hypot(lb[0] - la[0], lb[1] - la[1]) / 10.0))
    for k in range(steps + 1):
        f = k / steps
        px = la[0] + f * (lb[0] - la[0])
        py = la[1] + f * (lb[1] - la[1])
        # Distance from the point to the axis-aligned box, negative when inside.
        ox, oy = abs(px) - half[0], abs(py) - half[1]
        if ox <= 0.0 and oy <= 0.0:
            d = max(ox, oy)
        else:
            d = math.hypot(max(ox, 0.0), max(oy, 0.0))
        if worst is None or d < worst:
            worst = d
    return worst


def log(msg):
    unreal.log(f"PATROLYARD- {msg}")


def fail(msg):
    unreal.log_error(f"PATROLYARD-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, SPHERE, M_FLOOR, M_STRIPE, M_DARK, M_GLOW, M_HAZARD):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("PatrolGuardActor", "AlarmPanelActor",
                     "PatrolChaseFunctionalTest"):
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
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def check_geometry(alert_range):
    """The three distances the task turns on, measured rather than assumed.

    Measured FROM EACH POST, at every corner of the fixture's jitter, never from
    the midpoint of the patrol line. The guard can be anywhere on its route when
    the alarm rings, and the midpoint is the most flattering point on it: the
    first version of this check measured there, passed, and would have handed a
    correct solution a plate 2143 uu away from the far post with an alert range
    of 2000 -- i.e. a guard standing at the wrong end of its own route is
    forbidden to respond to the alarm at all.
    """
    plate_x = PANEL_AT[0] + math.cos(math.radians(PANEL_YAW)) * PLATE_OFFSET
    plate = (plate_x, PANEL_AT[1] + math.sin(math.radians(PANEL_YAW)) * PLATE_OFFSET)
    margin = 150.0
    worst_plate, best_wait, best_decoy = 0.0, 1e9, 1e9
    for base in (POST_A, POST_B):
        for jx in (-POST_JITTER, 0.0, POST_JITTER):
            for jy in (-POST_JITTER, 0.0, POST_JITTER):
                here = (base[0] + jx, base[1] + jy)
                worst_plate = max(worst_plate,
                                  math.hypot(plate[0] - here[0], plate[1] - here[1]))
                best_wait = min(best_wait, math.hypot(WAIT_AT[0] - here[0],
                                                      WAIT_AT[1] - here[1]))
                best_decoy = min(best_decoy, math.hypot(DECOY_AT[0] - here[0],
                                                        DECOY_AT[1] - here[1]))
    if worst_plate > alert_range - margin:
        fail(f"from the far end of its route the guard is {worst_plate:.0f} uu from "
             f"the alarm plate, against a {alert_range:.0f} uu alert range (need "
             f"{margin:.0f} uu of margin); a guard standing there could not "
             f"legitimately respond to the alarm at all")
    if best_wait < alert_range + margin:
        fail(f"the wait spot comes within {best_wait:.0f} uu of the guard's route, "
             f"against a {alert_range:.0f} uu alert range; a guard obeying the quiet "
             f"rule would be indistinguishable from one that chases everything")
    if best_decoy < alert_range + margin:
        fail(f"the second figure comes within {best_decoy:.0f} uu of the guard's "
             f"route, against a {alert_range:.0f} uu alert range; it is supposed to "
             f"be parked permanently outside it")
    # THE TWO STRAIGHT PATHS. The character walks from the wait spot to the plate,
    # and the guard comes at the character from its line. Neither may have to get past
    # the panel's board, and neither may have to push past a post or the guard's own
    # start. Measured against the board's real footprint at its real yaw -- the first
    # layout put it squarely across the character's path and the alarm never rang.
    # The guard must not START inside anything solid.
    for name, (px, py) in (("post A", POST_A), ("post B", POST_B)):
        d = math.hypot(GUARD_AT[0] - px, GUARD_AT[1] - py)
        if d < GUARD_POST_CLEARANCE:
            fail(f"the guard starts {d:.0f}cm from {name} (need "
                 f"{GUARD_POST_CLEARANCE:.0f}cm); it would be spawned inside it and a "
                 f"swept move can never get it out")

    need = 42.0 + 60.0   # the character's radius, plus room to not scrape
    for name, seg_a, seg_b in (
            ("the character walking to the plate", WAIT_AT, plate),
            ("the guard coming for the character", POST_A, plate),
            ("the guard coming from the far post", POST_B, plate)):
        clear = segment_clears_board(seg_a, seg_b, PANEL_AT, PANEL_YAW, BOARD_HALF,
                                     need)
        if clear < need:
            fail(f"{name} passes within {clear:.0f}cm of the alarm board (need "
                 f"{need:.0f}cm); it would be walking into it")
    for name, (px, py) in (("post A", POST_A), ("post B", POST_B),
                           ("the guard", GUARD_AT)):
        clear = segment_clears_board(WAIT_AT, plate, (px, py), 0.0, (60.0, 60.0), need)
        if clear < need:
            fail(f"{name} stands within {clear:.0f}cm of the line the character walks "
                 f"between the wait spot and the plate")
    # THE PLATE MUST BE ON THE LINE A PLAYER WALKS. Somebody who spawns at the far
    # end and heads for the guards has to step on it without being told to; a plate
    # 270 cm off that line is one a player walks straight past, which is what happened
    # the first time this level was played by hand.
    walk_a, walk_b = (WAIT_AT[0], WAIT_AT[1]), (PATROL_LINE_X, 0.0)
    seg = math.hypot(walk_b[0] - walk_a[0], walk_b[1] - walk_a[1])
    if seg > 1.0:
        tt = max(0.0, min(1.0, ((plate[0] - walk_a[0]) * (walk_b[0] - walk_a[0])
                                + (plate[1] - walk_a[1]) * (walk_b[1] - walk_a[1]))
                          / (seg * seg)))
        near = (walk_a[0] + tt * (walk_b[0] - walk_a[0]),
                walk_a[1] + tt * (walk_b[1] - walk_a[1]))
        off = math.hypot(plate[0] - near[0], plate[1] - near[1])
        if off > PLATE_HALF:
            fail(f"the alarm plate sits {off:.0f} cm off the straight line a player "
                 f"walks from the start to the guards, and the plate is only "
                 f"{PLATE_HALF:.0f} cm across; somebody walking in would miss it and "
                 f"the level would read as a guard that does nothing")
        log(f"plate is ON the player's walking line ({off:.0f} cm off centre, half "
            f"width {PLATE_HALF:.0f})")

    log(f"geometry checked from BOTH posts across the jitter: plate at worst "
        f"{worst_plate:.0f} uu (in), wait spot at best {best_wait:.0f} uu (out), "
        f"second figure at best {best_decoy:.0f} uu (out), alert range "
        f"{alert_range:.0f}")
    return plate


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # The alert range is read off the CLASS DEFAULT, not copied into this file, so the
    # layout and the guard cannot drift apart without the level refusing to save.
    alert_range = float(unreal.get_default_object(
        env["PatrolGuardActor"]).get_editor_property("alert_range_uu"))
    if abs(alert_range - ALERT_RANGE) > 1.0:
        fail(f"the guard's AlertRangeUu is {alert_range:.0f}, not the {ALERT_RANGE:.0f} "
             f"this layout was measured against")
    plate = check_geometry(alert_range)

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
        # PAINT, NOT GEOMETRY. These are 3 cm proud of the floor, which a character's
        # capsule steps over without noticing -- and which stopped the guard dead,
        # because a guard walked by a swept SetActorLocation has its feet exactly on
        # the floor and a 3 cm lip is a wall to it. Measured: the reference guard moved
        # 61 cm in 60 s and never reached its second post.
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes")

    # THE PATROL LINE, painted so a reviewer can see at a glance whether the guard is
    # on it. Bright, and the length of the route.
    block(env, CUBE, unreal.Vector(PATROL_LINE_X, 0.0, 2.0),
          unreal.Vector(0.5, (POST_B[1] - POST_A[1]) / 100.0, 0.04), "PatrolLine",
          M_GLOW, collide=False)

    # THE ALERT-RANGE ARC, so "inside" and "outside" are visible rather than stated.
    for k in range(-6, 7):
        ang = math.radians(k * 7.0)
        block(env, CUBE,
              unreal.Vector(PATROL_LINE_X + math.cos(ang) * alert_range,
                            math.sin(ang) * alert_range, 1.0),
              unreal.Vector(0.05, 1.4, 0.02), f"RangeArc_{k + 6:02d}", M_HAZARD,
              yaw=math.degrees(ang), collide=False)
    log(f"patrol line painted, alert-range arc marked at {alert_range:.0f} uu")

    for label, (px, py) in (("PatrolPost_A", POST_A), ("PatrolPost_B", POST_B)):
        post = block(env, CYL, unreal.Vector(px, py, 110.0),
                     unreal.Vector(0.5, 0.5, 2.2), label, M_DARK)
        post.tags = ["PatrolPost"]
        # MOVABLE, not static: the fixture nudges the posts before play, and PIE logs a
        # "mobility must be Movable" ERROR when a static one is moved -- which
        # AFunctionalTest scores as a test failure. Measured: a fully correct reference
        # run, patrolling and chasing exactly as asked, FAILED on that error alone.
        post.static_mesh_component.set_editor_property(
            "mobility", unreal.ComponentMobility.MOVABLE)
        # MOVABLE, not static: the fixture nudges the posts before play, and PIE logs a
        # "mobility must be Movable" ERROR when a static one is moved -- which
        # AFunctionalTest scores as a test failure. Measured: a fully correct reference
        # run, patrolling and chasing exactly as asked, FAILED on that error alone.
        post.static_mesh_component.set_editor_property(
            "mobility", unreal.ComponentMobility.MOVABLE)
        block(env, SPHERE, unreal.Vector(px, py, 250.0),
              unreal.Vector(0.7, 0.7, 0.7), f"{label}_Lamp", M_GLOW, collide=False)
    log(f"two lit posts at {POST_A} and {POST_B}")

    guard = eas.spawn_actor_from_class(
        env["PatrolGuardActor"], unreal.Vector(GUARD_AT[0], GUARD_AT[1],
                                              GUARD_STAND_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    if guard is None:
        fail("could not place the guard")
    guard.set_actor_label("PatrolGuard")
    # THE GUARD MUST STAND ON THE FLOOR, NOT IN IT. A guard whose collision dips below
    # the floor is penetrating from frame one and every swept move it makes is refused
    # at zero distance -- measured, with 90 cm of penetration and a Tick that ran 3600
    # times without the guard moving once. Measured from the placed actor's own bounds.
    g_origin, g_extent = guard.get_actor_bounds(only_colliding_components=True)
    g_bottom = g_origin.z - g_extent.z
    if g_bottom < FLOOR_TOP_Z + 1.0:
        fail(f"the guard's collision reaches down to z={g_bottom:.1f}, at or below the "
             f"floor at z={FLOOR_TOP_Z:.1f}; it would be penetrating the floor and "
             f"unable to move at all")
    log(f"guard stands with its collision bottom at z={g_bottom:.1f}, clear of the "
        f"floor")

    panel = eas.spawn_actor_from_class(
        env["AlarmPanelActor"], unreal.Vector(PANEL_AT[0], PANEL_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=PANEL_YAW))
    if panel is None:
        fail("could not place the alarm panel")
    panel.set_actor_label("AlarmPanel")
    log(f"guard at {GUARD_AT}, alarm panel at {PANEL_AT} with its plate at "
        f"({plate[0]:.0f}, {plate[1]:.0f})")

    # THE SECOND FIGURE. Parked permanently outside the alert range and never the
    # target: a guard that goes after whatever is nearest rather than what the alarm
    # is about ends up here.
    decoy_body = block(env, CYL, unreal.Vector(DECOY_AT[0], DECOY_AT[1], 90.0),
                       unreal.Vector(0.7, 0.7, 1.8), "DecoyFigure", M_DARK)
    decoy_body.tags = ["DecoyFigure"]
    block(env, SPHERE, unreal.Vector(DECOY_AT[0], DECOY_AT[1], 205.0),
          unreal.Vector(0.6, 0.6, 0.6), "DecoyFigure_Head", M_GLOW, collide=False)

    # A painted run-in from the start to the plate, so a player heading for the
    # guards walks down it and onto the trigger rather than past it.
    lane_from, lane_to = WAIT_AT[0], plate[0]
    steps = 12
    for k in range(steps):
        f0 = k / steps
        block(env, CUBE,
              unreal.Vector(lane_from + (lane_to - lane_from) * (f0 + 0.5 / steps),
                            plate[1], 2.0),
              unreal.Vector((abs(lane_to - lane_from) / steps) * 0.6 / 100.0, 0.9,
                            0.04),
              f"ApproachLane_{k:02d}", M_GLOW, collide=False)
    log(f"approach lane painted from the start to the plate ({abs(lane_to - lane_from):.0f} cm)")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(WAIT_AT[0], WAIT_AT[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 20.0, 90.0),
          unreal.Vector(span_x / 100.0, 0.3, 1.8), "Backdrop", M_DARK)
    for idx, (lx, ly) in enumerate(((FLOOR_MIN[0] + 200.0, FLOOR_MAX[1] - 300.0),
                                    (FLOOR_MAX[0] - 200.0, FLOOR_MAX[1] - 300.0))):
        block(env, CYL, unreal.Vector(lx, ly, 300.0),
              unreal.Vector(1.1 + idx * 0.8, 1.1 + idx * 0.8, 6.0), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=-50.0, yaw=-120.0))
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

    eas.spawn_actor_from_class(
        env["PatrolChaseFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 200.0, FLOOR_MIN[1] + 200.0, 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)).set_actor_label(
            "PatrolChaseFunctionalTest")

    # NO game mode is named on purpose -- the level inherits the project default, whose
    # pawn is the stock mannequin and whose controller carries IMC_Default.
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    for tag, want in (("PatrolGuard", 1), ("PatrolPost", 2), ("AlarmPanel", 1),
                      ("DecoyFigure", 1)):
        got = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}; the fixture "
                 f"resolves the yard by these tags and would refuse to start")
    # Anything the fixture RELOCATES before play has to be movable, or PIE logs an
    # error that AFunctionalTest scores as a failed test.
    for post in [a for a in eas.get_all_level_actors()
                 if a.actor_has_tag("PatrolPost")]:
        if post.static_mesh_component.get_editor_property("mobility") !=                 unreal.ComponentMobility.MOVABLE:
            fail(f"{post.get_actor_label()} is not MOVABLE; the fixture nudges the "
                 f"posts before play and PIE would log a mobility error, which the "
                 f"functional test scores as a FAIL")
    # Anything the fixture RELOCATES before play has to be movable, or PIE logs an
    # error that AFunctionalTest scores as a failed test.
    for post in [a for a in eas.get_all_level_actors()
                 if a.actor_has_tag("PatrolPost")]:
        if post.static_mesh_component.get_editor_property("mobility") !=                 unreal.ComponentMobility.MOVABLE:
            fail(f"{post.get_actor_label()} is not MOVABLE; the fixture nudges the "
                 f"posts before play and PIE would log a mobility error, which the "
                 f"functional test scores as a FAIL")
    log("tag census matches what the fixture resolves: 1 guard, 2 posts, 1 panel, "
        "1 second figure")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
