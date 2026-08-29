"""L2-introspect script for the t2-consistent-enum-names task.

THE RENAME LANE (design-o2-rename-lane, 2026-07-30; seed roster R4): the committed
baseline ships four MISNAMED UserDefinedEnum assets under
``/Game/Tasks/t2-consistent-enum-names/Enums/`` (``WeaponType``,
``E_ammo_kind``, ``enum_DamageType``, ``ItemRarity``) plus two Blueprints at
the task root (``BP_RefA``, ``BP_RefB``) whose variables are typed to them.
The agent brings the enums to the naming convention (``E_WeaponType``,
``E_AmmoKind``, ``E_DamageType``, ``E_ItemRarity``) with references kept
working. The old->new mapping is HARD-CODED here (the oracle is the fixed
committed baseline; no convention-parsing at grade time).

WHAT IS GRADED - the TRI-STATE CLOSURE over asset-registry state (the design's
central finding: a clean UE 5.8 rename deletes the old package and the
copy-only overlay resurrects the baseline enum as an ORPHAN, while a
fixup-blocked rename leaves a REDIRECTOR - both are legitimate mechanical
outcomes of the same correct action, so the grader accepts both and excludes
every lazy/cheap-wrong state):
  * C1-C4  ``new_asset_*``      - the four new packages exist and are
    UserDefinedEnum assets (registry class check).
  * C5-C8  ``old_path_retired_*`` - each OLD path is no longer load-bearing:
    EITHER a redirector whose DestinationObject registry tag lands EXACTLY on
    the expected new package (redirector-residue lane, tolerated by the
    spec's ``allow_redirectors`` key) OR a resurrected orphan enum with ZERO
    registry referencers (clean-fixup lane).
  * C9-C10 ``refs_resolved_*``  - each referencing BP exists, is a Blueprint,
    and its registry dependency set - after substituting each allowed old
    package through its C5-C8-VERIFIED redirector target - covers that BP's
    two expected new packages and contains NO old package that is not a
    verified redirector.
  * C11    ``folder_inventory`` - the Enums folder holds EXACTLY the eight
    expected packages (4 new + 4 old in either disposition), nothing else.

CONTRACT RULE HONOURED BY CONSTRUCTION (INTROSPECT_CONTRACT.md, the
``allow_redirectors`` section - this rule BINDS every grader whose spec
declares the key): allowed old paths are read ONLY through registry
``AssetData`` (``asset_class_path``, ``get_tag_value("DestinationObject")``,
``get_referencers``) - NEVER ``load_asset``/``load_object`` (which silently
follows the redirector and grades its TARGET). This grader goes further:
it calls ``load_asset`` on NOTHING - every fact, new paths included, is a
registry read. No PIE, no live world, no mutation.

UE 5.8 API notes (engine source at ``<UE_ROOT>`` + the 2026-07-30 live spike
facts, which OVERRIDE design-doc assumptions):
  * ``asset_data.get_tag_value("<tag>")`` returns a plain **str**; a missing
    tag returns **None** (no exception, no tuple) - spike facts section D.
  * ``ar.get_dependencies(pkg, unreal.AssetRegistryDependencyOptions())`` and
    ``get_referencers(...)`` return a plain **Array** (no bool marshaling) -
    spike facts section D.
  * The DestinationObject tag is written by
    ``UObjectRedirector::GetAssetRegistryTags`` (ObjectRedirector.cpp:63-78)
    as ``FObjectPropertyBase::GetExportPath`` text - expected shape
    ``Class'/Game/Path.Name'`` - and ObjectRedirector is NOT in the
    AR-filtered skip set (AssetRegistryInterface.cpp:65-121), so default
    registry queries return redirector AssetData. The exact 5.8 text shape is
    a design open question: the parse below is TOLERANT (quoted export form
    OR bare object path) and every surprise routes to an UNCREDITED
    ``ENUM_OLD_TAG_*`` token, never a graded semantic failure.
  * Derived-class registry queries return ``SKEL_<Name>_C`` duplicates in the
    same package (2026-07-30 corpus-boot correction). C11 therefore collapses
    the folder listing to a PACKAGE-NAME SET, never counting raw entries.
  * Enum MEMBER spellings are wrapper-relocated (underscore moves; the R13
    lesson) - irrelevant here because no enum member is ever compared: class
    names (``UserDefinedEnum``, ``ObjectRedirector``, ``Blueprint``) are
    asset-registry class names, compared verbatim.

Hard rules honoured (exemplars: ``move_jump_sprint_bindings.py``,
``weapon_held_in_right_hand.py``):
  * READ-ONLY; stock UE Python + stdlib only; never Aura's MCP tools.
  * Identity by pre-declared content path and pre-declared NAMES.
  * FAIL CLOSED: a missing registry, unreadable AssetData, unreadable tag or
    dependency list is a FAILURE with its own distinct token from
    ``UNCREDITED_TOKENS`` - never a skip, never a pass, and never creditable
    as a variant's named failure (the MATRIX carries none of those tokens).
  * CONSTANT check denominator (11) on every leg, including the committed
    baseline itself (a genuine 0/11) and a no-``unreal`` import.

Detail strings are stable ASCII greppable tokens. Echoed SUBMISSION-derived
text (registry class names, redirector tag text, referencer/extra package
names - all agent-influencable) is sanitized (whitespace and ``=`` map to
``~``) and length-capped before echoing, so an adversarial name can never
assemble an automation result marker inside the grading log; the two marker
substrings ``parse_automation_log`` counts as tests appear nowhere in this
file.
"""
import json
import re
import string

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and NAMES, never class) ------------
TASK_ID = "t2-consistent-enum-names"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
ENUM_DIR = "%s/Enums" % PKG_DIR

