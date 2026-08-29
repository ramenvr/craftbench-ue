"""Author a discrimination variant for kp-anim-track-bake. ONE LEG PER BOOT.

    CB_VARIANT=track-is-flat UnrealEditor-Cmd.exe <uproject>
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash -stdout

  track-covers-only-the-start/  varies, but keys sit in the opening tenth
                                -> fails ONLY new_track_spans_timeline
  track-is-flat/                spans the clip, every key one value
                                -> fails new_track_varies AND, by the grader's
                                   design, new_track_spans_timeline

THE CASCADE IS DELIBERATE: check 5 emits ANIMBAKE_NO_VARYING_TRACK (check 4 failed)
whenever check 4 fails, so no leg can isolate check 4 alone and refusing that shape
would mean never probing it. track-is-flat declares the cascade and is credited at
check 4's own token; acceptance still demands the failure set equal
{target} | cascades exactly.

Check 2 (baseline_state_intact) has NO leg: its only route is
ANIMBAKE_LENGTH_CHANGED, and changing an AnimSequence's length from Python is not
proven here. Recorded rather than faked with a substitute leg.

ONE LEG PER BOOT: this task MODIFIES a baseline asset in place, so after the bytes
are restored the editor still holds the baked state. The scratch law runs in a
finally -- stage, bake, grade, harvest, restore byte-verified -- so the substrate
keeps the unmodified duplicate the grader's pins were measured from.
"""
import os
import sys

import unreal  # noqa: F401 - required by the exec'd reference source

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(TASK_DIR, "..", "..", ".."))
REFERENCE_AUTHOR = os.path.join(_HERE, "author_reference.py")
GRADER = os.path.join(REPO_ROOT, "tools", "verify-single", "introspect",
                      "kp_anim_track_bake.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "authoring"))
import cb_variant_lib as CBV  # noqa: E402

MARK = "KPBAKE-VARIANTS"


def log(msg):
    print("%s %s" % (MARK, msg))


def die(msg):
    print("%s-ERROR %s" % (MARK, msg))
    sys.stdout.flush()
    raise SystemExit(1)


# author_reference.py here uses the `if __name__ == "__main__":` tail shape, so the
# loader leaves it inert without stripping anything.
try:
    R = CBV.load_reference_helpers(REFERENCE_AUTHOR, [
        "ensure_baseline", "print_baseline_pins", "stage_baseline_copy",
        "restore_baseline", "_float_track_type", "_sequence_length",
        "_asset_fs_path", "_content_fs_dir", "TRACK_NAME", "ASSET_PATH",
        "TASK_ID", "CONTENT_DIR"])
except CBV.AuthoringError as e:
    die(str(e))

TRACK_NAME = R["TRACK_NAME"]
ASSET_PATH = R["ASSET_PATH"]
TASK_ID = R["TASK_ID"]


def add_keys(seq, times, values):
    """Key the float track, using whichever AnimationLibrary route exists —
    the same two-route fallback the reference author uses."""
    names = [str(n) for n in (unreal.AnimationLibrary.get_animation_curve_names(
        seq, R["_float_track_type"]()) or [])]
    if TRACK_NAME not in names:
        unreal.AnimationLibrary.add_curve(seq, TRACK_NAME)
    fn_many = getattr(unreal.AnimationLibrary, "add_float_curve_keys", None)
    if fn_many is not None:
        fn_many(seq, TRACK_NAME, list(times), list(values))
    else:
        for t, v in zip(times, values):
            unreal.AnimationLibrary.add_float_curve_key(seq, TRACK_NAME, t, v)
    if not unreal.EditorAssetLibrary.save_loaded_asset(seq):
        die("variant save failed")


# --- the two legs ------------------------------------------------------------

def bake_span_short(seq):
    """Varies, but only across the opening tenth.

    The grader's window is `[<= SPAN_FRACTION*len .. >= (1-SPAN_FRACTION)*len]`
    with SPAN_FRACTION = 0.1, i.e. `[<=0.150 .. >=1.350]` for the pinned 1.5s clip.
    First key at 0.0 satisfies the opening bound on purpose, so the leg fails on the
    CLOSING bound alone and check 4 (varies) still passes: 0.0 -> 1.0 is a real
    change."""
    length = float(R["_sequence_length"](seq))
    end = 0.1 * length
    add_keys(seq, [0.0, end], [0.0, 1.0])
    log("baked keys=[0.0->0.0, %.4f->1.0] of a %.4fs clip" % (end, length))


def bake_flat(seq):
    """Spans the whole clip, but every key holds the same value."""
    length = float(R["_sequence_length"](seq))
    add_keys(seq, [0.0, length], [0.0, 0.0])
    log("baked keys=[0.0->0.0, %.4f->0.0] (flat) of a %.4fs clip" % (length, length))


#: variant dir -> (bake fn, target check, credited substring, declared cascades)
VARIANTS = {
    "track-covers-only-the-start": (
        bake_span_short, "new_track_spans_timeline",
        "ANIMBAKE_TRACK_SPAN_SHORT need=", ()),
    "track-is-flat": (
        bake_flat, "new_track_varies",
        "ANIMBAKE_ALL_NEW_TRACKS_FLAT", ("new_track_spans_timeline",)),
}


def main():
    want = os.environ.get("CB_VARIANT", "").strip()
    if want not in VARIANTS:
        die("set CB_VARIANT to one of: %s (got %r) — this task authors ONE leg "
            "per boot; see the module docstring"
            % (", ".join(sorted(VARIANTS)), want))
    bake, target, substring, cascades = VARIANTS[want]
    log("=== %s ===" % want)

    seq = R["ensure_baseline"]()
    names, length = R["print_baseline_pins"](seq)
    if names:
        log("NOTE baseline already carries float tracks %s — the grader pins "
            "BASELINE_CURVE_NAMES, so this is only a surprise if it disagrees" % names)
    staged = R["stage_baseline_copy"]()

    try:
        bake(seq)

        vector, err = CBV.grade_vector(GRADER)
        if err:
            die("self-grade unavailable: %s" % err)
        passed, total = CBV.score(vector)
        fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
        log("%s graded %d/%d fails=%s" % (want, passed, total, fails))
        for cid in sorted(vector):
            ok_c, detail = vector[cid]
            log("  %s %s %s" % ("PASS" if ok_c else "FAIL", cid, detail))

        ok, why = CBV.acceptance(vector, target, substring, cascades=cascades)
        if not ok:
            log("DO NOT HARVEST %s — %s" % (want, why))
            return
        # Derive the source dir from _asset_fs_path(), NOT _content_fs_dir():
        # the latter is the project's Content ROOT, so passing it made the harvest
        # look for .../Content/AS_TaskWalk.uasset and refuse (measured 2026-08-18,
        # after the leg had already graded 4/5 correctly). _asset_fs_path() is the
        # path restore_baseline() itself trusts, so it cannot drift from reality.
        dst = CBV.harvest(TASK_DIR, want, TASK_ID, ("AS_TaskWalk",),
                          os.path.dirname(R["_asset_fs_path"]()))
        log("HARVESTED %s -> %s" % (want, dst))
        log("OK %s %s" % (want, why))
    finally:
        # The scratch law: the substrate must keep the UNMODIFIED duplicate, since
        # the grader's pinned baseline was measured from it. Restored even when the
        # leg is refused or the bake raises.
        R["restore_baseline"](staged)


try:
    main()
except SystemExit:
    raise
except Exception as e:  # noqa: BLE001
    import traceback
    print("%s-ERROR %s: %s" % (MARK, type(e).__name__, e))
    print(traceback.format_exc()[-1200:])
sys.stdout.flush()
