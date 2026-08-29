// Copyright CraftBench. All Rights Reserved.

#include "ForgeCraftFunctionalTest.h"

#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---- DISCLOSED in the prompt -------------------------------------------
	// "Within half a second of play beginning, and within half a second of anything
	//  changing what the forge is holding or what you have read, both faces read the
	//  truth" and "within half a second of you coming that close the heap holds exactly
	//  what you left standing".
	constexpr double kSettleS = 0.5;

	// ---- UNDISCLOSED: fixture clocking and staging --------------------------
	constexpr double kWaypointUu = 70.0;      // arrival tolerance
	constexpr double kPlaqueDwellS = 2.0;     // long enough for a 1 Hz poller to read
	constexpr double kPadDwellS = 1.0;
	constexpr double kForgeDwellS = 1.5;
	constexpr double kProductDwellS = 1.5;
	constexpr double kSentinelS = 240.0;
	constexpr int32 kSentinelIndex = 23;      // 10..230 by 10, then the sentinel

	// A route sample is either PLAINLY at the thing it went to, or PLAINLY clear of
	// everything else. Nothing is ever graded from a marginal distance, because the
	// fixture and the submission would then be free to disagree about one frame.
	constexpr double kAtFactor = 0.5;
	constexpr double kClearFactor = 1.6;
	constexpr double kAnvilClearUu = 180.0;   // the anvil is 200 uu across, ~141 to a corner
	constexpr double kPadClaimUu = 250.0;     // a heap this close to a pad IS that pad's
	// A submission may measure "close enough" in 3D, or off a bounds sphere, and so
	// fire a frame or two either side of the fixture's flat test. Both slacks exist to
	// absorb exactly that, and both are far smaller than the clearances the hall is laid
	// out with (the nearest an unintended pad ever gets to the walk is 400 uu, and
	// deliveries are seconds apart).
	constexpr double kEarlyTakeUu = 60.0;
	constexpr double kEarlyCraftS = 0.10;
	constexpr double kPlaqueStandInUu = 150.0;

	// THE LANE BEHIND THE FORGE is solved, not chosen. It has to clear the forge's own
	// take reach by this factor -- a walker hauling three units down it would otherwise
	// hand them over halfway -- and clear every shelf-stone's reach by kClearFactor, or
	// it would pick up whatever is standing there in passing. The same arithmetic runs
	// in authoring/author_map.py before the level will save.
	constexpr double kForgeLaneClearFactor = 1.3;
	// The heap class's own default reach, which is what the forge's own outputs spawn
	// with. Used ONLY to solve the lane; every product is graded against its own live
	// ReachUu.
	constexpr double kProductReachAssumedUu = 220.0;
	// The band around a delivery in which the faces are not compared: a submission is
	// free to cross into the forge's reach a frame or two before the fixture's flat
	// test does, and for that frame its faces are ahead of the fixture's model.
	constexpr double kHandoverBandFactor = 1.4;

	// ---- what the hall carves and stocks ------------------------------------
	// THE CHAIN. Two steps, three units each: nine of the base unit become three of the
	// middle unit become the one thing at the top. Written here as the carvings a human
	// reads off the wall, step included, because the step is what decides which of two
	// recipes that both fit gets made.
	const TCHAR* const kCarvingTierOne = TEXT("TIER 1 : EMBER EMBER EMBER -> SLAG");
	const TCHAR* const kCarvingTierTwo = TEXT("TIER 2 : SLAG SLAG SLAG -> BLADE");
	// The re-carve. Same output, same step, a DIFFERENT input -- so a submission that
	// stored the parsed recipe instead of the carving goes on making SLAG out of a
	// material this recipe no longer names.
	const TCHAR* const kCarvingRecarved = TEXT("TIER 1 : CINDER CINDER CINDER -> SLAG");

	const TCHAR* const kBaseId = TEXT("EMBER");
	const TCHAR* const kRestockId = TEXT("CINDER");

	// What stands on each pad, by pad index (sorted by X, then by Y). 21 units of base
	// material against the 9 the chain needs, so a submission that wastes a trip is not
	// starved -- and two pads the walk never approaches, which have to still be standing
	// at the end.
	const int32 kStockUnits[8] = { 2, 2, 1, 4, 3, 3, 3, 3 };

	// The two caps the hall posts, in order. The second is smaller, so a cap read once
	// when play began takes one unit too many the first time it is used afterwards.
	constexpr int32 kCapPhase0 = 3;
	constexpr int32 kCapPhase1 = 2;
	// Which pad gets re-stocked with the new material at the re-stage, and with how
	// much. STRICTLY MORE THAN kCapPhase1: the whole point of the re-stock is that a
	// submission still using the cap it read when play began takes one unit too many and
	// the pad is left standing empty where it should be left standing with one.
	constexpr int32 kRestockPad = 0;
	constexpr int32 kRestockUnits = 3;

	FString Squeeze(const FString& In)
	{
		FString Out;
		Out.Reserve(In.Len());
		bool bSpace = false;
		for (const TCHAR C : In)
		{
			if (FChar::IsWhitespace(C)) { bSpace = true; continue; }
			if (bSpace && Out.Len() > 0) { Out.AppendChar(TEXT(' ')); }
			bSpace = false;
			Out.AppendChar(C);
		}
		return Out.ToUpper();
	}
}

AForgeCraftFunctionalTest::AForgeCraftFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------- reflection

FString AForgeCraftFunctionalTest::ReadStr(const AActor* A, const TCHAR* Prop)
{
	if (A == nullptr) { return FString(); }
	const FStrProperty* const P = FindFProperty<FStrProperty>(A->GetClass(), Prop);
	return P ? P->GetPropertyValue_InContainer(A) : FString();
}

bool AForgeCraftFunctionalTest::WriteStr(AActor* A, const TCHAR* Prop,
	const FString& Value)
{
	if (A == nullptr) { return false; }
	const FStrProperty* const P = FindFProperty<FStrProperty>(A->GetClass(), Prop);
	if (P == nullptr) { return false; }
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

FName AForgeCraftFunctionalTest::ReadName(const AActor* A, const TCHAR* Prop)
{
	if (A == nullptr) { return NAME_None; }
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Prop);
	return P ? P->GetPropertyValue_InContainer(A) : NAME_None;
}

bool AForgeCraftFunctionalTest::WriteName(AActor* A, const TCHAR* Prop, FName Value)
{
	if (A == nullptr) { return false; }
	const FNameProperty* const P = FindFProperty<FNameProperty>(A->GetClass(), Prop);
	if (P == nullptr) { return false; }
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

int32 AForgeCraftFunctionalTest::ReadInt(const AActor* A, const TCHAR* Prop,
	int32 Fallback)
{
	if (A == nullptr) { return Fallback; }
	const FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Prop);
	return P ? P->GetPropertyValue_InContainer(A) : Fallback;
}

bool AForgeCraftFunctionalTest::WriteInt(AActor* A, const TCHAR* Prop, int32 Value)
{
	if (A == nullptr) { return false; }
	const FIntProperty* const P = FindFProperty<FIntProperty>(A->GetClass(), Prop);
	if (P == nullptr) { return false; }
	P->SetPropertyValue_InContainer(A, Value);
	return true;
}

float AForgeCraftFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Prop,
	float Fallback)
{
	if (A == nullptr) { return Fallback; }
	const FFloatProperty* const P = FindFProperty<FFloatProperty>(A->GetClass(), Prop);
	return P ? P->GetPropertyValue_InContainer(A) : Fallback;
}

UTextRenderComponent* AForgeCraftFunctionalTest::FindText(AActor* On, const TCHAR* Name)
{
	if (On == nullptr) { return nullptr; }
	// By NAME, not by index: the prompt says the two faces must be kept and that more
	// may be added on top, so the first text component found is not enough.
	TArray<UTextRenderComponent*> Texts;
	On->GetComponents<UTextRenderComponent>(Texts);
	for (UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == Name) { return T; }
	}
	return nullptr;
}

FString AForgeCraftFunctionalTest::ReadFace(AActor* On, const TCHAR* Name)
{
	const UTextRenderComponent* const T = FindText(On, Name);
	return T ? T->Text.ToString() : FString();
}

bool AForgeCraftFunctionalTest::HeapIsGone(const AActor* H)
{
	// EVERY WAY A HEAP CAN LEGITIMATELY LEAVE THE HALL. The prompt describes an outcome
	// and never names a mechanism, so destroying the actor, hiding the actor, hiding the
	// pile, and emptying it all have to count. Grading only the component's own hidden
	// flag would have failed a submission that called SetActorHiddenInGame, which cannot
	// be seen from USceneComponent::IsVisible at all.
	if (H == nullptr || !IsValid(H)) { return true; }
	if (H->IsHidden()) { return true; }
	if (ReadInt(H, TEXT("UnitsInHeap"), 1) <= 0) { return true; }
	TArray<USceneComponent*> Comps;
	const_cast<AActor*>(H)->GetComponents<USceneComponent>(Comps);
	for (const USceneComponent* C : Comps)
	{
		if (C != nullptr && C->GetName() == TEXT("Heap"))
		{
			return !C->IsVisible() || C->bHiddenInGame;
		}
	}
	return false;
}

int32 AForgeCraftFunctionalTest::LiveUnits(const AActor* H)
{
	if (HeapIsGone(H)) { return 0; }
	return FMath::Max(ReadInt(H, TEXT("UnitsInHeap"), 0), 0);
}

// ------------------------------------------------------- the world's answer

void AForgeCraftFunctionalTest::ParseCarving(const FString& Carved, int32& OutTier,
	TArray<FName>& OutInputs, FName& OutOutput)
{
	OutTier = 0;
	OutInputs.Reset();
	OutOutput = NAME_None;

	FString Body = Carved;
	FString Head, Tail;
	if (Body.Split(TEXT(":"), &Head, &Tail))
	{
		Head.ToUpperInline();
		TArray<FString> HeadTokens;
		Head.ParseIntoArrayWS(HeadTokens);
		if (HeadTokens.Num() == 2 && HeadTokens[0] == TEXT("TIER")
			&& HeadTokens[1].IsNumeric())
		{
			OutTier = FCString::Atoi(*HeadTokens[1]);
			Body = Tail;
		}
	}

	FString Left, Right;
	if (!Body.Split(TEXT("->"), &Left, &Right)) { return; }
	TArray<FString> L, R;
	Left.ToUpperInline();
	Right.ToUpperInline();
	Left.ParseIntoArrayWS(L);
	Right.ParseIntoArrayWS(R);
	if (L.Num() == 0 || R.Num() != 1) { OutTier = 0; return; }
	for (const FString& T : L) { OutInputs.Add(FName(*T)); }
	OutOutput = FName(*R[0]);
}

