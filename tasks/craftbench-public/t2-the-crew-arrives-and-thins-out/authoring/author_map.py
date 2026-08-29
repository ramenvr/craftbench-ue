"""Authors L_CrewDeck for t2-the-crew-arrives-and-thins-out.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A MUSTER DECK WITH TWO IDENTICAL STATIONS, only one of which the drive ever steps on.
Each station is one board (its chalk and its row of six lamps), six numbered standing
spots painted on the deck in front of it, and two floor plates on its own lane.

WHAT MAKES THIS SCRIPT DIFFERENT FROM "PLACE SOME ACTORS": the fixture
(ACrewMusterFunctionalTest) refuses to START unless eight staging preconditions hold, and
a refusal is a HARNESS-PRECONDITION exit -- a whole wasted build-and-run cycle that says
nothing about any submission. So every one of those eight is computed HERE from the same
numbers, printed with its measured margin, and re-read off the PLACED actors before the
level is allowed to save. The level and the fixture cannot drift apart silently.

THE BAKED CHALK IS NOT DECORATION AND MUST NOT BE "TIDIED" TO MATCH THE SCHEDULE. The
fixture re-stamps all eight chalked values before the character has walked anywhere, and
its ValidateSchedule REFUSES to start if what this script bakes matches the first watch
or shares a roster code with either staged roster. What the level holds is deliberately
WRONG, because that is what makes a submission which read the map offline -- or cached
the chalk in BeginPlay, which fires before PrepareTest -- wrong from the FIRST call
rather than from the second.

Every prop except the floor and the four plate pads is NON-COLLIDING on every channel,
profile as well as enum. The deck promises nothing can get between the character and a
plate or shove a hand off its spot, and the fixture pins every living hand to within
2 cm of where it arrived -- a stripe that quietly blocked would fail a correct answer.

This level names NO game mode: it inherits the project default, so the play lane
(BP_ThirdPersonGameMode -> BP_ThirdPersonPlayerController, which carries IMC_Default)
comes for free. The fixture makes an unplayable level a HARNESS-PRECONDITION by property
name, so a regression here is attributed to the substrate and never to a model.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw), which is not the order anybody reads it in.
"""
import math

import unreal

TASK = "t2-the-crew-arrives-and-thins-out"
MAP_PKG = f"/Game/Maps/{TASK}/L_CrewDeck"

# ------------------------------------------------------------------ the deck's shape
# Two parallel lanes 4,500 uu apart in Y. The drive only ever walks the working lane;
# the twin station is a full identical copy of it that nobody steps on, and it is the
# in-scene negative control gauged at every checkpoint.
#
# THE ONE NUMBER EVERY THRESHOLD HANGS ON is the 4,500 uu between the lanes: it is what
# puts every twin plate 4,500 uu from the working lane against the fixture's 1,500 uu
# floor. An earlier draft of the spec put the two boards face to face 4,800 apart, which
# reads the same in prose and puts the twin's call plate ~1,000 uu from the working one.
WORKING_BOARD = "PortBoard"      # the board the drive walks to
TWIN_BOARD = "StarboardBoard"    # the twin, never stepped on

WORKING_LANE_Y = 0.0
TWIN_LANE_Y = 4500.0

BOARD_X = -3000.0                # the board stands at the far end of its lane
BERTH_X = -2200.0                # the standing-spot row, 800 uu in front of the board
CALL_PLATE_X = -800.0
DOWN_PLATE_X = 1200.0
PLAYER_START_X = 200.0           # exactly midway between the two working plates

BERTHS_PER_BOARD = 6
BERTH_SPACING = 500.0
# Spot 1 sits at lane_y - 1250, so the six run -1250 .. +1250 about the lane -- which is
# exactly where the board's own lamp row sits (LampGlow0..LampGlow5 at local
# Y = -1250 .. +1250). The lamp row and the painted numbers therefore read the same way
# for a person watching, and the fixture's name-order lamp lookup lands on the right one.
BERTH_FIRST_OFFSET = -1250.0
BOARD_LAMP_SPACING = 500.0       # mirrors AMusterBoardActor's kLampSpacingUu
BOARD_LAMP_FIRST_OFFSET = -1250.0

# 13,000 x 13,000, centred so both lanes and the whole walk sit on it with margin.
DECK_MIN = (-7500.0, -4250.0)
DECK_MAX = (5500.0, 8750.0)
STRIPE_EVERY = 400.0             # so speed and distance are readable by eye

PLAYER_START_Z = 120.0           # dropped in; it falls to the deck in phase 0
LANDMARK_X = -6600.0
BACKDROP_X = -3400.0

