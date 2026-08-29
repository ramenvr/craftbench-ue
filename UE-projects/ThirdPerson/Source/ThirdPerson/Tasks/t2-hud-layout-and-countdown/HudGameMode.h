// Copyright CraftBench. All Rights Reserved.
//
// AHudGameMode — pre-existing game mode for task t2-hud-layout-and-countdown.
// The task map's world settings select it. It ships EMPTY: putting the HUD on
// screen at play start is the task, and where that wiring lives (this game
// mode, a controller, or the widget itself) is the implementer's choice.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "HudGameMode.generated.h"

UCLASS()
class THIRDPERSON_API AHudGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AHudGameMode();
};
