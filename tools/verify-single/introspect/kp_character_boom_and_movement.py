"""L2I grader — kp-character-boom-and-movement.

Grades a Character-derived Blueprint carrying a named camera rig and three
CharacterMovement values.

WHY THE NUMERICS ARE THE DISCRIMINATOR AND THE HIERARCHY IS NOT (probed
2026-08-14, before this grader was written). The substrate's shipped
`BP_ThirdPersonCharacter` ALREADY has a `CameraBoom` -> `FollowCamera`
hierarchy, so "duplicate the stock character" satisfies any structural check on
its own. It also already has `orient_rotation_to_movement = True`, which is why
that property is NOT graded here — it would be a dead gate, passing at baseline.

What the stock character does not have is 900 / 700 / 1024; it ships
500 / 500 / 2048. So the movement values are the only facts a duplicate cannot
inherit, and they carry the discrimination. The task's prompt is written to
match: it asks for a character with this rig and these values, and does NOT
claim to grade "authored from scratch", because that is not gradable — a
duplicate has a hierarchy too.

TWO READBACK TRAPS, both measured and both live in this file:

  * COMPONENT NAMES COME BACK SUFFIXED. A component the agent names `TaskCam`
    reads back as `TaskCam_GEN_VARIABLE`. An exact-name comparison would FAIL
    conforming work — the F5 shape — so every name match below is on the STEM.
  * THE READBACK INCLUDES INHERITED COMPONENTS. `CollisionCylinder`, `Arrow`
    and `CharacterMesh0` come from `ACharacter` and are present in every
    submission, including an empty one. So nothing here counts components; the
    named ones are looked up by stem, and a count-based check would have been
    grading the parent class rather than the agent.

The parent class is read from the generated class's superclass, NOT from
`bp.get_editor_property("parent_class")` — that raises (measured; it is the R24
spike's single FAIL).
"""
import json
import sys

try:
    import unreal
except ImportError:
    unreal = None

TASK_ID = "kp-character-boom-and-movement"
DIR = "/Game/Tasks/" + TASK_ID
BP_NAME = "BP_TaskChar"
BP_PATH = DIR + "/" + BP_NAME

# Disclosed verbatim in the prompt.
BOOM_STEM = "TaskBoom"
CAM_STEM = "TaskCam"
WANTED_MOVEMENT = (
    ("max_walk_speed", 900.0),
    ("jump_z_velocity", 700.0),
    ("max_acceleration", 1024.0),
)

START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"

CHECK_IDS = (
    "blueprint_present",
    "derives_from_character",
    "boom_component_present",
    "camera_parented_to_boom",
    "movement_values_exact",
    "movement_untouched_defaults_absent",
)

UNCREDITED_TOKENS = (
    "CHARRIG_NO_UNREAL",
    "CHARRIG_LOAD_ERROR",
    "CHARRIG_SUBSYSTEM_ERROR",
    "CHARRIG_HIERARCHY_READ_ERROR",
    "CHARRIG_CDO_READ_ERROR",
)

_MARKER_BITS = ("CRAFTBENCH-INTROSPECT-JSON", "CRAFTBENCH-ASSET-INTEGRITY-JSON")


def _defang(text, cap=300):
    s = str(text)
    for bit in _MARKER_BITS:
        s = s.replace(bit, "~redacted~")
    return " ".join(s.split())[:cap]


def check(cid, passed, detail):
    return {"id": cid, "passed": bool(passed), "detail": _defang(detail)}


def _stem(name):
    """`TaskCam_GEN_VARIABLE` -> `TaskCam`. See the module docstring."""
    return str(name).split("_GEN_VARIABLE")[0]


