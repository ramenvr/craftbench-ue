// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
// Changes here require maintainer review (.github/CODEOWNERS).
//
// Build descriptor for the verifier-only editor module of the ThirdPerson
// substrate (the stock UE 5.8 Third Person C++ template). Same module NAME as
// CraftBenchTemplate's so the shared tooling (task_layout TESTS_MODULE_REL,
// sandbox deny prefixes, staging) applies unchanged across substrates. Type is
// Editor so the module is excluded from packaged builds — agent runtime code
// cannot link against the fixtures. Dependencies: AFunctionalTest base
// (FunctionalTesting), editor-only PIE helpers (UnrealEd), automation
// discovery (AutomationController), and AssetRegistry so fixtures can resolve
// a Blueprint deliverable by path/scan.

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
			"ThirdPerson",
			"AssetRegistry",
			// GAS probe: the pawn fixture base resolves an ASC via
			// IAbilitySystemInterface and triggers/inspects abilities by tag.
			"GameplayAbilities",
			"GameplayTags",
			"GameplayTasks",
			// Independent slot-state/owner telemetry for the station-handoff
			// verifier. Kept verifier-side so ownership is read from the engine
			// runtime, never from an agent-authored mirror boolean.
			"SmartObjectsModule",
			// Runtime-IK admission: the verifier reads the engine-owned retarget
			// processor and compiled node state directly.
			"IKRig"
		});

		// ThirdPerson is a flat-layout module (no Public/ folder). Its own
		// PublicIncludePaths cover the stock template subfolders, but add the
		// module root explicitly so fixtures can #include the shared CraftBench
		// scaffold headers (CraftBenchCharacter.h etc.) regardless of how UBT
		// resolves the template's Source-relative entries. Done verifier-side
		// (not in the agent-writable game Build.cs) so the agent cannot break
		// the include path by editing their own Build.cs — same rule as the
		// CraftBenchTemplate substrate.
		PublicIncludePaths.Add(System.IO.Path.Combine(ModuleDirectory, "..", "ThirdPerson"));

		// Flat-layout rule: per-task fixtures under Tasks/<task-id>/ do not see
		// the module root implicitly, so add it — their
		// #include "CraftBenchFunctionalTest.h" (the base class) resolves.
		PrivateIncludePaths.Add(ModuleDirectory);

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// The local-player admission harness temporarily provisions the
			// second platform input device through IPlatformInputDeviceMapper.
			// Link its owning module directly instead of relying on Engine's
			// transitive dependency.
			"ApplicationCore",
			// Batch-2 menu fixture uses the concrete EKeys constants directly;
			// link InputCore instead of relying on UMG/CommonUI transitively.
			"InputCore",
			// CommonUI admission fixture: stock activatable-widget stack and
			// local-user focus telemetry. The runtime task surface remains
			// behavior-only and does not expose verifier helpers.
			"CommonUI",
			"CommonInput",
			// Batch-2 crowd-sharing verifier reads and authors the engine-owned
			// setup, manager, state processor, and shared-pose telemetry directly.
			"AnimationSharing",
			// Batch-2 two-hand physics verifier authors and inspects the real
			// Control Rig/RigVM hierarchy, graph, generated VM, and runtime
			// AnimGraph node through their owning modules. Keep these direct
			// instead of relying on the ControlRig plugin's transitive graph.
			"ControlRig",
			"ControlRigDeveloper",
			"RigVM",
			"RigVMDeveloper",
			// Batch-2 PCG verifier owns the protected point source, reads graph
			// output/managed ISM resources, and authors the one editable graph.
			// Keep both runtime and editor owner modules direct rather than
			// relying on plugin/transitive linkage.
			"PCG",
			"PCGEditor",
			// Station-handoff verifier: independent nav-path checks and the
			// verifier-authored reference graph's SimpleMove helper.
			"NavigationSystem",
			"AIModule",
			// Verifier-owned reference/asset authoring helpers build and compile
			// deterministic Blueprint graphs; submission code cannot link this
			// editor-only module.
			"BlueprintGraph",
			"KismetCompiler",
			// Batch-2 patrol/chase authoring builds a real Behavior Tree and
			// Blackboard graph, then inspects the saved editor graph. Keep both
			// concrete editor owner modules direct instead of relying on AIModule
			// or BlueprintGraph transitively.
			"AIGraph",
			"BehaviorTreeEditor",
			// World Partition/Data Layer admission authoring creates runtime Data
			// Layer instances and assigns external actors through the public editor
			// subsystem. Runtime verification remains on Engine-owned APIs.
			"DataLayerEditor",
			// Batch-2 StateTree worker authoring/readback helper compiles the
			// verifier-owned StateTree asset through the public editor module and
			// directly instantiates runtime, AI-schema, compiler-log, and property
			// binding types. Keep their owner modules direct so DLL linkage does not
			// depend on StateTreeEditorModule's transitive dependency set.
			"StateTreeModule",
			"GameplayStateTreeModule",
			"StateTreeDeveloper",
			"PropertyBindingUtils",
			"StateTreeEditorModule",
			// Verifier-only AnimGraph/IK Retargeter authoring and structural
			// readback for the runtime-IK admission probe.
			"IKRigDeveloper",
			"AnimGraph",
			// Direct runtime node reflection/linkage for the CopyPose negative
			// control; do not rely on AnimGraph's transitive dependency.
			"AnimGraphRuntime",
			// Motion-matching admission reads the engine-owned search result and
			// trajectory component, while its verifier-only author/readback helper
			// inspects Pose Search assets through the editor module.
			"PoseSearch",
			"MotionTrajectory",
			"PoseSearchEditor",
			// Motion-intent admission validates the real local-player mapping
			// context and action/component classes through public Enhanced Input
			// APIs, so link the module directly rather than transitively.
			"EnhancedInput",
			// Advisory checkpoint capture (base fixture): reads GUsingNullRHI to
			// keep the screenshot path a no-op under -nullrhi.
			"RHI",
			// Asset-authoring and verifier helpers for three task fixtures
			// (t2-menu-blocks-gameplay..., t3-alert-state-swaps...,
			// t3-each-local-player-owns...) read/write JSON via FJsonSerializer.
			"Json",
			// UMG readback for the HUD fixture (t2-hud-layout-and-countdown):
			// viewport-widget enumeration + WidgetTree/ProgressBar/TextBlock
			// reads. Passive observation only — no widget is ever created here.
			"UMG",
			"Slate",
			"SlateCore"
		});
	}
}
