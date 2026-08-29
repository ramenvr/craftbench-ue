"""Author the `montage-plays-the-wrong-clip` discrimination variant.

Isolates C7 (montage_plays_the_clip), which no other leg does:
duplicate-the-shipped-set/ fails C4-C7 at once and is credited at C4, so C7 has never
been any leg's first failure.

  SK_TaskRig        shipped baseline, untouched
  A_TaskMotion      AnimSequence on SK_TaskRig         -> C1, C4 PASS
  A_TaskMotionAlt   a SECOND clip on the SAME task rig -> the decoy
  AM_TaskAction     montage built from the DECOY       -> C2, C5 PASS, C7 FAIL
  ABP_TaskLogic     AnimBlueprint on SK_TaskRig        -> C3, C6 PASS

The decoy must live on the task rig: AnimMontageFactory.source_animation derives the
montage's anchor from its source clip, so pointing at the STOCK clip would also break
C5 and destroy the isolation. 6/7, failing C7 alone.

Plausible rather than contrived -- what a submission looks like when it authors two
clips and wires the montage to whichever it made last.

Authored AT the grading path with the internal name asserted. SK_TaskRig is shipped
baseline and is required, never re-created: a script-invented rig would make the
anchor comparison compare against itself.
"""
import contextlib
import io
import json
import os
import re
import sys

import unreal

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(_HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(_HERE))))
GRADER = os.path.join(REPO_ROOT, "tools", "verify-single", "introspect",
                      "kp_motion_set_shares_one_rig.py")

# Shared harvest (raises rather than partially harvesting). Unit-tested off-box at
# tools/authoring/tests/.
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "authoring"))
import cb_variant_lib as CBV  # noqa: E402

TASK = "kp-motion-set-shares-one-rig"
VARIANT = "montage-plays-the-wrong-clip"
DIR = "/Game/Tasks/" + TASK

RIG = DIR + "/SK_TaskRig"          # shipped baseline — required, never authored here
CLIP = DIR + "/A_TaskMotion"       # the clip the montage is SUPPOSED to play
DECOY = DIR + "/A_TaskMotionAlt"   # the clip it plays instead
MONT = DIR + "/AM_TaskAction"
ABP = DIR + "/ABP_TaskLogic"

#: Authored by this script, and therefore what must be harvested.
AUTHORED = (CLIP, DECOY, MONT, ABP)

OUT = []


def say(k, v):
    OUT.append("%-46s %s" % (k, v))


def anchor_of(path):
    """The rig an asset is anchored to, or None. Registry-free object read."""
    a = unreal.EditorAssetLibrary.load_asset(path)
    if a is None:
        return "<absent>"
    for prop in ("skeleton", "target_skeleton"):
        try:
            s = a.get_editor_property(prop)
            if s is not None:
                return s.get_path_name().split(".")[0]
        except Exception:  # noqa: BLE001
            continue
    return None


def played_clip(montage):
    try:
        return montage.get_first_anim_reference().get_path_name().split(".")[0]
    except Exception as e:  # noqa: BLE001
        return "<unreadable %s>" % type(e).__name__


def self_grade():
    """Run the REAL grader in-process and return its checks.

    Turns a *predicted* verdict into a *measured* one inside the same headless
    boot, so a leg that does not isolate C7 is caught before harvesting rather
    than after a ~300 s-per-leg `cb discriminate`. Recipe from
    `kp-anim-track-bake/aids/author_reference.py`; `__name__` is deliberately not
    `__main__` so the grader's entry guard stays quiet and `main()` is explicit.
    """
    if not os.path.isfile(GRADER):
        return None, "grader not found at %s" % GRADER
    src = io.open(GRADER, encoding="utf-8").read()
    buf = io.StringIO()
    ns = {"__name__": "__cb_selfgrade__", "__file__": GRADER}
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, GRADER, "exec"), ns)  # noqa: S102 verifier-owned
            ns["main"]()
    except Exception as e:  # noqa: BLE001
        return None, "grader raised %r" % (e,)
    m = re.search(r"CRAFTBENCH-INTROSPECT-JSON-START\s*\n(.*?)\n\s*"
                  r"CRAFTBENCH-INTROSPECT-JSON-END", buf.getvalue(), re.S)
    if m is None:
        return None, "self-grade produced no verdict block"
    try:
        checks = json.loads(m.group(1))["checks"]
    except Exception as e:  # noqa: BLE001
        return None, "unparseable verdict block %r" % (e,)
    # Return the repo-standard VECTOR shape {cid: (passed, detail)} — identical to
    # every aids/author_reference.py grade_in_process() — so cb_variant_lib's
    # acceptance() can consume it directly. Returning the raw list here is what
    # broke the first authoring run (NameError, then a shape mismatch).
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}, None


