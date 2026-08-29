#!/usr/bin/env python3
"""One-shot migrator: legacy H2 task.md -> spec v2 front-matter task.md.

Reads each legacy spec through the ONE parser (tools/verify-single/spec.py,
legacy fallback path), emits the v2 file in place:

  * restricted front-matter block (id / substrate / set / tier /
    capability_bucket / category / layers / fixtures / introspect /
    fps_legs / deadline_s / action_budget / randomization — defaults and
    empty lists are omitted);
  * body that KEEPS, verbatim and in this order: the pre-H2 preamble
    (H1 title + intro prose), "## Prompt given to the agent",
    "## Workspace state pre-task", "## Anti-gaming notes", then every
    remaining section under its original heading (human docs);
  * DELETES the now-machine-redundant sections ("## Task ID and metadata",
    "## Verifier layers used" / "## Verifier layers", "## Verifier fixtures",
    "## Verifier introspection", "## Verifier framerate legs", "## Deadline",
    "## Action budget", "## Randomization").

Decisions baked in:
  * `set` comes from the task's parent-set FOLDER (tasks/<set>/<id>/), not
    from the legacy metadata bullet — three specs carried stale historical
    set names (internal-1, gold-1).
  * legacy `substrate: template` is spelled `CraftBenchTemplate` (the v2
    canonical name; also the v2 default, but we emit it explicitly).
  * L2 tasks without a "## Verifier fixtures" section get their single
    fixture synthesized from the legacy map_name + test_class_hint scans.

Usage:
    python3 tools/scripts/spec_v2_migrate.py            # migrate all 15 in place
    python3 tools/scripts/spec_v2_migrate.py --verify   # parse-check migrated specs

stdlib-only; idempotent (front-matter files are skipped on migrate).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "verify-single"))

import spec  # noqa: E402  (the single parser; never re-implement parsing)

# Embedded work-list (never trust an empty glob as a clean pass).
EXPECTED_TASKS = [
    "tasks/cpp/gp-crafting-queue/task.md",
    "tasks/cpp/gp-glide-stamina-cpp/task.md",
    "tasks/cpp/gp-harvestable-regrow/task.md",
    "tasks/cpp/gp-inventory-stacking/task.md",
    "tasks/cpp/gp-poison-dot-stack-cpp/task.md",
    "tasks/cpp/gp-spawner-population/task.md",
    "tasks/flagship/gp-gas-launch/task.md",
    "tasks/bp/t0-sanity-bp-log-on-beginplay/task.md",
    "tasks/cpp/t0-sanity-log-on-beginplay/task.md",
    "tasks/flagship/umg-image-brush-bound/task.md",
    "tasks/cpp/t1-data-asset-drives-speed/task.md",
    "tasks/cpp/t1-datatable-drives-value/task.md",
    "tasks/cpp/t1-movement-component-drives-actor/task.md",
    "tasks/cpp/t1-overlap-logs-once/task.md",
    "tasks/cpp/t1-physics-drop-and-rest/task.md",
]
assert len(EXPECTED_TASKS) == 15, "work-list drifted"

# Sections whose facts now live in the front matter — dropped from the body.
MACHINE_SECTIONS = {
    "Task ID and metadata",
    "Verifier layers used",
    "Verifier layers",
    "Verifier fixtures",
    "Verifier introspection",
    "Verifier framerate legs",
    "Deadline",
    "Action budget",
    "Randomization",
}

# Body ordering contract: the two agent-visible sections (headings FROZEN,
# prompt_extract.py keys on them) then anti-gaming, then everything else.
LEAD_SECTIONS = (
    "Prompt given to the agent",
    "Workspace state pre-task",
    "Anti-gaming notes",
)

DEFAULT_DEADLINE_S = 600.0
DEFAULT_ACTION_BUDGET = 30


def _first_fenced_h2_line(text: str):
    """1-based line number of the first '## ' line INSIDE a ``` fence, else None.

    Pre-flight guard: neither _split_sections below nor the legacy parser is
    fence-aware — a fenced '## ' lookalike would be treated as a real section
    boundary and silently reorder/drop body content. We refuse such inputs
    instead of making the split fence-aware."""
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.startswith("## "):
            return i
    return None


def _split_sections(text: str):
    """Split markdown into (preamble, [(heading, raw_section_text), ...]).

    Section text INCLUDES its '## ' heading line; trailing whitespace of each
    chunk is normalized to a single terminating newline on reassembly.
    """
    preamble_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            current = [line]
            sections.append((line[3:].strip(), current))
        elif current is None:
            preamble_lines.append(line)
        else:
            current.append(line)
    return (
        "\n".join(preamble_lines).strip(),
        [(h, "\n".join(ls).strip()) for h, ls in sections],
    )


def build_front_matter(ts: spec.TaskSpec, set_name: str) -> str:
    """Render the restricted front-matter block from a parsed TaskSpec."""
    lines = ["---"]
    lines.append(f"id: {ts.task_id}")
    lines.append("substrate: CraftBenchTemplate")
    lines.append(f"set: {set_name}")
    if ts.tier:
        lines.append(f"tier: {ts.tier}")
    if ts.capability_bucket:
        lines.append(f"capability_bucket: {ts.capability_bucket}")
    if ts.category:
        lines.append(f"category: {ts.category}")
    lines.append("layers: [" + ", ".join(ts.layers) + "]")

    fixtures = list(ts.fixtures)
    if "L2" in ts.layers and not fixtures:
        # Legacy single-fixture spec: synthesize from the global scans.
        if not (ts.map_name and ts.test_class_hint):
            raise SystemExit(
                f"{ts.source_path}: L2 task with no fixtures section and no "
                f"derivable map/class — cannot migrate"
            )
        fixtures = [spec.Fixture(ts.map_name, ts.test_class_hint)]
    if fixtures:
        rendered = ", ".join(
            f'"{f.map_name} :: {f.test_class}"' for f in fixtures
        )
        lines.append(f"fixtures: [{rendered}]")

    if ts.introspect_scripts:
        lines.append("introspect: [" + ", ".join(ts.introspect_scripts) + "]")
    if ts.fps_legs:
        lines.append("fps_legs: [" + ", ".join(str(f) for f in ts.fps_legs) + "]")
    if ts.deadline_s != DEFAULT_DEADLINE_S:
        d = ts.deadline_s
        lines.append(f"deadline_s: {int(d) if float(d).is_integer() else d}")
    if ts.action_budget != DEFAULT_ACTION_BUDGET:
        lines.append(f"action_budget: {ts.action_budget}")
    if ts.randomization:
        lines.append("randomization: [" + ", ".join(ts.randomization) + "]")
    lines.append("---")
    return "\n".join(lines)


def migrate_one(path: Path) -> bool:
    """Convert one task.md in place. Returns True if rewritten."""
    raw = path.read_text(encoding="utf-8")
    if spec.parse_front_matter(raw) is not None:
        print(f"  skip (already v2): {path}")
        return False

    fenced = _first_fenced_h2_line(raw)
    if fenced is not None:
        raise SystemExit(
            f"{path}: line {fenced}: a '## ' line sits inside a ``` fence — "
            "the section splitter is not fence-aware and would corrupt the "
            "body; refusing to migrate this file"
        )

    ts = spec.parse_task_file(path)
    assert ts.legacy, f"{path}: expected legacy parse"
    set_name = path.parent.parent.name  # tasks/<set>/<id>/task.md
    folder_id = path.parent.name
    if ts.task_id != folder_id:
        raise SystemExit(
            f"{path}: metadata task_id {ts.task_id!r} != folder {folder_id!r}"
        )

    preamble, sections = _split_sections(raw)
    by_heading = dict(sections)
    if len(by_heading) != len(sections):
        raise SystemExit(f"{path}: duplicate H2 headings — refusing to migrate")
    if "Prompt given to the agent" not in by_heading:
        raise SystemExit(f"{path}: missing '## Prompt given to the agent'")

    parts = [build_front_matter(ts, set_name)]
    if preamble:
        parts.append(preamble)
    emitted: set[str] = set()
    for h in LEAD_SECTIONS:
        if h in by_heading:
            parts.append(by_heading[h])
            emitted.add(h)
    for h, body in sections:  # remaining human-doc sections, original order
        if h in emitted or h in MACHINE_SECTIONS:
            continue
        parts.append(body)
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"  migrated: {path}")
    return True


