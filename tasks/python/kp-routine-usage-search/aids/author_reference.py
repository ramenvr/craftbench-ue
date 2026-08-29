"""Author the kp-routine-usage-search CORPUS baseline + REFERENCE report.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

TWO-PHASE by design (K2 graph wiring is NOT authorable from stock python;
BP creation via BlueprintFactory is):

  Phase 1 (first run): creates the four corpus Blueprints at their FINAL
  substrate paths under /Game/Tasks/kp-routine-usage-search/corpus/ -
  BP_North (parent Actor), BP_East (parent = BP_North's generated class,
  no logic of its own), BP_South (parent Actor), BP_West (parent Actor,
  carrying the FName tag "ComputeChecksum" on its CDO as the name-only
  decoy) - compiles, saves, then byte-scans the saved packages and DIES
  with named KPUSAGE-NEEDS-GRAPH-LANE instructions for the two call nodes
  stock python cannot author (BP_North -> EvalUtilityLibrary.ComputeChecksum,
  BP_South -> EvalUtilityLibrary.FormatLabel; wire each into the class's
  begin-of-play event via the MCP graph lane, compile, save).

  Phase 2 (re-run after the graph-lane session): finds the corpus already
  present, re-verifies every structural fact AND the byte-scan invariants,
  derives the per-entry usage verdict from READ-BACK disk facts (byte-scan
  + parent-chain walk - never transcribed from the truth constants),
  asserts the derivation equals the verifier's pinned CORPUS_TRUTH, writes
  the reference report, computes + prints the corpus digests (KPUSAGE-HASH
  lines - pin them into the introspect's CORPUS_SHA256 in the same commit
  as the binaries), grades ITSELF in-process with the real verifier script
  requiring 9/9, harvests the report into reference/, and removes the
  report from the substrate. The corpus STAYS: it is committed substrate
  baseline, not overlay content.

Fail-closed pattern (author_all_assets.py precedent): every step verifies
its own result and die()s loudly; the KPUSAGE-DONE marker prints ONLY on
full success - its absence means FAILED. All paths derive from this file's
own location (tasks/<basket>/<id>/aids/), never a hardcoded basket.

UE 5.8 python lane laws honoured (each burned us before):
  * CDOs via ``unreal.get_default_object(cls)`` ONLY - NEVER
    ``cls.get_default_object()`` (it resolves against the class of the
    instance and returns the CDO of BlueprintGeneratedClass itself,
    poisoning every downstream read; refgate catch 2026-08-12).
  * NO reads of protected reflection properties (UbergraphPages,
    EdGraphPinType pins) - graph presence is proven by byte-scanning the
    SAVED package for the function FName + the library class FName.
  * Components would go through
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``; this
    corpus deliberately needs NO components, no sockets
    (craftbench-scs-attachtoname-gap), and no member variables.
  * BP creation via BlueprintFactory works; K2 GRAPH WIRING does not -
    hence the two-phase MCP-graph-lane handoff above.
  * Asset renames leave registry tombstones - every asset is created once
    at its final path; nothing here renames.
  * CLEANUP TREATS DISK AS TRUTH: after a validated harvest, a stale
    in-memory/registry row is a KPUSAGE-WARN, never a die.
  * Property names are underscore-folded - every set/read tries each
    plausible spelling and fails closed if none sticks (KPUSAGE-SPELLING
    lines record the winners for notes.md).

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPUSAGE-SPELLING <step>=<winning spelling>
  KPUSAGE-NEEDS-GRAPH-LANE bp=<path> call=<Library.Function>   (phase 1 exit)
  KPUSAGE-VERDICT <entry>=<yes|no> route=<direct|inherited|none>
  KPUSAGE-HASH <file>=<sha256>          (pin into CORPUS_SHA256)
  KPUSAGE-VECTOR passed=<n>/9 fails=[ids]
  KPUSAGE-HARVEST <relative destination>
  KPUSAGE-DONE                          (success marker; absent = FAILED)
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-routine-usage-search"
CORPUS_PKG = "/Game/Tasks/%s/corpus" % TASK_ID

LIB_NAME = "EvalUtilityLibrary"
FUNC_NAME = "ComputeChecksum"
SIBLING_NAME = "FormatLabel"

NORTH = "BP_North"   # direct caller of FUNC_NAME (graph-lane authored)
EAST = "BP_East"     # child of BP_North, no logic of its own (inherits)
SOUTH = "BP_South"   # caller of SIBLING_NAME only (graph-lane authored)
WEST = "BP_West"     # FName tag decoy: carries FUNC_NAME, no library tie
CORPUS_NAMES = (NORTH, EAST, SOUTH, WEST)

# The truth this corpus must realize (must equal the grader's CORPUS_TRUTH).
EXPECTED_TRUTH = {NORTH: True, EAST: True, SOUTH: False, WEST: False}

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
CORPUS_DIR = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID, "corpus")
REPORTS_DIR = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID, "reports")
REPORT_FILE = os.path.join(REPORTS_DIR, "usage.txt")
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
REFERENCE_REPORT = os.path.join(
    REFERENCE_DIR, "Content", "Tasks", TASK_ID, "reports", "usage.txt")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_routine_usage_search.py")
LIB_SRC_DIR = os.path.join(SUBSTRATE, "Source", "ThirdPerson", "Tasks",
                           TASK_ID)

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("KPUSAGE-ERROR %s" % msg)
    raise SystemExit(msg)


_SPELLING_LOG = {}


def note_spelling(step, spelling):
    if step not in _SPELLING_LOG:
        _SPELLING_LOG[step] = spelling
        print("KPUSAGE-SPELLING %s=%s" % (step, spelling))


def set_prop(obj, value, *names):
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
            note_spelling(names[0], name)
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable spelling among %s: %r" % (names, last))


def read_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    die("no readable spelling among %s: %r" % (names, last))


def bp_path(name):
    return "%s/%s" % (CORPUS_PKG, name)


def gen_class_path(name):
    return "%s.%s_C" % (bp_path(name), name)


def uasset_file(name):
    return os.path.join(CORPUS_DIR, "%s.uasset" % name)


def generated_class(name):
    cls = unreal.load_object(None, gen_class_path(name))
    if cls is None:
        die("generated class unresolvable at %s" % gen_class_path(name))
    return cls


def default_object(cls):
    """LANE LAW: module function only. cls.get_default_object() resolves
    against the class OF THE INSTANCE and poisons everything downstream."""
    fn = getattr(unreal, "get_default_object", None)
    if fn is None:
        die("unreal.get_default_object is not exposed")
    cdo = fn(cls)
    if cdo is None:
        die("no CDO for %r" % (cls,))
    return cdo


def compile_and_save(name, bp):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not EAL.save_asset(bp_path(name), only_if_is_dirty=False):
        die("save_asset failed for %s" % bp_path(name))
    if not os.path.isfile(uasset_file(name)):
        die("saved package missing on DISK at %s" % uasset_file(name))


# --------------------------------------------------------------------------- #
# 0. preflight                                                                 #
# --------------------------------------------------------------------------- #

def preflight():
    if getattr(unreal, LIB_NAME, None) is None:
        die("unreal.%s is not exposed - the ThirdPersonEditor target with "
            "the committed library sources must be built before this aid "
            "runs" % LIB_NAME)
    for fname in ("%s.h" % LIB_NAME, "%s.cpp" % LIB_NAME):
        if not os.path.isfile(os.path.join(LIB_SRC_DIR, fname)):
            die("library source missing at %s"
                % os.path.join(LIB_SRC_DIR, fname))
    if os.path.isfile(REFERENCE_REPORT):
        die("reference/ already carries a report - delete it first to "
            "re-author")


# --------------------------------------------------------------------------- #
# 1. corpus build (idempotent: creates only what is missing)                   #
# --------------------------------------------------------------------------- #

def ensure_bp(name, parent_cls):
    """The named corpus Blueprint, created at its final path if absent."""
    if EAL.does_asset_exist(bp_path(name)):
        bp = EAL.load_asset(bp_path(name))
        if bp is None:
            die("existing asset unloadable at %s" % bp_path(name))
        return bp, False
    factory = unreal.BlueprintFactory()
    set_prop(factory, parent_cls, "parent_class", "ParentClass")
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, CORPUS_PKG, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s" % bp_path(name))
    compile_and_save(name, bp)
    return bp, True


def _child_of(child_cls, base_cls):
    """KDBS-proven route (2026-08-12): MathLibrary.class_is_child_of works on
    generated classes where every reflection read of Blueprint.parent_class
    and get_super_struct is protected/unavailable on 5.8."""
    lib = getattr(unreal, "MathLibrary", None)
    fn = getattr(lib, "class_is_child_of", None) if lib is not None else None
    if fn is None:
        die("MathLibrary.class_is_child_of is not exposed to Python")
    return bool(fn(child_cls, base_cls))


def _gen_cls(name):
    cls = EAL.load_blueprint_class(bp_path(name))
    if cls is None:
        die("generated class unresolvable for %s" % name)
    return cls


def verify_parent(child_name, expected_parent_path_fragment):
    """The child's parent-class path must contain the expected fragment."""
    # child-of check instead of a parent-property read (protected on 5.8):
    # the fragment names a corpus member; ancestry proves the wiring.
    expected_name = expected_parent_path_fragment.rsplit("/", 1)[-1].split(".")[0]
    if not _child_of(_gen_cls(child_name), _gen_cls(expected_name)):
        die("%s is not a descendant of %s" % (child_name, expected_name))


