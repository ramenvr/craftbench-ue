"""The recorded reasoning policy must keep matching what the request layer sends.

The harness sends no reasoning parameter on any path, so every run answers at its
provider's default, and each run's record says exactly that. The value of saying
it is entirely in it staying TRUE: a mandated-but-unverified setting is a defect
this repo has paid for twice (``CB_PROXY_OPENROUTER``, documented as on and off in
practice; ``--warm-cache``, a silent no-op across a whole sweep). So the
load-bearing test here is the STRUCTURAL one — it reads the request builders
rather than a hand-kept list, and fails the moment one of them starts sending a
parameter while the record still claims the provider default.

Scope the scan cannot reach, stated so nobody reads it as wider than it is. It
covers the request builders IN THIS REPOSITORY, which is every arm the
open-source release can run: claude-p, unreal-mcp, openrouter and bare. The
`aura-mcp` arm is disclosed but not runnable from here, and the vendor-side
half of it assembles its own request out of tree, so no scan in this repo can
speak for it. The claim the record makes is about OUR request layer only —
which is exactly the claim it makes.
"""

import ast
import json
import pathlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from adapters.base import (  # noqa: E402
    REASONING_PARAM_SENT,
    REASONING_POLICY,
    REASONING_REQUEST_PARAMS,
    AgentResult,
    reasoning_policy_fields,
)
import run  # noqa: E402

#: Directories holding every in-repo request builder: the adapters (JSON bodies,
#: CLI argv, env overrides) and the rig (whose logging proxy is the one middlebox
#: that could rewrite a body in flight). Globbed rather than listed so a NEW
#: adapter is covered on the day it lands.
_SCANNED_DIRS = ("adapters", "aura_rig")


def _normalize(token: str) -> str:
    """A JSON key, a CLI flag and an env var name reduced to one spelling.

    Splits on ``=`` because argv fuses the two halves: ``--reasoning-effort=high``
    is one token on the wire and must normalize to the same thing as the two-token
    form. Without the split it reduced to ``reasoning_effort=high``, matched
    nothing in REASONING_REQUEST_PARAMS, and scanned clean.
    """
    return token.strip().split("=", 1)[0].lstrip("-").replace("-", "_").lower()


#: Where the policy is DECLARED. Its own declaration must never count as an
#: emission -- see `declaration_site` below.
_POLICY_SRC = _ROOT / "adapters" / "base.py"

#: The module-level names in `_POLICY_SRC` that DECLARE the policy rather than
#: send it. Assignments to these are skipped when scanning that one file.
_DECLARATION_NAMES = ("REASONING_PARAM_SENT", "REASONING_REQUEST_PARAMS",
                      "REASONING_POLICY")


def _declaration_lines(source: str) -> set:
    """Line numbers spanned by the policy declarations in `_POLICY_SRC`."""
    out = set()
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id in _DECLARATION_NAMES
                   for t in targets):
            continue
        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        out |= set(range(node.lineno, end + 1))
    return out


