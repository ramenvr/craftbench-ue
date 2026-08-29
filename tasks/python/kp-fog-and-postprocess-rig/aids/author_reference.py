"""Author the kp-fog-and-postprocess-rig REFERENCE deliverable (a saved level).

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline, so the flow is: create the level at the
real content path -> spawn + label + configure the three actors -> save ->
GRADE IT IN-PROCESS with the real verifier script (which re-loads the level,
exercising THE map-load pattern this task introduces) -> harvest every file
the save produced into reference/ -> delete it all from the substrate. The
substrate ends with no /Game/Tasks/kp-fog-and-postprocess-rig content at all.

Validation is the actual grader, not a re-implementation: the authored level
is scored by tools/verify-single/introspect/kp_fog_and_postprocess_rig.py
(stdout captured, CRAFTBENCH-INTROSPECT-JSON block parsed) and harvested ONLY
on a clean 14/14.

FAIL-CLOSED throughout (the author_all_assets.py pattern): every property
write probes plausible UE 5.8 pythonized spellings and DIES on the first
property no spelling can set - a wrong guess aborts before harvest, it can
never ship a half-set level. Winning spellings print as KPFOG-SPELLING lines
(fills the notes.md calibration record).

UE 5.8 cautions honoured (the ones that burned earlier authoring lanes):
  * No SCS socket attachment anywhere in this design (cannot be set from
    Python) - level actors only, no Blueprint hierarchy.
  * No renames: every asset is created at its final path, so no registry
    tombstones.
  * No pin import_text: no graph authoring in this task.
  * Property names are underscore-folded by the Python codegen and bools drop
    their leading 'b' - hence the spelling probes.
  * The post-process settings struct is READ, mutated, then WRITTEN BACK via
    set_editor_property (a struct read may be a copy; in-place mutation
    without write-back is the known inert-settings trap this task grades).

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPFOG-SPELLING <property>=<winning name>
  KPFOG-VECTOR reference passed=<n>/14 fails=[ids]
  KPFOG-HARVEST <relpath>
  KPFOG-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-fog-and-postprocess-rig"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
LEVEL_NAME = "L_FogRig"
LEVEL_ASSET = "%s/%s" % (PKG_DIR, LEVEL_NAME)

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
# TASK_DIR from _HERE, not a hardcoded basket: survives tree moves.
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_fog_and_postprocess_rig.py")

# Substrate-relative prefixes the save may write into; everything found under
# them (for this task id) is harvested into reference/ at the same relpath.
HARVEST_PREFIXES = (
    os.path.join("Content", "Tasks", TASK_ID),
    os.path.join("Content", "__ExternalActors__", "Tasks", TASK_ID),
    os.path.join("Content", "__ExternalObjects__", "Tasks", TASK_ID),
)
CLEANUP_GAME_PATHS = (
    PKG_DIR,
    "/Game/__ExternalActors__/Tasks/%s" % TASK_ID,
    "/Game/__ExternalObjects__/Tasks/%s" % TASK_ID,
)

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("KPFOG-ERROR %s" % msg)
    raise SystemExit(msg)


# --------------------------------------------------------------------------- #
# property setting with spelling probes (mirrors the grader's _read_property)  #
# --------------------------------------------------------------------------- #

_SPELLING_LOG = {}


def set_prop(obj, value, *names):
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
            if names[0] not in _SPELLING_LOG:
                _SPELLING_LOG[names[0]] = name
                print("KPFOG-SPELLING %s=%s" % (names[0], name))
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable spelling among %s: %r" % (names, last))


def get_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    die("no readable spelling among %s: %r" % (names, last))


def _cls(name):
    cls = getattr(unreal, name, None)
    if cls is None:
        die("unreal.%s is not exposed to Python" % name)
    return cls


# --------------------------------------------------------------------------- #
# subsystem routes (each with the legacy EditorLevelLibrary fallback)          #
# --------------------------------------------------------------------------- #

def _level_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception:  # noqa: BLE001
        return None


def _actor_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:  # noqa: BLE001
        return None


def new_level(asset_path):
    les = _level_subsystem()
    if les is not None and getattr(les, "new_level", None) is not None:
        if bool(les.new_level(asset_path)):
            return
        die("LevelEditorSubsystem.new_level(%s) returned False" % asset_path)
    ell = getattr(unreal, "EditorLevelLibrary", None)
    if ell is not None and getattr(ell, "new_level", None) is not None:
        if bool(ell.new_level(asset_path)):
            return
        die("EditorLevelLibrary.new_level(%s) returned False" % asset_path)
    die("no new_level route available")


def spawn(cls, label):
    eas = _actor_subsystem()
    actor = None
    if eas is not None and getattr(eas, "spawn_actor_from_class", None) is not None:
        actor = eas.spawn_actor_from_class(cls, unreal.Vector(0.0, 0.0, 0.0))
    if actor is None:
        ell = getattr(unreal, "EditorLevelLibrary", None)
        if ell is not None and getattr(ell, "spawn_actor_from_class", None) is not None:
            actor = ell.spawn_actor_from_class(cls, unreal.Vector(0.0, 0.0, 0.0))
    if actor is None:
        die("spawn_actor_from_class(%s) returned None" % cls)
    actor.set_actor_label(label)
    got = str(actor.get_actor_label())
    if got != label:
        die("actor label read back %r, wanted %r (case-sensitive gate)"
            % (got, label))
    return actor


def save_level():
    les = _level_subsystem()
    if les is not None and getattr(les, "save_current_level", None) is not None:
        if bool(les.save_current_level()):
            return
        die("LevelEditorSubsystem.save_current_level returned False")
    ell = getattr(unreal, "EditorLevelLibrary", None)
    if ell is not None and getattr(ell, "save_current_level", None) is not None:
        if bool(ell.save_current_level()):
            return
        die("EditorLevelLibrary.save_current_level returned False")
    die("no save_current_level route available")


def open_neutral_map():
    """Leave the graded level so it can be deleted. Never saves anything."""
    utils = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    if utils is not None and getattr(utils, "new_blank_map", None) is not None:
        try:
            if utils.new_blank_map(False) is not None:
                return
        except Exception:  # noqa: BLE001 - fall through to the engine map
            pass
    if utils is not None and getattr(utils, "load_map", None) is not None:
        if utils.load_map("/Engine/Maps/Entry") is not None:
            return
    die("could not leave the authored level (no neutral-map route)")


# --------------------------------------------------------------------------- #
# the reference recipe - the EXACT values task.md's verifier specification     #
# gates on (targets, not band edges)                                           #
# --------------------------------------------------------------------------- #

def build_fog():
    actor = spawn(_cls("ExponentialHeightFog"), "Fog")
    comps = list(actor.get_components_by_class(
        _cls("ExponentialHeightFogComponent")) or [])
    if not comps:
        die("Fog actor carries no ExponentialHeightFogComponent")
    comp = comps[0]
    set_prop(comp, 0.03, "fog_density", "FogDensity")
    set_prop(comp, 0.15, "fog_height_falloff", "FogHeightFalloff")
    set_prop(comp, unreal.LinearColor(0.02, 0.04, 0.10, 1.0),
             "fog_inscattering_luminance", "FogInscatteringLuminance",
             "fog_inscattering_color", "FogInscatteringColor")


def build_ppv():
    actor = spawn(_cls("PostProcessVolume"), "Mood")
    set_prop(actor, True, "unbound", "bUnbound", "b_unbound")
    # READ the settings struct, mutate, WRITE BACK - a read may be a copy, and
    # mutating a copy without the write-back is exactly the inert-settings
    # trap the task grades (and the source sheet's step 2 warns about).
    settings = get_prop(actor, "settings", "Settings")
    if settings is None:
        die("post-process settings struct read back None")
    set_prop(settings, True, "override_bloom_intensity",
             "bOverride_BloomIntensity", "b_override_bloom_intensity")
    set_prop(settings, 1.8, "bloom_intensity", "BloomIntensity")
    set_prop(settings, True, "override_vignette_intensity",
             "bOverride_VignetteIntensity", "b_override_vignette_intensity")
    set_prop(settings, 0.6, "vignette_intensity", "VignetteIntensity")
    set_prop(settings, True, "override_color_saturation",
             "bOverride_ColorSaturation", "b_override_color_saturation")
    set_prop(settings, unreal.Vector4(0.85, 0.88, 0.95, 1.0),
             "color_saturation", "ColorSaturation")
    set_prop(settings, True, "override_auto_exposure_bias",
             "bOverride_AutoExposureBias", "b_override_auto_exposure_bias")
    set_prop(settings, -0.5, "auto_exposure_bias", "AutoExposureBias")
    set_prop(actor, settings, "settings", "Settings")
    # Read-back gate: the write-back must have stuck.
    check = get_prop(actor, "settings", "Settings")
    got = float(get_prop(check, "bloom_intensity", "BloomIntensity"))
    if abs(got - 1.8) > 1e-4:
        die("settings write-back did not stick (bloom read back %s)" % got)


def build_skylight():
    actor = spawn(_cls("SkyLight"), "Ambient")
    comps = list(actor.get_components_by_class(_cls("SkyLightComponent")) or [])
    if not comps:
        die("Ambient actor carries no SkyLightComponent")
    set_prop(comps[0], 0.2, "intensity", "Intensity")


# --------------------------------------------------------------------------- #
# grade in-process with the REAL verifier                                      #
# --------------------------------------------------------------------------- #

def grade_in_process():
    """Run the real grader; return {check_id: (passed, detail)}."""
    spec = importlib.util.spec_from_file_location("kpfog_grader", GRADER)
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
        die("grader output unparseable: %r; raw=%r" % (e, out[-500:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


# --------------------------------------------------------------------------- #
# harvest + cleanup                                                            #
# --------------------------------------------------------------------------- #

def harvest():
    copied = 0
    for prefix in HARVEST_PREFIXES:
        src_root = os.path.join(SUBSTRATE, prefix)
        if not os.path.isdir(src_root):
            continue
        for dirpath, _dirs, files in os.walk(src_root):
            for name in files:
                src = os.path.join(dirpath, name)
                rel = os.path.relpath(src, SUBSTRATE)
                dst = os.path.join(REFERENCE_DIR, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print("KPFOG-HARVEST %s" % rel.replace(os.sep, "/"))
                copied += 1
    if copied == 0:
        die("save produced no files under any harvest prefix")
    umap = os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID,
                        LEVEL_NAME + ".umap")
    if not os.path.isfile(umap):
        die("harvest is missing the level file itself: %s" % umap)


def cleanup():
    """Remove every trace of the authored level from the substrate."""
    open_neutral_map()
    for game_path in CLEANUP_GAME_PATHS:
        try:
            if EAL.does_directory_exist(game_path):
                EAL.delete_directory(game_path)
        except Exception:  # noqa: BLE001 - the disk sweep below is the gate
            pass
    for prefix in HARVEST_PREFIXES:
        path = os.path.join(SUBSTRATE, prefix)
        if os.path.isdir(path):
            shutil.rmtree(path)
    # The gate: DISK is the truth (the next editor session rescans from
    # disk). A remnant registry entry in THIS about-to-exit session is a
    # stale in-memory row, not a leftover - measured 2026-08-11: parking +
    # rmtree left the entry until exit and the die() here threw away an
    # already-validated harvest. Files on disk still die.
    if EAL.does_asset_exist(LEVEL_ASSET):
        print("KPFOG-WARN stale in-memory registry entry for %s (disk is "
              "clean; the next session rescans)" % LEVEL_ASSET)
    for prefix in HARVEST_PREFIXES:
        if os.path.isdir(os.path.join(SUBSTRATE, prefix)):
            die("substrate dir survived cleanup: %s" % prefix)


def main():
    if EAL.does_asset_exist(LEVEL_ASSET):
        die("substrate already carries %s - refusing to overwrite" % LEVEL_ASSET)
    for prefix in HARVEST_PREFIXES:
        if os.path.isdir(os.path.join(SUBSTRATE, prefix)):
            die("substrate already carries files under %s - clean up first"
                % prefix)

    new_level(LEVEL_ASSET)
    build_fog()
    build_ppv()
    build_skylight()
    save_level()

    vector = grade_in_process()
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPFOG-VECTOR reference passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 14:
        die("grader emitted %d checks, expected 14" % len(vector))
    if fails:
        for cid in fails:
            print("KPFOG-FAIL-DETAIL %s %s" % (cid, vector[cid][1]))
        die("reference did not grade 14/14; NOT harvesting")

    harvest()
    cleanup()
    print("KPFOG-DONE")


main()
