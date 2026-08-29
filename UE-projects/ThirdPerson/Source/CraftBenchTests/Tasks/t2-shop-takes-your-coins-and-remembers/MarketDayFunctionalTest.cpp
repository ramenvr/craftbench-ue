// Copyright CraftBench. All Rights Reserved.

#include "MarketDayFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName kStallTag(TEXT("MarketStall"));
	static const FName kLedgerTag(TEXT("MarketLedger"));

	// UNDISCLOSED: fixture clocking. Sized from MEASURED substrate movement -- the
	// ThirdPerson character walks at 500 uu/s with MaxAcceleration 2048 and
	// BrakingDecelerationWalking 2000 (ThirdPersonCharacter.cpp; NOT the engine
	// defaults of 600 / 2048 / 2048, which is what an earlier draft of this fixture
	// sized itself against). A 700 uu approach therefore takes ~1.7 s including both
	// ramps, and every dwell below clears the prompt's disclosed half second several
	// times over -- widened only in the direction that cannot fail correct work.
	constexpr double kLaneBeforeS = 1.2;   // settle, then the pre-step sample
	constexpr double kMatDwellS = 2.0;     // stand ON the mat
	constexpr double kLaneAfterS = 1.5;    // settle, then the graded sample
	constexpr double kStabilityArmS = 0.8; // after settling on the mat, before probing
	constexpr double kGateDwellS = 1.0;
	constexpr double kReopenSettleS = 4.0;

	constexpr double kWaypointUu = 70.0;
	// The mat is 240 square, so its near edge is 120 from the centre and a lane point
	// 700 out is 580 uu clear of it. Nothing about walking the lane can be mistaken
	// for standing on a mat.
	constexpr double kLaneOutUu = 700.0;
	constexpr double kGateExtraUu = 400.0;
	constexpr double kMinMatClearanceUu = 250.0;
	constexpr double kMinCounterClearanceUu = 150.0;
	constexpr double kMinPriceSpread = 8.0;

	// A walking character covers 500 * dt. Anything six times that in one frame was
	// not walked, it was placed.
	constexpr double kShoveFloorUu = 120.0;
	constexpr double kShoveFactor = 6.0;

	constexpr int32 kSentinelIndex = 60;
	constexpr double kSentinelAtS = 480.0;
	constexpr double kCheckpointEveryS = 6.0;

	/** Names every gate reads or writes. All of them live in the agent's own file, so
	 *  a missing one is a SCORED failure, not an unattributed harness error. */
	const TCHAR* const kStallIntProps[] = {
		TEXT("PriceCoins"), TEXT("StockCount"), TEXT("StockCapacity"),
		TEXT("DeliveredSinceClose"), TEXT("LastShownPrice"), TEXT("LastShownStock"),
		TEXT("LastShownOwned"),
	};
	const TCHAR* const kLedgerIntProps[] = {
		TEXT("StartingCoins"), TEXT("CarryLimit"), TEXT("LastShownCoins"),
	};
}

AMarketDayFunctionalTest::AMarketDayFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	// Registered in the CONSTRUCTOR, exactly as ASanityFunctionalTest does: the hook
	// fires after PostInitializeComponents and BEFORE any placed actor's BeginPlay,
	// which is the only window in which the day's numbers can be staged without a
	// submission having already read the level's.
	WorldInitHandle = FWorldDelegates::OnWorldInitializedActors.AddUObject(
		this, &AMarketDayFunctionalTest::OnWorldActorsInitialized);
}

void AMarketDayFunctionalTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WorldInitHandle.IsValid())
	{
		FWorldDelegates::OnWorldInitializedActors.Remove(WorldInitHandle);
		WorldInitHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

// ---------------------------------------------------------------------------
// Reflection helpers. Everything is read and written BY PROPERTY NAME, never by
// class, so a submission is free to subclass or rename the supplied actors.
// ---------------------------------------------------------------------------

bool AMarketDayFunctionalTest::GetIntProp(const AActor* A, const TCHAR* Name,
	int32& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	const FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AMarketDayFunctionalTest::SetIntProp(AActor* A, const TCHAR* Name, int32 Value)
{
	if (A == nullptr)
	{
		return false;
	}
	FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

bool AMarketDayFunctionalTest::GetNameProp(const AActor* A, const TCHAR* Name,
	FName& Out)
{
	if (A == nullptr)
	{
		return false;
	}
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	Out = P->GetPropertyValue_InContainer(A);
	return true;
}

bool AMarketDayFunctionalTest::SetNameProp(AActor* A, const TCHAR* Name, FName Value)
{
	if (A == nullptr)
	{
		return false;
	}
	FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Name);
	if (P == nullptr)
	{
		return false;
	}
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

FString AMarketDayFunctionalTest::ReadDisplay(const AActor* A,
	const TCHAR* PreferredName)
{
	if (A == nullptr)
	{
		return FString();
	}
	TArray<UTextRenderComponent*> Texts;
	const_cast<AActor*>(A)->GetComponents<UTextRenderComponent>(Texts);
	const UTextRenderComponent* Chosen = nullptr;
	for (const UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetFName() == FName(PreferredName))
		{
			Chosen = T;
			break;
		}
	}
	if (Chosen == nullptr)
	{
		for (const UTextRenderComponent* T : Texts)
		{
			if (T != nullptr)
			{
				Chosen = T;
				break;
			}
		}
	}
	// THE RENDERED TEXT, not a mirror. The mirrors live in a file the agent may edit,
	// so they are only ever a cross-check against this.
	return (Chosen != nullptr) ? Chosen->Text.ToString() : FString();
}

bool AMarketDayFunctionalTest::ReadTokenInt(const FString& Text, const TCHAR* Token,
	int32& Out)
{
	const int32 At = Text.Find(Token, ESearchCase::CaseSensitive,
		ESearchDir::FromStart);
	if (At == INDEX_NONE)
	{
		return false;
	}
	int32 i = At + FCString::Strlen(Token);
	while (i < Text.Len() && FChar::IsWhitespace(Text[i]))
	{
		++i;
	}
	bool bNegative = false;
	if (i < Text.Len() && Text[i] == TEXT('-'))
	{
		bNegative = true;
		++i;
	}
	if (i >= Text.Len() || !FChar::IsDigit(Text[i]))
	{
		return false;
	}
	int64 Value = 0;
	while (i < Text.Len() && FChar::IsDigit(Text[i]))
	{
		Value = Value * 10 + int64(Text[i] - TEXT('0'));
		++i;
	}
	Out = int32(bNegative ? -Value : Value);
	return true;
}

// ---------------------------------------------------------------------------
// Staging
// ---------------------------------------------------------------------------

void AMarketDayFunctionalTest::ChooseSet()
{
	// THREE SETS, one shape. Every set walks the same twelve steps to the same twelve
	// outcomes for the same twelve reasons; only the numbers move. Nothing a
	// submission can hard-code is right in more than one of them, and PrepareTest
	// re-derives the shape rather than trusting this table.
	static const FStagedSet kSets[] =
	{
		// set 0 -- the set every discrimination leg runs
		{ 240, 3,
		  { { 30, 2, 4, 0 }, { 40, 2, 3, 0 }, { 55, 4, 6, 0 } },
		  { { 10, 4, 4, 3 }, { 20, 3, 3, 1 }, { 70, 3, 3, 2 } } },
		// set 1
		{ 280, 3,
		  { { 45, 2, 5, 0 }, { 25, 2, 4, 0 }, { 60, 4, 6, 0 } },
		  { { 15, 5, 5, 2 }, { 30, 4, 4, 3 }, { 80, 4, 4, 3 } } },
		// set 2
		{ 200, 3,
		  { { 25, 2, 4, 0 }, { 55, 2, 4, 0 }, { 35, 4, 5, 0 } },
		  { {  8, 4, 4, 4 }, { 17, 4, 4, 2 }, { 40, 4, 4, 3 } } },
	};

	const int32 Count = int32(UE_ARRAY_COUNT(kSets));
	int32 Seed = 0;
	FParse::Value(FCommandLine::Get(), TEXT("CraftBenchMarketSeed="), Seed);
	SetIndex = ((Seed % Count) + Count) % Count;
	Set = &kSets[SetIndex];
}

void AMarketDayFunctionalTest::WipeDurableStores() const
{
	// A day written down SURVIVES THE PROCESS. On a second run in the same workdir --
	// a re-capture, a gate re-run, a second rep -- a correct submission would restore
	// yesterday's closing state at step 1 and be failed for having obeyed the prompt.
	// The slot directory is emptied before anything has begun play, so a solution
	// that writes its record down starts every run on the same footing as one that
	// keeps it in memory. The complementary half is the round-1 baseline check below,
	// which turns a store this could not reach into an attributed Error, not a FAIL.
	const FString SaveDir = FPaths::ProjectSavedDir() / TEXT("SaveGames");
	IFileManager::Get().DeleteDirectory(*SaveDir, false, true);
}

void AMarketDayFunctionalTest::OnWorldActorsInitialized(
	const FActorsInitializedParams& Params)
{
	// Single-shot, and only for OUR PIE world.
	if (bStaged || Params.World != GetWorld())
	{
		return;
	}
	bStaged = true;

	ChooseSet();
	WipeDurableStores();

	if (!ResolveYard(true))
	{
		return;     // ResolveYard has already finished the test with the reason
	}
	StageRound(Set->Open, Set->OpenCoins);
}

bool AMarketDayFunctionalTest::ResolveYard(bool bFirstOpen)
{
	UWorld* const World = GetWorld();
	TArray<AActor*> FoundStalls;
	UGameplayStatics::GetAllActorsWithTag(World, kStallTag, FoundStalls);
	if (FoundStalls.Num() != 3)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardsOwnNumbersAreStillThere: the yard should hold exactly three "
				 "market stalls and it holds %d. The stalls are supplied and placed; "
				 "they are not yours to add to or take away"), FoundStalls.Num()));
		return false;
	}
	TArray<AActor*> FoundLedgers;
	UGameplayStatics::GetAllActorsWithTag(World, kLedgerTag, FoundLedgers);
	if (FoundLedgers.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardsOwnNumbersAreStillThere: the yard should hold exactly one "
				 "board by the gate and it holds %d"), FoundLedgers.Num()));
		return false;
	}
	Ledger = FoundLedgers[0];
	for (const TCHAR* const PropName : kLedgerIntProps)
	{
		int32 Ignored = 0;
		if (!GetIntProp(FoundLedgers[0], PropName, Ignored))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardsOwnNumbersAreStillThere: the board by the gate no "
					 "longer says %s, so nothing can read what it is telling "
					 "anybody"), PropName));
			return false;
		}
	}

	// A stable order that does NOT depend on where a stall stands, because the stalls
	// are shuffled part way through the day.
	if (bFirstOpen)
	{
		FoundStalls.Sort([](const AActor& L, const AActor& R)
		{
			return L.GetName() < R.GetName();
		});
	}

	TArray<FStall> Rebuilt;
	Rebuilt.SetNum(3);
	for (int32 i = 0; i < FoundStalls.Num(); ++i)
	{
		AActor* const A = FoundStalls[i];
		for (const TCHAR* const PropName : kStallIntProps)
		{
			int32 Ignored = 0;
			if (!GetIntProp(A, PropName, Ignored))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheYardsOwnNumbersAreStillThere: a stall no longer says "
						 "%s, so nothing can read what that stall is asking or "
						 "holding"), PropName));
				return false;
			}
		}
		FName Goods = NAME_None;
		if (!GetNameProp(A, TEXT("GoodsName"), Goods) || Goods.IsNone())
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("TheYardsOwnNumbersAreStillThere: a stall does not say what it "
					 "sells, and a stall is known by nothing else"));
			return false;
		}

		int32 Slot = i;
		if (!bFirstOpen)
		{
			// After the yard reopens the stalls are found in whatever order the world
			// reports them, and every one of them has MOVED. Match by what they sell.
			Slot = INDEX_NONE;
			for (int32 k = 0; k < Stalls.Num(); ++k)
			{
				if (Stalls[k].Goods == Goods)
				{
					Slot = k;
					break;
				}
			}
			if (Slot == INDEX_NONE)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("AStallIsKnownByWhatItSells: the yard reopened with a stall "
						 "selling %s, which is not one of the three kinds it closed "
						 "with"), *Goods.ToString()));
				return false;
			}
		}
		Rebuilt[Slot].Actor = A;
		Rebuilt[Slot].Goods = Goods;
		Rebuilt[Slot].Home = A->GetActorLocation();

		// The mat's position is READ, never written down, so the route follows the
		// stalls wherever the yard puts them.
		TArray<UBoxComponent*> Boxes;
		A->GetComponents<UBoxComponent>(Boxes);
		const UBoxComponent* Mat = nullptr;
		for (const UBoxComponent* B : Boxes)
		{
			if (B != nullptr && B->GetFName() == FName(TEXT("Mat")))
			{
				Mat = B;
				break;
			}
		}
		if (Mat == nullptr)
		{
			// Not named Mat: take the biggest box on the stall rather than give up on
			// a submission that reorganised its components.
			double Best = -1.0;
			for (const UBoxComponent* B : Boxes)
			{
				if (B == nullptr)
				{
					continue;
				}
				const FVector E = B->GetScaledBoxExtent();
				const double Area = double(E.X) * double(E.Y);
				if (Area > Best)
				{
					Best = Area;
					Mat = B;
				}
			}
		}
		if (Mat == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardsOwnNumbersAreStillThere: the stall selling %s has no "
					 "mat in front of it, so there is nowhere to step on"),
				*Goods.ToString()));
			return false;
		}
		Rebuilt[Slot].MatCentre = Mat->GetComponentLocation();
		const FVector Out =
			(Rebuilt[Slot].MatCentre - Rebuilt[Slot].Home).GetSafeNormal2D();
		Rebuilt[Slot].LanePoint = Rebuilt[Slot].MatCentre + Out * kLaneOutUu;
	}

	// Three kinds of goods, or two of the stalls are interchangeable and half of what
	// this task claims to measure is gone.
	for (int32 i = 0; i < 3; ++i)
	{
		for (int32 j = i + 1; j < 3; ++j)
		{
			if (Rebuilt[i].Goods == Rebuilt[j].Goods)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("AStallIsKnownByWhatItSells: two stalls both sell %s, so a "
						 "stall cannot be told from its neighbour by what it sells"),
					*Rebuilt[i].Goods.ToString()));
				return false;
			}
		}
	}

	// Carry over what the fixture staged, so a re-resolve after the reopening does
	// not lose the numbers the price gate compares against.
	for (int32 i = 0; i < 3; ++i)
	{
		if (Stalls.IsValidIndex(i))
		{
			Rebuilt[i].StagedPrice = Stalls[i].StagedPrice;
			Rebuilt[i].StagedCapacity = Stalls[i].StagedCapacity;
			Rebuilt[i].StagedDelivered = Stalls[i].StagedDelivered;
		}
	}
	Stalls = Rebuilt;

	// The gate: out in front of the row and clear of every mat.
	FVector MeanLane = FVector::ZeroVector;
	FVector MeanOut = FVector::ZeroVector;
	for (const FStall& S : Stalls)
	{
		MeanLane += S.LanePoint;
		MeanOut += (S.MatCentre - S.Home).GetSafeNormal2D();
	}
	MeanLane /= 3.0;
	GatePoint = MeanLane + MeanOut.GetSafeNormal2D() * kGateExtraUu;
	return true;
}

