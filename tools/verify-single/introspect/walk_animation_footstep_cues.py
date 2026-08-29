"""L2-introspect script for the t1-walk-animation-footstep-cues task.

Structural, READ-ONLY verification of two animation clip assets via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R10, re-scoped; see the task spec's
"Provenance and the deliberate scope cut"):
the shipped duplicate walk clip must carry EXACTLY TWO instantaneous timeline
cues named ``Footstep``, one at 0.25 s and one at 0.75 s, with nothing else on
its timeline, its own length and frame count untouched, while the sibling jog
clip stays completely silent.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** (``ASSET_WALK`` / ``ASSET_JOG``)
    and pre-declared cue NAME (``CUE_NAME``), never by class.
  * Stock UE Python only (``EditorAssetLibrary``, ``AnimationLibrary``,
    reflection). Never Aura's MCP tools - that would grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **FAIL CLOSED.** No check may pass on the strength of "a probe did not
    raise". The sharp edge here is the NEGATIVE check ``jog_carries_no_cues``:
    unlike the pilot's subobject walk, an EMPTY cue list is a legitimate state
    for an animation clip, so "empty means broken" cannot be the guard.
    ``_cue_events`` instead demands that the accessor EXIST, that it return a
    SEQUENCE type, and that a second independent accessor
    (``get_animation_notify_event_names``) agree about emptiness - and it
    demands a positive read off the same object (it loaded as an animation
    sequence with a non-zero length). Anything else RAISES and the negative
    check records an error token that no MATRIX row can credit.
  * The check list has a **constant length (10)** on every leg, including a
    missing clip. ``registry.py`` reports ``tests_passed/tests_run`` from these
    counts, so a constant denominator keeps the ratio comparable and stops a
    submission from improving its score by making checks unreachable.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string **as printed inside the JSON block**, not on
the layer's ``<script>:<check>: FAIL - ...`` note rendering, so each failing
check owns a unique ``*_WRONG`` / ``*_MISSING`` / ``*_CHANGED`` / ``*_NOT_*``
token that never appears on the passing branch. No detail contains either of
the two automation result markers ("TestResult" + "=Passed", and
"Automation Test" + " Succeeded") that ``parse_automation_log``'s whole-file
``finditer`` counts as a TEST - a detail carrying one would inflate the test
tally and can flip a PASS to a FAIL through the ``expected_test_count`` guard.
Neither substring appears anywhere in this file, including this docstring.

UE 5.8 API notes (every route checked against engine source on this box,
<UE_ROOT>; plan the introspection-coverage plan section 10 confirmed
the AnimationLibrary family live on UE 5.8.0-55116800):
  * ``UAnimSequenceBase::Notifies`` is reflection-DENIED, so the cue list is
    read through the public library instead:
    ``Editor/AnimationBlueprintLibrary/Public/AnimationBlueprintLibrary.h``
    - ``GetAnimationNotifyEvents``      (BlueprintPure, :232)
    - ``GetAnimationNotifyEventNames``  (BlueprintPure, :236)
    - ``GetAnimNotifyEventTriggerTime`` (BlueprintPure, :318)
    - ``GetAnimNotifyEventDuration``    (BlueprintPure, :322)
    - ``GetSequenceLength``             (BlueprintPure, :598)
    - ``GetNumFrames``                  (BlueprintPure, :73)
    The UCLASS carries ``meta=(ScriptName="AnimationLibrary")`` (:65), which is
    why the Python spelling is ``unreal.AnimationLibrary``. It is an **Editor**
    module (Engine/Source/Editor/AnimationBlueprintLibrary), always loaded in
    ``UnrealEditor-Cmd``; no plugin has to be enabled.
  * On the cue struct itself
    (``Runtime/Engine/Public/Animation/AnimTypes.h``, ``FAnimNotifyEvent``):
    ``NotifyName`` is ``EditAnywhere, BlueprintReadOnly`` -> READABLE.
    ``NotifyStateClass`` is ``EditAnywhere, Instanced, BlueprintReadWrite``
    -> READABLE (used only as corroboration).
    ``Duration`` and ``TrackIndex`` are bare ``UPROPERTY()`` -> DENIED, which
    is exactly why the duration comes from the UFUNCTION and not the field.
  * Python property readability is ``CPF_Edit | CPF_BlueprintVisible |
    CPF_BlueprintAssignable`` only (``PropertyAccessUtil.cpp:425-433``).
  * The length/frame oracle is the STOCK clip at ``ORACLE_WALK``. That path is
    agent-DENY-listed (``UE-projects/ThirdPerson/AGENT_WRITABLE.json``:
    ``Content/Characters/``) and is NOT pruned by fairness isolation
    (``tools/run-agent/fairness.py:85`` prunes only ``Content/Tasks``,
    ``Content/Maps`` and the two ``Source/*/Tasks`` roots), so the verifier can
    read a value the submission provably cannot have moved. Deny-listing
    governs agent WRITES, not verifier reads.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and a cue NAME, never a class) -----
TASK_ID = "t1-walk-animation-footstep-cues"
ASSET_WALK = "/Game/Tasks/%s/A_WalkForward" % TASK_ID
ASSET_JOG = "/Game/Tasks/%s/A_JogForward" % TASK_ID

# The untouched stock clip the two baselines were duplicated from. Verifier-read
# only; agent-deny-listed and fairness-safe (see the module docstring).
ORACLE_WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"

CUE_NAME = "Footstep"

# --- Graded scalars ----------------------------------------------------------
EXPECTED_CUE_COUNT = 2
QUARTER_SECOND = 0.25
THREE_QUARTER_SECOND = 0.75
# +/-0.02 s is a little over half a frame at 30 fps: it absorbs the editor's
# frame snapping and FAnimNotifyEvent's TriggerTimeOffset without letting a
# genuinely mis-placed cue through (the two graded moments are 0.5 s apart).
TIME_TOL = 0.02
# "Instantaneous" means duration 0. A ranged cue (an anim notify STATE) reads
# back its span here.
DURATION_TOL = 1e-3
LENGTH_TOL = 0.01

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "walk_asset_exists",
    "walk_has_exactly_two_footstep_cues",
    "walk_footstep_at_quarter_second",
    "walk_footstep_at_three_quarter_second",
    "walk_footsteps_are_instantaneous",
    "walk_carries_no_other_cues",
    "walk_timeline_length_unchanged",
    "walk_frame_count_unchanged",
    "jog_asset_exists",
    "jog_carries_no_cues",
)

WALK_MISSING_TOKEN = "WALK_ASSET_MISSING"
JOG_MISSING_TOKEN = "JOG_ASSET_MISSING"
CUE_COUNT_TOKEN = "WALK_FOOTSTEP_COUNT_WRONG"


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
# small reflection helpers (each defensive; callers wrap in try/except)         #
# --------------------------------------------------------------------------- #

def _asset_exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is.

    UE pythonizes UPROPERTY names (``NotifyName`` -> ``notify_name``), but
    which spelling ``get_editor_property`` resolves has bitten this repo
    before, so both are tried. It never invents a value - if every spelling
    fails the last exception propagates and the caller records a *_READ_ERROR.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _anim_lib():
    """The AnimationLibrary function library. RAISES if it is not exposed."""
    lib = getattr(unreal, "AnimationLibrary", None)
    if lib is None:
        raise AttributeError("ANIM_LIBRARY_UNAVAILABLE unreal.AnimationLibrary")
    return lib


def _scalar_out(fn, *args):
    """Call a UFUNCTION expected to yield exactly ONE number.

    UE's Python codegen returns a bare value for a single out-param, but a
    ``(return_value, out)`` tuple when there is a return value as well. Both
    shapes are handled by picking the single non-bool numeric element - a
    positional ``res[-1]`` would silently mis-read a shape change, and this is
    the one place where a wrong number becomes a wrong verdict. Anything that
    is not exactly one number RAISES.
    """
    res = fn(*args)
    if isinstance(res, (tuple, list)):
        numeric = [v for v in res
                   if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numeric) != 1:
            raise RuntimeError("SCALAR_OUT_UNAVAILABLE shape=%r" % (res,))
        res = numeric[0]
    if res is None or isinstance(res, bool) or not isinstance(res, (int, float)):
        raise RuntimeError("SCALAR_OUT_UNAVAILABLE got=%r" % (res,))
    return res


def _array_out(fn, *args):
    """Call a UFUNCTION expected to yield an ARRAY, and return it as a list.

    Deliberately does NOT reuse the scalar unwrapper: an array of exactly two
    elements matches the ``(return_value, out)`` tuple shape, and unwrapping it
    would drop a cue and grade the wrong thing on the very submission the task
    is calibrated on.
    """
    res = fn(*args)
    if res is None:
        raise RuntimeError("ARRAY_OUT_UNAVAILABLE from %r" % (fn,))
    if isinstance(res, (str, bytes)) or not hasattr(res, "__iter__"):
        raise RuntimeError("ARRAY_OUT_UNAVAILABLE shape=%s" % type(res).__name__)
    return list(res)


def _load_sequence(path):
    """The animation clip at ``path``. RAISES unless it really is one.

    FAIL-CLOSED: ``load_asset`` returning something non-animation (or nothing)
    must never be treated as "an animation with no cues".
    """
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError("SEQUENCE_LOAD_UNAVAILABLE %s" % path)
    base = getattr(unreal, "AnimSequenceBase", None)
    if base is not None and not isinstance(asset, base):
        raise RuntimeError("SEQUENCE_TYPE_WRONG %s is %s"
                           % (path, _class_name(asset)))
    return asset


def _class_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_class().get_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _cue_events(sequence, path):
    """Every timeline cue on ``sequence`` as a list. RAISES on any doubt.

    FAIL-CLOSED, and the rules differ from the pilot's subobject walk because
    ZERO cues is a legitimate state for an animation clip - so "empty means
    broken" is not available as a guard. What is demanded instead:

      1. ``AnimationLibrary.GetAnimationNotifyEvents`` exists and returns a
         SEQUENCE type (not None, not a bool, not a scalar);
      2. the independent accessor ``GetAnimationNotifyEventNames`` also exists,
         also returns a sequence, and AGREES about emptiness - two accessors
         reading different storage cannot both be silently broken the same way;
      3. the caller has already proven the object is a real animation sequence
         with a positive length (``_load_sequence`` + the length read).

    Any violation raises, and the negative check that depends on it records an
    error token that appears in no MATRIX row.
    """
    lib = _anim_lib()
    getter = getattr(lib, "get_animation_notify_events", None)
    if getter is None:
        raise AttributeError("CUE_READER_UNAVAILABLE get_animation_notify_events")
    events = _array_out(getter, sequence)

    name_getter = getattr(lib, "get_animation_notify_event_names", None)
    if name_getter is None:
        raise AttributeError("CUE_READER_UNAVAILABLE get_animation_notify_event_names")
    names = _array_out(name_getter, sequence)
    if bool(events) != bool(names):
        raise RuntimeError("CUE_READER_UNAVAILABLE disagreement events=%d names=%d on %s"
                           % (len(events), len(names), path))
    return events


def _cue_name(event):
    """The authored name of a cue, as a plain string. Raises if unreadable."""
    return str(_read_property(event, "notify_name", "NotifyName"))


def _cue_names(events):
    out = []
    for event in events:
        try:
            out.append(_cue_name(event))
        except Exception:  # noqa: BLE001 - an unnamed cue still counts as one
            out.append("<unreadable>")
    return out


def _cue_trigger_time(event):
    return float(_scalar_out(_anim_lib().get_anim_notify_event_trigger_time, event))


def _cue_duration(event):
    return float(_scalar_out(_anim_lib().get_anim_notify_event_duration, event))


def _cue_state_class(event):
    """The ranged-cue backing object, or None. Corroboration only."""
    try:
        return _read_property(event, "notify_state_class", "NotifyStateClass")
    except Exception:  # noqa: BLE001
        return None


def _sequence_length(sequence):
    return float(_scalar_out(_anim_lib().get_sequence_length, sequence))


def _sequence_frames(sequence):
    return int(_scalar_out(_anim_lib().get_num_frames, sequence))


def _round3(value):
    """Stable, locale-free number rendering for detail strings."""
    return "%.3f" % float(value)


def _round3_list(values):
    return "[%s]" % ", ".join(_round3(v) for v in values)


def _one_cue_at(times, target):
    """(ok, matches) for "exactly one cue sits at ``target``"."""
    matches = [t for t in times if abs(t - target) <= TIME_TOL]
    return len(matches) == 1, matches


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _fanout(results, prefix, detail):
    for cid in CHECK_IDS:
        if cid.startswith(prefix) and cid not in results:
            results[cid] = check(cid, False, detail)


def _walk_checks(results):
    """Fill ``results`` for every walk-clip check. Constant emission."""
    # A raised probe is NOT the same event as a genuinely absent asset, and the
    # two must not share a token: an API break that fanned out
    # WALK_ASSET_MISSING would be credited as a variant's named failure.
    try:
        exists = _asset_exists(ASSET_WALK)
    except Exception as e:  # noqa: BLE001
        detail = "WALK_ASSET_PROBE_ERROR %s raised %r" % (ASSET_WALK, e)
        results["walk_asset_exists"] = check("walk_asset_exists", False, detail)
        _fanout(results, "walk_", detail)
        return

    if not exists:
        detail = "%s %s" % (WALK_MISSING_TOKEN, ASSET_WALK)
        results["walk_asset_exists"] = check("walk_asset_exists", False, detail)
        _fanout(results, "walk_", detail)
        return
    results["walk_asset_exists"] = check(
        "walk_asset_exists", True, "WALK_ASSET_OK path=%s" % ASSET_WALK)

    # --- load + the two shape reads the cue reader depends on ----------------
    try:
        walk = _load_sequence(ASSET_WALK)
        walk_length = _sequence_length(walk)
        if not walk_length > 0.0:
            raise RuntimeError("SEQUENCE_LENGTH_UNAVAILABLE length=%s" % walk_length)
    except Exception as e:  # noqa: BLE001
        detail = "WALK_LOAD_READ_ERROR %s raised %r" % (ASSET_WALK, e)
        _fanout(results, "walk_", detail)
        return

    # --- the cue list (shared by four checks) --------------------------------
    events = None
    try:
        events = _cue_events(walk, ASSET_WALK)
    except Exception as e:  # noqa: BLE001
        detail = "WALK_CUE_READ_ERROR raised %r" % (e,)
        for cid in ("walk_has_exactly_two_footstep_cues",
                    "walk_footstep_at_quarter_second",
                    "walk_footstep_at_three_quarter_second",
                    "walk_footsteps_are_instantaneous",
                    "walk_carries_no_other_cues"):
            results[cid] = check(cid, False, detail)

    if events is not None:
        names = _cue_names(events)
        footsteps = [e for e, n in zip(events, names) if n == CUE_NAME]
        count_ok = len(footsteps) == EXPECTED_CUE_COUNT
        count_detail = ("WALK_FOOTSTEP_COUNT_OK found=%d names=%s"
                        % (len(footsteps), sorted(names))) if count_ok else (
            "%s found=%d expected=%d names=%s"
            % (CUE_COUNT_TOKEN, len(footsteps), EXPECTED_CUE_COUNT, sorted(names)))
        results["walk_has_exactly_two_footstep_cues"] = check(
            "walk_has_exactly_two_footstep_cues", count_ok, count_detail)

        if not count_ok:
            # One root cause, three dependent checks. Same token on purpose:
            # the MATRIX blames the count check, and the per-check oracle test
            # pins the substring to it.
            for cid in ("walk_footstep_at_quarter_second",
                        "walk_footstep_at_three_quarter_second",
                        "walk_footsteps_are_instantaneous"):
                results[cid] = check(cid, False, count_detail)
        else:
            # --- placement ---------------------------------------------------
            times = None
            try:
                times = sorted(_cue_trigger_time(e) for e in footsteps)
            except Exception as e:  # noqa: BLE001
                detail = "WALK_CUE_TIME_READ_ERROR raised %r" % (e,)
                results["walk_footstep_at_quarter_second"] = check(
                    "walk_footstep_at_quarter_second", False, detail)
                results["walk_footstep_at_three_quarter_second"] = check(
                    "walk_footstep_at_three_quarter_second", False, detail)
            if times is not None:
                ok, matched = _one_cue_at(times, QUARTER_SECOND)
                results["walk_footstep_at_quarter_second"] = check(
                    "walk_footstep_at_quarter_second", ok,
                    ("WALK_CUE_QUARTER_OK t=%s" % _round3(matched[0])) if ok
                    else ("WALK_CUE_NOT_AT_QUARTER_SECOND times=%s expected=%s tol=%s"
                          % (_round3_list(times), _round3(QUARTER_SECOND),
                             _round3(TIME_TOL))))
                ok, matched = _one_cue_at(times, THREE_QUARTER_SECOND)
                results["walk_footstep_at_three_quarter_second"] = check(
                    "walk_footstep_at_three_quarter_second", ok,
                    ("WALK_CUE_THREE_QUARTER_OK t=%s" % _round3(matched[0])) if ok
                    else ("WALK_CUE_NOT_AT_THREE_QUARTER_SECOND times=%s expected=%s tol=%s"
                          % (_round3_list(times), _round3(THREE_QUARTER_SECOND),
                             _round3(TIME_TOL))))

            # --- instantaneous, not ranged -----------------------------------
            try:
                durations = [_cue_duration(e) for e in footsteps]
                ranged = [d for d in durations if abs(d) > DURATION_TOL]
                # Corroboration: a ranged cue is backed by a state object. This
                # can only ADD a failure - it never rescues a bad duration.
                state_backed = sum(1 for e in footsteps
                                   if _cue_state_class(e) is not None)
                ok = not ranged and state_backed == 0
                results["walk_footsteps_are_instantaneous"] = check(
                    "walk_footsteps_are_instantaneous", ok,
                    ("WALK_CUE_INSTANT_OK durations=%s" % _round3_list(durations))
                    if ok else
                    ("WALK_CUE_NOT_INSTANTANEOUS durations=%s ranged=%d state_backed=%d"
                     % (_round3_list(durations), len(ranged), state_backed)))
            except Exception as e:  # noqa: BLE001
                results["walk_footsteps_are_instantaneous"] = check(
                    "walk_footsteps_are_instantaneous", False,
                    "WALK_CUE_DURATION_READ_ERROR raised %r" % (e,))

        # --- nothing else on the timeline ------------------------------------
        total_ok = len(events) == EXPECTED_CUE_COUNT
        results["walk_carries_no_other_cues"] = check(
            "walk_carries_no_other_cues", total_ok,
            ("WALK_CUE_TOTAL_OK total=%d" % len(events)) if total_ok
            else ("WALK_CUE_TOTAL_WRONG total=%d expected=%d names=%s"
                  % (len(events), EXPECTED_CUE_COUNT, sorted(names))))

    # --- the clip itself is the shipped one ----------------------------------
    oracle = None
    oracle_error = None
    try:
        oracle = _load_sequence(ORACLE_WALK)
    except Exception as e:  # noqa: BLE001
        oracle_error = "WALK_ORACLE_UNAVAILABLE %s raised %r" % (ORACLE_WALK, e)

    try:
        if oracle is None:
            raise RuntimeError(oracle_error or "WALK_ORACLE_UNAVAILABLE no oracle")
        oracle_length = _sequence_length(oracle)
        ok = abs(walk_length - oracle_length) <= LENGTH_TOL
        results["walk_timeline_length_unchanged"] = check(
            "walk_timeline_length_unchanged", ok,
            ("WALK_LENGTH_OK length=%s" % _round3(walk_length)) if ok
            else ("WALK_LENGTH_CHANGED length=%s expected=%s tol=%s"
                  % (_round3(walk_length), _round3(oracle_length),
                     _round3(LENGTH_TOL))))
    except Exception as e:  # noqa: BLE001
        results["walk_timeline_length_unchanged"] = check(
            "walk_timeline_length_unchanged", False,
            "WALK_LENGTH_READ_ERROR raised %r" % (e,))

    try:
        if oracle is None:
            raise RuntimeError(oracle_error or "WALK_ORACLE_UNAVAILABLE no oracle")
        walk_frames = _sequence_frames(walk)
        oracle_frames = _sequence_frames(oracle)
        ok = walk_frames == oracle_frames
        results["walk_frame_count_unchanged"] = check(
            "walk_frame_count_unchanged", ok,
            ("WALK_FRAME_COUNT_OK frames=%d" % walk_frames) if ok
            else ("WALK_FRAME_COUNT_CHANGED frames=%d expected=%d"
                  % (walk_frames, oracle_frames)))
    except Exception as e:  # noqa: BLE001
        results["walk_frame_count_unchanged"] = check(
            "walk_frame_count_unchanged", False,
            "WALK_FRAME_READ_ERROR raised %r" % (e,))


def _jog_checks(results):
    """The sibling clip must come back silent. Runs whatever the walk did."""
    try:
        exists = _asset_exists(ASSET_JOG)
    except Exception as e:  # noqa: BLE001
        detail = "JOG_ASSET_PROBE_ERROR %s raised %r" % (ASSET_JOG, e)
        results["jog_asset_exists"] = check("jog_asset_exists", False, detail)
        results["jog_carries_no_cues"] = check("jog_carries_no_cues", False, detail)
        return

    if not exists:
        # FAIL-CLOSED: a missing sibling is NOT "the sibling is silent".
        detail = "%s %s" % (JOG_MISSING_TOKEN, ASSET_JOG)
        results["jog_asset_exists"] = check("jog_asset_exists", False, detail)
        results["jog_carries_no_cues"] = check("jog_carries_no_cues", False, detail)
        return
    results["jog_asset_exists"] = check(
        "jog_asset_exists", True, "JOG_ASSET_OK path=%s" % ASSET_JOG)

    try:
        jog = _load_sequence(ASSET_JOG)
        jog_length = _sequence_length(jog)
        if not jog_length > 0.0:
            raise RuntimeError("SEQUENCE_LENGTH_UNAVAILABLE length=%s" % jog_length)
        events = _cue_events(jog, ASSET_JOG)
        names = sorted(_cue_names(events))
        clean = len(events) == 0
        results["jog_carries_no_cues"] = check(
            "jog_carries_no_cues", clean,
            ("JOG_CLEAN_OK total=0 length=%s" % _round3(jog_length)) if clean
            else ("JOG_HAS_CUES names=%s total=%d" % (names, len(events))))
    except Exception as e:  # noqa: BLE001
        # Every failure mode of the reader lands here with a token no MATRIX
        # row carries, so a broken API can never be credited as "silent".
        results["jog_carries_no_cues"] = check(
            "jog_carries_no_cues", False, "JOG_CUE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _walk_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, "walk_", "WALK_INTROSPECTION_ABORTED %r" % (e,))
    try:
        _jog_checks(results)
    except Exception as e:  # noqa: BLE001
        _fanout(results, "jog_", "JOG_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
