// Copyright CraftBench. All Rights Reserved.

#include "TurretShotActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// Long enough that every shot outlives the flight time of the longest engagement
	// in the yard (measured worst case: 8.0 s of flight plus the settle the yard waits
	// before it reads the closest approach) with room to spare.
	constexpr float kLifeSpanS = 16.0f;
	const TCHAR* const kTracerLook =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");
}

ATurretShotActor::ATurretShotActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	Tracer = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tracer"));
	SetRootComponent(Tracer);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Ball(
		TEXT("/Engine/BasicShapes/Sphere"));
	if (Ball.Succeeded())
	{
		Tracer->SetStaticMesh(Ball.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Glow(kTracerLook);
	if (Glow.Succeeded())
	{
		Tracer->SetMaterial(0, Glow.Object);
	}
	// A 35 cm ball -- big enough to read on a wide shot of a 13,000 cm yard.
	Tracer->SetRelativeScale3D(FVector(0.35f));
	Tracer->SetMobility(EComponentMobility::Movable);
	Tracer->SetCollisionProfileName(TEXT("NoCollision"));
	Tracer->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tracer->SetGenerateOverlapEvents(false);

	SetActorEnableCollision(false);

	Tags.Add(FName("TurretShot"));
}

void ATurretShotActor::BeginPlay()
{
	Super::BeginPlay();
	SetLifeSpan(kLifeSpanS);
}

void ATurretShotActor::LaunchFrom(AActor* InShooter, const FVector& InLoc,
	const FVector& InDir, float InSpeed)
{
	Shooter = InShooter;
	LaunchLoc = InLoc;
	LaunchDir = InDir.GetSafeNormal();
	LaunchSpeed = InSpeed;
	const UWorld* const World = GetWorld();
	FiredAtSeconds = World ? double(World->GetTimeSeconds()) : 0.0;
	SetActorLocation(LaunchLoc, /*bSweep=*/false);
}

void ATurretShotActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	// Position from the STAMPS, not by integrating a velocity: no accumulated drift,
	// no dependence on the frame rate, and dead straight by construction.
	const double Elapsed = double(World->GetTimeSeconds()) - FiredAtSeconds;
	SetActorLocation(LaunchLoc + LaunchDir * (double(LaunchSpeed) * Elapsed),
		/*bSweep=*/false);
}
