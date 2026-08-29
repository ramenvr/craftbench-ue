// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "SharedHelperLeaseFunctionalTest.generated.h"

class USharedHelperLease;
class USharedHelperLeaseSubsystem;
class USharedLeaseHelper;
class UStaticMeshComponent;

UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API USharedHelperGcWitness : public UObject
{
	GENERATED_BODY()
};

/** Verifier-owned requester. It carries no cache or lease implementation. */
UCLASS(NotBlueprintable)
class CRAFTBENCHTESTS_API ASharedHelperLeaseOwner : public AActor
{
	GENERATED_BODY()

public:
	ASharedHelperLeaseOwner();

private:
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UStaticMeshComponent> Marker;
};

/**
 * World-clock L2 fixture. All keys, versions, payloads, owners, releases, GC
 * requests, and weak identity observations are verifier-owned live facts.
 */
UCLASS()
class CRAFTBENCHTESTS_API ASharedHelperLeaseFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ASharedHelperLeaseFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool ValidateInitialSharing(FString& OutDetail) const;
	bool ValidateFirstRelease(FString& OutDetail) const;
	bool ValidateReplacement(FString& OutDetail) const;
	bool ValidateRetiredCollected(FString& OutDetail) const;
	bool ValidateFinalCollection(FString& OutDetail) const;
	bool ReleaseExact(TObjectPtr<USharedHelperLease>& Lease, FString& OutDetail);
	bool RequirePreviousGc(FString& OutDetail) const;
	bool RequestFixtureGc(FString& OutDetail);
	void FailNamed(const TCHAR* Gate, double TimeSeconds, int32 CheckpointIndex, const FString& Detail);

	UPROPERTY(Transient)
	TObjectPtr<ASharedHelperLeaseOwner> OwnerA;

	UPROPERTY(Transient)
	TObjectPtr<ASharedHelperLeaseOwner> OwnerB;

	UPROPERTY(Transient)
	TObjectPtr<ASharedHelperLeaseOwner> OwnerControl;

	UPROPERTY(Transient)
	TObjectPtr<USharedHelperLease> LeaseA;

	UPROPERTY(Transient)
	TObjectPtr<USharedHelperLease> LeaseB;

	UPROPERTY(Transient)
	TObjectPtr<USharedHelperLease> LeaseNew;

	UPROPERTY(Transient)
	TObjectPtr<USharedHelperLease> LeaseControl;

	TWeakObjectPtr<USharedHelperLeaseSubsystem> Subject;
	TWeakObjectPtr<USharedLeaseHelper> OldHelper;
	TWeakObjectPtr<USharedLeaseHelper> NewHelper;
	TWeakObjectPtr<USharedLeaseHelper> ControlHelper;
	TWeakObjectPtr<USharedHelperGcWitness> GcWitness;

	FName PrimaryKey = NAME_None;
	FName ControlKey = NAME_None;
	int32 OldVersion = INDEX_NONE;
	int32 NewVersion = INDEX_NONE;
	FString OldPayload;
	FString NewPayload;
	FString ControlPayload;
	double EpochWorldSeconds = 0.0;
};
