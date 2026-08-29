// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `never-stops/` -- ONE DELTA from ../../reference (this
// file only). AXIS: a permanent regeneration that never expires. Defends
// PIN.md section 3 AG-4.
// EXPECTED: FAIL at HOT-3, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THIS IS THE VARIANT THE OWNER EDIT OF 2026-08-10 EXISTS FOR
// (PIN.md, "OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED":
// StopEpsilon 0.7 -> 0.25). It is tuned so that it FAILS HOT-3 at the pinned
// 0.25 and would have PASSED HOT-3 at the sheet's original 0.7. The arithmetic
// is below and is the whole reason this file carries a header this long.
//
// THE DELTA, in full: DurationPolicy goes HasDuration -> Infinite, the
// DurationMagnitude line is dropped (an Infinite effect has no duration),
// Period goes 1.0 -> 1.65 s and the per-period magnitude goes +5.0 -> +0.6.
// bExecutePeriodicEffectOnApplication stays false. Nothing else in the overlay
// changes.
//
// THREE CONSTANTS MOVE, ONE AXIS BREAKS. The axis is "the restore never stops";
// the period and the magnitude are the TUNING that turns a naive permanent
// regeneration into a GAMING one -- a submission deliberately shaped to hide
// inside the fixture's tolerances. Exactly the same construction, for exactly
// the same reason, as gp-poison-dot-stack-cpp/discrimination/permanent-drain/,
// which is the row that measured a real unsoundness in poison's stop gate.
//
// ---------------------------------------------------------------------------
// THE ARITHMETIC (this is the load-bearing part of the file)
// ---------------------------------------------------------------------------
//
// The fixture's Leg 1 samples, as offsets from the trigger at t = 0.5:
//     A1    +1.1     A2    +2.6     A3    +4.1
//     AStop +7.1     ATail +9.2
// so the three gated windows are
//     rise window 1 = (+1.1, +2.6]   length 1.5 s
//     rise window 2 = (+2.6, +4.1]   length 1.5 s   (CONGRUENT with the first)
//     stop window   = (+7.1, +9.2]   length 2.1 s
//
// With bExecutePeriodicEffectOnApplication = false, a periodic effect of period
// p executes at offsets k*p for k = 1, 2, 3, ... At p = 1.65 s those are
//     1.65, 3.30, 4.95, 6.60, 8.25, 9.90, ...
// which lands EXACTLY ONE execution in each of the three windows:
//     rise window 1: {1.65}                      -> nRise1 = 1
//     rise window 2: {3.30}                      -> nRise2 = 1
//     stop window:   {8.25}                      -> nStop  = 1
//
// TICK-PLACEMENT MARGIN (how much frame jitter this survives). Distance from
// every execution to the nearest window boundary that would change a count:
//     1.65 vs +1.1 -> 0.55      1.65 vs +2.6 -> 0.95
//     3.30 vs +2.6 -> 0.70      3.30 vs +4.1 -> 0.80
//     4.95 vs +4.1 -> 0.85      6.60 vs +7.1 -> 0.50
//     8.25 vs +7.1 -> 1.15      8.25 vs +9.2 -> 0.95
//     9.90 vs +9.2 -> 0.70
// The minimum is 0.50 s = 30 frames at the runner's -FPS=60. The counts above
// are therefore structural, not lucky.
//
// MAGNITUDE. With nRise1 = nRise2 = nStop = 1, the per-period magnitude m is
// the only free number and it is pinned by two inequalities:
//     HOT-2 must PASS       ->  1 * m >  RiseEpsilon = 0.50
//     HOT-3 must have
//     PASSED at the old bar ->  1 * m <= 0.70   (the sheet's original StopEpsilon)
// so m lies in (0.50, 0.70], and m = 0.60 is its exact midpoint: 0.10 of margin
// on each side. That is the same "equal margin each side" form the owner used to
// pin StopEpsilon itself.
//
// PREDICTED LEG 1 TIMELINE (Health starts at the fixture's preset of 40.0):
//     A1    (+1.1) = 40.0    (0 executions yet)
//     A2    (+2.6) = 40.6    (1)
//     A3    (+4.1) = 41.2    (2)
//     AStop (+7.1) = 42.4    (4)
//     ATail (+9.2) = 43.0    (5)
// RiseStep1 = 0.6, RiseStep2 = 0.6, StopRise = ATail - AStop = 0.6.
//
// THE VERDICT, AT BOTH BARS:
//     StopEpsilon = 0.25 (PINNED)   0.6 >  0.25  ->  HOT-3 FAILS   <-- expected
//     StopEpsilon = 0.70 (sheet)    0.6 <= 0.70  ->  HOT-3 PASSES
// which is precisely the claim the owner EDIT rests on: at 0.7, HOT-3 does not
// defend AG-4.
//
// ---------------------------------------------------------------------------
// HONEST LIMIT OF THIS ROW -- READ BEFORE CITING IT
// ---------------------------------------------------------------------------
// At StopEpsilon = 0.7 this submission would NOT have passed the task. It would
// have fallen through HOT-3 into HOT-4: five executions of +0.6 by +9.2 is a
// total of 3.0 Health, far under the disclosed 10-40 band, so HOT-4 fires and
// the run still FAILs -- under the name "the total restored is outside the
// stated 10-40 band", which describes something this submission's author did
// not get wrong. So for the single-effect shape the owner EDIT buys correct
// ATTRIBUTION, not a catch that did not exist before.
//
// THAT IS NOT A DEFECT IN THE EDIT, AND IT IS STRUCTURAL, NOT INCIDENTAL. For a
// single periodic effect the executions are spread uniformly, so the count over
// the whole (0, +9.2] observation is about 9.2/p and the count in the 2.1 s stop
// window is about 2.1/p -- a ratio of about 4.4. Passing HOT-4 needs total >= 10
// while passing HOT-3 at 0.7 needs the stop-window gain <= 0.7, i.e. a ratio of
// at least 14.3. No period achieves that: with one execution in each 1.5 s rise
// window the period is bounded to (1.37, 2.05] s, and over that whole range the
// 2.1 s stop window always contains at least one execution. A single-GE
// permanent regeneration therefore CANNOT clear HOT-3 and HOT-4 together.
//
// THE SHAPE THAT CAN is a conforming duration-limited restore applied ALONGSIDE
// a slow permanent drip, and it is committed as the sibling variant
// `../never-stops-in-band/`. That one passes all nine gates at StopEpsilon =
// 0.7 and dies at HOT-3 at 0.25 -- it is the row that proves the edit was
// load-bearing in the strict sense. The two rows share HOT-3's substring; the
// ISOLATION CAVEAT in ../MATRIX.md declares it rather than pretending
// otherwise.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-3 format string in
// HealOverTimeFunctionalTest.cpp -- the sample values are %.1f and are NOT part
// of the recorded substring):
//     the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=
//
// PREDICTED - NOT YET MEASURED, every number in this header included.

