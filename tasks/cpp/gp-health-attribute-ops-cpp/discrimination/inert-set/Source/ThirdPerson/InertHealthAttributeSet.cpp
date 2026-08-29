// Copyright CraftBench. All Rights Reserved.

#include "InertHealthAttributeSet.h"

void UInertHealthAttributeSet::PreAttributeBaseChange(const FGameplayAttribute& Attribute, float& NewValue) const
{
	Super::PreAttributeBaseChange(Attribute, NewValue);

	// Only Health is shadowed -- MaxHealth and Power keep working, so this is an
	// inert HEALTH attribute and not a broken attribute set.
	if (Attribute == GetHealthAttribute())
	{
		NewValue = InertShadowHealth;
	}
}

void UInertHealthAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);

	if (Attribute == GetHealthAttribute())
	{
		NewValue = InertShadowHealth;
	}
}
