"""The substring-literal oracle: static self-validation of every MATRIX row.

THE HOLE THIS CLOSES
--------------------
``cb discriminate`` credits a negative leg only when the MATRIX row's *named*
substring turns up in that leg's L2/L2I log. That grep IS the discrimination
claim. But ``aura_rig.discriminate._extract_substrings`` ends in a LAST-RESORT
branch: a message cell with no substantive backticked literal falls back to the
de-noised WHOLE CELL. Prose therefore becomes the "named substring", and prose
can match a log for reasons unrelated to the gate the row claims - or can never
match at all, in which case a *correct* FAIL is scored as a wrong-reason FAIL
and the task is condemned for the verifier's typo. The soft spot sits exactly
where the check should be hardest, and per this repo's closure doctrine the
defect class that never files an incident is closed by a TEST, not a probe.

So, offline (no UE, no build, no tokens), for every task that ships a
``discrimination/MATRIX.md``:

1. **Producibility** - every recorded expected-failure substring must be a
   LITERAL SUBSTRING of something the verifier's own source can print: a
   ``FinishTest(EFunctionalTestResult::Failed, ...)`` message in the fixture C++
   the front-matter ``fixtures:`` key names, or a string the ``introspect:``
   script builds. Format strings are cut at every ``%``-placeholder and the
   substring must fall inside ONE literal run, because only the literal runs
   survive verbatim: ``granted=`` is producible from ``... granted=%d``,
   ``granted=0`` is not.

   **This check is one-directional and every message it emits says so.** The
   corpus is an over-approximation (every fixture literal, not just reachable
   ones; a flow-insensitive fold of the introspect script), so a MISSING
   verdict is the strong claim "nothing here can build this at all", while a
   producible verdict means only "not disproven". The per-tier caveat printed
   with each finding is ``matrix_oracle.TIER_CAVEATS``; the reasoning is in
   that module's ASYMMETRY section. Do not read a green here as verification -
   only a real ``cb discriminate`` run is that.
2. **Uniqueness** - within a task, no negative leg's substrings may be ENTAILED
   by another leg's. Two legs dying at the same gate satisfy a count rule while
   isolating nothing; entailment (not just equality) is the test, because a
   substring that sits inside a longer one is satisfied by the longer one's log.

   **The ``empty`` leg is exempt from the pairwise matrix**, and that decision
   is argued in ``matrix_oracle.is_isolation_leg``: ``empty`` is the FR-017
   smoke floor, not a gaming mode, and it trips whichever gate the checkpoint
   schedule reaches first. Requiring it to differ from every variant would
   forbid any variant from targeting a task's FIRST gate. The exemption is
   paid for, not free: empty/variant collisions are still reported by name, and
   check 2b below refuses a matrix whose variants ALL collapse onto ``empty``.
2b. **The empty floor** - at least one negative variant leg must NOT be
   entailed by ``empty``. Otherwise every leg in the matrix is satisfied by the
   one failure an empty submission already produces, and the whole matrix
   re-proves the smoke test.
3. **ASCII** - the UE log's UTF-8 is read back as cp1252, so a cell containing
   an em dash or a smart quote can never match (live incident,
   ``t2-homing-projectile``, 2026-07-21).

Plus two structural guards that keep 1 and 2 from passing vacuously: the fixture
sources and introspect scripts a task declares must RESOLVE on disk (an empty
corpus would otherwise mean "nothing to contradict"), and every negative leg
that has a materialized variant directory must actually record a substring.

Parsers are reused, never re-implemented: ``spec.parse_task_file`` for the front
matter (THE parser) and ``aura_rig.discriminate.parse_matrix`` /
``_extract_substrings`` for the MATRIX, so this oracle sees exactly the
substrings ``cb discriminate`` will grep for - including the ones its
last-resort branch mangles. ``tasklint``'s substrate-alias resolution is
imported for the same reason. The static analysis of the verifier sources lives
in ``tools/verify-single/matrix_oracle.py``.

Tasks with no ``discrimination/MATRIX.md`` are SKIPPED, not failed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
_REPO = _VERIFY.parents[1]
_RUN_AGENT = _REPO / "tools" / "run-agent"

for _p in (str(_VERIFY), str(_RUN_AGENT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matrix_oracle as mo  # noqa: E402
import spec as spec_mod  # noqa: E402
from tasklint import _substrate_dir_name  # noqa: E402  (the alias table, reused)

try:
    from aura_rig.discriminate import discover_variants, parse_matrix
    _DISCRIMINATE_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - reported as a skip, never silent
    discover_variants = parse_matrix = None  # type: ignore[assignment]
    _DISCRIMINATE_IMPORT_ERROR = exc


# --------------------------------------------------------------------------- #
# Corpus discovery                                                             #
# --------------------------------------------------------------------------- #

def _matrix_paths() -> list[Path]:
    return sorted(_REPO.glob("tasks/*/*/discrimination/MATRIX.md"))


def _load(matrix_path: Path):
    """``(spec, rows, evidence)`` for one task, or ``None`` when unusable.

    Never raises: a spec that will not parse is reported by
    ``test_every_matrix_task_loads`` rather than erroring out every other
    subTest in the class through ``setUpClass``."""
    task_file = matrix_path.parent.parent / "task.md"
    if not task_file.is_file():
        return None
    spec = spec_mod.parse_task_file(task_file)
    rows = parse_matrix(matrix_path.read_text(encoding="utf-8"))
    evidence = mo.build_evidence(_REPO, spec, matrix_path, rows, _substrate_dir_name)
    return spec, rows, evidence


# --- the shrink-only ratchet -------------------------------------------------
#
# This oracle was written 2026-08-08 and was RED on 15 (check, task) pairs the
# moment it first ran. Every one is a real finding — see the entries below — but
# a red suite masks the other ~990 tests, which is the same failure mode
# the repo conventions record for a red `tasklint` (CI step 1) hiding every later suite.
#
# So the corpus checks run against a BASELINE rather than being switched off:
#   * a pair in the baseline SKIPs (with its reason printed), so the finding
#     stays visible instead of being deleted;
#   * a pair NOT in the baseline FAILs — a new unsound matrix is caught today;
#   * a pair in the baseline that has started PASSING also FAILs, demanding the
#     entry be removed. That is what makes it a ratchet: the list can only
#     shrink, and it cannot rot the way a plain skip-list does.
#
# Do not add to this dict to make a new task green. Fix the MATRIX.
#
# SHRUNK 2026-08-08: gp-poison-dot-stack-bp's `variant-named` and
# `reference-row` entries were REMOVED because the matrix was actually
# repaired (its 7 rows had parsed with zero substrings and its reference
# row as a FAIL, caused by a later table re-registering the same labels).
# The ratchet is what forced the removal: both checks started passing and
# it failed with "now PASSES but is still listed".
_KNOWN_UNSOUND: dict[tuple[str, str], str] = {
    # ARGUED, not deferred: gp-heal-over-time-cpp DECLARES three collisions in
    # its own MATRIX.md ("ISOLATION CAVEAT 1/2/3") rather than hiding them:
    #   empty vs no-maxhealth      - empty trips HOT-0 incidentally
    #   never-stops vs -in-band    - both are permanent regeneration, one tuned
    #                                to sit inside the disclosed band; they SHARE
    #                                HOT-3's single named FAIL by construction,
    #                                and -in-band exists to prove the StopEpsilon
    #                                edit was load-bearing (stopRise=0.60)
    #   no-clamp vs current-only-clamp - both exceed the cap; the second does so
    #                                only in the BASE value, which is the whole
    #                                point of HOT-5's dual read
    # Each pair dies at one gate that has exactly one named message, so no
    # producible literal can separate them. Removal condition: split the gate.
    ("unique", "gp-heal-over-time-cpp"):
        "3 declared collisions - argued in MATRIX.md ISOLATION CAVEAT 1/2/3",
    # ARGUED, not deferred: gp-glide-stamina-cpp's `no-stop` and `slow-no-stop`
    # both die at gate (5)'s SINGLE FinishTest(Failed) message
    # (GlideStaminaFunctionalTest.cpp:360-368), and after the 2026-08-09
    # forced-exhaustion change that convergence is intended. The only marker
    # that differs, `forced=1`, sits in a UE_LOG and spans a %d, so it is not a
    # matchable literal. Full reasoning + the removal condition:
    # tasks/cpp/gp-glide-stamina-cpp/discrimination/MATRIX.md, "ISOLATION CAVEAT".
    ("unique", "gp-glide-stamina-cpp"):
        "no-stop/slow-no-stop converge on gate (5)'s only named FAIL - argued in MATRIX.md",
    # CHECK 1 — substrings that no assertion in the declared verifier can print,
    # so the leg can never be credited and a correct FAIL reads as wrong-reason.
    # gp-glide-stamina-bp was REMOVED from this baseline 2026-08-16: its one
    # unsound row (the empty leg's pre-visibility-gate GAS prose, measured
    # 2026-07-17) was repaired to the base-class visibility literal after the
    # overnight run-2b sweep credited it wrong-reason — the ratchet flagged the
    # stale entry on its own, again. (Its "ascii-assert" entry below stays: the
    # fixture's U+2014 is a fixture fact this campaign did not touch.)
    ("producible", "gp-glide-stamina-cpp"): "prose/value-spanning substrings",
    # gp-poison-dot-stack-cpp was REMOVED from this baseline 2026-08-13. Its
    # five legs were repaired (an ellipsis inside the backticks, spans crossing
    # %-placeholders, and source deltas such as StackLimitCount = 0 that are
    # never logged), so every expected substring is now a verbatim,
    # placeholder-free span of a real FinishTest literal and this oracle passes
    # it. The ratchet flagged the stale entry on its own — which is precisely
    # what a shrink-only baseline exists to do.
    ("producible", "t0-sanity-bp-log-on-beginplay"): "prose substrings",
    ("producible", "t2-weapon-held-in-right-hand"): "prose substrings",
    # ADDED 2026-08-24, and unlike the entries above this one is argued in the
    # MATRIX itself rather than being a loose substring. gp-crafting-queue's
    # fixture has ONE FinishTest(...Failed...) call reused at all five
    # checkpoints, so its five legs are separated ONLY by the rendered count in
    # "expected exactly N 'CraftCompleted'" / "FIFO); found N." — and N is
    # exactly what this oracle cannot see, because it cuts every format string at
    # the placeholder. Truncating the rows to their placeholder-free span is not
    # available either: two rows would collapse to "FIFO); found " and three to
    # "expected exactly ", which breaks CHECK 2 (uniquely-named legs) and would
    # credit any of those failures as any other. So the fix is a FIXTURE change —
    # give each checkpoint its own placeholder-free phrase — which is a
    # CraftBenchTests edit, review-gated, and it re-invalidates every refgate
    # certificate. Not worth bundling into a rename. The other eight tasks that
    # failed this check on 2026-08-24 WERE fixed, by recording a placeholder-free
    # span that still names the assertion.
    ("producible", "gp-crafting-queue"):
        "five legs separated only by a rendered count; needs a fixture message "
        "change, not a MATRIX edit",
    # CHECK 2 — negative VARIANT legs that do not isolate: one failure satisfies
    # both greps, so the matrix proves a count rather than a discrimination.
    # (Two 2026-08-08 entries were RETIRED 2026-08-09, not fixed-by-deletion:
    # `gp-glide-stamina-cpp` and `t2-hud-layout-and-countdown` were listed for
    # "empty leg entails a variant leg", and the empty leg is now exempt by
    # design - see matrix_oracle.is_isolation_leg for the measurement and the
    # argument. Both tasks' VARIANT legs were re-read row by row when the
    # exemption landed and are pairwise non-entailing, which is why they are
    # gone rather than relabelled. Every remaining entry below is a genuine
    # variant-vs-variant clash:
    #   t0-sanity-bp        cpp-only / wrong-path      -> "No Actor Blueprint found at the required path"
    #   (t1-overlap-teleport-portal was REMOVED from this baseline 2026-08-17.
    #    Its two pre-contact gates - cp0's instant sample and the continuous
    #    per-frame guard - printed ONE literal, so teleport-without-contact
    #    and delayed-unconditional-teleport both credited "before entering
    #    the portal" and no row could say which gate fired. The fixture
    #    messages were SPLIT (message text only: both predicates, the gate
    #    order and every verdict are byte-identical), and each row now
    #    credits its own gate's literal. The ratchet flagged the stale entry
    #    on its own, again.)
    #   t2-gravity          teleport-down-on-timer / small-step-timer-descent -> "altitude changed by a discontinuous jump"
    #   t2-npc-follows      goes-to-original-spot / stops-after-brief-follow  -> "never re-acquired the moved player"
    # )
    ("unique", "t0-sanity-bp-log-on-beginplay"): "entailed legs",
    ("unique", "t2-gravity-floating-pawn-movement"): "entailed legs",
    ("unique", "t2-npc-follows-player"): "entailed legs",
    # CHECK 4 — non-ASCII in a graded assertion: the UE log is written UTF-8 and
    # read back cp1252, so the grep misses (the 2026-07-21 homing-projectile bug).
    ("ascii-assert", "gp-glide-stamina-bp"): "U+2014 in a FinishTest message",
    ("ascii-assert", "gp-glide-stamina-cpp"): "U+2014 in a FinishTest message",
    # CHECK 6/7 — gp-poison-dot-stack-bp's MATRIX records ZERO substrings across
    # all 7 rows, so `cb discriminate` credits its legs without matching any
    # named assertion at all. The sharpest finding here and the first to fix.
}


def _ratchet(case, check: str, task_id: str, failures: list, message: str):
    """Assert ``failures`` is empty, unless (check, task) is a known-unsound
    baseline entry — in which case SKIP, and fail loudly if it has been fixed."""
    known = _KNOWN_UNSOUND.get((check, task_id))
    if failures and known is not None:
        case.skipTest(f"KNOWN-UNSOUND ({check}/{task_id}): {known} "
                      f"- baseline entry in _KNOWN_UNSOUND, fix the MATRIX to "
                      f"remove it")
    if not failures and known is not None:
        case.fail(f"{check}/{task_id} now PASSES but is still listed in "
                  f"_KNOWN_UNSOUND ({known}). Delete the entry - the ratchet "
                  f"only shrinks.")
    case.assertEqual([], failures, message)


def _negative_rows(rows: dict) -> list:
    return [row for row in rows.values() if not row.expect_pass]


def _isolation_rows(rows: dict) -> list:
    """Negative rows that CLAIM to isolate a gaming mode, with a substring to
    isolate it by. Excludes the ``empty`` smoke leg - see
    ``matrix_oracle.is_isolation_leg`` for why that is a design decision and not
    a softening."""
    return [r for r in _negative_rows(rows)
            if r.substrings and mo.is_isolation_leg(r.label)]


def _empty_row(rows: dict):
    """The ``empty`` smoke leg, or ``None`` when the matrix omits it / records
    no substring for it (both legal: ``discriminate`` accepts a bare exit-1
    FAIL for this leg)."""
    row = rows.get(mo.SMOKE_LEG_LABEL)
    return row if row is not None and row.substrings and not row.expect_pass else None


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO)).replace("\\", "/")
    except ValueError:  # pragma: no cover
        return str(path)


@unittest.skipIf(_DISCRIMINATE_IMPORT_ERROR is not None,
                 f"aura_rig.discriminate not importable: {_DISCRIMINATE_IMPORT_ERROR}")
class TestMatrixSubstringOracle(unittest.TestCase):
    """One subTest per task; a red task names the exact rows to fix."""

    @classmethod
    def setUpClass(cls):
        cls.matrices = _matrix_paths()
        cls.loaded = {}
        cls.load_errors = {}
        for path in cls.matrices:
            try:
                got = _load(path)
            except Exception as exc:  # noqa: BLE001 - reported, never swallowed
                cls.load_errors[path] = f"{type(exc).__name__}: {exc}"
                continue
            if got is not None:
                cls.loaded[path] = got

    def test_ratchet_baseline_names_only_real_corpus_tasks(self):
        """The ratchet's one rot vector, found while testing the ratchet itself.

        A ``_KNOWN_UNSOUND`` key naming a task that is NOT in the corpus (no
        ``discrimination/MATRIX.md``, or renamed away) can never fire its
        subTest, so neither the SKIP nor the now-passing check ever runs and the
        entry sits there forever looking like a tracked debt. Pin the keys to
        the live corpus so a rename or a deleted matrix surfaces here instead of
        silently retiring a finding."""
        live = {spec.task_id for spec, _rows, _ev in self.loaded.values()}
        orphans = sorted({task for _check, task in _KNOWN_UNSOUND
                          if task not in live})
        self.assertEqual(
            [], orphans,
            "\n_KNOWN_UNSOUND names tasks with no discrimination/MATRIX.md in "
            "the corpus. Either the task was renamed (update the key) or its "
            "matrix was deleted (drop the entry) - as written these findings "
            "are silently untracked:\n  " + "\n  ".join(orphans))

    def test_corpus_is_non_empty(self):
        """A silent glob miss would make every check below vacuously green."""
        self.assertTrue(self.matrices,
                        "no tasks/*/*/discrimination/MATRIX.md found - the "
                        "oracle would pass vacuously")
        self.assertTrue(self.loaded, "no MATRIX.md resolved to a parseable task.md")

    def test_every_matrix_task_loads(self):
        """A task.md that will not parse silently removes its MATRIX from every
        check above, so the failure has to be named on its own."""
        self.assertEqual(
            {}, {_rel(p): e for p, e in self.load_errors.items()},
            "task.md / MATRIX.md pairs the oracle could not read")

    def test_declared_verifier_sources_resolve_on_disk(self):
        """The evidence corpus must exist, or 'producible' means nothing.

        Same resolution tasklint uses for `fixture-source-exists`; a miss here
        is a spec/substrate defect that would ALSO make the producibility check
        below fail for every row, so it is named separately."""
        for path, (spec, _rows, ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                self.assertEqual(
                    [], list(ev.unresolved),
                    f"{_rel(path)}: declared verifier sources not found on disk: "
                    + "; ".join(ev.unresolved))

    def test_every_matrix_substring_is_producible_by_the_verifier(self):
        """CHECK 1. Every recorded expected-failure substring must fall inside
        one literal run of something the verifier can print.

        ONE-DIRECTIONAL, and the messages say so. A MISSING verdict is the
        strong claim (an over-approximating corpus could not build the string on
        ANY path); a producible verdict only means "not disproven". The weakest
        producible tiers are called out by name with their caveat, so nobody
        reads a green row as a verified one:

          * ``introspect``    - flow-insensitive fold; the script CAN build it
            somewhere, not necessarily on the failing path.
          * ``fixture_other`` - the string is IN THE FIXTURE SOURCE, which is
            NOT the same as being on the failure path (it may be a UE_LOG
            diagnostic or the Succeeded message).
          * ``introspect_verdict`` - pins a check id and json.dumps' spacing,
            not the reason the check failed.
        """
        for path, (spec, rows, ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                bad: list[str] = []
                weak_by_tier: dict = {}
                for row in _negative_rows(rows):
                    for sub in row.substrings:
                        tier = ev.provenance(sub)
                        if tier == mo.TIER_NONE:
                            bad.append(f"    [{row.label}] {sub!r}")
                        elif tier != mo.TIER_FAILED:
                            weak_by_tier.setdefault(tier, []).append(
                                f"      [{row.label}] {sub!r}")
                if weak_by_tier:
                    note = [f"\n[matrix-oracle] {spec.task_id}: substrings that "
                            f"are PRODUCIBLE but weakly anchored. Producible is "
                            f"not verified - it means only that no source "
                            f"contradicts the row:"]
                    for tier in mo.TIER_ORDER:
                        hits = weak_by_tier.get(tier)
                        if not hits:
                            continue
                        note.append(f"    tier {tier}: {mo.tier_caveat(tier)}")
                        note.extend(hits)
                    print("\n".join(note))
                _ratchet(self, "producible", spec.task_id, bad,
                    f"\n{_rel(path)}: these expected-failure substrings are NOT "
                    f"literal substrings of any message this task's verifier can "
                    f"print, so the leg can never be credited (a correct FAIL "
                    f"will read as wrong-reason):\n" + "\n".join(bad)
                    + f"\n  {mo.tier_caveat(mo.TIER_NONE)}"
                    + f"\n  evidence from: "
                    + ", ".join(_rel(s) for s in ev.sources))

    def test_negative_legs_are_uniquely_named(self):
        """CHECK 2. No negative VARIANT leg may be entailed by another.

        Entailment, not equality: if every substring of leg X sits inside a
        substring of leg Y, then Y's log already satisfies X's grep and X
        isolates nothing of its own.

        THE ``empty`` LEG IS DELIBERATELY EXCLUDED, and this is the one place
        the decision bites, so it is argued here as well as in
        ``matrix_oracle.is_isolation_leg``:

        ``empty`` is not a gaming mode. ``discriminate`` grades it as the
        FR-017 smoke floor ("a throwaway empty dir must FAIL") and treats its
        MATRIX substring as OPTIONAL for that reason. An empty submission has no
        authored defect to attribute - it dies at whichever gate the checkpoint
        schedule reaches first, which is a fact about the fixture's ordering.

        MEASURED on ``gp-glide-stamina-cpp`` (2026-08-08): ``empty`` and
        ``no-mesh`` share a substring because the checkpoint-0 visibility gate
        runs before the ability check. Both are correct as authored - ``no-mesh``
        is a behaviorally perfect solve whose ONLY defect is invisibility, so the
        visibility gate is its own gate, and ``empty`` reaches it incidentally.
        ``t2-hud-layout-and-countdown`` records the identical shape for
        ``added-late``. Scoring those as uniqueness violations would assert that
        no variant may ever target a task's FIRST gate, which is not a rule
        anyone holds and which no task could satisfy.

        The exemption is NOT a softening, because nothing is discarded:
          * variant-vs-variant entailment still FAILS here (the real defect);
          * every empty/variant collision is PRINTED by name, so a variant that
            adds no isolation beyond the smoke leg stays visible in the output;
          * ``test_variant_legs_prove_more_than_the_empty_leg`` (check 2b)
            refuses a matrix whose variants ALL collapse onto ``empty``, which
            is the only case where the exemption could hide a real hole.
        """
        for path, (spec, rows, ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                legs = _isolation_rows(rows)
                clashes: list[str] = []
                for i, a in enumerate(legs):
                    for b in legs[i + 1:]:
                        if mo.entails(b.substrings, a.substrings):
                            clashes.append(
                                f"    [{a.label}] is entailed by [{b.label}]: "
                                f"{list(a.substrings)} <= {list(b.substrings)}")
                        elif mo.entails(a.substrings, b.substrings):
                            clashes.append(
                                f"    [{b.label}] is entailed by [{a.label}]: "
                                f"{list(b.substrings)} <= {list(a.substrings)}")

                # The exempted collisions, reported rather than asserted on.
                empty_row = _empty_row(rows)
                if empty_row is not None:
                    shared = [r.label for r in legs
                              if mo.entails(empty_row.substrings, r.substrings)
                              or mo.entails(r.substrings, empty_row.substrings)]
                    if shared:
                        names = ", ".join(shared)
                        print(f"\n[matrix-oracle] {spec.task_id}: variant leg(s) "
                              f"sharing the `empty` leg's substring: "
                              f"{names}. EXEMPT by design (empty is "
                              f"the FR-017 smoke floor and trips whichever gate "
                              f"runs first, not an isolation claim), but each of "
                              f"these proves only that the gate is REACHABLE - "
                              f"the empty leg already proves it fires.")

                _ratchet(self, "unique", spec.task_id, clashes,
                    f"\n{_rel(path)}: negative variant legs that do not isolate "
                    f"- both can be satisfied by one failure, so the matrix "
                    f"proves a count, not a discrimination:\n"
                    + "\n".join(clashes))

    def test_variant_legs_prove_more_than_the_empty_leg(self):
        """CHECK 2b. At least one variant must NOT be entailed by ``empty``.

        This is the price of check 2's ``empty`` exemption, paid in the same
        change. Exempting ``empty`` from the pairwise matrix is right for the
        measured case (one variant legitimately shares the first gate), but it
        would be wrong if it let a whole matrix collapse: if EVERY variant's
        grep is satisfied by the empty submission's own failure, then no leg in
        the file proves anything the FR-017 smoke test did not, and the task
        would read as discriminated on the strength of the smoke leg alone.

        Vacuous by construction where it should be: a task with no ``empty``
        substring recorded, or with no variant legs at all
        (``gp-inventory-stacking`` ships reference+empty only), asserts
        nothing."""
        for path, (spec, rows, _ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                empty_row = _empty_row(rows)
                legs = _isolation_rows(rows)
                if empty_row is None or not legs:
                    continue
                distinct = [r.label for r in legs
                            if not mo.entails(empty_row.substrings, r.substrings)]
                all_labels = ", ".join(r.label for r in legs)
                collapsed = [] if distinct else [
                    f"    every variant leg ({all_labels}) is entailed by "
                    f"[empty] {list(empty_row.substrings)}"]
                _ratchet(
                    self, "empty-floor", spec.task_id, collapsed,
                    f"\n{_rel(path)}: every negative variant leg is satisfied by "
                    f"the SAME failure an empty submission produces, so this "
                    f"matrix re-proves the FR-017 smoke test and demonstrates no "
                    f"discrimination at all. At least one variant must die at a "
                    f"gate the empty submission does not reach.")

    def test_matrix_substrings_are_ascii_only(self):
        """CHECK 3. The 2026-07-21 t2-homing-projectile bug.

        The UE log is written UTF-8 and read back cp1252, so any non-ASCII
        character in a substring becomes mojibake and the grep misses."""
        for path, (spec, rows, _ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                bad: list[str] = []
                for row in _negative_rows(rows):
                    for sub in row.substrings:
                        found = mo.non_ascii(sub)
                        if found:
                            chars = ", ".join(f"U+{ord(c):04X} at {i}"
                                              for i, c in found)
                            bad.append(f"    [{row.label}] {chars}: {sub!r}")
                self.assertEqual(
                    [], bad,
                    f"\n{_rel(path)}: non-ASCII in an expected substring; the "
                    f"cp1252 read-back mangles it and a CORRECT FAIL will be "
                    f"scored wrong-reason:\n" + "\n".join(bad))

    def test_failed_assertions_the_matrix_names_are_ascii_only(self):
        """The same rule on the other side of the grep, and repo law in its own
        right ("assertion messages are ASCII-only").

        A clean cell cannot save a dirty message: the log line the matrix greps
        arrives mojibake'd from the em dash onward. Each finding is annotated
        with whether a row anchors on that message TODAY - an unanchored one is
        a live trap for the next row someone adds to it, not a current break."""
        for path, (spec, rows, ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                anchors = [s for row in _negative_rows(rows) for s in row.substrings]
                bad: list[str] = []
                for msg in ev.failed_messages:
                    found = mo.non_ascii(msg)
                    if not found:
                        continue
                    chars = ", ".join(f"U+{ord(c):04X}" for _i, c in found)
                    anchored = any(a in run for run in mo.literal_runs(msg)
                                   for a in anchors)
                    tag = "ANCHORED BY A ROW" if anchored else "not yet anchored"
                    bad.append(f"    {chars} ({tag}): {msg!r}")
                _ratchet(self, "ascii-assert", spec.task_id, bad,
                    f"\n{_rel(path)}: non-ASCII inside a FinishTest(Failed) "
                    f"message of this task's fixture:\n" + "\n".join(bad))

    def test_reference_row_parses_as_a_pass_row(self):
        """The reference leg must read PASS to `parse_matrix`.

        This is the sharpest available detector for the "ONE parseable row per
        label" trap (documented on t1-third-person-chase-camera): a SECOND
        markdown table further down the file whose first column repeats a label
        silently OVERWRITES the real row, and because that table has no
        Overall/message column the overwrite lands `expect_pass=False` with an
        empty substring tuple. The reference flipping to expect-FAIL is the one
        symptom no amount of careful cell authoring can hide."""
        for path, (spec, rows, _ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                row = rows.get("reference")
                if row is None:
                    continue  # a matrix may legitimately omit the reference leg
                _ratchet(
                    self, "reference-row", spec.task_id,
                    [] if row.expect_pass else ["reference row parses as FAIL"],
                    f"\n{_rel(path)}: the 'reference' row parses as an expected "
                    f"FAIL. Almost always a later, non-matrix table in the same "
                    f"file re-registering the label (parse_matrix keys by label, "
                    f"last row wins) - which also blanks every other row's "
                    f"expected substring.")

    def test_materialized_variants_record_a_named_substring(self):
        """A variant with a committed submission dir but no recorded substring
        is graded on exit code alone - the same "it FAILed, never mind why"
        weakness the named-substring rule exists to remove.

        Rows whose label matches NO on-disk variant dir are reported as parse
        PHANTOMS instead (a stray ``A/B`` cell in a calibration table registers
        as a variant label), because those are a MATRIX-shape defect, not a
        missing assertion."""
        for path, (spec, rows, _ev) in self.loaded.items():
            with self.subTest(task=spec.task_id):
                on_disk = set(discover_variants(path.parent))
                missing: list[str] = []
                phantoms: list[str] = []
                for row in _negative_rows(rows):
                    if row.substrings:
                        continue
                    if row.label in on_disk:
                        missing.append(f"    [{row.label}] (dir exists, no substring)")
                    elif row.label != "empty":
                        phantoms.append(f"    [{row.label}]")
                if phantoms:
                    print(f"\n[matrix-oracle] {spec.task_id}: MATRIX rows that "
                          f"parse as a variant label but have no submission dir "
                          f"(likely a non-matrix table row being read as a leg; "
                          f"the label also OVERWRITES any real row of the same "
                          f"name):\n" + "\n".join(phantoms))
                _ratchet(self, "variant-named", spec.task_id, missing,
                    f"\n{_rel(path)}: committed discrimination variants with no "
                    f"named expected substring:\n" + "\n".join(missing))


class TestOracleMechanics(unittest.TestCase):
    """The oracle's own unit tests. Without these a green suite could just mean
    the extractor found nothing to check."""

    def test_literal_runs_cut_at_placeholders(self):
        self.assertEqual(
            ["granted=", " of "],
            mo.literal_runs("granted=%d of %0.2f"))
        runs = mo.literal_runs("... granted=%d")
        self.assertTrue(any("granted=" in r for r in runs), runs)
        self.assertFalse(
            any("granted=0" in r for r in runs),
            "a value that spans the placeholder must not survive as a run")

    def test_double_percent_is_a_literal_not_a_cut(self):
        self.assertEqual(["100% drained"], mo.literal_runs("100%% drained"))

    def test_only_failed_finishtest_lands_in_the_failed_tier(self):
        src = '''
        void F() {
            FinishTest(EFunctionalTestResult::Failed, TEXT("the gate says no"));
            FinishTest(EFunctionalTestResult::Succeeded, TEXT("all green"));
            UE_LOG(LogTemp, Display, TEXT("a diagnostic"));
        }
        '''
        failed, other = mo.cpp_literal_tiers(src)
        self.assertEqual(["the gate says no"], failed)
        self.assertIn("all green", other)
        self.assertIn("a diagnostic", other)

    def test_adjacent_and_wrapped_literals_concatenate(self):
        src = ('FinishTest(EFunctionalTestResult::Failed, TEXT(\n'
               '  "the character is not visibly "\n'
               '  "represented"));\n')
        failed, _ = mo.cpp_literal_tiers(src)
        self.assertEqual(["the character is not visibly represented"], failed)
        src2 = ('FinishTest(EFunctionalTestResult::Failed, '
                'TEXT("left ") TEXT("right"));')
        self.assertEqual(["left right"], mo.cpp_literal_tiers(src2)[0])

    def test_printf_message_is_extracted_and_cut(self):
        src = ('FinishTest(EFunctionalTestResult::Failed, FString::Printf('
               'TEXT("no ability on the pawn. granted=%d"), Granted));')
        failed, _ = mo.cpp_literal_tiers(src)
        runs = mo.literal_runs(failed[0])
        self.assertEqual(["no ability on the pawn. granted="], runs)

    def test_comments_are_not_mined_for_literals(self):
        src = ('// FinishTest(EFunctionalTestResult::Failed, TEXT("ghost"));\n'
               'FinishTest(EFunctionalTestResult::Failed, TEXT("real"));')
        failed, other = mo.cpp_literal_tiers(src)
        self.assertEqual(["real"], failed)
        self.assertNotIn("ghost", other)

    def test_introspect_folder_composes_a_token(self):
        script = (
            'TOKEN = "BOOM_COMPONENT_MISSING"\n'
            'def _absent(token, names):\n'
            '    return "%s searched=%d names=%s" % (token, len(names), names)\n'
            'def run(names):\n'
            '    return _absent(TOKEN, names)\n'
        )
        runs = [r for t in mo.introspect_templates(script)
                for r in mo.template_runs(t)]
        self.assertTrue(any("BOOM_COMPONENT_MISSING searched=" in r for r in runs),
                        f"composed token not folded; runs={runs}")

    def test_introspect_folder_varies_each_argument_slot(self):
        """A shared helper called with four token stems must yield all four -
        a truncated cartesian product silently yields only the first."""
        script = (
            'def _tag(stem):\n'
            '    return "%s_WRONG_TYPE class=%s expected=%s" % (stem, "a", "b")\n'
            'def run():\n'
            '    _tag("RIG_SKY_ATMOSPHERE")\n'
            '    _tag("RIG_SKY_LIGHT")\n'
            '    _tag("RIG_SUN_LIGHT")\n'
            '    _tag("RIG_HEIGHT_FOG")\n'
        )
        runs = [r for t in mo.introspect_templates(script)
                for r in mo.template_runs(t)]
        self.assertTrue(any(r.startswith("RIG_SUN_LIGHT_WRONG_TYPE class=")
                            for r in runs), f"runs={runs}")

    def test_introspect_folder_pairs_co_indexed_table_columns(self):
        """A table-driven grader must fold CORRELATED tuples, not just row 0.

        THE BUG THIS PINS (found 2026-08-12 by the kp- salvage wave).
        ``_arg_combos`` varied one position at a time off a base tuple, which
        holds every OTHER position at its base — so the only correlated tuple
        it could build was the base itself. For a grader that formats two
        fields of the same table row, that made row 0 read as producible and
        every other row read as MISSING, purely from where it sat in the
        table. CHECK 1 calls MISSING "the oracle's one STRONG verdict ...
        genuinely unbuildable here", so the blind spot presented as certainty
        and would have condemned a sound task.

        The last row is the one that matters: under the old strategy it was
        unreachable at any cap.
        """
        script = (
            'DIR = "/Game/Tasks/demo/Enums"\n'
            'SPECS = (("a", "E_Alpha"), ("b", "E_Beta"),\n'
            '         ("c", "E_Gamma"), ("d", "E_Delta"))\n'
            'def run():\n'
            '    for key, new in SPECS:\n'
            '        pkg = "%s/%s" % (DIR, new)\n'
            '        yield "ENUM_NEW_MISSING_%s path=%s" % (new, pkg)\n'
        )
        runs = [r for t in mo.introspect_templates(script)
                for r in mo.template_runs(t)]
        for name in ("E_Alpha", "E_Beta", "E_Gamma", "E_Delta"):
            want = "ENUM_NEW_MISSING_%s path=/Game/Tasks/demo/Enums/%s" % (name, name)
            self.assertIn(
                want, runs,
                "correlated tuple for %s not folded — a sound task's leg "
                "would read as unbuildable purely from its row index; "
                "runs=%r" % (name, runs))

    def test_introspect_folder_does_not_invent_values(self):
        script = 'def run(n):\n    return "socket=%s" % (n,)\n'
        runs = [r for t in mo.introspect_templates(script)
                for r in mo.template_runs(t)]
        self.assertNotIn("socket=None", runs)
        self.assertIn("socket=", runs)

    def test_entails_is_directional_and_substring_aware(self):
        self.assertTrue(mo.entails(("no mesh on the pawn",), ("no mesh",)))
        self.assertFalse(mo.entails(("no mesh",), ("no mesh on the pawn",)))
        self.assertTrue(mo.entails(("same",), ("same",)))
        self.assertFalse(mo.entails((), ("x",)))
        self.assertFalse(mo.entails(("x",), ()))

    def test_empty_is_the_only_leg_exempt_from_the_uniqueness_matrix(self):
        """The exemption must be EXACTLY one label wide.

        A broader predicate (say, "any leg with no submission dir", or a
        prefix match) would quietly excuse real variants, which is precisely
        the silent weakening the exemption is not allowed to be."""
        self.assertFalse(mo.is_isolation_leg("empty"))
        self.assertEqual("empty", mo.SMOKE_LEG_LABEL)
        for label in ("no-mesh", "added-late", "empty-hands", "emptied",
                      "reference", "Empty", "no-gas"):
            self.assertTrue(mo.is_isolation_leg(label),
                            f"{label!r} must stay in the uniqueness matrix")

    def test_isolation_rows_drops_only_empty(self):
        class _Row:
            def __init__(self, label, substrings):
                self.label = label
                self.substrings = substrings
                self.expect_pass = False

        rows = {
            "reference": _Row("reference", ()),
            "empty": _Row("empty", ("first gate",)),
            "no-mesh": _Row("no-mesh", ("first gate",)),
            "no-gas": _Row("no-gas", ("granted=",)),
            "blank": _Row("blank", ()),
        }
        rows["reference"].expect_pass = True
        self.assertEqual(
            ["no-mesh", "no-gas"], [r.label for r in _isolation_rows(rows)])
        # The empty row is still reachable for the collision REPORT - the
        # exemption hides it from the assertion, never from the reader.
        self.assertIsNotNone(_empty_row(rows))
        self.assertEqual(("first gate",), _empty_row(rows).substrings)

    def test_empty_row_is_none_when_there_is_nothing_to_compare(self):
        class _Row:
            def __init__(self, label, substrings, expect_pass=False):
                self.label = label
                self.substrings = substrings
                self.expect_pass = expect_pass

        self.assertIsNone(_empty_row({}))
        self.assertIsNone(_empty_row({"empty": _Row("empty", ())}))
        self.assertIsNone(
            _empty_row({"empty": _Row("empty", ("x",), expect_pass=True)}))

    def test_every_tier_carries_an_ascii_caveat(self):
        """The finding messages ride into a cp1252 read-back, and a caveat
        nobody can read is a caveat nobody heeds."""
        for tier in (mo.TIER_FAILED, mo.TIER_INTROSPECT, mo.TIER_FIXTURE,
                     mo.TIER_VERDICT, mo.TIER_NONE):
            caveat = mo.tier_caveat(tier)
            self.assertTrue(caveat, tier)
            self.assertEqual([], mo.non_ascii(caveat),
                             f"tier caveat for {tier} is not ASCII: {caveat!r}")
        self.assertIn("unknown provenance tier", mo.tier_caveat("nope"))

    def test_weak_tier_caveats_name_the_specific_weakness(self):
        """Requirements from the I0.4 review, pinned so a future edit cannot
        soften them into "weakly anchored" and lose the meaning."""
        introspect = mo.tier_caveat(mo.TIER_INTROSPECT).lower()
        self.assertIn("flow-insensitive", introspect)
        self.assertIn("not disproven", introspect)
        fixture = mo.tier_caveat(mo.TIER_FIXTURE).lower()
        self.assertIn("in the fixture source", fixture)
        self.assertIn("failure path", fixture)
        # And the one STRONG verdict must still read as strong.
        self.assertIn("no source", mo.tier_caveat(mo.TIER_NONE).lower())

    def test_module_docstring_states_the_asymmetry(self):
        """The docstring is the only place a reader meets this before trusting
        a green, so its absence is a real regression."""
        doc = (mo.__doc__ or "").lower()
        self.assertIn("asymmetry", doc)
        self.assertIn("over-approximation", doc)
        self.assertIn("flow-insensitive", doc)

    def test_non_ascii_finds_the_em_dash(self):
        # The em dashes on the next line are test DATA for the detector, not
        # prose. Every ASSERTION MESSAGE and every diagnostic string this file
        # emits is ASCII on purpose (the cp1252 read-back); the remaining
        # non-ASCII bytes in this file are em dashes in comments, which never
        # reach a log or a grep.
        self.assertEqual([(5, "—")], mo.non_ascii("gate — open"))
        self.assertEqual([], mo.non_ascii("gate - open"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
