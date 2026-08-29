// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.

#include "CrewMusterFunctionalTest.h"

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	// ---------------------------------------------------------------- disclosed
	/** "The deck has half a second to catch up after anything happens." */
	constexpr double kSettleS = 0.5;

	// -------------------------------------------------------------- undisclosed
	// Fixture clocking and tolerances. EVERY ONE OF THESE IS A WIDENING of the
	// disclosed contract; not one of them narrows it.
	constexpr double kSuppressAfterS = kSettleS * 1.5;   // 0.75 s
	constexpr double kPlateEventS    = kSettleS * 1.5;   // 0.75 s
	constexpr double kBandFloorS     = kSettleS * 1.5;   // 0.75 s
	constexpr double kBandFraction   = 0.30;

	/** PrepareTest refuses below this. It is what keeps the judged plateau between
	 *  two guard bands at least 0.5 s wide -- ten frames on the 20 Hz leg. */
	constexpr double kMinStagedGapS = 2.0;

	/** How near a standing spot a hand has to be to count as standing ON it. The
	 *  spec's prose says 2 cm, which is what a spawn at the spot's own location
	 *  gives; 120 cm is used instead because the standing spots are 500 cm apart, so
	 *  it cannot confuse two of them and cannot mask any wrong answer, while 2 cm
	 *  could fail a correct submission that nudges a hand for footing.
	 *  craftbench-drive-manufactures-fails: widen only in the safe direction. */
	constexpr double kOnSpotUu = 120.0;

	/** How far a LIVING hand may drift from where it first stood. This one is a
	 *  delta on the same actor, so it stays tight. */
	constexpr double kNoDriftUu = 2.0;

	/** How far a piece of the deck's furniture may be from where the deck put it. */
	constexpr double kFurnitureTolUu = 2.0;

	/** The twin's standing spots must be this clear of every hand in the level. */
	constexpr double kTwinClearUu = 200.0;

	/** The drive stops steering once it is this close to a waypoint. */
	constexpr double kWaypointUu = 90.0;

	/** Phase 3 only: when the drive steps off the call pad and when it steps back on,
	 *  measured from the fixture's own observation of the contact. Both are chosen so
	 *  the 0.75 s suppression either side of the resulting release/contact lands on a
	 *  guard band and never on the plateau the empty submission has to be named at
	 *  (plateau 1, which opens 2.75 s after the plate at the staged 2.0 s gap). */
	constexpr double kStepOffAtS = 4.5;
	constexpr double kStepBackAtS = 7.5;
	constexpr double kOffPadUu = 700.0;

	/** Held on the pad past the last expected arrival so the settle has judged frames
	 *  of its own before the walk away suppresses them. */
	constexpr double kSettleHoldS = 1.5;

	constexpr double kCheckpointEveryS = 8.0;
	constexpr int32  kGradedCheckpoints = 24;    // 8 s .. 192 s
	constexpr double kSentinelAtS = 200.0;

	/** The two boards, by the name each piece of furniture on the deck carries. */
	const TCHAR* const kWorkingBoard = TEXT("PortBoard");
	const TCHAR* const kTwinBoard = TEXT("StarboardBoard");

	constexpr int32 kBoardsExpected = 2;
	constexpr int32 kBerthsPerBoard = 6;
	constexpr int32 kPlatesExpected = 4;

	bool NearlySame(double A, double B)
	{
		return FMath::Abs(A - B) <= FMath::Abs(B) * 0.001 + 0.001;
	}

	/** Which of a board's two plates this is, in words. A FUNCTION and not a ternary
	 *  at each site on purpose: three FinishTest(Failed, ...) blocks used to spell
	 *  TEXT("stand-down") inline, and cb lint's fixture-fail-unique rule reads a FAIL
	 *  literal shared by more than one block as "the MATRIX cannot tell which gate
	 *  fired". The words a reader sees are unchanged; only where they are written
	 *  down moved. Do not inline this back. */
	const TCHAR* PlateKind(bool bIsCall)
	{
		return bIsCall ? TEXT("call") : TEXT("stand-down");
	}
}

ACrewMusterFunctionalTest::ACrewMusterFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

// ---------------------------------------------------------------------------
// Reflection. Every number on the deck is read BY NAME, live, every frame. The
// fixture includes nothing from the agent-writable module on purpose: a submission
// can neither break its compile nor hide behind a subclass.
// ---------------------------------------------------------------------------

int32 ACrewMusterFunctionalTest::ReadInt(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0;
}

float ACrewMusterFunctionalTest::ReadFloat(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return 0.0f;
}

FName ACrewMusterFunctionalTest::ReadName(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FNameProperty* const P = A
			? FindFProperty<FNameProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return NAME_None;
}

bool ACrewMusterFunctionalTest::ReadBool(const AActor* A, const TCHAR* Name,
	bool& bOk) const
{
	if (const FBoolProperty* const P = A
			? FindFProperty<FBoolProperty>(A->GetClass(), Name) : nullptr)
	{
		bOk = true;
		return P->GetPropertyValue_InContainer(A);
	}
	bOk = false;
	return false;
}

bool ACrewMusterFunctionalTest::ReadIntArray(const AActor* A, const TCHAR* Name,
	TArray<int32>& Out) const
{
	Out.Reset();
	const FArrayProperty* const P = A
		? FindFProperty<FArrayProperty>(A->GetClass(), Name) : nullptr;
	if (P == nullptr)
	{
		return false;
	}
	const FIntProperty* const Inner = CastField<FIntProperty>(P->Inner);
	if (Inner == nullptr)
	{
		return false;
	}
	void* const Addr = P->ContainerPtrToValuePtr<void>(const_cast<AActor*>(A));
	FScriptArrayHelper Helper(P, Addr);
	Out.Reserve(Helper.Num());
	for (int32 Index = 0; Index < Helper.Num(); ++Index)
	{
		Out.Add(Inner->GetPropertyValue(Helper.GetElementPtr(Index)));
	}
	return true;
}

