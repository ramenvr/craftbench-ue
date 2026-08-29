// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimFunctionalTest.h"

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimTypes.h"

#include "AIController.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationData.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AISense_Sight.h"

namespace
{
	constexpr double MinPhaseTravel = 95.0;
	constexpr double MaxFrameStep = 34.0;
	constexpr double MinVisibleSpineDelta = 3.0;
	constexpr double MaxNeutralSpineDelta = 10.0;

	double RotationDeltaDegrees(const FQuat& A, const FQuat& B)
	{
		return FMath::RadiansToDegrees(A.AngularDistance(B));
	}
}

AGuardVisibleAimScenario::AGuardVisibleAimScenario()
{
	PrimaryActorTick.bCanEverTick = false;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	Tags.AddUnique(TEXT("GuardVisibleAim.Scenario"));
}

AGuardVisibleAimFunctionalTestBase::AGuardVisibleAimFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

AGuardVisibleAimLeftHighFunctionalTest::AGuardVisibleAimLeftHighFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("GuardVisibleAim.Scenario.LeftHigh");
}

AGuardVisibleAimRightLowFunctionalTest::AGuardVisibleAimRightLowFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("GuardVisibleAim.Scenario.RightLow");
}

AGuardVisibleAimAdmissionFunctionalTest::AGuardVisibleAimAdmissionFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("GuardVisibleAim.Scenario.Admission");
}

bool AGuardVisibleAimFunctionalTestBase::ResolveWorld(FString& OutDetail)
{
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), ScenarioTag, Found);
	if (Found.Num() != 1)
	{
		OutDetail = FString::Printf(TEXT("scenario_tag=%s count=%d"),
			*ScenarioTag.ToString(), Found.Num());
		return false;
	}
	Scenario = Cast<AGuardVisibleAimScenario>(Found[0]);
	if (!Scenario.IsValid() || Scenario->ScenarioId.IsNone()
		|| Scenario->ExpectedAnimClass == nullptr || Scenario->MainGuard == nullptr
		|| Scenario->ControlGuard == nullptr || Scenario->VisibleTarget == nullptr
		|| Scenario->OccludedDecoy == nullptr || Scenario->DecoyOccluder == nullptr
		|| Scenario->SwitchOccluder == nullptr || Scenario->MainGoal == nullptr
		|| Scenario->ControlGoal == nullptr)
	{
		OutDetail = TEXT("scenario has missing exact actor/class references");
		return false;
	}
	TSet<const UObject*> Unique;
	Unique.Add(Scenario->MainGuard.Get());
	Unique.Add(Scenario->ControlGuard.Get());
	Unique.Add(Scenario->VisibleTarget.Get());
	Unique.Add(Scenario->OccludedDecoy.Get());
	Unique.Add(Scenario->DecoyOccluder.Get());
	Unique.Add(Scenario->SwitchOccluder.Get());
	Unique.Add(Scenario->MainGoal.Get());
	Unique.Add(Scenario->ControlGoal.Get());
	if (Unique.Num() != 8)
	{
		OutDetail = TEXT("scenario identities are not eight distinct objects");
		return false;
	}
	for (AGuardVisibleAimCharacter* Guard :
		{Scenario->MainGuard.Get(), Scenario->ControlGuard.Get()})
	{
		const AGuardVisibleAimController* Controller = Guard
			? Cast<AGuardVisibleAimController>(Guard->GetController()) : nullptr;
		USkeletalMeshComponent* Mesh = Guard ? Guard->GetMesh() : nullptr;
		if (Controller == nullptr || Controller->GetSightPerception() == nullptr
			|| Mesh == nullptr || Mesh->GetAnimClass() != Scenario->ExpectedAnimClass.Get()
			|| Guard->bUseControllerRotationYaw
			|| !Guard->GetCharacterMovement()->bOrientRotationToMovement)
		{
			OutDetail = FString::Printf(
				TEXT("guard=%s controller=%s perception=%s anim=%s expected=%s controller_yaw=%d orient_movement=%d"),
				*GetNameSafe(Guard), *GetNameSafe(Controller),
				*GetNameSafe(Controller ? Controller->GetSightPerception() : nullptr),
				*GetPathNameSafe(Mesh ? Mesh->GetAnimClass() : nullptr),
				*GetPathNameSafe(Scenario->ExpectedAnimClass.Get()),
				Guard && Guard->bUseControllerRotationYaw ? 1 : 0,
				Guard && Guard->GetCharacterMovement()->bOrientRotationToMovement ? 1 : 0);
			return false;
		}
	}
	const UStaticMeshComponent* DecoyWall = Scenario->DecoyOccluder->BlockingBody;
	const UStaticMeshComponent* SwitchWall = Scenario->SwitchOccluder->BlockingBody;
	if (DecoyWall == nullptr || SwitchWall == nullptr
		|| DecoyWall->GetCollisionEnabled() != ECollisionEnabled::QueryAndPhysics
		|| SwitchWall->GetCollisionEnabled() != ECollisionEnabled::QueryAndPhysics
		|| DecoyWall->GetCollisionResponseToChannel(ECC_Visibility) != ECR_Block
		|| SwitchWall->GetCollisionResponseToChannel(ECC_Visibility) != ECR_Block)
	{
		OutDetail = TEXT("both task occluders must block Visibility with QueryAndPhysics");
		return false;
	}
	return true;
}