# ------------------------------------------------------------------------- the chalk
# WHAT THE COMMITTED .umap HOLDS. Deliberately different from the fixture's schedule on
# all eight values, and sharing no roster code with either staged roster. See the module
# docstring: this is load-bearing wrongness, not a stale draft.
BAKED = {
    WORKING_BOARD: {
        "hands_to_call": 4,
        "seconds_between_arrivals": 1.9,
        "roster_codes": [5, 7, 9, 15],
        "slate_positions": [1, 2],
    },
    TWIN_BOARD: {
        "hands_to_call": 2,
        "seconds_between_arrivals": 2.9,
        "roster_codes": [2, 3, 4],
        "slate_positions": [1],
    },
}

# MIRRORS of ACrewMusterFunctionalTest::BuildSchedule, kept here ONLY so the checks below
# can prove the baked values differ from it. The fixture owns the schedule; if these two
# ever disagree the FIXTURE is right and this copy is stale -- which is why nothing here
# is placed from them, only compared against them.
STAGED_WORKING_CALL_W1 = 6
STAGED_WORKING_GAP_W1 = 2.0
STAGED_WORKING_ROSTER = [41, 47, 53, 59, 61, 67, 71, 73, 79]
STAGED_TWIN_ROSTER = [11, 13, 17, 19, 23, 29, 31]

# ------------------------------------------------- the fixture's staging preconditions
# Every one of these is a literal from ACrewMusterFunctionalTest. Breaking one costs a
# HARNESS-PRECONDITION exit at run time, so they are asserted here instead.
MIN_WORKING_PLATE_SPAN = 1200.0   # ValidateGeometry: the drive must be able to stand
                                  # between the two plates without being on one
MAX_START_TO_MIDPOINT = 400.0     # ValidateGeometry: PlayerStart is on the lane
MIN_TWIN_PLATE_TO_LANE = 1500.0   # ValidateGeometry: the drive can never step on the
                                  # board it is meant to leave alone
MIN_BERTH_TO_LANE = 600.0         # ValidateGeometry: a hand can never be walked into
MIN_STAGED_GAP_S = 2.0            # ValidateSchedule's floor -- applies to the STAGED
                                  # gaps only, which is why a baked 1.9 is legal here
PLATE_REGION_HALF_XY = 200.0      # ACrewPlateActor's PlateVolume box extent
BOARD_FACE_HALF_Y = 1500.0        # its Face is 3,000 uu wide in local Y
# The fixture decides "the hero is on this plate" by inflating the plate region by the
# MEASURED capsule radius, so a spot is "on the plate" from further out than the region.
# 60 uu is comfortably past the stock ThirdPerson capsule's 42, and being generous here
# only ever pushes the PlayerStart further from a plate.
CAPSULE_RADIUS_ALLOWANCE = 60.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"

SCAFFOLD_CLASSES = ("MusterBoardActor", "CrewBerthActor", "CrewPlateActor",
                    "CrewHandActor")
FIXTURE_CLASS = "CrewMusterFunctionalTest"


def log(msg):
    unreal.log(f"CREWDECK- {msg}")


def fail(msg):
    unreal.log_error(f"CREWDECK-ERROR {msg}")
    raise SystemExit(1)


# ------------------------------------------------------------------------ the geometry
# The same arithmetic the fixture does, in Python, so a layout that would refuse to
# start is caught here instead of 3 minutes into a graded run.

def lane_of(board_tag):
    return WORKING_LANE_Y if board_tag == WORKING_BOARD else TWIN_LANE_Y


def berth_xy(board_tag, spot_number):
    return (BERTH_X,
            lane_of(board_tag) + BERTH_FIRST_OFFSET
            + BERTH_SPACING * (spot_number - 1))


def board_lamp_y(board_tag, spot_number):
    """Where AMusterBoardActor puts LampGlow<spot-1> in world Y, at yaw 0."""
    return (lane_of(board_tag) + BOARD_LAMP_FIRST_OFFSET
            + BOARD_LAMP_SPACING * (spot_number - 1))


def plate_xy(board_tag, is_call):
    return (CALL_PLATE_X if is_call else DOWN_PLATE_X, lane_of(board_tag))


