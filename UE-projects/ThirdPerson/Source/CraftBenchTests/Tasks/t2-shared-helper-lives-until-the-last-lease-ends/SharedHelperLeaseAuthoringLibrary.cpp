// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY readback/authoring helper.

#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseAuthoringLibrary.h"

#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseFunctionalTest.h"
#include "Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.h"
#include "UObject/UnrealType.h"

FString USharedHelperLeaseAuthoringLibrary::InspectRuntimeContract()
{
	UClass* const SubsystemClass = USharedHelperLeaseSubsystem::StaticClass();
	UClass* const LeaseClass = USharedHelperLease::StaticClass();
	const bool bSubsystem = SubsystemClass->IsChildOf(UGameInstanceSubsystem::StaticClass());
	const bool bAcquire = SubsystemClass->FindFunctionByName(TEXT("AcquireLease")) != nullptr;
	const bool bRelease = SubsystemClass->FindFunctionByName(TEXT("ReleaseLease")) != nullptr;

	const FObjectPropertyBase* const LeaseHelper =
		CastField<FObjectPropertyBase>(LeaseClass->FindPropertyByName(TEXT("Helper")));
	const FWeakObjectProperty* const LeaseOwner =
		CastField<FWeakObjectProperty>(LeaseClass->FindPropertyByName(TEXT("Owner")));
	const bool bLeaseStrong = LeaseHelper != nullptr
		&& LeaseHelper->PropertyClass == USharedLeaseHelper::StaticClass();
	const bool bOwnerWeak = LeaseOwner != nullptr
		&& LeaseOwner->PropertyClass == UObject::StaticClass();

	const FArrayProperty* const CacheArray = CastField<FArrayProperty>(
		SubsystemClass->FindPropertyByName(TEXT("CacheEntries")));
	const FStructProperty* const CacheInner = CacheArray != nullptr
		? CastField<FStructProperty>(CacheArray->Inner) : nullptr;
	const bool bCacheArray = CacheInner != nullptr
		&& CacheInner->Struct == FSharedHelperCacheEntry::StaticStruct();
	const FObjectPropertyBase* const CacheHelper = CastField<FObjectPropertyBase>(
		FSharedHelperCacheEntry::StaticStruct()->FindPropertyByName(TEXT("Helper")));
	const FArrayProperty* const CacheLeases = CastField<FArrayProperty>(
		FSharedHelperCacheEntry::StaticStruct()->FindPropertyByName(TEXT("Leases")));
	const FObjectPropertyBase* const CacheLeaseInner = CacheLeases != nullptr
		? CastField<FObjectPropertyBase>(CacheLeases->Inner) : nullptr;
	const bool bCacheHelperStrong = CacheHelper != nullptr
		&& CacheHelper->PropertyClass == USharedLeaseHelper::StaticClass();
	const bool bCacheLeasesStrong = CacheLeaseInner != nullptr
		&& CacheLeaseInner->PropertyClass == USharedHelperLease::StaticClass();

	const FArrayProperty* const ActiveArray = CastField<FArrayProperty>(
		SubsystemClass->FindPropertyByName(TEXT("ActiveLeases")));
	const FObjectPropertyBase* const ActiveInner = ActiveArray != nullptr
		? CastField<FObjectPropertyBase>(ActiveArray->Inner) : nullptr;
	const bool bActiveLeases = ActiveInner != nullptr
		&& ActiveInner->PropertyClass == USharedHelperLease::StaticClass();

	const bool bPass = bSubsystem && bAcquire && bRelease && bLeaseStrong
		&& bOwnerWeak && bCacheArray && bCacheHelperStrong
		&& bCacheLeasesStrong && bActiveLeases;
	return FString::Printf(
		TEXT("%s subsystem=%d acquire=%d release=%d lease_strong=%d owner_weak=%d cache_array=%d cache_helper_strong=%d cache_leases_strong=%d active_leases_strong=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"),
		bSubsystem, bAcquire, bRelease, bLeaseStrong, bOwnerWeak,
		bCacheArray, bCacheHelperStrong, bCacheLeasesStrong, bActiveLeases);
}

FString USharedHelperLeaseAuthoringLibrary::InspectWorld(UObject* WorldContextObject)
{
	UWorld* const World = GEngine != nullptr
		? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull)
		: nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL world=0 fixtures=0 tag=0 serialized_owners=0");
	}

	int32 FixtureCount = 0;
	int32 TaggedFixtureCount = 0;
	int32 SerializedOwners = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* const Actor = *It;
		if (Actor->GetClass() == ASharedHelperLeaseFunctionalTest::StaticClass())
		{
			++FixtureCount;
			if (Actor->ActorHasTag(FName(TEXT("CraftBench.SharedHelperLeaseFixture"))))
			{
				++TaggedFixtureCount;
			}
		}
		if (Actor->IsA<ASharedHelperLeaseOwner>())
		{
			++SerializedOwners;
		}
	}

	const bool bPass = FixtureCount == 1 && TaggedFixtureCount == 1
		&& SerializedOwners == 0;
	return FString::Printf(
		TEXT("%s world=1 fixtures=%d tag=%d serialized_owners=%d"),
		bPass ? TEXT("PASS") : TEXT("FAIL"),
		FixtureCount, TaggedFixtureCount, SerializedOwners);
}
