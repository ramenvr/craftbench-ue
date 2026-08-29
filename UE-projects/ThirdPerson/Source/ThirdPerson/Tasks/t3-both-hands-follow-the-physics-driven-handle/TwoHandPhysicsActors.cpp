// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-both-hands-follow-the-physics-driven-handle/TwoHandPhysicsActors.h"

#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"

ATwoHandPhysicsHandle::ATwoHandPhysicsHandle()
{
	PrimaryActorTick.bCanEverTick = false;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);

	AnchorBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("AnchorBody"));
	AnchorBody->SetupAttachment(SceneRoot);
	AnchorBody->SetMobility(EComponentMobility::Movable);
	AnchorBody->SetSimulatePhysics(false);

	HandleBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HandleBody"));
	HandleBody->SetupAttachment(SceneRoot);
	HandleBody->SetMobility(EComponentMobility::Movable);
	HandleBody->SetSimulatePhysics(true);
	HandleBody->SetEnableGravity(false);
	HandleBody->SetLinearDamping(1.2f);
	HandleBody->SetAngularDamping(2.0f);

	Constraint = CreateDefaultSubobject<UPhysicsConstraintComponent>(TEXT("HandleConstraint"));
	Constraint->SetupAttachment(SceneRoot);
	Constraint->SetDisableCollision(true);
	Constraint->SetLinearXLimit(ELinearConstraintMotion::LCM_Limited, 95.0f);
	Constraint->SetLinearYLimit(ELinearConstraintMotion::LCM_Limited, 95.0f);
	Constraint->SetLinearZLimit(ELinearConstraintMotion::LCM_Limited, 60.0f);
	Constraint->SetAngularSwing1Limit(EAngularConstraintMotion::ACM_Limited, 30.0f);
	Constraint->SetAngularSwing2Limit(EAngularConstraintMotion::ACM_Limited, 30.0f);
	Constraint->SetAngularTwistLimit(EAngularConstraintMotion::ACM_Limited, 25.0f);
}

void ATwoHandPhysicsHandle::BeginPlay()
{
	Super::BeginPlay();
	Constraint->SetConstrainedComponents(AnchorBody, NAME_None, HandleBody, NAME_None);
}

void ATwoHandPhysicsHandle::ApplyWorldImpulse(const FVector& WorldImpulse)
{
	if (HandleBody != nullptr && HandleBody->IsSimulatingPhysics())
	{
		HandleBody->AddImpulse(WorldImpulse, NAME_None, false);
	}
}

FTransform ATwoHandPhysicsHandle::GetLeftGripWorldTransform() const
{
	return HandleBody ? LeftGripLocal * HandleBody->GetComponentTransform()
		: FTransform::Identity;
}

FTransform ATwoHandPhysicsHandle::GetRightGripWorldTransform() const
{
	return HandleBody ? RightGripLocal * HandleBody->GetComponentTransform()
		: FTransform::Identity;
}

ATwoHandRigCharacter::ATwoHandRigCharacter()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	if (USkeletalMeshComponent* CharacterMesh = GetMesh())
	{
		CharacterMesh->VisibilityBasedAnimTickOption =
			EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		CharacterMesh->bEnableUpdateRateOptimizations = false;
		CharacterMesh->AddTickPrerequisiteActor(this);
	}
}

void ATwoHandRigCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	USkeletalMeshComponent* CharacterMesh = GetMesh();
	if (TrackedHandle == nullptr || CharacterMesh == nullptr)
	{
		return;
	}

	const FTransform MeshWorld = CharacterMesh->GetComponentTransform();
	LeftHandTarget = TrackedHandle->GetLeftGripWorldTransform().GetRelativeTransform(MeshWorld);
	RightHandTarget = TrackedHandle->GetRightGripWorldTransform().GetRelativeTransform(MeshWorld);
	++TargetSampleSerial;
}

void UTwoHandRigAnimInstanceBase::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	LeftHandTarget = FTransform::Identity;
	RightHandTarget = FTransform::Identity;
	bRigEnabled = false;
	TargetSampleSerial = 0;
}

void UTwoHandRigAnimInstanceBase::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	const ATwoHandRigCharacter* Character = Cast<ATwoHandRigCharacter>(TryGetPawnOwner());
	if (Character == nullptr || Character->TrackedHandle == nullptr)
	{
		bRigEnabled = false;
		return;
	}
	LeftHandTarget = Character->LeftHandTarget;
	RightHandTarget = Character->RightHandTarget;
	TargetSampleSerial = Character->TargetSampleSerial;
	bRigEnabled = TargetSampleSerial > 0;
}
