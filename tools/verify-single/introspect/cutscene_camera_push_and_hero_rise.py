"""L2-introspect script for the t2-cutscene-camera-push-and-hero-rise task.

Structural, READ-ONLY verification of ONE LevelSequence asset via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R9, re-pathed / re-tiered / de-dead-gated; see the
task spec): a six-second, 24 fps cutscene asset that spawns its OWN camera and
its own hero, cuts to that camera for the whole shot, pushes the camera in
along X from -500 to -150 over the full six seconds, raises the hero from
Z=0 to Z=200 over the first three seconds and then HOLDS, and opens with a
fade up from black over the first half-second.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** (``ASSET_SEQUENCE``) and
    pre-declared binding NAME (``HERO_BINDING_NAME``), never by class. The one
    place a class is consulted is an assertion itself ("the cut targets a
    cinematic camera"), which is the graded property, not the lookup key - and
    it is written as an ``isinstance`` so a legitimate subclass is not
    penalized.
  * Stock UE Python only (``EditorAssetLibrary``, the SequencerScripting
    extension libraries, reflection). Never Aura's MCP tools - that would
    grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **MOTION IS GRADED ON ITS SHAPE, NOT ON ITS ENDPOINTS.** ``_eval_curve``
    holds the value outside the keyed range, so two endpoint samples cannot
    distinguish a six-second push-in from a 0.2-second snap sandwiched between
    two long holds - which scored 12/12 until 2026-07-27. The camera push is
    therefore sampled every ``PUSH_SAMPLE_STEP_S`` across the whole shot by
    ``_push_shape`` and must be keyed across the shot, monotonic toward the
    target, and spread over the shot within ``PUSH_PROGRESS_TOL``. The band is
    wide enough that an EASED push passes; only a snap or a reversal fails.
  * **FAIL CLOSED.** No check may pass on the strength of "a probe did not
    raise" or "the walk came back empty". Every PASS needs a positive read:
    an empty track list, an empty binding list, an empty channel list or an
    empty key list is a FAILURE, never a free pass. ``-1.0`` is what the
    SequencerScripting seconds-accessors return on a null/unbounded input, so
    every numeric comparison is an equality-within-tolerance against a
    REQUIRED value and never a "not obviously wrong" test.
  * The check list has a **constant length (12)** on every leg, including a
    missing asset. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a constant denominator keeps the ratio comparable and
    stops a submission from improving its score by making checks unreachable.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string **as printed inside the JSON block**, not on
the layer's ``<script>:<check>: FAIL - ...`` note rendering, so each failing
check owns a unique ``*_MISSING`` / ``*_WRONG`` / ``*_NOT_*`` token that never
appears on the passing branch. No detail contains either of the two automation
result markers ("TestResult" + "=Passed", and "Automation Test" +
" Succeeded") that ``parse_automation_log``'s whole-file ``finditer`` counts as
a TEST - a detail carrying one would inflate the test tally and can flip a PASS
to a FAIL through the ``expected_test_count`` guard. Neither substring appears
anywhere in this file, including this docstring.

UE 5.8 API notes (every route below was read out of engine source at
``<UE_ROOT>``; the family was additionally confirmed present on a live
UE 5.8.0-55116800 headless editor, plan
the introspection-coverage plan section 10.1):

  * ``MovieSceneSequenceExtensions`` / ``MovieSceneBindingExtensions`` /
    ``MovieSceneTrackExtensions`` / ``MovieSceneSectionExtensions`` live in the
    **SequencerScripting** plugin, which has no ``EnabledByDefault`` of its
    own - it is pulled in transitively by ``LevelSequenceEditor.uplugin``
    (``"EnabledByDefault": true`` + a ``"Plugins": [{"SequencerScripting",
    Enabled}]`` dependency). So it is live in any editor session of either
    substrate without a ``.uproject`` edit, which matters because
    ``.uproject`` and ``Plugins/`` are both deny-listed to the agent.
  * ``UMovieSceneSectionExtensions::GetChannel`` is ``#if WITH_EDITORONLY_DATA``
    and resolves by the channel's editor metadata name ("Location.X", ...),
    which only exists in an editor build. L2I always runs an editor binary, so
    this is fine - but a null return is treated as a FAILED read, never as
    "no keys".
  * ``UMovieSceneFadeSection``'s channel is registered with a
    default-constructed ``FMovieSceneChannelMetaData()``, i.e. its name is
    ``NAME_None`` (``MovieSceneFadeSection.cpp``). ``get_channel(section,
    "Fade")`` therefore does NOT work; the fade curve is reached through
    ``get_all_channels`` instead.
  * ``UMovieSceneFadeSection``'s constructor calls
    ``SetRange(TRange<FFrameNumber>::All())``, so the fade section is
    INFINITE and ``has_start_frame()`` is false. The fade is graded on its
    KEYS, never on its section bounds.
  * Key times are read in ``EMovieSceneTimeUnit.TICK_RESOLUTION`` and divided
    by the sequence's tick resolution, so no sub-frame rounding enters the
    comparison.
  * ``FMovieSceneObjectBindingID::Guid`` is ``UPROPERTY(EditAnywhere)`` and
    ``UMovieSceneCameraCutSection::GetCameraBindingID`` is a
    ``UFUNCTION(BlueprintPure)`` (``MovieSceneCameraCutSection.h``), so the
    cut's target binding is readable by both routes.
  * ``UMovieSceneSequenceExtensions::GetSpawnables`` covers BOTH the legacy
    ``FMovieSceneSpawnable`` array and 5.8's
    ``UMovieSceneSpawnableActorBinding`` custom bindings, so "the sequence
    spawns its own actor" is one read regardless of which representation the
    agent's tooling produced.

DEAD GATES deliberately NOT asserted here (each would grade nothing - see the
spec's "Dead-gate audit"): the camera's rotation (facing the origin from
X=-500 is yaw/pitch/roll 0, the engine default for any actor), the fade
colour (``FadeColor(FLinearColor::Black)`` is the constructor default), and
the sheet's own "5 seconds at 30 fps" (``MovieSceneToolsProjectSettings``
``DefaultStartTime=0``/``DefaultDuration=5`` and
``LevelSequenceProjectSettings::DefaultDisplayRate="30fps"`` are what
``ULevelSequenceFactoryNew`` stamps onto every brand-new sequence).
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATH and binding NAME, never class) ------
TASK_ID = "t2-cutscene-camera-push-and-hero-rise"
ASSET_SEQUENCE = "/Game/Tasks/%s/SEQ_EvalCutscene" % TASK_ID

HERO_BINDING_NAME = "EvalHero"

# --- Graded scalars (every one is a NON-default; see the dead-gate audit) ----
EXPECTED_FPS_NUM = 24
EXPECTED_FPS_DEN = 1
EXPECTED_START_S = 0.0
EXPECTED_END_S = 6.0

CAMERA_X_START = -500.0
CAMERA_X_END = -150.0

HERO_Z_START = 0.0
HERO_Z_TOP = 200.0
HERO_RISE_END_S = 3.0

FADE_START_VALUE = 1.0   # fully black at t=0
FADE_END_VALUE = 0.0     # fully clear at t=0.5
FADE_END_S = 0.5

TIME_TOL = 0.02   # seconds
POS_TOL = 1.0     # unreal units
FADE_TOL = 0.01   # normalized fade amount

# --- Push-in SHAPE (see ``_push_shape``) -------------------------------------
# Endpoint equality is not a push. ``_eval_curve`` HOLDS the value outside the
# keyed range, so a curve keyed only at (2.9,-500),(3.1,-150) reads -500 at
# t=0 and -150 at t=6 and would otherwise score as a smooth six-second push-in.
# The curve is therefore sampled every half-second across the whole shot.
PUSH_SAMPLE_STEP_S = 0.5
# Backwards jitter tolerated between consecutive samples, in unreal units.
PUSH_MONOTONIC_EPS = 0.5
# How far the fraction of travel completed may lag/lead the fraction of the
# shot elapsed. 0.20 accepts an eased push and rejects a mid-shot snap (which
# is off by 0.42 at t=2.5).
PUSH_PROGRESS_TOL = 0.20

CHANNEL_LOCATION_X = "Location.X"
CHANNEL_LOCATION_Z = "Location.Z"

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "sequence_asset_exists",
    "sequence_display_rate_24fps",
    "sequence_spans_six_seconds",
    "camera_cut_track_present",
    "camera_cut_covers_whole_shot",
    "camera_cut_targets_cine_camera",
    "camera_spawned_by_sequence",
    "camera_pushes_in_over_full_shot",
    "hero_binding_named_evalhero",
    "hero_spawned_by_sequence",
    "hero_rises_then_holds",
    "fade_in_from_black",
)

# Emitted for every check that cannot run because the sequence is absent.
SEQ_MISSING_TOKEN = "SEQ_ASSET_MISSING"


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

    UE pythonizes UPROPERTY names, and which spelling ``get_editor_property``
    resolves is not always obvious. Trying both is cheaper than being wrong,
    and it never invents a value - if every spelling fails the last exception
    propagates and the caller records a ``*_READ_ERROR``.
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


def _unwrap(res):
    """UE codegen may hand back ``(return_value, out_param)``; take the value.

    Only used on single-out-parameter getters. A bare value passes through.
    """
    if isinstance(res, (tuple, list)) and len(res) == 2:
        return res[-1]
    return res


def _seq_ext():
    return unreal.MovieSceneSequenceExtensions


def _binding_ext():
    return unreal.MovieSceneBindingExtensions


def _track_ext():
    return unreal.MovieSceneTrackExtensions


def _section_ext():
    return unreal.MovieSceneSectionExtensions


def _load_sequence(path):
    """The LevelSequence at ``path``. Raises if it will not load."""
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError("load_asset returned None")
    return asset


def _is_level_sequence(asset):
    """True only on a positive isinstance against the level-sequence type."""
    if asset is None:
        return False
    try:
        return bool(isinstance(asset, unreal.LevelSequence))
    except Exception:  # noqa: BLE001 - type not exposed => cannot confirm
        return False


def _root_tracks(sequence):
    """Every root (non-binding) track. FAIL-CLOSED: an unreadable walk raises.

    An EMPTY list is returned as empty on purpose here - "the sequence has no
    root tracks at all" is a legitimate, gradeable state (it is exactly the
    empty-timeline variant) and every consumer of this list treats empty as a
    FAILURE, never as a pass.
    """
    return list(_seq_ext().get_tracks(sequence) or [])


def _tracks_of_type(tracks, type_name):
    """Tracks whose class is ``unreal.<type_name>`` or a subclass of it.

    FAIL-CLOSED: if the type is not exposed by this build, this RAISES rather
    than returning ``[]`` - an unknown type name must never read as "the agent
    did not author that track".
    """
    cls = getattr(unreal, type_name, None)
    if cls is None:
        raise AttributeError("TRACK_TYPE_UNAVAILABLE %s" % type_name)
    out = []
    for t in tracks:
        try:
            if isinstance(t, cls):
                out.append(t)
        except Exception:  # noqa: BLE001 - unreadable candidate is not a match
            continue
    return out


def _sections(track):
    return list(_track_ext().get_sections(track) or [])


def _class_names(objs):
    return sorted(_class_name(o) for o in objs)


def _tick_resolution(sequence):
    """Ticks per second as a float. Raises if it cannot be read or is absurd."""
    rate = _seq_ext().get_tick_resolution(sequence)
    num = float(_read_property(rate, "numerator", "Numerator"))
    den = float(_read_property(rate, "denominator", "Denominator"))
    if num <= 0.0 or den <= 0.0:
        raise RuntimeError("TICK_RESOLUTION_INVALID %s/%s" % (num, den))
    return num / den


def _rate_pair(rate):
    num = int(_read_property(rate, "numerator", "Numerator"))
    den = int(_read_property(rate, "denominator", "Denominator"))
    return num, den


def _guid_text(guid):
    """A stable string for an FGuid, or '' - never raises.

    FGuid exposes NO reflected fields in UE 5.8, so ``str(guid)`` on a real
    engine struct yields an ADDRESS repr ("<Struct 'Guid' (0x...) {}>") that
    is unique per handle - two reads of the SAME guid compare unequal, which
    silently broke every binding-identity check on first live contact
    (2026-07-29). The engine route is the ScriptMethod ``to_string()``
    (KismetGuidLibrary.Conv_GuidToString). An address-shaped fallback is
    treated as UNREADABLE ('') so it can never be credited as an identity.
    """
    if guid is None:
        return ""
    fn = getattr(guid, "to_string", None)
    if callable(fn):
        try:
            return str(fn())
        except Exception:  # noqa: BLE001
            pass
    try:
        text = str(guid)
    except Exception:  # noqa: BLE001
        return ""
    if "0x" in text and "Struct" in text:
        return ""
    return text


def _binding_id(binding):
    """The FGuid identifying a binding proxy, as text. '' if unreadable."""
    try:
        return _guid_text(_binding_ext().get_id(binding))
    except Exception:  # noqa: BLE001
        return ""


def _binding_name(binding):
    """A binding's name, preferring the FString name over the display text."""
    try:
        name = str(_binding_ext().get_name(binding))
        if name:
            return name
    except Exception:  # noqa: BLE001
        pass
    try:
        return str(_binding_ext().get_display_name(binding))
    except Exception:  # noqa: BLE001
        return ""


