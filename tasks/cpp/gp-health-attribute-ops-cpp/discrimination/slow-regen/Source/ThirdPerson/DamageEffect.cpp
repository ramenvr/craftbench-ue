// Copyright CraftBench. All Rights Reserved.

#include "DamageEffect.h"

#include "CraftBenchAttributeSet.h"

// The per-application magnitude. PROPOSED - NOT YET MEASURED.
//
// 10 is a REFERENCE CHOICE inside the band the prompt discloses ("a fixed
// amount between 5 and 25"), not a calibrated bar: it sits mid-band, it is far
// from both edges of HO-8, and pairing it with the heal's +10 makes HO-9
// (drop2/drop1) and HO-10 (healDelta/drop1) read exactly 1.00, so the reference
// carries the maximum margin on both ratio gates. The fixture presets Health to
// 60 (PIN.md D4), so two damages plus one heal stay strictly inside (0, 100)
// and no clamp can bite.
static constexpr float HealthOpsDamageAmount = 10.0f;

UDamageEffect::UDamageEffect()
{
	// One application = one immediate change to the BASE value, then the effect
	// is gone. No duration, no period, no stacking: the operation is fully
	// event-driven, which is what HO-11's idle window asserts.
	DurationPolicy = EGameplayEffectDurationType::Instant;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(-HealthOpsDamageAmount));
	Modifiers.Add(HealthMod);
}
