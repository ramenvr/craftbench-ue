"""Authors L_LifeRun for t3-your-last-life-ends-the-run.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

ONE LONG STRIPED FLOOR WITH THREE LANES ON IT. Each lane opens on a painted marker
disc with a number on it; a runner stands on each. Part way down, a patch of
crumbling ground spans every lane; at the far end, a wide finish disc. The whole
task is which crossing of that patch is a runner's last one.

THIS SCRIPT SOLVES THE LEVEL BEFORE IT SAVES IT. Everything the fixture derives at
run time -- the off-lane crossing spot, the bypass corridor, every waypoint of the
whole drive, the crossing that ends the loss leg -- is re-derived here in Python
from the same numbers, and the script REFUSES TO SAVE if any of it does not come
out. That matters more here than in most tasks: `ALifeRunTerminalFunctionalTest`
reports a staging fault as a HARNESS-PRECONDITION, which is a NON-GRADED exit --
the most expensive kind of wrong verdict, because it looks like our bug on a day
when the submission was never even judged. Every check below exists so that fault
is found at authoring time instead.

What the fixture demands of this level, and where each one is enforced:
  * three ALifeMarkerActor tagged LifeMarker, >= 480 cm apart, >= 600 cm clear of
    the patch, each exposing PaintedLives            -> solve_layout / read-back
  * three ALifeRunnerCharacter tagged LifeRunner, each opening the run within
    200 cm of a DIFFERENT marker: one spawned by the level's own rules onto the
    PlayerStart, two PLACED and told apart by the per-instance tags RunnerLaneB
    (the win leg, driven) and RunnerLaneC (the bystander, never driven)
                                                      -> place_runners / read-back
  * THE PLAYER'S MARKER MUST BE AN OUTER LANE. The off-lane crossing spot is
    DERIVED by scanning the patch's near face for the point most clearly nearer
    another runner's marker than the player's own, and it must win by 400 cm. A
    player in the middle lane cannot satisfy that and the fixture says so by name
                                                      -> solve_layout
  * one ACrumbleGroundActor tagged CrumbleGround, UNSCALED and square to the
    floor, reaching a runner's standing height, spanning every lane
                                                      -> solve_layout / read-back
  * one AFinishDiscActor tagged FinishDisc with DiscRadiusUu > 100, >= 600 cm
    clear of the patch, exposing DemandedLives -- the number painted on its face,
    which the fixture re-writes TWICE mid-run so the goal opens where a runner is
    already standing                                  -> solve_layout / read-back
  * FLOOR UNDER EVERY STEP OF THE DRIVE, nothing but the floor colliding anywhere
    a runner walks, and no non-crossing segment that walks back onto the patch --
    including the bypass corridor 500 cm outside the patch's Y face, which is how
    the win leg reaches the finish without spending a life it does not have
                                                      -> solve_layout (route walk)
  * a level that can be PLAYED BY HAND. This level names its own game mode, which
    replaces GlobalDefaultGameMode -- so the game mode has to re-state
    BP_ThirdPersonPlayerController (which is what carries IMC_Default) and the
    pawn has to load the four IA_* actions. Without both the map grades
    byte-identically while being completely uncontrollable, which is how five of
    six ThirdPerson maps once shipped
    (the 2026-08-17 unplayable-play-lane finding)  -> check_play_lane

THE PAINTED NUMBERS HERE ARE NOT THE GRADED ONES. `PrepareTest` re-paints all
three markers to that framerate leg's own values before the drive starts, and
re-paints two of them again mid-run -- and it does the same to the number on the
FINISH -- so neither a life count nor the goal's own number mined out of this
committed .umap is right on either leg. The numbers authored below are what a
PERSON sees when they press Play, and they are deliberately different from every
staged value.

Every prop except the floor is NON-COLLIDING on every channel. The prompt promises
nothing in the level can push a runner anywhere, the fixture's stay-put watch
would read a shove as the submission moving a runner, and its route validation
refuses to start when anything but the floor stands where a runner walks.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-your-last-life-ends-the-run"
MAP_PKG = f"/Game/Maps/{TASK}/L_LifeRun"

# ----------------------------------------------------------------- the floor
# 9,600 x 5,600. The span is not decoration: the drive's bypass corridor runs at
# y = -2,000 and one of the loss leg's crossings lands at y = +1,342, so a floor
# sized to the three lanes alone would have the fixture refusing to start with
# "there is no floor there". solve_layout() walks every waypoint of the whole
# drive against these four numbers rather than trusting them.
FLOOR_MIN = (-800.0, -2800.0)
FLOOR_MAX = (8800.0, 2800.0)
STRIPE_EVERY = 400.0

# --------------------------------------------------------------- the three lanes
# 1,100 cm apart: the fixture refuses anything under 480 (four times the 120 cm
# that counts as standing "on" a marker), and the wider they are, the more clearly
# the off-lane crossing spot belongs to somebody else.
LANE_Y = (-1100.0, 0.0, 1100.0)
MARKER_X = 800.0

# The numbers a PERSON sees. Distinct, inside 1..6, and none of them is a value
# either staging leg ever paints (60 Hz stages 3/5/6 -> 4/5/6 -> 4/3/6 -> 1/2/6;
# 20 Hz stages 2/6/3 -> 4/6/3 -> 4/5/3 -> 6/1/3), so a submission that reads the
# committed map instead of the marker in front of it is wrong from frame one.
PAINTED = (4, 2, 5)

# ------------------------------------------------------- the two triggers
# The patch's own half-extents live in C++ (ACrumbleGroundActor's PatchVolume:
# 400 x 1500 x 120). They are MEASURED off the placed actor below, never assumed:
# a change to that box has to move this level, not silently unfit it.
PATCH_AT = (3600.0, 0.0)
DISC_AT = (7600.0, 0.0)
DISC_RADIUS_UU = 800.0
# What the finish asks for, as a PERSON sees it on pressing Play. Asserted below to
# be a value neither leg ever stages, so a submission that mines the committed map
# instead of reading the disc in front of it is wrong from the first judged frame.
DEMANDED = 4

# ------------------------------------------------- mirrors of the fixture's own
# constants, so "this level fits the fixture" is MEASURED here rather than
# discovered at run time as a non-graded HARNESS-PRECONDITION.
CAPSULE_RADIUS_UU = 42.0        # AThirdPersonCharacter::InitCapsuleSize(42, 96)
FOOT_CLEARANCE_UU = 4.0         # daylight under a runner's feet, invisible in a still
# The patch's PatchVolume hangs 60 cm above its actor's unscaled root (C++). The
# actor is placed at z=0, so this is where the box's centre lands. Asserted off the
# placed component rather than trusted.
PATCH_BOX_CENTRE_Z = 60.0
MARKER_SPACING_FLOOR_UU = 480.0  # kMarkerSpacingFloorUu (4x the 120 cm tolerance)
TRIGGER_CLEAR_UU = 600.0        # kTriggerClearUu
OWNERSHIP_MARGIN_UU = 400.0     # kOwnershipMarginUu
APPROACH_CLEAR_UU = 400.0       # kApproachClearUu
BYPASS_MARGIN_UU = 500.0        # kBypassMarginUu
ON_MARKER_UU = 120.0            # the disclosed "standing on a marker" tolerance
OFF_LANE_SCAN_STEP_UU = 25.0    # the fixture's own scan step -- see solve_layout
OFF_LANE_SCAN_INSET_UU = 100.0  # ... and its own inset from the patch's Y face
ROUTE_FLOOR_MARGIN_UU = 200.0   # how far inside the floor every waypoint must sit

# Both legs' staging tables, copied from ResolveLeg(). Nothing here is authored
# into the level -- they are mirrored so this script can derive the same
# PredictedFinalCrossing the fixture derives, and therefore build the same drive.
STAGING = {
    60: dict(start=(3, 5, 6), repaint_a=4, repaint_b=3, final=(1, 2),
             demand=(3, 5, 1)),
    20: dict(start=(2, 6, 3), repaint_a=4, repaint_b=5, final=(6, 1),
             demand=(5, 6, 2)),
}

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"LIFERUN- {msg}")


def fail(msg):
    unreal.log_error(f"LIFERUN-ERROR {msg}")
    raise SystemExit(1)


# ============================================================== the geometry
# These functions are the fixture's own arithmetic, in Python. If they disagree
# with the fixture the LEVEL is wrong, not the fixture, and the run would end as a
# non-graded HARNESS-PRECONDITION with nobody the wiser about why.

def planar_dist_to_patch(p, patch, half):
    """Signed flat distance from the patch box's surface; negative inside.
    ALifeRunTerminalFunctionalTest::PlanarDistToPatch."""
    dx = abs(p[0] - patch[0]) - half[0]
    dy = abs(p[1] - patch[1]) - half[1]
    if dx > 0.0 or dy > 0.0:
        return math.hypot(max(dx, 0.0), max(dy, 0.0))
    return max(dx, dy)


def in_patch_armed(p, patch, half):
    """Capsule centre inside the box grown by one capsule radius in the plane --
    the EARLIEST instant any part of a runner is over the patch, and the rule the
    fixture's route validation uses. InPatchArmed."""
    return (abs(p[0] - patch[0]) <= half[0] + CAPSULE_RADIUS_UU
            and abs(p[1] - patch[1]) <= half[1] + CAPSULE_RADIUS_UU)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def solve_off_lane(markers, own_index, patch, half):
    """The fixture's ValidateGeometry scan, step for step: walk the patch's NEAR
    face and keep the point that is most clearly nearer somebody ELSE's marker
    than the crossing runner's own.

    The step and the inset are copied deliberately. The scan runs
    `for (Y = -LaneLimit; Y <= LaneLimit; Y += 25.0)`, so with a 1,500 cm half
    extent it stops at +1,342 rather than reaching +1,358 -- and the spot the
    fixture picks is the one this level has to have floor under and a clear walk
    to. A hand-computed 'obvious' spot is not what runs."""
    lane_limit = half[1] - CAPSULE_RADIUS_UU - OFF_LANE_SCAN_INSET_UU
    near_x = patch[0] - half[0]
    best = (None, -1.0e9, None)
    y = -lane_limit
    while y <= lane_limit + 1e-9:
        p = (near_x, patch[1] + y)
        to_own = dist(p, markers[own_index])
        other = [(dist(p, m), i) for i, m in enumerate(markers) if i != own_index]
        to_other, other_idx = min(other)
        margin = to_own - to_other
        if margin > best[1]:
            best = (p[1], margin, other_idx)
        y += OFF_LANE_SCAN_STEP_UU
    return best


