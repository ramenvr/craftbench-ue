"""L2-introspect script for ``t3-gate-and-door-bp``.

Structural, READ-ONLY verification that the deliverable **really is Blueprint** — the
surface half of a bp/cpp pair whose behaviour half is graded, unchanged, by
``AOldDoorYardFunctionalTest`` (same map, same drive, same eleven named gates, same
``fps_legs``).

WHAT AN EXISTENCE CHECK WOULD MISS, and why this file is not one. "A Blueprint exists
under the task folder" is satisfied by a decorative Blueprint shipped beside a C++ solve.
The fixture resolves the graded actors as: the four placed native barriers, UNLESS a
Blueprint under ``/Game/Tasks`` derives from the class the map placed, in which case
``ACraftBenchFunctionalTest::SwapAllForGradedBlueprint`` replaces **all four** with
instances of it (`OldDoorYardFunctionalTest.cpp:384`). So the question that actually
matters is *which surface did the run grade*, and the only way to answer it structurally
is to reproduce the fixture's own resolution and require the answer to be
Blueprint-generated. The five other ``-bp`` graders learned this the same way; see
``gp_glide_stamina_bp.py``'s ``resolved_pawn_is_blueprint`` block and
``t1_screen_tint_bp.py``'s header.

THIS TASK HAS FOUR AGENT-FACING PLACED CLASSES AND THE FIXTURE SWAPS EXACTLY ONE, so
both resolutions are checked rather than one:

  * ``AYardBarrierActor`` — **the swapped class.** Its resolution IS the graded surface,
    so it must resolve to exactly one Blueprint, that Blueprint must be
    Blueprint-generated (a ``/Game/`` path, not ``/Script/``), it must sit in the
    declared folder, and no native subclass of it may be delivered.
  * ``AYardPadActor`` / ``AYardCrateActor`` / ``AGateLampActor`` — **placed and NOT
    swapped.** A Blueprint deriving from one of these is never instantiated by this
    fixture, so it changes nothing at all: the submission behaves exactly like the empty
    one while carrying an asset that looks like the whole answer. That is the Blueprint
    form of the brownfield failure (narrowing the pad's occupancy) and it is reported as
    a SHADOW asset rather than passing as "an asset exists". A *native* subclass of any
    of the three is a C++ answer and is swept for the same way as the barrier's.

Asserts:

  * ``/Game/Tasks/t3-gate-and-door-bp/`` exists and lists
    >= 1 asset;
  * exactly ONE Blueprint under ``/Game/Tasks`` has a ``GeneratedClass`` deriving from
    ``AYardBarrierActor`` — TWO would make the fixture raise a HARNESS-PRECONDITION
    rather than grade (`CraftBenchFunctionalTest.cpp:687-696`), so two is a defect here
    too, and reporting it structurally beats burning a non-graded run;
  * that Blueprint's generated class is what the fixture WOULD resolve: a strict subclass
    of the placed class, not the placed class itself, and **Blueprint-generated** (its
    class path is under ``/Game/``, never ``/Script/``);
  * it sits under the DECLARED folder — separate from the count check, because the
    fixture's resolver scans all of ``/Game/Tasks`` recursively and would grade a
    misfiled answer, so a misfiled answer must read as misfiled and not as missing;
  * NO native (C++) subclass of ``AYardBarrierActor`` was delivered. Without this the
    checks above never ask which surface was graded: a native subclass is a C++ answer,
    and on a task whose actor is PLACED it would be the class the map instantiates. The
    scaffold class itself is exempt by EXACT ``/Script/`` path, never by name — a name
    match would also exempt an agent class that happened to be called the same thing in
    another module;
  * NO native subclass of the pad, the crate or the lamp either, and no Blueprint
    shadowing any of the three.

KNOWN LIMITATION, recorded rather than papered over: L2I cannot see an **in-place edit**
of a scaffold ``.cpp``. The ``-cpp`` reference solves this task by editing
``YardBarrierActor.cpp`` rather than by subclassing anything, so the cheapest surface
violation on this leg — edit the same file, ship a Blueprint that does nothing — leaves
no new class for the sweep to find. The sweeps above catch a NEW native class; a modified
scaffold is caught by the submission diff and by human review of the deliverable, not
here. Do not read a green verdict from this script as "no C++ was written".

WHY THAT CANNOT BE CLOSED HERE, so the next reader does not try. The runner DOES know the
submission's file list (``run_task.py:2288`` builds ``submitted_rel_files`` from the
sandbox's accepted paths, and ``:2300`` already classifies compile inputs by extension for
``--lite``), but the list handed to this layer is filtered to ``Content/`` packages first
(``layers/l2_introspect.py:409-410`` keeps only entries with a ``content_package_path``),
so a submitted ``.cpp`` is not visible from inside this script by any route. Closing it
means passing the non-asset accepted paths through to the introspect layer — a runner
change, tracked outside this file. Three sentences in ``task.md`` used to assert the
contract WAS checked, one of them inside ``## Workspace state pre-task`` (i.e. read by the
model under test); they were corrected on 2026-08-20 to match what this file actually
does.

Deliberately NOT asserted here: anything about a panel's pose, a lamp's light, or which
pair a gate is cut for. That is the L2 fixture's job, it is identical on both legs of the
pair, and duplicating it in a structural layer would let the two disagree.

NOTE ON THE PAIR TUPLES, which cost a false FAIL once already. Two ``_bp_variant_lib``
helpers return TUPLES: ``task_folder_assets(dir) -> (exists, [paths])`` and
``native_subclasses(base, name, exempt) -> (offenders, swept_ok, exemptions)``. Using
either as a list is a silent disaster in BOTH directions — ``len()`` of the 2-tuple is 2
whatever the folder holds, so an existence check PASSES on an empty folder (a check that
cannot fail), and ``len()`` of the 3-tuple is 3 always, so a "no native subclass" check
FAILS every correct submission. Both are unpacked below, and ``swept_ok`` is honoured
because it is the library's own fail-closed self-test: a sweep that cannot see the base
class proves nothing about subclasses of it.
"""

