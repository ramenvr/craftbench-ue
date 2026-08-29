"""Fixed three-check L2I grader for per-local-player modal ownership."""

import json

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
CHECK_IDS = (
    "exact_two_player_owned_roots_and_stack_return",
    "owning_player_modal_lifecycle_and_focus_return",
    "exact_asset_inventory_without_global_substitute",
)


def _check(check_id, passed, detail):
    text = str(detail).replace("\r", " ").replace("\n", " ")
    return {"id": check_id, "passed": bool(passed), "detail": text[:420]}


def _emit(results):
    checks = [results.get(cid, _check(cid, False, "missing result"))
              for cid in CHECK_IDS]
    payload = json.dumps({"checks": checks}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


def main():
    results = {}
    if unreal is None:
        for cid in CHECK_IDS:
            results[cid] = _check(cid, False, "unreal module unavailable")
        _emit(results)
        return
    helper = getattr(unreal, "LocalPlayerModalAssetAuthoring", None)
    inspect = getattr(helper, "inspect_submission_assets", None) \
        if helper is not None else None
    if inspect is None:
        for cid in CHECK_IDS:
            results[cid] = _check(cid, False, "fixed verifier helper unavailable")
        _emit(results)
        return
    try:
        observed = json.loads(str(inspect()))
    except Exception as exc:  # noqa: BLE001
        observed = {}
        for cid in CHECK_IDS:
            results[cid] = _check(cid, False, "helper failed: %r" % exc)
        _emit(results)
        return
    for cid in CHECK_IDS:
        item = observed.get(cid, {}) if isinstance(observed, dict) else {}
        results[cid] = _check(
            cid, item.get("passed") is True,
            item.get("evidence", "helper omitted evidence"))
    _emit(results)


if __name__ == "__main__":
    main()
