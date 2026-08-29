"""Authors L_MemoryYard for t3-the-yard-remembers-after-you-leave.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A WALLED NEAR YARD -- five numbered posts in a row on one side of a walking lane,
three lamp-marked pads in a row on the other, a counter board by the gate -- and, across
a solid dividing wall, a FAR YARD of three more posts and a board of its own that
nothing done in the near yard may touch. The two yards sit in one camera frame on
purpose: the far yard is the in-scene negative control, and a picture of the near yard
alone proves nothing.

EVERY PROP IS MOVABLE. The fixture destroys all thirteen of them and spawns fresh ones
further along their own row, THREE times per run, and PIE scores moving a STATIC actor
as a failed test.

THE ROW-AND-LANE SHAPE IS NOT A TASTE DECISION -- IT IS THE FIXTURE'S ROUTE MODEL.
AMemoryYardFunctionalTest derives a single walking lane as
    LaneY = 0.5 * (mean near-post Y + mean pad Y)
and reaches every prop by a straight perpendicular leg off that lane
(MemoryYardFunctionalTest.cpp::LanePointFor / BuildRoute). CheckRouteIsWalkable then
refuses -- as an attributed HARNESS-PRECONDITION, not a graded FAIL -- any waypoint
within 250 uu of a prop the step is not about, or any leg that passes that close to one.
Two consequences, and this script enforces both rather than hoping:

  * the posts must be on ONE side of the lane and the pads on the OTHER, each row far
    enough off it that a lane traverse clears every prop;
  * no two props may share a column, because the outer one's perpendicular retreat to
    the lane would pass straight through the inner one.

The build brief's earlier layout -- five posts on an eight-slot 2x4 grid at
x in {400,1100} and three pads on a six-slot 2x3 grid at x in {-1400,-500} -- cannot
satisfy the second point at all: two columns cannot hold five posts without one column
holding three, and of any three posts in one column at least two fall on the same side
of the lane. Brute-forced over all 56 x 20 = 1,120 slot choices x 3 staged sets x 3
rebuild rotations: ZERO are walkable. This script's layout is the same yard re-shaped
into rows, and `check_geometry` re-runs that exact simulation -- the fixture's own two
checks, its own constants, its own rotation rule -- and REFUSES TO SAVE if a single
sample comes out short. A yard the walk cannot be run in is a task that reports the
level's fault as the model's.

THE NUMBERS IN THIS LEVEL ARE DECOYS AND THE SCRIPT ENFORCES THAT. The fixture stages
its own worths before anybody's BeginPlay and restages them on the fresh posts at every
rebuild; three complete sets ship in the fixture, TWELVE rounds in all, and which set
runs is taken from the clock. No worth authored here agrees with what any of those
twelve rounds paints on that same post, so an agent that reads the level binary and
hard-codes what it finds is wrong from the first frame.

`check_day` re-runs the fixture's own BuildDayTrace refusals over all three staged sets
before a single actor is placed, so a typo in a staged table is caught here rather than
as a HARNESS-PRECONDITION in the middle of a graded run.

This level names NO game mode: it inherits the project default, so BP_ThirdPersonGameMode
and BP_ThirdPersonPlayerController (which carries IMC_Default) apply and a person can hit
Play and walk this yard with WASD. The fixture asserts that lane by property name as a
HARNESS precondition, because it drives through AddMovementInput and would otherwise grade
an uncontrollable map byte-identically -- which is how five of six ThirdPerson maps once
shipped authored, lit, certified and unplayable
(the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-the-yard-remembers-after-you-leave"
MAP_PKG = f"/Game/Maps/{TASK}/L_MemoryYard"

# ---------------------------------------------------------------- the yard's shape
# A showroom: one big striped floor, the whole action envelope readable from the south,
# a backdrop with a different landmark at each end so a moving camera is distinguishable
# from a still one.
# The floor runs a long way SOUTH of the yard on purpose: every camera pose in
# cameras.json stands ON it, so a capture still never frames the yard from off the edge
# of the world with sky under the near half of the shot.
FLOOR_MIN = (-3800.0, -4200.0)
FLOOR_MAX = (3800.0, 2400.0)
STRIPE_EVERY = 200.0        # "200 cm stripes, so distance is readable by eye"

# The two rows and the lane between them. LANE_Y is what the fixture DERIVES; it is
# asserted below rather than assumed, so moving a row can never silently move the lane
# into a prop.
POST_ROW_Y = 700.0
PAD_ROW_Y = -700.0
LANE_Y = 0.0

# Five post slots in a row, 750 uu apart. The posts rotate among these five at every
# rebuild, so every slot has to be good for every post.
POST_SLOT_X = (-1500.0, -750.0, 0.0, 750.0, 1500.0)
# Three pad slots, 1,000 uu apart -- comfortably past the 2 x 150 uu that the prompt's
# disclosed resume radius would need to stay unambiguous. IF PAD SPACING EVER HAS TO
# CHANGE, CHANGE THE SPACING, NEVER THE DISCLOSED 150.
PAD_SLOT_X = (-1400.0, -400.0, 600.0)

NEAR_BOARD = (-2300.0, -1300.0)
FAR_BOARD = (2400.0, -1300.0)
FAR_POST_X = (2400.0, 2900.0, 3400.0)
FAR_POST_Y = 700.0

PLAYER_START = (-2400.0, 0.0)
PLAYER_START_Z = 100.0      # capsule half-height is 96: the runner stands, never sinks

# The near yard's enclosure. The gate is a gap in the WEST wall, centred on the lane, and
# it sits exactly where the fixture's gate waypoint lands (PlayerStart.X - kGateOutUu).
YARD_WEST_X = -3050.0
YARD_NORTH_Y = 1600.0
YARD_SOUTH_Y = -1600.0
DIVIDER_X = 2000.0          # solid, no gap: the far yard cannot be walked into
FAR_EAST_X = 3700.0
GATE_HALF = 400.0           # an 800-wide gap
WALL_HALF_THICK = 20.0
WALL_HEIGHT = 500.0
BACKDROP_Y = 2300.0

# ---------------------------------------------------------------- the props
# Sorted by name, because that is the order the fixture rows them up in
# (ResolveYards::TakeRow sorts by the name the post carries, so the staged table never
# has to spell an identity).
NEAR_YARD = "NearYard"
FAR_YARD = "FarYard"
NEAR_POSTS = ("Ash", "Birch", "Cedar", "Dale", "Elm")
FAR_POSTS = ("Fern", "Gorse", "Hazel")
# (PadOrder, PadId). DELIBERATELY NOT ALPHABETICAL: the order painted on a pad is the
# only thing that says which one is first, and a submission that sorts pads by name and
# calls the first one "pad 1" has to be wrong.
PADS = ((1, "Larch"), (2, "Ivy"), (3, "Juniper"))

# THE DECOYS. What is painted into this level, per post.
DECOY_NEAR = {"Ash": 13, "Birch": 5, "Cedar": 10, "Dale": 15, "Elm": 4}
DECOY_FAR = {"Fern": 17, "Gorse": 16, "Hazel": 7}

# ---------------------------------------------------------------- the fixture, mirrored
# Every constant below is READ OFF AMemoryYardFunctionalTest and is the reason this
# script can prove the walk before the level exists. If the fixture changes one of them,
# this script has to change with it -- that is the point of naming them here rather than
# eyeballing a layout.
FX_MIN_PROP_CLEARANCE = 250.0     # kMinPropClearanceUu
FX_MIN_BOARD_CLEARANCE = 200.0    # kMinBoardClearanceUu
FX_POST_STAND_INSET = 100.0       # kPostStandInsetUu
FX_GATE_OUT = 650.0               # kGateOutUu
# kBoardShiftUu[], indexed by ReopenIndex - 1. BOUNDED, not cumulative: three rebuilds
# times a fixed step would walk the far board through the far yard's east wall.
FX_BOARD_SHIFT = (550.0, 1100.0, 300.0)
FX_BOARD_SHIFT_LANE_GUARD = 400.0 # the |Candidate.Y - LaneY| > 400 in RebuildBothYards
FX_RESUME_RADIUS = 150.0          # kResumeRadiusUu, and it is DISCLOSED in the prompt
FX_WORTH_MIN, FX_WORTH_MAX = 3, 17
FX_ROUTE_SAMPLES = 40             # CheckRouteIsWalkable samples 40 points per leg

# The scaffold's own geometry, mirrored so the clearances are SOLVED rather than guessed.
POST_GROUND_HALF = 130.0          # AMemoryPostActor::Ground box half-extent, in plan
POST_GROUND_HALF_Z = 110.0
PAD_STEP_HALF = 150.0             # AMemoryPadActor::Step box half-extent, in plan
CAPSULE_RADIUS = 42.0             # the ThirdPerson character's capsule
CAPSULE_CENTRE_Z = 96.0           # ...and where its centre rides above the floor

# THE THREE STAGED SETS, all twelve rounds, transcribed from
# MemoryYardFunctionalTest.cpp::ChooseSet. Indices are into NEAR_POSTS / FAR_POSTS.
# Present ONLY so this script can prove the decoys really are decoys and can walk the
# same day the fixture walks; nothing here is authored into the level.
#
# FOUR ROUNDS PER SET NOW, not three: the yard is rebuilt THREE times, and what happens
# to the written record at each rebuild (nothing / an earlier copy put back / thrown
# away) is ordered differently in every set, so no submission can count rebuilds instead
# of reading the record.
FIXTURE_ROUNDS = (
    # set 0: open, then WARM, REWIND, COLD
    ((5, 12, 7, 16, 9), (4, 11, 14)),
    ((14, 3, 11, 6, 17), (9, 5, 12)),
    ((8, 15, 4, 13, 6), (16, 7, 3)),
    ((7, 10, 3, 5, 16), (13, 17, 4)),
    # set 1: open, then REWIND, COLD, WARM
    ((11, 4, 15, 8, 6), (13, 3, 9)),
    ((7, 16, 5, 12, 14), (4, 17, 6)),
    ((3, 9, 13, 17, 10), (11, 8, 15)),
    ((12, 7, 16, 4, 11), (5, 14, 3)),
    # set 2: open, then COLD, WARM, REWIND
    ((9, 17, 3, 11, 13), (6, 15, 8)),
    ((12, 6, 16, 4, 7), (14, 3, 11)),
    ((15, 10, 8, 3, 16), (5, 12, 17)),
    ((4, 13, 11, 16, 9), (10, 7, 14)),
)
ROUNDS_PER_SET = 4
# The scripts, step for step, from FStagedSet::Script. ("pad", order-1) / ("post", i) /
# ("walk", i) / ("rebuild", kind). Kinds are only carried so a reader can check the
# per-set ordering against the fixture; the walk simulation does not use them.
FIXTURE_SCRIPTS = (
    (("pad", 2), ("post", 1), ("post", 3), ("pad", 1), ("post", 0),
     ("rebuild", "warm"),
     ("walk", 3), ("post", 2), ("pad", 0),
     ("rebuild", "rewind"),
     ("post", 3), ("pad", 1),
     ("rebuild", "cold"),
     ("post", 4)),
    (("pad", 1), ("post", 2), ("post", 4), ("pad", 2), ("post", 1),
     ("rebuild", "rewind"),
     ("walk", 2), ("post", 3), ("pad", 2),
     ("rebuild", "cold"),
     ("post", 0), ("pad", 1),
     ("rebuild", "warm"),
     ("post", 1)),
    (("pad", 2), ("post", 4), ("post", 3), ("pad", 1), ("post", 1),
     ("rebuild", "cold"),
     ("post", 2), ("pad", 2),
     ("rebuild", "warm"),
     ("walk", 2), ("post", 0), ("pad", 1),
     ("rebuild", "rewind"),
     ("post", 3)),
)
# How far along its own row every prop moves at reopening r (1-based): the fixture's
# `Shift = (ReopenIndex >= 3) ? 2 : 1`. Cumulative offsets are therefore 1, 2, 4 and are
# never the identity in a row of three (1, 2, 1) or of five (1, 2, 4).
FIXTURE_SHIFTS = (1, 1, 2)
# Every cumulative rotation a prop is ever standing at: 0 at the open, then the running
# sums of FIXTURE_SHIFTS. Every clearance below is checked at all four.
ROTATIONS = (0, 1, 2, 4)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"

CLASSES = ("MemoryPostActor", "MemoryPadActor", "MemoryBoardActor",
           "MemoryYardFunctionalTest")


def log(msg):
    unreal.log(f"MEMORYYARD- {msg}")


def fail(msg):
    unreal.log_error(f"MEMORYYARD-ERROR {msg}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Geometry, all of it SOLVED
# ---------------------------------------------------------------------------

def post_slot(index, rotation):
    """Where near post `index` (by name order) stands after `rotation` rebuilds.
    RebuildBothYards moves prop i onto the slot prop i+1 was on, so after r rebuilds it
    is on slot (i + r) % N."""
    return (POST_SLOT_X[(index + rotation) % len(POST_SLOT_X)], POST_ROW_Y)


def pad_slot(index, rotation):
    """`index` is PadOrder - 1: the fixture rows the pads up by the order painted on
    them, never by name or by where they lie."""
    return (PAD_SLOT_X[(index + rotation) % len(PAD_SLOT_X)], PAD_ROW_Y)


def far_post_slot(index, rotation):
    return (FAR_POST_X[(index + rotation) % len(FAR_POST_X)], FAR_POST_Y)


def lane_point(where):
    return (where[0], LANE_Y)


def stand_point(where):
    """StandPointFor: FX_POST_STAND_INSET in from the post's origin toward the lane."""
    step = -FX_POST_STAND_INSET if where[1] > LANE_Y else FX_POST_STAND_INSET
    return (where[0], where[1] + step)


