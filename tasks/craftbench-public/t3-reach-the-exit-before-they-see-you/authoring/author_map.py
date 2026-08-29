"""Authors L_StealthYard for t3-reach-the-exit-before-they-see-you.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A WALLED NIGHT YARD with one way out: a plate at the start line, a gate at the far
end, a mast beside the gate carrying running / away / caught, three watchers pacing
three straight rounds behind painted sight arcs, a rail truck grinding back and forth
across the line from one round to one standing place, three crate stacks and one long
wall.

THE WHOLE TASK HANGS ON GEOMETRY, so this script does not place numbers and hope. It
SOLVES the same geometry the fixture solves -- where the drive can stand so that a
watcher's cone crosses it MID-LEG (never at a turn), where the truck's rail genuinely
lies across a sightline and then lets go of it, and where the same standing place means
opposite things on the two watches -- and it REFUSES TO SAVE if any of it fails to come
out. Every one of those checks is the fixture's own arithmetic in Python: if the two
disagree the level is wrong, not the fixture, and the run would end as a
HARNESS-PRECONDITION with nobody the wiser about why.

FIVE THINGS ARE SOLID AND EVERYTHING ELSE IS PAINT. The crates, the wall and the truck
block a line; the watchers are solid to each other for walking but the yard promises
they never block a line, which is why the fixture's footprint model does not include
them and the reference puts them in its trace's ignore list. Every other prop -- the
posts, the lamps, the mast, the plate, the gate, the stripes, the arcs, the backdrop --
is NON-COLLIDING on every channel and profile, and the script reads the level back and
refuses to save if any of them still answers a query.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (the 2026-08-17 unplayable-play-lane finding) -- the mannequin is
visible, animated and drivable by hand with WASD.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-reach-the-exit-before-they-see-you"
MAP_PKG = f"/Game/Maps/{TASK}/L_StealthYard"

# ----------------------------------------------------------------- the yard's shape
FLOOR_MIN = (-7400.0, -3400.0)
FLOOR_MAX = (7400.0, 5600.0)
STRIPE_EVERY = 400.0

LANE_Y = -1400.0
PLATE_AT = (-5800.0, LANE_Y)
GATE_AT = (5800.0, LANE_Y)
MAST_AT = (5800.0, -700.0)
START_AT = (-5800.0, -1900.0)

# (tag, x of the -X post, x of the +X post, y). Sorted SOUTH to NORTH, because that is
# how the fixture names them: the LANE round, the FAR round, and the WALLED one. The
# fixture re-derives that ordering from the posts' own Y, so it is the GEOMETRY that
# decides which round is which and never these names.
ROUNDS = (
    ("RoundCentre", -1200.0, 1200.0, 200.0),
    ("RoundNorth", -1200.0, 1200.0, 2000.0),
    ("RoundWalled", -1000.0, 1000.0, 4200.0),
)

# (label, reach, half-angle deg, base pace, round tag). THE THREE ARE NOT ALIKE, and
# none of the three numbers is written anywhere the agent can read except on the
# watcher itself.
#
#   NEAR   walks the lane round on the FIRST watch. Its reach x sin(view width) is
#          1,286 uu against the lane's 1,600 uu offset, so on the first watch it can
#          NEVER see any point of the lane -- which is what makes the first away round
#          winnable and the split spot invisible.
#   FAR    walks the far round on the first watch and takes the lane round at the watch
#          change with its reach multiplied by 1.2 -> 3,720, whose reach x sin(30 deg)
#          is 1,860 and therefore CAN hold the lane. That single multiplier is the
#          whole of "the same standing place means opposite things".
#   SENTRY never moves rounds and is the IN-SCENE NEGATIVE CONTROL: the largest reach
#          and the widest view width in the yard, behind a solid wall.
#
# NEAR'S PACE AND THE TRUCK'S SPEED ARE NOT FREE NUMBERS. They set the beat between the
# covering watcher's lap and the truck's rail, and the drive can only step into the
# shadow spot at a moment when the two line up: the cone must already hold the spot, the
# truck must already be across the line, and it must stay there past the gate's cover
# floor and then let go while the cone still holds. Swept offline over the whole beat
# (see notes.md): at pace 180 / truck 200 exactly ONE such departure moment exists in
# 400 s, which is a coincidence rather than a staging -- a small difference between the
# engine's start poses and the model's would move it out from under the drive. At pace
# 120 / truck 150 there are FOUR, the first at ~65 s, with a 7.33 s cone window and
# 2.31 s of truck cover. Change either number and re-run the sweep.
WATCHERS = (
    ("Near", 2000.0, 40.0, 120.0, "RoundCentre"),
    ("Far", 3100.0, 30.0, 220.0, "RoundNorth"),
    ("Sentry", 6400.0, 75.0, 260.0, "RoundWalled"),
)
# What the fixture's watch change does, mirrored here so the checks below can prove the
# geometry survives the SECOND watch as well as the first.
RESTAGE_REACH_MUL = 1.2
RESTAGE_ANGLE_MUL = 0.6
RESTAGE_PACE_MUL = 1.25

# (label, x, y, half-x, half-y, half-z). SOLID, floor to well above head height.
# The WALL is the control's cover and the only load-bearing static occluder; the crates
# are yard clutter placed deliberately CLEAR of every sightline a gate depends on, so
# no gate can ever turn on a grazing crate corner.
BLOCKERS = (
    ("Wall", 0.0, 3200.0, 4600.0, 150.0, 220.0),
    ("CrateWest", -3000.0, -400.0, 600.0, 400.0, 260.0),
    ("CrateSouth", 1900.0, -2400.0, 400.0, 400.0, 260.0),
    ("CrateEast", 4600.0, 700.0, 400.0, 400.0, 260.0),
)

# The rail truck. Its rail runs along Y, west of the lane round's middle, so it lies
# across the line from that round to the standing place the fixture solves for -- and
# NEVER between that round and the split spot, which would make the split-spot gate
# measure the truck instead of the two watchers' eyes.
TRUCK_AT = (-760.0, -585.0)
TRUCK_HALF = (350.0, 150.0, 220.0)
TRUCK_RAIL_HALF = (0.0, 415.0, 0.0)
TRUCK_SPEED = 150.0        # see the note on WATCHERS: this sets the beat

POST_STAND_Z = 150.0        # half the post's 300 cm height
# A WATCHER STANDS ON THE FLOOR, NOT IN IT, AND NOT ON IT EITHER.
#
# Its capsule is CENTRED on the actor location and is 180 cm tall, so 90.0 would put
# the capsule's bottom face exactly on the floor's top face. That is not standing on
# the floor, it is starting every frame in contact with it: AStealthWatcherActor::Tick
# walks by a SWEPT SetActorLocation, and ShouldIgnoreHitResult only forgives a
# start-in-contact hit when the move is heading OUT of it (MoveDot > 0). A horizontal
# move against the floor's up-normal has MoveDot == 0, so the sweep is refused at zero
# distance, every frame, for ever -- and the watcher never walks its round at all.
# Measured on the sibling task t2-alarm-escalates-and-cools-down 2026-08-19: both
# guards stood on their spawn points for a whole run and the fixture timed out a phase
# deadline that named the drive rather than the placement.
WATCHER_STAND_Z = 95.0
WATCHER_FOOT_CLEARANCE_UU = 5.0

# Mirrors of the fixture's own floors, so "the yard fits the fixture" is MEASURED here
# rather than discovered at run time as a HARNESS-PRECONDITION.
MIN_CROSS_WINDOW_S = 1.0
MIN_TURN_CLEARANCE_S = 2.0
MIN_SHADOW_WINDOW_S = 3.0
MIN_TRUCK_COVER_S = 1.5
ROUTE_FROM_ROUND_UU = 400.0
ROUTE_FROM_SOLID_UU = 250.0
OTHER_WATCHER_MARGIN = 1.25

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"STEALTHYARD- {msg}")


def fail(msg):
    unreal.log_error(f"STEALTHYARD-ERROR {msg}")
    raise SystemExit(1)


# ----------------------------------------------------------------------- the geometry
# These functions are the fixture's own arithmetic, in Python.

def seg_hits_rect(p, q, c, h):
    """2-D segment versus axis-aligned rectangle -- the fixture's SegmentHitsRect."""
    lo, hi = 0.0, 1.0
    d = (q[0] - p[0], q[1] - p[1])
    for i in range(2):
        if abs(d[i]) < 1e-9:
            if p[i] < c[i] - h[i] or p[i] > c[i] + h[i]:
                return False
            continue
        t1 = (c[i] - h[i] - p[i]) / d[i]
        t2 = (c[i] + h[i] - p[i]) / d[i]
        if t1 > t2:
            t1, t2 = t2, t1
        lo = max(lo, t1)
        hi = min(hi, t2)
        if lo > hi:
            return False
    return True


