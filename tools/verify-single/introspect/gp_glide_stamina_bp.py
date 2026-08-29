"""L2-introspect script for the gp-glide-stamina-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). Emits a
CRAFTBENCH-INTROSPECT-JSON verdict the L2-introspect layer parses.

Asserts, STRUCTURALLY (no PIE, no render — the behavior itself is gated by the
unchanged L2 fixture `AGlideStaminaFunctionalTest`):

  * ``/Game/Tasks/gp-glide-stamina-bp/`` exists and lists >= 1 asset, AND
  * >= 1 Blueprint asset under that folder has a ``GeneratedClass`` deriving
    from ``ACraftBenchCharacter`` (the BP pawn deliverable), AND
  * that BP pawn's class-defaults ``GrantedAbilities`` array contains >= 1
    ability class that is itself Blueprint-generated (class path under
    ``/Game/``, not ``/Script/``), AND
  * NO native (C++) subclass of ``ACraftBenchCharacter`` exists — without this
    the three checks above are pure EXISTENCE checks and never ask which pawn
    L2 actually grades, so a C++ solve shipped next to a conforming Blueprint
    passes both layers (native candidates are resolved FIRST). See the
    ``resolved_pawn_is_blueprint`` block in :func:`main` for the full argument.

Substrate: **ThirdPerson** since 2026-08-05 (owner decision: gameplay tasks run
on the Third Person template substrate, which ships the mannequin content
natively). The scaffold class name and every check are unchanged from the
CraftBenchTemplate era (git history) — only the native module that hosts the
scaffold moved (``/Script/ThirdPerson``), and ``/Game/Characters/`` is now the
substrate's own content rather than an imported pool.

Anti-circularity: stock UE Python only; never Aura's MCP tools.
Identity is by **pre-declared content path + derivation**, never by asset or
class NAME (the agent may name the Blueprints anything).
Run headless by the runner via ``UnrealEditor-Cmd -ExecutePythonScript=``.

API notes (NOT yet live-validated on UE 5.8 — each check is wrapped in its own
try/except so one bad API name degrades to a single FAILED check with the
exception in ``detail``, never an aborted verdict; the derivation check tries
three independent routes before giving up):
  * ``unreal.EditorAssetLibrary.list_assets(dir, recursive=True)`` enumerates
    the folder; ``does_directory_exist`` guards the empty-submission case.
  * ``unreal.EditorAssetLibrary.load_blueprint_class(path)`` returns the
    Blueprint's generated ``UClass`` (None / raises for non-Blueprint assets).
    Fallback: ``unreal.load_object(None, path + "_C")``.
  * Derivation: ``unreal.MathLibrary.class_is_child_of(cls, parent)``
    (KismetMathLibrary::ClassIsChildOf); fallback isinstance on
    ``unreal.get_default_object(cls)`` vs ``unreal.CraftBenchCharacter`` (the
    game module's native classes are reflected into the ``unreal`` namespace
    once the project is loaded).
  * ``GrantedAbilities`` is an ``EditAnywhere BlueprintReadWrite`` UPROPERTY on
    ``ACraftBenchCharacter`` — read off the BP pawn's CDO via
    ``get_editor_property('granted_abilities')``. A Blueprint-generated ability
    class's ``get_path_name()`` starts with ``/Game/``; a native (C++) one with
    ``/Script/``.
"""
import json
import os
import sys

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

# Sibling import, same mechanism the four other -bp graders use: this file is
# standalone by history, not by design, and it carried its OWN copy of the mesh
# probe — which meant the 2026-08-15 FALSE_FAIL widening had to be made twice or
# this task would keep failing conforming submissions. Reusing the library is the
# fix that cannot drift again.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # no __file__ — cannot locate the lib
    _HERE = None
if _HERE and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# A failure HERE is deliberately NOT caught: a missing verifier-owned library is
# a verifier defect and must kill the verdict channel (layer `error` ->
# HARNESS-ERROR, exit 7, NON-GRADED) rather than be scored against the model.
import _bp_variant_lib as bpl  # noqa: E402

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# Pre-declared content folder of the task's deliverable (NEVER name-based).
TASK_DIR = "/Game/Tasks/gp-glide-stamina-bp"

# The substrate scaffold class the BP pawn must derive from.
SCAFFOLD_CLASS_NAME = "CraftBenchCharacter"

