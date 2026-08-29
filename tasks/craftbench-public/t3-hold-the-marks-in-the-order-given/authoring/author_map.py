"""Authors L_MarkOrder for t3-hold-the-marks-in-the-order-given.

Run headless, from the repo root, with ABSOLUTE paths (a relative one reaches UE
verbatim and the boot dies with "Failed to open descriptor file"):

    REPO=$(pwd)
    MSYS_NO_PATHCONV=1 "$CB_UE_ROOT/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \\
      "$(cygpath -m "$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject")" \\
      -ExecutePythonScript="$(cygpath -m "$REPO/tasks/craftbench-public/\\
t3-hold-the-marks-in-the-order-given/authoring/author_map.py")" \\
      -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput

`-FullStdOutLogOutput` is not optional: without it the script runs and prints
NOTHING, which reads exactly like a crash. Every line is prefixed MARKORDER- and
the last one on success is MARKORDER-SAVED. A boot that ends without that marker
FAILED, whatever its exit code says.

WHAT THIS LEVEL IS. A striped hall with five painted rings on the floor and a duty
board on the wall at the north end. Three rings stand in the near row and two in
the far row; the closest pair -- Dune and the never-named control mark Elm -- is
EXACTLY 500 cm centre to centre, which is the separation the prompt promises,
asserted at its tightest rather than somewhere comfortable.

NOTHING HERE IS THE ANSWER, AND ALMOST NOTHING HERE IS EVEN THE QUESTION. Every
number the task grades -- the board's list, its length, and each mark's
RequiredSeconds -- is written by AMarkOrderFunctionalTest in PrepareTest, which
runs AFTER every BeginPlay, and is re-written seven more times while the run is in
flight. What this script commits is a DECOY: a two-name list that names the
control mark, and five sets of seconds none of which the fixture ever stages. A
submission that snapshots the level at BeginPlay reads 0/2 where the baseline
checkpoint demands 0/4, and treats the control as listed. It is wrong twice
before the character has entered a single ring.

THE GEOMETRY IS NOT HAND-TUNED, IT IS RE-SOLVED. AMarkOrderFunctionalTest solves
its whole route from the marks' live transforms and ends the run as a
HARNESS-PRECONDITION -- exit 7, non-graded, and expensive -- if any clearance
fails to come out. So this script runs THE SAME ARITHMETIC, over both the route
PRIMITIVES the fixture proves up front and all thirty-eight step polylines it
walks, and REFUSES TO SAVE a hall the drive could not walk. A layout fault has to
be caught here, in seconds, and never at minute nine of a graded run.

This level names NO game mode: it inherits the project default, so
BP_ThirdPersonGameMode and its BP_ThirdPersonPlayerController (which carries
IMC_Default) come with it and the map is controllable with WASD by a person.
Naming a task game mode replaces GlobalDefaultGameMode and silently drops both
halves of Enhanced Input, and the map still grades byte-identically -- five of
six ThirdPerson maps once shipped visible, animated and completely uncontrollable
that way. The fixture makes it a HARNESS-PRECONDITION; this script refuses to
save it.

EVERY MARK IS YAWED 180 AND THE BOARD IS YAWED 90. A UTextRenderComponent is read
from its own local +X. The mark's Face is built at relative yaw +90 and the
board's two faces at relative yaw 180, so those actor yaws are what point all six
readouts SOUTH -- at the camera plan's poses and at anybody standing in the hall
-- instead of half of them at a wall. Rotation is free: the ring is a cylinder,
IsInsideRing is flat and centre-relative, and the fixture reads GetActorLocation
and nothing else.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-hold-the-marks-in-the-order-given"
MAP_PKG = f"/Game/Maps/{TASK}/L_MarkOrder"

# ============================== the hall's shape ==============================
# (name, x, y). Three in the near row at y = -900, two in the far row at y = +900.
# The lane the drive walks runs along y = 0, so both rows sit 900 uu off it -- well
# past the 150 uu ring plus the 120 uu of clearance the fixture demands.
#
# Dune--Elm is EXACTLY 500 uu, the minimum the prompt promises. The control mark
# stands right beside a listed one ON PURPOSE: "walking across the mark the board
# never names changes nothing" is then asserted where it is hardest rather than
# where it is easiest. Every other pair is >= 1,200 uu.
MARKS = (
    ("Ash", -1600.0, -900.0),
    ("Birch", -400.0, -900.0),
    ("Cedar", 800.0, -900.0),
    ("Dune", 200.0, 900.0),
    ("Elm", 700.0, 900.0),
)
CONTROL = "Elm"          # the one mark NEITHER staged list may ever name
MARK_YAW = 180.0         # points every Face south, at the camera and at the hall
MARK_STAND_Z = 0.0       # the ring is paint at z = 0..4; the actor sits on the floor

BOARD_XY = (0.0, 2600.0)
BOARD_YAW = 90.0         # points OrderFace and TallyFace south, down the hall
BOARD_STAND_Z = 0.0

PLAYER_START = (-3200.0, 0.0)
PLAYER_START_Z = 110.0
PLAYER_START_YAW = 0.0   # facing +X, straight at the marks

FLOOR_MIN = (-4000.0, -4000.0)
FLOOR_MAX = (4000.0, 4000.0)
STRIPE_EVERY = 200.0     # task.md: "8,000 x 8,000, striped every 200 cm"

FIXTURE_AT = (0.0, 3500.0, 240.0)

# ======================= THE DECOY THE LEVEL COMMITS ==========================
# A TWO-name list, so a BeginPlay snapshot reads 0/2 against the 0/4 the baseline
# checkpoint demands and dies at the first gate armed. It names the CONTROL MARK,
# so the same cached answer also treats Elm as listed and fails
# TheUnnamedMarkStaysCold on the same frame -- the cached-list discrimination does
# not rest on one string any more than the empty one does.
DECOY_LIST = ("Elm", "Ash")

# Every one of these differs from that mark's OWN staged seconds in both rounds
# and from every mid-stand rewrite, by at least 0.5 s (checked below, per mark).
#
# Cedar is 11.0 and not the tidy 6.5 that would continue the ladder: 6.5 is
# EXACTLY Cedar's round-1 staged value, so the tidy number would have handed a
# BeginPlay-caching submission the right answer for that one mark. notes.md's
# "every one different from its round-1 value" was written against the ladder and
# was false for Cedar; the number moved, not the claim.
DECOY_SECONDS = {
    "Ash": 9.5,
    "Birch": 8.0,
    "Cedar": 11.0,
    "Dune": 5.0,
    "Elm": 3.5,
}
RING_RADIUS_UU = 150.0

# ============ MIRRORS OF THE FIXTURE'S OWN TABLES AND CONSTANTS ==============
# MarkOrderFunctionalTest.cpp owns these; they are copied here so that "the hall
# fits the fixture" is MEASURED at authoring time instead of discovered as a
# HARNESS-PRECONDITION at minute nine of a graded run. If the two ever disagree
# the level is wrong, not the fixture.
ROUND1 = {"Ash": 3.5, "Birch": 5.0, "Cedar": 6.5, "Dune": 2.5, "Elm": 8.0}
ROUND1_LIST = ("Dune", "Birch", "Cedar", "Ash")
ROUND2 = {"Ash": 4.5, "Birch": 7.0, "Cedar": 3.0, "Dune": 6.0, "Elm": 8.0}
ROUND2_LIST = ("Cedar", "Dune", "Ash")
# THE SAME-LENGTH REORDER. Three names again, the SAME three names, the SAME
# first name, and every mark's seconds left exactly where they already stand:
# only the ORDER moves. Round 1 -> round 2 goes four names to three, so a change
# detector that compares LENGTHS (or first names, or the set of names) fires
# there and looks right; this one is invisible to every one of them, which is
# what makes the difference between those detectors and a real order-sensitive
# comparison observable at all. ROUND3 is asserted below to BE round 2 after both
# of its rewrites -- no finished mark may see its number move.
ROUND3 = {"Ash": 4.5, "Birch": 7.0, "Cedar": 5.2, "Dune": 1.5, "Elm": 8.0}
ROUND3_LIST = ("Cedar", "Ash", "Dune")
# (round, mark, new value), applied in this order. The first two of each round
# fire MID-STAND; the last one of each fires with the character PARKED CLEAR OF
# EVERY RING, dropping the current mark's number below what it has already
# banked -- which has to finish that mark at once with nobody moving.
REWRITES = (
    (1, "Dune", 4.2),
    (1, "Birch", 2.0),
    (1, "Cedar", 1.2),
    (2, "Cedar", 5.2),
    (2, "Dune", 1.5),
)

MIN_SEPARATION_UU = 500.0    # kMinSeparationUu
NON_TARGET_CLEAR_UU = 120.0  # kNonTargetClearUu
PARK_CLEAR_UU = 300.0        # kParkClearUu
PARK_BACKOFF_UU = 1000.0     # kParkBackOffUu
CROSS_OUT_UU = 700.0         # kCrossOutUu
CROSS_BACK_UU = 500.0        # kCrossBackUu
CROSS_UP_UU = 600.0          # kCrossUpUu
ROW_ALIGN_UU = 5.0           # kRowAlignUu
MIN_SECONDS_S = 1.0          # kMinSecondsS
MIN_SECONDS_GAP_S = 0.5      # kMinSecondsGapS

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"MARKORDER- {msg}")


def fail(msg):
    unreal.log_error(f"MARKORDER-ERROR {msg}")
    raise SystemExit(1)


# ------------------------------------------------------------------ geometry

def xy(name):
    for label, x, y in MARKS:
        if label == name:
            return (x, y)
    fail(f"no mark called {name}")


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def lane(x):
    return (x, 0.0)


def point_to_segment(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    if span < 1e-9:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / span))
    return dist(p, (ax + t * dx, ay + t * dy))


def path_is_clear(start, waypoints, allowed):
    """The fixture's PathIsClear, in Python: does this polyline clear every ring it
    is not ALLOWED to cross, by the ring radius plus NON_TARGET_CLEAR_UU?

    Solved analytically rather than by the fixture's 25 uu sampling, which is
    strictly tighter -- a polyline this accepts, the sampler accepts too."""
    at = start
    for to in waypoints:
        for name, mx, my in MARKS:
            if name in allowed:
                continue
            d = point_to_segment((mx, my), at, to)
            need = RING_RADIUS_UU + NON_TARGET_CLEAR_UU
            if d < need:
                return (f"the leg to ({to[0]:.0f}, {to[1]:.0f}) passes {d:.0f} uu from "
                        f"{name}, whose ring reaches {RING_RADIUS_UU:.0f} -- it needs "
                        f"{need:.0f}")
        at = to
    return None


def on_floor(p, margin=200.0):
    return (FLOOR_MIN[0] + margin <= p[0] <= FLOOR_MAX[0] - margin
            and FLOOR_MIN[1] + margin <= p[1] <= FLOOR_MAX[1] - margin)


# --------------------------------------------------- the checks that refuse

def check_layout():
    names = [m[0] for m in MARKS]
    if len(set(names)) != len(names):
        fail(f"two marks share a name in {names}; a mark is known by its name and by "
             f"nothing else")
    if CONTROL not in names:
        fail(f"the control mark {CONTROL} is not in the hall")
    if len(MARKS) != 5:
        fail(f"{len(MARKS)} marks; the fixture resolves exactly five by tag and ends "
             f"the run as a HARNESS-PRECONDITION otherwise")

    closest = None
    for i in range(len(MARKS)):
        for j in range(i + 1, len(MARKS)):
            d = dist(MARKS[i][1:], MARKS[j][1:])
            if d < MIN_SEPARATION_UU - 1.0:
                fail(f"{MARKS[i][0]} and {MARKS[j][0]} stand {d:.0f} uu apart and the "
                     f"prompt promises at least {MIN_SEPARATION_UU:.0f}; the character "
                     f"could be on two marks at once")
            if closest is None or d < closest[0]:
                closest = (d, MARKS[i][0], MARKS[j][0])
    if abs(closest[0] - MIN_SEPARATION_UU) > 1.0:
        fail(f"the closest pair is {closest[1]}--{closest[2]} at {closest[0]:.0f} uu; "
             f"task.md commits to EXACTLY {MIN_SEPARATION_UU:.0f}, because the control "
             f"mark standing right beside a listed one is what makes the crossing "
             f"claim worth asserting")
    if CONTROL not in (closest[1], closest[2]):
        fail(f"the closest pair is {closest[1]}--{closest[2]} and neither is the "
             f"control mark {CONTROL}; the point of the tightest pair is that the "
             f"never-named mark is the one crowding a listed one")

    for name, mx, my in MARKS:
        if abs(my) < RING_RADIUS_UU + NON_TARGET_CLEAR_UU:
            fail(f"{name} stands {abs(my):.0f} uu off the lane the drive walks along "
                 f"(y = 0) and its ring reaches {RING_RADIUS_UU:.0f}; every transit "
                 f"would clip it")
        if not on_floor((mx, my), margin=600.0):
            fail(f"{name} at ({mx:.0f}, {my:.0f}) is not comfortably on the floor")

    near = sorted(n for n, _, y in MARKS if y < 0.0)
    far = sorted(n for n, _, y in MARKS if y > 0.0)
    if len(near) != 3 or len(far) != 2:
        fail(f"task.md commits to three marks in the near row and two in the far one; "
             f"this hall has {len(near)} and {len(far)}")
    log(f"layout: near row {near}, far row {far}, closest pair {closest[1]}--"
        f"{closest[2]} at {closest[0]:.0f} uu")


def check_staged_set(which, seconds, listed):
    for name in seconds:
        if seconds[name] < MIN_SECONDS_S:
            fail(f"{which} stages {name} at {seconds[name]:.2f} s; a mark nobody can "
                 f"measurably stand on is not a mark")
    items = sorted(seconds.items(), key=lambda kv: kv[1])
    for (n1, v1), (n2, v2) in zip(items, items[1:]):
        if v2 - v1 < MIN_SECONDS_GAP_S:
            fail(f"{which} stages {n1} at {v1:.2f} and {n2} at {v2:.2f}, inside the "
                 f"{MIN_SECONDS_GAP_S:.2f} s the fixture needs to tell 'used another "
                 f"mark's number' apart from a lagging face")
    for name in listed:
        if name not in seconds:
            fail(f"{which} names '{name}' and no mark in the hall carries that name")
        if name == CONTROL:
            fail(f"{which} names '{name}', which is the IN-SCENE NEGATIVE CONTROL -- "
                 f"the one mark neither list may ever name")
    if len(set(listed)) != len(listed):
        fail(f"{which} names a mark twice: {listed}")
    return min(v2 - v1 for (_, v1), (_, v2) in zip(items, items[1:]))


def check_staging():
    """Every set the fixture ever writes, including the two the mid-stand rewrites
    produce. A table whose separation does not come out has to be a staging fault
    BEFORE it can be mistaken for a model's."""
    gaps = {}
    gaps["round 1"] = check_staged_set("round 1", dict(ROUND1), ROUND1_LIST)
    gaps["round 2"] = check_staged_set("round 2", dict(ROUND2), ROUND2_LIST)
    live = dict(ROUND1)
    for rnd, name, value in REWRITES:
        if rnd == 2:
            continue
        live[name] = value
        gaps[f"round 1 after {name} -> {value}"] = check_staged_set(
            f"round 1 after the mid-stand rewrite of {name}", dict(live), ROUND1_LIST)
    live2 = dict(ROUND2)
    for rnd, name, value in REWRITES:
        if rnd == 1:
            continue
        live2[name] = value
        gaps[f"round 2 after {name} -> {value}"] = check_staged_set(
            f"round 2 after the mid-stand rewrite of {name}", dict(live2), ROUND2_LIST)

    gaps["the same-length reorder"] = check_staged_set(
        "the same-length reorder", dict(ROUND3), ROUND3_LIST)
    if ROUND3 != live2:
        fail(f"the same-length reorder stages {ROUND3} and the hall is carrying "
             f"{live2} when it lands. It has to move the ORDER and nothing else: "
             f"three marks are FINISHED at that instant, and whether a finished mark "
             f"comes undone when its own number moves under it is a corner no prompt "
             f"sentence settles and no gate can judge")

    if len(ROUND1_LIST) == len(ROUND2_LIST):
        fail(f"the first two staged lists carry {len(ROUND1_LIST)} names each; the "
             f"tally's right-hand number is one of the things this task grades, so "
             f"those two have to differ in LENGTH as well as in order")
    if list(ROUND1_LIST) == list(ROUND2_LIST):
        fail("the first two staged lists are the same list")
    # AND THE THIRD ONE DIFFERS IN ORDER *ONLY*, which is the whole point of it.
    if len(ROUND3_LIST) != len(ROUND2_LIST):
        fail(f"the reorder carries {len(ROUND3_LIST)} names against the previous "
             f"list's {len(ROUND2_LIST)}; it has to keep the LENGTH, or a change "
             f"detector that compares lengths passes it")
    if list(ROUND3_LIST) == list(ROUND2_LIST):
        fail("the reorder is the same list in the same order, so nothing about it "
             "can be judged")
    if ROUND3_LIST[0] != ROUND2_LIST[0]:
        fail(f"the reorder starts with '{ROUND3_LIST[0]}' where the previous list "
             f"started with '{ROUND2_LIST[0]}'; it has to keep the FIRST NAME, or a "
             f"change detector that only watches the first name passes it")
    if set(ROUND3_LIST) != set(ROUND2_LIST):
        fail(f"the reorder carries {sorted(set(ROUND3_LIST))} against the previous "
             f"list's {sorted(set(ROUND2_LIST))}; it has to carry the same NAMES, or "
             f"a change detector that compares the set of names passes it")

    # THE ROUND-1 ORDER MUST MATCH NO ORDERABLE PROPERTY OF THE HALL, or a
    # submission could infer it instead of reading it.
    park = solve_park()
    orderings = {
        "alphabetical": sorted(n for n in ROUND1_LIST),
        "x ascending": sorted(ROUND1_LIST, key=lambda n: xy(n)[0]),
        "distance from the parking spot": sorted(
            ROUND1_LIST, key=lambda n: dist(park, xy(n))),
        "required seconds ascending": sorted(ROUND1_LIST, key=lambda n: ROUND1[n]),
        "placement order": [n for n, _, _ in MARKS if n in ROUND1_LIST],
    }
    for label, order in orderings.items():
        for candidate, direction in ((order, ""), (order[::-1], " reversed")):
            if list(ROUND1_LIST) == list(candidate):
                fail(f"the round-1 list {list(ROUND1_LIST)} IS the hall in "
                     f"{label}{direction} order; it has to be readable off the board "
                     f"and derivable from nothing else")
    log(f"staging: every staged set >= {MIN_SECONDS_GAP_S} s apart (tightest "
        f"{min(gaps.values()):.2f} s), lists {len(ROUND1_LIST)} then "
        f"{len(ROUND2_LIST)} then {len(ROUND3_LIST)} names "
        f"({list(ROUND2_LIST)} -> {list(ROUND3_LIST)} moves the order and nothing "
        f"else), round-1 order matches none of {sorted(orderings)}")


