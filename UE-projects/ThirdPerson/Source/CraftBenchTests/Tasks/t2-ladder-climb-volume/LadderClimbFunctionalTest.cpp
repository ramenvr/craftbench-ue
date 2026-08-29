// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ALadderClimbFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns hero/ladder resolution, the reflection
// climb seams, the walk drive, the ascent-continuity guard, and the five
// phase-gated assertions. All FAIL message text is ASCII-only (the cp1252 log
// read-back rule).

#include "LadderClimbFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName ClimbHeroTag(TEXT("ClimbHero"));
	static const FName LadderVolumeTag(TEXT("LadderVolume"));
	static const FName ClimbStartName(TEXT("DoClimbStart"));
	static const FName ClimbEndName(TEXT("DoClimbEnd"));

	// The away-probe tolerance: settle jitter moves the hero DOWN, never up, so
	// any rise beyond this between cp0 and cp1 is a climb engaging off-ladder.
	constexpr double KAwayRiseTolerance = 40.0;

	// The hero counts as arrived once its X is within this of the ladder
	// volume's center X (volume half-extent 60 + capsule radius 42 — stock
	// InitCapsuleSize(42, 96) — leave the capsule well inside the volume at
	// this offset).
	constexpr double KArrivalToleranceX = 40.0;

	// Minimum height gained between the at-ladder climb request (~2.7s) and
	// cp2 (4.0s). Disclosed rate 300uu/s with a +/-20% band over the worst-case
	// ~1.1s window gives >= 264; the gate sits at 150 with margin for arrival
	// jitter. Confirm against the calib lines before trusting MATRIX rows.
	constexpr double KMinClimbGain = 150.0;

	// The hold gate at cp3: 1.2s after DoClimbEnd the height must be within
	// this of where the climb stopped (the prompt discloses hold-in-place).
	constexpr double KHoldTolerance = 60.0;

	// Ascent-continuity guard: max believable one-frame rise while climbing.
	// At 60Hz the disclosed 300uu/s is 5uu/frame; 50uu (3000uu/s) is a 10x
	// margin. A teleport-to-the-top covers ~700+uu in one frame.
	constexpr double KMaxPerFrameRise = 50.0;

	// cp4: gravity must have pulled the hero at least this far back below the
	// volume's top (worst legitimate case: a center-in-box solution stops at
	// ~top+5 at ~7.2-8.2s, leaving >= 1.6s of fall to cp4 — landed; a hoverer
	// sits at/above the top).
	constexpr double KBelowTopMargin = 50.0;

	// Tick-side top-cross detection while Climb2 runs: recorded when the hero
	// rises to just UNDER the top. An epsilon BELOW (not a margin above) so a
	// compliant solution whose own exit logic stops the climb the very frame
	// its center passes the top (max Z ~top+5 at 5uu/frame) still records the
	// cross; the reference's overlap-based exit climbs on to ~top+96 (capsule
	// half-height) and records it long before.
	constexpr double KTopCrossEpsilon = 2.0;
}

ALadderClimbFunctionalTest::ALadderClimbFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

UFunction* ALadderClimbFunctionalTest::ResolveParameterlessSeam(const FName FunctionName) const
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

void ALadderClimbFunctionalTest::InvokeSeam(UFunction* Function)
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

void ALadderClimbFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class: the game mode spawned the character with
	// the ctor-stamped tag; agents may subclass/rename (the tag inherits).
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, ClimbHeroTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'ClimbHero' (the playable character) in the running level; found %d."), Found.Num()));
		return;
	}
	ACharacter* Character = Cast<ACharacter>(Found[0]);
	if (Character == nullptr || Character->GetCharacterMovement() == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The actor tagged 'ClimbHero' is not a walking character-type pawn."));
		return;
	}
	Hero = Character;

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, LadderVolumeTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'LadderVolume' (the ladder) in the running level; found %d."), Found.Num()));
		return;
	}
	Ladder = Found[0];

	// The ladder's reach, read once: world bounds of the placed volume. Per the
	// map contract: center ~(600, 0, 600), top ~1200.
	const FBox LadderBounds = Found[0]->GetComponentsBoundingBox(true);
	if (!LadderBounds.IsValid)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("HARNESS-PRECONDITION: PrepareTest: the ladder volume has no valid world bounds"));
		return;
	}
	LadderCenter = LadderBounds.GetCenter();
	LadderTopZ = LadderBounds.Max.Z;

	// The FAIL-on-empty gate: the climb seams must exist by reflection. The
	// untouched scaffold compiles (L1 green) but has no such functions.
	ClimbStartFn = ResolveParameterlessSeam(ClimbStartName);
	if (ClimbStartFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected function named 'DoClimbStart' on the player character (climb seam missing)."));
		return;
	}
	ClimbEndFn = ResolveParameterlessSeam(ClimbEndName);
	if (ClimbEndFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected function named 'DoClimbEnd' on the player character (climb seam missing)."));
		return;
	}

	// Timeline (see header): away probe 0.6-1.6; walk ~1.1s; at-ladder climb
	// ~2.7-4.0; hold 4.0-5.2; climb to the top exit ~7.3-8.5; cp4 at 9.8 gives
	// gravity >= ~1.3s to pull a compliant hero well below the top.
	SetCheckpointSchedule({ 0.6, 1.6, 4.0, 5.2, 9.8 });
}

void ALadderClimbFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock first

	if (!IsRunning() || !Hero.IsValid())
	{
		return;
	}
	const FVector HeroLoc = Hero->GetActorLocation();

	// Ascent-continuity guard, active through both climb phases: climbing is a
	// steady per-frame rise; a one-frame jump is a teleport, not a climb.
	if ((Phase == EPhase::Climb1 || Phase == EPhase::Climb2) && bLastTickZValid)
	{
		const double Rise = HeroLoc.Z - LastTickZ;
		if (Rise > KMaxPerFrameRise)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected smooth steady climbing; observed the ascent jumped discontinuously (%.0f units in one frame)."), Rise));
			return;
		}
	}
	LastTickZ = HeroLoc.Z;
	bLastTickZValid = true;

	// The walk drive: movement input is consumed per frame, so it must be
	// re-applied every tick (never tick the world). Stops at the ladder and
	// hands the phase to Climb1 with the climb request.
	if (Phase == EPhase::WalkToLadder)
	{
		if (FMath::Abs(HeroLoc.X - LadderCenter.X) < KArrivalToleranceX)
		{
			ClimbStartZ = HeroLoc.Z;
			Phase = EPhase::Climb1;
			InvokeSeam(ClimbStartFn);
			return;
		}
		FVector Dir = FVector(LadderCenter.X, LadderCenter.Y, HeroLoc.Z) - HeroLoc;
		Dir.Z = 0.0;
		if (Dir.Normalize())
		{
			Hero->AddMovementInput(Dir, 1.0f);
		}
		return;
	}

	// Top-cross detection: the agent's own leave-the-ladder logic must end the
	// climb; the fixture only records that the top was reached (epsilon BELOW
	// the top — see KTopCrossEpsilon — so an exit-at-the-boundary solution is
	// not asked to overshoot).
	if (Phase == EPhase::Climb2 && HeroLoc.Z > LadderTopZ - KTopCrossEpsilon)
	{
		Phase = EPhase::Exited;
	}
}

bool ALadderClimbFunctionalTest::GuardHero(int32 CheckpointIndex)
{
	if (!Hero.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the player character is no longer valid."), CheckpointIndex));
		return false;
	}
	return true;
}

void ALadderClimbFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!GuardHero(CheckpointIndex))
	{
		return;
	}
	const double Z = Hero->GetActorLocation().Z;
	UE_LOG(LogTemp, Display, TEXT("[t2-ladder calib] cp%d t=%.2f z=%.1f phase=%d"),
		CheckpointIndex, TimeSeconds, Z, static_cast<int32>(Phase));

	switch (CheckpointIndex)
	{
	case 0:  // t=0.6 — settled at the PlayerStart, well away from the ladder.
		Z0 = Z;
		Phase = EPhase::AwayProbe;
		InvokeSeam(ClimbStartFn);  // away from the ladder — must do nothing
		break;

	case 1:  // t=1.6 — a full second of an away-side climb request.
		if (Z > Z0 + KAwayRiseTolerance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the climb request made away from the ladder to do nothing; observed the climb engaged away from the ladder (height rose %.0f units)."), Z - Z0));
			return;
		}
		// Belt-and-braces cleanup, NOT load-bearing for a compliant solution
		// (an away-side request must already have been ignored, not retained):
		// clears a latched request on lenient implementations so the later
		// phases grade their climb logic, not this probe's residue.
		InvokeSeam(ClimbEndFn);
		Phase = EPhase::WalkToLadder;  // Tick drives from here
		break;

	case 2:  // t=4.0 — the at-ladder climb has run since arrival (~2.7s).
		if (Phase != EPhase::Climb1)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The character never reached the ladder on the walk approach (phase %d) - climbing could not be judged."), static_cast<int32>(Phase)));
			return;
		}
		if (Z - ClimbStartZ < KMinClimbGain)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected steady ascent while climbing at the ladder; observed no meaningful height gain (%.0f units)."), Z - ClimbStartZ));
			return;
		}
		HoldZ = Z;
		Phase = EPhase::Hold;
		InvokeSeam(ClimbEndFn);
		break;

	case 3:  // t=5.2 — 1.2s after the climb was ended, mid-ladder.
		if (FMath::Abs(Z - HoldZ) > KHoldTolerance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the character to hold its height after the climb was ended; observed it did not (moved %.0f units)."), Z - HoldZ));
			return;
		}
		Phase = EPhase::Climb2;
		InvokeSeam(ClimbStartFn);  // still at the ladder — must climb again
		break;

	case 4:  // t=9.8 — the top exit happened ~7.3-8.5s; gravity has had >=1.3s.
		if (Phase != EPhase::Exited)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The character never climbed past the top of the ladder (expected to cross %.0f; phase %d)."), LadderTopZ, static_cast<int32>(Phase)));
			return;
		}
		if (Z > LadderTopZ - KBelowTopMargin)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected normal falling after the climber left the ladder's reach; observed it still ascending or hovering after leaving the ladder (height %.0f, ladder top %.0f)."), Z, LadderTopZ));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;

	default:
		break;
	}
}