# The native module hosting the scaffold (the ThirdPerson substrate's
# agent-writable runtime module).
SCAFFOLD_MODULE = "ThirdPerson"

# Committed ABSTRACT native subclass(es) of the scaffold -- the 2026-08-05
# health-first stage-1 base (ships in the substrate at HEAD, not agent work).
# Exempt from the resolved_pawn_is_blueprint native sweep by EXACT /Script/
# path: the L2 resolver skips CLASS_Abstract candidates
# (CraftBenchPawnFunctionalTest.cpp), so an abstract native can never win pawn
# resolution and cannot be the decoy this check exists to catch. An agent
# cannot author a colliding native class (a duplicate class name will not
# compile), and any OTHER native subclass still fails the check.
COMMITTED_ABSTRACT_BASES = {
    "/Script/%s.CraftBenchBareCharacter" % SCAFFOLD_MODULE,
}

# The read-only visual-representation pool (task.md §Workspace, 2026-08-04).
# Pool-anchored on purpose: "some mesh exists" is gameable with an empty
# placeholder asset under the agent-writable path, while /Game/Characters/ is
# the substrate's own mannequin content (native to the Third Person template,
# deny-listed for agents) — the agent cannot author into it.
POOL_PREFIX = "/Game/Characters/"


def check(cid, passed, detail=""):
    return {"id": cid, "passed": bool(passed), "detail": str(detail)}


def emit(checks):
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)


def _scaffold_class():
    """The native scaffold UClass, or None. Reflected as ``unreal.<Name>`` once
    the project's game module is loaded; ``load_object`` on the /Script/ path is
    the fallback."""
    cls = getattr(unreal, SCAFFOLD_CLASS_NAME, None)
    if cls is not None:
        try:
            return cls.static_class()
        except Exception:  # noqa: BLE001 — some reflections ARE the UClass already
            return cls
    try:
        return unreal.load_object(None, "/Script/%s.%s" % (SCAFFOLD_MODULE, SCAFFOLD_CLASS_NAME))
    except Exception:  # noqa: BLE001
        return None


def _generated_class(asset_path):
    """The Blueprint asset's generated UClass, or None for non-BP assets."""
    try:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
        if cls is not None:
            return cls
    except Exception:  # noqa: BLE001 — fall through to the _C route
        pass
    try:
        return unreal.load_object(None, asset_path + "_C")
    except Exception:  # noqa: BLE001
        return None


def _derives_from_scaffold(cls, scaffold):
    """Three independent derivation probes; True on the first that answers."""
    if cls is None or scaffold is None:
        return False
    try:
        if unreal.MathLibrary.class_is_child_of(cls, scaffold):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        cdo = unreal.get_default_object(cls)
        py_scaffold = getattr(unreal, SCAFFOLD_CLASS_NAME, None)
        if py_scaffold is not None and isinstance(cdo, py_scaffold):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:  # walk the super chain by name
        cur = cls
        for _ in range(64):
            if cur is None:
                break
            if cur.get_name() == SCAFFOLD_CLASS_NAME:
                return True
            cur = cur.get_super_class() if hasattr(cur, "get_super_class") else None
    except Exception:  # noqa: BLE001
        pass
    return False


def _native_pawn_subclasses(scaffold):
    """``(paths, swept_ok)`` — NATIVE (C++) subclasses of the scaffold that are
    currently loaded, plus whether the reflection sweep actually worked.

    Mirrors the fixture's native-candidate sweep (``GetDerivedClasses`` filtered
    to ``ClassGeneratedBy == nullptr``): the game module's UCLASSes are reflected
    into the ``unreal`` namespace once the project loads, a NATIVE class's
    ``get_path_name()`` lives under ``/Script/``, and a Blueprint-generated one
    under ``/Game/``.

    ``swept_ok`` is a fail-closed self-test: the sweep must be able to SEE the
    scaffold itself. Without it the check would silently PASS whenever the sweep
    returned nothing for an API reason — failing OPEN, the dangerous direction.
    """
    found = []
    swept_ok = False
    for name in dir(unreal):
        if name.startswith("_"):
            continue
        try:
            cls = getattr(unreal, name).static_class()
            path = cls.get_path_name()
        except Exception:  # noqa: BLE001 — enums/structs/functions have no static_class
            continue
        if not path.startswith("/Script/"):
            continue
        if path in COMMITTED_ABSTRACT_BASES:
            # Committed ABSTRACT stage-1 base (2026-08-05 health-first seam) --
            # skipped by the L2 resolver (CLASS_Abstract), so it can never be
            # the resolved decoy. See COMMITTED_ABSTRACT_BASES above.
            continue
        if name == SCAFFOLD_CLASS_NAME:
            swept_ok = True  # the sweep can see the scaffold, so it is working
            continue
        if _derives_from_scaffold(cls, scaffold):
            found.append(path)
    return found, swept_ok


