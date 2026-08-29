// Copyright CraftBench. All Rights Reserved.

#include "MemoryBoardActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The actor's origin sits ON THE FLOOR, and the root is a bare scene component with
	// no scale of its own.
	const FVector kMastScale(0.6f, 0.6f, 3.0f);        // 60 x 60 x 300
	constexpr float kMastCentreZ = 150.0f;

	const FVector kBoardOffset(0.0f, -40.0f, 330.0f);

	const TCHAR* const kMastMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AMemoryBoardActor::AMemoryBoardActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	USceneComponent* const Base = CreateDefaultSubobject<USceneComponent>(TEXT("Base"));
	SetRootComponent(Base);
	// MOVABLE: the board is destroyed and respawned mid-run, and PIE scores moving a
	// STATIC actor as a failed test.
	Base->SetMobility(EComponentMobility::Movable);

	Mast = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mast"));
	Mast->SetupAttachment(Base);
	if (CubeMesh.Succeeded())
	{
		Mast->SetStaticMesh(CubeMesh.Object);
	}
	Mast->SetRelativeLocation(FVector(0.0f, 0.0f, kMastCentreZ));
	Mast->SetRelativeScale3D(kMastScale);
	Mast->SetMobility(EComponentMobility::Movable);
	Mast->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MastLook(kMastMaterial);
	if (MastLook.Succeeded())
	{
		Mast->SetMaterial(0, MastLook.Object);
	}

	Board = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Board"));
	Board->SetupAttachment(Base);
	Board->SetRelativeLocation(kBoardOffset);
	// Yaw -90 turns the text's readable face from +X to -Y, the side the yard is walked
	// from.
	Board->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	Board->SetMobility(EComponentMobility::Movable);
	Board->SetHorizontalAlignment(EHTA_Center);
	Board->SetVerticalAlignment(EVRTA_TextBottom);
	Board->SetWorldSize(38.0f);
	Board->SetTextRenderColor(FColor(180, 240, 255));

	Tags.Add(FName("MemoryBoard"));
}

void AMemoryBoardActor::BeginPlay()
{
	Super::BeginPlay();

	// A board in a yard nobody has visited reads nothing. Anything past that is
	// somebody else's decision.
	ShowTotal(0);
}

void AMemoryBoardActor::ShowTotal(int32 Total)
{
	LastShownTotal = Total;

	if (Board != nullptr)
	{
		Board->SetText(FText::FromString(
			FString::Printf(TEXT("%s  banked %d"), *YardName.ToString(), Total)));
	}
}
