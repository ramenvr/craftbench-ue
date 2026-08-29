"""graded_scratch — the disposable single-task project graded drives run on.

Phase C1 of the additive-staging plan: instead of hiding foreign tasks inside
the checked-out benchmark template (and restoring afterwards — the layer every
Windows lock, presnap, heal, and dirty-substrate gate existed to protect),
each graded aura drive runs on a COMPOSED scratch project at a short,
non-OneDrive path:

    base (git-archive HEAD substrate — committed bytes, never maintainer WIP)
    ∪ the ACTIVE task's files only          (task_layout staging primitives)
    − ALL verifier fixtures                 (the tests module carries only its
                                             base classes; the answer key never
                                             reaches the agent-visible tree, so
                                             body-stubbing retires)
    + the per-task ue-config overlay (B7), applied with NO revert bookkeeping

The checkout is NEVER mutated; recomposition (delete_extras mirror) is
simultaneously the reset, the "restore", and the fairness guarantee — a crash
mid-drive leaves nothing to heal on disk (a crash that leaves a LOCKED handle
makes the next compose REFUSE loudly instead of staging a contaminated tree;
the reap/heal lives in the callers). Build state (Binaries/Intermediate)
lives OUTSIDE the mirrored trees and persists across compositions
(incremental rebuild on task switch; engine-stamped clean rebuild via
stack's .cb-built) — EXCEPT the _RUN_STATE_DIRS carve-out, run state that
happens to live under Intermediate/ and is cleared every compose.

This module is PURE composition (filesystem only, unit-testable). Editor
launch/build wiring stays in stack.py; run_graded[_product] repoint in C1b.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, List, Optional

from . import driver

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parents[0]), str(_HERE.parents[1] / "verify-single")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import task_layout  # noqa: E402  (tools/verify-single — the shared classifier)
import sandbox  # noqa: E402  (tools/verify-single — the manifest's owner)

# The trees that get mirrored/staged per composition. Everything else in the
# scratch (Binaries, Intermediate, Saved, Plugins junction, DDC) is build/run
# state and survives across tasks.
_STAGED_TREES = ("Source", "Content", "Config")
_MARKER = ".cb-staged"
_DEFAULT_SUBSTRATE = "CraftBenchTemplate"
# The asset kinds the shared-dir police cares about — the manifest's
# asset_writable allowance governs ASSET files only, so only these can ride
# a stale scratch into a graded submission. Sourced from the manifest's
# owner so the police and the sandbox can never diverge.
_ASSET_SUFFIXES = tuple(e.lower() for e in sandbox.ASSET_EXTENSIONS)
# Marker schema: bumped when the marker gains a key a GATE depends on, so a
# marker written by older code reads as a MISMATCH (one recompose upgrades
# it) instead of silently running with that gate disarmed. v2 = the
# shared_asset_dirs/shared_assets_kept police. v3 = writable_roots/
# writable_baseline, the PRE-DRIVE pristine gate (see reset_agent_writable).
_MARKER_SCHEMA = 3
# RUN-state dirs that happen to live under the build-state tree (which
# deliberately survives recompositions) — cleared on every compose, refusing
# on a locked survivor. Today: Aura's sandbox-FS copy-on-write store, whose
# run N-1 leftovers would be Accept-all'd INTO run N's Content by
# _flush_aura_sandbox after the staged gate.
_RUN_STATE_DIRS = (Path("Intermediate") / "Sandboxes",)
# NB: the old _ROOT_FILES = ("CraftBenchTemplate.uproject",) constant is gone —
# the root .uproject is SUBSTRATE-DERIVED (the base archive's own *.uproject),
# and a stale other-substrate .uproject is removed on recompose.


def _substrate_dir_name(key: str) -> str:
    """Map a task-spec substrate value to the on-disk dir name — the SAME
    mapping the verifier applies (run_task._substrate_dir_name: legacy alias
    'template' → CraftBenchTemplate, unknown names pass through). Falls back
    to a minimal local mapping only if run_task is unimportable."""
    try:
        from run_task import _substrate_dir_name as _rt_map  # type: ignore
        return _rt_map(key)
    except ImportError:
        return {"template": _DEFAULT_SUBSTRATE}.get(key, key)


def substrate_for(task_spec_path: Optional[Path]) -> str:
    """The on-disk substrate dir name the task declares (spec v2 front matter
    ``substrate:``; legacy specs map to the default). ``None`` (no spec in
    scope) falls back to the default substrate. Raises on a malformed spec —
    composing the WRONG substrate must never happen silently."""
    if task_spec_path is None:
        return _DEFAULT_SUBSTRATE
    import spec as _spec  # tools/verify-single — on sys.path (see above)
    return _substrate_dir_name(_spec.parse_task_file(Path(task_spec_path)).substrate)


def get_graded_project_dir(explicit: str = "") -> Path:
    """The graded-drive scratch — SIBLING of the batch-gen playground
    (CraftBenchScratch), same short non-OneDrive root. Precedence: explicit →
    CB_GRADED_PROJECT → the managed CB_ROOT default (see aura_rig.paths:
    ``<cb_root>/scratch/CraftBenchGraded``)."""
    from . import paths as cb_paths
    return cb_paths.graded_project_dir(explicit)


def _shared_asset_dirs(base: Path,
                       log: Callable[[str], None] = print) -> Optional[List[str]]:
    """The substrate's SHARED asset-deliverable dirs: ``asset_writable``
    prefixes outside every ``task_layout.PER_TASK_ROOTS`` tree —
    Content/Blueprints/ & co., where Aura's bp/material/audio sub-agents
    author by default. An asset a prior run left there is invisible to the
    per-task-dir gate AND swept into the next graded submission by
    --capture-assets, so compose records these dirs (plus the base's own
    legit assets under them) in the marker for verify_staged to police.
    Returns None when the manifest is absent or lists none — the gate stays
    off, exactly like ``root_maps_kept`` without a spec. A manifest that
    EXISTS but fails to parse also fails open (never abort a compose over a
    policing extra), but WARNs — silence would be indistinguishable from
    'this substrate has no manifest'."""
    manifest = base / "AGENT_WRITABLE.json"
    try:
        man = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except OSError as e:
        log(f"  WARN  {manifest.name} exists but is unreadable ({e}) — the "
            f"shared-asset-dir police is OFF for this compose")
        return None
    except ValueError:
        log(f"  WARN  {manifest.name} exists but is not valid JSON — the "
            f"shared-asset-dir police is OFF for this compose")
        return None
    prefixes = man.get("asset_writable")
    if not isinstance(prefixes, list):
        return None
    out = set()
    per_task_roots = tuple(r.casefold() for r in task_layout.PER_TASK_ROOTS)
    for pref in prefixes:
        if not isinstance(pref, str):
            continue
        norm = pref.replace("\\", "/").strip("/")
        if not norm:
            continue
        folded = norm.casefold()  # Windows: case-insensitive filesystem
        if any(folded == root or folded.startswith(root + "/")
               for root in per_task_roots):
            continue  # per-task trees have their own verify_staged gate
        out.add(norm)
    return sorted(out) or None


def _writable_roots(base: Path,
                    log: Callable[[str], None] = print) -> Optional[List[str]]:
    """The AGENT-WRITABLE AREA of the substrate: the manifest's ``writable``
    prefixes ∪ its ``asset_writable`` prefixes (normalized, nested ones
    folded into their parent). This is exactly the surface a drive may mutate
    — Source/<module>/, Content/Tasks/, and the shared asset roots — and
    therefore exactly the surface a per-rep reset must guarantee pristine.

    Returns None when the manifest is absent or unparseable: the pristine gate
    then reports ``unverified`` rather than silently policing a surface it
    could not derive (same fail-open-but-LOUD contract as
    :func:`_shared_asset_dirs`)."""
    manifest = base / "AGENT_WRITABLE.json"
    try:
        man = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log(f"  WARN  {manifest.name} exists but is unusable ({e}) — the "
            f"pre-drive pristine gate is UNVERIFIED for this compose")
        return None
    roots = set()
    for key in ("writable", "asset_writable"):
        for pref in man.get(key) or ():
            if not isinstance(pref, str):
                continue
            norm = pref.replace("\\", "/").strip("/")
            if norm:
                roots.add(norm)
    # Fold nested prefixes (Content/Tasks/ swallows Content/Tasks/Foo/) so the
    # baseline walk visits every file exactly once.
    out = [r for r in sorted(roots)
           if not any(r != o and r.casefold().startswith(o.casefold() + "/")
                      for o in roots)]
    return out or None


def _files_under(root: Path, dirs: List[str]) -> List[Path]:
    """Every file under ``dirs`` (root-relative prefixes), deterministic order."""
    out: List[Path] = []
    for d in dirs:
        droot = root / d
        if not droot.is_dir():
            continue
        out.extend(sorted(p for p in droot.rglob("*") if p.is_file()))
    return out


def _sha1(path: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _writable_baseline(root: Path, dirs: List[str]) -> dict:
    """``{root-relative POSIX path: sha1}`` for the agent-writable area.

    CONTENT-keyed, not mtime-keyed: the mirror rewrites mtimes, and an mtime
    baseline would report every compose as dirty. Hashing this area is cheap
    (the staged tree holds ONE task's content), and the hash is what makes
    'byte-identical to the substrate baseline' a checkable claim rather than a
    hope."""
    return {p.relative_to(root).as_posix(): _sha1(p)
            for p in _files_under(root, dirs)}


def _assets_under(root: Path, dirs: List[str]) -> List[str]:
    """Sorted root-relative POSIX paths of every asset file under ``dirs``.
    Suffix-tested before stat so non-asset entries cost nothing."""
    out: List[str] = []
    for d in dirs:
        droot = root / d
        if not droot.is_dir():
            continue
        out.extend(
            p.relative_to(root).as_posix() for p in droot.rglob("*")
            if p.suffix.lower() in _ASSET_SUFFIXES and p.is_file())
    return sorted(out)


def _marker_substrate(marker: dict) -> str:
    """The marker's substrate (pre-substrate markers mean the default)."""
    return marker.get("substrate") or _DEFAULT_SUBSTRATE


def _reset_or_refuse(path: Path, what: str) -> None:
    """Delete a dir the reset owns, refusing LOUDLY on a survivor — an
    un-reset leftover would ride into the next grade."""
    from . import stack
    if not os.path.lexists(str(path)):
        return
    # is_dir is INFERRED (the reset also owns individual residue FILES since
    # reset_agent_writable): _delete_retry's dir branch rmtree's, which raises
    # NotADirectoryError on a file and would read as a locked survivor.
    if not stack._delete_retry(path, is_dir=Path(path).is_dir()):
        raise OSError(
            f"compose: {what} survived removal (locked?): {path} — the "
            f"reset is incomplete, so composing REFUSES; close any editor "
            f"holding the scratch open and rerun")


def _substrate_head_sha(repo: Path, project_rel: str = driver.PROJECT_REL) -> str:
    """The HEAD tree sha of the substrate subtree (composition provenance)."""
    import subprocess
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{project_rel}"],
        capture_output=True, text=True, timeout=15)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def compose(
    task_id: str,
    *,
    repo: Path = None,
    scratch_dir: Optional[Path] = None,
    task_spec_path: Optional[Path] = None,
    copy_substrate_fn: Optional[Callable] = None,
    log: Callable[[str], None] = print,
) -> Path:
    """Compose the graded scratch for ``task_id`` and return its dir.

    Steps: git-archive HEAD of the ACTIVE TASK'S substrate (derived from
    ``task_spec_path`` — spec v2 ``substrate:``; default substrate when the
    spec path is None) → temp base; ADDITIVE staging in the temp (delete
    foreign per-task dirs, delete foreign flat scaffolds, strip the tests
    module to its base allowlist — fixtures never enter the agent-visible
    tree); apply the task's ue-config overlay; invalidate the OLD marker
    (an aborted compose must leave a marker-less tree, never a matching
    marker beside a half-reset one); clear the ``_RUN_STATE_DIRS``; mirror
    the staged trees into the scratch with delete_extras (the reset+restore
    in one move — a substrate SWITCH is just another recomposition),
    REFUSING loudly when a locked survivor defeats any of those deletes;
    write the ``.cb-staged`` marker (schema version, substrate + its
    .uproject name, the root-map and shared-asset-dir keep-sets).

    ``copy_substrate_fn``/``scratch_dir``/``repo`` are injectable for tests.
    Raises on composition failure — a drive must never start on a
    half-composed tree.
    """
    repo = Path(repo) if repo else driver.REPO
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    bare = task_layout.bare_task_id(task_id)
    substrate = substrate_for(task_spec_path)
    project_rel = driver.project_rel(substrate, repo=repo)  # validates; lists available

    if copy_substrate_fn is None:
        from run_task import copy_substrate as copy_substrate_fn  # type: ignore

    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="cb-compose-") as td:
        base = Path(td) / "base"
        copy_substrate_fn(repo / project_rel, base)

        removed_dirs = task_layout.stage_per_task_dirs_active_only(base, bare)
        removed_flat = task_layout.stage_flat_scaffolds_active_only(base, bare)
        removed_tests = task_layout.strip_tests_to_base(base)  # NO fixtures at all

        # Pre-migration FLAT maps at Content/Maps root are files, so the
        # per-task-dir stager can't see them. When the spec is available,
        # keep only the maps it names (plus shared infra) and record the
        # survivors in the marker so verify_staged can police them. Without
        # a spec (tests / ad-hoc composes) behavior is unchanged: keep all.
        removed_maps: List[str] = []
        root_maps_kept: Optional[List[str]] = None
        if task_spec_path is not None:
            try:
                spec_text = Path(task_spec_path).read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                spec_text = ""
            if spec_text:
                removed_maps = task_layout.stage_root_maps_active_only(
                    base, task_layout.spec_map_names(spec_text))
                maps_dir = base / "Content" / "Maps"
                kept_stems: set = set()
                if maps_dir.is_dir():
                    for p in maps_dir.iterdir():
                        if not p.is_file():
                            continue
                        for sfx in (".umap", ".uasset"):
                            if p.name.endswith(sfx):
                                kept_stems.add(p.name[:-len(sfx)])
                                break
                root_maps_kept = sorted(kept_stems)

        # B7 per-task ue-config overlay: applied directly onto the staged
        # Config/ — no parking/revert; the next compose re-mirrors wholesale.
        overlay_applied: List[str] = []
        if task_spec_path is not None:
            try:
                import config_overlay
            except ImportError:
                config_overlay = None
            if config_overlay is not None:
                frags = config_overlay.discover(Path(task_spec_path))
                if frags:
                    applied = config_overlay.apply(base / "Config", frags, bare)
                    overlay_applied = [f.ini_name for f in applied]

        # Shared-asset-dir police (see _shared_asset_dirs): record the dirs +
        # the base's own legit assets so verify_staged can flag leftovers —
        # the root_maps_kept pattern.
        shared_dirs = _shared_asset_dirs(base, log=log)
        shared_kept = None if shared_dirs is None else _assets_under(base, shared_dirs)

        # PRE-DRIVE pristine gate (see reset_agent_writable): record the
        # agent-writable area's baseline CONTENT here, where the freshly
        # staged base still IS the baseline. Recorded from the base, never
        # from the scratch — a scratch already carrying residue must not be
        # able to certify itself pristine.
        writable_roots = _writable_roots(base, log=log)
        writable_baseline = (None if writable_roots is None
                             else _writable_baseline(base, writable_roots))

        scratch.mkdir(parents=True, exist_ok=True)
        from . import stack
        # Invalidate the OLD marker before the first mutation: an exception
        # anywhere below (locked extra, Ctrl-C) must leave a marker-LESS
        # partial tree that the next attempt fully recomposes — never a
        # matching stale marker beside a half-reset scratch that
        # ensure_composed would fast-path over.
        (scratch / _MARKER).unlink(missing_ok=True)
        for rel in _RUN_STATE_DIRS:
            _reset_or_refuse(scratch / rel, f"run-state dir {rel.as_posix()}/")
        for tree in _STAGED_TREES:
            src = base / tree
            if src.is_dir():
                failed: List[str] = []
                if not stack._mirror_tree(src, scratch / tree,
                                          delete_extras=True,
                                          failed_deletes=failed):
                    raise OSError(f"compose: mirror of {tree} into {scratch} failed")
                if failed:
                    listed = ", ".join(f"{tree}/{p}" for p in failed[:5])
                    raise OSError(
                        f"compose: {len(failed)} stale scratch entries under "
                        f"{tree}/ survived delete_extras (locked?): {listed}"
                        f"{' …' if len(failed) > 5 else ''} — the reset is "
                        f"incomplete, so composing REFUSES; close any editor "
                        f"holding the scratch open and rerun")
            else:
                _reset_or_refuse(scratch / tree, f"stale {tree}/ tree")
        # Root .uproject: the substrate's OWN (substrate-derived, never a
        # fixed name). Exactly one is expected in the base archive; a stale
        # OTHER-substrate .uproject left in the scratch by a prior composition
        # would make the scratch ambiguous, so it is removed here (the
        # recompose IS the reset, exactly like delete_extras for the trees).
        base_uprojects = sorted(base.glob("*.uproject"))
        if len(base_uprojects) != 1:
            names = ", ".join(p.name for p in base_uprojects) or "(none)"
            raise OSError(
                f"compose: expected exactly one .uproject in the {substrate} "
                f"substrate, found {len(base_uprojects)}: {names}")
        uproject_name = base_uprojects[0].name
        for stale in scratch.glob("*.uproject"):
            if stale.name != uproject_name:
                stale.unlink(missing_ok=True)
        shutil.copy2(base_uprojects[0], scratch / uproject_name)
        # NB: AGENT_WRITABLE.json is deliberately NOT copied — it is verifier-
        # side policy (run_task loads it from the REPO substrate); keeping it
        # out of the agent-visible tree replaces the old manifest-move step.
        (scratch / "AGENT_WRITABLE.json").unlink(missing_ok=True)

    head = _substrate_head_sha(repo, project_rel)
    marker = {
        "schema": _MARKER_SCHEMA,
        "task_id": bare,
        "substrate": substrate,
        "uproject": uproject_name,
        "substrate_head": head,
        "composed_at": int(time.time()),
        "removed": {"dirs": len(removed_dirs), "flat": len(removed_flat),
                    "tests": len(removed_tests), "root_maps": len(removed_maps)},
        "config_overlay": overlay_applied,
    }
    if root_maps_kept is not None:
        marker["root_maps_kept"] = root_maps_kept
    if shared_dirs is not None:
        marker["shared_asset_dirs"] = shared_dirs
        marker["shared_assets_kept"] = shared_kept
    if writable_roots is not None:
        marker["writable_roots"] = writable_roots
        marker["writable_baseline"] = writable_baseline
    (scratch / _MARKER).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    log(f"[0] composed graded scratch for {bare} in {time.time()-t0:.1f}s "
        f"({scratch}, substrate {substrate}) — staged out {len(removed_dirs)} "
        f"per-task dir(s), {len(removed_flat)} flat scaffold file(s), "
        f"{len(removed_tests)} fixture file(s), {len(removed_maps)} foreign "
        f"root map file(s); overlay: {overlay_applied or 'none'}")
    return scratch


