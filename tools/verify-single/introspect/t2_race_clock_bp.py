"""L2-introspect script for ``t2-race-clock-bp``.

Structural, READ-ONLY verification that the deliverable **really is Blueprint** -
the surface half of a bp/cpp pair whose behaviour half is graded, unchanged, by
``ARaceTheClockFunctionalTest``.

WHY THIS TASK NEEDS **TWO** RESOLUTIONS, not one. Its agent delivers two
unrelated classes: the coin (``ARaceCoinBase``, placed seven times) and the round
marker (``ARaceRoundBase``, placed once). The fixture offers BOTH to the Blueprint
lane - ``SwapAllForGradedBlueprint`` over the coin set and
``SwapForGradedBlueprint`` for the round
(``RaceTheClockFunctionalTest.cpp:165-166``) - so a submission can be Blueprint on
one class and C++ on the other, and a single-class check would call that a
Blueprint answer. Each class is therefore resolved and swept separately, with its
own checks and its own detail line.

WHAT AN EXISTENCE CHECK WOULD MISS, and why this file is not one. "A Blueprint
exists under the task folder" is satisfied by a decorative Blueprint shipped
beside a C++ solve. The fixture resolves the graded actor as: the placed native
instance, UNLESS a Blueprint under ``/Game/Tasks`` derives from it
(``ACraftBenchFunctionalTest::ResolveGradedBlueprintClass``). So the question that
actually matters is *which surface did the run grade*, and the only way to answer
it structurally is to reproduce the fixture's own resolution and require the
answer to be Blueprint-generated. The four ``gp-*-bp`` graders learned this the
same way; see ``_bp_variant_lib.run_checks``'s ``resolved_pawn_is_blueprint``
block, which carries a MEASURED false-PASS-before / FAIL-after record.

Asserts, per agent class (coin, round), plus one shared folder check:

  * ``/Game/Tasks/t2-race-clock-bp/`` exists and lists >= 1 asset;
  * exactly ONE Blueprint under ``/Game/Tasks`` has a ``GeneratedClass`` that is a
    strict, **non-abstract** subclass of the placed class. That is the fixture's
    own filter, abstract skip included
    (``CraftBenchFunctionalTest.cpp:682-687``) - see THE ABSTRACT SKIP below.
    Two survivors make the fixture raise HARNESS-PRECONDITION rather than grade,
    so two is a defect here too;
  * that generated class is Blueprint-generated (its path lives under ``/Game/``,
    not ``/Script/``) - the surface question stated as directly as it can be;
  * it sits in the DECLARED folder, so a misfiled answer reads as misfiled rather
    than as missing;
  * NO native (C++) subclass of the placed class was delivered. Without this the
    checks above never ask which surface was graded: a native subclass is a C++
    answer, and on a task whose actors are PLACED it is what the map would
    instantiate. The scaffold classes themselves are exempt by EXACT ``/Script/``
    path, never by name.

THE ABSTRACT SKIP, because getting it wrong condemns a correct submission.
``ResolveGradedBlueprintClass`` skips any candidate carrying ``CLASS_Abstract``
BEFORE it counts, so a submission that factors an abstract Blueprint base plus one
concrete subclass under ``/Game/Tasks`` is resolved and graded cleanly by L2 - one
non-abstract candidate. A grader that counted both would report TWO and FAIL a
submission whose surface is Blueprint, i.e. the surface leg condemning a
Blueprint answer. ``_abstract_state`` therefore probes abstractness two
independent ways and drops the abstract candidates, exactly as the fixture does.

  Its unknown case is deliberately FAIL-OPEN (an unreadable candidate stays a
  candidate). That is the opposite of this file's usual bias, and the reason is
  that the defect being fixed here is a FALSE FAIL: tightening on an unreadable
  probe would re-create it, and treating unknown as concrete is byte-identical to
  the behaviour every other ``-bp`` grader has shipped with. The residual - probe
  blind AND the submission ships an abstract Blueprint - is narrower than the
  divergence it replaces, it is named in the check's own detail string
  (``abstract=?``), and it is recorded in the task spec's *Hidden invariants*.
  **The first graded run must confirm the probe answered**: a detail line reading
  ``abstract=?`` means the probe is blind and the divergence is back.

HARNESS FAULTS DO NOT GET A GRADED VERDICT. When this script cannot see the
scaffold classes, or cannot list ``/Game/Tasks`` at all, the thing that went wrong
is verifier-owned and nothing about the submission has been measured. Emitting a
well-formed verdict block with a failed check would score a module rename or a
load-order change against the MODEL, which is the one thing the repo's verdict
contract forbids. Such a fault therefore emits NO verdict block at all:
``l2_introspect.run_l2_introspect`` maps "no parseable verdict block" to layer
status ``error``, which ``run_task.harness_error_reasons`` predicate (5) turns into
HARNESS-ERROR / exit 7 - NON-GRADED, out of every pass-rate denominator. See
``harness_abort``. (The four other ``-bp`` graders, and ``t1_screen_tint_bp``
which this file was modelled on, still emit a graded FAIL there; that is a defect
on those files, filed rather than fixed here.)

THE ONE HOLE THIS CANNOT CLOSE, stated so nobody over-reads a green L2I. On this
task the C++ route is an IN-PLACE edit of the supplied scaffold - which is exactly
how the ``-cpp`` reference solves it (``RaceRoundBase.cpp`` /
``RaceCoinBase.cpp``). That creates no subclass, requires no new reflected member,
and the graded substrate on disk is indistinguishable from git HEAD by the time
this script's editor loads (the same reasoning as ``_bp_variant_lib``'s "keyed on
git-HEAD provenance, not path shape" note). A submission that edited the scaffold
in place AND shipped conforming Blueprints would be swapped in, graded, and read
green on both layers. This file therefore proves "the class the run graded was
Blueprint-generated, and no native subclass of either placed class was
delivered" - NOT "no C++ was written". Do not describe it as the latter.

Deliberately NOT asserted here: anything about the clock, the score, the coins or
the readouts. That is the L2 fixture's job, it is identical on both legs of the
pair, and duplicating it in a structural layer would let the two disagree.

NOTHING IN THIS FILE HAS BEEN RUN.
"""

