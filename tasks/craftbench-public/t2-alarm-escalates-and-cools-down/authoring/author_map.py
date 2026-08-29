"""Authors L_AlarmYard for t2-alarm-escalates-and-cools-down.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A YARD WITH TWO GUARDS WHOSE EYES ARE NOT THE SAME, six floodlights that are not in
any tidy order, and a panel whose raise numbers and drop numbers are deliberately
different. The whole task hangs on geometry, so this script does not place numbers and
hope: it SOLVES the same geometry the fixture solves -- where the drive can stand so
that one guard can never hold somebody there and the other comfortably can, and so that
every sighting window is long enough to judge at the fastest pace the yard ever reaches
-- and it REFUSES TO SAVE if any of it fails to come out.

Every prop except the floor and the guards themselves is NON-COLLIDING on every
channel. The yard promises there is nothing to hide behind, and the fixture's model
never asks whether anything is in the way; a post that quietly blocks a trace would
make a submission that DOES ask count different sightings from the fixture.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-alarm-escalates-and-cools-down"
MAP_PKG = f"/Game/Maps/{TASK}/L_AlarmYard"

# ---------------------------------------------------------------- the yard's shape
# Two parallel rounds, each marked by two posts. The drive walks on the side of the
# watched round AWAY from the other one, so the far guard is never the reason anything
# happens -- which the checks below verify rather than assume.
ROUND_HALF = 700.0          # each round is 1,400 uu of walking, so a lap is 5,600
NORTH_Y = 3000.0
SOUTH_Y = -3000.0
POST_STAND_Z = 150.0        # half the post's 300 cm height
# A GUARD STANDS ON THE FLOOR, NOT IN IT, AND NOT ON IT EITHER.
#
# The guard's collision capsule is CENTRED on its actor location, and its half-height
# lives in C++ (AWatchGuardActor's InitCapsuleSize), not here. This number is a first
# guess only: the height the guard is actually left at is MEASURED off the placed
# actor's own colliding bounds against the placed floor's own top face, below.
#
# This shipped at 90.0 -- exactly half the 180 cm hull -- which put the capsule's bottom
# face at z = 0.0, which is exactly the floor's top face. That is not standing on the
# floor, it is starting every frame in contact with it: AWatchGuardActor::Tick walks by
# a SWEPT SetActorLocation, and ShouldIgnoreHitResult (Engine/Private/Components/
# PrimitiveComponent.cpp) only forgives a start-in-contact hit when the move is heading
# OUT of it -- MoveDot > p.InitialOverlapTolerance, which defaults to 0.0. A horizontal
# move against the floor's up-normal has MoveDot == 0, so the hit blocks and the sweep
# is refused at zero distance, every frame, for ever.
#
# Measured, 2026-08-19: BOTH guards stood on their spawn points for the whole run. The
# fixture's calib line read the same distance and the same bearing on all fifteen
# checkpoints, no guard ever swept anybody, the count never left 0, and phase 3 ran out
# its 115 s deadline and reported a HARNESS-PRECONDITION that named the drive rather
# than the placement. Same fault and same fix as the sibling task
# t1-guard-patrols-until-the-alarm-then-chases, which ships 95.0 and asserts it.
GUARD_STAND_Z = 95.0
# The daylight the guard's feet must have under them: small enough to be invisible in a
# capture, large enough that no swept move ever begins in contact with the floor.
GUARD_FOOT_CLEARANCE_UU = 5.0
FLOOR_MIN = (-3400.0, -5000.0)
FLOOR_MAX = (6800.0, 5200.0)
STRIPE_EVERY = 400.0

# (label, reach, half-angle deg, base pace, round tag). THE TWO ARE NOT ALIKE: the slit
# guard sees a long way through a narrow slot, the wide one sees a short way across a
# broad arc. What matters is the product reach x sin(view width) -- the furthest to one
# side either can EVER hold a stationary target -- and those come out 540 uu and 1,720
# uu, a 3.2x spread. That spread is the entire reason one spot can mean opposite things
# on the two watches.
#
# THE TWO BASE PACES MUST DIFFER BY AT LEAST 20 uu/s -- both this script and the fixture
# refuse a yard where they do not, because one flat speed would fit both guards and the
# pace gate would measure nothing. 280 and 260 sit EXACTLY on that floor and pass only
# because the comparison is strict; move either of them toward the other by anything at
# all and the yard stops being authorable.
GUARDS = (
    ("Slit", 2400.0, 13.0, 280.0, "RoundNorth"),
    ("Wide", 2100.0, 55.0, 260.0, "RoundSouth"),
)

# (x, y, LitFromStage, ReachBonusUu, CoversRoundTag), IN SPAWN ORDER -- which is the
# order the fixture reads them in, and it is deliberately not the order of their
# settings. Per-setting lit counts come out 1 / 4 / 6, so neither "the first N lights"
# nor "N lights" is ever right.
#
# TWO OF THEM THROW LIGHT DOWN A ROUND. While such a floodlight burns, the guard walking
# that round sees further -- so the floodlights are an INPUT to the sighting count and
# not merely a readout of it, and a bug in the lamp loop changes what the guards see.
LAMPS = (
    (-1900.0, 3900.0, 1, 0.0, ""),
    (-1900.0, -3900.0, 2, 500.0, "RoundSouth"),
    (1900.0, 4600.0, 0, 0.0, ""),
    (1900.0, -3900.0, 2, 600.0, "RoundNorth"),
    (-2000.0, 0.0, 1, 0.0, ""),
    (5600.0, 0.0, 1, 0.0, ""),
)

ALARM_AT = (5600.0, 3000.0)

# The dials. RAISE and DROP are deliberately different numbers, and the gap between them
# is the band inside which the panel does not move at all.
DIALS = {
    "sightings_to_raise_watch": 2,
    "sightings_to_raise_hunt": 5,
    "sightings_to_drop_watch": 2,
    "sightings_to_drop_calm": 0,
    "max_sightings_remembered": 5,
    # THE FORGET STEP HAS TO BE LONGER THAN THE GUARD'S ROUND, and that is not a taste
    # question -- it is the difference between a yard whose count can climb and one
    # whose count cannot. Every spot the drive stands on sits past the end of the round,
    # so a guard sights the character exactly once per there-and-back; between two
    # sightings there is a stretch of unbroken quiet, and the panel forgets one sighting
    # per step of it. Forget faster than the guard comes round and the count oscillates
    # 0<->1 for ever: it never reaches sightings_to_raise_watch, never reaches the cap,
    # and the fixture waits for a setting that cannot happen.
    #
    # This shipped at 5.0 s and the yard was UNGRADABLE because of it. The wall-clock
    # cut on 2026-08-19 (notes.md, "WALL-CLOCK BLOCKER") took this dial 14.0 -> 5.0 and
    # the base paces 620/480 -> 280/260 in one move. Halving the paces DOUBLED the quiet
    # between sightings while the dial was cut to a third, and the ratio crossed below
    # one without anyone re-checking it; the fixture then died 115 s into phase 3 with
    # the count stuck at 0, reported as an unexplained timeout.
    #
    # 10.0 s, measured on this yard at the offsets the drive actually PARKS at (up to
    # 90 uu off the spot it aims for, which is what shortens the sighting):
    #   worst quiet between sightings   7.53 s  (close-in spot, Slit guard, calm)
    #                                   7.20 s  (split spot, Wide guard, calm)
    #   -> 2.47 s of margin, 33%.  8.0 s would leave 0.47 s, which is not a margin.
    # Cost: the two cooldowns are cap x this dial, so the drive runs 307 s instead of
    # 257 s (worst case 342 s if a submission never speeds the guards up at all),
    # against the fixture's 400 s sentinel and its last graded checkpoint at 392 s.
    # Both halves refuse to build a yard where this dial and the round disagree.
    "quiet_seconds_per_step_down": 10.0,
    "patrol_scale_when_calm": 1.0,
    "patrol_scale_when_watching": 1.4,
    "patrol_scale_when_hunting": 1.8,
}
# What the fixture's watch change re-sets them to, so the checks below can prove the
# geometry survives the SECOND watch as well as the first.
WATCH2_RAISE_WATCH = DIALS["sightings_to_raise_watch"] + 1
WATCH2_HUNT_SCALE = DIALS["patrol_scale_when_hunting"] * 1.1667

# Mirrors of the fixture's own constants, so "the yard fits the fixture" is MEASURED
# here rather than discovered at run time as a HARNESS-PRECONDITION.
SEEN_SPOT_FRACTION = 0.55
MIN_WINDOW_S = 2.0
MIN_GAP_S = 2.0
ANGLE_EXIT_MARGIN = 80.0
QUIET_CLEARANCE = 1.35
# The fixture's kWaypointUu: it stops driving the character the moment it is this close
# to a waypoint, so the drive can settle this far from the spot it solved for. The
# component that matters is the one perpendicular to the round -- it is the only one
# that shortens the sighting window, and therefore the only one that lengthens the
# quiet the panel's forget clock gets to run for.
WAYPOINT_UU = 90.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"ALARMYARD- {msg}")


def fail(msg):
    unreal.log_error(f"ALARMYARD-ERROR {msg}")
    raise SystemExit(1)


# --------------------------------------------------------------------- the geometry
# These four functions are the fixture's own arithmetic, in Python. If they disagree
# with the fixture the level is wrong, not the fixture, and the run would end as a
# HARNESS-PRECONDITION with nobody the wiser about why.

def sweep_window(reach, half_deg, offset, along, half_len):
    """(ever_visible, width_uu, angle_exit) for a guard walking a straight round,
    facing the way it moves, against a target `offset` uu to one side and `along` uu
    past the round's own +U end."""
    th = math.radians(min(max(half_deg, 0.1), 89.0))
    if offset >= reach * math.sin(th):
        return (False, 0.0, 0.0)
    angle_exit = along - offset / math.tan(th)
    range_entry = along - math.sqrt(max(reach * reach - offset * offset, 0.0))
    lo = max(range_entry, -half_len)
    hi = min(angle_exit, half_len)
    return (hi - lo > 0.0, max(hi - lo, 0.0), angle_exit)


