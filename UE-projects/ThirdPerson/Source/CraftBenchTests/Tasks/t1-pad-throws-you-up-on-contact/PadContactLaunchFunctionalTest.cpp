// Copyright CraftBench. All Rights Reserved.

#include "PadContactLaunchFunctionalTest.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/SoftObjectPath.h"

namespace
{
	// Every one of these is disclosed in the prompt. None is a private
	// threshold: see the spec's requirement-to-gate table.
	constexpr double kApexFloorCm      = 300.0;  // "rise at least 300 cm"
	constexpr double kAirTimeFloorS    = 1.0;    // "at least 1.0 second off the ground"
	constexpr double kLandDeadlineS    = 4.0;    // "standing again no more than 4.0 s after"
	constexpr double kRegainCm         = 50.0;   // "more than 50 cm again ... is a failure"
	constexpr double kGroundToleranceCm = 10.0;  // "on the ground ... within 10 cm"

	// Measured consequences of disclosed geometry, not thresholds of their own.
	constexpr double kCapsuleRadiusCm  = 34.0;   // stock third-person capsule
	constexpr double kTwinClearCm      = 20.0;   // "20 cm clear of the pad's edge"
	// A throw that zeroes horizontal speed drops the subject back onto the pad.
	// Re-triggering there is a FRESH CONTACT and is legal, so the off-pad guard
	// forgives an interval that opens within this long of leaving the region.
	constexpr double kJustLeftPadS     = 0.25;
}

APadContactLaunchFunctionalTest::APadContactLaunchFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void APadContactLaunchFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Identity by TAG, never by class: a subclassed or renamed pad inherits the
	// constructor-stamped tag, and the prompt permits both.
	TArray<AActor*> Pads;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("ContactPad")), Pads);
	if (Pads.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: expected exactly one ")
				TEXT("ContactPad-tagged actor in the level, found %d"), Pads.Num()));
		return;
	}
	Pad = Pads[0];
	PadCentre = Pad->GetActorLocation();

	Subject = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (!Subject.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the map's game mode possessed no player ")
			TEXT("character at index 0"));
		return;
	}

	// The control twin. Same read-only class the game mode uses, so it is an
	// identical twin rather than a bare ACharacter.
	const FSoftClassPath TwinPath(
		TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C"));
	UClass* TwinClass = TwinPath.TryLoadClass<ACharacter>();
	if (TwinClass == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: could not load ")
			TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter for the control twin"));
		return;
	}

	// 200 (pad half-extent) + 34 (capsule radius) + 20 (the disclosed clearance).
	const FVector TwinSpot = PadCentre
		+ FVector(0.0, -(PadHalfXY + kCapsuleRadiusCm + kTwinClearCm), 92.0);

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ACharacter* SpawnedTwin = World->SpawnActor<ACharacter>(
		TwinClass, FTransform(TwinSpot), SpawnParams);
	if (SpawnedTwin == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: control twin failed to spawn"));
		return;
	}
	// MANDATORY. An unpossessed Character is inert (MOVE_None, no gravity), so a
	// "the twin stayed grounded" gate on an unpossessed twin measures nothing.
	SpawnedTwin->SpawnDefaultController();
	Twin = SpawnedTwin;

	SubjectBaseZ = Subject->GetActorLocation().Z;
	TwinBaseZ = SpawnedTwin->GetActorLocation().Z;

	// Presentation only. Never gates. Under -nullrhi these render nothing and
	// the certified verdict is unaffected; the capture and preview legs show
	// them, which is how every number the grade depends on becomes visible.
	SubjectReadout = NewObject<UTextRenderComponent>(Subject.Get());
	if (SubjectReadout)
	{
		SubjectReadout->RegisterComponent();
		SubjectReadout->AttachToComponent(Subject->GetRootComponent(),
			FAttachmentTransformRules::KeepRelativeTransform);
		SubjectReadout->SetRelativeLocation(FVector(0.0, 0.0, 120.0));
		SubjectReadout->SetHorizontalAlignment(EHTA_Center);
		SubjectReadout->SetWorldSize(24.0f);
		// ABSOLUTE rotation, facing the camera plan's side of the lane. Two
		// reasons, both measured on the first capture pass: attached to the
		// character's root the text INHERITS the character's yaw, so it rendered
		// MIRRORED from the camera, and it would flip again when the character
		// turns around for the walk-back. Absolute rotation pins it.
		SubjectReadout->SetUsingAbsoluteRotation(true);
		SubjectReadout->SetWorldRotation(FRotator(0.0, 180.0, 0.0));
	}
	TwinReadout = NewObject<UTextRenderComponent>(SpawnedTwin);
	if (TwinReadout)
	{
		TwinReadout->RegisterComponent();
		TwinReadout->AttachToComponent(SpawnedTwin->GetRootComponent(),
			FAttachmentTransformRules::KeepRelativeTransform);
		TwinReadout->SetRelativeLocation(FVector(0.0, 0.0, 120.0));
		TwinReadout->SetHorizontalAlignment(EHTA_Center);
		TwinReadout->SetWorldSize(24.0f);
		TwinReadout->SetUsingAbsoluteRotation(true);
		TwinReadout->SetWorldRotation(FRotator(0.0, 180.0, 0.0));
	}

	SetCheckpointSchedule({ 0.6, 2.9, 6.6, 8.8, 13.2 });
}

