// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-walkers-yield-and-still-arrive/BothWalkersYieldFunctionalTest.h"

#include "Tasks/t3-both-walkers-yield-and-still-arrive/WalkerYieldCharacter.h"

#include "AIController.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Blueprint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationData.h"
#include "NavigationPath.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "Navigation/PathFollowingComponent.h"
#include "Navigation/CrowdFollowingComponent.h"
#include "Navigation/CrowdManager.h"
#include "NavigationSystem.h"

namespace
{
	constexpr int32 PairAIndex = 0;
	constexpr int32 PairBIndex = 1;
	constexpr int32 SoloAIndex = 2;
	constexpr int32 SoloBIndex = 3;

	double ProgressAlong(
		const FVector& Location, const FVector& Start,
		const FVector& Direction, const double PathLength)
	{
		if (PathLength <= UE_SMALL_NUMBER)
		{
			return 0.0;
		}
		FVector Delta = Location - Start;
		Delta.Z = 0.0f;
		return FVector::DotProduct(Delta, Direction) / PathLength;
	}

	double LateralDistance(
		const FVector& Location, const FVector& Start,
		const FVector& Direction)
	{
		const FVector Delta = Location - Start;
		return FMath::Abs(
			static_cast<double>(Delta.X) * Direction.Y
			- static_cast<double>(Delta.Y) * Direction.X);
	}

	double SteeringAngleDegrees(
		const FVector& ActualVelocity, const FVector& RequestedVelocity)
	{
		const FVector Actual = FVector(
			ActualVelocity.X, ActualVelocity.Y, 0.0f).GetSafeNormal();
		const FVector Requested = FVector(
			RequestedVelocity.X, RequestedVelocity.Y, 0.0f).GetSafeNormal();
		if (Actual.IsNearlyZero() || Requested.IsNearlyZero())
		{
			return 0.0;
		}
		const double Dot = FMath::Clamp(
			static_cast<double>(FVector::DotProduct(Actual, Requested)), -1.0, 1.0);
		return FMath::RadiansToDegrees(FMath::Acos(Dot));
	}
}

AWalkerYieldScenarioActor::AWalkerYieldScenarioActor()
{
	PrimaryActorTick.bCanEverTick = false;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	Tags.AddUnique(TEXT("WalkerYieldScenario"));
}

ABothWalkersYieldFunctionalTestBase::ABothWalkersYieldFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

ABothWalkersYieldLayoutAFunctionalTest::
	ABothWalkersYieldLayoutAFunctionalTest(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("WalkerYieldScenario.LayoutA");
}

ABothWalkersYieldLayoutBFunctionalTest::
	ABothWalkersYieldLayoutBFunctionalTest(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("WalkerYieldScenario.LayoutB");
}

ABothWalkersYieldAdmissionFunctionalTest::
	ABothWalkersYieldAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	ScenarioTag = TEXT("WalkerYieldScenario.Admission");
}

bool ABothWalkersYieldFunctionalTestBase::ResolveOneByTag(
	const FName Tag, AActor*& OutActor, FString& OutDetail) const
{
	OutActor = nullptr;
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), Tag, Found);
	if (Found.Num() != 1 || Found[0] == nullptr)
	{
		OutDetail = FString::Printf(
			TEXT("tag=%s count=%d"), *Tag.ToString(), Found.Num());
		return false;
	}
	OutActor = Found[0];
	return true;
}

