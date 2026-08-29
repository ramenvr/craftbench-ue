// Copyright CraftBench. All Rights Reserved.
//
// AFollowGameMode — pre-existing game mode for task t2-npc-follows-player.
// The task map's world settings select it; it spawns and possesses the
// playable character at the PlayerStart so a real player pawn exists for the
// enemy NPC to find. No gameplay rules live here and none are needed — the
// task's required behavior belongs on the enemy NPC side.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "FollowGameMode.generated.h"

UCLASS()
class THIRDPERSON_API AFollowGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AFollowGameMode();
};