bool AForgeCraftFunctionalTest::Contains(const TMap<FName, int32>& Have,
	const TArray<FName>& Need)
{
	// MULTIPLICITIES. "EMBER EMBER EMBER" needs THREE EMBER; a set-shaped containment
	// test passes on one, which is why the count is folded up before comparing.
	TMap<FName, int32> Want;
	for (const FName& N : Need) { Want.FindOrAdd(N) += 1; }
	for (const TPair<FName, int32>& P : Want)
	{
		const int32* const Got = Have.Find(P.Key);
		if (Got == nullptr || *Got < P.Value) { return false; }
	}
	return true;
}

FString AForgeCraftFunctionalTest::FormatHeld(const TMap<FName, int32>& Held)
{
	TArray<FName> Keys;
	for (const TPair<FName, int32>& P : Held)
	{
		if (P.Value > 0) { Keys.Add(P.Key); }
	}
	if (Keys.Num() == 0) { return TEXT("EMPTY"); }
	Keys.Sort([](const FName& A, const FName& B)
	{
		return A.ToString() < B.ToString();
	});
	FString S;
	for (int32 i = 0; i < Keys.Num(); ++i)
	{
		S += FString::Printf(TEXT("%s%s x%d"), i ? TEXT(" ") : TEXT(""),
			*Keys[i].ToString(), Held[Keys[i]]);
	}
	return S;
}

bool AForgeCraftFunctionalTest::ParseHeldFace(const FString& Face,
	TMap<FName, int32>& Out)
{
	Out.Reset();
	const FString S = Squeeze(Face);
	if (S == TEXT("EMPTY")) { return true; }
	TArray<FString> Tok;
	S.ParseIntoArrayWS(Tok);
	if (Tok.Num() == 0 || (Tok.Num() % 2) != 0) { return false; }
	for (int32 i = 0; i + 1 < Tok.Num(); i += 2)
	{
		const FString& Name = Tok[i];
		const FString& Count = Tok[i + 1];
		if (Name.IsEmpty() || Count.Len() < 2 || Count[0] != TEXT('X')) { return false; }
		const FString Digits = Count.Mid(1);
		if (!Digits.IsNumeric()) { return false; }
		Out.FindOrAdd(FName(*Name)) += FCString::Atoi(*Digits);
	}
	return true;
}

bool AForgeCraftFunctionalTest::IsKnown(const FPlaque& P) const
{
	// READ, AND STILL SAYING WHAT IT SAID. A plaque the character has stood at is known;
	// the moment it is re-carved it is unknown again until somebody goes back.
	return !P.ReadCarving.IsEmpty()
		&& P.ReadCarving == ReadStr(P.Actor.Get(), TEXT("CarvedText"));
}

int32 AForgeCraftFunctionalTest::ChooseRecipe(const TMap<FName, int32>& Held,
	bool bKnownOnly, int32& OutTier, int32& OutFittingCount) const
{
	OutTier = 0;
	OutFittingCount = 0;
	int32 Best = INDEX_NONE;
	for (int32 i = 0; i < Plaques.Num(); ++i)
	{
		const FPlaque& P = Plaques[i];
		if (bKnownOnly && !IsKnown(P)) { continue; }
		int32 Tier = 0;
		TArray<FName> Inputs;
		FName Output = NAME_None;
		ParseCarving(ReadStr(P.Actor.Get(), TEXT("CarvedText")), Tier, Inputs, Output);
		if (Inputs.Num() == 0 || Output.IsNone()) { continue; }
		if (!Contains(Held, Inputs)) { continue; }
		++OutFittingCount;
		// THE HIGHEST STEP CARVED. Every recipe in this hall takes the same three units,
		// so a count of units says nothing at all and the step says everything.
		if (Best == INDEX_NONE || Tier > OutTier)
		{
			OutTier = Tier;
			Best = i;
		}
	}
	return Best;
}

int32 AForgeCraftFunctionalTest::PlaqueForOutput(FName Output) const
{
	for (int32 i = 0; i < Plaques.Num(); ++i)
	{
		int32 Tier = 0;
		TArray<FName> Inputs;
		FName Out = NAME_None;
		ParseCarving(ReadStr(Plaques[i].Actor.Get(), TEXT("CarvedText")), Tier, Inputs,
			Out);
		if (Out == Output) { return i; }
	}
	return INDEX_NONE;
}

int32 AForgeCraftFunctionalTest::TierOf(FName Output) const
{
	const int32 Idx = PlaqueForOutput(Output);
	if (Idx == INDEX_NONE) { return 0; }
	int32 Tier = 0;
	TArray<FName> Inputs;
	FName Out = NAME_None;
	ParseCarving(ReadStr(Plaques[Idx].Actor.Get(), TEXT("CarvedText")), Tier, Inputs,
		Out);
	return Tier;
}

int32 AForgeCraftFunctionalTest::CarriedTotal() const
{
	int32 Total = 0;
	for (const TPair<FName, int32>& P : Carried) { Total += P.Value; }
	return Total;
}

void AForgeCraftFunctionalTest::Precondition(const FString& Why)
{
	FinishTest(EFunctionalTestResult::Error,
		FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Why));
}

// -------------------------------------------------------------- staging

bool AForgeCraftFunctionalTest::ResolveHall()
{
	UWorld* const World = GetWorld();

	// A COUNT THE SUBMISSION COULD HAVE INFLATED IS NOT A HARNESS FAULT. Too FEW of
	// anything is the hall failing to stage itself and ends the run attributed; too MANY
	// can only be the submission adding to the hall, and that is graded. Routing both to
	// HARNESS-PRECONDITION would hand every agent a way out of the denominator that
	// needs no correct behaviour at all.
	TArray<AActor*> Forges;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("ForgeStation")), Forges);
	if (Forges.Num() < 1)
	{
		Precondition(TEXT("no actor tagged ForgeStation; the hall has no forge"));
		return false;
	}
	if (Forges.Num() > 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NothingInTheHallMoved: there are %d forges in the hall and the hall "
				 "built one. What is in the hall is not yours to add to"), Forges.Num()));
		return false;
	}
	Forge = Forges[0];
	ForgeAt = Forges[0]->GetActorLocation();
	ForgeReach = ReadFloat(Forges[0], TEXT("TakeReachUu"), -1.0f);
	if (ForgeReach < 100.0f)
	{
		Precondition(TEXT("the forge does not expose TakeReachUu as a readable float, "
			"so the fixture cannot tell how close a delivery has to be"));
		return false;
	}
	if (FindText(Forges[0], TEXT("HeldFace")) == nullptr
		|| FindText(Forges[0], TEXT("CanMakeFace")) == nullptr)
	{
		Precondition(TEXT("the forge is missing HeldFace or CanMakeFace; the two faces "
			"are the readouts this task is graded on and the prompt says to keep them"));
		return false;
	}
	{
		TArray<USceneComponent*> Comps;
		Forges[0]->GetComponents<USceneComponent>(Comps);
		for (const USceneComponent* C : Comps)
		{
			if (C != nullptr && C->GetName().StartsWith(TEXT("Shelf")))
			{
				Stones.Add(C->GetComponentLocation());
			}
		}
	}
	if (Stones.Num() < 8)
	{
		Precondition(FString::Printf(
			TEXT("the forge has %d shelf-stone(s); the prompt says to keep them and the "
				 "run needs somewhere to put what it makes"), Stones.Num()));
		return false;
	}

	// THE LANE, SOLVED. Outside the forge's own take reach by kForgeLaneClearFactor, and
	// clear of every shelf-stone's reach by kClearFactor. Both bounds come off the hall,
	// so a re-authored forge or a moved stone row retunes the walk instead of breaking
	// it silently.
	{
		double MinStoneAbsY = TNumericLimits<double>::Max();
		for (const FVector& St : Stones)
		{
			MinStoneAbsY = FMath::Min(MinStoneAbsY, FMath::Abs(St.Y - ForgeAt.Y));
		}
		const double Low = double(ForgeReach) * kForgeLaneClearFactor;
		const double High = MinStoneAbsY - kProductReachAssumedUu * kClearFactor;
		if (High - Low < 100.0)
		{
			Precondition(FString::Printf(
				TEXT("there is no lane behind the forge: it would have to run further "
					 "than %.0f uu off the line (clear of the forge's %.0f uu reach) and "
					 "nearer than %.0f uu (clear of a shelf-stone's reach), and the "
					 "stones sit %.0f uu off the line"),
				Low, double(ForgeReach), High, MinStoneAbsY));
			return false;
		}
		LaneAbsY = (Low + High) * 0.5;
	}

	TArray<AActor*> Heaps;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("IngredientHeap")), Heaps);
	// Anything already standing on a shelf-stone was set down by the forge, not staged by
	// the hall, so it is a product and not a pad. A submission that crafted during
	// BeginPlay is therefore counted honestly instead of being excused.
	Heaps.RemoveAll([this](const AActor* A)
	{
		for (const FVector& St : Stones)
		{
			if (A != nullptr && FVector::Dist2D(A->GetActorLocation(), St) < 200.0)
			{
				return true;
			}
		}
		return false;
	});
	if (Heaps.Num() < 8)
	{
		Precondition(FString::Printf(
			TEXT("%d heap(s) standing on the hall's pads at the start, expected 8"),
			Heaps.Num()));
		return false;
	}
	if (Heaps.Num() > 8)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NothingVanishesExceptWhatYouCanCarry: there are %d heaps standing off "
				 "the shelf-stones and the hall stocked 8 pads. What is in the hall is "
				 "not yours to add to"), Heaps.Num()));
		return false;
	}
	// The class the hall staged with, kept so a pad whose heap a submission DESTROYED can
	// be re-stocked at the re-stage. Without this the re-stock would silently skip that
	// pad and every gate after it would read garbage.
	HeapClass = Heaps[0]->GetClass();
	Heaps.Sort([](const AActor& L, const AActor& R)
	{
		const FVector A = L.GetActorLocation();
		const FVector B = R.GetActorLocation();
		return FMath::IsNearlyEqual(A.X, B.X, 1.0) ? (A.Y < B.Y) : (A.X < B.X);
	});
	for (AActor* A : Heaps)
	{
		FPad P;
		P.At = A->GetActorLocation();
		P.Heap = A;
		P.Reach = ReadFloat(A, TEXT("ReachUu"), -1.0f);
		if (P.Reach < 50.0f)
		{
			Precondition(TEXT("a heap does not expose ReachUu as a readable float, so "
				"the fixture cannot tell how close you have to be to take it"));
			return false;
		}
		if (FindFProperty<FNameProperty>(A->GetClass(), TEXT("IngredientId")) == nullptr
			|| FindFProperty<FIntProperty>(A->GetClass(), TEXT("UnitsInHeap")) == nullptr)
		{
			Precondition(TEXT("a heap does not expose IngredientId and UnitsInHeap as "
				"readable properties under those names; the hall re-stocks itself "
				"through them and the prompt says to keep them"));
			return false;
		}
		Pads.Add(P);
	}

	TArray<AActor*> Slabs;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RecipePlaque")), Slabs);
	if (Slabs.Num() < 2)
	{
		Precondition(FString::Printf(
			TEXT("%d actor(s) tagged RecipePlaque, and the hall carves 2 -- one step of "
				 "the chain each"), Slabs.Num()));
		return false;
	}
	if (Slabs.Num() > 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NothingInTheHallMoved: there are %d plaques on the wall and the hall "
				 "carved 2. What is in the hall is not yours to add to"), Slabs.Num()));
		return false;
	}
	Slabs.Sort([](const AActor& L, const AActor& R)
	{
		return L.GetName() < R.GetName();
	});
	for (AActor* A : Slabs)
	{
		if (FindFProperty<FStrProperty>(A->GetClass(), TEXT("CarvedText")) == nullptr)
		{
			Precondition(TEXT("a plaque does not expose CarvedText as a readable string; "
				"the wall re-carves itself through it and the prompt says to keep it"));
			return false;
		}
		if (ReadFloat(A, TEXT("ReadReachUu"), -1.0f) < 50.0f)
		{
			Precondition(TEXT("a plaque does not expose ReadReachUu as a readable float, "
				"so the fixture cannot tell how close you have to stand to read it"));
			return false;
		}
		FPlaque P;
		P.Actor = A;
		Plaques.Add(P);
	}

	TArray<AActor*> Signs;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CarrySign")), Signs);
	if (Signs.Num() < 1)
	{
		Precondition(TEXT("no actor tagged CarrySign; the hall posts the carry cap on a "
			"sign and the fixture cannot tell how much a load is without it"));
		return false;
	}
	if (Signs.Num() > 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NothingInTheHallMoved: there are %d carry signs in the hall and the "
				 "hall posted one. What is in the hall is not yours to add to"),
			Signs.Num()));
		return false;
	}
	Sign = Signs[0];
	SignAt = Signs[0]->GetActorLocation();
	if (FindFProperty<FIntProperty>(Signs[0]->GetClass(), TEXT("CarryCapUnits"))
		== nullptr)
	{
		Precondition(TEXT("the sign does not expose CarryCapUnits as a readable int; the "
			"hall re-posts the cap through it and the prompt says to keep it"));
		return false;
	}

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetMesh() == nullptr
		|| Hero->GetMesh()->GetSkeletalMeshAsset() == nullptr)
	{
		Precondition(TEXT("no visibly represented player character in the hall"));
		return false;
	}
	HeroZ = Hero->GetActorLocation().Z;
	return true;
}