bool AGuardVisibleAimFunctionalTestBase::EnsureRuntimeNavigationReady(
	FString& OutDetail)
{
	UWorld* World = GetWorld();
	UNavigationSystemV1* Navigation = World
		? FNavigationSystem::GetCurrent<UNavigationSystemV1>(World) : nullptr;
	ARecastNavMesh* Recast = Navigation
		? Cast<ARecastNavMesh>(Navigation->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate)) : nullptr;
	TArray<ANavMeshBoundsVolume*> BoundsVolumes;
	if (World != nullptr)
	{
		for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
		{
			BoundsVolumes.Add(*It);
		}
	}
	const bool bDynamic = Recast != nullptr
		&& Recast->GetRuntimeGenerationMode()
			== ERuntimeGenerationType::Dynamic
		&& Recast->SupportsRuntimeGeneration();
	if (Navigation == nullptr || Recast == nullptr || BoundsVolumes.Num() != 1
		|| !bDynamic || Navigation->IsNavigationBuildingLocked())
	{
		OutDetail = FString::Printf(
			TEXT("exact dynamic navigation required nav=%s recast=%s bounds=%d mode=%d supports=%d locked=%d tiles=%d"),
			*GetNameSafe(Navigation), *GetNameSafe(Recast), BoundsVolumes.Num(),
			Recast ? static_cast<int32>(Recast->GetRuntimeGenerationMode()) : -1,
			Recast && Recast->SupportsRuntimeGeneration() ? 1 : 0,
			Navigation && Navigation->IsNavigationBuildingLocked() ? 1 : 0,
			Recast ? Recast->GetNumActiveTiles() : 0);
		return false;
	}
	if (Recast->GetNumActiveTiles() <= 0)
	{
		Navigation->OnNavigationBoundsUpdated(BoundsVolumes[0]);
		Navigation->Build();
		Recast = Cast<ARecastNavMesh>(Navigation->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate));
	}
	const int32 Tiles = Recast ? Recast->GetNumActiveTiles() : 0;
	const bool bBuilding = Navigation->IsNavigationBuildInProgress();
	const int32 Tasks = Navigation->GetNumRemainingBuildTasks();
	if (Recast == nullptr || Tiles <= 0 || bBuilding || Tasks != 0
		|| Navigation->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate) != Recast)
	{
		OutDetail = FString::Printf(
			TEXT("dynamic navigation build incomplete recast=%s tiles=%d building=%d tasks=%d"),
			*GetNameSafe(Recast), Tiles, bBuilding ? 1 : 0, Tasks);
		return false;
	}
	UE_LOG(LogTemp, Display,
		TEXT("GUARD-VISIBLE-AIM-NAV-RUNTIME PASS default=1 bounds=1 runtime_dynamic=1 runtime_supported=1 active_tiles=%d building=0 tasks=0"),
		Tiles);
	return true;
}

void AGuardVisibleAimFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	FString Detail;
	if (GetWorld() == nullptr || !EnsureRuntimeNavigationReady(Detail)
		|| !ResolveWorld(Detail))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: ") + Detail);
		return;
	}
	PrepareEpoch = GetWorld()->GetTimeSeconds();
	MainStart = LastMain = Scenario->MainGuard->GetActorLocation();
	ControlStart = LastControl = Scenario->ControlGuard->GetActorLocation();
	MoveSwitchOccluder(false);
	SetCheckpointSchedule({
		PrepareEpoch + 1.10,
		PrepareEpoch + 2.15,
		PrepareEpoch + 3.25,
	});
}

void AGuardVisibleAimFunctionalTestBase::StartTest()
{
	Super::StartTest();
	if (!IsRunning() || !Scenario.IsValid())
	{
		return;
	}
	AGuardVisibleAimController* MainController =
		Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController());
	AGuardVisibleAimController* ControlController =
		Cast<AGuardVisibleAimController>(Scenario->ControlGuard->GetController());
	if (MainController == nullptr || ControlController == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: exact AI controllers disappeared at StartTest"));
		return;
	}
	ControlController->DisableSightForControl();
	UNavigationSystemV1* Navigation =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	ARecastNavMesh* Recast = Navigation
		? Cast<ARecastNavMesh>(Navigation->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate)) : nullptr;
	auto ValidateRoute = [this, Navigation, Recast](
		AGuardVisibleAimCharacter* Guard, AActor* Goal,
		const TCHAR* RouteRole, double& OutLength, FString& OutDetail)
	{
		FNavLocation ProjectedStart;
		FNavLocation ProjectedGoal;
		const FVector Extent(160.0, 160.0, 300.0);
		const bool bStartProjected = Navigation && Recast && Guard
			&& Navigation->ProjectPointToNavigation(
				Guard->GetActorLocation(), ProjectedStart, Extent, Recast);
		const bool bGoalProjected = Navigation && Recast && Goal
			&& Navigation->ProjectPointToNavigation(
				Goal->GetActorLocation(), ProjectedGoal, Extent, Recast);
		UNavigationPath* Path = bStartProjected && bGoalProjected
			? UNavigationSystemV1::FindPathToLocationSynchronously(
				GetWorld(), ProjectedStart.Location, ProjectedGoal.Location, Guard)
			: nullptr;
		const bool bPathValid = Path && Path->IsValid() && !Path->IsPartial()
			&& Path->PathPoints.Num() >= 2 && Path->GetPathLength() > 100.0;
		OutLength = bPathValid ? Path->GetPathLength() : -1.0;
		if (!bStartProjected || !bGoalProjected || !bPathValid)
		{
			OutDetail = FString::Printf(
				TEXT("scenario=%s role=%s start=%s goal=%s start_projected=%d goal_projected=%d path_valid=%d partial=%d points=%d length=%.2f"),
				*Scenario->ScenarioId.ToString(), RouteRole,
				*GetNameSafe(Guard), *GetNameSafe(Goal),
				bStartProjected ? 1 : 0, bGoalProjected ? 1 : 0,
				bPathValid ? 1 : 0, Path && Path->IsPartial() ? 1 : 0,
				Path ? Path->PathPoints.Num() : 0, OutLength);
			return false;
		}
		return true;
	};
	double MainPathLength = -1.0;
	double ControlPathLength = -1.0;
	FString RouteDetail;
	if (!ValidateRoute(Scenario->MainGuard.Get(), Scenario->MainGoal.Get(),
			TEXT("main"), MainPathLength, RouteDetail)
		|| !ValidateRoute(Scenario->ControlGuard.Get(), Scenario->ControlGoal.Get(),
			TEXT("control"), ControlPathLength, RouteDetail))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: navigation route invalid ") + RouteDetail);
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("GUARD-VISIBLE-AIM-NAV-ROUTE PASS scenario=%s projected=4 paths=2 main_length=%.2f control_length=%.2f"),
		*Scenario->ScenarioId.ToString(), MainPathLength, ControlPathLength);
	const EPathFollowingRequestResult::Type MainMove = MainController->MoveToLocation(
		Scenario->MainGoal->GetActorLocation(), 70.0f, false, true, true, false,
		TSubclassOf<UNavigationQueryFilter>(), false);
	const EPathFollowingRequestResult::Type ControlMove = ControlController->MoveToLocation(
		Scenario->ControlGoal->GetActorLocation(), 70.0f, false, true, true, false,
		TSubclassOf<UNavigationQueryFilter>(), false);
	if (MainMove == EPathFollowingRequestResult::Failed
		|| ControlMove == EPathFollowingRequestResult::Failed)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(TEXT("HARNESS-PRECONDITION: movement requests failed main=%d control=%d"),
				static_cast<int32>(MainMove), static_cast<int32>(ControlMove)));
		return;
	}
}