def reach_on_round(base_reach, round_tag):
    """A guard's reach on a named round with every floodlight that covers it burning."""
    bonus = sum(l[3] for l in LAMPS if l[4] == round_tag)
    return base_reach + bonus


def quiet_between_sightings(guard, offset, along, stage, scale):
    """How long this guard leaves the character UNSEEN between two consecutive
    sightings at a dwell spot: the lap, less the one sighting window it affords,
    over the pace that setting dictates.

    Measured at the offset the drive PARKS at, not the one it aims for. The fixture
    stops driving within WAYPOINT_UU of a waypoint, and further off the round means a
    shorter sighting and therefore a longer quiet -- the conservative direction, and
    the one the panel's forget clock actually experiences. A width of zero (parked
    clean out of the cone) yields a whole lap, correctly the worst answer."""
    _, reach, half_deg, base, _ = guard
    r = reach if stage < 2 else reach_on_round(reach, "RoundNorth")
    _, width, _ = sweep_window(r, half_deg, offset + WAYPOINT_UU, along, ROUND_HALF)
    return (4.0 * ROUND_HALF - width) / max(base * scale, 1.0)


def score_at(guard, offset, along, scales, quiet_step):
    """The worst slack, over the three settings, between the sighting window this guard
    would get and the two seconds the fixture needs inside it. None when the spot is
    unusable at any setting -- including when the count could never climb there."""
    _, reach, half_deg, base, _ = guard
    worst = 1.0e9
    for stage, scale in enumerate(scales):
        r = reach if stage < 2 else reach_on_round(reach, "RoundNorth")
        ok, width, angle_exit = sweep_window(r, half_deg, offset, along, ROUND_HALF)
        if not ok:
            return None
        # The cone edge must let go WELL inside the round (a clean, transverse crossing)
        # or not at all before the guard turns (a clean 180-degree flip). Letting go a
        # few uu short of the post is the one shape where one frame of sampling order
        # could add or drop a sighting.
        if ROUND_HALF - ANGLE_EXIT_MARGIN < angle_exit < ROUND_HALF:
            return None
        # AND THE COUNT MUST BE ABLE TO CLIMB HERE. One sighting per lap is worth
        # nothing if the panel has forgotten it before the next one lands.
        if quiet_between_sightings(guard, offset, along, stage, scale) >= quiet_step:
            return None
        speed = max(base * scale, 1.0)
        lap = 4.0 * ROUND_HALF
        worst = min(worst, width / speed - MIN_WINDOW_S,
                    (lap - width) / speed - MIN_GAP_S)
    return worst


