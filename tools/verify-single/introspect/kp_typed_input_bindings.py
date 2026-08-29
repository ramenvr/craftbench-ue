"""L2-introspect script for the kp-typed-input-bindings task.

Structural, READ-ONLY verification of FOUR saved assets via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R29, ``t10-enhanced-input-mappings``, rewritten
behavior-only and re-pathed; see the task spec): three typed input-action
assets - ``IA_Move`` (a two-axis reading), ``IA_Zoom`` (a one-axis reading),
``IA_Jump`` (an on/off reading) - plus one input-configuration asset
``IMC_Bindings`` holding EXACTLY six key-to-action bindings, two of which
carry an axis-swap transform (first and second axis exchanged, third
untouched) and one of which additionally carries a sign flip, applied after
the swap. All under ``/Game/Tasks/kp-typed-input-bindings/``.

This is a ``tasks/python/`` basket task (owner decision 2026-08-11): the
prompt's exactness and volume make editor scripting the natural route, but the
DELIVERABLE is the resulting editor state and NOTHING here asserts "python was
used". This script reads the saved assets only.

Dead-gate audit (UE 5.8 defaults, from
``Engine/Plugins/EnhancedInput/Source/EnhancedInput/Public/``):

  * ``UInputAction::ValueType``      default ``Boolean`` (InputAction.h ctor
    default member init). So the Move/Axis2D and Zoom/Axis1D gates EXCLUDE
    the default; the Jump/Boolean gate is default-coincident and is an
    exactness confirmation conjoined with the (non-default) existence gate -
    recorded honestly in the task spec's audit table.
  * ``UInputMappingContext::Mappings`` default EMPTY - the count==6 gate and
    every per-binding gate exclude it.
  * ``FEnhancedActionKeyMapping::Modifiers`` default EMPTY - the two
    transform-carrying chains exclude it; the four empty-chain gates are
    default-coincident but each is conjoined with the non-default facts that
    the binding EXISTS, is bound EXACTLY ONCE, and targets the right action.
  * ``UInputModifierSwizzleAxis::Order`` default ``YXZ`` - default-coincident
    at the modifier level; the discriminating fact is the modifier EXISTING on
    a mapping at all (mappings carry none by default).

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** and pre-declared asset NAME,
    never by class and never by scanning. Class is consulted only as an
    ASSERTION ("is the thing at IA_Move really an input-action asset"),
    written subclass-tolerant via ``isinstance``.
  * Stock UE Python only (``EditorAssetLibrary`` + reflection). Never Aura's
    MCP tools - that would grade Aura with Aura.
  * Every check is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail`` instead of aborting the
    verdict.
  * **FAIL CLOSED.** No check passes because a probe did not raise. A type
    probe that cannot be evaluated FAILS the check; an unreadable property is
    a ``*_READ_ERROR`` failure, never a pass; an empty or missing submission
    scores 0/14 (this task ships NO baseline, so there is nothing for an
    empty overlay to inherit a pass from).
  * The check list has a **constant length (14)** on every leg, including a
    missing asset. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts; a constant denominator keeps the ratio comparable and stops
    a submission improving its score by making checks unreachable.

Detail strings are stable, ASCII, greppable tokens, and every token a MATRIX
row keys on is written in ONE source literal (never assembled across
concatenations or placeholders), so the static MATRIX oracle can grep them.
Error tokens (``*_READ_ERROR`` / ``*_PROBE_ERROR`` / ``*_ABORTED``) are
disjoint from graded failure tokens and appear in NO matrix row. No detail
contains either automation result marker; neither marker substring appears
anywhere in this file.

UE 5.8 API notes:
  * ``UInputAction`` / ``UInputMappingContext`` are ``UDataAsset`` subclasses
    from the EnhancedInput plugin (enabled by default on the ThirdPerson
    substrate; the stock template's own input content lives under the
    agent-denied ``Content/Input`` and ``Content/ThirdPerson`` prefixes and is
    NOT graded - full-path identity keeps the same-named stock assets out).
  * ``UInputAction::ValueType`` is ``UPROPERTY(EditAnywhere,
    BlueprintReadOnly)`` - readable. Pythonized ``value_type``; the sheet's
    ``action_value_type`` spelling is tried too rather than bet against.
  * ``UInputMappingContext::Mappings`` is ``UPROPERTY(EditAnywhere,
    BlueprintReadOnly)`` - readable; elements are
    ``FEnhancedActionKeyMapping`` structs whose ``Action`` / ``Key`` /
    ``Modifiers`` members are EditAnywhere-visible.
  * ``FKey::KeyName`` is an ``UPROPERTY(EditAnywhere)`` FName; FName
    comparison is case-insensitive, so key names are compared lower-cased.
  * Enum reads are compared through a canonical form (``AXIS2_D`` ==
    ``Axis2D`` == ``AXIS2D``) because Python enum entry spellings differ from
    C++ and between builds.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and NAMES, never class) ------------
TASK_ID = "kp-typed-input-bindings"

ACTION_MOVE = "/Game/Tasks/kp-typed-input-bindings/IA_Move"
ACTION_ZOOM = "/Game/Tasks/kp-typed-input-bindings/IA_Zoom"
ACTION_JUMP = "/Game/Tasks/kp-typed-input-bindings/IA_Jump"
CONTEXT_ASSET = "/Game/Tasks/kp-typed-input-bindings/IMC_Bindings"

EXPECTED_BINDING_COUNT = 6

ACTION_TYPE_NAME = "InputAction"
CONTEXT_TYPE_NAME = "InputMappingContext"
SWIZZLE_TYPE_NAME = "InputModifierSwizzleAxis"
NEGATE_TYPE_NAME = "InputModifierNegate"

# Canonical chain vocabulary (see _canon_chain): a swizzle modifier becomes
# "swizzle_<order>", a negate modifier becomes "negate", anything else becomes
# "other_<classname>". Expected chains per binding:
CHAIN_SWIZZLE = ("swizzle_yxz",)
CHAIN_SWIZZLE_NEGATE = ("swizzle_yxz", "negate")
CHAIN_EMPTY = ()

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "ia_move_asset_exists",
    "ia_move_reads_axis2d",
    "ia_zoom_asset_exists",
    "ia_zoom_reads_axis1d",
    "ia_jump_asset_exists",
    "ia_jump_reads_boolean",
    "imc_asset_exists",
    "imc_binding_count_is_six",
    "map_w_move_swizzled",
    "map_s_move_swizzled_negated",
    "map_a_move_plain",
    "map_d_move_plain",
    "map_wheel_zoom_plain",
    "map_space_jump_plain",
)

MAP_CHECK_IDS = CHECK_IDS[8:]


# --------------------------------------------------------------------------- #
# verdict plumbing                                                             #
# --------------------------------------------------------------------------- #

def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed), "detail": str(detail)}


def emit_verdict(checks):
    """Print the one verdict block the L2-introspect layer parses."""
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        try:
            unreal.log(INTROSPECT_JSON_START)
            unreal.log(payload)
            unreal.log(INTROSPECT_JSON_END)
        except Exception:  # noqa: BLE001 - stdout copy is authoritative
            pass


# --------------------------------------------------------------------------- #
# small reflection helpers (each defensive; callers wrap in try/except)        #
# --------------------------------------------------------------------------- #

def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is.

    UE pythonizes UPROPERTY names (``ValueType`` -> ``value_type``); trying
    every plausible spelling is cheaper than being wrong, and it never invents
    a value - if every spelling fails the last exception propagates and the
    caller records a ``*_READ_ERROR``.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _class_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_class().get_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _isinstance_tristate(obj, type_name):
    """``isinstance(obj, unreal.<type_name>)`` as True / False / None.

    ``None`` means "the type is not exposed / the probe could not be
    evaluated", and every caller treats that as NOT satisfied. This never
    returns True because an exception did not happen.
    """
    if obj is None:
        return False
    cls = getattr(unreal, type_name, None)
    if cls is None:
        return None
    try:
        return bool(isinstance(obj, cls))
    except Exception:  # noqa: BLE001
        return None


def _canon_enum(value):
    """Canonical UPPER alnum form of an enum read: 'InputActionValueType.
    AXIS2_D' -> 'AXIS2D', 'Axis2D' -> 'AXIS2D'. Never invents a value."""
    # Name-first: UE enum values render as 'Type.NAME: N' and the naive tail
    # kept the ': N' digits ('BOOLEAN0', 'AXIS2D2' - caught by the aid's
    # self-grade 2026-08-11). getattr covers plain strings and older enums.
    name = getattr(value, "name", None)
    tail = str(name) if name else str(value).split(".")[-1].split(":")[0]
    return "".join(ch for ch in tail.upper() if ch.isalnum())


