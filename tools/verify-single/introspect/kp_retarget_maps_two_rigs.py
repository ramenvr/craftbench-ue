"""L2I grader — kp-retarget-maps-two-rigs.

Grades an animation-retargeting pipeline built from scratch: two rig
definitions, each describing a different character's skeleton with a retarget
root and two named chains, plus a retargeter that references both and whose
chain mapping actually resolves.

WHY THIS TASK NEEDS NO SUBSTRATE BASELINE, unlike its sibling. R26 had to ship a
task-owned skeleton because the engine refuses to create its assets unanchored,
which would have made three anchor checks dead. Here the situation is the
opposite and better: ThirdPerson ships NO IKRigDefinition and NO IKRetargeter at
all (`git ls-files` over the substrate content: zero), so there is nothing for a
lazy submission to duplicate and every check below is live against an empty
start. The two skeletal meshes the rigs describe are stock, read-only template
content.

THE READ ROUTES, and the two this deliberately does NOT use — each settled by a
live spike on 2026-08-14, not by reading docs:

  * CHAIN MAPPING -> `get_source_chain(TargetChainName)`. This is the surviving
    per-chain accessor and it answers correctly.
  * NOT `get_all_chain_settings()`. UE 5.8 defines URetargetChainSettings in
    IKRetargetDeprecated.h with SourceChain/TargetChain marked
    DeprecatedProperty, and it returns EMPTY on 5.8.1 regardless of state. A
    grader built on it would report every submission as having no mappings --
    including a perfect one.
  * NOT `get_chain_mapping()`. FRetargetChainMapping exists in C++ and is not
    exposed to Python at all.
  * RIG REFERENCES -> the `source_ik_rig_asset` / `target_ik_rig_asset` object
    properties, which read back as full paths.

THE GATE THE ENGINE GIVES FOR FREE. A factory-fresh IKRetargeter has ZERO ops,
and until `AddDefaultOps()` runs, assigning rigs and auto-mapping both silently
do nothing -- every chain then maps to None. So `chain_mapping_resolves` fails
for a submission that built both rigs correctly, created the retargeter, pointed
it at both, and called auto-map, but never added ops. That is a real,
agent-reachable, non-obvious failure state, and it is the discrimination R26 had
to manufacture with a task-owned rig. It cost four spike boots to find, because
three separate reads returned None and each looked like a dead API rather than
an empty op stack.
"""
import json
import sys

try:
    import unreal
except ImportError:
    unreal = None

TASK_ID = "kp-retarget-maps-two-rigs"
DIR = "/Game/Tasks/" + TASK_ID

SOURCE_RIG = DIR + "/IK_TaskSource"
TARGET_RIG = DIR + "/IK_TaskTarget"
RETARGETER = DIR + "/RTG_TaskMotion"

# Disclosed verbatim in the prompt. The BONES each chain spans are deliberately
# NOT graded (the prompt says so): the capability under test is building the
# pipeline, not choosing anatomy, and grading bone spans would be an undisclosed
# literal enforced against conforming work.
REQUIRED_CHAINS = ("Spine", "LeftArm")

START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"

# CONSTANT denominator on every leg, including an empty submission (a genuine
# 0/8) and a no-`unreal` import.
CHECK_IDS = (
    "source_rig_present",
    "target_rig_present",
    "retargeter_present",
    "source_rig_has_retarget_root",
    "target_rig_has_retarget_root",
    "both_rigs_declare_required_chains",
    "retargeter_references_both_rigs",
    "chain_mapping_resolves",
)

# Verifier-side probe failures. None appears in any MATRIX row.
UNCREDITED_TOKENS = (
    "RETARGET_NO_UNREAL",
    "RETARGET_LOAD_ERROR",
    "RETARGET_CONTROLLER_ERROR",
    "RETARGET_CHAIN_READ_ERROR",
    "RETARGET_MAPPING_READ_ERROR",
)

_MARKER_BITS = ("CRAFTBENCH-INTROSPECT-JSON", "CRAFTBENCH-ASSET-INTEGRITY-JSON")


def _defang(text, cap=300):
    s = str(text)
    for bit in _MARKER_BITS:
        s = s.replace(bit, "~redacted~")
    return " ".join(s.split())[:cap]


def check(cid, passed, detail):
    return {"id": cid, "passed": bool(passed), "detail": _defang(detail)}


def _load(path):
    try:
        return unreal.EditorAssetLibrary.load_asset(path), None
    except Exception as e:  # noqa: BLE001
        return None, "RETARGET_LOAD_ERROR path=%s raised=%r" % (path, e)


def _rig_controller(rig):
    try:
        return unreal.IKRigController.get_controller(rig), None
    except Exception as e:  # noqa: BLE001
        return None, "RETARGET_CONTROLLER_ERROR raised=%r" % (e,)


