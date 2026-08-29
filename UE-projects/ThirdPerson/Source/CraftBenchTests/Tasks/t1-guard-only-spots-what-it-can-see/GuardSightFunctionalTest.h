// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-guard-only-spots-what-it-can-see.
//
// The fixture computes its OWN ground truth for each guard every frame -- range, cone
// angle and an occlusion trace from that guard's supplied eye -- and compares it with
// what the guard says about itself. It never asks the submission whether it should be
// lit.
//
// PrepareTest JITTERS both guards before play. The prompt withholds their coordinates,
// and the jitter means even a leaked coordinate is stale: a submission keyed on
// position rather than on what a guard can see fails the every-frame comparison.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GuardSightFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AGuardSightFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGuardSightFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FGuard
	{
		TWeakObjectPtr<AActor> Actor;
		/** Fixture-owned truth, recomputed every frame. */
		bool bShouldSee = false;
		/** When the truth last changed, so the half second is measured from it. */
		double ChangedAt = -100.0;
		/** Whether this guard was EVER correctly lit, and ever wrongly lit. */
		bool bEverCorrectlyLit = false;
		bool bEverSeenTrue = false;
		/** Where PrepareTest left this guard. The prompt forbids moving the guards,
		 *  and the difference between "a submission moved it" and "the yard was
		 *  staged wrong" decides who a control failure belongs to. */
		FTransform Staged;
	};

	bool ResolveStaging();
	FVector EyeOf(AActor* Guard) const;
	float RangeOf(AActor* Guard) const;
	float HalfAngleOf(AActor* Guard) const;
	bool ReadSpotted(AActor* Guard) const;
	/** The fixture's own answer to "can this guard see the character right now". */
	bool ComputeShouldSee(AActor* Guard) const;
	/** The same three steps, spelled out, so a calibration line says WHY a guard
	 *  cannot see rather than only that it cannot. */
	FString Diagnose(AActor* Guard) const;
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Crate;
	TArray<FGuard> Guards;
	/** Index of the guard the staged wall permanently blocks, decided GEOMETRICALLY
	 *  after the jitter -- never by tag, name or index. */
	int32 BlockedIndex = INDEX_NONE;

	TArray<FVector> Route;
	int32 Waypoint = 0;
	/** The run STANDS at each waypoint. Without dwell the whole route was consumed
	 *  in the first second and the character was never anywhere long enough to be
	 *  seen (measured 2026-08-18). */
	double DwellUntil = -1.0;
	int32 SightWindows = 0;
	bool bWasVisibleToAny = false;
};