def _object_content_path(obj):
    """'/Game/.../AssetName' for a loaded object; raises when unreadable."""
    try:
        full = str(obj.get_path_name())
    except Exception:  # noqa: BLE001
        full = str(obj.get_full_name()).split(" ", 1)[-1]
    if not full:
        raise RuntimeError("object path unreadable")
    return full.split(".")[0]


def _key_name_of(mapping):
    """Lower-cased FKey name of one mapping, or '<unreadable>'."""
    try:
        key = _read_property(mapping, "key", "Key")
        name = _read_property(key, "key_name", "KeyName")
        return str(name).lower()
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _canon_modifier(modifier):
    """Canonical token for one modifier instance. Raises on an unevaluable
    type probe - a chain that cannot be classified must FAIL, not pass."""
    is_swizzle = _isinstance_tristate(modifier, SWIZZLE_TYPE_NAME)
    if is_swizzle is None:
        raise RuntimeError("modifier type probe unevaluable class=%s"
                           % _class_name(modifier))
    if is_swizzle:
        order = _read_property(modifier, "order", "Order")
        return "swizzle_%s" % _canon_enum(order).lower()
    is_negate = _isinstance_tristate(modifier, NEGATE_TYPE_NAME)
    if is_negate is None:
        raise RuntimeError("modifier type probe unevaluable class=%s"
                           % _class_name(modifier))
    if is_negate:
        return "negate"
    if modifier is None:
        return "other_none"
    return "other_%s" % _class_name(modifier).lower()