import json
import os
import sys

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax/format checks
    unreal = None

# Sibling import, the same mechanism the other -bp graders use. A failure HERE is
# deliberately NOT caught: a missing verifier-owned library is a verifier defect
# and must kill the verdict channel (layer `error` -> HARNESS-ERROR, exit 7,
# NON-GRADED) rather than be scored against the model.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # no __file__ - cannot locate the lib
    _HERE = None
if _HERE and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _bp_variant_lib as bpl  # noqa: E402

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

#: Prefix for the non-verdict route. Deliberately NOT a member of the marker
#: family the layer's block parser looks for.
HARNESS_FAULT_PREFIX = "CRAFTBENCH-INTROSPECT-HARNESS-FAULT"

#: Pre-declared content folder of the task's deliverable (NEVER name-based).
TASK_DIR = "/Game/Tasks/t2-race-clock-bp"

#: The whole tree the fixture's resolver scans. A Blueprint filed in the wrong
#: folder would still be picked up by the run, so it must be visible here too
#: rather than silently passing.
TASKS_ROOT = "/Game/Tasks"

#: ``EClassFlags::CLASS_Abstract`` (``ObjectMacros.h:210``). The asset registry
#: publishes the GENERATED class's flag word as the ``ClassFlags`` tag
#: (``UBlueprint::GetAssetRegistryTags``, ``Blueprint.cpp:1111-1120``;
#: ``FBlueprintTags::ClassFlags`` is the literal string ``"ClassFlags"``,
#: ``BlueprintSupport.cpp:43``).
CLASS_ABSTRACT = 0x00000001

