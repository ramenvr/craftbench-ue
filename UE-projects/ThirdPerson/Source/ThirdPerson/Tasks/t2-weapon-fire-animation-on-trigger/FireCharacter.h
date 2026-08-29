// Copyright CraftBench. All Rights Reserved.
//
// AFireCharacter — pre-existing playable character for task
// t2-weapon-fire-animation-on-trigger. A concrete, spawnable subclass of the
// project's third-person character; the task map's game mode spawns and
// possesses it at the PlayerStart. The constructor stamps the "FireHero"
// identity tag and wires the project's standard animated body (skeletal mesh +
// animation blueprint) so the character has a body that can play animations —
// that wiring is start state, not behavior. The required behavior is specified
// in the task prompt and is the agent's to implement — extend/edit this class
// (or its writable parent) in place; do not rename it: the committed map's
// game mode spawns the pawn class it points at, so only what that class
// carries reaches the grade.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "FireCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AFireCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AFireCharacter();
};
