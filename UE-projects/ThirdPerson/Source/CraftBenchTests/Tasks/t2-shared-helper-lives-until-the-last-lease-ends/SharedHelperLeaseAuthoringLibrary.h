// Copyright CraftBench. All Rights Reserved.
// VERIFIER-ONLY readback/authoring helper.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SharedHelperLeaseAuthoringLibrary.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API USharedHelperLeaseAuthoringLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Fixed reflected ownership/API vector used by authoring and L2I. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Shared Helper")
	static FString InspectRuntimeContract();

	/** Read-only exact admission/final map identity check. */
	UFUNCTION(BlueprintCallable, Category = "CraftBench|Shared Helper", meta = (WorldContext = "WorldContextObject"))
	static FString InspectWorld(UObject* WorldContextObject);
};
