// Copyright CraftBench. All Rights Reserved.

#include "LatestMarkerResumeFunctionalTest.h"

#include "EngineUtils.h"
#include "Engine/World.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumePersistenceComponent.h"
#include "Tasks/t3-the-run-resumes-at-the-latest-marker-without-paying-twice/RunResumeProtectedTypes.h"

namespace RunResumeFixture
{
	const FName SubjectTag(TEXT("RunResumeSubject"));
	const FName OldCheckpoint(TEXT("HarborOld"));
	const FName LatestCheckpoint(TEXT("CedarLatest"));
	const FName RewardQuartz(TEXT("RewardQuartz"));
	const FName RewardViolet(TEXT("RewardViolet"));
	const FName RewardAmber(TEXT("RewardAmberControl"));
	constexpr int32 QuartzValue = 17;
	constexpr int32 VioletValue = 29;
	constexpr int32 AmberValue = 41;

	bool TransformNear(const FTransform& A, const FTransform& B)
	{
		return FVector::Dist(A.GetLocation(), B.GetLocation()) <= 1.0
			&& FMath::RadiansToDegrees(A.GetRotation().AngularDistance(
				B.GetRotation())) <= 0.25;
	}
}

ALatestMarkerResumeFunctionalTestBase::ALatestMarkerResumeFunctionalTestBase(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.AddUnique(TEXT("LatestMarkerResumeFixture"));
}

void ALatestMarkerResumeFunctionalTestBase::FailHarness(const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Error,
		TEXT("HARNESS-PRECONDITION: ") + Detail);
}

void ALatestMarkerResumeFunctionalTestBase::PassGate(
	const TCHAR* Gate, const FString& Detail)
{
	++PassedGates;
	UE_LOG(LogTemp, Display, TEXT("GATE[%s]=PASS %s"), Gate, *Detail);
}

void ALatestMarkerResumeFunctionalTestBase::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	FinishTest(EFunctionalTestResult::Failed,
		FString::Printf(TEXT("GATE[%s]=FAIL %s"), Gate, *Detail));
}

bool ALatestMarkerResumeFunctionalTestBase::ResolveHarness()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FailHarness(TEXT("PIE world missing"));
		return false;
	}
	TArray<ARunResumeSubject*> Subjects;
	for (TActorIterator<ARunResumeSubject> It(World); It; ++It)
	{
		if (It->ActorHasTag(RunResumeFixture::SubjectTag))
		{
			Subjects.Add(*It);
		}
	}
	for (TActorIterator<ARunResumeCheckpoint> It(World); It; ++It)
	{
		Checkpoints.Add(*It);
	}
	for (TActorIterator<ARunResumeReward> It(World); It; ++It)
	{
		Rewards.Add(*It);
	}
	if (Subjects.Num() != 1 || Checkpoints.Num() != 2 || Rewards.Num() != 3)
	{
		FailHarness(FString::Printf(TEXT(
			"cardinality subject=%d checkpoints=%d rewards=%d"),
			Subjects.Num(), Checkpoints.Num(), Rewards.Num()));
		return false;
	}
	Subject = Subjects[0];
	Persistence = Subjects[0]->Persistence;
	if (!Persistence.IsValid())
	{
		FailHarness(TEXT("subject persistence component missing"));
		return false;
	}
	Checkpoints.Sort([](const TWeakObjectPtr<ARunResumeCheckpoint>& Left,
		const TWeakObjectPtr<ARunResumeCheckpoint>& Right)
		{
			return Left->CheckpointId.LexicalLess(Right->CheckpointId);
		});
	Rewards.Sort([](const TWeakObjectPtr<ARunResumeReward>& Left,
		const TWeakObjectPtr<ARunResumeReward>& Right)
		{
			return Left->RewardId.LexicalLess(Right->RewardId);
		});
	const bool bCheckpointFacts = Checkpoints[0]->CheckpointId
			== RunResumeFixture::LatestCheckpoint
		&& Checkpoints[1]->CheckpointId == RunResumeFixture::OldCheckpoint;
	const bool bRewardFacts = Rewards[0]->RewardId
			== RunResumeFixture::RewardAmber
		&& Rewards[0]->RewardValue == RunResumeFixture::AmberValue
		&& Rewards[1]->RewardId == RunResumeFixture::RewardQuartz
		&& Rewards[1]->RewardValue == RunResumeFixture::QuartzValue
		&& Rewards[2]->RewardId == RunResumeFixture::RewardViolet
		&& Rewards[2]->RewardValue == RunResumeFixture::VioletValue;
	if (!bCheckpointFacts || !bRewardFacts)
	{
		FailHarness(TEXT("protected checkpoint/reward facts mismatch"));
		return false;
	}
	return true;
}

