"""L2-introspect script for ``t1-mud-wade-bp``.

Structural, READ-ONLY verification that the deliverable **really is Blueprint** —
the surface half of a bp/cpp pair whose behaviour half is graded, unchanged, by
``AMudWadeFunctionalTest``.

WHAT AN EXISTENCE CHECK WOULD MISS, and why this file is not one. "A Blueprint
exists under the task folder" is satisfied by a decorative Blueprint shipped
beside a C++ solve. The fixture resolves the graded actors as: the two placed
native instances, UNLESS a Blueprint under ``/Game/Tasks`` derives from them
(``ACraftBenchFunctionalTest::ResolveGradedBlueprintClass``, driven here by
``SwapAllForGradedBlueprintRepossessing``). So the question that actually matters
is *which surface did the run grade*, and the only way to answer it structurally
is to reproduce the fixture's own resolution and require the answer to be
Blueprint-generated. The tint and the four ``gp-*-bp`` graders learned this the
same way; see ``t1_screen_tint_bp.py`` and
``gp_glide_stamina_bp.py``'s ``resolved_pawn_is_blueprint`` block.

ONE agent class, TWO instances — deliberately checked once. The lane places two
figures (a control placed in the map, and the pawn the game mode spawns at the
player start and player 0 drives) and BOTH are instances of the single class the
agent extends. ``SwapAllForGradedBlueprint`` resolves the Blueprint ONCE off the
first entry and REFUSES a mixed array, so there is exactly one resolution to
verify, not two. What the second instance adds is a failure mode, not a second
resolution: abstract candidates are SKIPPED by the resolver, so if EVERY candidate
is abstract it returns "no Blueprint delivered" and grades the untouched C++
scaffold for both figures — a silent full FAIL that looks exactly like a
submission that did nothing. That is why ``answer_is_instantiable`` is asserted by
name below rather than left implicit.

THE SKIP HAPPENS BEFORE THE AMBIGUITY CHECK, which is the one detail this file got
wrong on its first pass and is worth stating twice.
``ResolveGradedBlueprintClass`` (``CraftBenchFunctionalTest.cpp:682-696``)
``continue``s on ``CLASS_Abstract`` and only THEN tests whether it already has a
chosen class, so an abstract intermediate Blueprint shipped beside one concrete
Blueprint resolves to exactly one class and is graded normally — no
HARNESS-PRECONDITION. A checker that counts raw candidates therefore reports a
FAIL on a submission the harness graded correctly, and the model wears it. Every
count below is over the RESOLVABLE (non-abstract) set for that reason.

Deliberately NOT asserted here: that the resolved class is a Pawn. It would be a
check that cannot fail — the resolver already requires ``IsChildOf(PlacedClass)``
and the placed class is a Character, so every candidate is a Pawn by
construction. The repossession helper's "stand-in is not a pawn" precondition is
unreachable for this task, and a check that cannot tell right from wrong is not a
test.

Asserts (6, a CONSTANT denominator on every leg):

  * ``/Game/Tasks/t1-mud-wade-bp/`` exists and lists
    >= 1 asset;
  * exactly ONE Blueprint under ``/Game/Tasks`` has a NON-ABSTRACT
    ``GeneratedClass`` deriving from ``AMudHeroCharacter`` — two such would make
    the fixture raise a HARNESS-PRECONDITION rather than grade, so two is a
    defect here too, while an abstract one alongside is not (the resolver skips
    it first). A candidate whose abstract flag cannot be READ fails this check
    rather than being sorted into a bucket by guess;
  * not every candidate was skipped as abstract, i.e. the resolver will actually
    choose one instead of silently falling back to the C++ lane;
  * the Blueprint that WOULD be resolved sits under the task's own declared
    folder;
  * NO native (C++) subclass of ``AMudHeroCharacter`` was delivered. Without this
    the checks above never ask which surface was graded: a native subclass is a
    C++ answer, and on a task whose actor is PLACED it would be the class the map
    instantiates. The scaffold class itself is exempt by exact ``/Script/`` path,
    never by name;
  * no ``-bp``-named C++ task folder was created under ``Source/ThirdPerson/``.

A HOLE THIS SCRIPT DOES NOT CLOSE, stated rather than papered over. A submission
could edit the placed class IN PLACE (``Source/ThirdPerson/Tasks/<...>-cpp/
MudHeroCharacter.cpp`` is inside the substrate's writable roots) and ship a
trivial Blueprint subclass that inherits the C++ behaviour: the swap happens, the
graded class IS Blueprint-generated, no new native subclass exists, and every
check here passes on a C++ answer. Closing it needs a baseline the editor does not
have — the submission's diff against git HEAD — so it belongs to the sandbox /
fairness lane, not here. The same hole is open on every ``-bp`` leg in the repo
(``_bp_variant_lib.native_subclasses`` is the established defence and has the
same blind spot); it is recorded in ``task.md``'s NOT YET MEASURED section so the
next reader does not mistake this script for complete.

Also deliberately NOT asserted: anything about speed, the wade clip, or which
motion drives the pose. That is the L2 fixture's job, it is identical on both legs
of the pair, and duplicating it in a structural layer would let the two disagree.
"""

