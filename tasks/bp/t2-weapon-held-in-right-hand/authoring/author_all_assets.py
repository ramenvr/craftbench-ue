"""Author ALL t2-weapon-held-in-right-hand assets: 3 baselines + reference + 5
discrimination variants, with the real grader run in-process at every state.

Run headless on the ThirdPerson substrate project:
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

ROUTE MAP (engine-source audit 2026-07-28, <UE_ROOT>):
  * Socket creation IS scriptable despite USkeleton::Sockets being
    reflection-denied: new_object(SkeletalMeshSocket, outer=mesh) ->
    USkeletalMesh.AddSocket (BlueprintCallable, auto-names "Socket"/roots the
    bone) -> USkeletalMeshSocket.SetSocketParent(mesh, "hand_r") ->
    SkeletalMeshEditorSubsystem.RenameSocket(-> "WeaponSocket").
    RemoveSocket exists for state resets. Offsets stay identity throughout.
  * SCS AttachToName has NO reflected write (bare UPROPERTY; the C++ setter
    FSubobjectData::SetSocketName is not in the script function library), so
    socket-bound BPs are authored via the HARVEST route: spawn a live
    Character, set its instance mesh, add + attach a StaticMeshComponent at
    runtime (AttachToComponent takes any socket/bone name, no validation),
    then create_blueprint_from_actor - the harvest bakes instance attachments
    (including socket names) into SCS nodes. Probed at startup; if absent the
    script dies with WEAPON-HARVEST-UNAVAILABLE before touching anything.
  * The two socketless BP variants would be SDS-authorable, but every BP here
    goes through the same harvest builder so a route difference can never be
    the hidden second deviation between a variant and the reference.

STATE MACHINE (the substrate must END as baselines-only, ready to commit):
  baseline SKM has NO WeaponSocket; per-variant socket states are created and
  removed via AddSocket/RemoveSocket; per-variant BPs are rebuilt from zero at
  the same content path (delete + harvest). Grading happens IN-SESSION at each
  state; a state that fails its expectation aborts before harvest.

ORACLE LEG: weapon-on-mesh-no-socket MUST read 9/10 failing exactly
weapon_attach_socket_is_weapon_socket with socket=None. If it reads 10/10 the
transient-spawn check is DEAD and the task must be re-declared at 9 checks
(notes.md section 5) - the script aborts with WEAPON-CHECK-DEAD so a human
makes that call; it never ships assets for a dead check.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  WEAPON-CAL ...            calibration facts (socket enumeration, routes)
  WEAPON-VECTOR <state> passed=n/10 fails=[...]
  WEAPON-ASSET-OK <state> -> <harvested file>
  WEAPON-CHECK-DEAD / WEAPON-HARVEST-UNAVAILABLE   named aborts
  WEAPON-DONE               success marker; absent = FAILED
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "t2-weapon-held-in-right-hand"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
SKEL_PATH = "%s/SK_EvalChar_Skeleton" % PKG_DIR
SKM_PATH = "%s/SKM_EvalChar" % PKG_DIR
BP_PATH = "%s/BP_EvalChar" % PKG_DIR

STOCK_SKEL = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
STOCK_SKM = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
CUBE = "/Engine/BasicShapes/Cube"
SOCKET = "WeaponSocket"
HAND_R = "hand_r"

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
# TASK_DIR from the script location (tasks/<basket>/<id>/authoring/), not a
# hardcoded basket: survives tree moves.
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
SUB_DIR = os.path.join(REPO, "UE-projects", "ThirdPerson", "Content", "Tasks",
                       TASK_ID)
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "weapon_held_in_right_hand.py")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("WEAPON-ERROR %s" % msg)
    raise SystemExit(msg)


def save(path):
    if not EAL.save_asset(path, only_if_is_dirty=False):
        die("save_asset failed for %s" % path)


# --------------------------------------------------------------------------- #
# grading (the real verifier, in-process)                                      #
# --------------------------------------------------------------------------- #

def grade():
    spec = importlib.util.spec_from_file_location("weapon_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    try:
        payload = out.split(mod.INTROSPECT_JSON_START)[1].split(
            mod.INTROSPECT_JSON_END)[0]
        checks = json.loads(payload.strip())["checks"]
    except Exception as e:  # noqa: BLE001
        die("grader output unparseable: %r; tail=%r" % (e, out[-400:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


def expect(state, vector, must_fail, must_pass, substrings=()):
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("WEAPON-VECTOR %s passed=%d/%d fails=%s"
          % (state, len(vector) - len(fails), len(vector), fails))
    for cid in must_fail:
        if vector.get(cid, (True, ""))[0]:
            die("%s: %s should FAIL but passed" % (state, cid))
    for cid in must_pass:
        if not vector.get(cid, (False, "missing"))[0]:
            die("%s: %s should PASS but read %s" % (state, cid,
                                                    vector.get(cid)))
    for cid, sub in substrings:
        detail = vector.get(cid, (None, ""))[1]
        if sub not in detail:
            die("%s: %s detail %r missing expected substring %r"
                % (state, cid, detail, sub))


# --------------------------------------------------------------------------- #
# socket state on SKM_EvalChar                                                 #
# --------------------------------------------------------------------------- #

def _skm():
    m = EAL.load_asset(SKM_PATH)
    if m is None or not isinstance(m, unreal.SkeletalMesh):
        die("SKM_EvalChar unloadable")
    return m


def socket_names(mesh):
    return [str(mesh.get_socket_by_index(i).get_editor_property("socket_name"))
            for i in range(mesh.num_sockets())]


def add_weapon_socket(bone):
    mesh = _skm()
    sock = unreal.new_object(unreal.SkeletalMeshSocket, outer=mesh)
    mesh.add_socket(sock, False)
    auto_name = str(sock.get_editor_property("socket_name"))
    sock.set_socket_parent(mesh, bone)
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    if not sub.rename_socket(mesh, auto_name, SOCKET):
        die("rename_socket %s -> %s failed" % (auto_name, SOCKET))
    got = mesh.find_socket(SOCKET)
    if got is None:
        die("socket not findable after authoring")
    got_bone = str(got.get_editor_property("bone_name"))
    if got_bone != bone:
        die("socket bone read back %r, wanted %r" % (got_bone, bone))
    rl = got.get_editor_property("relative_location")
    rr = got.get_editor_property("relative_rotation")
    if rl.length() > 1e-6 or abs(rr.pitch) + abs(rr.yaw) + abs(rr.roll) > 1e-6:
        die("socket offsets not identity: %s %s" % (rl, rr))
    save(SKM_PATH)


def remove_weapon_socket():
    mesh = _skm()
    if mesh.find_socket(SOCKET) is not None:
        sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
        if not sub.remove_socket(mesh, SOCKET):
            die("remove_socket failed")
    if mesh.find_socket(SOCKET) is not None:
        die("socket still present after removal")
    save(SKM_PATH)


# --------------------------------------------------------------------------- #
# BP builder: harvest from a live actor                                        #
# --------------------------------------------------------------------------- #

def _harvest_fn():
    for owner in (getattr(unreal, "EditorLevelLibrary", None),):
        fn = getattr(owner, "create_blueprint_from_actor", None) if owner \
            else None
        if fn:
            return fn
    return None


def build_bp(weapon=None):
    """(Re)build BP_EvalChar at BP_PATH from a live Character instance.

    weapon: None -> baseline (no Weapon component); else a dict
      {parent: 'mesh'|'capsule', socket: '<name>'|None, cube: bool}
    """
    if EAL.does_asset_exist(BP_PATH):
        if not EAL.delete_asset(BP_PATH):
            die("could not delete existing BP_EvalChar")
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = eas.spawn_actor_from_class(unreal.Character,
                                       unreal.Vector(0, 0, 20000))
    if actor is None:
        die("Character spawn failed")
    try:
        mesh_comp = actor.get_editor_property("mesh")
        skm = EAL.load_asset(SKM_PATH)
        mesh_comp.set_skeletal_mesh_asset(skm)
        mesh_comp.set_relative_location(unreal.Vector(0, 0, -89), False, False)
        mesh_comp.set_relative_rotation(unreal.Rotator(0, 0, -90), False, False)

        if weapon is not None:
            comp = actor.add_component_by_class(
                unreal.StaticMeshComponent, False, unreal.Transform(), False)
            if comp is None:
                die("add_component_by_class failed")
            if not comp.rename("Weapon", actor):
                die("component rename to Weapon failed")
            if weapon.get("cube", True):
                comp.set_static_mesh(EAL.load_asset(CUBE))
            parent = (mesh_comp if weapon["parent"] == "mesh"
                      else actor.get_editor_property("capsule_component"))
            sock = weapon.get("socket")
            comp.attach_to_component(
                parent, sock if sock else "",
                unreal.AttachmentRule.KEEP_RELATIVE,
                unreal.AttachmentRule.KEEP_RELATIVE,
                unreal.AttachmentRule.KEEP_RELATIVE, False)

        harvest = _harvest_fn()
        if harvest is None:
            die("WEAPON-HARVEST-UNAVAILABLE create_blueprint_from_actor is "
                "not exposed - no scripted route to SCS AttachToName; author "
                "the BPs via the MCP lane instead")
        bp = harvest(BP_PATH, actor, False)
        if bp is None:
            die("create_blueprint_from_actor returned None")
    finally:
        eas.destroy_actor(actor)
    blueprint = EAL.load_asset(BP_PATH)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    save(BP_PATH)


# --------------------------------------------------------------------------- #
# harvest-to-tasks-tree file copies                                            #
# --------------------------------------------------------------------------- #

def ship(state, target_rel, *asset_names):
    for name in asset_names:
        src = os.path.join(SUB_DIR, name + ".uasset")
        if not os.path.isfile(src):
            die("%s: %s not on disk" % (state, src))
        dst = os.path.join(TASK_DIR, target_rel.replace("/", os.sep),
                           "Content", "Tasks", TASK_ID, name + ".uasset")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print("WEAPON-ASSET-OK %s -> %s" % (state, dst))


def main():
    # ---- phase 0: baselines --------------------------------------------- #
    for p in (SKEL_PATH, SKM_PATH, BP_PATH):
        if EAL.does_asset_exist(p):
            die("substrate already carries %s - refusing to overwrite" % p)
    os.makedirs(SUB_DIR, exist_ok=True)

    if not EAL.duplicate_asset(STOCK_SKEL, SKEL_PATH):
        die("skeleton duplicate failed")
    save(SKEL_PATH)
    if not EAL.duplicate_asset(STOCK_SKM, SKM_PATH):
        die("mesh duplicate failed")
    skm = _skm()
    dup_skel = EAL.load_asset(SKEL_PATH)
    # Property is VisibleAnywhere (EditConst) so set_editor_property refuses;
    # the supported write is the BlueprintSetter (SkeletalMesh.h:765), which
    # UE Python folds into the plain ATTRIBUTE (skm.skeleton = x) rather than
    # exposing set_skeleton() as a method. Try every plausible route in order.
    errors = []
    for route in ("attribute", "method", "editor_property"):
        try:
            if route == "attribute":
                skm.skeleton = dup_skel
            elif route == "method":
                skm.set_skeleton(dup_skel)
            else:
                skm.set_editor_property("skeleton", dup_skel)
            print("WEAPON-CAL skeleton re-point route=%s" % route)
            break
        except Exception as e:  # noqa: BLE001
            errors.append("%s: %r" % (route, e))
    else:
        die("mesh skeleton re-point failed on every route: %s" % errors)
    got = skm.get_editor_property("skeleton")
    if got is None or got.get_path_name().split(".")[0] != SKEL_PATH:
        die("mesh skeleton read back %s" % (got and got.get_path_name()))
    save(SKM_PATH)
    names = socket_names(skm)
    print("WEAPON-CAL baseline mesh+skeleton sockets=%s" % names)
    if SOCKET in names:
        die("baseline already ships a WeaponSocket - task would be void")

    build_bp(weapon=None)
    v = grade()
    expect("baseline", v,
           must_fail=["weapon_socket_exists", "char_has_weapon_component"],
           must_pass=["char_mesh_uses_task_skeletal_mesh",
                      "char_bp_compiles_up_to_date"])
    passed = sum(1 for ok, _ in v.values() if ok)
    if passed != 2:
        die("baseline scored %d/10, expected exactly 2/10 (notes.md "
            "section 5)" % passed)

    # ---- phase 1: reference --------------------------------------------- #
    add_weapon_socket(HAND_R)
    build_bp({"parent": "mesh", "socket": SOCKET, "cube": True})
    v = grade()
    expect("reference", v, must_fail=[],
           must_pass=list(v.keys()))  # all ten
    ship("reference", "reference", "SKM_EvalChar", "BP_EvalChar")

    # ---- phase 2: weapon-without-cube-mesh (ref SKM stays) --------------- #
    build_bp({"parent": "mesh", "socket": SOCKET, "cube": False})
    v = grade()
    expect("weapon-without-cube-mesh", v,
           must_fail=["weapon_shows_engine_cube"],
           must_pass=["weapon_attach_socket_is_weapon_socket",
                      "char_has_weapon_component"],
           substrings=[("weapon_shows_engine_cube", "WEAPON_MESH_NOT_CUBE")])
    ship("weapon-without-cube-mesh",
         "discrimination/weapon-without-cube-mesh",
         "SKM_EvalChar", "BP_EvalChar")

    # ---- phase 3: weapon-on-mesh-no-socket (THE ORACLE) ------------------ #
    build_bp({"parent": "mesh", "socket": None, "cube": True})
    v = grade()
    fails = sorted(cid for cid, (ok, _) in v.items() if not ok)
    print("WEAPON-VECTOR weapon-on-mesh-no-socket passed=%d/%d fails=%s"
          % (len(v) - len(fails), len(v), fails))
    if fails == []:
        die("WEAPON-CHECK-DEAD weapon_attach_socket_is_weapon_socket passed "
            "on an unbound weapon - the transient-spawn read is dead; "
            "re-declare the task at 9 checks (notes.md section 5) instead of "
            "shipping this matrix")
    if fails != ["weapon_attach_socket_is_weapon_socket"]:
        die("oracle leg failed %s, expected exactly the attach-socket check"
            % fails)
    detail = v["weapon_attach_socket_is_weapon_socket"][1]
    if "WEAPON_ATTACH_SOCKET_WRONG socket=None" not in detail:
        die("oracle detail %r lacks socket=None signature" % detail)
    ship("weapon-on-mesh-no-socket",
         "discrimination/weapon-on-mesh-no-socket",
         "SKM_EvalChar", "BP_EvalChar")

    # ---- phase 4: weapon-on-capsule-root --------------------------------- #
    build_bp({"parent": "capsule", "socket": None, "cube": True})
    v = grade()
    expect("weapon-on-capsule-root", v,
           must_fail=["weapon_attach_parent_is_character_mesh"],
           must_pass=["weapon_socket_exists", "char_has_weapon_component"],
           substrings=[("weapon_attach_parent_is_character_mesh",
                        "WEAPON_ATTACH_PARENT_WRONG")])
    ship("weapon-on-capsule-root", "discrimination/weapon-on-capsule-root",
         "SKM_EvalChar", "BP_EvalChar")

    # ---- phase 5: socket-on-wrong-bone (socket -> hand_l, ref BP) -------- #
    remove_weapon_socket()
    add_weapon_socket("hand_l")
    build_bp({"parent": "mesh", "socket": SOCKET, "cube": True})
    v = grade()
    expect("socket-on-wrong-bone", v,
           must_fail=["weapon_socket_on_hand_r"],
           must_pass=["weapon_socket_exists",
                      "weapon_attach_socket_is_weapon_socket"],
           substrings=[("weapon_socket_on_hand_r", "WEAPONSOCKET_BONE_WRONG")])
    ship("socket-on-wrong-bone", "discrimination/socket-on-wrong-bone",
         "SKM_EvalChar", "BP_EvalChar")

    # ---- phase 6: bone-name-instead-of-socket (NO socket, attach hand_r) - #
    remove_weapon_socket()
    build_bp({"parent": "mesh", "socket": HAND_R, "cube": True})
    v = grade()
    expect("bone-name-instead-of-socket", v,
           must_fail=["weapon_socket_exists",
                      "weapon_attach_socket_is_weapon_socket"],
           must_pass=["char_has_weapon_component",
                      "weapon_attach_parent_is_character_mesh"],
           substrings=[("weapon_attach_socket_is_weapon_socket",
                        "WEAPON_ATTACH_SOCKET_WRONG socket=hand_r")])
    ship("bone-name-instead-of-socket",
         "discrimination/bone-name-instead-of-socket", "BP_EvalChar")

    # ---- phase 7: reset substrate to the committed-to-be baselines. ------ #
    # The editor still holds these packages, so a byte-level file restore is
    # not safe in-session; rebuild the baseline states through the exact same
    # code paths and prove them with a final grade instead.
    remove_weapon_socket()          # SKM back to no-socket baseline
    build_bp(weapon=None)           # BP back to baseline
    v = grade()
    passed = sum(1 for ok, _ in v.values() if ok)
    if passed != 2:
        die("post-reset baseline scored %d/10, expected 2/10" % passed)
    print("WEAPON-CAL final substrate state re-graded 2/10 (baselines only)")
    print("WEAPON-DONE")


main()
