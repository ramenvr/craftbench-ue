// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AWingHostFunctionalTest -- L2 fixture for t2-only-the-wing-you-called-opens.
// Runs in Content/Maps/t2-only-the-wing-you-called-opens/L_WingHost.umap.
//
// THE HOST IN ONE PARAGRAPH. Four wings hang off one host building. The HALL is in the
// running world from the first frame and no mark ever calls it. ROSE, GOLD and SLATE
// start out of the world; three call marks in the host floor each show one wing's name,
// and walking onto a mark has to bring ALL of that wing's fittings into the host and
// take the previously called wing's back out, inside the window the prompt promises,
// with the board over the gate naming what stands AND HOW MANY. GAMMA always shows
// SLATE and is never stepped on, so slate exists only ever as a wing nobody called.
//
// TWO THINGS ARE DELIBERATELY UNGUESSABLE, and both have to be read off the world at
// the moment they are needed:
//   1. WHICH WING A MARK CALLS. Re-dealt mid-run, and mirrored between the two
//      framerate legs, so a hard-coded pairing is wrong at cp1 of one of them.
//   2. HOW BIG A WING IS. The four wings hold 3 / 4 / 6 / 4 fittings (kWingFittings),
//      none of which is printed in the prompt, and the section a wing's fittings live
//      in is NOT named after the wing (kSectionIds) -- so neither the join nor the
//      count can be transcribed, concatenated or assumed. Both are coupled to (1):
//      the board's number is the count of the wing the mark was showing at the step.
//
// ============================ WHAT THIS FIXTURE MEASURES ============================
//
// NOTHING HERE READS A STREAMING OBJECT AS AN ANSWER. Every gate is a statement about
// actors standing in the host world and about the text on the board. A submission that
// got the right tagged, visible, solid fittings into and out of the host by some other
// means is correct by the prompt's own words and passes here. The only place a
// ULevelStreaming is touched at all is the PrepareTest staging check, which asks about
// the LEVEL (does the section exist, is it independently unloadable) and never about
// the answer.
//
// IDENTITY IS THE PER-INSTANCE TAG, NEVER A UPROPERTY. AWingFittingActor lives in the
// agent-writable module, so every property on it is a value the submission controls --
// WingLabel included, and this fixture never reads it. A fitting is identified by the
// Fitting.<WING>.<N> tag baked into its committed wing package. The obvious tamper (add
// a tag in the constructor) lands on all seventeen fittings at once and fails
// OnlyCalledWingPresent immediately.
//
// THE FIXTURE GRADES AGAINST WHAT IT DEALT, NEVER AGAINST WHAT IT READS BACK. The
// mark's live label and the fixture's own deal table are the same fact right up until a
// submission writes one of them; the moment they part company the deal table is the one
// that counts. Reading the mark back at the step would let a submission that re-letters
// every mark to ROSE agree with itself and pass.
//
// ================================ THE TWO LEGS =====================================
//
// fps_legs: [60, 20]. The two legs run MIRRORED deals, keyed off the leg's own FIXED
// DELTA TIME (FApp::GetFixedDeltaTime(), which the runner's -FPS sets in
// LaunchEngineLoop.cpp:4727) -- never wall clock, never randomness, so the same input
// gives the same deal every run. The consequence is the point: a HARD-CODED mark->wing
// pairing is wrong at the FIRST gauge point of one of the two legs, and both legs have
// to pass. A pairing CACHED AT BeginPlay is right at cp1..cp3r and wrong at cp4, where
// the same physical plate demands a different wing after the mid-run re-deal.
//
// THE MIRROR CARRIES THE COUNT TOO. Because the wings are different sizes, cp1 wants
// ROSE's four on the fast leg and GOLD's six on the slow one -- so a board that prints
// any CONSTANT number fails at cp1 or cp2 on BOTH legs, and a board that prints the
// count it had at the instant of the step prints the count of a wing that has not
// arrived yet. The readout is load-bearing rather than decorative for that reason.
//
// ============================ HOW THE DRIVE CANNOT LIE ==============================
//
// This repo has failed correct answers with turns, acceleration ramps and over-wide
// settle windows. Four deliberate choices here, each widening only in the direction
// that cannot manufacture a FAIL:
//
//   1. EVERY LEG IS STRAIGHT. The three marks sit in a row and the clear spot sits
//      square below ALPHA, so no walk is ever a curve and no walk passes within 900 uu
//      of a mark it is not aiming at.
//   2. THE APPROACH RAMPS DOWN. Movement input is scaled down inside 800 and 350 uu of
//      the target so the character arrives slowly; at full pace the 2000 uu/s^2 braking
//      deceleration would carry it 62 cm past the stop point and off the 220 cm plate.
//   3. THE STEP IS REGISTERED LATE, NEVER EARLY. The fixture calls the step landed at
//      45 uu from the mark's centre. The ENGINE's own begin-overlap fires at about 152
//      uu (110 uu box half-extent + 42 uu capsule radius), so the submission is always
//      notified BEFORE the fixture starts the one-second clock and can never be given
//      less than the second the prompt promised.
//   4. EVERY GAUGE POINT IS DERIVED FROM ITS OWN EVENT, never from a wall-clock
//      schedule: the settle window opens when the step lands, and the mid-run re-deal
//      fires after cp3 has been sampled and while the character overlaps no mark. A leg
//      that walks the same distance in a different number of frames cannot shift a gate
//      off its subject.
//
// The checkpoint schedule handed to SetCheckpointSchedule is a DENSE CALIBRATION GRID
// plus a SENTINEL far past the modelled drive, because ACraftBenchFunctionalTest::Tick
// ends the test the moment the last scheduled checkpoint is sampled. The fixture
// finishes itself as soon as its last phase completes.
//
// ======================= WHAT IS ATTRIBUTED AND WHAT IS GRADED ======================
//
// BeginPlay fires on every placed actor BEFORE PrepareTest, so "whatever the world
// looked like when the fixture first opened its eyes" is already downstream of the
// submission and can never be an attributed baseline. The line is drawn by one
// question: IS THE FIXTURE'S OWN EXPECTED VALUE SATISFIABLE BY ANY WORLD?
//
//   ATTRIBUTED (HARNESS-PRECONDITION) -- authoring faults only, i.e. no C++ a
//   submission can write changes them: no world; no possessed player character; a level
//   that cannot be driven by hand (the unplayable-input check, by property name); a
//   SectionId in THIS FIXTURE'S table naming no section the persistent level declares;
//   two sections declaring the same package; a section that is not independently
//   unloadable (a ULevelStreamingAlwaysLoaded hall would make SealedWingUntouched an
//   unfailable dead gate and the whole coupling a permissive fake).
//
//   GRADED -- everything else. Wrong actor counts, a moved or renamed mark, post or
//   board, a mark showing something other than what the fixture last dealt it, a
//   missing hall fitting: all of these are things a submission CAN cause, so all of
//   them are named FAILs. A staging exit a submission can trigger is a denominator
//   opt-out that costs the model nothing to buy.
//
//   DELIBERATE DEVIATION FROM task.md, documented rather than hidden: task.md lists "a
//   per-instance fitting tag missing or duplicated inside a committed wing package" as
//   an attributed authoring fault. It cannot be one HERE -- three of the four wings are
//   out of the world at PrepareTest, so their tags are unobservable until after the
//   submission has had a turn. Tags are therefore GRADED (OnlyCalledWingPresent /
//   SealedWingUntouched) and the authoring-fault gate for them lives where it can
//   actually be submission-proof: authoring/author_map.py refuses to save a level whose
//   seventeen tags do not read back after a load from disk.
//
// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. Before any deadline or sentinel overrun is
// written off, OnlyCalledWingPresent and SealedWingUntouched are re-checked
// UNCONDITIONALLY at the last gauge state reached -- those two are the gates a
// submission can trip while also stalling the drive (a fitting standing where it should
// not be is solid, and solid things block a walk).
//
// ============================ THE LAYOUT IS A SHARED TABLE ==========================
//
// kHallFittingAt / kMarkAt / kPostAt / kBoardAt below are the SAME NUMBERS
// authoring/author_map.py places. They are graded (SealedWingUntouched), so the two
// tables must never drift; the authoring script asserts its own read-back against them
// before it saves, which is what keeps an authoring change from presenting as a model
// failure.
//
// All FAIL text is ASCII-only (the cp1252 log read-back rule).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "WingHostFunctionalTest.generated.h"

