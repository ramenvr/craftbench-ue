// Copyright CraftBench. All Rights Reserved.

#include "BundleLeaseAssetAuthoring.h"

#include "BundleLeaseFunctionalTest.h"
#include "Editor.h"
#include "Engine/AssetManager.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseAssets.h"
#include "Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.h"

namespace
{
	struct FAuthorPayload
	{
		FName Bundle;
		FString PayloadName;
		FName Identity;
		FString HiddenName;
		double Marker;
	};

	struct FAuthorRecord
	{
		FString Name;
		FAuthorPayload Quartz;
		FAuthorPayload Violet;
	};

	const TArray<FAuthorRecord>& AuthorRecords()
	{
		static const TArray<FAuthorRecord> Values = {
			{ TEXT("DA_BundleRecord_Quartz"),
				{ TEXT("Quartz"), TEXT("DA_Quartz_Quartz_Payload"), TEXT("Quartz.Q"), TEXT("DA_Quartz_Quartz_Hidden"), 137.125 },
				{ TEXT("Violet"), TEXT("DA_Quartz_Violet_Payload"), TEXT("Quartz.V"), TEXT("DA_Quartz_Violet_Hidden"), -42.375 } },
			{ TEXT("DA_BundleRecord_Violet"),
				{ TEXT("Quartz"), TEXT("DA_Violet_Quartz_Payload"), TEXT("Violet.Q"), TEXT("DA_Violet_Quartz_Hidden"), 803.625 },
				{ TEXT("Violet"), TEXT("DA_Violet_Violet_Payload"), TEXT("Violet.V"), TEXT("DA_Violet_Violet_Hidden"), 19.875 } },
			{ TEXT("DA_BundleRecord_Amber"),
				{ TEXT("Quartz"), TEXT("DA_Amber_Quartz_Payload"), TEXT("Amber.Q"), TEXT("DA_Amber_Quartz_Hidden"), -611.25 },
				{ TEXT("Violet"), TEXT("DA_Amber_Violet_Payload"), TEXT("Amber.V"), TEXT("DA_Amber_Violet_Hidden"), 271.75 } }
		};
		return Values;
	}

	FString ObjectPath(const FString& Name)
	{
		return FString::Printf(
			TEXT("/Game/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/Records/%s.%s"),
			*Name,
			*Name);
	}

	template <typename TObjectType>
	TObjectType* LoadExact(const FString& Name, FString& OutMessage)
	{
		const FString Path = ObjectPath(Name);
		TObjectType* Object = LoadObject<TObjectType>(nullptr, *Path);
		if (!Object || Object->GetPathName() != Path)
		{
			OutMessage = FString::Printf(TEXT("exact asset failed to load with expected class/path: %s"), *Path);
			return nullptr;
		}
		return Object;
	}

	int32 CountTag(UWorld* World, FName Tag, UClass* RequiredClass, AActor*& OutActor)
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, Tag, Found);
		OutActor = Found.Num() == 1 ? Found[0] : nullptr;
		return OutActor && OutActor->IsA(RequiredClass) ? Found.Num() : -Found.Num();
	}
}

bool UBundleLeaseAssetAuthoring::ValidateAuthoredAssets(FString& OutMessage)
{
	UAssetManager* Manager = UAssetManager::GetIfInitialized();
	if (!Manager)
	{
		OutMessage = TEXT("Asset Manager is not initialized");
		return false;
	}
	// Authoring/readback may create these packages after this editor process's
	// initial config scan. Refresh only the exact protected type/path; production
	// fixture preflight separately proves the task overlay worked before boot.
	Manager->ScanPathForPrimaryAssets(
		FPrimaryAssetType(TEXT("BundleLeaseRecord")),
		TEXT("/Game/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/Records"),
		UBundleLeaseRecord::StaticClass(),
		false,
		false,
		true);
	int32 Inventory = 0;
	for (const FAuthorRecord& RecordSpec : AuthorRecords())
	{
		UBundleLeaseRecord* Record = LoadExact<UBundleLeaseRecord>(RecordSpec.Name, OutMessage);
		if (!Record)
		{
			return false;
		}
		++Inventory;
		const FPrimaryAssetId ExpectedId(
			FPrimaryAssetType(TEXT("BundleLeaseRecord")),
			FName(*RecordSpec.Name));
		if (Record->GetPrimaryAssetId() != ExpectedId
			|| Manager->GetPrimaryAssetPath(ExpectedId).ToString() != ObjectPath(RecordSpec.Name))
		{
			OutMessage = FString::Printf(TEXT("primary identity/registration mismatch: %s"), *RecordSpec.Name);
			return false;
		}

		for (const FAuthorPayload* PayloadSpec : { &RecordSpec.Quartz, &RecordSpec.Violet })
		{
			UBundleLeasePayload* Payload = LoadExact<UBundleLeasePayload>(PayloadSpec->PayloadName, OutMessage);
			UBundleLeaseHiddenDependency* Hidden =
				LoadExact<UBundleLeaseHiddenDependency>(PayloadSpec->HiddenName, OutMessage);
			if (!Payload || !Hidden)
			{
				return false;
			}
			Inventory += 2;
			const TSoftObjectPtr<UBundleLeasePayload>& RecordSoft =
				PayloadSpec->Bundle == TEXT("Quartz") ? Record->QuartzPayload : Record->VioletPayload;
			if (RecordSoft.ToSoftObjectPath().ToString() != ObjectPath(PayloadSpec->PayloadName)
				|| Payload->PayloadIdentity != PayloadSpec->Identity
				|| Payload->HiddenDependency != Hidden
				|| !FMath::IsNearlyEqual(Hidden->AuthoredMarker, PayloadSpec->Marker, 0.0001))
			{
				OutMessage = FString::Printf(TEXT("payload/hidden authored facts mismatch: %s"), *PayloadSpec->PayloadName);
				return false;
			}
			TSet<FSoftObjectPath> LoadSet;
			if (!Manager->GetPrimaryAssetLoadSet(LoadSet, ExpectedId, { PayloadSpec->Bundle }, false)
				|| LoadSet.Num() != 2
				|| !LoadSet.Contains(FSoftObjectPath(ObjectPath(RecordSpec.Name)))
				|| !LoadSet.Contains(FSoftObjectPath(ObjectPath(PayloadSpec->PayloadName))))
			{
				OutMessage = FString::Printf(TEXT("bundle load set mismatch: %s/%s"), *RecordSpec.Name, *PayloadSpec->Bundle.ToString());
				return false;
			}
		}
	}
	if (Inventory != 15)
	{
		OutMessage = FString::Printf(TEXT("inventory=%d expected=15"), Inventory);
		return false;
	}
	OutMessage = TEXT("assets=15 primary=3 payload=6 hidden=6 bundles=6 exact_load_sets=6");
	return true;
}

