"""Author the exact reference graph into the frozen live baseline WBP.

This UE Python step is never run directly. ``close_reference.py`` first parks
the baseline bytes, owns the outer watchdog, and restores on every failure.
"""
import json
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_contract import (
    BASELINE_SHA256,
    immutable_vector,
    sha256,
    snapshot,
    MENU_FILE,
)


def fail(message):
    rendered = "MENU-INPUT-REFERENCE-AUTHOR-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def main():
    before = snapshot(expected_menu_hash=BASELINE_SHA256)
    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    build = getattr(helper, "build_reference_menu_graph", None) \
        if helper is not None else None
    inspect = getattr(helper, "inspect_submission_asset", None) \
        if helper is not None else None
    if build is None or inspect is None:
        fail("compiled verifier-owned reference helper is unavailable")
    if not bool(build()):
        fail("BuildReferenceMenuGraph returned false")

    reference_hash = sha256(MENU_FILE)
    if reference_hash == BASELINE_SHA256:
        fail("authored reference is byte-identical to baseline")
    after = snapshot(expected_menu_hash=reference_hash)
    if immutable_vector(after) != immutable_vector(before):
        fail("reference author changed protected map/support/stock packages")

    try:
        checks = json.loads(str(inspect()))
    except Exception as exc:  # noqa: BLE001
        fail("reference inspection JSON unreadable: %r" % exc)
    required = (
        "menu_is_real_activatable_screen",
        "activation_adds_only_current_world_context",
        "deactivation_removes_captured_context_without_global_clear",
        "menu_declares_ui_routing_config",
    )
    failed = [name for name in required
              if not bool(checks.get(name, {}).get("passed", False))]
    if failed:
        fail("reference L2I vector failed: %s" % failed)

    marker = (
        "MENU-INPUT-REFERENCE-AUTHOR-PASS graph=activation,deactivation,config "
        "l2i=4 map_files=72 support=9 stock=4 hashes_unchanged=1 "
        "reference_sha256=%s" % reference_hash)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