bool APadContactLaunchFunctionalTest::IsOnPad(const FVector& Loc) const
{
	// The footprint overlaps the pad region in plan view. Half-extent plus the
	// capsule radius: both are disclosed geometry.
	const double Reach = PadHalfXY + kCapsuleRadiusCm;
	return FMath::Abs(Loc.X - PadCentre.X) <= Reach
		&& FMath::Abs(Loc.Y - PadCentre.Y) <= Reach;
}

void APadContactLaunchFunctionalTest::RecordSample(double T)
{
	ACharacter* const S = Subject.Get();
	if (S == nullptr)
	{
		return;
	}

	FPadSample Sample;
	Sample.T = T;
	Sample.Loc = S->GetActorLocation();
	Sample.Z = Sample.Loc.Z;
	Sample.VZ = S->GetVelocity().Z;
	const UCharacterMovementComponent* const CMC = S->GetCharacterMovement();
	Sample.bGrounded = CMC != nullptr && CMC->IsMovingOnGround();
	Series.Add(Sample);

	if (Sample.bGrounded && IsOnPad(Sample.Loc))
	{
		LastOnPadT = T;
	}

	// --- air-interval bookkeeping, ground-departure to ground-contact --------
	const int32 Count = Series.Num();
	const bool bWasGrounded = Count >= 2 ? Series[Count - 2].bGrounded : true;

	if (bWasGrounded && !Sample.bGrounded)
	{
		FPadAirInterval Opened;
		Opened.DepartT = Count >= 2 ? Series[Count - 2].T : T;
		Opened.PeakZ = Sample.Z;
		// On the pad, or having left it a moment ago (the zero-horizontal-speed
		// throw drops the subject straight back down onto its own pad).
		Opened.bOnPadAtOpen = IsOnPad(Sample.Loc) || (T - LastOnPadT) <= kJustLeftPadS;
		Intervals.Add(Opened);
	}
	else if (!Sample.bGrounded && Intervals.Num() > 0 && !Intervals.Last().bClosed)
	{
		FPadAirInterval& Open = Intervals.Last();
		// A rise is a monotone upward run of MORE than 50 cm (strictly greater:
		// an exactly-50.0 cm re-gain is legal by the prompt).
		if (Sample.Z > Open.PeakZ)
		{
			Open.PeakZ = Sample.Z;
		}
		// Upward runs are counted once, when the interval closes: a run's size
		// is only known at its top, and the close pass walks the whole interval.
	}

	if (!bWasGrounded && Sample.bGrounded && Intervals.Num() > 0
		&& !Intervals.Last().bClosed)
	{
		FPadAirInterval& Closing = Intervals.Last();
		Closing.ContactT = T;
		Closing.bClosed = true;

		// Count the monotone upward runs of > 50 cm inside the closed interval.
		double RunStartZ = 0.0;
		bool bInRun = false;
		int32 Rises = 0;
		for (int32 i = 0; i < Series.Num(); ++i)
		{
			if (Series[i].T < Closing.DepartT || Series[i].T > Closing.ContactT)
			{
				continue;
			}
			const bool bUp = Series[i].VZ > 0.0;
			if (bUp && !bInRun)
			{
				bInRun = true;
				RunStartZ = Series[i].Z;
			}
			else if (!bUp && bInRun)
			{
				bInRun = false;
				if (Series[i].Z - RunStartZ > kRegainCm)
				{
					++Rises;
				}
			}
		}
		if (bInRun && Series.Num() > 0
			&& Series.Last().Z - RunStartZ > kRegainCm)
		{
			++Rises;
		}
		Closing.RiseCount = Rises;
	}
}