bool AMarketDayFunctionalTest::ResolveHero()
{
	// NOT during staging. The stalls are placed actors and exist the moment the world
	// initialises them; the player's pawn is spawned by the game mode inside
	// UWorld::BeginPlay, which is AFTER OnWorldInitializedActors has fired. Asking for
	// it there returns null on a perfectly healthy yard.
	Hero = UGameplayStatics::GetPlayerCharacter(GetWorld(), 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheYardsOwnNumbersAreStillThere: there is no visibly represented "
				 "player character in the yard to do the shopping"));
		return false;
	}
	return true;
}

void AMarketDayFunctionalTest::RecordStaged(const FStallPlan* Plan)
{
	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		Stalls[i].StagedPrice = Plan[i].Price;
		Stalls[i].StagedCapacity = Plan[i].Capacity;
		Stalls[i].StagedDelivered = Plan[i].Delivered;
	}
}

void AMarketDayFunctionalTest::StageRound(const FStallPlan* Plan, int32 Coins)
{
	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		AActor* const A = Stalls[i].Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		SetIntProp(A, TEXT("PriceCoins"), Plan[i].Price);
		SetIntProp(A, TEXT("StockCount"), Plan[i].Stock);
		SetIntProp(A, TEXT("StockCapacity"), Plan[i].Capacity);
		SetIntProp(A, TEXT("DeliveredSinceClose"), Plan[i].Delivered);
	}
	if (AActor* const L = Ledger.Get())
	{
		SetIntProp(L, TEXT("StartingCoins"), Coins);
		SetIntProp(L, TEXT("CarryLimit"), Set->CarryLimit);
	}
	RecordStaged(Plan);
}

// ---------------------------------------------------------------------------
// The shadow ledger. Everything the gates expect is DERIVED here from the staged
// set, so changing a set moves the expectations with it and cannot leave a stale
// constant behind.
// ---------------------------------------------------------------------------

