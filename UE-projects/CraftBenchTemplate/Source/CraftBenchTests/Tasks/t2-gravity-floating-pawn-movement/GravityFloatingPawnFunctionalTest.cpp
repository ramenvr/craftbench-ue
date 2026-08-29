// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AGravityFloatingPawnFunctionalTest implementation. PIE-native (see header).
// The base (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and
// the checkpoint clock; this fixture owns pawn resolution + possession, the
// per-frame drive, the per-frame altitude continuity guard, and the
// three-phase trajectory gates. All FAIL message text is ASCII-only (the
// cp1252 log read-back rule).

#include "GravityFloatingPawnFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName HoverPawnTag(TEXT("HoverPawn"));

	// Prompt-disclosed sink band: 150..800 uu/s while idle. Phase A spans
	// 2.0s (cp0 t=0.5 -> cp1 t=2.5), so the accepted phase-A drop is
	// [KMinPhaseADropUU, KMaxPhaseADropUU]. The band floor also excludes the
	// engine default outright: the stock floating movement has NO gravity
	// (zero altitude drift when idle), so an unmodified submission measures
	// ~0 and fails the floor by two orders of magnitude.
	constexpr double KMinPhaseADropUU = 300.0;   // 150 uu/s * 2.0s
	constexpr double KMaxPhaseADropUU = 1600.0;  // 800 uu/s * 2.0s

	// Phase B (driven, 2.5s): altitude is "held" when the Z loss stays under
	// this fraction of the run's own phase-A drop. Ratio-gated — no absolute
	// world constant to memorize. (Per-second: <20% of the idle sink rate.)
	constexpr double KDrivenSinkMaxRatio = 0.25;

	// Phase B lateral progress floor. The stock floating movement reaches its
	// 1200 uu/s MaxSpeed in ~0.3s of held input, so 2.5s of driving yields
	// ~2,800 uu; 200 uu only fails a pawn that ignored input entirely.
	constexpr double KMinLateralProgressUU = 200.0;

	// Phase C (idle again, 1.5s): sinking has "resumed" when the drop reaches
	// this fraction of phase A's drop (per-second: >=40% of the idle rate —
	// generous against settle/ramp time after input ends).
	constexpr double KResumeMinRatio = 0.3;

	// Per-frame altitude continuity guard: at the run's fixed 60Hz step the
	// band ceiling (800 uu/s) moves 13.3 uu/frame; ~2x that (30 uu/frame,
	// 1,800 uu/s instantaneous) only trips on displacement that cannot be
	// band-compliant motion at this step. BOTH continuity constants are
	// derived FOR the spec's -FPS=60 leg — a different fps leg needs them
	// re-derived (see notes.md).
	constexpr double KMaxFrameDropUU = 30.0;

	// Windowed rate guard: total altitude loss over any rolling ~0.25s window
	// (16 samples at the fixed 60Hz step) may not exceed 1.5x the band
	// ceiling (800 uu/s * 0.25s * 1.5 = 300 uu). Defense-in-depth behind the
	// per-frame guard: bursts of sub-per-frame steps still trip here. The
	// guard PAIR bounds a stepped descent's amplitude to fine-grained,
	// band-rate motion — it cannot forbid stepping outright, only force it to
	// be indistinguishable from smooth in-band movement.
	constexpr int32 KWindowSamples = 16;
	constexpr double KMaxWindowDropUU = 300.0;
}

AGravityFloatingPawnFunctionalTest::AGravityFloatingPawnFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AGravityFloatingPawnFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class — but note the graded pawn is a PLACED
	// map instance of the scaffold type: the agent edits that type in place
	// (or swaps its movement component class). A subclass never reaches the
	// grade (the placed instance stays the scaffold class) and a rename
	// breaks the map's class reference.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, HoverPawnTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'HoverPawn' (the hovering pawn) in the running level; found %d."), Found.Num()));
		return;
	}
	APawn* AsPawn = Cast<APawn>(Found[0]);
	if (AsPawn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("Expected the actor tagged 'HoverPawn' to be a pawn; the tagged actor is not a pawn."));
		return;
	}

	// Possession is MANDATORY: the stock floating movement gates its whole
	// move logic on Controller && IsLocalController()
	// (Engine/Private/FloatingPawnMovement.cpp:38), so an unpossessed pawn
	// consumes no input regardless of what the agent wrote.
	AsPawn->SpawnDefaultController();
	if (AsPawn->GetController() == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("HARNESS-PRECONDITION: PrepareTest: pawn possession failed"));
		return;
	}
	Hover = AsPawn;

	// cp0 0.5 (settled; phase-A anchor Z0), cp1 2.5 (idle-sink gate; drive
	// starts), cp2 5.0 (driven gates; drive stops), cp3 6.5 (resume gate).
	// Between checkpoints the Tick guard watches altitude continuity every
	// simulated frame.
	SetCheckpointSchedule({ 0.5, 2.5, 5.0, 6.5 });
}

void AGravityFloatingPawnFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock first

	if (!IsRunning() || !Hover.IsValid())
	{
		return;
	}

	const double CurrentZ = Hover->GetActorLocation().Z;

	// CONTINUOUS altitude-continuity guard pair — a checkpoint-only sampler
	// would pass a timer that teleports the pawn down in steps sized to mimic
	// the band average. (1) Per-frame: motion inside the disclosed band moves
	// <= ~13 uu per fixed 60Hz frame; a single frame's |dZ| beyond
	// KMaxFrameDropUU is displacement, not motion. (2) Windowed: bursts of
	// sub-per-frame steps are bounded by the rolling-window rate cap. The
	// pair bounds step AMPLITUDE — a stepped descent that survives both is
	// necessarily fine-grained, band-rate movement.
	if (bHaveLastZ && FMath::Abs(CurrentZ - LastZ) > KMaxFrameDropUU)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected smooth, steady descent; observed altitude changed by a discontinuous jump (%.0f units in one frame)."),
				FMath::Abs(CurrentZ - LastZ)));
		return;
	}
	LastZ = CurrentZ;
	bHaveLastZ = true;

	RecentZ.Add(CurrentZ);
	if (RecentZ.Num() > KWindowSamples)
	{
		RecentZ.RemoveAt(0);
	}
	if (RecentZ.Num() == KWindowSamples
		&& (RecentZ[0] - CurrentZ) > KMaxWindowDropUU)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected the descent to stay near the allowed rate at every moment; observed a descent rate burst beyond the allowed band (%.0f units in a quarter second)."),
				RecentZ[0] - CurrentZ));
		return;
	}

	// Sustain lateral locomotion while driving: movement input is consumed
	// per frame, so the drive must be re-applied every tick (never tick the
	// world).
	if (bDriving)
	{
		Hover->AddMovementInput(FVector::XAxisVector, 1.0f);
	}
}

bool AGravityFloatingPawnFunctionalTest::GuardPawn(int32 CheckpointIndex)
{
	if (!Hover.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the hovering pawn is no longer valid (it must keep existing for the whole run)."), CheckpointIndex));
		return false;
	}
	return true;
}

void AGravityFloatingPawnFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!GuardPawn(CheckpointIndex))
	{
		return;
	}
	const FVector Loc = Hover->GetActorLocation();
	UE_LOG(LogTemp, Display, TEXT("[t2-gravpawn calib] cp%d t=%.2f z=%.1f x=%.1f"),
		CheckpointIndex, TimeSeconds, Loc.Z, Loc.X);

	switch (CheckpointIndex)
	{
	case 0:  // t=0.5 — possession settled; anchor the phase-A measurement.
		Z0 = Loc.Z;
		break;

	case 1:  // t=2.5 — idle for 2.0s: the pawn must have sunk, inside the band.
	{
		Z1 = Loc.Z;
		X1 = Loc.X;
		PhaseADrop = Z0 - Z1;
		if (PhaseADrop < KMinPhaseADropUU)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected a steady descent while no movement is requested; observed the pawn does not sink while idle (dropped %.0f units in 2.0s, need at least %.0f)."),
					PhaseADrop, KMinPhaseADropUU));
			return;
		}
		if (PhaseADrop > KMaxPhaseADropUU)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the idle descent to stay inside the required rate band; observed the pawn sinks faster than the required band (dropped %.0f units in 2.0s, cap %.0f)."),
					PhaseADrop, KMaxPhaseADropUU));
			return;
		}
		bDriving = true;
		break;
	}

	case 2:  // t=5.0 — driven for 2.5s: lateral progress + altitude held.
	{
		Z2 = Loc.Z;
		const double LateralProgress = Loc.X - X1;
		if (LateralProgress < KMinLateralProgressUU)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the pawn to translate under sustained movement input; observed no lateral movement under input (progressed %.0f units in 2.5s)."),
					LateralProgress));
			return;
		}
		const double DrivenSink = Z1 - Z2;
		if (DrivenSink > KDrivenSinkMaxRatio * PhaseADrop)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected altitude to hold while movement is requested; observed the pawn sinks while movement is applied (lost %.0f units driven vs %.0f idle)."),
					DrivenSink, PhaseADrop));
			return;
		}
		bDriving = false;
		break;
	}

	case 3:  // t=6.5 — idle again for 1.5s: sinking must have resumed.
	{
		const double ResumeDrop = Z2 - Loc.Z;
		if (ResumeDrop < KResumeMinRatio * PhaseADrop)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the descent to restart once movement input ends; observed sinking does not resume after input ends (dropped %.0f units in 1.5s vs %.0f in phase A)."),
					ResumeDrop, PhaseADrop));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;
	}

	default:
		break;
	}
}
