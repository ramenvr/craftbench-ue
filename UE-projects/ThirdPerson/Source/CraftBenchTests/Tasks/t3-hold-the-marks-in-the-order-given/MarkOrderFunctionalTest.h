// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-hold-the-marks-in-the-order-given.
//
// A hall with five painted rings and a duty board. Each ring banks occupancy time while
// the character stands in it; the board says which rings, in what order; and only the
// ring whose turn it is banks anything at all. The fixture runs ITS OWN COPY of that
// whole rule -- the same disclosed ring predicate, the same pause-and-resume banking,
// the same finish-against-the-live-number test, the same whole-hall wipe on an
// out-of-turn step, the same inert unlisted mark, the same restart on a new list -- and
// grades what the HALL SHOWS against it. Nothing private is ever read out of the
// submission: every gate is a statement about the five faces, the five lamps and the
// one tally.
//
// SIX THINGS THAT DECIDE THE SHAPE OF THIS FIXTURE:
//
//  1. THE PREDICATE IS DISCLOSED AND SHIPPED. "Standing on a mark" is a flat
//     centre-to-character distance against that mark's own RingRadiusUu, inclusive at
//     the edge, and AFloorMarkActor ships it as IsInsideRing. The fixture computes the
//     identical thing from the mark's live transform and the pawn's actor location, so
//     a submission that uses the supplied predicate CANNOT disagree with the fixture
//     about which frame an entry happened on. One that rolls its own sphere overlap
//     can, by up to a frame -- which is what the crossing suppression below is for.
//
//  2. EVERY NUMBER IS RE-READ EVERY FRAME AND RE-STAGED MID-RUN. The board's list, its
//     length and every mark's RequiredSeconds are read live. The fixture writes round 1
//     in PrepareTest (which runs AFTER BeginPlay, so a snapshot taken at BeginPlay is
//     already wrong at the baseline: the committed .umap carries a TWO-name decoy
//     list), RAISES one mark's number mid-stand, DROPS another below its already-banked
//     value mid-stand, DROPS the current mark's number below its already-banked value
//     TWICE MORE with the character parked clear of every ring (which must finish that
//     mark at once with NOBODY MOVING -- the one staging a finish test nested inside
//     the banking step can never produce), replaces the whole list mid-stand with a
//     SHORTER one drawn from a different subset, and replaces it once more with a list
//     of the SAME length, the SAME names, the SAME first name and the SAME seconds in a
//     DIFFERENT ORDER (which a length-, first-name- or set-comparing change detector
//     cannot see at all). No cached answer survives any of them. EVERY STAGED SET IS
//     WRITTEN IN ONE FRAME -- writing four numbers across four frames would manufacture
//     transient sets whose pairwise separation nobody checked, and any gate can be
//     judged on one of them.
//
//  3. THE DRIVE IS ANCHORED TO THE FIXTURE'S OWN MODEL, NEVER TO THE SUBMISSION. Every
//     standing step is "stay until MY model says this mark's bank reads X", never "stay
//     for T seconds" and never "stay until the hall says so". A submission that does
//     nothing therefore cannot stall the drive -- it just fails the gate that names it,
//     and no failure can ever be laundered into an uncredited harness exit. The
//     converse duty is discharged in AttributeOverrun(): before ANY deadline or
//     sentinel overrun is written off as a staging fault, gates 1, 9 and 12 are
//     re-checked unconditionally.
//
//  4. THE WINDOWED GATES ARM ON MODEL EVENTS, NOT ON STEP NUMBERS. An out-of-turn
//     entry, a list replacement, a re-entry onto the current mark, an off-mark wait and
//     a completion each arm their own gate wherever they happen. The drive's job is
//     only to MAKE those events happen, twice each, and the run-level gate asserts that
//     the HALL showed the right thing both times.
//
//  5. THE ROUTE IS SOLVED FROM THE LIVE TRANSFORMS AND REFUSED IF IT DOES NOT COME OUT.
//     One highway lane at y = 0 plus one column per mark, all derived from where the
//     hall actually put the marks. Every planned segment is measured against every ring
//     it is not meant to cross, and a hall that cannot be walked ends the run as
//     HARNESS-PRECONDITION before a single gate is judged. Each step carries the set of
//     rings it is ALLOWED to cross, so the deliberate control crossings are declared
//     rather than tolerated.
//
//  6. THE FACE TOLERANCE CARRIES ITS OWN UNCERTAINTY. The prompt promises a face may
//     lag a quarter second, and one-decimal rounding alone is +/-0.05 s. On top of that
//     the board and the fixture read the pawn's location in whatever order the engine
//     ticks them, so on each ring crossing the two models can disagree by exactly one
//     frame of banking. That is bounded, per mark, and it RESETS when the bank does --
//     so each mark carries an Uncertainty that grows by one frame per crossing within
//     the current attempt and is zeroed by every wipe, list change and completion. The
//     comparison is kFaceLagS + Uncertainty, capped at kUncertaintyCapS.
//
//  7. BOTH HALVES OF EVERY RULE ARE DRIVEN, TWICE EACH. A rule with two branches whose
//     drive only ever exercises one of them is an ungated rule, however loudly the
//     prompt states it. Three branches were ungated on 2026-08-19 and are now driven:
//     an out-of-turn step onto a mark LATER in the list that has never been the
//     current one (every out-of-turn step in the run used to land on a mark that was
//     both already finished AND at list index 0); a completion with NOBODY standing
//     anywhere; and a list replacement that keeps the length. The run-level gate
//     counts each of the three separately and demands two of each.
//
// TASK.MD PHASE MAP. task.md's "### The drive" table has 25 rows; this fixture runs 38
// steps, because five of those rows are several walks and stands (a row that says
// "re-walk the whole list in order" is four stands). The mapping is written into
// BeginStep, step by step, and every step logs its own label.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "MarkOrderFunctionalTest.generated.h"

