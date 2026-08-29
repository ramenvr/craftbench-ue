// Copyright CraftBench. All Rights Reserved.

#include "WalkableGroundAdmissionFunctionalTest.h"

#include "AIController.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationData.h"
#include "NavigationInvokerComponent.h"
#include "NavigationSystem.h"
#include "WalkableGroundAdmissionTypes.h"

namespace
{
	const FName AdmissionScoutTag(TEXT("WalkableGroundAdmissionScout"));
	const FName ProductionScoutTag(TEXT("WalkableGroundDesignatedScout"));

	constexpr double ProvisionalMinimumMove = 250.0;
	constexpr double ProvisionalMaxFrameStep = 80.0;
	constexpr int32 ProvisionalMinimumMovingFrames = 20;
}

AWalkableGroundFunctionalTest::AWalkableGroundFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Tags.Remove(TEXT("WalkableGroundAdmissionFixture"));
	Tags.AddUnique(TEXT("WalkableGroundFixture"));
}

AWalkableGroundInvokerAdmissionFunctionalTest::
	AWalkableGroundInvokerAdmissionFunctionalTest(
		const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.AddUnique(TEXT("WalkableGroundAdmissionFixture"));
}

void AWalkableGroundInvokerAdmissionFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	if (!ResolveHarness())
	{
		return;
	}
	// Two symmetric policies exercise different radii, lane positions, and
	// path lengths without changing difficulty. The token is verifier-owned and
	// emitted in telemetry; candidate content cannot observe it before PIE.
	PolicyToken = static_cast<uint32>(FPlatformTime::Cycles64());
	const bool bAlternate = (PolicyToken & 1u) != 0;
	const double LaneY = bAlternate ? 350.0 : -350.0;
	OldCenter = FVector(-5000.0, LaneY, 100.0);
	NewCenter = FVector(0.0, LaneY, 100.0);
	FarCenter = FVector(5000.0, -LaneY, 100.0);
	SegmentOffset = FVector(bAlternate ? 760.0 : 640.0, 0.0, 0.0);
	ExpectedGenerationRadius = bAlternate ? 1650.0f : 1450.0f;
	ExpectedRemovalRadius = bAlternate ? 2250.0f : 2050.0f;
	if (UNavigationInvokerComponent* Invoker =
		Scout->FindComponentByClass<UNavigationInvokerComponent>())
	{
		Invoker->Deactivate();
		Invoker->SetGenerationRadii(
			ExpectedGenerationRadius, ExpectedRemovalRadius);
		Invoker->Activate(true);
	}
	else
	{
		if (IsAdmissionFixture())
		{
			FailHarness(TEXT("designated scout lost its invoker before policy setup"));
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("WALKABLE-GROUND-CANDIDATE invoker_absent_before_policy=1"));
	}
	Scout->SetActorLocation(OldCenter, false, nullptr,
		ETeleportType::TeleportPhysics);

	// All times are ordinary PIE world time. The generous admission windows are
	// deliberately provisional until five live Windows runs establish tile
	// generation/removal envelopes.
	SetCheckpointSchedule({1.0, 5.0, 10.0, 13.0, 17.0});
}

bool AWalkableGroundInvokerAdmissionFunctionalTest::ResolveHarness()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FailHarness(TEXT("no PIE world"));
		return false;
	}

	TArray<AActor*> TaggedScouts;
	UGameplayStatics::GetAllActorsWithTag(World,
		IsAdmissionFixture() ? AdmissionScoutTag : ProductionScoutTag,
		TaggedScouts);
	if (TaggedScouts.Num() != 1)
	{
		FailHarness(FString::Printf(
			TEXT("expected one designated admission scout; actual=%d"),
			TaggedScouts.Num()));
		return false;
	}
	Scout = Cast<ADesignatedScoutCharacter>(TaggedScouts[0]);
	if (!Scout.IsValid())
	{
		FailHarness(TEXT("tagged designated scout has wrong production base"));
		return false;
	}
	if (IsAdmissionFixture()
		&& Scout->GetClass() != AWalkableGroundAdmissionScout::StaticClass())
	{
		FailHarness(TEXT("admission scout class is not exact"));
		return false;
	}

	int32 BoundsCount = 0;
	for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
	{
		++BoundsCount;
	}
	if (BoundsCount != 1)
	{
		FailHarness(FString::Printf(
			TEXT("expected one navigation bounds volume; actual=%d"), BoundsCount));
		return false;
	}
	return true;
}

