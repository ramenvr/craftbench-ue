// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseFunctionalTest.h"

#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseTypes.h"

#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/Tasks/BTTask_BlackboardBase.h"
#include "BehaviorTree/Tasks/BTTask_MoveTo.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationSystem.h"
#include "NavMesh/RecastNavMesh.h"

namespace
{
constexpr double InitialPatrolProgressUu = 45.0;
constexpr double ChaseClosingUu = 90.0;
constexpr double MarkerArrivalUu = 145.0;
constexpr double PostResetDepartureUu = 55.0;
constexpr double MaxPerFrameDisplacementUu = 48.0;
const FName AlertKey(TEXT("AlertActive"));
const FName LiveTargetKey(TEXT("LiveTarget"));
const FName PatrolPointKey(TEXT("PatrolPoint"));

int32 CountPopulatedNavMeshTiles(const ARecastNavMesh* RecastMesh)
{
	if (RecastMesh == nullptr || !RecastMesh->HasValidNavmesh())
	{
		return 0;
	}
	TArray<FNavTileRef> TileRefs;
	RecastMesh->GetAllNavMeshTiles(TileRefs);
	int32 PopulatedTiles = 0;
	for (const FNavTileRef TileRef : TileRefs)
	{
		TArray<FNavPoly> Polys;
		if (RecastMesh->GetPolysInTile(TileRef, Polys) && !Polys.IsEmpty())
		{
			++PopulatedTiles;
		}
	}
	return PopulatedTiles;
}
}

AGuardPatrolChaseFunctionalTest::AGuardPatrolChaseFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	PreparationTimeLimit = 15.0f;
}

void AGuardPatrolChaseFunctionalTest::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]: %s"), Gate, *Detail));
}

bool AGuardPatrolChaseFunctionalTest::ResolveProtectedWorld()
{
	UWorld* World = GetWorld();
	TArray<AActor*> Subjects;
	TArray<AActor*> Alerts;
	TArray<AActor*> Targets;
	TArray<AActor*> MarkersA;
	TArray<AActor*> MarkersB;
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("GuardPatrolSubject"), Subjects);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("GuardAlertSource"), Alerts);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("GuardChaseTarget"), Targets);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("GuardPatrolMarker.A"), MarkersA);
	UGameplayStatics::GetAllActorsWithTag(World, TEXT("GuardPatrolMarker.B"), MarkersB);
	if (Subjects.Num() != 1 || Alerts.Num() != 1 || Targets.Num() != 1 ||
		MarkersA.Num() != 1 || MarkersB.Num() != 1)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: exact support cardinality subject/alert/target/A/B=1/1/1/1/1 got=%d/%d/%d/%d/%d"),
			Subjects.Num(), Alerts.Num(), Targets.Num(), MarkersA.Num(), MarkersB.Num()));
		return false;
	}

	Subject = Cast<AGuardPatrolCharacter>(Subjects[0]);
	AlertSource = Cast<AGuardAlertSource>(Alerts[0]);
	Target = Cast<AGuardChaseTarget>(Targets[0]);
	MarkerA = Cast<AGuardPatrolMarker>(MarkersA[0]);
	MarkerB = Cast<AGuardPatrolMarker>(MarkersB[0]);
	Controller = Subject.IsValid()
		? Cast<AGuardPatrolAIController>(Subject->GetController()) : nullptr;
	if (!Subject.IsValid() || !AlertSource.IsValid() || !Target.IsValid() ||
		!MarkerA.IsValid() || !MarkerB.IsValid() || !Controller.IsValid() ||
		MarkerA.Get() == MarkerB.Get())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: protected support actors have wrong exact classes or identities"));
		return false;
	}

	USkeletalMeshComponent* Mesh = Subject->GetMesh();
	if (Mesh == nullptr || Mesh->GetSkeletalMeshAsset() == nullptr ||
		!Mesh->IsVisible() || Mesh->bHiddenInGame)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: protected guard must have one visible skeletal body"));
		return false;
	}

	return true;
}

