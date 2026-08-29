"""Author a discrimination variant for t1-playable-level-bootstrap. ONE LEG PER BOOT.

    CB_VARIANT=floor-beside-the-start UnrealEditor-Cmd.exe <uproject>
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash -stdout

  floor-beside-the-start/  the floor EXISTS (floor_candidate_present passes) but is
                           moved sideways -> fails ONLY floor_under_player_start
  two-player-starts/       a second PlayerStart -> fails player_start_exactly_one
                           AND, by design, floor_under_player_start (declared)

The first leg separates "a floor exists" from "a floor is under you" -- on this task,
the difference between spawning on ground and falling through the world.

The cascade on the second is traced, not discovered: _start_check returns None for any
count != 1, and the floor check then fans out carrying the START's token -- so a row
crediting the floor check at a floor substring would be wrong about this leg.

default_pawn_is_pawn_subclass has NO leg because it looks unreachable:
DefaultPawnClass is a TSubclassOf<APawn>, so UE type-checks the assignment and the
editor's class picker filters identically.

ONE LEG PER BOOT (a second new_level at the same path fails all session).
"""
import os
import sys

import unreal  # noqa: F401 - required by the exec'd reference source

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(TASK_DIR, "..", "..", ".."))
REFERENCE_AUTHOR = os.path.join(_HERE, "author_reference.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "authoring"))
import cb_variant_lib as CBV  # noqa: E402

MARK = "BOOT-VARIANTS"


def log(msg):
    print("%s %s" % (MARK, msg))


def die(msg):
    print("%s-ERROR %s" % (MARK, msg))
    sys.stdout.flush()
    raise SystemExit(1)


try:
    R = CBV.load_reference_helpers(REFERENCE_AUTHOR, [
        "EAL", "set_prop", "read_prop", "_spawn", "_set_label", "_vec3",
        "_level_subsystem_call", "_create_blueprint", "_generated_class",
        "_save_asset", "author_blueprints", "build_floor", "build_start",
        "wire_world_settings", "grade_in_process", "harvest", "cleanup",
        "LEVEL_ASSET", "REFERENCE_DIR", "PKG_DIR", "START_LOCATION",
        "_default_object", "GM_ASSET"])
except CBV.AuthoringError as e:
    die(str(e))

EAL = R["EAL"]
LEVEL_ASSET = R["LEVEL_ASSET"]


def actor_by_label(label):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if sub is None:
        die("no EditorActorSubsystem available")
    hits = [a for a in (sub.get_all_level_actors() or [])
            if a is not None and a.get_actor_label() == label]
    if len(hits) != 1:
        die("expected exactly one actor labelled %r, found %d" % (label, len(hits)))
    return hits[0]


# --- leg 1: move the floor out from under the spawn marker -------------------

def displace_floor():
    """The floor still exists, is still collidable, still has its mesh and scale —
    it is simply somewhere else. The grader's band is "10.0 above to 500.0 below"
    the marker, and the floor is 20x20 units of cube scale, so the shift has to
    clear its own footprint: 20 * 100 = 2000 units of half-extent at scale 20.
    12000 is comfortably clear of any reasonable trace radius."""
    floor = actor_by_label("Floor")
    loc = floor.get_actor_location()
    floor.set_actor_location(
        unreal.Vector(loc.x + 12000.0, loc.y, loc.z), False, False)
    got = floor.get_actor_location()
    if abs(got.x - (loc.x + 12000.0)) > 1.0:
        die("delta did not stick: floor x reads %s" % got.x)
    log("delta applied: Floor moved to x=%.1f (was %.1f); nothing collidable "
        "remains under the marker at %s" % (got.x, loc.x, R["START_LOCATION"]))


# --- leg 2: a second spawn marker ------------------------------------------

def add_second_start():
    """Place a SECOND PlayerStart. Everything else — ruleset, body, floor, the
    first marker — is exactly the reference's.

    This replaced an earlier `body-is-not-a-pawn` leg that CANNOT BE AUTHORED, and
    the reason is worth keeping: `DefaultPawnClass` is a `TSubclassOf<APawn>`, so UE
    type-checks the assignment and refuses a plain Actor outright —
    `NativizeClass: Cannot nativize 'BlueprintGeneratedClass' as 'Class' (allowed
    Class type: 'Pawn')`. See the module docstring for what that implies about the
    `default_pawn_is_pawn_subclass` gate.

    Cascade, traced and declared: `_start_check` returns None whenever the count is
    not exactly 1 (grader :615-620), and the floor check then does
    `_fanout(results, ("floor_under_player_start",), start_fail)` (:695-697). So this
    leg fails EXACTLY two checks, and the second is not a surprise — it is the
    grader's own design, the same shape as kp-anim-track-bake's flat-track leg.
    """
    cls = getattr(unreal, "PlayerStart", None)
    if cls is None:
        die("PlayerStart is not exposed to Python")
    extra = R["_spawn"](cls, (600.0, 0.0, 110.0))
    R["_set_label"](extra, "Start2")
    if extra.get_actor_label() != "Start2":
        die("delta did not stick: second start label reads %r"
            % extra.get_actor_label())
    log("delta applied: a SECOND PlayerStart placed at (600, 0, 110)")


#: variant dir -> (delta fn, target check, credited substring, declared cascades)
VARIANTS = {
    "floor-beside-the-start": (
        displace_floor, "floor_under_player_start",
        "BOOT_FLOOR_NOT_UNDER_START start=", ()),
    "two-player-starts": (
        add_second_start, "player_start_exactly_one",
        "BOOT_START_COUNT_WRONG count=", ("floor_under_player_start",)),
}


def main():
    want = os.environ.get("CB_VARIANT", "").strip()
    if want not in VARIANTS:
        die("set CB_VARIANT to one of: %s (got %r) — this task authors ONE leg per "
            "boot; see the module docstring" % (", ".join(sorted(VARIANTS)), want))
    delta, target, substring, cascades = VARIANTS[want]
    log("=== %s ===" % want)

    if EAL.does_asset_exist(LEVEL_ASSET):
        die("substrate already carries %s — clean via git first" % LEVEL_ASSET)

    gm_cls = R["author_blueprints"]()
    if not R["_level_subsystem_call"]("new_level", LEVEL_ASSET):
        die("new_level(%s) reported failure" % LEVEL_ASSET)
    R["build_floor"]()
    R["build_start"]()
    R["wire_world_settings"](gm_cls)
    # leg 2's delta needs the ruleset class (DefaultPawnClass lives on its CDO);
    # leg 1's does not. Dispatch on arity rather than duplicating the build.
    import inspect
    if len(inspect.signature(delta).parameters) == 1:
        delta(gm_cls)
    else:
        delta()
    if not R["_level_subsystem_call"]("save_current_level"):
        die("save_current_level reported failure")

    vector = R["grade_in_process"]()
    passed, total = CBV.score(vector)
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    log("%s graded %d/%d fails=%s" % (want, passed, total, fails))
    for cid in sorted(vector):
        ok_c, detail = vector[cid]
        log("  %s %s %s" % ("PASS" if ok_c else "FAIL", cid, detail))

    ok, why = CBV.acceptance(vector, target, substring, cascades=cascades)
    if not ok:
        log("DO NOT HARVEST %s — %s" % (want, why))
    else:
        dest = os.path.join(TASK_DIR, "discrimination", want)
        try:
            CBV.call_with_rebound_globals(R, "harvest", REFERENCE_DIR=dest)
            log("HARVESTED %s -> %s" % (want, dest))
            log("OK %s %s" % (want, why))
        except Exception as e:  # noqa: BLE001 - harvest failure is a refusal
            log("DO NOT HARVEST %s — harvest failed: %r" % (want, e))

    R["cleanup"]()


def _cleanup_after_failure():
    """Best-effort substrate cleanup on the failure path."""
    try:
        R["cleanup"]()
        print("%s cleaned up after failure" % MARK)
    except Exception:  # noqa: BLE001
        print("%s CLEANUP FAILED — check the substrate by hand" % MARK)



try:
    main()
except SystemExit:
    # A die() — ours or the reference author's — raises SystemExit. Re-raising it
    # WITHOUT cleaning left authored assets in the substrate, and an untracked
    # directory there makes a certifying sweep certify NOTHING (the cert key covers
    # the substrate tree and identities are computed before the loop). Measured
    # 2026-08-18: one failed leg left Content/Tasks/<id>/ behind and the next
    # sweep had to be killed and restarted. So clean, THEN re-raise.
    try:
        _cleanup_after_failure()
    finally:
        raise
except Exception as e:  # noqa: BLE001
    import traceback
    print("%s-ERROR %s: %s" % (MARK, type(e).__name__, e))
    print(traceback.format_exc()[-1200:])
    try:
        R["cleanup"]()
        print("%s cleaned up after failure" % MARK)
    except Exception:  # noqa: BLE001
        print("%s CLEANUP ALSO FAILED — check the substrate by hand" % MARK)
sys.stdout.flush()