void AWalkableGroundInvokerAdmissionFunctionalTest::Tick(float DeltaSeconds)
{
	if (IsRunning() && bMoveIssued && Scout.IsValid())
	{
		const FVector Current = Scout->GetActorLocation();
		const double Step = FVector::Dist2D(Current, PreviousMoveSample);
		if (!FMath::IsFinite(Step) || Step > ProvisionalMaxFrameStep)
		{
			FailGate(TEXT("NewlyNavigableGroundCarriesRealMove"),
				FString::Printf(TEXT("non-finite/teleport frame step=%.2f"), Step));
			return;
		}
		MaxMoveFrameStep = FMath::Max(MaxMoveFrameStep, Step);
		PreviousMoveSample = Current;
		++MoveSampleFrames;
		if (const AAIController* Controller = ScoutController.Get())
		{
			if (const UPathFollowingComponent* PathFollowing =
				Controller->GetPathFollowingComponent())
			{
				if (PathFollowing->GetStatus() == EPathFollowingStatus::Moving)
				{
					++MovingStatusFrames;
				}
			}
		}
	}

	Super::Tick(DeltaSeconds);
	if (!IsRunning() || !NavigationSystem.IsValid() || !RecastNavMesh.IsValid())
	{
		return;
	}

	// A third neighborhood is a dense negative control. Sampling every quarter
	// world-second prevents a timed whole-map build from hiding between the
	// named checkpoints without turning pathfinding into per-frame polling.
	const double Now = static_cast<double>(GetWorld()->GetTimeSeconds());
	const int32 ProductionGateBase = IsAdmissionFixture() ? 2 : 0;
	if (PassedGates[ProductionGateBase]
		&& Now >= NextFarControlSampleTime)
	{
		NextFarControlSampleTime = Now + 0.25;
		bFarEverReachable |= PathExists(FarCenter, FarCenter + SegmentOffset);
		if (bFarEverReachable)
		{
			FailGate(TEXT("FarPathFailsOutsideInvokerRadius"),
				TEXT("far control acquired a complete path after its gate"));
		}
	}
}

bool AWalkableGroundInvokerAdmissionFunctionalTest::PathExists(
	const FVector& Start, const FVector& End) const
{
	UNavigationSystemV1* NavSystem = NavigationSystem.Get();
	AWalkableGroundAdmissionRecastNavMesh* Recast = RecastNavMesh.Get();
	if (NavSystem == nullptr || Recast == nullptr)
	{
		return false;
	}
	const FPathFindingQuery Query(this, *Recast, Start, End);
	const FPathFindingResult PathResult = NavSystem->FindPathSync(Query);
	return PathResult.IsSuccessful() && PathResult.Path.IsValid() && !PathResult.IsPartial();
}

int32 AWalkableGroundInvokerAdmissionFunctionalTest::PopulatedTileLayersAt(
	const FVector& Point) const
{
	const AWalkableGroundAdmissionRecastNavMesh* Recast = RecastNavMesh.Get();
	if (Recast == nullptr)
	{
		return 0;
	}
	int32 TileX = 0;
	int32 TileY = 0;
	if (!Recast->GetNavMeshTileXY(Point, TileX, TileY))
	{
		return 0;
	}
	TArray<FNavTileRef> TileRefs;
	Recast->GetNavMeshTilesAt(TileX, TileY, TileRefs);
	return TileRefs.Num();
}

void AWalkableGroundInvokerAdmissionFunctionalTest::LogTelemetry(
	const TCHAR* Phase, double TimeSeconds) const
{
	const ADesignatedScoutCharacter* CurrentScout = Scout.Get();
	const UNavigationSystemV1* NavSystem = NavigationSystem.Get();
	const AWalkableGroundAdmissionRecastNavMesh* Recast = RecastNavMesh.Get();
	const FVector Location = CurrentScout
		? CurrentScout->GetActorLocation() : FVector::ZeroVector;
	const bool bOldPath = PathExists(OldCenter, OldCenter + SegmentOffset);
	const bool bNewPath = PathExists(NewCenter, NewCenter + SegmentOffset);
	const bool bFarPath = PathExists(FarCenter, FarCenter + SegmentOffset);
	UE_LOG(LogTemp, Display, TEXT(
		"WALKABLE-GROUND-TELEMETRY phase=%s t=%.2f policy=%u scout=(%.1f,%.1f,%.1f) "
		"invokers=%d active_tile_set=%d populated_tiles=%d "
		"old_path=%d new_path=%d far_path=%d old_layers=%d new_layers=%d "
		"far_layers=%d move_frames=%d moving_status_frames=%d max_step=%.2f"),
		Phase, TimeSeconds, PolicyToken, Location.X, Location.Y, Location.Z,
		NavSystem ? NavSystem->GetInvokerLocations().Num() : -1,
		Recast ? Recast->GetActiveTileSet().Num() : -1,
		Recast ? Recast->GetNumActiveTiles() : -1,
		bOldPath ? 1 : 0, bNewPath ? 1 : 0, bFarPath ? 1 : 0,
		PopulatedTileLayersAt(OldCenter), PopulatedTileLayersAt(NewCenter),
		PopulatedTileLayersAt(FarCenter), MoveSampleFrames,
		MovingStatusFrames, MaxMoveFrameStep);
}

