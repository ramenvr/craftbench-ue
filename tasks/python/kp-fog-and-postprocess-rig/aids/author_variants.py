"""Author a discrimination variant for kp-fog-and-postprocess-rig. ONE LEG PER BOOT.

    CB_VARIANT=ppv-left-bounded UnrealEditor-Cmd.exe <uproject>
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash -stdout

  ppv-left-bounded/     mood volume built correctly but left BOUNDED
                        -> fails ONLY ppv_is_unbound
  fog-falloff-default/  height falloff left at the engine default 0.2 (target 0.15)
                        -> fails ONLY fog_falloff_exact

ONE LEG PER BOOT: a second new_level at the same path fails for the rest of the
session, because deleting a level can leave a stale in-memory registry row.

Each leg calls the reference's own build_fog/build_ppv/build_skylight verbatim and
only then reverts ONE property, so nothing else can differ. The harvest is the
reference author's own three-prefix walk, retargeted via
cb_variant_lib.call_with_rebound_globals -- it must carry the One-File-Per-Actor
sidecars as well as the .umap, or the level loads with no actors.
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

MARK = "KPFOG-VARIANTS"


def log(msg):
    print("%s %s" % (MARK, msg))


def die(msg):
    print("%s-ERROR %s" % (MARK, msg))
    sys.stdout.flush()
    raise SystemExit(1)


try:
    R = CBV.load_reference_helpers(REFERENCE_AUTHOR, [
        "EAL", "set_prop", "get_prop", "_cls", "_actor_subsystem", "new_level",
        "spawn", "save_level", "open_neutral_map", "build_fog", "build_ppv",
        "build_skylight", "grade_in_process", "harvest", "cleanup",
        "TASK_ID", "LEVEL_ASSET", "LEVEL_NAME", "REFERENCE_DIR"])
except CBV.AuthoringError as e:
    die(str(e))

EAL = R["EAL"]
TASK_ID = R["TASK_ID"]
LEVEL_ASSET = R["LEVEL_ASSET"]


def find_actor(cls_name):
    """The one level actor of that class. Identity by class here is correct: this
    is OUR freshly-built level, not a submission being graded."""
    sub = R["_actor_subsystem"]()
    if sub is None:
        die("no EditorActorSubsystem available")
    cls = R["_cls"](cls_name)
    hits = [a for a in (sub.get_all_level_actors() or [])
            if a is not None and isinstance(a, cls)]
    if len(hits) != 1:
        die("expected exactly one %s in the authored level, found %d"
            % (cls_name, len(hits)))
    return hits[0]


# --- the two deltas, each applied AFTER the reference builders have run ------

def revert_ppv_to_bounded():
    """Undo `bUnbound` — the engine default is False (the grader's own detail
    text says so: `PPV_NOT_UNBOUND unbound=%s engine_default=False`)."""
    ppv = find_actor("PostProcessVolume")
    R["set_prop"](ppv, False, "unbound", "bUnbound", "b_unbound")
    got = bool(R["get_prop"](ppv, "unbound", "bUnbound", "b_unbound"))
    if got:
        die("delta did not stick: PPV still reads unbound=True")
    log("delta applied: PPV unbound -> False")


def revert_fog_falloff():
    """Undo the falloff — engine default 0.2, task target 0.15 (again, named in
    the grader's own detail: `target=0.15 engine_default=0.2`)."""
    comp = None
    fog = find_actor("ExponentialHeightFog")
    comps = list(fog.get_components_by_class(
        R["_cls"]("ExponentialHeightFogComponent")) or [])
    if not comps:
        die("fog actor carries no ExponentialHeightFogComponent")
    comp = comps[0]
    R["set_prop"](comp, 0.2, "fog_height_falloff", "FogHeightFalloff")
    got = float(R["get_prop"](comp, "fog_height_falloff", "FogHeightFalloff"))
    if abs(got - 0.2) > 1e-6:
        die("delta did not stick: falloff reads %s" % got)
    log("delta applied: fog height falloff -> 0.2 (engine default)")


#: (variant dir, delta fn, the ONE check it must fail, its credited substring)
VARIANTS = (
    ("ppv-left-bounded", revert_ppv_to_bounded, "ppv_is_unbound",
     "PPV_NOT_UNBOUND unbound="),
    ("fog-falloff-default", revert_fog_falloff, "fog_falloff_exact",
     "FOG_FALLOFF_OFF_TARGET falloff="),
)


def build_leg(delta):
    """Exactly the reference's construction, then one property reverted."""
    R["new_level"](LEVEL_ASSET)
    R["build_fog"]()
    R["build_ppv"]()
    R["build_skylight"]()
    delta()
    R["save_level"]()


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
            # Retarget the reference author's proven three-prefix walk (it also
            # carries the OFPA sidecars) at this variant's directory.
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
