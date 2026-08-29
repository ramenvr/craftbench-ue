// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY editor authoring helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AlertStrideAssetAuthoring.generated.h"

class AAlertStrideScenario;
class UAnimBlueprint;
class UStateTree;

UCLASS()
class CRAFTBENCHTESTS_API UAlertStrideAssetAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Alert Stride")
	static bool AuthorAssetSet(
		const FString& RootPackage, const FString& InterfacePackage,
		bool bComplete, FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Alert Stride")
	static bool ConfigureScenario(
		AAlertStrideScenario* Scenario, UAnimBlueprint* Host,
		UAnimBlueprint* LayerInterface, UAnimBlueprint* CalmLayer,
		UAnimBlueprint* AlertLayer, UStateTree* StateTree,
		FString& OutMessage);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Alert Stride")
	static FString InspectWorld(UObject* WorldContextObject, bool bAdmission);
};
