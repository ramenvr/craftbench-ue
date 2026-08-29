// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "PCGCommon.h"
#include "FilteredPointInstancesFunctionalTest.generated.h"

class AFilteredPointPCGHost;
class UPCGComponent;

/** Shared implementation for the two orthogonal protected point policies. */
UCLASS(Abstract)
class CRAFTBENCHTESTS_API AFilteredPointInstancesFunctionalTestBase
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AFilteredPointInstancesFunctionalTestBase(
		const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual bool UsesPolicyB() const PURE_VIRTUAL(
		AFilteredPointInstancesFunctionalTestBase::UsesPolicyB, return false;);

private:
	bool ResolveHarness();
	void EvaluateCandidate(double TimeSeconds);
	void PassGate(const TCHAR* GateName, const FString& Detail);
	void FailGate(const TCHAR* GateName, const FString& Detail);
	void FailHarness(const FString& Detail);

	TWeakObjectPtr<AFilteredPointPCGHost> Host;
	TWeakObjectPtr<UPCGComponent> PCGComponent;
	FBox ProtectedBounds = FBox(EForceInit::ForceInit);
	FPCGTaskId GenerationTask = InvalidPCGTaskId;
	double GenerationIssuedAt = 0.0;
	double GenerationCompletedAt = -1.0;
	bool bObservedGenerating = false;
	bool bObservedCompletion = false;
	int32 PassedGateCount = 0;
};
UCLASS()
class CRAFTBENCHTESTS_API AFilteredPointInstancesFunctionalTestA
	: public AFilteredPointInstancesFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual bool UsesPolicyB() const override { return false; }
};

UCLASS()
class CRAFTBENCHTESTS_API AFilteredPointInstancesFunctionalTestB
	: public AFilteredPointInstancesFunctionalTestBase
{
	GENERATED_BODY()

protected:
	virtual bool UsesPolicyB() const override { return true; }
};
