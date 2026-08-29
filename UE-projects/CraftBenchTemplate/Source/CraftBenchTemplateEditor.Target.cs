// Copyright CraftBench. All Rights Reserved.
//
// Editor target for the CraftBenchTemplate substrate. Standard UE 5.8 Editor
// target boilerplate. Adds BOTH the agent-writable runtime module
// (CraftBenchTemplate) and the verifier-only editor module (CraftBenchTests).
// The L1 verifier builds this target ("CraftBenchTemplateEditor Win64
// Development") to validate the agent's submission compiles.

using UnrealBuildTool;
using System.Collections.Generic;

public class CraftBenchTemplateEditorTarget : TargetRules
{
	public CraftBenchTemplateEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.AddRange(new string[] { "CraftBenchTemplate", "CraftBenchTests" });
	}
}