def check_decoy():
    if len(DECOY_LIST) == len(ROUND1_LIST):
        fail(f"the committed list carries {len(DECOY_LIST)} names, the same as the "
             f"round-1 list the fixture stages. The whole point of the decoy is that "
             f"a BeginPlay snapshot reads the WRONG DENOMINATOR at the baseline")
    if CONTROL not in DECOY_LIST:
        fail(f"the committed list {list(DECOY_LIST)} does not name {CONTROL}. It is "
             f"meant to, so that a cached list also treats the control mark as listed "
             f"and the cached-list discrimination does not rest on one gate")
    for name in DECOY_LIST:
        if name not in DECOY_SECONDS:
            fail(f"the committed list names '{name}' and no mark carries that name")
    for name in DECOY_SECONDS:
        staged = [ROUND1[name], ROUND2[name]] + [
            v for _, n, v in REWRITES if n == name]
        for value in staged:
            if abs(DECOY_SECONDS[name] - value) < MIN_SECONDS_GAP_S:
                fail(f"{name} is committed at {DECOY_SECONDS[name]:.2f} s and the "
                     f"fixture stages it at {value:.2f}; a submission that read the "
                     f"level once would be RIGHT about {name}, and the committed "
                     f"numbers exist precisely so that it is wrong about every mark")
    items = sorted(DECOY_SECONDS.items(), key=lambda kv: kv[1])
    tight = min(v2 - v1 for (_, v1), (_, v2) in zip(items, items[1:]))
    if tight < MIN_SECONDS_GAP_S:
        fail(f"the committed seconds are only {tight:.2f} s apart at their tightest; "
             f"a fixture that validated separation on its first read of the level "
             f"would trip on the decoy")
    log(f"decoy: list {list(DECOY_LIST)} ({len(DECOY_LIST)} names against the staged "
        f"{len(ROUND1_LIST)}), seconds {DECOY_SECONDS}, tightest pair {tight:.2f} s, "
        f"every mark's number moved off both staged values")


