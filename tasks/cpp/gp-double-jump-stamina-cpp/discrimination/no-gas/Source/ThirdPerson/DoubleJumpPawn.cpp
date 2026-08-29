// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-gas/` -- see DoubleJumpPawn.h for the full delta,
// the attribution argument and the pawn-resolution check.
// STATUS: UNVALIDATED / NOT YET RUN.

#include "DoubleJumpPawn.h"

#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

// Unchanged from the reference. NOT disclosed by the prompt and NOT a gate
// constant -- the verifier presets Power itself before each leg.
// PROPOSED - NOT YET MEASURED.
static constexpr float DoubleJumpInitialPower = 100.0f;

ADoubleJumpPawn::ADoubleJumpPawn()
{
	// THE DELTA lives here and in Tick(): the reference's
	//     GrantedAbilities.Add(UDoubleJumpAbility::StaticClass());
	// is REMOVED, so the pawn grants nothing and no tag can reach an ability.
	// DoubleJumpAbility.{h,cpp} still ship in this overlay byte-identical to the
	// reference -- they are compiled and simply never granted, which is exactly
	// AG-1's shape (the capability exists, the contract does not).

	// Tick must be on for the movement-component implementation below. ACharacter
	// enables it by default in the templates, but stating it here makes the
	// variant independent of that default.
	PrimaryActorTick.bCanEverTick = true;

	if (AttributeSet != nullptr)
	{
		AttributeSet->InitPower(DoubleJumpInitialPower);
	}

	// Mannequin unchanged -- DJ-7 must PASS on this pawn so the row is
	// attributable to DJ-1 and not to the checkpoint-0 visibility gate.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

// The second jump, implemented where AG-1 says a gaming solve puts it: in the
// movement path, driven by the pawn's own Tick, reachable by no tag and by no
// activation. Behaviourally this is the reference: one debit of exactly 20, one
// real velocity reversal, once per airborne period, refused below the cost.
void ADoubleJumpPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UCharacterMovementComponent* CMC = GetCharacterMovement();
	if (CMC == nullptr || bAutoJumpUsed)
	{
		return;
	}

	if (!CMC->IsFalling())
	{
		AirborneSeconds = 0.0f;
		return;
	}

	AirborneSeconds += DeltaSeconds;
	if (AirborneSeconds < AutoJumpDelay)
	{
		return;
	}

	// The cost is still a GATE, not a subtraction -- below it, nothing happens at
	// all. Kept faithful to the reference so that if this row ever DID reach the
	// Power gates it would pass them, and the only thing DJ-1 can be reporting is
	// the missing activatable contract.
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponent())
	{
		const float CurrentPower =
			ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
		if (CurrentPower < PowerCost)
		{
			return;
		}
		ASC->SetNumericAttributeBase(
			UCraftBenchAttributeSet::GetPowerAttribute(),
			FMath::Max(0.0f, CurrentPower - PowerCost));
	}

	CMC->Velocity.Z = JumpImpulseZ;
	bAutoJumpUsed = true;
}
