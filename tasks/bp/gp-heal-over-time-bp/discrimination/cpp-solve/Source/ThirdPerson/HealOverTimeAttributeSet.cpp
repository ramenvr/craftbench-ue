// Copyright CraftBench. All Rights Reserved.

#include "HealOverTimeAttributeSet.h"

// FGameplayEffectModCallbackData lives here; it only FORWARD-declares
// FGameplayModifierEvaluatedData, so GameplayEffectTypes.h is what makes
// Data.EvaluatedData.Attribute a complete type. Included explicitly rather than
// leaned on transitively through AbilitySystemComponent.h.
#include "GameplayEffectExtension.h"
#include "GameplayEffectTypes.h"

float UHealOverTimeAttributeSet::ClampHealth(float Value) const
{
	// The cap is read from the pawn's OWN MaxHealth attribute, not from a
	// constant. A pawn that never initializes MaxHealth therefore clamps every
	// restore to zero -- which is the honest consequence of leaving it at its
	// default, and is deliberately NOT special-cased here (special-casing it
	// would be writing to the gate rather than to the invariant).
	return FMath::Clamp(Value, 0.0f, GetMaxHealth());
}

void UHealOverTimeAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);

	// CURRENT value only. FGameplayAttribute::SetNumericValueChecked calls this
	// by reference just before it writes, so every read-back of Health obeys the
	// cap -- including reads of a value produced by a duration/infinite
	// aggregator modifier, which never touches the base value at all.
	if (Attribute == GetHealthAttribute())
	{
		NewValue = ClampHealth(NewValue);
	}
}

void UHealOverTimeAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
	Super::PostGameplayEffectExecute(Data);

	// BASE value. An instant or PERIODIC execution writes straight into the base
	// value, so by the time this runs the stored value may already be above the
	// cap even though PreAttributeChange has kept the read-back at exactly
	// MaxHealth. Writing the clamped value back through the base setter is what
	// keeps the two in step.
	//
	// GetHealth() reads the CURRENT value (that is what
	// GAMEPLAYATTRIBUTE_VALUE_GETTER generates) and SetHealth() writes the BASE
	// value via SetNumericAttributeBase (GAMEPLAYATTRIBUTE_VALUE_SETTER). That
	// asymmetry is the standard recipe and is what makes this one line correct:
	// PreAttributeChange has already clamped the current value, so this copies
	// the honest number down onto the stored one.
	if (Data.EvaluatedData.Attribute == GetHealthAttribute())
	{
		SetHealth(ClampHealth(GetHealth()));
	}
}