import json
import os
import sys

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

# Sibling import, the same mechanism the other -bp graders use. A failure HERE is
# deliberately NOT caught: a missing verifier-owned library is a verifier defect and must
# kill the verdict channel (layer `error` -> HARNESS-ERROR, exit 7, NON-GRADED) rather
# than be scored against the model.
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
TASK_DIR = "/Game/Tasks/t3-gate-and-door-bp"

#: The whole /Game/Tasks tree, scoped to match the FIXTURE's own resolver: a Blueprint
#: filed in the wrong folder would still be picked up by the run, so it must be visible
#: to this check too rather than silently passing.
ALL_TASKS_DIR = "/Game/Tasks"

#: The substrate scaffold class the MAP places and the FIXTURE SWAPS. Its resolution is
#: the graded surface.
GRADED_SCAFFOLD = "YardBarrierActor"

#: Placed by the map, NOT swapped by this fixture. A Blueprint deriving from one of these
#: is never instantiated; a native subclass of one is a C++ answer.
UNSWAPPED_SCAFFOLDS = ("YardPadActor", "YardCrateActor", "GateLampActor")

#: Exempt from the "no native subclass" sweeps, by EXACT /Script/ path rather than by
#: name. One entry per scaffold class, because each sweep exempts only its own base.
_EXEMPT_BY_CLASS = {
    "YardBarrierActor": ("/Script/ThirdPerson.YardBarrierActor",),
    "YardPadActor": ("/Script/ThirdPerson.YardPadActor",),
    "YardCrateActor": ("/Script/ThirdPerson.YardCrateActor",),
    "GateLampActor": ("/Script/ThirdPerson.GateLampActor",),
}


def emit(checks):
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)


