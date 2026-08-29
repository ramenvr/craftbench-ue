"""tasklint — static, no-UE validation of CraftBench task specs (``cb lint``).

The cheap end of "testing an eval". The expensive end is the discrimination
matrix (``cb discriminate``): reference PASS + empty FAIL + gamed FAILs, each a
full L1 build + L2 PIE session on a UE box. This linter is the *static* gate
that runs anywhere (PR CI on a hosted runner, a contributor laptop) in
milliseconds, and catches the spec rot that otherwise only surfaces after a
multi-minute UE session:

  * malformed / missing spec-v2 front matter (legacy H2 specs get a single
    "migrate" WARN — they still parse via the legacy fallback);
  * task id drifting from the task folder name;
  * unknown / unimplemented verifier layer tokens;
  * declared L2 fixtures whose C++ sources don't exist under the substrate's
    tests module, or whose map has no committed ``.umap`` binary (scaffolders
    are RETIRED — a missing binary is an ERROR, there is no re-bake path);
  * introspect scripts that don't exist under tools/verify-single/introspect/;
  * anti-gaming sections outside the mandatory 3-5 entry band;
  * Hard Rule #2 leaks — UE class tokens / plugin / design-pattern vocabulary
    in the agent-visible prompt (heuristic, so WARN not ERROR);
  * discrimination coverage — for tasks on the explicit gold-set list
    (``gold_set.txt``), every anti-gaming note must name a committed
    discrimination variant dir OR an inherited/argued justification with a
    pointer to where it is proven. Opt-in by name only; see the rule's own
    header block for why count-equality is rejected.

Severity model: ERROR = the spec will not run or violates a hard authoring
rule; WARN = heuristic or convention finding a human should look at. Exit 0
when no ERRORs (``--strict`` promotes WARNs), 1 otherwise, 2 on usage errors.

Usage::

    python3 tools/verify-single/tasklint.py tasks/flagship/gp-gas-launch/task.md
    python3 tools/verify-single/tasklint.py --all            # every spec under tasks/
    python3 tools/verify-single/tasklint.py --all --json     # machine-readable
    python3 tools/verify-single/tasklint.py --all --strict   # WARNs fail too

Design notes: ALL structural facts come from ``spec.parse_task_file`` — the
same single parser the runner executes, so there is no second grammar to
drift. Everything here is stdlib-only and must keep working without a UE
install.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

# Make sibling modules importable when run as a script (same pattern as tests/).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import inventory  # noqa: E402  (repo-level doc-vs-git checks; --all only)
from spec import (  # noqa: E402
    Fixture,
    IMPLEMENTED_LAYERS,
    RECOGNIZED_LAYERS,
    TaskSpec,
    _split_h2_sections,
    parse_task_file,
)


# --------------------------------------------------------------------------- #
# Data model                                                                   #
# --------------------------------------------------------------------------- #

ERROR = "error"
WARN = "warn"


@dataclass
class Finding:
    """One lint finding: a named rule + severity + human message."""

    rule: str
    severity: str
    message: str

    def render(self) -> str:
        tag = "ERROR" if self.severity == ERROR else "WARN "
        return f"  {tag} [{self.rule}] {self.message}"


@dataclass
class LintResult:
    """All findings for one task spec."""

    path: Path
    task_id: str
    findings: list[Finding] = field(default_factory=list)
    skipped: bool = False  # non-spec .md (no front matter / metadata) under --all

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == WARN)

    def ok(self, strict: bool = False) -> bool:
        if self.skipped:
            return True
        return self.errors == 0 and (not strict or self.warnings == 0)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "task_id": self.task_id,
            "skipped": self.skipped,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [
                {"rule": f.rule, "severity": f.severity, "message": f.message}
                for f in self.findings
            ],
        }


# --------------------------------------------------------------------------- #
# Local helpers (deliberately NOT imported from run_task — tasklint must stay  #
# runnable standalone; these are conventions, not task.md parsing)             #
# --------------------------------------------------------------------------- #

_UNIMPLEMENTED_LAYERS = frozenset(RECOGNIZED_LAYERS) - frozenset(IMPLEMENTED_LAYERS)

# Task-spec substrate alias -> on-disk UE-projects/<dir> name.
_SUBSTRATE_DIR_ALIASES = {
    "template": "CraftBenchTemplate",
    "lyra": "LyraStarter",
}


def _substrate_dir_name(substrate_key: str) -> str:
    return _SUBSTRATE_DIR_ALIASES.get(substrate_key, substrate_key)


def _strip_class_prefix(name: str) -> str:
    """UE automation-display convention: ``ASanityFunctionalTest`` appears as
    ``SanityFunctionalTest``. Spec authors may use either form."""
    if name and name[0] in ("A", "F"):
        return name[1:]
    return name


def _tests_module_dirs(substrate: Path) -> list[Path]:
    """The verifier-only tests module dir(s), e.g. Source/CraftBenchTests/."""
    src = substrate / "Source"
    if not src.is_dir():
        return []
    return sorted(d for d in src.iterdir()
                  if d.is_dir() and d.name.endswith("Tests"))


def _expected_task_id(spec_path: Path) -> str:
    """Folder-per-task layout: tasks/<set>/<task-id>/task.md joins on the
    folder name; a flat <task-id>.md joins on the file stem."""
    if spec_path.name == "task.md":
        return spec_path.parent.name
    return spec_path.stem


# --------------------------------------------------------------------------- #
# Rules                                                                        #
# --------------------------------------------------------------------------- #

# Hard Rule #2 heuristics (behavior-only prompts). Two detectors:
#   1. UE type-name shape: A/U/F prefix + CamelCase (AActor, UStaticMesh,
#      FTimerManager). Requires lowercase 3rd char so acronyms (API, USA)
#      don't trip it.
#   2. A curated vocabulary of lifecycle/API/plugin/pattern names that a
#      behavior-only prompt has no business containing.
# The prompt-jargon vocabulary (`_UE_CLASS_TOKEN_RE`, `_JARGON_TERMS`,
# `_CLASS_TOKEN_ALLOWLIST`) was removed with its only consumer on 2026-08-17 —
# see the retirement note above `_rule_fixtures_exist`. Kept out rather than
# left orphaned: a table of "forbidden words" that nothing reads is worse than
# no table, because the next author assumes it is enforced.
_PROMPT_SECTION = "Prompt given to the agent"
_ANTI_GAMING_SECTION = "Anti-gaming notes"


def _rule_format(spec_path: Path, raw: str, sections: dict[str, str],
                 ctx: "LintContext") -> list[Finding]:
    """Spec v2 front matter is REQUIRED for new specs; a legacy H2 spec gets
    exactly one WARN telling the author to migrate."""
    spec = ctx.spec
    if spec is None:
        return []
    if spec.legacy:
        return [Finding(
            "legacy-format", WARN,
            "legacy format, migrate: spec has no v2 front-matter block "
            "(--- id/layers/fixtures ---); parsed via the legacy H2 fallback")]
    return []


def _rule_task_id(spec_path: Path, raw: str, sections: dict[str, str],
                  ctx: "LintContext") -> list[Finding]:
    spec = ctx.spec
    if spec is None:
        return []
    expected = _expected_task_id(spec_path)
    if spec.task_id != expected:
        return [Finding(
            "task-id-folder", ERROR,
            f'task id "{spec.task_id}" != task folder "{expected}" '
            "(the runner, reference solutions, and CI join on this)")]
    return []


def _rule_layers(spec_path: Path, raw: str, sections: dict[str, str],
                 ctx: "LintContext") -> list[Finding]:
    spec = ctx.spec
    if spec is None:
        return []
    out: list[Finding] = []
    if not spec.layers:
        out.append(Finding(
            "layers-valid", ERROR,
            "no verifier layers declared / parseable"))
        return out
    for layer in spec.layers:
        if layer not in RECOGNIZED_LAYERS:
            out.append(Finding(
                "layers-valid", ERROR,
                f'unknown verifier layer "{layer}" (recognized: '
                f'{", ".join(RECOGNIZED_LAYERS)})'))
        elif layer in _UNIMPLEMENTED_LAYERS:
            out.append(Finding(
                "layers-valid", WARN,
                f'layer "{layer}" is recognized but not implemented in the '
                "runner (task cannot fully grade today)"))
    # An L2 task must give the runner a way to build the automation filter.
    # (The v2 front-matter parser already enforces this; the legacy fallback
    # can still yield L2 with neither a fixtures block nor a derivable pair.)
    if "L2" in spec.layers and not spec.fixtures:
        if not (spec.map_name and spec.test_class_hint):
            out.append(Finding(
                "l2-fixtures", ERROR,
                "L2 declared but no fixtures are present (and no legacy "
                "(map, FunctionalTest class) pair is derivable) — the "
                "runner cannot construct the RunTests filter"))
    if "L2I" in spec.layers and not spec.introspect_scripts:
        out.append(Finding(
            "l2i-introspect", ERROR,
            "L2I declared but no introspect scripts are listed"))
    return out


def _rule_prompt_required(spec_path: Path, raw: str, sections: dict[str, str],
                          ctx: "LintContext") -> list[Finding]:
    """The agent-visible prompt section is the one body section every spec
    must carry (prompt_extract.py joins on the exact heading)."""
    if sections.get(_PROMPT_SECTION, "").strip():
        return []
    return [Finding(
        "prompt-required", ERROR,
        f'missing or empty required H2 section "## {_PROMPT_SECTION}"')]


# Top-level anti-gaming entries: unindented "- " / "* " bullets or "1."
# numbers. THE single anti-gaming grammar in this file — `_rule_anti_gaming`
# (count) and `_rule_discrimination_coverage` (per-entry text) both go through
# `_anti_gaming_entries`, so there is no second parser to drift.
_ANTI_GAMING_ENTRY_RE = re.compile(r"(?m)^(?:[-*]|\d+\.)\s+\S")


def _anti_gaming_entries(sections: dict[str, str]) -> list[str]:
    """The ``## Anti-gaming notes`` entries, each as its FULL text (the entry
    line plus every continuation line up to the next top-level entry).

    Entries are delimited by ``_ANTI_GAMING_ENTRY_RE``, so ``len()`` of this
    is by construction the same count `_rule_anti_gaming` has always used."""
    block = sections.get(_ANTI_GAMING_SECTION, "")
    starts = [m.start() for m in _ANTI_GAMING_ENTRY_RE.finditer(block)]
    return [block[s:(starts[i + 1] if i + 1 < len(starts) else len(block))]
            for i, s in enumerate(starts)]


def _rule_anti_gaming(spec_path: Path, raw: str, sections: dict[str, str],
                      ctx: "LintContext") -> list[Finding]:
    n = len(_anti_gaming_entries(sections))
    out: list[Finding] = []
    if n < 3:
        out.append(Finding(
            "anti-gaming-count", ERROR,
            f"only {n} anti-gaming entr{'y' if n == 1 else 'ies'} — the "
            "authoring rule requires 3-5 (each pairing a gaming failure mode "
            f'with the verifier defense) under "## {_ANTI_GAMING_SECTION}"'))
    # UPPER BOUND RETIRED 2026-08-17 (owner instruction; the reasoning is
    # decision Q17 of DECISION-DIALOGUE-2026-08-16): the 2026-08-11 decision
    # replaced per-note gaming variants with the mandatory requirements table,
    # so the table now carries the soundness burden the count used to, and an
    # entry count above five measures compliance with a convention that no
    # longer exists. It was also the ONLY blocking branch: it kept four
    # otherwise-complete tasks (gp-dot-aoe-burn-bp, gp-double-jump-stamina-cpp,
    # gp-glide-stamina-cpp, gp-health-attribute-ops-cpp) permanently out of
    # SETTLED for writing MORE anti-gaming analysis than the rule of thumb.
    #
    # The n < 3 ERROR above deliberately STAYS. It is a different check with a
    # different job: it catches a spec that ships no anti-gaming analysis at
    # all (or renames the section away), which is an authoring floor rather
    # than a style bound, and it blocks nothing today because no spec trips it.
    return out


# `_rule_prompt_jargon` was RETIRED 2026-08-17 on the owner's instruction.
#
# It was a confirm-me heuristic by construction — its own message asked a human
# to "confirm these are behavior words" — so it could never resolve mechanically,
# and the corpus-ledger tool routed every hit to the OWNER-EYES verdict, which put
# three tasks in a state no amount of task work could clear. Of its three live
# hits, one was owner-ruled KEEP (kp-engine-source-search's `FCoreDelegates` /
# `FJsonObject`, decision Q9 — the answers the search task exists to make the
# agent find) and the other two were the SAME finding twice: `t0-sanity-bp-log-
# on-beginplay` and `t1-blueprint-graph-on-beginplay` leak `BeginPlay` not in
# prose but through their own ids, which appear in the prompt as the required
# `Content/Tasks/<id>/` path.
#
# That leak is real and is NOT dropped with the rule: it is exactly what
# decision Q15 approved renames for, both tasks were already replaced under D6
# by the Q9 rewords, and the obligation is recorded in each task's notes.md so
# it survives as scheduled work rather than as a permanent warning. Deleting a
# nag is only safe when the thing it nagged about is written down somewhere
# that gets acted on.

def _rule_fixtures_exist(spec_path: Path, raw: str, sections: dict[str, str],
                         ctx: "LintContext") -> list[Finding]:
    spec = ctx.spec
    if spec is None or ctx.repo_root is None:
        return []
    out: list[Finding] = []
    substrate = ctx.repo_root / "UE-projects" / _substrate_dir_name(spec.substrate)
    if not substrate.is_dir():
        out.append(Finding(
            "substrate-exists", ERROR,
            f"substrate directory not found: {substrate}"))
        return out

    tests_dirs = _tests_module_dirs(substrate)

    fixtures = list(spec.fixtures) + list(spec.l3_fixtures)
    if not fixtures and spec.map_name and spec.test_class_hint and "L2" in spec.layers:
        # Legacy single-fixture derivation — lint the derived pair too.
        fixtures = [Fixture(map_name=spec.map_name, test_class=spec.test_class_hint)]

    seen_classes: set[str] = set()
    seen_maps: set[str] = set()
    for fx in fixtures:
        cls = fx.test_class
        if cls not in seen_classes:
            seen_classes.add(cls)
            out.extend(_check_fixture_source(tests_dirs, cls))
        map_name = fx.map_name
        if map_name and map_name not in seen_maps:
            seen_maps.add(map_name)
            out.extend(_check_map(substrate, map_name, ctx.repo_root))
    return out


def _check_fixture_source(tests_dirs: list[Path], cls: str) -> list[Finding]:
    """The fixture class's .h/.cpp must exist under the substrate's tests
    module (flat or in a Tasks/<task-id>/ subfolder)."""
    stem = _strip_class_prefix(cls)
    found = False
    for tests_dir in tests_dirs:
        if any(tests_dir.rglob(f"{stem}.h")) or any(tests_dir.rglob(f"{stem}.cpp")):
            found = True
            break
        # Fallback: the class may live in a differently-named file.
        pat = re.compile(rf"\bclass\s+\w*\s*{re.escape(cls)}\b")
        for h in tests_dir.rglob("*.h"):
            try:
                if pat.search(h.read_text(encoding="utf-8", errors="replace")):
                    found = True
                    break
            except OSError:
                continue
        if found:
            break
    if found:
        return []
    where = ", ".join(f"Source/{d.name}/" for d in tests_dirs) or "Source/*Tests/"
    return [Finding(
        "fixture-source-exists", ERROR,
        f"fixture class {cls}: no {stem}.h/.cpp under {where} (and no "
        "header declares the class) — the L2 leg cannot run")]


_EXTERNAL_ACTOR_REFERENCE_MARKERS = (
    b"WorldExternalActorsReferences",
    b"/Game/__ExternalActors__/",
)
_OFPA_SIDE_ROOTS = ("__ExternalActors__", "__ExternalObjects__")


@lru_cache(maxsize=8)
def _git_tracked_files(repo_root: Path, pattern: str) -> Optional[tuple[str, ...]]:
    """One git inventory per repo/pattern across an ``--all`` lint pass."""
    tracked = inventory.tracked_files(repo_root, pattern)
    return None if tracked is None else tuple(tracked)


def _map_candidates(substrate: Path, map_name: str) -> list[Path]:
    candidates: list[Path] = []
    for content_sub in ("Maps", "Tasks"):
        root = substrate / "Content" / content_sub
        if root.is_dir():
            candidates.extend(
                p for p in root.rglob(f"{map_name}.umap") if p.is_file())
    return sorted(candidates)


def _map_has_external_actor_references(map_path: Path) -> bool:
    """Return true only for a concrete serialized external-actor reference.

    ``bUseExternalActors`` alone is merely a world setting. Requiring both the
    engine reference-container property and an exact external package path
    proves that this package names an OFPA actor without guessing a serialized
    boolean value or parsing private package tables.
    """
    try:
        data = map_path.read_bytes()
    except OSError:
        return False
    return all(marker in data for marker in _EXTERNAL_ACTOR_REFERENCE_MARKERS)


def _check_map_side_packages(
    map_path: Path,
    substrate: Path,
    repo_root: Path,
    tracked_assets: Optional[set[str]],
) -> list[Finding]:
    """Check the side-package mirrors that make an OFPA map runnable."""
    content = substrate / "Content"
    try:
        map_rel = map_path.relative_to(content).with_suffix("")
    except ValueError:
        return []

    side_packages: list[Path] = []
    actor_packages: list[Path] = []
    for side_name in _OFPA_SIDE_ROOTS:
        side_dir = content / side_name / map_rel
        packages = sorted(
            p for p in side_dir.rglob("*.uasset") if p.is_file()
        ) if side_dir.is_dir() else []
        side_packages.extend(packages)
        if side_name == "__ExternalActors__":
            actor_packages = packages

    out: list[Finding] = []
    if _map_has_external_actor_references(map_path) and not actor_packages:
        expected = content / "__ExternalActors__" / map_rel
        out.append(Finding(
            "map-side-packages-tracked", ERROR,
            f"map {map_path.stem}: the main package contains concrete "
            "WorldExternalActorsReferences but its required actor mirror is "
            f"missing or empty: {expected.relative_to(repo_root).as_posix()}"))

    if tracked_assets is not None:
        missing = sorted(
            p.relative_to(repo_root).as_posix()
            for p in side_packages
            if p.relative_to(repo_root).as_posix() not in tracked_assets
        )
        if missing:
            shown = ", ".join(missing[:5])
            more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            out.append(Finding(
                "map-side-packages-tracked", ERROR,
                f"map {map_path.stem}: {len(missing)} OFPA side package(s) "
                f"exist ON DISK but are NOT TRACKED BY GIT: {shown}{more}. "
                "The graded checkout would clone the .umap without the actors "
                "or external objects it depends on."))
    return out


def _check_map(substrate: Path, map_name: str,
               repo_root: Optional[Path] = None) -> list[Finding]:
    """The map must ship as a COMMITTED .umap binary. Scaffolders are
    RETIRED — a missing binary is an ERROR; there is no re-bake path.

    GIT IS THE AUTHORITY, not the filesystem (fixed 2026-08-10). This rule
    said "committed" in its docstring and its message while testing only
    `rglob(...).is_file()` — so a freshly authored, UNCOMMITTED map showed
    GREEN here. That is the worst possible direction for this particular
    check: `run_task.py` clones the graded substrate from **git HEAD** unless
    `--substrate-from-live` is passed, and the `cb eval` graded path only sets
    that under `CB_GRADE_FROM_LIVE=1`. So the certified lane sees no map,
    `locate_map` returns None, and L2 emits a **graded** fail — every
    submission, including a perfect one, recorded as a model failure. Caught on
    `gp-health-attribute-ops-cpp`, whose author had been told by this very rule
    that the map was fine. `inventory.py::tracked_files` was already the
    established git authority; this now uses it.

    Degrades to the filesystem check only when git cannot answer at all, and
    says so, so a non-repo checkout still lints instead of erroring on
    everything."""
    candidates = _map_candidates(substrate, map_name)
    rel_hits: list[str] = []
    tracked = (_git_tracked_files(repo_root, "*.umap")
               if repo_root is not None else None)
    if tracked is not None:
        want = f"/{map_name}.umap".lower()
        sub = substrate.name.lower()
        rel_hits = [t for t in tracked
                    if t.lower().endswith(want) and f"/{sub}/content/" in t.lower()]
        tracked_assets = _git_tracked_files(repo_root, "*.uasset")
        tracked_asset_set = (None if tracked_assets is None
                             else set(tracked_assets))
        if rel_hits:
            out: list[Finding] = []
            rel_hit_set = set(rel_hits)
            matched = [
                p for p in candidates
                if p.relative_to(repo_root).as_posix() in rel_hit_set
            ]
            # Sparse checkouts may expose git metadata without materializing
            # the binary. Preserve the existing git-authority behavior there;
            # a full checkout performs the side-package inspection below.
            for map_path in matched:
                out.extend(_check_map_side_packages(
                    map_path, substrate, repo_root, tracked_asset_set))
            return out
        # Distinguish "never authored" from "authored but not committed" — they
        # need completely different fixes and the message must not conflate them.
        if candidates:
            out = [Finding(
                "map-binary-exists", ERROR,
                f"map {map_name}: {map_name}.umap exists ON DISK but is NOT "
                "TRACKED BY GIT. The graded substrate is cloned from git HEAD, "
                "so the certified lane would find no world and record a GRADED "
                "fail against every submission. `git add` it.")]
            for map_path in candidates:
                out.extend(_check_map_side_packages(
                    map_path, substrate, repo_root, tracked_asset_set))
            return out
        return [Finding(
            "map-binary-exists", ERROR,
            f"map {map_name}: no committed {map_name}.umap under Content/Maps/ "
            "or Content/Tasks/ — scaffolders are retired, the binary is the only "
            "map source, so the L2 leg has no world")]

    # git unavailable — fall back, and label the weaker evidence.
    if candidates:
        return []
    return [Finding(
        "map-binary-exists", ERROR,
        f"map {map_name}: no {map_name}.umap under Content/Maps/ or "
        "Content/Tasks/ (git unavailable, so committed-ness was NOT verified) "
        "— scaffolders are retired, the binary is the only map source, so the "
        "L2 leg has no world")]


def _rule_introspect_exists(spec_path: Path, raw: str, sections: dict[str, str],
                            ctx: "LintContext") -> list[Finding]:
    spec = ctx.spec
    if spec is None or ctx.repo_root is None:
        return []
    out: list[Finding] = []
    introspect_dir = ctx.repo_root / "tools" / "verify-single" / "introspect"
    for script in spec.introspect_scripts:
        if not (introspect_dir / script).is_file():
            out.append(Finding(
                "introspect-script-exists", ERROR,
                f"introspect script {script} not found under "
                "tools/verify-single/introspect/"))
    return out


def _rule_reference_solution(spec_path: Path, raw: str, sections: dict[str, str],
                             ctx: "LintContext") -> list[Finding]:
    """References live folder-local at tasks/<set>/<id>/reference/ and must
    stay inside the substrate's agent-writable set (else grading exits 4)."""
    spec = ctx.spec
    if spec is None:
        return []
    out: list[Finding] = []
    ref_dir = spec_path.parent / "reference"
    if not ref_dir.is_dir():
        out.append(Finding(
            "reference-solution", WARN,
            f"no reference solution at {spec_path.parent.name}/reference/ "
            "— the task cannot be smoke-tested or discrimination-checked"))
        return out
    if ctx.repo_root is None:
        return out
    manifest_path = (ctx.repo_root / "UE-projects"
                     / _substrate_dir_name(spec.substrate) / "AGENT_WRITABLE.json")
    if not manifest_path.is_file():
        return out
    try:
        # Lazy import: tasklint must keep working on substrate-less checkouts
        # (hosted PR CI) where only the manifest-missing early-return applies.
        from sandbox import WritableManifest, scan_submission
        manifest = WritableManifest.load(manifest_path)
        result = scan_submission(ref_dir, manifest)
    except Exception as e:  # defensive: lint must not crash on a bad manifest
        out.append(Finding(
            "reference-solution", WARN,
            f"could not sandbox-scan the reference solution: {e}"))
        return out
    for v in result.violations:
        out.append(Finding(
            "reference-sandbox", ERROR,
            f"reference solution file outside the agent-writable set: "
            f"{v.rel_path} ({v.reason}) — grading it exits 4"))
    out.extend(_reference_not_already_in_substrate(ref_dir, spec, ctx))
    return out


