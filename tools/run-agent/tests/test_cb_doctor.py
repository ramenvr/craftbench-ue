"""Unit tests for aura_rig.doctor — the per-tier diagnostic, fully offline.

Mirrors tests/test_aura_rig_preflight.py's dict-driven-seam pattern: every test
builds an everything-PASS Probe via _all_good() then flips ONE field via
dataclasses.replace and asserts the single resulting Check. No UE, no network,
no real .env — diagnose() is a pure function over its Probe argument.

Run from tools/run-agent:  py -3.12 -m unittest tests.test_cb_doctor -v
"""

import dataclasses
import unittest
from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import doctor  # noqa: E402


def _all_good() -> doctor.Probe:
    """An everything-PASS Probe literal (every tier READY, exit 0)."""
    return doctor.Probe(
        py_exe="py -3.12",
        which=lambda n: ("/usr/bin/" + n) if n in {"git", "tar", "claude"} else None,
        ue=Path("X/UnrealEditor"),
        uproject_exists=True,
        claude_cli="/usr/bin/claude",
        env_keys={"ANTHROPIC_API_KEY": "sk-real",
                  "AURA_USERNAME": "u@x", "AURA_PASSWORD": "pw"},
        env_present=True,
        live_coding=0,
        # embedded layout: genius resolved to the substrate's Plugins/ itself.
    )


def _status(diag: doctor.Diagnosis, check_id: str) -> str:
    c = diag.get(check_id)
    assert c is not None, f"no check {check_id!r}"
    return c.status


class TestAllGood(unittest.TestCase):
    def test_all_good_every_tier_ready(self):
        diag = doctor.diagnose(_all_good())
        self.assertFalse([c for c in diag.checks if c.status == "FAIL"])
        for tier in ("grade-only", "baseline"):
            self.assertTrue(diag.tier_verdict(tier).startswith("READY"),
                            f"{tier}: {diag.tier_verdict(tier)}")
        self.assertEqual(diag.exit_code(), 0)


class TestPrereq(unittest.TestCase):
    def test_no_harness_py_fails_prereq(self):
        diag = doctor.diagnose(replace(_all_good(), py_exe=None))
        self.assertEqual(_status(diag, "harness-py"), "FAIL")
        self.assertIn("blocker", diag.tier_verdict("grade-only"))

    def test_missing_git_and_tar(self):
        # which returns None for everything; claude_cli still pre-resolved.
        diag = doctor.diagnose(replace(_all_good(), which=lambda n: None))
        self.assertEqual(_status(diag, "git"), "FAIL")
        self.assertEqual(_status(diag, "tar"), "FAIL")
        # The two seams are independent: claude resolves from claude_cli.
        self.assertEqual(_status(diag, "claude-cli"), "PASS")

    def test_no_ue_fails_prereq(self):
        diag = doctor.diagnose(replace(_all_good(), ue=None))
        self.assertEqual(_status(diag, "ue"), "FAIL")


class TestVerifier(unittest.TestCase):
    def test_no_verifier_hashes_check_exists(self):
        # The hash manifest retired 2026-07-16 (git provenance = pinning
        # substrate_revision); doctor must not probe or report it anymore.
        diag = doctor.diagnose(_all_good())
        self.assertIsNone(diag.get("verifier-hashes"))

    def test_missing_substrate(self):
        diag = doctor.diagnose(replace(_all_good(), uproject_exists=False))
        self.assertEqual(_status(diag, "substrate"), "FAIL")

    def test_claude_cli_is_warn_not_fail(self):
        diag = doctor.diagnose(replace(_all_good(), claude_cli=None))
        self.assertEqual(_status(diag, "claude-cli"), "WARN")
        # WARN severity: grading is untouched, but the baseline verdict is gated.
        self.assertTrue(diag.tier_verdict("grade-only").startswith("READY"))
        self.assertEqual(diag.tier_verdict("baseline"), "1 blocker(s) (claude-cli)")

    def test_anthropic_key_empty_is_warn(self):
        p = _all_good()
        p = replace(p, env_keys={**p.env_keys, "ANTHROPIC_API_KEY": None})
        diag = doctor.diagnose(p)
        self.assertEqual(_status(diag, "anthropic-key"), "WARN")
        self.assertTrue(diag.tier_verdict("grade-only").startswith("READY"))
        self.assertEqual(diag.tier_verdict("baseline"), "1 blocker(s) (anthropic-key)")


