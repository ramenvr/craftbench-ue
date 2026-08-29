// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT.

#include "BundleLeaseFunctionalTest.h"

#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/AssetManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseAssets.h"
#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.h"

struct FBundlePayloadPin
{
	FName BundleName;
	FSoftObjectPath PayloadPath;
	FName PayloadIdentity;
	FSoftObjectPath HiddenPath;
	double HiddenMarker;
};

struct FBundleRecordPin
{
	FPrimaryAssetId Id;
	FSoftObjectPath RecordPath;
	FBundlePayloadPin Quartz;
	FBundlePayloadPin Violet;

	const FBundlePayloadPin* FindBundle(FName BundleName) const
	{
		if (Quartz.BundleName == BundleName)
		{
			return &Quartz;
		}
		if (Violet.BundleName == BundleName)
		{
			return &Violet;
		}
		return nullptr;
	}
};

namespace
{
	static const FName HostTag(TEXT("BundleLease.Host"));
	static const FName ConsumerATag(TEXT("BundleLease.ConsumerA"));
	static const FName ConsumerBTag(TEXT("BundleLease.ConsumerB"));
	static const FName ScenarioTag(TEXT("BundleLease.Scenario"));
	static const FName PayloadIdentityTag(TEXT("PayloadIdentity"));
	static const FName HiddenMarkerTag(TEXT("AuthoredMarker"));
	static const FPrimaryAssetType RecordType(TEXT("BundleLeaseRecord"));

	constexpr double PollSeconds = 0.10;
	constexpr double PhaseTimeoutSeconds = 3.0;
	constexpr double FirstReleaseHoldSeconds = 0.30;
	constexpr double StableSeconds = 0.25;
	constexpr double SentinelSeconds = 11.0;

	FSoftObjectPath TaskPath(const TCHAR* AssetName)
	{
		return FSoftObjectPath(FString::Printf(
			TEXT("/Game/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/Records/%s.%s"),
			AssetName,
			AssetName));
	}

	FBundlePayloadPin MakePayload(
		const TCHAR* RecordStem,
		const TCHAR* Bundle,
		FName Identity,
		double Marker)
	{
		const FString PayloadName = FString::Printf(TEXT("DA_%s_%s_Payload"), RecordStem, Bundle);
		const FString HiddenName = FString::Printf(TEXT("DA_%s_%s_Hidden"), RecordStem, Bundle);
		return {
			FName(Bundle),
			TaskPath(*PayloadName),
			Identity,
			TaskPath(*HiddenName),
			Marker
		};
	}

	const TArray<FBundleRecordPin>& RecordPins()
	{
		static const TArray<FBundleRecordPin> Pins = {
			{
				FPrimaryAssetId(RecordType, FName(TEXT("DA_BundleRecord_Quartz"))),
				TaskPath(TEXT("DA_BundleRecord_Quartz")),
				MakePayload(TEXT("Quartz"), TEXT("Quartz"), TEXT("Quartz.Q"), 137.125),
				MakePayload(TEXT("Quartz"), TEXT("Violet"), TEXT("Quartz.V"), -42.375)
			},
			{
				FPrimaryAssetId(RecordType, FName(TEXT("DA_BundleRecord_Violet"))),
				TaskPath(TEXT("DA_BundleRecord_Violet")),
				MakePayload(TEXT("Violet"), TEXT("Quartz"), TEXT("Violet.Q"), 803.625),
				MakePayload(TEXT("Violet"), TEXT("Violet"), TEXT("Violet.V"), 19.875)
			},
			{
				FPrimaryAssetId(RecordType, FName(TEXT("DA_BundleRecord_Amber"))),
				TaskPath(TEXT("DA_BundleRecord_Amber")),
				MakePayload(TEXT("Amber"), TEXT("Quartz"), TEXT("Amber.Q"), -611.25),
				MakePayload(TEXT("Amber"), TEXT("Violet"), TEXT("Amber.V"), 271.75)
			}
		};
		return Pins;
	}

	const FBundleRecordPin* FindPin(const FPrimaryAssetId& Id)
	{
		return RecordPins().FindByPredicate(
			[&Id](const FBundleRecordPin& Pin) { return Pin.Id == Id; });
	}

