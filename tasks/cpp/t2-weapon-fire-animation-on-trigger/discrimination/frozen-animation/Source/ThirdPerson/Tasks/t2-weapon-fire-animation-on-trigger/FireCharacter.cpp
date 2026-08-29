// Gaming variant "frozen-animation" for t2-weapon-fire-animation-on-trigger:
// the fire request starts a montage and immediately pauses it — "a montage is
// active" is true, but nothing plays.
// Expected death: checkpoint 2 — "frozen, not playing".

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
	if (Anim->GetCurrentActiveMontage() != nullptr)
	{
		return;
	}
	UAnimMontage* Montage = Anim->PlaySlotAnimationAsDynamicMontage(
		FireClip, TEXT("DefaultSlot"), 0.1f, 0.1f, 1.0f, /*LoopCount*/ 1);
	// The gaming delta: freeze it on the first frame.
	if (Montage != nullptr)
	{
		Anim->Montage_Pause(Montage);
	}
}