import json
import os
import sys

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

# Sibling import, the same mechanism the six other -bp graders use. A failure
# HERE is deliberately NOT caught: a missing verifier-owned library is a verifier
# defect and must kill the verdict channel (layer `error` -> HARNESS-ERROR, exit
# 7, NON-GRADED) rather than be scored against the model.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # no __file__ — cannot locate the lib
    _HERE = None
if _HERE and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _bp_variant_lib as bpl  # noqa: E402

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

#: Pre-declared content folder of the task's deliverable (NEVER name-based).
TASK_DIR = "/Game/Tasks/t1-mud-wade-bp"

#: The substrate scaffold class the Blueprint must derive from. This is the class
#: the MAP places and the game mode spawns, which is exactly what the fixture's
#: resolver compares against.
SCAFFOLD_CLASS_NAME = "MudHeroCharacter"

#: Exempt from the "no native subclass" sweep, by EXACT /Script/ path rather than
#: by name — a name match would also exempt an agent class that happened to be
#: called the same thing in another module.
_SCAFFOLD_EXEMPT = ("/Script/ThirdPerson.MudHeroCharacter",)

#: A C++ task folder the agent must NOT create: this leg's contract is Blueprint
#: assets only. Relative to the project root.
_FORBIDDEN_CPP_DIR = os.path.join(
    "Source", "ThirdPerson", "Tasks",
    "t1-mud-wade-bp")


def emit(checks):
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)


def _blueprint_asset(path):
    """The ``UBlueprint`` at ``path``, or None."""
    if unreal is None:
        return None
    try:
        obj = unreal.EditorAssetLibrary.load_asset(path)
    except Exception:  # noqa: BLE001 - a load failure is "not a Blueprint here"
        return None
    try:
        if isinstance(obj, unreal.Blueprint):
            return obj
    except Exception:  # noqa: BLE001 - no reflection for Blueprint in this boot
        return None
    return None


def _is_abstract(bp_asset):
    """``True`` / ``False`` / ``None`` (could not be probed).

    ``UBlueprint::bGenerateAbstractClass`` is ``UPROPERTY(EditAnywhere)``
    (``Blueprint.h:464``) and ``CPF_Edit`` alone permits a Python read
    (``PropertyAccessUtil.cpp::CanGetPropertyValue``), so this is a supported
    route rather than a reflection gamble. ``None`` is returned rather than
    guessed at, and the caller FAILS the check on it — no check may pass because
    a probe did not raise.
    """
    if bp_asset is None:
        return None
    try:
        return bool(bp_asset.get_editor_property("generate_abstract_class"))
    except Exception:  # noqa: BLE001
        return None


def _forbidden_cpp_dir_state():
    """``(present, probed)`` for the ``-bp``-named C++ task folder.

    ``probed`` is False when the project root itself could not be located, which
    is reported rather than silently read as "absent".
    """
    if unreal is None:
        return False, False
    try:
        project = str(unreal.Paths.convert_relative_path_to_full(
            unreal.Paths.project_dir()))
    except Exception:  # noqa: BLE001
        return False, False
    if not project or not os.path.isdir(project):
        return False, False
    return os.path.isdir(os.path.join(project, _FORBIDDEN_CPP_DIR)), True


