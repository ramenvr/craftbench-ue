// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY MODULE - DO NOT EDIT FROM THE TASK WORKSPACE.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FilteredPointInstancesAssetAuthoring.generated.h"

class UPCGGraph;

/** Native graph/map authoring and read-only structural inspection. */
UCLASS()
class CRAFTBENCHTESTS_API UFilteredPointInstancesAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Reset a fresh graph to the protected shell or complete reference graph. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|FilteredPoints")
	static FString ConfigureGraph(UPCGGraph* Graph, bool bSolved);

	/** Exact solved-graph structural evidence used by cold readback and L2I. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|FilteredPoints")
	static FString InspectSolvedGraph(UPCGGraph* Graph);

	/** Exact answer-free baseline shell evidence. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|FilteredPoints")
	static FString InspectBaselineGraph(UPCGGraph* Graph);

	/** Read-only exact admission/final map contract. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|FilteredPoints")
	static FString InspectMap(UObject* WorldContextObject, bool bAdmission);
};
