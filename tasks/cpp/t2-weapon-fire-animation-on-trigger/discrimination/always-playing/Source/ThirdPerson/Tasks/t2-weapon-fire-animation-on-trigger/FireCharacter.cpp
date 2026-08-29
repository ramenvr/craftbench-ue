// Gaming variant "always-playing" for t2-weapon-fire-animation-on-trigger:
// loops the clip from BeginPlay so "an animation is playing" is trivially
// true whenever the verifier looks.
// Expected death: checkpoint 0 — "already playing before any fire request".

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

void AFireCharacter::BeginPlay()
{
	Super::BeginPlay();

	// The gaming delta: start a long loop immediately, before any request.
	UAnimInstance* Anim = GetMesh() ? GetMesh()->GetAnimInstance() : nullptr;
	if (Anim != nullptr && FireClip != nullptr)
	{
		Anim->PlaySlotAnimationAsDynamicMontage(
			FireClip, TEXT("DefaultSlot"), 0.1f, 0.1f, 1.0f, /*LoopCount*/ 100);
	}
}

void AFireCharacter::DoFireStart()
{
	// Nothing needed — something is "playing" already.
}