def main():
    checks = []

    scaffold = bpl.resolve_native_class(SCAFFOLD_CLASS_NAME)
    if scaffold is None:
        # The verifier cannot see the class the whole task is defined against.
        # That is a harness fault, not a submission fault, so say so loudly and
        # do not emit a graded-looking verdict for the other checks.
        checks.append(bpl.check(
            "scaffold_class_resolvable", False,
            "could not resolve %s from the loaded game module; the verifier "
            "cannot tell what the Blueprint should derive from"
            % SCAFFOLD_CLASS_NAME))
        emit(checks)
        return

    # (exists, [object paths]) -- a TUPLE. Unpacked, because len() on the tuple
    # is 2 no matter what is in the folder, which is a check that cannot fail.
    folder_exists, assets = bpl.task_folder_assets(TASK_DIR)
    checks.append(bpl.check(
        "deliverable_folder_has_assets", folder_exists and len(assets) > 0,
        "folder exists=%s, %d asset(s) under %s" % (
            folder_exists, len(assets), TASK_DIR)))

    # Reproduce the fixture's resolution: every Blueprint under /Game/Tasks whose
    # generated class is a STRICT subclass of the placed class. Scoped to the
    # whole /Game/Tasks tree on purpose, matching the fixture — a Blueprint filed
    # in the wrong folder would still be picked up by the run, so it must be
    # visible to this check too rather than silently passing.
    # The resolver's filter, reproduced IN THE SAME ORDER it runs. This ordering
    # is load-bearing and was got wrong once: ResolveGradedBlueprintClass skips
    # CLASS_Abstract candidates BEFORE its two-candidate check
    # (CraftBenchFunctionalTest.cpp:682-696), so an abstract intermediate shipped
    # beside one concrete Blueprint resolves to exactly ONE class and is graded
    # normally. Counting abstract candidates toward ambiguity here would report a
    # FAIL on a submission the harness graded correctly -- a false FAIL charged to
    # the model. Partition, do not just count.
    candidates = []        # every Blueprint strict subclass, abstract or not
    resolvable = []        # what the resolver would actually consider
    skipped_abstract = []  # skipped by the resolver before it counts
    unprobed = []          # abstractness unreadable -> fail closed, never assumed
    _all_exists, all_task_assets = bpl.task_folder_assets("/Game/Tasks")
    for raw in all_task_assets:
        # list_assets returns object paths (/Game/.../BP_X.BP_X); strip down to
        # the package path the load_* routes expect.
        path = str(raw).split(".")[0]
        gen = bpl.generated_class(path)
        if gen is None:
            continue
        if not bpl.derives_from(gen, scaffold, SCAFFOLD_CLASS_NAME):
            continue
        if str(gen.get_name()) == SCAFFOLD_CLASS_NAME:
            continue  # the placed class itself is not a submission
        candidates.append(path)
        abstract = _is_abstract(_blueprint_asset(path))
        if abstract is None:
            unprobed.append(path)
        elif abstract:
            skipped_abstract.append(path)
        else:
            resolvable.append(path)

    # TWO or more RESOLVABLE candidates is what makes the fixture raise
    # HARNESS-PRECONDITION instead of grading; zero is the silent C++-lane
    # fallback. An unprobed candidate could be either, so it fails this check
    # rather than being guessed into one bucket.
    single = len(resolvable) == 1 and not unprobed
    checks.append(bpl.check(
        "exactly_one_blueprint_answer", single,
        "%d Blueprint(s) under /Game/Tasks derive from %s; %d resolvable%s, "
        "%d skipped as abstract%s, %d unprobed%s"
        % (len(candidates), SCAFFOLD_CLASS_NAME,
           len(resolvable),
           (" (" + ", ".join(sorted(resolvable)) + ")") if resolvable else "",
           len(skipped_abstract),
           (" (" + ", ".join(sorted(skipped_abstract)) + ")")
           if skipped_abstract else "",
           len(unprobed),
           (" (" + ", ".join(sorted(unprobed)) + ")") if unprobed else "")))

    # This is NOT a restatement of the count above: it fires on the ONE shape the
    # count cannot distinguish from an empty submission -- every candidate the
    # agent shipped was skipped as abstract, so the resolver returns nullptr, the
    # placed C++ scaffold is graded for BOTH figures, and the run reports a
    # complete behavioural FAIL indistinguishable from doing nothing. It PASSES
    # when an abstract intermediate sits beside a usable concrete answer, because
    # the fixture grades that submission fine.
    all_abstract = bool(candidates) and not resolvable and not unprobed
    if unprobed:
        detail = ("could not read generate_abstract_class on %s; "
                  "ABSTRACT_PROBE_FAILED" % ", ".join(sorted(unprobed)))
    elif all_abstract:
        detail = ("every candidate is marked abstract (%s), so the resolver "
                  "skips them all and grades the C++ scaffold; "
                  "ABSTRACT_FALLBACK_TO_CPP" % ", ".join(sorted(candidates)))
    elif not candidates:
        detail = ("no Blueprint candidate to judge; the surface failure is "
                  "reported by exactly_one_blueprint_answer")
    else:
        detail = ("%d resolvable candidate(s): %s"
                  % (len(resolvable), ", ".join(sorted(resolvable))))
    checks.append(bpl.check(
        "answer_is_instantiable", not unprobed and not all_abstract, detail))

    # And the Blueprint that WOULD be resolved is the one in the task's own
    # folder, not merely somewhere under /Game/Tasks. Separate from the count
    # check so a misfiled answer reads as misfiled rather than as missing, and
    # scoped to the RESOLVABLE set rather than to every candidate: an abstract
    # intermediate parked elsewhere under /Game/Tasks is not the graded answer,
    # so it must not make a correctly-filed answer read as misfiled.
    in_own_folder = [p for p in resolvable if p.startswith(TASK_DIR + "/")]
    checks.append(bpl.check(
        "answer_is_in_the_declared_folder",
        single and len(in_own_folder) == 1,
        "of %d resolvable candidate(s), %d sit under %s"
        % (len(resolvable), len(in_own_folder), TASK_DIR)))

    # THE SURFACE QUESTION. A native subclass of the placed class is a C++
    # answer, and on a placed-actor task it is what the map would instantiate --
    # so its presence means the run may have graded C++ no matter what Blueprint
    # sits beside it.
    #
    # (offenders, swept_ok, exemptions) -- a 3-TUPLE. Unpacked, because len() on
    # the tuple is 3 always, which would FAIL every correct submission. swept_ok
    # is the library's own fail-closed self-test: a sweep that cannot see the
    # base class proves nothing about subclasses of it.
    offenders, swept_ok, _exempt_hit = bpl.native_subclasses(
        scaffold, SCAFFOLD_CLASS_NAME, _SCAFFOLD_EXEMPT)
    checks.append(bpl.check(
        "no_native_subclass_delivered", swept_ok and len(offenders) == 0,
        "sweep able to see the base class=%s; native subclasses of %s: %s" % (
            swept_ok, SCAFFOLD_CLASS_NAME,
            ", ".join(sorted(str(n) for n in offenders)) if offenders
            else "none")))

    # The subclass sweep above only sees SUBCLASSES. A C++ answer routed through
    # anything else -- an actor component, a subsystem, a replacement game mode --
    # would not appear there, and this leg's contract is Blueprint assets only.
    # Cheap, deterministic, and it cannot fail a correct submission: nothing
    # legitimate creates a -bp-named C++ task folder.
    cpp_dir_present, cpp_dir_probed = _forbidden_cpp_dir_state()
    checks.append(bpl.check(
        "no_cpp_task_folder_for_this_leg",
        cpp_dir_probed and not cpp_dir_present,
        "probed=%s, present=%s at <project>/%s" % (
            cpp_dir_probed, cpp_dir_present,
            _FORBIDDEN_CPP_DIR.replace(os.sep, "/"))))

    emit(checks)


if __name__ == "__main__":
    main()