def _granted_bp_abilities(pawn_cls):
    """Paths of Blueprint-generated (non-native) entries in the BP pawn CDO's
    GrantedAbilities array."""
    cdo = unreal.get_default_object(pawn_cls)
    granted = cdo.get_editor_property("granted_abilities")
    out = []
    native = []
    for ability_cls in granted or []:
        if ability_cls is None:
            continue
        try:
            path = ability_cls.get_path_name()
        except Exception:  # noqa: BLE001
            continue
        if path.startswith("/Game/"):
            out.append(path)
        else:
            # THE GRANTED-ABILITY NATIVE HOLE, closed 2026-08-10.
            # This used to DISCARD non-/Game/ entries and the caller then asserted
            # merely "at least one BP ability". So a pawn granting
            # [GA_BlueprintDecoy, UMyCppAbility] PASSED: the decoy satisfied the
            # count while the C++ ability did the real work. `resolved_pawn_is_blueprint`
            # could not catch it either - it sweeps native PAWN subclasses, and a
            # native ABILITY is not a pawn. Both layers went green on a submission
            # the prompt forbids in as many words ("Do not add or modify any C++
            # source for this task").
            # Returning them lets the caller REJECT, which cannot false-FAIL:
            # neither substrate commits a single UGameplayAbility subclass
            # (`grep -rn "public UGameplayAbility" UE-projects/*/Source/*/` is
            # empty outside the verifier module), so every /Script/ entry here is
            # agent C++ by construction.
            native.append(path)
    return out, native


