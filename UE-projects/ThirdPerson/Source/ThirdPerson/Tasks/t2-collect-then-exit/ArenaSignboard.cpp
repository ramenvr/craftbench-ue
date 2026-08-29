// Copyright CraftBench. All Rights Reserved.

#include "ArenaSignboard.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AArenaSignboard::AArenaSignboard()
{
	PrimaryActorTick.bCanEverTick = false;

	// An UNSCALED root, and the text hangs off THAT. Attached to the board mesh
	// instead, a child's relative offset is multiplied by the mesh's own scale
	// (0.2, 3.6, 2.2), which threw the readouts hundreds of cm out of frame and
	// distorted the glyphs -- measured 2026-08-18, twice, before the cause was
	// obvious. With an unscaled root the offsets below are plain centimetres.
	BoardRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoardRoot"));
	SetRootComponent(BoardRoot);

	BoardMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BoardMesh"));
	BoardMesh->SetupAttachment(BoardRoot);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		BoardMesh->SetStaticMesh(CubeMesh.Object);
	}
	BoardMesh->SetRelativeScale3D(FVector(0.2f, 3.6f, 2.2f));
	BoardMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 110.0f));
	BoardMesh->SetMobility(EComponentMobility::Static);
	BoardMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	// Both faces read from the actor's +X side, so placing the board yawed 180
	// turns them down the arena -- the direction the character walks in from and
	// the direction every camera in the plan looks from.
	TallyText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("TallyText"));
	TallyText->SetupAttachment(BoardRoot);
	TallyText->SetRelativeLocation(FVector(-15.0f, 0.0f, 165.0f));
	TallyText->SetHorizontalAlignment(EHTA_Center);
	TallyText->SetWorldSize(95.0f);
	TallyText->SetTextRenderColor(FColor(255, 238, 120));
	TallyText->SetText(FText::GetEmpty());

	StatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("StatusText"));
	StatusText->SetupAttachment(BoardRoot);
	StatusText->SetRelativeLocation(FVector(-15.0f, 0.0f, 60.0f));
	StatusText->SetHorizontalAlignment(EHTA_Center);
	StatusText->SetWorldSize(70.0f);
	StatusText->SetTextRenderColor(FColor(150, 225, 255));
	StatusText->SetText(FText::GetEmpty());

	Tags.Add(FName("ArenaBoard"));
}