def _reference_not_already_in_substrate(ref_dir: Path, spec, ctx) -> list[Finding]:
    """The committed SUBSTRATE must not already contain the reference's answer.

    Testing a reference means copying it over the scaffold and building. If the
    scaffold is not put back, the answer ships INSIDE the substrate and an EMPTY
    submission passes — the single worst failure this repo can commit, because it
    makes a wrong answer graded correct. It is silent: L1 builds, the reference
    passes, the certificate is issued, and only the `empty` discrimination leg
    notices. It happened twice on 2026-08-17 (t1-door-stays-open… caught before
    commit, t1-shoved-block-slides-on-one-rail caught by `empty PASS(unexpected-
    pass)` AFTER commit and after three certificates had been taken against the
    contaminated tree).

    ERROR when EVERY file the reference provides is byte-identical to the
    substrate's copy — that means the reference contributes nothing, i.e. the
    substrate already holds the answer. WARN per individual identical file, since
    a reference may legitimately ship an unchanged header beside a changed .cpp.
    """
    out: list[Finding] = []
    if ctx.repo_root is None:
        return out
    substrate_root = (ctx.repo_root / "UE-projects"
                      / _substrate_dir_name(spec.substrate))
    files = [f for f in sorted(ref_dir.rglob("*")) if f.is_file()]
    if not files:
        return out
    identical, compared = [], 0
    for f in files:
        rel = f.relative_to(ref_dir)
        target = substrate_root / rel
        if not target.is_file():
            continue
        compared += 1
        try:
            same = f.read_bytes() == target.read_bytes()
        except OSError:
            continue
        if same:
            identical.append(rel.as_posix())
    if compared == 0:
        return out
    if len(identical) == compared:
        out.append(Finding(
            "reference-in-substrate", ERROR,
            f"the committed substrate ALREADY CONTAINS this reference: all "
            f"{compared} file(s) under reference/ are byte-identical to "
            f"UE-projects/{_substrate_dir_name(spec.substrate)}/ "
            f"({', '.join(identical[:3])}"
            f"{'…' if len(identical) > 3 else ''}). An empty submission would "
            f"PASS. Restore the scaffold — you almost certainly copied the "
            f"reference in to test it and did not put it back"))
    else:
        for rel in identical:
            out.append(Finding(
                "reference-in-substrate", WARN,
                f"reference file {rel} is byte-identical to the substrate copy, "
                f"so it contributes nothing to the answer — intended, or a "
                f"scaffold that was never restored?"))
    return out


