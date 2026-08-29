"""Author the kp-engine-source-search REFERENCE deliverable.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline and its corpus is the PINNED ENGINE
SOURCE itself (read-only, outside the sandbox), so the flow is:

  1. CORPUS TRUTH RE-DERIVATION - open the live engine source under the
     running editor's own root and re-derive every answer the grader pins
     (the delegate declaration, the cvar default expression, the declaring
     module, the NAME_SIZE value). Any mismatch with the grader's
     EXPECTED_ANSWERS constants die()s: the pinned answer key must be a
     fact of THIS engine, proven at authoring time, or nothing ships.
  2. BUILD THE DELIVERABLE - write answers.txt at the real content path
     FROM THE GRADER'S OWN CONSTANTS (agreement by construction; the file
     is never hand-typed here).
  3. SELF-GRADE IN-PROCESS with the real verifier script
     (tools/verify-single/introspect/kp_engine_source_search.py, stdout
     captured, CRAFTBENCH-INTROSPECT-JSON parsed) - this also proves the
     engine-pin probe (SystemLibrary.get_engine_version) live under
     -nullrhi. Harvest into tasks/python/kp-engine-source-search/reference/
     ONLY on a 7/7 vector.
  4. CLEANUP - delete the task folder from the substrate so it ends with no
     Content/Tasks/kp-engine-source-search directory at all. DISK IS TRUTH
     (2026-08 lane law): the deliverable is a plain text file, no asset was
     ever created, so there is no registry row to chase - and if the asset
     registry somehow held a stale row for the folder, that would be a
     KPESS-WARN, never a die, after a validated harvest.

Fail-closed pattern (author_all_assets.py precedent): every step verifies
its own result and die()s loudly; the KPESS-DONE marker prints ONLY on full
success - its absence means FAILED. TASK_DIR is derived from this file's own
location (tasks/<basket>/<id>/aids/), never a hardcoded basket.

UE 5.8 python cautions (2026-08 lane laws), noted for completeness - this
aid touches NONE of the hazardous surfaces: no Blueprint is created (no
BlueprintFactory, no K2 graph wiring), no CDO is read (were one needed, the
law is unreal.get_default_object(cls), NEVER cls.get_default_object()), no
SCS/subobject walk, no protected reflection properties (UbergraphPages,
EdGraphPinType pins), no asset rename (registry tombstones). The only
unreal calls are Paths (roots) and the grader's own version probe.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPESS-TRUTH <qid> value=<derived> evidence=<file>:<line>
  KPESS-VECTOR passed=<n>/7 fails=[ids]
  KPESS-HARVEST <relative destination>
  KPESS-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil

import unreal

TASK_ID = "kp-engine-source-search"

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
SUBSTRATE_TASK_CONTENT = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID)
ANSWERS_FILE = os.path.join(SUBSTRATE_TASK_CONTENT, "reports", "answers.txt")
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_engine_source_search.py")


def die(msg):
    print("KPESS-ERROR %s" % msg)
    raise SystemExit(msg)


def load_grader():
    spec = importlib.util.spec_from_file_location("kpess_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 1. Corpus truth re-derivation (the live engine source vs the pinned key)     #
# --------------------------------------------------------------------------- #

def engine_root():
    """The installation root (the directory containing Engine/)."""
    raw = unreal.Paths.root_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        full = os.path.abspath(str(raw))
    root = str(full)
    if not os.path.isdir(os.path.join(root, "Engine", "Source")):
        die("engine root %r carries no Engine/Source tree" % root)
    return root


def read_lines(root, rel):
    """(lines, rel) for one engine source file; die if unreadable."""
    path = os.path.join(root, *rel.split("/"))
    if not os.path.isfile(path):
        die("engine source file missing: %s" % path)
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return text.splitlines(), rel


def find_line(lines, rel, pattern, what):
    """(match, 1-based line number) for the ONE line matching pattern."""
    rx = re.compile(pattern)
    hits = [(rx.search(line), n) for n, line in enumerate(lines, 1)
            if rx.search(line)]
    if not hits:
        die("%s: no line in %s matches %r" % (what, rel, pattern))
    if len(hits) > 1:
        die("%s: %d lines in %s match %r - ambiguous corpus fact"
            % (what, len(hits), rel, pattern))
    return hits[0]


def derive_truth(mod, root):
    """{qid: (value, 'file:line')} re-derived from the live engine source."""
    truth = {}

    # delegate-header: the header that DECLARES the delegate member. The
    # declaration line is the evidence; the answer is the header's own path.
    header_rel = mod.EXPECTED_ANSWERS[mod.QID_DELEGATE]
    lines, rel = read_lines(root, header_rel)
    _m, n = find_line(lines, rel,
                      r"FSimpleMulticastDelegate\s+OnEnginePreExit\s*;",
                      "delegate declaration")
    truth[mod.QID_DELEGATE] = (header_rel, "%s:%d" % (rel, n))

    # cvar-default: parse the initializer expression (ints joined by *) of
    # the variable the cvar registration binds, and evaluate it.
    cvar_rel = "Engine/Source/Runtime/Engine/Private/DataChannel.cpp"
    lines, rel = read_lines(root, cvar_rel)
    m, n = find_line(
        lines, rel,
        r"NetMaxConstructedPartialBunchSizeBytes\s*=\s*([0-9][0-9\s*]*);",
        "cvar default initializer")
    factors = [int(f) for f in m.group(1).replace(" ", "").split("*")]
    value = 1
    for f in factors:
        value *= f
    find_line(lines, rel,
              r"TEXT\(\"net\.MaxConstructedPartialBunchSizeBytes\"\)",
              "cvar registration")
    truth[mod.QID_CVAR] = (str(value), "%s:%d" % (rel, n))

    # class-module: the class declaration must live under the module whose
    # Build.cs stem is the answer.
    module_name = mod.EXPECTED_ANSWERS[mod.QID_MODULE]
    class_rel = "Engine/Source/Runtime/%s/Public/Dom/JsonObject.h" % module_name
    lines, rel = read_lines(root, class_rel)
    _m, n = find_line(lines, rel, r"^class\s+FJsonObject\s*$",
                      "FJsonObject class declaration")
    build_cs = os.path.join(root, "Engine", "Source", "Runtime", module_name,
                            "%s.Build.cs" % module_name)
    if not os.path.isfile(build_cs):
        die("module rules file missing: %s" % build_cs)
    truth[mod.QID_MODULE] = (module_name, "%s:%d" % (rel, n))

    # name-capacity: the enum constant's literal value.
    name_rel = "Engine/Source/Runtime/Core/Public/UObject/NameTypes.h"
    lines, rel = read_lines(root, name_rel)
    m, n = find_line(lines, rel, r"\bNAME_SIZE\s*=\s*(\d+)", "NAME_SIZE value")
    truth[mod.QID_NAME] = (m.group(1), "%s:%d" % (rel, n))

    for qid in mod.QUESTION_IDS:
        value, evidence = truth[qid]
        print("KPESS-TRUTH %s value=%s evidence=%s" % (qid, value, evidence))
        expected = mod.EXPECTED_ANSWERS[qid]
        if value != expected:
            die("corpus drift on %s: engine says %r, grader pins %r - "
                "re-derive the answer key before shipping anything"
                % (qid, value, expected))
    return truth


# --------------------------------------------------------------------------- #
# 2. Build the deliverable from the grader's own constants                     #
# --------------------------------------------------------------------------- #

def build_answers(mod):
    lines = ["answer id=%s value=%s" % (qid, mod.EXPECTED_ANSWERS[qid])
             for qid in mod.QUESTION_IDS]
    os.makedirs(os.path.dirname(ANSWERS_FILE), exist_ok=True)
    with open(ANSWERS_FILE, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("KPESS-ANSWERS %d lines" % len(lines))


# --------------------------------------------------------------------------- #
# 3. Grade in-process with the REAL grader; harvest only on 7/7                #
# --------------------------------------------------------------------------- #

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


def harvest():
    if not os.path.isfile(ANSWERS_FILE):
        die("nothing to harvest at %s" % ANSWERS_FILE)
    dst = os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID,
                       "reports", "answers.txt")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(ANSWERS_FILE, dst)
    print("KPESS-HARVEST %s"
          % os.path.relpath(dst, TASK_DIR).replace(os.sep, "/"))


def cleanup():
    """Leave the substrate exactly as this task ships it: nothing at all.

    DISK IS TRUTH (2026-08 lane law): no asset was created, so no registry
    interaction is owed. After the validated harvest above, any in-memory
    registry oddity about this plain-file folder would be a KPESS-WARN,
    never a die; filesystem residue, by contrast, still dies.
    """
    if os.path.isdir(SUBSTRATE_TASK_CONTENT):
        shutil.rmtree(SUBSTRATE_TASK_CONTENT, ignore_errors=True)
    if os.path.isdir(SUBSTRATE_TASK_CONTENT):
        die("filesystem residue remains at %s" % SUBSTRATE_TASK_CONTENT)
    try:
        if unreal.EditorAssetLibrary.does_directory_exist(
                "/Game/Tasks/%s" % TASK_ID):
            print("KPESS-WARN stale registry row for /Game/Tasks/%s - disk "
                  "is clean, continuing" % TASK_ID)
    except Exception:  # noqa: BLE001 - advisory only; disk is the truth
        pass


def main():
    if os.path.isfile(ANSWERS_FILE):
        die("substrate already carries %s - refusing to overwrite"
            % ANSWERS_FILE)
    if os.path.isdir(os.path.join(REFERENCE_DIR, "Content")):
        die("reference/ already populated - delete it first to re-author")
    if not os.path.isfile(GRADER):
        die("grader missing at %s" % GRADER)

    mod = load_grader()
    root = engine_root()
    derive_truth(mod, root)
    build_answers(mod)

    vector = grade_in_process(mod)
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPESS-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 7:
        die("grader emitted %d checks, wanted 7" % len(vector))
    if fails:
        for cid in fails:
            print("KPESS-FAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 7/7; nothing harvested")

    harvest()
    cleanup()
    print("KPESS-DONE")


main()