void AGuardVisibleAimFunctionalTestBase::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!IsRunning() || !Scenario.IsValid())
	{
		return;
	}
	const FVector Main = Scenario->MainGuard->GetActorLocation();
	const FVector Control = Scenario->ControlGuard->GetActorLocation();
	MaxMainFrameStep = FMath::Max(MaxMainFrameStep,
		static_cast<double>(FVector::Dist2D(Main, LastMain)));
	MaxControlFrameStep = FMath::Max(MaxControlFrameStep,
		static_cast<double>(FVector::Dist2D(Control, LastControl)));
	bEverMovingMain |= Scenario->MainGuard->GetVelocity().Size2D() > 90.0f;
	bEverMovingControl |= Scenario->ControlGuard->GetVelocity().Size2D() > 90.0f;
	for (const AGuardVisibleAimCharacter* Guard :
		{Scenario->MainGuard.Get(), Scenario->ControlGuard.Get()})
	{
		FVector Velocity = Guard->GetVelocity();
		Velocity.Z = 0.0f;
		if (!Velocity.IsNearlyZero())
		{
			const double Error = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
				static_cast<double>(FVector::DotProduct(
					Guard->GetActorForwardVector().GetSafeNormal2D(),
					Velocity.GetSafeNormal2D())), -1.0, 1.0)));
			MaxActorFacingError = FMath::Max(MaxActorFacingError, Error);
		}
	}
	LastMain = Main;
	LastControl = Control;
	(void)DeltaSeconds;
}

bool AGuardVisibleAimFunctionalTestBase::CheckPerceivedIdentity(
	const bool bExpectedVisible, FString& OutDetail) const
{
	const AGuardVisibleAimController* Controller = Scenario.IsValid()
		? Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController()) : nullptr;
	TArray<AActor*> Current;
	TArray<AActor*> Known;
	if (Controller && Controller->GetSightPerception())
	{
		Controller->GetSightPerception()->GetCurrentlyPerceivedActors(
			UAISense_Sight::StaticClass(), Current);
		Controller->GetSightPerception()->GetKnownPerceivedActors(
			UAISense_Sight::StaticClass(), Known);
	}
	TArray<AActor*> CurrentTargets;
	TArray<AActor*> KnownTargets;
	for (AActor* Actor : Current)
	{
		if (Actor && Actor->ActorHasTag(GuardVisibleAim::TargetTag))
		{
			CurrentTargets.Add(Actor);
		}
	}
	for (AActor* Actor : Known)
	{
		if (Actor && Actor->ActorHasTag(GuardVisibleAim::TargetTag))
		{
			KnownTargets.Add(Actor);
		}
	}
	const bool bCurrentExact = bExpectedVisible
		? CurrentTargets.Num() == 1 && CurrentTargets[0] == Scenario->VisibleTarget
		: CurrentTargets.Num() == 0;
	const bool bKnownExact = bExpectedVisible
		? KnownTargets.Contains(Scenario->VisibleTarget.Get())
		: !KnownTargets.Contains(Scenario->VisibleTarget.Get());
	const bool bDecoyAbsent = !CurrentTargets.Contains(Scenario->OccludedDecoy.Get())
		&& !KnownTargets.Contains(Scenario->OccludedDecoy.Get());
	const bool bControllerExact = Controller && (bExpectedVisible
		? Controller->GetCurrentVisibleTarget() == Scenario->VisibleTarget
		: Controller->GetCurrentVisibleTarget() == nullptr);
	OutDetail = FString::Printf(
		TEXT("expected_visible=%d raw_current=%d raw_known=%d target_current=%d target_known=%d current_target=%s visible=%s decoy=%s revision=%d"),
		bExpectedVisible ? 1 : 0, Current.Num(), Known.Num(),
		CurrentTargets.Num(), KnownTargets.Num(),
		*GetNameSafe(Controller ? Controller->GetCurrentVisibleTarget() : nullptr),
		*GetNameSafe(Scenario->VisibleTarget), *GetNameSafe(Scenario->OccludedDecoy),
		Controller ? Controller->GetPerceptionRevision() : -1);
	return bCurrentExact && bKnownExact && bDecoyAbsent && bControllerExact;
}