# --------------------------------------------------------------------------- #
# discrimination-coverage — the GOLD-SET rule                                  #
# --------------------------------------------------------------------------- #
#
# THE BAR: on a gold-listed task, every "## Anti-gaming notes" entry must name
# EITHER (a) a committed discrimination variant directory, OR (b) an explicit
# inherited/argued justification carrying a pointer to where it IS proven.
# Half of "the bar" is argued rather than run today (gp-glide-stamina-cpp ships
# 6 notes and ZERO committed variants), and cloning a gold task clones the
# hole. This rule is the static instrument that names which notes are argued.
#
# THREE DESIGN CONSTRAINTS, all deliberate, none negotiable without re-reading
# The g2 scale-up plan, I0.3:
#
#  1. COUNT-EQUALITY IS REJECTED. A `len(variants) == len(notes)` rule fires on
#     8 of 8 current bp-g2 tasks, OUTLAWS the documented `-bp` inheritance law
#     (a `-bp` twin legitimately inherits its C++ original's behavioral
#     variants), and makes DELETING an honest anti-gaming note the cheapest way
#     to go green. The bar is per-NOTE coverage, and an inherited note that
#     says where it is proven is fully covered.
#
#  2. SEVERITY IS A CONSTANT AND LANDS AS WARN. CI runs `tasklint --all` BEFORE
#     every unit suite (.github/workflows), so an ERROR here fails the lint
#     step and MASKS every downstream suite — over a pre-existing gold-set gap
#     the T1.0 hardening work has not closed yet. Flip the constant to ERROR
#     after one clean CI cycle on the gold set, not before.
#
#  3. OPT-IN BY EXPLICIT LIST, never by set membership or heuristic. A new task
#     must not silently become subject to the gold bar by landing in
#     tasks/bp-g2/, by declaring L2I, or by growing a discrimination/ dir.
#
# WHY THIS DOES NOT PARSE MATRIX.md. `aura_rig.discriminate.parse_matrix` /
# `_extract_substrings` already own the MATRIX row grammar (variant -> expected
# named-FAIL substring), and that is a live-run concern: the substring only
# means something against an L2 log. This rule asks a strictly different,
# static question — "does a committed directory exist for this note?" — which
# it answers from the note text plus a directory listing. Duplicating the row
# parser here would be a second grammar to drift for no gain, and IMPORTING it
# would drag tools/run-agent/ onto tasklint's path, breaking the module's
# stdlib-only, standalone-runnable contract (hosted PR CI has no aura_rig).
# The MATRIX-substring oracle is a SEPARATE piece of work (plan I0.4) and
# belongs wherever discriminate's parser already lives.