def build_routes(own_lane_a, own_lane_b, runner_lane_y, patch, half, disc, disc_r,
                 final_crossing):
    """Every waypoint of the whole drive, in order, exactly as BuildPhases builds
    it -- with the per-runner CURSOR walked forward phase by phase, because the
    routes are a SEQUENCE and validating each from a runner's opening position
    checks journeys the drive never makes.

    Returns [(runner, label, is_cross, [points...]), ...] with the phase's own
    opening position prepended, so the caller can sample real segments."""
    near_x, far_x, mid_x = patch[0] - half[0], patch[0] + half[0], patch[0]
    bypass_y = patch[1] - (half[1] + BYPASS_MARGIN_UU)
    # THE RUNNER'S OWN MARKER'S Y, never markers[0] / markers[1]: BuildPhases takes
    # OwnLaneA / OwnLaneB from Runners[0].MarkerAt / Runners[1].MarkerAt, and which
    # marker that is depends on where each runner opened the run.
    own_a, own_b = own_lane_a, own_lane_b
    off_y = runner_lane_y

    def near_stage(y):
        return (near_x - APPROACH_CLEAR_UU, y)

    def far_stage(y):
        return (far_x + APPROACH_CLEAR_UU, y)

    def cross_to(y):
        return (mid_x, y)

    disc_win = (disc[0], disc[1] - disc_r * 0.5)
    disc_lost = (disc[0], disc[1] + disc_r * 0.6)
    # Clear of the disc's reach by a full approach margin, so stepping off and back
    # on is a REAL second arrival and never a boundary skim.
    disc_step_off = (disc[0] - disc_r - APPROACH_CLEAR_UU, disc_win[1])

    phases = []

    # ---- the loss leg: matched pairs of crossings, own lane / off lane -------
    for k in range(1, final_crossing + 1):
        y = own_a if (k % 2) == 1 else off_y
        where = "its own lane" if (k % 2) == 1 else "the off lane"
        phases.append((0, f"the near runner lines up on {where}", False,
                       [near_stage(y)]))
        phases.append((0, f"the near runner walks onto the crumbling ground on "
                          f"{where} (crossing {k})", True,
                       [near_stage(y), cross_to(y)]))

    # ---- the win leg --------------------------------------------------------
    phases.append((1, "the middle runner lines up", False, [near_stage(own_b)]))
    phases.append((1, "the middle runner walks onto the crumbling ground", True,
                   [near_stage(own_b), cross_to(own_b)]))
    phases.append((1, "the middle runner lines up again", False, [near_stage(own_b)]))
    phases.append((1, "the middle runner walks onto the crumbling ground a second "
                      "time", True, [near_stage(own_b), cross_to(own_b)]))
    # AROUND the hazard, never through it: a third crossing here would spend a
    # life the win leg does not have and the finish could never be reached.
    phases.append((1, "the middle runner goes round the hazard to the finish", False,
                   [(near_x - APPROACH_CLEAR_UU, bypass_y),
                    (far_x + APPROACH_CLEAR_UU, bypass_y), disc_win]))
    # It arrives SHORT of what the finish asks for and must go on running; the goal's
    # own number then moves up (still short), the arrival is repeated so the trigger
    # fires twice, and only then does the number come down below what this runner is
    # holding -- which wins the run with nobody moving.
    phases.append((1, "the middle runner steps back off the finish", False,
                   [disc_step_off]))
    phases.append((1, "the middle runner walks onto the finish again", False,
                   [disc_win]))

    # ---- the ended runs are driven at, on BOTH terminal kinds ----------------
    phases.append((0, "the lost runner is walked back off the crumbling ground",
                   False, [near_stage(off_y)]))
    phases.append((0, "the lost runner is walked onto the crumbling ground again",
                   True, [near_stage(off_y), cross_to(off_y)]))
    phases.append((0, "the lost runner is walked onto the finish", False,
                   [far_stage(off_y), disc_lost]))
    phases.append((1, "the won runner is walked back to the hazard", False,
                   [far_stage(patch[1])]))
    phases.append((1, "the won runner is walked onto the crumbling ground", True,
                   [far_stage(patch[1]), cross_to(patch[1])]))
    phases.append((1, "the won runner is walked onto the finish a second time",
                   False, [far_stage(patch[1]), disc_win]))
    return phases, bypass_y, disc_win, disc_lost, disc_step_off


