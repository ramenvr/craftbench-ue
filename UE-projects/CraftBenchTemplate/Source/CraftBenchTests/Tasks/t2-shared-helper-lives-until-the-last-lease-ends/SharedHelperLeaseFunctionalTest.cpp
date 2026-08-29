// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseFunctionalTest.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.h"
#include "UObject/ConstructorHelpers.h"
#include "UObject/Package.h"

ASharedHelperLeaseOwner::ASharedHelperLeaseOwner()
{
	PrimaryActorTick.bCanEverTick = false;
	Marker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeaseOwnerMarker"));
	SetRootComponent(Marker);
	Marker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Marker->SetWorldScale3D(FVector(0.35));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		Marker->SetStaticMesh(Sphere.Object);
	}
}

ASharedHelperLeaseFunctionalTest::ASharedHelperLeaseFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Tags.Add(FName(TEXT("CraftBench.SharedHelperLeaseFixture")));
}

void ASharedHelperLeaseFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World != nullptr ? World->GetGameInstance() : nullptr;
	USharedHelperLeaseSubsystem* Runtime =
		GameInstance != nullptr ? GameInstance->GetSubsystem<USharedHelperLeaseSubsystem>() : nullptr;
	if (World == nullptr || Runtime == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SHL-0 runtime_contract_available: game-instance subsystem unavailable"));
		return;
	}
	Subject = Runtime;

	const FGuid Seed = FGuid::NewGuid();
	const FString Digits = Seed.ToString(EGuidFormats::Digits);
	PrimaryKey = FName(*FString::Printf(TEXT("LeaseKey_%s"), *Digits.Left(12)));
	ControlKey = FName(*FString::Printf(TEXT("ControlKey_%s"), *Digits.Right(12)));
	OldVersion = 1 + static_cast<int32>(Seed.A & 0x1FFFFFFF);
	NewVersion = OldVersion + 1;
	OldPayload = FString::Printf(TEXT("old:%s:%d"), *Digits, OldVersion);
	NewPayload = FString::Printf(TEXT("new:%s:%d"), *Digits, NewVersion);
	ControlPayload = FString::Printf(TEXT("control:%s:%u"), *Digits, Seed.D);

	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	OwnerA = World->SpawnActor<ASharedHelperLeaseOwner>(
		ASharedHelperLeaseOwner::StaticClass(), FVector(0.0, -160.0, 90.0), FRotator::ZeroRotator, Spawn);
	OwnerB = World->SpawnActor<ASharedHelperLeaseOwner>(
		ASharedHelperLeaseOwner::StaticClass(), FVector(0.0, 0.0, 90.0), FRotator::ZeroRotator, Spawn);
	OwnerControl = World->SpawnActor<ASharedHelperLeaseOwner>(
		ASharedHelperLeaseOwner::StaticClass(), FVector(0.0, 160.0, 90.0), FRotator::ZeroRotator, Spawn);
	if (OwnerA == nullptr || OwnerB == nullptr || OwnerControl == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS: verifier-owned lease owner spawn failed"));
		return;
	}
	OwnerA->Tags.Add(FName(TEXT("SharedHelper.OwnerA")));
	OwnerB->Tags.Add(FName(TEXT("SharedHelper.OwnerB")));
	OwnerControl->Tags.Add(FName(TEXT("SharedHelper.OwnerControl")));

	LeaseA = Runtime->AcquireLease(OwnerA, PrimaryKey, OldVersion, OldPayload);
	LeaseB = Runtime->AcquireLease(OwnerB, PrimaryKey, OldVersion, OldPayload);
	LeaseControl = Runtime->AcquireLease(
		OwnerControl, ControlKey, OldVersion, ControlPayload);
	if (LeaseA == nullptr || LeaseB == nullptr || LeaseControl == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("SHL-0 runtime_contract_available: one or more initial leases are null"));
		return;
	}
	OldHelper = LeaseA->GetHelper();
	ControlHelper = LeaseControl->GetHelper();

	EpochWorldSeconds = static_cast<double>(World->GetTimeSeconds());
	SetCheckpointSchedule({
		EpochWorldSeconds + 0.15,
		EpochWorldSeconds + 0.45,
		EpochWorldSeconds + 0.75,
		EpochWorldSeconds + 1.05,
	});
	UE_LOG(LogTemp, Display,
		TEXT("[CB-SHARED-LEASE] prepared key=%s control_key=%s old_version=%d new_version=%d epoch=%.3f"),
		*PrimaryKey.ToString(), *ControlKey.ToString(), OldVersion, NewVersion, EpochWorldSeconds);
}

