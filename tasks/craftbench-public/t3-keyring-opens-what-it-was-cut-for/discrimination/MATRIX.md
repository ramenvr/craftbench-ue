# Discrimination matrix — t3-keyring-opens-what-it-was-cut-for

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs. The
discrimination is carried by the nineteen per-stop named gates plus five continuous
guards: an empty submission fails at the first gate that asks whether anything
happened at all, and every gate is independently named and greppable. See
`docs/TASK-AUTHOR-GUIDE.md` step 7 for the reasoning and for what this
deliberately gives up.

Substring law that has bitten sibling tasks in this set, and applies here: a
backticked substring must contain a space or one of `(),.=` **and** fall inside ONE
literal run of the fixture's format string. A bareword tick is discarded as a
parenthetical and the parser then matches the WHOLE cell (which appears in no log); a
phrase spanning a `%s`/`%d` matches the LOG but is not statically anchorable, which
`test_matrix_substring_oracle` rejects. Two ticked literals per row, ALL-of
semantics, each inside its own run.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `[t3-keyring recut] seed=` + `[t3-keyring shift] t=` | A world subsystem holds the ring; the body is re-resolved from the controller every tick; stands are once-only against their own mat; bays are latched and tested all-of over both category slots; the board is redrawn whenever it disagrees with the ring. Both anchors are real fixture literals and neither can appear unless the yard actually staged and actually changed shift, so a run that died before either is not silently read as a pass. |
| `empty` | FAIL | `OnlyTheKeysYouWentToAreGone: the character has stood on stand` + `expected 1 key gone from that stand, found 0` | The unmodified scaffold compiles, so L1 is green and the failure is behavioural. Stops 1 and 2 are free to an untouched yard — the board ships reading `--` and every bay ships shut — and the run dies at **stop 3**, 1.5 s into a 3.0 s stand on the first key stand, with the key still floating over the post and the lamp still lit. |

## Why the empty submission does not die earlier, and why that is right

Two stops precede the one that fails, and an untouched yard passes both:

- **Stop 1** asks the board to read `--` for an empty ring. `ARingBoardActor` ships
  reading `--`, so this is free. It is kept because it is the only stop that measures
  the empty-ring rendering at all, and because a submission that writes something to
  the board at `BeginPlay` fails here.
- **Stop 2** asks bay 1 to be shut with an empty ring. An untouched yard never opens
  anything, so this is free too. It is kept because it is the before-photograph for
  `ADoorAnswersOnlyToTheKeysItAsksFor`, and because a submission that opens
  everything at `BeginPlay` fails here rather than sliding through to stop 4 and
  looking correct.

Stop 3 is the first stop that asks whether **anything happened**, and it is
deliberately ordered stand-first, board-second: an untouched yard has to fail on the
thing that plainly did not happen (the key is still there) rather than on a readout
that only follows from it.

## What carries the discrimination without variants

Nineteen stops, each with its own named message, chosen so a partially-correct
submission cannot slide through:

- **Stops 4 and 5 are the consumed-key pair.** Bay 1 opens for the first key; bay 2
  is painted with the same key. A ring modelled as a pool of spendable keys passes
  stop 4 and dies at stop 5, at `AKeyOpensEveryDoorItWasCutFor`'s own literal, and
  crucially **before the board is next sampled** (stop 7) — so the bug fails where it
  can be read rather than as a board mismatch three stops later.
- **Stop 6 is the any-key-opens-any-door stop.** Bay 3 is painted with a category
  carried only by one of the three stands the drive never visits.
- **Stop 11 is the ContainsAny-instead-of-ContainsAll stop.** The character stands on
  the two-category bay's mat holding exactly one of its two categories.
- **Stops 9, 10 and 12 are the shift change.** The board is wiped, the body is
  retired, a fresh one takes over. Stop 10 asks for the ring back on the board; stop
  12 asks a bay that was never opened before the swap to open for a body that never
  fetched its key. A ring living on the character fails both; a ring that survives but
  is only ever drawn from the pickup handler fails the first.
- **Stop 14 is the cached-pointer stop.** The fresh body stands on the third stand's
  mat. A manager that stored `GetPlayerCharacter` in `BeginPlay` has worked perfectly
  for eighty seconds and is now holding a destroyed pawn; nothing happens.
- **Stop 16 is the one stop that cannot pass unless the ring is genuinely ONE ring
  across the swap**: the two-category bay needs a key fetched by the retired body and
  a key fetched by the fresh one at the same time.
- **Five guards run every frame**, so there is no gap between samples to thread: a bay
  that opened may never read shut again; no bay may be open unless every category it
  asks for is in the generous held-model AND somebody has stood near its mat; no stand
  may read empty unless somebody has stood near it; and every prop must still exist,
  still be within 2 uu of where the yard staged it, and have a panel that has
  travelled either nothing or one slide.

## The one-sided margins, and why they cannot false-FAIL correct work

Every fixture-side number that is not disclosed is leniency in the safe direction:

| Number | Value | Direction it biases |
|---|---|---|
| stop depth into a mat | 0.50x (stands), 0.65x (bays) | deep inside; the worst 3D reading at the worst settle point is 263 uu against a 400 uu stand mat and 547 uu against a 760 uu bay mat, both inside the 0.75x audit floor |
| arrival tolerance | 45 uu | at most 0.15x of the smaller mat, asserted |
| accusing "has been near" model | 1.5x the prop's own radius | the fixture will not accuse until the character was half again as far out as the mat |
| route clearance from anything unreached | 2.0x, at stops and at 48 samples per leg, asserted | 0.5x of daylight behind every accusation, so no accusing gate is vacuous |
| settle floor | 1.5 s, against a disclosed 0.5 s | three times the budget the prompt gives |
| open threshold | 0.9x of the bay's own `SlideUu` | anything short of a full slide reads SHUT, so a mid-animation panel is never called open early; the dwell is 3.0 s and the sample is at 1.5 s |
| watchdog | 3x the straight-line walking time plus 25 s | and it splits by cause: a shut panel across the blocked leg is a graded FAIL, anything else is a HARNESS fault |

## Reproducing a run

The six category names are re-cut per run from a seeded shuffle, so two runs of the
same submission read differently on the board. The seed is on the
`[t3-keyring recut] seed=` line; pass `-KeyYardSeed=N` to the editor to pin it. Every
FAIL message quotes the board verbatim and the ring the yard expects, so a mismatch is
legible without the seed.
