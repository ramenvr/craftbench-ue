// Copyright CraftBench. All Rights Reserved.

#include "EpochAssetWorldSubsystem.h"

#include "Engine/StreamableManager.h"

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
	// Intentionally empty supplied scaffold. The submission implements the
	// asynchronous load, epoch guard, destination write, and retirement path.
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
