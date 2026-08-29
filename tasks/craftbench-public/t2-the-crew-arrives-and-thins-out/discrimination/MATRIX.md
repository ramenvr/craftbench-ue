# Discrimination matrix — t2-the-crew-arrives-and-thins-out

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs; the
per-checkpoint named gates carry the discrimination.

> **EVERY NUMBER BELOW IS PREDICTED, NOT MEASURED.** Nothing on this task has been
> compiled or run: the L1 build, the two L2 legs, and `cb refgate` are all still ahead
> of it, and `Content/Maps/t2-the-crew-arrives-and-thins-out/L_CrewDeck.umap` does not
> exist until `authoring/author_map.py` has been run in an attended editor. Every time,
> spot set, badge code and gate attribution here is derived by hand from
> `CrewMusterFunctionalTest.cpp` and the committed reference, and is exactly as good as
> that reading. Three tasks are already in this tree whose MATRIX claims a PASS the run
> does not give; do not promote a single figure here to "observed" without the log line
> that says so.
>
> **Revised 2026-08-19 after an adversarial review.** Two of this file's claims were
> not true of the fixture as written and are now true of the fixture as fixed: the badge
> gate checked roster MEMBERSHIP and never roster ORDER (so "spot 4 must show 73" was
> asserted by no code at all), and a hand that stopped answering to the `CrewHand` tag
> was silently forgotten (so untag-and-hide read as "sent ashore"). A third finding —
> three gates keying on the level-wide count of hand actors, which an off-deck pool
> would fail with nothing in the prompt to warn it — was closed by DISCLOSING the
> contract in the prompt ("nobody waits in the wings"), not by loosening the gates. The
> rows below reflect the fixed fixture and are, like everything else here, PREDICTED.

| Submission | Overall | Named substring(s) | Why it lands there and not somewhere else |
| --- | --- | --- | --- |
| `../reference` | PASS (predicted) | `Test Completed. Result={Success}` | The reference changes only `MusterBoardActor.{h,cpp}` — the board is the host because every other piece of the deck is a placed instance in a map the agent cannot edit, so a new class would never be instantiated. It latches the call on the plate's RISING edge and refuses to re-arm while a call runs; it books each arrival off the gap read at the moment of booking; it seats each arrival on the lowest-numbered free spot resolved through its OWN board name; it issues the first roster code not yet spent tonight and never recycles one; it resolves every slate place to a BODY before destroying any of them, and it EMPTIES the arrival slot rather than removing it so the remaining places do not shift; and it drives the lamp row off live occupancy every frame. Nothing in it knows which board is which or which watch it is on, which is exactly why the mate's re-chalk between watches costs it nothing. Predicted final state: spot 1 = 41, spot 3 = 53, spot 4 = 73, spot 6 = 67; lamps 1/3/4/6 burning, 2 and 5 dark; the twin board untouched throughout. |
| `empty` | FAIL (predicted) | `TheDeckFillsToTheCalledNumber: the board called for ` | An empty submission is an empty directory overlaid on the substrate, so the graded tree is the committed scaffold verbatim. **L1 is green** — the four scaffold actors compile, `SetLampLit`, `SetBadgeCode` and `IsSomebodyStandingHere` all exist and work, and nothing calls any of them. The run then gets further than one might expect, and the reason is worth writing down: the deck's honest starting state is *empty and dark*, and the empty submission produces exactly that, so the phase-1 baseline (4 s at the quiet spot, both decks empty, every lamp put out in `BeginPlay`) **passes every gate**. It also survives the first judged window of the fill, at about contact + 0.75–1.25 s, where the fixture's own model still expects nobody aboard. It dies on the **first plateau after the first expected arrival** — the working board was chalked to bring one aboard every 2.0 s, so at roughly contact + 2.8 s one hand should be standing on spot 1 and none is. `TheyArriveOneAfterAnother` is deliberately disarmed until at least one of a call's hands is aboard, precisely so that "nobody ever turned up" is named by the fill gate rather than by the cadence gate. |