#: The two substrate scaffold classes the map PLACES, which is exactly what the
#: fixture's resolver compares against. `label` is only for the detail strings.
#:
#: Exemptions are EXACT /Script/ paths, never a name and never a prefix - a name
#: match would also exempt an agent class that happened to be called the same
#: thing in another module. Enumerate the committed natives with (from the repo
#: root, against the COMMITTED tree):
#:
#:   git grep -n "public ARaceCoinBase" -- UE-projects/ThirdPerson/Source/ThirdPerson
#:   git grep -n "public ARaceRoundBase" -- UE-projects/ThirdPerson/Source/ThirdPerson
#:
#: As of 2026-08-20 both are EMPTY: the substrate commits no subclass of either.
#: The scaffold class itself is listed anyway, so the exemption is explicit and
#: exact rather than resting on the library's own name fallback. Drift is
#: fail-CLOSED in the only direction that matters: if HEAD later gains a native
#: subclass that is not listed, the sweep reports it and the check FAILs.
AGENT_CLASSES = (
    {
        "key": "coin",
        "label": "the coin (placed seven times; SwapAllForGradedBlueprint)",
        "class_name": "RaceCoinBase",
        "exempt": ("/Script/ThirdPerson.RaceCoinBase",),
    },
    {
        "key": "round",
        "label": "the round marker (placed once; SwapForGradedBlueprint)",
        "class_name": "RaceRoundBase",
        "exempt": ("/Script/ThirdPerson.RaceRoundBase",),
    },
)


def emit(checks):
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        unreal.log(INTROSPECT_JSON_START)
        unreal.log(payload)
        unreal.log(INTROSPECT_JSON_END)


def harness_abort(reason):
    """Say loudly that the VERIFIER is broken, and emit NO verdict block.

    "No parseable verdict block" is the layer's `error` status
    (`l2_introspect.run_l2_introspect`), which routes to HARNESS-ERROR / exit 7
    and is excluded from every pass-rate denominator. A graded-looking FAIL here
    would charge a module rename or a load-order change to the model.
    """
    line = "%s: %s" % (HARNESS_FAULT_PREFIX, reason)
    print(line)
    try:
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 - nothing useful to do about it
        pass
    if unreal is not None:
        # WARNING, not error: this must be loud in the log without giving the
        # editor session a reason to report a failure of its own.
        unreal.log_warning(line)


def _defang(raw, limit=160):
    """Neutralize agent-chosen text before it reaches a check detail.

    Asset paths and class names are named by the AGENT. The layer's block regexes
    are end-of-line anchored so an embedded marker can no longer truncate the
    JSON, but per-grader defanging is still the house rule
    (`layers/INTROSPECT_CONTRACT.md`): cap the length and break the marker
    family. Cosmetic only - it can never move a verdict.
    """
    text = str(raw)
    text = text.replace("CRAFTBENCH", "CRAFT~BENCH")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


def _join(items, empty="none"):
    return ", ".join(_defang(i) for i in items) if items else empty


def _package_path(raw):
    """`list_assets` yields object paths (`/Game/A/BP.BP`); the load_* routes
    want the package path. `_bp_variant_lib.find_bp_pawns` strips it the same
    way."""
    return str(raw).split(".")[0]


def _is_blueprint_generated(cls):
    """True when `cls` is a Blueprint-generated class rather than a native one.

    A Blueprint-generated class's `get_path_name()` starts with `/Game/`; a
    native one with `/Script/`. Same rule `_bp_variant_lib.native_subclasses`
    uses, and the most direct structural statement of the surface question there
    is.
    """
    try:
        return str(cls.get_path_name()).startswith("/Game/")
    except Exception:  # noqa: BLE001 - an unreadable path is not a pass
        return False


def _abstract_state(object_path, package_path):
    """`True` / `False` / `None` - does the generated class carry CLASS_Abstract?

    `None` means neither probe could answer, or the two disagreed; the caller
    treats that as concrete (see THE ABSTRACT SKIP in the module docstring for why
    the unknown case fails OPEN here rather than closed).

    Probe 1 is the asset registry's `ClassFlags` tag, which is the flag word off
    the GENERATED class - the same bit the fixture tests. Probe 2 is the
    UBlueprint's own `bGenerateAbstractClass` (`Blueprint.h:465`), the authoring
    intent the Kismet compiler turns into that bit. They can disagree only on an
    asset saved between a toggle and a recompile; when they do, nothing here knows
    which surface the run would grade, so the answer is `None`.
    """
    if unreal is None:
        return None
    from_tag = None
    try:
        data = None
        # Both spellings, because `find_asset_data` wants an OBJECT path and
        # `list_assets` is the only thing that hands us one.
        for probe in (object_path, package_path):
            if not probe:
                continue
            try:
                found = unreal.EditorAssetLibrary.find_asset_data(probe)
            except Exception:  # noqa: BLE001 - try the other spelling
                continue
            if found is not None:
                data = found
                break
        if data is not None:
            raw = data.get_tag_value("ClassFlags")
            if raw is not None and str(raw).strip() != "":
                from_tag = (int(str(raw).strip()) & CLASS_ABSTRACT) != 0
    except Exception:  # noqa: BLE001
        from_tag = None
    from_prop = None
    try:
        asset = unreal.EditorAssetLibrary.load_asset(package_path)
        if asset is not None:
            from_prop = bool(asset.get_editor_property("generate_abstract_class"))
    except Exception:  # noqa: BLE001
        from_prop = None
    if from_tag is None:
        return from_prop
    if from_prop is None:
        return from_tag
    return from_tag if from_tag == from_prop else None


