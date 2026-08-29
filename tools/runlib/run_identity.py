r"""run_identity.py -- THE answer to "given a run record, which task is this?".

ONE implementation. Every aggregator that reads run records imports it and
DELEGATES; nobody re-derives a task id or a basket from a run field. Import it,
do not copy it: a rename here must break the readers loudly (ImportError), which
is the only shape of coupling that has held in this repo.

WHY THIS FILE EXISTS (measured 2026-08-19, before the fix, over the 80
``result.json`` under ``C:/cb/bench-tree/runs`` -- all 80 carry an ABSOLUTE
WINDOWS path in ``task``, e.g.
``C:\cb\bench-tree\tasks\bp\gp-glide-stamina-bp\task.md``):

    tools/compare/compare_products.py:106  Path(task).stem   ->  1 distinct id
                                    (every path ends in ``task.md``, so every
                                    run in the corpus was the task "task")
    tools/dashboard/collect.py:433  PurePosixPath(...).stem  -> 13 distinct ids,
                                    each spelled as a whole Windows path with
                                    ``.md`` shaved off -- 0 of 13 joined to the
                                    task tree, so ``coverage_gaps`` reported
                                    72 of 72 tasks unattempted.

Three implementations, three answers, same bytes. None of them failed a run;
they made the NUMBERS wrong quietly, which is worse.

TWO WRITER SHAPES, BOTH MANDATORY. There are two writers and neither may be
changed, so the reader accepts both:

  * ``tools/run-agent/run.py`` writes ``result.json`` with ``"task"`` -- a
    filesystem path to the spec (absolute or repo-relative; Windows or POSIX
    separators; folder form ``.../<id>/task.md`` or legacy flat ``.../<id>.md``).
  * ``tools/run-agent/aura_rig/run_graded.py`` writes ``summary.json`` with
    ``"task_id"`` and NO ``"task"`` key at all (three sites: lines 1105, 1386,
    1682) -- a BARE id, or a set-qualified ``<set>/<id>``, exactly as the
    operator typed it on the command line.

FAIL CLOSED ON THE BASKET. The pre-fix private ``_basket_of("")`` spelling did not
merely lose the basket, it returned a CONFIDENT WRONG one: an empty task field
produced an empty id, and the probe ``(REPO/"tasks"/b/"").is_dir()`` is TRUE for
the first basket because ``Path("tasks/cpp") / "" == Path("tasks/cpp")``, an
existing directory. Every aura-product run therefore came out
``task_id='unknown', basket='cpp'`` -- and since cells key on
(task_id, arm, model, basket), that arm's whole epoch folded into ONE cell.
Here an unanswerable basket is ``UNKNOWN_BASKET`` and it is never coerced into a
real one; ``basket_order()`` exists so the readers can SHOW that row instead of
dropping it, because an invisible gap reads as "no runs" and is just a quieter
wrong number.

WHAT THIS DELIBERATELY DOES NOT DO:
  * It never guesses the task from the run DIRECTORY name. Real dir names look
    like ``20260818-163023-gp-glide-stamina-bp-aura-mcp-claude-sonnet-5``: the
    task id and the model slug are joined by the same ``-`` that appears inside
    both, so any split is a guess. A check that cannot tell "no" from "could not
    tell" is not a check.
  * It does not re-implement the harness's id disambiguation
    (``aura_rig/tasks.resolve_task_path``: root-wins, folder-form-wins). It
    cannot IMPORT it either -- these readers are deliberately stdlib-only and
    outside the ``run-agent`` package, and ``aura_rig`` is pip-installed ``-e``
    from a DIFFERENT worktree on this box, so an import would silently resolve
    against another tree's ``tasks/``. So the tree probe here answers only the
    narrower question it can answer without policy: "does exactly ONE set dir
    under ``tasks/`` hold a spec for this id?" -- and refuses (UNKNOWN) on zero
    or on ambiguity, which is what ``resolve_task_path`` also does on ambiguity.

Stdlib only, read-only, no repo imports -- every consumer is stdlib-only too.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping, NamedTuple, Optional, Sequence

#: The three agent-written surfaces results are reported over, in table-row order.
#: A set outside this tuple (``tasks/craftbench-public/``, 22 task dirs on
#: 2026-08-19) is returned VERBATIM when a record names it -- never folded into
#: one of the three, never dropped. ``basket_order()`` places it after these.
KNOWN_BASKETS = ("cpp", "bp", "python")

#: Sentinels. Deliberately loud and identical in every reader's output: a table
#: cell reading "UNKNOWN" is a visible gap; "cpp" or "other" is a claim.
UNKNOWN_TASK_ID = "UNKNOWN"
UNKNOWN_BASKET = "UNKNOWN"

#: Record fields that can name the task, in the order they are trusted. ``task``
#: is first because it carries the basket in its path; ``task_id`` cannot.
TASK_FIELDS = ("task", "task_id")

_SPEC_NAME = "task.md"

#: Components that are never a task id. ``tasks`` guards a record whose field is
#: just the tree root; the dot forms guard a relative path; ``task.md`` guards a
#: field that is the bare spec filename with nothing to identify it.
_NOT_AN_ID = frozenset({"", ".", "..", "tasks", _SPEC_NAME})


class TaskIdentity(NamedTuple):
    """What a run record says about which task it graded.

    ``source`` names the record field that answered ("task", "task_id", or
    "none"), so a caller can tell "the record said X" from "no field said
    anything" without re-parsing.
    """

    task_id: str
    basket: str
    source: str

    @property
    def known(self) -> bool:
        return self.task_id != UNKNOWN_TASK_ID

    @property
    def basket_known(self) -> bool:
        return self.basket != UNKNOWN_BASKET


#: The one "we could not tell" value.
UNIDENTIFIED = TaskIdentity(UNKNOWN_TASK_ID, UNKNOWN_BASKET, "none")


# --------------------------------------------------------------------------- parsing
def _components(value: object) -> List[str]:
    r"""Split a task locator into path components, extension already resolved.

    Handles every shape the two writers emit, with one rule each::

        C:\a\tasks\bp\x\task.md  -> [C:, a, tasks, bp, x]   (folder form)
        /home/a/tasks/bp/x/task.md -> [home, a, tasks, bp, x]  (same, POSIX)
        tasks/cpp/x.md           -> [tasks, cpp, x]         (legacy flat)
        bp/x                     -> [bp, x]                 (set-qualified id)
        x                        -> [x]                     (bare id)

    Both separators are normalised before splitting, so a Windows path and the
    POSIX spelling of the same task give the SAME components -- that identity is
    the whole point (the dashboard's ``PurePosixPath`` never split a Windows path
    at all, which is how one task became 13 unjoinable full-path ids).
    """
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return []
    parts = [p for p in text.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts:
        return []
    last = parts[-1]
    if last.lower() == _SPEC_NAME:
        parts.pop()                      # folder form: the id is the parent dir
    elif last.lower().endswith(".md"):
        parts[-1] = last[:-3]            # legacy flat form: the id is the stem
    return parts


def _set_dirs(repo_root: Path) -> List[Path]:
    tasks = Path(repo_root) / "tasks"
    if not tasks.is_dir():
        return []
    return sorted((p for p in tasks.iterdir() if p.is_dir()), key=lambda p: p.name)


def _spec_in_set(set_dir: Path, task_id: str) -> Optional[Path]:
    """The spec file for ``task_id`` inside one set dir, or None.

    Folder form first, then legacy flat -- the same precedence
    ``aura_rig/tasks.resolve_task_candidates`` applies within a set. ``task_id``
    is validated by every caller before it gets here, so this never joins an
    EMPTY component: that empty join is exactly the bug this module ends.
    """
    folder = set_dir / task_id / _SPEC_NAME
    if folder.is_file():
        return folder
    flat = set_dir / f"{task_id}.md"
    if flat.is_file():
        return flat
    return None


#: The agent-written SURFACE, which is not the same question as the basket.
#: The basket answers "which folder holds this spec"; the surface answers "what
#: did the agent write". They agreed as long as every pair was split across
#: baskets, and stopped agreeing the moment a set keyed on DISCLOSURE
#: (tasks/craftbench-public/) held tasks of both surfaces. Deriving the reported
#: surface column from the folder then reports a set name where a surface belongs
#: -- or worse, folds it into "cpp", which is the failure this module's
#: UNKNOWN_BASKET sentinels exist to make loud.
#:
#: The id is the stronger signal and always has been: the -cpp/-bp suffix
#: convention (2026-08-06 owner rename) is what makes a pair a pair, and it
#: travels with the spec no matter which folder it sits in.
_SURFACE_SUFFIXES = (("-bp", "bp"), ("-cpp", "cpp"))


def surface_of(task_id: object, basket: object = None) -> str:
    """The agent-written surface for a task: bp / cpp / python, else UNKNOWN.

    The id's surface suffix WINS over the basket, so moving a spec between sets
    can never silently relabel a measured run. Falls back to the basket only when
    the id carries no suffix, and only when that basket is one of the three
    reported surfaces -- a set name is never returned as a surface.
    """
    tid = str(task_id or "").strip().lower()
    if tid and tid != UNKNOWN_TASK_ID.lower():
        tid = tid.replace("\\", "/").rsplit("/", 1)[-1]
        for suffix, surface in _SURFACE_SUFFIXES:
            if tid.endswith(suffix):
                return surface
    b = str(basket or "").strip().lower()
    if b in KNOWN_BASKETS:
        return b
    return UNKNOWN_BASKET


def pair_base(task_id: object) -> str:
    """A task id with its SURFACE SUFFIX removed: the identity its pair SHARES.

    ``t1-mud-wade-bp`` and ``t1-mud-wade-cpp`` both return ``t1-mud-wade``. An id
    with no surface suffix returns itself, lowercased and stripped of any set
    prefix, so this is safe to call on anything.

    WHY IT EXISTS (measured 2026-08-22, and it had silently broken three tasks).
    ``task_layout.stage_per_task_dirs_active_only`` deletes every per-task
    directory whose name is not the ACTIVE task id, comparing by exact equality.
    When the surface rename gave the ids their ``-bp``/``-cpp`` suffixes, the
    directories the pair SHARES kept their old names -- so for
    ``t1-mud-wade-bp`` the staging deleted:

      * ``Content/Tasks/t1-mud-wade/``, which holds the
        SUPPLIED animation clip the prompt orders the agent to play, and
      * ``Source/ThirdPerson/Tasks/t1-mud-wade-cpp/``,
        which holds the PARENT CLASS the Blueprint has to derive from.

    Both legs lost the clip, because neither leg's id equals the unsuffixed
    directory name -- so the ``-cpp`` leg was broken too, and nobody noticed
    because the pair had never been graded.

    Sharing is the DEFINITION of a pair, so keeping every directory whose pair
    base matches is the semantically right rule rather than a workaround. It does
    mean a ``-bp`` run can see a ``<base>-cpp`` content directory: that is not a
    leak, because per-task substrate content is SUPPLIED material and an answer
    never lives in the substrate (references live under ``tasks/<set>/<id>/``,
    which the repo-level hide parks outright).
    """
    tid = str(task_id or "").strip().lower()
    tid = tid.replace("\\", "/").rsplit("/", 1)[-1]
    for suffix, _surface in _SURFACE_SUFFIXES:
        if tid.endswith(suffix):
            return tid[: -len(suffix)]
    return tid


def basket_from_tree(task_id: str, repo_root: object) -> str:
    """The set dir that holds ``task_id``, or ``UNKNOWN_BASKET``.

    UNIQUE match or refuse. Zero matches (an id from another tree, or a retired
    task) and >1 match (an id defined in two sets) both yield UNKNOWN: guessing
    on ambiguity is how a wrong basket gets read as fact. No caching -- the probe
    is at most (#sets x 2) stat calls, and a cache would go stale against a tree
    a test builds after the first lookup.
    """
    if not task_id or task_id == UNKNOWN_TASK_ID or repo_root is None:
        return UNKNOWN_BASKET
    hits = [d.name for d in _set_dirs(Path(repo_root)) if _spec_in_set(d, task_id)]
    return hits[0] if len(hits) == 1 else UNKNOWN_BASKET


def _basket_from_components(parts: Sequence[str], repo_root: object) -> str:
    """Basket implied by the locator itself, before any tree probe."""
    # (a) AUTHORITATIVE: ".../tasks/<set>/<id>". This is the set dir the run
    #     actually read its spec from, so it is a measurement, not a lookup --
    #     and it stays right for a run whose task tree was a DIFFERENT checkout.
    #     All 80 bench-tree runs are exactly that case (C:/cb/bench-tree/tasks/...).
    if len(parts) >= 3 and parts[-3] == "tasks":
        return parts[-2]
    # (b) a set-qualified bare id ("bp/gp-glide-stamina-bp"), which is a legal
    #     --task argument and therefore a legal run_graded task_id. Accept the
    #     preceding component only when it NAMES a set: either one of the three
    #     results are reported over, or one the tree confirms. Otherwise a path such as
    #     ".../scratch/<id>/task.md" would report basket "scratch".
    if len(parts) >= 2:
        prev, tid = parts[-2], parts[-1]
        if prev in KNOWN_BASKETS:
            return prev
        if repo_root is not None and _spec_in_set(Path(repo_root) / "tasks" / prev, tid):
            return prev
    return UNKNOWN_BASKET


def from_task_field(value: object, repo_root: object = None,
                    *, source: str = "field") -> TaskIdentity:
    """Resolve ONE record field (a path or a bare id) into a TaskIdentity.

    ``repo_root`` is optional: the task id never needs it, so a caller with no
    repo still gets a correct id -- only the tree-probe half of the basket is
    skipped, and the basket then reports UNKNOWN rather than a guess.
    """
    parts = _components(value)
    if not parts:
        return TaskIdentity(UNKNOWN_TASK_ID, UNKNOWN_BASKET, source)
    task_id = parts[-1]
    # A drive letter ("C:") or a tree root is not an id. Refuse rather than emit
    # a plausible-looking cell key.
    if task_id.lower() in _NOT_AN_ID or task_id.endswith(":"):
        return TaskIdentity(UNKNOWN_TASK_ID, UNKNOWN_BASKET, source)
    basket = _basket_from_components(parts, repo_root)
    if basket == UNKNOWN_BASKET:
        basket = basket_from_tree(task_id, repo_root)
    return TaskIdentity(task_id, basket, source)


def identify(record: Any, repo_root: object = None) -> TaskIdentity:
    """Resolve a whole run record (``result.json`` or ``summary.json``).

    Tries ``task`` then ``task_id`` (see TASK_FIELDS). The first field that
    yields an id wins the id; a later field may still supply a basket the winner
    lacked, but only when it agrees on the id -- two fields naming two different
    tasks is a record we refuse to reconcile silently.
    """
    if not isinstance(record, Mapping):
        return UNIDENTIFIED
    best = UNIDENTIFIED
    for key in TASK_FIELDS:
        ident = from_task_field(record.get(key), repo_root, source=key)
        if not ident.known:
            continue
        if not best.known:
            best = ident
        elif (not best.basket_known and ident.basket_known
              and ident.task_id == best.task_id):
            best = best._replace(basket=ident.basket)
    return best


def spec_path(task_id: str, repo_root: object) -> Optional[Path]:
    """The spec file a bare or set-qualified id denotes, or None if it does not
    resolve UNIQUELY in this tree.

    This is the JOIN: it answers "is the task this run names still in the task
    tree?", which is what a coverage/gap view needs and what none of the three
    readers could ask while their ids were unjoinable.
    """
    if repo_root is None:
        return None
    parts = _components(task_id)
    if not parts:
        return None
    tid = parts[-1]
    if tid.lower() in _NOT_AN_ID or tid.endswith(":"):
        return None
    root = Path(repo_root)
    if len(parts) >= 2:                                   # set-qualified wins
        qualified = _spec_in_set(root / "tasks" / parts[-2], tid)
        if qualified is not None:
            return qualified
    hits: List[Path] = []
    for d in _set_dirs(root):
        found = _spec_in_set(d, tid)
        if found is not None:
            hits.append(found)
    return hits[0] if len(hits) == 1 else None


def basket_order(observed: object) -> List[str]:
    """Row order for a per-basket table: the three reported surfaces, then any other set
    actually observed (alphabetical), then UNKNOWN last.

    Lives here so "make the gap visible" has ONE implementation too. A reader
    that iterated only KNOWN_BASKETS would silently DROP every unresolved run --
    replacing a wrong number with an invisible one.
    """
    seen = {str(b) for b in (observed or ())}
    extra = sorted(seen - set(KNOWN_BASKETS) - {UNKNOWN_BASKET})
    out = list(KNOWN_BASKETS) + extra
    if UNKNOWN_BASKET in seen:
        out.append(UNKNOWN_BASKET)
    return out
