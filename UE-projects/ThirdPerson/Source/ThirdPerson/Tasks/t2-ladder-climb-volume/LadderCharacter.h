// Copyright CraftBench. All Rights Reserved.
//
// ALadderCharacter — pre-existing playable character for task
// t2-ladder-climb-volume. A concrete, spawnable subclass of the project's
// third-person character; the task map's game mode spawns and possesses it at
// the PlayerStart. The constructor stamps the "ClimbHero" identity tag. The
// required behavior is specified in the task prompt and is the agent's to
// implement. Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "LadderCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ALadderCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ALadderCharacter();
};
