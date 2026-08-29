"""Author the complete graph at its exact final package path."""

from pathlib import Path
import sys

import unreal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reference_contract as contract  # noqa: E402
from guard_aim_common import FINAL_ANIM, FINAL_DIR, sha256  # noqa: E402


MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
LOCOMOTION = "/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run"
AIM_OFFSET = "/Game/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle"


def fail(message: str) -> None:
    rendered = "GUARD-AIM-REFERENCE-AUTHOR-FAILED " + message
    unreal.log_error(rendered)
    raise RuntimeError(message)


def main() -> None:
    contract.require_reference_absent()
    if contract.FINAL_DISK_DIR.exists():
        fail("live final namespace must be absent")
    immutable = contract.immutable_vector()
    mesh = unreal.EditorAssetLibrary.load_asset(MESH)
    locomotion = unreal.EditorAssetLibrary.load_asset(LOCOMOTION)
    aim_offset = unreal.EditorAssetLibrary.load_asset(AIM_OFFSET)
    parent = unreal.load_class(
        None, "/Script/ThirdPerson.GuardVisibleAimAnimInstance")
    helper = getattr(unreal, "GuardVisibleAimAssetAuthoring", None)
    verifier = getattr(unreal, "GuardVisibleAimVerifierLibrary", None)
    if any(value is None for value in
           (mesh, locomotion, aim_offset, parent, helper, verifier)):
        fail("stock dependency or native helper missing")
    factory = unreal.AnimBlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    factory.set_editor_property("target_skeleton",
                                mesh.get_editor_property("skeleton"))
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        FINAL_ANIM.rsplit("/", 1)[-1], FINAL_DIR,
        unreal.AnimBlueprint, factory)
    if asset is None:
        fail("AnimBlueprintFactory returned None")
    detail = str(helper.build_anim_graph(asset, True))
    if not detail.startswith("PASS ") or '"probe_ok":true' not in detail:
        fail("complete graph author failed: " + detail)
    if not unreal.EditorAssetLibrary.save_asset(
            FINAL_ANIM, only_if_is_dirty=False):
        fail("save failed")
    vector = contract.exact_live_vector()
    readback = str(verifier.inspect_anim_blueprint(asset, True))
    if '"probe_ok":true' not in readback or '"expect_aim":true' not in readback:
        fail("same-process complete readback failed: " + readback)
    if contract.immutable_vector() != immutable:
        fail("protected asset/map bytes changed")
    marker = (
        "GUARD-AIM-REFERENCE-AUTHOR-PASS assets=1 complete=1 sha256=%s "
        "readback=%s" % (sha256(contract.FINAL_ASSET), readback))
    unreal.log(marker)
    print(marker, flush=True)


main()
