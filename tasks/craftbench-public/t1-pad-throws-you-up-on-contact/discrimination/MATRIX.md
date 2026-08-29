# Discrimination matrix — t1-pad-throws-you-up-on-contact

The self-validation oracle: the reference must PASS, and every variant plus the
empty leg must FAIL **at the predicted gate, via the named substring**. A
wrong-reason FAIL (an L1 build failure, a different gate, `SANDBOX-REJECT` exit 4)
means the gates are NOT discriminated — fix them, or relabel the task for the
weaker property it actually tests.

Each variant below is aimed at a **different** named gate. That is the point: if
several variants all failed the same gate, the other gates would be unproven and
could be dead without anyone noticing.

## Three parser rules this file is written against

All three were learned the hard way; the second cost a full 5-leg run.

- **One parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table repeating a label silently
  overwrites the first — and a table without a "substring"/"message" header
  yields an empty substring, so the leg can never be credited. There is
  therefore **exactly one table with variant rows** in this file; everything
  else is prose.
- **A variant cell must contain a `/`.** `parse_matrix` classifies a row as a variant
  only when `"/" in first` (`discriminate.py:286`), so a bare `short-launch` is silently
  DROPPED — the leg still runs (legs come from the on-disk directory listing, not from this
  file) but it carries no expected substring and reports `no-named-assertion`. Measured
  2026-08-17: all three variants here were written without the slash and all three were
  dropped, while `reference` and `empty` parsed fine because they take separate branches.
  Write `` `short-launch/` ``, with the trailing slash.
- **Every expected substring contains a space.** `_extract_substrings` keeps a
  backticked span only if it is "substantive" (contains a space or one of
  `(),.=`); a bare `SCREAMING_SNAKE` id falls through to a branch that returns
  the cell with its backticks attached, which can never match log text. Each
  cell below pairs the gate name with the fixed prefix of the sentence that
  follows it in the fixture, so it is both substantive and a verbatim substring
  of what `FinishTest` prints.

| Submission | Expected verdict | Expected substring | Which gate, and why it is the one that fires |
|---|---|---|---|
| `../reference` | PASS | `pad threw the character on every contact` | All eight gates green. Measured: peak 412 cm, two contact events, control twin unmoved at every checkpoint. |
| `empty` | FAIL | `ContactThrowsSubjectUp: the character walked onto the pad` | Gate 2. The unmodified scaffold compiles, so L1 is green and the failure is behavioural, not a build error. Measured: still grounded at t=2.90, `dz=-1.0`. |
| `short-launch/` | FAIL | RisesThenFallsUnderGravity, anchored on `rose only` + `cm above the` | Gate 3 alone. Re-uses the character's own jump impulse: apex = 700²/(2·980) = 250 cm against the disclosed 300 cm floor. Air time is 1.43 s, so gate 3b must stay green — that separation is why the air-time floor was split out of gate 3. |
| `timer-throw/` | FAIL | `PadInertBeforeContact: the character was thrown while it` | Gate 1, via the **continuous** off-pad guard. Throws on a timer that never consults the pad, **first firing at t=1.0** — while the character is still walking toward it (x ~ -450) and between cp0 (0.6) and cp1 (2.9), so only a per-frame guard can catch it. **A t=3.0 first firing tested the wrong gate:** cp1 samples at t=2.90, found the character on the pad un-thrown, and `ContactThrowsSubjectUp` fired 0.1 s before the timer misbehaved (measured 2026-08-17, `FAIL(wrong-reason)`). Variant timing has to be checked against the checkpoint schedule, not just the intent. |
| `throws-everything/` | FAIL | `ControlStaysGroundedThroughout: the second character left` | Gate 7. The arrival is thrown *correctly*, so gates 2/3/3b/4/5/6 all pass — this variant exists to prove the in-scene control is load-bearing and not decoration. |

## What each variant deliberately does NOT break

`short-launch` throws on contact, once per contact, and lands in time; only the
height is wrong. `timer-throw` produces a textbook arc; only its cause is wrong.
`throws-everything` is a correct pad that is also indiscriminate. Keeping each
variant wrong in exactly one way is what makes a wrong-reason FAIL diagnostic
instead of ambiguous.

## The empty leg is automatic

`empty` needs no directory: the runner grades an empty submission against the
committed substrate. It is listed here because its expected substring is part of
the oracle.

## Gates with no variant, and why that is honest

Gates **4** (`LandsBackOnTheGround`) and **6** (`SecondContactThrowsAgain`) carry
no hand-authored variant. Per the 2026-08-11 owner decision, variants are written
for a hole the requirements table actually found, not one per gate. Both of these
are covered by the table in `../task.md`, and both are reachable: gate 4 fires on
any throw that never lands inside 4.0 s, and gate 6 on any pad that works once
and then latches. If a future submission is seen passing either of them
vacuously, that is the moment to author the variant — record it here when it
happens.

## Status

Authored and calibrated against real runs on 2026-08-17 (UE 5.8.1, Windows).
Reference PASS and `empty` FAIL are **measured**; the three variant legs are
authored and are graded by `cb discriminate`. Their predicted substrings are taken
verbatim from the fixture's `FinishTest` text, not paraphrased.
