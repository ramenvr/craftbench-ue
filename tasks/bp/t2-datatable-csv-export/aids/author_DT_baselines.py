"""Author the three t2-datatable-csv-export baseline DataTables (binary half).

Run headless on the ThirdPerson substrate project (authoring only, no render;
the module must already be built so /Script/ThirdPerson.EvalItemRow resolves):

  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

Flow (fail-closed, dawn-fog authoring mold):
  1. create each DataTable asset at /Game/Tasks/t2-datatable-csv-export/data/
     with its scaffold row struct, fill it from the PINNED CSV literal below,
     and save;
  2. STAGE-1 in-process grade with the real grader
     (tools/verify-single/introspect/datatable_csv_export.py): expect the
     EMPTY-submission vector — 0/13 where every failing detail is an
     agent-side *_CSV_MISSING / EXPORTS_DIR_ABSENT token and NO
     *_TABLE_MISSING / *_PROBE_ERROR token appears (proves the baselines and
     the grader's live reads);
  3. STAGE-2: copy ../reference/Content/Tasks/<id>/exports/ into the live
     Content tree, re-grade expecting 13/13, then DELETE the copied exports
     dir — the substrate must end baselines-only.

BASELINE_CSVS below is THE single source of truth for the pinned table
content. The reference CSVs and the offline oracle both derive from it — edit
it only together with them.

Output contract (grep the newest ThirdPerson*.log):
  DTEXPORT-CREATED <table>
  DTEXPORT-VECTOR stage=<1|2> passed=<n>/13
  DTEXPORT-DONE            (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

try:
    import unreal  # absent when the offline oracle imports the constants
except ImportError:
    unreal = None

TASK_ID = "t2-datatable-csv-export"
PKG_DIR = "/Game/Tasks/%s/data" % TASK_ID

# Struct path -> pinned content. First header cell is the row-name column
# label, which UE's importer ignores; its exporter writes "---" (calibration
# item: confirm on the stage-2 grade).
TABLE_STRUCTS = {
    "DT_EvalItems": "/Script/ThirdPerson.EvalItemRow",
    "DT_EvalWaves": "/Script/ThirdPerson.EvalWaveRow",
    "DT_EvalTuning": "/Script/ThirdPerson.EvalTuningRow",
}

# Values are deliberately non-default, distinct per row, and exactly
# float-representable (0.5 / 0.25 / 0.75 fractions) so no gate can hinge on
# decimal formatting (dead-gate audit, notes.md).
BASELINE_CSVS = {
    "DT_EvalItems": (
        '---,DisplayName,Cost,Weight\n'
        'Sword,"Iron Sword",250,8.5\n'
        'Shield,"Oak Shield",180,12.25\n'
        'Potion,"Healing Draught",35,0.5\n'
        'Torch,"Pine Torch",12,1.75\n'
    ),
    "DT_EvalWaves": (
        '---,EnemyCount,SpawnInterval\n'
        'Wave1,5,2.5\n'
        'Wave2,9,1.75\n'
        'Wave3,14,1.25\n'
    ),
    "DT_EvalTuning": (
        '---,Value\n'
        'PlayerSpeed,640\n'
        'JumpHeight,420\n'
    ),
}

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "datatable_csv_export.py")
# Derived from _HERE (this file lives at tasks/<basket>/<id>/aids/), not a
# hardcoded basket: survives tree moves.
REFERENCE_EXPORTS = os.path.join(
    os.path.abspath(os.path.join(_HERE, "..")), "reference", "Content", "Tasks",
    TASK_ID, "exports")


def die(msg):
    print("DTEXPORT-ERROR %s" % msg)
    raise SystemExit(msg)


def _grade_in_process():
    """Run the real grader in-process; returns (passed, total, details)."""
    spec = importlib.util.spec_from_file_location("_dt_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    start = out.index(mod.INTROSPECT_JSON_START) + len(mod.INTROSPECT_JSON_START)
    end = out.index(mod.INTROSPECT_JSON_END)
    payload = json.loads(out[start:end].strip())
    checks = payload["checks"]
    return (sum(1 for c in checks if c["passed"]), len(checks),
            [c["detail"] for c in checks if not c["passed"]])


def _author_table(name, struct_path, csv_text):
    if unreal.EditorAssetLibrary.does_asset_exist("%s/%s" % (PKG_DIR, name)):
        unreal.EditorAssetLibrary.delete_asset("%s/%s" % (PKG_DIR, name))
    struct = unreal.load_object(None, struct_path)
    if struct is None:
        die("row struct not found: %s (build ThirdPersonEditor first)"
            % struct_path)
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", struct)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    table = tools.create_asset(name, PKG_DIR, unreal.DataTable, factory)
    if table is None:
        die("create_asset failed for %s" % name)
    ok = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
        table, csv_text)
    if isinstance(ok, (tuple, list)):
        ok = ok[0] if ok else False
    if not ok:
        die("fill_data_table_from_csv_string rejected the pinned CSV for %s"
            % name)
    got = sorted(str(n) for n in
                 unreal.DataTableFunctionLibrary.get_data_table_row_names(table))
    expected = sorted(ln.split(",", 1)[0] for ln
                      in csv_text.strip().splitlines()[1:])
    if got != expected:
        die("%s row names %s != pinned %s" % (name, got, expected))
    if not unreal.EditorAssetLibrary.save_asset("%s/%s" % (PKG_DIR, name),
                                                only_if_is_dirty=False):
        die("save_asset failed for %s" % name)
    print("DTEXPORT-CREATED %s" % name)


def main():
    if unreal is None:
        die("this script must run inside UnrealEditor-Cmd")

    for name, struct_path in TABLE_STRUCTS.items():
        _author_table(name, struct_path, BASELINE_CSVS[name])

    # STAGE 1: empty-submission vector — no exports dir on the live tree.
    passed, total, details = _grade_in_process()
    print("DTEXPORT-VECTOR stage=1 passed=%d/%d" % (passed, total))
    if total != 13 or passed != 0:
        die("stage-1 vector unexpected: %d/%d %s" % (passed, total, details))
    bad = [d for d in details
           if ("_TABLE_MISSING" in d or "_PROBE_ERROR" in d
               or "_ABORTED" in d or "_LOAD_FAILED" in d)]
    if bad:
        die("stage-1 verifier-side tokens present (baselines broken?): %s"
            % bad)

    # STAGE 2: overlay the reference exports, expect 13/13, then remove them.
    content_dir = str(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()))
    live_exports = os.path.join(content_dir, "Tasks", TASK_ID, "exports")
    if not os.path.isdir(REFERENCE_EXPORTS):
        die("reference exports missing at %s" % REFERENCE_EXPORTS)
    try:
        shutil.copytree(REFERENCE_EXPORTS, live_exports, dirs_exist_ok=True)
        passed, total, details = _grade_in_process()
        print("DTEXPORT-VECTOR stage=2 passed=%d/%d" % (passed, total))
        if (passed, total) != (13, 13):
            die("stage-2 reference vector not 13/13: %s" % details)
    finally:
        shutil.rmtree(live_exports, ignore_errors=True)

    print("DTEXPORT-DONE")


if __name__ == "__main__":
    main()