	template <typename TActor>
	TActor* FindExactlyOne(UWorld* World, FName Tag, FString& OutError)
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, Tag, Found);
		if (Found.Num() != 1)
		{
			OutError = FString::Printf(TEXT("tag %s cardinality was %d, expected 1"), *Tag.ToString(), Found.Num());
			return nullptr;
		}
		TActor* Typed = Cast<TActor>(Found[0]);
		if (!Typed)
		{
			OutError = FString::Printf(TEXT("tag %s resolved the wrong actor class"), *Tag.ToString());
		}
		return Typed;
	}

	bool IsResident(const FSoftObjectPath& Path)
	{
		return Path.ResolveObject() != nullptr;
	}

	void MakeSecondaryCollectableInPIE(const FSoftObjectPath& Path)
	{
		// Editor GC deliberately keeps RF_Standalone objects. A packaged Game does
		// not. Clear that editor-only keep flag after the exact secondary has been
		// observed resident so later GC still distinguishes an engine handle leak
		// from a correctly released bundle without changing any disk asset.
		if (GIsEditor)
		{
			if (UObject* Object = Path.ResolveObject())
			{
				Object->ClearFlags(RF_Standalone);
			}
		}
	}

	bool ExactBundleState(
		UAssetManager& Manager,
		const FPrimaryAssetId& Id,
		FName ExpectedBundle,
		bool bExpectBundle,
		bool bForceCurrent,
		FString& OutError)
	{
		TArray<FName> Bundles;
		const TSharedPtr<FStreamableHandle> Handle =
			Manager.GetPrimaryAssetHandle(Id, bForceCurrent, &Bundles);
		if (!Handle.IsValid())
		{
			OutError = FString::Printf(TEXT("managed handle for %s was absent"), *Id.ToString());
			return false;
		}
		if (bExpectBundle)
		{
			if (Bundles.Num() != 1 || Bundles[0] != ExpectedBundle)
			{
				OutError = FString::Printf(
					TEXT("bundle state for %s was [%s], expected exactly [%s]"),
					*Id.ToString(),
					*FString::JoinBy(Bundles, TEXT(","), [](FName Value) { return Value.ToString(); }),
					*ExpectedBundle.ToString());
				return false;
			}
		}
		else if (!Bundles.IsEmpty())
		{
			OutError = FString::Printf(
				TEXT("bundle state for %s retained [%s], expected no bundles"),
				*Id.ToString(),
				*FString::JoinBy(Bundles, TEXT(","), [](FName Value) { return Value.ToString(); }));
			return false;
		}
		return true;
	}
}

ABundleLeaseScenario::ABundleLeaseScenario()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(ScenarioTag);
}

ABundleLeaseFunctionalTest::ABundleLeaseFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ABundleLeaseFunctionalTest::FailSelected(double TimeSeconds, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("SelectedBundleAloneBecomesResident at t=%.2fs: %s"), TimeSeconds, *Detail));
}

void ABundleLeaseFunctionalTest::FailUnselected(double TimeSeconds, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("UnselectedBundleStaysNonResident at t=%.2fs: %s"), TimeSeconds, *Detail));
}

void ABundleLeaseFunctionalTest::FailFirstRelease(double TimeSeconds, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("OneReleaseKeepsSharedDependencyAlive at t=%.2fs: %s"), TimeSeconds, *Detail));
}

void ABundleLeaseFunctionalTest::FailLastRelease(double TimeSeconds, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, FString::Printf(
		TEXT("LastReleaseUnloadsOnlyManagedBundle at t=%.2fs: %s"), TimeSeconds, *Detail));
}