def _grade():
    results = {}
    loaded = {}

    for cid, path, want in (("source_rig_present", SOURCE_RIG, "IKRigDefinition"),
                            ("target_rig_present", TARGET_RIG, "IKRigDefinition"),
                            ("retargeter_present", RETARGETER, "IKRetargeter")):
        asset, err = _load(path)
        if err:
            results[cid] = check(cid, False, err)
            continue
        if asset is None:
            results[cid] = check(cid, False, "RETARGET_ASSET_ABSENT path=%s" % path)
            continue
        try:
            cls = asset.get_class().get_name()
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False, "RETARGET_LOAD_ERROR class raised=%r" % (e,))
            continue
        if cls != want:
            results[cid] = check(cid, False,
                                 "RETARGET_WRONG_CLASS path=%s expected=%s got=%s"
                                 % (path, want, cls))
            continue
        loaded[cid] = asset
        results[cid] = check(cid, True, "RETARGET_ASSET_OK %s" % path)

    # --- retarget roots ---------------------------------------------------
    controllers = {}
    for cid, src in (("source_rig_has_retarget_root", "source_rig_present"),
                     ("target_rig_has_retarget_root", "target_rig_present")):
        rig = loaded.get(src)
        if rig is None:
            results[cid] = check(cid, False, "RETARGET_ROOT_UNCHECKABLE its rig is missing")
            continue
        ctrl, err = _rig_controller(rig)
        if err:
            results[cid] = check(cid, False, err)
            continue
        controllers[src] = ctrl
        try:
            root = str(ctrl.get_retarget_root())
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False, "RETARGET_CHAIN_READ_ERROR root raised=%r" % (e,))
            continue
        ok = bool(root) and root not in ("None", "")
        results[cid] = check(cid, ok,
                             "RETARGET_ROOT_OK %s" % root if ok
                             else "RETARGET_ROOT_UNSET got=%s" % root)

    # --- named chains on BOTH rigs (one check, both rigs) -----------------
    cid = "both_rigs_declare_required_chains"
    missing = []
    unreadable = None
    for label, src in (("source", "source_rig_present"), ("target", "target_rig_present")):
        ctrl = controllers.get(src)
        if ctrl is None:
            missing.append("%s=<rig missing>" % label)
            continue
        try:
            names = {str(c.chain_name) for c in ctrl.get_retarget_chains()}
        except Exception as e:  # noqa: BLE001
            unreadable = "RETARGET_CHAIN_READ_ERROR %s raised=%r" % (label, e)
            break
        for want in REQUIRED_CHAINS:
            if want not in names:
                missing.append("%s:%s" % (label, want))
    if unreadable:
        results[cid] = check(cid, False, unreadable)
    else:
        results[cid] = check(cid, not missing,
                             "RETARGET_CHAINS_OK %s" % (list(REQUIRED_CHAINS),)
                             if not missing
                             else "RETARGET_CHAIN_MISSING %s" % (missing,))

    # --- the retargeter's two rig references -------------------------------
    cid = "retargeter_references_both_rigs"
    rtg = loaded.get("retargeter_present")
    if rtg is None:
        results[cid] = check(cid, False, "RETARGET_REFS_UNCHECKABLE retargeter missing")
    else:
        got = {}
        bad = None
        for prop, want in (("source_ik_rig_asset", SOURCE_RIG),
                           ("target_ik_rig_asset", TARGET_RIG)):
            try:
                ref = rtg.get_editor_property(prop)
                got[prop] = ref.get_path_name().split(".")[0] if ref is not None else None
            except Exception as e:  # noqa: BLE001
                bad = "RETARGET_MAPPING_READ_ERROR %s raised=%r" % (prop, e)
                break
        if bad:
            results[cid] = check(cid, False, bad)
        else:
            ok = (got.get("source_ik_rig_asset") == SOURCE_RIG
                  and got.get("target_ik_rig_asset") == TARGET_RIG)
            results[cid] = check(cid, ok,
                                 "RETARGET_REFS_OK" if ok
                                 else "RETARGET_REFS_WRONG source=%s target=%s"
                                      % (got.get("source_ik_rig_asset"),
                                         got.get("target_ik_rig_asset")))

    # --- THE ONE THAT CATCHES A RETARGETER WITH NO OPS ---------------------
    cid = "chain_mapping_resolves"
    if rtg is None:
        results[cid] = check(cid, False, "RETARGET_MAPPING_UNCHECKABLE retargeter missing")
    else:
        try:
            rc = unreal.IKRetargeterController.get_controller(rtg)
        except Exception as e:  # noqa: BLE001
            rc = None
            results[cid] = check(cid, False, "RETARGET_CONTROLLER_ERROR raised=%r" % (e,))
        if rc is not None:
            unresolved = []
            err = None
            for chain in REQUIRED_CHAINS:
                try:
                    mapped = str(rc.get_source_chain(chain))
                except Exception as e:  # noqa: BLE001
                    err = "RETARGET_MAPPING_READ_ERROR chain=%s raised=%r" % (chain, e)
                    break
                if not mapped or mapped in ("None", ""):
                    unresolved.append(chain)
            if err:
                results[cid] = check(cid, False, err)
            else:
                results[cid] = check(
                    cid, not unresolved,
                    "RETARGET_MAPPING_OK %s" % (list(REQUIRED_CHAINS),) if not unresolved
                    else "RETARGET_MAPPING_UNRESOLVED chains=%s" % (unresolved,))

    return results


def main():
    if unreal is None:
        checks = [check(cid, False, "RETARGET_NO_UNREAL editor python unavailable")
                  for cid in CHECK_IDS]
    else:
        try:
            results = _grade()
        except Exception as e:  # noqa: BLE001
            results = {}
            sys.stderr.write("retarget grader raised: %r\n" % (e,))
        checks = [results.get(cid) or check(cid, False,
                                            "RETARGET_CHECK_UNREACHED %s" % cid)
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
