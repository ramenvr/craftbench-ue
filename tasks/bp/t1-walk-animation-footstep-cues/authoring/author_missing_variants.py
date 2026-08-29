"""Author the 2 missing footstep-row discrimination variants IN THE SUBSTRATE.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

The runner script (run_author_missing_variants.sh, same folder) wraps this with
the baseline backup / harvest / restore file steps - this script only MUTATES
SUBSTRATE assets in place and prints verdict lines; it never touches the
tasks/ tree itself. The runner must back the two baseline .uassets up FIRST.

What gets authored here (contracts: the two README-MISSING-ASSETS.md files):
  1. variant cues-on-both-clips  -> A_JogForward gains the two reference cues
     (its A_WalkForward half is a byte-for-byte file copy of the reference,
     done by the runner - no editor needed).
  2. variant clip-retimed-to-short-stub -> A_WalkForward becomes a clip of a
     MATERIALLY different length (>=0.10 s from stock, still > 0.80 s),
     carrying the same two perfect cues.
     Route A: true retime via the AnimationData controller, IF Python-exposed
       (engine source shows no reflected GetController route, so this is a
       runtime probe - see notes.md section 5's "return shapes" caveat).
     Route B (guaranteed): a DIFFERENT stock clip wearing the right name -
       which is exactly what the variant models ("a different clip wearing the
       right name", README line 13). Picks the stock Unarmed clip whose length
       is farthest from the oracle's, preferring shorter, requiring >=0.15 s
       difference (1.5x the graded minimum) and > 0.80 s.

Cue mechanism (verified against the LANDED reference binary, which imports
/Game/Tasks/<id>/AnimNotify_Footstep - the shipped Blueprint notify class):
  AnimationLibrary.add_animation_notify_event(seq, track, t, notify_class)
with the class loaded from the task folder. The engine derives NotifyName
"Footstep" from the class name; the read-back below asserts it.

Output contract (grep the EDITOR LOG - newest ThirdPerson*.log; a second
editor instance writes ThirdPerson_2.log):
  FOOTSTEP-CAL    stock oracle measurements (notes.md section 5 record)
  VARIANT-JOG-OK / VARIANT-RETIME-OK  per-variant success + read-back numbers
  FOOTSTEP-VARIANTS-DONE              overall success marker; absent = FAILED

Every read-back gate FAILS CLOSED: nothing is saved unless the numbers match,
so a half-authored asset can never be harvested into the variant folder.
"""
import unreal

TASK_ID = "t1-walk-animation-footstep-cues"
TASK_DIR = "/Game/Tasks/%s" % TASK_ID
ASSET_WALK = "%s/A_WalkForward" % TASK_DIR
ASSET_JOG = "%s/A_JogForward" % TASK_DIR
NOTIFY_CLASS = "%s/AnimNotify_Footstep" % TASK_DIR
ORACLE_WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"
STOCK_ANIM_ROOT = "/Game/Characters/Mannequins/Anims/Unarmed"

CUE_TIMES = (0.25, 0.75)
CUE_NAME = "Footstep"
READBACK_TOL = 0.002     # notes.md section 2: reference-grade placement margin
DURATION_TOL = 1e-3
RETIME_TARGET_S = 1.00   # Route A target (README: "a round 1.00 s")
MIN_LEN_DIFF = 0.15      # 1.5x the variant's graded 0.10 minimum
MIN_LEN_ABS = 0.80       # the 0.75 s cue must fit (notes.md section 1a gate)

LIB = unreal.AnimationLibrary
EAL = unreal.EditorAssetLibrary


def die(msg):
    # No FOOTSTEP-VARIANTS-DONE will be printed; the runner treats that as FAIL.
    print("FOOTSTEP-VARIANTS-ERROR %s" % msg)
    raise SystemExit(msg)


def load_seq(path):
    asset = EAL.load_asset(path)
    if asset is None or not isinstance(asset, unreal.AnimSequenceBase):
        die("not an AnimSequenceBase: %s" % path)
    return asset


def seq_length(seq):
    return float(LIB.get_sequence_length(seq))


def seq_frames(seq):
    return int(LIB.get_num_frames(seq))


def track_name(seq):
    """First existing notify track, else a fresh '1' (notes.md section 2)."""
    try:
        names = list(LIB.get_animation_notify_track_names(seq))
    except Exception as e:  # noqa: BLE001
        die("track name read failed on %s: %r" % (seq.get_name(), e))
    if names:
        return names[0]
    LIB.add_animation_notify_track(seq, "1", unreal.LinearColor.WHITE)
    return "1"


def add_footstep_cues(seq, label):
    """Add the two class-backed cues and FAIL CLOSED on any read-back drift."""
    cls = EAL.load_blueprint_class(NOTIFY_CLASS)
    if cls is None:
        die("notify class missing: %s" % NOTIFY_CLASS)
    track = track_name(seq)
    for t in CUE_TIMES:
        LIB.add_animation_notify_event(seq, track, float(t), cls)

    events = list(LIB.get_animation_notify_events(seq))
    if len(events) != len(CUE_TIMES):
        die("%s: expected %d events after authoring, found %d"
            % (label, len(CUE_TIMES), len(events)))
    names, times, durs = [], [], []
    for ev in events:
        names.append(str(ev.get_editor_property("notify_name")))
        times.append(float(LIB.get_anim_notify_event_trigger_time(ev)))
        durs.append(float(LIB.get_anim_notify_event_duration(ev)))
    times.sort()
    if any(n != CUE_NAME for n in names):
        die("%s: cue names read back %s, need %r x%d - the class-name"
            " derivation did not hold; fix the route, do not rename by hand"
            % (label, names, CUE_NAME, len(CUE_TIMES)))
    for want, got in zip(sorted(CUE_TIMES), times):
        if abs(want - got) > READBACK_TOL:
            die("%s: cue at %.4f s, wanted %.2f +/-%.3f (frame snapping?)"
                % (label, got, want, READBACK_TOL))
    if any(abs(d) > DURATION_TOL for d in durs):
        die("%s: non-zero cue durations %s" % (label, durs))
    return times


