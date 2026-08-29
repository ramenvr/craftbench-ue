// Copyright CraftBench. All Rights Reserved.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	// ACharacter already enables tick; stated explicitly so the delta is legible.
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	// STAGE 1 -- the reference verbatim.
	HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 -- the reference verbatim: both operations are still real,
	// tag-activated, instant, fixed-magnitude abilities. This variant does not
	// fake either operation; it adds a passive drift ON TOP of a conforming solve,
	// which is the harder shape and the one AG-6 describes.
	GrantedAbilities.Add(UDamageAbility::StaticClass());
	GrantedAbilities.Add(UHealAbility::StaticClass());

	// Visible-character requirement (HO-5) -- unchanged from the reference.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

void AHealthOpsPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// THE DELTA: out-of-combat health regeneration. Health creeps back up, but
	// only once the character has gone HealthOpsRegenDelay seconds without taking
	// damage -- the shape shipped games use, and the shape whose timing (not
	// whose magnitude) is what lets it isolate HO-11. The full derivation is in
	// the header; the two guards below are the load-bearing parts.

	UAbilitySystemComponent* ASC = GetAbilitySystemComponent();
	const UWorld* World = GetWorld();
	if (ASC == nullptr || World == nullptr)
	{
		return;
	}

	const float Current = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
	const float Max = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetMaxHealthAttribute());
	const double Now = World->GetTimeSeconds();

	// --- damage detection ---------------------------------------------------
	// "Took damage" = Health went DOWN since the previous tick. Regeneration only
	// ever raises Health, so the loop below can never restart its own timer.
	//
	// The fixture's own writes inside checkpoint 0 (the 37 write probe, then the
	// preset to 60) net out as a decrease from 100, so they stamp LastDamageTime
	// at ~0.5 s -- the same instant the first real damage lands. Harmless: cp0 is
	// where the first damage is triggered anyway, and the arithmetic in the header
	// is solved against the LAST damage at cp1 (t=1.2), not the first.
	if (PreviousHealth >= 0.0f && Current < PreviousHealth - HealthOpsDamageDetectEpsilon)
	{
		LastDamageTime = Now;
	}
	PreviousHealth = Current;

	// --- guard 1: the health cap --------------------------------------------
	// `Current < Max` IS LOAD-BEARING, not decoration -- the same finding
	// ../MATRIX.md records for `regen/`. The checkpoint schedule is anchored to
	// ABSOLUTE world game-time (CraftBenchFunctionalTest.cpp:99-106), and the pawn
	// is spawned in PrepareTest, roughly half a second of world time BEFORE
	// checkpoint 0 at t=0.5 s. Nothing has damaged the character yet at that
	// point, so the out-of-combat condition below is ALREADY true and this guard
	// is the only thing holding Health at exactly 100 for the stage-1 ladder.
	// Without it the drift would move Health off 100 before HO-3 reads it and the
	// variant would die at HO-3 -- a real FAIL at the wrong gate, masking the one
	// axis it exists to exercise.
	//
	// It never re-closes during the leg: Health peaks at a predicted 51.8, far
	// below the cap.
	if (!(Current < Max))
	{
		return;
	}

	// --- guard 2: out of combat ---------------------------------------------
	if (Now - LastDamageTime < HealthOpsRegenDelay)
	{
		return;
	}

	ASC->SetNumericAttributeBase(
		UCraftBenchAttributeSet::GetHealthAttribute(),
		FMath::Min(Current + HealthOpsRegenRate * DeltaSeconds, Max));
}
