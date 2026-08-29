// Copyright CraftBench. All Rights Reserved.
//
// Decides who you are when you press Play in the level for task
// t3-your-last-life-ends-the-run: you arrive as one of the three runners, standing on
// its own marker.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LifeRunGameMode.generated.h"

UCLASS()
class THIRDPERSON_API ALifeRunGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALifeRunGameMode();
};
