// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-your-last-life-ends-the-run.
//
// Three runners on one floor. Each has a life budget PAINTED ON ITS OWN MARKER -- a
// number the fixture re-writes twice while the run is going -- a patch of crumbling
// ground that costs one life per crossing, and a finish disc that costs none but only
// opens to a runner holding at least the number PAINTED ON THE DISC, which the fixture
// re-writes twice as well. Two questions, and they are shaped differently:
//
//   * WHICH CROSSING IS THE LAST ONE, and what happens on that one crossing (nobody
//     comes back; the row goes dark; the word latches; nothing may move it again);
//   * WHEN THE GOAL OPENS. The ground is an EDGE -- it costs on the step that carries
//     a runner on. The finish is a CONDITION -- standing on it with enough in hand
//     wins, and that can become true with NOBODY MOVING AT ALL, because the disc's own
//     number came down or the runner's board went up. An answer that models the finish
//     the way it models the ground passes every arrival check and never wins here.
//
// The fixture runs its own copy of the whole rule against the same live world:
// remaining = max(0, the number CURRENTLY painted on that runner's own marker, minus
// the crossings that runner has suffered), a terminal latch the ledger decides, and
// the latch gating the ground, the finish and the board back. Every gate compares the
// level's VISIBLE state -- the lamps' actual glow and the text component's string --
// against that model. Nothing private is ever read: there is no lives property on any
// supplied class, and GetLitCount() (which a submission may rewrite) is never called.
//
// ------------------------------------------------------------------------------
// THE ONE CALIBRATION HAZARD, AND HOW IT IS CLOSED
// ------------------------------------------------------------------------------
// Two honest implementations disagree about WHEN a crossing happens, by up to one
// capsule radius of travel:
//
//   * an OVERLAP-driven answer (the patch's query volume vs the capsule) fires when
//     the capsule SURFACE touches the box -- capsule centre at box + 42 cm;
//   * a point-in-box answer (the reference) fires when the capsule CENTRE enters.
//
// 42 cm is 0.084 s at the template's 500 cm/s walk. This fixture:
//
//   1. ARMS ITS OWN MODEL AT THE EARLIEST OF THE TWO (the box grown by one capsule
//      radius in the plane), so it can never notice a crossing later than the
//      submission and score a correct spend as "lost a life while nothing touched it";
//   2. KEEPS DRIVING UNTIL THE CAPSULE CENTRE IS INSIDE THE PLAIN BOX, so it can never
//      notice a crossing EARLIER than the submission either. This one is not
//      decoration: the character coasts only ~28 cm after input is released
//      (v' = -(8v + 2000) from 500 cm/s), which is LESS than the 42 cm radius -- a
//      drive that released input at the grown box would leave a point-in-box answer
//      standing outside the patch, having never been claimed at all. That is a
//      manufactured FAIL of a correct reference, and it is why the release rule is
//      written against the PLAIN box;
//   3. SUPPRESSES a still-running runner's gates while it is within kBoundaryBandUu
//      OUTSIDE the patch's or the disc's edge, so the 0.084 s the two models can
//      disagree by is never judged. Only the outside: once the capsule centre is in,
//      every honest answer agrees it is in, and banding the inside too would leave a
//      runner LEFT LYING IN THE PATCH unjudgeable -- which is the one submission
//      WhileLivesRemainYouComeBackToYourMarker exists to name;
//   4. records the CLAIM SPOT at the plain-box entry (the fixture's own geometry, not
//      the submission's reaction), so "left standing where the ground claimed it"
//      is measured from a point ~28 cm from where a correct answer comes to rest,
//      against a disclosed 150 cm tolerance.
//
// Every timing tolerance below is a WIDENING of the disclosed contract (0.5 s to
// settle, 1 s to come back) and never a narrowing.
//
// ------------------------------------------------------------------------------
// WHAT THE DRIVE DOES, AND WHY IT CANNOT MANUFACTURE A FAILURE
// ------------------------------------------------------------------------------
//   * Tier-1 locomotion only: the shipping per-frame AddMovementInput timeline. No
//     key press anywhere.
//   * Every crossing is HEAD-ON: the drive always stages 400 cm clear of the patch
//     face on the side it is approaching from, then walks straight across it. No
//     boundary is ever skimmed.
//   * Runners are driven ONE AT A TIME, so every gate window names exactly one
//     runner and no FAIL has to be attributed between two moving subjects.
//   * No route except a crossing route ever touches the patch -- asserted in
//     PrepareTest, sampled along every segment. (The design's own drive table had the
//     win-leg runner walking to the finish straight through the patch, which would
//     have spent a third life and made the win leg arithmetically unreachable.)
//   * Every waiting phase is "stay here until MY model says X", never "for T seconds
//     since the level opened".
//   * Every walking deadline is derived from the MEASURED distance and the MEASURED
//     GetMaxSpeed(), never written down.
//
// ------------------------------------------------------------------------------
// PER-LEG STAGING -- the load-bearing numbers are NOT in the .umap
// ------------------------------------------------------------------------------
// PrepareTest re-paints all three markers to this leg's values before the drive
// starts, and re-paints two of them again mid-run in OPPOSITE directions. The leg is
// selected from the run's own framerate, so the two PIE processes run different
// numbers and a life count mined out of the committed map is wrong on both.
//
// ------------------------------------------------------------------------------
// GATE PRECEDENCE (the order Tick evaluates them; at most one of 2-8 is armed per
// runner per frame, so a named FAIL is never a race between two of them)
// ------------------------------------------------------------------------------
//   1  TheRunIsNotYoursToRewire            every frame, every runner, from the first
//   2  TheLastLifeEndsTheRun               the run-ending crossing .. +2.5 s, plus the
//                                          stay-put watch for the rest of the run
//   3  WhileLivesRemainYouComeBackToYourMarker  each non-final crossing .. +1.8 s,
//                                          plus the no-second-teleport watch after it
//   4  EachDeathSpendsExactlyOneLife       the same window, a DIFFERENT channel (lamps
//                                          rather than position); both run
//   5  TheBoardIsReadWhenItMatters         each mid-run re-paint .. +1.8 s
//   6  TheGoalOnlyOpensToWhatItAsksFor     a still-running runner standing on the disc
//                                          holding less than the disc asks for
//  6b  ReachingTheGoalWinsAndSpendsNothing the frame the disc opened to it, .. +1.8 s
//   7  ARunThatEndedNeverChangesAgain      from a runner's terminal event onward
//   8  TheRunReadsWhatItIs                 everywhere else, per runner
//   9  TheBystanderIsUntouched             every judged frame, ALWAYS LAST and only
//                                          once whichever gate was armed has agreed
//  10  BothRunsEndedTheirOwnWay            run level, at drive completion / sentinel
//  11  ARunnerIsAlwaysFreeToWalk           only when a walking phase overran: a body
//                                          the submission is holding in place
//
// TheRunIsNotYoursToRewire is ANTI-TAMPER, not discrimination: it is the ONE gate an
// empty submission passes, and it must never be counted in a discrimination k/N.
// BothRunsEndedTheirOwnWay is CORROBORATIVE: it reads the three words off the level at
// the end, but a runner showing the wrong one has already been named by a per-frame
// gate, so it should be discounted in a k/N too. Its MODEL half is a
// HARNESS-PRECONDITION and never a graded FAIL -- a drive that did not put one runner
// out and win another is ours, not the submission's.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "LifeRunTerminalFunctionalTest.generated.h"

