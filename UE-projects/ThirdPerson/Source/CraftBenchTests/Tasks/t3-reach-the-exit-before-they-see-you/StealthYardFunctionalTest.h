// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-reach-the-exit-before-they-see-you.
//
// A walled night yard: three watchers pacing three straight rounds behind painted
// sight arcs, a rail truck grinding back and forth, a plate at the start line, a gate
// at the far end and a mast carrying three lights -- running, away, caught -- of which
// exactly one must burn. The fixture drives the runner with the shipping per-frame
// AddMovementInput timeline and grades what a reviewer can SEE: three mast light
// intensities, three head-lamp intensities and three PaceUuPerSec floats.
//
// THE FIXTURE RUNS THE SAME RULE. Every frame it re-reads, BY NAME and LIVE, each
// watcher's SightReachUu / SightHalfAngleDeg / BasePaceUuPerSec / RoundTag and live
// transform, the truck's TruckHalfExtentUu / RailHalfSpanUu / RailSpeedUuPerSec and
// live transform, every blocker's BlockHalfExtentUu and transform, and the plate's
// RoundIndex; and steps its own model of the whole rule. Every gate compares the
// yard's VISIBLE state against that model. Nothing private is ever read.
//
// TWO INDEPENDENT IMPLEMENTATIONS OF ONE DISCLOSED RULE. The model's clear-line test
// is a 2-D segment-versus-rectangle test against the live footprints; a submission
// will almost certainly trace. That is deliberate -- a fixture that traced would grade
// "did you call the function I called". The staging contract's four-height occlusion
// probe is what guarantees the two cannot disagree; if that probe is ever dropped this
// gate degrades into a coin toss on trace height.
//
// WHY THE DRIVE IS GOVERNED. Standing where a watcher will sweep is how this yard ends
// a round, so an UNGOVERNED transit ends rounds by accident and manufactures failures
// that say nothing about the submission. Every walk taken WHILE A ROUND IS STILL
// RUNNING is therefore released only once the fixture's own model has SIMULATED every
// watcher forward over the TRANSIT ITSELF and proved that no point of the leg can be
// seen before the runner gets there (EarliestSightingOnPath). Two properties of that
// rule are load-bearing and both were got wrong once:
//
//   * the horizon is the TRANSIT, never a fixed 3-40 s. Half the places this drive
//     stands -- the shadow spot, and the split spot on the second watch -- are places
//     a cone WILL sweep; that is what they are for. A governor demanding safety for
//     seconds AFTER arrival could never release the walk to them at all, and the drive
//     would stall on the first phase that mattered.
//   * once a round has ENDED there is nothing left to protect, so the governor is
//     skipped entirely. Otherwise no walk could ever leave a place the runner was
//     caught standing in, and the drive would stall on the very frame it was supposed
//     to start proving that caught is final.
//
// THE SHADOW ENTRY IS PHASE-ALIGNED. Walking into the one place the truck hides is not
// safe at an arbitrary moment: the covering watcher's cone and the truck's rail are two
// independent periodic things, and arriving when the cone holds the spot while the
// truck is elsewhere ends round 1 on the spot -- a staging coin toss, not a
// measurement. The fixture therefore waits, on a lane rest point nobody can see, until
// its own forward simulation says that leaving NOW arrives inside a stretch where the
// cone holds the spot AND the truck lies across the line, that the stretch lasts at
// least kMinTruckCoverS, and that the truck then LETS GO of the line while the cone
// still holds it -- which is the event phase 3 grades.
//
// PRECEDENCE, in the order Tick evaluates. One gate unsuppressed every frame, then --
// inside the settle window the prompt promises -- the board-shape gate, EXACTLY ONE
// windowed board gate, then EXACTLY ONE independent-channel gate, always last and only
// once the board has already been agreed:
//
//    1  TheYardIsNotYoursToRewire            every frame, from the first, unsuppressed
//    2  ExactlyOneLampBurnsOnTheBoard        every JUDGED frame -- i.e. inside the same
//                                            settle window as everything else, so a
//                                            board caught mid-transition across two
//                                            frames is forgiven exactly as the prompt
//                                            says it is
//    -- exactly one BOARD gate, narrowest window first --
//    3  SeenTheMomentTheyCross               phase 12's staged mid-leg crossing
//    4  TheTruckMakesAShadowWhileItPasses    phases 2-3
//    5  EachWatcherSeesWithItsOwnEyes        phases 7 and 12 (the split spot, twice)
//    6  CaughtIsFinalEvenAtTheGate           phases 4-5 and 13-14
//    7  AwayIsFinalEvenInPlainSight          phases 9 and 17
//    8  EveryRoundStartsCleanWhenThePlateClicks   every other judged frame of a
//                                            running round
//    -- then exactly one INDEPENDENT CHANNEL gate, always LAST --
//    9  EachWatcherShowsWhatItCanSeeRightNow while a round is running
//   10  TheYardStandsDownWhenTheRoundIsOver  while a round is over
//    -- run level --
//   11  BothEndingsHappenedTwice             at drive completion and at the sentinel
//
// Gates 9 and 10 are mutually exclusive by definition, so exactly one runs on every
// judged frame, and neither is suppressed inside a board gate's window -- suppressing
// them would leave the head lamps and the paces ungraded on exactly the frames that
// matter most.
//
// WHERE THE LIT HALF OF THE LAMP CHANNEL LIVES, and why it is not in gate 9. Seeing the
// runner is what ENDS a round, so on every frame gate 9 can possibly run the model's
// visible set is necessarily EMPTY. Gate 9's teeth are therefore "no lamp burns that
// should not", which is exactly where a range-only or occlusion-blind sight test dies:
// the whole of the truck window, and the walled sentry on every judged frame of the
// run. The LIT half is owned by gate 10. When a round ends caught, the lamps of the
// watchers that could see the runner AT THAT INSTANT stay burning until the next plate
// click, and gate 10 requires the burning set to equal that latched set exactly. A
// submission that RE-DERIVES "who can see the runner" during the stand-down reports {}
// the moment the runner walks away and fails by name -- the one place in this task
// where the outcome has to be remembered rather than recomputed. The IN-SCENE NEGATIVE
// CONTROL spans both: the walled sentry has the largest reach and the widest view width
// in the yard and its round is behind a solid wall that crosses every line from it to
// every point of the route, so it is never in the model's visible set and never in the
// latched set. Its lamp is additionally gauged at EVERY checkpoint, suppression or
// none, because it can never be marginal about anything.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "StealthYardFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AStealthYardFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AStealthYardFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------ the yard

	/** A flat, axis-aligned footprint: everything solid in this yard is an unrotated
	 *  box standing from the floor to well above head height, so what blocks a line is
	 *  a rectangle on the floor and nothing else. */
	struct FFootprint
	{
		FVector2D Centre = FVector2D::ZeroVector;
		FVector2D Half = FVector2D::ZeroVector;
		FString Label;
	};

	struct FWatcher
	{
		TWeakObjectPtr<AActor> Actor;
		FString Label;
		/** Re-read EVERY frame: two of them trade rounds and three numbers change. */
		float Reach = 0.0f;
		float HalfAngleDeg = 0.0f;
		float BasePace = 0.0f;
		float Pace = 0.0f;
		FName RoundTag = NAME_None;
		/** What the yard staged for the watch in progress, so a submission that edits
		 *  a watcher is caught by comparison rather than by trust. */
		float StagedReach = 0.0f;
		float StagedHalfAngleDeg = 0.0f;
		float StagedBasePace = 0.0f;
		FName StagedRoundTag = NAME_None;
		/** The round it is meant to be walking, re-derived per staging. */
		FVector RoundA = FVector::ZeroVector;
		FVector RoundB = FVector::ZeroVector;
	};

	struct FRound
	{
		FName Tag = NAME_None;
		FVector A = FVector::ZeroVector;   // the -X end
		FVector B = FVector::ZeroVector;   // the +X end
	};

	// -------------------------------------------------------------- reflection

	float ReadFloat(const AActor* A, const TCHAR* Name, bool& bOk) const;
	int32 ReadInt(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FName ReadName(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FVector ReadVector(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool WriteFloat(AActor* A, const TCHAR* Name, float Value) const;
	bool WriteName(AActor* A, const TCHAR* Name, FName Value) const;

	/** Calls a no-argument BlueprintPure UFUNCTION by name and returns what it said.
	 *  This exists for ONE reason: the model must ask the yard the SAME question the
	 *  prompt tells the submission to ask. "The gate knows when somebody is standing in
	 *  it" is the only reader the prompt discloses, so the model calls exactly that
	 *  reader rather than re-deriving standing-in-it from the box's extents -- a
	 *  re-derivation is a second, undisclosed definition, and a stricter one fails a
	 *  correct submission for the handful of frames the two disagree over. */
	bool CallBoolFunc(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FVector CallVectorFunc(const AActor* A, const TCHAR* Name, bool& bOk) const;

	/** Intensity of a named UPointLightComponent on an actor, or -1 when there is no
	 *  such component. A hidden light reads 0: hidden and dark look identical. */
	double LightIntensity(const AActor* A, const TCHAR* ComponentName) const;
	/** Intensity of the FIRST point light on an actor (the head lamp), or -1. */
	double AnyLightIntensity(const AActor* A) const;

	// ------------------------------------------------------------- the oracle

	/** Every solid footprint in the yard THIS FRAME: the crates, the wall and the
	 *  truck where it is at this instant. Rebuilt each frame -- the truck moves. */
	void RebuildFootprints();
	/** 2-D segment versus axis-aligned rectangle. */
	static bool SegmentHitsRect(const FVector2D& P, const FVector2D& Q,
		const FVector2D& C, const FVector2D& H);
	/** How far the nearest footprint edge is from the flat line, in uu -- small when a
	 *  frame of motion could flip the answer. Used only for the marginality
	 *  suppression, never for a verdict. */
	double FootprintEdgeMargin(const FVector2D& P, const FVector2D& Q) const;

	/** The disclosed predicate, run against LIVE numbers and LIVE transforms: flat,
	 *  watcher location to the given place, inclusive at both edges, with nothing
	 *  solid on the flat line. bIncludeTruck=false answers the same question with the
	 *  truck taken out -- the CONSERVATIVE direction for a safety prediction, never
	 *  for a gate. */
	bool ModelCanSee(const FWatcher& W, const FVector& Point, bool bIncludeTruck,
		double& OutDistance, double& OutAngleDeg) const;
	/** The same predicate for a HYPOTHETICAL watcher pose -- used only to simulate the
	 *  yard forward when deciding whether a walk is safe to release. */
	bool ModelCanSeeFrom(const FWatcher& W, const FVector& Eye, const FVector& Facing,
		const FVector& Point, bool bIncludeTruck) const;
	/** The same predicate again with the truck placed WHERE IT WILL BE rather than
	 *  where it is -- the only way to ask "will the truck still be covering this line
	 *  in two seconds", which is what the shadow entry has to know before it commits
	 *  the runner to a walk it cannot abort. */
	bool ModelCanSeeWithTruckAt(const FWatcher& W, const FVector& Eye,
		const FVector& Facing, const FVector& Point, const FVector2D& TruckCentre) const;
	/** Is the truck's footprint across this flat line, with the truck at TruckCentre? */
	bool TruckOnLineAt(const FVector& Eye, const FVector& Point,
		const FVector2D& TruckCentre) const;

	/** The set of watchers the model says can see the runner right now. */
	void VisibleSet(const FVector& Point, TArray<int32>& Out) const;
	FString DescribeSet(const TArray<int32>& Set) const;
	FString DescribeLitLamps() const;

	/** True when any watcher's verdict is close enough to one of its own boundaries --
	 *  or to a footprint edge -- that a frame of sampling order could flip it. */
	bool AnyVerdictMarginal(const FVector& Point) const;

	// ------------------------------------------------- simulating the yard forward

	/** Where a watcher will be, and which way it will face, AheadS seconds from now if
	 *  it keeps walking its own round at its own base pace. */
	void PredictWatcher(const FWatcher& W, double AheadS, FVector& OutAt,
		FVector& OutFacing) const;
	/** The earliest time within HorizonS at which ANY watcher could see the runner if
	 *  it walked the given path from where it stands at its measured pace. The truck
	 *  is deliberately EXCLUDED -- a moving occluder can only ever help, so ignoring
	 *  it is the safe direction. Returns HorizonS when nobody can. */
	double EarliestSightingOnPath(const TArray<FVector>& Path, double HorizonS) const;
	/** The same question for standing still where the runner is. */
	double EarliestSightingStanding(double HorizonS) const;
	/** Where the truck's centre will be AheadS seconds from now: the same triangle wave
	 *  along the same rail, run forward from the LIVE position and the LIVE direction.
	 *  The rail's two ends are read off the truck itself, so this is the truck's own
	 *  arithmetic and not a guess about where it was placed. */
	FVector2D PredictTruck(double AheadS) const;
	/** Is now the moment to step into the shadow spot? True only when the forward
	 *  simulation says the runner arrives unseen, arrives inside a stretch where the
	 *  covering watcher's cone holds the spot AND the truck lies across the line, that
	 *  the stretch lasts at least the cover floor, and that the truck then lets go of
	 *  the line while the cone still holds -- the event phase 3 grades. */
	bool ShadowEntryRipe(double& OutArriveS, double& OutCoverS, double& OutClearS) const;

	// -------------------------------------------------------------- the staging

	bool ResolveStaging();
	bool ResolveRounds();
	void ReReadNumbers();
	void StageWatch(int32 WatchIndex);
	bool ValidateStagingContract();
	/** Probes every solid thing in the level at four heights and refuses to start if
	 *  any two heights disagree about what is in the way. */
	bool ValidateHeightsCannotMatter();
	/** Nothing but the floor, the crates, the wall, the truck and the watchers may
	 *  answer a query. */
	bool ValidateNothingElseIsSolid();
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	// ---------------------------------------------------------------- the drive

	/** The places the drive stands, solved from the live level rather than written
	 *  down, so a re-authored yard moves the drive with it. */
	bool SolveSpots();
	/** Has the round the plate is currently counting already ended? */
	bool RoundIsOver() const;
	/** The lane x-ranges no watcher can ever see under the staging in force -- the
	 *  rest points every long transit hops between. */
	void SolveSafeLaneBands();
	double NearestSafeLaneX(double X) const;
	/** A place the frozen covering watcher can plainly see, reachable without walking
	 *  through anything solid. Re-solved when the phase needs it. */
	bool SolveSeenSpot(int32 WatcherIndex, FVector& Out) const;
	/** The watcher currently walking a named round, or INDEX_NONE. */
	int32 WatcherOnRound(FName Tag) const;

	void BeginPhase(int32 NewPhase, double Now);
	void DriveHero(double Now);
	void AdvancePhases(double Now);
	/** Lays a governed transit into the phase's waypoint ladder: lane hops between
	 *  safe bands, then the final approach. */
	void PlanWalkTo(const FVector& Target, bool bViaLane);
	double PathLength(const FVector& From, const TArray<FVector>& Path) const;

	// --------------------------------------------------------------- the gates

	bool Suppressed(double Now) const;
	bool GateNotRewired(double Now);
	bool GateExactlyOneLamp(double Now);
	bool GateSeenTheMomentTheyCross(double Now);
	bool GateTruckShadow(double Now);
	bool GateOwnEyes(double Now);
	bool GateCaughtIsFinal(double Now);
	bool GateAwayIsFinal(double Now);
	bool GateRoundStartsClean(double Now);
	bool GateLampsShowWhatIsSeen(double Now);
	bool GateStandDown(double Now);
	/** The in-scene control, gauged at EVERY checkpoint whatever the suppression. */
	bool GateControlAtCheckpoint(double Now);

	void StepModel(double Now);
	void LogCalib(int32 Index, double Now) const;
	FString BoardDescription() const;
	int32 BoardReading() const;
	int32 RoundSlot() const;

	// ------------------------------------------------------------------ state

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FWatcher> Watchers;
	TArray<FRound> Rounds;
	TWeakObjectPtr<AActor> Mast;
	TWeakObjectPtr<AActor> Plate;
	TWeakObjectPtr<AActor> Gate;
	TWeakObjectPtr<AActor> Truck;
	TArray<TWeakObjectPtr<AActor>> Blockers;
	TArray<FVector> StagedBlockerAt;
	TArray<FVector> StagedBlockerHalf;
	FVector StagedMastAt = FVector::ZeroVector;
	FVector StagedPlateAt = FVector::ZeroVector;
	FVector StagedGateAt = FVector::ZeroVector;
	FVector TruckHome = FVector::ZeroVector;
	FVector TruckRailHalf = FVector::ZeroVector;
	FVector TruckHalf = FVector::ZeroVector;
	float TruckSpeed = 0.0f;
	/** The two ends of the rail, read OFF THE TRUCK rather than inferred from where it
	 *  happened to be standing when PrepareTest ran -- PrepareTest runs a fraction of a
	 *  second after BeginPlay, so the truck has already left the middle of its rail. */
	FVector RailEndA = FVector::ZeroVector;
	FVector RailEndB = FVector::ZeroVector;
	bool bRailEndsKnown = false;
	/** Which way it is running, measured from two consecutive frames. */
	FVector TruckPrevAt = FVector::ZeroVector;
	bool bTruckPrevKnown = false;
	double TruckHeading = 1.0;   // +1 toward RailEndB, -1 toward RailEndA

	/** The solid footprints as of this frame. The truck is always the LAST entry. */
	TArray<FFootprint> Footprints;
	int32 TruckFootprintIndex = INDEX_NONE;

	/** Which watcher is the in-scene negative control -- the one whose round the wall
	 *  stands across. Resolved from the geometry, never written down. */
	int32 SentryIndex = INDEX_NONE;
	/** The round the drive is built around: the one nearest the lane. */
	FName LaneRoundTag = NAME_None;
	FName FarRoundTag = NAME_None;
	FName WalledRoundTag = NAME_None;

	// the model
	int32 ModelOutcome = 0;             // 0 running, 1 away, 2 caught
	int32 SeenRoundIndex = 0;
	int32 PlateIndex = 0;
	double LastModelChangeAt = -100.0;
	TArray<int32> ModelVisible;

	// the drive
	double LaneY = 0.0;
	double WalkZ = 0.0;
	double MeasuredHeroSpeed = 500.0;
	FVector SpotShadow = FVector::ZeroVector;
	/** The lane rest point the runner waits on until the shadow entry ripens. */
	FVector SpotShadowWait = FVector::ZeroVector;
	FVector SpotSplit = FVector::ZeroVector;
	FVector SpotOpen = FVector::ZeroVector;
	FVector SpotSeen = FVector::ZeroVector;
	TArray<FVector2D> SafeBands;        // lane x-ranges nobody can ever see
	int32 Watch = 0;
	int32 Phase = 0;
	double PhaseStartedAt = 0.0;
	double PhaseDeadline = 0.0;
	double HoldSince = -1.0;
	double StagingUntil = -1.0;
	TArray<FVector> Waypoints;
	int32 WaypointIndex = 0;
	bool bWalkReleased = false;
	double NextSafetyCheckAt = -1.0;
	/** The shadow entry's own state: waiting on the rest point for the right moment. */
	bool bShadowEntryCommitted = false;
	double ShadowWaitSince = -1.0;
	double LastRipeReportAt = -1.0;
	bool bPrepared = false;
	bool bDriveComplete = false;

	// what the windows measured
	double TruckCoverSince = -1.0;
	double TruckCoverBest = 0.0;
	double TruckClearedAt = -1.0;
	int32 TruckWindowsProved = 0;
	double CrossFirstVisibleAt = -1.0;
	int32 GateEntries = 0;
	bool bInGateVolume = false;
	/** What the two split-spot holds saw, for the end-of-run opposite-answers claim. */
	bool bSplitHoldSeen[2] = {false, false};
	bool bSplitHoldDone[2] = {false, false};
	int32 SplitCoveringWatcher[2] = {INDEX_NONE, INDEX_NONE};
	/** How each round ended, in order. -1 never ended. */
	int32 RoundEnding[4] = {-1, -1, -1, -1};
	int32 RoundEndingChanges[4] = {0, 0, 0, 0};
	double RoundEndedAt[4] = {-1.0, -1.0, -1.0, -1.0};
	/** Who was looking when each round ended caught, latched at that instant. */
	TArray<int32> RoundCaughtBy[4];
	/** Measured once the staging is validated, for the messages and the deadlines. */
	double MeasuredCrossWindowS = 0.0;
	double MeasuredCrossClearanceS = 0.0;
	double MeasuredShadowWindowS = 0.0;
};