bool AGuardVisibleAimFunctionalTestBase::CheckAimOverlay(
	const bool bExpectedActive, FString& OutDetail) const
{
	const USkeletalMeshComponent* MainMesh = Scenario->MainGuard->GetMesh();
	const USkeletalMeshComponent* ControlMesh = Scenario->ControlGuard->GetMesh();
	const UGuardVisibleAimAnimInstance* MainAnim = MainMesh
		? Cast<UGuardVisibleAimAnimInstance>(MainMesh->GetAnimInstance()) : nullptr;
	const UGuardVisibleAimAnimInstance* ControlAnim = ControlMesh
		? Cast<UGuardVisibleAimAnimInstance>(ControlMesh->GetAnimInstance()) : nullptr;
	const int32 MainSpine = MainMesh ? MainMesh->GetBoneIndex(TEXT("spine_03")) : INDEX_NONE;
	const int32 ControlSpine = ControlMesh
		? ControlMesh->GetBoneIndex(TEXT("spine_03")) : INDEX_NONE;
	const FQuat MainRotation = MainSpine != INDEX_NONE
		? MainMesh->GetBoneTransform(MainSpine).GetRotation() : FQuat::Identity;
	const FQuat ControlRotation = ControlSpine != INDEX_NONE
		? ControlMesh->GetBoneTransform(ControlSpine).GetRotation() : FQuat::Identity;
	const double SpineDelta = RotationDeltaDegrees(MainRotation, ControlRotation);
	const bool bState = MainAnim && ControlAnim && (bExpectedActive
		? MainAnim->PerceivedTarget == Scenario->VisibleTarget
			&& MainAnim->AimAlpha >= 0.95f
			&& MainAnim->AimYaw * Scenario->ExpectedYawSign >= 8.0f
			&& MainAnim->AimPitch * Scenario->ExpectedPitchSign >= 4.0f
		: MainAnim->PerceivedTarget == nullptr
			&& MainAnim->AimAlpha <= 0.05f
			&& FMath::Abs(MainAnim->AimYaw) <= 0.5f
			&& FMath::Abs(MainAnim->AimPitch) <= 0.5f);
	const bool bPose = MainSpine != INDEX_NONE && ControlSpine != INDEX_NONE
		&& (bExpectedActive ? SpineDelta >= MinVisibleSpineDelta
			: SpineDelta <= MaxNeutralSpineDelta);
	OutDetail = FString::Printf(
		TEXT("active=%d anim=%s control_anim=%s target=%s alpha=%.3f yaw=%.2f pitch=%.2f signs=(%.0f,%.0f) spine_delta=%.2f bones=(%d,%d)"),
		bExpectedActive ? 1 : 0, *GetNameSafe(MainAnim), *GetNameSafe(ControlAnim),
		*GetNameSafe(MainAnim ? MainAnim->PerceivedTarget.Get() : nullptr),
		MainAnim ? MainAnim->AimAlpha : -1.0f,
		MainAnim ? MainAnim->AimYaw : 999.0f,
		MainAnim ? MainAnim->AimPitch : 999.0f,
		Scenario->ExpectedYawSign, Scenario->ExpectedPitchSign,
		SpineDelta, MainSpine, ControlSpine);
	return bState && bPose;
}

