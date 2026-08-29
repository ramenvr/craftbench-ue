// Copyright CraftBench. All Rights Reserved.
//
// UEvalHudWidget — reference solution HUD for task t2-hud-layout-and-countdown.
// A NATIVE UUserWidget: the whole tree (canvas root, the three named fill
// bars, the named countdown text block) is built programmatically in
// NativeOnInitialized — no widget asset exists or is needed. The fixture
// grades what is ON SCREEN by widget NAME, so a designer-authored widget
// asset and this native class grade identically; native is the reference's
// shape because headless WBP-asset authoring has no stock route on UE 5.8
// (see the task notes archaeology record).

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "EvalHudWidget.generated.h"

class UTextBlock;

UCLASS()
class THIRDPERSON_API UEvalHudWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** One countdown step: 60 -> 59 -> ... floored at 0. */
	void DecrementCountdown();

protected:
	/** Builds the tree. Fires at the end of UUserWidget::Initialize() —
	 *  inside CreateWidget, where the transient WidgetTree for a native
	 *  widget already exists — so the named tree is complete before
	 *  AddToViewport and long before any verifier observation. */
	virtual void NativeOnInitialized() override;

private:
	UPROPERTY() TObjectPtr<UTextBlock> CountdownWidget;
};
