// Copyright CraftBench. All Rights Reserved.
//
// Build descriptor for the agent-writable runtime module. PublicDependencyModuleNames
// is fixed by tasks/t0-sanity-log-on-beginplay.md under "Workspace state pre-task":
// Core, CoreUObject, Engine, InputCore, FunctionalTesting. The agent is permitted to
// edit this file but the t0 task does not require any change here.

using UnrealBuildTool;

public class CraftBenchTemplate : ModuleRules
{
	public CraftBenchTemplate(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"FunctionalTesting",
			// Catalog readers query FAssetData metadata at runtime and must link
			// AssetRegistry directly; package loading is forbidden by the task.
			"AssetRegistry",
			// GAS modules — required by the (untracked) gold-#19 source files
			// CraftBenchCharacter / CraftBenchAttributeSet / CraftBenchLaunchAbility
			// that live in this shared substrate. These deps were uncommitted working
			// state; restored after a blanket `git checkout` inadvertently reverted them.
			"GameplayAbilities",
			"GameplayTags",
			"GameplayTasks"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		// Flat-layout module (no Public/ folder): per-task sources under
		// Tasks/<task-id>/ do not see the module root implicitly. Add it so
		// task code can #include shared root headers (CraftBenchCharacter.h
		// etc.) without ../.. relative paths.
		PrivateIncludePaths.Add(ModuleDirectory);
	}
}
