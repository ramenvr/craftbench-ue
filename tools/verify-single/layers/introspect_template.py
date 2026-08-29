"""REFERENCE TEMPLATE — a verifier-owned L2-introspect script.

Copy this per task into the verifier-owned, hash-pinned location and adapt the
two EDIT-BELOW blocks. It runs under ``UnrealEditor-Cmd -ExecutePythonScript=``
(see ``layers/l2_introspect.py``): it loads the agent's generated asset(s) via
stock UE editor-Python and asserts STRUCTURAL facts, then prints the verdict
block the L2-introspect layer parses.

Hard rules:
- READ-ONLY introspection — never mutate the asset, the level, or anything.
- Identity by a pre-declared content path / asset tag, never by class
  (an agent may subclass; class-based lookup would penalize that).
- Emit exactly one verdict block; if it repeats, the layer takes the LAST one.
- Anti-circularity: use stock UE Python (EditorAssetLibrary / reflection /
  the MaterialEditingLibrary etc.), never Aura's MCP tools, to grade Aura.

Note: the exact reflection API per asset class (MaterialEditingLibrary,
WidgetTree walk, AnimBlueprintGeneratedClass, BlueprintGeneratedClass graph
reflection, DataTable row reads) varies by UE 5.7 surface — confirm against
the live install when authoring a real task.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # lets this file import (for syntax checks) outside the editor
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"


def check(check_id, passed, detail=""):
    return {"id": check_id, "passed": bool(passed), "detail": str(detail)}


def emit_verdict(checks):
    """Print the verdict block the L2-introspect layer parses (stdout + UE log)."""
    payload = json.dumps({"checks": checks})
    for sink in (print, (unreal.log if unreal is not None else None)):
        if sink is None:
            continue
        sink(INTROSPECT_JSON_START)
        sink(payload)
        sink(INTROSPECT_JSON_END)


def main():
    checks = []

    # --- EDIT 1: the target asset this task verifies (pre-declared path) ---
    asset_path = "/Game/Materials/M_TaskTarget"
    # ----------------------------------------------------------------------

    exists = bool(unreal.EditorAssetLibrary.does_asset_exist(asset_path))
    checks.append(check("asset_exists", exists, asset_path))
    if not exists:
        emit_verdict(checks)  # fail-safe: stop here, the layer marks this FAIL
        return

    asset = unreal.EditorAssetLibrary.load_asset(asset_path)

    # --- EDIT 2: structural assertions on `asset` -------------------------
    # Example (Material): assert a scalar parameter named "PulseSpeed" exists.
    try:
        names = [str(n) for n in
                 unreal.MaterialEditingLibrary.get_scalar_parameter_names(asset)]
        checks.append(check("has_PulseSpeed_param", "PulseSpeed" in names,
                            "scalar params: %s" % names))
    except Exception as e:  # asset wasn't a material / API mismatch
        checks.append(check("introspection_ran", False, repr(e)))
    # ----------------------------------------------------------------------

    emit_verdict(checks)


if __name__ == "__main__":
    main()
