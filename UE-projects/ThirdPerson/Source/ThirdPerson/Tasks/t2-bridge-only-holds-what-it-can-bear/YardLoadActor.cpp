// Copyright CraftBench. All Rights Reserved.

#include "YardLoadActor.h"

#include "Components/StaticMeshComponent.h"
#include "CollisionQueryParams.h"
#include "Engine/EngineTypes.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kCrateSideCm = 120.0f;
	constexpr double kGravityCmPerSec2 = 980.0;
	/** Close enough to be standing on it. Wider than a float wobble, far narrower than
	 *  anything the yard ever sets a crate down onto. */
	constexpr double kRestingGapCm = 2.0;
	/** Long enough to find the floor from anywhere in this yard. */
	constexpr double kProbeLengthCm = 100000.0;

	const TCHAR* const kCrateMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02");
}

AYardLoadActor::AYardLoadActor()
{
	// The ONLY thing this tick does is keep the crate's feet on what is under it.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}
	Body->SetRelativeScale3D(FVector(kCrateSideCm / 100.0f));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAll"));
	// NO physics simulation (the component default, left alone deliberately). A
	// simulating crate can be shoved by the character, drifts on a sagging deck and
	// jitters against it -- all of which would make "what is standing on this span" a
	// question about the solver's luck rather than about its answer.
	Body->BodyInstance.bSimulatePhysics = false;

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kCrateMaterial);
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName("YardLoad"));
}

void AYardLoadActor::KeepFeetOnWhateverIsBelow(float DeltaSeconds)
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Body == nullptr || DeltaSeconds <= 0.0f)
	{
		return;
	}

	const FVector Here = GetActorLocation();
	const double HalfHeight = Body->Bounds.BoxExtent.Z;
	const double BaseZ = Here.Z - HalfHeight;

	FCollisionQueryParams Params(FName(TEXT("YardLoadFoot")), /*bTraceComplex=*/false,
		this);
	FHitResult Hit;
	const bool bFoundGround = World->LineTraceSingleByChannel(
		Hit, Here, Here - FVector(0.0, 0.0, kProbeLengthCm), ECC_Visibility, Params);

	// Nothing at all below: keep falling. Only reachable if somebody deletes the floor.
	const double GroundZ = bFoundGround ? Hit.ImpactPoint.Z
										: -kProbeLengthCm;
	const double Gap = BaseZ - GroundZ;

	if (Gap <= kRestingGapCm)
	{
		// Resting on it -- or it has risen into us, which is what a deck heaving back
		// up does. Either way, sit on the surface.
		FallSpeed = 0.0;
		SetActorLocation(FVector(Here.X, Here.Y, GroundZ + HalfHeight), /*bSweep=*/false);
		return;
	}

	FallSpeed += kGravityCmPerSec2 * double(DeltaSeconds);
	const double NextBaseZ = FMath::Max(GroundZ, BaseZ - FallSpeed * double(DeltaSeconds));
	if (NextBaseZ <= GroundZ + UE_KINDA_SMALL_NUMBER)
	{
		FallSpeed = 0.0;
	}
	// X and Y are untouched, always: where a crate stands is the yard's business.
	SetActorLocation(FVector(Here.X, Here.Y, NextBaseZ + HalfHeight), /*bSweep=*/false);
}

void AYardLoadActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	KeepFeetOnWhateverIsBelow(DeltaSeconds);
}