bool AMarketDayFunctionalTest::BuildStepTrace()
{
	struct FPlanned
	{
		int32 Stall;
		EMarketWant Want;
	};
	// THE DAY. Eight steps, the yard closes and reopens, then four more. Each refusal
	// is placed where exactly ONE of the three conditions fails, so the gate that
	// names it is the gate that is measuring it.
	static const FPlanned kR1[] = {
		{ 0, EMarketWant::Buy },        // 1  buy
		{ 0, EMarketWant::Buy },        // 2  buy, and this stall walks to exactly none left
		{ 0, EMarketWant::NoStock },    // 3  sold out, and the purse could plainly pay
		{ 1, EMarketWant::Buy },        // 4  a second stall, a different price
		{ 2, EMarketWant::Buy },        // 5  a third stall, a third price
		{ 2, EMarketWant::Buy },        // 6
		{ 2, EMarketWant::NoMoney },    // 7  cannot pay, and there is stock
		{ 0, EMarketWant::NoStock },    // 8  sold out at EXACTLY the price the purse holds
	};
	static const FPlanned kR2[] = {
		{ 0, EMarketWant::Buy },        // 9  the delivery restocked a stall that sold out
		{ 0, EMarketWant::HandsFull },  // 10 can pay, has stock, hands full of that kind
		{ 1, EMarketWant::Buy },        // 11 the last coin buys: >= is a sale
		{ 2, EMarketWant::NoMoney },    // 12 nothing left to pay with, so step 11 really did
	};

	const int32 Carry = Set->CarryLimit;
	int32 Coins = Set->OpenCoins;
	int32 Stock[3] = { Set->Open[0].Stock, Set->Open[1].Stock, Set->Open[2].Stock };
	int32 Owned[3] = { 0, 0, 0 };
	int32 Price[3] = { Set->Open[0].Price, Set->Open[1].Price, Set->Open[2].Price };

	Steps.Reset();
	Round1Count = int32(UE_ARRAY_COUNT(kR1));

	auto RunOne = [&](const FPlanned& P, int32 Number) -> bool
	{
		const int32 i = P.Stall;
		const bool bCanPay = Coins >= Price[i];
		const bool bInStock = Stock[i] >= 1;
		const bool bRoom = Owned[i] < Carry;
		const int32 Failures = (bCanPay ? 0 : 1) + (bInStock ? 0 : 1) + (bRoom ? 0 : 1);

		EMarketWant Actual = EMarketWant::Buy;
		if (!bCanPay)
		{
			Actual = EMarketWant::NoMoney;
		}
		else if (!bInStock)
		{
			Actual = EMarketWant::NoStock;
		}
		else if (!bRoom)
		{
			Actual = EMarketWant::HandsFull;
		}

		if (Actual != P.Want || (Actual != EMarketWant::Buy && Failures != 1))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: staged set %d no longer walks the day it "
					 "claims to. Step %d at the stall selling %s: can-pay %d, "
					 "in-stock %d, room %d (%d conditions failing) -- the day is only "
					 "worth walking if every refusal has exactly one reason"),
				SetIndex, Number, *Stalls[i].Goods.ToString(), bCanPay ? 1 : 0,
				bInStock ? 1 : 0, bRoom ? 1 : 0, Failures));
			return false;
		}

		if (Actual == EMarketWant::Buy)
		{
			Coins -= Price[i];
			Stock[i] -= 1;
			Owned[i] += 1;
		}
		FStep S;
		S.Stall = i;
		S.Want = Actual;
		S.CoinsAfter = Coins;
		S.StockAfter = Stock[i];
		S.OwnedAfter = Owned[i];
		Steps.Add(S);
		return true;
	};

	for (int32 k = 0; k < Round1Count; ++k)
	{
		if (!RunOne(kR1[k], k + 1))
		{
			return false;
		}
	}

	// THE REOPENING. What each stall comes back holding is what it had left, PLUS
	// what it was delivered, and never more than it can hold.
	ReopenCoins = Coins;
	for (int32 i = 0; i < 3; ++i)
	{
		ClosingStock[i] = Stock[i];
		ReopenOwned[i] = Owned[i];
		ReopenStock[i] = FMath::Clamp(Stock[i] + Set->Reopen[i].Delivered, 0,
			Set->Reopen[i].Capacity);
	}

	// The four naive restores, each of which must be wrong about at least one stall,
	// or the reopening is not measuring what the spec says it measures.
	bool bBeatsRemembered = false;
	bool bBeatsDeliveredOnly = false;
	bool bBeatsRebuilt = false;
	bool bBeatsUnclamped = false;
	for (int32 i = 0; i < 3; ++i)
	{
		const int32 DeliveredOnly = FMath::Clamp(Set->Reopen[i].Delivered, 0,
			Set->Reopen[i].Capacity);
		bBeatsRemembered |= (ReopenStock[i] != Stock[i]);
		bBeatsDeliveredOnly |= (ReopenStock[i] != DeliveredOnly);
		bBeatsRebuilt |= (ReopenStock[i] != Set->Reopen[i].Stock);
		bBeatsUnclamped |= (ReopenStock[i] != Stock[i] + Set->Reopen[i].Delivered);
	}
	if (!bBeatsRemembered || !bBeatsDeliveredOnly || !bBeatsRebuilt
		|| !bBeatsUnclamped)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: staged set %d reopens on numbers that a naive "
				 "restore would get right (remembered-only %d, delivered-only %d, "
				 "kept-what-arrived %d, added-without-a-cap %d). The reopening has to "
				 "separate all four or it measures nothing"), SetIndex,
			bBeatsRemembered ? 1 : 0, bBeatsDeliveredOnly ? 1 : 0,
			bBeatsRebuilt ? 1 : 0, bBeatsUnclamped ? 1 : 0));
		return false;
	}

	for (int32 i = 0; i < 3; ++i)
	{
		Stock[i] = ReopenStock[i];
		Price[i] = Set->Reopen[i].Price;
	}
	for (int32 k = 0; k < int32(UE_ARRAY_COUNT(kR2)); ++k)
	{
		if (!RunOne(kR2[k], Round1Count + k + 1))
		{
			return false;
		}
	}

	// The three stalls must not be interchangeable in either round, and the market
	// must actually have reset every price -- otherwise a submission that saved the
	// price alongside the stock would go unpunished on that stall.
	for (int32 i = 0; i < 3; ++i)
	{
		if (Set->Open[i].Price == Set->Reopen[i].Price)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: staged set %d reopens the stall selling "
					 "%s at the same %d it closed on, so a remembered price would be "
					 "indistinguishable from the market's"), SetIndex,
				*Stalls[i].Goods.ToString(), Set->Open[i].Price));
			return false;
		}
		for (int32 j = i + 1; j < 3; ++j)
		{
			const int32 OpenGap = FMath::Abs(Set->Open[i].Price - Set->Open[j].Price);
			const int32 BackGap =
				FMath::Abs(Set->Reopen[i].Price - Set->Reopen[j].Price);
			if (double(OpenGap) < kMinPriceSpread || double(BackGap) < kMinPriceSpread)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: staged set %d puts two prices %d and "
						 "%d apart; one number would very nearly fit them both and "
						 "the task would measure less than it claims"), SetIndex,
					OpenGap, BackGap));
				return false;
			}
		}
	}
	return true;
}

const AMarketDayFunctionalTest::FStep& AMarketDayFunctionalTest::StepAt(
	int32 GlobalIndex) const
{
	return Steps[GlobalIndex];
}

// ---------------------------------------------------------------------------
// Reading the yard, off the text a person standing in it would read
// ---------------------------------------------------------------------------

