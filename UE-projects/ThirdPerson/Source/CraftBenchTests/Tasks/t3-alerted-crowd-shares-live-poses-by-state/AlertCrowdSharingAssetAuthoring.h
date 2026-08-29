// Copyright CraftBench. All Rights Reserved.
// Verifier-only one-shot asset authoring/readback helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AlertCrowdSharingAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UAlertCrowdSharingAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString AuthorAdmissionAssets();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString InspectAdmissionAssets();

	/** Later owner-only baseline step; never called by admission authoring. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString AuthorEmptyFinalScaffold();

	/** Disposable-substrate reference step; refuses any existing final package. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString AuthorReferenceAssets();

	/** Read-only final/reference inspection with an explicit completeness contract. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString InspectFinalAssets(bool bExpectedComplete);
};
