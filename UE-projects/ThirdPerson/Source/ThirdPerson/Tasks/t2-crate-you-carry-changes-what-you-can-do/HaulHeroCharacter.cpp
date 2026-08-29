// Copyright CraftBench. All Rights Reserved.

#include "HaulHeroCharacter.h"

#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "InputAction.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** Loads one of the template's Enhanced Input actions, or leaves it null. */
	UInputAction* FindInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}
}

AHaulHeroCharacter::AHaulHeroCharacter()
{
	Tags.Add(FName(TEXT("HaulHero")));

	// AThirdPersonCharacter declares these four as EditAnywhere and assigns none:
	// the template fills them in on BP_ThirdPersonCharacter's class defaults, so
	// ANY native subclass inherits four null pointers and SetupPlayerInputComponent
	// binds nothing at all. Wired here so the yard can be walked around by hand --
	// the graded drive uses AddMovementInput and would pass either way, which is
	// exactly how an unplayable level ships unnoticed.
	MoveAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump"));

	// The project's standard body and its animation blueprint. A body-less pawn
	// satisfies every measurement and is invisible to anyone watching, which is
	// why this is shipped rather than left to the agent.
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
}