def _resolve_candidates(scaffold, class_name, all_task_assets):
    """Reproduce the fixture's resolution
    (`ACraftBenchFunctionalTest::ResolveGradedBlueprintClass`).

    Returns `(candidates, dropped_abstract, unknown_abstract)`, where `candidates`
    is `[(generated_class, package_path, abstract_state), ...]` - every Blueprint
    under /Game/Tasks whose generated class is a strict, non-abstract subclass of
    the placed class. `dropped_abstract` and `unknown_abstract` are package paths,
    carried only so the detail strings can say what happened.
    """
    found = []
    dropped = []
    unknown = []
    for raw in all_task_assets:
        object_path = str(raw)
        path = _package_path(object_path)
        gen = bpl.generated_class(path)
        if gen is None:
            continue
        if not bpl.derives_from(gen, scaffold, class_name):
            continue
        if str(gen.get_name()) == class_name:
            continue  # the placed class itself is not a submission
        state = _abstract_state(object_path, path)
        if state is True:
            dropped.append(path)   # the fixture skips it, so this must too
            continue
        if state is None:
            unknown.append(path)
        found.append((gen, path, state))
    return found, dropped, unknown


def _checks_for_class(spec, scaffold, resolved):
    """The four per-class checks. ALWAYS four, reached or not, so the
    denominator is a constant and an empty submission scores 0 of them."""
    key = spec["key"]
    class_name = spec["class_name"]
    label = spec["label"]
    candidates, dropped, unknown = resolved
    checks = []

    paths = sorted(p for _c, p, _s in candidates)
    # `abstract=` is the probe's own report card: `?` when some candidate's
    # abstractness could not be read, which means the fixture's abstract skip is
    # NOT being reproduced for it. See the docstring.
    probe_note = "abstract=%s" % ("?" if unknown else "read")
    skipped_note = ("; abstract candidate(s) skipped exactly as the fixture "
                    "skips them: %s" % _join(dropped)) if dropped else ""
    checks.append(bpl.check(
        "%s_answer_is_the_one_blueprint" % key,
        len(candidates) == 1,
        "%s: %d non-abstract Blueprint(s) under %s derive from %s (%s)%s%s"
        % (label, len(candidates), TASKS_ROOT, class_name, probe_note,
           skipped_note, (": " + _join(paths)) if paths else "")))

    # The surface question, stated directly on the class the fixture WOULD
    # resolve. Only meaningful when there is exactly one candidate: with two the
    # fixture raises HARNESS-PRECONDITION and grades nothing, and with none it
    # grades the placed C++.
    try:
        resolved_cls = candidates[0][0] if len(candidates) == 1 else None
        checks.append(bpl.check(
            "%s_answer_is_blueprint_generated" % key,
            resolved_cls is not None and _is_blueprint_generated(resolved_cls),
            "%s: resolved class=%s (must live under /Game/, i.e. be "
            "Blueprint-generated, not /Script/)"
            % (label,
               _defang(resolved_cls.get_path_name())
               if resolved_cls is not None else "none")))
    except Exception as e:  # noqa: BLE001
        checks.append(bpl.check(
            "%s_answer_is_blueprint_generated" % key, False, _defang(repr(e))))

    in_folder = [p for _c, p, _s in candidates if p.startswith(TASK_DIR + "/")]
    checks.append(bpl.check(
        "%s_answer_is_in_the_declared_folder" % key,
        len(candidates) == 1 and len(in_folder) == 1,
        "%s: of %d candidate(s), %d sit under %s"
        % (label, len(candidates), len(in_folder), TASK_DIR)))

    # A native subclass of the placed class is a C++ answer, and on a
    # placed-actor task it is what the map would instantiate - so its presence
    # means the run may have graded C++ no matter what Blueprint sits beside it.
    #
    # THE TUPLE. `native_subclasses` returns (offenders, swept_ok, exemptions).
    # len() of that tuple is 3 whatever the sweep found, so treating it as a list
    # makes "no native subclass" FAIL every correct submission. Unpack it, and
    # honour `swept_ok`: it is the library's own fail-closed self-test, and a
    # sweep that cannot see the base class proves nothing about subclasses of it.
    try:
        offenders, swept_ok, exemptions = bpl.native_subclasses(
            scaffold, class_name, frozenset(spec["exempt"]))
        checks.append(bpl.check(
            "no_native_%s_subclass_delivered" % key,
            swept_ok and len(offenders) == 0,
            "%s: sweep able to see %s=%s; native subclasses of it (must be "
            "none): %s; exact-path exemptions matched: %s"
            % (label, class_name, swept_ok, _join(sorted(offenders)),
               _join(sorted(exemptions)))))
    except Exception as e:  # noqa: BLE001
        checks.append(bpl.check(
            "no_native_%s_subclass_delivered" % key, False, _defang(repr(e))))

    return checks


