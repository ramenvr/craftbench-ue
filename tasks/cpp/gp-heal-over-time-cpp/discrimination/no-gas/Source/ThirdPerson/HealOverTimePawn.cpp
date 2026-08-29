// Copyright CraftBench. All Rights Reserved.
//
// See HealOverTimePawn.h in this directory for the full delta description,
// the pawn-resolution check and the expected named FAIL.

#include "HealOverTimePawn.h"

#include "HealOverTimeAttributeSet.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

// The health cap. 100 is DISCLOSED in the prompt.
// PROPOSED - NOT YET MEASURED.
static constexpr float HealOverTimeMaxHealth = 100.0f;

// Seconds between Tick-driven restore steps, and Health per step. Chosen to
// reproduce the reference's OBSERVABLE timeline (+5 per second) so the only
// difference a reader can find between this pawn and a conforming one is the
// missing ability. Not a calibrated bar -- no gate in the fixture ever reads
// these, because HOT-1 fires before HOT-2.
// PROPOSED - NOT YET MEASURED.
static constexpr float NoGasRestorePeriodSeconds = 1.0f;
static constexpr float NoGasRestorePerPeriod = 5.0f;

AHealOverTimePawn::AHealOverTimePawn(const FObjectInitializer& ObjectInitializer)
	// Unchanged from the reference: the clamping attribute set is still installed,
	// so Health still respects the cap. The clamp is not the axis here.
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UHealOverTimeAttributeSet>(TEXT("AttributeSet")))
{
	// Ticking is stated explicitly rather than inherited by assumption: the whole
	// point of this variant is that the restore runs off the actor tick, so the
	// tick has to be on regardless of what the base class defaults to.
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	if (AttributeSet != nullptr)
	{
		AttributeSet->InitMaxHealth(HealOverTimeMaxHealth);
		AttributeSet->InitHealth(HealOverTimeMaxHealth);
	}

	// THE DELTA: GrantedAbilities stays EMPTY. UHealOverTimeAbility still ships in
	// this overlay and still compiles; it is simply never granted, so
	// NumGrantedAbilitiesWithTag(Ability.HealOverTime) reads 0 and
	// TryActivateAbilitiesByTag has nothing to activate.

	// Visible-character requirement kept intact -- checkpoint 0 must stay green so
	// this variant reaches HOT-1 and dies THERE, not at HOT-7.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

void AHealOverTimePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UAbilitySystemComponent* ASC = GetAbilitySystemComponent();
	if (ASC == nullptr)
	{
		return;
	}

	SecondsSinceRestore += DeltaSeconds;
	if (SecondsSinceRestore < NoGasRestorePeriodSeconds)
	{
		return;
	}
	SecondsSinceRestore -= NoGasRestorePeriodSeconds;

	// Write the BASE value, the same channel a periodic GameplayEffect execution
	// writes into. The clamping attribute set's PreAttributeChange still guards the
	// read-back, so this pawn never pushes Health past MaxHealth either -- it is a
	// behaviorally plausible restore in every respect except that no ability
	// exists.
	const FGameplayAttribute HealthAttribute = UCraftBenchAttributeSet::GetHealthAttribute();
	if (!ASC->HasAttributeSetForAttribute(HealthAttribute))
	{
		return;
	}
	const float Current = ASC->GetNumericAttributeBase(HealthAttribute);
	ASC->SetNumericAttributeBase(HealthAttribute, Current + NoGasRestorePerPeriod);
}
