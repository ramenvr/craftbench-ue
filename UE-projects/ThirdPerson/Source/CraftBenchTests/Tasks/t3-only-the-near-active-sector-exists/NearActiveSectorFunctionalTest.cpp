// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorFunctionalTest.h"

#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "WorldPartition/DataLayer/DataLayerAsset.h"
#include "WorldPartition/DataLayer/DataLayerInstance.h"
#include "WorldPartition/DataLayer/DataLayerManager.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionSubsystem.h"

namespace
{
	const FName ControllerTag(TEXT("NearActiveSectorController"));
	const FName RequestTag(TEXT("NearActiveSectorRequest"));
	const FName SourceTag(TEXT("NearActiveSectorSource"));
}

void ANearActiveSectorAdmissionController::ApplySectorRequest_Implementation(
	ANearActiveSectorRequest* RequestValue)
{
	if (RequestValue == nullptr || RequestValue->StreamingSourceActor == nullptr
		|| RequestValue->SelectedLayer == nullptr
		|| RequestValue->CandidateLayers.Num() != 2)
	{
		return;
	}
	UDataLayerManager* Manager = UDataLayerManager::GetDataLayerManager(this);
	if (Manager == nullptr)
	{
		return;
	}
	for (UDataLayerAsset* Layer : RequestValue->CandidateLayers)
	{
		if (Layer == nullptr)
		{
			return;
		}
		Manager->SetDataLayerRuntimeState(Layer,
			Layer == RequestValue->SelectedLayer
				? EDataLayerRuntimeState::Activated
				: EDataLayerRuntimeState::Unloaded);
	}
	RequestValue->StreamingSourceActor->SetActorLocation(
		RequestValue->SelectedDestination, false, nullptr,
		ETeleportType::TeleportPhysics);
}

ANearActiveSectorFunctionalTestBase::ANearActiveSectorFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

bool ANearActiveSectorFunctionalTestBase::RequireHarness(
	const bool bCondition, const FString& Detail)
{
	if (!bCondition)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: ") + Detail);
	}
	return bCondition;
}

void ANearActiveSectorFunctionalTestBase::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]: %s"), Gate, *Detail));
}

bool ANearActiveSectorFunctionalTestBase::ResolveStaging()
{
	UWorld* World = GetWorld();
	TArray<AActor*> Controllers;
	TArray<AActor*> Requests;
	TArray<AActor*> Sources;
	UGameplayStatics::GetAllActorsWithTag(World, ControllerTag, Controllers);
	UGameplayStatics::GetAllActorsWithTag(World, RequestTag, Requests);
	UGameplayStatics::GetAllActorsWithTag(World, SourceTag, Sources);
	if (!RequireHarness(Controllers.Num() == 1 && Requests.Num() == 1
		&& Sources.Num() == 1, FString::Printf(
			TEXT("controller/request/source expected 1/1/1 got %d/%d/%d"),
			Controllers.Num(), Requests.Num(), Sources.Num())))
	{
		return false;
	}
	Controller = Cast<ANearActiveSectorControllerBase>(Controllers[0]);
	Request = Cast<ANearActiveSectorRequest>(Requests[0]);
	Source = Cast<ANearActiveSectorStreamingSource>(Sources[0]);
	SourceComponent = Source.IsValid() ? Source->StreamingSource : nullptr;
	if (!RequireHarness(Controller.IsValid() && Request.IsValid()
		&& Source.IsValid() && SourceComponent.IsValid(),
		TEXT("exact native controller/request/source classes are required")))
	{
		return false;
	}
	const bool bAdmissionClass = Controller->IsA<ANearActiveSectorAdmissionController>();
	if (!RequireHarness(bAdmissionClass == UsesAdmissionController(),
		FString::Printf(TEXT("controller mode mismatch admission=%d expected=%d"),
			bAdmissionClass ? 1 : 0, UsesAdmissionController() ? 1 : 0)))
	{
		return false;
	}
	UWorldPartition* Partition = World ? World->GetWorldPartition() : nullptr;
	UWorldPartitionSubsystem* Subsystem = World
		? World->GetSubsystem<UWorldPartitionSubsystem>() : nullptr;
	UDataLayerManager* Manager = UDataLayerManager::GetDataLayerManager(World);
	if (!RequireHarness(Partition != nullptr && Subsystem != nullptr
		&& Manager != nullptr && SourceComponent->IsRegistered()
		&& SourceComponent->IsStreamingSourceEnabled(),
		TEXT("real World Partition, Data Layer manager, and registered source are required")))
	{
		return false;
	}
	if (!RequireHarness(LayerA != nullptr && LayerB != nullptr && LayerA != LayerB
		&& LayerA->IsRuntime() && LayerB->IsRuntime()
		&& Manager->GetDataLayerInstanceFromAsset(LayerA) != nullptr
		&& Manager->GetDataLayerInstanceFromAsset(LayerB) != nullptr,
		TEXT("exact two distinct runtime Data Layer instances are required")))
	{
		return false;
	}
	FirstLayer = ReverseOrder() ? LayerB : LayerA;
	SecondLayer = ReverseOrder() ? LayerA : LayerB;
	FirstLocation = ReverseOrder() ? SectorBLocation : SectorALocation;
	SecondLocation = ReverseOrder() ? SectorALocation : SectorBLocation;
	FirstSector = ReverseOrder() ? TEXT("SectorB") : TEXT("SectorA");
	SecondSector = ReverseOrder() ? TEXT("SectorA") : TEXT("SectorB");
	Request->StreamingSourceActor = Source.Get();
	Request->CandidateLayers = {LayerA, LayerB};
	Request->SelectedLayer = nullptr;
	Request->SelectedDestination = FVector::ZeroVector;
	Request->RequestToken = NAME_None;
	Manager->SetDataLayerRuntimeState(LayerA, EDataLayerRuntimeState::Unloaded);
	Manager->SetDataLayerRuntimeState(LayerB, EDataLayerRuntimeState::Unloaded);
	Source->SetActorLocation((SectorALocation + SectorBLocation) * 0.5,
		false, nullptr, ETeleportType::TeleportPhysics);
	return true;
}

void ANearActiveSectorFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	// Automation prepares every placed FunctionalTest when PIE starts, but runs
	// them sequentially. Per-fixture world reset therefore belongs in StartTest.
}

void ANearActiveSectorFunctionalTestBase::StartTest()
{
	Super::StartTest();
	if (!IsRunning())
	{
		return;
	}
	RetiredFirstMarkers.Reset();
	RetiredFirstById.Reset();
	RetiredFirstBeginEpochs.Reset();
	if (!ResolveStaging())
	{
		return;
	}
	const UWorld* World = GetWorld();
	const double Now = World ? static_cast<double>(World->GetTimeSeconds()) : 0.0;
	// Checkpoints use absolute PIE world time. Anchor each placed fixture to its
	// own actual start so the second reversed leg cannot consume the first leg's
	// already-past schedule.
	SetCheckpointSchedule({Now + 2.50, Now + 5.00, Now + 7.50,
		Now + 10.00, Now + 12.50});
}

void ANearActiveSectorFunctionalTestBase::Issue(
	UDataLayerAsset* SelectedLayer, const FVector& Destination, const FName Token)
{
	Request->SelectedLayer = SelectedLayer;
	Request->SelectedDestination = Destination;
	Request->RequestToken = Token;
	Controller->ApplySectorRequest(Request.Get());
}

bool ANearActiveSectorFunctionalTestBase::RequireSettled(const TCHAR* Stage) const
{
	const UWorld* World = GetWorld();
	const UWorldPartitionSubsystem* Subsystem = World
		? World->GetSubsystem<UWorldPartitionSubsystem>() : nullptr;
	const bool bComponentComplete = SourceComponent.IsValid()
		&& SourceComponent->IsStreamingCompleted();
	const bool bSubsystemComplete = Subsystem != nullptr
		&& Subsystem->IsStreamingCompleted(SourceComponent.Get());
	if (!bComponentComplete || !bSubsystemComplete)
	{
		const_cast<ANearActiveSectorFunctionalTestBase*>(this)->FinishTest(
			EFunctionalTestResult::Error, FString::Printf(
				TEXT("HARNESS-PRECONDITION: World Partition did not settle at %s component=%d subsystem=%d"),
				Stage, bComponentComplete ? 1 : 0, bSubsystemComplete ? 1 : 0));
		return false;
	}
	return true;
}

