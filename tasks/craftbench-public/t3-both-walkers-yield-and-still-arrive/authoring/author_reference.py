"""Enable avoidance only inside an explicitly admitted disposable project."""

import hashlib
import os
from pathlib import Path
import unreal


TASK_ID = "t3-both-walkers-yield-and-still-arrive"
ASSET = "/Game/Tasks/%s/BP_YieldingWalker" % TASK_ID
LIVE_PROJECT = (Path(__file__).resolve().parents[4] / "UE-projects" /
                "ThirdPerson").resolve()


def fail(message):
    unreal.log_error("WALKER-YIELD-REFERENCE-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    project = Path(unreal.Paths.project_dir()).resolve()
    if os.environ.get("CRAFTBENCH_REFERENCE_SCRATCH") != "1":
        fail("CRAFTBENCH_REFERENCE_SCRATCH=1 is required")
    if project == LIVE_PROJECT:
        fail("reference authoring is forbidden in the live project")
    file_path = (Path(unreal.Paths.project_content_dir()) / "Tasks" / TASK_ID /
                 "BP_YieldingWalker.uasset").resolve()
    if not file_path.is_file():
        fail("scratch baseline is missing: " + str(file_path))
    before = sha256(file_path)
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET)
    if blueprint is None:
        fail("scratch Blueprint did not load")
    result = str(
        unreal.WalkerYieldAuthoringLibrary.configure_walker_blueprint(
            blueprint, True, 0.50, 650.0))
    after = sha256(file_path)
    if not result.startswith("PASS ") or before == after:
        fail("reference did not become distinct: %s before=%s after=%s" %
             (result, before, after))
    unreal.log(
        "WALKER-YIELD-REFERENCE-SAVED scratch=1 asset=%s before=%s after=%s %s"
        % (ASSET, before, after, result))


main()
