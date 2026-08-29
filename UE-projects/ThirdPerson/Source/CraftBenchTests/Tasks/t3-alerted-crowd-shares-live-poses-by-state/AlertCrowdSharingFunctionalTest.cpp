// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingFunctionalTest.h"

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingActors.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "AnimationSharingManager.h"
#include "AnimationSharingSetup.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	const FName SubjectTag(TEXT("AlertCrowdSharingSubject"));
	const FName HostTag(TEXT("AlertCrowdSharingHost"));
	const FName GroupA(TEXT("GroupA"));
	const FName GroupB(TEXT("GroupB"));
	const TCHAR OrdinaryAnimation[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.MF_Unarmed_Walk_Fwd");
	const TCHAR AlertAnimation[] =
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd.MF_Unarmed_Jog_Fwd");

	bool FiniteTransform(const FTransform& Value)
	{
		return !Value.ContainsNaN() && Value.GetRotation().IsNormalized();
	}
}

AAlertCrowdSharingFunctionalTest::AAlertCrowdSharingFunctionalTest(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
}

void AAlertCrowdSharingFunctionalTest::FailHarness(const FString& Detail)
{
	if (!bLocalFinishIssued)
	{
		bLocalFinishIssued = true;
		FinishTest(EFunctionalTestResult::Error,
			TEXT("HARNESS-PRECONDITION: ") + Detail);
	}
}

void AAlertCrowdSharingFunctionalTest::FailGate(
	const TCHAR* Gate, const FString& Detail)
{
	if (!bLocalFinishIssued)
	{
		bLocalFinishIssued = true;
		FinishTest(EFunctionalTestResult::Failed,
			FString::Printf(TEXT("%s: %s"), Gate, *Detail));
	}
}