def _canon_chain(mapping):
    """Ordered tuple of canonical modifier tokens for one mapping. Raises on
    an unreadable modifiers array or an unclassifiable element."""
    mods = _read_property(mapping, "modifiers", "Modifiers")
    return tuple(_canon_modifier(m) for m in list(mods or []))


# --------------------------------------------------------------------------- #
# asset resolution (existence AND class, both required)                        #
# --------------------------------------------------------------------------- #

def _resolve_asset(path, type_name, tok_ok, tok_missing, tok_load_failed,
                   tok_wrong_class, tok_class_probe, tok_probe):
    """``(asset_or_None, detail)`` for one pre-declared asset path.

    Three positive facts are required and any unreadable one FAILS: the asset
    exists at the path, it loads, and ``isinstance`` against the required
    asset class returns True (subclass-tolerant). The outcomes carry DISTINCT
    tokens so the matrix can tell "absent" from "impostor" from "the class is
    not exposed to Python".
    """
    try:
        exists = bool(unreal.EditorAssetLibrary.does_asset_exist(path))
    except Exception as e:  # noqa: BLE001
        return None, tok_probe % (e,)
    if not exists:
        return None, tok_missing
    try:
        asset = unreal.EditorAssetLibrary.load_asset(path)
    except Exception as e:  # noqa: BLE001
        return None, tok_probe % (e,)
    if asset is None:
        return None, tok_load_failed
    verdict = _isinstance_tristate(asset, type_name)
    if verdict is None:
        return None, tok_class_probe % _class_name(asset)
    if not verdict:
        return None, tok_wrong_class % _class_name(asset)
    return asset, tok_ok % _class_name(asset)


# --------------------------------------------------------------------------- #
# the three input-action assets                                                #
# --------------------------------------------------------------------------- #
# Every MATRIX-keyed token below is ONE literal; the missing-asset tokens
# embed the full pre-declared path so no matrix span crosses a placeholder.

