"""Shared pawn-shaped introspection for the bp-g2 `-bp` (Blueprint-deliverable)
twins.

A `-bp` twin shares its `-cpp` original's L2 fixture and committed `.umap`
verbatim. The only deltas are (a) the prompt mandates a BLUEPRINT deliverable
under `Content/Tasks/<id>-bp/`, (b) this L2I leg structurally asserts the
deliverable really IS Blueprint - the anti-gaming gate against solving the "BP
variant" in C++ - and (c) C++ decoy discrimination variants that try to defeat
(b). Everything in (b) that is not task-specific lives here.

Emits the `CRAFTBENCH-INTROSPECT-JSON` verdict block the L2-introspect layer
parses (`tools/verify-single/layers/INTROSPECT_CONTRACT.md`):

    CRAFTBENCH-INTROSPECT-JSON-START
    {"checks": [{"id": "<str>", "passed": <bool>, "detail": "<str>"}, ...]}
    CRAFTBENCH-INTROSPECT-JSON-END

Layer status is `pass` iff the block parses, has >= 1 check, and every check
passed; `fail` if any check is false; **`error`** (-> HARNESS-ERROR, exit 7,
NON-GRADED) if no parseable block is printed at all. That taxonomy is why every
check below is individually wrapped in try/except - one bad UE API name must
degrade to a single FAILED check with the exception in `detail`, never to an
aborted verdict - and equally why a breakage in THIS module (a syntax error, a
failed import) must NOT be caught and converted into a failing check: a
verifier-owned defect has to reach the `error` channel, never a graded FAIL
against the model.

WHY THE TWO ORIGINALS ARE DELIBERATELY LEFT ALONE
-------------------------------------------------
`gp_glide_stamina_bp.py` and `gp_poison_dot_stack_bp.py` still carry their own
copies of this logic and are NOT refactored onto this module. They are shipped
and graded (glide: `cb discriminate` 1/1 on a live runner 2026-07-17, reference
re-validated on the ThirdPerson substrate 2026-08-06; the `resolved_pawn_is_
blueprint` gate has a MEASURED false-PASS-before / FAIL-after record in
`tasks/bp/gp-glide-stamina-bp/discrimination/MATRIX.md`). Rewriting a live
grader buys nothing and risks a graded task, so the duplication is a deliberate
cost. Consequence to keep in view: **a fix made here does not reach them.** Two
divergences exist on purpose and are named where they occur below
(`GRANTED-ABILITY NATIVE HOLE`, `min_bp_abilities`).

HARD RULES INHERITED FROM THE CONTRACT
--------------------------------------
* READ-ONLY. Nothing here mutates an asset, a level, or the project.
* Anti-circularity: stock UE Python only (`EditorAssetLibrary`, reflection);
  never Aura's MCP tools.
* Identity by **pre-declared content path + derivation**, NEVER by asset name
  or class name - the agent may name its Blueprints anything.
* ASCII only in every `detail` string (repo law).

THE NATIVE SWEEP IS KEYED ON GIT-HEAD PROVENANCE, NOT PATH SHAPE
----------------------------------------------------------------
`resolved_pawn_is_blueprint` refuses ANY native (C++) subclass of the scaffold
pawn, exempting only classes that ship in the committed substrate at git HEAD,
enumerated as EXACT `/Script/<Module>.<Class>` paths in
`COMMITTED_THIRDPERSON_PAWN_SUBCLASSES` below.

A path-SHAPE exemption ("classes under a sibling task's scaffold folder are
fine") would re-open the exact hole this check exists to close: the runner
materializes the substrate from git HEAD and overlays the submission on top, so
agent C++ lands in the same writable module as the committed scaffolds, and the
committed decoy literally lives at
`tasks/bp/gp-glide-stamina-bp/discrimination/cpp-solve/Source/ThirdPerson/
GlidePawn.{h,cpp}` - i.e. under the same `Source/ThirdPerson/` prefix as the
scaffold itself. `bp-g2-scaleup-plan.md` I1.2 states this as a requirement, and
`gp-glide-stamina-bp/discrimination/MATRIX.md` records the MEASURED false PASS
from before the gate existed. Enumerating HEAD by exact path is the only key
available to a script running inside the graded editor: the submission overlay
is indistinguishable from the substrate on disk by the time the editor loads,
and a class's `ModuleRelativePath` metadata is path shape by another name.

Drift in the two possible directions, and why only one needs a guard:
  * HEAD GAINS a native scaffold subclass that is not listed -> the sweep
    reports it as a decoy and the check FAILs. Fail-CLOSED, which is the safe
    direction, and the FAIL detail names the class so the fix is one line here.
  * HEAD LOSES or RENAMES a listed class -> the entry is simply never matched.
    No hole opens (a renamed class is caught as an unlisted native), so no
    guard is warranted; a "listed class must be present" guard would only add a
    way to false-FAIL a conforming submission. The unmatched entries are still
    reported in the `detail` so the staleness is visible.

WHAT THIS MODULE DOES **NOT** COVER
-----------------------------------
The sweep is scaffold-PAWN shaped. A native `UAttributeSet`,
`UGameplayModMagnitudeCalculation` or `UGameplayEffect` subclass referenced
from a Blueprint pawn is NOT swept (`bp-g2-verifier-extensions.md` V2.1 says
the same of the shipped scripts). What IS covered, and is a divergence from the
two originals, is the `GRANTED-ABILITY NATIVE HOLE` below.

API notes (NOT live-validated on UE 5.8; each is probed defensively):
  * `EditorAssetLibrary.does_directory_exist` / `list_assets(dir, recursive)`.
  * `EditorAssetLibrary.load_blueprint_class(pkg)` -> the generated UClass
    (None / raises for a non-Blueprint asset). Fallback: `load_object(None,
    pkg + "_C")`.
  * Derivation: `MathLibrary.class_is_child_of`, then an isinstance probe on
    the CDO, then a super-chain walk by name. First route that answers wins.
  * `GrantedAbilities` is `EditAnywhere BlueprintReadWrite` on
    `ACraftBenchCharacter` (`TArray<TSubclassOf<UGameplayAbility>>`), read off
    the pawn CDO via `get_editor_property('granted_abilities')`. A
    Blueprint-generated class's `get_path_name()` starts with `/Game/`; a
    native one with `/Script/`.
  * UE 5.1+ renamed `SkeletalMesh` -> `SkeletalMeshAsset`; both are probed.

`unreal` is resolved LAZILY (`_ue()`), never bound at module import. Two
reasons: this module must import cleanly outside an editor for offline syntax /
oracle checks, and an offline test that swaps `sys.modules["unreal"]` between
legs would otherwise be graded against the FIRST leg's fake forever, because
this module - unlike a per-task script loaded by path - is cached in
`sys.modules`.
"""

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# The ThirdPerson substrate's agent-writable runtime module - the module that
# hosts the GAS scaffold AND anything an agent adds under Source/ThirdPerson/.
THIRDPERSON_MODULE = "ThirdPerson"

