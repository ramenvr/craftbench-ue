// Copyright CraftBench. All Rights Reserved.

#include "StealthStartPlateActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AStealthStartPlateActor::AStealthStartPlateActor()
{
	// Nothing to tick: the plate answers a step, and a step is an event.
	PrimaryActorTick.bCanEverTick = false;

	// An unscaled anchor at floor level is the root, and everything hangs off it at
	// plain centimetres above the floor. The volume is NOT the root: a root component's
	// relative location IS the actor's location, so seating the region above the floor
	// by moving it would move the whole actor.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	// 240 x 240 cm of floor, 80 cm of air above it: a region somebody standing on the
	// pad is inside, whatever their feet are doing.
	PlateVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PlateVolume"));
	PlateVolume->SetupAttachment(Anchor);
	PlateVolume->SetBoxExtent(FVector(120.0f, 120.0f, 40.0f));
	PlateVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	PlateVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	PlateVolume->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	// 240 x 240 x 4 cm, lying on the floor. NON-COLLIDING, and that is not tidiness: a
	// solid pad would stop a line taken close to the floor, and the yard promises that
	// the plate never blocks anything. You stand on the floor; the pad is paint.
	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(Anchor);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, 2.0f));
	Pad->SetRelativeScale3D(FVector(2.4f, 2.4f, 0.04f));
	// The PROFILE as well as the enum: on an earlier task set_collision_enabled alone
	// did not survive into the saved level.
	Pad->SetCollisionProfileName(TEXT("NoCollision"));
	Pad->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PadLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (PadLook.Succeeded())
	{
		Pad->SetMaterial(0, PadLook.Object);
	}

	Face = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Face"));
	Face->SetupAttachment(Anchor);
	Face->SetRelativeLocation(FVector(0.0f, 0.0f, 360.0f));
	Face->SetHorizontalAlignment(EHTA_Center);
	Face->SetWorldSize(110.0f);
	Face->SetTextRenderColor(FColor(235, 235, 235));
	Face->SetText(FText::FromString(TEXT("0")));
	Face->SetCollisionProfileName(TEXT("NoCollision"));
	Face->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(FName(TEXT("StealthStartPlate")));
}

void AStealthStartPlateActor::BeginPlay()
{
	Super::BeginPlay();

	if (PlateVolume != nullptr)
	{
		PlateVolume->OnComponentBeginOverlap.AddDynamic(
			this, &AStealthStartPlateActor::OnPlateBeginOverlap);
	}
	RepaintFace();
}

void AStealthStartPlateActor::OnPlateBeginOverlap(UPrimitiveComponent* /*OverlappedComponent*/,
												  AActor* OtherActor,
												  UPrimitiveComponent* /*OtherComp*/,
												  int32 /*OtherBodyIndex*/,
												  bool /*bFromSweep*/,
												  const FHitResult& /*SweepResult*/)
{
	// Somebody, not something: the truck and the watchers are not somebody.
	if (Cast<APawn>(OtherActor) == nullptr)
	{
		return;
	}
	++RoundIndex;
	RepaintFace();
}

void AStealthStartPlateActor::RepaintFace()
{
	if (Face != nullptr)
	{
		Face->SetText(FText::FromString(FString::Printf(TEXT("%d"), RoundIndex)));
	}
}