def dist2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def check_layout():
    """The eight preconditions, measured. Prints every margin so a future edit that
    eats one is visible in the log rather than at run time."""
    call_at = plate_xy(WORKING_BOARD, True)
    down_at = plate_xy(WORKING_BOARD, False)
    mid = ((call_at[0] + down_at[0]) * 0.5, (call_at[1] + down_at[1]) * 0.5)
    start = (PLAYER_START_X, WORKING_LANE_Y)
    lane_points = (mid, call_at, down_at)

    # 1. counts
    if BERTHS_PER_BOARD != 6:
        fail(f"the fixture is staged for exactly 6 standing spots per board, not "
             f"{BERTHS_PER_BOARD}")

    # 2. the working board's two plates
    span = dist2d(call_at, down_at)
    if span < MIN_WORKING_PLATE_SPAN:
        fail(f"the working board's plates are {span:.0f} uu apart against a "
             f"{MIN_WORKING_PLATE_SPAN:.0f} uu floor")

    # 3. PlayerStart on the lane. It has to be ON the midpoint and not merely near it,
    #    because that midpoint is where the fixture parks the character between plates
    #    and the whole drive is one straight line through it.
    start_off = dist2d(start, mid)
    if start_off > MAX_START_TO_MIDPOINT:
        fail(f"PlayerStart is {start_off:.0f} uu from the midpoint of the working "
             f"board's plates, against a {MAX_START_TO_MIDPOINT:.0f} uu ceiling")

    # 3b. AND it must not be standing ON either plate at spawn -- the fixture seeds each
    #     plate's observed state from where the character starts, so a PlayerStart inside
    #     a plate region would make the first step onto it not a step at all and the
    #     first call would never fire. Checked against the region INFLATED by a generous
    #     capsule radius, because that is what the fixture's own overlap arithmetic uses:
    #     a check against the bare region would pass a PlayerStart the fixture reads as
    #     already standing on the plate.
    contact_half = PLATE_REGION_HALF_XY + CAPSULE_RADIUS_ALLOWANCE
    for is_call in (True, False):
        at = plate_xy(WORKING_BOARD, is_call)
        if (abs(start[0] - at[0]) <= contact_half
                and abs(start[1] - at[1]) <= contact_half):
            fail(f"PlayerStart is within {contact_half:.0f} uu of the working board's "
                 f"{'call' if is_call else 'stand-down'} plate; the fixture would read "
                 f"the character as already standing on it")

    # 4. every twin plate clear of all three working-lane points
    twin_min = min(dist2d(plate_xy(TWIN_BOARD, c), p)
                   for c in (True, False) for p in lane_points)
    if twin_min < MIN_TWIN_PLATE_TO_LANE:
        fail(f"a twin-board plate stands {twin_min:.0f} uu from the lane the drive "
             f"walks, against a {MIN_TWIN_PLATE_TO_LANE:.0f} uu floor")

    # 5. every standing spot clear of all three working-lane points
    berth_min = None
    berth_worst = None
    for tag in (WORKING_BOARD, TWIN_BOARD):
        for spot in range(1, BERTHS_PER_BOARD + 1):
            d = min(dist2d(berth_xy(tag, spot), p) for p in lane_points)
            if berth_min is None or d < berth_min:
                berth_min, berth_worst = d, (tag, spot)
    if berth_min < MIN_BERTH_TO_LANE:
        fail(f"standing spot {berth_worst[1]} of '{berth_worst[0]}' is "
             f"{berth_min:.0f} uu from the lane the drive walks, against a "
             f"{MIN_BERTH_TO_LANE:.0f} uu floor")

    # 6. the lamp row and the painted numbers must read the same way, or a person
    #    watching sees a lamp row that disagrees with the spots it is reporting on.
    #    A tautology on today's constants, and kept for exactly that reason: it is the
    #    only thing that catches an edit to BERTH_SPACING / BERTH_FIRST_OFFSET that does
    #    not also move AMusterBoardActor's kLampSpacingUu, which lives in C++.
    for tag in (WORKING_BOARD, TWIN_BOARD):
        for spot in range(1, BERTHS_PER_BOARD + 1):
            want = berth_xy(tag, spot)[1]
            got = board_lamp_y(tag, spot)
            if abs(want - got) > 1.0:
                fail(f"on '{tag}', standing spot {spot} is painted at y={want:.0f} "
                     f"while its lamp sits at y={got:.0f}; the row would read "
                     f"backwards to a reviewer")

    # 7. every actor on the deck sits inside the floor
    for tag in (WORKING_BOARD, TWIN_BOARD):
        pts = [(BOARD_X, lane_of(tag) - BOARD_FACE_HALF_Y),
               (BOARD_X, lane_of(tag) + BOARD_FACE_HALF_Y)]
        pts += [berth_xy(tag, s) for s in range(1, BERTHS_PER_BOARD + 1)]
        pts += [plate_xy(tag, True), plate_xy(tag, False)]
        for x, y in pts:
            if not (DECK_MIN[0] + 100.0 <= x <= DECK_MAX[0] - 100.0
                    and DECK_MIN[1] + 100.0 <= y <= DECK_MAX[1] - 100.0):
                fail(f"'{tag}' puts something at ({x:.0f},{y:.0f}), off the "
                     f"{DECK_MAX[0] - DECK_MIN[0]:.0f} x "
                     f"{DECK_MAX[1] - DECK_MIN[1]:.0f} floor")

    # 8. the baked chalk. This is the check that keeps a well-meant "fix" from turning
    #    the whole read-it-live half of the task into a decoy.
    staged_codes = set(STAGED_WORKING_ROSTER) | set(STAGED_TWIN_ROSTER)
    for tag, chalk in BAKED.items():
        overlap = sorted(set(chalk["roster_codes"]) & staged_codes)
        if overlap:
            fail(f"board '{tag}' bakes roster code(s) {overlap}, which the fixture also "
                 f"stages; a badge would stop naming which source produced it and the "
                 f"fixture would refuse to start")
        if chalk["hands_to_call"] < 1:
            fail(f"board '{tag}' bakes a call for {chalk['hands_to_call']}")
    if set(BAKED[WORKING_BOARD]["roster_codes"]) & set(
            BAKED[TWIN_BOARD]["roster_codes"]):
        fail("the two boards bake overlapping rosters")
    work = BAKED[WORKING_BOARD]
    if (work["hands_to_call"] == STAGED_WORKING_CALL_W1
            and abs(work["seconds_between_arrivals"] - STAGED_WORKING_GAP_W1) < 0.01):
        fail("the working board bakes exactly what the first watch stages, so a value "
             "cached in BeginPlay would be RIGHT and nothing would test reading it "
             "live; the fixture refuses to start on this")
    if work["hands_to_call"] > BERTHS_PER_BOARD:
        fail(f"the working board bakes a call for {work['hands_to_call']} against "
             f"{BERTHS_PER_BOARD} standing spots; a human pressing Play before any "
             f"fixture runs would see a board asking for more than it has room for")
    if STAGED_WORKING_GAP_W1 < MIN_STAGED_GAP_S:
        fail(f"this script's mirror of the staged watch-1 gap ({STAGED_WORKING_GAP_W1}) "
             f"is below the fixture's {MIN_STAGED_GAP_S} s floor -- the mirror is stale")

    log(f"layout OK: working plates {span:.0f} uu apart (floor "
        f"{MIN_WORKING_PLATE_SPAN:.0f}); PlayerStart {start_off:.0f} uu off the midpoint "
        f"(ceiling {MAX_START_TO_MIDPOINT:.0f}); nearest twin plate {twin_min:.0f} uu "
        f"from the lane (floor {MIN_TWIN_PLATE_TO_LANE:.0f}); nearest standing spot "
        f"{berth_min:.0f} uu from the lane (floor {MIN_BERTH_TO_LANE:.0f})")
    log(f"baked chalk (deliberately NOT the staged schedule): "
        f"{WORKING_BOARD} call {work['hands_to_call']} every "
        f"{work['seconds_between_arrivals']}s roster {work['roster_codes']} slate "
        f"{work['slate_positions']}; {TWIN_BOARD} call "
        f"{BAKED[TWIN_BOARD]['hands_to_call']} every "
        f"{BAKED[TWIN_BOARD]['seconds_between_arrivals']}s roster "
        f"{BAKED[TWIN_BOARD]['roster_codes']} slate "
        f"{BAKED[TWIN_BOARD]['slate_positions']}")
    return {"call": call_at, "down": down_at, "mid": mid, "start": start}


