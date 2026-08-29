"""Unit tests for provenance.genius_provenance in the COPY era.

ensure_scratch_plugins stages Plugins/Aura as a real COPY (not a junction), so
"which Aura ran" is anchored by the .cb-plugin-provenance.json marker written
at copy time. These tests drive the split semantics fully offline via the
injected environ + runner seams (no git, no real rig).

Run from tools/run-agent:  py -3.12 -m unittest tests.test_provenance_split -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import provenance  # noqa: E402

GENIUS_SHA = "cafe1234deadbeef"


def _runner_for(genius: Path, sha: str = GENIUS_SHA):
    """Fake subprocess.run: yields the rig sha ONLY for `git -C <genius> …`;
    every other repo (e.g. the scratch's non-repo parent) resolves to none."""
    class _R:
        def __init__(self, out: str) -> None:
            self.stdout = out
            self.returncode = 0
    def runner(cmd, capture_output=True, text=True, timeout=15):
        if "rev-parse" in cmd and str(genius) in cmd:
            return _R(sha + "\n")
        return _R("")
    return runner


def _mk_project(root: Path, marker: dict | None) -> Path:
    aura = root / "proj" / "Plugins" / "Aura"
    aura.mkdir(parents=True)
    (aura / "Aura.uplugin").write_text(
        json.dumps({"VersionName": "0.15.2"}), encoding="utf-8")
    if marker is not None:
        (aura / ".cb-plugin-provenance.json").write_text(
            json.dumps(marker), encoding="utf-8")
    return root / "proj"


class TestGeniusProvenanceCopyEra(unittest.TestCase):
    def test_anchored_fresh_copy_is_not_split(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            genius = root / "rig"
            genius.mkdir()
            proj = _mk_project(root, {"src": str(genius / "Aura"),
                                      "genius_sha": GENIUS_SHA,
                                      "copied_at": "2026-07-22T10:00:00"})
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(genius)},
                runner=_runner_for(genius))
        self.assertIs(out["split"], False)
        self.assertEqual(out["plugin_copy_sha"], GENIUS_SHA)
        # marker backfills the repo sha when the copy's parent isn't a repo
        self.assertEqual(out["plugin_repo_sha"], GENIUS_SHA)
        self.assertEqual(out["aura_plugin_version"], "0.15.2")
        self.assertNotIn("plugin_copy_unanchored", out)

    def test_anchored_stale_copy_is_split(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            genius = root / "rig"
            genius.mkdir()
            proj = _mk_project(root, {"src": str(genius / "Aura"),
                                      "genius_sha": "OLD-sha",
                                      "copied_at": "2026-07-10T10:00:00"})
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(genius)},
                runner=_runner_for(genius))
        self.assertIs(out["split"], True)

    def test_copy_from_foreign_rig_is_split(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            genius = root / "rig"
            genius.mkdir()
            proj = _mk_project(root, {"src": str(root / "OTHER-rig" / "Aura"),
                                      "genius_sha": GENIUS_SHA,
                                      "copied_at": "t"})
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(genius)},
                runner=_runner_for(genius))
        self.assertIs(out["split"], True)

    def test_unanchored_copy_flags_unknown_explicitly(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            genius = root / "rig"
            genius.mkdir()
            proj = _mk_project(root, marker=None)
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(genius)},
                runner=_runner_for(genius))
        self.assertIsNone(out["split"])
        self.assertTrue(out.get("plugin_copy_unanchored"))
        # the physical facts are still recorded (were null before 2026-07-22)
        self.assertEqual(out["aura_plugin_version"], "0.15.2")
        self.assertIsNotNone(out["plugin_link_target"])


if __name__ == "__main__":
    unittest.main()
