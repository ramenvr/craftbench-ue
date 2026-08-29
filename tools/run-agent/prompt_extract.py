"""Extract the agent-visible portion of a CraftBench task .md.

Uses an allow-list: only specific H2 sections are kept. Any future
section added to the task spec is dropped by default — preventing
accidental leakage when new answer-key sections are introduced.

Sections KEPT (in order):
    - "## Prompt given to the agent"
    - "## Workspace state pre-task"

Everything else (metadata, primary concept, verifier spec, anti-gaming
notes, reference solution metadata, verifier fixtures, future sections)
is dropped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict


ALLOWED_SECTIONS = (
    "Prompt given to the agent",
    "Workspace state pre-task",
)


def _split_h2_sections(md: str) -> Dict[str, str]:
    """Return {heading_text: body_text} for every '## <heading>' in md.

    Heading matching is exact (case-sensitive) on the text after '## '.
    Body is everything until the next '## ' or end of file.
    """
    sections: Dict[str, str] = {}
    current_heading: str | None = None
    current_body: list[str] = []

    for line in md.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_body).strip("\n")
            current_heading = line[3:].strip()
            current_body = []
        else:
            if current_heading is not None:
                current_body.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_body).strip("\n")

    return sections


def extract_agent_visible_prompt(task_md_path: Path, *, preamble: str = "") -> str:
    """Return the concatenation of the allow-listed sections of a task .md.

    Section bodies are joined with two blank lines between them. Section
    headings themselves are not included in the output. Raises ValueError
    if the task does not contain a 'Prompt given to the agent' section.

    ``preamble`` (the rendered central benchmark contract — see
    tasks/PREAMBLE.md + preamble.render_preamble) is prepended when given,
    with a ``# Task`` heading separating it from the task body so the
    template's own headings and the task text don't run together. Injecting
    HERE makes the contract uniform across every backend that parses task
    specs through this module.
    """
    md = Path(task_md_path).read_text(encoding="utf-8")
    sections = _split_h2_sections(md)

    if "Prompt given to the agent" not in sections:
        raise ValueError(
            f"{task_md_path} has no '## Prompt given to the agent' section"
        )

    chunks: list[str] = []
    for name in ALLOWED_SECTIONS:
        body = sections.get(name)
        if body:
            chunks.append(body)

    text = "\n\n".join(chunks).strip() + "\n"
    if preamble:
        text = preamble.strip() + "\n\n# Task\n\n" + text
    return text