class ACharacter;
class UBoxComponent;

UCLASS()
class ALifeRunTerminalFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ALifeRunTerminalFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// -------------------------------------------------------------------- model

	enum class ERunState : uint8
	{
		Running,
		Won,
		Lost
	};

	/** One runner and the fixture's whole model of its run. Nothing here is ever read
	 *  out of the submission -- it is all derived from the world's geometry and the
	 *  markers' live painted numbers. */
	struct FRunner
	{
		TWeakObjectPtr<ACharacter> Actor;
		/** Pinned at t=0 so "nobody is ever replaced" is checkable. */
		TWeakObjectPtr<AActor> Identity;
		/** The marker under this runner's feet when the run opened -- resolved once,
		 *  exactly as the prompt promises, and never re-derived. */
		TWeakObjectPtr<AActor> OwnMarker;
		int32 MarkerIndex = INDEX_NONE;
		FVector MarkerAt = FVector::ZeroVector;
		const TCHAR* Label = TEXT("");

		ERunState State = ERunState::Running;
		int32 Deaths = 0;
		int32 FrozenLit = 0;
		double TerminalAt = -1.0;
		/** Which of the two terminal kinds, for the frozen-word expectation. */
		bool bTerminalWasLoss = false;

		/** Crossing bookkeeping (the fixture's own geometry, never the submission's). */
		bool bInPatchLastFrame = false;
		int32 Crossings = 0;
		int32 SpendingCrossings = 0;
		double LastCrossingAt = -1.0;
		bool bLastCrossingWasFinal = false;
		FVector ClaimSpot = FVector::ZeroVector;
		bool bClaimSpotIsPlainEntry = false;
		int32 LitBeforeCrossing = 0;

		/** Finish-disc bookkeeping. */
		bool bOnDiscLastFrame = false;
		int32 DiscArrivals = 0;
		double FirstWinAt = -1.0;
		int32 LitBeforeWin = 0;
		/** Judged frames on which this runner stood on the finish holding LESS than
		 *  the disc asks for and correctly did not win. The leg proves nothing about
		 *  the goal's own number without them. */
		int32 ShortOnDiscJudged = 0;

		/** Re-paint bookkeeping (this runner's OWN marker). */
		double RepaintAt = -1.0;
		int32 RepaintFrom = 0;
		int32 RepaintTo = 0;

		/** Driven conflicting events after this runner's run ended. */
		int32 ConflictEvents = 0;

		double LastModelChangeAt = -1000.0;
		/** The lamp count read on the last frame this runner was judged. */
		int32 LitLastJudged = 0;
		/** For the no-second-teleport watch. */
		FVector WasAt = FVector::ZeroVector;
		bool bHaveWasAt = false;
		/** Every word this runner has ever been seen reading, for the run-level gate. */
		bool bEverReadWon = false;
		bool bEverReadLost = false;
	};

	/** One leg's whole staging table. Selected from the run's own framerate, so a
	 *  number mined out of the committed .umap is wrong on both legs. */
	struct FStaging
	{
		int32 Rate = 0;
		int32 StartA = 0;
		int32 StartB = 0;
		int32 StartC = 0;
		int32 RepaintA = 0;   // UP, after A's first crossing
		int32 RepaintB = 0;   // DOWN, after B's first crossing
		int32 FinalA = 0;     // after A's run has ended -- must change nothing
		int32 FinalB = 0;
		/** What the FINISH asks for. Staged so the win leg ARRIVES SHORT of it, moved
		 *  UP once (still short -- moving the number alone opens nothing), then DOWN
		 *  below what that runner is holding, which wins the run with nobody moving. */
		int32 DemandStart = 0;
		int32 DemandMid = 0;   // UP, while the win leg stands on the disc
		int32 DemandEnd = 0;   // DOWN, and the goal opens where the runner stands
	};

	/** What a phase of the drive is. Every waiting phase ends on the MODEL, never on
	 *  a wall-clock guess about the submission. */
	enum class EPhaseKind : uint8
	{
		Settle,     // nothing driven, gates off
		Walk,       // follow Waypoints; ends when the last one is reached
		Cross,      // walk at Target until the model records a crossing AND the
		            // capsule centre is inside the PLAIN patch box
		Stand,      // no input; ends HoldSeconds after that runner's last crossing
		            // (or, when AnchorIsPhaseStart, after the phase began)
		Repaint,    // arm quiet, write the marker by reflection, hold quiet
		Demand,     // the same, on the FINISH's own number
		Complete
	};

	struct FPhase
	{
		EPhaseKind Kind = EPhaseKind::Settle;
		int32 Runner = INDEX_NONE;
		TArray<FVector> Waypoints;
		double HoldSeconds = 0.0;
		bool bAnchorIsPhaseStart = false;
		int32 MarkerIndex = INDEX_NONE;
		int32 PaintTo = 0;
		FString Label;
	};

	// --------------------------------------------------------------- resolution

	bool ResolveStaging();
	bool ResolveLeg();
	bool ValidateStagingTable();
	bool ValidateGeometry();
	bool BuildPhases();
	bool ValidateRoutes();
	FString DescribeBrokenPlayerInput() const;

	/** Reflection, by NAME: the fixture never needs the agent's class layout, and the
	 *  same helpers WRITE the paint so an overridden setter cannot intercept staging. */
	int32 ReadInt(const AActor* A, const TCHAR* Name, bool& bOk) const;
	float ReadFloat(const AActor* A, const TCHAR* Name, bool& bOk) const;
	bool WriteInt(AActor* A, const TCHAR* Name, int32 Value) const;

	/** The painted number on a marker, read LIVE. */
	int32 PaintedOn(int32 MarkerIndex) const;
	/** What the finish is asking for right now, read LIVE off the disc. */
	int32 DemandNow() const;

	// ------------------------------------------------------------- the readouts

	/** Lit lamps, counted off the point lights' own intensity. Never GetLitCount(),
	 *  which lives on a class the submission may rewrite. OutTotal is how many lamp
	 *  components the runner carries at all (six, or the anti-tamper gate fires). */
	int32 LitCountOf(const FRunner& R, int32& OutTotal) const;
	/** The floating word, as its first run of ASCII letters, upper-cased. */
	FString WordOf(const FRunner& R) const;
	/** How many text components the runner carries (one, or anti-tamper fires). */
	int32 WordComponentsOf(const FRunner& R) const;

	// ---------------------------------------------------------------- the rule

	int32 RemainingFor(const FRunner& R) const;
	int32 ExpectedLitFor(const FRunner& R) const;
	const TCHAR* ExpectedWordFor(const FRunner& R) const;

	/** Capsule centre inside the patch box grown by one capsule radius in the plane --
	 *  the EARLIEST instant any part of the runner is over the patch. */
	bool InPatchArmed(const FVector& At) const;
	/** Capsule centre inside the plain patch box -- the LATEST instant any plausible
	 *  answer can have noticed, and the release rule for the drive. */
	bool InPatchPlain(const FVector& At) const;
	/** Signed planar distance from the patch box surface; negative inside. */
	double PlanarDistToPatch(const FVector& At) const;
	/** Flat distance from the finish disc's painted edge; negative inside. */
	double PlanarDistToDisc(const FVector& At) const;
	bool OnDiscArmed(const FVector& At) const;

	void StepModel(double Now);

	// -------------------------------------------------------------- suppression

	/** True on a frame no gate may judge this runner: the fixture is re-staging, the
	 *  runner's own model has just moved, or a still-running runner is close enough to
	 *  a trigger edge that two honest entry models could disagree. */
	bool SuppressedFor(const FRunner& R, double Now) const;

	// ------------------------------------------------------------------ gates

	bool GateNotRewired(double Now);
	bool GateLastLife(FRunner& R, double Now);
	bool GateComeBack(FRunner& R, double Now);
	bool GateSpendOne(FRunner& R, double Now);
	bool GateBoardRead(FRunner& R, double Now);
	bool GateGoalShort(FRunner& R, double Now);
	bool GateGoalWins(FRunner& R, double Now);
	bool GateEndedNeverChanges(FRunner& R, double Now);
	bool GateRunReads(FRunner& R, double Now);
	bool GateNoTeleport(FRunner& R, double Now, double Dt);
	bool GateBystander(double Now);
	/** Re-run for every runner before ANY harness exit, so a submission that stalls
	 *  the drive can never launder a FAIL into an uncredited non-graded exit. */
	bool ReCheckDisplays(double Now);
	/** A walking phase overran and the runner it was pushing has not moved:
	 *  something of the submission's is holding a body in place. True when it
	 *  has FAILED the run. */
	bool BlamedAPinnedRunner(const FPhase& P, double Now);

	// ------------------------------------------------------------------ drive

	void BeginPhase(int32 NewPhase, double Now);
	void AdvancePhases(double Now);
	void DrivePhase(double Now);
	void FinalGrade(double Now);
	void LogCalib(int32 Index, double Now) const;
	FString DescribeRunner(const FRunner& R) const;

	// ------------------------------------------------------------------ state

	TArray<FRunner> Runners;                       // 0 = A (loss leg), 1 = B (win), 2 = C
	TArray<TWeakObjectPtr<AActor>> Markers;        // sorted by Y ascending
	TArray<FVector> MarkerStagedAt;
	TArray<int32> MarkerStagedPaint;

	TWeakObjectPtr<AActor> Patch;
	TWeakObjectPtr<UBoxComponent> PatchBox;
	FTransform PatchXform;
	FVector PatchExtent = FVector::ZeroVector;
	FVector PatchStagedAt = FVector::ZeroVector;
	double PatchNearX = 0.0;
	double PatchFarX = 0.0;
	double PatchCentreX = 0.0;
	double PatchHalfY = 0.0;

	TWeakObjectPtr<AActor> Disc;
	FVector DiscStagedAt = FVector::ZeroVector;
	float DiscRadius = 0.0f;
	float DiscStagedRadius = 0.0f;
	/** What the fixture last painted on the finish, for the anti-tamper read-back. */
	int32 DiscStagedDemand = 0;
	int32 DemandWrites = 0;

	FStaging Stage;

	double CapsuleRadius = 42.0;
	double WalkSpeed = 500.0;
	double WalkZ = 96.0;
	/** The crossing lane the drive alternates onto -- DERIVED: the spot inside the
	 *  patch whose nearest marker is most clearly NOT the loss-leg runner's own. */
	double OffLaneY = 0.0;
	double OffLaneMarginUu = 0.0;
	int32 OffLaneNearestMarker = INDEX_NONE;
	double BypassY = 0.0;

	TArray<FPhase> Phases;
	int32 PhaseIndex = -1;
	int32 WaypointIndex = 0;
	double PhaseStartedAt = 0.0;
	double PhaseDeadline = 0.0;
	/** Where the phase's runner stood when it opened, for the pinned-body check. */
	FVector PhaseStartLocation = FVector::ZeroVector;
	int32 CrossingsAtPhaseStart = 0;
	bool bRepaintPending = false;

	/** Nothing is judged while the fixture itself is moving the level's numbers. */
	double StagingUntil = -1.0;
	bool bPrepared = false;
	bool bDriveComplete = false;
	bool bGraded = false;
	/** The crossing index on which the staging says the loss-leg runner must run out. */
	int32 PredictedFinalCrossing = 0;
};
