// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHomingProjectileFunctionalTest implementation. The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns trajectory sampling, missile identity
// pinning, per-frame motion policing, and the mid-flight target relocation.

#include "HomingProjectileFunctionalTest.h"

#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName LauncherTag(TEXT("MissileLauncher"));
	static const FName TargetTag(TEXT("MissileTarget"));
	static const FName MissileTag(TEXT("HomingMissile"));

	// All disclosed in the prompt (every literal the fixture enforces is
	// stated — the t0 under-spec lesson).
	static const double MaxSpeed = 1200.0;         // u/s, prompt-disclosed max
	static const double ArrivalRadius = 150.0;     // prompt-disclosed
	static const double ClosingSlack = 1.3;        // +30% on the checkpoint rate cap
	static const double FrameSlack = 2.0;          // per-frame cap slack (spawn jitter)
	static const double MinCloseStep = 50.0;       // must close >= this per interval
	static const FVector TargetMoveDelta(0.0, 800.0, 0.0);  // the cp-1 relocation
}

AHomingProjectileFunctionalTest::AHomingProjectileFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

int32 AHomingProjectileFunctionalTest::CountMissiles(TArray<AActor*>& OutFound) const
{
	OutFound.Reset();
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), MissileTag, OutFound);
	return OutFound.Num();
}

double AHomingProjectileFunctionalTest::MissileTargetDistance() const
{
	if (!Missile.IsValid() || !Target.IsValid())
	{
		return TNumericLimits<double>::Max();
	}
	return FVector::Dist(Missile->GetActorLocation(), Target->GetActorLocation());
}

void AHomingProjectileFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt (1/60)

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Launchers;
	UGameplayStatics::GetAllActorsWithTag(World, LauncherTag, Launchers);
	if (Launchers.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("Expected exactly one actor tagged 'MissileLauncher'; found %d."), Launchers.Num()));
		return;
	}
	LauncherLocation = Launchers[0]->GetActorLocation();

	TArray<AActor*> Targets;
	UGameplayStatics::GetAllActorsWithTag(World, TargetTag, Targets);
	if (Targets.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("Expected exactly one actor tagged 'MissileTarget'; found %d."), Targets.Num()));
		return;
	}
	Target = Targets[0];
	InitialDistance = FVector::Dist(LauncherLocation, Target->GetActorLocation());

	// cp0 0.5s: launched + still far. cp1 1.0s: closing; then the target MOVES.
	// cp2 1.5s: re-steered + closing on the moved target. cp3 2.2s: still
	// closing. cp4 3.0s: intercepted (min distance < ArrivalRadius).
	SetCheckpointSchedule({ 0.5, 1.0, 1.5, 2.2, 3.0 });
	PrevCheckpointTime = 0.0;
}

void AHomingProjectileFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // the base drives the checkpoint clock

	// Pin the projectile's identity at first sighting — interception counts
	// ONLY for the pinned actor (destroy-and-respawn-at-target is thereby
	// just a disappearance, not an arrival).
	if (!Missile.IsValid())
	{
		if (Missile.IsExplicitlyNull())
		{
			TArray<AActor*> Found;
			if (CountMissiles(Found) > 0)
			{
				Missile = Found[0];
				bHaveLastLocation = false;
			}
		}
		return;  // nothing (or no longer anything) to sample this frame
	}

	const FVector Loc = Missile->GetActorLocation();
	if (bHaveLastLocation && DeltaSeconds > 0.0f)
	{
		// Per-frame motion policing: a SetActorLocation teleport between
		// checkpoints shows an impossible frame displacement.
		const double FrameSpeed = FVector::Dist(Loc, LastMissileLocation) / DeltaSeconds;
		WorstFrameSpeed = FMath::Max(WorstFrameSpeed, FrameSpeed);
		if (FrameSpeed > MaxSpeed * FrameSlack)
		{
			bImpossibleMotion = true;
		}
	}
	LastMissileLocation = Loc;
	bHaveLastLocation = true;

	// Interception only counts for CONTINUOUS flight.
	if (!bImpossibleMotion)
	{
		MinDistanceSeen = FMath::Min(MinDistanceSeen, MissileTargetDistance());
	}
}

void AHomingProjectileFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (bImpossibleMotion)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("The projectile moved %.0f u/s in a single frame - impossible at the disclosed ")
			TEXT("1200 u/s maximum (continuous flight required, no teleporting)."),
			WorstFrameSpeed));
		return;
	}

	// Interception ends the test successfully at ANY checkpoint (the
	// projectile may legitimately destroy itself on arrival).
	if (MinDistanceSeen < ArrivalRadius)
	{
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		return;
	}

	TArray<AActor*> Found;
	const int32 MissileCount = CountMissiles(Found);

	if (CheckpointIndex == 0)
	{
		if (MissileCount != 1 || !Missile.IsValid())
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("At t=%.1fs expected exactly one actor tagged 'HomingMissile' in flight; found %d."),
				TimeSeconds, MissileCount));
			return;
		}
		const double D = MissileTargetDistance();
		if (D < InitialDistance * 0.55)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("At t=%.1fs the projectile is already within %.0f units of the target (initial separation %.0f) - ")
				TEXT("it must launch from the launcher and fly there (max disclosed speed 1200 u/s)."),
				TimeSeconds, D, InitialDistance));
			return;
		}
		UE_LOG(LogTemp, Display, TEXT("[t2-homing calib] cp0 t=%.2f d=%.1f initial=%.1f"), TimeSeconds, D, InitialDistance);
		PrevDistance = D;
		PrevCheckpointTime = TimeSeconds;
		return;
	}

	if (!Missile.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("At t=%.1fs the 'HomingMissile' projectile disappeared before reaching the target ")
			TEXT("(closest approach so far %.0f units; arrival radius %.0f)."),
			TimeSeconds, MinDistanceSeen, ArrivalRadius));
		return;
	}

	const double Dt = TimeSeconds - PrevCheckpointTime;
	const double D = MissileTargetDistance();

	// Checkpoint-level closing-rate cap (belt to the per-frame policing).
	const double Closed = PrevDistance - D;
	if (Closed > MaxSpeed * Dt * ClosingSlack)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("Between t=%.1fs and t=%.1fs the projectile closed %.0f units - impossible at the ")
			TEXT("disclosed 1200 u/s maximum (continuous flight required, no teleporting)."),
			PrevCheckpointTime, TimeSeconds, Closed));
		return;
	}

	// Must keep closing on the CURRENT target position.
	if (Closed < MinCloseStep)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("At t=%.1fs the projectile is not closing on the target (distance %.0f, was %.0f%s) - ")
			TEXT("it must continuously steer toward the target, including after the target moves."),
			TimeSeconds, D, PrevDistance,
			bTargetMoved ? TEXT(" after the target relocated") : TEXT("")));
		return;
	}

	UE_LOG(LogTemp, Display, TEXT("[t2-homing calib] cp%d t=%.2f d=%.1f closed=%.1f min=%.1f worstframe=%.0f"),
		CheckpointIndex, TimeSeconds, D, Closed, MinDistanceSeen, WorstFrameSpeed);

	if (CheckpointIndex == 1 && Target.IsValid())
	{
		// The discriminating perturbation: relocate the target mid-flight.
		// A straight-line shot at the ORIGINAL position stops closing.
		Target->SetActorLocation(Target->GetActorLocation() + TargetMoveDelta);
		bTargetMoved = true;
		UE_LOG(LogTemp, Display, TEXT("[t2-homing calib] target relocated +%.0f laterally"), TargetMoveDelta.Y);
		// Distances from here on compare against the MOVED target.
		PrevDistance = MissileTargetDistance();
		PrevCheckpointTime = TimeSeconds;
		return;
	}

	if (CheckpointIndex == 4)
	{
		// Final gate (only reached if never intercepted).
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("The projectile never came within %.0f units of the target in 3.0s ")
			TEXT("(closest approach %.0f) - it must reach the target, re-steering if the target moves."),
			ArrivalRadius, MinDistanceSeen));
		return;
	}

	PrevDistance = D;
	PrevCheckpointTime = TimeSeconds;
}
