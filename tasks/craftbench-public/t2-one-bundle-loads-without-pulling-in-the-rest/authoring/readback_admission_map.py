"""Fresh-process readback for admission or final map; never executes fixtures."""

import hashlib
from pathlib import Path
import sys
import unreal


TASK = "t2-one-bundle-loads-without-pulling-in-the-rest"
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()))
ASSET_DIR = CONTENT / "Maps" / TASK / "Records"
MAP_DIR = CONTENT / "Maps" / TASK
EXPECTED = {
    "admission": "map=admission scenario=1 admission_fixture=1 final_fixture=0 runtime_hosts=0 runtime_consumers=0",
    "final": "map=final scenario=1 final_fixture=1 admission_fixture=0 runtime_hosts=1 runtime_consumers=2 initial_ready=0",
}
MAP_NAMES = {"admission": "L_BundleLeaseAdmission", "final": "L_BundleLeases"}


def fail(message):
    unreal.log_error("BUNDLE-LEASE-MAP-READBACK-ERROR " + message)
    raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(result, expected):
    if isinstance(result, str):
        return result == expected, result
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return bool(result[0]), str(result[1])
    fail("native helper returned unexpected shape: %r" % (result,))


def main(mode):
    assets = sorted(ASSET_DIR.glob("*.uasset"))
    map_file = MAP_DIR / (MAP_NAMES[mode] + ".umap")
    if len(assets) != 15 or not map_file.is_file():
        fail("exact 15 assets + selected map inventory missing")
    protected = assets + [map_file]
    before = {str(path): sha(path) for path in protected}
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    package = f"/Game/Maps/{TASK}/{MAP_NAMES[mode]}"
    if not les.load_level(package):
        fail("cold load failed: " + package)
    helper = getattr(unreal, "BundleLeaseAssetAuthoring", None)
    validate_assets = getattr(helper, "validate_authored_assets", None) if helper else None
    validate = getattr(helper, "validate_current_map", None) if helper else None
    if not callable(validate_assets) or not callable(validate):
        fail("native asset/map validation helpers unavailable")
    assets_valid, assets_detail = parse_native(
        validate_assets(),
        "assets=15 primary=3 payload=6 hidden=6 bundles=6 exact_load_sets=6")
    if not assets_valid:
        fail("native asset vector mismatch: " + assets_detail)
    valid, detail = parse_native(validate(mode == "admission"), EXPECTED[mode])
    if not valid or detail != EXPECTED[mode]:
        fail("native map vector mismatch: " + detail)
    after = {str(path): sha(path) for path in protected}
    if after != before:
        fail("cold readback changed protected packages")
    unreal.log("BUNDLE-LEASE-MAP-READBACK-PASS mode=%s hashes_unchanged=%d %s" %
               (mode, len(protected), detail))


flags = set(sys.argv[1:])
if ("--admission" in flags) == ("--final" in flags):
    fail("exactly one of --admission/--final is required")
main("admission" if "--admission" in flags else "final")