bool AForgeCraftFunctionalTest::StageHall(int32 PhaseIndex)
{
	bStaging = true;
	UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	// ---- the wall ----------------------------------------------------------
	// PHASE 0 carves both steps of the chain. PHASE 1 re-carves the FIRST step only,
	// leaving its output alone and changing what it eats, so a submission that stored the
	// parsed recipe rather than the carving goes on making it out of the old material.
	// Nothing on the wall ever moves, so where a plaque hangs is not a thing the answer
	// has to track.
	for (int32 i = 0; i < Plaques.Num(); ++i)
	{
		AActor* const A = Plaques[i].Actor.Get();
		if (A == nullptr) { continue; }
		FString Carving;
		if (PhaseIndex == 0)
		{
			Carving = FString(i == 0 ? kCarvingTierOne : kCarvingTierTwo);
		}
		else if (i == TierOnePlaque)
		{
			Carving = FString(kCarvingRecarved);
		}
		else
		{
			Carving = Plaques[i].StagedCarving;
		}
		WriteStr(A, TEXT("CarvedText"), Carving);
		// The visible carving too, so a human reading the wall sees what the fixture
		// wrote. Presentation only; the graded read is the property.
		if (UTextRenderComponent* const T = FindText(A, TEXT("Carving")))
		{
			T->SetText(FText::FromString(Carving));
		}
		Plaques[i].StagedAt = A->GetActorLocation();
		Plaques[i].StagedCarving = Carving;
		Plaques[i].DistToForge = FVector::Dist2D(Plaques[i].StagedAt, ForgeAt);
		int32 Tier = 0;
		TArray<FName> Inputs;
		FName Output = NAME_None;
		ParseCarving(Carving, Tier, Inputs, Output);
		Plaques[i].StagedTier = Tier;
		// A re-carved plaque is UNKNOWN again; IsKnown() would say so on its own, but
		// clearing the read text keeps the calibration log honest too.
		if (PhaseIndex > 0 && i == TierOnePlaque) { Plaques[i].ReadCarving.Reset(); }
	}

	if (PhaseIndex == 0)
	{
		TierOnePlaque = INDEX_NONE;
		TierTwoPlaque = INDEX_NONE;
		for (int32 i = 0; i < Plaques.Num(); ++i)
		{
			if (TierOnePlaque == INDEX_NONE
				|| Plaques[i].StagedTier < Plaques[TierOnePlaque].StagedTier)
			{
				TierOnePlaque = i;
			}
			if (TierTwoPlaque == INDEX_NONE
				|| Plaques[i].StagedTier > Plaques[TierTwoPlaque].StagedTier)
			{
				TierTwoPlaque = i;
			}
		}
		if (TierOnePlaque == INDEX_NONE || TierTwoPlaque == INDEX_NONE
			|| TierOnePlaque == TierTwoPlaque
			|| Plaques[TierOnePlaque].StagedTier < 1)
		{
			Precondition(FString::Printf(
				TEXT("the wall does not carve two different steps of a chain; it reads "
					 "'%s' and '%s'"),
				*Plaques[0].StagedCarving,
				Plaques.Num() > 1 ? *Plaques[1].StagedCarving : TEXT("(nothing)")));
			bStaging = false;
			return false;
		}
		// The top step has to eat what the first step makes, or there is no chain at all
		// and the errand behind the forge proves nothing.
		int32 TopTier = 0;
		TArray<FName> TopInputs;
		FName TopOutput = NAME_None;
		ParseCarving(Plaques[TierTwoPlaque].StagedCarving, TopTier, TopInputs, TopOutput);
		int32 LowTier = 0;
		TArray<FName> LowInputs;
		FName LowOutput = NAME_None;
		ParseCarving(Plaques[TierOnePlaque].StagedCarving, LowTier, LowInputs, LowOutput);
		bool bChained = TopInputs.Num() > 0;
		for (const FName& N : TopInputs) { if (N != LowOutput) { bChained = false; } }
		if (!bChained)
		{
			Precondition(FString::Printf(
				TEXT("the top step of the chain ('%s') does not eat what the first step "
					 "makes ('%s'), so nothing the forge sets down is ever an "
					 "ingredient"),
				*Plaques[TierTwoPlaque].StagedCarving,
				*Plaques[TierOnePlaque].StagedCarving));
			bStaging = false;
			return false;
		}
	}

	// ---- the sign ----------------------------------------------------------
	CarryCap = PhaseIndex == 0 ? kCapPhase0 : kCapPhase1;
	if (AActor* const S = Sign.Get())
	{
		WriteInt(S, TEXT("CarryCapUnits"), CarryCap);
		if (UTextRenderComponent* const T = FindText(S, TEXT("Notice")))
		{
			T->SetText(FText::FromString(
				FString::Printf(TEXT("CARRY AT MOST %d"), CarryCap)));
		}
	}

	// ---- the pads ----------------------------------------------------------
	// PHASE 0 stocks every pad. PHASE 1 re-stocks exactly ONE, with a material that was
	// not in the hall before -- everything else stays exactly as the walk left it, which
	// is what makes the residuals the cap gates read cumulative and legible.
	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		if (PhaseIndex > 0 && i != kRestockPad) { continue; }
		FPad& P = Pads[i];
		AActor* A = P.Heap.Get();
		if (A == nullptr && World != nullptr && HeapClass != nullptr)
		{
			// The submission destroyed this heap to make it gone -- which is a legal way
			// to empty it. Re-stock means putting a heap BACK, so spawn one.
			FActorSpawnParameters Sp;
			Sp.SpawnCollisionHandlingOverride =
				ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			A = World->SpawnActor<AActor>(HeapClass, P.At, FRotator::ZeroRotator, Sp);
			P.Heap = A;
		}
		if (A == nullptr) { continue; }
		A->SetActorLocation(P.At, /*bSweep=*/false);
		A->SetActorHiddenInGame(false);
		P.PreviousId = P.StagedId;
		WriteName(A, TEXT("IngredientId"),
			FName(PhaseIndex == 0 ? kBaseId : kRestockId));
		WriteInt(A, TEXT("UnitsInHeap"),
			PhaseIndex == 0 ? kStockUnits[i] : kRestockUnits);
		// UN-HIDE. Without this a pad emptied earlier comes back invisible, and every
		// gate that reads its residual would be measuring a heap nobody can see.
		TArray<USceneComponent*> Comps;
		A->GetComponents<USceneComponent>(Comps);
		for (USceneComponent* C : Comps)
		{
			if (C == nullptr) { continue; }
			C->SetVisibility(true, false);
			C->SetHiddenInGame(false, false);
		}
		P.StagedId = ReadName(A, TEXT("IngredientId"));
		P.StagedUnits = ReadInt(A, TEXT("UnitsInHeap"), 0);
		P.Remaining = P.StagedUnits;
		P.Reach = ReadFloat(A, TEXT("ReachUu"), P.Reach);
		P.bApproached = false;
		P.bInReachNow = false;
		P.ClosestApproachUu = 1.0e9;
		P.CompareFrom = Now + kSettleS;
		if (UTextRenderComponent* const T = FindText(A, TEXT("Label")))
		{
			T->SetText(FText::FromString(FString::Printf(TEXT("%s x%d"),
				*P.StagedId.ToString(), P.StagedUnits)));
		}
	}

	// Anything the forge made before the re-stage stays where it is, and the walk is not
	// going to touch it again.
	if (PhaseIndex > 0)
	{
		for (FProduct& Pr : Products)
		{
			Pr.bInReachNow = false;
		}
	}

	Carried.Reset();
	BuildRoute(PhaseIndex);
	Waypoint = 0;
	DwellUntil = -1.0;
	bStaging = false;
	return true;
}

