// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "LatestMarkerResumeAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ULatestMarkerResumeAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Persistence")
	static FString InspectMap(UObject* WorldContextObject);
};
