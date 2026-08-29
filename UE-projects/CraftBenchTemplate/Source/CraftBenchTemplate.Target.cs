// Copyright CraftBench. All Rights Reserved.
//
// Game target for the CraftBenchTemplate substrate. Standard UE 5.8 Game target
// boilerplate produced by the third-person C++ project template, narrowed to the
// minimal module set this substrate ships. Includes ONLY the agent-writable
// runtime module (CraftBenchTemplate); the verifier-only CraftBenchTests module
// is editor-only and is added in CraftBenchTemplateEditor.Target.cs instead.

using UnrealBuildTool;
using System.Collections.Generic;

public class CraftBenchTemplateTarget : TargetRules
{
	public CraftBenchTemplateTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.AddRange(new string[] { "CraftBenchTemplate" });
	}
}
