// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-shoved-block-slides-on-one-rail.
//
// Derives ACraftBenchFunctionalTest, NOT ACraftBenchPawnFunctionalTest: the
// graded subject and the control are both PLACED blocks, and the single pawn is
// spawned and possessed by the map's game mode, then resolved by tag. Nothing in
// either base class is touched and no fixture-local pawn spawner is duplicated.
//
// All measurements are in the RAIL FRAME: s along the authored rail direction,
// d signed perpendicular horizontal distance from the rail line, z height.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "ShovedBlockRailFunctionalTest.generated.h"

class ACharacter;
class UPrimitiveComponent;

/** One block's identity plus everything measured about it across a shove. */
USTRUCT()
struct FRailBlockProbe
{
	GENERATED_BODY()

	TWeakObjectPtr<AActor> Actor;
	TWeakObjectPtr<UPrimitiveComponent> Body;
	FVector StartLocation = FVector::ZeroVector;
	FQuat StartRotation = FQuat::Identity;

	/** Window maxima since the last window reset. */
	double MaxOffLine = 0.0;
	double MaxOffHeight = 0.0;
	double MaxTurnDeg = 0.0;
	double MaxSpeed = 0.0;

	/** Worst per-frame gap between how far the block ACTUALLY moved and how far its
	 *  own rigid-body velocity says it should have. A body the world's physics moves
	 *  keeps this near zero; a body written along a path does not. */
	double MaxUnexplained = 0.0;
	FVector PrevLocation = FVector::ZeroVector;
	bool bHasPrev = false;
};

UCLASS()
class AShovedBlockRailFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AShovedBlockRailFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Phase of the drive + grading state machine. */
	enum class EPhase : uint8
	{
		Settling,      // before cp0
		DrivingIn,     // walking into the plunger, waiting for shove 1
		AwaitCp1,      // shove 1 seen, waiting out the settle window
		DrivingOut,    // backing away so the plunger re-arms
		DrivingInAgain,// walking back in, waiting for shove 2
		AwaitCp2,      // shove 2 seen, waiting out the settle window
		AwaitCp3,      // knocked, waiting out the tether window
		Done
	};

	bool ResolveOne(const TCHAR* Tag, TWeakObjectPtr<AActor>& Out);
	bool InitProbe(FRailBlockProbe& Probe, AActor* Actor, const TCHAR* Which);
	void ResetWindow(FRailBlockProbe& Probe);
	void AccumulateWindow(FRailBlockProbe& Probe, float DeltaSeconds);

	/** Rail-frame readings. */
	double AlongRail(const FVector& P) const;
	double OffRail(const FVector& P) const;
	double TurnDegrees(const FRailBlockProbe& Probe) const;
	double Speed(const FRailBlockProbe& Probe) const;

	void DriveToward(const FVector& Target, float DeltaSeconds);
	void LogCalib(int32 Index, double Now) const;
	bool RailMarkerStillPlaced();

	void GradeCp0(double Now);
	void GradeCp1(double Now);
	void GradeCp2(double Now);
	void GradeCp3(double Now);

	FRailBlockProbe Rail;
	FRailBlockProbe Twin;
	TWeakObjectPtr<AActor> Plunger;
	TWeakObjectPtr<AActor> RailMarker;
	TWeakObjectPtr<ACharacter> Hero;

	/** The authored rail frame, asserted against the placed marker every cp. */
	FVector RailForward = FVector::ForwardVector;
	FVector RailRight = FVector::RightVector;
	FVector RailPoint = FVector::ZeroVector;

	EPhase Phase = EPhase::Settling;
	bool bCheckpointDue[4] = {false, false, false, false};
	/** Index 4 in the schedule is a sentinel, not a graded instant. */

	double Shove1Time = -1.0;
	double Shove2Time = -1.0;
	double KnockTime = -1.0;
	bool bTwinSettledAfterShove1 = false;

	/** s of the railed block at cp0 and at cp1, for the per-shove advance. */
	double RailSAtCp0 = 0.0;
	double RailSAtCp1 = 0.0;
	/** |d| of each block immediately before the knock. */
	double RailPreKnockOffLine = 0.0;
	double TwinPreKnockOffLine = 0.0;
};
