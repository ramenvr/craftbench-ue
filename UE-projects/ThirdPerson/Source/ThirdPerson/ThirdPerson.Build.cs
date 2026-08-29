// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class ThirdPerson : ModuleRules
{
	public ThirdPerson(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			// Batch-2 catalog-reader port: the public runtime candidate performs
			// metadata-only FARFilter queries without relying on verifier linkage.
			"AssetRegistry",
			// Batch-2 Animation Sharing task: the public runtime state processor
			// derives directly from UAnimationSharingStateProcessor.
			"AnimationSharing",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate",
			// Batch-2 menu/input task: the agent-visible runtime widget derives
			// directly from UCommonActivatableWidget. Keep this a direct public
			// dependency instead of relying on verifier-only CommonUI linkage.
			"CommonUI",
			// GAS modules — required by the shared CraftBench GAS scaffold
			// (CraftBenchCharacter / CraftBenchAttributeSet /
			// CraftBenchGameplayTags), ported 2026-08-05 for the ThirdPerson
			// gameplay-task lane (gp-glide-stamina-bp first).
			"GameplayAbilities",
			"GameplayTags",
			"GameplayTasks",
			// Smart Objects substrate admission for the station-handoff lane.
			// The plugin is enabled in ThirdPerson.uproject; task runtime code
			// owns one real single-slot USmartObjectComponent and Blueprint
			// workers exercise the engine claim/occupy/free lifecycle.
			"SmartObjectsModule"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// Cross-world epoch task: protected runtime fixture actors derive from
			// AFunctionalTest so the retained maps remain discoverable while their
			// verdict survives travel in a GameInstance subsystem.
			"FunctionalTesting",
			// Smart Object definitions own World Condition query state. The
			// station-handoff substrate initializes its actor-owned definition
			// explicitly so its empty preconditions remain warning-free.
			"WorldConditions"
		});

		// CraftBench per-task folder convention: scaffold pairs live under
		// Tasks/<task-id>/ — add the module root so their headers resolve by
		// name from subfolders (same rule as both CraftBenchTemplate modules).
		PrivateIncludePaths.Add(ModuleDirectory);

		PublicIncludePaths.AddRange(new string[] {
			"ThirdPerson",
			"ThirdPerson/Variant_Platforming",
			"ThirdPerson/Variant_Platforming/Animation",
			"ThirdPerson/Variant_Combat",
			"ThirdPerson/Variant_Combat/AI",
			"ThirdPerson/Variant_Combat/Animation",
			"ThirdPerson/Variant_Combat/Gameplay",
			"ThirdPerson/Variant_Combat/Interfaces",
			"ThirdPerson/Variant_Combat/UI",
			"ThirdPerson/Variant_SideScrolling",
			"ThirdPerson/Variant_SideScrolling/AI",
			"ThirdPerson/Variant_SideScrolling/Gameplay",
			"ThirdPerson/Variant_SideScrolling/Interfaces",
			"ThirdPerson/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