bool AGuardPatrolChaseFunctionalTest::IsReady_Implementation()
{
	if (!Super::IsReady_Implementation() || GetWorld() == nullptr)
	{
		return false;
	}

	TArray<ARecastNavMesh*> RecastMeshes;
	for (TActorIterator<ARecastNavMesh> It(GetWorld()); It; ++It)
	{
		RecastMeshes.Add(*It);
	}
	UNavigationSystemV1* NavigationSystem =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	ARecastNavMesh* Candidate = RecastMeshes.Num() == 1 ? RecastMeshes[0] : nullptr;
	const bool bDefault = Candidate != nullptr && NavigationSystem != nullptr &&
		NavigationSystem->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) == Candidate;
	const int32 ActiveTiles = CountPopulatedNavMeshTiles(Candidate);
	const bool bBuildInProgress = NavigationSystem != nullptr &&
		NavigationSystem->IsNavigationBuildInProgress();
	const int32 RemainingTasks = NavigationSystem
		? NavigationSystem->GetNumRemainingBuildTasks() : -1;
	const int32 RuntimeGeneration = Candidate
		? static_cast<int32>(Candidate->GetRuntimeGenerationMode()) : -1;
	NavigationReadinessDetail = FString::Printf(
		TEXT("nav_system=%d recast=%d default=%d active_tiles=%d build_in_progress=%d remaining=%d runtime_generation=%d world_type=%d"),
		NavigationSystem ? 1 : 0, RecastMeshes.Num(), bDefault ? 1 : 0,
		ActiveTiles, bBuildInProgress ? 1 : 0, RemainingTasks,
		RuntimeGeneration, static_cast<int32>(GetWorld()->WorldType));

	bNavigationReady = NavigationSystem != nullptr && RecastMeshes.Num() == 1 &&
		bDefault && ActiveTiles > 0 && !bBuildInProgress && RemainingTasks == 0;
	if (ActiveTiles != LastLoggedNavigationTiles || bNavigationReady)
	{
		UE_LOG(LogTemp, Display, TEXT("GUARD-PATROL-NAV-READINESS ready=%d %s"),
			bNavigationReady ? 1 : 0, *NavigationReadinessDetail);
		LastLoggedNavigationTiles = ActiveTiles;
	}
	if (bNavigationReady)
	{
		RecastNavMesh = Candidate;
	}
	return bNavigationReady;
}

void AGuardPatrolChaseFunctionalTest::OnTimeout()
{
	if (!bNavigationReady)
	{
		FinishTest(EFunctionalTestResult::Error, FString::Printf(
			TEXT("HARNESS-PRECONDITION: protected map navigation did not become ready within %.1fs; %s"),
			PreparationTimeLimit, *NavigationReadinessDetail));
		return;
	}
	Super::OnTimeout();
}

bool AGuardPatrolChaseFunctionalTest::ActiveMoveUses(
	const FName KeyName, FString& OutDetail) const
{
	if (!Controller.IsValid())
	{
		OutDetail = TEXT("controller invalid");
		return false;
	}
	const UBehaviorTreeComponent* TreeComp =
		Controller->GetGuardBehaviorTreeComponent();
	const UBTTask_MoveTo* Move = TreeComp
		? Cast<UBTTask_MoveTo>(TreeComp->GetActiveNode()) : nullptr;
	const UPathFollowingComponent* Path = Controller->GetPathFollowingComponent();
	const FName ActiveKey = Move ? Move->GetSelectedBlackboardKey() : NAME_None;
	const int32 PathStatus = Path ? static_cast<int32>(Path->GetStatus()) : -1;
	OutDetail = FString::Printf(TEXT("tree=%s active=%s key=%s path_status=%d"),
		TreeComp && TreeComp->GetRootTree()
			? *TreeComp->GetRootTree()->GetPathName() : TEXT("null"),
		TreeComp && TreeComp->GetActiveNode()
			? *TreeComp->GetActiveNode()->GetClass()->GetPathName() : TEXT("null"),
		*ActiveKey.ToString(), PathStatus);
	return Move != nullptr && ActiveKey == KeyName && Path != nullptr &&
		Path->GetStatus() == EPathFollowingStatus::Moving;
}

void AGuardPatrolChaseFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	if (GetWorld() == nullptr || !ResolveProtectedWorld())
	{
		return;
	}

	AlertSource->ClearAlert();
	InitialSubjectLocation = Subject->GetActorLocation();
	LastSubjectLocation = InitialSubjectLocation;
	TargetOrigin = Target->GetActorLocation();
	SetCheckpointSchedule({0.55, 1.25, 1.40, 2.45, 2.55, 2.90, 5.00, 7.80, 9.00});
}

