// Copyright CraftBench. All Rights Reserved.

#include "CraftBenchGameplayTags.h"

#include "NativeGameplayTags.h"

namespace
{
	// Registered in the global gameplay-tag table at static init.
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Launch, "Ability.Launch");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Fly, "Ability.Fly");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Glide, "Ability.Glide");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Poison, "Ability.Poison");
	UE_DEFINE_GAMEPLAY_TAG(GTag_Ability_Melee, "Ability.Melee");
}

FGameplayTag FCraftBenchGameplayTags::AbilityLaunch()
{
	return GTag_Ability_Launch.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityFly()
{
	return GTag_Ability_Fly.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityGlide()
{
	return GTag_Ability_Glide.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityPoison()
{
	return GTag_Ability_Poison.GetTag();
}

FGameplayTag FCraftBenchGameplayTags::AbilityMelee()
{
	return GTag_Ability_Melee.GetTag();
}
