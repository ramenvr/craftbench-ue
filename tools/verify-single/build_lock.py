"""Machine-global advisory lock over the UBT build window.

WHY. ``Build.bat`` serializes on a lock file keyed by its OWN PATH, not by the
project::

    set LockFile=%~f0                       rem <UE_ROOT>\\...\\Build.bat
    set LockFile=%LockFile:\\=-%
    set LockFile=%tmp%\\%LockFile::=%.lock

So every build against one engine install contends, across unrelated projects and
unrelated workdirs. Observed 2026-07-31: a CraftBenchTemplate grade collided with a
ThirdPerson ``cb discriminate``, waited 86s, and returned **exit 1 with no compile
errors** — which is a GRADED agent FAIL, byte-indistinguishable in report.json from
"this code does not compile". The same submission sha (583ebb4839a9) PASSed on a
quiet box. That is the defect this module exists to remove.

MONOTONE BY CONSTRUCTION — the property that makes this unattackable.
=====================================================================
This lock can only ever cause the harness to WAIT. It can never:
  * change a verdict CLASS (no new exit code, no non-graded route, no harness-error),
  * fail a run that would otherwise have passed, or
  * pass a run that would otherwise have failed.

That is a security property, not a style choice. An adversarial review of the
obvious design — "could not take the lock -> non-graded verdict" — found it hands
the model under test a denominator opt-out that needs no submission content at all:
one detached process holding the lock is enough to make any run non-graded. The
repo's own verdict contract already reasons this way about L1/L2I exit 124
("routing 124 here would hand every agent an opt-out of the denominator ... ambiguity
resolves toward GRADED"). So: on ANY problem — lock busy past the timeout, an
unwritable lock directory, a hostile path, an OS that refuses — we log it and
BUILD ANYWAY, exactly as if this module did not exist.

The worst case is therefore precisely today's behaviour. There is no configuration,
no race and no attack that makes a locked run worse than an unlocked one.

WHAT IT DOES NOT DEFEND AGAINST. A build started outside CraftBench (an operator's
IDE, a stray UBT) does not take this lock, so it can still contend on Build.bat's
own mutex. This lock removes CraftBench-vs-CraftBench contention — the reproduced
incident's entire class, and the one ``batch_eval``'s ``--verify-concurrency``
creates against itself. Foreign contention is handled one level up by ``run_l1``,
which retries rather than reclassifying (retrying is monotone; reclassifying is not).

LOCK ORDER — normative, and the reason this is safe to add.
==========================================================
Two lock domains already exist. The order MUST be, outermost first::

    runs/.live-run.lock   (live_lock, held across a whole graded leg by the rig)
      -> warm slot lock   (warm_cache.SlotLock, taken in the verify child)
        -> UBT build lock (this module, innermost, held only across the compile)

Nothing may acquire in the reverse order. This module sits at the INNERMOST level
and never acquires anything else while held, so it cannot participate in a cycle.
Keep ``live_lock.acquire_live_run_lock`` non-blocking (it is) and the AB/BA
deadlock an adversarial review flagged between these two domains stays impossible.
"""

from __future__ import annotations

import hashlib
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

# Default ceiling on how long we WAIT for a peer's build. Generous on purpose: a
# cold two-target build is ~300s on the reference box and a batch can queue
# several, so a tight budget would just make us give up and re-create the
# contention this module removes. Exceeding it is not an error — see the
# module docstring's monotonicity guarantee.
DEFAULT_TIMEOUT_S = 900.0
_POLL_S = 0.25

# Read from the process environment, NOT from the repo .env. `.env` is re-read
# inside the grade child (run_task.load_repo_env) and the agent under test can
# write to the repo, so a verdict-affecting knob sourced from there would be
# agent-controlled. This one is deliberately not verdict-affecting (it only
# changes how long we wait before building anyway), and it stays that way.
ENV_TIMEOUT = "CRAFTBENCH_BUILD_LOCK_TIMEOUT"
ENV_DISABLE = "CRAFTBENCH_NO_BUILD_LOCK"


@dataclass(frozen=True)
class BuildLockOutcome:
    """What happened while trying to serialize this build.

    Purely descriptive. No consumer may branch a VERDICT on any field here — the
    monotonicity guarantee is what keeps this lock unattackable, and a consumer
    that gated on ``held`` would silently give it away.
    """

    held: bool                 # did we actually own the lock during the build?
    waited_s: float            # how long we blocked before proceeding
    reason: str                # "acquired" | "timeout" | "disabled" | "unavailable: ..."
    lock_path: Optional[Path]

    @property
    def note(self) -> Optional[str]:
        """One line for L1Result.notes, or None when there is nothing to say."""
        if self.reason == "acquired" and self.waited_s < 1.0:
            return None
        if self.reason == "acquired":
            return (f"build lock: waited {self.waited_s:.0f}s for a peer "
                    f"CraftBench build before compiling")
        if self.reason == "timeout":
            return (f"build lock: NOT acquired after {self.waited_s:.0f}s — built "
                    f"anyway (verdict semantics unchanged); a peer or foreign "
                    f"build may have contended")
        if self.reason == "disabled":
            return f"build lock: disabled via {ENV_DISABLE}"
        return f"build lock: unavailable ({self.reason}) — built anyway"


