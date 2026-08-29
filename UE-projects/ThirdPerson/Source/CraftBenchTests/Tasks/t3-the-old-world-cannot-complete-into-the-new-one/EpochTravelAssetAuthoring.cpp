// Copyright CraftBench. All Rights Reserved.

#include "EpochTravelAssetAuthoring.h"

#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "Tasks/t3-the-old-world-cannot-complete-into-the-new-one/EpochTravelProtectedTypes.h"

namespace
{
	constexpr TCHAR TaskRoot[] = TEXT(
		"/Game/Maps/t3-the-old-world-cannot-complete-into-the-new-one");
	constexpr TCHAR OldRecordPath[] = TEXT(
		"/Game/Maps/t3-the-old-world-cannot-complete-into-the-new-one/Support/"
		"DA_EpochRecord_Old.DA_EpochRecord_Old");
	constexpr TCHAR NewRecordPath[] = TEXT(
		"/Game/Maps/t3-the-old-world-cannot-complete-into-the-new-one/Support/"
		"DA_EpochRecord_New.DA_EpochRecord_New");

	bool IsExactRecord(const TCHAR* Path, const TCHAR* Id, int32 Value)
	{
		UEpochAssetRecord* Record = LoadObject<UEpochAssetRecord>(nullptr, Path);
		return Record != nullptr && Record->GetClass() == UEpochAssetRecord::StaticClass()
			&& Record->RecordId == FName(Id) && Record->RecordValue == Value
			&& Record->GetPathName() == Path;
	}
}

FString UEpochTravelAssetAuthoring::InspectRecords()
{
	const bool bOld = IsExactRecord(OldRecordPath, TEXT("OldQuartz"), 31);
	const bool bNew = IsExactRecord(NewRecordPath, TEXT("NewViolet"), 74);
	if (!bOld || !bNew)
	{
		return FString::Printf(TEXT("FAIL RECORDS old=%d new=%d"),
			bOld ? 1 : 0, bNew ? 1 : 0);
	}
	return TEXT("PASS records=2 old=OldQuartz:31 new=NewViolet:74 exact=1");
}

FString UEpochTravelAssetAuthoring::InspectMap(
	UObject* WorldContextObject, bool bStartMap)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL MAP_WORLD world=null");
	}
	const FString ExpectedPackage = FString::Printf(TEXT("%s/%s"), TaskRoot,
		bStartMap ? TEXT("L_OldEpochStart") : TEXT("L_NewEpochDestination"));
	if (World->GetPackage()->GetName() != ExpectedPackage)
	{
		return FString::Printf(TEXT("FAIL MAP_PACKAGE expected=%s actual=%s"),
			*ExpectedPackage, *World->GetPackage()->GetName());
	}
	int32 DisplayCount = 0;
	int32 StartFixtureCount = 0;
	int32 DestinationFixtureCount = 0;
	int32 PlayerStartCount = 0;
	AEpochAssetDisplay* Display = nullptr;
	AOldEpochStartFunctionalTest* StartFixture = nullptr;
	ANewEpochDestinationFunctionalTest* DestinationFixture = nullptr;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->GetClass() == AEpochAssetDisplay::StaticClass())
		{
			++DisplayCount;
			Display = CastChecked<AEpochAssetDisplay>(Actor);
		}
		else if (Actor->GetClass() == AOldEpochStartFunctionalTest::StaticClass())
		{
			++StartFixtureCount;
			StartFixture = CastChecked<AOldEpochStartFunctionalTest>(Actor);
		}
		else if (Actor->GetClass()
			== ANewEpochDestinationFunctionalTest::StaticClass())
		{
			++DestinationFixtureCount;
			DestinationFixture = CastChecked<ANewEpochDestinationFunctionalTest>(Actor);
		}
		else if (Actor->GetClass() == APlayerStart::StaticClass())
		{
			++PlayerStartCount;
		}
	}
	const AFunctionalTest* Fixture = bStartMap
		? static_cast<AFunctionalTest*>(StartFixture)
		: static_cast<AFunctionalTest*>(DestinationFixture);
	const bool bClassCounts = DisplayCount == 1 && PlayerStartCount == 1
		&& StartFixtureCount == (bStartMap ? 1 : 0)
		&& DestinationFixtureCount == (bStartMap ? 0 : 1);
	bool bFacts = false;
	if (bStartMap && StartFixture != nullptr)
	{
		bFacts = StartFixture->Display == Display
			&& StartFixture->AssignedRecord.ToSoftObjectPath().ToString()
				== FString(OldRecordPath)
			&& StartFixture->ExpectedRecordId == TEXT("OldQuartz")
			&& StartFixture->ExpectedRecordValue == 31
			&& StartFixture->DestinationMap == TEXT(
				"/Game/Maps/t3-the-old-world-cannot-complete-into-the-new-one/"
				"L_NewEpochDestination");
	}
	else if (!bStartMap && DestinationFixture != nullptr)
	{
		bFacts = DestinationFixture->Display == Display
			&& DestinationFixture->AssignedRecord.ToSoftObjectPath().ToString()
				== FString(NewRecordPath)
			&& DestinationFixture->ExpectedRecordId == TEXT("NewViolet")
			&& DestinationFixture->ExpectedRecordValue == 74;
	}
	UClass* GameMode = World->GetWorldSettings()
		? World->GetWorldSettings()->DefaultGameMode : nullptr;
	const bool bGameMode = GetPathNameSafe(GameMode) == TEXT(
		"/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
		"BP_ThirdPersonGameMode_C");
	const bool bFixtureEnabled = Fixture != nullptr && Fixture->IsEnabled();
	if (!bClassCounts || !bFacts || !bGameMode || !bFixtureEnabled)
	{
		return FString::Printf(TEXT(
			"FAIL MAP_CONTRACT start_mode=%d display=%d start_fixture=%d "
			"destination_fixture=%d player_start=%d facts=%d game_mode=%d "
			"fixture_enabled=%d"), bStartMap ? 1 : 0, DisplayCount,
			StartFixtureCount, DestinationFixtureCount, PlayerStartCount,
			bFacts ? 1 : 0, bGameMode ? 1 : 0,
			bFixtureEnabled ? 1 : 0);
	}
	return FString::Printf(TEXT(
		"PASS map_exact=1 stage=%s display=1 fixture=1 player_start=1 "
		"record_soft=1 facts_exact=1 game_mode_exact=1 playable=1 "
		"runtime_observed=0"), bStartMap ? TEXT("old") : TEXT("new"));
}
