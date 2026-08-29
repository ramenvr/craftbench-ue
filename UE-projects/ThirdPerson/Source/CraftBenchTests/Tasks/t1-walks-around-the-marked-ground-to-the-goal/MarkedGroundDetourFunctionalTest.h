// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-walks-around-the-marked-ground-to-the-goal.
//
// The yard is walked TWICE, and the patch that is out of bounds SWAPS between the
// two trips. That is the whole anti-hard-coding design: a submission that decided
// once which patch to avoid passes the first trip and fails the second, with its own
// named message.
//
// The fixture works out for itself whether the walker is standing on painted ground,
// from the patches' component bounds. It does NOT call the patch's own CoversPoint --
// that class lives in the agent-writable module, and an assertion that asks the
// submission whether the submission is correct is not an assertion.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "MarkedGroundDetourFunctionalTest.generated.h"

UCLASS()
class AMarkedGroundDetourFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMarkedGroundDetourFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FPatch
	{
		TWeakObjectPtr<AActor> Actor;
		/** The painted strokes, in world space, as the fixture measured them at
		 *  PrepareTest -- before any submission code could move them. */
		TArray<FBox> Strokes;
		/** Whether a straight line across this patch was CLEAR before play. Paint
		 *  does not block; a submission that turns it into a wall changes this. */
		bool bLaneWasClear = false;
		FVector LaneFrom = FVector::ZeroVector;
		FVector LaneTo = FVector::ZeroVector;
	};

	struct FTrip
	{
		int32 OutOfBoundsIndex = INDEX_NONE;
		double Travelled = 0.0;
		bool bSteppedOnAllowed = false;
		bool bArrived = false;
		double StartedAt = 0.0;
		double ArrivedAt = -1.0;
	};

	bool ResolveStaging();
	bool CoversPoint(const FPatch& Patch, const FVector& P) const;
	bool LaneIsClear(const FPatch& Patch) const;
	bool ReadOutOfBounds(const AActor* Patch) const;
	void ApplyTripStaging(int32 TripIndex);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<AActor> Walker;
	TWeakObjectPtr<AActor> StartMark;
	TWeakObjectPtr<AActor> GoalMark;
	TArray<FPatch> Patches;

	/** Where the walker is put back between trips. Its HEIGHT is the walker's own
	 *  standing height, never the start marker's -- the marker is a disc lying on
	 *  the floor, and putting a capsule-rooted actor at that height buries half of
	 *  it and every swept move it makes is refused at zero distance. */
	FVector StartAt = FVector::ZeroVector;
	FVector GoalAt = FVector::ZeroVector;
	double StraightLine = 0.0;

	TArray<FTrip> Trips;
	int32 Trip = 0;
	FVector LastWalkerAt = FVector::ZeroVector;
	/** Set while the fixture is repositioning the walker between trips, so the
	 *  teleport is not charged to the submission's distance budget. */
	bool bStaging = false;
};
