"""refgate — gate-certificate bookkeeping for ``cb refgate`` / ``cb bench --refgates``.

A *reference gate* is a token-free ``run_task.py`` grade of a task's committed
reference solution — proof that the task, its fixture, and this machine can
still produce a PASS before anyone spends tokens against that task. As of the
owner decision of 2026-08-06 the gate is an EXPLICIT action (``cb refgate``,
run when authoring/changing a task and as the fuller fresh-machine
certification), not an automatic phase of every multi-task bench.

This module makes the explicit action IDEMPOTENT: "refgate runs once per real
change" (owner amendment, same night). A PASS persists a **gate certificate**
into a LOCAL, GITIGNORED store (``runs/.refgate-certs.json`` — ``runs/`` is
already in .gitignore; certificates are machine-specific and must never travel
with the repo). A later ``cb refgate`` finds the certificate still valid and
self-skips instead of re-spending ~minutes of build+PIE per task.

What invalidates a certificate (the CONTENT KEY, :func:`identity_for`):

  * the git tree sha of the task's own folder (``tasks/<set>/<id>/``, or the
    legacy flat ``<id>.md`` blob) — any committed task/fixture/reference edit;
  * the git tree sha of the task's substrate dir (``UE-projects/<substrate>/``,
    resolved from the spec's ``substrate:`` key) — any committed substrate or
    verifier-module edit;
  * the UE install root and the hostname — a certificate never transfers
    across engines or machines.

Both shas come from ``git rev-parse HEAD:<path>`` — cheap, exact, and the same
"graded truth is git HEAD" anchor the verifier itself uses. UNCOMMITTED
changes under either path (``git status --porcelain`` non-empty) mean the tree
cannot be certified at all: the gate still RUNS (never skip on a dirty tree —
the operator is mid-edit and wants the grade), but no certificate is written,
because a certificate for state that git cannot name would outlive the edit it
graded.

Failure direction is always conservative: git unavailable / not a repo /
sha lookup failed → no key → never skip, never certify. A gate FAIL removes
any stored certificate for that task. The store itself is an optimization —
an unreadable or unwritable store degrades to "gate every time", never to an
error.

Every git call routes through the module-level :data:`_run_git` seam so the
unit suite fakes repository state without a real repo (the injectable-runner
pattern the rest of the rig uses).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Store schema version: bump when the record shape changes so an old store
# reads as "no valid certificate" (one re-gate) instead of being misread.
SCHEMA = 1

# Repo-relative store path. runs/ is gitignored (checked 2026-08-06), so the
# store is local machine state by construction — exactly what a
# hostname-keyed certificate must be.
CERTS_RELPATH = Path("runs") / ".refgate-certs.json"

# The default substrate when a spec cannot name one (mirrors
# graded_scratch._DEFAULT_SUBSTRATE without importing its UE-side deps here).
_DEFAULT_SUBSTRATE = "CraftBenchTemplate"

# The verifier tree — the code that DOES the grading. It belongs in the
# certificate key for the reason spelled out at its use site in identity_for:
# a certificate says "this reference graded PASS", and editing a grader changes
# what that sentence means.
_VERIFIER_REL = "tools/verify-single"

# (args, repo) -> (returncode | None, stdout). None returncode = git itself
# could not run (missing binary, timeout) — treated exactly like a failure.
RunGit = Callable[[List[str], Path], Tuple[Optional[int], str]]


def _run_git(args: List[str], repo: Path) -> Tuple[Optional[int], str]:
    """Production git runner (module-level so tests monkeypatch it)."""
    try:
        cp = subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30)
    except Exception:  # noqa: BLE001 — no git / timeout / bad cwd: all "no key"
        return None, ""
    return cp.returncode, (cp.stdout or "").strip()


@dataclass
class GateIdentity:
    """One task's certificate identity — everything :class:`CertStore` needs.

    ``task_id`` is the STORE key (set-qualified where possible, so
    ``glide-bp`` and ``bp-g2/glide-bp`` share one certificate). ``key`` is the
    content key, or ``None`` when it could not be computed (never skip, never
    certify). ``dirty`` means uncommitted changes under the task/substrate
    paths (gate runs; certificate withheld). ``reason`` says why a PASS will
    not be certified, for the operator-facing NOTE."""

    task_id: str
    key: Optional[str]
    dirty: bool
    task_rel: str = ""
    substrate_rel: str = ""
    ue_root: str = ""
    hostname: str = ""
    engine_build: str = ""
    reason: str = ""

    @property
    def certifiable(self) -> bool:
        return self.key is not None and not self.dirty


def engine_build_id(ue_root: str) -> Optional[str]:
    """A stable identity for the ENGINE BUILD at ``ue_root``, or None.

    WHY THIS EXISTS (2026-08-14). The certificate key used to be
    ``sha1(task_sha + sub_sha + str(ue_root) + host)``, and ``ue_root`` is the
    PATH — not the engine. So an IN-PLACE engine upgrade at the same path left
    every cached certificate valid, and ``cb refgate`` self-skipped tasks it had
    certified against a build that no longer existed on disk. The docstring's
    promise ("re-gates only when the task/substrate git tree, UE root, or host
    changes") was true as written and misleading in effect, because "UE root"
    reads as "the engine" and means "the path to it".

    Not hypothetical: the engine at ``<UE_ROOT>`` went 5.8.0-55116800 ->
    5.8.1-56057345 mid-session on 2026-08-14, between one spike and the next.
    It was benign only because every run that day happened after the bump.

    A certificate is supposed to mean "this reference graded PASS on this
    engine". Including the changelist is what makes that sentence true.

    Returns None when the version file is missing or unparseable — the caller
    turns that into ``key=None``, i.e. RE-GATE. That is the fail-safe direction
    this module already commits to: never a wrong key, which would skip on
    stale state.
    """
    try:
        raw = (Path(ue_root) / "Engine" / "Build" / "Build.version").read_text(
            encoding="utf-8")
        v = json.loads(raw)
        # Changelist alone would be enough to detect a rebuild, but the version
        # triple makes the cert file readable by a human debugging a re-gate.
        return "%s.%s.%s+%s" % (v["MajorVersion"], v["MinorVersion"],
                                v["PatchVersion"], v["Changelist"])
    except Exception:      # noqa: BLE001 — missing/garbled version file
        return None


def _substrate_rel(spec_path: Path) -> str:
    """``UE-projects/<substrate>`` for the task's declared substrate (spec v2
    ``substrate:`` key via graded_scratch's mapping; any parse problem falls
    back to the default substrate — the gate itself will surface a truly
    malformed spec with a better message)."""
    name = _DEFAULT_SUBSTRATE
    try:
        from aura_rig import graded_scratch as _gs
        name = _gs.substrate_for(Path(spec_path))
    except Exception:  # noqa: BLE001 — malformed spec / missing verifier half
        pass
    return f"UE-projects/{name}"


# Substrate paths of the form ``**/Tasks/<id>/**`` and ``**/Content/Maps/<id>/**``
# are PER-TASK PARTITIONS: they belong to exactly one task and no other task's
# grade can read them.
_PARTITION_PARENTS = ("Tasks", "Maps")


def partition_owner(sub_rel_path: str) -> Optional[str]:
    """The task id that owns this substrate-relative path, or None if the path
    is SHARED (shared source, config, shared content, the module's own files).

    Shared is the safe answer: an unrecognised path stays in every task's key.
    """
    parts = sub_rel_path.split("/")
    for i, seg in enumerate(parts[:-1]):
        if seg in _PARTITION_PARENTS and i + 1 < len(parts) - 0:
            owner = parts[i + 1]
            # ``Tasks/<id>/file`` — a bare file directly under Tasks/ is shared.
            if i + 2 <= len(parts) - 1:
                return owner
    return None


def _keeps(sub_rel_path: str, task_id: str) -> bool:
    """True when this substrate path belongs in THIS task's certificate key."""
    owner = partition_owner(sub_rel_path)
    return owner is None or owner == task_id


def substrate_sha_for_task(repo: Path, substrate_rel: str, task_id: str,
                           run_git: RunGit) -> Optional[str]:
    """The substrate's content sha AS THIS TASK SEES IT.

    WHY THIS IS NOT ``tree_sha(substrate_rel)``. The whole-tree sha put every
    task's map and every task's scaffold into every OTHER task's key, so
    authoring one task invalidated all of them — 62 certificates dropped by a
    change that could not affect 61 of them. Adding ten tasks in a night made
    the gate cache nothing at all, which is the cost the owner called out on
    2026-08-19.

    What is EXCLUDED is exactly the other tasks' per-task partitions:
    ``Source/<Module>/Tasks/<other>/**`` and ``Content/Maps/<other>/**``.
    Everything else — shared source, the module's own headers, Config, shared
    Content — stays in the key for every task.

    WHY THAT IS SAFE, stated as the argument it rests on:
      * Content. A task's fixture loads ITS map and resolves actors by tag
        inside it. It cannot read another task's .umap, so another task's map
        cannot change this task's grade.
      * Source. Every task's scaffold does compile into ONE shared module, so
        another task's source CAN affect this one — but only by failing to
        build, which is LOUD: L1 fails for everything and is impossible to
        mistake for a pass. It cannot silently alter this task's behaviour,
        because a per-task folder holds only that task's own classes; anything
        shared lives OUTSIDE ``Tasks/`` and is therefore still hashed.
      * Under-invalidation is the only dangerous direction. Every exclusion
        here is one whose failure mode is a build error, never a wrong verdict.

    Falls back to the whole-tree sha when ``ls-tree`` is unavailable — the
    conservative direction (over-invalidate), never the permissive one.
    """
    rc, out = run_git(["ls-tree", "-r", f"HEAD:{substrate_rel}"], repo)
    if rc != 0:
        return tree_sha(repo, substrate_rel, run_git)
    kept = [ln for ln in out.splitlines()
            if ln.strip() and _keeps(ln.split("\t", 1)[-1], task_id)]
    if not kept:
        return tree_sha(repo, substrate_rel, run_git)
    return hashlib.sha1("\n".join(kept).encode("utf-8")).hexdigest()


def substrate_dirty_for_task(repo: Path, substrate_rel: str, task_id: str,
                             run_git: RunGit) -> bool:
    """Whether the substrate is dirty AS THIS TASK SEES IT.

    The same partition rule as the key, and it matters more here: `git status`
    over the whole substrate meant ten untracked task folders made EVERY task
    dirty, and a dirty task is never certified. That is how the gate degraded
    into a full re-grade that cached nothing.
    """
    rc, out = run_git(["status", "--porcelain", "--", substrate_rel], repo)
    if rc != 0:
        return True
    prefix = substrate_rel.rstrip("/") + "/"
    for line in out.splitlines():
        if not line.strip():
            continue
        # LOCATE the path rather than slicing a fixed offset. Porcelain is
        # "XY <path>", but _run_git strips its output, so the FIRST line loses
        # its leading status space and a line[3:] slice eats a character of the
        # path -- which silently made every path unrecognised, and therefore
        # every task dirty, which is the exact bug this function exists to fix.
        # rfind also picks the DESTINATION of a rename ("old -> new").
        idx = line.rfind(prefix)
        if idx == -1:
            return True          # unparseable / outside the substrate: dirty
        if _keeps(line[idx + len(prefix):].strip().strip('"'), task_id):
            return True
    return False


def tree_sha(repo: Path, rel: str, run_git: RunGit) -> Optional[str]:
    """``git rev-parse HEAD:<rel>`` — the committed tree (or blob) sha, or
    None when the path is not in HEAD / git failed."""
    rc, out = run_git(["rev-parse", f"HEAD:{rel}"], repo)
    if rc != 0 or not out.strip():
        return None
    return out.splitlines()[0].strip()


def paths_dirty(repo: Path, rels: List[str], run_git: RunGit) -> bool:
    """True when ``git status --porcelain -- <rels>`` reports ANY change —
    or when git itself failed (conservative: an unknowable tree is treated
    as dirty, so it is graded but never certified)."""
    rc, out = run_git(["status", "--porcelain", "--", *rels], repo)
    if rc != 0:
        return True
    return bool(out.strip())


def head_rev(repo: Path, run_git: RunGit = None) -> str:
    """The repo HEAD sha (the certificate's ``substrate_rev`` provenance
    anchor — the same git-HEAD truth the verifier grades from)."""
    rc, out = (run_git or _run_git)(["rev-parse", "HEAD"], repo)
    if rc != 0 or not out.strip():
        return "unknown"
    return out.splitlines()[0].strip()


def identity_for(
    repo: Path,
    task_id: str,
    spec_path: Optional[Path],
    ue_root: str,
    *,
    hostname: Optional[str] = None,
    run_git: Optional[RunGit] = None,
) -> GateIdentity:
    """Compute the certificate identity for one resolved task.

    Never raises: every unknowable input degrades to ``key=None`` (gate runs
    every time) rather than to a wrong key (gate skips on stale state)."""
    run_git = run_git or _run_git
    host = hostname or socket.gethostname()
    repo = Path(repo)
    if spec_path is None:
        return GateIdentity(task_id=task_id, key=None, dirty=False,
                            ue_root=ue_root, hostname=host,
                            reason="task spec unresolved")
    spec_path = Path(spec_path)
    # The store key: set-qualified so the same task always maps to ONE cert
    # however the operator spelled it on the command line.
    store_id = task_id
    try:
        from aura_rig import tasks as _tasks
        store_id = _tasks.qualified_id(repo, spec_path)
    except Exception:  # noqa: BLE001 — spec outside tasks/ (test fixtures)
        pass
    # Task identity path: the task FOLDER for folder-form specs (covers the
    # spec + fixture-adjacent reference/ + discrimination/), the .md blob for
    # legacy flat specs.
    try:
        anchor = spec_path.parent if spec_path.name == "task.md" else spec_path
        task_rel = anchor.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return GateIdentity(task_id=store_id, key=None, dirty=False,
                            ue_root=ue_root, hostname=host,
                            reason="task spec outside the repo")
    substrate_rel = _substrate_rel(spec_path)
    # The per-task partition name: the task FOLDER's basename, which is what
    # names Source/<Module>/Tasks/<id>/ and Content/Maps/<id>/ on this substrate.
    partition_id = task_rel.rsplit("/", 1)[-1]
    if partition_id.endswith(".md"):
        partition_id = partition_id[:-3]
    task_sha = tree_sha(repo, task_rel, run_git)
    sub_sha = substrate_sha_for_task(repo, substrate_rel, partition_id, run_git)
    # THE VERIFIER'S OWN CODE (added 2026-08-14, found in code review). A
    # certificate asserts "this reference graded PASS". The thing that GRADES it
    # is tools/verify-single/ — the per-task graders, the layers, the runner.
    # Without it in the key, editing a grader left every certificate valid, so
    # `cb refgate` self-skipped exactly the tasks whose grading logic had just
    # changed. Same shape as the engine-path bug fixed alongside it: the key
    # covered the INPUTS and not the JUDGE.
    ver_sha = tree_sha(repo, _VERIFIER_REL, run_git)
    dirty = (paths_dirty(repo, [task_rel, _VERIFIER_REL], run_git)
             or substrate_dirty_for_task(repo, substrate_rel, partition_id,
                                         run_git))
    if task_sha is None or sub_sha is None or ver_sha is None:
        return GateIdentity(task_id=store_id, key=None, dirty=dirty,
                            task_rel=task_rel, substrate_rel=substrate_rel,
                            ue_root=ue_root, hostname=host,
                            reason="git identity unavailable (not committed, "
                                   "or git failed)")
    # The ENGINE BUILD, not just its path — see engine_build_id. Without this
    # an in-place engine upgrade leaves every cached certificate valid, and the
    # gate skips tasks it certified against a build that is no longer on disk.
    engine = engine_build_id(ue_root)
    if engine is None:
        return GateIdentity(task_id=store_id, key=None, dirty=dirty,
                            task_rel=task_rel, substrate_rel=substrate_rel,
                            ue_root=ue_root, hostname=host,
                            reason="engine build identity unavailable "
                                   "(Engine/Build/Build.version missing or "
                                   "unreadable) — re-gating rather than "
                                   "trusting a version-blind certificate")
    key = hashlib.sha1("\n".join(
        [task_sha, sub_sha, ver_sha, str(ue_root), engine, host]).encode("utf-8")).hexdigest()
    return GateIdentity(task_id=store_id, key=key, dirty=dirty,
                        task_rel=task_rel, substrate_rel=substrate_rel,
                        ue_root=ue_root, hostname=host, engine_build=engine,
                        reason=("uncommitted changes under the task/substrate"
                                if dirty else ""))


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class CertStore:
    """The on-disk certificate map (``{task_id: record}``), write-through.

    Read once at construction; every mutation rewrites the file atomically.
    An unreadable/corrupt store loads as EMPTY (one re-gate per task) and an
    unwritable one silently keeps working in memory — the store is an
    optimization and must never fail a gate."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._certs: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            return {}
        certs = data.get("certs")
        return dict(certs) if isinstance(certs, dict) else {}

    def _write(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps({"schema": SCHEMA, "certs": self._certs}, indent=2),
                encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass  # in-memory state stays right; next run just re-gates

    def valid(self, ident: GateIdentity) -> Optional[Dict[str, Any]]:
        """The stored record iff it matches ``ident``'s content key exactly
        (and the identity is certifiable at all); else None. Any mismatch —
        task tree, substrate tree, UE root, hostname, schema — is simply a
        different key, so ONE rule covers every staleness class."""
        if not ident.certifiable:
            return None
        rec = self._certs.get(ident.task_id)
        if isinstance(rec, dict) and rec.get("key") == ident.key:
            return rec
        return None

    def certify(self, ident: GateIdentity, substrate_rev: str,
                now: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Persist a PASS for ``ident``; returns the record, or None when the
        identity is not certifiable (dirty tree / no key) — the caller prints
        the why from ``ident.reason``."""
        if not ident.certifiable:
            return None
        rec = {
            "task_id": ident.task_id,
            "key": ident.key,
            "ue_root": ident.ue_root,
            "hostname": ident.hostname,
            "ts": now or _utcnow(),
            "substrate_rev": substrate_rev,
        }
        self._certs[ident.task_id] = rec
        self._write()
        return rec

    def invalidate(self, task_id: str) -> None:
        """Drop a task's certificate (a gate FAIL must never leave one)."""
        if task_id in self._certs:
            del self._certs[task_id]
            self._write()