bool ABothWalkersYieldFunctionalTestBase::ConfigureTrackedWalker(
	FTrackedWalker& Tracked, const FName SubjectTag, const FName GoalTag,
	const float Speed, const float Radius, FString& OutDetail)
{
	AActor* SubjectActor = nullptr;
	AActor* GoalActor = nullptr;
	if (!ResolveOneByTag(SubjectTag, SubjectActor, OutDetail)
		|| !ResolveOneByTag(GoalTag, GoalActor, OutDetail))
	{
		return false;
	}

	AWalkerYieldCharacter* Character = Cast<AWalkerYieldCharacter>(SubjectActor);
	AAIController* Controller = Character
		? Cast<AAIController>(Character->GetController()) : nullptr;
	UCharacterMovementComponent* Movement = Character
		? Character->GetCharacterMovement() : nullptr;
	UCapsuleComponent* Capsule = Character
		? Character->GetCapsuleComponent() : nullptr;
	if (Character == nullptr || Controller == nullptr || Movement == nullptr
		|| Capsule == nullptr || GoalActor == nullptr)
	{
		OutDetail = FString::Printf(
			TEXT("subject=%s class=%s controller=%s movement=%s capsule=%s goal=%s"),
			*SubjectTag.ToString(), *GetNameSafe(SubjectActor),
			*GetNameSafe(Controller), *GetNameSafe(Movement),
			*GetNameSafe(Capsule), *GetNameSafe(GoalActor));
		return false;
	}
	if (Scenario->ExpectedWalkerClass == nullptr
		|| Character->GetClass() != Scenario->ExpectedWalkerClass
		|| Character->GetClass()->ClassGeneratedBy == nullptr
		|| !Character->GetClass()->ClassGeneratedBy->IsA<UBlueprint>())
	{
		OutDetail = FString::Printf(
			TEXT("subject=%s class=%s expected=%s generated_by=%s"),
			*SubjectTag.ToString(), *Character->GetClass()->GetPathName(),
			*GetPathNameSafe(Scenario->ExpectedWalkerClass),
			*GetPathNameSafe(Character->GetClass()->ClassGeneratedBy));
		return false;
	}

	Controller->StopMovement();
	Movement->StopMovementImmediately();
	Movement->MaxWalkSpeed = Speed;
	const float AuthoredHalfHeight = Capsule->GetUnscaledCapsuleHalfHeight();
	if (AuthoredHalfHeight < Radius)
	{
		OutDetail = FString::Printf(
			TEXT("subject=%s radius=%.2f authored_half_height=%.2f"),
			*SubjectTag.ToString(), Radius, AuthoredHalfHeight);
		return false;
	}
	Capsule->SetCapsuleSize(Radius, AuthoredHalfHeight, true);

	Tracked.SubjectTag = SubjectTag;
	Tracked.GoalTag = GoalTag;
	Tracked.Character = Character;
	Tracked.Controller = Controller;
	Tracked.Goal = GoalActor;
	Tracked.Start = Character->GetActorLocation();
	Tracked.GoalLocation = GoalActor->GetActorLocation();
	FVector Path = Tracked.GoalLocation - Tracked.Start;
	Path.Z = 0.0f;
	Tracked.PathLength = Path.Size();
	Tracked.PathDirection = Path.GetSafeNormal();
	Tracked.LastLocation = Tracked.Start;
	Tracked.Speed = Speed;
	Tracked.Radius = Radius;
	if (Tracked.PathLength < 800.0 || Tracked.PathDirection.IsNearlyZero())
	{
		OutDetail = FString::Printf(
			TEXT("subject=%s path_length=%.2f start=%s goal=%s"),
			*SubjectTag.ToString(), Tracked.PathLength,
			*Tracked.Start.ToCompactString(),
			*Tracked.GoalLocation.ToCompactString());
		return false;
	}
	return true;
}

bool ABothWalkersYieldFunctionalTestBase::ResolveScenarioAndWalkers()
{
	AActor* ScenarioActor = nullptr;
	FString Detail;
	if (!ResolveOneByTag(ScenarioTag, ScenarioActor, Detail))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: exact scenario identity is required; ") + Detail);
		return false;
	}
	Scenario = Cast<AWalkerYieldScenarioActor>(ScenarioActor);
	if (!Scenario.IsValid() || Scenario->ScenarioId.IsNone()
		|| Scenario->ExpectedWalkerClass == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: scenario class, id, and walker class are required"));
		return false;
	}

	Walkers.SetNum(4);
	const bool bConfigured =
		ConfigureTrackedWalker(Walkers[PairAIndex], Scenario->PairATag,
			Scenario->PairAGoalTag, Scenario->PairASpeed,
			Scenario->PairARadius, Detail)
		&& ConfigureTrackedWalker(Walkers[PairBIndex], Scenario->PairBTag,
			Scenario->PairBGoalTag, Scenario->PairBSpeed,
			Scenario->PairBRadius, Detail)
		&& ConfigureTrackedWalker(Walkers[SoloAIndex], Scenario->SoloATag,
			Scenario->SoloAGoalTag, Scenario->PairASpeed,
			Scenario->PairARadius, Detail)
		&& ConfigureTrackedWalker(Walkers[SoloBIndex], Scenario->SoloBTag,
			Scenario->SoloBGoalTag, Scenario->PairBSpeed,
			Scenario->PairBRadius, Detail);
	if (!bConfigured)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: four exact walkers and goals are required; ")
			+ Detail);
		return false;
	}

	TSet<const AAIController*> UniqueControllers;
	for (const FTrackedWalker& Tracked : Walkers)
	{
		UniqueControllers.Add(Tracked.Controller.Get());
	}
	if (UniqueControllers.Num() != 4)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(
				TEXT("HARNESS-PRECONDITION: four independent AI controllers are required; found=%d"),
				UniqueControllers.Num()));
		return false;
	}
	return true;
}

