// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (permanent-drain) for task gp-poison-dot-stack-cpp.
//
// THE ONE AXIS: the poison NEVER ENDS. DurationPolicy is Infinite instead of
// HasDuration, so Health falls forever after a single application. That is
// anti-gaming note 4's "permanent drain" failure mode, and the prompt forbids
// it in as many words: "for roughly five seconds, then stops (not a single
// hit, and not a drain that never ends)".
//
// This is deliberately a GAMING variant, not a naive one. A naive infinite
// drain at the reference's own -5.0/1.0s is caught immediately: the 2.1s Leg A
// stop window (7.6, 9.7] holds two ticks, so it leaves 10.0 against
// StopEpsilon=2.5 and FAILs. To model an agent that games the gate rather than
// one that misreads the prompt, the period and magnitude are retuned to hide
// inside the tolerances:
//
//     Period    = 1.164 s
//     Magnitude = -2.25 Health per tick (x stack count, as the reference)
//
// Derived by exhaustive rational enumeration over every admissible period on a
// 1 ms grid (see discrimination/MATRIX.md and the g2 Q5 gate-change note).
// Against the shipped 16-checkpoint schedule this configuration reads:
//
//     Leg A periodic w1 (1.6, 3.1]   2 ticks -> 4.500  need >= 2.0   PASS
//     Leg A periodic w2 (3.1, 4.6]   1 tick  -> 2.250  need >= 2.0   PASS
//     Leg A stop        (7.6, 9.7]   1 tick  -> 2.250  need <= 2.5   PASS  <-- never ends
//     Leg C refresh   (17.9, 19.4]   1 tick  -> 2.250  need >= 2.0   PASS
//     Leg C stop      (21.4, 23.5]   1 tick  -> 2.250  need <= 2.5   PASS  <-- never ends
//
// Stacking is left exactly as the reference (AggregateByTarget, cap 3,
// bFactorInStackCount), so Leg B/D still reads ~3.00x and passes.
//
// EXPECTED VERDICT AS OF THIS COMMIT: **PASS** — which is the point. This
// variant exists to MEASURE a hole, not to be caught by the gate it targets.
// The shipped StopEpsilon justification (PoisonStackFunctionalTest.h:100,
// "2.5 < 4.0 == 2 x PeriodicMinStep") silently presumes at least two ticks land
// in the 2.1s stop window, i.e. a period <= 1.05s — and NO period bound is
// enforced anywhere. 410 admissible periods in (0.388s, 2.050s] admit a
// never-ending drain that clears all four duration gates.
//
// Once the Q5 gate change lands, this variant must FLIP to FAIL by name at the
// Leg A stop gate. It is the stop gate's first committed failing variant: until
// now anti-gaming note 4 was defended by argument alone.

#include "PoisonEffect.h"

#include "CraftBenchAttributeSet.h"

UPoisonEffect::UPoisonEffect()
{
	// THE DELTA: never expires. Everything else below mirrors the reference.
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Period = FScalableFloat(1.164f);
	bExecutePeriodicEffectOnApplication = false;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(-2.25f));
	Modifiers.Add(HealthMod);
	bFactorInStackCount = true;

	// Unchanged from the reference so Leg B/D still reads ~3.00x.
	StackingType = EGameplayEffectStackingType::AggregateByTarget;
	StackLimitCount = 3;
	StackDurationRefreshPolicy = EGameplayEffectStackingDurationPolicy::RefreshOnSuccessfulApplication;
	StackPeriodResetPolicy = EGameplayEffectStackingPeriodPolicy::ResetOnSuccessfulApplication;
}
