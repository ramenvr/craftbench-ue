// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-turret-leads-you-and-holds-fire.
//
// Two bolted-down turrets, four readable numbers each, RE-TUNED TWICE mid-run. The
// yard walks the character through eight legs and asks two questions about every
// instant: was a shot taken when one could genuinely connect, and was one held when
// no straight shot at that turret's own speed could ever have caught them.
//
// THE FIXTURE TRUSTS NOTHING THE SUBMISSION STAMPS. Everything the agent could
// rewrite -- the turret class, the trigger, the aiming control, the tracer's own
// "read-only" provenance fields -- lives in Source/ThirdPerson/, which is the agent's
// writable tree. So a shot's identity, launch point, direction and speed are all
// re-derived HERE, from the fixture's own per-frame samples of the world:
//   * which turret fired it       -> the muzzle it appeared at (<= 150 uu)
//   * where it left from          -> the fixture's sample of that muzzle
//   * which way it left           -> the shot's own motion over its first 0.2 s
//   * how fast it flies           -> the fixture's read of that turret's LIVE
//                                    ShotSpeedUu at the instant it appeared
// Everything the supplied code claims to enforce is re-derived as a gate; anything
// that could not be re-derived was dropped from the claim rather than left implied.
//
// EVERY STOP IS DERIVED from the parameter sets the yard stages, never written down,
// so the route re-shapes itself around each re-tune and no stop ever lands within 8%
// of a reach boundary where a correct answer could round the wrong way.
//
// PrepareTest DRY-RUNS the whole route before a single frame is graded and refuses to
// start if any fairness invariant fails: a stop or a leg too near a solid turret base,
// a demanded firing window too short for the owning turret to swing and reload inside,
// an intercept bearing rate the barrel physically could not follow, or two turrets
// whose numbers are close enough that one constant would fit both.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "TurretLeadFunctionalTest.generated.h"

class ACharacter;
class USceneComponent;

UCLASS()
class ATurretLeadFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ATurretLeadFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FTurret
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<USceneComponent> Barrel;
		TWeakObjectPtr<USceneComponent> Muzzle;
		TWeakObjectPtr<USceneComponent> BasePart;

		/** Where and how the yard bolted it down. Nothing may change either. */
		FVector StagedLoc = FVector::ZeroVector;
		FQuat StagedRot = FQuat::Identity;
		FQuat StagedBaseRot = FQuat::Identity;

		/** The barrel PIVOT's world location. It turns; it does not travel. Every
		 *  solve the fixture does for itself starts here rather than at the live
		 *  muzzle, because the muzzle swings 230 uu with the barrel and the barrel
		 *  belongs to the submission -- a window definition that moved with it would
		 *  be a window definition the submission could shift. */
		FVector StagedBarrelLoc = FVector::ZeroVector;

		/** Re-read from the actor every frame -- never cached across a re-tune. */
		double Speed = 0.0;
		double Reach = 0.0;
		double Traverse = 0.0;
		double Reload = 0.0;

		/** Servo watch: the barrel's orientation on the previous graded frame. */
		FQuat LastBarrel = FQuat::Identity;
		bool bHaveLastBarrel = false;

		/** Trigger watch. MinReloadSince is the SMALLEST reload this turret has
		 *  advertised since its last shot, so a re-tune can only ever forgive. */
		double LastShotAt = -1.0e6;
		double MinReloadSince = 1.0e6;

		/** The firing window in progress, if any. */
		bool bWindowOpen = false;
		double WindowStart = 0.0;
		int32 WindowShots = 0;

		int32 TotalShots = 0;
		int32 GradeableShots = 0;
	};

	struct FShot
	{
		TWeakObjectPtr<AActor> Actor;
		int32 Turret = 0;
		double T0 = 0.0;
		FVector P0 = FVector::ZeroVector;
		/** The fixture's own read of the firing turret's live ShotSpeedUu at T0. */
		double Speed = 0.0;
		/** The fixture's own sample of that turret's barrel forward at T0. */
		FVector BarrelFwd0 = FVector::ForwardVector;

		FVector Dir = FVector::ZeroVector;
		bool bHaveDir = false;
		FVector LastPos = FVector::ZeroVector;

		double MinDistUu = 1.0e9;
		bool bGradeable = false;
		double SolveT = 0.0;
		bool bJudged = false;
		/** Fired within half a second of a re-tune: the fixture cannot say which of
		 *  the two shot speeds was live when it left, so it is neither speed-checked
		 *  nor accuracy-graded. Can only ever forgive. */
		bool bSpeedAmbiguous = false;
	};

	// --- staging -----------------------------------------------------------------
	bool ResolveStaging();
	void ApplyPhase(int32 PhaseIndex);
	bool WriteNumber(AActor* A, const TCHAR* PropName, double Value);
	bool ReadNumber(const AActor* A, const TCHAR* PropName, double& Out) const;
	bool RefreshLiveNumbers();
	void BuildRoute();
	bool ValidatePlan();

	// --- geometry ----------------------------------------------------------------
	static bool SolveIntercept(const FVector& D, const FVector& V, double ShotSpeed,
		double& OutFlightSeconds);
	/** Splits V into the part across the line of sight and the part along it
	 *  (positive = opening). Both sides of every comparison come from here. */
	static void SightSplit(const FVector& D, const FVector& V, double& OutAcross,
		double& OutAlong);
	/** The yard's own answer for turret T at this instant, from the LIVE numbers. */
	static bool WindowOpenFor(const FTurret& T, const FVector& HeroAt,
		const FVector& HeroVel, double& OutFlight);
	static bool OutOfReachFor(const FTurret& T, const FVector& HeroAt);
	static bool NoSolutionFor(const FTurret& T, const FVector& HeroAt,
		const FVector& HeroVel);
	static int32 ShotsRequired(double WindowSeconds, double Traverse, double Reload);

	// --- per-frame ---------------------------------------------------------------
	void DriveHero(double Now);
	bool CheckIntegrity(double Dt);
	bool TrackShots(double Now, const FVector& HeroPrev, const FVector& HeroAt);
	bool CloseWindow(FTurret& T, int32 Index, double Now);
	bool HeroIsSteady(double Now) const;
	void LogCalib(int32 Index, double Now) const;
	bool FinishTotals(double Now);

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FTurret> Turrets;
	TArray<FShot> Shots;

	/** Waypoints, the leg speed used to REACH each one, and the phase in force while
	 *  walking to it. Built by BuildRoute from the staged parameter sets. */
	TArray<FVector> Route;
	TArray<double> LegSpeed;
	int32 Waypoint = 0;
	double DwellStart = -1.0;
	bool bDwelling = false;

	int32 Phase = 0;
	int32 RetunesDone = 0;
	double LastRetuneAt = -1.0e6;

	double StagedTopSpeed = 0.0;
	double RouteDoneAt = -1.0;
	bool bTotalsDone = false;

	/** Rolling velocity history, for "has been walking a straight line for 1.0 s". */
	TArray<double> HistT;
	TArray<FVector> HistV;

	FVector HeroPrevAt = FVector::ZeroVector;
	bool bHaveHeroPrev = false;
	int32 FramesGraded = 0;
};
