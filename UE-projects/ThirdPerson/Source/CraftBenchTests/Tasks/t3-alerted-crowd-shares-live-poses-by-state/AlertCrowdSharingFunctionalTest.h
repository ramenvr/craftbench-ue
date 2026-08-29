// Copyright CraftBench. All Rights Reserved.
// Verifier-only Animation Sharing world-clock fixture.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "AlertCrowdSharingFunctionalTest.generated.h"

class AAlertCrowdSharingHost;
class AAlertCrowdSharingSubject;
class UAnimationSharingSetup;
class UAnimationSharingManager;
class USkeletalMeshComponent;

UCLASS()
class CRAFTBENCHTESTS_API AAlertCrowdSharingFunctionalTest
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AAlertCrowdSharingFunctionalTest(const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, Category = "CraftBench|Expected")
	TObjectPtr<UAnimationSharingSetup> ExpectedSetup;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual bool IsAdmissionProbe() const { return false; }

private:
	void FailHarness(const FString& Detail);
	void FailGate(const TCHAR* Gate, const FString& Detail);
	void ApplyAlertGroup(FName Group);
	bool ValidateSharingState(const TCHAR* Phase, bool bRequireRestore);
	bool ValidateLeaderPose(
		AAlertCrowdSharingSubject* Subject,
		USkeletalMeshComponent* Leader, FString& OutProblem) const;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AAlertCrowdSharingSubject>> Subjects;

	UPROPERTY(Transient)
	TObjectPtr<AAlertCrowdSharingHost> Host;

	UPROPERTY(Transient)
	TObjectPtr<UAnimationSharingManager> Manager;

	TMap<TWeakObjectPtr<USkeletalMeshComponent>, float> LastLeaderTimes;
	TArray<FVector> StartLocations;
	TArray<FVector> LastLocations;
	TArray<FName> ExpectedIdentities;
	TArray<int32> MovingFrames;
	TArray<int32> SampledFrames;
	TWeakObjectPtr<USkeletalMeshComponent> OriginalOrdinaryLeader;
	TWeakObjectPtr<USkeletalMeshComponent> OriginalAlertLeader;
	TWeakObjectPtr<UAnimationSharingManager> PinnedManager;
	FName FirstAlertGroup;
	FName SecondAlertGroup;
	double StartWorldSeconds = 0.0;
	int32 MembershipSeed = 0;
	int32 LeaderTimeAdvances = 0;
	bool bLocalFinishIssued = false;
};

UCLASS()
class CRAFTBENCHTESTS_API AAlertCrowdSharingAdmissionFunctionalTest
	: public AAlertCrowdSharingFunctionalTest
{
	GENERATED_BODY()

protected:
	virtual bool IsAdmissionProbe() const override { return true; }
};
