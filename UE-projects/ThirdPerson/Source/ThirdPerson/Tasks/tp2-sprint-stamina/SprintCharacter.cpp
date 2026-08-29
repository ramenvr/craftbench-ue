// Copyright CraftBench. All Rights Reserved.
//
// ASprintCharacter implementation for task tp2-sprint-stamina. The constructor
// stamps the "SprintHero" identity tag. No behavior is provided; the required
// behavior is specified in the task prompt and is the agent's to implement.

#include "SprintCharacter.h"

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

ASprintCharacter::ASprintCharacter()
{
	Tags.Add(FName("SprintHero"));

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
}
