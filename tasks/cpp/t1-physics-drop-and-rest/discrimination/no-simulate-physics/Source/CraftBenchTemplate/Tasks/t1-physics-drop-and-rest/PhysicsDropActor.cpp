// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "no-simulate-physics" for task t1-physics-drop-and-rest.
// ONE DELTA vs the reference: SetSimulatePhysics(true) is missing. The collision
// responses pass checkpoint 0, but the cube never descends, so checkpoint 1's
// descend gate must fire ("Is dynamic physics enabled?").

#include "PhysicsDropActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

APhysicsDropActor::APhysicsDropActor()
{
	PrimaryActorTick.bCanEverTick = false;

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
	// DELTA: no SetSimulatePhysics(true) — physics is never enabled.
}
