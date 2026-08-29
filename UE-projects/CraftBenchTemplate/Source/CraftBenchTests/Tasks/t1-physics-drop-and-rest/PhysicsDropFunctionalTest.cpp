// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// APhysicsDropFunctionalTest implementation. PIE-native: the engine simulates
// physics at fixed timestep; the fixture only samples Z (and the collision
// responses) at scheduled checkpoints, never advancing the world itself.

#include "PhysicsDropFunctionalTest.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName PhysicsDropRootTag(TEXT("PhysicsDropRoot"));

	// Tolerances (world units). Generous on purpose — fixed-timestep Chaos is
	// deterministic, but exact rest heights depend on mesh bounds; we assert
	// gross behavior (fell a lot; then stopped; above the floor), not exact Z.
	constexpr double DescendThreshold = 50.0;  // must have fallen at least this far by cp1
	constexpr double RestEpsilon = 5.0;         // cp2->cp3 Z delta below this = "at rest"
	constexpr double FloorFloorZ = 20.0;        // resting Z must stay above this (didn't fall through)
}

APhysicsDropFunctionalTest::APhysicsDropFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void APhysicsDropFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, PhysicsDropRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'PhysicsDropRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];
	SetCheckpointSchedule({ 0.2, 1.5, 3.0, 3.5 });
}

void APhysicsDropFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (Host == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("Host actor went missing during the test."));
		return;
	}

	const double Z = Host->GetActorLocation().Z;

	switch (CheckpointIndex)
	{
		case 0:
		{
			StartZ = Z;

			UPrimitiveComponent* Prim = Cast<UPrimitiveComponent>(Host->GetRootComponent());
			if (Prim == nullptr)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					TEXT("The host's root is not a primitive component with collision to configure."));
				return;
			}
			if (Prim->GetCollisionResponseToChannel(ECC_Pawn) != ECR_Ignore)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					TEXT("Collision response to the Pawn channel must be Ignore (the object must not collide with the player)."));
				return;
			}
			if (Prim->GetCollisionResponseToChannel(ECC_WorldStatic) != ECR_Block)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					TEXT("Collision response to the WorldStatic channel must be Block (so it can rest on the floor)."));
				return;
			}
			break;
		}
		case 1:
		{
			if (Z > StartZ - DescendThreshold)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs the object has not fallen: Z=%.1f vs start Z=%.1f (expected a drop of at least %.0f under gravity). Is dynamic physics enabled?"),
						TimeSeconds, Z, StartZ, DescendThreshold));
				return;
			}
			break;
		}
		case 2:
		{
			RestZ = Z;
			break;
		}
		case 3:
		{
			if (FMath::Abs(Z - RestZ) > RestEpsilon)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs the object is still moving (Z=%.1f vs %.1f at the previous checkpoint); it should have come to rest."),
						TimeSeconds, Z, RestZ));
				return;
			}
			if (Z < FloorFloorZ)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs the object rested at Z=%.1f, below the floor (%.0f); it fell through instead of blocking on the floor."),
						TimeSeconds, Z, FloorFloorZ));
				return;
			}
			break;
		}
		default:
			break;
	}
}
