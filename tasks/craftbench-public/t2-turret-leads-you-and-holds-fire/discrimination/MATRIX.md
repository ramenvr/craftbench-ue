# Discrimination matrix — t2-turret-leads-you-and-holds-fire

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | Each turret answers for itself: every frame it reads its own `ShotSpeedUu` and `EngageRangeUu`, solves `(\|V\|²-s²)t² + 2(D·V)t + \|D\|² = 0` from its muzzle to the character, takes the smallest positive root, holds fire when there is none, commands the barrel at the meeting point, and pulls the trigger only when the character is inside its own reach, the trigger is free, and the barrel's forward vector is inside a cone derived from the disclosed 120 cm and the current range. Nothing in the solution knows there are two turrets, where either of them stands, or that the numbers ever change — which is exactly why the swap and the re-tunes cost it nothing. |
| `empty` | FAIL | `TheTurretsActuallyEngage: a turret sat silent through a stretch` | The unmodified scaffold compiles, so L1 is green. `AimBarrel` and `FireNow` exist and work; nothing calls either. Turret 1 (SET-L, 4200 uu reach) has the character moving steadily inside its reach with a plain interception available for 13.4 s on leg A, which demands three shots at its 1.5 s reload, and it fires none. The FAIL lands ~19 s into the run, at the first window close. |

Both substrings are contiguous spans of one source literal in
`Source/CraftBenchTests/Tasks/t2-turret-leads-you-and-holds-fire/TurretLeadFunctionalTest.cpp`
(`CloseWindow`), crossing no `printf` placeholder, and appear verbatim in the log.

## Requirements table

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| a shot connects within **120 cm** of the middle of the character | `ShotsFromTheOpenConnect`, per shot | for shots fired while the character was accelerating, turning, standing, out of that turret's reach, within 0.5 s of a re-tune, or with a flight longer than the current leg has left |
| **every** such shot has to connect, not most of them | the same gate — per shot, no averaging, first miss ends the run | same |
| a turret has to have taken shots that can be judged at all | `EveryTurretTookAShotYouCanJudge` (>= 1 per turret, >= 4 in total) | never |
| fire only inside **that turret's own** reach | `NothingIsFiredBeyondItsOwnReach` | in the 1.0x–1.25x band, which forgives measuring range from the muzzle rather than from the turret |
| fire only when a straight shot at **that turret's own** speed would genuinely meet them | `NothingIsFiredWithNowhereToAim` | inside the 1.25x / 0.25x margins, which are a strict subset of the true no-root region |
| outrunning a shot is not on its own a reason to hold | `TheTurretsActuallyEngage` on leg D (520 uu/s charging a 460 uu/s gun) | for windows too short to demand a shot |
| whenever both hold, take the shot and keep taking it | `TheTurretsActuallyEngage`, per window on close | for windows shorter than a quarter-turn plus max(2.5 s, 1.6 reloads) |
| as often as **that turret's own** reload allows | `NoTurretFiresFasterThanItsOwnReload` (0.85 x the smallest reload advertised between two shots) | never |
| a shot leaves along wherever the barrel is actually pointing | `TheBaseIsBoltedDownAndTheBarrelDoesTheAiming`, 6 deg, plus the 150 uu muzzle window | never |
| the barrel swings at that turret's own rate; it does not snap | `TheBarrelSwingsAtItsOwnRate` | for the first two graded frames |
| the base is bolted; only the barrel moves, and it turns on the spot | `TheBaseIsBoltedDownAndTheBarrelDoesTheAiming` (actor quat, base quat, barrel-pivot location) | never |
| dead straight, at that turret's own speed, never pulled down | `ShotsFlyStraightAtTheirOwnSpeed` | for shots fired within 0.5 s of a re-tune |
| the four numbers are readable and change under you | `TheTurretsKeptTheirFourNumbers`, plus every gate above reading them live each frame | never |
| how fast the character can move is not yours to change | `TheCharacterKeptTheSpeedTheYardSet` | never |
| where the turrets stand is not yours to change | the bolted gate, every frame, to 2 uu | never |
| the whole run happened | `TheYardWalkedTheWholeRoute` at the sentinel | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## What carries the discrimination without variants

**Two turrets, never one constant.** The two shot speeds are at least 500 uu/s apart
and the two reaches at least 1000 uu apart in every phase, and `PrepareTest` refuses
to start otherwise. Whichever number a submission hard-codes is wrong about one gun
at every instant.

**The numbers move twice.** The map is authored with the phase-1 set on purpose, so
reading them once in `BeginPlay` is *correct* for the first 66 s and wrong about all
eight numbers thereafter. That is the failure that looks like a working solution
right up until it does not.

**Two gates that only exist because the agent owns the supplied files.**
`Source/ThirdPerson/` is writable, so `AimBarrel` and `FireNow` enforce nothing —
they are a convention. `TheBarrelSwingsAtItsOwnRate` and
`NoTurretFiresFasterThanItsOwnReload` re-derive both from the fixture's own samples,
which is what keeps the trigger-against-servo interaction alive. Without them
`Barrel->SetWorldRotation(Solution)` is one legal line that deletes the hardest half
of the task.

**The route is derived and dry-run.** Every stop is a multiple of the reach of the
set that owns its leg, so it re-shapes itself around each re-tune; and `PrepareTest`
walks the whole thing at 240 samples per leg before grading a single frame, refusing
to start if any demanded window is shorter than 3.3 reloads, if the intercept point
would out-swing the barrel, if a stop sits within 8% of a reach boundary or 400 uu of
a solid base, or if either hold-fire gate would be vacuous.

**Both directions, at three shot speeds.** The engage duty and the two hold-fire
gates cover the same instants from opposite sides, and the lead is measured at
460, 1350 and 750 uu/s, so no single lead angle is ever right twice.

## Two things that would have failed a CORRECT implementation, and how they were headed off

1. **A charging sprinter out-swings a slow barrel.** Leg D is the leg built to kill
   "if the target is faster than my shot, hold". The first geometry ran the charge to
   700 uu from the turret, where the intercept point's bearing rate reaches 36 deg/s
   against a 40 deg/s barrel — the demanded shot was one the gun physically could not
   take, and a correct submission would have been failed for silence. The charge now
   stops at 840 uu (bearing rate 14.5 deg/s) and `PrepareTest` refuses to start any
   route whose demanded windows exceed 0.6x the owning turret's traverse.
2. **A once-per-frame fixture cannot see intra-frame tick order.** The first cut
   compared a shot's launch direction against the barrel to a quarter of a degree.
   At 130 deg/s and 60 FPS a barrel legally swings 2.2 deg between two fixture
   samples, so a correct submission that happened to call `FireNow` before
   `AimBarrel` within a tick would have false-FAILed on ordering alone. The bar is
   6 deg, which still catches a shot spawned along a computed vector while the gun
   points elsewhere by a factor of fifteen. The same reasoning sets
   `TheBarrelSwingsAtItsOwnRate`'s allowance at three frames of legal slew plus
   1.5 deg.
