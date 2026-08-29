"""Offline staging check for t3-reach-the-exit-before-they-see-you.

    python authoring/check_staging.py            # check the authored staging
    python authoring/check_staging.py --sweep    # re-tune the lane pace / truck speed

NO UNREAL REQUIRED. This runs `author_map.py`'s OWN solvers (with the `unreal` module
stubbed and `main()` stripped), which is the same arithmetic the fixture re-runs inside
`PrepareTest`, and then adds two simulations the map script cannot do because they are
properties of the DRIVE rather than of the level:

  * THE SHADOW ENTRY. `AStealthYardFunctionalTest::ShadowEntryRipe` refuses to walk the
    runner into the truck's shadow until the covering watcher's cone and the truck's rail
    line up: arrive unseen, arrive inside a stretch where the cone holds the spot AND the
    truck lies across the line, hold it past the gate's cover floor, then watch the truck
    let go while the cone still holds. Those are two independent periods, so a staging can
    easily admit exactly ONE such moment in a whole run -- a coincidence, not a staging.
    This scans the whole beat and reports every departure window.

  * THE GOVERNOR. `DriveHero` releases a walk taken during a running round only once the
    model proves nobody can see the runner before it arrives. On the second watch the lane
    is only safe in bands, so this checks, from every relative phase of the covering
    watcher's lap, that each long lane leg does get released.

Both were written after the 2026-08-19 review found that the drive as first built could
stall before any gate could speak. Re-run this after ANY change to the yard's numbers --
especially the lane watcher's base pace, the truck's speed, its rail or its footprint.
"""
from __future__ import annotations

import argparse
import io
import math
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "author_map.py")

# Mirrors of the fixture's constants. Keep these in step with
# Source/CraftBenchTests/Tasks/<task>/StealthYardFunctionalTest.cpp.
HERO_SPEED = 500.0            # AThirdPersonCharacter MaxWalkSpeed
RIPE_STEP = 0.10              # kRipeStepS
ARRIVE_SLACK = 0.30           # kRipeArriveSlackS
MIN_TRUCK_COVER = 1.5         # kMinTruckCoverS
CLEAR_SEARCH = 14.0           # kRipeClearSearchS
WAYPOINT_UU = 90.0            # kWaypointUu
WALK_HORIZON_SLACK = 0.75     # kWalkHorizonSlackS


def load(**overrides):
    """author_map.py as a module, with `unreal` stubbed and main() stripped."""
    u = types.ModuleType("unreal")
    u.log = overrides.pop("log", lambda m: None)
    u.log_warning = lambda m: None
    u.log_error = lambda m: None
    sys.modules["unreal"] = u
    src = io.open(SRC, encoding="utf-8").read()
    src = "\n".join(ln for ln in src.splitlines() if ln.strip() != "main()")
    src = src.replace('if __name__ == "__main__":', "if False:")
    for old, new in overrides.pop("subs", ()):
        assert src.count(old) == 1, "substitution did not apply: %s" % old[:60]
        src = src.replace(old, new)
    am = types.ModuleType("author_map")
    exec(compile(src, SRC, "exec"), am.__dict__)
    return am


def triangle(start, length, direction, travel):
    """The wave both the watchers and the truck walk: to the end, turn, keep going."""
    s, d, rem = start, direction, travel
    while rem > 0.0:
        to_end = (length - s) if d > 0 else s
        if rem <= to_end:
            s += d * rem
            rem = 0.0
        else:
            rem -= max(to_end, 0.0)
            s = length if d > 0 else 0.0
            d = -d
    return max(0.0, min(length, s)), d


class Yard:
    """The live yard, as the fixture's PredictWatcher / PredictTruck model it."""

    def __init__(self, am, watchers=None):
        self.am = am
        self.watchers = watchers if watchers is not None else am.WATCHERS
        self.static = am.static_rects()
        self.rail_a = (am.TRUCK_AT[0] - am.TRUCK_RAIL_HALF[0],
                       am.TRUCK_AT[1] - am.TRUCK_RAIL_HALF[1])
        self.rail_b = (am.TRUCK_AT[0] + am.TRUCK_RAIL_HALF[0],
                       am.TRUCK_AT[1] + am.TRUCK_RAIL_HALF[1])
        self.rail_len = math.hypot(self.rail_b[0] - self.rail_a[0],
                                   self.rail_b[1] - self.rail_a[1])

    def watcher_at(self, w, t, phase0=0.0):
        ax, bx, y = self.am.round_by_tag(w[4])
        s, d = triangle(0.0, bx - ax, 1.0, w[3] * (t + phase0))
        return (ax + s, y, (1.0 if d > 0 else -1.0, 0.0))

    def truck_at(self, t):
        s, _d = triangle(self.rail_len * 0.5, self.rail_len, 1.0,
                         self.am.TRUCK_SPEED * t)
        f = s / self.rail_len
        return (self.rail_a[0] + (self.rail_b[0] - self.rail_a[0]) * f,
                self.rail_a[1] + (self.rail_b[1] - self.rail_a[1]) * f)

    def cone(self, w, t, pt, phase0=0.0):
        ex, ey, facing = self.watcher_at(w, t, phase0)
        return self.am.can_see((ex, ey), facing, w[1], w[2], pt, self.static)

    def truck_on_line(self, w, t, pt, phase0=0.0):
        ex, ey, _f = self.watcher_at(w, t, phase0)
        return self.am.seg_hits_rect((ex, ey), pt, self.truck_at(t),
                                     (self.am.TRUCK_HALF[0], self.am.TRUCK_HALF[1]))

    def sees(self, w, t, pt, phase0=0.0):
        return self.cone(w, t, pt, phase0) and not self.truck_on_line(w, t, pt, phase0)


