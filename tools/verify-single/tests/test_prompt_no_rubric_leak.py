"""The agent-visible prompt must not restate the grading rubric.

A band is discriminating only while the agent cannot read it. If the prompt
prints the thresholds, every value gate collapses into one skill - copying
numbers out of a prompt into a details panel - and an agent that knows nothing
about the subject matter scores full marks. That is the defect this file
guards, found in `t1-dawn-fog-lighting-rig` on 2026-07-27 (its prompt restated
"between 0.05 and 0.6", "2 and 20 degrees below horizontal" and "red channel at
least 150" verbatim) and fixed by moving every number into the verifier spec.

Deliberately NOT part of any one row's introspect oracle: this is a property of
the SPEC TEXT and of `prompt_extract`'s allow-list, and it wants to outlive any
particular grader.

Scope note: only rows whose prompt has actually been audited are listed in
`DIGIT_FREE_PROMPTS`. Other specs legitimately carry numbers an agent must be
told (a required count, a name containing a digit), so this is an opt-in
allow-list, not a sweep.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parent.parent

sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

from prompt_extract import (  # noqa: E402
    ALLOWED_SECTIONS,
    extract_agent_visible_prompt,
)

TASKS = _REPO / "tasks"

# task id -> spec path. Every row here has had its prompt audited to contain no
# digit at all once its own id is removed.
DIGIT_FREE_PROMPTS = {
    "t1-dawn-fog-lighting-rig":
        TASKS / "bp" / "t1-dawn-fog-lighting-rig" / "task.md",
    "t1-walk-animation-footstep-cues":
        TASKS / "bp" / "t1-walk-animation-footstep-cues" / "task.md",
}


class TestPromptExtractAllowList(unittest.TestCase):
    """The allow-list is what makes 'answer key' sections safe to write."""

    def test_exactly_two_sections_are_agent_visible(self):
        self.assertEqual(
            ALLOWED_SECTIONS,
            ("Prompt given to the agent", "Workspace state pre-task"),
        )

    def test_both_rows_yield_both_sections_and_nothing_else(self):
        for task_id, path in DIGIT_FREE_PROMPTS.items():
            with self.subTest(task=task_id):
                text = extract_agent_visible_prompt(path)
                self.assertTrue(text.strip())
                # the answer-key H2s must never appear in the extract
                for section in ("## Verifier specification", "## Anti-gaming",
                                "## Hidden invariants", "## Primary concept",
                                "## Reference solution metadata"):
                    self.assertNotIn(section, text)
                # ...nor their distinctive contents
                for token in ("engine default", "dead-gate", "MATRIX",
                              "discrimination/", "tests_run"):
                    self.assertNotIn(token, text,
                                     "%s leaked into the prompt" % token)


class TestNoThresholdLeaksIntoThePrompt(unittest.TestCase):
    def test_no_digit_survives_into_the_agent_visible_prompt(self):
        """Stronger, and far less brittle, than grepping for each threshold.

        Strip the task's own id (whose slug carries the only legitimate digit)
        and the extracted text must contain no digit at all. Any number later
        added to a prompt - a band, a tolerance, an angle, a count - trips this
        and has to be justified by editing the allow-list above.
        """
        for task_id, path in DIGIT_FREE_PROMPTS.items():
            with self.subTest(task=task_id):
                text = extract_agent_visible_prompt(path).replace(task_id, "")
                found = sorted(set(re.findall(r"\d", text)))
                context = [m.group(0)
                           for m in re.finditer(r".{0,60}\d.{0,60}", text)]
                self.assertEqual(found, [],
                                 "numbers leaked into %s's prompt: %s"
                                 % (task_id, context))

    def test_the_dawn_bands_are_absent_from_the_prompt_but_present_in_the_spec(self):
        """The numbers must be gone from the prompt WITHOUT being gone from the
        spec - a row that documents none of its thresholds is worse, not
        better."""
        path = DIGIT_FREE_PROMPTS["t1-dawn-fog-lighting-rig"]
        prompt = extract_agent_visible_prompt(path)
        body = path.read_text(encoding="utf-8")
        for literal in ("[-25, -1]", "[0.05, 5.0]", "[0.01, 0.6]",
                        "[0.1, 10.0]", ">= 1.5", "[1000, 4000]"):
            with self.subTest(band=literal):
                self.assertNotIn(literal, prompt,
                                 "band %r leaked into the prompt" % literal)
                self.assertIn(literal, body,
                              "band %r is graded but documented nowhere"
                              % literal)

    def test_the_retired_leaky_phrasings_are_gone(self):
        """The exact strings the 2026-07-27 review flagged."""
        prompt = extract_agent_visible_prompt(
            DIGIT_FREE_PROMPTS["t1-dawn-fog-lighting-rig"])
        for phrase in ("between `0.05` and `0.6`",
                       "2 and 20\n> degrees below horizontal",
                       "degrees below horizontal",
                       "red channel is at least",
                       "kelvin"):
            self.assertNotIn(phrase, prompt)


if __name__ == "__main__":
    unittest.main()
