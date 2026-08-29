"""Author the reference graphs into the exact live baseline assets."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-REFERENCE-AUTHOR-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    contract.require_reference_absent()
    before = contract.asset_vector()
    if not unreal.LocalPlayerModalAssetAuthoring.validate_baseline_assets():
        fail("entry assets are not the exact empty baseline")
    if not unreal.LocalPlayerModalAssetAuthoring.build_reference_graphs():
        fail("native reference graph author failed")
    parsed = json.loads(
        unreal.LocalPlayerModalAssetAuthoring.inspect_submission_assets())
    if set(parsed) != {
            "exact_two_player_owned_roots_and_stack_return",
            "owning_player_modal_lifecycle_and_focus_return",
            "exact_asset_inventory_without_global_substitute"} or not all(
                item.get("passed") is True for item in parsed.values()):
        fail("reference inspection did not pass exact three gates: %r" % parsed)
    after = contract.asset_vector()
    if after == before:
        fail("reference author did not change either asset vector")
    marker = (
        "LOCAL-PLAYER-MODAL-REFERENCE-AUTHOR-PASS assets=2 l2i=3 "
        "root_graph=1 lifecycle=3 focus=1 input_config=1")
    unreal.log(marker)
    print(marker)


main()
