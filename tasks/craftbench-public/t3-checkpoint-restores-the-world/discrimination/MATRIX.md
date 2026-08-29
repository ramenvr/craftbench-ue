# Discrimination matrix — t3-checkpoint-restores-the-world

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The director keeps three things and makes them agree: the pad stood on most recently, a **three-way** place per coin (on its stand / in hand / over the line), and a snapshot of the coin places plus the door open-set taken at **every** mark. A death restores the snapshot intersected with what has been banked since, then **derives** CARRIED from the result and never writes BANKED. Nothing in it knows how many props there are, where any of them stands, or what the counter opened at. |
| `empty` | FAIL | `YouComeBackAtTheLastPadYouStoodOn: at death ` | The unmodified scaffold compiles, so L1 is green. Every prop works: the plate opens door 0, the coin is taken, the hot floor announces the touch. Nothing listens, so two seconds after the first life ends the character is still standing on the hot floor, roughly 4,000 uu from the way in. |

**The empty leg's rendered line** (for eyeballing an `l2_pie.log`):

```
YouComeBackAtTheLastPadYouStoodOn: at death 1 the mark was the spot the character
walked in from, no pad having been stood on yet, and 2.0 s later the character is
<N> uu away from it at X=... Y=... Z=..., still standing on hot floor. A life that
ends on hot floor puts them back on the mark
```

The MATRIX cell above is the **contiguous source literal** up to the first
format placeholder, so the oracle's grep cannot straddle a substituted value.

## Requirements table

Full map in `../task.md` § *Requirement-to-assertion map*. The short form:

| Prompt requirement | Gate | Skipped when |
| --- | --- | --- |
| back at the pad stood on **most recently** | G1 `YouComeBackAtTheLastPadYouStoodOn` | never |
| before any pad, back at the way in | G1's pre-pad branch | never |
| the lit pad is the mark, at most one lit | G2 `TheLitPadIsTheMark` | 1.0 s after each mark and each death window |
| the doors come back to the mark moment | G3 `TheDoorsComeBackToHowTheyWereWhenYouArmed` | never |
| nothing moves a door except a plate or a death | G3's transition rule | never |
| the coins come back to the mark moment | G4 `TheCoinsComeBackToWhereTheyWereWhenYouArmed` | never |
| BANKED moves only at the line, by what was in hand | G5 `WhatWentOverTheLineStaysOverTheLine` clause 1 | never |
| a banked coin never comes back | G5 clause 2 | never |
| CARRIED always says what is in hand | G6 `TheCounterAgreesWithYourHands` | 1.0 s after a ledger change or a death window |
| the yard still works afterwards | G7 `TheYardStillWorksAfterYouComeBack` | if the walk never reaches the re-use stops — G8 then FAILs |
| able to walk on after coming back | G8 `TheYardRanAllThreeDeaths` mobility clause | never |
| every graded fact read off the world | not a gate — see below | — |

## What carries the discrimination without variants

**Three deaths, three different right answers.** Death 1 has no mark, so the
right answer is the opening state. Death 2's mark was set with two doors open
and two coins in hand — and three coins have crossed the line since. Death 3's
mark was set with all three doors open and one coin already in hand. Any
submission that computes one restore and replays it is wrong at two of the
three, and each of the three is judged by the same gates, so the message names
which death as well as which prop.

**The counter is the sharpest edge.** `Restore()` deliberately does not touch
CARRIED, so after the coin loop the correct CARRIED is a **count of the answer**,
not the snapshot's number. At death 2 the snapshot's number is 2 and the answer
is 0, and handing back the 2 would make the same coins bankable a second time —
BANKED would then read `open + 6` for five coins. G6 catches the number and
G5 catches the double-bank.

**Everything the gates read is a visible consequence.** A leaf's world position
against that door's own two places, a coin mesh's visibility, a lamp's
intensity, the two numbers on the counter's text faces, the character's
location. No private member is graded, and no `bool` stands in for a light.

**Nothing graded is a constant.** Which pad is the mark, which doors were open
then, which coins were where and what has been banked since are all runtime
events; the fixture builds its own ledger from the same ones the submission
sees. The **coins change places** after death 2 is judged (a cyclic shift among
their own stands), so an answer keyed to a remembered position rather than to a
coin gets every coin wrong from there on. And the whole run is graded **twice at
different frame rates** (`fps_legs: [60, 20]`), so nothing fitted to a frame
count or a wall-clock delay survives. *Honest limit:* the prop inventory itself
— how many, which ids, where they stand — IS a constant in one committed map and
an editor-driving lane can read it. Hard-coding it is not detected; it simply
buys nothing, because no gate is keyed on identity.

## Predicate hazards this design had to get right first

1. **A window anchored on the wrong side makes the task unwinnable for
   everyone.** The props fire on capsule-versus-box overlaps, which begin about
   a capsule radius of travel before the character's origin reaches the box. A
   gate that says "a door may open only within 0.5 s of the fixture seeing the
   character on the plate" would therefore see the door open BEFORE its own
   window opened — an unsanctioned transition at drive stop 1, on every
   submission ever made, including the reference. Every window in the fixture is
   the union of *(the prop's own overlap set)* and *(its box grown by capsule
   radius + half height + 60 uu)*, which is a strict superset of what the prop
   can see. The **mark** ledger is the deliberate exception and stays ungrown,
   because a grown pad box would let the fixture record a stand the pad never
   announced.
2. **The death window has to open before the frame's transitions are read.** A
   correct submission is told a life ended and puts the yard back inside the
   same frame. If the fixture observed doors and coins first and registered the
   death second, that restore would read as "a door shut with nobody dead" — and
   every correct answer would fail. Tick order between two actors is not
   something a fixture may assume, so the death is registered at the top of the
   tick.
3. **The death instant comes from the hazard's own announcement**, not from a
   sampled overlap: the same correct submission has already moved the character
   off the hot floor by the time anything could be sampled. The sampled overlap
   is kept as a second detector for a run where no announcement arrives.
4. **The fixture holds its own input for the whole judging window.** Without
   that it would still be walking the character at the hazard while measuring
   how far they are from the mark — measuring its own drive, at up to 500 uu/s
   against a 200 uu tolerance.