def _class_path(cls):
    """`cls.get_path_name()` or None. Never raises: a missing API must degrade to one
    failed check with the reason in `detail`, never to an aborted verdict."""
    try:
        return str(cls.get_path_name())
    except Exception:  # noqa: BLE001
        return None


def _blueprint_subclasses(assets, base_cls, base_name):
    """Every asset path under `assets` whose generated class is a STRICT subclass of
    `base_cls`, paired with that class. Reproduces the fixture's resolver."""
    out = []
    for path in assets:
        try:
            gen = bpl.generated_class(path)
        except Exception:  # noqa: BLE001
            continue
        if gen is None:
            continue
        if not bpl.derives_from(gen, base_cls, base_name):
            continue
        try:
            if str(gen.get_name()) == base_name:
                continue  # the placed class itself is not a submission
        except Exception:  # noqa: BLE001
            pass
        out.append((path, gen))
    return out


def _sweep_native(base_cls, base_name):
    """`(offenders, swept_ok)` for one scaffold class, exceptions folded into a
    failed sweep rather than an aborted verdict."""
    try:
        offenders, swept_ok, _exempt_hit = bpl.native_subclasses(
            base_cls, base_name, _EXEMPT_BY_CLASS.get(base_name, ()))
        return [str(n) for n in offenders], bool(swept_ok)
    except Exception as exc:  # noqa: BLE001
        return ["<sweep raised: %s>" % exc], False


#: ---------------------------------------------------------------------------------
#: BLOCKED, 2026-08-20. Set to False in the SAME change that fixes the surface swap.
#: ---------------------------------------------------------------------------------
#: This leg cannot reach a graded verdict, and the reason is in the harness, not in the
#: recipe or in this script. ``ACraftBenchFunctionalTest::SwapAllForGradedBlueprint``
#: (CraftBenchFunctionalTest.cpp:735-798) carries the placed actor's TRANSFORM and TAGS
#: across the swap and nothing else, so on the Blueprint lane:
#:
#:   * each pad's ``AnsweredBarrier`` and each lamp's ``LampBarrier``
#:     (EditInstanceOnly AActor*) still point at the DESTROYED placed barrier, which
#:     trips two fixture staging exits (OldDoorYardFunctionalTest.cpp:604, :653);
#:   * each barrier's per-instance ``CutForFirstName`` / ``CutForSecondName`` collapse to
#:     the Blueprint's class defaults ``(None, None)``, which trips a third (:1316);
#:   * and past all three, the stand-in's own ``BeginPlay`` fills ``Pads`` / ``Lamps`` by
#:     scanning for ``AnsweredBarrier == this`` (YardBarrierActor.cpp:150-168) and finds
#:     NOTHING — so a CORRECT submission would grade FAIL because the old door can never
#:     open. That last one is the outcome this guard exists to prevent: L2's own staging
#:     exits are already non-graded, but a PARTIAL swap fix that repairs the staging and
#:     not the spawn ordering would stage cleanly and then grade a correct answer FAIL.
#:
#: HOW THE GUARD WORKS, and why it is not a failed check. It prints a diagnostic and
#: returns WITHOUT emitting a verdict block. layers/l2_introspect.py reads that as status
#: ``error`` ("the verdict channel produced nothing to read"), and
#: run_task.harness_error_reasons predicate (5) turns it into exit 7 /
#: ``overall: "harness-error"``, which adapters.base.GRADED_VERDICTS excludes from every
#: pass-rate denominator. Emitting ``{"passed": false}`` checks instead would be a GRADED
#: FAIL, i.e. blaming the model for a harness gap — the thing the verdict contract exists
#: to forbid. This is the contract's non-graded channel used for exactly what it is for.
#:
#: TO LIFT: fix the swap so it (a) copies the placed instance's editable UPROPERTY values
#: onto the stand-in, (b) re-points every inbound ``AActor*`` reference in the world from
#: the placed actor to its stand-in, and (c) does both BEFORE the stand-in's BeginPlay
#: runs (bDeferConstruction + FinishSpawningActor). Then set BLOCKED = False here, drop
#: the banner from task.md, and run the discrimination that has never been run.
#: LIFTED 2026-08-23. All three conditions above are met in
#: ``SwapAllForGradedBlueprint`` (CraftBenchFunctionalTest.cpp:859-923) — verified
#: against that function specifically, not just the single-actor path, because the
#: warning above is precisely about a partial fix:
#:   (a) `SpawnStandInFor` -> `CopyPropertiesForUnrelatedObjects` carries the
#:       placed instance's editable UPROPERTY values;
#:   (b) `RepointReferencesTo(Placed, Spawned)` re-points every inbound AActor*;
#:   (c) TWO PASSES — the first builds, wires and destroys each placed actor into
#:       `Pending`; only the second calls `FinishStandIn`, so no stand-in's
#:       BeginPlay runs until every stand-in in the set is wired. That is the
#:       `bDeferConstruction` + deferred `FinishSpawning` ordering this guard
#:       required.
#: The same lane now discriminates on `t1-screen-tint-bp` end to
#: end, which is independent evidence the single-actor half works.
BLOCKED = False

