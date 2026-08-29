// Copyright CraftBench. All Rights Reserved.

#include "EpochTravelProtectedTypes.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EpochAssetWorldSubsystem.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr TCHAR ProtocolEnv[] = TEXT("CRAFTBENCH_EPOCH_TRAVEL_RUN");
	constexpr TCHAR NonceEnv[] = TEXT("CRAFTBENCH_EPOCH_TRAVEL_NONCE");

	bool IsProtocolEnabled()
	{
		return FPlatformMisc::GetEnvironmentVariable(ProtocolEnv) == TEXT("1");
	}

	UStaticMesh* LoadCube()
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
			TEXT("/Engine/BasicShapes/Cube.Cube"));
		return Cube.Object;
	}
}

AEpochAssetDisplay::AEpochAssetDisplay()
{
	PrimaryActorTick.bCanEverTick = false;
	DisplayMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DisplayMesh"));
	SetRootComponent(DisplayMesh);
	DisplayMesh->SetStaticMesh(LoadCube());
	DisplayMesh->SetWorldScale3D(FVector(1.0, 1.0, 1.4));
}

void AEpochAssetDisplay::ApplyRecord(UEpochAssetRecord* Record)
{
	if (Record == nullptr)
	{
		return;
	}
	AppliedRecordId = Record->RecordId;
	AppliedValue = Record->RecordValue;
	++ApplyCount;
	const double Scale = 0.8 + FMath::Clamp(
		static_cast<double>(FMath::Abs(AppliedValue)) / 100.0, 0.0, 1.8);
	SetActorScale3D(FVector(Scale, Scale, 1.0 + Scale * 0.35));
}

void UEpochTravelReporterSubsystem::Initialize(
	FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	WorldCleanupHandle = FWorldDelegates::OnWorldCleanup.AddUObject(
		this, &UEpochTravelReporterSubsystem::HandleWorldCleanup);
	PostWorldCleanupHandle = FWorldDelegates::OnPostWorldCleanup.AddUObject(
		this, &UEpochTravelReporterSubsystem::HandlePostWorldCleanup);
}

void UEpochTravelReporterSubsystem::Deinitialize()
{
	FWorldDelegates::OnWorldCleanup.Remove(WorldCleanupHandle);
	FWorldDelegates::OnPostWorldCleanup.Remove(PostWorldCleanupHandle);
	Super::Deinitialize();
}

void UEpochTravelReporterSubsystem::BeginOldEpoch(
	UWorld* World, UEpochAssetWorldSubsystem* Subsystem,
	AEpochAssetDisplay* Display, const FSoftObjectPath& RecordPath,
	FName ExpectedId, int32 ExpectedValue, bool bInitiallyPending)
{
	if (bTerminal || bOldBegan || World == nullptr || Subsystem == nullptr
		|| Display == nullptr || RecordPath.IsNull())
	{
		AbortHarness(TEXT("OLD_STAGE_INVALID"));
		return;
	}
	RunNonce = FPlatformMisc::GetEnvironmentVariable(NonceEnv);
	if (RunNonce.IsEmpty())
	{
		AbortHarness(TEXT("NONCE_MISSING"));
		return;
	}
	bProtocolActive = true;
	bOldBegan = true;
	bOldInitiallyPending = bInitiallyPending;
	OldWorld = World;
	OldSubsystem = Subsystem;
	OldDisplay = Display;
	OldRecordPath = RecordPath;
	OldExpectedId = ExpectedId;
	OldExpectedValue = ExpectedValue;
	OldWorldPackage = World->GetPackage()->GetName();
	UE_LOG(LogTemp, Display, TEXT(
		"EPOCH-TRAVEL-START READY nonce=%s world=%s record=%s pending=%d"),
		*RunNonce, *OldWorldPackage, *OldRecordPath.ToString(),
		bOldInitiallyPending ? 1 : 0);
}

