// Copyright CraftBench. All Rights Reserved.

#include "PoisonEffect.h"

#include "CraftBenchAttributeSet.h"

UPoisonEffect::UPoisonEffect()
{
	// ~5s duration, ticking every ~1s.
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(5.0f));
	Period = FScalableFloat(1.0f);
	// Don't apply a tick on the application frame — first damage lands one period
	// later, so the per-second cadence is clean to sample.
	bExecutePeriodicEffectOnApplication = false;

	// Health -= 5 per stack, per period: a plain additive -5.0 modifier. UE
	// 5.8's UGameplayEffect::bFactorInStackCount (default true) multiplies
	// periodic executions by the CURRENT stack count, so 3 stacks => -15/tick
	// (~3x of 1 stack) with no MMC. (Until 2026-08-06 this file fed a
	// "-5 x stackCount" MMC through that same engine factor and
	// DOUBLE-scaled: 4 applications measured 9.00x the single-stack rate --
	// superlinear, violating the prompt's "three stacks ~= three times" and
	// failing the Leg D cap gate by design. Same recipe as the BP reference.)
	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(-5.0f));
	Modifiers.Add(HealthMod);
	bFactorInStackCount = true; // 5.8 default, stated because the math above depends on it

	// DISCRIMINATION VARIANT (no-refresh): identical to the reference EXCEPT
	// the duration-refresh policy — a re-application adds a stack but NEVER
	// extends the duration, so the whole poison still expires ~5s after the
	// FIRST application. Leg C must FAIL this by name ("re-application did not
	// refresh the duration"); every other leg (A periodic/stop, B/D ratio+cap)
	// passes, isolating the refresh axis. The period reset is kept so ONLY the
	// refresh policy differs from the reference.
	StackingType = EGameplayEffectStackingType::AggregateByTarget;
	StackLimitCount = 3;
	StackDurationRefreshPolicy = EGameplayEffectStackingDurationPolicy::NeverRefresh;
	StackPeriodResetPolicy = EGameplayEffectStackingPeriodPolicy::ResetOnSuccessfulApplication;
}