bool ABothWalkersYieldFunctionalTestBase::EnsureRuntimeNavigationReady()
{
	UWorld* World = GetWorld();
	UNavigationSystemV1* NavigationSystem = World
		? FNavigationSystem::GetCurrent<UNavigationSystemV1>(World) : nullptr;
	ARecastNavMesh* Recast = NavigationSystem
		? Cast<ARecastNavMesh>(NavigationSystem->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate))
		: nullptr;
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
	if (NavigationSystem == nullptr || Recast == nullptr
		|| BoundsVolumes.Num() != 1 || !bDynamic
		|| NavigationSystem->IsNavigationBuildingLocked())
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(
				TEXT("HARNESS-PRECONDITION: exact dynamic runtime navigation is required; nav=%s recast=%s bounds=%d mode=%d supports=%d locked=%d tiles=%d"),
				*GetNameSafe(NavigationSystem), *GetNameSafe(Recast),
				BoundsVolumes.Num(), Recast
					? static_cast<int32>(Recast->GetRuntimeGenerationMode()) : -1,
				Recast && Recast->SupportsRuntimeGeneration() ? 1 : 0,
				NavigationSystem
					&& NavigationSystem->IsNavigationBuildingLocked() ? 1 : 0,
				Recast ? Recast->GetNumActiveTiles() : 0));
		return false;
	}

	if (Recast->GetNumActiveTiles() <= 0)
	{
		NavigationSystem->OnNavigationBoundsUpdated(BoundsVolumes[0]);
		NavigationSystem->Build();
		Recast = Cast<ARecastNavMesh>(
			NavigationSystem->GetDefaultNavDataInstance(
				FNavigationSystem::DontCreate));
	}
	const int32 Tiles = Recast ? Recast->GetNumActiveTiles() : 0;
	const bool bBuilding = NavigationSystem->IsNavigationBuildInProgress();
	const int32 Tasks = NavigationSystem->GetNumRemainingBuildTasks();
	if (Recast == nullptr || Tiles <= 0 || bBuilding || Tasks != 0
		|| NavigationSystem->GetDefaultNavDataInstance(
			FNavigationSystem::DontCreate) != Recast)
	{
		FinishTest(EFunctionalTestResult::Error,
			FString::Printf(
				TEXT("HARNESS-PRECONDITION: dynamic runtime navigation build did not complete; recast=%s tiles=%d building=%d tasks=%d"),
				*GetNameSafe(Recast), Tiles, bBuilding ? 1 : 0, Tasks));
		return false;
	}
	UE_LOG(LogTemp, Display,
		TEXT("WALKER-YIELD-NAV-RUNTIME PASS default=1 bounds=1 runtime_dynamic=1 runtime_supported=1 active_tiles=%d building=0 tasks=0"),
		Tiles);
	return true;
}

void ABothWalkersYieldFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	AdmissionControl = FPlatformMisc::GetEnvironmentVariable(
		TEXT("CRAFTBENCH_WALKER_YIELD_CONTROL")).TrimStartAndEnd();
	if (!AdmissionControl.IsEmpty())
	{
		const bool bKnownControl = AdmissionControl == TEXT("no-avoidance")
			|| AdmissionControl == TEXT("freeze-one")
			|| AdmissionControl == TEXT("collision-disabled")
			|| AdmissionControl == TEXT("permanent-detour");
		if (GetClass()
				!= ABothWalkersYieldAdmissionFunctionalTest::StaticClass()
			|| !bKnownControl)
		{
			FinishTest(EFunctionalTestResult::Error,
				FString::Printf(
					TEXT("HARNESS-PRECONDITION: invalid admission control class=%s control=%s"),
					*GetClass()->GetPathName(), *AdmissionControl));
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-CONTROL armed=%s admission_only=1"),
			*AdmissionControl);
	}
	if (GetWorld() == nullptr || !EnsureRuntimeNavigationReady()
		|| !ResolveScenarioAndWalkers())
	{
		return;
	}
	PrepareEpochSeconds = GetWorld()->GetTimeSeconds();
	SetCheckpointSchedule({
		PrepareEpochSeconds + 0.25,
		PrepareEpochSeconds + 0.75,
		PrepareEpochSeconds + 1.35,
		PrepareEpochSeconds + 2.10,
		PrepareEpochSeconds + 2.80,
		PrepareEpochSeconds + 3.80,
		PrepareEpochSeconds + 5.20,
		PrepareEpochSeconds + 6.50,
	});
}

