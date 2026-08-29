// Copyright CraftBench. All Rights Reserved.
// Supplied editable async bundle lease scaffold. Implement the manager methods
// in BundleLeaseRuntime.cpp; verifier-owned content and tests are not writable.

#pragma once

#include "CoreMinimal.h"
#include "Engine/StreamableManager.h"
#include "GameFramework/Actor.h"
#include "UObject/PrimaryAssetId.h"
#include "BundleLeaseRuntime.generated.h"

USTRUCT()
struct FBundleLeaseKey
{
	GENERATED_BODY()

	FBundleLeaseKey() = default;
	FBundleLeaseKey(const FPrimaryAssetId& InPrimaryAssetId, FName InBundleName)
		: PrimaryAssetId(InPrimaryAssetId)
		, BundleName(InBundleName)
	{
	}

	FPrimaryAssetId PrimaryAssetId;
	FName BundleName = NAME_None;

	bool operator==(const FBundleLeaseKey& Other) const
	{
		return PrimaryAssetId == Other.PrimaryAssetId && BundleName == Other.BundleName;
	}
};

FORCEINLINE uint32 GetTypeHash(const FBundleLeaseKey& Key)
{
	return HashCombine(GetTypeHash(Key.PrimaryAssetId), GetTypeHash(Key.BundleName));
}

struct FBundleLeaseEntry
{
	TSet<TWeakObjectPtr<UObject>> Owners;
	TArray<FStreamableDelegate> PendingCallbacks;
	TSharedPtr<FStreamableHandle> LoadHandle;
	uint64 RequestSerial = 0;
	bool bLoadCompleted = false;
};

UCLASS(BlueprintType)
class THIRDPERSON_API UBundleLeaseManager : public UObject
{
	GENERATED_BODY()

public:
	/** Acquire one owner lease on exactly PrimaryAssetId + BundleName. Completion
	 * may execute in this call or on a later engine tick. */
	void AcquireLease(
		UObject* LeaseOwner,
		const FPrimaryAssetId& PrimaryAssetId,
		FName BundleName,
		FStreamableDelegate Completion);

	/** Release only this owner's current lease. The managed bundle must remain
	 * resident until the last owner of the same identity/bundle releases it. */
	void ReleaseLease(UObject* LeaseOwner);

	int32 GetLeaseCount(const FPrimaryAssetId& PrimaryAssetId, FName BundleName) const;
	bool HasLease(UObject* LeaseOwner) const;

private:
	void CompleteLoad(FBundleLeaseKey Key, uint64 RequestSerial);
	void CompleteRemoval(FBundleLeaseKey Key, uint64 RequestSerial);
	void RemoveDeadOwners(FBundleLeaseKey Key);

	TMap<TWeakObjectPtr<UObject>, FBundleLeaseKey> OwnerToKey;
	TMap<FBundleLeaseKey, FBundleLeaseEntry> Entries;
	uint64 NextRequestSerial = 1;
};

UCLASS()
class THIRDPERSON_API ABundleLeaseHost : public AActor
{
	GENERATED_BODY()

public:
	ABundleLeaseHost();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Bundle lease")
	TObjectPtr<UBundleLeaseManager> LeaseManager = nullptr;
};

UCLASS()
class THIRDPERSON_API ABundleLeaseConsumer : public AActor
{
	GENERATED_BODY()

public:
	ABundleLeaseConsumer();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bundle lease")
	TObjectPtr<ABundleLeaseHost> LeaseHost = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bundle lease")
	FPrimaryAssetId RequestedPrimaryAssetId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bundle lease")
	FName RequestedBundleName = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bundle lease")
	bool bBundleReady = false;

	UFUNCTION(BlueprintCallable, Category = "Bundle lease")
	void AcquireAssignedBundle();

	UFUNCTION(BlueprintCallable, Category = "Bundle lease")
	void ReleaseAssignedBundle();

private:
	void OnAssignedBundleReady(uint64 RequestSerial, FPrimaryAssetId RequestedId, FName BundleName);

	uint64 ActiveRequestSerial = 0;
};