bool AGuardVisibleAimFunctionalTestBase::CheckMovementPhase(
	const FVector& MainPhaseStart, const FVector& ControlPhaseStart,
	FString& OutDetail) const
{
	const double MainTravel = FVector::Dist2D(
		Scenario->MainGuard->GetActorLocation(), MainPhaseStart);
	const double ControlTravel = FVector::Dist2D(
		Scenario->ControlGuard->GetActorLocation(), ControlPhaseStart);
	const bool bWalking = Scenario->MainGuard->GetCharacterMovement()->IsWalking()
		&& Scenario->ControlGuard->GetCharacterMovement()->IsWalking();
	OutDetail = FString::Printf(
		TEXT("main_travel=%.2f control_travel=%.2f main_speed=%.2f control_speed=%.2f walking=%d frame_steps=(%.2f,%.2f) facing_error=%.2f ever_moving=(%d,%d)"),
		MainTravel, ControlTravel, Scenario->MainGuard->GetVelocity().Size2D(),
		Scenario->ControlGuard->GetVelocity().Size2D(), bWalking ? 1 : 0,
		MaxMainFrameStep, MaxControlFrameStep, MaxActorFacingError,
		bEverMovingMain ? 1 : 0, bEverMovingControl ? 1 : 0);
	return MainTravel >= MinPhaseTravel && ControlTravel >= MinPhaseTravel
		&& bWalking && bEverMovingMain && bEverMovingControl
		&& MaxMainFrameStep <= MaxFrameStep && MaxControlFrameStep <= MaxFrameStep
		&& MaxActorFacingError <= 40.0;
}

void AGuardVisibleAimFunctionalTestBase::MoveSwitchOccluder(const bool bBlocked)
{
	Scenario->SwitchOccluder->SetActorLocation(
		bBlocked ? Scenario->SwitchBlockedLocation : Scenario->SwitchOpenLocation,
		false, nullptr, ETeleportType::TeleportPhysics);
	if (AGuardVisibleAimController* Controller =
		Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController()))
	{
		Controller->GetSightPerception()->RequestStimuliListenerUpdate();
	}
}

void AGuardVisibleAimFunctionalTestBase::FailGate(
	const TCHAR* Gate, const int32 CheckpointIndex,
	const double TimeSeconds, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("GATE[%s]: cp=%d world=%.3f %s"), Gate, CheckpointIndex,
		TimeSeconds, *Detail));
}

void AGuardVisibleAimFunctionalTestBase::EmitTelemetry(
	const int32 CheckpointIndex, const double TimeSeconds) const
{
	const AGuardVisibleAimController* Controller = Scenario.IsValid()
		? Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController()) : nullptr;
	const UGuardVisibleAimAnimInstance* Anim = Scenario.IsValid()
		? Cast<UGuardVisibleAimAnimInstance>(
			Scenario->MainGuard->GetMesh()->GetAnimInstance()) : nullptr;
	UE_LOG(LogTemp, Display,
		TEXT("CB-GUARD-AIM scenario=%s cp=%d world=%.3f target=%s revision=%d alpha=%.3f yaw=%.2f pitch=%.2f main=%s control=%s"),
		Scenario.IsValid() ? *Scenario->ScenarioId.ToString() : TEXT("none"),
		CheckpointIndex, TimeSeconds,
		*GetNameSafe(Controller ? Controller->GetCurrentVisibleTarget() : nullptr),
		Controller ? Controller->GetPerceptionRevision() : -1,
		Anim ? Anim->AimAlpha : -1.0f, Anim ? Anim->AimYaw : 999.0f,
		Anim ? Anim->AimPitch : 999.0f,
		Scenario.IsValid() ? *Scenario->MainGuard->GetActorLocation().ToCompactString() : TEXT("none"),
		Scenario.IsValid() ? *Scenario->ControlGuard->GetActorLocation().ToCompactString() : TEXT("none"));
}

