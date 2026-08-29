// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "LocalPlayerModalAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ULocalPlayerModalAssetAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool CreateBaselineAssets();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateBaselineAssets();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool BuildReferenceGraphs();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectSubmissionAssets();
};
