"""Offline oracle for the t2-cutscene-camera-push-and-hero-rise L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
the SequencerScripting reflection surface the introspect script actually uses
(sequence, root tracks, bindings, sections, channels, keys, spawnables), so
every leg of ``discrimination/MATRIX.md`` can be simulated and joined against
the REAL ``discriminate.parse_matrix`` + the REAL ``layers/l2_introspect``
parser.

What this pins:
  * the reference shape scores 12/12 and the layer reads ``pass``;
  * every negative leg's MATRIX substring is a literal the script PRINTS, on
    the check the matrix names;
  * the denominator is 12 on EVERY leg, including the empty one;
  * error tokens are disjoint from every matrix substring, so a broken UE API
    name can never be credited as a variant's named failure;
  * the fail-closed rules hold: an unreadable spawnable list, an unresolvable
    channel and a section with no channels all FAIL rather than pass;
  * "rise then hold" accepts both the two-key and the three-key authoring, and
    rejects the straight ramp.

The fake is deliberately dumb: it models names, classes, key times/values and
binding ownership, and nothing else. It cannot prove the UE API names are
right - only a live editor does that - but it does prove the grader's LOGIC
and its printed tokens.
"""
import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parent.parent

sys.path.insert(0, str(_VERIFY))
sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402
from aura_rig.discriminate import parse_matrix  # noqa: E402

TASK_DIR = _REPO / "tasks" / "bp" / "t2-cutscene-camera-push-and-hero-rise"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "cutscene_camera_push_and_hero_rise.py"

TICKS_PER_SECOND = 24000.0


