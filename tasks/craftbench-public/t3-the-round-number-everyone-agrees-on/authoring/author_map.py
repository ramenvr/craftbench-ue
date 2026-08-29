"""Authors L_RoundHall for t3-the-round-number-everyone-agrees-on.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A STONE HALL ON ONE LANE. Everything the runner walks into sits off that lane on its
own spur, and the lane itself is empty from end to end:

    y = +1500   the two far pillars, each carrying one of the hall's signs
    y = +1120   the empty pillar, where the hoist stacks the signs it raises
    y =  +800   THE MARK in the middle of the room, and THE HOIST PLATE
    y =     0   THE LANE -- the entrance stone's floor mark, and nothing else, ever
    y =  -900   THE SINKHOLE
    y = -1500   the two near pillars, each carrying one of the hall's signs

That layout is not decoration and it was not tuned by eye. `ARoundHallFunctionalTest`
REFUSES TO RUN a hall whose geometry it cannot walk, and it says so as a
HARNESS-PRECONDITION -- a non-verdict, which costs a whole graded cell. So this script
solves and then CHECKS the same four route properties the fixture checks, against the
same numbers, and raises before the level is written rather than after a bench:

    1. the lane clears every trigger by 600 uu, sampled at 201 points;
    2. every walk in and out of one trigger clears the other two by 200 uu, at 41;
    3. the entrance mark -- where a fresh runner is put back -- clears every trigger by
       600 uu, so nothing is waiting under their feet;
    4. the sinkhole is within 150 uu of the entrance mark's floor height, because the
       runner only ever walks.

It also proves, here, two things a reviewer would otherwise have to take on trust: that
the THREE NUMBERS THE RUN TURNS ON are not the numbers committed in this level (they are
staged before any BeginPlay, and this script refuses a collision), and that no named
wrong answer's arithmetic ever coincides with the right answer at an advance the fixture
judges -- the fixture asserts that too, and a hall where the two disagreed would be a
non-verdict rather than a graded cell.

TWO THINGS THAT ARE EASY TO GET BACKWARDS, both load-bearing:

  * THE STONE MUST FACE INTO THE HALL. Its floor mark sits at +240 on the STONE'S OWN X
    (RoundHallProps.cpp), a fresh runner is put back on that mark, and the reference puts
    them back facing the way the stone faces. So the stone stands at the far -X end at
    yaw 0, its mark 240 uu further into the room, and the PlayerStart is ON that mark.
  * THE HOIST'S RAISE SOCKET IS AT LOCAL +Y. At yaw 0 the column of raised signs
    therefore stands on the far side of the plate FROM THE LANE, which is what keeps the
    runner from walking through the readout it is being graded on. Turn the plate and
    that column lands in the walk.

The sinkhole's rim and shaft are non-colliding decoration -- what takes a runner is the
volume -- so the floor under it is left whole. A real gap would have to stay inside the
volume's 200 uu half-extent or a runner could fall past the trigger.

Every prop except the FLOOR is non-colliding on every channel, so nothing in the hall
can trap or trip a runner: the level's own floor is what holds people up.

This level names NO game mode: it inherits the project default, so both halves of
Enhanced Input survive and the hall can be played by hand
(the 2026-08-17 unplayable-play-lane finding). It also places NO pawn of its
own -- the fixture deliberately carries no "exactly one pawn" precondition, because that
would hand a submission which spawns a spare runner a non-verdict, so a second PLACED
body is refused HERE instead.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-the-round-number-everyone-agrees-on"
MAP_PKG = f"/Game/Maps/{TASK}/L_RoundHall"

# ------------------------------------------------------------------ the hall's shape
FLOOR_MIN = (-2200.0, -2000.0)
FLOOR_MAX = (1800.0, 2000.0)
STRIPE_EVERY = 200.0            # "striped every 200 cm", so a pace is readable by eye

# The stone stands at the -X end facing +X into the hall. Its floor mark -- the spot a
# runner walks in from, and the spot a fresh runner is put back on -- is MARK_LOCAL_X
# further in. Mirrors AEntranceStoneActor's Mark component offset.
STONE = (-1840.0, 0.0)
MARK_LOCAL_X = 240.0
ENTRANCE = (STONE[0] + MARK_LOCAL_X, STONE[1])       # (-1600, 0)
LANE_Y = ENTRANCE[1]

STEP_MARK = (0.0, 800.0)
HOIST = (-700.0, 800.0)
SINKHOLE = (1000.0, -900.0)

RELIC = (1600.0, 0.0)
HALL_SIGNS = ((400.0, 1500.0), (1400.0, 1500.0), (400.0, -1500.0), (1400.0, -1500.0))

# Half-extents of the three trigger volumes, mirroring RoundHallProps.cpp. Kept here so
# the checks below measure the same boxes the fixture measures. If either side moves,
# both must.
EXT_STEP = (140.0, 140.0)
EXT_HOIST = (120.0, 120.0)
EXT_HOLE = (200.0, 200.0)

# The hoist's raise socket, local (0, +320, +240), and how far above the last one each
# further sign goes. Mirrors AHoistPlateActor.
RAISE_SOCKET_LOCAL = (0.0, 320.0, 240.0)
RAISE_STACK_STEP = 220.0

# ------------------------------------------------------------------------ the numbers
# COMMITTED IN THIS LEVEL -- the decoy. Not one of them is a number the run turns on.
COMMITTED_START = 1
COMMITTED_STEP = 1
COMMITTED_RELIC = 0

# What the fixture writes before any BeginPlay. Mirrored here ONLY so this script can
# prove at authoring time that the fixture's own staged-triple precondition passes on
# this hall -- a hall where it did not would be a non-verdict, not a graded cell.
STAGED_START = 4
STAGED_STEP_FIRST = 2
STAGED_STEP_AFTER = 3
STAGED_RELIC = 1

# --------------------------------------------------- the fixture's own thresholds
MIN_LANE_CLEAR = 600.0          # kMinLaneClearUu
MIN_CROSS_CLEAR = 200.0         # kMinCrossClearUu
MIN_ENTRANCE_CLEAR = 600.0      # kMinEntranceClearUu
MAX_STEP_UP = 150.0             # kMaxStepUpUu
RESTAGE_CLEAR = 400.0           # kRestageClearUu
MARK_TOL = 150.0                # kMarkTolUu -- how far off the mark a fresh runner may be
GROW_XY = 102.0                 # kGrowXYUu -- capsule radius + margin
LEG_BASE_S = 4.0                # kLegBaseS
LEG_SPEED_UU = 220.0            # kLegSpeedUu, the deliberately slow deadline pace
FALL_HOLD_S = 3.5               # kFallHoldS
SENTINEL_S = 200.0              # kSentinelS -- the drive MUST finish before this

# The nineteen-stop script, mirroring ARoundHallFunctionalTest::BuildScript. A hole stop
# is ended by the fall, not by a dwell.
#
# THE SECOND HOIST SITS IMMEDIATELY AFTER THE SECOND FALL, ON PURPOSE: the sign it
# raises then has to come up on a number that has survived a re-body with no advance in
# between, which the first hoist cannot ask. If this order is changed, change
# BuildScript with it -- the two are checked against each other by nothing but a reader.
SCRIPT = (
    ("settle", "entrance", 3.0),
    ("mark", "mark", 2.5),
    ("clear", "lane_mark", 1.5),
    ("mark", "mark", 2.5),
    ("clear", "lane_mark", 1.5),
    ("hoist", "hoist", 2.5),
    ("restage", "lane_hoist", 3.0),
    ("mark", "mark", 2.5),
    ("clear", "lane_mark", 1.5),
    ("hole", "hole", 0.0),
    ("mark", "mark", 2.5),
    ("clear", "lane_mark", 1.5),
    ("hole", "hole", 0.0),
    ("hoist", "hoist", 2.5),
    ("clear", "lane_hoist", 1.5),
    ("mark", "mark", 2.5),
    ("clear", "lane_mark", 1.5),
    ("settle", "lane_mark", 4.0),
)
# What a real walk costs, for the "does the drive finish before the sentinel" check. The
# pawn manages 500 uu/s (ThirdPersonCharacter.cpp); 380 is deliberately pessimistic, and
# the check is a REFUSAL, so pessimism is the safe direction.
EST_WALK_UU = 380.0
EST_ACCEL_S = 1.2               # per leg, for getting up to pace and settling
EST_FALL_S = 1.0                # a hole stop ends when the hole takes the runner

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"

CLASSES = ("HallSignActor", "EntranceStoneActor", "StepMarkActor", "HoistPlateActor",
           "SinkholeActor", "RoundHallFunctionalTest")


def log(msg):
    unreal.log(f"ROUNDHALL- {msg}")


def fail(msg):
    unreal.log_error(f"ROUNDHALL-ERROR {msg}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# The geometry, solved and then checked against the fixture's own numbers
# ---------------------------------------------------------------------------

def triggers():
    """(label, cx, cy, ex, ey) for each of the three things the runner walks into."""
    return (
        ("the mark in the middle of the room", STEP_MARK[0], STEP_MARK[1],
         EXT_STEP[0], EXT_STEP[1]),
        ("the hoist plate", HOIST[0], HOIST[1], EXT_HOIST[0], EXT_HOIST[1]),
        ("the sinkhole", SINKHOLE[0], SINKHOLE[1], EXT_HOLE[0], EXT_HOLE[1]),
    )


def dist_to_volume(trig, px, py):
    """Flat distance from a point to a box's surface -- the fixture's DistToVolume."""
    _, cx, cy, ex, ey = trig
    dx = max(0.0, abs(px - cx) - ex)
    dy = max(0.0, abs(py - cy) - ey)
    return math.hypot(dx, dy)


def stop_point(where):
    """The world XY of a named stop, exactly as the fixture builds it."""
    return {
        "entrance": ENTRANCE,
        "mark": STEP_MARK,
        "hoist": HOIST,
        "hole": SINKHOLE,
        "lane_mark": (STEP_MARK[0], LANE_Y),
        "lane_hoist": (HOIST[0], LANE_Y),
    }[where]


def leg_path_uu(frm, to):
    """Out to the lane, along the lane, in to the stop -- the fixture's BuildTransits."""
    a = (frm[0], LANE_Y)
    b = (to[0], LANE_Y)
    return math.dist(frm, a) + math.dist(a, b) + math.dist(b, to)


