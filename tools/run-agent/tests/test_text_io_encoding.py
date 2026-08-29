"""Production text reads must name their encoding, or the harness is locale-bound.

THE MEASUREMENT, 2026-08-24. Running the run-agent suite on this box with
``PYTHONUTF8=0`` produced 23 errors, all the same shape:

    workspace.py:254  json.loads(agent_writable_json.read_text())
    UnicodeDecodeError: 'gbk' codec can't decode byte 0x94 in position 1146

Nothing was wrong with the file. ``Path.read_text()`` with no encoding decodes
with the LOCALE, this box's locale is GBK, and the manifest holds a curly quote.
The whole harness only works here because ``PYTHONUTF8=1`` happens to be set in
the environment -- unset it, or run from a service/scheduler that does not
inherit it, and workspace construction dies before the agent starts. CI and
the bench host never saw it because cp1252 decodes those bytes without
complaint, which is precisely why a latent locale dependency survives for
months.

SCOPE, stated rather than implied. This gate covers ``Path.read_text()`` calls
with no ``encoding=``, which is unambiguous: the method takes no positional
encoding. Two neighbouring shapes are measured and NOT covered yet --
15 ``write_text`` calls and 19 candidate ``open()`` calls -- because
distinguishing ``builtins.open(path, mode)`` from ``Path.open(mode)`` needs more
than the AST node, and a gate that mis-classifies would be worse than one with a
named boundary. Widen it when that is done; do not read the silence as coverage.

Stdlib only, no UE, no editor, no tokens.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Trees whose .py files ship as production code. Test trees are excluded on
#: purpose: a test that reads a fixture it just wrote in a known encoding is not
#: the hazard, and sweeping them in would bury the signal.
SCAN_ROOTS = ("tools",)


def _encodingless_read_text(tree: ast.AST) -> list:
    """Line numbers of ``.read_text()`` calls that name no encoding."""
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "read_text"
                and not any(k.arg == "encoding" for k in node.keywords)):
            out.append(node.lineno)
    return out


def _production_files():
    for root in SCAN_ROOTS:
        for p in sorted((REPO_ROOT / root).rglob("*.py")):
            parts = p.relative_to(REPO_ROOT).as_posix().split("/")
            if "tests" in parts or "__pycache__" in parts:
                continue
            yield p


class TestEveryProductionReadNamesItsEncoding(unittest.TestCase):
    def test_no_production_read_text_relies_on_the_locale(self):
        offenders = []
        for p in _production_files():
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            offenders += [f"{p.relative_to(REPO_ROOT).as_posix()}:{n}"
                          for n in _encodingless_read_text(tree)]
        self.assertEqual([], offenders,
                         "read_text() without encoding= decodes with the "
                         "machine locale; these will behave differently on a "
                         "GBK box, a cp1252 box and in UTF-8 mode")

    def test_the_detector_has_teeth(self):
        # Without this, the assertion above would also pass on a scan that
        # silently matched nothing -- a bad import path, a renamed tree, an AST
        # walk that missed the node shape.
        bad = ast.parse("from pathlib import Path" + chr(10)
                        + "x = Path('a').read_text()" + chr(10))
        good = ast.parse("from pathlib import Path" + chr(10)
                         + "x = Path('a').read_text(encoding='utf-8')" + chr(10))
        self.assertEqual([2], _encodingless_read_text(bad))
        self.assertEqual([], _encodingless_read_text(good))

    def test_the_scan_actually_reaches_the_harness(self):
        names = {p.name for p in _production_files()}
        for expected in ("workspace.py", "run.py", "leak_audit.py"):
            self.assertIn(expected, names,
                          "the scan is not reaching run-agent, so a green "
                          "result would mean nothing")


if __name__ == "__main__":
    unittest.main()
