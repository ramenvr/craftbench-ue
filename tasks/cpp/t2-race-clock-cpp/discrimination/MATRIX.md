# Discrimination matrix — t2-race-clock

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `the round ran its ten seconds, each coin added its own value` | The round derives its clock from world time rather than accumulating it, so it cannot drift; coins ask the round whether it is still running BEFORE consuming themselves, so both halves of "the score is final" hold. Measured: coins worth 15 + 40 + 25 + 60 collected inside the round -> 140 by t=4.0, then the drive HELD until t=11.2 and walked into two more coins AFTER the whistle -- score stayed 140 and neither coin vanished. The control coin was never touched and kept its value. |
| `empty` | FAIL | `ReadoutsShowTheLiveValues: the state readout shows` + `with a round state of` | The unmodified scaffold compiles, so L1 is green. All three readouts ship showing frozen placeholder text (`SCORE --`, `--`, `----`), which is exactly what the prompt describes, so the state readout disagrees with the round's own state on the very first frame. |

## Two requirements added 2026-08-18, after the owner played it

**The readouts have to face the player.** They shipped at a fixed rotation and
the reference left them there -- legible from exactly one direction. The gate
samples the angle every frame and wants 80% of samples within 35 degrees.

**The round can be run again.** A lit pad in front of the board; stepping onto it
after the whistle starts a fresh round, full clock and no score. That is more
than a convenience -- and it made FIVE existing gates wrong:

| gate | what it had assumed | now |
|---|---|---|
| `ClockTracksTheRound` | seconds left = 10 minus time since the LEVEL began | minus time since THIS round began |
| `RoundRunsForTenSeconds` (both directions) | the round ends 10 s into the level | 10 s into the round |
| `ScoreOnlyRisesFromCoins` | the score never decreases | re-baselines when a round starts |
| `ScoreIsFinalAfterTheRound` | after one whistle the score never changes again | re-arms at the next whistle |

That is the part worth keeping: **"the level contains exactly one round" was
never written down anywhere.** It was distributed across five gates as an
unexamined assumption, and every one of them read as a correct-looking check
right up until the level gained a second round.

## What carries the discrimination without variants

The clock is checked **continuously against the world's own play time**, not only at
the end, so a round that jumps straight to zero, or drifts and then snaps right, fails
while it is happening rather than passing on its final value:

- `ClockNeverGoesNegative` — every frame.
- `ClockTracksTheRound` — every frame, against `10 - world time`, 1.0 s of allowance.
- `RoundStateIsOneOfTwoWords` — every frame; `InProgress` and `TimedOut` are the only
  values the state may EVER take, including during the transition.
- `RoundRunsForTenSeconds` — fails if the state flips before 9.5 s or has not flipped
  by 10.5 s.
- `ClockReadsZeroWhenTheRoundEnds` — the clock must read 0 at the instant the state
  flips, not merely settle there later.

And the score half:

- `CoinAddsItsOwnValue` — when a coin visibly goes, the score must rise by exactly
  THAT coin's `PointValue`, checked against a fixture-owned running total.
- `ScoreOnlyRisesFromCoins` / `ScoreIsFinalAfterTheRound` — the score may never fall,
  and may not change at all once the whistle has gone.
- `TheUntouchedCoinSurvives` — the control is 300 cm off the route line against a
  ~94 cm contact reach (60 cm region + 34 cm capsule), better than 3x clearance. It
  must stay visible, on its spot, and keep its own value.
- `ReadoutsShowTheLiveValues` — all three faces are read by COMPONENT NAME and must
  agree with the properties, after the round as well as during it.

**The drive is what makes "final after the whistle" measured rather than promised:**
four coins are collected inside the round, then the drive HOLDS until 11.2 s and only
then walks into the last two. Both are still standing at the end, and the score never
moved.

The schedule ends with a SENTINEL far past any real grade, because the base declares
success the moment the last scheduled checkpoint is crossed; the gates that are
vacuous unless their leg happened (the round ended, four coins were consumed, the
after-whistle coins were reached) are evaluated there with their own messages.