def dist_point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    t = 0.0 if denom <= 0.0 else max(0.0, min(1.0,
        ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denom))
    return math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dy * t))


def dist_point_rect(p, c, h):
    return math.hypot(max(0.0, abs(p[0] - c[0]) - h[0]),
                      max(0.0, abs(p[1] - c[1]) - h[1]))


def static_rects(include_truck_sweep=False):
    r = [((b[1], b[2]), (b[3], b[4])) for b in BLOCKERS]
    if include_truck_sweep:
        r.append((TRUCK_AT, (TRUCK_HALF[0] + abs(TRUCK_RAIL_HALF[0]),
                             TRUCK_HALF[1] + abs(TRUCK_RAIL_HALF[1]))))
    return r


def can_see(eye, facing, reach, half_deg, point, rects):
    """The disclosed predicate: flat, inclusive at both edges, nothing solid between."""
    vx, vy = point[0] - eye[0], point[1] - eye[1]
    d = math.hypot(vx, vy)
    if d > reach:
        return False
    if d > 1e-6:
        cos = (facing[0] * vx + facing[1] * vy) / d
        if math.degrees(math.acos(max(-1.0, min(1.0, cos)))) > half_deg:
            return False
    for c, h in rects:
        if seg_hits_rect(eye, point, c, h):
            return False
    return True


def round_by_tag(tag):
    for t, ax, bx, y in ROUNDS:
        if t == tag:
            return (ax, bx, y)
    fail(f"no round tagged {tag}")


def ever_sees(reach, half_deg, tag, point, rects, phases=25):
    """Could a watcher on this round hold this place from ANY phase, facing either way?"""
    ax, bx, y = round_by_tag(tag)
    for k in range(phases):
        x = ax + (bx - ax) * k / (phases - 1)
        for facing in ((1.0, 0.0), (-1.0, 0.0)):
            if can_see((x, y), facing, reach, half_deg, point, rects):
                return True
    return False


