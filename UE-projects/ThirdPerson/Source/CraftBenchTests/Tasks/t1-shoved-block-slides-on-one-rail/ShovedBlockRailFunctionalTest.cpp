// Copyright CraftBench. All Rights Reserved.

#include "ShovedBlockRailFunctionalTest.h"

#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	// DISCLOSED in the prompt. None of these is a private threshold.
	constexpr double kMinAdvanceCm     = 200.0;  // "at least 200 cm further along"
	constexpr double kMaxOffLineCm     = 8.0;    // "never more than 8 cm to either side"
	constexpr double kMaxOffHeightCm   = 10.0;   // "never more than 10 cm above or below"
	constexpr double kMaxTurnDeg       = 10.0;   // "never turned more than 10 degrees"
	constexpr double kMinSpeedCmS      = 100.0;  // "at least 100 cm/s at some point"
	constexpr double kRestSpeedCmS     = 5.0;    // "moving slower than 5 cm per second"
	constexpr double kRestPosCm        = 10.0;   // "within 10 cm of the mark"
	constexpr double kKnockOffCm       = 60.0;   // "say 60 cm to one side"
	constexpr double kKnockUpCm        = 40.0;   // "and 40 cm up"
	constexpr double kTwinOff1Cm       = 60.0;   // "at least 60 cm off after the first"
	constexpr double kTwinOff2Cm       = 100.0;  // "at least 100 cm off after the second"
	constexpr double kTwinTurnDeg      = 45.0;   // "turned at least 45 degrees"
	constexpr double kTwinStillOffCm   = 40.0;   // the knock's displacement is still there
	constexpr double kRecoverCm        = 10.0;   // "back within 10 cm of the line" / height
	constexpr double kRailYawDeg       = 30.0;   // "30 degrees off the world X axis"

	// UNDISCLOSED: fixture geometry and clocking, never thresholds on the answer.
	constexpr double kMarkerYawToleranceDeg = 0.5;
	constexpr double kMarkerOriginToleranceCm = 5.0;
	constexpr double kPreContactGuardCm = 250.0;
	constexpr double kShoveDetectCmS    = 50.0;
	constexpr double kTwinSettledCmS    = 20.0;
	constexpr double kShoveDeadlineS    = 4.0;
	constexpr double kSettleAfterShoveS = 1.5;
	constexpr double kTetherWaitS       = 1.6;
	constexpr double kOutOfPlungerCm    = 320.0;
	// How much of a frame's motion may be UNEXPLAINED by the body's own velocity
	// before we stop believing the world's physics is what moved it, and the speed
	// below which the comparison is not worth making.
	constexpr double kUnexplainedCmS    = 120.0;
	constexpr double kExplainAboveCmS   = 200.0;
}

AShovedBlockRailFunctionalTest::AShovedBlockRailFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool AShovedBlockRailFunctionalTest::ResolveOne(const TCHAR* Tag,
	TWeakObjectPtr<AActor>& Out)
{
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(Tag), Found);
	if (Found.Num() != 1 || Found[0] == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected exactly one actor tagged %s, found %d"),
			Tag, Found.Num()));
		return false;
	}
	Out = Found[0];
	return true;
}

bool AShovedBlockRailFunctionalTest::InitProbe(FRailBlockProbe& Probe, AActor* Actor,
	const TCHAR* Which)
{
	Probe.Actor = Actor;
	Probe.Body = Actor ? Cast<UPrimitiveComponent>(Actor->GetRootComponent()) : nullptr;
	if (!Probe.Body.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: the %s block has no primitive root, so no "
				 "rigid body can be read off it"), Which));
		return false;
	}
	Probe.StartLocation = Actor->GetActorLocation();
	Probe.StartRotation = Actor->GetActorQuat();
	ResetWindow(Probe);
	return true;
}

void AShovedBlockRailFunctionalTest::ResetWindow(FRailBlockProbe& Probe)
{
	Probe.MaxOffLine = 0.0;
	Probe.MaxOffHeight = 0.0;
	Probe.MaxTurnDeg = 0.0;
	Probe.MaxSpeed = 0.0;
	Probe.MaxUnexplained = 0.0;
	Probe.bHasPrev = false;
}

