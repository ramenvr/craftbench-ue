// Copyright Epic Games, Inc. All Rights Reserved.
//
// CraftBench: adds the verifier-only editor module (CraftBenchTests) beside
// the template's runtime module. The L1 verifier builds this target
// ("ThirdPersonEditor Win64 Development") to validate a submission compiles.

using UnrealBuildTool;
using System.Collections.Generic;

public class ThirdPersonEditorTarget : TargetRules
{
	public ThirdPersonEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.Add("ThirdPerson");
		ExtraModuleNames.Add("CraftBenchTests");
	}
}
