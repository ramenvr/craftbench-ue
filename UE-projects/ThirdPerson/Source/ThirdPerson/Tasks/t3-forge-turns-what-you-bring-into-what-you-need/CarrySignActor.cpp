// Copyright CraftBench. All Rights Reserved.

#include "CarrySignActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* const kPostMesh = TEXT("/Engine/BasicShapes/Cube");
	const TCHAR* const kPostLook =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
}

ACarrySignActor::ACarrySignActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(kPostMesh);

	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	SetRootComponent(Post);
	if (CubeMesh.Succeeded())
	{
		Post->SetStaticMesh(CubeMesh.Object);
	}
	// A 260 x 30 x 220 cm standing board.
	Post->SetRelativeScale3D(FVector(2.6f, 0.3f, 2.2f));
	Post->SetMobility(EComponentMobility::Movable);
	// NO COLLISION, both ways round: the profile AND the enum. The sign stands beside
	// the PlayerStart, and a solid board there would jam the first step of every walk.
	Post->SetCollisionProfileName(TEXT("NoCollision"));
	Post->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kPostLook);
	if (Look.Succeeded())
	{
		Post->SetMaterial(0, Look.Object);
	}

	Notice = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Notice"));
	Notice->SetupAttachment(Post);
	// Relative offsets are multiplied by the post's own non-uniform scale, so the
	// 25 uu of clearance is divided back out of it (0.3 in Y) to land 25 uu proud of
	// the face rather than 7 uu inside it. The scale is divided out for the same
	// reason: a 2.6 x 0.3 x 2.2 parent would otherwise stretch the lettering.
	Notice->SetRelativeLocation(FVector(0.0f, -25.0f / 0.3f, 0.0f));
	Notice->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	Notice->SetRelativeScale3D(FVector(1.0f / 2.6f, 1.0f / 0.3f, 1.0f / 2.2f));
	Notice->SetHorizontalAlignment(EHTA_Center);
	Notice->SetVerticalAlignment(EVRTA_TextCenter);
	Notice->SetWorldSize(52.0f);
	Notice->SetTextRenderColor(FColor(255, 190, 140));
	Notice->SetMobility(EComponentMobility::Movable);
	Notice->SetText(FText::FromString(TEXT("--")));

	Tags.Add(FName("CarrySign"));
}

void ACarrySignActor::BeginPlay()
{
	Super::BeginPlay();

	// Say what you post from the first frame, whatever the editor left behind.
	RefreshNotice();
}

void ACarrySignActor::RefreshNotice()
{
	if (Notice != nullptr)
	{
		Notice->SetText(FText::FromString(
			FString::Printf(TEXT("CARRY AT MOST %d"), CarryCapUnits)));
	}
}
