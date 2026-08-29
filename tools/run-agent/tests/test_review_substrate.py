"""`cb review` must reset the scratch from the run's OWN substrate.

WHY THIS FILE EXISTS. Until 2026-08-15 the reset used `paths.template_dir`, which
`stack.py` hard-codes to CraftBenchTemplate, and it mirrors with
`delete_extras=True`. So reviewing any of the 43 ThirdPerson tasks mirrored the
WRONG substrate's Content over the scratch and DELETED BP_ThirdPersonCharacter,
the player controller and IMC_Default — the exact rig that makes a review
playable. The failure is silent: you get a level with no player and no obvious
reason why.

The tests below pin both halves: the resolver picks the right substrate per task,
and an UNRESOLVABLE run yields None so the caller skips the reset rather than
falling back to the destructive default.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RUNAGENT = _HERE.parent
if str(_RUNAGENT) not in sys.path:
    sys.path.insert(0, str(_RUNAGENT))

from aura_rig import cb  # noqa: E402

_REPO = _RUNAGENT.parent.parent


class _Paths:
    craftbench = _REPO


class _Ctx:
    paths = _Paths()


class ReviewSubstrateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _summary(self, payload):
        (self.run / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    def _resolve(self, run_dir=None):
        return cb._review_substrate_content(_Ctx(), run_dir or self.run)

    # ---- the resolver ----------------------------------------------------

    def test_a_thirdperson_task_resolves_to_thirdperson(self):
        self._summary({"verifier": {"task_id": "gp-poison-dot-stack-bp"}})
        got = self._resolve()
        self.assertIsNotNone(got)
        self.assertEqual("ThirdPerson", got.parent.name)

    def test_a_template_task_resolves_to_craftbenchtemplate(self):
        self._summary({"verifier": {"task_id": "gp-crafting-queue"}})
        got = self._resolve()
        self.assertIsNotNone(got)
        self.assertEqual("CraftBenchTemplate", got.parent.name)

    def test_the_two_substrates_actually_differ(self):
        """Guards the whole point: if both resolved the same, the bug would be
        invisible to every test above."""
        self._summary({"verifier": {"task_id": "gp-poison-dot-stack-bp"}})
        tp = self._resolve()
        self._summary({"verifier": {"task_id": "gp-crafting-queue"}})
        tmpl = self._resolve()
        self.assertNotEqual(tp, tmpl)

    def test_task_id_at_top_level_also_works(self):
        self._summary({"task_id": "gp-crafting-queue"})
        self.assertEqual("CraftBenchTemplate", self._resolve().parent.name)

    def test_result_json_is_read_when_summary_is_absent(self):
        (self.run / "result.json").write_text(
            json.dumps({"verifier": {"task_id": "gp-poison-dot-stack-bp"}}),
            encoding="utf-8")
        self.assertEqual("ThirdPerson", self._resolve().parent.name)

    # ---- the fail-safe ---------------------------------------------------

    def test_a_freeform_drive_resolves_to_None(self):
        """`cb headless` has no task. None must mean 'skip the reset', never
        'fall back to CraftBenchTemplate' — that fallback IS the bug."""
        self._summary({"label": "drive", "mode": "drive"})
        self.assertIsNone(self._resolve())

    def test_an_empty_run_dir_resolves_to_None(self):
        self.assertIsNone(self._resolve())

    def test_unparseable_json_resolves_to_None(self):
        (self.run / "summary.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(self._resolve())

    def test_an_unknown_task_id_resolves_to_None(self):
        self._summary({"verifier": {"task_id": "no-such-task-anywhere"}})
        self.assertIsNone(self._resolve())

    # ---- the dir-name fallback, for runs predating the embedded report ----

    def test_the_dir_name_is_used_when_no_report_exists(self):
        d = self.run / "bp-g2__gp-glide-stamina-bp-20260803-230141"
        d.mkdir()
        got = self._resolve(d)
        self.assertIsNotNone(got)
        self.assertEqual("ThirdPerson", got.parent.name)

    def test_the_dir_name_match_prefers_the_LONGEST_id(self):
        """`gp-poison-dot-stack-bp` contains no shorter id today, but the -cpp/-bp
        rename history shows how easily one id becomes another's substring; the
        resolver sorts longest-first so the specific id wins."""
        d = self.run / "eval__gp-poison-dot-stack-bp-20260101-000000"
        d.mkdir()
        got = self._resolve(d)
        self.assertIsNotNone(got)
        self.assertEqual("ThirdPerson", got.parent.name)

    def test_an_embedded_report_BEATS_the_dir_name(self):
        d = self.run / "mislabelled__gp-crafting-queue-20260101-000000"
        d.mkdir()
        (d / "summary.json").write_text(
            json.dumps({"verifier": {"task_id": "gp-poison-dot-stack-bp"}}),
            encoding="utf-8")
        self.assertEqual("ThirdPerson", self._resolve(d).parent.name)

    # ---- the call site ---------------------------------------------------

    def test_cmd_review_no_longer_resets_from_template_dir(self):
        """A source assertion, because the destructive line is a one-token
        regression away and no runtime test here opens an editor."""
        src = (_RUNAGENT / "aura_rig" / "cb.py").read_text(encoding="utf-8")
        head = src.index("def cmd_review(")
        body = src[head:head + 6000]
        self.assertNotIn("tmpl_content = ctx.paths.template_dir", body)
        self.assertIn("_review_substrate_content(ctx, run_dir)", body)


if __name__ == "__main__":
    unittest.main()
