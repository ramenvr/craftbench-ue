// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t2-race-clock.

#include "RaceRoundBase.h"

#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "RaceReplayPadActor.h"

ARaceRoundBase::ARaceRoundBase()
{
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
	ScoreText = MakeFace(TEXT("ScoreText"), 420.0f, 110.0f, FColor(255, 232, 120),
						 TEXT("SCORE 0"));
	ClockText = MakeFace(TEXT("ClockText"), 300.0f, 130.0f, FColor(160, 235, 255),
						 TEXT("10"));
	StateText = MakeFace(TEXT("StateText"), 200.0f, 80.0f, FColor(235, 235, 235),
						 TEXT("InProgress"));

	Tags.Add(FName("RaceRound"));
}

void ARaceRoundBase::BeginPlay()
{
	Super::BeginPlay();

	// The round length is whatever the board shipped showing: the arena states it,
	// and reading it back beats writing the same number down in two places.
	RoundLengthSeconds = TimeRemaining;

	TArray<AActor*> Pads;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("RaceReplayPad")),
		Pads);
	if (Pads.Num() > 0)
	{
		ReplayPad = Pads[0];
	}

	StartFreshRound();
}

void ARaceRoundBase::AddPoints(int32 Points)
{
	// After zero the score is final: a coin contacted later adds nothing, ever.
	if (!IsRoundRunning())
	{
		return;
	}
	Score += Points;
	RefreshFaces();
}

void ARaceRoundBase::StartFreshRound()
{
	Score = 0;
	TimeRemaining = RoundLengthSeconds;
	RoundState = TEXT("InProgress");
	RoundStartedAt = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	// A fresh round has to be asked for again: whoever started this one has to step
	// off the pad before it will listen a second time.
	bReplayArmed = false;
	RefreshFaces();
}

void ARaceRoundBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const UWorld* const World = GetWorld();
	if (World == nullptr)
	{
		return;
	}

	// MEASURED FROM WHEN THIS ROUND STARTED, not from world time. A clock derived
	// from world time can only count down once, so no wiring of the pad could ever
	// produce a second round.
	const double Left = double(RoundLengthSeconds)
		- (World->GetTimeSeconds() - RoundStartedAt);
	TimeRemaining = static_cast<float>(FMath::Max(0.0, Left));
	RoundState = (Left > 0.0) ? TEXT("InProgress") : TEXT("TimedOut");

	// THE READOUTS FOLLOW THE PLAYER.
	if (const APawn* const Watcher = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		FaceTheReadoutsAt(Watcher->GetActorLocation());
	}

	// THE REPLAY. Once the round has ended, STEPPING onto the pad starts another.
	if (!IsRoundRunning())
	{
		const ARaceReplayPadActor* const Pad =
			Cast<ARaceReplayPadActor>(ReplayPad.Get());
		const bool bPressed = Pad != nullptr && Pad->IsPressed();
		if (!bPressed)
		{
			bReplayArmed = true;
		}
		else if (bReplayArmed)
		{
			StartFreshRound();
			return;
		}
	}

	RefreshFaces();
}

void ARaceRoundBase::FaceTheReadoutsAt(const FVector& Watcher)
{
	// About the vertical only: tipping a readout up or down at somebody standing
	// close would make it unreadable from anywhere else, and the arena is flat.
	UTextRenderComponent* const Faces[] = {ScoreText, ClockText, StateText};
	for (UTextRenderComponent* const Face : Faces)
	{
		if (Face == nullptr)
		{
			continue;
		}
		const FVector ToWatcher =
			(Watcher - Face->GetComponentLocation()).GetSafeNormal2D();
		if (!ToWatcher.IsNearlyZero())
		{
			Face->SetWorldRotation(ToWatcher.Rotation());
		}
	}
}

void ARaceRoundBase::RefreshFaces()
{
	if (ScoreText != nullptr)
	{
		ScoreText->SetText(FText::FromString(
			FString::Printf(TEXT("SCORE %d"), Score)));
	}
	if (ClockText != nullptr)
	{
		ClockText->SetText(FText::FromString(
			FString::Printf(TEXT("%d"), FMath::CeilToInt(TimeRemaining))));
	}
	if (StateText != nullptr)
	{
		StateText->SetText(FText::FromString(RoundState));
	}
}
