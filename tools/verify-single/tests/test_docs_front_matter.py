"""Every front-matter example in the docs must parse through THE parser.

``docs/AUTHORING_TEMPLATE.md`` is normative (EVALS.md step 1
cites it for the grammar) and it is the file every task author copies from. On
2026-07-25 it documented no v2 front matter at all — 1121 lines of the legacy H2
format, with ``set:`` values naming three task sets deleted 2026-07-08 and
``substrate: template | lyra`` naming a substrate that does not exist. An author
following it wrote a spec the parser only read through its legacy fallback.

So: any fenced block in the docs that LOOKS like a task spec's front matter is
extracted and fed to ``spec.parse_task_file``. A block that cannot round-trip
is a documentation bug that would land in a real ``task.md``.

The multi-line-list trap this is most likely to catch: ``fixtures:`` must be an
INLINE ``[a, b]`` list. Written YAML-style across two lines it raises
``front matter line N is not 'key: value'`` — a shape that reads perfectly to a
human and fails instantly for the parser.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import spec

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Docs that carry (or should carry) copyable spec examples.
SCANNED = (
    Path("docs") / "AUTHORING_TEMPLATE.md",
    Path("docs") / "TASK-AUTHOR-GUIDE.md",
    Path("EVALS.md"),
    Path("tasks") / "README.md",
)

#: A fenced block whose FIRST line is `---` and which assigns `id:` is a task
#: front-matter example. Anything else in a fence (C++, shell, JSON) is ignored.
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*$")


def _front_matter_blocks(text: str):
    """Yield ``(line_number, block_text)`` for each front-matter-looking fence."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            start = i + 1
            j = start
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            block = "\n".join(lines[start:j])
            stripped = block.lstrip()
            if stripped.startswith("---") and re.search(r"(?m)^id\s*:", block):
                yield start + 1, block
            i = j + 1
            continue
        i += 1


def _all_examples():
    out = []
    for rel in SCANNED:
        p = REPO_ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for lineno, block in _front_matter_blocks(text):
            out.append((rel, lineno, block))
    return out


class TestDocFrontMatterRoundTrips(unittest.TestCase):
    def test_every_example_parses(self):
        failures = []
        for rel, lineno, block in _all_examples():
            body = block if block.endswith("\n") else block + "\n"
            # A front-matter example is a spec HEAD; give it the one body
            # section every spec carries so the whole file is realistic.
            if "## Prompt given to the agent" not in body:
                body += "\n# example\n\n## Prompt given to the agent\n\n> behavior.\n"
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "task.md"
                p.write_text(body, encoding="utf-8")
                try:
                    parsed = spec.parse_task_file(p)
                except ValueError as exc:
                    failures.append(f"{rel}:{lineno} — {exc}")
                    continue
                if parsed.legacy:
                    failures.append(
                        f"{rel}:{lineno} — parsed via the LEGACY H2 fallback, not v2 "
                        f"front matter; the normative docs must show v2")
        self.assertFalse(failures, "doc front-matter examples that do not round-trip:\n"
                                   + "\n".join(failures))

    def test_the_normative_template_actually_shows_v2_front_matter(self):
        # Guards the vacuous-pass case: if AUTHORING_TEMPLATE.md stops carrying a
        # front-matter example, test_every_example_parses passes by finding
        # nothing — which is exactly the state that shipped the drift.
        template = Path("docs") / "AUTHORING_TEMPLATE.md"
        blocks = [b for (rel, _ln, b) in _all_examples() if rel == template]
        self.assertTrue(
            blocks,
            f"{template} carries NO v2 front-matter example — it is the file every "
            f"author copies from, and which the guides call normative")

    def test_multiline_list_would_be_caught(self):
        # Proof the round-trip has teeth: the shape a human would naturally
        # write must fail, so a doc example in that shape cannot pass silently.
        bad = ("---\nid: demo\nlayers: [L1, L2]\nfixtures:\n"
               '  - "L_Demo :: ADemoFunctionalTest"\n---\n')
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "task.md"
            p.write_text(bad, encoding="utf-8")
            with self.assertRaises(ValueError):
                spec.parse_task_file(p)

    def _template_code_blocks(self) -> str:
        """Every fenced block in AUTHORING_TEMPLATE.md, joined.

        Scoped to fenced blocks because that is the COPYABLE surface — an
        author lifts a block, not a sentence. Prose may (and should) name a
        retired key in order to warn about it, so scanning prose produces false
        positives on the very warnings that fix the drift.
        """
        text = (REPO_ROOT / "docs" / "AUTHORING_TEMPLATE.md").read_text(
            encoding="utf-8", errors="replace")
        blocks, inside, buf = [], False, []
        for line in text.splitlines():
            if line.startswith("```"):
                if inside:
                    blocks.append("\n".join(buf))
                    buf = []
                inside = not inside
                continue
            if inside:
                buf.append(line)
        return "\n".join(blocks)

    def test_retired_keys_and_sets_are_not_in_any_copyable_block(self):
        """`deadline_seconds` is not a v2 key (it is `deadline_s`), and the
        `internal-1`/`concept-1`/`canary` sets were deleted 2026-07-08 — the
        pre-migration template offered all four inside a copyable block."""
        blocks = self._template_code_blocks()
        for dead in ("deadline_seconds", "task_id:", "internal-1", "concept-1",
                     "canary"):
            self.assertNotIn(
                dead, blocks,
                f"{dead!r} appears in a copyable block in AUTHORING_TEMPLATE.md — "
                f"an author will paste it into a real task.md")

    def test_lyra_is_not_offered_as_a_substrate(self):
        blocks = self._template_code_blocks()
        bad = [ln.strip() for ln in blocks.splitlines()
               if re.search(r"substrate\s*:.*lyra", ln, re.I)]
        self.assertFalse(bad, f"substrate: lyra is not a real substrate "
                              f"(CraftBenchTemplate | ThirdPerson): {bad}")

    def test_every_substrate_named_in_a_block_exists_on_disk(self):
        blocks = self._template_code_blocks()
        for m in re.finditer(r"(?m)^\s*substrate\s*:\s*(\S+)\s*$", blocks):
            name = m.group(1).strip("\"'")
            self.assertTrue((REPO_ROOT / "UE-projects" / name).is_dir(),
                            f"substrate: {name} has no UE-projects/{name}/ on disk")


if __name__ == "__main__":
    unittest.main()
