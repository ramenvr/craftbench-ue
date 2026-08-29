#!/usr/bin/env python3
"""Task-spec parsing — THE single parser for ``task.md`` files.

Spec v2 (preferred): a restricted front-matter block followed by a markdown
body. The front matter is NOT general YAML — the grammar is deliberately
tiny so a hand-rolled stdlib parser covers it completely:

    ---
    id: t0-sanity-log-on-beginplay
    substrate: CraftBenchTemplate
    set: flagship
    tier: T1
    capability_bucket: Gameplay Programming
    category: gameplay
    layers: [L1, L2]
    fixtures: ["L_SanityTask :: ASanityFunctionalTest"]
    introspect: [my_asset_check.py]
    fps_legs: [60, 20]
    deadline_s: 600
    action_budget: 30
    randomization: [log-tag, actor-tag]
    ---

Only two body sections are agent-visible ("## Prompt given to the agent",
"## Workspace state pre-task" — extracted by prompt_extract.py, headings
FROZEN); everything else in the body is human documentation.

Legacy fallback: when the file does not open with a front-matter block the
parser falls back to the historical H2-section parsing lifted verbatim from
run_task.py (metadata bullets, "## Verifier layers used", the unified
"## Verifier layers" block, fixtures/introspect/framerate/randomization
sections, and the global map/test-class regex scans). Legacy semantics are
intentionally IDENTICAL to run_task.parse_task_spec — quirks included —
and the result is flagged ``legacy=True``.

Everyone imports from this module; nobody re-implements task.md parsing.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional


class Fixture(NamedTuple):
    """One leg of a multi-fixture L2 verifier: a map name + the
    ``AFunctionalTest`` subclass placed in that map. A NamedTuple so it
    behaves as the plain ``(map, cls)`` tuple downstream consumers expect
    while keeping readable attribute access."""

    map_name: str
    test_class: str


@dataclass
class TaskSpec:
    """The parsed subset of a task .md needed by the runner + harness."""

    task_id: str
    substrate: str
    layers: tuple[str, ...]

    # Task-card metadata (front matter keys / legacy metadata bullets).
    tier: Optional[str] = None
    capability_bucket: Optional[str] = None
    category: Optional[str] = None
    set_name: Optional[str] = None

    # Editor RHI contract for graded runtime legs. ``null`` preserves the
    # headless default; ``real`` requires the platform default real RHI;
    # ``d3d11`` additionally pins Windows D3D11 for tasks that need a real
    # viewport path but cannot reliably allocate through the host's D3D12
    # adapter/driver combination.
    rhi: str = "null"

    # L2 fixtures: (map, class) tuples. Empty when the task has no L2 layer
    # (or, legacy-only, when a single fixture is derived via map_name +
    # test_class_hint below).
    fixtures: tuple[Fixture, ...] = ()

    # Single-fixture hints. Front-matter path: derived from fixtures[0]
    # (never from prose scans). Legacy path: global regex scans over the
    # whole spec, identical to run_task.parse_task_spec.
    map_name: Optional[str] = None
    test_class_hint: Optional[str] = None

    # Per-task fixed-timestep L2 legs (DD-9). Empty => single default-fps run.
    fps_legs: tuple[int, ...] = ()

    # L2-introspect scripts under tools/verify-single/introspect/.
    introspect_scripts: tuple[str, ...] = ()

    deadline_s: float = 600.0
    action_budget: int = 30

    # Randomization tokens (kebab-case identifiers).
    randomization: tuple[str, ...] = ()

    # Config-lane allowlist entries ("<Config/File.ini> :: <Section> ::
    # <Key[*]>"). Kept as raw strings here; parsed and format-checked lazily
    # by config_lane.parse_config_allow at use time (fail closed there).
    config_allow: tuple[str, ...] = ()

    # Optional task-scoped exact submission manifest. Unlike the substrate's
    # broad writable prefixes, this list names every file this task accepts.
    # run_task rejects both missing and extra accepted files before grading.
    accepted_files: tuple[str, ...] = ()

    # L2I integrity-preamble redirector exception (rename-residue lane):
    # /Game package paths whose submitted UObjectRedirector is tolerated.
    # Default-closed; the builder pins every entry inside the task's own
    # /Game/Tasks/<id>/ namespace (fail closed, exit 2 on violation).
    allow_redirectors: tuple[str, ...] = ()

    # True when the task declares the non-gating R2 advisory (v2: R2 in
    # layers; legacy: an R2 layer token or a "## R2 advisory rubric" section).
    declares_r2: bool = False

    # True when this spec was parsed via the legacy H2 fallback.
    legacy: bool = False

    # Carried through for downstream consumers (report headers, prompt
    # extraction, R2 wiring).
    raw_text: str = ""
    source_path: Optional[Path] = None

    # Legacy unified-block extras (no front-matter spelling yet).
    artifact_path: Optional[str] = None
    l3_fixtures: tuple[Fixture, ...] = ()


# ---------------------------------------------------------------------------
# Front matter (spec v2)
# ---------------------------------------------------------------------------

_FM_DELIM = "---"
_FM_LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<val>.*)$")

_KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FIXTURE_COMPACT_RE = re.compile(
    r"^(?P<map>L_[A-Za-z0-9_]+)\s*::\s*(?P<cls>[A-Z][A-Za-z0-9_]+)$"
)

# Layer tokens. L4/L5 are recognized (parse cleanly) but unimplemented in the
# runner — the registry decides what actually runs.
IMPLEMENTED_LAYERS = ("L1", "L2", "L2I", "L3", "ART", "R2")
RECOGNIZED_LAYERS = IMPLEMENTED_LAYERS + ("L4", "L5")

_SCALAR_KEYS = frozenset(
    {"id", "substrate", "set", "tier", "capability_bucket", "category", "rhi",
     "deadline_s", "action_budget"}
)
_LIST_KEYS = frozenset(
    {"layers", "fixtures", "introspect", "fps_legs", "randomization",
     "config_allow", "allow_redirectors", "accepted_files"}
)
_KNOWN_KEYS = _SCALAR_KEYS | _LIST_KEYS


def _strip_quotes(s: str) -> str:
    """Strip ONE layer of matching single/double quotes from a value."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def parse_front_matter(text: str) -> Optional[dict]:
    """Parse the restricted front-matter block at the top of ``text``.

    Returns ``None`` when the first line is not exactly ``---`` (=> the file
    is a legacy spec). Returns ``{key: str | list[str]}`` on success — values
    are RAW strings; typing/validation happens in the TaskSpec builder.
    Raises ``ValueError`` on a malformed block (no closing ``---``, a line
    that is not ``key: value``, a duplicate key, an unterminated list).
    """
    lines = text.splitlines()
    # Tolerate a UTF-8 BOM and surrounding whitespace on the opening '---' —
    # a BOM'd/space-padded v2 spec must NOT silently fall through to the
    # legacy parser. tasklint.is_task_spec applies the SAME normalization;
    # keep the two in lockstep.
    if not lines or lines[0].lstrip("﻿").strip() != _FM_DELIM:
        return None
    out: dict = {}
    closed = False
    for lineno, line in enumerate(lines[1:], start=2):
        if line.strip() == _FM_DELIM:
            closed = True
            break
        if not line.strip() or line.lstrip().startswith("#"):
            continue  # tolerate blank + comment lines
        m = _FM_LINE_RE.match(line)
        if not m:
            raise ValueError(
                f"front matter line {lineno} is not 'key: value': {line!r}"
            )
        key, val = m.group("key"), m.group("val").strip()
        if key in out:
            raise ValueError(f"duplicate front matter key: {key!r}")
        if val.startswith("["):
            if not val.endswith("]"):
                raise ValueError(
                    f"front matter list for {key!r} must be inline "
                    f"'[a, b, c]' (got {val!r})"
                )
            inner = val[1:-1].strip()
            items = (
                [_strip_quotes(p) for p in inner.split(",")] if inner else []
            )
            items = [p for p in (i.strip() for i in items) if p]
            out[key] = items
        else:
            out[key] = _strip_quotes(val)
    if not closed:
        raise ValueError("front matter block is missing its closing '---'")
    return out


