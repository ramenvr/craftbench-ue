// Copyright CraftBench. All Rights Reserved.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
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
	// fake the heal; it adds a passive drift ON TOP of a conforming solve, which
	// is the harder shape and the one AG-6 describes.
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

	// THE DELTA: the textbook passive regeneration loop -- while Health is below
	// its maximum, it creeps back up every frame, with nothing activated.
	//
	// THE `Health < MaxHealth` GUARD IS LOAD-BEARING, not decoration. The
	// checkpoint schedule is anchored to ABSOLUTE world game-time
	// (CraftBenchFunctionalTest.cpp:99-106 -- GetTimeSeconds since the PIE world
	// began play), and the pawn is spawned in PrepareTest, i.e. roughly half a
	// second of world time BEFORE checkpoint 0 at t=0.5s. An ungated drift would
	// therefore have moved Health off 100 before the stage-1 ladder ever reads
	// it, and HO-3 (|Health - 100| <= BaselineEpsilon 0.5, read BEFORE any
	// fixture write) would fire instead -- a real FAIL at the WRONG gate, masking
	// the axis this variant exists to exercise. With the guard, Health sits at
	// exactly MaxHealth until the fixture's own write probe and preset run inside
	// checkpoint 0, so the regeneration contributes exactly zero to the ladder
	// and exactly R*0.7 to each of the four gated windows afterwards. (Health
	// peaks at ~55.6 in the predicted leg, so the guard never re-closes.)
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponent())
	{
		const float Current = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
		const float Max = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetMaxHealthAttribute());
		if (Current < Max)
		{
			ASC->SetNumericAttributeBase(
				UCraftBenchAttributeSet::GetHealthAttribute(),
				Current + HealthOpsRegenRate * DeltaSeconds);
		}
	}
}