void APadContactLaunchFunctionalTest::UpdateReadouts()
{
	if (SubjectReadout && Subject.IsValid())
	{
		double Peak = 0.0;
		double Air = 0.0;
		for (const FPadAirInterval& I : Intervals)
		{
			Peak = FMath::Max(Peak, I.PeakZ - SubjectBaseZ);
			const double End = I.bClosed ? I.ContactT
				: (Series.Num() ? Series.Last().T : I.DepartT);
			Air = FMath::Max(Air, End - I.DepartT);
		}
		SubjectReadout->SetText(FText::FromString(FString::Printf(
			TEXT("up %.0f cm   peak %.0f cm   air %.2f s"),
			Subject->GetActorLocation().Z - SubjectBaseZ, Peak, Air)));
	}
	if (TwinReadout && Twin.IsValid())
	{
		TwinReadout->SetText(FText::FromString(FString::Printf(
			TEXT("control   up %.0f cm"),
			Twin->GetActorLocation().Z - TwinBaseZ)));
	}
}

void APadContactLaunchFunctionalTest::Tick(float DeltaSeconds)
{
	// Base first: it owns the checkpoint clock, so OnCheckpoint sees the series
	// this frame already appended.
	UWorld* const World = GetWorld();
	const double Now = World ? World->GetTimeSeconds() : 0.0;

	RecordSample(Now);
	UpdateReadouts();

	Super::Tick(DeltaSeconds);

	if (bDriving && bDriveUntilClearOfPad && Subject.IsValid()
		&& !IsOnPad(Subject->GetActorLocation())
		&& FMath::Abs(Subject->GetActorLocation().X - PadCentre.X)
			> PadHalfXY + kCapsuleRadiusCm + 140.0)
	{
		// Off the plate with real clearance. Stop, so the walk-back is a clean
		// fresh approach rather than a march to the end of the floor.
		bDriving = false;
		bDriveUntilClearOfPad = false;
	}
	if (bDriving && ReleaseDriveAboveIntervals >= 0
		&& Intervals.Num() > ReleaseDriveAboveIntervals)
	{
		// Thrown. Let go, exactly as a player would. The subject keeps the
		// horizontal speed it had (lateral friction is 0 in air), so it travels
		// forward through the arc and brakes where it lands.
		bDriving = false;
	}
	if (bDriving && Subject.IsValid())
	{
		// Per-frame, exactly as holding a key does: movement input is consumed
		// every frame. Never tick the world.
		Subject->AddMovementInput(DriveDir, 1.0f);
	}

	if (!bGuardsArmed)
	{
		return;
	}

	// --- continuous off-pad guard (gate 1) ---------------------------------
	// Armed for the WHOLE run so an unconditional or timed throw is caught
	// wherever it happens. Keyed to CONTACT, never to an interval ordinal.
	for (const FPadAirInterval& I : Intervals)
	{
		if (!I.bOnPadAtOpen)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PadInertBeforeContact: the character was thrown while it ")
				TEXT("was not on the pad (air interval opened at t=%.2f with the ")
				TEXT("character at X=%.0f Y=%.0f, outside the pad region)"),
				I.DepartT,
				Series.Num() ? Series.Last().Loc.X : 0.0,
				Series.Num() ? Series.Last().Loc.Y : 0.0));
			return;
		}
	}

	// --- continuous control guard (gate 7) ---------------------------------
	if (Twin.IsValid())
	{
		const double TwinDZ = Twin->GetActorLocation().Z - TwinBaseZ;
		if (FMath::Abs(TwinDZ) > kGroundToleranceCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ControlStaysGroundedThroughout: the second character left ")
				TEXT("its start height by %.1f cm at t=%.2f (allowed %.0f cm); ")
				TEXT("the pad must throw only what is actually on it"),
				TwinDZ, Now, kGroundToleranceCm));
			return;
		}
	}
}

