// Copyright CraftBench. All Rights Reserved.
// VERIFIER/AUTHORING-ONLY - candidates cannot submit this surface.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ReplicatedDoorAssetAuthoring.generated.h"

class UWorld;

UCLASS()
class CRAFTBENCHTESTS_API UReplicatedDoorAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString CreateBaselineDoorBlueprint();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString CreateAdmissionDoorBlueprint();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString BuildReferenceDoorGraph();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectDoorBlueprint(bool bAdmission, bool bExpectSolved);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectDoorMap(UWorld* World, bool bAdmission);
};
