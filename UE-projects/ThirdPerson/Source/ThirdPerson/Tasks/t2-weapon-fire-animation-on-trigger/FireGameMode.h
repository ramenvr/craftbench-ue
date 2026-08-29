// Copyright CraftBench. All Rights Reserved.
//
// AFireGameMode — pre-existing game mode for task
// t2-weapon-fire-animation-on-trigger. The task map's world settings select
// it BY NAME (the map is not editable), and it spawns the playable character
// this task is about at the PlayerStart. Do not rename this class — a rename
// silently breaks the map's game-mode override. Repointing DefaultPawnClass
// is allowed but unnecessary; no gameplay rules live here and none are
// needed — the task's required behavior belongs on the character.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "FireGameMode.generated.h"

UCLASS()
class THIRDPERSON_API AFireGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AFireGameMode();
};
