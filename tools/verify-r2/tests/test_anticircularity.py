"""Executable anti-circularity invariant (I2): no module under tools/verify-r2/
may import Aura, the agent-under-test adapter, or an Aura MCP tool. The evidence
must be re-derived by CraftBench's own stock-UE primitives — never by calling
Aura to grade Aura.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

# Import statements referencing an aura module, the aura harness adapters, or a
# concrete Aura MCP tool call. Matched against the CODE portion of each line
# (comments stripped) so prose mentions of "Aura" in docstrings/comments pass.
_FORBIDDEN = re.compile(
    r"(^\s*(import|from)\s+[\w.]*aura|aura_agent|aura_mcp\b|"
    r"harness-adapters/aura|mcp__unreal_(editor|inspector))"
)


class TestAntiCircularity(unittest.TestCase):
    def test_no_aura_or_mcp_in_r2_source(self):
        offenders = []
        for p in sorted(_R2.rglob("*.py")):
            if "tests" in p.parts:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]  # ignore comment-only mentions
                if _FORBIDDEN.search(code):
                    offenders.append(f"{p.relative_to(_R2)}:{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "R2 must not import Aura / call Aura's MCP tools (anti-circularity):\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