def solve_layout(markers, runner_at, patch, half, disc, disc_r, walk_z):
    """Re-derive everything the fixture derives, and refuse the level if any of it
    does not come out. Each fail() below is a HARNESS-PRECONDITION the fixture
    would otherwise report at run time as a non-graded exit."""
    # ---- the staging tables, so the drive this script validates is the drive the
    # fixture builds. Both legs must give the loss leg the same number of
    # crossings, because that number sets the length of the whole route list.
    finals = set()
    for rate, s in STAGING.items():
        for v in list(s["start"]) + [s["repaint_a"], s["repaint_b"]] + list(s["final"]):
            if not 1 <= v <= 6:
                fail(f"the {rate} Hz staging table wants to paint {v}, and the level "
                     f"promises every marker reads between 1 and 6")
        if s["repaint_a"] < 4:
            fail(f"the {rate} Hz staging table gives the crumbling ground only "
                 f"{s['repaint_a']} spending crossing(s) on the loss leg; the "
                 f"re-trigger rule needs at least four in two matched pairs")
        if s["repaint_b"] - 2 < 1:
            fail(f"the {rate} Hz staging table leaves the win leg on "
                 f"{s['repaint_b'] - 2} after two deaths, so it would be LOST before "
                 f"it ever reached the finish")
        # WHAT THE FINISH ASKS FOR -- ValidateStagingTable's four rules, in Python.
        holding = s["repaint_b"] - 2
        d0, d1, d2 = s["demand"]
        for v in s["demand"]:
            if not 1 <= v <= 6:
                fail(f"the {rate} Hz staging wants the finish to ask for {v}, and the "
                     f"level promises that number reads between 1 and 6")
        if d0 <= holding or d1 <= holding:
            fail(f"the {rate} Hz staging has the finish asking for {d0} and then {d1} "
                 f"while the win-leg runner arrives holding {holding}, so it would be "
                 f"let through the moment it walked on and nothing would ever gauge "
                 f"what the goal asks for")
        if d0 > s["repaint_b"]:
            fail(f"the {rate} Hz staging has the finish asking for {d0} while the "
                 f"win-leg runner's board reads {s['repaint_b']}, so reading the board "
                 f"instead of what is left would grade exactly like reading what is "
                 f"left and that wrong answer would go unnamed")
        if d2 > holding:
            fail(f"the {rate} Hz staging brings the finish down to {d2} while the "
                 f"win-leg runner is holding {holding}, so the goal never opens and "
                 f"the win leg is arithmetically unreachable")
        if d1 == d0 or d2 == d1:
            fail(f"the {rate} Hz staging moves the finish's number {d0} -> {d1} -> "
                 f"{d2}, and a move that changes nothing proves nothing about reading "
                 f"it at the moment it is needed")
        finals.add(s["repaint_a"])
    if len(finals) != 1:
        fail(f"the two legs end the loss run on different crossings {sorted(finals)}; "
             f"one route list cannot be validated for both")
    final_crossing = finals.pop()

    # ---- the markers ---------------------------------------------------------
    for i in range(len(markers)):
        for j in range(i + 1, len(markers)):
            d = dist(markers[i], markers[j])
            if d < MARKER_SPACING_FLOOR_UU:
                fail(f"two markers are {d:.0f} cm apart and standing 'on' one reaches "
                     f"{ON_MARKER_UU:.0f} cm, so going to the WRONG marker would grade "
                     f"exactly like going to the right one and the ownership rule "
                     f"would measure nothing (the fixture needs "
                     f"{MARKER_SPACING_FLOOR_UU:.0f})")
        to_patch = planar_dist_to_patch(markers[i], patch, half)
        if to_patch < TRIGGER_CLEAR_UU:
            fail(f"the marker at ({markers[i][0]:.0f},{markers[i][1]:.0f}) is only "
                 f"{to_patch:.0f} cm from the crumbling ground and the fixture needs "
                 f"{TRIGGER_CLEAR_UU:.0f}, or a runner put back on its marker would "
                 f"be claimed again at once")

    # ---- every runner on its OWN marker, and no two on the same one ----------
    # Resolved exactly as ResolveStaging resolves it: nearest marker at t=0, once,
    # never re-derived. The ORDER matters -- runner_at[0] is the one the level's own
    # rules put under the player's control, which is the loss leg the drive builds
    # its off-lane crossing around.
    owned = {}
    runner_marker = []
    for label, at in runner_at:
        d, idx = min((dist(at, m), i) for i, m in enumerate(markers))
        if d > 200.0:
            fail(f"{label} does not open the run standing on a marker (nearest is "
                 f"{d:.0f} cm away) and the level promises every runner opens on its "
                 f"own")
        if idx in owned:
            fail(f"{label} and {owned[idx]} both open the run on the marker at "
                 f"({markers[idx][0]:.0f},{markers[idx][1]:.0f}); whose marker is "
                 f"whose would not be decidable")
        owned[idx] = label
        runner_marker.append(idx)

    # ---- the patch has to cover every lane, and reach a runner's middle ------
    for label, at in runner_at:
        lane = abs(at[1] - patch[1])
        if lane + CAPSULE_RADIUS_UU > half[1]:
            fail(f"{label} runs on a lane {lane:.0f} cm off the crumbling ground's "
                 f"centre and the patch is only {half[1]:.0f} cm across from there, so "
                 f"that runner could walk straight past the hazard")
    if abs(walk_z - PATCH_BOX_CENTRE_Z) > half[2]:
        fail(f"a runner stands with its middle at z={walk_z:.0f} and the crumbling "
             f"ground's box is centred at z={PATCH_BOX_CENTRE_Z:.0f} reaching "
             f"{half[2]:.0f} cm; walking onto it would never be noticed at all")

    # ---- the two triggers must not fire together ----------------------------
    patch_to_disc = dist((patch[0] + half[0], patch[1]), disc) - disc_r
    if patch_to_disc < TRIGGER_CLEAR_UU:
        fail(f"the finish disc reaches to within {patch_to_disc:.0f} cm of the "
             f"crumbling ground and the fixture needs {TRIGGER_CLEAR_UU:.0f}, or the "
             f"two triggers would fire together")
    if disc_r <= 100.0:
        fail(f"DiscRadiusUu is {disc_r:.0f}; the fixture needs more than 100 cm or it "
             f"cannot tell what counts as standing on the finish")

    # ---- the off-lane crossing spot: DERIVED, never written down -------------
    off_y, margin, other_idx = solve_off_lane(markers, runner_marker[0], patch, half)
    if off_y is None or margin < OWNERSHIP_MARGIN_UU:
        fail(f"nowhere on the crumbling ground is more than {OWNERSHIP_MARGIN_UU:.0f} "
             f"cm nearer another runner's marker than the player's own (best is "
             f"{margin:.0f} cm). THE PLAYER'S MARKER MUST BE AN OUTER LANE: from the "
             f"middle one, every point on the patch is about as near its own marker as "
             f"anybody else's, 'go back to the nearest marker' would grade exactly "
             f"like 'go back to your own', and the ownership rule would measure "
             f"nothing")

    # ---- the whole drive, walked, against the floor and the hazard -----------
    phases, bypass_y, disc_win, disc_lost, disc_step_off = build_routes(
        markers[runner_marker[0]][1], markers[runner_marker[1]][1], off_y, patch,
        half, disc, disc_r, final_crossing)
    cursor = {0: runner_at[0][1], 1: runner_at[1][1]}
    for runner, label, is_cross, points in phases:
        frm = cursor[runner]
        left_patch = not in_patch_armed(frm, patch, half)
        for w, to in enumerate(points):
            cross_segment = is_cross and w == len(points) - 1
            for s in range(13):
                t = s / 12.0
                at = (frm[0] + (to[0] - frm[0]) * t, frm[1] + (to[1] - frm[1]) * t)
                if not (FLOOR_MIN[0] + ROUTE_FLOOR_MARGIN_UU < at[0]
                        < FLOOR_MAX[0] - ROUTE_FLOOR_MARGIN_UU
                        and FLOOR_MIN[1] + ROUTE_FLOOR_MARGIN_UU < at[1]
                        < FLOOR_MAX[1] - ROUTE_FLOOR_MARGIN_UU):
                    fail(f"the drive would walk '{label}' over "
                         f"({at[0]:.0f},{at[1]:.0f}) and the floor runs {FLOOR_MIN} to "
                         f"{FLOOR_MAX}; the fixture traces for ground under every step "
                         f"and refuses to start when there is none")
                if not in_patch_armed(at, patch, half):
                    left_patch = True
                elif not cross_segment and left_patch:
                    fail(f"the drive's route '{label}' walks back onto the crumbling "
                         f"ground at ({at[0]:.0f},{at[1]:.0f}), which would spend a "
                         f"life the staging never allowed for -- the win leg must go "
                         f"AROUND the patch, through the corridor at y={bypass_y:.0f}")
            frm = to
        cursor[runner] = points[-1]

    step_off_reach = dist(disc_step_off, disc) - disc_r
    if step_off_reach <= CAPSULE_RADIUS_UU:
        fail(f"the middle runner's step-off spot is only {step_off_reach:.0f} cm "
             f"outside the finish's reach and the fixture counts an arrival from "
             f"{CAPSULE_RADIUS_UU:.0f} cm outside it, so stepping off and back on "
             f"would never be a second arrival at all")

    log(f"layout solved: loss leg runs out on crossing {final_crossing}; off-lane "
        f"crossing at y={off_y:.0f}, {margin:.0f} cm nearer the marker at "
        f"({markers[other_idx][0]:.0f},{markers[other_idx][1]:.0f}) than its own "
        f"(floor {OWNERSHIP_MARGIN_UU:.0f}); bypass corridor at y={bypass_y:.0f}; "
        f"finish spots {disc_win} / {disc_lost}, step-off {disc_step_off}; "
        f"{len(phases)} driven phases, every "
        f"waypoint on the floor and no non-crossing segment on the hazard")
    return dict(off_lane_y=off_y, off_lane_margin=margin, bypass_y=bypass_y,
                final_crossing=final_crossing, phases=len(phases))


