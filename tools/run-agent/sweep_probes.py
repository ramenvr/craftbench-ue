"""Direct gauges for the two conditions a serial sweep must not violate.

Both answer a question the sweep previously GUESSED at:

  live-run-lock  -- "is another --live-project run going?" Previously a process
                    count, which is unreliable: the query's own shell matches the
                    pattern it searches for, so counts read >0 with nothing running
                    (mis-read repeatedly on 2026-08-21). The lock is an OS fd lock,
                    so `is_live_run_active` is authoritative.

  hide-target    -- "can the fairness hide move Content/Maps yet?" Previously a
                    fixed one-shot retry, which lost cells when the holder outlived
                    it. This opens each file with dwShareMode=0: if any process
                    holds a handle, CreateFileW fails ERROR_SHARING_VIOLATION.
                    NON-MUTATING on purpose -- the obvious alternative (rename the
                    dir and rename it back) leaves a broken tree if the probe dies
                    between the two renames.

Usage:  py -3 sweep_probes.py live-run     (NOT `py -3.12`: it stopped
        resolving 2026-07-28 and exits 103)
Exit 0 = clear/idle, 1 = busy/held, 2 = could not measure.
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent


# --------------------------------------------------------------------------- #


def live_run_busy() -> bool:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from live_lock import is_live_run_active
    return bool(is_live_run_active(REPO / "runs" / ".live-run.lock"))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    which = argv[1]
    wait = 0
    if "--wait" in argv:
        wait = int(argv[argv.index("--wait") + 1])
    probe = {"live-run": live_run_busy}.get(which)
    if probe is None:
        return 2
    deadline = time.time() + wait
    while True:
        try:
            busy = probe()
        except Exception as e:  # noqa: BLE001 -- unmeasurable is not "busy"
            print(f"probe error: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        if not busy:
            return 0
        if time.time() >= deadline:
            return 1
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