def _load_script():
    spec = importlib.util.spec_from_file_location("_cutscene_introspect", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# the fake unreal module                                                       #
# --------------------------------------------------------------------------- #

class _Class:
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


class _Reflected:
    """Anything with ``get_editor_property`` + ``get_class``."""

    def __init__(self, **props):
        self._props = dict(props)

    def get_editor_property(self, name):
        if name not in self._props:
            raise Exception("unknown property %r on %s" % (name, type(self).__name__))
        return self._props[name]

    def get_class(self):
        return _Class(type(self).__name__)

    def get_name(self):
        return type(self).__name__


class FrameNumber(_Reflected):
    pass


class FrameTime(_Reflected):
    pass


class FrameRate(_Reflected):
    pass


class Guid:
    def __init__(self, text):
        self._text = text

    def __str__(self):
        return self._text


class MovieSceneTimeUnit:
    DISPLAY_RATE = "DisplayRate"
    TICK_RESOLUTION = "TickResolution"


class Actor(_Reflected):
    pass


class StaticMeshActor(Actor):
    pass


class CameraActor(Actor):
    pass


class CineCameraActor(CameraActor):
    pass


class LevelSequence(_Reflected):
    """The fake asset. Carries everything the extension libraries read."""

    def __init__(self, display_rate=(24, 1), tick_resolution=(24000, 1),
                 playback=(0.0, 6.0), tracks=None, bindings=None):
        _Reflected.__init__(self)
        self.display_rate = display_rate
        self.tick_resolution = tick_resolution
        self.playback = playback
        self.tracks = list(tracks or [])
        self.bindings = list(bindings or [])
        self.spawnables_raise = False


class NotASequence(_Reflected):
    """Something that loads but is not a level sequence."""


class Key:
    def __init__(self, seconds, value):
        self.seconds = seconds
        self.value = value

    def get_time(self, unit):
        assert unit == MovieSceneTimeUnit.TICK_RESOLUTION, unit
        ticks = int(round(self.seconds * TICKS_PER_SECOND))
        return FrameTime(frame_number=FrameNumber(value=ticks))

    def get_value(self):
        return self.value


class Channel(_Reflected):
    def __init__(self, name, keys):
        _Reflected.__init__(self, channel_name=name)
        self.name = name
        self.keys = [Key(t, v) for t, v in keys]

    def get_keys(self):
        return list(self.keys)


class Section(_Reflected):
    def __init__(self, start=None, end=None, channels=None, camera_guid=None,
                 channels_raise=False):
        _Reflected.__init__(self)
        self.start = start
        self.end = end
        self.channels = list(channels or [])
        self.camera_guid = camera_guid
        self.channels_raise = channels_raise

    # Only camera-cut sections expose this, exactly like the real class.
    def get_camera_binding_id(self):
        if self.camera_guid is None:
            raise Exception("section carries no camera binding")
        return _Reflected(guid=Guid(self.camera_guid))


class MovieSceneTrack(_Reflected):
    def __init__(self, sections=None):
        _Reflected.__init__(self)
        self.sections = list(sections or [])


class MovieSceneCameraCutTrack(MovieSceneTrack):
    pass


class MovieSceneFadeTrack(MovieSceneTrack):
    pass


class MovieScene3DTransformTrack(MovieSceneTrack):
    pass


class Binding:
    """Stands in for FMovieSceneBindingProxy."""

    def __init__(self, guid, name, spawnable=True, template=None,
                 possessed_class=None, tracks=None, children=None):
        self.guid = guid
        self.name = name
        self.spawnable = spawnable
        self.template = template
        self.possessed_class = possessed_class
        self.tracks = list(tracks or [])
        self.children = list(children or [])


class EditorAssetLibrary:
    registry = {}

    @staticmethod
    def does_asset_exist(path):
        return path in EditorAssetLibrary.registry

    @staticmethod
    def load_asset(path):
        return EditorAssetLibrary.registry.get(path)


class MovieSceneSequenceExtensions:
    @staticmethod
    def get_display_rate(seq):
        num, den = seq.display_rate
        return FrameRate(numerator=num, denominator=den)

    @staticmethod
    def get_tick_resolution(seq):
        num, den = seq.tick_resolution
        return FrameRate(numerator=num, denominator=den)

    @staticmethod
    def get_playback_start_seconds(seq):
        return seq.playback[0]

    @staticmethod
    def get_playback_end_seconds(seq):
        return seq.playback[1]

    @staticmethod
    def get_tracks(seq):
        return list(seq.tracks)

    @staticmethod
    def get_bindings(seq):
        return list(seq.bindings)

    @staticmethod
    def get_spawnables(seq):
        if seq.spawnables_raise:
            raise Exception("spawnable accessor unavailable in this build")
        return [b for b in seq.bindings if b.spawnable]


class MovieSceneBindingExtensions:
    @staticmethod
    def get_id(binding):
        return Guid(binding.guid)

    @staticmethod
    def get_name(binding):
        return binding.name

    @staticmethod
    def get_display_name(binding):
        return binding.name

    @staticmethod
    def get_tracks(binding):
        return list(binding.tracks)

    @staticmethod
    def get_child_possessables(binding):
        return list(binding.children)

    @staticmethod
    def get_object_template(binding):
        return binding.template

    @staticmethod
    def get_possessed_object_class(binding):
        return _Class(binding.possessed_class) if binding.possessed_class else None


class MovieSceneTrackExtensions:
    @staticmethod
    def get_sections(track):
        return list(track.sections)


class MovieSceneSectionExtensions:
    @staticmethod
    def has_start_frame(section):
        return section.start is not None

    @staticmethod
    def has_end_frame(section):
        return section.end is not None

    @staticmethod
    def get_start_frame_seconds(section):
        return -1.0 if section.start is None else section.start

    @staticmethod
    def get_end_frame_seconds(section):
        return -1.0 if section.end is None else section.end

    @staticmethod
    def get_channel(section, name):
        for c in section.channels:
            if c.name == name:
                return c
        return None  # exactly what the real library does on a miss

    @staticmethod
    def get_all_channels(section):
        if section.channels_raise:
            raise Exception("channel proxy unavailable")
        return list(section.channels)


def log(*_a, **_k):
    pass


def _install_fake_unreal(mod, registry):
    """Point the loaded introspect module at this module's fake surface."""
    fake = sys.modules[__name__]
    EditorAssetLibrary.registry = dict(registry)
    mod.unreal = fake
    return mod


# --------------------------------------------------------------------------- #
# scenario builders                                                            #
# --------------------------------------------------------------------------- #

def _transform_track(channel_name, keys):
    return MovieScene3DTransformTrack(
        sections=[Section(start=0.0, end=6.0,
                          channels=[Channel(channel_name, keys)])])


def build_reference(hero_keys=None, camera_keys=None, fade_keys=None,
                    camera_spawnable=True, tracks_override=None,
                    bindings_override=None, display_rate=(24, 1),
                    playback=(0.0, 6.0)):
    camera_keys = camera_keys if camera_keys is not None else [(0.0, -500.0), (6.0, -150.0)]
    hero_keys = hero_keys if hero_keys is not None else [(0.0, 0.0), (3.0, 200.0)]
    fade_keys = fade_keys if fade_keys is not None else [(0.0, 1.0), (0.5, 0.0)]

    camera = Binding(
        "CAM-GUID", "CineCameraActor",
        spawnable=camera_spawnable,
        template=CineCameraActor() if camera_spawnable else None,
        possessed_class=None if camera_spawnable else "CineCameraActor",
        tracks=[_transform_track("Location.X", camera_keys)])
    hero = Binding(
        "HERO-GUID", "EvalHero", spawnable=True, template=StaticMeshActor(),
        tracks=[_transform_track("Location.Z", hero_keys)])

    cut = MovieSceneCameraCutTrack(
        sections=[Section(start=0.0, end=6.0, camera_guid="CAM-GUID")])
    # The real fade section is INFINITE (start/end None) and its channel has
    # no metadata name - both modelled here on purpose.
    fade = MovieSceneFadeTrack(
        sections=[Section(channels=[Channel("", fade_keys)])])

    seq = LevelSequence(
        display_rate=display_rate,
        playback=playback,
        tracks=tracks_override if tracks_override is not None else [cut, fade],
        bindings=bindings_override if bindings_override is not None else [camera, hero],
    )
    return seq


def run_leg(sequence):
    """Run the grader against a fake sequence; return the parsed verdict."""
    mod = _load_script()
    registry = {} if sequence is None else {mod.ASSET_SEQUENCE: sequence}
    _install_fake_unreal(mod, registry)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    parsed = parse_introspect_verdict(buf.getvalue())
    return mod, parsed


def details(parsed):
    return {c.id: c.detail for c in parsed.checks}


def failed_ids(parsed):
    return [c.id for c in parsed.checks if not c.passed]


# --------------------------------------------------------------------------- #
# the legs                                                                     #
# --------------------------------------------------------------------------- #

#: The camera sits still for 2.9s, jumps 350uu in 0.2s, sits still again. Both
#: endpoint samples read the reference values; nothing moves for 97% of the shot.
SNAP_KEYS = [(0.0, -500.0), (2.9, -500.0), (3.1, -150.0), (6.0, -150.0)]

#: label -> (sequence factory, the check id the MATRIX says it dies at)
NEGATIVE_LEGS = {
    "empty": (lambda: None, "sequence_asset_exists"),
    "timeline-header-only": (
        lambda: build_reference(tracks_override=[], bindings_override=[]),
        "camera_cut_track_present"),
    "camera-possessed-from-level": (
        lambda: build_reference(camera_spawnable=False),
        "camera_spawned_by_sequence"),
    "camera-static-single-key": (
        lambda: build_reference(camera_keys=[(0.0, -500.0)]),
        "camera_pushes_in_over_full_shot"),
    # Endpoints EXACTLY right, motion snapped into 0.2s in the middle. Scored
    # 12/12 overall PASS before _push_shape landed (2026-07-27).
    "camera-snaps-instead-of-pushing": (
        lambda: build_reference(camera_keys=SNAP_KEYS),
        "camera_pushes_in_over_full_shot"),
    "hero-ramps-whole-shot": (
        lambda: build_reference(hero_keys=[(0.0, 0.0), (6.0, 200.0)]),
        "hero_rises_then_holds"),
    "fade-out-not-in": (
        lambda: build_reference(fade_keys=[(0.0, 0.0), (0.5, 1.0)]),
        "fade_in_from_black"),
}


class TestReferenceLeg(unittest.TestCase):
    def test_reference_scores_all_green(self):
        mod, parsed = run_leg(build_reference())
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, len(mod.CHECK_IDS))
        self.assertEqual(
            parsed.passed_count, parsed.total,
            "reference must be 12/12; failures: %s"
            % {k: v for k, v in details(parsed).items()
               if k in failed_ids(parsed)})
        self.assertTrue(parsed.all_passed)

    def test_three_key_hold_also_passes(self):
        """Both the two-key and the three-key authoring of the hold are legal."""
        _mod, parsed = run_leg(build_reference(
            hero_keys=[(0.0, 0.0), (3.0, 200.0), (6.0, 200.0)]))
        self.assertTrue(parsed.all_passed, details(parsed))

    def test_transform_keyed_on_a_child_binding_also_passes(self):
        seq = build_reference()
        camera = seq.bindings[0]
        child = Binding("CAM-ROOT", "SceneComponent", spawnable=False,
                        tracks=camera.tracks)
        camera.tracks = []
        camera.children = [child]
        _mod, parsed = run_leg(seq)
        self.assertTrue(parsed.all_passed, details(parsed))