def _bindings(sequence):
    """Every binding proxy on the sequence."""
    return list(_seq_ext().get_bindings(sequence) or [])


def _spawnable_guids(sequence):
    """The guid TEXTS of every spawnable binding.

    FAIL-CLOSED: this raises if the accessor is unavailable. An empty SET is a
    legitimate answer ("the sequence spawns nothing"), and every caller reads
    it as a FAILURE for the binding it was asking about.
    """
    ext = _seq_ext()
    fn = getattr(ext, "get_spawnables", None)
    if fn is None:
        raise AttributeError("GET_SPAWNABLES_UNAVAILABLE")
    return set(_binding_id(b) for b in (fn(sequence) or []) if _binding_id(b))


def _binding_object_class_name(binding):
    """Class name of the object a binding animates, or ''.

    Two routes, tried in order and both positive reads:
      * spawnables carry an object TEMPLATE inside the asset
        (``MovieSceneBindingExtensions::GetObjectTemplate`` ->
        ``MovieSceneHelpers::GetObjectTemplate``, which handles both the legacy
        ``FMovieSceneSpawnable`` array and 5.8's custom spawnable bindings);
      * possessables record the class they were bound to
        (``GetPossessedObjectClass``, ``WITH_EDITORONLY_DATA``).
    Returns the template OBJECT too so the caller can isinstance it.
    """
    obj = None
    try:
        obj = _binding_ext().get_object_template(binding)
    except Exception:  # noqa: BLE001
        obj = None
    if obj is not None:
        return obj, _class_name(obj)
    cls = None
    try:
        cls = _binding_ext().get_possessed_object_class(binding)
    except Exception:  # noqa: BLE001
        cls = None
    if cls is not None:
        try:
            return None, str(cls.get_name())
        except Exception:  # noqa: BLE001
            return None, "<unreadable>"
    return None, ""


