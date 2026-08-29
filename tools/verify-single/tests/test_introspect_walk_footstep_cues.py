"""Offline oracle for the t1-walk-animation-footstep-cues L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models the
reflection surface the introspect script actually uses, so every leg of
``discrimination/MATRIX.md`` can be simulated and joined against the REAL
``discriminate.parse_matrix`` + the REAL ``layers/l2_introspect`` parser.

What this pins:
  * every negative leg's MATRIX substring is a literal the script PRINTS, on
    the check the MATRIX blames;
  * the array/scalar return-shape split - a cue list of exactly TWO elements
    matches UE's ``(return_value, out_param)`` tuple shape, and unwrapping it
    would drop a cue on the very submission the task is calibrated on;
  * the negative check ``jog_carries_no_cues`` fails CLOSED even though "zero
    cues" is its passing state - a deleted sibling, an unreadable accessor, a
    non-animation asset and two accessors disagreeing must all FAIL, not pass;
  * the length/frame oracle failing to load is a FAIL, never a free pass;
  * a constant denominator of 10 on every leg, including with no ``unreal``.

The fake is deliberately dumb: it models asset paths, clip length/frames and a
list of named, timed, spanned cues, and nothing else. It cannot prove the UE
API names are right - only a live editor does that - but it does prove the
grader's LOGIC and its printed tokens.
"""
import contextlib
import importlib.util
import io
import json
import re
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

TASK_DIR = _REPO / "tasks" / "bp" / "t1-walk-animation-footstep-cues"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "walk_animation_footstep_cues.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("_walk_cues_introspect",
                                                  SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# the fake unreal module                                                       #
# --------------------------------------------------------------------------- #

# Placeholder stand-ins for the STOCK clip's real numbers. The real values are
# a calibration item (notes.md section 5); nothing in the grader hard-codes
# them - it reads them off the stock asset - so the fake only has to be
# self-consistent.
STOCK_LENGTH = 1.200
STOCK_FRAMES = 36


class _Class:
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


class _UObject:
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def get_class(self):
        return _Class(type(self).__name__)


class AnimNotifyState(_UObject):
    """Stands in for the ranged-cue backing object."""


class NotifyEvent:
    def __init__(self, name, time, duration=0.0, state_class=None):
        self.name = name
        self.time = float(time)
        self.duration = float(duration)
        self.state_class = state_class

    def get_editor_property(self, prop):
        if prop in ("notify_name", "NotifyName"):
            return self.name
        if prop in ("notify_state_class", "NotifyStateClass"):
            return self.state_class
        raise Exception("unknown property %r" % (prop,))


class AnimSequenceBase(_UObject):
    def __init__(self, name, length=STOCK_LENGTH, frames=STOCK_FRAMES,
                 events=None):
        _UObject.__init__(self, name)
        self.length = float(length)
        self.frames = int(frames)
        self.events = list(events or [])


class NotAnAnimation(_UObject):
    """Something else entirely, sitting at an animation's path."""


class _World:
    def __init__(self):
        self.assets = {}          # path -> object
        self.reader_shape = None  # None | "scalar" | "missing" | "disagree"


WORLD = _World()


class _EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(path):
        return path in WORLD.assets

    @staticmethod
    def load_asset(path):
        return WORLD.assets.get(path)


class _AnimationLibrary:
    @staticmethod
    def get_animation_notify_events(seq):
        if WORLD.reader_shape == "scalar":
            return 0          # a shape change that must RAISE, not read as []
        return list(seq.events)

    @staticmethod
    def get_animation_notify_event_names(seq):
        if WORLD.reader_shape == "disagree":
            return []         # names say empty while events say otherwise
        return sorted({e.name for e in seq.events})

    @staticmethod
    def get_anim_notify_event_trigger_time(event):
        return event.time

    @staticmethod
    def get_anim_notify_event_duration(event):
        return event.duration

    @staticmethod
    def get_sequence_length(seq):
        return seq.length

    @staticmethod
    def get_num_frames(seq):
        return seq.frames