def window_beyond_west_end(reach, half_deg, pace, ax, bx, y, xs, p):
    """The closed form the whole layout is solved from. A watcher walking a straight
    round facing along it holds a stationary target at perpendicular offset p and
    along-track lead b inside its cone while b >= p/tan(theta) and inside its reach
    while b <= sqrt(R^2 - p^2). Both ends are MID-LEG exactly when both bounds lie
    strictly inside the round -- and the RETURN pass has the target more than 90 deg
    off the facing whatever the reach, so there is exactly ONE window per lap. That is
    why every standing place in this yard sits beyond the end of a round rather than
    beside it: beside it there are two windows a lap, the shorter one grazing, and a
    one-frame sampling difference changes an edge COUNT instead of an edge TIME."""
    th = math.radians(min(max(half_deg, 0.1), 89.0))
    cone = p / math.tan(th)
    inner = reach * reach - p * p
    if inner <= 0.0:
        return None
    reach_bound = math.sqrt(inner)
    if reach_bound <= cone:
        return None
    width = reach_bound - cone
    slack = (bx - ax) - width
    if slack <= 0.0:
        return None
    entry_x = xs + reach_bound
    exit_x = xs + cone
    if not (ax < exit_x < entry_x < bx):
        return None
    return dict(duration=width / pace,
                clear_east=(bx - entry_x) / pace,
                clear_west=(exit_x - ax) / pace,
                entry_x=entry_x, exit_x=exit_x, cone=cone, reach_bound=reach_bound)


def truck_cover_seconds(xs, p, round_y, entry_x, exit_x):
    """How long the truck's rail lies across the line from the covering watcher to a
    standing place, measured at three phases of the window and taken at its WORST --
    and whether it ever LETS GO of that line. A rail that covers the line end to end
    never clears, so the board's half of the shadow gate could never fire, and a rail
    that barely brushes it gives nothing to grade."""
    rail_len = 2.0 * math.hypot(TRUCK_RAIL_HALF[0], TRUCK_RAIL_HALF[1])
    rail_s = rail_len / max(TRUCK_SPEED, 1.0)
    worst = 1e30
    always = False
    for k in range(3):
        xw = exit_x + (entry_x - exit_x) * k / 2.0
        run = longest = blocked = 0
        samples = 60
        for j in range(samples + 1):
            f = j / samples * 2.0 - 1.0
            at = (TRUCK_AT[0] + TRUCK_RAIL_HALF[0] * f,
                  TRUCK_AT[1] + TRUCK_RAIL_HALF[1] * f)
            if seg_hits_rect((xw, round_y), (xs, round_y - p), at,
                             (TRUCK_HALF[0], TRUCK_HALF[1])):
                run += 1
                blocked += 1
                longest = max(longest, run)
            else:
                run = 0
        if blocked > samples - 2:
            always = True
        worst = min(worst, longest / samples * rail_s)
    return (None if always else worst)


def solve_shadow_spot():
    """The fixture's SolveSpots, first half. Returns the place the drive stands while
    the truck makes a shadow, or fails the build."""
    _, reach, half_deg, pace, tag = WATCHERS[0]
    ax, bx, y = round_by_tag(tag)
    rects = static_rects()
    best = None
    tried = 0
    for i in range(53):
        p = 300.0 + 25.0 * i
        # The standing place is solved FROM the window, not the other way round: put
        # the window in the MIDDLE of the round and read off where the target has to
        # be for that to happen.
        th = math.radians(min(max(half_deg, 0.1), 89.0))
        cone = p / math.tan(th)
        inner = reach * reach - p * p
        if inner <= 0.0:
            continue
        reach_bound = math.sqrt(inner)
        if reach_bound <= cone:
            continue
        width = reach_bound - cone
        slack = (bx - ax) - width
        if slack <= 0.0:
            continue
        xs = bx - slack * 0.5 - reach_bound
        w = window_beyond_west_end(reach, half_deg, pace, ax, bx, y, xs, p)
        if w is None:
            continue
        tried += 1
        if w["duration"] < MIN_SHADOW_WINDOW_S:
            continue
        if min(w["clear_east"], w["clear_west"]) < MIN_TURN_CLEARANCE_S:
            continue
        # The EAST pass must give nothing, or the window is two windows a lap.
        if xs - ax >= cone:
            continue
        spot = (xs, y - p)
        # Clear of every round, every solid thing and the truck's whole swept rail.
        if any(dist_point_segment(spot, (rax, ry), (rbx, ry)) < ROUTE_FROM_ROUND_UU
               for _, rax, rbx, ry in ROUNDS):
            continue
        if any(dist_point_rect(spot, c, h) < ROUTE_FROM_SOLID_UU
               for c, h in static_rects(include_truck_sweep=True)):
            continue
        # NOBODY UNPLANNED IS LOOKING: no watcher other than the one this window names.
        others = False
        for label, r2, a2, _p2, t2 in WATCHERS[1:]:
            if ever_sees(r2, a2, t2, spot, rects):
                others = True
        if others:
            continue
        cover = truck_cover_seconds(xs, p, y, w["entry_x"], w["exit_x"])
        # 1.5x, matching the fixture: the GATE wants MIN_TRUCK_COVER_S of cover, but
        # the DRIVE only commits the runner to the walk in when it can prove the truck
        # will still be across the line half a second past that floor and will then let
        # go while the cone still holds. A window sized exactly to the gate's floor
        # never ripens, and the run reports a staging fault instead of a grade.
        if cover is None or cover < MIN_TRUCK_COVER_S * 1.5:
            continue
        score = min(w["duration"], 12.0) + min(min(w["clear_east"], w["clear_west"]),
                                               8.0) + min(cover, 4.0)
        if best is None or score > best[0]:
            best = (score, p, xs, spot, w, cover)
    if best is None:
        fail(f"no standing place in this yard gives the lane round's watcher "
             f"({WATCHERS[0][0]}: reach {reach:.0f}, view {half_deg:.0f} deg, pace "
             f"{pace:.0f}) a continuous {MIN_SHADOW_WINDOW_S:.1f}s of sight with "
             f"{MIN_TURN_CLEARANCE_S:.1f}s of clearance to both turns AND the truck's "
             f"rail lying across the line for {MIN_TRUCK_COVER_S:.1f}s and then "
             f"letting go of it ({tried} offsets had a window at all). The shadow gate "
             f"would have nothing to measure")
    _, p, xs, spot, w, cover = best
    log(f"shadow spot solved at ({spot[0]:.0f},{spot[1]:.0f}), offset {p:.0f} uu: "
        f"{w['duration']:.2f}s of continuous sight, clearance {w['clear_east']:.2f}s / "
        f"{w['clear_west']:.2f}s to the two turns, truck cover {cover:.2f}s (floor "
        f"{MIN_TRUCK_COVER_S:.1f}s)")
    return spot, w, cover