bool AMarketDayFunctionalTest::ReadYard(FReadout& Out, FString& Why) const
{
	Out = FReadout();

	const AActor* const L = Ledger.Get();
	if (L == nullptr)
	{
		Why = TEXT("there is no board by the gate any more");
		return false;
	}
	const FString BoardText = ReadDisplay(L, TEXT("CoinsBoard"));
	int32 ShownCoins = 0;
	if (!ReadTokenInt(BoardText, TEXT("coins"), ShownCoins))
	{
		Why = FString::Printf(TEXT("the board by the gate reads [%s], which does not "
			"say how many coins"), *BoardText);
		return false;
	}
	int32 ShownCarry = 0;
	if (!ReadTokenInt(BoardText, TEXT("carry"), ShownCarry)
		|| ShownCarry != Set->CarryLimit)
	{
		Why = FString::Printf(TEXT("the board by the gate reads [%s]; it should say "
			"you can carry %d of a kind"), *BoardText, Set->CarryLimit);
		return false;
	}
	int32 MirrorCoins = 0;
	if (!GetIntProp(L, TEXT("LastShownCoins"), MirrorCoins)
		|| MirrorCoins != ShownCoins)
	{
		Why = FString::Printf(TEXT("the board by the gate reads [%s] but reports its "
			"own last shown coins as %d"), *BoardText, MirrorCoins);
		return false;
	}
	Out.Coins = ShownCoins;

	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		const AActor* const A = Stalls[i].Actor.Get();
		if (A == nullptr)
		{
			Why = FString::Printf(TEXT("the stall selling %s is gone"),
				*Stalls[i].Goods.ToString());
			return false;
		}
		const FString SignText = ReadDisplay(A, TEXT("Sign"));
		int32 P = 0;
		int32 S = 0;
		int32 O = 0;
		int32 Came = 0;
		int32 Holds = 0;
		if (!ReadTokenInt(SignText, TEXT("price"), P)
			|| !ReadTokenInt(SignText, TEXT("left"), S)
			|| !ReadTokenInt(SignText, TEXT("yours"), O)
			|| !ReadTokenInt(SignText, TEXT("came"), Came)
			|| !ReadTokenInt(SignText, TEXT("holds"), Holds))
		{
			Why = FString::Printf(TEXT("the sign on the stall selling %s reads [%s], "
				"which does not state a price, a count left, a count owned, a "
				"delivery and a capacity in the wording the yard prints"),
				*Stalls[i].Goods.ToString(), *SignText);
			return false;
		}
		if (Came != Stalls[i].StagedDelivered || Holds != Stalls[i].StagedCapacity)
		{
			Why = FString::Printf(TEXT("the sign on the stall selling %s says it was "
				"delivered %d and holds %d; the market delivered it %d and it holds "
				"%d, and neither is anybody else's to write"),
				*Stalls[i].Goods.ToString(), Came, Holds, Stalls[i].StagedDelivered,
				Stalls[i].StagedCapacity);
			return false;
		}
		int32 MirrorP = 0;
		int32 MirrorS = 0;
		int32 MirrorO = 0;
		GetIntProp(A, TEXT("LastShownPrice"), MirrorP);
		GetIntProp(A, TEXT("LastShownStock"), MirrorS);
		GetIntProp(A, TEXT("LastShownOwned"), MirrorO);
		if (MirrorP != P || MirrorS != S || MirrorO != O)
		{
			Why = FString::Printf(TEXT("the sign on the stall selling %s reads [%s] "
				"but the stall reports last showing %d / %d / %d"),
				*Stalls[i].Goods.ToString(), *SignText, MirrorP, MirrorS, MirrorO);
			return false;
		}
		Out.Price[i] = P;
		Out.Stock[i] = S;
		Out.Owned[i] = O;
	}
	return true;
}

// ---------------------------------------------------------------------------
// The walk
// ---------------------------------------------------------------------------

void AMarketDayFunctionalTest::BuildRoute(int32 FirstStepIndex, int32 StepCount)
{
	Route.Reset();
	Waypoint = 0;
	DwellUntil = -1.0;
	bHaveWas = false;
	if (!Hero.IsValid())
	{
		return;
	}
	const double Z = Hero->GetActorLocation().Z;

	for (int32 k = 0; k < StepCount; ++k)
	{
		const int32 Global = FirstStepIndex + k;
		const int32 i = Steps[Global].Stall;

		FLeg Before;
		Before.Target = FVector(Stalls[i].LanePoint.X, Stalls[i].LanePoint.Y, Z);
		Before.Dwell = kLaneBeforeS;
		Before.Stall = i;
		Before.Step = Global;
		Before.Kind = 0;
		Route.Add(Before);

		FLeg OnMat;
		OnMat.Target = FVector(Stalls[i].MatCentre.X, Stalls[i].MatCentre.Y, Z);
		OnMat.Dwell = kMatDwellS;
		OnMat.Stall = i;
		OnMat.Step = Global;
		OnMat.Kind = 1;
		Route.Add(OnMat);

		FLeg After = Before;
		After.Dwell = kLaneAfterS;
		After.Kind = 2;
		Route.Add(After);
	}

	FLeg Gate;
	Gate.Target = FVector(GatePoint.X, GatePoint.Y, Z);
	Gate.Dwell = kGateDwellS;
	Gate.Kind = 3;
	Route.Add(Gate);
}

bool AMarketDayFunctionalTest::CheckRouteIsWalkable()
{
	// A route that walks through a counter jams the character and the run simply
	// stops, which reads as the submission's fault. A lane point that clips a mat
	// buys something nobody asked for. Both are the YARD's fault, so both are an
	// attributed Error.
	for (int32 s = 0; s < Route.Num(); ++s)
	{
		const bool bOnMat = (Route[s].Kind == 1);
		for (int32 i = 0; i < Stalls.Num(); ++i)
		{
			if (FVector::Dist2D(Route[s].Target, Stalls[i].Home)
				< kMinCounterClearanceUu)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: waypoint %d stands %.0f uu from the "
						 "counter of the stall selling %s; the character would be "
						 "pushing it"), s,
					FVector::Dist2D(Route[s].Target, Stalls[i].Home),
					*Stalls[i].Goods.ToString()));
				return false;
			}
			if (!bOnMat && i != Route[s].Stall)
			{
				const double D = FVector::Dist2D(Route[s].Target, Stalls[i].MatCentre);
				if (D < kMinMatClearanceUu)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: waypoint %d stands %.0f uu from "
							 "the mat of the stall selling %s, close enough to be "
							 "standing on it"), s, D, *Stalls[i].Goods.ToString()));
					return false;
				}
			}
		}
	}
	// And no leg of the walk may pass through a counter on its way.
	for (int32 s = 0; s + 1 < Route.Num(); ++s)
	{
		constexpr int32 kSamples = 40;
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector P = FMath::Lerp(Route[s].Target, Route[s + 1].Target,
				double(k) / double(kSamples));
			for (int32 i = 0; i < Stalls.Num(); ++i)
			{
				if (FVector::Dist2D(P, Stalls[i].Home) < kMinCounterClearanceUu)
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: the walk from waypoint %d to %d "
							 "passes %.0f uu from the counter of the stall selling "
							 "%s; the character would jam against it"), s, s + 1,
						FVector::Dist2D(P, Stalls[i].Home),
						*Stalls[i].Goods.ToString()));
					return false;
				}
			}
		}
	}
	return true;
}

void AMarketDayFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Waypoint) || !Hero.IsValid())
	{
		return;
	}
	const FLeg Leg = Route[Waypoint];
	const FVector Here = Hero->GetActorLocation();
	const FVector Flat(Leg.Target.X - Here.X, Leg.Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() > kWaypointUu)
	{
		// THE SAME INPUT PATH A HUMAN USES.
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
		return;
	}
	if (DwellUntil < 0.0)
	{
		// STAND here. Every gate is about a state that has settled, and a route that
		// only passes through a spot never gives the yard a chance to be judged.
		DwellUntil = Now + Leg.Dwell;
		if (Leg.Kind == 1)
		{
			StabilityArmAt = Now + kStabilityArmS;
			bStabilityArmed = false;
		}
		return;
	}
	if (Now < DwellUntil)
	{
		return;
	}

	FString Why;
	if (Leg.Kind == 0)
	{
		FReadout Sample;
		if (!ReadYard(Sample, Why))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSignsSayWhatTheYardShows: %s"), *Why));
			return;
		}
		if (!bBaselineChecked)
		{
			bBaselineChecked = true;
			bool bAsStaged = (Sample.Coins == Set->OpenCoins);
			for (int32 i = 0; i < 3; ++i)
			{
				bAsStaged = bAsStaged && Sample.Price[i] == Set->Open[i].Price
					&& Sample.Stock[i] == Set->Open[i].Stock && Sample.Owned[i] == 0;
			}
			if (!bAsStaged)
			{
				// ATTRIBUTED, NOT SCORED. The overwhelmingly likely cause is a day
				// written down by an earlier run in this same workdir that the
				// fixture's wipe could not reach -- which is a state fault, not a
				// model fault. Run it in a clean workdir before believing anything
				// else.
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: the yard did not open on the numbers "
						 "the fixture staged (board %d, expected %d; stalls %d/%d "
						 "%d/%d %d/%d, expected %d/%d %d/%d %d/%d). A record left "
						 "behind by an earlier run in this workdir is the usual "
						 "cause"),
					Sample.Coins, Set->OpenCoins,
					Sample.Price[0], Sample.Stock[0], Sample.Price[1], Sample.Stock[1],
					Sample.Price[2], Sample.Stock[2],
					Set->Open[0].Price, Set->Open[0].Stock,
					Set->Open[1].Price, Set->Open[1].Stock,
					Set->Open[2].Price, Set->Open[2].Stock));
				return;
			}
		}
		Was = Sample;
		bHaveWas = true;
	}
	else if (Leg.Kind == 1)
	{
		bStabilityArmed = false;
	}
	else if (Leg.Kind == 2)
	{
		FReadout Sample;
		if (!ReadYard(Sample, Why))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSignsSayWhatTheYardShows: %s"), *Why));
			return;
		}
		if (bHaveWas)
		{
			GradeStep(StepAt(Leg.Step), Was, Sample);
			if (!IsRunning())
			{
				return;
			}
			++StepsDone;
			bHaveWas = false;
		}
	}
	else
	{
		if (!bReopened)
		{
			CloseTheYard();
		}
		else
		{
			FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
				TEXT("The market day finished: %d steps, the yard closed and reopened "
					 "on staged set %d, and every sign and the gate board told the "
					 "truth throughout"), StepsDone, SetIndex));
		}
		return;
	}

	++Waypoint;
	DwellUntil = -1.0;
}

void AMarketDayFunctionalTest::CloseTheYard()
{
	StallRebuilds.Reset();
	RebuildClasses.Reset();
	for (const FStall& S : Stalls)
	{
		AActor* const A = S.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		FRebuild R;
		R.Cls = A->GetClass();
		R.Xform = A->GetActorTransform();
		R.Goods = S.Goods;
		StallRebuilds.Add(R);
		RebuildClasses.Add(R.Cls);
	}
	if (AActor* const L = Ledger.Get())
	{
		LedgerRebuild.Cls = L->GetClass();
		LedgerRebuild.Xform = L->GetActorTransform();
		LedgerRebuild.Goods = NAME_None;
		RebuildClasses.Add(LedgerRebuild.Cls);
	}

	// The yard is taken away. The stalls' and the board's EndPlay run here -- a
	// perfectly legitimate place for a submission to write the day down, which is
	// why the fixture does not care where it was written.
	for (const FStall& S : Stalls)
	{
		if (AActor* const A = S.Actor.Get())
		{
			A->Destroy();
		}
	}
	if (AActor* const L = Ledger.Get())
	{
		L->Destroy();
	}
	bYardDown = true;
	bAwaitingRebuild = true;
}

void AMarketDayFunctionalTest::ReopenTheYard(double Now)
{
	bAwaitingRebuild = false;
	UWorld* const World = GetWorld();
	if (World == nullptr || StallRebuilds.Num() != 3 || LedgerRebuild.Cls == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the yard could not be put back together"));
		return;
	}

	for (int32 i = 0; i < 3; ++i)
	{
		// ONE PLACE FURTHER ALONG THE ROW, so every stall moves and none of them can
		// be found where it was left.
		const FTransform& Where = StallRebuilds[(i + 1) % 3].Xform;
		// OverrideRootScale, not the default MultiplyWithRoot: the transform captured
		// off the destroyed stall ALREADY carries the counter's (2,1,2) root scale,
		// and multiplying it by the fresh actor's default would spawn a stall at
		// (4,1,4) for the length of the deferred window -- with the mat's box extent
		// scaled with it. FinishSpawning below defaults to OverrideRootScale, so this
		// only makes the two ends agree.
		AActor* const A = World->SpawnActorDeferred<AActor>(StallRebuilds[i].Cls,
			Where, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn,
			ESpawnActorScaleMethod::OverrideRootScale);
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: the stall selling %s could not be put "
					 "back"), *StallRebuilds[i].Goods.ToString()));
			return;
		}
		// DEFERRED on purpose: a fresh stall paints its sign in BeginPlay, so what it
		// sells, what it now charges, what it was delivered and what it can hold all
		// have to be on it BEFORE that runs, or a correct submission would be failed
		// for the fixture's own ordering.
		SetNameProp(A, TEXT("GoodsName"), StallRebuilds[i].Goods);
		SetIntProp(A, TEXT("PriceCoins"), Set->Reopen[i].Price);
		SetIntProp(A, TEXT("StockCount"), Set->Reopen[i].Stock);
		SetIntProp(A, TEXT("StockCapacity"), Set->Reopen[i].Capacity);
		SetIntProp(A, TEXT("DeliveredSinceClose"), Set->Reopen[i].Delivered);
		A->FinishSpawning(Where);
	}

	AActor* const L = World->SpawnActorDeferred<AActor>(LedgerRebuild.Cls,
		LedgerRebuild.Xform, nullptr, nullptr,
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn,
		ESpawnActorScaleMethod::OverrideRootScale);
	if (L == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the board by the gate could not be put back"));
		return;
	}
	// A BRAND NEW board says what the day STARTS with. A submission with no record
	// shows exactly that, which is the tell.
	SetIntProp(L, TEXT("StartingCoins"), Set->OpenCoins);
	SetIntProp(L, TEXT("CarryLimit"), Set->CarryLimit);
	L->FinishSpawning(LedgerRebuild.Xform);

	if (!ResolveYard(false))
	{
		return;
	}
	RecordStaged(Set->Reopen);
	SettleUntil = Now + kReopenSettleS;
}

// ---------------------------------------------------------------------------
// Grading
// ---------------------------------------------------------------------------