def gate_point():
    """PrepareTest resolves the LEVEL's single PlayerStart and walks out to
    PlayerStart.X - kGateOutUu on the derived lane -- never from wherever the runner
    happens to be standing, so a submission cannot move this waypoint. That is why the
    script asserts there is exactly one PlayerStart, and why the gate gap below has to
    be centred on the lane at exactly this x."""
    return (PLAYER_START[0] - FX_GATE_OUT, LANE_Y)


def wall_boxes():
    """Every colliding wall, as an (x0, y0, x1, y1) footprint. The runner is a capsule,
    so a wall is only ever a hazard if the walk comes within a capsule radius of it --
    but a wall 200 uu from a waypoint is a wall a settling character can brush, which is
    exactly the kind of thing that fails correct work."""
    t = WALL_HALF_THICK
    return (
        # the west wall, in two segments, leaving the gate gap on the lane
        (YARD_WEST_X - t, YARD_SOUTH_Y - t, YARD_WEST_X + t, LANE_Y - GATE_HALF),
        (YARD_WEST_X - t, LANE_Y + GATE_HALF, YARD_WEST_X + t, YARD_NORTH_Y + t),
        # the near yard's long sides
        (YARD_WEST_X - t, YARD_NORTH_Y - t, DIVIDER_X + t, YARD_NORTH_Y + t),
        (YARD_WEST_X - t, YARD_SOUTH_Y - t, DIVIDER_X + t, YARD_SOUTH_Y + t),
        # the solid dividing wall
        (DIVIDER_X - t, YARD_SOUTH_Y - t, DIVIDER_X + t, YARD_NORTH_Y + t),
        # the far yard. Its long walls START past the dividing wall's own footprint, so
        # two static slabs never share a face and z-fight in a capture still.
        (DIVIDER_X + t, YARD_NORTH_Y - t, FAR_EAST_X + t, YARD_NORTH_Y + t),
        (DIVIDER_X + t, YARD_SOUTH_Y - t, FAR_EAST_X + t, YARD_SOUTH_Y + t),
        (FAR_EAST_X - t, YARD_SOUTH_Y - t, FAR_EAST_X + t, YARD_NORTH_Y + t),
        # the backdrop
        (FLOOR_MIN[0], BACKDROP_Y - t, FLOOR_MAX[0], BACKDROP_Y + t),
    )


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist_to_box(p, box):
    dx = max(box[0] - p[0], 0.0, p[0] - box[2])
    dy = max(box[1] - p[1], 0.0, p[1] - box[3])
    return math.hypot(dx, dy)