class TestNegativeLegsMatchTheMatrix(unittest.TestCase):
    """Every MATRIX substring is a literal the script prints on that leg."""

    @classmethod
    def setUpClass(cls):
        cls.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_matrix_has_a_row_for_every_leg_and_the_reference(self):
        self.assertEqual(set(self.rows), set(NEGATIVE_LEGS) | {"reference"})
        self.assertTrue(self.rows["reference"].expect_pass)

    def test_the_on_disk_variant_dirs_match_the_matrix(self):
        """A matrix row with no folder is a leg `cb discriminate` cannot run."""
        disc = TASK_DIR / "discrimination"
        on_disk = sorted(p.name for p in disc.iterdir() if p.is_dir())
        declared = sorted(k for k in self.rows if k not in ("reference", "empty"))
        self.assertEqual(on_disk, declared)

    def test_every_negative_row_has_a_clean_substring(self):
        for label, row in self.rows.items():
            if row.expect_pass:
                continue
            with self.subTest(label=label):
                self.assertTrue(row.substrings, "blank substring tuple")
                for s in row.substrings:
                    self.assertTrue(s.strip(), "empty substring")
                    self.assertNotIn("`", s, "backticks survived the parser")
                    self.assertTrue(s.isascii(), "non-ASCII substring")

    def test_each_leg_fails_at_the_named_check_via_the_named_substring(self):
        for label, (factory, expected_check) in NEGATIVE_LEGS.items():
            with self.subTest(label=label):
                _mod, parsed = run_leg(factory())
                self.assertTrue(parsed.found)
                self.assertFalse(parsed.all_passed, "leg must not pass")
                d = details(parsed)
                self.assertIn(expected_check, failed_ids(parsed),
                              "expected %s to fail; details=%s"
                              % (expected_check, d))
                for substring in self.rows[label].substrings:
                    self.assertIn(
                        substring, d[expected_check],
                        "MATRIX substring %r is not in the printed detail %r"
                        % (substring, d[expected_check]))

    def test_single_deviation_legs_fail_exactly_one_check(self):
        """Everything except empty/timeline-header-only isolates one gate."""
        for label in ("camera-possessed-from-level", "camera-static-single-key",
                      "camera-snaps-instead-of-pushing",
                      "hero-ramps-whole-shot", "fade-out-not-in"):
            with self.subTest(label=label):
                factory, expected_check = NEGATIVE_LEGS[label]
                _mod, parsed = run_leg(factory())
                self.assertEqual(failed_ids(parsed), [expected_check],
                                 details(parsed))

    def test_possessed_camera_still_passes_the_type_check(self):
        """Ownership and type are separate gates - the matrix relies on it."""
        _mod, parsed = run_leg(build_reference(camera_spawnable=False))
        d = {c.id: c.passed for c in parsed.checks}
        self.assertTrue(d["camera_cut_targets_cine_camera"])
        self.assertFalse(d["camera_spawned_by_sequence"])


