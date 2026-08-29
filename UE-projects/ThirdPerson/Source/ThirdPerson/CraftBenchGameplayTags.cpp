// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchGameplayTags.h"

#include "NativeGameplayTags.h"

namespace
{
	// Registered in the global gameplay-tag table at static init.
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Glide, "Ability.Glide");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Poison, "Ability.Poison");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Damage, "Ability.Damage");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Heal, "Ability.Heal");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_HealOverTime, "Ability.HealOverTime");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_DoubleJump, "Ability.DoubleJump");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_AoeBurn, "Ability.AoeBurn");
}

FGameplayTag FCraftBenchGameplayTags::AbilityGlide()
{
	return GTag_Ability_Glide.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityPoison()
{
	return GTag_Ability_Poison.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityDamage()
{
	return GTag_Ability_Damage.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityHeal()
{
	return GTag_Ability_Heal.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityHealOverTime()
{
	return GTag_Ability_HealOverTime.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityDoubleJump()
{
	return GTag_Ability_DoubleJump.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityAoeBurn()
{
	return GTag_Ability_AoeBurn.GetTag();
}