def _is_cine_camera(template_obj, class_name):
    """True iff the bound object is a cinematic camera actor (or a subclass).

    FAIL-CLOSED: the ``isinstance`` is the primary, positive route. The
    class-NAME comparison is only a fallback for a possessable, where no
    template object exists inside the asset to isinstance - and it accepts
    only the exact engine type name plus the Blueprint-generated form of it.
    """
    if template_obj is not None:
        try:
            if isinstance(template_obj, unreal.CineCameraActor):
                return True
        except Exception:  # noqa: BLE001 - type not exposed; fall through
            pass
        return False
    if not class_name:
        return False
    return class_name in ("CineCameraActor", "CineCameraActor_C")


def _child_bindings(binding):
    try:
        return list(_binding_ext().get_child_possessables(binding) or [])
    except Exception:  # noqa: BLE001
        return []


def _transform_sections(binding):
    """Every 3D-transform section reachable from a binding.

    Looks at the binding's own tracks and at its child possessables' tracks,
    because a transform can legitimately be keyed on the actor binding or on
    its root-component child binding.

    FAIL-CLOSED: raises if the transform track type is not exposed.
    """
    out = []
    candidates = [binding] + _child_bindings(binding)
    for b in candidates:
        try:
            tracks = list(_binding_ext().get_tracks(b) or [])
        except Exception:  # noqa: BLE001
            continue
        for track in _tracks_of_type(tracks, "MovieScene3DTransformTrack"):
            out.extend(_sections(track))
    return out


