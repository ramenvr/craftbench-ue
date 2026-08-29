// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-bridge-only-holds-what-it-can-bear.
//
// Two footbridges rated differently. A span holds anything up to its own rating, sags in
// proportion to how much of that rating is in use, gives way the moment the total goes
// over, stays down while anything is still standing on the FALLEN deck, and heaves back
// up once it is clear. The character standing on a span is part of that total, and the
// character does not weigh the same all day.
//
// THREE THINGS ABOUT THIS FIXTURE ARE LOAD-BEARING AND EASY TO UNDO BY ACCIDENT:
//
// 1. IT STAMPS THE NUMBERS, IT DOES NOT READ THEM. Both ratings, all three crate
//    weights, both sag distances and the character's mass are written INTO the world by
//    this fixture -- the first four before any placed actor's BeginPlay has run, via
//    FWorldDelegates::OnWorldInitializedActors. Everything the gates compute afterwards
//    is computed from what the fixture WROTE, never from a live re-read. That is what
//    makes it impossible for a submission to satisfy a gate by editing the number the
//    gate is about (zero the character's mass and the fixture's own expected total goes
//    to zero with it -- so the divergence is graded instead, by
//    TheYardsSetupIsNotYoursToChange). It is also what makes the numbers differ from run
//    to run, so no constant can be right twice.
//
// 2. NOTHING A SUBMISSION CAN CAUSE IS AN ::Error. The ::Error tag audit: an
//    ::Error leaves the run out of the denominator, so it may only fire on a condition
//    no submission can manufacture. Here that is exactly two things -- no world, and the
//    fixture's OWN drawn staging failing the fixture's own arithmetic. Every claim about
//    the world (wrong actor counts, a moved crate, a re-stamped rating, a destroyed
//    span) is a graded FAIL through TheYardsSetupIsNotYoursToChange.
//
// 3. THE OCCUPANCY TRUTH FOLLOWS THE DECK. Whether something is standing on a span is
//    asked against where the deck IS -- which is 200 cm lower after a collapse. Between
//    "plainly on it" and "plainly off it" there is a band in which this fixture asserts
//    NOTHING, because a correct submission may reasonably draw that line a few
//    centimetres either side of where this one draws it. No stand is ever taken in the
//    band.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "TrestleLoadFunctionalTest.generated.h"

class ACharacter;
class UPrimitiveComponent;
struct FActorsInitializedParams;

