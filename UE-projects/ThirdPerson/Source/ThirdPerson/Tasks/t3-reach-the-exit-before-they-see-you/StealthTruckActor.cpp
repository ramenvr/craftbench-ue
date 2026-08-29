// Copyright CraftBench. All Rights Reserved.

#include "StealthTruckActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** How close to an end of the rail counts as having reached it. */
	constexpr double kRailArriveUu = 4.0;
}

AStealthTruckActor::AStealthTruckActor()
{
	// It drives itself, every frame, for as long as the night lasts.
	PrimaryActorTick.bCanEverTick = true;

	// An unscaled anchor at floor level is the root, and the box hangs off it. The box
	// itself is NOT the root: a root component's relative location IS the actor's
	// location, so seating the box above the floor by moving it would move the whole
	// actor -- and this actor's location is the middle of its own rail.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);
	Anchor->SetMobility(EComponentMobility::Movable);

	Block = CreateDefaultSubobject<UBoxComponent>(TEXT("Block"));
	Block->SetupAttachment(Anchor);
	Block->SetCollisionProfileName(TEXT("BlockAll"));
	Block->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Block->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Block);
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName(TEXT("StealthTruck")));
}

void AStealthTruckActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	if (Block == nullptr)
	{
		return;
	}
	const FVector Half(
		FMath::Max(1.0, double(TruckHalfExtentUu.X)),
		FMath::Max(1.0, double(TruckHalfExtentUu.Y)),
		FMath::Max(1.0, double(TruckHalfExtentUu.Z)));

	Block->SetBoxExtent(Half, /*bUpdateOverlaps=*/false);
	// The actor's location is at floor level and the truck rides up from there. This
	// moves the BOX, never the actor -- the actor's own location is the rail's middle.
	Block->SetRelativeLocation(FVector(0.0, 0.0, Half.Z));

	if (Body != nullptr)
	{
		Body->SetRelativeScale3D(FVector(Half.X * 2.0 / 100.0,
										 Half.Y * 2.0 / 100.0,
										 Half.Z * 2.0 / 100.0));
		Body->SetRelativeLocation(FVector::ZeroVector);
	}
}

void AStealthTruckActor::BeginPlay()
{
	Super::BeginPlay();

	// The middle of the rail is wherever the yard set the truck down.
	HomeLocation = GetActorLocation();
	bHeadingToB = true;
}

void AStealthTruckActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (DeltaSeconds <= 0.0f || RailSpeedUuPerSec <= 0.0f)
	{
		return;
	}
	if (RailHalfSpanUu.IsNearlyZero())
	{
		return;
	}

	const FVector Here = GetActorLocation();
	FVector Target = bHeadingToB ? GetRailEndB() : GetRailEndA();
	FVector Along = Target - Here;
	if (Along.Size() <= kRailArriveUu)
	{
		// Turn round AND keep going in the same frame: a truck that stood still for
		// the frame it turned would put a one-frame hole in where it is, and where it
		// is at this instant is the whole point of it.
		bHeadingToB = !bHeadingToB;
		Target = bHeadingToB ? GetRailEndB() : GetRailEndA();
		Along = Target - Here;
	}
	const double Distance = Along.Size();
	if (Distance <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	// Never overshoot the end of the rail, whatever the frame length.
	const double Travel = FMath::Min(Distance, double(RailSpeedUuPerSec) * DeltaSeconds);
	// No sweep: the truck runs its own rail and is never asked to shove anything. The
	// yard is laid out so nothing of the route is ever on the rail.
	SetActorLocation(Here + (Along / Distance) * Travel, /*bSweep=*/false);
}
