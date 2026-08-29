// Copyright CraftBench. All Rights Reserved.

#include "RaceReplayPadActor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ARaceReplayPadActor::ARaceReplayPadActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Plate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plate"));
	SetRootComponent(Plate);
	if (CubeMesh.Succeeded())
	{
		Plate->SetStaticMesh(CubeMesh.Object);
	}
	// 260 cm across and 8 cm proud. Flat enough that a character walks onto it, and
	// LOW enough that its box does not have to fight the capsule for room.
	Plate->SetRelativeScale3D(FVector(2.6f, 2.6f, 0.08f));
	Plate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlateLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (PlateLook.Succeeded())
	{
		Plate->SetMaterial(0, PlateLook.Object);
	}

	// The volume is TALLER than the plate: a box flush with an 8 cm plate is exited
	// by the ordinary step cycle, and the pad would flicker.
	Volume = CreateDefaultSubobject<UBoxComponent>(TEXT("Volume"));
	Volume->SetupAttachment(Plate);
	Volume->SetBoxExtent(FVector(130.0f, 130.0f, 100.0f));
	// The plate is scaled (2.6, 2.6, 0.08), so the box's own scale undoes that and
	// its extents above are plain centimetres.
	Volume->SetRelativeScale3D(FVector(1.0f / 2.6f, 1.0f / 2.6f, 1.0f / 0.08f));
	Volume->SetRelativeLocation(FVector(0.0f, 0.0f, 100.0f / 0.08f * 0.08f));
	Volume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Volume->SetCollisionResponseToAllChannels(ECR_Overlap);
	Volume->SetGenerateOverlapEvents(true);

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Plate);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 220.0f / 0.08f * 0.08f));
	Lamp->SetLightColor(FLinearColor(0.25f, 1.0f, 0.4f));
	Lamp->SetIntensity(0.0f);
	Lamp->SetAttenuationRadius(800.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("RaceReplayPad"));
}

void ARaceReplayPadActor::BeginPlay()
{
	Super::BeginPlay();

	if (Volume != nullptr)
	{
		Volume->OnComponentBeginOverlap.AddDynamic(
			this, &ARaceReplayPadActor::OnPadBegin);
		Volume->OnComponentEndOverlap.AddDynamic(
			this, &ARaceReplayPadActor::OnPadEnd);
	}
	Occupants = 0;
	RefreshLamp();
}

void ARaceReplayPadActor::OnPadBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	if (Cast<APawn>(OtherActor) != nullptr)
	{
		++Occupants;
		RefreshLamp();
	}
}

void ARaceReplayPadActor::OnPadEnd(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32)
{
	if (Cast<APawn>(OtherActor) != nullptr)
	{
		Occupants = FMath::Max(0, Occupants - 1);
		RefreshLamp();
	}
}

void ARaceReplayPadActor::RefreshLamp()
{
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(Occupants > 0 ? 6000.0f : 0.0f);
	}
}
