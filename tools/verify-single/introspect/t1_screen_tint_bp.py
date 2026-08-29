"""L2-introspect script for ``t1-screen-tint-bp``.

Structural, READ-ONLY verification that the deliverable **really is Blueprint** —
the surface half of a bp/cpp pair whose behaviour half is graded, unchanged, by
``AScreenTintFunctionalTest``.

WHAT AN EXISTENCE CHECK WOULD MISS, and why this file is not one. "A Blueprint
exists under the task folder" is satisfied by a decorative Blueprint shipped
beside a C++ solve. The fixture resolves the graded actor as: the placed native
instance, UNLESS a Blueprint under ``/Game/Tasks`` derives from it
(``ACraftBenchFunctionalTest::SwapForGradedBlueprint``). So the question that
actually matters is *which surface did the run grade*, and the only way to answer
it structurally is to reproduce the fixture's own resolution and require the
answer to be Blueprint-generated. The four ``gp-*-bp`` graders learned this the
same way; see ``gp_glide_stamina_bp.py``'s ``resolved_pawn_is_blueprint`` block.

Asserts:

  * ``/Game/Tasks/t1-screen-tint-bp/`` exists and lists >= 1 asset;
  * exactly ONE Blueprint under ``/Game/Tasks`` has a ``GeneratedClass`` deriving
    from ``AScreenTintActor`` — two would make the fixture raise a
    HARNESS-PRECONDITION rather than grade, so two is a defect here too;
  * that Blueprint's generated class is what the fixture WOULD resolve, i.e. it
    is a strict subclass of the placed class and not the placed class itself;
  * NO native (C++) subclass of ``AScreenTintActor`` was delivered. Without this
    the checks above never ask which surface was graded: a native subclass is a
    C++ answer, and on a task whose actor is PLACED it would be the class the map
    instantiates. The scaffold class itself is exempt by exact path.

Deliberately NOT asserted here: anything about the vignette's value over time.
That is the L2 fixture's job, it is identical on both legs of the pair, and
duplicating it in a structural layer would let the two disagree.
"""

import json
import os
import sys

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

# Sibling import, the same mechanism the five other -bp graders use. A failure
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
TASK_DIR = "/Game/Tasks/t1-screen-tint-bp"

#: The substrate scaffold class the Blueprint must derive from. This is the class
#: the MAP places, which is exactly what the fixture's resolver compares against.
SCAFFOLD_CLASS_NAME = "ScreenTintActor"

#: Exempt from the "no native subclass" sweep, by EXACT /Script/ path rather than
#: by name — a name match would also exempt an agent class that happened to be
#: called the same thing in another module.
_SCAFFOLD_EXEMPT = ("/Script/ThirdPerson.ScreenTintActor",)


def emit(checks):
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)


def main():
    checks = []

    scaffold = bpl.resolve_native_class(SCAFFOLD_CLASS_NAME)
    if scaffold is None:
        # The verifier cannot see the class the whole task is defined against.
        # That is a harness fault, not a submission fault, so say so loudly and
        # do not emit a graded-looking verdict for the other checks.
        # A VERIFIER fault, not a submission fault: the grader cannot see the class
        # the task is defined against. Emitting a failed CHECK would score this
        # against the model. Raising instead kills the verdict channel, which the
        # L2I layer reports as status `error` -> HARNESS-ERROR (exit 7, NON-GRADED).
        raise RuntimeError(
            "HARNESS: could not resolve %s from the loaded game module; the "
            "verifier cannot tell what the Blueprint should derive from"
            % SCAFFOLD_CLASS_NAME)

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
    candidates = []
    _all_exists, all_task_assets = bpl.task_folder_assets("/Game/Tasks")
    for path in all_task_assets:
        gen = bpl.generated_class(path)
        if gen is None:
            continue
        if not bpl.derives_from(gen, scaffold, SCAFFOLD_CLASS_NAME):
            continue
        if str(gen.get_name()) == SCAFFOLD_CLASS_NAME:
            continue  # the placed class itself is not a submission
        # KNOWN DIVERGENCE, still open -- and it can only ever fail a CORRECT
        # answer, which is why it is recorded here instead of left to be
        # rediscovered. ResolveGradedBlueprintClass skips a CLASS_Abstract
        # candidate BEFORE it counts, so a submission shipping an abstract
        # intermediate plus one concrete Blueprint resolves to exactly ONE class
        # and is graded normally. This grader counts both, reports two, and FAILs
        # the count check below.
        #
        # The route to close it is NOT unknown: the sibling grader
        # `t1_mud_wade_bp.py::_is_abstract` reads
        # `UBlueprint::bGenerateAbstractClass` through
        # `get_editor_property("generate_abstract_class")` -- a
        # UPROPERTY(EditAnywhere) (`Blueprint.h:464`) that
        # `PropertyAccessUtil.cpp::CanGetPropertyValue` permits Python to read --
        # and PARTITIONS candidates into resolvable / skipped-abstract / unprobed
        # rather than counting them. That grader is covered by
        # `tests/test_introspect_mud_wade_bp.py`; this one has no test of its own
        # yet, and porting resolution logic into an untested grader is how a
        # verifier starts failing correct answers quietly. Port it WITH an offline
        # oracle, in that order.
        candidates.append(path)

    checks.append(bpl.check(
        "exactly_one_blueprint_answer", len(candidates) == 1,
        "%d Blueprint(s) under /Game/Tasks derive from %s%s"
        % (len(candidates), SCAFFOLD_CLASS_NAME,
           (": " + ", ".join(sorted(candidates))) if candidates else "")))

    # The surface question. A native subclass of the placed class is a C++ answer,
    # and on a placed-actor task it is what the map would instantiate — so its
    # presence means the run may have graded C++ no matter what Blueprint sits
    # beside it.
    offenders, swept_ok, _exempt_hit = bpl.native_subclasses(
        scaffold, SCAFFOLD_CLASS_NAME, _SCAFFOLD_EXEMPT)
    checks.append(bpl.check(
        "no_native_subclass_delivered", swept_ok and len(offenders) == 0,
        "sweep able to see the base class=%s; native subclasses of %s: %s" % (
            swept_ok, SCAFFOLD_CLASS_NAME,
            ", ".join(sorted(str(n) for n in offenders)) if offenders
            else "none")))

    # And the Blueprint that WOULD be resolved is the one in the task's own
    # folder, not merely somewhere under /Game/Tasks. Separate from the count
    # check so a misfiled answer reads as misfiled rather than as missing.
    in_own_folder = [p for p in candidates if p.startswith(TASK_DIR + "/")]
    checks.append(bpl.check(
        "answer_is_in_the_declared_folder",
        len(candidates) == 1 and len(in_own_folder) == 1,
        "of %d candidate(s), %d sit under %s"
        % (len(candidates), len(in_own_folder), TASK_DIR)))

    emit(checks)


if __name__ == "__main__":
    main()
