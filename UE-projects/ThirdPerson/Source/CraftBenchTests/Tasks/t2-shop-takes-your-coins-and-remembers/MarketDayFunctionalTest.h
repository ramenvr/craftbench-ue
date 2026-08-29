// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// L2 for t2-shop-takes-your-coins-and-remembers.
//
// Three stalls, each with its own price, its own stock, its own capacity and its own
// delivery. The fixture stages every one of those numbers BEFORE anybody's BeginPlay
// (FWorldDelegates::OnWorldInitializedActors, the pattern ASanityFunctionalTest already
// ships), so the numbers a submission has to work from are never the numbers written
// into the level -- reading the .umap gets you the wrong answer.
//
// It then walks the character onto twelve mats with AddMovementInput -- the same input
// path a human uses -- keeping a SHADOW LEDGER of what each step must do, and grades
// what the signs and the gate board actually SAY. The whole day is graded off the
// rendered text (UTextRenderComponent::Text, parsed) with the actors' reflected
// LastShown* mirrors required to AGREE with it: the mirrors live in a file the agent
// may edit, so a mirror on its own is not evidence of a sign.
//
// Part way through, the yard is torn down and rebuilt: all three stalls and the board
// are DESTROYED and fresh ones spawned deferred, one place further along the row, with
// reset prices, a per-stall delivery and a per-stall capacity written before their
// BeginPlay runs. What must come back is the purse, the holdings and each stall's
// stock -- RECONCILED, not assigned: what it had left, plus what it was delivered,
// never more than it can hold. What must NOT come back is the price.
//
// Three staged number sets are shipped and one is selected by -CraftBenchMarketSeed=N
// (default 0, so a discrimination leg is byte-reproducible). PrepareTest SIMULATES the
// selected set against the twelve steps and refuses to run it unless every step lands
// on its intended outcome for its intended REASON, and unless the reopening
// discriminates all four naive restores. A set that stopped measuring what it claims
// is an Error, never a FAIL.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "MarketDayFunctionalTest.generated.h"

class ACharacter;

/** What an attempt must do. Used to grade AND to prove the staged set still isolates
 *  each refusal to one reason. Kept OUT of the UCLASS body deliberately: a nested,
 *  unreflected enum is one more thing for UHT to have an opinion about, and this file
 *  is only ever compiled by a machine nobody is watching. */
enum class EMarketWant : uint8
{
	Buy,
	NoMoney,
	NoStock,
	HandsFull,
};

