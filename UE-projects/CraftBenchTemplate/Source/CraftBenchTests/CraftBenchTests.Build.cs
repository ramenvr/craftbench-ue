// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy. The
// CraftBench eval runner re-applies this directory by hash and rejects any
// modification pre-grade.
//
// Build descriptor for the verifier-only editor module. Type is set to Editor
// so this module is excluded from packaged/shipping builds — the agent's
// runtime cannot link against it, which is part of the anti-gaming surface
// (the agent cannot reach into the test fixture from gameplay code).
// Dependencies cover: actor/world access (Engine, CoreUObject, Core),
// AFunctionalTest base (FunctionalTesting), editor-only PIE helpers (UnrealEd),
// the automation discovery surface (AutomationController), and the
// agent-writable runtime module (CraftBenchTemplate) so map-fixture tests that
// must call a substrate entry point directly — e.g. AModularAttachFunctionalTest
// calling AAttachCoordinator::TryAttachModule — can include its headers. This is
// a normal editor->runtime dependency direction; the runtime module never
// depends back on this editor-only module (anti-gaming: gameplay code cannot
// reach the fixtures).

using UnrealBuildTool;

public class CraftBenchTests : ModuleRules
{
	public CraftBenchTests(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		Type = ModuleType.CPlusPlus;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"FunctionalTesting",
			"UnrealEd",
			"AutomationController",
			"CraftBenchTemplate",
			// GAS probe: the pawn fixture base resolves an ASC via
			// IAbilitySystemInterface and triggers/inspects abilities by tag.
			"GameplayAbilities",
			"GameplayTags",
			"GameplayTasks",
			// Blueprint pawn resolution: scan /Game/Tasks for BP subclasses of the
			// substrate pawn (so a Blueprint/MCP agent's deliverable is gradable).
			"AssetRegistry"
		});

		// CraftBenchTemplate is a flat-layout module (no Public/ folder), so a
		// plain module dependency does NOT put its headers on this module's
		// include path. Add its source dir explicitly so a fixture can
		// #include the agent's substrate headers (e.g. AAttachCoordinator).
		// Done verifier-side (not in the agent-writable game Build.cs) so the
		// agent cannot break the include path by editing their own Build.cs.
		PublicIncludePaths.Add(System.IO.Path.Combine(ModuleDirectory, "..", "CraftBenchTemplate"));

		// Same flat-layout rule applies to THIS module: per-task fixtures under
		// Tasks/<task-id>/ do not see the module root implicitly, so add it —
		// their #include "CraftBenchFunctionalTest.h" (the base class) resolves.
		PrivateIncludePaths.Add(ModuleDirectory);

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// Advisory checkpoint capture (base fixture): reads GUsingNullRHI to
			// keep the screenshot path a no-op under -nullrhi.
			"RHI",
			// AUTHORING-ONLY (Authoring/CraftBenchGraphAuthoring.cpp): the
			// K2 graph-node types (UK2Node_Event, UK2Node_CallFunction,
			// UEdGraphSchema_K2) used to author Blueprint graph content that
			// stock editor Python cannot create. No grader, layer or fixture
			// references that file — it is a task-authoring tool that lives
			// here because this module is verifier-only (CODEOWNERS-gated,
			// graded from git HEAD) and already depends on UnrealEd.
			"BlueprintGraph",
			"KismetCompiler"
		});
	}
}
