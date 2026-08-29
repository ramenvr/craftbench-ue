// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-mud-wade.
//
// Speed is judged from MEASURED ground speed -- distance covered per frame -- not from
// MaxWalkSpeed, so a submission that sets the number without the figure actually
// slowing down does not pass. The pose question is answered by asking the mesh which
// animation is driving it, not by asking the submission.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "MudWadeFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AMudWadeFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMudWadeFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	bool ResolveStaging();
	bool OnMud(ACharacter* Who) const;
	/** True when the supplied wade clip is what is driving the pose right now. */
	bool WadeDrivesPose(ACharacter* Who) const;
	double GroundSpeed(ACharacter* Who) const;
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<ACharacter> Twin;
	TWeakObjectPtr<AActor> Patch;

	FVector HeroPrev = FVector::ZeroVector;
	FVector TwinPrev = FVector::ZeroVector;
	bool bHavePrev = false;

	/** Rolling measured speeds, so one hitching frame cannot decide a verdict. */
	double HeroSpeed = 0.0;
	double TwinSpeed = 0.0;

	/** Clean-ground reference, measured on this run rather than assumed. */
	double CleanGroundSpeed = 0.0;
	int32 CleanSamples = 0;

	bool bWasOnMud = false;
	double EnteredMudAt = -1.0;
	double LeftMudAt = -1.0;
	int32 Crossings = 0;
	/** Per crossing: did we ever see the wade driving, and the slowed speed. */
	bool bWadeSeenThisCrossing = false;
	int32 CrossingsWithWade = 0;
	int32 CrossingsSlowed = 0;
	bool bTwinEverWaded = false;
	double TwinSlowestFraction = 1.0;

	/** Waypoints: down the lane, back, and down again. */
	TArray<FVector> Route;
	int32 Waypoint = 0;
	/** When the graded figure last reached a waypoint and reversed. Its speed is
	 *  not judged just after, for the same reason the control's is not. */
	double HeroTurnedAt = -100.0;
	FVector TwinFrom = FVector::ZeroVector;
	FVector TwinTo = FVector::ZeroVector;
	bool bTwinOutbound = true;
	/** When the control last turned around; its speed is not judged just after. */
	double TwinTurnedAt = -100.0;
};
