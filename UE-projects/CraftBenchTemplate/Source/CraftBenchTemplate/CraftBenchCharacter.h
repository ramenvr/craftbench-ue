// Copyright CraftBench. All Rights Reserved.
//
// ACraftBenchCharacter — the generalizable substrate pawn for CraftBench motion
// and GAS tasks. Owns the un-conceptual GAS plumbing the agent shouldn't have to
// re-derive headless:
//   - a pawn-owned UAbilitySystemComponent (avatar = owner = this pawn; NOT a
//     PlayerState-owned ASC — minimal model, right for atomic single-player PIE);
//   - InitAbilityActorInfo in both BeginPlay and PossessedBy (idempotent);
//   - a minimal UCraftBenchAttributeSet;
//   - an EditAnywhere GrantedAbilities array auto-granted on the authority — the
//     agent fills it (C++ subclass ctor OR Blueprint defaults) and that is the
//     ONLY GAS wiring the agent must do besides authoring the ability;
//   - the "CraftBenchPawn" identity tag.
//
// The base ships GrantedAbilities EMPTY — an unmodified pawn grants nothing, so a
// tag-trigger finds no ability and the GAS task fails (anti-gaming).
//
// 2026-08-05 health-first redefinition (gp-poison-dot-stack-cpp / -bp): THIS class
// deliberately KEEPS pre-constructing the attribute set — ripping it out would
// break every task whose fixture presets/reads attributes on a generic-scaffold
// pawn (gp-glide-stamina-cpp's fixture writes+reads Power on this very set, and its
// committed references subclass this class). The stage-1 ("the agent BUILDS the
// health system") seam is the ABSTRACT sibling ACraftBenchBareCharacter
// (CraftBenchBareCharacter.h), which suppresses the subobject; health-first
// tasks derive from it. UCraftBenchAttributeSet remains the exported contract
// class either way.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AbilitySystemInterface.h"
#include "CraftBenchCharacter.generated.h"

class UAbilitySystemComponent;
class UCraftBenchAttributeSet;
class UGameplayAbility;

UCLASS()
class CRAFTBENCHTEMPLATE_API ACraftBenchCharacter : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()

public:
	/** FObjectInitializer pass-through so a subclass can suppress the pre-built
	 *  attribute set via DoNotCreateDefaultSubobject (the stage-1 seam — see
	 *  ACraftBenchBareCharacter). */
	ACraftBenchCharacter(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());

	//~ IAbilitySystemInterface.
	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;

	/** Abilities auto-granted on the authority at BeginPlay/PossessedBy. The agent
	 *  populates this (C++ ctor or BP class defaults) with the ability they author. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CraftBench|GAS")
	TArray<TSubclassOf<UGameplayAbility>> GrantedAbilities;

protected:
	virtual void PossessedBy(AController* NewController) override;
	virtual void BeginPlay() override;

	void InitAbilityActorInfo();
	void GrantDefaultAbilities();

	UPROPERTY(VisibleAnywhere, Category = "CraftBench|GAS")
	TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;

	/** Pre-built minimal attribute set. NULL on the ACraftBenchBareCharacter
	 *  lineage (subobject suppressed — the stage-1 seam), so null-check it. */
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> AttributeSet;

private:
	bool bAbilitiesGranted = false;
};