Both legs run **twice**, at `-FPS=60` and `-FPS=20`, in separate PIE processes
(`fps_legs: [60, 20]`); all legs must pass. Predicted world game-time to the empty
leg's failure: about **12 s** (3 s drop-in + 4 s baseline + ~2.6 s to reach and rest on
the call plate at the character's 500 uu/s + ~2.8 s into the fill), well inside the
first two scheduled checkpoints. Predicted world game-time for a full reference run:
about **74 s** against a 200 s sentinel and a 202 s `TimeLimit`.

## Requirements table

The full prompt-requirement to gate mapping is in `../task.md` under
**Requirement-to-assertion map**. It has 19 rows, and every one names the gate that
checks it and the condition under which that gate does not run.

## Which gate names which wrong answer

Written down because the fixture's gate order makes this deterministic, and because a
gate whose named failure is always stolen by an earlier gate is a dead gate. Evaluation
order per judged frame is `TheDeckIsNotYoursToRearrange` → `TheQuietBoardStaysQuiet` →
`NobodyArrivesUncalled` → `TheyArriveOneAfterAnother` → `TheDeckFillsToTheCalledNumber`
→ `TheRightHandsAreLeftStanding` → `NobodyShufflesAlongTheDeck` →
`TheSurvivorsKeepTheirOwnBadges` → `TheBoardShowsWhoIsAboard`. **All predicted.**