def required_trajectory():
    """Start, two advances at the first step, three at the second -- the fixture's
    CheckTheStagedTriple. Index 0 is the hall as it opens."""
    out = [STAGED_START]
    for step in (STAGED_STEP_FIRST, STAGED_STEP_FIRST,
                 STAGED_STEP_AFTER, STAGED_STEP_AFTER, STAGED_STEP_AFTER):
        out.append(out[-1] + step)
    return out


def check_the_numbers():
    """Everything the fixture's own staged-triple precondition asserts, asserted here so
    that a hall which would be a non-verdict is refused before it is written."""
    for label, committed, staged in (("StartNumber", COMMITTED_START, STAGED_START),
                                     ("StepWritten", COMMITTED_STEP, STAGED_STEP_FIRST),
                                     ("PaintedNumber", COMMITTED_RELIC, STAGED_RELIC)):
        if committed == staged:
            fail(f"this level commits {label} {committed} and the fixture stages "
                 f"{staged}; a level-file read and a world read would then be "
                 f"indistinguishable, and 'read it off the thing' would be untested")
    if STAGED_STEP_FIRST == STAGED_STEP_AFTER:
        fail("the mark carries the same step before and after the re-stage, so "
             "read-it-at-the-moment-of-use is unobservable")

    req = required_trajectory()
    for i, v in enumerate(req):
        if v == STAGED_RELIC:
            fail(f"the relic is painted with {STAGED_RELIC} and the hall itself takes "
                 f"that value at advance {i}; the in-scene control has to be a number "
                 f"the hall never shows")
        for j in range(i + 1, len(req)):
            if req[j] == v:
                fail(f"the hall is on {v} at both advance {i} and advance {j}; a "
                     f"repeated value lets a stale readout pass for a fresh one")
    if req[2] == STAGED_START or req[4] == STAGED_START:
        fail(f"the hall is on the number it started with ({STAGED_START}) at one of the "
             f"two hoists, so a sign that initialised itself from the entrance stone "
             f"would be indistinguishable from a right one")

    # The named wrong answers, exactly as the fixture models them.
    #
    # THERE IS NO "private counter on the raised sign" ROW. It was here once and it was a
    # strawman: the hoist spawns Template->GetClass() off a sign the LEVEL placed, so the
    # sign it raises is always the stock supplied sign, and a per-sign counter could only
    # exist if a submission rewrote the supplied prop file it was told to leave alone.
    # What the late-sign gate really catches is a readout population captured once at
    # BeginPlay: the raised sign is never written to and stays BLANK, which is not a
    # number and needs no trajectory.
    cached = [STAGED_START]
    for _ in range(5):
        cached.append(cached[-1] + STAGED_STEP_FIRST)
    body = [STAGED_START,
            STAGED_START + STAGED_STEP_FIRST,
            STAGED_START + 2 * STAGED_STEP_FIRST,
            STAGED_START + 2 * STAGED_STEP_FIRST + STAGED_STEP_AFTER,
            STAGED_START + STAGED_STEP_AFTER,
            STAGED_START + STAGED_STEP_AFTER]
    for name, values, first in (("a step read once and remembered", cached, 1),
                                ("the number kept on the body", body, 4)):
        diverged = None
        for i in range(first, len(req)):
            if values[i] != req[i]:
                diverged = i
                break
        if diverged is None:
            fail(f"'{name}' never disagrees with the right answer at any advance, so "
                 f"that wrong answer would pass the whole run")
        for i in range(diverged, len(req)):
            if values[i] == req[i]:
                fail(f"'{name}' first disagrees at advance {diverged} and comes back "
                     f"into agreement at advance {i}; a wrong answer that re-coincides "
                     f"can slip through the advance it is judged on")

    # THE DOORPLATE, the crossing point of the two halves. Its value is the hall's number
    # sampled at a body change; there are three bodies in the run, and the two falls land
    # after advance 3 and after advance 4.
    door = [req[0], req[0], req[0], req[0], req[3], req[4]]
    door_mirrors = list(req)                       # written like a hall sign
    door_once = [req[0]] * len(req)                # written when the hall opens, once
    for name, values, first in (
            ("a doorplate that shows whatever the hall is on", door_mirrors, 1),
            ("a doorplate written once when the hall opens", door_once, 4)):
        diverged = None
        for i in range(first, len(door)):
            if values[i] != door[i]:
                diverged = i
                break
        if diverged is None:
            fail(f"'{name}' never disagrees with what the doorplate has to show, so "
                 f"that wrong answer would pass the whole run")
        for i in range(diverged, len(door)):
            if values[i] == door[i]:
                fail(f"'{name}' first disagrees with the doorplate at advance "
                     f"{diverged} and comes back into agreement at advance {i}")

    log(f"numbers checked: required {req}; the committed decoys "
        f"({COMMITTED_START}, {COMMITTED_STEP}, {COMMITTED_RELIC}) all differ from the "
        f"staged ({STAGED_START}, {STAGED_STEP_FIRST}->{STAGED_STEP_AFTER}, "
        f"{STAGED_RELIC}); cached-step {cached}, body-scoped {body}, doorplate {door}")


