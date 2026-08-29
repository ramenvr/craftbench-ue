// Copyright CraftBench. All Rights Reserved.
// Reference implementation for exact, lease-counted Asset Manager bundles.

#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.h"

#include "Engine/AssetManager.h"

void UBundleLeaseManager::AcquireLease(
	UObject* LeaseOwner,
	const FPrimaryAssetId& PrimaryAssetId,
	FName BundleName,
	FStreamableDelegate Completion)
{
	if (!IsValid(LeaseOwner) || !PrimaryAssetId.IsValid() || BundleName.IsNone())
	{
		return;
	}

	const FBundleLeaseKey NewKey(PrimaryAssetId, BundleName);
	const TWeakObjectPtr<UObject> OwnerKey(LeaseOwner);
	if (const FBundleLeaseKey* ExistingKey = OwnerToKey.Find(OwnerKey))
	{
		if (!(*ExistingKey == NewKey))
		{
			ReleaseLease(LeaseOwner);
		}
		else if (FBundleLeaseEntry* ExistingEntry = Entries.Find(NewKey))
		{
			if (ExistingEntry->bLoadCompleted)
			{
				Completion.ExecuteIfBound();
			}
			else
			{
				ExistingEntry->PendingCallbacks.Add(MoveTemp(Completion));
			}
			return;
		}
	}

	FBundleLeaseEntry* Entry = Entries.Find(NewKey);
	if (Entry)
	{
		Entry->Owners.Add(LeaseOwner);
		OwnerToKey.Add(OwnerKey, NewKey);
		if (Entry->bLoadCompleted)
		{
			Completion.ExecuteIfBound();
		}
		else
		{
			Entry->PendingCallbacks.Add(MoveTemp(Completion));
		}
		return;
	}

	FBundleLeaseEntry& NewEntry = Entries.Add(NewKey);
	NewEntry.Owners.Add(LeaseOwner);
	NewEntry.PendingCallbacks.Add(MoveTemp(Completion));
	NewEntry.RequestSerial = NextRequestSerial++;
	OwnerToKey.Add(OwnerKey, NewKey);

	const uint64 RequestSerial = NewEntry.RequestSerial;
	TSharedPtr<FStreamableHandle> RequestHandle = UAssetManager::Get().LoadPrimaryAsset(
		PrimaryAssetId,
		{ BundleName },
		FStreamableDelegate::CreateUObject(
			this,
			&UBundleLeaseManager::CompleteLoad,
			NewKey,
			RequestSerial));

	// Completion is permitted to execute synchronously. Re-find the entry after
	// LoadPrimaryAsset instead of retaining a reference across the callback.
	if (FBundleLeaseEntry* CurrentEntry = Entries.Find(NewKey);
		CurrentEntry && CurrentEntry->RequestSerial == RequestSerial)
	{
		CurrentEntry->LoadHandle = MoveTemp(RequestHandle);
	}
}

void UBundleLeaseManager::ReleaseLease(UObject* LeaseOwner)
{
	if (!LeaseOwner)
	{
		return;
	}

	FBundleLeaseKey Key;
	const TWeakObjectPtr<UObject> OwnerKey(LeaseOwner);
	if (!OwnerToKey.RemoveAndCopyValue(OwnerKey, Key))
	{
		return;
	}

	FBundleLeaseEntry* Entry = Entries.Find(Key);
	if (!Entry)
	{
		return;
	}
	Entry->Owners.Remove(LeaseOwner);
	RemoveDeadOwners(Key);
	Entry = Entries.Find(Key);
	if (!Entry || Entry->Owners.Num() > 0)
	{
		return;
	}

	// Drop our copy of the old bundle handle before asking Asset Manager to
	// remove only this bundle. The manager's pending/current state retains the
	// replacement primary-only request; no user handle can pin the old payload.
	Entry->LoadHandle.Reset();
	Entries.Remove(Key);
	UAssetManager::Get().ChangeBundleStateForPrimaryAssets(
		{ Key.PrimaryAssetId },
		{},
		{ Key.BundleName },
		false);
}

int32 UBundleLeaseManager::GetLeaseCount(
	const FPrimaryAssetId& PrimaryAssetId,
	FName BundleName) const
{
	const FBundleLeaseKey Key(PrimaryAssetId, BundleName);
	if (const FBundleLeaseEntry* Entry = Entries.Find(Key))
	{
		return Entry->Owners.Num();
	}
	return 0;
}

bool UBundleLeaseManager::HasLease(UObject* LeaseOwner) const
{
	return LeaseOwner && OwnerToKey.Contains(TWeakObjectPtr<UObject>(LeaseOwner));
}

void UBundleLeaseManager::CompleteLoad(FBundleLeaseKey Key, uint64 RequestSerial)
{
	FBundleLeaseEntry* Entry = Entries.Find(Key);
	if (!Entry || Entry->RequestSerial != RequestSerial)
	{
		return;
	}
	Entry->bLoadCompleted = true;
	TArray<FStreamableDelegate> Callbacks = MoveTemp(Entry->PendingCallbacks);
	Entry->PendingCallbacks.Reset();
	for (FStreamableDelegate& Callback : Callbacks)
	{
		Callback.ExecuteIfBound();
	}
}

void UBundleLeaseManager::CompleteRemoval(FBundleLeaseKey Key, uint64 RequestSerial)
{
	// Removal is observed through Asset Manager's engine-owned bundle state.
}

void UBundleLeaseManager::RemoveDeadOwners(FBundleLeaseKey Key)
{
	FBundleLeaseEntry* Entry = Entries.Find(Key);
	if (!Entry)
	{
		return;
	}
	for (auto It = Entry->Owners.CreateIterator(); It; ++It)
	{
		if (!It->IsValid())
		{
			OwnerToKey.Remove(*It);
			It.RemoveCurrent();
		}
	}
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
