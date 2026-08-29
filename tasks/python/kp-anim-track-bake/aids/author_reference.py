"""Authoring aid - builds the kp-anim-track-bake baseline AND reference.

VERIFIER-SIDE tooling (never shipped to agents, never graded itself). Runs
INSIDE the worktree ThirdPerson editor:

    UnrealEditor-Cmd.exe <worktree>/UE-projects/ThirdPerson/ThirdPerson.uproject
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash
        -stdout -FullStdOutLogOutput

What one run does, in order:

  1. duplicate the stock unarmed walk cycle to
     /Game/Tasks/kp-anim-track-bake/AS_TaskWalk (skipped if present), save.
  2. print the BASELINE pin values (KPBAKE-BASELINE marker): float-track
     names + clip length. These are pinned into
     tools/verify-single/introspect/kp_anim_track_bake.py
     (BASELINE_CURVE_NAMES / BASELINE_LENGTH) in the SAME commit as the
     binaries - the re-pin law; the grader fails closed until then.
  3. stage a filesystem copy of the UNMODIFIED saved .uasset (the substrate
     baseline that gets committed).
  4. bake the reference track (WalkPhase: 0.0 -> 0.0, length -> 1.0), save.
  5. harvest the MODIFIED .uasset into ../reference/Content/Tasks/... .
  6. restore the staged baseline bytes over the substrate path (the
     substrate must keep the UNMODIFIED duplicate - scratch law), verify
     byte-equality, KPBAKE-RESTORED.
  7. self-grade IN-PROCESS against the real grader - full 5/5 only when
     the pins are already in (second run); on the sentinel it expects
     exactly the ANIMBAKE_BASELINE_UNPINNED failure and reports
     KPBAKE-PIN-NEEDED instead of dying.

Markers: KPBAKE-VECTOR, KPBAKE-BASELINE, KPBAKE-PIN-NEEDED,
KPBAKE-SELFGRADE, KPBAKE-HARVEST, KPBAKE-RESTORED, KPBAKE-DONE (full
success only), KPBAKE-ERROR (fail-closed).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil

import unreal

TASK_ID = "kp-anim-track-bake"
CONTENT_DIR = "/Game/Tasks/kp-anim-track-bake"
ASSET_PATH = CONTENT_DIR + "/AS_TaskWalk"
STOCK_WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"

TRACK_NAME = "WalkPhase"

AIDS_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(AIDS_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TASK_DIR)))
GRADER = os.path.join(REPO_ROOT, "tools", "verify-single", "introspect",
                      "kp_anim_track_bake.py")


def log(msg):
    print(msg)
    try:
        unreal.log(msg)
    except Exception:  # noqa: BLE001
        pass


def die(msg):
    log("KPBAKE-ERROR " + msg)
    raise SystemExit(msg)


def vector(step):
    log("KPBAKE-VECTOR " + step)


def _content_fs_dir():
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001
        full = os.path.abspath(str(raw))
    return str(full)


def _asset_fs_path():
    return os.path.join(_content_fs_dir(), "Tasks", TASK_ID,
                        "AS_TaskWalk.uasset")


def _float_track_type():
    enum = getattr(unreal, "RawCurveTrackTypes", None)
    for spelling in ("RCT_FLOAT", "RCT_Float"):
        value = getattr(enum, spelling, None) if enum is not None else None
        if value is not None:
            return value
    die("RawCurveTrackTypes spelling unresolved")


def _sequence_length(seq):
    fn = getattr(unreal.AnimationLibrary, "get_sequence_length", None)
    if fn is not None:
        try:
            out = fn(seq)
            if isinstance(out, (tuple, list)):
                out = out[-1]
            return float(out)
        except Exception:  # noqa: BLE001
            pass
    for name in ("sequence_length", "SequenceLength"):
        try:
            return float(seq.get_editor_property(name))
        except Exception:  # noqa: BLE001
            continue
    die("sequence length unreadable")


def ensure_baseline():
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        vector("baseline-exists " + ASSET_PATH)
    else:
        if not unreal.EditorAssetLibrary.does_asset_exist(STOCK_WALK):
            die("stock walk missing at %s" % STOCK_WALK)
        if not unreal.EditorAssetLibrary.duplicate_asset(STOCK_WALK,
                                                         ASSET_PATH):
            die("duplicate_asset failed %s -> %s" % (STOCK_WALK, ASSET_PATH))
        vector("baseline-duplicated " + ASSET_PATH)
    seq = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if seq is None:
        die("baseline unloadable after duplicate")
    if not unreal.EditorAssetLibrary.save_loaded_asset(seq):
        die("baseline save failed")
    return seq


def print_baseline_pins(seq):
    names = [str(n) for n in (unreal.AnimationLibrary
                              .get_animation_curve_names(
                                  seq, _float_track_type()) or [])]
    length = _sequence_length(seq)
    log("KPBAKE-BASELINE names=%s length=%.6f" % (json.dumps(names), length))
    return names, length


def stage_baseline_copy():
    src = _asset_fs_path()
    if not os.path.isfile(src):
        die("saved baseline not on disk at %s" % src)
    dst = src + ".baseline-stage"
    shutil.copy2(src, dst)
    vector("baseline-staged " + dst)
    return dst


def bake_reference(seq):
    names = [str(n) for n in (unreal.AnimationLibrary
                              .get_animation_curve_names(
                                  seq, _float_track_type()) or [])]
    length = _sequence_length(seq)
    if TRACK_NAME not in names:
        unreal.AnimationLibrary.add_curve(seq, TRACK_NAME)
        vector("track-added " + TRACK_NAME)
    fn_many = getattr(unreal.AnimationLibrary, "add_float_curve_keys", None)
    if fn_many is not None:
        fn_many(seq, TRACK_NAME, [0.0, length], [0.0, 1.0])
    else:
        unreal.AnimationLibrary.add_float_curve_key(seq, TRACK_NAME, 0.0, 0.0)
        unreal.AnimationLibrary.add_float_curve_key(seq, TRACK_NAME,
                                                    length, 1.0)
    if not unreal.EditorAssetLibrary.save_loaded_asset(seq):
        die("reference save failed")
    vector("reference-baked keys=[0.0->0.0, %.4f->1.0]" % length)


def harvest_reference():
    src = _asset_fs_path()
    dst_dir = os.path.join(TASK_DIR, "reference", "Content", "Tasks", TASK_ID)
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dst_dir, "AS_TaskWalk.uasset"))
    log("KPBAKE-HARVEST reference AS_TaskWalk.uasset")


def restore_baseline(staged):
    src = _asset_fs_path()
    shutil.copy2(staged, src)
    with open(staged, "rb") as a, open(src, "rb") as b:
        if a.read() != b.read():
            die("restore verify failed - substrate baseline corrupt")
    os.remove(staged)
    log("KPBAKE-RESTORED substrate baseline bytes verified")


def self_grade():
    if not os.path.isfile(GRADER):
        die("grader not found at %s" % GRADER)
    src = io.open(GRADER, encoding="utf-8").read()
    buf = io.StringIO()
    ns = {"__name__": "__cb_selfgrade__", "__file__": GRADER}
    with contextlib.redirect_stdout(buf):
        exec(compile(src, GRADER, "exec"), ns)  # noqa: S102 - verifier-owned
        ns["main"]()
    out = buf.getvalue()
    m = re.search(r"CRAFTBENCH-INTROSPECT-JSON-START\s*\n(.*?)\n\s*"
                  r"CRAFTBENCH-INTROSPECT-JSON-END", out, re.S)
    if m is None:
        die("self-grade produced no verdict block")
    checks = json.loads(m.group(1))["checks"]
    passed = sum(1 for c in checks if c["passed"])
    log("KPBAKE-SELFGRADE %d/%d" % (passed, len(checks)))
    for c in checks:
        log("  %s %s %s" % ("PASS" if c["passed"] else "FAIL",
                            c["id"], c["detail"]))
    unpinned = [c for c in checks
                if not c["passed"]
                and "ANIMBAKE_BASELINE_UNPINNED" in c["detail"]]
    if unpinned and passed == len(checks) - 1:
        log("KPBAKE-PIN-NEEDED pin BASELINE_* from the KPBAKE-BASELINE "
            "line, commit with the binaries, re-run this aid")
        return False
    if passed != len(checks) or len(checks) != 5:
        die("self-grade not 5/5 (and not the expected unpinned shape)")
    return True


def main():
    # NOTE self-grade runs against the SUBSTRATE asset in its reference
    # (baked) state - i.e. BETWEEN bake and restore - which is exactly the
    # state the graded workdir reproduces when the reference overlays the
    # baseline.
    seq = ensure_baseline()
    print_baseline_pins(seq)
    staged = stage_baseline_copy()
    bake_reference(seq)
    graded_ok = self_grade()
    harvest_reference()
    restore_baseline(staged)
    if graded_ok:
        log("KPBAKE-DONE")
    else:
        log("KPBAKE-DONE-PENDING-PINS (artifacts harvested; pin + re-run "
            "for the 5/5 certificate)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        die("unhandled %r" % e)
