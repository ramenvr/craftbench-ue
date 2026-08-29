// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-data-asset-drives-speed.

#include "ProfiledMoverActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "MovementProfileAsset.h"
#include "TimerManager.h"
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
		// WRONG-TIME DELTA (variant applies-too-late, anti-gaming note #2's
		// boundary): reads the profile CORRECTLY but only applies it at
		// t=0.9s -- after the fixture's 0.5s moving-by-now checkpoint. Probes
		// that "when gameplay begins" is a real gate, not just "eventually".
		const float Speed = Profile->CruiseSpeed;
		FTimerHandle StartTimer;
		GetWorldTimerManager().SetTimer(
			StartTimer,
			FTimerDelegate::CreateWeakLambda(this, [this, Speed]()
			{
				Movement->InitialSpeed = Speed;
				Movement->MaxSpeed = Speed;
				Movement->Velocity = GetActorForwardVector() * Speed;
			}),
			0.9f, false);
	}
}