# ================================================================== authoring

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
    for cls_name in ("LifeMarkerActor", "LifeRunnerCharacter", "CrumbleGroundActor",
                     "FinishDiscActor", "LifeRunGameMode",
                     "LifeRunTerminalFunctionalTest"):
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
        # THE PROFILE, NOT JUST THE ENUM: on an earlier task set_collision_enabled
        # alone did not survive into the saved level. Paint that quietly blocks is
        # worse here than elsewhere -- the fixture's route validation refuses to
        # start when anything but the floor stands where a runner walks, and that
        # is a non-graded exit.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def paint_stripe(env, a, b, label, material, width=14.0, z=2.0):
    """A thin painted line on the floor from a to b. Never collides."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1.0:
        return
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    block(env, CUBE, unreal.Vector((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, z),
          unreal.Vector(length / 100.0, width / 100.0, 0.04), label, material, yaw=yaw)


def place(env, cls, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def add_tags(actor, *names):
    """APPEND, never replace. The class tag (LifeRunner / LifeMarker / ...) is set
    in the constructor and the fixture resolves by it; assigning a fresh list --
    which is what the obvious `set_editor_property("tags", [...])` does -- would
    drop it, and the fixture reports three runners of which some number 'no longer
    carry the marking the level gave them' as a FAILED submission."""
    have = [str(t) for t in actor.get_editor_property("tags")]
    for name in names:
        if name not in have:
            have.append(name)
    actor.set_editor_property("tags", [unreal.Name(n) for n in have])
    back = [str(t) for t in actor.get_editor_property("tags")]
    for name in names:
        if name not in back:
            fail(f"{actor.get_actor_label()} would not take the tag {name}")
    return back