def _channel_keys_seconds(section, channel_name, ticks_per_second):
    """``[(seconds, value)]`` for a NAMED channel, sorted by time.

    FAIL-CLOSED: raises when the channel cannot be resolved, so "no channel"
    can never be mistaken for "no keys" and neither can be mistaken for a
    correct curve.
    """
    channel = _section_ext().get_channel(section, channel_name)
    if channel is None:
        raise RuntimeError("CHANNEL_UNRESOLVED %s" % channel_name)
    return _keys_seconds(channel, ticks_per_second)


def _keys_seconds(channel, ticks_per_second):
    """``[(seconds, value)]`` for a scripting channel, sorted by time."""
    keys = list(channel.get_keys() or [])
    unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
    out = []
    for key in keys:
        frame_time = key.get_time(unit)
        frame_number = _read_property(frame_time, "frame_number", "FrameNumber")
        ticks = float(_read_property(frame_number, "value", "Value"))
        out.append((ticks / ticks_per_second, float(key.get_value())))
    out.sort(key=lambda kv: kv[0])
    return out


def _all_channel_key_sets(section, ticks_per_second):
    """``[(name, [(seconds, value)])]`` for every channel on a section.

    Used where the channel carries no editor metadata NAME - the fade curve is
    registered with a default-constructed ``FMovieSceneChannelMetaData()``.
    """
    channels = list(_section_ext().get_all_channels(section) or [])
    if not channels:
        raise RuntimeError("SECTION_HAS_NO_CHANNELS")
    out = []
    for channel in channels:
        try:
            name = str(_read_property(channel, "channel_name", "ChannelName"))
        except Exception:  # noqa: BLE001 - unnamed channel is still usable
            name = ""
        try:
            out.append((name, _keys_seconds(channel, ticks_per_second)))
        except Exception:  # noqa: BLE001 - one unreadable channel is not fatal
            continue
    if not out:
        raise RuntimeError("SECTION_CHANNELS_UNREADABLE")
    return out


def _eval_curve(keys, t):
    """Piecewise-LINEAR value of a keyed curve at ``t``; ``None`` if unkeyed.

    Outside the key range the value is held constant, which is what Sequencer
    itself does before the first and after the last key. Evaluating (rather
    than demanding a key at each sampled time) is deliberate: "rise to 200 by
    t=3 and hold" is correctly authored EITHER as two keys (0,3) or as three
    (0,3,6), and both must pass. It still fails a straight 0->200 ramp across
    the whole shot, which reads 100 at t=3.

    **That hold is also a gaming surface, and callers must defend against it.**
    Two endpoint samples cannot tell a push from a snap: keys at
    ``(2.9,-500),(3.1,-150)`` read -500 at t=0 and -150 at t=6 purely because
    of the hold. Anything graded as MOTION is therefore run through
    ``_push_shape`` as well, never on its endpoints alone.
    """
    if not keys:
        return None
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for i in range(1, len(keys)):
        t0, v0 = keys[i - 1]
        t1, v1 = keys[i]
        if t <= t1:
            if (t1 - t0) <= 1e-9:
                return v1
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def _fmt_keys(keys):
    """A compact ASCII rendering of a key list for the detail string."""
    return "[" + ",".join("%.3f@%.3fs" % (v, t) for t, v in keys) + "]"


def _sample_times(t_start, t_end, step):
    """Inclusive ``[t_start .. t_end]`` sample grid at ``step`` seconds."""
    count = int(round((t_end - t_start) / float(step)))
    if count < 1:
        count = 1
    return [t_start + (t_end - t_start) * i / float(count)
            for i in range(count + 1)]