# (check key, OLD asset name, NEW asset name) - the hard-coded mapping.
ENUM_SPECS = (
    ("weapon_type", "WeaponType", "E_WeaponType"),
    ("ammo_kind", "E_ammo_kind", "E_AmmoKind"),
    ("damage_type", "enum_DamageType", "E_DamageType"),
    ("item_rarity", "ItemRarity", "E_ItemRarity"),
)

# (check key, BP asset name, the two enum spec-keys its variables use)
BP_SPECS = (
    ("bp_ref_a", "BP_RefA", ("weapon_type", "ammo_kind")),
    ("bp_ref_b", "BP_RefB", ("damage_type", "item_rarity")),
)

OLD_PKGS = {key: "%s/%s" % (ENUM_DIR, old) for key, old, _ in ENUM_SPECS}
NEW_PKGS = {key: "%s/%s" % (ENUM_DIR, new) for key, _, new in ENUM_SPECS}
EXPECTED_FOLDER_PKGS = frozenset(OLD_PKGS.values()) | frozenset(NEW_PKGS.values())

# Echo sanitizer allowlist: NO space and NO '=' (automation-marker injection
# defense, header comment) - anything else becomes '~'. '/' stays so real
# package paths echo verbatim.
_SNIPPET_SAFE = frozenset(string.ascii_letters + string.digits + "_./()-,'")
# A full /Game/Tasks/<this-id>/Enums/<name> package path is ~56 chars and the
# MATRIX joins on whole echoed paths - the cap must never truncate one.
SNIPPET_LEN = 100
OFFENDER_CAP = 6

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "new_asset_weapon_type",
    "new_asset_ammo_kind",
    "new_asset_damage_type",
    "new_asset_item_rarity",
    "old_path_retired_weapon_type",
    "old_path_retired_ammo_kind",
    "old_path_retired_damage_type",
    "old_path_retired_item_rarity",
    "refs_resolved_bp_ref_a",
    "refs_resolved_bp_ref_b",
    "folder_inventory",
)