# Flip to ERROR after one clean CI cycle on the gold set. See constraint (2).
DISCRIMINATION_COVERAGE_SEVERITY = WARN

# Repo-relative location of the opt-in list.
GOLD_SET_REL_PATH = ("tools", "verify-single", "gold_set.txt")

# A note "names a variant" by writing its committed path: `discrimination/no-cap/`.
# A VARIANT is a directory under discrimination/. The sibling files that
# live there (MATRIX.md, notes) are not variants, and reading one as a
# missing variant dir manufactures a "claims a proof that does not exist"
# warning against a note that correctly cites the matrix as its evidence.
_VARIANT_REF_RE = re.compile(
    r"discrimination/(?!MATRIX\.md(?![A-Za-z0-9._-]))([A-Za-z0-9][A-Za-z0-9._-]*)")
# ...or, for a local variant, just its bare directory name in backticks.
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# The (b) branch: the note must SAY it is inherited/argued, not merely imply it.
_INHERIT_MARKER_RE = re.compile(
    r"(?i)\b(inherit|inherits|inherited|inheriting|inheritance|argued|argument)\b")
# Bare path-ish tokens outside backticks (docs/foo.md, tasks/bp-g2/x/notes.md).
_PATHISH_TOKEN_RE = re.compile(r"[A-Za-z0-9._\-/]*/[A-Za-z0-9._\-/]+")


def _load_gold_set(repo_root: Path) -> frozenset[str]:
    """Parse gold_set.txt: one task per line, bare id or `<set>/<id>`,
    `#` comments, blank lines ignored. A missing file means the rule is
    inert — never an error, so a partial checkout still lints."""
    path = repo_root.joinpath(*GOLD_SET_REL_PATH)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    out: set[str] = set()
    for line in raw.splitlines():
        entry = line.split("#", 1)[0].strip().strip("/")
        if entry:
            out.add(entry)
    return frozenset(out)


def _task_dir(spec_path: Path) -> Path:
    """The task's folder (where reference/ and discrimination/ live)."""
    if spec_path.name == "task.md":
        return spec_path.parent
    sibling = spec_path.parent / spec_path.stem
    return sibling if sibling.is_dir() else spec_path.parent


def _gold_keys(spec_path: Path, task_id: str) -> tuple[str, ...]:
    """Both forms the list may use: bare id and `<set>/<id>`."""
    task_dir = _task_dir(spec_path)
    set_name = task_dir.parent.name
    return (task_id, f"{set_name}/{task_id}")


def _variant_dirs(task_dir: Path) -> set[str]:
    disc = task_dir / "discrimination"
    if not disc.is_dir():
        return set()
    try:
        return {d.name for d in disc.iterdir() if d.is_dir()}
    except OSError:
        return set()


def _variant_is_committed(name: str, task_dir: Path,
                          repo_root: Optional[Path]) -> bool:
    """True when `discrimination/<name>/` is a COMMITTED, NON-EMPTY variant —
    under THIS task, or under this task's own family.

    Three deliberate tightenings over the first cut (2026-08-08 review), each
    closing a way to satisfy the gold bar with no reviewable content:

    1. **git, not the filesystem.** The word here is *committed*, and grading
    materializes from git HEAD — a variant that exists only on disk never
    reaches a grade and never reaches a reviewer. The first cut was a bare
    `Path.is_dir()`, so an untracked local scratch dir passed. `inventory.py`
    already treats git as the authority; same rule here.
    2. **Non-empty.** Nothing checked the directory had files in it, which made
    `mkdir` the cheapest possible way to go green — cheaper than the
    note-deletion loophole this rule's own header rejects count-equality for.
    3. **Family-scoped, not repo-wide.** The cross-task hit exists for ONE
    reason: the `-bp` inheritance law, where `gp-poison-dot-stack-bp` cites
    its `-cpp` original's variant. A repo-wide glob let `gp-crafting-queue`
    be covered by a same-named dir under an unrelated task (measured:
    poison-cpp citing glide-cpp's `no-gas` returned True). Family = the id
    with any `-cpp`/`-bp` suffix stripped, which is exactly the pair the law
    is about.

    Degrades to the filesystem check only when git cannot answer at all, so a
    non-repo checkout still lints rather than reporting everything uncovered."""
    tracked = _tracked_dirs_with_files(repo_root) if repo_root else None

    def _ok(d: Path) -> bool:
        if tracked is None:  # git unavailable — fall back, but still require content
            return d.is_dir() and any(p.is_file() for p in d.rglob("*"))
        try:
            rel = d.relative_to(repo_root).as_posix()
        except ValueError:
            return False
        return rel in tracked

    if _ok(task_dir / "discrimination" / name):
        return True
    if repo_root is None:
        return False
    family = _task_family(task_dir.name)
    try:
        return any(_ok(p)
                   for p in repo_root.glob(f"tasks/*/*/discrimination/{name}")
                   if _task_family(p.parent.parent.name) == family)
    except OSError:
        return False


def _task_family(task_id: str) -> str:
    """The `-cpp`/`-bp` pair an id belongs to (`gp-glide-stamina-bp` ->
    `gp-glide-stamina`). The unit the inheritance law is written about."""
    for suffix in ("-cpp", "-bp"):
        if task_id.endswith(suffix):
            return task_id[: -len(suffix)]
    return task_id


