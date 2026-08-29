// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (spawns-tagged-proxy-mover) for task
// t1-movement-component-drives-actor. ONE DELTA vs the reference: the placed
// actor stays motionless; BeginPlay spawns a proxy StaticMeshActor, tags it
// 'DriftRoot', and attaches a correctly-configured projectile movement
// component to the PROXY. The proxy drifts perfectly — but the placed actor's
// BeginPlay runs before PrepareTest, so the fixture's tag lookup finds TWO
// tagged actors and fails the exactly-one resolve gate before any motion is
// ever sampled.

#include "DriftActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
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
}

void ADriftActor::BeginPlay()
{
	Super::BeginPlay();

	// Spawn a fresh proxy, give it the identity tag, and drive the PROXY with
	// a movement component — leaving this placed actor untouched.
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AStaticMeshActor* Proxy = World->SpawnActor<AStaticMeshActor>(
		GetActorLocation() + FVector(0.0f, 200.0f, 0.0f), FRotator::ZeroRotator, SpawnParams);
	if (Proxy == nullptr)
	{
		return;
	}
	Proxy->SetMobility(EComponentMobility::Movable);
	Proxy->Tags.Add(FName("DriftRoot"));

	UProjectileMovementComponent* ProxyMovement =
		NewObject<UProjectileMovementComponent>(Proxy, TEXT("ProxyMovement"));
	ProxyMovement->SetUpdatedComponent(Proxy->GetRootComponent());
	ProxyMovement->ProjectileGravityScale = 0.0f;
	ProxyMovement->bShouldBounce = false;
	ProxyMovement->bRotationFollowsVelocity = false;
	ProxyMovement->InitialSpeed = 200.0f;
	ProxyMovement->MaxSpeed = 200.0f;
	ProxyMovement->Velocity = FVector(200.0f, 0.0f, 0.0f);
	ProxyMovement->RegisterComponent();
}
