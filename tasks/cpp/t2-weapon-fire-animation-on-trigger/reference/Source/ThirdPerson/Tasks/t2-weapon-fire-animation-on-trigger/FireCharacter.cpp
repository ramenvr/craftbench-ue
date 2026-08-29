// Copyright CraftBench. All Rights Reserved.
//
// Reference implementation for t2-weapon-fire-animation-on-trigger.

#include "FireCharacter.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AFireCharacter::AFireCharacter()
{
	Tags.Add(FName("FireHero"));

	// Start state (shipped by the scaffold): the standard animated body.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
	static ConstructorHelpers::FClassFinder<UAnimInstance> AnimFinder(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	if (AnimFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetAnimInstanceClass(AnimFinder.Class);
	}

	// Solution: the one-shot firing clip (a template attack read as firing).
	static ConstructorHelpers::FObjectFinder<UAnimSequence> ClipFinder(
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"));
	if (ClipFinder.Succeeded())
	{
		FireClip = ClipFinder.Object;
	}
}

void AFireCharacter::DoFireStart()
{
	UAnimInstance* Anim = GetMesh() ? GetMesh()->GetAnimInstance() : nullptr;
	if (Anim == nullptr || FireClip == nullptr)
	{
		return;
	}
	// One at a time: a request while the fire is already playing does nothing.
	if (Anim->GetCurrentActiveMontage() != nullptr)
	{
		return;
	}
	// One-shot dynamic montage: natural clip length, single loop, short blends.
	Anim->PlaySlotAnimationAsDynamicMontage(
		FireClip, TEXT("DefaultSlot"),
		/*BlendInTime*/ 0.1f, /*BlendOutTime*/ 0.1f,
		/*InPlayRate*/ 1.0f, /*LoopCount*/ 1);
}
