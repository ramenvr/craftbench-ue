// Copyright CraftBench. All Rights Reserved.

#include "BridgeSpanActor.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "YardLoadActor.h"

namespace
{
	// The deck: 900 (X) x 700 (Y) x 40 thick, off the 100 cm engine cube.
	const FVector kDeckScale(9.0f, 7.0f, 0.4f);

	// ANY pose to ANY pose inside this. The whole travel a deck can make is
	// FullSagCm + GiveWayDropCm, so the speed is derived from that rather than
	// written down -- re-stamp either number and the deck still arrives in time.
	constexpr double kFullTravelSeconds = 0.35;

	constexpr float kLampIdleIntensity = 6000.0f;
	constexpr float kLampFallenIntensity = 12000.0f;

	const TCHAR* const kDeckMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");

	// REFERENCE SOLUTION constants. Both are slack in the SAFE direction: the yard
	// never sets anything down straddling an edge, and everything it does set down
	// rests on the deck's top face. -40 tolerates the couple of centimetres a crate
	// lags behind a deck that is sagging away underneath it; +260 covers the whole of
	// the gap that opens up while a deck is dropping out from under something, which
	// measures about 155 cm at its widest (a 200 cm drop takes the deck ~0.30 s and a
	// free fall covers ~45 cm in that time).
	constexpr double kFootBelowDeckTopCm = 40.0;
	constexpr double kFootAboveDeckTopCm = 260.0;
}

ABridgeSpanActor::ABridgeSpanActor()
{
	// The deck has to be moved toward its commanded pose every frame. That is the ONLY
	// thing this tick does.
	PrimaryActorTick.bCanEverTick = true;

	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);
	// Movable so the deck under it may be Movable without the editor complaining about
	// a movable child of a static parent. The anchor itself never moves.
	Anchor->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Deck = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Deck"));
	Deck->SetupAttachment(Anchor);
	if (CubeMesh.Succeeded())
	{
		Deck->SetStaticMesh(CubeMesh.Object);
	}
	Deck->SetRelativeScale3D(kDeckScale);
	// MOVABLE, and it matters: a character standing on a movable primitive is carried
	// when that primitive moves. A static deck would slide out from under them.
	Deck->SetMobility(EComponentMobility::Movable);
	Deck->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DeckLook(kDeckMaterial);
	if (DeckLook.Succeeded())
	{
		Deck->SetMaterial(0, DeckLook.Object);
	}

	StrainLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("StrainLamp"));
	// Attached to the DECK, so it rides down with it and a reviewer can see where the
	// deck went. Divided back out of the deck's scale so it sits just above the planks.
	StrainLamp->SetupAttachment(Deck);
	StrainLamp->SetRelativeLocation(FVector(0.0f, 0.0f, 90.0f / kDeckScale.Z));
	StrainLamp->SetIntensity(kLampIdleIntensity);
	StrainLamp->SetAttenuationRadius(1400.0f);
	StrainLamp->SetLightColor(FLinearColor(0.05f, 1.0f, 0.05f));
	StrainLamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("LoadSpan"));
}

void ABridgeSpanActor::BeginPlay()
{
	Super::BeginPlay();

	// Level and whole from the first frame, whatever the editor left behind.
	bGivenWay = false;
	CommandedSagFraction = 0.0f;
	if (Deck != nullptr)
	{
		Deck->SetRelativeLocation(FVector::ZeroVector);
	}
}

void ABridgeSpanActor::SetSagFraction(float NewSagFraction)
{
	CommandedSagFraction = FMath::Clamp(NewSagFraction, 0.0f, 1.0f);
}

void ABridgeSpanActor::GiveWay()
{
	bGivenWay = true;
}

void ABridgeSpanActor::HeaveBackUp()
{
	bGivenWay = false;
}

