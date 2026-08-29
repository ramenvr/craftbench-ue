// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY editor authoring helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GuardVisibleAimAssetAuthoring.generated.h"

class AGuardVisibleAimCharacter;
class UAnimBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UGuardVisibleAimAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Guard Aim")
	static FString BuildAnimGraph(
		UAnimBlueprint* AnimBlueprint, bool bCompleteAimOverlay);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Guard Aim")
	static FString ConfigureGuard(
		AGuardVisibleAimCharacter* Guard, UAnimBlueprint* AnimBlueprint);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Guard Aim")
	static FString BuildNavigation(UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Guard Aim")
	static FString InspectWorld(
		UObject* WorldContextObject, bool bAdmission);
};
