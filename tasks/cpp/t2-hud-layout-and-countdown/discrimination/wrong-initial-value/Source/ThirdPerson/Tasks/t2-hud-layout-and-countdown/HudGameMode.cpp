// GAMING VARIANT (wrong-initial-value) for task t2-hud-layout-and-countdown.
// The HUD reaches the screen at play start with all four named widgets — but
// the readout is overwritten to "0" the moment it appears (a placeholder
// value; the countdown never really starts at 60). Dies at the start-value
// gate via "the countdown does not start at 60".

#include "HudGameMode.h"

#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/TextBlock.h"
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

	// The cheat: the widget's built value is ignored — the readout is
	// stamped "0" immediately (wrong starting value on screen).
	if (Hud->WidgetTree != nullptr)
	{
		if (UTextBlock* Readout = Cast<UTextBlock>(Hud->WidgetTree->FindWidget(TEXT("CountdownText"))))
		{
			Readout->SetText(FText::FromString(TEXT("0")));
		}
	}
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
