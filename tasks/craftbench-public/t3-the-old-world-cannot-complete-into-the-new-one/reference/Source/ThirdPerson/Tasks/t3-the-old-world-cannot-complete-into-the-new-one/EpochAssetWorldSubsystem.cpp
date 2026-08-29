// Copyright CraftBench. All Rights Reserved.

#include "EpochAssetWorldSubsystem.h"

#include "Engine/AssetManager.h"
#include "Engine/StreamableManager.h"
#include "EpochTravelProtectedTypes.h"

void UEpochAssetWorldSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	BoundWorld = GetWorld();
}

void UEpochAssetWorldSubsystem::Deinitialize()
{
	RetireActiveRequest();
	BoundWorld.Reset();
	Super::Deinitialize();
}

void UEpochAssetWorldSubsystem::BeginEpochRequest(
	const FSoftObjectPath& RecordPath, AEpochAssetDisplay* Destination,
	bool bStartStalled)
{
	RetireActiveRequest();
	if (RecordPath.IsNull() || Destination == nullptr || GetWorld() == nullptr)
	{
		return;
	}
	const uint64 RequestEpoch = ++ActiveEpoch;
	BoundWorld = GetWorld();
	BoundDestination = Destination;
	TWeakObjectPtr<UEpochAssetWorldSubsystem> WeakSelf(this);
	TWeakObjectPtr<UWorld> RequestWorld(GetWorld());
	TWeakObjectPtr<AEpochAssetDisplay> WeakDestination(Destination);
	ActiveHandle = UAssetManager::GetStreamableManager().RequestAsyncLoad(
		RecordPath,
		[WeakSelf, RequestWorld, WeakDestination, RecordPath, RequestEpoch]()
		{
			UEpochAssetWorldSubsystem* Self = WeakSelf.Get();
			AEpochAssetDisplay* LiveDestination = WeakDestination.Get();
			UE_LOG(LogTemp, Display, TEXT(
				"EPOCH-REFERENCE-COMPLETION epoch=%llu self=%d world=%d "
				"destination=%d current_epoch=%llu resolved=%d"),
				RequestEpoch, Self != nullptr ? 1 : 0,
				RequestWorld.IsValid() ? 1 : 0,
				LiveDestination != nullptr ? 1 : 0,
				Self != nullptr ? Self->ActiveEpoch : 0,
				RecordPath.ResolveObject() != nullptr ? 1 : 0);
			if (Self == nullptr || LiveDestination == nullptr
				|| !RequestWorld.IsValid() || Self->GetWorld() != RequestWorld.Get()
				|| LiveDestination->GetWorld() != RequestWorld.Get()
				|| Self->ActiveEpoch != RequestEpoch)
			{
				return;
			}
			UEpochAssetRecord* Record = Cast<UEpochAssetRecord>(
				RecordPath.ResolveObject());
			if (Record != nullptr)
			{
				LiveDestination->ApplyRecord(Record);
			}
		}, FStreamableManager::AsyncLoadHighPriority, false,
		bStartStalled, TEXT("CraftBenchEpochAssetRequest"));
	UE_LOG(LogTemp, Display, TEXT(
		"EPOCH-REFERENCE-REQUEST epoch=%llu path=%s valid=%d active=%d "
		"stalled=%d priority=high"),
		RequestEpoch, *RecordPath.ToString(), ActiveHandle.IsValid() ? 1 : 0,
		ActiveHandle.IsValid() && ActiveHandle->IsActive() ? 1 : 0,
		bStartStalled ? 1 : 0);
}

bool UEpochAssetWorldSubsystem::HasActiveEpochRequest() const
{
	return ActiveHandle.IsValid() && ActiveHandle->IsActive();
}

void UEpochAssetWorldSubsystem::RetireActiveRequest()
{
	++ActiveEpoch;
	if (ActiveHandle.IsValid())
	{
		ActiveHandle->CancelHandle();
		ActiveHandle.Reset();
	}
	BoundDestination.Reset();
}