def ensure_west_marker():
    """BP_West carries FUNC_NAME as an FName tag on its CDO - the name-only
    decoy. Tag defaults are plain property wiring (no graph, no variable
    machinery); verified by read-back and later by byte-scan."""
    bp = EAL.load_asset(bp_path(WEST))
    cdo = default_object(generated_class(WEST))
    tags = list(read_prop(cdo, "tags", "Tags") or [])
    if not any(str(t) == FUNC_NAME for t in tags):
        set_prop(cdo, [unreal.Name(FUNC_NAME)], "tags", "Tags")
        compile_and_save(WEST, bp)
        cdo = default_object(generated_class(WEST))
        tags = list(read_prop(cdo, "tags", "Tags") or [])
        if not any(str(t) == FUNC_NAME for t in tags):
            die("BP_West marker tag did not stick (read back %s)" % (tags,))


def build_corpus():
    ensure_bp(NORTH, unreal.Actor)
    ensure_bp(SOUTH, unreal.Actor)
    ensure_bp(WEST, unreal.Actor)
    # East is parented to North's GENERATED class - the indirect route.
    ensure_bp(EAST, generated_class(NORTH))
    verify_parent(EAST, gen_class_path(NORTH))
    ensure_west_marker()


# --------------------------------------------------------------------------- #
# 2. byte-scan invariants (the contamination gate + the phase-1 exit)          #
# --------------------------------------------------------------------------- #

