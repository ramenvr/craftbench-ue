// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY, AUTHORING-ONLY helper for the menu/input-routing task.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "MenuInputAssetAuthoring.generated.h"

class UWorld;

UCLASS()
class CRAFTBENCHTESTS_API UMenuInputAssetAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Fail-closed creation of one empty editable WBP and protected two-leg input assets. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool CreateAdmissionAssets();

	/** Independent exact readback for freshly authored baseline/support assets. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateAdmissionAssets();

	/**
	 * Author the reference behavior into the exact existing baseline WBP.
	 * The external closure runner owns byte-level baseline parking and rollback.
	 */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool BuildReferenceMenuGraph();

	/** Fixed L2I graph inspection. The returned string is one JSON object. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Introspection")
	static FString InspectSubmissionAsset();

	/** Cold editor-world contract inspection. Never starts either fixture. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectAdmissionMapContract(UWorld* World);
};
