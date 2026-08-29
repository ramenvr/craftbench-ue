// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-movement-component-drives-actor.

#include "DriftActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

ADriftActor::ADriftActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}

	Tags.Add(FName("DriftRoot"));

	// A projectile movement component drives the actor at a constant velocity
	// (no gravity, no bounce) — the component updates the transform every frame
	// scaled by DeltaTime, so the motion is smooth and framerate-independent.
	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->SetUpdatedComponent(Body);
	Movement->ProjectileGravityScale = 0.0f;
	Movement->bShouldBounce = false;
	Movement->bRotationFollowsVelocity = false;
	Movement->InitialSpeed = 200.0f;
	Movement->MaxSpeed = 200.0f;
	Movement->Velocity = FVector(200.0f, 0.0f, 0.0f);
}
