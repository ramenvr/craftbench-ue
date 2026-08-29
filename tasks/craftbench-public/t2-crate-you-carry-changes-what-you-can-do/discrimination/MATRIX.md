# Discrimination matrix — t2-crate-you-carry-changes-what-you-can-do

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | One carry flag drives all five channels. The crate is moved every frame with `SetActorLocation(Hold, /*bSweep=*/true)` so the world still stops it; the crate and the capsule are each told to ignore the other while it is held, in **both** directions; `MaxWalkSpeed` is halved from the value read off the movement component in `BeginPlay` and put back on release; `CanJumpInternal_Implementation` refuses below the input layer and `SetJumpAllowed` is re-asserted every frame in both directions; the release traces straight down and sets the crate on what it finds. Each plate re-derives the SET of crates resting on its own pad every frame, sums their live `MassKg`, compares with its own live `MinimumHoldKg`, and tells its own `LinkedDoor`. Nothing is cached, so the re-price costs it nothing. |
| `empty` | FAIL | `cm from a crate with empty hands` | The unmodified scaffold compiles, so L1 is green, and the drive's first two legs (the empty-handed lane walk and the empty-handed jump) even pass. It then walks up to the west crate, stands 240 cm from it with nothing riding, and `TheCrateRidesInFrontOfYou` fires at 2.0 s. |

**Full empty-submission failure line** (the quoted cell above is a contiguous span
of one source literal, per the verbatim-substring rule — the gate name and the
detail are joined by a `Printf` and therefore live in different literals):

```text
TheCrateRidesInFrontOfYou: the character stood 240 cm from a crate with empty
hands for 2.0 s and nothing was riding in front of it (the reach is 250 cm)
```

## Requirements table

See the *Requirement-to-assertion map* in `../task.md` — every prompt requirement,
the assertion that checks it, and the condition under which that assertion does
not run. Two entries there are load-bearing and worth repeating:

- **Nothing is skipped silently.** Where a speed gate needs at least 20 clean
  samples, falling short is a **FAIL naming the gate**, not a skip. The
  constant-denominator rule forbids a submission improving its ratio by making a
  check unreachable.
- **Two conditions are suspensions the PROMPT states**, not hidden ones: the ride
  band is not asked for in the first 0.5 s after a pick-up, nor within 600 cm of a
  wall. Both appear in the prompt in those words. The no-clipping gate is never
  suspended.

## What carries the discrimination without variants

**The re-price is the whole anti-hardcoding mechanism.** Part way through the run,
with the character standing still, empty-handed, and every crate at rest, the
fixture rewrites `MassKg` on all three crates and `MinimumHoldKg` on both plates.
Round 2's numbers are chosen so that the low plate goes from 60 kg over a 30 kg
threshold to 76 kg under a 90 kg one, and the high plate from 70 over 55 to 48
under 60. **Two doors that are standing open have to shut, and not one crate has
moved.** A table of thresholds, a constant, a value read off the map, or anything
cached in `BeginPlay` leaves both doors up and fails at
`TheDoorDropsWhenTheWeightComesOff` with both numbers in the message. The crates'
own painted labels are derived from the property every frame, so the picture on
screen follows the price and a human reviewer sees what the grade sees.

**The wall gate separates right from wrong by 2x, on arithmetic that is written
down.** Capsule radius 42 (`ThirdPersonCharacter.cpp` `InitCapsuleSize(42, 96)`),
hold distance 330, crate half-extent 40, wall 800 cm deep along the push axis. A
carry that teleports leaves the crate 248–328 cm inside the block: 80 cm of
overlap on **every** axis against a 40 cm allowance. A swept carry stops the crate
at the face: 0 cm. The authoring script refuses to save a wall too shallow to
contain the wrong answer, so the gate can never quietly become undecidable.

**The ride band and the wall gate are not made mutually unsatisfiable.** A crate
correctly stopped by a wall cannot also be 290–380 cm in front of a character
standing at that wall — so within 600 cm of a wall the fixture judges only the
no-clipping gate, and the prompt says so in the same words. Getting this wrong
would fail the only correct answer there is.

**One removal has to keep a door open and another has to shut one.** Step 5 of the
staged sequence lifts one of two crates off the high plate and the door must
**stay open** on the 70 kg still resting there; step 9 lifts one crate off and the
door must **shut**. A `bool` or a single `AActor*` occupant cannot satisfy both.

**Both halves of every movement rule are asserted.** Speed is gated carrying
(35–65%) and after setting down (85–115%); jumping is gated carrying (never leaves
the ground) and empty-handed (must leave it). Suppressing jumping and forgetting
to re-enable it fails `EmptyHandedYouJumpNormally`; halving walk speed permanently
fails `WalksAtItsNormalTopSpeedEmptyHanded` by name rather than being excused as a
harness error.

## Staging faults that are attributed, never scored

All of these end the run as `HARNESS-PRECONDITION` (uncredited), because none of
them is anything a submission got wrong:

- the yard is not staged as authored (wrong counts of crates, plates, doors, walls);
- the possessed pawn is not the tagged `HaulHero`, or has no visible body;
- a crate or plate no longer exposes `MassKg` / `MinimumHoldKg` as a readable
  number, or a plate's `LinkedDoor` is unset, redeclared, or shared with the other
  plate — a task made unwinnable by a rename is a staging fault, not a wrong
  answer;
- any of the 13 staged mass-vs-threshold comparisons clears by less than 8 kg, or
  the second price list does not change a verdict — a gate that could round either
  way, or that could never fire, must not run at all;
- a route leg would pass within 290 cm of a crate it is not fetching (it would be
  picked up and the script would desynchronise), or would run into a wall.