void ABridgeSpanActor::DriveDeckToCommandedPose(float DeltaSeconds)
{
	if (Deck == nullptr)
	{
		return;
	}

	const double Sag = double(FullSagCm);
	const double Drop = double(GiveWayDropCm);
	const double TargetZ = bGivenWay ? -Drop
									 : -double(CommandedSagFraction) * Sag;

	FVector Rel = Deck->GetRelativeLocation();
	if (!FMath::IsNearlyEqual(Rel.Z, TargetZ, 0.01))
	{
		const double Speed = FMath::Max(Sag + Drop, 1.0) / kFullTravelSeconds;
		const double Step = Speed * double(DeltaSeconds);
		Rel.Z += FMath::Clamp(TargetZ - Rel.Z, -Step, Step);
		// NEVER SWEPT. The deck slides through whatever it passes; it must not shove
		// the character or a crate sideways on its way down, and the engine carries
		// anything standing on it regardless.
		Deck->SetRelativeLocation(Rel);
	}

	if (StrainLamp != nullptr)
	{
		const double Strain = bGivenWay
			? 1.0
			: FMath::Clamp(-Rel.Z / FMath::Max(Sag, 1.0), 0.0, 1.0);
		StrainLamp->SetLightColor(
			FLinearColor(float(Strain), float(1.0 - Strain), 0.05f));
		StrainLamp->SetIntensity(bGivenWay ? kLampFallenIntensity : kLampIdleIntensity);
	}
}

void ABridgeSpanActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	DriveDeckToCommandedPose(DeltaSeconds);

	// ---------------------------------------------------------------------------
	// REFERENCE SOLUTION. This one call, and the two functions below it, are the
	// whole difference between this file and the one the yard ships.
	// ---------------------------------------------------------------------------
	UpdateLoad();
}

bool ABridgeSpanActor::StandsOnDeck(const AActor* Candidate, const FBox& DeckBox)
{
	const UPrimitiveComponent* const Root =
		Candidate != nullptr
			? Cast<UPrimitiveComponent>(Candidate->GetRootComponent())
			: nullptr;
	if (Root == nullptr)
	{
		return false;
	}
	// World-space bounds, re-read this frame. Middle over the deck, feet on it.
	const FBoxSphereBounds B = Root->Bounds;
	const double BaseZ = B.Origin.Z - B.BoxExtent.Z;
	if (B.Origin.X < DeckBox.Min.X || B.Origin.X > DeckBox.Max.X)
	{
		return false;
	}
	if (B.Origin.Y < DeckBox.Min.Y || B.Origin.Y > DeckBox.Max.Y)
	{
		return false;
	}
	return BaseZ >= DeckBox.Max.Z - kFootBelowDeckTopCm
		&& BaseZ <= DeckBox.Max.Z + kFootAboveDeckTopCm;
}

void ABridgeSpanActor::UpdateLoad()
{
	UWorld* const World = GetWorld();
	if (World == nullptr || Deck == nullptr)
	{
		return;
	}

	// WHERE THE DECK IS, this frame. Not where it was built, and not where it was the
	// last time anything arrived on it.
	const FBox DeckBox = Deck->Bounds.GetBox();

	double TotalKg = 0.0;
	int32 StandingOnIt = 0;

	TArray<AActor*> Loads;
	UGameplayStatics::GetAllActorsWithTag(World, FName(TEXT("YardLoad")), Loads);
	for (const AActor* Load : Loads)
	{
		const AYardLoadActor* const Crate = Cast<AYardLoadActor>(Load);
		if (Crate != nullptr && StandsOnDeck(Crate, DeckBox))
		{
			// Read live: the yard stamps fresh weights, it does not keep the old ones.
			TotalKg += double(Crate->WeightKg);
			++StandingOnIt;
		}
	}

	// The character is a load like any other, and the one whose number moves during a
	// round -- so it is read off the character every frame rather than remembered.
	const ACharacter* const Hero = UGameplayStatics::GetPlayerCharacter(World, 0);
	if (Hero != nullptr && StandsOnDeck(Hero, DeckBox))
	{
		if (const UCharacterMovementComponent* const Movement = Hero->GetCharacterMovement())
		{
			TotalKg += double(Movement->Mass);
		}
		++StandingOnIt;
	}

	if (bGivenWay)
	{
		// A fallen deck stays down while ANYTHING is still standing on it -- which is a
		// different question from whether the load has dropped back under the rating.
		// The anvil left behind on a fallen deck weighs less than the span is rated
		// for, and it still keeps the span down.
		if (StandingOnIt == 0)
		{
			HeaveBackUp();
			SetSagFraction(0.0f);
		}
		return;
	}

	const double Rating = FMath::Max(double(RatedLoadKg), 1.0);
	if (TotalKg > Rating)
	{
		GiveWay();
		return;
	}
	SetSagFraction(float(TotalKg / Rating));
}
