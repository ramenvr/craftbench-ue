// Copyright CraftBench. All Rights Reserved.

#include "AlarmPanelActor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FLinearColor kRingingColour(1.0f, 0.05f, 0.03f);
	const FLinearColor kRestColour(0.07f, 0.07f, 0.08f);
	constexpr float kRingingIntensity = 6000.0f;
}

AAlarmPanelActor::AAlarmPanelActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	SetRootComponent(Board);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}
	// A board standing on edge: 40 cm thick, 300 wide, 260 tall.
	Board->SetRelativeScale3D(FVector(0.4f, 3.0f, 2.6f));
	Board->SetRelativeLocation(FVector(0.0f, 0.0f, 130.0f));
	Board->SetMobility(EComponentMobility::Movable);
	Board->SetCollisionProfileName(TEXT("BlockAll"));

	// The plate sits WELL in front of the board -- 3 m, not flush with it. A plate
	// tucked against the board puts the board between the plate and everything that
	// wants to reach it, and both the character walking up and the guard coming for
	// the character arrive from that side. Its offsets are divided back out of the
	// board's (0.4, 3.0, 2.6) scale.
	Plate = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plate"));
	Plate->SetupAttachment(Board);
	if (CubeMesh.Succeeded())
	{
		Plate->SetStaticMesh(CubeMesh.Object);
	}
	Plate->SetRelativeScale3D(FVector(2.4f / 0.4f, 2.4f / 3.0f, 0.1f / 2.6f));
	Plate->SetRelativeLocation(
		FVector(300.0f / 0.4f, 0.0f, (5.0f - 130.0f) / 2.6f));
	Plate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlateLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (PlateLook.Succeeded())
	{
		Plate->SetMaterial(0, PlateLook.Object);
	}

	// The volume is deliberately TALLER than the plate so a character standing on it
	// overlaps at the ankles and stays overlapping; a volume flush with a 10 cm plate
	// is exited by the ordinary step cycle.
	PlateVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PlateVolume"));
	PlateVolume->SetupAttachment(Board);
	PlateVolume->SetBoxExtent(FVector(120.0f, 120.0f, 90.0f));
	PlateVolume->SetRelativeScale3D(FVector(1.0f / 0.4f, 1.0f / 3.0f, 1.0f / 2.6f));
	PlateVolume->SetRelativeLocation(
		FVector(300.0f / 0.4f, 0.0f, (90.0f - 130.0f) / 2.6f));
	PlateVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PlateVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	PlateVolume->SetGenerateOverlapEvents(true);

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Board);
	Lamp->SetRelativeLocation(FVector(120.0f / 0.4f, 0.0f, (240.0f - 130.0f) / 2.6f));
	Lamp->SetLightColor(kRingingColour);
	Lamp->SetIntensity(0.0f);
	Lamp->SetAttenuationRadius(900.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("AlarmPanel"));
}

void AAlarmPanelActor::BeginPlay()
{
	Super::BeginPlay();

	if (Board != nullptr)
	{
		BoardMaterial = Board->CreateAndSetMaterialInstanceDynamic(0);
	}
	if (PlateVolume != nullptr)
	{
		PlateVolume->OnComponentBeginOverlap.AddDynamic(
			this, &AAlarmPanelActor::OnPlateBegin);
		PlateVolume->OnComponentEndOverlap.AddDynamic(
			this, &AAlarmPanelActor::OnPlateEnd);
	}
	Occupants = 0;
	Refresh();
}

void AAlarmPanelActor::OnPlateBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	// Pawns only: the guard's own body is a prop and must not set off the alarm it is
	// supposed to be responding to.
	if (Cast<APawn>(OtherActor) != nullptr)
	{
		++Occupants;
		Refresh();
	}
}

void AAlarmPanelActor::OnPlateEnd(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32)
{
	if (Cast<APawn>(OtherActor) != nullptr)
	{
		Occupants = FMath::Max(0, Occupants - 1);
		Refresh();
	}
}

void AAlarmPanelActor::Refresh()
{
	const bool bRinging = IsRinging();
	if (BoardMaterial != nullptr)
	{
		BoardMaterial->SetVectorParameterValue(
			TEXT("Color"), bRinging ? kRingingColour : kRestColour);
	}
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bRinging ? kRingingIntensity : 0.0f);
	}
}
