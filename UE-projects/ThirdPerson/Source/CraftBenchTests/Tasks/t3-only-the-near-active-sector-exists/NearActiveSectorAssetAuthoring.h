// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY, EDITOR/AUTHORING ONLY.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "NearActiveSectorAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UNearActiveSectorAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString CreateDataLayerAssets(bool bAdmission);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectDataLayerAssets(bool bAdmission);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString CreateBaselineController();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString BuildReferenceControllerGraph();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString ConfigureMap(UWorld* World, bool bAdmission);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectMap(UWorld* World, bool bAdmission);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectController(bool bReferenceExpected);
};