def _push_shape(keys, t_start, t_end, v_start, v_end):
    """``None`` if the curve really pushes from ``v_start`` to ``v_end``.

    Otherwise a FAILURE detail naming which of the three shape gates broke.
    Endpoint equality alone is NOT a push - ``_eval_curve`` holds the value
    outside the keyed range, so a curve that SNAPS mid-shot, or one whose keys
    sit entirely inside a sliver of the timeline, reads the right value at
    t=0 and t=6 while nothing moves for most of the shot. Three independent
    gates, all required, all evaluated on INTERMEDIATE samples:

      1. **keyed across the shot** - the first key is at (or before) the start
         and the last at (or after) the end, so the hold is never what is being
         graded;
      2. **monotonic toward the target** - no sample may move AWAY from
         ``v_end`` by more than ``PUSH_MONOTONIC_EPS``, which rejects an
         out-and-back curve that happens to land on both endpoints;
      3. **spread across the shot** - at every sample the fraction of the
         travel completed must track the elapsed fraction to within
         ``PUSH_PROGRESS_TOL``. This is the gate a mid-shot snap dies on, and
         the band is wide enough (0.20 of the travel) that an eased push, not
         just the linear reference, still passes.
    """
    span = float(v_end) - float(v_start)
    if abs(span) <= 1e-9:          # not a movement at all; caller mis-declared
        return "CAMERA_PUSH_IN_SPAN_DEGENERATE start=%s end=%s" % (v_start, v_end)
    sign = 1.0 if span > 0 else -1.0

    first_t, last_t = keys[0][0], keys[-1][0]
    if first_t > t_start + TIME_TOL or last_t < t_end - TIME_TOL:
        return ("CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT first_key=%.3fs "
                "last_key=%.3fs shot=%.3f..%.3fs keys=%s"
                % (first_t, last_t, t_start, t_end, _fmt_keys(keys)))

    samples = [(t, _eval_curve(keys, t))
               for t in _sample_times(t_start, t_end, PUSH_SAMPLE_STEP_S)]
    if any(v is None for _t, v in samples):
        return ("CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT first_key=%.3fs "
                "last_key=%.3fs shot=%.3f..%.3fs keys=%s"
                % (first_t, last_t, t_start, t_end, _fmt_keys(keys)))

    for i in range(1, len(samples)):
        step = (samples[i][1] - samples[i - 1][1]) * sign
        if step < -PUSH_MONOTONIC_EPS:
            return ("CAMERA_PUSH_IN_NOT_MONOTONIC at=%.3fs step=%.3f "
                    "samples=%s" % (samples[i][0], step, _fmt_keys(samples)))

    duration = float(t_end) - float(t_start)
    for t, v in samples:
        elapsed = (t - t_start) / duration
        travelled = (v - float(v_start)) / span
        if abs(travelled - elapsed) > PUSH_PROGRESS_TOL:
            return ("CAMERA_PUSH_IN_NOT_GRADUAL at=%.3fs travelled=%.3f "
                    "elapsed=%.3f tol=%.2f samples=%s"
                    % (t, travelled, elapsed, PUSH_PROGRESS_TOL,
                       _fmt_keys(samples)))
    return None


def _near(a, b, tol):
    return a is not None and abs(float(a) - float(b)) <= tol


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _sequence_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # A raised probe is NOT the same event as a genuinely absent asset, and the
    # two must not share a token: an API break that fanned out
    # SEQ_ASSET_MISSING would be credited as the empty leg's named failure.
    root_cause = None
    sequence = None
    try:
        exists = _asset_exists(ASSET_SEQUENCE)
    except Exception as e:  # noqa: BLE001
        root_cause = "SEQ_ASSET_PROBE_ERROR %s raised %r" % (ASSET_SEQUENCE, e)
        results["sequence_asset_exists"] = check(
            "sequence_asset_exists", False, root_cause)
        exists = False
    else:
        if not exists:
            root_cause = "%s %s" % (SEQ_MISSING_TOKEN, ASSET_SEQUENCE)
            results["sequence_asset_exists"] = check(
                "sequence_asset_exists", False, root_cause)

    if exists:
        try:
            sequence = _load_sequence(ASSET_SEQUENCE)
        except Exception as e:  # noqa: BLE001
            root_cause = "SEQ_LOAD_ERROR %s raised %r" % (ASSET_SEQUENCE, e)
            results["sequence_asset_exists"] = check(
                "sequence_asset_exists", False, root_cause)
            sequence = None
        else:
            if not _is_level_sequence(sequence):
                root_cause = ("SEQ_ASSET_NOT_LEVEL_SEQUENCE class=%s path=%s"
                              % (_class_name(sequence), ASSET_SEQUENCE))
                results["sequence_asset_exists"] = check(
                    "sequence_asset_exists", False, root_cause)
                sequence = None
            else:
                results["sequence_asset_exists"] = check(
                    "sequence_asset_exists", True,
                    "SEQ_ASSET_OK %s" % ASSET_SEQUENCE)

    if sequence is None:
        # Constant denominator: every remaining check still reports, as a
        # failure whose detail names the single root cause.
        for cid in CHECK_IDS:
            if cid not in results:
                results[cid] = check(cid, False, root_cause)
        return

    # --- timeline shape ------------------------------------------------------
    try:
        rate = _seq_ext().get_display_rate(sequence)
        num, den = _rate_pair(rate)
        ok = (num == EXPECTED_FPS_NUM and den == EXPECTED_FPS_DEN)
        results["sequence_display_rate_24fps"] = check(
            "sequence_display_rate_24fps", ok,
            ("SEQ_DISPLAY_RATE_OK rate=%d/%d" % (num, den)) if ok
            else ("SEQ_DISPLAY_RATE_WRONG rate=%d/%d expected=%d/%d"
                  % (num, den, EXPECTED_FPS_NUM, EXPECTED_FPS_DEN)))
    except Exception as e:  # noqa: BLE001
        results["sequence_display_rate_24fps"] = check(
            "sequence_display_rate_24fps", False,
            "SEQ_DISPLAY_RATE_READ_ERROR raised %r" % (e,))

    try:
        start = float(_seq_ext().get_playback_start_seconds(sequence))
        end = float(_seq_ext().get_playback_end_seconds(sequence))
        ok = (_near(start, EXPECTED_START_S, TIME_TOL)
              and _near(end, EXPECTED_END_S, TIME_TOL))
        results["sequence_spans_six_seconds"] = check(
            "sequence_spans_six_seconds", ok,
            ("SEQ_DURATION_OK start=%.3f end=%.3f" % (start, end)) if ok
            else ("SEQ_DURATION_WRONG start=%.3f end=%.3f expected=%.3f..%.3f"
                  % (start, end, EXPECTED_START_S, EXPECTED_END_S)))
    except Exception as e:  # noqa: BLE001
        results["sequence_spans_six_seconds"] = check(
            "sequence_spans_six_seconds", False,
            "SEQ_DURATION_READ_ERROR raised %r" % (e,))

    # --- shared reads --------------------------------------------------------
    ticks_per_second = None
    try:
        ticks_per_second = _tick_resolution(sequence)
    except Exception as e:  # noqa: BLE001
        ticks_per_second = None
        tick_error = repr(e)
    else:
        tick_error = None

    tracks = []
    tracks_error = None
    try:
        tracks = _root_tracks(sequence)
    except Exception as e:  # noqa: BLE001
        tracks_error = repr(e)

    bindings = []
    bindings_error = None
    try:
        bindings = _bindings(sequence)
    except Exception as e:  # noqa: BLE001
        bindings_error = repr(e)

    spawnables = set()
    spawnables_error = None
    try:
        spawnables = _spawnable_guids(sequence)
    except Exception as e:  # noqa: BLE001
        spawnables_error = repr(e)

    # --- camera cut track ----------------------------------------------------
    cut_sections = []
    try:
        if tracks_error is not None:
            raise RuntimeError(tracks_error)
        cut_tracks = _tracks_of_type(tracks, "MovieSceneCameraCutTrack")
        if not cut_tracks:
            results["camera_cut_track_present"] = check(
                "camera_cut_track_present", False,
                "CAMERA_CUT_TRACK_MISSING tracks=%s" % _class_names(tracks))
        else:
            for t in cut_tracks:
                cut_sections.extend(_sections(t))
            if not cut_sections:
                results["camera_cut_track_present"] = check(
                    "camera_cut_track_present", False,
                    "CAMERA_CUT_TRACK_EMPTY sections=0 tracks=%s"
                    % _class_names(cut_tracks))
            else:
                results["camera_cut_track_present"] = check(
                    "camera_cut_track_present", True,
                    "CAMERA_CUT_TRACK_OK sections=%d" % len(cut_sections))
    except Exception as e:  # noqa: BLE001
        results["camera_cut_track_present"] = check(
            "camera_cut_track_present", False,
            "CAMERA_CUT_TRACK_READ_ERROR raised %r" % (e,))

    if not cut_sections:
        fanout = (results.get("camera_cut_track_present") or {}).get(
            "detail", "CAMERA_CUT_TRACK_MISSING tracks=[]")
        for cid in ("camera_cut_covers_whole_shot",
                    "camera_cut_targets_cine_camera",
                    "camera_spawned_by_sequence",
                    "camera_pushes_in_over_full_shot"):
            results[cid] = check(cid, False, fanout)
    else:
        _camera_checks(results, sequence, cut_sections, bindings, spawnables,
                       bindings_error, spawnables_error,
                       ticks_per_second, tick_error)

    # --- hero binding --------------------------------------------------------
    _hero_checks(results, bindings, spawnables, bindings_error,
                 spawnables_error, ticks_per_second, tick_error)

    # --- fade ----------------------------------------------------------------
    _fade_checks(results, tracks, tracks_error, ticks_per_second, tick_error)