# The root scaffold pawn. Every bp-g2 GAS family derives from it (directly, or
# via the abstract health-first base), so sweeping ITS native subclasses covers
# every family with one rule.
SCAFFOLD_ROOT_CLASS = "CraftBenchCharacter"

# GIT-HEAD PROVENANCE LIST (see the module docstring). Native subclasses of
# SCAFFOLD_ROOT_CLASS that ship in UE-projects/ThirdPerson/ at HEAD and are
# therefore NOT agent work. Exact /Script/ paths only - never a prefix, never a
# folder rule.
#
# Enumerate with (from the repo root, against the COMMITTED tree):
#   git grep -n "public ACraftBenchCharacter\|public ACraftBenchBareCharacter" \
#       -- UE-projects/ThirdPerson/Source/ThirdPerson
# As of 2026-08-10 that is exactly one class:
#   CraftBenchBareCharacter.h:46  UCLASS(Abstract)  : public ACraftBenchCharacter
# It is ABSTRACT, so `ResolveAgentPawnClass` (CraftBenchPawnFunctionalTest.cpp)
# skips it as a CLASS_Abstract candidate and it can never be the resolved pawn
# a decoy would need to be. An agent cannot collide with the name (a duplicate
# UCLASS does not compile), so the exemption cannot be borrowed.
COMMITTED_THIRDPERSON_PAWN_SUBCLASSES = frozenset((
    "/Script/%s.CraftBenchBareCharacter" % THIRDPERSON_MODULE,
))

