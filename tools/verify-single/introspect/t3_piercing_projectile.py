"""t3-piercing-projectile - L2I introspect: collision vocabulary + wired actors.

Verifier-owned. Runs headless (UnrealEditor-Cmd -ExecutePythonScript= under
-nullrhi), read-only, and prints ONE verdict block between the
CRAFTBENCH-INTROSPECT-JSON markers with EXACTLY 9 named checks on every leg
(constant denominator - a submission cannot improve its ratio by making
checks unreachable).

Two graded halves that cross-check each other (population plan SS12.2):

  * DEFINITIONS (checks 1-4) - the channel + preset definitions are dead
    through reflection (UCollisionProfile: bare globalconfig arrays, zero
    UFUNCTIONs), so they are read as TEXT from the submitted
    Config/DefaultEngine.ini with UE-ini semantics (array ``+`` prefixes
    part of the key; profile responses default to Block, CustomResponses
    lists deviations).
  * RESOLVED BEHAVIOR (checks 5-8) - per-component collision state is plain
    EditAnywhere reflection on the three Blueprints' SCS component
    templates, read through the BlueprintCallable getters
    (get_collision_profile_name / get_collision_object_type /
    get_collision_response_to_channel) at grade-time boot - i.e. AFTER the
    engine loaded the submitted ini, so an undefined preset cannot resolve.

  A text-only submission (ini right, Blueprints on default profiles) dies
  at 6-8; a reflection-only submission (components hand-set, presets never
  defined) dies at 2-4 and at 5.

Read routes are wrapped, multi-spelling, and FAIL-CLOSED: an unevaluable
probe is a graded FAIL carrying a named token, never a silent pass. Failure
tokens are single greppable literals (PIERCE_*) so discrimination MATRIX
rows can credit each variant at its named assertion.
"""

from __future__ import annotations

import json
import os
import re

try:
    import unreal  # type: ignore
except Exception:  # noqa: BLE001 - emit an all-fail verdict outside UE
    unreal = None


TASK_ID = "t3-piercing-projectile"
CONTENT_PREFIX = "/Game/Tasks/t3-piercing-projectile"

BP_BULLET = CONTENT_PREFIX + "/BP_Bullet"
BP_PIERCABLE = CONTENT_PREFIX + "/BP_PiercableWall"
BP_NONPIERCABLE = CONTENT_PREFIX + "/BP_NonPiercableWall"

CHANNEL_NAME = "Projectile"
PRESET_BULLET = "Bullet"
PRESET_PIERCABLE = "Piercable"
PRESET_NONPIERCABLE = "NonPiercable"

COLLISION_SECTION = "/Script/Engine.CollisionProfile"
KEY_CHANNELS = "+DefaultChannelResponses"
KEY_PROFILES = "+Profiles"

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

CHECK_IDS = (
    "projectile_channel_defined",
    "bullet_preset_defined",
    "piercable_preset_defined",
    "nonpiercable_preset_defined",
    "both_sides_rule_holds",
    "bullet_actor_wired",
    "piercable_wall_wired",
    "nonpiercable_wall_wired",
    "all_three_compile_clean",
)

DEFINITION_CIDS = CHECK_IDS[:4]
ACTOR_CIDS = CHECK_IDS[5:8]


# --------------------------------------------------------------------------- #
# verdict plumbing (kp_blueprint_actor_audit_report lineage)                    #
# --------------------------------------------------------------------------- #

def _defang(text, cap=500):
    """Neutralize agent-controlled text before it enters the verdict block.

    Review catch 2026-08-12: an embedded END marker inside a detail string
    truncates the JSON body into HARNESS-ERROR (a denominator opt-out).
    Details here carry ini fragments - agent-controlled - so every detail
    flows through check() and this is the one seam."""
    s = str(text)
    for marker in ("CRAFTBENCH-INTROSPECT-JSON", "CRAFTBENCH-ASSET-INTEGRITY-JSON"):
        s = s.replace(marker, "CB-MARKER-DEFANGED")
    if len(s) > cap:
        s = s[:cap] + "...[capped]"
    return s


def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed),
            "detail": _defang(detail)}


def emit_verdict(checks):
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


def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


# --------------------------------------------------------------------------- #
# small reflection helpers                                                      #
# --------------------------------------------------------------------------- #

