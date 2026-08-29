// Copyright CraftBench. All Rights Reserved.
//
// ALadderGameMode — pre-existing game mode for task t2-ladder-climb-volume.
// The task map's world settings select it; it spawns the playable character
// this task is about at the PlayerStart. No gameplay rules live here and none
// are needed — the task's required behavior belongs on the character.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LadderGameMode.generated.h"

UCLASS()
class THIRDPERSON_API ALadderGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALadderGameMode();
};