def _require_list(fm: dict, key: str) -> list:
    v = fm[key]
    if not isinstance(v, list):
        raise ValueError(f"front matter key {key!r} must be a list [..], got scalar {v!r}")
    return v


def _require_scalar(fm: dict, key: str) -> str:
    v = fm[key]
    if isinstance(v, list):
        raise ValueError(f"front matter key {key!r} must be a scalar, got list {v!r}")
    return v


def _spec_from_front_matter(fm: dict, raw: str, path: Path) -> TaskSpec:
    """Build + strictly validate a TaskSpec from a parsed front-matter dict."""
    unknown = sorted(set(fm) - _KNOWN_KEYS)
    if unknown:
        raise ValueError(
            f"unknown front matter key(s) in {path}: {', '.join(unknown)} "
            f"(allowed: {', '.join(sorted(_KNOWN_KEYS))})"
        )

    # --- id (required, kebab) --------------------------------------------
    if "id" not in fm:
        raise ValueError(f"front matter in {path} is missing required key 'id'")
    task_id = _require_scalar(fm, "id")
    if not _KEBAB_RE.match(task_id):
        raise ValueError(f"'id' must be kebab-case ([a-z0-9-]), got {task_id!r}")

    # --- layers (required, known tokens) ----------------------------------
    if "layers" not in fm:
        raise ValueError(f"front matter in {path} is missing required key 'layers'")
    layer_list = _require_list(fm, "layers")
    if not layer_list:
        raise ValueError("'layers' must name at least one layer")
    for tok in layer_list:
        if tok not in RECOGNIZED_LAYERS:
            raise ValueError(
                f"unknown layer token {tok!r} (recognized: "
                f"{', '.join(RECOGNIZED_LAYERS)})"
            )
    layers = tuple(dict.fromkeys(layer_list))

    # --- fixtures (required iff L2) ---------------------------------------
    fixtures: tuple[Fixture, ...] = ()
    if "fixtures" in fm:
        if "L2" not in layers:
            raise ValueError("'fixtures' declared but L2 is not in 'layers'")
        parsed = []
        for item in _require_list(fm, "fixtures"):
            m = _FIXTURE_COMPACT_RE.match(item.strip())
            if not m:
                raise ValueError(
                    f"bad fixture {item!r} — expected "
                    f"'L_<Map> :: <ClassFunctionalTest>'"
                )
            parsed.append(Fixture(map_name=m.group("map"), test_class=m.group("cls")))
        fixtures = tuple(dict.fromkeys(parsed))
    if "L2" in layers and not fixtures:
        raise ValueError("L2 in 'layers' requires a non-empty 'fixtures' list")

    # --- introspect (required iff L2I) ------------------------------------
    introspect: tuple[str, ...] = ()
    if "introspect" in fm:
        if "L2I" not in layers:
            raise ValueError("'introspect' declared but L2I is not in 'layers'")
        scripts = _require_list(fm, "introspect")
        for s in scripts:
            if not s.endswith(".py"):
                raise ValueError(f"introspect entry {s!r} must be a .py filename")
        introspect = tuple(dict.fromkeys(scripts))
    if "L2I" in layers and not introspect:
        raise ValueError("L2I in 'layers' requires a non-empty 'introspect' list")

    # --- fps_legs (int list, each >= 1) ------------------------------------
    fps_legs: tuple[int, ...] = ()
    if "fps_legs" in fm:
        legs = []
        for item in _require_list(fm, "fps_legs"):
            try:
                fps = int(item)
            except ValueError:
                raise ValueError(f"fps_legs entry {item!r} is not an integer") from None
            if fps < 1:
                raise ValueError(f"fps_legs entry {fps} must be >= 1")
            legs.append(fps)
        fps_legs = tuple(dict.fromkeys(legs))

    # --- scalars with defaults ---------------------------------------------
    substrate = _require_scalar(fm, "substrate") if "substrate" in fm else "CraftBenchTemplate"
    set_name = _require_scalar(fm, "set") if "set" in fm else None
    tier = _require_scalar(fm, "tier") if "tier" in fm else None
    capability_bucket = (
        _require_scalar(fm, "capability_bucket") if "capability_bucket" in fm else None
    )
    category = _require_scalar(fm, "category") if "category" in fm else None
    rhi = _require_scalar(fm, "rhi").lower() if "rhi" in fm else "null"
    if rhi not in {"null", "real", "d3d11"}:
        raise ValueError("'rhi' must be one of 'null', 'real', or 'd3d11'")

    deadline_s = 600.0
    if "deadline_s" in fm:
        try:
            deadline_s = float(_require_scalar(fm, "deadline_s"))
        except ValueError:
            raise ValueError(
                f"'deadline_s' must be a number, got {fm['deadline_s']!r}"
            ) from None
        if not math.isfinite(deadline_s) or deadline_s <= 0:
            raise ValueError(
                f"'deadline_s' must be finite and > 0, got {fm['deadline_s']!r}"
            )

    action_budget = 30
    if "action_budget" in fm:
        try:
            action_budget = int(_require_scalar(fm, "action_budget"))
        except ValueError:
            raise ValueError(
                f"'action_budget' must be an integer, got {fm['action_budget']!r}"
            ) from None
        if action_budget < 1:
            raise ValueError(
                f"'action_budget' must be >= 1, got {fm['action_budget']!r}"
            )

    # --- randomization (kebab token list) ----------------------------------
    randomization: tuple[str, ...] = ()
    if "randomization" in fm:
        toks = _require_list(fm, "randomization")
        for t in toks:
            if not _KEBAB_RE.match(t):
                raise ValueError(
                    f"randomization token {t!r} must be kebab-case ([a-z0-9-])"
                )
        randomization = tuple(dict.fromkeys(toks))

    # --- config_allow (semantic config lane) -------------------------------
    # Entries stay raw strings here; config_lane.parse_config_allow
    # format-checks them (fail closed) when the runner builds its rules.
    config_allow: tuple[str, ...] = ()
    if "config_allow" in fm:
        config_allow = tuple(dict.fromkeys(_require_list(fm, "config_allow")))

    # --- accepted_files (task-scoped exact submission boundary) -----------
    accepted_files: tuple[str, ...] = ()
    if "accepted_files" in fm:
        raw_files = _require_list(fm, "accepted_files")
        if not raw_files:
            raise ValueError("'accepted_files' must not be empty when declared")
        normalized: list[str] = []
        folded: set[str] = set()
        for item in raw_files:
            rel = item.replace("\\", "/")
            parts = rel.split("/")
            if (
                not rel
                or rel.startswith("/")
                or re.match(r"^[A-Za-z]:", rel)
                or any(part in ("", ".", "..") for part in parts)
            ):
                raise ValueError(
                    f"accepted_files entry {item!r} must be a normalized "
                    "repository-relative path"
                )
            key = rel.casefold()
            if key in folded:
                raise ValueError(
                    f"accepted_files contains a duplicate path: {item!r}"
                )
            folded.add(key)
            normalized.append(rel)
        accepted_files = tuple(normalized)

    # --- allow_redirectors (L2I integrity-preamble exception) ---------------
    # Rename-residue lane: package paths whose submitted redirector the
    # asset-integrity preamble tolerates. Fail closed on two fronts: the key
    # is meaningless without L2I, and the exception may only name packages
    # inside the task's own namespace (a broader allowlist would let a spec
    # reopen the redirector hole for shared content).
    allow_redirectors: tuple[str, ...] = ()
    if "allow_redirectors" in fm:
        if "L2I" not in layers:
            raise ValueError(
                "'allow_redirectors' declared but L2I is not in 'layers'"
            )
        req_prefix = f"/Game/Tasks/{task_id}/"
        for item in _require_list(fm, "allow_redirectors"):
            if not item.startswith(req_prefix):
                raise ValueError(
                    f"allow_redirectors entry {item!r} must start with "
                    f"{req_prefix!r} (the exception is task-scoped)"
                )
        allow_redirectors = tuple(
            dict.fromkeys(_require_list(fm, "allow_redirectors"))
        )

    # Front-matter path derives single-fixture hints from fixtures[0] — it
    # never runs the fragile legacy global map/class regex scans.
    map_name = fixtures[0].map_name if fixtures else None
    test_class_hint = fixtures[0].test_class if fixtures else None

    return TaskSpec(
        task_id=task_id,
        substrate=substrate,
        layers=layers,
        tier=tier,
        capability_bucket=capability_bucket,
        category=category,
        set_name=set_name,
        rhi=rhi,
        fixtures=fixtures,
        map_name=map_name,
        test_class_hint=test_class_hint,
        fps_legs=fps_legs,
        introspect_scripts=introspect,
        deadline_s=deadline_s,
        action_budget=action_budget,
        randomization=randomization,
        config_allow=config_allow,
        accepted_files=accepted_files,
        allow_redirectors=allow_redirectors,
        declares_r2="R2" in layers,
        legacy=False,
        raw_text=raw,
        source_path=path,
    )


