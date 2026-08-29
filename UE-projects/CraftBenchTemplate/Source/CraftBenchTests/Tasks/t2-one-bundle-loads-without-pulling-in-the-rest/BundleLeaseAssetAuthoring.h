// Copyright CraftBench. All Rights Reserved.
// AUTHORING-ONLY, verifier-owned readback helpers for the bundle-lease task.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BundleLeaseAssetAuthoring.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API UBundleLeaseAssetAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Loads and validates the exact 15 authored record/payload/dependency assets,
	 * their classes, fields, PrimaryAssetIds, and bundle load sets. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateAuthoredAssets(FString& OutMessage);

	/** Read-only current-world contract verification. Admission expects only the
	 * native engine-control fixture; final expects the editable host/owners and
	 * production fixture. Neither route executes a Functional Test. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool ValidateCurrentMap(bool bAdmission, FString& OutMessage);
};