void AForgeCraftFunctionalTest::BuildRoute(int32 PhaseIndex)
{
	Route.Reset();
	const FVector S(ForgeAt.X + 300.0, ForgeAt.Y, HeroZ);
	FVector Cursor = Hero.IsValid()
		? FVector(Hero->GetActorLocation().X, Hero->GetActorLocation().Y, HeroZ) : S;

	auto Push = [&](const FVector& At, double Dwell, EStopKind Kind, int32 Ref,
		ERole InRole)
	{
		FStop St;
		St.At = FVector(At.X, At.Y, HeroZ);
		St.Dwell = Dwell;
		St.Kind = Kind;
		St.Ref = Ref;
		St.Role = InRole;
		Route.Add(St);
		Cursor = St.At;
	};
	// Everything in front of the forge is reached down the aisle and then straight out to
	// the thing, so every turn is a right angle on open floor and no leg of the walk ever
	// cuts across a pad or a plaque it did not go to.
	auto GoFront = [&](const FVector& To, double Dwell, EStopKind Kind, int32 Ref,
		ERole InRole)
	{
		if (FMath::Abs(Cursor.Y - ForgeAt.Y) > 1.0)
		{
			Push(FVector(Cursor.X, ForgeAt.Y, HeroZ), 0.0, EStopKind::Transit,
				INDEX_NONE, ERole::None);
		}
		if (FMath::Abs(To.Y - ForgeAt.Y) > 1.0
			&& FMath::Abs(To.X - Cursor.X) > 1.0)
		{
			Push(FVector(To.X, ForgeAt.Y, HeroZ), 0.0, EStopKind::Transit,
				INDEX_NONE, ERole::None);
		}
		Push(To, Dwell, Kind, Ref, InRole);
	};
	auto GoPlaque = [&](int32 Idx)
	{
		if (!Plaques.IsValidIndex(Idx)) { return; }
		const FVector At = Plaques[Idx].StagedAt;
		const double Side = At.Y >= ForgeAt.Y ? 1.0 : -1.0;
		// DERIVED from the plaque's own reach, never a bare constant. A fixed 150 uu
		// stand-off desynced from the map's 120 and the drive then failed this fixture's
		// OWN precondition -- the stop has to sit inside ReadReachUu * kAtFactor. Reading
		// the reach off the plaque means a map that retunes it cannot silently break the
		// walk; the clamp keeps the character from standing inside the slab.
		const double R = ReadFloat(Plaques[Idx].Actor.Get(), TEXT("ReadReachUu"), 300.0f);
		const double StandIn = FMath::Clamp(R * kAtFactor * 0.8, 80.0, kPlaqueStandInUu);
		const FVector Stand(At.X, At.Y - Side * StandIn, HeroZ);
		GoFront(Stand, kPlaqueDwellS, EStopKind::Plaque, Idx, ERole::None);
	};
	auto GoPad = [&](int32 Idx)
	{
		if (!Pads.IsValidIndex(Idx)) { return; }
		GoFront(Pads[Idx].At, kPadDwellS, EStopKind::Pad, Idx, ERole::None);
	};
	auto GoForge = [&](ERole InRole)
	{
		GoFront(S, kForgeDwellS, EStopKind::Forge, INDEX_NONE, InRole);
	};

	if (PhaseIndex == 0)
	{
		// THE CHAIN, walked. Four loads of base material at a cap of three, then the
		// errand that carries the forge's own three outputs back in, then the load that
		// makes both steps fit at once.
		GoPlaque(TierOnePlaque);       // the first step, read
		GoPad(0);                      // 2 units: a partial load
		GoForge(ERole::Partial);       // D1 -- nothing fits, nothing is spent
		GoPad(3);                      // 4 units against room for 3: it keeps one
		GoPad(1);                      // already full: it keeps all of itself
		GoForge(ERole::Tier1);         // D2
		GoPad(1);                      // what the full carrier left behind
		GoPad(4);                      // tops the load up to the cap
		GoForge(ERole::Tier1);         // D3
		GoPad(4);                      // what THAT left behind
		GoPad(5);                      // tops the load up to the cap
		GoForge(ERole::Tier1);         // D4
		// THE ERRAND. Where the forge set its own three outputs down is not knowable
		// here, so eleven stops are pushed and resolved when the walk reaches them (see
		// DriveHero): out to the lane, along to each product and back to the lane, then
		// home.
		for (int32 k = 0; k < 11; ++k)
		{
			FStop St;
			St.At = S;
			const bool bAtProduct = (k == 2 || k == 5 || k == 8);
			St.Dwell = bAtProduct ? kProductDwellS : 0.0;
			St.Kind = bAtProduct ? EStopKind::Product : EStopKind::Transit;
			St.bDeferred = true;
			Route.Add(St);
		}
		Cursor = S;
		Push(S, kForgeDwellS, EStopKind::Forge, INDEX_NONE, ERole::Unread);  // D5
		GoPlaque(TierTwoPlaque);       // the top step, read at last: the second face
		                               // must follow with no delivery at all
		GoPad(2);                      // one more unit, so both steps fit at once
		GoForge(ERole::Top);           // D6
	}
	else
	{
		GoPad(kRestockPad);            // re-stocked, under a smaller cap
		GoForge(ERole::Epilogue);      // D7
	}
}

bool AForgeCraftFunctionalTest::SweepRoute()
{
	// THE WALK MUST ONLY EVER BE WITHIN REACH OF THE THING IT WENT TO. A leg that grazes
	// an unintended heap takes from it, and every delivery after that is graded against
	// arithmetic the hall never staged.
	constexpr int32 kSamples = 40;
	for (int32 s = 0; s + 1 < Route.Num(); ++s)
	{
		if (Route[s].bDeferred || Route[s + 1].bDeferred) { continue; }
		const FStop& Dest = Route[s + 1];
		// THE ORIGIN IS EXEMPT TOO, not just the destination. A leg LEAVING a plaque or a
		// pad starts at that stop, which is by definition inside its reach -- the arrival
		// precondition demands the stop be within ReadReach*kAtFactor while this sweep
		// demands ReadReach*kClearFactor of clearance. Those cannot both hold for a
		// departing leg at ANY stand-off.
		const FStop& Orig = Route[s];
		for (int32 k = 0; k <= kSamples; ++k)
		{
			const FVector P = FMath::Lerp(Route[s].At, Dest.At,
				double(k) / double(kSamples));
			if (FVector::Dist2D(P, ForgeAt) < kAnvilClearUu)
			{
				Precondition(FString::Printf(
					TEXT("the walk from stop %d to stop %d passes %.0f uu from the "
						 "forge; the anvil is solid and the character would jam"),
					s, s + 1, FVector::Dist2D(P, ForgeAt)));
				return false;
			}
			for (int32 i = 0; i < Pads.Num(); ++i)
			{
				if (Dest.Kind == EStopKind::Pad && Dest.Ref == i) { continue; }
				if (Orig.Kind == EStopKind::Pad && Orig.Ref == i) { continue; }
				const double D = FVector::Dist2D(P, Pads[i].At);
				if (D < Pads[i].Reach * kClearFactor)
				{
					Precondition(FString::Printf(
						TEXT("the walk from stop %d to stop %d passes %.0f uu from pad "
							 "%d, which can be taken from %.0f uu; it would take from a "
							 "heap the walk never went to"),
						s, s + 1, D, i + 1, Pads[i].Reach));
					return false;
				}
			}
			for (int32 i = 0; i < Plaques.Num(); ++i)
			{
				if (Dest.Kind == EStopKind::Plaque && Dest.Ref == i) { continue; }
				if (Orig.Kind == EStopKind::Plaque && Orig.Ref == i) { continue; }
				const double R = ReadFloat(Plaques[i].Actor.Get(),
					TEXT("ReadReachUu"), 300.0f);
				const double D = FVector::Dist2D(P, Plaques[i].StagedAt);
				if (D < R * kClearFactor)
				{
					Precondition(FString::Printf(
						TEXT("the walk from stop %d to stop %d passes %.0f uu from "
							 "plaque %d, which can be read from %.0f uu; it would be "
							 "read without the character ever going to it"),
						s, s + 1, D, i + 1, R));
					return false;
				}
			}
			for (const FVector& Stone : Stones)
			{
				if (FVector::Dist2D(P, Stone)
					< kProductReachAssumedUu * kClearFactor)
				{
					Precondition(FString::Printf(
						TEXT("the walk from stop %d to stop %d passes %.0f uu from a "
							 "shelf-stone; whatever the forge sets down there would be "
							 "picked up in passing"),
						s, s + 1, FVector::Dist2D(P, Stone)));
					return false;
				}
			}
		}
		// The thing the walk went to has to be PLAINLY within reach when it gets there.
		if (Dest.Kind == EStopKind::Pad && Pads.IsValidIndex(Dest.Ref))
		{
			const double D = FVector::Dist2D(Dest.At, Pads[Dest.Ref].At);
			if (D > Pads[Dest.Ref].Reach * kAtFactor)
			{
				Precondition(FString::Printf(
					TEXT("the stop for pad %d is %.0f uu from it and it can only be "
						 "taken from %.0f uu"), Dest.Ref + 1, D, Pads[Dest.Ref].Reach));
				return false;
			}
		}
		if (Dest.Kind == EStopKind::Plaque && Plaques.IsValidIndex(Dest.Ref))
		{
			const double R = ReadFloat(Plaques[Dest.Ref].Actor.Get(),
				TEXT("ReadReachUu"), 300.0f);
			const double D = FVector::Dist2D(Dest.At, Plaques[Dest.Ref].StagedAt);
			if (D > R * kAtFactor)
			{
				Precondition(FString::Printf(
					TEXT("the stop for plaque %d is %.0f uu from it and it can only be "
						 "read from %.0f uu"), Dest.Ref + 1, D, R));
				return false;
			}
		}
		if (Dest.Kind == EStopKind::Forge)
		{
			const double D = FVector::Dist2D(Dest.At, ForgeAt);
			if (D > double(ForgeReach) - 60.0)
			{
				Precondition(FString::Printf(
					TEXT("the forge stop is %.0f uu out and the forge only takes from "
						 "%.0f uu; a correct submission would miss the delivery"),
					D, double(ForgeReach)));
				return false;
			}
		}
		// AND EVERY STOP THAT IS NOT A DELIVERY HAS TO BE PLAINLY OUTSIDE the forge's
		// reach. A stop that merely LOOKS like transit but sits inside the reach hands
		// over whatever the character is carrying at a moment the fixture is not
		// modelling a delivery, and every count after it is wrong. This is the check
		// whose absence made the previous design of this task stage a delivery it never
		// walked to.
		if (Dest.Kind != EStopKind::Forge)
		{
			const double D = FVector::Dist2D(Dest.At, ForgeAt);
			if (D <= double(ForgeReach))
			{
				Precondition(FString::Printf(
					TEXT("stop %d is not a delivery and it stands %.0f uu from the "
						 "forge, inside its %.0f uu reach; anything the character was "
						 "carrying would be handed over there"),
					s + 1, D, double(ForgeReach)));
				return false;
			}
		}
	}

	// THE ERRAND TO THE SHELF-STONES is not in the route above: where the forge sets
	// something down is not knowable until it has made it. So sweep the lane and the spur
	// to EVERY stone instead -- whichever ones the products land on, the walk to them has
	// already been checked. A multi-stone errand runs along the same lane between spurs,
	// which is a sub-segment of the lane run swept for the further stone.
	for (int32 i = 0; i < Stones.Num(); ++i)
	{
		const double Side = Stones[i].Y >= ForgeAt.Y ? 1.0 : -1.0;
		TArray<FVector> Errand;
		Errand.Add(FVector(ForgeAt.X + 300.0, ForgeAt.Y, HeroZ));
		Errand.Add(FVector(ForgeAt.X + 300.0, ForgeAt.Y + Side * LaneAbsY, HeroZ));
		Errand.Add(FVector(Stones[i].X, ForgeAt.Y + Side * LaneAbsY, HeroZ));
		Errand.Add(FVector(Stones[i].X, Stones[i].Y, HeroZ));
		for (int32 s = 0; s + 1 < Errand.Num(); ++s)
		{
			for (int32 k = 0; k <= kSamples; ++k)
			{
				const FVector P = FMath::Lerp(Errand[s], Errand[s + 1],
					double(k) / double(kSamples));
				if (FVector::Dist2D(P, ForgeAt) < kAnvilClearUu)
				{
					Precondition(FString::Printf(
						TEXT("the errand to shelf-stone %d passes %.0f uu from the "
							 "forge; the anvil is solid and the character would jam"),
						i + 1, FVector::Dist2D(P, ForgeAt)));
					return false;
				}
				for (const FPad& Pad : Pads)
				{
					if (FVector::Dist2D(P, Pad.At) < Pad.Reach * kClearFactor)
					{
						Precondition(FString::Printf(
							TEXT("the errand to shelf-stone %d passes within reach of a "
								 "heap it never went to"), i + 1));
						return false;
					}
				}
				for (const FPlaque& Pl : Plaques)
				{
					const double R = ReadFloat(Pl.Actor.Get(), TEXT("ReadReachUu"),
						300.0f);
					if (FVector::Dist2D(P, Pl.StagedAt) < R * kClearFactor)
					{
						Precondition(FString::Printf(
							TEXT("the errand to shelf-stone %d passes within reading "
								 "distance of a plaque it never went to"), i + 1));
						return false;
					}
				}
				for (int32 j = 0; j < Stones.Num(); ++j)
				{
					if (j == i) { continue; }
					if (FVector::Dist2D(P, Stones[j])
						< kProductReachAssumedUu * kClearFactor)
					{
						Precondition(FString::Printf(
							TEXT("the errand to shelf-stone %d passes %.0f uu from "
								 "shelf-stone %d; it would pick up whatever is standing "
								 "there in passing"), i + 1,
							FVector::Dist2D(P, Stones[j]), j + 1));
						return false;
					}
				}
			}
		}
		// AND THE LANE HAS TO BE OUTSIDE THE FORGE'S REACH along its whole run, or three
		// units hauled down it would be handed over halfway and every count after that
		// would be wrong.
		{
			const FVector A(ForgeAt.X + 300.0, ForgeAt.Y + Side * LaneAbsY, HeroZ);
			const FVector B(Stones[i].X, ForgeAt.Y + Side * LaneAbsY, HeroZ);
			for (int32 k = 0; k <= kSamples; ++k)
			{
				const FVector P = FMath::Lerp(A, B, double(k) / double(kSamples));
				if (FVector::Dist2D(P, ForgeAt) <= double(ForgeReach))
				{
					Precondition(FString::Printf(
						TEXT("the lane to shelf-stone %d runs %.0f uu off the forge's "
							 "line and passes %.0f uu from it, inside its %.0f uu reach; "
							 "what the character is carrying would be handed over "
							 "halfway"),
						i + 1, LaneAbsY, FVector::Dist2D(P, ForgeAt),
						double(ForgeReach)));
					return false;
				}
			}
		}
	}
	return true;
}

void AForgeCraftFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr || !ResolveHall()) { return; }
	if (!StageHall(0)) { return; }
	if (!SweepRoute()) { return; }

	// The last entry is a SENTINEL, far past a drive measured at ~126 s of world time,
	// because the base class ends the test the instant the last scheduled checkpoint is
	// crossed. It is also kept well inside the L2 layer's 600 s WALL-clock budget: a
	// sentinel the drive never reaches grades as a task FAIL, indistinguishably from a
	// bad submission.
	TArray<double> Schedule;
	for (int32 k = 1; k <= 23; ++k) { Schedule.Add(double(k) * 10.0); }
	Schedule.Add(kSentinelS);
	SetCheckpointSchedule(Schedule);
}

// ------------------------------------------------------------- per-frame

bool AForgeCraftFunctionalTest::ObserveHeaps(double Now)
{
	UWorld* const World = GetWorld();
	const FVector H = Hero->GetActorLocation();

	// Anything tagged as a heap that is not standing on one of the hall's pads was set
	// down by the forge. The set GROWS mid-run, which is the whole point of the errand.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("IngredientHeap")), Found);
	for (AActor* A : Found)
	{
		if (A == nullptr) { continue; }
		bool bOnPad = false;
		for (const FPad& P : Pads)
		{
			if (FVector::Dist2D(A->GetActorLocation(), P.At) < kPadClaimUu)
			{
				bOnPad = true;
				break;
			}
		}
		if (bOnPad) { continue; }
		bool bKnown = false;
		for (const FProduct& Pr : Products)
		{
			if (Pr.Actor.Get() == A) { bKnown = true; break; }
		}
		if (!bKnown)
		{
			FProduct Pr;
			Pr.Actor = A;
			Pr.Id = ReadName(A, TEXT("IngredientId"));
			Pr.At = A->GetActorLocation();
			Pr.Reach = double(ReadFloat(A, TEXT("ReachUu"), 220.0f));
			Pr.Remaining = FMath::Max(ReadInt(A, TEXT("UnitsInHeap"), 1), 0);
			Pr.SeenAt = Now;
			Pr.CompareFrom = Now + kSettleS;
			Products.Add(Pr);
		}
	}

	// ---- the pads ----------------------------------------------------------
	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		FPad& P = Pads[i];
		AActor* const A = P.Heap.Get();
		const double D = FVector::Dist2D(H, P.At);
		P.ClosestApproachUu = FMath::Min(P.ClosestApproachUu, D);

		// THE FIXTURE'S OWN MODEL OF THE CARRY. On the first frame in this heap's own
		// reach the character takes as much of it as the cap still leaves room for -- all
		// of it, part of it, or none of it -- and the rest stays standing.
		if (D <= double(P.Reach))
		{
			if (!P.bInReachNow)
			{
				P.bInReachNow = true;
				P.bApproached = true;
				const int32 Room = FMath::Max(CarryCap - CarriedTotal(), 0);
				const int32 Take = FMath::Min(Room, P.Remaining);
				if (Take > 0)
				{
					Carried.FindOrAdd(P.StagedId) += Take;
					P.Remaining -= Take;
				}
			}
		}
		else
		{
			P.bInReachNow = false;
		}

		// The residual is not compared while the character is anywhere near, nor for
		// kSettleS afterwards: a submission may fire a frame or two either side of the
		// fixture's flat test and must not be failed for it.
		if (D <= double(P.Reach) + kEarlyTakeUu)
		{
			P.CompareFrom = FMath::Max(P.CompareFrom, Now + kSettleS);
		}
		if (Now < P.CompareFrom) { continue; }

		const int32 Live = LiveUnits(A);
		if (Live == P.Remaining) { continue; }
		if (Live < P.Remaining)
		{
			if (!P.bApproached)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("NothingVanishesExceptWhatYouCanCarry: pad %d was stocked with "
						 "%d unit(s) of %s and %d are standing on it, and the closest "
						 "the character has ever been to it is %.0f uu, when it can only "
						 "be taken from %.0f uu. Never take from a heap you did not walk "
						 "up to"),
					i + 1, P.Remaining, *P.StagedId.ToString(), Live,
					P.ClosestApproachUu, double(P.Reach)));
				return false;
			}
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("YouCarryOnlyWhatTheSignAllows: pad %d should have %d unit(s) of %s "
					 "left standing and it has %d. The sign says carry at most %d at "
					 "once, and coming up to a heap takes only as much of it as there is "
					 "still room for -- the rest stays standing"),
				i + 1, P.Remaining, *P.StagedId.ToString(), Live, CarryCap));
			return false;
		}
		if (!P.bApproached)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: pad %d should have %d unit(s) of %s standing "
					 "on it and has %d, and the character has never been within %.0f uu "
					 "of it. What is in the hall is not yours to add to"),
				i + 1, P.Remaining, *P.StagedId.ToString(), Live, double(P.Reach)));
			return false;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("YouCarryOnlyWhatTheSignAllows: pad %d has %d unit(s) of %s standing on "
				 "it and %d should be left. The sign says carry at most %d at once, and "
				 "coming up to a heap takes as much of it as there is still room for -- "
				 "not less"),
			i + 1, Live, *P.StagedId.ToString(), P.Remaining, CarryCap));
		return false;
	}

	// ---- the forge's own outputs -------------------------------------------
	for (int32 i = 0; i < Products.Num(); ++i)
	{
		FProduct& Pr = Products[i];
		AActor* const A = Pr.Actor.Get();
		// MEASURED AGAINST WHERE IT WAS SET DOWN, frozen at the frame it appeared, and
		// never re-read off the actor. Two reasons, and both are load-bearing:
		//   - a submission is entitled to DESTROY a heap to empty it, and if it does so
		//     a frame before the fixture's own flat test fires, an actor-derived
		//     distance would jump to infinity, the pickup would never be modelled, and
		//     the next comparison would fail correct work for taking from a heap it
		//     never walked up to;
		//   - and following the actor would let a submission dodge the errand entirely
		//     by moving its own output out of the walk's way, or shrink ReachUu to zero
		//     so nothing could ever be taken from it.
		const double R = Pr.Reach;
		const double D = FVector::Dist2D(H, Pr.At);
		Pr.ClosestApproachUu = FMath::Min(Pr.ClosestApproachUu, D);

		if (D <= R)
		{
			if (!Pr.bInReachNow)
			{
				Pr.bInReachNow = true;
				Pr.bApproached = true;
				const int32 Room = FMath::Max(CarryCap - CarriedTotal(), 0);
				const int32 Take = FMath::Min(Room, Pr.Remaining);
				if (Take > 0)
				{
					Carried.FindOrAdd(Pr.Id) += Take;
					Pr.Remaining -= Take;
				}
			}
		}
		else
		{
			Pr.bInReachNow = false;
		}

		if (D <= R + kEarlyTakeUu)
		{
			Pr.CompareFrom = FMath::Max(Pr.CompareFrom, Now + kSettleS);
		}
		if (Now < Pr.CompareFrom) { continue; }

		const int32 Live = LiveUnits(A);
		if (Live == Pr.Remaining) { continue; }
		if (Live > Pr.Remaining && Pr.bApproached)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheForgeCanUseWhatItMade: the character walked up to the %s the "
					 "forge set down on a shelf-stone and %d of it is still standing "
					 "there. What the forge makes is a heap like any other -- you can "
					 "walk up to it and carry it back, and the top of the chain cannot "
					 "be made until you do"),
				*Pr.Id.ToString(), Live));
			return false;
		}
		if (Live < Pr.Remaining && !Pr.bApproached)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingVanishesExceptWhatYouCanCarry: the %s standing on a "
					 "shelf-stone should have %d unit(s) on it and has %d, and the "
					 "closest the character has ever been to it is %.0f uu when it can "
					 "only be taken from %.0f uu"),
				*Pr.Id.ToString(), Pr.Remaining, Live, Pr.ClosestApproachUu, R));
			return false;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("YouCarryOnlyWhatTheSignAllows: the %s standing on a shelf-stone should "
				 "have %d unit(s) on it and has %d. The sign says carry at most %d at "
				 "once, and what the forge set down is taken under exactly the same cap "
				 "as anything else"),
			*Pr.Id.ToString(), Pr.Remaining, Live, CarryCap));
		return false;
	}
	return true;
}