def main():
    checks = []

    # --- task_folder_exists ------------------------------------------------
    assets = []
    try:
        exists = unreal.EditorAssetLibrary.does_directory_exist(TASK_DIR)
        if exists:
            assets = list(
                unreal.EditorAssetLibrary.list_assets(TASK_DIR, recursive=True) or []
            )
        checks.append(check(
            "task_folder_exists",
            bool(exists and assets),
            "%s: exists=%s, %d asset(s): %s" % (TASK_DIR, exists, len(assets), assets),
        ))
    except Exception as e:  # noqa: BLE001
        checks.append(check("task_folder_exists", False, repr(e)))

    # --- bp_pawn_present ---------------------------------------------------
    scaffold = _scaffold_class()
    bp_pawn_cls = None
    bp_pawn_path = None
    probed = []
    try:
        for raw in assets:
            # list_assets returns object paths like /Game/.../BP_X.BP_X — strip
            # the .ObjectName suffix down to the package path load_* expects.
            path = str(raw).split(".")[0]
            cls = _generated_class(path)
            if cls is None:
                continue
            probed.append(path)
            if _derives_from_scaffold(cls, scaffold):
                bp_pawn_cls = cls
                bp_pawn_path = path
                break
        checks.append(check(
            "bp_pawn_present",
            bp_pawn_cls is not None,
            "scaffold=%s; blueprint(s) probed=%s; pawn=%s"
            % (SCAFFOLD_CLASS_NAME, probed, bp_pawn_path),
        ))
    except Exception as e:  # noqa: BLE001
        checks.append(check("bp_pawn_present", False, repr(e)))

    # --- bp_pawn_grants_bp_ability ------------------------------------------
    if bp_pawn_cls is None:
        checks.append(check(
            "bp_pawn_grants_bp_ability", False, "no BP pawn resolved"))
    else:
        try:
            bp_abilities, native_abilities = _granted_bp_abilities(bp_pawn_cls)
            checks.append(check(
                "bp_pawn_grants_bp_ability",
                bool(bp_abilities) and not native_abilities,
                "BP-generated GrantedAbilities entries: %s; NATIVE (C++) entries "
                "that must not be present: %s" % (bp_abilities, native_abilities),
            ))
        except Exception as e:  # noqa: BLE001
            checks.append(check("bp_pawn_grants_bp_ability", False, repr(e)))

    # --- resolved_pawn_is_blueprint -----------------------------------------
    # The three checks above are EXISTENCE checks: they prove a conforming
    # Blueprint is present, never that it is the pawn L2 actually grades.
    # ResolveAgentPawnClass (CraftBenchPawnFunctionalTest.cpp, both substrates'
    # CraftBenchTests modules carry the identical port) enumerates
    # NATIVE subclasses BEFORE Blueprint ones and returns the first that grants
    # an Ability.Glide-tagged ability, so a C++ pawn shipped ALONGSIDE a
    # conforming Blueprint wins resolution: L2 grades the C++ solve while the
    # checks above grade the Blueprint, and the submission passes both layers
    # while violating the prompt's "Do not add or modify any C++ source for this
    # task." That is the decoy hole task.md §Anti-gaming note 2 documents; this
    # check closes it.
    #
    # Deliberately STRICTER than the fixture's preference — it rejects a native
    # subclass even where the tag preference would have skipped it. For a `-bp`
    # task ANY C++ subclass of the provided character is already the violation,
    # and the stricter rule is the one a human reviewer applies. The clean
    # substrate ships exactly ONE native subclass of ACraftBenchCharacter -- the
    # committed ABSTRACT stage-1 base, exempted by exact /Script/ path in
    # COMMITTED_ABSTRACT_BASES (the L2 resolver skips CLASS_Abstract, so it can
    # never be the graded pawn) -- so every OTHER one found is agent-authored.
    if scaffold is None:
        checks.append(check(
            "resolved_pawn_is_blueprint", False,
            "could not resolve the %s scaffold class" % SCAFFOLD_CLASS_NAME))
    else:
        try:
            natives, swept_ok = _native_pawn_subclasses(scaffold)
            if not swept_ok:
                checks.append(check(
                    "resolved_pawn_is_blueprint", False,
                    "native-class sweep is not working (could not see %s in the "
                    "unreal namespace); failing closed rather than passing on an "
                    "empty sweep" % SCAFFOLD_CLASS_NAME))
            elif natives:
                checks.append(check(
                    "resolved_pawn_is_blueprint", False,
                    "C++ subclass(es) of %s present: %s — native candidates are "
                    "enumerated BEFORE Blueprint ones, so L2 would grade the C++ "
                    "pawn, not the Blueprint deliverable"
                    % (SCAFFOLD_CLASS_NAME, natives)))
            else:
                checks.append(check(
                    "resolved_pawn_is_blueprint",
                    bp_pawn_cls is not None,
                    "no C++ subclass of %s; blueprint pawn=%s"
                    % (SCAFFOLD_CLASS_NAME, bp_pawn_path)))
        except Exception as e:  # noqa: BLE001
            checks.append(check("resolved_pawn_is_blueprint", False, repr(e)))

    # --- pawn_visibly_represented -------------------------------------------
    # The invisible-deliverable gate (task.md §Anti-gaming note 6). MEASURED
    # 2026-08-04: all 9 matrix reps across 3 models shipped behaviorally-graded
    # pawns with NO mesh — a human reviewer sees an empty level, and review was
    # only possible by instrumenting copies with a debug cube. The prompt now
    # requires a mannequin from the read-only /Game/Characters/ pool; this
    # asserts it structurally. The mesh must be ASSIGNED (not None) and its
    # asset path must live under the pool — see POOL_PREFIX for why the pool
    # anchor, not mere existence.
    if bp_pawn_cls is None:
        checks.append(check("pawn_visibly_represented", False, "no BP pawn resolved"))
    else:
        try:
            # Shared with the four sibling -bp graders: reads the inherited
            # `mesh` component FIRST and falls back to the pawn's own skeletal
            # mesh components, because the prompt never says which component
            # must carry the mannequin and the L2 fixture accepts either.
            comp_present, skm_path = bpl.assigned_mesh_path(bp_pawn_cls)
            checks.append(check(
                "pawn_visibly_represented",
                bool(skm_path) and skm_path.startswith(POOL_PREFIX),
                "pawn mesh component=%s; SkeletalMesh=%s (must be under %s)"
                % ("present" if comp_present else "MISSING",
                   skm_path, POOL_PREFIX),
            ))
        except Exception as e:  # noqa: BLE001
            checks.append(check("pawn_visibly_represented", False, repr(e)))

    emit(checks)


if __name__ == "__main__":
    main()
