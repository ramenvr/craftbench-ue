"""Fresh-process, read-only validation of the exact protected asset inventory."""

import hashlib
from pathlib import Path
import unreal


TASK = "t2-one-bundle-loads-without-pulling-in-the-rest"
ROOT = f"/Game/Maps/{TASK}/Records"
EXPECTED_DETAIL = "assets=15 primary=3 payload=6 hidden=6 bundles=6 exact_load_sets=6"
NAMES = tuple(
    [f"DA_BundleRecord_{stem}" for stem in ("Quartz", "Violet", "Amber")] +
    [f"DA_{stem}_{bundle}_{kind}"
     for stem in ("Quartz", "Violet", "Amber")
     for bundle in ("Quartz", "Violet")
     for kind in ("Payload", "Hidden")])


def fail(message):
    unreal.log_error("BUNDLE-LEASE-ASSET-READBACK-ERROR " + message)
    raise RuntimeError(message)


def disk_path(name):
    return Path(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir())) / "Maps" / TASK / "Records" / (name + ".uasset")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_result(result):
    if isinstance(result, str):
        return result == EXPECTED_DETAIL, result
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return bool(result[0]), str(result[1])
    fail("ValidateAuthoredAssets returned unexpected shape: %r" % (result,))


def main():
    files = [disk_path(name) for name in NAMES]
    if any(not path.is_file() for path in files) or len(set(files)) != 15:
        fail("exact 15-file inventory is incomplete")
    before = {str(path): sha(path) for path in files}
    helper = getattr(unreal, "BundleLeaseAssetAuthoring", None)
    validate = getattr(helper, "validate_authored_assets", None) if helper else None
    if not callable(validate):
        fail("native ValidateAuthoredAssets unavailable")
    valid, detail = parse_result(validate())
    if not valid or detail != EXPECTED_DETAIL:
        fail("native vector mismatch: " + detail)
    after = {str(path): sha(path) for path in files}
    if after != before:
        fail("read-only helper changed an authored package")
    unreal.log("BUNDLE-LEASE-ASSET-READBACK-PASS hashes_unchanged=15 " + detail)


main()
