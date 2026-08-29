"""The pass-rate denominator has ONE definition. This test is why it stays one.

the denominator rule recorded a "known divergence, tracked separately": three
places in this repo each carried their own copy of "which verdicts count in a
pass-rate", and they did not agree. Concretely, before 2026-08-17:

    run-agent/adapters/base.GRADED_VERDICTS   = {PASS, FAIL}
    tools/compare/compare_products.py         = {PASS, FAIL} | 3 model outcomes
    tools/dashboard/collect.py                = {PASS, FAIL} | 3 model outcomes

So ONE set of runs produced TWO different pass rates depending on which
aggregator you asked, and a published comparison would have carried two tables that
contradicted each other on the same data. Nothing detected it: each copy had a
correct-looking comment, and ``collect.py``'s even said "kept in lockstep with
compare_products.py" — which was true, and was the wrong pair to be in lockstep
with.

**Why the two aggregators cannot simply import the constant.** Both are
deliberately stdlib-only and live OUTSIDE the ``run-agent`` package so they can
run against a bare checkout with nothing installed (``compare_products.py`` says
so in its own comment, as do ``verify-stability/reliability.py`` and
``verify-stability/reliability.py``). That is a real constraint, not laziness, so the
duplication has to stay — which means the only durable defence is a test that
reads all three and asserts equality. That is this file.

It parses the literals out of source rather than importing the modules, for the
same reason those modules do not import: the test must not require the two tools
to be importable, only readable.

**What is deliberately NOT in the equality set.**
CORRECTLY narrower ({PASS, FAIL}). Its question is "may this run be RENDERED
into a report", and a deny-path SANDBOX-REJECT must never be rendered even
though it is a graded model outcome that belongs in the denominator. Two
different questions wearing one name is what made this bug hard to see, so the
test pins the distinction instead of erasing it.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import base  # noqa: E402

_REPO = Path(__file__).resolve().parents[3]

#: The one true denominator. Every aggregator must agree with this.
EXPECTED = frozenset({
    "PASS", "FAIL", "FAIL_NO_EDITS", "SANDBOX-REJECT", "NO_DELIVERABLE",
})


def _literal_frozenset(path: Path, name: str) -> frozenset:
    """Evaluate ``<name> = frozenset({...}) [| ...]`` out of a source file.

    Uses ``ast.literal_eval`` on the set literals and unions them, so the
    assignment may be spelled as one literal or as ``base | extras`` — but a
    non-literal (a call, a comprehension, an import) raises rather than being
    silently skipped. A check that quietly passes when it cannot find its target
    is worse than no check: it reports agreement it never verified.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if name not in targets:
            continue
        return _eval_set_expr(node.value, path, name)
    raise AssertionError(
        f"{path.relative_to(_REPO)} no longer assigns {name} — the denominator "
        f"moved or was renamed. Update this test in the SAME change, do not "
        f"delete it: an unchecked copy is how the original divergence survived."
    )


def _eval_set_expr(node: ast.expr, path: Path, name: str) -> frozenset:
    """``frozenset({...})``, a bare ``{...}``, or a ``|`` chain of those."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return (_eval_set_expr(node.left, path, name)
                | _eval_set_expr(node.right, path, name))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "frozenset" and len(node.args) == 1):
        return frozenset(ast.literal_eval(node.args[0]))
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return frozenset(ast.literal_eval(node))
    if isinstance(node, ast.Name):
        # A reference to a sibling module-level set (e.g. _MODEL_OUTCOME_GRADED).
        return _literal_frozenset(path, node.id)
    raise AssertionError(
        f"{path.relative_to(_REPO)}:{name} is no longer a set literal "
        f"({type(node).__name__}); this test can no longer verify it, which "
        f"means the divergence guard is off. Make it a literal or rewrite the "
        f"guard — do not leave it unverifiable."
    )


class TestOneDenominatorDefinition(unittest.TestCase):

    def test_base_is_the_expected_denominator(self):
        self.assertEqual(base.GRADED_VERDICTS, EXPECTED)

    def test_model_outcome_verdicts_are_the_three_named_ones(self):
        self.assertEqual(
            base.MODEL_OUTCOME_VERDICTS,
            frozenset({"FAIL_NO_EDITS", "SANDBOX-REJECT", "NO_DELIVERABLE"}),
        )
        # And they really are a subset of the denominator, not a parallel list.
        self.assertTrue(base.MODEL_OUTCOME_VERDICTS <= base.GRADED_VERDICTS)

    def test_compare_products_agrees(self):
        got = _literal_frozenset(
            _REPO / "tools" / "compare" / "compare_products.py",
            "_GRADED_VERDICTS")
        self.assertEqual(got, EXPECTED)

    def test_dashboard_collect_agrees(self):
        got = _literal_frozenset(
            _REPO / "tools" / "dashboard" / "collect.py", "_GRADED_VERDICTS")
        self.assertEqual(got, EXPECTED)

    def test_all_three_agree_with_each_other(self):
        """The property, stated directly: one run set, one pass rate."""
        sets = {
            "adapters/base.py": base.GRADED_VERDICTS,
            "tools/compare/compare_products.py": _literal_frozenset(
                _REPO / "tools" / "compare" / "compare_products.py",
                "_GRADED_VERDICTS"),
            "tools/dashboard/collect.py": _literal_frozenset(
                _REPO / "tools" / "dashboard" / "collect.py",
                "_GRADED_VERDICTS"),
        }
        distinct = {frozenset(v) for v in sets.values()}
        self.assertEqual(
            len(distinct), 1,
            "the denominator diverged again — %s. One run set must not yield "
            "two pass rates." % {k: sorted(v) for k, v in sets.items()},
        )


    def test_no_fourth_copy_appeared_unguarded(self):
        """A new spelled-out denominator anywhere in tools/ must be registered.

        The original bug was a copy nobody knew about. This scans for the
        pattern and fails on an unknown location, so the next copy arrives with
        a decision attached instead of silently disagreeing.
        """
        known = {
            Path("tools/run-agent/adapters/base.py"),
            Path("tools/compare/compare_products.py"),
            Path("tools/dashboard/collect.py"),
            Path("tools/run-agent/tests/test_denominator_is_one_definition.py"),
        }
        pat = re.compile(r"^\s*_?(?:MODEL_OUTCOME_)?GRADED_VERDICTS\s*=",
                         re.MULTILINE)
        found = set()
        for py in (_REPO / "tools").rglob("*.py"):
            rel = py.relative_to(_REPO)
            if rel in known:
                continue
            try:
                src = py.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pat.search(src):
                found.add(rel.as_posix())
        self.assertEqual(
            found, set(),
            "a new pass-rate denominator was defined outside the four known "
            "places: %s. Either import/derive it, or add it to `known` here "
            "AND to test_all_three_agree_with_each_other." % sorted(found),
        )


if __name__ == "__main__":
    unittest.main()
