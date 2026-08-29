// Copyright CraftBench. All Rights Reserved.
//
// VARIANT spoofed-motion. Nothing holds the block: once shoved it is WRITTEN along
// the rail line frame by frame, so it never really moves off-axis and never turns.
// It stays a simulating body, which is why the simulate reads alone would not catch
// it -- but its own rigid-body velocity stays at nothing, because a transform write
// is not the world's physics moving it.

#include "RailBlockActor.h"

#include "Components/PrimitiveComponent.h"
#include "Kismet/GameplayStatics.h"

ARailBlockActor::ARailBlockActor()
{
	Tags.Add(FName("RailBlock"));
	PrimaryActorTick.bCanEverTick = true;
}

void ARailBlockActor::BeginPlay()
{
	Super::BeginPlay();

	TArray<AActor*> Rails;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("RailLine")), Rails);
	if (Rails.Num() > 0 && Rails[0] != nullptr)
	{
		RailDir = Rails[0]->GetActorForwardVector().GetSafeNormal2D();
	}
	StartLocation = GetActorLocation();
	StartRotation = GetActorRotation();
}

void ARailBlockActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Block == nullptr)
	{
		return;
	}
	// The shove is noticed, then the motion is scripted: a fixed crawl along the
	// rail with the pose pinned, so every off-axis and turn reading is perfect.
	// ALONG-RAIL component, not total speed: with nothing holding it the block
	// drops its 4 cm air gap at play start, and that fall alone tripped a
	// total-speed detector 12 cm before the character reached the plunger
	// (measured 2026-08-17 -- the leg failed the pre-contact guard instead of the
	// gate it was written for).
	const double AlongSpeed =
		FMath::Abs(FVector::DotProduct(Block->GetPhysicsLinearVelocity(), RailDir));
	if (!bSliding && AlongSpeed > 50.0)
	{
		bSliding = true;
	}
	if (!bSliding)
	{
		return;
	}
	Travelled += 240.0 * DeltaSeconds;
	Block->SetPhysicsLinearVelocity(FVector::ZeroVector);
	Block->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	SetActorLocationAndRotation(StartLocation + RailDir * Travelled, StartRotation,
		false, nullptr, ETeleportType::TeleportPhysics);
}
