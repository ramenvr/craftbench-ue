"""Author a discrimination variant for kp-spawn-level-actors. ONE LEG PER BOOT.

    CB_VARIANT=floor-left-unscaled UnrealEditor-Cmd.exe <uproject>
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash -stdout

  floor-left-unscaled/  floor keeps the spawn-default (1,1,1) instead of (20,20,1)
                        -> fails ONLY floor_scale_exact
  one-enemy-too-many/   the three required enemies plus a fourth Enemy_4
                        -> fails ONLY no_extra_enemy_labels

no_extra_enemy_labels is the only OVER-delivery gate in this task, and an `empty` leg
can never reach one -- it is always too few. Without this leg that requirement has no
evidence.

ONE LEG PER BOOT (a second new_level at the same path fails all session). Each leg
calls the reference's builders verbatim, then perturbs one thing.
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

MARK = "KPSPAWN-VARIANTS"


def log(msg):
    print("%s %s" % (MARK, msg))


def die(msg):
    print("%s-ERROR %s" % (MARK, msg))
    sys.stdout.flush()
    raise SystemExit(1)


try:
    R = CBV.load_reference_helpers(REFERENCE_AUTHOR, [
        "EAL", "_spawn", "_assign_mesh", "_set_label", "_load_engine_mesh",
        "_level_subsystem_call", "_vec3", "build_floor", "build_start",
        "build_bounds", "build_enemies", "grade_in_process", "harvest",
        "cleanup", "LEVEL_ASSET", "REFERENCE_DIR", "SPHERE_MESH_PKG",
        "SPHERE_MESH_OBJ"])
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


# --- the two deltas, applied AFTER the reference builders have run -----------

def revert_floor_scale():
    """Undo the floor's scale. The grader's own detail names this exact value:
    `FLOOR_SCALE_WRONG got=... expected=(20.0, 20.0, 1.0) ... spawn_default=(1, 1, 1)`."""
    floor = actor_by_label("Floor")
    floor.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    got = R["_vec3"](floor.get_actor_scale3d())
    if not all(abs(c - 1.0) < 1e-4 for c in got):
        die("delta did not stick: floor scale reads %s" % (got,))
    log("delta applied: Floor scale -> (1,1,1) (spawn default)")


def add_fourth_enemy():
    """Add one extra `Enemy_`-prefixed actor. The three required enemies are
    untouched and still exactly correct — only the over-delivery gate should fire."""
    sphere = R["_load_engine_mesh"](R["SPHERE_MESH_PKG"], R["SPHERE_MESH_OBJ"])
    extra = R["_spawn"](unreal.StaticMeshActor, (0.0, -300.0, 110.0))
    R["_assign_mesh"](extra, sphere, R["SPHERE_MESH_OBJ"], "Enemy_4")
    R["_set_label"](extra, "Enemy_4")
    if extra.get_actor_label() != "Enemy_4":
        die("delta did not stick: extra enemy label reads %r"
            % extra.get_actor_label())
    log("delta applied: added a fourth enemy labelled Enemy_4")


#: (variant dir, delta fn, the ONE check it must fail, its credited substring)
VARIANTS = (
    ("floor-left-unscaled", revert_floor_scale, "floor_scale_exact",
     "FLOOR_SCALE_WRONG got="),
    ("one-enemy-too-many", add_fourth_enemy, "no_extra_enemy_labels",
     "ENEMY_EXTRA_LABELS extras="),
)


def build_leg(delta):
    """Exactly the reference's construction, then one perturbation."""
    if not R["_level_subsystem_call"]("new_level", LEVEL_ASSET):
        die("new_level(%s) reported failure" % LEVEL_ASSET)
    R["build_floor"]()
    R["build_start"]()
    R["build_bounds"]()
    R["build_enemies"]()
    delta()
    if not R["_level_subsystem_call"]("save_current_level"):
        die("save_current_level reported failure")


def main():
    if EAL.does_asset_exist(LEVEL_ASSET):
        die("substrate already carries %s — clean via git first" % LEVEL_ASSET)

    # One leg per boot for a LEVEL task — see the module docstring.
    only = os.environ.get("CB_VARIANT", "").strip()
    legs = [v for v in VARIANTS if not only or v[0] == only]
    if only and not legs:
        die("CB_VARIANT=%r matches no leg (have: %s)"
            % (only, ", ".join(v[0] for v in VARIANTS)))
    if not only and len(VARIANTS) > 1:
        log("WARNING authoring %d level legs in ONE boot; the second new_level "
            "will fail. Set CB_VARIANT to author one at a time."
            % len(VARIANTS))

    harvested, refused = [], []
    for variant, delta, target, substring in legs:
        log("=== %s ===" % variant)
        build_leg(delta)

        vector = R["grade_in_process"]()
        passed, total = CBV.score(vector)
        fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
        log("%s graded %d/%d fails=%s" % (variant, passed, total, fails))
        for cid in fails:
            log("  FAIL-DETAIL %s %s" % (cid, vector[cid][1]))

        ok, why = CBV.acceptance(vector, target, substring)
        if ok:
            dest = os.path.join(TASK_DIR, "discrimination", variant)
            try:
                CBV.call_with_rebound_globals(R, "harvest", REFERENCE_DIR=dest)
                harvested.append(variant)
                log("HARVESTED %s -> %s" % (variant, dest))
                log("OK %s %s" % (variant, why))
            except Exception as e:  # noqa: BLE001 - harvest failure is a refusal
                refused.append(variant)
                log("DO NOT HARVEST %s — harvest failed: %r" % (variant, e))
        else:
            refused.append(variant)
            log("DO NOT HARVEST %s — %s" % (variant, why))

        R["cleanup"]()

    log("SUMMARY harvested=%s refused=%s" % (harvested, refused))
    log("DONE" if not refused else "DONE-WITH-REFUSALS")


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
