// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WalkerYieldAuthoringLibrary.generated.h"

class AActor;
class UBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UWalkerYieldAuthoringLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString ConfigureWalkerBlueprint(
		UBlueprint* Blueprint, bool bEnableAvoidance, float AvoidanceWeight,
		float ConsiderationRadius);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectWalkerBlueprint(
		UBlueprint* Blueprint, bool bExpectAvoidance, float ExpectedWeight,
		float ExpectedConsiderationRadius);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString ConfigureGoalMarker(AActor* GoalActor);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString BuildNavigation(UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectWorld(
		UObject* WorldContextObject, int32 ExpectedScenarios,
		int32 ExpectedFixtures, int32 ExpectedWalkers, int32 ExpectedGoals);
};