# Tokens that mean "the VERIFIER could not establish a fact" (or a state no
# agent action can cause under the copy-only overlay). Graded FAILED,
# conservative taxonomy - and NEVER creditable: the offline oracle asserts
# none of these appears in any MATRIX substring.
UNCREDITED_TOKENS = (
    "ENUM_NEW_READ_ERROR",
    "ENUM_OLD_READ_ERROR",
    "ENUM_OLD_ASSETDATA_UNAVAILABLE",
    "ENUM_OLD_TAG_UNREADABLE",
    "ENUM_OLD_TAG_UNPARSEABLE",
    "ENUM_OLD_REFERENCERS_READ_ERROR",
    "BP_DEP_READ_ERROR",
    "ENUM_FOLDER_READ_ERROR",
    "RENAME_REGISTRY_UNAVAILABLE",
    "RENAME_INTROSPECTION_ABORTED",
    "CHECK_NOT_EVALUATED",
)


# --------------------------------------------------------------------------- #
# verdict plumbing                                                             #
# --------------------------------------------------------------------------- #

def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed), "detail": str(detail)}


def emit_verdict(checks):
    """Print the one verdict block the L2-introspect layer parses."""
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        try:
            unreal.log(INTROSPECT_JSON_START)
            unreal.log(payload)
            unreal.log(INTROSPECT_JSON_END)
        except Exception:  # noqa: BLE001 - stdout copy is authoritative
            pass


def _sanitize(text):
    """Truncate + neutralize agent-influencable text before echoing it.

    '=' and whitespace map to '~' so an adversarial package/class/tag name can
    never assemble an automation result marker inside the grading log.
    """
    return "".join(ch if ch in _SNIPPET_SAFE else "~"
                   for ch in str(text)[:SNIPPET_LEN])


# --------------------------------------------------------------------------- #
# registry read helpers (each defensive; callers wrap in try/except)           #
# --------------------------------------------------------------------------- #

def _registry():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    if ar is None:
        raise RuntimeError("get_asset_registry returned None")
    # The L2I bootstrap has already wait_for_completion'd; re-wait defensively
    # (a still-scanning registry must never misread an asset as missing).
    try:
        ar.wait_for_completion()
    except Exception:  # noqa: BLE001 - absence of the method is tolerable
        pass
    return ar


def _asset_data(ar, obj_path):
    """Registry AssetData for an object path, or None when absent/invalid."""
    try:
        ad = ar.get_asset_by_object_path(obj_path)
    except TypeError:
        soft = getattr(unreal, "SoftObjectPath", None)
        if soft is None:
            raise
        ad = ar.get_asset_by_object_path(soft(obj_path))
    if ad is None:
        return None
    try:
        if hasattr(ad, "is_valid") and not ad.is_valid():
            return None
    except Exception:  # noqa: BLE001 - unqueryable validity = not usable
        return None
    return ad


def _class_name_of(ad):
    """The AssetData's class name (5.8 TopLevelAssetPath primary, legacy
    ``asset_class`` fallback). Raises when neither surface reads."""
    try:
        tl = ad.asset_class_path
        name = str(tl.asset_name)
        if name:
            return name
    except Exception:  # noqa: BLE001 - fall through to the legacy spelling
        pass
    return str(ad.asset_class)


def _tag_value(ad, name):
    """Registry tag as text. Live fact (spike section D): plain str, or None
    for a nonexistent tag. Raises only when the read surface itself breaks."""
    return ad.get_tag_value(name)


def _parse_export_target(text):
    """Package path out of a DestinationObject tag, tolerantly.

    Accepts the export form ``Class'/Game/Path.Name'`` AND a bare object path
    ``/Game/Path.Name`` (the exact 5.8 shape is pinned by the authoring boot;
    a surprise shape returns None -> uncredited ENUM_OLD_TAG_UNPARSEABLE).
    A CHAINED redirector parses fine but its one-hop target equals the
    intermediate, not the expected new package - so chains fail C5-C8.
    """
    s = str(text).strip()
    m = re.search(r"'([^']+)'", s)
    obj = m.group(1) if m else s
    if not obj.startswith("/"):
        return None
    return obj.split(".")[0]