def save(seq, label):
    path = seq.get_path_name().split(".")[0]
    if not EAL.save_asset(path, only_if_is_dirty=False):
        die("%s: save_asset failed for %s" % (label, path))


# --------------------------------------------------------------------------- #
# 0. calibration record (notes.md section 5)                                   #
# --------------------------------------------------------------------------- #
oracle = load_seq(ORACLE_WALK)
oracle_len = seq_length(oracle)
oracle_frames = seq_frames(oracle)
print("FOOTSTEP-CAL oracle=%s length=%.4f frames=%d"
      % (ORACLE_WALK, oracle_len, oracle_frames))
if oracle_len <= MIN_LEN_ABS:
    die("oracle clip is %.3f s <= %.2f - the task premise broke" %
        (oracle_len, MIN_LEN_ABS))

# --------------------------------------------------------------------------- #
# 1. variant cues-on-both-clips: the jog clip gains the two cues               #
# --------------------------------------------------------------------------- #
jog = load_seq(ASSET_JOG)
jog_len_before = seq_length(jog)
pre = list(LIB.get_animation_notify_events(jog))
if pre:
    die("jog baseline is not clean: %d pre-existing events" % len(pre))
jog_times = add_footstep_cues(jog, "jog-variant")
if abs(seq_length(jog) - jog_len_before) > 0.001:
    die("jog length moved during cue authoring")
save(jog, "jog-variant")
print("VARIANT-JOG-OK times=[%.4f, %.4f] length=%.4f"
      % (jog_times[0], jog_times[1], jog_len_before))

# --------------------------------------------------------------------------- #
# 2. variant clip-retimed-to-short-stub: a different-length A_WalkForward      #
# --------------------------------------------------------------------------- #
walk = load_seq(ASSET_WALK)
route = None

# --- Route A probe: AnimationData controller (uncertain Python exposure) -----
try:
    getter = getattr(walk, "get_controller", None)
    ctrl = getter() if callable(getter) else None
    if ctrl is not None and hasattr(ctrl, "set_number_of_frames"):
        rate = float(oracle_frames) / oracle_len  # fps of the duplicate
        target_frames = int(round(rate * RETIME_TARGET_S))
        try:
            ctrl.set_number_of_frames(unreal.FrameNumber(target_frames), False)
        except TypeError:
            ctrl.set_number_of_frames(target_frames, False)
        new_len = seq_length(walk)
        if (abs(new_len - RETIME_TARGET_S) <= 0.05
                and seq_frames(walk) == target_frames):
            route = "A-controller"
        else:
            print("FOOTSTEP-WARN route A produced length=%.4f frames=%d - "
                  "falling back" % (new_len, seq_frames(walk)))
except Exception as e:  # noqa: BLE001
    print("FOOTSTEP-WARN route A unavailable: %r" % (e,))

# --- Route B: a different stock clip wearing the right name ------------------
if route is None:
    best, best_len, best_diff = None, None, 0.0
    for ap in EAL.list_assets(STOCK_ANIM_ROOT, recursive=True):
        path = str(ap).split(".")[0]
        if path == ORACLE_WALK:
            continue
        try:
            cand = EAL.load_asset(path)
            if not isinstance(cand, unreal.AnimSequenceBase):
                continue
            clen = float(LIB.get_sequence_length(cand))
        except Exception:  # noqa: BLE001
            continue
        if clen <= MIN_LEN_ABS:
            continue
        diff = abs(clen - oracle_len)
        if diff < MIN_LEN_DIFF:
            continue
        # prefer shorter-than-stock ("short stub"), then largest difference
        key = (clen < oracle_len, diff)
        if best is None or key > (best_len < oracle_len, best_diff):
            best, best_len, best_diff = path, clen, diff
    if best is None:
        die("route B found no stock clip >= %.2f s different from the oracle"
            % MIN_LEN_DIFF)
    if not EAL.delete_asset(ASSET_WALK):
        die("route B could not delete the baseline walk for replacement")
    if not EAL.duplicate_asset(best, ASSET_WALK):
        die("route B duplicate_asset failed from %s" % best)
    walk = load_seq(ASSET_WALK)
    route = "B-substitute src=%s" % best

walk_len = seq_length(walk)
walk_frames = seq_frames(walk)
if abs(walk_len - oracle_len) < 0.10 or walk_len <= MIN_LEN_ABS:
    die("retimed walk length %.4f s does not satisfy the variant contract "
        "(oracle %.4f)" % (walk_len, oracle_len))
if walk_frames == oracle_frames:
    die("retimed walk frame count unchanged (%d) - the frame-count check "
        "would not fire" % walk_frames)
walk_times = add_footstep_cues(walk, "retime-variant")
save(walk, "retime-variant")
print("VARIANT-RETIME-OK route=%s length=%.4f frames=%d oracle_length=%.4f "
      "oracle_frames=%d times=[%.4f, %.4f]"
      % (route, walk_len, walk_frames, oracle_len, oracle_frames,
         walk_times[0], walk_times[1]))

print("FOOTSTEP-VARIANTS-DONE")
