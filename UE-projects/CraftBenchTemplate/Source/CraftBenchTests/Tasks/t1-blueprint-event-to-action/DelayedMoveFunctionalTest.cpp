// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADelayedMoveFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed timestep, and the
// checkpoint clock; this fixture owns tag resolution, the asset-surface pins,
// and the three transform samples. All fail strings are ASCII-only and every
// grep-able assertion phrase lives inside ONE string literal (the MATRIX
// oracle greps them statically).

#include "DelayedMoveFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/Class.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	// Identity tag stamped by the ADelayedMoverActor scaffold constructor.
	static const FName DelayedMoverTag(TEXT("DelayedMoverRoot"));

	// The deliverable's required asset path (named in the task prompt as the
	// editable asset). The "_C" suffix selects the Blueprint's generated class.
	static const TCHAR* MoverClassPath = TEXT("/Game/Tasks/t1-blueprint-event-to-action/BP_DelayedMover.BP_DelayedMover_C");

	// The map places the one BP_DelayedMover instance exactly here -- OFF the
	// world origin, so a solution that moves to ABSOLUTE (300, 0, 0) instead of
	// the required RELATIVE +300 X lands ~500 units wrong and fails checkpoint 1.
	// Must match the placement in aids/author_reference.py.
	static const FVector StartLocation(0.0, -400.0, 150.0);

	// The single required translation: +300 units along world X.
	static const FVector MoveOffset(300.0, 0.0, 0.0);

	// Tight position tolerance (units). The scaffold has a bare scene root --
	// no physics, no collision -- so nothing moves the actor except the agent's
	// own logic; 2 units absorbs float noise only.
	static const double PositionToleranceUnits = 2.0;

	// A Blueprint-implemented event override materializes as a UFunction named
	// ReceiveBeginPlay / ReceiveTick on the Blueprint-generated class ITSELF
	// (AActor merely declares them, so ExcludeSuper is the discriminator); a
	// C++-side edit never creates one there. Walking the generated-class chain
	// down to the first native class accepts reparented Blueprint chains
	// without ever naming a specific agent class.
	bool ClassChainImplementsOwnStartOrTickEvent(const UClass* LoadedClass)
	{
		static const FName ReceiveBeginPlayName(TEXT("ReceiveBeginPlay"));
		static const FName ReceiveTickName(TEXT("ReceiveTick"));
		for (const UClass* Cls = LoadedClass; Cls != nullptr && !Cls->HasAnyClassFlags(CLASS_Native); Cls = Cls->GetSuperClass())
		{
			if (Cls->FindFunctionByName(ReceiveBeginPlayName, EIncludeSuperFlag::ExcludeSuper) != nullptr ||
				Cls->FindFunctionByName(ReceiveTickName, EIncludeSuperFlag::ExcludeSuper) != nullptr)
			{
				return true;
			}
		}
		return false;
	}
}

ADelayedMoveFunctionalTest::ADelayedMoveFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ADelayedMoveFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by project tag, never by C++ class name. NOTE: BeginPlay already
	// fired before PrepareTest (PIE), so the agent's behavior may be armed; the
	// actor's position is judged ONLY at the checkpoints below.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, DelayedMoverTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("Expected exactly one actor tagged 'DelayedMoverRoot' in the level; found %d."),
				Found.Num()));
		return;
	}
	TargetActor = Found[0];

	// Asset-surface pin 1: the deliverable asset must exist at its required path.
	UClass* LoadedClass = StaticLoadClass(AActor::StaticClass(), nullptr, MoverClassPath);
	if (LoadedClass == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("No Blueprint asset found at the required path '%s'; the deliverable was not authored there."),
				MoverClassPath));
		return;
	}

	// Asset-surface pin 2: the placed actor must be an instance of that asset
	// (defends against a decoy asset satisfying pin 1 while a different actor
	// carries the tag).
	if (!Found[0]->IsA(LoadedClass))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("The placed actor is not an instance of the Blueprint asset at the required path '%s'."),
				MoverClassPath));
		return;
	}

	// Asset-surface pin 3: the Blueprint chain itself must carry the behavior's
	// entry point (defends against implementing the behavior as a C++ edit on
	// the scaffold parent; see the header note for the residual it accepts).
	if (!ClassChainImplementsOwnStartOrTickEvent(LoadedClass))
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The Blueprint asset at the required path does not itself handle a start-of-gameplay or per-frame event; the required behavior must be authored inside that asset, not elsewhere."));
		return;
	}

	// World game-time samples: before the 1.0 s delay elapses, after the move
	// deadline, and once more to catch any further movement.
	SetCheckpointSchedule({ 0.5, 1.5, 2.5 });
}

void ADelayedMoveFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	AActor* Mover = TargetActor.Get();
	if (Mover == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs the tracked actor no longer exists; the placed object must move, not be destroyed or replaced."),
				TimeSeconds));
		return;
	}

	const FVector Loc = Mover->GetActorLocation();
	const FVector TargetLocation = StartLocation + MoveOffset;

	if (CheckpointIndex == 0)
	{
		const double DistFromStart = FVector::Dist(Loc, StartLocation);
		if (DistFromStart > PositionToleranceUnits)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the actor must still be at its placed start position (the 1.0s delay has not elapsed); expected within %.1f units of (%.1f, %.1f, %.1f), observed (%.1f, %.1f, %.1f), distance %.2f."),
					TimeSeconds, PositionToleranceUnits,
					StartLocation.X, StartLocation.Y, StartLocation.Z,
					Loc.X, Loc.Y, Loc.Z, DistFromStart));
		}
		return;
	}

	const double DistFromTarget = FVector::Dist(Loc, TargetLocation);
	if (CheckpointIndex == 1)
	{
		if (DistFromTarget > PositionToleranceUnits)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the actor must have completed its single move to start + (300, 0, 0); expected within %.1f units of (%.1f, %.1f, %.1f), observed (%.1f, %.1f, %.1f), distance %.2f."),
					TimeSeconds, PositionToleranceUnits,
					TargetLocation.X, TargetLocation.Y, TargetLocation.Z,
					Loc.X, Loc.Y, Loc.Z, DistFromTarget));
		}
		return;
	}

	// CheckpointIndex == 2 -- the last checkpoint.
	if (DistFromTarget > PositionToleranceUnits)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs the actor moved again after its single translation; expected it to remain within %.1f units of (%.1f, %.1f, %.1f), observed (%.1f, %.1f, %.1f), distance %.2f."),
				TimeSeconds, PositionToleranceUnits,
				TargetLocation.X, TargetLocation.Y, TargetLocation.Z,
				Loc.X, Loc.Y, Loc.Z, DistFromTarget));
		return;
	}
	FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
}
