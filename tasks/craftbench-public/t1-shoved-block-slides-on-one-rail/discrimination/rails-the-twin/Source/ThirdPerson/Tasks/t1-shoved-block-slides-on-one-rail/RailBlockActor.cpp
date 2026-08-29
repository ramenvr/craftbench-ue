// Copyright CraftBench. All Rights Reserved.
//
// VARIANT rails-the-twin. The railed block is solved correctly, and the COMPARISON
// block is quietly given the same treatment -- which is how an agent could make the
// off-axis and no-spin gates unfalsifiable if the twin were not itself gauged.

#include "RailBlockActor.h"

#include "Components/PrimitiveComponent.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"

namespace
{
	/** Wires one block to a world-anchored, one-axis joint. */
	void RailUp(UPhysicsConstraintComponent* Joint, UPrimitiveComponent* Body)
	{
		if (Joint == nullptr || Body == nullptr)
		{
			return;
		}
		Joint->SetLinearXLimit(ELinearConstraintMotion::LCM_Free, 0.0f);
		Joint->SetLinearYLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
		Joint->SetLinearZLimit(ELinearConstraintMotion::LCM_Locked, 0.0f);
		Joint->SetAngularSwing1Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
		Joint->SetAngularSwing2Limit(EAngularConstraintMotion::ACM_Locked, 0.0f);
		Joint->SetAngularTwistLimit(EAngularConstraintMotion::ACM_Locked, 0.0f);
		Joint->SetDisableCollision(true);
		Joint->SetConstrainedComponents(nullptr, NAME_None, Body, NAME_None);
	}
}

ARailBlockActor::ARailBlockActor()
{
	Tags.Add(FName("RailBlock"));

	RailJoint = CreateDefaultSubobject<UPhysicsConstraintComponent>(TEXT("RailJoint"));
	RailJoint->SetupAttachment(GetRootComponent());
}

void ARailBlockActor::BeginPlay()
{
	Super::BeginPlay();

	RailUp(RailJoint, Block);

	// ...and the same to the comparison block, built at runtime on the twin itself.
	TArray<AActor*> Twins;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("TwinBlock")), Twins);
	for (AActor* Twin : Twins)
	{
		UPrimitiveComponent* const TwinBody =
			Twin ? Cast<UPrimitiveComponent>(Twin->GetRootComponent()) : nullptr;
		if (TwinBody == nullptr)
		{
			continue;
		}
		UPhysicsConstraintComponent* const TwinJoint =
			NewObject<UPhysicsConstraintComponent>(Twin);
		TwinJoint->RegisterComponent();
		TwinJoint->AttachToComponent(TwinBody,
			FAttachmentTransformRules::SnapToTargetIncludingScale);
		RailUp(TwinJoint, TwinBody);
	}
}
