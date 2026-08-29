"""Headless editor-Python: flush every DIRTY package to disk.

Agent sub-agents (Aura's bp_agent / material_agent / etc.) author Blueprints
and other ``.uasset``s by mutating in-memory packages. Those edits live ONLY in
the editor's transient package set until something saves them — a graded run
that snapshots ``Content/`` off disk right after the agent finishes would miss
every unsaved Blueprint. This script forces them to disk so the deliverable
capture sees real ``.uasset`` files.

Run headless by the runner via ``UnrealEditor-Cmd -ExecutePythonScript=`` (the
same channel as the L2-introspect scripts and the map scaffolder). It prints a
verdict block in the L2-introspect format so the caller can confirm the save ran
(the runner only needs the terminal marker; the JSON is for the log + tests).

Anti-circularity: stock UE Python only (``unreal.EditorAssetLibrary`` /
``unreal.EditorLoadingAndSavingUtils``), never Aura's MCP tools.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

SAVE_JSON_START = "CRAFTBENCH-SAVE-DIRTY-JSON-START"
SAVE_JSON_END = "CRAFTBENCH-SAVE-DIRTY-JSON-END"


def emit(payload):
    body = json.dumps(payload)
    print(SAVE_JSON_START)
    print(body)
    print(SAVE_JSON_END)
    if unreal is not None:
        unreal.log(SAVE_JSON_START)
        unreal.log(body)
        unreal.log(SAVE_JSON_END)


def main():
    result = {"saved": False, "dirty_before": None, "detail": ""}

    # Enumerate dirty packages first (best-effort; informational only).
    try:
        dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        result["dirty_before"] = [str(p) for p in dirty]
    except Exception as e:  # noqa: BLE001 — informational only, never fatal
        result["dirty_before"] = None
        result["detail"] = "get_dirty_content_packages failed: %r" % (e,)

    # Persist every dirty package. ``save_all_dirty`` (no-prompt, all-content)
    # is the stock route; fall back to ``EditorAssetLibrary.save_all`` if it is
    # unavailable on this engine build.
    try:
        # only_dirty=True, save_map_packages excluded — we never want to rewrite
        # the verifier-owned task maps under Content/Maps (denied downstream too).
        ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
            save_map_packages=False, save_content_packages=True
        )
        result["saved"] = bool(ok)
        result["detail"] = (result["detail"] + " save_dirty_packages -> %s" % ok).strip()
    except Exception as e:  # noqa: BLE001
        try:
            ok = unreal.EditorAssetLibrary.save_all_dirty()
            result["saved"] = bool(ok)
            result["detail"] = (
                result["detail"] + " fallback save_all_dirty -> %s" % ok
            ).strip()
        except Exception as e2:  # noqa: BLE001
            result["detail"] = (
                result["detail"]
                + " save_dirty_packages err=%r; save_all_dirty err=%r" % (e, e2)
            ).strip()

    emit(result)


if __name__ == "__main__":
    if unreal is None:
        # Offline format check: emit a deterministic 'no-engine' block so the
        # terminal marker is present (the runner invokes this inside
        # UnrealEditor-Cmd; offline it must not raise).
        emit({"saved": False, "dirty_before": None,
              "detail": "unreal module not importable (offline)"})
    else:
        main()