def _read_property(obj, *names):
    """First readable spelling of a property; re-raises if none reads."""
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
    """isinstance as True / False / None; None = probe unevaluable, and every
    caller treats that as NOT satisfied."""
    if obj is None:
        return False
    cls = getattr(unreal, type_name, None)
    if cls is None:
        return None
    try:
        return bool(isinstance(obj, cls))
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# ini half: parse the submitted DefaultEngine.ini with UE-ini semantics         #
# --------------------------------------------------------------------------- #

def _project_ini_path():
    raw = unreal.Paths.project_config_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001
        full = os.path.abspath(str(raw))
    return os.path.join(str(full), "DefaultEngine.ini")


def _parse_ue_ini(text):
    """{section: ordered [(raw_key, value)]}. Mirrors config_lane.parse_ue_ini
    semantics: ``+ - . !`` prefixes are PART of raw_key; the value is
    everything after the FIRST ``=``; duplicates preserved in file order."""
    sections = {}
    current = ""
    sections[current] = []
    for line in text.replace("\r\n", "\n").lstrip("﻿").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
            sections.setdefault(current, [])
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            sections.setdefault(current, []).append((key.strip(), value))
        else:
            sections.setdefault(current, []).append((stripped, ""))
    return sections


_RE_STRUCT_FIELD = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[^,()]+)')
_RE_CUSTOM_RESPONSE = re.compile(
    r'Channel\s*=\s*"([^"]+)"\s*,\s*Response\s*=\s*(\w+)')


def _struct_fields(value):
    """Top-ish-level Key=Value pairs of a UE struct literal. Values keep their
    quotes stripped. Nested CustomResponses fields also land here (harmless -
    FIRST occurrence of a key wins, outer fields precede nested ones, and the
    outer fields of interest, Name/ObjectTypeName/CollisionEnabled/
    DefaultResponse/bTraceType, never appear inside a CustomResponses
    tuple)."""
    fields = {}
    for key, raw in _RE_STRUCT_FIELD.findall(value):
        v = raw.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        if key not in fields:  # FIRST occurrence wins: outer fields precede nested ones
            fields[key] = v
    return fields


def _profile_response_to(entry_value, channel, default="ECR_Block"):
    """UE profile semantics: responses default to Block; CustomResponses
    lists the deviations. Returns the ECR_* token for ``channel``."""
    for chan, resp in _RE_CUSTOM_RESPONSE.findall(entry_value):
        if chan == channel:
            return resp
    return default


def _collect_definitions(results):
    """Fills checks 1-4 from ini text. Returns (channel_index_or_None,
    profiles_by_name) for the resolved half."""
    ini_path = _project_ini_path()
    if not os.path.isfile(ini_path):
        _fanout(results, DEFINITION_CIDS,
                "PIERCE_INI_MISSING path=%s" % ini_path)
        return None, {}
    with open(ini_path, "rb") as fh:
        text = fh.read().decode("utf-8-sig", errors="replace")
    sections = _parse_ue_ini(text)
    entries = sections.get(COLLISION_SECTION, [])

    channels = [v for k, v in entries if k == KEY_CHANNELS]
    profiles = [v for k, v in entries if k == KEY_PROFILES]

    # -- check 1: exactly one new channel, object-type, named, Block-default.
    #    Trace channels arrive through the SAME +DefaultChannelResponses key
    #    (bTraceType=True), so the exactly-one gate IS the no-other-channels
    #    gate.
    channel_index = None
    if len(channels) != 1:
        results["projectile_channel_defined"] = check(
            "projectile_channel_defined", False,
            "PIERCE_CHANNEL_COUNT expected=1 got=%d" % len(channels))
    else:
        f = _struct_fields(channels[0])
        name = f.get("Name", "")
        default_resp = f.get("DefaultResponse", "")
        trace = f.get("bTraceType", "False").strip().lower()
        m = re.search(r"ECC_GameTraceChannel(\d+)", f.get("Channel", ""))
        problems = []
        if name != CHANNEL_NAME:
            problems.append("name=%r" % name)
        if default_resp != "ECR_Block":
            problems.append("default=%r" % default_resp)
        if trace == "true":
            problems.append("bTraceType=True(trace-channel)")
        if m is None:
            problems.append("channel-slot-unparsed=%r" % f.get("Channel", ""))
        else:
            channel_index = int(m.group(1))
        if problems:
            results["projectile_channel_defined"] = check(
                "projectile_channel_defined", False,
                "PIERCE_CHANNEL_BAD " + " ".join(problems))
            channel_index = None
        else:
            results["projectile_channel_defined"] = check(
                "projectile_channel_defined", True,
                "channel=ECC_GameTraceChannel%d name=%s" % (channel_index,
                                                           CHANNEL_NAME))

    # -- checks 2-4: the three presets, by name, with their graded fields.
    by_name = {}
    for value in profiles:
        f = _struct_fields(value)
        if "Name" in f:
            by_name.setdefault(f["Name"], value)

    def preset_check(cid, preset, object_type, response_rows):
        value = by_name.get(preset)
        if value is None:
            results[cid] = check(cid, False,
                                 "PIERCE_PRESET_MISSING name=%s defined=%s"
                                 % (preset, sorted(by_name)))
            return
        f = _struct_fields(value)
        problems = []
        if f.get("ObjectTypeName", "") != object_type:
            problems.append("object_type=%r expected=%r"
                            % (f.get("ObjectTypeName", ""), object_type))
        for channel, expected in response_rows:
            got = _profile_response_to(value, channel)
            if got != expected:
                problems.append("response[%s]=%s expected=%s"
                                % (channel, got, expected))
        if cid == "bullet_preset_defined":
            enabled = f.get("CollisionEnabled", "")
            if "QueryAndPhysics" not in enabled:
                problems.append("collision_enabled=%r" % enabled)
        if problems:
            results[cid] = check(cid, False,
                                 "PIERCE_PRESET_BAD name=%s %s"
                                 % (preset, " ".join(problems)))
        else:
            results[cid] = check(cid, True, "preset=%s ok" % preset)

    preset_check("bullet_preset_defined", PRESET_BULLET, CHANNEL_NAME,
                 [("WorldStatic", "ECR_Block"), ("Pawn", "ECR_Ignore")])
    preset_check("piercable_preset_defined", PRESET_PIERCABLE, "WorldStatic",
                 [(CHANNEL_NAME, "ECR_Overlap")])
    preset_check("nonpiercable_preset_defined", PRESET_NONPIERCABLE,
                 "WorldStatic", [(CHANNEL_NAME, "ECR_Block")])
    return channel_index, by_name


