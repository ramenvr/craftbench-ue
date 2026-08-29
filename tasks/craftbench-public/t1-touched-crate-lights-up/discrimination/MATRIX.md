# Discrimination matrix — t1-touched-crate-lights-up

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | Each crate answers for itself: it ticks, measures the flat distance to the player pawn, and compares against **its own** `NoticeRadiusUu`. Nothing in the solution knows there are two crates or where either of them stands, which is exactly why different radii and a swap cost it nothing. Measured: 4 separate spells per crate across the two legs. |
| `empty` | FAIL | `EachCrateLightsForItsOwnReach: crate ` | The unmodified scaffold compiles, so L1 is green. `SetHighlighted` exists and works; nothing calls it after `BeginPlay`, so both crates stay plain and the first crate fails the moment the character stands 200 uu from it. |

## Requirements table

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| lights while within **its own** reach | `EachCrateLightsForItsOwnReach`, every frame, per crate | for half a second after the truth about that crate changes — the settle the prompt states |
| goes out when the character leaves | the same gate, other direction | same |
| settles within **half a second** | the settle window itself | never |
| lights **again** on a later approach | `ACrateLightsUpAgainWhenYouComeBack` — at least two distinct spells per crate | judged at the sentinel; a run that fails the per-frame gate earlier never reaches it, which is the more useful message |
| the two reaches differ | not a gate but a **precondition**: the fixture refuses to start if they are within 100 uu, so the task can never silently lose the thing it measures | never |
| the crates swap places | `TheYardRanBothLegs` fails a run that never got to leg 2 | never |
| where the crates stand is not yours to change | `TheCratesWereNotMoved`, every frame, to 2 uu | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## What carries the discrimination without variants

**Two reaches, not one.** 260 uu and 520 uu, and the route stops at 0.7x and 1.5x
of **each** crate's own radius. A submission with a single hard-coded number is
wrong at two of the six stops on every leg. The failure message names both radii
in the same sentence, so the diagnosis is in the verdict rather than in a
follow-up investigation.

**The route is derived, not written down.** Every stop is a multiple of the
radius of the crate it is about, offset into a lane to one side. That makes it
self-calibrating: after the crates swap, the same schedule produces the right
stops for their new places. It also means the level can be re-authored with
different radii and the fixture follows.

**`PrepareTest` refuses a route it could grade unfairly.** It rejects any stop
within 20% of a crate's radius (where a correct answer could round either way),
any stop closer than 130 uu to a crate's centre, and any leg of the walk that
passes that close — because the crates are solid and a route through one jams the
character, which reads as the submission's fault.

**Both directions and a re-arm.** The per-frame gate covers "lit when it should
be" and "dark when it should not" in one place, and the spell counter covers
"and again". An overlap-begin handler with no end fails the second; a
one-shot flag fails the third.

## Two staging faults that failed a CORRECT implementation first

1. **The route walked through the crates.** The first version put each crate's
   in-reach stop on the line joining them, so the walk from one to the other went
   straight through two solid boxes. The character jammed against the first crate
   at stop 3 of 7 and the run never reached leg 2 — while its highlight logic was
   working perfectly, visible in the trace as two correct spells before it stuck.
   The route now runs in a lane to one side, and `PrepareTest` samples every leg
   of the walk and refuses to start if any of it passes within 130 uu of a crate.
2. **`static_mesh_component` is a `StaticMeshActor` attribute.** The authoring
   script used it on `AHighlightCrateActor`, which raised after the level had
   already been created — leaving a 6 KB EMPTY map on disk that the automation
   run then reported as "No automation tests". The lesson is not the attribute
   name: it is that `new_level()` **saves an empty package immediately**, so an
   authoring script that fails later leaves a plausible-looking map behind. A
   map that exists is not a map that was authored.