void AAlertCrowdSharingFunctionalTest::PrepareTest()
{
	Super::PrepareTest();
	UWorld* World = GetWorld();
	if (World == nullptr || ExpectedSetup == nullptr)
	{
		FailHarness(TEXT("PIE world or exact expected Animation Sharing setup is absent"));
		return;
	}

	TArray<AActor*> FoundSubjects;
	TArray<AActor*> FoundHosts;
	UGameplayStatics::GetAllActorsWithTag(World, SubjectTag, FoundSubjects);
	UGameplayStatics::GetAllActorsWithTag(World, HostTag, FoundHosts);
	for (AActor* Actor : FoundSubjects)
	{
		if (AAlertCrowdSharingSubject* Subject =
			Cast<AAlertCrowdSharingSubject>(Actor))
		{
			Subjects.Add(Subject);
		}
	}
	Subjects.Sort([](const AAlertCrowdSharingSubject& Left,
		const AAlertCrowdSharingSubject& Right)
	{
		return Left.SlotIndex < Right.SlotIndex;
	});
	Host = FoundHosts.Num() == 1
		? Cast<AAlertCrowdSharingHost>(FoundHosts[0]) : nullptr;
	if (Subjects.Num() != 6 || FoundSubjects.Num() != 6 || Host == nullptr
		|| FoundHosts.Num() != 1)
	{
		FailHarness(FString::Printf(
			TEXT("expected exact subjects=6 host=1, got subjects=%d tagged=%d hosts=%d"),
			Subjects.Num(), FoundSubjects.Num(), FoundHosts.Num()));
		return;
	}
	if (Host->SharingSetup.Get() != ExpectedSetup
		&& Host->SharingSetup.ToSoftObjectPath().ToString()
			!= ExpectedSetup->GetPathName())
	{
		FailHarness(TEXT("host soft setup path is not the exact fixture setup"));
		return;
	}

	TSet<int32> Slots;
	for (AAlertCrowdSharingSubject* Subject : Subjects)
	{
		Slots.Add(Subject->SlotIndex);
	}
	if (Slots.Num() != 6 || !Slots.Contains(0) || !Slots.Contains(5))
	{
		FailHarness(TEXT("subject SlotIndex values are not exact unique 0..5"));
		return;
	}

	MembershipSeed = static_cast<int32>(GetTypeHash(FGuid::NewGuid()));
	FRandomStream Stream(MembershipSeed);
	TArray<int32> Assignment = {0, 0, 0, 1, 1, 1};
	for (int32 Index = Assignment.Num() - 1; Index > 0; --Index)
	{
		Assignment.Swap(Index, Stream.RandRange(0, Index));
	}
	FirstAlertGroup = (MembershipSeed & 1) == 0 ? GroupA : GroupB;
	SecondAlertGroup = FirstAlertGroup == GroupA ? GroupB : GroupA;
	bool bMadeIneligible[2] = {false, false};
	for (int32 Index = 0; Index < Subjects.Num(); ++Index)
	{
		AAlertCrowdSharingSubject* Subject = Subjects[Index];
		const int32 GroupIndex = Assignment[Index];
		Subject->SubjectIdentity = FName(*FString::Printf(
			TEXT("Crowd_%08X_%d"), static_cast<uint32>(MembershipSeed), Index));
		ExpectedIdentities.Add(Subject->SubjectIdentity);
		Subject->CrowdGroup = GroupIndex == 0 ? GroupA : GroupB;
		Subject->bSharingEligible = bMadeIneligible[GroupIndex];
		bMadeIneligible[GroupIndex] = true;
		Subject->bAlerted = false;
		Subject->bTravelEnabled = true;
		Subject->TravelSpeed = 125.0f + 7.0f * Index;
		// Keep the six independent movement witnesses on parallel trajectories.
		// Alternating directions in the authored two-row layout creates a
		// head-on capsule collision before the first state transition and tests
		// crowd avoidance, which is outside this task's Animation Sharing scope.
		Subject->TravelDirection = FVector::ForwardVector;
		StartLocations.Add(Subject->GetActorLocation());
		LastLocations.Add(Subject->GetActorLocation());
		MovingFrames.Add(0);
		SampledFrames.Add(0);
		UE_LOG(LogTemp, Display, TEXT(
			"ALERT-CROWD-MEMBER identity=%s slot=%d group=%s eligible=%d speed=%.2f"),
			*Subject->SubjectIdentity.ToString(), Subject->SlotIndex,
			*Subject->CrowdGroup.ToString(), Subject->bSharingEligible ? 1 : 0,
			Subject->TravelSpeed);
	}

	StartWorldSeconds = World->GetTimeSeconds();
	SetCheckpointSchedule({
		StartWorldSeconds + 0.45,
		StartWorldSeconds + 1.10,
		StartWorldSeconds + 1.75,
		StartWorldSeconds + 2.40,
	});
	UE_LOG(LogTemp, Display, TEXT(
		"ALERT-CROWD-WORLD-FACTS seed=%d first=%s second=%s subjects=6 eligible=4"),
		MembershipSeed, *FirstAlertGroup.ToString(), *SecondAlertGroup.ToString());
}

void AAlertCrowdSharingFunctionalTest::Tick(const float DeltaSeconds)
{
	if (!bLocalFinishIssued && Subjects.Num() == 6 && DeltaSeconds > 0.0f)
	{
		for (int32 Index = 0; Index < Subjects.Num(); ++Index)
		{
			AAlertCrowdSharingSubject* Subject = Subjects[Index];
			if (Subject == nullptr)
			{
				FailHarness(TEXT("subject identity was destroyed during the run"));
				break;
			}
			const FVector Now = Subject->GetActorLocation();
			const double Delta = FVector::Dist(Now, LastLocations[Index]);
			const double MaxEngineStep =
				Subject->TravelSpeed * DeltaSeconds * 2.5 + 2.0;
			if (!FMath::IsFinite(Delta) || Delta > MaxEngineStep)
			{
				FailGate(TEXT("CrowdContinuesMovingThroughStateChanges"),
					FString::Printf(TEXT("identity=%s per_frame_delta=%.3f max=%.3f"),
						*Subject->SubjectIdentity.ToString(), Delta, MaxEngineStep));
				break;
			}
			MovingFrames[Index] += Delta > 0.05 ? 1 : 0;
			++SampledFrames[Index];
			LastLocations[Index] = Now;

			USkeletalMeshComponent* Leader = Cast<USkeletalMeshComponent>(
				Subject->GetMesh()->LeaderPoseComponent.Get());
			UAnimSingleNodeInstance* Single = Leader
				? Leader->GetSingleNodeInstance() : nullptr;
			if (Single != nullptr)
			{
				const float Time = Single->GetCurrentTime();
				if (float* Previous = LastLeaderTimes.Find(Leader))
				{
					LeaderTimeAdvances += !FMath::IsNearlyEqual(
						*Previous, Time, 0.0001f) ? 1 : 0;
				}
				LastLeaderTimes.Add(Leader, Time);
			}
		}
	}
	Super::Tick(DeltaSeconds);
}