| Wrong answer | Named gate it dies at | When, and why that gate and not another |
| --- | --- | --- |
| nothing at all (the unmodified scaffold) | `TheDeckFillsToTheCalledNumber` | watch 1, first plateau, ~contact + 2.8 s. See the table above. |
| the whole watch turns up in one loop on the frame the plate is stepped on | `TheDeckFillsToTheCalledNumber` | watch 1, the **N = 0** window at ~contact + 0.75–1.25 s: six aboard where the chalked gap says none should be yet — "expected spots none and found 1, 2, 3, 4, 5, 6". NOT the cadence gate: that one is disarmed while the expected count is still zero, so that "arriving at the wrong pace" is never said about a watch that did not arrive one at a time at all. `task.md` anti-gaming note 3 names this gate. |
| a fill paced at half the chalked gap, or off a hard-coded constant faster than it | `TheDeckFillsToTheCalledNumber` | watch 1, the N = 0 window again: the first arrival lands inside a window where the model still expects an empty board. |
| a fill paced off the gap **cached at the first call** | `TheyArriveOneAfterAnother` | watch 2, whose chalked gap is 2.6 s against watch 1's 2.0 s. Predicted: the cached pace puts a second hand aboard at ~contact + 4.0 s while the board's live gap says one, inside the N = 1 plateau (~3.4–4.4 s). This is the gate's live case — it needs a fill that is genuinely *arriving*, just at the wrong pace. |
| a fill paced by counting ticks | whichever leg it is wrong on | a count fitted at 60 Hz runs 3x SLOW at 20 Hz and dies at `TheDeckFillsToTheCalledNumber` on the 20 Hz leg; a count fitted at 20 Hz runs 3x FAST at 60 Hz and dies at the same gate in the N = 0 window. Either way one of the two `fps_legs` is red, which is the whole reason the task runs both. |
| walking the slate over a live array and removing as you go — `for (Place : Slate) { Crew[Place-1]->Destroy(); Crew.RemoveAt(Place-1); }` | `TheRightHandsAreLeftStanding` | the **first** stand-down. Slate {2,4,5} over a list that shifts under the loop sends places 2 and 5 ashore and then runs past the end or takes place 6 — the right *number* of hands, the wrong hands. The message prints the slate as read, the arrival-order-to-spot map the fixture OBSERVED, the spots it expected cleared and the spots actually cleared, so the diagnosis is in the failure line. |
| reading the slate as standing-spot numbers | `TheRightHandsAreLeftStanding` | the **second** stand-down, and nowhere earlier — on watch 1 the deck starts empty so arrival place k lands on spot k and the two readings are identical by construction. Watch 2 calls 3 into the vacated spots 2/4/5, so place 1 is spot 2 and place 3 is spot 5; a slate of {1,3} therefore clears 2 and 5, not 1 and 3. This is the coupling the whole task exists for. |
| restarting the roster from the top on the second call | `TheSurvivorsKeepTheirOwnBadges` | watch 2's first arrival. The re-chalked roster is the same list EXTENDED, not a fresh one, so restarting re-issues 41 — a code the watch-1 survivor on spot 1 is still visibly wearing. The ledger spans the whole run, so the message names both the earlier holder's spot and the new one. |
| recycling the badges of the hands that went ashore (a free-list) | `TheSurvivorsKeepTheirOwnBadges` | watch 2's first arrival. 47, 59 and 61 leave the deck at the first stand-down and must never appear again; the prompt says so in as many words. The right answer in most pooling code, the wrong one here. |
| reading the chalk once in `BeginPlay` and caching it | `TheSurvivorsKeepTheirOwnBadges` or `TheyArriveOneAfterAnother`, whichever the cached value breaks first | the **first** call, not the second: `BeginPlay` fires on placed actors before `PrepareTest`, and the committed `.umap` bakes call 4 / gap 1.9 / roster [5,7,9,15] against a staged call 6 / gap 2.0 / roster [41,…]. A badge showing 5 is not on the board's live roster; a fill of 4 into a call for 6 is a count failure. `author_map.py` refuses to save a level whose baked values match the staged watch, so this can never quietly become unreachable. |
| doing it to every board, or to "the" board found by a level-wide search | `TheQuietBoardStaysQuiet` | the first judged frame at which anything lands on the twin — zero hands within 200 cm of any of its six spots, every one of its lamps dark, and not one of its own roster codes (11/13/17/19/23/29/31) on any badge anywhere in the level. The twin's chalk differs from the working board's on all four values, so a submission that grabbed the wrong board's numbers also trips the fill and cadence gates. |
| `SetLampLit` called with a 0-based array index instead of a spot number | `TheBoardShowsWhoIsAboard` | the first judged frame after the first arrival. `SetLampLit` takes a SPOT NUMBER and maps `Index = SpotNumber - 1` internally, so `SetLampLit(0, true)` lights nothing and spot 6's lamp is never reachable — a lamp row that is silently off by one with no error anywhere. The gate reads the point light's own intensity, and it runs LAST and only on a frame where the armed occupancy gate has already agreed, so a right occupancy with a wrong lamp row is always named here. |
| modelling everything correctly and never touching a lamp or a badge | `TheBoardShowsWhoIsAboard` (lamp) / `TheSurvivorsKeepTheirOwnBadges` (badge) | the first judged frame after the first arrival. Nothing private is ever graded: the board deliberately carries no "current watch" or "aboard count" property for a submission to set and be credited for. |
| compacting the row by moving the survivors so the spots stay contiguous | `NobodyShufflesAlongTheDeck` | the frame a survivor moves more than 2 cm from where it arrived. Reaching this gate rather than the stand-down gate is deliberate: the fixture keys occupancy off the spot each hand ARRIVED on, so a moved-but-not-respawned hand still reads as holding its own spot and `TheRightHandsAreLeftStanding` passes — this gate is the only one that sees it. A submission that instead DESTROYS the survivors and respawns them compacted dies one gate earlier, at `TheRightHandsAreLeftStanding`. |
| a repeating timer that keeps calling after the watch is full | `NobodyArrivesUncalled` | the first judged frame after the stand-down closes the fill window (phase 6/7/8): the hand count rises with no call running. Inside a fill window this gate stands down and the count belongs to the fill gate, which is why the extra arrival is caught after the window and not during it. |
| a fill on `BeginPlay`, or any hand aboard before a plate is stepped on | `NobodyArrivesUncalled` | phase 1, the 4 s baseline — "every standing spot starts empty, and N hand(s) are already in the world before any call plate has been stepped on. A hand is in the world only while it is aboard". |
| pre-creating a pool of hands parked off the deck in `BeginPlay` and moving one onto a spot per arrival | `NobodyArrivesUncalled` | phase 1, the same 4 s baseline, on the level-wide count. This is a DISCLOSED contract, not a hidden one: the prompt's "nobody waits in the wings" paragraph says a hand is in the world only while it is aboard and that there is never one anywhere off a numbered spot. (Before 2026-08-19 the prompt did not say it, and this row was a false FAIL on the standard pooling shape for exactly this task family — the finding that added the paragraph.) Such a submission also dies at `NobodyShufflesAlongTheDeck`, since a hand first seen off-deck and later moved onto a spot has moved. |
| taking the badge from the wrong end of the unspent pool — `Avail.Pop()`, or draining a `TSet<int32>` in hash order | `TheSurvivorsKeepTheirOwnBadges` | watch 1's **first** arrival: 67 (or whatever hash order yields) where 41 was due. Every other clause in the gate is green — the code is on the live roster, no two hands wear the same one, none is ever re-issued — which is exactly why the ORDER is asserted separately, at the instant a code enters the night's ledger. The message prints the roster as read, the codes already spent, and the code that was due. |
| sending a hand ashore by dropping its `CrewHand` tag (with or without hiding it) instead of destroying it | `TheRightHandsAreLeftStanding` | the first stand-down's settled window. The fixture forgets a tracked hand only when its actor is genuinely gone, so an untagged-but-present hand keeps holding the spot it arrived on: the deck reads as having cleared nothing, and the message adds "N of them stopped answering as a hand while still standing on the deck". A hand that has entered `Destroy()` is forgotten on the same frame, so a correct submission is unaffected. |
| clearing the chalk (e.g. writing `HandsToCall = 0`) so the call cannot re-arm | `TheDeckIsNotYoursToRearrange` | the frame it does it, and this gate is the one place where "ceremonial" would be exactly wrong: the fixture's own model reads the boards' LIVE chalk, so without this gate a submission that rewrote a dial would make the model agree with whatever it did. Evaluated every frame from the first, and re-checked unconditionally before any deadline or sentinel overrun is written off as a staging fault, so a submission cannot move a plate, make a phase unreachable, and be paid for it with a non-graded exit. |
| parking a hand somewhere that is not a standing spot | `NobodyArrivesUncalled` outside a fill window, `TheDeckFillsToTheCalledNumber` inside one | a hand more than 120 cm from every standing spot counts as standing on none. 120 cm and not 2 cm: the spots are 500 cm apart so it cannot confuse two of them and cannot mask a wrong answer, while 2 cm would fail a correct submission that nudges a hand for footing. |
| a one-shot latch that calls once and never again | `TheDeckFillsToTheCalledNumber` | watch 2, the first plateau after its first expected arrival (~contact + 3.4–4.4 s at the staged 2.6 s gap): "the board called for 3, 4 should be aboard … expected spots 1, 2, 3, 6 and found 1, 3, 6". The **4** is not a typo for the call size — the message prints the whole expected OCCUPANCY (three watch-1 survivors held over, plus the one arrival due), which is why a substring grep for this row must not include the call size and the count as one phrase. It survives the N = 0 window (~contact + 0.75–1.25 s), where {1,3,6} held over is exactly right. **Not** `TheDeckThinnedOutTwice`, and this is a correction to the obvious reading — see the note below. |