UCLASS()
class ATrestleLoadFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ATrestleLoadFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	/** What the yard does when the drive reaches a step. */
	enum class EYardAction : uint8
	{
		None,
		StageAnvil,
		LiftAnvil,
		StageSackAndKeg,
		ClearSackAndKeg,
		ShoulderThePack,
	};

	/** One place the character walks to and STANDS at. Advancing on arrival would
	 *  consume the whole route in a couple of seconds and nothing would ever settle. */
	struct FStep
	{
		double X = 0.0;
		double Y = 0.0;
		double Dwell = 3.0;
		EYardAction Action = EYardAction::None;
		/** nullptr = this step is travel, not a measured stand. */
		const TCHAR* Stand = nullptr;
		/** Which span the character must be standing on for the stand to count.
		 *  INDEX_NONE = on neither. This is how "the deck's collision was switched off
		 *  and the character walked the route on the floor below" is caught: nothing is
		 *  ever on a span, so no stand is ever taken. */
		int32 CharOnSpan = INDEX_NONE;
		/** When true, an up/down verdict on THIS stand's span is reported under
		 *  TheCharactersOwnWeightCounts, so attribution is deterministic. */
		bool bAboutTheCharactersWeight = false;
		bool bSampled = false;
	};

	struct FSpan
	{
		TWeakObjectPtr<AActor> Actor;
		TWeakObjectPtr<UPrimitiveComponent> Deck;
		const TCHAR* Name = TEXT("?");
		FVector StagedAt = FVector::ZeroVector;

		// What the yard stamped. The gates compute from THESE, never from a re-read.
		double RatedKg = 0.0;
		double FullSagCm = 0.0;
		double DropCm = 0.0;

		// The fixture's own running truth about this span.
		double TotalKg = 0.0;
		int32 Occupants = 0;
		FString ItemList;
		bool bAmbiguous = false;
		bool bExpectDown = false;
		bool bRecoveryPending = false;
		double TruthChangedAt = 0.0;
		double EmptySince = -1.0;

		// Observed, for the completion gate.
		bool bDeckWasDown = false;
		int32 GaveWayCount = 0;
		int32 CameBackCount = 0;
	};

	struct FLoad
	{
		TWeakObjectPtr<AActor> Actor;
		const TCHAR* Name = TEXT("?");
		double WeightKg = 0.0;
		/** Where the yard parks it when it is not on a span. */
		FVector Home = FVector::ZeroVector;
		/** Where the yard last put it. XY is pinned against this every frame. */
		FVector StagedAt = FVector::ZeroVector;
		double HalfHeightCm = 60.0;
	};

	// -- staging -------------------------------------------------------------------
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	bool ResolveAndStampTheYard(UWorld* World);
	bool DrawTheNumbers(FString& OutWhy);
	void BuildRoute();

	// -- the fixture's own truth ---------------------------------------------------
	static bool GetFootprint(const AActor* A, FVector& OutMiddle, double& OutBaseZ);
	/** 0 = plainly off the deck, 1 = plainly on it, -1 = in the band between, where
	 *  this fixture refuses to have an opinion. */
	int32 ClassifyOnSpan(const FSpan& Span, const AActor* Candidate) const;
	void UpdateSpanTruth(FSpan& Span, double Now);
	double DeckDropCm(const FSpan& Span) const;
	bool IsSettled(const FSpan& Span, double Now) const;

	// -- gates (one FinishTest(Failed) each, so the matrix can name the one that fired)
	void FailHolds(const FSpan& Span);
	void FailGivesWay(const FSpan& Span);
	void FailSag(const FSpan& Span, double Measured, double Wanted);
	void FailCharacterWeight(const FSpan& Span, bool bShouldHold);
	void FailStaysDown(const FSpan& Span);
	void FailHeavesBackUp(const FSpan& Span, double Now);
	void FailSetupChanged(const FString& What);
	void FailRoundsUnfinished(const FString& What);

	bool CheckTheYardIsAsTheYardLeftIt();
	bool YardFinishedItsRounds(FString& OutWhy) const;

	// -- the drive -----------------------------------------------------------------
	void RunYardAction(EYardAction Action);
	void PutCrateOnSpan(FLoad& Load, const FSpan& Span, double OffsetX);
	void SendCrateHome(FLoad& Load);
	void DriveHero(double Now);
	void LogCalibration(int32 CheckpointIndex, double Now) const;
	FString DescribeSpan(const FSpan& Span) const;

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FSpan> Spans;
	TArray<FLoad> Loads;
	TArray<FStep> Steps;

	/** The mass the yard has stamped on the character right now. Every gate that
	 *  involves the character uses THIS, and the world is pinned against it. */
	double CharacterMassKg = 0.0;
	double PackedMassKg = 0.0;

	FVector DeckHalfExtent = FVector::ZeroVector;

	/** Index of the sentinel checkpoint, DERIVED from the schedule that was actually
	 *  built. Written down instead, an off-by-one would silently skip the completion
	 *  gate -- which is the only gate that sees a submission nothing can stand on. */
	int32 SentinelIndex = 0;

	int32 Step = 0;
	double DwellUntil = -1.0;
	bool bActionRun = false;
	bool bStaged = false;
	bool bStampFailed = false;
	FString StampFailure;
	int32 DrawSeed = 0;

	FDelegateHandle WorldInitHandle;
};
