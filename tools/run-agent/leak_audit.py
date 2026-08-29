"""Audit one run's transcript for answer-key material.

The fairness stages are preventive; this is the detector behind them, because
this defect class files no incident — a contaminated run looks like an ordinary
PASS. Markers are split by CONFIDENCE so a human can judge a borderline hit
instead of trusting one number:

  park      a path under a parked answer tree. Only reachable if the hide was
            defeated or (pre-2026-08-21) parked in-tree.
  answer    an answer subdir (reference, discrimination, aids, authoring)
            or task.md belonging to THIS RUN'S OWN task. Scoped to the own
            task because a repo-wide Glob returns thousands of paths and a
            single foreign `.../reference/...` entry among them is not this
            cell's answer.
  foreign   the same, for some OTHER task. Exposure, like `park`.
  fixture   verifier fixture BODY text the stub removes, so seeing it means
            something served pre-stub bytes. Scoped to THIS RUN'S OWN task, and
            it must be: the markers used to be three names of the fixture base
            class's public API, which appear in 66 of 117 task specs and 219
            docs because DATASET.md Tier 1 publishes the checkpoint-schedule
            shape for every task on purpose. See `own_fixture_markers`.

Scanned only in tool RESULTS: a model may NAME a path from the prompt, but only
a result proves it read one. `.dll`/`.pdb` hits are dropped — build logs mention
UnrealEditor-CraftBenchTests.dll constantly and are not a read of anything.

A `park` or `foreign` hit ALONE is exposure, not consumption: in practice a
directory listing that showed the park's name. Still a defect — a drive can
follow that signpost into the answer — but not evidence the run read one, so it
warns instead of voiding.

Usage:  py -3 leak_audit.py <run-dir> [--void]     (any Python 3.11+)
Exit 0 = clean, 1 = contaminated, 2 = nothing to audit, 3 = park exposed only.

This file also owns the VOID RECORD — see ``VOID_KEY``. ``--void`` is the rig's
one automated writer of one and leak_audit_sweep delegates here, so the shape
has a single author.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path, PurePath
from typing import Optional

PARK = (".cb-fairness-hidden__", "cb-fairness-park")
ANSWER_DIRS = ("/reference/", "/discrimination/", "/aids/",
               "/authoring/")
BINARY = (".dll", ".pdb", ".lib", ".obj")

#: A void's one machine-readable home is the CELL'S OWN result.json: the report
#: travels with the cell and a sweep-level ledger does not.
#:
#: sweep_report is the ONLY reader today. Other aggregators and
#: sweep_mcp_lanes.sh's cell_done still decide from ``overall`` alone, so a void
#: that leaves ``overall`` graded is invisible to both — every writer must pair
#: one with a non-graded ``overall`` until those two are widened.
VOID_KEY = "void"


def read_void(record: dict) -> dict | None:
    """The void stamped on this cell, or None. A reinstatement wins.

    Also accepts the legacy flat ``voided_reason``/``voided_verdict`` pair, so
    records already carrying it read as void with no migration.
    """
    if (record.get("reinstated") or {}).get("to"):
        return None
    v = record.get(VOID_KEY)
    if isinstance(v, dict) and v.get("reason"):
        return v
    if record.get("voided_reason"):
        return {"reason": record["voided_reason"],
                "verdict_before": record.get("voided_verdict")}
    return None


#: The verdicts that MEAN "this cell was voided". A record carrying one of them
#: must also carry a reason, or nobody can review the decision either way.
VOID_VERDICTS = ("FAIRNESS-BREACH",)


def unauditable_void(record: dict) -> Optional[str]:
    """Why this record's void cannot be reviewed, or None when it is fine.

    THE CASE, found on the build machine 2026-08-25 in the 127-cell MCP sweep:
    ``20260823-040909-gp-glide-stamina-bp-aura-mcp-claude-sonnet-5`` carries
    ``overall = FAIRNESS-BREACH`` with ``voided_reason`` and ``voided_verdict``
    both ``null``, against $8.33 of spend. Every writer in the rig pairs a void
    with its reason (``leak_audit.main`` and ``run.py``'s ``void_reason`` branch
    both go through :func:`stamp_void`), so this one did not come from either —
    and the consequence is that the cell is neither recoverable nor
    confirmable. The verdict says a breach happened; nothing says which, so it
    cannot be triaged the way the four false positives from the retired
    fixture-marker set were.

    Worse, it reads as CLEAN to :func:`read_void`, which returns None when the
    reason is empty. So the cell is simultaneously "breached" to anything
    reading ``overall`` and "not voided" to anything reading the void record —
    and ``sweep_report.is_graded`` asks both. It lands outside the pass rate on
    the verdict test alone, which is the right answer by luck rather than by
    evidence.

    Diagnostic only: this never changes a verdict. It exists so a review can SEE
    the contradiction instead of inheriting it.
    """
    overall = str(record.get("overall") or "")
    if overall not in VOID_VERDICTS:
        return None
    if read_void(record) is not None:
        return None
    return (f"overall is {overall} but no void reason is recorded "
            f"(void={record.get(VOID_KEY)!r}, "
            f"voided_reason={record.get('voided_reason')!r}) — the decision "
            f"cannot be reviewed, so the cell is neither recoverable nor "
            f"confirmable")


def stamp_void(record: dict, reason: str, by: str = "leak_audit") -> bool:
    """Write the void into ``record`` in place. False if it already carries one.

    Deliberately does NOT touch ``overall`` — what it should become depends on
    WHY the cell was voided, so the caller decides.
    """
    if read_void(record) is not None:
        return False
    record[VOID_KEY] = {
        "reason": reason,
        "at": datetime.datetime.now(datetime.timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by": by,
        "verdict_before": record.get("overall"),
    }
    return True


#: RETIRED 2026-08-24. This was
#: ``("setcheckpointschedule", "oncheckpoint(", "acraftbenchfunctionaltest")`` —
#: three names of the fixture base class's PUBLIC API — and it was a
#: false-positive machine rather than a detector. Measured on this tree:
#:
#:   * **66 of 117 task specs** carry one of those strings in their own body,
#:     and so do **219 docs**. `DATASET.md` Tier 1 publishes "the verification
#:     method ... checkpoint schedule shape" for EVERY task on purpose, so the
#:     tier voided cells for reading material the benchmark deliberately ships.
#:   * `Intermediate/Build/**/UHT/*.generated.h` carries the base class name and
#:     is NOT covered by the hide (`fairness` stubs `Source/CraftBenchTests/`),
#:     so a warm workdir tripped it too — and those files hold UE reflection
#:     boilerplate, no assertion names and no gate values.
#:
#: A later review made this urgent rather than cosmetic: `run._answer_key_leak` now
#: gates PRE-GRADE on the `fixture` class alone, so a false hit no longer just
#: annotates a finished run — it destroys a graded cell before the build. That
#: is a denominator opt-out a drive can take with one `Read`, which is the one
#: thing the harness must never offer. The staged-workspace design reached the
#: same conclusion independently (docs/design/2026-08-23-…-fairness.md §5.3) and
#: made re-scoping a precondition of the MCP-lane migration, because the compose
#: KEEPS the base classes an agent may then legitimately read.
#:
#: Two narrower repairs were measured and rejected rather than assumed:
#:   * a different GLOBAL marker — every candidate that appears in fixture
#:     bodies also appears in the specs or the playbook, because Tier 1
#:     documents the fixture-authoring API on purpose.
#:     `finishtest(efunctionaltestresult`: 88 bodies, but 3 specs + 2 docs.
#:   * marker AND a `Source/CraftBenchTests/` path — 48 of the 66 specs contain
#:     BOTH (a spec must name what is denied), while only 31 of 89 fixture
#:     bodies contain their own path. Strictly worse: the same false positives
#:     for a third of the detection.
#:
#: What replaces it is per-run and derived from the task's own verifier —
#: see :func:`own_fixture_markers`.
FIXTURE: tuple = ()

#: A marker must be at least this long. SWEPT, not guessed (2026-08-24), against
#: 9.6 MB of agent-visible substrate text INCLUDING the base classes the staged
#: compose keeps:
#:
#:     floor 16 -> 100/117 tasks carry a marker, 1 false positive
#:     floor 20 ->  99/117,                      1 false positive
#:     floor 24 ->  98/117,                      0
#:     floor 28 ->  97/117,                      0
#:
#: 24 is the shortest floor with none. The one survivor at 20 was
#: `with no mesh assigned` — generic enough to appear in ordinary substrate
#: source, which is exactly the shape a marker must not have.
MARKER_MIN_LEN = 24

#: Spelled by codepoint: a literal here is what broke the first attempt.
_BACKSLASH = chr(92)

#: Fixture sources the staged compose deliberately KEEPS, so an agent may read
#: them legitimately. Text they contain can never be evidence, no matter which
#: MATRIX row or fixture body also names it — several tasks inherit their
#: "not visibly represented" assertion straight from the base class, and 10 of
#: them would otherwise void on a legal read.
BASE_FIXTURE_NAMES = (
    "CraftBenchFunctionalTest.h", "CraftBenchFunctionalTest.cpp",
    "CraftBenchPawnFunctionalTest.h", "CraftBenchPawnFunctionalTest.cpp",
    "RenderProbeFunctionalTest.h", "RenderProbeFunctionalTest.cpp",
)

_FINISHTEST_FAILED_RE = re.compile(
    r"FinishTest\s*\(\s*EFunctionalTestResult::Failed\s*,(.{0,4000}?)\)\s*;", re.S)
_TEXT_LITERAL_RE = re.compile(r'TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)')


def _spec_path_for(run_dir: Path, spec_path=None):
    """The task spec this run was driven from, or None.

    ``spec_path`` is what the PRE-GRADE caller has (``args.task``); the post-hoc
    CLI has result.json instead. Both are supported because the gate now runs at
    both points and must not answer differently at the two.
    """
    if spec_path:
        return _anchor(Path(str(spec_path)))
    try:
        spec = json.loads(
            (run_dir / "result.json").read_text(encoding="utf-8")).get("task") or ""
    except (OSError, ValueError):
        return None
    return _anchor(Path(str(spec).replace("\\", "/"))) if spec else None


def _anchor(spec: Path) -> Path:
    """Resolve a RELATIVE spec path against this file's own repo, not the cwd.

    ``cb`` happens to run from the repo root today, so ``Path("tasks/bp/x/
    task.md")`` resolves. "Happens to" is the whole problem: from any other cwd
    the spec would be missing, the markers would come back empty, and the
    fixture tier would silently detect NOTHING — a detector that reports clean
    because it could not look. `run.py` passes ``args.task`` through verbatim,
    and nothing normalises it.
    """
    if spec.is_absolute() or spec.exists():
        return spec
    here = Path(__file__).resolve().parents[2] / spec
    return here if here.exists() else spec


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ""


#: Process-local memo for the two repo-wide reads below.
#:
#: WHY CACHING IS SOUND HERE, and it is worth stating rather than assuming: the
#: graded substrate is materialised from git HEAD BEFORE this process starts and
#: is not written during a run, so `UE-projects/**` is invariant for the life of
#: an interpreter. Keys are the resolved repo path, so a test that builds a
#: throwaway tree gets its own entry rather than another tree's answer.
#:
#: WHY IT MATTERS: `audit()` derives markers per RUN, and both reads glob the
#: substrate. Measured 2026-08-25 on this box: 35 ms per uncached call, ~10 s for
#: the corpus-wide guard test alone — and the build machine reported the merged suite at
#: roughly 6x this box's wall-clock, which is the same work on slower I/O. A
#: 127-run `leak_audit_sweep` paid it 127 times over.
_BASE_TEXT_CACHE: dict = {}
_FIXTURE_LIT_CACHE: dict = {}


def _base_fixture_text(repo: Path) -> str:
    """The base-class allowlist text — the fixture sources the staged compose
    KEEPS, which an agent may therefore read legitimately. Memoised per repo."""
    key = str(repo.resolve())
    hit = _BASE_TEXT_CACHE.get(key)
    if hit is None:
        hit = "\n".join(
            _read(p) for name in BASE_FIXTURE_NAMES
            for p in repo.glob("UE-projects/*/Source/CraftBenchTests/**/" + name))
        _BASE_TEXT_CACHE[key] = hit
    return hit


def _fixture_fail_literals(repo: Path, cls: str) -> list:
    """``TEXT("…")`` literals inside one fixture class's Failed FinishTest calls.

    Memoised per (repo, class): a task's fixture is read once however many runs
    of that task are audited in the same process.
    """
    key = (str(repo.resolve()), cls)
    hit = _FIXTURE_LIT_CACHE.get(key)
    if hit is None:
        hit = []
        for src in repo.glob(
                "UE-projects/*/Source/CraftBenchTests/**/%s.cpp" % cls):
            # CASE-PRESERVED on purpose. `_read` lowercases (every marker is
            # compared against a lowercased transcript line), and both regexes
            # below are case-SENSITIVE UE spellings -- `FinishTest`,
            # `EFunctionalTestResult::Failed`, `TEXT(`. Feeding them lowercased
            # text matched NOTHING, so this whole half was dead from the day it
            # shipped (2026-08-24) and every marker came from the MATRIX alone.
            # Measured on AdditemStackFunctionalTest.cpp: 10 blocks raw, 0
            # lowercased. The literals are lowercased at the end of
            # `own_fixture_markers`, which is where the comparison happens.
            try:
                raw = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for block in _FINISHTEST_FAILED_RE.findall(raw):
                hit += _TEXT_LITERAL_RE.findall(block)
        _FIXTURE_LIT_CACHE[key] = hit
    return list(hit)


def own_fixture_markers(run_dir: Path, spec_path=None) -> tuple:
    """Text that lives ONLY in this task's verifier, as fixture-leak markers.

    Two sources, unioned: the FAIL substrings the task's own
    ``discrimination/MATRIX.md`` names, and the ``TEXT("…")`` literals inside its
    own fixture's ``FinishTest(EFunctionalTestResult::Failed, …)`` calls. The
    first is what `discriminate` matches on; the second is literally "fixture
    BODY text the stub removes", which is what the `fixture` tier has always
    claimed to mean.

    Then subtracted, because a marker the agent may legitimately have READ is
    not evidence of anything:

      * the base-class allowlist (:data:`BASE_FIXTURE_NAMES`) — the staged
        compose keeps those files, and 10 tasks inherit an assertion string from
        them;
      * this run's own ``prompt.md``, so nothing the harness itself handed the
        agent can void the cell;
      * anything shorter than :data:`MARKER_MIN_LEN`.

    Scoped to the run's OWN task for the same reason the `answer` tier is: a
    repo-wide marker set turns one foreign string into this cell's breach, and
    re-adjudicating the 2026-08-22 sweep that way reinstated a cell whose only
    answer paths belonged to another task.

    Returns EMPTY whenever it cannot answer — no spec, no repo, unparseable
    MATRIX. The tier then detects nothing, which is the correct failure
    direction: an unreaped leak costs one contaminated cell that the post-hoc
    sweep still catches, while a blind detector that VOIDS destroys good cells
    and cannot be told apart from a working one.
    """
    spec = _spec_path_for(run_dir, spec_path)
    if spec is None:
        return ()
    task_dir = spec.parent
    # <repo>/tasks/<set>/<id>/task.md — anchored on the `tasks` segment rather
        # than a parents[] count, so a relative --task still resolves.
    repo = None
    for anc in task_dir.parents:
        if anc.name == "tasks":
            repo = anc.parent
            break
    if repo is None:
        return ()

    cand: list = []
    matrix = task_dir / "discrimination" / "MATRIX.md"
    if matrix.is_file():
        try:
            vs = str(Path(__file__).resolve().parent)
            if vs not in sys.path:
                sys.path.insert(0, vs)
            from aura_rig.discriminate import parse_matrix  # the ONE parser
            for row in parse_matrix(_read(matrix)).values():
                cand += [str(s) for s in (getattr(row, "substrings", ()) or ())]
        except Exception:
            pass

    for cls in _fixture_classes(spec, repo):
        cand += _fixture_fail_literals(repo, cls)

    if not cand:
        return ()
    excluded = _base_fixture_text(repo) + "\n" + _read(run_dir / "prompt.md")
    out = []
    for c in cand:
        c = str(c).strip().lower()
        if len(c) < MARKER_MIN_LEN or c in excluded:
            continue
        # A marker carrying a quote or a backslash can NEVER match. `audit`
        # scans the raw JSONL line and folds every backslash to `/` so one
        # marker set covers both path flavours, so a transcript's `\"` arrives
        # as `/"` and the marker's bare `"` misses it. Several L2I introspect
        # payloads are JSON fragments and land here for exactly that reason.
        # Dropping them costs ONE task of coverage out of 93 (measured) and buys
        # the guarantee that every marker retained is one that can actually
        # fire — a marker that cannot is indistinguishable from a clean repo.
        if '"' in c or _BACKSLASH in c:
            continue
        out.append(c)
    return tuple(dict.fromkeys(out))


def _fixture_classes(spec: Path, repo: Path) -> tuple:
    """This task's L2 fixture class names, via verify-single's spec parser.

    The same sys.path bridge `run.derive_substrate_root` uses. Empty on any
    failure, and empty is CORRECT for the 22 specs that declare no L2 fixture at
    all — those keep only their MATRIX substrings.
    """
    try:
        vs = str(repo / "tools" / "verify-single")
        if vs not in sys.path:
            sys.path.insert(0, vs)
        import spec as _spec  # noqa: E402  (tools/verify-single — THE parser)
        parsed = _spec.parse_task_file(spec)
    except Exception:
        return ()
    out = []
    for f in (getattr(parsed, "fixtures", ()) or ()):
        cls = str(getattr(f, "test_class", "") or "").strip()
        if cls.startswith("A"):
            cls = cls[1:]
        if cls:
            out.append(cls)
    return tuple(dict.fromkeys(out))


def own_task(run_dir: Path) -> str:
    """The task id this run was graded on, from its own result.json."""
    rj = run_dir / "result.json"
    try:
        spec = json.loads(rj.read_text(encoding="utf-8")).get("task") or ""
    except (OSError, ValueError):
        return ""
    return PurePath(spec.replace("\\", "/")).parent.name.lower()


#: Paths under ANOTHER cell's run dir that carry a finished answer. A peer dir
#: NAME appearing in a listing is exposure; reaching into one of these is
#: consumption, which is why only these two qualify.
#: NARROWED after a false positive, measured the same day it was written: a
#: `find` listing in one cell surfaced a peer's `/verifier_out/` and
#: `/preview/pie_l2.log` paths, and a tier that voided on those would have
#: destroyed a legitimate FAIL for reading a directory listing. verifier_out is
#: grading OUTPUT, not the answer, and the fixture source it derives from is
#: already the `fixture` tier's job. What is left is the two paths that hold a
#: finished ANSWER and nothing else.
PEER_ANSWER_PARTS = ("/submission/", "/live_backup/")
#: `runs/<lane>/<YYYYMMDD-HHMMSS>-...`, on the already-folded lowercase line.
_PEER_RE = re.compile(r"/runs/[a-z0-9._-]+/(\d{8}-\d{6})-")


def peer_reach(low: str, own_stamp: str) -> bool:
    """Did this tool_result reach into ANOTHER cell's finished work?

    THE HOLE THIS CLOSES, measured 2026-08-26. The agent runs under
    ``--permission-mode bypassPermissions``, which means ``--add-dir`` and the
    deliberately "neutral cwd" are HINTS, not boundaries -- the process can read
    anywhere on the box. `runs/` therefore sits wide open, and one cell walked
    straight into it:

        line 6    Glob C:/cb/<other-worktree>       **/*Mud*
        line 99   Glob C:/cb/<other-worktree>/runs  **/BP_MudHero.uasset
        line 120  Glob .../20260826-033551-.../submission  **/*

    That is a deliberate search of other cells for the answer, and it read five
    earlier cells' submissions for the same task. No tier named it: `answer` and
    `foreign` scope to the TASK tree, `park` to the fairness park. The cell was
    voided only because it ALSO read the relocated fixture, which was luck.

    The exposure grows monotonically through a block -- the later a cell runs,
    the more finished answers sit next to it -- so an undetected version of this
    biases every model that happens to be scheduled late.

    A peer dir NAME in a listing is not enough: `PEER_ANSWER_PARTS` requires the
    line to reach into the answer itself. Intent is not consulted, for the same
    reason the `answer` tier does not consult it -- the material reached the
    agent's context either way.
    """
    if not own_stamp:
        return False
    stamps = {m.group(1) for m in _PEER_RE.finditer(low)} - {own_stamp}
    if len(stamps) != 1:
        # A LISTING, not a read. You can only read one file at a time, so a line
        # naming many peers is an enumeration -- exposure, not consumption. This
        # is not a guess: measured on the three cells that touched peers at all,
        # the separation is total. The real reader's reads are 1 stamp / 1-13 KB
        # each; the cell that only ran `find` has exactly ONE such line carrying
        # 50 stamps and 33 KB. Voiding on the wide lines would have destroyed a
        # legitimate FAIL for reading a directory listing -- caught the same day
        # this tier was written, by checking the one cell it newly accused.
        return False
    return any(part in low for part in PEER_ANSWER_PARTS)


def audit(run_dir: Path, spec_path=None) -> dict:
    """Marker hits per confidence class, ``{kind: [transcript line numbers]}``.

    ``spec_path`` is the task spec, needed only by the ``fixture`` tier and only
    because the PRE-GRADE caller runs before result.json exists. Omit it and the
    post-hoc path reads it from result.json instead; omit it where neither is
    available and the fixture tier detects nothing, which is the correct failure
    direction (see :func:`own_fixture_markers`).
    """
    t = run_dir / "agent_transcript.jsonl"
    if not t.is_file():
        return {}
    mine = own_task(run_dir)
    own_stamp = run_dir.name[:15] if len(run_dir.name) >= 15 else ""
    fixture_marks = own_fixture_markers(run_dir, spec_path)
    # No id to scope with -> every answer path counts, the pre-scoping
    # behaviour. Losing a good cell beats banking a contaminated one.
    own_marks = ([f"/{mine}{m}" for m in ANSWER_DIRS] + [f"/{mine}/task.md"]
                 if mine else list(ANSWER_DIRS))
    hits: dict = {}
    with t.open(encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            if '"tool_result"' not in line and "toolUseResult" not in line:
                continue
            # JSON-escaped Windows paths arrive as C:\\Users\\...; fold every
            # separator to '/' so one marker set matches both path flavours.
            low = line.lower().replace('\\\\', '/').replace('\\', '/')
            while '//' in low:
                low = low.replace('//', '/')
            if peer_reach(low, own_stamp):
                hits.setdefault("peer", []).append(n)
            for kind, marks in (("park", PARK), ("answer", own_marks),
                                ("foreign", ANSWER_DIRS),
                                ("fixture", fixture_marks)):
                for m in marks:
                    if m not in low:
                        continue
                    i = low.find(m)
                    if any(b in low[max(0, i - 120):i + 120] for b in BINARY):
                        continue
                    hits.setdefault(kind, []).append(n)
                    break
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--void", action="store_true",
                    help="stamp the void into result.json and set its verdict "
                         "to FAIRNESS-BREACH")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir)
    hits = audit(run_dir)
    if not hits:
        return 0 if (run_dir / "agent_transcript.jsonl").is_file() else 2

    summary = ", ".join(f"{k}x{len(v)} (first line {v[0]})"
                        for k, v in sorted(hits.items()))
    # `peer` voids: another cell's finished submission is an answer, and a cell
    # that read one is not a measurement of the model.
    consumed = bool(hits.keys() & {"answer", "fixture", "peer"})
    print(f"{'LEAK' if consumed else 'EXPOSED'}: {run_dir.name} — {summary}",
          file=sys.stderr)
    if not consumed:
        return 3
    rj = run_dir / "result.json"
    if a.void and rj.is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from adapters.base import VERDICT_FAIRNESS_BREACH
        r = json.loads(rj.read_text(encoding="utf-8"))
        if stamp_void(r, f"fairness breach — leak_audit: {summary}"):
            prior = r[VOID_KEY]["verdict_before"]
            r["overall"] = VERDICT_FAIRNESS_BREACH
            rj.write_text(json.dumps(r, indent=2), encoding="utf-8")
            print(f"      voided {prior} -> FAIRNESS-BREACH", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