bool ACrewMusterFunctionalTest::WriteInt(AActor* A, const TCHAR* Name,
	int32 Value) const
{
	if (const FIntProperty* const P = A
			? FindFProperty<FIntProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool ACrewMusterFunctionalTest::WriteFloat(AActor* A, const TCHAR* Name,
	float Value) const
{
	if (const FFloatProperty* const P = A
			? FindFProperty<FFloatProperty>(A->GetClass(), Name) : nullptr)
	{
		P->SetPropertyValue_InContainer(A, Value);
		return true;
	}
	return false;
}

bool ACrewMusterFunctionalTest::WriteIntArray(AActor* A, const TCHAR* Name,
	const TArray<int32>& Values) const
{
	const FArrayProperty* const P = A
		? FindFProperty<FArrayProperty>(A->GetClass(), Name) : nullptr;
	if (P == nullptr)
	{
		return false;
	}
	const FIntProperty* const Inner = CastField<FIntProperty>(P->Inner);
	if (Inner == nullptr)
	{
		return false;
	}
	void* const Addr = P->ContainerPtrToValuePtr<void>(A);
	FScriptArrayHelper Helper(P, Addr);
	Helper.Resize(Values.Num());
	for (int32 Index = 0; Index < Values.Num(); ++Index)
	{
		Inner->SetPropertyValue(Helper.GetElementPtr(Index), Values[Index]);
	}
	return true;
}

bool ACrewMusterFunctionalTest::ReadChalk(const AActor* A, FChalk& Out) const
{
	bool bAll = true;
	bool bThis = false;
	Out.Call = ReadInt(A, TEXT("HandsToCall"), bThis); bAll = bAll && bThis;
	Out.Gap = double(ReadFloat(A, TEXT("SecondsBetweenArrivals"), bThis));
	bAll = bAll && bThis;
	bAll = ReadIntArray(A, TEXT("RosterCodes"), Out.Roster) && bAll;
	bAll = ReadIntArray(A, TEXT("SlatePositions"), Out.Slate) && bAll;
	return bAll;
}

bool ACrewMusterFunctionalTest::StampChalk(AActor* A, const FChalk& In) const
{
	bool bAll = WriteInt(A, TEXT("HandsToCall"), In.Call);
	bAll = WriteFloat(A, TEXT("SecondsBetweenArrivals"), float(In.Gap)) && bAll;
	bAll = WriteIntArray(A, TEXT("RosterCodes"), In.Roster) && bAll;
	bAll = WriteIntArray(A, TEXT("SlatePositions"), In.Slate) && bAll;
	return bAll;
}

// ---------------------------------------------------------------------------
// Reading the world. Only four things are ever read from the deck: which actors
// tagged CrewHand exist, where they are, what their badges SAY, and which point
// lights on a board are burning. Nothing private is graded, ever.
// ---------------------------------------------------------------------------

int32 ACrewMusterFunctionalTest::BadgeCodeOf(const AActor* Hand) const
{
	if (Hand == nullptr)
	{
		return 0;
	}
	TArray<UTextRenderComponent*> Texts;
	const_cast<AActor*>(Hand)->GetComponents<UTextRenderComponent>(Texts);
	const UTextRenderComponent* Pick = nullptr;
	for (const UTextRenderComponent* T : Texts)
	{
		if (T != nullptr && T->GetName() == TEXT("Badge"))
		{
			Pick = T;
			break;
		}
	}
	if (Pick == nullptr)
	{
		for (const UTextRenderComponent* T : Texts)
		{
			if (T != nullptr)
			{
				Pick = T;
				break;
			}
		}
	}
	if (Pick == nullptr)
	{
		return 0;
	}
	// THE TEXT ON SCREEN, never a field beside it. A hand cannot be wearing one
	// number and believe it is wearing another.
	return FCString::Atoi(*Pick->Text.ToString());
}

bool ACrewMusterFunctionalTest::LampLit(const AActor* Board, int32 Spot,
	bool& bOutFound) const
{
	bOutFound = false;
	if (Board == nullptr || Spot < 1)
	{
		return false;
	}
	TArray<UPointLightComponent*> Glows;
	const_cast<AActor*>(Board)->GetComponents<UPointLightComponent>(Glows);
	if (Glows.Num() == 0)
	{
		return false;
	}

	// The lamp row is numbered the way the standing spots are, and the deck's own
	// board names its lights in that order.
	const FString Want = FString::Printf(TEXT("LampGlow%d"), Spot - 1);
	const UPointLightComponent* Named = nullptr;
	for (const UPointLightComponent* G : Glows)
	{
		if (G != nullptr && G->GetName() == Want)
		{
			Named = G;
			break;
		}
	}
	if (Named == nullptr)
	{
		// Fall back to the row's own geometry: the lamps are laid out along the
		// board's local Y, so sorting by relative Y reproduces spot order without
		// depending on any component name at all.
		TArray<UPointLightComponent*> Sorted = Glows;
		Sorted.Sort([](const UPointLightComponent& L, const UPointLightComponent& R)
			{ return L.GetRelativeLocation().Y < R.GetRelativeLocation().Y; });
		if (Sorted.IsValidIndex(Spot - 1))
		{
			Named = Sorted[Spot - 1];
		}
	}
	if (Named == nullptr)
	{
		return false;
	}
	bOutFound = true;
	// Hidden and zero-intensity both read as dark: they look identical.
	if (Named->IsVisible() && !Named->bHiddenInGame && Named->Intensity > 0.0f)
	{
		return true;
	}
	// A WIDENING, never a narrowing: a submission that lights the row with a light of
	// its own rather than the supplied one still reads as lit, provided the light is
	// at that spot's lamp. The lamps are 500 uu apart, so 200 uu cannot confuse two.
	const FVector At = Named->GetComponentLocation();
	for (const UPointLightComponent* G : Glows)
	{
		if (G == nullptr || G == Named)
		{
			continue;
		}
		if (G->IsVisible() && !G->bHiddenInGame && G->Intensity > 0.0f
			&& FVector::Dist(G->GetComponentLocation(), At) <= 200.0)
		{
			return true;
		}
	}
	return false;
}

int32 ACrewMusterFunctionalTest::SpotAt(const FVector& Where, FName& OutBoardTag) const
{
	OutBoardTag = NAME_None;
	int32 Best = 0;
	double BestDist = kOnSpotUu;
	for (const FBerth& B : Berths)
	{
		const double D = FVector::Dist2D(Where, B.StagedAt);
		if (D <= BestDist)
		{
			BestDist = D;
			Best = B.SpotNumber;
			OutBoardTag = B.BoardTag;
		}
	}
	return Best;
}

bool ACrewMusterFunctionalTest::HeroOnPlate(const FPlate& P) const
{
	const ACharacter* const H = Hero.Get();
	const UBoxComponent* const Box = P.Volume.Get();
	if (H == nullptr || Box == nullptr)
	{
		return false;
	}
	// The fixture's OWN observation, in the plate region's own frame, so a yawed
	// plate is handled without assuming the level put it square.
	const FVector Local =
		Box->GetComponentTransform().InverseTransformPositionNoScale(
			H->GetActorLocation());
	const FVector Extent = Box->GetScaledBoxExtent();
	return FMath::Abs(Local.X) <= Extent.X + CapsuleRadius
		&& FMath::Abs(Local.Y) <= Extent.Y + CapsuleRadius
		&& FMath::Abs(Local.Z) <= Extent.Z + CapsuleHalfHeight;
}

TArray<int32> ACrewMusterFunctionalTest::ObservedOccupied(FName BoardTag) const
{
	TArray<int32> Out;
	for (const FHand& H : Live)
	{
		if (H.BoardTag == BoardTag && H.SpotNumber > 0)
		{
			Out.AddUnique(H.SpotNumber);
		}
	}
	Out.Sort();
	return Out;
}

int32 ACrewMusterFunctionalTest::ObservedHandCount(FName BoardTag) const
{
	int32 N = 0;
	for (const FHand& H : Live)
	{
		if (H.BoardTag == BoardTag && H.SpotNumber > 0)
		{
			++N;
		}
	}
	return N;
}

FString ACrewMusterFunctionalTest::DescribeSpots(const TArray<int32>& Spots)
{
	if (Spots.Num() == 0)
	{
		return FString(TEXT("none"));
	}
	TArray<FString> Parts;
	for (const int32 S : Spots)
	{
		Parts.Add(FString::FromInt(S));
	}
	return FString::Join(Parts, TEXT(", "));
}

FString ACrewMusterFunctionalTest::DescribeArrivalMap() const
{
	if (StandDownArrivals.Num() == 0)
	{
		return FString(TEXT("nobody"));
	}
	TArray<FString> Parts;
	for (int32 Index = 0; Index < StandDownArrivals.Num(); ++Index)
	{
		Parts.Add(FString::Printf(TEXT("place %d on spot %d"), Index + 1,
			StandDownArrivals[Index]));
	}
	return FString::Join(Parts, TEXT(", "));
}

FString ACrewMusterFunctionalTest::DescribeBadges() const
{
	if (Live.Num() == 0)
	{
		return FString(TEXT("nobody aboard"));
	}
	TArray<FHand> Sorted = Live;
	Sorted.Sort([](const FHand& L, const FHand& R)
		{ return L.SpotNumber < R.SpotNumber; });
	TArray<FString> Parts;
	for (const FHand& H : Sorted)
	{
		Parts.Add(FString::Printf(TEXT("spot %d wears %d"), H.SpotNumber,
			BadgeCodeOf(H.Actor.Get())));
	}
	return FString::Join(Parts, TEXT(", "));
}

int32 ACrewMusterFunctionalTest::FirstUnspentRosterCode(TArray<int32>& OutSpent) const
{
	// The board's LIVE roster, in the order it is written, against the night's issue
	// ledger. Both are things the fixture already holds, so the ordering clause in
	// TheSurvivorsKeepTheirOwnBadges costs no new state.
	OutSpent.Reset();
	int32 Due = 0;
	for (const int32 Code : Working.Staged.Roster)
	{
		if (IssuedEver.Contains(Code))
		{
			OutSpent.Add(Code);
		}
		else if (Due == 0)
		{
			Due = Code;
		}
	}
	return Due;
}

FString ACrewMusterFunctionalTest::UntaggedNote() const
{
	if (UntaggedStillAboard <= 0)
	{
		return FString();
	}
	return FString::Printf(
		TEXT(". %d of them stopped answering as a hand while still standing on the "
			 "deck; a hand that is sent ashore leaves the deck entirely, so it is "
			 "still counted here"), UntaggedStillAboard);
}

// ---------------------------------------------------------------------------
// The model. It reads the boards' LIVE chalk -- which is why
// TheDeckIsNotYoursToRearrange is load-bearing rather than ceremonial: without it a
// submission that rewrote a dial would make the model agree with whatever it did.
// ---------------------------------------------------------------------------

double ACrewMusterFunctionalTest::GuardBand() const
{
	return FMath::Max(kBandFloorS, kBandFraction * CallGap);
}

int32 ACrewMusterFunctionalTest::ExpectedAboard(double Now) const
{
	if (!bCallActive || CallGap <= 0.0)
	{
		return 0;
	}
	const double Tau = Now - CallContactAt;
	if (Tau <= 0.0)
	{
		return 0;
	}
	return FMath::Clamp(FMath::FloorToInt(Tau / CallGap), 0, CallSize);
}

TArray<int32> ACrewMusterFunctionalTest::ExpectedOccupiedAfter(int32 N) const
{
	TArray<int32> Out = HeldOverSpots;
	for (int32 Index = 0; Index < N && Index < FreeAtCall.Num(); ++Index)
	{
		Out.AddUnique(FreeAtCall[Index]);
	}
	Out.Sort();
	return Out;
}

// ---------------------------------------------------------------------------
// Staging. Everything in here ends the run as HARNESS-PRECONDITION rather than as a
// model failure: a deck that is not staged as authored is ours, never the agent's.
// ---------------------------------------------------------------------------

FString ACrewMusterFunctionalTest::DescribeBrokenPlayerInput(UWorld* World) const
{
	TArray<FString> Problems;

	// Half one: the pawn's own Enhanced Input actions, read by PROPERTY NAME so a
	// renamed or subclassed pawn still answers.
	const AGameModeBase* const GameMode = World ? World->GetAuthGameMode() : nullptr;
	const UClass* const PawnClass =
		GameMode != nullptr ? GameMode->DefaultPawnClass.Get() : nullptr;
	if (PawnClass != nullptr)
	{
		const UObject* const PawnCDO = PawnClass->GetDefaultObject();
		TArray<FString> Unbound;
		for (const TCHAR* const Name : { TEXT("MoveAction"), TEXT("LookAction"),
										 TEXT("MouseLookAction"), TEXT("JumpAction") })
		{
			const FObjectProperty* const Prop =
				FindFProperty<FObjectProperty>(PawnClass, Name);
			if (Prop == nullptr || PawnCDO == nullptr
				|| Prop->GetObjectPropertyValue_InContainer(PawnCDO) == nullptr)
			{
				Unbound.Add(Name);
			}
		}
		if (Unbound.Num() > 0)
		{
			Problems.Add(FString::Printf(TEXT("the pawn (%s) has nothing bound to %s"),
				*PawnClass->GetName(), *FString::Join(Unbound, TEXT(", "))));
		}
	}
	else
	{
		Problems.Add(TEXT("the game mode names no DefaultPawnClass"));
	}

	// Half two: a mapping context has to be applied, or no key reaches any of those
	// actions even when all four are set.
	const UClass* const PCClass =
		GameMode != nullptr ? GameMode->PlayerControllerClass.Get() : nullptr;
	if (PCClass == nullptr)
	{
		Problems.Add(TEXT("the game mode names no PlayerControllerClass, so the player "
						  "gets a bare APlayerController"));
	}
	else if (const FArrayProperty* const Contexts =
				 FindFProperty<FArrayProperty>(PCClass, TEXT("DefaultMappingContexts")))
	{
		const FObjectProperty* const Element = CastField<FObjectProperty>(Contexts->Inner);
		void* const Addr =
			Contexts->ContainerPtrToValuePtr<void>(PCClass->GetDefaultObject());
		FScriptArrayHelper Helper(Contexts, Addr);
		int32 Applied = 0;
		for (int32 Index = 0; Element != nullptr && Index < Helper.Num(); ++Index)
		{
			if (Element->GetObjectPropertyValue(Helper.GetElementPtr(Index)) != nullptr)
			{
				++Applied;
			}
		}
		if (Applied == 0)
		{
			Problems.Add(FString::Printf(TEXT("%s applies no input mapping context"),
				*PCClass->GetName()));
		}
	}
	else
	{
		Problems.Add(FString::Printf(
			TEXT("%s carries no DefaultMappingContexts, so nothing here can confirm a "
				 "key is mapped"), *PCClass->GetName()));
	}

	return FString::Join(Problems, TEXT("; "));
}

bool ACrewMusterFunctionalTest::ResolveStaging()
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;

	Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Hero.IsValid() || Hero->GetCharacterMovement() == nullptr
		|| Hero->GetCapsuleComponent() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no possessed character with a movement "
				 "component; the deck cannot be walked"));
		return false;
	}
	CapsuleRadius = double(Hero->GetCapsuleComponent()->GetScaledCapsuleRadius());
	CapsuleHalfHeight = double(Hero->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
	HeroSpeed = FMath::Max(120.0, double(Hero->GetCharacterMovement()->MaxWalkSpeed));

	// THE LEVEL HAS TO BE PLAYABLE BY HAND. Both halves, by property name. Five of six
	// ThirdPerson maps once shipped visible, animated and completely uncontrollable
	// while grading byte-identically; this is a HARNESS precondition because the input
	// lane is substrate we ship and never anything the agent was asked to write.
	if (const FString Unwired = DescribeBrokenPlayerInput(World); !Unwired.IsEmpty())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the level cannot be played by hand -- %s. The "
				 "graded drive would still pass, so fix the substrate, not the task."),
			*Unwired));
		return false;
	}

	// ---- the boards ----------------------------------------------------------
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MusterBoard")), Found);
	if (Found.Num() != kBoardsExpected)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the deck is not staged as authored - expected "
				 "%d actors tagged MusterBoard, found %d"), kBoardsExpected,
			Found.Num()));
		return false;
	}
	for (AActor* A : Found)
	{
		bool bOk = false;
		const FName Tag = ReadName(A, TEXT("BoardTag"), bOk);
		if (!bOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a muster board does not expose BoardTag "
					 "readably, so the fixture cannot tell the two boards apart"));
			return false;
		}
		FBoard* Slot = nullptr;
		if (Tag == FName(kWorkingBoard)) { Slot = &Working; }
		else if (Tag == FName(kTwinBoard)) { Slot = &Twin; }
		if (Slot == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a muster board is named '%s'; this deck is "
					 "staged for '%s' and '%s'"), *Tag.ToString(), kWorkingBoard,
				kTwinBoard));
			return false;
		}
		if (Slot->Actor.IsValid())
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: two muster boards are both named '%s'"),
				*Tag.ToString()));
			return false;
		}
		Slot->Actor = A;
		Slot->Tag = Tag;
		Slot->StagedAt = A->GetActorLocation();
		if (!ReadChalk(A, Slot->Baked))
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: board '%s' does not expose HandsToCall / "
					 "SecondsBetweenArrivals / RosterCodes / SlatePositions readably, "
					 "so the fixture cannot stage the night"), *Tag.ToString()));
			return false;
		}
	}
	if (!Working.Actor.IsValid() || !Twin.Actor.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the deck does not carry one board named "
				 "PortBoard and one named StarboardBoard"));
		return false;
	}

	// ---- the standing spots --------------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewBerth")), Found);
	if (Found.Num() != kBerthsPerBoard * kBoardsExpected)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected %d actors tagged CrewBerth, found %d"),
			kBerthsPerBoard * kBoardsExpected, Found.Num()));
		return false;
	}
	for (AActor* A : Found)
	{
		FBerth B;
		bool bTagOk = false, bNumOk = false;
		B.Actor = A;
		B.BoardTag = ReadName(A, TEXT("BoardTag"), bTagOk);
		B.SpotNumber = ReadInt(A, TEXT("SpotNumber"), bNumOk);
		B.StagedAt = A->GetActorLocation();
		if (!bTagOk || !bNumOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a standing spot does not expose BoardTag / "
					 "SpotNumber readably"));
			return false;
		}
		if (B.BoardTag != Working.Tag && B.BoardTag != Twin.Tag)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a standing spot belongs to board '%s', "
					 "which is not on this deck"), *B.BoardTag.ToString()));
			return false;
		}
		Berths.Add(B);
	}
	for (FBoard* Board : { &Working, &Twin })
	{
		for (const FBerth& B : Berths)
		{
			if (B.BoardTag == Board->Tag)
			{
				if (Board->Spots.Contains(B.SpotNumber))
				{
					FinishTest(EFunctionalTestResult::Error, FString::Printf(
						TEXT("HARNESS-PRECONDITION: board '%s' has two standing spots "
							 "numbered %d"), *Board->Tag.ToString(), B.SpotNumber));
					return false;
				}
				Board->Spots.Add(B.SpotNumber);
			}
		}
		Board->Spots.Sort();
		if (Board->Spots.Num() != kBerthsPerBoard)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: board '%s' has %d standing spots, expected "
					 "%d"), *Board->Tag.ToString(), Board->Spots.Num(),
				kBerthsPerBoard));
			return false;
		}
		// 1-BASED AND CONTIGUOUS. The whole coupling this task is built on -- that on
		// the first watch "the k-th to turn up" and "standing spot k" are the same
		// hand -- is only exact when the spots run 1..6.
		for (int32 Index = 0; Index < Board->Spots.Num(); ++Index)
		{
			if (Board->Spots[Index] != Index + 1)
			{
				FinishTest(EFunctionalTestResult::Error, FString::Printf(
					TEXT("HARNESS-PRECONDITION: board '%s' numbers its standing spots "
						 "%s; they must run 1..%d, or arrival place k and spot k stop "
						 "coinciding on the first watch and the task's whole coupling "
						 "dissolves"), *Board->Tag.ToString(),
					*DescribeSpots(Board->Spots), kBerthsPerBoard));
				return false;
			}
		}
	}

	// ---- the plates ----------------------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewPlate")), Found);
	if (Found.Num() != kPlatesExpected)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected %d actors tagged CrewPlate, found %d"),
			kPlatesExpected, Found.Num()));
		return false;
	}
	for (AActor* A : Found)
	{
		FPlate P;
		bool bTagOk = false, bCallOk = false;
		P.Actor = A;
		P.BoardTag = ReadName(A, TEXT("BoardTag"), bTagOk);
		P.bIsCall = ReadBool(A, TEXT("bIsCallPlate"), bCallOk);
		P.StagedAt = A->GetActorLocation();
		if (!bTagOk || !bCallOk)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a floor plate does not expose BoardTag / "
					 "bIsCallPlate readably"));
			return false;
		}
		TArray<UBoxComponent*> Boxes;
		A->GetComponents<UBoxComponent>(Boxes);
		if (Boxes.Num() == 0)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a floor plate has no region, so the fixture "
					 "cannot observe the character stepping on it"));
			return false;
		}
		P.Volume = Boxes[0];
		Plates.Add(P);
	}
	int32 WorkCall = 0, WorkDown = 0, TwinCall = 0, TwinDown = 0;
	for (const FPlate& P : Plates)
	{
		if (P.BoardTag == Working.Tag) { P.bIsCall ? ++WorkCall : ++WorkDown; }
		else if (P.BoardTag == Twin.Tag) { P.bIsCall ? ++TwinCall : ++TwinDown; }
	}
	if (WorkCall != 1 || WorkDown != 1 || TwinCall != 1 || TwinDown != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: each board needs exactly one call plate and "
				 "one stand-down plate; the working board has %d/%d and the twin %d/%d"),
			WorkCall, WorkDown, TwinCall, TwinDown));
		return false;
	}

	// ---- the deck starts empty ----------------------------------------------
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewHand")), Found);
	// Deliberately NOT a precondition: a hand that exists before anybody has stepped
	// on anything is the submission's doing (the committed level places none), and
	// NobodyArrivesUncalled names it on the first judged frame.
	if (Found.Num() > 0)
	{
		UE_LOG(LogTemp, Display,
			TEXT("[t2-crew] %d hand(s) already exist before the first call; "
				 "NobodyArrivesUncalled owns that"), Found.Num());
	}
	return true;
}

