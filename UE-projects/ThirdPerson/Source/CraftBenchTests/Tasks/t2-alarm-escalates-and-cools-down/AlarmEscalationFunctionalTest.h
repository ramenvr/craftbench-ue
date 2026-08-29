// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-alarm-escalates-and-cools-down.
//
// A yard with three settings whose RAISE numbers and DROP numbers are deliberately
// different, so the same sighting count means one thing on the way up and another on
// the way down. The fixture runs its own copy of the whole rule -- the same predicate,
// the same dials, the same live guard transforms -- and grades the yard against it.
//
// THE COUNT IS THE HARD PART, and the whole shape of this fixture follows from one
// fact: the fixture's integer sighting count and the submission's have to agree over
// several hundred seconds with no re-sync, and one divergent edge would fail correct
// work on everything downstream. Three things make that safe:
//
//   1. THE PREDICATE IS DISCLOSED IN FULL (prompt): flat, from the guard's own
//      location to the character's, against the guard's own two numbers, inclusive at
//      both edges. There is no measurement origin to guess.
//   2. THE COUNT SATURATES AT BOTH ENDS, and every phase of the drive ends at one of
//      them -- at the panel's cap, or at zero. Saturation is a RE-SYNC: two counters
//      that both clamp arrive at the same integer no matter what happened before.
//      So a divergence can never outlive the phase it started in.
//   3. EVERY TRANSIT IS ROUTED OUT THROUGH THE QUIET SPOT, never spot-to-spot, and
//      PrepareTest refuses to start unless every boundary the route crosses is crossed
//      transversely (measured, not assumed) and every dwell spot clears its guard's
//      cone by a real margin at every phase of that guard's round.
//
// Assertions are additionally suppressed for 0.75 s after any change in the fixture's
// own model (twice the half-second the prompt discloses), while the model is within
// 0.4 s of its next forget tick, and whenever any guard's verdict is inside a marginal
// band -- so a one-frame difference in tick order between the submission's logic and
// the guards' own movement can never be scored as a failure.
//
// THE FLOODLIGHTS FEED BACK INTO PERCEPTION: a burning floodlight lengthens the reach
// of a guard walking the round it covers. So the lamp loop is an INPUT to the sighting
// count, not just a readout of it, and a bug in one really does break the other.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "AlarmEscalationFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AAlarmEscalationFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AAlarmEscalationFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ---------------------------------------------------------------- the yard

	struct FGuard
	{
		TWeakObjectPtr<AActor> Actor;
		/** Re-read EVERY frame: both guards trade rounds mid-run. */
		float Reach = 0.0f;
		float HalfAngleDeg = 0.0f;
		float BaseSpeed = 0.0f;
		FName RoundTag = NAME_None;
		/** What the yard staged for the leg in progress, so a submission that edits a
		 *  guard is caught by comparison rather than by trust. */
		float StagedReach = 0.0f;
		float StagedHalfAngleDeg = 0.0f;
		float StagedBaseSpeed = 0.0f;
		FName StagedRoundTag = NAME_None;
		/** The round it is meant to be walking, re-derived per leg from the posts. */
		FVector RoundA = FVector::ZeroVector;
		FVector RoundB = FVector::ZeroVector;
	};

	struct FLamp
	{
		TWeakObjectPtr<AActor> Actor;
		int32 LitFromStage = 0;
		float ReachBonusUu = 0.0f;
		FName CoversRoundTag = NAME_None;
		int32 StagedLitFromStage = 0;
		float StagedReachBonusUu = 0.0f;
		FName StagedCoversRoundTag = NAME_None;
		FString Label;
	};

	struct FDials
	{
		int32 RaiseWatch = 0;
		int32 RaiseHunt = 0;
		int32 DropWatch = 0;
		int32 DropCalm = 0;
		int32 Cap = 0;
		double QuietStep = 0.0;
		double ScaleCalm = 0.0;
		double ScaleWatching = 0.0;
		double ScaleHunting = 0.0;
	};

	// -------------------------------------------------------------- resolution

	bool ResolveStaging();
	bool ReadDials(FDials& Out) const;
	void ReReadGuardNumbers();
	bool ReadLit(const AActor* Lamp) const;
	float ReadFloat(const AActor* A, const TCHAR* Name, bool& bOk) const;
	int32 ReadInt(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FName ReadName(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool WriteFloat(AActor* A, const TCHAR* Name, float Value) const;
	bool WriteInt(AActor* A, const TCHAR* Name, int32 Value) const;
	bool WriteName(AActor* A, const TCHAR* Name, FName Value) const;

	// ------------------------------------------------------------- the oracle

	/** The reach a guard has at a given SETTING: its own number plus every floodlight
	 *  that would be burning at that setting and covers the round it is on. */
	double ReachAtStage(const FGuard& G, int32 InStage) const;

	/** Flat, guard location to point, inclusive at both edges. OutAngleDeg/OutDist are
	 *  filled for the marginal-band test and the failure messages. */
	bool CanSee(const FGuard& G, const FVector& Point, int32 InStage,
		double& OutAngleDeg, double& OutDist, double& OutReach) const;

	/** True when any guard's verdict this frame is close enough to a boundary that a
	 *  one-frame difference in sampling order could flip it. */
	bool AnyVerdictMarginal(const FVector& Point) const;

	/** Advances the fixture's model one frame. */
	void StepModel(double Dt);

	/** The scale the panel CURRENTLY reads for a setting. */
	double ScaleFor(int32 InStage) const;

	// -------------------------------------------------------------- the gates

	/** True on a frame no gate may judge: the fixture is re-staging, the model has
	 *  just changed, its next forget tick is imminent, or some guard's verdict is
	 *  close enough to a boundary that a frame of sampling order could flip it. */
	bool Suppressed(double Now) const;
	/** Is the yard SHOWING the setting the model says it should be? Reads the lights,
	 *  never a flag. */
	bool ShownStageMatches(int32 Expect) const;

	bool GateNotRewired(double Now);
	bool GateOwnEyes(double Now);
	bool GateHysteresis(double Now);
	bool GateStepDown(double Now);
	bool GateCap(double Now);
	bool GateStageShown(double Now);
	bool GateSpeeds(double Now);
	/** The set of lamps that must be burning at the model's setting, as a string. */
	FString LitSetDescription(int32 InStage) const;
	FString ActualLitDescription() const;

	// -------------------------------------------------------------- the drive

	void StageLeg(int32 LegIndex);
	bool BuildSpots();
	bool ValidateGeometry();
	bool ValidateSightlines();
	void BeginPhase(int32 NewPhase, double Now);
	void AdvancePhases(double Now);
	/** One full there-and-back of a guard's round at a given setting. */
	double LapSecondsFor(const FGuard& G, int32 InStage) const;
	/** How long a guard leaves the character UNSEEN between two consecutive sightings
	 *  at a dwell spot: the lap, less the one sighting window that lap affords, over
	 *  the pace that setting dictates. Measured at the offset the drive PARKS at
	 *  (kWaypointUu further off the round than it aims for), because that is the
	 *  quiet the panel's forget clock actually gets to run for. Compared against
	 *  Dials.QuietStep -- if the quiet is the longer of the two, the panel forgets
	 *  each sighting before the next one lands and the count can never climb. */
	double QuietBetweenSightings(const FGuard& G, double Offset, double AlongPos,
		int32 InStage) const;
	/** The guard currently walking the round the drive is built around. */
	const FGuard* CoveringGuard() const;
	/** The other one. */
	const FGuard* FarGuard() const;
	/** Reach on a NAMED round at a NAMED setting - needed for the guard that is not
	 *  on that round yet. */
	double ReachOnRound(const FGuard& G, int32 InStage, FName Tag) const;
	void DriveHero(double Now);
	void LogCalib(int32 Index, double Now) const;

	// ------------------------------------------------------------------ state

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FGuard> Guards;
	TArray<FLamp> Lamps;
	TWeakObjectPtr<AActor> Alarm;
	FDials Dials;

	/** The watched round -- the one the drive is built around, and the one the two
	 *  guards trade at the watch change. Derived from the posts, never written down. */
	FName WatchedRoundTag = NAME_None;
	FName FarRoundTag = NAME_None;
	FVector RoundCentre = FVector::ZeroVector;
	FVector RoundU = FVector::ZeroVector;   // along the round
	FVector RoundV = FVector::ZeroVector;   // perpendicular, AWAY from the far round
	double RoundHalfLen = 0.0;
	double WalkZ = 0.0;

	/** Every post in the yard, with where the yard put it. */
	TArray<TWeakObjectPtr<AActor>> Posts;
	TArray<FVector> StagedPostAt;

	/** The dials as the yard staged them for the leg in progress. */
	FDials StagedDials;

	/** The three places the drive stands, plus the lane it travels on. All derived
	 *  from the round and the guards' own numbers -- never written down. */
	FVector SpotQuiet = FVector::ZeroVector;
	FVector SpotSeen = FVector::ZeroVector;    // seen by BOTH guards
	FVector SpotSplit = FVector::ZeroVector;   // seen by ONE of them only
	FVector LaneOverSeen = FVector::ZeroVector;
	double OffsetSeen = 0.0;
	double OffsetSplit = 0.0;
	double AlongSeen = 0.0;
	double AlongSplit = 0.0;

	/** The model. */
	int32 Stage = 0;
	int32 Sightings = 0;
	int32 RawSightings = 0;
	bool bSeenLastFrame = false;
	double QuietFor = 0.0;
	double LastModelChangeAt = -100.0;
	int32 StageForReach = 0;   // the setting the yard was showing when the frame began
	/** Which way the count last moved -- the whole point of the deadband. */
	bool bCountRising = false;
	/** Raw sightings when the phase in progress began, for the over-exposure. */
	int32 RawAtPhaseStart = 0;
	/** How many raw sightings the deliberate over-exposure actually delivered. */
	int32 RawInOverexposure = 0;

	/** Bookkeeping for the run-level gate. */
	int32 RisesInLeg[2] = {0, 0};
	bool bReachedCalmAfterFirstRise = false;

	/** Did the fixture's own model ever stand STRICTLY inside each deadband -- above a
	 *  drop number and below its raise number? That is the ONLY place a remembered
	 *  setting and a plain threshold ladder are allowed to disagree, so it is the only
	 *  place TheYardRemembersWhichWayItCame can arm. A run in which neither band was
	 *  ever occupied graded nothing at all about hysteresis, and reporting it as a
	 *  pass would say the task measured something it did not. Set from the model's own
	 *  count, so it records what the DRIVE produced and cannot be influenced by the
	 *  submission. */
	bool bWasInWatchBand = false;
	bool bWasInHuntBand = false;

	int32 Leg = 0;
	int32 Phase = 0;
	double PhaseStartedAt = 0.0;
	double PhaseDeadline = 0.0;
	double HoldSince = -1.0;
	double HeroSpeed = 500.0;
	bool bPrepared = false;
	bool bDriveComplete = false;

	/** The waypoints of the WALK in progress; empty during a STAND. */
	TArray<FVector> Waypoints;
	int32 WaypointIndex = 0;

	/** Every gate is off while the fixture itself is re-staging the yard. */
	double StagingUntil = -1.0;
};
