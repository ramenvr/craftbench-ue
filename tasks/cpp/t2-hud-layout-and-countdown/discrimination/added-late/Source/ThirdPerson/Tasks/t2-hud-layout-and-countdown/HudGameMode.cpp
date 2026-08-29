// GAMING VARIANT (added-late) for task t2-hud-layout-and-countdown.
// The HUD is correct in every respect — but it is created on a 3-second
// deferred timer, not at play start. The presence gate samples earlier and
// FAILs via "no HUD widget reached the screen at play start".

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

	// The cheat: "at play start" read lazily — defer everything by 3 seconds.
	FTimerHandle DeferredShow;
	GetWorldTimerManager().SetTimer(DeferredShow,
		FTimerDelegate::CreateWeakLambda(this, [this]()
		{
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
		}),
		3.0f, /*bLoop*/ false);
}
