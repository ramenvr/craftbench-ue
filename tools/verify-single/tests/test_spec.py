"""Unit tests for tools/verify-single/spec.py — the single task.md parser.

No UE required. Covers:

  - the restricted front-matter grammar (parse_front_matter);
  - the strict v2 TaskSpec builder (defaults, required-iff rules, unknown
    keys, type errors, fixture compact strings);
  - the legacy H2 fallback, asserted field-for-field against what
    run_task.parse_task_spec returns today on REAL committed specs.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make the verify package importable when running this file directly.
_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402  (legacy-parity comparison source)
import spec  # noqa: E402
from spec import Fixture, TaskSpec, parse_front_matter, parse_task_file  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_task(tmpdir: str, text: str, name: str = "task.md") -> Path:
    p = Path(tmpdir) / name
    p.write_text(text, encoding="utf-8")
    return p


V2_FULL = """\
---
id: gp-example-task
substrate: CraftBenchTemplate
set: flagship
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I, R2]
fixtures: ["L_Example :: AExampleFunctionalTest", "L_ExampleControl :: AExampleControlFunctionalTest"]
introspect: [example_check.py]
fps_legs: [60, 20]
deadline_s: 300
action_budget: 25
randomization: [log-tag, actor-tag]
---

# gp-example-task

## Prompt given to the agent

> Do the thing.

## Workspace state pre-task

Some files exist.

## Anti-gaming notes