void AForgeCraftFunctionalTest::ObservePlaques(double Now)
{
	const FVector H = Hero->GetActorLocation();
	for (FPlaque& P : Plaques)
	{
		AActor* const A = P.Actor.Get();
		if (A == nullptr) { continue; }
		const double R = double(ReadFloat(A, TEXT("ReadReachUu"), 300.0f));
		if (FVector::Dist2D(H, P.StagedAt) <= R)
		{
			P.ReadCarving = ReadStr(A, TEXT("CarvedText"));
		}
	}
}

bool AForgeCraftFunctionalTest::CheckNothingMoved(double Now)
{
	UWorld* const World = GetWorld();
	AActor* const F = Forge.Get();
	if (F == nullptr)
	{
		Precondition(TEXT("the forge stopped existing mid-run"));
		return false;
	}
	if (!F->GetActorLocation().Equals(ForgeAt, 2.0))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NothingInTheHallMoved: the forge is at %s and the hall put it at %s; "
				 "where the forge, the sign, the heaps, the plaques and the shelf-stones "
				 "stand is not yours to change"),
			*F->GetActorLocation().ToCompactString(), *ForgeAt.ToCompactString()));
		return false;
	}

	// COUNTS, EVERY FRAME, not only at resolution. A plaque added mid-run would carve a
	// recipe the fixture would then grade against, and a second sign would post a cap
	// nobody agreed to.
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("RecipePlaque")), Found);
		if (Found.Num() != Plaques.Num())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: there are %d plaques on the wall and the "
					 "hall carved %d. What is in the hall is not yours to add to"),
				Found.Num(), Plaques.Num()));
			return false;
		}
		UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CarrySign")), Found);
		if (Found.Num() != 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: there are %d carry signs in the hall and the "
					 "hall posted one. What is in the hall is not yours to add to"),
				Found.Num()));
			return false;
		}
		UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("ForgeStation")), Found);
		if (Found.Num() != 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: there are %d forges in the hall and the hall "
					 "built one. What is in the hall is not yours to add to"),
				Found.Num()));
			return false;
		}
	}

	for (int32 i = 0; i < Plaques.Num(); ++i)
	{
		const AActor* const A = Plaques[i].Actor.Get();
		if (A == nullptr) { continue; }
		if (!A->GetActorLocation().Equals(Plaques[i].StagedAt, 2.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: plaque %d is at %s and the hall hung it at "
					 "%s; where a plaque hangs is not yours to change"),
				i + 1, *A->GetActorLocation().ToCompactString(),
				*Plaques[i].StagedAt.ToCompactString()));
			return false;
		}
		// WHAT IT SAYS, TOO. The wall is the hall's to write; a submission that re-carves
		// a plaque is writing its own exam paper.
		const FString Live = ReadStr(A, TEXT("CarvedText"));
		if (Live != Plaques[i].StagedCarving)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: plaque %d now reads '%s' and the hall carved "
					 "'%s'. What the plaques say, what the sign says and what the heaps "
					 "say are the hall's to write and not yours to change"),
				i + 1, *Live, *Plaques[i].StagedCarving));
			return false;
		}
	}

	if (AActor* const S = Sign.Get())
	{
		if (!S->GetActorLocation().Equals(SignAt, 2.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: the carry sign is at %s and the hall stood "
					 "it at %s; where the sign stands is not yours to change"),
				*S->GetActorLocation().ToCompactString(), *SignAt.ToCompactString()));
			return false;
		}
		const int32 LiveCap = ReadInt(S, TEXT("CarryCapUnits"), CarryCap);
		if (LiveCap != CarryCap)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: the sign now posts a cap of %d and the hall "
					 "posted %d. What the plaques say, what the sign says and what the "
					 "heaps say are the hall's to write and not yours to change"),
				LiveCap, CarryCap));
			return false;
		}
	}

	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		const AActor* const A = Pads[i].Heap.Get();
		if (A != nullptr && !A->GetActorLocation().Equals(Pads[i].At, 2.0))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: the heap on pad %d is at %s and the hall "
					 "stood it at %s; where the heaps stand is not yours to change"),
				i + 1, *A->GetActorLocation().ToCompactString(),
				*Pads[i].At.ToCompactString()));
			return false;
		}
	}
	{
		TArray<USceneComponent*> Comps;
		F->GetComponents<USceneComponent>(Comps);
		int32 Seen = 0;
		for (const USceneComponent* C : Comps)
		{
			if (C == nullptr || !C->GetName().StartsWith(TEXT("Shelf"))) { continue; }
			bool bFound = false;
			for (const FVector& St : Stones)
			{
				if (C->GetComponentLocation().Equals(St, 2.0)) { bFound = true; break; }
			}
			++Seen;
			if (!bFound)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("NothingInTheHallMoved: shelf-stone %s is at %s, which is not "
						 "where the hall laid it; where the shelf-stones stand is not "
						 "yours to change"),
					*C->GetName(), *C->GetComponentLocation().ToCompactString()));
				return false;
			}
		}
		if (Seen < Stones.Num())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingInTheHallMoved: the forge has %d shelf-stone(s) and the hall "
					 "laid %d; keep the shelf-stones"), Seen, Stones.Num()));
			return false;
		}
	}
	return true;
}

