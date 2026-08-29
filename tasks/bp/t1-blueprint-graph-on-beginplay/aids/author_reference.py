"""Authoring provenance for task t1-blueprint-graph-on-beginplay.

Produces, fail-closed, the two binaries this task is missing:

  1. Content/Maps/t1-blueprint-graph-on-beginplay/L_GraphMath.umap
       - the committed task map: the L2 fixture actor ONLY (the verifier
         spawns the graded subject itself; nothing else may be placed).
  2. tasks/bp/t1-blueprint-graph-on-beginplay/reference/Content/Tasks/
         t1-blueprint-graph-on-beginplay/BP_GraphMath.uasset
       - the harvested reference Blueprint (parent AGraphMathActor, EventGraph:
         BeginPlay -> Get BaseValue / Get BonusValue -> integer Add -> build
         string "CRAFTBENCH_GRAPH_TOTAL=" + total -> Print String), DELETED
         from the substrate after harvest so the graded tree ships no gold.

Run against the CraftBenchTemplate substrate with a REAL off-screen RHI (map
authoring crashes under -nullrhi):

  UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
      -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen

GRAPH-WIRING PRECONDITION (the one step vanilla editor Python cannot do):
UE 5.8 Python exposes no API for creating/wiring K2 event-graph nodes, so the
reference graph is wired ONCE via the MCP bp lane (precedent:
tasks/bp/t0-sanity-bp-log-on-beginplay/REFERENCE-NOTE.md - create_assets +
bp_agent, then PROMOTE the AuraSandbox file into the real Content/ tree before
re-running this script). This script therefore:
  - creates the empty BP shell at the required path if it is missing, then
    STOPS with GRAPHMATH-NEEDS-GRAPH-LANE (fail-closed, no DONE marker);
  - on a later run, VERIFIES the graph is wired (node-count + event-node probe
    over ubergraph_pages, fail-closed if unreadable), compiles, saves,
    harvests, and deletes the substrate copy.

Fail-closed contract: any error die()s before harvest; the DONE marker (log
line GRAPHMATH-DONE + marker file aids/author_reference.DONE) is written only
after every stage verified. Re-runs are idempotent: an already-harvested
reference short-circuits the BP stages; the map is (re)authored on every run.

UE 5.8 Python cautions honored here: editor-property names are probed
(underscore-folded spellings differ across surfaces); assets are created at
their final path and DELETED, never renamed (Asset Registry rename
tombstones); no SCS socket attachment is attempted (not exposed in 5.8).

Output contract (grep the newest CraftBenchTemplate*.log):
  GRAPHMATH-STAGE <name> ok
  GRAPHMATH-NEEDS-GRAPH-LANE          (shell created; wire the graph via MCP, re-run)
  GRAPHMATH-ERROR <detail>            (fail-closed abort)
  GRAPHMATH-DONE                      (success marker; absent = NOT done)
"""
import os
import shutil

import unreal

TASK_ID = "t1-blueprint-graph-on-beginplay"

BP_NAME = "BP_GraphMath"
BP_PKG_DIR = "/Game/Tasks/%s" % TASK_ID
BP_PATH = "%s/%s" % (BP_PKG_DIR, BP_NAME)

MAP_NAME = "L_GraphMath"
MAP_PKG_DIR = "/Game/Maps/%s" % TASK_ID
MAP_PATH = "%s/%s" % (MAP_PKG_DIR, MAP_NAME)

SCAFFOLD_CLASS = "/Script/CraftBenchTemplate.GraphMathActor"
FIXTURE_CLASS = "/Script/CraftBenchTests.GraphMathFunctionalTest"

# Repo layout, derived from this file living at tasks/bp/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "CraftBenchTemplate")
SUBSTRATE_BP_FILE = os.path.join(
    SUBSTRATE, "Content", "Tasks", TASK_ID, BP_NAME + ".uasset")
SUBSTRATE_MAP_FILE = os.path.join(
    SUBSTRATE, "Content", "Maps", TASK_ID, MAP_NAME + ".umap")