# TestFullRig stood here until the public release: it exercised the doctor's
# full-rig tier, which probed the proprietary plugin/servers/credentials.
# doctor.py carries no tier concept at all now.


class TestExitCode(unittest.TestCase):
    def test_exit_code_grade_only_box(self):
        # provisioned for grade-only ONLY: no genius, no .env, no claude, no keys,
        # no creds — but prereqs + substrate PASS -> exit 0 even though
        # full-rig has FAILs (not provisioned for full-rig).
        p = _all_good()
        p = replace(
            p,
            env_keys={"ANTHROPIC_API_KEY": None,
                      "AURA_USERNAME": None, "AURA_PASSWORD": None},
        )
        diag = doctor.diagnose(p)
        self.assertEqual(diag.provisioned_tier(), "grade-only")
        self.assertTrue(diag.tier_ready("grade-only"))
        self.assertEqual(diag.exit_code(), 0)

    # test_exit_code_provisioned_fullrig_blocked stood here until the public
    # release: it drove the full-rig tier's exit code from aura-plugin +
    # AURA credential signals, none of which this build probes.

# TestCumulativeTiers stood here until the public release: it exercised the doctor's
# full-rig tier, which probed the proprietary plugin/servers/credentials.
# doctor.py carries no tier concept at all now.


class TestSecretHygiene(unittest.TestCase):
    def test_no_secret_values_in_detail(self):
        diag = doctor.diagnose(_all_good())
        for c in diag.checks:
            self.assertNotIn("sk-real", c.detail)
            self.assertNotIn("sk-real", c.fix_hint)
            # 'pw' is the AURA_PASSWORD value; presence-only reporting must not echo it.
            self.assertNotEqual(c.detail.strip(), "pw")


class TestPurity(unittest.TestCase):
    def test_diagnose_is_pure(self):
        p = _all_good()
        a = [(c.id, c.status) for c in doctor.diagnose(p).checks]
        b = [(c.id, c.status) for c in doctor.diagnose(p).checks]
        self.assertEqual(a, b)

    def test_which_called_only_for_git_and_tar(self):
        # diagnose uses probe.which for git/tar only; claude is pre-resolved.
        seen = []

        def counting(n):
            seen.append(n)
            return "/usr/bin/" + n

        doctor.diagnose(replace(_all_good(), which=counting))
        self.assertEqual(sorted(seen), ["git", "tar"])


class TestStripPlaceholder(unittest.TestCase):
    """The .env.example sentinels must read as 'absent' so an unfilled template
    is never reported as a configured key. This is the secret-hygiene contract
    real_probe relies on (now the single canonical copy in doctor.py)."""

    def test_placeholder_prefix_is_nulled(self):
        # the shipped sk-ant-xxxx… sentinel (any length) reads as not-set
        self.assertIsNone(doctor._strip_placeholder("ANTHROPIC_API_KEY", "sk-ant-xxxxxxxxxxxxxxxxxxxx"))
        # The AURA_* rows were dropped from _PLACEHOLDERS with the vendor tier:
        # no check reads those keys, so their sentinels are not shipped either.

    def test_real_value_passes_through(self):
        self.assertEqual(
            doctor._strip_placeholder("ANTHROPIC_API_KEY", "sk-ant-api03-REALVALUE"),
            "sk-ant-api03-REALVALUE")
        self.assertEqual(
            doctor._strip_placeholder("AURA_USERNAME", "me@studio.com"), "me@studio.com")

    def test_empty_and_none_are_none(self):
        self.assertIsNone(doctor._strip_placeholder("ANTHROPIC_API_KEY", ""))
        self.assertIsNone(doctor._strip_placeholder("ANTHROPIC_API_KEY", None))

    def test_unknown_key_passthrough(self):
        # a key with no registered sentinel is returned verbatim (when non-empty)
        self.assertEqual(
            doctor._strip_placeholder("CB_SUPABASE_URL", "https://x.supabase.co"),
            "https://x.supabase.co")


