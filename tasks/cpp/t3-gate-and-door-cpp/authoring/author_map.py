"""Authors L_OldDoorYard for t3-gate-and-door.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

REAL RHI, never -nullrhi: a level saved out of a null-RHI editor has no rendering
state worth capturing and the showroom shots are the only thing a human reviews.

A YARD WITH ONE SHARED RULE AND CONSUMERS THAT WANT DIFFERENT ANSWERS OUT OF IT.
FOUR barriers, all instances of the same class: the OLD DOOR at the north end with one
pad in front of it, an untouched TWIN 3,000 cm east that nothing in the graded run ever
approaches, and TWO GATES in the west wall, each with two pads and two lamps of its own.
Three crates on rails: one feeds the near pad, and two feed the far pad FROM OPPOSITE
SIDES, so parking one there physically excludes the other.

THE TWO GATES STAND OVER THE SAME TWO PATCHES OF FLOOR. The second gate's pads are
painted over the arch gate's, 3 cm proud so neither mat z-fights the other, so both
gates see exactly the same three crates at exactly the same instants. Each is cut for
its OWN ordered pair and each is re-cut on its own schedule, so through most of the run
one gate is open while the other is shut -- and at the last re-cut, with nothing in the
yard moving at all, one comes down while the other goes up. This script proves that
disagreement holds for the pairs it is about to save.

Nothing here is placed and hoped for. This script solves the SAME geometry the fixture
solves -- where each crate's two stops land against its pad's own radius, whether the
two contested rails really do oppose, whether the walking lanes the fixture routes down
clear every rail and every barrier frame, and whether every pair the gate is ever
required to OPEN under is a pair the layout can actually satisfy -- and it REFUSES TO
SAVE if any of it fails to come out.

THE LEVEL IS DELIBERATELY SAVED HOLDING THE WRONG PAIR. The fixture writes the pair the
run grades in PrepareTest, which PIE runs after every BeginPlay, so the only pair a
submission can read ahead of time is not the pair it is graded against. The pair saved
here must still be one a HUMAN can open the gate with, because the owner plays the
reference by hand before this ships.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (BP_ThirdPersonGameMode -> BP_ThirdPersonPlayerController, which carries
IMC_Default -> BP_ThirdPersonCharacter, which has the four IA_* actions bound on its
class defaults). Naming one would REPLACE GlobalDefaultGameMode and leave the player on
a bare APlayerController with no mapping context, which every L2 fixture would miss
because they all drive through AddMovementInput.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw), which is not the order anybody reads it in.
"""
import math

import unreal

TASK = "t3-gate-and-door"
MAP_PKG = f"/Game/Maps/{TASK}/L_OldDoorYard"

# ------------------------------------------------------------------ the yard's shape
# X runs north (toward the old door), Y runs east. Every number below is in cm.
FLOOR_MIN = (-4000.0, -4500.0)
FLOOR_MAX = (5000.0, 4500.0)
STRIPE_EVERY = 400.0

# The old door and the twin. "Thirty metres east" is the prompt's own wording.
OLD_DOOR_AT = (2200.0, 0.0)
TWIN_OFFSET_Y = 3000.0
PAD_IN_FRONT = 300.0          # the prompt: "a floor pad 300 cm in front of the panel"
DOOR_YAW = 180.0              # so the panel swings NORTH, away from the pad a person
                              # is standing on -- a swinging panel must never shove the
                              # body whose weight is holding it open

# The gate, and the two pads that answer for it. The prompt states both offsets:
# "one 700 cm east of the gate, one 800 cm south of that".
GATE_AT = (0.0, -2400.0)
GATE_YAW = 90.0               # the arch is crossed walking east-west
NEAR_PAD_EAST_OF_GATE = 700.0
FAR_PAD_SOUTH_OF_NEAR = 800.0

# The SECOND GATE, in the same wall, well clear of both walking lanes. Its two pads are
# painted over the arch gate's -- same centres, lifted 3 cm so the two mats do not
# z-fight and a person can see there are two of them.
SIDE_GATE_AT = (-2100.0, -2400.0)
SIDE_PAD_LIFT_UU = 3.0

# The rails. Each crate stands at its AWAY stop and its forward line points at the pad.
RAIL_LEN = 900.0
SHOVE_SPEED = 220.0
SHOVE_REACH = 165.0

# The three names. Deliberately unlike each other to read and unrelated to any role, so
# nothing in the yard can be identified by what it is called.
NEAR_NAME = "Marrow"          # A: the only crate that can reach the NEAR pad
FAR_EAST_NAME = "Cinder"      # B: contests the far pad from the east
FAR_WEST_NAME = "Bramble"     # C: contests the far pad from the west

