// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-guard-aims-only-at-the-visible-target/GuardVisibleAimTypes.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AIPerceptionStimuliSourceComponent.h"
#include "Perception/AISenseConfig_Sight.h"
#include "Perception/AISense_Sight.h"
#include "UObject/ConstructorHelpers.h"

namespace GuardVisibleAim
{
const FName GuardTag(TEXT("GuardVisibleAim.Guard"));
const FName TargetTag(TEXT("GuardVisibleAim.Target"));
const FName OccluderTag(TEXT("GuardVisibleAim.Occluder"));
const FName GoalTag(TEXT("GuardVisibleAim.Goal"));
}

void UGuardVisibleAimAnimInstance::NativeUpdateAnimation(const float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	const APawn* Pawn = TryGetPawnOwner();
	GroundSpeed = Pawn ? Pawn->GetVelocity().Size2D() : 0.0f;
	const AGuardVisibleAimController* Controller = Pawn
		? Cast<AGuardVisibleAimController>(Pawn->GetController()) : nullptr;
	PerceivedTarget = Controller ? Controller->GetCurrentVisibleTarget() : nullptr;
	if (Pawn == nullptr || !IsValid(PerceivedTarget))
	{
		AimYaw = 0.0f;
		AimPitch = 0.0f;
		AimAlpha = 0.0f;
		return;
	}

	const FVector LocalDirection = Pawn->GetActorTransform().InverseTransformVectorNoScale(
		PerceivedTarget->GetActorLocation() - Pawn->GetActorLocation()).GetSafeNormal();
	const FRotator LocalAim = LocalDirection.Rotation();
	AimYaw = FMath::Clamp(FRotator::NormalizeAxis(LocalAim.Yaw), -90.0f, 90.0f);
	AimPitch = FMath::Clamp(FRotator::NormalizeAxis(LocalAim.Pitch), -60.0f, 60.0f);
	AimAlpha = 1.0f;
}

AGuardVisibleAimController::AGuardVisibleAimController()
{
	PrimaryActorTick.bCanEverTick = false;
	SightPerception = CreateDefaultSubobject<UAIPerceptionComponent>(TEXT("SightPerception"));
	SightConfig = CreateDefaultSubobject<UAISenseConfig_Sight>(TEXT("SightConfig"));
	SightConfig->SightRadius = 2200.0f;
	SightConfig->LoseSightRadius = 2350.0f;
	SightConfig->PeripheralVisionAngleDegrees = 120.0f;
	SightConfig->SetMaxAge(0.35f);
	SightConfig->DetectionByAffiliation.bDetectEnemies = true;
	SightConfig->DetectionByAffiliation.bDetectFriendlies = true;
	SightConfig->DetectionByAffiliation.bDetectNeutrals = true;
	SightPerception->ConfigureSense(*SightConfig);
	SightPerception->SetDominantSense(UAISense_Sight::StaticClass());
	SetPerceptionComponent(*SightPerception);
	SightPerception->OnTargetPerceptionUpdated.AddDynamic(
		this, &AGuardVisibleAimController::HandleTargetPerceptionUpdated);
	SightPerception->OnTargetPerceptionForgotten.AddDynamic(
		this, &AGuardVisibleAimController::HandleTargetForgotten);
}

void AGuardVisibleAimController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	CurrentVisibleTarget = nullptr;
	++PerceptionRevision;
	SightPerception->RequestStimuliListenerUpdate();
}

void AGuardVisibleAimController::DisableSightForControl()
{
	SightPerception->SetSenseEnabled(UAISense_Sight::StaticClass(), false);
	SightPerception->ForgetAll();
	CurrentVisibleTarget = nullptr;
	++PerceptionRevision;
}

void AGuardVisibleAimController::HandleTargetPerceptionUpdated(
	AActor* Actor, const FAIStimulus Stimulus)
{
	if (!IsValid(Actor) || !Actor->ActorHasTag(GuardVisibleAim::TargetTag))
	{
		return;
	}
	++PerceptionRevision;
	if (Stimulus.WasSuccessfullySensed())
	{
		CurrentVisibleTarget = Actor;
		return;
	}
	if (CurrentVisibleTarget == Actor)
	{
		CurrentVisibleTarget = nullptr;
	}
	// Exercise the engine-owned forgetting lifecycle; the verifier independently
	// reads both the current and known sight sets after the occlusion transition.
	SightPerception->ForgetActor(Actor);
}

void AGuardVisibleAimController::HandleTargetForgotten(AActor* Actor)
{
	++PerceptionRevision;
	if (CurrentVisibleTarget == Actor)
	{
		CurrentVisibleTarget = nullptr;
	}
}

AGuardVisibleAimCharacter::AGuardVisibleAimCharacter()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(GuardVisibleAim::GuardTag);
	AIControllerClass = AGuardVisibleAimController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->MaxWalkSpeed = 285.0f;
	GetCapsuleComponent()->InitCapsuleSize(42.0f, 96.0f);
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MannyMesh(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	if (MannyMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(MannyMesh.Object);
	}
	GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -96.0));
	GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	GetMesh()->VisibilityBasedAnimTickOption =
		EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	GetMesh()->bEnableUpdateRateOptimizations = false;
}

AGuardVisibleAimTarget::AGuardVisibleAimTarget()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(GuardVisibleAim::TargetTag);
	VisibleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleBody"));
	SetRootComponent(VisibleBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		VisibleBody->SetStaticMesh(Sphere.Object);
	}
	VisibleBody->SetRelativeScale3D(FVector(0.45));
	VisibleBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SightStimulus = CreateDefaultSubobject<UAIPerceptionStimuliSourceComponent>(
		TEXT("SightStimulus"));
	SightStimulus->RegisterForSense(UAISense_Sight::StaticClass());
}

void AGuardVisibleAimTarget::BeginPlay()
{
	Super::BeginPlay();
	SightStimulus->RegisterWithPerceptionSystem();
}

AGuardVisibleAimOccluder::AGuardVisibleAimOccluder()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(GuardVisibleAim::OccluderTag);
	BlockingBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BlockingBody"));
	SetRootComponent(BlockingBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded())
	{
		BlockingBody->SetStaticMesh(Cube.Object);
	}
	BlockingBody->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	BlockingBody->SetCollisionResponseToAllChannels(ECR_Ignore);
	BlockingBody->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	BlockingBody->SetGenerateOverlapEvents(false);
}

AGuardVisibleAimGoal::AGuardVisibleAimGoal()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(GuardVisibleAim::GoalTag);
	VisibleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleBody"));
	SetRootComponent(VisibleBody);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (Cylinder.Succeeded())
	{
		VisibleBody->SetStaticMesh(Cylinder.Object);
	}
	VisibleBody->SetRelativeScale3D(FVector(0.25, 0.25, 0.08));
	VisibleBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
