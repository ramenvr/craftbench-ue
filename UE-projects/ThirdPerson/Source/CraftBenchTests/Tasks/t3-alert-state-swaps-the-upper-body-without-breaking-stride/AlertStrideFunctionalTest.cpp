// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideFunctionalTest.h"

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideTypes.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimLayerInterface.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StateTreeComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"

namespace
{
	constexpr double MinimumPoseDelta = 2.0;
	constexpr double MaximumRestoreRatio = 0.60;
	constexpr double MinimumVelocityRatio = 0.35;
	constexpr double MaximumFrameMultiplier = 4.0;
	constexpr double FrameSlack = 18.0;

	bool HasState(const TArray<FName>& States, const FName Name)
	{
		return States.Contains(Name);
	}

	double MaximumOf(const TArray<double>& Values)
	{
		double Result = 0.0;
		for (const double Value : Values)
		{
			Result = FMath::Max(Result, Value);
		}
		return Result;
	}
}

AAlertStrideFunctionalTestBase::AAlertStrideFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

AAlertStrideSlowFunctionalTest::AAlertStrideSlowFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	RequiredScenarioId = TEXT("SlowEarly");
}

AAlertStrideFastFunctionalTest::AAlertStrideFastFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	RequiredScenarioId = TEXT("FastLate");
}

AAlertStrideAdmissionFunctionalTest::AAlertStrideAdmissionFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	RequiredScenarioId = TEXT("Admission");
}

void AAlertStrideFunctionalTestBase::FailGate(
	const TCHAR* Gate, const FString& Detail) const
{
	const_cast<AAlertStrideFunctionalTestBase*>(this)->FinishTest(
		EFunctionalTestResult::Failed,
		FString::Printf(TEXT("%s: %s"), Gate, *Detail));
}

bool AAlertStrideFunctionalTestBase::ResolveScenario()
{
	UWorld* World = GetWorld();
	TArray<AAlertStrideScenario*> Matches;
	for (TActorIterator<AAlertStrideScenario> It(World); It; ++It)
	{
		if (It->ActorHasTag(TEXT("AlertStrideScenario"))
			&& It->ScenarioId == RequiredScenarioId)
		{
			Matches.Add(*It);
		}
	}
	if (Matches.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: scenario=%s count=%d expected=1"),
			*RequiredScenarioId.ToString(), Matches.Num()));
		return false;
	}
	Scenario = Matches[0];
	Subject = Scenario->Subject;
	Signal = Scenario->Signal;
	const bool bWorldFacts = Subject.IsValid() && Signal.IsValid()
		&& Scenario->WalkSpeed >= 100.0f && Scenario->WalkSpeed <= 600.0f
		&& !Scenario->TravelDirection.IsNearlyZero()
		&& Scenario->AlertDelay >= 0.55
		&& Scenario->ClearDelay >= Scenario->AlertDelay + 0.65
		&& Scenario->EndDelay >= Scenario->ClearDelay + 0.65;
	if (!bWorldFacts)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: scenario has incomplete or unsafe world facts"));
		return false;
	}
	if (Scenario->StateTree == nullptr
		|| Scenario->LayerInterfaceClass == nullptr
		|| Scenario->CalmLayerClass == nullptr
		|| Scenario->AlertLayerClass == nullptr)
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("one or more submitted behavior/layer assets did not resolve"));
		return false;
	}
	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	if (Mesh == nullptr || Mesh->GetSkeletalMeshAsset() == nullptr
		|| !Mesh->IsVisible() || Mesh->bHiddenInGame)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: scenario subject lacks a visible skeletal body"));
		return false;
	}
	if (Mesh->GetAnimClass() == nullptr)
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("submitted host animation class did not resolve"));
		return false;
	}
	return true;
}

bool AAlertStrideFunctionalTestBase::ReadPose(
	FVector& OutLeftFoot, FVector& OutRightFoot,
	FVector& OutHandRelativeToPelvis) const
{
	const USkeletalMeshComponent* Mesh = Subject.IsValid()
		? Subject->GetMesh() : nullptr;
	if (Mesh == nullptr || Mesh->GetBoneIndex(TEXT("foot_l")) == INDEX_NONE
		|| Mesh->GetBoneIndex(TEXT("foot_r")) == INDEX_NONE
		|| Mesh->GetBoneIndex(TEXT("hand_r")) == INDEX_NONE
		|| Mesh->GetBoneIndex(TEXT("pelvis")) == INDEX_NONE)
	{
		return false;
	}
	OutLeftFoot = Mesh->GetSocketTransform(
		TEXT("foot_l"), RTS_Component).GetLocation();
	OutRightFoot = Mesh->GetSocketTransform(
		TEXT("foot_r"), RTS_Component).GetLocation();
	const FVector Hand = Mesh->GetSocketTransform(
		TEXT("hand_r"), RTS_Component).GetLocation();
	const FVector Pelvis = Mesh->GetSocketTransform(
		TEXT("pelvis"), RTS_Component).GetLocation();
	OutHandRelativeToPelvis = Hand - Pelvis;
	return !OutLeftFoot.ContainsNaN() && !OutRightFoot.ContainsNaN()
		&& !OutHandRelativeToPelvis.ContainsNaN();
}

