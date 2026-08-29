"""Fixed L2I grader for t2-menu-blocks-gameplay-and-restores-it-exactly.

Runtime action routing and exact context restoration are graded by the L2
fixture. This fixed-denominator script asks the verifier-owned editor helper to
inspect only the exact submitted Widget Blueprint's saved parent and graphs.
"""
import json

try:
    import unreal
except ImportError:  # offline parser/static checks
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
CHECK_IDS = (
    "menu_is_real_activatable_screen",
    "activation_adds_only_current_world_context",
    "deactivation_removes_captured_context_without_global_clear",
    "menu_declares_ui_routing_config",
)


def _defang(value, limit=360):
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.replace(START, "<START>").replace(END, "<END>")[:limit]


def _check(cid, passed, detail):
    return {"id": cid, "passed": bool(passed), "detail": _defang(detail)}


def _emit(results):
    checks = [results.get(cid, _check(cid, False, "grader did not set result"))
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

    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    inspect = getattr(helper, "inspect_submission_asset", None) \
        if helper is not None else None
    if inspect is None:
        for cid in CHECK_IDS:
            results[cid] = _check(cid, False, "verifier helper unavailable")
        _emit(results)
        return

    try:
        raw = str(inspect())
        observed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        for cid in CHECK_IDS:
            results[cid] = _check(cid, False, "helper readback failed: %r" % exc)
        _emit(results)
        return

    for cid in CHECK_IDS:
        item = observed.get(cid, {}) if isinstance(observed, dict) else {}
        results[cid] = _check(
            cid, bool(item.get("passed", False)), item.get("detail", "missing helper result"))
    _emit(results)


if __name__ == "__main__":
    main()
