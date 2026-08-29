// Copyright CraftBench. All Rights Reserved.

#include "RaceRoundBase.h"

#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"

ARaceRoundBase::ARaceRoundBase()
{
	// The round is ticked every frame. What it does with those ticks -- what the
	// clock reads, and what the readouts should say -- is the thing to work out.
	PrimaryActorTick.bCanEverTick = true;

	// An UNSCALED root, with the readouts hanging off it, so their offsets are plain
	// centimetres and their glyphs are not stretched by a parent's scale.
	BoardRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoardRoot"));
	SetRootComponent(BoardRoot);

	auto MakeFace = [this](const TCHAR* Name, float Height, float Size,
						   const FColor& Colour, const TCHAR* Placeholder)
	{
		UTextRenderComponent* const Face =
			CreateDefaultSubobject<UTextRenderComponent>(Name);
		Face->SetupAttachment(BoardRoot);
		Face->SetRelativeLocation(FVector(0.0f, 0.0f, Height));
		Face->SetHorizontalAlignment(EHTA_Center);
		Face->SetWorldSize(Size);
		Face->SetTextRenderColor(Colour);
		Face->SetText(FText::FromString(Placeholder));
		return Face;
	};
	// Frozen placeholders on purpose: nothing writes to these yet.
	ScoreText = MakeFace(TEXT("ScoreText"), 420.0f, 110.0f, FColor(255, 232, 120),
						 TEXT("SCORE --"));
	ClockText = MakeFace(TEXT("ClockText"), 300.0f, 130.0f, FColor(160, 235, 255),
						 TEXT("--"));
	StateText = MakeFace(TEXT("StateText"), 200.0f, 80.0f, FColor(235, 235, 235),
						 TEXT("----"));

	Tags.Add(FName("RaceRound"));
}