class _AnimationLibraryNoReader(_AnimationLibrary):
    get_animation_notify_events = None


class FakeUnreal:
    EditorAssetLibrary = _EditorAssetLibrary
    AnimationLibrary = _AnimationLibrary
    AnimSequenceBase = AnimSequenceBase

    @staticmethod
    def log(msg):
        pass


# --------------------------------------------------------------------------- #
# leg builders                                                                 #
# --------------------------------------------------------------------------- #

MOD = _load_script()
WALK = MOD.ASSET_WALK
JOG = MOD.ASSET_JOG
ORACLE = MOD.ORACLE_WALK


def _stock_oracle():
    WORLD.assets[ORACLE] = AnimSequenceBase("MF_Unarmed_Walk_Fwd")


def _walk(events=(), length=STOCK_LENGTH, frames=STOCK_FRAMES):
    WORLD.assets[WALK] = AnimSequenceBase("A_WalkForward", length, frames,
                                          list(events))


def _jog(events=()):
    WORLD.assets[JOG] = AnimSequenceBase("A_JogForward", 0.9, 27, list(events))


def _two_good_cues():
    return [NotifyEvent("Footstep", 0.25), NotifyEvent("Footstep", 0.75)]


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _stock_oracle()
    _walk(_two_good_cues())
    _jog()


@_leg("empty")
def _empty():
    # The substrate ships BOTH baselines; an empty submission leaves the walk
    # clip's timeline completely empty.
    _stock_oracle()
    _walk()
    _jog()


@_leg("cues-at-wrong-times")
def _cues_at_wrong_times():
    _stock_oracle()
    _walk([NotifyEvent("Footstep", 0.30), NotifyEvent("Footstep", 0.70)])
    _jog()


@_leg("ranged-cues-not-instants")
def _ranged_cues_not_instants():
    _stock_oracle()
    state = AnimNotifyState("ANS_Footstep")
    _walk([NotifyEvent("Footstep", 0.25, 0.20, state),
           NotifyEvent("Footstep", 0.75, 0.15, state)])
    _jog()


@_leg("extra-cues-left-on-clip")
def _extra_cues_left_on_clip():
    _stock_oracle()
    _walk(_two_good_cues() + [NotifyEvent("Land", 0.10),
                              NotifyEvent("Step", 0.90)])
    _jog()


@_leg("clip-retimed-to-short-stub")
def _clip_retimed_to_short_stub():
    _stock_oracle()
    _walk(_two_good_cues(), length=1.000, frames=30)
    _jog()


@_leg("cues-on-both-clips")
def _cues_on_both_clips():
    _stock_oracle()
    _walk(_two_good_cues())
    _jog(_two_good_cues())


def run_leg(builder, unreal_module=FakeUnreal):
    """Run the introspect script against a freshly built world."""
    global WORLD
    WORLD = _World()
    MOD.unreal = unreal_module
    builder()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        MOD.main()
    out = buf.getvalue()
    return out, parse_introspect_verdict(out)


def _by_id(parsed):
    return {c.id: c for c in parsed.checks}


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #

class TestMatrixIsCreditable(unittest.TestCase):
    """Every MATRIX row must be parseable AND its substring actually printed."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_every_declared_leg_has_a_row(self):
        self.assertEqual(set(self.rows), set(LEGS))

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for s in row.substrings:
                self.assertNotIn("`", s,
                                 "%s: backticks never match log text" % label)

    def test_reference_leg_passes_all_ten(self):
        out, parsed = run_leg(LEGS["reference"])
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, 10)
        failed = [(c.id, c.detail) for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [], out)

    def test_every_leg_reports_the_same_ten_checks(self):
        for label, builder in LEGS.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(builder)
                self.assertEqual(parsed.total, 10)
                self.assertEqual([c.id for c in parsed.checks],
                                 list(MOD.CHECK_IDS))

    def test_every_negative_leg_fails_with_its_named_substring(self):
        for label, builder in LEGS.items():
            row = self.rows[label]
            if row.expect_pass:
                continue
            with self.subTest(leg=label):
                out, parsed = run_leg(builder)
                self.assertTrue(parsed.found)
                self.assertEqual(parsed.total, 10)
                self.assertLess(parsed.passed_count, 10, "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks
                                    if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        """The substring must appear on the check the MATRIX blames, not just
        somewhere in the verdict."""
        expected = {
            "empty": "walk_has_exactly_two_footstep_cues",
            "cues-at-wrong-times": "walk_footstep_at_quarter_second",
            "ranged-cues-not-instants": "walk_footsteps_are_instantaneous",
            "extra-cues-left-on-clip": "walk_carries_no_other_cues",
            "clip-retimed-to-short-stub": "walk_timeline_length_unchanged",
            "cues-on-both-clips": "jog_carries_no_cues",
        }
        self.assertEqual(set(expected) | {"reference"}, set(LEGS))
        for label, check_id in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = _by_id(parsed)[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)

    def test_each_variant_fails_only_its_predicted_family(self):
        """A variant that failed everything would not discriminate anything."""
        budget = {
            "cues-at-wrong-times": 2,
            "ranged-cues-not-instants": 1,
            "extra-cues-left-on-clip": 1,
            "clip-retimed-to-short-stub": 2,
            "cues-on-both-clips": 1,
        }
        for label, allowed in budget.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                failed = [c.id for c in parsed.checks if not c.passed]
                self.assertEqual(len(failed), allowed, failed)


class TestFailsClosed(unittest.TestCase):
    """No check may pass because a probe merely did not raise."""

    def test_two_cues_are_not_collapsed_by_the_out_param_unwrap(self):
        # A list of exactly 2 matches UE's (return_value, out_param) tuple
        # shape. Unwrapping it would report 1 Footstep on the REFERENCE.
        _, parsed = run_leg(LEGS["reference"])
        got = _by_id(parsed)["walk_has_exactly_two_footstep_cues"]
        self.assertTrue(got.passed, got.detail)
        self.assertIn("found=2", got.detail)

    def test_deleted_sibling_is_not_scored_as_a_silent_sibling(self):
        def build():
            _stock_oracle()
            _walk(_two_good_cues())
            # no jog at all
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["jog_asset_exists"].passed)
        self.assertFalse(by_id["jog_carries_no_cues"].passed)
        self.assertIn("JOG_ASSET_MISSING /Game/Tasks/",
                      by_id["jog_carries_no_cues"].detail)

    def test_unreadable_cue_accessor_is_not_scored_as_silence(self):
        class NoReader(FakeUnreal):
            AnimationLibrary = _AnimationLibraryNoReader

        def build():
            _stock_oracle()
            _walk(_two_good_cues())
            _jog()
        _, parsed = run_leg(build, unreal_module=NoReader)
        got = _by_id(parsed)["jog_carries_no_cues"]
        self.assertFalse(got.passed)
        self.assertIn("JOG_CUE_READ_ERROR", got.detail)

    def test_wrong_return_shape_is_not_scored_as_silence(self):
        def build():
            _stock_oracle()
            _walk(_two_good_cues())
            _jog()
            WORLD.reader_shape = "scalar"
        _, parsed = run_leg(build)
        got = _by_id(parsed)["jog_carries_no_cues"]
        self.assertFalse(got.passed)
        self.assertIn("JOG_CUE_READ_ERROR", got.detail)

    def test_disagreeing_accessors_are_not_scored_as_silence(self):
        # events say "two cues", names say "none". One of the two is lying;
        # neither answer may be credited.
        def build():
            _stock_oracle()
            _walk(_two_good_cues())
            _jog(_two_good_cues())
            WORLD.reader_shape = "disagree"
        _, parsed = run_leg(build)
        got = _by_id(parsed)["jog_carries_no_cues"]
        self.assertFalse(got.passed)
        self.assertIn("JOG_CUE_READ_ERROR", got.detail)

    def test_non_animation_at_the_walk_path_is_not_a_clip_with_no_cues(self):
        def build():
            _stock_oracle()
            WORLD.assets[WALK] = NotAnAnimation("A_WalkForward")
            _jog()
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertTrue(by_id["walk_asset_exists"].passed)  # it does exist ...
        self.assertFalse(by_id["walk_has_exactly_two_footstep_cues"].passed)
        self.assertIn("WALK_LOAD_READ_ERROR",
                      by_id["walk_has_exactly_two_footstep_cues"].detail)

    def test_missing_length_oracle_fails_rather_than_passes(self):
        def build():
            _walk(_two_good_cues())   # no stock oracle in the world
            _jog()
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["walk_timeline_length_unchanged"].passed)
        self.assertFalse(by_id["walk_frame_count_unchanged"].passed)
        self.assertIn("WALK_LENGTH_READ_ERROR",
                      by_id["walk_timeline_length_unchanged"].detail)

    def test_both_cues_at_the_same_moment_fails_both_placement_checks(self):
        def build():
            _stock_oracle()
            _walk([NotifyEvent("Footstep", 0.25), NotifyEvent("Footstep", 0.25)])
            _jog()
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["walk_footstep_at_quarter_second"].passed)
        self.assertFalse(by_id["walk_footstep_at_three_quarter_second"].passed)

    def test_correctly_placed_cues_under_a_different_name_fail(self):
        def build():
            _stock_oracle()
            _walk([NotifyEvent("Foot_L", 0.25), NotifyEvent("Foot_R", 0.75)])
            _jog()
        _, parsed = run_leg(build)
        got = _by_id(parsed)["walk_has_exactly_two_footstep_cues"]
        self.assertFalse(got.passed)
        self.assertIn("WALK_FOOTSTEP_COUNT_WRONG found=0", got.detail)

    def test_walk_missing_entirely_fans_out_without_touching_jog(self):
        def build():
            _stock_oracle()
            _jog()
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertIn("WALK_ASSET_MISSING /Game/Tasks/",
                      by_id["walk_asset_exists"].detail)
        for cid in MOD.CHECK_IDS:
            if cid.startswith("walk_"):
                self.assertFalse(by_id[cid].passed, cid)
        self.assertTrue(by_id["jog_asset_exists"].passed)
        self.assertTrue(by_id["jog_carries_no_cues"].passed)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def test_no_error_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tokens = sorted({t for t in re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                         if t.endswith(("_ERROR", "_ABORTED", "_UNAVAILABLE",
                                        "_EMPTY", "_NOT_EVALUATED", "_WRONG"))
                         and not t.startswith(("WALK_FOOTSTEP_COUNT",
                                               "WALK_CUE_TOTAL"))})
        self.assertTrue(tokens, "expected the script to define error tokens")
        for token in tokens:
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_script_carries_no_automation_result_marker(self):
        # parse_automation_log's whole-file finditer counts these as TESTS.
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult" + "=Passed", source)
        self.assertNotIn("Automation Test" + " Succeeded", source)

    def test_script_is_pure_ascii(self):
        raw = SCRIPT_PATH.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_matrix_substrings_are_ascii_and_contain_a_space(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for label, row in rows.items():
            for sub in row.substrings:
                sub.encode("ascii")
                self.assertIn(" ", sub,
                              "%s: a space-less tick is dropped by "
                              "_extract_substrings" % label)

    def test_offline_run_without_unreal_fails_every_check(self):
        """No editor => 0/10, all error tokens. Never a vacuous PASS."""
        global WORLD
        WORLD = _World()
        MOD.unreal = None
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                MOD.main()
            out = buf.getvalue()
            parsed = parse_introspect_verdict(out)
            self.assertEqual(parsed.total, 10)
            self.assertEqual(parsed.passed_count, 0)
            payload = json.loads(out.splitlines()[1])
            self.assertEqual(len(payload["checks"]), 10)
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()
