// Copyright CraftBench. All Rights Reserved.

#include "RaceCollector.h"

#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "InputAction.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	UInputAction* FindInputAction(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<UInputAction> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}
}

ARaceCollector::ARaceCollector()
{
	Tags.Add(FName("RaceCollector"));

	// AThirdPersonCharacter declares these four as EditAnywhere and assigns none of
	// them: the template fills them in on BP_ThirdPersonCharacter's class defaults,
	// so ANY native subclass inherits four null pointers and binds no input at all.
	MoveAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Move"));
	LookAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Look"));
	MouseLookAction = FindInputAction(TEXT("/Game/Input/Actions/IA_MouseLook"));
	JumpAction      = FindInputAction(TEXT("/Game/Input/Actions/IA_Jump"));

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