def main():
    # Both scaffolds must be visible before anything else means anything. The
    # verifier not being able to see the classes the whole task is defined
    # against is a HARNESS fault, not a submission fault, so it takes the
    # no-verdict-block route rather than a graded FAIL.
    scaffolds = {}
    missing = []
    for spec in AGENT_CLASSES:
        cls = bpl.resolve_native_class(spec["class_name"])
        scaffolds[spec["key"]] = cls
        if cls is None:
            missing.append(spec["class_name"])
    if missing:
        harness_abort(
            "could not resolve %s from the loaded game module; the verifier "
            "cannot tell what the Blueprints should derive from, so nothing "
            "about this submission has been measured" % ", ".join(missing))
        return

    checks = [bpl.check(
        "scaffold_classes_resolvable", True,
        "resolved %s" % ", ".join(s["class_name"] for s in AGENT_CLASSES))]

    # (exists, [object paths]) -- a TUPLE. Unpacked, because len() on the tuple
    # is 2 no matter what is in the folder, which is a check that cannot fail.
    # A folder that does not EXIST is a legitimate (empty) submission and grades
    # as a failed check; a folder that cannot be PROBED is a harness fault.
    try:
        folder_exists, assets = bpl.task_folder_assets(TASK_DIR)
    except Exception as e:  # noqa: BLE001
        harness_abort("could not probe %s: %s" % (TASK_DIR, _defang(repr(e))))
        return
    checks.append(bpl.check(
        "deliverable_folder_has_assets",
        bool(folder_exists) and len(assets) > 0,
        "folder exists=%s, %d asset(s) under %s: %s"
        % (folder_exists, len(assets), TASK_DIR, _join(assets))))

    # Scoped to the whole /Game/Tasks tree on purpose, matching the fixture.
    # Swallowing a probe failure here would silently grade every submission as if
    # it shipped nothing, which is a harness fault wearing a graded FAIL.
    try:
        _all_exists, all_task_assets = bpl.task_folder_assets(TASKS_ROOT)
    except Exception as e:  # noqa: BLE001
        harness_abort("could not list %s, so the fixture's own resolution "
                      "cannot be reproduced: %s"
                      % (TASKS_ROOT, _defang(repr(e))))
        return

    for spec in AGENT_CLASSES:
        try:
            resolved = _resolve_candidates(
                scaffolds[spec["key"]], spec["class_name"], all_task_assets)
        except Exception as e:  # noqa: BLE001
            harness_abort(
                "the resolution sweep for %s raised, so which surface the run "
                "graded is unknown: %s"
                % (spec["class_name"], _defang(repr(e))))
            return
        checks.extend(_checks_for_class(spec, scaffolds[spec["key"]], resolved))

    emit(checks)


if __name__ == "__main__":
    main()