void UEpochTravelReporterSubsystem::BeginNewEpoch(
	UWorld* World, UEpochAssetWorldSubsystem* Subsystem,
	AEpochAssetDisplay* Display, const FSoftObjectPath& RecordPath,
	FName ExpectedId, int32 ExpectedValue, bool bInitiallyPending)
{
	if (!bProtocolActive || bTerminal || !bOldBegan || bNewBegan
		|| World == nullptr || Subsystem == nullptr || Display == nullptr
		|| RecordPath.IsNull())
	{
		AbortHarness(TEXT("NEW_STAGE_INVALID"));
		return;
	}
	bNewBegan = true;
	bNewInitiallyPending = bInitiallyPending;
	NewWorld = World;
	NewSubsystem = Subsystem;
	NewDisplay = Display;
	NewRecordPath = RecordPath;
	NewExpectedId = ExpectedId;
	NewExpectedValue = ExpectedValue;
	NewWorldPackage = World->GetPackage()->GetName();
	UE_LOG(LogTemp, Display, TEXT(
		"EPOCH-TRAVEL-DESTINATION READY nonce=%s world=%s record=%s "
		"pending=%d cleanup=%d"), *RunNonce, *NewWorldPackage,
		*NewRecordPath.ToString(), bNewInitiallyPending ? 1 : 0,
		OldCleanupCount);
}

void UEpochTravelReporterSubsystem::HandleWorldCleanup(
	UWorld* World, bool bSessionEnded, bool bCleanupResources)
{
	if (!bProtocolActive || bTerminal || World == nullptr
		|| World != OldWorld.GetEvenIfUnreachable())
	{
		return;
	}
	++OldCleanupCount;
	OldApplyCountAtCleanup = OldDisplay.IsValid()
		? OldDisplay->GetApplyCount() : INDEX_NONE;
	UE_LOG(LogTemp, Display, TEXT(
		"EPOCH-TRAVEL-OLD-CLEANUP count=%d apply_count=%d session_end=%d "
		"cleanup_resources=%d"), OldCleanupCount, OldApplyCountAtCleanup,
		bSessionEnded ? 1 : 0, bCleanupResources ? 1 : 0);
}

void UEpochTravelReporterSubsystem::HandlePostWorldCleanup(
	UWorld* World, bool bSessionEnded, bool bCleanupResources)
{
	if (bProtocolActive && !bTerminal && World != nullptr
		&& World == OldWorld.GetEvenIfUnreachable())
	{
		++OldPostCleanupCount;
	}
}

void UEpochTravelReporterSubsystem::EmitGate(
	const TCHAR* GateName, bool bPassed) const
{
	UE_LOG(LogTemp, Display, TEXT("GATE[%s]=%s"), GateName,
		bPassed ? TEXT("PASS") : TEXT("FAIL"));
}

