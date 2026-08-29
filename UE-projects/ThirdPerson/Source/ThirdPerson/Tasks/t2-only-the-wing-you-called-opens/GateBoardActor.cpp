// Copyright CraftBench. All Rights Reserved.

#include "GateBoardActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AGateBoardActor::AGateBoardActor()
{
	// Nothing to tick as shipped: a board decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));

	// A 520 x 30 x 180 cm board hanging over the gate.
	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	Board->SetupAttachment(Pivot);
	Board->SetRelativeScale3D(FVector(5.2f, 0.3f, 1.8f));
	Board->SetCollisionProfileName(TEXT("NoCollision"));
	Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Look.Succeeded())
	{
		Board->SetMaterial(0, Look.Object);
	}

	Line = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Line"));
	Line->SetupAttachment(Pivot);
	Line->SetRelativeLocation(FVector(0.0f, -20.0f, 0.0f));
	Line->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Line->SetHorizontalAlignment(EHTA_Center);
	Line->SetVerticalAlignment(EVRTA_TextCenter);
	Line->SetWorldSize(120.0f);
	Line->SetTextRenderColor(FColor(255, 240, 200));
	Line->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Line->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("GateBoard")));
}

void AGateBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// The board says what it says from the first frame of play, whatever the editor
	// left behind: nothing has been called, and nothing of a called wing is standing.
	Report(NAME_None, 0);
}

void AGateBoardActor::Report(FName WingName, int32 StandingCount)
{
	// FName's own empty value prints as "None", which upper-cases to the NONE the
	// board is supposed to show before anything has been called.
	const FString Name = WingName.ToString().ToUpper();
	const int32 Count = FMath::Max(0, StandingCount);

	if (Line != nullptr)
	{
		Line->SetText(FText::FromString(FString::Printf(TEXT("%s %d"), *Name, Count)));
	}
}

FString AGateBoardActor::GetReportedLine() const
{
	return Line != nullptr ? Line->Text.ToString() : FString();
}