bool APadContactLaunchFunctionalTest::JudgeThrow(const FPadAirInterval& Interval,
	int32 CheckpointIndex, const TCHAR* WhichThrow)
{
	const double Apex = Interval.PeakZ - SubjectBaseZ;
	const double AirTime = Interval.ContactT - Interval.DepartT;

	// Gate 3 — apex and peak-then-descend, its OWN literal.
	if (Apex < kApexFloorCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RisesThenFallsUnderGravity: %s rose only %.0f cm above the ")
			TEXT("height the character was standing at (the level asks for at ")
			TEXT("least %.0f cm, the marked band on the post)"),
			WhichThrow, Apex, kApexFloorCm));
		return false;
	}

	// Gate 3b — the air-time floor, split out so a short honest launch and a
	// set-Z-then-drop spoof cannot produce the same failure string.
	if (AirTime < kAirTimeFloorS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("StaysOffTheGroundLongEnough: %s kept the character off the ")
			TEXT("ground for only %.2f s (the level asks for at least %.1f s); ")
			TEXT("a jump to the top and an instant drop back is not a throw"),
			WhichThrow, AirTime, kAirTimeFloorS));
		return false;
	}

	// Gate 4 — landed inside the deadline.
	if (AirTime > kLandDeadlineS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("LandsBackOnTheGround: %s left the character off the ground for ")
			TEXT("%.2f s, past the %.1f s the level allows before it must be ")
			TEXT("standing again"),
			WhichThrow, AirTime, kLandDeadlineS));
		return false;
	}

	// Gate 5 — one touch is one throw.
	if (Interval.RiseCount != 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("OneThrowPerContact: %s gained height %d separate times before ")
			TEXT("landing (one touch is one throw; gaining more than %.0f cm ")
			TEXT("again in mid-air is a failure)"),
			WhichThrow, Interval.RiseCount, kRegainCm));
		return false;
	}

	return true;
}

bool APadContactLaunchFunctionalTest::GuardSubjects(int32 CheckpointIndex)
{
	if (!Subject.IsValid() || !Twin.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: a graded character went away before cp%d"),
			CheckpointIndex));
		return false;
	}
	return true;
}

