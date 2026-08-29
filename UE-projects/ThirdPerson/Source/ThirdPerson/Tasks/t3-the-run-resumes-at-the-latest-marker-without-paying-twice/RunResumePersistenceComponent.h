// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "RunResumePersistenceComponent.generated.h"

class ARunResumeReward;

/** Editable persistence surface supplied to the task agent. */
UCLASS(ClassGroup = (CraftBench), meta = (BlueprintSpawnableComponent))
class THIRDPERSON_API URunResumePersistenceComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	URunResumePersistenceComponent();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Persistence")
	void ConfigurePersistence(const FString& InSlotName, int32 InUserIndex,
		const FString& InRunNonce);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Persistence")
	bool RecordCheckpoint(FName CheckpointId,
		const FTransform& CheckpointTransform);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Persistence")
	bool CollectReward(ARunResumeReward* Reward);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Persistence")
	bool RestoreFromSlot(AActor* Subject,
		const TArray<ARunResumeReward*>& Rewards);

	UFUNCTION(BlueprintPure, Category = "CraftBench|Persistence")
	int32 GetRewardTotal() const { return RewardTotal; }

	UFUNCTION(BlueprintPure, Category = "CraftBench|Persistence")
	bool IsRewardCollected(FName RewardId) const;

	UFUNCTION(BlueprintPure, Category = "CraftBench|Persistence")
	FName GetLatestCheckpointId() const { return LatestCheckpointId; }

private:
	bool SaveCurrentRecord();

	UPROPERTY(Transient)
	FString SlotName;

	UPROPERTY(Transient)
	int32 UserIndex = 0;

	UPROPERTY(Transient)
	FString RunNonce;

	UPROPERTY(Transient)
	FName LatestCheckpointId = NAME_None;

	UPROPERTY(Transient)
	FTransform LatestCheckpointTransform = FTransform::Identity;

	UPROPERTY(Transient)
	TSet<FName> CollectedRewardIds;

	UPROPERTY(Transient)
	int32 RewardTotal = 0;
};
