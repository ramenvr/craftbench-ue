// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WorkerPlanAssetAuthoring.generated.h"

class UStateTree;

UCLASS()
class CRAFTBENCHTESTS_API UWorkerPlanAssetAuthoring : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool AuthorStateTree(const FString& PackageName, FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool InspectStateTree(UStateTree* StateTree, FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool AuthorStateTreeShell(const FString& PackageName, FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static bool InspectStateTreeShell(UStateTree* StateTree, FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString BuildAdmissionNavigation(UObject* WorldContextObject);
};
