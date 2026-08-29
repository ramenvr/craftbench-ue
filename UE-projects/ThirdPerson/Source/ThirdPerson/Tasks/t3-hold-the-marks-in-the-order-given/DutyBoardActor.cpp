// Copyright CraftBench. All Rights Reserved.

#include "DutyBoardActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
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
	// The board ticks for ONE reason: to keep the ORDER face reading whatever list it
	// is currently carrying. It decides nothing and it never writes the tally.
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

	// A blank tally face from the first frame, whatever the editor left behind. NOTE
	// that a blank tally is NOT what the board is supposed to read: at the start of a
	// round it reads none-of-them out of however many names it is carrying, and
	// somebody has to write that.
	if (TallyFace != nullptr)
	{
		TallyFace->SetText(FText::GetEmpty());
	}
	LastShownFinished = -1;
	LastShownListLength = -1;
	bTallyEverWritten = false;

	PaintedOrder.Reset();
	RefreshOrderFace();
}

void ADutyBoardActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The order face follows the list and nothing else happens here.
	if (PaintedOrder != ListedMarkNames)
	{
		RefreshOrderFace();
	}
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