def on_floor(p, margin=150.0):
    return (FLOOR_MIN[0] + margin <= p[0] <= FLOOR_MAX[0] - margin
            and FLOOR_MIN[1] + margin <= p[1] <= FLOOR_MAX[1] - margin)


def visit_plan(script):
    """The walked steps of one staged set's script, in order, as (kind, index) pairs.
    A walk-through targets a post exactly as a take does; only what is graded there
    differs, and the route does not care."""
    return tuple(("pad", a) if kind == "pad" else ("post", a)
                 for kind, a in script if kind != "rebuild")


def phases(script):
    """PhaseStart / PhaseCount, ported: the stretches of walked steps between rebuilds,
    as (first visit, count, lane-return-first, gate-at-end). The counts DIFFER BY SET --
    the fixture slices them out of the script, and so does this."""
    out = []
    first = 0
    count = 0
    rebuilds = 0
    for kind, _a in script:
        if kind == "rebuild":
            out.append((first, count, rebuilds > 0, True))
            first += count
            count = 0
            rebuilds += 1
        else:
            count += 1
    out.append((first, count, rebuilds > 0, False))
    return out


def rotation_after(reopens):
    """How far every prop has moved along its own row after `reopens` rebuilds:
    the running sum of the fixture's per-rebuild Shift."""
    return sum(FIXTURE_SHIFTS[:reopens])


def build_route(script, phase, rotation, start_x):
    """BuildRoute, ported. Returns [(target, about_or_None), ...] where `about` is the
    prop a leg is EXEMPT against -- and only a Kind-1 leg has one, exactly as
    CheckRouteIsWalkable::PropOfLeg has it."""
    first, count, lane_return_first, gate_at_end = phases(script)[phase]
    plan = visit_plan(script)
    legs = []
    if lane_return_first:
        legs.append(((start_x, LANE_Y), None))
    for k in range(count):
        kind, index = plan[first + k]
        home = post_slot(index, rotation) if kind == "post" else pad_slot(index, rotation)
        ident = (kind, index)
        legs.append((lane_point(home), None))
        legs.append((home if kind == "pad" else stand_point(home), ident))
        legs.append((lane_point(home), None))
    if gate_at_end:
        legs.append((gate_point(), None))
    return legs


def simulate(set_index):
    """BuildDayTrace's shadow ledger, ported far enough to name every number a person
    could read off the near board during the day and to prove the staged set still
    discriminates. Returns (rounds, every board value the day shows, reopenings)."""
    script = FIXTURE_SCRIPTS[set_index]
    rounds = FIXTURE_ROUNDS[set_index * ROUNDS_PER_SET:
                            (set_index + 1) * ROUNDS_PER_SET]
    taken, worth_when_taken, board, marked = set(), {}, 0, 1
    snapshot = None
    round_index = 0
    boards = [0]
    reopens = []
    for kind, a in script:
        if kind == "pad":
            marked = a + 1
        elif kind == "walk":
            continue
        elif kind == "post":
            worth = rounds[round_index][0][a]
            taken.add(a)
            worth_when_taken[a] = worth
            board += worth
            boards.append(board)
            if snapshot is None:
                snapshot = (set(taken), dict(worth_when_taken), board, marked)
        else:
            was = (set(taken), dict(worth_when_taken), board, marked)
            round_index += 1
            if a == "rewind":
                taken, worth_when_taken, board, marked = (
                    set(snapshot[0]), dict(snapshot[1]), snapshot[2], snapshot[3])
            elif a == "cold":
                taken, worth_when_taken, board, marked = set(), {}, 0, 1
            reopens.append((a, was, (set(taken), dict(worth_when_taken), board, marked),
                            round_index))
            boards.append(board)
    return rounds, boards, reopens


