// Copyright CraftBench. All Rights Reserved.

#include "ScreenTintActor.h"

#include "Components/PostProcessComponent.h"

AScreenTintActor::AScreenTintActor()
{
	// The screen is ticked every frame. What it should read, and what to set from
	// it, is the thing to work out.
	PrimaryActorTick.bCanEverTick = true;

	Screen = CreateDefaultSubobject<UPostProcessComponent>(TEXT("Screen"));
	SetRootComponent(Screen);
	// Unbound, so the effect applies wherever the character happens to be standing
	// rather than only inside a box somebody has to walk into.
	Screen->bUnbound = true;
	Screen->Priority = 10.0f;

	// Both settings are OVERRIDDEN here, so they are live from the first frame and a
	// submission never has to discover that an override flag exists. What they READ
	// is the whole question.
	Screen->Settings.bOverride_VignetteIntensity = true;
	Screen->Settings.VignetteIntensity = RestVignette;
	Screen->Settings.bOverride_SceneFringeIntensity = true;
	Screen->Settings.SceneFringeIntensity = SuppliedFringe;

	Tags.Add(FName("ScreenTint"));
}

void AScreenTintActor::BeginPlay()
{
	Super::BeginPlay();

	// Start from rest whatever the editor left behind, and put the other setting back
	// to the value it is supplied at.
	SetVignette(RestVignette);
	if (Screen != nullptr)
	{
		Screen->Settings.bOverride_SceneFringeIntensity = true;
		Screen->Settings.SceneFringeIntensity = SuppliedFringe;
	}
}

float AScreenTintActor::CurrentVignette() const
{
	return Screen != nullptr ? Screen->Settings.VignetteIntensity : 0.0f;
}

void AScreenTintActor::SetVignette(float NewVignette)
{
	if (Screen != nullptr)
	{
		Screen->Settings.bOverride_VignetteIntensity = true;
		Screen->Settings.VignetteIntensity = NewVignette;
	}
}
