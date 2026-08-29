// GAMING VARIANT (anti-gaming note #2): a straight-line shot — aims the
// initial velocity at the target's ORIGINAL position and never steers.
// Intercepts a stationary target fine; fails after the fixture relocates
// the target (stops closing / never arrives).

#include "HomingMissile.h"

#include "Components/SceneComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"

AHomingMissile::AHomingMissile()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
	Tags.Add(FName("HomingMissile"));

	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->InitialSpeed = 1000.0f;
	Movement->MaxSpeed = 1100.0f;
	Movement->ProjectileGravityScale = 0.0f;
	Movement->bRotationFollowsVelocity = true;
	// NO homing: bIsHomingProjectile stays false.
}

void AHomingMissile::InitHoming(AActor* InTarget)
{
	if (InTarget == nullptr)
	{
		return;
	}
	// One-shot aim at the CURRENT (initial) target position; never re-steers.
	const FVector ToTarget = (InTarget->GetActorLocation() - GetActorLocation()).GetSafeNormal();
	Movement->Velocity = ToTarget * Movement->InitialSpeed;
}