void AMarketDayFunctionalTest::GradeStep(const FStep& Step, const FReadout& Before,
	const FReadout& After)
{
	const int32 i = Step.Stall;
	const FString Goods = Stalls[i].Goods.ToString();

	if (Step.Want == EMarketWant::Buy)
	{
		if (After.Coins != Step.CoinsAfter)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("EachStallChargesItsOwnCurrentPrice: after stepping onto the mat "
					 "of the stall selling %s the gate board should read %d coins and "
					 "it reads %d. It read %d before the step and that stall is "
					 "asking %d"), *Goods, Step.CoinsAfter, After.Coins, Before.Coins,
				Stalls[i].StagedPrice));
			return;
		}
		if (After.Stock[i] != Step.StockAfter || After.Owned[i] != Step.OwnedAfter)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("OneStepOntoTheMatBuysExactlyOne: one step onto the mat of the "
					 "stall selling %s should leave it with %d left and %d yours; its "
					 "sign says %d left and %d yours. Before the step it said %d and "
					 "%d"), *Goods, Step.StockAfter, Step.OwnedAfter, After.Stock[i],
				After.Owned[i], Before.Stock[i], Before.Owned[i]));
			return;
		}
	}
	else
	{
		const bool bMoved = (After.Coins != Before.Coins)
			|| (After.Stock[i] != Before.Stock[i])
			|| (After.Owned[i] != Before.Owned[i]);
		if (bMoved)
		{
			if (Step.Want == EMarketWant::NoStock)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("SoldOutStaysSoldOut: the stall selling %s has none left and "
						 "the step onto its mat still changed something -- coins %d "
						 "to %d, left %d to %d, yours %d to %d. The purse was "
						 "carrying %d and that stall is asking %d, so money was never "
						 "the question"), *Goods, Before.Coins, After.Coins,
					Before.Stock[i], After.Stock[i], Before.Owned[i], After.Owned[i],
					Before.Coins, Stalls[i].StagedPrice));
			}
			else if (Step.Want == EMarketWant::HandsFull)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("YourHandsAreOnlySoBig: you were already carrying %d of what "
						 "the stall selling %s is selling, which is all you can "
						 "carry, and the step onto its mat still changed something -- "
						 "coins %d to %d, left %d to %d, yours %d to %d. It had %d in "
						 "stock and the purse could pay the %d it asks"),
					Before.Owned[i], *Goods, Before.Coins, After.Coins,
					Before.Stock[i], After.Stock[i], Before.Owned[i], After.Owned[i],
					Before.Stock[i], Stalls[i].StagedPrice));
			}
			else
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("ARefusedSaleCostsNothing: %d coins cannot pay the %d the "
						 "stall selling %s is asking, and the step onto its mat still "
						 "changed something -- coins %d to %d, left %d to %d, yours "
						 "%d to %d"), Before.Coins, Stalls[i].StagedPrice, *Goods,
					Before.Coins, After.Coins, Before.Stock[i], After.Stock[i],
					Before.Owned[i], After.Owned[i]));
			}
			return;
		}
	}

	// Whatever the step did, it did it to ONE stall.
	for (int32 k = 0; k < Stalls.Num(); ++k)
	{
		if (k == i)
		{
			continue;
		}
		if (After.Stock[k] != Before.Stock[k] || After.Owned[k] != Before.Owned[k])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("OneStepOntoTheMatBuysExactlyOne: a step onto the mat of the "
					 "stall selling %s also moved the stall selling %s, whose sign "
					 "went from %d left and %d yours to %d left and %d yours"),
				*Goods, *Stalls[k].Goods.ToString(), Before.Stock[k],
				Before.Owned[k], After.Stock[k], After.Owned[k]));
			return;
		}
	}
}

void AMarketDayFunctionalTest::GradeReopening(const FReadout& After)
{
	if (After.Coins != ReopenCoins)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheYardRemembersWhatYouSpent: the day closed with %d coins in the "
				 "purse and the yard reopened with the board reading %d. The board is "
				 "new and the purse is not"), ReopenCoins, After.Coins));
		return;
	}
	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		if (After.Stock[i] != ReopenStock[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardRemembersWhatYouSpent: the stall selling %s closed with "
					 "%d left and was delivered %d while the yard was shut, and it "
					 "holds at most %d, so it should reopen with %d left; its sign "
					 "says %d"), *Stalls[i].Goods.ToString(), ClosingStock[i],
				Stalls[i].StagedDelivered, Stalls[i].StagedCapacity, ReopenStock[i],
				After.Stock[i]));
			return;
		}
		if (After.Owned[i] != ReopenOwned[i])
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardRemembersWhatYouSpent: you were carrying %d of what the "
					 "stall selling %s sells when the yard shut, and its fresh sign "
					 "says %d yours"), ReopenOwned[i], *Stalls[i].Goods.ToString(),
				After.Owned[i]));
			return;
		}
	}
}

bool AMarketDayFunctionalTest::CheckAlwaysTrue(double Now, float DeltaSeconds)
{
	ACharacter* const H = Hero.Get();
	if (H == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheBuyerKeepsWalking: the player character stopped existing part "
				 "way through the day"));
		return false;
	}
	// BUYING NEVER TAKES THE CHARACTER AWAY FROM THE PLAYER. Each of these is a
	// separate way to freeze somebody at a till, and each is readable.
	if (!H->InputEnabled())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheBuyerKeepsWalking: the character's controls were taken away "
				 "part way through the day and not given back"));
		return false;
	}
	if (H->IsMoveInputIgnored())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TheBuyerKeepsWalking: the character's movement input is being "
				 "ignored part way through the day"));
		return false;
	}
	const UCharacterMovementComponent* const Move = H->GetCharacterMovement();
	if (Move == nullptr || Move->MovementMode == MOVE_None
		|| Move->GetMaxSpeed() <= 0.0f)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheBuyerKeepsWalking: the character can no longer walk (movement "
				 "mode %d, top speed %.0f)"),
			Move != nullptr ? int32(Move->MovementMode.GetValue()) : -1,
			Move != nullptr ? Move->GetMaxSpeed() : 0.0f));
		return false;
	}
	const FVector HereNow = H->GetActorLocation();
	// The first second is grace: the character is dropped onto the floor from the
	// PlayerStart and the very first ticks of a PIE session can carry an unusual dt.
	// A shove that matters is hundreds of uu and happens long after this.
	if (bHeroWasValid && Now > 1.0)
	{
		const double Moved = FVector::Dist2D(HereNow, HeroWas);
		const double Bound = FMath::Max(kShoveFloorUu,
			double(Move->GetMaxSpeed()) * double(DeltaSeconds) * kShoveFactor);
		if (Moved > Bound)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheBuyerKeepsWalking: the character travelled %.0f uu in one "
					 "frame, which is more than %.0f uu of walking -- it was moved, "
					 "not walked"), Moved, Bound));
			return false;
		}
	}
	HeroWas = HereNow;
	bHeroWasValid = true;

	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		const AActor* const A = Stalls[i].Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheYardsOwnNumbersAreStillThere: the stall selling %s stopped "
					 "existing part way through the day"),
				*Stalls[i].Goods.ToString()));
			return false;
		}
		FName Goods = NAME_None;
		if (!GetNameProp(A, TEXT("GoodsName"), Goods) || Goods != Stalls[i].Goods)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("AStallIsKnownByWhatItSells: a stall that was selling %s now "
					 "says it sells %s"), *Stalls[i].Goods.ToString(),
				*Goods.ToString()));
			return false;
		}
		// THE MARKET'S PRICE, compared against what the FIXTURE staged -- never
		// against the stall's own live number, because a submission that wrote a
		// remembered price back onto the stall would satisfy shown-equals-live and
		// sail through.
		int32 LivePrice = 0;
		GetIntProp(A, TEXT("PriceCoins"), LivePrice);
		if (LivePrice != Stalls[i].StagedPrice)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheStallsAreTheMarketsToPrice: the stall selling %s is asking "
					 "%d and the market has it at %d. What a stall charges is the "
					 "market's business, never yours to write"),
				*Stalls[i].Goods.ToString(), LivePrice, Stalls[i].StagedPrice));
			return false;
		}
		int32 ShownPrice = 0;
		GetIntProp(A, TEXT("LastShownPrice"), ShownPrice);
		if (ShownPrice != Stalls[i].StagedPrice)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheStallsAreTheMarketsToPrice: the sign on the stall selling %s "
					 "says %d and the market has it at %d"),
				*Stalls[i].Goods.ToString(), ShownPrice, Stalls[i].StagedPrice));
			return false;
		}
		int32 ShownStock = 0;
		GetIntProp(A, TEXT("LastShownStock"), ShownStock);
		if (ShownStock < 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SoldOutStaysSoldOut: the sign on the stall selling %s says it "
					 "has %d left. No stall ever has less than none"),
				*Stalls[i].Goods.ToString(), ShownStock));
			return false;
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

void AMarketDayFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld"));
		return;
	}
	if (Set == nullptr || Stalls.Num() != 3)
	{
		// ResolveYard already reported the reason during world init.
		return;
	}
	if (!ResolveHero())
	{
		return;
	}
	if (!BuildStepTrace())
	{
		return;
	}
	BuildRoute(0, Round1Count);
	if (!CheckRouteIsWalkable())
	{
		return;
	}

	// The last entry is a SENTINEL, far past a walk that measures ~130 s at 500 uu/s,
	// because the base class ends the test the moment the last scheduled checkpoint
	// is sampled. Without it, a submission that never lets the walk get anywhere
	// would ride an automatic Success.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kSentinelIndex; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
}

void AMarketDayFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || Set == nullptr || Stalls.Num() != 3)
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = (World != nullptr) ? double(World->GetTimeSeconds()) : 0.0;

	if (bYardDown)
	{
		// The yard is empty for exactly one frame, then it is put back and given
		// time to settle. Nothing is graded while there is nothing to read.
		if (bAwaitingRebuild)
		{
			ReopenTheYard(Now);
			return;
		}
		if (Now < SettleUntil)
		{
			return;
		}
		FReadout Sample;
		FString Why;
		if (!ReadYard(Sample, Why))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSignsSayWhatTheYardShows: %s"), *Why));
			return;
		}
		GradeReopening(Sample);
		if (!IsRunning())
		{
			return;
		}
		bYardDown = false;
		bReopened = true;
		bHeroWasValid = false;
		BuildRoute(Round1Count, Steps.Num() - Round1Count);
		if (!CheckRouteIsWalkable())
		{
			return;
		}
		return;
	}

	if (!CheckAlwaysTrue(Now, DeltaSeconds))
	{
		return;
	}

	// STANDING ON A MAT DOES NOT KEEP BUYING. Armed a while after the character has
	// settled on the mat -- long past the half second the prompt allows a sale -- and
	// narrowed to the stall being stood on and the gate board, which is exactly what
	// the sentence it grades talks about.
	if (Route.IsValidIndex(Waypoint) && Route[Waypoint].Kind == 1 && DwellUntil > 0.0)
	{
		const int32 i = Route[Waypoint].Stall;
		FReadout Sample;
		FString Why;
		if (ReadYard(Sample, Why))
		{
			if (!bStabilityArmed && Now >= StabilityArmAt)
			{
				OnMatSnapshot = Sample;
				bStabilityArmed = true;
			}
			else if (bStabilityArmed
				&& (Sample.Coins != OnMatSnapshot.Coins
					|| Sample.Stock[i] != OnMatSnapshot.Stock[i]
					|| Sample.Owned[i] != OnMatSnapshot.Owned[i]))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("OneStepOntoTheMatBuysExactlyOne: the character has been "
						 "standing still on the mat of the stall selling %s and the "
						 "yard kept changing under it -- coins %d then %d, left %d "
						 "then %d, yours %d then %d. Standing on a mat is not buying "
						 "again"), *Stalls[i].Goods.ToString(), OnMatSnapshot.Coins,
					Sample.Coins, OnMatSnapshot.Stock[i], Sample.Stock[i],
					OnMatSnapshot.Owned[i], Sample.Owned[i]));
				return;
			}
		}
	}

	DriveHero(Now);
}

void AMarketDayFunctionalTest::LogCalib(int32 Index, double Now) const
{
	FString S;
	for (int32 i = 0; i < Stalls.Num(); ++i)
	{
		int32 P = 0;
		int32 K = 0;
		int32 O = 0;
		GetIntProp(Stalls[i].Actor.Get(), TEXT("LastShownPrice"), P);
		GetIntProp(Stalls[i].Actor.Get(), TEXT("LastShownStock"), K);
		GetIntProp(Stalls[i].Actor.Get(), TEXT("LastShownOwned"), O);
		S += FString::Printf(TEXT("%s[p%d l%d y%d] "), *Stalls[i].Goods.ToString(),
			P, K, O);
	}
	int32 C = 0;
	GetIntProp(Ledger.Get(), TEXT("LastShownCoins"), C);
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	UE_LOG(LogTemp, Display,
		TEXT("[t2-market calib] cp%d t=%.2f set=%d step=%d/%d wp=%d/%d reopened=%d "
			 "coins=%d %sat=(%.0f,%.0f)"),
		Index, Now, SetIndex, StepsDone, Steps.Num(), Waypoint, Route.Num(),
		bReopened ? 1 : 0, C, *S, H.X, H.Y);
}

void AMarketDayFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex)
	{
		return;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("TheMarketDayFinished: the day never finished -- %d of %d steps done, "
			 "the yard %s reopened, and the walk is stuck at waypoint %d of %d. "
			 "Buying must never take the character away from the player"),
		StepsDone, Steps.Num(), bReopened ? TEXT("had") : TEXT("had not"),
		Waypoint, Route.Num()));
}