void ACrewMusterFunctionalTest::BuildSchedule()
{
	// THE PINNED SCHEDULE. The committed .umap holds DIFFERENT numbers on every one of
	// these eight values, so a submission that read the map offline -- or cached the
	// chalk in BeginPlay, which fires before PrepareTest -- is wrong from the FIRST
	// call rather than from the second.
	//
	// Watch 1 fills an empty deck: arrivals 1..6 take spots 1..6 badged 41,47,53,59,
	// 61,67; the slate {2,4,5} sends arrival places 2, 4 and 5 ashore, which on this
	// watch are also spots 2, 4 and 5 -- the coincidence is deliberate.
	// Watch 2 calls 3 into exactly the three spots that came free (2, 4 and 5), so
	// arrival place 1 is spot 2 and place 3 is spot 5; the slate {1,3} therefore
	// clears spots 2 and 5, NOT spots 1 and 3. The roster is re-chalked LONGER rather
	// than fresh, so the next unspent codes are 71, 73 and 79 -- restarting it would
	// re-issue badges that watch-1 survivors are still visibly wearing.
	PortWatch[0].Call = 6;
	PortWatch[0].Gap = 2.0;
	PortWatch[0].Roster = TArray<int32>({41, 47, 53, 59, 61, 67});
	PortWatch[0].Slate = TArray<int32>({2, 4, 5});

	PortWatch[1].Call = 3;
	PortWatch[1].Gap = 2.6;
	PortWatch[1].Roster = TArray<int32>({41, 47, 53, 59, 61, 67, 71, 73, 79});
	PortWatch[1].Slate = TArray<int32>({1, 3});

	// The twin is never stepped on. Its chalk differs from the working board's on all
	// four values so that a submission which grabbed the wrong board's numbers trips
	// the fill and cadence gates, and its roster is disjoint so any badge code in the
	// level names exactly which source produced it.
	TwinWatch[0].Call = 4;
	TwinWatch[0].Gap = 3.1;
	TwinWatch[0].Roster = TArray<int32>({11, 13, 17, 19, 23});
	TwinWatch[0].Slate = TArray<int32>({1, 2});

	TwinWatch[1].Call = 5;
	TwinWatch[1].Gap = 2.2;
	TwinWatch[1].Roster = TArray<int32>({11, 13, 17, 19, 23, 29, 31});
	TwinWatch[1].Slate = TArray<int32>({2, 4});
}