def stand_height(env, cls, probe_at, label):
    """Where a runner's capsule centre has to sit so its feet are just clear of the
    floor -- MEASURED off a real placed instance, then thrown away.

    'A 96 cm half-height means z = 96' is arithmetic in a comment, which is not
    evidence: a change to InitCapsuleSize, a scaled root or a different pawn would
    all move it silently. A runner buried in the floor or floating above it is the
    same class of fault as the guard that never walked its round."""
    scratch = place(env, cls, unreal.Vector(probe_at[0], probe_at[1], 1000.0),
                    "__StandHeightProbe")
    origin, extent = scratch.get_actor_bounds(only_colliding_components=True)
    foot_offset = (origin.z - extent.z) - scratch.get_actor_location().z
    capsule = scratch.get_component_by_class(unreal.CapsuleComponent)
    half = None
    if capsule is not None:
        try:
            half = float(capsule.get_scaled_capsule_half_height())
        except Exception:
            half = None
    env["eas"].destroy_actor(scratch)
    if not -400.0 < foot_offset < -10.0:
        fail(f"{label}: the colliding hull of a runner reaches {-foot_offset:.1f} cm "
             f"below its own origin, which is not a standing pawn's shape; the level "
             f"cannot work out where to stand it")
    if half is not None and abs(half + foot_offset) > 12.0:
        fail(f"{label}: the runner's capsule half-height reads {half:.1f} cm and its "
             f"colliding hull reaches {-foot_offset:.1f} cm below its origin; those "
             f"disagree, so something other than the capsule decides where its feet "
             f"are and the placement below would be guesswork")
    log(f"{label}: hull reaches {-foot_offset:.1f} cm below the origin"
        + (f", capsule half-height {half:.1f}" if half is not None else ""))
    return -foot_offset


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0

    # ONE solid slab under the whole run: the drive walks a bypass corridor
    # 2,000 cm off the lanes and a crossing 1,342 cm the other way, and a runner
    # that walked off the edge would read as the submission moving it.
    floor = block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
                  unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR,
                  collide=True)
    f_origin, f_extent = floor.get_actor_bounds(only_colliding_components=True)
    floor_top_z = f_origin.z + f_extent.z
    if abs(floor_top_z) > 1.0:
        fail(f"the floor's top face measures z={floor_top_z:.1f} and everything in "
             f"this level (the patch's Z band, the runners' standing height, the "
             f"fixture's own WalkZ check) is derived from a top face at z=0")
    log(f"floor {span_x:.0f}x{span_y:.0f}, top face measured at z={floor_top_z:.1f}")

    # Stripes across the run, so distance and speed read by eye. Every third one
    # is bright, which makes 1,200 cm countable between two stills.
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        bright = (n % 3) == 0
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.10 if bright else 0.06, span_y / 100.0, 0.03),
              f"Stripe_{n:02d}", M_GLOW if bright else M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    # The three lanes and the bypass corridor, painted the length of the floor:
    # a reviewer can see that the three runners are on three lanes, that the patch
    # spans all three, and that there is a way round it.
    for idx, y in enumerate(LANE_Y):
        paint_stripe(env, (FLOOR_MIN[0] + 200.0, y), (FLOOR_MAX[0] - 200.0, y),
                     f"LaneLine_{idx}", M_STRIPE, width=20.0, z=2.5)
    log(f"{n} stripes every {STRIPE_EVERY:.0f} cm + three lane lines")

    # ---- the three markers, near to far ------------------------------------
    markers = []
    for idx, y in enumerate(LANE_Y):
        m = place(env, env["LifeMarkerActor"], unreal.Vector(MARKER_X, y, 0.0),
                  f"LifeMarker_{idx}")
        m.set_editor_property("painted_lives", PAINTED[idx])
        add_tags(m, "LifeMarker")
        markers.append(m)
    log(f"three markers at x={MARKER_X:.0f}, lanes {LANE_Y}, painted {PAINTED}")

    # ---- the crumbling ground, UNSCALED and square to the floor -------------
    patch = place(env, env["CrumbleGroundActor"],
                  unreal.Vector(PATCH_AT[0], PATCH_AT[1], 0.0), "CrumbleGround")
    add_tags(patch, "CrumbleGround")
    patch_box = None
    for comp in patch.get_components_by_class(unreal.BoxComponent):
        if comp.get_name() == "PatchVolume" or patch_box is None:
            patch_box = comp
    if patch_box is None:
        fail("the placed crumbling ground carries no box the fixture could read as "
             "the shape of the patch")
    # MEASURED off the placed component. The half-extents live in C++; a change
    # there has to move this level rather than silently unfit it.
    box_extent = patch_box.get_unscaled_box_extent()
    box_world = patch_box.get_world_location()
    patch_half = (float(box_extent.x), float(box_extent.y), float(box_extent.z))
    patch_scale = patch.get_actor_scale3d()
    if not (abs(patch_scale.x - 1.0) < 0.01 and abs(patch_scale.y - 1.0) < 0.01):
        fail(f"the crumbling ground is placed at scale {patch_scale}; the fixture "
             f"drives head-on across a patch that is UNSCALED and square to the floor")
    if abs(box_world.z - PATCH_BOX_CENTRE_Z) > 1.0:
        fail(f"the patch's box is centred at z={box_world.z:.1f} and this level's "
             f"arithmetic assumes {PATCH_BOX_CENTRE_Z:.1f}")
    log(f"crumbling ground at {PATCH_AT}, box half-extents {patch_half}, centred at "
        f"z={box_world.z:.1f}")

    # The way round the hazard, painted from the patch's MEASURED half-extent rather
    # than a number typed twice: this is the line the win leg walks so it can reach
    # the finish without spending a life it does not have, and a reviewer should be
    # able to see that such a way exists.
    bypass_y_paint = PATCH_AT[1] - (patch_half[1] + BYPASS_MARGIN_UU)
    paint_stripe(env, (FLOOR_MIN[0] + 200.0, bypass_y_paint),
                 (FLOOR_MAX[0] - 200.0, bypass_y_paint), "BypassLine", M_DARK,
                 width=20.0, z=2.5)
    log(f"bypass corridor painted at y={bypass_y_paint:.0f}")

    # ---- the finish disc ----------------------------------------------------
    disc = place(env, env["FinishDiscActor"],
                 unreal.Vector(DISC_AT[0], DISC_AT[1], 0.0), "FinishDisc")
    add_tags(disc, "FinishDisc")
    disc.set_editor_property("disc_radius_uu", DISC_RADIUS_UU)
    disc.set_editor_property("demanded_lives", DEMANDED)
    if int(disc.get_editor_property("demanded_lives")) != DEMANDED:
        fail(f"the finish disc would not take DemandedLives {DEMANDED}")
    staged_demands = {v for s in STAGING.values() for v in s["demand"]}
    if DEMANDED in staged_demands:
        fail(f"the finish is authored asking for {DEMANDED} and some leg stages that "
             f"same value ({sorted(staged_demands)}); a submission that mined the "
             f"committed map would then be right on one leg by luck")
    disc_r = float(disc.get_editor_property("disc_radius_uu"))
    if abs(disc_r - DISC_RADIUS_UU) > 0.5:
        fail(f"the finish disc would not take a radius: asked for "
             f"{DISC_RADIUS_UU:.0f}, it reads {disc_r:.0f}")
    sphere = disc.get_component_by_class(unreal.SphereComponent)
    if sphere is not None:
        reach = float(sphere.get_scaled_sphere_radius())
        # The painted disc and the reach are ONE number in C++ (OnConstruction). If
        # the construction script did not re-run, what a person walks onto and what
        # the fixture measures would be two different circles.
        if abs(reach - DISC_RADIUS_UU) > 1.0:
            fail(f"the finish disc reads DiscRadiusUu {disc_r:.0f} but its reach "
                 f"measures {reach:.0f}; the construction script did not follow the "
                 f"number, so what a person walks onto is not what the fixture reads")
        log(f"finish disc at {DISC_AT}, DiscRadiusUu {disc_r:.0f}, reach measured "
            f"{reach:.0f}")

    # ---- the runners -------------------------------------------------------
    # One is SPAWNED by the level's own rules onto the PlayerStart (that is the one
    # a person drives and the one the fixture drives); two are PLACED and told
    # apart by per-instance tags authored HERE, never in a constructor.
    hull = stand_height(env, env["LifeRunnerCharacter"], (mid_x, FLOOR_MAX[1] - 600.0),
                        "runner")
    stand_z = floor_top_z + FOOT_CLEARANCE_UU + hull
    runner_b = place(env, env["LifeRunnerCharacter"],
                     unreal.Vector(MARKER_X, LANE_Y[1], stand_z), "LifeRunner_Middle")
    add_tags(runner_b, "LifeRunner", "RunnerLaneB")
    runner_c = place(env, env["LifeRunnerCharacter"],
                     unreal.Vector(MARKER_X, LANE_Y[2], stand_z), "LifeRunner_Far")
    add_tags(runner_c, "LifeRunner", "RunnerLaneC")
    for runner in (runner_b, runner_c):
        # CORRECT FROM THE PLACED ACTOR, not from the probe. stand_height measures a
        # scratch pawn spawned in the air, where the skeletal mesh's bounds have not
        # grown to their standing size yet; a placed runner's colliding hull reaches
        # ~5 cm further down than the probe's did (96.0 measured in the air, 101.0
        # once placed). Trusting the probe's figure buries the feet. So: place, then
        # measure THIS actor and lift it by whatever it is actually short.
        origin, extent = runner.get_actor_bounds(only_colliding_components=True)
        shortfall = (floor_top_z + FOOT_CLEARANCE_UU) - (origin.z - extent.z)
        if shortfall > 0.0:
            here = runner.get_actor_location()
            runner.set_actor_location(
                unreal.Vector(here.x, here.y, here.z + shortfall), False, True)
            log(f"{runner.get_actor_label()}: lifted {shortfall:.1f} cm so its own "
                f"measured hull clears the floor")
        origin, extent = runner.get_actor_bounds(only_colliding_components=True)
        bottom = origin.z - extent.z
        if bottom < floor_top_z + 1.0:
            fail(f"{runner.get_actor_label()}'s collision reaches down to "
                 f"z={bottom:.1f}, at or below the floor's top face at "
                 f"z={floor_top_z:.1f}; it would begin every frame in contact with "
                 f"the floor")
        if bottom > floor_top_z + 40.0:
            fail(f"{runner.get_actor_label()} floats {bottom - floor_top_z:.1f} cm "
                 f"above the floor; it would drop when play begins, and the fixture "
                 f"resolves whose marker is whose from where a runner IS when the run "
                 f"opens")
    log(f"two runners placed at z={stand_z:.1f} on lanes {LANE_Y[1]:.0f} "
        f"(RunnerLaneB, the win leg) and {LANE_Y[2]:.0f} (RunnerLaneC, the "
        f"bystander); the third is spawned onto the PlayerStart")

    # THE PLAYER'S MARKER IS THE OUTER LANE, and that is load-bearing rather than
    # tidy: the off-lane crossing spot has to be at least 400 cm nearer another
    # runner's marker than the player's own, and no point on the patch satisfies
    # that from the middle lane.
    start = place(env, unreal.PlayerStart,
                  unreal.Vector(MARKER_X, LANE_Y[0], stand_z), "PlayerStart", yaw=0.0)
    log(f"PlayerStart on the OUTER lane {LANE_Y[0]:.0f} at z={stand_z:.1f}, facing "
        f"down the floor toward the hazard")

    # ---- SOLVE THE LEVEL, and refuse to save it if it does not come out -----
    marker_xy = [(MARKER_X, y) for y in LANE_Y]
    runner_xy = [("the near runner (spawned on the PlayerStart)", (MARKER_X, LANE_Y[0])),
                 ("the middle runner (RunnerLaneB)", (MARKER_X, LANE_Y[1])),
                 ("the far runner (RunnerLaneC)", (MARKER_X, LANE_Y[2]))]
    solved = solve_layout(marker_xy, runner_xy, PATCH_AT, patch_half, DISC_AT, disc_r,
                          stand_z)

    # ---- backdrop, landmarks, lighting -------------------------------------
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.5, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 300.0, FLOOR_MAX[0] - 300.0)):
        # Deliberately different sizes: a still from a moving camera has to be
        # distinguishable from a still from a static one.
        block(env, CYL, unreal.Vector(lx, FLOOR_MIN[1] + 400.0, 320.0),
              unreal.Vector(1.2 + idx * 1.1, 1.2 + idx * 1.1, 6.4), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-52.0, yaw=-118.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(FLOOR_MIN[0] + 200.0, FLOOR_MIN[1] + 200.0,
                                            1400.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")

    place(env, env["LifeRunTerminalFunctionalTest"],
          unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MAX[1] - 500.0, 200.0),
          "LifeRunTerminalFunctionalTest")

    # ---- the level's own rules ----------------------------------------------
    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["LifeRunGameMode"])
    log("world settings: default game mode = LifeRunGameMode")

    check_play_lane(env)
    read_back(env, marker_xy, patch_half, disc_r, stand_z, floor_top_z, solved)

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


