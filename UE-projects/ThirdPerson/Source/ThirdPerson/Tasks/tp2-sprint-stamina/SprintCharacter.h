// Copyright CraftBench. All Rights Reserved.
//
// ASprintCharacter — pre-existing playable character for task tp2-sprint-stamina.
// A concrete, spawnable subclass of the project's third-person character; the
// task map's game mode spawns and possesses it at the PlayerStart. The
// constructor stamps the "SprintHero" identity tag. The required behavior is
// specified in the task prompt and is the agent's to implement. Agents may
// subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "SprintCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ASprintCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ASprintCharacter();
};