class ACharacter;
class UStaticMeshComponent;
class UTextRenderComponent;

/** The eight points at which every gate is evaluated.
 *  cp3r is the RE-LETTER gauge: one settle window after the marks are re-lettered,
 *  with the character standing on nothing, and its expectation is cp3's UNCHANGED --
 *  re-lettering a mark is not a call.
 *  cp6 is the SAME-MARK RE-STEP: BETA again, un-re-lettered since cp5, so the step
 *  calls the wing that is already standing and the demanded outcome is cp5's,
 *  UNCHANGED. It is the only gauge point at which a take-down and a bring-in issued
 *  against one shared handle can present. */
UENUM()
enum class EWingGauge : uint8
{
	Cp0,
	Cp1,
	Cp2,
	Cp3,
	Cp3r,
	Cp4,
	Cp5,
	Cp6,
	Count,
};

/** The drive. Every walk is a straight leg; every stand ends on its own event. */
UENUM()
enum class EWingPhase : uint8
{
	Settle,
	ToAlpha1,
	StandAlpha1,
	ToBeta1,
	StandBeta1,
	ToAlpha2,
	StandAlpha2,
	ToClear,
	Reletter,
	ToAlpha3,
	StandAlpha3,
	ToBeta2,
	StandBeta2,
	ToStepOff,
	ToBeta3,
	StandBeta3,
	Done,
};