ACTIONS = (
    (
        "ia_move_asset_exists", "ia_move_reads_axis2d", ACTION_MOVE, "AXIS2D",
        "IA_MOVE_OK class=%s",
        "IA_MOVE_MISSING /Game/Tasks/kp-typed-input-bindings/IA_Move",
        "IA_MOVE_LOAD_FAILED /Game/Tasks/kp-typed-input-bindings/IA_Move",
        "IA_MOVE_WRONG_CLASS class=%s expected=InputAction",
        "IA_MOVE_CLASS_PROBE_ERROR class=%s",
        "IA_MOVE_PROBE_ERROR raised %r",
        "IA_MOVE_VALUE_TYPE_OK value_type=%s",
        "IA_MOVE_VALUE_TYPE_WRONG value_type=%s expected=AXIS2D",
        "IA_MOVE_VALUE_TYPE_READ_ERROR raised %r",
    ),
    (
        "ia_zoom_asset_exists", "ia_zoom_reads_axis1d", ACTION_ZOOM, "AXIS1D",
        "IA_ZOOM_OK class=%s",
        "IA_ZOOM_MISSING /Game/Tasks/kp-typed-input-bindings/IA_Zoom",
        "IA_ZOOM_LOAD_FAILED /Game/Tasks/kp-typed-input-bindings/IA_Zoom",
        "IA_ZOOM_WRONG_CLASS class=%s expected=InputAction",
        "IA_ZOOM_CLASS_PROBE_ERROR class=%s",
        "IA_ZOOM_PROBE_ERROR raised %r",
        "IA_ZOOM_VALUE_TYPE_OK value_type=%s",
        "IA_ZOOM_VALUE_TYPE_WRONG value_type=%s expected=AXIS1D",
        "IA_ZOOM_VALUE_TYPE_READ_ERROR raised %r",
    ),
    (
        "ia_jump_asset_exists", "ia_jump_reads_boolean", ACTION_JUMP, "BOOLEAN",
        "IA_JUMP_OK class=%s",
        "IA_JUMP_MISSING /Game/Tasks/kp-typed-input-bindings/IA_Jump",
        "IA_JUMP_LOAD_FAILED /Game/Tasks/kp-typed-input-bindings/IA_Jump",
        "IA_JUMP_WRONG_CLASS class=%s expected=InputAction",
        "IA_JUMP_CLASS_PROBE_ERROR class=%s",
        "IA_JUMP_PROBE_ERROR raised %r",
        "IA_JUMP_VALUE_TYPE_OK value_type=%s",
        "IA_JUMP_VALUE_TYPE_WRONG value_type=%s expected=BOOLEAN",
        "IA_JUMP_VALUE_TYPE_READ_ERROR raised %r",
    ),
)


def _action_checks(results):
    for (cid_exists, cid_type, path, expected_canon, tok_ok, tok_missing,
         tok_load_failed, tok_wrong_class, tok_class_probe, tok_probe,
         tok_vt_ok, tok_vt_wrong, tok_vt_err) in ACTIONS:
        asset, detail = _resolve_asset(
            path, ACTION_TYPE_NAME, tok_ok, tok_missing, tok_load_failed,
            tok_wrong_class, tok_class_probe, tok_probe)
        results[cid_exists] = check(cid_exists, asset is not None, detail)
        if asset is None:
            # One cause, one token: the value-type check carries the same
            # resolution detail instead of inventing an unrelated failure.
            results[cid_type] = check(cid_type, False, detail)
            continue
        try:
            raw = _read_property(asset, "value_type", "ValueType",
                                 "action_value_type")
            canon = _canon_enum(raw)
            ok = canon == expected_canon
            results[cid_type] = check(
                cid_type, ok,
                (tok_vt_ok % canon) if ok else (tok_vt_wrong % canon))
        except Exception as e:  # noqa: BLE001
            results[cid_type] = check(cid_type, False, tok_vt_err % (e,))


# --------------------------------------------------------------------------- #
# the input-configuration asset and its six bindings                           #
# --------------------------------------------------------------------------- #

# (check id, lower-cased key name, expected action path, expected chain,
#  tok_ok, tok_not_once, tok_wrong_action, tok_wrong_chain, tok_err)
BINDINGS = (
    (
        "map_w_move_swizzled", "w", ACTION_MOVE, CHAIN_SWIZZLE,
        "MAP_W_OK action=%s chain=%s",
        "MAP_W_KEY_NOT_BOUND_ONCE count=%d key=W bound_keys=%s",
        "MAP_W_WRONG_ACTION action=%s expected=%s",
        "MAP_W_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_W_READ_ERROR raised %r",
    ),
    (
        "map_s_move_swizzled_negated", "s", ACTION_MOVE, CHAIN_SWIZZLE_NEGATE,
        "MAP_S_OK action=%s chain=%s",
        "MAP_S_KEY_NOT_BOUND_ONCE count=%d key=S bound_keys=%s",
        "MAP_S_WRONG_ACTION action=%s expected=%s",
        "MAP_S_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_S_READ_ERROR raised %r",
    ),
    (
        "map_a_move_plain", "a", ACTION_MOVE, CHAIN_EMPTY,
        "MAP_A_OK action=%s chain=%s",
        "MAP_A_KEY_NOT_BOUND_ONCE count=%d key=A bound_keys=%s",
        "MAP_A_WRONG_ACTION action=%s expected=%s",
        "MAP_A_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_A_READ_ERROR raised %r",
    ),
    (
        "map_d_move_plain", "d", ACTION_MOVE, CHAIN_EMPTY,
        "MAP_D_OK action=%s chain=%s",
        "MAP_D_KEY_NOT_BOUND_ONCE count=%d key=D bound_keys=%s",
        "MAP_D_WRONG_ACTION action=%s expected=%s",
        "MAP_D_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_D_READ_ERROR raised %r",
    ),
    (
        "map_wheel_zoom_plain", "mousewheelaxis", ACTION_ZOOM, CHAIN_EMPTY,
        "MAP_WHEEL_OK action=%s chain=%s",
        "MAP_WHEEL_KEY_NOT_BOUND_ONCE count=%d key=MouseWheelAxis bound_keys=%s",
        "MAP_WHEEL_WRONG_ACTION action=%s expected=%s",
        "MAP_WHEEL_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_WHEEL_READ_ERROR raised %r",
    ),
    (
        "map_space_jump_plain", "spacebar", ACTION_JUMP, CHAIN_EMPTY,
        "MAP_SPACE_OK action=%s chain=%s",
        "MAP_SPACE_KEY_NOT_BOUND_ONCE count=%d key=SpaceBar bound_keys=%s",
        "MAP_SPACE_WRONG_ACTION action=%s expected=%s",
        "MAP_SPACE_MODIFIER_CHAIN_WRONG chain=%s expected=%s",
        "MAP_SPACE_READ_ERROR raised %r",
    ),
)


