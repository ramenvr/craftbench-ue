// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/WorkerPlanFunctionalTest.h"

#include "Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/WorkerPlanStateTreeTypes.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/StateTreeAIComponent.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "NavMesh/RecastNavMesh.h"
#include "Navigation/PathFollowingComponent.h"
#include "StateTree.h"

namespace
{
	constexpr double StationaryToleranceUu = 12.0;
	constexpr double InitialProgressUu = 20.0;
	constexpr double ContinuedProgressUu = 45.0;
	constexpr double TeleportFrameUu = 90.0;
}

AWorkerPlanFunctionalTest::AWorkerPlanFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void AWorkerPlanFunctionalTest::FailGate(const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("%s: %s"), Gate, *Detail));
}

bool AWorkerPlanFunctionalTest::ResolveStaging()
{
	UWorld* World = GetWorld();
	TArray<AActor*> Subjects;
	TArray<AActor*> Signals;
	TArray<AActor*> Destinations;
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("WorkerPlanSubject"), Subjects);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("WorkerPlanSignal"), Signals);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("WorkerPlanDestination"), Destinations);
	if (Subjects.Num() != 1 || Signals.Num() != 1 || Destinations.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected subject/signal/destination=1/1/1 got=%d/%d/%d"),
			Subjects.Num(), Signals.Num(), Destinations.Num()));
		return false;
	}

	TArray<ARecastNavMesh*> RecastMeshes;
	for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
	{
		RecastMeshes.Add(*It);
	}
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	if (NavigationSystem == nullptr || RecastMeshes.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: expected navigation system and exact one real Recast nav data; nav_system=%d recast=%d"),
			NavigationSystem != nullptr ? 1 : 0, RecastMeshes.Num()));
		return false;
	}
	Subject = Cast<AWorkerPlanCharacter>(Subjects[0]);
	Signal = Cast<AWorkerPlanSignalActor>(Signals[0]);
	Destination = Destinations[0];
	Controller = Subject.IsValid()
		? Cast<AWorkerPlanAIController>(Subject->GetController())
		: nullptr;
	if (!Subject.IsValid() || !Signal.IsValid() || !Destination.IsValid()
		|| !Controller.IsValid() || ExpectedStateTree == nullptr
		|| !ExpectedStateTree->IsReadyToRun())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: exact worker classes, controller, and compiled StateTree are required"));
		return false;
	}

	ARecastNavMesh* ExactRecast = RecastMeshes[0];
	const bool bIsDefaultNavData = NavigationSystem->GetDefaultNavDataInstance(
		FNavigationSystem::DontCreate) == ExactRecast;
	const bool bHasValidNavmesh = ExactRecast->HasValidNavmesh();
	const FVector QueryExtent(200.0, 200.0, 300.0);
	FNavLocation ProjectedSubject;
	FNavLocation ProjectedDestination;
	const bool bSubjectProjects = NavigationSystem->ProjectPointToNavigation(
		Subject->GetActorLocation(), ProjectedSubject, QueryExtent, ExactRecast);
	const bool bDestinationProjects = NavigationSystem->ProjectPointToNavigation(
		Destination->GetActorLocation(), ProjectedDestination, QueryExtent, ExactRecast);
	UNavigationPath* InitialPath = bSubjectProjects && bDestinationProjects
		? UNavigationSystemV1::FindPathToLocationSynchronously(
			World, ProjectedSubject.Location, ProjectedDestination.Location, ExactRecast)
		: nullptr;
	InitialNavigationPathPoints = InitialPath != nullptr ? InitialPath->PathPoints.Num() : 0;
	const bool bInitialPathIsUsable = InitialPath != nullptr && InitialPath->IsValid()
		&& !InitialPath->IsPartial() && InitialNavigationPathPoints >= 2;
	const int32 GeneratorActiveTiles = ExactRecast->GetNumActiveTiles();
	if (!bIsDefaultNavData || !bHasValidNavmesh || !bSubjectProjects
		|| !bDestinationProjects || !bInitialPathIsUsable)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: exact serialized Recast must be default, valid, project both endpoints, and provide a complete path; default=%d valid=%d subject_projects=%d destination_projects=%d path_valid=%d path_points=%d generator_active_tiles=%d nav_data=%s"),
			bIsDefaultNavData ? 1 : 0, bHasValidNavmesh ? 1 : 0,
			bSubjectProjects ? 1 : 0, bDestinationProjects ? 1 : 0,
			bInitialPathIsUsable ? 1 : 0, InitialNavigationPathPoints,
			GeneratorActiveTiles, *ExactRecast->GetPathName()));
		return false;
	}
	RecastNavMesh = ExactRecast;
	UE_LOG(LogTemp, Display,
		TEXT("WORKER-PLAN-NAV-PREFLIGHT default=1 valid=1 subject_projects=1 destination_projects=1 path_valid=1 path_points=%d generator_active_tiles=%d nav_data=%s"),
		InitialNavigationPathPoints, GeneratorActiveTiles, *ExactRecast->GetPathName());

	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	if (Mesh == nullptr || Mesh->GetSkeletalMeshAsset() == nullptr
		|| !Mesh->IsVisible() || Mesh->bHiddenInGame)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: the worker must have one visible skeletal body"));
		return false;
	}
	return true;
}

void AWorkerPlanFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	if (GetWorld() == nullptr || !ResolveStaging())
	{
		return;
	}
	Signal->ClearSignal();
	if (!Controller->ConfigureStateTree(ExpectedStateTree))
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: failed to start the exact compiled StateTree"));
		return;
	}
	StartLocation = Subject->GetActorLocation();
	LastTickLocation = StartLocation;
	SetCheckpointSchedule({0.50, 0.80, 1.35, 1.80, 2.50, 3.20});
}

void AWorkerPlanFunctionalTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!IsRunning() || !Subject.IsValid())
	{
		return;
	}
	MaxFrameStep = FMath::Max(MaxFrameStep,
		FVector::Dist2D(LastTickLocation, Subject->GetActorLocation()));
	LastTickLocation = Subject->GetActorLocation();
	if (MaxFrameStep > TeleportFrameUu)
	{
		FailGate(TEXT("ContinuesMoving"), FString::Printf(
			TEXT("one frame displaced %.2f uu; navigation cannot be replaced by a teleport"),
			MaxFrameStep));
	}
}

void AWorkerPlanFunctionalTest::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!Subject.IsValid() || !Controller.IsValid() || !Signal.IsValid()
		|| !Destination.IsValid() || !RecastNavMesh.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: staged actor identity changed during the run"));
		return;
	}

	const double FromStart = FVector::Dist2D(StartLocation, Subject->GetActorLocation());
	const UPathFollowingComponent* Path = Controller->GetPathFollowingComponent();
	const int32 PathStatus = Path ? static_cast<int32>(Path->GetStatus()) : -1;
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	const bool bHasValidNavmesh = RecastNavMesh->HasValidNavmesh();
	const bool bIsStillDefault = NavigationSystem != nullptr
		&& NavigationSystem->GetDefaultNavDataInstance(FNavigationSystem::DontCreate)
			== RecastNavMesh.Get();
	const FVector QueryExtent(200.0, 200.0, 300.0);
	FNavLocation ProjectedSubject;
	FNavLocation ProjectedDestination;
	const bool bSubjectProjects = NavigationSystem != nullptr
		&& NavigationSystem->ProjectPointToNavigation(
			Subject->GetActorLocation(), ProjectedSubject, QueryExtent, RecastNavMesh.Get());
	const bool bDestinationProjects = NavigationSystem != nullptr
		&& NavigationSystem->ProjectPointToNavigation(
			Destination->GetActorLocation(), ProjectedDestination, QueryExtent, RecastNavMesh.Get());
	const int32 GeneratorActiveTiles = RecastNavMesh->GetNumActiveTiles();
	if (!bHasValidNavmesh || !bIsStillDefault || !bSubjectProjects || !bDestinationProjects)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: serialized Recast health changed during the run; valid=%d default=%d subject_projects=%d destination_projects=%d generator_active_tiles=%d"),
			bHasValidNavmesh ? 1 : 0, bIsStillDefault ? 1 : 0,
			bSubjectProjects ? 1 : 0, bDestinationProjects ? 1 : 0,
			GeneratorActiveTiles));
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("WORKER-PLAN-TELEMETRY cp=%d t=%.3f signal=%d revision=%d distance=%.2f "
			 "condition_reads=%d passing_reads=%d nav_enter=%d nav_exit=%d move_result=%d path_status=%d "
			 "recast=%s navmesh_valid=1 endpoint_projection=1 initial_path_points=%d generator_active_tiles=%d"),
		CheckpointIndex, TimeSeconds, Signal->IsSignalActive() ? 1 : 0,
		Signal->PlanRevision, FromStart, Controller->SignalReadCount,
		Controller->PassingSignalReadCount, Controller->NavigationEnterCount,
		Controller->NavigationExitCount,
		static_cast<int32>(Controller->LastMoveRequestResult.GetValue()), PathStatus,
		*RecastNavMesh->GetPathName(), InitialNavigationPathPoints, GeneratorActiveTiles);

	switch (CheckpointIndex)
	{
	case 0:
		if (FromStart > StationaryToleranceUu)
		{
			FailGate(TEXT("SubjectStationaryBeforeSignal"), FString::Printf(
				TEXT("worker displaced %.2f uu before the separate signal"), FromStart));
			break;
		}
		if (Signal->IsSignalActive() || Controller->NavigationEnterCount != 0
			|| Controller->SignalReadCount <= 0)
		{
			FailGate(TEXT("IdleStateActiveBeforeSignal"), FString::Printf(
				TEXT("signal=%d distance=%.2f nav_enter=%d condition_reads=%d"),
				Signal->IsSignalActive() ? 1 : 0, FromStart,
				Controller->NavigationEnterCount, Controller->SignalReadCount));
		}
		break;
	case 1:
		Signal->PublishPlan(Destination.Get());
		bSignalPublished = true;
		break;
	case 2:
		if (!bSignalPublished || Controller->PassingSignalReadCount <= 0
			|| Controller->NavigationEnterCount != 1
			|| Controller->LastMoveRequestResult == EPathFollowingRequestResult::Failed
			|| FromStart < InitialProgressUu)
		{
			FailGate(TEXT("TransitionedAndRemainsActive"), FString::Printf(
				TEXT("published=%d pass_reads=%d nav_enter=%d result=%d distance=%.2f"),
				bSignalPublished ? 1 : 0, Controller->PassingSignalReadCount,
				Controller->NavigationEnterCount,
				static_cast<int32>(Controller->LastMoveRequestResult.GetValue()), FromStart));
			break;
		}
		LocationAtSignalClear = Subject->GetActorLocation();
		Signal->ClearSignal();
		bSignalCleared = true;
		break;
	case 3:
	case 4:
		if (!bSignalCleared || Signal->IsSignalActive()
			|| Controller->NavigationEnterCount != 1
			|| Controller->NavigationExitCount != 0)
		{
			FailGate(TEXT("TransitionedAndRemainsActive"), FString::Printf(
				TEXT("cleared=%d signal=%d nav_enter=%d nav_exit=%d"),
				bSignalCleared ? 1 : 0, Signal->IsSignalActive() ? 1 : 0,
				Controller->NavigationEnterCount, Controller->NavigationExitCount));
			break;
		}
		if (CheckpointIndex == 4)
		{
			const double AfterClear = FVector::Dist2D(
				LocationAtSignalClear, Subject->GetActorLocation());
			if (AfterClear < ContinuedProgressUu)
			{
				FailGate(TEXT("ContinuesMoving"), FString::Printf(
					TEXT("only %.2f uu after the signal cleared; expected continued navigation"),
					AfterClear));
			}
		}
		break;
	case 5:
		if (Controller->NavigationExitCount != 0
			|| FVector::Dist2D(LocationAtSignalClear, Subject->GetActorLocation())
				< ContinuedProgressUu)
		{
			FailGate(TEXT("ContinuesMoving"),
				TEXT("the persistent active plan did not survive through the sentinel"));
		}
		break;
	default:
		break;
	}
}
