// Copyright CraftBench. All Rights Reserved.
// Verifier-only, read-only Animation Sharing L2I helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AlertCrowdSharingIntrospectionLibrary.generated.h"

class UAnimationSharingSetup;
class UBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UAlertCrowdSharingIntrospectionLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString InspectSharingSetup(
		const UAnimationSharingSetup* Setup,
		const UBlueprint* ProcessorBlueprint);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|AlertCrowd")
	static FString InspectStateProcessorGraph(
		const UBlueprint* ProcessorBlueprint);
};