void UEpochTravelReporterSubsystem::FinishProtocol()
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	AEpochAssetDisplay* Destination = NewDisplay.Get();
	const bool bHarnessHealthy = bProtocolActive && bOldBegan && bNewBegan
		&& bOldInitiallyPending && bNewInitiallyPending
		&& !OldWorldPackage.IsEmpty() && !NewWorldPackage.IsEmpty()
		&& OldWorldPackage != NewWorldPackage && OldCleanupCount >= 1
		&& NewWorld.IsValid() && NewSubsystem.IsValid()
		&& Destination != nullptr;
	if (!bHarnessHealthy)
	{
		UE_LOG(LogTemp, Error, TEXT(
			"EPOCH-TRAVEL-HARNESS-ERROR reason=FINAL_PRECONDITION "
			"old=%d new=%d old_pending=%d new_pending=%d cleanup=%d "
			"worlds_distinct=%d destination=%d"), bOldBegan ? 1 : 0,
			bNewBegan ? 1 : 0, bOldInitiallyPending ? 1 : 0,
			bNewInitiallyPending ? 1 : 0, OldCleanupCount,
			OldWorldPackage != NewWorldPackage ? 1 : 0,
			Destination != nullptr ? 1 : 0);
		FPlatformMisc::RequestExit(false);
		return;
	}
	const bool bOldLifecycle = OldCleanupCount == 1
		&& OldPostCleanupCount == 1 && !OldSubsystem.IsValid();
	const bool bOldHarmless = OldApplyCountAtCleanup == 0
		&& Destination->GetAppliedRecordId() != OldExpectedId
		&& Destination->GetAppliedValue() != OldExpectedValue;
	const bool bNewResolved = Destination->GetAppliedRecordId() == NewExpectedId
		&& Destination->GetAppliedValue() == NewExpectedValue
		&& Destination->GetApplyCount() == 1;
	const bool bOldCollected = !OldWorld.IsValid() && !OldSubsystem.IsValid()
		&& !OldDisplay.IsValid() && OldRecordPath.ResolveObject() == nullptr;
	EmitGate(TEXT("OldWorldSubsystemDeinitializesOnce"), bOldLifecycle);
	EmitGate(TEXT("OldEpochCompletionCannotMutateNewWorld"), bOldHarmless);
	EmitGate(TEXT("NewWorldResolvesItsAssignedRecord"), bNewResolved);
	EmitGate(TEXT("TravelLeavesNoOldWorldRootedObjects"), bOldCollected);
	const int32 Passed = static_cast<int32>(bOldLifecycle)
		+ static_cast<int32>(bOldHarmless) + static_cast<int32>(bNewResolved)
		+ static_cast<int32>(bOldCollected);
	if (Passed == 4)
	{
		UE_LOG(LogTemp, Display, TEXT(
			"EPOCH-TRAVEL-SUCCEEDED gates=4/4 nonce=%s old_cleanup=1 "
			"old_post_cleanup=1 new_apply=1 old_collected=1"), *RunNonce);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT(
			"EPOCH-TRAVEL-FAILED kind=behavior gates=%d/4 nonce=%s "
			"old_cleanup=%d old_post=%d old_apply=%d new_id=%s "
			"new_value=%d new_apply=%d old_world_valid=%d old_subsystem_valid=%d "
			"old_display_valid=%d old_record_resident=%d"), Passed, *RunNonce,
			OldCleanupCount, OldPostCleanupCount, OldApplyCountAtCleanup,
			*Destination->GetAppliedRecordId().ToString(),
			Destination->GetAppliedValue(), Destination->GetApplyCount(),
			OldWorld.IsValid() ? 1 : 0, OldSubsystem.IsValid() ? 1 : 0,
			OldDisplay.IsValid() ? 1 : 0,
			OldRecordPath.ResolveObject() != nullptr ? 1 : 0);
	}
	FPlatformMisc::RequestExit(false);
}

void UEpochTravelReporterSubsystem::AbortHarness(const FString& Reason)
{
	if (bTerminal)
	{
		return;
	}
	bTerminal = true;
	UE_LOG(LogTemp, Error, TEXT("EPOCH-TRAVEL-HARNESS-ERROR reason=%s"),
		*Reason);
	FPlatformMisc::RequestExit(false);
}

AOldEpochStartFunctionalTest::AOldEpochStartFunctionalTest()
{
	PrimaryActorTick.bCanEverTick = false;
}