bool ABothWalkersYieldFunctionalTestBase::IssueMoveRequests(FString& OutDetail)
{
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	for (FTrackedWalker& Tracked : Walkers)
	{
		if (!Tracked.Controller.IsValid() || !Tracked.Goal.IsValid())
		{
			OutDetail = TEXT("controller or goal identity expired before request");
			return false;
		}
		const FNavAgentProperties& AgentProperties =
			Tracked.Controller->GetNavAgentPropertiesRef();
		FNavLocation ProjectedStart;
		FNavLocation ProjectedGoal;
		const bool bStartProjects = NavigationSystem != nullptr
			&& NavigationSystem->ProjectPointToNavigation(
				Tracked.Start, ProjectedStart, INVALID_NAVEXTENT,
				&AgentProperties);
		const bool bGoalProjects = NavigationSystem != nullptr
			&& NavigationSystem->ProjectPointToNavigation(
				Tracked.GoalLocation, ProjectedGoal, INVALID_NAVEXTENT,
				&AgentProperties);
		UNavigationPath* DiagnosticPath =
			UNavigationSystemV1::FindPathToLocationSynchronously(
				GetWorld(), Tracked.Start, Tracked.GoalLocation,
				Tracked.Controller.Get());
		const EPathFollowingRequestResult::Type MoveRequestResult =
			Tracked.Controller->MoveToLocation(
				Tracked.GoalLocation,
				Scenario->AcceptanceRadius,
				/*bStopOnOverlap=*/false,
				/*bUsePathfinding=*/true,
				/*bProjectDestinationToNavigation=*/true,
				/*bCanStrafe=*/false,
				TSubclassOf<UNavigationQueryFilter>(),
				/*bAllowPartialPath=*/false);
		Tracked.MoveRequestResult = static_cast<int32>(MoveRequestResult);
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-MOVE subject=%s result=%d start_projected=%d goal_projected=%d path_valid=%d path_partial=%d path_points=%d agent_radius=%.2f agent_height=%.2f start=%s goal=%s projected_start=%s projected_goal=%s"),
			*Tracked.SubjectTag.ToString(), Tracked.MoveRequestResult,
			bStartProjects ? 1 : 0, bGoalProjects ? 1 : 0,
			DiagnosticPath && DiagnosticPath->IsValid() ? 1 : 0,
			DiagnosticPath && DiagnosticPath->IsPartial() ? 1 : 0,
			DiagnosticPath ? DiagnosticPath->PathPoints.Num() : 0,
			AgentProperties.AgentRadius, AgentProperties.AgentHeight,
			*Tracked.Start.ToCompactString(),
			*Tracked.GoalLocation.ToCompactString(),
			*ProjectedStart.Location.ToCompactString(),
			*ProjectedGoal.Location.ToCompactString());
	}
	bMoveRequestsIssued = true;
	return true;
}

void ABothWalkersYieldFunctionalTestBase::StartTest()
{
	Super::StartTest();
	if (!IsRunning())
	{
		return;
	}
	FString Detail;
	if (!IssueMoveRequests(Detail))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: failed to issue four movement requests; ")
			+ Detail);
		return;
	}

	if (AdmissionControl == TEXT("no-avoidance"))
	{
		for (const int32 Index : { PairAIndex, PairBIndex })
		{
			AAIController* Controller = Walkers[Index].Controller.Get();
			UCrowdFollowingComponent* CrowdFollowing = Controller
				? Cast<UCrowdFollowingComponent>(
					Controller->GetPathFollowingComponent()) : nullptr;
			if (CrowdFollowing == nullptr)
			{
				FinishTest(EFunctionalTestResult::Error,
					TEXT("HARNESS-PRECONDITION: no-avoidance control requires two crowd followers"));
				return;
			}
			CrowdFollowing->SetCrowdObstacleAvoidance(false);
		}
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-CONTROL applied=no-avoidance pair_agents=2"));
	}
	else if (AdmissionControl == TEXT("freeze-one"))
	{
		UCharacterMovementComponent* Movement =
			Walkers[PairAIndex].Character.IsValid()
				? Walkers[PairAIndex].Character->GetCharacterMovement() : nullptr;
		if (Movement == nullptr)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: freeze-one control has no movement component"));
			return;
		}
		Movement->DisableMovement();
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-CONTROL applied=freeze-one pair=PairA"));
	}
	else if (AdmissionControl == TEXT("collision-disabled"))
	{
		for (const int32 Index : { PairAIndex, PairBIndex })
		{
			UCapsuleComponent* Capsule = Walkers[Index].Character.IsValid()
				? Walkers[Index].Character->GetCapsuleComponent() : nullptr;
			if (Capsule == nullptr)
			{
				FinishTest(EFunctionalTestResult::Error,
					TEXT("HARNESS-PRECONDITION: collision-disabled control has no capsule"));
				return;
			}
			Capsule->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
		}
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-CONTROL applied=collision-disabled pair_agents=2"));
	}
}