bool UBundleLeaseAssetAuthoring::ValidateCurrentMap(bool bAdmission, FString& OutMessage)
{
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		OutMessage = TEXT("editor world is unavailable");
		return false;
	}
	const FString ExpectedMap = bAdmission
		? TEXT("/Game/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/L_BundleLeaseAdmission")
		: TEXT("/Game/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/L_BundleLeases");
	if (World->GetOutermost()->GetName() != ExpectedMap)
	{
		OutMessage = FString::Printf(TEXT("current map=%s expected=%s"), *World->GetOutermost()->GetName(), *ExpectedMap);
		return false;
	}

	AActor* ScenarioActor = nullptr;
	if (CountTag(World, TEXT("BundleLease.Scenario"), ABundleLeaseScenario::StaticClass(), ScenarioActor) != 1)
	{
		OutMessage = TEXT("scenario tag/class cardinality mismatch");
		return false;
	}
	ABundleLeaseScenario* Scenario = CastChecked<ABundleLeaseScenario>(ScenarioActor);
	const bool bKnownId = AuthorRecords().ContainsByPredicate(
		[Scenario](const FAuthorRecord& Spec)
		{
			return Scenario->SelectedPrimaryAssetId == FPrimaryAssetId(
				FPrimaryAssetType(TEXT("BundleLeaseRecord")),
				FName(*Spec.Name));
		});
	if (!bKnownId || (Scenario->SelectedBundleName != TEXT("Quartz") && Scenario->SelectedBundleName != TEXT("Violet")))
	{
		OutMessage = TEXT("scenario world facts do not select protected id/bundle");
		return false;
	}

	TArray<AActor*> FinalFixtures;
	TArray<AActor*> AdmissionFixtures;
	UGameplayStatics::GetAllActorsOfClass(World, ABundleLeaseFunctionalTest::StaticClass(), FinalFixtures);
	UGameplayStatics::GetAllActorsOfClass(World, ABundleLeaseAdmissionFunctionalTest::StaticClass(), AdmissionFixtures);
	if (bAdmission)
	{
		TArray<AActor*> RuntimeHosts;
		TArray<AActor*> RuntimeConsumers;
		UGameplayStatics::GetAllActorsOfClass(World, ABundleLeaseHost::StaticClass(), RuntimeHosts);
		UGameplayStatics::GetAllActorsOfClass(World, ABundleLeaseConsumer::StaticClass(), RuntimeConsumers);
		if (AdmissionFixtures.Num() != 1 || FinalFixtures.Num() != 0
			|| RuntimeHosts.Num() != 0 || RuntimeConsumers.Num() != 0)
		{
			OutMessage = TEXT("admission/final fixture isolation mismatch");
			return false;
		}
		OutMessage = TEXT("map=admission scenario=1 admission_fixture=1 final_fixture=0 runtime_hosts=0 runtime_consumers=0");
		return true;
	}

	AActor* HostActor = nullptr;
	AActor* ConsumerAActor = nullptr;
	AActor* ConsumerBActor = nullptr;
	if (FinalFixtures.Num() != 1 || AdmissionFixtures.Num() != 0
		|| CountTag(World, TEXT("BundleLease.Host"), ABundleLeaseHost::StaticClass(), HostActor) != 1
		|| CountTag(World, TEXT("BundleLease.ConsumerA"), ABundleLeaseConsumer::StaticClass(), ConsumerAActor) != 1
		|| CountTag(World, TEXT("BundleLease.ConsumerB"), ABundleLeaseConsumer::StaticClass(), ConsumerBActor) != 1)
	{
		OutMessage = TEXT("final fixture/host/consumer cardinality mismatch");
		return false;
	}
	ABundleLeaseHost* Host = CastChecked<ABundleLeaseHost>(HostActor);
	ABundleLeaseConsumer* ConsumerA = CastChecked<ABundleLeaseConsumer>(ConsumerAActor);
	ABundleLeaseConsumer* ConsumerB = CastChecked<ABundleLeaseConsumer>(ConsumerBActor);
	if (!Host->LeaseManager || ConsumerA == ConsumerB || ConsumerA->LeaseHost != Host || ConsumerB->LeaseHost != Host
		|| ConsumerA->bBundleReady || ConsumerB->bBundleReady)
	{
		OutMessage = TEXT("final initial public host/consumer contract mismatch");
		return false;
	}
	OutMessage = TEXT("map=final scenario=1 final_fixture=1 admission_fixture=0 runtime_hosts=1 runtime_consumers=2 initial_ready=0");
	return true;
}
