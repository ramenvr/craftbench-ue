// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY, AUTHORING-ONLY. The saved reference Blueprint depends only
// on ThirdPerson and Engine runtime APIs; no runtime fixture calls this class.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DistrictStreamingReferenceAuthoring.generated.h"

class UBlueprint;

UCLASS()
class CRAFTBENCHTESTS_API UDistrictStreamingReferenceAuthoring
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectEmptyBaseline(UBlueprint* Blueprint);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString InspectReferenceGraph(UBlueprint* Blueprint);

	UFUNCTION(BlueprintCallable, Category = "CraftBench|Authoring")
	static FString AuthorReferenceGraph(UBlueprint* Blueprint);
};