class TestPushShapeIsNotEndpointOnly(unittest.TestCase):
    """The 2026-07-27 gaming hole, and the three gates that close it.

    ``camera_pushes_in_over_full_shot`` used to sample ``_eval_curve`` at
    ``t=0`` and ``t=6`` only. ``_eval_curve`` HOLDS the value outside the keyed
    range, so several curves that never push scored a full-marks PASS. Each
    test below names one such curve, asserts the gate that now catches it, and
    - crucially - the two "this must still pass" cases that keep the fix from
    turning into a false negative of its own.
    """

    def _push(self, keys):
        _mod, parsed = run_leg(build_reference(camera_keys=keys))
        by_id = {c.id: c for c in parsed.checks}
        return by_id["camera_pushes_in_over_full_shot"]

    def test_a_midshot_snap_with_perfect_endpoints_is_rejected(self):
        got = self._push(SNAP_KEYS)
        self.assertFalse(got.passed, "a 0.2s snap is not a six-second push")
        self.assertIn("CAMERA_PUSH_IN_NOT_GRADUAL at=", got.detail)

    def test_the_snap_endpoints_really_are_exact(self):
        """Proves the leg is credited for its SHAPE, not for a wrong endpoint.

        If the endpoints were off, the old ``CAMERA_PUSH_IN_KEYS_WRONG`` token
        would fire and the new variant would be a duplicate of
        ``camera-static-single-key`` rather than a new discrimination.
        """
        mod = _load_script()
        self.assertEqual(mod._eval_curve(SNAP_KEYS, mod.EXPECTED_START_S),
                         mod.CAMERA_X_START)
        self.assertEqual(mod._eval_curve(SNAP_KEYS, mod.EXPECTED_END_S),
                         mod.CAMERA_X_END)
        self.assertNotIn("CAMERA_PUSH_IN_KEYS_WRONG",
                         self._push(SNAP_KEYS).detail)

    def test_keys_parked_inside_a_sliver_of_the_shot_are_rejected(self):
        """The purest form of the hold exploit: no key at either endpoint."""
        got = self._push([(2.9, -500.0), (3.1, -150.0)])
        self.assertFalse(got.passed)
        self.assertIn("CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT first_key=",
                      got.detail)

    def test_an_out_and_back_curve_is_rejected(self):
        """Both endpoints correct, but the camera pulls out before pushing in."""
        got = self._push([(0.0, -500.0), (1.0, -600.0), (3.0, -300.0),
                          (6.0, -150.0)])
        self.assertFalse(got.passed)
        self.assertIn("CAMERA_PUSH_IN_NOT_MONOTONIC at=", got.detail)

    def test_the_linear_reference_still_passes(self):
        got = self._push([(0.0, -500.0), (6.0, -150.0)])
        self.assertTrue(got.passed, got.detail)
        self.assertIn("CAMERA_PUSH_IN_OK keys=", got.detail)

    def test_an_eased_push_still_passes(self):
        """FALSE-NEGATIVE GUARD: slow-in/slow-out is a legitimate push-in."""
        got = self._push([(0.0, -500.0), (1.5, -470.0), (3.0, -325.0),
                          (4.5, -180.0), (6.0, -150.0)])
        self.assertTrue(got.passed, got.detail)

    def test_a_dense_uniform_push_still_passes(self):
        """FALSE-NEGATIVE GUARD: a key every half second is also legitimate."""
        keys = [(i * 0.5, -500.0 + 350.0 * (i * 0.5) / 6.0) for i in range(13)]
        got = self._push(keys)
        self.assertTrue(got.passed, got.detail)

    def test_the_three_shape_tokens_are_distinct_and_matrix_safe(self):
        """No shape token may collide with an error token or another row."""
        mod = _load_script()
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        tokens = ("CAMERA_PUSH_IN_NOT_GRADUAL",
                  "CAMERA_PUSH_IN_NOT_MONOTONIC",
                  "CAMERA_PUSH_IN_NOT_KEYED_ACROSS_SHOT")
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        for token in tokens:
            self.assertIn(token, src)
            for marker in TestErrorTokensAreDisjointFromMatrix.ERROR_MARKERS:
                self.assertNotIn(marker, token)
        # Exactly one of them is claimed by the matrix, and by exactly one row.
        claimed = [(label, s) for label, r in rows.items() for s in r.substrings
                   if any(t in s for t in tokens)]
        self.assertEqual(
            claimed, [("camera-snaps-instead-of-pushing",
                       "CAMERA_PUSH_IN_NOT_GRADUAL at=")], claimed)
        self.assertIn("PUSH_PROGRESS_TOL", src)
        self.assertEqual(mod.PUSH_PROGRESS_TOL, 0.20)


