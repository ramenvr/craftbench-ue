"""L2I grader — kp-motion-set-shares-one-rig.

Grades three animation assets the agent AUTHORS FROM SCRATCH, and the one fact
that ties them together: all three must be anchored to the task's own rig, and
the montage must actually play the authored clip.

WHY A TASK-OWNED RIG IS THE WHOLE DESIGN (measured 2026-08-13, one headless
boot; the design did not survive contact with the engine without it).

The obvious version of this task anchors everything to the stock SK_Mannequin
and argues that a lazy submission "leaves the anchor null and fails". THAT IS
FALSE ON UE 5.8 — the engine refuses to create ANY of the three unanchored:

  * AnimSequence  -> "USkeleton missing, cannot initialize RigHierarchy"
  * AnimMontage   -> the factory returns None with neither skeleton nor source
  * AnimBlueprint -> the template (null-skeleton) escape hatch is not exposed
                     to Python at all (no `b_template` property)

So on the stock rig, any submission that produced the assets AT ALL would pass
every anchor check: three dead gates over 43% of the score. The substrate
therefore ships its own ``SK_TaskRig``, and the anchor checks compare against
THAT path. The cheapest gaming route — duplicate the shipped Mannequin
animations instead of authoring — then lands on
``/Game/Characters/Mannequins/Meshes/SK_Mannequin``, the WRONG rig, and fails
checks 4-6. Proven live on both sides: the reference grades 7/7 from disk in a
fresh editor, and a duplicated stock clip reports the Mannequin anchor.

WHAT IS DELIBERATELY NOT GRADED, and why (all four established by spike, not
by argument — a check whose failing state is unreachable is worse than no check):

  * COMPILE STATUS. ``UBlueprint::Status`` is a *transient* UPROPERTY, so the
    grader would read what its own load produced, never what the agent shipped
    — and ``AnimBlueprintFactory`` compiles at creation, so every census probe
    returned ``BS_UP_TO_DATE`` including a child of a shipped ABP. Unreachable
    failing state.
  * CLIP DURATION / RETIME. ``AnimSequence`` exposes no ``get_controller`` to
    Python (``IAnimationDataController`` is not a UFUNCTION), and a
    factory-fresh clip is 1 frame / 0.0333 s. A duration gate would be
    unwinnable, so the prompt does not ask for one.
  * ANIMGRAPH CONTENT. Authoring graph nodes needs a route stock Python does
    not have; the prompt therefore never asks the AnimBlueprint to *play*
    anything, only to be anchored.
  * A SKELETON AUTHORED FROM SCRATCH. ``SkeletonFactory`` has
    ``bCreateNew = false``, its ``TargetSkeletalMesh`` is reflection-denied, and
    its success path dirties the deny-listed ``Content/Characters/``. Out of
    reach and out of scope; the rig is shipped, not requested.

A KNOWN CRASH SURFACE, disclosed rather than defended against (see notes.md).
``AnimMontageFactory`` carries an unguarded
``check(TargetSkeleton == NULL || TargetSkeleton == SourceSkeleton)`` — engine
code, and the repo is engine-pinned. An agent that sets BOTH a target rig and a
source clip anchored to a DIFFERENT rig kills the editor outright: no exception,
nothing saved, and the run records EDITOR-GONE (non-graded). The safe route —
the one the reference takes — is to set ONLY ``source_animation`` and let the
anchor be derived. Nothing here can prevent that crash; the harness now captures
its evidence (``aura_rig/crash_evidence.py``) so it is diagnosable in one read.

READ ROUTES, and one that was rejected on evidence. Anchors are read as object
properties (``skeleton`` / ``target_skeleton``); the montage->clip link uses
``get_first_anim_reference`` with a reflection-chain fallback.
``AssetRegistry.get_dependencies`` is NOT used: the spike found it works on a
shipped montage but raises ``TypeError`` on one created in the same session, and
a route that behaves differently at authoring time than at grade time is exactly
how a false FAIL gets manufactured.
"""
import json
import sys

