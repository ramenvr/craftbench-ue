"""Author the t1-gameplay-tag-gate task MAP (the committed-binary source).

This is a cpp-basket task, so the reference deliverable is source (already at
../reference/Source/...) and this script authors the MAP ONLY:
Content/Maps/t1-gameplay-tag-gate/L_TagGate.umap on the CraftBenchTemplate
substrate, holding one placed ATagGateActor (its constructor stamps the
TagGateRoot identity tag) and one placed ATagGateFunctionalTest fixture.

Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
authoring crashes under -nullrhi), after building CraftBenchTemplateEditor:
  UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
      -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen

Fail-closed pattern (mirrors tasks/python/kp-spawn-level-actors/aids/):
  * every path is derived from this file's own location (tree moves survive;
    never a hardcoded basket);
  * every uncertain step dies loudly (TAGGATE-ERROR ...) instead of guessing;
  * the TAGGATE-DONE marker is printed ONLY on full success — grep the editor
    log for it; absent = FAILED.

UE 5.8 python cautions honoured:
  * no asset is ever RENAMED (renames leave Asset Registry tombstones) — the
    map name is final at creation time; re-authoring loads and overwrites in
    place;
  * no SCS socket attachment anywhere (unsettable from Python on 5.8);
  * no property writes beyond spawn transforms, so the underscore-folded
    property-name hazard does not arise (readback checks below would catch a
    silent miss anyway);
  * no graph pins, so no import_text pinning applies.

Output contract (grep the EDITOR LOG, newest CraftBenchTemplate*.log):
  TAGGATE-PLACED <actor label>
  TAGGATE-DONE               (success marker; absent = FAILED)
"""
import os

import unreal

TASK_ID = "t1-gameplay-tag-gate"
MAP_NAME = "L_TagGate"
MAP_PACKAGE_DIR = "/Game/Maps/%s" % TASK_ID
MAP_OBJECT_PATH = "%s/%s" % (MAP_PACKAGE_DIR, MAP_NAME)

HOST_CLASS_PATH = "/Script/CraftBenchTemplate.TagGateActor"
FIXTURE_CLASS_PATH = "/Script/CraftBenchTests.TagGateFunctionalTest"
HOST_IDENTITY_TAG = "TagGateRoot"

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "CraftBenchTemplate")
UMAP_FILE = os.path.join(SUBSTRATE, "Content", "Maps", TASK_ID, MAP_NAME + ".umap")


def die(msg):
    print("TAGGATE-ERROR %s" % msg)
    raise SystemExit(msg)


def main():
    # Sanity: this script must be running inside the intended substrate
    # project, or the save would land in a foreign Content/ tree.
    project_dir = os.path.abspath(unreal.SystemLibrary.get_project_directory())
    if os.path.normcase(project_dir.rstrip("\\/")) != os.path.normcase(SUBSTRATE):
        die("running inside %r but this task's substrate is %r - launch the "
            "CraftBenchTemplate project" % (project_dir, SUBSTRATE))

    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if les is None or eas is None:
        die("LevelEditorSubsystem / EditorActorSubsystem unavailable")

    host_cls = unreal.load_class(None, HOST_CLASS_PATH)
    fixture_cls = unreal.load_class(None, FIXTURE_CLASS_PATH)
    if host_cls is None or fixture_cls is None:
        die("task classes not found (%s, %s) - build CraftBenchTemplateEditor "
            "first" % (HOST_CLASS_PATH, FIXTURE_CLASS_PATH))

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
        unreal.log("[%s] map already exists at %s; re-authoring over it"
                   % (TASK_ID, MAP_OBJECT_PATH))
        if not les.load_level(MAP_OBJECT_PATH):
            die("load_level(%s) failed" % MAP_OBJECT_PATH)
    else:
        # Template_Default ships a WorldSettings (raw new_level does not).
        if not les.new_level_from_template(
                MAP_OBJECT_PATH, "/Engine/Maps/Templates/Template_Default"):
            die("new_level_from_template failed for %s" % MAP_OBJECT_PATH)

    # Idempotence: clear any prior instances before placing fresh ones.
    for actor in list(eas.get_all_level_actors()):
        if actor.get_class().get_name() in ("TagGateActor", "TagGateFunctionalTest"):
            eas.destroy_actor(actor)

    host = eas.spawn_actor_from_class(host_cls, unreal.Vector(0.0, 0.0, 100.0))
    if host is None:
        die("TagGateActor spawn failed")
    # Readback-verify the constructor-stamped identity tag: the fixture's whole
    # host resolution hangs off it.
    if not host.actor_has_tag(unreal.Name(HOST_IDENTITY_TAG)):
        die("placed TagGateActor does not carry the %r identity tag - the "
            "scaffold constructor changed?" % HOST_IDENTITY_TAG)
    print("TAGGATE-PLACED %s" % host.get_name())

    fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 400.0, 100.0))
    if fixture is None:
        die("TagGateFunctionalTest fixture spawn failed")
    print("TAGGATE-PLACED %s" % fixture.get_name())

    if not les.save_current_level():
        die("save_current_level failed")
    if not os.path.isfile(UMAP_FILE):
        die("save reported success but no file on disk at %s" % UMAP_FILE)

    print("TAGGATE-DONE")


main()
