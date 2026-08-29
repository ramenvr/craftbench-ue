// Copyright CraftBench. All Rights Reserved.

#include "RailBlockActor.h"

#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"

ARailBlockActor::ARailBlockActor()
{
	Tags.Add(FName("RailBlock"));

	RailJoint = CreateDefaultSubobject<UPhysicsConstraintComponent>(TEXT("RailJoint"));
	RailJoint->SetupAttachment(GetRootComponent());

	// The block is placed square with the rail, so the block's OWN forward axis
	// already points along the rail: free that one translation and lock the rest.
	// Nothing here names a world axis, which is what makes it work for a rail that
	// runs at an angle.
	RailJoint->SetLinearXLimit(ELinearConstraintMotion::LCM_Free, 0.0f);
	RailJoint->SetLinearYLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
	RailJoint->SetLinearZLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
	RailJoint->SetAngularSwing1Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetAngularSwing2Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetAngularTwistLimit(EAngularConstraintMotion::ACM_Locked, 0.0f);
	RailJoint->SetDisableCollision(true);

	// Projection is what makes the rail HOLD rather than merely resist. A single
	// hard, off-axis hit transiently pulls a solved joint open -- measured
	// 2026-08-17, the second shove opened it 20 cm before it recovered, past the
	// 8 cm the level allows -- and it is also what carries the block back after
	// something lifts it off the line. Full correction, 1 cm tolerance.
	RailJoint->ConstraintInstance.SetProjectionParams(true, 1.0f, 1.0f, 1.0f, 1.0f);
}

void ARailBlockActor::BeginPlay()
{
	Super::BeginPlay();

	// Anchored to the WORLD, not to the rail's own body. Both look equivalent -- the
	// rail never moves either way -- but they are not: anchored to the rail's static
	// primitive the joint degraded badly as the block travelled away from where it
	// was defined (measured 2026-08-17: first shove held the line to 0.01 cm, the
	// second, starting 496 cm along, was torn 16.6 cm off it and lost a third of its
	// travel). Against the world the same joint holds 0.00 cm on both shoves.
	if (RailJoint != nullptr && Block != nullptr)
	{
		RailJoint->SetConstrainedComponents(nullptr, NAME_None, Block, NAME_None);
	}
}