double AShovedBlockRailFunctionalTest::AlongRail(const FVector& P) const
{
	return FVector::DotProduct(P - RailPoint, RailForward);
}

double AShovedBlockRailFunctionalTest::OffRail(const FVector& P) const
{
	return FVector::DotProduct(P - RailPoint, RailRight);
}

double AShovedBlockRailFunctionalTest::TurnDegrees(const FRailBlockProbe& Probe) const
{
	if (!Probe.Actor.IsValid())
	{
		return 0.0;
	}
	// Full angular distance, not yaw only: a block that tips is turned too.
	return FMath::RadiansToDegrees(
		Probe.StartRotation.AngularDistance(Probe.Actor->GetActorQuat()));
}

double AShovedBlockRailFunctionalTest::Speed(const FRailBlockProbe& Probe) const
{
	return Probe.Body.IsValid()
		? Probe.Body->GetPhysicsLinearVelocity().Size() : 0.0;
}

void AShovedBlockRailFunctionalTest::AccumulateWindow(FRailBlockProbe& Probe,
	float DeltaSeconds)
{
	if (!Probe.Actor.IsValid())
	{
		return;
	}
	const FVector P = Probe.Actor->GetActorLocation();

	// DOES ITS OWN VELOCITY EXPLAIN THE MOTION? The peak-speed gate alone does not
	// answer that: the plunger's real push gives even a scripted block a brief real
	// velocity, and a spoofed-motion variant sailed past a 100 cm/s floor on 131 cm/s
	// of residual while a per-tick transform write did all the travelling (measured
	// 2026-08-17). Comparing distance actually covered against the velocity the
	// solver reports catches that, and it is the prompt's own wording -- "its own
	// physics velocity is what carries it".
	if (Probe.bHasPrev && DeltaSeconds > SMALL_NUMBER)
	{
		const double Observed = FVector::Dist(P, Probe.PrevLocation) / DeltaSeconds;
		if (Observed > kExplainAboveCmS)
		{
			Probe.MaxUnexplained = FMath::Max(Probe.MaxUnexplained,
				Observed - Speed(Probe));
		}
	}
	Probe.PrevLocation = P;
	Probe.bHasPrev = true;
	Probe.MaxOffLine = FMath::Max(Probe.MaxOffLine, FMath::Abs(OffRail(P)));
	Probe.MaxOffHeight = FMath::Max(Probe.MaxOffHeight,
		FMath::Abs(P.Z - Probe.StartLocation.Z));
	Probe.MaxTurnDeg = FMath::Max(Probe.MaxTurnDeg, TurnDegrees(Probe));
	Probe.MaxSpeed = FMath::Max(Probe.MaxSpeed, Speed(Probe));
}

bool AShovedBlockRailFunctionalTest::RailMarkerStillPlaced()
{
	if (!RailMarker.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RailMarkerPresent: the painted rail marker is gone from the level"));
		return false;
	}
	const double YawOff = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
		FVector::DotProduct(RailMarker->GetActorForwardVector().GetSafeNormal2D(),
			RailForward), -1.0, 1.0)));
	const double OriginOff = FVector::Dist(RailMarker->GetActorLocation(), RailPoint);
	if (YawOff > kMarkerYawToleranceDeg || OriginOff > kMarkerOriginToleranceCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailMarkerUnmoved: the rail marker is not where the level put it "
				 "(bearing off by %.2f deg, origin off by %.1f cm)"),
			YawOff, OriginOff));
		return false;
	}
	return true;
}

void AShovedBlockRailFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: no world"));
		return;
	}

	// Identity by TAG, never by class: the agent may subclass or rename.
	TWeakObjectPtr<AActor> RailBlockActor, TwinBlockActor, HeroActor;
	if (!ResolveOne(TEXT("RailBlock"), RailBlockActor)) { return; }
	if (!ResolveOne(TEXT("TwinBlock"), TwinBlockActor)) { return; }
	if (!ResolveOne(TEXT("Plunger"), Plunger)) { return; }
	if (!ResolveOne(TEXT("RailLine"), RailMarker)) { return; }
	if (!ResolveOne(TEXT("BenchHero"), HeroActor)) { return; }

	Hero = Cast<ACharacter>(HeroActor.Get());
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the BenchHero actor is not a character"));
		return;
	}
	// Owner bar #1: an invisible run is unreviewable.
	const USkeletalMeshComponent* const HeroMesh = Hero->GetMesh();
	if (HeroMesh == nullptr || HeroMesh->GetSkeletalMeshAsset() == nullptr
		|| !HeroMesh->IsVisible()
		|| HeroMesh->GetComponentScale().IsNearlyZero())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the playable character has no visible mesh, "
				 "so a human watching the replay would see nothing"));
		return;
	}

	// The authored rail frame is a constant of the map contract; the placed marker
	// is asserted against it here and at every checkpoint, so rotating the rail at
	// runtime to make a world-axis lock look correct is not a route.
	RailForward = FRotator(0.0, kRailYawDeg, 0.0).Vector().GetSafeNormal2D();
	RailRight = FVector::CrossProduct(FVector::UpVector, RailForward).GetSafeNormal2D();
	RailPoint = RailMarker->GetActorLocation();
	if (!RailMarkerStillPlaced()) { return; }

	if (!InitProbe(Rail, RailBlockActor.Get(), TEXT("railed"))) { return; }
	if (!InitProbe(Twin, TwinBlockActor.Get(), TEXT("twin"))) { return; }
	RailSAtCp0 = AlongRail(Rail.StartLocation);

	// The four graded instants, plus a SENTINEL.
	//
	// THE SENTINEL IS LOAD-BEARING, and its absence made this fixture pass
	// vacuously. ACraftBenchFunctionalTest::Tick ends with
	//     if (NextCheckpointIndex >= Checkpoints.Num())
	//         FinishTest(Succeeded, "All checkpoints sampled.")
	// so the moment the LAST scheduled instant is crossed the base declares
	// success. This fixture treats the schedule as the EARLIEST instant each
	// checkpoint may be graded and defers the rest off measured events, so cp3 --
	// clocked 1.6 s after a knock that happens when cp2 grades -- landed AFTER
	// 10.1 and never ran at all. Measured 2026-08-17: the reference and the
	// one-shot-rail variant both reported Result={Success} with no cp3 line in
	// either log, i.e. the tether leg, the whole point of the task, was
	// unreachable while reading green.
	//
	// The sentinel sits far past any real grade, so the base's auto-success is
	// never reached; and if the machine somehow has not finished by then, this
	// FAILS loudly instead of inheriting a pass.
	TimeLimitMargin = 4.0f;
	SetCheckpointSchedule({0.7, 4.5, 8.5, 10.1, 20.0});
}

void AShovedBlockRailFunctionalTest::LogCalib(int32 Index, double Now) const
{
	if (!Rail.Actor.IsValid() || !Twin.Actor.IsValid())
	{
		return;
	}
	const FVector RP = Rail.Actor->GetActorLocation();
	const FVector TP = Twin.Actor->GetActorLocation();
	UE_LOG(LogTemp, Display,
		TEXT("[t1-rail calib] cp%d t=%.2f rail s=%.1f d=%.2f dz=%.2f turn=%.2f v=%.1f "
			 "vmax=%.1f dmax=%.2f dzmax=%.2f turnmax=%.2f twin d=%.1f turn=%.1f"),
		Index, Now, AlongRail(RP) - RailSAtCp0, OffRail(RP),
		RP.Z - Rail.StartLocation.Z, TurnDegrees(Rail), Speed(Rail),
		Rail.MaxSpeed, Rail.MaxOffLine, Rail.MaxOffHeight, Rail.MaxTurnDeg,
		FVector::DotProduct(TP - Twin.StartLocation, RailRight), TurnDegrees(Twin));
}

void AShovedBlockRailFunctionalTest::DriveToward(const FVector& Target, float)
{
	if (!Hero.IsValid())
	{
		return;
	}
	const FVector Here = Hero->GetActorLocation();
	const FVector Flat(Target.X - Here.X, Target.Y - Here.Y, 0.0);
	// Input is consumed per frame, so it is re-applied every tick. This is the
	// same path a human's WASD drives.
	Hero->AddMovementInput(Flat.GetSafeNormal(), 1.0f);
}

void AShovedBlockRailFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double)
{
	// The base's schedule is the EARLIEST instant each checkpoint may be graded.
	// Grading itself is ordered by the state machine in Tick, because cp1..cp3 are
	// deferred off MEASURED events (the two shove instants and the knock) rather
	// than off fixed sample times.
	if (CheckpointIndex >= 0 && CheckpointIndex < 4)
	{
		bCheckpointDue[CheckpointIndex] = true;
		return;
	}
	// The sentinel. Reaching it means a deferred grade never happened.
	if (Phase != EPhase::Done)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailRunCompletes: the run never reached its last graded instant "
				 "(stopped in phase %d; shove1 at %.2f, shove2 at %.2f, knock at "
				 "%.2f -- a negative value is an event that never happened)"),
			(int32)Phase, Shove1Time, Shove2Time, KnockTime));
	}
}

void AShovedBlockRailFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);  // base first: checkpoint clock + timeout machinery

	if (!IsRunning() || Phase == EPhase::Done
		|| !Rail.Actor.IsValid() || !Twin.Actor.IsValid()
		|| !Hero.IsValid() || !Plunger.IsValid())
	{
		return;
	}
	const UWorld* const World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;

	if (!RailMarkerStillPlaced())
	{
		return;
	}

	AccumulateWindow(Rail, DeltaSeconds);
	AccumulateWindow(Twin, DeltaSeconds);

	const FVector PlungerAt = Plunger->GetActorLocation();
	const double HeroToPlunger = FVector::Dist2D(Hero->GetActorLocation(), PlungerAt);

	// CONTINUOUS pre-contact guard: nothing may move either block until the
	// character walks into the plunger.
	if (Shove1Time < 0.0 && HeroToPlunger > kPreContactGuardCm)
	{
		for (const FRailBlockProbe* Probe : {&Rail, &Twin})
		{
			const double Moved = FVector::Dist(
				Probe->Actor->GetActorLocation(), Probe->StartLocation);
			if (Moved > kRestPosCm)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(
					TEXT("BlocksWaitForContact: the blocks moved before the character "
						 "reached the plunger (%s block is %.1f cm off its mark with "
						 "the character still %.0f cm away; the level allows %.0f cm)"),
					Probe == &Rail ? TEXT("railed") : TEXT("twin"),
					Moved, HeroToPlunger, kRestPosCm));
				return;
			}
		}
	}

	// The shove instants are MEASURED off the control twin, never assumed.
	if (Phase == EPhase::DrivingIn && Shove1Time < 0.0
		&& Speed(Twin) > kShoveDetectCmS)
	{
		Shove1Time = Now;
		Phase = EPhase::AwaitCp1;
	}
	if (Phase == EPhase::DrivingIn && Now > kShoveDeadlineS && Shove1Time < 0.0)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("PlungerShovesBlocks: the plunger never shoved the blocks (nothing "
				 "moved by t=%.1f s, with the character %.0f cm from the post)"),
			Now, HeroToPlunger));
		return;
	}
	if (Phase == EPhase::DrivingInAgain)
	{
		if (!bTwinSettledAfterShove1 && Speed(Twin) < kTwinSettledCmS)
		{
			bTwinSettledAfterShove1 = true;  // only then can a second shove be told apart
		}
		if (bTwinSettledAfterShove1 && Shove2Time < 0.0
			&& Speed(Twin) > kShoveDetectCmS)
		{
			Shove2Time = Now;
			Phase = EPhase::AwaitCp2;
		}
	}

	switch (Phase)
	{
	case EPhase::Settling:
		if (bCheckpointDue[0])
		{
			GradeCp0(Now);
		}
		break;

	case EPhase::DrivingIn:
	case EPhase::DrivingInAgain:
		DriveToward(PlungerAt, DeltaSeconds);
		break;

	case EPhase::AwaitCp1:
		DriveToward(PlungerAt, DeltaSeconds);
		if (bCheckpointDue[1] && Now >= Shove1Time + kSettleAfterShoveS)
		{
			GradeCp1(Now);
		}
		break;

	case EPhase::DrivingOut:
	{
		// Back out far enough that the plunger re-arms, then walk in again.
		const FVector Away = Hero->GetActorLocation()
			+ (Hero->GetActorLocation() - PlungerAt).GetSafeNormal2D() * 500.0;
		DriveToward(Away, DeltaSeconds);
		if (HeroToPlunger > kOutOfPlungerCm)
		{
			Phase = EPhase::DrivingInAgain;
		}
		break;
	}

	case EPhase::AwaitCp2:
		if (bCheckpointDue[2] && Now >= Shove2Time + kSettleAfterShoveS)
		{
			GradeCp2(Now);
		}
		break;

	case EPhase::AwaitCp3:
		if (Now >= KnockTime + kTetherWaitS)
		{
			GradeCp3(Now);
		}
		break;

	default:
		break;
	}
}