def solve_geometry():
    """Reproduce the fixture's solve and refuse the level if it does not come out."""
    scales1 = (DIALS["patrol_scale_when_calm"], DIALS["patrol_scale_when_watching"],
               DIALS["patrol_scale_when_hunting"])
    scales2 = (DIALS["patrol_scale_when_calm"], DIALS["patrol_scale_when_watching"],
               WATCH2_HUNT_SCALE)
    quiet_step = DIALS["quiet_seconds_per_step_down"]

    # THE ROUND AND THE FORGET CLOCK HAVE TO FIT EACH OTHER, and this says so before any
    # offset arithmetic because it needs nothing but the round, the paces and one dial.
    #
    # Every dwell spot sits PAST the end of the round on purpose, so a guard sights the
    # character exactly once per there-and-back. The FLOOR on the quiet between two
    # sightings is therefore HALF A LAP: the widest window physically available is the
    # whole outbound pass, and the pace that matters is the CALM one, because that is
    # the setting the count has to start climbing from and it is the slowest. If half a
    # lap is already as long as the forget step, no offset, no along-track position and
    # no re-routing can rescue it -- these numbers, not the drive, are the thing that
    # has to move.
    #
    # This yard: 1400/280 = 5.00 s (Slit) and 1400/260 = 5.38 s (Wide) against a 10.0 s
    # forget step. At the 5.00 s step this level shipped with, BOTH guards failed this
    # and the fixture died 115 s into phase 3 with the count stuck at 0.
    for label, _reach, _half, base, _tag in GUARDS:
        half_lap = 2.0 * ROUND_HALF / max(base * DIALS["patrol_scale_when_calm"], 1.0)
        if half_lap >= quiet_step:
            fail(f"guard {label} comes round its own {2.0 * ROUND_HALF:.0f} uu of round "
                 f"no more often than every {half_lap:.2f} s at its calm pace of "
                 f"{base * DIALS['patrol_scale_when_calm']:.0f} uu/s, and the panel "
                 f"forgets a sighting after {quiet_step:.2f} s of quiet. A spot past "
                 f"the end of the round is sighted once per lap, so the count would be "
                 f"forgotten between every sighting and could never reach the raise "
                 f"number {DIALS['sightings_to_raise_watch']}, let alone the cap "
                 f"{DIALS['max_sightings_remembered']}")

    unlit = [g[1] * math.sin(math.radians(g[2])) for g in GUARDS]
    lit = [reach_on_round(g[1], "RoundNorth") * math.sin(math.radians(g[2]))
           for g in GUARDS]
    narrow = 0 if lit[0] <= lit[1] else 1
    wide = 1 - narrow
    if unlit[wide] < lit[narrow] * 2.0:
        fail(f"the guards hold somebody out to {lit[narrow]:.0f} uu and "
             f"{unlit[wide]:.0f} uu off their round - less than 2x apart, so no spot "
             f"means opposite things to them and the watch change proves nothing")

    offset_seen = SEEN_SPOT_FRACTION * min(unlit)
    offset_split = math.sqrt(lit[narrow] * unlit[wide])
    if not (lit[narrow] * 1.35 <= offset_split <= unlit[wide] * 0.75):
        fail(f"no offset is both plainly beyond the narrow guard ({lit[narrow]:.0f} uu "
             f"lit) and plainly inside the wide one ({unlit[wide]:.0f} uu)")

    max_reach = max(max(reach_on_round(g[1], "RoundNorth"),
                        reach_on_round(g[1], "RoundSouth")) for g in GUARDS)

    best_seen = (None, -1.0e9)
    best_split = (None, -1.0e9)
    x = ROUND_HALF + 40.0
    while x < ROUND_HALF + 3.4 * max_reach:
        s0 = score_at(GUARDS[0], offset_seen, x, scales1, quiet_step)
        s1 = score_at(GUARDS[1], offset_seen, x, scales1, quiet_step)
        if s0 is not None and s1 is not None and s0 > 0.0 and s1 > 0.0:
            s = min(s0, s1)
            if s > best_seen[1]:
                best_seen = (x, s)
        sw = score_at(GUARDS[wide], offset_split, x, scales1, quiet_step)
        if sw is not None and sw > 0.0 and sw > best_split[1]:
            best_split = (x, sw)
        x += 20.0
    if best_seen[0] is None:
        fail(f"nowhere on the lane gives BOTH guards a sighting window long enough to "
             f"judge AND a quiet stretch between sightings shorter than the panel's "
             f"{quiet_step:.2f} s forget step; the round, the reaches, the patrol "
             f"scales and that dial do not fit together")
    if best_split[0] is None:
        fail(f"nowhere on the lane gives the wide guard a sighting window long enough "
             f"to judge, and a quiet stretch shorter than the panel's {quiet_step:.2f} "
             f"s forget step, at the offset the narrow guard can never reach")
    along_seen, along_split = best_seen[0], best_split[0]

    # THE SECOND WATCH TOO. The sergeant makes the hunting scale faster, and a faster
    # guard means a shorter window; a yard that only works on the first watch would die
    # half way through as a harness fault.
    sw2 = score_at(GUARDS[wide], offset_split, along_split, scales2, quiet_step)
    if sw2 is None or sw2 <= 0.0:
        fail(f"the split spot at {along_split:.0f} uu stops working once the sergeant "
             f"raises the hunting scale to {WATCH2_HUNT_SCALE:.2f}")

    # The quiet spot: far enough along the same lane that neither guard reaches it from
    # either round, with a quarter of the largest reach to spare.
    quiet = None
    x = along_split + 400.0
    while x < along_split + 24000.0:
        p = (x, NORTH_Y + offset_split)
        d = min(point_to_segment(p, (-ROUND_HALF, NORTH_Y), (ROUND_HALF, NORTH_Y)),
                point_to_segment(p, (-ROUND_HALF, SOUTH_Y), (ROUND_HALF, SOUTH_Y)))
        if d >= max_reach * QUIET_CLEARANCE:
            quiet = p
            break
        x += 50.0
    if quiet is None:
        fail(f"there is nowhere on the lane out of reach of both rounds by a quarter "
             f"(largest reach {max_reach:.0f} uu)")

    spots = {
        "seen": (along_seen, NORTH_Y + offset_seen),
        "split": (along_split, NORTH_Y + offset_split),
        "lane": (along_seen, NORTH_Y + offset_split),
        "quiet": quiet,
        "offset_seen": offset_seen,
        "offset_split": offset_split,
        "narrow": narrow,
        "wide": wide,
        "max_reach": max_reach,
    }

    # THE FAR GUARD MUST BE IRRELEVANT everywhere the drive goes, on both watches.
    far_reach = max(reach_on_round(g[1], "RoundSouth") for g in GUARDS)
    route = [spots["quiet"], spots["split"], spots["lane"], spots["seen"]]
    for i in range(len(route) - 1):
        for k in range(9):
            t = k / 8.0
            p = (route[i][0] + (route[i + 1][0] - route[i][0]) * t,
                 route[i][1] + (route[i + 1][1] - route[i][1]) * t)
            d = point_to_segment(p, (-ROUND_HALF, SOUTH_Y), (ROUND_HALF, SOUTH_Y))
            if d < far_reach * 1.25:
                fail(f"the route passes {d:.0f} uu from the other round and the guard "
                     f"on it reaches {far_reach:.0f} uu; the drive would collect "
                     f"sightings nobody designed")
            if not (FLOOR_MIN[0] + 200.0 < p[0] < FLOOR_MAX[0] - 200.0
                    and FLOOR_MIN[1] + 200.0 < p[1] < FLOOR_MAX[1] - 200.0):
                fail(f"the route leaves the floor at ({p[0]:.0f},{p[1]:.0f}); the "
                     f"floor runs {FLOOR_MIN} to {FLOOR_MAX}")

    # THE SPLIT SPOT MUST MEAN OPPOSITE THINGS on the two watches: the narrow guard can
    # never hold anybody there even with every floodlight burning, and the wide one can
    # at every setting.
    if offset_split < lit[narrow] * 1.35:
        fail(f"the split spot is {offset_split:.0f} uu off the round and the narrow "
             f"guard holds somebody out to {lit[narrow]:.0f} uu when it is lit up")
    if offset_split > unlit[wide] * 0.75:
        fail(f"the split spot is {offset_split:.0f} uu off the round and the wide "
             f"guard only holds somebody out to {unlit[wide]:.0f} uu unlit")

    # The one number the wall-clock cut of 2026-08-19 stopped re-checking: the longest
    # the panel is left alone between two sightings, at the offsets the drive PARKS at.
    # It has to stay under the forget step or the count can never climb, and it is
    # logged rather than merely asserted so a re-author can see the margin shrinking
    # before it crosses.
    worst_quiet = max(
        quiet_between_sightings(GUARDS[gi], off, along, stage, scale)
        for gi, off, along in ((0, offset_seen, along_seen),
                               (1, offset_seen, along_seen),
                               (wide, offset_split, along_split))
        for stage, scale in enumerate(scales1))
    log(f"geometry solved: offsets seen {offset_seen:.0f} split {offset_split:.0f}; "
        f"along seen {along_seen:.0f} (slack {best_seen[1]:.2f}s) split "
        f"{along_split:.0f} (slack {best_split[1]:.2f}s, {sw2:.2f}s on watch 2); "
        f"quiet at ({quiet[0]:.0f},{quiet[1]:.0f}); largest reach {max_reach:.0f}; "
        f"worst parked quiet between sightings {worst_quiet:.2f}s against a "
        f"{quiet_step:.2f}s forget step ({quiet_step - worst_quiet:.2f}s of margin)")
    return spots


