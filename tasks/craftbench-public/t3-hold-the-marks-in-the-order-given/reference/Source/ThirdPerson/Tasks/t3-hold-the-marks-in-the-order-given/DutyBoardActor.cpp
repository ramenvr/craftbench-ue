// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION. Everything below the constructor is the work.

#include "DutyBoardActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "FloorMarkActor.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kPanelWidthUu = 520.0f;
	constexpr float kPanelHeightUu = 300.0f;
	constexpr float kPanelDepthUu = 30.0f;
}

ADutyBoardActor::ADutyBoardActor()
{
	// Every frame: somebody's foot crosses a ring at any moment, and the hall is
	// allowed half a second to catch up with what that means.
	PrimaryActorTick.bCanEverTick = true;

	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
	Panel->SetupAttachment(Anchor);
	if (CubeMesh.Succeeded())
	{
		Panel->SetStaticMesh(CubeMesh.Object);
	}
	// /Engine/BasicShapes/Cube is 100 uu on a side.
	Panel->SetRelativeScale3D(FVector(kPanelDepthUu / 100.0f,
		kPanelWidthUu / 100.0f, kPanelHeightUu / 100.0f));
	Panel->SetRelativeLocation(FVector(0.0f, 0.0f, kPanelHeightUu * 0.5f + 120.0f));
	// Non-colliding on the PROFILE as well as the enum.
	Panel->SetCollisionProfileName(TEXT("NoCollision"));
	Panel->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	OrderFace = CreateDefaultSubobject<UTextRenderComponent>(TEXT("OrderFace"));
	OrderFace->SetupAttachment(Anchor);
	OrderFace->SetRelativeLocation(FVector(-kPanelDepthUu, 0.0f, 330.0f));
	OrderFace->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	OrderFace->SetHorizontalAlignment(EHTA_Center);
	OrderFace->SetWorldSize(52.0f);
	OrderFace->SetMobility(EComponentMobility::Movable);
	OrderFace->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	OrderFace->SetTextRenderColor(FColor(150, 205, 255));
	OrderFace->SetText(FText::GetEmpty());

	TallyFace = CreateDefaultSubobject<UTextRenderComponent>(TEXT("TallyFace"));
	TallyFace->SetupAttachment(Anchor);
	TallyFace->SetRelativeLocation(FVector(-kPanelDepthUu, 0.0f, 200.0f));
	TallyFace->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	TallyFace->SetHorizontalAlignment(EHTA_Center);
	TallyFace->SetWorldSize(96.0f);
	TallyFace->SetMobility(EComponentMobility::Movable);
	TallyFace->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// The graded numbers have to be READABLE, not merely present.
	TallyFace->SetTextRenderColor(FColor(255, 214, 120));
	TallyFace->SetText(FText::GetEmpty());

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Look.Succeeded() && Panel != nullptr)
	{
		Panel->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName(TEXT("DutyBoard")));
}

void ADutyBoardActor::BeginPlay()
{
	Super::BeginPlay();

	if (TallyFace != nullptr)
	{
		TallyFace->SetText(FText::GetEmpty());
	}
	LastShownFinished = -1;
	LastShownListLength = -1;
	bTallyEverWritten = false;

	PaintedOrder.Reset();
	RefreshOrderFace();

	// THE ACTORS are resolved once -- the hall is fixed. Their NUMBERS never are.
	Marks.Reset();
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("HallMark")), Found);
	for (AActor* A : Found)
	{
		if (AFloorMarkActor* const M = Cast<AFloorMarkActor>(A))
		{
			Marks.Add(M);
		}
	}

	// Whatever the board happens to be carrying at this instant is only a starting
	// guess: the hall re-writes it, and the very first frame it differs the round
	// starts over anyway. Nothing here is remembered as an answer.
	LastSeenList = ListedMarkNames;
	StartRoundOver();
	PaintHall();
}

void ADutyBoardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// ---- 1. THE LIST, READ NOW. -------------------------------------------------
	// A different order, a different set of names or a different NUMBER of names is a
	// new round: every bank empties, every lamp goes dark and the tally reads none of
	// however many names the new list carries.
	if (PaintedOrder != ListedMarkNames)
	{
		RefreshOrderFace();
	}
	if (LastSeenList != ListedMarkNames)
	{
		LastSeenList = ListedMarkNames;
		StartRoundOver();
	}

	// ---- 2. WHERE THE CHARACTER IS STANDING, AND WHETHER THAT IS A STEP ONTO. ----
	AFloorMarkActor* const Occupied = MarkUnderCharacter();
	if (Occupied != OccupiedLastFrame.Get())
	{
		// Stepping OFF the mark somebody was stood on out of turn forgives it. It is
		// the STEP ONTO that poisons a stand, so a stand that has ended cannot stay
		// poisoned.
		if (PoisonedMark.IsValid() && PoisonedMark.Get() != Occupied)
		{
			PoisonedMark.Reset();
		}

		if (Occupied != nullptr)
		{
			const int32 Idx = IndexInList(Occupied->MarkName);
			// A mark the board does not name is not part of the round: stepping onto
			// it disturbs nothing (Idx == INDEX_NONE). Stepping back onto the mark
			// whose turn it is is never out of turn (Idx == TurnIndex). Anything else
			// the board names -- later in the list, or already finished -- starts the
			// whole round over AT THIS MOMENT, and banks nothing for as long as this
			// stand lasts.
			if (Idx != INDEX_NONE && Idx != TurnIndex)
			{
				StartRoundOver();
				PoisonedMark = Occupied;
			}
		}
		OccupiedLastFrame = Occupied;
	}

	// ---- 3. BANK, SECOND FOR SECOND, AND ONLY WHERE IT IS ALLOWED. --------------
	// Stepping off pauses a bank; nothing here empties one, so stepping back on
	// carries on from the value it stopped at.
	if (Occupied != nullptr && Occupied != PoisonedMark.Get()
		&& IndexInList(Occupied->MarkName) == TurnIndex)
	{
		float* Bank = Banked.Find(Occupied->MarkName);
		if (Bank == nullptr)
		{
			Bank = &Banked.Add(Occupied->MarkName, 0.0f);
		}
		*Bank += DeltaSeconds;
	}

	// ---- 4. IS THE MARK WHOSE TURN IT IS FINISHED? ------------------------------
	// Against ITS OWN number as that number reads AT THIS MOMENT -- which is why this
	// runs whether or not anybody is still standing there: a number dropped below what
	// is already banked finishes the mark at once.
	for (int32 Guard = 0; Guard <= LastSeenList.Num(); ++Guard)
	{
		if (!LastSeenList.IsValidIndex(TurnIndex))
		{
			break;
		}
		const FName TurnName = LastSeenList[TurnIndex];
		const AFloorMarkActor* const Current = MarkNamed(TurnName);
		float* const Bank = Banked.Find(TurnName);
		if (Current == nullptr || Bank == nullptr)
		{
			break;
		}
		if (*Bank + UE_KINDA_SMALL_NUMBER < Current->RequiredSeconds)
		{
			break;
		}
		// A finished mark stands at its own number until the round starts over.
		*Bank = Current->RequiredSeconds;
		++TurnIndex;
	}

	// ---- 5. SHOW IT. ------------------------------------------------------------
	PaintHall();
}

void ADutyBoardActor::StartRoundOver()
{
	Banked.Reset();
	TurnIndex = 0;
	// The lamps and the faces are not touched here: PaintHall writes the whole hall
	// from this state on the same frame, so there is only ever one place that decides
	// what the hall reads.
}

int32 ADutyBoardActor::IndexInList(FName Name) const
{
	return LastSeenList.IndexOfByKey(Name);
}

AFloorMarkActor* ADutyBoardActor::MarkNamed(FName Name) const
{
	for (AFloorMarkActor* const M : Marks)
	{
		if (M != nullptr && M->MarkName == Name)
		{
			return M;
		}
	}
	return nullptr;
}

AFloorMarkActor* ADutyBoardActor::MarkUnderCharacter() const
{
	const APawn* const Character = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Character == nullptr)
	{
		return nullptr;
	}
	const FVector Where = Character->GetActorLocation();
	for (AFloorMarkActor* const M : Marks)
	{
		// The ring predicate is the mark's own: flat, centre to character, inclusive
		// at the edge. Everybody in the hall means the same thing by "standing on it".
		if (M != nullptr && M->IsInsideRing(Where))
		{
			return M;
		}
	}
	return nullptr;
}

void ADutyBoardActor::PaintHall()
{
	for (AFloorMarkActor* const M : Marks)
	{
		if (M == nullptr)
		{
			continue;
		}
		const float* const Bank = Banked.Find(M->MarkName);
		const int32 Idx = IndexInList(M->MarkName);
		const bool bFinished = (Idx != INDEX_NONE && Idx < TurnIndex);
		// Its own bank out of ITS OWN number, read now -- not a shared constant and
		// not the value it had when somebody started standing here.
		M->ShowBank(Bank != nullptr ? *Bank : 0.0f, M->RequiredSeconds);
		M->SetLampLit(bFinished);
	}
	// How many of the board's marks are finished, out of how many names the board is
	// carrying NOW. The right-hand number is never a constant.
	ShowTally(TurnIndex, LastSeenList.Num());
}

void ADutyBoardActor::RefreshOrderFace()
{
	PaintedOrder = ListedMarkNames;

	if (OrderFace == nullptr)
	{
		return;
	}
	FString Line;
	for (int32 i = 0; i < ListedMarkNames.Num(); ++i)
	{
		if (i > 0)
		{
			Line += TEXT("  >  ");
		}
		Line += ListedMarkNames[i].ToString().ToUpper();
	}
	OrderFace->SetText(FText::FromString(Line));
}

void ADutyBoardActor::ShowTally(int32 FinishedCount, int32 ListLength)
{
	LastShownFinished = FinishedCount;
	LastShownListLength = ListLength;
	bTallyEverWritten = true;

	if (TallyFace != nullptr)
	{
		TallyFace->SetText(FText::FromString(
			FString::Printf(TEXT("%d/%d"), FinishedCount, ListLength)));
	}
}