void AWalkableGroundInvokerAdmissionFunctionalTest::PassGate(
	int32 GateIndex, const TCHAR* GateName, const FString& Detail)
{
	if (!ensure(GateIndex >= 0 && GateIndex < UE_ARRAY_COUNT(PassedGates))
		|| PassedGates[GateIndex])
	{
		FailHarness(FString::Printf(
			TEXT("invalid/duplicate gate index=%d name=%s"), GateIndex, GateName));
		return;
	}
	PassedGates[GateIndex] = true;
	++PassedGateCount;
	UE_LOG(LogTemp, Display, TEXT("GATE[%s]=PASS %s"), GateName, *Detail);
}

void AWalkableGroundInvokerAdmissionFunctionalTest::FailGate(
	const TCHAR* GateName, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]=FAIL %s"), GateName, *Detail));
}

void AWalkableGroundInvokerAdmissionFunctionalTest::FailHarness(
	const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Error,
		TEXT("HARNESS-PRECONDITION: ") + Detail);
}

void AWalkableGroundInvokerAdmissionFunctionalTest::OnCheckpoint(
	int32 CheckpointIndex, double TimeSeconds)
{
	if (!Scout.IsValid())
	{
		FailHarness(TEXT("designated scout identity did not survive"));
		return;
	}

	if (CheckpointIndex == 0)
	{
		UWorld* World = GetWorld();
		NavigationSystem = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
		if (!NavigationSystem.IsValid()
			|| NavigationSystem->GetClass()
				!= UWalkableGroundAdmissionNavigationSystem::StaticClass())
		{
			FailHarness(FString::Printf(TEXT("wrong navigation system class=%s"),
				*GetPathNameSafe(NavigationSystem.Get())));
			return;
		}
		RecastNavMesh = Cast<AWalkableGroundAdmissionRecastNavMesh>(
			NavigationSystem->GetDefaultNavDataInstance(
				FNavigationSystem::DontCreate));
		if (!RecastNavMesh.IsValid())
		{
			FailHarness(TEXT("custom dynamic Recast is not default nav data"));
			return;
		}
		if (!NavigationSystem->IsActiveTilesGenerationEnabled()
			|| RecastNavMesh->GetRuntimeGenerationMode()
				!= ERuntimeGenerationType::Dynamic
			|| !RecastNavMesh->SupportsRuntimeGeneration())
		{
			const FString Detail = FString::Printf(
					TEXT("active_tiles_enabled=%d runtime_mode=%d "
						 "supports_runtime=%d"),
					NavigationSystem->IsActiveTilesGenerationEnabled() ? 1 : 0,
					static_cast<int32>(
						RecastNavMesh->GetRuntimeGenerationMode()),
					RecastNavMesh->SupportsRuntimeGeneration() ? 1 : 0);
			if (IsAdmissionFixture())
			{
				FailGate(TEXT("DynamicNavigationIsInvokerBounded"), Detail);
			}
			else
			{
				FailHarness(TEXT("protected navigation mechanism invalid: ")
					+ Detail);
			}
			return;
		}
		if (IsAdmissionFixture())
		{
			PassGate(0, TEXT("DynamicNavigationIsInvokerBounded"),
				FString::Printf(TEXT("navsys=%s recast=%s active_tiles=%d"),
					*NavigationSystem->GetClass()->GetPathName(),
					*RecastNavMesh->GetClass()->GetPathName(),
					RecastNavMesh->GetNumActiveTiles()));
		}

		UNavigationInvokerComponent* Invoker =
			Scout->FindComponentByClass<UNavigationInvokerComponent>();
		const TArray<FNavigationInvokerRaw>& RawInvokers =
			NavigationSystem->GetInvokerLocations();
		const bool bExactInvoker = Invoker != nullptr && Invoker->IsActive()
			&& Invoker->GetOwner() == Scout.Get()
			&& FMath::IsNearlyEqual(Invoker->GetGenerationRadius(),
				ExpectedGenerationRadius)
			&& FMath::IsNearlyEqual(Invoker->GetRemovalRadius(),
				ExpectedRemovalRadius)
			&& RawInvokers.Num() == 1
			&& FVector::Dist2D(RawInvokers[0].Location,
				Scout->GetActorLocation()) < 25.0
			&& FMath::IsNearlyEqual(RawInvokers[0].RadiusMin,
				ExpectedGenerationRadius)
			&& FMath::IsNearlyEqual(RawInvokers[0].RadiusMax,
				ExpectedRemovalRadius);
		if (!bExactInvoker)
		{
			const FString Detail = FString::Printf(
				TEXT("component=%d active=%d raw_count=%d"),
					Invoker ? 1 : 0, Invoker && Invoker->IsActive() ? 1 : 0,
					RawInvokers.Num());
			if (IsAdmissionFixture())
			{
				FailGate(TEXT("DesignatedAgentOwnsNavigationInvoker"), Detail);
				return;
			}
			else
			{
				UE_LOG(LogTemp, Display,
					TEXT("WALKABLE-GROUND-CANDIDATE invalid_invoker=1 %s"),
					*Detail);
			}
		}
		if (IsAdmissionFixture())
		{
			PassGate(1, TEXT("DesignatedAgentOwnsNavigationInvoker"),
				FString::Printf(
					TEXT("owner=%s generation=%.1f removal=%.1f raw=1"),
					*Scout->GetPathName(), Invoker->GetGenerationRadius(),
					Invoker->GetRemovalRadius()));
		}
		LogTelemetry(TEXT("mechanism"), TimeSeconds);
		return;
	}

	if (!NavigationSystem.IsValid() || !RecastNavMesh.IsValid())
	{
		FailHarness(TEXT("navigation identities did not survive"));
		return;
	}

	switch (CheckpointIndex)
	{
	case 1:
	{
		const int32 GateBase = IsAdmissionFixture() ? 2 : 0;
		const bool bOld = PathExists(OldCenter, OldCenter + SegmentOffset);
		const bool bNew = PathExists(NewCenter, NewCenter + SegmentOffset);
		const bool bFar = PathExists(FarCenter, FarCenter + SegmentOffset);
		LogTelemetry(TEXT("old-only"), TimeSeconds);
		if (!bOld)
		{
			if (IsAdmissionFixture())
			{
				FailHarness(TEXT("old neighborhood never acquired its admission path"));
			}
			else
			{
				FailGate(TEXT("FarPathFailsOutsideInvokerRadius"),
					TEXT("old_complete=0 candidate local ground unavailable"));
			}
			return;
		}
		if (bNew || bFar)
		{
			FailGate(TEXT("FarPathFailsOutsideInvokerRadius"),
				FString::Printf(TEXT("new_before_move=%d far=%d"),
					bNew ? 1 : 0, bFar ? 1 : 0));
			return;
		}
		PassGate(GateBase, TEXT("FarPathFailsOutsideInvokerRadius"),
			TEXT("old_complete=1 new_before_move=0 far=0"));
		NextFarControlSampleTime = TimeSeconds + 0.25;
		if (AAIController* Controller = Cast<AAIController>(Scout->GetController()))
		{
			Controller->StopMovement();
			ScoutController = Controller;
		}
		else
		{
			FailHarness(TEXT("designated scout has no live AIController"));
			return;
		}
		if (!Scout->SetActorLocation(NewCenter, false, nullptr,
			ETeleportType::TeleportPhysics))
		{
			FailHarness(TEXT("fixture could not relocate scout to new neighborhood"));
		}
		break;
	}

	case 2:
	{
		const int32 GateBase = IsAdmissionFixture() ? 2 : 0;
		const bool bNew = PathExists(NewCenter, NewCenter + SegmentOffset);
		const bool bFar = PathExists(FarCenter, FarCenter + SegmentOffset);
		LogTelemetry(TEXT("new-live"), TimeSeconds);
		if (!bNew || bFar || bFarEverReachable)
		{
			FailGate(TEXT("NewNeighborhoodBecomesNavigable"),
				FString::Printf(TEXT("new_complete=%d far=%d far_ever=%d"),
					bNew ? 1 : 0, bFar ? 1 : 0,
					bFarEverReachable ? 1 : 0));
			return;
		}
		PassGate(GateBase + 1, TEXT("NewNeighborhoodBecomesNavigable"),
			FString::Printf(TEXT("new_complete=1 new_layers=%d far=0"),
				PopulatedTileLayersAt(NewCenter)));
		AAIController* Controller = ScoutController.Get();
		if (Controller == nullptr)
		{
			FailHarness(TEXT("AIController disappeared before movement probe"));
			return;
		}
		MoveStart = Scout->GetActorLocation();
		PreviousMoveSample = MoveStart;
		const EPathFollowingRequestResult::Type Request =
			Controller->MoveToLocation(
				NewCenter + SegmentOffset, 75.0f, true, true,
				true, true, TSubclassOf<UNavigationQueryFilter>(), false);
		if (Request == EPathFollowingRequestResult::Failed)
		{
			FailGate(TEXT("NewlyNavigableGroundCarriesRealMove"),
				TEXT("AAIController::MoveToLocation returned Failed"));
			return;
		}
		bMoveIssued = true;
		UE_LOG(LogTemp, Display,
			TEXT("WALKABLE-GROUND-MOVE request=%d start=(%.1f,%.1f) goal=(%.1f,%.1f)"),
			static_cast<int32>(Request), MoveStart.X, MoveStart.Y,
			(NewCenter + SegmentOffset).X,
			(NewCenter + SegmentOffset).Y);
		break;
	}

	case 3:
	{
		const int32 GateBase = IsAdmissionFixture() ? 2 : 0;
		const double Displacement = FVector::Dist2D(
			Scout->GetActorLocation(), MoveStart);
		LogTelemetry(TEXT("real-move"), TimeSeconds);
		if (!bMoveIssued || Displacement < ProvisionalMinimumMove
			|| MovingStatusFrames < ProvisionalMinimumMovingFrames
			|| MaxMoveFrameStep > ProvisionalMaxFrameStep)
		{
			FailGate(TEXT("NewlyNavigableGroundCarriesRealMove"),
				FString::Printf(TEXT(
					"issued=%d displacement=%.1f moving_frames=%d max_step=%.2f"),
					bMoveIssued ? 1 : 0, Displacement, MovingStatusFrames,
					MaxMoveFrameStep));
			return;
		}
		PassGate(GateBase + 2, TEXT("NewlyNavigableGroundCarriesRealMove"),
			FString::Printf(TEXT(
				"displacement=%.1f samples=%d moving_frames=%d max_step=%.2f"),
				Displacement, MoveSampleFrames, MovingStatusFrames,
				MaxMoveFrameStep));
		break;
	}

	case 4:
	{
		const int32 GateBase = IsAdmissionFixture() ? 2 : 0;
		const bool bOld = PathExists(OldCenter, OldCenter + SegmentOffset);
		const bool bFar = PathExists(FarCenter, FarCenter + SegmentOffset);
		const int32 OldLayers = PopulatedTileLayersAt(OldCenter);
		LogTelemetry(TEXT("old-retired"), TimeSeconds);
		if (bOld || OldLayers != 0 || bFar || bFarEverReachable)
		{
			FailGate(TEXT("OldNeighborhoodLosesNavigation"),
				FString::Printf(TEXT(
					"old_path=%d old_layers=%d far=%d far_ever=%d"),
					bOld ? 1 : 0, OldLayers, bFar ? 1 : 0,
					bFarEverReachable ? 1 : 0));
			return;
		}
		PassGate(GateBase + 3, TEXT("OldNeighborhoodLosesNavigation"),
			TEXT("old_path=0 old_layers=0 far=0 far_ever=0"));
		const int32 ExpectedGateCount = IsAdmissionFixture() ? 6 : 4;
		if (PassedGateCount != ExpectedGateCount)
		{
			FailHarness(FString::Printf(
				TEXT("terminal gate count=%d expected=%d"),
				PassedGateCount, ExpectedGateCount));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded,
			IsAdmissionFixture()
				? TEXT("WALKABLE-GROUND-ADMISSION-SUCCEEDED gates=6/6")
				: TEXT("WALKABLE-GROUND-SUCCEEDED gates=4/4"));
		break;
	}

	default:
		FailHarness(FString::Printf(TEXT("unexpected checkpoint=%d"),
			CheckpointIndex));
		break;
	}
}