try:
    import unreal
except ImportError:  # graded outside an editor: emit a real 0/N, never a crash
    unreal = None

TASK_ID = "kp-motion-set-shares-one-rig"
DIR = "/Game/Tasks/" + TASK_ID

RIG = DIR + "/SK_TaskRig"
CLIP = DIR + "/A_TaskMotion"
MONTAGE = DIR + "/AM_TaskAction"
ANIMBP = DIR + "/ABP_TaskLogic"

START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"

# CONSTANT denominator: this exact tuple is emitted on every leg, including the
# untouched baseline (a genuine 0/7) and a no-`unreal` import. A submission
# cannot improve its reported tests_passed/tests_run by making checks
# unreachable.
CHECK_IDS = (
    "clip_present",
    "montage_present",
    "animbp_present",
    "clip_uses_task_rig",
    "montage_uses_task_rig",
    "animbp_uses_task_rig",
    "montage_plays_the_clip",
)

# Verifier-side probe failures. NONE of these appears in any MATRIX row, so a
# broken probe can never be credited as a variant's named failure.
UNCREDITED_TOKENS = (
    "MOTIONSET_NO_UNREAL",
    "MOTIONSET_LOAD_ERROR",
    "MOTIONSET_CLASS_READ_ERROR",
    "MOTIONSET_ANCHOR_READ_ERROR",
    "MOTIONSET_LINK_READ_ERROR",
)

_MARKER_BITS = ("CRAFTBENCH-INTROSPECT-JSON", "CRAFTBENCH-ASSET-INTEGRITY-JSON")


def _defang(text, cap=300):
    """Neutralize agent-controlled text before it enters the verdict block.

    Asset paths and class names are chosen by the SUBMISSION. The layer parser
    is end-of-line anchored, so an embedded marker can no longer truncate the
    block — but a capped, quiet detail beats a 50 KB one regardless, and
    defence-in-depth here costs one function.
    """
    s = str(text)
    for bit in _MARKER_BITS:
        s = s.replace(bit, "~redacted~")
    s = " ".join(s.split())
    return s[:cap]


def check(cid, passed, detail):
    return {"id": cid, "passed": bool(passed), "detail": _defang(detail)}


def _load(path):
    """(asset, error_token). A raise is UNCREDITED; a None asset is graded."""
    try:
        return unreal.EditorAssetLibrary.load_asset(path), None
    except Exception as e:  # noqa: BLE001
        return None, "MOTIONSET_LOAD_ERROR path=%s raised=%r" % (path, e)


def _class_name(asset):
    try:
        return asset.get_class().get_name(), None
    except Exception as e:  # noqa: BLE001
        return None, "MOTIONSET_CLASS_READ_ERROR raised=%r" % (e,)


def _anchor(asset):
    """The rig package an animation asset is anchored to, or (None, token).

    ``skeleton`` covers AnimSequence/AnimMontage, ``target_skeleton`` the
    AnimBlueprint. Both are single object references, so "anchored to exactly
    one rig" is a property of the type, not something a check has to enforce.
    """
    last = None
    for prop in ("skeleton", "target_skeleton"):
        try:
            rig = asset.get_editor_property(prop)
        except Exception as e:  # noqa: BLE001
            last = "MOTIONSET_ANCHOR_READ_ERROR prop=%s raised=%r" % (prop, e)
            continue
        if rig is not None:
            try:
                return rig.get_path_name().split(".")[0], None
            except Exception as e:  # noqa: BLE001
                return None, "MOTIONSET_ANCHOR_READ_ERROR raised=%r" % (e,)
    return None, last