UCLASS()
class AMarketDayFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AMarketDayFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	/** One staged stall for one round. */
	struct FStallPlan
	{
		int32 Price = 0;
		int32 Stock = 0;
		int32 Capacity = 0;
		int32 Delivered = 0;
	};

	/** One numbered set: how the yard opens, and what it comes back as. */
	struct FStagedSet
	{
		int32 OpenCoins = 0;
		int32 CarryLimit = 0;
		FStallPlan Open[3];
		FStallPlan Reopen[3];
	};

	/** One mat-step, and the whole of what it must do. Computed in PrepareTest from
	 *  the staged set, so a set change moves the expectations with it. */
	struct FStep
	{
		int32 Stall = 0;
		EMarketWant Want = EMarketWant::Buy;
		int32 CoinsAfter = 0;
		int32 StockAfter = 0;
		int32 OwnedAfter = 0;
	};

	/** A stall as it stands right now. Re-resolved after the yard reopens. */
	struct FStall
	{
		TWeakObjectPtr<AActor> Actor;
		FName Goods = NAME_None;
		FVector Home = FVector::ZeroVector;
		FVector MatCentre = FVector::ZeroVector;
		FVector LanePoint = FVector::ZeroVector;
		/** What the FIXTURE staged for this stall this round. Every price gate
		 *  compares against THIS, never against the stall's live property -- a
		 *  submission that wrote a stale price back onto the stall would otherwise
		 *  satisfy "shown == live" and pass. */
		int32 StagedPrice = 0;
		int32 StagedCapacity = 0;
		int32 StagedDelivered = 0;
	};

	/** One waypoint of the walk. */
	struct FLeg
	{
		FVector Target = FVector::ZeroVector;
		double Dwell = 0.0;
		int32 Stall = INDEX_NONE;
		int32 Step = INDEX_NONE;
		/** 0 = lane before the step, 1 = on the mat, 2 = lane after the step,
		 *  3 = the gate. */
		int32 Kind = 3;
	};

	/** What the yard reads RIGHT NOW, off the text a person sees. */
	struct FReadout
	{
		int32 Coins = 0;
		int32 Price[3] = { 0, 0, 0 };
		int32 Stock[3] = { 0, 0, 0 };
		int32 Owned[3] = { 0, 0, 0 };
	};

	/** Everything needed to put one destroyed actor back. */
	struct FRebuild
	{
		UClass* Cls = nullptr;
		FTransform Xform;
		FName Goods = NAME_None;
	};

	// ---- staging -------------------------------------------------------------
	/** Picks the numbered set. -CraftBenchMarketSeed=N chooses; the default is 0, so
	 *  a discrimination leg reproduces byte for byte. */
	void ChooseSet();
	void OnWorldActorsInitialized(const FActorsInitializedParams& Params);
	void WipeDurableStores() const;
	bool ResolveYard(bool bFirstOpen);
	/** Resolved SEPARATELY, and later. The stalls exist at world-init; the player's
	 *  pawn does not -- it is spawned by the game mode during UWorld::BeginPlay,
	 *  which is after FWorldDelegates::OnWorldInitializedActors has already fired.
	 *  Checking for it during staging would have failed every submission, the
	 *  reference included. */
	bool ResolveHero();
	void StageRound(const FStallPlan* Plan, int32 Coins);
	/** Records what the fixture staged WITHOUT writing it, for the round the yard has
	 *  already been rebuilt into -- writing again after a submission's BeginPlay would
	 *  paper over exactly the mistakes the price gate exists to catch. */
	void RecordStaged(const FStallPlan* Plan);
	bool BuildStepTrace();
	const FStep& StepAt(int32 GlobalIndex) const;

	// ---- reading the yard ----------------------------------------------------
	bool ReadYard(FReadout& Out, FString& Why) const;
	static bool ReadTokenInt(const FString& Text, const TCHAR* Token, int32& Out);
	static bool GetIntProp(const AActor* A, const TCHAR* Name, int32& Out);
	static bool SetIntProp(AActor* A, const TCHAR* Name, int32 Value);
	static bool GetNameProp(const AActor* A, const TCHAR* Name, FName& Out);
	static bool SetNameProp(AActor* A, const TCHAR* Name, FName Value);
	static FString ReadDisplay(const AActor* A, const TCHAR* PreferredName);

	// ---- the walk ------------------------------------------------------------
	void BuildRoute(int32 FirstStepIndex, int32 StepCount);
	bool CheckRouteIsWalkable();
	void DriveHero(double Now);
	void CloseTheYard();
	void ReopenTheYard(double Now);

	// ---- grading -------------------------------------------------------------
	void GradeStep(const FStep& Step, const FReadout& Was, const FReadout& Now);
	void GradeReopening(const FReadout& Now);
	bool CheckAlwaysTrue(double Now, float DeltaSeconds);
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<ACharacter> Hero;
	TArray<FStall> Stalls;
	TWeakObjectPtr<AActor> Ledger;

	FDelegateHandle WorldInitHandle;
	bool bStaged = false;

	const FStagedSet* Set = nullptr;
	int32 SetIndex = 0;

	TArray<FStep> Steps;
	int32 Round1Count = 0;
	/** What the yard must read the instant it reopens. */
	int32 ReopenCoins = 0;
	int32 ReopenStock[3] = { 0, 0, 0 };
	int32 ReopenOwned[3] = { 0, 0, 0 };
	/** What each stall had left the moment the yard shut -- the first term of the
	 *  reconciliation, kept so the failure message can spell the sum out. */
	int32 ClosingStock[3] = { 0, 0, 0 };

	TArray<FLeg> Route;
	int32 Waypoint = 0;
	double DwellUntil = -1.0;
	int32 StepsDone = 0;
	bool bReopened = false;
	bool bBaselineChecked = false;

	/** The settled sample taken before the step now in progress. */
	FReadout Was;
	bool bHaveWas = false;

	/** Stability probe: armed a while after the character settles on a mat, cleared
	 *  when it leaves. */
	double StabilityArmAt = -1.0;
	bool bStabilityArmed = false;
	FReadout OnMatSnapshot;

	/** Set while the yard has no stalls in it, so the every-frame gates stand down
	 *  for exactly as long as there is nothing to read. */
	bool bYardDown = false;
	bool bAwaitingRebuild = false;
	double SettleUntil = -1.0;

	TArray<FRebuild> StallRebuilds;
	FRebuild LedgerRebuild;
	/** Keeps the destroyed actors' classes alive across the one frame the yard is
	 *  empty. Native classes are rooted anyway; a Blueprint subclass is not. */
	UPROPERTY()
	TArray<TObjectPtr<UClass>> RebuildClasses;

	FVector GatePoint = FVector::ZeroVector;
	FVector HeroWas = FVector::ZeroVector;
	bool bHeroWasValid = false;
};