def check_route(script, phase, rotation, start_x):
    """CheckRouteIsWalkable, ported, plus a wall check the fixture cannot do (it has no
    model of the walls) and a board check on the boards' ORIGINAL homes, which is what
    the fixture compares against -- ResolveYards only records a board's Home on the
    first open."""
    legs = build_route(script, phase, rotation, start_x)
    props = [(("post", i), post_slot(i, rotation)) for i in range(len(NEAR_POSTS))]
    props += [(("pad", i), pad_slot(i, rotation)) for i in range(len(PADS))]
    walls = wall_boxes()
    worst = [1.0e9, 1.0e9, 1.0e9]

    def gauge(point, exempt):
        for ident, where in props:
            if ident in exempt:
                continue
            d = dist(point, where)
            worst[0] = min(worst[0], d)
            if d < FX_MIN_PROP_CLEARANCE:
                fail(f"staged set day {script} phase {phase}: the walk comes {d:.0f} uu from the "
                     f"{ident[0]} at index {ident[1]} ({where}), which the step is not "
                     f"about; the fixture needs {FX_MIN_PROP_CLEARANCE:.0f} and reports "
                     f"a shortfall as a HARNESS-PRECONDITION -- the LEVEL's fault "
                     f"reported as nobody's")
        for board in (NEAR_BOARD, FAR_BOARD):
            d = dist(point, board)
            worst[1] = min(worst[1], d)
            if d < FX_MIN_BOARD_CLEARANCE:
                fail(f"staged set day {script} phase {phase}: the walk comes {d:.0f} uu from a "
                     f"counter board; the runner would be pushing it")
        for box in walls:
            d = dist_to_box(point, box)
            worst[2] = min(worst[2], d)
            if d < FX_MIN_BOARD_CLEARANCE:
                fail(f"staged set day {script} phase {phase}: the walk comes {d:.0f} uu from a "
                     f"wall at {box}; a runner that jams on a wall stops the day and "
                     f"the stall reads as the submission's fault")

    for target, about in legs:
        gauge(target, {about} if about is not None else set())
    for i in range(len(legs) - 1):
        (a, about_a), (b, about_b) = legs[i], legs[i + 1]
        exempt = {x for x in (about_a, about_b) if x is not None}
        for k in range(FX_ROUTE_SAMPLES + 1):
            t = float(k) / float(FX_ROUTE_SAMPLES)
            gauge((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), exempt)
    return worst


def check_day():
    """BuildDayTrace's own refusals, re-run here so a typo in a staged set is caught
    when the level is authored rather than as a HARNESS-PRECONDITION in a graded run.
    Every clause below is the fixture's, in the fixture's order."""
    for set_index in range(len(FIXTURE_SCRIPTS)):
        rounds, boards, reopens = simulate(set_index)
        tag = f"staged set {set_index}"
        for r, (near, far) in enumerate(rounds):
            for worth in tuple(near) + tuple(far):
                if not FX_WORTH_MIN <= worth <= FX_WORTH_MAX:
                    fail(f"{tag} round {r} paints a post {worth}, outside the "
                         f"{FX_WORTH_MIN}..{FX_WORTH_MAX} the prompt states")
        kinds = [k for k, _was, _now, _r in reopens]
        if sorted(kinds) != ["cold", "rewind", "warm"]:
            fail(f"{tag} reopens {kinds}; every set does warm, rewind and cold once "
                 f"each, in its own order, or the shape of the day becomes something a "
                 f"submission can count instead of reading the record")
        for kind, was, now, r in reopens:
            was_taken, was_worths, was_board, was_pad = was
            now_taken, _now_worths, now_board, now_pad = now
            near = rounds[r][0]
            recompute = sum(near[i] for i in now_taken)
            all_five = sum(near)
            if kind == "cold":
                if was_board == 0 or was_pad == 1 or not was_taken:
                    fail(f"{tag}: the record is thrown away while the board reads "
                         f"{was_board}, the mark is on pad {was_pad} and {len(was_taken)} "
                         f"posts are gone; a yard that never remembered would read the "
                         f"same")
                continue
            if now_board in (0, recompute, all_five, len(now_taken)):
                fail(f"{tag}: the yard reopens on {now_board}, which a naive answer "
                     f"would also produce (0, count {len(now_taken)}, recompute "
                     f"{recompute}, all five {all_five})")
            if now_pad == 1:
                fail(f"{tag}: the yard reopens with the mark on the first pad, where a "
                     f"yard that remembered nothing would also put the runner")
            for i in now_taken:
                if was_worths.get(i, near[i]) == near[i] and i in was_taken:
                    fail(f"{tag}: post {NEAR_POSTS[i]} is repainted with the same "
                         f"number it was worth when it was taken, so a re-derived "
                         f"total would be indistinguishable from the banked one")
            if kind == "rewind" and (now_board == was_board or now_taken == was_taken
                                     or now_pad == was_pad):
                fail(f"{tag}: putting the earlier copy of the record back leaves the "
                     f"yard reading the same as a warm memory would ({now_board} vs "
                     f"{was_board}, {sorted(now_taken)} vs {sorted(was_taken)}, pad "
                     f"{now_pad} vs {was_pad}); all three readings have to disagree")
        counts = [c for _f, c, _l, _g in phases(FIXTURE_SCRIPTS[set_index])]
        if min(counts) < 1:
            fail(f"{tag} has a stretch of the day with nothing walked in it")
        if len(set(boards)) < 4:
            fail(f"{tag} shows only {sorted(set(boards))} on the counter board all day")
    log(f"the day CHECKS OUT for all {len(FIXTURE_SCRIPTS)} staged sets: three "
        f"reopenings each, warm/rewind/cold in a different order per set, and no naive "
        f"answer lands on a reading any of them requires")


