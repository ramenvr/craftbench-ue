// Copyright CraftBench. All Rights Reserved.
//
// See HealOverTimeAttributeSet.h in this directory for the full delta
// description, the predicted three-leg timeline and how the reserve is pinned.

#include "HealOverTimeAttributeSet.h"

#include "GameplayEffectExtension.h"
#include "GameplayEffectTypes.h"

/** THE DELTA. Health is held this far BELOW MaxHealth instead of at it -- the
 *  "leave a little headroom" idiom. Pinned above AtMaxEpsilon (0.5) so HOT-6
 *  fires, and far below Leg 1's peak of 65.0 so the effective cap of 98.0 is
 *  never met inside the HOT-2 rise windows.
 *  PROPOSED - NOT YET MEASURED. */
static constexpr float AtMaxHeadroomReserve = 2.0f;

float UHealOverTimeAttributeSet::ClampHealth(float Value) const
{
	// The reference reads FMath::Clamp(Value, 0.0f, GetMaxHealth()). The upper
	// bound is the only thing that moves.
	return FMath::Clamp(Value, 0.0f, GetMaxHealth() - AtMaxHeadroomReserve);
}

void UHealOverTimeAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);

	if (Attribute == GetHealthAttribute())
	{
		NewValue = ClampHealth(NewValue);
	}
}

void UHealOverTimeAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
	Super::PostGameplayEffectExecute(Data);

	if (Data.EvaluatedData.Attribute == GetHealthAttribute())
	{
		SetHealth(ClampHealth(GetHealth()));
	}
}
