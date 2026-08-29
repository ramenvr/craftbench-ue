"""Fresh-process readback of the empty designated-scout Blueprint."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walkable_ground_final_common import (  # noqa: E402
    FINAL_ASSET, final_vector, immutable_vector,
)

SUCCESS = (
    "PASS baseline_empty=1 class_exact=1 compile_exact=1 component_count=0 "
    "graph_nodes=0 visible=1")


def fail(message):
    unreal.log_error("WALKABLE-GROUND-BASELINE-ASSET-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main():
    before = {"final": final_vector(), "immutable": immutable_vector()}
    blueprint = unreal.EditorAssetLibrary.load_asset(FINAL_ASSET)
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    if blueprint is None or helper is None:
        fail("Blueprint/helper unavailable")
    detail = helper.inspect_designated_scout_blueprint_shell(blueprint)
    if type(detail) is not str or detail != SUCCESS:
        fail("native shell contract mismatch expected=%r actual=%r" %
             (SUCCESS, detail))
    after = {"final": final_vector(), "immutable": immutable_vector()}
    if after != before:
        fail("readback changed protected artifacts")
    marker = ("WALKABLE-GROUND-BASELINE-ASSET-READBACK-PASS assets=1 "
              "baseline_empty=1 component_count=0 graph_nodes=0 visible=1 "
              "hashes_unchanged=1")
    unreal.log(marker)
    print(marker, flush=True)


main()