void AShovedBlockRailFunctionalTest::GradeCp0(double Now)
{
	LogCalib(0, Now);

	struct FRestCase
	{
		const FRailBlockProbe* Probe;
		const TCHAR* Gate;
		const TCHAR* Which;
	};
	const FRestCase Cases[] = {
		{&Rail, TEXT("RailBlockAtRest"), TEXT("railed")},
		{&Twin, TEXT("TwinBlockAtRest"), TEXT("twin")},
	};
	for (const FRestCase& Case : Cases)
	{
		const FVector P = Case.Probe->Actor->GetActorLocation();
		const double Moved = FVector::Dist(P, Case.Probe->StartLocation);
		const double V = Speed(*Case.Probe);
		const double Turn = TurnDegrees(*Case.Probe);
		if (Moved > kRestPosCm || V > kRestSpeedCmS || Turn > kMaxTurnDeg)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("%s: the %s block is not standing still on its mark before the "
					 "character reaches the plunger (%.1f cm off its mark, %.1f cm/s, "
					 "turned %.1f deg; the level allows %.0f cm, %.0f cm/s and "
					 "%.0f deg)"),
				Case.Gate, Case.Which, Moved, V, Turn,
				kRestPosCm, kRestSpeedCmS, kMaxTurnDeg));
			return;
		}
	}
	if (!Rail.Body->IsSimulatingPhysics())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RailBlockSimulatingAtStart: the railed block is not a body the "
				 "world physics moves when play begins"));
		return;
	}
	if (!Twin.Body->IsSimulatingPhysics())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("TwinBlockSimulatingAtStart: the twin block is not a body the world "
				 "physics moves when play begins"));
		return;
	}

	RailSAtCp0 = AlongRail(Rail.Actor->GetActorLocation());
	ResetWindow(Rail);
	ResetWindow(Twin);
	Phase = EPhase::DrivingIn;
}