def _played_clip(montage):
    """The clip a montage plays, via two independent routes.

    ``get_first_anim_reference`` returning None is a SUCCESSFUL call meaning
    "no segment", not an unavailable route — so it must not fall through to the
    fallback as though the API were missing. Conflating those is how a real
    "empty montage" FAIL turns into an uncredited probe error.
    """
    try:
        ref = montage.get_first_anim_reference()
    except Exception:  # noqa: BLE001 - route unavailable: try the fallback
        ref = "<unavailable>"
    if ref is None:
        return None, None                      # answered: nothing to play
    if ref != "<unavailable>":
        try:
            return ref.get_path_name().split(".")[0], None
        except Exception as e:  # noqa: BLE001
            return None, "MOTIONSET_LINK_READ_ERROR raised=%r" % (e,)
    try:
        for track in montage.get_editor_property("slot_anim_tracks") or []:
            seg = (track.get_editor_property("anim_track")
                   .get_editor_property("anim_segments") or [])
            if seg:
                a = seg[0].get_editor_property("anim_reference")
                if a is not None:
                    return a.get_path_name().split(".")[0], None
        return None, None
    except Exception as e:  # noqa: BLE001
        return None, "MOTIONSET_LINK_READ_ERROR fallback raised=%r" % (e,)


def _grade():
    results = {}

    assets = {}
    for cid, path, want in (("clip_present", CLIP, "AnimSequence"),
                            ("montage_present", MONTAGE, "AnimMontage"),
                            ("animbp_present", ANIMBP, "AnimBlueprint")):
        asset, err = _load(path)
        if err:
            results[cid] = check(cid, False, err)
            continue
        if asset is None:
            results[cid] = check(cid, False, "MOTIONSET_ASSET_ABSENT path=%s" % path)
            continue
        cls, cerr = _class_name(asset)
        if cerr:
            results[cid] = check(cid, False, cerr)
            continue
        if cls != want:
            results[cid] = check(
                cid, False,
                "MOTIONSET_WRONG_CLASS path=%s expected=%s got=%s" % (path, want, cls))
            continue
        assets[cid] = asset
        results[cid] = check(cid, True, "MOTIONSET_ASSET_OK %s" % path)

    for cid, src in (("clip_uses_task_rig", "clip_present"),
                     ("montage_uses_task_rig", "montage_present"),
                     ("animbp_uses_task_rig", "animbp_present")):
        asset = assets.get(src)
        if asset is None:
            results[cid] = check(
                cid, False, "MOTIONSET_ANCHOR_UNCHECKABLE its asset is missing")
            continue
        got, err = _anchor(asset)
        if err:
            results[cid] = check(cid, False, err)
            continue
        results[cid] = check(
            cid, got == RIG,
            "MOTIONSET_ANCHOR_OK %s" % RIG if got == RIG
            else "MOTIONSET_WRONG_RIG expected=%s got=%s" % (RIG, got))

    montage = assets.get("montage_present")
    if montage is None:
        results["montage_plays_the_clip"] = check(
            "montage_plays_the_clip", False, "MOTIONSET_LINK_UNCHECKABLE montage missing")
    else:
        played, err = _played_clip(montage)
        if err:
            results["montage_plays_the_clip"] = check("montage_plays_the_clip", False, err)
        else:
            results["montage_plays_the_clip"] = check(
                "montage_plays_the_clip", played == CLIP,
                "MOTIONSET_LINK_OK %s" % CLIP if played == CLIP
                else "MOTIONSET_LINK_WRONG expected=%s got=%s" % (CLIP, played))

    return results


def main():
    if unreal is None:
        checks = [check(cid, False, "MOTIONSET_NO_UNREAL editor python unavailable")
                  for cid in CHECK_IDS]
    else:
        try:
            results = _grade()
        except Exception as e:  # noqa: BLE001
            results = {}
            sys.stderr.write("motion-set grader raised: %r\n" % (e,))
        checks = [results.get(cid)
                  or check(cid, False, "MOTIONSET_CHECK_UNREACHED %s" % cid)
                  for cid in CHECK_IDS]

    block = json.dumps({"checks": checks})
    print(START)
    print(block)
    print(END)
    sys.stdout.flush()
    if unreal is not None:
        try:
            unreal.log(START)
            unreal.log(block)
            unreal.log(END)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
