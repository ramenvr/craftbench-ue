"""Render the central benchmark preamble (tasks/PREAMBLE.md) for a task.

The preamble is the uniform prompt contract every backend prepends to every
task prompt (unattended-run rules, the active task's scaffold files, the
writable roots, and — on the aura paths — a fresh-from-disk excerpt of the
scaffold contents that replaces the client's own stale context injection).

The WORDING lives entirely in tasks/PREAMBLE.md so it can be tuned without a
code change; this module only fills placeholders from machine-readable
sources:

  * writable/asset roots        UE-projects/<substrate>/AGENT_WRITABLE.json
  * editable config files       the same manifest's `config_writable`, narrowed
                                to the files THIS TASK's spec licenses via
                                `config_allow` (see _config_files_for_task)
  * scaffold files (foldered)   Source/CraftBenchTemplate/Tasks/<id>/ listing
                                + Content/Tasks/<id>/ asset baselines
  * scaffold files (flat)       the "for task <id>" header-marker scan
                                (fairness._declared_tasks — the same scan task
                                isolation uses, so prompt and staging can never
                                disagree about which files belong to the task)

Rendered output carries a sha256 (over the rendered text) so every run's
summary can pin exactly which preamble the agent saw.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fairness import _bare_task_id, _declared_tasks  # noqa: E402

TEMPLATE_REL = Path("tasks") / "PREAMBLE.md"
_SUBSTRATE_REL = Path("UE-projects") / "CraftBenchTemplate"
_MANIFEST_NAME = "AGENT_WRITABLE.json"
_WRITABLE_MODULE_REL = Path("Source") / "CraftBenchTemplate"
_TASKS_SUBDIR = "Tasks"
_CONTENT_TASKS_REL = Path("Content") / "Tasks"

# Only text sources are excerpted (binary .uasset baselines are named but not
# inlined). Total excerpt is capped so the prompt stays lean.
_EXCERPT_SUFFIXES = (".h", ".cpp", ".cs", ".ini")
_EXCERPT_CAP_BYTES = 8192

_EXCERPT_HEADER = (
    "\n# Current scaffold contents (rendered from disk at run start)\n"
)


@dataclass
class Preamble:
    text: str            # the rendered preamble, ready to prepend
    sha: str             # sha256 hex of `text` (run provenance)
    scaffold_files: List[str]  # substrate-relative paths named in the prompt


def _strip_template_comment(md: str) -> str:
    """Drop the leading <!-- ... --> maintainer comment — it documents the
    template for EDITORS and must never reach the agent."""
    s = md.lstrip()
    if s.startswith("<!--"):
        end = s.find("-->")
        if end != -1:
            s = s[end + 3:]
    return s.lstrip("\n")


def task_substrate_root(task_id: str, repo: Path) -> Optional[Path]:
    """``UE-projects/<substrate>`` for THIS TASK, read from its spec's
    ``substrate:`` key. ``None`` when the task cannot be resolved.

    WHY THIS EXISTS (measured 2026-08-08, and it made a whole task family
    unwinnable). Both manifest lookups below used to fall back to the DEFAULT
    substrate, so a ThirdPerson task's prompt was rendered from
    CraftBenchTemplate's AGENT_WRITABLE.json and told the agent

        "You may create new files only under: Source/CraftBenchTemplate/, …"

    On a `-bp` task that is harmless BY LUCK — the deliverable is a .uasset
    under Content/Tasks/, which both manifests share, so the error was
    invisible for a week. On `-cpp`, where the deliverable IS C++ source, the
    agent obediently wrote into Source/CraftBenchTemplate/ — a directory the
    ThirdPerson module does not compile and the sandbox does not accept — and
    the whole submission evaporated. deepseek-v4-pro reasoned it out loud:
    "The Source/CraftBenchTemplate/ directory isn't part of the ThirdPerson
    module's compilation paths. Let me add it to the Build.cs". It did exactly
    what it was told; the prompt was wrong. That is a harness fault landing as
    a model FAIL, the one thing the verdict contract forbids.

    Uses the canonical resolver + parser (``aura_rig.tasks.resolve_task_path``,
    ``spec``) rather than re-deriving the layout — imported lazily so this
    module keeps no import-time dependency on the rig package."""
    try:
        from aura_rig.tasks import resolve_task_path  # noqa: PLC0415
        import spec as _taskspec                      # noqa: PLC0415
        path = resolve_task_path(Path(repo), task_id)
        if not path:
            return None
        substrate = _taskspec.parse_task_file(path).substrate
        return Path(repo) / "UE-projects" / substrate if substrate else None
    except Exception:      # noqa: BLE001 - never break prompt rendering
        return None


def _manifest_for(substrate_root: Path, repo: Path,
                  task_substrate: Optional[Path] = None) -> Path:
    """The AGENT_WRITABLE.json to render the contract from.

    Preference order, and the middle one is the fix: the given root (the live
    graded project when it ships a manifest) -> **THIS TASK'S substrate in the
    repo** -> the default substrate. The C1 graded scratch deliberately ships
    without a manifest, so the fallback is the ACTIVE path in every aura run —
    which is precisely why it must not be substrate-blind."""
    here = substrate_root / _MANIFEST_NAME
    if here.exists():
        return here
    if task_substrate is not None:
        theirs = task_substrate / _MANIFEST_NAME
        if theirs.exists():
            return theirs
    return repo / _SUBSTRATE_REL / _MANIFEST_NAME


def _writable_module_rel(substrate_root: Path,
                         manifest_path: Optional[Path] = None) -> Path:
    """``Source/<game module>`` for THIS substrate — from ``game_module`` in
    ``manifest_path`` (default: the manifest sitting in ``substrate_root``),
    else the default module name (byte-identical for CraftBenchTemplate, whose
    game_module IS the default)."""
    try:
        path = manifest_path or (substrate_root / _MANIFEST_NAME)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        module = manifest.get("game_module")
        if module:
            return Path("Source") / module
    except (OSError, ValueError):
        pass
    return _WRITABLE_MODULE_REL


# --- the write-scope contract -----------------------------------------------
#
# The ALLOW-side keys of AGENT_WRITABLE.json, i.e. every key the VERIFIER'S
# SANDBOX consults to say yes to a submitted file
# (tools/verify-single/sandbox.py::_is_writable): `writable` (path prefixes,
# any file), `asset_writable` (path prefixes, .uasset/.umap only) and
# `config_writable` (EXACT rel-paths, then diffed against the task spec's
# `config_allow`). `deny` is deliberately NOT rendered: the template's
# "Everything else in the project is read-only or absent by design" already
# carries it, and enumerating deny prefixes only tells an agent what to probe.
#
# WHY THIS IS DERIVED AND NOT REMEMBERED (measured 2026-08-18,
# bp/t3-piercing-projectile). render_preamble filled {writable_roots} from
# `writable` and {asset_roots} from `asset_writable` and never mentioned
# `config_writable` at all -- so on the one task that REQUIRES a
# Config/DefaultEngine.ini edit, the prompt told the agent Config/ was
# read-only while the sandbox stood ready to accept it. The 2026-08-18 review
# reports that both graded passes came from a model ignoring the stated
# contract and inferring the undeclared lane (that run evidence is cited, not
# re-measured here); what IS measured here is the contradiction itself, and it
# means the cell scored "did it guess our unstated rule", not capability. One human transcribing a subset of the manifest once
# is exactly how that happens, so the key set is now CHECKED against the
# manifest (_assert_allow_keys_rendered) instead of trusted.
_RENDERED_ALLOW_KEYS = ("writable", "asset_writable", "config_writable",
                        "plugin_asset_writable")

# Appended to {asset_roots} only when this task opens a plugin content lane.
# Rendered SEPARATELY from asset_writable rather than folded into it, because
# sandbox.py keeps them separate for a reason: this is a narrow carve-out from
# the substrate's broad `Plugins/` deny, and the plugin descriptor, its
# Source/, its Config/ and every neighbouring feature stay DENIED. Folding the
# two would read as "Plugins/ is open", which is the overstatement that costs a
# rep to discover. Adding the key to _RENDERED_ALLOW_KEYS without this clause
# would silence the guard while leaving the agent untold -- the decorative fix
# the guard exists to prevent.
_PLUGIN_ASSET_CLAUSE = (
    ". This task also opens ONE plugin content root for .uasset/.umap "
    "only. Nothing else under Plugins/ is writable: not the .uplugin "
    "descriptor, not that plugin's own code or settings folders, and not "
    "any other feature. The root is: {roots}")

# Appended to {writable_roots} only when this task actually has a config lane.
# Wording constraints, both load-bearing -- see _config_files_for_task:
#   * EDIT, never create: config_writable entries are FILES (sandbox matches
#     them with `rel_path in manifest.config_writable`, an exact compare),
#     unlike the prefix-matched writable/asset roots;
#   * "nothing else under Config/ is writable" is the manifest's own warning
#     ("NEVER add a broad Config/ writable prefix: that would path-accept
#     arbitrary engine-config edits with no semantic gate") turned into the one
#     sentence the agent needs, so naming two files cannot read as "Config/ is
#     open".
_CONFIG_CLAUSE = (". You may also EDIT (never create, never delete) exactly "
                  "these existing files, and nothing else under Config/ is "
                  "writable: {files}")


def _allow_keys_present(manifest: dict) -> List[str]:
    """The manifest's ALLOW-side keys, recognised BY SHAPE (`writable` or
    `*_writable`) rather than against a remembered list -- so a key someone
    adds to a manifest and to sandbox.py announces itself here instead of being
    silently skipped, which is the defect this module already shipped once.
    Leading-underscore keys are the manifests' own prose (`_comment`,
    `_asset_writable_comment`), not policy."""
    return [k for k in manifest
            if not k.startswith("_")
            and (k == "writable" or k.endswith("_writable"))]


def _assert_allow_keys_rendered(manifest: dict, manifest_path: Path) -> None:
    """Refuse to render a contract that omits an allowlist the sandbox honours.

    FAIL CLOSED, because the failure is invisible in the other direction: an
    understated write scope does not look like a harness fault at run time, it
    looks like a model that failed to find a lane, and it is unfixable after
    the epoch opens. The only way to reach this is to add an allow key to a
    committed AGENT_WRITABLE.json (a governed substrate change) without
    teaching this renderer -- and it then fires on the FIRST render, before any
    build or token spend, naming what to do."""
    missing = [k for k in _allow_keys_present(manifest)
               if k not in _RENDERED_ALLOW_KEYS]
    if missing:
        raise ValueError(
            f"{manifest_path}: allowlist key(s) {sorted(missing)} are honoured "
            "by tools/verify-single/sandbox.py but are not rendered into the "
            "prompt contract. Teach preamble.py (_RENDERED_ALLOW_KEYS + "
            "render_preamble) before running a bench, or agents will be graded "
            "on a lane they were never told about."
        )


def _config_files_for_task(manifest: dict, task_id: str,
                           repo: Path) -> List[str]:
    """The exact Config/ files THIS TASK may edit: the manifest's
    `config_writable` list INTERSECTED with the files the task spec's
    `config_allow` rules license. Manifest order is preserved.

    WHY THE INTERSECTION AND NOT JUST THE MANIFEST. The sandbox's acceptance of
    a config file is two-stage: sandbox.py path-accepts a rel-path listed in
    `config_writable`, and config_lane.validate_config_submission then requires
    every ini change inside it to be covered by the task's `config_allow`
    rules. With no `config_allow` the second stage covers NOTHING. Measured
    2026-08-19 by calling config_lane.validate_config_submission directly:
    baseline DefaultInput.ini plus one added `+ActionMappings` line, with
    `config_allow=()`, returns ("Config/DefaultInput.ini", "config change not
    allowed: [/Script/Engine.InputSettings] +ActionMappings (added)"), and
    run_task.py appends that to sandbox_result.violations -- so the WHOLE
    submission exits 4 SANDBOX-REJECT. That is a non-graded, unrecoverable
    cell, not a per-file drop.

    Census the same day: 64 tasks sit on the ThirdPerson substrate, whose
    manifest carries `config_writable`; exactly ONE
    (bp/t3-piercing-projectile) declares `config_allow`. Rendering the manifest
    list unconditionally would therefore not widen the contract for the other
    63 -- it would advertise a trapdoor, and several of those specs'
    anti-gaming entries depend on the opposite (bp/gp-heal-over-time-bp:
    "declares no `config_allow`, so such a submission is sandbox-rejected (exit
    4)"). The intersection is what the sandbox actually accepts FROM THIS TASK,
    which is what the prompt is supposed to state.

    Fail direction on any read error: return [] (today's roots-only text). It
    is the conservative half of an asymmetry -- omitting costs a lane the model
    may still infer, naming a file the sandbox will reject costs the whole
    cell. `config_lane.parse_config_allow` raising on a malformed entry lands
    here too; run_task exits 2 on that same spec, so the run dies either way.
    The `aura_rig.tasks` import must come FIRST: it is what puts
    tools/verify-single on sys.path, so `spec`/`config_lane`/`sandbox`
    resolve."""
    declared = [str(f) for f in manifest.get("config_writable", ())]
    if not declared:
        return []
    try:
        from aura_rig.tasks import resolve_task_path    # noqa: PLC0415
        import spec as _taskspec                        # noqa: PLC0415
        import config_lane as _config_lane              # noqa: PLC0415
        from sandbox import _normalize_prefix as _norm  # noqa: PLC0415
        path = resolve_task_path(Path(repo), task_id)
        if not path:
            return []
        licensed = {r.file for r in _config_lane.parse_config_allow(
            _taskspec.parse_task_file(path).config_allow)}
    except Exception:      # noqa: BLE001 - never break prompt rendering
        return []
    return [f for f in declared if _norm(f) in licensed]


def scaffold_files_for_task(task_id: str, substrate_root: Path,
                            manifest_path: Optional[Path] = None) -> List[str]:
    """Substrate-relative paths of the active task's pre-existing scaffold.

    Folder-per-task layout wins when present (Source/.../Tasks/<id>/ +
    Content/Tasks/<id>/); flat tasks fall back to the marker scan over the
    writable module (``Source/<game_module>`` per ``manifest_path``), with
    .h/.cpp pair completion (a pair where only one file carries the marker is
    still one scaffold).

    ``manifest_path`` matters for the same reason as in :func:`_manifest_for`:
    the live scratch has no manifest, so without it this scanned
    ``Source/CraftBenchTemplate/`` on a ThirdPerson substrate and found
    nothing."""
    bare = _bare_task_id(task_id) or task_id
    out: List[str] = []

    writable_module_rel = _writable_module_rel(substrate_root, manifest_path)
    task_dir = substrate_root / writable_module_rel / _TASKS_SUBDIR / bare
    if task_dir.is_dir():
        out += sorted(
            p.relative_to(substrate_root).as_posix()
            for p in task_dir.rglob("*") if p.is_file()
        )
    else:
        module_dir = substrate_root / writable_module_rel
        if module_dir.is_dir():
            matched = set()
            for p in sorted(module_dir.glob("*")):
                if p.suffix.lower() not in (".h", ".cpp"):
                    continue
                if bare in _declared_tasks(p):
                    matched.add(p)
            for p in list(matched):
                sibling = p.with_suffix(".cpp" if p.suffix == ".h" else ".h")
                if sibling.exists():
                    matched.add(sibling)
            out += sorted(
                p.relative_to(substrate_root).as_posix() for p in matched
            )

    asset_dir = substrate_root / _CONTENT_TASKS_REL / bare
    if asset_dir.is_dir():
        out += sorted(
            p.relative_to(substrate_root).as_posix()
            for p in asset_dir.rglob("*") if p.is_file()
        )
    return out


def _render_excerpt(files: List[str], substrate_root: Path) -> str:
    """The optional appendix: scaffold text-file contents, fresh from disk,
    total capped at _EXCERPT_CAP_BYTES (truncated file gets a marker line)."""
    budget = _EXCERPT_CAP_BYTES
    parts: List[str] = []
    for rel in files:
        if not rel.lower().endswith(_EXCERPT_SUFFIXES):
            continue
        p = substrate_root / rel
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if budget <= 0:
            parts.append(f"--- {rel} (omitted: excerpt budget reached) ---")
            continue
        if len(body) > budget:
            body = body[:budget] + "\n… (truncated)"
        budget -= len(body)
        parts.append(f"--- {rel} ---\n```\n{body.rstrip()}\n```")
    if not parts:
        return ""
    return _EXCERPT_HEADER + "\n" + "\n\n".join(parts) + "\n"


def _lane_rules(repo: Path, lane: Optional[str]) -> str:
    """Lane-scoped operational rules (tasks/PREAMBLE.<lane>.md), rendered into
    the ``{lane_rules}`` placeholder only for that lane (owner decision
    2026-08-19, splitting the aura-product editor-lifecycle prose out of the
    shared contract). A lane file exists for exactly one reason: a rule that
    lane's harness cannot ENFORCE (aura-product's client owns its own tool
    set, so its rules can only be prose). Enforceable rules belong in
    adapters/registry.py::_DENIED_ORCHESTRATION, never here. Every lane file
    is disclosed verbatim in that arm's Harness Card."""
    if not lane:
        return ""
    p = Path(repo) / "tasks" / f"PREAMBLE.{lane}.md"
    if not p.is_file():
        return ""
    return _strip_template_comment(p.read_text(encoding="utf-8")).strip()


def render_preamble(
    task_id: str,
    repo: Path,
    *,
    substrate_root: Optional[Path] = None,
    include_excerpt: bool = False,
    lane: Optional[str] = None,
) -> Preamble:
    """Render tasks/PREAMBLE.md for ``task_id``. Raises FileNotFoundError if
    the template or the AGENT_WRITABLE manifest is missing (a benchmark run
    without the contract would be silently unfair — fail loudly instead).

    ``lane`` selects the optional per-lane rules block (see _lane_rules);
    omitted or unknown lanes render the uniform contract alone."""
    repo = Path(repo)
    substrate_root = Path(substrate_root) if substrate_root else repo / _SUBSTRATE_REL

    template = _strip_template_comment(
        (repo / TEMPLATE_REL).read_text(encoding="utf-8"))

    # The writable-roots manifest is VERIFIER-side policy. The C1 graded
    # scratch deliberately ships without it (nothing in the agent-visible tree
    # names the deny map), so a fallback is the ACTIVE path on every aura run.
    # It resolves to THIS TASK'S substrate before the default one — see
    # task_substrate_root() for the week-long, task-family-breaking bug that
    # the old substrate-blind fallback caused.
    manifest_path = _manifest_for(
        substrate_root, repo, task_substrate_root(task_id, repo))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _assert_allow_keys_rendered(manifest, manifest_path)

    # `roots` stays the PLAIN prefix list on purpose: it is both the first
    # half of {writable_roots} and the {asset_roots} fallback, and folding
    # the config sentence into it would file "you may EDIT
    # Config/DefaultEngine.ini" under the template's "New assets
    # (Blueprints, materials, ...) belong under:".
    roots = ", ".join(manifest.get("writable", ())) or "(none)"
    config_files = _config_files_for_task(manifest, task_id, repo)
    writable = roots + (
        _CONFIG_CLAUSE.format(files=", ".join(config_files))
        if config_files else "")   # degrades to today's text, no empty clause
    assets = ", ".join(manifest.get("asset_writable", ())) or roots
    plugin_roots = tuple(manifest.get("plugin_asset_writable", ()))
    if plugin_roots:
        assets = assets + _PLUGIN_ASSET_CLAUSE.format(
            roots=", ".join(plugin_roots))

    files = scaffold_files_for_task(task_id, substrate_root, manifest_path)
    files_str = ", ".join(files) if files else (
        "(none — this task starts from an empty workspace; create your files "
        "under the writable roots below)")

    excerpt = _render_excerpt(files, substrate_root) if include_excerpt else ""

    lane_rules = _lane_rules(repo, lane)
    if lane_rules and "{lane_rules}" not in template:
        # Fail closed: a lane's rules exist but the template cannot carry
        # them — dropping them silently would un-tell aura-product the
        # editor-lifecycle rules that cost 5 reps to learn (2026-08-06).
        raise ValueError(
            f"tasks/PREAMBLE.{lane}.md exists but {TEMPLATE_REL} has no "
            "{lane_rules} placeholder — add the placeholder or delete the "
            "lane file.")

    text = (template
            .replace("{task_id}", _bare_task_id(task_id) or task_id)
            .replace("{scaffold_files}", files_str)
            .replace("{writable_roots}", writable)
            .replace("{asset_roots}", assets)
            .replace("{lane_rules}", lane_rules)
            .replace("{scaffold_excerpt_section}", excerpt))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip() + "\n"
    return Preamble(
        text=text,
        sha=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        scaffold_files=files,
    )
