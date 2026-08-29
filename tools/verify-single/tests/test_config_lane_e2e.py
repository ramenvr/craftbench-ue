"""End-to-end proof of the semantic config lane's run_task wiring (2026-07-29).

Drives the REAL ``run_task.main()`` with no UE install, using the same no-UE
shape as ``test_verdict_taxonomy.TestL2IntrospectErrorEndToEnd``: the spec
declares only L2I with a nonexistent grader, so an ACCEPTED submission dies at
the missing-grader branch (exit 7) before any editor could launch. That makes
the exit code itself the discriminator for what the sandbox decided:

  * disallowed config change  -> exit 4  (SANDBOX-REJECT; never reached layers)
  * allowed config change     -> exit 7  (passed the sandbox, died at grader)
  * malformed config_allow    -> exit 2  (SPEC error; never graded)

Pinning by exit code keeps the taxonomy honest: a config violation must ride
the sandbox-reject class (non-graded), not leak into a graded FAIL.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402

_RULE = "Config/DefaultEngine.ini :: /Script/Engine.CollisionProfile :: +Profiles"

_MANIFEST = {
    "substrate": "FakeSub",
    "game_module": "FakeSub",
    "writable": ["Source/FakeSub/"],
    "config_writable": ["Config/DefaultEngine.ini"],
    "deny": ["Source/FakeSubTests/"],
}

_BASELINE_INI = (
    "[/Script/Engine.CollisionProfile]\n"
    "+Profiles=(Name=\"Existing\",CollisionEnabled=QueryOnly)\n"
    "\n"
    "[/Script/Engine.RendererSettings]\n"
    "r.SomeSetting=1\n"
)

_EXISTING_PROFILE = "+Profiles=(Name=\"Existing\",CollisionEnabled=QueryOnly)\n"


def _with_lines_in_collision_section(*new_lines: str) -> str:
    """The baseline with lines INSERTED INSIDE [CollisionProfile].

    Appending at end-of-file would physically place them in the LAST section
    ([RendererSettings]) - which is exactly what the parser (correctly)
    reported when this fixture first did that.
    """
    return _BASELINE_INI.replace(
        _EXISTING_PROFILE, _EXISTING_PROFILE + "".join(new_lines)
    )


def _spec(config_allow_entry: str | None) -> str:
    allow = (
        f'config_allow: ["{config_allow_entry}"]\n' if config_allow_entry else ""
    )
    return (
        "---\n"
        "id: config-lane-e2e-probe\n"
        "substrate: FakeSub\n"
        "layers: [L2I]\n"
        "introspect: [definitely_not_a_real_grader__config_e2e.py]\n"
        + allow +
        "---\n"
        "\n"
        "## Prompt given to the agent\n"
        "\n"
        "> Do the thing.\n"
    )


class TestConfigLaneEndToEnd(unittest.TestCase):
    def _fixture(self, tmp: Path, spec_text: str, submitted_ini: str,
                 submitted_bytes: bytes | None = None):
        substrate = tmp / "UE-projects" / "FakeSub"
        (substrate / "Source" / "FakeSub").mkdir(parents=True)
        (substrate / "Config").mkdir()
        (substrate / "Config" / "DefaultEngine.ini").write_text(
            _BASELINE_INI, encoding="utf-8"
        )
        (substrate / "FakeSub.uproject").write_text(
            json.dumps({"FileVersion": 3, "EngineAssociation": "5.8",
                        "Plugins": []}),
            encoding="utf-8",
        )
        (substrate / "AGENT_WRITABLE.json").write_text(
            json.dumps(_MANIFEST), encoding="utf-8"
        )
        spec_path = tmp / "task.md"
        spec_path.write_text(spec_text, encoding="utf-8")
        submission = tmp / "sub"
        (submission / "Config").mkdir(parents=True)
        target = submission / "Config" / "DefaultEngine.ini"
        if submitted_bytes is not None:
            target.write_bytes(submitted_bytes)
        else:
            target.write_text(submitted_ini, encoding="utf-8")
        return spec_path, substrate, submission

    def _drive(self, spec_text: str, submitted_ini: str,
               submitted_bytes: bytes | None = None):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            spec_path, substrate, submission = self._fixture(
                tmp, spec_text, submitted_ini, submitted_bytes
            )
            report_json = tmp / "report.json"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(submission),
                    "--ue-root", str(tmp / "no-ue"),
                    "--substrate-overlay", str(substrate),
                    "--substrate-from-live",
                    "--report-json", str(report_json),
                ])
            report = (
                json.loads(report_json.read_text(encoding="utf-8"))
                if report_json.exists() else None
            )
            return rc, out.getvalue(), err.getvalue(), report

    def test_disallowed_config_change_is_sandbox_reject(self) -> None:
        # The spec allows +Profiles; the submission ALSO adds a channel
        # response -> that second change is outside the allowlist.
        rc, out, _err, _report = self._drive(
            _spec(_RULE),
            _with_lines_in_collision_section(
                "+Profiles=(Name=\"Projectile1\",CollisionEnabled=QueryAndPhysics)\n",
                "+DefaultChannelResponses=(Channel=ECC_GameTraceChannel1)\n",
            ),
        )
        self.assertEqual(rc, run_task.EXIT_SANDBOX_REJECT)
        self.assertIn("config change not allowed", out)
        self.assertIn("+DefaultChannelResponses", out)
        self.assertIn("/Script/Engine.CollisionProfile", out)

    def test_allowed_config_change_passes_the_sandbox(self) -> None:
        # Only the allowlisted key changes -> the sandbox accepts and the run
        # proceeds to die at the (deliberately missing) grader: exit 7 proves
        # acceptance without needing an editor.
        rc, _out, err, _report = self._drive(
            _spec(_RULE),
            _with_lines_in_collision_section(
                "+Profiles=(Name=\"Projectile1\",CollisionEnabled=QueryAndPhysics)\n",
            ),
        )
        self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
        self.assertIn("harness could not grade this run", err)

    def test_config_change_with_no_allowlist_rejects(self) -> None:
        rc, out, _err, _report = self._drive(
            _spec(None),
            _with_lines_in_collision_section(
                "+Profiles=(Name=\"Projectile1\",CollisionEnabled=QueryAndPhysics)\n",
            ),
        )
        self.assertEqual(rc, run_task.EXIT_SANDBOX_REJECT)
        self.assertIn("config change not allowed", out)

    def test_malformed_config_allow_is_a_spec_error(self) -> None:
        rc, _out, err, _report = self._drive(
            _spec("just-one-field-no-separators"),
            _BASELINE_INI,
        )
        self.assertEqual(rc, run_task.EXIT_USAGE)
        self.assertIn("config_allow", err)

    def test_untouched_config_file_is_accepted(self) -> None:
        # Submitting the baseline byte-for-byte changes nothing -> no
        # violations even with an empty allowlist; proceeds to exit 7.
        rc, _out, err, _report = self._drive(_spec(None), _BASELINE_INI)
        self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
        self.assertIn("harness could not grade this run", err)

    def test_non_utf8_but_unchanged_config_is_accepted(self) -> None:
        """A UTF-16 capture of an UNCHANGED config must not exit 4.

        RED before 2026-08-19: config_lane read the submitted file with
        ``encoding="utf-8"`` and turned the UnicodeDecodeError into a
        violation, so this returned EXIT_SANDBOX_REJECT -- a non-graded cell
        for a submission whose config is character-for-character the baseline.
        Reachable because the live-project collector now captures every
        manifest ``config_writable`` file on every run, and that file is
        agent-writable.
        """
        rc, out, err, _report = self._drive(
            _spec(None), "", submitted_bytes=_BASELINE_INI.encode("utf-16")
        )
        self.assertNotEqual(rc, run_task.EXIT_SANDBOX_REJECT)
        self.assertNotIn("config change not allowed", out)
        self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
        self.assertIn("harness could not grade this run", err)

    def test_undecodable_config_rejects_but_says_UNKNOWN(self) -> None:
        """Fail closed on a file we cannot read -- and never call it a change.

        The rejection is the old behaviour; the WORDING is the fix. An
        operator triaging an exit-4 must be able to tell "the agent edited
        something it may not" from "we could not look", and before this the
        two were the same class of line.
        """
        rc, out, _err, _report = self._drive(
            _spec(None), "", submitted_bytes=bytes([0x5B, 0x53, 0x5D, 0xC3, 0x28])
        )
        self.assertEqual(rc, run_task.EXIT_SANDBOX_REJECT)
        self.assertIn("config UNKNOWN", out)
        self.assertIn("UNDETERMINED", out)
        self.assertNotIn("config change not allowed", out)


if __name__ == "__main__":
    unittest.main()