bool ACrewMusterFunctionalTest::ValidateSchedule()
{
	// EVERY BOUNDARY THE PROMPT DELIBERATELY LEAVES UNDEFINED MUST NEVER BE STAGED.
	// The prompt says nothing about a board that calls for more hands than it has free
	// spots, or a roster that runs out, so a run that staged either would be
	// unwinnable-by-ambiguity rather than hard.
	auto Refuse = [this](const FString& Why) -> bool
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: %s"), *Why));
		return false;
	};

	int32 CalledOnWorking = 0;
	int32 FreeOnWorking = kBerthsPerBoard;
	for (int32 W = 0; W < 2; ++W)
	{
		for (int32 B = 0; B < 2; ++B)
		{
			const FChalk& C = (B == 0) ? PortWatch[W] : TwinWatch[W];
			const TCHAR* const Name = (B == 0) ? kWorkingBoard : kTwinBoard;
			if (C.Gap < kMinStagedGapS)
			{
				return Refuse(FString::Printf(
					TEXT("watch %d chalks board '%s' an arrival gap of %.2f s, below "
						 "the %.2f s floor. Below it the guard band of max(%.2f s, "
						 "%.2f x gap) either side of an arrival swallows the plateau "
						 "between two of them and the cadence gate would have nothing "
						 "left to judge"), W + 1, Name, C.Gap, kMinStagedGapS,
					kBandFloorS, kBandFraction));
			}
			if (C.Call < 1 || C.Call > kBerthsPerBoard)
			{
				return Refuse(FString::Printf(
					TEXT("watch %d chalks board '%s' a call for %d hands against %d "
						 "standing spots"), W + 1, Name, C.Call, kBerthsPerBoard));
			}
			for (const int32 Place : C.Slate)
			{
				if (Place < 1 || Place > C.Call)
				{
					return Refuse(FString::Printf(
						TEXT("watch %d chalks board '%s' a stand-down place of %d "
							 "against a call for %d; the prompt says nothing about a "
							 "place nobody occupies"), W + 1, Name, Place, C.Call));
				}
			}
			TSet<int32> Seen;
			for (const int32 Place : C.Slate)
			{
				if (Seen.Contains(Place))
				{
					return Refuse(FString::Printf(
						TEXT("watch %d chalks board '%s' the same stand-down place "
							 "twice"), W + 1, Name));
				}
				Seen.Add(Place);
			}
		}

		// The working board's own arithmetic, watch by watch.
		if (PortWatch[W].Call > FreeOnWorking)
		{
			return Refuse(FString::Printf(
				TEXT("watch %d calls the working board for %d hands with only %d "
					 "standing spots free"), W + 1, PortWatch[W].Call, FreeOnWorking));
		}
		CalledOnWorking += PortWatch[W].Call;
		if (PortWatch[W].Roster.Num() < CalledOnWorking)
		{
			return Refuse(FString::Printf(
				TEXT("watch %d chalks the working board a roster of %d numbers against "
					 "%d hands called for over the night; a roster that runs out is a "
					 "case the prompt never defines"), W + 1,
				PortWatch[W].Roster.Num(), CalledOnWorking));
		}
		FreeOnWorking = FreeOnWorking - PortWatch[W].Call + PortWatch[W].Slate.Num();
	}

	// The rosters must be disjoint from one another AND from what the committed map
	// holds, or a badge code no longer names which source produced it and
	// TheQuietBoardStaysQuiet cannot assert what it claims to.
	TSet<int32> WorkAll;
	for (int32 W = 0; W < 2; ++W)
	{
		for (const int32 Code : PortWatch[W].Roster) { WorkAll.Add(Code); }
	}
	TSet<int32> TwinAll;
	for (int32 W = 0; W < 2; ++W)
	{
		for (const int32 Code : TwinWatch[W].Roster) { TwinAll.Add(Code); }
	}
	for (const int32 Code : TwinAll)
	{
		if (WorkAll.Contains(Code))
		{
			return Refuse(FString::Printf(
				TEXT("badge code %d is on both boards' rosters, so a badge no longer "
					 "names which board issued it"), Code));
		}
	}
	for (const FChalk* Baked : { &Working.Baked, &Twin.Baked })
	{
		for (const int32 Code : Baked->Roster)
		{
			if (WorkAll.Contains(Code) || TwinAll.Contains(Code))
			{
				return Refuse(FString::Printf(
					TEXT("badge code %d is both chalked in the committed level and on a "
						 "staged roster, so a submission that read the map offline "
						 "would be indistinguishable from one that read the board"),
					Code));
			}
		}
	}
	if (Working.Baked.Call == PortWatch[0].Call
		&& NearlySame(Working.Baked.Gap, PortWatch[0].Gap))
	{
		return Refuse(TEXT("the committed level already chalks the working board what "
						   "the first watch stages, so a value cached in BeginPlay "
						   "would be right and nothing would test reading it live"));
	}

	// PHASE 3'S STEP-BACK MUST LAND INSIDE WATCH 1'S FILL, AND THIS IS A LANDMINE FOR
	// A FUTURE SCHEDULE EDIT RATHER THAN A THEORETICAL WORRY.
	//
	// The prompt draws a line the fixture also draws: stepping on and off again "while
	// a call is still running" starts no second call -- which means stepping on again
	// AFTER the watch is full legitimately DOES. This fixture holds its fill window
	// open from the call plate's contact until the next stand-down, which is wider than
	// "while a call is running", so a submission that correctly started a fresh call on
	// a re-contact after the fill completed would be judged against a model expecting
	// nobody new. That would be a FALSE FAIL on a correct answer.
	//
	// It cannot happen today because the drive steps back on at kStepBackAtS = 7.5 s
	// while watch 1's fill runs to 6 x 2.0 = 12.0 s. But kStepOffAtS/kStepBackAtS are
	// CONSTANTS and the schedule is DATA: shrink watch 1's call or its gap and the
	// step-back silently crosses the end of the fill. So the relationship is asserted
	// here, where breaking it costs an attributed refusal instead of a wrong verdict.
	// The margin covers the walk back onto the pad plus the 0.75 s plate-event
	// suppression the re-contact arms.
	{
		constexpr double kStepBackMarginS = 2.5;
		const double Watch1FillEndsS = double(PortWatch[0].Call) * PortWatch[0].Gap;
		if (Watch1FillEndsS < kStepBackAtS + kStepBackMarginS)
		{
			return Refuse(FString::Printf(
				TEXT("watch 1's fill runs to %.2f s (%d hands every %.2f s) and the "
					 "drive steps back onto the call plate at %.2f s. The step-back has "
					 "to land at least %.2f s BEFORE the fill ends: after it, a "
					 "re-contact legitimately starts a fresh call, this fixture's fill "
					 "window is still open, and a CORRECT submission would be failed "
					 "for the arrivals it was right to bring. Lengthen watch 1 or move "
					 "kStepBackAtS"), Watch1FillEndsS, PortWatch[0].Call,
				PortWatch[0].Gap, kStepBackAtS, kStepBackMarginS));
		}
	}
	return true;
}

bool ACrewMusterFunctionalTest::ValidateGeometry()
{
	// The lane: the quiet spot is the midpoint of the working board's own two plates,
	// derived from the deck rather than written down.
	for (const FPlate& P : Plates)
	{
		if (P.BoardTag != Working.Tag)
		{
			continue;
		}
		if (P.bIsCall) { CallPlateAt = P.StagedAt; } else { StandDownPlateAt = P.StagedAt; }
	}
	const double HeroZ = Hero->GetActorLocation().Z;
	QuietSpot = FVector((CallPlateAt.X + StandDownPlateAt.X) * 0.5,
		(CallPlateAt.Y + StandDownPlateAt.Y) * 0.5, HeroZ);
	CallPlateAt.Z = HeroZ;
	StandDownPlateAt.Z = HeroZ;
	OffPadSpot = CallPlateAt
		+ (QuietSpot - CallPlateAt).GetSafeNormal2D() * kOffPadUu;
	OffPadSpot.Z = HeroZ;

	const double PlateSpan = FVector::Dist2D(CallPlateAt, StandDownPlateAt);
	if (PlateSpan < 1200.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the working board's two plates are only %.0f "
				 "uu apart; the drive cannot stand between them without being on one "
				 "of them"), PlateSpan));
		return false;
	}
	if (FVector::Dist2D(Hero->GetActorLocation(), QuietSpot) > 400.0)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the character starts %.0f uu from the point "
				 "midway between the working board's plates; the level is meant to put "
				 "the PlayerStart on that lane"),
			FVector::Dist2D(Hero->GetActorLocation(), QuietSpot)));
		return false;
	}

	// Nothing on the drive's lane may be a plate the drive did not mean to touch, and
	// the twin's plates must be nowhere near it.
	for (const FPlate& P : Plates)
	{
		if (P.BoardTag == Working.Tag)
		{
			continue;
		}
		const double D = FMath::Min3(FVector::Dist2D(P.StagedAt, QuietSpot),
			FVector::Dist2D(P.StagedAt, CallPlateAt),
			FVector::Dist2D(P.StagedAt, StandDownPlateAt));
		if (D < 1500.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: a twin-board plate stands %.0f uu from the "
					 "lane the drive walks; the drive would step on the board it is "
					 "meant to leave alone"), D));
			return false;
		}
	}

	// And the standing spots are off the lane, so a walk can never shove a hand.
	for (const FBerth& B : Berths)
	{
		const double D = FMath::Min3(FVector::Dist2D(B.StagedAt, QuietSpot),
			FVector::Dist2D(B.StagedAt, CallPlateAt),
			FVector::Dist2D(B.StagedAt, StandDownPlateAt));
		if (D < 600.0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: standing spot %d of board '%s' is %.0f uu "
					 "from the lane the drive walks; a hand standing there could be "
					 "walked into"), B.SpotNumber, *B.BoardTag.ToString(), D));
			return false;
		}
	}
	return true;
}

void ACrewMusterFunctionalTest::StageWatch(int32 InWatchIndex, double Now)
{
	WatchIndex = FMath::Clamp(InWatchIndex, 0, 1);
	AActor* const W = Working.Actor.Get();
	AActor* const T = Twin.Actor.Get();
	if (W == nullptr || T == nullptr
		|| !StampChalk(W, PortWatch[WatchIndex])
		|| !StampChalk(T, TwinWatch[WatchIndex]))
	{
		// bFinished, not IsRunning(): this runs from PrepareTest as well as from the
		// drive, and IsRunning() is false until StartTest.
		bFinished = true;
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: a board's chalk could not be written, so the "
				 "mate cannot re-chalk it and half the task is unreachable"));
		return;
	}
	Working.Staged = PortWatch[WatchIndex];
	Twin.Staged = TwinWatch[WatchIndex];
	LastModelChangeAt = Now;
	StagingUntil = FMath::Max(StagingUntil, Now + 2.0);

	UE_LOG(LogTemp, Display,
		TEXT("[t2-crew] watch %d chalked at t=%.2f: working call %d every %.2fs "
			 "roster %d long slate {%s}; twin call %d every %.2fs"),
		WatchIndex + 1, Now, Working.Staged.Call, Working.Staged.Gap,
		Working.Staged.Roster.Num(), *DescribeSpots(Working.Staged.Slate),
		Twin.Staged.Call, Twin.Staged.Gap);
}

// ---------------------------------------------------------------------------
// PrepareTest
// ---------------------------------------------------------------------------

void ACrewMusterFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	if (GetWorld() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}
	if (!ResolveStaging())
	{
		return;
	}
	BuildSchedule();
	if (!ValidateSchedule())
	{
		return;
	}
	if (!ValidateGeometry())
	{
		return;
	}

	// THE CHALK IS STAMPED BEFORE THE CHARACTER HAS WALKED ANYWHERE.
	StageWatch(0, 0.0);
	if (bFinished)
	{
		return;
	}

	Phase = 0;
	PhaseStartedAt = 0.0;
	PhaseDeadline = 30.0;
	LastModelChangeAt = -1000.0;
	LastPlateEventAt = -1000.0;
	StagingUntil = -1.0;
	Waypoints.Reset();
	Waypoints.Add(QuietSpot);
	WaypointIndex = 0;

	// Seed the plates' observed state so the drop-in does not read as a contact.
	for (FPlate& P : Plates)
	{
		P.bHeroInside = HeroOnPlate(P);
	}

	UE_LOG(LogTemp, Display,
		TEXT("[t2-crew] deck resolved: working board '%s' at (%.0f,%.0f), twin '%s' at "
			 "(%.0f,%.0f); quiet spot (%.0f,%.0f), call plate (%.0f,%.0f), stand-down "
			 "plate (%.0f,%.0f); hero pace %.0f uu/s, capsule r=%.0f h=%.0f"),
		*Working.Tag.ToString(), Working.StagedAt.X, Working.StagedAt.Y,
		*Twin.Tag.ToString(), Twin.StagedAt.X, Twin.StagedAt.Y,
		QuietSpot.X, QuietSpot.Y, CallPlateAt.X, CallPlateAt.Y,
		StandDownPlateAt.X, StandDownPlateAt.Y, HeroSpeed, CapsuleRadius,
		CapsuleHalfHeight);

	// The last entry is a SENTINEL far past the ~85 s the drive models, because the
	// base class ends the test the moment the last scheduled checkpoint is sampled.
	TArray<double> Schedule;
	for (int32 k = 1; k <= kGradedCheckpoints; ++k)
	{
		Schedule.Add(double(k) * kCheckpointEveryS);
	}
	Schedule.Add(kSentinelAtS);
	SetCheckpointSchedule(Schedule);
	bPrepared = true;
}

// ---------------------------------------------------------------------------
// Observation
// ---------------------------------------------------------------------------