bool AAlertStrideFunctionalTestBase::ValidateStableRuntime(const TCHAR* Gate)
{
	USkeletalMeshComponent* Mesh = Subject.IsValid()
		? Subject->GetMesh() : nullptr;
	UAnimInstance* Current = Mesh ? Mesh->GetAnimInstance() : nullptr;
	if (Current == nullptr || Current != MainAnimInstance.Get())
	{
		FailGate(Gate, FString::Printf(
			TEXT("main AnimInstance identity changed expected=%s actual=%s"),
			*GetPathNameSafe(MainAnimInstance.Get()), *GetPathNameSafe(Current)));
		return false;
	}
	if (Current->GetCurrentActiveMontage() != nullptr)
	{
		FailGate(Gate, FString::Printf(TEXT("montage=%s must remain absent"),
			*GetPathNameSafe(Current->GetCurrentActiveMontage())));
		return false;
	}
	return true;
}

bool AAlertStrideFunctionalTestBase::ValidateWalking(
	const TCHAR* Gate, const double MinimumProgressFraction)
{
	if (!Subject.IsValid() || !Scenario.IsValid())
	{
		return false;
	}
	const FVector Direction = Scenario->TravelDirection.GetSafeNormal2D();
	const double Progress = FVector::DotProduct(
		Subject->GetActorLocation() - StartLocation, Direction);
	const double Elapsed = GetWorld()->GetTimeSeconds() - EpochSeconds;
	const double Expected = Scenario->WalkSpeed * Elapsed * MinimumProgressFraction;
	const UCharacterMovementComponent* Movement = Subject->GetCharacterMovement();
	const double Speed = Movement ? Movement->Velocity.Size2D() : 0.0;
	if (Movement == nullptr || !Movement->IsMovingOnGround()
		|| Progress < Expected
		|| Speed < Scenario->WalkSpeed * MinimumVelocityRatio)
	{
		FailGate(Gate, FString::Printf(
			TEXT("walking progress=%.2f expected>=%.2f speed=%.2f configured=%.2f mode=%d"),
			Progress, Expected, Speed, Scenario->WalkSpeed,
			Movement ? static_cast<int32>(Movement->MovementMode) : -1));
		return false;
	}
	return true;
}

bool AAlertStrideFunctionalTestBase::ValidateLowerBodyWindow(
	const TCHAR* DetailLabel, const TArray<double>& Window) const
{
	if (BaselineLowerSteps.Num() < 4 || Window.Num() < 2)
	{
		FailGate(TEXT("LowerBodyStrideRemainsContinuous"), FString::Printf(
			TEXT("%s insufficient live bone samples baseline=%d window=%d"),
			DetailLabel, BaselineLowerSteps.Num(), Window.Num()));
		return false;
	}
	const double BaselineMax = MaximumOf(BaselineLowerSteps);
	const double WindowMax = MaximumOf(Window);
	const double Allowed = FMath::Max(10.0, BaselineMax * 3.0 + 2.0);
	if (WindowMax > Allowed)
	{
		FailGate(TEXT("LowerBodyStrideRemainsContinuous"), FString::Printf(
			TEXT("%s lower-body frame step %.3f exceeded live baseline %.3f allowed %.3f"),
			DetailLabel, WindowMax, BaselineMax, Allowed));
		return false;
	}
	return true;
}

void AAlertStrideFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	if (GetWorld() == nullptr || !ResolveScenario())
	{
		return;
	}
	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	MainAnimInstance = Mesh ? Mesh->GetAnimInstance() : nullptr;
	if (!MainAnimInstance.IsValid())
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("submitted host animation graph produced no live AnimInstance"));
		return;
	}
	StartLocation = Subject->GetActorLocation();
	LastLocation = StartLocation;
	EpochSeconds = GetWorld()->GetTimeSeconds();
	if (!Subject->StartScenario(Scenario->StateTree, Signal.Get(),
		Scenario->WalkSpeed, Scenario->TravelDirection))
	{
		FailGate(TEXT("AlertStateBecomesActive"),
			TEXT("submitted behavior asset did not start in the real StateTree component"));
		return;
	}
	SetCheckpointSchedule({
		EpochSeconds + 0.30,
		EpochSeconds + Scenario->AlertDelay,
		EpochSeconds + Scenario->AlertDelay + 0.38,
		EpochSeconds + Scenario->ClearDelay,
		EpochSeconds + Scenario->ClearDelay + 0.38,
		EpochSeconds + Scenario->EndDelay,
	});
}