# THE SEQUENCE OF PAIRS, mirrored from the fixture so this script can prove the layout
# survives all of it. The level is saved holding the FIRST one; the fixture writes the
# second before the first judged frame (re-cut #0) and the last two mid-run.
PAIR_IN_LEVEL = (FAR_WEST_NAME, NEAR_NAME)     # (Bramble, Marrow)
PAIR_GRADED = (NEAR_NAME, FAR_EAST_NAME)       # (Marrow, Cinder)  -- re-cut #0
PAIR_RECUT_1 = (FAR_WEST_NAME, NEAR_NAME)      # (Bramble, Marrow)
PAIR_RECUT_2 = (FAR_WEST_NAME, FAR_EAST_NAME)  # (Bramble, Cinder) -- unopenable ON
                                               # PURPOSE: the arch gate must come down
                                               # with nothing in the yard moving

# THE SECOND GATE'S OWN SEQUENCE, mirrored from the fixture's SidePairs. Chosen so the
# two gates disagree at every judged dwell that matters, and so that at re-cut #2 the
# second gate must come UP on the very frames the arch gate must come DOWN.
SIDE_PAIR_IN_LEVEL = (NEAR_NAME, FAR_EAST_NAME)   # (Marrow, Cinder)
SIDE_PAIR_GRADED = (FAR_WEST_NAME, NEAR_NAME)     # (Bramble, Marrow) -- re-cut #0
SIDE_PAIR_RECUT_1 = (NEAR_NAME, FAR_EAST_NAME)    # (Marrow, Cinder)
SIDE_PAIR_RECUT_2 = (FAR_WEST_NAME, NEAR_NAME)    # (Bramble, Marrow)

# Barrier and pad dials. Every one of these is disclosed verbatim in the prompt except
# the grounded band, which the prompt gives as prose ("down on the pad's own level
# rather than up in the air") and which can only ever matter for an airborne body.
OPEN_ANGLE_DEG = 90.0
TRAVEL_RATE_DEG_PER_SEC = 180.0
CONTACT_RADIUS_UU = 100.0
GROUNDED_BAND_UU = 50.0

# Mirrors of the fixture's own constants, so "the yard fits the drive" is MEASURED here
# rather than discovered at run time as a HARNESS-PRECONDITION nobody can act on.
# EVERY NUMBER HERE MUST EQUAL THE FIXTURE'S, not merely resemble it: this block once
# carried 420 against the fixture's 380, so the script validated lanes at x=420 and
# x=-1220 while the drive actually walked x=380 and x=-1180 -- a mirror that measures a
# different yard is worse than no mirror, because it reads as proof.
# kLaneClearUu in OldDoorYardFunctionalTest.cpp:
LANE_CLEAR_UU = 380.0
PUSH_STAND_UU = 260.0
PARK_NEAR_UU = 10.0
DEEP_FACTOR = 5.0
OPPOSED_DOT = -0.8
TWIN_KEEP_UU = 2000.0
BARRIER_FRAME_CLEAR_UU = 340.0
BAND_S = 1.20
BAND_MARGIN_X = 2.0
OPEN_DEG = 80.0

PLAYER_START_AT = (900.0, 0.0, 120.0)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"OLDDOORYARD- {msg}")


def fail(msg):
    unreal.log_error(f"OLDDOORYARD-ERROR {msg}")
    raise SystemExit(1)


# --------------------------------------------------------------------- the geometry

def forward_from_yaw(yaw_deg):
    return (math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg)))


def dist2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    t = 0.0 if denom <= 0.0 else max(0.0, min(1.0,
        ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denom))
    return math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dy * t))


