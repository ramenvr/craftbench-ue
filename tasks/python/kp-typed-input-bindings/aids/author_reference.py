"""Author the kp-typed-input-bindings REFERENCE deliverable (4 assets).

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline (notes.md), so the flow is: build the
four assets at the real content path -> save -> GRADE THEM IN-PROCESS with the
real verifier script -> harvest the .uasset files into the tasks/ tree
(reference/ overlay layout) -> delete them from the substrate. The substrate
ends with no /Game/Tasks/kp-typed-input-bindings folder at all, which the
runner verifies via git status.

Validation is the actual grader, not a re-implementation: the authored state
is scored by tools/verify-single/introspect/kp_typed_input_bindings.py
(stdout captured, CRAFTBENCH-INTROSPECT-JSON block parsed) and harvested ONLY
on a 14/14 vector.

UE 5.8 cautions this script is written around (each has burned a task before):
  * Property names in python are underscore-folded (ValueType -> value_type,
    and a bool drops its leading 'b'). Every set below probes several
    spellings and FAILS CLOSED - a wrong guess aborts the run before harvest,
    it can never ship a half-set asset. Winning spellings are printed as
    KPEIM-SPELLING lines for notes.md.
  * Asset renames leave registry tombstones - so nothing here renames.
    Every asset is created at its final name/path, and the pre-flight check
    refuses to run against a substrate that already carries the folder
    (a previous partial run must be cleaned via git, not overwritten).
  * SCS component SOCKET attachment cannot be set from python - irrelevant
    here by design: no Blueprint, no components, no sockets. (Recorded so a
    future editor of this task does not drift the design into that trap.)
  * import_text pin exactness - irrelevant here: no graph pins are authored.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPEIM-SPELLING <property>=<winning name>
  KPEIM-VECTOR passed=<n>/14 fails=[ids]
  KPEIM-ASSET-OK <file>
  KPEIM-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-typed-input-bindings"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID

ASSET_NAMES = ("IA_Move", "IA_Zoom", "IA_Jump", "IMC_Bindings")
ACTION_MOVE = "%s/IA_Move" % PKG_DIR
ACTION_ZOOM = "%s/IA_Zoom" % PKG_DIR
ACTION_JUMP = "%s/IA_Jump" % PKG_DIR
CONTEXT_ASSET = "%s/IMC_Bindings" % PKG_DIR

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
# TASK_DIR from _HERE, not a hardcoded basket: survives tree moves.
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE_TASK_DIR = os.path.join(
    REPO, "UE-projects", "ThirdPerson", "Content", "Tasks", TASK_ID)
GRADER = os.path.join(
    REPO, "tools", "verify-single", "introspect",
    "kp_typed_input_bindings.py")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("KPEIM-ERROR %s" % msg)
    raise SystemExit(msg)


if not os.path.isfile(GRADER):
    die("grader not found at %s (layout drift?)" % GRADER)


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
                print("KPEIM-SPELLING %s=%s" % (names[0], name))
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable spelling among %s: %r" % (names, last))


def read_prop(obj, *names):
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
# asset creation                                                               #
# --------------------------------------------------------------------------- #

def create_data_asset(name, cls):
    """One data asset at PKG_DIR/name of class cls. Fail-closed.

    Route A: DataAssetFactory as-is (the create_asset class argument decides).
    Route B: DataAssetFactory with its data-asset class pinned first. Either
    way the result is verified by isinstance before use.
    """
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = None
    for pin_class in (False, True):
        factory = unreal.DataAssetFactory()
        if pin_class:
            try:
                factory.set_editor_property("data_asset_class", cls)
            except Exception:  # noqa: BLE001 - spelling probe, route B only
                continue
        try:
            asset = tools.create_asset(name, PKG_DIR, cls, factory)
        except Exception:  # noqa: BLE001 - try the other route
            asset = None
        if asset is not None:
            break
    if asset is None:
        die("create_asset failed for %s/%s" % (PKG_DIR, name))
    if not isinstance(asset, cls):
        die("created %s but it is a %s, wanted %s"
            % (name, type(asset).__name__, cls.__name__))
    return asset


def make_key(key_name):
    """An unreal.Key carrying key_name, read back and verified."""
    key = None
    try:
        key = unreal.Key(key_name=key_name)
    except Exception:  # noqa: BLE001 - constructor kwargs not supported
        key = None
    if key is None:
        key = unreal.Key()
        set_prop(key, key_name, "key_name", "KeyName")
    got = str(read_prop(key, "key_name", "KeyName"))
    if got.lower() != key_name.lower():
        die("key name read back %r, wanted %r" % (got, key_name))
    return key


def make_modifier(cls_name, outer):
    """An instanced input-modifier object. Instanced UPROPERTY entries need a
    real outer; the context asset is used so the reference serializes
    self-contained."""
    cls = _cls(cls_name)
    mod = None
    try:
        mod = unreal.new_object(cls, outer=outer)
    except Exception:  # noqa: BLE001 - fall through to the bare route
        mod = None
    if mod is None:
        try:
            mod = unreal.new_object(cls)
        except Exception as e:  # noqa: BLE001
            die("new_object(%s) failed: %r" % (cls_name, e))
    if mod is None:
        die("new_object(%s) returned None" % cls_name)
    return mod


def make_mapping(action, key_name, modifiers):
    m = unreal.EnhancedActionKeyMapping()
    set_prop(m, action, "action", "Action")
    set_prop(m, make_key(key_name), "key", "Key")
    if modifiers:
        set_prop(m, modifiers, "modifiers", "Modifiers")
    return m


def save_asset(path):
    if not EAL.save_asset(path, only_if_is_dirty=False):
        die("save_asset failed for %s" % path)


# --------------------------------------------------------------------------- #
# grading + harvest                                                            #
# --------------------------------------------------------------------------- #

def grade_in_process():
    """Run the real grader; return {check_id: (passed, detail)}."""
    spec = importlib.util.spec_from_file_location("kpeim_grader", GRADER)
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
    if EAL.does_asset_exist(CONTEXT_ASSET) or EAL.does_asset_exist(ACTION_MOVE):
        die("substrate already carries %s content - refusing to overwrite "
            "(clean via git first; renames leave registry tombstones)"
            % PKG_DIR)

    input_action_cls = _cls("InputAction")
    context_cls = _cls("InputMappingContext")
    value_type_enum = _cls("InputActionValueType")

    # --- the three typed actions --------------------------------------------
    ia_move = create_data_asset("IA_Move", input_action_cls)
    ia_zoom = create_data_asset("IA_Zoom", input_action_cls)
    ia_jump = create_data_asset("IA_Jump", input_action_cls)

    axis2d = getattr(value_type_enum, "AXIS2_D",
                     getattr(value_type_enum, "AXIS2D", None))
    axis1d = getattr(value_type_enum, "AXIS1_D",
                     getattr(value_type_enum, "AXIS1D", None))
    boolean = getattr(value_type_enum, "BOOLEAN", None)
    if axis2d is None or axis1d is None or boolean is None:
        die("InputActionValueType entries not found (have: %s)"
            % [n for n in dir(value_type_enum) if not n.startswith("_")])

    set_prop(ia_move, axis2d, "value_type", "ValueType", "action_value_type")
    set_prop(ia_zoom, axis1d, "value_type", "ValueType", "action_value_type")
    set_prop(ia_jump, boolean, "value_type", "ValueType", "action_value_type")

    # --- the configuration asset and its six bindings -----------------------
    imc = create_data_asset("IMC_Bindings", context_cls)

    def swizzle():
        mod = make_modifier("InputModifierSwizzleAxis", imc)
        order_enum = _cls("InputAxisSwizzle")
        yxz = getattr(order_enum, "YXZ", None)
        if yxz is None:
            die("InputAxisSwizzle.YXZ not found (have: %s)"
                % [n for n in dir(order_enum) if not n.startswith("_")])
        set_prop(mod, yxz, "order", "Order")
        return mod

    def negate():
        return make_modifier("InputModifierNegate", imc)

    mappings = [
        make_mapping(ia_move, "W", [swizzle()]),
        make_mapping(ia_move, "S", [swizzle(), negate()]),
        make_mapping(ia_move, "A", []),
        make_mapping(ia_move, "D", []),
        make_mapping(ia_zoom, "MouseWheelAxis", []),
        make_mapping(ia_jump, "SpaceBar", []),
    ]
    set_prop(imc, mappings, "mappings", "Mappings")
    got = list(read_prop(imc, "mappings", "Mappings") or [])
    if len(got) != 6:
        die("mapping array read back %d entries, wanted 6" % len(got))

    for path in (ACTION_MOVE, ACTION_ZOOM, ACTION_JUMP, CONTEXT_ASSET):
        save_asset(path)

    # --- self-grade with the REAL verifier; 14/14 or no harvest -------------
    vector = grade_in_process()
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPEIM-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if fails:
        for cid in fails:
            print("KPEIM-FAIL-DETAIL %s %s" % (cid, vector[cid][1]))
        die("reference did not grade 14/14; nothing harvested")

    # --- harvest into the reference/ overlay, then clean the substrate ------
    dst_dir = os.path.join(TASK_DIR, "reference", "Content", "Tasks", TASK_ID)
    os.makedirs(dst_dir, exist_ok=True)
    for name in ASSET_NAMES:
        src = os.path.join(SUBSTRATE_TASK_DIR, name + ".uasset")
        if not os.path.isfile(src):
            die("saved asset not on disk at %s" % src)
        dst = os.path.join(dst_dir, name + ".uasset")
        shutil.copy2(src, dst)
        print("KPEIM-ASSET-OK %s" % dst)

    for path in (CONTEXT_ASSET, ACTION_MOVE, ACTION_ZOOM, ACTION_JUMP):
        if not EAL.delete_asset(path):
            print("KPEIM-WARN could not delete the staged asset %s" % path)
        if EAL.does_asset_exist(path):
            die("asset still exists after delete: %s" % path)
    # Leave the substrate exactly as this task ships it: no folder at all.
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception:  # noqa: BLE001 - empty-dir cleanup is best-effort
        pass
    print("KPEIM-DONE")


main()