# The read-only visual-representation pool: the ThirdPerson substrate's own
# mannequin content. Pool-anchored on purpose - "some mesh exists" is gameable
# with an empty placeholder under the agent-writable path, while
# /Game/Characters/ is outside the writable sandbox and the agent cannot author
# into it. Mirrors the prompt's own instruction.
MANNEQUIN_POOL_PREFIX = "/Game/Characters/"


def _ue():
    """The live `unreal` module. Raises ImportError outside an editor.

    Deliberately re-imported per call rather than bound at module import: see
    the module docstring's last paragraph.
    """
    import unreal
    return unreal


# --------------------------------------------------------------------------- #
# verdict emission (INTROSPECT_CONTRACT.md)                                    #
# --------------------------------------------------------------------------- #

def check(cid, passed, detail=""):
    return {"id": cid, "passed": bool(passed), "detail": str(detail)}


def emit(checks):
    """Print the one verdict block, and mirror it to the UE log.

    stdout is authoritative (`layers/l2_introspect.py` parses the log text and
    takes the LAST block), so a failure to reach `unreal.log` is never fatal.
    """
    import json
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    try:
        unreal = _ue()
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)
    except Exception:  # noqa: BLE001 - offline, or no log sink; stdout stands
        pass


# --------------------------------------------------------------------------- #
# reflection primitives                                                        #
# --------------------------------------------------------------------------- #

def resolve_native_class(class_name, module=THIRDPERSON_MODULE):
    """The native UClass for `class_name`, or None.

    The project's game-module UCLASSes are reflected into the `unreal`
    namespace once the project loads; `load_object` on the `/Script/` path is
    the fallback. The module is a PARAMETER because hardcoding it is how the
    poison script's fallback went stale across the 2026-08-05 substrate move
    (the getattr route masked it for months).
    """
    try:
        unreal = _ue()
    except Exception:  # noqa: BLE001
        return None
    cls = getattr(unreal, class_name, None)
    if cls is not None:
        try:
            return cls.static_class()
        except Exception:  # noqa: BLE001 - some reflections ARE the UClass
            return cls
    try:
        return unreal.load_object(None, "/Script/%s.%s" % (module, class_name))
    except Exception:  # noqa: BLE001
        return None


def generated_class(asset_path):
    """The Blueprint asset's generated UClass, or None for a non-BP asset."""
    try:
        unreal = _ue()
    except Exception:  # noqa: BLE001
        return None
    try:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
        if cls is not None:
            return cls
    except Exception:  # noqa: BLE001 - fall through to the _C route
        pass
    try:
        return unreal.load_object(None, asset_path + "_C")
    except Exception:  # noqa: BLE001
        return None


def derives_from(cls, base_cls, base_name):
    """Three independent derivation probes; True on the first that answers."""
    if cls is None or base_cls is None:
        return False
    try:
        unreal = _ue()
    except Exception:  # noqa: BLE001
        return False
    try:
        if unreal.MathLibrary.class_is_child_of(cls, base_cls):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        cdo = unreal.get_default_object(cls)
        py_base = getattr(unreal, base_name, None)
        if py_base is not None and isinstance(cdo, py_base):
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


