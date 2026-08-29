// Copyright CraftBench. All Rights Reserved.
// Agent-writable scaffold: the supplied owner entry points are wired, while
// lease sharing and Asset Manager bundle transitions are intentionally empty.

#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.h"

void UBundleLeaseManager::AcquireLease(
	UObject* LeaseOwner,
	const FPrimaryAssetId& PrimaryAssetId,
	FName BundleName,
	FStreamableDelegate Completion)
{
	// TODO: implement exact managed-bundle acquisition and shared owner leases.
}

void UBundleLeaseManager::ReleaseLease(UObject* LeaseOwner)
{
	// TODO: release only this owner's lease and remove the bundle after the last owner.
}

int32 UBundleLeaseManager::GetLeaseCount(const FPrimaryAssetId& PrimaryAssetId, FName BundleName) const
{
	return 0;
}

bool UBundleLeaseManager::HasLease(UObject* LeaseOwner) const
{
	return false;
}

void UBundleLeaseManager::CompleteLoad(FBundleLeaseKey Key, uint64 RequestSerial)
{
}

void UBundleLeaseManager::CompleteRemoval(FBundleLeaseKey Key, uint64 RequestSerial)
{
}

void UBundleLeaseManager::RemoveDeadOwners(FBundleLeaseKey Key)
{
}

ABundleLeaseHost::ABundleLeaseHost()
{
	PrimaryActorTick.bCanEverTick = false;
	LeaseManager = CreateDefaultSubobject<UBundleLeaseManager>(TEXT("BundleLeaseManager"));
	Tags.Add(TEXT("BundleLease.Host"));
}

ABundleLeaseConsumer::ABundleLeaseConsumer()
{
	PrimaryActorTick.bCanEverTick = false;
}

void ABundleLeaseConsumer::AcquireAssignedBundle()
{
	++ActiveRequestSerial;
	bBundleReady = false;
	if (!LeaseHost || !LeaseHost->LeaseManager)
	{
		return;
	}

	const uint64 RequestSerial = ActiveRequestSerial;
	const FPrimaryAssetId RequestId = RequestedPrimaryAssetId;
	const FName BundleName = RequestedBundleName;
	LeaseHost->LeaseManager->AcquireLease(
		this,
		RequestId,
		BundleName,
		FStreamableDelegate::CreateUObject(
			this,
			&ABundleLeaseConsumer::OnAssignedBundleReady,
			RequestSerial,
			RequestId,
			BundleName));
}

void ABundleLeaseConsumer::ReleaseAssignedBundle()
{
	++ActiveRequestSerial;
	bBundleReady = false;
	if (LeaseHost && LeaseHost->LeaseManager)
	{
		LeaseHost->LeaseManager->ReleaseLease(this);
	}
}

void ABundleLeaseConsumer::OnAssignedBundleReady(
	uint64 RequestSerial,
	FPrimaryAssetId RequestedId,
	FName BundleName)
{
	if (RequestSerial == ActiveRequestSerial
		&& RequestedId == RequestedPrimaryAssetId
		&& BundleName == RequestedBundleName)
	{
		bBundleReady = true;
	}
}
