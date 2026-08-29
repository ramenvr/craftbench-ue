"""matrix_oracle — offline evidence for every discrimination MATRIX substring.

WHY THIS EXISTS
---------------
``cb discriminate`` credits a negative leg only when the MATRIX row's *named*
substring appears in that leg's log. That is the whole discrimination claim.
But ``aura_rig.discriminate._extract_substrings`` has a **last-resort branch**:
when a message cell carries no substantive backticked literal, it falls back to
the de-noised WHOLE CELL. Loose prose in a cell therefore becomes the "named
substring", and loose prose can match a log for reasons that have nothing to do
with the gate the row claims. The green light is then meaningless exactly where
it should be hardest.

This module is the static counter-evidence. For every task that ships a
``discrimination/MATRIX.md`` it answers two questions with **no UE, no build and
no tokens**:

1. **Is the recorded substring real?** Can the verifier's own source ever print
   it verbatim — from a ``FinishTest(EFunctionalTestResult::Failed, ...)``
   message in the fixture C++ the task's front-matter ``fixtures:`` key names,
   or from a string the ``introspect:`` script can build? A substring that
   exists nowhere in the verifier's source cannot be the reason anything failed.
2. **Does the substring isolate?** Within one task, two negative legs whose
   substrings are indistinguishable satisfy the count rule ("N legs FAILed")
   while isolating nothing. Entailment, not just equality, is the test: if leg
   X's substrings all sit inside leg Y's message, then X's log is satisfied by
   Y's failure and X pins nothing of its own.

Plus the ASCII rule (the 2026-07-21 ``t2-homing-projectile`` incident): the UE
log's UTF-8 is read back as cp1252, so a MATRIX cell containing an em dash or a
smart quote can never match — a *correct* FAIL then misclassifies as
wrong-reason.

HOW FORMAT STRINGS ARE HANDLED (the load-bearing approximation)
---------------------------------------------------------------
Most failure messages are ``FString::Printf(TEXT("... %.0f ... %d"), A, B)``.
Only the LITERAL portions survive into the log verbatim; the ``%``-runs are
replaced at runtime by values nobody can predict statically. So each extracted
message is cut at every printf placeholder into **literal runs**, and a MATRIX
substring must fall entirely inside ONE run. That is deliberately strict and it
is the point: ``granted=0`` spans the boundary of ``... granted=%d`` and is
therefore NOT a literal substring of anything the fixture can print — it can
only match by accident of the value. ``granted=`` is.

``%%`` folds back to a literal ``%`` rather than acting as a cut.

The Python introspect scripts get the same treatment, except that there the
token and its label are almost never one literal: the scripts are built from
``TOKEN = "BOOM_COMPONENT_MISSING"`` module constants fed through
``"%s searched=%d ..." % (token, ...)`` inside a shared helper. A literal-only
scan would report every such row as invented, which is false. So this module
folds Python string expressions into templates: module-level string constants,
function-local string assignments, and **function parameters whose value is a
module constant at every in-module call site** are all substituted in; f-string
fields, ``%``-args and ``.format`` fields that cannot be resolved become cuts.
The result is the same "one literal run" discipline, applied to a value the
script provably can build.

PROVENANCE TIERS (why the C++ corpus is wider than FinishTest alone)
--------------------------------------------------------------------
The ideal anchor is a literal inside ``FinishTest(Failed, ...)``. Real fixtures
routinely compose one: ``ClassifyCube`` writes ``TEXT("found no static-mesh
component on the actor.")`` into an out-param that the Failed ``Printf``
interpolates through ``%s``. That literal genuinely reaches the log, so
rejecting it would manufacture a false alarm against an honest task. Rather
than build a C++ dataflow analysis, every literal in the resolved fixture
sources is in the corpus, but each is TAGGED with its provenance:

  * ``finish_failed``      — inside a ``FinishTest(EFunctionalTestResult::Failed…)``
  * ``introspect``         — folded from the task's introspect script
  * ``fixture_other``      — any other literal in the fixture sources (detail
    helpers, ``UE_LOG`` diagnostics, the Succeeded message)
  * ``introspect_verdict`` — the L2I JSON envelope, ``"id": "<cid>", "passed":
    false``, for a check id the script actually defines

The oracle FAILS a substring that lands in NO tier. It additionally REPORTS
which substrings anchor only on ``fixture_other`` — that is a weaker anchor
than the row implies, and it is the honest place to look next. The tier is not
silently discarded; :func:`TaskEvidence.provenance` returns it.

THE ASYMMETRY: A RED HERE IS STRONG, A GREEN HERE IS NOT
--------------------------------------------------------
This is the single most misreadable thing about the module, so it is stated
once, plainly, and repeated in every finding message the tests emit.

The corpus is deliberately an OVER-APPROXIMATION of what the verifier can
print. The C++ side takes every literal in the resolved fixture sources, not
just the ones a Failed ``FinishTest`` provably reaches. The Python side folds
templates with :class:`_PyFolder`, which is FLOW-INSENSITIVE: a later
assignment adds a candidate rather than replacing one, a function parameter
takes the union of every in-module call site's value, and a branch contributes
both arms. Nothing here is a reachability analysis and nothing here knows which
path FAILED.

Both directions of that follow, and only one of them is a claim:

* **MISSING (the oracle FAILS the row) is trustworthy.** The claim is "no
  source this task declares can build this string on ANY path", and it is made
  against a corpus strictly larger than the reachable one, so a string the
  over-approximation cannot build is genuinely unbuildable here. Act on it.
* **Producible (the oracle passes the row) is NOT verification.** It says the
  string is inside something the sources could emit somewhere. It does not say
  the FAILURE path emits it, that the check the row names is the one that would
  fire, or that any run has ever printed it. At the ``introspect`` tier this is
  at its weakest, because the fold is over-approximating twice (unresolved
  arguments become cuts, resolved ones become the union of all call sites).
  Read it as "not disproven", never as "verified". The only instrument that
  upgrades it is a real ``cb discriminate`` run.

:data:`TIER_CAVEATS` carries the per-tier version of that sentence in ASCII, so
a finding message can print the honest caveat instead of a tier name a reader
has to interpret.

Everything here is stdlib-only and never touches UE.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

# Sentinel standing for "a run-time value goes here" in a folded template. Never
# appears in real source text.
CUT = "\x00"
_PCT_ESCAPE = "\x01"

TIER_FAILED = "finish_failed"
TIER_FIXTURE = "fixture_other"
TIER_INTROSPECT = "introspect"
TIER_VERDICT = "introspect_verdict"
TIER_NONE = "MISSING"

# Strongest-first; a substring is credited to the strongest tier that has it.
TIER_ORDER = (TIER_FAILED, TIER_INTROSPECT, TIER_FIXTURE, TIER_VERDICT)

# What a reader must NOT conclude from each tier. These strings ride into
# assertion / diagnostic messages, which this repo reads back through cp1252,
# so they are ASCII-ONLY: no em dashes, no smart quotes (repo convention). The
# ASCII-ness is pinned by test_every_tier_carries_an_ascii_caveat.
TIER_CAVEATS: dict = {
    TIER_FAILED: (
        "anchored inside a FinishTest(EFunctionalTestResult::Failed, ...) "
        "message of a fixture this task declares. The strongest anchor "
        "available: the literal is on a failure path by construction. Still "
        "not proof that THIS leg takes that path."
    ),
    TIER_INTROSPECT: (
        "folded out of the task's introspect script by an OVER-APPROXIMATING, "
        "FLOW-INSENSITIVE constant folder. It proves the script CAN build this "
        "string on SOME path (union of every call site, both arms of every "
        "branch); it does NOT prove the FAILING path builds it. Read this as "
        "'not disproven', never as 'verified' - only a real `cb discriminate` "
        "run upgrades it."
    ),
    TIER_FIXTURE: (
        "this string is IN THE FIXTURE SOURCE somewhere - a detail helper, a "
        "UE_LOG diagnostic, or the Succeeded message. It is NOT known to be on "
        "the FAILURE path at all. The MATRIX row implies a named assertion; "
        "this anchor does not deliver one, so the leg may be credited by a log "
        "line that has nothing to do with the gate the row claims."
    ),
    TIER_VERDICT: (
        "the L2I JSON envelope for a check id the script really defines. It "
        "pins the check id and json.dumps' default spacing, not the REASON the "
        "check failed, and it dies silently if anyone passes indent= or "
        "renames a key."
    ),
    TIER_NONE: (
        "NO source this task declares can build this string on any path. This "
        "is the oracle's one STRONG verdict: the corpus is an "
        "over-approximation, so what it cannot build is genuinely unbuildable "
        "here, and the leg can never be credited."
    ),
}


def tier_caveat(tier: str) -> str:
    """The honest one-liner for a provenance tier, for use in a finding message.

    Exists so no caller has to re-derive the asymmetry documented in the module
    docstring: MISSING is a strong claim, everything else is a weak one, and
    ``introspect`` / ``fixture_other`` are weak for DIFFERENT reasons that a
    reader needs spelled out. ASCII-only by contract."""
    return TIER_CAVEATS.get(tier, f"unknown provenance tier {tier!r}")


# --------------------------------------------------------------------------- #
# Leg taxonomy: which negative legs carry an ISOLATION claim                    #
# --------------------------------------------------------------------------- #

#: The label ``discriminate.parse_matrix`` gives the no-submission leg.
SMOKE_LEG_LABEL = "empty"


def is_isolation_leg(label: str) -> bool:
    """True for a negative leg that CLAIMS to isolate a specific gaming mode.

    ``empty`` is the one negative leg that does not. It is the FR-017 smoke
    floor - "grade a throwaway empty dir; it must FAIL" - and
    ``discriminate.build_legs`` treats its MATRIX substring as optional for
    exactly that reason ("exit-1 FAIL is sufficient for empty"). An empty
    submission has no authored defect to attribute; it trips whichever gate the
    checkpoint schedule reaches FIRST, and which gate that is, is a property of
    the fixture's ordering, not of anything the submission did.

    MEASURED, gp-glide-stamina-cpp, 2026-08-08: ``empty`` and the ``no-mesh``
    variant land on the SAME substring, because the checkpoint-0 visibility gate
    runs before the ability check. That is BY DESIGN on both sides - ``no-mesh``
    is a behaviorally perfect solve whose only defect is invisibility, so the
    visibility gate is precisely its own gate, and ``empty`` reaches it
    incidentally. t2-hud-layout-and-countdown records the same shape for
    ``added-late`` (a genuine late-creation gaming mode that legitimately dies
    at the presence gate ``empty`` also trips).

    Treating that collision as a uniqueness violation would assert something no
    one believes: that no variant may ever target a task's FIRST gate. So
    ``empty`` is EXCLUDED from the pairwise entailment matrix.

    The exclusion is narrow and it does not discard the signal:

      * variant-vs-variant entailment is still a hard failure - two authored
        gaming modes dying at one gate prove a count, not a discrimination;
      * every empty/variant collision is still REPORTED by name, so the fact
        that a variant adds no isolation beyond the smoke leg stays visible;
      * a separate check (``empty-floor``) requires at least one variant leg
        that is NOT entailed by ``empty``, so a matrix cannot collapse onto the
        smoke leg wholesale and read green.
    """
    return label != SMOKE_LEG_LABEL

# The L2I verdict envelope: the layer prints ``json.dumps({"checks": [...]})``
# where each entry is ``check(cid, passed, detail)`` ->
# ``{"id": ..., "passed": ..., "detail": ...}``. json.dumps' default separators
# make ``"id": "<cid>", "passed": false`` a verbatim log substring, so a MATRIX
# row CAN legitimately anchor on it. It is its own tier because it is a weaker
# anchor than a named detail: it pins the check id and the serializer's spacing,
# not the reason the check failed, and it silently dies if anyone passes
# ``indent=`` or renames a key.
_JSON_VERDICT_RE = re.compile(r'^"id":\s"(?P<cid>[A-Za-z0-9_]+)",\s"passed":\s(?:true|false)$')


# --------------------------------------------------------------------------- #
# Placeholder cutting                                                          #
# --------------------------------------------------------------------------- #

_PRINTF_RE = re.compile(
    r"%[-+ #0']*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|q|j|z|t)?[diuoxXeEfFgGaAcspn]"
)


def literal_runs(msg: str) -> list[str]:
    """Cut a printf-style format string into its verbatim literal runs."""
    tmp = msg.replace("%%", _PCT_ESCAPE)
    return [p.replace(_PCT_ESCAPE, "%") for p in _PRINTF_RE.split(tmp) if p]


def template_runs(template: str) -> list[str]:
    """Cut an already-folded template (CUT-separated) into its literal runs."""
    return [p for p in template.split(CUT) if p]


def _apply_percent(left: str, args: Optional[Sequence[str]]) -> str:
    """``left % args`` at template level: substitute what is known, cut the rest."""
    tmp = left.replace("%%", _PCT_ESCAPE)
    out: list[str] = []
    pos = 0
    idx = 0
    for m in _PRINTF_RE.finditer(tmp):
        out.append(tmp[pos:m.start()])
        if args is not None and idx < len(args):
            out.append(args[idx])
        else:
            out.append(CUT)
        idx += 1
        pos = m.end()
    out.append(tmp[pos:])
    return "".join(out).replace(_PCT_ESCAPE, "%")


# --------------------------------------------------------------------------- #
# C++ side: literals, and which of them a Failed FinishTest owns                #
# --------------------------------------------------------------------------- #

def strip_cpp_comments(text: str) -> str:
    """Blank out ``//`` and ``/* */`` comments, preserving offsets and newlines.

    String and character literals are honoured, so a ``"//"`` inside a message
    is not mistaken for a comment. Offsets are preserved because the literal
    scanner reports positions."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            quote = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            for _ in range(2):
                if i < n:
                    out[i] = " "
                    i += 1
            continue
        i += 1
    return "".join(out)