def solve_yard():
    """Every position in the level, derived from the offsets the prompt states, plus
    the checks that say the layout can actually be driven and played."""
    old_door = OLD_DOOR_AT
    old_pad = (old_door[0] - PAD_IN_FRONT, old_door[1])
    twin_door = (old_door[0], old_door[1] + TWIN_OFFSET_Y)
    twin_pad = (old_pad[0], old_pad[1] + TWIN_OFFSET_Y)

    gate = GATE_AT
    side_gate = SIDE_GATE_AT
    near_pad = (gate[0], gate[1] + NEAR_PAD_EAST_OF_GATE)
    far_pad = (near_pad[0] - FAR_PAD_SOUTH_OF_NEAR, near_pad[1])
    # The second gate's pads ARE the arch gate's patches of floor, to the centimetre.
    side_near_pad = near_pad
    side_far_pad = far_pad

    # Each crate stands at its away stop; its forward line points at the pad it feeds.
    # The two contested rails come at the far pad head on from either side.
    crates = [
        # (label, name, anchor, yaw, pad, role tag)
        ("Marrow", NEAR_NAME, (near_pad[0], near_pad[1] + RAIL_LEN), -90.0, near_pad,
         "NearRailCrate"),
        ("Cinder", FAR_EAST_NAME, (far_pad[0], far_pad[1] + RAIL_LEN), -90.0, far_pad,
         "FarRailEastCrate"),
        ("Bramble", FAR_WEST_NAME, (far_pad[0], far_pad[1] - RAIL_LEN), 90.0, far_pad,
         "FarRailWestCrate"),
    ]

    # -- every crate's two stops, against its pad's own radius.
    for label, _name, anchor, yaw, pad, _tag in crates:
        fx, fy = forward_from_yaw(yaw)
        home = (anchor[0] + fx * RAIL_LEN, anchor[1] + fy * RAIL_LEN)
        home_off = dist2d(home, pad)
        away_off = dist2d(anchor, pad)
        if home_off > PARK_NEAR_UU or home_off * DEEP_FACTOR > CONTACT_RADIUS_UU:
            fail(f"crate {label} parks {home_off:.1f} uu from its pad, which is not "
                 f"deep inside a {CONTACT_RADIUS_UU:.0f} uu radius; a crate left "
                 f"grazing the boundary makes the fixture's model and the "
                 f"submission's disagree over a rounding")
        if away_off < CONTACT_RADIUS_UU * DEEP_FACTOR:
            fail(f"crate {label} rests {away_off:.1f} uu from its pad at its other "
                 f"stop, which is not far outside a {CONTACT_RADIUS_UU:.0f} uu radius")

    # -- THE TWO CONTESTED RAILS MUST OPPOSE, or both crates could be home at once and
    #    the identity axis of the whole task stops being something a human can play.
    ce = forward_from_yaw(crates[1][3])
    cw = forward_from_yaw(crates[2][3])
    dot = ce[0] * cw[0] + ce[1] * cw[1]
    if dot > OPPOSED_DOT:
        fail(f"the two rails feeding the contested pad have an axis dot product of "
             f"{dot:.2f}; they must approach it from opposite sides")

    # -- THE PAIRS. Any pair the gate is required to OPEN under must name the near-pad
    #    crate, because the two far-rail crates can never be home together. Get this
    #    wrong and the task is unwinnable through no fault of any submission.
    names = {c[1] for c in crates}
    for label, pair in (("the level", PAIR_IN_LEVEL), ("the graded pair", PAIR_GRADED),
                        ("re-cut #1", PAIR_RECUT_1),
                        ("the second gate in the level", SIDE_PAIR_IN_LEVEL),
                        ("the second gate's graded pair", SIDE_PAIR_GRADED),
                        ("the second gate at re-cut #1", SIDE_PAIR_RECUT_1),
                        ("the second gate at re-cut #2", SIDE_PAIR_RECUT_2)):
        if pair[0] == pair[1] or not set(pair) <= names:
            fail(f"{label} is cut for {pair}, which is not two distinct crate names")
        if NEAR_NAME not in pair:
            fail(f"{label} is cut for {pair}, which does not name the near-pad crate "
                 f"{NEAR_NAME}; the two far-rail crates contest one pad and can never "
                 f"be home together, so that pair is unopenable BY LAYOUT and the task "
                 f"would be unwinnable")
    if set(PAIR_RECUT_2) == {FAR_EAST_NAME, FAR_WEST_NAME}:
        log("re-cut #2 names both contested crates on purpose: the gate must come "
            "down and stay down with nothing in the yard moving")
    else:
        fail(f"re-cut #2 is {PAIR_RECUT_2}; it must name both contested crates, which "
             f"is the whole point of the re-cut that moves nothing")
    if PAIR_IN_LEVEL == PAIR_GRADED:
        fail("the level is saved holding the same pair the run grades, so a hard-coded "
             "answer would not be wrong from the first frame")
    if SIDE_PAIR_IN_LEVEL == SIDE_PAIR_GRADED:
        fail("the second gate is saved holding the same pair it is graded against")
    if PAIR_IN_LEVEL == SIDE_PAIR_IN_LEVEL:
        fail("both gates are saved cut for the same pair, so the level shows a "
             "submission a yard where one answer happens to serve both")
    if PAIR_GRADED == SIDE_PAIR_GRADED:
        fail("both gates are graded against the same pair from the first judged frame")

    # -- THE TWO GATES MUST ACTUALLY DISAGREE, and not merely be written differently.
    #    Traced against the drive's own crate-home states at the four dwells the design
    #    turns on. If a pair edit ever makes both gates agree everywhere, the second
    #    gate stops being a control and this script refuses to save the yard.
    def open_under(pair, home):
        return set(pair) <= home

    both_pads = [
        ("phase 4, the near and east crates home",
         {NEAR_NAME, FAR_EAST_NAME}, PAIR_GRADED, SIDE_PAIR_GRADED),
        ("phase 5, the near and west crates home",
         {NEAR_NAME, FAR_WEST_NAME}, PAIR_GRADED, SIDE_PAIR_GRADED),
        ("phase 14, the near and west crates home after re-cut #1",
         {NEAR_NAME, FAR_WEST_NAME}, PAIR_RECUT_1, SIDE_PAIR_RECUT_1),
        ("phase 17, nothing moving after re-cut #2",
         {NEAR_NAME, FAR_WEST_NAME}, PAIR_RECUT_2, SIDE_PAIR_RECUT_2),
    ]
    for label, home, arch_pair, side_pair in both_pads:
        if open_under(arch_pair, home) == open_under(side_pair, home):
            fail(f"at {label} the arch gate cut for {arch_pair} and the second gate "
                 f"cut for {side_pair} would BOTH be "
                 f"{'open' if open_under(arch_pair, home) else 'shut'}; the second "
                 f"gate only earns its place by disagreeing")
    # And the second gate has to RISE at least once before the first re-cut and once
    # after the last one, or its run-level clauses are unreachable.
    if not open_under(SIDE_PAIR_GRADED, {NEAR_NAME, FAR_WEST_NAME}):
        fail(f"the second gate cut for {SIDE_PAIR_GRADED} never opens before the first "
             f"re-cut, so it can never come up and come home again")
    if not open_under(SIDE_PAIR_RECUT_2, {NEAR_NAME, FAR_WEST_NAME}):
        fail(f"the second gate cut for {SIDE_PAIR_RECUT_2} is not satisfied by the "
             f"crates already standing on the pads at re-cut #2, so the moment where "
             f"one gate falls and the other rises with nothing moving does not exist")
    # The graded pair must NOT be readable off the layout either. re-cut #1 is
    # deliberately the mirror of it, so an answer that decides the first name is
    # whatever is on the near pad is right for one half of the run and wrong for the
    # other -- which is what makes the lamp channel load-bearing.
    if PAIR_GRADED[0] != NEAR_NAME or PAIR_RECUT_1[0] == NEAR_NAME:
        fail(f"the graded pair {PAIR_GRADED} and re-cut #1 {PAIR_RECUT_1} do not put "
             f"the near-pad crate in OPPOSITE slots; without that, identifying the "
             f"crates positionally passes the whole run")

    # -- the fixture's walking lanes, solved here so a clearance fault is caught now.
    near_rail_x = crates[0][2][0]
    far_rail_x = crates[1][2][0]
    if abs(crates[2][2][0] - far_rail_x) > 5.0:
        fail("the two contested rails are not on one line, so the drive cannot serve "
             "them from a single lane")
    # THE FIXTURE'S OWN RAIL-SEPARATION PRECONDITION, mirrored. StageDrive refuses a
    # yard whose two rail groups are closer than two lane widths, and this script used
    # to omit the check entirely -- so a layout edit that narrowed the gap would author
    # and SAVE a map happily and then die in every L2 run with a message nobody could
    # act on.
    if abs(near_rail_x - far_rail_x) < 2.0 * LANE_CLEAR_UU:
        fail(f"the near rail sits at x={near_rail_x:.0f} and the contested rails at "
             f"x={far_rail_x:.0f}, only {abs(near_rail_x - far_rail_x):.0f} uu apart "
             f"against the {2.0 * LANE_CLEAR_UU:.0f} uu this drive needs to walk "
             f"between them")
    sign = 1.0 if near_rail_x > far_rail_x else -1.0
    lane_near_x = near_rail_x + sign * LANE_CLEAR_UU
    lane_far_x = far_rail_x - sign * LANE_CLEAR_UU

    stations, rail_segments = [], []
    for _label, _name, anchor, yaw, _pad, _tag in crates:
        fx, fy = forward_from_yaw(yaw)
        rail_segments.append((anchor, (anchor[0] + fx * RAIL_LEN,
                                       anchor[1] + fy * RAIL_LEN)))
        stations.append((anchor[0] - fx * PUSH_STAND_UU,
                         anchor[1] - fy * PUSH_STAND_UU))
        stations.append((anchor[0] + fx * (RAIL_LEN + PUSH_STAND_UU),
                         anchor[1] + fy * (RAIL_LEN + PUSH_STAND_UU)))

    ys = [p[1] for seg in rail_segments for p in seg] + [s[1] for s in stations]
    cross_north_y = old_pad[1]
    cross_south_y = min(ys) - LANE_CLEAR_UU
    if cross_north_y < max(ys) + LANE_CLEAR_UU:
        fail(f"the crossing at the old door's end sits at y={cross_north_y:.0f}, only "
             f"{cross_north_y - max(ys):.0f} uu clear of the nearest rail work")
    for label, at in (("the arch gate", gate), ("the second gate", side_gate)):
        if cross_south_y > at[1] - 600.0:
            fail(f"the far crossing at y={cross_south_y:.0f} does not clear {label} at "
                 f"y={at[1]:.0f} by enough for its panel to swing")

    # Neither lane may run through a barrier's frame, and neither may brush a rail.
    for lane_x in (lane_near_x, lane_far_x):
        for label, at in (("the old door", old_door), ("the twin door", twin_door),
                          ("the arch gate", gate), ("the second gate", side_gate)):
            if abs(lane_x - at[0]) < BARRIER_FRAME_CLEAR_UU:
                fail(f"the walking lane at x={lane_x:.0f} passes through the frame of "
                     f"{label} at x={at[0]:.0f}")
        for seg, crate in zip(rail_segments, crates):
            # Both the lanes and the rails run along Y here, so the clearance is the
            # perpendicular gap plus, for a rail whose span does not overlap the
            # lane's, whatever the ends are apart. Measured over the lane's whole
            # travel rather than sampled.
            clear = min(point_to_segment((lane_x, y), seg[0], seg[1])
                        for y in (cross_north_y, cross_south_y, seg[0][1], seg[1][1]))
            if clear < SHOVE_REACH + 100.0:
                fail(f"the walking lane at x={lane_x:.0f} passes {clear:.0f} uu from "
                     f"crate {crate[0]}'s rail, and a body inside {SHOVE_REACH:.0f} uu "
                     f"of a crate shoves it")

    # -- AND THE DRIVE NEVER GOES NEAR THE CONTROL. The twin pair is the in-scene
    #    negative control; a route that brushed it would make the control prove
    #    nothing at all.
    watched = [(lane_near_x, cross_north_y), (lane_near_x, cross_south_y),
               (lane_far_x, cross_north_y), (lane_far_x, cross_south_y),
               old_pad, near_pad] + stations \
        + [p for seg in rail_segments for p in seg]
    for p in watched:
        d = min(dist2d(p, twin_pad), dist2d(p, twin_door))
        if d < TWIN_KEEP_UU:
            fail(f"the drive reaches ({p[0]:.0f},{p[1]:.0f}), only {d:.0f} uu from the "
                 f"untouched twin pair, and it must stay {TWIN_KEEP_UU:.0f} uu clear")
        if not (FLOOR_MIN[0] + 200.0 < p[0] < FLOOR_MAX[0] - 200.0
                and FLOOR_MIN[1] + 200.0 < p[1] < FLOOR_MAX[1] - 200.0):
            fail(f"the drive leaves the floor at ({p[0]:.0f},{p[1]:.0f})")

    # -- the band has to be a contract on the SUBMISSION's decision latency, never a
    #    race against the supplied animation.
    reach_open_s = OPEN_DEG / TRAVEL_RATE_DEG_PER_SEC
    if reach_open_s * BAND_MARGIN_X > BAND_S:
        fail(f"a panel takes {reach_open_s:.3f} s to clear {OPEN_DEG:.0f} deg at "
             f"{TRAVEL_RATE_DEG_PER_SEC:.0f} deg/s, which does not clear the "
             f"{BAND_S:.2f} s band by {BAND_MARGIN_X:.0f}x")
    if OPEN_ANGLE_DEG < OPEN_DEG + 5.0:
        fail(f"a barrier that opens to only {OPEN_ANGLE_DEG:.0f} deg can never be "
             f"{OPEN_DEG:.0f} deg from shut")

    log(f"geometry solved: old door {old_door} pad {old_pad}; twin {twin_door} pad "
        f"{twin_pad}; gate {gate} near pad {near_pad} far pad {far_pad}; lanes "
        f"x={lane_near_x:.0f} and x={lane_far_x:.0f}; crossings y={cross_north_y:.0f} "
        f"and y={cross_south_y:.0f}; a panel clears {OPEN_DEG:.0f} deg in "
        f"{reach_open_s:.3f} s against a {BAND_S:.2f} s band "
        f"({BAND_S / reach_open_s:.1f}x margin)")
    return {
        "old_door": old_door, "old_pad": old_pad,
        "twin_door": twin_door, "twin_pad": twin_pad,
        "gate": gate, "near_pad": near_pad, "far_pad": far_pad,
        "side_gate": side_gate,
        "side_near_pad": side_near_pad, "side_far_pad": side_far_pad,
        "crates": crates,
        "lane_near_x": lane_near_x, "lane_far_x": lane_far_x,
        "cross_north_y": cross_north_y, "cross_south_y": cross_south_y,
    }


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
    for cls_name in ("YardBarrierActor", "YardPadActor", "YardCrateActor",
                     "GateLampActor", "OldDoorYardFunctionalTest"):
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
        # The PROFILE, not just the enum: on an earlier task in this set
        # set_collision_enabled alone did not survive into the saved level, and paint
        # that quietly blocks a walking lane is indistinguishable from a bug in the
        # submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def add_tag(actor, tag):
    """APPEND, never replace. The C++ constructor already stamps the family tag
    (YardBarrier / YardPad / YardCrate / GateLamp) and the fixture counts by it;
    overwriting the array would silently take that tag away."""
    tags = list(actor.get_editor_property("tags"))
    tags.append(unreal.Name(tag))
    actor.set_editor_property("tags", tags)


