// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADoorHitchFunctionalTest implementation. The base owns the PIE lever, the
// fixed timestep, and the checkpoint clock; this fixture owns the door
// resolution, the Interact seam, the pose gates, and the per-tick continuity
// monitor. All FAIL message text is ASCII-only (the cp1252 log read-back
// rule), and every gate fails through its OWN literal — the named-FAIL
// placement law: the snap is the continuity gate's concept, the ignored
// reversal is the end-state gate's, never each other's.

#include "DoorHitchFunctionalTest.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
	static const FName HitchDoorTag(TEXT("HitchDoor"));
	static const FName InteractName(TEXT("Interact"));

	// The behavior envelope. The baseline swings ~90 deg over ~1.5 s; the
	// prompt floors "keep roughly the current swing and duration", so the
	// bands are generous. All gates are RELATIVE to the door's own recorded
	// closed pose — no absolute rotations past resolve time.
	constexpr double QuietTolDeg = 2.0;        // pre-Interact motion allowed
	constexpr double MinSwingDeg = 45.0;       // "open" = at least this far
	constexpr double ClosedTolDeg = 10.0;      // "closed" = back within this
	constexpr double MidSwingMinDeg = 15.0;    // reversal must fire mid-swing
	// Continuity: a smooth 90 deg / 1.5 s swing at the deterministic 60 fps
	// is ~1 deg/tick; cubic-tangent peaks stay under ~3. The baseline's
	// restart defect jumps 40-90 deg in ONE tick. 12 deg/tick separates the
	// families with 4x margin on both sides.
	constexpr double TeleportAngleDeg = 12.0;
	constexpr double TeleportLocUnits = 50.0;

	// Checkpoint schedule (world game-time, seconds). Swing time 1.5 s.
	constexpr double CpQuietEnd = 0.50;     // cp0: quiet gate + Interact #1
	constexpr double CpOpenCheck = 2.60;    // cp1: opened + settled
	constexpr double CpCloseCmd = 3.10;     // cp2: Interact #2 (close)
	constexpr double CpClosedCheck = 5.20;  // cp3: closed again
	constexpr double CpReopenCmd = 5.70;    // cp4: Interact #3 (open)
	constexpr double CpMidSwing = 6.45;     // cp5: mid-swing + Interact #4
	constexpr double CpFinal = 8.60;        // cp6: continuity + end-state
}

ADoorHitchFunctionalTest::ADoorHitchFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

UFunction* ADoorHitchFunctionalTest::ResolveInteractSeam() const
{
	if (!Door.IsValid())
	{
		return nullptr;
	}
	UFunction* Function = Door->FindFunction(InteractName);
	if (Function == nullptr)
	{
		return nullptr;
	}
	for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
	{
		if (!(It->PropertyFlags & CPF_ReturnParm))
		{
			return nullptr;
		}
	}
	return Function;
}

void ADoorHitchFunctionalTest::FireInteract()
{
	if (!Door.IsValid() || InteractFn == nullptr)
	{
		return;
	}
	if (InteractFn->ParmsSize > 0)
	{
		TArray<uint8> Buffer;
		Buffer.SetNumZeroed(InteractFn->ParmsSize);
		for (TFieldIterator<FProperty> It(InteractFn); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->InitializeValue_InContainer(Buffer.GetData());
		}
		Door->ProcessEvent(InteractFn, Buffer.GetData());
		for (TFieldIterator<FProperty> It(InteractFn); It && (It->PropertyFlags & CPF_Parm); ++It)
		{
			It->DestroyValue_InContainer(Buffer.GetData());
		}
	}
	else
	{
		Door->ProcessEvent(InteractFn, nullptr);
	}
}

void ADoorHitchFunctionalTest::RecordClosedPose()
{
	ClosedRotations.Reset();
	ClosedLocations.Reset();
	for (const TWeakObjectPtr<UStaticMeshComponent>& Part : Parts)
	{
		if (Part.IsValid())
		{
			ClosedRotations.Add(Part->GetComponentQuat());
			ClosedLocations.Add(Part->GetComponentLocation());
		}
		else
		{
			ClosedRotations.Add(FQuat::Identity);
			ClosedLocations.Add(FVector::ZeroVector);
		}
	}
}

double ADoorHitchFunctionalTest::DisplacementFromClosedDeg() const
{
	double MaxDeg = 0.0;
	for (int32 i = 0; i < Parts.Num(); ++i)
	{
		const TWeakObjectPtr<UStaticMeshComponent>& Part = Parts[i];
		if (!Part.IsValid() || !ClosedRotations.IsValidIndex(i))
		{
			continue;
		}
		const double Rad = Part->GetComponentQuat().AngularDistance(ClosedRotations[i]);
		MaxDeg = FMath::Max(MaxDeg, FMath::RadiansToDegrees(Rad));
	}
	return MaxDeg;
}

void ADoorHitchFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class (the module-wide rule). The level
	// places the door; the agent edits its Blueprint in place, so the placed
	// instance picks the edit up. Renames/subclassing keep the instance tag.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, HitchDoorTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'HitchDoor' (the swinging door) in the running level; found %d."), Found.Num()));
		return;
	}
	Door = Found[0];

	// The observable surface: every static-mesh part of the door. The gates
	// are relative to each part's own closed pose, so mesh choice, component
	// names and extra decorative parts are all free.
	Parts.Reset();
	TInlineComponentArray<UStaticMeshComponent*> MeshComponents(Found[0]);
	for (UStaticMeshComponent* Component : MeshComponents)
	{
		if (Component != nullptr)
		{
			Parts.Add(Component);
		}
	}
	if (Parts.Num() == 0)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("The actor tagged 'HitchDoor' has no static-mesh part to observe - the door lost its visible body."));
		return;
	}

	// The interaction contract: a parameterless reflected entry named
	// 'Interact' (a Blueprint custom event is one). The prompt floors keeping
	// it; the fixture drives the door exclusively through it.
	InteractFn = ResolveInteractSeam();
	if (InteractFn == nullptr)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			TEXT("No parameterless reflected entry named 'Interact' on the door (the interaction contract is broken)."));
		return;
	}

	RecordClosedPose();
	bHavePrevSample = false;
	bMonitorArmed = false;
	MaxTickAngleDeg = 0.0;
	MaxTickLocDelta = 0.0;

	SetCheckpointSchedule({ CpQuietEnd, CpOpenCheck, CpCloseCmd, CpClosedCheck,
	                        CpReopenCmd, CpMidSwing, CpFinal });
}

void ADoorHitchFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // the base checkpoint clock stays the sequencer

	if (IsRunning() == false || !Door.IsValid())
	{
		return;
	}

	// Per-tick continuity monitor (the owner constraint: Tick, never
	// OnCheckpoint - a one-frame teleport is invisible at checkpoint
	// resolution). Only SAMPLES here; the verdict is the final gate's.
	const UWorld* World = GetWorld();
	const double Now = (World != nullptr) ? World->GetTimeSeconds() : 0.0;

	for (int32 i = 0; i < Parts.Num(); ++i)
	{
		const TWeakObjectPtr<UStaticMeshComponent>& Part = Parts[i];
		if (!Part.IsValid())
		{
			continue;
		}
		const FQuat Rotation = Part->GetComponentQuat();
		const FVector Location = Part->GetComponentLocation();
		if (bHavePrevSample && bMonitorArmed
			&& PrevRotations.IsValidIndex(i) && PrevLocations.IsValidIndex(i))
		{
			const double AngleDeg =
				FMath::RadiansToDegrees(Rotation.AngularDistance(PrevRotations[i]));
			const double LocDelta = FVector::Dist(Location, PrevLocations[i]);
			if (AngleDeg > MaxTickAngleDeg)
			{
				MaxTickAngleDeg = AngleDeg;
				MaxTickAngleTime = Now;
			}
			if (LocDelta > MaxTickLocDelta)
			{
				MaxTickLocDelta = LocDelta;
				MaxTickLocTime = Now;
			}
		}
		if (PrevRotations.Num() <= i)
		{
			PrevRotations.SetNum(Parts.Num());
			PrevLocations.SetNum(Parts.Num());
		}
		PrevRotations[i] = Rotation;
		PrevLocations[i] = Location;
	}
	bHavePrevSample = true;
}

void ADoorHitchFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Door.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("The door actor became invalid mid-run (checkpoint %d)."), CheckpointIndex));
		return;
	}

	const double Displacement = DisplacementFromClosedDeg();

	switch (CheckpointIndex)
	{
	case 0:  // quiet-window gate, then the first Interact
		if (Displacement > QuietTolDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The door moved before any Interact fired: %.1f deg in the quiet window - the door must be driven by Interact, not auto-play."), Displacement));
			return;
		}
		// Re-anchor the closed pose to the settled state, arm the monitor,
		// and open the door.
		RecordClosedPose();
		bMonitorArmed = true;
		FireInteract();
		break;

	case 1:  // the door opened
		if (Displacement < MinSwingDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The door did not open after Interact: displacement %.1f deg by t=%.2fs (need at least %.1f deg)."), Displacement, TimeSeconds, MinSwingDeg));
			return;
		}
		break;

	case 2:  // close it (from rest)
		FireInteract();
		break;

	case 3:  // the door closed again
		if (Displacement > ClosedTolDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The door did not return to closed after the second Interact: displacement %.1f deg (closed tolerance %.1f deg)."), Displacement, ClosedTolDeg));
			return;
		}
		break;

	case 4:  // reopen - phase B begins
		FireInteract();
		break;

	case 5:  // the reversal must fire MID-swing to test anything
		if (Displacement < MidSwingMinDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("The door was not visibly mid-swing when the reversal fired: displacement %.1f deg (need at least %.1f deg) - the swing timing changed too much."), Displacement, MidSwingMinDeg));
			return;
		}
		FireInteract();
		break;

	case 6:  // the verdict gates. Continuity FIRST (it owns the snap
	         // concept), then the honored-reversal end state.
		if (MaxTickAngleDeg > TeleportAngleDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("mid-swing Interact teleported the door: a single-tick jump of %.1f deg (limit %.1f) at t=%.2fs - it must reverse smoothly from its current position."), MaxTickAngleDeg, TeleportAngleDeg, MaxTickAngleTime));
			return;
		}
		if (MaxTickLocDelta > TeleportLocUnits)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("mid-swing Interact teleported the door: a single-tick position jump of %.1f units (limit %.1f) at t=%.2fs."), MaxTickLocDelta, TeleportLocUnits, MaxTickLocTime));
			return;
		}
		if (Displacement > ClosedTolDeg)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("the mid-swing Interact was ignored: the door finished opening instead of returning - displacement %.1f deg at the final checkpoint (closed tolerance %.1f deg)."), Displacement, ClosedTolDeg));
			return;
		}
		// All gates green: the base finishes past the last checkpoint.
		break;

	default:
		break;
	}
}