void APadContactLaunchFunctionalTest::OnCheckpoint(int32 CheckpointIndex,
	double TimeSeconds)
{
	if (!GuardSubjects(CheckpointIndex))
	{
		return;
	}

	ACharacter* const S = Subject.Get();
	const FVector SLoc = S->GetActorLocation();
	const UCharacterMovementComponent* const CMC = S->GetCharacterMovement();
	const bool bGrounded = CMC != nullptr && CMC->IsMovingOnGround();

	double Peak = 0.0;
	for (const FPadAirInterval& I : Intervals)
	{
		Peak = FMath::Max(Peak, I.PeakZ - SubjectBaseZ);
	}

	// Calibration line. Read this instead of guessing at a wrong decomposition.
	UE_LOG(LogTemp, Display,
		TEXT("[t1-pad calib] cp%d t=%.2f z=%.1f dz=%.1f vz=%.1f mode=%d x=%.0f ")
		TEXT("y=%.0f twindz=%.1f intervals=%d peak=%.0f"),
		CheckpointIndex, TimeSeconds, SLoc.Z, SLoc.Z - SubjectBaseZ,
		S->GetVelocity().Z, CMC ? (int32)CMC->MovementMode : -1, SLoc.X, SLoc.Y,
		Twin->GetActorLocation().Z - TwinBaseZ, Intervals.Num(), Peak);

	switch (CheckpointIndex)
	{
	case 0:
	{
		// Gate 1 (instant half) and gate 7 (instant half).
		const UCharacterMovementComponent* const TCMC =
			Twin->GetCharacterMovement();
		if (TCMC == nullptr || !TCMC->IsMovingOnGround())
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: the control twin is not walking on ")
				TEXT("the ground at cp0, so a 'the control stayed put' gate would ")
				TEXT("measure nothing"));
			return;
		}
		if (S->GetMesh() == nullptr || S->GetMesh()->GetSkeletalMeshAsset() == nullptr
			|| Twin->GetMesh() == nullptr
			|| Twin->GetMesh()->GetSkeletalMeshAsset() == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: a graded character has no visible ")
				TEXT("body, so a human reviewing the recording would see nothing"));
			return;
		}
		if (FMath::Abs(SLoc.Z - SubjectBaseZ) > kGroundToleranceCm || !bGrounded)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PadInertBeforeContact: the character was already %.1f cm ")
				TEXT("off its start height at t=%.2f with nobody on the pad ")
				TEXT("(allowed %.0f cm)"),
				SLoc.Z - SubjectBaseZ, TimeSeconds, kGroundToleranceCm));
			return;
		}
		if (Intervals.Num() != 0)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("PadInertBeforeContact: the character had already left the ")
				TEXT("ground %d time(s) before anyone stood on the pad"),
				Intervals.Num()));
			return;
		}
		bGuardsArmed = true;
		DriveDir = FVector(1.0, 0.0, 0.0);
		bDriving = true;
		ReleaseDriveAboveIntervals = Intervals.Num();   // 0: release on throw #1
		break;
	}
	case 1:
	{
		// Gate 2 — contact threw the subject up.
		if (bGrounded || SLoc.Z <= SubjectBaseZ + kGroundToleranceCm)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("ContactThrowsSubjectUp: the character walked onto the pad ")
				TEXT("and was still on the ground at t=%.2f (height %.1f cm above ")
				TEXT("its start); walking onto the pad must throw it upward"),
				TimeSeconds, SLoc.Z - SubjectBaseZ));
			return;
		}
		break;
	}
	case 2:
	{
		// Gates 3, 3b, 4, 5 against THROW(1) — the interval opened by the first
		// contact event.
		const FPadAirInterval* First = nullptr;
		for (const FPadAirInterval& I : Intervals)
		{
			if (I.bOnPadAtOpen && I.bClosed)
			{
				First = &I;
				break;
			}
		}
		if (First == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("LandsBackOnTheGround: by t=%.2f no throw begun on the pad ")
				TEXT("had finished with the character standing again"),
				TimeSeconds));
			return;
		}
		if (!JudgeThrow(*First, CheckpointIndex, TEXT("the first throw")))
		{
			return;
		}
		// MEASURED, not assumed: this reference throws near-vertically, so the
		// subject comes back down ONTO the plate (x=-140, 9 cm up on the plate's
		// own top face). The spec declares that shape legal, so the drive plan
		// has to cope with it: walk OFF the pad now, and come back at cp3. A
		// reference that instead carried the subject forward would already be
		// clear here, and this drive stops immediately on the same condition.
		DriveDir = FVector(-1.0, 0.0, 0.0);
		bDriving = true;
		bDriveUntilClearOfPad = true;
		ReleaseDriveAboveIntervals = -1;   // no throw expected walking off
		break;
	}
	case 3:
	{
		// Nothing here counts intervals. A bounce back onto the pad between cp2
		// and cp3 is a fresh contact and is legal; what forbids an uncaused
		// throw is the continuous guard in Tick.
		if (!bGrounded)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("LandsBackOnTheGround: the character was still off the ")
				TEXT("ground at t=%.2f, %.1f cm above its start height"),
				TimeSeconds, SLoc.Z - SubjectBaseZ));
			return;
		}
		// Back onto the pad for the second contact. Direction is derived from
		// where the subject actually is, so it works whichever side the first
		// throw left it on.
		DriveDir = FVector(SLoc.X < PadCentre.X ? 1.0 : -1.0, 0.0, 0.0);
		bDriving = true;
		bDriveUntilClearOfPad = false;
		ReleaseDriveAboveIntervals = Intervals.Num();   // release on throw #2
		break;
	}
	case 4:
	{
		// Gate 6 — a SECOND contact event exists at all.
		int32 ContactEvents = 0;
		const FPadAirInterval* Last = nullptr;
		for (const FPadAirInterval& I : Intervals)
		{
			if (I.bOnPadAtOpen)
			{
				++ContactEvents;
				if (I.bClosed)
				{
					Last = &I;
				}
			}
		}
		if (ContactEvents < 2)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("SecondContactThrowsAgain: the character walked back onto ")
				TEXT("the pad but was thrown only %d time(s) in the whole run; ")
				TEXT("the pad must not be a one-time trick"),
				ContactEvents));
			return;
		}
		if (Last == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("LandsBackOnTheGround: the second throw had not finished ")
				TEXT("with the character standing again by t=%.2f"), TimeSeconds));
			return;
		}
		// Gates 3, 3b, 4, 5 again, against THROW(2) — the LAST contact-opened
		// interval before this checkpoint. Keyed to contact EVENTS, so an
		// intermediate bounce cannot shift which throw is graded.
		if (!JudgeThrow(*Last, CheckpointIndex, TEXT("the second throw")))
		{
			return;
		}
		bDriving = false;
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("pad threw the character on every contact; the control stayed put"));
		break;
	}
	default:
		break;
	}
}
