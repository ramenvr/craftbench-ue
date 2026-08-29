// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `out-of-band/` -- ONE DELTA from ../../reference (this
// file only). AXIS: a token restore, so every window technically rises while
// the effect does essentially nothing. Defends PIN.md section 3 AG-6.
// EXPECTED: FAIL at HOT-4, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the per-period magnitude goes +5.0 -> +1.0. The duration
// (5.0 s), the period (1.0 s) and bExecutePeriodicEffectOnApplication (false)
// are all the reference's, so the effect is still genuinely periodic and still
// genuinely stops. One application now restores 5 x 1.0 = 5.0 Health, which is
// BELOW the disclosed 10-40 band.
//
// WHY THE UNDER-BAND DIRECTION. AG-6 is stated as "restore a token 1 HP so
// every window technically rises", i.e. the gaming move is to satisfy HOT-2's
// direction predicate with a magnitude that means nothing. An over-band variant
// (e.g. +10 per period, total 50) would fail the same gate but would not be the
// shape the note describes.
//
// PREDICTED LEG 1 TIMELINE (Health starts at the fixture's preset of 40.0;
// executions at trigger+1, +2, +3, +4, +5):
//     A1    (+1.1) = 41.0    (1 execution)
//     A2    (+2.6) = 42.0    (2)
//     A3    (+4.1) = 44.0    (4)
//     AStop (+7.1) = 45.0    (5, the effect has ended)
//     ATail (+9.2) = 45.0
// RiseStep1 = 1.0 and RiseStep2 = 2.0 against RiseEpsilon = 0.5, so HOT-2
// PASSES -- which is the whole point of the row. StopRise = 0.0 against
// StopEpsilon = 0.25, so HOT-3 PASSES too. TotalRestored = 45.0 - 40.0 = 5.0
// against a band of [10, 40], so HOT-4 FAILS by 5.0.
//
// JITTER NOTE. The first execution at trigger+1.0 sits only 0.1 s before the A1
// sample at trigger+1.1, so a frame of drift could move it after the sample.
// That does NOT change the verdict: if A1 reads 40.0 instead of 41.0, then
// RiseStep1 becomes 2.0 (still far above 0.5) and RiseStep2 is unchanged at
// 2.0, while ATail and therefore TotalRestored are untouched. HOT-2 passes and
// HOT-4 fires either way.
//
// GATE-ORDER CHECK (why the row isolates): HOT-1, HOT-1c, HOT-2 and HOT-3 all
// pass, HOT-4 is the next assertion, and HOT-5/HOT-6 would also have passed --
// Leg 2 presets 95 and adds at most 5.0, so nothing reaches the cap and the
// reference's clamp is never even exercised. HOT-4 is the only gate this
// submission fails.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-4 format string in
// HealOverTimeFunctionalTest.cpp -- the "40.0" in it is a LITERAL in the format
// string, not a placeholder, so the substring below is safe; the two values
// after it are %.1f and are excluded):
//     the total restored is outside the stated 10-40 band: Health went 40.0 ->
//
// PREDICTED - NOT YET MEASURED, every number above included.

#include "HealOverTimeEffect.h"

#include "CraftBenchAttributeSet.h"

/** Total effect lifetime. UNCHANGED from the reference -- this variant's axis is
 *  magnitude, not duration. PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimeDurationSeconds = 5.0f;

/** Seconds between restorations. UNCHANGED from the reference.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimePeriodSeconds = 1.0f;

/** THE DELTA: a token restore. 5 executions x 1.0 = 5.0 per application, which
 *  is 5.0 below the disclosed band floor of 10 -- enough margin that HOT-4
 *  cannot be reached by rounding, and small enough that the row is unambiguously
 *  the AG-6 shape. PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimePerPeriod = 1.0f;

UHealOverTimeEffect::UHealOverTimeEffect()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(HealOverTimeDurationSeconds));
	Period = FScalableFloat(HealOverTimePeriodSeconds);
	bExecutePeriodicEffectOnApplication = false;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(HealOverTimePerPeriod));
	Modifiers.Add(HealthMod);
}