HARVEST_BP_FILE = os.path.join(
    TASK_DIR, "reference", "Content", "Tasks", TASK_ID, BP_NAME + ".uasset")
DONE_MARKER = os.path.join(_HERE, "author_reference.DONE")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("GRAPHMATH-ERROR %s" % msg)
    raise SystemExit(msg)


def stage_ok(name):
    print("GRAPHMATH-STAGE %s ok" % name)


def get_prop(obj, *names):
    """Probe underscore-folded property spellings; fail-closed on all-miss."""
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    die("no readable spelling among %s on %s: %r" % (names, obj, last))


# --------------------------------------------------------------------------- #
# Stage: preflight (classes compiled into the editor)                          #
# --------------------------------------------------------------------------- #

def preflight():
    scaffold = unreal.load_class(None, SCAFFOLD_CLASS)
    fixture = unreal.load_class(None, FIXTURE_CLASS)
    if scaffold is None or fixture is None:
        die("task classes not found (scaffold=%s fixture=%s) - build "
            "CraftBenchTemplateEditor first" % (scaffold, fixture))
    stage_ok("preflight")
    return scaffold, fixture


# --------------------------------------------------------------------------- #
# Stage: map — fixture actor ONLY, saved to the committed-map path            #
# --------------------------------------------------------------------------- #

def author_map(fixture_cls):
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if EAL.does_asset_exist(MAP_PATH):
        unreal.log("[%s] map already exists at %s; re-authoring over it"
                   % (TASK_ID, MAP_PATH))
        if not les.load_level(MAP_PATH):
            die("load_level failed for existing %s" % MAP_PATH)
    else:
        # Template_Default ships a WorldSettings (raw new_level does not).
        if not les.new_level_from_template(
                MAP_PATH, "/Engine/Maps/Templates/Template_Default"):
            die("new_level_from_template failed for %s" % MAP_PATH)

    # Idempotence + the fixture-only invariant: clear any prior fixture,
    # scaffold, or (stale) reference-BP instances before placing fresh ones.
    for actor in list(eas.get_all_level_actors()):
        cls_name = actor.get_class().get_name()
        if cls_name in ("GraphMathFunctionalTest", "GraphMathActor",
                        BP_NAME + "_C"):
            eas.destroy_actor(actor)

    fixture = eas.spawn_actor_from_class(
        fixture_cls, unreal.Vector(0.0, 400.0, 100.0))
    if fixture is None:
        die("fixture spawn failed")

    if not les.save_current_level():
        die("save_current_level failed")
    if not os.path.isfile(SUBSTRATE_MAP_FILE):
        die("map saved but %s not found on disk" % SUBSTRATE_MAP_FILE)
    stage_ok("map")


# --------------------------------------------------------------------------- #
# Stage: reference BP shell (created at its FINAL path; never renamed)        #
# --------------------------------------------------------------------------- #

