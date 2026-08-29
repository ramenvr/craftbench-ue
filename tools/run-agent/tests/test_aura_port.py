"""Unit tests for aura_port — the stale-port self-heal for authentic aura-mcp.

The HTTP probe is injected (no live editor needed), so these run offline.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_port import (  # noqa: E402
    candidate_ports,
    discover_live_aura_port,
    ensure_aura_client_port,
    probe_aura_port,
    read_port_file,
)


class TestReadPortFile(unittest.TestCase):
    def test_reads_integer(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.txt"
            f.write_text("41200\n")
            self.assertEqual(read_port_file(f), 41200)

    def test_missing_returns_none(self):
        self.assertIsNone(read_port_file(Path("/no/such/port.txt")))

    def test_garbage_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.txt"
            f.write_text("not-a-port")
            self.assertIsNone(read_port_file(f))


class TestProbeAuraPort(unittest.TestCase):
    def test_200_with_token_is_live(self):
        opener = lambda url, t: (200, "eyJhbGciOiJIUzI1NiJ9.token")  # noqa: E731
        self.assertTrue(probe_aura_port(41200, opener=opener))

    def test_200_with_error_body_is_not_live(self):
        # Editor up but signed out → error payload → not usable.
        opener = lambda url, t: (200, '{"error":"No valid session token found."}')  # noqa: E731
        self.assertFalse(probe_aura_port(41200, opener=opener))

    def test_empty_body_is_not_live(self):
        opener = lambda url, t: (200, "")  # noqa: E731
        self.assertFalse(probe_aura_port(41200, opener=opener))

    def test_connection_error_is_not_live(self):
        def opener(url, t):
            raise ConnectionRefusedError("nothing listening")
        self.assertFalse(probe_aura_port(3002, opener=opener))


class TestCandidatePorts(unittest.TestCase):
    def test_current_first_then_default(self):
        self.assertEqual(candidate_ports(3002), [3002, 41200])

    def test_dedups_when_current_is_default(self):
        self.assertEqual(candidate_ports(41200), [41200])

    def test_none_current_is_just_default(self):
        self.assertEqual(candidate_ports(None), [41200])


class TestDiscoverLivePort(unittest.TestCase):
    def test_picks_first_live_candidate(self):
        # 3002 dead, 41200 live → returns 41200.
        live = {41200}
        port = discover_live_aura_port([3002, 41200], probe=lambda p: p in live)
        self.assertEqual(port, 41200)

    def test_none_when_nothing_live(self):
        self.assertIsNone(discover_live_aura_port([3002, 41200], probe=lambda p: False))


class TestEnsureAuraClientPort(unittest.TestCase):
    def _make_project(self, d: str, port_text: str | None):
        project = Path(d)
        aura = project / "Plugins" / "Aura"
        aura.mkdir(parents=True)
        port_file = aura / "aura_client_port.txt"
        if port_text is not None:
            port_file.write_text(port_text)
        return project, port_file

    def test_stale_port_is_rewritten_to_live(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project, port_file = self._make_project(d, "3002")
            logs = []
            live = ensure_aura_client_port(
                project, log=logs.append, probe=lambda p: p == 41200
            )
            self.assertEqual(live, 41200)
            self.assertEqual(port_file.read_text(encoding="utf-8"), "41200")
            self.assertTrue(any("normalized" in m for m in logs))

    def test_correct_port_is_left_untouched(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project, port_file = self._make_project(d, "41200")
            mtime_before = port_file.stat().st_mtime_ns
            logs = []
            live = ensure_aura_client_port(
                project, log=logs.append, probe=lambda p: p == 41200
            )
            self.assertEqual(live, 41200)
            # No rewrite when already correct (idempotent, no normalize log).
            self.assertEqual(port_file.stat().st_mtime_ns, mtime_before)
            self.assertFalse(any("normalized" in m for m in logs))

    def test_no_live_editor_warns_and_leaves_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project, port_file = self._make_project(d, "3002")
            logs = []
            live = ensure_aura_client_port(
                project, log=logs.append, probe=lambda p: False
            )
            self.assertIsNone(live)
            self.assertEqual(port_file.read_text(encoding="utf-8"), "3002")  # unchanged
            self.assertTrue(any("WARNING" in m for m in logs))

    def test_missing_port_file_is_created_when_editor_live(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project, port_file = self._make_project(d, None)  # dir exists, no file
            live = ensure_aura_client_port(
                project, log=lambda m: None, probe=lambda p: p == 41200
            )
            self.assertEqual(live, 41200)
            self.assertEqual(port_file.read_text(encoding="utf-8"), "41200")

    def test_non_aura_project_is_noop(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)  # no Plugins/Aura
            live = ensure_aura_client_port(
                project, log=lambda m: None, probe=lambda p: True
            )
            self.assertIsNone(live)


if __name__ == "__main__":
    unittest.main()