def point_to_segment(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0.0 if denom <= 0.0 else max(0.0, min(1.0,
        ((p[0] - ax) * dx + (p[1] - ay) * dy) / denom))
    return math.hypot(p[0] - (ax + dx * t), p[1] - (ay + dy * t))


def check_dials():
    d = DIALS
    if not (d["sightings_to_drop_calm"] < d["sightings_to_raise_watch"]
            and d["sightings_to_drop_watch"] < d["sightings_to_raise_hunt"]
            and d["sightings_to_drop_calm"] <= d["sightings_to_drop_watch"]
            and d["sightings_to_raise_watch"] <= d["sightings_to_raise_hunt"]
            and d["sightings_to_raise_hunt"] <= d["max_sightings_remembered"]):
        fail(f"the dials do not describe a yard that can hold a setting: {d}")
    # There must be a real band on BOTH steps, or half the deadband gate is vacuous.
    if d["sightings_to_raise_hunt"] - d["sightings_to_drop_watch"] < 2:
        fail("the hunting band is narrower than two counts, so the fixture can never "
             "stand inside it and watch the setting be remembered")
    if d["sightings_to_raise_watch"] - d["sightings_to_drop_calm"] < 1:
        fail("the watching band is empty; the same count could never mean two things")
    stages = [l[2] for l in LAMPS]
    if stages == sorted(stages):
        fail(f"the floodlights' settings {stages} run in order along their names; "
             f"lighting the first N of them would pass and the gate would measure "
             f"nothing")
    counts = [sum(1 for s in stages if s <= k) for k in range(3)]
    if counts != sorted(set(counts)) or len(set(counts)) != 3:
        fail(f"the per-setting lit counts are {counts}; they must be three different "
             f"numbers so a submission cannot key on how many are lit")
    if counts == [1, 2, 3]:
        fail("the per-setting lit counts are 1/2/3, which 'light N floodlights for "
             "setting N' would pass by accident")
    if not any(l[3] > 0.0 and l[4] for l in LAMPS):
        fail("no floodlight throws light down a round, so the floodlights and the "
             "guards' eyes never touch and the task is two independent readouts")
    log(f"dials checked: raise {d['sightings_to_raise_watch']}/"
        f"{d['sightings_to_raise_hunt']}, drop {d['sightings_to_drop_watch']}/"
        f"{d['sightings_to_drop_calm']}, cap {d['max_sightings_remembered']}, quiet "
        f"{d['quiet_seconds_per_step_down']}s; lit counts {counts} from stages {stages}")


# ------------------------------------------------------------------------ authoring

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
    for cls_name in ("WatchGuardActor", "YardLampActor", "YardAlarmActor",
                     "YardPostActor", "AlarmEscalationFunctionalTest"):
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
    """The wedge one guard can see, drawn on the floor from the end of its round: the
    two edges of its view and the arc at its own reach. The two guards' wedges are
    visibly different shapes, so the level is honest about what it is asking."""
    for sign in (-1.0, 1.0):
        ang = math.radians(facing_deg + sign * half_deg)
        paint_stripe(env, apex,
                     (apex[0] + math.cos(ang) * reach, apex[1] + math.sin(ang) * reach),
                     f"{label}_edge{'P' if sign > 0 else 'M'}", material)
    steps = 18
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
    check_dials()
    spots = solve_geometry()

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
    # its top at z=0" is arithmetic in a comment, which is not evidence -- a scale, a
    # different mesh or a moved centre would all change it silently.
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
    log(f"yard {span_x:.0f}x{span_y:.0f} + {n} stripes")

    # POSTS, in the order the fixture sorts them: the -X end of each round first, so
    # "along the round" points the way the drive expects.
    post_plan = (
        (-ROUND_HALF, NORTH_Y, "RoundNorth", "PostNorthA"),
        (ROUND_HALF, NORTH_Y, "RoundNorth", "PostNorthB"),
        (-ROUND_HALF, SOUTH_Y, "RoundSouth", "PostSouthA"),
        (ROUND_HALF, SOUTH_Y, "RoundSouth", "PostSouthB"),
    )
    for px, py, tag, label in post_plan:
        post = eas.spawn_actor_from_class(
            env["YardPostActor"], unreal.Vector(px, py, POST_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if post is None:
            fail(f"could not place {label}")
        post.set_actor_label(label)
        post.set_editor_property("tags", [unreal.Name(tag)])
    for tag in ("RoundNorth", "RoundSouth"):
        marked = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(marked) != 2:
            fail(f"{len(marked)} actor(s) tagged {tag}, expected exactly two")
    log("four posts placed and tagged, -X end of each round first")

    # The rounds themselves, painted so a reviewer can see where each guard walks.
    paint_stripe(env, (-ROUND_HALF, NORTH_Y), (ROUND_HALF, NORTH_Y), "RoundLineN",
                 M_GLOW, width=24.0)
    paint_stripe(env, (-ROUND_HALF, SOUTH_Y), (ROUND_HALF, SOUTH_Y), "RoundLineS",
                 M_HAZARD, width=24.0)

    # GUARDS, slit guard first: the fixture takes the round of the first guard by name
    # as the one the drive is built around.
    guard_actors = []
    for idx, (label, reach, half_deg, base, tag) in enumerate(GUARDS):
        y = NORTH_Y if tag == "RoundNorth" else SOUTH_Y
        guard = eas.spawn_actor_from_class(
            env["WatchGuardActor"], unreal.Vector(-ROUND_HALF, y, GUARD_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if guard is None:
            fail(f"could not place guard {label}")
        guard.set_actor_label(f"WatchGuard_{idx + 1}_{label}")
        # STOOD ON THE FLOOR, MEASURED, NOT WORKED OUT. Where the guard's collision
        # actually reaches is read off the placed actor; the height it is left at is
        # then derived from that and the floor's own measured top face, so a change to
        # the capsule in C++ moves the guard rather than burying it. A guard that
        # begins a frame in contact with the floor has every swept move refused at zero
        # distance and never walks its round at all -- see GUARD_STAND_Z above.
        g_origin, g_extent = guard.get_actor_bounds(only_colliding_components=True)
        foot_offset = (g_origin.z - g_extent.z) - guard.get_actor_location().z
        want_z = floor_top_z + GUARD_FOOT_CLEARANCE_UU - foot_offset
        if abs(want_z - GUARD_STAND_Z) > 0.01:
            log(f"guard {label}: hull reaches {-foot_offset:.1f} uu below its own "
                f"origin, so GUARD_STAND_Z {GUARD_STAND_Z:.1f} is corrected to "
                f"{want_z:.1f}")
            guard.set_actor_location(unreal.Vector(-ROUND_HALF, y, want_z), False, True)
        g_origin, g_extent = guard.get_actor_bounds(only_colliding_components=True)
        g_bottom = g_origin.z - g_extent.z
        if g_bottom < floor_top_z + 1.0:
            fail(f"guard {label}'s collision reaches down to z={g_bottom:.1f}, at or "
                 f"below the floor's top face at z={floor_top_z:.1f}; it would begin "
                 f"every frame in contact with the floor, every swept move its Tick "
                 f"makes would be refused at zero distance, and it would never walk "
                 f"its round -- the fixture would then wait out a phase deadline with "
                 f"no sighting ever collected")
        log(f"guard {label} stands at z={guard.get_actor_location().z:.1f} with its "
            f"collision bottom at z={g_bottom:.1f}, "
            f"{g_bottom - floor_top_z:.1f} uu clear of the floor")
        guard.set_editor_property("sight_range_uu", reach)
        guard.set_editor_property("sight_half_angle_deg", half_deg)
        guard.set_editor_property("base_patrol_speed_uu", base)
        guard.set_editor_property("patrol_speed_uu_per_sec", base)
        guard.set_editor_property("round_tag", tag)
        if guard.get_editor_property("hull").get_editor_property("mobility") != \
                unreal.ComponentMobility.MOVABLE:
            fail(f"guard {label} is not MOVABLE; it walks its round every frame and "
                 f"PIE scores moving a static actor as a failed test")
        guard_actors.append(guard)
        # Its own view, painted on the floor at the end of the round it walks, in both
        # directions -- so the difference between the two guards is visible.
        for facing, suffix in ((0.0, "F"), (180.0, "B")):
            apex = (ROUND_HALF if facing == 0.0 else -ROUND_HALF, y)
            paint_sight_arc(env, apex, facing, half_deg, reach,
                            f"Sight_{label}_{suffix}",
                            M_GLOW if idx == 0 else M_HAZARD)
        # And the one line that matters most: the furthest to one side this guard can
        # EVER hold somebody, reach x sin(view width), drawn parallel to its round.
        limit = reach * math.sin(math.radians(half_deg))
        # Drawn on the yard-facing side of each round so both lines land on the floor;
        # the cone is symmetric, so either side is the same statement.
        side = 1.0
        paint_stripe(env, (-ROUND_HALF - reach, y + side * limit),
                     (ROUND_HALF + reach, y + side * limit),
                     f"Limit_{label}", M_DARK, width=18.0)
    log(f"two guards placed: {[g[0] for g in GUARDS]}, cone limits "
        f"{[round(g[1] * math.sin(math.radians(g[2]))) for g in GUARDS]} uu")

    # FLOODLIGHTS, in the spawn order the fixture reads them in.
    for idx, (lx, ly, stage, bonus, covers) in enumerate(LAMPS):
        lamp = eas.spawn_actor_from_class(
            env["YardLampActor"], unreal.Vector(lx, ly, 200.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if lamp is None:
            fail(f"could not place floodlight {idx + 1}")
        lamp.set_actor_label(f"YardLamp_{idx + 1}")
        lamp.set_editor_property("lit_from_stage", stage)
        lamp.set_editor_property("reach_bonus_uu", bonus)
        lamp.set_editor_property("covers_round_tag", covers)

    panel = eas.spawn_actor_from_class(
        env["YardAlarmActor"], unreal.Vector(ALARM_AT[0], ALARM_AT[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    if panel is None:
        fail("could not place the panel")
    panel.set_actor_label("YardAlarm")
    for key, value in DIALS.items():
        panel.set_editor_property(key, value)

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(spots["quiet"][0], spots["quiet"][1], 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A back wall and two differently sized landmarks, so a moving camera reads as
    # moving. NON-COLLIDING like everything else that is not the floor or a guard.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.5, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 300.0, FLOOR_MAX[0] - 300.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MIN[1] + 500.0, 320.0),
              unreal.Vector(1.2 + idx * 1.0, 1.2 + idx * 1.0, 6.4), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1200.0),
        unreal.Rotator(roll=0.0, pitch=-50.0, yaw=-115.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1200.0),
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
        env["AlarmEscalationFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MAX[1] - 400.0, 140.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("AlarmEscalationFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ------------------------------------------------------- read the level back
    placed_guards = sorted([a for a in eas.get_all_level_actors()
                            if a.actor_has_tag("WatchGuard")], key=lambda a: a.get_name())
    if len(placed_guards) != 2:
        fail(f"{len(placed_guards)} actor(s) tagged WatchGuard, expected two")
    if str(placed_guards[0].get_editor_property("round_tag")) != "RoundNorth":
        fail(f"the first guard by name walks "
             f"'{placed_guards[0].get_editor_property('round_tag')}'; the fixture "
             f"builds its whole drive around the round of the FIRST guard by name, "
             f"and this level's geometry was solved for RoundNorth")
    # AND NEITHER OF THEM IS IN THE FLOOR, checked once more on the actors as they are
    # about to be SAVED rather than only as they were placed. This is the one fault
    # that costs a whole run and says nothing about why: a guard in contact with the
    # floor has every swept move refused, walks nowhere, sights nobody, and the fixture
    # times out a phase deadline it derived from a lap that never happened.
    for g in placed_guards:
        o, e = g.get_actor_bounds(only_colliding_components=True)
        if o.z - e.z < floor_top_z + 1.0:
            fail(f"{g.get_actor_label()}'s collision reaches down to z={o.z - e.z:.1f} "
                 f"against a floor whose top face is at z={floor_top_z:.1f}; it would "
                 f"never move and the yard could not be graded")

    read_back = []
    for g in placed_guards:
        read_back.append((float(g.get_editor_property("sight_range_uu")),
                          float(g.get_editor_property("sight_half_angle_deg")),
                          float(g.get_editor_property("base_patrol_speed_uu"))))
    limits = [r * math.sin(math.radians(h)) for r, h, _ in read_back]
    if min(limits) * 2.0 > max(limits):
        fail(f"the placed guards hold somebody out to {limits}; less than 2x apart "
             f"and the watch change proves nothing")
    if abs(read_back[0][2] - read_back[1][2]) < 20.0:
        fail(f"the placed guards' base paces are {read_back[0][2]:.0f} and "
             f"{read_back[1][2]:.0f}; one flat speed would fit both")

    placed_lamps = sorted([a for a in eas.get_all_level_actors()
                           if a.actor_has_tag("YardLamp")], key=lambda a: a.get_name())
    if len(placed_lamps) != len(LAMPS):
        fail(f"{len(placed_lamps)} actor(s) tagged YardLamp, expected {len(LAMPS)}")
    placed_stages = [int(l.get_editor_property("lit_from_stage")) for l in placed_lamps]
    if placed_stages != [l[2] for l in LAMPS]:
        fail(f"the placed floodlights read {placed_stages} in name order, not "
             f"{[l[2] for l in LAMPS]}; the order is what stops 'light the first N' "
             f"from passing")

    lit_actors = [a for a in eas.get_all_level_actors()
                  if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit_actors) < 2:
        fail(f"level has {len(lit_actors)} light actor(s); a capture still would be "
             f"black")

    # Nothing but the floor and the guards may block a sightline.
    for actor in eas.get_all_level_actors():
        if actor.actor_has_tag("WatchGuard") or actor.get_actor_label() == "Floor":
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            if comp.get_collision_enabled() in (
                    unreal.CollisionEnabled.QUERY_ONLY,
                    unreal.CollisionEnabled.QUERY_AND_PHYSICS):
                fail(f"{actor.get_actor_label()} still answers queries; the yard "
                     f"promises there is nothing to hide behind, and a prop that "
                     f"blocks a trace makes a submission that checks for cover count "
                     f"different sightings from the fixture")

    log(f"read back: guards {read_back}, cone limits "
        f"{[round(v) for v in limits]}, floodlights {placed_stages}, panel dials set, "
        f"PlayerStart at the quiet spot ({spots['quiet'][0]:.0f},"
        f"{spots['quiet'][1]:.0f})")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