void ABothWalkersYieldFunctionalTestBase::SampleDense(const float DeltaSeconds)
{
	if (Walkers.Num() != 4 || GetWorld() == nullptr)
	{
		return;
	}
	UCrowdManager* CrowdManager = UCrowdManager::GetCurrent(GetWorld());
	for (FTrackedWalker& Tracked : Walkers)
	{
		AWalkerYieldCharacter* Character = Tracked.Character.Get();
		AAIController* Controller = Tracked.Controller.Get();
		UCharacterMovementComponent* Movement = Character
			? Character->GetCharacterMovement() : nullptr;
		if (Character == nullptr || Controller == nullptr || Movement == nullptr)
		{
			continue;
		}

		const FVector Location = Character->GetActorLocation();
		UPathFollowingComponent* PathFollowing =
			Controller->GetPathFollowingComponent();
		const FVector RequestedPathDirection = PathFollowing
			? PathFollowing->GetCurrentDirection() : FVector::ZeroVector;
		const double Progress = ProgressAlong(
			Location, Tracked.Start, Tracked.PathDirection, Tracked.PathLength);
		const double Advance = Progress - Tracked.LastProgress;
		Tracked.MaxProgress = FMath::Max(Tracked.MaxProgress, Progress);
		Tracked.MaxLateralDeviation = FMath::Max(
			Tracked.MaxLateralDeviation,
			LateralDistance(Location, Tracked.Start, Tracked.PathDirection));
		Tracked.MaxFrameStep = FMath::Max(
			Tracked.MaxFrameStep,
			static_cast<double>(FVector::Dist2D(Location, Tracked.LastLocation)));
		Tracked.CurrentSteeringAngle = SteeringAngleDegrees(
			Movement->Velocity, RequestedPathDirection);
		Tracked.MaxSteeringAngle = FMath::Max(
			Tracked.MaxSteeringAngle, Tracked.CurrentSteeringAngle);
		Tracked.bStayedWalking = Tracked.bStayedWalking
			&& Movement->MovementMode == MOVE_Walking
			&& FMath::Abs(Location.Z - Tracked.Start.Z) <= 8.0f;

		if (Controller->GetMoveStatus() == EPathFollowingStatus::Moving
			&& Advance <= 0.0002)
		{
			Tracked.CurrentStallSeconds += DeltaSeconds;
		}
		else
		{
			Tracked.CurrentStallSeconds = 0.0;
		}
		Tracked.MaxStallSeconds = FMath::Max(
			Tracked.MaxStallSeconds, Tracked.CurrentStallSeconds);

		UCrowdFollowingComponent* CrowdFollowing =
			Cast<UCrowdFollowingComponent>(PathFollowing);
		float CrowdRadius = 0.0f;
		float CrowdHalfHeight = 0.0f;
		if (CrowdFollowing != nullptr)
		{
			CrowdFollowing->GetCrowdAgentCollisions(
				CrowdRadius, CrowdHalfHeight);
		}
		const bool bRegistered = CrowdManager != nullptr
			&& CrowdFollowing != nullptr
			&& CrowdManager->IsAgentValid(CrowdFollowing)
			&& CrowdFollowing->IsCrowdSimulationActive()
			&& CrowdFollowing->IsCrowdObstacleAvoidanceActive();
		const FVector CrowdLocation = CrowdFollowing
			? CrowdFollowing->GetCrowdAgentLocation() : FVector::ZeroVector;
		const FVector CrowdVelocity = CrowdFollowing
			? CrowdFollowing->GetCrowdAgentVelocity() : FVector::ZeroVector;
		Tracked.bAvoidanceRegistrationSeen =
			Tracked.bAvoidanceRegistrationSeen || bRegistered;
		Tracked.bAvoidanceDataSeen = Tracked.bAvoidanceDataSeen
			|| (bRegistered && !CrowdLocation.ContainsNaN()
				&& !CrowdVelocity.ContainsNaN() && CrowdRadius > 0.0f
				&& CrowdHalfHeight > 0.0f
				&& FVector::Dist2D(CrowdLocation, Location) <= 20.0f);

		Tracked.LastProgress = Progress;
		Tracked.LastLocation = Location;
	}

	const FVector PairALocation = Walkers[PairAIndex].Character.IsValid()
		? Walkers[PairAIndex].Character->GetActorLocation() : FVector::ZeroVector;
	const FVector PairBLocation = Walkers[PairBIndex].Character.IsValid()
		? Walkers[PairBIndex].Character->GetActorLocation() : FVector::ZeroVector;
	const double CenterDistance = FVector::Dist2D(PairALocation, PairBLocation);
	const double Clearance = CenterDistance
		- Walkers[PairAIndex].Radius - Walkers[PairBIndex].Radius;
	ClosestPairCenterDistance = FMath::Min(ClosestPairCenterDistance, CenterDistance);
	MinPairClearance = FMath::Min(MinPairClearance, Clearance);
	if (CenterDistance <= ConflictObservationRadiusUu)
	{
		bConflictWindowObserved = true;
		if (Clearance >= PreContactClearanceUu)
		{
			MinPreContactClearance = FMath::Min(MinPreContactClearance, Clearance);
			Walkers[PairAIndex].MaxConflictSteeringAngle = FMath::Max(
				Walkers[PairAIndex].MaxConflictSteeringAngle,
				Walkers[PairAIndex].CurrentSteeringAngle);
			Walkers[PairBIndex].MaxConflictSteeringAngle = FMath::Max(
				Walkers[PairBIndex].MaxConflictSteeringAngle,
				Walkers[PairBIndex].CurrentSteeringAngle);
		}
	}
}

void ABothWalkersYieldFunctionalTestBase::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (IsRunning())
	{
		SampleDense(DeltaSeconds);
	}
}