void AAlertCrowdSharingFunctionalTest::ApplyAlertGroup(const FName Group)
{
	for (AAlertCrowdSharingSubject* Subject : Subjects)
	{
		Subject->bAlerted = !Group.IsNone() && Subject->CrowdGroup == Group;
	}
}

bool AAlertCrowdSharingFunctionalTest::ValidateLeaderPose(
	AAlertCrowdSharingSubject* Subject, USkeletalMeshComponent* Leader,
	FString& OutProblem) const
{
	static const FName Bones[] = {
		FName(TEXT("pelvis")), FName(TEXT("hand_l")), FName(TEXT("hand_r"))};
	USkeletalMeshComponent* Mesh = Subject ? Subject->GetMesh() : nullptr;
	if (Mesh == nullptr || Leader == nullptr)
	{
		OutProblem = TEXT("mesh or leader is null");
		return false;
	}
	for (const FName Bone : Bones)
	{
		const FTransform FollowerPose = Mesh->GetBoneTransform(Bone, RTS_Component);
		const FTransform LeaderPose = Leader->GetBoneTransform(Bone, RTS_Component);
		const double Translation = FVector::Dist(
			FollowerPose.GetTranslation(), LeaderPose.GetTranslation());
		const double Rotation = FMath::RadiansToDegrees(
			FollowerPose.GetRotation().AngularDistance(LeaderPose.GetRotation()));
		if (!FiniteTransform(FollowerPose) || !FiniteTransform(LeaderPose)
			|| Translation > 0.05 || Rotation > 0.20)
		{
			OutProblem = FString::Printf(
				TEXT("identity=%s bone=%s leader/follower residual=%.4fcm/%.4fdeg"),
				*Subject->SubjectIdentity.ToString(), *Bone.ToString(),
				Translation, Rotation);
			return false;
		}
	}
	return true;
}

