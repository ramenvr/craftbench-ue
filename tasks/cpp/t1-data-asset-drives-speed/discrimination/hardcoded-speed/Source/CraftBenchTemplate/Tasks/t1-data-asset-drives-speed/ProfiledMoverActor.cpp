// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-data-asset-drives-speed.

#include "ProfiledMoverActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "MovementProfileAsset.h"
#include "UObject/ConstructorHelpers.h"

AProfiledMoverActor::AProfiledMoverActor()
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

	Profile = nullptr;
	Tags.Add(FName("ProfiledMoverRoot"));

	// Constant-velocity mover (no gravity); velocity is set from the profile in
	// BeginPlay once the configured speed is known.
	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->SetUpdatedComponent(Body);
	Movement->ProjectileGravityScale = 0.0f;
	Movement->bShouldBounce = false;
	Movement->bRotationFollowsVelocity = false;
}

void AProfiledMoverActor::BeginPlay()
{
	Super::BeginPlay();
	if (Profile != nullptr && Movement != nullptr)
	{
		// GAMED DELTA (variant hardcoded-speed, anti-gaming note #1/#4): a
		// number written in code instead of Profile->CruiseSpeed. The actor
		// moves confidently -- at the wrong rate.
		const float Speed = 300.0f;
		Movement->InitialSpeed = Speed;
		Movement->MaxSpeed = Speed;
		Movement->Velocity = GetActorForwardVector() * Speed;
	}
}