def solve_park():
    """The fixture's own BuildRoute: one clear stretch west of the westmost mark, on
    the lane. DERIVED, so a re-authored hall moves it instead of leaving it inside a
    ring."""
    return lane(min(m[1] for m in MARKS) - PARK_BACKOFF_UU)


def drive_steps():
    """The thirty-eight polylines BeginStep walks, in order, chained from where the
    previous one ended. Every one is re-checked here, because the fixture checks
    them again at run time and a failure THERE costs a whole graded run.

    Five phases were added on 2026-08-19, all of them because a rule with two
    branches whose drive only exercises one of them is an UNGATED rule: two SKIP
    AHEADS (out of turn onto a name that is not due yet, rather than onto one
    already finished -- every out-of-turn step in the old drive landed on a mark
    that was both already finished and at list index 0), and two WALK-CLEAR phases
    that park the character outside every ring while the fixture drops the current
    mark's number below its bank, so a completion has to fire with nobody standing
    anywhere. The reorder in step 36 needs no polyline: the character is already
    parked."""
    ash, birch, cedar, dune, elm = (xy(n) for n in
                                    ("Ash", "Birch", "Cedar", "Dune", "Elm"))
    park = solve_park()
    east = (elm[0] + CROSS_OUT_UU, elm[1])
    west = (birch[0] - CROSS_BACK_UU, birch[1])
    north = (elm[0], elm[1] + CROSS_UP_UU)
    return (park, east, west, north, (
        # (step, label, waypoints, marks this step is ALLOWED to cross)
        (0, "walk-to-the-parking-spot", [park], ()),
        (1, "the-baseline", [], ()),
        (2, "stand-on-the-first-name", [lane(dune[0]), dune], ("Dune",)),
        (3, "step-ahead-onto-a-name-that-is-not-due-yet",
         [lane(dune[0]), lane(cedar[0]), cedar], ("Dune", "Cedar")),
        (4, "re-bank-the-first-name",
         [lane(cedar[0]), lane(dune[0]), dune], ("Cedar", "Dune")),
        (5, "walk-out-and-wait", [lane(dune[0]), park], ("Dune",)),
        (6, "walk-back-on-to-the-finish", [lane(dune[0]), dune], ("Dune",)),
        (7, "cross-the-unnamed-mark", [east], ("Dune", "Elm")),
        (8, "stand-on-the-second-name",
         [lane(east[0]), lane(birch[0]), birch], ("Birch",)),
        (9, "step-onto-a-finished-name-out-of-turn",
         [lane(birch[0]), lane(dune[0]), dune], ("Birch", "Dune")),
        (10, "step-off-the-poisoned-mark", [lane(dune[0])], ("Dune",)),
        (11, "re-walk-the-first-name", [dune], ("Dune",)),
        (12, "re-walk-the-second-name",
         [lane(dune[0]), lane(birch[0]), birch], ("Dune", "Birch")),
        (13, "re-walk-the-third-name-part-way",
         [lane(birch[0]), lane(cedar[0]), cedar], ("Birch", "Cedar")),
        (14, "walk-clear-while-the-third-name-is-still-owed",
         [lane(cedar[0]), park], ("Cedar",)),
        (15, "re-walk-the-last-name", [lane(ash[0]), ash], ("Ash",)),
        (16, "hold-the-finished-round", [lane(ash[0])], ("Ash",)),
        (17, "step-out-of-turn-again", [lane(dune[0]), dune], ("Dune",)),
        (18, "step-off-again", [lane(dune[0])], ("Dune",)),
        (19, "back-on-and-bank-a-little", [dune], ("Dune",)),
        (20, "the-shift-change", [], ("Dune",)),
        (21, "bank-the-new-first-name",
         [lane(dune[0]), lane(cedar[0]), cedar], ("Dune", "Cedar")),
        (22, "step-ahead-onto-a-new-name-that-is-not-due-yet",
         [lane(cedar[0]), lane(dune[0]), dune], ("Cedar", "Dune")),
        (23, "re-bank-the-new-first-name",
         [lane(dune[0]), lane(cedar[0]), cedar], ("Dune", "Cedar")),
        (24, "walk-out-and-wait-again", [lane(cedar[0]), park], ("Cedar",)),
        (25, "back-on-to-the-new-finish", [lane(cedar[0]), cedar], ("Cedar",)),
        (26, "cross-the-demoted-name", [west], ("Cedar", "Birch")),
        (27, "cross-the-unnamed-mark-again",
         [lane(west[0]), lane(elm[0]), north], ("Elm",)),
        (28, "bank-the-new-second-name-part-way",
         [(dune[0], north[1]), dune], ("Dune",)),
        (29, "step-onto-the-new-first-name-out-of-turn",
         [lane(dune[0]), lane(cedar[0]), cedar], ("Dune", "Cedar")),
        (30, "step-off-the-poisoned-mark-again", [lane(cedar[0])], ("Cedar",)),
        (31, "re-walk-the-new-first-name", [cedar], ("Cedar",)),
        (32, "re-walk-the-new-second-name-part-way",
         [lane(cedar[0]), lane(dune[0]), dune], ("Cedar", "Dune")),
        (33, "walk-clear-while-the-new-second-name-is-still-owed",
         [lane(dune[0]), park], ("Dune",)),
        (34, "re-walk-the-new-last-name", [lane(ash[0]), ash], ("Ash",)),
        (35, "park-and-hold", [lane(ash[0]), park], ("Ash",)),
        (36, "the-board-changes-its-mind", [], ()),
        (37, "park-and-hold-again", [], ()),
    ))