_CPP_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"', "\\": "\\",
    "'": "'", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
}


def _cpp_literals(text: str) -> list[tuple[int, int, str]]:
    """Every double-quoted literal in ``text`` as ``(start, end, decoded)``."""
    out: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "'":  # char literal — skip whole
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        if text[i] != '"':
            i += 1
            continue
        start = i
        i += 1
        buf: list[str] = []
        while i < n:
            ch = text[i]
            if ch == "\\" and i + 1 < n:
                buf.append(_CPP_ESCAPES.get(text[i + 1], text[i + 1]))
                i += 2
                continue
            if ch == '"':
                i += 1
                break
            buf.append(ch)
            i += 1
        out.append((start, i, "".join(buf)))
    return out


# Gap between two literals that still means "these concatenate", incl.
# ``TEXT("a") TEXT("b")`` and a line-wrapped ``TEXT("a"\n  "b")``.
_CONCAT_GAP_RE = re.compile(r"[\s)]*(?:TEXT(?:VIEW)?\s*\()?\s*\Z")


def _merge_adjacent(text: str, lits: Sequence[tuple[int, int, str]]) -> list[tuple[int, str]]:
    """C++ adjacent-literal concatenation. Returns ``(start_offset, value)``."""
    merged: list[tuple[int, str]] = []
    cur: Optional[str] = None
    cur_start = 0
    prev_end: Optional[int] = None
    for start, end, val in lits:
        if cur is not None and prev_end is not None and _CONCAT_GAP_RE.fullmatch(
                text[prev_end:start]):
            cur += val
        else:
            if cur is not None:
                merged.append((cur_start, cur))
            cur, cur_start = val, start
        prev_end = end
    if cur is not None:
        merged.append((cur_start, cur))
    return merged