bool ASharedHelperLeaseFunctionalTest::ValidateInitialSharing(FString& OutDetail) const
{
	const USharedLeaseHelper* A = LeaseA != nullptr ? LeaseA->GetHelper() : nullptr;
	const USharedLeaseHelper* B = LeaseB != nullptr ? LeaseB->GetHelper() : nullptr;
	const USharedLeaseHelper* Control =
		LeaseControl != nullptr ? LeaseControl->GetHelper() : nullptr;
	if (!LeaseA->IsActive() || !LeaseB->IsActive() || A == nullptr || A != B)
	{
		OutDetail = TEXT("same key/version did not resolve to one active helper identity");
		return false;
	}
	if (Control == nullptr || Control == A)
	{
		OutDetail = TEXT("independent key reused the primary helper identity");
		return false;
	}
	if (A->Key != PrimaryKey || A->Version != OldVersion || A->Payload != OldPayload)
	{
		OutDetail = TEXT("primary helper does not carry exact live key/version/payload");
		return false;
	}
	if (Control->Key != ControlKey || Control->Version != OldVersion
		|| Control->Payload != ControlPayload)
	{
		OutDetail = TEXT("control helper does not carry exact independent facts");
		return false;
	}
	return true;
}

bool ASharedHelperLeaseFunctionalTest::ValidateFirstRelease(FString& OutDetail) const
{
	const USharedLeaseHelper* Old = OldHelper.Get();
	if (Old == nullptr || LeaseB == nullptr || !LeaseB->IsActive()
		|| LeaseB->GetHelper() != Old)
	{
		OutDetail = TEXT("shared helper did not survive while the second owner retained its lease");
		return false;
	}
	if (Old->Key != PrimaryKey || Old->Version != OldVersion || Old->Payload != OldPayload)
	{
		OutDetail = TEXT("surviving helper state changed after sibling release");
		return false;
	}
	return true;
}

bool ASharedHelperLeaseFunctionalTest::ValidateReplacement(FString& OutDetail) const
{
	const USharedLeaseHelper* Old = OldHelper.Get();
	const USharedLeaseHelper* Replacement =
		LeaseNew != nullptr ? LeaseNew->GetHelper() : nullptr;
	if (Old == nullptr || Replacement == nullptr || Replacement == Old)
	{
		OutDetail = TEXT("replacement version did not receive a fresh helper identity");
		return false;
	}
	if (Replacement->Key != PrimaryKey || Replacement->Version != NewVersion
		|| Replacement->Payload != NewPayload)
	{
		OutDetail = TEXT("replacement helper lacks exact new version/payload");
		return false;
	}
	if (Old->Version != OldVersion || Old->Payload != OldPayload)
	{
		OutDetail = TEXT("retired helper was mutated into the replacement");
		return false;
	}
	return true;
}

bool ASharedHelperLeaseFunctionalTest::ValidateRetiredCollected(FString& OutDetail) const
{
	if (OldHelper.IsValid())
	{
		OutDetail = TEXT("retired helper remains reachable after its final lease and full GC");
		return false;
	}
	if (!NewHelper.IsValid() || !ControlHelper.IsValid())
	{
		OutDetail = TEXT("current or unrelated helper was collected while its lease remained active");
		return false;
	}
	return true;
}

bool ASharedHelperLeaseFunctionalTest::ValidateFinalCollection(FString& OutDetail) const
{
	if (NewHelper.IsValid() || ControlHelper.IsValid())
	{
		OutDetail = TEXT("current/control helper remains reachable after each final lease and full GC");
		return false;
	}
	return true;
}

bool ASharedHelperLeaseFunctionalTest::ReleaseExact(
	TObjectPtr<USharedHelperLease>& Lease,
	FString& OutDetail)
{
	USharedHelperLeaseSubsystem* Runtime = Subject.Get();
	if (Runtime == nullptr || Lease == nullptr || !Runtime->ReleaseLease(Lease))
	{
		OutDetail = TEXT("release operation rejected an active verifier-owned lease");
		return false;
	}
	if (Lease->IsActive() || Lease->GetHelper() != nullptr)
	{
		OutDetail = TEXT("released token still exposes an active strong helper reference");
		return false;
	}
	Lease = nullptr;
	return true;
}