bool ABothWalkersYieldFunctionalTestBase::IsCollisionHealthy(
	const FTrackedWalker& Tracked, FString& OutDetail) const
{
	const AWalkerYieldCharacter* Character = Tracked.Character.Get();
	const UCapsuleComponent* Capsule = Character
		? Character->GetCapsuleComponent() : nullptr;
	if (Capsule == nullptr
		|| Capsule->GetCollisionEnabled() != ECollisionEnabled::QueryAndPhysics
		|| Capsule->GetCollisionResponseToChannel(ECC_Pawn) != ECR_Block)
	{
		OutDetail = FString::Printf(
			TEXT("subject=%s collision=%d pawn_response=%d"),
			*Tracked.SubjectTag.ToString(),
			Capsule ? static_cast<int32>(Capsule->GetCollisionEnabled()) : -1,
			Capsule ? static_cast<int32>(
				Capsule->GetCollisionResponseToChannel(ECC_Pawn)) : -1);
		return false;
	}
	return true;
}

bool ABothWalkersYieldFunctionalTestBase::ArePinnedIdentitiesValid(
	FString& OutDetail) const
{
	if (!Scenario.IsValid() || Walkers.Num() != 4)
	{
		OutDetail = TEXT("scenario or walker set is absent");
		return false;
	}
	for (const FTrackedWalker& Tracked : Walkers)
	{
		if (!Tracked.Character.IsValid() || !Tracked.Controller.IsValid()
			|| !Tracked.Goal.IsValid()
			|| !Tracked.Character->ActorHasTag(Tracked.SubjectTag)
			|| !Tracked.Goal->ActorHasTag(Tracked.GoalTag)
			|| Tracked.Character->GetController() != Tracked.Controller.Get()
			|| Tracked.Character->GetClass() != Scenario->ExpectedWalkerClass)
		{
			OutDetail = FString::Printf(
				TEXT("subject=%s character=%s controller=%s goal=%s class=%s expected=%s"),
				*Tracked.SubjectTag.ToString(),
				*GetNameSafe(Tracked.Character.Get()),
				*GetNameSafe(Tracked.Controller.Get()),
				*GetNameSafe(Tracked.Goal.Get()),
				*GetNameSafe(Tracked.Character.IsValid()
					? Tracked.Character->GetClass() : nullptr),
				*GetNameSafe(Scenario->ExpectedWalkerClass));
			return false;
		}
	}
	return true;
}

void ABothWalkersYieldFunctionalTestBase::LogCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds) const
{
	if (Walkers.Num() != 4)
	{
		return;
	}
	const double AngleDeltaA = Walkers[PairAIndex].MaxConflictSteeringAngle
		- Walkers[SoloAIndex].MaxSteeringAngle;
	const double AngleDeltaB = Walkers[PairBIndex].MaxConflictSteeringAngle
		- Walkers[SoloBIndex].MaxSteeringAngle;
	const double LateralDeltaA = Walkers[PairAIndex].MaxLateralDeviation
		- Walkers[SoloAIndex].MaxLateralDeviation;
	const double LateralDeltaB = Walkers[PairBIndex].MaxLateralDeviation
		- Walkers[SoloBIndex].MaxLateralDeviation;
	UE_LOG(LogTemp, Display,
		TEXT("WALKER-YIELD-TELEMETRY scenario=%s cp=%d t=%.3f "
			 "progress=%.3f,%.3f,%.3f,%.3f conflict_angle=%.2f,%.2f "
			 "solo_angle=%.2f,%.2f angle_delta=%.2f,%.2f lateral_delta=%.2f,%.2f "
			 "crowd_registered=%d,%d crowd_data=%d,%d min_clearance=%.2f closest=%.2f "
			 "stall=%.3f,%.3f frame=%.2f,%.2f walking=%d,%d "
			 "move_results=%d,%d,%d,%d"),
		*Scenario->ScenarioId.ToString(), CheckpointIndex, TimeSeconds,
		Walkers[0].MaxProgress, Walkers[1].MaxProgress,
		Walkers[2].MaxProgress, Walkers[3].MaxProgress,
		Walkers[0].MaxConflictSteeringAngle,
		Walkers[1].MaxConflictSteeringAngle,
		Walkers[2].MaxSteeringAngle, Walkers[3].MaxSteeringAngle,
		AngleDeltaA, AngleDeltaB, LateralDeltaA, LateralDeltaB,
		Walkers[0].bAvoidanceRegistrationSeen ? 1 : 0,
		Walkers[1].bAvoidanceRegistrationSeen ? 1 : 0,
		Walkers[0].bAvoidanceDataSeen ? 1 : 0,
		Walkers[1].bAvoidanceDataSeen ? 1 : 0,
		MinPairClearance, ClosestPairCenterDistance,
		Walkers[0].MaxStallSeconds, Walkers[1].MaxStallSeconds,
		Walkers[0].MaxFrameStep, Walkers[1].MaxFrameStep,
		Walkers[0].bStayedWalking ? 1 : 0,
		Walkers[1].bStayedWalking ? 1 : 0,
		Walkers[0].MoveRequestResult, Walkers[1].MoveRequestResult,
		Walkers[2].MoveRequestResult, Walkers[3].MoveRequestResult);
}