def check_play_lane(env):
    """Refuse to save a level nobody can DRIVE.

    Naming a game mode above replaced GlobalDefaultGameMode, and BOTH halves of
    Enhanced Input live on the Blueprints it would otherwise have supplied: the
    four IA_* actions on BP_ThirdPersonCharacter's class defaults, and IMC_Default
    on BP_ThirdPersonPlayerController. A native pawn plus a game mode that forgets
    the controller grades BYTE-IDENTICALLY while being completely uncontrollable --
    five of six ThirdPerson maps once shipped exactly that way. The fixture asserts
    the same two halves as a HARNESS-PRECONDITION; this says so before saving."""
    gm_cdo = unreal.get_default_object(env["LifeRunGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass, so pressing Play would "
             "give a bare APlayerController, which carries no mapping context and "
             "never sees a keypress")
    if pawn_class is None or pawn_class.get_name() != "LifeRunnerCharacter":
        fail(f"the game mode's DefaultPawnClass is "
             f"{pawn_class.get_name() if pawn_class else 'unset'}; the level opens "
             f"with a RUNNER under the player's control, and the fixture refuses to "
             f"start otherwise")
    pawn_cdo = unreal.get_default_object(pawn_class)
    unbound = []
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if not pawn_cdo.get_editor_property(prop):
                unbound.append(prop)
        except Exception:
            unbound.append(prop)
    if unbound:
        fail(f"the runner has nothing bound to {', '.join(unbound)}; "
             f"AThirdPersonCharacter declares those four and assigns none, so the "
             f"level would grade identically while nobody could walk it")
    contexts = None
    try:
        contexts = unreal.get_default_object(pc_class).get_editor_property(
            "default_mapping_contexts")
    except Exception:
        contexts = None
    if not contexts:
        fail(f"{pc_class.get_name()} applies no input mapping context, so no key "
             f"reaches any of the four actions even with all of them set")
    log(f"play lane OK: controller={pc_class.get_name()} ({len(contexts)} mapping "
        f"context(s)) pawn={pawn_class.get_name()}")


def read_back(env, marker_xy, patch_half, disc_r, stand_z, floor_top_z, solved):
    """Read the level back off the actors as they are about to be SAVED, not as
    they were placed."""
    eas = env["eas"]
    actors = eas.get_all_level_actors()

    # Two runners are PLACED; the third arrives when the level's rules run, so the
    # authored count is two and the fixture's count is three.
    for tag, want in (("LifeMarker", 3), ("LifeRunner", 2), ("RunnerLaneB", 1),
                      ("RunnerLaneC", 1), ("CrumbleGround", 1), ("FinishDisc", 1)):
        got = [a for a in actors if a.actor_has_tag(tag)]
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}")

    placed = sorted([a for a in actors if a.actor_has_tag("LifeMarker")],
                    key=lambda a: a.get_actor_location().y)
    painted = [int(m.get_editor_property("painted_lives")) for m in placed]
    if len(set(painted)) != 3 or not all(1 <= v <= 6 for v in painted):
        fail(f"the markers read {painted} near-to-far; the level promises three "
             f"DIFFERENT numbers, each between 1 and 6")
    for m, (mx, my) in zip(placed, marker_xy):
        at = m.get_actor_location()
        if abs(at.x - mx) > 1.0 or abs(at.y - my) > 1.0:
            fail(f"a marker saved at ({at.x:.0f},{at.y:.0f}) and the layout was "
                 f"solved for ({mx:.0f},{my:.0f})")

    # THE TWO PLACED RUNNERS MUST BE TELLABLE APART, and by an INSTANCE tag rather
    # than by class or by order: the fixture asks for RunnerLaneB and RunnerLaneC
    # by name and cannot say which one it is driving without them.
    lanes = {}
    for a in actors:
        if not a.actor_has_tag("LifeRunner"):
            continue
        which = [t for t in ("RunnerLaneB", "RunnerLaneC") if a.actor_has_tag(t)]
        if len(which) != 1:
            fail(f"{a.get_actor_label()} carries {which or 'no'} lane mark; each "
                 f"placed runner needs exactly one of RunnerLaneB / RunnerLaneC")
        lanes[which[0]] = a.get_actor_location()
    if abs(lanes["RunnerLaneB"].y - 0.0) > 1.0:
        fail(f"the win-leg runner (RunnerLaneB) saved on lane "
             f"{lanes['RunnerLaneB'].y:.0f}; the layout was solved with it in the "
             f"middle, and its own marker's Y is what the drive lines up on")
    if abs(lanes["RunnerLaneC"].y - 1100.0) > 1.0:
        fail(f"the bystander (RunnerLaneC) saved on lane {lanes['RunnerLaneC'].y:.0f} "
             f"rather than the far one")

    finish = [a for a in actors if a.actor_has_tag("FinishDisc")][0]
    demanded = int(finish.get_editor_property("demanded_lives"))
    if demanded != DEMANDED or not 1 <= demanded <= 6:
        fail(f"the finish saved asking for {demanded}; the level authors {DEMANDED} "
             f"and the fixture refuses a goal number outside 1..6")

    starts = [a for a in actors if a.get_class().get_name() == "PlayerStart"]
    if len(starts) != 1:
        fail(f"{len(starts)} PlayerStart(s); the level's rules spawn exactly one "
             f"runner and the fixture reads whose marker it is from where it lands")
    sat = starts[0].get_actor_location()
    if abs(sat.y - marker_xy[0][1]) > 1.0:
        fail(f"the PlayerStart saved on lane {sat.y:.0f} rather than the outer one at "
             f"{marker_xy[0][1]:.0f}; the off-lane crossing spot's "
             f"{solved['off_lane_margin']:.0f} cm ownership margin was solved for the "
             f"outer lane and the middle one cannot satisfy it at all")
    if abs(sat.z - stand_z) > 1.0:
        fail(f"the PlayerStart saved at z={sat.z:.1f} and the placed runners stand at "
             f"z={stand_z:.1f}; the fixture takes the patch's Z band and its whole "
             f"drive height from where the PLAYER's capsule centre is")

    lit = [a for a in actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    fixtures = [a for a in actors
                if a.get_class().get_name() == "LifeRunTerminalFunctionalTest"]
    if len(fixtures) != 1:
        fail(f"{len(fixtures)} functional test(s) placed, expected exactly one")

    # NOTHING BUT THE FLOOR MAY BLOCK A RUNNER. The prompt promises the level can
    # never push anybody, the fixture's stay-put watch would read a shove as the
    # submission moving a runner, and its route validation refuses to start when
    # anything solid stands where the drive walks.
    for actor in actors:
        if actor.actor_has_tag("LifeRunner") or actor.get_actor_label() == "Floor":
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            if comp.get_collision_enabled() in (
                    unreal.CollisionEnabled.QUERY_AND_PHYSICS,
                    unreal.CollisionEnabled.PHYSICS_ONLY):
                fail(f"{actor.get_actor_label()}'s {comp.get_name()} still answers "
                     f"physics; only the floor may stop or push a runner")
            if comp.get_collision_enabled() == unreal.CollisionEnabled.QUERY_ONLY:
                # The two triggers are query-only ON PURPOSE -- they notice bodies
                # and block nothing. Anything else query-only is paint that would
                # be read as an obstacle.
                if not (actor.actor_has_tag("CrumbleGround")
                        or actor.actor_has_tag("FinishDisc")):
                    fail(f"{actor.get_actor_label()}'s {comp.get_name()} answers "
                         f"queries; the only query-only shapes in this level are the "
                         f"crumbling ground and the finish disc")

    log(f"read back: markers {painted} near-to-far at x={marker_xy[0][0]:.0f}; patch "
        f"half-extents {patch_half}; disc reach {disc_r:.0f} asking for {demanded}; "
        f"runners at "
        f"z={stand_z:.1f} over a floor topping out at z={floor_top_z:.1f}; loss leg "
        f"runs out on crossing {solved['final_crossing']}; off-lane crossing at "
        f"y={solved['off_lane_y']:.0f} with {solved['off_lane_margin']:.0f} cm of "
        f"ownership margin; bypass corridor at y={solved['bypass_y']:.0f}")


main()
