"""Author the complete four-asset reference inside a disposable substrate."""

from __future__ import annotations

import unreal


TASK_ID = "t3-alert-state-swaps-the-upper-body-without-breaking-stride"
ROOT = "/Game/Tasks/" + TASK_ID
INTERFACE = "/Game/Maps/" + TASK_ID + "/ALI_AlertStrideUpperBody"
NAMES = (
    "ABP_AlertStrideHost",
    "ABP_AlertStrideCalmLayer",
    "ABP_AlertStrideAlertLayer",
    "ST_AlertStride",
)


def fail(message: str) -> None:
    rendered = "ALERT-STRIDE-REFERENCE-AUTHOR-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def unpack(value) -> tuple[bool, str]:
    if isinstance(value, tuple) and len(value) == 2:
        return bool(value[0]), str(value[1])
    if isinstance(value, str):
        return value.startswith("PASS "), value
    return bool(value), str(value)


def main() -> None:
    expected = {ROOT + "/" + name for name in NAMES}
    observed = {str(value).split(".", 1)[0]
                for value in unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed:
        fail("editable namespace must be absent: %r" % sorted(observed))
    if not unreal.EditorAssetLibrary.does_asset_exist(INTERFACE):
        fail("read-only interface is absent: " + INTERFACE)
    helper = getattr(unreal, "AlertStrideAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper unavailable")
    passed, detail = unpack(helper.author_asset_set(ROOT, INTERFACE, True))
    after = {str(value).split(".", 1)[0]
             for value in unreal.EditorAssetLibrary.list_assets(
                 ROOT, recursive=True, include_folder=False)}
    if not passed or not detail.startswith("PASS ALERT_STRIDE_ASSETS mode=complete"):
        fail("native complete author failed: " + detail)
    if after != expected:
        fail("exact four-asset inventory mismatch expected=%r actual=%r" %
             (sorted(expected), sorted(after)))
    facts = str(unreal.AlertStrideVerifierLibrary.inspect_asset_set(
        ROOT, INTERFACE, True))
    if '"probe_ok":true' not in facts:
        fail("same-process complete readback failed: " + facts)
    marker = (
        "ALERT-STRIDE-REFERENCE-AUTHOR-PASS editable=4 interface_reused=1 "
        "complete=1 facts=" + facts)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
