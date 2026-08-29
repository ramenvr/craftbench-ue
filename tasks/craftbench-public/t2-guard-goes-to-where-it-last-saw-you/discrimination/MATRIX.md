# Discrimination matrix — t2-guard-goes-to-where-it-last-saw-you

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | A five-state machine on the watchman itself. `LastSeenSpot` is refreshed on **every** frame the eyes report true, so on the frame they go false it already holds where the character was on the last sighted frame; that falling edge is the only place a spot is created and the only place the radio speaks. The radio hands over an `FVector`, found by walking the world for other watchmen rather than by any level reference. The give-up clock starts on ARRIVAL. Sight is tested before the switch, not inside one of its cases. Nothing in the solution knows there are two watchmen, which way round they are, or where anything stands — which is exactly why the reversed roles, the moved walls and the per-run jitter of leg 2 cost it nothing. |
| `empty` | FAIL | `WentToWhereItLastSawYou: the watchman that lost sight of the` | The unmodified scaffold compiles, so L1 is green. The eyes, the feet and the post all work; nothing calls them. The character walks up the north lane, the north watchman's own sight test goes true at ~1600 uu short of the post's beam and false again ~3200 uu later, the fixture opens the alert at that spot — and the watchman is still standing exactly where the yard put it when its allowance (its own pace over the straight-line distance, plus six seconds) runs out. Measured on the offline simulation of the drive: the spot is ~2400 uu from the post and the allowance is ~16 s. |

## Requirements table

Kept in `task.md` under **Requirement-to-assertion map**, together with the condition
under which each gate does not run. Two of the eleven gates are leg-scoped and both are
named there; this task produces a single verdict from the first gate that fires, so the
constant-denominator rule does not apply and is documented as inapplicable rather than
quietly ignored.

## What carries the discrimination without variants

**The three plausible "spots" are thousands of uu apart.** A first pass has to pick one
of: where the character was FIRST spotted, where the WATCHMAN was standing when it lost
them, or where the character was on the last sighted frame. The staging pulls those
three as far apart as the yard allows and the failure message prints all three in one
sentence:

| Quantity | Measured (offline simulation, leg 1) |
| --- | --- |
| gap between the watchman and the character at sight-loss | ~2400 uu (it is exactly the sight range: sight breaks because the character outran the watchman) |
| distance from where it was first spotted to where it was last seen | ~6200 uu |
| distance from the last-seen spot to where the character actually hid | ~2500 uu |
| closest a **correct** watchman comes to the hidden character while blind and away from the spot | ~2400 uu, against a floor of 1200 |
| closest a **live-transform chaser** comes while blind | ~600 uu — it walks up to the alcove's outer wall |

**The character outruns the watchmen.** 500 uu/s against 300. That is what makes the
sight break happen by RANGE with a real gap behind it instead of with the watchman
standing on top of the character, and it is also why the "it only ever walked" budget
(pace x 1.4 + 60 = 480 uu/s) is deliberately set below the character's speed: a
submission that speeds its watchmen up to keep the character in view fails that gate
instead of quietly deleting every other one.

**The alcove opens away from the lane.** This is the single geometric fact that lets a
six-second search be measured at all. With the mouth facing the lane, a watchman
standing on the last-seen spot could see straight in, the search would collapse back
into a chase on its first frame, and the task would grade nothing. The authoring script
refuses to save a level where the hiding place is visible from any point of the band a
watchman searches, and the fixture re-checks the same thing at run time against the
live walls.

**Nothing is written down.** Every waypoint, every deadline and both legs' geometry are
derived at run time from the live wall positions, the two latched posts and the two
readable numbers on the watchmen. Leg 2 reverses the roles by geometry (not by index),
slides its alcove, and lands the last-seen spot thousands of uu from leg 1's; a per-run
jitter drawn from the hardware timestamp means two runs of the same submission do not
even see the same numbers.

## Design faults found before this was authored, and what was done

The first design was reviewed adversarially and the review found two things that were
fatal rather than merely wrong. Both are fixed here; the full list is in `notes.md`.

1. **The prompt was self-contradictory.** It demanded a watchman close to five metres
   while it could see, and never come within nine metres while it could not — so a
   watchman that legitimately closed was in breach the instant sight broke. The blind
   rule now carries a five-second grace AND an exemption for a watchman standing on the
   spot it was sent to, which makes it unfailable by a correct answer whatever the
   run-time geometry turns out to be, while still catching a chaser by a factor of four.
2. **Half the staging preconditions were functions of submission behaviour**, so a
   misbehaving submission could route itself into a non-graded verdict. Everything a
   submission can cause — a moved watchman, a changed pace or sight range, a re-labelled
   or destroyed watchman — is now a NAMED graded FAIL. Only geometry the fixture itself
   stages can end a run as `HARNESS-PRECONDITION`.