def _parent_stem(data):
    """The attach-parent's name stem for one subobject, or None.

    DEREFERENCES the parent handle. It does NOT compare handles, and that is
    the whole point of this function existing separately.

    THE BUG THIS REPLACES (caught in review before this task ever graded a
    submission, and it would have made the task unwinnable). The first cut built
    ``{str(handle): stem}`` from the gathered handles and looked the parent up
    as ``by_handle[str(get_parent_handle(d))]``. That cannot work, for three
    reasons each sufficient on its own:

      1. ``GetParentHandle`` is a void-with-out-param UFUNCTION
         (``SubobjectDataBlueprintFunctionLibrary.h:50``), so Python
         materializes a BRAND-NEW ``SubobjectDataHandle`` wrapper — never one of
         the objects already in the gathered list.
      2. UE's struct ``__str__`` is
         ``"<Struct '%s' (%p) %s>"`` with the wrapper's own instance ADDRESS
         (``PyWrapperStruct.cpp:807``). The gathered wrappers stay alive, so the
         fresh one always has a different address and every lookup misses.
      3. ``FSubobjectDataHandle`` declares no ``UPROPERTY`` at all — its only
         member is a private ``TSharedPtr`` — so the exported-value half of that
         string is constant and the address is the only distinguishing content.

    Consequence had it shipped: ``parent`` is ``None`` for every component, so
    ``camera_parented_to_boom`` could never pass and every conforming submission
    scored 5/6. Neither the spike nor the offline oracle could catch it — the
    spike read names only and never called ``get_parent_handle``, and a fake
    returning the identical Python object makes ``str(ph) == str(h)`` true in
    the test and only in the test.

    This is the route the SHIPPING, editor-validated graders use
    (``hero_blueprint_copy_with_flashlight.py::_parent_data``,
    ``third_person_chase_camera.py``), including its two defenses: the return
    may arrive as a tuple/list, and a handle whose validity cannot be
    established is treated as INVALID rather than walked.
    """
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handle = lib.get_parent_handle(data)
    if isinstance(handle, (tuple, list)):
        handle = handle[-1] if handle else None
    if handle is None:
        return None
    validator = getattr(lib, "is_handle_valid", None)
    if validator is not None:
        try:
            if not bool(validator(handle)):
                return None
        except Exception:  # noqa: BLE001 - unreadable => not valid
            return None
    pdata = lib.get_data(handle)
    if pdata is None:
        return None
    pobj = lib.get_object(pdata)
    return _stem(pobj.get_name()) if pobj is not None else None


def _hierarchy(bp):
    """[(stem, class_name, parent_stem)] for every subobject, or (None, token).

    Walks the SubobjectDataSubsystem, which is the supported route for reading
    a Blueprint's component tree (`AttachToName` is a bare UPROPERTY and not
    Python-writable, but this is a READ and the subsystem answers it).
    """
    try:
        sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    except Exception as e:  # noqa: BLE001
        return None, "CHARRIG_SUBSYSTEM_ERROR raised=%r" % (e,)
    try:
        handles = sub.k2_gather_subobject_data_for_blueprint(bp)
        lib = unreal.SubobjectDataBlueprintFunctionLibrary
        rows = []
        for h in handles:
            d = lib.get_data(h)
            obj = lib.get_object(d)
            if obj is None:
                continue
            try:
                parent = _parent_stem(d)
            except Exception:  # noqa: BLE001 - the root has no parent
                parent = None
            rows.append((_stem(obj.get_name()),
                         obj.get_class().get_name(), parent))
        return rows, None
    except Exception as e:  # noqa: BLE001
        return None, "CHARRIG_HIERARCHY_READ_ERROR raised=%r" % (e,)