def file_bytes(name):
    path = uasset_file(name)
    if not os.path.isfile(path):
        die("no package on disk at %s" % path)
    with open(path, "rb") as fh:
        return fh.read()


def scan(name, token):
    return token.encode("ascii") in file_bytes(name)


def verify_scan_invariants():
    """Every byte-level fact the corpus design depends on. A missing call
    node exits with the MCP-graph-lane handoff; a contaminated package
    (a token where none belongs) is a hard authoring error."""
    needs = []
    if not (scan(NORTH, FUNC_NAME) and scan(NORTH, LIB_NAME)):
        needs.append((bp_path(NORTH), "%s.%s" % (LIB_NAME, FUNC_NAME)))
    if not (scan(SOUTH, SIBLING_NAME) and scan(SOUTH, LIB_NAME)):
        needs.append((bp_path(SOUTH), "%s.%s" % (LIB_NAME, SIBLING_NAME)))
    if needs:
        for path, call in needs:
            print("KPUSAGE-NEEDS-GRAPH-LANE bp=%s call=%s" % (path, call))
        die("stock python cannot author K2 call nodes: wire each listed "
            "call into the class's begin-of-play event via the MCP graph "
            "lane (bp_agent / edit_blueprint / add_blueprint_node_to_strand "
            "+ insert_node_on_exec_wire), compile_blueprint, save, then "
            "re-run this aid for phase 2")
    # Contamination gates - these can never be repaired by the graph lane;
    # they mean the corpus was mis-authored and must be deleted and rebuilt.
    if scan(SOUTH, FUNC_NAME):
        die("CONTAMINATED: %s package mentions %s (it must only call %s)"
            % (SOUTH, FUNC_NAME, SIBLING_NAME))
    if scan(EAST, FUNC_NAME) or scan(EAST, SIBLING_NAME) or scan(EAST, LIB_NAME):
        die("CONTAMINATED: %s must carry NO library/function names of its "
            "own (its reference is inherited from %s)" % (EAST, NORTH))
    if not scan(WEST, FUNC_NAME):
        die("%s decoy marker absent from the saved package" % WEST)
    if scan(WEST, LIB_NAME):
        die("CONTAMINATED: %s must have no tie to %s" % (WEST, LIB_NAME))