def task_folder_assets(task_dir):
    """`(exists, [object paths])` for the pre-declared task content folder."""
    unreal = _ue()
    exists = bool(unreal.EditorAssetLibrary.does_directory_exist(task_dir))
    if not exists:
        return False, []
    return True, list(unreal.EditorAssetLibrary.list_assets(task_dir, recursive=True) or [])


def find_bp_pawns(assets, base_cls, base_name):
    """`([(pawn_class, pawn_package_path), ...], [blueprint packages probed])`.

    EVERY Blueprint under the task folder whose generated class derives from
    `base_name`, in asset-registry order. Identity is derivation + the
    pre-declared folder, never the asset's name.
    """
    found = []
    probed = []
    for raw in assets:
        # list_assets returns object paths like /Game/.../BP_X.BP_X - strip the
        # .ObjectName suffix down to the package path load_* expects.
        path = str(raw).split(".")[0]
        cls = generated_class(path)
        if cls is None:
            continue
        probed.append(path)
        if derives_from(cls, base_cls, base_name):
            found.append((cls, path))
    return found, probed


def find_bp_pawn(assets, base_cls, base_name):
    """`(pawn_class, pawn_package_path, [blueprint packages probed])` — first match.

    Kept for callers that legitimately want any derived pawn. The graded checks
    use :func:`find_bp_pawns` instead: see the ordering note in ``run_checks``.
    """
    found, probed = find_bp_pawns(assets, base_cls, base_name)
    if not found:
        return None, None, probed
    return found[0][0], found[0][1], probed


def native_subclasses(base_cls, base_name, exempt_paths):
    """`(offenders, swept_ok, exemptions_matched)`.

    NATIVE (C++) subclasses of `base_cls` currently loaded, minus the exact
    `/Script/` paths in `exempt_paths` (the git-HEAD provenance list).

    Mirrors the fixture's own native-candidate sweep (`GetDerivedClasses`
    filtered to `ClassGeneratedBy == nullptr`): the game module's UCLASSes are
    reflected into the `unreal` namespace once the project loads, a NATIVE
    class's `get_path_name()` lives under `/Script/`, a Blueprint-generated one
    under `/Game/`.

    `swept_ok` is a FAIL-CLOSED self-test: the sweep must be able to see the
    base class itself. Without it the whole check would silently pass whenever
    the sweep returned nothing for an API reason - failing OPEN, which is the
    direction that silently re-opens the decoy hole on a future UE API change.
    """
    unreal = _ue()
    base_path = None
    try:
        base_path = base_cls.get_path_name()
    except Exception:  # noqa: BLE001
        base_path = None
    offenders = []
    matched = set()
    swept_ok = False
    for name in dir(unreal):
        if name.startswith("_"):
            continue
        try:
            cls = getattr(unreal, name).static_class()
            path = cls.get_path_name()
        except Exception:  # noqa: BLE001 - enums/structs/functions have no static_class
            continue
        if not path.startswith("/Script/"):
            continue
        if (base_path is not None and path == base_path) or name == base_name:
            swept_ok = True  # the sweep can see the base, so it is working
            continue
        if path in exempt_paths:
            matched.add(path)
            continue
        if derives_from(cls, base_cls, base_name):
            offenders.append(path)
    return sorted(offenders), swept_ok, matched


def granted_ability_paths(pawn_cls):
    """`(blueprint_generated, native)` class paths in the pawn CDO's
    `GrantedAbilities` array."""
    unreal = _ue()
    cdo = unreal.get_default_object(pawn_cls)
    granted = cdo.get_editor_property("granted_abilities")
    bp_paths = []
    native_paths = []
    for ability_cls in granted or []:
        if ability_cls is None:
            continue
        try:
            path = ability_cls.get_path_name()
        except Exception:  # noqa: BLE001
            continue
        if path.startswith("/Game/"):
            bp_paths.append(path)
        elif path.startswith("/Script/"):
            native_paths.append(path)
    return bp_paths, native_paths


