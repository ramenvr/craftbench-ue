// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-the-guard-resumes-patrol-after-the-chase/GuardPatrolChaseTypes.h"

#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace GuardPatrolChase
{
const FName AlertSourceTag(TEXT("GuardAlertSource"));
const FName MarkerATag(TEXT("GuardPatrolMarker.A"));
const FName MarkerBTag(TEXT("GuardPatrolMarker.B"));
const FName SubjectTag(TEXT("GuardPatrolSubject"));
const FName TargetTag(TEXT("GuardChaseTarget"));
const FName AlertActiveKey(TEXT("AlertActive"));
const FName LiveTargetKey(TEXT("LiveTarget"));
}

AGuardAlertSource::AGuardAlertSource()
{
	PrimaryActorTick.bCanEverTick = false;
	VisibleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleBody"));
	SetRootComponent(VisibleBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (SphereMesh.Succeeded())
	{
		VisibleBody->SetStaticMesh(SphereMesh.Object);
	}
	VisibleBody->SetRelativeScale3D(FVector(0.35));
	VisibleBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tags.Add(GuardPatrolChase::AlertSourceTag);
}

void AGuardAlertSource::PublishAlert(AActor* InLiveTarget)
{
	if (!IsValid(InLiveTarget))
	{
		return;
	}
	LiveTarget = InLiveTarget;
	bAlertActive = true;
	OnAlertChanged.Broadcast(true, LiveTarget);
}

void AGuardAlertSource::ClearAlert()
{
	bAlertActive = false;
	LiveTarget = nullptr;
	OnAlertChanged.Broadcast(false, nullptr);
}

AGuardPatrolMarker::AGuardPatrolMarker()
{
	PrimaryActorTick.bCanEverTick = false;
	VisibleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleBody"));
	SetRootComponent(VisibleBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		VisibleBody->SetStaticMesh(CylinderMesh.Object);
	}
	VisibleBody->SetRelativeScale3D(FVector(0.45, 0.45, 1.2));
	VisibleBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

FVector AGuardPatrolMarker::GetNavAgentLocation() const
{
	if (const UWorld* World = GetWorld())
	{
		FHitResult FloorHit;
		FCollisionQueryParams QueryParams(
			TEXT("GuardPatrolMarkerNavGoal"), false, this);
		const FVector TraceStart = GetActorLocation() + FVector(0.0, 0.0, 200.0);
		const FVector TraceEnd = GetActorLocation() - FVector(0.0, 0.0, 1000.0);
		if (World->LineTraceSingleByChannel(
			FloorHit, TraceStart, TraceEnd, ECC_Visibility, QueryParams))
		{
			return FloorHit.ImpactPoint;
		}
	}
	return GetActorLocation();
}

void AGuardPatrolMarker::GetMoveGoalReachTest(
	const AActor* MovingActor,
	const FVector& MoveOffset,
	FVector& GoalOffset,
	float& GoalRadius,
	float& GoalHalfHeight) const
{
	(void)MovingActor;
	(void)MoveOffset;
	GoalOffset = FVector::ZeroVector;
	GoalRadius = 60.0f;
	GoalHalfHeight = 140.0f;
}

AGuardChaseTarget::AGuardChaseTarget()
{
	PrimaryActorTick.bCanEverTick = false;
	VisibleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleBody"));
	SetRootComponent(VisibleBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		VisibleBody->SetStaticMesh(CubeMesh.Object);
	}
	VisibleBody->SetRelativeScale3D(FVector(0.55, 0.55, 1.1));
	VisibleBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tags.Add(GuardPatrolChase::TargetTag);
}

AGuardPatrolCharacter::AGuardPatrolCharacter()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(GuardPatrolChase::SubjectTag);
	AIControllerClass = AGuardPatrolAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	GetCapsuleComponent()->InitCapsuleSize(42.0f, 96.0f);
	GetCharacterMovement()->MaxWalkSpeed = 360.0f;
	GetCharacterMovement()->bOrientRotationToMovement = true;
	bUseControllerRotationYaw = false;

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MannyMesh(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	if (MannyMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(MannyMesh.Object);
	}
	static ConstructorHelpers::FClassFinder<UAnimInstance> MannyAnim(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	if (MannyAnim.Succeeded())
	{
		GetMesh()->SetAnimInstanceClass(MannyAnim.Class);
	}
	GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -96.0));
	GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
}

AGuardPatrolAIController::AGuardPatrolAIController()
{
	PrimaryActorTick.bCanEverTick = false;
	BlackboardComponent = CreateDefaultSubobject<UBlackboardComponent>(TEXT("Blackboard"));
	BehaviorTreeComponent = CreateDefaultSubobject<UBehaviorTreeComponent>(TEXT("BehaviorTree"));
	BrainComponent = BehaviorTreeComponent;
	bStartAILogicOnPossess = true;
}

void AGuardPatrolAIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	const AGuardPatrolCharacter* Guard = Cast<AGuardPatrolCharacter>(InPawn);
	if (Guard == nullptr || Guard->DecisionTree == nullptr ||
		Guard->DecisionTree->BlackboardAsset == nullptr)
	{
		return;
	}

	UBlackboardComponent* EffectiveBlackboard = BlackboardComponent;
	if (!UseBlackboard(Guard->DecisionTree->BlackboardAsset, EffectiveBlackboard) ||
		EffectiveBlackboard != BlackboardComponent)
	{
		return;
	}
	BindAlertSource();
	BehaviorTreeComponent->StartTree(*Guard->DecisionTree, EBTExecutionMode::Looped);
}

