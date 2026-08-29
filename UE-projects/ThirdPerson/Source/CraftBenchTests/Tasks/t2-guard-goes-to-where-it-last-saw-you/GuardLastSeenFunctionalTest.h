// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-guard-goes-to-where-it-last-saw-you.
//
// Two watchmen on two posts, and a night yard with an alcove at each end. The hero is
// driven up a lane that passes inside exactly ONE watchman's sight range -- the other
// is kept blind by RANGE alone, never by a wall, because a wall that blocks its sight
// of the lane also blocks its straight walk to the spot it is radioed. It then outruns
// the watchman (the hero does 500 uu/s, a watchman 300), so sight breaks by range with
// the watchman ~2000 uu behind, and ducks into an alcove that opens AWAY from the lane.
//
// Three properties of that staging are what the gates rest on, and all three were
// measured before the map was authored (notes.md, "the simulation"):
//   * the last-seen spot is ~4400 uu from where the hero was FIRST spotted and ~2000 uu
//     from where the watchman was standing when it lost them, so the three plausible
//     "spots" a first pass stores are far apart and tell each other apart;
//   * the alcove is ~2600 uu from the last-seen spot and opens away from it, so a
//     watchman that searches the spot honestly can never see the hero from there --
//     no re-acquisition, no flapping -- while a watchman that walks at the hero's LIVE
//     position closes to a few hundred uu of it while stone blind;
//   * everything is computed at run time from the LIVE positions of the tagged walls,
//     the two posts and the hero, so a submission cannot write any of it down.
//
// SIGHT IS COMPUTED HERE, not read off the submission. The rule is identical to the
// supplied one (chest to chest, unobstructed, within the watchman's own SightRangeUu),
// so weakening the supplied eyes moves the submission away from the world instead of
// moving the gates with it. Note BaseEngine.ini:3110/:3112 give the "Pawn" and
// "CharacterMesh" collision profiles Visibility=ECR_Ignore, so no character can ever
// block this trace: only the yard's walls and floor occlude. That single fact is what
// the whole staging rests on.
//
// THE SENTINEL. ACraftBenchFunctionalTest ends the test the moment the last scheduled
// checkpoint is crossed, so the schedule runs far past the drive and every tally that
// can only be judged at the end hangs off that last checkpoint. The drive also ends
// itself the moment both legs are complete and every tally is satisfied, so a healthy
// run does not burn the wall clock waiting for the sentinel (the L2 layer's own budget
// is 600 s of WALL time -- tools/verify-single/layers/l2_pie.py:369).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GuardLastSeenFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AGuardLastSeenFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGuardLastSeenFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** One watchman, and everything the gates need to say about it. */
	struct FWatch
	{
		TWeakObjectPtr<ACharacter> Actor;
		FString Name;
		/** Where the yard put it, latched in PrepareTest. The scaffold latches its own
		 *  copy in BeginPlay, which runs EARLIER -- by then the placed capsule has
		 *  already settled onto the floor, so the two are not bit-identical. Both
		 *  comparisons here are 2D and the tolerance is 300 uu, which swallows the
		 *  difference many times over; see the spec's Hidden invariants. */
		FVector Post = FVector::ZeroVector;
		float Pace = 0.0f;
		float Range = 0.0f;

		/** The FIXTURE's own verdict, last frame, and where the hero was then. */
		bool bSaw = false;
		FVector SeenHeroAt = FVector::ZeroVector;
		bool bHasSeenHeroAt = false;
		double BlindSince = -1.0;
		double SightedSince = -1.0;

		/** Per leg. */
		bool bEverSawThisLeg = false;

		/** Progress against the alert in force. */
		double MinDistToSpot = 1.0e9;
		bool bReachedSpot = false;
		double ReachedAt = -1.0;
		double HoldRun = 0.0;          // continuous seconds within HoldRadius of the spot
		double HoldBest = 0.0;
		bool bHoldSatisfied = false;
		double HoldDeadline = -1.0;
		double HomeDeadline = -1.0;
		bool bHomeSatisfied = false;
		double ArriveDeadline = -1.0;

		/** Gate 5 arming. */
		bool bChaseArmed = false;
		double ChaseDeadline = -1.0;
		double ChaseGapAtArm = 0.0;
		double ChaseBest = 1.0e9;
		bool bChaseSatisfied = false;
		bool bEverChaseArmed = false;

		/** Rolling one-second displacement window (gate: only ever walked). */
		TArray<double> TrailT;
		TArray<FVector> TrailP;
	};

	/** The alert in force: one place, the moment it was raised, and who raised it. */
	struct FAlert
	{
		bool bLive = false;
		FVector Spot = FVector::ZeroVector;
		double Time = -1.0;
		int32 Spotter = -1;
		FVector HeroFirstSeenAt = FVector::ZeroVector;
	};

	/** A tagged wall, and where the yard staged it for the leg in progress. */
	struct FWall
	{
		TWeakObjectPtr<AActor> Actor;
		FVector StagedAt = FVector::ZeroVector;
		FBox Bounds = FBox(ForceInit);
	};

	// --- resolution + staging -------------------------------------------------
	bool ResolveYard();
	void MeasureWalls();
	void StageLeg(int32 LegIndex);
	bool CheckStagingPreconditions(FString& OutWhy);

	// --- world reading --------------------------------------------------------
	bool FixtureCanSee(const FWatch& W, const FVector& HeroEye) const;
	bool SegmentHitsAnyWall(const FVector& A, const FVector& B) const;
	double ClearanceToWalls(const FVector& P) const;
	FVector HeroEyePoint() const;

	// --- the drive ------------------------------------------------------------
	void BuildRoute();
	void DriveHero(double Now);

	// --- grading --------------------------------------------------------------
	void OpenAlert(int32 SpotterIdx, const FVector& Spot, double Now);
	bool GradePerFrame(double Now);
	bool GradeFinalTallies(double Now, bool bAtSentinel);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FWatch> Watch;              // exactly 2, sorted by name
	TArray<FWall> Walls;
	FAlert Alert;

	/** Per-run staging, drawn once from the hardware timestamp so two runs of the same
	 *  submission do not see byte-identical geometry. Every draw is re-verified against
	 *  the staging preconditions and shrunk toward zero until they hold. */
	double JitterAlcove[2] = { 0.0, 0.0 };
	double LaneY = 600.0;

	/** Alcove bounding boxes for the leg in progress, index 0 = +Y alcove. */
	FBox AlcoveBox[2] = { FBox(ForceInit), FBox(ForceInit) };

	TArray<FVector> Route;
	TArray<double> RouteDwell;         // < 0 means "hold until the leg's exit condition"
	int32 Waypoint = 0;
	double DwellUntil = -1.0;
	bool bHeroStanding = false;

	int32 Leg = 0;                     // 0 or 1
	bool bLegTwoDone = false;
	bool bStaging = false;
	bool bFirstSightChecked = false;
	bool bLegHadSighting = false;
	bool bDone = false;

	/** Leg 2's hiding place releases the character when both watchmen have stood their
	 *  six seconds, or at this time whatever happened -- so a submission that never
	 *  settles cannot stall the drive and turn a real failure into a hang. */
	double LegTwoReleaseAt = -1.0;

	/** Rolling one-second window for the hero, so a submission that shifts the hero is
	 *  caught without the fixture pretending it can attribute the shove. */
	TArray<double> HeroTrailT;
	TArray<FVector> HeroTrailP;
};
