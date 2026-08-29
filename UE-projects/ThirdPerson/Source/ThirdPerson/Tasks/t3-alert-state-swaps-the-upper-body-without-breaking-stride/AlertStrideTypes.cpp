// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/AlertStrideTypes.h"

#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StateTreeComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/SkeletalMesh.h"
#include "StateTree.h"
#include "StateTreeExecutionContext.h"
#include "UObject/ConstructorHelpers.h"

AAlertStrideSignalActor::AAlertStrideSignalActor()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Tags.Add(TEXT("AlertStrideSignal"));
}

void AAlertStrideSignalActor::SetAlertActive(const bool bNewAlertActive)
{
	if (bAlertActive != bNewAlertActive)
	{
		bAlertActive = bNewAlertActive;
		++Revision;
	}
}

void UAlertStrideAnimInstance::NativeUpdateAnimation(const float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	const APawn* Pawn = TryGetPawnOwner();
	GroundSpeed = Pawn ? Pawn->GetVelocity().Size2D() : 0.0f;
}

AAlertStrideCharacter::AAlertStrideCharacter(
	const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(TEXT("AlertStrideSubject"));
	BehaviorStateTree = CreateDefaultSubobject<UStateTreeComponent>(
		TEXT("AlertStrideStateTree"));
	BehaviorStateTree->SetStartLogicAutomatically(false);
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->bRunPhysicsWithNoController = true;
	GetCharacterMovement()->MaxAcceleration = 4096.0f;

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	if (MeshFinder.Succeeded())
	{
		GetMesh()->SetSkeletalMesh(MeshFinder.Object);
		GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -90.0));
		GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	}
	GetMesh()->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	GetMesh()->bEnableUpdateRateOptimizations = false;
}

void AAlertStrideCharacter::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bDriveEnabled && !DriveDirection.IsNearlyZero())
	{
		AddMovementInput(DriveDirection.GetSafeNormal(), 1.0f, true);
	}
}

bool AAlertStrideCharacter::StartScenario(
	UStateTree* StateTree, AAlertStrideSignalActor* Signal,
	const float WalkSpeed, const FVector WorldDirection)
{
	if (BehaviorStateTree == nullptr || StateTree == nullptr || Signal == nullptr
		|| !StateTree->IsReadyToRun() || WalkSpeed <= 0.0f
		|| WorldDirection.IsNearlyZero())
	{
		return false;
	}
	if (BehaviorStateTree->IsRunning())
	{
		BehaviorStateTree->StopLogic(TEXT("Alert stride scenario restart"));
	}
	SignalActor = Signal;
	SignalActor->SetAlertActive(false);
	DriveDirection = WorldDirection.GetSafeNormal();
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
	BehaviorStateTree->SetStateTree(StateTree);
	BehaviorStateTree->StartLogic();
	bDriveEnabled = BehaviorStateTree->IsRunning();
	return bDriveEnabled;
}

void AAlertStrideCharacter::StopScenario()
{
	bDriveEnabled = false;
	if (BehaviorStateTree && BehaviorStateTree->IsRunning())
	{
		BehaviorStateTree->StopLogic(TEXT("Alert stride scenario stopped"));
	}
	SignalActor = nullptr;
}

TArray<FName> AAlertStrideCharacter::GetEngineActiveStateNames() const
{
#if WITH_GAMEPLAY_DEBUGGER
	return BehaviorStateTree ? BehaviorStateTree->GetActiveStateNames()
		: TArray<FName>();
#else
	return TArray<FName>();
#endif
}

AAlertStrideScenario::AAlertStrideScenario()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Tags.Add(TEXT("AlertStrideScenario"));
}

bool FAlertStrideSignalCondition::TestCondition(
	FStateTreeExecutionContext& Context) const
{
	const FInstanceDataType& Data = Context.GetInstanceData(*this);
	const AAlertStrideCharacter* Character =
		Cast<AAlertStrideCharacter>(Context.GetOwner());
	const AAlertStrideSignalActor* Signal = Character
		? Character->GetSignalActor() : nullptr;
	return Signal != nullptr && Signal->IsAlertActive() == Data.bExpectedAlert;
}

FAlertStrideLinkLayerTask::FAlertStrideLinkLayerTask()
{
	bShouldCallTick = false;
	bConsideredForScheduling = false;
	bShouldStateChangeOnReselect = false;
}

EStateTreeRunStatus FAlertStrideLinkLayerTask::EnterState(
	FStateTreeExecutionContext& Context,
	const FStateTreeTransitionResult& Transition) const
{
	const FInstanceDataType& Data = Context.GetInstanceData(*this);
	AAlertStrideCharacter* Character =
		Cast<AAlertStrideCharacter>(Context.GetOwner());
	USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
	if (Mesh == nullptr || Data.AlertLayerClass == nullptr)
	{
		return EStateTreeRunStatus::Failed;
	}
	Mesh->LinkAnimClassLayers(Data.AlertLayerClass);
	return Mesh->GetLinkedAnimLayerInstanceByClass(Data.AlertLayerClass)
		? EStateTreeRunStatus::Running
		: EStateTreeRunStatus::Failed;
}

void FAlertStrideLinkLayerTask::ExitState(
	FStateTreeExecutionContext& Context,
	const FStateTreeTransitionResult& Transition) const
{
	const FInstanceDataType& Data = Context.GetInstanceData(*this);
	AAlertStrideCharacter* Character =
		Cast<AAlertStrideCharacter>(Context.GetOwner());
	if (USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr)
	{
		if (Data.AlertLayerClass)
		{
			Mesh->UnlinkAnimClassLayers(Data.AlertLayerClass);
		}
	}
}