BLOCKED_REASON = (
    "t3-gate-and-door-bp is BLOCKED: the surface swap "
    "carries only transform+tags, so this yard's per-instance property values and "
    "inter-actor instance references do not survive it. A perfect Blueprint submission "
    "cannot reach a graded verdict (three fixture HARNESS-PRECONDITION exits, then "
    "empty Pads/Lamps on every stand-in). Emitting NO verdict block on purpose: that is "
    "layer status 'error' -> exit 7 harness-error -> excluded from every denominator, "
    "which is the correct verdict for a harness gap and is NOT a grade of the "
    "submission. Fix ACraftBenchFunctionalTest::SwapAllForGradedBlueprint, then set "
    "BLOCKED = False in this file. See task.md's banner for the line cites."
)


def main():
    if BLOCKED:
        # Deliberately NO verdict block. See BLOCKED above: suppressing the block is the
        # contract's non-graded channel, and it is the only mechanism inside this task's
        # remit that can stop a run. A failed check here would score a harness gap
        # against the model instead.
        print("CRAFTBENCH-INTROSPECT-BLOCKED")
        print(BLOCKED_REASON)
        if unreal is not None:
            unreal.log_warning("CRAFTBENCH-INTROSPECT-BLOCKED")
            unreal.log_warning(BLOCKED_REASON)
        return

    checks = []

    scaffold = bpl.resolve_native_class(GRADED_SCAFFOLD)
    if scaffold is None:
        # The verifier cannot see the class the whole task is defined against. That is a
        # harness fault, not a submission fault, so say so loudly and do not emit a
        # graded-looking verdict for the other checks.
        checks.append(bpl.check(
            "scaffold_class_resolvable", False,
            "could not resolve %s from the loaded game module; the verifier cannot "
            "tell what the Blueprint should derive from" % GRADED_SCAFFOLD))
        emit(checks)
        return

    # (exists, [object paths]) -- a TUPLE. Unpacked, because len() on the tuple is 2 no
    # matter what is in the folder, which is a check that cannot fail.
    folder_exists, assets = bpl.task_folder_assets(TASK_DIR)
    checks.append(bpl.check(
        "deliverable_folder_has_assets", folder_exists and len(assets) > 0,
        "folder exists=%s, %d asset(s) under %s" % (
            folder_exists, len(assets), TASK_DIR)))

    # Reproduce the fixture's resolution over the WHOLE /Game/Tasks tree, matching the
    # resolver's own recursive scope.
    _all_exists, all_task_assets = bpl.task_folder_assets(ALL_TASKS_DIR)
    candidates = _blueprint_subclasses(all_task_assets, scaffold, GRADED_SCAFFOLD)
    candidate_paths = [p for p, _c in candidates]

    checks.append(bpl.check(
        "exactly_one_blueprint_answer", len(candidates) == 1,
        "%d Blueprint(s) under %s derive from %s%s"
        % (len(candidates), ALL_TASKS_DIR, GRADED_SCAFFOLD,
           (": " + ", ".join(sorted(candidate_paths))) if candidate_paths else "")))

    # THE SURFACE QUESTION, made explicit rather than inferred from the count: the class
    # the fixture WOULD resolve has to be Blueprint-generated. A Blueprint-generated
    # class lives under /Game/; a native one under /Script/.
    resolved_path = None
    resolved_is_bp = False
    if len(candidates) == 1:
        resolved_path = _class_path(candidates[0][1])
        resolved_is_bp = bool(resolved_path and resolved_path.startswith("/Game/"))
    checks.append(bpl.check(
        "resolved_barrier_class_is_blueprint_generated", resolved_is_bp,
        "the class the fixture would swap all four barriers to is %s"
        % (resolved_path if resolved_path is not None
           else "unresolvable (no single Blueprint candidate)")))

    # And it must be the one in the task's own folder. Separate from the count check so a
    # misfiled answer reads as misfiled rather than as missing.
    in_own_folder = [p for p in candidate_paths if p.startswith(TASK_DIR + "/")]
    checks.append(bpl.check(
        "answer_is_in_the_declared_folder",
        len(candidates) == 1 and len(in_own_folder) == 1,
        "of %d candidate(s), %d sit under %s"
        % (len(candidates), len(in_own_folder), TASK_DIR)))

    # (offenders, swept_ok, exemptions) -- a 3-TUPLE. Unpacked, because len() on the
    # tuple is 3 ALWAYS, so a length test would FAIL every correct submission. swept_ok
    # is honoured: a sweep that cannot see the base class proves nothing about subclasses
    # of it, so it must read as a failure and not as a clean result.
    offenders, swept_ok = _sweep_native(scaffold, GRADED_SCAFFOLD)
    checks.append(bpl.check(
        "no_native_subclass_of_the_barrier", swept_ok and len(offenders) == 0,
        "sweep able to see the base class=%s; native subclasses of %s: %s" % (
            swept_ok, GRADED_SCAFFOLD,
            ", ".join(sorted(offenders)) if offenders else "none")))

    # ---- the three PLACED-BUT-NOT-SWAPPED classes -------------------------------
    # A Blueprint deriving from one of these is never instantiated by this fixture, so it
    # is a silent no-op that looks like the whole answer; a NATIVE subclass of one is a
    # C++ answer on a leg whose contract is Blueprint-only.
    shadow_bps = []
    unswept = []
    native_offenders = []
    for name in UNSWAPPED_SCAFFOLDS:
        base = bpl.resolve_native_class(name)
        if base is None:
            # Fail CLOSED: an unresolvable base means these two checks proved nothing.
            unswept.append("%s (unresolvable)" % name)
            continue
        for path, _gen in _blueprint_subclasses(all_task_assets, base, name):
            shadow_bps.append("%s -> %s" % (path, name))
        offs, ok = _sweep_native(base, name)
        if not ok:
            unswept.append(name)
        native_offenders.extend("%s (%s)" % (o, name) for o in offs)

    checks.append(bpl.check(
        "no_blueprint_shadows_an_unswapped_placed_class",
        len(shadow_bps) == 0 and len(unswept) == 0,
        "shadow Blueprint(s): %s; class(es) the sweep could not cover: %s" % (
            ", ".join(sorted(shadow_bps)) if shadow_bps else "none",
            ", ".join(sorted(unswept)) if unswept else "none")))

    checks.append(bpl.check(
        "no_native_subclass_of_the_pad_crate_or_lamp",
        len(native_offenders) == 0 and len(unswept) == 0,
        "native subclasses: %s; class(es) the sweep could not cover: %s" % (
            ", ".join(sorted(native_offenders)) if native_offenders else "none",
            ", ".join(sorted(unswept)) if unswept else "none")))

    emit(checks)


if __name__ == "__main__":
    main()