# --------------------------------------------------------------------------- #
# resolved half: the three Blueprints' SCS component collision state            #
# --------------------------------------------------------------------------- #

def _is_handle(obj):
    try:
        return isinstance(obj, unreal.SubobjectDataHandle)
    except Exception:  # noqa: BLE001
        return False


def _gather_handles(subsystem, blueprint):
    for name in ("gather_subobject_data_for_blueprint",
                 "k2_gather_subobject_data_for_blueprint"):
        fn = getattr(subsystem, name, None)
        if fn is None:
            continue
        out = fn(blueprint)
        if (isinstance(out, (tuple, list)) and len(out) == 2
                and isinstance(out[-1], (tuple, list)) and not _is_handle(out[0])):
            out = out[-1]
        handles = list(out or [])
        if not handles:
            raise RuntimeError("SUBOBJECT_GATHER_EMPTY via %s" % name)
        return handles
    raise AttributeError("SUBOBJECT_GATHER_UNAVAILABLE on %r" % (subsystem,))


def _data_for(handle):
    try:
        res = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(res, (tuple, list)):
        res = res[-1] if res else None
    return res


def _sub_object(data):
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    for name in ("get_object", "get_associated_object"):
        fn = getattr(lib, name, None)
        if fn is None:
            continue
        try:
            obj = fn(data)
        except Exception:  # noqa: BLE001
            continue
        if obj is not None:
            return obj
    return None


def _primitive_components(blueprint):
    """Every PRIMITIVE component template on the Blueprint's SCS chain.
    FAIL-CLOSED: raises rather than returning an unevaluable walk."""
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if subsystem is None:
        raise RuntimeError("SUBOBJECT_SUBSYSTEM_UNAVAILABLE")
    out = []
    for handle in _gather_handles(subsystem, blueprint):
        data = _data_for(handle)
        if data is None:
            continue
        obj = _sub_object(data)
        if obj is None:
            continue
        verdict = _isinstance_tristate(obj, "PrimitiveComponent")
        if verdict is None:
            raise RuntimeError("SUBOBJECT_TYPE_PROBE_ERROR class=%s"
                               % _class_name(obj))
        if verdict:
            out.append(obj)
    return out


def _profile_name_of(comp):
    fn = getattr(comp, "get_collision_profile_name", None)
    if fn is not None:
        try:
            return str(fn())
        except Exception:  # noqa: BLE001
            pass
    bi = _read_property(comp, "body_instance", "BodyInstance")
    return str(_read_property(bi, "collision_profile_name",
                              "CollisionProfileName"))


