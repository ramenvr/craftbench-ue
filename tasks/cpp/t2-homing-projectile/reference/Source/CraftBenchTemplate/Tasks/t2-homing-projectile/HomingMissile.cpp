// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-homing-projectile. Speed stays inside the
// disclosed 600-1200 u/s band; homing acceleration is high enough to
// re-steer onto a target relocated 800 units laterally mid-flight.

#include "HomingMissile.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

AHomingMissile::AHomingMissile()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
	Tags.Add(FName("HomingMissile"));

	// Showcase-visibility only: a small sphere so the missile shows up in
	// captures — the verifier samples the root's trajectory, never meshes or
	// pixels. Attached to the existing scene root (root/Movement unchanged);
	// collision disabled so the flight the fixture polices is unaffected.
	Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShowcaseVisual"));
	Visual->SetupAttachment(Root);
	Visual->SetMobility(EComponentMobility::Movable);
	Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Visual->SetGenerateOverlapEvents(false);
	Visual->SetRelativeScale3D(FVector(0.3f));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMeshFinder(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (SphereMeshFinder.Succeeded())
	{
		Visual->SetStaticMesh(SphereMeshFinder.Object);
	}

	Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
	Movement->InitialSpeed = 1000.0f;
	Movement->MaxSpeed = 1100.0f;
	Movement->ProjectileGravityScale = 0.0f;
	Movement->bRotationFollowsVelocity = true;
	Movement->bIsHomingProjectile = true;
	Movement->HomingAccelerationMagnitude = 12000.0f;
}

void AHomingMissile::InitHoming(AActor* InTarget)
{
	if (InTarget == nullptr || InTarget->GetRootComponent() == nullptr)
	{
		return;
	}
	const FVector ToTarget = (InTarget->GetActorLocation() - GetActorLocation()).GetSafeNormal();
	Movement->Velocity = ToTarget * Movement->InitialSpeed;
	Movement->HomingTargetComponent = InTarget->GetRootComponent();
}
