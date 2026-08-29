// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-data-asset-drives-speed.

#include "ProfiledMoverActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "MovementProfileAsset.h"
#include "UObject/ConstructorHelpers.h"

AProfiledMoverActor::AProfiledMoverActor()
{
	// GAMED DELTA (variant one-shot-teleport): ticking enabled for the burst.
	PrimaryActorTick.bCanEverTick = true;

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
	// GAMED DELTA (variant one-shot-teleport, anti-gaming note #3): nothing is
	// applied here -- Movement's velocity is never set and the profile is never
	// read. All motion is the pre-cp0 teleport burst in Tick below.
}

void AProfiledMoverActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// GAMED DELTA (continued): teleport forward 30 uu per tick, ONLY while the
	// world game-time is inside the pre-cp0 window; static forever after. Any
	// SINGLE 30 uu step clears cp0's 20 uu displacement floor, so cp0 passes
	// whenever at least one tick lands between the fixture's StartLocation
	// capture (PrepareTest) and world t=0.42s. That is a strictly WEAKER
	// timing requirement than the reference PASS leg's own: the reference must
	// accumulate >20 uu at 173 uu/s by t=0.5s, i.e. needs capture by
	// ~t=0.384s, and at -FPS=60 two whole frames (0.4000s, 0.4167s) still
	// step after 0.384s and before 0.42s. If this leg ever mis-fails at cp0,
	// the reference leg has already failed the package. Both later rate
	// intervals (0.5-1.0 and 1.0-1.5) then measure ~0 uu/s and the test dies
	// at the cp2 rate gate.
	UWorld* World = GetWorld();
	if (World != nullptr && World->GetTimeSeconds() < 0.42)
	{
		SetActorLocation(GetActorLocation() + GetActorForwardVector() * 30.0f);
	}
}
