// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/WorkerPlanStateTreeTypes.h"

#include "Components/StateTreeAIComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "StateTree.h"
#include "StateTreeExecutionContext.h"
#include "UObject/ConstructorHelpers.h"

AWorkerPlanSignalActor::AWorkerPlanSignalActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("WorkerPlanSignal"));
}

void AWorkerPlanSignalActor::PublishPlan(AActor* NewDestination)
{
	PlanDestination = NewDestination;
	bSignalActive = IsValid(NewDestination);
	if (bSignalActive)
	{
		++PlanRevision;
	}
}

void AWorkerPlanSignalActor::ClearSignal()
{
	bSignalActive = false;
}

AWorkerPlanAIController::AWorkerPlanAIController(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	StateTreeComponent = CreateDefaultSubobject<UStateTreeAIComponent>(TEXT("WorkerStateTree"));
	StateTreeComponent->SetStartLogicAutomatically(false);
	bStartAILogicOnPossess = false;
	BrainComponent = StateTreeComponent;
}

bool AWorkerPlanAIController::ConfigureStateTree(UStateTree* StateTree)
{
	if (StateTreeComponent == nullptr || StateTree == nullptr || StateTreeComponent->IsRunning())
	{
		return false;
	}
	StateTreeComponent->SetStateTree(StateTree);
	StateTreeComponent->StartLogic();
	return StateTreeComponent->IsRunning();
}

AWorkerPlanSignalActor* AWorkerPlanAIController::ResolveSignalActor()
{
	if (CachedSignalActor.IsValid())
	{
		return CachedSignalActor.Get();
	}
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return nullptr;
	}
	AWorkerPlanSignalActor* Found = nullptr;
	int32 Matches = 0;
	for (TActorIterator<AWorkerPlanSignalActor> It(World); It; ++It)
	{
		if (It->ActorHasTag(TEXT("WorkerPlanSignal")))
		{
			Found = *It;
			++Matches;
		}
	}
	if (Matches == 1)
	{
		CachedSignalActor = Found;
		return Found;
	}
	return nullptr;
}

void AWorkerPlanAIController::RecordSignalRead(const bool bPassed)
{
	++SignalReadCount;
	PassingSignalReadCount += bPassed ? 1 : 0;
}

void AWorkerPlanAIController::RecordNavigationEnter(const EPathFollowingRequestResult::Type Result)
{
	++NavigationEnterCount;
	LastMoveRequestResult = Result;
}

void AWorkerPlanAIController::RecordNavigationExit()
{
	++NavigationExitCount;
}

AWorkerPlanCharacter::AWorkerPlanCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("WorkerPlanSubject"));
	AIControllerClass = AWorkerPlanAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	GetCharacterMovement()->MaxWalkSpeed = 360.0f;
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	if (MeshFinder.Succeeded())
	{
		GetMesh()->SetSkeletalMesh(MeshFinder.Object);
		GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -90.0));
		GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	}
}

bool FWorkerPlanSignalCondition::TestCondition(FStateTreeExecutionContext& Context) const
{
	AWorkerPlanAIController* Controller = Cast<AWorkerPlanAIController>(Context.GetOwner());
	AWorkerPlanSignalActor* Signal = Controller ? Controller->ResolveSignalActor() : nullptr;
	const bool bPass = Signal != nullptr && Signal->IsSignalActive()
		&& IsValid(Signal->GetPlanDestination());
	if (Controller)
	{
		Controller->RecordSignalRead(bPass);
	}
	return bPass;
}

FWorkerPlanNavigateTask::FWorkerPlanNavigateTask()
{
	bShouldCallTick = false;
	bConsideredForScheduling = false;
	bShouldStateChangeOnReselect = false;
}

EStateTreeRunStatus FWorkerPlanNavigateTask::EnterState(
	FStateTreeExecutionContext& Context,
	const FStateTreeTransitionResult& Transition) const
{
	AWorkerPlanAIController* Controller = Cast<AWorkerPlanAIController>(Context.GetOwner());
	AWorkerPlanSignalActor* Signal = Controller ? Controller->ResolveSignalActor() : nullptr;
	AActor* Destination = Signal ? Signal->GetPlanDestination() : nullptr;
	if (Controller == nullptr || Destination == nullptr)
	{
		return EStateTreeRunStatus::Failed;
	}
	const EPathFollowingRequestResult::Type Result = Controller->MoveToActor(
		Destination, 80.0f, true, true, true, nullptr, false);
	Controller->RecordNavigationEnter(Result);
	return Result == EPathFollowingRequestResult::Failed
		? EStateTreeRunStatus::Failed
		: EStateTreeRunStatus::Running;
}

void FWorkerPlanNavigateTask::ExitState(
	FStateTreeExecutionContext& Context,
	const FStateTreeTransitionResult& Transition) const
{
	if (AWorkerPlanAIController* Controller =
		Cast<AWorkerPlanAIController>(Context.GetOwner()))
	{
		Controller->RecordNavigationExit();
	}
}