def _grade():
    results = {}

    try:
        bp = unreal.EditorAssetLibrary.load_asset(BP_PATH)
    except Exception as e:  # noqa: BLE001
        for cid in CHECK_IDS:
            results[cid] = check(cid, False,
                                 "CHARRIG_LOAD_ERROR raised=%r" % (e,))
        return results

    if bp is None:
        results["blueprint_present"] = check(
            "blueprint_present", False, "CHARRIG_BP_ABSENT path=%s" % BP_PATH)
        for cid in CHECK_IDS[1:]:
            results[cid] = check(cid, False,
                                 "CHARRIG_UNCHECKABLE the blueprint is missing")
        return results
    results["blueprint_present"] = check(
        "blueprint_present", True, "CHARRIG_BP_OK %s" % BP_PATH)

    # --- parent class, via the generated class (NOT the object property) ----
    cid = "derives_from_character"
    try:
        gen = unreal.load_object(None, BP_PATH + "." + BP_NAME + "_C")
        cdo = unreal.get_default_object(gen)
        is_char = isinstance(cdo, unreal.Character)
        results[cid] = check(
            cid, is_char,
            "CHARRIG_PARENT_OK Character" if is_char
            else "CHARRIG_WRONG_PARENT not a character class")
    except Exception as e:  # noqa: BLE001
        cdo = None
        results[cid] = check(cid, False, "CHARRIG_CDO_READ_ERROR raised=%r" % (e,))

    # --- the rig ------------------------------------------------------------
    rows, err = _hierarchy(bp)
    if err:
        for cid in ("boom_component_present", "camera_parented_to_boom"):
            results[cid] = check(cid, False, err)
    else:
        by_stem = {r[0]: r for r in rows}

        # THE ROOT IS NOT THE ROW WITH NO PARENT (measured in a real editor,
        # 2026-08-14 — and this cost a FAIL on the reference before it was
        # understood). The parentless row is the CLASS DEFAULT OBJECT, an
        # artifact of how the subobject walk presents the tree. `ACharacter`'s
        # actual scene root is its capsule, `CollisionCylinder`, so a component
        # the authoring code attaches to `handles[0]` reports its parent as the
        # CAPSULE, not the CDO.
        #
        # So "attached at the character's root" is graded as "attached to the
        # inherited root component", identified by name, with the CDO row
        # excluded. Anything the agent creates itself is a valid answer only if
        # it lands there.
        # The root component is the one whose PARENT is the CDO row.
        _CDO = "Default__"
        cdo_stems = {r[0] for r in rows if r[0].startswith(_CDO)}
        root_stem = next((r[0] for r in rows if r[2] in cdo_stems), None)
        # BOTH spellings of "at the root" are accepted: the inherited root
        # component itself, and the CDO row (which is what `handles[0]` is, and
        # what an authoring script naturally passes). They are the same intent,
        # and rejecting either would be a false FAIL on a legitimate answer —
        # the mistake this check already made once.
        root_ok = {s for s in (root_stem,) if s} | cdo_stems

        # THE COMPONENT TYPE IS GRADED, not merely collected. An earlier cut
        # read each class into the row and then never looked at it, so two bare
        # SceneComponents named TaskBoom/TaskCam scored 6/6 while anti-gaming
        # note 3 claimed the tree walk defended against exactly that. Both
        # sibling graders in this family assert class identity; so does this one
        # now. Suffix match, not equality: a subclass of the required type is a
        # legitimate answer (the prompt names a behaviour, not a class).
        boom = by_stem.get(BOOM_STEM)
        if boom is None:
            results["boom_component_present"] = check(
                "boom_component_present", False,
                "CHARRIG_BOOM_MISSING wanted=%s got=%s"
                % (BOOM_STEM, sorted(by_stem)))
        elif not str(boom[1]).endswith("SpringArmComponent"):
            results["boom_component_present"] = check(
                "boom_component_present", False,
                "CHARRIG_BOOM_WRONG_CLASS wanted=SpringArmComponent got=%s"
                % (boom[1],))
        elif root_ok and boom[2] not in root_ok:
            # "an extendable arm attached at the character's root" - the prompt
            # says where it goes, so the grader checks it. Skipped entirely when
            # the root cannot be identified, rather than guessing.
            results["boom_component_present"] = check(
                "boom_component_present", False,
                "CHARRIG_BOOM_WRONG_PARENT expected=%s got=%s"
                % (sorted(root_ok), boom[2]))
        else:
            results["boom_component_present"] = check(
                "boom_component_present", True, "CHARRIG_BOOM_OK %s" % BOOM_STEM)

        cam = by_stem.get(CAM_STEM)
        if cam is None:
            results["camera_parented_to_boom"] = check(
                "camera_parented_to_boom", False,
                "CHARRIG_CAMERA_MISSING wanted=%s got=%s"
                % (CAM_STEM, sorted(by_stem)))
        elif not str(cam[1]).endswith("CameraComponent"):
            results["camera_parented_to_boom"] = check(
                "camera_parented_to_boom", False,
                "CHARRIG_CAMERA_WRONG_CLASS wanted=CameraComponent got=%s"
                % (cam[1],))
        else:
            ok = cam[2] == BOOM_STEM
            results["camera_parented_to_boom"] = check(
                "camera_parented_to_boom", ok,
                "CHARRIG_CAMERA_ON_BOOM_OK" if ok
                else "CHARRIG_CAMERA_WRONG_PARENT expected=%s got=%s"
                     % (BOOM_STEM, cam[2]))

    # --- the movement values, which carry the discrimination ---------------
    cid = "movement_values_exact"
    if cdo is None:
        results[cid] = check(cid, False, "CHARRIG_UNCHECKABLE no class default object")
        results["movement_untouched_defaults_absent"] = check(
            "movement_untouched_defaults_absent", False,
            "CHARRIG_UNCHECKABLE no class default object")
    else:
        try:
            mv = cdo.get_editor_property("character_movement")
            got = {k: mv.get_editor_property(k) for k, _ in WANTED_MOVEMENT}
        except Exception as e:  # noqa: BLE001
            mv = None
            got = None
            results[cid] = check(cid, False, "CHARRIG_CDO_READ_ERROR raised=%r" % (e,))
            results["movement_untouched_defaults_absent"] = check(
                "movement_untouched_defaults_absent", False,
                "CHARRIG_CDO_READ_ERROR raised=%r" % (e,))
        if got is not None:
            wrong = ["%s=%s want=%s" % (k, got[k], v)
                     for k, v in WANTED_MOVEMENT if got[k] != v]
            results[cid] = check(
                cid, not wrong,
                "CHARRIG_MOVEMENT_OK" if not wrong
                else "CHARRIG_MOVEMENT_WRONG %s" % wrong)
            # A SEPARATE, NARROWER claim than the one above: none of the three
            # is still sitting at the value the stock character ships. It can
            # only fail when a submission inherited the shipped character's
            # tuning rather than setting its own, which is exactly the
            # duplicate route — so it names that cause instead of letting it
            # hide inside a generic "wrong value".
            stock = {"max_walk_speed": 500.0, "jump_z_velocity": 500.0,
                     "max_acceleration": 2048.0}
            inherited = [k for k, _ in WANTED_MOVEMENT if got[k] == stock[k]]
            results["movement_untouched_defaults_absent"] = check(
                "movement_untouched_defaults_absent", not inherited,
                "CHARRIG_MOVEMENT_NOT_INHERITED" if not inherited
                else "CHARRIG_MOVEMENT_STILL_STOCK fields=%s" % inherited)

    return results


def main():
    if unreal is None:
        checks = [check(cid, False, "CHARRIG_NO_UNREAL editor python unavailable")
                  for cid in CHECK_IDS]
    else:
        try:
            results = _grade()
        except Exception as e:  # noqa: BLE001
            results = {}
            sys.stderr.write("char-rig grader raised: %r\n" % (e,))
        checks = [results.get(cid) or check(cid, False,
                                            "CHARRIG_CHECK_UNREACHED %s" % cid)
                  for cid in CHECK_IDS]

    block = json.dumps({"checks": checks})
    print(START)
    print(block)
    print(END)
    sys.stdout.flush()
    if unreal is not None:
        try:
            unreal.log(START)
            unreal.log(block)
            unreal.log(END)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
