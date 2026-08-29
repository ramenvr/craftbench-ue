// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-touched-crate-lights-up.
//
// Two crates that look identical and are the same class. What differs is one number
// on each: how close somebody has to be before that crate notices them. They are NOT
// the same number, so a single hard-coded reach is wrong about one of the two
// wherever the character stands between them.
//
// The yard is walked TWICE, and the crates SWAP PLACES between the legs. A submission
// keyed to where a crate stands, rather than to which crate it is, lights the wrong
// one on the second leg.
//
// The stops are computed from the crates' LIVE positions and their OWN radii -- 0.7x
// in, 1.5x out -- so they self-calibrate after the swap and never sit on a boundary
// where a correct answer could round the wrong way.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "CrateHighlightFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class ACrateHighlightFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACrateHighlightFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FCrate
	{
		TWeakObjectPtr<AActor> Actor;
		float Reach = 0.0f;
		/** Where the yard put it for the leg in progress. A submission may not move
		 *  it, and the fixture compares against this rather than trusting it. */
		FVector StagedAt = FVector::ZeroVector;
		/** How many separate spells it has been lit for -- one is not re-arming. */
		int32 Spells = 0;
		bool bWasLit = false;
		/** When the truth about this crate last changed, so the settle is measured
		 *  from the change and not from the frame. */
		double TruthChangedAt = -100.0;
		bool bLastTruth = false;
	};

	bool ResolveStaging();
	bool ReadLit(const AActor* Crate) const;
	/** Every crate's reach, for a failure message that names the spread. */
	FString ReachList() const;
	void StageLeg(int32 LegIndex);
	void BuildRoute();
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FCrate> Crates;

	TArray<FVector> Route;
	int32 Waypoint = 0;
	double DwellUntil = -1.0;
	int32 Leg = 0;
	bool bStaging = false;
};
