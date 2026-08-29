// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ============================ AUTHORING-ONLY =============================
// This file is a TASK-AUTHORING TOOL, not a grader. Nothing here is ever
// referenced by any verifier layer, any AFunctionalTest fixture, or any
// introspect script — it exists so a task author can create Blueprint graph
// content that stock editor Python cannot (the graph containers are bare
// reflection-denied UPROPERTYs: Blueprint.h:540-555 /
// PropertyAccessUtil.cpp:425-433, the same engine fact that killed
// t2-beacon-igniter-blueprints' live oracle).
//
// It lives in CraftBenchTests deliberately: that module is the verifier-only
// EDITOR module — review-gated via .github/CODEOWNERS and graded from git
// HEAD, so an agent cannot reach it — and it already carries the UnrealEd
// dependency this needs. Placing an authoring helper in the agent-writable
// runtime module would both fail to link (UnrealEd is editor-only) and hand
// agents an editable surface.
//
// GRADERS MUST NEVER CALL THIS. If a future grader needs to know something
// about a Blueprint graph, it must probe the shipped asset, not re-run the
// authoring path — otherwise the verifier would be grading its own writes.
// =========================================================================
//
// Usage (editor Python, headless boot on the substrate project):
//
//     import unreal
//     bp  = unreal.EditorAssetLibrary.load_asset("/Game/Tasks/<id>/BP_Foo")
//     cls = unreal.load_class(None, "/Script/CraftBenchTemplate.MyLibrary")
//     ok  = unreal.CraftBenchGraphAuthoring.add_begin_play_call_node(
//               bp, cls, "MyStaticFunction")
//
// The helper is FAIL-LOUD: every missing graph / pin / class / function
// returns false (never true) with a `CRAFTBENCH-AUTHORING` log line naming
// the exact precondition that failed, so a calling script can abort by name
// instead of shipping doubtful bytes.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CraftBenchGraphAuthoring.generated.h"

class UBlueprint;

UCLASS()
class UCraftBenchGraphAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Adds ONE static-function call node off the Blueprint's Event BeginPlay,
	 * wires the exec pin, compiles the Blueprint and saves its package.
	 *
	 * The call node's non-exec input pins are left at their literal defaults —
	 * this authors "call the function with a literal argument", which is the
	 * minimal shape that puts the callee's name into the caller's serialized
	 * import table.
	 *
	 * If the event graph has no Event BeginPlay node yet, one is created.
	 *
	 * @param Blueprint           the asset to modify (must be loaded).
	 * @param FunctionOwnerClass  the class that declares the function (e.g. a
	 *                            UBlueprintFunctionLibrary subclass).
	 * @param FunctionName        the C++ (reflected) name of the function.
	 * @return true ONLY if the call node was created AND wired AND the
	 *         Blueprint compiled clean (BS_UpToDate) AND the package saved.
	 *         Any other outcome returns false.
	 */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool AddBeginPlayCallNode(UBlueprint* Blueprint, UClass* FunctionOwnerClass, FName FunctionName);
};
