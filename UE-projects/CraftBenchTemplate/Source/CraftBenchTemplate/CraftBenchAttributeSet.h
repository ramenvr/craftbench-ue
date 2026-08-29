// Copyright CraftBench. All Rights Reserved.
//
// Minimal attribute set for CraftBench pawn/GAS tasks. The launch task
// (gp-gas-launch) does not touch attributes; this exists so attribute-moving
// abilities (heal/buff/damage tasks) have generic attributes to move. Kept
// deliberately small — no clamping,
// no GameplayEffect execution logic at v1.0.

#pragma once

#include "CoreMinimal.h"
#include "AttributeSet.h"
#include "AbilitySystemComponent.h"
#include "CraftBenchAttributeSet.generated.h"

// Standard GAS accessor boilerplate (getter / value getter / setter / initter).
#define ATTRIBUTE_ACCESSORS(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)

UCLASS()
class CRAFTBENCHTEMPLATE_API UCraftBenchAttributeSet : public UAttributeSet
{
	GENERATED_BODY()

public:
	UPROPERTY(BlueprintReadOnly, Category = "CraftBench|Attributes")
	FGameplayAttributeData Health;
	ATTRIBUTE_ACCESSORS(UCraftBenchAttributeSet, Health)

	UPROPERTY(BlueprintReadOnly, Category = "CraftBench|Attributes")
	FGameplayAttributeData MaxHealth;
	ATTRIBUTE_ACCESSORS(UCraftBenchAttributeSet, MaxHealth)

	UPROPERTY(BlueprintReadOnly, Category = "CraftBench|Attributes")
	FGameplayAttributeData Power;
	ATTRIBUTE_ACCESSORS(UCraftBenchAttributeSet, Power)
};
