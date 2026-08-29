// Copyright CraftBench. All Rights Reserved.

#include "StealthBlockerActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AStealthBlockerActor::AStealthBlockerActor()
{
	// Nothing to tick: a crate is a thing, not a decision.
	PrimaryActorTick.bCanEverTick = false;

	// An unscaled anchor at floor level is the root, and the box hangs off it. The box
	// itself is NOT the root: a root component's relative location IS the actor's
	// location, so seating the box above the floor by moving it would move the whole
	// actor and the yard would no longer be where the yard put it.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);
	Anchor->SetMobility(EComponentMobility::Movable);

	Block = CreateDefaultSubobject<UBoxComponent>(TEXT("Block"));
	Block->SetupAttachment(Anchor);
	// Solid to everything -- what stops you walking is exactly what stops a line.
	Block->SetCollisionProfileName(TEXT("BlockAll"));
	Block->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	// Movable rather than Static: OnConstruction re-seats the box from
	// BlockHalfExtentUu, and a Static component that is ever re-seated logs a mobility
	// warning that reads like a defect in whatever ran last.
	Block->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Block);
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}
	// The box is the collision; the mesh is only the face of it.
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName(TEXT("StealthBlocker")));
}

void AStealthBlockerActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	if (Block == nullptr)
	{
		return;
	}
	const FVector Half(
		FMath::Max(1.0, double(BlockHalfExtentUu.X)),
		FMath::Max(1.0, double(BlockHalfExtentUu.Y)),
		FMath::Max(1.0, double(BlockHalfExtentUu.Z)));

	Block->SetBoxExtent(Half, /*bUpdateOverlaps=*/false);
	// The actor's location is at floor level and the block rises from there, so the box
	// centre sits half a block up. This moves the BOX, never the actor.
	Block->SetRelativeLocation(FVector(0.0, 0.0, Half.Z));

	if (Body != nullptr)
	{
		// The engine cube is 100 cm on a side, and the root is deliberately unscaled,
		// so this is plain centimetres divided by a hundred.
		Body->SetRelativeScale3D(FVector(Half.X * 2.0 / 100.0,
										 Half.Y * 2.0 / 100.0,
										 Half.Z * 2.0 / 100.0));
		Body->SetRelativeLocation(FVector::ZeroVector);
	}
}