# ---------------------------------------------------------------------------
# Legacy H2 parsing — lifted VERBATIM from run_task.py. Semantics identical
# (quirks included); do not "fix" this path. The fallback exists so
# un-migrated specs keep parsing exactly as they do today.
# ---------------------------------------------------------------------------

_METADATA_LINE_RE = re.compile(r"^\s*-\s*([A-Za-z_][\w]*)\s*:\s*(.+?)\s*$")
_LAYERS_RE = re.compile(r"\b(L[1-5])\b")
# Maps may live flat ("Maps/L_X.umap") or one folder deep after the
# folder-per-task migration ("Maps/<task-id>/L_X.umap") — tolerate an
# optional folder segment between "Maps/" and the L_ name.
_MAP_NAME_RE = re.compile(
    r"Maps/(?:[A-Za-z0-9_\-]+/)?(?P<name>L_[A-Za-z0-9_]+)(?:\.umap)?",
    re.IGNORECASE,
)
_TEST_CLASS_RE = re.compile(r"\b([AF][A-Z][A-Za-z0-9_]*FunctionalTest)\b")
_FIXTURE_LINE_RE = re.compile(
    r"^\s*-\s*(?P<map>L_[A-Za-z0-9_]+)\s*::\s*(?P<cls>[A-Z][A-Za-z0-9_]+)\s*$"
)
_RANDOMIZATION_LINE_RE = re.compile(r"^\s*-\s*(?P<tok>[a-z][a-z0-9-]*)\b")
_FRAMERATE_LEG_RE = re.compile(r"\d+")
_INTROSPECT_LINE_RE = re.compile(
    r"^\s*-\s*(?:.*::\s*)?(?P<script>[A-Za-z0-9_./-]+\.py)\s*$"
)
_VLAYER_LINE_RE = re.compile(
    r"^\s*-\s*(?P<key>[A-Z][A-Z0-9]*)\s*(?:\((?P<cfg>.*)\))?\s*$"
)