_FINISHTEST_RE = re.compile(r"\bFinishTest\s*\(")
_FAILED_ARG_RE = re.compile(r"\A\s*EFunctionalTestResult\s*::\s*Failed\s*,")


def _call_span(text: str, open_paren: int) -> Optional[tuple[int, int]]:
    """``(body_start, body_end)`` for the parens starting at ``open_paren``."""
    depth = 0
    i, n = open_paren, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            quote = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return open_paren + 1, i
        i += 1
    return None


def cpp_literal_tiers(cpp_text: str) -> tuple[list[str], list[str]]:
    """``(failed_messages, other_literals)`` for one fixture source file.

    ``failed_messages`` are the (still placeholder-bearing) messages handed to
    ``FinishTest(EFunctionalTestResult::Failed, ...)``; ``other_literals`` is
    every remaining string literal in the file."""
    src = strip_cpp_comments(cpp_text)
    failed_spans: list[tuple[int, int]] = []
    failed: list[str] = []
    for m in _FINISHTEST_RE.finditer(src):
        span = _call_span(src, m.end() - 1)
        if span is None:
            continue
        body = src[span[0]:span[1]]
        if not _FAILED_ARG_RE.match(body):
            continue
        failed_spans.append(span)
        failed.extend(v for _, v in _merge_adjacent(body, _cpp_literals(body)))

    # Adjacent-merge the non-Failed literals too, so a wrapped detail string is
    # one run rather than two.
    outside = [(s, e, v) for s, e, v in _cpp_literals(src)
               if not any(a <= s < b for a, b in failed_spans)]
    other = [v for _, v in _merge_adjacent(src, outside)]
    return failed, other