def solve_split_spot():
    """The fixture's SolveSpots, second half: the identical standing place walked on
    BOTH watches with a DIFFERENT watcher covering it."""
    lane_tag = WATCHERS[0][4]
    ax, bx, y = round_by_tag(lane_tag)
    # The numbers the sergeant WILL set: the far watcher takes the lane round with its
    # reach multiplied.
    reach = WATCHERS[1][1] * RESTAGE_REACH_MUL
    half_deg = WATCHERS[1][2]
    pace = WATCHERS[1][3]
    p = abs(y - LANE_Y)
    th = math.radians(half_deg)
    cone = p / math.tan(th)
    inner = reach * reach - p * p
    if inner <= 0.0:
        fail(f"after the watch change the lane round's watcher reaches {reach:.0f} uu "
             f"and the lane is {p:.0f} uu off its round; it can never hold the lane at "
             f"all")
    reach_bound = math.sqrt(inner)
    if reach_bound <= cone:
        fail(f"after the watch change the lane round's watcher reaches {reach:.0f} uu "
             f"through {half_deg:.0f} deg, so at the lane's {p:.0f} uu offset its view "
             f"width lets go ({cone:.0f} uu) further out than its reach does "
             f"({reach_bound:.0f} uu) and there is NO crossing window at all -- the "
             f"gate this task is built around would be unreachable")
    width = reach_bound - cone
    slack = (bx - ax) - width
    if slack <= 0.0:
        fail(f"the crossing window is {width:.0f} uu wide against a round only "
             f"{bx - ax:.0f} uu long; it cannot open and close between two turns")
    split_x = ax + slack * 0.5 + reach_bound
    spot = (split_x, LANE_Y)
    dur = width / pace
    clear = (slack * 0.5) / pace
    if dur < MIN_CROSS_WINDOW_S or clear < MIN_TURN_CLEARANCE_S:
        fail(f"the staged crossing gives {dur:.2f}s of continuous sight with "
             f"{clear:.2f}s of clearance to the nearest turn, against floors of "
             f"{MIN_CROSS_WINDOW_S:.1f}s and {MIN_TURN_CLEARANCE_S:.1f}s. A window "
             f"this tight can be straddled by a CORRECT submission, which is a "
             f"manufactured failure, not a measurement")
    # ... and NOBODY may hold it on the FIRST watch.
    rects = static_rects()
    for label, r, a, _pace, tag in WATCHERS:
        if ever_sees(r, a, tag, spot, rects):
            fail(f"{label} can already hold the split spot ({spot[0]:.0f},"
                 f"{spot[1]:.0f}) on the FIRST watch; the whole point of that place is "
                 f"that it means opposite things on the two watches")
    # ... and the truck must NOT be on that line ANYWHERE INSIDE THE WINDOW, or the
    # gate measures the truck instead of the two watchers' eyes. Checked over the
    # window widened by 300 uu of watcher travel at each end, because the window's own
    # ends are where a one-frame difference lands.
    win_lo = ax + slack * 0.5 - 300.0
    win_hi = bx - slack * 0.5 + 300.0
    for k in range(41):
        xw = win_lo + (win_hi - win_lo) * k / 40.0
        if seg_hits_rect((xw, y), spot, TRUCK_AT,
                         (TRUCK_HALF[0] + abs(TRUCK_RAIL_HALF[0]),
                          TRUCK_HALF[1] + abs(TRUCK_RAIL_HALF[1]))):
            fail(f"the truck's swept rail lies across the line from ({xw:.0f},{y:.0f}) "
                 f"to the split spot, inside the crossing window; "
                 f"EachWatcherSeesWithItsOwnEyes and SeenTheMomentTheyCross would be "
                 f"measuring the truck instead of the two watchers' eyes")
    log(f"the truck's swept rail clears every sightline to the split spot over the "
        f"window x[{win_lo:.0f}..{win_hi:.0f}]")
    log(f"split spot solved at ({spot[0]:.0f},{spot[1]:.0f}): invisible to all three "
        f"on watch 1; on watch 2 the covering watcher holds it for {dur:.2f}s with "
        f"{clear:.2f}s of clearance to both turns (reach {reach:.0f}, view "
        f"{half_deg:.0f} deg)")
    return spot, dur, clear