void AForgeCraftFunctionalTest::MaybeDeliver(double Now)
{
	if (Carried.Num() == 0) { return; }
	if (FVector::Dist2D(Hero->GetActorLocation(), ForgeAt) > double(ForgeReach)) { return; }

	// The role the hall staged this delivery to prove: the next forge stop at or after
	// the waypoint the walk is heading for. Keyed off the FIRST FRAME IN REACH, not off
	// the dwell -- a correct submission delivers the moment it crosses the reach, which
	// is a good half-second before the character finishes walking in.
	ERole InRole = ERole::None;
	for (int32 k = Waypoint; k < Route.Num(); ++k)
	{
		if (Route[k].Kind == EStopKind::Forge) { InRole = Route[k].Role; break; }
	}

	FDelivery D;
	D.Phase = Phase;
	D.At = Now;
	D.Role = InRole;
	D.IndexInPhase = 1;
	for (const FDelivery& Prev : Deliveries)
	{
		if (Prev.Phase == Phase) { ++D.IndexInPhase; }
	}

	TMap<FName, int32> New = Holdings;
	for (const TPair<FName, int32>& P : Carried) { New.FindOrAdd(P.Key) += P.Value; }

	int32 Tier = 0, Fitting = 0;
	const int32 Pick = ChooseRecipe(New, /*bKnownOnly=*/true, Tier, Fitting);
	int32 WholeTier = 0, WholeFitting = 0;
	const int32 WholePick = ChooseRecipe(New, /*bKnownOnly=*/false, WholeTier,
		WholeFitting);

	// THE STAGING MUST STILL HAVE THE SHAPE IT CLAIMS. Checked here rather than in
	// PrepareTest because the holdings do not exist until the delivery happens.
	//
	// HARD, for the shapes that depend only on the hall: losing one of those can only be
	// an authoring mistake, and the run ends attributed rather than scored.
	if (InRole == ERole::Partial && Pick != INDEX_NONE)
	{
		Precondition(FString::Printf(
			TEXT("phase %d delivery %d is staged as the one where nothing can be made, "
				 "and the forge holding %s can make %d thing(s)"),
			Phase + 1, D.IndexInPhase, *FormatHeld(New), Fitting));
		return;
	}
	if (InRole == ERole::Tier1 && (Pick == INDEX_NONE || Fitting != 1))
	{
		Precondition(FString::Printf(
			TEXT("phase %d delivery %d is staged as a first-step merge with exactly one "
				 "recipe fitting, and the forge holding %s has %d that fit"),
			Phase + 1, D.IndexInPhase, *FormatHeld(New), Fitting));
		return;
	}
	if (InRole == ERole::Epilogue && Pick != INDEX_NONE)
	{
		Precondition(FString::Printf(
			TEXT("phase %d delivery %d is staged as the one after the re-carve, where "
				 "nothing the character has read still fits, and the forge holding %s "
				 "can make %d thing(s)"),
			Phase + 1, D.IndexInPhase, *FormatHeld(New), Fitting));
		return;
	}
	// SOFT, for the two shapes that need the forge's own output to exist. A submission
	// that never made the first step of the chain has already failed an earlier gate;
	// turning that into a HARNESS-PRECONDITION here would take a graded run out of the
	// denominator, which is exactly what the previous design of this task did.
	if (InRole == ERole::Unread
		&& (Pick != INDEX_NONE || WholePick == INDEX_NONE))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("[t3-forge] the errand delivery did not land in its staged shape: the "
				 "forge holds %s, the read set makes %s and the whole wall makes %s. "
				 "The run is still graded"),
			*FormatHeld(New),
			Pick == INDEX_NONE ? TEXT("nothing") : TEXT("something"),
			WholePick == INDEX_NONE ? TEXT("nothing") : TEXT("something"));
	}
	if (InRole == ERole::Top && (Pick == INDEX_NONE || Fitting < 2))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("[t3-forge] the top-of-chain delivery did not land in its staged shape: "
				 "the forge holds %s and %d recipe(s) fit, where both steps of the chain "
				 "were meant to. The run is still graded"),
			*FormatHeld(New), Fitting);
	}

	if (Pick != INDEX_NONE)
	{
		int32 PickTier = 0;
		TArray<FName> Inputs;
		FName Output = NAME_None;
		ParseCarving(ReadStr(Plaques[Pick].Actor.Get(), TEXT("CarvedText")), PickTier,
			Inputs, Output);
		D.ExpectedProduct = Output;
		D.ExpectedInputs = Inputs.Num();
		D.ExpectedTier = PickTier;
		for (const FName& N : Inputs)
		{
			int32& Have = New.FindOrAdd(N);
			--Have;
			if (Have <= 0) { New.Remove(N); }
		}
	}
	for (auto It = New.CreateIterator(); It; ++It)
	{
		if (It.Value() <= 0) { It.RemoveCurrent(); }
	}
	D.ExpectedHeld = New;
	if (WholePick != INDEX_NONE)
	{
		int32 WTier = 0;
		TArray<FName> In;
		ParseCarving(ReadStr(Plaques[WholePick].Actor.Get(), TEXT("CarvedText")), WTier,
			In, D.WholeWallProduct);
	}

	Holdings = New;
	Carried.Reset();
	Deliveries.Add(D);

	UE_LOG(LogTemp, Display,
		TEXT("[t3-forge] phase %d delivery %d at t=%.2f: makes %s (step %d), holds %s"),
		D.Phase + 1, D.IndexInPhase, D.At,
		D.ExpectedProduct.IsNone() ? TEXT("nothing") : *D.ExpectedProduct.ToString(),
		D.ExpectedTier, *FormatHeld(D.ExpectedHeld));
}

bool AForgeCraftFunctionalTest::CheckDeliveryOutcome(double Now)
{
	if (Deliveries.Num() == 0) { return true; }
	FDelivery* const D = &Deliveries.Last();
	if (Now < D->At + kSettleS) { return true; }

	// AT MOST ONE THING PER DELIVERY -- checked continuously, so a second product that
	// turns up late is caught too.
	FName Last = NAME_None;
	const int32 Got = ProductsFor(*D, Last);
	const int32 Want = D->ExpectedProduct.IsNone() ? 0 : 1;
	if (Got > Want)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("OneThingPerDelivery: phase %d delivery %d set down %d things and the "
				 "forge makes at most one. Having made its one thing it stops, even when "
				 "what is left over (%s) could make something else"),
			D->Phase + 1, D->IndexInPhase, Got, *FormatHeld(D->ExpectedHeld)));
		return false;
	}
	if (D->bSettled) { return true; }
	D->bSettled = true;

	const FName Made = Last;
	if (Made == D->ExpectedProduct) { return true; }

	const int32 MadePlaque = Made.IsNone() ? INDEX_NONE : PlaqueForOutput(Made);
	if (MadePlaque != INDEX_NONE && !IsKnown(Plaques[MadePlaque]))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheForgeOnlyKnowsTheRecipesYouHaveRead: phase %d delivery %d set down "
				 "%s, and the plaque carved '%s' has never been read since it was carved "
				 "-- the character has not stood within %.0f uu of it. Reading the whole "
				 "wall gives %s; of the recipes the character HAS read, %s was the "
				 "highest step that fitted"),
			D->Phase + 1, D->IndexInPhase, *Made.ToString(),
			*ReadStr(Plaques[MadePlaque].Actor.Get(), TEXT("CarvedText")),
			double(ReadFloat(Plaques[MadePlaque].Actor.Get(), TEXT("ReadReachUu"),
				300.0f)),
			D->WholeWallProduct.IsNone() ? TEXT("nothing")
				: *D->WholeWallProduct.ToString(),
			D->ExpectedProduct.IsNone() ? TEXT("nothing")
				: *D->ExpectedProduct.ToString()));
		return false;
	}
	if (D->ExpectedProduct.IsNone())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("APartialStackIsSpentOnNothing: phase %d delivery %d set down %s, and "
				 "no recipe the character has read can be made from what the forge is "
				 "holding (%s). A part-load spends nothing and makes nothing -- two "
				 "units sitting in the forge stay two units"),
			D->Phase + 1, D->IndexInPhase, *Made.ToString(),
			*FormatHeld(D->ExpectedHeld)));
		return false;
	}
	if (Made.IsNone())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("ThreeOfAKindMakesTheNextTier: phase %d delivery %d set down nothing "
				 "and %s was required -- the forge was holding every unit the step-%d "
				 "recipe lists, counts included. Three of a kind merge into one of the "
				 "next thing up"),
			D->Phase + 1, D->IndexInPhase, *D->ExpectedProduct.ToString(),
			D->ExpectedTier));
		return false;
	}
	const int32 MadeTier = TierOf(Made);
	if (MadeTier > 0 && MadeTier < D->ExpectedTier)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheForgeMakesTheHighestTierItCan: phase %d delivery %d set down %s, "
				 "which is carved as step %d, and %s at step %d also fitted what the "
				 "forge was holding (%s). Of the recipes you have read that can be made, "
				 "it makes the one carved with the highest step"),
			D->Phase + 1, D->IndexInPhase, *Made.ToString(), MadeTier,
			*D->ExpectedProduct.ToString(), D->ExpectedTier,
			*FormatHeld(D->ExpectedHeld)));
		return false;
	}
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("ThreeOfAKindMakesTheNextTier: phase %d delivery %d set down %s and %s was "
			 "required -- the highest step among the recipes the character has read whose "
			 "units the forge's holdings covered. The forge holds %s"),
		D->Phase + 1, D->IndexInPhase, *Made.ToString(),
		*D->ExpectedProduct.ToString(), *FormatHeld(D->ExpectedHeld)));
	return false;
}

bool AForgeCraftFunctionalTest::CheckFaces(double Now)
{
	AActor* const F = Forge.Get();

	// WHAT THE FACES SHOULD SAY RIGHT NOW, recomputed every frame. What the forge could
	// make next changes when the character walks up to a plaque and when the hall
	// re-carves one -- neither of which is a delivery, and a face written only inside the
	// craft path never notices either.
	const FString Held = FormatHeld(Holdings);
	int32 Tier = 0, Fitting = 0;
	const int32 Next = ChooseRecipe(Holdings, /*bKnownOnly=*/true, Tier, Fitting);
	FString Can = TEXT("NOTHING");
	if (Next != INDEX_NONE)
	{
		int32 NTier = 0;
		TArray<FName> In;
		FName Out = NAME_None;
		ParseCarving(ReadStr(Plaques[Next].Actor.Get(), TEXT("CarvedText")), NTier, In,
			Out);
		if (!Out.IsNone()) { Can = Out.ToString(); }
	}
	if (Held != WantHeldLine) { WantHeldLine = Held; HeldChangedAt = Now; }
	if (Can != WantCanLine) { WantCanLine = Can; CanChangedAt = Now; }

	// A HANDOVER IS ABOUT TO HAPPEN. A submission is free to cross into the forge's reach
	// a frame or two before the fixture's flat test does, and for those frames its faces
	// are legitimately ahead of the fixture's model. Hold the deadline open until the
	// fixture has recorded the delivery too.
	if (Carried.Num() > 0 && Hero.IsValid()
		&& FVector::Dist2D(Hero->GetActorLocation(), ForgeAt)
			<= double(ForgeReach) * kHandoverBandFactor)
	{
		HeldChangedAt = FMath::Max(HeldChangedAt, Now);
		CanChangedAt = FMath::Max(CanChangedAt, Now);
	}

	const FString HeldRaw = ReadFace(F, TEXT("HeldFace"));
	const FString CanRaw = ReadFace(F, TEXT("CanMakeFace"));

	if (Now >= HeldChangedAt + kSettleS)
	{
		// AN ATTRIBUTION SPLIT, ahead of the plain comparison. After the re-stage one pad
		// holds a material the hall did not have before; a submission still working from
		// what that pad USED to hold says so in its own words.
		if (Phase > 0)
		{
			TMap<FName, int32> Parsed;
			if (ParseHeldFace(HeldRaw, Parsed))
			{
				for (int32 i = 0; i < Pads.Num(); ++i)
				{
					const FPad& P = Pads[i];
					if (P.PreviousId.IsNone() || P.PreviousId == P.StagedId) { continue; }
					const int32* const WantN = Holdings.Find(P.StagedId);
					if (WantN == nullptr || *WantN <= 0) { continue; }
					const int32* const GotN = Parsed.Find(P.StagedId);
					if (GotN != nullptr && *GotN >= *WantN) { continue; }
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("TheHallReadsAsItStandsNow: the first face reads '%s' and "
							 "the forge has been handed %d unit(s) of %s off pad %d, "
							 "which used to hold %s and does not any more. Read what a "
							 "heap is at the moment you pick it up; a name you remember "
							 "from when play began will be wrong later"),
						*HeldRaw, *WantN, *P.StagedId.ToString(), i + 1,
						*P.PreviousId.ToString()));
					return false;
				}
			}
		}
		// Both sides squeezed the same way: whitespace folded to single spaces and case
		// folded up. FormatHeld writes the x lower-case the way the prompt spells it, so
		// the comparison has to fold BOTH or a correct face fails on its own x.
		if (Squeeze(HeldRaw) != Squeeze(WantHeldLine))
		{
			TMap<FName, int32> Parsed;
			const bool bParsed = ParseHeldFace(HeldRaw, Parsed);
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheFirstFaceSaysWhatTheForgeIsHolding: the first face reads '%s' "
					 "and it has to read '%s'. The forge spends exactly the units the "
					 "recipe lists and nothing else; everything else it is holding stays "
					 "held%s"),
				*HeldRaw, *WantHeldLine,
				bParsed ? TEXT("") : TEXT(" (and the face has to read EMPTY, or one "
					"NAME xN entry per kind separated by single spaces in alphabetical "
					"order)")));
			return false;
		}
	}
	if (Now >= CanChangedAt + kSettleS && Squeeze(CanRaw) != WantCanLine.ToUpper())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheSecondFaceSaysWhatItCouldMakeNext: the second face reads '%s' and it "
				 "has to read '%s'. It shows what the forge could make from what it is "
				 "holding right now (%s) out of the recipes the character has read, by "
				 "exactly the rule it makes things by -- and it has to keep up when "
				 "walking up to a plaque changes the answer without anything being "
				 "delivered at all"),
			*CanRaw, *WantCanLine, *WantHeldLine));
		return false;
	}
	return true;
}