def check_geometry():
    """What has to be true before the level is worth saving. Nothing here is a taste
    judgement: every number is the fixture's own, computed the fixture's own way."""
    check_day()
    # ---- the lane is DERIVED, never assumed --------------------------------------
    derived = 0.5 * (sum(POST_ROW_Y for _ in POST_SLOT_X) / float(len(POST_SLOT_X))
                     + sum(PAD_ROW_Y for _ in PAD_SLOT_X) / float(len(PAD_SLOT_X)))
    if abs(derived - LANE_Y) > 1.0:
        fail(f"the fixture derives its lane at y={derived:.1f} and this script's "
             f"geometry is written around y={LANE_Y:.1f}. LaneY is "
             f"0.5*(mean post Y + mean pad Y) and is not a constant anybody may set")
    if abs(POST_ROW_Y - LANE_Y) < FX_MIN_PROP_CLEARANCE + POST_GROUND_HALF:
        fail(f"the post row stands {abs(POST_ROW_Y - LANE_Y):.0f} uu off the lane; a "
             f"lane traverse would come inside the fixture's "
             f"{FX_MIN_PROP_CLEARANCE:.0f} uu of every post in the row at once")
    if abs(PAD_ROW_Y - LANE_Y) < FX_MIN_PROP_CLEARANCE + PAD_STEP_HALF:
        fail(f"the pad row lies {abs(PAD_ROW_Y - LANE_Y):.0f} uu off the lane")
    if (POST_ROW_Y - LANE_Y) * (PAD_ROW_Y - LANE_Y) > 0.0:
        fail("the posts and the pads are on the SAME side of the lane; the fixture "
             "reaches each row by a perpendicular leg off the lane and one row would be "
             "reached through the other")

    # ---- no two props share a column ---------------------------------------------
    # The retreat from a prop to the lane is a straight perpendicular leg, and only the
    # prop it is about is exempt from the 250 uu clearance. Two props at the same X on
    # the same side of the lane means one leg runs straight through the other.
    for row, label in ((POST_SLOT_X, "post"), (PAD_SLOT_X, "pad"),
                       (FAR_POST_X, "far post")):
        for i, a in enumerate(row):
            for b in row[i + 1:]:
                if abs(a - b) < FX_MIN_PROP_CLEARANCE:
                    fail(f"two {label} slots are {abs(a - b):.0f} uu apart in x; the "
                         f"perpendicular leg to the further one passes inside "
                         f"{FX_MIN_PROP_CLEARANCE:.0f} uu of the nearer")

    # ---- the disclosed resume radius has to name exactly one pad -----------------
    pad_gap = min(abs(a - b) for i, a in enumerate(PAD_SLOT_X) for b in PAD_SLOT_X[i + 1:])
    if pad_gap <= 2.0 * FX_RESUME_RADIUS:
        fail(f"two pad slots are {pad_gap:.0f} uu apart and the prompt discloses a "
             f"{FX_RESUME_RADIUS:.0f} uu radius, so 'within {FX_RESUME_RADIUS:.0f} of "
             f"the marked pad' could be satisfied by the wrong pad. CHANGE THE SPACING, "
             f"NEVER THE DISCLOSED NUMBER")

    # ---- a set-down on a pad must not land in a standing post's ground -----------
    # The reference puts the runner at the pad's own XY, so the capsule reaches
    # CAPSULE_RADIUS out from there; a post notices anything inside POST_GROUND_HALF of
    # its origin. Anything less than the sum and being put back would TAKE A POST.
    #
    # SUBSUMED TODAY by the two row checks above (opposite sides of the lane, each row
    # at least 380/400 uu off it, so the rows are never closer than 780 uu). It is kept
    # because it is the constraint the REFERENCE depends on -- notes.md records that
    # TakePost is deliberately NOT guarded against a placement's own overlap, on the
    # grounds that this geometry makes it impossible -- and a future edit that loosened
    # a row check must not be able to make a set-down take a post in silence.
    need = POST_GROUND_HALF + CAPSULE_RADIUS + FX_MIN_BOARD_CLEARANCE
    for r in ROTATIONS:
        for i in range(len(PADS)):
            for j in range(len(NEAR_POSTS)):
                d = dist(pad_slot(i, r), post_slot(j, r))
                if d < need:
                    fail(f"a pad slot and a post slot are {d:.0f} uu apart; a runner set "
                         f"down on that pad reaches {CAPSULE_RADIUS:.0f} uu into a "
                         f"{POST_GROUND_HALF * 2:.0f}-square patch of ground and would "
                         f"take a post just by being put back ({need:.0f} uu needed)")

    # ---- the runner never starts, or leaves, standing on a mark ------------------
    for i in range(len(PADS)):
        for label, p in (("PlayerStart", PLAYER_START), ("gate waypoint", gate_point())):
            d = dist(p, pad_slot(i, 0))
            if d < 900.0:
                fail(f"the {label} is {d:.0f} uu from a pad; the prompt's "
                     f"{FX_RESUME_RADIUS:.0f} uu radius has to mean the yard put the "
                     f"runner there, not that the runner never left")

    # ---- the gate gap is where the fixture walks, and wide enough ----------------
    gate = gate_point()
    if abs(gate[0] - YARD_WEST_X) > 1.0:
        fail(f"the fixture walks out to x={gate[0]:.0f} (PlayerStart.X - "
             f"{FX_GATE_OUT:.0f}) and the gate gap is in a wall at x={YARD_WEST_X:.0f}; "
             f"the runner would be walking at a wall, not through a gap")
    if GATE_HALF < FX_MIN_BOARD_CLEARANCE + CAPSULE_RADIUS:
        fail(f"the gate gap is {2.0 * GATE_HALF:.0f} uu wide; a runner standing in it "
             f"would be brushing a wall")

    # ---- THE WHOLE WALK, every set, every phase, every rotation ------------------
    worst = [1.0e9, 1.0e9, 1.0e9]
    runs = 0
    for script in FIXTURE_SCRIPTS:
        for phase, (_first, _count, lane_return, _gate) in enumerate(phases(script)):
            rotation = rotation_after(phase)
            if lane_return:
                # BuildRoute starts a post-reopen route from wherever the runner IS.
                # A correct submission has set it down on the marked pad; a wrong one
                # may have left it at the gate, or on the wrong pad, or up to the
                # disclosed radius off centre. NONE of those may turn into an
                # attributed Error, so all of them are checked.
                starts = [gate_point()[0]]
                for i in range(len(PADS)):
                    px = pad_slot(i, rotation)[0]
                    starts += [px - FX_RESUME_RADIUS, px, px + FX_RESUME_RADIUS]
            else:
                starts = [None]
            for start_x in starts:
                got = check_route(script, phase, rotation, start_x)
                worst = [min(a, b) for a, b in zip(worst, got)]
                runs += 1

    # ---- the boards move, and moving them may never wreck a walk ----------------
    # THREE reopenings now, and the offsets are bounded rather than cumulative, so the
    # far board cannot walk out through the far yard's east wall. Each offset is checked
    # for the same three things the fixture's own guard checks, plus the two the fixture
    # has no model for: the floor, and which side of the dividing wall it lands on.
    for reopen in (1, 2, 3):
        rotation = rotation_after(reopen)
        for board, label in ((NEAR_BOARD, "near"), (FAR_BOARD, "far")):
            cand = (board[0] + FX_BOARD_SHIFT[reopen - 1], board[1])
            if abs(cand[1] - LANE_Y) <= FX_BOARD_SHIFT_LANE_GUARD:
                fail(f"the {label} board would not move at reopen {reopen}: the fixture "
                     f"only shifts a board that sits more than "
                     f"{FX_BOARD_SHIFT_LANE_GUARD:.0f} uu off the lane, and this one is "
                     f"{abs(cand[1] - LANE_Y):.0f}")
            slots = [post_slot(i, rotation) for i in range(len(NEAR_POSTS))]
            slots += [pad_slot(i, rotation) for i in range(len(PADS))]
            slots += [far_post_slot(i, rotation) for i in range(len(FAR_POSTS))]
            gap = min(dist(cand, s) for s in slots)
            if gap <= FX_MIN_PROP_CLEARANCE + FX_MIN_BOARD_CLEARANCE:
                fail(f"the {label} board would not move at reopen {reopen}: its shifted "
                     f"spot is {gap:.0f} uu from a prop and the fixture only takes a "
                     f"shift that clears "
                     f"{FX_MIN_PROP_CLEARANCE + FX_MIN_BOARD_CLEARANCE:.0f}")
            if not on_floor(cand):
                fail(f"the {label} board walks off the floor at reopen {reopen} "
                     f"({cand})")
            if (label == "near") != (cand[0] < DIVIDER_X):
                fail(f"the {label} board lands at x={cand[0]:.0f} at reopen {reopen}, "
                     f"on the wrong side of the dividing wall at x={DIVIDER_X:.0f}")
        if len(set(FX_BOARD_SHIFT)) != len(FX_BOARD_SHIFT):
            fail("two reopenings move a counter board to the same spot, so a "
                 "position-keyed restore is not challenged at both")

    # ---- everything is on the floor, and in the yard it says it is in ------------
    for label, p in ([("PlayerStart", PLAYER_START), ("near board", NEAR_BOARD),
                      ("far board", FAR_BOARD), ("gate", gate)]
                     + [(f"post slot {i}", post_slot(i, 0)) for i in range(5)]
                     + [(f"pad slot {i}", pad_slot(i, 0)) for i in range(3)]
                     + [(f"far post slot {i}", far_post_slot(i, 0)) for i in range(3)]):
        if not on_floor(p):
            fail(f"the {label} lands at {p}, off a floor of {FLOOR_MIN}..{FLOOR_MAX}")
    for i in range(5):
        if not (YARD_WEST_X < post_slot(i, 0)[0] < DIVIDER_X):
            fail(f"near post slot {i} is not inside the near yard's walls")
    for i in range(3):
        if not (DIVIDER_X < far_post_slot(i, 0)[0] < FAR_EAST_X):
            fail(f"far post slot {i} is not inside the far yard's walls")
    if not NEAR_BOARD[0] < DIVIDER_X < FAR_BOARD[0]:
        fail("the two counter boards are not on opposite sides of the dividing wall")

    # ---- THE DECOYS MUST STAY DECOYS -------------------------------------------
    for name, worth in list(DECOY_NEAR.items()) + list(DECOY_FAR.items()):
        if not FX_WORTH_MIN <= worth <= FX_WORTH_MAX:
            fail(f"{name} is authored at {worth}, outside the {FX_WORTH_MIN}.."
                 f"{FX_WORTH_MAX} band the prompt discloses")
    for round_index, (near, far) in enumerate(FIXTURE_ROUNDS):
        for i, name in enumerate(NEAR_POSTS):
            if DECOY_NEAR[name] == near[i]:
                fail(f"{name} is authored at {DECOY_NEAR[name]} and the fixture's round "
                     f"{round_index} paints it {near[i]}; reading the level binary would "
                     f"become a partly correct answer, and the whole anti-hardcode "
                     f"defence rests on it never being one")
        for i, name in enumerate(FAR_POSTS):
            if DECOY_FAR[name] == far[i]:
                fail(f"{name} is authored at {DECOY_FAR[name]} and the fixture's round "
                     f"{round_index} paints it {far[i]}")
    authored_total = sum(DECOY_NEAR.values())
    for set_index in range(len(FIXTURE_SCRIPTS)):
        rounds, boards, _reopens = simulate(set_index)
        naive = set(boards) | {sum(near) for near, _far in rounds}
        if authored_total in naive:
            fail(f"the authored near worths sum to {authored_total}, which set "
                 f"{set_index} produces somewhere in its day (board values "
                 f"{sorted(set(boards))}, all-five sums "
                 f"{sorted({sum(near) for near, _far in rounds})}); a total read off "
                 f"the level would be right by accident")

    # ---- identities -------------------------------------------------------------
    if list(NEAR_POSTS) != sorted(NEAR_POSTS) or list(FAR_POSTS) != sorted(FAR_POSTS):
        fail("the post names are not in sorted order; the fixture rows posts up by the "
             "name each one carries and its staged table is written against that order")
    if len(set(NEAR_POSTS) | set(FAR_POSTS)) != len(NEAR_POSTS) + len(FAR_POSTS):
        fail("two posts share a name, so one cannot be told from the other")
    if sorted(o for o, _ in PADS) != [1, 2, 3]:
        fail("the pads are not the first, the second and the third")
    if len({pid for _, pid in PADS}) != len(PADS):
        fail("two pads share a name")

    log(f"geometry SOLVED: lane derived at y={derived:.0f}; {runs} routes simulated "
        f"(3 staged days x 4 stretches x every plausible set-down); worst clearance to "
        f"a prop {worst[0]:.0f} uu (need {FX_MIN_PROP_CLEARANCE:.0f}), to a board "
        f"{worst[1]:.0f} uu (need {FX_MIN_BOARD_CLEARANCE:.0f}), to a wall "
        f"{worst[2]:.0f} uu; pad slots {pad_gap:.0f} uu apart against a disclosed "
        f"{FX_RESUME_RADIUS:.0f} uu radius; decoys disagree with all "
        f"{len(FIXTURE_ROUNDS)} staged rounds")


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
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW, M_HAZARD):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in CLASSES:
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
        # into a saved level on an earlier task, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def wall(env, box, label):
    """A 500-tall slab over an (x0, y0, x1, y1) footprint -- the same footprint
    check_geometry proved the walk clears."""
    x0, y0, x1, y1 = box
    block(env, CUBE,
          unreal.Vector(0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * WALL_HEIGHT),
          unreal.Vector(max(x1 - x0, 1.0) / 100.0, max(y1 - y0, 1.0) / 100.0,
                        WALL_HEIGHT / 100.0),
          label, M_DARK)


