"""Authoring aid - builds the t3-piercing-projectile reference solution.

VERIFIER-SIDE tooling (never shipped to agents, never graded itself). Runs
INSIDE the worktree ThirdPerson editor:

    UnrealEditor-Cmd.exe <worktree>/UE-projects/ThirdPerson/ThirdPerson.uproject
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash
        -stdout -FullStdOutLogOutput

TWO-PHASE CONTRACT (runbook in ../notes.md). Collision presets resolve from
Config/DefaultEngine.ini AT ENGINE BOOT, so:

  phase A (shell, BEFORE this script): append the reference collision
          section to the worktree substrate's Config/DefaultEngine.ini
          (the exact lines live in _INI_SECTION below; ../notes.md carries
          the copy-paste command). This script FAILS CLOSED with
          KPIERCE-NEEDS-INI if the section is absent - authoring or
          self-grading without it would bake/verify unresolved profiles.
  phase B (this script): author the three Blueprints, wire collision,
          compile, save, SELF-GRADE 9/9 against the real introspect
          (t3_piercing_projectile.py, exec'd in-process), then harvest the
          assets AND the session ini into ../reference/.
  phase C (shell, AFTER): git-restore the substrate ini (the reference copy
          keeps the change; the SUBSTRATE must stay baseline - cross-rep
          scratch law).

Markers (fail-closed; grep targets for the runner):
  KPIERCE-NEEDS-INI     phase A not done - nothing was authored
  KPIERCE-VECTOR        per-step progress
  KPIERCE-SPELLING      an API spelling died; NEEDS-GRAPH-LANE if component
                        authoring itself is the dead half
  KPIERCE-SELFGRADE     the in-process grade line (must read 9/9)
  KPIERCE-HARVEST       files copied into ../reference/
  KPIERCE-DONE          full success ONLY
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys

import unreal

TASK_ID = "t3-piercing-projectile"
CONTENT_DIR = "/Game/Tasks/t3-piercing-projectile"
AIDS_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(AIDS_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TASK_DIR)))
GRADER = os.path.join(REPO_ROOT, "tools", "verify-single", "introspect",
                      "t3_piercing_projectile.py")

# The exact reference config half. Phase A appends this to the substrate's
# Config/DefaultEngine.ini; the harvest copies the whole session ini into
# ../reference/Config/. Both config_allow rules cover every line.
_INI_SECTION = """
[/Script/Engine.CollisionProfile]
+DefaultChannelResponses=(Channel=ECC_GameTraceChannel1,DefaultResponse=ECR_Block,bTraceType=False,bStaticObject=False,Name="Projectile")
+Profiles=(Name="Bullet",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="Projectile",CustomResponses=((Channel="Pawn",Response=ECR_Ignore)),HelpText="Piercing projectile body")
+Profiles=(Name="Piercable",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="WorldStatic",CustomResponses=((Channel="Projectile",Response=ECR_Overlap)),HelpText="Wall a projectile passes through, overlap still fires")
+Profiles=(Name="NonPiercable",CollisionEnabled=QueryAndPhysics,bCanModify=True,ObjectTypeName="WorldStatic",HelpText="Wall that stops projectiles")
"""

CUBE = "/Engine/BasicShapes/Cube"


def log(msg):
    print(msg)
    try:
        unreal.log(msg)
    except Exception:  # noqa: BLE001
        pass


def die(msg):
    log("KPIERCE-ERROR " + msg)
    raise SystemExit(msg)


def vector(step):
    log("KPIERCE-VECTOR " + step)


# --------------------------------------------------------------------------- #
# phase-A gate: the session must have booted with the collision section        #
# --------------------------------------------------------------------------- #

def _project_ini_path():
    raw = unreal.Paths.project_config_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001
        full = os.path.abspath(str(raw))
    return os.path.join(str(full), "DefaultEngine.ini")


def require_ini():
    path = _project_ini_path()
    try:
        text = io.open(path, encoding="utf-8-sig").read()
    except OSError as e:
        die("KPIERCE-NEEDS-INI unreadable %s (%r)" % (path, e))
    need = ('Name="Projectile"', 'Name="Bullet"', 'Name="Piercable"',
            'Name="NonPiercable"')
    missing = [n for n in need if n not in text]
    if missing:
        die("KPIERCE-NEEDS-INI phase A not done, missing %s in %s"
            % (missing, path))
    vector("ini-present " + path)


# --------------------------------------------------------------------------- #
# Blueprint authoring (BlueprintFactory + SubobjectDataSubsystem - the KPBOOT  #
# recipe)                                                                      #
# --------------------------------------------------------------------------- #

def _asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def make_actor_bp(name):
    path = CONTENT_DIR + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        vector("bp-exists " + path + " (reusing)")
        return unreal.EditorAssetLibrary.load_asset(path)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    bp = _asset_tools().create_asset(name, CONTENT_DIR, unreal.Blueprint,
                                     factory)
    if bp is None:
        die("BlueprintFactory returned None for %s" % path)
    vector("bp-created " + path)
    return bp


def _subsystem():
    ss = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if ss is None:
        die("KPIERCE-SPELLING SubobjectDataSubsystem unavailable "
            "NEEDS-GRAPH-LANE")
    return ss


def _root_handle(ss, bp):
    handles = ss.k2_gather_subobject_data_for_blueprint(bp) \
        if hasattr(ss, "k2_gather_subobject_data_for_blueprint") \
        else ss.gather_subobject_data_for_blueprint(bp)
    if isinstance(handles, (tuple, list)) and len(handles) == 2 \
            and isinstance(handles[-1], (tuple, list)):
        handles = handles[-1]
    handles = list(handles or [])
    if not handles:
        die("gather returned no handles for %s" % bp.get_name())
    return handles[0]


def add_component(bp, component_class, var_name):
    """New SCS component via SubobjectDataSubsystem; returns the template."""
    ss = _subsystem()
    root = _root_handle(ss, bp)
    params = unreal.AddNewSubobjectParams(
        parent_handle=root, new_class=component_class,
        blueprint_context=bp)
    out = ss.add_new_subobject(params)
    handle, fail_reason = None, ""
    if isinstance(out, (tuple, list)):
        handle = out[0]
        if len(out) > 1:
            fail_reason = str(out[1])
    else:
        handle = out
    data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
    if isinstance(data, (tuple, list)):
        data = data[-1] if data else None
    obj = None
    if data is not None:
        lib = unreal.SubobjectDataBlueprintFunctionLibrary
        for spelling in ("get_object", "get_associated_object"):
            fn = getattr(lib, spelling, None)
            if fn is None:
                continue
            try:
                obj = fn(data)
            except Exception:  # noqa: BLE001
                continue
            if obj is not None:
                break
    if obj is None:
        die("KPIERCE-SPELLING add_new_subobject gave no template "
            "(reason=%s) NEEDS-GRAPH-LANE" % fail_reason)
    try:
        ss.rename_subobject(handle, unreal.Text(var_name))
    except Exception:  # noqa: BLE001 - cosmetic; grading is name-blind
        pass
    vector("component-added %s on %s" % (var_name, bp.get_name()))
    return obj


def set_collision(comp, profile, overlap_events):
    """Profile via the BlueprintCallable setter, body_instance fallback."""
    applied = False
    fn = getattr(comp, "set_collision_profile_name", None)
    if fn is not None:
        try:
            fn(profile)
            applied = True
        except Exception as e:  # noqa: BLE001
            log("KPIERCE-SPELLING set_collision_profile_name failed %r" % e)
    if not applied:
        try:
            bi = comp.get_editor_property("body_instance")
            bi.set_editor_property("collision_profile_name", profile)
            comp.set_editor_property("body_instance", bi)  # struct COPY law
            applied = True
        except Exception as e:  # noqa: BLE001
            die("KPIERCE-SPELLING no route set profile %s (%r)"
                % (profile, e))
    comp.set_editor_property("generate_overlap_events", bool(overlap_events))
    got = None
    fn = getattr(comp, "get_collision_profile_name", None)
    if fn is not None:
        try:
            got = str(fn())
        except Exception:  # noqa: BLE001
            got = None
    if got is not None and got != profile:
        die("profile did not stick: wanted %s got %s" % (profile, got))
    vector("collision-set profile=%s overlaps=%s" % (profile, overlap_events))


def set_cube_mesh(comp):
    mesh = unreal.EditorAssetLibrary.load_asset(CUBE)
    if mesh is None:
        die("engine cube unloadable at %s" % CUBE)
    comp.set_editor_property("static_mesh", mesh)


def compile_and_save(bp):
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    if lib is not None and getattr(lib, "compile_blueprint", None) is not None:
        lib.compile_blueprint(bp)
    if not unreal.EditorAssetLibrary.save_loaded_asset(bp):
        die("save failed for %s" % bp.get_name())
    vector("compiled-saved " + bp.get_name())


# --------------------------------------------------------------------------- #
# self-grade: exec the REAL grader in-process, parse its verdict               #
# --------------------------------------------------------------------------- #

def self_grade():
    import contextlib

    if not os.path.isfile(GRADER):
        die("grader not found at %s" % GRADER)
    src = io.open(GRADER, encoding="utf-8").read()
    buf = io.StringIO()
    ns = {"__name__": "__cb_selfgrade__", "__file__": GRADER}
    with contextlib.redirect_stdout(buf):
        exec(compile(src, GRADER, "exec"), ns)  # noqa: S102 - verifier-owned file
        ns["main"]()
    out = buf.getvalue()
    m = re.search(r"CRAFTBENCH-INTROSPECT-JSON-START\s*\n(.*?)\n\s*"
                  r"CRAFTBENCH-INTROSPECT-JSON-END", out, re.S)
    if m is None:
        die("self-grade produced no verdict block")
    checks = json.loads(m.group(1))["checks"]
    passed = sum(1 for c in checks if c["passed"])
    log("KPIERCE-SELFGRADE %d/%d" % (passed, len(checks)))
    for c in checks:
        log("  %s %s %s" % ("PASS" if c["passed"] else "FAIL",
                            c["id"], c["detail"]))
    if passed != len(checks) or len(checks) != 9:
        die("self-grade not 9/9")


# --------------------------------------------------------------------------- #
# harvest                                                                      #
# --------------------------------------------------------------------------- #

def _content_fs_dir():
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001
        full = os.path.abspath(str(raw))
    return str(full)


def harvest():
    src_dir = os.path.join(_content_fs_dir(), "Tasks", TASK_ID)
    dst_assets = os.path.join(TASK_DIR, "reference", "Content", "Tasks",
                              TASK_ID)
    os.makedirs(dst_assets, exist_ok=True)
    copied = 0
    for name in sorted(os.listdir(src_dir)):
        if name.lower().endswith(".uasset"):
            shutil.copy2(os.path.join(src_dir, name),
                         os.path.join(dst_assets, name))
            copied += 1
            log("KPIERCE-HARVEST asset " + name)
    if copied != 3:
        die("harvest expected 3 .uasset, copied %d from %s"
            % (copied, src_dir))
    dst_cfg = os.path.join(TASK_DIR, "reference", "Config")
    os.makedirs(dst_cfg, exist_ok=True)
    shutil.copy2(_project_ini_path(),
                 os.path.join(dst_cfg, "DefaultEngine.ini"))
    log("KPIERCE-HARVEST config DefaultEngine.ini")


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    require_ini()

    bullet = make_actor_bp("BP_Bullet")
    comp = add_component(bullet, unreal.SphereComponent, "BulletCollision")
    set_collision(comp, "Bullet", overlap_events=True)
    compile_and_save(bullet)

    pierce = make_actor_bp("BP_PiercableWall")
    comp = add_component(pierce, unreal.StaticMeshComponent, "WallMesh")
    set_cube_mesh(comp)
    set_collision(comp, "Piercable", overlap_events=True)
    compile_and_save(pierce)

    solid = make_actor_bp("BP_NonPiercableWall")
    comp = add_component(solid, unreal.StaticMeshComponent, "WallMesh")
    set_cube_mesh(comp)
    set_collision(comp, "NonPiercable", overlap_events=False)
    compile_and_save(solid)

    self_grade()
    harvest()
    log("KPIERCE-DONE")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        die("unhandled %r" % e)
