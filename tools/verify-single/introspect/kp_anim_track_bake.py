"""kp-anim-track-bake - L2I introspect: baked numeric track on the walk anim.

Verifier-owned. Runs headless (UnrealEditor-Cmd -ExecutePythonScript= under
-nullrhi), read-only, and prints ONE verdict block between the
CRAFTBENCH-INTROSPECT-JSON markers with EXACTLY 5 named checks on every leg
(constant denominator).

Graded surface: the saved /Game/Tasks/kp-anim-track-bake/AS_TaskWalk asset
only - outcome-graded per the python-basket law (no gate asserts HOW the
track was authored). The variance and span checks read raw KEYS
(AnimationLibrary.get_float_keys), never interpolated samples, so
interpolation tricks have no surface.

Baseline truth: BASELINE_CURVE_NAMES / BASELINE_LENGTH are pinned from the
authoring run and commit WITH the baseline binary (the re-pin law). The
``None`` sentinel fails ``baseline_state_intact`` CLOSED - a fresh checkout
with an unpinned grader must refuse to certify, never silently pass.

Failure tokens are single greppable ANIMBAKE_* literals; the error class
(ANIMBAKE_PROBE_ERROR / ANIMBAKE_CHECK_UNREACHED) is disjoint from every
credited token.
"""

from __future__ import annotations

import json

try:
    import unreal  # type: ignore
except Exception:  # noqa: BLE001 - emit an all-fail verdict outside UE
    unreal = None


TASK_ID = "kp-anim-track-bake"
ASSET_PATH = "/Game/Tasks/kp-anim-track-bake/AS_TaskWalk"

# --- pinned baseline truth (authoring run 2026-08-12, KPBAKE-BASELINE line:
#     the stock unarmed walk duplicate carries ZERO float tracks, 1.5s clip;
#     re-pin on any baseline regeneration - the None sentinel fails closed) ---
BASELINE_CURVE_NAMES = ()
BASELINE_LENGTH = 1.5

LENGTH_TOLERANCE = 0.01
VALUE_EPSILON = 0.001
SPAN_FRACTION = 0.1  # first key within the opening tenth, last within closing

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

CHECK_IDS = (
    "task_walk_asset_resolves",
    "baseline_state_intact",
    "new_named_track_exists",
    "new_track_varies",
    "new_track_spans_timeline",
)


def _defang(text, cap=500):
    """Neutralize agent-controlled text (track names) before the verdict."""
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
# read routes                                                                   #
# --------------------------------------------------------------------------- #

def _float_track_type():
    enum = getattr(unreal, "RawCurveTrackTypes", None)
    if enum is None:
        raise RuntimeError("ANIMBAKE_ENUM_UNAVAILABLE RawCurveTrackTypes")
    for spelling in ("RCT_FLOAT", "RCT_Float"):
        value = getattr(enum, spelling, None)
        if value is not None:
            return value
    raise RuntimeError("ANIMBAKE_ENUM_UNAVAILABLE RCT_FLOAT")


def _load_sequence():
    if not unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        raise RuntimeError("ANIMBAKE_ASSET_MISSING path=%s" % ASSET_PATH)
    seq = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if seq is None:
        raise RuntimeError("ANIMBAKE_ASSET_UNLOADABLE path=%s" % ASSET_PATH)
    cls = getattr(unreal, "AnimSequenceBase", None)
    if cls is None or not isinstance(seq, cls):
        raise RuntimeError("ANIMBAKE_NOT_ANIM_SEQUENCE class=%s"
                           % seq.get_class().get_name())
    return seq


def _curve_names(seq):
    out = unreal.AnimationLibrary.get_animation_curve_names(
        seq, _float_track_type())
    return [str(n) for n in (out or [])]


def _sequence_length(seq):
    fn = getattr(unreal.AnimationLibrary, "get_sequence_length", None)
    if fn is not None:
        try:
            out = fn(seq)
            if isinstance(out, (tuple, list)):
                out = out[-1]
            return float(out)
        except Exception:  # noqa: BLE001 - property fallback below
            pass
    for name in ("sequence_length", "SequenceLength"):
        try:
            return float(seq.get_editor_property(name))
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("ANIMBAKE_LENGTH_UNREADABLE")


def _float_keys(seq, name):
    out = unreal.AnimationLibrary.get_float_keys(seq, name)
    if isinstance(out, (tuple, list)) and len(out) == 2:
        times, values = out
    else:
        raise RuntimeError("ANIMBAKE_KEYS_UNREADABLE track=%s" % name)
    return [float(t) for t in (times or [])], [float(v) for v in (values or [])]


# --------------------------------------------------------------------------- #
# checks                                                                        #
# --------------------------------------------------------------------------- #

