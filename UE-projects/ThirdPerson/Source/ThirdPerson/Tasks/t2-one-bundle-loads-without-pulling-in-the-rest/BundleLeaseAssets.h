// Copyright CraftBench. All Rights Reserved.
// Supplied managed-content schema for
// t2-one-bundle-loads-without-pulling-in-the-rest.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "BundleLeaseAssets.generated.h"

UCLASS(BlueprintType)
class THIRDPERSON_API UBundleLeaseHiddenDependency : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, AssetRegistrySearchable, Category = "Bundle lease")
	double AuthoredMarker = 0.0;
};

UCLASS(BlueprintType)
class THIRDPERSON_API UBundleLeasePayload : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, AssetRegistrySearchable, Category = "Bundle lease")
	FName PayloadIdentity = NAME_None;

	/** Deliberately hard from the selected payload: loading that payload must also
	 * make this hidden dependency resident. An unselected payload and its hidden
	 * dependency must both remain non-resident. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bundle lease")
	TObjectPtr<UBundleLeaseHiddenDependency> HiddenDependency = nullptr;
};

UCLASS(BlueprintType)
class THIRDPERSON_API UBundleLeaseRecord : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	/** The two stable authored bundle names are intentionally public schema.
	 * The world fixture chooses the record identity and one of these names. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, meta = (AssetBundles = "Quartz"), Category = "Bundle lease")
	TSoftObjectPtr<UBundleLeasePayload> QuartzPayload;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, meta = (AssetBundles = "Violet"), Category = "Bundle lease")
	TSoftObjectPtr<UBundleLeasePayload> VioletPayload;

	virtual FPrimaryAssetId GetPrimaryAssetId() const override;
};
