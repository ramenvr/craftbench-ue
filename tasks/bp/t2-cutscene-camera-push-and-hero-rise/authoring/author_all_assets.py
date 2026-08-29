"""Author ALL six t2-cutscene-camera-push-and-hero-rise assets (reference +
5 variants), with the real grader run in-process at every state.

Run headless on the ThirdPerson substrate project:
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline (notes.md section 1) - flow per asset:
build the LevelSequence at the real content path -> save -> grade in-process
with tools/verify-single/introspect/cutscene_camera_push_and_hero_rise.py ->
harvest the .uasset into the tasks/ tree -> delete from the substrate. The
substrate ends without the task folder at all.

Timing law (notes.md section 2 gotchas): tick resolution stays at the 24000fps
default; display rate is set to 24fps. ALL keys are authored in TICKS:
0.0s=0, 0.5s=12000, 3.0s=72000, 6.0s=144000. The camera cut is exactly ONE
bounded section spanning the full range.

Contracts (notes.md section 2 + section 4):
  reference               -> 12/12
  timeline-header-only    -> header right, zero tracks/bindings
  camera-possessed-from-level -> camera binding is a POSSESSABLE (bound to a
                             live CineCameraActor spawned in the editor world)
  camera-static-single-key-> camera Location.X has ONE key at -500
  hero-ramps-whole-shot   -> EvalHero Location.Z ramps 0->200 over all 6s
  fade-out-not-in         -> fade keys 0.0s->0.0, 0.5s->1.0 (fade TO black)

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  CUTSCENE-VECTOR <asset> passed=n/12 fails=[ids]
  CUTSCENE-ASSET-OK <asset> -> <file>
  CUTSCENE-DONE      success marker; absent = FAILED
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "t2-cutscene-camera-push-and-hero-rise"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
ASSET_NAME = "SEQ_EvalCutscene"
ASSET_PATH = "%s/%s" % (PKG_DIR, ASSET_NAME)

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
# TASK_DIR from the script location (tasks/<basket>/<id>/authoring/), not a
# hardcoded basket: survives tree moves.
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
SUBSTRATE_FILE = os.path.join(
    REPO, "UE-projects", "ThirdPerson", "Content", "Tasks", TASK_ID,
    ASSET_NAME + ".uasset")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "cutscene_camera_push_and_hero_rise.py")

EAL = unreal.EditorAssetLibrary
# Channel add_key() interprets FrameNumber in DISPLAY-RATE frames by default
# (SequenceTimeUnit.DISPLAY_RATE) - first attempt keyed "ticks" and the fade
# landed at t=500s. At 24fps: 0.5s=12, 3s=72, 6s=144.
S0, S0_5, S3, S6 = 0, 12, 72, 144


def die(msg):
    print("CUTSCENE-ERROR %s" % msg)
    raise SystemExit(msg)


def new_sequence():
    if EAL.does_asset_exist(ASSET_PATH):
        if not EAL.delete_asset(ASSET_PATH):
            die("could not delete existing sequence")
    factory = unreal.LevelSequenceFactoryNew()
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(ASSET_NAME, PKG_DIR, unreal.LevelSequence, factory)
    if seq is None:
        die("create_asset failed")
    seq.set_display_rate(unreal.FrameRate(24, 1))
    seq.set_playback_start_seconds(0.0)
    seq.set_playback_end_seconds(6.0)
    return seq


def keyed_channel(section, index, keys):
    """Key channel[index] of a section with [(tick, value), ...]."""
    chans = section.get_all_channels()
    if index >= len(chans):
        die("channel index %d out of %d" % (index, len(chans)))
    ch = chans[index]
    for tick, value in keys:
        ch.add_key(unreal.FrameNumber(tick), float(value))
    return ch


def transform_track(binding, channel_index, keys, tick_keys=False):
    # The actor transform track class is MovieScene3DTransformTrack (the
    # grader matches on that exact class name). tick_keys=True keys in
    # TICK_RESOLUTION units for times that are not integer display frames
    # (the snap variant's 2.9s/3.1s = ticks 69600/74400 at 24000fps).
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_start_frame_seconds(0.0)
    section.set_end_frame_seconds(6.0)
    if tick_keys:
        chans = section.get_all_channels()
        for tick, value in keys:
            chans[channel_index].add_key(
                unreal.FrameNumber(tick), float(value), 0.0,
                unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    else:
        keyed_channel(section, channel_index, keys)
    return track


def camera_cut(seq, cam_binding):
    track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    section = track.add_section()
    section.set_start_frame_seconds(0.0)
    section.set_end_frame_seconds(6.0)
    # UE 5.8 spelling: MovieSceneSequenceExtensions.GetBindingID (ScriptMethod)
    binding_id = seq.get_binding_id(cam_binding)
    section.set_camera_binding_id(binding_id)
    return track


def fade_track(seq, keys):
    track = seq.add_track(unreal.MovieSceneFadeTrack)
    section = track.add_section()
    keyed_channel(section, 0, keys)
    return track


def build(kind):
    seq = new_sequence()
    if kind == "timeline-header-only":
        return seq
    # camera binding
    if kind == "camera-possessed-from-level":
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        cam_actor = eas.spawn_actor_from_class(unreal.CineCameraActor,
                                               unreal.Vector(0, 0, 10000))
        cam = seq.add_possessable(cam_actor)
    else:
        cam = seq.add_spawnable_from_class(unreal.CineCameraActor)
    # camera push-in (Location.X channel index 0)
    if kind == "camera-static-single-key":
        transform_track(cam, 0, [(S0, -500.0)])
    elif kind == "camera-snaps-instead-of-pushing":
        # still 0..2.9s, snap 350uu in 0.2s, still 3.1..6s (ticks @24000fps)
        transform_track(cam, 0, [(0, -500.0), (69600, -500.0),
                                 (74400, -150.0), (144000, -150.0)],
                        tick_keys=True)
    else:
        transform_track(cam, 0, [(S0, -500.0), (S6, -150.0)])
    camera_cut(seq, cam)
    # hero binding
    hero = seq.add_spawnable_from_class(unreal.StaticMeshActor)
    hero.set_name("EvalHero")
    tmpl = None
    try:
        tmpl = hero.get_object_template()
        smc = tmpl.static_mesh_component
        smc.set_editor_property(
            "static_mesh", EAL.load_asset("/Engine/BasicShapes/Cube"))
    except Exception as e:  # noqa: BLE001 - display-only nicety, not graded
        print("CUTSCENE-WARN hero template cube not set: %r" % (e,))
    if kind == "hero-ramps-whole-shot":
        transform_track(hero, 2, [(S0, 0.0), (S6, 200.0)])
    else:
        transform_track(hero, 2, [(S0, 0.0), (S3, 200.0), (S6, 200.0)])
    # fade
    if kind == "fade-out-not-in":
        fade_track(seq, [(S0, 0.0), (S0_5, 1.0)])
    else:
        fade_track(seq, [(S0, 1.0), (S0_5, 0.0)])
    return seq


def grade():
    spec = importlib.util.spec_from_file_location("cutscene_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    try:
        payload = out.split(mod.INTROSPECT_JSON_START)[1].split(
            mod.INTROSPECT_JSON_END)[0]
        checks = json.loads(payload.strip())["checks"]
    except Exception as e:  # noqa: BLE001
        die("grader output unparseable: %r; tail=%r" % (e, out[-400:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


HEADER_OK = ["sequence_asset_exists", "sequence_display_rate_24fps",
             "sequence_spans_six_seconds"]

ASSETS = [
    ("reference", "reference", [], None),  # must_fail empty => all must pass
    ("timeline-header-only", "discrimination/timeline-header-only",
     ["camera_cut_track_present"], HEADER_OK),
    ("camera-possessed-from-level",
     "discrimination/camera-possessed-from-level",
     ["camera_spawned_by_sequence"], HEADER_OK + ["camera_cut_track_present"]),
    ("camera-static-single-key", "discrimination/camera-static-single-key",
     ["camera_pushes_in_over_full_shot"],
     HEADER_OK + ["camera_spawned_by_sequence", "hero_rises_then_holds"]),
    ("camera-snaps-instead-of-pushing",
     "discrimination/camera-snaps-instead-of-pushing",
     ["camera_pushes_in_over_full_shot"],
     HEADER_OK + ["camera_spawned_by_sequence", "hero_rises_then_holds",
                  "fade_in_from_black", "camera_cut_covers_whole_shot"]),
    ("hero-ramps-whole-shot", "discrimination/hero-ramps-whole-shot",
     ["hero_rises_then_holds"],
     HEADER_OK + ["camera_pushes_in_over_full_shot", "fade_in_from_black"]),
    ("fade-out-not-in", "discrimination/fade-out-not-in",
     ["fade_in_from_black"],
     HEADER_OK + ["hero_rises_then_holds", "camera_pushes_in_over_full_shot"]),
]


def main():
    if EAL.does_asset_exist(ASSET_PATH):
        die("substrate already carries %s" % ASSET_PATH)
    for kind, target, must_fail, must_pass in ASSETS:
        seq = build(kind)
        if not EAL.save_asset(ASSET_PATH, only_if_is_dirty=False):
            die("%s: save failed" % kind)
        vector = grade()
        fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
        print("CUTSCENE-VECTOR %s passed=%d/%d fails=%s"
              % (kind, len(vector) - len(fails), len(vector), fails))
        if kind == "reference":
            if fails:
                for cid in fails:
                    print("CUTSCENE-DETAIL %s :: %s" % (cid, vector[cid][1][:160]))
                die("reference must pass 12/12")
        else:
            for cid in must_fail:
                if vector.get(cid, (True, ""))[0]:
                    die("%s: %s should FAIL but passed" % (kind, cid))
            for cid in (must_pass or []):
                if not vector.get(cid, (False, "missing"))[0]:
                    print("CUTSCENE-DETAIL %s :: %s"
                          % (cid, vector.get(cid, (None, "?"))[1][:160]))
                    die("%s: %s should PASS but did not" % (kind, cid))
        if not os.path.isfile(SUBSTRATE_FILE):
            die("%s: saved asset not on disk" % kind)
        dst = os.path.join(TASK_DIR, target.replace("/", os.sep), "Content",
                           "Tasks", TASK_ID, ASSET_NAME + ".uasset")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(SUBSTRATE_FILE, dst)
        if not EAL.delete_asset(ASSET_PATH):
            die("%s: cleanup delete failed" % kind)
        print("CUTSCENE-ASSET-OK %s -> %s" % (kind, dst))
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception:  # noqa: BLE001
        pass
    print("CUTSCENE-DONE")


main()