void AAlertStrideFunctionalTestBase::CleanUp()
{
	if (Subject.IsValid())
	{
		Subject->StopScenario();
	}
	Super::CleanUp();
}

void AAlertStrideFunctionalTestBase::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!IsRunning() || !Subject.IsValid() || !Scenario.IsValid())
	{
		return;
	}
	const FVector CurrentLocation = Subject->GetActorLocation();
	const double ActorStep = FVector::Dist2D(CurrentLocation, LastLocation);
	LastLocation = CurrentLocation;
	MaxActorFrameStep = FMath::Max(MaxActorFrameStep, ActorStep);
	const double AllowedActorStep =
		Scenario->WalkSpeed / 60.0 * MaximumFrameMultiplier + FrameSlack;
	if (ActorStep > AllowedActorStep)
	{
		FailGate(TEXT("LowerBodyStrideRemainsContinuous"), FString::Printf(
			TEXT("actor frame step %.2f exceeded %.2f; teleport/direct transform is not walking"),
			ActorStep, AllowedActorStep));
		return;
	}
	if (!ValidateStableRuntime(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer")))
	{
		return;
	}
	FVector Left;
	FVector Right;
	FVector Hand;
	if (!ReadPose(Left, Right, Hand))
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("live evaluated Manny bone telemetry is unavailable"));
		return;
	}
	if (bHavePoseSample)
	{
		const double LowerStep = FMath::Max(
			FVector::Dist(Left, LastLeftFoot),
			FVector::Dist(Right, LastRightFoot));
		if (!bAlertRequested)
		{
			BaselineLowerSteps.Add(LowerStep);
		}
		else if (!bClearRequested)
		{
			AlertTransitionLowerSteps.Add(LowerStep);
		}
		else
		{
			ClearTransitionLowerSteps.Add(LowerStep);
		}
	}
	LastLeftFoot = Left;
	LastRightFoot = Right;
	bHavePoseSample = true;
}