### `TheDeckThinnedOutTwice` is a BACKSTOP, not the one-shot gate

Recorded rather than glossed, because the honest reading of the fixture and the
intuitive reading differ. `CallsMade` is the FIXTURE's own count of plate contacts, so
it reaches 2 whenever the drive completes regardless of what the submission does;
`FillsCompleted` and `ThinningsSeen` only increment on judged frames where the fill and
stand-down gates already AGREED. So a one-shot latch never reaches the run-level gate —
it is named by `TheDeckFillsToTheCalledNumber` on watch 2, about 50 s earlier and with a
far more useful message. What is left for `TheDeckThinnedOutTwice` is the case where
every per-frame gate stayed green and a whole window nevertheless never completed
(chiefly the sentinel path, where the drive is still running at t = 200 s). That is
worth keeping as a backstop, and it costs one checkpoint — but it should not be
described as the thing that catches the latch. `task.md`'s requirement-table row "it is
not one-shot" already says the same thing in its skip column ("a run that fails a
per-frame gate earlier never reaches it, which is the more useful message"), so the two
documents agree; this section is the longer form of that sentence, not a correction to
it.

## What carries the discrimination without variants

**Two subsystems whose outputs are each other's inputs.** The first stand-down does not
merely remove hands — it CHOOSES the geometry the second watch fills. Because spots
2/4/5 come free and 1/3/6 stay held, watch 2's arrival order maps onto a non-contiguous
spot set, and that is the only place in the run where "the second to turn up" and
"standing spot 2" disagree. Get the seating right and the removal wrong, or the removal
right and the seating wrong, and a different named gate fails; get both right and the
badge map on the final frame (spot 4 must show 73) is a joint function of the two —
and, since 2026-08-19, actually enforced: the badge gate checks the ORDER codes are
issued in, not merely that each code is somewhere on the roster, so 71 on spot 4 is a
named FAIL rather than the clean PASS it used to be.

