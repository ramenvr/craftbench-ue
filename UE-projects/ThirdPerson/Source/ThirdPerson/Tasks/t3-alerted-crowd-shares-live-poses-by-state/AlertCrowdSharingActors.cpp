// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alerted-crowd-shares-live-poses-by-state/AlertCrowdSharingActors.h"

#include "AnimationSharingManager.h"
#include "AnimationSharingSetup.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FName SubjectTag(TEXT("AlertCrowdSharingSubject"));
}

AAlertCrowdSharingSubject::AAlertCrowdSharingSubject()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.AddUnique(SubjectTag);
	GetCapsuleComponent()->InitCapsuleSize(42.0f, 96.0f);

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> Manny(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	if (Manny.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(Manny.Object);
	}
	GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));
	GetMesh()->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
	GetMesh()->SetAnimInstanceClass(nullptr);
	GetMesh()->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

	bUseControllerRotationYaw = false;
	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bOrientRotationToMovement = false;
	Movement->MaxWalkSpeed = TravelSpeed;
}

void AAlertCrowdSharingSubject::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UCharacterMovementComponent* Movement = GetCharacterMovement();
	if (bTravelEnabled && Movement != nullptr && !TravelDirection.IsNearlyZero())
	{
		Movement->MaxWalkSpeed = FMath::Max(1.0f, TravelSpeed);
		// This is the engine CharacterMovement input accumulator, never a direct
		// transform write. The verifier samples dense frame displacement.
		Movement->AddInputVector(TravelDirection.GetSafeNormal());
	}
}

void UAlertCrowdSharingStateProcessorBase::ProcessActorState_Implementation(
	int32& OutState, AActor* InActor, const uint8 CurrentState,
	const uint8 OnDemandState, bool& bShouldProcess)
{
	const AAlertCrowdSharingSubject* Subject =
		Cast<AAlertCrowdSharingSubject>(InActor);
	(void)OnDemandState;
	bShouldProcess = Subject != nullptr && Subject->bSharingEligible;
	if (bShouldProcess)
	{
		OutState = static_cast<int32>(EvaluateAlertState(Subject));
	}
	else
	{
		OutState = static_cast<int32>(CurrentState);
	}
}

UEnum* UAlertCrowdSharingStateProcessorBase::GetAnimationStateEnum_Implementation()
{
	return StaticEnum<EAlertCrowdSharingState>();
}

EAlertCrowdSharingState
UAlertCrowdSharingStateProcessorBase::EvaluateAlertState_Implementation(
	const AAlertCrowdSharingSubject* Subject) const
{
	return EAlertCrowdSharingState::Ordinary;
}

EAlertCrowdSharingState
UAlertCrowdSharingStateProcessorBase::ResolveAlertStateFromFlag(
	const bool bAlerted)
{
	return bAlerted
		? EAlertCrowdSharingState::Alerted
		: EAlertCrowdSharingState::Ordinary;
}

AAlertCrowdSharingHost::AAlertCrowdSharingHost()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.AddUnique(FName(TEXT("AlertCrowdSharingHost")));
}

void AAlertCrowdSharingHost::BeginPlay()
{
	Super::BeginPlay();
	// One-shot next-frame initialization lets all placed subject components
	// complete BeginPlay. It is not a polling or retry loop.
	GetWorldTimerManager().SetTimerForNextTick(
		this, &AAlertCrowdSharingHost::InitializeSharingOnce);
}

void AAlertCrowdSharingHost::InitializeSharingOnce()
{
	UWorld* World = GetWorld();
	const UAnimationSharingSetup* Setup = SharingSetup.LoadSynchronous();
	if (World == nullptr || Setup == nullptr)
	{
		return;
	}

	UAnimationSharingManager::CreateAnimationSharingManager(this, Setup);
	UAnimationSharingManager* Manager =
		UAnimationSharingManager::GetManagerForWorld(World);
	if (Manager == nullptr)
	{
		return;
	}

	TArray<AActor*> Subjects;
	UGameplayStatics::GetAllActorsWithTag(World, SubjectTag, Subjects);
	Subjects.Sort([](const AActor& Left, const AActor& Right)
	{
		return Left.GetPathName() < Right.GetPathName();
	});
	for (AActor* Actor : Subjects)
	{
		AAlertCrowdSharingSubject* Subject =
			Cast<AAlertCrowdSharingSubject>(Actor);
		USkeletalMeshComponent* Mesh = Subject ? Subject->GetMesh() : nullptr;
		const USkeletalMesh* SkeletalMesh = Mesh
			? Mesh->GetSkeletalMeshAsset() : nullptr;
		const USkeleton* Skeleton = SkeletalMesh
			? SkeletalMesh->GetSkeleton() : nullptr;
		if (Subject != nullptr && Skeleton != nullptr)
		{
			Manager->RegisterActorWithSkeletonBP(Subject, Skeleton);
		}
	}
}
