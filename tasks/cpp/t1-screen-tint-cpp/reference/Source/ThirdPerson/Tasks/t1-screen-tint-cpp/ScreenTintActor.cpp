// Copyright CraftBench. All Rights Reserved.

#include "ScreenTintActor.h"

#include "Components/PostProcessComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

AScreenTintActor::AScreenTintActor()
{
	// Every frame: the effect is supposed to track a speed that changes continuously,
	// and anything coarser shows as a staircase.
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

void AScreenTintActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The character the player controls. Resolved every frame rather than cached at
	// BeginPlay: it is spawned and possessed by the game mode, and a cached pointer
	// would be null on any frame before that has happened.
	const APawn* const Watched = UGameplayStatics::GetPlayerPawn(this, 0);
	const ACharacter* const AsCharacter = Cast<ACharacter>(Watched);
	if (AsCharacter == nullptr || AsCharacter->GetCharacterMovement() == nullptr)
	{
		SetVignette(RestVignette);
		return;
	}

	// BOTH numbers come off the character, every frame. The top speed is not a
	// constant: it is whatever this character can do right now, and dividing by a
	// remembered value is wrong the moment somebody changes it.
	const double TopSpeed = AsCharacter->GetCharacterMovement()->MaxWalkSpeed;
	if (TopSpeed <= KINDA_SMALL_NUMBER)
	{
		SetVignette(RestVignette);
		return;
	}
	// How fast it is ACTUALLY going, not how fast it is allowed to go.
	const double Speed = AsCharacter->GetVelocity().Size2D();
	const double Fraction = FMath::Clamp(Speed / TopSpeed, 0.0, 1.0);

	SetVignette(FMath::Lerp(RestVignette, FullVignette, float(Fraction)));
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
