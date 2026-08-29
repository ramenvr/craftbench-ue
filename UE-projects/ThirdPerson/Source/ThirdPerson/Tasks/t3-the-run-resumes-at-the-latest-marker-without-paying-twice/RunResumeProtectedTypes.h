// Copyright CraftBench. All Rights Reserved.
// PROTECTED TASK SUPPORT - NOT PART OF THE EDITABLE SUBMISSION.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/SaveGame.h"
#include "RunResumeProtectedTypes.generated.h"

class URunResumePersistenceComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API URunResumeSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY()
	int32 SchemaVersion = 1;

	UPROPERTY()
	FString RunNonce;

	UPROPERTY()
	FName LatestCheckpointId = NAME_None;

	UPROPERTY()
	FTransform LatestCheckpointTransform = FTransform::Identity;

	UPROPERTY()
	TArray<FName> CollectedRewardIds;

	UPROPERTY()
	int32 RewardTotal = 0;
};

UCLASS()
class THIRDPERSON_API ARunResumeCheckpoint : public AActor
{
	GENERATED_BODY()

public:
	ARunResumeCheckpoint();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench")
	FName CheckpointId = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench")
	TObjectPtr<UStaticMeshComponent> MarkerMesh;
};

UCLASS()
class THIRDPERSON_API ARunResumeReward : public AActor
{
	GENERATED_BODY()

public:
	ARunResumeReward();

	UFUNCTION(BlueprintCallable, Category = "CraftBench")
	void SetRetired(bool bInRetired);

	UFUNCTION(BlueprintPure, Category = "CraftBench")
	bool IsRetired() const { return bRetired; }

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench")
	FName RewardId = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench")
	int32 RewardValue = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench")
	TObjectPtr<UStaticMeshComponent> RewardMesh;

private:
	UPROPERTY(VisibleInstanceOnly, Category = "CraftBench")
	bool bRetired = false;
};

UCLASS()
class THIRDPERSON_API ARunResumeSubject : public AActor
{
	GENERATED_BODY()

public:
	ARunResumeSubject();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench")
	TObjectPtr<UStaticMeshComponent> SubjectMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench")
	TObjectPtr<URunResumePersistenceComponent> Persistence;
};
