// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "fakes-fall-in-tick" for task t1-physics-drop-and-rest.
// ONE COHERENT DELTA vs the reference: SetSimulatePhysics(true) is replaced by a
// manual constant-rate descent in Tick (no sweep). Checkpoint 0 passes (the
// collision responses are set), checkpoint 1 passes (it descended far more than
// 50 units), but the actor never stops — checkpoint 3's rest gate must fire
// ("it should have come to rest"), which the code checks BEFORE the floor gate.

#include "PhysicsDropActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

APhysicsDropActor::APhysicsDropActor()
{
	// DELTA: tick-driven fake fall needs the actor tick.
	PrimaryActorTick.bCanEverTick = true;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	Body->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}

	Tags.Add(FName("PhysicsDropRoot"));

	// Dynamic physics object: simulate + query collision so it falls and can land.
	Body->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Body->SetCollisionObjectType(ECC_PhysicsBody);
	Body->SetCollisionResponseToAllChannels(ECR_Block);
	// Ignore the player (Pawn) channel; still block static world geometry so it
	// comes to rest on the floor.
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Body->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
	// DELTA: no SetSimulatePhysics(true) — the "fall" is faked in Tick below.
}

void APhysicsDropActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// DELTA: constant-rate manual descent, no sweep — looks like falling by
	// checkpoint 1, but never decelerates and never rests.
	AddActorWorldOffset(FVector(0.0, 0.0, -200.0 * DeltaSeconds), /*bSweep=*/false);
}