bool ABundleLeaseFunctionalTest::ValidateProtectedAssets(double TimeSeconds)
{
	UAssetManager* Manager = UAssetManager::GetIfInitialized();
	if (!Manager)
	{
		FailSelected(TimeSeconds, TEXT("Asset Manager was not initialized before PrepareTest"));
		return false;
	}
	IAssetRegistry& Registry = FAssetRegistryModule::GetRegistry();
	TSet<FSoftObjectPath> UniquePaths;
	for (const FBundleRecordPin& Pin : RecordPins())
	{
		if (Manager->GetPrimaryAssetPath(Pin.Id) != Pin.RecordPath)
		{
			FailSelected(TimeSeconds, FString::Printf(TEXT("protected primary identity/path mismatch for %s"), *Pin.Id.ToString()));
			return false;
		}
		FAssetData RecordData;
		if (!Manager->GetPrimaryAssetData(Pin.Id, RecordData)
			|| RecordData.AssetClassPath != UBundleLeaseRecord::StaticClass()->GetClassPathName())
		{
			FailSelected(TimeSeconds, FString::Printf(TEXT("protected primary metadata/class mismatch for %s"), *Pin.Id.ToString()));
			return false;
		}
		if (Manager->GetPrimaryAssetHandle(Pin.Id).IsValid())
		{
			FailUnselected(TimeSeconds, FString::Printf(TEXT("%s had a managed handle before any lease"), *Pin.Id.ToString()));
			return false;
		}

		UniquePaths.Add(Pin.RecordPath);
		for (const FBundlePayloadPin* Bundle : { &Pin.Quartz, &Pin.Violet })
		{
			TSet<FSoftObjectPath> LoadSet;
			if (!Manager->GetPrimaryAssetLoadSet(LoadSet, Pin.Id, { Bundle->BundleName }, false)
				|| LoadSet.Num() != 2
				|| !LoadSet.Contains(Pin.RecordPath)
				|| !LoadSet.Contains(Bundle->PayloadPath))
			{
				FailSelected(TimeSeconds, FString::Printf(
					TEXT("bundle metadata for %s/%s did not resolve exactly record+payload"),
					*Pin.Id.ToString(), *Bundle->BundleName.ToString()));
				return false;
			}

			const FAssetData PayloadData = Registry.GetAssetByObjectPath(Bundle->PayloadPath, true);
			const FAssetData HiddenData = Registry.GetAssetByObjectPath(Bundle->HiddenPath, true);
			FName ActualIdentity;
			double ActualMarker = 0.0;
			if (!PayloadData.IsValid()
				|| PayloadData.AssetClassPath != UBundleLeasePayload::StaticClass()->GetClassPathName()
				|| !PayloadData.GetTagValue(PayloadIdentityTag, ActualIdentity)
				|| ActualIdentity != Bundle->PayloadIdentity
				|| !HiddenData.IsValid()
				|| HiddenData.AssetClassPath != UBundleLeaseHiddenDependency::StaticClass()->GetClassPathName()
				|| !HiddenData.GetTagValue(HiddenMarkerTag, ActualMarker)
				|| !FMath::IsNearlyEqual(ActualMarker, Bundle->HiddenMarker, 0.0001))
			{
				FailSelected(TimeSeconds, FString::Printf(TEXT("protected payload/dependency metadata mismatch for %s"), *Bundle->PayloadPath.ToString()));
				return false;
			}
			UniquePaths.Add(Bundle->PayloadPath);
			UniquePaths.Add(Bundle->HiddenPath);
		}
	}
	if (UniquePaths.Num() != 15)
	{
		FailSelected(TimeSeconds, FString::Printf(TEXT("protected object paths were not distinct: %d/15"), UniquePaths.Num()));
		return false;
	}
	for (const FSoftObjectPath& Path : UniquePaths)
	{
		if (IsResident(Path))
		{
			FailUnselected(TimeSeconds, FString::Printf(TEXT("protected object was resident before the first lease: %s"), *Path.ToString()));
			return false;
		}
	}
	return true;
}

bool ABundleLeaseFunctionalTest::ValidateManagedBundleState(double TimeSeconds, bool bExpectSelectedBundle)
{
	UAssetManager* Manager = UAssetManager::GetIfInitialized();
	FString Error;
	if (!Manager || !SelectedPin || !ExactBundleState(
		*Manager,
		SelectedPin->Id,
		Scenario->SelectedBundleName,
		bExpectSelectedBundle,
		false,
		Error))
	{
		if (bExpectSelectedBundle)
		{
			FailSelected(TimeSeconds, Error.IsEmpty() ? TEXT("Asset Manager unavailable") : Error);
		}
		else
		{
			FailLastRelease(TimeSeconds, Error.IsEmpty() ? TEXT("Asset Manager unavailable") : Error);
		}
		return false;
	}
	for (const FBundleRecordPin& Pin : RecordPins())
	{
		if (Pin.Id != SelectedPin->Id && Manager->GetPrimaryAssetHandle(Pin.Id).IsValid())
		{
			FailUnselected(TimeSeconds, FString::Printf(TEXT("unselected primary asset acquired a managed handle: %s"), *Pin.Id.ToString()));
			return false;
		}
	}
	return true;
}