def paint_stripe(env, a, b, label, material, width=14.0):
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1.0:
        return
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    block(env, CUBE,
          unreal.Vector((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, 2.0),
          unreal.Vector(length / 100.0, width / 100.0, 0.04), label, material, yaw=yaw)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    yard = solve_yard()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # ------------------------------------------------------------------ the floor
    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    floor = block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
                  collide=True)
    # THE FLOOR'S TOP FACE, MEASURED off the placed block. Everything that stands on
    # the floor is derived from this number; "a 100 uu cube centred at z=-50 has its
    # top at z=0" is arithmetic in a comment, which is not evidence.
    f_origin, f_extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = f_origin.z + f_extent.z
    if abs(floor_top_z) > 0.5:
        fail(f"the floor's top face measured at z={floor_top_z:.2f}; every pad in this "
             f"yard measures a body's base against its OWN level, and the pads are "
             f"placed at z=0")
    log(f"floor {span_x:.0f}x{span_y:.0f}, top face measured at z={floor_top_z:.1f}")

    # Stripes both ways, so speed and distance are readable by eye from any angle.
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        paint_stripe(env, (x, FLOOR_MIN[1]), (x, FLOOR_MAX[1]), f"StripeX_{n:02d}",
                     M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    y = FLOOR_MIN[1] + STRIPE_EVERY
    while y < FLOOR_MAX[1]:
        paint_stripe(env, (FLOOR_MIN[0], y), (FLOOR_MAX[0], y), f"StripeY_{n:02d}",
                     M_STRIPE)
        n += 1
        y += STRIPE_EVERY
    log(f"{n} stripes every {STRIPE_EVERY:.0f} cm, both ways")

    # --------------------------------------------------------------- the barriers
    def barrier(at, yaw, label, role_tag, pair):
        a = eas.spawn_actor_from_class(
            env["YardBarrierActor"], unreal.Vector(at[0], at[1], floor_top_z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        if a is None:
            fail(f"could not place {label}")
        a.set_actor_label(label)
        a.set_editor_property("open_angle_deg", OPEN_ANGLE_DEG)
        a.set_editor_property("travel_rate_deg_per_sec", TRAVEL_RATE_DEG_PER_SEC)
        if pair is not None:
            # LEFT ALONE for the two doors. A barrier that is cut for NOTHING is what
            # takes the yard's shared any-body rule, and that is the whole of what the
            # preservation gate measures; writing an empty FName here would be writing
            # NAME_None back over NAME_None, but only by luck of how FName("") folds,
            # and this contract is too load-bearing to leave to that.
            a.set_editor_property("cut_for_first_name", unreal.Name(pair[0]))
            a.set_editor_property("cut_for_second_name", unreal.Name(pair[1]))
        add_tag(a, role_tag)
        return a

    old_door = barrier(yard["old_door"], DOOR_YAW, "OldDoor", "OldDoor", None)
    twin_door = barrier(yard["twin_door"], DOOR_YAW, "QuietDoor", "QuietDoor", None)
    gate = barrier(yard["gate"], GATE_YAW, "ArchGate", "ArchGate", PAIR_IN_LEVEL)
    side_gate = barrier(yard["side_gate"], GATE_YAW, "SideGate", "SideGate",
                        SIDE_PAIR_IN_LEVEL)

    # ------------------------------------------------------------------- the pads
    def pad(at, label, role_tag, answered, lift=0.0):
        a = eas.spawn_actor_from_class(
            env["YardPadActor"], unreal.Vector(at[0], at[1], floor_top_z + lift),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if a is None:
            fail(f"could not place {label}")
        a.set_actor_label(label)
        a.set_editor_property("contact_radius_uu", CONTACT_RADIUS_UU)
        a.set_editor_property("grounded_band_uu", GROUNDED_BAND_UU)
        a.set_editor_property("answered_barrier", answered)
        add_tag(a, role_tag)
        return a

    pad(yard["old_pad"], "OldPad", "OldPad", old_door)
    pad(yard["twin_pad"], "QuietPad", "QuietPad", twin_door)
    pad(yard["near_pad"], "GateNearPad", "GateNearPad", gate)
    pad(yard["far_pad"], "GateFarPad", "GateFarPad", gate)
    # THE SECOND GATE'S PADS ARE THE SAME TWO PATCHES OF FLOOR, lifted 3 cm so neither
    # mat z-fights the other and a person can see there are two. The lift is far inside
    # the pads' own grounded band, so what is resting on one is resting on both.
    pad(yard["side_near_pad"], "SideNearPad", "SideNearPad", side_gate,
        lift=SIDE_PAD_LIFT_UU)
    pad(yard["side_far_pad"], "SideFarPad", "SideFarPad", side_gate,
        lift=SIDE_PAD_LIFT_UU)

    # ----------------------------------------------------------------- the crates
    crate_actors = []
    for label, name, anchor, yaw, _pad, role_tag in yard["crates"]:
        a = eas.spawn_actor_from_class(
            env["YardCrateActor"], unreal.Vector(anchor[0], anchor[1], floor_top_z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        if a is None:
            fail(f"could not place crate {label}")
        a.set_actor_label(f"Crate_{label}")
        a.set_editor_property("crate_name", unreal.Name(name))
        a.set_editor_property("rail_length_uu", RAIL_LEN)
        a.set_editor_property("shove_speed_uu", SHOVE_SPEED)
        a.set_editor_property("shove_reach_uu", SHOVE_REACH)
        add_tag(a, role_tag)
        crate_actors.append(a)
        # Its own rail, painted on the floor, so a person can see where each crate can
        # and cannot go without reading a single number.
        fx, fy = forward_from_yaw(yaw)
        paint_stripe(env, anchor,
                     (anchor[0] + fx * RAIL_LEN, anchor[1] + fy * RAIL_LEN),
                     f"Rail_{label}", M_GLOW if role_tag == "NearRailCrate" else M_HAZARD,
                     width=22.0)

    # ------------------------------------------------------------------ the lamps
    # On each gate's own frame, above the lintel, one per name slot. FOUR lamps: a lamp
    # stands for a slot ON ITS OWN GATE, and the two gates carry different pairs at the
    # same instant, so "slot 0" is not a thing the yard has -- only each gate has one.
    for tag, owner, at in (("Arch", gate, yard["gate"]),
                           ("Side", side_gate, yard["side_gate"])):
        gx, gy = at
        for slot, offset in ((0, -160.0), (1, 160.0)):
            lamp = eas.spawn_actor_from_class(
                env["GateLampActor"], unreal.Vector(gx + offset, gy, 560.0),
                unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if lamp is None:
                fail(f"could not place the {tag} lamp for slot {slot}")
            lamp.set_actor_label(f"{tag}Lamp_{slot}")
            lamp.set_editor_property("name_slot", slot)
            lamp.set_editor_property("lamp_barrier", owner)

    # ------------------------------------------------- the player, and the showroom
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(*PLAYER_START_AT),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A back wall and two differently sized landmarks, so a moving camera reads as
    # moving. NON-COLLIDING, like everything that is not the floor, a crate or a
    # barrier's own frame.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MIN[1] + 60.0, 150.0),
          unreal.Vector(span_x / 100.0, 0.5, 3.0), "Backdrop", M_DARK)
    for idx, bx in enumerate((FLOOR_MIN[0] + 400.0, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(bx, FLOOR_MIN[1] + 400.0, 340.0),
              unreal.Vector(1.2 + idx * 1.4, 1.2 + idx * 1.4, 6.8), f"Landmark_{idx}",
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
        env["OldDoorYardFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 500.0, FLOOR_MAX[1] - 500.0, 200.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("OldDoorYardFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings name a game mode; this level must inherit the project "
             "default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # -------------------------------------------------------- read the level back
    actors = eas.get_all_level_actors()

    def tagged(tag):
        return sorted([a for a in actors if a.actor_has_tag(tag)],
                      key=lambda a: a.get_name())

    for tag, want in (("YardBarrier", 4), ("YardPad", 6), ("YardCrate", 3),
                      ("GateLamp", 4)):
        got = tagged(tag)
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}; the fixture "
                 f"counts by these tags and a miscount ends the run as a "
                 f"HARNESS-PRECONDITION")
    for tag in ("OldDoor", "QuietDoor", "ArchGate", "SideGate", "OldPad", "QuietPad",
                "GateNearPad", "GateFarPad", "SideNearPad", "SideFarPad",
                "NearRailCrate", "FarRailEastCrate", "FarRailWestCrate"):
        if len(tagged(tag)) != 1:
            fail(f"{len(tagged(tag))} actor(s) tagged {tag}, expected exactly one")

    read_pair = (str(gate.get_editor_property("cut_for_first_name")),
                 str(gate.get_editor_property("cut_for_second_name")))
    if read_pair != PAIR_IN_LEVEL:
        fail(f"the arch gate reads back cut for {read_pair}, not {PAIR_IN_LEVEL}")
    side_read_pair = (str(side_gate.get_editor_property("cut_for_first_name")),
                      str(side_gate.get_editor_property("cut_for_second_name")))
    if side_read_pair != SIDE_PAIR_IN_LEVEL:
        fail(f"the second gate reads back cut for {side_read_pair}, not "
             f"{SIDE_PAIR_IN_LEVEL}")

    # THE TWO GATES' PADS MUST BE THE SAME TWO PATCHES OF FLOOR, measured off the
    # placed actors. If they drifted apart, the gates could disagree because of where
    # the crates are rather than because of what is written on each of them, and the
    # whole second-gate control would be a geometry accident.
    placed_pads = {a.get_actor_label(): a for a in actors if a.actor_has_tag("YardPad")}
    for near_label, side_label in (("GateNearPad", "SideNearPad"),
                                   ("GateFarPad", "SideFarPad")):
        a, b = placed_pads.get(near_label), placed_pads.get(side_label)
        if a is None or b is None:
            fail(f"cannot read back the pair {near_label} / {side_label}")
        la, lb = a.get_actor_location(), b.get_actor_location()
        off = dist2d((la.x, la.y), (lb.x, lb.y))
        if off > 2.0:
            fail(f"{side_label} stands {off:.1f} uu from {near_label}; they are meant "
                 f"to be one patch of floor and the fixture refuses more than 2 uu")
        if not (0.0 < lb.z - la.z <= GROUNDED_BAND_UU * 0.2):
            fail(f"{side_label} sits {lb.z - la.z:.1f} cm above {near_label}; it must "
                 f"be proud enough not to z-fight and far inside the grounded band")
    for door, label in ((old_door, "the old door"), (twin_door, "the twin door")):
        pair = (str(door.get_editor_property("cut_for_first_name")),
                str(door.get_editor_property("cut_for_second_name")))
        if pair not in (("None", "None"), ("", "")):
            fail(f"{label} reads back cut for {pair}; both doors must be cut for "
                 f"nothing, or they stop taking the yard's shared rule and the whole "
                 f"preservation gate measures nothing")

    read_names = [str(a.get_editor_property("crate_name")) for a in crate_actors]
    if len(set(read_names)) != 3:
        fail(f"the placed crates read back {read_names}; two crates carrying one name "
             f"could never be told apart")

    # Every crate's parking stop, MEASURED off the placed actors rather than off the
    # plan, against the placed pad's own placed radius.
    for a, (label, _name, _anchor, yaw, pad_at, _tag) in zip(crate_actors,
                                                             yard["crates"]):
        loc = a.get_actor_location()
        fwd = a.get_actor_forward_vector()
        home = (loc.x + fwd.x * RAIL_LEN, loc.y + fwd.y * RAIL_LEN)
        off = dist2d(home, pad_at)
        if off > PARK_NEAR_UU:
            fail(f"placed crate {label} would park {off:.1f} uu from its pad centre")
        o, e = a.get_actor_bounds(only_colliding_components=True)
        base = o.z - e.z
        if abs(base - floor_top_z) > GROUNDED_BAND_UU * 0.5:
            fail(f"placed crate {label}'s solid base sits at z={base:.1f} against a "
                 f"floor top at z={floor_top_z:.1f}; a crate that is not down on the "
                 f"pad's own level never counts as resting on it")

    lit_actors = [a for a in actors
                  if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit_actors) < 2:
        fail(f"level has {len(lit_actors)} light actor(s); a capture would be black")

    # NOTHING DECORATIVE MAY BLOCK A WALKING LANE. The floor, the crates and the
    # barriers' own frames are the only solid things in this yard.
    for a in actors:
        label = a.get_actor_label()
        if label == "Floor" or a.actor_has_tag("YardCrate") \
                or a.actor_has_tag("YardBarrier"):
            continue
        if a.get_class().get_name() != "StaticMeshActor":
            continue
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            if comp.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION:
                fail(f"decorative actor {label} still collides; a stripe or a landmark "
                     f"that blocks the drive stalls a phase and reports it as a "
                     f"staging fault rather than as what it is")

    log(f"read back: crates {read_names}; the arch gate is saved cut for {read_pair} "
        f"and grades against {PAIR_GRADED}; the second gate is saved cut for "
        f"{side_read_pair} and grades against {SIDE_PAIR_GRADED}; doors cut for "
        f"nothing; PlayerStart at {PLAYER_START_AT}")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