def _emitted_reasoning_params(source: str, declaration_site: bool = False):
    """Reasoning parameters this source EMITS, as (lineno, token) pairs.

    Emission sites only: a dict-literal key, a subscript assignment, a keyword
    argument, or a FLAG-or-ENV-shaped member of a sequence literal. Everything
    else names a parameter without sending one, and the two must not read alike:

    * Reads are not emissions. The proxy and the wire adapter legitimately read
      ``reasoning_tokens`` / ``thinking_tokens`` back out of a usage payload, and
      a guard that could not tell accounting from actuation would be switched off
      within a week.
    * A BARE key inside a sequence is vocabulary, not traffic — a renderer's
      record-key lookup list, or this guard's own parameter tuple. What a sequence
      does carry outward is argv and env names, so inside one only ``-``-prefixed
      flags and ALL_CAPS env vars count; a bare key can only be emitted through
      one of the other three shapes anyway.
    """
    # THE REVERSE LEG WAS SELF-SATISFYING. `_SCANNED_DIRS` includes `adapters`,
    # so the scan reads `adapters/base.py` -- the file that HOLDS the declaration.
    # Writing the natural policy change there, `REASONING_PARAM_SENT =
    # {"reasoning": {"effort": "high"}}`, made the dict-literal rule count line
    # 314 as an emission (verified: the scan returned exactly
    # `{'adapters/base.py': [(314, 'reasoning')]}`), so "declared but nobody
    # sends -> red" passed on a single edit with no request-layer change at all.
    # That is the one direction this guard exists for; the declaration must not
    # be able to satisfy it.
    skip = _declaration_lines(source) if declaration_site else set()
    hits = []
    for node in ast.walk(ast.parse(source)):
        if skip and getattr(node, "lineno", 0) in skip:
            continue
        tokens = []
        if isinstance(node, ast.Dict):
            tokens += [k.value for k in node.keys
                       if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            tokens += [e.value for e in node.elts
                       if isinstance(e, ast.Constant) and isinstance(e.value, str)
                       and (e.value.startswith("-") or e.value.isupper())]
        elif isinstance(node, ast.Call):
            tokens += [kw.arg for kw in node.keywords if kw.arg]
            # POSITIONAL string arguments too. `cmd.append("--reasoning-effort")`
            # and `body.setdefault("thinking", x)` are emissions, and the first is
            # this very repo's idiom -- `cmd.append("--strict-mcp-config")` sits
            # at adapters/claude_p.py:168, one line from where a reasoning flag
            # would go. Reading only `node.keywords` let both scan clean.
            #
            # Scoped the same way a sequence literal is (flag- or ENV-shaped), for
            # the same reason: a bare positional string is usually a lookup key
            # being READ, and this guard must keep telling accounting from
            # actuation. A bare key can still only be emitted through one of the
            # other three shapes.
            tokens += [a.value for a in node.args
                       if isinstance(a, ast.Constant) and isinstance(a.value, str)
                       and (a.value.startswith("-") or a.value.isupper())]
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            tokens += [t.slice.value for t in targets
                       if isinstance(t, ast.Subscript)
                       and isinstance(t.slice, ast.Constant)
                       and isinstance(t.slice.value, str)]
        for token in tokens:
            if _normalize(token) in REASONING_REQUEST_PARAMS:
                hits.append((getattr(node, "lineno", 0), token))
    return hits


def _scan_request_builders():
    """Every reasoning-parameter emission in the in-repo request builders."""
    found = {}
    for name in _SCANNED_DIRS:
        for path in sorted((_ROOT / name).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            hits = _emitted_reasoning_params(path.read_text(encoding="utf-8"),
                                             declaration_site=(path == _POLICY_SRC))
            if hits:
                found[path.relative_to(_ROOT).as_posix()] = hits
    return found


class TestRecordedPolicyMatchesTheRequestLayer(unittest.TestCase):
    def test_the_recorded_policy_and_the_request_layer_agree(self):
        """Either both say "nothing sent", or both say something is.

        Symmetric on purpose. Starting to send a parameter is allowed — it just
        has to be declared in adapters/base.py in the same change, which is what
        makes every run's record true again. Claiming one nobody sends is the same
        lie mirrored, and it is how a documented-but-unverified setting becomes a
        table in a published comparison.
        """
        emissions = _scan_request_builders()
        # The two declarations must first agree with EACH OTHER. Anding them into
        # one flag let either skew through: a label of "effort-high" beside a sent
        # value of None, or the reverse, both fell to the else branch and passed
        # green whenever any emission existed.
        self.assertEqual(
            REASONING_PARAM_SENT is None,
            REASONING_POLICY == "provider-default",
            f"adapters/base.py declares REASONING_PARAM_SENT="
            f"{REASONING_PARAM_SENT!r} beside REASONING_POLICY="
            f"{REASONING_POLICY!r}. One says a parameter goes out and the other "
            "says none does; every run's record would carry the contradiction.")
        claims_default = REASONING_PARAM_SENT is None
        if claims_default:
            self.assertEqual(
                emissions, {},
                "a request builder emits a reasoning parameter while every run's "
                f"record still says {REASONING_POLICY!r} with nothing sent: "
                f"{json.dumps(emissions, indent=2)}. Set REASONING_PARAM_SENT and "
                "REASONING_POLICY in adapters/base.py in the SAME change, so the "
                "record names what the wire actually carries.")
        else:
            self.assertNotEqual(
                emissions, {},
                f"the record claims policy {REASONING_POLICY!r} / sent "
                f"{REASONING_PARAM_SENT!r}, but no in-repo request builder sends "
                "any of REASONING_REQUEST_PARAMS. Either the emission was reverted "
                "and the label was not, or the parameter now goes out through a "
                "builder this scan cannot see (see the module docstring's scope "
                "note) — in which case say so where the policy is declared.")

    def test_a_read_is_still_not_an_emission(self):
        """The other half of the shape rule, or the guard gets switched off.

        Widening the Call branch to positional args (2026-08-25) risked exactly
        this: the proxy and the wire adapter legitimately READ
        ``reasoning_tokens`` back out of a usage payload, and a guard that called
        accounting "actuation" would be red on correct code and disabled within a
        week. Positional strings are therefore scoped the same way sequence
        members are -- flag- or ENV-shaped only.
        """
        for source in ('n = usage.get("reasoning_tokens")',
                       'x = payload["thinking_tokens"]',
                       'total += d.get("reasoning", 0)',
                       'KEYS = ["reasoning_tokens", "thinking_tokens"]'):
            with self.subTest(source=source):
                self.assertEqual([], _emitted_reasoning_params(source))

    def test_the_declaration_itself_cannot_satisfy_the_reverse_leg(self):
        """THE defect this guard's reverse direction existed to prevent, and
        could not.

        ``_SCANNED_DIRS`` includes ``adapters``, so the scan reads
        ``adapters/base.py`` -- the file that HOLDS the declaration. Writing the
        natural policy change there, ``REASONING_PARAM_SENT = {"reasoning":
        {"effort": "high"}}``, made the dict-literal rule count that very line as
        an emission: the scan returned ``{'adapters/base.py': [(314,
        'reasoning')]}``, the else branch's assertNotEqual passed, and "declared
        but nobody sends -> red" was satisfiable with a SINGLE edit and no
        request-layer change at all.

        The consequence was not cosmetic: every run's record would then carry
        ``reasoning_policy="effort-high"`` / ``reasoning_requested={...}`` while
        the wire carried nothing, and ``repcard`` renders that claim straight
        from the record. A documented-but-unverified setting is worse than an
        undocumented one, because it is quoted.
        """
        src = (_POLICY_SRC).read_text(encoding="utf-8")
        mutated = src.replace('REASONING_PARAM_SENT = None',
                              'REASONING_PARAM_SENT = '
                              '{"reasoning": {"effort": "high"}}')
        self.assertNotEqual(src, mutated, "the declaration moved; re-point this")

        # Scanned as an ordinary file, the declaration DOES look like traffic --
        # which is the whole trap, and why the fix cannot be "the dict rule is
        # too broad".
        self.assertTrue(_emitted_reasoning_params(mutated),
                        "the declaration no longer parses as a dict literal, so "
                        "this test is no longer describing the hazard")
        # Scanned as the declaration site, it is correctly not an emission.
        self.assertEqual(
            [], _emitted_reasoning_params(mutated, declaration_site=True),
            "declaring a reasoning parameter still satisfies the guard that "
            "exists to catch a declaration nobody honours")

    def test_the_real_scan_treats_base_py_as_the_declaration_site(self):
        # A fix that is not WIRED is the same defect one layer up: the scan must
        # pass declaration_site=True for base.py specifically, not for every file.
        src = pathlib.Path(__file__).read_text(encoding="utf-8")
        self.assertIn("declaration_site=(path == _POLICY_SRC)", src)
        self.assertTrue(_POLICY_SRC.is_file(),
                        f"the declaration source {_POLICY_SRC} does not exist, "
                        "so the exemption matches nothing and the leg is "
                        "self-satisfying again")

    def test_the_scan_sees_each_wire_shape(self):
        """Every shape a reasoning parameter can arrive in, detected.

        Without this the guard above is unfalsifiable: an empty result reads the
        same whether nothing is emitted or the scanner is blind to the shape.
        """
        shapes = {
            'body = {"reasoning": {"effort": "high"}}': "reasoning",
            'body["reasoning_effort"] = "high"': "reasoning_effort",
            'call(thinking={"type": "enabled"})': "thinking",
            'cmd = ["claude", "--reasoning-effort", "high"]': "--reasoning-effort",
            'env["MAX_THINKING_TOKENS"] = "8000"': "MAX_THINKING_TOKENS",
            'run(cmd, env={**os.environ, "MAX_THINKING_TOKENS": "8000"})':
                "MAX_THINKING_TOKENS",
            # Added 2026-08-25, all three previously invisible. The first is
            # THIS FILE'S OWN NEIGHBOUR IDIOM -- adapters/claude_p.py:168 reads
            # `cmd.append("--strict-mcp-config")`, one line from where a
            # reasoning flag would go -- and that argv builder is the request
            # layer for all three measured arms.
            'cmd.append("--reasoning-effort")': "--reasoning-effort",
            'cmd.extend(["--reasoning-effort=high"])': "--reasoning-effort=high",
            'body.setdefault("THINKING", x)': "THINKING",
        }
        for source, token in shapes.items():
            with self.subTest(source=source):
                self.assertEqual(
                    [t for _ln, t in _emitted_reasoning_params(source)], [token])

    def test_naming_a_parameter_is_not_sending_one(self):
        """Both false positives this scan actually produced, kept out.

        The usage fields the proxy and the wire adapter read back; and the bare
        key names a renderer looks up on the record (aura_rig/repcard.py reads
        ``reasoning_effort`` off the envelope) or this guard declares as its own
        vocabulary. A guard that fails on the code READING the record it guards
        gets deleted, not fixed.
        """
        source = ('rec["reasoning_tokens"] = int(details["thinking_tokens"])\n'
                  'usage = {"reasoning_tokens": cd.get("reasoning_tokens")}\n'
                  '_REQUEST_KEYS = ("reasoning_requested", "reasoning_effort")\n'
                  'PARAMS = ("reasoning", "thinking", "budget_tokens")\n')
        self.assertEqual(_emitted_reasoning_params(source), [])


class TestUnmeasuredIsNotZero(unittest.TestCase):
    """The defect this line of work exists to remove.

    Most runs are not gateway-routed, so no reasoning count exists for them. Read
    as zeroes, those runs pull a model's measured reasoning share toward nothing —
    an average diluted by the cells that measured nothing at all.
    """

    def test_a_reported_zero_and_no_measurement_differ(self):
        self.assertEqual(reasoning_policy_fields(0)["reasoning_measurement"],
                         "reported")
        self.assertEqual(reasoning_policy_fields(0)["reasoning_tokens"], 0)
        self.assertEqual(reasoning_policy_fields(None)["reasoning_measurement"],
                         "unmeasured")
        self.assertIsNone(reasoning_policy_fields(None)["reasoning_tokens"])


class TestTheBlockReachesResultJson(unittest.TestCase):
    """A field the writer omits is invisible to every analysis — and this repo has
    lost ``tokens_in``, the scaffold-identity fields and the provider join keys
    that exact way. So the assertion is on the bytes, not on the helper.
    """

    def _record(self, reasoning_tokens):
        run_dir = Path(tempfile.mkdtemp())
        args = types.SimpleNamespace(
            task="tasks/cpp/t0-sanity-log-on-beginplay/task.md",
            model="claude-p:sonnet-5", timeout=1200, preamble_sha=None)
        result = AgentResult(exit_code=0, transcript="", summary="",
                             tool_use_count=0, duration_s=1.0,
                             reasoning_tokens=reasoning_tokens)
        run._write_result(run_dir, args, "run-1", result, None, "PASS")
        return json.loads(
            (run_dir / "result.json").read_text(encoding="utf-8"))["agent"]

    def test_an_unproxied_run_records_the_policy_and_no_measurement(self):
        """``reasoning_requested`` is the parameter, verbatim — never a level name
        like "high", which no provider on this wire reports back."""
        agent = self._record(None)
        self.assertEqual(agent["reasoning_policy"], "provider-default")
        self.assertIsNone(agent["reasoning_requested"])
        self.assertIsNone(agent["reasoning_tokens"])
        self.assertEqual(agent["reasoning_measurement"], "unmeasured")

    def test_a_gateway_routed_run_records_the_count(self):
        agent = self._record(4321)
        self.assertEqual(agent["reasoning_tokens"], 4321)
        self.assertEqual(agent["reasoning_measurement"], "reported")
        self.assertIsNone(agent["reasoning_requested"])


if __name__ == "__main__":
    unittest.main()