bool ASharedHelperLeaseFunctionalTest::RequestFixtureGc(FString& OutDetail)
{
	if (GEngine == nullptr)
	{
		OutDetail = TEXT("engine unavailable for fixture-owned GC request");
		return false;
	}
	USharedHelperGcWitness* Witness = NewObject<USharedHelperGcWitness>(
		GetTransientPackage(), NAME_None, RF_Transient);
	if (Witness == nullptr)
	{
		OutDetail = TEXT("could not allocate independent GC witness");
		return false;
	}
	GcWitness = Witness;
	GEngine->ForceGarbageCollection(true);
	return true;
}

bool ASharedHelperLeaseFunctionalTest::RequirePreviousGc(FString& OutDetail) const
{
	if (GcWitness.IsValid())
	{
		OutDetail = TEXT("independent unrooted witness survived; requested full GC did not complete");
		return false;
	}
	return true;
}

void ASharedHelperLeaseFunctionalTest::FailNamed(
	const TCHAR* Gate,
	const double TimeSeconds,
	const int32 CheckpointIndex,
	const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("At t=%.3fs (checkpoint %d): %s: %s"),
		TimeSeconds, CheckpointIndex, Gate, *Detail));
}

void ASharedHelperLeaseFunctionalTest::OnCheckpoint(
	const int32 CheckpointIndex,
	const double TimeSeconds)
{
	FString Detail;
	switch (CheckpointIndex)
	{
	case 0:
		if (!ValidateInitialSharing(Detail))
		{
			FailNamed(TEXT("SHL-1 SameKeySharesOneLiveHelper"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		if (!ReleaseExact(LeaseA, Detail) || !RequestFixtureGc(Detail))
		{
			FailNamed(TEXT("SHL-2 FirstReleaseDoesNotCollectSharedHelper"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		break;

	case 1:
		if (!RequirePreviousGc(Detail))
		{
			FinishTest(EFunctionalTestResult::Error,
				FString::Printf(TEXT("HARNESS: GC witness failure: %s"), *Detail));
			return;
		}
		if (!ValidateFirstRelease(Detail))
		{
			FailNamed(TEXT("SHL-2 FirstReleaseDoesNotCollectSharedHelper"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		LeaseNew = Subject->AcquireLease(OwnerA, PrimaryKey, NewVersion, NewPayload);
		NewHelper = LeaseNew != nullptr ? LeaseNew->GetHelper() : nullptr;
		if (!ValidateReplacement(Detail))
		{
			FailNamed(TEXT("SHL-3 ReplacementKeepsFreshIdentityAndPayload"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		if (!ReleaseExact(LeaseB, Detail) || !RequestFixtureGc(Detail))
		{
			FailNamed(TEXT("SHL-4 RetiredVersionCollectedAfterLastLease"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		break;

	case 2:
		if (!RequirePreviousGc(Detail))
		{
			FinishTest(EFunctionalTestResult::Error,
				FString::Printf(TEXT("HARNESS: GC witness failure: %s"), *Detail));
			return;
		}
		if (!ValidateRetiredCollected(Detail))
		{
			FailNamed(TEXT("SHL-4 RetiredVersionCollectedAfterLastLease"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		if (!ReleaseExact(LeaseNew, Detail) || !ReleaseExact(LeaseControl, Detail)
			|| !RequestFixtureGc(Detail))
		{
			FailNamed(TEXT("SHL-5 LastLeaseCollectsCurrentAndControl"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		break;

	case 3:
		if (!RequirePreviousGc(Detail))
		{
			FinishTest(EFunctionalTestResult::Error,
				FString::Printf(TEXT("HARNESS: GC witness failure: %s"), *Detail));
			return;
		}
		if (!ValidateFinalCollection(Detail))
		{
			FailNamed(TEXT("SHL-5 LastLeaseCollectsCurrentAndControl"), TimeSeconds, CheckpointIndex, Detail);
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("[CB-SHARED-LEASE] PASS checkpoints=4 key=%s old_version=%d new_version=%d old_valid=0 new_valid=0 control_valid=0 gc_witness=collected"),
			*PrimaryKey.ToString(), OldVersion, NewVersion);
		break;

	default:
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS: unexpected shared-helper checkpoint index"));
		break;
	}
}