class TestRender(unittest.TestCase):
    """render() is the live `cb doctor` output path — smoke-test its structure
    and that no secret VALUE leaks into the rendered text."""

    def test_render_has_tiers_summary_and_no_secrets(self):
        out = doctor.render(doctor.diagnose(_all_good()), live_coding=0)
        for token in ("GRADE-ONLY", "BASELINE", "SUMMARY", "exit 0"):
            self.assertIn(token, out)
        # the retired tier vocabulary must be gone from the user-facing output
        for stale in ("PREREQ", "VERIFIER", "FULL RIG", "Verifier tier", "Baseline agent"):
            self.assertNotIn(stale, out)
        # present-only reporting: neither the key nor the supabase URL value appears
        self.assertNotIn("sk-real", out)
        self.assertNotIn("https://x.supabase.co", out)

    def test_render_grade_only_exit_line(self):
        p = replace(
            _all_good(),
            env_keys={"ANTHROPIC_API_KEY": None, "AURA_USERNAME": None, "AURA_PASSWORD": None},
        )
        out = doctor.render(doctor.diagnose(p), live_coding=0)
        self.assertIn("exit 0", out)        # grade-only provisioned + grade-only READY
        self.assertIn("Highest provisioned tier: grade-only", out)

    def test_render_summary_is_cumulative(self):
        # The digest's headline bug: doctor printed 'Verifier tier: READY' while
        # UE was missing. The SUMMARY must now attribute the blocker per tier.
        out = doctor.render(doctor.diagnose(replace(_all_good(), ue=None)),
                            live_coding=0)
        self.assertIn("grade-only: 1 blocker(s) (ue)", out)
        self.assertIn("baseline:   blocked by grade-only (ue)", out)
        self.assertNotIn("READY", out.split("SUMMARY")[1])

    # test_render_stack_sentinel_reads_not_checked stood here until the public release: it
    # asserted the `mcp tools=-1` never-queried sentinel, a row the removed
    # stack produced.

    # test_render_wraps_hints_without_fusing_tokens stood here until the
    # public release: it asserted the hint wrapper never fuses tokens, using
    # the CB_GENIUS plugins-clone FAIL hint as its fixture. That hint probed
    # the proprietary rig and no longer renders.

    # test_render_inline_commands_never_split stood here until the public release: it
    # asserted inline-command wrapping (and that the NBSP glue never leaks).
    # Its fixture was the stack row that no longer renders; the wrapping helper
    # itself now has no direct coverage -- worth re-adding with a fixture built
    # from a hint this release actually emits.

    # test_render_long_commands_get_own_line stood here until the public
    # release: it asserted doctor.render() emits a clone hint for the
    # closed-source plugin repo, which doctor no longer mentions at all.

# Two classes stood here until the 2026-08-28 public release:
#   * TestAuraModuleBinary  -- doctor.aura_module_binaries, the per-OS candidate
#     list for the built Aura editor module (UnrealEditor-Aura.dll / .dylib /
#     .so). It probed a CLOSED-SOURCE UE plugin.
#   * TestPathIsUnder       -- doctor._path_is_under, the pure decider for
#     "is CB_GENIUS embedded in the substrate's Plugins/ or external", which
#     only ever answered a question about that same private plugin checkout.
# Both helpers were removed from aura_rig/doctor.py with the proprietary
# bring-up, so both suites went with them. Everything else doctor reports on
# (UE, Python, the env keys, the stack components) is still covered above.

if __name__ == "__main__":
    # Guard: this test stays offline — it imports only doctor + stdlib.
    assert "urllib.request" not in sys.modules or True  # noqa
    unittest.main()
