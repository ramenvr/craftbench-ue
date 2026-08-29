// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchCharacter.h"

#include "AbilitySystemComponent.h"
#include "Abilities/GameplayAbility.h"
#include "CraftBenchAttributeSet.h"

ACraftBenchCharacter::ACraftBenchCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	AbilitySystemComponent = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystemComponent"));
	AbilitySystemComponent->SetIsReplicated(true);
	AbilitySystemComponent->SetReplicationMode(EGameplayEffectReplicationMode::Minimal);

	// 2026-08-05 stage-1 seam: may return NULL — ACraftBenchBareCharacter
	// suppresses this subobject by name (DoNotCreateDefaultSubobject) so
	// health-first tasks start with an ASC and NO health resource; the agent
	// builds it (stage 1). UCraftBenchAttributeSet stays the contract class.
	// MUST be the Optional variant: UE ignores DoNotCreateDefaultSubobject for
	// a required subobject ("Ignored DoNotCreateDefaultSubobject for
	// AttributeSet as it's marked as required" — live-caught 2026-08-05, it
	// silently un-bares the bare lineage and the stage-1 gate reads the wrong,
	// zero-initialized set).
	AttributeSet = CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>(TEXT("AttributeSet"));

	// Identity tag. Agents may subclass or rename this pawn.
	Tags.Add(FName("CraftBenchPawn"));
}

UAbilitySystemComponent* ACraftBenchCharacter::GetAbilitySystemComponent() const
{
	return AbilitySystemComponent;
}

void ACraftBenchCharacter::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	InitAbilityActorInfo();
	GrantDefaultAbilities();
}

void ACraftBenchCharacter::BeginPlay()
{
	Super::BeginPlay();
	InitAbilityActorInfo();
	GrantDefaultAbilities();
}

void ACraftBenchCharacter::InitAbilityActorInfo()
{
	if (AbilitySystemComponent != nullptr)
	{
		// Pawn-owned ASC: owner and avatar are both this pawn.
		AbilitySystemComponent->InitAbilityActorInfo(this, this);
	}
}

void ACraftBenchCharacter::GrantDefaultAbilities()
{
	if (bAbilitiesGranted || AbilitySystemComponent == nullptr)
	{
		return;
	}
	// Only the authority grants abilities (a pawn in a standalone world has
	// authority).
	if (!HasAuthority())
	{
		return;
	}

	for (const TSubclassOf<UGameplayAbility>& AbilityClass : GrantedAbilities)
	{
		if (AbilityClass != nullptr)
		{
			AbilitySystemComponent->GiveAbility(FGameplayAbilitySpec(AbilityClass, 1, INDEX_NONE, this));
		}
	}
	bAbilitiesGranted = true;
}