def ensure_bp_shell(scaffold_cls):
    if EAL.does_asset_exist(BP_PATH):
        stage_ok("bp-shell(existing)")
        return unreal.load_asset(BP_PATH)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", scaffold_cls)
    at = unreal.AssetToolsHelpers.get_asset_tools()
    bp = at.create_asset(BP_NAME, BP_PKG_DIR, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed for %s" % BP_PATH)
    if not EAL.save_asset(BP_PATH):
        die("save_asset failed for freshly created %s" % BP_PATH)
    stage_ok("bp-shell(created)")
    return bp


# --------------------------------------------------------------------------- #
# Stage: graph-wired verification (fail-closed; wiring itself is MCP-lane)     #
# --------------------------------------------------------------------------- #

def verify_graph_wired(bp):
    """True iff the event graph carries a wired-looking node set: >= 4 nodes
    including at least one event node. Fail-closed: an unreadable graph is an
    ERROR, never a silent pass."""
    pages = get_prop(bp, "ubergraph_pages", "UbergraphPages")
    total_nodes = 0
    saw_event_node = False
    for graph in list(pages or []):
        nodes = get_prop(graph, "nodes", "Nodes")
        for node in list(nodes or []):
            total_nodes += 1
            if "K2Node_Event" in node.get_class().get_name():
                saw_event_node = True
    if total_nodes >= 4 and saw_event_node:
        stage_ok("graph-verified(nodes=%d)" % total_nodes)
        return True
    print("GRAPHMATH-NEEDS-GRAPH-LANE shell at %s has %d node(s), "
          "event_node=%s. Wire BeginPlay -> Get BaseValue/Get BonusValue -> "
          "Add(int) -> append to 'CRAFTBENCH_GRAPH_TOTAL=' -> Print String "
          "via the MCP bp lane (see t0-sanity-bp REFERENCE-NOTE.md; promote "
          "the AuraSandbox file into real Content/ first), then re-run this "
          "script." % (BP_PATH, total_nodes, saw_event_node))
    return False


# --------------------------------------------------------------------------- #
# Stage: compile + save + harvest + substrate delete                          #
# --------------------------------------------------------------------------- #

def compile_and_check(bp):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    status = get_prop(bp, "status", "Status")
    if "ERROR" in str(status).upper():
        die("blueprint compile reported %s" % status)
    if not EAL.save_asset(BP_PATH):
        die("save_asset failed post-compile for %s" % BP_PATH)
    stage_ok("compile(status=%s)" % status)


def harvest_and_scrub():
    if not os.path.isfile(SUBSTRATE_BP_FILE):
        die("expected substrate file missing: %s" % SUBSTRATE_BP_FILE)
    os.makedirs(os.path.dirname(HARVEST_BP_FILE), exist_ok=True)
    shutil.copy2(SUBSTRATE_BP_FILE, HARVEST_BP_FILE)
    if not os.path.isfile(HARVEST_BP_FILE):
        die("harvest copy failed: %s" % HARVEST_BP_FILE)
    stage_ok("harvest")

    # DELETE (never rename - registry tombstones) so the graded substrate
    # ships no gold. Directory too, once empty.
    if not EAL.delete_asset(BP_PATH):
        die("delete_asset failed for %s" % BP_PATH)
    if EAL.does_directory_exist(BP_PKG_DIR):
        EAL.delete_directory(BP_PKG_DIR)  # best-effort; file check is the gate
    if os.path.isfile(SUBSTRATE_BP_FILE):
        die("substrate still carries %s after delete" % SUBSTRATE_BP_FILE)
    stage_ok("scrub")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main():
    scaffold_cls, fixture_cls = preflight()

    # The map is (re)authored on every run - it is cheap and idempotent.
    author_map(fixture_cls)

    if os.path.isfile(HARVEST_BP_FILE) and not EAL.does_asset_exist(BP_PATH):
        # Reference already harvested + scrubbed on a prior run.
        stage_ok("bp(already-harvested)")
    else:
        bp = ensure_bp_shell(scaffold_cls)
        try:
            wired = verify_graph_wired(bp)
        except BaseException as e:  # noqa: BLE001 - the probe's own die() is
            # a SystemExit; a PROTECTED reflection property (measured
            # 2026-08-11: 'UbergraphPages' cannot be read in 5.8) must mean
            # "cannot certify wired", never a crash past the fail-closed exit.
            print("GRAPHMATH-WARN wiredness probe unavailable (%s) - "
                  "treating as not wired" % type(e).__name__)
            wired = False
        if not wired:
            # Fail-closed: shell exists, graph not wired. No DONE marker.
            raise SystemExit("graph not wired; see GRAPHMATH-NEEDS-GRAPH-LANE")
        compile_and_check(bp)
        harvest_and_scrub()

    with open(DONE_MARKER, "w", encoding="ascii") as fh:
        fh.write("map=%s\nreference=%s\n" % (SUBSTRATE_MAP_FILE, HARVEST_BP_FILE))
    print("GRAPHMATH-DONE map=%s reference=%s" % (MAP_PATH, HARVEST_BP_FILE))


main()