def run_checks(results):
    try:
        seq = _load_sequence()
    except Exception as e:  # noqa: BLE001
        results["task_walk_asset_resolves"] = check(
            "task_walk_asset_resolves", False, str(e))
        _fanout(results, CHECK_IDS, "ANIMBAKE_ASSET_UNRESOLVED (see check 1)")
        return
    results["task_walk_asset_resolves"] = check(
        "task_walk_asset_resolves", True, "loaded %s" % ASSET_PATH)

    names = _curve_names(seq)
    length = _sequence_length(seq)

    # -- check 2: the pinned-baseline guard (fails closed while unpinned).
    cid = "baseline_state_intact"
    if BASELINE_CURVE_NAMES is None or BASELINE_LENGTH is None:
        results[cid] = check(cid, False,
                             "ANIMBAKE_BASELINE_UNPINNED pin BASELINE_* "
                             "from the authoring run before certifying")
        baseline = set()
    else:
        baseline = set(BASELINE_CURVE_NAMES)
        missing = sorted(baseline - set(names))
        drift = abs(length - float(BASELINE_LENGTH))
        if missing:
            results[cid] = check(cid, False,
                                 "ANIMBAKE_BASELINE_CURVE_REMOVED missing=%s"
                                 % missing)
        elif drift > LENGTH_TOLERANCE:
            results[cid] = check(cid, False,
                                 "ANIMBAKE_LENGTH_CHANGED got=%.4f pinned=%.4f"
                                 % (length, float(BASELINE_LENGTH)))
        else:
            results[cid] = check(cid, True,
                                 "baseline tracks + length intact (%.4fs)"
                                 % length)

    # -- check 3: a NEW named track exists.
    new_names = [n for n in names if n not in baseline]
    cid = "new_named_track_exists"
    if not new_names:
        results[cid] = check(cid, False,
                             "ANIMBAKE_NO_NEW_TRACK baseline=%d tracks, "
                             "found=%d" % (len(baseline), len(names)))
    else:
        results[cid] = check(cid, True, "new tracks=%s" % new_names)

    # -- checks 4-5: some new track varies first->last key, and THAT track's
    #    keys span the outer tenths of the clip. Read raw KEYS only.
    varying = []  # (name, times, values)
    flat_details = []
    for name in new_names:
        try:
            times, values = _float_keys(seq, name)
        except Exception as e:  # noqa: BLE001
            flat_details.append("%s:%s" % (name, e))
            continue
        if len(values) >= 2 and abs(values[-1] - values[0]) > VALUE_EPSILON:
            varying.append((name, times, values))
        else:
            delta = (abs(values[-1] - values[0])
                     if len(values) >= 2 else "single-key")
            flat_details.append("%s:delta=%s" % (name, delta))

    cid = "new_track_varies"
    if not new_names:
        results[cid] = check(cid, False,
                             "ANIMBAKE_NO_NEW_TRACK (check 3 failed)")
    elif not varying:
        results[cid] = check(cid, False,
                             "ANIMBAKE_ALL_NEW_TRACKS_FLAT %s" % flat_details)
    else:
        results[cid] = check(cid, True,
                             "varying=%s" % [v[0] for v in varying])

    cid = "new_track_spans_timeline"
    if not varying:
        results[cid] = check(cid, False,
                             "ANIMBAKE_NO_VARYING_TRACK (check 4 failed)")
    else:
        spanning = None
        spans = []
        lo, hi = SPAN_FRACTION * length, (1.0 - SPAN_FRACTION) * length
        for name, times, _values in varying:
            first, last = min(times), max(times)
            spans.append("%s:[%.3f..%.3f]" % (name, first, last))
            if first <= lo and last >= hi:
                spanning = name
                break
        if spanning is None:
            results[cid] = check(
                cid, False,
                "ANIMBAKE_TRACK_SPAN_SHORT need=[<=%.3f..>=%.3f] got=%s"
                % (lo, hi, spans))
        else:
            results[cid] = check(cid, True,
                                 "track=%s spans [%.3f..%.3f] of %.3fs clip"
                                 % (spanning, lo, hi, length))


def main():
    results = {}
    if unreal is None:
        _fanout(results, CHECK_IDS, "ANIMBAKE_NO_UNREAL_MODULE")
    else:
        try:
            run_checks(results)
        except Exception as e:  # noqa: BLE001 - probe break = graded FAIL
            _fanout(results, CHECK_IDS, "ANIMBAKE_PROBE_ERROR %r" % e)
    _fanout(results, CHECK_IDS, "ANIMBAKE_CHECK_UNREACHED")
    emit_verdict([results[cid] for cid in CHECK_IDS])


if __name__ == "__main__":
    main()
