// Copyright CraftBench. All Rights Reserved.

#include "RailBlockActor.h"

#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"

ARailBlockActor::ARailBlockActor()
{
	Tags.Add(FName("RailBlock"));
	PrimaryActorTick.bCanEverTick = true;

	RailJoint = CreateDefaultSubobject<UPhysicsConstraintComponent>(TEXT("RailJoint"));
	RailJoint->SetupAttachment(GetRootComponent());
	RailJoint->SetLinearXLimit(ELinearConstraintMotion::LCM_Free, 0.0f);
	RailJoint->SetLinearYLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
	RailJoint->SetLinearZLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
	RailJoint->SetAngularSwing1Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetAngularSwing2Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetAngularTwistLimit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetDisableCollision(true);
}

void ARailBlockActor::BeginPlay()
{
	Super::BeginPlay();

	if (RailJoint != nullptr && Block != nullptr)
	{
		RailJoint->SetConstrainedComponents(nullptr, NAME_None, Block, NAME_None);
	}
}

void ARailBlockActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (RailJoint == nullptr || Block == nullptr)
	{
		return;
	}
	// Re-anchor at wherever the block is NOW. Nothing to tune and nothing to detect:
	// the joint stops the block acquiring off-axis or angular motion, and it forgets
	// the line it was defined against every single frame.
	RailJoint->TermComponentConstraint();
	RailJoint->SetConstrainedComponents(nullptr, NAME_None, Block, NAME_None);
}
