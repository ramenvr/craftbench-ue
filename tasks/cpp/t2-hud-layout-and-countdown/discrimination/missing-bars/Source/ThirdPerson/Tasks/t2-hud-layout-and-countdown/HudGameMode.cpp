// Copyright CraftBench. All Rights Reserved.
//
// AHudGameMode reference implementation for task t2-hud-layout-and-countdown.
// The HUD is the native UEvalHudWidget (its tree is built in
// NativeOnInitialized, i.e. inside CreateWidget); the countdown runs on a
// looping world timer calling the widget's typed step method.

#include "HudGameMode.h"

#include "Blueprint/UserWidget.h"
#include "Engine/World.h"
#include "EvalHudWidget.h"
#include "TimerManager.h"

AHudGameMode::AHudGameMode()
{
}

void AHudGameMode::BeginPlay()
{
	Super::BeginPlay();

	APlayerController* Pc = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (Pc == nullptr)
	{
		return;
	}
	Hud = CreateWidget<UEvalHudWidget>(Pc, UEvalHudWidget::StaticClass());
	if (Hud == nullptr)
	{
		return;
	}
	Hud->AddToViewport(0);

	GetWorldTimerManager().SetTimer(
		CountdownTimer,
		FTimerDelegate::CreateWeakLambda(this, [this]()
		{
			if (Hud != nullptr)
			{
				Hud->DecrementCountdown();
			}
		}),
		1.0f, /*bLoop*/ true);
}