void ACrewMusterFunctionalTest::ObservePlates(double Now)
{
	for (FPlate& P : Plates)
	{
		const bool bNow = HeroOnPlate(P);
		if (bNow == P.bHeroInside)
		{
			continue;
		}
		P.bHeroInside = bNow;
		// Nothing is judged within 0.75 s either side of ANY plate event, on either
		// board -- three times the settle the deck is promised.
		LastPlateEventAt = Now;
		if (!bNow || P.BoardTag != Working.Tag)
		{
			continue;
		}
		PlateContactAt = Now;
		bPlateContactSeen = true;
		if (P.bIsCall)
		{
			// STEPPING ON AND OFF AGAIN WHILE A CALL IS RUNNING DOES NOT START A
			// SECOND ONE. That is the whole point of phase 3's off-and-on-again.
			if (!bCallActive)
			{
				BeginCall(Now);
			}
		}
		else
		{
			DoStandDown(Now);
		}
	}
}

void ACrewMusterFunctionalTest::BeginCall(double Now)
{
	bool bOk = false;
	AActor* const B = Working.Actor.Get();
	// HOW MANY AND HOW OFTEN ARE READ HERE, at the moment the plate is stepped on,
	// off the board's LIVE chalk -- exactly where the prompt pins them.
	CallSize = FMath::Max(0, ReadInt(B, TEXT("HandsToCall"), bOk));
	CallGap = FMath::Max(0.01, double(ReadFloat(B, TEXT("SecondsBetweenArrivals"), bOk)));
	CallContactAt = Now;
	bCallActive = true;
	bFillCounted = false;
	bStandDownArmed = false;
	Arrivals.Reset();
	// A NEW WATCH STARTS THE ARRIVAL ORDER AGAIN FROM NOBODY. Whoever is already
	// aboard from an earlier watch is not in it and can never be named by its slate --
	// and, just as load-bearing, must not be counted as one of this call's arrivals by
	// TheyArriveOneAfterAnother.
	for (FHand& H : Live)
	{
		H.ArrivalPlace = 0;
	}
	HeldOverSpots = ObservedOccupied(Working.Tag);
	FreeAtCall.Reset();
	for (const int32 Spot : Working.Spots)
	{
		if (!HeldOverSpots.Contains(Spot))
		{
			FreeAtCall.Add(Spot);
		}
	}
	FreeAtCall.Sort();
	LastExpectedAboard = 0;
	LastModelChangeAt = Now;
	++CallsMade;

	UE_LOG(LogTemp, Display,
		TEXT("[t2-crew] call %d at t=%.2f: chalked for %d, one every %.2fs; held over "
			 "{%s}, free {%s}"), CallsMade, Now, CallSize, CallGap,
		*DescribeSpots(HeldOverSpots), *DescribeSpots(FreeAtCall));
}

void ACrewMusterFunctionalTest::DoStandDown(double Now)
{
	AActor* const B = Working.Actor.Get();
	StandDownSlate.Reset();
	ReadIntArray(B, TEXT("SlatePositions"), StandDownSlate);

	// THE ARRIVAL ORDER IS THE ONE THE FIXTURE WATCHED, never one it assumed. That is
	// what makes this a statement about the removal rule alone: a submission with a
	// wrong seating rule has already been named by TheDeckFillsToTheCalledNumber, and
	// is judged here against its own fill.
	StandDownArrivals = Arrivals;
	OccupiedBeforeStandDown = ObservedOccupied(Working.Tag);
	ExpectedClearedSpots.Reset();
	for (const int32 Place : StandDownSlate)
	{
		if (Place >= 1 && Place <= StandDownArrivals.Num())
		{
			const int32 Spot = StandDownArrivals[Place - 1];
			if (Spot > 0 && OccupiedBeforeStandDown.Contains(Spot))
			{
				ExpectedClearedSpots.AddUnique(Spot);
			}
		}
	}
	ExpectedClearedSpots.Sort();
	ExpectedAfterStandDown = OccupiedBeforeStandDown;
	for (const int32 Spot : ExpectedClearedSpots)
	{
		ExpectedAfterStandDown.Remove(Spot);
	}
	ExpectedAfterStandDown.Sort();

	bStandDownArmed = true;
	bStandDownCounted = false;
	StandDownAt = Now;
	// The fill window closes here, which is what hands the deck back to
	// TheRightHandsAreLeftStanding.
	bCallActive = false;
	LastModelChangeAt = Now;

	UE_LOG(LogTemp, Display,
		TEXT("[t2-crew] stand-down at t=%.2f: slate {%s} over arrival order [%s]; "
			 "expect spots {%s} cleared, leaving {%s}"), Now,
		*DescribeSpots(StandDownSlate), *DescribeArrivalMap(),
		*DescribeSpots(ExpectedClearedSpots), *DescribeSpots(ExpectedAfterStandDown));
}

void ACrewMusterFunctionalTest::ObserveDeck(double Now)
{
	UWorld* const World = GetWorld();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewHand")), Found);

	// WHOEVER HAS LEFT THE DECK -- AND ONLY THEM. A hand leaves by leaving, not by
	// ceasing to answer to its own name. Everything the fixture knows about who is
	// aboard flows from this list: occupancy, the lamp gate, the fill gate and the
	// stand-down gate all key off it, so dropping an actor here the instant it stops
	// carrying the CrewHand tag would let a submission free every spot on the board
	// at once without moving or destroying anybody -- untag-and-hide passing as
	// "sent ashore". So a tracked hand is forgotten only once it is genuinely gone
	// from the world; one that still exists stays tracked, keeps holding the spot it
	// arrived on, and is named by whichever gate its continued presence breaks.
	// Destroy() marks the actor garbage, so a correctly destroyed hand fails IsValid
	// on the same frame and this costs a correct submission nothing.
	UntaggedStillAboard = 0;
	for (int32 Index = Live.Num() - 1; Index >= 0; --Index)
	{
		AActor* const A = Live[Index].Actor.Get();
		// IsActorBeingDestroyed as well as IsValid, deliberately belt-and-braces: the
		// ONLY way this change could cost a correct submission anything is if a hand
		// on its way out still resolved as a live actor for a frame, so a hand that
		// has entered Destroy() is forgotten here whatever the weak pointer says.
		if (!IsValid(A) || A->IsActorBeingDestroyed())
		{
			Live.RemoveAt(Index);
			continue;
		}
		Live[Index].bAnswersTag = Found.Contains(A);
		if (!Live[Index].bAnswersTag)
		{
			++UntaggedStillAboard;
		}
	}

	// Whoever is new. Sorted lowest standing spot first so that even a submission that
	// brings a whole watch aboard on one frame is read in a deterministic order.
	TArray<AActor*> Fresh;
	for (AActor* const A : Found)
	{
		if (!IsValid(A))
		{
			continue;
		}
		bool bKnown = false;
		for (const FHand& H : Live)
		{
			if (H.Actor.Get() == A)
			{
				bKnown = true;
				break;
			}
		}
		if (!bKnown)
		{
			Fresh.Add(A);
		}
	}
	Fresh.Sort([this](const AActor& L, const AActor& R)
	{
		FName TL = NAME_None, TR = NAME_None;
		const int32 SL = SpotAt(L.GetActorLocation(), TL);
		const int32 SR = SpotAt(R.GetActorLocation(), TR);
		if (SL != SR)
		{
			return SL < SR;
		}
		return L.GetName() < R.GetName();
	});
	for (AActor* const A : Fresh)
	{
		FHand H;
		H.Actor = A;
		H.FirstAt = A->GetActorLocation();
		H.FirstSeenAt = Now;
		H.SpotNumber = SpotAt(H.FirstAt, H.BoardTag);
		if (bCallActive && H.BoardTag == Working.Tag && H.SpotNumber > 0)
		{
			Arrivals.Add(H.SpotNumber);
			H.ArrivalPlace = Arrivals.Num();
		}
		Live.Add(H);
	}
}

void ACrewMusterFunctionalTest::LockInBadges(double Now)
{
	for (FHand& H : Live)
	{
		if (H.IssuedCode != 0)
		{
			continue;
		}
		const int32 Code = BadgeCodeOf(H.Actor.Get());
		if (Code != 0)
		{
			H.IssuedCode = Code;
		}
	}
	(void)Now;
}

// ---------------------------------------------------------------------------
// Suppression. Every clause is a WIDENING of the half second the prompt promises.
// ---------------------------------------------------------------------------

bool ACrewMusterFunctionalTest::Suppressed(double Now) const
{
	if (Phase < 1)
	{
		return true;                       // the character is still dropping in
	}
	if (Now < StagingUntil)
	{
		return true;                       // the fixture itself is re-chalking
	}
	if (Now - LastModelChangeAt < kSuppressAfterS)
	{
		return true;                       // 1.5x the disclosed settle
	}
	if (Now - LastPlateEventAt < kPlateEventS)
	{
		return true;                       // a plate was just stepped on or left
	}
	if (bCallActive && CallGap > 0.0)
	{
		const double Band = GuardBand();
		for (int32 k = 1; k <= CallSize; ++k)
		{
			if (FMath::Abs(Now - (CallContactAt + double(k) * CallGap)) < Band)
			{
				return true;               // too near an expected arrival to judge
			}
		}
	}
	return false;
}

// ---------------------------------------------------------------------------
// The gates, in the order they are evaluated. At most one of 4-6 can fail on any
// judged frame, so a named FAIL is never a race between two of them.
// ---------------------------------------------------------------------------

