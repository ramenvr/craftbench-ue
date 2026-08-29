// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t3-the-yard-remembers-after-you-leave.
//
// A near yard of five numbered posts, three lamp-marked pads and a counter board, and
// a far yard of three posts and a board of its own on the other side of a solid wall.
// The fixture walks the character with AddMovementInput -- the same input path a human
// uses -- keeping a SHADOW LEDGER of what every step must do, and grades what the
// boards, the painted numbers, the pillars and the lamps actually SHOW.
//
// WHAT MAKES THIS TASK DIFFERENT FROM ITS SIBLING (t2-shop-takes-your-coins-and-
// remembers, whose spec says outright that a slot, a subsystem or a file all pass
// identically): the yard is torn down and rebuilt TWICE inside one PIE world, and the
// SECOND rebuild deletes the project's save-game directory in the same tick. After that
// deletion there is exactly one channel left that could carry the day across -- a warm
// in-memory store -- and ColdReopenForgetsEverything condemns it. That is the whole
// task: is disk the source of truth, or merely a copy of one?
//
// THREE REBUILDS, AND WHAT HAPPENS TO THE RECORD AT EACH IS A PROPERTY OF THE STAGED
// SET, not of the fixture. Every set rebuilds the yard three times and does each of
// these once, in an order that differs from set to set:
//   * WARM   -- nothing is done to the record. The yard must come back as it was.
//   * REWIND -- the record is replaced, byte for byte, with the copy this fixture took
//               a moment after the counter board first rose. The yard must then come
//               back AS IT STOOD AT THAT MOMENT: one post gone, the board carrying only
//               what had been banked by then, the runner on the pad marked then. This
//               is the gate that grades what is IN the record. Memory-plus-a-touched-
//               file cannot survive it: the file's CONTENT decides the yard, and the
//               content that comes back is older than anything in memory.
//   * COLD   -- the record is deleted. The yard must open as if never visited.
// Because the order is per-set and the set is chosen from the clock, "reset on the
// second rebuild" is a wrong answer somewhere, and there is no shape to count.
//
// THE THREE THINGS THAT ARE STAGED, never read out of the level:
//   1. Every post's painted worth, written before ANY BeginPlay through
//      FWorldDelegates::OnWorldInitializedActors (the ASanityFunctionalTest pattern),
//      and RESTAGED on the fresh posts at every rebuild. Three complete sets ship
//      here and the one in force is CHOSEN FROM THE CLOCK unless -CraftBenchYardSeed=N
//      pins it, so a discrimination leg is byte-reproducible while a graded run cannot
//      be pre-answered from a published table. The committed .umap carries different
//      numbers again.
//   2. Where everything stands. Posts and pads come back on each other's slots at every
//      rebuild, so a restore keyed on index, spawn order or world position lands on
//      the wrong prop.
//   3. The save-game directory itself, emptied before anything begins play -- MANDATORY,
//      not optional: a record written to disk survives the workdir, so without the wipe
//      the SECOND run in one workdir would open warm at t=0 and a CORRECT submission
//      would be failed for having obeyed the prompt.
//
// EVERYTHING GRADED IS READ OFF WHAT A PERSON IN THE YARD WOULD SEE: the rendered
// UTextRenderComponent::Text on every board and worth sign, the pillar's visibility,
// and the pad lamp's UPointLightComponent intensity. The actors' reflected mirrors
// (LastShownTotal / LastShownWorth / bLastShownStanding / bLastShownLit) are required
// to AGREE with what was read -- they live in files the agent may edit, so a mirror on
// its own is never evidence.
//
// Identity is by TAG (MemoryPost / MemoryPad / MemoryBoard) and by the name the prop
// carries, never by class: a submission is free to subclass or replace the scaffolds.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "MemoryYardFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class AMemoryYardFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMemoryYardFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	static constexpr int32 kNearPosts = 5;
	static constexpr int32 kFarPosts = 3;
	static constexpr int32 kPads = 3;

	/** What the posts are painted with for one round of one staged set. */
	struct FRound
	{
		int32 Near[kNearPosts];
		int32 Far[kFarPosts];
	};

	static constexpr int32 kRebuilds = 3;
	static constexpr int32 kRounds = kRebuilds + 1;
	static constexpr int32 kSteps = 14;

	/** What happens to the written record while the yard is shut. */
	enum class ERebuild : uint8
	{
		/** Nothing. The yard must come back exactly as it stood. */
		Warm,
		/** The record is replaced with the copy taken a moment after the counter board
		 *  first rose, so the yard must come back as it stood THEN -- which no amount
		 *  of memory can produce, because memory has moved on. */
		Rewind,
		/** The record is deleted. The yard must open as if never visited. */
		Cold,
	};

	/** One thing the day does. Rebuild steps carry an ERebuild in A; every other step
	 *  carries a near-post index or a pad order minus one. */
	enum class EStep : uint8
	{
		StandOnPad,
		TakePost,
		WalkThroughTakenPost,
		Rebuild,
	};

	struct FStep
	{
		EStep Kind;
		int32 A;
	};

	/** One numbered set: what the posts are painted with at the open and after each of
	 *  the three rebuilds, and the day walked in it. Post indices are into the near
	 *  yard sorted by the name each post carries, so the table never has to spell a
	 *  name and the level owns the identities. */
	struct FStagedSet
	{
		FRound Rounds[kRounds];
		FStep Script[kSteps];
	};

	/** Everything a person in the yard could read about the day so far. The fixture's
	 *  own shadow of it, simulated from the staged set -- never read back off the
	 *  submission. */
	struct FYardState
	{
		bool bTaken[kNearPosts] = { false, false, false, false, false };
		/** What each taken post was painted with AT THE MOMENT IT WAS TAKEN. Board is
		 *  always the sum of these over the taken posts -- the amount is history, and
		 *  the number over the post is news. */
		int32 WorthWhenTaken[kNearPosts] = { 0, 0, 0, 0, 0 };
		int32 Board = 0;
		/** The order painted on the marked pad; 1 before anybody has stood on one. */
		int32 MarkedPad = 1;
	};

	/** One prop as it stands right now, plus everything needed to put it back. */
	struct FProp
	{
		TWeakObjectPtr<AActor> Actor;
		FName Id = NAME_None;      // PostId / PadId; NAME_None for a board
		int32 Order = 0;           // PadOrder; unused elsewhere
		FTransform Home;           // where the fixture last put it
		UClass* Cls = nullptr;
	};

	/** One thing the walk does. */
	enum class EVisit : uint8
	{
		StandOnPad,
		TakePost,
		WalkThroughTakenPost,
	};

	/** Which named gate is graded at this visit's settled after-sample. */
	enum class EGate : uint8
	{
		None,
		SessionTallyTracksExactly,
		RetakenPostAddsNothing,
		UntakenPostStillAddsAfterReopen,
		LatestPadMovesAfterReopen,
		ColdYardTakesAgain,
	};

	struct FVisit
	{
		EVisit Kind = EVisit::TakePost;
		int32 Index = 0;           // near-post index, or pad index (PadOrder - 1)
		EGate Grade = EGate::None;
		/** Which round's numbers are painted on the props while this visit happens. */
		int32 Round = 0;
		/** DERIVED by simulating the staged set: what the post being walked into is
		 *  painted with right now, and what the counter board must read afterwards. */
		int32 Worth = 0;
		int32 BoardBefore = 0;
		int32 BoardAfter = 0;
		/** True for the visit whose settled after-sample is when the fixture takes its
		 *  copy of the written record. Exactly one visit per day carries it: the first
		 *  post walked into, i.e. the moment the counter board first rises. */
		bool bSnapshotAfter = false;
	};

	/** One rebuild, and everything a gate needs to say what the yard must show and why
	 *  every plausible wrong answer is a different number. All DERIVED. */
	struct FReopen
	{
		ERebuild Kind = ERebuild::Warm;
		/** The state the yard must come back in, and the one it was in when it shut. */
		FYardState Expect;
		FYardState Was;
		/** Which round is painted on the fresh props. */
		int32 Round = 0;
		/** The total a solution would show if it re-derived it from the taken posts'
		 *  freshly painted numbers, the sum of all five fresh numbers, and how many
		 *  posts the record says are gone. None of the three may equal Expect.Board. */
		int32 RecomputeTotal = 0;
		int32 AllFiveTotal = 0;
		int32 TakenCount = 0;
	};

	/** One waypoint of the walk. */
	struct FLeg
	{
		FVector Target = FVector::ZeroVector;
		double Dwell = 0.0;
		/** 0 = on the lane before the visit, 1 = on the thing itself, 2 = back on the
		 *  lane after it, 3 = out through the gate, 4 = back to the lane after the
		 *  yard set the runner down on a pad. */
		int32 Kind = 3;
		int32 Visit = INDEX_NONE;
	};

	/** What one post is showing right now. */
	struct FPostRead
	{
		FName Id = NAME_None;
		// Always true on a successful read: a post that is no longer IN the world at
		// all is a scored TheYardsOwnPropsAreStillThere failure, not a reading of
		// "gone". Being taken hides the pillar and the number and leaves the ground.
		bool bPresent = false;
		bool bStanding = false;
		int32 ShownWorth = 0;
	};

	/** What one pad is showing right now. */
	struct FPadRead
	{
		FName Id = NAME_None;
		int32 Order = 0;
		bool bLit = false;
		FVector Loc = FVector::ZeroVector;
	};

	/** What a person standing in the yards would read off them. */
	struct FWorldRead
	{
		int32 NearBoard = 0;
		int32 FarBoard = 0;
		FString NearBoardText;
		FPostRead Near[kNearPosts];
		FPostRead Far[kFarPosts];
		FPadRead Pad[kPads];
	};

	// ---- staging -------------------------------------------------------------
	void ChooseSet();
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	/** Empties the project's save-game directory. Called before any BeginPlay, and
	 *  again -- in the same tick as the second rebuild -- to take the day's written
	 *  record away while the yard is shut.
	 *
	 *  bRecordEmptiness: on the FIRST call only, remember whether the directory was
	 *  actually gone afterwards. Read once, by ProbeOpening, to decide whether a yard
	 *  that did not open on the staged numbers is the WORKDIR's fault (an attributed
	 *  Error) or the submission's (a scored FAIL). Recorded at wipe time on purpose:
	 *  nothing has begun play yet, so the answer is purely about the wipe and cannot
	 *  be confused with a record the submission itself wrote during the run. */
	void WipeDurableStores(bool bRecordEmptiness);
	/** Copies every byte the project's save-game directory holds right now INTO MEMORY.
	 *  In memory on purpose: a copy left anywhere on disk is a copy a submission could
	 *  find, and the whole point is that the only thing carrying the day forward is the
	 *  submission's own record. Taken once per run, a moment after the counter board
	 *  first rises -- a moment the prompt discloses. */
	void SnapshotDurableStores();
	/** Puts that copy back, byte for byte, in place of whatever the record has since
	 *  become. Never opens a file and never asks what is in one; it hands the
	 *  submission back its own earlier bytes and requires the yard to open on them. */
	void RestoreDurableStores();
	FString DurableStoreDir() const;
	bool ResolveYards(bool bFirstOpen);
	bool ResolveHero();
	/** Writes one round's numbers onto the props that are standing right now. Only
	 *  ever used for the OPENING round; the rebuilds write the numbers onto the fresh
	 *  actors before their BeginPlay runs. */
	void StageRound(const FRound& Round);
	const FRound& RoundFor(int32 Reopen) const;
	bool BuildDayTrace();

	// ---- reading the yards ---------------------------------------------------
	/** NOT const: it records, in ReadFailGate, whether the thing it could not read is a
	 *  prop that has been removed from the world -- a different gate's business. */
	bool ReadWorld(FWorldRead& Out, FString& Why);
	/** The yard did not open on the numbers the fixture staged. WHOSE FAULT THAT IS
	 *  depends on bDurableStoreEmptyAtOpen: a store the wipe could not empty makes it
	 *  the WORKDIR's (an attributed Error), a store verifiably gone makes it the
	 *  submission's (a scored FAIL under SessionTallyTracksExactly, since with nothing
	 *  written down anywhere only the submission's own BeginPlay can have repainted or
	 *  hidden a post). Returns false having finished the test. */
	bool ProbeOpening(const FWorldRead& Now);
	/** The gate a readout failure is attributed to while a given visit is in flight. */
	static const TCHAR* GateName(EGate Gate);
	/** The three readings taken at every reopening. */
	enum class EClaim : uint8
	{
		Posts,
		Board,
		Placement,
	};
	/** The gate name a rebuild of this kind grades that claim under. */
	static const TCHAR* ReopenGateName(ERebuild Kind, EClaim Claim);
	/** The sentence that explains, in the yard's own terms, what this kind of reopening
	 *  was supposed to have done to the written record. */
	static const TCHAR* ReopenBecause(ERebuild Kind);
	/** THE ONE place that formats "<gate>: <reason>". Kept to a single call site so
	 *  that every scored message begins with its own gate's name by construction, and
	 *  so tasklint's fixture-fail-unique rule -- which compares SOURCE literals, not
	 *  emitted text -- sees one "%s: %s" rather than one per call site. */
	void FailUnderGate(const TCHAR* Gate, const FString& Why);
	/** The word a person would use for a lamp. One definition, so the same four
	 *  letters are not a literal shared between four different gates' messages. */
	static const TCHAR* LampWord(bool bLit);
	static bool ReadTokenInt(const FString& Text, const TCHAR* Token, int32& Out);
	static bool GetIntProp(const AActor* A, const TCHAR* Name, int32& Out);
	static bool SetIntProp(AActor* A, const TCHAR* Name, int32 Value);
	static bool GetBoolProp(const AActor* A, const TCHAR* Name, bool& Out);
	static bool GetNameProp(const AActor* A, const TCHAR* Name, FName& Out);
	static bool SetNameProp(AActor* A, const TCHAR* Name, FName Value);
	static FString ReadDisplay(const AActor* A, const TCHAR* PreferredName);
	static bool ReadPillarVisible(const AActor* A, bool& Out);
	static bool ReadLampLit(const AActor* A, bool& Out);
	/** The near posts that are not standing right now, as a readable list. */
	static FString NameList(const TArray<FName>& Names);

	// ---- the walk ------------------------------------------------------------
	void BuildRoute(int32 FirstVisit, int32 VisitCount, bool bLaneReturnFirst,
		bool bGateAtEnd);
	bool CheckRouteIsWalkable();
	void DriveHero(double Now);
	/** Destroys every prop in BOTH yards, does to the written record whatever this
	 *  rebuild's kind says (nothing / put the earlier copy back / take it away), and
	 *  spawns fresh props on each other's slots with the next round's numbers -- all in
	 *  ONE tick, by construction. */
	void RebuildBothYards(double Now);
	FVector LanePointFor(const FVector& Where) const;
	FVector StandPointFor(const FProp& Post) const;

	// ---- grading -------------------------------------------------------------
	void GradeVisit(const FVisit& Visit, const FWorldRead& Was, const FWorldRead& Now);
	/** The settled sample after a rebuild. ONE function for all three kinds, because
	 *  the three questions asked are the same three -- which posts are gone, what the
	 *  board reads, where the runner is standing -- and only the answer the record
	 *  gives differs. */
	void GradeReopen(const FWorldRead& Now);
	/** The in-scene negative control, gauged at every checkpoint and every graded
	 *  sample. Returns false having finished the test. */
	bool GaugeTwinYard(const FWorldRead& Now);
	bool CheckRunnerKeepsWalking(double Now);
	void LogCalib(int32 Index, double Now) const;
	FString DescribeBrokenPlayerInput(UWorld* World) const;

	// ---- state ---------------------------------------------------------------
	TWeakObjectPtr<ACharacter> Hero;
	FVector HeroStart = FVector::ZeroVector;

	FProp NearPosts[kNearPosts];
	FProp FarPostProps[kFarPosts];
	FProp PadProps[kPads];
	FProp NearBoardProp;
	FProp FarBoardProp;

	FDelegateHandle WorldInitHandle;
	bool bStaged = false;
	bool bResolved = false;

	/** Which yard is which, read off the level rather than assumed: the yard the pads
	 *  are in is the near one, and the other name found on the posts is the far one. */
	FName NearYard = NAME_None;
	FName FarYard = NAME_None;

	/** A staging failure is REMEMBERED here and reported from PrepareTest, never
	 *  reported from the world-init hook. AFunctionalTest::FinishTest is a no-op
	 *  before the test is running, so a reason raised at world-init time would be
	 *  swallowed and the run would sit there until the sentinel -- a real fault
	 *  reported as "the walk got stuck", which is the wrong diagnosis every time. */
	FString StagingFailure;
	bool bStagingIsHarnessFault = false;

	const FStagedSet* Set = nullptr;
	int32 SetIndex = 0;

	/** THE WHOLE DAY, DERIVED in BuildDayTrace by simulating the staged set's script,
	 *  so editing a set moves every expectation with it and cannot leave a stale
	 *  constant behind. Visits holds only the steps the runner walks; Reopens holds one
	 *  entry per rebuild; PhaseStart/PhaseCount slice Visits into the stretches between
	 *  rebuilds, so nothing anywhere hard-codes "five visits then three then one". */
	TArray<FVisit> Visits;
	TArray<FReopen> Reopens;
	TArray<int32> PhaseStart;
	TArray<int32> PhaseCount;
	/** Which phase's route is being walked: 0 before the first rebuild. */
	int32 Phase = 0;

	TArray<FLeg> Route;
	int32 Waypoint = 0;
	double DwellUntil = -1.0;
	int32 VisitsDone = 0;

	/** 0 before the first rebuild, then 1..Reopens.Num() after each one. */
	int32 ReopenIndex = 0;
	double RebuiltAt = -1.0;
	bool bAwaitingReopenGrade = false;
	bool bYardDown = false;
	bool bOpeningProbed = false;
	/** True when the pre-BeginPlay wipe left the project's save-game directory
	 *  genuinely absent. See WipeDurableStores. */
	bool bDurableStoreEmptyAtOpen = false;

	/** The settled sample taken on the lane before the visit now in progress. */
	FWorldRead Was;
	bool bHaveWas = false;

	/** The project's save-game directory as it stood a moment after the counter board
	 *  first rose: relative path -> bytes. Held in memory so nothing on disk can be
	 *  found and read by the thing being measured. */
	TMap<FString, TArray<uint8>> RecordSnapshot;
	bool bHaveSnapshot = false;

	/** Set by ReadWorld when what it could not read is a prop that is no longer in the
	 *  world at all -- which is TheYardsOwnPropsAreStillThere's business, not the
	 *  business of whichever gate happened to be in flight. Cleared on every read. */
	const TCHAR* ReadFailGate = nullptr;

	/** The yard's marked pad, by the name the pad carries -- the fixture's own record
	 *  of what the runner did, never read back off the submission. */
	FName MarkedPadId = NAME_None;

	/** Keeps the destroyed props' classes alive across the rebuild. Native classes are
	 *  rooted anyway; a Blueprint subclass is not. */
	UPROPERTY()
	TArray<TObjectPtr<UClass>> RebuildClasses;

	/** The way out of the yard, derived from the LEVEL's PlayerStart -- never from
	 *  where the runner happens to be standing. A submission is expressly allowed to
	 *  set the runner down at the level's first open, and a waypoint that moved with
	 *  it would be a waypoint the submission chose. */
	FVector GatePoint = FVector::ZeroVector;
	double LaneY = 0.0;
};