void AShovedBlockRailFunctionalTest::GradeCp1(double Now)
{
	LogCalib(1, Now);

	const FVector RP = Rail.Actor->GetActorLocation();
	const double Advance = AlongRail(RP) - RailSAtCp0;
	if (Advance < kMinAdvanceCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailAdvancesOnFirstShove: the railed block travelled only %.1f cm "
				 "along the rail on the first shove (the level asks for %.0f)"),
			Advance, kMinAdvanceCm));
		return;
	}
	if (Rail.MaxOffLine > kMaxOffLineCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailStaysOnLineFirstShove: the railed block drifted %.1f cm off its "
				 "rail line during the first shove (the level allows %.0f)"),
			Rail.MaxOffLine, kMaxOffLineCm));
		return;
	}
	if (Rail.MaxOffHeight > kMaxOffHeightCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailKeepsHeightFirstShove: the railed block left its rail height by "
				 "%.1f cm during the first shove (the level allows %.0f)"),
			Rail.MaxOffHeight, kMaxOffHeightCm));
		return;
	}
	if (Rail.MaxTurnDeg > kMaxTurnDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailStaysSquareFirstShove: the railed block turned %.1f deg during "
				 "the first shove (the level allows %.0f)"),
			Rail.MaxTurnDeg, kMaxTurnDeg));
		return;
	}
	if (!Rail.Body->IsSimulatingPhysics())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RailSimulatingFirstShove: the railed block stopped being a body the "
				 "world physics moves during the first shove"));
		return;
	}
	if (Rail.MaxSpeed < kMinSpeedCmS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailCarriedByPhysicsFirstShove: the railed block's own physics "
				 "velocity peaked at %.1f cm/s on the first shove, so something other "
				 "than the world's physics is moving it (the level asks for %.0f)"),
			Rail.MaxSpeed, kMinSpeedCmS));
		return;
	}

	if (Rail.MaxUnexplained > kUnexplainedCmS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailMotionIsPhysicsFirstShove: the railed block covered ground its own physics "
				 "velocity cannot account for on the first shove "
				 "(%.0f cm/s of motion unexplained, and the level allows %.0f), so it "
				 "is being driven along a path rather than moved by the world"),
			Rail.MaxUnexplained, kUnexplainedCmS));
		return;
	}

	// CONTROL: also what certifies the push kept its off-axis, off-centre character.
	const double TwinOff = FMath::Abs(FVector::DotProduct(
		Twin.Actor->GetActorLocation() - Twin.StartLocation, RailRight));
	// Displacement is read at the sample because it does not wrap; the TURN is read
	// as the window MAXIMUM because it does. FQuat::AngularDistance returns the
	// shortest angle in [0,180], so a block that tumbles through several
	// revolutions can finish reading any angle at all -- measured 2026-08-17, the
	// same twin read 158 deg on one layout and 15 deg on another purely from where
	// the tumble happened to stop. The maximum is what actually witnesses that the
	// push was off-centre.
	const double TwinTurn = Twin.MaxTurnDeg;
	if (TwinOff < kTwinOff1Cm || TwinTurn < kTwinTurnDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TwinThrownClearFirstShove: the untouched twin ended %.1f cm off its "
				 "own line and turned at most %.1f deg on the first shove, so the push "
				 "was not "
				 "the off-axis, off-centre one this level delivers (expected at least "
				 "%.0f cm and %.0f deg)"),
			TwinOff, TwinTurn, kTwinOff1Cm, kTwinTurnDeg));
		return;
	}

	RailSAtCp1 = AlongRail(RP);
	ResetWindow(Rail);
	ResetWindow(Twin);
	Phase = EPhase::DrivingOut;
}

void AShovedBlockRailFunctionalTest::GradeCp2(double Now)
{
	LogCalib(2, Now);

	const FVector RP = Rail.Actor->GetActorLocation();
	const double Advance = AlongRail(RP) - RailSAtCp1;
	if (Advance < kMinAdvanceCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailAdvancesOnSecondShove: the railed block travelled only %.1f cm "
				 "further along the rail on the second shove (the level asks for %.0f "
				 "every time)"),
			Advance, kMinAdvanceCm));
		return;
	}
	if (Rail.MaxOffLine > kMaxOffLineCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailStaysOnLineSecondShove: the railed block drifted %.1f cm off its "
				 "rail line during the second shove, so the rail did not hold it a "
				 "second time (the level allows %.0f)"),
			Rail.MaxOffLine, kMaxOffLineCm));
		return;
	}
	if (Rail.MaxOffHeight > kMaxOffHeightCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailKeepsHeightSecondShove: the railed block left its rail height by "
				 "%.1f cm during the second shove (the level allows %.0f)"),
			Rail.MaxOffHeight, kMaxOffHeightCm));
		return;
	}
	if (Rail.MaxTurnDeg > kMaxTurnDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailStaysSquareSecondShove: the railed block turned %.1f deg during "
				 "the second shove (the level allows %.0f)"),
			Rail.MaxTurnDeg, kMaxTurnDeg));
		return;
	}
	if (!Rail.Body->IsSimulatingPhysics())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RailSimulatingSecondShove: the railed block stopped being a body the "
				 "world physics moves during the second shove"));
		return;
	}
	if (Rail.MaxSpeed < kMinSpeedCmS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailCarriedByPhysicsSecondShove: the railed block's own physics "
				 "velocity peaked at %.1f cm/s on the second shove (the level asks for "
				 "%.0f every time)"),
			Rail.MaxSpeed, kMinSpeedCmS));
		return;
	}

	if (Rail.MaxUnexplained > kUnexplainedCmS)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailMotionIsPhysicsSecondShove: the railed block covered ground its own physics "
				 "velocity cannot account for on the second shove "
				 "(%.0f cm/s of motion unexplained, and the level allows %.0f), so it "
				 "is being driven along a path rather than moved by the world"),
			Rail.MaxUnexplained, kUnexplainedCmS));
		return;
	}

	const double TwinOff = FMath::Abs(FVector::DotProduct(
		Twin.Actor->GetActorLocation() - Twin.StartLocation, RailRight));
	const double TwinTurn = Twin.MaxTurnDeg;  // window max: rotation wraps, see cp1
	if (TwinOff < kTwinOff2Cm || TwinTurn < kTwinTurnDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TwinThrownClearSecondShove: the untouched twin ended %.1f cm off its "
				 "own line and turned at most %.1f deg after the second shove "
				 "(expected at least %.0f cm and %.0f deg)"),
			TwinOff, TwinTurn, kTwinOff2Cm, kTwinTurnDeg));
		return;
	}

	// KNOCK both blocks the same way: +60 cm across the rail and +40 cm up. Each
	// block's recovery is judged against its OWN pre-knock offset, so neither "the
	// twin was already far away" nor "the twin was already on its mark" can
	// manufacture the control reading.
	RailPreKnockOffLine = FMath::Abs(OffRail(RP));
	TwinPreKnockOffLine = FMath::Abs(FVector::DotProduct(
		Twin.Actor->GetActorLocation() - Twin.StartLocation, RailRight));
	const FVector Knock = RailRight * kKnockOffCm + FVector::UpVector * kKnockUpCm;
	for (FRailBlockProbe* Probe : {&Rail, &Twin})
	{
		Probe->Actor->SetActorLocation(Probe->Actor->GetActorLocation() + Knock,
			false, nullptr, ETeleportType::TeleportPhysics);
	}
	KnockTime = Now;
	ResetWindow(Rail);   // also clears bHasPrev, so the teleport frame itself is
	ResetWindow(Twin);   // never read as unexplained motion
	Phase = EPhase::AwaitCp3;
}

