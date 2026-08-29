# Reference recipe - shared helper leases

This recipe describes the minimal production solution without changing the
grader. The checked-in reference implementation source is authoritative; the
scratch project retains the supplied live scaffold header.

## Acquisition

1. Reject null owner, empty key, or negative version.
2. Reuse a non-retired cache entry only when both key and version match and its
   payload equals the requested current payload.
3. When the key exists at a different version, mark those entries retired but
   do not remove them while any old lease remains.
4. Create one ordinary transient helper for a genuinely new version, write the
   exact key/version/payload, and put it behind reflected cache ownership.
5. Create one lease token with a reflected strong helper pointer and reflected
   weak owner pointer. Add it to both the selected entry and the reflected
   active-token array.

## Release

1. Reject null, already-released, or foreign tokens without changing state.
2. Remove exactly that token from the active-token array and its entry.
3. Remove the entry only when its final lease is gone; this drops the cache's
   strong helper edge.
4. Clear the token's strong helper edge and weak owner, then mark it released.
5. Never call `AddToRoot`, `RemoveFromRoot`, direct destruction, or GC from
   production code.

## Why the reference passes

- two leases in one entry expose the same helper identity;
- releasing one token leaves the entry and sibling token strong;
- a different version creates a fresh entry and retires, rather than mutates,
  the old entry;
- releasing the final old token removes every old strong edge, so a later
  fixture-owned GC invalidates the old weak identity;
- new/control entries remain independently strong until their own final
  releases, then invalidate after the final fixture-owned GC.

## Admission boundary

Never copy this implementation into `CraftBenchTests`, a control actor, or the
live empty runtime. `run_admission.py prepare` copies the whole live substrate
to a fresh disposable root, overlays only this exact implementation `.cpp`
there, retains the copied live header byte-for-byte, and records both live and
scratch hashes. The exact production fixture then grades the scratch project.
