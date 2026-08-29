"""Create one isolated five-asset Alert Stride set without overwrites."""

from __future__ import annotations

import unreal

from alert_stride_common import (
    ADMISSION_INTERFACE, ADMISSION_MAP, ADMISSION_ROOT, FINAL_INTERFACE,
    FINAL_MAP, FINAL_ROOT, REFERENCE, all_packages, disk, sha256, signature,
    snapshot,
)


def fail(message: str):
    unreal.log_error("ALERT-STRIDE-ASSETS-FAILED: " + message)
    raise RuntimeError(message)


def unpack(value):
    if isinstance(value, tuple) and len(value) == 2:
        return bool(value[0]), str(value[1])
    return bool(value), str(value)


def author(mode: str):
    if mode not in ("admission", "final"):
        fail("unsupported mode=" + mode)
    root = ADMISSION_ROOT if mode == "admission" else FINAL_ROOT
    interface = ADMISSION_INTERFACE if mode == "admission" else FINAL_INTERFACE
    complete = mode == "admission"
    expected = set(all_packages(root, interface))
    output_files = [disk(value, ".uasset") for value in expected]
    protected = {
        "other_assets": disk(FINAL_ROOT if complete else ADMISSION_ROOT, ""),
        "other_interface": disk(
            FINAL_INTERFACE if complete else ADMISSION_INTERFACE, ".uasset"),
        "final_map": disk(FINAL_MAP, ".umap"),
        "admission_map": disk(ADMISSION_MAP, ".umap"),
        "reference": REFERENCE,
    }
    before = {name: snapshot(path) for name, path in protected.items()}
    listed = {str(value).split(".", 1)[0]
              for value in unreal.EditorAssetLibrary.list_assets(
                  root, recursive=True, include_folder=False)}
    if listed or any(path.exists() or path.is_symlink() for path in output_files):
        fail("refusing non-empty output namespace/interface: %r" % sorted(listed))
    helper = getattr(unreal, "AlertStrideAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper missing")
    passed, detail = unpack(helper.author_asset_set(root, interface, complete))
    observed = {str(value).split(".", 1)[0]
                for value in unreal.EditorAssetLibrary.list_assets(
                    root, recursive=True, include_folder=False)}
    if unreal.EditorAssetLibrary.does_asset_exist(interface):
        observed.add(interface)
    if not passed or not detail.startswith("PASS ALERT_STRIDE_ASSETS"):
        fail("native author failed: " + detail)
    if observed != expected or not all(path.is_file() for path in output_files):
        fail("exact inventory mismatch expected=%r observed=%r" %
             (sorted(expected), sorted(observed)))
    after = {name: snapshot(path) for name, path in protected.items()}
    if after != before:
        fail("protected task bytes changed")
    hashes = {path.name: sha256(path) for path in output_files}
    unreal.log("ALERT-STRIDE-ASSETS-SAVED mode=%s packages=5 editable=4 complete=%d "
               "hashes=%s protected=%s detail=%s" %
               (mode, int(complete), signature(hashes), signature(after),
                detail))