def _pkg_list(ar, method_name, pkg):
    """get_referencers / get_dependencies as a list of str package names.
    Raises on any surprise (None return, unreadable elements) - fail closed.
    """
    out = getattr(ar, method_name)(pkg, unreal.AssetRegistryDependencyOptions())
    if out is None:
        raise RuntimeError("%s(%s) returned None" % (method_name, pkg))
    return [str(x) for x in out]


# --------------------------------------------------------------------------- #
# C1-C4: the four new assets                                                   #
# --------------------------------------------------------------------------- #

def _new_asset_check(results, ar, cid, new_name, new_pkg):
    ad = _asset_data(ar, "%s.%s" % (new_pkg, new_name))
    if ad is None:
        results[cid] = check(cid, False,
                             "ENUM_NEW_MISSING_%s path=%s" % (new_name, new_pkg))
        return
    cls = _class_name_of(ad)
    if cls != "UserDefinedEnum":
        # A redirector parked at a NEW path also lands here (never followed:
        # this grader loads nothing) - and the integrity preamble has already
        # graded it REDIRECTOR_SUBMITTED (the allowlist names old paths only).
        results[cid] = check(cid, False,
                             "ENUM_NEW_WRONG_CLASS_%s path=%s class=%s"
                             % (new_name, new_pkg, _sanitize(cls)))
        return
    results[cid] = check(cid, True, "ENUM_NEW_OK path=%s" % new_pkg)


# --------------------------------------------------------------------------- #
# C5-C8: each old path retired (redirector-with-exact-target OR zero-ref       #
# orphan) - returns the verified redirector target for C9-C10 substitution     #
#                                                                              #
# COVERAGE NOTE (2026-07-30, live finding - do NOT "simplify" this branch):    #
# branch (a), the redirector residue, is LIVE-UNEXERCISABLE on this box.       #
# The authoring boot proved three routes dead headless on UE 5.8: the stock    #
# rename lane with loadable Blueprint referencers always fixes them up in      #
# memory, resaves them and DELETES the old package (no redirector); the        #
# read-only-referencer trick does not reach DetectReadOnlyPackages headless    #
# (named abort RENLANE-REDIRECTOR-NOT-CREATED); and an unloaded-map            #
# referencer cannot be arranged because a level holding a placed instance of   #
# the referencing Blueprint references the BLUEPRINT, not the enum. Python     #
# cannot construct a UObjectRedirector directly either (DestinationObject is   #
# an unreflected C++ member). So NO discrimination-matrix folder leg can       #
# exercise this branch, and its logic is pinned by the OFFLINE oracle only     #
# (tests/test_introspect_consistent_enum_names.py::TestTriStateContract).      #
# The branch STAYS: an agent with source control, a genuinely unloaded map     #
# referencer, or a partially-failing fixup really can produce the residue,     #
# and a grader that dropped it would fail a correct submission.                #
# --------------------------------------------------------------------------- #

