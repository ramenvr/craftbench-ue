"""L2-introspect script for the gp-poison-dot-stack-bp task.

Structural, READ-ONLY verification that the deliverable **really is Blueprint**
(the `-bp` variant's anti-gaming gate against solving it in C++). Emits a
CRAFTBENCH-INTROSPECT-JSON verdict the L2-introspect layer parses.

Asserts, STRUCTURALLY (no PIE, no render — the behavior itself is gated by the
unchanged L2 fixture `APoisonStackFunctionalTest`):

  * ``/Game/Tasks/gp-poison-dot-stack-bp/`` exists and lists >= 1 asset, AND
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

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# Pre-declared content folder of the task's deliverable (NEVER name-based).
TASK_DIR = "/Game/Tasks/gp-poison-dot-stack-bp"

# The substrate scaffold class the BP pawn must derive from.
SCAFFOLD_CLASS_NAME = "CraftBenchCharacter"

# The native module hosting the scaffold (the ThirdPerson substrate's
# agent-writable runtime module). Fix applied with the 2026-08-05 health-first
# refactor: the /Script/ fallback below previously hardcoded CraftBenchTemplate,
# stale since the 2026-08-05 ThirdPerson migration (the getattr primary route
# masked it).
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


#: The engine base every GameplayEffect derives from, by reflected name.
GE_BASE_NAME = "GameplayEffect"


def _derives_from_named(cls, base_name):
    """Generic twin of `_derives_from_scaffold`, keyed on a base's reflected
    NAME rather than a resolved handle — the same three probes, in the same
    order, for the same reason (any one of them can be unavailable).

    Written as its own function rather than by calling `cls.is_child_of(...)`:
    that is not the idiom this script (or the test harness that models UE's
    Python reflection) uses, and reaching for it silently returned False for
    every class under test."""
    if cls is None:
        return False
    base = getattr(unreal, base_name, None)
    if base is not None:
        try:
            if unreal.MathLibrary.class_is_child_of(cls, base.static_class()):
                return True
        except Exception:  # noqa: BLE001
            pass
    try:  # walk the super chain by name
        cur = cls
        for _ in range(64):
            if cur is None:
                break
            if cur.get_name() == base_name:
                return True
            cur = cur.get_super_class() if hasattr(cur, "get_super_class") else None
    except Exception:  # noqa: BLE001
        pass
    return False


def _native_gameplay_effects():
    """``(paths, swept_ok)`` — NATIVE (C++) ``UGameplayEffect`` subclasses that
    are currently loaded.

    THE NATIVE-EFFECT HOLE, closed 2026-08-11. The 2026-08-10 fix above rejects
    a native ABILITY, and ``resolved_pawn_is_blueprint`` rejects a native PAWN.
    Neither sees a native EFFECT — and on this task the effect is where the
    graded behaviour actually lives: period, duration, the Health modifier,
    stacking policy, stack limit and refresh policy are all GameplayEffect
    properties. So a submission could ship a Blueprint pawn granting a Blueprint
    ability that applies a C++ ``UGameplayEffect``, satisfy all four existing
    checks, and have its entire assessed behaviour in C++ — on a task whose
    prompt says, in as many words, "Do not add or modify any C++ source for this
    task."

    Sound by the same argument the ability sweep uses, verified 2026-08-11:
    ``grep -rn "public UGameplayEffect" UE-projects/*/Source/*/`` is EMPTY
    outside the verifier module on both substrates, so every ``/Script/`` effect
    subclass found here is agent C++ by construction and rejecting it cannot
    false-FAIL committed work.

    PROPORTIONATE ON PURPOSE (owner steer 2026-08-11): this is a clearly-stated
    prompt requirement, not an exploit needing heavy machinery, so it is one
    more reflection sweep in the pattern already proven here — NOT a
    submission-wide "no C++ touched" diff against git HEAD. A model that does
    this has picked the approach it is better at and ignored the instruction;
    the right answer is a named FAIL that says so.

    ``swept_ok`` fails CLOSED exactly like the pawn sweep: the sweep must be
    able to see ``GameplayEffect`` itself, or an API change would silently
    return nothing and the check would pass on a submission it never inspected.
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
        if name == GE_BASE_NAME:
            swept_ok = True  # the sweep can see the engine base, so it is working
            continue
        if _derives_from_named(cls, GE_BASE_NAME):
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
    # ResolveAgentPawnClass (CraftBenchPawnFunctionalTest.cpp:63-149) enumerates
    # NATIVE subclasses BEFORE Blueprint ones and returns the first that grants
    # an Ability.Poison-tagged ability, so a C++ pawn shipped ALONGSIDE a
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

    # --- effect_is_blueprint -----------------------------------------------
    # The third native hole, and the one where the graded behaviour actually
    # lives on this task: period, duration, the Health modifier, stacking
    # policy, stack limit and refresh policy are all GameplayEffect properties.
    # A Blueprint pawn granting a Blueprint ability that applies a C++ effect
    # satisfied every check above while doing all its assessed work in C++.
    # See _native_gameplay_effects for why rejecting a /Script/ effect cannot
    # false-FAIL committed work.
    try:
        native_ges, ge_swept_ok = _native_gameplay_effects()
        if not ge_swept_ok:
            checks.append(check(
                "effect_is_blueprint", False,
                "GameplayEffect sweep is not working (could not see the engine "
                "GameplayEffect class in the unreal namespace); failing closed "
                "rather than passing on an empty sweep"))
        elif native_ges:
            checks.append(check(
                "effect_is_blueprint", False,
                "C++ UGameplayEffect subclass(es) present: %s — the period, "
                "duration, Health modifier and stacking policy this task grades "
                "are GameplayEffect properties, so a native effect puts the "
                "assessed behaviour in C++. The prompt says: do not add or "
                "modify any C++ source for this task" % native_ges))
        else:
            # CONJOINED with the positive requirement, exactly like
            # `resolved_pawn_is_blueprint` above, and for the same reason: this
            # is an ABSENCE check, so on its own an EMPTY submission satisfies
            # it vacuously and scores a point. That would weaken the stub guard,
            # which must be FAIL-on-empty rather than differs-from-reference
            # (the gp-gas-launch gold-leak lesson). Caught by
            # test_empty_submission_scores_zero the first time this check ran.
            checks.append(check(
                "effect_is_blueprint",
                bp_pawn_cls is not None,
                "no C++ UGameplayEffect subclass present; blueprint pawn=%s"
                % bp_pawn_path))
    except Exception as e:  # noqa: BLE001
        checks.append(check("effect_is_blueprint", False, repr(e)))

    emit(checks)


if __name__ == "__main__":
    main()
