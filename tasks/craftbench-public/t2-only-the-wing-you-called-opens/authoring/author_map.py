"""Authors the FIVE committed levels of t2-only-the-wing-you-called-opens.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript
        -script="<abs path to this file>" -nullrhi -unattended -nopause
        -log -stdout -FullStdOutLogOutput

ONE HOST AND FOUR WINGS. `L_WingHost` is the persistent level: a 6,000 x 6,000 striped
floor, three call marks set into it, the four wing posts, the gate board, a backdrop with
a landmark at each end, the lighting rig, the PlayerStart and the fixture. The four wings
-- `L_WingVault` (HALL), `L_WingLoft` (ROSE), `L_WingKeep` (GOLD) and `L_WingSpur`
(SLATE) -- are STREAMED SECTIONS of that host, `AWingFittingActor`s and nothing else.
The hall starts in the running world; the other three start out of it.

TWO DELIBERATE UN-GUESSABLES, and this script is where both are made true.
  * A SECTION IS NOT NAMED AFTER ITS WING. HALL lives in `L_WingVault`, ROSE in
    `L_WingLoft`, GOLD in `L_WingKeep`, SLATE in `L_WingSpur`, and none of those names
    is printed in the prompt. `UGameplayStatics::GetStreamingLevel` suffix-matches
    case-insensitively, so an `L_Wing<WING>` scheme would let a submission build the
    section name out of the wing name and never read a post at all -- the join the
    whole task turns on would be free. The post is the only place the join exists.
  * THE WINGS ARE DIFFERENT SIZES: 3 / 4 / 6 / 4 fittings (WING_FITTINGS), and no
    number is printed either. The board has to report how many of the called wing's
    fittings are STANDING, so a constant is wrong -- the deals are mirrored, so cp1
    wants ROSE's four on the fast leg and GOLD's six on the slow one -- and so is the
    count taken at the instant of the step, because the wing has not arrived yet.

WHY THE HALL IS A STREAMED SECTION AND NOT PART OF THE PERSISTENT LEVEL. It is the whole
task. The owner's named wrong answer is "clear every section the world knows about, then
bring in the one this mark names"; if the hall's three fittings sat in the persistent
level that loop would never touch them, the wrong answer would pass, and the task would
collapse into "load a level by name" -- a T0. The hall has to be a section exactly like
the other three, and indistinguishable from one to any clear-everything loop.

WHY EVERY WING IS `ULevelStreamingDynamic` AND NEVER `AlwaysLoaded`.
`ULevelStreamingAlwaysLoaded::ShouldBeLoaded()` is `{ return true; }`
(LevelStreamingAlwaysLoaded.h:27), so the world refuses to take such a section out --
`SealedWingUntouched` would become an unfailable dead gate and the whole coupling a
permissive fake. The fixture raises a HARNESS-PRECONDITION on it (`ShouldBeAlwaysLoaded`),
and this script refuses to leave a level standing unless all four read back as
`LevelStreamingDynamic` FROM DISK.

THIS SCRIPT REFUSES RATHER THAN WARNS. Every assumption the fixture's tables make is
re-read from disk after the save and checked here, because each of these faults presents
at run time as a named gate FAIL against a submission that did nothing wrong:

  (a) the persistent level is NOT a World-Partition world (`new_level(..., False)`), so
      the streaming records this script writes are the ones PIE honours;
  (b) all four wings are added with `unreal.LevelStreamingDynamic`;
  (c) the hall starts loaded AND visible; the other three start neither;
  (d) each fitting carries exactly ONE `Fitting.<WING>.<N>` tag beside the class's own
      `WingFitting`, all seventeen distinct, and every tag reads back after a load from
      disk. The fixture cannot gate this: three of the four wings are out of the world
      when `PrepareTest` runs, so their tags are unobservable until after the submission
      has had its turn, and an attributed exit keyed on them would be a denominator
      opt-out a submission could buy. So the authoring-fault gate lives HERE, which is
      the one place it can be submission-proof;
  (e) World Settings name NO game mode, so the level inherits `BP_ThirdPersonGameMode`
      and `BP_ThirdPersonPlayerController` -- which carries `IMC_Default` -- and the play
      lane comes for free (the 2026-08-17 unplayable-play-lane finding);
  (f) every fitting's `WingLabel` is set. The FIXTURE never reads it; the REFERENCE
      counts what is standing with it, so an unset label makes the board read `ROSE 0`
      and fails `BoardNamesTheOpenWing` at cp1 -- a map fault wearing a gate's name.
      This matters MORE now than it did when every wing held three: the count is a
      graded number, not a constant the reference could fall back on;
  (g) the PlayerStart sits on the clear ground square below ALPHA, so the fixture's first
      straight leg crosses no other mark's step volume. The fixture does NOT check where
      the player starts, so a PlayerStart east of BETA would call the wrong wing first
      and manufacture a FAIL on correct work.

THE LAYOUT TABLE BELOW IS SHARED WITH THE JUDGE AND IS GRADED. It is the same set of
numbers as `kMarkAt` / `kPostAt` / `kBoardAt` / `kHallFittingAt` in
`Source/CraftBenchTests/Tasks/t2-only-the-wing-you-called-opens/WingHostFunctionalTest.cpp`
-- marks, posts and board to 2 uu, hall fittings to 1 uu. A drift is a graded FAIL of a
correct submission, so the fixture's copy is restated here as FIXTURE_* constants and the
two are cross-checked before the first editor call.

EVERYTHING FACES SOUTH. A `UTextRenderComponent`'s glyphs live in its local YZ plane and
advance along -Y (TextRenderComponent.cpp:1373), so the scaffold's `Label` / `Nameplate`
/ `Line` (relative yaw 180) are readable from -X. Every mark, post, fitting and the board
is therefore placed at yaw +90, which turns that readable direction into -Y: the way the
player walks in from, and the way every camera in cameras.json looks. The pad, the post
and the column are square or round in XY, so the yaw costs them nothing; the board's
520 x 30 plate ends up edge-on, which is the one accepted trade -- the graded readout is
the TEXT, and an unreadable readout would be the real defect.

NOT IDEMPOTENT, on purpose: `new_level` refuses an existing package, and silently
overwriting a committed graded map is worse than stopping. Delete the five .umap files
from the SHELL and re-run.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-only-the-wing-you-called-opens"
MAPS = f"/Game/Maps/{TASK}"
HOST = f"{MAPS}/L_WingHost"
HOST_NAME = "L_WingHost"

# ============================== THE LAYOUT TABLE ==============================
# Shared with WingHostFunctionalTest.cpp. GRADED. Copy it; never re-derive it.

# (MarkId, X, Y, the wing this mark is LETTERED WITH IN THE SAVED LEVEL).
# The staged letters are leg 0 / deal 0 of the fixture's own deal table. PrepareTest
# re-deals immediately, so this cannot touch the grade -- it exists so a human who simply
# presses Play walks into a coherent, correctly labelled building.
MARKS = (
    ("ALPHA", -1400.0, -1200.0, "ROSE"),
    ("BETA", 0.0, -1200.0, "GOLD"),
    ("GAMMA", 1400.0, -1200.0, "SLATE"),
)

# (WingName, X, Y, SectionId). SectionId is a BARE BASENAME and never a /Game/ path:
# UGameplayStatics::GetStreamingLevel runs the name through MakeSafeLevelName (which
# prepends the PIE prefix) and then suffix-matches GetWorldAssetPackageName()
# (GameplayStatics.cpp:940-966), so a basename is what resolves under PIE.
# THE SECTION NAME IS NOT THE WING NAME, and it is printed nowhere the agent can read.
# GetStreamingLevel suffix-matches case-insensitively, so an L_Wing<WING> scheme would
# make the post decorative and the join free.
POSTS = (
    ("HALL", -2250.0, 600.0, "L_WingVault"),
    ("ROSE", -750.0, 600.0, "L_WingLoft"),
    ("GOLD", 750.0, 600.0, "L_WingKeep"),
    ("SLATE", 2250.0, 600.0, "L_WingSpur"),
)

# HOW MANY FITTINGS EACH WING HOLDS, in POSTS order. Different on purpose: the board's
# number is a graded world read, so no constant can supply it. The hall keeps THREE
# because its three positions are the graded in-scene control and are shared with the
# fixture verbatim.
WING_FITTINGS = (3, 4, 6, 4)
BOARD_AT = (0.0, 2450.0)

# A wing's fittings stand at its own post. The first three are the triangle the hall uses
# -- ordinal 1 west, 2 far, 3 east, the order kHallFittingAt is written in -- and wings
# larger than three take the next offsets in order. |dx| never exceeds 620 uu, so with
# posts 1,500 uu apart the nearest columns of two neighbouring wings stay 170 uu clear of
# each other, and no fitting of any wing lands within 200 uu of the floor's edge.
FITTING_OFFSETS = ((-420.0, 650.0), (0.0, 1050.0), (420.0, 650.0),
                   (-620.0, 1150.0), (620.0, 1150.0), (0.0, 1650.0))

# The clear ground square below ALPHA: where the PlayerStart stands, and where the drive
# waits while the fixture re-letters the marks. 1,200 uu from ALPHA, 1,844 from BETA.
CLEAR_SPOT = (-1400.0, -2400.0)

# The clear ground square below BETA, where the drive steps OFF BETA before stepping
# straight back onto it (the fixture's cp6, the same-mark re-step). 1,200 uu from BETA,
# 1,844 from ALPHA and from GAMMA.
STEP_OFF_SPOT = (0.0, -2400.0)

# --- the fixture's own copy, restated so a drift cannot ship silently ---
FIXTURE_MARK_AT = ((-1400.0, -1200.0), (0.0, -1200.0), (1400.0, -1200.0))
FIXTURE_POST_AT = ((-2250.0, 600.0), (-750.0, 600.0), (750.0, 600.0), (2250.0, 600.0))
FIXTURE_BOARD_AT = (0.0, 2450.0)
FIXTURE_HALL_FITTING_AT = ((-2670.0, 1250.0, 0.0),
                           (-2250.0, 1650.0, 0.0),
                           (-1830.0, 1250.0, 0.0))
FIXTURE_CLEAR_SPOT = (-1400.0, -2400.0)
FIXTURE_STEP_OFF_AT = (0.0, -2400.0)
FIXTURE_SECTION_IDS = ("L_WingVault", "L_WingLoft", "L_WingKeep", "L_WingSpur")
FIXTURE_WING_NAMES = ("HALL", "ROSE", "GOLD", "SLATE")
FIXTURE_MARK_IDS = ("ALPHA", "BETA", "GAMMA")
FIXTURE_WING_FITTINGS = (3, 4, 6, 4)   # kWingFittings
FIXTURE_HALL_FITTINGS = 3              # kHallFittings
# The fixture's own tolerances. Placement is asserted far tighter than either.
FIXTURE_HALL_MOVE_CM = 1.0
FIXTURE_FURNITURE_MOVE_CM = 2.0
PLACE_TOLERANCE_CM = 0.5

# ============================== the host's shape ==============================
FLOOR_MIN = (-3000.0, -3000.0)
FLOOR_MAX = (3000.0, 3000.0)
STRIPE_EVERY = 300.0
FACE_SOUTH_YAW = 90.0

# Z heights. The floor's top face is MEASURED off the placed block rather than assumed,
# and every one of these is checked against it: "a 100 uu cube centred at z=-50 has its
# top at 0" is arithmetic in a comment, which is not evidence.
MARK_Z = 45.0        # the pad's top ends up 5 cm proud of the floor
POST_Z = 0.0         # the post stands ON the floor
FITTING_Z = 0.0      # the column stands ON the floor -- and this one is GRADED
BOARD_Z = 300.0
START_Z = 120.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"

# The fixture registers a step at 45 uu from a mark's centre; the engine's own
# begin-overlap fires at about 152 uu (110 uu box half-extent + 42 uu capsule radius).
# A walk that grazes ANOTHER mark inside that reach would call a wing nobody asked for.
STEP_VOLUME_REACH_CM = 152.0
LEG_CLEARANCE_CM = 400.0
CLEAR_OF_MARK_CM = 700.0   # the fixture's own re-deal clearance

TASK_TAGS = ("CallMark", "WingPost", "GateBoard", "WingFitting")


def log(msg):
    unreal.log(f"WINGHOST- {msg}")


def warn(msg):
    unreal.log_warning(f"WINGHOST-WARN {msg}")


def fail(msg):
    unreal.log_error(f"WINGHOST-ERROR {msg}")
    raise SystemExit(1)


def wing_pkg(section_id):
    return f"{MAPS}/{section_id}"


def wing_index(wing):
    for i, (name, _x, _y, _s) in enumerate(POSTS):
        if name == wing:
            return i
    fail(f"no post carries the wing name {wing}")


def fittings_for(wing):
    """How many fittings the named wing holds. Cross-checked against the fixture's own
    copy in check_tables(), because the count is GRADED -- it is the number the board
    has to report, and BoardNamesTheOpenWing compares the rendered line exactly."""
    return WING_FITTINGS[wing_index(wing)]


def fitting_spots(post_x, post_y, count):
    """The `count` fittings of the wing whose post stands at (post_x, post_y)."""
    if count > len(FITTING_OFFSETS):
        fail(f"a wing wants {count} fittings and only {len(FITTING_OFFSETS)} offsets "
             f"are defined; add offsets that keep |dx| <= 620 uu or the neighbouring "
             f"wings' columns overlap")
    return tuple((post_x + dx, post_y + dy, FITTING_Z)
                 for dx, dy in FITTING_OFFSETS[:count])


def fitting_tag(wing, ordinal):
    return f"Fitting.{wing}.{ordinal}"


def point_to_segment(p, a, b):
    """Shortest 2D distance from p to the segment ab."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = 0.0 if span <= 0.0 else max(0.0, min(1.0,
                                             ((px - ax) * dx + (py - ay) * dy) / span))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# --------------------------------------------------------------------- the tables

