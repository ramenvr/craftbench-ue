// Copyright CraftBench. All Rights Reserved.

#include "RunResumePersistenceComponent.h"

#include "RunResumeProtectedTypes.h"

URunResumePersistenceComponent::URunResumePersistenceComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void URunResumePersistenceComponent::ConfigurePersistence(
	const FString& InSlotName, int32 InUserIndex, const FString& InRunNonce)
{
	SlotName = InSlotName;
	UserIndex = InUserIndex;
	RunNonce = InRunNonce;
}

bool URunResumePersistenceComponent::RecordCheckpoint(
	FName CheckpointId, const FTransform& CheckpointTransform)
{
	return false;
}

bool URunResumePersistenceComponent::CollectReward(ARunResumeReward* Reward)
{
	return false;
}

bool URunResumePersistenceComponent::RestoreFromSlot(
	AActor* Subject, const TArray<ARunResumeReward*>& Rewards)
{
	return false;
}

bool URunResumePersistenceComponent::IsRewardCollected(FName RewardId) const
{
	return CollectedRewardIds.Contains(RewardId);
}

bool URunResumePersistenceComponent::SaveCurrentRecord()
{
	return false;
}