# --------------------------------------------------------------------------- #
# 3. verdict derivation from READ-BACK disk facts (never the constants)        #
# --------------------------------------------------------------------------- #

def _parent_bp_name(name):
    """The corpus-internal parent Blueprint of `name`, or None if its parent
    is native/foreign. Reads only the unprotected parent_class property."""
    my_cls = _gen_cls(name)
    # Most-derived corpus ancestor via child-of checks (the KDBS idiom):
    # no protected reflection, no super-struct walk.
    ancestors = [c for c in CORPUS_NAMES
                 if c != name and _child_of(my_cls, _gen_cls(c))]
    if not ancestors:
        return None
    most_derived = ancestors[0]
    for c in ancestors[1:]:
        if _child_of(_gen_cls(c), _gen_cls(most_derived)):
            most_derived = c
    return most_derived


def derive_verdict(name, _depth=0):
    """(references, route): True iff this package - or an ancestor corpus
    package - byte-carries BOTH the function name AND the library class
    name (a call imports both; the tag decoy imports neither class)."""
    if _depth > len(CORPUS_NAMES):
        die("parent chain loop at %s" % name)
    if scan(name, FUNC_NAME) and scan(name, LIB_NAME):
        return True, ("direct" if _depth == 0 else "inherited")
    parent = _parent_bp_name(name)
    if parent is None:
        return False, "none"
    refs, _route = derive_verdict(parent, _depth + 1)
    return refs, ("inherited" if refs else "none")


def derive_all_verdicts():
    verdicts = {}
    for name in CORPUS_NAMES:
        refs, route = derive_verdict(name)
        verdicts[name] = refs
        print("KPUSAGE-VERDICT %s=%s route=%s"
              % (name, "yes" if refs else "no", route))
    if verdicts != EXPECTED_TRUTH:
        die("derived verdicts %s do not match the pinned truth %s - "
            "corpus and grader constants must be re-pinned TOGETHER"
            % (verdicts, EXPECTED_TRUTH))
    return verdicts


# --------------------------------------------------------------------------- #
# 4. the reference report (written from the derived verdicts)                  #
# --------------------------------------------------------------------------- #

def write_report(verdicts):
    lines = ["function name=%s" % FUNC_NAME]
    for name in CORPUS_NAMES:
        lines.append("entry name=%s references=%s"
                     % (name, "yes" if verdicts[name] else "no"))
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("KPUSAGE-REPORT %d lines" % len(lines))


# --------------------------------------------------------------------------- #
# 5. digests + in-process grade with the REAL verifier (9/9 or nothing)        #
# --------------------------------------------------------------------------- #

