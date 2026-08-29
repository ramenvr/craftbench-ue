// Copyright CraftBench. All Rights Reserved.

#include "HealOverTimeEffect.h"

#include "CraftBenchAttributeSet.h"

// ---------------------------------------------------------------------------
// EVERY CONSTANT IN THIS FILE IS `PROPOSED - NOT YET MEASURED`.
//
// Bars in this repo are pinned by MEASURING (PIN.md section 2: "All bars:
// PROPOSED - NOT YET MEASURED"; section 6 requires both populations in
// notes.md). Nothing below has been compiled, run in PIE, or graded. These are
// mid-band REFERENCE CHOICES, chosen to sit far from the edges of what the
// prompt discloses, not calibrated readings.
// ---------------------------------------------------------------------------

/** Total effect lifetime. The prompt discloses "roughly five seconds" and a
 *  four-to-seven-second acceptance band; 5.0 sits mid-band with 1.0s of margin
 *  below and 2.0s above. PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimeDurationSeconds = 5.0f;

/** Seconds between restorations. The prompt discloses "about once per second".
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimePeriodSeconds = 1.0f;

/** Health restored per period, POSITIVE (this is the sign flip against poison).
 *
 *  With bExecutePeriodicEffectOnApplication = false, a 5.0s duration on a 1.0s
 *  period executes 5 times, so one application restores 5 * 5 = 25 Health in
 *  total. The prompt discloses a 10-40 per-application band; 25 is its exact
 *  midpoint, i.e. 15 of margin on BOTH sides -- which matters because the band
 *  is two-sided and a reference parked near either edge would leave the family
 *  unable to tell a conforming solve from a marginal one.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float HealOverTimePerPeriod = 5.0f;

UHealOverTimeEffect::UHealOverTimeEffect()
{
	// A HasDuration effect: it ends on its own. An Infinite effect would be the
	// permanent regeneration the prompt rules out ("it must not keep restoring
	// forever"), and an Instant one would be the single restore it also rules out.
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(HealOverTimeDurationSeconds));
	Period = FScalableFloat(HealOverTimePeriodSeconds);

	// Do NOT restore on the application frame. bExecutePeriodicEffectOnApplication
	// defaults to TRUE in UE 5.8 (GameplayEffect.cpp:187), which would make a 5s
	// duration on a 1s period execute SIX times, not five -- so the per-application
	// total would be 30 rather than 25 and the first restore would be blurred into
	// the same frame as the activation. Same choice, and the same reason, as
	// gp-poison-dot-stack-cpp's UPoisonEffect.
	bExecutePeriodicEffectOnApplication = false;

	// Health += 5 per period. A plain additive modifier: a periodic execution
	// writes into the BASE value, which is exactly why the clamp cannot live in
	// PreAttributeChange alone (see UHealOverTimeAttributeSet).
	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(HealOverTimePerPeriod));
	Modifiers.Add(HealthMod);

	// No stacking policy is set. The prompt says nothing about stacking, so the
	// engine default (EGameplayEffectStackingType::None -- each application is its
	// own effect instance) is the right shape. gp-poison-dot-stack-cpp is the
	// family where stacking IS the graded axis; borrowing its stacking block here
	// would be answering a question this prompt does not ask.
}
