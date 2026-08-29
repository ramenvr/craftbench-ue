// Copyright CraftBench. All Rights Reserved.

#include "HealEffect.h"

#include "CraftBenchAttributeSet.h"

// The per-application magnitude. PROPOSED - NOT YET MEASURED.
//
// Equal in size to UDamageEffect's, and opposite in sign: the prompt says "one
// heal restores exactly as much Health as one damage removes", so HO-10's
// healDelta/drop1 ratio reads exactly 1.00 for this reference.
static constexpr float HealthOpsHealAmount = 10.0f;

UHealEffect::UHealEffect()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(HealthOpsHealAmount));
	Modifiers.Add(HealthMod);
}