void AAlertStrideFunctionalTestBase::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!Scenario.IsValid() || !Subject.IsValid() || !Signal.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: pinned scenario identity changed"));
		return;
	}
	if (!MainAnimInstance.IsValid())
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("submitted main AnimInstance was destroyed during the run"));
		return;
	}
	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	const TArray<FName> States = Subject->GetEngineActiveStateNames();
	UAnimInstance* CalmLayer = Mesh
		? Mesh->GetLinkedAnimLayerInstanceByClass(Scenario->CalmLayerClass) : nullptr;
	UAnimInstance* AlertLayer = Mesh
		? Mesh->GetLinkedAnimLayerInstanceByClass(Scenario->AlertLayerClass) : nullptr;
	FVector Left;
	FVector Right;
	FVector Hand;
	if (!ReadPose(Left, Right, Hand))
	{
		FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
			TEXT("checkpoint pose telemetry is unavailable"));
		return;
	}
	const double Progress = FVector::DotProduct(
		Subject->GetActorLocation() - StartLocation,
		Scenario->TravelDirection.GetSafeNormal2D());
	UE_LOG(LogTemp, Display,
		TEXT("[CB-ALERT-STRIDE] scenario=%s cp=%d t=%.3f alert=%d revision=%d states=%s main=%s calm_layer=%s alert_layer=%s progress=%.2f velocity=%.2f lower_base_max=%.3f lower_alert_max=%.3f lower_clear_max=%.3f actor_step_max=%.3f hand=%s"),
		*Scenario->ScenarioId.ToString(), CheckpointIndex, TimeSeconds,
		Signal->IsAlertActive() ? 1 : 0, Signal->Revision,
		*FString::JoinBy(States, TEXT(","), [](const FName Name)
		{
			return Name.ToString();
		}),
		*GetPathNameSafe(MainAnimInstance.Get()), *GetPathNameSafe(CalmLayer),
		*GetPathNameSafe(AlertLayer), Progress, Subject->GetVelocity().Size2D(),
		MaximumOf(BaselineLowerSteps), MaximumOf(AlertTransitionLowerSteps),
		MaximumOf(ClearTransitionLowerSteps), MaxActorFrameStep,
		*Hand.ToCompactString());

	if (!ValidateStableRuntime(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer")))
	{
		return;
	}
	switch (CheckpointIndex)
	{
	case 0:
		if (!HasState(States, TEXT("Calm")) || HasState(States, TEXT("Alert")))
		{
			FailGate(TEXT("AlertStateBecomesActive"), FString::Printf(
				TEXT("before alarm engine states=%s expected Calm without Alert"),
				*FString::JoinBy(States, TEXT(","), [](const FName Name)
				{
					return Name.ToString();
				})));
			return;
		}
		if (CalmLayer == nullptr || AlertLayer != nullptr)
		{
			FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
				TEXT("calm engine linked-layer instance must be active before alert"));
			return;
		}
		ValidateWalking(TEXT("LowerBodyStrideRemainsContinuous"), 0.25);
		break;
	case 1:
		CalmHandRelative = Hand;
		Signal->SetAlertActive(true);
		bAlertRequested = true;
		break;
	case 2:
		if (!HasState(States, TEXT("Alert")) || HasState(States, TEXT("Calm")))
		{
			FailGate(TEXT("AlertStateBecomesActive"), FString::Printf(
				TEXT("after alarm engine states=%s expected Alert without Calm"),
				*FString::JoinBy(States, TEXT(","), [](const FName Name)
				{
					return Name.ToString();
				})));
			return;
		}
		AlertHandRelative = Hand;
		if (AlertLayer == nullptr || CalmLayer != nullptr
			|| FVector::Dist(AlertHandRelative, CalmHandRelative) < MinimumPoseDelta)
		{
			FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"), FString::Printf(
				TEXT("linked alert instance calm=%s alert=%s upper_pose_delta=%.3f"),
				*GetPathNameSafe(CalmLayer), *GetPathNameSafe(AlertLayer),
				FVector::Dist(AlertHandRelative, CalmHandRelative)));
			return;
		}
		if (!ValidateLowerBodyWindow(TEXT("alert swap"), AlertTransitionLowerSteps)
			|| !ValidateWalking(TEXT("LowerBodyStrideRemainsContinuous"), 0.40))
		{
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("GATE[AlertStateBecomesActive]=PASS scenario=%s state=Alert"),
			*Scenario->ScenarioId.ToString());
		UE_LOG(LogTemp, Display,
			TEXT("GATE[BehaviorStateLinksAndDrivesDeclaredLayer]=PASS scenario=%s alert_layer=%s pose_delta=%.3f"),
			*Scenario->ScenarioId.ToString(), *GetPathNameSafe(AlertLayer),
			FVector::Dist(AlertHandRelative, CalmHandRelative));
		UE_LOG(LogTemp, Display,
			TEXT("GATE[LowerBodyStrideRemainsContinuous]=PASS scenario=%s phase=alert"),
			*Scenario->ScenarioId.ToString());
		break;
	case 3:
		if (!HasState(States, TEXT("Alert")) || AlertLayer == nullptr)
		{
			FailGate(TEXT("BehaviorStateLinksAndDrivesDeclaredLayer"),
				TEXT("alert state/layer did not persist until the world-authored clear time"));
			return;
		}
		Signal->SetAlertActive(false);
		bClearRequested = true;
		break;
	case 4:
	{
		const double AlertDelta = FVector::Dist(
			AlertHandRelative, CalmHandRelative);
		const double RestoreDelta = FVector::Dist(Hand, CalmHandRelative);
		if (!HasState(States, TEXT("Calm")) || HasState(States, TEXT("Alert"))
			|| CalmLayer == nullptr || AlertLayer != nullptr
			|| RestoreDelta > FMath::Max(1.5, AlertDelta * MaximumRestoreRatio))
		{
			FailGate(TEXT("ClearRestoresOriginalLayerWithoutRestart"), FString::Printf(
				TEXT("states=%s calm=%s alert=%s restore_delta=%.3f alert_delta=%.3f"),
				*FString::JoinBy(States, TEXT(","), [](const FName Name)
				{
					return Name.ToString();
				}), *GetPathNameSafe(CalmLayer), *GetPathNameSafe(AlertLayer),
				RestoreDelta, AlertDelta));
			return;
		}
		if (!ValidateLowerBodyWindow(TEXT("clear swap"), ClearTransitionLowerSteps)
			|| !ValidateWalking(TEXT("LowerBodyStrideRemainsContinuous"), 0.45))
		{
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("GATE[ClearRestoresOriginalLayerWithoutRestart]=PASS scenario=%s main=%s restore_delta=%.3f"),
			*Scenario->ScenarioId.ToString(),
			*GetPathNameSafe(MainAnimInstance.Get()), RestoreDelta);
		break;
	}
	case 5:
		if (!ValidateWalking(TEXT("LowerBodyStrideRemainsContinuous"), 0.50))
		{
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("[CB-ALERT-STRIDE] PASS scenario=%s checkpoints=6 state_tree=1 linked_layer=1 pose=1 movement=1"),
			*Scenario->ScenarioId.ToString());
		break;
	default:
		break;
	}
}