bool ABundleLeaseFunctionalTest::ValidateUnselectedNonResident(double TimeSeconds)
{
	if (!SelectedPin || !Scenario)
	{
		FailUnselected(TimeSeconds, TEXT("selected world facts are unavailable"));
		return false;
	}
	const FBundlePayloadPin* SelectedBundle = SelectedPin->FindBundle(Scenario->SelectedBundleName);
	for (const FBundleRecordPin& Pin : RecordPins())
	{
		if (Pin.Id != SelectedPin->Id && IsResident(Pin.RecordPath))
		{
			FailUnselected(TimeSeconds, FString::Printf(TEXT("unselected primary record became resident: %s"), *Pin.RecordPath.ToString()));
			return false;
		}
		for (const FBundlePayloadPin* Bundle : { &Pin.Quartz, &Pin.Violet })
		{
			if (Bundle != SelectedBundle && (IsResident(Bundle->PayloadPath) || IsResident(Bundle->HiddenPath)))
			{
				FailUnselected(TimeSeconds, FString::Printf(
					TEXT("unselected payload/dependency became resident: %s / %s"),
					*Bundle->PayloadPath.ToString(), *Bundle->HiddenPath.ToString()));
				return false;
			}
		}
	}
	return true;
}

bool ABundleLeaseFunctionalTest::ValidateSelectedResident(double TimeSeconds, bool bRequireBothReady)
{
	if (!SelectedPin || !Scenario || !Host || !Host->LeaseManager)
	{
		FailSelected(TimeSeconds, TEXT("selected pin/scenario/host contract is unavailable"));
		return false;
	}
	const FBundlePayloadPin* Bundle = SelectedPin->FindBundle(Scenario->SelectedBundleName);
	if (!Bundle || !IsResident(SelectedPin->RecordPath)
		|| !IsResident(Bundle->PayloadPath) || !IsResident(Bundle->HiddenPath))
	{
		FailSelected(TimeSeconds, TEXT("selected record, payload, and hidden dependency were not all resident"));
		return false;
	}
	MakeSecondaryCollectableInPIE(Bundle->PayloadPath);
	MakeSecondaryCollectableInPIE(Bundle->HiddenPath);
	const int32 ExpectedLeases = bRequireBothReady ? 2 : 1;
	if (Host->LeaseManager->GetLeaseCount(SelectedPin->Id, Scenario->SelectedBundleName) != ExpectedLeases
		|| !Host->LeaseManager->HasLease(ConsumerA)
		|| (bRequireBothReady && !Host->LeaseManager->HasLease(ConsumerB)))
	{
		FailSelected(TimeSeconds, FString::Printf(TEXT("shared lease telemetry did not report %d exact owners"), ExpectedLeases));
		return false;
	}
	if (!ConsumerA->bBundleReady || (bRequireBothReady && !ConsumerB->bBundleReady))
	{
		FailSelected(TimeSeconds, TEXT("consumer completion state did not match the selected resident bundle"));
		return false;
	}
	return ValidateManagedBundleState(TimeSeconds, true) && ValidateUnselectedNonResident(TimeSeconds);
}

void ABundleLeaseFunctionalTest::RequestGarbageCollection()
{
	if (GEngine)
	{
		GEngine->ForceGarbageCollection(true);
	}
}

void ABundleLeaseFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	UWorld* World = GetWorld();
	const double Now = World ? World->GetTimeSeconds() : -1.0;
	if (!World)
	{
		FailSelected(Now, TEXT("PIE world was unavailable"));
		return;
	}

	FString Error;
	Host = FindExactlyOne<ABundleLeaseHost>(World, HostTag, Error);
	ConsumerA = FindExactlyOne<ABundleLeaseConsumer>(World, ConsumerATag, Error);
	ConsumerB = FindExactlyOne<ABundleLeaseConsumer>(World, ConsumerBTag, Error);
	Scenario = FindExactlyOne<ABundleLeaseScenario>(World, ScenarioTag, Error);
	if (!Host || !ConsumerA || !ConsumerB || !Scenario || ConsumerA == ConsumerB)
	{
		FailSelected(Now, Error.IsEmpty() ? TEXT("host/consumer/scenario identities were invalid") : Error);
		return;
	}
	SelectedPin = FindPin(Scenario->SelectedPrimaryAssetId);
	if (!SelectedPin || !SelectedPin->FindBundle(Scenario->SelectedBundleName))
	{
		FailSelected(Now, TEXT("world scenario did not select a protected primary id and exact authored bundle"));
		return;
	}
	if (!Host->LeaseManager || ConsumerA->LeaseHost != Host || ConsumerB->LeaseHost != Host
		|| ConsumerA->bBundleReady || ConsumerB->bBundleReady
		|| Host->LeaseManager->HasLease(ConsumerA) || Host->LeaseManager->HasLease(ConsumerB))
	{
		FailSelected(Now, TEXT("initial supplied host/consumer public contract was altered or eager"));
		return;
	}
	if (!ValidateProtectedAssets(Now))
	{
		return;
	}

	ConsumerA->RequestedPrimaryAssetId = SelectedPin->Id;
	ConsumerB->RequestedPrimaryAssetId = SelectedPin->Id;
	ConsumerA->RequestedBundleName = Scenario->SelectedBundleName;
	ConsumerB->RequestedBundleName = Scenario->SelectedBundleName;

	TArray<double> Schedule;
	for (double Offset = PollSeconds; Offset < SentinelSeconds; Offset += PollSeconds)
	{
		Schedule.Add(Now + Offset);
	}
	SentinelCheckpointIndex = Schedule.Num();
	Schedule.Add(Now + SentinelSeconds);
	SetCheckpointSchedule(Schedule);
	Phase = EPhase::AcquireFirst;
}

void ABundleLeaseFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex == SentinelCheckpointIndex)
	{
		FailLastRelease(TimeSeconds, TEXT("lease lifecycle did not finish before the final scheduled sentinel"));
		return;
	}
	if (!ValidateUnselectedNonResident(TimeSeconds))
	{
		return;
	}

	switch (Phase)
	{
		case EPhase::AcquireFirst:
			ConsumerA->AcquireAssignedBundle();
			PhaseStartedAt = TimeSeconds;
			if (!Host->LeaseManager->HasLease(ConsumerA)
				|| Host->LeaseManager->GetLeaseCount(SelectedPin->Id, Scenario->SelectedBundleName) != 1
				|| ConsumerB->bBundleReady)
			{
				FailSelected(TimeSeconds, TEXT("first acquire did not establish exactly one manager-owned lease in the same call"));
				return;
			}
			if (!ValidateManagedBundleState(TimeSeconds, true))
			{
				return;
			}
			if (!ValidateUnselectedNonResident(TimeSeconds))
			{
				return;
			}
			Phase = EPhase::WaitFirst;
			return;

		case EPhase::WaitFirst:
			if (ConsumerA->bBundleReady)
			{
				if (!ValidateSelectedResident(TimeSeconds, false))
				{
					return;
				}
				ConsumerB->AcquireAssignedBundle();
				PhaseStartedAt = TimeSeconds;
				if (!Host->LeaseManager->HasLease(ConsumerB)
					|| Host->LeaseManager->GetLeaseCount(SelectedPin->Id, Scenario->SelectedBundleName) != 2)
				{
					FailSelected(TimeSeconds, TEXT("second acquire did not join the exact shared managed lease"));
					return;
				}
				if (!ValidateManagedBundleState(TimeSeconds, true))
				{
					return;
				}
				if (!ValidateUnselectedNonResident(TimeSeconds))
				{
					return;
				}
				Phase = EPhase::WaitSecond;
				return;
			}
			if (TimeSeconds - PhaseStartedAt >= PhaseTimeoutSeconds)
			{
				FailSelected(TimeSeconds, TEXT("first consumer did not complete within 3.0 world seconds"));
			}
			return;

		case EPhase::WaitSecond:
			if (ConsumerB->bBundleReady)
			{
				if (!ValidateSelectedResident(TimeSeconds, true))
				{
					return;
				}
				ABundleLeaseConsumer* First = Scenario->bReleaseAFirst ? ConsumerA : ConsumerB;
				First->ReleaseAssignedBundle();
				PhaseStartedAt = TimeSeconds;
				RequestGarbageCollection();
				Phase = EPhase::WaitAfterFirstRelease;
				return;
			}
			if (TimeSeconds - PhaseStartedAt >= PhaseTimeoutSeconds)
			{
				FailSelected(TimeSeconds, TEXT("second consumer did not complete within 3.0 world seconds"));
			}
			return;

		case EPhase::WaitAfterFirstRelease:
			if (TimeSeconds - PhaseStartedAt < FirstReleaseHoldSeconds)
			{
				return;
			}
			{
				ABundleLeaseConsumer* First = Scenario->bReleaseAFirst ? ConsumerA : ConsumerB;
				ABundleLeaseConsumer* Remaining = Scenario->bReleaseAFirst ? ConsumerB : ConsumerA;
				const FBundlePayloadPin* Bundle = SelectedPin->FindBundle(Scenario->SelectedBundleName);
				if (!Bundle || First->bBundleReady || !Remaining->bBundleReady
					|| IsResident(Bundle->PayloadPath) == false || IsResident(Bundle->HiddenPath) == false
					|| Host->LeaseManager->GetLeaseCount(SelectedPin->Id, Scenario->SelectedBundleName) != 1
					|| Host->LeaseManager->HasLease(First) || !Host->LeaseManager->HasLease(Remaining))
				{
					FailFirstRelease(TimeSeconds, TEXT("first release changed residency or the remaining exact owner"));
					return;
				}
				UAssetManager* Manager = UAssetManager::GetIfInitialized();
				FString BundleError;
				if (!Manager || !ExactBundleState(
					*Manager,
					SelectedPin->Id,
					Scenario->SelectedBundleName,
					true,
					false,
					BundleError))
				{
					FailFirstRelease(TimeSeconds, BundleError.IsEmpty()
						? TEXT("Asset Manager unavailable after first release")
						: BundleError);
					return;
				}
				Remaining->ReleaseAssignedBundle();
				PhaseStartedAt = TimeSeconds;
				RequestGarbageCollection();
				Phase = EPhase::WaitAfterLastRelease;
				return;
			}

		case EPhase::WaitAfterLastRelease:
		{
			RequestGarbageCollection();
			const FBundlePayloadPin* Bundle = SelectedPin->FindBundle(Scenario->SelectedBundleName);
			FString BundleError;
			UAssetManager* Manager = UAssetManager::GetIfInitialized();
			const bool bBundleRemoved = Manager && ExactBundleState(
				*Manager, SelectedPin->Id, Scenario->SelectedBundleName, false, false, BundleError);
			const bool bPayloadGone = Bundle && !IsResident(Bundle->PayloadPath) && !IsResident(Bundle->HiddenPath);
			const bool bNoLeases = Host->LeaseManager->GetLeaseCount(SelectedPin->Id, Scenario->SelectedBundleName) == 0
				&& !Host->LeaseManager->HasLease(ConsumerA)
				&& !Host->LeaseManager->HasLease(ConsumerB)
				&& !ConsumerA->bBundleReady && !ConsumerB->bBundleReady;
			if (bBundleRemoved && bPayloadGone && bNoLeases)
			{
				PhaseStartedAt = TimeSeconds;
				Phase = EPhase::StableAfterUnload;
				return;
			}
			if (TimeSeconds - PhaseStartedAt >= PhaseTimeoutSeconds)
			{
				FailLastRelease(TimeSeconds, FString::Printf(
					TEXT("last release did not remove only the selected bundle: bundle='%s' payload_gone=%d leases_clear=%d"),
					*BundleError, bPayloadGone ? 1 : 0, bNoLeases ? 1 : 0));
			}
			return;
		}

		case EPhase::StableAfterUnload:
			if (!ValidateManagedBundleState(TimeSeconds, false))
			{
				return;
			}
			if (TimeSeconds - PhaseStartedAt >= StableSeconds)
			{
				FinishTest(EFunctionalTestResult::Succeeded,
					TEXT("Bundle lease gates passed: exact bundle, unselected isolation, shared first release, exact last release."));
			}
			return;
	}
}

ABundleLeaseAdmissionFunctionalTest::ABundleLeaseAdmissionFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

bool ABundleLeaseAdmissionFunctionalTest::FailAdmission(const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed, TEXT("BUNDLE-LEASE-ADMISSION-FAIL ") + Detail);
	return false;
}

void ABundleLeaseAdmissionFunctionalTest::OnAdmissionLoadComplete()
{
	bLoadComplete = true;
	++LoadCompleteCallbackCount;
	LoadCompletedAtSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : -1.0;
	UE_LOG(LogTemp, Display,
		TEXT("BUNDLE-LEASE-ADMISSION-PHASE load_complete=1 callbacks=%d world_time=%.6f"),
		LoadCompleteCallbackCount,
		LoadCompletedAtSeconds);
}

