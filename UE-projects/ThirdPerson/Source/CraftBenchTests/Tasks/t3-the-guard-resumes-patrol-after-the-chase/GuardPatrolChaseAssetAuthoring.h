// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY editor authoring and read-only inspection helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GuardPatrolChaseAssetAuthoring.generated.h"

class UBehaviorTree;
class UBlackboardData;

UCLASS()
class CRAFTBENCHTESTS_API UGuardPatrolChaseAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Creates a Blackboard and Behavior Tree at exact new package paths. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool AuthorDecisionAssets(
		const FString& BlackboardPackageName,
		const FString& BehaviorTreePackageName,
		bool bAuthorCompleteSolution,
		FString& OutMessage);

	/** Python-stable wrapper that preserves the native diagnostic on failure. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString AuthorDecisionAssetsText(
		const FString& BlackboardPackageName,
		const FString& BehaviorTreePackageName,
		bool bAuthorCompleteSolution);

	/** Independent engine-owned structural inspection used by authoring and L2I. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool InspectDecisionAssets(
		UBehaviorTree* BehaviorTree,
		UBlackboardData* Blackboard,
		FString& OutMessage);

	/** Python-stable wrapper that preserves the native diagnostic on failure. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectDecisionAssetsText(
		UBehaviorTree* BehaviorTree,
		UBlackboardData* Blackboard);

	/** Exact empty-but-editable task scaffold contract. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool InspectBaselineAssets(
		UBehaviorTree* BehaviorTree,
		UBlackboardData* Blackboard,
		FString& OutMessage);

	/** Python-stable wrapper that preserves the native diagnostic on failure. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectBaselineAssetsText(
		UBehaviorTree* BehaviorTree,
		UBlackboardData* Blackboard);

	/** Read-only cold-map contract; does not start or tick the fixture. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool InspectAuthoredMap(
		UObject* WorldContextObject,
		bool bAdmissionMap,
		FString& OutMessage);

	/** Python-stable wrapper that preserves the native diagnostic on failure. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectAuthoredMapText(
		UObject* WorldContextObject,
		bool bAdmissionMap);

	/** Deterministically creates/builds editor navigation after a bounds volume exists. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString BuildAdmissionNavigation(UObject* WorldContextObject);
};
