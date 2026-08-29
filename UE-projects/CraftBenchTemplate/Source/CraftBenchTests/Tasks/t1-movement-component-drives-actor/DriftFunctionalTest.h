// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADriftFunctionalTest — L2 fixture for task t1-movement-component-drives-actor.
// PIE-native. Resolves the host by the "DriftRoot" tag, records its spawn
// location, and samples location at four evenly-spaced checkpoints to assert the
// actor (a) leaves its start, (b) keeps moving to the end, and (c) moves at a
// constant rate (equal displacement per equal interval — not accelerating, not a
// one-shot teleport).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "DriftFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ADriftFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADriftFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	FVector StartLocation = FVector::ZeroVector;
	TArray<FVector> Samples;
};
