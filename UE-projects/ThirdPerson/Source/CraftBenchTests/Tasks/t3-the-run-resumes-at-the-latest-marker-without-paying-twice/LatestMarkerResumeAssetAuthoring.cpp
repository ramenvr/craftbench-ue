// Copyright CraftBench. All Rights Reserved.

#include "LatestMarkerResumeAssetAuthoring.h"

#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "LatestMarkerResumeFunctionalTest.h"
#include "Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumePersistenceComponent.h"
#include "Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumeProtectedTypes.h"

FString ULatestMarkerResumeAssetAuthoring::InspectMap(
	UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return TEXT("FAIL MAP_WORLD world=null");
	}
	const FString ExpectedPackage = TEXT(
		"/Game/Maps/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/"
		"L_LatestMarkerResume");
	if (World->GetPackage()->GetName() != ExpectedPackage)
	{
		return FString::Printf(TEXT("FAIL MAP_PACKAGE expected=%s actual=%s"),
			*ExpectedPackage, *World->GetPackage()->GetName());
	}
	int32 SubjectCount = 0;
	int32 CheckpointCount = 0;
	int32 RewardCount = 0;
	int32 WriteFixtureCount = 0;
	int32 ResumeFixtureCount = 0;
	int32 PlayerStartCount = 0;
	ARunResumeSubject* Subject = nullptr;
	TSet<FName> CheckpointIds;
	TSet<FName> RewardIds;
	int32 RewardTotal = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor->GetClass() == ARunResumeSubject::StaticClass())
		{
			++SubjectCount;
			Subject = CastChecked<ARunResumeSubject>(Actor);
		}
		else if (Actor->GetClass() == ARunResumeCheckpoint::StaticClass())
		{
			++CheckpointCount;
			CheckpointIds.Add(CastChecked<ARunResumeCheckpoint>(Actor)->CheckpointId);
		}
		else if (Actor->GetClass() == ARunResumeReward::StaticClass())
		{
			++RewardCount;
			ARunResumeReward* Reward = CastChecked<ARunResumeReward>(Actor);
			RewardIds.Add(Reward->RewardId);
			RewardTotal += Reward->RewardValue;
		}
		else if (Actor->GetClass()
			== ALatestMarkerWriteFunctionalTest::StaticClass())
		{
			++WriteFixtureCount;
		}
		else if (Actor->GetClass()
			== ALatestMarkerResumeFunctionalTest::StaticClass())
		{
			++ResumeFixtureCount;
		}
		else if (Actor->GetClass() == APlayerStart::StaticClass())
		{
			++PlayerStartCount;
		}
	}
	UClass* GameMode = World->GetWorldSettings()
		? World->GetWorldSettings()->DefaultGameMode : nullptr;
	const bool bFactsExact = CheckpointIds.Num() == 2
		&& CheckpointIds.Contains(TEXT("HarborOld"))
		&& CheckpointIds.Contains(TEXT("CedarLatest"))
		&& RewardIds.Num() == 3 && RewardIds.Contains(TEXT("RewardQuartz"))
		&& RewardIds.Contains(TEXT("RewardViolet"))
		&& RewardIds.Contains(TEXT("RewardAmberControl"))
		&& RewardTotal == 87;
	const bool bSubjectExact = Subject != nullptr
		&& Subject->ActorHasTag(TEXT("RunResumeSubject"))
		&& Subject->Persistence != nullptr;
	const bool bGameModeExact = GetPathNameSafe(GameMode)
		== TEXT("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
			"BP_ThirdPersonGameMode_C");
	if (SubjectCount != 1 || CheckpointCount != 2 || RewardCount != 3
		|| WriteFixtureCount != 1 || ResumeFixtureCount != 1
		|| PlayerStartCount != 1 || !bFactsExact || !bSubjectExact
		|| !bGameModeExact)
	{
		return FString::Printf(TEXT(
			"FAIL MAP_CONTRACT subject=%d checkpoints=%d rewards=%d write=%d "
			"resume=%d start=%d facts=%d subject_exact=%d game_mode=%d"),
			SubjectCount, CheckpointCount, RewardCount, WriteFixtureCount,
			ResumeFixtureCount, PlayerStartCount, bFactsExact ? 1 : 0,
			bSubjectExact ? 1 : 0, bGameModeExact ? 1 : 0);
	}
	return TEXT("PASS map_exact=1 subject=1 checkpoints=2 rewards=3 "
		"write_fixture=1 resume_fixture=1 player_start=1 facts_exact=1 "
		"persistence_component=1 game_mode_exact=1 playable=1 "
		"runtime_observed=0");
}
