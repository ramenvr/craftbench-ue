// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "WalkableGroundAdmissionFunctionalTest.generated.h"

class AAIController;
class AWalkableGroundAdmissionRecastNavMesh;
class ADesignatedScoutCharacter;
class UNavigationSystemV1;

/**
 * Admission-only proof for invoker-bounded dynamic navigation.
 *
 * The fixed world-clock sequence first proves that only the old neighborhood
 * has path data, moves the designated scout to a distant neighborhood, proves
 * that region becomes navigable, drives the scout with a real AI move request,
 * and finally proves the old region retired while a third far control never
 * became navigable. No world/navigation/controller object is manually ticked.
 */
UCLASS()
class CRAFTBENCHTESTS_API AWalkableGroundInvokerAdmissionFunctionalTest
	: public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AWalkableGroundInvokerAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual bool IsAdmissionFixture() const { return true; }

private:
	bool ResolveHarness();
	bool PathExists(const FVector& Start, const FVector& End) const;
	int32 PopulatedTileLayersAt(const FVector& Point) const;
	void LogTelemetry(const TCHAR* Phase, double TimeSeconds) const;
	void PassGate(int32 GateIndex, const TCHAR* GateName, const FString& Detail);
	void FailGate(const TCHAR* GateName, const FString& Detail);
	void FailHarness(const FString& Detail);

	TWeakObjectPtr<ADesignatedScoutCharacter> Scout;
	TWeakObjectPtr<AAIController> ScoutController;
	TWeakObjectPtr<UNavigationSystemV1> NavigationSystem;
	TWeakObjectPtr<AWalkableGroundAdmissionRecastNavMesh> RecastNavMesh;

	FVector MoveStart = FVector::ZeroVector;
	FVector PreviousMoveSample = FVector::ZeroVector;
	FVector OldCenter = FVector::ZeroVector;
	FVector NewCenter = FVector::ZeroVector;
	FVector FarCenter = FVector::ZeroVector;
	FVector SegmentOffset = FVector::ZeroVector;
	float ExpectedGenerationRadius = 0.0f;
	float ExpectedRemovalRadius = 0.0f;
	uint32 PolicyToken = 0;
	double NextFarControlSampleTime = 0.0;
	int32 MovingStatusFrames = 0;
	int32 MoveSampleFrames = 0;
	double MaxMoveFrameStep = 0.0;
	bool bMoveIssued = false;
	bool bFarEverReachable = false;
	bool PassedGates[6] = {false, false, false, false, false, false};
	int32 PassedGateCount = 0;
};

/** Production fixture: same engine evidence, fixed four-gate denominator. */
UCLASS()
class CRAFTBENCHTESTS_API AWalkableGroundFunctionalTest
	: public AWalkableGroundInvokerAdmissionFunctionalTest
{
	GENERATED_BODY()

public:
	AWalkableGroundFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual bool IsAdmissionFixture() const override { return false; }
};