def _old_path_check(results, ar, cid, old_name, old_pkg, new_pkg):
    """Fill the old-path tri-state check. Returns the VERIFIED redirector
    target package (str) when the redirector branch passed, else None."""
    ad = _asset_data(ar, "%s.%s" % (old_pkg, old_name))
    if ad is None:
        # Unreachable via agent action: the copy-only overlay ALWAYS
        # resurrects the committed baseline file at the old path (or the
        # submission overwrote it with a redirector). Conservative FAIL,
        # uncredited - a registry surprise must never be credited.
        results[cid] = check(cid, False,
                             "ENUM_OLD_ASSETDATA_UNAVAILABLE old=%s" % old_pkg)
        return None
    cls = _class_name_of(ad)

    if cls == "ObjectRedirector":
        try:
            tag = _tag_value(ad, "DestinationObject")
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False,
                                 "ENUM_OLD_TAG_UNREADABLE old=%s raised %r"
                                 % (old_pkg, e))
            return None
        if tag is None:
            results[cid] = check(cid, False,
                                 "ENUM_OLD_TAG_UNREADABLE old=%s tag=None"
                                 % old_pkg)
            return None
        target = _parse_export_target(tag)
        if target is None:
            results[cid] = check(cid, False,
                                 "ENUM_OLD_TAG_UNPARSEABLE old=%s raw=%s"
                                 % (old_pkg, _sanitize(tag)))
            return None
        if target != new_pkg:
            results[cid] = check(
                cid, False,
                "ENUM_OLD_REDIRECT_WRONG_TARGET_%s got=%s expected=%s"
                % (old_name, _sanitize(target), new_pkg))
            return None
        results[cid] = check(cid, True,
                             "ENUM_OLD_REDIRECTS_OK old=%s target=%s"
                             % (old_pkg, new_pkg))
        return target

    if cls == "UserDefinedEnum":
        try:
            refs = _pkg_list(ar, "get_referencers", old_pkg)
        except Exception as e:  # noqa: BLE001
            results[cid] = check(
                cid, False,
                "ENUM_OLD_REFERENCERS_READ_ERROR old=%s raised %r"
                % (old_pkg, e))
            return None
        if refs:
            shown = ",".join(_sanitize(r) for r in sorted(refs)[:OFFENDER_CAP])
            results[cid] = check(
                cid, False,
                "ENUM_OLD_STILL_REFERENCED_%s old=%s refs=[%s]"
                % (old_name, old_pkg, shown))
            return None
        results[cid] = check(cid, True,
                             "ENUM_OLD_ORPHAN_OK old=%s refs=0" % old_pkg)
        return None

    results[cid] = check(cid, False,
                         "ENUM_OLD_UNEXPECTED_CLASS_%s old=%s class=%s"
                         % (old_name, old_pkg, _sanitize(cls)))
    return None


# --------------------------------------------------------------------------- #
# C9-C10: BP dependencies resolved onto the new packages                       #
# --------------------------------------------------------------------------- #

def _bp_check(results, ar, cid, bp_name, enum_keys, verified_targets):
    bp_pkg = "%s/%s" % (PKG_DIR, bp_name)
    ad = _asset_data(ar, "%s.%s" % (bp_pkg, bp_name))
    if ad is None:
        results[cid] = check(cid, False,
                             "BP_REF_MISSING_%s path=%s" % (bp_name, bp_pkg))
        return
    cls = _class_name_of(ad)
    if cls != "Blueprint":
        results[cid] = check(cid, False,
                             "BP_REF_WRONG_CLASS_%s path=%s class=%s"
                             % (bp_name, bp_pkg, _sanitize(cls)))
        return
    try:
        deps = _pkg_list(ar, "get_dependencies", bp_pkg)
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False,
                             "BP_DEP_READ_ERROR bp=%s raised %r" % (bp_name, e))
        return

    all_old = set(OLD_PKGS.values())
    resolved = set()
    old_live = set()
    for dep in deps:
        if dep in all_old:
            if dep in verified_targets:
                # One-hop substitution through a C5-C8-VERIFIED redirector
                # only. An unverified redirector (wrong target, unreadable
                # tag) or a still-real old enum counts as LIVE.
                resolved.add(verified_targets[dep])
            else:
                old_live.add(dep)
        else:
            resolved.add(dep)  # engine/script/other deps: out of scope
    if old_live:
        results[cid] = check(
            cid, False,
            "BP_DEP_OLD_NAME_LIVE_%s old=%s"
            % (bp_name, ",".join(sorted(old_live))))
        return
    expected = {NEW_PKGS[k] for k in enum_keys}
    missing = sorted(expected - resolved)
    if missing:
        results[cid] = check(
            cid, False,
            "BP_DEP_UNRESOLVED_%s missing=%s" % (bp_name, ",".join(missing)))
        return
    results[cid] = check(cid, True, "BP_DEPS_OK bp=%s" % bp_name)


