"""janitor — the tiny detached stack watchdog (owner mandate 2026-08-07).

ONE stdlib-only process, armed by every successful bring-up, that polls the
stack ownership manifest (:mod:`aura_rig.stack_guard`) every ~60s:

  * owner pid DEAD (hard-stopped/crashed/closed-console wrapper — scenarios
    1-3, without waiting for the next cb invocation) -> full ``stop_stack``
    teardown (kill-audited), manifest cleared, exit;
  * ``CB_STACK_IDLE_TEARDOWN_HOURS`` set (default UNSET = off, conservative)
    and the stack idle beyond it (scenario 8, overnight rot) -> same teardown;
  * owner alive and not idle -> keep waiting. The janitor NEVER kills a stack
    whose owner lives — it is a dead-man's switch, not a policy engine;
  * manifest gone (a ``cb down`` / bench teardown already ran) -> exit.

``--no-teardown`` (scenario 4) does NOT protect an orphan: the manifest
records the flag, but the flag means "keep the stack between MY runs", not
"keep it after I'm gone" — ownership transfers to the operator's SESSION on
clean exit (see ``stack_guard.release_at_exit``), so the janitor fires only
once that session itself dies.

Lifecycle mechanics:
  * SINGLE-INSTANCE via an OS advisory lock (``runs/.stack-janitor.lock``,
    reusing the live_lock primitive) — the lock dies with the process, so
    there is no stale state to clean; a second spawn sees it held and exits 0.
  * IDEMPOTENT re-arm: every bring-up calls :func:`arm`; an incumbent janitor
    simply re-reads the manifest each poll, so it serves NEW generations
    without restarting.
  * DOUBLE-SPAWN detachment: ``arm`` starts stage 1, which respawns the real
    loop detached (``--respawned``) and exits — so the loop's recorded parent
    is already dead and a ``taskkill /T`` of the cb tree (the documented
    hard-stop) cannot enumerate it. Reconciliation at the next cb invocation
    stays the backstop regardless.

Run it by hand:  ``py -m aura_rig.janitor --once``  (one decision, no loop)
from ``tools/run-agent``. Logs to ``%TEMP%/cb_janitor.log`` when armed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

_RUNAGENT_DIR = Path(__file__).resolve().parents[1]

DEFAULT_INTERVAL_S = 60.0


def _log_line(msg: str) -> None:
    print(f"[janitor {time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def idle_limit_hours(env: Optional[dict] = None) -> Optional[float]:
    """The OPT-IN idle-teardown limit. UNSET (the default) = no idle teardown —
    conservative: an operator who leaves a stack up on purpose keeps it until
    their session ends. Unparseable values read as unset (never a verdict)."""
    env = os.environ if env is None else env
    raw = (env.get("CB_STACK_IDLE_TEARDOWN_HOURS") or "").strip()
    if not raw:
        return None
    try:
        val = float(raw.split()[0])
    except (ValueError, IndexError):
        return None
    return val if val > 0 else None


def decide(manifest: Optional[dict], *, owner_alive: bool, now: float,
           idle_limit_h: Optional[float]) -> str:
    """The PURE per-poll decision. -> 'exit' | 'wait' | 'teardown-orphan' |
    'teardown-idle'.

    Load-bearing properties (each has a test):
      * no manifest -> 'exit' (nothing to guard; a new bring-up re-arms);
      * dead owner -> 'teardown-orphan', and ``no_teardown`` in the manifest
        does NOT change that (the flag's documented meaning). This is
        state-BLIND on purpose: a PENDING manifest (bring-up armed at start,
        2026-08-07) with a dead owner is an INTERRUPTED bring-up, and its
        half-started stack is exactly as leaky as a green one — same verdict,
        no special case;
      * live owner + no idle limit -> 'wait', ALWAYS — the janitor never
        kills a stack whose owner is alive;
      * idle limit set and exceeded -> 'teardown-idle' even with a live owner
        (scenario 8: the owner's shell being open overnight is exactly the
        leak).
    """
    if not manifest:
        return "exit"
    if not owner_alive:
        return "teardown-orphan"
    if idle_limit_h is not None:
        try:
            last = float(manifest.get("last_activity")
                         or manifest.get("created_at") or 0.0)
        except (TypeError, ValueError):
            last = 0.0
        if last > 0 and (now - last) > idle_limit_h * 3600.0:
            return "teardown-idle"
    return "wait"


def run_loop(*, read: Callable[[], Optional[dict]],
             owner_alive_of: Callable[[dict], bool],
             teardown: Callable[[str, Optional[dict]], None],
             idle_limit: Callable[[], Optional[float]] = idle_limit_hours,
             interval_s: float = DEFAULT_INTERVAL_S,
             sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], float] = time.time,
             log: Callable[[str], None] = _log_line,
             max_ticks: Optional[int] = None) -> str:
    """The poll loop over :func:`decide` — every effect injected, so the tests
    drive it fully offline. Returns the terminal action ('exit',
    'teardown-orphan', 'teardown-idle', or 'wait' when ``max_ticks`` ran out)."""
    ticks = 0
    while True:
        try:
            m = read()
        except Exception:  # noqa: BLE001 — a read glitch must not kill the watchdog
            m = None
        try:
            alive = owner_alive_of(m) if m else False
        except Exception:  # noqa: BLE001 — unknown liveness: NEVER tear down on it
            alive = True
        action = decide(m, owner_alive=alive, now=clock(),
                        idle_limit_h=idle_limit())
        if action == "exit":
            log("manifest gone - stack already torn down elsewhere; exiting.")
            return action
        if action.startswith("teardown"):
            gen = (m or {}).get("generation", "?")
            opid = (m or {}).get("owner_pid", "?")
            log(f"{action}: generation {gen}, owner pid {opid} - running full "
                "stop_stack (kill-audited).")
            done = True
            try:
                # A teardown may DECLINE (return False) when its decision went
                # stale — a new bring-up replaced the manifest between the read
                # and the kill (see _real_teardown's recheck). Then keep
                # looping: the fresh generation's arm saw our lock held and
                # exited, so we are its watchdog now.
                done = teardown(action, m) is not False
            except Exception as e:  # noqa: BLE001
                log(f"teardown errored ({e.__class__.__name__}: {e}) - exiting "
                    "anyway (next cb reconciliation is the backstop)")
            if done:
                return action
            log("teardown declined (manifest superseded) - continuing to watch "
                "the new generation")
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return "wait"
        sleep(interval_s)


# --------------------------------------------------------------------------- #
# Live wiring.                                                                 #
# --------------------------------------------------------------------------- #

def _real_read():
    from aura_rig import stack_guard
    return stack_guard.read_manifest()


def _real_owner_alive(manifest: dict) -> bool:
    from aura_rig import stack_guard
    pid = manifest.get("owner_pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    return stack_guard.pid_alive(pid, manifest.get("owner_created"))


def _real_teardown(action: str, manifest: Optional[dict]) -> bool:
    """Execute the teardown — unless the DECISION went stale: a concurrent
    bring-up replaced the manifest (new generation / owner now alive) in the
    window between the poll's read and this kill. Then return False (decline)
    and the loop keeps watching the new generation instead of killing a stack
    somebody just brought up. Narrow race, cheap recheck."""
    from aura_rig import stack, stack_guard
    cur = stack_guard.read_manifest()
    if cur is not None and (
            cur.get("generation") != (manifest or {}).get("generation")
            or _real_owner_alive(cur)):
        return False
    stack.audit_kill(
        "stack (all ports + editors)",
        f"janitor {action} gen={(manifest or {}).get('generation', '?')}")
    stack.stop_stack(log=_log_line)          # includes the orphan sweep
    stack_guard.clear_manifest(log=_log_line)  # stop_stack clears too; belt+braces
    return True


def _acquire_single_instance_lock():
    """The janitor's single-instance lock, or None when an incumbent holds it.
    live_lock's OS advisory lock dies with the process — no stale cleanup."""
    from aura_rig import stack_guard
    try:
        import live_lock
    except ImportError:
        sys.path.insert(0, str(_RUNAGENT_DIR))
        import live_lock
    try:
        return live_lock.acquire_live_run_lock(stack_guard.janitor_lock_path())
    except live_lock.LiveRunLockBusy:
        return None


def arm(log=print) -> bool:
    """Spawn the watchdog, detached (called by every successful bring-up).
    Idempotent: an incumbent janitor holds the single-instance lock and the
    fresh spawn exits 0; the incumbent re-reads the manifest each poll, so it
    guards the NEW generation without restarting. Called TWICE per bring-up
    since 2026-08-07 (at the pending arm and again at green) — idempotence is
    what makes that free. Never raises."""
    from aura_rig import kill_guard, stack, stack_guard
    if not stack_guard.guard_enabled():
        return False
    if kill_guard.in_test_process():
        # Spawning a detached watchdog that can stop_stack the operator's box
        # is never something a unit test should do (incident 2026-08-07).
        return False
    try:
        log_path = Path(os.environ.get("TEMP") or "/tmp") / "cb_janitor.log"
        stack.start_detached(
            [sys.executable, "-m", "aura_rig.janitor"],
            cwd=_RUNAGENT_DIR, log_path=log_path)
        log(f"  ..    janitor armed (watchdog: dead owner -> auto stop_stack; "
            f"log {log_path})")
        return True
    except Exception as e:  # noqa: BLE001 — arming must never break a bring-up
        try:
            log(f"  WARN  janitor arm failed ({e.__class__.__name__}: {e}) - "
                "startup reconciliation remains the backstop")
        except Exception:
            pass
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aura_rig.janitor")
    ap.add_argument("--respawned", action="store_true",
                    help="internal: this IS the detached loop (stage 2)")
    ap.add_argument("--once", action="store_true",
                    help="one decision (no loop, no teardown side effects "
                         "beyond what the decision demands); for smoke checks")
    ap.add_argument("--interval", type=float, default=None,
                    help=f"poll interval seconds (default "
                         f"{DEFAULT_INTERVAL_S:.0f}; env CB_JANITOR_INTERVAL_S)")
    args = ap.parse_args(argv)

    from aura_rig import stack_guard
    if not stack_guard.guard_enabled():
        _log_line("CB_STACK_GUARD=0 - janitor disabled; exiting.")
        return 0

    interval = args.interval
    if interval is None:
        try:
            interval = float(os.environ.get("CB_JANITOR_INTERVAL_S", "")
                             or DEFAULT_INTERVAL_S)
        except ValueError:
            interval = DEFAULT_INTERVAL_S

    if not args.respawned and not args.once:
        # Stage 1: respawn the real loop DETACHED and exit, so the loop's
        # parent is already gone — a `taskkill /T` of the cb tree (the
        # documented hard-stop) cannot enumerate it as a descendant.
        from aura_rig import stack
        log_path = Path(os.environ.get("TEMP") or "/tmp") / "cb_janitor.log"
        stack.start_detached(
            [sys.executable, "-m", "aura_rig.janitor", "--respawned",
             "--interval", str(interval)],
            cwd=_RUNAGENT_DIR, log_path=log_path)
        return 0

    release = _acquire_single_instance_lock()
    if release is None:
        _log_line("another janitor holds the lock - exiting (single-instance).")
        return 0
    # Hold the lock for the loop's whole life; process death releases it.
    _log_line(f"watching {stack_guard.manifest_path()} every {interval:.0f}s "
              f"(idle limit: {idle_limit_hours() or 'off'})")
    if args.once:
        m = _real_read()
        action = decide(m, owner_alive=(_real_owner_alive(m) if m else False),
                        now=time.time(), idle_limit_h=idle_limit_hours())
        _log_line(f"--once decision: {action}")
        release()
        return 0
    try:
        run_loop(read=_real_read, owner_alive_of=_real_owner_alive,
                 teardown=_real_teardown, interval_s=interval)
    finally:
        try:
            release()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