def check_control():
    """The IN-SCENE NEGATIVE CONTROL has to be worth something: the walled sentry must
    dominate every other watcher AFTER the watch change's multipliers, must be blind to
    every point of the route WITH the wall, and must see a great deal of it WITHOUT
    the wall -- otherwise a range-only sight test would barely light it and the control
    measures nothing."""
    s_label, s_reach, s_angle, _s_pace, s_tag = WATCHERS[2]
    for label, reach, angle, _pace, _tag in WATCHERS[:2]:
        most_reach = reach * RESTAGE_REACH_MUL
        if s_reach < most_reach * OTHER_WATCHER_MARGIN or s_angle <= angle:
            fail(f"the walled sentry (reach {s_reach:.0f}, view {s_angle:.0f} deg) "
                 f"does not dominate {label} (at most reach {most_reach:.0f}, view "
                 f"{angle:.0f} deg after the watch change)")
    route = [(PLATE_AT[0] + (GATE_AT[0] - PLATE_AT[0]) * k / 24.0, LANE_Y)
             for k in range(25)]
    with_wall = static_rects()
    no_wall = [r for r in with_wall if r[0] != (BLOCKERS[0][1], BLOCKERS[0][2])]
    seen_with = sum(1 for p in route if ever_sees(s_reach, s_angle, s_tag, p, with_wall))
    seen_without = sum(1 for p in route if ever_sees(s_reach, s_angle, s_tag, p, no_wall))
    if seen_with != 0:
        fail(f"the walled sentry can see {seen_with} of {len(route)} route points even "
             f"WITH the wall; its lamp is required dark at every checkpoint, so a yard "
             f"where it CAN see somebody would fail a correct submission")
    if seen_without < len(route) // 3:
        fail(f"the walled sentry would hold only {seen_without} of {len(route)} route "
             f"points even with nothing in the way; a range-only or occlusion-blind "
             f"sight test would barely light it and the control measures almost "
             f"nothing")
    log(f"control checked: the walled sentry holds {seen_without}/{len(route)} route "
        f"points with the wall taken away and {seen_with}/{len(route)} with it there")


def check_ends():
    """The start line and the gate must be out of every live cone at EVERY staging, or
    a watcher that can see the start line ends every round on the frame it begins and
    one that can see the gate makes both away endings impossible."""
    rects = static_rects()
    for name, spot in (("the start plate", PLATE_AT), ("the gate", GATE_AT),
                       ("PlayerStart", START_AT)):
        for label, reach, angle, _pace, tag in WATCHERS:
            widest = reach * RESTAGE_REACH_MUL
            nearest = min(dist_point_segment(spot, (ax, y), (bx, y))
                          for _t, ax, bx, y in ROUNDS)
            if label == WATCHERS[2][0]:
                continue   # the wall answers for the sentry (check_control)
            if nearest < widest * OTHER_WATCHER_MARGIN:
                fail(f"{name} is {nearest:.0f} uu from the nearest round against a "
                     f"reach of up to {widest:.0f} ({nearest / widest:.2f}x, and "
                     f"{OTHER_WATCHER_MARGIN:.2f}x is the floor)")
            if ever_sees(widest, angle, tag, spot, rects):
                fail(f"{label} can hold {name} at some phase of round {tag}")
    log("start line, gate and PlayerStart are out of every live cone at both stagings")


def check_route_and_rounds():
    """Two clearances the drive owes the supplied actors, neither of which the window
    arithmetic covers: a watcher moves SWEPT and would jam against anything solid, and
    the watchers are solid to each other for walking even though they never block a
    LINE."""
    for tag, ax, bx, y in ROUNDS:
        for label, x, by, hx, hy, _hz in BLOCKERS:
            d = dist_point_rect(((ax + bx) * 0.5, y), (x, by), (hx, hy))
            near = min(dist_point_rect((ax + (bx - ax) * k / 20.0, y), (x, by), (hx, hy))
                       for k in range(21))
            if near < 200.0:
                fail(f"round {tag} passes within {near:.0f} uu of {label}; a watcher "
                     f"moves swept and would jam against it, then fail "
                     f"TheYardIsNotYoursToRewire's on-its-own-round clause for the "
                     f"rest of the run")
        near_truck = min(dist_point_rect((ax + (bx - ax) * k / 20.0, y), TRUCK_AT,
                                         (TRUCK_HALF[0] + abs(TRUCK_RAIL_HALF[0]),
                                          TRUCK_HALF[1] + abs(TRUCK_RAIL_HALF[1])))
                         for k in range(21))
        if near_truck < 200.0:
            fail(f"round {tag} passes within {near_truck:.0f} uu of the truck's swept "
                 f"footprint")
    for i, (t1, a1, b1, y1) in enumerate(ROUNDS):
        for t2, a2, b2, y2 in ROUNDS[i + 1:]:
            if abs(y1 - y2) < 200.0:
                fail(f"rounds {t1} and {t2} pass within {abs(y1 - y2):.0f} uu of each "
                     f"other; the watchers are solid to each other for walking")
    # The lane itself must be walkable: nothing solid on it, with room either side.
    for label, x, by, hx, hy, _hz in BLOCKERS:
        for k in range(61):
            p = (PLATE_AT[0] + (GATE_AT[0] - PLATE_AT[0]) * k / 60.0, LANE_Y)
            if dist_point_rect(p, (x, by), (hx, hy)) < ROUTE_FROM_SOLID_UU:
                fail(f"the lane passes within {ROUTE_FROM_SOLID_UU:.0f} uu of {label} "
                     f"at x={p[0]:.0f}")
    for k in range(61):
        p = (PLATE_AT[0] + (GATE_AT[0] - PLATE_AT[0]) * k / 60.0, LANE_Y)
        if dist_point_rect(p, TRUCK_AT, (TRUCK_HALF[0] + abs(TRUCK_RAIL_HALF[0]),
                                         TRUCK_HALF[1] + abs(TRUCK_RAIL_HALF[1]))) \
                < ROUTE_FROM_SOLID_UU:
            fail(f"the lane passes within {ROUTE_FROM_SOLID_UU:.0f} uu of the truck's "
                 f"swept footprint at x={p[0]:.0f}")
    log("rounds clear every solid thing and each other; the lane clears the truck and "
        "every crate")


