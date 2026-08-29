// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AProfiledMoverFunctionalTest — L2 fixture for task t1-data-asset-drives-speed.
// PIE-native. Resolves the host by the "ProfiledMoverRoot" tag and samples its
// location across checkpoints, asserting it moves at the profile's configured
// CruiseSpeed (measured as displacement rate; the authored speed is NOT
// disclosed to the agent).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "ProfiledMoverFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AProfiledMoverFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AProfiledMoverFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	FVector StartLocation = FVector::ZeroVector;
	TArray<FVector> Samples;
};
