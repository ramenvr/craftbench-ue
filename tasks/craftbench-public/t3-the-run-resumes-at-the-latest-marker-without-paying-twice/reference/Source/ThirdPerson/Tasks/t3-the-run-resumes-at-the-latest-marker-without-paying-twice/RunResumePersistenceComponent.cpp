// Copyright CraftBench. All Rights Reserved.

#include "RunResumePersistenceComponent.h"

#include "Kismet/GameplayStatics.h"
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
	if (SlotName.IsEmpty() || RunNonce.IsEmpty() || CheckpointId.IsNone()
		|| !CheckpointTransform.IsValid())
	{
		return false;
	}
	LatestCheckpointId = CheckpointId;
	LatestCheckpointTransform = CheckpointTransform;
	return SaveCurrentRecord();
}

bool URunResumePersistenceComponent::CollectReward(ARunResumeReward* Reward)
{
	if (Reward == nullptr || Reward->RewardId.IsNone()
		|| Reward->RewardValue <= 0
		|| CollectedRewardIds.Contains(Reward->RewardId))
	{
		return false;
	}
	CollectedRewardIds.Add(Reward->RewardId);
	RewardTotal += Reward->RewardValue;
	if (!SaveCurrentRecord())
	{
		CollectedRewardIds.Remove(Reward->RewardId);
		RewardTotal -= Reward->RewardValue;
		return false;
	}
	Reward->SetRetired(true);
	return true;
}

bool URunResumePersistenceComponent::RestoreFromSlot(
	AActor* Subject, const TArray<ARunResumeReward*>& Rewards)
{
	if (Subject == nullptr || SlotName.IsEmpty() || RunNonce.IsEmpty())
	{
		return false;
	}
	URunResumeSaveGame* Record = Cast<URunResumeSaveGame>(
		UGameplayStatics::LoadGameFromSlot(SlotName, UserIndex));
	if (Record == nullptr || Record->SchemaVersion != 1
		|| Record->RunNonce != RunNonce || Record->LatestCheckpointId.IsNone()
		|| !Record->LatestCheckpointTransform.IsValid())
	{
		return false;
	}
	LatestCheckpointId = Record->LatestCheckpointId;
	LatestCheckpointTransform = Record->LatestCheckpointTransform;
	CollectedRewardIds.Reset();
	for (FName RewardId : Record->CollectedRewardIds)
	{
		CollectedRewardIds.Add(RewardId);
	}
	RewardTotal = Record->RewardTotal;
	Subject->SetActorTransform(LatestCheckpointTransform, false, nullptr,
		ETeleportType::TeleportPhysics);
	for (ARunResumeReward* Reward : Rewards)
	{
		if (Reward != nullptr)
		{
			Reward->SetRetired(CollectedRewardIds.Contains(Reward->RewardId));
		}
	}
	return true;
}

bool URunResumePersistenceComponent::IsRewardCollected(FName RewardId) const
{
	return CollectedRewardIds.Contains(RewardId);
}

bool URunResumePersistenceComponent::SaveCurrentRecord()
{
	if (SlotName.IsEmpty() || RunNonce.IsEmpty())
	{
		return false;
	}
	URunResumeSaveGame* Record = Cast<URunResumeSaveGame>(
		UGameplayStatics::CreateSaveGameObject(URunResumeSaveGame::StaticClass()));
	if (Record == nullptr)
	{
		return false;
	}
	Record->SchemaVersion = 1;
	Record->RunNonce = RunNonce;
	Record->LatestCheckpointId = LatestCheckpointId;
	Record->LatestCheckpointTransform = LatestCheckpointTransform;
	Record->CollectedRewardIds = CollectedRewardIds.Array();
	Record->CollectedRewardIds.Sort(
		[](FName Left, FName Right)
		{
			return Left.LexicalLess(Right);
		});
	Record->RewardTotal = RewardTotal;
	return UGameplayStatics::SaveGameToSlot(Record, SlotName, UserIndex);
}
