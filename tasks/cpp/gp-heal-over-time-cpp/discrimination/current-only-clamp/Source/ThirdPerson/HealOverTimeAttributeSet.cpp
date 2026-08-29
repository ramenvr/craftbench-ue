// Copyright CraftBench. All Rights Reserved.
//
// See HealOverTimeAttributeSet.h in this directory for the full delta
// description, the engine-source mechanism and the declared substring collision
// with ../no-clamp/.

#include "HealOverTimeAttributeSet.h"

float UHealOverTimeAttributeSet::ClampHealth(float Value) const
{
	// Kept verbatim from the reference: the cap is read from the pawn's OWN
	// MaxHealth attribute, not from a constant.
	return FMath::Clamp(Value, 0.0f, GetMaxHealth());
}

void UHealOverTimeAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);

	// Kept verbatim from the reference. This guards the CURRENT value only -- it
	// is called by reference from FGameplayAttribute::SetNumericValueChecked just
	// before the current value is written, and it never sees the base write a
	// periodic execution performs.
	if (Attribute == GetHealthAttribute())
	{
		NewValue = ClampHealth(NewValue);
	}
}

// THE DELTA: PostGameplayEffectExecute is NOT overridden. The reference's
// implementation --
//
//     if (Data.EvaluatedData.Attribute == GetHealthAttribute())
//         SetHealth(ClampHealth(GetHealth()));
//
// -- is the half that copies the already-clamped current value back down onto
// the stored base after an instant or periodic execution. Without it the base
// accumulates without bound while every read-back stays at exactly MaxHealth.