def distinct_class_count(paths):
    """How many DISTINCT class paths a granted-ability list carries.

    DEDUP 2026-08-16 (decision Q7). Both gate sites counted the RAW list, so
    one Blueprint ability granted twice (`[GA_Damage, GA_Damage]`) satisfied
    `min_bp_abilities=2` - a gate measuring >= 1 while the spec docstring, the
    task's normative verifier section and its MATRIX all say DISTINCT. The
    GATE counts unique paths; callers keep the raw list for their `detail`
    strings so the printed evidence still shows the duplication a reviewer
    needs to see.

    WHY IT IS LOAD-BEARING, not cosmetic (established 2026-08-16 by an
    adversarial review that refuted the first write-up): the L2 twin does NOT
    catch the duplicate. `NumGrantedAbilitiesWithTag`
    (CraftBenchPawnFunctionalTest.cpp:389-403) counts per TAG and is
    class-agnostic, so ONE ability class carrying both `Ability.Damage` and
    `Ability.Heal` in its asset tags satisfies both per-tag gates - and,
    granted twice, it satisfied the old raw `len() >= 2` here as well. A single
    dual-tagged Blueprint ability was therefore a reachable FALSE-PASS route.

    THE REGRESSION IT INTRODUCES, stated because decision Q7 requires it to be:
    a pawn whose class defaults hold one ability twice while the second
    distinct ability is granted at RUNTIME now FAILs. Runtime grants are
    invisible here by construction - `granted_ability_paths` reads only
    `cdo.get_editor_property("granted_abilities")` - so that false-FAIL family
    already existed for fully-runtime-granting submissions (which read count 0).
    This narrows it rather than opening it, but it is a real verdict change and
    it belongs in the PR description, not only here.
    """
    return len(set(paths))


def _skeletal_mesh_of(comp):
    """The skeletal mesh asset a component holds, or None.

    UE 5.1+ renamed the property SkeletalMesh -> SkeletalMeshAsset; both are
    probed so an engine-side rename degrades to the next candidate, never to a
    false FAIL.
    """
    for prop in ("skeletal_mesh_asset", "skeletal_mesh"):
        try:
            skm = comp.get_editor_property(prop)
            if skm is not None:
                return skm
        except Exception:  # noqa: BLE001
            continue
    return None


def assigned_mesh_path(pawn_cls):
    """`(mesh_component_present, skeletal_mesh_asset_path_or_None)`.

    WIDENED 2026-08-15 (FALSE_FAIL). This read only the ACharacter-inherited
    `mesh` component, so a submission that satisfied the prompt -- "assign one of
    the provided mannequin skeletal meshes as your character's mesh" -- by adding
    its OWN skeletal mesh component was graded as having no mesh at all. The
    prompt never says WHICH component must carry it, and the fixture's own
    checkpoint-0 gate accepts any skeletal/static mesh component with a mesh
    assigned, so this was stricter than both the prompt and the L2 twin.

    The inherited component is still tried FIRST, so the ordinary case is
    unchanged and keeps its exact previous behaviour; the Blueprint's own
    component templates are only walked when that comes back empty.
    """
    unreal = _ue()
    cdo = unreal.get_default_object(pawn_cls)
    mesh_comp = None
    try:
        mesh_comp = cdo.get_editor_property("mesh")
    except Exception:  # noqa: BLE001
        mesh_comp = None
    if mesh_comp is not None:
        skm = _skeletal_mesh_of(mesh_comp)
        if skm is not None:
            return True, skm.get_path_name()

    # Fall back to every skeletal-mesh component the pawn owns, inherited or
    # author-added. get_components_by_class reads the CDO's component set, which
    # for a Blueprint class includes its own templates.
    found_comp = mesh_comp is not None
    try:
        comps = cdo.get_components_by_class(unreal.SkeletalMeshComponent) or []
    except Exception:  # noqa: BLE001
        comps = []
    for comp in comps:
        found_comp = True
        skm = _skeletal_mesh_of(comp)
        if skm is not None:
            return True, skm.get_path_name()
    return found_comp, None


