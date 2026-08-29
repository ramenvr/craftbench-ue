// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "LatestMarkerResumeFunctionalTest.generated.h"

class ARunResumeCheckpoint;
class ARunResumeReward;
class ARunResumeSubject;
class URunResumePersistenceComponent;

UCLASS(Abstract)
class CRAFTBENCHTESTS_API ALatestMarkerResumeFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ALatestMarkerResumeFunctionalTestBase(
		const FObjectInitializer& ObjectInitializer);
	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex,
		double TimeSeconds) override;
	virtual bool IsResumeLeg() const PURE_VIRTUAL(
		ALatestMarkerResumeFunctionalTestBase::IsResumeLeg, return false;);

private:
	bool ResolveHarness();
	void PassGate(const TCHAR* Gate, const FString& Detail);
	void FailGate(const TCHAR* Gate, const FString& Detail);
	void FailHarness(const FString& Detail);
	void RunWriteCheckpoint(int32 CheckpointIndex);
	void RunResumeCheckpoint(int32 CheckpointIndex);

	TWeakObjectPtr<ARunResumeSubject> Subject;
	TArray<TWeakObjectPtr<ARunResumeCheckpoint>> Checkpoints;
	TArray<TWeakObjectPtr<ARunResumeReward>> Rewards;
	TWeakObjectPtr<URunResumePersistenceComponent> Persistence;
	FString SlotName;
	FString RunNonce;
	double Epoch = 0.0;
	int32 PassedGates = 0;
};

UCLASS()
class CRAFTBENCHTESTS_API ALatestMarkerWriteFunctionalTest
	: public ALatestMarkerResumeFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual bool IsResumeLeg() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API ALatestMarkerResumeFunctionalTest
	: public ALatestMarkerResumeFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual bool IsResumeLeg() const override { return true; }
};
