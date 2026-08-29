// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-the-round-number-everyone-agrees-on.
//
// The hall is walked once, on a nineteen-stop script. Along the way the runner steps
// onto the mark in the middle of the room five times, onto the hoist plate twice, and
// into the sinkhole twice. What is graded is what the SIGNS PRINT at each of those
// moments -- never a member the submission holds, and never a call the submission could
// make instead of doing the work.
//
// EVERY NUMBER THE RUN TURNS ON IS STAGED BEFORE ANY BeginPlay and differs from what
// the committed .umap holds, so a submission that reads the level file, or hard-codes
// the corpus's own "starts at 1, advances by 1", is wrong at the FIRST judged frame.
// One of the three (the mark's step) is re-staged mid-run with nobody standing on it,
// so a step read once and remembered is wrong from the third advance on.
//
// FIVE THINGS ABOUT THE PREDICATES, because getting any of them backwards either makes
// the task unwinnable or hands a wrong answer a way out:
//
//  (1) ENTRIES ONTO THE MARK ARE COUNTED OFF THE CAPSULE, not off the mark's
//      announcement. The union of (the mark's own overlap set) and (its box grown by
//      capsule radius + half height + margin) is a strict superset of what the prop can
//      see, so the fixture's window opens EARLIER than the prop can fire and never
//      later. A submission that suppresses, re-broadcasts or re-plumbs the mark's
//      announcement is graded against the walk that actually happened.
//  (2) THE AGREEMENT GATE STANDS OFF LONGER THAN THE STEP GATE'S DEADLINE. Both gates
//      catch a cached step; only one of them NAMES it. kAgreeSuppressS > kRiseDeadlineS
//      is what makes EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries the gate
//      that speaks first for that answer. Same reason across a fall: the agreement gate
//      stands off for kFallSuppressS, which is longer than the body gates' own
//      kBodyJudgeS, so a number that did not survive the fall is named by
//      TheNumberSurvivesANewRunner rather than laundered into a disagreement.
//  (3) A BLANK HALL SIGN IS NOT A ZERO. Parsing yields "no number", which FAILS. Reading
//      blank as 0 would be a permissive fake the moment a wrong answer's value was 0.
//  (4) THE FIXTURE HOLDS ITS OWN INPUT for the whole judging window after each fall.
//      Without that it would be walking the fresh body away from the entrance mark while
//      measuring how far from it that body is -- i.e. measuring its own drive, at up to
//      500 uu/s against a 150 uu tolerance.
//  (5) THE SUPPLIED HALL IS INCLUDED, NOT REFLECTED. RoundHallProps.h lives in the
//      agent-writable module, so a submission that deletes or renames it breaks THIS
//      module's compile and takes a GRADED L1 FAIL. That is deliberate: resolving the
//      props by property name instead would turn the same edit into "no actor carries
//      the tag" -> HARNESS-PRECONDITION, i.e. a denominator opt-out available to any
//      submission willing to delete one file. Ambiguity resolves toward GRADED.
//
// The nine named gates, and what fails each one:
//
//   EverySignInTheHallShowsTheNumberTheHallIsOn   a submission that prints nothing (the
//       empty leg, at t = 2 s), or whose signs disagree, or that lets a hall sign go
//       blank, or that destroys one rather than keep it up to date.
//   TheNewSignComesUpOnTheNumberTheHallIsOn       a readout population captured once at
//       BeginPlay: the sign the hoist raises at round 8 is not in the set, is never
//       written to, and stays blank. The second hoist runs AFTER the second fall with no
//       advance in between, so it asks the same question of a number that has survived a
//       re-body -- which the first hoist cannot ask.
//   TheDoorplateShowsTheRoundTheRunnerWalkedInOn  THE CROSSING POINT of the two halves:
//       its value is the hall's number SAMPLED AT A BODY CHANGE, so neither half alone
//       produces it. A submission that owns the number perfectly but never notices that
//       the body changed fails here and nowhere else; one that re-bodies perfectly but
//       keeps the number on the body fails here as well as on the fall gate; one that
//       writes the hall's current round onto it, like a hall sign, fails at the first
//       advance; one that writes it once at the start fails after the first fall.
//   EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries   a step cached at BeginPlay
//       (10 where 11 is wanted), a rise that repeats while the runner stands still, a
//       rise that never comes, a number that moves with nobody on the mark.
//   TheNumberSurvivesANewRunner                   the number kept on the body that walks
//       around: the sinkhole destroys it and the hall comes back on 4 instead of 11.
//   ANewRunnerOfTheSameKindStandsOnTheEntranceMark  a one-shot re-body latch (passes the
//       first fall, has nobody alive at the second), two runners at once, a hand-rolled
//       body of some other kind, a body nobody controls, a body put somewhere else.
//   TheRelicKeepsItsOwnNumber                     THE IN-SCENE CONTROL: a submission that
//       prints the round number onto every sign in the world fails at the first advance.
//   TheHallKeepsWhatWasGivenToIt                  rewriting the mark's step or repainting
//       the stone so the arithmetic comes out; moving a fitting; breaking the hoist or
//       the hole the hall was given working.
//   TheRunnerCouldNotGetWhereHeWasGoing           DRIVE FAULT as a NAMED GRADED FAIL: no
//       live controlled body to steer, a body the player does not actually control, or a
//       runner put back somewhere it cannot walk out of.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "RoundHallFunctionalTest.generated.h"