void ALatestMarkerResumeFunctionalTestBase::PrepareTest()
{
	Super::PrepareTest();
	SlotName = FPlatformMisc::GetEnvironmentVariable(
		TEXT("CRAFTBENCH_RUN_RESUME_SLOT"));
	RunNonce = FPlatformMisc::GetEnvironmentVariable(
		TEXT("CRAFTBENCH_RUN_RESUME_NONCE"));
	if (SlotName.IsEmpty() || RunNonce.Len() < 16 || !ResolveHarness())
	{
		if (IsRunning())
		{
			FailHarness(TEXT("nonce-scoped slot environment missing"));
		}
		return;
	}
	Persistence->ConfigurePersistence(SlotName, 0, RunNonce);
	Epoch = GetWorld()->GetTimeSeconds();
	if (IsResumeLeg())
	{
		SetCheckpointSchedule({Epoch + 0.30, Epoch + 0.60});
	}
	else
	{
		SetCheckpointSchedule({Epoch + 0.20, Epoch + 0.40, Epoch + 0.60,
			Epoch + 0.80, Epoch + 1.00, Epoch + 1.20});
	}
}

void ALatestMarkerResumeFunctionalTestBase::OnCheckpoint(
	int32 CheckpointIndex, double TimeSeconds)
{
	if (IsResumeLeg())
	{
		RunResumeCheckpoint(CheckpointIndex);
	}
	else
	{
		RunWriteCheckpoint(CheckpointIndex);
	}
}

void ALatestMarkerResumeFunctionalTestBase::RunWriteCheckpoint(
	int32 CheckpointIndex)
{
	ARunResumeCheckpoint* Latest = Checkpoints[0].Get();
	ARunResumeCheckpoint* Old = Checkpoints[1].Get();
	ARunResumeReward* Quartz = Rewards[1].Get();
	ARunResumeReward* Violet = Rewards[2].Get();
	if (CheckpointIndex == 0)
	{
		if (UGameplayStatics::DoesSaveGameExist(SlotName, 0))
		{
			FailHarness(TEXT("nonce-scoped slot was not fresh"));
			return;
		}
		PassGate(TEXT("FreshNonceScopedSlotBeginsEmpty"),
			TEXT("slot_absent=1 user=0"));
	}
	else if (CheckpointIndex == 1)
	{
		if (!Persistence->RecordCheckpoint(Old->CheckpointId,
			Old->GetActorTransform()))
		{
			FailGate(TEXT("NewestCheckpointRecordIsSerialized"),
				TEXT("first checkpoint save rejected"));
		}
	}
	else if (CheckpointIndex == 2)
	{
		if (!Persistence->CollectReward(Quartz))
		{
			FailGate(TEXT("CollectedRewardIdentitySetIsSerialized"),
				TEXT("first reward save rejected"));
		}
	}
	else if (CheckpointIndex == 3)
	{
		if (!Persistence->RecordCheckpoint(Latest->CheckpointId,
			Latest->GetActorTransform()))
		{
			FailGate(TEXT("NewestCheckpointRecordIsSerialized"),
				TEXT("latest checkpoint save rejected"));
		}
	}
	else if (CheckpointIndex == 4)
	{
		if (!Persistence->CollectReward(Violet))
		{
			FailGate(TEXT("CollectedRewardIdentitySetIsSerialized"),
				TEXT("second reward save rejected"));
		}
	}
	else if (CheckpointIndex == 5)
	{
		URunResumeSaveGame* Record = Cast<URunResumeSaveGame>(
			UGameplayStatics::LoadGameFromSlot(SlotName, 0));
		if (Record == nullptr || Record->SchemaVersion != 1
			|| Record->RunNonce != RunNonce
			|| Record->LatestCheckpointId != Latest->CheckpointId
			|| !RunResumeFixture::TransformNear(
				Record->LatestCheckpointTransform, Latest->GetActorTransform()))
		{
			FailGate(TEXT("NewestCheckpointRecordIsSerialized"),
				TEXT("saved latest checkpoint identity/transform mismatch"));
			return;
		}
		PassGate(TEXT("NewestCheckpointRecordIsSerialized"),
			FString::Printf(TEXT("id=%s transform_exact=1 nonce_exact=1"),
				*Record->LatestCheckpointId.ToString()));
		TSet<FName> Ids;
		for (FName RewardId : Record->CollectedRewardIds)
		{
			Ids.Add(RewardId);
		}
		if (Ids.Num() != 2 || !Ids.Contains(Quartz->RewardId)
			|| !Ids.Contains(Violet->RewardId)
			|| Record->RewardTotal != RunResumeFixture::QuartzValue
				+ RunResumeFixture::VioletValue)
		{
			FailGate(TEXT("CollectedRewardIdentitySetIsSerialized"),
				TEXT("saved identity set/total mismatch"));
			return;
		}
		PassGate(TEXT("CollectedRewardIdentitySetIsSerialized"),
			TEXT("ids=2 total=46 control_absent=1"));
		FinishTest(EFunctionalTestResult::Succeeded,
			FString::Printf(TEXT(
				"RUN-RESUME-WRITE-SUCCEEDED gates=%d/3 slot=%s nonce=%s"),
				PassedGates, *SlotName, *RunNonce));
	}
}