def check_tables():
    """The two tables are one table. Cross-checked BEFORE the first editor call, so a
    drift costs a second instead of a whole graded run."""
    for i, (mark_id, x, y, _letter) in enumerate(MARKS):
        if (x, y) != FIXTURE_MARK_AT[i] or mark_id != FIXTURE_MARK_IDS[i]:
            fail(f"mark {i} is ({mark_id}, {x}, {y}) here and {FIXTURE_MARK_IDS[i]} at "
                 f"{FIXTURE_MARK_AT[i]} in the fixture; marks are graded to "
                 f"{FIXTURE_FURNITURE_MOVE_CM} uu, so a drift FAILs SealedWingUntouched "
                 f"against a correct submission")
    for i, (wing, x, y, section) in enumerate(POSTS):
        if (x, y) != FIXTURE_POST_AT[i]:
            fail(f"post {wing} is at ({x}, {y}) here and {FIXTURE_POST_AT[i]} in the "
                 f"fixture")
        if wing != FIXTURE_WING_NAMES[i] or section != FIXTURE_SECTION_IDS[i]:
            fail(f"post {i} is {wing}->{section} here and {FIXTURE_WING_NAMES[i]}->"
                 f"{FIXTURE_SECTION_IDS[i]} in the fixture")
    if WING_FITTINGS != FIXTURE_WING_FITTINGS:
        fail(f"the wings hold {WING_FITTINGS} fittings here and the fixture grades "
             f"{FIXTURE_WING_FITTINGS}; the count is the number the board has to "
             f"report, so a drift FAILs BoardNamesTheOpenWing (and CalledWingOpens) "
             f"against a correct submission")
    if WING_FITTINGS[0] != FIXTURE_HALL_FITTINGS:
        fail(f"the hall holds {WING_FITTINGS[0]} fittings and the fixture's control "
             f"gate reads {FIXTURE_HALL_FITTINGS}")
    if len(set(WING_FITTINGS[1:])) < 2:
        fail(f"the three callable wings hold {WING_FITTINGS[1:]} fittings; at least "
             f"two different sizes are needed or a CONSTANT count satisfies the "
             f"board at every gauge point of both legs and the readout stops being "
             f"load-bearing")
    if BOARD_AT != FIXTURE_BOARD_AT:
        fail(f"the board is at {BOARD_AT} here and {FIXTURE_BOARD_AT} in the fixture")
    if CLEAR_SPOT != FIXTURE_CLEAR_SPOT:
        fail(f"the clear spot is {CLEAR_SPOT} here and {FIXTURE_CLEAR_SPOT} in the "
             f"fixture; the drive walks to the fixture's one, so a PlayerStart anywhere "
             f"else is not where the drive begins")
    if STEP_OFF_SPOT != FIXTURE_STEP_OFF_AT:
        fail(f"the step-off spot is {STEP_OFF_SPOT} here and {FIXTURE_STEP_OFF_AT} in "
             f"the fixture; the drive walks to the fixture's one")
    hall = fitting_spots(POSTS[0][1], POSTS[0][2], WING_FITTINGS[0])
    if hall != FIXTURE_HALL_FITTING_AT:
        fail(f"the hall's fittings come out at {hall} and the fixture compares against "
             f"{FIXTURE_HALL_FITTING_AT} to {FIXTURE_HALL_MOVE_CM} uu; the in-scene "
             f"negative control would fail at cp0 against every submission")
    # GetStreamingLevel SUFFIX-matches, so one basename ending in another would make two
    # wings resolve to one section.
    for a in FIXTURE_SECTION_IDS:
        for b in FIXTURE_SECTION_IDS:
            if a != b and ("/" + b).endswith("/" + a):
                fail(f"section basename {a} is a suffix of {b}; GetStreamingLevel "
                     f"suffix-matches, so the two wings would resolve to one section")
    # Every walk the fixture makes is a straight leg between these points, and none of
    # them may graze a mark it is not aiming at.
    alpha = (MARKS[0][1], MARKS[0][2])
    beta = (MARKS[1][1], MARKS[1][2])
    legs = (("PlayerStart -> ALPHA", CLEAR_SPOT, alpha, 0),
            ("ALPHA -> BETA", alpha, beta, 1),
            ("BETA -> ALPHA", beta, alpha, 0),
            ("ALPHA -> the clear spot", alpha, CLEAR_SPOT, None),
            ("the clear spot -> ALPHA", CLEAR_SPOT, alpha, 0),
            ("ALPHA -> BETA (again)", alpha, beta, 1),
            # cp6, the same-mark re-step: off BETA and straight back onto it.
            ("BETA -> the step-off spot", beta, STEP_OFF_SPOT, None),
            ("the step-off spot -> BETA", STEP_OFF_SPOT, beta, 1))
    for what, start, end, target in legs:
        for i, (mark_id, mx, my, _l) in enumerate(MARKS):
            if target is not None and i == target:
                continue
            if (mx, my) == start:
                continue
            gap = point_to_segment((mx, my), start, end)
            if gap < LEG_CLEARANCE_CM:
                fail(f"the leg '{what}' passes {gap:.0f} uu from mark {mark_id}, whose "
                     f"step volume reaches {STEP_VOLUME_REACH_CM:.0f} uu; the drive "
                     f"would call a wing nobody asked for and the FAIL would be ours")
    for what, spot in (("clear spot", CLEAR_SPOT), ("step-off spot", STEP_OFF_SPOT)):
        for mark_id, mx, my, _l in MARKS:
            gap = math.hypot(spot[0] - mx, spot[1] - my)
            if gap < CLEAR_OF_MARK_CM:
                fail(f"the {what} is {gap:.0f} uu from mark {mark_id}, and the fixture "
                     f"will not advance past it until the character is "
                     f"{CLEAR_OF_MARK_CM:.0f} uu clear of every mark; the phase would "
                     f"never end and the run would stop at the sentinel")
    # Every fitting of every wing must sit ON the floor and INSIDE it.
    for wing, px, py, _s in POSTS:
        for n, (fx, fy, _fz) in enumerate(
                fitting_spots(px, py, fittings_for(wing)), start=1):
            if not (FLOOR_MIN[0] + 200.0 <= fx <= FLOOR_MAX[0] - 200.0
                    and FLOOR_MIN[1] + 200.0 <= fy <= FLOOR_MAX[1] - 200.0):
                fail(f"fitting {wing}.{n} at ({fx}, {fy}) is off the floor "
                     f"{FLOOR_MIN}..{FLOOR_MAX}; it would stand in mid-air")
    # NO TWO WINGS' FITTINGS MAY STAND IN EACH OTHER. A column is 90 cm across, so
    # two centres closer than that are one solid lump a person cannot read.
    placed = []
    for wing, px, py, _s in POSTS:
        for n, (fx, fy, _fz) in enumerate(
                fitting_spots(px, py, fittings_for(wing)), start=1):
            placed.append((f"{wing}.{n}", fx, fy))
    for i, (an, ax, ay) in enumerate(placed):
        for bn, bx, by in placed[i + 1:]:
            gap = math.hypot(ax - bx, ay - by)
            if gap < 140.0:
                fail(f"fittings {an} and {bn} stand {gap:.0f} uu apart and a column "
                     f"is 90 cm across; widen FITTING_OFFSETS")
    log("layout table agrees with the fixture's copy; every straight leg is clear")


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
    for cls_name in ("CallMarkActor", "WingPostActor", "GateBoardActor",
                     "WingFittingActor", "WingHostFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built? "
                 f"(the fixture lives in CraftBenchTests, the other four in ThirdPerson)")
        got[cls_name] = getattr(unreal, cls_name)
    if not hasattr(unreal, "LevelStreamingDynamic"):
        fail("unreal.LevelStreamingDynamic is not available; the wings cannot be added "
             "as dynamic sections and an always-loaded hall makes the control gate dead")
    for pkg in [HOST] + [wing_pkg(s) for s in FIXTURE_SECTION_IDS]:
        if unreal.EditorAssetLibrary.does_asset_exist(pkg):
            fail(f"{pkg} already exists. Delete the five .umap files from the SHELL and "
                 f"re-run; this script will not overwrite a committed graded map.")
    log(f"probe OK: {sorted(k for k in got)}")
    return got