class TestConstantDenominator(unittest.TestCase):
    def test_every_leg_reports_twelve_checks(self):
        mod = _load_script()
        self.assertEqual(len(mod.CHECK_IDS), 12)
        self.assertEqual(len(set(mod.CHECK_IDS)), 12)
        legs = [build_reference()] + [f() for f, _ in NEGATIVE_LEGS.values()]
        for i, seq in enumerate(legs):
            with self.subTest(leg=i):
                _m, parsed = run_leg(seq)
                self.assertTrue(parsed.found)
                self.assertEqual(parsed.total, 12)

    def test_loaded_object_that_is_not_a_sequence_still_reports_twelve(self):
        _m, parsed = run_leg(NotASequence())
        self.assertEqual(parsed.total, 12)
        self.assertEqual(parsed.passed_count, 0)
        self.assertIn("SEQ_ASSET_NOT_LEVEL_SEQUENCE class=",
                      details(parsed)["sequence_asset_exists"])


class TestFailClosed(unittest.TestCase):
    def test_unreadable_spawnable_list_fails_both_ownership_checks(self):
        seq = build_reference()
        seq.spawnables_raise = True
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["camera_spawned_by_sequence"][0])
        self.assertFalse(d["hero_spawned_by_sequence"][0])
        self.assertIn("SPAWNABLE_READ_ERROR", d["camera_spawned_by_sequence"][1])

    def test_unresolvable_channel_fails_rather_than_reading_as_unkeyed(self):
        seq = build_reference()
        # A transform section that carries no "Location.Z" channel at all.
        seq.bindings[1].tracks = [MovieScene3DTransformTrack(
            sections=[Section(start=0.0, end=6.0, channels=[])])]
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["hero_rises_then_holds"][0])
        self.assertIn("HERO_RISE_READ_ERROR", d["hero_rises_then_holds"][1])

    def test_fade_section_with_no_channels_fails(self):
        seq = build_reference()
        seq.tracks[1].sections = [Section(channels=[])]
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["fade_in_from_black"][0])
        self.assertIn("FADE_READ_ERROR", d["fade_in_from_black"][1])

    def test_unbounded_camera_cut_is_rejected_not_read_as_minus_one(self):
        seq = build_reference()
        seq.tracks[0].sections = [Section(camera_guid="CAM-GUID")]
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["camera_cut_covers_whole_shot"][0])
        self.assertIn("CAMERA_CUT_RANGE_WRONG", d["camera_cut_covers_whole_shot"][1])

    def test_two_cut_sections_are_rejected(self):
        seq = build_reference()
        seq.tracks[0].sections.append(
            Section(start=3.0, end=6.0, camera_guid="CAM-GUID"))
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["camera_cut_covers_whole_shot"][0])

    def test_engine_default_timeline_fails_both_header_checks(self):
        """The dead-gate audit's whole point: 5s @ 30fps must NOT pass."""
        seq = build_reference(display_rate=(30, 1), playback=(0.0, 5.0))
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        self.assertFalse(d["sequence_display_rate_24fps"][0])
        self.assertFalse(d["sequence_spans_six_seconds"][0])
        self.assertIn("SEQ_DISPLAY_RATE_WRONG rate=", d["sequence_display_rate_24fps"][1])
        self.assertIn("SEQ_DURATION_WRONG start=", d["sequence_spans_six_seconds"][1])

    def test_cut_pointing_at_an_unknown_binding_fails_closed(self):
        seq = build_reference()
        seq.tracks[0].sections = [Section(start=0.0, end=6.0,
                                          camera_guid="NO-SUCH-GUID")]
        _m, parsed = run_leg(seq)
        d = {c.id: (c.passed, c.detail) for c in parsed.checks}
        for cid in ("camera_cut_targets_cine_camera", "camera_spawned_by_sequence",
                    "camera_pushes_in_over_full_shot"):
            self.assertFalse(d[cid][0])
            self.assertIn("CAMERA_CUT_BINDING_UNRESOLVED guid=", d[cid][1])

    def test_hero_bound_but_possessed_fails_only_the_ownership_gate(self):
        seq = build_reference()
        seq.bindings[1].spawnable = False
        _m, parsed = run_leg(seq)
        self.assertEqual(failed_ids(parsed), ["hero_spawned_by_sequence"])
        self.assertIn("HERO_BINDING_NOT_SPAWNABLE name=",
                      details(parsed)["hero_spawned_by_sequence"])


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """A broken UE API name must never be credited as a variant's failure."""

    ERROR_MARKERS = ("_READ_ERROR", "_PROBE_ERROR", "_LOAD_ERROR",
                     "_UNRESOLVED", "_UNAVAILABLE", "_ABORTED",
                     "CHECK_NOT_EVALUATED")

    def test_no_matrix_substring_contains_an_error_marker(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for label, row in rows.items():
            for s in row.substrings:
                for marker in self.ERROR_MARKERS:
                    self.assertNotIn(marker, s, "%s: %r" % (label, s))

    def test_no_matrix_substring_is_produced_by_the_no_unreal_run(self):
        """With no ``unreal`` module at all, every check errors out - and none
        of those error details may satisfy a matrix row."""
        mod = _load_script()
        mod.unreal = None
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main()
        parsed = parse_introspect_verdict(buf.getvalue())
        self.assertEqual(parsed.total, 12)
        self.assertEqual(parsed.passed_count, 0)
        blob = "\n".join(c.detail for c in parsed.checks)
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for label, row in rows.items():
            if row.expect_pass:
                continue
            for s in row.substrings:
                self.assertNotIn(
                    s, blob,
                    "%s's substring %r is emitted by a pure API failure" % (label, s))


class TestAutomationMarkersAbsent(unittest.TestCase):
    """``parse_automation_log`` counts these substrings as TESTS anywhere in
    the log, which would inflate the tally and can flip a PASS to a FAIL."""

    def test_script_source_carries_neither_marker(self):
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult" + "=Passed", src)
        self.assertNotIn("Automation Test" + " Succeeded", src)

    def test_script_source_is_ascii(self):
        self.assertTrue(SCRIPT_PATH.read_text(encoding="utf-8").isascii())


if __name__ == "__main__":
    unittest.main()
