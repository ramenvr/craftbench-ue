// Copyright CraftBench. All Rights Reserved.
//
// Supplied editable runtime surface for task
// t2-shared-helper-lives-until-the-last-lease-ends. The declarations expose
// one game-instance cache, lease tokens, and ordinary UObject helpers. The
// requested acquisition/release behavior is intentionally not implemented.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "UObject/WeakObjectPtrTemplates.h"
#include "SharedHelperLeaseSubsystem.generated.h"

UCLASS(BlueprintType)
class THIRDPERSON_API USharedLeaseHelper : public UObject
{
	GENERATED_BODY()

public:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	FName Key = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	int32 Version = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	FString Payload;
};

UCLASS(BlueprintType)
class THIRDPERSON_API USharedHelperLease : public UObject
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintPure, Category = "Shared Helper")
	USharedLeaseHelper* GetHelper() const { return Helper; }

	UFUNCTION(BlueprintPure, Category = "Shared Helper")
	bool IsActive() const { return !bReleased && Helper != nullptr; }

	/** Reflected strong reference: an active lease keeps its helper alive. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	TObjectPtr<USharedLeaseHelper> Helper;

	/** The requester is observed, never owned, by its lease. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	TWeakObjectPtr<UObject> Owner;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	FName Key = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	int32 Version = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	bool bReleased = false;
};

USTRUCT(BlueprintType)
struct THIRDPERSON_API FSharedHelperCacheEntry
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	FName Key = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	int32 Version = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	bool bRetired = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	TObjectPtr<USharedLeaseHelper> Helper;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Shared Helper")
	TArray<TObjectPtr<USharedHelperLease>> Leases;
};

/**
 * Pre-existing subsystem for task
 * t2-shared-helper-lives-until-the-last-lease-ends.
 *
 * Agents may edit this supplied header/source pair. They must not replace the
 * verifier-owned owners, GC schedule, keys, versions, or payloads.
 */
UCLASS(BlueprintType)
class THIRDPERSON_API USharedHelperLeaseSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** Acquire one lease for the current key/version/payload. */
	UFUNCTION(BlueprintCallable, Category = "Shared Helper")
	USharedHelperLease* AcquireLease(
		UObject* Owner,
		FName Key,
		int32 Version,
		const FString& Payload);

	/** End exactly this lease; unrelated and sibling leases remain active. */
	UFUNCTION(BlueprintCallable, Category = "Shared Helper")
	bool ReleaseLease(USharedHelperLease* Lease);

protected:
	/** Reflected subsystem-owned cache. Ordinary GC is the only destruction path. */
	UPROPERTY(Transient)
	TArray<FSharedHelperCacheEntry> CacheEntries;

	/** Reflected active tokens; a released token must be removed from this set. */
	UPROPERTY(Transient)
	TArray<TObjectPtr<USharedHelperLease>> ActiveLeases;
};