def report_safe_bands():
    """The lane x-ranges nobody can ever see, on both watches. The fixture hops between
    them, so a lane with no safe band on the second watch would leave every long
    transit ungoverned."""
    for watch in (0, 1):
        cast = []
        for i, (label, reach, angle, pace, tag) in enumerate(WATCHERS):
            if watch == 0:
                cast.append((label, reach, angle, tag))
            elif i == 0:
                cast.append((label, reach, angle * RESTAGE_ANGLE_MUL, WATCHERS[1][4]))
            elif i == 1:
                cast.append((label, reach * RESTAGE_REACH_MUL, angle, WATCHERS[0][4]))
            else:
                cast.append((label, reach, angle, tag))
        rects = static_rects()
        bands = []
        open_at = None
        x = PLATE_AT[0]
        while x <= GATE_AT[0] + 1.0:
            p = (x, LANE_Y)
            seen = any(ever_sees(r, a, t, p, rects) for _l, r, a, t in cast)
            if not seen and open_at is None:
                open_at = x
            elif seen and open_at is not None:
                if x - 100.0 - open_at > 400.0:
                    bands.append((open_at, x - 100.0))
                open_at = None
            x += 100.0
        if open_at is not None and GATE_AT[0] - open_at > 400.0:
            bands.append((open_at, GATE_AT[0]))
        if not bands:
            fail(f"watch {watch + 1} leaves no stretch of the lane that nobody can "
                 f"ever see; every long transit would be ungoverned and the drive "
                 f"would end rounds by accident")
        log(f"watch {watch + 1}: {len(bands)} safe lane band(s) "
            f"{[(round(a), round(b)) for a, b in bands]}")


