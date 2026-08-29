"""A cell that reads ANOTHER cell's finished answer is not a measurement.

MEASURED 2026-08-27. The agent runs under `--permission-mode bypassPermissions`,
which makes `--add-dir` and the deliberately "neutral cwd" HINTS rather than
boundaries: the process can read anywhere on the box, and `runs/` sits wide open
beside it. One cell walked straight in --

    line 6    Glob C:/cb/<other-worktree>       **/*Mud*
    line 99   Glob C:/cb/<other-worktree>/runs  **/BP_MudHero.uasset
    line 120  Glob .../20260826-033551-.../submission  **/*

-- and two more read peer submissions outright, one of them a cell that then
PASSED on four source files copied from a peer that had already PASSED.

No tier named it: `answer` and `foreign` scope to the TASK tree, `park` to the
fairness park, `fixture` to the verifier source. The exposure also grows
monotonically through a block -- the later a cell runs, the more finished answers
sit next to it -- so undetected it biases whichever models are scheduled late.

THE LOAD-BEARING PART IS THE LISTING/READ SPLIT. The first version of this tier
accused a legitimate FAIL that had merely run `find` and got back a 33 KB
directory listing naming 50 peers. You can only read one file at a time, so a
line naming MANY peers is an enumeration. Measured separation on the three cells
that touched peers at all: real reads are 1 stamp and 1-13 KB; the listing was 50
stamps. Both directions are tested here, because a tier that voids on listings
destroys good cells and one that ignores reads banks copied answers.

Stdlib only.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from leak_audit import peer_reach  # noqa: E402

OWN = "20260827-021532"
PEER = "20260826-115328"


def fold(s: str) -> str:
    low = s.lower().replace("\\\\", "/").replace("\\", "/")
    while "//" in low:
        low = low.replace("//", "/")
    return low


def read_of(peer: str, part: str = "/submission/") -> str:
    return fold(json.dumps({"type": "tool_result", "file": {
        "filepath": f"c:/cb/run-tree/runs/unreal-mcp/{peer}-gp-health"
                    f"{part}source/thirdperson/x.cpp",
        "content": "// Copyright CraftBench. All rights reserved.\n"}}))


def listing_of(peers) -> str:
    return fold(json.dumps({"type": "tool_result", "content": ",".join(
        f"c:/cb/run-tree/runs/unreal-mcp/{p}-t1-mud/submission/x.cpp"
        for p in peers)}))


class TestAReadOfAPeerAnswerFires(unittest.TestCase):
    def test_submission(self):
        self.assertTrue(peer_reach(read_of(PEER), OWN))

    def test_live_backup(self):
        self.assertTrue(peer_reach(read_of(PEER, "/live_backup/"), OWN))


class TestALISTINGDoesNotFire(unittest.TestCase):
    """The direction that cost a good cell before it was fixed."""

    def test_many_peers_on_one_line_is_an_enumeration(self):
        peers = [f"2026082{i%10}-{100000+i:06d}" for i in range(50)]
        self.assertFalse(peer_reach(listing_of(peers), OWN))

    def test_even_two_peers_is_not_a_read(self):
        # You can only read one file at a time. Two is already a listing.
        self.assertFalse(peer_reach(listing_of([PEER, "20260826-033551"]), OWN))


class TestItNeverAccusesACellOfItsOwnWork(unittest.TestCase):
    def test_its_own_submission_is_not_a_peer(self):
        self.assertFalse(peer_reach(read_of(OWN), OWN))

    def test_own_run_dir_among_peers_is_excluded_from_the_count(self):
        # A line naming ONLY itself must not read as "exactly one peer".
        self.assertFalse(peer_reach(listing_of([OWN]), OWN))


class TestItIgnoresWhatOtherTiersOwn(unittest.TestCase):
    def test_a_peer_path_with_no_answer_part_is_not_consumption(self):
        # verifier_out is grading OUTPUT and preview/ is stills; the fixture
        # source they derive from is the `fixture` tier's job. Voiding on these
        # is what produced the first false positive.
        for part in ("/verifier_out/", "/preview/", "/"):
            self.assertFalse(peer_reach(read_of(PEER, part), OWN), part)


class TestItDegradesSafely(unittest.TestCase):
    def test_no_own_stamp_means_no_accusation(self):
        # Without an id to scope by, every peer path would look foreign. Silence
        # is the correct failure direction for a tier that VOIDS.
        self.assertFalse(peer_reach(read_of(PEER), ""))

    def test_a_line_with_no_runs_path_is_quiet(self):
        self.assertFalse(peer_reach(fold("nothing to see here"), OWN))


class TestItIsWiredAndItVOIDS(unittest.TestCase):
    def test_audit_emits_the_peer_kind(self):
        src = (_ROOT / "leak_audit.py").read_text(encoding="utf-8")
        self.assertIn('hits.setdefault("peer", []).append(n)', src)

    def test_peer_is_in_the_consuming_set_not_merely_exposed(self):
        src = (_ROOT / "leak_audit.py").read_text(encoding="utf-8")
        self.assertIn('{"answer", "fixture", "peer"}', src)


if __name__ == "__main__":
    unittest.main()
