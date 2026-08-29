// Copyright CraftBench. All Rights Reserved.
//
// AHudGameMode — reference solution for task t2-hud-layout-and-countdown.
// BeginPlay creates the native HUD widget (UEvalHudWidget — no widget asset
// exists or is needed), puts it on screen, and runs a 1-second world timer
// that counts the readout down.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "HudGameMode.generated.h"

class UEvalHudWidget;

UCLASS()
class THIRDPERSON_API AHudGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AHudGameMode();

	virtual void BeginPlay() override;

private:
	UPROPERTY() TObjectPtr<UEvalHudWidget> Hud;
	FTimerHandle CountdownTimer;
};