bool AAlertCrowdSharingFunctionalTest::ValidateSharingState(
	const TCHAR* Phase, const bool bRequireRestore)
{
	UAnimationSharingManager* CurrentManager =
		UAnimationSharingManager::GetManagerForWorld(GetWorld());
	if (CurrentManager == nullptr)
	{
		FailGate(TEXT("CrowdRegistersWithWorldSharingManager"),
			FString::Printf(TEXT("phase=%s manager=null"), Phase));
		return false;
	}
	if (PinnedManager.IsValid() && PinnedManager.Get() != CurrentManager)
	{
		FailGate(TEXT("CrowdRegistersWithWorldSharingManager"),
			FString::Printf(TEXT("phase=%s manager identity changed"), Phase));
		return false;
	}
	PinnedManager = CurrentManager;
	Manager = CurrentManager;

	USkeletalMeshComponent* OrdinaryLeader = nullptr;
	USkeletalMeshComponent* AlertLeader = nullptr;
	int32 AlertedLeaders = 0;
	int32 OrdinaryLeaders = 0;
	for (int32 SubjectIndex = 0; SubjectIndex < Subjects.Num(); ++SubjectIndex)
	{
		AAlertCrowdSharingSubject* Subject = Subjects[SubjectIndex];
		USkeletalMeshComponent* Mesh = Subject ? Subject->GetMesh() : nullptr;
		USkeletalMeshComponent* Leader = Mesh
			? Cast<USkeletalMeshComponent>(Mesh->LeaderPoseComponent.Get()) : nullptr;
		if (Subject == nullptr
			|| Subject->SubjectIdentity != ExpectedIdentities[SubjectIndex]
			|| Mesh == nullptr || !Mesh->IsVisible()
			|| !Manager->CheckDataForActor(Subject) || Leader == nullptr
			|| Leader == Mesh || Leader->GetOwner() == Subject)
		{
			FailGate(TEXT("CrowdRegistersWithWorldSharingManager"),
				FString::Printf(TEXT("phase=%s identity=%s registered/leader/visible invalid"),
					Phase, *GetNameSafe(Subject)));
			return false;
		}

		UAnimSingleNodeInstance* Single = Leader->GetSingleNodeInstance();
		UAnimationAsset* Asset = Single ? Single->GetAnimationAsset() : nullptr;
		const bool bExpectedAlerted = Subject->bAlerted && Subject->bSharingEligible;
		const TCHAR* ExpectedPath = bExpectedAlerted
			? AlertAnimation : OrdinaryAnimation;
		if (GetPathNameSafe(Asset) != ExpectedPath || Single == nullptr
			|| !FMath::IsFinite(Single->GetCurrentTime()))
		{
			FailGate(TEXT("AlarmChangesOnlyAssignedMembers"), FString::Printf(
				TEXT("phase=%s identity=%s group=%s fact=%d eligible=%d expected=%s actual=%s"),
				Phase, *Subject->SubjectIdentity.ToString(),
				*Subject->CrowdGroup.ToString(), Subject->bAlerted ? 1 : 0,
				Subject->bSharingEligible ? 1 : 0, ExpectedPath, *GetPathNameSafe(Asset)));
			return false;
		}

		USkeletalMeshComponent*& StateLeader = bExpectedAlerted
			? AlertLeader : OrdinaryLeader;
		if (StateLeader != nullptr && StateLeader != Leader)
		{
			FailGate(TEXT("SharedStateUsesEnginePoseLeader"), FString::Printf(
				TEXT("phase=%s same state has multiple leader identities"), Phase));
			return false;
		}
		StateLeader = Leader;
		bExpectedAlerted ? ++AlertedLeaders : ++OrdinaryLeaders;
		FString PoseProblem;
		if (!ValidateLeaderPose(Subject, Leader, PoseProblem))
		{
			FailGate(TEXT("SharedStateUsesEnginePoseLeader"),
				FString::Printf(TEXT("phase=%s %s"), Phase, *PoseProblem));
			return false;
		}
	}

	if (AlertedLeaders > 0 && (AlertLeader == nullptr
		|| OrdinaryLeader == nullptr || AlertLeader == OrdinaryLeader))
	{
		FailGate(TEXT("SharedStateUsesEnginePoseLeader"),
			FString::Printf(TEXT("phase=%s ordinary/alert leader identities did not separate"),
				Phase));
		return false;
	}
	if (AlertedLeaders > 0
		&& AlertLeader->GetOwner() != OrdinaryLeader->GetOwner())
	{
		FailGate(TEXT("SharedStateUsesEnginePoseLeader"),
			FString::Printf(TEXT("phase=%s state leaders have different engine owners"),
				Phase));
		return false;
	}
	if (FCString::Strstr(Phase, TEXT("alert-wave")) != nullptr
		&& (AlertedLeaders != 2 || OrdinaryLeaders != 4))
	{
		FailGate(TEXT("AlarmChangesOnlyAssignedMembers"), FString::Printf(
			TEXT("phase=%s expected alerted/ordinary=2/4 actual=%d/%d"),
			Phase, AlertedLeaders, OrdinaryLeaders));
		return false;
	}
	if (!OriginalOrdinaryLeader.IsValid())
	{
		OriginalOrdinaryLeader = OrdinaryLeader;
	}
	else if (OrdinaryLeader != OriginalOrdinaryLeader.Get())
	{
		FailGate(TEXT("SharedStateUsesEnginePoseLeader"),
			FString::Printf(TEXT("phase=%s ordinary leader identity changed"), Phase));
		return false;
	}
	if (AlertLeader != nullptr && !OriginalAlertLeader.IsValid())
	{
		OriginalAlertLeader = AlertLeader;
	}
	else if (AlertLeader != nullptr && AlertLeader != OriginalAlertLeader.Get())
	{
		FailGate(TEXT("SharedStateUsesEnginePoseLeader"),
			FString::Printf(TEXT("phase=%s alert leader identity changed"), Phase));
		return false;
	}
	if (bRequireRestore && (AlertedLeaders != 0
		|| OrdinaryLeaders != 6 || OrdinaryLeader != OriginalOrdinaryLeader.Get()))
	{
		FailGate(TEXT("ClearedAlarmRestoresOriginalBucket"), FString::Printf(
			TEXT("phase=%s alerted=%d ordinary=%d original_leader=%d"),
			Phase, AlertedLeaders, OrdinaryLeaders,
			OrdinaryLeader == OriginalOrdinaryLeader.Get() ? 1 : 0));
		return false;
	}

	UE_LOG(LogTemp, Display, TEXT(
		"ALERT-CROWD-PHASE phase=%s seed=%d ordinary=%d alerted=%d ordinary_leader=%s alert_leader=%s"),
		Phase, MembershipSeed, OrdinaryLeaders, AlertedLeaders,
		*GetPathNameSafe(OrdinaryLeader), *GetPathNameSafe(AlertLeader));
	return true;
}