def _resp_name(value):
    """ECR token of a CollisionResponseType value, spelling-tolerant."""
    s = str(value)
    for token in ("BLOCK", "OVERLAP", "IGNORE"):
        if token in s.upper():
            return "ECR_" + token.capitalize()
    return s


def _response_to(comp, channel_value):
    return _resp_name(comp.get_collision_response_to_channel(channel_value))


# ECC_GameTraceChannel1 == 14 (EngineTypes.h:1520 field comment); the
# ECC_GameTraceChannel* enum entries are UMETA(Hidden) until a project
# names them, so the python enum EXPOSES NO MEMBER for them (live catch
# 2026-08-12, first aid run) - the value must be constructed by integer.
_GAME_TRACE_CHANNEL_BASE = 13  # base + index -> ECC_GameTraceChannel<index>


def _game_trace_channel(index):
    """The CollisionChannel VALUE for ECC_GameTraceChannel<index>.
    Named members first (a project that surfaces the channel may expose
    one), then the integer cast; raises the named token if neither works."""
    names = ("ECC_GAME_TRACE_CHANNEL%d" % index,
             "ECC_GAME_TRACE_CHANNEL_%d" % index)
    for name in names:
        value = getattr(unreal.CollisionChannel, name, None)
        if value is not None:
            return value
    cast = getattr(unreal.CollisionChannel, "cast", None)
    if cast is not None:
        try:
            return cast(_GAME_TRACE_CHANNEL_BASE + index)
        except Exception:  # noqa: BLE001 - named token below
            pass
    raise RuntimeError("PIERCE_CHANNEL_ENUM_UNAVAILABLE index=%d" % index)


def _response_to_game_channel(comp, index):
    """Resolved response to ECC_GameTraceChannel<index>, two routes: the
    channel-value getter, then the response-container UPROPERTY
    (FCollisionResponseContainer.GameTraceChannel<N> is EditAnywhere/
    BlueprintReadOnly - EngineTypes.h:1519)."""
    try:
        return _response_to(comp, _game_trace_channel(index))
    except Exception:  # noqa: BLE001 - container route below
        container = comp.get_collision_response_to_channels()
        return _resp_name(container.get_editor_property(
            "game_trace_channel%d" % index))


def _load_bp(path):
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        return None, "PIERCE_BP_MISSING path=%s" % path
    bp = unreal.EditorAssetLibrary.load_asset(path)
    if bp is None:
        return None, "PIERCE_BP_UNLOADABLE path=%s" % path
    return bp, ""


def _find_wired(bp, preset, want_static_mesh):
    """(component, detail) - the first primitive component carrying the
    wanted preset (and static-mesh identity for the walls). Distinct tokens
    for absent-vs-mismatch so the MATRIX can tell delivery classes apart."""
    comps = _primitive_components(bp)
    if not comps:
        return None, "PIERCE_NO_PRIMITIVE_COMPONENT"
    profiles = []
    for comp in comps:
        name = _profile_name_of(comp)
        profiles.append("%s:%s" % (_class_name(comp), name))
        if name != preset:
            continue
        if want_static_mesh:
            verdict = _isinstance_tristate(comp, "StaticMeshComponent")
            if verdict is None:
                raise RuntimeError("SUBOBJECT_TYPE_PROBE_ERROR class=%s"
                                   % _class_name(comp))
            if not verdict:
                continue
        return comp, "component=%s profile=%s" % (_class_name(comp), name)
    return None, "PIERCE_PROFILE_MISMATCH wanted=%s components=%s" % (
        preset, profiles)


def _overlap_events_on(comp):
    v = _read_property(comp, "generate_overlap_events",
                       "bGenerateOverlapEvents")
    return bool(v)


def _compile_clean(bp):
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    if lib is not None and getattr(lib, "compile_blueprint", None) is not None:
        try:
            lib.compile_blueprint(bp)
        except Exception:  # noqa: BLE001 - status read below stays the gate
            pass
    status = str(_read_property(bp, "status", "Status"))
    return "UP_TO_DATE" in status.upper(), status


def _min_rule(a, b):
    order = {"ECR_Ignore": 0, "ECR_Overlap": 1, "ECR_Block": 2}
    if a not in order or b not in order:
        return "<unevaluable>"
    return a if order[a] <= order[b] else b


