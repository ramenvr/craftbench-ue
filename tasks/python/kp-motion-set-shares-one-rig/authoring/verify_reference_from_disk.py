"""AUTHORING-TIME grader prototype: does the reference read back FROM DISK?

WHY IT COUNTS 8 WHEN THE SHIPPED GRADER COUNTS 7, since the mismatch is
otherwise alarming (flagged in code review). This script is not the grader
and its tally is not the score. It additionally asserts `rig_present` — that the
substrate baseline `SK_TaskRig` is actually on disk — because that is the
authoring step most likely to be missed, and getting it wrong is exactly how the
t2-consistent-enum-names salvage shipped a reference that could not pass its own
grader.

The SHIPPED grader deliberately does NOT check the rig: the submission overlay is
copy-only, so a deleted baseline is restored before grading and the check could
never fail — a dead gate. See `tools/verify-single/introspect/
kp_motion_set_shares_one_rig.py` (7 checks) and the task's requirements table,
row 7, which records that reasoning.

So: 8 here = the grader's 7 + one authoring-only precondition.

The spike found an in-session read that did NOT survive a reload
(package_dependencies threw on a same-session montage but worked on a shipped
one), so every fact below is read in a FRESH editor from committed bytes --
which is what the real grader does.
"""
import sys
import unreal

TASK = "kp-motion-set-shares-one-rig"
D = "/Game/Tasks/" + TASK
RIG, CLIP, MONT, ABP = D+"/SK_TaskRig", D+"/A_TaskMotion", D+"/AM_TaskAction", D+"/ABP_TaskLogic"
STOCK_RIG = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
CHECKS = []

def check(cid, ok, detail):
    CHECKS.append((cid, bool(ok), detail))

def load(p):
    try:
        return unreal.EditorAssetLibrary.load_asset(p)
    except Exception:
        return None

def anchor(a):
    for prop in ("skeleton", "target_skeleton"):
        try:
            s = a.get_editor_property(prop)
            if s is not None:
                return s.get_path_name().split(".")[0]
        except Exception:
            continue
    return None

rig = load(RIG)
check("rig_present", rig is not None and rig.get_class().get_name() == "Skeleton",
      "RIG_MISSING" if rig is None else "rig_class=%s" % rig.get_class().get_name())

for cid, path, cls in (("clip_present", CLIP, "AnimSequence"),
                       ("montage_present", MONT, "AnimMontage"),
                       ("animbp_present", ABP, "AnimBlueprint")):
    a = load(path)
    check(cid, a is not None and a.get_class().get_name() == cls,
          "ABSENT %s" % path if a is None else "class=%s" % a.get_class().get_name())

for cid, path in (("clip_on_task_rig", CLIP),
                  ("montage_on_task_rig", MONT),
                  ("animbp_on_task_rig", ABP)):
    a = load(path)
    got = anchor(a) if a else "<absent>"
    check(cid, got == RIG,
          "anchor=%s" % got if got != RIG else "OK",)

m = load(MONT)
try:
    ref = m.get_first_anim_reference().get_path_name().split(".")[0]
except Exception as e:
    ref = "ERR:%s" % type(e).__name__
check("montage_plays_the_clip", ref == CLIP, "plays=%s" % ref)

print("R26-VERIFY-START")
for cid, ok, detail in CHECKS:
    print("%-26s %-5s %s" % (cid, "PASS" if ok else "FAIL", detail))
print("TALLY %d/%d" % (sum(1 for _,o,_ in CHECKS if o), len(CHECKS)))
print("R26-VERIFY-END")
sys.stdout.flush()
