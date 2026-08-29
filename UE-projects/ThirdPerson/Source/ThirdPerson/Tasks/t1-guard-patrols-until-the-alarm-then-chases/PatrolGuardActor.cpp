// Copyright CraftBench. All Rights Reserved.

#include "PatrolGuardActor.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

APatrolGuardActor::APatrolGuardActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone"));

	Hull = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Hull"));
	SetRootComponent(Hull);
	// 70 cm across, 180 cm tall. The actor stands with this capsule's CENTRE at its
	// location, the way a character does, so the level places the guard at half its
	// height and its feet land on the floor.
	Hull->InitCapsuleSize(35.0f, 90.0f);
	Hull->SetCollisionProfileName(TEXT("BlockAll"));
	Hull->SetMobility(EComponentMobility::Movable);

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Hull);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// Centred on the hull, so what a reviewer sees and what the guard bumps into
	// are the same 70 x 180 cm.
	Body->SetRelativeScale3D(FVector(0.7f, 0.7f, 1.8f));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	// A cone on the front, laid on its side so it points the way the guard faces.
	// Attached to the HULL, not the body, so the body's scale does not distort it.
	Snout = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Snout"));
	Snout->SetupAttachment(Hull);
	if (ConeMesh.Succeeded())
	{
		Snout->SetStaticMesh(ConeMesh.Object);
	}
	Snout->SetRelativeScale3D(FVector(0.4f, 0.4f, 0.7f));
	Snout->SetRelativeLocation(FVector(45.0f, 0.0f, 60.0f));
	Snout->SetRelativeRotation(FRotator(-90.0f, 0.0f, 0.0f));
	Snout->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SnoutLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (SnoutLook.Succeeded())
	{
		Snout->SetMaterial(0, SnoutLook.Object);
	}

	Tags.Add(FName("PatrolGuard"));
}

void APatrolGuardActor::BeginPlay()
{
	Super::BeginPlay();

	if (Body != nullptr)
	{
		BodyMaterial = Body->CreateAndSetMaterialInstanceDynamic(0);
	}
}

void APatrolGuardActor::StepToward(const FVector& Destination, float SpeedUu,
	float DeltaSeconds)
{
	if (DeltaSeconds <= 0.0f || SpeedUu <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	// Flat: the yard is level, and letting a destination's height into this would walk
	// the guard into the floor or up into the air.
	const FVector Flat(Destination.X - Here.X, Destination.Y - Here.Y, 0.0);
	const double Distance = Flat.Size();
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	const FVector Direction = Flat / Distance;
	// Never overshoot: a long frame must not teleport the guard past its destination.
	const double Travel = FMath::Min(Distance, double(SpeedUu) * DeltaSeconds);
	SetActorLocation(Here + Direction * Travel, /*bSweep=*/true);
	SetActorRotation(Direction.Rotation());
}

bool APatrolGuardActor::HasReached(const FVector& Point) const
{
	const FVector Here = GetActorLocation();
	return FVector(Point.X - Here.X, Point.Y - Here.Y, 0.0).Size() <= ArriveRadiusUu;
}