bool ACrewMusterFunctionalTest::GateNotRearranged(double Now)
{
	(void)Now;
	UWorld* const World = GetWorld();

	// 1a. The chalk. LOAD-BEARING, not ceremonial: the fixture's own model reads the
	//     boards' LIVE chalk, so without this a submission that rewrote a dial would
	//     make the model agree with whatever it did.
	for (const FBoard* Board : { &Working, &Twin })
	{
		AActor* const A = Board->Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: board '%s' stopped existing "
					 "mid-run"), *Board->Tag.ToString()));
			return false;
		}
		FChalk Current;
		if (!ReadChalk(A, Current))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: board '%s' no longer exposes its "
					 "chalk readably"), *Board->Tag.ToString()));
			return false;
		}
		if (Current.Call != Board->Staged.Call)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: HandsToCall on board '%s' was "
					 "chalked %d and now reads %d"), *Board->Tag.ToString(),
				Board->Staged.Call, Current.Call));
			return false;
		}
		if (!NearlySame(Current.Gap, Board->Staged.Gap))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: SecondsBetweenArrivals on board "
					 "'%s' was chalked %.3f and now reads %.3f"),
				*Board->Tag.ToString(), Board->Staged.Gap, Current.Gap));
			return false;
		}
		if (Current.Roster != Board->Staged.Roster)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: RosterCodes on board '%s' was "
					 "chalked [%s] and now reads [%s]"), *Board->Tag.ToString(),
				*DescribeSpots(Board->Staged.Roster), *DescribeSpots(Current.Roster)));
			return false;
		}
		if (Current.Slate != Board->Staged.Slate)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: SlatePositions on board '%s' was "
					 "chalked {%s} and now reads {%s}"), *Board->Tag.ToString(),
				*DescribeSpots(Board->Staged.Slate), *DescribeSpots(Current.Slate)));
			return false;
		}
		if (FVector::Dist(A->GetActorLocation(), Board->StagedAt) > kFurnitureTolUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: board '%s' was put at "
					 "(%.0f,%.0f,%.0f) and now stands at (%.0f,%.0f,%.0f)"),
				*Board->Tag.ToString(), Board->StagedAt.X, Board->StagedAt.Y,
				Board->StagedAt.Z, A->GetActorLocation().X, A->GetActorLocation().Y,
				A->GetActorLocation().Z));
			return false;
		}
	}

	// 1b. The furniture: where it stands, and what it says it is.
	for (const FBerth& B : Berths)
	{
		AActor* const A = B.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: standing spot %d of board '%s' "
					 "stopped existing mid-run"), B.SpotNumber, *B.BoardTag.ToString()));
			return false;
		}
		if (FVector::Dist(A->GetActorLocation(), B.StagedAt) > kFurnitureTolUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: standing spot %d of board '%s' was "
					 "painted at (%.0f,%.0f) and is now at (%.0f,%.0f)"), B.SpotNumber,
				*B.BoardTag.ToString(), B.StagedAt.X, B.StagedAt.Y,
				A->GetActorLocation().X, A->GetActorLocation().Y));
			return false;
		}
		bool bTagOk = false, bNumOk = false;
		const FName Tag = ReadName(A, TEXT("BoardTag"), bTagOk);
		const int32 Num = ReadInt(A, TEXT("SpotNumber"), bNumOk);
		if (!bTagOk || !bNumOk || Tag != B.BoardTag || Num != B.SpotNumber)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: a standing spot was painted %d on "
					 "board '%s' and now reads %d on '%s'"), B.SpotNumber,
				*B.BoardTag.ToString(), Num, *Tag.ToString()));
			return false;
		}
	}
	for (const FPlate& P : Plates)
	{
		AActor* const A = P.Actor.Get();
		if (A == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: a floor plate of board '%s' stopped "
					 "existing mid-run"), *P.BoardTag.ToString()));
			return false;
		}
		if (FVector::Dist(A->GetActorLocation(), P.StagedAt) > kFurnitureTolUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: the %s plate of board '%s' was laid "
					 "at (%.0f,%.0f) and is now at (%.0f,%.0f)"),
				PlateKind(P.bIsCall), *P.BoardTag.ToString(),
				P.StagedAt.X, P.StagedAt.Y, A->GetActorLocation().X,
				A->GetActorLocation().Y));
			return false;
		}
		bool bTagOk = false, bCallOk = false;
		const FName Tag = ReadName(A, TEXT("BoardTag"), bTagOk);
		const bool bCall = ReadBool(A, TEXT("bIsCallPlate"), bCallOk);
		if (!bTagOk || !bCallOk || Tag != P.BoardTag || bCall != P.bIsCall)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheDeckIsNotYoursToRearrange: a floor plate was laid as the %s "
					 "plate of board '%s' and now reads as the %s plate of '%s'"),
				PlateKind(P.bIsCall), *P.BoardTag.ToString(),
				PlateKind(bCall), *Tag.ToString()));
			return false;
		}
	}

	// 1c. And nothing new of the deck's own furniture has appeared.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("MusterBoard")), Found);
	const int32 NBoards = Found.Num();
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewBerth")), Found);
	const int32 NBerths = Found.Num();
	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("CrewPlate")), Found);
	const int32 NPlates = Found.Num();
	if (NBoards != kBoardsExpected || NBerths != Berths.Num() || NPlates != Plates.Num())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheDeckIsNotYoursToRearrange: the deck was staged with %d boards, %d "
				 "standing spots and %d floor plates, and now carries %d, %d and %d"),
			kBoardsExpected, Berths.Num(), Plates.Num(), NBoards, NBerths, NPlates));
		return false;
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateQuietBoard(double Now)
{
	(void)Now;
	// THE IN-SCENE TWIN. Identical class, its own six standing spots, its own six
	// lamps, its own two plates and its own chalk -- and never stepped on. This is
	// what catches a BeginPlay fill, a level-wide "any plate calls every board" hook,
	// and a global singleton that ignores which board was triggered.
	for (const FHand& H : Live)
	{
		AActor* const A = H.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		if (H.BoardTag == Twin.Tag && H.SpotNumber > 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheQuietBoardStaysQuiet: board '%s' was never stepped on, and a "
					 "hand is standing on its standing spot %d"), *Twin.Tag.ToString(),
				H.SpotNumber));
			return false;
		}
		for (const FBerth& B : Berths)
		{
			if (B.BoardTag != Twin.Tag)
			{
				continue;
			}
			const double D = FVector::Dist2D(A->GetActorLocation(), B.StagedAt);
			if (D < kTwinClearUu)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheQuietBoardStaysQuiet: board '%s' was never stepped on, and "
						 "a hand stands %.0f uu from its standing spot %d"),
					*Twin.Tag.ToString(), D, B.SpotNumber));
				return false;
			}
		}
	}
	for (const int32 Spot : Twin.Spots)
	{
		bool bFound = false;
		if (LampLit(Twin.Actor.Get(), Spot, bFound))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheQuietBoardStaysQuiet: board '%s' was never stepped on, and the "
					 "lamp for its standing spot %d is burning"), *Twin.Tag.ToString(),
				Spot));
			return false;
		}
	}
	// Its roster is disjoint from the working board's and from what the committed
	// level holds, so a code off it names its source exactly.
	for (const FHand& H : Live)
	{
		const int32 Code = BadgeCodeOf(H.Actor.Get());
		if (Code != 0 && Twin.Staged.Roster.Contains(Code))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheQuietBoardStaysQuiet: badge %d is off board '%s' roster and it "
					 "was never stepped on; it is being worn on standing spot %d"),
				Code, *Twin.Tag.ToString(), H.SpotNumber));
			return false;
		}
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateNobodyUncalled(double Now)
{
	(void)Now;
	if (bCallActive)
	{
		// Inside a fill window the count belongs to TheDeckFillsToTheCalledNumber.
		bHaveJudgedHandCount = false;
		return true;
	}
	const int32 Count = Live.Num();

	if (CallsMade == 0 && Count > 0)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NobodyArrivesUncalled: every standing spot starts empty, and %d "
				 "hand(s) are already in the world before any call plate has been "
				 "stepped on. A hand is in the world only while it is aboard"),
			Count));
		return false;
	}
	if (bHaveJudgedHandCount && Count > LastJudgedHandCount)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("NobodyArrivesUncalled: nobody turns up who was not called for. %d "
				 "hand(s) were aboard and now %d are, with no call running"),
			LastJudgedHandCount, Count));
		return false;
	}
	for (const FHand& H : Live)
	{
		const int32 Code = BadgeCodeOf(H.Actor.Get());
		if (Code != 0 && !IssuedEver.Contains(Code))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NobodyArrivesUncalled: badge %d has appeared with no call "
					 "running; it was never issued to anybody"), Code));
			return false;
		}
		AActor* const A = H.Actor.Get();
		if (A != nullptr && H.SpotNumber == 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NobodyArrivesUncalled: a hand is standing at (%.0f,%.0f), which "
					 "is not any board's standing spot. A hand is in the world only "
					 "while it is aboard, so there is never one anywhere that is not "
					 "on a numbered spot"), A->GetActorLocation().X,
				A->GetActorLocation().Y));
			return false;
		}
	}
	LastJudgedHandCount = Count;
	bHaveJudgedHandCount = true;
	return true;
}

