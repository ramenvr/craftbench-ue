// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "ignores-world-static" for task t1-physics-drop-and-rest.
// ONE DELTA vs the reference: the response base is Ignore-all and the explicit
// WorldStatic Block line is gone — the cheap "ignore everything so it never
// collides with the player" shortcut. The Pawn probe passes (Ignore), then the
// WorldStatic probe at checkpoint 0 must fire ("must be Block").

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
	// DELTA: ignore EVERY channel (including WorldStatic) instead of blocking the
	// world — "it must not collide with the player" gamed by not colliding at all.
	Body->SetCollisionResponseToAllChannels(ECR_Ignore);
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Body->SetSimulatePhysics(true);
}
