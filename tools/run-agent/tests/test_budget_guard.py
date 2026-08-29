"""A spend ceiling that measures the wrong number, or nothing, is not a ceiling.

WHY THIS EXISTS. The $50 block ceiling (owner, 2026-08-25) has to be enforced by
something, and the two obvious implementations are both wrong in ways that only
show up after the money is gone:

  * **Enforcing on the RECORDED cost.** The cost rule: recorded
    `cost_usd` is untrusted for openrouter-served runs — the Claude Code CLI
    prices every call at Anthropic first-party rates and cannot see the gateway.
    Measured on the 2026-08-22 sweep it overstated by 2.6x overall and **12.7x on
    gemini**. A ceiling on that number stops a gemini block at ~$4 of real spend
    while believing it spent $50, and the error runs the other way on models the
    sheet prices high.
  * **Ignoring an UNPRICED id.** `derived_cost` returns None when the audited
    sheet has no row — `anthropic/claude-opus-5` has none today, and opus is the
    pre-committed final phase. Summing None as 0 gives a ceiling that can never
    fire, on the most expensive model in the plan.

Both directions are pinned below, plus the third property that makes the guard
safe to leave running: it stops the sweep at a CELL BOUNDARY via the existing
stop flag rather than killing anything, because killing mid-cell skips that
cell's post-cell leak audit — which is how a contaminated PASS got banked on
2026-08-23.

Stdlib only. No UE, no editor, no network, no tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import budget_guard as bg  # noqa: E402
from sweep_report import PRICE_SHEET  # noqa: E402

#: The six ids the 2026-08-25 cpp block runs, as `cb` spells them.
BLOCK_SLUGS = (
    "unreal-mcp:claude-sonnet-5",
    "aura-mcp:deepseek/deepseek-v4-pro-0813",
    "unreal-mcp:x-ai/grok-4.6",
    "aura-mcp:google/gemini-3.7-flash",
    "unreal-mcp:openai/gpt-5.6-luna",
    "aura-mcp:openai/gpt-5.6-sol",
)


def _cell(root: Path, name: str, model: str, *, tin=100_000, tout=20_000,
          crd=80_000, ccr=5_000, recorded=9.99):
    d = root / "lane" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text(json.dumps({
        "model": model, "overall": "PASS",
        "agent": {"tokens_in": tin, "tokens_out": tout,
                  "cache_read_tokens": crd, "cache_creation_tokens": ccr,
                  "cost_usd": recorded},
    }), encoding="utf-8")
    return d


class TestEveryModelInTheBlockIsPriced(unittest.TestCase):
    """The check that must run BEFORE the block, not after it."""

    def test_all_six_resolve_to_a_sheet_row(self):
        unpriced = [s for s in BLOCK_SLUGS
                    if s.split(":", 1)[-1] not in PRICE_SHEET]
        self.assertEqual([], unpriced,
                         "these would be counted at $0 and the ceiling could "
                         "never fire on them")

    def test_opus_is_still_unpriced_so_the_final_phase_needs_a_row(self):
        # Pinned as a REMINDER, not as an aspiration: opus is the pre-committed
        # phase after the six, and inventing a price here is what §9 forbids
        # ("costs derive from tokens x a dated sheet, never from a remembered
        # price"). When an audited row lands, this test flips and should be
        # deleted in the same change.
        self.assertNotIn("anthropic/claude-opus-5", PRICE_SHEET,
                         "opus is priced now — delete this test and drop the "
                         "opus caveat from the readiness page")


class TestTheCeilingMeasuresTheDerivedNumber(unittest.TestCase):
    def test_a_wildly_wrong_recorded_cost_does_not_move_the_ceiling(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # One gemini cell whose RECORDED cost is 12.7x the truth, the
            # measured 2026-08-22 ratio.
            _cell(root, "c1", "aura-mcp:google/gemini-3.7-flash", recorded=999.0)
            total, unpriced, cells, recorded = bg.tally(root, set())
        self.assertEqual(1, cells)
        self.assertEqual(0, unpriced)
        self.assertAlmostEqual(999.0, recorded, places=2)
        self.assertLess(total, 1.0,
                        "the ceiling is reading the untrusted recorded figure")

    def test_the_excluded_model_is_left_out_entirely(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _cell(root, "c1", "unreal-mcp:claude-sonnet-5")
            _cell(root, "c2", "unreal-mcp:x-ai/grok-4.6")
            total_all, _u, cells_all, _r = bg.tally(root, set())
            total_ex, _u2, cells_ex, _r2 = bg.tally(root, {"claude-sonnet-5"})
        self.assertEqual((2, 1), (cells_all, cells_ex))
        self.assertLess(total_ex, total_all,
                        "excluding sonnet did not reduce the counted spend")

    def test_an_unreadable_record_is_skipped_not_counted_as_free(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad = root / "lane" / "broken"
            bad.mkdir(parents=True)
            (bad / "result.json").write_text("{ not json", encoding="utf-8")
            total, unpriced, cells, _r = bg.tally(root, set())
        self.assertEqual((0.0, 0, 0), (total, unpriced, cells))


class TestBlindSpendStopsTheSweep(unittest.TestCase):
    """The loud direction: spending on something the ceiling cannot see."""

    def _run(self, root, flag, argv_extra=()):
        return bg.main(["--ceiling", "50", "--runs-root", str(root),
                        "--stop-flag", str(flag), "--once", *argv_extra])

    def test_all_unpriced_drops_the_flag_and_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "c1", "aura-mcp:anthropic/claude-opus-5")
            rc = self._run(root, flag)
            # ASSERT INSIDE the `with`: TemporaryDirectory deletes the tree on
            # exit, so a flag.exists() outside it is always False and the test
            # fails for a reason that has nothing to do with the guard.
            self.assertEqual(2, rc)
            self.assertTrue(flag.exists(),
                            "the sweep was allowed to spend blind")

    def test_a_small_unpriced_share_keeps_measuring(self):
        """One stray unpriced cell must not halt an otherwise measured run.

        This is what the rule "one priced cell is enough" was reaching for, and
        within this range it was right: a ceiling that stops because a single
        odd model id showed up is a ceiling nobody leaves running.
        """
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "odd", "aura-mcp:anthropic/claude-opus-5",
                  tin=1_000, tout=200, crd=800, ccr=50)
            for i in range(12):
                _cell(root, f"p{i}", "unreal-mcp:x-ai/grok-4.6")
            rc = self._run(root, flag)
            self.assertEqual(0, rc)
            self.assertFalse(flag.exists())

    def test_an_unpriced_share_that_carries_the_spend_refuses(self):
        """...and OUTSIDE that range the same rule was unsafe.

        The rule this replaces was "all cells unpriced -> refuse, otherwise
        carry on", written as the simple complement rather than as a weighed
        decision. It leaves the dangerous case open: when the UNPRICED model is
        the EXPENSIVE one, the ceiling is blind to the largest cost in the grid
        and says so in a single soft line it will not act on.

        That case is scheduled, not hypothetical -- `anthropic/claude-opus-5`
        has no row (the 2026-08-19 audit skipped it on purpose, "opus-5 is
        newer but a different tier") and the opus phase runs after this block.
        A grid mixing opus with the priced six would have spent past $50 with
        the guard reporting a comfortable number the whole way.

        Measured in TOKENS, not cells: blindness is proportional to volume, so
        the rule has to weigh a 2M-token cell above a hundred 2k-token strays.
        """
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "big", "aura-mcp:anthropic/claude-opus-5",
                  tin=2_000_000, tout=400_000, crd=1_600_000, ccr=100_000)
            _cell(root, "small", "unreal-mcp:x-ai/grok-4.6")
            rc = self._run(root, flag)
            self.assertEqual(2, rc)
            self.assertTrue(flag.exists(),
                            "the ceiling was blind to the largest cost in the "
                            "grid and let it spend")

    def test_the_refusal_names_the_model_that_needs_a_row(self):
        # The whole cost of this class of stop is the diagnosis. A refusal that
        # does not name the id sends the reader to grep the price sheet.
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "big", "aura-mcp:anthropic/claude-opus-5",
                  tin=2_000_000, tout=400_000, crd=1_600_000, ccr=100_000)
            _cell(root, "small", "unreal-mcp:x-ai/grok-4.6")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self._run(root, flag)
            out = buf.getvalue()
        self.assertIn("anthropic/claude-opus-5", out)
        self.assertIn("AUDITED", out)

    def test_an_empty_runs_root_is_not_blind_spend(self):
        # Nothing has run yet. Refusing here would make the guard unstartable.
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            self.assertEqual(0, self._run(root, flag))
            self.assertFalse(flag.exists())

    def test_the_escape_hatch_works(self):
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "c1", "aura-mcp:anthropic/claude-opus-5")
            rc = self._run(root, flag, ("--no-refuse-blind",))
            self.assertEqual(0, rc)
            self.assertFalse(flag.exists())


class TestTheCeilingActuallyFires(unittest.TestCase):
    def test_it_drops_the_flag_once_the_derived_total_crosses(self):
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            # grok at ~$0.19/cell on this shape; 40 cells clears a $2 ceiling.
            for i in range(40):
                _cell(root, f"c{i}", "unreal-mcp:x-ai/grok-4.6")
            rc = bg.main(["--ceiling", "2", "--runs-root", str(root),
                          "--stop-flag", str(flag), "--once"])
            self.assertEqual(0, rc)
            self.assertTrue(flag.exists(), "the ceiling never fired")
            self.assertIn("ceiling", flag.read_text(encoding="utf-8"))

    def test_it_does_not_fire_below_the_ceiling(self):
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            _cell(root, "c1", "unreal-mcp:x-ai/grok-4.6")
            bg.main(["--ceiling", "50", "--runs-root", str(root),
                     "--stop-flag", str(flag), "--once"])
            self.assertFalse(flag.exists(), "one cell tripped a $50 ceiling")

    def test_it_never_writes_to_a_run_record(self):
        with tempfile.TemporaryDirectory() as d:
            root, flag = Path(d), Path(d) / "stop"
            cell = _cell(root, "c1", "unreal-mcp:x-ai/grok-4.6")
            rj = cell / "result.json"
            before = rj.read_bytes()
            bg.main(["--ceiling", "0.0001", "--runs-root", str(root),
                     "--stop-flag", str(flag), "--once"])
            self.assertEqual(before, rj.read_bytes(),
                             "the guard edited a graded record")


if __name__ == "__main__":
    unittest.main()