void AGuardVisibleAimFunctionalTestBase::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!IsRunning() || !Scenario.IsValid())
	{
		return;
	}
	EmitTelemetry(CheckpointIndex, TimeSeconds);
	FString PerceptionDetail;
	FString AimDetail;
	FString MovementDetail;
	if (CheckpointIndex == 0)
	{
		if (!CheckPerceivedIdentity(true, PerceptionDetail))
		{
			FailGate(TEXT("OnlySightPerceivedIdentityMayDriveAim"),
				CheckpointIndex, TimeSeconds, PerceptionDetail);
			return;
		}
		if (!CheckAimOverlay(true, AimDetail))
		{
			FailGate(TEXT("PerceivedTargetDrivesAdditiveAimOverlay"),
				CheckpointIndex, TimeSeconds, AimDetail);
			return;
		}
		if (!CheckMovementPhase(MainStart, ControlStart, MovementDetail))
		{
			FailGate(TEXT("BaseLocomotionRemainsContinuous"),
				CheckpointIndex, TimeSeconds, MovementDetail);
			return;
		}
		MainAtBlock = Scenario->MainGuard->GetActorLocation();
		ControlAtBlock = Scenario->ControlGuard->GetActorLocation();
		if (const AGuardVisibleAimController* Controller =
			Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController()))
		{
			RevisionBeforeBlock = Controller->GetPerceptionRevision();
		}
		MoveSwitchOccluder(true);
		return;
	}
	if (CheckpointIndex == 1)
	{
		if (!CheckPerceivedIdentity(false, PerceptionDetail)
			|| !CheckAimOverlay(false, AimDetail))
		{
			FailGate(TEXT("OccludedTargetStopsDrivingAim"), CheckpointIndex,
				TimeSeconds, PerceptionDetail + TEXT(" ") + AimDetail);
			return;
		}
		const AGuardVisibleAimController* Controller =
			Cast<AGuardVisibleAimController>(Scenario->MainGuard->GetController());
		RevisionAfterForget = Controller ? Controller->GetPerceptionRevision() : -1;
		if (RevisionAfterForget <= RevisionBeforeBlock)
		{
			FailGate(TEXT("OccludedTargetStopsDrivingAim"), CheckpointIndex,
				TimeSeconds, TEXT("real perception revision did not advance across forget"));
			return;
		}
		if (!CheckMovementPhase(MainAtBlock, ControlAtBlock, MovementDetail))
		{
			FailGate(TEXT("BaseLocomotionRemainsContinuous"),
				CheckpointIndex, TimeSeconds, MovementDetail);
			return;
		}
		MainAtBlock = Scenario->MainGuard->GetActorLocation();
		ControlAtBlock = Scenario->ControlGuard->GetActorLocation();
		MoveSwitchOccluder(false);
		return;
	}
	if (!CheckPerceivedIdentity(true, PerceptionDetail)
		|| !CheckAimOverlay(true, AimDetail))
	{
		FailGate(TEXT("ReappearingTargetIsReacquired"), CheckpointIndex,
			TimeSeconds, PerceptionDetail + TEXT(" ") + AimDetail);
		return;
	}
	if (!CheckMovementPhase(MainAtBlock, ControlAtBlock, MovementDetail))
	{
		FailGate(TEXT("BaseLocomotionRemainsContinuous"),
			CheckpointIndex, TimeSeconds, MovementDetail);
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("GUARD-VISIBLE-AIM-PASS OnlySightPerceivedIdentityMayDriveAim PerceivedTargetDrivesAdditiveAimOverlay OccludedTargetStopsDrivingAim ReappearingTargetIsReacquired BaseLocomotionRemainsContinuous scenario=%s revision_before=%d revision_after_forget=%d"),
		*Scenario->ScenarioId.ToString(), RevisionBeforeBlock, RevisionAfterForget);
	FinishTest(EFunctionalTestResult::Succeeded,
		TEXT("Guard aims only at the live sight target while locomotion continues"));
}