def check_geometry():
    trigs = triggers()

    # The stone has to face INTO the hall, or its mark is behind it and a fresh runner is
    # put back outside the room.
    if MARK_LOCAL_X <= 0.0:
        fail("the stone's floor mark is not on its +X side; the placement below assumes "
             "that it is")
    for label, cx, _, _, _ in trigs:
        if cx <= ENTRANCE[0]:
            fail(f"{label} sits at x={cx:.0f}, at or behind the entrance mark "
                 f"(x={ENTRANCE[0]:.0f}); the stone would be facing out of the hall")

    # 1. The lane the drive walks is clear the whole way along. The fixture derives its
    #    own span the same way: from the entrance and the three trigger centres, +/-400.
    xs = [ENTRANCE[0]] + [t[1] for t in trigs]
    x0, x1 = min(xs) - 400.0, max(xs) + 400.0
    worst_d, worst_who = min(
        ((dist_to_volume(t, x0 + (x1 - x0) * k / 200.0, LANE_Y), t[0])
         for t in trigs for k in range(201)), key=lambda p: p[0])
    if worst_d < MIN_LANE_CLEAR:
        fail(f"the lane the drive walks passes {worst_d:.0f} uu from {worst_who} and "
             f"{MIN_LANE_CLEAR:.0f} uu is the least that keeps a walk past a trigger "
             f"from firing it")

    # 2. Every walk in and out of one trigger clears the other two. This is the property
    #    the prompt's own layout claim -- "the hole is off any route between the other
    #    three" -- actually stands on.
    for own in trigs:
        for k in range(41):
            py = LANE_Y + (own[2] - LANE_Y) * k / 40.0
            for other in trigs:
                if other is own:
                    continue
                d = dist_to_volume(other, own[1], py)
                if d < MIN_CROSS_CLEAR:
                    fail(f"the walk in and out of {own[0]} passes {d:.0f} uu from "
                         f"{other[0]}, and {MIN_CROSS_CLEAR:.0f} uu is the least that "
                         f"keeps the runner from brushing a trigger the script never "
                         f"aimed at")

    # 3. Nothing may be waiting under a fresh runner's feet on the entrance mark.
    for t in trigs:
        d = dist_to_volume(t, ENTRANCE[0], ENTRANCE[1])
        if d < MIN_ENTRANCE_CLEAR:
            fail(f"the entrance mark is {d:.0f} uu from {t[0]}; a runner put back that "
                 f"close would fire it without walking anywhere")

    # 4. The hole is reachable from the entrance on ordinary flat ground. Everything in
    #    this hall stands on the same floor, so the rise is zero by construction --
    #    computed rather than asserted, because a later edit could give something a Z.
    rise = abs(0.0 - 0.0)
    if rise > MAX_STEP_UP:
        fail(f"the sinkhole sits {rise:.0f} uu above or below the entrance mark and the "
             f"runner only walks; {MAX_STEP_UP:.0f} uu is the most a flat route absorbs")

    # 5. The fixture rewrites the mark's step while the runner stands at the lane point
    #    beside the hoist, and REFUSES to do it with anybody near the mark.
    restage = stop_point("lane_hoist")
    d = dist_to_volume(trigs[0], restage[0], restage[1])
    if d < RESTAGE_CLEAR:
        fail(f"the spot the step is rewritten from is {d:.0f} uu from the mark and the "
             f"fixture wants {RESTAGE_CLEAR:.0f}; it would refuse to re-stage and the "
             f"whole run would be a non-verdict")

    # 6. Every stop has to be on the floor with room for a body.
    for _, where, _ in SCRIPT:
        p = stop_point(where)
        if not (FLOOR_MIN[0] + 200.0 < p[0] < FLOOR_MAX[0] - 200.0
                and FLOOR_MIN[1] + 200.0 < p[1] < FLOOR_MAX[1] - 200.0):
            fail(f"drive stop {where} at ({p[0]:.0f},{p[1]:.0f}) is off a floor of "
                 f"{FLOOR_MIN} .. {FLOOR_MAX}")

    # 7. The column of raised signs must stand clear of the lane and of every OTHER
    #    trigger's window, or the runner walks through the readout it is graded on.
    socket = (HOIST[0] + RAISE_SOCKET_LOCAL[0], HOIST[1] + RAISE_SOCKET_LOCAL[1])
    if abs(socket[1] - LANE_Y) <= abs(HOIST[1] - LANE_Y):
        fail(f"the hoist's raise socket lands at y={socket[1]:.0f}, on the LANE side of "
             f"the plate (y={HOIST[1]:.0f}); turn the plate so the column stands away "
             f"from the walk")
    for t in trigs:
        if t[0] == "the hoist plate":
            continue
        d = dist_to_volume(t, socket[0], socket[1])
        if d < GROW_XY:
            fail(f"the column of raised signs stands {d:.0f} uu from {t[0]}, inside the "
                 f"window the fixture uses to notice a trigger")

    # 8. THE DRIVE HAS TO FINISH BEFORE THE SENTINEL, and no single leg's derived
    #    deadline may be tight. The base class ends the test the moment the last
    #    scheduled checkpoint is sampled, so a walk that runs long is graded at t=200 s
    #    having done only part of what it measures -- a FAIL charged to the submission
    #    for the level's geometry. And a deadline that expires on a correct answer
    #    manufactures a drive fault, which this repo has done four times in one night.
    at = stop_point("entrance")
    total, worst_ratio, worst_leg = 0.0, 0.0, ""
    for kind, where, dwell in SCRIPT:
        to = stop_point(where)
        path = leg_path_uu(at, to)
        deadline = LEG_BASE_S + path / LEG_SPEED_UU
        real = path / EST_WALK_UU + EST_ACCEL_S
        if real / deadline > worst_ratio:
            worst_ratio, worst_leg = real / deadline, where
        if real > 0.8 * deadline:
            fail(f"the walk to {where} is {path:.0f} uu, which takes about {real:.1f} s "
                 f"against a derived deadline of {deadline:.1f} s; a deadline that tight "
                 f"manufactures a drive fault on a correct answer")
        total += real + (EST_FALL_S + FALL_HOLD_S if kind == "hole" else dwell)
        # A fall puts the runner back at the entrance, so the next leg starts there.
        at = stop_point("entrance") if kind == "hole" else to
    total += 4.0                      # the IsReady warmup and the closing grade
    if total > 0.7 * SENTINEL_S:
        fail(f"the drive models about {total:.0f} s of world time and the sentinel is at "
             f"{SENTINEL_S:.0f} s; shorten the hall or raise the sentinel")

    log(f"geometry checked: lane y={LANE_Y:.0f}, clear by {worst_d:.0f} uu (nearest "
        f"{worst_who}) from x={x0:.0f} to x={x1:.0f}; entrance mark "
        f"({ENTRANCE[0]:.0f},{ENTRANCE[1]:.0f}); raise column "
        f"({socket[0]:.0f},{socket[1]:.0f}); the drive models ~{total:.0f} s of a "
        f"{SENTINEL_S:.0f} s budget, tightest leg '{worst_leg}' at {worst_ratio:.0%} of "
        f"its own deadline")


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in CLASSES:
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, yaw=0.0, collide=False):
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
        # into a saved level on the marked-ground task, and scenery that quietly blocks
        # is indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls_name, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        env[cls_name], loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def pillar(env, x, y, height, radius, label, material):
    """A stone pillar for a sign to stand against. Set BEHIND the board -- at +X, the
    side the board's face does not read from -- so it never hides the number."""
    block(env, CYL, unreal.Vector(x + 90.0, y, 0.5 * height),
          unreal.Vector(radius / 50.0, radius / 50.0, height / 100.0), label, material)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    check_the_numbers()
    check_geometry()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = 0.5 * (FLOOR_MAX[0] + FLOOR_MIN[0])
    mid_y = 0.5 * (FLOOR_MAX[1] + FLOOR_MIN[1])

    # THE FLOOR is the one thing in this hall that collides.
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
          collide=True)

    # Stripes across the hall every 200 cm, so a pace and a distance are readable by eye.
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0] - 1.0:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.10, span_y / 100.0, 0.02), f"Stripe_{n:02d}", M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    # The lane itself is painted, so a person watching can see that the drive keeps to
    # the empty band and never brushes anything.
    block(env, CUBE, unreal.Vector(mid_x, LANE_Y, 2.0),
          unreal.Vector(span_x / 100.0, 0.6, 0.03), "TheLane", M_DARK)
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes + the painted lane")

    # ---- the hall's four signs, and the relic that is not one of them --------
    for i, (sx, sy) in enumerate(HALL_SIGNS):
        sign = place(env, "HallSignActor", unreal.Vector(sx, sy, 0.0), f"HallSign_{i}")
        sign.set_editor_property("belongs_to_the_hall", True)
        sign.set_editor_property("painted_number", 0)
        pillar(env, sx, sy, 260.0, 70.0, f"Pillar_{i}", M_FLOOR)

    relic = place(env, "HallSignActor", unreal.Vector(RELIC[0], RELIC[1], 0.0), "Relic")
    relic.set_editor_property("belongs_to_the_hall", False)
    relic.set_editor_property("painted_number", COMMITTED_RELIC)
    # A darker, heavier pillar, so a reviewer can tell at a glance which sign is the one
    # that is NOT the hall's.
    pillar(env, RELIC[0], RELIC[1], 380.0, 110.0, "RelicPillar", M_DARK)

    # ---- the things the runner walks into -----------------------------------
    stone = place(env, "EntranceStoneActor", unreal.Vector(STONE[0], STONE[1], 0.0),
                  "EntranceStone")
    stone.set_editor_property("start_number", COMMITTED_START)

    mark = place(env, "StepMarkActor", unreal.Vector(STEP_MARK[0], STEP_MARK[1], 0.0),
                 "StepMark")
    mark.set_editor_property("step_written", COMMITTED_STEP)

    place(env, "HoistPlateActor", unreal.Vector(HOIST[0], HOIST[1], 0.0), "HoistPlate")
    # The empty pillar the hoist stacks onto. Tall enough to carry the first raised sign.
    socket = (HOIST[0] + RAISE_SOCKET_LOCAL[0], HOIST[1] + RAISE_SOCKET_LOCAL[1])
    pillar(env, socket[0], socket[1], RAISE_SOCKET_LOCAL[2], 90.0, "EmptyPillar", M_FLOOR)

    place(env, "SinkholeActor", unreal.Vector(SINKHOLE[0], SINKHOLE[1], 0.0), "Sinkhole")

    # ---- where a runner walks in from, and comes back to -------------------
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(ENTRANCE[0], ENTRANCE[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # ---- backdrop + a distinct landmark at each end of the lane -------------
    block(env, CUBE, unreal.Vector(FLOOR_MAX[0] - 40.0, mid_y, 300.0),
          unreal.Vector(0.5, span_y / 100.0, 6.0), "Backdrop", M_DARK)
    for side in (FLOOR_MIN[1] + 40.0, FLOOR_MAX[1] - 40.0):
        block(env, CUBE, unreal.Vector(mid_x, side, 150.0),
              unreal.Vector(span_x / 100.0, 0.4, 3.0),
              "SideWall_S" if side < 0 else "SideWall_N", M_DARK)
    block(env, CYL, unreal.Vector(FLOOR_MIN[0] + 150.0, FLOOR_MIN[1] + 250.0, 450.0),
          unreal.Vector(1.2, 1.2, 9.0), "Landmark_TallThin", M_GLOW)
    block(env, CYL, unreal.Vector(FLOOR_MAX[0] - 250.0, FLOOR_MAX[1] - 250.0, 200.0),
          unreal.Vector(3.0, 3.0, 4.0), "Landmark_ShortFat", M_STRIPE)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-52.0, yaw=-120.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(mid_x, mid_y, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")

    place(env, "RoundHallFunctionalTest",
          unreal.Vector(FLOOR_MIN[0] + 200.0, FLOOR_MAX[1] - 200.0, 250.0),
          "RoundHallFunctionalTest")

    # ---- read back what was actually placed --------------------------------
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default, so that both halves of Enhanced Input survive and so "
             "that nothing in the room's rules is reachable from a writable path")
    log("world settings: no game mode named (inherits the project default)")

    actors = eas.get_all_level_actors()

    def tagged(tag):
        return [a for a in actors if a.actor_has_tag(tag)]

    for tag, want in (("HallSign", len(HALL_SIGNS) + 1), ("EntranceStone", 1),
                      ("StepMark", 1), ("HoistPlate", 1), ("Sinkhole", 1)):
        got = len(tagged(tag))
        if got != want:
            fail(f"{got} actor(s) tagged {tag}, expected {want}")

    hall = [a for a in tagged("HallSign")
            if bool(a.get_editor_property("belongs_to_the_hall"))]
    relics = [a for a in tagged("HallSign")
              if not bool(a.get_editor_property("belongs_to_the_hall"))]
    if len(hall) != len(HALL_SIGNS) or len(relics) != 1:
        fail(f"{len(hall)} sign(s) say they are the hall's and {len(relics)} say they are "
             f"not; the fixture is written around exactly {len(HALL_SIGNS)} and one, and "
             f"without a second kind of sign in the room there is no in-scene control")
    painted = int(relics[0].get_editor_property("painted_number"))
    if painted != COMMITTED_RELIC:
        fail(f"the relic reads back PaintedNumber {painted}, expected {COMMITTED_RELIC}")

    # NO PLACED BODY. The fixture deliberately carries no "exactly one pawn"
    # precondition -- that would hand a submission which spawns a spare runner a
    # non-verdict -- so a level that places a second body is refused HERE.
    bodies = [a for a in actors if isinstance(a, unreal.Pawn)]
    if bodies:
        fail(f"{len(bodies)} pawn(s) are placed in this level "
             f"({[b.get_actor_label() for b in bodies]}); the hall must open with exactly "
             f"the one runner the project's own rules put in, or 'never more than one "
             f"runner alive' is false before anybody does anything")
    starts = [a for a in actors if isinstance(a, unreal.PlayerStart)]
    if len(starts) != 1:
        fail(f"{len(starts)} PlayerStart(s) placed; a fresh runner has to have one "
             f"unambiguous place to come back to")

    # The committed numbers, read back off the things themselves.
    stone_back = tagged("EntranceStone")[0]
    got_start = int(stone_back.get_editor_property("start_number"))
    got_step = int(tagged("StepMark")[0].get_editor_property("step_written"))
    if got_start != COMMITTED_START or got_step != COMMITTED_STEP:
        fail(f"the level reads back start {got_start} step {got_step}, expected "
             f"{COMMITTED_START} and {COMMITTED_STEP}")

    # THE MARK ON THE FLOOR IS WHERE A FRESH RUNNER IS PUT BACK, read off the stone's own
    # component rather than assumed from the stone's location.
    centre = stone_back.get_editor_property("mark").get_world_location()
    if math.hypot(centre.x - ENTRANCE[0], centre.y - ENTRANCE[1]) > 1.0:
        fail(f"the stone's floor mark came out at ({centre.x:.0f},{centre.y:.0f}) and the "
             f"hall is solved around ({ENTRANCE[0]:.0f},{ENTRANCE[1]:.0f}); the stone is "
             f"facing the wrong way or has been moved")
    start_at = starts[0].get_actor_location()
    if math.hypot(centre.x - start_at.x, centre.y - start_at.y) > MARK_TOL:
        fail("the PlayerStart is not on the stone's floor mark; a submission that puts a "
             "fresh runner back with the level's own start would then miss the "
             f"{MARK_TOL:.0f} uu gate through no fault of its own")

    # Nothing in this hall may be STATIC and then change at runtime: the mark's face
    # follows the step (which the fixture rewrites mid-run), the signs' faces follow the
    # round number, and a Static component that moves or redraws is a PIE ERROR -- which
    # the functional test scores as a FAIL.
    movable = unreal.ComponentMobility.MOVABLE
    for a in tagged("HallSign"):
        if a.get_editor_property("face").get_editor_property("mobility") != movable:
            fail(f"{a.get_actor_label()}'s face is not MOVABLE; it is redrawn every time "
                 f"the hall's number changes")
    for tag, comps in (("EntranceStone", ("face", "mark")),
                       ("StepMark", ("face", "volume")),
                       ("HoistPlate", ("volume",)), ("Sinkhole", ("volume",))):
        a = tagged(tag)[0]
        for comp in comps:
            if a.get_editor_property(comp).get_editor_property("mobility") != movable:
                fail(f"{a.get_actor_label()}'s {comp} is not MOVABLE")

    lit = [a for a in actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")
    fixtures = [a for a in actors
                if a.get_class().get_name() == "RoundHallFunctionalTest"]
    if len(fixtures) != 1:
        fail(f"{len(fixtures)} test-harness actor(s) placed, expected exactly one")

    log(f"read back: {len(hall)} hall sign(s) + 1 relic painted {painted}; the stone "
        f"commits {got_start} with its floor mark at ({centre.x:.0f},{centre.y:.0f}); the "
        f"mark commits +{got_step}; one hoist, one hole, one PlayerStart, no placed body, "
        f"{len(lit)} lights, one fixture")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
