// Copyright CraftBench. All Rights Reserved.
//
// AFollowHeroCharacter — pre-existing playable character for task
// t2-npc-follows-player. A concrete, spawnable subclass of the project's
// third-person character; the task map's game mode spawns and possesses it at
// the PlayerStart, so it IS the player character in the running level. The
// constructor stamps the "FollowHero" identity tag. It needs no code for this
// task and should not gain any — the task's required behavior belongs on the
// enemy NPC side.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "FollowHeroCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AFollowHeroCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AFollowHeroCharacter();
};
