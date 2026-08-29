// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADefaultCubeMeshFunctionalTest — L2 verifier fixture for task
// t1-default-cube-mesh-actor. PIE-native (see ACraftBenchFunctionalTest).
//
// The graded property is DEFAULT-ness, observed three ways:
//   (a) pre-BeginPlay — in OnWorldInitializedActors (after
//       PostInitializeComponents, before placed-actor BeginPlay — the t0
//       listener window) the placed 'CubeMeshDisplay' actor must ALREADY carry
//       a static-mesh component showing the engine cube. A mesh acquired at
//       runtime (BeginPlay/tick) is not yet present here and fails.
//   (b) checkpoint 0 (~0.5 s) — a registered, visible static-mesh component on
//       the tagged actor still displays the engine cube.
//   (c) class-default probe — the actor class's default object carries the
//       cube on a static-mesh component, i.e. the cube is part of what the
//       TYPE ships, not per-instance or per-run state.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "DefaultCubeMeshFunctionalTest.generated.h"

struct FActorsInitializedParams;

UCLASS()
class CRAFTBENCHTESTS_API ADefaultCubeMeshFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADefaultCubeMeshFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Probes the tagged actor once, in this world, before placed-actor BeginPlay. */
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);

	UPROPERTY()
	TObjectPtr<AActor> Host = nullptr;
	FDelegateHandle WorldInitHandle;

	/** Result of the pre-BeginPlay probe: did the tagged actor already show the
	 *  engine cube before any BeginPlay ran? */
	bool bPreBeginPlayProbed = false;
	bool bPreBeginPlayCube = false;
	FString PreBeginPlayDetail;
};