def _camera_checks(results, sequence, cut_sections, bindings, spawnables,
                   bindings_error, spawnables_error, ticks_per_second,
                   tick_error):
    # The cut must cover the whole shot. Exactly one bounded section spanning
    # [0, 6] is required: an unbounded section, a short section, or two
    # sections that merely add up are all rejected, because "the entire shot is
    # viewed through that camera" is a statement about ONE continuous cut.
    try:
        if len(cut_sections) != 1:
            results["camera_cut_covers_whole_shot"] = check(
                "camera_cut_covers_whole_shot", False,
                "CAMERA_CUT_RANGE_WRONG sections=%d expected=1"
                % len(cut_sections))
        else:
            section = cut_sections[0]
            has_start = bool(_section_ext().has_start_frame(section))
            has_end = bool(_section_ext().has_end_frame(section))
            if not (has_start and has_end):
                results["camera_cut_covers_whole_shot"] = check(
                    "camera_cut_covers_whole_shot", False,
                    "CAMERA_CUT_RANGE_WRONG start=<unbounded:%s> "
                    "end=<unbounded:%s>" % (not has_start, not has_end))
            else:
                start = float(_section_ext().get_start_frame_seconds(section))
                end = float(_section_ext().get_end_frame_seconds(section))
                ok = (_near(start, EXPECTED_START_S, TIME_TOL)
                      and _near(end, EXPECTED_END_S, TIME_TOL))
                results["camera_cut_covers_whole_shot"] = check(
                    "camera_cut_covers_whole_shot", ok,
                    ("CAMERA_CUT_RANGE_OK start=%.3f end=%.3f" % (start, end))
                    if ok else
                    ("CAMERA_CUT_RANGE_WRONG start=%.3f end=%.3f "
                     "expected=%.3f..%.3f"
                     % (start, end, EXPECTED_START_S, EXPECTED_END_S)))
    except Exception as e:  # noqa: BLE001
        results["camera_cut_covers_whole_shot"] = check(
            "camera_cut_covers_whole_shot", False,
            "CAMERA_CUT_RANGE_READ_ERROR raised %r" % (e,))

    # Resolve the binding the cut points at.
    camera_binding = None
    camera_guid = ""
    resolve_error = None
    try:
        section = cut_sections[0]
        binding_id = None
        getter = getattr(section, "get_camera_binding_id", None)
        if getter is not None:
            binding_id = _unwrap(getter())
        if binding_id is None:
            binding_id = _read_property(
                section, "camera_binding_id", "CameraBindingID")
        camera_guid = _guid_text(_read_property(binding_id, "guid", "Guid"))
        if bindings_error is not None:
            raise RuntimeError(bindings_error)
        for b in bindings:
            if camera_guid and _binding_id(b) == camera_guid:
                camera_binding = b
                break
    except Exception as e:  # noqa: BLE001
        resolve_error = repr(e)

    if resolve_error is not None:
        for cid in ("camera_cut_targets_cine_camera",
                    "camera_spawned_by_sequence",
                    "camera_pushes_in_over_full_shot"):
            results[cid] = check(
                cid, False, "CAMERA_CUT_BINDING_READ_ERROR raised %s"
                % resolve_error)
        return

    if camera_binding is None:
        unresolved = ("CAMERA_CUT_BINDING_UNRESOLVED guid=%s bindings=%s"
                      % (camera_guid or "<none>",
                         sorted(_binding_name(b) for b in bindings)))
        for cid in ("camera_cut_targets_cine_camera",
                    "camera_spawned_by_sequence",
                    "camera_pushes_in_over_full_shot"):
            results[cid] = check(cid, False, unresolved)
        return

    camera_name = _binding_name(camera_binding)

    # It is a cinematic camera.
    try:
        template, cls_name = _binding_object_class_name(camera_binding)
        ok = _is_cine_camera(template, cls_name)
        results["camera_cut_targets_cine_camera"] = check(
            "camera_cut_targets_cine_camera", ok,
            ("CAMERA_CUT_CAMERA_OK class=%s name=%s" % (cls_name or "?",
                                                        camera_name))
            if ok else
            ("CAMERA_CUT_BINDING_NOT_CINE_CAMERA class=%s name=%s"
             % (cls_name or "<unreadable>", camera_name or "<unnamed>")))
    except Exception as e:  # noqa: BLE001
        results["camera_cut_targets_cine_camera"] = check(
            "camera_cut_targets_cine_camera", False,
            "CAMERA_CUT_CAMERA_READ_ERROR raised %r" % (e,))

    # The sequence brings its own camera (spawnable), it does not borrow one.
    if spawnables_error is not None:
        results["camera_spawned_by_sequence"] = check(
            "camera_spawned_by_sequence", False,
            "CAMERA_SPAWNABLE_READ_ERROR raised %s" % spawnables_error)
    else:
        ok = bool(camera_guid) and camera_guid in spawnables
        results["camera_spawned_by_sequence"] = check(
            "camera_spawned_by_sequence", ok,
            ("CAMERA_SPAWNABLE_OK name=%s" % camera_name) if ok
            else ("CAMERA_BINDING_NOT_SPAWNABLE name=%s spawnables=%d"
                  % (camera_name or "<unnamed>", len(spawnables))))

    # It pushes in from X=-500 to X=-150 across the whole shot.
    try:
        if tick_error is not None:
            raise RuntimeError(tick_error)
        sections = _transform_sections(camera_binding)
        if not sections:
            results["camera_pushes_in_over_full_shot"] = check(
                "camera_pushes_in_over_full_shot", False,
                "CAMERA_TRANSFORM_TRACK_MISSING name=%s"
                % (camera_name or "<unnamed>"))
        else:
            keys = []
            for s in sections:
                keys.extend(_channel_keys_seconds(
                    s, CHANNEL_LOCATION_X, ticks_per_second))
            keys.sort(key=lambda kv: kv[0])
            at_start = _eval_curve(keys, EXPECTED_START_S)
            at_end = _eval_curve(keys, EXPECTED_END_S)
            endpoints_ok = (len(keys) >= 2
                            and _near(at_start, CAMERA_X_START, POS_TOL)
                            and _near(at_end, CAMERA_X_END, POS_TOL))
            if not endpoints_ok:
                detail = ("CAMERA_PUSH_IN_KEYS_WRONG keys=%s x0=%s x6=%s "
                          "expected=%.1f..%.1f"
                          % (_fmt_keys(keys), at_start, at_end,
                             CAMERA_X_START, CAMERA_X_END))
            else:
                # The endpoints are right - now prove the camera actually
                # TRAVELLED between them instead of holding and snapping.
                detail = _push_shape(keys, EXPECTED_START_S, EXPECTED_END_S,
                                     CAMERA_X_START, CAMERA_X_END)
            ok = endpoints_ok and detail is None
            results["camera_pushes_in_over_full_shot"] = check(
                "camera_pushes_in_over_full_shot", ok,
                ("CAMERA_PUSH_IN_OK keys=%s" % _fmt_keys(keys)) if ok
                else detail)
    except Exception as e:  # noqa: BLE001
        results["camera_pushes_in_over_full_shot"] = check(
            "camera_pushes_in_over_full_shot", False,
            "CAMERA_PUSH_IN_READ_ERROR raised %r" % (e,))