def check_route():
    ash, birch, cedar, dune, elm = (xy(n) for n in
                                    ("Ash", "Birch", "Cedar", "Dune", "Elm"))
    park, east, west, north, steps = drive_steps()

    if not on_floor(park, margin=400.0):
        fail(f"the derived parking spot ({park[0]:.0f}, {park[1]:.0f}) is off the "
             f"floor; widen FLOOR_MIN or move the westmost mark east")
    for name, mx, my in MARKS:
        d = dist(park, (mx, my))
        if d < RING_RADIUS_UU + PARK_CLEAR_UU:
            fail(f"the parking spot is {d:.0f} uu from {name}, whose ring reaches "
                 f"{RING_RADIUS_UU:.0f}; the drive parks at least "
                 f"{PARK_CLEAR_UU:.0f} clear of every ring")

    # The three head-on crossings the fixture demands of the layout, by name.
    if abs(elm[1] - dune[1]) > ROW_ALIGN_UU or elm[0] <= dune[0]:
        fail(f"Elm is at ({elm[0]:.0f},{elm[1]:.0f}) and Dune at "
             f"({dune[0]:.0f},{dune[1]:.0f}); the drive crosses the unnamed mark "
             f"head-on along their shared row, which needs Elm east of Dune on the "
             f"same row")
    if abs(birch[1] - cedar[1]) > ROW_ALIGN_UU or birch[0] >= cedar[0]:
        fail(f"Cedar is at ({cedar[0]:.0f},{cedar[1]:.0f}) and Birch at "
             f"({birch[0]:.0f},{birch[1]:.0f}); the drive crosses the demoted mark "
             f"head-on along their shared row, which needs Birch west of Cedar on the "
             f"same row")

    max_x = max(m[1] for m in MARKS)
    primitives = (
        ("the lane the drive walks along", park, [lane(max_x + CROSS_OUT_UU)], ()),
        ("the crossing of the unnamed mark", dune, [east], ("Dune", "Elm")),
        ("the way back to the lane from the far side of the unnamed mark",
         east, [lane(east[0])], ()),
        ("the crossing of the demoted mark", cedar, [west], ("Cedar", "Birch")),
        ("the way back to the lane from the far side of the demoted mark",
         west, [lane(west[0])], ()),
        ("the second crossing of the unnamed mark",
         lane(elm[0]), [north], ("Elm",)),
        ("the way back down into Dune from the top of the hall",
         north, [(dune[0], north[1]), dune], ("Dune",)),
    )
    for name, mx, my in MARKS:
        primitives += ((f"the walk in to {name}", lane(mx), [(mx, my)], (name,)),)
    for label, start, way, allowed in primitives:
        why = path_is_clear(start, way, allowed)
        if why is not None:
            fail(f"{label} is not clear -- {why}")

    # AND THEN THE POLYLINES THEMSELVES, chained. BuildRoute proves the primitives;
    # BeginStep proves the actual walk, and it is the one that ends a graded run.
    here = (PLAYER_START[0], PLAYER_START[1])
    for step, label, way, allowed in steps:
        under = tuple(n for n, mx, my in MARKS
                      if dist(here, (mx, my)) <= RING_RADIUS_UU + 1.0)
        why = path_is_clear(here, way, tuple(allowed) + under)
        if why is not None:
            fail(f"drive step {step} ({label}) cannot be walked -- {why}")
        for p in way:
            if not on_floor(p, margin=200.0):
                fail(f"drive step {step} ({label}) walks to ({p[0]:.0f}, "
                     f"{p[1]:.0f}), which is off the floor")
        if way:
            here = way[-1]

    for name, mx, my in MARKS:
        d = dist(PLAYER_START, (mx, my))
        if d < RING_RADIUS_UU + PARK_CLEAR_UU:
            fail(f"the PlayerStart is {d:.0f} uu from {name}; a character that spawns "
                 f"inside or beside a ring makes the opening frames mean something")
    if not on_floor(PLAYER_START, margin=400.0):
        fail(f"the PlayerStart at {PLAYER_START} is off the floor")

    log(f"route solved: park ({park[0]:.0f},{park[1]:.0f}), lane y=0, east end "
        f"{east[0]:.0f}, west end {west[0]:.0f}, north end {north[1]:.0f}; all "
        f"{len(primitives)} primitives and all {len(steps)} drive steps clear every "
        f"ring they are not meant to cross by {NON_TARGET_CLEAR_UU:.0f} uu")