void AShovedBlockRailFunctionalTest::GradeCp3(double Now)
{
	LogCalib(3, Now);

	const FVector RP = Rail.Actor->GetActorLocation();
	const double OffLine = FMath::Abs(OffRail(RP));
	if (OffLine > kRecoverCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailBackOnLine: the railed block is still %.1f cm off its rail line "
				 "after being lifted off it, so nothing is holding it to the rail (the "
				 "level asks for %.0f)"),
			OffLine, kRecoverCm));
		return;
	}
	const double OffHeight = FMath::Abs(RP.Z - Rail.StartLocation.Z);
	if (OffHeight > kRecoverCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailBackAtHeight: the railed block settled %.1f cm from its rail "
				 "height after being lifted off it (the level asks for %.0f)"),
			OffHeight, kRecoverCm));
		return;
	}
	const double Turn = TurnDegrees(Rail);
	if (Turn > kMaxTurnDeg)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("RailBackSquare: the railed block ended %.1f deg from its start "
				 "facing after being lifted off the rail (the level allows %.0f)"),
			Turn, kMaxTurnDeg));
		return;
	}
	if (!Rail.Body->IsSimulatingPhysics())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("RailStillSimulating: the railed block is no longer a body the world "
				 "physics moves after being lifted off the rail"));
		return;
	}

	// The control half of the tether leg: nothing may have pulled the twin back
	// toward its own line, so the knock's displacement must still be there.
	const double TwinOff = FMath::Abs(FVector::DotProduct(
		Twin.Actor->GetActorLocation() - Twin.StartLocation, RailRight));
	if (TwinOff < TwinPreKnockOffLine + kTwinStillOffCm)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("TwinStaysOffItsLine: the twin came back toward its own line after "
				 "the knock (%.1f cm off now against %.1f cm before it, so less than "
				 "the %.0f cm the knock added), which means the comparison block is "
				 "being held to something too"),
			TwinOff, TwinPreKnockOffLine, kTwinStillOffCm));
		return;
	}

	Phase = EPhase::Done;
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("the railed block tracked its rail on both shoves and returned to it "
			 "after being lifted off, while the twin was thrown clear"));
}