void AAlertCrowdSharingFunctionalTest::OnCheckpoint(
	const int32 CheckpointIndex, const double TimeSeconds)
{
	if (bLocalFinishIssued)
	{
		return;
	}
	if (CheckpointIndex == 0)
	{
		if (ValidateSharingState(TEXT("ordinary-baseline"), false))
		{
			ApplyAlertGroup(FirstAlertGroup);
		}
		return;
	}
	if (CheckpointIndex == 1)
	{
		if (ValidateSharingState(TEXT("first-alert-wave"), false))
		{
			ApplyAlertGroup(SecondAlertGroup);
		}
		return;
	}
	if (CheckpointIndex == 2)
	{
		if (ValidateSharingState(TEXT("second-alert-wave"), false))
		{
			ApplyAlertGroup(NAME_None);
		}
		return;
	}
	if (!ValidateSharingState(TEXT("cleared"), true))
	{
		return;
	}

	for (int32 Index = 0; Index < Subjects.Num(); ++Index)
	{
		const AAlertCrowdSharingSubject* Subject = Subjects[Index];
		const double Elapsed = TimeSeconds - StartWorldSeconds;
		const double Distance = FVector::Dist(
			Subject->GetActorLocation(), StartLocations[Index]);
		const double Required = Subject->TravelSpeed * Elapsed * 0.20;
		const UCharacterMovementComponent* Movement = Subject->GetCharacterMovement();
		const double Speed = Movement ? Movement->Velocity.Size2D() : 0.0;
		if (Distance < Required || Speed < Subject->TravelSpeed * 0.20
			|| MovingFrames[Index] * 2 < SampledFrames[Index])
		{
			FailGate(TEXT("CrowdContinuesMovingThroughStateChanges"), FString::Printf(
				TEXT("identity=%s distance=%.2f required=%.2f speed=%.2f moving_frames=%d/%d"),
				*Subject->SubjectIdentity.ToString(), Distance, Required, Speed,
				MovingFrames[Index], SampledFrames[Index]));
			return;
		}
	}
	if (LeaderTimeAdvances < 20)
	{
		FailGate(TEXT("LeaderAnimationRemainsLive"), FString::Printf(
			TEXT("leader animation time advanced only %d samples"), LeaderTimeAdvances));
		return;
	}

	UE_LOG(LogTemp, Display, TEXT(
		"%s seed=%d phases=4 exact_subjects=6 engine_manager=1 leader_time_advances=%d movement=continuous"),
		IsAdmissionProbe()
			? TEXT("ALERT-CROWD-ADMISSION-SUCCEEDED")
			: TEXT("ALERT-CROWD-SHARING-SUCCEEDED"),
		MembershipSeed, LeaderTimeAdvances);
}