void AOldEpochStartFunctionalTest::BeginPlay()
{
	Super::BeginPlay();
	if (!IsProtocolEnabled())
	{
		return;
	}
	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UEpochTravelReporterSubsystem* Reporter = GameInstance
		? GameInstance->GetSubsystem<UEpochTravelReporterSubsystem>() : nullptr;
	UEpochAssetWorldSubsystem* Subsystem = World
		? World->GetSubsystem<UEpochAssetWorldSubsystem>() : nullptr;
	const bool bPending = !AssignedRecord.IsNull()
		&& AssignedRecord.Get() == nullptr;
	if (Reporter == nullptr || Subsystem == nullptr || Display == nullptr
		|| DestinationMap.IsNone())
	{
		if (Reporter)
		{
			Reporter->AbortHarness(TEXT("START_BINDINGS"));
		}
		return;
	}
	Reporter->BeginOldEpoch(World, Subsystem, Display,
		AssignedRecord.ToSoftObjectPath(), ExpectedRecordId,
		ExpectedRecordValue, bPending);
	if (!Reporter->IsProtocolActive())
	{
		return;
	}
	Subsystem->BeginEpochRequest(
		AssignedRecord.ToSoftObjectPath(), Display, true);
	GetWorldTimerManager().SetTimer(TravelTimer, this,
		&AOldEpochStartFunctionalTest::TravelToDestination, 0.35f, false);
}

void AOldEpochStartFunctionalTest::TravelToDestination()
{
	UGameplayStatics::OpenLevel(this, DestinationMap, true);
}

ANewEpochDestinationFunctionalTest::ANewEpochDestinationFunctionalTest()
{
	PrimaryActorTick.bCanEverTick = false;
}

void ANewEpochDestinationFunctionalTest::BeginPlay()
{
	Super::BeginPlay();
	if (!IsProtocolEnabled())
	{
		return;
	}
	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UEpochTravelReporterSubsystem* Reporter = GameInstance
		? GameInstance->GetSubsystem<UEpochTravelReporterSubsystem>() : nullptr;
	UEpochAssetWorldSubsystem* Subsystem = World
		? World->GetSubsystem<UEpochAssetWorldSubsystem>() : nullptr;
	const bool bPending = !AssignedRecord.IsNull()
		&& AssignedRecord.Get() == nullptr;
	if (Reporter == nullptr || Subsystem == nullptr || Display == nullptr)
	{
		if (Reporter)
		{
			Reporter->AbortHarness(TEXT("DESTINATION_BINDINGS"));
		}
		return;
	}
	Reporter->BeginNewEpoch(World, Subsystem, Display,
		AssignedRecord.ToSoftObjectPath(), ExpectedRecordId,
		ExpectedRecordValue, bPending);
	if (!Reporter->IsProtocolActive())
	{
		return;
	}
	Subsystem->BeginEpochRequest(
		AssignedRecord.ToSoftObjectPath(), Display, false);
	StartWorldSeconds = World->GetTimeSeconds();
	GetWorldTimerManager().SetTimer(ObserveTimer, this,
		&ANewEpochDestinationFunctionalTest::ObserveDestination, 0.10f, true);
}

void ANewEpochDestinationFunctionalTest::ObserveDestination()
{
	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UEpochTravelReporterSubsystem* Reporter = GameInstance
		? GameInstance->GetSubsystem<UEpochTravelReporterSubsystem>() : nullptr;
	if (World == nullptr || Reporter == nullptr || Display == nullptr)
	{
		if (Reporter)
		{
			Reporter->AbortHarness(TEXT("DESTINATION_OBSERVE"));
		}
		return;
	}
	const double Elapsed = World->GetTimeSeconds() - StartWorldSeconds;
	const bool bResolved = Display->GetAppliedRecordId() == ExpectedRecordId
		&& Display->GetAppliedValue() == ExpectedRecordValue;
	if (CollectionRequestedSeconds < 0.0 && (bResolved || Elapsed >= 4.0))
	{
		CollectionRequestedSeconds = World->GetTimeSeconds();
		if (GEngine)
		{
			GEngine->ForceGarbageCollection(true);
		}
		return;
	}
	if (CollectionRequestedSeconds >= 0.0
		&& World->GetTimeSeconds() - CollectionRequestedSeconds >= 1.5)
	{
		GetWorldTimerManager().ClearTimer(ObserveTimer);
		Reporter->FinishProtocol();
	}
}
