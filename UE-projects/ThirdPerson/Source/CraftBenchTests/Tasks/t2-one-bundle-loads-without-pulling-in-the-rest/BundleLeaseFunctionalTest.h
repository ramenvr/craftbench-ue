// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GameFramework/Actor.h"
#include "UObject/PrimaryAssetId.h"
#include "BundleLeaseFunctionalTest.generated.h"

class ABundleLeaseConsumer;
class ABundleLeaseHost;
struct FBundleRecordPin;

UCLASS()
class CRAFTBENCHTESTS_API ABundleLeaseScenario : public AActor
{
	GENERATED_BODY()

public:
	ABundleLeaseScenario();

	UPROPERTY(EditAnywhere, Category = "Verifier scenario")
	FPrimaryAssetId SelectedPrimaryAssetId;

	UPROPERTY(EditAnywhere, Category = "Verifier scenario")
	FName SelectedBundleName = NAME_None;

	UPROPERTY(EditAnywhere, Category = "Verifier scenario")
	bool bReleaseAFirst = true;
};

UCLASS()
class CRAFTBENCHTESTS_API ABundleLeaseFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ABundleLeaseFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	enum class EPhase : uint8
	{
		AcquireFirst,
		WaitFirst,
		WaitSecond,
		WaitAfterFirstRelease,
		WaitAfterLastRelease,
		StableAfterUnload
	};

	void FailSelected(double TimeSeconds, const FString& Detail);
	void FailUnselected(double TimeSeconds, const FString& Detail);
	void FailFirstRelease(double TimeSeconds, const FString& Detail);
	void FailLastRelease(double TimeSeconds, const FString& Detail);
	bool ValidateProtectedAssets(double TimeSeconds);
	bool ValidateSelectedResident(double TimeSeconds, bool bRequireBothReady);
	bool ValidateUnselectedNonResident(double TimeSeconds);
	bool ValidateManagedBundleState(double TimeSeconds, bool bExpectSelectedBundle);
	void RequestGarbageCollection();

	UPROPERTY()
	TObjectPtr<ABundleLeaseHost> Host = nullptr;

	UPROPERTY()
	TObjectPtr<ABundleLeaseConsumer> ConsumerA = nullptr;

	UPROPERTY()
	TObjectPtr<ABundleLeaseConsumer> ConsumerB = nullptr;

	UPROPERTY()
	TObjectPtr<ABundleLeaseScenario> Scenario = nullptr;

	const FBundleRecordPin* SelectedPin = nullptr;
	EPhase Phase = EPhase::AcquireFirst;
	double PhaseStartedAt = 0.0;
	int32 SentinelCheckpointIndex = INDEX_NONE;
};

/** Admission-only engine control. It validates the protected bundle metadata
 * and Asset Manager load/remove semantics without using the editable runtime.
 * This class is never placed in the production task map. */
UCLASS()
class CRAFTBENCHTESTS_API ABundleLeaseAdmissionFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ABundleLeaseAdmissionFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	void OnAdmissionLoadComplete();
	bool FailAdmission(const FString& Detail);
	FString DescribeAdmissionState() const;

	FPrimaryAssetId SelectedId;
	FName SelectedBundle = NAME_None;
	FSoftObjectPath SelectedPayload;
	FSoftObjectPath SelectedHidden;
	FSoftObjectPath UnselectedPayload;
	FSoftObjectPath UnselectedHidden;
	TSharedPtr<struct FStreamableHandle> AdmissionHandle;
	bool bLoadRequested = false;
	bool bLoadComplete = false;
	bool bRemovalRequested = false;
	int32 LoadCompleteCallbackCount = 0;
	double LoadRequestedAtSeconds = -1.0;
	double LoadCompletedAtSeconds = -1.0;
	double RemovalRequestedAtSeconds = -1.0;
	int32 SentinelCheckpointIndex = INDEX_NONE;
};