def staged_marker(scratch_dir: Optional[Path] = None) -> Optional[dict]:
    """Read the .cb-staged marker (None when absent/unreadable)."""
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    try:
        return json.loads((scratch / _MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verify_staged(task_id: str, scratch_dir: Optional[Path] = None, *,
                  substrate: Optional[str] = None) -> List[str]:
    """Compose-verify gate: return problems (empty = clean). Refuse-to-drive
    conditions: marker missing/for another task, the marker's substrate not
    matching the REQUESTED one (``substrate``, when the caller threads it), a
    stale other-substrate ``.uproject`` surviving in the scratch root, a
    foreign per-task dir surviving (e.g. a locked file defeating
    delete_extras), a root-level map outside the marker's recorded keep-set,
    a shared-dir asset outside the marker's kept set (see
    _shared_asset_dirs), any fixture file in the tests module, or
    AGENT_WRITABLE.json present."""
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    bare = task_layout.bare_task_id(task_id)
    problems: List[str] = []

    marker = staged_marker(scratch)
    if not marker:
        return [f"no {_MARKER} marker at {scratch}"]
    if marker.get("task_id") != bare:
        problems.append(f"marker task {marker.get('task_id')!r} != active {bare!r}")

    # Substrate gate: the composed substrate must be the one the active task
    # declares (pre-marker markers default to the default substrate).
    marker_sub = _marker_substrate(marker)
    if substrate is not None and marker_sub != substrate:
        problems.append(
            f"marker substrate {marker_sub!r} != requested {substrate!r} "
            f"(recompose for this task)")
    expected_uproject = marker.get("uproject") or f"{marker_sub}.uproject"
    root_uprojects = sorted(p.name for p in scratch.glob("*.uproject"))
    if expected_uproject not in root_uprojects:
        problems.append(f"scratch root is missing {expected_uproject}")
    for name in root_uprojects:
        if name != expected_uproject:
            problems.append(f"stale other-substrate .uproject in the scratch: {name}")

    for root_rel in task_layout.PER_TASK_ROOTS:
        root = scratch / root_rel
        if not root.is_dir():
            continue
        require_task_like = root_rel.startswith("Content/")
        for child in root.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if name.lower() == bare:
                continue
            if require_task_like and not task_layout.TASK_DIR_RE.match(name):
                continue
            problems.append(f"foreign per-task dir survived staging: {root_rel}/{name}")

    tests_dir = scratch / task_layout.TESTS_MODULE_REL
    if tests_dir.is_dir():
        for p in tests_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(tests_dir).as_posix()
                if (task_layout.classify_tests_rel(rel) is not None
                        or (rel not in task_layout.TESTS_BASE_ALLOWLIST)):
                    problems.append(f"non-base file in tests module: {rel}")

    kept = marker.get("root_maps_kept")
    if isinstance(kept, list):
        maps_dir = scratch / "Content" / "Maps"
        if maps_dir.is_dir():
            for p in sorted(maps_dir.iterdir()):
                if not p.is_file():
                    continue
                for sfx in (".umap", ".uasset"):
                    if p.name.endswith(sfx):
                        if p.name[:-len(sfx)] not in kept:
                            problems.append(
                                f"foreign root-level map survived staging: "
                                f"Content/Maps/{p.name}")
                        break

    # Shared asset-dir police — see _shared_asset_dirs. A marker without the
    # key (no-asset_writable manifest) skips the gate, like root_maps_kept.
    shared_dirs = marker.get("shared_asset_dirs")
    if isinstance(shared_dirs, list):
        kept_set = set(marker.get("shared_assets_kept") or [])
        problems.extend(
            f"leaked shared-dir asset survived staging: {rel}"
            for rel in _assets_under(scratch, [str(d) for d in shared_dirs])
            if rel not in kept_set)

    if (scratch / "AGENT_WRITABLE.json").exists():
        problems.append("AGENT_WRITABLE.json present in the agent-visible tree")
    return problems


def ensure_composed(
    task_id: str,
    *,
    repo: Path = None,
    scratch_dir: Optional[Path] = None,
    task_spec_path: Optional[Path] = None,
    copy_substrate_fn: Optional[Callable] = None,
    on_heal: Optional[Callable[[List[str]], None]] = None,
    log: Callable[[str], None] = print,
) -> List[str]:
    """Compose-if-needed drive gate: recompose on a marker mismatch (task or
    substrate switch, or a marker written by an older schema — one recompose
    upgrades it instead of running with a newer gate disarmed), verify, and
    HEAL a matching-but-DIRTY scratch by recomposing once. The heal covers
    the POLICED classes (foreign per-task dirs, root maps, fixture files,
    stale .uproject, the shared-asset-dir leftovers that used to ride the
    marker-match compose skip straight into the next run's snapshot and
    grade) — a clean-looking same-task repeat still inherits the prior run's
    ACTIVE-task files by design (the marker-match fast path).

    ``on_heal`` (called with the problem list BEFORE the heal recompose) lets
    the caller release resources that would defeat or outlive the reset —
    run_graded uses it to stop a live editor whose in-memory packages could
    resurrect the healed-away leftovers.

    Returns ``verify_staged``'s problems; empty = ready to drive. ``compose``
    raises propagate (a half-composed or unresettable tree must abort
    pre-spend, exactly as in cmd_eval)."""
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    sub = substrate_for(task_spec_path)
    bare = task_layout.bare_task_id(task_id)

    def _compose():
        compose(task_id, repo=repo, scratch_dir=scratch,
                task_spec_path=task_spec_path,
                copy_substrate_fn=copy_substrate_fn, log=log)

    marker = staged_marker(scratch)
    matched = bool(marker) and marker.get("task_id") == bare and \
        _marker_substrate(marker) == sub and \
        marker.get("schema") == _MARKER_SCHEMA
    if not matched:
        _compose()
    problems = verify_staged(task_id, scratch, substrate=sub)
    if problems and matched:
        log(f"[0] staged scratch is DIRTY on a same-task repeat "
            f"({len(problems)} problem(s), e.g. {problems[0]}) — recomposing "
            f"(recomposition IS the reset)")
        if on_heal is not None:
            on_heal(list(problems))
        _compose()
        problems = verify_staged(task_id, scratch, substrate=sub)
    return problems


# --------------------------------------------------------------------------- #
# PRE-DRIVE pristine gate — level 1 of the 2026-08-07 contamination fix.        #
# --------------------------------------------------------------------------- #
#
# WHY A SEPARATE GATE, when recomposition already IS the reset.
# ``verify_staged`` polices STRUCTURE (foreign per-task dirs, root maps,
# fixtures, the shared-asset dirs) and ``ensure_composed``'s fast path skips
# the recompose whenever the marker matches. Neither answers the question a
# graded rep actually needs answered: "is the surface the agent may write
# byte-identical to the substrate baseline, right now, before this drive?"
# On 2026-08-07 a rep that ended ABNORMALLY (EDITOR-GONE) left
# Content/Tasks/gp-glide-stamina-bp/GA_Glide.uasset in the shared scratch and
# the NEXT rep — a different task — graded FAIL on it.
#
# So this runs PRE-DRIVE, on every rep, and never depends on the previous rep
# having exited cleanly: a post-drive cleanup is exactly what an abnormal end
# skips. Its answer is recorded as a one-line provenance fact
# (``scratch_reset``) so a summary can never merely IMPLY a clean scratch.

# The pristine verdict a rep records. "unverified" is NOT a failure — it is
# the honest answer when the substrate ships no readable AGENT_WRITABLE.json
# (or the marker predates schema 3), and it must stay distinguishable from
# "pristine" so nobody reads a disarmed gate as a clean one.
RESET_PRISTINE = "pristine"
RESET_UNVERIFIED = "unverified"


def _reset_status(n: int) -> str:
    return RESET_PRISTINE if not n else f"reset-{n}-paths"


def pristine_residue(scratch_dir: Optional[Path] = None,
                     marker: Optional[dict] = None) -> Optional[List[str]]:
    """Residue in the agent-writable area vs the marker's recorded baseline.

    Returns ``[]`` when pristine, a list of ``"<kind> <rel>"`` strings
    otherwise (``extra`` = a file the baseline never had — the leftover class
    that caused the incident; ``modified``/``missing`` = a baseline file the
    prior rep changed or removed), or ``None`` when the marker carries no
    baseline (schema < 3, or a substrate with no manifest) — the caller
    reports that as ``unverified``."""
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    marker = marker if marker is not None else staged_marker(scratch)
    if not marker:
        return None
    roots = marker.get("writable_roots")
    baseline = marker.get("writable_baseline")
    if not isinstance(roots, list) or not isinstance(baseline, dict):
        return None
    out: List[str] = []
    seen = set()
    for p in _files_under(scratch, [str(r) for r in roots]):
        rel = p.relative_to(scratch).as_posix()
        seen.add(rel)
        want = baseline.get(rel)
        if want is None:
            out.append(f"extra {rel}")
        else:
            try:
                if _sha1(p) != want:
                    out.append(f"modified {rel}")
            except OSError:
                out.append(f"modified {rel}")  # unreadable → treat as dirty
    out.extend(f"missing {rel}" for rel in baseline if rel not in seen)
    return sorted(out)


def _prune_empty_dirs(root: Path, dirs: List[str]) -> None:
    """Delete directories left empty by an extras sweep (a foreign per-task
    FOLDER must not survive as an empty shell — ``verify_staged`` would flag
    it on the next rep, and an empty ``Content/Tasks/<other>/`` reads to a
    human exactly like contamination)."""
    for d in dirs:
        droot = root / d
        if not droot.is_dir():
            continue
        for p in sorted(droot.rglob("*"), key=lambda q: len(q.parts),
                        reverse=True):
            if p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass  # non-empty (or locked) — nothing to prune here


def reset_agent_writable(
    task_id: str,
    *,
    repo: Path = None,
    scratch_dir: Optional[Path] = None,
    task_spec_path: Optional[Path] = None,
    copy_substrate_fn: Optional[Callable] = None,
    log: Callable[[str], None] = print,
) -> dict:
    """Guarantee the agent-writable area is baseline-pristine BEFORE a drive.

    Cheap path first: EXTRA files (the leftover class) are deleted in place —
    a locked survivor raises, exactly like ``compose``, because an un-reset
    leftover riding into a graded submission is the failure this exists to
    prevent. Anything the deletion cannot fix (a baseline file the prior rep
    MODIFIED or DELETED — we hold its hash, not its bytes) escalates to a full
    ``compose`` recomposition, then re-verifies.

    Returns ``{"status": "pristine"|"reset-N-paths"|"unverified",
    "residue": [...]}`` — ``status`` is the one-line provenance fact a run
    summary records; ``residue`` is what was found (empty when pristine).
    Raises only when the reset itself could not be completed."""
    scratch = Path(scratch_dir) if scratch_dir else get_graded_project_dir()
    residue = pristine_residue(scratch)
    if residue is None:
        log("[0] WARN  scratch pristine gate UNVERIFIED — the composed marker "
            "carries no writable baseline (pre-v3 marker, or a substrate with "
            "no AGENT_WRITABLE.json); a leftover from a prior rep could not be "
            "ruled out")
        return {"status": RESET_UNVERIFIED, "residue": []}
    if not residue:
        return {"status": RESET_PRISTINE, "residue": []}

    log(f"[0] !! scratch is NOT pristine pre-drive — {len(residue)} residue "
        f"path(s) from a prior rep (abnormal end?): "
        + ", ".join(residue[:5]) + (" …" if len(residue) > 5 else ""))
    marker = staged_marker(scratch) or {}
    roots = [str(r) for r in (marker.get("writable_roots") or [])]
    only_extras = all(r.startswith("extra ") for r in residue)
    if only_extras:
        for entry in residue:
            _reset_or_refuse(scratch / entry[len("extra "):], "residue file")
        _prune_empty_dirs(scratch, roots)
    else:
        log("[0] residue includes MODIFIED/MISSING baseline files — the marker "
            "holds hashes, not bytes, so recomposing (recomposition IS the "
            "reset)")
        compose(task_id, repo=repo, scratch_dir=scratch,
                task_spec_path=task_spec_path,
                copy_substrate_fn=copy_substrate_fn, log=log)

    left = pristine_residue(scratch)
    if left:
        raise OSError(
            f"scratch reset incomplete: {len(left)} residue path(s) survived "
            f"({', '.join(left[:5])}) — refusing to drive a contaminated "
            f"scratch; close any editor holding it open and rerun")
    log(f"[0] scratch reset to baseline ({len(residue)} path(s) cleared) — "
        f"pristine")
    return {"status": _reset_status(len(residue)), "residue": residue}
