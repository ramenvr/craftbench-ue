// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (gravity-acceleration-ramp) for task
// t1-movement-component-drives-actor. ONE DELTA vs the reference: gravity is
// enabled (ProjectileGravityScale 0 -> 1) and the speed clamp removed
// (MaxSpeed 200 -> 0 = uncapped), so the actor accelerates over the test
// window instead of drifting at a steady speed. Predicted per-interval steps
// at 0.5 s spacing: ~381 / ~621 / ~863 uu — |d12-d01|/max = ~0.39 > the 30%
// tolerance, so the equal-displacement check fires (ContinuesMoving passes
// first: d23 ~863 uu >> 20 uu).

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

	// A projectile movement component drives the actor — but with gravity on
	// and the speed clamp removed, so speed GROWS over time (the acceleration
	// ramp the ConstantVelocity gate exists to catch).
	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->SetUpdatedComponent(Body);
	Movement->ProjectileGravityScale = 1.0f;
	Movement->bShouldBounce = false;
	Movement->bRotationFollowsVelocity = false;
	Movement->InitialSpeed = 200.0f;
	Movement->MaxSpeed = 0.0f;
	Movement->Velocity = FVector(200.0f, 0.0f, 0.0f);
}