#include "HealOverTimeEffect.h"

#include "CraftBenchAttributeSet.h"

/** Seconds between restorations. Chosen so that exactly one execution lands in
 *  each of the fixture's two congruent 1.5 s rise windows AND exactly one in its
 *  2.1 s stop window, with 0.50 s of clearance to the nearest boundary that
 *  would change any of those counts. See the header derivation.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float NeverStopsPeriodSeconds = 1.65f;

/** Health restored per period. The exact midpoint of the interval (0.50, 0.70]
 *  in which this variant both PASSES HOT-2 at RiseEpsilon = 0.5 and would have
 *  PASSED HOT-3 at the sheet's original StopEpsilon = 0.7 -- 0.10 of margin on
 *  each side. It FAILS HOT-3 at the pinned StopEpsilon = 0.25 by 0.35.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float NeverStopsPerPeriod = 0.6f;

UHealOverTimeEffect::UHealOverTimeEffect()
{
	// THE DELTA. Infinite: the effect is added to the active container and is
	// never removed by anything, so the restore runs for the whole life of the
	// pawn. This is the "restore that never ends" the prompt rules out ("it must
	// not keep restoring forever").
	//
	// No DurationMagnitude is set -- an Infinite effect has no duration to
	// magnitude.
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Period = FScalableFloat(NeverStopsPeriodSeconds);

	// Unchanged from the reference, and load-bearing for the tick arithmetic in
	// the header: with this false, executions land at k*Period for k >= 1. Leaving
	// it at its UE 5.8 default of TRUE would add an execution on the application
	// frame and shift every count in the derivation by one.
	bExecutePeriodicEffectOnApplication = false;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(NeverStopsPerPeriod));
	Modifiers.Add(HealthMod);
}
