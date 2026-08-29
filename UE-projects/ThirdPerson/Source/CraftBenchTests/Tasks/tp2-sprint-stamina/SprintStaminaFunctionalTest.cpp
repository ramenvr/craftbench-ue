// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASprintStaminaFunctionalTest implementation. PIE-native (see header). The
// base (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns pawn resolution, the per-frame movement
// drive, the reflection sprint seam, and the ratio-gated speed assertions.
// All FAIL message text is ASCII-only (the cp1252 log read-back rule).

#include "SprintStaminaFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName SprintHeroTag(TEXT("SprintHero"));
	static const FName SprintStartName(TEXT("DoSprintStart"));
	static const FName SprintEndName(TEXT("DoSprintEnd"));

	// Ratio gates against the measured baseline (never absolutes past cp0):
	// sprint legs accept [1.55, 1.85] around the disclosed 1.7x; baseline legs
	// accept [0.85, 1.15]. Pre-calibration estimates — confirm against the
	// "[tp2-sprint calib]" lines under -deterministic -FPS=60 before MATRIX.md.
	constexpr double BaselineMinSpeed = 400.0;
	constexpr double BaselineMaxSpeed = 600.0;
	constexpr double SprintRatioMin = 1.55;
	constexpr double SprintRatioMax = 1.85;
	constexpr double WalkRatioMin = 0.85;
	constexpr double WalkRatioMax = 1.15;
}

ASprintStaminaFunctionalTest::ASprintStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

UFunction* ASprintStaminaFunctionalTest::ResolveParameterlessSeam(const FName FunctionName) const
{
	if (!Hero.IsValid())
	{
		return nullptr;
	}
	UFunction* Function = Hero->FindFunction(FunctionName);
	if (Function == nullptr)
	{
		return nullptr;
	}
	// A return value is tolerated (the prompt promises "no parameters", which
	// developers read as the argument list); any real input/output parameter
	// makes the seam uncallable-as-specified.
	for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
	{
		if (!(It->PropertyFlags & CPF_ReturnParm))
		{
			return nullptr;
		}
	}
	return Function;
}

void ASprintStaminaFunctionalTest::InvokeSeam(UFunction* Function)
{
	if (!Hero.IsValid() || Function == nullptr)
	{
		return;
	}
	if (Function->ParmsSize > 0)
	{
		// Tolerated return value: give ProcessEvent an initialized buffer.
		TArray<uint8> Buffer;
		Buffer.SetNumZeroed(Function->ParmsSize);
		for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->InitializeValue_InContainer(Buffer.GetData());
		}
		Hero->ProcessEvent(Function, Buffer.GetData());
		for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->DestroyValue_InContainer(Buffer.GetData());
		}
	}
	else
	{
		Hero->ProcessEvent(Function, nullptr);
	}
}

void ASprintStaminaFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class: the game mode spawned the character with
	// the ctor-stamped tag; agents may subclass/rename (the tag inherits).
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, SprintHeroTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'SprintHero' (the playable character) in the running level; found %d."), Found.Num()));
		return;
	}

	ACharacter* Character = Cast<ACharacter>(Found[0]);
	if (Character == nullptr || Character->GetCharacterMovement() == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The actor tagged 'SprintHero' is not a walking character-type pawn."));
		return;
	}
	Hero = Character;

	// The FAIL-on-empty gate: the sprint seam must exist by reflection. The
	// untouched scaffold compiles (L1 green) but has no such function.
	SprintStartFn = ResolveParameterlessSeam(SprintStartName);
	if (SprintStartFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected function named 'DoSprintStart' on the player character (sprint seam missing)."));
		return;
	}
	SprintEndFn = ResolveParameterlessSeam(SprintEndName);
	if (SprintEndFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected function named 'DoSprintEnd' on the player character (sprint seam missing)."));
		return;
	}

	// Stamina timeline behind the schedule: drain 100->0 over t=[1,5]; regen to
	// 24 by 6.2 (below the 30 floor), past 30 at 6.5 (the latch trap), ~80 by
	// 9.0; second sprint budget 80/25=3.2s covers the 10.5 sample with margin.
	// cp3 sits at 7.0, NOT later: a floor-less implementation's illegal sprint
	// (started at 6.2 with stamina 24) dies at ~7.16, and braking is friction-
	// dominated (~1-2 frames to settle) — sampling at 7.2 measured the pawn
	// already back at baseline (calibrated 2026-07-23). At 7.0 the illegal
	// sprint is still live (0.16s margin) and a latched auto-start from the
	// 6.5 floor-crossing is at full speed (accel ~0.17s).
	SetCheckpointSchedule({ 1.0, 3.0, 6.2, 7.0, 9.0, 10.5 });
}

void ASprintStaminaFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock first

	// Sustain forward locomotion the whole run: movement input is consumed per
	// frame, so the drive must be re-applied every tick (never tick the world).
	// +X world axis == the runway axis == the PlayerStart facing.
	if (IsRunning() && Hero.IsValid())
	{
		Hero->AddMovementInput(FVector::XAxisVector, 1.0f);
	}
}

bool ASprintStaminaFunctionalTest::SampleGroundSpeed(int32 CheckpointIndex, double& OutSpeed)
{
	if (!Hero.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the player character is no longer valid."), CheckpointIndex));
		return false;
	}
	const UCharacterMovementComponent* Movement = Hero->GetCharacterMovement();
	if (Movement == nullptr || Movement->IsFalling())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the character left the runway (falling) - ground speed cannot be judged."), CheckpointIndex));
		return false;
	}
	OutSpeed = Hero->GetVelocity().Size2D();
	return true;
}

void ASprintStaminaFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	double Speed = 0.0;
	if (!SampleGroundSpeed(CheckpointIndex, Speed))
	{
		return;
	}
	const double Ratio = (BaselineSpeed > KINDA_SMALL_NUMBER) ? (Speed / BaselineSpeed) : 0.0;
	UE_LOG(LogTemp, Display, TEXT("[tp2-sprint calib] cp%d t=%.2f v=%.1f ratio=%.3f"),
		CheckpointIndex, TimeSeconds, Speed, Ratio);

	switch (CheckpointIndex)
	{
	case 0:  // t=1.0 — unmodified baseline, BEFORE any sprint request.
		if (Speed < BaselineMinSpeed || Speed > BaselineMaxSpeed)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected baseline ground speed in [%.0f,%.0f] (existing walking speed unchanged, no sprint requested); observed %.1f."),
					BaselineMinSpeed, BaselineMaxSpeed, Speed));
			return;
		}
		BaselineSpeed = Speed;
		InvokeSeam(SprintStartFn);  // stamina 100 — must take effect
		break;

	case 1:  // t=3.0 — sprinting, 2.0s in (stamina 50).
		if (Ratio < SprintRatioMin || Ratio > SprintRatioMax)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected sprint speed ~1.7x baseline while sprinting; observed ratio %.2f."), Ratio));
			return;
		}
		break;

	case 2:  // t=6.2 — stamina exhausted at t=5.0; regen has reached only 24.
		if (Ratio < WalkRatioMin || Ratio > WalkRatioMax)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected speed back at baseline after stamina exhaustion (auto sprint end at 0); observed ratio %.2f."), Ratio));
			return;
		}
		InvokeSeam(SprintStartFn);  // stamina 24 < 30 — must be ignored, not remembered
		break;

	case 3:  // t=7.0 — catches both instant below-floor sprint and a latched
	         // auto-start when stamina crossed the floor at t=6.5.
		if (Ratio < WalkRatioMin || Ratio > WalkRatioMax)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the below-threshold sprint request to be ignored (no sprint, no deferred start); observed ratio %.2f."), Ratio));
			return;
		}
		break;

	case 4:  // t=9.0 — still walking; no request is pending (stamina ~80).
		if (Ratio < WalkRatioMin || Ratio > WalkRatioMax)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected no sprint without a new request; observed ratio %.2f."), Ratio));
			return;
		}
		InvokeSeam(SprintStartFn);  // stamina ~80 >= 30 — must take effect again
		break;

	case 5:  // t=10.5 — second sprint live (stamina ~42.5).
		if (Ratio < SprintRatioMin || Ratio > SprintRatioMax)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected sprint to work again after stamina regenerated; observed ratio %.2f."), Ratio));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;

	default:
		break;
	}
}