def _split_h2_sections(markdown: str) -> dict[str, str]:
    """Return a dict mapping H2 heading text -> raw body up to the next H2."""
    out: dict[str, str] = {}
    current_heading: Optional[str] = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if current_heading is not None:
                out[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        out[current_heading] = "\n".join(current_lines).strip()
    return out


def _parse_metadata_block(block: str) -> dict[str, str]:
    """Parse the loose 'key: value' bullets in the metadata block."""
    out: dict[str, str] = {}
    for line in block.splitlines():
        m = _METADATA_LINE_RE.match(line)
        if m:
            key = m.group(1).lower()
            out[key] = m.group(2).strip()
    return out


def _parse_scalar_section(block: str, *, default, cast):
    """Parse a single-number H2 section like ``## Deadline``.

    Accepts the first integer/float found in the body; falls back to
    ``default`` when the section is missing, empty, or unparseable.
    """
    if not block:
        return default
    m = re.search(r"-?\d+(?:\.\d+)?", block)
    if not m:
        return default
    try:
        return cast(m.group(0))
    except (TypeError, ValueError):
        return default


def _parse_fixtures_block(block: str) -> tuple[Fixture, ...]:
    """Extract `<map> :: <class>` bullet lines from a Verifier fixtures
    section. Non-matching lines are skipped; order preserved; dupes collapse."""
    out: list[Fixture] = []
    if not block:
        return ()
    seen: set[tuple[str, str]] = set()
    for line in block.splitlines():
        m = _FIXTURE_LINE_RE.match(line)
        if not m:
            continue
        key = (m.group("map"), m.group("cls"))
        if key in seen:
            continue
        seen.add(key)
        out.append(Fixture(map_name=m.group("map"), test_class=m.group("cls")))
    return tuple(out)


def _parse_framerate_legs(block: str) -> tuple[int, ...]:
    """Extract fixed-timestep fps legs (order-preserving, de-duplicated)."""
    if not block:
        return ()
    out: list[int] = []
    seen: set[int] = set()
    for tok in _FRAMERATE_LEG_RE.findall(block):
        fps = int(tok)
        if fps in seen:
            continue
        seen.add(fps)
        out.append(fps)
    return tuple(out)


def _parse_introspect_block(block: str) -> tuple[str, ...]:
    """Extract introspect script filenames from a ``## Verifier introspection``
    section (optionally prefixed by ``<asset> :: ``)."""
    if not block:
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for line in block.splitlines():
        m = _INTROSPECT_LINE_RE.match(line)
        if not m:
            continue
        s = m.group("script")
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return tuple(out)


def _parse_randomization_block(block: str) -> tuple[str, ...]:
    """Parse a ``## Randomization`` block into an ordered token tuple."""
    if not block:
        return ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for line in block.splitlines():
        m = _RANDOMIZATION_LINE_RE.match(line)
        if not m:
            continue
        tok = m.group("tok")
        if tok in seen_set:
            continue
        seen_set.add(tok)
        seen.append(tok)
    return tuple(seen)


def _parse_verifier_layers_block(block: str) -> dict[str, dict[str, str]]:
    """Parse the unified ``## Verifier layers`` block into ``{KEY: {param: value}}``."""
    out: dict[str, dict[str, str]] = {}
    if not block:
        return out
    for line in block.splitlines():
        m = _VLAYER_LINE_RE.match(line)
        if not m:
            continue
        cfg: dict[str, str] = {}
        for part in (m.group("cfg") or "").split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                cfg[k.strip()] = v.strip()
        out[m.group("key")] = cfg
    return out


def _fixtures_inline_to_block(inline: str) -> str:
    """Turn a comma-separated inline fixtures value into the bullet-list
    block shape ``_parse_fixtures_block`` expects."""
    return "\n".join(f"- {part.strip()}" for part in inline.split(",") if part.strip())


def _parse_legacy(raw: str, path: Path) -> TaskSpec:
    """Legacy H2 parsing — mirrors run_task.parse_task_spec exactly, then
    maps the result onto the new TaskSpec field names + card metadata."""
    sections = _split_h2_sections(raw)

    # --- Task ID and metadata block --------------------------------------
    meta_block = sections.get("Task ID and metadata", "")
    metadata = _parse_metadata_block(meta_block)
    task_id = metadata.get("task_id")
    substrate = metadata.get("substrate")
    if not task_id:
        task_id = path.parent.name if path.stem == "task" else path.stem
    if not substrate:
        substrate = "template"

    # --- Verifier layers used --------------------------------------------
    layers_block = sections.get("Verifier layers used", "")
    layers = tuple(dict.fromkeys(_LAYERS_RE.findall(layers_block)))
    if not layers:
        # Defensive: fall back to scanning the whole spec.
        layers = tuple(dict.fromkeys(_LAYERS_RE.findall(raw)))

    # --- Map + test-class hints (used to construct the L2 test filter) ---
    map_name = None
    m = _MAP_NAME_RE.search(raw)
    if m:
        map_name = m.group("name")

    test_class = None
    m = _TEST_CLASS_RE.search(raw)
    if m:
        test_class = m.group(1)

    # --- Verifier fixtures (optional, multi-fixture L2 tasks) ------------
    fixtures = _parse_fixtures_block(sections.get("Verifier fixtures", ""))

    # --- Per-task deadline + action budget (FR-020b, FR-020c) ------------
    deadline_s = _parse_scalar_section(
        sections.get("Deadline", ""), default=600.0, cast=float
    )
    action_budget = _parse_scalar_section(
        sections.get("Action budget", ""), default=30, cast=int
    )

    randomization = _parse_randomization_block(sections.get("Randomization", ""))
    introspect_scripts = _parse_introspect_block(
        sections.get("Verifier introspection", "")
    )

    artifact_path = None
    l3_fixtures: tuple[Fixture, ...] = ()

    # --- Unified "## Verifier layers" block (single source of truth) -----
    unified = _parse_verifier_layers_block(sections.get("Verifier layers", ""))
    if unified:
        layers = tuple(unified.keys())
        if "fixtures" in unified.get("L2", {}):
            fixtures = _parse_fixtures_block(
                _fixtures_inline_to_block(unified["L2"]["fixtures"])
            )
        if "scripts" in unified.get("L2I", {}):
            introspect_scripts = tuple(
                s.strip()
                for s in re.split(r"[,;]", unified["L2I"]["scripts"])
                if s.strip()
            )
        if "fixtures" in unified.get("L3", {}):
            l3_fixtures = _parse_fixtures_block(
                _fixtures_inline_to_block(unified["L3"]["fixtures"])
            )
        artifact_path = unified.get("ART", {}).get("artifact")

    # --- Verifier framerate legs (standalone section wins; else L2 fps:) --
    fps_legs = _parse_framerate_legs(sections.get("Verifier framerate legs", ""))
    if not fps_legs and unified.get("L2", {}).get("fps"):
        fps_legs = _parse_framerate_legs(unified["L2"]["fps"])

    declares_r2 = ("R2" in layers) or ("## R2 advisory rubric" in raw)

    return TaskSpec(
        task_id=task_id,
        substrate=substrate,
        layers=layers,
        tier=metadata.get("tier"),
        capability_bucket=metadata.get("capability_bucket"),
        category=metadata.get("category"),
        set_name=metadata.get("set"),
        fixtures=fixtures,
        map_name=map_name,
        test_class_hint=test_class,
        fps_legs=fps_legs,
        introspect_scripts=introspect_scripts,
        deadline_s=deadline_s,
        action_budget=action_budget,
        randomization=randomization,
        declares_r2=declares_r2,
        legacy=True,
        raw_text=raw,
        source_path=path,
        artifact_path=artifact_path,
        l3_fixtures=l3_fixtures,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_task_file(path: Path) -> TaskSpec:
    """Parse a task.md into a TaskSpec.

    Front matter (spec v2) is preferred; when the file does not open with a
    ``---`` line the legacy H2 parsing runs with semantics identical to
    run_task.parse_task_spec and the result is flagged ``legacy=True``.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    fm = parse_front_matter(raw)
    if fm is not None:
        return _spec_from_front_matter(fm, raw, path)
    return _parse_legacy(raw, path)