void ALatestMarkerResumeFunctionalTestBase::RunResumeCheckpoint(
	int32 CheckpointIndex)
{
	ARunResumeCheckpoint* Latest = Checkpoints[0].Get();
	ARunResumeReward* Control = Rewards[0].Get();
	ARunResumeReward* Quartz = Rewards[1].Get();
	ARunResumeReward* Violet = Rewards[2].Get();
	TArray<ARunResumeReward*> RewardActors{Control, Quartz, Violet};
	if (CheckpointIndex == 0)
	{
		if (!Persistence->RestoreFromSlot(Subject.Get(), RewardActors))
		{
			FailGate(TEXT("ResumeUsesLatestMarkerTransform"),
				TEXT("RestoreFromSlot returned false"));
			return;
		}
		if (!RunResumeFixture::TransformNear(
			Subject->GetActorTransform(), Latest->GetActorTransform())
			|| Persistence->GetLatestCheckpointId() != Latest->CheckpointId)
		{
			FailGate(TEXT("ResumeUsesLatestMarkerTransform"),
				TEXT("subject did not restore to latest marker"));
			return;
		}
		PassGate(TEXT("ResumeUsesLatestMarkerTransform"),
			TEXT("latest_id=1 transform_exact=1 fresh_subject=1"));
		if (Persistence->GetRewardTotal() != 46)
		{
			FailGate(TEXT("RewardTotalRestoresExactly"),
				FString::Printf(TEXT("expected=46 actual=%d"),
					Persistence->GetRewardTotal()));
			return;
		}
		PassGate(TEXT("RewardTotalRestoresExactly"),
			TEXT("expected=46 actual=46"));
	}
	else if (CheckpointIndex == 1)
	{
		const int32 Before = Persistence->GetRewardTotal();
		const bool bRetiredExact = Quartz->IsRetired() && Violet->IsRetired()
			&& !Control->IsRetired();
		const bool bRejected = !Persistence->CollectReward(Quartz)
			&& !Persistence->CollectReward(Violet)
			&& Persistence->GetRewardTotal() == Before;
		if (!bRetiredExact || !bRejected)
		{
			FailGate(TEXT("AlreadyCollectedRewardsDoNotPayTwice"),
				FString::Printf(TEXT("retired=%d rejected=%d before=%d after=%d"),
					bRetiredExact ? 1 : 0, bRejected ? 1 : 0, Before,
					Persistence->GetRewardTotal()));
			return;
		}
		PassGate(TEXT("AlreadyCollectedRewardsDoNotPayTwice"),
			TEXT("retired=2 duplicate_delta=0"));
		const bool bControlFirst = Persistence->CollectReward(Control);
		const int32 AfterFirst = Persistence->GetRewardTotal();
		const bool bControlSecond = Persistence->CollectReward(Control);
		const bool bControlExact = bControlFirst && !bControlSecond
			&& Control->IsRetired() && AfterFirst == Before + 41
			&& Persistence->GetRewardTotal() == AfterFirst;
		if (!bControlExact)
		{
			FailGate(TEXT("UncollectedControlStillPaysOnce"),
				FString::Printf(TEXT(
					"first=%d second=%d retired=%d before=%d after=%d final=%d"),
					bControlFirst ? 1 : 0, bControlSecond ? 1 : 0,
					Control->IsRetired() ? 1 : 0, Before, AfterFirst,
					Persistence->GetRewardTotal()));
			return;
		}
		PassGate(TEXT("UncollectedControlStillPaysOnce"),
			TEXT("value=41 first_delta=41 second_delta=0"));
		FinishTest(EFunctionalTestResult::Succeeded,
			FString::Printf(TEXT(
				"RUN-RESUME-RESUME-SUCCEEDED gates=%d/4 slot=%s nonce=%s"),
				PassedGates, *SlotName, *RunNonce));
	}
}