# --------------------------------------------------------------------------- #
# Python side: what an introspect script can build                             #
# --------------------------------------------------------------------------- #

_MAX_ALTS = 8          # candidate templates kept per expression
_MAX_ROUNDS = 3        # fixed-point rounds for params / returns / consts


class _Tup:
    """A tuple value: per-position candidate lists."""

    __slots__ = ("items",)

    def __init__(self, items: list[list]):
        self.items = items


class _Seq:
    """A list/set/dict-values collection: flattened element candidates."""

    __slots__ = ("items",)

    def __init__(self, items: list):
        self.items = items


def _arg_combos(per_pos: list[list[str]], limit: int = 24) -> list[list[str]]:
    """Argument tuples to try for one format string.

    NOT the cartesian product. A shared helper called with four different token
    stems gives 4 candidates in position 0 and 4 in position 2; a truncated
    product varies the LAST position fastest and would only ever emit the first
    token stem — which is exactly how ``RIG_SUN_LIGHT_WRONG_TYPE`` reads as
    invented while ``RIG_SKY_ATMOSPHERE_WRONG_TYPE`` reads as real. So vary one
    position at a time off a base tuple: every candidate is exercised in its own
    slot, at linear rather than exponential cost.

    PLUS the CO-INDEXED DIAGONAL, and that half is load-bearing (2026-08-12).
    Varying one position at a time holds every OTHER position at its base, so
    the only CORRELATED tuple it can build is the base tuple itself. A grader
    that formats two fields of the same table row —

        for key, old, new in ENUM_SPECS:
            detail = "ENUM_NEW_MISSING_%s path=%s" % (new, "%s/%s" % (DIR, new))

    — therefore reads as producible for the table's FIRST row and unbuildable
    for every other row, purely as an artifact of which row happens to sit at
    index 0. That is not a weak verdict, it is a WRONG one: CHECK 1 calls
    TIER_NONE "the oracle's one STRONG verdict ... genuinely unbuildable here",
    so the blind spot presented as certainty. Found when
    ``t2-consistent-enum-names`` landed with four co-indexed rows: the
    ``E_WeaponType`` leg passed and the ``E_ItemRarity`` leg failed, off the
    same format string, on the same code path.

    So also advance EVERY position together (positions with fewer candidates
    hold at their base rather than inventing a value). Still linear, and it is
    the shape a table-driven grader actually emits.

    AND take the EXACT product whenever it fits in the budget. The original
    objection above is to a TRUNCATED product, which is genuinely worse than
    the linear sweep — but an untruncated one is not an approximation at all,
    and most real format strings are small enough to afford it (2x4 = 8 here).
    Falling back to the sweeps only when the product would blow the budget
    makes this strictly more complete than either strategy alone, and it is
    what closes the remaining case: a detail joining TWO different tables
    (``BP_DEP_OLD_NAME_LIVE_%s old=%s`` pairs a Blueprint from BP_SPECS with an
    enum package from ENUM_SPECS) needs a cross pairing that no diagonal walk
    of co-indexed rows can reach.

    ORDER IS THE LOAD-BEARING PART, not enumeration completeness. Whatever
    this returns is truncated downstream by ``_cap`` at ``_MAX_ALTS``, so a
    strategy is only as good as its first few entries. Taking the exact
    cartesian product was tried and is WORSE for exactly that reason: 4x4=16
    tuples capped at 8 keeps only the first two values of position 0 and drops
    the correlated tuples for the rest, which is the truncated-product bias the
    paragraph above rejects, reintroduced one layer down. Emitting the
    correlated tuples FIRST is what survives the cap."""
    base = [p[0] for p in per_pos]
    combos = [list(base)]

    width = max((len(p) for p in per_pos), default=0)
    for j in range(1, width):
        combo = [p[j] if j < len(p) else p[0] for p in per_pos]
        if combo not in combos:
            combos.append(combo)
            if len(combos) >= limit:
                return combos

    for i, cands in enumerate(per_pos):
        for c in cands[1:]:
            combo = list(base)
            combo[i] = c
            if combo not in combos:
                combos.append(combo)
                if len(combos) >= limit:
                    return combos
    return combos