# --------------------------------------------------------------------------- #
# the shared 5-check verdict                                                   #
# --------------------------------------------------------------------------- #

class BpVariantSpec(object):
    """Everything a `-bp` twin's L2I leg needs, and nothing task-behavioral.

    task_dir            pre-declared content folder of the deliverable
                        (`/Game/Tasks/<id>-bp`). NEVER a name pattern.
    pawn_base_class     class the BP pawn must DERIVE from - the family's task
                        base (`CraftBenchCharacter`, or the abstract
                        `CraftBenchBareCharacter` for the health-first family).
                        Matches the L2 fixture's own derivation gate.
    min_bp_abilities    how many DISTINCT Blueprint-generated ability classes
                        the pawn must grant. 2 for the two-operation
                        health-attribute-ops family, 1 elsewhere. DISTINCT is
                        enforced (`distinct_class_count`, 2026-08-16): one
                        class granted twice counts once, so a duplicate pair
                        no longer satisfies 2. Deliberately
                        NOT a tag check: the L2 fixture already gates the tags
                        (and which ability carries which), so re-deriving them
                        here would double-book one axis on an unvalidated API.
    sweep_base_class    class whose native subclasses are forbidden. Always the
                        ROOT scaffold, even when pawn_base_class is narrower -
                        for a `-bp` task ANY C++ subclass of the provided
                        character is already the violation, which is stricter
                        than the fixture's tag preference and is the rule a
                        human reviewer applies.
    committed_natives   the git-HEAD provenance exemption set (exact /Script/
                        paths). See the module docstring.
    """

    def __init__(self, task_dir, pawn_base_class, min_bp_abilities=1,
                 module=THIRDPERSON_MODULE,
                 sweep_base_class=SCAFFOLD_ROOT_CLASS,
                 committed_natives=COMMITTED_THIRDPERSON_PAWN_SUBCLASSES,
                 pool_prefix=MANNEQUIN_POOL_PREFIX):
        self.task_dir = task_dir
        self.pawn_base_class = pawn_base_class
        self.min_bp_abilities = int(min_bp_abilities)
        self.module = module
        self.sweep_base_class = sweep_base_class
        self.committed_natives = frozenset(committed_natives)
        self.pool_prefix = pool_prefix


def _pawn_satisfies(cls, spec):
    """Does this candidate pass BOTH per-pawn gates? Errors count as no."""
    try:
        bp_abilities, native_abilities = granted_ability_paths(cls)
        if (distinct_class_count(bp_abilities) < spec.min_bp_abilities
                or native_abilities):
            return False
    except Exception:  # noqa: BLE001
        return False
    try:
        _, skm_path = assigned_mesh_path(cls)
    except Exception:  # noqa: BLE001
        return False
    return bool(skm_path) and skm_path.startswith(spec.pool_prefix)


def _best_pawn(candidates, spec):
    """The candidate to grade: one that satisfies both gates, else the first.

    Falling back to the FIRST when none qualifies is deliberate — it preserves
    the previous behaviour exactly for a failing submission, so the detail line a
    reviewer reads on a FAIL still names a real pawn and its real shortfall
    rather than "none". Only a submission that HAS a conforming pawn changes
    outcome, which is precisely the false-FAIL being fixed.
    """
    if not candidates:
        return None, None
    for cls, path in candidates:
        if _pawn_satisfies(cls, spec):
            return cls, path
    return candidates[0]