@lru_cache(maxsize=4)
def _tracked_dirs_with_files(repo_root: Path) -> Optional[frozenset]:
    """Repo-relative POSIX dirs under `tasks/**/discrimination/` that contain at
    least one git-tracked file. None when git cannot answer."""
    try:
        cp = subprocess.run(
            ["git", "ls-files", "tasks/*/*/discrimination/*/*"],
            cwd=str(repo_root), capture_output=True, text=True,
            errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return None
    dirs = set()
    for line in (cp.stdout or "").splitlines():
        parts = line.strip().split("/")
        if len(parts) >= 5:  # tasks/<set>/<id>/discrimination/<variant>/...
            dirs.add("/".join(parts[:5]))
    return frozenset(dirs)


def _pointer_resolves(token: str, task_dir: Path,
                      repo_root: Optional[Path]) -> bool:
    """Does this token point at something that exists on disk?

    Accepted pointers: a path relative to the task folder or the repo root
    (`discrimination/no-cap/`, the g2 scale-up plan,
    `tools/verify-single/introspect/gp_poison_dot_stack_bp.py`), or a bare
    task id (`gp-poison-dot-stack-cpp`) that names a task folder."""
    tok = token.strip().strip("`").strip("()[]{}.,;:*_ ").rstrip("/")
    if not tok or any(ch in tok for ch in "<>|*?\"") or tok.startswith("-"):
        return False
    for base in (task_dir, repo_root):
        if base is None:
            continue
        try:
            if (base / tok).exists():
                return True
        except (OSError, ValueError):
            continue
    if "/" not in tok and repo_root is not None:
        try:
            if any(p.is_dir() for p in repo_root.glob(f"tasks/*/{tok}")):
                return True
        except OSError:
            pass
    return False


def _note_lead(entry: str, width: int = 72) -> str:
    """A one-line, ASCII-safe label for a note (first line, collapsed)."""
    flat = " ".join(entry.split())
    flat = flat.encode("ascii", "replace").decode("ascii")
    return flat if len(flat) <= width else flat[:width - 3] + "..."


def _rule_discrimination_coverage(spec_path: Path, raw: str,
                                  sections: dict[str, str],
                                  ctx: "LintContext") -> list[Finding]:
    """Gold-set only: every anti-gaming note must be covered by a committed
    variant dir or an inherited/argued justification with a live pointer."""
    if ctx.repo_root is None:
        return []
    task_id = ctx.spec.task_id if ctx.spec is not None \
        else _expected_task_id(spec_path)
    gold = _load_gold_set(ctx.repo_root)
    if not gold or not any(k in gold for k in _gold_keys(spec_path, task_id)):
        return []  # not opted in — untouched, by design

    entries = _anti_gaming_entries(sections)
    if not entries:
        return []  # `anti-gaming-count` already ERRORs on this

    task_dir = _task_dir(spec_path)
    local_variants = _variant_dirs(task_dir)

    uncovered: list[str] = []
    dangling: list[str] = []
    pending: list[str] = []
    for idx, entry in enumerate(entries, start=1):
        named = dict.fromkeys(_VARIANT_REF_RE.findall(entry))
        committed = {n: _variant_is_committed(n, task_dir, ctx.repo_root)
                     for n in named}
        backticked = [t.strip().strip("/") for t in _BACKTICK_RE.findall(entry)]
        # (a) names a committed discrimination variant directory. A bare
        # backticked name is only meaningful for a LOCAL variant.
        covered = (any(committed.values())
                   or any(t in local_variants for t in backticked))
        # Two very different defects hide behind "not committed", and
        # conflating them cost a real signal (2026-08-08): a variant that is
        # AUTHORED BUT UNSTAGED is a pending `git add` during normal authoring,
        # while a variant that is ABSENT FROM DISK means the note claims a
        # proof nobody ever wrote. Only the second is a lie in the spec, so
        # they are reported separately and the strong invariant ("no gold note
        # cites a proof that does not exist") stays assertable.
        missing = sorted(n for n, ok in committed.items() if not ok)
        absent = sorted(n for n in missing
                        if not (task_dir / "discrimination" / n).is_dir())
        unstaged = [n for n in missing if n not in absent]
        if absent:
            dangling.append(f"note {idx}: {', '.join(absent)}")
        if unstaged:
            pending.append(f"note {idx}: {', '.join(unstaged)}")
        if not covered:
            # (b) an explicit inherited/argued justification + a live pointer.
            if _INHERIT_MARKER_RE.search(entry):
                tokens = backticked + _PATHISH_TOKEN_RE.findall(entry)
                covered = any(_pointer_resolves(t, task_dir, ctx.repo_root)
                              for t in tokens)
        if not covered:
            uncovered.append(f"note {idx} ({_note_lead(entry)})")

    out: list[Finding] = []
    if dangling:
        out.append(Finding(
            "discrimination-coverage", DISCRIMINATION_COVERAGE_SEVERITY,
            f"gold-set task: anti-gaming note(s) cite a discrimination variant "
            f"directory that is NOT committed -> {'; '.join(dangling)} "
            f"(the note claims a proof that does not exist on disk)"))
    if pending:
        out.append(Finding(
            "discrimination-coverage", DISCRIMINATION_COVERAGE_SEVERITY,
            f"gold-set task: variant dir(s) exist on disk but are NOT TRACKED "
            f"by git -> {'; '.join(pending)}. Grading materializes the "
            f"substrate from git HEAD, so an unstaged variant never reaches a "
            f"grade or a reviewer: `git add` them."))
    if uncovered:
        out.append(Finding(
            "discrimination-coverage", DISCRIMINATION_COVERAGE_SEVERITY,
            f"gold-set task: {len(uncovered)} of {len(entries)} anti-gaming "
            f"note(s) name neither a committed discrimination/<variant>/ dir "
            f"nor an inherited/argued defense with a resolvable pointer -> "
            f"{'; '.join(uncovered)}. Commit a one-delta variant, or state "
            f"where the defense is already proven (a repo path, a task-local "
            f"path, or another task id). This is per-note coverage, NOT a "
            f"variant/note count."))
    return out


# --------------------------------------------------------------------------- #
# Standardization rules (2026-08-13)                                           #
#                                                                              #
# A survey of all 59 shipped tasks found uniformity is high wherever lint       #
# exists and drifts wherever it does not: front matter 59/59 and the six core   #
# sections 59/59 (both already checked), but section ORDER 29/59, the §7        #
# requirements table 16/49, per-task UE layout 42/59 (none checked). These      #
# rules close that gap. They land as WARN because the tree violates most of     #
# them today; each flips to ERROR in the same change that fixes its batch, so   #
# the ratchet only tightens. See the task standardization plan.                 #
# --------------------------------------------------------------------------- #

#: Normative H2 order (docs/AUTHORING_TEMPLATE.md:78 — "Section order is
#: normative; do not re-order, omit, or rename headings").
_CANONICAL_H2_ORDER = (
    "Primary concept",
    "Prompt given to the agent",
    "Workspace state pre-task",
    "Verifier specification",
    "Reference solution metadata",
    "Anti-gaming notes",
)
#: Sanctioned trailing sections. "Discrimination" is the modern replacement for
#: "Hidden invariants" (all four 2026-08-12 specs use it); both are allowed.
_OPTIONAL_H2 = ("Hidden invariants", "Discrimination")
#: docs/AUTHORING_TEMPLATE.md. The enum was originally the three coarse scoring
#: buckets, on the stated rationale that "the finer taxonomy lives in
#: capability_bucket, so values like lighting/input are redundant here."
#: **That rationale was measured FALSE (2026-08-14) and the enum widened instead
#: of narrowing four specs into a lie.** capability_bucket carries NONE of the
#: finer values for any spec that uses one:
#:   t1-dawn-fog-lighting-rig        category=lighting   bucket=Content, Data, Assets
#:   t1-walk-animation-footstep-cues category=animation  bucket=Gameplay Programming
#:   kp-fog-and-postprocess-rig      category=lighting   bucket=Tools & Pipeline
#:   kp-typed-input-bindings         category=input      bucket=Gameplay Programming
#: Folding those to "other" would have destroyed real, non-recoverable labels.
#: Note also that `category` has NO consumer today — it is parsed (spec.py) and
#: round-tripped by the migrate script, and nothing scores on it, so "scoring
#: category" in the template describes an intent, not a behaviour. Widening is
#: therefore safe; if a scorer is ever written it must handle these six values.
_CATEGORY_ENUM = frozenset({
    "gameplay", "materials-structural", "other",
    "lighting", "animation", "input",
})

_MD_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_BACKTICKED_RE = re.compile(r"`([^`]+)`")


def _md_tables(text: str) -> list[list[list[str]]]:
    """Every pipe-table in a markdown document as a list of cell-rows.
    Separator rows are dropped; cells keep their raw text."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        m = _MD_ROW_RE.match(line)
        if m is None:
            if current:
                tables.append(current)
                current = []
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if all(c and set(c) <= set("-: ") for c in cells):
            continue  # separator row
        current.append(cells)
    if current:
        tables.append(current)
    return tables


def _submission_tables(text: str) -> list[list[list[str]]]:
    """Tables aura_rig.discriminate.parse_matrix would actually key on.

    Two conditions, both required, because either alone false-positives on a
    well-formed package:

    * the header carries a MESSAGE/SUBSTRING column (discriminate.py:257) —
    matching the word "submission" instead flags every modern package, whose
    §7 requirements table has a column "What a submission could get away
    with";
    * at least one row CLASSIFIES as reference/empty/variant — because a
    requirements table can also name a column "Named failure substring"
    (kp-engine-source-search does), and only row classification separates it
    from the real submission table."""
    out = []
    for tbl in _md_tables(text):
        if not tbl or len(tbl) < 2:
            continue
        lowered = [c.lower() for c in tbl[0]]
        if not any("message" in c or "substring" in c for c in lowered):
            continue
        if any(_classify_row_label(r[0]) for r in tbl[1:] if r):
            out.append(tbl)
    return out


#: Verbatim from aura_rig.discriminate:172 — the runner finds a variant label
#: by SEARCHING the cell, so an annotated label like "`no-cap/` (NEW 08-06)"
#: still classifies. Mirroring this exactly matters: a stricter local copy
#: reports phantom "unrowed variant" warnings for rows the runner does credit.
_VARIANT_DIR_RE = re.compile(r"`?([A-Za-z0-9_-]+)/`?")


def _classify_row_label(first_cell: str) -> Optional[str]:
    """The label parse_matrix would give this row, or None if it would skip it.
    Mirrors aura_rig.discriminate.parse_matrix:270-288 — reference / empty /
    a '<dir>/' variant path found anywhere in the cell. Prose rows classify as
    None, which is why a requirements or anti-gaming table contributes no
    labels."""
    first = (first_cell or "").strip()
    # Strip BACKTICKS ONLY — discriminate.py:271 does `first.strip("`").strip()`.
    # Also stripping markdown emphasis would classify a `**empty**` row that the
    # runner skips, i.e. re-introduce the paraphrase-instead-of-transcribe bug
    # this function exists to avoid (review catch).
    plain = first.strip("`").strip()
    if not plain:
        return None
    noslash = plain.rstrip("/")
    if ("reference-solution" in noslash or noslash.endswith("/reference")
            or noslash == "reference"):
        return "reference"
    if plain.lower().startswith("empty"):
        return "empty"
    m = _VARIANT_DIR_RE.fullmatch(plain) or _VARIANT_DIR_RE.search(plain)
    if m and "/" in first and "reference-solution" not in plain:
        return m.group(1)
    return None


def _matrix_path(spec_path: Path) -> Path:
    return spec_path.parent / "discrimination" / "MATRIX.md"


def _rule_section_order(spec_path: Path, raw: str, sections: dict[str, str],
                        ctx: "LintContext") -> list[Finding]:
    """The canonical H2s must appear in the normative order; 30/59 specs carry
    the legacy shape (anti-gaming hoisted above primary concept)."""
    seen = [h for h in sections if h in _CANONICAL_H2_ORDER]
    expected = [h for h in _CANONICAL_H2_ORDER if h in sections]
    if seen != expected:
        return [Finding(
            "spec-section-order", WARN,
            "H2 sections out of normative order: got %s | expected %s"
            % (" > ".join(seen), " > ".join(expected)))]
    return []


def _rule_h2_allowlist(spec_path: Path, raw: str, sections: dict[str, str],
                       ctx: "LintContext") -> list[Finding]:
    """An unknown H2 is either drift or content that belongs inside a
    canonical section."""
    allowed = set(_CANONICAL_H2_ORDER) | set(_OPTIONAL_H2)
    extra = [h for h in sections if h not in allowed]
    if extra:
        return [Finding("spec-h2-allowlist", WARN,
                        "non-canonical H2: " + ", ".join(repr(h) for h in extra))]
    return []


def _rule_category_enum(spec_path: Path, raw: str, sections: dict[str, str],
                        ctx: "LintContext") -> list[Finding]:
    spec = ctx.spec
    if spec is None:
        return []
    value = getattr(spec, "category", None)
    if not value:
        return [Finding("spec-category-enum", WARN,
                        "front matter has no `category:` key")]
    if value not in _CATEGORY_ENUM:
        return [Finding(
            "spec-category-enum", WARN,
            "category %r outside the documented enum (%s) — the finer taxonomy "
            "belongs in capability_bucket"
            % (value, " | ".join(sorted(_CATEGORY_ENUM))))]
    return []


def _rule_discrimination_required(spec_path: Path, raw: str,
                                  sections: dict[str, str],
                                  ctx: "LintContext") -> list[Finding]:
    """A task shipping a reference must ship the oracle proving it
    discriminates."""
    ref = spec_path.parent / "reference"
    if not ref.is_dir() or not any(ref.rglob("*")):
        return []
    if not _matrix_path(spec_path).is_file():
        return [Finding("discrimination-required", WARN,
                        "ships reference/ but has no discrimination/MATRIX.md")]
    return []


def _rule_matrix_structure(spec_path: Path, raw: str, sections: dict[str, str],
                           ctx: "LintContext") -> list[Finding]:
    """Three MATRIX invariants the discriminate runner depends on:

    * exactly ONE submission-labelled table — parse_matrix returns a dict keyed
    by row label, so a second table silently overwrites rows;
    * each expected-message cell holds exactly ONE backticked literal —
    grade_leg matches ALL of them, so a second literal (a source delta that is
    never logged, an ellipsis-spliced printf template) makes the leg
    uncreditable;
    * those literals are ASCII — the log is written UTF-8 and read back cp1252,
    so anything else becomes mojibake and the match silently misses.
    """
    path = _matrix_path(spec_path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [Finding("matrix-structure", WARN, f"cannot read MATRIX.md: {e}")]

    findings: list[Finding] = []
    tables = _submission_tables(text)

    # The overwrite trap is not "two tables" — parse_matrix builds a dict keyed
    # by CLASSIFIED row label, so the trap is armed only when more than one
    # table yields labels, and it has actually FIRED when a label repeats.
    per_table = [[lab for lab in (_classify_row_label(r[0]) for r in tbl[1:] if r)
                  if lab] for tbl in tables]
    classifying = [labs for labs in per_table if labs]
    if len(classifying) > 1:
        findings.append(Finding(
            "matrix-one-submission-table", WARN,
            "%d tables yield submission row labels; parse_matrix keys by label, "
            "so a later table can silently overwrite an earlier row"
            % len(classifying)))
    flat = [lab for labs in classifying for lab in labs]
    dupes = sorted({lab for lab in flat if flat.count(lab) > 1})
    if dupes:
        findings.append(Finding(
            "matrix-duplicate-row-label", WARN,
            "row label(s) defined more than once — last one wins and the "
            "earlier leg's expectation is silently discarded: "
            + ", ".join(dupes)))

    for tbl in tables:
        header = [c.lower() for c in tbl[0]]
        col = next((i for i, c in enumerate(header)
                    if "substring" in c or "message" in c), None)
        over_col = next((i for i, c in enumerate(header) if "overall" in c),
                        1 if len(header) > 1 else None)
        if col is None:
            continue
        for row in tbl[1:]:
            if col >= len(row):
                continue
            cell = row[col]
            label = row[0] if row else "?"
            # PASS rows carry descriptive prose, never an assertion:
            # discriminate.py:298 sets `substrings = () if expect_pass else ...`,
            # so requiring a literal there would invent a rule the runner does
            # not have (review catch).
            overall = row[over_col] if over_col is not None and over_col < len(row) else ""
            if "pass" in overall.lower() and "fail" not in overall.lower():
                continue
            if not cell or cell.strip("*") in {"", "—", "-", "–"}:
                continue
            lits = _BACKTICKED_RE.findall(cell)
            if not lits:
                # Worse than too many: with no backticked literal,
                # _extract_substrings falls back to the de-noised WHOLE CELL, so
                # prose becomes the "named substring" — it can match for reasons
                # unrelated to the gate, or never match at all.
                findings.append(Finding(
                    "matrix-row-no-literal", WARN,
                    "row %s is a FAIL row with no backticked literal; the "
                    "runner falls back to matching the whole prose cell, so the "
                    "leg is credited on prose rather than on its gate" % label))
            if len(lits) > 1:
                findings.append(Finding(
                    "matrix-row-single-literal", WARN,
                    "row %s carries %d backticked literals; grade_leg matches "
                    "ALL of them, so the leg is uncreditable unless every one "
                    "is logged verbatim" % (label, len(lits))))
            for lit in lits:
                if any(ord(ch) > 127 for ch in lit):
                    findings.append(Finding(
                        "matrix-row-ascii", WARN,
                        "row %s expects a non-ASCII literal (%r) — cp1252 "
                        "read-back makes this miss" % (label, lit[:40])))
    return findings


def _rule_matrix_variant_bijection(spec_path: Path, raw: str,
                                   sections: dict[str, str],
                                   ctx: "LintContext") -> list[Finding]:
    """A committed variant dir with no MATRIX row runs as a leg that can never
    be credited."""
    path = _matrix_path(spec_path)
    if not path.is_file():
        return []
    try:
        dirs = {p.name for p in path.parent.iterdir() if p.is_dir()}
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not dirs:
        return []
    # Use the shared classifier, not a local approximation: row labels carry
    # annotations ("`no-cap/` (NEW 2026-08-06)") that only the runner's search
    # fallback resolves. An approximation here reports rows as unrowed that the
    # runner credits perfectly well.
    labels = {lab for tbl in _submission_tables(text) for row in tbl[1:]
              if row for lab in [_classify_row_label(row[0])] if lab}
    unrowed = sorted(d for d in dirs if d not in labels)
    if unrowed:
        return [Finding(
            "matrix-variant-unrowed", WARN,
            "variant dir(s) with no MATRIX row (the leg runs but cannot be "
            "credited): " + ", ".join(unrowed))]
    return []


#: Words a row uses to DISCLOSE that its variant is not on disk. A disclosed
#: row is still counted by the dossier, but the author is not hiding it, so the
#: rule stays quiet rather than firing on a sentence that explains itself (the
#: nuisance failure mode `check_matrix_status_staleness` records in its own
#: docstring).
_UNBACKED_DISCLOSURES = ("unauthored", "absent from disk", "does not exist",
                         "not on disk", "never run on this task")


def _rule_matrix_row_unbacked(spec_path: Path, raw: str,
                              sections: dict[str, str],
                              ctx: "LintContext") -> list[Finding]:
    """A MATRIX variant ROW with no directory claims evidence that cannot exist.

    THE EXACT INVERSE of ``matrix-variant-unrowed`` above, and the direction
    nothing checked until 2026-08-17. Measured that day: 9 undisclosed rows
    across 3 tasks, and `cb discriminate` printed **discriminated: YES, exit 0**
    for `bp/t1-blueprint-graph-on-beginplay` after running only its reference
    and empty legs, while its MATRIX rows and the review dossier both credited
    it with FOUR variant legs.

    Why the asymmetry mattered. `cb discriminate` discovers legs from DISK, so
    an unbacked row is never executed and costs no wrong verdict — it costs
    EVIDENCE. `the corpus-ledger tool.py` fills its leg count from parsed ROWS (:237),
    computes only `committed - rowed` (:98), and gates the SETTLED verdict on
    that row count (:111). So a task could read `Y/Y/4`, qualify as settled on
    leg count, and have nothing but the FR-017 smoke floor behind it.

    Scoped to `_submission_tables()` for the same reason the sibling rule is:
    the runner's own two-condition filter keeps calibration/requirements/
    anti-gaming rows out, so prose like `Content/Tasks/...`, `B/D (4 applies)`
    or `not a corrupt/partial file set` does not mint a phantom leg. One
    residual is accepted: a task whose tables are ambiguous enough to trip
    `matrix-one-submission-table` can surface one extra label, and that
    warning is itself the instruction to fix the table.
    """
    path = _matrix_path(spec_path)
    if not path.is_file():
        return []
    try:
        dirs = {p.name for p in path.parent.iterdir() if p.is_dir()}
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    undisclosed, disclosed = [], []
    for tbl in _submission_tables(text):
        for row in tbl[1:]:
            if not row:
                continue
            label = _classify_row_label(row[0])
            if not label or label in ("reference", "empty") or label in dirs:
                continue
            blob = " ".join(row).lower()
            (disclosed if any(d in blob for d in _UNBACKED_DISCLOSURES)
             else undisclosed).append(label)
    if not undisclosed:
        return []
    msg = ("MATRIX variant row(s) with NO directory on disk — the leg is never "
           "run, yet the dossier counts it as evidence: "
           + ", ".join(sorted(set(undisclosed))))
    if disclosed:
        msg += ("  (also unbacked but DISCLOSED in the row, so not counted here: "
                + ", ".join(sorted(set(disclosed))) + ")")
    return [Finding("matrix-row-unbacked", WARN, msg)]

#: Base classes whose subclass, when named as a level's game mode, REPLACES
#: ``GlobalDefaultGameMode`` and therefore inherits none of its wiring.
_GAME_MODE_BASES = ("AGameModeBase", "AGameMode")

#: An author's explicit statement that this map is not meant to be driven, which
#: discharges ``game-mode-no-player-controller``. Deliberately a specific phrase,
#: not a loose keyword: it must be impossible to satisfy by accident, and writing
#: it should feel like making a claim. Same disclosure-is-rewarded design as
#: ``_UNBACKED_DISCLOSURES`` — a check that fires on a sentence explaining why it
#: should not fire trains people to ignore it.
_NO_PAWN_DISCLOSURES = ("no drivable pawn",)


def _rule_game_mode_supplies_player(spec_path: Path, raw: str,
                                    sections: dict[str, str],
                                    ctx: "LintContext") -> list[Finding]:
    """A ThirdPerson task game mode that never names a ``PlayerControllerClass``.

    Naming a task game mode REPLACES ``GlobalDefaultGameMode``, which is where a map
    overriding nothing gets its player controller. Omit it and the player lands on a
    bare ``APlayerController`` — no ``DefaultMappingContexts`` property at all, so no
    Enhanced Input mapping context is applied and NO keypress reaches the pawn.

    This must be a LINT rule because no gate can see it: every L2 fixture drives its
    pawn through ``AddMovementInput`` and never presses a key, so a map with a dead
    keyboard grades byte-identically to a working one. Only a human notices — and a
    hand audit of the four known cases missed a fifth that this sweep found.

    Scoped narrowly on purpose. ThirdPerson only: ``CraftBenchTemplate``'s
    ``GlobalDefaultGameMode`` is a bare ``GameModeBase`` with nothing to inherit, so
    firing there is noise. And WARN, not ERROR: a task may legitimately forbid input
    (``t2-hud-layout-and-countdown`` does), which the exact phrase "no drivable pawn"
    in the spec discharges.
    """
    spec = ctx.spec
    if spec is None or ctx.repo_root is None:
        return []
    if _substrate_dir_name(spec.substrate) != "ThirdPerson":
        return []
    # The author has stated this map is not meant to be driven. Honour it — the
    # message below promises this escape, so it has to exist, or the rule tells
    # authors to do something with no effect.
    lowered = raw.lower()
    if any(d in lowered for d in _NO_PAWN_DISCLOSURES):
        return []
    task_dir = (ctx.repo_root / "UE-projects" / "ThirdPerson"
                / "Source" / "ThirdPerson" / "Tasks" / spec.task_id)
    if not task_dir.is_dir():
        return []

    offenders: list[str] = []
    for header in sorted(task_dir.glob("*.h")):
        try:
            hdr = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Only a class that DERIVES from a game-mode base replaces the default.
        if not any(re.search(r":\s*public\s+%s\b" % base, hdr)
                   for base in _GAME_MODE_BASES):
            continue
        impl = header.with_suffix(".cpp")
        try:
            body = impl.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # A header with no companion .cpp cannot set anything.
            body = ""
        if "PlayerControllerClass" not in body:
            offenders.append(header.stem)

    if not offenders:
        return []
    return [Finding(
        "game-mode-no-player-controller", WARN,
        "ThirdPerson task game mode(s) never set PlayerControllerClass: "
        + ", ".join(offenders)
        + " — naming a game mode REPLACES GlobalDefaultGameMode, so the player "
          "lands on a bare APlayerController with no DefaultMappingContexts and "
          "NO keypress reaches the pawn. Invisible to every L2 fixture (they all "
          "drive via AddMovementInput), so only a human notices. Set it, or state "
          "in the spec why this map needs \"no drivable pawn\" (that exact phrase "
          "discharges this rule).")]


def _rule_matrix_requirements_table(spec_path: Path, raw: str,
                                    sections: dict[str, str],
                                    ctx: "LintContext") -> list[Finding]:
    """The checklist §7 requirements table became mandatory 2026-08-11; 33 of
    49 packages predate it."""
    path = _matrix_path(spec_path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if re.search(r"(?im)^#{2,3}\s+Requirements table", text) is None:
        return [Finding("matrix-requirements-table", WARN,
                        "no '## Requirements table' — the §7 soundness artifact")]
    return []


#: Minimum literal length compared by fixture-fail-unique.
_FAIL_LITERAL_MIN_LEN = 6

_FINISHTEST_FAILED_RE = re.compile(
    r"FinishTest\s*\(\s*EFunctionalTestResult::Failed\s*,(.{0,4000}?)\)\s*;", re.S)
_TEXT_LITERAL_RE = re.compile(r'TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)')


def _rule_fixture_fail_literals(spec_path: Path, raw: str,
                                sections: dict[str, str],
                                ctx: "LintContext") -> list[Finding]:
    """Two laws over a task's own fixture sources: FAIL text is ASCII-only, and
    no two gates share a literal (a shared message makes the MATRIX unable to
    say WHICH gate fired)."""
    spec = ctx.spec
    root = ctx.repo_root
    if spec is None or root is None or not getattr(spec, "fixtures", None):
        return []
    findings: list[Finding] = []
    for fixture in spec.fixtures:
        cls = _strip_class_prefix(str(getattr(fixture, "test_class", "") or ""))
        if not cls:
            continue
        for src_path in root.glob(
                "UE-projects/*/Source/CraftBenchTests/**/%s.cpp" % cls):
            try:
                src = src_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            seen: dict[str, int] = {}
            for block in _FINISHTEST_FAILED_RE.findall(src):
                for lit in _TEXT_LITERAL_RE.findall(block):
                    if any(ord(ch) > 127 for ch in lit):
                        findings.append(Finding(
                            "fixture-fail-ascii", WARN,
                            "%s: non-ASCII in a Failed message (%r) — cp1252 "
                            "read-back turns it to mojibake"
                            % (src_path.name, lit[:48])))
                    # Short fragments ("failed", "%s") repeat harmlessly and
                    # are not what a MATRIX row names, so a floor is needed —
                    # but 12 chars silently skipped real sentinel-style
                    # collisions. 6 keeps the noise out and the message below
                    # states the floor rather than hiding it (review catch).
                    key = lit.strip()
                    if len(key) >= _FAIL_LITERAL_MIN_LEN:
                        seen[key] = seen.get(key, 0) + 1
            for lit, n in sorted(seen.items()):
                if n > 1:
                    findings.append(Finding(
                        "fixture-fail-unique", WARN,
                        "%s: %d gates share the FAIL literal %r (literals of "
                        "at least %d chars are compared) — the matrix cannot "
                        "tell which fired"
                        % (src_path.name, n, lit[:48], _FAIL_LITERAL_MIN_LEN)))
    return findings


_RULES: tuple[Callable[..., list[Finding]], ...] = (
    _rule_section_order,
    _rule_h2_allowlist,
    _rule_category_enum,
    _rule_discrimination_required,
    _rule_matrix_structure,
    _rule_matrix_variant_bijection,
    _rule_matrix_row_unbacked,
    _rule_matrix_requirements_table,
    _rule_game_mode_supplies_player,
    _rule_fixture_fail_literals,
    _rule_format,
    _rule_task_id,
    _rule_layers,
    _rule_prompt_required,
    _rule_anti_gaming,
    _rule_fixtures_exist,
    _rule_introspect_exists,
    _rule_reference_solution,
    _rule_discrimination_coverage,
)


# --------------------------------------------------------------------------- #
# Engine                                                                       #
# --------------------------------------------------------------------------- #


@dataclass
class LintContext:
    """Shared per-run facts every rule may consult."""

    repo_root: Optional[Path]
    spec: Optional[TaskSpec] = None  # set per task before rules run


def lint_task(spec_path: Path, ctx: LintContext) -> LintResult:
    """Run every rule against one task spec. Never raises on bad input."""
    try:
        raw = spec_path.read_text(encoding="utf-8")
    except OSError as e:
        r = LintResult(path=spec_path, task_id=_expected_task_id(spec_path))
        r.findings.append(Finding("readable", ERROR, f"cannot read spec: {e}"))
        return r

    sections = _split_h2_sections(raw)
    result = LintResult(path=spec_path, task_id=_expected_task_id(spec_path))

    try:
        ctx.spec = parse_task_file(spec_path)
        result.task_id = ctx.spec.task_id
    except Exception as e:
        # A malformed v2 front-matter block (or any parser rejection) is an
        # ERROR — front matter is required to be well-formed for new specs.
        ctx.spec = None
        result.findings.append(Finding(
            "parseable", ERROR,
            f"spec.parse_task_file failed: {e}"))

    for rule in _RULES:
        try:
            result.findings.extend(rule(spec_path, raw, sections, ctx))
        except Exception as e:  # a rule bug must not take down the lint run
            result.findings.append(Finding(
                "lint-internal", WARN,
                f"rule {rule.__name__} crashed: {e}"))
    return result


def is_task_spec(path: Path) -> bool:
    """A .md counts as a task spec iff it opens with a v2 front-matter block
    or (legacy) declares the metadata H2 section."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = raw.splitlines()
    # BOM/whitespace-tolerant, in lockstep with spec.parse_front_matter — a
    # BOM'd v2 spec must still be discovered (and then lint its parse result).
    if lines and lines[0].lstrip("﻿").strip() == "---":
        return True
    return "## Task ID and metadata" in raw


def discover_specs(tasks_dir: Path) -> list[Path]:
    """All task specs under tasks/ (recursive), skipping docs like CATALOG.md."""
    return sorted(
        p for p in tasks_dir.rglob("*.md")
        if is_task_spec(p)
    )


def find_repo_root(start: Path) -> Optional[Path]:
    """Walk up from ``start`` to the directory containing ``tasks/``."""
    for cand in (start, *start.parents):
        if (cand / "tasks").is_dir() and (cand / "tools" / "verify-single").is_dir():
            return cand
    return None


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tasklint",
        description="Static, no-UE lint for CraftBench task specs.",
    )
    p.add_argument("specs", nargs="*", type=Path,
                   help="task spec .md paths (omit with --all)")
    p.add_argument("--all", action="store_true",
                   help="lint every task spec under <repo>/tasks/")
    p.add_argument("--repo-root", type=Path, default=None,
                   help="repo root (default: auto-detected)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="emit machine-readable JSON instead of text")
    p.add_argument("--strict", action="store_true",
                   help="exit nonzero on WARN findings too")
    p.add_argument("--no-inventory", action="store_true",
                   help="skip the repo-level doc-inventory checks (--all only)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    repo_root = args.repo_root or find_repo_root(_HERE)
    if repo_root is not None:
        repo_root = repo_root.resolve()

    targets: list[Path] = [p for p in args.specs]
    if args.all:
        if repo_root is None:
            print("tasklint: --all needs a repo root (pass --repo-root)",
                  file=sys.stderr)
            return 2
        targets.extend(discover_specs(repo_root / "tasks"))
    if not targets:
        print("tasklint: nothing to lint (pass spec paths or --all)",
              file=sys.stderr)
        return 2

    ctx = LintContext(repo_root=repo_root)

    results: list[LintResult] = []
    for t in targets:
        # Explicitly-passed non-spec .md (docs like CATALOG.md, set READMEs,
        # future NOTES.md) are SKIPPED, not error-stormed — the PR gate passes
        # touched paths verbatim and must not fail on a docs file.
        if t.is_file() and not is_task_spec(t):
            results.append(LintResult(path=t, task_id=t.stem, skipped=True))
            continue
        results.append(lint_task(t, ctx))

    # Repo-level inventory (only on the full sweep — a narrowed `cb lint --task
    # <id>` must stay about that spec). These are the hand-maintained docs that
    # restate machine-derivable facts: docs/MAPS.md, tasks/CATALOG.md.
    inv: list = []
    if args.all and not args.no_inventory and repo_root is not None:
        inv = inventory.check_repo_inventory(repo_root)

    inv_errors = sum(1 for f in inv if f.severity == "error")
    inv_warnings = sum(1 for f in inv if f.severity == "warn")
    ok = (all(r.ok(strict=args.strict) for r in results)
          and inv_errors == 0 and (not args.strict or inv_warnings == 0))

    if args.as_json:
        print(json.dumps({
            "ok": ok,
            "strict": args.strict,
            "results": [r.to_dict() for r in results],
            "inventory": [{"rule": f.rule, "severity": f.severity,
                           "message": f.message} for f in inv],
        }, indent=2))
        return 0 if ok else 1

    n_err = sum(r.errors for r in results)
    n_warn = sum(r.warnings for r in results)
    for r in results:
        if r.skipped:
            print(f"SKIP  {r.task_id}  (not a task spec)  {r.path}")
            continue
        verdict = "PASS" if r.ok(strict=args.strict) else "FAIL"
        print(f"{verdict}  {r.task_id}  ({r.errors} error(s), "
              f"{r.warnings} warning(s))  {r.path}")
        for f in r.findings:
            print(f.render())
    if args.all and not args.no_inventory:
        # Always announce the verdict: a silent pass is indistinguishable from
        # a check that never ran.
        print("\nREPO INVENTORY  (docs vs what git tracks)")
        print(inventory.render(inv) if inv
              else "  OK  docs/MAPS.md + tasks/CATALOG.md agree with git")
    print(f"\ntasklint: {len(results)} spec(s), {n_err + inv_errors} error(s), "
          f"{n_warn + inv_warnings} warning(s) -> {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