def resolve_timeout() -> float:
    raw = str(os.environ.get(ENV_TIMEOUT, "")).strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    # A non-positive budget means "never wait", which is a legitimate opt-out
    # (still builds anyway). Negative values normalize to 0 rather than erroring.
    return max(0.0, value)


def _state_root() -> Path:
    """Where the lock file lives — the SAME machine-state root the warm pool uses.

    Reused rather than re-derived so both land on one canonical spelling: that
    helper already expands Windows 8.3 short names, and two processes that
    disagreed on the path would lock two different files and silently lose mutual
    exclusion (the failure mode an exploration of this repo flagged for
    ``runs/.live-run.lock``, whose path is derived three independent ways).
    """
    try:
        import warm_cache
        return warm_cache.default_cache_root().parent / "locks"
    except Exception:  # noqa: BLE001 — never let path resolution fail a build
        import tempfile
        return Path(tempfile.gettempdir()) / "craftbench-locks"


def lock_path_for(ue_root: Path) -> Path:
    """Lock file for one engine install.

    Keyed on the RESOLVED, case-folded engine root because that is what
    ``Build.bat``'s own mutex is keyed on — two CraftBench processes pointed at
    the same engine by different spellings (``Q:/UE_5.8`` vs ``q:\\ue_5.8``) must
    still exclude each other, or the lock silently does nothing for the exact
    pair of runs most likely to collide.
    """
    try:
        key = str(Path(ue_root).resolve()).lower()
    except OSError:
        key = str(ue_root).lower()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return _state_root() / f"ubt-{digest}.lock"


@contextmanager
def ubt_build_lock(
    ue_root: Path,
    *,
    timeout: Optional[float] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Iterator[BuildLockOutcome]:
    """Serialize the UBT build window against other CraftBench processes.

    NEVER RAISES and never re-raises from the lock machinery — every failure path
    yields an outcome with ``held=False`` and lets the caller build. The body's
    own exceptions propagate untouched (the lock is released first).

    Deliberately NOT reused from ``live_lock``: that primitive's
    ``acquire_live_run_lock`` is strictly non-blocking with no timeout parameter,
    and its ``live_run_lock`` context manager silently ignores ``blocking=False``
    when a timeout is passed. Queuing (not refusing) is the whole point here, and
    a lock this one must never be able to fail a build wants an explicit,
    total implementation rather than a footgun-adjacent reuse.
    """
    emit = log or (lambda _msg: None)
    if str(os.environ.get(ENV_DISABLE, "")).strip().lower() in ("1", "true", "yes"):
        yield BuildLockOutcome(False, 0.0, "disabled", None)
        return

    budget = resolve_timeout() if timeout is None else max(0.0, timeout)
    lp: Optional[Path] = None
    fh = None
    started = time.monotonic()
    acquired = False
    reason = "timeout"
    announced = False

    try:
        lp = lock_path_for(ue_root)
        lp.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lp, "a+")
    except Exception as e:  # noqa: BLE001 — a hostile/unwritable path must not fail a build
        # Includes the case an adversarial review demonstrated live: a DIRECTORY
        # planted at the lock path makes open() raise PermissionError, which
        # without this guard would reach run_task's crash trap and become exit 7
        # (HARNESS-ERROR) — a non-graded verdict an agent could trigger at will.
        yield BuildLockOutcome(False, 0.0, f"unavailable: {type(e).__name__}", lp)
        return

    try:
        deadline = started + budget
        while True:
            if _try_lock(fh):
                acquired = True
                reason = "acquired"
                break
            if time.monotonic() >= deadline:
                break
            if not announced:
                announced = True
                emit(f"build lock: another CraftBench build holds {lp.name}; "
                     f"waiting up to {budget:.0f}s")
            time.sleep(_POLL_S)

        waited = time.monotonic() - started
        if acquired and waited >= 1.0:
            emit(f"build lock: acquired after {waited:.0f}s")
        elif not acquired:
            emit(f"build lock: timed out after {waited:.0f}s — building anyway "
                 f"(verdict semantics unchanged)")
        yield BuildLockOutcome(acquired, waited, reason, lp)
    finally:
        if acquired:
            _unlock(fh)
        try:
            fh.close()
        except OSError:
            pass


def _try_lock(fh) -> bool:
    """One non-blocking exclusive attempt. False when held; False on any error.

    Errors resolve to "not held" rather than propagating: a lock we cannot take
    must degrade to building unlocked, never to failing the build.
    """
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except Exception:  # noqa: BLE001 — busy, or an OS that will not lock here
        return False


def _unlock(fh) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_UN)
    except Exception:  # noqa: BLE001 — best-effort; the fd close releases it anyway
        pass


def is_build_active(ue_root: Path) -> bool:
    """Non-blocking probe: is another CraftBench build holding this engine's lock?

    Note the same caveat ``live_lock.is_live_run_active`` carries — it cannot tell
    a peer's lock from one this very process already holds, because the probe
    opens a fresh handle. Diagnostics only; never gate anything on it.
    """
    try:
        lp = lock_path_for(ue_root)
        if not lp.exists():
            return False
        with open(lp, "a+") as fh:
            if _try_lock(fh):
                _unlock(fh)
                return False
            return True
    except Exception:  # noqa: BLE001
        return False