void AGuardPatrolChaseFunctionalTest::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!IsRunning() || !Subject.IsValid())
	{
		return;
	}

	const FVector SubjectLocation = Subject->GetActorLocation();
	MaxFrameStep = FMath::Max(MaxFrameStep,
		FVector::Dist2D(LastSubjectLocation, SubjectLocation));
	LastSubjectLocation = SubjectLocation;
	if (MaxFrameStep > MaxPerFrameDisplacementUu)
	{
		FailGate(TEXT("ChaseClosesDistance"), FString::Printf(
			TEXT("one frame displaced %.2f uu; path following cannot be replaced by teleport"),
			MaxFrameStep));
		return;
	}

	if (bAlertPublished && !bAlertCleared && Target.IsValid())
	{
		FVector Next = Target->GetActorLocation() + TargetVelocity * DeltaSeconds;
		const double OffsetY = Next.Y - TargetOrigin.Y;
		if (FMath::Abs(OffsetY) > 250.0)
		{
			TargetVelocity.Y *= -1.0;
			Next = Target->GetActorLocation() + TargetVelocity * DeltaSeconds;
		}
		Target->SetActorLocation(Next, true);
	}

	if (bAlertCleared && MarkerA.IsValid() && MarkerB.IsValid())
	{
		const double DistanceA = FVector::Dist2D(SubjectLocation, MarkerA->GetActorLocation());
		const double DistanceB = FVector::Dist2D(SubjectLocation, MarkerB->GetActorLocation());
		if (!bObservedPostResetArrival && FMath::Min(DistanceA, DistanceB) <= MarkerArrivalUu)
		{
			bObservedPostResetArrival = true;
			ReachedMarkerIndexAfterReset = DistanceA <= DistanceB ? 0 : 1;
			BestDistanceToPostResetOther = ReachedMarkerIndexAfterReset == 0
				? DistanceB : DistanceA;
		}
		else if (bObservedPostResetArrival)
		{
			const double DistanceToReached = ReachedMarkerIndexAfterReset == 0
				? DistanceA : DistanceB;
			const double DistanceToOther = ReachedMarkerIndexAfterReset == 0
				? DistanceB : DistanceA;
			bObservedPostResetDeparture |= DistanceToReached >
				MarkerArrivalUu + PostResetDepartureUu;
			BestDistanceToPostResetOther = FMath::Min(
				BestDistanceToPostResetOther, DistanceToOther);
		}
	}
}

void AGuardPatrolChaseFunctionalTest::EmitTelemetry(
	const int32 CheckpointIndex, const double TimeSeconds) const
{
	const UBehaviorTreeComponent* TreeComp = Controller.IsValid()
		? Controller->GetGuardBehaviorTreeComponent() : nullptr;
	const UBlackboardComponent* Blackboard = Controller.IsValid()
		? Controller->GetGuardBlackboardComponent() : nullptr;
	const UBTTask_BlackboardBase* ActiveTask = TreeComp
		? Cast<UBTTask_BlackboardBase>(TreeComp->GetActiveNode()) : nullptr;
	const UPathFollowingComponent* PathFollowing = Controller.IsValid()
		? Controller->GetPathFollowingComponent() : nullptr;
	const double SubjectTargetDistance = Subject.IsValid() && Target.IsValid()
		? FVector::Dist2D(Subject->GetActorLocation(), Target->GetActorLocation()) : -1.0;
	const double MarkerADistance = Subject.IsValid() && MarkerA.IsValid()
		? FVector::Dist2D(Subject->GetActorLocation(), MarkerA->GetActorLocation()) : -1.0;
	const double MarkerBDistance = Subject.IsValid() && MarkerB.IsValid()
		? FVector::Dist2D(Subject->GetActorLocation(), MarkerB->GetActorLocation()) : -1.0;
	const UObject* PatrolPoint = Blackboard
		? Blackboard->GetValueAsObject(PatrolPointKey) : nullptr;
	const AActor* PatrolPointActor = Cast<AActor>(PatrolPoint);
	const FVector PathTarget = PathFollowing
		? PathFollowing->GetCurrentTargetLocation() : FVector::ZeroVector;
	const FNavLocation CurrentNavLocation = PathFollowing
		? PathFollowing->GetCurrentNavLocation() : FNavLocation();
	const bool bPathReachedPatrolPoint = PathFollowing && PatrolPointActor &&
		PathFollowing->HasReached(
			*PatrolPointActor,
			EPathFollowingReachMode::OverlapAgentAndGoal,
			PathFollowing->GetAcceptanceRadius());
	UE_LOG(LogTemp, Display,
		TEXT("GUARD-PATROL-CHASE-TELEMETRY cp=%d t=%.3f alert=%d bb_alert=%d active=%s key=%s path_status=%d speed=%.2f patrol_point=%s move_goal=%s acceptance=%.2f has_reached=%d path_target=(%.2f,%.2f,%.2f) nav_location=(%.2f,%.2f,%.2f) subject_target=%.2f marker_a=%.2f marker_b=%.2f max_frame=%.2f arrived=%d departed=%d nav_tiles=%d"),
		CheckpointIndex, TimeSeconds,
		AlertSource.IsValid() && AlertSource->IsAlertActive() ? 1 : 0,
		Blackboard && Blackboard->GetValueAsBool(AlertKey) ? 1 : 0,
		TreeComp && TreeComp->GetActiveNode()
			? *TreeComp->GetActiveNode()->GetClass()->GetName() : TEXT("null"),
		ActiveTask ? *ActiveTask->GetSelectedBlackboardKey().ToString() : TEXT("None"),
		PathFollowing ? static_cast<int32>(PathFollowing->GetStatus()) : -1,
		Subject.IsValid() ? Subject->GetVelocity().Size2D() : -1.0,
		*GetPathNameSafe(PatrolPoint),
		*GetPathNameSafe(PathFollowing ? PathFollowing->GetMoveGoal() : nullptr),
		PathFollowing ? PathFollowing->GetAcceptanceRadius() : -1.0,
		bPathReachedPatrolPoint ? 1 : 0,
		PathTarget.X, PathTarget.Y, PathTarget.Z,
		CurrentNavLocation.Location.X, CurrentNavLocation.Location.Y,
		CurrentNavLocation.Location.Z, SubjectTargetDistance,
		MarkerADistance, MarkerBDistance, MaxFrameStep,
		bObservedPostResetArrival ? 1 : 0,
		bObservedPostResetDeparture ? 1 : 0,
		CountPopulatedNavMeshTiles(RecastNavMesh.Get()));
}

