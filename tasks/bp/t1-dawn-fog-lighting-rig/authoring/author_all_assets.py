"""Author ALL six t1-dawn-fog-lighting-rig assets (reference + 5 variants).

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline (notes.md section 1), so the flow per
asset is: build the Blueprint at the real content path -> compile -> save ->
GRADE IT IN-PROCESS with the real verifier script -> harvest the .uasset file
into the tasks/ tree -> delete it from the substrate. The substrate ends with
no /Game/Tasks/t1-dawn-fog-lighting-rig folder at all, which the runner
verifies via git status.

Validation is the actual grader, not a re-implementation: each authored asset
is scored by tools/verify-single/introspect/dawn_fog_lighting_rig.py (stdout
captured, CRAFTBENCH-INTROSPECT-JSON block parsed) and harvested ONLY if its
vector matches the expectation for that asset:
  reference                 -> 14/14, every check passes
  three-lights-no-atmosphere-> rig_sky_atmosphere_present FAILS, presence of
                               the other three + compile still pass
  named-not-typed           -> rig_sun_light_present FAILS (Sun is a
                               PointLightComponent), other presence passes
  overhead-noon-sun         -> sun_angle_is_low_dawn FAILS (pitch -60)
  default-white-sun         -> sun_color_is_warm FAILS (colour left white)
  engine-default-fog        -> fog_density_is_dense FAILS (plus the two other
                               fog gates - every fog property is default)
Secondary fan-out failures on a variant (e.g. sun_* reads on the point-light
Sun) are RECORDED but not asserted either way; `cb discriminate` against
MATRIX.md stays the final authority.

Property-spelling uncertainty (notes.md section 5) is handled by trying each
plausible pythonized name and FAILING CLOSED - a wrong guess aborts that
asset before harvest, it can never ship a half-set Blueprint. The winning
spellings are printed as DAWNFOG-SPELLING lines to fill the section 5 record.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  DAWNFOG-SPELLING <property>=<winning name>
  DAWNFOG-VECTOR <asset> passed=<n>/14 fails=[ids]
  DAWNFOG-ASSET-OK <asset>
  DAWNFOG-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "t1-dawn-fog-lighting-rig"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
ASSET_NAME = "BP_DawnLighting"
ASSET_PATH = "%s/%s" % (PKG_DIR, ASSET_NAME)

# Repo layout, derived from this file living at tasks/<basket>/<id>/authoring/.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
# TASK_DIR from _HERE, not a hardcoded basket: survives tree moves.
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
SUBSTRATE_FILE = os.path.join(
    REPO, "UE-projects", "ThirdPerson", "Content", "Tasks", TASK_ID,
    ASSET_NAME + ".uasset")
GRADER = os.path.join(
    REPO, "tools", "verify-single", "introspect", "dawn_fog_lighting_rig.py")

EAL = unreal.EditorAssetLibrary
SDS_LIB = unreal.SubobjectDataBlueprintFunctionLibrary


def die(msg):
    print("DAWNFOG-ERROR %s" % msg)
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
                print("DAWNFOG-SPELLING %s=%s" % (names[0], name))
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable spelling among %s: %r" % (names, last))


# --------------------------------------------------------------------------- #
# Blueprint construction                                                       #
# --------------------------------------------------------------------------- #

def scene_root_handle(sds, bp):
    handles = list(sds.k2_gather_subobject_data_for_blueprint(bp))
    if not handles:
        die("subobject gather came back empty")
    named = []
    for h in handles:
        try:
            data = SDS_LIB.get_data(h)
            named.append((h, str(SDS_LIB.get_variable_name(data))))
        except Exception:  # noqa: BLE001
            named.append((h, "<unreadable>"))
    for h, name in named:
        if name == "DefaultSceneRoot":
            return h
    # A plain Actor blueprint gathers (actor, scene root); fall back to the
    # last handle rather than the actor itself.
    print("DAWNFOG-WARN no DefaultSceneRoot among %s; using last handle"
          % [n for _, n in named])
    return handles[-1]


def add_component(sds, bp, parent, cls, var_name):
    params = unreal.AddNewSubobjectParams(
        parent_handle=parent, new_class=cls, blueprint_context=bp)
    res = sds.add_new_subobject(params)
    handle, fail = (res if isinstance(res, tuple) else (res, None))
    ok = False
    try:
        ok = bool(handle.is_valid())
    except Exception:  # noqa: BLE001
        ok = handle is not None
    if not ok:
        die("add_new_subobject(%s) failed: %s" % (var_name, fail))
    if not sds.rename_subobject(handle, unreal.Text(var_name)):
        die("rename_subobject to %r failed" % var_name)
    data = SDS_LIB.get_data(handle)
    got = str(SDS_LIB.get_variable_name(data))
    if got != var_name:
        die("variable name read back %r, wanted %r (case-sensitive gate)"
            % (got, var_name))
    obj = SDS_LIB.get_object(data)
    if obj is None:
        die("no template object behind %s" % var_name)
    return obj


def rotator(pitch):
    r = unreal.Rotator()
    r.pitch = float(pitch)
    r.yaw = 0.0
    r.roll = 0.0
    return r


def warm_color():
    return unreal.Color(r=255, g=128, b=70, a=255)


# Component recipes. Each entry: (class_name, var_name, setter) where setter
# receives the template object. Class objects are resolved lazily so a missing
# exposure dies with a named error (notes.md section 5 third checkbox).
def _cls(name):
    cls = getattr(unreal, name, None)
    if cls is None:
        die("unreal.%s is not exposed to Python" % name)
    return cls


def sun_setters(obj, pitch=-8.0, color=True):
    set_prop(obj, rotator(pitch), "relative_rotation", "RelativeRotation")
    if color:
        set_prop(obj, warm_color(), "light_color", "LightColor")
    set_prop(obj, 2.5, "intensity", "Intensity")


def ambient_setters(obj):
    set_prop(obj, 0.25, "intensity", "Intensity")
    set_prop(obj, True, "real_time_capture", "b_real_time_capture",
             "bRealTimeCapture")


def fog_setters(obj):
    set_prop(obj, 0.6, "fog_density", "FogDensity")
    set_prop(obj, True, "enable_volumetric_fog", "b_enable_volumetric_fog",
             "bEnableVolumetricFog")
    set_prop(obj, 4.0, "volumetric_fog_extinction_scale",
             "VolumetricFogExtinctionScale")


REFERENCE = [
    ("SkyAtmosphereComponent", "Sky", None),
    ("SkyLightComponent", "Ambient", ambient_setters),
    ("DirectionalLightComponent", "Sun", sun_setters),
    ("ExponentialHeightFogComponent", "Fog", fog_setters),
]

# (folder-relative target, recipe, must_fail check ids, must_pass check ids)
_PRESENCE = ["rig_asset_exists", "rig_compiles_up_to_date"]
ASSETS = [
    ("reference", REFERENCE, [], [c for c in (
        "rig_asset_exists", "rig_sky_atmosphere_present",
        "rig_sky_light_present", "rig_sun_light_present",
        "rig_height_fog_present", "sun_angle_is_low_dawn", "sun_color_is_warm",
        "sun_intensity_is_dim", "skylight_intensity_is_dim",
        "skylight_recaptures_live_sky", "fog_density_is_dense",
        "fog_volumetric_enabled", "fog_extinction_raised",
        "rig_compiles_up_to_date")]),
    ("discrimination/three-lights-no-atmosphere",
     [r for r in REFERENCE if r[1] != "Sky"],
     ["rig_sky_atmosphere_present"],
     _PRESENCE + ["rig_sky_light_present", "rig_sun_light_present",
                  "rig_height_fog_present"]),
    ("discrimination/named-not-typed",
     [("SkyAtmosphereComponent", "Sky", None),
      ("SkyLightComponent", "Ambient", ambient_setters),
      ("PointLightComponent", "Sun",
       lambda o: sun_setters(o)),  # same numbers on the wrong type
      ("ExponentialHeightFogComponent", "Fog", fog_setters)],
     ["rig_sun_light_present"],
     _PRESENCE + ["rig_sky_atmosphere_present", "rig_sky_light_present",
                  "rig_height_fog_present"]),
    ("discrimination/overhead-noon-sun",
     [("SkyAtmosphereComponent", "Sky", None),
      ("SkyLightComponent", "Ambient", ambient_setters),
      ("DirectionalLightComponent", "Sun",
       lambda o: sun_setters(o, pitch=-60.0)),
      ("ExponentialHeightFogComponent", "Fog", fog_setters)],
     ["sun_angle_is_low_dawn"],
     _PRESENCE + ["rig_sun_light_present", "sun_color_is_warm",
                  "sun_intensity_is_dim"]),
    ("discrimination/default-white-sun",
     [("SkyAtmosphereComponent", "Sky", None),
      ("SkyLightComponent", "Ambient", ambient_setters),
      ("DirectionalLightComponent", "Sun",
       lambda o: sun_setters(o, color=False)),
      ("ExponentialHeightFogComponent", "Fog", fog_setters)],
     ["sun_color_is_warm"],
     _PRESENCE + ["rig_sun_light_present", "sun_angle_is_low_dawn",
                  "sun_intensity_is_dim"]),
    ("discrimination/engine-default-fog",
     [("SkyAtmosphereComponent", "Sky", None),
      ("SkyLightComponent", "Ambient", ambient_setters),
      ("DirectionalLightComponent", "Sun", sun_setters),
      ("ExponentialHeightFogComponent", "Fog", None)],  # every default
     ["fog_density_is_dense", "fog_volumetric_enabled",
      "fog_extinction_raised"],
     _PRESENCE + ["rig_height_fog_present", "rig_sun_light_present"]),
]


def build_asset(recipe):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(ASSET_NAME, PKG_DIR, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s" % ASSET_PATH)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if sds is None:
        die("SubobjectDataSubsystem unavailable")
    root = scene_root_handle(sds, bp)
    for cls_name, var_name, setter in recipe:
        obj = add_component(sds, bp, root, _cls(cls_name), var_name)
        if setter is not None:
            setter(obj)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not EAL.save_asset(ASSET_PATH, only_if_is_dirty=False):
        die("save_asset failed for %s" % ASSET_PATH)


def grade_in_process():
    """Run the real grader; return {check_id: (passed, detail)}."""
    spec = importlib.util.spec_from_file_location("dawnfog_grader", GRADER)
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


def main():
    if EAL.does_asset_exist(ASSET_PATH):
        die("substrate already carries %s - refusing to overwrite" % ASSET_PATH)
    for target, recipe, must_fail, must_pass in ASSETS:
        label = target.rsplit("/", 1)[-1]
        build_asset(recipe)
        vector = grade_in_process()
        fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
        print("DAWNFOG-VECTOR %s passed=%d/%d fails=%s"
              % (label, len(vector) - len(fails), len(vector), fails))
        for cid in must_fail:
            if vector.get(cid, (True, ""))[0]:
                die("%s: %s should FAIL but passed" % (label, cid))
        for cid in must_pass:
            if not vector.get(cid, (False, "missing"))[0]:
                die("%s: %s should PASS but read %s"
                    % (label, cid, vector.get(cid)))
        if not os.path.isfile(SUBSTRATE_FILE):
            die("%s: saved asset not on disk at %s" % (label, SUBSTRATE_FILE))
        dst = os.path.join(TASK_DIR, target.replace("/", os.sep), "Content",
                           "Tasks", TASK_ID, ASSET_NAME + ".uasset")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(SUBSTRATE_FILE, dst)
        if not EAL.delete_asset(ASSET_PATH):
            die("%s: could not delete the staged asset" % label)
        if EAL.does_asset_exist(ASSET_PATH):
            die("%s: asset still exists after delete" % label)
        print("DAWNFOG-ASSET-OK %s -> %s" % (label, dst))
    # Leave the substrate exactly as this task ships it: no folder at all.
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception:  # noqa: BLE001 - empty-dir cleanup is best-effort
        pass
    print("DAWNFOG-DONE")


main()