def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


def _binding_check(results, mappings, bound_keys, spec):
    (cid, key_lower, expected_path, expected_chain,
     tok_ok, tok_not_once, tok_wrong_action, tok_wrong_chain, tok_err) = spec

    matches = [m for m, name in zip(mappings, bound_keys) if name == key_lower]
    if len(matches) != 1:
        # Covers absent (0) and duplicated (>1). Unreadable key names never
        # count as a match, so the check cannot pass through an unreadable key.
        results[cid] = check(cid, False,
                             tok_not_once % (len(matches), sorted(bound_keys)))
        return
    mapping = matches[0]

    try:
        action = _read_property(mapping, "action", "Action")
        if action is None:
            results[cid] = check(
                cid, False, tok_wrong_action % ("None", expected_path))
            return
        got_path = _object_content_path(action)
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, tok_err % (e,))
        return
    if got_path != expected_path:
        results[cid] = check(
            cid, False, tok_wrong_action % (got_path, expected_path))
        return

    try:
        got_chain = _canon_chain(mapping)
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, tok_err % (e,))
        return
    if got_chain != expected_chain:
        results[cid] = check(
            cid, False,
            tok_wrong_chain % (list(got_chain), list(expected_chain)))
        return

    results[cid] = check(cid, True, tok_ok % (got_path, list(got_chain)))


def _context_checks(results):
    imc, detail = _resolve_asset(
        CONTEXT_ASSET, CONTEXT_TYPE_NAME,
        "IMC_OK class=%s",
        "IMC_MISSING /Game/Tasks/kp-typed-input-bindings/IMC_Bindings",
        "IMC_LOAD_FAILED /Game/Tasks/kp-typed-input-bindings/IMC_Bindings",
        "IMC_WRONG_CLASS class=%s expected=InputMappingContext",
        "IMC_CLASS_PROBE_ERROR class=%s",
        "IMC_PROBE_ERROR raised %r")
    results["imc_asset_exists"] = check("imc_asset_exists", imc is not None,
                                        detail)
    if imc is None:
        _fanout(results, ("imc_binding_count_is_six",) + MAP_CHECK_IDS, detail)
        return

    try:
        mappings = list(_read_property(imc, "mappings", "Mappings") or [])
    except Exception as e:  # noqa: BLE001
        err = "IMC_MAPPINGS_READ_ERROR raised %r" % (e,)
        _fanout(results, ("imc_binding_count_is_six",) + MAP_CHECK_IDS, err)
        return

    count = len(mappings)
    ok = count == EXPECTED_BINDING_COUNT
    results["imc_binding_count_is_six"] = check(
        "imc_binding_count_is_six", ok,
        ("IMC_BINDING_COUNT_OK count=%d" % count) if ok
        else ("IMC_BINDING_COUNT_WRONG count=%d expected=6" % count))

    # Key names are read ONCE, defensively; an unreadable one becomes
    # '<unreadable>' and can never satisfy a binding's exactly-once gate.
    bound_keys = [_key_name_of(m) for m in mappings]
    for spec in BINDINGS:
        try:
            _binding_check(results, mappings, bound_keys, spec)
        except Exception as e:  # noqa: BLE001 - belt and braces per binding
            results[spec[0]] = check(spec[0], False, spec[8] % (e,))


def main():
    results = {}
    try:
        _action_checks(results)
        _context_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, CHECK_IDS, "KPEIM_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
