// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `set-to-constant/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-4 (PIN.md section 3): "'damage' implemented as *set Health
// to a constant*."
//
// THE ONE DELTA, confined to this file: the damage effect's modifier is an
// OVERRIDE to a constant instead of an ADDITIVE subtraction of a fixed amount.
// UHealEffect, both abilities and the pawn are the reference verbatim.
//
// EXPECTED: FAIL at the final checkpoint, HO-9, on the named substring
//   "the damage operation is not a fixed amount: the first application removed"
// UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.

#include "DamageEffect.h"

#include "CraftBenchAttributeSet.h"

// The constant this "damage" sets Health to. PROPOSED - NOT YET MEASURED.
//
// 50 is CHOSEN, and the choice is the whole design of this variant. The fixture
// presets Health to 60 (PIN.md D4), so the FIRST application removes 60-50 = 10
// -- identical to the reference's per-application magnitude, which puts drop1
// squarely inside HO-8's disclosed 5-25 band and clears HO-7's noise floor. The
// SECOND application then finds Health already at 50 and removes 0, so
// drop2/drop1 = 0.00 against HO-9's 0.90-1.10 window.
//
// That sequencing is deliberate: a naive "damage = Health = 0" variant (the
// shape PIN.md section 4's secondary table sketches) would remove 60 on the
// first application and die at HO-8 -- "outside the stated 5-25 band" -- which
// is a real FAIL at the WRONG gate and would prove nothing about HO-9. Picking
// a constant that makes the first application look perfectly conforming is what
// forces the verdict onto the repeatability axis HO-9 exists to defend, and it
// is also the harder, more realistic gaming shape.
static constexpr float HealthOpsDamageSetTo = 50.0f;

UDamageEffect::UDamageEffect()
{
	// Unchanged from the reference: still instant, still one application per
	// activation, still nothing left active afterwards (so HO-11's idle window
	// stays clean and cannot claim this verdict).
	DurationPolicy = EGameplayEffectDurationType::Instant;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	// THE DELTA. Reference: EGameplayModOp::Additive with magnitude -10.0f.
	// EGameplayModOp::Override = 3 in UE 5.8 (GameplayEffectTypes.h:148); on an
	// instant effect it executes against the BASE value, so Health lands on the
	// constant regardless of what it was.
	HealthMod.ModifierOp = EGameplayModOp::Override;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(HealthOpsDamageSetTo));
	Modifiers.Add(HealthMod);
}