void ABothWalkersYieldFunctionalTestBase::FailGate(
	const TCHAR* Gate, const double TimeSeconds, const int32 CheckpointIndex,
	const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(
			TEXT("%s: At world t=%.3fs checkpoint=%d; %s"),
			Gate, TimeSeconds, CheckpointIndex, *Detail));
}

void ABothWalkersYieldFunctionalTestBase::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	FString Detail;
	if (!ArePinnedIdentitiesValid(Detail))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: pinned scenario identity changed; ") + Detail);
		return;
	}
	LogCheckpoint(CheckpointIndex, TimeSeconds);

	const auto PairProgressHealthy = [this](const double Minimum)
	{
		return Walkers[PairAIndex].MaxProgress >= Minimum
			&& Walkers[PairBIndex].MaxProgress >= Minimum;
	};
	const auto MotionHealthy = [this]()
	{
		return Walkers[PairAIndex].bStayedWalking
			&& Walkers[PairBIndex].bStayedWalking
			&& Walkers[PairAIndex].MaxStallSeconds <= FrozenMaxStallSeconds
			&& Walkers[PairBIndex].MaxStallSeconds <= FrozenMaxStallSeconds
			&& Walkers[PairAIndex].MaxFrameStep <= FrozenMaxFrameStepUu
			&& Walkers[PairBIndex].MaxFrameStep <= FrozenMaxFrameStepUu;
	};

	if (CheckpointIndex == 0)
	{
		if (!bMoveRequestsIssued
			|| Walkers.ContainsByPredicate([](const FTrackedWalker& Tracked)
			{
				return Tracked.MoveRequestResult
					== static_cast<int32>(EPathFollowingRequestResult::Failed);
			}))
		{
			FailGate(TEXT("BothAgentsKeepForwardProgress"), TimeSeconds,
				CheckpointIndex,
				FString::Printf(
					TEXT("one or more controller requests failed results=%d,%d,%d,%d"),
					Walkers[0].MoveRequestResult,
					Walkers[1].MoveRequestResult,
					Walkers[2].MoveRequestResult,
					Walkers[3].MoveRequestResult));
		}
		return;
	}

	if ((CheckpointIndex == 1 && !PairProgressHealthy(0.04))
		|| (CheckpointIndex == 2 && !PairProgressHealthy(0.12)))
	{
		FailGate(TEXT("BothAgentsKeepForwardProgress"), TimeSeconds,
			CheckpointIndex,
			FString::Printf(TEXT("pair_progress=%.3f,%.3f"),
				Walkers[0].MaxProgress, Walkers[1].MaxProgress));
		return;
	}

	if (CheckpointIndex == 4)
	{
		const double AngleDeltaA = Walkers[PairAIndex].MaxConflictSteeringAngle
			- Walkers[SoloAIndex].MaxSteeringAngle;
		const double AngleDeltaB = Walkers[PairBIndex].MaxConflictSteeringAngle
			- Walkers[SoloBIndex].MaxSteeringAngle;
		const double LateralDeltaA = Walkers[PairAIndex].MaxLateralDeviation
			- Walkers[SoloAIndex].MaxLateralDeviation;
		const double LateralDeltaB = Walkers[PairBIndex].MaxLateralDeviation
			- Walkers[SoloBIndex].MaxLateralDeviation;
		const bool bConflictDriven = bConflictWindowObserved
			&& Walkers[0].bAvoidanceRegistrationSeen
			&& Walkers[1].bAvoidanceRegistrationSeen
			&& Walkers[0].bAvoidanceDataSeen && Walkers[1].bAvoidanceDataSeen
			&& Walkers[0].MaxConflictSteeringAngle
				>= FrozenMinSteeringAngleDeg
			&& Walkers[1].MaxConflictSteeringAngle
				>= FrozenMinSteeringAngleDeg
			&& AngleDeltaA >= FrozenPairOverSoloAngleDeg
			&& AngleDeltaB >= FrozenPairOverSoloAngleDeg
			&& LateralDeltaA >= FrozenPairOverSoloLateralUu
			&& LateralDeltaB >= FrozenPairOverSoloLateralUu;
		if (!bConflictDriven)
		{
			FailGate(TEXT("BothAgentsConflictDrivenSteering"), TimeSeconds,
				CheckpointIndex,
				FString::Printf(
					TEXT("conflict=%d crowd_registered=%d,%d crowd_data=%d,%d angle=%.2f,%.2f angle_delta=%.2f,%.2f lateral_delta=%.2f,%.2f"),
					bConflictWindowObserved ? 1 : 0,
					Walkers[0].bAvoidanceRegistrationSeen ? 1 : 0,
					Walkers[1].bAvoidanceRegistrationSeen ? 1 : 0,
					Walkers[0].bAvoidanceDataSeen ? 1 : 0,
					Walkers[1].bAvoidanceDataSeen ? 1 : 0,
					Walkers[0].MaxConflictSteeringAngle,
					Walkers[1].MaxConflictSteeringAngle,
					AngleDeltaA, AngleDeltaB, LateralDeltaA, LateralDeltaB));
			return;
		}
	}

	if ((CheckpointIndex == 4 || CheckpointIndex == 6
			|| CheckpointIndex == 7)
		&& (!MotionHealthy()
			|| (CheckpointIndex >= 6 && !PairProgressHealthy(0.65))))
	{
		FailGate(TEXT("BothAgentsKeepForwardProgress"), TimeSeconds,
			CheckpointIndex,
			FString::Printf(
				TEXT("progress=%.3f,%.3f stall=%.3f,%.3f frame=%.2f,%.2f walking=%d,%d"),
				Walkers[0].MaxProgress, Walkers[1].MaxProgress,
				Walkers[0].MaxStallSeconds, Walkers[1].MaxStallSeconds,
				Walkers[0].MaxFrameStep, Walkers[1].MaxFrameStep,
				Walkers[0].bStayedWalking ? 1 : 0,
				Walkers[1].bStayedWalking ? 1 : 0));
		return;
	}

	if (CheckpointIndex == 4 || CheckpointIndex == 7)
	{
		bool bCollisionHealthy = true;
		for (const FTrackedWalker& Tracked : Walkers)
		{
			if (!IsCollisionHealthy(Tracked, Detail))
			{
				bCollisionHealthy = false;
				break;
			}
		}
		if (!bCollisionHealthy || MinPairClearance < FrozenMinClearanceUu)
		{
			FailGate(TEXT("NoOverlapEnRoute"), TimeSeconds, CheckpointIndex,
				FString::Printf(TEXT("min_clearance=%.2f collision_detail=%s"),
					MinPairClearance, *Detail));
			return;
		}
	}

	if (CheckpointIndex == 4
		&& AdmissionControl == TEXT("permanent-detour")
		&& !bPermanentDetourInjected)
	{
		FTrackedWalker& PairA = Walkers[PairAIndex];
		AAIController* Controller = PairA.Controller.Get();
		const FVector SideDirection(
			-PairA.PathDirection.Y, PairA.PathDirection.X, 0.0f);
		const FVector DetourTarget = PairA.GoalLocation
			+ SideDirection * 600.0f;
		const EPathFollowingRequestResult::Type MoveResult = Controller
			? Controller->MoveToLocation(
				DetourTarget, Scenario->AcceptanceRadius,
				/*bStopOnOverlap=*/false, /*bUsePathfinding=*/true,
				/*bProjectDestinationToNavigation=*/true,
				/*bCanStrafe=*/false, TSubclassOf<UNavigationQueryFilter>(),
				/*bAllowPartialPath=*/false)
			: EPathFollowingRequestResult::Failed;
		if (MoveResult == EPathFollowingRequestResult::Failed)
		{
			FinishTest(EFunctionalTestResult::Error,
				TEXT("HARNESS-PRECONDITION: permanent-detour control request failed"));
			return;
		}
		bPermanentDetourInjected = true;
		UE_LOG(LogTemp, Display,
			TEXT("WALKER-YIELD-CONTROL applied=permanent-detour pair=PairA target=%s"),
			*DetourTarget.ToCompactString());
	}

	if (CheckpointIndex == 7)
	{
		TArray<double> GoalDistances;
		bool bAllArrived = true;
		for (const FTrackedWalker& Tracked : Walkers)
		{
			const double Distance = Tracked.Character.IsValid()
				? FVector::Dist2D(
					Tracked.Character->GetActorLocation(), Tracked.GoalLocation)
				: TNumericLimits<double>::Max();
			GoalDistances.Add(Distance);
			bAllArrived = bAllArrived && Distance <= FrozenArrivalBandUu;
		}
		if (!bAllArrived)
		{
			FailGate(TEXT("BothAgentsReachOwnGoals"), TimeSeconds,
				CheckpointIndex,
				FString::Printf(TEXT("goal_distance=%.2f,%.2f,%.2f,%.2f"),
					GoalDistances[0], GoalDistances[1],
					GoalDistances[2], GoalDistances[3]));
		}
	}
}

void ABothWalkersYieldFunctionalTestBase::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	for (FTrackedWalker& Tracked : Walkers)
	{
		if (Tracked.Controller.IsValid())
		{
			Tracked.Controller->StopMovement();
		}
	}
	Super::EndPlay(EndPlayReason);
}