def _cap(xs: list) -> list:
    out: list = []
    for x in xs:
        if x not in out:
            out.append(x)
        if len(out) >= _MAX_ALTS:
            break
    return out


class _PyFolder:
    """A small, deliberately over-approximating constant folder for the
    introspect scripts.

    It exists because these scripts almost never spell a failure token as one
    literal. The recurring shape is a module constant (or a table key) pushed
    through a shared helper::

        BOOM_MISSING_TOKEN = "BOOM_COMPONENT_MISSING"
        def _absent(token, ...):
            return "%s searched=%d names=%s wanted=%s" % (token, ...)
        ... _absent(BOOM_MISSING_TOKEN, ...)

    A literal-only scan would report ``BOOM_COMPONENT_MISSING searched=`` as
    invented, which is false — the script builds it on every run. So this
    folder resolves the constructs those scripts actually use, and CUTs
    everything else:

      * module-level string constants, dicts/lists and comprehensions;
      * function-local assignments, incl. tuple-unpack from a call;
      * function parameters, from the values passed at in-module call sites;
      * in-module function return values;
      * ``%``-formatting, f-strings, ``.format``, ``+``, conditional
        expressions, ``.upper()/.lower()/.strip()``, subscripting a known
        table, and ``for`` targets bound from a known table.

    It is FLOW-INSENSITIVE (a later assignment simply adds a candidate) and
    over-approximating: a template it reports might not be reachable on every
    path. That direction is the safe one here, because the oracle's failing
    verdict is the strong claim "no source in this repo can build this at all".
    The converse does NOT hold and must not be read as if it did: a substring
    this folder credits is a string the script could build SOMEWHERE - union of
    every call site, both arms of every branch, no ordering - which is not
    evidence that the failing path builds it, nor that the named check is the
    one that fired. See the module docstring's ASYMMETRY section; the sentence a
    finding message should print is ``TIER_CAVEATS[TIER_INTROSPECT]``.
    Bounded by :data:`_MAX_ALTS` candidates per expression so a pathological
    script cannot blow up the test."""

    _STR_METHODS = {
        "upper": str.upper, "lower": str.lower, "strip": str.strip,
        "rstrip": str.rstrip, "lstrip": str.lstrip, "title": str.title,
    }

    def __init__(self, tree: ast.Module):
        self.tree = tree
        self.module: dict[str, list] = {}
        self.funcs: dict[str, ast.AST] = {}
        self.params: dict[str, dict[str, list]] = {}
        self.returns: dict[str, list] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[node.name] = node
        for _ in range(_MAX_ROUNDS):
            self._seed_module()
            self._seed_returns()

    # -- seeding ----------------------------------------------------------- #
    def _seed_module(self) -> None:
        scope = self.module
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and \
                    isinstance(stmt.targets[0], ast.Name):
                vals = self.vals(stmt.value, scope)
                if vals and vals != [CUT]:
                    scope[stmt.targets[0].id] = vals

    def _seed_returns(self) -> None:
        for name, fn in self.funcs.items():
            out: list = []
            for scope in self._param_scopes(fn):
                for node in ast.walk(fn):
                    if isinstance(node, ast.Return) and node.value is not None:
                        out.extend(self.vals(node.value, scope))
            self.returns[name] = _cap([v for v in out if v != CUT])

    def _param_scopes(self, fn) -> list[dict[str, list]]:
        known = self.params.get(fn.name, {})
        scope = dict(self.module)
        for k, v in known.items():
            scope[k] = v
        return [scope]

    def _record_params(self, call: ast.Call, scope: dict[str, list]) -> None:
        if not isinstance(call.func, ast.Name):
            return
        fn = self.funcs.get(call.func.id)
        if fn is None:
            return
        names = [a.arg for a in getattr(fn.args, "args", [])]
        slot = self.params.setdefault(fn.name, {})
        pairs: list[tuple[str, ast.AST]] = []
        for i, arg in enumerate(call.args):
            if i < len(names):
                pairs.append((names[i], arg))
        for kw in call.keywords:
            if kw.arg in names:
                pairs.append((kw.arg, kw.value))
        for name, node in pairs:
            vals = [v for v in self.vals(node, scope) if v != CUT]
            if vals:
                slot[name] = _cap(slot.get(name, []) + vals)

    # -- value folding ------------------------------------------------------ #
    def vals(self, node: ast.AST, scope: dict[str, list]) -> list:
        """Candidate values for ``node``: string templates, ``_Tup``, ``_Seq``."""
        if isinstance(node, ast.Constant):
            return [node.value] if isinstance(node.value, str) else [CUT]
        if isinstance(node, ast.Name):
            return scope.get(node.id, [CUT])
        if isinstance(node, ast.Tuple):
            return [_Tup([self.vals(e, scope) for e in node.elts])]
        if isinstance(node, (ast.List, ast.Set)):
            return [_Seq(_cap([v for e in node.elts for v in self.vals(e, scope)]))]
        if isinstance(node, ast.Dict):
            return [_Seq(_cap([v for e in node.values if e is not None
                               for v in self.vals(e, scope)]))]
        if isinstance(node, (ast.DictComp, ast.SetComp, ast.ListComp, ast.GeneratorExp)):
            inner = dict(scope)
            for gen in node.generators:
                self._bind_target(gen.target, self.vals(gen.iter, inner), inner)
            body = node.value if isinstance(node, ast.DictComp) else node.elt
            return [_Seq(_cap(self.vals(body, inner)))]
        if isinstance(node, ast.Subscript):
            out: list = []
            for base in self.vals(node.value, scope):
                if isinstance(base, _Seq):
                    out.extend(base.items)
                elif isinstance(base, _Tup):
                    for pos in base.items:
                        out.extend(pos)
            return _cap(out) or [CUT]
        if isinstance(node, ast.IfExp):
            return _cap(self.vals(node.body, scope) + self.vals(node.orelse, scope))
        if isinstance(node, ast.JoinedStr):
            acc = [""]
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    acc = [a + v.value for a in acc]
                elif isinstance(v, ast.FormattedValue) and v.format_spec is None:
                    parts = [s for s in self.vals(v.value, scope) if isinstance(s, str)]
                    acc = _cap([a + p for a in acc for p in (parts or [CUT])])
                else:
                    acc = [a + CUT for a in acc]
            return acc
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                left = [s for s in self.vals(node.left, scope) if isinstance(s, str)]
                right = [s for s in self.vals(node.right, scope) if isinstance(s, str)]
                return _cap([a + b for a in (left or [CUT]) for b in (right or [CUT])])
            if isinstance(node.op, ast.Mod):
                return self._fold_percent(node, scope)
            return [CUT]
        if isinstance(node, ast.Call):
            return self._fold_call(node, scope)
        return [CUT]

    def _fold_percent(self, node: ast.BinOp, scope: dict[str, list]) -> list:
        lefts = [s for s in self.vals(node.left, scope)
                 if isinstance(s, str) and CUT not in s]
        if not lefts:
            return [CUT]
        if isinstance(node.right, ast.Tuple):
            per_pos = [[s for s in self.vals(e, scope) if isinstance(s, str)] or [CUT]
                       for e in node.right.elts]
        elif isinstance(node.right, ast.Dict):
            per_pos = None
        else:
            per_pos = [[s for s in self.vals(node.right, scope)
                        if isinstance(s, str)] or [CUT]]
        out: list = []
        if per_pos is None:
            out = [_apply_percent(left, None) for left in lefts]
        else:
            for left in lefts:
                for combo in _arg_combos(per_pos):
                    out.append(_apply_percent(left, combo))
        return _cap(out) or [CUT]

    def _fold_call(self, node: ast.Call, scope: dict[str, list]) -> list:
        fn = node.func
        if isinstance(fn, ast.Attribute):
            if fn.attr in self._STR_METHODS:
                bases = [s for s in self.vals(fn.value, scope)
                         if isinstance(s, str) and CUT not in s]
                op = self._STR_METHODS[fn.attr]
                return _cap([op(b) for b in bases]) or [CUT]
            if fn.attr == "format":
                return self._fold_format(node, fn, scope)
            return [CUT]
        if isinstance(fn, ast.Name):
            if fn.id in self.funcs:
                return self.returns.get(fn.id, [CUT]) or [CUT]
            if fn.id in ("str", "repr"):
                return [CUT]
        return [CUT]

    def _fold_format(self, node: ast.Call, fn: ast.Attribute,
                     scope: dict[str, list]) -> list:
        bases = [s for s in self.vals(fn.value, scope)
                 if isinstance(s, str) and CUT not in s]
        if not bases:
            return [CUT]
        args = [([s for s in self.vals(a, scope) if isinstance(s, str)] or [CUT])[0]
                for a in node.args]
        out = []
        for base in bases:
            pieces: list[str] = []
            pos = idx = 0
            for m in re.finditer(r"\{[^{}]*\}", base):
                pieces.append(base[pos:m.start()])
                field = m.group(0)[1:-1].split(":")[0].split("!")[0]
                if field.isdigit() and int(field) < len(args):
                    pieces.append(args[int(field)])
                elif field == "" and idx < len(args):
                    pieces.append(args[idx])
                else:
                    pieces.append(CUT)
                if field == "":
                    idx += 1
                pos = m.end()
            pieces.append(base[pos:])
            out.append("".join(pieces))
        return _cap(out) or [CUT]

    # -- binding ----------------------------------------------------------- #
    @staticmethod
    def _elements(vals: list) -> list:
        out: list = []
        for v in vals:
            if isinstance(v, _Seq):
                out.extend(v.items)
            elif isinstance(v, _Tup):
                for pos in v.items:
                    out.extend(pos)
        return out

    def _bind_target(self, target: ast.AST, vals: list,
                     scope: dict[str, list]) -> None:
        """Bind a ``for``/comprehension target from an iterable's elements."""
        elements = self._elements(vals)
        if not elements:
            return
        if isinstance(target, ast.Name):
            scope[target.id] = _cap(elements)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for i, elt in enumerate(target.elts):
                if not isinstance(elt, ast.Name):
                    continue
                picked = [e.items[i][0] for e in elements
                          if isinstance(e, _Tup) and i < len(e.items) and e.items[i]]
                if picked:
                    scope[elt.id] = _cap(picked)

    def _assign(self, stmt: ast.Assign, scope: dict[str, list]) -> None:
        target = stmt.targets[0] if len(stmt.targets) == 1 else None
        if isinstance(target, ast.Name):
            scope[target.id] = _cap(scope.get(target.id, []) +
                                    [v for v in self.vals(stmt.value, scope) if v != CUT]) \
                or [CUT]
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            vals = [v for v in self.vals(stmt.value, scope) if isinstance(v, _Tup)]
            for i, elt in enumerate(target.elts):
                if not isinstance(elt, ast.Name):
                    continue
                picked = [v.items[i][0] for v in vals
                          if i < len(v.items) and v.items[i]]
                if picked:
                    scope[elt.id] = _cap(scope.get(elt.id, []) + picked)

    # -- collection -------------------------------------------------------- #
    def templates(self) -> list[str]:
        out: list[str] = []
        # Repeated rounds: each one discovers call-site parameter values (incl.
        # ones bound inside loops or one call deep) and the next folds with them
        # in hand. Three rounds cover the deepest chain in the shipped scripts
        # (module loop -> per-table helper -> per-check helper).
        for _round in range(_MAX_ROUNDS):
            out = []
            self._seed_returns()
            self._walk(self.tree.body, dict(self.module), out)
            for fn in self.funcs.values():
                for scope in self._param_scopes(fn):
                    self._walk(fn.body, dict(scope), out)
        return out

    def _walk(self, stmts, scope: dict[str, list], out: list[str]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue  # walked separately with its own parameter scope
            if isinstance(stmt, (ast.For, ast.AsyncFor)):
                self._bind_target(stmt.target, self.vals(stmt.iter, scope), scope)
            self._collect(stmt, scope, out)
            if isinstance(stmt, ast.Assign):
                self._assign(stmt, scope)
            for field_name in ("body", "orelse", "finalbody"):
                sub = getattr(stmt, field_name, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                    self._walk(sub, scope, out)
            for handler in getattr(stmt, "handlers", []) or []:
                self._walk(handler.body, scope, out)

    def _collect(self, stmt: ast.stmt, scope: dict[str, list],
                 out: list[str]) -> None:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Call):
                self._record_params(node, scope)
            if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call,
                                 ast.IfExp, ast.Subscript)):
                for v in self.vals(node, scope):
                    if isinstance(v, str) and v and v != CUT:
                        out.append(v)