# --------------------------------------------------------------------------- authoring

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
    for cls_name in ("StealthWatcherActor", "StealthPostActor", "StealthMastActor",
                     "StealthStartPlateActor", "StealthGateActor",
                     "StealthBlockerActor", "StealthTruckActor",
                     "StealthYardFunctionalTest"):
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
        # The PROFILE, not just the enum: on an earlier task set_collision_enabled
        # alone did not survive into the saved level, and paint that quietly blocks a
        # sightline is indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def paint_stripe(env, a, b, label, material, width=14.0):
    """A thin painted line on the floor from a to b. Never collides."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1.0:
        return
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    block(env, CUBE,
          unreal.Vector((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, 2.0),
          unreal.Vector(length / 100.0, width / 100.0, 0.04), label, material, yaw=yaw)


def paint_sight_arc(env, apex, facing_deg, half_deg, reach, label, material):
    """The wedge one watcher can see, drawn on the floor from the end of its round: the
    two edges of its view and the arc at its own reach. The three watchers' wedges are
    visibly different shapes, so the level is honest about what it is asking."""
    for sign in (-1.0, 1.0):
        ang = math.radians(facing_deg + sign * half_deg)
        paint_stripe(env, apex,
                     (apex[0] + math.cos(ang) * reach, apex[1] + math.sin(ang) * reach),
                     f"{label}_edge{'P' if sign > 0 else 'M'}", material)
    steps = 22
    prev = None
    for k in range(steps + 1):
        ang = math.radians(facing_deg - half_deg + 2.0 * half_deg * k / steps)
        here = (apex[0] + math.cos(ang) * reach, apex[1] + math.sin(ang) * reach)
        if prev is not None:
            paint_stripe(env, prev, here, f"{label}_arc{k:02d}", material)
        prev = here


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # EVERY CHECK BEFORE ANY BYTE IS WRITTEN. A level that cannot be graded is worse
    # than no level: it reports as a HARNESS-PRECONDITION halfway through a paid run.
    check_control()
    check_ends()
    check_route_and_rounds()
    shadow, shadow_window, shadow_cover = solve_shadow_spot()
    split, split_dur, split_clear = solve_split_spot()
    report_safe_bands()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    floor = block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
                  collide=True)
    # THE FLOOR'S TOP FACE, MEASURED off the placed block. Everything that has to stand
    # on the floor is derived from this number, and "a 100 uu cube centred at z=-50 has
    # its top at z=0" is arithmetic in a comment, which is not evidence.
    f_origin, f_extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = f_origin.z + f_extent.z
    log(f"floor {span_x:.0f}x{span_y:.0f}, top face measured at z={floor_top_z:.1f}")

    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"yard {span_x:.0f}x{span_y:.0f} + {n} stripes every {STRIPE_EVERY:.0f} cm, so "
        f"speed and distance read by eye")

    # THE LANE the runner walks, painted end to end.
    paint_stripe(env, PLATE_AT, GATE_AT, "Lane", M_GLOW, width=40.0)

    # POSTS. Two per round, each carrying the tag its round is known by.
    for tag, ax, bx, y in ROUNDS:
        for suffix, px in (("A", ax), ("B", bx)):
            post = eas.spawn_actor_from_class(
                env["StealthPostActor"], unreal.Vector(px, y, POST_STAND_Z),
                unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if post is None:
                fail(f"could not place post {tag}{suffix}")
            post.set_actor_label(f"Post_{tag}_{suffix}")
            post.set_editor_property("tags", [unreal.Name(tag)])
        marked = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(marked) != 2:
            fail(f"{len(marked)} actor(s) tagged {tag}, expected exactly two")
        paint_stripe(env, (ax, y), (bx, y), f"RoundLine_{tag}", M_HAZARD, width=26.0)
    log(f"{len(ROUNDS) * 2} posts placed and tagged; each round painted on the floor")

    # WATCHERS.
    for idx, (label, reach, half_deg, pace, tag) in enumerate(WATCHERS):
        ax, _bx, y = round_by_tag(tag)
        w = eas.spawn_actor_from_class(
            env["StealthWatcherActor"], unreal.Vector(ax, y, WATCHER_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if w is None:
            fail(f"could not place watcher {label}")
        w.set_actor_label(f"StealthWatcher_{idx + 1}_{label}")
        # STOOD ON THE FLOOR, MEASURED, NOT WORKED OUT -- see WATCHER_STAND_Z.
        w_origin, w_extent = w.get_actor_bounds(only_colliding_components=True)
        foot_offset = (w_origin.z - w_extent.z) - w.get_actor_location().z
        want_z = floor_top_z + WATCHER_FOOT_CLEARANCE_UU - foot_offset
        if abs(want_z - WATCHER_STAND_Z) > 0.01:
            log(f"watcher {label}: hull reaches {-foot_offset:.1f} uu below its own "
                f"origin, so WATCHER_STAND_Z {WATCHER_STAND_Z:.1f} is corrected to "
                f"{want_z:.1f}")
            w.set_actor_location(unreal.Vector(ax, y, want_z), False, True)
        w_origin, w_extent = w.get_actor_bounds(only_colliding_components=True)
        w_bottom = w_origin.z - w_extent.z
        if w_bottom < floor_top_z + 1.0:
            fail(f"watcher {label}'s collision reaches down to z={w_bottom:.1f}, at or "
                 f"below the floor's top face at z={floor_top_z:.1f}; every swept move "
                 f"its Tick makes would be refused at zero distance and it would never "
                 f"walk its round at all")
        w.set_editor_property("sight_reach_uu", reach)
        w.set_editor_property("sight_half_angle_deg", half_deg)
        w.set_editor_property("base_pace_uu_per_sec", pace)
        w.set_editor_property("pace_uu_per_sec", pace)
        w.set_editor_property("round_tag", tag)
        if w.get_editor_property("hull").get_editor_property("mobility") != \
                unreal.ComponentMobility.MOVABLE:
            fail(f"watcher {label} is not MOVABLE; it walks its round every frame and "
                 f"PIE scores moving a static actor as a failed test")
        # Its own view, painted on the floor at BOTH ends of the round it walks, so the
        # difference between the three watchers is visible at a glance.
        ax2, bx2, y2 = round_by_tag(tag)
        look = (M_GLOW, M_HAZARD, M_DARK)[idx % 3]
        for facing, suffix, apex in ((0.0, "F", (bx2, y2)), (180.0, "B", (ax2, y2))):
            paint_sight_arc(env, apex, facing, half_deg, reach,
                            f"Sight_{label}_{suffix}", look)
        # And the one line that matters most: the furthest to one side this watcher can
        # EVER hold somebody, reach x sin(view width), drawn parallel to its round.
        limit = reach * math.sin(math.radians(half_deg))
        paint_stripe(env, (ax2 - reach, y2 - limit), (bx2 + reach, y2 - limit),
                     f"Limit_{label}", M_DARK, width=18.0)
    log(f"three watchers placed: "
        f"{[(g[0], round(g[1] * math.sin(math.radians(g[2])))) for g in WATCHERS]} "
        f"(label, furthest to one side it can ever hold somebody)")

    # SOLID BLOCKS: the wall and the crates.
    for label, bx, by, hx, hy, hz in BLOCKERS:
        b = eas.spawn_actor_from_class(
            env["StealthBlockerActor"], unreal.Vector(bx, by, 0.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if b is None:
            fail(f"could not place {label}")
        b.set_actor_label(f"StealthBlocker_{label}")
        b.set_editor_property("block_half_extent_uu", unreal.Vector(hx, hy, hz))

    # THE RAIL TRUCK.
    truck = eas.spawn_actor_from_class(
        env["StealthTruckActor"], unreal.Vector(TRUCK_AT[0], TRUCK_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if truck is None:
        fail("could not place the truck")
    truck.set_actor_label("StealthTruck")
    truck.set_editor_property("truck_half_extent_uu", unreal.Vector(*TRUCK_HALF))
    truck.set_editor_property("rail_half_span_uu", unreal.Vector(*TRUCK_RAIL_HALF))
    truck.set_editor_property("rail_speed_uu_per_sec", TRUCK_SPEED)
    paint_stripe(env, (TRUCK_AT[0], TRUCK_AT[1] - TRUCK_RAIL_HALF[1]),
                 (TRUCK_AT[0], TRUCK_AT[1] + TRUCK_RAIL_HALF[1]), "Rail", M_DARK,
                 width=30.0)

    # THE PLATE, THE GATE AND THE MAST.
    plate = eas.spawn_actor_from_class(
        env["StealthStartPlateActor"], unreal.Vector(PLATE_AT[0], PLATE_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if plate is None:
        fail("could not place the start plate")
    plate.set_actor_label("StealthStartPlate")
    plate.set_editor_property("round_index", 0)

    # YAW 90 so the gateway's opening faces along the lane: the uprights stand either
    # side of the runner instead of across the path.
    gate = eas.spawn_actor_from_class(
        env["StealthGateActor"], unreal.Vector(GATE_AT[0], GATE_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    if gate is None:
        fail("could not place the gate")
    gate.set_actor_label("StealthGate")

    mast = eas.spawn_actor_from_class(
        env["StealthMastActor"], unreal.Vector(MAST_AT[0], MAST_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if mast is None:
        fail("could not place the mast")
    mast.set_actor_label("StealthMast")

    # PlayerStart BESIDE the plate, never on it, and out of every watcher's view --
    # otherwise round 1 begins before the fixture has taken its baseline.
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")
    if math.hypot(START_AT[0] - PLATE_AT[0], START_AT[1] - PLATE_AT[1]) < 200.0:
        fail("PlayerStart is on the plate; round 1 would begin on the first frame")

    # The two standing places the fixture solves for, painted so a reviewer can see
    # where the drive stops. NON-COLLIDING, like all paint.
    paint_stripe(env, (shadow[0] - 160.0, shadow[1]), (shadow[0] + 160.0, shadow[1]),
                 "MarkShadow", M_GLOW, width=60.0)
    paint_stripe(env, (split[0] - 160.0, split[1]), (split[0] + 160.0, split[1]),
                 "MarkSplit", M_HAZARD, width=60.0)

    # A back wall and two differently sized landmarks, so a moving camera reads as
    # moving. NON-COLLIDING like everything else that is not the floor, a block, the
    # truck or a watcher.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.5, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 400.0, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 700.0, 340.0),
              unreal.Vector(1.2 + idx * 1.2, 1.2 + idx * 1.2, 6.8), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-120.0))
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

    fixture = eas.spawn_actor_from_class(
        env["StealthYardFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 400.0, FLOOR_MAX[1] - 1200.0, 160.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("StealthYardFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ---------------------------------------------------------- read the level back
    placed = sorted([a for a in eas.get_all_level_actors()
                     if a.actor_has_tag("StealthWatcher")], key=lambda a: a.get_name())
    if len(placed) != 3:
        fail(f"{len(placed)} actor(s) tagged StealthWatcher, expected three")
    read_back = [(float(w.get_editor_property("sight_reach_uu")),
                  float(w.get_editor_property("sight_half_angle_deg")),
                  float(w.get_editor_property("base_pace_uu_per_sec")),
                  str(w.get_editor_property("round_tag"))) for w in placed]
    if len({r[3] for r in read_back}) != 3:
        fail(f"the placed watchers walk {[r[3] for r in read_back]}; three different "
             f"rounds are required or there is no watch to change")
    if len({round(r[0]) for r in read_back}) != 3 \
            or len({round(r[1]) for r in read_back}) != 3:
        fail(f"the placed watchers read {read_back}; the three are supposed to be set "
             f"to THREE different reaches and THREE different view widths, and one "
             f"shared number would pass EachWatcherSeesWithItsOwnEyes by accident")
    for w in placed:
        o, e = w.get_actor_bounds(only_colliding_components=True)
        if o.z - e.z < floor_top_z + 1.0:
            fail(f"{w.get_actor_label()}'s collision reaches down to z={o.z - e.z:.1f} "
                 f"against a floor whose top face is at z={floor_top_z:.1f}; it would "
                 f"never move and the yard could not be graded")

    blocks = [a for a in eas.get_all_level_actors() if a.actor_has_tag("StealthBlocker")]
    if len(blocks) != len(BLOCKERS):
        fail(f"{len(blocks)} solid block(s), expected {len(BLOCKERS)}")
    for name, tag, want in (("mast", "StealthMast", 1), ("plate", "StealthStartPlate", 1),
                            ("gate", "StealthGate", 1), ("truck", "StealthTruck", 1)):
        got = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    # NOTHING BUT THE FLOOR, THE BLOCKS, THE TRUCK AND THE WATCHERS MAY STOP A LINE.
    for actor in eas.get_all_level_actors():
        label = actor.get_actor_label()
        if (actor.actor_has_tag("StealthWatcher") or actor.actor_has_tag("StealthBlocker")
                or actor.actor_has_tag("StealthTruck") or label == "Floor"
                or actor.get_class().get_name() == "PlayerStart"):
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            # THE PROMISE IS ABOUT BLOCKING A SIGHTLINE, NOT ABOUT ANSWERING QUERIES.
            # Both the fixture and the reference trace ECC_Visibility
            # (StealthYardFunctionalTest.cpp:1125, StealthMastActor.cpp:240), and the
            # fixture's own prop audit at :1179 asks exactly this question. Trigger
            # volumes MUST answer overlap queries -- the start plate is stepped on --
            # so testing collision-enabled condemned the plate for doing its job.
            if comp.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
                continue
            if (comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)
                    == unreal.CollisionResponseType.ECR_BLOCK):
                fail(f"{label} ({comp.get_name()}) BLOCKS the sight channel; the yard "
                     f"promises that only the crates, the wall and the truck stop a "
                     f"line, and a prop that quietly blocks a sightline makes a "
                     f"submission that asks 'is anything in the way?' disagree with a "
                     f"model that never sees it")

    log(f"read back: watchers {read_back}; shadow spot ({shadow[0]:.0f},"
        f"{shadow[1]:.0f}) window {shadow_window['duration']:.2f}s cover "
        f"{shadow_cover:.2f}s; split spot ({split[0]:.0f},{split[1]:.0f}) crossing "
        f"{split_dur:.2f}s clearance {split_clear:.2f}s; {len(blocks)} solid blocks, "
        f"PlayerStart at ({START_AT[0]:.0f},{START_AT[1]:.0f})")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