def main():
    tools = unreal.AssetToolsHelpers.get_asset_tools()

    # The rig is SHIPPED BASELINE. Re-duplicating it from stock here would make
    # the anchor comparison meaningless (it would compare against a rig this
    # script invented), so require the committed one.
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    if rig is None:
        raise RuntimeError(
            "%s is absent. It is shipped substrate baseline, not something this "
            "script may author — open the substrate project, do not re-create it."
            % RIG)
    say("baseline.rig", rig.get_path_name().split(".")[0])

    # Author one leg at a time: the reference and every variant share these paths.
    for p in AUTHORED:
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            raise RuntimeError(
                "%s already exists — author one leg at a time (the reference and "
                "every variant share these paths). Delete it first." % p)

    # ---- the clip the montage SHOULD play (correct, so C1/C4 pass) ----------
    f = unreal.AnimSequenceFactory()
    f.set_editor_property("target_skeleton", rig)
    clip = tools.create_asset("A_TaskMotion", DIR, unreal.AnimSequence, f)

    # ---- the decoy: a second, equally valid clip on the SAME task rig -------
    f2 = unreal.AnimSequenceFactory()
    f2.set_editor_property("target_skeleton", rig)
    decoy = tools.create_asset("A_TaskMotionAlt", DIR, unreal.AnimSequence, f2)

    # ---- THE SINGLE DELTA: the montage is built from the DECOY --------------
    fm = unreal.AnimMontageFactory()
    fm.set_editor_property("source_animation", decoy)
    mont = tools.create_asset("AM_TaskAction", DIR, unreal.AnimMontage, fm)

    fa = unreal.AnimBlueprintFactory()
    fa.set_editor_property("target_skeleton", rig)
    tools.create_asset("ABP_TaskLogic", DIR, unreal.AnimBlueprint, fa)

    for p in AUTHORED:
        a = unreal.EditorAssetLibrary.load_asset(p)
        if a is None:
            raise RuntimeError("authoring produced nothing at %s" % p)
        internal = a.get_path_name().split(".")[0]
        if internal != p:
            raise RuntimeError(
                "internal package name %r != grading path %r — harvesting this "
                "would commit a PACKAGE_IDENTITY_MISMATCH" % (internal, p))
        unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)
        say("saved", internal)

    # ---- predict the grade, per check --------------------------------------
    anchors = {"clip": anchor_of(CLIP), "montage": anchor_of(MONT),
               "animbp": anchor_of(ABP), "decoy": anchor_of(DECOY)}
    for k, v in anchors.items():
        say("anchor." + k, v)
    played = played_clip(mont)
    say("montage_plays", played)

    say("PREDICT.C4_clip_uses_task_rig",
        "PASS" if anchors["clip"] == RIG else "FAIL MOTIONSET_WRONG_RIG")
    say("PREDICT.C5_montage_uses_task_rig",
        "PASS" if anchors["montage"] == RIG else "FAIL MOTIONSET_WRONG_RIG")
    say("PREDICT.C6_animbp_uses_task_rig",
        "PASS" if anchors["animbp"] == RIG else "FAIL MOTIONSET_WRONG_RIG")
    say("PREDICT.C7_montage_plays_the_clip",
        "PASS" if played == CLIP
        else "FAIL MOTIONSET_LINK_WRONG expected=%s got=%s" % (CLIP, played))

    # ---- MEASURE it with the real grader, in this same boot ----------------
    vector, err = self_grade()
    if err:
        say("SELFGRADE", "UNAVAILABLE %s" % err)
        say("VERDICT.isolates_C7_alone", "UNVERIFIED — predicted only")
        return
    passed, total = CBV.score(vector)
    failed = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    say("SELFGRADE", "%d/%d" % (passed, total))
    for cid in sorted(vector):
        ok_c, detail = vector[cid]
        say("  " + ("PASS " if ok_c else "FAIL "), "%s %s" % (cid, detail))

    # THE ACCEPTANCE CRITERION: exactly one failure, and it is C7. A leg that
    # fails more than C7 proves nothing `duplicate-the-shipped-set` already did,
    # so refuse to bless it rather than harvest a leg crediting a substring it
    # did not isolate.
    ok, why = CBV.acceptance(vector, "montage_plays_the_clip",
                             "MOTIONSET_LINK_WRONG expected=")
    say("VERDICT.isolates_C7_alone", ok)
    if not ok:
        say("DO NOT HARVEST", why)
        return

    # Harvest BEFORE the module-level cleanup deletes the staged assets. The first
    # run proved 6/7 isolating C7 and then deleted everything, because printing
    # "HARVEST OK" is not harvesting.
    # NOTE: SK_TaskRig is shipped substrate baseline and is deliberately NOT
    # harvested — a submission does not deliver it, and including it would make the
    # leg's overlay differ from the reference's in a second way.
    substrate_task_dir = os.path.join(
        REPO_ROOT, "UE-projects", "ThirdPerson", "Content", "Tasks", TASK)
    try:
        dst = CBV.harvest(TASK_DIR, VARIANT, TASK,
                          ("A_TaskMotion", "A_TaskMotionAlt", "AM_TaskAction",
                           "ABP_TaskLogic"),
                          substrate_task_dir)
    except CBV.AuthoringError as e:
        say("DO NOT HARVEST", str(e))
        return
    say("HARVESTED", dst)
    say("OK", why)


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    say("FATAL", "%s: %s" % (type(e).__name__, e))
    OUT.append(traceback.format_exc()[-900:])

print("R26-VARIANT-START")
for line in OUT:
    print(line)
print("R26-VARIANT-END")
sys.stdout.flush()

if os.environ.get("CB_KEEP_STAGED") != "1":
    try:
        for p in AUTHORED:
            if unreal.EditorAssetLibrary.does_asset_exist(p):
                unreal.EditorAssetLibrary.delete_asset(p)
        print("cleanup done (authored assets removed; SK_TaskRig kept)")
    except Exception as e:  # noqa: BLE001
        print("cleanup skipped: %r" % (e,))
sys.stdout.flush()