def shadow_entry_windows(am, shadow, horizon_s=400.0):
    """Every moment ShadowEntryRipe would return true, grouped into windows."""
    yard = Yard(am)
    lane = am.WATCHERS[0]
    wait = (shadow[0], am.LANE_Y)
    dist = math.hypot(shadow[0] - wait[0], shadow[1] - wait[1])
    dx, dy = (shadow[0] - wait[0]) / dist, (shadow[1] - wait[1]) / dist
    stop = (shadow[0] - dx * WAYPOINT_UU, shadow[1] - dy * WAYPOINT_UU)
    early = dist / HERO_SPEED
    arrive = early + ARRIVE_SLACK

    def ripe(t0):
        # (a) unseen the whole way in, truck included
        k = 0
        while k * RIPE_STEP <= arrive:
            t = k * RIPE_STEP
            k += 1
            f = min(HERO_SPEED * t, dist) / dist
            at = (wait[0] + (shadow[0] - wait[0]) * f,
                  wait[1] + (shadow[1] - wait[1]) * f)
            for w in am.WATCHERS:
                if yard.sees(w, t0 + t, at):
                    return None
        # (b) cone AND truck from the earliest possible arrival, past the cover floor,
        #     at BOTH ends of the stopping segment
        until = arrive + MIN_TRUCK_COVER + 0.2
        k = 0
        while early + k * RIPE_STEP <= until:
            t = early + k * RIPE_STEP
            k += 1
            for pt in (shadow, stop):
                if not yard.cone(lane, t0 + t, pt):
                    return None
                if not yard.truck_on_line(lane, t0 + t, pt):
                    return None
            for w in am.WATCHERS[1:]:
                if yard.sees(w, t0 + t, shadow) or yard.sees(w, t0 + t, stop):
                    return None
        # (c) and then the truck lets go while the cone still holds
        t = until
        while t <= arrive + CLEAR_SEARCH:
            if not (yard.cone(lane, t0 + t, shadow) and yard.cone(lane, t0 + t, stop)):
                return None
            if not (yard.truck_on_line(lane, t0 + t, shadow)
                    or yard.truck_on_line(lane, t0 + t, stop)):
                return t
            t += RIPE_STEP
        return None

    hits = []
    t0 = 0.0
    while t0 <= horizon_s:
        if ripe(t0) is not None:
            hits.append(t0)
        t0 += 0.05
    windows, start, prev = [], None, None
    for t in hits:
        if start is None:
            start = t
        elif t - prev > 0.2:
            windows.append((start, prev))
            start = t
        prev = t
    if start is not None:
        windows.append((start, prev))
    return windows, dist, arrive


def governor_waits(am):
    """From every relative lap phase, how long each watch-2 lane leg waits to release."""
    near = ("Near", am.WATCHERS[0][1], am.WATCHERS[0][2] * am.RESTAGE_ANGLE_MUL,
            am.WATCHERS[0][3] * am.RESTAGE_PACE_MUL, "RoundNorth")
    far = ("Far", am.WATCHERS[1][1] * am.RESTAGE_REACH_MUL, am.WATCHERS[1][2],
           am.WATCHERS[1][3], "RoundCentre")
    watch2 = (near, far, am.WATCHERS[2])
    yard = Yard(am, watch2)

    def earliest(start, target, horizon, t0, phase0):
        dist = math.hypot(target[0] - start[0], target[1] - start[1])
        t = 0.0
        while t <= horizon:
            f = min(HERO_SPEED * t, dist) / dist if dist > 0 else 1.0
            at = (start[0] + (target[0] - start[0]) * f,
                  start[1] + (target[1] - start[1]) * f)
            for w in watch2:
                if yard.cone(w, t0 + t, at, phase0):
                    return t
            t += 0.2
        return horizon

    def first_release(start, target, phase0, limit=240.0):
        dist = math.hypot(target[0] - start[0], target[1] - start[1])
        horizon = dist / HERO_SPEED * 1.35 + WALK_HORIZON_SLACK
        t0 = 0.0
        while t0 <= limit:
            if earliest(start, target, horizon, t0, phase0) >= horizon - 0.01:
                return t0, horizon
            t0 += 0.25
        return None, horizon

    lane_y = am.LANE_Y
    bands = [(-5800.0, -3700.0), (-1500.0, 1500.0), (4600.0, 5800.0)]
    rests = [(0.5 * (a + b), lane_y) for a, b in bands]
    legs = [
        ("plate -> rest A", (am.PLATE_AT[0], lane_y), rests[0]),
        ("rest A -> rest B", rests[0], rests[1]),
        ("rest B -> the SPLIT spot", rests[1], (3064.8, lane_y)),
        ("rest B -> rest C", rests[1], rests[2]),
        ("rest C -> the GATE", rests[2], (am.GATE_AT[0], lane_y)),
    ]
    lap = 2.0 * 2400.0 / far[3]
    out = []
    for label, a, b in legs:
        waits, phase0 = [], 0.0
        while phase0 < lap:
            t, horizon = first_release(a, b, phase0)
            waits.append(float("inf") if t is None else t)
            phase0 += 1.0
        out.append((label, horizon, max(waits)))
    return out, lap