def verify_all(paths: list[Path]) -> int:
    """Parse every migrated spec through spec.py and assert invariants."""
    failures = 0
    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8")
            assert spec.parse_front_matter(raw) is not None, "no front matter"
            ts = spec.parse_task_file(path)
            assert not ts.legacy, "still parsing via legacy fallback"
            assert ts.task_id == path.parent.name, (
                f"id {ts.task_id!r} != folder {path.parent.name!r}"
            )
            assert ts.set_name == path.parent.parent.name, (
                f"set {ts.set_name!r} != folder set {path.parent.parent.name!r}"
            )
            assert ts.layers, "empty layers"
            if "L2" in ts.layers:
                assert ts.fixtures, "L2 declared but no fixtures"
                assert ts.map_name and ts.test_class_hint, "no fixture hints"
            if "L2I" in ts.layers:
                assert ts.introspect_scripts, "L2I declared but no introspect"
            assert "## Prompt given to the agent" in raw, "prompt heading lost"
            for h in MACHINE_SECTIONS:
                assert f"## {h}\n" not in raw and not raw.endswith(f"## {h}"), (
                    f"machine section '## {h}' still present"
                )
            print(f"  OK: {path}  layers={','.join(ts.layers)} "
                  f"fixtures={len(ts.fixtures)}")
        except (AssertionError, ValueError) as exc:
            failures += 1
            print(f"  FAIL: {path}: {exc}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify", action="store_true",
                    help="parse-check migrated specs instead of migrating")
    args = ap.parse_args()

    paths = [REPO_ROOT / rel for rel in EXPECTED_TASKS]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise SystemExit("missing task specs: " + ", ".join(map(str, missing)))

    if args.verify:
        failures = verify_all(paths)
        print(f"verify: {len(paths) - failures}/{len(paths)} OK")
        return 1 if failures else 0

    changed = sum(migrate_one(p) for p in paths)
    print(f"migrated {changed}/{len(paths)} specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