# ------------------------------------------------------------------ authoring

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
    for cls_name in ("FloorMarkActor", "DutyBoardActor", "MarkOrderFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built? "
                 f"(MarkOrderFunctionalTest lives in CraftBenchTests, the marks and "
                 f"the board in ThirdPerson; both have to be compiled)")
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
        # alone did not survive into the saved level, and a stripe that quietly
        # becomes a step you trip over would deflect the whole drive.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def make_movable(component, label):
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    if component.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
        fail(f"{label} would not go MOVABLE. A STATIC point light CANNOT change "
             f"intensity at run time, so every lamp in the hall would read the same "
             f"number for the whole night and the lamp channel -- one of the three "
             f"things this task grades -- would be dead while looking healthy")


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # BEFORE new_level: it writes an empty package immediately, so a script that
    # raises later leaves a plausible-looking map on disk that the automation run
    # then reports as "No automation tests".
    check_layout()
    check_staging()
    check_decoy()
    check_route()

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
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor",
                  M_FLOOR, collide=True)
    # THE FLOOR'S TOP FACE, MEASURED off the placed block. "A 100 uu cube centred at
    # z=-50 has its top at z=0" is arithmetic in a comment, which is not evidence.
    f_origin, f_extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = f_origin.z + f_extent.z
    if abs(floor_top_z) > 1.0:
        fail(f"the floor's top face measures z={floor_top_z:.1f}; every z in this "
             f"script assumes 0 and the marks would float or sink")
    log(f"floor {span_x:.0f}x{span_y:.0f}, top face measured at z={floor_top_z:.1f}")

    # Stripes ACROSS the lane, so pace along it is readable by eye. Every fifth one
    # is wider, which is a 1,000 uu ruler a reviewer can count.
    stripes = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0] - 1.0:
        heavy = abs(round(x / 1000.0) * 1000.0 - x) < 1.0
        block(env, CUBE, unreal.Vector(x, mid_y, 1.0),
              unreal.Vector(0.24 if heavy else 0.10, span_y / 100.0, 0.02),
              f"Stripe_{stripes:02d}", M_DARK if heavy else M_STRIPE)
        stripes += 1
        x += STRIPE_EVERY
    log(f"painted {stripes} cross-stripes every {STRIPE_EVERY:.0f} uu")

    # ------------------------------------------------------------- the marks
    placed = {}
    for name, mx, my in MARKS:
        mark = eas.spawn_actor_from_class(
            env["FloorMarkActor"],
            unreal.Vector(mx, my, MARK_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=MARK_YAW))
        if mark is None:
            fail(f"could not place the mark called {name}")
        mark.set_actor_label(f"FloorMark_{name}")
        mark.set_editor_property("mark_name", unreal.Name(name))
        mark.set_editor_property("required_seconds", DECOY_SECONDS[name])
        mark.set_editor_property("ring_radius_uu", RING_RADIUS_UU)
        for comp_name in ("anchor", "ring", "mast", "lamp", "face", "name_plate"):
            comp = mark.get_editor_property(comp_name)
            if comp is None:
                fail(f"the mark called {name} has no {comp_name}; the fixture reads "
                     f"the lamp and the face off the placed actor")
            make_movable(comp, f"FloorMark_{name}.{comp_name}")
        placed[name] = mark

    board = eas.spawn_actor_from_class(
        env["DutyBoardActor"],
        unreal.Vector(BOARD_XY[0], BOARD_XY[1], BOARD_STAND_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=BOARD_YAW))
    if board is None:
        fail("could not place the duty board")
    board.set_actor_label("DutyBoard")
    board.set_editor_property(
        "listed_mark_names", [unreal.Name(n) for n in DECOY_LIST])
    for comp_name in ("anchor", "panel", "order_face", "tally_face"):
        comp = board.get_editor_property(comp_name)
        if comp is None:
            fail(f"the board has no {comp_name}")
        make_movable(comp, f"DutyBoard.{comp_name}")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(PLAYER_START[0], PLAYER_START[1], PLAYER_START_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=PLAYER_START_YAW))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A back wall behind the board and two differently sized posts at its ends, so a
    # moving camera reads as moving. NON-COLLIDING, like everything but the floor.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 150.0),
          unreal.Vector(span_x / 100.0, 0.5, 3.0), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 400.0, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 500.0, 330.0),
              unreal.Vector(1.1 + idx * 1.1, 1.1 + idx * 1.1, 6.6),
              f"Landmark_{idx}", M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-60.0))
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
        env["MarkOrderFunctionalTest"],
        unreal.Vector(*FIXTURE_AT), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("MarkOrderFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default, or both halves of Enhanced Input vanish and the map "
             "grades byte-identically while being impossible to walk around")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode and its "
        "BP_ThirdPersonPlayerController, which carries IMC_Default)")

    # ------------------------------------------------- read the level back
    # Everything above is what was ASKED FOR. This is what is about to be SAVED.
    saved_marks = [a for a in eas.get_all_level_actors() if a.actor_has_tag("HallMark")]
    if len(saved_marks) != len(MARKS):
        fail(f"{len(saved_marks)} actor(s) tagged HallMark, expected {len(MARKS)}; "
             f"the fixture resolves the hall by tag and ends the run as a "
             f"HARNESS-PRECONDITION on any other count")
    saved_boards = [a for a in eas.get_all_level_actors()
                    if a.actor_has_tag("DutyBoard")]
    if len(saved_boards) != 1:
        fail(f"{len(saved_boards)} actor(s) tagged DutyBoard, expected exactly one")

    read_back = {}
    for a in saved_marks:
        name = str(a.get_editor_property("mark_name"))
        loc = a.get_actor_location()
        read_back[name] = (float(a.get_editor_property("required_seconds")),
                           float(a.get_editor_property("ring_radius_uu")),
                           round(loc.x, 1), round(loc.y, 1))
    for name, mx, my in MARKS:
        if name not in read_back:
            fail(f"no saved mark calls itself '{name}'; the fixture stages "
                 f"{[m[0] for m in MARKS]} and grades nothing else")
        secs, radius, gx, gy = read_back[name]
        if abs(secs - DECOY_SECONDS[name]) > 0.01:
            fail(f"{name} saved carrying {secs:.2f} s, not the committed "
                 f"{DECOY_SECONDS[name]:.2f}")
        if abs(radius - RING_RADIUS_UU) > 0.5:
            fail(f"{name} saved with a {radius:.1f} uu ring; the prompt discloses "
                 f"{RING_RADIUS_UU:.0f} and the fixture refuses anything else")
        if abs(gx - mx) > 1.0 or abs(gy - my) > 1.0:
            fail(f"{name} saved at ({gx:.0f},{gy:.0f}), not ({mx:.0f},{my:.0f})")

    # The painted circle a person sees and the circle the hall MEANS have to be the
    # same circle -- OnConstruction drives the Ring's scale from RingRadiusUu, and a
    # ring that did not follow would make the level lie about where the edge is.
    for a in saved_marks:
        ring = a.get_editor_property("ring")
        scale = ring.get_editor_property("relative_scale3d")
        want = RING_RADIUS_UU / 50.0
        if abs(scale.x - want) > 0.02 or abs(scale.y - want) > 0.02:
            fail(f"{a.get_actor_label()}'s painted ring is scaled "
                 f"({scale.x:.2f},{scale.y:.2f}) where {want:.2f} draws the disclosed "
                 f"{RING_RADIUS_UU:.0f} uu; the paint and the predicate disagree")

    saved_list = [str(n) for n
                  in saved_boards[0].get_editor_property("listed_mark_names")]
    if saved_list != list(DECOY_LIST):
        fail(f"the board saved carrying {saved_list}, not the committed "
             f"{list(DECOY_LIST)}")

    # NOTHING BUT THE FLOOR MAY ANSWER A QUERY. The prompt says the hall is flat and
    # nothing blocks the walk; a stripe or a mast that quietly collides would deflect
    # the drive into a ring nobody aimed at and wipe the round.
    for actor in eas.get_all_level_actors():
        if actor.get_actor_label() == "Floor":
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            if comp.get_collision_enabled() in (
                    unreal.CollisionEnabled.QUERY_ONLY,
                    unreal.CollisionEnabled.QUERY_AND_PHYSICS):
                fail(f"{actor.get_actor_label()} still answers queries; only the "
                     f"floor may, and a prop that deflects the walk starts the round "
                     f"over on a mark nobody stepped on deliberately")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"the level has {len(lit)} light actor(s); a --capture still would be "
             f"black and the graded numbers are meant to be readable by a person")

    log(f"read back: marks {read_back}, board list {saved_list}, "
        f"PlayerStart at ({PLAYER_START[0]:.0f},{PLAYER_START[1]:.0f}), board at "
        f"({BOARD_XY[0]:.0f},{BOARD_XY[1]:.0f}) yawed {BOARD_YAW:.0f}, marks yawed "
        f"{MARK_YAW:.0f} so every readout faces south")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()
