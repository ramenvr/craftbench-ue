// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `instant/` -- ONE DELTA from ../../reference (this file
// only). AXIS: one instant restore of the whole amount, dressed as an ability.
// Defends PIN.md section 3 AG-3.
// EXPECTED: FAIL at HOT-2, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: DurationPolicy goes HasDuration -> Instant, Period and
// bExecutePeriodicEffectOnApplication are dropped (both are meaningless on an
// Instant effect), and the modifier magnitude goes +5.0 per period -> +25.0
// once. The header, the ability, the attribute set and the pawn are all
// byte-identical to the reference.
//
// THE MAGNITUDE IS 25.0 ON PURPOSE. That is the reference's TOTAL for one
// application (5 periods x 5.0), so this variant restores exactly as much
// Health as a conforming solve and lands inside the disclosed 10-40 band. It
// therefore CANNOT be caught by HOT-4, and it is the periodicity gate alone
// that has to do the work. A variant that also broke the magnitude would prove
// nothing about HOT-2.
//
// PREDICTED LEG 1 TIMELINE (trigger at t=0.5; offsets below are from the
// trigger). An Instant effect executes once, on application, so the whole +25
// has landed before the first sample:
//     A1    (+1.1) = 65.0
//     A2    (+2.6) = 65.0
//     A3    (+4.1) = 65.0
//     AStop (+7.1) = 65.0
//     ATail (+9.2) = 65.0
// RiseStep1 = A2 - A1 = 0.0 and RiseStep2 = A3 - A2 = 0.0, both against
// RiseEpsilon = 0.5. HOT-2 requires BOTH steps to exceed the floor, so it fires
// with a margin of the full epsilon on each step -- there is no jitter story
// here at all, because a finished Instant effect cannot move Health again.
//
// GATE-ORDER CHECK (why the row isolates): HOT-1 passes (the ability is granted
// and activates three times), HOT-1c passes (the ability ends immediately, so no
// activation is refused), and HOT-2 is the very next assertion. HOT-3 would also
// have passed (StopRise = 0.0) and HOT-4 would also have passed (total 25.0), so
// HOT-2 is not merely the first gate to fire -- it is the ONLY one this
// submission fails.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-2 format string in
// HealOverTimeFunctionalTest.cpp -- the three sample values are %.1f and are NOT
// part of the recorded substring):
//     the restore was not periodic: Health did not keep rising in steps (A1=
//
// PREDICTED - NOT YET MEASURED, every number above included.

#include "HealOverTimeEffect.h"

#include "CraftBenchAttributeSet.h"

/** Health restored by the single instant execution. Equal to the reference's
 *  per-application TOTAL (5 periods x 5.0), so this variant stays inside the
 *  disclosed 10-40 band and cannot be caught by HOT-4.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float InstantRestoreTotal = 25.0f;

UHealOverTimeEffect::UHealOverTimeEffect()
{
	// THE DELTA. An Instant effect: it executes once, on application, straight
	// into the BASE value, and is never added to the active-effect container. This
	// is the "single instant restore" the prompt rules out in so many words ("It
	// must not be a single instant restore").
	DurationPolicy = EGameplayEffectDurationType::Instant;

	// No DurationMagnitude, no Period, no bExecutePeriodicEffectOnApplication --
	// all three are duration-policy machinery an Instant effect does not carry.

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(InstantRestoreTotal));
	Modifiers.Add(HealthMod);
}