**The fixture OBSERVES the arrival order instead of assuming it.** The expected cleared
spots are derived from the arrival-order-to-spot map the fixture actually watched, so
`TheRightHandsAreLeftStanding` is a statement about the removal rule ALONE and a wrong
seating rule is named by the fill gate instead. Without that, one bug would fail two
gates and the verdict could not say which subsystem was broken.

**Every load-bearing number is read off an actor and re-chalked twice mid-run.** All
eight chalked values are stamped over the committed map before the character has walked
anywhere, and all eight again at the watch change. A hard-coded answer is wrong from the
FIRST call, and the authoring script refuses to save a level whose baked values match
the staged watch or share a roster code with either staged roster — so this can never
degrade into a decoy without the authoring step failing loudly.

**The rosters name their own source.** The working board's codes, the twin's codes and
the codes baked into the committed level are three disjoint sets, which is what lets
`TheQuietBoardStaysQuiet` assert "not one code of its own roster was issued to anything
anywhere" rather than merely "the twin's spots are empty", and what makes a
map-read-offline submission distinguishable from a board-read one.

**Every tolerance is a WIDENING of the disclosed contract.** The prompt promises the
deck half a second to catch up; the fixture suppresses judgement for 0.75 s after its
own model changes, for 0.75 s either side of any plate contact or release, and inside a
guard band of `max(0.75 s, 0.30 x gap)` either side of every expected arrival — and it
refuses to START below a 2.0 s staged gap, which is what keeps the judged plateau
between two bands at least 0.5 s wide (ten frames on the 20 Hz leg). The one tolerance
that stays tight, 2 cm, is a delta on a single actor and on the deck's own furniture,
never a radius that could confuse two things 500 cm apart.

**The staging is attributed, never scored.** Wrong actor counts, a board that does not
expose its chalk, spot numbers that are not 1..6 contiguous, a staged gap below the
floor, a call for more hands than there are free spots, a roster that would run out, a
twin plate within 1,500 uu of the lane the drive walks, a standing spot within 600 uu of
it, an unplayable input lane, or a drive phase that overruns its derived deadline all end
the run as `HARNESS-PRECONDITION`. `authoring/author_map.py` computes and re-reads every
one of those off the PLACED actors before it is allowed to save, so a staging fault costs
an authoring re-run rather than a graded build-and-run cycle.

**And one precondition guards the fixture against ITSELF.** Phase 3's step-off-and-back
is the only thing that grades "a call runs to its number whether or not anybody is still
on the plate", and its two instants are C++ constants while the schedule is data. The
fixture's fill window stays open from the call plate's contact until the next stand-down
— wider than the prompt's "while a call is still running" — so if a future schedule edit
shrank watch 1 enough that the step-back landed after the fill had finished, a
submission that correctly began a fresh call on the re-contact would be judged against a
model expecting nobody new and FAIL for being right. `ValidateSchedule` asserts the
relationship (`watch 1's fill end >= step-back + 2.5 s`; today 12.0 vs 10.0) and refuses
to start otherwise, so that edit costs an attributed refusal instead of a wrong verdict.
