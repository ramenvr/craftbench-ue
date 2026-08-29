"""Unit tests for tools/verify-single/config_lane.py - the semantic config lane.

No UE required. Covers:

  - parse_ue_ini: the UE ini dialect (sections, duplicate +Array keys,
    op-prefix chars as part of the key, comment/blank/CRLF/BOM tolerance,
    values containing '=', pre-section keys);
  - diff_ue_ini: the (section, key) value-MULTISET model (reorder-tolerant,
    modification = removed + added pair, base None = all added);
  - parse_config_allow: the 'file :: section :: key[*]' rule grammar,
    fail-closed on malformed entries;
  - validate_config_submission: rule coverage, no-rules-means-no-changes,
    unreadable files, non-Config rels ignored;
  - classify_config_submission: the FOUR named outcomes (unchanged / allowed /
    disallowed / unreadable), the byte-identity short circuit, BOM-aware
    decoding, and that validate_config_submission DELEGATES to it;
  - sandbox integration: WritableManifest.config_writable path acceptance
    (exact-file, deny-wins, back-compat absent key) plus the REAL
    UE-projects/ThirdPerson/AGENT_WRITABLE.json contents;
  - spec integration: the v2 front-matter 'config_allow:' list key.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make the verify package importable when running this file directly.
_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import config_lane  # noqa: E402
from config_lane import (  # noqa: E402
    DISALLOWED_REASON_PREFIX,
    OUTCOME_ALLOWED,
    OUTCOME_DISALLOWED,
    OUTCOME_UNCHANGED,
    OUTCOME_UNREADABLE,
    UNREADABLE_REASON_PREFIX,
    ConfigAllowRule,
    ConfigChange,
    classify_config_submission,
    decode_ini_bytes,
    diff_ue_ini,
    parse_config_allow,
    parse_ue_ini,
    validate_config_submission,
)
from sandbox import WritableManifest, scan_submission  # noqa: E402
from spec import parse_task_file  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

BOM = "\ufeff"

COLLISION_RULE = (
    "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile :: +Profiles"
)

BASE_ENGINE_INI = (
    "[/Script/Engine.Engine]\n"
    "GameEngine=/Script/Engine.GameEngine\n"
    "\n"
    "[/Script/Engine.CollisionProfile]\n"
    '+Profiles=(Name="Existing",CollisionEnabled=QueryAndPhysics)\n'
)


class TestParseUeIni(unittest.TestCase):
    def test_sections_and_pairs(self) -> None:
        parsed = parse_ue_ini(
            "[SectionA]\nKeyOne=1\nKeyTwo=two\n[SectionB]\nKeyThree=3\n"
        )
        self.assertEqual(
            parsed["SectionA"], [("KeyOne", "1"), ("KeyTwo", "two")]
        )
        self.assertEqual(parsed["SectionB"], [("KeyThree", "3")])

    def test_duplicate_array_keys_preserved_as_separate_entries(self) -> None:
        parsed = parse_ue_ini(
            "[S]\n+Profiles=(Name=\"A\")\n+Profiles=(Name=\"B\")\n"
        )
        self.assertEqual(
            parsed["S"],
            [("+Profiles", '(Name="A")'), ("+Profiles", '(Name="B")')],
        )

    def test_op_prefix_chars_are_part_of_raw_key(self) -> None:
        parsed = parse_ue_ini(
            "[S]\n+AddKey=a\n-RemoveKey=b\n.AppendKey=c\n!ClearKey=d\nPlain=e\n"
        )
        keys = [k for k, _ in parsed["S"]]
        self.assertEqual(
            keys, ["+AddKey", "-RemoveKey", ".AppendKey", "!ClearKey", "Plain"]
        )

    def test_comments_blanks_crlf_and_bom_tolerated(self) -> None:
        text = (
            BOM
            + "; leading comment\r\n"
            + "\r\n"
            + "[S]\r\n"
            + "  ; indented comment\r\n"
            + "Key=Value\r\n"
        )
        parsed = parse_ue_ini(text)
        self.assertEqual(parsed["S"], [("Key", "Value")])

    def test_value_keeps_everything_after_first_equals(self) -> None:
        value = '(Name="X",Responses=((Channel="Vis",Response=ECR_Block)))'
        parsed = parse_ue_ini(f"[S]\n+Profiles={value}\n")
        self.assertEqual(parsed["S"], [("+Profiles", value)])

    def test_pre_section_keys_land_under_empty_section(self) -> None:
        parsed = parse_ue_ini("Orphan=1\n[S]\nKey=2\n")
        self.assertEqual(parsed[""], [("Orphan", "1")])
        self.assertEqual(parsed["S"], [("Key", "2")])


class TestDiffUeIni(unittest.TestCase):
    def test_identical_texts_diff_empty(self) -> None:
        self.assertEqual(diff_ue_ini(BASE_ENGINE_INI, BASE_ENGINE_INI), [])

    def test_added_key(self) -> None:
        new = BASE_ENGINE_INI + "[NewSection]\nNewKey=1\n"
        changes = diff_ue_ini(BASE_ENGINE_INI, new)
        self.assertEqual(
            changes, [ConfigChange("NewSection", "NewKey", "added", "1")]
        )

    def test_removed_key(self) -> None:
        changes = diff_ue_ini(
            "[S]\nKeep=1\nGone=2\n", "[S]\nKeep=1\n"
        )
        self.assertEqual(changes, [ConfigChange("S", "Gone", "removed", "2")])

    def test_value_change_is_removed_plus_added_pair(self) -> None:
        changes = diff_ue_ini("[S]\nKey=old\n", "[S]\nKey=new\n")
        self.assertEqual(
            changes,
            [
                ConfigChange("S", "Key", "removed", "old"),
                ConfigChange("S", "Key", "added", "new"),
            ],
        )

    def test_array_entry_added_among_existing_entries(self) -> None:
        base = "[S]\n+Profiles=(Name=\"A\")\n+Profiles=(Name=\"B\")\n"
        new = (
            "[S]\n+Profiles=(Name=\"B\")\n+Profiles=(Name=\"C\")\n"
            "+Profiles=(Name=\"A\")\n"
        )
        changes = diff_ue_ini(base, new)
        self.assertEqual(
            changes, [ConfigChange("S", "+Profiles", "added", '(Name="C")')]
        )

    def test_reordered_only_array_diffs_empty(self) -> None:
        base = "[S]\n+Profiles=(Name=\"A\")\n+Profiles=(Name=\"B\")\n"
        new = "[S]\n+Profiles=(Name=\"B\")\n+Profiles=(Name=\"A\")\n"
        self.assertEqual(diff_ue_ini(base, new), [])

    def test_base_none_means_everything_added(self) -> None:
        changes = diff_ue_ini(None, "[S]\nKeyOne=1\nKeyTwo=2\n")
        self.assertEqual(
            changes,
            [
                ConfigChange("S", "KeyOne", "added", "1"),
                ConfigChange("S", "KeyTwo", "added", "2"),
            ],
        )

    def test_detail_truncated_to_120_chars(self) -> None:
        long_value = "x" * 300
        changes = diff_ue_ini(None, f"[S]\nKey={long_value}\n")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].detail, "x" * 120)


class TestParseConfigAllow(unittest.TestCase):
    def test_happy_path(self) -> None:
        rules = parse_config_allow([COLLISION_RULE])
        self.assertEqual(
            rules,
            (
                ConfigAllowRule(
                    file="Config/DefaultEngine.ini",
                    section="/Script/Engine.CollisionProfile",
                    key="+Profiles",
                ),
            ),
        )

    def test_wildcard_key_prefix_matches(self) -> None:
        (rule,) = parse_config_allow(
            ["Config/DefaultInput.ini :: /Script/Engine.InputSettings :: +Action*"]
        )
        self.assertTrue(
            rule.matches(
                "Config/DefaultInput.ini",
                "/Script/Engine.InputSettings",
                "+ActionMappings",
            )
        )
        self.assertFalse(
            rule.matches(
                "Config/DefaultInput.ini",
                "/Script/Engine.InputSettings",
                "+AxisMappings",
            )
        )

    def test_exact_key_does_not_prefix_match(self) -> None:
        (rule,) = parse_config_allow([COLLISION_RULE])
        self.assertFalse(
            rule.matches(
                "Config/DefaultEngine.ini",
                "/Script/Engine.CollisionProfile",
                "+ProfilesExtra",
            )
        )

    def test_malformed_entries_raise_value_error_naming_entry(self) -> None:
        for bad in (
            "only-two :: fields",
            "a :: b :: c :: d",
            "Config/DefaultEngine.ini ::  :: +Profiles",
            "",
        ):
            with self.assertRaises(ValueError) as ctx:
                parse_config_allow([bad])
            self.assertIn(repr(bad), str(ctx.exception))


class TestValidateConfigSubmission(unittest.TestCase):
    """End-to-end lane validation over real temp files."""

    def _stage(self, tmp: str, submitted_text: str, rel: str = "Config/DefaultEngine.ini"):
        """Build substrate (with the BASE_ENGINE_INI baseline) + submission."""
        root = Path(tmp)
        substrate = root / "substrate"
        (substrate / "Config").mkdir(parents=True)
        (substrate / "Config" / "DefaultEngine.ini").write_text(
            BASE_ENGINE_INI, encoding="utf-8"
        )
        sub_file = root / "submission" / Path(rel)
        sub_file.parent.mkdir(parents=True, exist_ok=True)
        sub_file.write_text(submitted_text, encoding="utf-8")
        return substrate, sub_file

    def test_allowed_collision_profile_change_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_text = BASE_ENGINE_INI + '+Profiles=(Name="AgentAdded")\n'
            substrate, sub_file = self._stage(tmp, new_text)
            violations = validate_config_submission(
                [(sub_file, "Config/DefaultEngine.ini")],
                substrate,
                parse_config_allow([COLLISION_RULE]),
            )
            self.assertEqual(violations, [])

    def test_same_change_with_no_rules_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_text = BASE_ENGINE_INI + '+Profiles=(Name="AgentAdded")\n'
            substrate, sub_file = self._stage(tmp, new_text)
            violations = validate_config_submission(
                [(sub_file, "Config/DefaultEngine.ini")], substrate, ()
            )
            self.assertEqual(len(violations), 1)
            rel, reason = violations[0]
            self.assertEqual(rel, "Config/DefaultEngine.ini")
            self.assertIn("config change not allowed", reason)

    def test_disallowed_key_in_allowed_file_names_section_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_text = (
                BASE_ENGINE_INI
                + "[/Script/Engine.RendererSettings]\nr.SecretCheat=1\n"
            )
            substrate, sub_file = self._stage(tmp, new_text)
            violations = validate_config_submission(
                [(sub_file, "Config/DefaultEngine.ini")],
                substrate,
                parse_config_allow([COLLISION_RULE]),
            )
            self.assertEqual(len(violations), 1)
            rel, reason = violations[0]
            self.assertEqual(rel, "Config/DefaultEngine.ini")
            self.assertIn("[/Script/Engine.RendererSettings]", reason)
            self.assertIn("r.SecretCheat", reason)
            self.assertIn("(added)", reason)

    def test_new_config_file_with_full_rule_coverage_passes(self) -> None:
        # DefaultInput.ini does not exist in the substrate: baseline is None,
        # so EVERY entry is an "added" change and each needs rule coverage.
        with tempfile.TemporaryDirectory() as tmp:
            substrate, sub_file = self._stage(
                tmp,
                "[/Script/Engine.InputSettings]\n"
                '+ActionMappings=(ActionName="Jump",Key=SpaceBar)\n'
                '+ActionMappings=(ActionName="Fire",Key=LeftMouseButton)\n',
                rel="Config/DefaultInput.ini",
            )
            violations = validate_config_submission(
                [(sub_file, "Config/DefaultInput.ini")],
                substrate,
                parse_config_allow(
                    [
                        "Config/DefaultInput.ini :: "
                        "/Script/Engine.InputSettings :: +ActionMappings"
                    ]
                ),
            )
            self.assertEqual(violations, [])

    def test_unreadable_submitted_file_is_one_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            substrate = Path(tmp) / "substrate"
            substrate.mkdir()
            missing = Path(tmp) / "submission" / "Config" / "DefaultEngine.ini"
            violations = validate_config_submission(
                [(missing, "Config/DefaultEngine.ini")], substrate, ()
            )
            self.assertEqual(len(violations), 1)
            rel, reason = violations[0]
            self.assertEqual(rel, "Config/DefaultEngine.ini")
            self.assertIn("config file unreadable", reason)

    def test_non_config_rels_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "Source" / "ThirdPerson" / "Foo.cpp"
            src.parent.mkdir(parents=True)
            src.write_text("// code\n", encoding="utf-8")
            violations = validate_config_submission(
                [(src, "Source/ThirdPerson/Foo.cpp")], root / "substrate", ()
            )
            self.assertEqual(violations, [])


class TestSandboxConfigWritable(unittest.TestCase):
    """Path-level acceptance: sandbox.WritableManifest.config_writable."""

    MANIFEST = {
        "substrate": "Tiny",
        "game_module": "Tiny",
        "writable": ["Source/Tiny/"],
        "config_writable": ["Config/DefaultEngine.ini"],
        "deny": ["Source/TinyTests/"],
    }

    def _load(self, data: dict) -> WritableManifest:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "AGENT_WRITABLE.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            return WritableManifest.load(p)

    def _scan_one(self, manifest: WritableManifest, rel: str):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / Path(rel)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("[S]\nK=V\n", encoding="utf-8")
            return scan_submission(Path(tmp), manifest)

    def test_listed_config_file_is_path_accepted(self) -> None:
        manifest = self._load(self.MANIFEST)
        result = self._scan_one(manifest, "Config/DefaultEngine.ini")
        self.assertTrue(result.ok, msg=result.render_report())
        self.assertEqual(
            result.accepted[0][1], "Config/DefaultEngine.ini"
        )

    def test_unlisted_config_file_rejects_by_allowlist_miss(self) -> None:
        manifest = self._load(self.MANIFEST)
        result = self._scan_one(manifest, "Config/DefaultGame.ini")
        self.assertFalse(result.ok)
        self.assertIn(
            "not under any writable prefix", result.violations[0].reason
        )

    def test_entries_are_files_not_prefixes(self) -> None:
        # A descendant of a listed FILE path must not ride along.
        manifest = self._load(self.MANIFEST)
        result = self._scan_one(
            manifest, "Config/DefaultEngine.ini/sneaky.ini"
        )
        self.assertFalse(result.ok)
        self.assertIn(
            "not under any writable prefix", result.violations[0].reason
        )

    def test_deny_still_wins_over_config_writable(self) -> None:
        data = dict(self.MANIFEST)
        data["deny"] = ["Config/"]
        manifest = self._load(data)
        result = self._scan_one(manifest, "Config/DefaultEngine.ini")
        self.assertFalse(result.ok)
        self.assertIn("denied by manifest prefix", result.violations[0].reason)

    def test_absent_key_defaults_to_empty_back_compat(self) -> None:
        data = {k: v for k, v in self.MANIFEST.items() if k != "config_writable"}
        manifest = self._load(data)
        self.assertEqual(manifest.config_writable, ())
        result = self._scan_one(manifest, "Config/DefaultEngine.ini")
        self.assertFalse(result.ok)

    def test_real_thirdperson_manifest_wires_the_config_lane(self) -> None:
        manifest_path = (
            REPO_ROOT / "UE-projects" / "ThirdPerson" / "AGENT_WRITABLE.json"
        )
        self.assertTrue(manifest_path.exists(), f"missing {manifest_path}")
        manifest = WritableManifest.load(manifest_path)
        self.assertEqual(
            manifest.config_writable,
            ("Config/DefaultEngine.ini", "Config/DefaultInput.ini"),
        )
        self.assertNotIn("Config/", manifest.deny)


class TestSpecConfigAllow(unittest.TestCase):
    """Front-matter 'config_allow:' list key round-trips into TaskSpec."""

    V2_WITH_CONFIG_ALLOW = (
        "---\n"
        "id: t9-config-lane-demo\n"
        "substrate: ThirdPerson\n"
        "layers: [L1]\n"
        'config_allow: ["' + COLLISION_RULE + '"]\n'
        "---\n"
        "\n"
        "## Prompt given to the agent\n"
        "\n"
        "> Do the thing.\n"
    )

    V2_WITHOUT_CONFIG_ALLOW = (
        "---\n"
        "id: t9-no-config-lane\n"
        "layers: [L1]\n"
        "---\n"
        "\n"
        "## Prompt given to the agent\n"
        "\n"
        "> Do the thing.\n"
    )

    def _parse(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            p.write_text(text, encoding="utf-8")
            return parse_task_file(p)

    def test_config_allow_round_trips(self) -> None:
        spec_obj = self._parse(self.V2_WITH_CONFIG_ALLOW)
        self.assertFalse(spec_obj.legacy)
        self.assertEqual(spec_obj.config_allow, (COLLISION_RULE,))
        # The raw entries feed straight into the lane's rule parser.
        rules = parse_config_allow(spec_obj.config_allow)
        self.assertEqual(rules[0].file, "Config/DefaultEngine.ini")

    def test_absent_key_defaults_to_empty(self) -> None:
        spec_obj = self._parse(self.V2_WITHOUT_CONFIG_ALLOW)
        self.assertEqual(spec_obj.config_allow, ())


# The REAL substrate config the live-project collector now captures on every
# run. Used verbatim rather than a hand-rolled fixture so these tests cannot
# pass on a toy ini the lane would never see.
REAL_THIRDPERSON_ENGINE_INI = (
    REPO_ROOT / "UE-projects" / "ThirdPerson" / "Config" / "DefaultEngine.ini"
)


class TestFourNamedOutcomes(unittest.TestCase):
    """The gate must distinguish no-change / allowed / disallowed / could-not-read.

    WHY THIS CLASS EXISTS (2026-08-19). ``validate_config_submission`` used to
    answer one question -- "any violations?" -- and fold four different states
    into it. That is only a naming complaint until you notice the fourth state
    is COULD-NOT-READ: the lane did
    ``Path(abs_file).read_text(encoding="utf-8")`` and turned a
    UnicodeDecodeError into a violation whose text read "config file
    unreadable", which the runner appends to ``sandbox_result.violations``,
    which is exit 4. A check that cannot tell "no" from "could not tell" is not
    a check.

    Reachability: the live-project collector now captures every manifest
    ``config_writable`` file on EVERY run (run_task.py step (2) of
    ``extract_writable_subset_from_project``), and those files are
    agent-writable, so their encoding is not ours to assume.
    """

    REL = "Config/DefaultEngine.ini"

    def _stage_bytes(self, tmp, submitted: bytes, baseline: bytes = None):
        """substrate/<REL> = baseline (default: the REAL ThirdPerson ini),
        submission/<REL> = submitted. Returns (substrate_root, abs_file)."""
        root = Path(tmp)
        if baseline is None:
            baseline = REAL_THIRDPERSON_ENGINE_INI.read_bytes()
        substrate = root / "substrate"
        (substrate / "Config").mkdir(parents=True)
        (substrate / "Config" / "DefaultEngine.ini").write_bytes(baseline)
        sub = root / "submission" / "Config" / "DefaultEngine.ini"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_bytes(submitted)
        return substrate, sub

    def _classify_one(self, tmp, submitted: bytes, rules=(), baseline=None):
        substrate, sub = self._stage_bytes(tmp, submitted, baseline)
        outcomes = classify_config_submission(
            [(sub, self.REL)], substrate, rules
        )
        self.assertEqual(len(outcomes), 1, "one submitted file -> one outcome")
        return outcomes[0]

    # -- no config change ---------------------------------------------------

    def test_byte_identical_capture_is_unchanged_with_no_rules(self) -> None:
        """An unchanged file is not a config change -- even with no allowlist.

        NOT a new behaviour and NOT a red-first test: the pre-2026-08-19 code
        already diffed identical text to zero changes, and
        ``test_config_lane_e2e.test_untouched_config_file_is_accepted`` already
        pinned it end to end. Kept because the byte-identity SHORT CIRCUIT is
        new, and this is the case it must not change.
        """
        with tempfile.TemporaryDirectory() as tmp:
            raw = REAL_THIRDPERSON_ENGINE_INI.read_bytes()
            outcome = self._classify_one(tmp, raw)
            self.assertEqual(outcome.kind, OUTCOME_UNCHANGED)
            self.assertEqual(outcome.violations, ())
            self.assertTrue(outcome.ok)

    def test_utf16_recode_of_the_real_ini_is_unchanged_not_rejected(self) -> None:
        """Same config, different bytes -> UNCHANGED, not exit 4.

        RED before the fix, measured 2026-08-19 against the real file: the
        utf-8-only read raised UnicodeDecodeError on the UTF-16 BOM and
        returned ``[('Config/DefaultEngine.ini', "config file unreadable:
        'utf-8' codec can't decode byte 0xff in position 0: invalid start
        byte")]`` -- a SANDBOX-REJECT for a submission that changed nothing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            text = REAL_THIRDPERSON_ENGINE_INI.read_text(encoding="utf-8")
            outcome = self._classify_one(tmp, text.encode("utf-16"))
            self.assertEqual(outcome.kind, OUTCOME_UNCHANGED)
            self.assertEqual(outcome.violations, ())

    def test_utf8_bom_and_crlf_rewrites_are_unchanged(self) -> None:
        """An editor rewriting the BOM or the line endings is not a config edit."""
        text = REAL_THIRDPERSON_ENGINE_INI.read_text(encoding="utf-8")
        for label, raw in (
            ("utf-8-sig", text.encode("utf-8-sig")),
            ("crlf", text.replace("\n", "\r\n").encode("utf-8")),
        ):
            with self.subTest(rewrite=label):
                with tempfile.TemporaryDirectory() as tmp:
                    outcome = self._classify_one(tmp, raw)
                    self.assertEqual(outcome.kind, OUTCOME_UNCHANGED)
                    self.assertEqual(outcome.violations, ())

    # -- allowed vs disallowed ----------------------------------------------

    def test_allowed_change_is_named_allowed_not_merely_silent(self) -> None:
        """A covered change is ALLOWED -- an outcome, not the absence of one.

        RED before the fix: ``classify_config_submission`` did not exist, so
        "no violations" was the only way to say this, and it was the same
        answer as "the file did not change".
        """
        with tempfile.TemporaryDirectory() as tmp:
            new_text = BASE_ENGINE_INI + '+Profiles=(Name="AgentAdded")\n'
            outcome = self._classify_one(
                tmp,
                new_text.encode("utf-8"),
                rules=parse_config_allow([COLLISION_RULE]),
                baseline=BASE_ENGINE_INI.encode("utf-8"),
            )
            self.assertEqual(outcome.kind, OUTCOME_ALLOWED)
            self.assertEqual(outcome.violations, ())
            self.assertTrue(outcome.ok)
            self.assertEqual(len(outcome.changes), 1)

    def test_uncovered_change_is_disallowed_and_keeps_its_reason_text(self) -> None:
        """The observed-violation wording is load-bearing and must not drift.

        ``test_config_lane_e2e`` asserts on this substring, several task specs'
        anti-gaming entries quote it, and it is what an operator greps for.
        """
        with tempfile.TemporaryDirectory() as tmp:
            new_text = (
                BASE_ENGINE_INI
                + "[/Script/Engine.RendererSettings]\nr.SecretCheat=1\n"
            )
            outcome = self._classify_one(
                tmp,
                new_text.encode("utf-8"),
                rules=parse_config_allow([COLLISION_RULE]),
                baseline=BASE_ENGINE_INI.encode("utf-8"),
            )
            self.assertEqual(outcome.kind, OUTCOME_DISALLOWED)
            self.assertEqual(len(outcome.violations), 1)
            _rel, reason = outcome.violations[0]
            self.assertTrue(reason.startswith(DISALLOWED_REASON_PREFIX), reason)
            self.assertIn("r.SecretCheat", reason)
            self.assertFalse(outcome.ok)

    # -- could not read: neither a violation nor a pass ---------------------

    def test_undecodable_capture_is_unreadable_not_a_policy_violation(self) -> None:
        """We did not observe a change; we failed to look. Say so.

        RED before the fix on both halves: there was no ``kind`` at all, and
        the reason said "config file unreadable", which reads as a property of
        the submission rather than as an admission that the verdict is
        undetermined.
        """
        with tempfile.TemporaryDirectory() as tmp:
            # No BOM, and invalid utf-8 -- genuinely undecodable, not merely
            # a different encoding we know how to read.
            garbage = bytes([0x5B, 0x53, 0x5D, 0x0A, 0x4B, 0x3D, 0xC3, 0x28])
            outcome = self._classify_one(tmp, garbage)
            self.assertEqual(outcome.kind, OUTCOME_UNREADABLE)
            self.assertEqual(len(outcome.violations), 1)
            _rel, reason = outcome.violations[0]
            self.assertTrue(reason.startswith(UNREADABLE_REASON_PREFIX), reason)
            self.assertIn("UNDETERMINED", reason)
            # Not silently equated with an observed violation ...
            self.assertNotIn(DISALLOWED_REASON_PREFIX, reason)

    def test_unreadable_fails_closed_and_is_never_ok(self) -> None:
        """... and not silently equated with success either.

        The pair with the assertion above: UNKNOWN must still reject. Both
        halves have to hold at once, which is exactly what a single boolean
        could not express.
        """
        with tempfile.TemporaryDirectory() as tmp:
            outcome = self._classify_one(tmp, bytes([0xC3, 0x28]))
            self.assertEqual(outcome.kind, OUTCOME_UNREADABLE)
            self.assertFalse(outcome.ok)
            self.assertTrue(outcome.violations)

    def test_undecodable_but_byte_identical_capture_is_unchanged(self) -> None:
        """Identical bytes are the same config whatever the encoding is.

        RED before the fix: the lane decoded before it compared, so a
        substrate whose committed ini is not utf-8 would have exit-4'd every
        run that merely CAPTURED it -- with the agent having touched nothing.
        This is the case the byte-identity short circuit exists for, and the
        reason it runs before any decode.
        """
        with tempfile.TemporaryDirectory() as tmp:
            weird = bytes([0x5B, 0x53, 0x5D, 0x0A, 0x4B, 0x3D, 0xC3, 0x28])
            outcome = self._classify_one(tmp, weird, baseline=weird)
            self.assertEqual(outcome.kind, OUTCOME_UNCHANGED)
            self.assertEqual(outcome.violations, ())

    def test_undecodable_baseline_is_unreadable_not_everything_added(self) -> None:
        """A baseline we cannot decode must not be treated as ABSENT.

        Absent baseline means "every entry is added", i.e. a flood of
        fictional violations naming keys the agent never touched. Fail closed
        with the UNKNOWN wording instead.
        """
        with tempfile.TemporaryDirectory() as tmp:
            outcome = self._classify_one(
                tmp,
                b"[S]\nKey=1\n",
                baseline=bytes([0xC3, 0x28, 0x0A]),
            )
            self.assertEqual(outcome.kind, OUTCOME_UNREADABLE)
            self.assertEqual(len(outcome.violations), 1)
            self.assertIn("baseline", outcome.violations[0][1])
            self.assertTrue(
                outcome.violations[0][1].startswith(UNREADABLE_REASON_PREFIX)
            )

    def test_missing_submitted_file_is_the_unreadable_class(self) -> None:
        """An OSError is the same "could not look" state as a decode failure."""
        with tempfile.TemporaryDirectory() as tmp:
            substrate = Path(tmp) / "substrate"
            substrate.mkdir()
            missing = Path(tmp) / "submission" / "Config" / "DefaultEngine.ini"
            outcomes = classify_config_submission(
                [(missing, self.REL)], substrate, ()
            )
            self.assertEqual(outcomes[0].kind, OUTCOME_UNREADABLE)
            self.assertFalse(outcomes[0].ok)

    # -- the delegation -----------------------------------------------------

    def test_validate_config_submission_delegates_to_classify(self) -> None:
        """The violation list is a VIEW of the outcomes, not a second rule.

        The shape that worked on 2026-08-19 for the collector fix: one
        implementation, and a caller that would break loudly if the callee
        moved. Monkeypatching the classifier and seeing the facade's answer
        change proves delegation; asserting the two merely AGREE would not.
        """
        sentinel = [
            config_lane.ConfigFileOutcome(
                rel="Config/Whatever.ini",
                kind=OUTCOME_DISALLOWED,
                violations=(("Config/Whatever.ini", "sentinel reason"),),
            )
        ]
        original = config_lane.classify_config_submission
        config_lane.classify_config_submission = (
            lambda submitted, substrate_root, rules: sentinel
        )
        try:
            self.assertEqual(
                config_lane.validate_config_submission([], Path("."), ()),
                [("Config/Whatever.ini", "sentinel reason")],
            )
        finally:
            config_lane.classify_config_submission = original

    def test_non_config_rels_produce_no_outcome_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "Source" / "ThirdPerson" / "Foo.cpp"
            src.parent.mkdir(parents=True)
            src.write_text("// code\n", encoding="utf-8")
            self.assertEqual(
                classify_config_submission(
                    [(src, "Source/ThirdPerson/Foo.cpp")], root / "substrate", ()
                ),
                [],
            )


class TestDecodeIniBytes(unittest.TestCase):
    """The decoder must be BOM-honest and must be allowed to fail."""

    def test_bom_marked_encodings_round_trip(self) -> None:
        text = '[S]\nKey=(Name="value")\n'
        for codec in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be",
                      "utf-32", "utf-32-le", "utf-32-be"):
            with self.subTest(codec=codec):
                raw = text.encode(codec)
                if codec in ("utf-16-le", "utf-16-be",
                             "utf-32-le", "utf-32-be"):
                    # BOM-less variants carry no declaration; only the plain
                    # 'utf-16'/'utf-32' codecs emit one. Skip -- guessing at a
                    # BOM-less wide encoding is exactly what this must not do.
                    continue
                self.assertEqual(decode_ini_bytes(raw).lstrip("\ufeff"), text)

    def test_utf32le_bom_is_not_mistaken_for_utf16le(self) -> None:
        """ff fe 00 00 starts with ff fe -- longest BOM must win."""
        text = "[S]\nKey=1\n"
        self.assertEqual(decode_ini_bytes(text.encode("utf-32")), text)

    def test_undecodable_bytes_raise_rather_than_return_mojibake(self) -> None:
        """No errors="replace", no latin-1 fallback.

        Both always succeed, and the resulting mojibake would diff against the
        baseline as a large set of config changes that never happened -- a
        WRONG answer, not a missing one.
        """
        with self.assertRaises(UnicodeDecodeError):
            decode_ini_bytes(bytes([0xC3, 0x28]))


class TestSourceHygiene(unittest.TestCase):
    def test_config_lane_module_is_pure_ascii(self) -> None:
        raw = (_VERIFY / "config_lane.py").read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_this_test_file_is_pure_ascii_except_bom_constant(self) -> None:
        raw = Path(__file__).read_bytes()
        self.assertTrue(raw.decode("utf-8").isascii())


if __name__ == "__main__":
    unittest.main()