FString ABundleLeaseAdmissionFunctionalTest::DescribeAdmissionState() const
{
	const UAssetManager* Manager = UAssetManager::GetIfInitialized();
	TArray<FName> EffectiveBundles;
	TArray<FName> CurrentBundles;
	const TSharedPtr<FStreamableHandle> EffectiveHandle = Manager
		? Manager->GetPrimaryAssetHandle(SelectedId, false, &EffectiveBundles)
		: nullptr;
	const TSharedPtr<FStreamableHandle> CurrentHandle = Manager
		? Manager->GetPrimaryAssetHandle(SelectedId, true, &CurrentBundles)
		: nullptr;
	const auto JoinBundles = [](const TArray<FName>& Bundles)
	{
		return Bundles.IsEmpty()
			? FString(TEXT("none"))
			: FString::JoinBy(Bundles, TEXT(","), [](FName Value) { return Value.ToString(); });
	};
	return FString::Printf(
		TEXT("load_requested=%d load_complete=%d callbacks=%d removal_requested=%d ")
		TEXT("request_t=%.6f complete_t=%.6f removal_t=%.6f local_handle=%d local_loading=%d local_complete=%d ")
		TEXT("effective_handle=%d effective_bundles=%s current_handle=%d current_bundles=%s ")
		TEXT("selected_payload=%d selected_hidden=%d unselected_payload=%d unselected_hidden=%d"),
		bLoadRequested ? 1 : 0,
		bLoadComplete ? 1 : 0,
		LoadCompleteCallbackCount,
		bRemovalRequested ? 1 : 0,
		LoadRequestedAtSeconds,
		LoadCompletedAtSeconds,
		RemovalRequestedAtSeconds,
		AdmissionHandle.IsValid() ? 1 : 0,
		AdmissionHandle.IsValid() && AdmissionHandle->IsLoadingInProgress() ? 1 : 0,
		AdmissionHandle.IsValid() && AdmissionHandle->HasLoadCompleted() ? 1 : 0,
		EffectiveHandle.IsValid() ? 1 : 0,
		*JoinBundles(EffectiveBundles),
		CurrentHandle.IsValid() ? 1 : 0,
		*JoinBundles(CurrentBundles),
		IsResident(SelectedPayload) ? 1 : 0,
		IsResident(SelectedHidden) ? 1 : 0,
		IsResident(UnselectedPayload) ? 1 : 0,
		IsResident(UnselectedHidden) ? 1 : 0);
}

void ABundleLeaseAdmissionFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	AdmissionHandle.Reset();
	bLoadRequested = false;
	bLoadComplete = false;
	bRemovalRequested = false;
	LoadCompleteCallbackCount = 0;
	LoadRequestedAtSeconds = -1.0;
	LoadCompletedAtSeconds = -1.0;
	RemovalRequestedAtSeconds = -1.0;
	SentinelCheckpointIndex = INDEX_NONE;
	UWorld* World = GetWorld();
	const double Now = World ? World->GetTimeSeconds() : -1.0;
	if (!World)
	{
		FailAdmission(TEXT("PIE world unavailable"));
		return;
	}
	FString Error;
	ABundleLeaseScenario* AdmissionScenario = FindExactlyOne<ABundleLeaseScenario>(World, ScenarioTag, Error);
	const FBundleRecordPin* Pin = AdmissionScenario ? FindPin(AdmissionScenario->SelectedPrimaryAssetId) : nullptr;
	const FBundlePayloadPin* Bundle = Pin ? Pin->FindBundle(AdmissionScenario->SelectedBundleName) : nullptr;
	const FBundlePayloadPin* Other = Pin
		? Pin->FindBundle(AdmissionScenario->SelectedBundleName == TEXT("Quartz") ? FName(TEXT("Violet")) : FName(TEXT("Quartz")))
		: nullptr;
	if (!Pin || !Bundle || !Other)
	{
		FailAdmission(Error.IsEmpty() ? TEXT("scenario selection invalid") : Error);
		return;
	}
	SelectedId = Pin->Id;
	SelectedBundle = Bundle->BundleName;
	SelectedPayload = Bundle->PayloadPath;
	SelectedHidden = Bundle->HiddenPath;
	UnselectedPayload = Other->PayloadPath;
	UnselectedHidden = Other->HiddenPath;
	UAssetManager* Manager = UAssetManager::GetIfInitialized();
	TSet<FSoftObjectPath> LoadSet;
	if (!Manager || Manager->GetPrimaryAssetHandle(SelectedId).IsValid()
		|| IsResident(SelectedPayload) || IsResident(SelectedHidden)
		|| IsResident(UnselectedPayload) || IsResident(UnselectedHidden)
		|| !Manager->GetPrimaryAssetLoadSet(LoadSet, SelectedId, { SelectedBundle }, false)
		|| LoadSet.Num() != 2 || !LoadSet.Contains(Pin->RecordPath) || !LoadSet.Contains(SelectedPayload))
	{
		FailAdmission(TEXT("cold exact bundle metadata/residency preflight failed"));
		return;
	}
	TArray<double> Schedule;
	for (double Offset = PollSeconds; Offset < 6.0; Offset += PollSeconds)
	{
		Schedule.Add(Now + Offset);
	}
	SentinelCheckpointIndex = Schedule.Num();
	Schedule.Add(Now + 6.0);
	SetCheckpointSchedule(Schedule);
}

void ABundleLeaseAdmissionFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex == SentinelCheckpointIndex)
	{
		FailAdmission(TEXT("world-clock sentinel reached ") + DescribeAdmissionState());
		return;
	}
	UAssetManager* Manager = UAssetManager::GetIfInitialized();
	if (!Manager)
	{
		FailAdmission(TEXT("Asset Manager unavailable"));
		return;
	}
	if (!bLoadRequested && !bLoadComplete && !bRemovalRequested)
	{
		bLoadRequested = true;
		LoadRequestedAtSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : -1.0;
		AdmissionHandle = Manager->LoadPrimaryAsset(
			SelectedId,
			{ SelectedBundle },
			FStreamableDelegate::CreateUObject(this, &ABundleLeaseAdmissionFunctionalTest::OnAdmissionLoadComplete));
		FString Error;
		if (!ExactBundleState(*Manager, SelectedId, SelectedBundle, true, false, Error))
		{
			FailAdmission(TEXT("same-call managed bundle gate: ") + Error);
			return;
		}
		UE_LOG(LogTemp, Display,
			TEXT("BUNDLE-LEASE-ADMISSION-PHASE load_requested=1 world_time=%.6f handle=%d loading=%d complete=%d"),
			LoadRequestedAtSeconds,
			AdmissionHandle.IsValid() ? 1 : 0,
			AdmissionHandle.IsValid() && AdmissionHandle->IsLoadingInProgress() ? 1 : 0,
			AdmissionHandle.IsValid() && AdmissionHandle->HasLoadCompleted() ? 1 : 0);
		return;
	}
	if (!bRemovalRequested)
	{
		if (!bLoadComplete)
		{
			return;
		}
		if (!IsResident(SelectedPayload) || !IsResident(SelectedHidden)
			|| IsResident(UnselectedPayload) || IsResident(UnselectedHidden))
		{
			FailAdmission(TEXT("selected/unselected residency after completion was wrong"));
			return;
		}
		MakeSecondaryCollectableInPIE(SelectedPayload);
		MakeSecondaryCollectableInPIE(SelectedHidden);
		AdmissionHandle.Reset();
		Manager->ChangeBundleStateForPrimaryAssets({ SelectedId }, {}, { SelectedBundle }, false);
		bRemovalRequested = true;
		RemovalRequestedAtSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : -1.0;
		UE_LOG(LogTemp, Display,
			TEXT("BUNDLE-LEASE-ADMISSION-PHASE removal_requested=1 world_time=%.6f %s"),
			RemovalRequestedAtSeconds,
			*DescribeAdmissionState());
		if (GEngine)
		{
			GEngine->ForceGarbageCollection(true);
		}
		return;
	}
	if (GEngine)
	{
		GEngine->ForceGarbageCollection(true);
	}
	FString Error;
	if (ExactBundleState(*Manager, SelectedId, SelectedBundle, false, false, Error)
		&& !IsResident(SelectedPayload) && !IsResident(SelectedHidden)
		&& !IsResident(UnselectedPayload) && !IsResident(UnselectedHidden))
	{
		FinishTest(EFunctionalTestResult::Succeeded,
			TEXT("BUNDLE-LEASE-ADMISSION-PASS exact_bundle=1 hidden_dependency=1 unselected_nonresident=1 remove_bundle=1"));
	}
}
