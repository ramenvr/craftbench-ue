// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE - DO NOT EDIT.
//
// L2 for t3-gate-and-door.
//
// A yard with ONE shared rule and consumers that want DIFFERENT answers out of it.
// FOUR barriers are instances of the same class: an old door with one pad, a matched
// twin 3,000 cm east that the drive never approaches, and TWO new gates in the west
// wall, each with two pads and two lamps of its own. The pads answer one question -
// who is resting on me - and that question counts people and crates alike, which is
// the only reason the old door works. A gate needs the same pads to yield an answer
// that counts crates, by name, in an ordered pair, with a person counting for nothing.
//
// THE TWO GATES SHARE THE FLOOR AND DISAGREE. Each gate's two pads are painted on the
// same two patches of floor as the other's, so both see exactly the same three crates
// at exactly the same moments - and each is cut for its OWN ordered pair, re-cut on
// its own schedule. Through most of the run one gate is open while the other is shut,
// and at the last re-cut, with nothing in the yard moving at all, one comes down while
// the other goes up. Anything that decides once for "the gate", stores the rule
// anywhere shared, or indexes the lamps globally is wrong for one of the two.
//
// THE FIXTURE RUNS THE SAME RULE, AND NEVER CALLS THE SUBMISSION'S CODE. Every frame
// it re-reads, live and BY PROPERTY NAME, each pad's centre / ContactRadiusUu /
// GroundedBandUu / AnsweredBarrier, each barrier's OpenAngleDeg / TravelRateDegPerSec /
// CutForFirstName / CutForSecondName, each crate's CrateName and live transform, and
// each lamp's NameSlot / LampBarrier. It then steps its own model with the SAME resting
// predicate the prompt discloses (the middle of a body's colliding bounds within the
// pad's own radius measured flat, the base of those bounds within the pad's own band of
// the pad's level), the same any-body rule for a barrier cut for nothing, and the same
// both-names-home rule for a barrier cut for a pair. It re-implements the predicate
// rather than calling AYardPadActor's copy of it, because that copy lives in the
// agent's writable module and a submission that widened it would otherwise move the
// model with it. TheYardIsNotYoursToRewire pins both numbers so the two can only
// disagree if a submission changed something the prompt tells it not to change.
//
// THE LOAD-BEARING FACT IS RE-STAGED THREE TIMES, and the first re-staging happens
// before the first judged frame. PIE fires BeginPlay on every placed actor BEFORE
// PrepareTest, so PrepareTest writing the graded pair over the pair the level was
// saved holding is what makes a hard-coded or BeginPlay-cached answer wrong from the
// FIRST judged frame instead of from the middle of the run. Two further re-cuts move
// it again mid-run, the second of them with nothing in the yard moving at all.
//
// SHUT IS STRUCTURAL, NOT SAMPLED. A barrier's Hinge is squared at BeginPlay and its
// Panel carries no relative rotation of its own, so "shut" is exactly the barrier
// ACTOR's own yaw - a level-staged constant that TheYardIsNotYoursToRewire pins. That
// is deliberately not "the panel's pose the first time the fixture looked": a
// submission that swings a panel open in its first frames would otherwise have its own
// wrong pose recorded as the pose it is graded against.
//
// THE DRIVE IS ADAPTIVE AND ROUTED. Every shove is "push until this crate has reached
// its stop", never "push for T seconds"; every walk is "until arrival"; every dwell is
// a wall-clock hold AFTER the crate has stopped and the character has RETREATED to a
// standoff, so no dwell is judged with the character leaning on a crate 102 uu from a
// pad centre whose radius is 100. Every transit is routed down two lanes that clear
// every rail by at least 380 uu and every pad centre by at least 380 uu, because a
// straight line between two stations passes within 24 uu of a crate and would shove it.
// The character is the PIE-supplied pawn, driven through the shipping per-frame
// AddMovementInput timeline - the same path a human drives with WASD. No key press is
// ever injected.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "OldDoorYardFunctionalTest.generated.h"

class ACharacter;
class UPointLightComponent;
class USceneComponent;