void AGuardPatrolChaseFunctionalTest::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!Subject.IsValid() || !Controller.IsValid() || !AlertSource.IsValid() ||
		!Target.IsValid() || !MarkerA.IsValid() || !MarkerB.IsValid() ||
		!RecastNavMesh.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: protected actor identity changed during run"));
		return;
	}
	EmitTelemetry(CheckpointIndex, TimeSeconds);

	UBehaviorTreeComponent* TreeComp = Controller->GetGuardBehaviorTreeComponent();
	UBlackboardComponent* Blackboard = Controller->GetGuardBlackboardComponent();
	FString ActiveDetail;
	const bool bExactTreeContract = ExpectedBehaviorTree != nullptr &&
		ExpectedBlackboard != nullptr && TreeComp != nullptr && Blackboard != nullptr &&
		TreeComp->GetRootTree() == ExpectedBehaviorTree &&
		ExpectedBehaviorTree->BlackboardAsset == ExpectedBlackboard &&
		Blackboard->GetBlackboardAsset() == ExpectedBlackboard &&
		Subject->DecisionTree == ExpectedBehaviorTree;

	switch (CheckpointIndex)
	{
	case 0:
		if (!bExactTreeContract || AlertSource->IsAlertActive() ||
			Blackboard->GetValueAsBool(AlertKey) ||
			Blackboard->GetValueAsObject(LiveTargetKey) != nullptr ||
			!ActiveMoveUses(PatrolPointKey, ActiveDetail))
		{
			FailGate(TEXT("PrioritySelectorAndDecoratorsAuthored"), FString::Printf(
				TEXT("exact_contract=%d alert=%d bb_alert=%d live_target=%s %s"),
				bExactTreeContract ? 1 : 0, AlertSource->IsAlertActive() ? 1 : 0,
				Blackboard && Blackboard->GetValueAsBool(AlertKey) ? 1 : 0,
				Blackboard && Blackboard->GetValueAsObject(LiveTargetKey)
					? *Blackboard->GetValueAsObject(LiveTargetKey)->GetPathName()
					: TEXT("null"), *ActiveDetail));
		}
		break;
	case 1:
		if (FVector::Dist2D(InitialSubjectLocation, Subject->GetActorLocation())
			< InitialPatrolProgressUu || !ActiveMoveUses(PatrolPointKey, ActiveDetail))
		{
			FailGate(TEXT("PrioritySelectorAndDecoratorsAuthored"), FString::Printf(
				TEXT("quiet patrol progress=%.2f %s"),
				FVector::Dist2D(InitialSubjectLocation, Subject->GetActorLocation()),
				*ActiveDetail));
			break;
		}
		ChaseStartDistance = FVector::Dist2D(
			Subject->GetActorLocation(), Target->GetActorLocation());
		AlertSource->PublishAlert(Target.Get());
		bAlertPublished = true;
		break;
	case 2:
		if (!bAlertPublished || !AlertSource->IsAlertActive() ||
			!Blackboard->GetValueAsBool(AlertKey) ||
			Blackboard->GetValueAsObject(LiveTargetKey) != Target.Get() ||
			!ActiveMoveUses(LiveTargetKey, ActiveDetail))
		{
			FailGate(TEXT("TrueKeyAbortsPatrolAndStartsChase"), FString::Printf(
				TEXT("published=%d alert=%d bb_alert=%d exact_target=%d %s"),
				bAlertPublished ? 1 : 0, AlertSource->IsAlertActive() ? 1 : 0,
				Blackboard->GetValueAsBool(AlertKey) ? 1 : 0,
				Blackboard->GetValueAsObject(LiveTargetKey) == Target.Get() ? 1 : 0,
				*ActiveDetail));
		}
		break;
	case 3:
	{
		const double CurrentDistance = FVector::Dist2D(
			Subject->GetActorLocation(), Target->GetActorLocation());
		if (!ActiveMoveUses(LiveTargetKey, ActiveDetail) ||
			CurrentDistance > ChaseStartDistance - ChaseClosingUu)
		{
			FailGate(TEXT("ChaseClosesDistance"), FString::Printf(
				TEXT("start=%.2f current=%.2f required_closing=%.2f %s"),
				ChaseStartDistance, CurrentDistance, ChaseClosingUu, *ActiveDetail));
		}
		break;
	}
	case 4:
		if (FVector::Dist2D(Subject->GetActorLocation(), Target->GetActorLocation())
			< 320.0)
		{
			FailGate(TEXT("ResetFalseExitsChase"),
				TEXT("fixture reset would be ambiguous because chase target was already reached"));
			break;
		}
		AlertSource->ClearAlert();
		bAlertCleared = true;
		break;
	case 5:
		if (!bAlertCleared || AlertSource->IsAlertActive() ||
			Blackboard->GetValueAsBool(AlertKey) ||
			Blackboard->GetValueAsObject(LiveTargetKey) != nullptr ||
			!ActiveMoveUses(PatrolPointKey, ActiveDetail))
		{
			FailGate(TEXT("ResetFalseExitsChase"), FString::Printf(
				TEXT("cleared=%d alert=%d bb_alert=%d live_target=%s %s"),
				bAlertCleared ? 1 : 0, AlertSource->IsAlertActive() ? 1 : 0,
				Blackboard->GetValueAsBool(AlertKey) ? 1 : 0,
				Blackboard->GetValueAsObject(LiveTargetKey)
					? *Blackboard->GetValueAsObject(LiveTargetKey)->GetPathName()
					: TEXT("null"), *ActiveDetail));
		}
		break;
	case 6:
	case 7:
		if (!ActiveMoveUses(PatrolPointKey, ActiveDetail))
		{
			FailGate(TEXT("PatrolResumesAfterReset"), ActiveDetail);
		}
		break;
	case 8:
	{
		const bool bPatrolMove = ActiveMoveUses(PatrolPointKey, ActiveDetail);
		if (!bObservedPostResetArrival || !bObservedPostResetDeparture || !bPatrolMove)
		{
			FailGate(TEXT("PatrolResumesAfterReset"), FString::Printf(
				TEXT("arrival=%d departure=%d reached_index=%d best_other=%.2f patrol_move=%d %s"),
				bObservedPostResetArrival ? 1 : 0,
				bObservedPostResetDeparture ? 1 : 0,
				ReachedMarkerIndexAfterReset, BestDistanceToPostResetOther,
				bPatrolMove ? 1 : 0,
				*ActiveDetail));
		}
		else
		{
			UE_LOG(LogTemp, Display,
				TEXT("GUARD-PATROL-CHASE-%s-PASS PrioritySelectorAndDecoratorsAuthored TrueKeyAbortsPatrolAndStartsChase ChaseClosesDistance ResetFalseExitsChase PatrolResumesAfterReset max_frame=%.2f"),
				IsA<AGuardPatrolChaseAdmissionTest>()
					? TEXT("admission") : TEXT("production"),
				MaxFrameStep);
		}
		break;
	}
	default:
		break;
	}
}