bool ANearActiveSectorFunctionalTestBase::RequireInitialReset() const
{
	const UDataLayerManager* Manager = UDataLayerManager::GetDataLayerManager(this);
	const UDataLayerInstance* A = Manager
		? Manager->GetDataLayerInstanceFromAsset(LayerA) : nullptr;
	const UDataLayerInstance* B = Manager
		? Manager->GetDataLayerInstanceFromAsset(LayerB) : nullptr;
	const bool bReset = Manager != nullptr && A != nullptr && B != nullptr
		&& Manager->GetDataLayerInstanceEffectiveRuntimeState(A)
			== EDataLayerRuntimeState::Unloaded
		&& Manager->GetDataLayerInstanceEffectiveRuntimeState(B)
			== EDataLayerRuntimeState::Unloaded;
	if (!bReset)
	{
		const_cast<ANearActiveSectorFunctionalTestBase*>(this)->FinishTest(
			EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: verifier initial Data Layer reset did not settle"));
	}
	return bReset;
}

bool ANearActiveSectorFunctionalTestBase::RequireLayerStates(
	UDataLayerAsset* ActiveLayer, UDataLayerAsset* InactiveLayer,
	const TCHAR* Stage) const
{
	const UDataLayerManager* Manager = UDataLayerManager::GetDataLayerManager(this);
	const UDataLayerInstance* Active = Manager
		? Manager->GetDataLayerInstanceFromAsset(ActiveLayer) : nullptr;
	const UDataLayerInstance* Inactive = Manager
		? Manager->GetDataLayerInstanceFromAsset(InactiveLayer) : nullptr;
	const bool bValid = Manager != nullptr && Active != nullptr && Inactive != nullptr
		&& Manager->GetDataLayerInstanceEffectiveRuntimeState(Active)
			== EDataLayerRuntimeState::Activated
		&& Manager->GetDataLayerInstanceEffectiveRuntimeState(Inactive)
			== EDataLayerRuntimeState::Unloaded;
	if (!bValid)
	{
		const_cast<ANearActiveSectorFunctionalTestBase*>(this)->FailGate(
			TEXT("InactiveLayerHasNoLiveActors"), FString::Printf(
				TEXT("wrong effective layer state at %s"), Stage));
	}
	return bValid;
}

TArray<ANearActiveSectorMarker*>
ANearActiveSectorFunctionalTestBase::LiveMarkers() const
{
	TArray<ANearActiveSectorMarker*> LiveMarkerActors;
	for (TActorIterator<ANearActiveSectorMarker> It(GetWorld()); It; ++It)
	{
		if (IsValid(*It))
		{
			LiveMarkerActors.Add(*It);
		}
	}
	return LiveMarkerActors;
}

bool ANearActiveSectorFunctionalTestBase::RequireExactMarkers(
	const FName SectorId, const TCHAR* Stage,
	TArray<TWeakObjectPtr<ANearActiveSectorMarker>>* Capture) const
{
	const TArray<ANearActiveSectorMarker*> Markers = LiveMarkers();
	TSet<FName> Ids;
	bool bOwnership = true;
	for (ANearActiveSectorMarker* Marker : Markers)
	{
		Ids.Add(Marker->MarkerId);
		bOwnership = bOwnership && Marker->SectorId == SectorId
			&& Marker->GetLevel() != GetWorld()->PersistentLevel
			&& Marker->GetIsSpatiallyLoaded();
		if (Capture != nullptr)
		{
			Capture->Add(Marker);
		}
	}
	const FName One = SectorId == TEXT("SectorA") ? TEXT("A_Quartz") : TEXT("B_Amber");
	const FName Two = SectorId == TEXT("SectorA") ? TEXT("A_Violet") : TEXT("B_Cedar");
	const bool bExact = Markers.Num() == 2 && Ids.Num() == 2
		&& Ids.Contains(One) && Ids.Contains(Two) && bOwnership;
	if (!bExact)
	{
		const_cast<ANearActiveSectorFunctionalTestBase*>(this)->FailGate(
			TEXT("ActiveNearCellLoadsExactActorSet"), FString::Printf(
				TEXT("stage=%s sector=%s live=%d ids=%d ownership=%d"), Stage,
				*SectorId.ToString(), Markers.Num(), Ids.Num(), bOwnership ? 1 : 0));
	}
	return bExact;
}

bool ANearActiveSectorFunctionalTestBase::RequireNoMarkers(
	const TCHAR* Gate, const TCHAR* Stage) const
{
	const int32 Count = LiveMarkers().Num();
	if (Count != 0)
	{
		const_cast<ANearActiveSectorFunctionalTestBase*>(this)->FailGate(
			Gate, FString::Printf(TEXT("stage=%s live_markers=%d"), Stage, Count));
		return false;
	}
	return true;
}

void ANearActiveSectorFunctionalTestBase::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (!Controller.IsValid() || !Request.IsValid() || !Source.IsValid()
		|| !SourceComponent.IsValid())
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: staged identity changed"));
		return;
	}
	UE_LOG(LogTemp, Display,
		TEXT("NEAR-ACTIVE-SECTOR-TELEMETRY cp=%d t=%.3f token=%s source=%s live=%d"),
		CheckpointIndex, TimeSeconds, *Request->RequestToken.ToString(),
		*Source->GetActorLocation().ToCompactString(), LiveMarkers().Num());
	switch (CheckpointIndex)
	{
	case 0:
		if (RequireSettled(TEXT("initial-reset"))
			&& RequireInitialReset()
			&& RequireNoMarkers(TEXT("InactiveLayerHasNoLiveActors"), TEXT("initial")))
		{
			Issue(FirstLayer, FirstLocation, TEXT("LoadFirst"));
		}
		break;
	case 1:
		if (RequireSettled(TEXT("first"))
			&& RequireLayerStates(FirstLayer, SecondLayer, TEXT("first"))
			&& RequireExactMarkers(FirstSector, TEXT("first"), &RetiredFirstMarkers))
		{
			RetiredFirstById.Reset();
			RetiredFirstBeginEpochs.Reset();
			for (const TWeakObjectPtr<ANearActiveSectorMarker>& Retired
				: RetiredFirstMarkers)
			{
				if (const ANearActiveSectorMarker* Marker = Retired.Get())
				{
					RetiredFirstById.Add(Marker->MarkerId, Retired);
					RetiredFirstBeginEpochs.Add(
						Marker->MarkerId, Marker->BeginPlayEpoch);
				}
			}
			Issue(FirstLayer, SecondLocation, TEXT("LeaveFirstKeepLayer"));
		}
		break;
	case 2:
		if (RequireSettled(TEXT("left-first"))
			&& RequireNoMarkers(TEXT("LeavingCellUnloadsPriorIdentities"), TEXT("left-first")))
		{
			int32 RetiredValid = 0;
			int32 Ended = 0;
			for (const TPair<FName, TWeakObjectPtr<ANearActiveSectorMarker>>& Pair
				: RetiredFirstById)
			{
				if (const ANearActiveSectorMarker* Marker = Pair.Value.Get())
				{
					++RetiredValid;
					Ended += Marker->EndPlayEpoch > 0 ? 1 : 0;
					if (Marker->EndPlayEpoch <= 0)
					{
						FailGate(TEXT("LeavingCellUnloadsPriorIdentities"),
							FString::Printf(TEXT("marker=%s has no EndPlay epoch"),
								*Pair.Key.ToString()));
						return;
					}
				}
			}
			UE_LOG(LogTemp, Display,
				TEXT("NEAR-ACTIVE-SECTOR-LIFECYCLE stage=left retired_valid=%d endplay=%d"),
				RetiredValid, Ended);
			Issue(SecondLayer, SecondLocation, TEXT("LoadSecond"));
		}
		break;
	case 3:
		if (RequireSettled(TEXT("second"))
			&& RequireLayerStates(SecondLayer, FirstLayer, TEXT("second"))
			&& RequireExactMarkers(SecondSector, TEXT("second")))
		{
			Issue(FirstLayer, FirstLocation, TEXT("ReturnFirst"));
		}
		break;
	case 4:
		{
			TArray<TWeakObjectPtr<ANearActiveSectorMarker>> ReturnedFirstMarkers;
			if (RequireSettled(TEXT("returned"))
				&& RequireLayerStates(FirstLayer, SecondLayer, TEXT("returned"))
				&& RequireExactMarkers(FirstSector, TEXT("returned"),
					&ReturnedFirstMarkers))
			{
				int32 ReusedWithNewEpoch = 0;
				int32 Recreated = 0;
				for (const TWeakObjectPtr<ANearActiveSectorMarker>& Returned
					: ReturnedFirstMarkers)
				{
					ANearActiveSectorMarker* ReturnedMarker = Returned.Get();
					if (ReturnedMarker == nullptr || ReturnedMarker->BeginPlayEpoch <= 0)
					{
						FailGate(TEXT("ReturningCellCreatesFreshValidInstances"),
							TEXT("returned marker lacks a valid BeginPlay epoch"));
						return;
					}
					const TWeakObjectPtr<ANearActiveSectorMarker>* Retired =
						RetiredFirstById.Find(ReturnedMarker->MarkerId);
					const int32* PriorBegin =
						RetiredFirstBeginEpochs.Find(ReturnedMarker->MarkerId);
					if (Retired == nullptr || PriorBegin == nullptr)
					{
						FailGate(TEXT("ReturningCellCreatesFreshValidInstances"),
							TEXT("returned marker identity was not retired earlier"));
						return;
					}
					if (Retired->Get() == ReturnedMarker)
					{
						if (ReturnedMarker->BeginPlayEpoch <= *PriorBegin)
						{
							FailGate(TEXT("ReturningCellCreatesFreshValidInstances"),
								TEXT("reused object did not enter a new BeginPlay epoch"));
							return;
						}
						++ReusedWithNewEpoch;
					}
					else
					{
						++Recreated;
					}
				}
				UE_LOG(LogTemp, Display,
					TEXT("NEAR-ACTIVE-SECTOR-LIFECYCLE stage=returned reused_new_epoch=%d recreated=%d"),
					ReusedWithNewEpoch, Recreated);
				UE_LOG(LogTemp, Display,
					TEXT("NEAR-ACTIVE-SECTOR-PASS fixture=%s InactiveLayerHasNoLiveActors "
						 "ActiveNearCellLoadsExactActorSet LeavingCellUnloadsPriorIdentities "
						 "ReturningCellCreatesFreshValidInstances"), *GetName());
			}
		}
		break;
	default:
		break;
	}
}
