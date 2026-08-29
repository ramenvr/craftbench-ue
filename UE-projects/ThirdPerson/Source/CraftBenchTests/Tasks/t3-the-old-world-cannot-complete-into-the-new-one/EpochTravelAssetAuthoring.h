// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EpochTravelAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UEpochTravelAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Epoch")
	static FString InspectRecords();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Epoch")
	static FString InspectMap(UObject* WorldContextObject, bool bStartMap);
};