class ACharacter;
class UWorld;

UCLASS()
class AMarkOrderFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMarkOrderFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------- the hall

	struct FMark
	{
		TWeakObjectPtr<AActor> Actor;

		/** Read LIVE every frame -- the hall re-writes RequiredSeconds mid-run. */
		FName Name = NAME_None;
		double Required = 0.0;
		double Radius = 0.0;
		FVector At = FVector::ZeroVector;

		/** What the FIXTURE staged for the phase in progress. A submission that writes
		 *  any of these is caught by comparison rather than by trust. */
		FName StagedName = NAME_None;
		double StagedRequired = 0.0;
		double StagedRadius = 0.0;
		FVector StagedAt = FVector::ZeroVector;

		/** The number this mark carried BEFORE the most recent mid-run rewrite, and
		 *  when that rewrite landed. Gate 8's early arm needs both: a submission that
		 *  cached the required value at the start of the stand finishes the mark when
		 *  the bank passes THIS number, and that is the failure to name. */
		double PreviousRequired = 0.0;
		double RewrittenAt = -1000.0;

		/** Label used in messages -- the staged name, so a renamed mark still reads. */
		FString Label;

		// ------------------------------------------------------------ the model
		/** Seconds banked in the CURRENT attempt. bHasBank mirrors the reference's
		 *  "there is no entry in the map yet" state, which its finish test reads. */
		double Bank = 0.0;
		bool bHasBank = false;
		bool bFinished = false;
		double FinishedAt = -1000.0;
		/** The required value at the instant of finishing (the bank clamps to it) and
		 *  the UN-clamped bank at that instant. A submission may legitimately show
		 *  either; see GateEveryFace. */
		double RequiredAtFinish = 0.0;
		double BankAtFinish = 0.0;
		/** When bFinished last changed, for gate 12's PER-MARK settle grace. */
		double FinishedChangedAt = -1000.0;

		bool bInside = false;
		bool bInsideLast = false;
		/** One frame of sampling ambiguity per crossing in this attempt; zeroed with
		 *  the bank. */
		double Uncertainty = 0.0;
		int32 CrossingsThisAttempt = 0;
		/** Ring crossings over the whole run, for the calib line and for gate 9's
		 *  "the route really did walk through the control twice". */
		int32 CrossingsTotal = 0;
	};

	// ------------------------------------------------------------ reflection helpers
	// The hall's numbers are read and written BY NAME, never through a cast: the
	// fixture never needs to know the agent's class layout, and a submission is free to
	// subclass either placed actor.

	double ReadFloat(const AActor* A, const TCHAR* PropName, bool& bOk) const;
	int32 ReadInt(const AActor* A, const TCHAR* PropName, bool& bOk) const;
	FName ReadName(const AActor* A, const TCHAR* PropName, bool& bOk) const;
	bool ReadBool(const AActor* A, const TCHAR* PropName, bool& bOk) const;
	bool ReadNameArray(const AActor* A, const TCHAR* PropName, TArray<FName>& Out) const;
	bool WriteFloat(AActor* A, const TCHAR* PropName, double Value) const;
	bool WriteNameArray(AActor* A, const TCHAR* PropName, const TArray<FName>& Values) const;

	/** The brightest VISIBLE point light on this mark. THE LIGHT, not a flag: a
	 *  burning lamp is what a reviewer sees, and a private bool is invisible to
	 *  reflection anyway. */
	double LampIntensity(const FMark& M) const;

	// ----------------------------------------------------------------- the readouts

	/** The two numbers this mark's FACE currently reads, mirrored by the supplied
	 *  ShowBank in the same breath it writes the glass. False when no face has ever
	 *  been written -- which is an AGENT failure, never a harness exit. */
	bool ReadFace(const FMark& M, double& OutBanked, double& OutRequired) const;
	/** The two numbers the board's TALLY face currently reads. */
	bool ReadTally(int32& OutFinished, int32& OutLength) const;

	// -------------------------------------------------------------- staging + model

	bool ResolveHall();
	bool BuildRoute();
	bool ValidateStagedSet(const TCHAR* Which, const TArray<double>& Seconds,
		const TArray<FName>& List);
	void ReReadHall();

	/** Writes one staged configuration of the hall -- every number in ONE frame, plus
	 *  the list -- and remembers it as the thing gate 1 compares against. */
	void StageRound(int32 Which, double Now);
	/** One mid-stand rewrite, in one frame, remembering the value it replaced. */
	void StageOneRequired(int32 MarkIndex, double NewRequired, double Now);

	int32 MarkIndexNamed(FName InName) const;
	int32 IndexInModelList(FName InName) const;
	int32 MarkUnderCharacter() const;

	void StartRoundOver(double Now, const TCHAR* Why);
	void StepModel(double Dt, double Now);
	int32 ModelFinishedCount() const;

	// --------------------------------------------------------------- the suppression

	/** True on a frame no everywhere-else gate may judge: the fixture is re-staging the
	 *  hall, or the model changed state inside the last kSuppressS (1.5x the half
	 *  second the prompt promises). */
	bool SettleSuppressed(double Now) const;
	/** True while the character is close enough to a ring's edge, or recently enough
	 *  past a modelled crossing, that a frame of sampling order could put the two
	 *  models on opposite sides of it. */
	bool EdgeSuppressed(double Now) const;
	/** True for the few frames after the fixture wrote the hall's numbers. */
	bool StagingSuppressed(double Now) const;
	/** kFaceLagS plus this mark's accumulated one-frame sampling ambiguity. */
	double FaceTolerance(const FMark& M) const;

	// -------------------------------------------------------------------- the gates
	// Each returns TRUE when the run may continue. Each FAILS with a substring nothing
	// else in this file uses, so the discrimination matrix can always say which fired.

	bool GateHallNotRewired(double Now);
	bool GateWrongStepEmpties(double Now);
	bool GateOutOfTurnBanksNothing(double Now);
	bool GateListChangeRestarts(double Now);
	bool GateBankStillThere(double Now);
	bool GateBankPicksUp(double Now);
	bool GateBankHoldsAway(double Now);
	bool GateWaitsForItsOwnNumber(double Now);
	bool GateUnnamedStaysCold(double Now);
	bool GateEveryFace(double Now);
	bool GateBoardTally(double Now);
	bool GateLamps(double Now);
	bool RunLevelGate(double Now, bool bAtSentinel);

	/** True when one of gates 2-8 is armed on this frame, i.e. when the everywhere-else
	 *  channels must stand down because a sharper gate is already speaking. */
	bool AnyWindowArmed(double Now) const;

	/** Every graded failure goes through here. */
	void FailGate(const FString& Message);
	/** A deadline or sentinel overrun. Re-checks gates 1, 9 and 12 UNCONDITIONALLY
	 *  first, so a hall that never advanced cannot launder a FAIL into a harness exit,
	 *  and only then attributes the overrun to staging. */
	void AttributeOverrun(double Now, const FString& What);

	FString DescribeHall() const;
	FString DescribeShownFaces() const;
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	// -------------------------------------------------------------------- the drive

	void BeginStep(int32 NewStep, double Now);
	void DriveHero(double Now);
	bool StepComplete(double Now) const;
	void AdvanceSteps(double Now);
	void MaybeFireStagedRewrite(double Now);
	void LogCalib(int32 Index, double Now) const;

	FVector Lane(double X) const;
	FVector Centre(int32 MarkIndex) const;
	double PathLength(const FVector& From, const TArray<FVector>& Way) const;

	/** Does this polyline clear every ring it is not ALLOWED to cross, by
	 *  kNonTargetClearUu? Used twice on purpose: once up front in BuildRoute over the
	 *  route PRIMITIVES (the lane, every column, the three declared crossing legs), and
	 *  again in BeginStep over the actual polyline about to be walked. A walk that
	 *  brushes a ring nobody aimed at would wipe the round and the whole comparison
	 *  would be against the wrong answer, so this is checked rather than asserted. */
	bool PathIsClear(const FVector& From, const TArray<FVector>& Way,
		const TArray<int32>& Allowed, FString& OutWhy) const;

	// --------------------------------------------------------------------- the world

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Board;
	TArray<FMark> Marks;
	double HeroSpeed = 500.0;
	double WalkZ = 0.0;
	double FrameDt = 1.0 / 60.0;

	/** Named by index into Marks, resolved once from the mark names the hall carries. */
	int32 IdxAsh = INDEX_NONE;
	int32 IdxBirch = INDEX_NONE;
	int32 IdxCedar = INDEX_NONE;
	int32 IdxDune = INDEX_NONE;
	/** THE IN-SCENE NEGATIVE CONTROL: the one mark NEITHER staged list ever names. */
	int32 IdxControl = INDEX_NONE;

	// -------------------------------------------------------------------- the model

	/** The list the model is working to. Replaced the frame the board's own list stops
	 *  matching it, which is what "the round starts over when the list changes" means. */
	TArray<FName> ModelList;
	/** The list the FIXTURE staged, for gate 1. */
	TArray<FName> StagedList;
	int32 Turn = 0;
	int32 PoisonedMark = INDEX_NONE;
	int32 OccupiedLast = INDEX_NONE;
	int32 BankingMark = INDEX_NONE;
	int32 StagedRound = 0;

	// -------------------------------------------------------- model-event bookkeeping

	double LastModelChangeAt = -1000.0;
	double LastCrossingAt = -1000.0;
	double StagingUntil = -1000.0;
	double LastRingExitAt = -1000.0;
	/** When the round last started over, WHATEVER the cause -- an out-of-turn step or
	 *  a new list. NEVER cleared, unlike OutOfTurnAt (which dies with the stand it
	 *  belongs to) and unlike anything scoped to one event. Gate 8's deferred check
	 *  needs it: a completion the hall was RIGHT to throw away cannot be judged, and
	 *  reading OutOfTurnAt there would mean a character who stepped off before the
	 *  check landed made the wipe invisible to it -- a false FAIL on a correct
	 *  submission. */
	double RoundStartedOverAt = -1000.0;

	/** Gates 2 + 3: the most recent out-of-turn entry.
	 *
	 *  CLEARED WHEREVER PoisonedMark IS. Both gates are claims about THE STAND that
	 *  the out-of-turn step began -- "for as long as they remain on it, this mark
	 *  banks nothing" -- so a stand that has ended cannot keep them armed. Leaving
	 *  this set past the step-off left both gates permanently armed on the last mark
	 *  anybody ever stepped onto out of turn, which (a) false-FAILed every later
	 *  LEGITIMATE stand on that same mark, including the reference's, and (b) made
	 *  AnyWindowArmed permanently true there, silently un-grading the per-mark face
	 *  channel and the tally for the whole of those stands. */
	double OutOfTurnAt = -1000.0;
	int32 OutOfTurnMark = INDEX_NONE;
	/** Which HALF of the out-of-turn rule that entry exercised: true when the mark
	 *  stepped onto sits LATER in the list and has never been the current one (a skip
	 *  ahead), false when it is one already finished. The rule has both halves and the
	 *  run-level gate demands both, twice: a submission that only treats an
	 *  already-finished mark as out of turn is a locally reasonable wrong answer, and
	 *  it is invisible to a drive that only ever steps backwards. */
	bool bOutOfTurnAhead = false;
	int32 OutOfTurnDisplacedTurn = 0;
	int32 OutOfTurnCount = 0;
	int32 WrongStepJudged = 0;
	int32 OutOfTurnJudged = 0;
	int32 SkipAheadCount = 0;
	int32 SkipAheadJudged = 0;
	int32 FinishedStepCount = 0;
	int32 FinishedStepJudged = 0;

	/** Gate 4: the most recent list replacement. */
	double ListChangedAt = -1000.0;
	int32 ListChangeCount = 0;
	int32 ListChangeJudged = 0;

	/** Gates 5 + 6: the most recent re-entry onto the current mark carrying a bank
	 *  worth preserving. */
	double ReEntryAt = -1000.0;
	int32 ReEntryMark = INDEX_NONE;
	double ReEntryPreserved = 0.0;
	int32 ReEntryCount = 0;
	int32 StillThereJudged = 0;
	int32 PicksUpJudged = 0;

	/** Gate 7: the off-mark wait in progress. */
	double AwaySinceAt = -1000.0;
	int32 AwayMark = INDEX_NONE;
	bool bAwayArmed = false;
	bool bAwaySampled = false;
	TArray<double> AwaySampleFace;
	int32 AwayCount = 0;
	int32 AwayJudged = 0;

	/** Gate 8: completions still owing their deferred check. */
	struct FCompletion
	{
		int32 Mark = INDEX_NONE;
		double At = 0.0;
		double RequiredThen = 0.0;
		int32 FinishedAfter = 0;
		bool bChecked = false;
		/** True when NOBODY was standing in any ring at the instant this mark
		 *  finished -- the fixture dropped its number below what it had already
		 *  banked while the character was parked. A finish test nested inside
		 *  "somebody is standing here and banking" cannot produce this one at all,
		 *  and it is the only thing that separates the two. */
		bool bNobodyStanding = false;
	};
	TArray<FCompletion> Completions;
	int32 CompletionJudged = 0;
	int32 AwayCompletionCount = 0;
	int32 AwayCompletionJudged = 0;

	/** Gate 9: the control's crossings, and the tally the hall showed when each began. */
	int32 ControlCrossings = 0;
	bool bControlWatchOpen = false;
	int32 ControlWatchTally = 0;
	int32 ControlWatchLength = 0;
	double ControlWatchClosesAt = -1000.0;
	bool bControlWatchModelMoved = false;

	/** Gate 13: what the HALL showed, not what the model did. */
	bool bShownFullRoundOne = false;
	bool bShownZeroBetween = false;
	bool bShownFullRoundTwo = false;
	int32 ShownFullLengthOne = 0;
	int32 ShownFullLengthTwo = 0;

	// --------------------------------------------------------------------- the route

	FVector Park = FVector::ZeroVector;

	// ---------------------------------------------------------------------- stepping

	int32 Step = 0;
	FString StepLabel;
	double StepStartedAt = 0.0;
	double StepDeadline = 0.0;
	TArray<FVector> Waypoints;
	int32 WaypointIndex = 0;
	TArray<int32> MayCross;
	/** The mark this step ends standing on, and what "done" means for it. */
	int32 StandOn = INDEX_NONE;
	double StandUntilBank = -1.0;
	bool bStandUntilFinished = false;
	int32 StandUntilFinishedCount = -1;
	double DwellS = -1.0;
	double AwayForS = -1.0;
	double OutOfTurnForS = -1.0;
	/** The one staged rewrite this step is allowed to fire. */
	int32 RewriteMark = INDEX_NONE;
	double RewriteTo = 0.0;
	double RewriteAtBank = -1.0;
	bool bRewriteFired = false;
	/** THE DROP THAT LANDS WITH NOBODY IN ANY RING. The ordinary rewrite fires
	 *  mid-stand; this one waits until the character has walked clear of every ring
	 *  and the off-mark wait has already been sampled, and then drops the CURRENT
	 *  mark's number below what it has already banked. The mark has to finish at
	 *  once with nobody moving, which no finish test nested inside the banking step
	 *  can ever do. */
	bool bRewriteWhileAway = false;
	bool bShiftChangeStep = false;
	bool bShiftChangeFired = false;
	/** THE SAME-LENGTH REORDER. The board takes the same names, the same number of
	 *  names and the same seconds, in a different order and with the same first
	 *  name -- so a change detector that compares lengths, or the first name, or the
	 *  SET of names, cannot see it at all. Fired while the character is parked. */
	bool bReorderStep = false;
	bool bReorderFired = false;
	/** When this step's staged event actually landed, and how long the step holds
	 *  afterwards. Measured from the EVENT and not from the step's start, because
	 *  these steps carry a long walk first and a dwell measured from the start would
	 *  be a wall-clock guess about how fast the character got there. */
	double EventFiredAt = -1000.0;
	double HoldAfterEventS = -1.0;

	bool bPrepared = false;
	bool bGatesArmed = false;
	bool bBaselineStep = false;
	bool bDriveComplete = false;
	double DriveCompletedAt = -1.0;
	bool bRunLevelDone = false;
	int32 NextEarlyCalib = 0;
};