def load_grader():
    spec = importlib.util.spec_from_file_location("kpusage_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def corpus_digests():
    digests = {}
    for name in CORPUS_NAMES:
        h = hashlib.sha256(file_bytes(name)).hexdigest()
        digests["%s.uasset" % name] = h
        print("KPUSAGE-HASH %s.uasset=%s" % (name, h))
    return digests


def reconcile_hashes(mod, digests):
    """Inject fresh digests when the grader still carries the sentinel;
    demand exact agreement once real digests are pinned."""
    if set(mod.CORPUS_SHA256.keys()) != set(digests.keys()):
        die("grader CORPUS_SHA256 keys %s do not match the corpus %s"
            % (sorted(mod.CORPUS_SHA256), sorted(digests)))
    if any(h == mod.HASH_UNPINNED for h in mod.CORPUS_SHA256.values()):
        mod.CORPUS_SHA256.clear()
        mod.CORPUS_SHA256.update(digests)
        print("KPUSAGE-WARN grader digests were the sentinel; graded with "
              "the freshly computed set - PIN the KPUSAGE-HASH lines above "
              "into CORPUS_SHA256 in the SAME commit as the binaries")
    elif dict(mod.CORPUS_SHA256) != digests:
        die("pinned CORPUS_SHA256 disagrees with the corpus on disk - "
            "either the corpus drifted (rebuild or restore it) or the pins "
            "are stale (re-pin from the KPUSAGE-HASH lines above)")
    # Library pins are always real; verify them against the repo sources.
    for fname, pinned in mod.LIBRARY_SHA256.items():
        path = os.path.join(LIB_SRC_DIR, fname)
        if not os.path.isfile(path):
            die("library source missing at %s" % path)
        with open(path, "rb") as fh:
            got = hashlib.sha256(fh.read().replace(b"\r", b"")).hexdigest()
        if got != pinned:
            die("library pin stale for %s: disk=%s pinned=%s - re-pin the "
                "grader's LIBRARY_SHA256 alongside any source change"
                % (fname, got, pinned))


def grade_in_process(mod):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    try:
        payload = out.split(mod.INTROSPECT_JSON_START)[1].split(
            mod.INTROSPECT_JSON_END)[0]
        checks = json.loads(payload.strip())["checks"]
    except Exception as e:  # noqa: BLE001
        die("grader output unparseable: %r; raw=%r" % (e, out[-500:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


# --------------------------------------------------------------------------- #
# 6. harvest + cleanup (DISK IS TRUTH; corpus STAYS - it is baseline)          #
# --------------------------------------------------------------------------- #

def harvest():
    if not os.path.isfile(REPORT_FILE):
        die("nothing to harvest at %s" % REPORT_FILE)
    os.makedirs(os.path.dirname(REFERENCE_REPORT), exist_ok=True)
    shutil.copy2(REPORT_FILE, REFERENCE_REPORT)
    print("KPUSAGE-HARVEST %s"
          % os.path.relpath(REFERENCE_REPORT, TASK_DIR).replace(os.sep, "/"))


def cleanup():
    """The substrate ships the CORPUS (baseline) and NO report (deliverable).
    DISK IS TRUTH after a validated harvest: filesystem facts decide
    pass/fail here; a stale registry row is a WARN, never a die."""
    if os.path.isdir(REPORTS_DIR):
        shutil.rmtree(REPORTS_DIR, ignore_errors=True)
    if os.path.isdir(REPORTS_DIR):
        die("reports residue remains at %s" % REPORTS_DIR)
    for name in CORPUS_NAMES:
        if not os.path.isfile(uasset_file(name)):
            die("corpus package vanished from disk at %s" % uasset_file(name))
    # Registry is advisory ONLY at this point (lane law: disk is truth).
    try:
        for name in CORPUS_NAMES:
            if not EAL.does_asset_exist(bp_path(name)):
                print("KPUSAGE-WARN registry row stale for %s (disk file "
                      "present; harmless - the graded leg rescans)"
                      % bp_path(name))
    except Exception as e:  # noqa: BLE001
        print("KPUSAGE-WARN registry probe raised %r (disk already "
              "verified)" % (e,))
    print("KPUSAGE-NOTE commit the four corpus .uasset files as SUBSTRATE "
          "baseline (UE-projects/ThirdPerson/Content/Tasks/%s/corpus/) and "
          "pin the KPUSAGE-HASH digests into the grader in the same commit"
          % TASK_ID)


def main():
    preflight()
    build_corpus()
    verify_scan_invariants()          # phase-1 exit lives inside
    verdicts = derive_all_verdicts()
    write_report(verdicts)

    mod = load_grader()
    digests = corpus_digests()
    reconcile_hashes(mod, digests)

    vector = grade_in_process(mod)
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPUSAGE-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 9:
        die("grader emitted %d checks, wanted 9" % len(vector))
    if fails:
        for cid in fails:
            print("KPUSAGE-FAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 9/9; nothing harvested")

    harvest()
    cleanup()
    print("KPUSAGE-DONE")


main()