def _hero_checks(results, bindings, spawnables, bindings_error,
                 spawnables_error, ticks_per_second, tick_error):
    hero = None
    if bindings_error is not None:
        detail = "HERO_BINDING_READ_ERROR raised %s" % bindings_error
        for cid in ("hero_binding_named_evalhero", "hero_spawned_by_sequence",
                    "hero_rises_then_holds"):
            results[cid] = check(cid, False, detail)
        return

    names = sorted(n for n in (_binding_name(b) for b in bindings) if n)
    for b in bindings:
        if _binding_name(b) == HERO_BINDING_NAME:
            hero = b
            break

    results["hero_binding_named_evalhero"] = check(
        "hero_binding_named_evalhero", hero is not None,
        ("HERO_BINDING_OK name=%s" % HERO_BINDING_NAME) if hero is not None
        else ("HERO_BINDING_MISSING bindings=%s expected=%s"
              % (names, HERO_BINDING_NAME)))

    if hero is None:
        fanout = ("HERO_BINDING_MISSING bindings=%s expected=%s"
                  % (names, HERO_BINDING_NAME))
        results["hero_spawned_by_sequence"] = check(
            "hero_spawned_by_sequence", False, fanout)
        results["hero_rises_then_holds"] = check(
            "hero_rises_then_holds", False, fanout)
        return

    hero_guid = _binding_id(hero)

    if spawnables_error is not None:
        results["hero_spawned_by_sequence"] = check(
            "hero_spawned_by_sequence", False,
            "HERO_SPAWNABLE_READ_ERROR raised %s" % spawnables_error)
    else:
        ok = bool(hero_guid) and hero_guid in spawnables
        results["hero_spawned_by_sequence"] = check(
            "hero_spawned_by_sequence", ok,
            ("HERO_SPAWNABLE_OK name=%s" % HERO_BINDING_NAME) if ok
            else ("HERO_BINDING_NOT_SPAWNABLE name=%s spawnables=%d"
                  % (HERO_BINDING_NAME, len(spawnables))))

    try:
        if tick_error is not None:
            raise RuntimeError(tick_error)
        sections = _transform_sections(hero)
        if not sections:
            results["hero_rises_then_holds"] = check(
                "hero_rises_then_holds", False,
                "HERO_TRANSFORM_TRACK_MISSING name=%s" % HERO_BINDING_NAME)
        else:
            keys = []
            for s in sections:
                keys.extend(_channel_keys_seconds(
                    s, CHANNEL_LOCATION_Z, ticks_per_second))
            keys.sort(key=lambda kv: kv[0])
            z0 = _eval_curve(keys, EXPECTED_START_S)
            z3 = _eval_curve(keys, HERO_RISE_END_S)
            z6 = _eval_curve(keys, EXPECTED_END_S)
            ok = (len(keys) >= 2
                  and _near(z0, HERO_Z_START, POS_TOL)
                  and _near(z3, HERO_Z_TOP, POS_TOL)
                  and _near(z6, HERO_Z_TOP, POS_TOL))
            results["hero_rises_then_holds"] = check(
                "hero_rises_then_holds", ok,
                ("HERO_RISE_OK keys=%s" % _fmt_keys(keys)) if ok
                else ("HERO_RISE_KEYS_WRONG keys=%s z0=%s z3=%s z6=%s "
                      "expected=%.1f,%.1f,%.1f"
                      % (_fmt_keys(keys), z0, z3, z6,
                         HERO_Z_START, HERO_Z_TOP, HERO_Z_TOP)))
    except Exception as e:  # noqa: BLE001
        results["hero_rises_then_holds"] = check(
            "hero_rises_then_holds", False,
            "HERO_RISE_READ_ERROR raised %r" % (e,))