def run_checks(spec):
    """The five shared checks, in verdict order. Returns the checks list.

    Every check is emitted on EVERY leg, reached or not, so the denominator is
    a constant: an empty submission scores 0/5 and no check can be satisfied by
    doing nothing. Each is individually try/except-wrapped so one bad UE API
    name degrades to one FAILED check with the exception in `detail`.
    """
    checks = []

    # --- task_folder_exists ------------------------------------------------
    assets = []
    try:
        exists, assets = task_folder_assets(spec.task_dir)
        checks.append(check(
            "task_folder_exists",
            bool(exists and assets),
            "%s: exists=%s, %d asset(s): %s"
            % (spec.task_dir, exists, len(assets), assets),
        ))
    except Exception as e:  # noqa: BLE001
        checks.append(check("task_folder_exists", False, repr(e)))

    # --- bp_pawn_present ---------------------------------------------------
    # ORDERING DEPENDENCE FIXED 2026-08-15 (FALSE_FAIL). This used to grade the
    # FIRST derived Blueprint in asset-registry order. A submission that leaves a
    # second derived pawn in the task folder -- a duplicate, an earlier attempt,
    # a base someone subclassed -- then had a coin-flip decide which one carried
    # the verdict, and registry order is not something the prompt lets an agent
    # control. Now every candidate is collected and the one that satisfies BOTH
    # downstream gates TOGETHER is graded, so the submission is judged on its
    # actual deliverable rather than on enumeration luck.
    #
    # This does not weaken the family's anti-gaming position: an extra pawn that
    # satisfies neither gate still fails, and `resolved_pawn_is_blueprint` below
    # is untouched -- it sweeps NATIVE subclasses, which is the hole that check
    # exists to close and which no amount of Blueprint choosing can open.
    pawn_base = resolve_native_class(spec.pawn_base_class, spec.module)
    bp_pawn_cls = None
    bp_pawn_path = None
    candidates = []
    try:
        candidates, probed = find_bp_pawns(assets, pawn_base, spec.pawn_base_class)
        bp_pawn_cls, bp_pawn_path = _best_pawn(candidates, spec)
        checks.append(check(
            "bp_pawn_present",
            bp_pawn_cls is not None,
            "base=%s; blueprint(s) probed=%s; derived=%s; graded pawn=%s"
            % (spec.pawn_base_class, probed,
               [p for _, p in candidates], bp_pawn_path),
        ))
    except Exception as e:  # noqa: BLE001
        checks.append(check("bp_pawn_present", False, repr(e)))

    # --- bp_pawn_grants_bp_ability -----------------------------------------
    # GRANTED-ABILITY NATIVE HOLE (a deliberate divergence from the two shipped
    # originals, which only COUNT the /Game/ entries). Counting alone passes a
    # submission that grants one Blueprint ability next to a C++ one that does
    # the real work: the BP pawn still wins L2 resolution, so
    # `resolved_pawn_is_blueprint` - which sweeps native PAWN subclasses - never
    # sees it, and the prompt's "Do not add or modify any C++ source for this
    # task" is violated with both layers green. This check therefore requires
    # BOTH: at least `min_bp_abilities` DISTINCT Blueprint-generated classes
    # AND zero native ones. DISTINCT is counted for real since 2026-08-16
    # (decision Q7): the raw len() passed one ability granted twice for min=2 -
    # see `distinct_class_count`. The detail string still prints the RAW list.
    # Safe against false FAILs: neither substrate commits a single
    # UGameplayAbility subclass, so every /Script/ entry found here is
    # agent-authored C++.
    if bp_pawn_cls is None:
        checks.append(check(
            "bp_pawn_grants_bp_ability", False, "no BP pawn resolved"))
    else:
        try:
            bp_abilities, native_abilities = granted_ability_paths(bp_pawn_cls)
            passed = (distinct_class_count(bp_abilities) >= spec.min_bp_abilities
                      and not native_abilities)
            checks.append(check(
                "bp_pawn_grants_bp_ability",
                passed,
                "BP-generated GrantedAbilities entries (need >= %d DISTINCT "
                "class paths; raw list shown): %s; "
                "NATIVE (C++) entries (must be none): %s"
                % (spec.min_bp_abilities, bp_abilities, native_abilities),
            ))
        except Exception as e:  # noqa: BLE001
            checks.append(check("bp_pawn_grants_bp_ability", False, repr(e)))

    # --- resolved_pawn_is_blueprint ----------------------------------------
    # The three checks above are EXISTENCE checks: they prove a conforming
    # Blueprint is PRESENT, never that it is the pawn L2 actually grades.
    # `ResolveAgentPawnClass` (CraftBenchPawnFunctionalTest.cpp, both
    # substrates carry the identical port) enumerates NATIVE subclasses BEFORE
    # Blueprint ones, so a C++ pawn shipped ALONGSIDE a conforming Blueprint
    # wins resolution: L2 grades the C++ solve while the checks above grade the
    # Blueprint, and the submission passes both layers while violating the
    # prompt. That hole is MEASURED, not argued - see
    # `gp-glide-stamina-bp/discrimination/MATRIX.md`, which records the PASS
    # from before this check existed against the FAIL after it.
    sweep_base = resolve_native_class(spec.sweep_base_class, spec.module)
    if sweep_base is None:
        checks.append(check(
            "resolved_pawn_is_blueprint", False,
            "could not resolve the %s scaffold class" % spec.sweep_base_class))
    else:
        try:
            offenders, swept_ok, matched = native_subclasses(
                sweep_base, spec.sweep_base_class, spec.committed_natives)
            unmatched = sorted(spec.committed_natives - matched)
            provenance = ("git-HEAD exemptions matched=%s unmatched=%s"
                          % (sorted(matched), unmatched))
            if not swept_ok:
                checks.append(check(
                    "resolved_pawn_is_blueprint", False,
                    "native-class sweep is not working (could not see %s in "
                    "the unreal namespace); failing closed rather than passing "
                    "on an empty sweep. %s"
                    % (spec.sweep_base_class, provenance)))
            elif offenders:
                checks.append(check(
                    "resolved_pawn_is_blueprint", False,
                    "C++ subclass(es) of %s present: %s - native candidates "
                    "are enumerated BEFORE Blueprint ones, so L2 would grade "
                    "the C++ pawn, not the Blueprint deliverable. Only classes "
                    "committed in the substrate at git HEAD are exempt. %s"
                    % (spec.sweep_base_class, offenders, provenance)))
            else:
                checks.append(check(
                    "resolved_pawn_is_blueprint",
                    bp_pawn_cls is not None,
                    "no agent-authored C++ subclass of %s; blueprint pawn=%s. %s"
                    % (spec.sweep_base_class, bp_pawn_path, provenance)))
        except Exception as e:  # noqa: BLE001
            checks.append(check("resolved_pawn_is_blueprint", False, repr(e)))

    # --- pawn_visibly_represented ------------------------------------------
    # The invisible-deliverable gate. MEASURED 2026-08-04 on the glide family:
    # all 9 matrix reps across 3 models shipped behaviorally-graded pawns with
    # NO mesh, and human review was only possible by instrumenting copies with
    # a debug cube. The mesh must be ASSIGNED (not None) and its asset path
    # must live under the read-only pool - see MANNEQUIN_POOL_PREFIX for why
    # the pool anchor rather than mere existence. This is the L2I twin of the
    # fixture's own checkpoint-0 visible-character gate; on these tasks it adds
    # the pool pin, not a new requirement.
    if bp_pawn_cls is None:
        checks.append(check("pawn_visibly_represented", False, "no BP pawn resolved"))
    else:
        try:
            comp_present, skm_path = assigned_mesh_path(bp_pawn_cls)
            checks.append(check(
                "pawn_visibly_represented",
                bool(skm_path) and skm_path.startswith(spec.pool_prefix),
                "pawn mesh component=%s; SkeletalMesh=%s (must be under %s)"
                % ("present" if comp_present else "MISSING",
                   skm_path, spec.pool_prefix),
            ))
        except Exception as e:  # noqa: BLE001
            checks.append(check("pawn_visibly_represented", False, repr(e)))

    return checks


def main(spec):
    """Run the shared checks for `spec` and emit the one verdict block."""
    emit(run_checks(spec))