def place(env, cls_name, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        env[cls_name], loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def assert_movable(actor, comp_names, label):
    """Every prop is destroyed and respawned mid-run. A Static component logs a PIE
    mobility error that the functional test scores as a FAIL, so this is asserted on the
    PLACED actor rather than trusted from the constructor."""
    try:
        root = actor.get_editor_property("root_component")
    except Exception:  # noqa: BLE001 - not readable on every build
        root = None
    if root is not None and root.get_editor_property("mobility") \
            != unreal.ComponentMobility.MOVABLE:
        fail(f"{label}'s root is not MOVABLE and the yard is rebuilt twice mid-run")
    for comp_name in comp_names:
        comp = actor.get_editor_property(comp_name)
        if comp is None:
            fail(f"{label} has no {comp_name}; the fixture resolves it by that name")
        comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        if comp.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
            fail(f"{label}.{comp_name} would not go MOVABLE")


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    # BEFORE new_level: it saves an empty package immediately, so a script that raises
    # later leaves a plausible-looking map on disk that the automation run then reports
    # as "No automation tests".
    check_geometry()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # ---- the showroom floor ---------------------------------------------------
    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = 0.5 * (FLOOR_MAX[0] + FLOOR_MIN[0])
    mid_y = 0.5 * (FLOOR_MAX[1] + FLOOR_MIN[1])
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR)

    # Cross stripes every 200 cm, so pace and distance along the lane are readable by
    # eye in a capture; and the lane itself painted, so a person can see the walk keeps
    # to the empty band between the two rows and never brushes a prop.
    stripes = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0] - 1.0:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.0),
              unreal.Vector(0.24, span_y / 100.0, 0.02), f"Stripe_{stripes:02d}",
              M_STRIPE, collide=False)
        stripes += 1
        x += STRIPE_EVERY
    block(env, CUBE, unreal.Vector(mid_x, LANE_Y, 1.6),
          unreal.Vector(span_x / 100.0, 0.5, 0.03), "WalkingLane", M_STRIPE,
          collide=False)
    log(f"floor {span_x:.0f}x{span_y:.0f} + {stripes} stripes at {STRIPE_EVERY:.0f} cm "
        f"+ the lane painted at y={LANE_Y:.0f}")

    # ---- the walls ------------------------------------------------------------
    for idx, box in enumerate(wall_boxes()):
        wall(env, box, f"Wall_{idx:02d}")
    log(f"{len(wall_boxes())} wall slabs: the near yard walled with an "
        f"{2.0 * GATE_HALF:.0f}-wide gate gap on the lane at x={YARD_WEST_X:.0f}, a "
        f"solid dividing wall at x={DIVIDER_X:.0f}, the far yard walled, and a backdrop")

    # ---- the near yard --------------------------------------------------------
    for i, name in enumerate(NEAR_POSTS):
        px, py = post_slot(i, 0)
        post = place(env, "MemoryPostActor", unreal.Vector(px, py, 0.0),
                     f"MemoryPost_{name}")
        post.set_editor_property("yard_name", NEAR_YARD)
        post.set_editor_property("post_id", name)
        post.set_editor_property("worth_now", DECOY_NEAR[name])
        assert_movable(post, ("pillar", "ground_plate", "ground", "worth_sign"),
                       f"MemoryPost_{name}")

    for order, pad_id in PADS:
        px, py = pad_slot(order - 1, 0)
        pad = place(env, "MemoryPadActor", unreal.Vector(px, py, 0.0),
                    f"MemoryPad_{order}_{pad_id}")
        pad.set_editor_property("yard_name", NEAR_YARD)
        pad.set_editor_property("pad_id", pad_id)
        pad.set_editor_property("pad_order", order)
        assert_movable(pad, ("plate", "step", "lamp_post", "lamp_glow", "lamp",
                             "pad_sign"), f"MemoryPad_{order}_{pad_id}")

    near_board = place(env, "MemoryBoardActor",
                       unreal.Vector(NEAR_BOARD[0], NEAR_BOARD[1], 0.0),
                       "MemoryBoard_Near")
    near_board.set_editor_property("yard_name", NEAR_YARD)
    assert_movable(near_board, ("mast", "board"), "MemoryBoard_Near")

    # ---- the far yard: the in-scene control, torn down with the near one -------
    for i, name in enumerate(FAR_POSTS):
        px, py = far_post_slot(i, 0)
        post = place(env, "MemoryPostActor", unreal.Vector(px, py, 0.0),
                     f"MemoryPost_{name}")
        post.set_editor_property("yard_name", FAR_YARD)
        post.set_editor_property("post_id", name)
        post.set_editor_property("worth_now", DECOY_FAR[name])
        assert_movable(post, ("pillar", "ground_plate", "ground", "worth_sign"),
                       f"MemoryPost_{name}")

    far_board = place(env, "MemoryBoardActor",
                      unreal.Vector(FAR_BOARD[0], FAR_BOARD[1], 0.0),
                      "MemoryBoard_Far")
    far_board.set_editor_property("yard_name", FAR_YARD)
    assert_movable(far_board, ("mast", "board"), "MemoryBoard_Far")

    # ---- the runner, the landmarks, the light ---------------------------------
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(PLAYER_START[0], PLAYER_START[1], PLAYER_START_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A DIFFERENT landmark at each end of the backdrop, so a still camera and a moving
    # one can be told apart in a capture.
    for idx, lx in enumerate((FLOOR_MIN[0] + 400.0, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(lx, BACKDROP_Y - 400.0, 300.0),
              unreal.Vector(1.2 + idx * 1.0, 1.2 + idx * 1.0, 6.0),
              f"Landmark_{idx}", M_HAZARD if idx else M_GLOW)

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
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    place(env, "MemoryYardFunctionalTest",
          unreal.Vector(FLOOR_MIN[0] + 400.0, FLOOR_MIN[1] + 400.0, 200.0),
          "MemoryYardFunctionalTest")

    # ---- read back what was actually placed ----------------------------------
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so BP_ThirdPersonPlayerController and IMC_Default apply "
             "and a person can walk this yard by hand. The fixture asserts that lane as "
             "a HARNESS precondition")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    actors = eas.get_all_level_actors()

    def tagged(tag):
        return [a for a in actors if a.actor_has_tag(tag)]

    for tag, want in (("MemoryPost", len(NEAR_POSTS) + len(FAR_POSTS)),
                      ("MemoryPad", len(PADS)), ("MemoryBoard", 2)):
        got = len(tagged(tag))
        if got != want:
            fail(f"{got} actor(s) tagged {tag}, expected {want}; the fixture resolves "
                 f"every prop by tag and nothing else")

    seen_near, seen_far = [], []
    for post in tagged("MemoryPost"):
        yard = str(post.get_editor_property("yard_name"))
        pid = str(post.get_editor_property("post_id"))
        worth = int(post.get_editor_property("worth_now"))
        (seen_near if yard == NEAR_YARD else seen_far).append(pid)
        if yard not in (NEAR_YARD, FAR_YARD):
            fail(f"{post.get_actor_label()} says it is in {yard}; this level has two "
                 f"yards")
        want = DECOY_NEAR.get(pid, DECOY_FAR.get(pid))
        if want is None or worth != want:
            fail(f"{post.get_actor_label()} reads back PostId {pid} worth {worth}, "
                 f"expected {want}; the decoys did not survive placement")
        ground = post.get_editor_property("ground")
        extent = ground.get_scaled_box_extent()
        if abs(extent.x - POST_GROUND_HALF) > 1.0 \
                or abs(extent.y - POST_GROUND_HALF) > 1.0:
            fail(f"{post.get_actor_label()}'s patch of ground measures {extent.x:.0f} x "
                 f"{extent.y:.0f} in half-extent, expected {POST_GROUND_HALF:.0f}; "
                 f"every clearance this script solved is against that number, and a "
                 f"scaled root is how a 120-square pad once became 840 x 960 in mid-air")
        # A volume that does not reach the walking capsule's centre would never fire, and
        # the task would be unwinnable while looking perfect in the editor.
        world_z = ground.get_world_location().z
        if world_z - extent.z > CAPSULE_CENTRE_Z - 40.0 \
                or world_z + extent.z < CAPSULE_CENTRE_Z + 40.0:
            fail(f"{post.get_actor_label()}'s ground spans z "
                 f"{world_z - extent.z:.0f}..{world_z + extent.z:.0f}; a walking "
                 f"capsule rides its centre {CAPSULE_CENTRE_Z:.0f} above the floor and "
                 f"would miss it")
        try:
            if ground.get_collision_enabled() != unreal.CollisionEnabled.QUERY_ONLY:
                fail(f"{post.get_actor_label()}'s ground is not query-only; it would "
                     f"shove the runner instead of noticing them")
        except Exception:  # noqa: BLE001 - the getter is not on every build
            log("note: ground collision-enabled could not be read back on this build")
        origin, bounds = post.get_actor_bounds(only_colliding_components=True)
        if origin.z - bounds.z < -1.0:
            fail(f"{post.get_actor_label()} reaches down to z={origin.z - bounds.z:.1f}, "
                 f"below the floor")

    if sorted(seen_near) != sorted(NEAR_POSTS) or sorted(seen_far) != sorted(FAR_POSTS):
        fail(f"the placed posts read back {sorted(seen_near)} in {NEAR_YARD} and "
             f"{sorted(seen_far)} in {FAR_YARD}, expected {sorted(NEAR_POSTS)} and "
             f"{sorted(FAR_POSTS)}")

    orders = []
    for pad in tagged("MemoryPad"):
        if str(pad.get_editor_property("yard_name")) != NEAR_YARD:
            fail(f"{pad.get_actor_label()} is not in {NEAR_YARD}; the fixture reads "
                 f"which yard is the near one off the pads, and the marks all belong to "
                 f"one yard")
        orders.append(int(pad.get_editor_property("pad_order")))
        step = pad.get_editor_property("step")
        extent = step.get_scaled_box_extent()
        if abs(extent.x - PAD_STEP_HALF) > 1.0 or abs(extent.y - PAD_STEP_HALF) > 1.0:
            fail(f"{pad.get_actor_label()}'s step measures {extent.x:.0f} x "
                 f"{extent.y:.0f} in half-extent, expected {PAD_STEP_HALF:.0f}")
        world_z = step.get_world_location().z
        if world_z - extent.z > CAPSULE_CENTRE_Z - 40.0 \
                or world_z + extent.z < CAPSULE_CENTRE_Z + 40.0:
            fail(f"{pad.get_actor_label()}'s step spans z "
                 f"{world_z - extent.z:.0f}..{world_z + extent.z:.0f} and would never "
                 f"notice a walking capsule")
        if pad.get_editor_property("lamp") is None:
            fail(f"{pad.get_actor_label()} has no lamp; every gate that reads which "
                 f"mark is burning reads the light's own intensity")
    if sorted(orders) != [o for o, _ in PADS]:
        fail(f"the placed pads read back PadOrder {sorted(orders)}, expected "
             f"{[o for o, _ in PADS]}; the numbering did not survive placement, and the "
             f"order painted on a pad is the only thing that says which one is first")

    board_yards = sorted(str(b.get_editor_property("yard_name"))
                         for b in tagged("MemoryBoard"))
    if board_yards != sorted((NEAR_YARD, FAR_YARD)):
        fail(f"the counter boards read back {board_yards}; each yard needs exactly one "
             f"board of its own or there is no one number to read")

    if len(tagged("MemoryPost")) and not [a for a in actors
                                          if a.get_class().get_name()
                                          == "MemoryYardFunctionalTest"]:
        fail("the functional test is not in the level; L2 would report no automation "
             "tests and grade nothing")
    if len([a for a in actors if a.get_class().get_name() == "PlayerStart"]) != 1:
        fail("this level needs exactly one PlayerStart")
    lit = [a for a in actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    log(f"read back: {len(seen_near)} posts in {NEAR_YARD} {sorted(seen_near)} and "
        f"{len(seen_far)} in {FAR_YARD} {sorted(seen_far)}, all with decoy worths; "
        f"{len(orders)} pads with orders {sorted(orders)}, every trigger volume tall "
        f"enough to notice a walking capsule; one board per yard; one PlayerStart; one "
        f"fixture; no game mode named")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
