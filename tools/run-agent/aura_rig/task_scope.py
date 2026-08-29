"""task_scope — the TASK-SCOPED belt on the deliverable sweep + the
foreign-asset compile-error note.

THE INCIDENT THIS EXISTS FOR (measured 2026-08-07, bench-20260807-015524).
Rep 1 (``cpp/gp-glide-stamina-cpp``) authored
``Content/Tasks/gp-glide-stamina-bp/GA_Glide.uasset`` into the shared graded
scratch and then died EDITOR-GONE — its own deliverable came out EMPTY. Rep 2
was a DIFFERENT task (``cpp/gp-poison-dot-stack-cpp``); it composed a clean
scratch (its ``.cb-staged`` marker proves it), yet that orphan Blueprint
reappeared DURING its drive (it is listed as ``new`` in rep 2's deliverable
diff, so it was absent at the post-compose ``before`` snapshot — a stale
editor's in-memory package re-saved it). ``--submission-from-project`` then
swept the whole writable subtree, the orphan rode into the graded submission,
UE failed to compile it in the poison substrate ("this Blueprint (self) is not
a Character…"), and the automation test returned ``Result={Fail}`` — while
poison's OWN behavior was byte-identical to the committed reference PASS.

A false FAIL charged to a model is the unforgivable failure class, so the
defense is two-layered: ``graded_scratch.reset_agent_writable`` guarantees a
pristine pre-drive scratch (level 1), and THIS module is the belt (level 2) —
it partitions the post-drive diff so a foreign leftover can neither enter the
graded submission nor the saved ``deliverable/``, and it names the symptom in
the L2 log so the next reader sees "contamination" instead of "the model wrote
a broken Blueprint".

THE RULE (and its deliberate conservatism)
------------------------------------------
A swept path is FOREIGN only when ALL of these hold:

 1. it lives under a per-task folder — ``…/Tasks/<owner>/…`` (this covers
    ``Content/Tasks/<id>/``, ``Source/<module>/Tasks/<id>/`` and the OFPA
    mirrors ``Content/__External{Actors,Objects}__/Tasks/<id>/``);
 2. ``<owner>`` is not the GRADED task;
 3. ``<owner>`` is a REAL task id, derived from the spec layout
    (``tasks.bare_task_ids`` → ``tasks/**/task.md``) — never hand-coded, and
    never guessed: an agent-invented folder name is KEPT, because excluding on
    a guess would delete real work;
 4. the path is inside the substrate manifest's ``writable``/``asset_writable``
    allowance and NOT under a ``deny`` prefix. This is the guard against
    masking a genuine sandbox violation: a submission under
    ``Content/Maps/<other>/`` or ``Source/CraftBenchTests/Tasks/<other>/`` is
    the sandbox's business (exit 4), so we hand it through untouched;
 5. the graded task's OWN spec text does not mention ``<owner>`` — a task that
    legitimately targets another task's folder keeps its deliverable.

Everything else is KEPT ("agnostic"): whole ``Source/<module>/`` files, the
shared asset roots (``Content/Blueprints/`` & co.), unknown folders, and every
path we could not classify (a missing/unreadable manifest yields status
``"unverified"`` and excludes NOTHING). The fail-safe direction is always
KEEP — keeping a foreign file merely reproduces the old behavior, while a
wrong exclusion would hide either real work or a real violation.

Pure functions over strings + one filesystem read for the manifest; no editor,
no network, fully unit-testable.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parents[0]), str(_HERE.parents[1] / "verify-single")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sandbox  # noqa: E402  (tools/verify-single — the manifest's owner)
import task_layout  # noqa: E402  (tools/verify-single — the shared classifier)

from . import tasks as _tasks  # noqa: E402

# The path segment that opens a per-task folder in EVERY per-task root
# (Content/Tasks, Source/<module>/Tasks, Content/__ExternalActors__/Tasks, …).
# Content/Maps/<id>/ deliberately has NO such segment — it is a deny prefix, so
# it must reach the sandbox rather than this filter (rule 4 above).
_TASK_SEGMENT = "Tasks"

# The note the grade side prints/records when L2 failed with LogBlueprint
# compile errors for assets outside the graded task's folders. Named, because
# unnamed this cost hours: the verdict said FAIL, the log said "Blueprint",
# and nothing said "these bytes are not the model's".
FOREIGN_COMPILE_NOTE = ("foreign asset compile errors present — suspect "
                        "contamination")

# Asset paths inside a UE log line: ".../Content/Tasks/<id>/Foo.uasset" as well
# as the package form "/Game/Tasks/<id>/Foo". Both separators; the log is UE's,
# so it is Windows-flavored and may be non-ASCII (the incident's compiler text
# was localized) — match on the STRUCTURE, never on the message wording.
_LOG_TASK_DIR_RE = re.compile(
    r"[/\\]Tasks[/\\]([A-Za-z0-9][A-Za-z0-9_-]*)[/\\]")


def _norm(rel) -> str:
    """Project-relative POSIX form of a swept path (the snapshot keys are
    os.sep-joined on Windows)."""
    return str(rel).replace("\\", "/").lstrip("./")


def bare(task_id: str) -> str:
    """'cpp/gp-poison-dot-stack-cpp' → 'gp-poison-dot-stack-cpp'."""
    return task_layout.bare_task_id(task_id)


def owning_task(rel) -> Optional[str]:
    """The per-task folder id that OWNS a path, or None when it is task-agnostic.

    Structural only: the first ``Tasks/<id>/`` pair with at least one more
    segment after it (i.e. ``<id>`` is a directory, not a file). Deliberately
    NOT content-based — ``fairness.classify_deliverable_file`` already covers
    the 'for task <id>' header-marker signature, and a marker in an agent's own
    new file must never cost it its deliverable."""
    parts = _norm(rel).split("/")
    for i, seg in enumerate(parts[:-2]):
        if seg == _TASK_SEGMENT and task_layout.TASK_DIR_RE.match(
                parts[i + 1].lower()):
            return parts[i + 1].lower()
    return None


def _under_any(rel: str, prefixes: Iterable[str]) -> bool:
    """Windows-style case-insensitive prefix test against manifest prefixes
    (which sandbox normalizes to a trailing '/' or an exact file rel-path)."""
    folded = _norm(rel).casefold()
    for pref in prefixes:
        p = _norm(pref).casefold()
        if not p:
            continue
        if folded == p.rstrip("/") or folded.startswith(p.rstrip("/") + "/"):
            return True
    return False


def bare_task_ids(repo: Path) -> frozenset:
    """Every REAL task id, from the spec layout (never hand-coded)."""
    return frozenset(_tasks.bare_task_ids(repo))


def load_manifest(repo: Path, substrate: str):
    """The substrate's AGENT_WRITABLE.json, or None when it is absent/unreadable.

    Read from the REPO substrate on purpose: the composed scratch deliberately
    does NOT carry the manifest (it is verifier-side policy), exactly as
    run_task.py loads it. None disarms the whole belt (status 'unverified') —
    we never classify a path whose policy we could not read."""
    from . import driver
    try:
        path = (Path(repo) / driver.project_rel(substrate, repo=Path(repo))
                / "AGENT_WRITABLE.json")
    except Exception:  # noqa: BLE001 — unknown substrate: disarm, never raise
        return None
    try:
        return sandbox.WritableManifest.load(path)
    except (OSError, ValueError, KeyError):
        return None


@dataclass(frozen=True)
class ForeignPath:
    """One swept path excluded from the submission, with the id that owns it."""

    path: str
    owner: str

    def as_dict(self) -> dict:
        return {"path": self.path, "owner": self.owner}


@dataclass
class Scope:
    """The partitioned sweep. ``status`` is a provenance fact for the summary:
    ``"scoped"`` = the rule ran, ``"unverified"`` = no manifest, nothing
    excluded (and the caller should say so rather than imply a clean sweep)."""

    kept: List[str] = field(default_factory=list)
    foreign: List[ForeignPath] = field(default_factory=list)
    status: str = "scoped"

    @property
    def foreign_paths(self) -> List[str]:
        return [f.path for f in self.foreign]


def classify(rel, *, graded_id: str, known_ids, manifest,
             spec_text: str = "") -> str:
    """'own' | 'foreign' | 'agnostic' for ONE swept path — the rule in the
    module docstring, in the same order (each early return is a KEEP)."""
    owner = owning_task(rel)
    if owner is None:
        return "agnostic"                      # task-agnostic (Source/, shared)
    if owner == bare(graded_id):
        return "own"
    if owner not in known_ids:
        return "agnostic"                      # 3: never exclude on a guess
    if manifest is None:
        return "agnostic"                      # 4: policy unknown → keep
    if _under_any(rel, manifest.deny):
        return "agnostic"                      # 4: the SANDBOX must see this
    if not _under_any(rel, tuple(manifest.writable) + tuple(manifest.asset_writable)):
        return "agnostic"                      # 4: outside the allowance → sandbox
    if spec_text and owner in spec_text:
        return "own"                           # 5: the graded prompt targets it
    return "foreign"


def partition(rels: Sequence[str], *, graded_id: str, repo: Path,
              substrate: str, spec_path: Optional[Path] = None,
              known_ids=None, manifest=None) -> Scope:
    """Split a swept path list into (kept, foreign). Never raises: an
    unreadable spec degrades to no rule-5 keep, a missing manifest to
    ``status='unverified'`` with everything kept."""
    if known_ids is None:
        known_ids = bare_task_ids(repo)
    if manifest is None:
        manifest = load_manifest(repo, substrate)
    spec_text = ""
    if spec_path is not None:
        try:
            spec_text = Path(spec_path).read_text(encoding="utf-8",
                                                  errors="replace")
        except OSError:
            spec_text = ""
    sc = Scope(status="scoped" if manifest is not None else "unverified")
    for rel in rels:
        verdict = classify(rel, graded_id=graded_id, known_ids=known_ids,
                           manifest=manifest, spec_text=spec_text)
        if verdict == "foreign":
            sc.foreign.append(ForeignPath(_norm(rel), owning_task(rel) or ""))
        else:
            sc.kept.append(rel)
    return sc


def foreign_asset_errors(log_text: str, *, graded_id: str,
                         known_ids) -> Optional[dict]:
    """Foreign-asset Blueprint COMPILE errors in an L2 log, or None.

    Scans ``LogBlueprint``+``Error`` lines for a ``Tasks/<owner>/`` asset path
    whose owner is a REAL task id other than the graded one — the exact shape
    of the 2026-08-07 false FAIL. Same conservatism as ``classify``: an
    unknown folder name is ignored, so the note fires on contamination, not on
    an agent's own creatively-named folder."""
    graded = bare(graded_id)
    owners: Dict[str, str] = {}
    for line in (log_text or "").splitlines():
        if "LogBlueprint" not in line or "Error" not in line:
            continue
        for m in _LOG_TASK_DIR_RE.finditer(line):
            owner = m.group(1).lower()
            if owner == graded or owner not in known_ids:
                continue
            owners.setdefault(owner, line.strip()[:400])
    if not owners:
        return None
    return {"note": FOREIGN_COMPILE_NOTE,
            "owners": sorted(owners),
            "samples": [owners[o] for o in sorted(owners)][:5]}


def l2_failed(report: Optional[dict], verdict: Optional[str]) -> bool:
    """Did L2 fail? The report's own L2 status when readable (fail OR error),
    else the run verdict — a FAIL with no parseable report is exactly the case
    where the note is most needed, so the fallback errs toward asking."""
    if isinstance(report, dict):
        layer = (report.get("layers") or {}).get("L2")
        if isinstance(layer, dict) and layer.get("status"):
            return str(layer["status"]).lower() in ("fail", "error")
    return (verdict or "").upper() == "FAIL"


def contamination_note(log_path, *, graded_id: str, repo: Path,
                       report: Optional[dict] = None,
                       verdict: Optional[str] = None,
                       known_ids=None) -> Optional[dict]:
    """The grade-side note: fires ONLY when L2 failed AND the L2 log carries
    foreign-asset compile errors. Returns the summary block, or None."""
    if not l2_failed(report, verdict):
        return None
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if known_ids is None:
        known_ids = bare_task_ids(repo)
    return foreign_asset_errors(text, graded_id=graded_id, known_ids=known_ids)