bool ACrewMusterFunctionalTest::GateCadence(double Now)
{
	if (!bCallActive || CallGap <= 0.0)
	{
		return true;
	}
	const int32 N = ExpectedAboard(Now);
	// PLATEAUS ONLY, and only the intermediate ones: the settle after the last
	// arrival belongs to TheDeckFillsToTheCalledNumber.
	if (N < 1 || N >= CallSize)
	{
		return true;
	}
	int32 Aboard = 0;
	for (const FHand& H : Live)
	{
		if (H.ArrivalPlace > 0 && H.BoardTag == Working.Tag)
		{
			++Aboard;
		}
	}
	// DISARMED UNTIL AT LEAST ONE OF THIS CALL'S HANDS IS ABOARD. "The watch is
	// arriving at the wrong pace" is a statement about a watch that is arriving;
	// "nobody ever turned up" is a fill failure and belongs to the gate an empty
	// submission has to be named by.
	if (Aboard < 1)
	{
		return true;
	}
	if (Aboard != N)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheyArriveOneAfterAnother: %.2fs after the plate was stepped on, "
				 "with the board chalked to bring one aboard every %.2fs, %d should "
				 "have turned up and %d has"), Now - CallContactAt, CallGap, N, Aboard));
		return false;
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateFill(double Now)
{
	if (!bCallActive)
	{
		return true;
	}
	const int32 N = ExpectedAboard(Now);
	const TArray<int32> Want = ExpectedOccupiedAfter(N);
	const TArray<int32> Got = ObservedOccupied(Working.Tag);
	const int32 HandsHere = ObservedHandCount(Working.Tag);

	// THE SET, at every judged frame of the fill window and not only at the settle.
	// A highest-free-first seating produces the identical set at the END of each fill
	// ({1..6}, then the vacated {2,4,5}); it is only at the intermediate plateaus that
	// the correct {1..k} and its {7-k..6} disagree.
	if (Got != Want || HandsHere != Want.Num() || Live.Num() != Want.Num())
	{
		const FString GotDesc = Got.Num() > 0
			? DescribeSpots(Got) : FString(TEXT("none aboard"));
		// The level-wide count is a DISCLOSED contract -- the prompt says a hand is in
		// the world only while it is aboard -- so when that is the clause which
		// disagreed the message has to say so, rather than print two identical spot
		// sets and read as a fixture bug.
		FString Extra;
		if (Live.Num() > Want.Num())
		{
			Extra = FString::Printf(
				TEXT(". %d hand(s) exist anywhere on the deck against the %d that "
					 "should be aboard; a hand is in the world only while it is "
					 "aboard"), Live.Num(), Want.Num());
		}
		Extra += UntaggedNote();
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheDeckFillsToTheCalledNumber: the board called for %d, %d should be "
				 "aboard %.2fs after the plate, expected spots %s and found %s%s"),
			CallSize, Want.Num(), Now - CallContactAt, *DescribeSpots(Want), *GotDesc,
			*Extra));
		return false;
	}
	if (N >= CallSize && !bFillCounted)
	{
		++FillsCompleted;
		bFillCounted = true;
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateStandDown(double Now)
{
	(void)Now;
	if (!bStandDownArmed || bCallActive)
	{
		return true;
	}
	const TArray<int32> Got = ObservedOccupied(Working.Tag);
	const int32 HandsHere = ObservedHandCount(Working.Tag);
	if (Got != ExpectedAfterStandDown || HandsHere != ExpectedAfterStandDown.Num()
		|| Live.Num() != ExpectedAfterStandDown.Num())
	{
		TArray<int32> ActuallyCleared;
		for (const int32 Spot : OccupiedBeforeStandDown)
		{
			if (!Got.Contains(Spot))
			{
				ActuallyCleared.Add(Spot);
			}
		}
		FString Extra;
		if (Live.Num() > ExpectedAfterStandDown.Num())
		{
			Extra = FString::Printf(
				TEXT(". %d hand(s) exist anywhere on the deck against the %d that "
					 "should be left standing; a hand that is sent ashore leaves the "
					 "deck entirely"), Live.Num(), ExpectedAfterStandDown.Num());
		}
		Extra += UntaggedNote();
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheRightHandsAreLeftStanding: the board's slate read {%s} -- places "
				 "in the arrival order of the watch just called, which turned up [%s]. "
				 "That names spots {%s} to go ashore, leaving {%s} standing; the deck "
				 "cleared {%s} and is holding {%s}%s"),
			*DescribeSpots(StandDownSlate), *DescribeArrivalMap(),
			*DescribeSpots(ExpectedClearedSpots),
			*DescribeSpots(ExpectedAfterStandDown), *DescribeSpots(ActuallyCleared),
			*DescribeSpots(Got), *Extra));
		return false;
	}
	if (!bStandDownCounted && ExpectedClearedSpots.Num() > 0)
	{
		++ThinningsSeen;
		bStandDownCounted = true;
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateNoShuffle(double Now)
{
	(void)Now;
	for (const FHand& H : Live)
	{
		AActor* const A = H.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		const FVector At = A->GetActorLocation();
		if (FVector::Dist2D(At, H.FirstAt) > kNoDriftUu)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NobodyShufflesAlongTheDeck: the hand wearing %d came aboard on "
					 "standing spot %d at (%.0f,%.0f) and is now at (%.0f,%.0f). A hand "
					 "never moves again for as long as it is aboard, including when the "
					 "spots beside it empty"), BadgeCodeOf(A), H.SpotNumber,
				H.FirstAt.X, H.FirstAt.Y, At.X, At.Y));
			return false;
		}
		FName NowTag = NAME_None;
		const int32 NowSpot = SpotAt(At, NowTag);
		if (NowSpot != H.SpotNumber || NowTag != H.BoardTag)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("NobodyShufflesAlongTheDeck: the hand wearing %d came aboard on "
					 "standing spot %d of board '%s' and now reads as spot %d of '%s'"),
				BadgeCodeOf(A), H.SpotNumber, *H.BoardTag.ToString(), NowSpot,
				*NowTag.ToString()));
			return false;
		}
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateBadges(double Now)
{
	(void)Now;
	TMap<int32, int32> SeenOnSpot;
	for (FHand& H : Live)
	{
		AActor* const A = H.Actor.Get();
		if (A == nullptr)
		{
			continue;
		}
		const int32 Shows = BadgeCodeOf(A);
		if (H.IssuedCode == 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSurvivorsKeepTheirOwnBadges: the hand on standing spot %d has "
					 "been aboard %.2fs and its badge is blank; every hand wears a "
					 "number where anyone can read it"), H.SpotNumber,
				Now - H.FirstSeenAt));
			return false;
		}
		if (Shows != H.IssuedCode)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSurvivorsKeepTheirOwnBadges: the hand on standing spot %d was "
					 "issued %d when it came aboard and is now wearing %d"),
				H.SpotNumber, H.IssuedCode, Shows));
			return false;
		}
		if (const int32* const Other = SeenOnSpot.Find(Shows))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSurvivorsKeepTheirOwnBadges: badge %d is being worn on "
					 "standing spot %d and on standing spot %d at the same time"),
				Shows, *Other, H.SpotNumber));
			return false;
		}
		SeenOnSpot.Add(Shows, H.SpotNumber);

		// THE WHOLE-RUN LEDGER. A number is spent once for the night: not to a later
		// hand on the same board, and not after the deck has emptied out. The roster
		// is re-chalked LONGER rather than fresh, so a submission that restarts it
		// re-issues codes watch-1 survivors are still visibly wearing.
		if (!H.bLedgered)
		{
			if (IssuedEver.Contains(H.IssuedCode))
			{
				const int32* const First = IssuedOnSpot.Find(H.IssuedCode);
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheSurvivorsKeepTheirOwnBadges: badge %d has been issued "
						 "twice tonight. It went to the hand on standing spot %d "
						 "earlier and has now been issued again to the hand on "
						 "standing spot %d; a number is spent once for the whole "
						 "night"), H.IssuedCode, First ? *First : 0, H.SpotNumber));
				return false;
			}
			// THE ORDER THE ROSTER IS WRITTEN IN. The prompt pins it in as many
			// words: one number to each hand in the order the hands arrive, each
			// taking the FIRST number on the roster that has not been issued yet
			// tonight. Membership plus uniqueness cannot tell that apart from an
			// unspent pool popped from the WRONG END, or one held in a TSet and
			// drained in hash order -- both a keystroke away in real UE code, and
			// both of which leave every other clause in this gate green while
			// getting a stated requirement wrong. Asserted at the moment the code is
			// entered in the ledger, against the two things the fixture already
			// holds: the board's live roster and the night's ledger. It is a
			// statement about the arrival the fixture OBSERVED, so a wrong SEATING
			// rule is still named by its own gate and never by this one.
			// A code that is not on the roster AT ALL is a different answer with a
			// better message of its own, three clauses down; this one only speaks
			// about which of the board's own numbers went out when.
			if (H.BoardTag == Working.Tag
				&& Working.Staged.Roster.Contains(H.IssuedCode))
			{
				TArray<int32> Spent;
				const int32 Due = FirstUnspentRosterCode(Spent);
				const FString SpentDesc = Spent.Num() > 0
					? DescribeSpots(Spent) : FString(TEXT("nothing yet"));
				if (Due != 0 && H.IssuedCode != Due)
				{
					FinishTest(EFunctionalTestResult::Failed, FString::Printf(
						TEXT("TheSurvivorsKeepTheirOwnBadges: the hand that turned up "
							 "at arrival place %d, on standing spot %d, wears %d. The "
							 "board's roster reads [%s], of which [%s] has been "
							 "issued tonight, so the first number on it that has not "
							 "been issued yet is %d. The numbers go out in the order "
							 "the roster is written, one to each hand in the order "
							 "the hands arrive"), H.ArrivalPlace, H.SpotNumber,
						H.IssuedCode, *DescribeSpots(Working.Staged.Roster),
						*SpentDesc, Due));
					return false;
				}
			}

			IssuedEver.Add(H.IssuedCode);
			IssuedOnSpot.Add(H.IssuedCode, H.SpotNumber);
			H.bLedgered = true;
		}

		// And it has to have come off the board's own roster, read live. A submission
		// that cached the numbers the committed level holds fails here on the first
		// hand it brings aboard.
		if (H.BoardTag == Working.Tag && !Working.Staged.Roster.Contains(Shows))
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("TheSurvivorsKeepTheirOwnBadges: the hand on standing spot %d "
					 "wears %d, which is not on the board's roster [%s]"),
				H.SpotNumber, Shows, *DescribeSpots(Working.Staged.Roster)));
			return false;
		}
	}
	return true;
}

bool ACrewMusterFunctionalTest::GateLamps(double Now)
{
	(void)Now;
	// THE VISIBLE READOUT, graded so it is load-bearing. Read from the light, never
	// from a flag -- and on BOTH boards, so a submission that lights the wrong row is
	// named here rather than passing on its private bookkeeping.
	for (const FBoard* Board : { &Working, &Twin })
	{
		const TArray<int32> Occupied = ObservedOccupied(Board->Tag);
		for (const int32 Spot : Board->Spots)
		{
			bool bFound = false;
			const bool bLit = LampLit(Board->Actor.Get(), Spot, bFound);
			if (!bFound)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheBoardShowsWhoIsAboard: board '%s' has no lamp for standing "
						 "spot %d, so there is nothing for a person watching to read"),
					*Board->Tag.ToString(), Spot));
				return false;
			}
			const bool bWant = Occupied.Contains(Spot);
			if (bLit != bWant)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("TheBoardShowsWhoIsAboard: on board '%s' the standing spots "
						 "with somebody on them are {%s}, and the lamp for spot %d is "
						 "%s. A board's lamp is lit exactly while its own standing spot "
						 "has somebody on it"), *Board->Tag.ToString(),
					*DescribeSpots(Occupied), Spot,
					bLit ? TEXT("burning") : TEXT("dark")));
				return false;
			}
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// The drive. One straight lane in X, every leg a straight walk, every deadline
// derived from the MEASURED distance and the MEASURED pace -- never from a written
// number of seconds. craftbench-drive-manufactures-fails: turns, acceleration ramps
// and over-wide settle windows have failed correct answers here before.
// ---------------------------------------------------------------------------

void ACrewMusterFunctionalTest::BeginPhase(int32 NewPhase, double Now)
{
	Phase = NewPhase;
	PhaseStartedAt = Now;
	ArrivedAt = -1.0;
	bPlateContactSeen = false;
	Phase3Sub = -1;
	Waypoints.Reset();
	WaypointIndex = 0;

	switch (Phase)
	{
	case 1:  PhaseDeadline = Now + 25.0; break;
	case 2:  Waypoints.Add(CallPlateAt); break;
	case 3:  PhaseDeadline =
		Now + double(CallSize) * CallGap + GuardBand() + kSettleHoldS + 30.0; break;
	case 4:  Waypoints.Add(QuietSpot); break;
	case 5:  Waypoints.Add(StandDownPlateAt); break;
	case 6:  Waypoints.Add(QuietSpot); break;
	case 7:  PhaseDeadline = Now + 25.0; StagingUntil = Now + 4.0; break;
	case 8:  Waypoints.Add(CallPlateAt); break;
	case 9:  PhaseDeadline =
		Now + double(CallSize) * CallGap + GuardBand() + kSettleHoldS + 30.0; break;
	case 10: Waypoints.Add(QuietSpot); break;
	case 11: Waypoints.Add(StandDownPlateAt); break;
	case 12: Waypoints.Add(QuietSpot); break;
	case 13: PhaseDeadline = Now + 35.0; break;
	default: PhaseDeadline = Now + 25.0; break;
	}

	if (Waypoints.Num() > 0)
	{
		double Length = 0.0;
		FVector From = Hero.IsValid() ? Hero->GetActorLocation() : QuietSpot;
		for (const FVector& P : Waypoints)
		{
			Length += FVector::Dist2D(From, P);
			From = P;
		}
		// 2.5x the ideal plus twenty: it covers the acceleration ramp, the settle at
		// each waypoint and the one-second rest on a plate.
		PhaseDeadline = Now + Length / HeroSpeed * 2.5 + 20.0;
	}
}

void ACrewMusterFunctionalTest::SteerPhase(double Now)
{
	// The mate re-chalks both boards half way through the phase set aside for it, so
	// there are two quiet seconds either side of the write.
	if (Phase == 7 && WatchIndex == 0 && (Now - PhaseStartedAt) >= 2.0)
	{
		StageWatch(1, Now);
		return;
	}

	// THE OFF-AND-ON-AGAIN, and it is not decoration: it is the only thing that grades
	// "once a call is made it runs to its number whether or not anybody is still
	// standing on the plate, and stepping on and off again does not start a second
	// one". Both instants are chosen so the 0.75 s suppression either side of the
	// resulting release and re-contact lands on a guard band, never on the plateau an
	// empty submission has to be named at.
	if (Phase == 3 && bCallActive)
	{
		const double Tau = Now - CallContactAt;
		const int32 Sub = (Tau < kStepOffAtS) ? 0 : (Tau < kStepBackAtS ? 1 : 2);
		if (Sub != Phase3Sub)
		{
			Phase3Sub = Sub;
			Waypoints.Reset();
			WaypointIndex = 0;
			ArrivedAt = -1.0;
			Waypoints.Add(Sub == 1 ? OffPadSpot : CallPlateAt);
		}
	}
}