def introspect_templates(py_text: str) -> list[str]:
    """Every string template the introspect module can build."""
    return _PyFolder(ast.parse(py_text)).templates()


# --------------------------------------------------------------------------- #
# On-disk resolution (mirrors tasklint's fixture-source rule)                   #
# --------------------------------------------------------------------------- #

def tests_module_dirs(substrate_root: Path) -> list[Path]:
    """Same rule tasklint uses: ``Source/*Tests/`` under the substrate."""
    src = substrate_root / "Source"
    if not src.is_dir():
        return []
    return sorted(d for d in src.iterdir() if d.is_dir() and d.name.endswith("Tests"))


def strip_class_prefix(name: str) -> str:
    return name[1:] if name and name[0] in ("A", "F") else name


def resolve_fixture_sources(substrate_root: Path, test_class: str) -> list[Path]:
    """The .h/.cpp implementing ``test_class`` — tasklint's resolution
    (``<stem>.h``/``<stem>.cpp`` anywhere under a tests module, else the header
    that declares the class) — PLUS the shared base classes at each tests-module
    ROOT.

    The bases belong in the corpus: ``CraftBenchFunctionalTest`` and
    ``CraftBenchPawnFunctionalTest`` own real Failed messages ("pawn did not
    spawn/resolve", the checkpoint time-limit path) a MATRIX row may
    legitimately name. Other tasks' per-task fixture folders are NOT included —
    crediting one task's row against another task's assertion is exactly the
    confusion this oracle exists to prevent."""
    stem = strip_class_prefix(test_class)
    found: list[Path] = []
    decl_re = re.compile(rf"\bclass\s+[\w\s]*\b{re.escape(test_class)}\b")
    for tests_dir in tests_module_dirs(substrate_root):
        hit: list[Path] = []
        for suffix in (".h", ".cpp"):
            hit.extend(sorted(tests_dir.rglob(f"{stem}{suffix}")))
        if not hit:
            for h in sorted(tests_dir.rglob("*.h")):
                try:
                    if decl_re.search(h.read_text(encoding="utf-8", errors="replace")):
                        hit.append(h)
                        cpp = h.with_suffix(".cpp")
                        if cpp.exists():
                            hit.append(cpp)
                except OSError:
                    continue
        found.extend(hit)
        # Shared bases only — NOT every module-root .cpp. In the pre-convention
        # flat CraftBenchTemplate layout the module root also holds six OTHER
        # tasks' fixtures, and pulling those in would let one task's MATRIX row
        # be credited against another task's assertion (and would report one
        # fixture's em dash against ten unrelated tasks). The naming convention
        # is the seam: shared machinery is CraftBench*, per-task fixtures are
        # <Task>FunctionalTest.
        found.extend(p for p in sorted(tests_dir.glob("CraftBench*.cpp")))
    seen: set[Path] = set()
    ordered: list[Path] = []
    for p in found:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


