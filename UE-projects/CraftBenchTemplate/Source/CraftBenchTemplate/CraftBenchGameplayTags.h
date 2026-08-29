// Copyright CraftBench. All Rights Reserved.
//
// Native gameplay tags for the CraftBench pawn/GAS tasks. Declared in the
// runtime module so each tag is registered in the global tag table at module
// load. Consumers call the static accessor (a method — exports cleanly across
// modules, unlike a raw FNativeGameplayTag global), e.g.
// FCraftBenchGameplayTags::AbilityLaunch().

#pragma once

#include "CoreMinimal.h"
#include "GameplayTagContainer.h"

struct CRAFTBENCHTEMPLATE_API FCraftBenchGameplayTags
{
	/** "Ability.Launch" — the gameplay tag an agent's launch ability carries in
	 *  its AbilityTags; activating this tag runs the ability. */
	static FGameplayTag AbilityLaunch();

	/** "Ability.Fly" — the tag a flight ability carries (enter Flying movement mode
	 *  + ascend). gp-flight-mode. */
	static FGameplayTag AbilityFly();

	/** "Ability.Glide" — the tag a glide ability carries (slow descent while falling
	 *  + drain the stamina resource). gp-glide-stamina-cpp. */
	static FGameplayTag AbilityGlide();

	/** "Ability.Poison" — the tag a poison ability carries (periodic Health
	 *  damage-over-time, stacking). gp-poison-dot-stack-cpp. */
	static FGameplayTag AbilityPoison();

	/** "Ability.Melee" — the tag a melee-strike ability carries (short-reach,
	 *  in-front damage with a cooldown). t2-melee-ability-with-cooldown. */
	static FGameplayTag AbilityMelee();
};
