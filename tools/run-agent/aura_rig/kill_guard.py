"""kill_guard — the refusal layer in front of every REAL process kill.

WHY THIS EXISTS (INCIDENT 2026-08-07). A unit-test run murdered a LIVE
aura-product drive editor. ``runs/.kill-audit.log`` around 20:59 and 21:01
carries the proof: one process wrote audit lines for the MOCK pids 101/303 —
literally the fixtures in ``tests/test_cb_stack.py`` — INTERLEAVED with real
``image=UnrealEditor reason=kill_by_image`` entries. A test process had reached
:func:`aura_rig.stack.kill_by_image` / ``kill_port_owner`` and ``taskkill``'d
the live editor plus the :3000/:3002/:9222 owners. The drive died "EDITOR GONE
— RC port 30010 did not accept a connection" with no crash dump, because it was
KILLED, not crashed. That very likely explains most of the preceding two days'
EDITOR-GONE verdicts: test suites were run concurrently with live benches many
times.

The lesson is not "audit harder" — the rig already audited every kill and the
audit is what root-caused it. The lesson is that a kill primitive must not be
reachable-with-effect from a process that has no business killing anything.
This module is that gate. Two independent refusals, both fail-SAFE:

  1. TEST-PROCESS REFUSAL (the primary guard). A unittest/pytest process never
     performs a real kill. Detection is cheap and deliberately OVER-broad
     (``unittest``/``pytest`` in ``sys.modules``, an ``argv`` token naming a
     test runner, or ``CB_IN_TEST=1``): when we cannot tell, we REFUSE. A
     missed kill costs a leaked stack and a ~1 min re-bring-up; a murdered live
     run costs an entire graded rep and, worse, produces a machine-fault
     verdict that reads like a model failure.
     Deliberate override: ``CB_ALLOW_REAL_KILLS=1`` — for the ONE legitimate
     case, a human debugging kill paths from a REPL that happens to have
     imported unittest. It is audited loudly every time it is used.

  2. LIVE-OWNER REFUSAL. ``stack_guard``'s ``runs/.stack-manifest.json``
     records the pid (+ create time, so a reused pid cannot impersonate it)
     that owns the live stack. If that owner is ALIVE and is neither this
     process nor one of its ancestors (which covers the session anchor), then
     SOMEONE ELSE's bench is in flight and no kill here is legitimate — not
     from another ``cb``, not from a stray script, not from another agent
     session. Override: ``CB_ALLOW_STACK_TAKEOVER=1`` (the same flag
     ``stack_guard.reconcile_at_entry`` already documents for taking over a
     live stack).

``CB_STACK_GUARD=0`` (the subsystem kill switch) disables ONLY the live-owner
layer, exactly as it disables the rest of the manifest subsystem. It does NOT
re-enable kills from a test process — that layer has no legitimate off switch
other than ``CB_ALLOW_REAL_KILLS=1``.

Everything here is a pure function over injected facts (modules / argv / env /
manifest), so the whole guard is unit-testable without a process table.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Iterable, Mapping, Optional

_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: Refusal reasons, written verbatim into the ``reason=`` field of the audit
#: line so ``runs/.kill-audit.log`` is greppable for "what did NOT happen".
REFUSED_TEST = "REFUSED(test-process)"
REFUSED_LIVE_OWNER = "REFUSED(live-owner pid={pid})"

#: Modules whose mere presence in ``sys.modules`` means "a test runner is
#: driving this process". No production module under ``tools/run-agent``
#: imports any of them (verified 2026-08-07), so this cannot fire on a real cb.
_TEST_MODULES = ("unittest", "pytest", "_pytest")

#: Lowercased substrings that mark an ``argv`` token as a test runner entry
#: point (``-m unittest`` rewrites argv[0] to ``.../unittest/__main__.py``;
#: IDE runners use the ``_jb_*`` shims).
_TEST_ARGV_TOKENS = ("unittest", "pytest", "py.test", "_jb_unittest",
                     "_jb_pytest")


def env_true(name: str, env: Optional[Mapping[str, str]] = None) -> bool:
    """A CraftBench boolean env flag (``1/true/yes/on``), never raising."""
    try:
        env = os.environ if env is None else env
        return (env.get(name) or "").strip().lower() in _TRUTHY
    except Exception:  # noqa: BLE001 — a flag read must never break a teardown
        return False


# --------------------------------------------------------------------------- #
# Detection (pure over injected facts).                                        #
# --------------------------------------------------------------------------- #

def in_test_process(*, modules: Optional[Iterable[str]] = None,
                    argv: Optional[Iterable[str]] = None,
                    env: Optional[Mapping[str, str]] = None) -> bool:
    """True when this process looks like a test runner. OR of three cheap
    signals; any one is enough (fail-SAFE — an ambiguous process is a test)."""
    if env_true("CB_IN_TEST", env):
        return True
    try:
        mods = sys.modules if modules is None else modules
        for name in _TEST_MODULES:
            if name in mods:
                return True
    except Exception:  # noqa: BLE001
        return True  # cannot tell -> treat as a test -> refuse
    try:
        av = sys.argv if argv is None else argv
        for tok in (av or ()):
            low = str(tok).replace("\\", "/").lower()
            if any(t in low for t in _TEST_ARGV_TOKENS):
                return True
    except Exception:  # noqa: BLE001
        return True
    return False


def acting_role(*, modules: Optional[Iterable[str]] = None,
                argv: Optional[Iterable[str]] = None,
                env: Optional[Mapping[str, str]] = None) -> str:
    """The acting process's role for the audit line: ``test`` | ``janitor`` |
    ``cb`` | ``other``. Cheap, best-effort, never raises — tonight's diagnosis
    would have been instant with this field present."""
    try:
        if in_test_process(modules=modules, argv=argv, env=env):
            return "test"
        e = os.environ if env is None else env
        explicit = (e.get("CB_PROC_ROLE") or "").strip().lower()
        if explicit:
            return explicit
        av = [str(a) for a in (sys.argv if argv is None else argv) or ()]
        joined = " ".join(av).replace("\\", "/").lower()
        if "aura_rig.janitor" in joined or joined.split(" ")[0].endswith("/janitor.py"):
            return "janitor"
        head = av[0].replace("\\", "/").lower() if av else ""
        base = head.rsplit("/", 1)[-1]
        if "aura_rig.cb" in joined or base in ("cb", "cb.py", "cb.cmd", "cb.exe"):
            return "cb"
        return "other"
    except Exception:  # noqa: BLE001
        return "other"


def live_foreign_owner(manifest: Optional[dict], *,
                       self_pid: Optional[int] = None,
                       alive: Optional[Callable[..., bool]] = None,
                       is_ancestor: Optional[Callable[[int], bool]] = None
                       ) -> Optional[int]:
    """The pid of a LIVE stack owner that is not us — or None.

    "Not us" means: not this pid, and not an ancestor of it. The ancestor test
    is what lets the owning session's own ``cb down`` / mid-bench recycle
    through: ``stack_guard.release_at_exit`` transfers ownership to the SESSION
    ANCHOR, which is by construction an ancestor of every cb launched from that
    session. Anything else holding a live manifest is a concurrent run whose
    editor this process must not touch."""
    if not isinstance(manifest, dict):
        return None
    pid = manifest.get("owner_pid")
    if not isinstance(pid, int) or pid <= 0:
        return None                      # unattributable manifest: not a claim
    me = os.getpid() if self_pid is None else self_pid
    if pid == me:
        return None
    try:
        if alive is None or is_ancestor is None:
            from aura_rig import stack_guard as _sg
            alive = alive or _sg.pid_alive
            is_ancestor = is_ancestor or _sg._is_ancestor
        if not alive(pid, manifest.get("owner_created")):
            return None                  # a dead owner is an orphan, not a run
        if is_ancestor(pid):
            return None                  # our own session anchor / wrapper
    except Exception:  # noqa: BLE001 — an unreadable process table is not a
        return None                      # claim of ownership (see module doc)
    return pid


# --------------------------------------------------------------------------- #
# The decision (pure) + the wired entry point.                                 #
# --------------------------------------------------------------------------- #

def decide(*, is_test: bool, allow_real_kills: bool,
           live_owner_pid: Optional[int] = None,
           allow_takeover: bool = False) -> Optional[str]:
    """PURE core. Returns None to allow the kill, else the refusal reason that
    goes into the audit line's ``reason=`` field. Test refusal is checked
    FIRST: it is the layer that cannot be traded away."""
    if is_test and not allow_real_kills:
        return REFUSED_TEST
    if live_owner_pid and not allow_takeover:
        return REFUSED_LIVE_OWNER.format(pid=live_owner_pid)
    return None


def _read_manifest() -> Optional[dict]:
    """The stack ownership manifest, or None (absent / unreadable / the
    ``CB_STACK_GUARD=0`` kill switch)."""
    try:
        from aura_rig import stack_guard as _sg
        if not _sg.guard_enabled():
            return None
        return _sg.read_manifest()
    except Exception:  # noqa: BLE001
        return None


def refusal(target: str = "", reason: str = "") -> Optional[str]:
    """THE wired gate. None -> the caller may perform a real kill; otherwise a
    refusal reason for the audit line. ``target``/``reason`` are accepted for
    symmetry with ``stack.audit_kill`` (and for future per-target policy) —
    the decision itself is process-wide, never per-target."""
    try:
        is_test = in_test_process()
    except Exception:  # noqa: BLE001 — unsure whether this is a test -> refuse
        is_test = True
    return decide(is_test=is_test,
                  allow_real_kills=env_true("CB_ALLOW_REAL_KILLS"),
                  live_owner_pid=live_foreign_owner(_read_manifest()),
                  allow_takeover=env_true("CB_ALLOW_STACK_TAKEOVER"))


__all__ = [
    "REFUSED_TEST",
    "REFUSED_LIVE_OWNER",
    "env_true",
    "in_test_process",
    "acting_role",
    "live_foreign_owner",
    "decide",
    "refusal",
]
