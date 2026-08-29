"""Fixed three-check structural grader for the replicated Door Blueprint."""

import json
import os

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-every-player-sees-the-same-door-state"
ASSET = f"/Game/Tasks/{TASK_ID}/BP_ReplicatedDoorState"
EXPECTED_FILE = (
    f"Content/Tasks/{TASK_ID}/BP_ReplicatedDoorState.uasset"
)
EXPECTED_VECTOR = (
    "PASS DOOR_BLUEPRINT mode=final solved=1 parent=direct variable=1 "
    "rpc=server_reliable repnotify=1 nodes=5 onrep_graph=1"
)
CHECK_IDS = (
    "ClientRequestUsesServerRPC",
    "DoorStateReplicatesThroughNotify",
    "SubmissionHasNoEphemeralReplicationSubstitute",
)


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>")
                     .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def main():
    results = {}
    if unreal is None:
        results = {item: check(item, False, "DOOR_NO_UNREAL")
                   for item in CHECK_IDS}
    else:
        try:
            helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
            asset = unreal.EditorAssetLibrary.load_asset(ASSET)
            detail = helper.inspect_door_blueprint(False, True) \
                if helper is not None else None
            manifest = json.loads(os.environ.get(
                "CRAFTBENCH_SUBMITTED_FILES_JSON", "[]"))
            normalized = sorted(str(item).replace("\\", "/")
                                for item in manifest) \
                if isinstance(manifest, list) else []
            vector_ok = type(detail) is str and detail == EXPECTED_VECTOR
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], vector_ok and "rpc=server_reliable" in detail,
                "DOOR_RPC asset=%d vector=%r" % (asset is not None, detail))
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], vector_ok and "repnotify=1" in detail
                and "onrep_graph=1" in detail,
                "DOOR_REPNOTIFY vector=%r" % detail)
            boundary_ok = asset is not None and normalized == [EXPECTED_FILE]
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], boundary_ok,
                "DOOR_BOUNDARY files=%r exact_asset=%d" %
                (normalized, asset is not None))
        except Exception as exc:
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "DOOR_READ_ERROR %r" % exc)
    payload = json.dumps(
        {"checks": [results[item] for item in CHECK_IDS]},
        separators=(",", ":"), ensure_ascii=True)
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
