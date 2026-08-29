"""Fresh-process fixed readback for walker asset or authored map."""

import argparse
import os
import unreal


TASK_ID = "t3-both-walkers-yield-and-still-arrive"
ASSETS = {
    "baseline": ("/Game/Tasks/%s/BP_YieldingWalker" % TASK_ID,
                 False, 0.50, 650.0),
    "reference": ("/Game/Tasks/%s/BP_YieldingWalker" % TASK_ID,
                  True, 0.50, 650.0),
    "admission": ("/Game/__CraftBenchAdmission/%s/"
                  "BP_YieldingWalker_Admission" % TASK_ID,
                  True, 0.50, 650.0),
}
MAPS = {
    "admission": ("/Game/Maps/%s/L_BothWalkersYieldAdmission" % TASK_ID,
                  1, 1, 4, 4),
    "final": ("/Game/Maps/%s/L_BothWalkersYield" % TASK_ID,
              2, 2, 8, 8),
}


def fail(message):
    unreal.log_error("WALKER-YIELD-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("asset", "map"),
                        default=os.environ.get("CRAFTBENCH_WALKER_YIELD_KIND"))
    parser.add_argument("--mode", choices=(
        "baseline", "reference", "admission", "final"),
                        default=os.environ.get("CRAFTBENCH_WALKER_YIELD_MODE"))
    args, _ = parser.parse_known_args()
    if args.kind is None or args.mode is None:
        fail("kind/mode arguments or environment variables are required")
    if args.kind == "asset":
        if args.mode not in ASSETS:
            fail("asset mode must be baseline, reference, or admission")
        path, enabled, weight, radius = ASSETS[args.mode]
        blueprint = unreal.EditorAssetLibrary.load_asset(path)
        if blueprint is None:
            fail("asset did not load: " + path)
        result = str(
            unreal.WalkerYieldAuthoringLibrary.inspect_walker_blueprint(
                blueprint, enabled, weight, radius))
        if not result.startswith("PASS "):
            fail("asset contract: " + result)
        unreal.log("WALKER-YIELD-ASSET-READBACK mode=%s %s" %
                   (args.mode, result))
        return
    if args.mode not in MAPS:
        fail("map mode must be admission or final")
    path, scenarios, fixtures, walkers, goals = MAPS[args.mode]
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(path):
        fail("load_level failed: " + path)
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    result = str(unreal.WalkerYieldAuthoringLibrary.inspect_world(
        world, scenarios, fixtures, walkers, goals))
    if not result.startswith("PASS "):
        fail("map contract: " + result)
    unreal.log("WALKER-YIELD-MAP-READBACK mode=%s map=%s %s" %
               (args.mode, path, result))


main()