def editor_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None:
        fail("no editor world")
    return world


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
        # The PROFILE, not just the enum: on an earlier task set_collision_enabled alone
        # did not survive into the saved level, and paint that quietly blocks the floor
        # is indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def paint_stripe(env, a, b, label, width=16.0):
    """A thin painted line on the floor from a to b. Never collides."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1.0:
        return
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    block(env, CUBE,
          unreal.Vector((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, 2.0),
          unreal.Vector(length / 100.0, width / 100.0, 0.04), label, M_STRIPE, yaw=yaw)


def add_task_tag(actor, tag):
    """APPEND, never replace: every one of these classes adds its own class tag in its
    constructor, and the fixture reads both -- the class tag to know the thing is a
    fitting at all, the per-instance tag to know WHICH fitting it is. Replacing the array
    would drop the class tag and make every fitting an unnamed one."""
    tags = [str(t) for t in (actor.get_editor_property("tags") or [])]
    if tag not in tags:
        tags.append(tag)
    actor.set_editor_property("tags", [unreal.Name(t) for t in tags])
    return tags


def spawn_fitting(env, wing, ordinal, spot):
    fitting = env["eas"].spawn_actor_from_class(
        env["WingFittingActor"],
        unreal.Vector(spot[0], spot[1], spot[2]),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=FACE_SOUTH_YAW))
    if fitting is None:
        fail(f"could not place fitting {wing}.{ordinal}")
    fitting.set_actor_label(f"Fitting_{wing}_{ordinal}")
    # THE IDENTITY THE FIXTURE GRADES BY. Not a property: AWingFittingActor lives in the
    # agent-writable module, so every UPROPERTY on it is a value the submission controls.
    add_task_tag(fitting, fitting_tag(wing, ordinal))
    # THE NAME THE REFERENCE COUNTS BY, and the only thing the nameplate prints. The
    # fixture never reads it; leave it unset and the board reads 'ROSE 0'.
    fitting.set_editor_property("wing_label", wing)
    return fitting


def read_fittings(env, expect_wing, expect_spots, scope_to_wing=False):
    """Every fitting in the CURRENTLY LOADED world, checked against one wing's table.
    Called after a load from disk, which is the only read that proves anything.

    `scope_to_wing` narrows the read to this wing's own tags. It is False when the world
    IS one wing (so a stray fitting is a hard fault) and True in the host, where whether
    the editor keeps a shut section's actors around is the editor's business and not a
    statement about PIE -- that one is reported separately, and loudly."""
    prefix = f"Fitting.{expect_wing}."
    seen = {}
    for actor in env["eas"].get_all_level_actors():
        if not actor.actor_has_tag("WingFitting"):
            continue
        tags = [str(t) for t in (actor.get_editor_property("tags") or [])]
        ids = [t for t in tags if t.startswith("Fitting.")]
        if scope_to_wing and not any(t.startswith(prefix) for t in ids):
            continue
        if len(ids) != 1:
            fail(f"a fitting in {expect_wing} carries {len(ids)} Fitting.* tag(s) "
                 f"({tags}); the fixture counts anything with none or two as a thing "
                 f"nobody can name and fails OnlyCalledWingPresent by name")
        if ids[0] in seen:
            fail(f"tag {ids[0]} is on two actors in {expect_wing}; a duplicate fails "
                 f"OnlyCalledWingPresent (the multiset is exact)")
        seen[ids[0]] = actor
    want = len(expect_spots)
    if len(seen) != want:
        fail(f"{expect_wing} holds {len(seen)} tagged fitting(s), not {want}: "
             f"{sorted(seen)}. The count is GRADED -- it is the number the board has "
             f"to report and the size of the multiset OnlyCalledWingPresent demands")
    for n, spot in enumerate(expect_spots, start=1):
        tag = fitting_tag(expect_wing, n)
        actor = seen.get(tag)
        if actor is None:
            fail(f"{expect_wing} has no fitting tagged {tag}; found {sorted(seen)}")
        at = actor.get_actor_location()
        drift = math.dist((at.x, at.y, at.z), spot)
        if drift > PLACE_TOLERANCE_CM:
            fail(f"{tag} read back {drift:.2f} uu from {spot}; the hall's three are "
                 f"graded to {FIXTURE_HALL_MOVE_CM} uu")
        label = str(actor.get_editor_property("wing_label"))
        if label != expect_wing:
            fail(f"{tag} carries WingLabel '{label}', not '{expect_wing}'; the reference "
                 f"counts standing fittings by that name, so the board would read "
                 f"'{expect_wing} 0' and fail BoardNamesTheOpenWing at cp1")
        columns = [c for c in actor.get_components_by_class(unreal.StaticMeshComponent)]
        if not columns:
            fail(f"{tag} carries no mesh; OpenWingIsSolidAndSeen would fail on it")
        solid = False
        for comp in columns:
            enabled = comp.get_collision_enabled()
            if enabled in (unreal.CollisionEnabled.QUERY_ONLY,
                           unreal.CollisionEnabled.QUERY_AND_PHYSICS):
                solid = True
            if not comp.get_editor_property("visible"):
                fail(f"{tag} has a hidden mesh component; OpenWingIsSolidAndSeen refuses "
                     f"invisible stand-ins and would fail a correct submission")
        if not solid:
            fail(f"{tag} answers no collision query; the prompt promises its fittings "
                 f"are solid enough to walk into and OpenWingIsSolidAndSeen checks it")
    return seen


def nearest_to(pool, at):
    """(actor, distance) for the actor in `pool` nearest the 2D point `at`."""
    best, best_d = None, None
    for actor in pool:
        loc = actor.get_actor_location()
        d = math.hypot(loc.x - at[0], loc.y - at[1])
        if best_d is None or d < best_d:
            best, best_d = actor, d
    return best, (best_d if best_d is not None else float("inf"))


def check_placed_furniture(env, where):
    """The three marks, four posts and one board against the shared layout table.

    Run BOTH before the save (so a placement bug never reaches the disk) and again
    after re-opening the host FROM DISK (so a serialization surprise never reaches a
    graded run). Every one of these is something the fixture grades to 2 uu and names as
    a SealedWingUntouched failure, so a drift here presents as a model failure."""
    by_tag = {tag: [] for tag in TASK_TAGS}
    for actor in env["eas"].get_all_level_actors():
        for tag in TASK_TAGS:
            if actor.actor_has_tag(tag):
                by_tag[tag].append(actor)
    counts = {tag: len(v) for tag, v in by_tag.items()}
    if counts["CallMark"] != 3 or counts["WingPost"] != 4 or counts["GateBoard"] != 1:
        fail(f"[{where}] the host holds {counts}; the fixture resolves three marks, four "
             f"posts and one board by tag and reports a missing one as a graded "
             f"SealedWingUntouched failure")

    for mark_id, mx, my, letter in MARKS:
        mark, drift = nearest_to(by_tag["CallMark"], (mx, my))
        if drift > PLACE_TOLERANCE_CM:
            fail(f"[{where}] the nearest mark to {mark_id}'s slot ({mx}, {my}) is "
                 f"{drift:.2f} uu away; marks are graded to "
                 f"{FIXTURE_FURNITURE_MOVE_CM} uu")
        got_id = str(mark.get_editor_property("mark_id"))
        if got_id != mark_id:
            fail(f"[{where}] the mark at ({mx}, {my}) reads MarkId '{got_id}', not "
                 f"'{mark_id}'; the fixture matches the table by position and then checks "
                 f"the name, so a swap is a graded FAIL")
        got_letter = str(mark.get_editor_property("called_wing_name"))
        if got_letter != letter:
            fail(f"[{where}] mark {mark_id} is lettered '{got_letter}' and the level "
                 f"stages leg 0 deal 0 ('{letter}'); the grade is unaffected -- "
                 f"PrepareTest re-deals -- but a human pressing Play would walk into a "
                 f"building that lies about itself")

    for wing, px, py, section_id in POSTS:
        post, drift = nearest_to(by_tag["WingPost"], (px, py))
        if drift > PLACE_TOLERANCE_CM:
            fail(f"[{where}] the nearest post to {wing}'s slot ({px}, {py}) is "
                 f"{drift:.2f} uu away")
        got_wing = str(post.get_editor_property("wing_name"))
        got_section = str(post.get_editor_property("section_id"))
        if got_wing != wing:
            fail(f"[{where}] the post at ({px}, {py}) carries WingName '{got_wing}', not "
                 f"'{wing}'")
        if got_section != section_id:
            fail(f"[{where}] the {wing} post points at section '{got_section}', not "
                 f"'{section_id}'; the reference resolves a wing's section off its own "
                 f"post at the point of use, so it would open nothing")
        if got_section.startswith("/"):
            fail(f"[{where}] the {wing} post's SectionId '{got_section}' is a path; "
                 f"GetStreamingLevel wants a BARE BASENAME so the PIE prefix can be "
                 f"prepended before the suffix match")

    board, drift = nearest_to(by_tag["GateBoard"], BOARD_AT)
    if drift > PLACE_TOLERANCE_CM:
        fail(f"[{where}] the board is {drift:.2f} uu from {BOARD_AT}")
    if not any(c.get_name() == "Line" for c
               in board.get_components_by_class(unreal.TextRenderComponent)):
        fail(f"[{where}] the board carries no component named 'Line'; the fixture "
             f"prefers that component when it reads the RENDERED text, and the readout "
             f"is graded")

    starts = [a for a in env["eas"].get_all_level_actors()
              if a.get_class().get_name() == "PlayerStart"]
    if len(starts) != 1:
        fail(f"[{where}] {len(starts)} PlayerStart(s); the drive begins wherever the "
             f"player is put, and the fixture does not check where that is")
    at = starts[0].get_actor_location()
    if math.hypot(at.x - CLEAR_SPOT[0], at.y - CLEAR_SPOT[1]) > PLACE_TOLERANCE_CM:
        fail(f"[{where}] PlayerStart is at ({at.x:.0f}, {at.y:.0f}) and the drive's "
             f"straight legs are solved from {CLEAR_SPOT}; anywhere else can cross a "
             f"mark's step volume on the way to ALPHA and call the wrong wing first")
    for mark_id, mx, my, _l in MARKS:
        gap = math.hypot(at.x - mx, at.y - my)
        if gap < CLEAR_OF_MARK_CM:
            fail(f"[{where}] PlayerStart is {gap:.0f} uu from mark {mark_id}; the "
                 f"character would begin play standing on a mark")

    fixtures = [a for a in env["eas"].get_all_level_actors()
                if a.get_class().get_name() == "WingHostFunctionalTest"]
    if len(fixtures) != 1:
        fail(f"[{where}] {len(fixtures)} AWingHostFunctionalTest actor(s); the "
             f"automation filter needs exactly one placed fixture")
    log(f"[{where}] 3 marks, 4 posts, 1 board, 1 PlayerStart and 1 fixture all agree "
        f"with the shared layout table")


def build_wing(env, wing, section_id, post_x, post_y):
    """One wing: a fresh level holding that wing's own number of fittings and nothing
    else, saved, then RE-LOADED FROM DISK and read back."""
    pkg = wing_pkg(section_id)
    spots = fitting_spots(post_x, post_y, fittings_for(wing))
    if not env["les"].new_level(pkg, False):
        fail(f"new_level({pkg}) returned False")
    log(f"created {pkg}")
    for n, spot in enumerate(spots, start=1):
        spawn_fitting(env, wing, n, spot)
    # A wing holds ITS OWN fittings AND NOTHING ELSE. Anything carrying another task tag
    # here would be a second copy of the host's furniture inside a streamed section.
    for actor in env["eas"].get_all_level_actors():
        for tag in TASK_TAGS:
            if tag != "WingFitting" and actor.actor_has_tag(tag):
                fail(f"{pkg} holds an actor tagged {tag}; a wing is its own fittings "
                     f"and nothing else")
    if not env["les"].save_current_level():
        fail(f"save_current_level() returned False for {pkg}")
    if not unreal.EditorAssetLibrary.does_asset_exist(pkg):
        fail(f"{pkg} reports saved and does not exist on disk")
    # THE READ THAT PROVES ANYTHING: from disk, not from the objects just spawned.
    if not env["les"].load_level(pkg):
        fail(f"load_level({pkg}) returned False; the wing cannot be read back")
    read_fittings(env, wing, spots)
    log(f"SAVED and read back from disk: {pkg} -- {len(spots)} fitting(s), tags "
        f"{[fitting_tag(wing, n) for n in range(1, len(spots) + 1)]}, "
        f"WingLabel={wing}")
    return spots


# ------------------------------------------------------------------- the streaming

def set_streaming_flag(streaming, prop, setter, value, what):
    """Set one of the two flags that decide whether a wing is in the running world.

    THREE MECHANISMS, TRIED IN ORDER, AND THE READ-BACK IS THE AUTHORITY. bShouldBeLoaded
    and bShouldBeVisible are UPROPERTYs with a BlueprintSetter and no EditAnywhere
    (LevelStreaming.h:261/266), so `set_editor_property` reaches them via CPF_BlueprintVisible
    (PropertyAccessUtil.cpp:725) -- but that is a rule about a property flag, not a
    contract, so the attribute form and the reflected setter are both kept as fallbacks
    and the value is READ BACK either way. Failing here beats shipping a level whose hall
    is not in the world at cp0."""
    ok = False
    for how in ("set_editor_property", "attribute", setter):
        try:
            if how == "set_editor_property":
                streaming.set_editor_property(prop, value)
            elif how == "attribute":
                setattr(streaming, prop, value)
            else:
                streaming.call_method(setter, (value,))
            ok = True
            break
        except Exception as exc:                                # noqa: BLE001
            warn(f"{what}: {how} could not set {prop} ({exc}); trying the next form")
    if not ok:
        fail(f"{what}: nothing could set {prop}; without it the wing's start state is "
             f"whatever the editor left behind")
    try:
        got = bool(streaming.get_editor_property(prop))
    except Exception as exc:                                    # noqa: BLE001
        fail(f"{what}: {prop} is not readable back ({exc}); an unverifiable start state "
             f"is exactly the fault this script exists to catch")
    if got != value:
        fail(f"{what}: {prop} reads {got} after being set to {value}")
    return got


def add_wings_to_host(env, world):
    """Add the four wings as DYNAMIC sections, stage the hall in and the rest out."""
    streams = {}
    for wing, _x, _y, section_id in POSTS:
        pkg = wing_pkg(section_id)
        streaming = unreal.EditorLevelUtils.add_level_to_world(
            world, pkg, unreal.LevelStreamingDynamic)
        if streaming is None:
            fail(f"add_level_to_world({pkg}) returned None; the wing is not a section of "
                 f"the host and no submission could ever bring it in")
        cls_name = streaming.get_class().get_name()
        if cls_name != "LevelStreamingDynamic":
            fail(f"{section_id} was added as {cls_name}; an always-loaded section makes "
                 f"SealedWingUntouched an unfailable dead gate and the whole coupling a "
                 f"permissive fake, and the fixture raises a HARNESS-PRECONDITION on it")
        if not streaming.is_level_loaded():
            fail(f"{section_id} was added but its level did not load; nothing can be "
                 f"read back and the fittings' tags cannot be checked from the host")
        streams[section_id] = streaming
        log(f"added {section_id} as {cls_name}")

    # THE HALL IS IN THE RUNNING WORLD FROM THE FIRST FRAME; the other three are out of
    # it. The two runtime flags are the authority PIE honours; the editor visibility is
    # set to MATCH so the level a human opens shows what play shows, and so nothing can
    # leak into PIE from an editor-visible section.
    for wing, _x, _y, section_id in POSTS:
        streaming = streams[section_id]
        resident = (wing == "HALL")
        what = f"section {section_id} ({wing})"
        set_streaming_flag(streaming, "should_be_loaded", "SetShouldBeLoaded",
                           resident, what)
        set_streaming_flag(streaming, "should_be_visible", "SetShouldBeVisible",
                           resident, what)
        level = streaming.get_loaded_level()
        if level is None:
            fail(f"{what} has no loaded level to set the editor visibility of")
        unreal.EditorLevelUtils.set_level_visibility(level, resident, False)
        log(f"{what}: should_be_loaded={resident} should_be_visible={resident} "
            f"editor_visible={streaming.is_level_visible()}")
    return streams


# ------------------------------------------------------------------------- the host

def build_host(env):
    les, eas = env["les"], env["eas"]
    if not les.new_level(HOST, False):
        fail(f"new_level({HOST}) returned False")
    log(f"created {HOST} (non-partitioned, so its streaming records are the ones PIE "
        f"honours)")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    floor = block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
                  collide=True)
    origin, extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = origin.z + extent.z
    log(f"floor {span_x:.0f}x{span_y:.0f}, top face MEASURED at z={floor_top_z:.1f}")
    if abs(floor_top_z - 0.0) > 0.5:
        fail(f"the floor's top face measures z={floor_top_z:.1f} and every graded Z in "
             f"the layout table is written against z=0; the hall's three fittings are "
             f"compared to within {FIXTURE_HALL_MOVE_CM} uu including Z, so they would "
             f"all read as moved")

    # THE SHOWROOM GRID. Stripes both ways at 300 cm so both the north-south approach and
    # the east-west walk between marks are readable by eye. Never collides.
    lines = 0
    y = FLOOR_MIN[1] + STRIPE_EVERY
    while y < FLOOR_MAX[1] - 1.0:
        paint_stripe(env, (FLOOR_MIN[0], y), (FLOOR_MAX[0], y), f"Stripe_Y_{lines:02d}")
        lines += 1
        y += STRIPE_EVERY
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0] - 1.0:
        paint_stripe(env, (x, FLOOR_MIN[1]), (x, FLOOR_MAX[1]), f"Stripe_X_{lines:02d}")
        lines += 1
        x += STRIPE_EVERY
    log(f"painted {lines} stripes every {STRIPE_EVERY:.0f} cm, both ways")

    for mark_id, mx, my, letter in MARKS:
        mark = eas.spawn_actor_from_class(
            env["CallMarkActor"], unreal.Vector(mx, my, MARK_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=FACE_SOUTH_YAW))
        if mark is None:
            fail(f"could not place mark {mark_id}")
        mark.set_actor_label(f"CallMark_{mark_id}")
        mark.set_editor_property("mark_id", mark_id)
        # Leg 0 / deal 0. PrepareTest re-deals before anything is graded; this is here so
        # a human who presses Play reads a coherent building.
        mark.set_editor_property("called_wing_name", letter)

    for wing, px, py, section_id in POSTS:
        post = eas.spawn_actor_from_class(
            env["WingPostActor"], unreal.Vector(px, py, POST_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=FACE_SOUTH_YAW))
        if post is None:
            fail(f"could not place the {wing} post")
        post.set_actor_label(f"WingPost_{wing}")
        post.set_editor_property("wing_name", wing)
        # THE JOIN THE WHOLE TASK TURNS ON, and a BARE BASENAME on purpose.
        post.set_editor_property("section_id", section_id)

    board = eas.spawn_actor_from_class(
        env["GateBoardActor"], unreal.Vector(BOARD_AT[0], BOARD_AT[1], BOARD_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=FACE_SOUTH_YAW))
    if board is None:
        fail("could not place the gate board")
    board.set_actor_label("GateBoard")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(CLEAR_SPOT[0], CLEAR_SPOT[1], START_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=FACE_SOUTH_YAW))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A back wall and two differently sized landmarks, so a moving camera reads as moving
    # and each end of the host is tellable from the other. Non-colliding.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.5, 2.8), "Backdrop", M_DARK)
    block(env, CYL, unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MAX[1] - 250.0, 300.0),
          unreal.Vector(1.2, 1.2, 6.0), "Landmark_West", M_HAZARD)
    block(env, CYL, unreal.Vector(FLOOR_MAX[0] - 300.0, FLOOR_MAX[1] - 250.0, 450.0),
          unreal.Vector(2.2, 2.2, 9.0), "Landmark_East", M_GLOW)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-52.0, yaw=-60.0))
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
        env["WingHostFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 200.0, FLOOR_MIN[1] + 200.0, 200.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("WingHostFunctionalTest")

    world = editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default or the pawn stops carrying the four input actions and the "
             "player controller stops carrying IMC_Default -- the map would grade "
             "byte-identically while being uncontrollable")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # NO FITTING MAY LIVE IN THE PERSISTENT LEVEL. If the hall's three sat here the
    # owner's named wrong answer -- clear every section, then load the target -- would
    # never touch them, and the task would collapse into a T0.
    for actor in eas.get_all_level_actors():
        if actor.actor_has_tag("WingFitting"):
            fail(f"{actor.get_actor_label()} is a fitting in the PERSISTENT level; every "
                 f"fitting belongs to a streamed wing, the hall included, or the control "
                 f"the whole task rests on cannot fail")

    # BEFORE THE BYTES ARE WRITTEN. The from-disk pass below is strictly stronger, but a
    # placement fault is much cheaper to read here than as a serialization surprise.
    check_placed_furniture(env, "pre-save")

    streams = add_wings_to_host(env, world)

    # add_level_to_world makes the level it added CURRENT (EditorLevelUtils.cpp:412), so
    # the persistent level has to be made current again before anything is saved.
    if not les.set_current_level_by_name(HOST_NAME):
        fail(f"set_current_level_by_name({HOST_NAME}) returned False; the save would "
             f"land on a wing rather than on the host")
    if not les.save_current_level():
        fail("save_current_level() returned False for the host")
    # Belt and braces: a sublevel dirtied by the visibility change gets written too. Its
    # return is advisory -- there may be nothing left dirty -- and the from-disk pass
    # below is the actual authority.
    log(f"save_all_dirty_levels() -> {les.save_all_dirty_levels()}")
    for pkg in [HOST] + [wing_pkg(s) for s in FIXTURE_SECTION_IDS]:
        if not unreal.EditorAssetLibrary.does_asset_exist(pkg):
            fail(f"{pkg} does not exist on disk after the save")
    log(f"SAVED {HOST} with {len(streams)} dynamic sections")


# --------------------------------------------------------- the read that counts

def verify_host_from_disk(env):
    """Re-open the host FROM DISK and check every fact the fixture's tables assume.

    Everything up to here read objects this script had just created. This reads what a
    graded run will read. A failure here means the five levels are on disk and MUST NOT
    BE COMMITTED."""
    les, eas = env["les"], env["eas"]
    if not les.load_level(HOST):
        fail(f"load_level({HOST}) returned False; the host cannot be re-opened")
    world = editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("the saved host names a game mode; the play lane is dead and the map would "
             "still grade byte-identically")

    check_placed_furniture(env, "from disk")

    # ---- the four sections, read the way the FIXTURE reads them ----
    resolved = {}
    for wing, _x, _y, section_id in POSTS:
        streaming = unreal.GameplayStatics.get_streaming_level(world, section_id)
        if streaming is None:
            fail(f"GetStreamingLevel({section_id}) resolves nothing in the saved host; "
                 f"the fixture raises a HARNESS-PRECONDITION and no submission could "
                 f"ever bring the {wing} wing in")
        cls_name = streaming.get_class().get_name()
        if cls_name != "LevelStreamingDynamic":
            fail(f"{section_id} reads back as {cls_name} from disk; an always-loaded "
                 f"section cannot be taken out, SealedWingUntouched becomes an "
                 f"unfailable dead gate and the coupling becomes a permissive fake")
        for other, got in resolved.items():
            if got is streaming:
                fail(f"{section_id} and {other} resolve to the same streaming section; "
                     f"two wings sharing one package means neither can be opened alone")
        resolved[section_id] = streaming
        resident = (wing == "HALL")
        for prop in ("should_be_loaded", "should_be_visible"):
            got = bool(streaming.get_editor_property(prop))
            if got != resident:
                fail(f"{section_id} ({wing}) reads {prop}={got} from disk, expected "
                     f"{resident}. The hall must be in the running world at cp0 and the "
                     f"other three must not: a resident rose fails "
                     f"OnlyCalledWingPresent at cp0, and an absent hall fails "
                     f"SealedWingUntouched at cp0, both against a correct submission")

    # ---- no callable wing's fitting is standing in the host ----
    strays = []
    for actor in eas.get_all_level_actors():
        for tag in [str(t) for t in (actor.get_editor_property("tags") or [])]:
            if tag.startswith("Fitting.") and not tag.startswith("Fitting.HALL."):
                strays.append(tag)
    if strays:
        # NOT a refusal: the editor's own idea of which sections are open is not PIE's,
        # and refusing on an inconclusive signal would block the map batch on a maybe.
        # But this is the ONE thing that would make cp0 fail for every correct
        # submission, so it is shouted with the check to run.
        warn(f"the editor world shows callable-wing fittings standing in the host "
             f"({sorted(set(strays))}). The saved flags are correct, so this is the "
             f"editor's view rather than PIE's -- but the FIRST graded run must be "
             f"checked for 'OnlyCalledWingPresent: at cp0 the host should hold exactly "
             f"[Fitting.HALL.1, Fitting.HALL.2, Fitting.HALL.3]'. If that fires, the fix "
             f"is in this script, never in the fixture.")

    # ---- the hall's three fittings, from disk, in the host world ----
    hall_spots = fitting_spots(POSTS[0][1], POSTS[0][2], WING_FITTINGS[0])
    read_fittings(env, "HALL", hall_spots, scope_to_wing=True)
    log(f"the hall's {len(hall_spots)} fittings read back from disk at {hall_spots}")

    # ---- nothing but the floor, the pads and the fittings may block a walk ----
    for actor in eas.get_all_level_actors():
        if actor.actor_has_tag("CallMark") or actor.actor_has_tag("WingFitting"):
            continue
        if actor.get_actor_label() == "Floor":
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            if comp.get_collision_enabled() in (unreal.CollisionEnabled.QUERY_ONLY,
                                                unreal.CollisionEnabled.QUERY_AND_PHYSICS):
                fail(f"{actor.get_actor_label()}'s {comp.get_name()} still answers "
                     f"queries; the host promises nothing stands in anybody's way, and a "
                     f"prop that blocks the floor can stall the drive into a "
                     f"HARNESS-PRECONDITION on correct work")

    log("read back from disk: 3 marks, 4 posts, 1 board, 1 PlayerStart, 1 fixture, "
        "4 dynamic sections (hall resident, three shut), 3 hall fittings, nothing in "
        "the way")


def main():
    check_tables()
    # EVERY IDENTITY DISTINCT, before a single actor is placed. The fixture's
    # multiset is exact, so one repeated tag is a graded OnlyCalledWingPresent FAIL
    # against every submission, in a message that names a gate rather than the map.
    every = [fitting_tag(w, n) for w, _x, _y, _s in POSTS
             for n in range(1, fittings_for(w) + 1)]
    if len(set(every)) != len(every) or len(every) != sum(WING_FITTINGS):
        fail(f"the {sum(WING_FITTINGS)} fitting identities are not that many distinct "
             f"names: {every}")
    env = probe()
    for wing, px, py, section_id in POSTS:
        build_wing(env, wing, section_id, px, py)
    build_host(env)
    verify_host_from_disk(env)
    log("ALL FIVE LEVELS AUTHORED, SAVED AND READ BACK FROM DISK. Commit the five .umap "
        "binaries, the fixture and the scaffold in ONE change: the runner grades the "
        "substrate from git HEAD, so a map without its fixture fails L2 for the wrong "
        "reason (filter-miss / 0 tests).")


main()