void ACrewMusterFunctionalTest::DriveHero(double Now)
{
	if (!Hero.IsValid() || !Waypoints.IsValidIndex(WaypointIndex))
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Target = Waypoints[WaypointIndex];
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	if (Flat.Size2D() <= kWaypointUu)
	{
		++WaypointIndex;
		if (WaypointIndex >= Waypoints.Num() && ArrivedAt < 0.0)
		{
			ArrivedAt = Now;
		}
		return;
	}
	// The shipping per-frame timeline, exactly the path a human walks with WASD.
	Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
}

void ACrewMusterFunctionalTest::AdvancePhases(double Now)
{
	const bool bAtEnd = Waypoints.Num() > 0 && WaypointIndex >= Waypoints.Num();
	const double Elapsed = Now - PhaseStartedAt;
	const double FillEnds = double(CallSize) * CallGap + GuardBand() + kSettleHoldS;
	bool bDone = false;

	switch (Phase)
	{
	case 0:  bDone = Elapsed >= 3.0; break;
	case 1:  bDone = Elapsed >= 4.0; break;
	case 2:  bDone = bPlateContactSeen && (Now - PlateContactAt) >= 1.0; break;
	case 3:  bDone = bCallActive && (Now - CallContactAt) >= FillEnds; break;
	case 4:  bDone = bAtEnd && ArrivedAt >= 0.0 && (Now - ArrivedAt) >= 3.0; break;
	case 5:  bDone = bPlateContactSeen && (Now - PlateContactAt) >= 1.0; break;
	case 6:  bDone = bAtEnd && Elapsed >= 4.0; break;
	case 7:  bDone = Elapsed >= 4.0; break;
	case 8:  bDone = bPlateContactSeen && (Now - PlateContactAt) >= 1.0; break;
	case 9:  bDone = bCallActive && (Now - CallContactAt) >= FillEnds; break;
	case 10: bDone = bAtEnd && ArrivedAt >= 0.0 && (Now - ArrivedAt) >= 3.0; break;
	case 11: bDone = bPlateContactSeen && (Now - PlateContactAt) >= 1.0; break;
	case 12: bDone = bAtEnd && Elapsed >= 4.0; break;
	case 13: bDone = Elapsed >= 12.0; break;
	default: break;
	}

	if (bDone)
	{
		if (Phase >= 13)
		{
			bDriveComplete = true;
			return;
		}
		BeginPhase(Phase + 1, Now);
		return;
	}

	if (Now <= PhaseDeadline)
	{
		return;
	}

	// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. A submission that moved a plate or
	// rewrote a dial could otherwise make a phase unreachable and be paid for it with
	// a non-graded exit, so both unconditional gates are re-checked first.
	if (!GateNotRearranged(Now) || !GateQuietBoard(Now))
	{
		return;
	}
	if ((Phase == 2 || Phase == 5 || Phase == 8 || Phase == 11) && !bPlateContactSeen)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the character never reached the %s plate in "
				 "phase %d -- it is %.0f uu away after %.1fs with every unconditional "
				 "gate green; the deck is staged so the drive cannot finish"),
			PlateKind(Phase == 2 || Phase == 8), Phase,
			FVector::Dist2D(Hero->GetActorLocation(),
				(Phase == 2 || Phase == 8) ? CallPlateAt : StandDownPlateAt), Elapsed));
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: drive phase %d overran its %.1fs deadline with "
			 "every unconditional gate green; the deck is staged so the drive cannot "
			 "finish, which is ours and not the submission's"), Phase,
		PhaseDeadline - PhaseStartedAt));
}

bool ACrewMusterFunctionalTest::FinishRunLevel(double Now, const TCHAR* Where)
{
	(void)Now;
	if (bFinished)
	{
		return true;
	}
	bFinished = true;
	const bool bOneShot =
		(CallsMade < 2 || FillsCompleted < 2 || ThinningsSeen < 2);

	// A HARNESS EXIT CAN NEVER LAUNDER A FAIL. On the sentinel path the drive did not
	// finish, so the per-window bookkeeping is incomplete by construction and cannot
	// be allowed to speak first.
	if (!bDriveComplete && bOneShot)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheDeckThinnedOutTwice: the deck has to be able to do the whole thing "
				 "again. It was called %d time(s), rose to the number chalked for it %d "
				 "time(s), and was thinned by a stand-down %d time(s) (%s). A one-shot "
				 "latch can only manage it once"), CallsMade, FillsCompleted,
			ThinningsSeen, Where));
		return false;
	}

	// Every window has to have been JUDGED. A zero here means a whole window went
	// ungraded and the run proved less than it claims -- the drive's fault, never the
	// submission's, so it ends the run as ours.
	for (int32 Index = 0; Index < 4; ++Index)
	{
		if (JudgedFrames[Index] == 0)
		{
			FinishTest(EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: round %d's %s window produced no judged "
					 "frame at all (judged frames per window: %d/%d/%d/%d), so part of "
					 "the run graded nothing; the drive and the suppression windows do "
					 "not fit each other"), Index / 2 + 1,
				(Index % 2 == 0) ? TEXT("fill") : TEXT("settled"), JudgedFrames[0],
				JudgedFrames[1], JudgedFrames[2], JudgedFrames[3]));
			return false;
		}
	}

	// NONE OF THIS IS ONE-SHOT. A latch that can only do it once satisfies every
	// first-pass check and then does nothing on the second round.
	if (bOneShot)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TheDeckThinnedOutTwice: the deck has to be able to do the whole thing "
				 "again. It was called %d time(s), rose to the number chalked for it %d "
				 "time(s), and was thinned by a stand-down %d time(s) (%s). A one-shot "
				 "latch can only manage it once"), CallsMade, FillsCompleted,
			ThinningsSeen, Where));
		return false;
	}

	FinishTest(EFunctionalTestResult::Succeeded, FString::Printf(
		TEXT("Both watches ran: %d calls, %d full fills, %d stand-downs; the deck ends "
			 "with %s, lamps and badges agreeing (%s)"), CallsMade, FillsCompleted,
		ThinningsSeen, *DescribeBadges(), Where));
	return true;
}

// ---------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------

void ACrewMusterFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!IsRunning() || !bPrepared || bFinished || !Hero.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? double(World->GetTimeSeconds()) : 0.0;

	ObservePlates(Now);
	if (!IsRunning())
	{
		return;
	}
	ObserveDeck(Now);

	// The model's own clock: whenever the number of hands that SHOULD be aboard
	// changes, nothing is judged for the next 0.75 s.
	const int32 N = ExpectedAboard(Now);
	if (N != LastExpectedAboard)
	{
		LastExpectedAboard = N;
		LastModelChangeAt = Now;
	}

	// GATE 1 IS UNCONDITIONAL, from the first frame.
	if (!GateNotRearranged(Now))
	{
		return;
	}

	if (Phase >= 1 && !Suppressed(Now))
	{
		if (CallsMade >= 1 && CallsMade <= 2)
		{
			JudgedFrames[(CallsMade - 1) * 2 + (bCallActive ? 0 : 1)] += 1;
		}

		LockInBadges(Now);

		if (!GateQuietBoard(Now)) { return; }
		if (!GateNobodyUncalled(Now)) { return; }
		if (!GateCadence(Now)) { return; }
		if (!GateFill(Now)) { return; }
		if (!GateStandDown(Now)) { return; }
		if (!GateNoShuffle(Now)) { return; }
		if (!GateBadges(Now)) { return; }
		// ALWAYS LAST, and only on a frame where whichever occupancy gate was armed
		// has already agreed -- so a wrong occupancy is always named by its own gate
		// and a right occupancy with a wrong lamp row is always named here.
		if (!GateLamps(Now)) { return; }
	}

	SteerPhase(Now);
	if (bFinished || !IsRunning())
	{
		return;
	}
	DriveHero(Now);
	AdvancePhases(Now);

	if (bDriveComplete && IsRunning())
	{
		FinishRunLevel(Now, TEXT("at drive completion"));
	}
}

// ---------------------------------------------------------------------------
// Checkpoints. Calibration only -- every gate above is per-frame.
// ---------------------------------------------------------------------------

void ACrewMusterFunctionalTest::LogCalib(int32 Index, double Now) const
{
	const FVector At = Hero.IsValid() ? Hero->GetActorLocation() : FVector::ZeroVector;
	TArray<FString> LampBits;
	for (const FBoard* Board : { &Working, &Twin })
	{
		TArray<int32> Burning;
		for (const int32 Spot : Board->Spots)
		{
			bool bFound = false;
			if (LampLit(Board->Actor.Get(), Spot, bFound))
			{
				Burning.Add(Spot);
			}
		}
		LampBits.Add(FString::Printf(TEXT("%s lamps {%s} spots {%s}"),
			*Board->Tag.ToString(), *DescribeSpots(Burning),
			*DescribeSpots(ObservedOccupied(Board->Tag))));
	}
	UE_LOG(LogTemp, Display,
		TEXT("[t2-crew calib] cp%d t=%.2f watch=%d phase=%d at=(%.0f,%.0f) call=%d "
			 "gap=%.2f tau=%.2f expect=%d live=%d arrivals=[%s] | %s | badges: %s"),
		Index, Now, WatchIndex + 1, Phase, At.X, At.Y, CallSize, CallGap,
		bCallActive ? Now - CallContactAt : -1.0, ExpectedAboard(Now), Live.Num(),
		*DescribeSpots(Arrivals), *FString::Join(LampBits, TEXT(" | ")),
		*DescribeBadges());
}

void ACrewMusterFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!bPrepared)
	{
		return;
	}
	LogCalib(CheckpointIndex, TimeSeconds);

	if (CheckpointIndex < kGradedCheckpoints)
	{
		return;
	}
	// THE SENTINEL. The base class ends the test the moment the last scheduled
	// checkpoint is sampled, so the run-level gate is evaluated here as well as at
	// drive completion -- whichever comes first.
	if (bDriveComplete || bFinished)
	{
		return;
	}
	if (!GateNotRearranged(TimeSeconds) || !GateQuietBoard(TimeSeconds))
	{
		return;
	}
	if (CallsMade < 2 || FillsCompleted < 2 || ThinningsSeen < 2)
	{
		FinishRunLevel(TimeSeconds, TEXT("at the sentinel, with the drive still running"));
		return;
	}
	FinishTest(EFunctionalTestResult::Error, FString::Printf(
		TEXT("HARNESS-PRECONDITION: the drive was still at phase %d at the sentinel "
			 "with every gate green and both watches complete; the deck is staged so "
			 "the drive cannot finish, which is ours and not the submission's"), Phase));
}
