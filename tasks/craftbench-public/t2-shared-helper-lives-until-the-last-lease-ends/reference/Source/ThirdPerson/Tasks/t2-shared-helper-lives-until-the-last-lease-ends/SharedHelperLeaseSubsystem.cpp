// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.h"

#include "UObject/Package.h"

USharedHelperLease* USharedHelperLeaseSubsystem::AcquireLease(
	UObject* Owner,
	const FName Key,
	const int32 Version,
	const FString& Payload)
{
	if (Owner == nullptr || Key.IsNone() || Version < 0)
	{
		return nullptr;
	}

	FSharedHelperCacheEntry* Selected = nullptr;
	for (FSharedHelperCacheEntry& Entry : CacheEntries)
	{
		if (Entry.Key == Key && Entry.Version == Version && !Entry.bRetired)
		{
			if (Entry.Helper == nullptr || Entry.Helper->Payload != Payload)
			{
				return nullptr;
			}
			Selected = &Entry;
			break;
		}
	}

	if (Selected == nullptr)
	{
		for (FSharedHelperCacheEntry& Entry : CacheEntries)
		{
			if (Entry.Key == Key)
			{
				Entry.bRetired = true;
			}
		}

		USharedLeaseHelper* Helper = NewObject<USharedLeaseHelper>(
			GetTransientPackage(), NAME_None, RF_Transient);
		Helper->Key = Key;
		Helper->Version = Version;
		Helper->Payload = Payload;

		FSharedHelperCacheEntry& Added = CacheEntries.AddDefaulted_GetRef();
		Added.Key = Key;
		Added.Version = Version;
		Added.Helper = Helper;
		Selected = &Added;
	}

	USharedHelperLease* Lease = NewObject<USharedHelperLease>(this, NAME_None, RF_Transient);
	Lease->Helper = Selected->Helper;
	Lease->Owner = Owner;
	Lease->Key = Key;
	Lease->Version = Version;
	Lease->bReleased = false;
	Selected->Leases.Add(Lease);
	ActiveLeases.Add(Lease);
	return Lease;
}

bool USharedHelperLeaseSubsystem::ReleaseLease(USharedHelperLease* Lease)
{
	if (Lease == nullptr || Lease->bReleased || ActiveLeases.RemoveSingleSwap(Lease) != 1)
	{
		return false;
	}

	for (int32 Index = 0; Index < CacheEntries.Num(); ++Index)
	{
		FSharedHelperCacheEntry& Entry = CacheEntries[Index];
		if (Entry.Leases.RemoveSingleSwap(Lease) == 1)
		{
			if (Entry.Leases.IsEmpty())
			{
				CacheEntries.RemoveAtSwap(Index);
			}
			break;
		}
	}

	Lease->Helper = nullptr;
	Lease->Owner.Reset();
	Lease->bReleased = true;
	return true;
}