def _collect_actors(results, channel_index):
    """Fills checks 5-9 from engine-resolved state."""
    specs = (
        ("bullet_actor_wired", BP_BULLET, PRESET_BULLET, False, True),
        ("piercable_wall_wired", BP_PIERCABLE, PRESET_PIERCABLE, True, True),
        ("nonpiercable_wall_wired", BP_NONPIERCABLE, PRESET_NONPIERCABLE,
         True, False),
    )
    found = {}
    bps = {}
    for cid, path, preset, want_sm, want_overlap in specs:
        try:
            bp, detail = _load_bp(path)
            if bp is None:
                results[cid] = check(cid, False, detail)
                continue
            bps[cid] = bp
            comp, detail = _find_wired(bp, preset, want_sm)
            if comp is None:
                results[cid] = check(cid, False, detail)
                continue
            if want_overlap and not _overlap_events_on(comp):
                results[cid] = check(
                    cid, False,
                    "PIERCE_OVERLAP_EVENTS_OFF %s" % detail)
                continue
            found[cid] = comp
            results[cid] = check(cid, True, detail)
        except Exception as e:  # noqa: BLE001 - probe break = graded FAIL
            results[cid] = check(cid, False, "PIERCE_PROBE_ERROR %r" % e)

    # -- check 5: the both-sides rule from RESOLVED state. Needs the channel
    #    slot (from the ini text) plus the bullet and both wall components.
    cid = "both_sides_rule_holds"
    try:
        missing = [c for c in ("bullet_actor_wired", "piercable_wall_wired",
                               "nonpiercable_wall_wired") if c not in found]
        if channel_index is None:
            results[cid] = check(cid, False,
                                 "PIERCE_BOTH_SIDES_NO_CHANNEL (check 1 failed)")
        elif missing:
            results[cid] = check(cid, False,
                                 "PIERCE_BOTH_SIDES_COMPONENTS_MISSING %s"
                                 % missing)
        else:
            bullet = found["bullet_actor_wired"]
            pierce = found["piercable_wall_wired"]
            solid = found["nonpiercable_wall_wired"]
            b_vs_static = _response_to(bullet, unreal.CollisionChannel.ECC_WORLD_STATIC)
            b_vs_pawn = _response_to(bullet, unreal.CollisionChannel.ECC_PAWN)
            p_vs_proj = _response_to_game_channel(pierce, channel_index)
            s_vs_proj = _response_to_game_channel(solid, channel_index)
            pair_pierce = _min_rule(b_vs_static, p_vs_proj)
            pair_solid = _min_rule(b_vs_static, s_vs_proj)
            ok = (pair_pierce == "ECR_Overlap" and pair_solid == "ECR_Block"
                  and b_vs_pawn == "ECR_Ignore")
            results[cid] = check(
                cid, ok,
                ("resolved: bulletVsStatic=%s bulletVsPawn=%s "
                 "piercableVsProjectile=%s solidVsProjectile=%s "
                 "pair(piercable)=%s pair(solid)=%s")
                % (b_vs_static, b_vs_pawn, p_vs_proj, s_vs_proj,
                   pair_pierce, pair_solid))
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, "PIERCE_PROBE_ERROR %r" % e)

    # -- check 9: all three compile clean (existence gated above).
    cid = "all_three_compile_clean"
    try:
        if len(bps) != 3:
            results[cid] = check(cid, False,
                                 "PIERCE_COMPILE_MISSING_ASSETS have=%d"
                                 % len(bps))
        else:
            statuses = []
            ok = True
            for bp in bps.values():
                clean, status = _compile_clean(bp)
                statuses.append(status)
                ok = ok and clean
            results[cid] = check(cid, ok, "statuses=%s" % statuses)
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, "PIERCE_PROBE_ERROR %r" % e)


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    if unreal is None:
        _fanout(results, CHECK_IDS, "PIERCE_NO_UNREAL_MODULE")
    else:
        try:
            channel_index, _ = _collect_definitions(results)
        except Exception as e:  # noqa: BLE001
            _fanout(results, DEFINITION_CIDS, "PIERCE_PROBE_ERROR %r" % e)
            channel_index = None
        try:
            _collect_actors(results, channel_index)
        except Exception as e:  # noqa: BLE001
            _fanout(results, CHECK_IDS, "PIERCE_PROBE_ERROR %r" % e)
    _fanout(results, CHECK_IDS, "PIERCE_CHECK_UNREACHED")
    emit_verdict([results[cid] for cid in CHECK_IDS])


if __name__ == "__main__":
    main()