void AGuardPatrolAIController::OnUnPossess()
{
	if (BoundAlertSource != nullptr)
	{
		BoundAlertSource->OnAlertChanged.RemoveDynamic(
			this, &AGuardPatrolAIController::HandleAlertChanged);
	}
	BoundAlertSource = nullptr;
	if (BehaviorTreeComponent != nullptr)
	{
		BehaviorTreeComponent->StopTree(EBTStopMode::Safe);
	}
	Super::OnUnPossess();
}

void AGuardPatrolAIController::BindAlertSource()
{
	BoundAlertSource = nullptr;
	if (GetWorld() == nullptr)
	{
		return;
	}
	for (TActorIterator<AGuardAlertSource> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(GuardPatrolChase::AlertSourceTag))
		{
			if (BoundAlertSource != nullptr)
			{
				BoundAlertSource = nullptr;
				return;
			}
			BoundAlertSource = *It;
		}
	}
	if (BoundAlertSource != nullptr)
	{
		BoundAlertSource->OnAlertChanged.AddUniqueDynamic(
			this, &AGuardPatrolAIController::HandleAlertChanged);
		HandleAlertChanged(BoundAlertSource->IsAlertActive(),
			BoundAlertSource->GetLiveTarget());
	}
}

void AGuardPatrolAIController::HandleAlertChanged(
	const bool bAlertActive, AActor* LiveTarget)
{
	if (BlackboardComponent == nullptr)
	{
		return;
	}
	BlackboardComponent->SetValueAsObject(
		GuardPatrolChase::LiveTargetKey, bAlertActive ? LiveTarget : nullptr);
	BlackboardComponent->SetValueAsBool(
		GuardPatrolChase::AlertActiveKey, bAlertActive && IsValid(LiveTarget));
}

UGuardBTTask_SelectNextPatrolPoint::UGuardBTTask_SelectNextPatrolPoint()
{
	NodeName = TEXT("Select Next Live Patrol Point");
	BlackboardKey.AddObjectFilter(
		this, GET_MEMBER_NAME_CHECKED(UGuardBTTask_SelectNextPatrolPoint, BlackboardKey),
		AActor::StaticClass());
}

EBTNodeResult::Type UGuardBTTask_SelectNextPatrolPoint::ExecuteTask(
	UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	(void)NodeMemory;
	UBlackboardComponent* Blackboard = OwnerComp.GetBlackboardComponent();
	UWorld* World = OwnerComp.GetWorld();
	if (Blackboard == nullptr || World == nullptr)
	{
		return EBTNodeResult::Failed;
	}

	AActor* MarkerA = nullptr;
	AActor* MarkerB = nullptr;
	for (TActorIterator<AGuardPatrolMarker> It(World); It; ++It)
	{
		if (It->ActorHasTag(GuardPatrolChase::MarkerATag))
		{
			if (MarkerA != nullptr)
			{
				return EBTNodeResult::Failed;
			}
			MarkerA = *It;
		}
		if (It->ActorHasTag(GuardPatrolChase::MarkerBTag))
		{
			if (MarkerB != nullptr)
			{
				return EBTNodeResult::Failed;
			}
			MarkerB = *It;
		}
	}
	if (MarkerA == nullptr || MarkerB == nullptr || MarkerA == MarkerB)
	{
		return EBTNodeResult::Failed;
	}

	const FName KeyName = GetSelectedBlackboardKey();
	AActor* Current = Cast<AActor>(Blackboard->GetValueAsObject(KeyName));
	Blackboard->SetValueAsObject(KeyName, Current == MarkerA ? MarkerB : MarkerA);
	return EBTNodeResult::Succeeded;
}
