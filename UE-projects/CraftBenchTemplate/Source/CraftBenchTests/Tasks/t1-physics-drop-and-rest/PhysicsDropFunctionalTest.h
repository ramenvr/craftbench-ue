// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// APhysicsDropFunctionalTest — L2 fixture for task t1-physics-drop-and-rest.
// PIE-native. Resolves the host by the "PhysicsDropRoot" tag and samples its Z
// across a checkpoint schedule while the PIE engine simulates physics at a fixed
// timestep:
//   checkpoint 0 (~0.2s): record start Z + assert the root's collision responses
//                         (Pawn = Ignore, WorldStatic = Block);
//   checkpoint 1 (~1.5s): assert Z has descended well below the start (it fell);
//   checkpoint 2 (~3.0s): record resting Z;
//   checkpoint 3 (~3.5s): assert Z is unchanged since cp2 (came to rest) and is
//                         above the floor (did not fall through).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "PhysicsDropFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API APhysicsDropFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	APhysicsDropFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	double StartZ = 0.0;
	double RestZ = 0.0;
};