- a defense
"""


class TestFrontMatterGrammar(unittest.TestCase):
    def test_returns_none_without_leading_delimiter(self):
        self.assertIsNone(parse_front_matter("# a legacy spec\n\n## Prompt\n"))
        self.assertIsNone(parse_front_matter(""))
        # A first line that is not '---' (after BOM/whitespace normalization)
        # stays legacy — e.g. a horizontal rule spelled with extra dashes.
        self.assertIsNone(parse_front_matter("----\nid: x\n---\n"))
        self.assertIsNone(parse_front_matter("--- x\nid: x\n---\n"))

    def test_scalar_and_list_values(self):
        fm = parse_front_matter(
            "---\nid: my-task\nlayers: [L1, L2]\ndeadline_s: 42\n---\nbody\n"
        )
        self.assertEqual(fm["id"], "my-task")
        self.assertEqual(fm["layers"], ["L1", "L2"])
        self.assertEqual(fm["deadline_s"], "42")  # raw strings; typed later

    def test_quoted_scalars_and_list_items_unquoted(self):
        fm = parse_front_matter(
            '---\nid: "my-task"\nfixtures: ["L_A :: AFoo", \'L_B :: ABar\']\n---\n'
        )
        self.assertEqual(fm["id"], "my-task")
        self.assertEqual(fm["fixtures"], ["L_A :: AFoo", "L_B :: ABar"])

    def test_empty_list(self):
        fm = parse_front_matter("---\nid: t\nlayers: []\n---\n")
        self.assertEqual(fm["layers"], [])

    def test_blank_and_comment_lines_tolerated(self):
        fm = parse_front_matter("---\n\n# comment\nid: t\n---\n")
        self.assertEqual(fm["id"], "t")

    def test_missing_closing_delimiter_raises(self):
        with self.assertRaises(ValueError):
            parse_front_matter("---\nid: t\n")

    def test_non_key_value_line_raises(self):
        with self.assertRaises(ValueError):
            parse_front_matter("---\nthis is not a kv line\n---\n")

    def test_multiline_list_raises(self):
        with self.assertRaises(ValueError):
            parse_front_matter("---\nlayers: [L1,\n  L2]\n---\n")

    def test_duplicate_key_raises(self):
        with self.assertRaises(ValueError):
            parse_front_matter("---\nid: a\nid: b\n---\n")

    def test_bom_on_opening_delimiter_tolerated(self):
        # A UTF-8 BOM must NOT silently route a v2 spec to the legacy parser.
        fm = parse_front_matter("﻿---\nid: t\nlayers: [L1]\n---\n")
        self.assertIsNotNone(fm)
        self.assertEqual(fm["id"], "t")

    def test_whitespace_around_opening_delimiter_tolerated(self):
        fm = parse_front_matter("---  \nid: t\nlayers: [L1]\n---\n")
        self.assertIsNotNone(fm)
        self.assertEqual(fm["id"], "t")


class TestV2Spec(unittest.TestCase):
    def _parse(self, text: str) -> TaskSpec:
        with tempfile.TemporaryDirectory() as td:
            return parse_task_file(_write_task(td, text))

    def test_full_round_trip(self):
        t = self._parse(V2_FULL)
        self.assertEqual(t.task_id, "gp-example-task")
        self.assertEqual(t.substrate, "CraftBenchTemplate")
        self.assertEqual(t.set_name, "flagship")
        self.assertEqual(t.tier, "T1")
        self.assertEqual(t.capability_bucket, "Gameplay Programming")
        self.assertEqual(t.category, "gameplay")
        self.assertEqual(t.layers, ("L1", "L2", "L2I", "R2"))
        self.assertEqual(
            t.fixtures,
            (
                Fixture("L_Example", "AExampleFunctionalTest"),
                Fixture("L_ExampleControl", "AExampleControlFunctionalTest"),
            ),
        )
        self.assertEqual(t.introspect_scripts, ("example_check.py",))
        self.assertEqual(t.fps_legs, (60, 20))
        self.assertEqual(t.deadline_s, 300.0)
        self.assertEqual(t.action_budget, 25)
        self.assertEqual(t.randomization, ("log-tag", "actor-tag"))
        self.assertTrue(t.declares_r2)
        self.assertFalse(t.legacy)
        # Hints derive from fixtures[0], never from prose scans.
        self.assertEqual(t.map_name, "L_Example")
        self.assertEqual(t.test_class_hint, "AExampleFunctionalTest")
        self.assertIn("## Prompt given to the agent", t.raw_text)

    def test_fixtures_are_plain_tuples_too(self):
        t = self._parse(V2_FULL)
        # Fixture is a NamedTuple: downstream (map, cls) unpacking works.
        m, c = t.fixtures[0]
        self.assertEqual((m, c), ("L_Example", "AExampleFunctionalTest"))
        self.assertEqual(t.fixtures[0], ("L_Example", "AExampleFunctionalTest"))

    def test_defaults(self):
        t = self._parse("---\nid: minimal-task\nlayers: [L1]\n---\nbody\n")
        self.assertEqual(t.substrate, "CraftBenchTemplate")
        self.assertIsNone(t.set_name)
        self.assertIsNone(t.tier)
        self.assertIsNone(t.capability_bucket)
        self.assertIsNone(t.category)
        self.assertEqual(t.rhi, "null")
        self.assertEqual(t.fixtures, ())
        self.assertIsNone(t.map_name)
        self.assertIsNone(t.test_class_hint)
        self.assertEqual(t.fps_legs, ())
        self.assertEqual(t.introspect_scripts, ())
        self.assertEqual(t.deadline_s, 600.0)
        self.assertEqual(t.action_budget, 30)
        self.assertEqual(t.randomization, ())
        self.assertFalse(t.declares_r2)
        self.assertFalse(t.legacy)

    def test_real_rhi_contract(self):
        t = self._parse("---\nid: real-rhi-task\nlayers: [L1]\nrhi: real\n---\n")
        self.assertEqual(t.rhi, "real")

    def test_unknown_rhi_contract_rejected(self):
        with self.assertRaisesRegex(ValueError, "'rhi'"):
            self._parse("---\nid: bad-rhi-task\nlayers: [L1]\nrhi: gpu\n---\n")

    def test_d3d11_rhi_contract(self):
        t = self._parse("---\nid: d3d11-task\nlayers: [L1]\nrhi: d3d11\n---\n")
        self.assertEqual(t.rhi, "d3d11")

    def test_prose_map_mentions_do_not_leak_into_hints(self):
        # The front-matter path must NOT run the legacy global regex scans:
        # a map path + class name in the body prose must not become hints.
        t = self._parse(
            "---\nid: prose-task\nlayers: [L1]\n---\n"
            "## Workspace state pre-task\n\n"
            "- `Maps/prose-task/L_Prose.umap` mentions `AProseFunctionalTest`.\n"
        )
        self.assertIsNone(t.map_name)
        self.assertIsNone(t.test_class_hint)

    def test_l4_l5_recognized_but_parse(self):
        t = self._parse("---\nid: t-future\nlayers: [L1, L4, L5]\n---\n")
        self.assertEqual(t.layers, ("L1", "L4", "L5"))

    def test_unknown_layer_token_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown layer token"):
            self._parse("---\nid: t-bad\nlayers: [L1, L9]\n---\n")

    def test_l2_without_fixtures_error(self):
        with self.assertRaisesRegex(ValueError, "fixtures"):
            self._parse("---\nid: t-l2\nlayers: [L1, L2]\n---\n")

    def test_l2_with_empty_fixtures_error(self):
        with self.assertRaisesRegex(ValueError, "fixtures"):
            self._parse("---\nid: t-l2\nlayers: [L1, L2]\nfixtures: []\n---\n")

    def test_fixtures_without_l2_error(self):
        with self.assertRaisesRegex(ValueError, "L2"):
            self._parse(
                '---\nid: t-fx\nlayers: [L1]\nfixtures: ["L_A :: AFoo"]\n---\n'
            )

    def test_l2i_without_introspect_error(self):
        with self.assertRaisesRegex(ValueError, "introspect"):
            self._parse("---\nid: t-l2i\nlayers: [L1, L2I]\n---\n")

    def test_introspect_without_l2i_error(self):
        with self.assertRaisesRegex(ValueError, "L2I"):
            self._parse(
                "---\nid: t-in\nlayers: [L1]\nintrospect: [check.py]\n---\n"
            )

    def test_introspect_non_py_rejected(self):
        with self.assertRaisesRegex(ValueError, r"\.py"):
            self._parse(
                "---\nid: t-in\nlayers: [L2I]\nintrospect: [check.txt]\n---\n"
            )

    def test_unknown_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown front matter key"):
            self._parse("---\nid: t\nlayers: [L1]\nbanana: yes\n---\n")

    def test_missing_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "'id'"):
            self._parse("---\nlayers: [L1]\n---\n")

    def test_non_kebab_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "kebab"):
            self._parse("---\nid: BadTask\nlayers: [L1]\n---\n")

    def test_missing_layers_rejected(self):
        with self.assertRaisesRegex(ValueError, "'layers'"):
            self._parse("---\nid: t\n---\n")

    def test_layers_scalar_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be a list"):
            self._parse("---\nid: t\nlayers: L1\n---\n")

    def test_scalar_key_given_list_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be a scalar"):
            self._parse("---\nid: t\nlayers: [L1]\ntier: [T1]\n---\n")

    def test_bad_fixture_string_rejected(self):
        with self.assertRaisesRegex(ValueError, "bad fixture"):
            self._parse(
                '---\nid: t\nlayers: [L2]\nfixtures: ["NotAMap :: AFoo"]\n---\n'
            )

    def test_fps_legs_non_int_rejected(self):
        with self.assertRaisesRegex(ValueError, "fps_legs"):
            self._parse("---\nid: t\nlayers: [L1]\nfps_legs: [60, fast]\n---\n")

    def test_deadline_non_number_rejected(self):
        with self.assertRaisesRegex(ValueError, "deadline_s"):
            self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: soon\n---\n")

    def test_action_budget_non_int_rejected(self):
        with self.assertRaisesRegex(ValueError, "action_budget"):
            self._parse("---\nid: t\nlayers: [L1]\naction_budget: 3.5\n---\n")

    def test_randomization_non_kebab_rejected(self):
        with self.assertRaisesRegex(ValueError, "kebab"):
            self._parse(
                "---\nid: t\nlayers: [L1]\nrandomization: [LOG_TAG]\n---\n"
            )

    def test_deadline_accepts_float(self):
        t = self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: 90.5\n---\n")
        self.assertEqual(t.deadline_s, 90.5)

    def test_bom_spec_routes_to_v2_not_legacy(self):
        # End-to-end: a BOM'd v2 file parses via the front-matter path
        # (legacy=False, clean layers) instead of the legacy whole-file scan.
        t = self._parse("﻿---\nid: bom-task\nlayers: [L1]\n---\nbody\n")
        self.assertFalse(t.legacy)
        self.assertEqual(t.task_id, "bom-task")
        self.assertEqual(t.layers, ("L1",))

    # --- numeric range validation ------------------------------------------

    def test_fps_legs_zero_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be >= 1"):
            self._parse("---\nid: t\nlayers: [L1]\nfps_legs: [0]\n---\n")

    def test_fps_legs_negative_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be >= 1"):
            self._parse("---\nid: t\nlayers: [L1]\nfps_legs: [60, -20]\n---\n")

    def test_deadline_zero_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite and > 0"):
            self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: 0\n---\n")

    def test_deadline_negative_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite and > 0"):
            self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: -5\n---\n")

    def test_deadline_nan_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite and > 0"):
            self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: nan\n---\n")

    def test_deadline_inf_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite and > 0"):
            self._parse("---\nid: t\nlayers: [L1]\ndeadline_s: inf\n---\n")

    def test_action_budget_zero_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be >= 1"):
            self._parse("---\nid: t\nlayers: [L1]\naction_budget: 0\n---\n")

    def test_action_budget_negative_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be >= 1"):
            self._parse("---\nid: t\nlayers: [L1]\naction_budget: -3\n---\n")


# Real committed specs used for the legacy-parity check. Chosen to cover the
# three legacy shapes: single-fixture derivation (t0), a "## Verifier
# fixtures" multi-fixture block (gp-gas-launch), and the unified "## Verifier
# layers" block + introspection (umg-image-brush-bound).
# Frozen legacy-format samples. The live tasks/ tree is fully migrated to v2
# front matter (2026-07-16), so legacy-path coverage uses these embedded
# specimens instead of committed files (which would race any migration).
LEGACY_SINGLE = """\
# Sanity: log on BeginPlay