# -------------------------------------------------------------------------- authoring

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
    for cls_name in SCAFFOLD_CLASSES + (FIXTURE_CLASS,):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built? "
                 f"(the fixture lives in CraftBenchTests, the four scaffold actors in "
                 f"ThirdPerson; both have to be compiled before this runs)")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def set_prop(actor, name, value, alt=None):
    """set_editor_property by name, trying the alternate spelling a bool UPROPERTY
    gets. `bIsCallPlate` reaches Python as `is_call_plate`, and a wrong guess raises
    rather than silently doing nothing -- but a SILENT miss is exactly what would leave
    a plate unlabelled and cost a HARNESS-PRECONDITION, so both spellings are tried and
    a total miss is fatal."""
    names = [name] + ([alt] if alt else [])
    last = None
    for candidate in names:
        try:
            actor.set_editor_property(candidate, value)
            return candidate
        except Exception as exc:            # noqa: BLE001 - any binding error
            last = exc
    fail(f"{actor.get_actor_label()}: none of {names} could be set to {value!r} "
         f"({last})")


def get_prop(actor, name, alt=None):
    for candidate in [name] + ([alt] if alt else []):
        try:
            return actor.get_editor_property(candidate)
        except Exception:                   # noqa: BLE001
            continue
    fail(f"{actor.get_actor_label()}: neither {name} nor {alt} can be read back")


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
        # THE PROFILE AS WELL AS THE ENUM. On an earlier task in this set
        # set_collision_enabled alone did not survive into the saved level, and a
        # stripe that quietly blocks is indistinguishable from a submission bug: it
        # could shove a hand off its spot and fail NobodyShufflesAlongTheDeck on a
        # correct answer.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls, x, y, z, yaw, label):
    """Spawn one of the four scaffold actors at an EXACT spot.

    The re-set of the location is not belt-and-braces. Three of the four scaffold
    actors carry collision on a component (the plate's pad BLOCKS, so that the
    character can step onto it), and a spawn whose collision handling nudges the actor
    would move a piece of furniture the fixture then pins to within 2 cm of where the
    deck put it. Setting the transform explicitly, with teleport, makes the placement
    exact; verify_placed() then reads it back and refuses to save on any drift."""
    actor = env["eas"].spawn_actor_from_class(
        cls, unreal.Vector(x, y, z), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    actor.set_actor_location(unreal.Vector(x, y, z), False, True)
    return actor


def paint_stripe(env, a, b, label, material, width=14.0, z=2.0, thick=4.0):
    """A thin painted line on the deck from a to b. Never collides.

    `z` is the slab's CENTRE and `thick` its full height, so the slab occupies
    [z - thick/2, z + thick/2]. Both are spelled out because a painted line is only
    decoration until it swallows something: ACrewBerthActor draws its spot's number on
    a TextRender plane at z = 4 over paint that occupies [0, 2], so a line laid across
    the standing-spot row has to sit ABOVE 2 and clear of 4, and "thin" alone does not
    say that."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1.0:
        return None
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    return block(env, CUBE,
                 unreal.Vector((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, z),
                 unreal.Vector(length / 100.0, width / 100.0, thick / 100.0), label,
                 material, yaw=yaw)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    spots = check_layout()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = DECK_MAX[0] - DECK_MIN[0]
    span_y = DECK_MAX[1] - DECK_MIN[1]
    mid_x = (DECK_MAX[0] + DECK_MIN[0]) / 2.0
    mid_y = (DECK_MAX[1] + DECK_MIN[1]) / 2.0

    floor = block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
                  collide=True)
    # THE DECK'S TOP FACE, MEASURED off the placed block rather than worked out in a
    # comment. Every actor below is placed at Z = 0 and every one of them assumes the
    # deck is there; "a 100 uu cube centred at -50 has its top at 0" is arithmetic, not
    # evidence, and a scale or a moved centre would break it silently.
    f_origin, f_extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = f_origin.z + f_extent.z
    if abs(floor_top_z) > 0.5:
        fail(f"the deck's top face measured at z={floor_top_z:.2f}; every actor here is "
             f"placed at z=0 and the fixture pins each of them to within 2 cm of where "
             f"it was put, so the deck has to be at z=0")
    log(f"deck {span_x:.0f}x{span_y:.0f}, top face measured at z={floor_top_z:.2f}")

    n = 0
    x = DECK_MIN[0] + STRIPE_EVERY
    while x < DECK_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"{n} stripes every {STRIPE_EVERY:.0f} cm, so a walk's pace reads by eye")

    # THE TWO LANES, painted so a reviewer can see there are two of them and which one
    # the drive walks. The bright one is the working lane; the dark one is the twin's.
    # Neither says anything about the answer -- it is which way somebody walks.
    for tag, look in ((WORKING_BOARD, M_GLOW), (TWIN_BOARD, M_HAZARD)):
        y = lane_of(tag)
        paint_stripe(env, (DOWN_PLATE_X + 700.0, y), (CALL_PLATE_X - 700.0, y),
                     f"Lane_{tag}", look, width=26.0)
        # And the muster line the standing spots are painted along, so the six spots
        # visibly belong to the board standing behind them.
        # THE SLAB HAS TO FIT BETWEEN TWO THINGS THE SCAFFOLD OWNS: each standing
        # spot's own paint fills [0, 2] and its painted NUMBER is a flat TextRender
        # plane at z = 4. A 4 cm slab centred at z = 3 spans [1, 5] and swallows that
        # plane -- the muster line would be drawn straight through every number. A 1 cm
        # slab centred at 2.6 spans [2.1, 3.1]: clear of the paint below and of the
        # numbers above, with no z-fighting against either.
        paint_stripe(env, (BERTH_X, y + BERTH_FIRST_OFFSET - 250.0),
                     (BERTH_X, y - BERTH_FIRST_OFFSET + 250.0),
                     f"MusterLine_{tag}", M_DARK, width=20.0, z=2.6, thick=1.0)

    # ---- THE BOARDS. Yaw 0, so local +X (where the lamps, the bulbs and the chalk
    # ---- face) points down the lane toward the deck and the camera.
    for tag in (WORKING_BOARD, TWIN_BOARD):
        board = place(env, env["MusterBoardActor"], BOARD_X, lane_of(tag), 0.0, 0.0,
                      f"MusterBoard_{tag}")
        set_prop(board, "board_tag", tag)
        for key, value in BAKED[tag].items():
            set_prop(board, key, value)
    log(f"two boards placed at x={BOARD_X:.0f}: '{WORKING_BOARD}' on y="
        f"{WORKING_LANE_Y:.0f} and '{TWIN_BOARD}' on y={TWIN_LANE_Y:.0f}")

    # ---- THE STANDING SPOTS. Numbered 1..6 CONTIGUOUS per board: the whole coupling
    # ---- this task is built on -- that on the first watch "the k-th to turn up" and
    # ---- "standing spot k" are the same hand -- is only exact when they run 1..6, and
    # ---- the fixture refuses to start otherwise.
    for tag in (WORKING_BOARD, TWIN_BOARD):
        for spot in range(1, BERTHS_PER_BOARD + 1):
            bx, by = berth_xy(tag, spot)
            berth = place(env, env["CrewBerthActor"], bx, by, 0.0, 0.0,
                          f"CrewBerth_{tag}_{spot}")
            set_prop(berth, "board_tag", tag)
            set_prop(berth, "spot_number", spot)
    log(f"{2 * BERTHS_PER_BOARD} standing spots placed, 1..{BERTHS_PER_BOARD} per "
        f"board, {BERTH_SPACING:.0f} cm apart")

    # ---- THE FLOOR PLATES. The region is the plate's ROOT, so the level's transform
    # ---- IS the region's transform; placed at z=0 the pad stands 10 cm proud of the
    # ---- deck (far inside MaxStepHeight) and the region reaches a standing body.
    for tag in (WORKING_BOARD, TWIN_BOARD):
        for is_call in (True, False):
            px, py = plate_xy(tag, is_call)
            plate = place(env, env["CrewPlateActor"], px, py, 0.0, 0.0,
                          f"CrewPlate_{tag}_{'Call' if is_call else 'StandDown'}")
            set_prop(plate, "board_tag", tag)
            set_prop(plate, "is_call_plate", is_call, alt="b_is_call_plate")
    log("four floor plates placed: one call and one stand-down on each board's lane")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(spots["start"][0], spots["start"][1], PLAYER_START_Z),
        # Yaw 180 faces -X: down the lane, toward the call plate and the board.
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A low back wall behind each board and two differently sized landmarks at opposite
    # ends of the deck, so a moving camera is distinguishable from a still one.
    # NON-COLLIDING like everything that is not the floor or a plate pad.
    for tag in (WORKING_BOARD, TWIN_BOARD):
        block(env, CUBE, unreal.Vector(BACKDROP_X, lane_of(tag), 140.0),
              unreal.Vector(0.5, 40.0, 2.8), f"Backdrop_{tag}", M_DARK)
    block(env, CYL, unreal.Vector(LANDMARK_X, DECK_MIN[1] + 1050.0, 200.0),
          unreal.Vector(1.2, 1.2, 4.0), "Landmark_Short", M_HAZARD)
    block(env, CYL, unreal.Vector(LANDMARK_X, DECK_MAX[1] - 1050.0, 400.0),
          unreal.Vector(2.4, 2.4, 8.0), "Landmark_Tall", M_GLOW)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1600.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-25.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1600.0),
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
        env[FIXTURE_CLASS],
        unreal.Vector(DECK_MAX[0] - 900.0, DECK_MAX[1] - 950.0, 200.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label(FIXTURE_CLASS)

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default or both halves of Enhanced Input go with it and the deck "
             "grades byte-identically while being uncontrollable "
             "(the 2026-08-17 unplayable-play-lane finding)")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode, which "
        "supplies BP_ThirdPersonPlayerController and IMC_Default)")

    verify_placed(env, floor_top_z)

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


# ------------------------------------------------------- read the level back
# Everything above placed things; everything below reads them off the level that is
# about to be SAVED. The two are deliberately separate: a property that silently failed
# to write, a tag a constructor stopped adding, or a coordinate that drifted are all
# invisible on the write side and all cost a HARNESS-PRECONDITION exit at run time.

def verify_placed(env, floor_top_z):
    eas = env["eas"]
    all_actors = eas.get_all_level_actors()

    def tagged(tag):
        return [a for a in all_actors if a.actor_has_tag(tag)]

    boards = tagged("MusterBoard")
    berths = tagged("CrewBerth")
    plates = tagged("CrewPlate")
    hands = tagged("CrewHand")
    if len(boards) != 2 or len(berths) != 2 * BERTHS_PER_BOARD or len(plates) != 4:
        fail(f"the fixture expects exactly 2 MusterBoard / {2 * BERTHS_PER_BOARD} "
             f"CrewBerth / 4 CrewPlate actors and the level carries "
             f"{len(boards)} / {len(berths)} / {len(plates)}. A missing tag reads the "
             f"same as a missing actor here -- the four scaffold constructors add their "
             f"own tags, so check those before adding one by hand")
    if hands:
        fail(f"{len(hands)} actor(s) tagged CrewHand are placed in the level. Every "
             f"standing spot must start EMPTY: a placed hand makes the empty submission "
             f"look like it did something and is named by NobodyArrivesUncalled on the "
             f"first judged frame")

    # ---- the boards: names, chalk, and the disjointness the badge story rests on ----
    by_tag = {}
    for b in boards:
        tag = str(get_prop(b, "board_tag"))
        if tag in by_tag:
            fail(f"two boards are both named '{tag}'")
        by_tag[tag] = b
    if set(by_tag) != {WORKING_BOARD, TWIN_BOARD}:
        fail(f"the boards read back as {sorted(by_tag)}; the fixture is staged for "
             f"'{WORKING_BOARD}' (the working board) and '{TWIN_BOARD}' (the twin)")
    for tag, want in BAKED.items():
        b = by_tag[tag]
        got_call = int(get_prop(b, "hands_to_call"))
        got_gap = float(get_prop(b, "seconds_between_arrivals"))
        got_roster = [int(v) for v in get_prop(b, "roster_codes")]
        got_slate = [int(v) for v in get_prop(b, "slate_positions")]
        if (got_call != want["hands_to_call"]
                or abs(got_gap - want["seconds_between_arrivals"]) > 0.001
                or got_roster != want["roster_codes"]
                or got_slate != want["slate_positions"]):
            fail(f"board '{tag}' reads back call {got_call} / gap {got_gap} / roster "
                 f"{got_roster} / slate {got_slate}, not {want}. All four are "
                 f"EditAnywhere so set_editor_property can write them; a mismatch means "
                 f"a write silently missed")
        if abs(b.get_actor_location().z) > 0.5:
            fail(f"board '{tag}' sits at z={b.get_actor_location().z:.1f}, not 0")
        if abs(b.get_actor_rotation().yaw) > 0.5:
            fail(f"board '{tag}' is yawed {b.get_actor_rotation().yaw:.1f} deg; at any "
                 f"yaw but 0 its lamp row no longer runs along world +Y and stops "
                 f"reading the same way as the painted spot numbers")

    # ---- the standing spots: 1..6 contiguous per board, at the coordinates the
    # ---- geometry check cleared, with the lamp row agreeing ----
    per_board = {WORKING_BOARD: {}, TWIN_BOARD: {}}
    for a in berths:
        tag = str(get_prop(a, "board_tag"))
        spot = int(get_prop(a, "spot_number"))
        if tag not in per_board:
            fail(f"a standing spot belongs to board '{tag}', which is not on this deck")
        if spot in per_board[tag]:
            fail(f"board '{tag}' has two standing spots numbered {spot}")
        per_board[tag][spot] = a
    for tag, spots in per_board.items():
        if sorted(spots) != list(range(1, BERTHS_PER_BOARD + 1)):
            fail(f"board '{tag}' numbers its standing spots {sorted(spots)}; they must "
                 f"run 1..{BERTHS_PER_BOARD} contiguous or arrival place k and spot k "
                 f"stop coinciding on the first watch and the task's whole coupling "
                 f"dissolves")
        for spot, a in spots.items():
            want = berth_xy(tag, spot)
            at = a.get_actor_location()
            if abs(at.x - want[0]) > 1.0 or abs(at.y - want[1]) > 1.0 \
                    or abs(at.z) > 0.5:
                fail(f"standing spot {spot} of '{tag}' is at "
                     f"({at.x:.0f},{at.y:.0f},{at.z:.0f}), not "
                     f"({want[0]:.0f},{want[1]:.0f},0)")

    # ---- the plates: one call and one stand-down per board, at the cleared spots ----
    kinds = {WORKING_BOARD: [], TWIN_BOARD: []}
    for a in plates:
        tag = str(get_prop(a, "board_tag"))
        is_call = bool(get_prop(a, "is_call_plate", alt="b_is_call_plate"))
        if tag not in kinds:
            fail(f"a floor plate belongs to board '{tag}', which is not on this deck")
        kinds[tag].append(is_call)
        want = plate_xy(tag, is_call)
        at = a.get_actor_location()
        if abs(at.x - want[0]) > 1.0 or abs(at.y - want[1]) > 1.0 or abs(at.z) > 0.5:
            fail(f"the {'call' if is_call else 'stand-down'} plate of '{tag}' is at "
                 f"({at.x:.0f},{at.y:.0f},{at.z:.0f}), not "
                 f"({want[0]:.0f},{want[1]:.0f},0)")
        boxes = a.get_components_by_class(unreal.BoxComponent)
        if not boxes:
            fail(f"a floor plate of '{tag}' has no region, so nothing can observe the "
                 f"character stepping on it")
    for tag, got in kinds.items():
        if sorted(got) != [False, True]:
            fail(f"board '{tag}' has call-plate flags {got}; each board needs exactly "
                 f"one call plate and one stand-down plate")

    # ---- the play lane, and the drive's own lane, measured on the placed actors ----
    starts = [a for a in all_actors
              if a.get_class().get_name() == "PlayerStart"]
    if len(starts) != 1:
        fail(f"{len(starts)} PlayerStart(s); the fixture takes player 0's character and "
             f"requires it to spawn on the working board's lane")
    call_at = [a.get_actor_location() for a in plates
               if str(get_prop(a, "board_tag")) == WORKING_BOARD
               and bool(get_prop(a, "is_call_plate", alt="b_is_call_plate"))][0]
    down_at = [a.get_actor_location() for a in plates
               if str(get_prop(a, "board_tag")) == WORKING_BOARD
               and not bool(get_prop(a, "is_call_plate", alt="b_is_call_plate"))][0]
    mid = ((call_at.x + down_at.x) * 0.5, (call_at.y + down_at.y) * 0.5)
    s_at = starts[0].get_actor_location()
    measured = {
        "plate span": (dist2d((call_at.x, call_at.y), (down_at.x, down_at.y)),
                       MIN_WORKING_PLATE_SPAN, "floor"),
        "start off midpoint": (dist2d((s_at.x, s_at.y), mid),
                               MAX_START_TO_MIDPOINT, "ceiling"),
    }
    lane_points = (mid, (call_at.x, call_at.y), (down_at.x, down_at.y))
    twin_min = min(dist2d((a.get_actor_location().x, a.get_actor_location().y), p)
                   for a in plates
                   if str(get_prop(a, "board_tag")) == TWIN_BOARD
                   for p in lane_points)
    berth_min = min(dist2d((a.get_actor_location().x, a.get_actor_location().y), p)
                    for a in berths for p in lane_points)
    measured["nearest twin plate"] = (twin_min, MIN_TWIN_PLATE_TO_LANE, "floor")
    measured["nearest standing spot"] = (berth_min, MIN_BERTH_TO_LANE, "floor")
    for label, (value, threshold, kind) in measured.items():
        bad = value < threshold if kind == "floor" else value > threshold
        if bad:
            fail(f"{label} measured {value:.0f} uu against a {threshold:.0f} uu "
                 f"{kind}; the fixture would refuse to start with a "
                 f"HARNESS-PRECONDITION and the run would say nothing about any "
                 f"submission")
    log("measured on the placed actors: "
        + "; ".join(f"{k} {v:.0f} uu ({c} {t:.0f})"
                    for k, (v, t, c) in measured.items()))

    # ---- nothing but the deck and the plate pads may BLOCK anything ----
    # Scoped to BLOCKING, not to "answers a query", and the difference is deliberate.
    # The deck's promise is that nothing can get between the character and a plate or
    # shove a hand off its spot -- and the fixture pins every living hand to within 2 cm
    # of where it arrived, so a prop that blocks would fail a CORRECT submission. A
    # query-only component cannot shove anything (that is exactly what the plates' own
    # overlap regions are), and UTextRenderComponent -- which the chalk, the painted spot
    # numbers and every badge are -- is a UPrimitiveComponent whose engine default this
    # script must not be made to depend on. Widening this to query-only would turn a
    # harmless engine default into a refusal to author the level at all.
    blocking = (unreal.CollisionEnabled.QUERY_AND_PHYSICS,
                unreal.CollisionEnabled.PHYSICS_ONLY)
    allowed = {"Floor"} | {a.get_actor_label() for a in plates}
    queried = []
    for actor in all_actors:
        label = actor.get_actor_label()
        if label in allowed:
            continue
        # PlayerStart ships a capsule whose collision is the engine's business, not
        # ours, and it stands well clear of every standing spot.
        if actor.get_class().get_name() == "PlayerStart":
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            enabled = comp.get_collision_enabled()
            if enabled in blocking:
                fail(f"{label}'s {comp.get_name()} BLOCKS ({enabled}). Nothing on this "
                     f"deck but the floor and the four plate pads may block: the "
                     f"fixture pins every living hand to within 2 cm of where it "
                     f"arrived, so a prop that can be walked into would fail a CORRECT "
                     f"submission")
            elif enabled != unreal.CollisionEnabled.NO_COLLISION:
                queried.append(f"{label}/{comp.get_name()}")
    if queried:
        log(f"note: {len(queried)} non-blocking component(s) still answer queries "
            f"(harmless here -- an overlap cannot shove a hand): "
            f"{', '.join(queried[:8])}{' ...' if len(queried) > 8 else ''}")

    lit = [a for a in all_actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"the level carries {len(lit)} light actor(s); a --capture still would be "
             f"black and the reviewer would see nothing")

    fixtures = [a for a in all_actors
                if a.get_class().get_name() == FIXTURE_CLASS]
    if len(fixtures) != 1:
        fail(f"{len(fixtures)} {FIXTURE_CLASS} actor(s); L2 needs exactly one")
    fx = fixtures[0].get_actor_location()
    if min(dist2d((fx.x, fx.y), p) for p in lane_points) < 1500.0:
        fail(f"the functional test actor stands on the lane the drive walks "
             f"({fx.x:.0f},{fx.y:.0f}); move it off")

    log(f"read back OK: 2 boards ({sorted(by_tag)}), {len(berths)} standing spots "
        f"1..{BERTHS_PER_BOARD} per board, {len(plates)} plates, no hands aboard, "
        f"deck top z={floor_top_z:.2f}, {len(lit)} lights, one {FIXTURE_CLASS}")


main()
