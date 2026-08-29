"""Create exactly one isolated Guard Aim AnimBlueprint."""

from __future__ import annotations

import json
from pathlib import Path
import unreal

from guard_aim_common import (
    ADMISSION_ANIM, ADMISSION_DIR, ADMISSION_MAP, FINAL_ANIM, FINAL_DIR,
    FINAL_MAP, REFERENCE, disk, sha256, signature, snapshot,
)


MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
LOCOMOTION = "/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run"
AIM_OFFSET = "/Game/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle"


def fail(message: str):
    unreal.log_error("GUARD-AIM-ASSETS-FAILED: " + message)
    raise RuntimeError(message)


def author(mode: str):
    if mode not in ("admission", "final"):
        fail("unsupported mode=" + mode)
    output = ADMISSION_ANIM if mode == "admission" else FINAL_ANIM
    directory = ADMISSION_DIR if mode == "admission" else FINAL_DIR
    output_file = disk(output, ".uasset")
    protected = {
        "other_asset": disk(FINAL_ANIM if mode == "admission" else ADMISSION_ANIM,
                            ".uasset"),
        "final_map": disk(FINAL_MAP, ".umap"),
        "admission_map": disk(ADMISSION_MAP, ".umap"),
        "reference": REFERENCE,
    }
    before = {name: snapshot(path) for name, path in protected.items()}
    listed = {str(value).split(".", 1)[0]
              for value in unreal.EditorAssetLibrary.list_assets(
                  directory, recursive=True, include_folder=False)}
    if listed or output_file.exists() or output_file.is_symlink():
        fail("refusing non-empty output namespace: %s" % sorted(listed))
    mesh = unreal.EditorAssetLibrary.load_asset(MESH)
    locomotion = unreal.EditorAssetLibrary.load_asset(LOCOMOTION)
    aim_offset = unreal.EditorAssetLibrary.load_asset(AIM_OFFSET)
    parent = unreal.load_class(
        None, "/Script/ThirdPerson.GuardVisibleAimAnimInstance")
    helper = getattr(unreal, "GuardVisibleAimAssetAuthoring", None)
    if any(value is None for value in
           (mesh, locomotion, aim_offset, parent, helper)):
        fail("stock dependency, runtime parent, or verifier helper missing")
    factory = unreal.AnimBlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    factory.set_editor_property("target_skeleton",
                                mesh.get_editor_property("skeleton"))
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        output.rsplit("/", 1)[-1], directory, unreal.AnimBlueprint, factory)
    if asset is None:
        fail("AnimBlueprintFactory returned None")
    complete = mode == "admission"
    readback = str(helper.build_anim_graph(asset, complete))
    if not readback.startswith("PASS "):
        fail("graph author/readback failed: " + readback)
    if not unreal.EditorAssetLibrary.save_asset(output, only_if_is_dirty=False):
        fail("save failed: " + output)
    observed = {str(value).split(".", 1)[0]
                for value in unreal.EditorAssetLibrary.list_assets(
                    directory, recursive=True, include_folder=False)}
    if observed != {output} or not output_file.is_file():
        fail("exact output mismatch: %s" % sorted(observed))
    after = {name: snapshot(path) for name, path in protected.items()}
    if after != before:
        fail("protected assets/maps/reference changed")
    unreal.log("GUARD-AIM-ASSETS-SAVED mode=%s outputs=1 complete=%d "
               "sha256=%s protected=%s readback=%s" %
               (mode, int(complete), sha256(output_file), signature(after),
                readback))
