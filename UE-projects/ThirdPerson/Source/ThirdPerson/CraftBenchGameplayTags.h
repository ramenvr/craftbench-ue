// Copyright CraftBench. All Rights Reserved.
//
// Native gameplay tags for the CraftBench pawn/GAS tasks on the ThirdPerson
// substrate. Declared in the runtime module so each tag is registered in the
// global tag table at module load. Consumers call the static accessor (a
// method — exports cleanly across modules, unlike a raw FNativeGameplayTag
// global), e.g. FCraftBenchGameplayTags::AbilityGlide().
//
// Ported from the CraftBenchTemplate substrate 2026-08-05. Only the tags a
// ThirdPerson task actually wires are registered here — add the sibling
// ability tags as their tasks migrate, mirroring the template's file.

#pragma once

#include "CoreMinimal.h"
#include "GameplayTagContainer.h"

struct THIRDPERSON_API FCraftBenchGameplayTags
{
	/** "Ability.Glide" — the tag a glide ability carries (slow descent while falling
	 *  + drain the stamina resource). gp-glide-stamina-bp. */
	static FGameplayTag AbilityGlide();

	/** "Ability.Poison" — the tag a poison ability carries (periodic Health
	 *  damage-over-time, stacking). gp-poison-dot-stack-bp. */
	static FGameplayTag AbilityPoison();

	/** "Ability.Damage" — the tag a one-shot damage ability carries (a single
	 *  fixed decrease of Health per activation). gp-health-attribute-ops-{cpp,bp};
	 *  it is this family's PreferredAbilityTag. */
	static FGameplayTag AbilityDamage();

	/** "Ability.Heal" — the tag a one-shot heal ability carries (a single fixed
	 *  increase of Health per activation, symmetric with Ability.Damage).
	 *  gp-health-attribute-ops-{cpp,bp}. */
	static FGameplayTag AbilityHeal();

	/** "Ability.HealOverTime" — the tag a restorative heal-over-time ability
	 *  carries (Health raised repeatedly, about once per second, for roughly five
	 *  seconds, then stopping; clamped at MaxHealth in BOTH the current and the
	 *  base value). gp-heal-over-time-{cpp,bp}; it is that family's
	 *  PreferredAbilityTag.
	 *
	 *  DISTINCT from Ability.Heal on purpose (PIN.md D5): PreferredAbilityTag()
	 *  is what ResolveAgentPawnClass uses to pick the graded pawn, so it must stay
	 *  unique per GAS family or gp-health-attribute-ops' committed pawn and this
	 *  family's committed pawn can win each other's resolution by enumeration
	 *  order. */
	static FGameplayTag AbilityHealOverTime();

	/** "Ability.DoubleJump" - the tag a second-jump ability carries (activated
	 *  while the character is already falling, it reverses the descent with a
	 *  real upward impulse and debits a fixed one-shot Power cost).
	 *  gp-double-jump-stamina-{cpp,bp}; it is that family's PreferredAbilityTag.
	 *
	 *  DISTINCT from every other ability tag for the same reason
	 *  Ability.HealOverTime is (PIN.md D5): PreferredAbilityTag() is what
	 *  ResolveAgentPawnClass uses to pick the graded pawn, so a family that
	 *  reused an existing tag could have another task's committed pawn win its
	 *  resolution by enumeration order. */
	static FGameplayTag AbilityDoubleJump();

	/** "Ability.AoeBurn" - the tag a burning-area ability carries (activated,
	 *  it creates a damaging area at the character's location: characters
	 *  inside lose Health periodically for the area's duration; characters
	 *  outside are untouched). gp-dot-aoe-burn-{cpp,bp}; that family's
	 *  PreferredAbilityTag.
	 *
	 *  DISTINCT from every other ability tag for the same reason the two
	 *  accessors above are (PIN.md D5): PreferredAbilityTag() drives
	 *  ResolveAgentPawnClass, so tag reuse would let another family's
	 *  committed pawn win this family's resolution by enumeration order. */
	static FGameplayTag AbilityAoeBurn();
};