# --------------------------------------------------------------------------- #
# C11: exact folder inventory                                                  #
# --------------------------------------------------------------------------- #

def _folder_check(results, ar, cid):
    try:
        try:
            ads = ar.get_assets_by_path(ENUM_DIR, recursive=False)
        except TypeError:
            ads = ar.get_assets_by_path(ENUM_DIR)
        if ads is None:
            raise RuntimeError("get_assets_by_path returned None")
        # PACKAGE-NAME SET collapse (the SKEL_<Name>_C lesson, 2026-07-30):
        # never count raw AssetData entries - same-package duplicates fold.
        pkgs = {str(ad.package_name) for ad in ads}
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False,
                             "ENUM_FOLDER_READ_ERROR raised %r" % (e,))
        return
    extras = sorted(pkgs - EXPECTED_FOLDER_PKGS)
    missing = sorted(EXPECTED_FOLDER_PKGS - pkgs)
    if extras:
        shown = ",".join(_sanitize(p) for p in extras[:OFFENDER_CAP])
        results[cid] = check(
            cid, False,
            "ENUM_FOLDER_UNEXPECTED_ASSET extra=[%s] n=%d"
            % (shown, len(extras)))
        return
    if missing:
        # Missing-only inventories are already caught name-by-name at C1-C8;
        # this token is recorded, never MATRIX-credited.
        results[cid] = check(
            cid, False,
            "ENUM_FOLDER_INCOMPLETE missing=[%s]" % ",".join(missing))
        return
    results[cid] = check(cid, True,
                         "ENUM_FOLDER_OK n=%d packages" % len(pkgs))


# --------------------------------------------------------------------------- #
# the eleven checks                                                            #
# --------------------------------------------------------------------------- #

def _run_checks(results):
    if unreal is None:
        for cid in CHECK_IDS:
            results[cid] = check(
                cid, False, "RENAME_INTROSPECTION_ABORTED no unreal module")
        return

    try:
        ar = _registry()
    except Exception as e:  # noqa: BLE001
        for cid in CHECK_IDS:
            results[cid] = check(
                cid, False, "RENAME_REGISTRY_UNAVAILABLE raised %r" % (e,))
        return

    # --- C1-C4: new assets exist + class ------------------------------------
    for key, _old, new_name in ENUM_SPECS:
        cid = "new_asset_%s" % key
        try:
            _new_asset_check(results, ar, cid, new_name, NEW_PKGS[key])
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False,
                                 "ENUM_NEW_READ_ERROR name=%s raised %r"
                                 % (new_name, e))

    # --- C5-C8: old paths retired; collect verified redirector targets ------
    verified_targets = {}
    for key, old_name, _new in ENUM_SPECS:
        cid = "old_path_retired_%s" % key
        try:
            target = _old_path_check(results, ar, cid, old_name,
                                     OLD_PKGS[key], NEW_PKGS[key])
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False,
                                 "ENUM_OLD_READ_ERROR name=%s raised %r"
                                 % (old_name, e))
            target = None
        if target is not None:
            verified_targets[OLD_PKGS[key]] = target

    # --- C9-C10: BP dependency closure --------------------------------------
    for key, bp_name, enum_keys in BP_SPECS:
        cid = "refs_resolved_%s" % key
        try:
            _bp_check(results, ar, cid, bp_name, enum_keys, verified_targets)
        except Exception as e:  # noqa: BLE001
            results[cid] = check(cid, False,
                                 "BP_DEP_READ_ERROR bp=%s raised %r"
                                 % (bp_name, e))

    # --- C11: exact folder inventory ----------------------------------------
    _folder_check(results, ar, "folder_inventory")


def main():
    results = {}
    try:
        _run_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        for cid in CHECK_IDS:
            if cid not in results:
                results[cid] = check(
                    cid, False, "RENAME_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