def check(verbose=True):
    am = load(log=(lambda m: print("    " + str(m))) if verbose else (lambda m: None))
    ok = True
    print("== the map script's own solvers ==")
    try:
        shadow, win, cover = am.solve_shadow_spot()
        am.solve_split_spot()
        am.check_control()
        am.check_ends()
        am.check_route_and_rounds()
        am.report_safe_bands()
    except SystemExit:
        print("  *** a solver REFUSED the staging; the map would not author ***")
        return False

    print()
    print("== the drive's shadow entry ==")
    windows, dist, arrive = shadow_entry_windows(am, shadow)
    print("   walk in %.0f uu, arriving in %.2f s at the latest" % (dist, arrive))
    print("   %d departure window(s) in the first 400 s" % len(windows))
    for a, b in windows:
        print("     %7.2f .. %7.2f s  (%.2f s wide)" % (a, b, b - a))
    if len(windows) < 3:
        ok = False
        print("   *** FEWER THAN THREE. One or two departure moments is a coincidence,")
        print("       not a staging: a small difference between the engine's start")
        print("       poses and this model moves them out from under the drive, and")
        print("       phase 2 then reports a staging fault instead of a grade. Re-run")
        print("       with --sweep. ***")

    print()
    print("== the governor, on the second watch ==")
    legs, lap = governor_waits(am)
    print("   covering watcher's lap %.1f s" % lap)
    for label, horizon, worst in legs:
        flag = "" if worst != float("inf") else "   *** NEVER RELEASES ***"
        if worst == float("inf"):
            ok = False
        print("     %-26s horizon %5.1f s   worst wait %6.2f s%s"
              % (label, horizon, worst, flag))

    print()
    print("ALL CHECKS PASS" if ok else "*** CHECKS FAILED -- see above ***")
    return ok


def sweep():
    print("%-6s %-6s | %-14s %-7s %-7s %-6s %-6s %s"
          % ("pace", "truck", "shadow", "cone", "clear", "cover", "wins", "first"))
    best = None
    for pace in (180.0, 150.0, 120.0, 100.0):
        for tspd in (200.0, 150.0, 120.0):
            subs = [
                ('("Near", 2000.0, 40.0, 120.0, "RoundCentre")',
                 '("Near", 2000.0, 40.0, %r, "RoundCentre")' % pace),
                ("TRUCK_SPEED = 150.0", "TRUCK_SPEED = %r" % tspd),
            ]
            try:
                am = load(subs=subs)
                shadow, win, cover = am.solve_shadow_spot()
                am.solve_split_spot()
                am.check_control()
                am.check_ends()
                am.check_route_and_rounds()
                am.report_safe_bands()
            except SystemExit:
                print("%-6.0f %-6.0f | refused by an author-time check" % (pace, tspd))
                continue
            windows, _d, _a = shadow_entry_windows(am, shadow)
            first = windows[0][0] if windows else None
            print("%-6.0f %-6.0f | %-14s %-7.2f %-7.2f %-6.2f %-6d %s"
                  % (pace, tspd, "(%.0f,%.0f)" % shadow, win["duration"],
                     min(win["clear_east"], win["clear_west"]), cover, len(windows),
                     ("%.1f s" % first) if first is not None else "never"))
            key = (len(windows), -(first if first is not None else 1e9))
            if best is None or key > best[0]:
                best = (key, (pace, tspd))
    if best:
        print()
        print("BEST: lane base pace %.0f, truck %.0f uu/s (%d windows)"
              % (best[1][0], best[1][1], best[0][0]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", action="store_true",
                    help="re-tune the lane watcher's pace against the truck's speed")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if args.sweep:
        sweep()
    else:
        sys.exit(0 if check(verbose=not args.quiet) else 1)