UCLASS()
class CRAFTBENCHTESTS_API AWingHostFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AWingHostFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	// ------------------------------------------------------------------ staging

	/** Empty when a human could pick up a controller and drive this level; otherwise
	 *  the reason they cannot. Read by PROPERTY NAME so a renamed or subclassed pawn
	 *  still answers. Nothing in the graded drive depends on the keyboard lane, so
	 *  without this the level is free to ship visible, animated and uncontrollable. */
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	/** The four sections named in THIS fixture's table must each resolve to a distinct
	 *  streaming section that the world can take back out. Authoring faults only --
	 *  see the header. False after raising the attributed exit. */
	bool CheckSectionsAreStagedForStreaming(UWorld* World);

	/** Resolve the marks, the posts and the board by tag and match them to the layout
	 *  table by position. False after raising the attributed exit (only for things no
	 *  submission can cause); a submission-caused mismatch is left for the gates. */
	bool ResolveHostFurniture(UWorld* World);

	// -------------------------------------------------------------- the deal

	/** Deal the three marks their labels for this leg and record what was dealt.
	 *  Prefers the supplied SetCalledWingName UFUNCTION (so the floating label a human
	 *  reads repaints, and so a submission that overrode it sees exactly what a human
	 *  re-lettering the mark would produce) and falls back to writing the FName
	 *  property directly when that function is gone. */
	void DealMarks(int32 DealIndex);

	// ------------------------------------------------------------ the observables

	/** One reading of every fitting standing in the host world, keyed by the
	 *  per-instance tag baked into its committed wing package. */
	struct FStandingFittings
	{
		/** Fitting.<WING>.<N> -> how many actors carry it (duplicates are a failure). */
		TMap<FName, int32> CountByTag;
		/** The first actor found for each tag, for the solid-and-seen read. */
		TMap<FName, TWeakObjectPtr<AActor>> ActorByTag;
		/** Fittings carrying no Fitting.* tag at all, or more than one. */
		int32 Unidentified = 0;
	};
	FStandingFittings ReadStanding() const;

	/** The multiset the host SHOULD hold at a gauge point: the hall's three, plus (from
	 *  cp1 onward) the currently-expected wing's three. */
	TArray<FName> ExpectedTagsAt(EWingGauge Gauge) const;

	/** Sorted, comma-joined, for the failure messages. */
	static FString DescribeTags(const TArray<FName>& Tags);
	static FString DescribeStanding(const FStandingFittings& Standing);

	/** Is this fitting one a person would see and could walk into? OutWhy is filled
	 *  with the first reason it is not. */
	bool FittingIsSolidAndSeen(const AActor* Fitting, FString& OutWhy) const;

	/** The board's RENDERED text, read off the text component, never off a flag.
	 *  Prefers the component named "Line"; else the only one; else the largest by world
	 *  size, ties broken by name ascending -- never enumeration order. */
	FString ReadBoardLine() const;

	// -------------------------------------------------------------- the gates

	/** Runs the five gates in the precedence order task.md fixes. False after a FAIL
	 *  has been raised by name. */
	bool Gauge(EWingGauge Gauge, double Now);

	bool GateCalledWingOpens(EWingGauge Gauge, const FStandingFittings& Standing);
	bool GateOnlyCalledWingPresent(EWingGauge Gauge, const FStandingFittings& Standing);
	bool GateSealedWingUntouched(EWingGauge Gauge, const FStandingFittings& Standing);
	bool GateOpenWingIsSolidAndSeen(EWingGauge Gauge, const FStandingFittings& Standing);
	bool GateBoardNamesTheOpenWing(EWingGauge Gauge, const FStandingFittings& Standing);

	/** The gates a submission can trip WHILE stalling the drive, re-checked before any
	 *  deadline or sentinel overrun is written off as ours -- in the one form that
	 *  cannot itself invent a FAIL. SealedWingUntouched is expectation-independent and
	 *  is re-checked whole; the multiset is checked only for SCOPE (the hall plus the
	 *  complete set of at most one called wing, that wing being the last one gauged or
	 *  the one lettered on a mark the character is already close enough to have
	 *  triggered), because a stall can strand the character inside the window where a
	 *  CORRECT submission has already swapped and the fixture has not yet said
	 *  'landed'. */
	bool RecheckStallableGates(const TCHAR* Where);

	/** The in-scene negative control, every frame rather than only at gauge points --
	 *  SealedWingUntouched CLAUSE (a) ONLY: the hall's fittings, present and
	 *  within kHallMoveCm of where the shared layout table stands them.
	 *
	 *  CLAUSE (b), THE HOST'S FIXED FURNITURE, IS DELIBERATELY NOT RE-READ HERE. It is
	 *  gauged at cp0..cp6 and cp3r by GateSealedWingUntouched and nowhere else, which
	 *  is exactly what task.md's requirement map promises; a comment that claims the
	 *  judge checks more than it does is itself the defect, because the next reader
	 *  trusts it instead of the code.
	 *
	 *  A correct answer never touches the hall on any frame, so this can only ever
	 *  catch a wrong one -- and it is the only thing that catches a hall unloaded and
	 *  reloaded INSIDE a settle window, which every checkpoint-only sample would miss.
	 *  Armed once cp0 has been sampled. */
	bool GuardControlsContinuously();

	// -------------------------------------------------------------- the drive

	/** Straight-leg walk toward a world point, ramped down on approach. True once the
	 *  character is inside kArriveCm of it and standing on the ground. */
	bool DriveTo(const FVector& Target);
	void BeginWalk(const FVector& Target, const TCHAR* What, double Now);
	void BeginStand(EWingPhase NextPhase, int32 SteppedMark, double Now);
	double DistanceToMark(int32 MarkIndex) const;
	double NearestMarkDistance() const;
	void LogCalib(int32 CheckpointIndex, double Now) const;

	// -------------------------------------------------------------- reflection

	static FName ReadName(const AActor* A, const TCHAR* PropertyName, bool& bOk);
	static bool WriteName(AActor* A, const TCHAR* PropertyName, FName Value);
	static bool CallNameFunction(AActor* A, const TCHAR* FunctionName, FName Value);

	// ------------------------------------------------------------------ state

	TWeakObjectPtr<ACharacter> Hero;

	/** The three marks and the four posts, in the LAYOUT TABLE's order (ALPHA/BETA/
	 *  GAMMA and HALL/ROSE/GOLD/SLATE), matched to it by position at PrepareTest. A
	 *  slot left null is a graded SealedWingUntouched failure, never an attributed one. */
	TWeakObjectPtr<AActor> Marks[3];
	TWeakObjectPtr<AActor> Posts[4];
	TWeakObjectPtr<AActor> Board;

	/** Which of the two mirrored deal sets this leg runs, from the leg's fixed dt. */
	int32 LegIndex = 0;
	/** Which deal is currently on the marks (0 before the mid-run re-deal, 1 after). */
	int32 DealIndex = 0;
	/** What the fixture last dealt each mark. The grade comes from HERE, never from a
	 *  read-back of the mark. */
	FName DealtWing[3];

	/** The wing the last step called, from the fixture's own deal table, and which mark
	 *  was stepped on. NAME_None / -1 before the first step. */
	FName ExpectedWing = NAME_None;
	int32 SteppedMarkIndex = -1;

	EWingPhase Phase = EWingPhase::Settle;
	EWingGauge LastGauge = EWingGauge::Cp0;
	bool bCp0Sampled = false;
	bool bDriveComplete = false;
	bool bPrepared = false;

	/** World game-time the current step landed, and the time the marks were re-lettered
	 *  mid-run. Both are EVENTS, never clock positions. */
	double StepLandedAt = -1.0;
	double ReletteredAt = -1.0;

	/** The straight leg in progress, and the derived deadline for it. */
	FVector WalkTarget = FVector::ZeroVector;
	double PhaseDeadline = 0.0;
	FString PhaseWhat;

	/** Measured once, from the character's own movement component. */
	double HeroSpeed = 500.0;

	/** The last gauge the run actually reached, named in the stall messages. */
	FString LastGaugeName = TEXT("cp0");
};
