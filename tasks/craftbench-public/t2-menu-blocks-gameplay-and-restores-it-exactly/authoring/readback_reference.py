"""Fresh-process, read-only four-gate readback of the live reference WBP."""
import json
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_contract import immutable_vector, snapshot


EXPECTED_HASH_ENV = "CRAFTBENCH_MENU_INPUT_REFERENCE_SHA256"
CHECK_IDS = (
    "menu_is_real_activatable_screen",
    "activation_adds_only_current_world_context",
    "deactivation_removes_captured_context_without_global_clear",
    "menu_declares_ui_routing_config",
)


def fail(message):
    rendered = "MENU-INPUT-REFERENCE-COLD-READBACK-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def main():
    expected_hash = os.environ.get(EXPECTED_HASH_ENV, "").strip().lower()
    if len(expected_hash) != 64 or any(
            character not in "0123456789abcdef" for character in expected_hash):
        fail("missing or malformed %s" % EXPECTED_HASH_ENV)
    before = snapshot(expected_menu_hash=expected_hash)

    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    inspect = getattr(helper, "inspect_submission_asset", None) \
        if helper is not None else None
    if inspect is None:
        fail("compiled verifier-owned introspection helper is unavailable")
    try:
        observed = json.loads(str(inspect()))
    except Exception as exc:  # noqa: BLE001
        fail("L2I JSON unreadable: %r" % exc)
    if not isinstance(observed, dict):
        fail("L2I JSON root is not an object")
    failed = [check_id for check_id in CHECK_IDS
              if not bool(observed.get(check_id, {}).get("passed", False))]
    if failed:
        fail("fixed L2I gate vector failed: %s raw=%s" %
             (failed, json.dumps(observed, sort_keys=True)))

    after = snapshot(expected_menu_hash=expected_hash)
    if after["menu"] != before["menu"] or \
            immutable_vector(after) != immutable_vector(before):
        fail("read-only reference inspection changed a protected package")
    marker = (
        "MENU-INPUT-REFERENCE-COLD-READBACK-PASS l2i=4 graph_exact=1 "
        "map_files=72 support=9 stock=4 hashes_unchanged=1 no_reparse=1 "
        "reference_sha256=%s" % expected_hash)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