# --------------------------------------------------------------------------- #
# The oracle                                                                   #
# --------------------------------------------------------------------------- #

@dataclass
class TaskEvidence:
    """Everything the oracle statically knows about one task's MATRIX."""

    task_id: str
    task_path: Path
    matrix_path: Path
    tiers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    sources: tuple[Path, ...] = ()
    unresolved: tuple[str, ...] = ()
    rows: dict = field(default_factory=dict)
    check_ids: frozenset = frozenset()
    # The Failed messages BEFORE placeholder cutting - the actual line a fixture
    # emits, which is what a diagnostic wants to quote.
    failed_messages: tuple = ()

    def provenance(self, substring: str) -> str:
        """The strongest tier whose literal runs contain ``substring``."""
        for tier in TIER_ORDER:
            if tier == TIER_VERDICT:
                continue
            if any(substring in run for run in self.tiers.get(tier, ())):
                return tier
        m = _JSON_VERDICT_RE.match(substring.strip())
        if m and m.group("cid") in self.check_ids:
            return TIER_VERDICT
        return TIER_NONE

    @property
    def has_corpus(self) -> bool:
        return any(self.tiers.get(t) for t in TIER_ORDER)


def build_evidence(repo_root: Path, spec, matrix_path: Path, rows: dict,
                   substrate_dir_name) -> TaskEvidence:
    """Collect every literal run this task's verifier source can print."""
    failed_runs: list[str] = []
    failed_msgs: list[str] = []
    other_runs: list[str] = []
    introspect_runs: list[str] = []
    sources: list[Path] = []
    unresolved: list[str] = []

    substrate = repo_root / "UE-projects" / substrate_dir_name(spec.substrate)
    fixtures = list(spec.fixtures) + list(spec.l3_fixtures)
    if not fixtures and spec.map_name and spec.test_class_hint and "L2" in spec.layers:
        from spec import Fixture  # the single parser's own type
        fixtures = [Fixture(map_name=spec.map_name, test_class=spec.test_class_hint)]

    seen_cls: set[str] = set()
    for fx in fixtures:
        if fx.test_class in seen_cls:
            continue
        seen_cls.add(fx.test_class)
        paths = resolve_fixture_sources(substrate, fx.test_class) if substrate.is_dir() else []
        if not paths:
            unresolved.append(f"fixture {fx.test_class} (substrate {substrate.name})")
            continue
        for p in paths:
            sources.append(p)
            failed, other = cpp_literal_tiers(p.read_text(encoding="utf-8", errors="replace"))
            for msg in failed:
                failed_msgs.append(msg)
                failed_runs.extend(literal_runs(msg))
            for msg in other:
                other_runs.extend(literal_runs(msg))

    introspect_dir = repo_root / "tools" / "verify-single" / "introspect"
    # Worklist, not a plain loop: a declared script may DELEGATE its check
    # emission to a sibling module (the three unshipped -bp twins print their
    # whole check JSON from `_bp_variant_lib`), so the corpus must follow
    # sibling imports or every lib-emitted literal reads as unbuildable — the
    # oracle's one STRONG verdict, issued falsely. Only siblings that exist in
    # the introspect dir are followed (`import os` resolves nowhere here);
    # stdlib/site imports never enter the queue.
    seen_scripts: set[Path] = set()
    script_queue: list[tuple[str, bool]] = [(s, True) for s in spec.introspect_scripts]
    while script_queue:
        script, declared = script_queue.pop(0)
        path = introspect_dir / script
        if path in seen_scripts:
            continue
        seen_scripts.add(path)
        if not path.is_file():
            if declared:
                unresolved.append(f"introspect script {script}")
            continue
        sources.append(path)
        py_text = path.read_text(encoding="utf-8")
        try:
            templates = introspect_templates(py_text)
        except SyntaxError as exc:  # pragma: no cover - a broken script
            unresolved.append(f"introspect script {script} (unparseable: {exc})")
            continue
        for tpl in templates:
            introspect_runs.extend(template_runs(tpl))
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)",
                             py_text, re.M):
            sibling = f"{m.group(1)}.py"
            if (introspect_dir / sibling).is_file():
                script_queue.append((sibling, False))

    return TaskEvidence(
        task_id=spec.task_id,
        task_path=spec.source_path or matrix_path,
        matrix_path=matrix_path,
        tiers={
            TIER_FAILED: tuple(failed_runs),
            TIER_FIXTURE: tuple(other_runs),
            TIER_INTROSPECT: tuple(introspect_runs),
        },
        sources=tuple(sources),
        unresolved=tuple(unresolved),
        rows=rows,
        # Check ids as the script spells them: an identifier-shaped literal it
        # can build. Used only to validate a TIER_VERDICT anchor, so that a row
        # naming a check id the script does NOT define still reads as MISSING.
        check_ids=frozenset(r for r in introspect_runs
                            if re.fullmatch(r"[a-z][a-z0-9_]{2,}", r)),
        failed_messages=tuple(failed_msgs),
    )


def entails(outer: Iterable[str], inner: Iterable[str]) -> bool:
    """True when every substring in ``inner`` sits inside some substring of
    ``outer`` — a log satisfying ``outer`` also satisfies ``inner``, so
    ``inner`` isolates nothing ``outer`` does not already claim."""
    outer, inner = list(outer), list(inner)
    if not inner or not outer:
        return False
    return all(any(i in o for o in outer) for i in inner)


def non_ascii(s: str) -> list[tuple[int, str]]:
    return [(i, ch) for i, ch in enumerate(s) if ord(ch) > 127]
