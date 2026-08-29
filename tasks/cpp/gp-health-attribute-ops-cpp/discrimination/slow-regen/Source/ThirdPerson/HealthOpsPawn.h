// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `slow-regen/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-6 (PIN.md section 3), THE HALF `regen/` COULD NOT REACH:
// a passive regeneration loop that trips HO-11 -- the idle-window gate -- and
// nothing else.
//
// WHY THIS FILE EXISTS. `regen/` was authored to prove HO-11 and lands on HO-10
// instead: its drift contaminates the heal window as hard as the idle window, so
// the measured leg reads symRatio 1.33 and HO-10, which is evaluated first, is
// what reports. That left HO-11 as the only gate in this task with NO committed
// variant failing at it -- the exact shape that hid the poison stop-gate defect
// for six weeks (../MATRIX.md, "HO-11 IS NOT REACHABLE"; the follow-up recorded
// there is this variant).
//
// THE ONE DELTA, same axis as `regen/`: the reference PLUS a passive Health
// regeneration loop in Tick. Stage 1, both abilities, both instant effects and
// the mesh are the reference verbatim. What differs from `regen/` is WHEN the
// drift is allowed to run: this is out-of-combat regeneration -- Health creeps
// back only once nothing has damaged the character for a while -- which is the
// canonical shape of the mechanic in shipped games, not a schedule hack.
//
// EXPECTED: FAIL at the final checkpoint, at **HO-11**, on the named substring
//   "Health kept moving with no operation active:"
// PREDICTED -- NOT YET RUN. No build, no PIE, no run_task.py was executed for
// this package.
//
// =========================================================================
// THE ARITHMETIC. Read this before changing either constant.
// =========================================================================
//
// MEASURED reference population (../MATRIX.md, 2026-08-10, the only measured
// numbers this file leans on):
//
//     drop1 = 10.00   drop2 = 10.00   heal = 10.00   idleDelta = 0.00
//     w1 = w2 = w3 = w4 = 0.700 s     (the four windows are congruent, MEASURED)
//
// Bars from the fixture (HealthAttributeOpsFunctionalTest.h:155-177):
//     DirectionEpsilon 0.5   band [5, 25]   RepeatTol 0.10
//     SymTol 0.10            IdleEpsilon 0.5
//
// Schedule (HealthAttributeOpsFunctionalTest.cpp:56): {0.5, 1.2, 1.9, 2.6, 3.3}.
// Damage is triggered at cp0 (t=0.5) and cp1 (t=1.2); the heal at cp2 (t=1.9);
// NOTHING is triggered in the idle window (cp3, cp4] = (2.6, 3.3].
//
// -- STEP 1: a UNIFORM drift cannot do this, and that is not an opinion. ------
//
// Let R be a constant drift rate and x = R * 0.7 the Health it moves in one
// window. A uniform drift contributes x to EVERY window, so with M = 10:
//
//     drop1 = M - x        drop2 = M - x        healDelta = M + x
//     HO-9  repeatRatio = (M-x)/(M-x) = 1.00 exactly -- a uniform drift cancels
//     HO-10 symRatio    = (M+x)/(M-x)  must be <= 1 + SymTol = 1.10
//                       ->  10 + x <= 11 - 1.1x  ->  x <= 1/2.1 = 0.4762
//     HO-11 fires only when idleDelta = x > IdleEpsilon = 0.5
//
// 0.4762 < 0.5, so the two conditions do not overlap: THERE IS NO UPWARD
// UNIFORM RATE. (Nor a downward one worth shipping: flipping the sign gives
// symRatio = (M-x)/(M+x) >= 0.90 -> x <= 0.5263, a live band of
// 0.5 < x <= 0.5263 whose margin on each bar is under 0.03 Health -- 3% of one
// application. That is not a bar anyone can pin a variant on, and a downward
// drift would also move Health off 100 before cp0 and die at HO-3 instead.)
//
// The magnitude of the drift is therefore NOT the free axis. Its TIMING is.
//
// -- STEP 2: suppress the drift until after the heal window closes. ----------
//
// Out-of-combat regeneration keys off the last DAMAGE, so with a delay D the
// drift resumes at
//
//     resume = t(last damage) + D = 1.2 + D
//
// and contributes to a window only for the part of the window after `resume`.
// Choose D so that `resume` falls strictly inside the idle window (2.6, 3.3]:
//
//     windows 1 and 2 -> zero drift -> drop1 = drop2 = 10.00, repeatRatio 1.00
//                        (HO-7, HO-8, HO-9 read EXACTLY the reference values)
//     window 3        -> zero drift -> healDelta = 10.00, symRatio 1.00
//                        (HO-10 reads EXACTLY the reference value -- maximum margin)
//     window 4        -> drift for (3.3 - resume) seconds
//                        idleDelta = R * (3.3 - resume)    <- the only gate moved
//
// -- STEP 3: pin R and D by equalising the margin on each side. --------------
//
// Two failure modes bound `resume`, and both are stated as a TIME because time
// is what the schedule can jitter:
//
//   (a) resume too EARLY -> drift leaks into window 3 -> HO-10 breaks when the
//       leak reaches SymTol * drop1 = 1.0 Health, i.e. 1.0/R seconds of leak:
//           resume > 2.6 - 1.0/R
//   (b) resume too LATE  -> too little drift in window 4 -> HO-11 stops firing
//       when idleDelta falls to IdleEpsilon = 0.5, i.e. 0.5/R seconds of drift:
//           resume < 3.3 - 0.5/R
//
// At R = 3.0 Health/s that safe band is (2.267, 3.133) and its MIDPOINT is
// exactly 2.700 -- equal margin of 0.433 s on each side, the same "equal margin
// each side" form the owner used to pin StopEpsilon on gp-heal-over-time.
// resume = 2.700 gives D = 2.700 - 1.2 = 1.5 s.
//
// PREDICTED LEG (arithmetic, not a reading):
//     H0 60.0 -> H1 50.0 -> H2 40.0 -> H3 50.0 -> H4 51.8
//     drop1     10.00  -> HO-7  10.00 > 0.5              (passes, reference value)
//     drop1     10.00  -> HO-8  inside [5, 25]           (passes, dead centre)
//     repeatRatio 1.00 -> HO-9  inside 0.90-1.10         (passes, dead centre)
//     symRatio    1.00 -> HO-10 inside 0.90-1.10         (passes, dead centre)
//     idleDelta   1.80 -> HO-11 |1.80| > 0.50            (FAILS -- 3.6x the bar)
//
// Every gate except HO-11 reads the reference's own measured value, which is
// what makes the verdict attributable: this variant does not merely fail at
// HO-11, it fails ONLY at HO-11 with no bar even approached on the way.
//
// -- STEP 4: what would invalidate this. --------------------------------------
//
// The schedule is normative (PIN.md section 2) and is what STEP 3 is solved
// against. If cp3/cp4 move, if IdleEpsilon or SymTol is re-pinned, or if the
// reference magnitude leaves 10, re-solve STEP 3 -- do not nudge R. Note that
// R and D are coupled: the safe band's width is 0.7 + 0.5/R, so raising R
// narrows the band on both sides at once.
//
// Both constants below are `PROPOSED - NOT YET MEASURED`. They are derived from
// the reference's MEASURED population, but the leg they predict has not been run.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "HealthOpsPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class AHealthOpsPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

	/** THE DELTA. The reference does not override Tick at all. */
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;

	/** Out-of-combat regeneration rate, Health per second, while regenerating.
	 *  PROPOSED - NOT YET MEASURED. See STEP 3 in the file header. */
	static constexpr float HealthOpsRegenRate = 3.0f;

	/** How long the character must go without taking damage before regeneration
	 *  resumes. PROPOSED - NOT YET MEASURED. Solved in STEP 3 so that the resume
	 *  instant lands at the midpoint of the band that keeps HO-10 passing and
	 *  HO-11 firing. */
	static constexpr float HealthOpsRegenDelay = 1.5f;

	/** A Health decrease larger than this counts as "took damage" and restarts
	 *  the out-of-combat timer. Any value well below one application magnitude
	 *  (10) works; it exists only so float noise cannot masquerade as a hit.
	 *  Regeneration only ever RAISES Health, so it can never re-trigger this. */
	static constexpr float HealthOpsDamageDetectEpsilon = 0.01f;

	/** Health as of the previous tick, used to spot a decrease. Sentinel < 0
	 *  means "no previous tick yet" -- the first tick only seeds it. */
	float PreviousHealth = -1.0f;

	/** World game-time of the last detected damage; large negative so the
	 *  character counts as out of combat from spawn. */
	double LastDamageTime = -1000.0;
};