class ACharacter;
class AEntranceStoneActor;
class AHallSignActor;
class AHoistPlateActor;
class APawn;
class ASinkholeActor;
class AStepMarkActor;
class UBoxComponent;
struct FActorsInitializedParams;

UCLASS()
class ARoundHallFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ARoundHallFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	/** Where the drive is going and what it is there for. */
	enum class EStopKind : uint8
	{
		Settle,    // stand still where you are
		Mark,      // the mark in the middle of the room
		Hoist,     // the hoist plate
		Hole,      // the sinkhole; ended by the fall, not by the dwell
		Clear,     // the lane point beside the last thing, i.e. step OFF it
		Restage,   // the lane point, and the fixture rewrites the mark's step here
		Finish
	};

	struct FStop
	{
		EStopKind Kind = EStopKind::Settle;
		FVector Where = FVector::ZeroVector;
		double DwellS = 0.0;
	};

	/** One sign, placed or raised. Raised ones join the population at run time, which is
	 *  the whole point of the hoist: a design that captures the readers once at
	 *  BeginPlay is wrong only from the moment the set changes. */
	struct FSign
	{
		TWeakObjectPtr<AHallSignActor> Actor;
		FString Label;
		bool bPlaced = false;
		bool bFromTheHoist = false;
		double AppearedAt = 0.0;
		int32 RaisedOnNumber = 0;
		bool bLateWindowOpen = false;   // closed by the next advance
	};

	/** A fitting the hall was given, and where it was given. */
	struct FFitting
	{
		TWeakObjectPtr<AActor> Actor;
		FString Label;
		FVector At = FVector::ZeroVector;
	};

	// -- staging ------------------------------------------------------------
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	bool StageTheNumbers();
	bool ResolveStaging();
	bool CheckTheStagedTriple();
	bool CheckTheRoutes();
	bool CheckTheLevelCanBePlayed();
	bool BuildScript();

	// -- geometry -----------------------------------------------------------
	FVector HeroAt() const;
	bool InVolume(const UBoxComponent* Box, const FVector& P, bool bGrow) const;
	bool InsideTrigger(const UBoxComponent* Box) const;
	static double DistToVolume(const UBoxComponent* Box, const FVector& P);

	// -- reads, all of them what somebody in the room would read ------------
	static int32 FirstWholeNumber(const FString& In, bool& bOk);
	int32 ReadSign(const AHallSignActor* S, bool& bOk) const;
	/** The number the hall's signs agree on. False when one of them is blank, is not a
	 *  number, or disagrees with another. Signs raised inside the last kRaiseSuppressS
	 *  are left out: they have their own gate and their own grace. */
	bool ReadHallNumber(double Now, int32& Out, FString& Detail) const;
	FString SignReadout(double Now) const;

	// -- housekeeping -------------------------------------------------------
	void RefreshSigns(double Now);
	void NoteAdvance(double Now, int32 Step);
	void ObserveMark(double Now);
	void ObserveFall(double Now);
	void DoTheRestage(double Now);

	// -- the gates ----------------------------------------------------------
	bool GateTheRelic(double Now);
	bool GateTheHall(double Now);
	bool GateTheStep(double Now);
	bool GateTheFall(double Now);
	bool GateTheBody(double Now);
	bool GateTheLateSign(double Now);
	bool GateTheDoorplate(double Now);
	bool GateEverybodyAgrees(double Now, bool bIgnoreSuppression);
	void FinalGrade(double Now);

	// -- drive --------------------------------------------------------------
	void BuildTransits(double Now);
	void AdvanceStop(double Now);
	void DriveRunner(double Now);
	void LogCalib(int32 Index, double Now) const;

	// -- verdicts -----------------------------------------------------------
	void Fail(const FString& Message);
	void Precondition(const FString& Message);

	// -- staged world -------------------------------------------------------
	TWeakObjectPtr<AEntranceStoneActor> Stone;
	TWeakObjectPtr<AStepMarkActor> Mark;
	TWeakObjectPtr<AHoistPlateActor> Hoist;
	TWeakObjectPtr<ASinkholeActor> Hole;
	TWeakObjectPtr<AHallSignActor> Relic;
	TWeakObjectPtr<ACharacter> Hero;
	TArray<FSign> Signs;
	TArray<FFitting> Fittings;

	/** The kind of runner the visit began with, and the body that is walking now. */
	TWeakObjectPtr<UClass> OpeningRunnerClass;
	FName OpeningRunnerClassName;
	FName BodyName;

	FDelegateHandle WorldInitHandle;
	bool bNumbersStaged = false;
	bool bNumbersWritten = false;
	bool bStaged = false;
	bool bGraded = false;

	/** THE CAST AND THE COUNT ARE TAKEN BEFORE ANY BeginPlay, and that is a verdict
	 *  decision rather than tidiness. Read in PrepareTest instead, the same two checks
	 *  would read a world the submission's own BeginPlay has already touched -- and a
	 *  submission that spawned one extra actor tagged HallSign would then take a
	 *  HARNESS-PRECONDITION non-verdict rather than a graded result, which is a
	 *  denominator opt-out needing no correct work at all. Taken pre-BeginPlay they say
	 *  exactly what they are meant to say: what the LEVEL shipped. Anything that appears
	 *  later is simply another sign the hall's number has to reach, and RefreshSigns
	 *  finds it like any other. */
	FString StagingFault;
	int32 StagedRelics = 0;

	// -- the staged numbers -------------------------------------------------
	int32 StagedStart = 0;
	int32 StagedStepFirst = 0;
	int32 StagedStepAfterRestage = 0;
	int32 StagedStepNow = 0;
	int32 StagedRelic = 0;
	bool bRestaged = false;

	// -- the fixture's own model of the rule --------------------------------
	int32 ModelNumber = 0;
	double ModelChangedAt = -1000.0;
	int32 LastGoodNumber = 0;
	bool bHaveGoodNumber = false;

	// -- the doorplate: the hall's number SAMPLED AT A BODY CHANGE ----------
	// This is the one value in the run that neither half of the task produces on its
	// own. DoorModel moves only when the body walking in the hall becomes a different
	// object, and it takes whatever the hall's number is at that instant.
	int32 DoorModel = 0;
	double DoorChangedAt = -1000.0;
	int32 DoorEpochs = 0;
	FName DoorBodyName;

	// -- entries onto the mark ----------------------------------------------
	bool bOnTheMark = false;
	bool bEntryOpen = false;
	bool bEntryJudged = false;
	double EntryAt = -1000.0;
	int32 EntriesSeen = 0;
	int32 StepAtEntry = 0;
	int32 NumberBeforeEntry = 0;

	// -- falls ---------------------------------------------------------------
	int32 FallsSeen = 0;
	int32 RunnersLostSeen = 0;
	int32 FallsJudged = 0;
	bool bInFallWindow = false;
	bool bFallJudged = false;
	bool bHoldingInput = false;
	double FallAt = -1000.0;
	int32 NumberBeforeFall = 0;
	FName BodyBeforeFallName;
	bool bAwaitAdvanceAfterFall = false;

	// -- the hoist and the hole, and whether they still work ------------------
	int32 SignsRaisedSeen = 0;
	double InsideHoistSince = -1.0;
	double InsideHoleSince = -1.0;
	int32 HoistCountAtEnter = 0;
	int32 LostCountAtEnter = 0;

	// -- drive state ---------------------------------------------------------
	TArray<FStop> Script;
	int32 StopIndex = 0;
	TArray<FVector> Transits;
	int32 TransitIndex = 0;
	double DwellUntil = -1.0;
	double LegDeadline = -1.0;
	double LaneY = 0.0;
};
