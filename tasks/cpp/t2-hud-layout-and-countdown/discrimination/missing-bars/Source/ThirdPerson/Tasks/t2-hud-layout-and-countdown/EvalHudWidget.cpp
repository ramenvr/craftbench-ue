// GAMING VARIANT (missing-bars) for task t2-hud-layout-and-countdown.
// The GameMode wiring is byte-identical to the reference; the WIDGET is the
// delta — its tree ships HealthBar, StaminaBar and CountdownText but NO
// ManaBar. Dies at the cp0 name gate via "missing a widget named".

#include "EvalHudWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ProgressBar.h"
#include "Components/TextBlock.h"

void UEvalHudWidget::NativeOnInitialized()
{
	Super::NativeOnInitialized();

	if (WidgetTree == nullptr)
	{
		return;
	}

	UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(
		UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
	WidgetTree->RootWidget = Canvas;

	// The cheat: two of the three required bars — ManaBar never built.
	const TCHAR* BarNames[] = { TEXT("HealthBar"), TEXT("StaminaBar") };
	float Y = 40.f;
	for (const TCHAR* BarName : BarNames)
	{
		UProgressBar* Bar = WidgetTree->ConstructWidget<UProgressBar>(
			UProgressBar::StaticClass(), BarName);
		Bar->SetPercent(1.0f);
		if (UCanvasPanelSlot* PanelSlot = Canvas->AddChildToCanvas(Bar))
		{
			PanelSlot->SetPosition(FVector2D(1400.f, Y));
			PanelSlot->SetSize(FVector2D(320.f, 24.f));
		}
		Y += 40.f;
	}

	UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(
		UTextBlock::StaticClass(), TEXT("CountdownText"));
	Text->SetText(FText::FromString(TEXT("60")));
	if (UCanvasPanelSlot* PanelSlot = Canvas->AddChildToCanvas(Text))
	{
		PanelSlot->SetPosition(FVector2D(60.f, 40.f));
		PanelSlot->SetSize(FVector2D(200.f, 48.f));
	}
	CountdownWidget = Text;
}

void UEvalHudWidget::DecrementCountdown()
{
	if (CountdownWidget == nullptr)
	{
		return;
	}
	const int32 Current = FCString::Atoi(*CountdownWidget->GetText().ToString().TrimStartAndEnd());
	const int32 Next = FMath::Max(0, Current - 1);
	CountdownWidget->SetText(FText::FromString(FString::FromInt(Next)));
}