def _fade_checks(results, tracks, tracks_error, ticks_per_second, tick_error):
    try:
        if tracks_error is not None:
            raise RuntimeError(tracks_error)
        if tick_error is not None:
            raise RuntimeError(tick_error)
        fade_tracks = _tracks_of_type(tracks, "MovieSceneFadeTrack")
        if not fade_tracks:
            results["fade_in_from_black"] = check(
                "fade_in_from_black", False,
                "FADE_TRACK_MISSING tracks=%s" % _class_names(tracks))
            return
        sections = []
        for t in fade_tracks:
            sections.extend(_sections(t))
        if not sections:
            results["fade_in_from_black"] = check(
                "fade_in_from_black", False,
                "FADE_TRACK_EMPTY sections=0 tracks=%s"
                % _class_names(fade_tracks))
            return
        # The fade section is INFINITE by construction, so its bounds say
        # nothing; the curve is the graded property. Take the first channel
        # that actually carries keys - the fade section registers exactly one
        # float curve, under a NAME_None metadata name.
        keys = []
        for s in sections:
            for _name, ks in _all_channel_key_sets(s, ticks_per_second):
                if ks:
                    keys.extend(ks)
        keys.sort(key=lambda kv: kv[0])
        at0 = _eval_curve(keys, 0.0)
        at_half = _eval_curve(keys, FADE_END_S)
        ok = (len(keys) >= 2
              and _near(at0, FADE_START_VALUE, FADE_TOL)
              and _near(at_half, FADE_END_VALUE, FADE_TOL))
        results["fade_in_from_black"] = check(
            "fade_in_from_black", ok,
            ("FADE_IN_OK keys=%s" % _fmt_keys(keys)) if ok
            else ("FADE_IN_KEYS_WRONG keys=%s f0=%s f05=%s expected=%.2f..%.2f"
                  % (_fmt_keys(keys), at0, at_half,
                     FADE_START_VALUE, FADE_END_VALUE)))
    except Exception as e:  # noqa: BLE001
        results["fade_in_from_black"] = check(
            "fade_in_from_black", False,
            "FADE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _sequence_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        for cid in CHECK_IDS:
            if cid not in results:
                results[cid] = check(
                    cid, False, "SEQ_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
