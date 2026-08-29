// Copyright CraftBench. All Rights Reserved.
//
// AFireCharacter implementation for task t2-weapon-fire-animation-on-trigger.
// The constructor stamps the "FireHero" identity tag and gives the character
// the project's standard animated body (the stock C++ template leaves the mesh
// and animation blueprint to a derived Blueprint asset; this task ships them in
// C++ so the start state is a complete, animatable character). No firing
// behavior is provided; the required behavior is specified in the task prompt
// and is the agent's to implement.

#include "FireCharacter.h"

#include "InputAction.h"
#include "UObject/ConstructorHelpers.h"

#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
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

AFireCharacter::AFireCharacter()
{
	Tags.Add(FName("FireHero"));

	// PLAY-LANE FIX 2026-08-17 (brief: play-lane, four maps).
	// AThirdPersonCharacter declares these four as EditAnywhere and never assigns them: the
	// template fills them in on BP_ThirdPersonCharacter's CLASS DEFAULTS, so any NATIVE
	// subclass inherits four null pointers and SetupPlayerInputComponent calls
	// BindAction(nullptr, ...) four times, binding nothing. Assigned here rather than in
	// Epic's shared base, which would re-sha the whole project tree and invalidate every
	// task's certificate at once.
	MoveAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump"));

	// The project's standard mannequin body + its animation blueprint, wired at
	// construction so every instance starts with an animated body.
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
