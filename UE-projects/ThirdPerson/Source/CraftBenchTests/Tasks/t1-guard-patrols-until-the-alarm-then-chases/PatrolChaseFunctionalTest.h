// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-guard-patrols-until-the-alarm-then-chases.
//
// The fixture drives the player character onto and off the alarm plate twice, and
// judges the guard on WHERE IT IS, never on what it says about itself. Two things
// carry the grade: while the alarm is quiet the guard has to stay on its line and
// leave the target alone, and while the alarm rings it has to close on the target and
// face it. A guard that always chases fails the first; a guard that never chases fails
// the second; a guard that chases once fails the second alarm.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "PatrolChaseFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class APatrolChaseFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	APatrolChaseFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** One ringing spell, opened when the alarm starts and closed when it stops. */
	struct FAlarm
	{
		double StartedAt = -1.0;
		double EndedAt = -1.0;
		/** Guard-to-target distance when the alarm began, and the least it reached. */
		double StartGap = 0.0;
		double BestGap = 0.0;
		/** Frames sampled after the settle, and how many of them the guard faced the
		 *  target on. A chase is a position AND a heading, not one of the two. */
		int32 Samples = 0;
		int32 Facing = 0;
	};

	bool ResolveStaging();
	bool HeroOnPlate() const;
	/** Whether the panel is sounding, read off the LAMP a reviewer watches. */
	bool ReadRinging() const;
	double GapToHero() const;
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Guard;
	TWeakObjectPtr<AActor> Panel;
	TWeakObjectPtr<AActor> Decoy;
	TArray<TWeakObjectPtr<AActor>> Posts;

	/** Where the fixture walks the character: the plate, and a spot far enough away
	 *  that a guard on its line has no business being near it. */
	FVector PlateStand = FVector::ZeroVector;
	FVector WaitSpot = FVector::ZeroVector;
	/** The X the two posts share; the line the guard is supposed to keep to. */
	double PatrolLineX = 0.0;
	double StartDecoyGap = 0.0;

	/** The drive: stand at the wait spot, on the plate, off, on, off. */
	TArray<FVector> Route;
	int32 Waypoint = 0;
	double DwellUntil = -1.0;

	TArray<FAlarm> Alarms;
	bool bWasRinging = false;
	double QuietSince = 0.0;
	/** When the panel and the plate first disagreed, so a boundary frame is not a
	 *  verdict. -1 while they agree. */
	double MismatchSince = -1.0;
	/** Which posts the guard has reached, and whether it reached one after the first
	 *  alarm ended -- "goes back to pacing the posts" is a separate claim from
	 *  "paced them at the start". */
	TArray<bool> PostReached;
	bool bReachedAPostBeforeFirstAlarm = false;
	bool bReachedAPostAfterFirstAlarm = false;
};