UCLASS()
class AOldDoorYardFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AOldDoorYardFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------ the yard

	/** One barrier: the old door, its untouched twin, or the new gate. */
	struct FBarrier
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<USceneComponent> Panel;
		FString Label;

		/** STRUCTURAL, not sampled: the barrier actor's own yaw. See the file header. */
		double ShutYaw = 0.0;

		/** What the FIXTURE ITSELF last wrote into this barrier's two name slots. The
		 *  integrity gate compares against THIS, never against what the level holds -
		 *  the level is deliberately saved holding different pairs. Both doors stay
		 *  empty for the whole run, so a submission that writes names onto a door to
		 *  push it down the new branch is caught by the same clause. */
		FName ExpectFirst;
		FName ExpectSecond;

		/** What the yard staged, pinned every frame. */
		FVector StagedLoc = FVector::ZeroVector;
		double StagedYaw = 0.0;
		double StagedOpenAngleDeg = 0.0;
		double StagedTravelRate = 0.0;

		/** Per-frame travel-cap tracking. Seeded from the first sample, never from a
		 *  default, or frame one reads hundreds of cm of travel and fails everything. */
		double LastAngle = 0.0;
		FVector LastPanelLoc = FVector::ZeroVector;
		bool bSeeded = false;

		/** The fixture's own model of what this barrier should be doing. */
		bool bModelOpen = false;
		double ModelChangedAt = -1000.0;
		/** When the panel actually got there, for the reported latency. Negative
		 *  means it has not got there yet in the window that is running. */
		double ReachedAt = -1.0;
	};

	/** One floor pad. */
	struct FPad
	{
		TWeakObjectPtr<AActor> Actor;
		FString Label;
		FVector Centre = FVector::ZeroVector;
		double Radius = 0.0;
		double Band = 0.0;
		TWeakObjectPtr<AActor> Answers;

		FVector StagedCentre = FVector::ZeroVector;
		double StagedRadius = 0.0;
		double StagedBand = 0.0;
		TWeakObjectPtr<AActor> StagedAnswers;
	};

	/** One crate on its rail. The rail is re-derived here from the crate's own placed
	 *  pose, exactly as the crate's BeginPlay derives it, rather than read back
	 *  through the crate's accessors - which live in the agent's writable module. */
	struct FCrate
	{
		TWeakObjectPtr<AActor> Actor;
		FString Label;
		FName CrateName;
		FVector Anchor = FVector::ZeroVector;
		FVector Axis = FVector::ForwardVector;
		/** Flat unit normal to the rail, pointing at the lane the drive walks. */
		FVector Side = FVector::RightVector;
		double RailLen = 0.0;
		double ShoveSpeed = 0.0;

		FName StagedName;
		double StagedRailLen = 0.0;
		double StagedShoveSpeed = 0.0;
	};

	/** One lamp on the gate's frame. */
	struct FLamp
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<UPointLightComponent> Light;
		FString Label;
		int32 Slot = 0;
		TWeakObjectPtr<AActor> Barrier;
		/** Which barrier in Barriers this lamp is bolted to. Resolved once; a lamp
		 *  stands for a slot ON ITS OWN GATE, never for a slot in the yard. */
		int32 GateIndex = INDEX_NONE;
		int32 StagedSlot = 0;
		TWeakObjectPtr<AActor> StagedBarrier;
		/** Its OWN clock, so the disclosed 1.20 s applies per lamp rather than being
		 *  swallowed by one yard-wide settle window. */
		bool bExpect = false;
		double ExpectChangedAt = -1000.0;
		bool bExpectSeeded = false;
	};

	// ------------------------------------------------------------- the drive plan

	enum class EStep : uint8
	{
		Go,       // walk the routed lanes to Target, then hold Hold seconds
		Push,     // shove Crate toward Dir until it reaches that stop
		Retreat,  // hop off the rail onto the crate's own lane, then hold
		Stand,    // hold still where you are
		Recut,    // the fixture rewrites the gate's pair; gates blind for a window
		Finish
	};

	struct FStep
	{
		EStep Kind = EStep::Go;
		int32 Phase = 0;
		/** Which of the gate-panel gates owns the judged frames of this step. */
		int32 ArmedGate = 0;
		int32 Crate = INDEX_NONE;
		int32 Pad = INDEX_NONE;
		double Dir = 1.0;
		double Hold = 0.0;
		int32 Recut = INDEX_NONE;
		/** Where the walk ends, and which lane it hangs off. Lane INDEX_NONE means
		 *  this step does no walking at all. */
		FVector Target = FVector::ZeroVector;
		int32 Lane = INDEX_NONE;
		double ArriveUu = 0.0;
		/** True when the target IS a pad centre: the drive keeps a light corrective
		 *  input on through the hold so braking cannot carry the character out past
		 *  the pad's own radius, which is what a person standing on a pad does. */
		bool bStayOnTarget = false;
		/** Filled when the step begins, from the character's LIVE position. */
		TArray<FVector> Route;
		FString What;
	};

	// -------------------------------------------------------------- resolution

	bool ResolveTagged(const TCHAR* Tag, int32 Expected, TArray<AActor*>& Out);
	bool ResolveOne(const TCHAR* Tag, TWeakObjectPtr<AActor>& Out);
	USceneComponent* ResolvePanel(AActor* Door) const;
	UPointLightComponent* ResolveLight(AActor* Lamp) const;

	double ReadFloat(const AActor* A, const TCHAR* Name, bool& bOk) const;
	int32 ReadInt(const AActor* A, const TCHAR* Name, bool& bOk) const;
	FName ReadName(const AActor* A, const TCHAR* Name, bool& bOk) const;
	AActor* ReadActor(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool WriteName(AActor* A, const TCHAR* Name, FName Value) const;

	bool ResolveYard();
	bool StageDrive();
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	// --------------------------------------------------------------- the oracle

	/** THE DISCLOSED PREDICATE, re-implemented: the middle of the body's colliding
	 *  bounds within this pad's own radius measured flat, its base within this pad's
	 *  own band of the pad's level. */
	bool IsResting(const FPad& Pad, const AActor* Body) const;
	/** Is any body at all resting on this pad (person or crate alike). */
	bool AnyResting(const FPad& Pad) const;
	/** Is a crate carrying exactly this name resting on any pad answering for B. */
	bool NamedCrateHome(const FBarrier& B, FName Wanted) const;
	/** What the model says this barrier should be doing right now. */
	bool ModelWants(const FBarrier& B) const;
	/** The name in one slot of one barrier right now, read live off that barrier. */
	FName LiveCut(const FBarrier& B, int32 Slot) const;

	double PanelAngle(const FBarrier& B) const;
	bool LampIsLit(const FLamp& L) const;
	/** Which crates are home on one barrier's own pads, as an ASCII list. */
	FString HomeCrateList(const FBarrier& B) const;
	FString LampStateList() const;

	// ---------------------------------------------------------------- the gates

	/** Nothing is judged on a frame where the model has just changed, the fixture is
	 *  re-staging, or the drive has not arrived. Each is a WIDENING of the disclosed
	 *  contract, never a narrowing. */
	bool Suppressed(double Now) const;
	/** Is this barrier where the model says it must be, now that the disclosed band
	 *  has run out? Fills OutWhy with the whole picture when it is not. Shared by
	 *  every panel gate, so the arithmetic is written once; the gate NAME is chosen
	 *  by the caller, which is what keeps at most one of them armed per frame. */
	bool BandVerdict(const FBarrier& B, double Now, FString& OutWhy) const;
	/** The two baseline old-door cycles' own measured numbers, so a regression is
	 *  reported against a measurement from the same run, never against a constant. */
	FString BaselineText() const;
	/** Which gate-panel gate the step in progress arms. */
	int32 ArmedNow() const;
	bool GateNotRewired(double Now);
	bool GateTwinNeverMoves(double Now);
	bool GateOldDoorBand(double Now);
	bool GateRunnerIsNotACrate(double Now);
	bool GateCutRightNow(double Now);
	bool GateLeavesAndComesBack(double Now);
	bool GateStaysShut(double Now);
	bool GateOpensWhenBothHome(double Now);
	/** The second gate, gauged on EVERY judged frame from its own model. It is the
	 *  in-scene control on the side of the coupling the submission actually builds:
	 *  a matched instance, cut for its own pair, over the same pads and the same
	 *  crates, whose answer disagrees with the arch gate's through most of the run. */
	bool GateSecondGateAnswers(double Now);
	bool GateLamps(double Now);
	void GradeRunLevel(double Now);

	/** The per-frame travel caps, one call per barrier, seeded on first sight. */
	bool CheckTravelCaps(FBarrier& B, double Budget, const TCHAR* GateName);

	/** Re-checked UNCONDITIONALLY before any overrun is written off as staging, so a
	 *  submission that jams a panel across the walking lane is a FAIL and not an
	 *  uncredited harness exit. Returns true when all three still hold. */
	bool PreservationStillHolds(double Now);
	void FailStaging(const FString& Why, double Now);

	// ---------------------------------------------------------------- the drive

	void StepModel(double Now);
	void DriveCharacter(double Now, float DeltaSeconds);
	void AdvanceSteps(double Now);
	void ApplyRecut(int32 Which, double Now);
	void LogCalib(int32 Index, double Now) const;

	/** Rail parameter of a crate, measured from its own anchor, by the fixture. */
	double RailParam(const FCrate& C) const;
	/** Where the character waits before shoving this crate toward that stop. */
	FVector PushStation(int32 CrateIndex, double Dir) const;
	/** A routed path from the character's current position to Target on Lane. Never
	 *  a straight line: a straight line between two shove stations passes within
	 *  24 uu of a crate and would shove it. */
	TArray<FVector> RouteTo(const FVector& Target, int32 Lane) const;
	/** The X of a lane, and which lane a point hangs off. */
	double LaneX(int32 Lane) const;
	int32 LaneOf(const FVector& P) const;
	void BeginStep(double Now);
	/** Do the pair's two names both exist on crates, and does the pair name the
	 *  near-pad crate (without which the gate can never be opened at all)? */
	bool PairIsOpenable(FName First, FName Second) const;

	// ------------------------------------------------------------------- state

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FBarrier> Barriers;
	TArray<FPad> Pads;
	TArray<FCrate> Crates;
	TArray<FLamp> Lamps;

	/** Role indices, resolved by tag. */
	int32 IdxOldDoor = INDEX_NONE;
	int32 IdxTwinDoor = INDEX_NONE;
	int32 IdxGate = INDEX_NONE;      // the arch gate
	int32 IdxSideGate = INDEX_NONE;  // the second gate, cut for its own pair
	int32 IdxOldPad = INDEX_NONE;
	int32 IdxTwinPad = INDEX_NONE;
	int32 IdxNearPad = INDEX_NONE;
	int32 IdxFarPad = INDEX_NONE;
	int32 IdxSideNearPad = INDEX_NONE;  // painted over the arch gate's near pad
	int32 IdxSideFarPad = INDEX_NONE;   // and over its far pad
	int32 IdxCrateNear = INDEX_NONE;    // A
	int32 IdxCrateFarEast = INDEX_NONE; // B
	int32 IdxCrateFarWest = INDEX_NONE; // C

	/** The model, and when it last changed. */
	double LastModelChangeAt = -1000.0;
	FString LastModelDigest;

	/** The four old-door cycles: when the character arrived, how long the panel took
	 *  to clear 80 deg, when it left, how long it took to come home. Cycles 0 and 1
	 *  are the in-run baseline the later two are reported against. */
	struct FCycle
	{
		double OpenLatency = -1.0;
		double ShutLatency = -1.0;
		double AngleReached = 0.0;
		bool bGraded = false;
	};
	FCycle Cycles[4];
	int32 CycleCursor = 0;

	/** Run-level bookkeeping for TheGateRoseAgainAfterEveryRecut. */
	bool bGateRoseBeforeRecut1 = false;
	bool bGateCameHomeBeforeRecut1 = false;
	bool bGateRoseBetweenRecuts = false;
	bool bGateCameHomeAfterRecut2 = false;
	/** And for the second gate, which rises where the arch gate falls: it comes up
	 *  while the arch gate is shut before the first re-cut, comes home again, and
	 *  comes up a second time at the re-cut where NOTHING IN THE YARD MOVES and the
	 *  arch gate is coming down. */
	bool bSideRoseBeforeRecut1 = false;
	bool bSideCameHomeBeforeRecut1 = false;
	bool bSideRoseAfterRecut2 = false;
	int32 RecutsApplied = 0;

	/** The drive. */
	TArray<FStep> Steps;
	int32 StepIndex = 0;
	int32 RouteIndex = 0;
	double StepStartedAt = 0.0;
	double StepDeadline = 0.0;
	double HoldSince = -1.0;
	/** Set once a Push has reached its stop; the retreat then runs. */
	bool bPushDone = false;
	double HeroSpeed = 500.0;
	double WalkZ = 0.0;
	bool bPrepared = false;
	bool bDriveComplete = false;
	bool bArrived = false;
	double StagingUntil = -1.0;

	/** The routed ring, solved in StageDrive from the placed rails and pads. Two
	 *  lanes along the rails' bearing, one on the outside of each rail group, plus a
	 *  crossing line at each end. Every clearance is measured, never assumed. */
	double LaneNearX = 0.0;   // the lane serving the near-rail crate and both pads
	double LaneFarX = 0.0;    // the lane serving the two contested rails
	double CrossNorthY = 0.0;
	double CrossSouthY = 0.0;
};