int32 AForgeCraftFunctionalTest::ProductsFor(const FDelivery& D, FName& OutLast) const
{
	OutLast = NAME_None;
	int32 Count = 0;
	double NextAt = TNumericLimits<double>::Max();
	for (const FDelivery& Other : Deliveries)
	{
		if (Other.At > D.At && Other.At < NextAt) { NextAt = Other.At; }
	}
	for (const FProduct& Pr : Products)
	{
		if (Pr.SeenAt >= D.At - kEarlyCraftS && Pr.SeenAt < NextAt - kEarlyCraftS)
		{
			++Count;
			OutLast = Pr.Id;
		}
	}
	return Count;
}

void AForgeCraftFunctionalTest::DriveHero(double Now)
{
	if (!Route.IsValidIndex(Waypoint) || !Hero.IsValid()) { return; }

	// THE ERRAND STOPS, resolved the moment the walk reaches them: the forge's own
	// outputs are spawned mid-run and where they stand is not knowable in PrepareTest.
	if (Route[Waypoint].bDeferred)
	{
		// WHICH of the forge's own outputs to go and fetch is DERIVED, not remembered:
		// the ones whose name some recipe on the wall lists as an ingredient, nearest
		// first. That stays right if the wall is ever re-authored.
		TArray<FName> WantedByWall;
		for (const FPlaque& Pl : Plaques)
		{
			int32 Tier = 0;
			TArray<FName> In;
			FName Out = NAME_None;
			ParseCarving(ReadStr(Pl.Actor.Get(), TEXT("CarvedText")), Tier, In, Out);
			WantedByWall.Append(In);
		}
		TArray<TPair<double, FVector>> Targets;
		for (const FProduct& Pr : Products)
		{
			const AActor* const A = Pr.Actor.Get();
			if (A == nullptr || HeapIsGone(A) || !WantedByWall.Contains(Pr.Id))
			{
				continue;
			}
			// WHERE THE FORGE SET IT DOWN, not where the actor is now. SweepRoute
			// pre-swept the errand to every SHELF-STONE, so a target that is not on one
			// is a walk nobody checked -- and a submission that moved its own output
			// out of the walk's way would otherwise dodge the errand entirely instead
			// of failing TheForgeCanUseWhatItMade at the spot it set it down.
			bool bOnStone = false;
			for (const FVector& St : Stones)
			{
				if (FVector::Dist2D(Pr.At, St) < 200.0) { bOnStone = true; break; }
			}
			if (!bOnStone) { continue; }
			Targets.Add(TPair<double, FVector>(
				FVector::Dist2D(Pr.At, ForgeAt), Pr.At));
		}
		Targets.Sort([](const TPair<double, FVector>& A,
			const TPair<double, FVector>& B) { return A.Key < B.Key; });
		// One side of the lane only. A correct run sets everything down on the row the
		// forge fills first, and a walk that crossed from one row to the other would run
		// straight through the forge.
		const double Side = Targets.Num() > 0 && Targets[0].Value.Y < ForgeAt.Y
			? -1.0 : 1.0;
		Targets.RemoveAll([this, Side](const TPair<double, FVector>& T)
		{
			return (T.Value.Y - ForgeAt.Y) * Side <= 0.0;
		});

		const FVector LaneHome(ForgeAt.X + 300.0, ForgeAt.Y + Side * LaneAbsY, HeroZ);
		for (int32 k = 0; k < 11 && Route.IsValidIndex(Waypoint + k); ++k)
		{
			if (!Route[Waypoint + k].bDeferred) { break; }
			FVector At = LaneHome;
			if (k > 0 && k < 10)
			{
				const int32 Which = (k - 1) / 3;
				const int32 Where = (k - 1) % 3;      // 0 = out, 1 = at it, 2 = back
				if (Targets.IsValidIndex(Which))
				{
					const FVector T = Targets[Which].Value;
					At = Where == 1
						? FVector(T.X, T.Y, HeroZ)
						: FVector(T.X, ForgeAt.Y + Side * LaneAbsY, HeroZ);
				}
				else
				{
					// Nothing was made to go and fetch. Collapse this leg onto the lane
					// rather than walking a diagonal nobody swept; the gate fires at the
					// delivery.
					At = LaneHome;
					Route[Waypoint + k].Dwell = 0.0;
				}
			}
			Route[Waypoint + k].At = At;
			Route[Waypoint + k].bDeferred = false;
		}
	}

	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Route[Waypoint].At;
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		// STAND here. Every gate is about a state that has settled, and a walk that only
		// passes through a spot never gives the hall a chance to be judged.
		if (Route[Waypoint].Dwell <= 0.0) { ++Waypoint; DwellUntil = -1.0; }
		else if (DwellUntil < 0.0) { DwellUntil = Now + Route[Waypoint].Dwell; }
		else if (Now >= DwellUntil) { ++Waypoint; DwellUntil = -1.0; }
	}
	else
	{
		Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
	}
}

void AForgeCraftFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || bStaging || !Hero.IsValid() || Pads.Num() != 8) { return; }
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	if (!CheckNothingMoved(Now)) { return; }
	if (!ObserveHeaps(Now)) { return; }
	ObservePlaques(Now);
	MaybeDeliver(Now);
	if (!IsRunning()) { return; }          // a staging precondition may have ended it
	if (!CheckDeliveryOutcome(Now)) { return; }
	if (!CheckFaces(Now)) { return; }

	DriveHero(Now);

	if (Waypoint >= Route.Num() && Phase == 0)
	{
		Phase = 1;
		PhasesRun = 2;
		RestagedAt = Now;
		if (!StageHall(1)) { return; }
		// The epilogue is a different walk under a different cap, so it gets the same
		// refusal-to-start sweep the first phase got.
		SweepRoute();
	}
}

void AForgeCraftFunctionalTest::LogCalib(int32 Index, double Now)
{
	const FVector H = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	FString Wall;
	for (int32 i = 0; i < Plaques.Num(); ++i)
	{
		Wall += FString::Printf(TEXT("p%d[%s %s] "), i + 1,
			IsKnown(Plaques[i]) ? TEXT("read") : TEXT("----"),
			*Plaques[i].StagedCarving);
	}
	FString Residuals;
	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		Residuals += FString::Printf(TEXT("%d/%d "),
			LiveUnits(Pads[i].Heap.Get()), Pads[i].Remaining);
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t3-forge calib] cp%d t=%.2f phase=%d cap=%d wp=%d/%d at=(%.0f,%.0f) "
			 "carry=%s held=%s face1='%s' face2='%s' products=%d pads=%s %s"),
		Index, Now, Phase + 1, CarryCap, Waypoint, Route.Num(), H.X, H.Y,
		*FormatHeld(Carried), *FormatHeld(Holdings),
		*ReadFace(Forge.Get(), TEXT("HeldFace")),
		*ReadFace(Forge.Get(), TEXT("CanMakeFace")), Products.Num(), *Residuals, *Wall);
}

void AForgeCraftFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kSentinelIndex) { return; }

	if (PhasesRun < 2)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheChainReachedTheTop: the run stopped before the hall re-staged, at "
				 "stop %d of %d, so the cap was never re-posted and the first step of the "
				 "chain was never re-carved"),
			Waypoint, Route.Num()));
		return;
	}
	if (Deliveries.Num() < 7)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheChainReachedTheTop: the forge took something %d time(s) and the walk "
				 "makes 7 deliveries; the run did not reach the end (stop %d of %d)"),
			Deliveries.Num(), Waypoint, Route.Num()));
		return;
	}

	// THE GOAL, read off the world: the thing the top step of the chain makes has to be
	// standing somewhere the forge set it down.
	FName TopOutput = NAME_None;
	if (Plaques.IsValidIndex(TierTwoPlaque))
	{
		int32 Tier = 0;
		TArray<FName> In;
		ParseCarving(ReadStr(Plaques[TierTwoPlaque].Actor.Get(), TEXT("CarvedText")),
			Tier, In, TopOutput);
	}
	bool bTopMade = false;
	for (const FProduct& Pr : Products)
	{
		if (!TopOutput.IsNone() && Pr.Id == TopOutput) { bTopMade = true; break; }
	}
	if (!bTopMade)
	{
		FString Made;
		for (const FProduct& Pr : Products)
		{
			Made += FString::Printf(TEXT("%s "), *Pr.Id.ToString());
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheChainReachedTheTop: nothing the forge set down is a %s, which is "
				 "what the top step of the chain makes. Over the run it set down: %s"),
			*TopOutput.ToString(), Products.Num() > 0 ? *Made : TEXT("nothing")));
		return;
	}

	for (int32 i = 0; i < Pads.Num(); ++i)
	{
		const FPad& P = Pads[i];
		const int32 Live = LiveUnits(P.Heap.Get());
		if (Live == P.Remaining) { continue; }
		if (!P.bApproached)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NothingVanishesExceptWhatYouCanCarry: the %s heap on pad %d was "
					 "stocked with %d unit(s) and never walked up to, and %d are standing "
					 "on it at the end"),
				*P.StagedId.ToString(), i + 1, P.StagedUnits, Live));
			return;
		}
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("YouCarryOnlyWhatTheSignAllows: the %s heap on pad %d should have %d "
				 "unit(s) left standing at the end and has %d"),
			*P.StagedId.ToString(), i + 1, P.Remaining, Live));
		return;
	}
}
