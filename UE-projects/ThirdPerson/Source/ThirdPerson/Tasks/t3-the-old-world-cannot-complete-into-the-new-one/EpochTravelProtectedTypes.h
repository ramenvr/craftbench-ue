// Copyright CraftBench. All Rights Reserved.
// PROTECTED TASK SUPPORT - NOT PART OF THE EDITABLE SUBMISSION.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "FunctionalTest.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "UObject/SoftObjectPtr.h"
#include "EpochTravelProtectedTypes.generated.h"

class AEpochAssetDisplay;
class UEpochAssetWorldSubsystem;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API UEpochAssetRecord : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench")
	FName RecordId = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "CraftBench")
	int32 RecordValue = 0;
};

UCLASS()
class THIRDPERSON_API AEpochAssetDisplay : public AActor
{
	GENERATED_BODY()

public:
	AEpochAssetDisplay();

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Epoch")
	void ApplyRecord(UEpochAssetRecord* Record);

	UFUNCTION(BlueprintPure, Category = "CraftBench|Epoch")
	FName GetAppliedRecordId() const { return AppliedRecordId; }

	UFUNCTION(BlueprintPure, Category = "CraftBench|Epoch")
	int32 GetAppliedValue() const { return AppliedValue; }

	UFUNCTION(BlueprintPure, Category = "CraftBench|Epoch")
	int32 GetApplyCount() const { return ApplyCount; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "CraftBench")
	TObjectPtr<UStaticMeshComponent> DisplayMesh;

private:
	UPROPERTY(VisibleInstanceOnly, Category = "CraftBench")
	FName AppliedRecordId = NAME_None;

	UPROPERTY(VisibleInstanceOnly, Category = "CraftBench")
	int32 AppliedValue = 0;

	UPROPERTY(VisibleInstanceOnly, Category = "CraftBench")
	int32 ApplyCount = 0;
};

/** Verifier-owned primitive/weak record that survives ordinary map travel. */
UCLASS()
class THIRDPERSON_API UEpochTravelReporterSubsystem
	: public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void BeginOldEpoch(UWorld* World, UEpochAssetWorldSubsystem* Subsystem,
		AEpochAssetDisplay* Display, const FSoftObjectPath& RecordPath,
		FName ExpectedId, int32 ExpectedValue, bool bInitiallyPending);
	void BeginNewEpoch(UWorld* World, UEpochAssetWorldSubsystem* Subsystem,
		AEpochAssetDisplay* Display, const FSoftObjectPath& RecordPath,
		FName ExpectedId, int32 ExpectedValue, bool bInitiallyPending);
	void FinishProtocol();
	void AbortHarness(const FString& Reason);
	bool IsProtocolActive() const { return bProtocolActive; }

private:
	void HandleWorldCleanup(UWorld* World, bool bSessionEnded,
		bool bCleanupResources);
	void HandlePostWorldCleanup(UWorld* World, bool bSessionEnded,
		bool bCleanupResources);
	void EmitGate(const TCHAR* GateName, bool bPassed) const;

	bool bProtocolActive = false;
	bool bTerminal = false;
	bool bOldBegan = false;
	bool bNewBegan = false;
	bool bOldInitiallyPending = false;
	bool bNewInitiallyPending = false;
	FString RunNonce;
	FString OldWorldPackage;
	FString NewWorldPackage;
	FSoftObjectPath OldRecordPath;
	FSoftObjectPath NewRecordPath;
	FName OldExpectedId = NAME_None;
	FName NewExpectedId = NAME_None;
	int32 OldExpectedValue = 0;
	int32 NewExpectedValue = 0;
	int32 OldCleanupCount = 0;
	int32 OldPostCleanupCount = 0;
	int32 OldApplyCountAtCleanup = INDEX_NONE;
	TWeakObjectPtr<UWorld> OldWorld;
	TWeakObjectPtr<UEpochAssetWorldSubsystem> OldSubsystem;
	TWeakObjectPtr<AEpochAssetDisplay> OldDisplay;
	TWeakObjectPtr<UWorld> NewWorld;
	TWeakObjectPtr<UEpochAssetWorldSubsystem> NewSubsystem;
	TWeakObjectPtr<AEpochAssetDisplay> NewDisplay;
	FDelegateHandle WorldCleanupHandle;
	FDelegateHandle PostWorldCleanupHandle;
};

UCLASS()
class THIRDPERSON_API AOldEpochStartFunctionalTest : public AFunctionalTest
{
	GENERATED_BODY()

public:
	AOldEpochStartFunctionalTest();
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TSoftObjectPtr<UEpochAssetRecord> AssignedRecord;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AEpochAssetDisplay> Display;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ExpectedRecordId = NAME_None;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	int32 ExpectedRecordValue = 0;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName DestinationMap = NAME_None;

private:
	void TravelToDestination();
	FTimerHandle TravelTimer;
};

UCLASS()
class THIRDPERSON_API ANewEpochDestinationFunctionalTest : public AFunctionalTest
{
	GENERATED_BODY()

public:
	ANewEpochDestinationFunctionalTest();
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TSoftObjectPtr<UEpochAssetRecord> AssignedRecord;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	TObjectPtr<AEpochAssetDisplay> Display;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	FName ExpectedRecordId = NAME_None;

	UPROPERTY(EditAnywhere, Category = "CraftBench")
	int32 ExpectedRecordValue = 0;

private:
	void ObserveDestination();
	double StartWorldSeconds = 0.0;
	double CollectionRequestedSeconds = -1.0;
	FTimerHandle ObserveTimer;
};