## Task ID and metadata

- task_id: legacy-single
- substrate: template
- tier: T1
- capability_bucket: Gameplay Programming
- set: internal-1

## Primary concept

- actor-lifecycle

## Prompt given to the agent

Make the placed actor log a token when play begins.

## Verifier layers used

- L1
- L2

## Verifier fixtures

- L_SanityTask :: ASanityFunctionalTest

## Deadline

- 300 seconds

## Anti-gaming notes

- a :: b
- c :: d
- e :: f
"""

LEGACY_MULTI = """\
# GAS launch (two legs)

## Task ID and metadata

- task_id: legacy-multi
- substrate: template

## Prompt given to the agent

Launch the pawn when the ability fires.

## Verifier layers used

- L1
- L2

## Verifier fixtures

- L_GasLaunch :: AGasLaunchFunctionalTest
- L_GasLaunchControl :: AGasLaunchControlFunctionalTest

## Verifier framerate legs

- 60
- 20

## Randomization

- log-tag
"""


def _write_legacy(td: str, text: str, folder: str) -> Path:
    d = Path(td) / folder
    d.mkdir(parents=True, exist_ok=True)
    p = d / "task.md"
    p.write_text(text, encoding="utf-8")
    return p


class TestLegacyFallbackParity(unittest.TestCase):
    """spec.parse_task_file on a legacy spec must equal run_task.parse_task_spec."""

    def _assert_parity(self, path: Path):
        self.assertTrue(path.is_file(), f"missing committed spec: {path}")
        new = parse_task_file(path)
        old = run_task.parse_task_spec(path)

        self.assertTrue(new.legacy, "legacy flag must be True for H2 specs")
        self.assertEqual(new.task_id, old.task_id)
        self.assertEqual(new.substrate, old.substrate)
        self.assertEqual(new.layers, old.layers)
        self.assertEqual(new.map_name, old.map_name)
        self.assertEqual(new.test_class_hint, old.test_class_hint)
        self.assertEqual(
            [(f.map_name, f.test_class) for f in new.fixtures],
            [(f.map_name, f.test_class) for f in old.fixtures],
        )
        self.assertEqual(new.deadline_s, old.deadline_s)
        self.assertEqual(new.action_budget, old.action_budget)
        self.assertEqual(new.randomization, old.randomization)
        self.assertEqual(new.introspect_scripts, old.introspect_scripts)
        self.assertEqual(new.fps_legs, old.fps_legs)
        self.assertEqual(new.artifact_path, old.artifact_path)
        self.assertEqual(
            [(f.map_name, f.test_class) for f in new.l3_fixtures],
            [(f.map_name, f.test_class) for f in old.l3_fixtures],
        )
        self.assertEqual(new.raw_text, old.raw_text)
        self.assertEqual(new.source_path, old.source_path)

    def test_parity_on_frozen_legacy_samples(self):
        with tempfile.TemporaryDirectory() as td:
            for folder, text in (("legacy-single", LEGACY_SINGLE),
                                 ("legacy-multi", LEGACY_MULTI)):
                with self.subTest(spec=folder):
                    self._assert_parity(_write_legacy(td, text, folder))

    def test_parity_on_all_committed_specs(self):
        """Belt-and-braces: every committed task.md parses identically."""
        specs = sorted((REPO_ROOT / "tasks").glob("*/*/task.md"))
        self.assertGreaterEqual(len(specs), 2, "expected committed task specs")
        for p in specs:
            # Skip any spec already migrated to v2 front matter.
            if p.read_text(encoding="utf-8").startswith("---\n"):
                continue
            with self.subTest(spec=str(p.relative_to(REPO_ROOT))):
                self._assert_parity(p)

    def test_legacy_metadata_card_fields(self):
        with tempfile.TemporaryDirectory() as td:
            t = parse_task_file(_write_legacy(td, LEGACY_SINGLE, "legacy-single"))
        self.assertEqual(t.tier, "T1")
        self.assertEqual(t.capability_bucket, "Gameplay Programming")
        self.assertEqual(t.set_name, "internal-1")
        self.assertEqual(t.substrate, "template")  # legacy alias preserved

    def test_legacy_flag_and_v2_flag(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = parse_task_file(
                _write_legacy(td, LEGACY_SINGLE, "legacy-single"))
        self.assertTrue(legacy.legacy)
        with tempfile.TemporaryDirectory() as td:
            v2 = parse_task_file(_write_task(td, V2_FULL))
        self.assertFalse(v2.legacy)

    def test_legacy_filename_fallback_task_id(self):
        # No metadata block: task.md derives id from the parent folder name,
        # exactly like run_task.parse_task_spec.
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "my-fallback-task"
            folder.mkdir()
            p = folder / "task.md"
            p.write_text("# untitled\n\n## Verifier layers used\n\n- L1\n",
                         encoding="utf-8")
            new = parse_task_file(p)
            old = run_task.parse_task_spec(p)
        self.assertEqual(new.task_id, "my-fallback-task")
        self.assertEqual(new.task_id, old.task_id)
        self.assertEqual(new.substrate, old.substrate)  # "template"


if __name__ == "__main__":
    unittest.main()
